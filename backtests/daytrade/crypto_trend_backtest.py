"""
Crypto day-trading strategy through the strategy-discovery-backtest GATE.

SPEC (falsifiable, written before fitting):
  Universe : BTC/USD, ETH/USD, SOL/USD (Coinbase 1h bars). HYPE/USD reported separately
             (short history since late-2024 launch — not enough OOS to PASS).
  Signal   : long-only intraday TREND. Long when close > SMA(slow) AND fast>slow
             (Donchian-free, simple & robust); flat otherwise. NO shorts (spot/CDP).
  Decision : on PRIOR bar close only (no look-ahead; signal shifted +1 bar).
  Sizing   : volatility-target — scale each asset to TARGET_VOL annualized, capped at 1x.
  Costs    : Coinbase taker 0.50%/side (retail) is the base case; also test maker 0.10%.
  Horizon  : intraday-to-swing on 1h bars; position can hold multiple bars.
  Economic reason: crypto momentum persistence (24/7 herding/reflexivity is a
             documented anomaly). Hypothesis — does it survive REAL costs, OOS?

GATE: PASS only if OOS edge beats hold-BTC risk-adjusted AND survives doubled costs.
"no edge found" is a valid, valuable result. Educational analysis, not financial advice.
"""
import os, sys, itertools
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(__file__))
from crypto_data import load_universe

BARS_PER_YEAR = 24 * 365  # 1h crypto, 24/7
RF = 0.04
IS_END = "2023-12-31"     # in-sample: data start .. 2023-12-31
OOS_START = "2024-01-01"  # out-of-sample: 2024-01-01 .. now  (headline)
TARGET_VOL = 0.60         # annualized vol target per asset (crypto is high-vol)


def sma_signal(close, fast, slow):
    """Long (1) when fast SMA > slow SMA AND price>slow; else flat (0). Decide on prior bar."""
    f = close.rolling(fast).mean()
    s = close.rolling(slow).mean()
    raw = ((f > s) & (close > s)).astype(float)
    return raw.shift(1).fillna(0.0)  # ENTER next bar -> no look-ahead


def vol_target_weights(close, signal, target_vol=TARGET_VOL, lookback=72, band=0.10):
    """Vol-target weight with a no-trade BAND: only move the live weight when the
    target drifts > `band` from current. Cuts noise-rebalancing turnover (realistic
    execution; the COST per trade is unchanged — this is not loosening the cost model)."""
    ret = close.pct_change()
    realized = ret.rolling(lookback).std() * np.sqrt(BARS_PER_YEAR)
    scale = (target_vol / realized).clip(upper=1.0).shift(1).fillna(0.0)
    target = (signal * scale).clip(0.0, 1.0)
    # apply band
    tv = target.values
    out = np.zeros_like(tv)
    cur = 0.0
    for i in range(len(tv)):
        if abs(tv[i] - cur) > band:
            cur = tv[i]
        out[i] = cur
    return pd.Series(out, index=target.index)


def run_asset(close, fast, slow, cost_per_side):
    sig = sma_signal(close, fast, slow)
    w = vol_target_weights(close, sig)
    ret = close.pct_change().fillna(0.0)
    strat_gross = w * ret
    turnover = w.diff().abs().fillna(w.abs())
    cost = turnover * cost_per_side
    strat_net = strat_gross - cost
    return strat_net, w, turnover


def metrics(net, w):
    net = net.dropna()
    if len(net) < 10 or net.std() == 0:
        return None
    eq = (1 + net).cumprod()
    yrs = len(net) / BARS_PER_YEAR
    cagr = eq.iloc[-1] ** (1 / yrs) - 1 if eq.iloc[-1] > 0 else -1
    vol = net.std() * np.sqrt(BARS_PER_YEAR)
    sharpe = (net.mean() * BARS_PER_YEAR - RF) / vol if vol > 0 else 0
    dd = (eq / eq.cummax() - 1).min()
    # round-trips/day: half the per-bar weight changes, scaled to a day
    rt_day = (w.diff().abs().fillna(0) > 0.01).mean() * 24 / 2
    exposure = w.mean()
    return dict(cagr=cagr, vol=vol, sharpe=sharpe, maxdd=dd, exposure=exposure,
                rt_day=rt_day, final=eq.iloc[-1], eq=eq)


def bench_hold(close):
    ret = close.pct_change().fillna(0.0)
    return metrics(ret, pd.Series(1.0, index=close.index))


def slice_period(s, start=None, end=None):
    if start: s = s[s.index >= pd.Timestamp(start, tz="UTC")]
    if end:   s = s[s.index <= pd.Timestamp(end, tz="UTC")]
    return s


def portfolio_net(data, params, cost, start=None, end=None):
    """Equal-weight across assets of each asset's vol-targeted net return."""
    nets = []
    for sym, df in data.items():
        c = slice_period(df["close"], start, end)
        if len(c) < params["slow"] + 100:
            continue
        net, w, _ = run_asset(c, params["fast"], params["slow"], cost)
        nets.append(net.rename(sym))
    if not nets:
        return None, None
    M = pd.concat(nets, axis=1).fillna(0.0)
    port = M.mean(axis=1)
    # portfolio weight proxy for turnover/exposure stats
    ws = []
    for sym, df in data.items():
        c = slice_period(df["close"], start, end)
        if len(c) < params["slow"] + 100:
            continue
        _, w, _ = run_asset(c, params["fast"], params["slow"], cost)
        ws.append(w.rename(sym))
    W = pd.concat(ws, axis=1).fillna(0.0).mean(axis=1)
    return port, W


def main():
    syms = ["BTC/USD", "ETH/USD", "SOL/USD", "HYPE/USD"]
    print("Loading Coinbase 1h bars (cached)...")
    data = load_universe(syms, "1h")
    core = {k: v for k, v in data.items() if k in ("BTC/USD", "ETH/USD", "SOL/USD")}

    TAKER, MAKER = 0.005, 0.001
    grid = list(itertools.product([12, 24, 48], [72, 120, 200]))  # (fast,slow) hrs
    grid = [g for g in grid if g[0] < g[1]]
    n_trials = len(grid)

    # ---- 1) SELECT on IS only (taker costs), pick best Sharpe ----
    print(f"\n=== IN-SAMPLE selection (<= {IS_END}, taker {TAKER:.1%}/side, {n_trials} trials) ===")
    is_rows = []
    for fast, slow in grid:
        port, W = portfolio_net(core, dict(fast=fast, slow=slow), TAKER, end=IS_END)
        m = metrics(port, W) if port is not None else None
        if m:
            is_rows.append(((fast, slow), m))
            print(f"  SMA({fast:>3},{slow:>3})  Sharpe {m['sharpe']:5.2f}  CAGR {m['cagr']:7.1%}  "
                  f"DD {m['maxdd']:6.1%}  rt/day {m['rt_day']:.1f}")
    best_params = max(is_rows, key=lambda r: r[1]["sharpe"])[0]
    print(f"  -> best IS params: SMA{best_params}")

    # ---- 2) OOS with the IS-chosen params (headline) ----
    def show(tag, cost, start, end):
        port, W = portfolio_net(core, dict(fast=best_params[0], slow=best_params[1]), cost, start, end)
        m = metrics(port, W)
        if not m:
            print(f"  {tag}: insufficient data"); return None
        print(f"  {tag:30s} Sharpe {m['sharpe']:5.2f}  CAGR {m['cagr']:7.1%}  "
              f"DD {m['maxdd']:6.1%}  exp {m['exposure']:.2f}  rt/day {m['rt_day']:.1f}")
        return m

    print(f"\n=== OUT-OF-SAMPLE ({OOS_START} ->), params fixed from IS ===")
    oos_taker = show(f"OOS taker {TAKER:.1%}/side", TAKER, OOS_START, None)
    oos_maker = show(f"OOS maker {MAKER:.1%}/side", MAKER, OOS_START, None)
    oos_2x    = show(f"STRESS OOS 2x taker {2*TAKER:.1%}", 2 * TAKER, OOS_START, None)

    print("\n  Benchmark (hold, OOS):")
    bh = {}
    for sym, df in core.items():
        c = slice_period(df["close"], OOS_START, None)
        m = bench_hold(c)
        if m:
            bh[sym] = m
            print(f"    hold {sym:8s} Sharpe {m['sharpe']:5.2f}  CAGR {m['cagr']:7.1%}  DD {m['maxdd']:6.1%}")
    hold_btc = bh.get("BTC/USD")

    # ---- 3) VERDICT ----
    print("\n=== GATE VERDICT ===")
    reasons = []
    passed = True
    if oos_taker is None or oos_taker["sharpe"] <= 0:
        passed = False; reasons.append("OOS Sharpe <= 0 at retail taker cost")
    if hold_btc and oos_taker and oos_taker["sharpe"] < hold_btc["sharpe"]:
        passed = False; reasons.append(
            f"OOS risk-adj < hold-BTC ({oos_taker['sharpe']:.2f} < {hold_btc['sharpe']:.2f})")
    if oos_2x and oos_2x["sharpe"] <= 0:
        passed = False; reasons.append("edge dies under 2x cost stress")
    verdict = "PASS" if passed else "FAIL (no edge found)"
    print(f"  {verdict}")
    for r in reasons:
        print(f"   - {r}")
    if passed:
        print("   - survives retail cost + 2x stress AND beats hold-BTC risk-adjusted OOS")

    # ---- HYPE note (short history) ----
    if "HYPE/USD" in data and len(data["HYPE/USD"]) > 0:
        h = data["HYPE/USD"]
        print(f"\n  HYPE/USD: {len(h)} bars since {h.index[0].date()} — too short for OOS gate; tracked, not traded.")

    # ---- chart: OOS equity vs hold-BTC ----
    try:
        port, W = portfolio_net(core, dict(fast=best_params[0], slow=best_params[1]), TAKER, OOS_START, None)
        m = metrics(port, W)
        fig, ax = plt.subplots(figsize=(11, 6))
        ax.plot(m["eq"].index, m["eq"].values, label=f"Trend SMA{best_params} (net taker {TAKER:.1%})", lw=1.6)
        if hold_btc:
            ax.plot(hold_btc["eq"].index, hold_btc["eq"].values, label="Hold BTC", lw=1.2, alpha=0.8)
        ax.set_title(f"Crypto intraday trend — OOS {OOS_START}+ — {verdict}\n(educational, not advice)")
        ax.set_ylabel("growth of $1 (net of cost)"); ax.legend(); ax.grid(alpha=0.3)
        out = os.path.join(os.path.dirname(__file__), "..", "..", "report", "img", "crypto_daytrade_trend.png")
        out = os.path.abspath(out)
        fig.tight_layout(); fig.savefig(out, dpi=110)
        print(f"\n  chart -> {out}")
    except Exception as e:
        print("  chart skipped:", str(e)[:80])

    return verdict


if __name__ == "__main__":
    main()
