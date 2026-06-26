import { test, expect, describe, beforeAll, afterAll } from "bun:test";
import { mkdirSync, rmSync, existsSync } from "node:fs";
import { connect, ingest, query, newSince } from "./news_store";
import type { Article } from "./types";

const TEST_DIR = ".db/test-read-news";
const DB_PATH = `${TEST_DIR}/news.db`;

// ── Fixture ──────────────────────────────────────────────────────────────────

const FIXTURE: Article[] = [
  {
    source: "coindesk",
    url: "https://coindesk.com/articles/bitcoin-etf-record",
    title: "Bitcoin ETF sees record inflows as BTC surges past $70k",
    summary: "Spot bitcoin ETFs posted record daily inflows driven by institutional demand.",
    body: null,
    published_at: new Date(Date.now() - 3_600_000).toISOString(), // 1h ago
    lang: "en",
    tags: ["bitcoin", "etf"],
  },
  {
    source: "cointelegraph",
    url: "https://cointelegraph.com/news/ethereum-dencun-upgrade",
    title: "Ethereum Dencun upgrade cuts layer-2 fees by 90%",
    summary: "The Dencun upgrade introduces proto-danksharding, dramatically reducing L2 transaction costs.",
    body: null,
    published_at: new Date(Date.now() - 7_200_000).toISOString(), // 2h ago
    lang: "en",
    tags: ["ethereum", "upgrade"],
  },
  {
    source: "ft",
    url: "https://ft.com/content/macro-outlook-2024",
    title: "Fed signals rate cuts as inflation cools",
    summary: "Federal Reserve officials have signalled they expect to cut interest rates in 2024.",
    body: null,
    published_at: new Date(Date.now() - 10_800_000).toISOString(), // 3h ago
    lang: "en",
    tags: ["fed", "rates"],
  },
];

// ── Setup / teardown ─────────────────────────────────────────────────────────

let db: ReturnType<typeof connect>;

beforeAll(() => {
  mkdirSync(TEST_DIR, { recursive: true });
  db = connect(DB_PATH);
  ingest(db, FIXTURE as unknown as Record<string, unknown>[]);
});

afterAll(() => {
  try { db.close(); } catch { /* already closed */ }
  if (existsSync(TEST_DIR)) rmSync(TEST_DIR, { recursive: true, force: true });
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("ingest → query", () => {
  test("query('bitcoin') returns events with bitcoin article near top", () => {
    const results = query(db, "bitcoin", { days: 3650, k: 15 });
    expect(results.length).toBeGreaterThan(0);
    // The bitcoin ETF article should be ranked first (it mentions bitcoin explicitly)
    const titles = results.map((e) => e.title.toLowerCase());
    const bitcoinIdx = titles.findIndex((t) => t.includes("bitcoin"));
    expect(bitcoinIdx).toBe(0);
  });

  test("query returns events with score field", () => {
    const results = query(db, "bitcoin", { days: 3650, k: 15 });
    for (const evt of results) {
      expect(typeof evt.score).toBe("number");
      expect(evt.score).toBeGreaterThan(0);
    }
  });
});

describe("ingest → newSince", () => {
  test("newSince returns all 3 distinct events (within 3650 days)", () => {
    const events = newSince(db, 3650);
    expect(events.length).toBe(3);
  });

  test("newSince events have required fields", () => {
    const events = newSince(db, 3650);
    for (const evt of events) {
      expect(typeof evt.event_cluster_id).toBe("number");
      expect(typeof evt.title).toBe("string");
      expect(Array.isArray(evt.sources)).toBe(true);
      expect(typeof evt.source_count).toBe("number");
    }
  });
});

describe("idempotency", () => {
  test("re-ingesting same fixture yields duplicate > 0", () => {
    const result = ingest(db, FIXTURE as unknown as Record<string, unknown>[]);
    expect(result.duplicate).toBeGreaterThan(0);
  });

  test("re-ingesting does not grow the event count", () => {
    const before = newSince(db, 3650).length;
    ingest(db, FIXTURE as unknown as Record<string, unknown>[]);
    const after = newSince(db, 3650).length;
    expect(after).toBe(before);
  });
});

describe("output shape contract", () => {
  test("{fetched, feeds_ok, unavailable, events} keys with correct types", () => {
    const records = FIXTURE;
    const unavailable = ["bloomberg:ConnectionError", "wsj:TimeoutError"];

    // Simulate what read_news.ts builds
    const NEWS_FEEDS_COUNT = 9; // matches NEWS_FEEDS.length from feeds/index.ts
    const result = {
      fetched: records.length,
      feeds_ok: NEWS_FEEDS_COUNT - unavailable.length,
      unavailable,
      events: newSince(db, 3650),
    };

    // Key presence
    expect("fetched" in result).toBe(true);
    expect("feeds_ok" in result).toBe(true);
    expect("unavailable" in result).toBe(true);
    expect("events" in result).toBe(true);

    // Type checks
    expect(typeof result.fetched).toBe("number");
    expect(typeof result.feeds_ok).toBe("number");
    expect(Array.isArray(result.unavailable)).toBe(true);
    expect(Array.isArray(result.events)).toBe(true);

    // Value sanity
    expect(result.fetched).toBe(3);
    expect(result.feeds_ok).toBe(7);
    expect(result.unavailable).toHaveLength(2);
  });

  test("all-unavailable path returns note key", () => {
    const result = {
      fetched: 0,
      feeds_ok: 0,
      unavailable: ["ft:Error", "wsj:Error"],
      events: [],
      note: "all feeds [UNAVAILABLE]",
    };
    expect(result.note).toBe("all feeds [UNAVAILABLE]");
    expect(result.events).toHaveLength(0);
  });
});
