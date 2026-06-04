# backtests/daytrade — intraday strategy harnesses (gated)

Every script here runs a strategy through the **`strategy-discovery-backtest` gate** (invariant #1 of
@GOAL.md): no rule reaches a live order without a PASS, net of real costs, out-of-sample.
**Educational analysis, not financial advice.**

## Files
- `crypto_data.py` — Coinbase 1h OHLCV loader (ccxt), paginated, cached to `data/*.csv`.
  Coinbase granularities are 1m/5m/15m/1h/6h/1d (no 4h). Run: `python3 backtests/daytrade/crypto_data.py 1h`.
- `crypto_trend_backtest.py` — first gated crypto day-trade candidate (intraday SMA trend, long-only,
  vol-targeted, no-trade band). Run from repo root: `python3 backtests/daytrade/crypto_trend_backtest.py`.
- `stock_intraday_backtest.py` — Track B equity intraday gate (ORB / momentum / VWAP-reversion on
  SPY/QQQ/AAPL/NVDA/AMD/TSLA, yfinance 1h). Run: `python3 backtests/daytrade/stock_intraday_backtest.py`.
- `data/` — cached OHLCV (git-ignored; re-fetch via the loader).

## Track B — stock intraday (`stock_intraday_backtest.py`) — FAIL (no edge)

Three long-only intraday candidates on liquid US names, yfinance 1h (~730d), IS/OOS 60/40, ~3 bps/side
cost + 2× stress, vs hold-SPY.

| Candidate | IS Sharpe | OOS Sharpe | OOS DD | 2× cost | vs hold-SPY (1.59) | Verdict |
|-----------|-----------|-----------|--------|---------|--------------------|---------|
| ORB (opening-range breakout) | −0.61 | 1.28 | −7% | 0.67 | loses | FAIL |
| MOM (intraday momentum) | −1.01 | −0.93 | −28% | −2.18 | loses | FAIL |
| REV (VWAP mean-reversion) | −0.44 | 1.30 | −5% | 0.78 | loses | FAIL |

**Honest read:** ORB and REV show *positive* OOS Sharpe — but their **IS Sharpe is negative**, so the
OOS "win" is **regime luck** (the OOS window 2025-04→2026-06 was a strong bull where holding SPY returned
34%/Sharpe 1.59), not a persistent edge. None beats buy-and-hold risk-adjusted. The gate correctly FAILs
all three. Caveats stated: yfinance gives only ~730d hourly (one regime, short sample); and a multi-name
intraday strategy needs ≥$25k to clear the **PDT** rule regardless of backtest.

**Consistent with the whole day-trade investigation:** across crypto (intraday + daily) and equities
(intraday), **buy-and-hold / mid-risk allocation beats systematic day-trading after costs.** For income,
Track A's mid-risk book (`strategy/midrisk-bubble-trimmed.md`) is the evidence-backed answer; the
day-trade desks trade nothing until a candidate PASSes the gate.

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

## Candidate 2 — lower-frequency / regime-gated (`crypto_lowfreq_backtest.py`)

The gate steered us to lower frequency + regime gating. Daily bars, BTC/ETH/SOL, vol-targeted, no-trade
band. Three families, each gated; OOS 2024+ (params chosen IS ≤2023):

| Candidate | OOS taker 0.5% | OOS maker 0.1% | OOS 2× stress | Max DD | vs hold-BTC | Verdict |
|-----------|----------------|----------------|---------------|--------|-------------|---------|
| TSMOM N=30 | Sharpe 0.14 | 0.50 | −0.30 | −36% | < 0.45 | FAIL |
| SMA N=50 | 0.13 | 0.39 | −0.20 | −28% | < 0.45 | FAIL |
| **REGIME-SMA (BTC>200d) N=50** | **0.41** | **0.61** | **0.15** | **−24%** | 0.41 < 0.45 | FAIL (retail) |
| Hold BTC (benchmark) | 0.45 | — | — | **−50%** | — | — |

**The honest read on REGIME-SMA:** it FAILs the strict gate at retail taker (Sharpe 0.41 vs hold 0.45 —
the gate's bar is "beat hold risk-adjusted at realistic cost", and we did NOT loosen it). BUT it is a
real **drawdown-control** result, not noise: it **halves the drawdown (−24% vs −50%)** at comparable
risk-adjusted return, survives 2× cost stress (0.15 > 0), and **beats hold at maker fees (0.61 > 0.45)**.
That is the bubble-defense ethos applied to crypto — same ballpark return, half the pain.

**Status:** not promoted to trade (fails the alpha bar at retail taker). Promotable to **paper** as a
*drawdown-managed crypto sleeve* (NOT a daily-income day-trade) **iff** a maker-fill model confirms the
0.1% execution is achievable. That fill model is the next gate.

## Bottom line for the crypto day-trade mandate (honest)
Across intraday **and** daily horizons, **buy-and-hold the majors beats systematic trend after retail
costs.** No candidate has cleared the gate to trade. The one genuinely useful finding is REGIME-SMA's
**drawdown halving** — a risk-control sleeve, not a daily-income engine. Until something PASSes at
realistic cost, the crypto desk **trades nothing**. "No edge found" + "found a drawdown control, not
alpha" are both honest, valuable results — and exactly what the gate exists to tell us.

## Still-open hypotheses (each must re-pass the gate)
- **Maker-fill model** — does limit-only execution at ~0.1% actually fill enough to realize REGIME-SMA's edge?
- **Cross-sectional momentum** — long strongest / short weakest of the majors (shorting adds funding/borrow).
- **Vol/funding carry** — harvest funding on perps in range regimes (different risk: liquidation, exchange).
