#!/usr/bin/env python3
"""
dip_screener.py — Daily quality-stock dip scanner.
Screens S&P 100 for stocks >= threshold% below their 52-week INTRADAY high.
Educational only — not investment advice.

Usage:
    python3 dip_screener.py
    python3 dip_screener.py --threshold 25
    python3 dip_screener.py --json

Honesty notes:
  - "52w high" = max of the trailing-1-year INTRADAY HIGH (yfinance 'High', auto_adjust=False),
    NOT a closing-price max and NOT an all-time high. pct_from_high uses the real high.
  - sma200 is null when <200 trading days of history exist (never a mislabeled shorter mean).
"""
from __future__ import annotations
import argparse, json, os, sys, time
from datetime import datetime, timezone

try:
    import yfinance as yf
except ImportError:
    sys.exit("pip install yfinance")

# DURABLE pool path (NOT /tmp — openclaw isolated cron sessions don't share /tmp, so a pool written by
# the 07:45 dip job must live on disk for the 08:30 convergence job to read it).
DEFAULT_POOL = os.environ.get(
    "DIP_POOL", os.path.expanduser("~/.openclaw/workspace/investor/pools/dip_candidates.jsonl"))

SP100 = [
    "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "BRK-B", "LLY", "JPM", "V",
    "UNH", "TSLA", "XOM", "MA", "JNJ", "PG", "AVGO", "HD", "COST", "ABBV",
    "MRK", "CVX", "KO", "PEP", "ADBE", "WMT", "BAC", "CRM", "ACN", "TMO",
    "MCD", "CSCO", "ABT", "DHR", "NFLX", "ORCL", "AMD", "QCOM", "TXN", "PM",
    "NEE", "AMGN", "IBM", "INTC", "HON", "CAT", "GE", "SPGI", "MS", "GS",
    "RTX", "BLK", "T", "UNP", "AXP", "ELV", "MDT", "PFE", "BMY", "GILD",
    "USB", "C", "LOW", "DE", "SBUX", "SCHW", "MO", "BA", "MMC", "CVS",
    "SO", "DUK", "CL", "ZTS", "CB", "NOW", "ISRG", "ADI", "REGN", "SYK",
    "PLD", "AMT", "EQIX", "VRTX", "PANW", "ANET", "MU", "KLAC", "LRCX", "SNPS",
    "AON", "TGT", "FDX", "ETN", "ADP", "ITW", "NSC", "WM", "APH", "CARR",
]


def scan(threshold_pct: float = 20.0) -> list[dict]:
    results = []
    batch_size = 10
    for i in range(0, len(SP100), batch_size):
        batch = SP100[i:i + batch_size]
        try:
            # auto_adjust=False so we get the true unadjusted intraday High/Close.
            raw = yf.download(batch, period="1y", auto_adjust=False, progress=False, group_by="column")
        except Exception as e:
            print(f"[dip-screener] batch fetch failed {batch}: {e}", file=sys.stderr)
            time.sleep(2)
            continue
        try:
            close = raw["Close"]
            high = raw["High"]
        except Exception:
            print(f"[dip-screener] batch missing OHLC columns {batch}", file=sys.stderr)
            continue
        for ticker in batch:
            try:
                if ticker not in close.columns:
                    print(f"[dip-screener] no data for {ticker} (skipped)", file=sys.stderr)
                    continue
                cs = close[ticker].dropna()
                hs = high[ticker].dropna()
                if len(cs) < 20 or len(hs) < 20:
                    continue
                current = float(cs.iloc[-1])
                high_52w = float(hs.max())  # true trailing-1y intraday high
                pct_from_high = (current - high_52w) / high_52w * 100
                if len(cs) >= 200:
                    sma200 = float(cs.rolling(200).mean().iloc[-1])
                    pct_vs_200d = round((current - sma200) / sma200 * 100, 1)
                else:
                    sma200 = None
                    pct_vs_200d = None
                if pct_from_high <= -threshold_pct:
                    results.append({
                        "ticker": ticker,
                        "current": round(current, 2),
                        "high_52w": round(high_52w, 2),
                        "pct_from_high": round(pct_from_high, 1),
                        "sma200": round(sma200, 2) if sma200 is not None else None,
                        "pct_vs_200d": pct_vs_200d,
                        "conviction": (
                            "HIGH" if pct_from_high <= -30
                            else "MEDIUM" if pct_from_high <= -25
                            else "WATCH"
                        ),
                    })
            except Exception as e:
                print(f"[dip-screener] {ticker} parse error: {e}", file=sys.stderr)
                continue
        time.sleep(1)
    results.sort(key=lambda x: x["pct_from_high"])
    return results


def emit_pool(hits: list[dict], path: str) -> int:
    """Deterministically append HIGH+MEDIUM dips to the durable convergence pool (no LLM in the loop)."""
    rows = [h for h in hits if h["conviction"] in ("HIGH", "MEDIUM")]
    if not rows:
        return 0
    today = datetime.now(timezone.utc).date().isoformat()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a") as f:
        for h in rows:
            f.write(json.dumps({
                "ticker": h["ticker"],
                "reason": f"dip {h['pct_from_high']}% below 52w high ({h['conviction']})",
                "date": today,
            }) + "\n")
    return len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=float, default=20.0)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--emit-pool", nargs="?", const=DEFAULT_POOL, default=None,
                    help="append HIGH+MEDIUM dips to the durable convergence pool (default: %(default)s)")
    a = ap.parse_args()

    hits = scan(a.threshold)

    if a.emit_pool:
        n = emit_pool(hits, a.emit_pool)
        print(f"[dip-screener] wrote {n} candidate(s) to pool {a.emit_pool}", file=sys.stderr)

    if a.json:
        print(json.dumps(hits, indent=2))
        return

    if not hits:
        print(f"No S&P 100 stocks >= {a.threshold:.0f}% below 52-week high today.")
        return

    print(f"\n=== DIP SCREENER — S&P 100 stocks >= {a.threshold:.0f}% below 52-week intraday high ===\n")
    for r in hits:
        label = {"HIGH": "[HIGH]", "MEDIUM": "[MED]", "WATCH": "[WATCH]"}[r["conviction"]]
        if r["sma200"] is not None:
            trend = "above" if r["pct_vs_200d"] >= 0 else "below"
            ma = f"200dMA ${r['sma200']:.2f} ({r['pct_vs_200d']:+.1f}% {trend})"
        else:
            ma = "200dMA n/a (<200d history)"
        print(
            f"  {label} {r['ticker']:6s}  {r['pct_from_high']:+.1f}% from 52w high (${r['high_52w']:.2f})  "
            f"now ${r['current']:.2f}  {ma}"
        )
    print(f"\n  {len(hits)} candidate(s). Educational only — not advice.\n")


if __name__ == "__main__":
    main()
