#!/usr/bin/env python3
"""
trend-scout Stage 2 — within-theme stock picker (BUY-STRENGTH).

Stage 0 (French 49, OOS, all horizons) proved: within a strong group, the momentum LEADER
beats the laggard. So within each confirmed-strong theme this ranks constituents by 6-month
relative strength and surfaces the STRONGEST names still in uptrend (>200d MA) — continuation,
not mean-reversion. Valuation is a SECONDARY RISK FLAG only (don't grossly overpay); it never
promotes a laggard over a leader, because that's exactly what testing refuted.

Module: import rank_theme()/valuation_flag() from weekly_scout (avoids re-downloading prices).
Standalone: `python3 stock_picker.py` runs the radar fetch and prints picks for strong themes.
Educational, not advice.
"""
import sys, json, math, warnings
warnings.filterwarnings("ignore")
import yfinance as yf
from theme_radar import load_baskets, fetch, ret, above_200


def valuation_flag(ticker):
    """Cheap valuation proxy via fallback chain. Returns (metric, value) or None.
    RISK annotation only — high value = expensive = caution, NOT a reason to pick a laggard."""
    try:
        info = yf.Ticker(ticker).info
    except Exception:
        return None
    for k in ("forwardPE", "trailingPE", "priceToSalesTrailing12Months"):
        v = info.get(k)
        if isinstance(v, (int, float)) and v > 0 and math.isfinite(v):
            short = {"forwardPE": "fwdPE", "trailingPE": "PE",
                     "priceToSalesTrailing12Months": "P/S"}[k]
            return (short, round(float(v), 1))
    return None


def rank_theme(close, theme, top=3, want_valuation=True):
    """Rank a theme's constituents by 6m RS; return top names confirmed in uptrend."""
    names = []
    for c in theme["core"] + theme["second_derivative"]:
        if c not in close.columns:
            continue
        pct, is_above = above_200(close[c])
        r = ret(close[c], 126)
        if r is None:
            continue
        role = ("leader" if c == theme["leader"]
                else "2nd-deriv" if c in theme["second_derivative"] else "core")
        names.append({"ticker": c, "ret_6m": r, "above_200d": bool(is_above),
                      "ext_vs_200d": pct, "role": role})
    names.sort(key=lambda x: x["ret_6m"], reverse=True)
    picks = [n for n in names if n["above_200d"]][:top]   # trend filter: no falling knives
    if want_valuation:
        for p in picks:
            p["valuation"] = valuation_flag(p["ticker"])
    return picks


def is_strong(m):
    """Confirmed-strong theme: outperforming over 6m AND broad participation."""
    return (m.get("rs_6m") is not None and m["rs_6m"] > 0
            and m.get("breadth") is not None and m["breadth"] >= 0.5)


if __name__ == "__main__":
    from theme_radar import theme_metrics, heat_scores, classify_stage
    b = load_baskets(); bench = b["_meta"]["benchmark"]
    tickers = sorted({t for th in b["themes"]
                      for t in th["core"] + th["second_derivative"]} | {bench})
    close = fetch(tickers, "400d"); spy = close[bench]
    metrics = heat_scores([theme_metrics(t, close, spy) for t in b["themes"]])
    for m in metrics:
        m["stage"] = classify_stage(m)
    metrics.sort(key=lambda m: (m["heat"] or -1), reverse=True)
    print("STRONG-THEME PICKS (buy-strength; valuation = risk flag only)\n" + "=" * 60)
    bythme = {t["theme"]: t for t in b["themes"]}
    for m in metrics:
        if not is_strong(m):
            continue
        picks = rank_theme(close, bythme[m["theme"]])
        print(f"\n{m['theme']}  (heat {m['heat']:.0f}, RS_6m {m['rs_6m']*100:+.0f}%)")
        for p in picks:
            v = f"  [{p['valuation'][0]} {p['valuation'][1]}]" if p.get("valuation") else ""
            print(f"  {p['ticker']:<6} {p['ret_6m']*100:+6.0f}% 6m  {p['role']}{v}")
