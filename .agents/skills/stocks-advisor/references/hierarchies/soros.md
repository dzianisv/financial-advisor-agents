# Hierarchy: Soros (Quantum)

## When to use
Macro-reflexivity-driven positions where the trade thesis is as much about the market's self-reinforcing feedback loop as it is about underlying fundamentals. Use when a position is large enough to influence the price itself, or when the setup requires explicit P0/P1/P2/P3 execution staging with hard triggers.

## Key gate
Macro Thesis Frame (Pre-Panel): analyst must articulate the reflexivity hypothesis — how does participant belief change the underlying, and how does that change feed back into belief? No generic macro thesis; the feedback loop must be named.

---

## Pre-Panel: Macro Thesis Frame

Run inline before spawning any subagent.

**Inline prompt — fill `{placeholders}`:**

```
Macro Thesis Frame for {TICKER}: state the reflexivity hypothesis.

Reflexivity (Soros): a two-way feedback loop where market participant beliefs change the underlying reality, which then changes participant beliefs, creating a self-reinforcing process until it reverses.

THESIS STATEMENT: "The reflexive loop for {TICKER} is: [how does rising/falling price change the underlying business or macro variable?] → [how does that change in the underlying reinforce or reverse the price move?] → [what breaks the loop?]"

PHASE: {BOOM (loop self-reinforcing, ride it) | BUST (loop self-reinforcing on downside, short or exit) | TURNING (loop about to reverse, critical juncture)}

FALSIFICATION: "This thesis is wrong if [specific observable condition that breaks the loop — a fundamental, a policy decision, a positioning metric, a price level]."

Output:
REFLEXIVITY_HYPOTHESIS: {one paragraph, specific}
PHASE: {BOOM|BUST|TURNING}
FALSIFICATION: {one sentence, named observable condition}
THESIS_STRENGTH: {STRONG (specific, testable loop) | WEAK (generic macro story) | REJECT (no loop identified)}

Gate: THESIS_STRENGTH = WEAK or REJECT → PASS. Write "{TICKER}: PASS — no reflexive loop identified; this is a generic macro story, not a Soros-style position."
```

Output: `REFLEXIVITY_HYPOTHESIS / PHASE / FALSIFICATION / THESIS_STRENGTH`

Do not proceed if THESIS_STRENGTH is WEAK or REJECT.

---

## Step A: Trade Expression

Run inline after the Macro Thesis Frame passes.

**Inline prompt — fill `{placeholders}`:**

```
Trade Expression for {TICKER} (phase: {PHASE}, loop: "{REFLEXIVITY_HYPOTHESIS}").

INSTRUMENT SELECTION: Which instrument best expresses the thesis?
  Equity long/short | options (name the structure) | ETF (name it) | futures
  Explain why this instrument captures the reflexive payoff, not just directional exposure.

INITIAL SIZING: Express position as % of book.
  Soros sizing logic: start small (1–3%), size UP as the market confirms the thesis (not before).
  Never size the full conviction at entry — position is earned by confirmation, not assumed at open.

STOP LOGIC: Name the stop as a falsification event, not a price percentage:
  "Stop fires when [the falsification condition from the Macro Thesis Frame fires]."
  Translate to a price level only as a secondary indicator: "which corresponds approximately to ${level}."

ENTRY: State the initial entry zone (not a precise price — a zone where the thesis is still cheap):
  "${low}–${high} — thesis is mispriced at this level because [one sentence]."

Output:
INSTRUMENT: {type + rationale}
INITIAL_SIZE: {1–3}% of book
ENTRY_ZONE: ${low}–${high}
STOP_EVENT: {named falsification event} (approx. ${price})
EXPRESSION_MEMO: {1 sentence: why this instrument/size captures the reflexive payoff}

Inputs: {REFLEXIVITY_HYPOTHESIS} | {PHASE} | {FALSIFICATION} | {DATA_PACKAGE_JSON}
```

Cache output: `echo '{expression_json}' > "$RUN_DIR/{TICKER}/seat_expression.json"`

---

## Step B: Position Monitor Logic

Spawn as a subagent (`/model sonnet /effort high`).

**Subagent prompt — inject verbatim, fill `{placeholders}`:**

```
You are the Position Monitor for {TICKER} (initial size: {INITIAL_SIZE}%, entry: ${ENTRY_ZONE}).

Soros rule: "if the market confirms, ADD; if it contradicts, re-examine — not double-down."

CONFIRMATION SIGNALS (define before entering — what does "market confirms" look like?):
  Price confirmation: "{TICKER} closes above ${level} on above-average volume for {N} consecutive sessions."
  Fundamental confirmation: "{named metric} moves in direction predicted by reflexive loop."
  Positioning confirmation: "Short interest / put-call / sentiment indicator moves to {value}."

CONTRADICTION SIGNALS (define before entering — what does "market contradicts" look like?):
  Price contradiction: "{TICKER} closes below ${stop_level} or reverses {N}% from high on volume."
  Fundamental contradiction: "{named metric} moves opposite to the reflexive loop prediction."
  Positioning contradiction: "Smart money exits (13F reduction or insider selling above ${level})."

ADD RULE: If ALL confirmation signals fire → ADD {increment}% (new total: up to {MAX_SIZE}% of book).
  Never add on thesis alone — confirmation must be observable, not inferred.

RE-EXAMINE RULE: If ANY contradiction signal fires → pause all adds, re-run Step A (Macro Thesis Frame).
  Do not double-down. Re-examine = fresh analysis, not defense of existing position.
  If re-examination returns WEAK or REJECT → EXIT at market.

Output:
CONFIRMATION_SIGNALS: [{signal 1}, {signal 2}, {signal 3}]
CONTRADICTION_SIGNALS: [{signal 1}, {signal 2}, {signal 3}]
ADD_TRIGGER: {specific condition} → +{increment}% (max total: {MAX_SIZE}%)
RE_EXAMINE_TRIGGER: {specific condition} → pause + re-run thesis
EXIT_TRIGGER: thesis re-examined and returns WEAK or REJECT → EXIT at market

Inputs: {EXPRESSION_JSON} | {REFLEXIVITY_HYPOTHESIS} | {DATA_PACKAGE_JSON} | {MACRO_REGIME}
```

Cache output: `echo '{monitor_json}' > "$RUN_DIR/{TICKER}/seat_monitor.json"`

---

## Step C: Reflexivity Gate

Run inline. Applies to all positions above 5% of book — Soros's own self-limiting discipline.

**Inline prompt — fill `{placeholders}`:**

```
Reflexivity Gate for {TICKER} (current size: {CURRENT_SIZE}%, book: ${BOOK}).

Soros principle: a position large enough to move the market itself changes the thesis — you are no longer analyzing the instrument, you are analyzing your own impact on it.

MARKET IMPACT TEST:
  ADV = {avg_daily_volume} shares/day (from data package)
  Proposed position: {shares} shares
  Entry_days = ceil(shares / (ADV × 0.10))  ← 10% of ADV limit to avoid moving price
  If entry_days > 5: position is TOO LARGE for quiet entry → THROTTLE to {adjusted_shares} shares.

SELF-FULFILLING CHECK:
  "Is our public thesis or position size large enough that other participants are likely reacting to us?"
  Threshold: size > 1% of free-float OR position disclosed in a 13F filed this quarter → YES.
  If YES → CLOSE or reduce to below threshold; the reflexive loop is now about us, not the underlying.

Output:
ADV: {shares/day}
ENTRY_DAYS_AT_FULL_SIZE: {N} days
THROTTLE_REQUIRED: {yes|no}
ADJUSTED_SIZE: {shares at 10% ADV × 5-day limit} or "no change"
SELF_FULFILLING: {yes|no}
GATE_VERDICT: {PROCEED | THROTTLE | CLOSE}

Inputs: {EXPRESSION_JSON} | {DATA_PACKAGE_JSON} | {CURRENT_SIZE_PCT}
```

Cache output: `echo '{reflex_gate_json}' > "$RUN_DIR/{TICKER}/seat_reflex_gate.json"`

---

## Step D: P0/P1/P2/P3 Execution Table

Mandatory output — no Soros hierarchy result is complete without a staged execution table. Build from the prior steps. Run inline.

**Construct the execution table from these inputs:**
- Initial entry (Step A): entry zone, initial size, stop event
- Add triggers (Step B): confirmation signals → add increment
- Re-examine triggers (Step B): contradiction signals → pause
- Gate verdict (Step C): throttle adjustments

```
EXECUTION TABLE — {TICKER} — {DATE}
Priority  Action         Shares   Entry zone    Trigger                       Port %   Falsification
--------  ------         ------   ----------    -------                       ------   -------------
P0        EXIT / SHORT   all      market open   [thesis break already fired — name the event]
P1        ENTER initial  {N}shr   ${low–high}   [confirmation signal 1]        +{X}%   [falsification event]
P2        ADD            {N}shr   mkt confirm   [all 3 confirmation signals]   +{X}%   [contradiction signal fires]
P3        ADD MAX        {N}shr   deep confirm  [fundamental + price confirm]  +{X}%   [self-fulfilling gate fires]
```

Priority rules:
- **P0** — act at open, no conditions. Only if a falsification event has already fired (loop broken, contradiction confirmed). No P0 without a named event already observed.
- **P1** — initial entry. Size: 1–3% of book. Trigger: first confirmation signal fires. Falsification: the named stop event.
- **P2** — first add. Size: +2–4% of book (total ≤ 7%). Trigger: all 3 confirmation signals confirmed. Falsification: any contradiction signal fires.
- **P3** — max size. Size: up to {MAX_SIZE}% of book total. Trigger: fundamental confirmation + consecutive price closes above level. Falsification: reflexivity gate re-runs and returns THROTTLE or CLOSE.

**Share count rule:** use Risk Manager APPROVED size ($amount) ÷ entry_zone_high. Round to nearest 5 shares. State dollar amount alongside share count.

---

## Output shape

```
FINAL VERDICT: {ENTER|WATCH|PASS}
REFLEXIVITY HYPOTHESIS: {one paragraph — specific loop, not generic macro}
PHASE: {BOOM|BUST|TURNING}
INSTRUMENT: {type + rationale}
INITIAL SIZE: {1–3}% / ${dollar amount}
STOP EVENT: {named falsification event} (approx ${price})
CONFIRMATION SIGNALS: [{1}, {2}, {3}]
CONTRADICTION SIGNALS: [{1}, {2}, {3}]
REFLEXIVITY GATE: {PROCEED|THROTTLE|CLOSE}

EXECUTION TABLE:
P0 | P1 | P2 | P3 — share counts, entry zones, triggers, falsification conditions (see Step D)
```

P0 fires only on a confirmed loop break. P3 is earned by market confirmation — never assumed at entry.
