#!/usr/bin/env python3
"""
Pull current fundamentals + price levels for ONE stock via yfinance, so the
stocks-advisor orchestrator can inject them into the data package the
analyst seats reason over. Subagents cannot call yfinance (no network tools), so
the orchestrator runs this once per ticker and merges the output.

IMPORTANT — point-in-time UNSAFE: yfinance returns *today's* fundamentals. That
is correct for CURRENT screening/entry analysis (what this skill does), but it
is look-ahead-biased for backtesting. Never feed this script's output into a
historical screen backtest — route those to strategy-discovery-backtest with a
point-in-time vendor (Sharadar/SimFin). See the fundamental-analysis skill.

INPUT (JSON file passed as argv[1]):
  {"symbol": "AVGO", "period": "1y"}

OUTPUT (written to <path>.out.json, also printed to stdout):
  symbol, company, price, 52w_high, 52w_low, ma50, ma200,
  forward_pe, trailing_pe, peg_ratio, revenue_growth, earnings_growth,
  gross_margin, operating_margin, fcf, market_cap, fcf_yield, roe,
  short_percent, institutional_pct, recommendation_mean, analyst_count,
  dd_from_52wh, vs_200d_ma, vs_50d_ma
  (any field yfinance does not provide is emitted as null — never invented)

USAGE:
  python3 fundamentals.py /path/to/AVGO.json
"""
import json
import sys


def pct(numer, denom):
    """Percent change of numer vs denom, rounded to 1 dp; None if unusable."""
    if numer is None or denom in (None, 0):
        return None
    return round((numer / denom - 1) * 100, 1)


def ratio_pct(part, whole):
    """part/whole as a percentage (e.g. fcf_yield, short %), 2 dp; None if unusable."""
    if part is None or whole in (None, 0):
        return None
    return round(part / whole * 100, 2)


def to_pct(frac, dp=1):
    """yfinance gives margins/growth/ownership as fractions (0.48 = 48%)."""
    if frac is None:
        return None
    return round(frac * 100, dp)


def fundamentals(symbol, period="1y"):
    import yfinance as yf

    t = yf.Ticker(symbol)
    info = t.info or {}

    # Price: prefer the live quote, fall back to the last historical close.
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    hi = info.get("fiftyTwoWeekHigh")
    lo = info.get("fiftyTwoWeekLow")
    ma50 = info.get("fiftyDayAverage")
    ma200 = info.get("twoHundredDayAverage")

    # Recompute MAs and 52w levels from history when possible — more transparent
    # than the .info rollups and resilient when those fields are missing.
    try:
        hist = t.history(period=period)
        if not hist.empty:
            closes = hist["Close"].dropna()
            if price is None and len(closes):
                price = float(closes.iloc[-1])
            if len(closes) >= 200:
                ma200 = float(closes.rolling(200).mean().iloc[-1])
            if len(closes) >= 50:
                ma50 = float(closes.rolling(50).mean().iloc[-1])
            if hi is None:
                hi = float(closes.max())
            if lo is None:
                lo = float(closes.min())
    except Exception:
        pass  # keep the .info values; never crash on a data gap

    market_cap = info.get("marketCap")
    fcf = info.get("freeCashflow")

    out = {
        "symbol": symbol,
        "company": info.get("longName") or info.get("shortName") or symbol,
        "price": round(price, 2) if price is not None else None,
        "52w_high": round(hi, 2) if hi is not None else None,
        "52w_low": round(lo, 2) if lo is not None else None,
        "ma50": round(ma50, 2) if ma50 is not None else None,
        "ma200": round(ma200, 2) if ma200 is not None else None,
        # Valuation
        "forward_pe": info.get("forwardPE"),
        "trailing_pe": info.get("trailingPE"),
        "peg_ratio": info.get("trailingPegRatio") or info.get("pegRatio"),
        # Growth (fractions -> %)
        "revenue_growth": to_pct(info.get("revenueGrowth")),
        "earnings_growth": to_pct(
            info.get("earningsGrowth") or info.get("earningsQuarterlyGrowth")
        ),
        # Margins / quality (fractions -> %)
        "gross_margin": to_pct(info.get("grossMargins")),
        "operating_margin": to_pct(info.get("operatingMargins")),
        "roe": to_pct(info.get("returnOnEquity")),
        # Cash flow
        "fcf": fcf,
        "market_cap": market_cap,
        "fcf_yield": ratio_pct(fcf, market_cap),
        # Positioning / sentiment
        "short_percent": to_pct(info.get("shortPercentOfFloat"), dp=2),
        "institutional_pct": to_pct(info.get("heldPercentInstitutions")),
        "recommendation_mean": info.get("recommendationMean"),
        "analyst_count": info.get("numberOfAnalystOpinions"),
        # Derived price-level context
        "dd_from_52wh": pct(price, hi),
        "vs_200d_ma": pct(price, ma200),
        "vs_50d_ma": pct(price, ma50),
    }
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: fundamentals.py <input.json>  (input: {\"symbol\":\"AVGO\",\"period\":\"1y\"})")

    path = sys.argv[1]
    with open(path) as f:
        spec = json.load(f)

    symbol = spec["symbol"].upper().strip()
    period = spec.get("period", "1y")

    try:
        out = fundamentals(symbol, period)
    except Exception as e:
        out = {"symbol": symbol, "error": f"{type(e).__name__}: {e}"}

    out_path = path + ".out.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
