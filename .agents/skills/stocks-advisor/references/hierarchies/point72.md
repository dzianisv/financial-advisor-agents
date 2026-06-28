# Hierarchy: Point72 (Cohen)

## When to use
Short-to-medium duration equity ideas that require a named informational or analytical edge before consuming any analytical resources. Use when running a high-throughput idea filter across many names — the edge validator eliminates weak ideas cheaply before the conviction scorer spends time on them.

## Key gate
Edge Validator (Pre-Panel): analyst must articulate why they know something others don't. Edge score below 3/5 → REJECT immediately. No panel runs without a named edge.

---

## Pre-Panel: Edge Validator

Run inline before spawning any subagent.

**Inline prompt — fill `{placeholders}`:**

```
Edge Validator for {TICKER}: answer one question before any research runs.

"Why do I know something about {TICKER} that other market participants do not, or have not yet priced?"

Name the edge and score it 1–5:
  5 — hard-to-replicate proprietary signal (primary source, supply chain check, expert network)
  4 — analytical advantage on public data (misread earnings quality, segment mix, channel check)
  3 — timing advantage on known catalyst (event date known, market hasn't positioned)
  2 — consensus view with better execution timing (no differentiation on the idea itself)
  1 — "I have a feeling" / narrative momentum / no articulable edge

EDGE TYPE: {INFORMATION|ANALYTICAL|TIMING|STRUCTURAL|NONE}
EDGE STATEMENT: "{one sentence: what specifically do I know and why haven't others priced it?}"
EDGE SCORE: {1–5}

Gate: score < 3 → REJECT. Write "{TICKER}: REJECT — edge score {N}/5 ({EDGE_STATEMENT}). Not worth PM time."
```

Output: `EDGE_SCORE / EDGE_TYPE / EDGE_STATEMENT` or `REJECT`

Do not proceed past Pre-Panel if REJECT.

---

## Step A: Conviction Scorer (PM seat)

Spawn as a subagent (`/model sonnet /effort high`).

**Subagent prompt — inject verbatim, fill `{placeholders}`:**

```
You are the PM Conviction Scorer for {TICKER} (edge: {EDGE_TYPE} — "{EDGE_STATEMENT}").

IDEA SCORE (1–10): Score this idea on four dimensions, then average:
  (a) Quality of edge: does the edge hold up on inspection, or does it dissolve into consensus?
      Edge score from pre-panel: {EDGE_SCORE}/5. Map to idea dimension: 5→10, 4→8, 3→6.
  (b) Fundamental quality: revenue growth trajectory, FCF positive, moat present?
      Use: {DATA_PACKAGE_JSON} — forward_pe, revenue_growth, fcf_yield, gross_margin.
  (c) Technical setup: is the chart set up (above trend, not extended, named setup)?
      Use: {DATA_PACKAGE_JSON} — vs_200d_ma, dd_from_52wh, rsi (if available).
  (d) Sizing fit: does adding this name reduce concentration, fill a theme gap, or add redundancy?
      Evaluate against current portfolio factor exposures: {FACTOR_MAP}.

PORTFOLIO FIT CHECK: Would this position:
  - Fill a theme gap in the current book? {yes|no — which gap}
  - Create redundant AI/rates/USD factor exposure? {yes|no — which overlap}
  - Push any single factor above 25% of book? {yes|no — which factor}

Output exactly:
IDEA_SCORE: {1–10}  (average of four dimensions above)
DIMENSION SCORES: edge={N}, fundamental={N}, technical={N}, fit={N}
PORTFOLIO FIT: {ADDITIVE|REDUNDANT|CONCENTRATION_RISK}
PM VERDICT: {SEND_TO_COHEN (≥7, ADDITIVE or ok fit) | WATCH (5–6) | REJECT (<5 or CONCENTRATION_RISK)}
PM MEMO: {1 sentence: the controlling factor in this score}

Inputs: {DATA_PACKAGE_JSON} | {EDGE_STATEMENT} | {EDGE_SCORE} | {FACTOR_MAP} | {MACRO_REGIME}
```

**Gate:** REJECT → final verdict is REJECT. WATCH → register alert via `mkt` skill and stop here. SEND_TO_COHEN → proceed to Step B.

Cache output: `echo '{pm_json}' > "$RUN_DIR/{TICKER}/seat_pm.json"`

---

## Step B: Risk Overlay

Run inline after PM returns SEND_TO_COHEN.

**Inline prompt — fill `{placeholders}`:**

```
Risk Overlay for {TICKER} (PM score: {IDEA_SCORE}/10).

FACTOR EXPOSURE: Identify the primary risk factor this name loads on:
  {Fed/rates | USD | oil | AI-capex | China-exposure | credit-spreads | OTHER}
  Current factor weight in portfolio: {FACTOR_WEIGHT}%. After adding {PROPOSED_SIZE}%: {NEW_WEIGHT}%.
  Gate: new factor weight > 25% → flag CONCENTRATION_WARNING (PM can override with Cohen approval).

DRAWDOWN BUDGET: What is the maximum dollar loss this position can produce before it consumes more than {DRAWDOWN_BUDGET_PCT}% of the quarterly P&L budget?
  Formula: stop_distance × proposed_shares × price = max_dollar_loss
  State the implied stop price given the drawdown budget constraint.

STOP LOGIC: Name a market-based stop (not a % from entry — a structural level):
  - Below a key support level (52w low, prior breakout, 200d MA) — which one and why
  - State: "Stop fires on daily close below ${level} ({rationale})"

Output:
FACTOR: {type} | CURRENT_WEIGHT: {pct}% | AFTER_ADD: {pct}% | CONCENTRATION_WARNING: {yes|no}
DRAWDOWN_BUDGET_STOP: ${price} (max loss ${dollar_amount})
MARKET_BASED_STOP: close below ${level} ({rationale})
RISK_STATUS: {CLEAR | CONCENTRATION_WARNING (Cohen can override)}

Inputs: {PM_JSON} | {DATA_PACKAGE_JSON} | {PORTFOLIO_FACTOR_MAP} | {DRAWDOWN_BUDGET_PCT}
```

Cache output: `echo '{risk_json}' > "$RUN_DIR/{TICKER}/seat_risk.json"`

---

## Step C: Cohen Seat (adversarial override)

Spawn as a subagent (`/model sonnet /effort high`). Cohen reads the PM memo and the Risk Overlay, then probes adversarially and decides.

**Subagent prompt — inject verbatim, fill `{placeholders}`:**

```
You are the Cohen seat for {TICKER}. You have unilateral override authority — you can APPROVE, REJECT, or SIZE_DOWN at will, for any reason or no reason. Your instinct is a data point.

READ: PM Conviction Score ({IDEA_SCORE}/10), Portfolio Fit ({PORTFOLIO_FIT}), Risk Status ({RISK_STATUS}).

ADVERSARIAL PROBE — answer these before deciding:
  "What's the bear case that the PM is not pricing?"
    Name one scenario (with probability 1–20%) where this idea loses 40%+ within 6 months.
  "Is the edge real or is it narrative momentum?"
    State in one sentence whether the {EDGE_TYPE} edge will still exist in 30 days.
  "What does the market know that we don't?"
    Name one signal in the data package ({DATA_PACKAGE_JSON}) that cuts against the thesis.

COHEN DECISION:
  APPROVE → trade proceeds at PM-scored size
  SIZE_DOWN {N}% → approve but reduce proposed size by N% (state the reason)
  REJECT → kill the trade (state the single controlling reason, one sentence)

Output exactly:
BEAR_CASE: {scenario, probability, max loss}
EDGE_CHECK: {real|narrative} — {one sentence}
MARKET_SIGNAL: {one data point that cuts against the thesis}
COHEN_DECISION: {APPROVE | SIZE_DOWN {N}% | REJECT}
COHEN_MEMO: {1 sentence: controlling factor in the decision}

Inputs: {PM_JSON} | {RISK_JSON} | {DATA_PACKAGE_JSON} | {MACRO_REGIME}
```

Cache output: `echo '{cohen_json}' > "$RUN_DIR/{TICKER}/seat_cohen.json"`

---

## Output shape

```
FINAL VERDICT: {TRADE|WATCH|REJECT}
EDGE: {INFORMATION|ANALYTICAL|TIMING|STRUCTURAL} score {N}/5 — "{edge statement}"
IDEA SCORE: {N}/10 (edge={N}, fundamental={N}, technical={N}, fit={N})
COHEN DECISION: {APPROVE|SIZE_DOWN N%|REJECT} — {one sentence}
CONVICTION SIZE: {conviction-scaled % of book}
STOP: close below ${level} ({rationale})
BEAR CASE: {scenario, probability}
PORTFOLIO FIT: {ADDITIVE|REDUNDANT|CONCENTRATION_RISK}
```

Execution table entry: P0/P1/P2/P3 row with conviction-scaled share count and Cohen's stop level as the falsification trigger.
