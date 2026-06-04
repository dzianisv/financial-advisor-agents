"""
Crypto OHLCV loader for day-trade backtests — Coinbase (our target CDP venue), via ccxt.
Paginates fetch_ohlcv (300/call), caches to backtests/daytrade/data/<sym>_<tf>.csv.
Point-in-time: bars are exchange closes; the backtest decides on the PRIOR bar only.

Educational analysis, not financial advice.
"""
import os, time, sys
import pandas as pd

CACHE = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(CACHE, exist_ok=True)


def fetch(symbol="BTC/USD", timeframe="4h", since="2021-01-01T00:00:00Z", exchange="coinbase"):
    """Return a DataFrame indexed by UTC ts with open/high/low/close/volume. Cached."""
    safe = symbol.replace("/", "-")
    path = os.path.join(CACHE, f"{safe}_{timeframe}.csv")
    if os.path.exists(path):
        df = pd.read_csv(path, parse_dates=["ts"], index_col="ts")
        return df
    import ccxt
    ex = getattr(ccxt, exchange)()
    ex.load_markets()
    if symbol not in ex.markets:
        raise ValueError(f"{symbol} not listed on {exchange}")
    ms = ex.parse8601(since)
    tf_ms = ex.parse_timeframe(timeframe) * 1000
    now = ex.milliseconds()
    rows = []
    last_ts = -1
    empty_skips = 0
    while ms < now:
        batch = None
        for attempt in range(4):  # retry transient empties / rate limits
            try:
                batch = ex.fetch_ohlcv(symbol, timeframe, since=ms, limit=300)
            except Exception:
                batch = None
            if batch:
                break
            time.sleep(1.0 + attempt)
        if not batch:
            # empty can mean pre-listing dates (Coinbase returns nothing, not a skip).
            # Step forward a window and keep probing; only give up after data started
            # or many consecutive empties near the end.
            if rows or empty_skips > 60:
                break
            empty_skips += 1
            ms += 300 * tf_ms
            continue
        empty_skips = 0
        rows += batch
        new_last = batch[-1][0]
        if new_last <= last_ts:  # no forward progress -> done
            break
        last_ts = new_last
        ms = new_last + tf_ms
        time.sleep(ex.rateLimit / 1000.0)
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df = df.drop_duplicates("ts")
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df = df.set_index("ts").sort_index()
    df.to_csv(path)
    return df


def load_universe(symbols, timeframe="4h", since="2021-01-01T00:00:00Z"):
    out = {}
    for s in symbols:
        try:
            out[s] = fetch(s, timeframe, since)
            print(f"  {s:10s} {len(out[s]):6d} bars  {out[s].index[0].date()} -> {out[s].index[-1].date()}")
        except Exception as e:
            print(f"  {s:10s} SKIP: {str(e)[:60]}")
    return out


if __name__ == "__main__":
    syms = ["BTC/USD", "ETH/USD", "SOL/USD", "HYPE/USD"]
    tf = sys.argv[1] if len(sys.argv) > 1 else "4h"
    print(f"Fetching {tf} bars from Coinbase (cached to data/):")
    load_universe(syms, tf)
