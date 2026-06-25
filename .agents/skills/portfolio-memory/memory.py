#!/usr/bin/env python3
"""
portfolio-memory — SQLite FTS5 BM25 + exponential recency-decay cross-run memory store.

Architecture mirrors crypto-news-store/news_store.py.
Stdlib only — no numpy, no embeddings, no external dependencies.
"""

import argparse
import datetime
import json
import os
import re
import sqlite3
import sys

DEFAULT_DB = ".db/portfolio_memory.db"

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS memory (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  kind        TEXT NOT NULL,
  desk        TEXT NOT NULL,
  ticker      TEXT,
  verdict     TEXT,
  body        TEXT NOT NULL,
  meta        TEXT,
  run_id      TEXT,
  created_at  TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts
  USING fts5(ticker, body, content='memory', content_rowid='id',
             tokenize='porter unicode61');

CREATE TRIGGER IF NOT EXISTS mem_ai AFTER INSERT ON memory BEGIN
  INSERT INTO memory_fts(rowid, ticker, body) VALUES (new.id, new.ticker, new.body);
END;

CREATE TABLE IF NOT EXISTS preferences (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  desk        TEXT,
  scope       TEXT,
  text        TEXT NOT NULL,
  created_at  TEXT NOT NULL
);
"""


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def connect(db_path: str = DEFAULT_DB) -> sqlite3.Connection:
    """Open (or create) the memory DB; register the decay() function."""
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    _register_decay(con)
    con.executescript(_DDL)
    con.commit()
    return con


def _register_decay(con: sqlite3.Connection) -> None:
    """Register a scalar decay(iso_datetime) → float on the connection."""

    def decay(iso: str, half_life_days: float = 45.0) -> float:
        if not iso:
            return 0.0
        try:
            ts = datetime.datetime.fromisoformat(iso)
            now = datetime.datetime.now(tz=datetime.timezone.utc)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=datetime.timezone.utc)
            age_days = (now - ts).total_seconds() / 86400.0
            return 0.5 ** (age_days / half_life_days)
        except Exception:
            return 0.0

    con.create_function("decay", 2, decay)


# ---------------------------------------------------------------------------
# Write path
# ---------------------------------------------------------------------------

def remember_verdict(
    con: sqlite3.Connection,
    desk: str,
    ticker: str,
    verdict: str,
    body: str,
    meta: dict | None = None,
    run_id: str | None = None,
) -> int:
    """Insert one verdict row; returns its rowid."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    cur = con.execute(
        """INSERT INTO memory (kind, desk, ticker, verdict, body, meta, run_id, created_at)
           VALUES ('verdict', ?, ?, ?, ?, ?, ?, ?)""",
        (
            desk,
            (ticker or "").upper(),
            verdict,
            body,
            json.dumps(meta) if meta else None,
            run_id,
            now,
        ),
    )
    con.commit()
    return cur.lastrowid


def remember_analysis(
    con: sqlite3.Connection,
    desk: str,
    body: str,
    ticker: str | None = None,
    meta: dict | None = None,
    run_id: str | None = None,
) -> int:
    """Insert a free-form analysis row; returns rowid."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    cur = con.execute(
        """INSERT INTO memory (kind, desk, ticker, verdict, body, meta, run_id, created_at)
           VALUES ('analysis', ?, ?, NULL, ?, ?, ?, ?)""",
        (
            desk,
            (ticker or "").upper() if ticker else None,
            body,
            json.dumps(meta) if meta else None,
            run_id,
            now,
        ),
    )
    con.commit()
    return cur.lastrowid


def remember_preference(
    con: sqlite3.Connection,
    text: str,
    desk: str | None = None,
    scope: str | None = None,
) -> int:
    """Insert a durable preference row; returns rowid."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    cur = con.execute(
        "INSERT INTO preferences (desk, scope, text, created_at) VALUES (?, ?, ?, ?)",
        (desk, scope, text, now),
    )
    con.commit()
    return cur.lastrowid


# ---------------------------------------------------------------------------
# Read path
# ---------------------------------------------------------------------------

def _sanitize_match_query(query: str) -> str | None:
    """
    Extract safe FTS5 MATCH tokens from a user query.
    - Keep only [a-z0-9$] tokens (after lowercasing)
    - Wrap each in double quotes (exact-term FTS5 match)
    - Join with ' OR '
    Returns None if no safe tokens remain.
    """
    tokens = re.findall(r"[a-z0-9$]+", query.lower())
    if not tokens:
        return None
    return " OR ".join(f'"{t}"' for t in tokens)


def recall(
    con: sqlite3.Connection,
    query: str,
    desk: str | None = None,
    k: int = 8,
    half_life_days: float = 45.0,
) -> list[dict]:
    """
    BM25 × exponential recency decay recall.

    SQLite FTS5 bm25() returns negative numbers — we flip with the leading minus.
    Ticker column is weighted 10× body so symbol queries dominate.
    Returns up to k rows, highest score first.
    """
    match_expr = _sanitize_match_query(query)
    rows = []

    if match_expr:
        desk_filter = "AND m.desk = ?" if desk else ""
        params_fts: list = [match_expr, half_life_days]
        if desk:
            params_fts.append(desk)
        params_fts.append(k)

        sql = f"""
            SELECT
                m.id,
                m.kind,
                m.desk,
                m.ticker,
                m.verdict,
                m.body,
                m.meta,
                m.run_id,
                m.created_at,
                (-bm25(memory_fts, 10.0, 1.0)) * decay(m.created_at, ?) AS score
            FROM memory_fts
            JOIN memory m ON memory_fts.rowid = m.id
            WHERE memory_fts MATCH ?
            {desk_filter}
            ORDER BY score DESC
            LIMIT ?
        """
        # Note: MATCH must come before other WHERE predicates in FTS5
        # Reorder params: match_expr first in WHERE clause
        params_ordered: list = [half_life_days, match_expr]
        if desk:
            params_ordered.append(desk)
        params_ordered.append(k)

        try:
            cur = con.execute(sql, params_ordered)
            rows = [dict(r) for r in cur.fetchall()]
        except sqlite3.OperationalError:
            # FTS MATCH failed (e.g. no rows in fts table yet) — fall through to recency fallback
            rows = []

    if not rows:
        # Graceful degradation: return most recent rows for the desk
        desk_filter = "WHERE desk = ?" if desk else ""
        params_plain: list = [desk, k] if desk else [k]
        cur = con.execute(
            f"SELECT id, kind, desk, ticker, verdict, body, meta, run_id, created_at, 0.0 AS score "
            f"FROM memory {desk_filter} ORDER BY created_at DESC LIMIT ?",
            params_plain,
        )
        rows = [dict(r) for r in cur.fetchall()]

    # Parse meta JSON for callers
    for r in rows:
        if r.get("meta"):
            try:
                r["meta"] = json.loads(r["meta"])
            except Exception:
                pass

    return rows


def load_preferences(
    con: sqlite3.Connection,
    desk: str | None = None,
) -> list[dict]:
    """Return all durable preferences (not BM25-gated; always injected)."""
    if desk:
        cur = con.execute(
            "SELECT id, desk, scope, text, created_at FROM preferences WHERE desk = ? OR desk IS NULL ORDER BY created_at DESC",
            (desk,),
        )
    else:
        cur = con.execute(
            "SELECT id, desk, scope, text, created_at FROM preferences ORDER BY created_at DESC"
        )
    return [dict(r) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_context(prefs: list[dict], memories: list[dict]) -> str:
    """
    Format prior context for injection into a seat prompt.

    Example output:
        PRIOR VERDICTS (BM25-recalled, recency-weighted):
        [2026-06-24] COIN stocks HOLD — crypto bullish, above 200d | conviction 3/5
        [2026-06-17] COIN stocks WATCH — below trigger, wait for 200d reclaim

        DURABLE PREFERENCES:
        - crypto bullish (applies to: COIN, HOOD, CRCL)
        - RSP over VOO for new US equity
    """
    lines: list[str] = []

    if memories:
        lines.append("PRIOR VERDICTS (BM25-recalled, recency-weighted):")
        for m in memories:
            date = (m.get("created_at") or "")[:10]
            body = m.get("body") or ""
            # Compact: first 140 chars of body (body already includes ticker/desk/verdict)
            body_short = body[:140].rstrip()
            if len(body) > 140:
                body_short += "…"
            line = f"[{date}] {body_short}"
            meta = m.get("meta")
            if isinstance(meta, dict):
                conv = meta.get("conviction")
                if conv is not None:
                    line += f" | conviction {conv}/5"
            lines.append(line)

    if prefs:
        if lines:
            lines.append("")
        lines.append("DURABLE PREFERENCES:")
        for p in prefs:
            text = p.get("text", "")
            scope = p.get("scope")
            entry = f"- {text}"
            if scope:
                entry += f" (applies to: {scope})"
            lines.append(entry)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cmd_recall(args: argparse.Namespace) -> None:
    con = connect(args.db)
    memories = recall(con, args.q, desk=args.desk, k=args.k)
    print(json.dumps(memories, indent=2, default=str))


def _cmd_remember(args: argparse.Namespace) -> None:
    con = connect(args.db)
    meta = None
    if args.meta:
        try:
            meta = json.loads(args.meta)
        except json.JSONDecodeError as e:
            print(f"ERROR: --meta is not valid JSON: {e}", file=sys.stderr)
            sys.exit(1)
    rowid = remember_verdict(
        con,
        desk=args.desk,
        ticker=args.ticker,
        verdict=args.verdict,
        body=args.body,
        meta=meta,
        run_id=args.run_id,
    )
    print(json.dumps({"status": "ok", "id": rowid}))


def _cmd_pref_add(args: argparse.Namespace) -> None:
    con = connect(args.db)
    rowid = remember_preference(con, text=args.text, desk=args.desk, scope=args.scope)
    print(json.dumps({"status": "ok", "id": rowid}))


def _cmd_pref_list(args: argparse.Namespace) -> None:
    con = connect(args.db)
    prefs = load_preferences(con, desk=args.desk)
    print(json.dumps(prefs, indent=2, default=str))


def _cmd_stats(args: argparse.Namespace) -> None:
    con = connect(args.db)
    cur = con.execute(
        "SELECT desk, kind, COUNT(*) AS n FROM memory GROUP BY desk, kind ORDER BY desk, kind"
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur2 = con.execute(
        "SELECT desk, COUNT(*) AS n FROM preferences GROUP BY desk ORDER BY desk"
    )
    prefs_stats = [{"desk": r["desk"], "kind": "preference", "n": r["n"]} for r in cur2.fetchall()]
    print(json.dumps({"memory": rows, "preferences": prefs_stats}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="portfolio-memory — BM25 + recency-decay cross-run memory store"
    )
    parser.add_argument("--db", default=DEFAULT_DB, help="Path to SQLite DB")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # recall
    p_recall = sub.add_parser("recall", help="BM25 × decay ranked recall")
    p_recall.add_argument("--q", required=True, help="Query string")
    p_recall.add_argument("--desk", default=None, help="Filter by desk (stocks|crypto)")
    p_recall.add_argument("--k", type=int, default=8, help="Max results")
    p_recall.set_defaults(func=_cmd_recall)

    # remember
    p_rem = sub.add_parser("remember", help="Write one verdict to memory")
    p_rem.add_argument("--desk", required=True, help="stocks|crypto")
    p_rem.add_argument("--ticker", required=True, help="Ticker symbol")
    p_rem.add_argument("--verdict", required=True, help="BUY|WATCH|SKIP|HOLD|EXIT|…")
    p_rem.add_argument("--body", required=True, help="Free-form description (BM25 ranked)")
    p_rem.add_argument("--meta", default=None, help="JSON blob: entry, stop, conviction, …")
    p_rem.add_argument("--run-id", default=None, dest="run_id", help="Run identifier (e.g. 2026-06-24)")
    p_rem.set_defaults(func=_cmd_remember)

    # pref-add
    p_padd = sub.add_parser("pref-add", help="Add a durable preference")
    p_padd.add_argument("--text", required=True, help="Preference text")
    p_padd.add_argument("--desk", default=None, help="Desk scope (stocks|crypto|None=global)")
    p_padd.add_argument("--scope", default=None, help="Ticker scope e.g. 'COIN,HOOD,CRCL'")
    p_padd.set_defaults(func=_cmd_pref_add)

    # pref-list
    p_plist = sub.add_parser("pref-list", help="List durable preferences")
    p_plist.add_argument("--desk", default=None, help="Filter by desk")
    p_plist.set_defaults(func=_cmd_pref_list)

    # stats
    p_stats = sub.add_parser("stats", help="Row counts by desk/kind")
    p_stats.set_defaults(func=_cmd_stats)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
