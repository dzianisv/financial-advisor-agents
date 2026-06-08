#!/usr/bin/env python3
"""
trend-scout Stage 1 — theme radar.

Detects which investment THEMES are waking up vs trending vs euphoric, using only
free yfinance price data. Trend/relative-strength + breadth + extension are the
backtested-survivable signals (momentum); narrative is deliberately NOT used here.

For each theme (equal-weight basket of `core` tickers) it computes, vs SPY:
  - RS_3m / RS_6m : basket return minus SPY return (relative strength)
  - breadth       : fraction of constituents above their own 200d MA
  - extension     : mean % each constituent sits above its 200d MA (euphoria gauge)
  - accel         : 1m return minus the per-month pace of the last 3m (speeding up?)
  - heat (0-100)  : percentile rank of a composite across themes (rotation signal)
  - stage         : EARLY/MID/LATE/WEAK — DESCRIPTIVE ONLY. Stage 0 backtest (French 49,
                    OOS) found EARLY>LATE is NOT predictive; don't act on the label alone.
  - leader_pick   : constituent confirmed in uptrend (>200dMA) that has run the MOST over 6m
                    — momentum continuation. Stage 0 showed buy-STRENGTH beats buy-laggard at
                    every horizon (1/3/6/12mo), so the skill surfaces the leader, not a laggard.

Usage:
  python3 theme_radar.py                 # full table + JSON next to this file
  python3 theme_radar.py --json-only     # just write theme_radar_latest.json
  python3 theme_radar.py --period 400d   # history window (default 400d)

Educational, not advice. Output is hypothesis generation; backtest with realistic
costs before risking capital (the repo GOAL.md / Carver gate).
"""
import sys, os, json, argparse, warnings
from datetime import datetime
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))


def load_baskets():
    with open(os.path.join(HERE, "baskets.json")) as f:
        return json.load(f)


def fetch(tickers, period):
    """Download adjusted close for all tickers. Returns DataFrame (cols=tickers)."""
    try:
        data = yf.download(
            tickers, period=period, interval="1d",
            auto_adjust=True, progress=False, threads=True,
        )
    except Exception as e:
        sys.exit(f"ERROR: price download failed ({e}). Check network / yfinance.")
    if data is None or len(data) == 0:
        sys.exit("ERROR: price download returned no data. Check network / yfinance.")
    if isinstance(data.columns, pd.MultiIndex):
        close = data["Close"]
    else:  # single ticker
        close = data[["Close"]].rename(columns={"Close": tickers[0]})
    return close.dropna(how="all")


def ret(series, days):
    """Total return over the last `days` trading days; None if insufficient history."""
    s = series.dropna()
    if len(s) < days + 1:
        return None
    return float(s.iloc[-1] / s.iloc[-1 - days] - 1.0)


def above_200(series):
    """(% above 200d MA, is_above) or (None, None) if <200 days of history."""
    s = series.dropna()
    if len(s) < 200:
        return None, None
    ma = s.rolling(200).mean().iloc[-1]
    if not np.isfinite(ma) or ma <= 0:
        return None, None
    pct = float(s.iloc[-1] / ma - 1.0)
    return pct, bool(pct > 0)


def mean_skip_none(xs):
    xs = [x for x in xs if x is not None]
    return float(np.mean(xs)) if xs else None


def theme_metrics(t, close, spy):
    core = [c for c in t["core"] if c in close.columns]
    spy3, spy6 = ret(spy, 63), ret(spy, 126)

    r3 = [ret(close[c], 63) for c in core]
    r6 = [ret(close[c], 126) for c in core]
    r1 = [ret(close[c], 21) for c in core]
    ext_above = [above_200(close[c]) for c in core]
    exts = [e[0] for e in ext_above]
    aboves = [e[1] for e in ext_above if e[1] is not None]

    b3, b6, b1 = mean_skip_none(r3), mean_skip_none(r6), mean_skip_none(r1)
    rs3 = (b3 - spy3) if (b3 is not None and spy3 is not None) else None
    rs6 = (b6 - spy6) if (b6 is not None and spy6 is not None) else None
    breadth = (sum(aboves) / len(aboves)) if aboves else None
    extension = mean_skip_none(exts)
    # acceleration: last month vs the average monthly pace of the last 3 months
    accel = (b1 - b3 / 3.0) if (b1 is not None and b3 is not None) else None

    # leader pick: confirmed uptrend (>200dMA) constituent that has run the MOST over 6m.
    # Stage 0 (French 49, OOS, all horizons) proved buy-strength beats buy-laggard, so we
    # surface the strongest continuation, not the laggard. laggard kept only as FYI.
    candidates = []
    for c in core + [s for s in t["second_derivative"] if s in close.columns]:
        if c not in close.columns:
            continue
        pct, is_above = above_200(close[c])
        r = ret(close[c], 126)
        if is_above and r is not None:
            candidates.append((c, r, pct))
    leader = max(candidates, key=lambda x: x[1]) if candidates else None
    laggard = min(candidates, key=lambda x: x[1]) if candidates else None

    return {
        "theme": t["theme"], "leader": t["leader"], "etf_proxy": t["etf_proxy"],
        "rs_3m": rs3, "rs_6m": rs6, "breadth": breadth,
        "n_breadth": len(aboves),
        "extension": extension, "accel": accel,
        "ret_3m": b3, "ret_6m": b6,
        "leader_pick": ({"ticker": leader[0], "ret_6m": leader[1], "ext_vs_200d": leader[2]}
                        if leader else None),
        "laggard_fyi": ({"ticker": laggard[0], "ret_6m": laggard[1]}
                        if laggard else None),
        "n_core": len(core),
    }


def classify_stage(m):
    rs3, br, ext, ac = m["rs_3m"], m["breadth"], m["extension"], m["accel"]
    if rs3 is None or br is None:
        return "NO_DATA"
    # WEAK: lagging the market and most names below trend
    if rs3 < 0 and br < 0.4:
        return "WEAK"
    # LATE: stretched far above trend or near-universal participation = euphoria
    if (ext is not None and ext > 0.30) or br > 0.85:
        return "LATE"
    # EARLY: outperforming, speeding up, broad-but-not-crowded, not yet stretched
    if rs3 > 0 and (ac is not None and ac > 0) and 0.4 <= br <= 0.75 \
       and (ext is None or ext < 0.18):
        return "EARLY"
    return "MID"


def heat_scores(metrics):
    """Percentile-rank a composite across themes -> 0-100 rotation heat."""
    def z(vals):
        v = pd.Series([x if x is not None else np.nan for x in vals], dtype=float)
        return v.rank(pct=True) * 100.0

    comp = []
    for m in metrics:
        parts, wts = [], []
        for key, w in (("rs_3m", 0.40), ("rs_6m", 0.25), ("breadth", 0.20), ("accel", 0.15)):
            if m[key] is not None:
                parts.append(m[key]); wts.append(w)
        comp.append(np.average(parts, weights=wts) if parts else np.nan)
    ranked = z(comp)
    for m, h in zip(metrics, ranked):
        m["heat"] = round(float(h), 1) if np.isfinite(h) else None
    return metrics


def fmt_pct(x):
    return f"{x*100:+5.1f}%" if x is not None else "   n/a"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", default="400d")
    ap.add_argument("--json-only", action="store_true")
    args = ap.parse_args()

    b = load_baskets()
    bench = b["_meta"]["benchmark"]
    tickers = sorted({t for th in b["themes"]
                      for t in th["core"] + th["second_derivative"]} | {bench})

    close = fetch(tickers, args.period)
    missing = [t for t in tickers if t not in close.columns]
    spy = close[bench]

    metrics = [theme_metrics(t, close, spy) for t in b["themes"]]
    metrics = heat_scores(metrics)
    for m in metrics:
        m["stage"] = classify_stage(m)
    metrics.sort(key=lambda m: (m["heat"] if m["heat"] is not None else -1), reverse=True)

    out = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "benchmark": bench, "period": args.period,
        "missing_tickers": missing, "themes": metrics,
    }
    with open(os.path.join(HERE, "theme_radar_latest.json"), "w") as f:
        json.dump(out, f, indent=2)

    if args.json_only:
        print(f"wrote theme_radar_latest.json ({len(metrics)} themes)")
        return

    print(f"\nTREND-SCOUT theme radar  |  {out['generated']}  |  vs {bench}  |  window {args.period}")
    if missing:
        print(f"(no data, dropped: {', '.join(missing)})")
    print("=" * 92)
    print(f"{'THEME':<20}{'HEAT':>5} {'STAGE':<6}{'RS_3m':>8}{'RS_6m':>8}{'BREADTH':>8}{'EXT>200':>8}  LEADER (strongest)")
    print("-" * 92)
    for m in metrics:
        lp = m["leader_pick"]
        lead = f"{lp['ticker']} ({fmt_pct(lp['ret_6m']).strip()} 6m)" if lp else "-"
        br = f"{m['breadth']*100:4.0f}%" if m["breadth"] is not None else "  n/a"
        ext = fmt_pct(m["extension"])
        heat = f"{m['heat']:>4.0f}" if m["heat"] is not None else " n/a"
        print(f"{m['theme']:<20}{heat:>5} {m['stage']:<6}{fmt_pct(m['rs_3m']):>8}"
              f"{fmt_pct(m['rs_6m']):>8}{br:>8}{ext:>8}  {lead}")
    print("-" * 92)
    print("HEAT ranks themes by relative strength (buy-strength — the only Stage-0-survivable edge).")
    print("STAGE is descriptive only; EARLY>LATE was NOT predictive out-of-sample — do not act on it.")
    print("LEADER = strongest confirmed-uptrend name (continuation). Buy-strength beat buy-laggard")
    print("at every tested horizon (Stage 0, French 49). Screener output — route to multi-lens-quorum.")
    print("Educational, not advice. Weak edge; backtest with costs before trading.\n")


if __name__ == "__main__":
    main()
