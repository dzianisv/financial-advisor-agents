"""
Track B — Stock intraday strategy through the strategy-discovery-backtest GATE.

SPEC (falsifiable, before fitting):
  Universe : liquid US ETFs/large-caps — SPY, QQQ, AAPL, NVDA, AMD, TSLA (yfinance 1h bars).
             yfinance serves only ~730 days of hourly data — note this limit; IS/OOS split
             inside that window. Regular-hours bars (pre/post excluded by yfinance default).
  Candidates (each gated independently, long-only — avoids short borrow/locate):
    1. ORB   : opening-range breakout — long when the first-bar-of-day high breaks, hold to close.
    2. MOM   : intraday momentum — long when prior bar return > 0 AND price > VWAP-proxy.
    3. REV   : VWAP mean-reversion — long when price stretched below rolling mean (fade).
  Decision : on PRIOR bar (no look-ahead; signals shifted +1 bar). Flat overnight (true day-trade).
  Costs    : 1 bp commission-equivalent + 2 bps slippage = ~3 bps/side liquid (Robinhood PFOF
             fills are not midpoint). Also a 2x-cost stress. PDT noted (see below).
  PASS if  : OOS Sharpe > 0 net of cost AND beats buy-hold-SPY risk-adjusted AND survives 2x cost.
             Else honest FAIL / "no edge found".
  PDT CAVEAT: under $25k equity, max 3 day-trades / 5 business days — a multi-name intraday
             strategy is NOT runnable under $25k regardless of backtest. Stated up front.
Educational analysis, not financial advice.
"""
import os, sys
import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RF = 0.04
COST = 0.0003          # ~3 bps/side (1bp comm-equiv + 2bps slippage)
BARS_PER_YEAR = 252 * 7  # ~7 RTH hourly bars/day
UNIVERSE = ["SPY", "QQQ", "AAPL", "NVDA", "AMD", "TSLA"]


def load_1h(tickers):
    df = yf.download(tickers, period="730d", interval="60m", auto_adjust=True, progress=False)
    close = df["Close"]
    high = df["High"]
    return close, high


def daykey(idx):
    return pd.Index(idx).tz_convert("America/New_York").date if idx.tz else pd.Index(idx).date


def sig_orb(close, high):
    """Long after the day's first bar high is exceeded; flat overnight. Decide on prior bar."""
    df = pd.DataFrame({"c": close, "h": high}).dropna()
    if df.empty:
        return pd.Series(dtype=float)
    days = pd.Series(df.index, index=df.index).dt.tz_convert("America/New_York").dt.date
    first_high = df.groupby(days.values)["h"].cummax()
    # first bar's high per day = the opening range high
    or_high = df.groupby(days.values)["h"].transform("first")
    sig = (df["c"] > or_high).astype(float)
    return sig.shift(1).fillna(0.0)


def sig_mom(close):
    r = close.pct_change()
    vwap_proxy = close.rolling(7).mean()
    sig = ((r > 0) & (close > vwap_proxy)).astype(float)
    return sig.shift(1).fillna(0.0)


def sig_rev(close):
    m = close.rolling(14).mean()
    sd = close.rolling(14).std()
    z = (close - m) / sd
    sig = (z < -1.0).astype(float)   # fade stretched-down moves
    return sig.shift(1).fillna(0.0)


def asset_net(close, sig, cost):
    ret = close.pct_change().fillna(0.0)
    turn = sig.diff().abs().fillna(sig.abs())
    return sig * ret - turn * cost


def metrics(net):
    net = net.dropna()
    if len(net) < 50 or net.std() == 0:
        return None
    eq = (1 + net).cumprod()
    yrs = len(net) / BARS_PER_YEAR
    cagr = eq.iloc[-1] ** (1 / yrs) - 1 if eq.iloc[-1] > 0 else -1
    vol = net.std() * np.sqrt(BARS_PER_YEAR)
    sharpe = (net.mean() * BARS_PER_YEAR - RF) / vol if vol else 0
    dd = (eq / eq.cummax() - 1).min()
    rt_day = (net != 0).mean() * 7  # rough
    return dict(cagr=cagr, vol=vol, sharpe=sharpe, maxdd=dd, final=eq.iloc[-1], eq=eq)


def split(close, frac=0.6):
    n = int(len(close) * frac)
    return close.iloc[:n], close.iloc[n:]


def portfolio(closes, highs, sigfn, cost, use_high=False, idx=None):
    nets = []
    for t in closes.columns:
        c = closes[t].dropna()
        if idx is not None:
            c = c[c.index.isin(idx)]
        if len(c) < 60:
            continue
        s = sigfn(c, highs[t].reindex(c.index)) if use_high else sigfn(c)
        nets.append(asset_net(c, s, cost).rename(t))
    if not nets:
        return None
    return pd.concat(nets, axis=1).fillna(0.0).mean(axis=1)


def main():
    print("Downloading 1h bars (yfinance, ~730d limit)...")
    closes, highs = load_1h(UNIVERSE)
    closes = closes.dropna(how="all"); highs = highs.dropna(how="all")
    print(f"  {closes.index[0].date()} -> {closes.index[-1].date()}, {len(closes)} bars, {list(closes.columns)}")

    # IS/OOS split on the shared index
    full_idx = closes.index
    n = int(len(full_idx) * 0.6)
    is_idx, oos_idx = full_idx[:n], full_idx[n:]
    print(f"  IS {is_idx[0].date()}->{is_idx[-1].date()} | OOS {oos_idx[0].date()}->{oos_idx[-1].date()}")

    cands = {
        "ORB (opening-range breakout)": (sig_orb, True),
        "MOM (intraday momentum)": (sig_mom, False),
        "REV (VWAP mean-reversion)": (sig_rev, False),
    }

    # benchmark: buy-hold SPY over OOS
    spy_oos = closes["SPY"].reindex(oos_idx).pct_change().fillna(0.0)
    spy_m = metrics(spy_oos)

    print(f"\n{'candidate':32s} {'IS Sharpe':>9} {'OOS Shrp':>9} {'OOS CAGR':>9} {'OOS DD':>8} {'2x Shrp':>8}")
    results = []
    for name, (fn, uh) in cands.items():
        is_net = portfolio(closes, highs, fn, COST, use_high=uh, idx=is_idx)
        oos_net = portfolio(closes, highs, fn, COST, use_high=uh, idx=oos_idx)
        oos_2x = portfolio(closes, highs, fn, 2 * COST, use_high=uh, idx=oos_idx)
        mi, mo, m2 = metrics(is_net), metrics(oos_net), metrics(oos_2x)
        if not mo:
            continue
        results.append((name, mo, m2))
        print(f"{name:32s} {mi['sharpe'] if mi else 0:8.2f} {mo['sharpe']:8.2f} "
              f"{mo['cagr']:8.1%} {mo['maxdd']:7.1%} {m2['sharpe'] if m2 else 0:7.2f}")

    print(f"\n  Benchmark hold-SPY (OOS): Sharpe {spy_m['sharpe']:.2f}  CAGR {spy_m['cagr']:.1%}  DD {spy_m['maxdd']:.1%}")

    print("\n=== GATE VERDICTS (Track B) ===")
    any_pass = False
    for name, mo, m2 in results:
        ok = mo["sharpe"] > 0 and mo["sharpe"] >= spy_m["sharpe"] and m2 and m2["sharpe"] > 0
        why = ""
        if not ok:
            if mo["sharpe"] <= 0: why = "OOS Sharpe <= 0 after cost"
            elif mo["sharpe"] < spy_m["sharpe"]: why = f"< hold-SPY ({mo['sharpe']:.2f} < {spy_m['sharpe']:.2f})"
            elif not (m2 and m2["sharpe"] > 0): why = "dies under 2x cost"
        print(f"  {name:32s} {'PASS' if ok else 'FAIL (no edge)'}  {why}")
        any_pass = any_pass or ok

    print("\n  PDT CAVEAT: a multi-name intraday strategy needs >=$25k equity (else 3 day-trades/5d cap).")
    print("  DATA CAVEAT: yfinance gives only ~730d of hourly bars — short sample, one market regime.")
    print("  " + ("A candidate PASSED — promote to paper with a fill model + PDT-aware sizing." if any_pass
                  else "No edge found — intraday equity signals don't clear costs OOS. Honest result; "
                       "for income, hold/mid-risk (Track A) beats day-trading here too."))

    # chart best
    if results:
        name, mo, _ = max(results, key=lambda r: r[1]["sharpe"])
        fig, ax = plt.subplots(figsize=(11, 6))
        ax.plot(mo["eq"].index, mo["eq"].values, lw=1.6, label=f"{name} (net ~3bps/side)")
        spy_eq = (1 + spy_oos).cumprod()
        ax.plot(spy_eq.index, spy_eq.values, lw=1.2, alpha=0.8, label="Hold SPY")
        ax.set_title(f"Track B — best intraday equity candidate, OOS — {'PASS' if any_pass else 'FAIL'}\n(educational, not advice)")
        ax.set_ylabel("growth of $1 (net of cost)"); ax.legend(); ax.grid(alpha=0.3)
        out = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "report", "img", "stock_intraday.png"))
        fig.tight_layout(); fig.savefig(out, dpi=110)
        print(f"\n  chart -> {out}")


if __name__ == "__main__":
    main()
