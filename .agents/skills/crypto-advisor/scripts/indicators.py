#!/usr/bin/env python3
"""
Fill the ONE gap the TradingView MCP can't: moving averages.

Read RSI(14), Bollinger(20,2), MACD(12,26,9) and Volume straight from the MCP
(`data_get_study_values`) — they return correctly at their standard lengths, so
do NOT recompute them. The MCP's `chart_manage_indicator`, however, ignores the
moving-average `length` input (an added MA exposes `inputs:[]` and stays stuck
at a short default ~= price; verified for BTC: read $64,540 when SMA200 was
~$76,600) and has no `update` action. So EMA20 / SMA50 / SMA200 / 200-week-MA
are the only values that must be computed here — from the MCP's OWN returned
closes, so the data source stays 100% TradingView. These are plain rolling means
(SMA) / EWMs (EMA20); nothing TradingView would compute differently.

Death cross uses the classic SMA50/SMA200 (exact with N bars, no warmup error).

INPUT (stdin or file): JSON, one object per token:
  {"symbol":"BTC",
   "price": 64522.49,                          # last close from the MCP
   "daily_closes":[...>=200 daily closes...],  # from MCP data_get_ohlcv
   "weekly_closes":[...weekly closes, optional]}# from MCP, for the 200-week MA

USAGE:
  cat mas.json | python3 indicators.py
  python3 indicators.py mas.json

OUTPUT: only the moving-average block — merge it into the data package alongside
the RSI/BB/MACD/Volume/52w values you read directly from TradingView.
"""
import json, sys
import pandas as pd
import numpy as np


def moving_averages(t):
    c = pd.Series([float(x) for x in t["daily_closes"]])
    price = float(t.get("price", c.iloc[-1]))
    e20 = float(c.ewm(span=20, adjust=False).mean().iloc[-1])
    sma50 = float(c.rolling(50).mean().iloc[-1]) if len(c) >= 50 else None
    sma200 = float(c.rolling(200).mean().iloc[-1]) if len(c) >= 200 else None

    wk200 = None
    wc = t.get("weekly_closes")
    if wc and len(wc) >= 50:
        ws = pd.Series([float(x) for x in wc])
        wk200 = float(ws.rolling(min(200, len(ws))).mean().iloc[-1])

    pos = lambda e: ("ABOVE" if price > e else "BELOW") if e else None
    return {
        "symbol": t["symbol"], "src": "tradingview-mcp closes",
        "ema20": round(e20, 4), "sma50": round(sma50, 4) if sma50 else None,
        "sma200": round(sma200, 4) if sma200 else None,
        "vs_ema20": pos(e20), "vs_sma50": pos(sma50), "vs_sma200": pos(sma200),
        "death_cross_50_200": (sma50 < sma200) if (sma50 and sma200) else None,
        "ma200w": round(wk200, 4) if wk200 else None,
        "pct_vs_200wma": round((price / wk200 - 1) * 100, 1) if wk200 else None,
    }


def main():
    raw = open(sys.argv[1]).read() if len(sys.argv) > 1 else sys.stdin.read()
    data = json.loads(raw)
    items = data if isinstance(data, list) else [data]
    print(json.dumps([moving_averages(t) for t in items], indent=2))


if __name__ == "__main__":
    main()
