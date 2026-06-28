# Hierarchy: Bridgewater

## When to use
Baseline Bridgewater architecture — the original 23/25-scoring panel design. No edge gate, no citation tagging, no hard dollar-impact requirement on tail stress. Use when running a lighter adversarial pass without the Point72-derived edge filter layered on top.

## Key gate
Skeptic (Step A): the mandatory institutional adversary who must name a real historical analog and a specific tail scenario. Ideas survive only if the CIO can rebut the Skeptic's strongest argument with evidence.

---

## Step A: Skeptic

The analyst panel is the proposal. The Skeptic is the mandatory institutional adversary — assigned, not volunteer. It runs on every ticker regardless of how bullish the panel looks. Never skip this step. Spawn as a subagent (`/model sonnet /effort high`).

**Skeptic subagent prompt — inject verbatim, fill `{placeholders}`:**

```
You are the Skeptic for {TICKER}. Your role is mandatory: find the strongest case AGAINST the consensus, even if you privately agree with the analysts.

GAP ANALYSIS: Name the single biggest blind spot across all 5 analyst verdicts — data they had but underweighted, or a dimension none of them checked.
TAIL RISK: Name one specific, non-generic downside scenario. Assign a probability (1–15%) and the expected loss magnitude if it fires. No generics like "macro deterioration."
HISTORICAL ANALOG: One real failed trade with a structurally identical setup — same thesis type, same narrative phase, same sentiment read. Exact company, year, outcome. No fabricated cases.

INVALIDATION CONDITIONS (all three required before any BUY advances):
  (a) {falsifiable condition — a specific price level, ratio, or filing event that proves the thesis wrong}
  (b) {falsifiable condition 2}
  (c) {falsifiable condition 3}

PORTFOLIO TAIL STRESS: Qualitatively assess the dollar impact of a severe drawdown (–30% to –50%) at the current proposed weight. State: what weight are we considering, and how painful would a halving be at that size?

SKEPTIC VERDICT: {SKIP | WATCH | BUY} — {one sentence explaining the controlling factor}
Inputs: {ALL_5_SEAT_VERDICTS_JSON} | {MACRO_REGIME}
```

Cache output: `echo '{skeptic_json}' > "$RUN_DIR/{TICKER}/seat_skeptic.json"`

---

## Step B: CIO Synthesis

The CIO reads all 5 analyst verdicts plus the Skeptic's challenge and makes the final call. Cannot abstain. Spawn as a subagent (`/model sonnet /effort high`). Apply with judgment, not mechanically.

**CIO subagent prompt — inject verbatim, fill `{placeholders}`:**

```
You are the CIO for {TICKER}. Read all 5 analyst verdicts and the Skeptic challenge. You cannot abstain.

CIRCLE OF COMPETENCE: State in 2 sentences how {TICKER} earns money and why competitors cannot replicate it. If you cannot → FINAL VERDICT: PASS. Stop here.
SKEPTIC RESPONSE: Address the Skeptic's single strongest argument — rebut with evidence, or accept it and explain why you invest despite it.
VERDICT (believability-weighted: fundamental/narrative 2×, technical 2×):
  BUY requires: Fundamental ≥ GOOD, named setup + live bar-close trigger, narrative not LATE/FADING, Sentiment ≠ EXTREME.
  Holdings path: ADD/HOLD/TRIM/EXIT when cost basis is known (EXIT: POOR/FADING/BROKEN; TRIM: weight>15%/EXTREME/LATE; ADD: BUY gate + room; HOLD: else).
  Conviction (start 3): +1 ≥3 seats; +1 EARLY+QUIET; −1 CROWDED; −1 PEG>2/neg FCF; −1 LATE; +1 SM-accum (≥2 seats); −1 SM-distrib (caps BUY at 3). Clamp 1–5.

Output exactly:
FINAL VERDICT: {BUY|WATCH|SKIP}  or {ADD|HOLD|TRIM|EXIT}
CONVICTION: {1–5}/5
DISSENT LOGGED: {Skeptic's best objection in one sentence — printed even when overruled}
CIO MEMO: {1 paragraph: controlling factor, Skeptic right/wrong and why, one fact that would change this call}
Inputs: {ALL_5_VERDICTS_JSON} | {SKEPTIC_JSON} | {MACRO_REGIME}
```

> Source: Surowiecki, *Wisdom of Crowds* (2004) — domain-weighted aggregation (believability by demonstrated track record) consistently outperforms equal-vote averaging. Bridgewater ILC design principle: every open position has a standing institutional adversary; the Skeptic role encodes this structurally.

**A WATCH verdict is an alert trigger.** Register via the `mkt` skill with the CIO Memo as the thesis string. No P0/P1/P2/P3 execution table — Bridgewater hierarchy produces a verdict and conviction score; execution tabling is the orchestrator's job, not this panel's.

Cache output: `echo '{cio_json}' > "$RUN_DIR/{TICKER}/seat_cio.json"`

---

## Step C: Risk Manager

Skip entirely when CIO verdict is WATCH, SKIP, HOLD, TRIM, EXIT, or PASS. Checks portfolio-level constraints only — thesis quality is the CIO's job. Run this inline (not a subagent) using the portfolio data already loaded.

**Risk Manager check prompt — run inline, fill `{placeholders}`:**

```
You are the Risk Manager for {TICKER} (CIO: {BUY|ADD}, conviction: {N}/5). Check constraints only — not thesis quality. First breach blocks, no override.
Rule 1: Position ≥ 10% of book → BLOCKED: "concentration cap — no ADD until trimmed below 8%."
Rule 2: Primary factor group ≥ 25% of book → BLOCKED: "factor concentration limit."
Rule 3: Cash < $2,000 → BLOCKED: "insufficient cash for minimum position."
Rule 4: Conviction ≤ 2/5 → BLOCKED: "below minimum conviction threshold."
If no rule fires → APPROVED.
Position size (APPROVED): conviction × 2% × total_book, capped at (10% − current_weight).
  5/5 → 10% target; 4/5 → 6%; 3/5 → 4%. Subtract current weight for the add size.

Output:
STATUS: {APPROVED | BLOCKED}
POSITION SIZE: {$amount, % of book} or "n/a"
REASON: {rule fired, or "all constraints clear — factor headroom: {pct}%"}
Portfolio inputs: current_weight={W}%, factor_group={F}, factor_group_weight={FW}%, cash=${CASH}, total_book=${BOOK}
```

**Verdict flow:** if APPROVED → CIO verdict stands; if BLOCKED → downgrade to WATCH (thesis intact, constraint violated). Log the block reason in the final output block.

Cache output: `echo '{risk_json}' > "$RUN_DIR/{TICKER}/seat_risk.json"`

> Source: Carver, *Systematic Trading*, Ch.4 — concentration limits (≤10% single name, ≤25% factor group) are the primary structural protection against idiosyncratic drawdown; stops alone are insufficient.

---

## Output shape

```
FINAL VERDICT: {BUY|WATCH|SKIP|PASS}   or {ADD|HOLD|TRIM|EXIT}
CONVICTION: {1–5}/5
DISSENT LOGGED: {Skeptic's best objection — printed even when overruled}
CIO MEMO: {1 paragraph: controlling factor + what one fact would change this call}
Risk status: {APPROVED $X (N% book) | BLOCKED: reason | N/A (not BUY/ADD)}
Invalidation: {3 falsifiable conditions from Skeptic}
```

WATCH verdict registers an alert via the `mkt` skill — no P0/P1/P2/P3 table in this hierarchy; the orchestrator handles execution priority from CIO verdict + conviction score directly.
