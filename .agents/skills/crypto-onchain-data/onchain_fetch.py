#!/usr/bin/env python3
"""Deterministic BTC on-chain valuation fetcher for the crypto-onchain-data seat.

Replaces the flaky JS-gated WebFetch path (checkonchain/lookintobitcoin 403/428)
with a reliable JSON API (bitcoin-data.com, no key). Stops MVRV-Z/NUPL/Puell from
coming back [UNAVAILABLE] run-to-run.

    python3 onchain_fetch.py            # -> JSON {metric,value,asof,source}[] + unavailable[]

Stdlib only. Per-metric failures degrade to a logged [UNAVAILABLE], never crash.
Price + 200d/200w MA come from yfinance in the seat (reliable); this covers the
on-chain valuation CORE only.
"""
import json, os, ssl, sys, time, urllib.request

BASE = "https://bitcoin-data.com/v1"
UA = "Mozilla/5.0 (crypto-research)"
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "..", "..", "..", "crypto", "news", "onchain_cache.json")
# endpoint -> (json key, human metric, zone hint)
METRICS = {
    "mvrv-zscore":    ("mvrvZscore",    "MVRV-Z score",  "tops >7, accumulation <1"),
    "nupl":           ("nupl",          "NUPL",          "euphoria >0.75, capitulation <0"),
    "puell-multiple": ("puellMultiple", "Puell multiple", "miner stress / capitulation <0.5"),
    "realized-price": ("realizedPrice", "Realized price ($)", "aggregate cost basis"),
}


def _get(url):
    # bitcoin-data.com rate-limits bursts (429). One gentle retry; the 2s inter-request
    # spacing in main() is what actually keeps us under the limit.
    for i in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            return urllib.request.urlopen(req, timeout=20, context=ssl.create_default_context()).read()
        except urllib.error.HTTPError as e:
            if e.code == 429 and i == 0:
                time.sleep(5)
                continue
            raise


def _load_cache():
    try:
        with open(CACHE) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(cache):
    try:
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        with open(CACHE, "w") as f:
            json.dump(cache, f, indent=1)
    except Exception:
        pass


def main():
    cache = _load_cache()
    out, unavailable, from_cache = [], [], []
    for ep, (key, name, hint) in METRICS.items():
        try:
            d = json.loads(_get(f"{BASE}/{ep}/last"))
            val = d.get(key)
            if val is None:
                raise ValueError(f"no key {key}")
            rec = {"metric": name, "value": val, "asof": d.get("d", ""),
                   "source": f"bitcoin-data.com/{ep}", "zone_hint": hint}
            out.append(rec)
            cache[ep] = rec  # refresh cache on every live success
        except Exception as e:
            # rate-limited / gated → serve the last good value, honestly labeled with its real as-of date
            if ep in cache:
                rec = dict(cache[ep])
                rec["source"] += " (CACHED — live pull rate-limited)"
                out.append(rec)
                from_cache.append(ep)
            else:
                unavailable.append(ep)
                print(f"[UNAVAILABLE] {ep}: {e}", file=sys.stderr)
        time.sleep(2)  # polite spacing to stay under the rate limit
    _save_cache(cache)
    print(json.dumps({"onchain_core": out, "unavailable": unavailable, "served_from_cache": from_cache,
                      "note": "valuation core via bitcoin-data.com (cache-on-ratelimit; metrics are daily-granular so a 1-2d-old cached value is valid, labeled with its real as-of); price/MA from yfinance; ETF flows separate"},
                     indent=1))


if __name__ == "__main__":
    main()
