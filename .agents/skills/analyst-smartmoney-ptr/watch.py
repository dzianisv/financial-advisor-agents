#!/usr/bin/env python3
"""analyst-smartmoney-ptr — STOCK Act dedup ledger manager.

The HTTP fetching is done by the LLM agent (via WebFetch on capitoltrades.com).
This script only manages the dedup ledger so tickers are never proposed twice.

Dedup key: (ticker, transaction_date) — a new filing on the same ticker re-alerts;
the same filing date on the same ticker is suppressed. Old rows without transaction_date
have r.get("transaction_date","") == "" which never matches a real date, so they
surface as new on next run (correct — they lack the date context to suppress).

Usage:
  watch.py seen <TICKER> --date YYYY-MM-DD   # exit 0=already recommended; exit 1=NEW
  watch.py record --ticker NVDA --member "Nancy Pelosi" --chamber house \\
                  --date 2026-01-15 --amount "$1,000,001+" --action purchase \\
                  [--reason "..."] [--committee "Science, Space & Technology"]
  watch.py list [--since YYYY-MM-DD]
"""
import argparse
import json
import os
import sys
from datetime import date, datetime

_SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_SKILL_DIR, "..", "..", ".."))
LEDGER = os.environ.get("CONGRESS_LEDGER", os.path.join(_REPO_ROOT, ".cache", "PTR", "recommended.jsonl"))


def _load() -> list:
    if not os.path.exists(LEDGER):
        return []
    with open(LEDGER) as f:
        return [json.loads(l) for l in f if l.strip()]


def _seen(ticker: str, transaction_date: str) -> bool:
    """Return True if (ticker, transaction_date) pair already in ledger."""
    t = ticker.upper()
    return any(
        r["ticker"].upper() == t and r.get("transaction_date", "") == transaction_date
        for r in _load()
    )


def _record(ticker: str, transaction_date: str) -> None:
    """Write a minimal ledger entry (used by tests and internal callers)."""
    entry = {
        "ticker": ticker.upper(),
        "transaction_date": transaction_date,
        "recommended_on": date.today().isoformat(),
    }
    os.makedirs(os.path.dirname(LEDGER) or ".", exist_ok=True)
    with open(LEDGER, "a") as f:
        f.write(json.dumps(entry) + "\n")


def cmd_seen(a):
    t = a.ticker.upper()
    transaction_date = getattr(a, "date", "") or ""
    if _seen(t, transaction_date):
        rows = _load()
        r = next(
            r for r in rows
            if r["ticker"].upper() == t and r.get("transaction_date", "") == transaction_date
        )
        print(f"SEEN {t}@{transaction_date} — recommended {r['recommended_on']} via {r.get('member','?')} ({r.get('chamber','?')}); SKIP")
        sys.exit(0)
    print(f"NEW {t}@{transaction_date} — not yet recommended; ok to propose")
    sys.exit(1)


def cmd_record(a):
    try:
        datetime.strptime(a.date, "%Y-%m-%d")
    except ValueError:
        print(f"error: --date must be YYYY-MM-DD, got '{a.date}'", file=sys.stderr)
        sys.exit(2)
    t = a.ticker.upper()
    if _seen(t, a.date):
        print(f"skip: {t}@{a.date} already recommended — dedup rule", file=sys.stderr)
        sys.exit(3)
    entry = {
        "ticker": t,
        "member": a.member,
        "chamber": a.chamber,
        "transaction_date": a.date,
        "amount": a.amount or "",
        "action": a.action,
        "reason": a.reason or "",
        "committee": a.committee or "",
        "recommended_on": date.today().isoformat(),
    }
    os.makedirs(os.path.dirname(LEDGER) or ".", exist_ok=True)
    with open(LEDGER, "a") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"recorded {t}  {a.member}  {a.chamber}  {a.date}  ({a.action})")


def cmd_list(a):
    rows = _load()
    if a.since:
        rows = [r for r in rows if r["recommended_on"] >= a.since]
    if not rows:
        print("(none)")
        return
    for r in sorted(rows, key=lambda r: r["recommended_on"]):
        print(f'{r["recommended_on"]}  {r["ticker"]:<6}  {r["member"]} [{r["chamber"]}]  '
              f'{r.get("amount","")}  {r.get("reason","")}')


def main():
    p = argparse.ArgumentParser(description="analyst-smartmoney-ptr dedup ledger")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("seen", help="check if ticker+date already recommended")
    s.add_argument("ticker")
    s.add_argument("--date", default="", help="transaction date YYYY-MM-DD (required for date-scoped dedup)")
    s.set_defaults(fn=cmd_seen)

    s = sub.add_parser("record", help="record a new recommendation")
    s.add_argument("--ticker", required=True)
    s.add_argument("--member", required=True)
    s.add_argument("--chamber", required=True, choices=["house", "senate"])
    s.add_argument("--date", required=True, help="transaction date YYYY-MM-DD")
    s.add_argument("--amount", default="")
    s.add_argument("--action", required=True, choices=["purchase", "exchange"])
    s.add_argument("--reason", default="")
    s.add_argument("--committee", default="")
    s.set_defaults(fn=cmd_record)

    s = sub.add_parser("list", help="list all recommended tickers")
    s.add_argument("--since", help="YYYY-MM-DD filter")
    s.set_defaults(fn=cmd_list)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
