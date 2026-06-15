#!/usr/bin/env python3
"""
mention_velocity.py — deterministic narrative-velocity counter (the SanDisk instrument).

trend-stock-research's SYNTHESIZE does prose/theme acceleration; this is the hard, testable backstop:
count how many RECENT-DATED headlines mention each watchlist ticker, compare to that ticker's OWN
trailing baseline, and FLAG a spike (e.g. 0→3+/week). Spikes feed ~/.openclaw/workspace/investor/pools/narrative.jsonl so
signal-convergence-alert can cross them with dips/13F/congress — catching a multi-week narrative
build (SanDisk Sept-2025) BEFORE it's obvious.

Data: Google News RSS (free, no key, stdlib only). Counts only headlines whose pubDate is within
--days (Google serves a fixed ~100-item feed, so a recency filter is what makes counts move).
NEVER fabricates a headline; a failed fetch → that ticker is [unavailable], not invented.

Ledger: $NARRATIVE_LEDGER or ~/.openclaw/workspace/investor/narrative_ledger.jsonl

Usage:
    python3 mention_velocity.py --tickers NVDA,WDC,STX,MU,AVGO --days 7
    python3 mention_velocity.py --json            # uses a default large-cap watchlist
"""
from __future__ import annotations
import argparse, json, os, re, sys
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.request import Request, urlopen
from urllib.parse import quote
from xml.etree import ElementTree as ET

LEDGER = os.environ.get("NARRATIVE_LEDGER", os.path.expanduser("~/.openclaw/workspace/investor/narrative_ledger.jsonl"))
# DURABLE pool (NOT /tmp — convergence runs in a separate cron session that can't see this job's /tmp).
NARRATIVE_POOL = os.environ.get("NARRATIVE_POOL", os.path.expanduser("~/.openclaw/workspace/investor/pools/narrative.jsonl"))
MIN_BASELINE_OBS = 3  # need this many prior daily observations before a spike may FEED convergence (cold-start guard)
DEFAULT = ["NVDA", "WDC", "STX", "MU", "AVGO", "AMD", "TSM", "ASML", "ANET", "VRT",
           "SMCI", "MRVL", "KLAC", "LRCX", "DELL"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def fetch_recent_count(ticker: str, days: int) -> tuple[int, list[str]] | None:
    """Return (count_within_window, sample_headlines) or None on fetch failure (never fabricate)."""
    q = quote(f"{ticker} stock")
    url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=15) as r:
            xml = r.read()
    except Exception:
        return None
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return None
    cutoff = _now() - timedelta(days=days)
    count, samples = 0, []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        pub = item.findtext("pubDate")
        dt = None
        if pub:
            try:
                dt = parsedate_to_datetime(pub)
                if dt and dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                dt = None
        if dt is None or dt < cutoff:
            continue
        # Count is Google's query-relevance for "<ticker> stock" (fuzzy by design). We do NOT hard-gate on
        # the literal symbol — many real headlines say "Nvidia", not "NVDA". The SIGNAL is the velocity
        # RATIO vs this ticker's OWN baseline, so a constant fuzzy-match rate cancels out. Sample only
        # headlines that explicitly name the symbol (cleaner display).
        count += 1
        if len(samples) < 3 and re.search(rf"\b{re.escape(ticker)}\b", title, re.I):
            samples.append(title)
    return count, samples


def trailing_stats(ticker: str, exclude_today: bool = True) -> tuple[float, int]:
    """(mean, n_observations) of prior logged counts for this ticker — its own baseline + maturity."""
    if not os.path.exists(LEDGER):
        return 0.0, 0
    today = _now().date().isoformat()
    vals = []
    with open(LEDGER) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("ticker") != ticker:
                continue
            if exclude_today and str(r.get("date", "")).startswith(today):
                continue
            c = r.get("mentions")
            if isinstance(c, (int, float)):
                vals.append(float(c))
    return (round(sum(vals) / len(vals), 2) if vals else 0.0), len(vals)


def record(ticker: str, mentions: int) -> None:
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with open(LEDGER, "a") as f:
        f.write(json.dumps({"ticker": ticker, "date": _now().isoformat(), "mentions": mentions}) + "\n")


def feed_convergence(ticker: str, reason: str) -> None:
    try:
        os.makedirs(os.path.dirname(NARRATIVE_POOL) or ".", exist_ok=True)
        with open(NARRATIVE_POOL, "a") as f:
            f.write(json.dumps({"ticker": ticker, "reason": reason, "date": _now().date().isoformat()}) + "\n")
    except OSError:
        pass


def run(tickers: list[str], days: int, min_spike: int, ratio: float) -> list[dict]:
    out = []
    for t in tickers:
        res = fetch_recent_count(t, days)
        if res is None:
            out.append({"ticker": t, "mentions_now": None, "status": "[unavailable]"})
            continue
        now_n, samples = res
        base, n_obs = trailing_stats(t)
        record(t, now_n)  # persist AFTER reading baseline so today doesn't pollute its own avg
        vr = round(now_n / base, 2) if base > 0 else (float("inf") if now_n >= min_spike else 0.0)
        spike = now_n >= min_spike and (base == 0 or now_n >= ratio * base)
        mature = n_obs >= MIN_BASELINE_OBS               # cold-start guard: don't feed convergence yet
        pool_fed = bool(spike and mature)
        row = {"ticker": t, "mentions_now": now_n, "trailing_avg": base, "baseline_obs": n_obs,
               "velocity_ratio": (None if vr == float("inf") else vr), "spike": spike,
               "pool_fed": pool_fed, "sample_headlines": samples}
        if pool_fed:
            feed_convergence(t, f"narrative velocity spike: {now_n} mentions/{days}d vs trailing {base} ({n_obs}obs)")
        out.append(row)
    out.sort(key=lambda r: (r.get("spike") is True, r.get("mentions_now") or 0), reverse=True)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", default=",".join(DEFAULT))
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--min-spike", type=int, default=3, help="min recent mentions to qualify as a spike")
    ap.add_argument("--ratio", type=float, default=2.0, help="current must be >= ratio x trailing baseline")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    tickers = [t.strip().upper() for t in a.tickers.split(",") if t.strip()]
    rows = run(tickers, a.days, a.min_spike, a.ratio)

    if a.json:
        print(json.dumps(rows, indent=2))
        return
    spikes = [r for r in rows if r.get("spike")]
    print(f"\n=== NARRATIVE VELOCITY ({a.days}d window) ===\n")
    if not spikes:
        print("  No mention-velocity spikes. (Baselines build over a few days of runs.)")
    for r in spikes:
        vr = r["velocity_ratio"]
        print(f"  [SPIKE] {r['ticker']:5s}  {r['mentions_now']} mentions vs trailing {r['trailing_avg']}"
              f"  (x{vr if vr is not None else '∞'})")
        for h in r["sample_headlines"]:
            print(f"          - {h}")
    print("\n  Educational only — not advice. Spikes appended to the convergence pool.\n")


if __name__ == "__main__":
    main()
