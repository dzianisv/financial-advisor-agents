#!/usr/bin/env python3
"""
fetch_article.py — cache-first article fetcher with FTS5 search.

Usage:
  python fetch_article.py --url "https://..."              # fetch (cache-first)
  python fetch_article.py --url "https://..." --force-refresh
  python fetch_article.py --search "CRDO revenue" [--source wsj] [--limit 5]
  python fetch_article.py --ingest --url "..." --title "..." --body "..." --source "ft-manual"
  python fetch_article.py --stats
  python fetch_article.py --prune-days N
"""

import argparse
import hashlib
import html.parser
import json
import os
import re
import sqlite3
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# DB setup
# ---------------------------------------------------------------------------

DB_PATH = Path("~/.agents/cache/articles.db").expanduser()

DDL = """
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    url_hash TEXT NOT NULL,
    fetched_date TEXT NOT NULL,
    status_code INTEGER,
    title TEXT,
    body TEXT,
    source TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_url_date ON articles(url_hash, fetched_date);
CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
    title, body, url, source,
    content='articles', content_rowid='id',
    tokenize='porter unicode61'
);
CREATE TRIGGER IF NOT EXISTS articles_ai AFTER INSERT ON articles BEGIN
    INSERT INTO articles_fts(rowid, title, body, url, source)
    VALUES (new.id, new.title, new.body, new.url, new.source);
END;
CREATE TRIGGER IF NOT EXISTS articles_ad AFTER DELETE ON articles BEGIN
    INSERT INTO articles_fts(articles_fts, rowid, title, body, url, source)
    VALUES('delete', old.id, old.title, old.body, old.url, old.source);
END;
"""


def get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    for stmt in DDL.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass  # table/index already exists
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def today() -> str:
    return date.today().isoformat()


def infer_source(url: str) -> str:
    """Infer source label from URL domain."""
    # Strip scheme
    domain_part = re.sub(r"^https?://", "", url)
    domain = domain_part.split("/")[0].lower()

    # For Wayback Machine URLs, try to extract original source
    if "web.archive.org" in domain:
        # pattern: /web/<ts>/<original_url>
        m = re.search(r"web\.archive\.org/web/\d+/https?://([^/]+)", url)
        if m:
            orig_domain = m.group(1).lower().lstrip("www.")
            orig_source = _map_domain(orig_domain)
            if orig_source != orig_domain:
                return orig_source
        return "wayback"

    bare = domain.lstrip("www.")
    return _map_domain(bare)


def _map_domain(bare: str) -> str:
    mapping = {
        "wsj.com": "wsj",
        "ft.com": "ft",
        "sec.gov": "sec.gov",
        "finance.yahoo.com": "yahoo-finance",
        "yahoo.com": "yahoo-finance",
        "bloomberg.com": "bloomberg",
        "coindesk.com": "coindesk",
        "cointelegraph.com": "cointelegraph",
        "theblock.co": "theblock",
        "decrypt.co": "decrypt",
    }
    for k, v in mapping.items():
        if bare == k or bare.endswith("." + k):
            return v
    return bare


class _TitleExtractor(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self._in_title = False
        self._in_skip = False
        self.title = ""
        self._chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self._in_title = True
        if tag in ("script", "style", "noscript", "nav", "footer", "header"):
            self._in_skip = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag in ("script", "style", "noscript", "nav", "footer", "header"):
            self._in_skip = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._in_skip:
            text = data.strip()
            if text:
                self._chunks.append(text)

    def body_text(self) -> str:
        return "\n".join(self._chunks)


def parse_html(raw: str) -> tuple[str, str]:
    """Return (title, body_text) from raw HTML."""
    parser = _TitleExtractor()
    try:
        parser.feed(raw)
    except Exception:
        pass
    title = parser.title.strip()
    body = parser.body_text().strip()
    # Collapse excessive blank lines
    body = re.sub(r"\n{3,}", "\n\n", body)
    return title, body


def is_paywalled(text: str) -> bool:
    markers = [
        "subscribe to read",
        "subscribe to continue",
        "subscription required",
        "sign in to read",
        "to continue reading",
    ]
    lower = text.lower()
    return any(m in lower for m in markers)


USER_AGENT = (
    "Mozilla/5.0 (compatible; BacktestAgent/1.0; +https://github.com/backtest)"
)


def http_get(url: str, timeout: int = 20) -> tuple[int, str]:
    """Fetch URL, return (status_code, text). Raises on network error."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = "utf-8"
        ct = resp.headers.get_content_charset()
        if ct:
            charset = ct
        raw_bytes = resp.read()
        try:
            text = raw_bytes.decode(charset, errors="replace")
        except (LookupError, UnicodeDecodeError):
            text = raw_bytes.decode("utf-8", errors="replace")
        return resp.status, text


# ---------------------------------------------------------------------------
# Fetch logic
# ---------------------------------------------------------------------------

def fetch_url(url: str, force: bool = False) -> dict:
    """Fetch URL with caching. Returns result dict."""
    conn = get_db()
    h = url_hash(url)
    td = today()

    if not force:
        row = conn.execute(
            "SELECT * FROM articles WHERE url_hash=? AND fetched_date=?",
            (h, td),
        ).fetchone()
        if row:
            conn.close()
            return {
                "url": row["url"],
                "title": row["title"] or "",
                "body": row["body"] or "",
                "source": row["source"] or "",
                "fetched_date": row["fetched_date"],
                "status_code": row["status_code"],
                "cache_hit": True,
            }

    source = infer_source(url)

    # Determine fetch strategy
    title = ""
    body = ""
    status_code = None

    try:
        result = None
        if source == "wsj" or "wsj.com" in url:
            result = _fetch_wsj(url)
        elif (
            "web.archive.org" in url
            or "sec.gov" in url
            or "finance.yahoo.com" in url
            or "yahoo.com" in url
        ):
            try:
                status_code, raw = http_get(url)
                title, body = parse_html(raw)
            except urllib.error.HTTPError as e:
                status_code = e.code
                body = f"[UNAVAILABLE - HTTP {e.code}]"
                title = ""
        else:
            try:
                status_code, raw = http_get(url)
                title, body = parse_html(raw)
                if status_code in (401, 403) or is_paywalled(body):
                    body = "[UNAVAILABLE - paywall]"
            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    status_code = e.code
                    body = "[UNAVAILABLE - paywall]"
                else:
                    raise

        if source == "wsj" or "wsj.com" in url:
            title = result.get("title", "")
            body = result.get("body", "")
            status_code = result.get("status_code")

    except Exception as exc:
        conn.close()
        return {"url": url, "error": str(exc), "body": "[UNAVAILABLE]", "cache_hit": False}

    # Store
    try:
        conn.execute(
            """INSERT OR REPLACE INTO articles
               (url, url_hash, fetched_date, status_code, title, body, source)
               VALUES (?,?,?,?,?,?,?)""",
            (url, h, td, status_code, title, body, source),
        )
        conn.commit()
    except Exception:
        pass
    conn.close()

    return {
        "url": url,
        "title": title,
        "body": body,
        "source": source,
        "fetched_date": td,
        "status_code": status_code,
        "cache_hit": False,
    }


def _fetch_wsj(url: str) -> dict:
    """WSJ fetch: try Wayback first, else mark unavailable."""
    wayback_url = f"https://web.archive.org/web/2/{url}"
    try:
        status_code, raw = http_get(wayback_url, timeout=30)
        title, body = parse_html(raw)
        if not body or is_paywalled(body):
            body = "[UNAVAILABLE - paywall]"
        return {"title": title, "body": body, "status_code": status_code}
    except Exception as exc:
        return {
            "title": "",
            "body": "[UNAVAILABLE - paywall]",
            "status_code": None,
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def search_articles(query: str, source_filter: str | None = None, limit: int = 5) -> list[dict]:
    conn = get_db()
    if source_filter:
        rows = conn.execute(
            """SELECT a.url, a.title, a.body, a.source, a.fetched_date, a.status_code
               FROM articles_fts f
               JOIN articles a ON a.id = f.rowid
               WHERE articles_fts MATCH ? AND a.source = ?
               ORDER BY rank
               LIMIT ?""",
            (query, source_filter, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT a.url, a.title, a.body, a.source, a.fetched_date, a.status_code
               FROM articles_fts f
               JOIN articles a ON a.id = f.rowid
               WHERE articles_fts MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (query, limit),
        ).fetchall()
    conn.close()
    results = []
    for r in rows:
        results.append({
            "url": r["url"],
            "title": r["title"] or "",
            "body": (r["body"] or "")[:500],  # truncate for readability
            "source": r["source"] or "",
            "fetched_date": r["fetched_date"],
            "status_code": r["status_code"],
        })
    return results


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------

def ingest(url: str, title: str, body: str, source: str) -> dict:
    conn = get_db()
    h = url_hash(url)
    td = today()
    inferred = source or infer_source(url)
    try:
        conn.execute(
            """INSERT OR REPLACE INTO articles
               (url, url_hash, fetched_date, status_code, title, body, source)
               VALUES (?,?,?,?,?,?,?)""",
            (url, h, td, 200, title, body, inferred),
        )
        conn.commit()
    finally:
        conn.close()
    return {
        "url": url,
        "title": title,
        "body": body,
        "source": inferred,
        "fetched_date": td,
        "cache_hit": False,
        "ingested": True,
    }


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def stats() -> dict:
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    by_source = conn.execute(
        "SELECT source, COUNT(*) as n FROM articles GROUP BY source ORDER BY n DESC"
    ).fetchall()
    stale_cutoff = (date.today() - timedelta(days=7)).isoformat()
    stale = conn.execute(
        "SELECT COUNT(*) FROM articles WHERE fetched_date < ?", (stale_cutoff,)
    ).fetchone()[0]
    conn.close()
    return {
        "total": total,
        "stale_7d": stale,
        "db_path": str(DB_PATH),
        "by_source": {r["source"] or "unknown": r["n"] for r in by_source},
    }


# ---------------------------------------------------------------------------
# Prune
# ---------------------------------------------------------------------------

def prune(days: int) -> dict:
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    conn = get_db()
    cur = conn.execute("DELETE FROM articles WHERE fetched_date < ?", (cutoff,))
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return {"pruned": deleted, "cutoff": cutoff}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Cache-first article fetcher")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="URL to fetch")
    group.add_argument("--by-url", metavar="URL", help="Exact URL cache lookup (no fetch)")
    group.add_argument("--search", metavar="QUERY", help="BM25 full-text search")
    group.add_argument("--stats", action="store_true", help="Show DB stats")
    group.add_argument("--prune-days", type=int, metavar="N", help="Prune entries older than N days")

    parser.add_argument("--force-refresh", action="store_true", help="Bypass cache")
    parser.add_argument("--ingest", action="store_true", help="Ingest pre-fetched content (use with --url)")
    parser.add_argument("--title", default="", help="Title for --ingest")
    parser.add_argument("--body", default="", help="Body for --ingest")
    parser.add_argument("--source", default="", help="Source label (for --ingest or --search filter)")
    parser.add_argument("--limit", type=int, default=5, help="Max results for --search")

    args = parser.parse_args()

    if args.stats:
        print(json.dumps(stats(), indent=2))
        return

    if args.prune_days is not None:
        print(json.dumps(prune(args.prune_days), indent=2))
        return

    if args.search:
        results = search_articles(args.search, source_filter=args.source or None, limit=args.limit)
        print(json.dumps(results, indent=2))
        return

    if args.by_url:
        conn = get_db()
        today = date.today().isoformat()
        row = conn.execute(
            "SELECT url, title, body, source, fetched_date FROM articles WHERE url = ? ORDER BY fetched_date DESC LIMIT 1",
            (args.by_url,),
        ).fetchone()
        conn.close()
        if row:
            print(json.dumps({"url": row[0], "title": row[1], "body": row[2], "source": row[3], "fetched_date": row[4], "cache_hit": True}, indent=2))
        else:
            print(json.dumps({}))
        return

    # --url path
    if args.ingest:
        result = ingest(args.url, args.title, args.body, args.source)
    else:
        result = fetch_url(args.url, force=args.force_refresh)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
