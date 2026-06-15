#!/usr/bin/env python3
"""
convergence.py — Cross-reference the day's signal pools; surface tickers hit by >= N
independent sources. The point: a ticker that shows up in BOTH a dip screen AND journalism
AND a 13F buy is a high-conviction, time-sensitive convergence — DM it immediately.

Reads (any subset that exists):
  ~/.openclaw/workspace/investor/pools/dip_candidates.jsonl   {"ticker": "...", ...}   source=dip (≤5d)
  ~/.openclaw/workspace/investor/pools/narrative.jsonl        {"ticker": "...", ...}   source=journalism (≤5d)
  <13F ledger>.jsonl          {"ticker": "...", ...}            source=13f       (last 14d)
  <congress ledger>.jsonl     {"ticker": "...", ...}            source=congress  (last 14d)

Educational only — not advice. No fabrication: only reports what is actually in the pools.

Usage:
    python3 convergence.py
    python3 convergence.py --min-sources 2 --json
"""
from __future__ import annotations
import argparse, json, os, sys
from datetime import datetime, timedelta, timezone

# DURABLE pool paths — NOT /tmp. openclaw isolated cron sessions don't share /tmp, so the dip job
# (07:45) and convergence job (08:30) run in separate sandboxes; the pool MUST live on disk between them.
# Daily pools carry a freshness window (stale dips/narratives don't count as "today's convergence").
_POOLS_DIR = os.path.expanduser("~/.openclaw/workspace/investor/pools")
POOLS = [
    ("dip", os.environ.get("DIP_POOL", os.path.join(_POOLS_DIR, "dip_candidates.jsonl")), 5),
    ("journalism", os.environ.get("NARRATIVE_POOL", os.path.join(_POOLS_DIR, "narrative.jsonl")), 5),
    ("13f", os.environ.get("THIRTEENF_LEDGER", os.path.expanduser("~/.openclaw/workspace/investor/13f/recommended.jsonl")), 14),
    ("congress", os.environ.get("CONGRESS_LEDGER", os.path.expanduser("~/.openclaw/workspace/investor/congress/recommended.jsonl")), 14),
]


def _load(path: str, max_age_days: int | None) -> list[dict]:
    rows = []
    if not os.path.exists(path):
        return rows
    cutoff = None
    if max_age_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if cutoff is not None:
                    # FAIL CLOSED: this feeds an "immediate DM" signal, so a row whose date is
                    # missing or unparseable must NOT leak into "today's convergence". Drop it.
                    d = r.get("date") or r.get("recorded") or r.get("ts")
                    keep = False
                    if d is not None:
                        try:
                            dt = datetime.fromisoformat(str(d).replace("Z", "+00:00"))
                            if dt.tzinfo is None:
                                dt = dt.replace(tzinfo=timezone.utc)
                            keep = dt >= cutoff
                        except (ValueError, TypeError):
                            keep = False
                    if not keep:
                        continue
                rows.append(r)
    except OSError:
        pass
    return rows


def converge(min_sources: int = 2) -> dict:
    by_ticker: dict[str, dict] = {}
    for source, path, max_age in POOLS:
        for r in _load(path, max_age):
            t = (r.get("ticker") or r.get("symbol") or "").upper().strip()
            if not t:
                continue
            entry = by_ticker.setdefault(t, {"ticker": t, "sources": {}, "notes": []})
            entry["sources"][source] = True
            note = r.get("note") or r.get("reason") or r.get("why")
            if note:
                entry["notes"].append(f"{source}: {note}")

    hits = []
    for t, e in by_ticker.items():
        srcs = sorted(e["sources"].keys())
        if len(srcs) >= min_sources:
            hits.append({"ticker": t, "sources": srcs, "n_sources": len(srcs), "notes": e["notes"]})
    hits.sort(key=lambda x: x["n_sources"], reverse=True)
    return {"min_sources": min_sources, "convergences": hits, "pools_read": [p for _, p, _ in POOLS if os.path.exists(p)]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-sources", type=int, default=2)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    r = converge(a.min_sources)

    if a.json:
        print(json.dumps(r, indent=2))
        return

    print("\n=== SIGNAL CONVERGENCE ===\n")
    if not r["pools_read"]:
        print("  No signal pools found. Run the daily scans first.")
        return
    if not r["convergences"]:
        print(f"  No ticker hit by >= {a.min_sources} independent sources today.")
    else:
        for h in r["convergences"]:
            print(f"  [{h['n_sources']}x] {h['ticker']:6s}  sources: {', '.join(h['sources'])}")
            for n in h["notes"]:
                print(f"          - {n}")
    print("\n  Educational only — not advice.\n")


if __name__ == "__main__":
    main()
