#!/usr/bin/env python3
"""Deterministic crypto-news fetcher for the narrative-news gather seat.

Fetches the crypto-native RSS feeds (the feed-* skills document the per-source
quirks), normalizes to the common article record, pipes them into news_store.py
(dedup + cross-run state), and prints the NEW/updated EVENTS as JSON.

One reliable command instead of N fragile WebFetch calls:
    python3 news_fetch.py --days 3 --db crypto/news/news.db

Stdlib only. Per-feed failures degrade to a logged [UNAVAILABLE], never crash.
Paywalled macro (ft/wsj/bloomberg) is intentionally NOT fetched here — those
feed-* skills are headline-only/[UNAVAILABLE] and handled by an agent when needed.
"""
import argparse, json, os, re, ssl, sys, subprocess, urllib.request
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.parse import urljoin
from xml.etree import ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
STORE = os.path.join(HERE, "news_store.py")

# Verified-resolving crypto-native RSS (2026-06-15). coindesk 308-redirects.
FEEDS = {
    "decrypt": "https://decrypt.co/feed",
    "cointelegraph": "https://cointelegraph.com/rss",
    "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "theblock": "https://www.theblock.co/rss.xml",
    "bitcoinmagazine": "https://bitcoinmagazine.com/feed",
}
UA = "Mozilla/5.0 (crypto-research; +https://example.invalid)"
TAG = re.compile(r"<[^>]+>")


def _fetch(url, depth=0):
    """GET with UA; follow 308 (urllib doesn't) up to 3 hops."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        return urllib.request.urlopen(req, timeout=20,
                                      context=ssl.create_default_context()).read()
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 307, 308) and depth < 3:
            loc = e.headers.get("Location")
            if loc:
                return _fetch(urljoin(url, loc), depth + 1)  # Location may be relative
        raise


def _clean(s):
    return unescape(TAG.sub("", s or "")).strip()


def _parse(source, xml_bytes):
    out = []
    root = ET.fromstring(xml_bytes)
    for item in root.iter("item"):
        def g(tag):
            el = item.find(tag)
            return el.text if el is not None else ""
        title = _clean(g("title"))
        if not title:
            continue
        pub = g("pubDate") or ""
        iso = ""
        try:
            iso = parsedate_to_datetime(pub).astimezone().isoformat() if pub else ""
        except Exception:
            iso = ""
        out.append({
            "source": source,
            "url": (g("link") or "").strip(),
            "title": title,
            "published_at": iso or pub,
            "summary": _clean(g("description"))[:600],
            "lang": "en",
            "tags": [],
        })
    return out


def main():
    ap = argparse.ArgumentParser(description="fetch crypto RSS -> news_store -> new events")
    ap.add_argument("--db", default=os.path.join(HERE, "..", "..", "..", "crypto", "news", "news.db"))
    ap.add_argument("--days", type=int, default=3)
    ap.add_argument("--k", type=int, default=15)
    ap.add_argument("--query", default="", help="if set, return ranked question-relevant events (hybrid BM25+near-dup) instead of all new-since; cuts noise")
    args = ap.parse_args()

    records, unavailable = [], []
    for name, url in FEEDS.items():
        try:
            records += _parse(name, _fetch(url))
        except Exception as e:
            unavailable.append(f"{name}:{type(e).__name__}")
            print(f"[UNAVAILABLE] feed {name}: {e}", file=sys.stderr)

    if not records:
        print(json.dumps({"events": [], "unavailable": unavailable,
                          "note": "all feeds [UNAVAILABLE]"}))
        return

    # ingest (idempotent) then ask the store for new/updated events
    tmp = os.path.join(HERE, ".fetch_tmp.json")
    with open(tmp, "w") as f:
        json.dump(records, f)
    try:
        subprocess.run([sys.executable, STORE, "--db", args.db, "ingest", "--json", tmp],
                       check=True, capture_output=True, text=True)
        if args.query:  # focused, ranked, relevant — cuts the new-since noise
            ns = subprocess.run([sys.executable, STORE, "--db", args.db, "query",
                                 "--q", args.query, "--days", str(args.days), "--k", str(args.k)],
                                check=True, capture_output=True, text=True)
        else:
            ns = subprocess.run([sys.executable, STORE, "--db", args.db, "new-since",
                                 "--days", str(args.days)], check=True, capture_output=True, text=True)
    finally:
        os.path.exists(tmp) and os.remove(tmp)

    try:
        events = json.loads(ns.stdout)
    except Exception:
        events = ns.stdout
    print(json.dumps({"fetched": len(records), "feeds_ok": len(FEEDS) - len(unavailable),
                      "unavailable": unavailable, "events": events}, indent=1))


if __name__ == "__main__":
    main()
