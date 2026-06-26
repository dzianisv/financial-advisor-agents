import { test, expect, describe, beforeAll, afterAll } from "bun:test";
import { mkdirSync, writeFileSync, rmSync, existsSync } from "node:fs";
import { Database } from "bun:sqlite";
import {
  normalizeText,
  canonicalUrl,
  contentHash,
  shingles,
  jaccard,
  simhash,
  connect,
  ingest,
  query,
  newSince,
  markSurfaced,
  parseDt,
  articleCount,
  recentArticles,
} from "./news_store";

const TEST_DIR = ".db/test-news-store";

beforeAll(() => {
  mkdirSync(TEST_DIR, { recursive: true });
});

afterAll(() => {
  if (existsSync(TEST_DIR)) rmSync(TEST_DIR, { recursive: true, force: true });
});

// ── normalizeText ────────────────────────────────────────────────────────────

describe("normalizeText", () => {
  test("basic lowercase and strip", () => {
    expect(normalizeText("Hello World!")).toBe("hello world");
    expect(normalizeText("")).toBe("");
  });

  test("NFKC normalization", () => {
    // NFKC converts full-width ASCII to ASCII
    expect(normalizeText("\uFF42\uFF49\uFF54\uFF43\uFF4F\uFF49\uFF4E")).toBe("bitcoin");
  });

  test("strips URLs", () => {
    expect(normalizeText("read more at https://example.com/path?q=1 today")).toBe(
      "read more at today",
    );
    expect(normalizeText("http://foo.bar/baz and http://x.com/y end")).toBe("and end");
  });

  test("strips punctuation but keeps $ and alphanumeric", () => {
    expect(normalizeText("Bitcoin $100k: record!")).toBe("bitcoin $100k record");
    expect(normalizeText("price: $50,000")).toBe("price $50 000");
  });

  test("collapses whitespace", () => {
    expect(normalizeText("  too   many   spaces  ")).toBe("too many spaces");
    expect(normalizeText("\t\nnewlines\r")).toBe("newlines");
  });
});

// ── canonicalUrl ─────────────────────────────────────────────────────────────

describe("canonicalUrl", () => {
  test("empty input", () => {
    expect(canonicalUrl("")).toBe("");
  });

  test("strips fragment", () => {
    expect(canonicalUrl("https://example.com/page#section")).toBe(
      "https://example.com/page",
    );
  });

  test("strips utm params", () => {
    expect(canonicalUrl("https://example.com/path?utm_source=twitter&utm_medium=social")).toBe(
      "https://example.com/path",
    );
  });

  test("strips ref, fbclid, gclid", () => {
    expect(canonicalUrl("https://example.com/path?ref=homepage")).toBe(
      "https://example.com/path",
    );
    expect(canonicalUrl("https://example.com/path?fbclid=abc123")).toBe(
      "https://example.com/path",
    );
    expect(canonicalUrl("https://example.com/path?gclid=xyz")).toBe(
      "https://example.com/path",
    );
  });

  test("preserves non-tracking params (Python behavior: leading ? becomes &)", () => {
    // Python re.sub removes '?utm_source=foo' leaving '&other=bar' → path&other=bar
    expect(canonicalUrl("https://example.com/path?utm_source=foo&other=bar")).toBe(
      "https://example.com/path&other=bar",
    );
  });

  test("strips trailing slashes and query chars", () => {
    expect(canonicalUrl("https://example.com/path/")).toBe("https://example.com/path");
    expect(canonicalUrl("https://example.com/path?")).toBe("https://example.com/path");
  });

  test("lowercases entire URL", () => {
    expect(canonicalUrl("HTTPS://EXAMPLE.COM/Path")).toBe("https://example.com/path");
  });

  test("strips fragment before query removal", () => {
    expect(canonicalUrl("https://example.com/path?ref=hp#top")).toBe(
      "https://example.com/path",
    );
  });
});

// ── contentHash ───────────────────────────────────────────────────────────────

describe("contentHash", () => {
  test("deterministic", () => {
    const h1 = contentHash("Bitcoin ETF approved", "SEC greenlights spot Bitcoin ETF.");
    const h2 = contentHash("Bitcoin ETF approved", "SEC greenlights spot Bitcoin ETF.");
    expect(h1).toBe(h2);
  });

  test("sha256 length", () => {
    expect(contentHash("a", "b")).toHaveLength(64);
  });

  test("different inputs produce different hashes", () => {
    expect(contentHash("Title A", "Summary A")).not.toBe(contentHash("Title B", "Summary B"));
  });

  test("normalizes before hashing", () => {
    // Case and punctuation differences → same hash after normalize
    expect(contentHash("Bitcoin!", "Hit $100k.")).toBe(contentHash("bitcoin", "hit $100k"));
  });
});

// ── shingles ─────────────────────────────────────────────────────────────────

describe("shingles", () => {
  test("returns words and bigrams", () => {
    const s = shingles("hello world foo");
    expect(s.has("hello")).toBe(true);
    expect(s.has("world")).toBe(true);
    expect(s.has("foo")).toBe(true);
    expect(s.has("hello world")).toBe(true);
    expect(s.has("world foo")).toBe(true);
    // no trigrams (JAC_NGRAM=2)
    expect(s.has("hello world foo")).toBe(false);
  });

  test("empty string returns set with empty string", () => {
    const s = shingles("");
    expect(s.has("")).toBe(true);
  });

  test("single word returns set with just that word", () => {
    const s = shingles("bitcoin");
    expect(s.has("bitcoin")).toBe(true);
    expect(s.size).toBe(1);
  });
});

// ── jaccard ──────────────────────────────────────────────────────────────────

describe("jaccard", () => {
  test("identical sets → 1.0", () => {
    const s = shingles("bitcoin price record high");
    expect(jaccard(s, s)).toBe(1.0);
  });

  test("disjoint sets → 0.0", () => {
    const a = shingles("bitcoin record high");
    const b = shingles("federal reserve rates");
    expect(jaccard(a, b)).toBe(0);
  });

  test("near-dup headlines score above threshold (0.15)", () => {
    const a = shingles(
      normalizeText(
        "Bitcoin hits new all-time high above $100k bitcoin surged to a new record above $100,000 as institutional buyers piled in",
      ),
    );
    const b = shingles(
      normalizeText(
        "Bitcoin sets new all-time high above $100,000 bitcoin surged past the $100,000 record as institutional buyers continued buying",
      ),
    );
    expect(jaccard(a, b)).toBeGreaterThan(0.15);
  });

  test("different-event headlines score below 0.15", () => {
    const a = shingles(normalizeText("bitcoin price hits new all time high"));
    const b = shingles(normalizeText("federal reserve holds benchmark interest rates unchanged"));
    expect(jaccard(a, b)).toBeLessThan(0.1);
  });
});

// ── simhash ───────────────────────────────────────────────────────────────────

describe("simhash", () => {
  test("returns decimal string", () => {
    const h = simhash("hello world");
    expect(typeof h).toBe("string");
    expect(/^\d+$/.test(h)).toBe(true);
  });

  test("deterministic", () => {
    expect(simhash("bitcoin price surges")).toBe(simhash("bitcoin price surges"));
  });

  test("empty string returns some value", () => {
    const h = simhash("");
    expect(typeof h).toBe("string");
  });
});

// ── parseDt ───────────────────────────────────────────────────────────────────

describe("parseDt", () => {
  test("ISO 8601 with Z", () => {
    const d = parseDt("2026-06-20T10:00:00Z");
    expect(d).not.toBeNull();
    expect(d!.getFullYear()).toBe(2026);
  });

  test("ISO 8601 with offset", () => {
    const d = parseDt("2026-06-20T10:00:00+00:00");
    expect(d).not.toBeNull();
  });

  test("date only", () => {
    const d = parseDt("2026-06-20");
    expect(d).not.toBeNull();
    expect(d!.getFullYear()).toBe(2026);
  });

  test("datetime with space separator (UTC)", () => {
    const d = parseDt("2026-06-20 10:00:00");
    expect(d).not.toBeNull();
    expect(d!.getUTCHours()).toBe(10);
  });

  test("RFC-822 format", () => {
    const d = parseDt("Thu, 25 Jun 2026 10:00:00 +0000");
    expect(d).not.toBeNull();
    expect(d!.getFullYear()).toBe(2026);
  });

  test("null/empty → null", () => {
    expect(parseDt(null)).toBeNull();
    expect(parseDt("")).toBeNull();
    expect(parseDt("garbage")).toBeNull();
  });
});

// ── exact dedup ───────────────────────────────────────────────────────────────

describe("exact dedup", () => {
  test("same URL deduplicates", () => {
    const db = connect(":memory:");
    const records = [
      {
        title: "Test Headline",
        summary: "Test summary text.",
        source: "reuters",
        url: "https://reuters.com/test-article",
      },
      {
        title: "Test Headline",
        summary: "Test summary text.",
        source: "reuters",
        url: "https://reuters.com/test-article",
      },
    ];
    const result = ingest(db, records);
    expect(result.new).toBe(1);
    expect(result.duplicate).toBe(1);
    expect(result.events_touched).toBe(0);
  });

  test("same content hash deduplicates even with different URL", () => {
    const db = connect(":memory:");
    const records = [
      {
        title: "Same Content",
        summary: "Same summary.",
        source: "site-a",
        url: "https://site-a.com/article",
      },
      {
        title: "Same Content",
        summary: "Same summary.",
        source: "site-b",
        url: "https://site-b.com/other-url",
      },
    ];
    const result = ingest(db, records);
    expect(result.new).toBe(1);
    expect(result.duplicate).toBe(1);
  });

  test("canonical URL strips tracking before dedup check", () => {
    const db = connect(":memory:");
    const records = [
      {
        title: "Article A",
        summary: "Summary A.",
        source: "s1",
        url: "https://example.com/a?utm_source=twitter",
      },
      {
        title: "Article A",
        summary: "Summary A.",
        source: "s1",
        url: "https://example.com/a?utm_source=facebook",
      },
    ];
    const result = ingest(db, records);
    expect(result.new).toBe(1);
    expect(result.duplicate).toBe(1);
  });

  test("skips records with no title", () => {
    const db = connect(":memory:");
    const result = ingest(db, [
      { title: "", summary: "No title article.", source: "s1", url: "https://x.com/1" },
      { title: "  ", summary: "Blank title.", source: "s1", url: "https://x.com/2" },
    ]);
    expect(result.new).toBe(0);
    expect(result.duplicate).toBe(0);
  });
});

// ── near-dup clustering ────────────────────────────────────────────────────────

describe("near-dup clustering", () => {
  test("three similar headlines from different outlets → one event", () => {
    const db = connect(":memory:");
    const records = [
      {
        title: "Bitcoin hits new all-time high above $100k",
        summary:
          "Bitcoin surged to a new record above $100,000 as institutional buyers piled in.",
        source: "reuters",
        url: "https://reuters.com/btc-ath-1",
        published_at: "2026-06-20T10:00:00Z",
      },
      {
        title: "Bitcoin sets new all-time high above $100,000",
        summary:
          "Bitcoin surged past the $100,000 record as institutional buyers continued buying.",
        source: "bloomberg",
        url: "https://bloomberg.com/btc-ath-1",
        published_at: "2026-06-20T10:30:00Z",
      },
      {
        title: "Bitcoin reaches new all-time high topping $100,000",
        summary: "Bitcoin hit a new record above $100k as institutional demand surged.",
        source: "coindesk",
        url: "https://coindesk.com/btc-ath-1",
        published_at: "2026-06-20T11:00:00Z",
      },
    ];
    const result = ingest(db, records);
    expect(result.new).toBe(3);
    expect(result.duplicate).toBe(0);
    expect(result.events_touched).toBe(2);

    const events = db.prepare("SELECT * FROM events").all() as { source_count: number }[];
    expect(events).toHaveLength(1);
    expect(events[0].source_count).toBe(3);
  });

  test("distinct topics do not cluster", () => {
    const db = connect(":memory:");
    const records = [
      {
        title: "Bitcoin reaches record high above $100k",
        summary: "Bitcoin surged past $100,000 to a new record.",
        source: "reuters",
        url: "https://reuters.com/btc",
      },
      {
        title: "Federal Reserve holds interest rates unchanged",
        summary: "Fed keeps benchmark rates at 5.25% citing inflation.",
        source: "wsj",
        url: "https://wsj.com/fed",
      },
    ];
    ingest(db, records);
    const events = db.prepare("SELECT * FROM events").all();
    expect(events).toHaveLength(2);
  });
});

// ── query ─────────────────────────────────────────────────────────────────────

describe("query", () => {
  test("returns events ranked by relevance", () => {
    const db = connect(":memory:");
    ingest(db, [
      {
        title: "Bitcoin price surges to new record high",
        summary: "BTC reached all-time high above $100k.",
        source: "reuters",
        url: "https://reuters.com/btc",
      },
      {
        title: "Federal Reserve holds rates steady",
        summary: "Fed keeps rates unchanged at 5.25%.",
        source: "wsj",
        url: "https://wsj.com/fed",
      },
      {
        title: "Ethereum ETF sees record inflows",
        summary: "ETH spot ETF attracted $500m in a day.",
        source: "coindesk",
        url: "https://coindesk.com/eth",
      },
    ]);
    const results = query(db, "bitcoin record high", { k: 3 });
    expect(results.length).toBeGreaterThan(0);
    expect(results[0].title).toContain("Bitcoin");
    expect(results[0].score).toBeGreaterThan(0);
  });

  test("days cutoff excludes old events", () => {
    const db = connect(":memory:");
    // Insert a record directly with old last_updated
    db.prepare(
      "INSERT INTO events(rep_simhash,rep_norm,title,first_seen,last_updated,sources,source_count)"
      + " VALUES (?,?,?,?,?,?,?)",
    ).run("0", "old event text", "Old Event Title", "2020-01-01T00:00:00Z", "2020-01-01T00:00:00Z", "[]", 0);
    ingest(db, [
      {
        title: "Recent Event Today",
        summary: "Something that just happened.",
        source: "s1",
        url: "https://s1.com/recent",
      },
    ]);
    const all = query(db, "event", { k: 10 });
    const recent = query(db, "event", { days: 30, k: 10 });
    expect(all.length).toBeGreaterThanOrEqual(2);
    const oldInRecent = recent.find((e) => e.title === "Old Event Title");
    expect(oldInRecent).toBeUndefined();
  });

  test("returns up to k results", () => {
    const db = connect(":memory:");
    for (let i = 0; i < 5; i++) {
      ingest(db, [
        {
          title: `News Article ${i} about crypto`,
          summary: `Summary of article ${i}.`,
          source: "s1",
          url: `https://s1.com/article-${i}`,
        },
      ]);
    }
    const results = query(db, "crypto", { k: 3 });
    expect(results.length).toBeLessThanOrEqual(3);
  });
});

// ── newSince ─────────────────────────────────────────────────────────────────

describe("newSince", () => {
  test("returns all unsurfaced events within window", () => {
    const db = connect(":memory:");
    ingest(db, [
      {
        title: "Federal Reserve raises interest rates",
        summary: "Fed hikes benchmark rates to combat inflation.",
        source: "s1",
        url: "https://s1.com/fed-rates",
      },
      {
        title: "Solana blockchain upgrade increases throughput",
        summary: "Solana network processes 50k transactions per second after upgrade.",
        source: "s1",
        url: "https://s1.com/solana-upgrade",
      },
    ]);
    const events = newSince(db, 3650);
    expect(events.length).toBe(2);
    // surfaced_to_panel_on must be null
    for (const e of events) expect(e.surfaced_to_panel_on).toBeNull();
  });

  test("excludes already-surfaced events", () => {
    const db = connect(":memory:");
    ingest(db, [
      {
        title: "Federal Reserve raises interest rates",
        summary: "Fed hikes benchmark rates to combat inflation.",
        source: "s1",
        url: "https://s1.com/fed-rates-x",
      },
      {
        title: "Solana blockchain upgrade increases throughput",
        summary: "Solana network processes 50k transactions per second after upgrade.",
        source: "s1",
        url: "https://s1.com/solana-upgrade-x",
      },
    ]);
    const all = newSince(db, 3650);
    expect(all.length).toBe(2);
    const firstId = all[0].event_cluster_id;
    markSurfaced(db, [firstId]);

    const remaining = newSince(db, 3650);
    expect(remaining.length).toBe(1);
    expect(remaining.every((e) => e.surfaced_to_panel_on === null)).toBe(true);
  });

  test("sorted by last_updated descending", () => {
    const db = connect(":memory:");
    // Insert events with explicit timestamps
    db.prepare(
      "INSERT INTO events(rep_simhash,rep_norm,title,first_seen,last_updated,sources,source_count)"
      + " VALUES (?,?,?,?,?,?,?)",
    ).run("1", "older event", "Older Event", "2026-06-01T00:00:00Z", "2026-06-01T00:00:00Z", "[]", 0);
    db.prepare(
      "INSERT INTO events(rep_simhash,rep_norm,title,first_seen,last_updated,sources,source_count)"
      + " VALUES (?,?,?,?,?,?,?)",
    ).run("2", "newer event", "Newer Event", "2026-06-20T00:00:00Z", "2026-06-20T00:00:00Z", "[]", 0);
    const events = newSince(db, 3650);
    expect(events[0].title).toBe("Newer Event");
    expect(events[1].title).toBe("Older Event");
  });
});

// ── markSurfaced ─────────────────────────────────────────────────────────────

describe("markSurfaced", () => {
  test("stamps surfaced_to_panel_on and returns count", () => {
    const db = connect(":memory:");
    ingest(db, [
      {
        title: "Federal Reserve raises interest rates to 5.5%",
        summary: "Fed hikes benchmark rates citing stubborn inflation figures.",
        source: "s",
        url: "https://s.com/fed-hike",
      },
      {
        title: "Solana blockchain upgrade increases throughput",
        summary: "Solana network processes 50k transactions per second after upgrade.",
        source: "s",
        url: "https://s.com/sol-upgrade",
      },
    ]);
    const events = newSince(db, 3650);
    const ids = events.map((e) => e.event_cluster_id);
    const result = markSurfaced(db, ids);
    expect(result.marked).toBe(2);
    expect(result.on).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(newSince(db, 3650)).toHaveLength(0);
  });

  test("custom date via --on", () => {
    const db = connect(":memory:");
    ingest(db, [{ title: "X", summary: "Y.", source: "s", url: "https://s.com/x" }]);
    const [ev] = newSince(db, 3650);
    const result = markSurfaced(db, [ev.event_cluster_id], "2026-01-15");
    expect(result.on).toBe("2026-01-15");
  });

  test("does not double-stamp already surfaced", () => {
    const db = connect(":memory:");
    ingest(db, [{ title: "Z", summary: "W.", source: "s", url: "https://s.com/z" }]);
    const [ev] = newSince(db, 3650);
    markSurfaced(db, [ev.event_cluster_id], "2026-01-01");
    const result = markSurfaced(db, [ev.event_cluster_id], "2026-06-01");
    expect(result.marked).toBe(0);
    const row = db.prepare("SELECT surfaced_to_panel_on FROM events WHERE event_cluster_id=?")
      .get(ev.event_cluster_id) as { surfaced_to_panel_on: string };
    expect(row.surfaced_to_panel_on).toBe("2026-01-01");
  });
});

// ── flat-store helpers ────────────────────────────────────────────────────────

describe("flat-store helpers", () => {
  test("articleCount returns total and by source", () => {
    const db = connect(":memory:");
    ingest(db, [
      { title: "A", summary: "S.", source: "reuters", url: "https://reuters.com/1" },
      { title: "B", summary: "S.", source: "reuters", url: "https://reuters.com/2" },
      { title: "C", summary: "S.", source: "bloomberg", url: "https://bloomberg.com/1" },
    ]);
    expect(articleCount(db)).toBe(3);
    expect(articleCount(db, "reuters")).toBe(2);
    expect(articleCount(db, "bloomberg")).toBe(1);
    expect(articleCount(db, "unknown")).toBe(0);
  });

  test("recentArticles filters by source and days", () => {
    const db = connect(":memory:");
    const recent = new Date().toISOString();
    const old = new Date(Date.now() - 30 * 86_400_000).toISOString();
    ingest(db, [
      { title: "Recent", summary: "S.", source: "coindesk", url: "https://cd.com/r", published_at: recent },
      { title: "Old", summary: "S.", source: "coindesk", url: "https://cd.com/o", published_at: old },
    ]);
    const r7 = recentArticles(db, "coindesk", 7);
    expect(r7.length).toBe(1);
    expect(r7[0].title).toBe("Recent");
    const r60 = recentArticles(db, "coindesk", 60);
    expect(r60.length).toBe(2);
  });
});

// ── GOLDEN PARITY TEST ────────────────────────────────────────────────────────

const PARITY_DIR = ".db/test-news-parity";

const FIXTURE = [
  // Event 1: Bitcoin ATH — 3 outlets, should cluster to 1 event
  {
    title: "Bitcoin hits new all-time high above $100k",
    summary:
      "Bitcoin surged to a new record above $100,000 as institutional buyers piled in.",
    source: "reuters",
    url: "https://reuters.com/crypto/bitcoin-ath?utm_source=twitter&utm_medium=social",
    published_at: "2026-06-20T10:00:00Z",
  },
  {
    title: "Bitcoin sets new all-time high above $100,000",
    summary:
      "Bitcoin surged past the $100,000 record as institutional buyers continued buying.",
    source: "bloomberg",
    url: "https://bloomberg.com/crypto/btc-all-time-high?ref=homepage#top",
    published_at: "2026-06-20T10:30:00Z",
  },
  {
    title: "Bitcoin reaches new all-time high topping $100,000",
    summary: "Bitcoin hit a new record above $100k as institutional demand surged.",
    source: "coindesk",
    url: "https://coindesk.com/markets/btc-ath?utm_campaign=morning",
    published_at: "2026-06-20T11:00:00Z",
  },
  // Exact duplicate of record 0
  {
    title: "Bitcoin hits new all-time high above $100k",
    summary:
      "Bitcoin surged to a new record above $100,000 as institutional buyers piled in.",
    source: "reuters",
    url: "https://reuters.com/crypto/bitcoin-ath?utm_source=twitter&utm_medium=social",
    published_at: "2026-06-20T10:00:00Z",
  },
  // Distinct events
  {
    title: "Federal Reserve holds interest rates steady at 5.25%",
    summary:
      "The Federal Reserve kept benchmark rates unchanged citing persistent inflation concerns.",
    source: "wsj",
    url: "https://wsj.com/economy/fed-rates-june-2026",
    published_at: "2026-06-19T18:00:00Z",
  },
  {
    title: "Apple announces new AI chip for iPhone 18",
    summary: "[UNAVAILABLE - paywall]",
    source: "ft",
    url: "https://ft.com/content/apple-ai-chip-iphone18",
    published_at: "2026-06-18T09:00:00Z",
  },
  {
    title: "Ethereum spot ETF sees record single-day inflows",
    summary:
      "Ethereum ETFs attracted $500 million in a single day, the highest since launch.",
    source: "theblock",
    url: "https://theblock.co/eth-etf-inflows-record",
    published_at: "2026-06-17T14:00:00Z",
  },
  {
    title: "Solana network upgrade boosts throughput to 50k TPS",
    summary:
      "The latest Solana protocol upgrade increases transaction throughput significantly.",
    source: "decrypt",
    url: "https://decrypt.co/solana-upgrade-throughput",
    published_at: "2026-06-16T11:00:00Z",
  },
  {
    title: "SEC approves new crypto custody rules for banks",
    summary:
      "The SEC released final rules allowing banks to custody digital assets for clients.",
    source: "coinbase",
    url: "https://coinbase.com/blog/sec-crypto-custody-rules",
    published_at: "2026-06-15T16:00:00Z",
  },
  {
    title: "Gold hits record high amid dollar weakness",
    summary:
      "Gold prices surged to $3,500 per ounce as the US dollar fell to multi-year lows.",
    source: "reuters",
    url: "https://reuters.com/markets/gold-record-high-3500",
    published_at: "2026-06-14T12:00:00Z",
  },
  {
    title: "MicroStrategy announces purchase of 5,000 BTC",
    summary:
      "MicroStrategy purchased 5,000 more Bitcoin bringing total holdings above 200,000 BTC.",
    source: "bloomberg",
    url: "https://bloomberg.com/news/microstrategy-5000-btc",
    published_at: "2026-06-13T08:00:00Z",
  },
  {
    title: "Nvidia reports record Q2 earnings beating estimates",
    summary:
      "Nvidia beat expectations with $35 billion quarterly revenue driven by AI chip demand.",
    source: "wsj",
    url: "https://wsj.com/tech/nvidia-q2-earnings-record",
    published_at: "2026-06-12T20:00:00Z",
  },
  {
    title: "DeFi total value locked surpasses $200 billion milestone",
    summary:
      "DeFi protocols collectively hold over $200 billion in assets for the first time.",
    source: "theblock",
    url: "https://theblock.co/defi-tvl-200b",
    published_at: "2026-06-11T13:00:00Z",
  },
  {
    title: "US inflation falls to 2.1% in May approaching Fed target",
    summary:
      "Consumer prices rose 2.1% year-over-year in May approaching the 2% inflation target.",
    source: "ft",
    url: "https://ft.com/content/us-inflation-may-2026",
    published_at: "2026-06-10T08:30:00Z",
  },
  {
    title: "Bitcoin miners face profitability squeeze after halving",
    summary:
      "BTC mining margins compressed significantly in the months following the April halving.",
    source: "coindesk",
    url: "https://coindesk.com/markets/btc-mining-halving-squeeze",
    published_at: "2026-06-09T10:00:00Z",
  },
  {
    title: "JPMorgan launches institutional crypto trading desk",
    summary:
      "JPMorgan Chase opened its cryptocurrency trading desk for institutional clients.",
    source: "bloomberg",
    url: "https://bloomberg.com/finance/jpmorgan-crypto-desk",
    published_at: "2026-06-08T09:00:00Z",
  },
];

describe("golden parity test (frozen snapshot vs retired news_store.py)", () => {
  // GOLDEN values captured from the reference Python store
  // (crypto-news-store/news_store.py @ origin/main) run on the FIXTURE below, BEFORE that
  // Python pipeline was retired in favor of this TS store. They are the SPEC: this TS store
  // must reproduce Python's exact dedup counts, new-since set, and query ranking. The snapshot
  // is frozen (not a live spawn) so the guard survives deleting the Python source.
  // To re-verify against a restored copy:
  //   git show <pre-migration-ref>:.agents/skills/crypto-news-store/news_store.py > /tmp/ns.py
  //   python3 /tmp/ns.py --db /tmp/p.db ingest --json <fixture> && ...new-since/query
  const tsDb = `${PARITY_DIR}/parity-ts.db`;
  const ingestDb = `${PARITY_DIR}/parity-ingest.db`;
  const fixtureFile = `${PARITY_DIR}/parity-fixture.json`;
  const tsScript = ".agents/skills/read-news/scripts/news_store.ts";

  const GOLDEN_INGEST = { new: 15, duplicate: 1, events_touched: 2 };
  const GOLDEN_NEW_SINCE_TITLES = [
    "Apple announces new AI chip for iPhone 18",
    "Bitcoin hits new all-time high above $100k",
    "Bitcoin miners face profitability squeeze after halving",
    "DeFi total value locked surpasses $200 billion milestone",
    "Ethereum spot ETF sees record single-day inflows",
    "Federal Reserve holds interest rates steady at 5.25%",
    "Gold hits record high amid dollar weakness",
    "JPMorgan launches institutional crypto trading desk",
    "MicroStrategy announces purchase of 5,000 BTC",
    "Nvidia reports record Q2 earnings beating estimates",
    "SEC approves new crypto custody rules for banks",
    "Solana network upgrade boosts throughput to 50k TPS",
    "US inflation falls to 2.1% in May approaching Fed target",
  ];
  const GOLDEN_QUERY_TOP5 = [
    "Bitcoin hits new all-time high above $100k",
    "JPMorgan launches institutional crypto trading desk",
    "MicroStrategy announces purchase of 5,000 BTC",
    "Bitcoin miners face profitability squeeze after halving",
    "DeFi total value locked surpasses $200 billion milestone",
  ];

  function runTs(args: string[]): { stdout: string; ok: boolean } {
    const r = Bun.spawnSync(["bun", tsScript, ...args]);
    return {
      stdout: new TextDecoder().decode(r.stdout),
      ok: r.exitCode === 0,
    };
  }

  beforeAll(() => {
    mkdirSync(PARITY_DIR, { recursive: true });
    writeFileSync(fixtureFile, JSON.stringify(FIXTURE, null, 2));
    // Populate the shared DB used by the new-since + query tests (order-independent).
    runTs(["--db", tsDb, "ingest", "--json", fixtureFile]);
  });

  afterAll(() => {
    if (existsSync(PARITY_DIR)) rmSync(PARITY_DIR, { recursive: true, force: true });
  });

  test("ingest counts match Python golden snapshot", () => {
    const tsResult = runTs(["--db", ingestDb, "ingest", "--json", fixtureFile]);
    expect(tsResult.ok).toBe(true);

    const tsIngest = JSON.parse(tsResult.stdout) as IngestResult;
    expect(tsIngest.new).toBe(GOLDEN_INGEST.new);
    expect(tsIngest.duplicate).toBe(GOLDEN_INGEST.duplicate);
    expect(tsIngest.events_touched).toBe(GOLDEN_INGEST.events_touched);
  });

  test("new-since returns same set of event titles as Python golden snapshot", () => {
    const tsResult = runTs(["--db", tsDb, "new-since", "--days", "3650"]);
    expect(tsResult.ok).toBe(true);

    const tsEvents = JSON.parse(tsResult.stdout) as { title: string }[];
    const tsTitles = new Set(tsEvents.map((e) => e.title));

    expect(tsTitles.size).toBe(GOLDEN_NEW_SINCE_TITLES.length);
    for (const t of GOLDEN_NEW_SINCE_TITLES) expect(tsTitles.has(t)).toBe(true);
  });

  test("query returns same top events as Python golden snapshot", () => {
    const q = "bitcoin all time high institutional";
    const tsResult = runTs(["--db", tsDb, "query", "--q", q, "--k", "5"]);
    expect(tsResult.ok).toBe(true);

    const tsQ = JSON.parse(tsResult.stdout) as { title: string }[];
    expect(tsQ.length).toBeGreaterThan(0);

    // Top result must match Python exactly.
    expect(tsQ[0].title).toBe(GOLDEN_QUERY_TOP5[0]);

    // Top-3 set must match Python's top-3 (BM25 sub-1e-7 score diffs may reorder within the set).
    const goldenTop3 = new Set(GOLDEN_QUERY_TOP5.slice(0, 3));
    const tsTop3 = new Set(tsQ.slice(0, 3).map((e) => e.title));
    expect(tsTop3.size).toBe(goldenTop3.size);
    for (const t of goldenTop3) expect(tsTop3.has(t)).toBe(true);
  });
});

// Type alias for use in parity test
type IngestResult = { new: number; duplicate: number; events_touched: number };
