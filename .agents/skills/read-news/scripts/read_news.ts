#!/usr/bin/env bun
/**
 * read_news.ts — unified news-fetch orchestrator (TypeScript port of news_fetch.py).
 *
 * Flow: fetchAllNews → ingest (in-process) → query or newSince → print JSON.
 * Output keys match news_fetch.py: {fetched, feeds_ok, unavailable, events}.
 */

import { connect, ingest, query, newSince } from "./news_store";
import { fetchAllNews, NEWS_FEEDS } from "./feeds/index";
import type { Article } from "./types";

// ── Arg parsing ──────────────────────────────────────────────────────────────

interface ReadNewsOpts {
  db?: string;
  days?: number;
  k?: number;
  query?: string;
  sources?: string[];
}

interface ReadNewsResult {
  fetched: number;
  feeds_ok: number;
  unavailable: string[];
  events: unknown[];
  note?: string;
}

function parseCliArgs(): ReadNewsOpts {
  const args = process.argv.slice(2);
  const opts: ReadNewsOpts = {};

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--db" && args[i + 1]) {
      opts.db = args[++i];
    } else if (args[i] === "--days" && args[i + 1]) {
      opts.days = parseInt(args[++i], 10);
    } else if (args[i] === "--k" && args[i + 1]) {
      opts.k = parseInt(args[++i], 10);
    } else if (args[i] === "--query" && args[i + 1]) {
      opts.query = args[++i];
    } else if (args[i] === "--source" && args[i + 1]) {
      opts.sources = args[++i].split(",").map((s) => s.trim()).filter(Boolean);
    }
  }

  return opts;
}

// ── Core logic (exported for tests) ─────────────────────────────────────────

export async function runReadNews(opts: ReadNewsOpts = {}): Promise<ReadNewsResult> {
  const dbPath = opts.db ?? process.env.CRYPTO_NEWS_DB ?? ".db/news.db";
  const days = opts.days ?? 3;
  const k = opts.k ?? 15;
  const queryStr = opts.query ?? "";
  const sources = opts.sources; // undefined → fetch all NEWS_FEEDS

  // 1. Fetch all requested feeds
  const { records, unavailable } = await fetchAllNews({ sources });

  // 2. All feeds failed
  if (records.length === 0) {
    return {
      fetched: 0,
      feeds_ok: 0,
      unavailable,
      events: [],
      note: "all feeds [UNAVAILABLE]",
    };
  }

  // 3. Open store and ingest (idempotent)
  const db = connect(dbPath);
  ingest(db, records as unknown as Record<string, unknown>[]);

  // 4. Query or new-since
  let events: unknown[];
  if (queryStr) {
    events = query(db, queryStr, { days, k });
  } else {
    events = newSince(db, days);
  }

  db.close();

  // 5. feeds_ok = requested feed count - number of unavailable entries
  const requestedCount = sources ? sources.length : NEWS_FEEDS.length;
  const feedsOk = requestedCount - unavailable.length;

  return {
    fetched: records.length,
    feeds_ok: feedsOk,
    unavailable,
    events,
  };
}

// ── CLI entry point ──────────────────────────────────────────────────────────

if (import.meta.main) {
  const opts = parseCliArgs();
  const result = await runReadNews(opts);
  console.log(JSON.stringify(result, null, 1));
}
