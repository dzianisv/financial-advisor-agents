# backtests/daytrade — intraday strategy harnesses (gated)

Every script here runs a strategy through the **`strategy-discovery-backtest` gate** (invariant #1 of
@GOAL.md): no rule reaches a live order without a PASS, net of real costs, out-of-sample.
**Educational analysis, not financial advice.**

## Files
- `crypto_data.py` — Coinbase 1h OHLCV loader (ccxt), paginated, cached to `data/*.csv`.
  Coinbase granularities are 1m/5m/15m/1h/6h/1d (no 4h). Run: `python3 backtests/daytrade/crypto_data.py 1h`.
- `crypto_trend_backtest.py` — first gated crypto day-trade candidate (intraday SMA trend, long-only,
  vol-targeted, no-trade band). Run from repo root: `python3 backtests/daytrade/crypto_trend_backtest.py`.
- `data/` — cached OHLCV (git-ignored; re-fetch via the loader).

## Result so far (honest)

| Candidate | Venue/costs | IS | OOS (2024+) | vs hold-BTC | Verdict |
|-----------|-------------|----|----|----|---------|
| Intraday SMA trend (BTC/ETH/SOL, 1h) | Coinbase taker 0.5%/side | Sharpe −1.3 best | Sharpe −2.7 | hold-BTC +0.49 | **FAIL — no edge** |
| same, maker 0.1%/side | — | — | Sharpe −0.26 | loses | **FAIL** |
| same, 2× cost stress | — | — | Sharpe −5.5 | loses | **FAIL** |

**Why it fails:** at ~0.7–1.0 round-trips/day the strategy turns over ~250–365×/yr. At 0.5%/side retail
taker that is a ~250–365%/yr cost drag — no intraday trend signal on majors clears it. Even at pro maker
fees (0.1%) the net OOS Sharpe is negative, and **buy-and-hold BTC (Sharpe 0.49) beats it outright**.
This held in-sample AND out-of-sample, with a no-trade band applied (turnover already minimized).

**This is the gate doing its job.** "No edge found" is a valid, valuable result — it prevented a
cost-mirage strategy from reaching real capital. Logged here so we do not blindly re-test it.

**HYPE/USD:** only listed on Coinbase ~2026-02-05 (~4 months, 2.8k bars) — too little out-of-sample to
gate. Tracked, not traded.

## What the gate points to next (hypotheses, each must re-pass)
1. **Lower frequency** — daily/6h trend trades far less; costs may stop dominating (likely converges to
   the long-horizon book, which is the honest answer: for majors, *hold* tends to beat *day-trade*).
2. **Maker-passive only** — limit-only execution at ~0.1%; needs a fill model (not every limit fills).
3. **Regime-gated** — only trade trend in confirmed high-trend regimes, stand down in chop (most cost
   bleed is chop whipsaw).
4. **Cross-sectional / relative-value** rather than time-series trend (long strongest vs short weakest —
   but shorting adds funding/borrow).

Bottom line for the day-trade mandate: **so far the backtested evidence says hold-the-majors beats
intraday trend after costs.** We keep searching for an honest intraday edge; until one PASSes, the
crypto desk trades nothing intraday.
