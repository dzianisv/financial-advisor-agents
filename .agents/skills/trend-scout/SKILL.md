---
name: trend-scout
description: Weekly equity theme-momentum screener (buy-strength, NOT laggard rotation). Ranks 9 themes by relative-strength heat, surfaces the STRONGEST above-200dMA names within confirmed-hot themes as FINALISTS for multi-lens-quorum conviction gate. Stage 0 validated on Ken French 49 industries OOS: plain momentum survives weakly; buy-laggard is empirically backwards (−0.45%/mo net); EARLY>LATE staging was overfit and dropped. Use when asked "what trend/theme is hot right now", "find emerging themes", "scan themes", "run the trend scout", "weekly stock research", "what's waking up in the market", "rotate into what", or names a theme (AI, optics, space, nuclear, memory, defense, quantum, robotics, datacenter power) and asks how to play it. Weak-edge screener feeding human/quorum judgment — hypothesis funnel, never alpha claim, never auto-trades. Educational, not advice.
license: MIT
compatibility: opencode
metadata:
  audience: thematic-momentum-investors
  domain: equity-theme-momentum-screening
  role: Stage-0-validated-momentum-screener-buy-strength
  source: "Built 2026-06-08; Ken French 49-industry OOS validation; free yfinance data; buy-laggard thesis refuted and dropped"
---

# Trend Scout — weekly theme-momentum screener

Surface which investment themes have real relative-strength right now, then name the **strongest confirmed-uptrend names** within them as candidates for deeper review.

**What was tested and dropped:** an earlier design surfaced the cheapest/least-run name within a hot theme ("buy the laggard"). Stage 0 validation (Ken French 49 industries, OOS ≥2010, 1185 months, 15bps costs) found that rule is *empirically backwards* — leaders beat laggards −0.45%/mo net, consistent in both train and test. That design is gone. Only plain momentum (buy-strength) survived OOS, and only weakly (t=1.70). The skill is honest about this: weak edge, screener only.

This is the **research/screen layer**. It generates finalists; it does not decide. Route finalists to `multi-lens-quorum` (conviction gate — an agent step, not a Python call).

## Pipeline

```
theme_radar.py  →  stock_picker.py  →  weekly_scout.py  →  FINALISTS  →  multi-lens-quorum
   (rank themes)     (rank names)       (one command)      (hand off)      (agent step)
```

## Run it

Use the repo venv: `/Users/engineer/.venv/bin/python3`. Requires `yfinance pandas numpy`.

```bash
# Recommended: run everything in one shot
/Users/engineer/.venv/bin/python3 scripts/weekly_scout.py

# Individual stages (for debugging)
/Users/engineer/.venv/bin/python3 scripts/theme_radar.py
/Users/engineer/.venv/bin/python3 scripts/stock_picker.py

# Stage 0 validation (reproduce the OOS signal test)
/Users/engineer/.venv/bin/python3 scripts/stage0_horizons.py
/Users/engineer/.venv/bin/python3 scripts/signal_test.py
```

`weekly_scout.py` writes `reports/<YYYY-MM-DD>.md` (theme table + per-theme picks + FINALISTS block + week-over-week diff) and a state JSON used for next week's diff.

## Reading the output

**Theme table columns:**

- **heat (0-100)** — percentile rank of a composite (RS_3m 40% / RS_6m 25% / breadth 20% / accel 15%) *across the 9 themes*. Relative signal only; adding/removing themes reshuffles it.
- **stage** (EARLY/MID/LATE/WEAK) — descriptive label from breadth + extension. EARLY>LATE ordering was *not predictive OOS* (Stage 0 t=0.52); treat it as context, not a trading signal.
- **RS_3m / RS_6m** — basket return vs SPY over 3 and 6 months.
- **breadth** — fraction of basket constituents above their 200d MA.

**Picks section:** within each confirmed-strong theme, constituents ranked by 6m RS — strongest first, all above 200d MA. Valuation (fwdPE / P/S) is a **risk flag** shown in brackets — high valuation means overpay caution, not a reason to drop to a laggard. A name *below* its 200d MA does not appear regardless of valuation.

**FINALISTS block:** one strongest above-trend name per strong theme. These go to `multi-lens-quorum`.

**Diff block:** theme heat moves and finalist changes vs the prior week's state JSON. A theme flipping WEAK→MID or a new top-RS name appearing is the highest-value weekly event.

## Handoff to multi-lens-quorum

After `weekly_scout.py` produces the FINALISTS block, run `multi-lens-quorum` as an agent step (not from Python) with the finalists as input. Quorum is the conviction gate: buy/size/timing decision, valuation stress-test (Graham seat), and macro context. The screener produces candidates; the quorum decides.

## Honesty rails

- **Hypothesis funnel, not alpha.** Stage 0 shows a weak, decaying momentum edge. No claim of demonstrated profitability.
- **Survivorship bias.** Thematic baskets cannot be point-in-time backtested on free yfinance data — constituents are known today, not historically. Output is a current-screen hypothesis, not a simulated track record.
- **Momentum is backward-looking.** The scout describes what IS trending. It will lag tops and occasionally signal strength just before a reversal. Pair with quorum's macro and valuation seats.
- **No narrative in the score.** News and hot stories confirm; they do not rank. A LATE/WEAK reading on a hyped theme is the correct output; do not override it.
- **Watchlist only.** Notification-first; never auto-trades. Educational, not advice.
- **Scheduler deferred by design.** Automated weekly runs are intentionally not scheduled until the funnel earns trust through manual use.

## Maintaining baskets

`scripts/baskets.json` — equal-weight `core` + `second_derivative` per theme, validated US-listed/ADR + yfinance-resolvable. Re-validate periodically: ADRs delist, names spin out (SNDK from WDC). A dropped ticker prints under "no data" — fix or replace it. To add a theme, append an object with the same shape; heat re-ranks automatically. No Morningstar scraping.

## Example

```bash
/Users/engineer/.venv/bin/python3 scripts/weekly_scout.py
# → reports/2026-06-08.md
# Theme table: ai-memory-storage heat=100 LATE, optical-networking heat=89 LATE, ...
# FINALISTS: SNDK (ai-memory-storage) +702% 6m [fwdPE 8.8], AAOI (optical-networking) +590% 6m [fwdPE 37.1], ...
# → run multi-lens-quorum on FINALISTS for conviction call
```

## Done when

`weekly_scout.py` has produced a dated report in `reports/`, the operator can read which themes are heat-ranked and why, the FINALISTS block has been handed to `multi-lens-quorum` as an agent step, and no finalist is treated as actionable without passing the conviction gate.
