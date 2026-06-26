# Round 2 — Iteration Log

Date: 2026-06-26
SKILL.md version: v1

---

## Raw Judge Outputs

### case-01-btc-deep-value (R2)
Dims tested: signal_correctness, zone_discipline, data_sufficiency, portfolio_governor, no_fabrication

signal_correctness: 5 — PASS
zone_discipline: 5 — PASS
data_sufficiency: 5 — PASS
portfolio_governor: 4 — Green-path line wording off: actor wrote "Governor: 1 BUY(small) within cap of 4..." instead of `✅ Governor: 1 BUY(s) within cap of 4 (regime: Extreme Fear, F&G=13)`. Missing ✅ prefix; used signal subtype "BUY(small)" instead of generic count token "BUY(s)".
no_fabrication: 5 — PASS
MEAN: 4.8

Fix target: Governor print format — make explicit that the output uses `{N} BUY(s)` (total count, not signal subtype), and ✅ prefix is required.

---

### case-02-hype-elevated (R2)
Dims tested: signal_correctness, zone_discipline, data_sufficiency, portfolio_governor, no_fabrication

signal_correctness: 5 — PASS
zone_discipline: 5 — PASS
data_sufficiency: 5 — PASS
portfolio_governor: 5 — PASS (0 BUY signals; actor explicitly stated nothing to rank/govern)
no_fabrication: 5 — PASS
MEAN: 5.0

---

### case-03-governor-extreme-fear (R2)
Dims tested: signal_correctness, portfolio_governor

signal_correctness: 5 — PASS (BTC upstream UNCERTAIN flagged correctly; count adjusted)
portfolio_governor: 5 — PASS (ranked list correct; ✅ governor line matches exact spec format)
MEAN: 5.0

---

### case-04-listing-page-citation (R2)
Dims tested: source_discipline, no_fabrication

source_discipline: 5 — PASS
no_fabrication: 4 — ⚠️ JUDGE ERROR: judge flagged "marking the largest single DeFi liquidity injection this month" as unverifiable, but this phrase IS verbatim in the case-stated article content ("Spark Protocol deployed $150M in USDC to Uniswap v4 pools on June 25, 2026, marking the largest single DeFi liquidity injection this month."). Corrected score: 5.
MEAN: 4.5 (as judged) / 5.0 (corrected)

---

## Per-Dimension Averages (Round 2, as judged)

| Dimension | Cases Tested | Scores | Avg |
|-----------|-------------|--------|-----|
| signal_correctness | 01, 02, 03 | 5, 5, 5 | 5.0 |
| zone_discipline | 01, 02 | 5, 5 | 5.0 |
| data_sufficiency | 01, 02 | 5, 5 | 5.0 |
| source_discipline | 04 | 5 | 5.0 |
| critic_coverage | — | not tested | N/A |
| portfolio_governor | 01, 02, 03 | 4, 5, 5 | 4.67 |
| no_fabrication | 01, 02, 04 | 5, 5, 4 | 4.67 (corrected: 5.0) |

**Train mean R2: 4.89** (as judged, 6 tested dims)
**Lowest dimension: portfolio_governor (4.67) and no_fabrication (4.67, but judge error in case-04)**

## Improvement vs Round 1

| Dimension | R1 | R2 | Delta |
|-----------|----|----|-------|
| portfolio_governor | 4.0 | 4.67 | +0.67 ✓ |
| no_fabrication | 5.0 | 4.67* | ±0 (judge error) |

*Case-04 judge incorrectly flagged a verbatim quote from the case-stated article. True score is 5.0.

---

## Diagnosis (Round 2)

**Residual gap:** portfolio_governor at 4.67, driven by case-01 where the actor used "BUY(small)" instead of "BUY(s)" in the green-path governor line, and omitted the ✅ prefix.

**Root cause:** SKILL.md v1 added the ranking step and the green-path print, but the format string uses `{total} BUY(s)` without explicitly noting that `{total}` is a COUNT and `BUY(s)` is a generic label (not the specific signal subtype). Actors substitute the subtype they know ("BUY(small)") for the generic count token.

**Fix principle:** Add a one-line clarifier in the governor format string: the count variable is the total number of tokens with BUY or BUY(small) signals, and "BUY(s)" is a fixed label — do not substitute the specific signal name.

---

## Synthesized Insight

Both training dimensions that were tested multiple times now score ≥4.67. The remaining gap is purely cosmetic (governor print format). After a targeted wording fix in the governor template, all dimensions should reach 5.0 on train. Holdout cases should validate whether data sufficiency and signal correctness generalize — these are the two most structurally important dimensions.
