# Crypto-Advisor Eval Rubric

7 dimensions, each scored 0–5. All anchors are concrete and verifiable against SKILL.md.

Stop condition: mean holdout ≥ 4.2 AND no dimension below 3.0, OR 3 rounds completed (whichever first).

---

## Score Anchors (global)

| Score | Meaning |
|-------|---------|
| 5 | Perfect — no deviation from SKILL.md rule |
| 4 | Correct approach, minor gap (one edge case missed, wording slightly off) |
3 | Right direction, soft on specifics or misses one named requirement |
| 2 | Partial — gets roughly half right; material omission or error |
| 1 | Mostly wrong — violates the principle more than it follows it |
| 0 | Violates the principle outright |

---

## Dimension 1 — signal_correctness

**What it tests:** quorum_verdict truth table applied correctly; signal decision rule applied correctly.

**Truth table (from SKILL.md `quorum_verdict mapping`):**

| seats_bull | seats_bear | Expected verdict |
|------------|------------|-----------------|
| ≥3         | ≤1         | BULLISH         |
| ≥3         | ≥2         | SPLIT           |
| 2          | ≤1         | SPLIT           |
| ≤1         | ≥3         | BEARISH         |
| anything else | —       | UNCERTAIN       |

**Signal decision (from Step 2):**

| Signal | Condition |
|--------|-----------|
| BUY | quorum=BULLISH, seats_bull≥3, zone∈{DEEP_VALUE,FAIR_VALUE} |
| HOLD (await pullback) | quorum=BULLISH, seats_bull≥3, zone=ELEVATED |
| HOLD (extended, avoid) | quorum=BULLISH, seats_bull≥3, zone=EXTREME |
| BUY (small) | quorum=SPLIT, zone=DEEP_VALUE |
| SELL | quorum=BEARISH, seats_bear≥4 |
| HOLD | everything else (including zone=UNKNOWN) |

**Anchors:**

- **5** — truth table applied exactly; signal rule applied exactly; all intermediate steps shown (count seats_bull/bear → verdict → zone check → signal)
- **4** — correct verdict and signal; one step not shown explicitly or minor notation off
- **3** — correct final signal but truth table mapping stated ambiguously or zone check mentioned without applying it
- **2** — correct on verdict OR signal but wrong on the other; or one material mis-classification
- **1** — both verdict and signal wrong, or the rule applied backward
- **0** — no attempt to use the truth table; signal pulled from thin air

---

## Dimension 2 — zone_discipline

**What it tests:** zone guard enforced before signal; BUY blocked when zone=ELEVATED/EXTREME/UNKNOWN; BUY(small) blocked when zone≠DEEP_VALUE.

**Key rules from SKILL.md:**
- zone=UNKNOWN **blocks** BUY and BUY(small); signal must be HOLD
- zone=ELEVATED/EXTREME → downgrade BULLISH to HOLD with the named note
- BUY(small) requires zone=DEEP_VALUE (not FAIR_VALUE, not ELEVATED, not UNKNOWN)

**Anchors:**

- **5** — zone checked before signal; all guards enforced; correct note printed ("await pullback" / "extended, avoid" / "data gate: UNKNOWN")
- **4** — zone guard applied correctly; named note slightly different from SKILL.md wording
- **3** — zone guard applied but only for the obvious case (e.g. UNKNOWN blocks BUY), misses BUY(small) restriction or ELEVATED downgrade note
- **2** — zone mentioned but guard not applied; or guard inverted (e.g., BUY(small) issued in FAIR_VALUE zone)
- **1** — zone computed but ignored in signal decision
- **0** — zone not checked; signal issued without zone validation

---

## Dimension 3 — data_sufficiency

**What it tests:** 200wMA marked INSUFFICIENT when weekly_closes<200; fallback data tagged; zone forced UNKNOWN when data insufficient.

**Key rules from SKILL.md (DATA SUFFICIENCY GATE):**
- `weekly_closes < 200` → `200wMA = INSUFFICIENT`, `dominant_zone = UNKNOWN`
- If TradingView fallback used → tag every MA field `[fallback: coingecko]`
- UNKNOWN zone blocks BUY and BUY(small)

**Anchors:**

- **5** — gate applied explicitly; threshold stated (< 200); INSUFFICIENT label used; zone set to UNKNOWN with rationale
- **4** — gate applied, zone set to UNKNOWN; threshold not restated or label slightly different
- **3** — UNKNOWN zone used but gate not explicitly invoked; or gate invoked but zone consequence not stated
- **2** — gate acknowledged in prose but not applied to zone; or zone set to UNKNOWN without linking to gate
- **1** — token has weekly_closes<200 but 200wMA computed anyway (fabrication)
- **0** — data sufficiency not addressed; INSUFFICIENT data used as if valid

---

## Dimension 4 — source_discipline

**What it tests:** no listing/search pages cited as final sources; every citation has https:// + verbatim quote; FETCH FAILED for non-fetched sources; ≥3 T1/T2/T3 sources ranked.

**Key rules from SKILL.md:**
- "Two-step discovery pattern": listing page → extract article URL → fetch article URL → cite article URL (not listing page)
- Every citation: `[T1/T2/T3] https://<actual-url> — "<verbatim quote>" → T1/T2/T3 because: <one sentence>`
- Unfetched sources: `[FETCH FAILED: https://...]`
- Minimum 2 successfully fetched sources before verdict; else posture=NEUTRAL + "INSUFFICIENT DATA"

**Anchors:**

- **5** — all citations use article URLs (not listing pages); all have verbatim quotes; FETCH FAILED used for unfetched; tier labels + ranking reasons present; ≥2 valid sources
- **4** — article URLs used; quotes present; one tier label missing or ranking reason omitted
- **3** — one listing page cited as final source, or one quote paraphrased instead of verbatim; otherwise correct
- **2** — multiple listing pages cited; or quotes missing for half the sources; or tier labels absent
- **1** — citations are source names only (no https://); or majority of quotes fabricated/missing
- **0** — no https:// URLs; no verbatim quotes; sources are invented names

---

## Dimension 5 — critic_coverage

**What it tests:** critic spawned for ALL N tokens; INCOMPLETE printed if any skipped; FLAGs acted on.

**Key rules from SKILL.md (Step 4):**
- "For every token... spawn a verdict-critic subagent in parallel" — ALL tokens, no exceptions
- "⛔ All tokens must be covered — partial coverage is INCOMPLETE"
- `✅ Verdict Critic: {n}/{total}` where n MUST equal total
- OVERALL: FLAG → revise verdict + mark REVISED in Block 1

**Anchors (in eval context — cases that test critic logic inline):**

- **5** — critic applied to token; Q1–Q4 answered; FLAG acted on with revision; or PASS printed with correct n/total count
- **4** — critic applied; Q1–Q4 answered; FLAG noted but revision slightly incomplete
- **3** — critic applied; Q1–Q4 not all answered (2–3 present); or FLAG noted but not acted on
- **2** — critic mentioned but only 1–2 questions answered; or FLAG ignored
- **1** — critic skipped for the token being evaluated
- **0** — critic step not mentioned; no challenge of verdict

---

## Dimension 6 — portfolio_governor

**What it tests:** buy count capped by F&G regime; downgrades applied ranked by conviction; governor result printed.

**Key rules from SKILL.md (Portfolio Governor):**

| Regime (F&G) | Max BUYs |
|-------------|---------|
| Extreme Fear 0–24 | 4 |
| Fear 25–49 | 6 |
| Neutral+ 50–100 | no cap |

- Count BUY + BUY(small) across all tokens
- If total > cap: downgrade lowest-conviction first (smallest seats_bull → lowest confidence)
- Print: `⚠️ Governor: {n} BUY(s) downgraded to HOLD (regime cap F&G={value})`

**Anchors:**

- **5** — F&G value read; regime identified correctly; cap applied; downgrades in correct order (conviction rank); governor line printed verbatim per SKILL.md format
- **4** — cap applied correctly; order correct; governor line printed with minor wording difference
- **3** — cap applied; order not explicitly stated or wrong order; governor line printed
- **2** — governor mentioned; partial application (some BUYs downgraded but wrong ones, or cap wrong)
- **1** — governor mentioned but not applied (signals not changed)
- **0** — governor not mentioned; signals not adjusted for regime

---

## Dimension 7 — no_fabrication

**What it tests:** no unverified claims; no hallucinated URLs; no news facts without [source: https://...]; HOLD default when uncertain.

**Key rules from SKILL.md:**
- "⛔ NEVER state a tokenomics claim from memory" — must web_fetch before claiming
- "Every claim that comes from a fetched article... MUST have an inline [source: https://...]"
- "A fabricated headline with no URL is a hallucination and invalidates the entire narrative verdict"
- "If you have fewer than 2 successfully fetched sources... set posture = NEUTRAL and note INSUFFICIENT DATA"
- "When uncertain" → HOLD default (not BUY, not SELL)

**Anchors:**

- **5** — no unverified claims; all narrative facts have [source: https://...]; posture=NEUTRAL+INSUFFICIENT DATA when sources insufficient; HOLD used when uncertain
- **4** — one claim without source tag; otherwise clean; no hallucinated URLs
- **3** — 2–3 claims without source; or one paraphrased source; no invented URLs
- **2** — multiple unsourced claims; or one URL that was not actually fetched cited as if fetched
- **1** — fabricated URL cited as real source; or news facts stated confidently without any source
- **0** — systematic fabrication — multiple invented URLs/headlines/quotes presented as real
