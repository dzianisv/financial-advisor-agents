# Hierarchy: Berkshire Hathaway

## When to use
Long-duration, high-conviction single-name analysis modeled on Buffett/Munger. Use when the question is "should we own this for a decade" rather than "should we enter this setup this week." Replaces Steps 2–2.7 entirely — no 5-seat panel timing signals, no RSI/MACD gate.

## Key gate
Circle of Competence (Pre-Panel): if the analyst cannot explain in 2 sentences how the company earns money and why that will still be true in 20 years, the full panel is skipped — PASS immediately. No panel runs without competence.

---

## Pre-Panel: Circle of Competence (Buffett gate)

**Prompt — run inline before spawning any subagent:**

```
In 2 sentences, explain how {TICKER} earns money and why that will still be true in 20 years.
If you cannot answer confidently → FINAL: PASS (circle of competence boundary). Do not run the panel.
```

Output: `INSIDE_CIRCLE` or `OUTSIDE → PASS`

If OUTSIDE: write the output block as `{TICKER}: PASS — circle of competence boundary. Panel not run.` and stop here. Do not proceed.

---

## Step A: Moat Assessment

Spawn as a subagent (`/model sonnet /effort high`).

**Subagent prompt — inject verbatim, fill `{placeholders}`:**

```
You are the Moat Analyst for {TICKER}. Answer three questions in order.

1. MOAT TYPE: Name the specific moat type from this list exactly:
   brand/pricing_power | network_effect | switching_costs | cost_advantage | regulatory_licence
   If more than one applies, name the PRIMARY one. No invented categories.

2. FOUNDER TEST: "Would this moat survive if the founder retired tomorrow?" State yes or no, and name the structural mechanism that makes it founder-independent (or name the dependency that makes it founder-reliant).

3. DURABILITY: Assess the moat for 20 years, not 5. What macro, technology, or regulatory trend is most likely to erode it? Assign a durability score: DURABLE / NARROWING / ILLUSORY.

Output exactly:
MOAT TYPE: {brand/pricing_power|network_effect|switching_costs|cost_advantage|regulatory_licence}
FOUNDER INDEPENDENT: {yes|no} — {one sentence mechanism}
DURABILITY: {DURABLE|NARROWING|ILLUSORY}
MOAT MEMO: {2 sentences: controlling durability factor and what would change this assessment}

Inputs: {DATA_PACKAGE_JSON} | {MACRO_REGIME}
```

**Gate:** ILLUSORY → FINAL: PASS. Write `{TICKER}: PASS — moat assessed ILLUSORY ({MOAT_MEMO}).` Do not proceed.

Cache output: `echo '{moat_json}' > "$RUN_DIR/{TICKER}/seat_moat.json"`

---

## Step B: Management Quality

Spawn as a subagent (`/model sonnet /effort high`).

**Subagent prompt — inject verbatim, fill `{placeholders}`:**

```
You are the Management Analyst for {TICKER}. Assess capital allocation and honesty.

CAPITAL ALLOCATION RECORD:
  - Were buybacks executed at reasonable prices (below intrinsic value) or at cycle peaks?
  - Were acquisitions bolt-on (adjacent, clear synergy) or empire-building (size for size)?
  - Name one specific capital allocation decision (with year) that reveals management's instincts.

HONESTY SIGNALS:
  - Goodwill impairments: has management written down past acquisitions, or is goodwill growing faster than book value? (check fundamentals.py data)
  - Options grants vs. book value growth: are executives paid in stock while book value stagnates?
  - Owner-letter transparency: do shareholder letters name mistakes and explain them, or are they marketing?
  Cite one specific signal per bullet (with year or filing reference).

Output exactly:
CAPITAL ALLOCATION: {DISCIPLINED|MIXED|EMPIRE_BUILDING} — {one sentence with the named example}
HONESTY: {HIGH|MEDIUM|LOW} — {one sentence with the named signal}
MANAGEMENT VERDICT: {HONEST_CAPABLE|CAPABLE_ONLY|PASS}
MANAGEMENT MEMO: {1 sentence: the single most important thing this assessment reveals}

Inputs: {DATA_PACKAGE_JSON} | {MACRO_REGIME}
```

**Gate:** PASS → FINAL: PASS. Write `{TICKER}: PASS — management verdict PASS ({MANAGEMENT_MEMO}).` Do not proceed.

Cache output: `echo '{mgmt_json}' > "$RUN_DIR/{TICKER}/seat_mgmt.json"`

---

## Step C: Munger Inversion ("Invert, always invert")

Spawn as a subagent (`/model sonnet /effort high`).

**Subagent prompt — inject verbatim, fill `{placeholders}`:**

```
You are the Munger Inverter for {TICKER}. Invert, always invert.

NAME 3 SPECIFIC FAILURE MODES — not generic risks. Each must be:
  (a) A real competitive threat (name the specific competitor or technology)
  (b) A real regulatory risk (name the specific jurisdiction, law, or agency)
  (c) A real balance-sheet trap (name the specific liability, covenant, or maturity wall)

FOR EACH FAILURE MODE, Buffett must rebut with a specific reason it does NOT invalidate the 20-year thesis:
  - A rebuttal is a structural argument, not "management is good" or "the sector is growing."
  - If a failure mode has no structural rebuttal → that is a KILLER, not a headwind.

Output exactly:
FAILURE MODE 1 (competitive): {specific threat} | REBUTTAL: {structural argument or KILLER_FOUND}
FAILURE MODE 2 (regulatory): {specific risk} | REBUTTAL: {structural argument or KILLER_FOUND}
FAILURE MODE 3 (balance sheet): {specific trap} | REBUTTAL: {structural argument or KILLER_FOUND}
INVERSION VERDICT: {CLEAR|KILLER_FOUND}
If KILLER_FOUND: state which failure mode killed the thesis and why the rebuttal failed.

Inputs: {DATA_PACKAGE_JSON} | {MOAT_JSON} | {MGMT_JSON}
```

**Gate:** KILLER_FOUND → FINAL: PASS with reason. Write `{TICKER}: PASS — Munger inversion KILLER_FOUND: {failure mode + reason}.` Do not proceed.

Cache output: `echo '{inversion_json}' > "$RUN_DIR/{TICKER}/seat_inversion.json"`

---

## Step D: Margin of Safety (Graham/Buffett)

Run inline (not a subagent) using the data package already loaded.

**Inline prompt — fill `{placeholders}`:**

```
Estimate intrinsic value for {TICKER} using owner earnings (not GAAP net income).

OWNER EARNINGS = net income + depreciation/amortization − maintenance capex
  Use fundamentals.py fields: fcf (proxy for owner earnings if capex breakdown unavailable), market_cap, revenue_growth, operating_margin.

10-YEAR DCF (conservative inputs only):
  - Growth rate: min(revenue_growth from fundamentals.py, 10%) for years 1–5; half that for years 6–10
  - Terminal growth: 3% (GDP-level, do not exceed)
  - Discount rate: 8% (Buffett's minimum hurdle — do not lower it)

INTRINSIC VALUE = DCF result in $ per share
CURRENT PRICE = price from fundamentals.py
DISCOUNT = (intrinsic_value − current_price) / intrinsic_value × 100

Sizing gate:
  < 25% discount → WATCH (not BUY; wait for a better price — Berkshire waits years)
  ≥ 25% discount → proceed to Step E (Conviction Sizing)

Output:
OWNER_EARNINGS_PER_SHARE: ${amount}
INTRINSIC_VALUE: ${amount}
CURRENT_PRICE: ${price}
DISCOUNT_PCT: {N}%
VERDICT: {BUY_CANDIDATE (≥25%) | WATCH (< 25%)}
MARGIN_MEMO: {1 sentence: what assumption most affects the intrinsic value estimate}
```

**Gate:** WATCH → final verdict is WATCH. Write `{TICKER}: WATCH — discount {N}% below 25% threshold. Intrinsic value ${IV}; wait for the price.`

Cache output: `echo '{mos_json}' > "$RUN_DIR/{TICKER}/seat_mos.json"`

---

## Step E: Conviction Sizing

Run inline after all prior steps pass.

**Inline logic — apply directly:**

```
All gates cleared (INSIDE_CIRCLE, moat not ILLUSORY, management not PASS, inversion CLEAR, discount ≥ 25%) → BUY.

SIZING RULES (Berkshire-specific — concentration is a feature, not a risk):
  Minimum position: 5% of portfolio. No half-positions. If 5% would breach cash floor → WATCH until cash frees.
  Exceptional criteria (BOTH must be true): moat DURABLE AND discount ≥ 40% → up to 15% of portfolio.
  Default: 5–10% based on moat durability and discount depth.

HOLD_FOREVER intent: default exit condition is thesis break ONLY:
  - Moat assessed ILLUSORY (re-run Step A annually)
  - Management assessed DISHONEST (re-run Step B on each earnings release)
  Never sell on price decline. Price decline + intact thesis = re-examine sizing upward.

Berkshire hard constraints (enforced here, not in Risk Manager):
  - No short selling, no leverage, no options
  - P/E ratio is irrelevant if moat is real and management reinvests intelligently
  - Diversification is NOT a goal — conviction and margin of safety are the goal

Output:
POSITION_SIZE_PCT: {5–15}%
POSITION_SIZE_$: {dollar amount at current book size}
HOLD_FOREVER: true
EXIT_CONDITIONS: moat becomes ILLUSORY | management becomes DISHONEST
```

Cache output: `echo '{sizing_json}' > "$RUN_DIR/{TICKER}/seat_sizing.json"`

---

## Output shape

```
FINAL VERDICT: {BUY|WATCH|PASS}
POSITION SIZE: {5–15}% / ${dollar amount}   or "n/a"
HOLD FOREVER: true (exit only on thesis break)
MOAT: {type} — {DURABLE|NARROWING|ILLUSORY}
MANAGEMENT: {HONEST_CAPABLE|CAPABLE_ONLY|PASS}
INVERSION: {CLEAR|KILLER_FOUND — reason}
INTRINSIC VALUE: ${amount} | DISCOUNT: {N}%
EXIT CONDITIONS: moat ILLUSORY | management DISHONEST
BERKSHIRE MEMO: {1 sentence: why this is a 20-year hold or why it isn't}
```

No P0/P1/P2/P3 table — Berkshire hierarchy produces a HOLD_FOREVER BUY or a WATCH. Urgency is irrelevant; margin of safety and thesis integrity are the only clocks.
