#!/usr/bin/env python3
"""
inject_context.py — helper for stocks-portfolio-manager and crypto-portfolio-manager.

Recalls prior verdicts + durable preferences for the run's tickers and prints
a formatted prior-context block ready to inject into any seat prompt.

Usage:
    python3 .agents/skills/portfolio-memory/scripts/inject_context.py \
        --db .db/portfolio_memory.db \
        --desk stocks \
        --tickers COIN PYPL AVGO

Output (stdout): a plain-text <prior_context> block.
"""

import argparse
import sys
import os

# Allow running from repo root or directly
_SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _SKILL_DIR)

from memory import connect, recall, load_preferences, format_context  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inject prior memory context for portfolio-manager seats"
    )
    parser.add_argument("--db", default=".db/portfolio_memory.db", help="Path to SQLite DB")
    parser.add_argument("--desk", required=True, help="stocks | crypto")
    parser.add_argument("--tickers", nargs="+", required=True, help="Ticker symbols for this run")
    parser.add_argument("--k", type=int, default=8, help="Max recalled rows per ticker")
    parser.add_argument("--half-life", type=float, default=45.0, dest="half_life",
                        help="Recency decay half-life in days (default 45)")
    args = parser.parse_args()

    con = connect(args.db)

    # Recall for each ticker and deduplicate by id (same row can rank for multiple tickers)
    seen_ids: set[int] = set()
    all_memories: list[dict] = []

    for ticker in args.tickers:
        rows = recall(con, query=ticker, desk=args.desk, k=args.k, half_life_days=args.half_life)
        for row in rows:
            rid = row.get("id")
            if rid not in seen_ids:
                seen_ids.add(rid)
                all_memories.append(row)

    # Sort merged list by score descending (score is 0.0 in fallback path)
    all_memories.sort(key=lambda r: r.get("score") or 0.0, reverse=True)

    # Also recall a global desk-level query to catch cross-ticker preferences / themes
    general_rows = recall(con, query=args.desk, desk=args.desk, k=4, half_life_days=args.half_life)
    for row in general_rows:
        rid = row.get("id")
        if rid not in seen_ids:
            seen_ids.add(rid)
            all_memories.append(row)

    prefs = load_preferences(con, desk=args.desk)

    if not all_memories and not prefs:
        print("<prior_context>\n[no prior memory for this run]\n</prior_context>")
        return

    context = format_context(prefs, all_memories)
    print(f"<prior_context>\n{context}\n</prior_context>")


if __name__ == "__main__":
    main()
