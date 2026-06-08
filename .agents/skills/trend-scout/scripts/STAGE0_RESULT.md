# Stage 0 signal-information test — RESULT (Ken French 49 industries, bias-free)

OOS split 2010, cost 15bps, 1185 months.

## TRAIN (pre-2010)
- Staging Q5-Q1: +0.43%/mo, t=2.84  (momentum present — known)
- EARLY>LATE:    +0.48%/mo, t=3.86  (novel staging claim works IN TRAIN)
- LAGGARD>LEADER: gross -0.12%/mo t=-1.06; net -0.42%/mo  (FAILS — leaders beat laggards)

## TEST / OUT-OF-SAMPLE (>=2010)
- Staging Q5-Q1: +0.48%/mo, t=1.70  (positive but WEAK significance — momentum decayed post-2010)
- EARLY>LATE:    +0.14%/mo, t=0.52  (DISAPPEARED OOS — overfit/regime-dependent)
- LAGGARD>LEADER: gross -0.15%/mo t=-0.57; net -0.45%/mo  (FAILS AGAIN — robustly negative)

## Verdict
1. The "cheap LAGGARD within a strong theme" rule — the skill's headline differentiator
   ("cheap_pick") — is EMPIRICALLY BACKWARDS. Within a strong cohort, leaders continue to
   beat laggards; buying the laggard loses ~0.45%/mo net. Consistent in train AND test.
2. EARLY>LATE staging looked strong in train (t=3.86) but vanished OOS (t=0.52) = overfit.
3. Only plain momentum (buy strength) survives OOS, and only weakly (t=1.70) — the already-
   known anomaly, nothing novel to trend-scout.

## Caveat
Industry-level, monthly, 1m-forward. Stock-level/weekly could differ — but the laggard
result is robust and directionally clear both periods; stocks are MORE momentum-driven, so
the test is if anything generous. Longer-horizon fundamental catch-up untested.

## Implication
Do NOT ship a screener whose headline feature is value-destructive. Must invert (surface
the LEADER/continuation, not the laggard) or drop it, and reposition honestly.
