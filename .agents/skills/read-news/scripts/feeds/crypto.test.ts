import { test, expect } from "bun:test";
import { parseRSS, stripHtml, toISO } from "../types";
import { CRYPTO_FEED_URLS } from "./crypto";
import { NEWS_FEEDS, fetchAllNews } from "./index";

// ── RSS fixture (inline, no network) ─────────────────────────────────────────

const RSS_FIXTURE = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel>
  <title>Test Crypto Feed</title>
  <item>
    <title><![CDATA[Bitcoin Hits New All-Time High]]></title>
    <link>https://decrypt.co/bitcoin-ath-2026</link>
    <description><![CDATA[Bitcoin surged past $100k as institutional demand accelerated.]]></description>
    <pubDate>Thu, 25 Jun 2026 10:00:00 GMT</pubDate>
    <category><![CDATA[Bitcoin]]></category>
    <category><![CDATA[Markets]]></category>
    <content:encoded><![CDATA[<p>Full article body with <b>HTML tags</b> and details.</p>]]></content:encoded>
  </item>
  <item>
    <title><![CDATA[ETH Upgrade Scheduled for Q3]]></title>
    <link>https://decrypt.co/eth-upgrade-q3</link>
    <description><![CDATA[Ethereum devs announce next major protocol upgrade timeline.]]></description>
    <pubDate>Wed, 24 Jun 2026 08:30:00 GMT</pubDate>
  </item>
  <item>
    <title><![CDATA[Vance&#x2019;s Crypto Bill Advances in Senate]]></title>
    <link>https://coindesk.com/vance-crypto-bill</link>
    <description><![CDATA[The bill&#x2014;backed by both parties&#x2014;cleared committee.]]></description>
    <pubDate>Tue, 23 Jun 2026 14:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Item with no description</title>
    <link>https://cointelegraph.com/no-desc</link>
    <pubDate>Mon, 22 Jun 2026 12:00:00 GMT</pubDate>
  </item>
</channel>
</rss>`;

// ── parseRSS + manual Article mapping (mirrors what crypto.ts does) ─────────

function rssToArticles(xml: string, source: string, hasContentEncoded: boolean) {
  const items = parseRSS(xml);
  return items
    .filter((i) => !!i.link)
    .map((i) => ({
      source,
      url: i.link,
      title: i.title,
      summary: stripHtml(i.description),
      body: hasContentEncoded && i.contentEncoded ? stripHtml(i.contentEncoded) : null,
      published_at: toISO(i.pubDate),
      lang: "en",
      tags: i.categories,
    }));
}

test("parseRSS extracts title and url from fixture", () => {
  const items = parseRSS(RSS_FIXTURE);
  expect(items.length).toBe(4);
  expect(items[0].title).toBe("Bitcoin Hits New All-Time High");
  expect(items[0].link).toBe("https://decrypt.co/bitcoin-ath-2026");
});

test("CDATA is unwrapped in title, description, and content:encoded", () => {
  const items = parseRSS(RSS_FIXTURE);
  expect(items[0].title).not.toContain("CDATA");
  expect(items[0].description).not.toContain("CDATA");
  expect(items[0].contentEncoded).not.toBeNull();
  expect(items[0].contentEncoded).not.toContain("CDATA");
});

test("stripHtml strips HTML tags from content:encoded body", () => {
  const items = parseRSS(RSS_FIXTURE);
  const body = items[0].contentEncoded ? stripHtml(items[0].contentEncoded) : null;
  expect(body).toBe("Full article body with HTML tags and details.");
});

test("hex entity decoded in title and summary", () => {
  const articles = rssToArticles(RSS_FIXTURE, "coindesk", false);
  const vance = articles.find((a) => a.url === "https://coindesk.com/vance-crypto-bill");
  expect(vance).toBeDefined();
  expect(vance!.title).toBe("Vance\u2019s Crypto Bill Advances in Senate");
  expect(vance!.summary).toBe("The bill\u2014backed by both parties\u2014cleared committee.");
});

test("missing description produces empty string, not null or undefined", () => {
  const articles = rssToArticles(RSS_FIXTURE, "cointelegraph", false);
  const noDesc = articles.find((a) => a.url === "https://cointelegraph.com/no-desc");
  expect(noDesc).toBeDefined();
  expect(typeof noDesc!.summary).toBe("string");
});

test("categories extracted correctly", () => {
  const items = parseRSS(RSS_FIXTURE);
  expect(items[0].categories).toEqual(["Bitcoin", "Markets"]);
  expect(items[1].categories).toEqual([]);
});

test("contentEncoded present for item that has it, null for item that doesn't", () => {
  const items = parseRSS(RSS_FIXTURE);
  expect(items[0].contentEncoded).not.toBeNull();
  expect(items[1].contentEncoded).toBeNull();
});

test("body is set when hasContentEncoded=true and content:encoded present", () => {
  const articles = rssToArticles(RSS_FIXTURE, "decrypt", true);
  expect(articles[0].body).toBe("Full article body with HTML tags and details.");
  expect(articles[1].body).toBeNull(); // no content:encoded on second item
});

test("body is null when hasContentEncoded=false even if content:encoded present", () => {
  const articles = rssToArticles(RSS_FIXTURE, "bloomberg", false);
  expect(articles[0].body).toBeNull();
});

// ── Registry tests (no network) ─────────────────────────────────────────────

test("NEWS_FEEDS contains all 9 feed names", () => {
  expect(NEWS_FEEDS).toContain("ft");
  expect(NEWS_FEEDS).toContain("wsj");
  expect(NEWS_FEEDS).toContain("decrypt");
  expect(NEWS_FEEDS).toContain("coindesk");
  expect(NEWS_FEEDS).toContain("cointelegraph");
  expect(NEWS_FEEDS).toContain("theblock");
  expect(NEWS_FEEDS).toContain("bitcoinmagazine");
  expect(NEWS_FEEDS).toContain("coinbase");
  expect(NEWS_FEEDS).toContain("bloomberg");
  expect(NEWS_FEEDS.length).toBe(9);
});

test("CRYPTO_FEED_URLS has correct URLs including coinbase Google News proxy", () => {
  expect(CRYPTO_FEED_URLS.coinbase).toContain("news.google.com");
  expect(CRYPTO_FEED_URLS.coinbase).toContain("coinbase.com");
  expect(CRYPTO_FEED_URLS.bloomberg).toBe("https://www.bloomberg.com/feed/podcast/etf-report.xml");
  expect(CRYPTO_FEED_URLS.decrypt).toBe("https://decrypt.co/feed");
  expect(CRYPTO_FEED_URLS.coindesk).toBe("https://www.coindesk.com/arc/outboundfeeds/rss/");
});

test("fetchAllNews({sources:[]}) returns empty records without throwing", async () => {
  const result = await fetchAllNews({ sources: [] });
  expect(result.records).toEqual([]);
  expect(result.unavailable).toEqual([]);
});

test("fetchAllNews signature returns {records, unavailable}", async () => {
  const result = await fetchAllNews({ sources: [] });
  expect(Array.isArray(result.records)).toBe(true);
  expect(Array.isArray(result.unavailable)).toBe(true);
});
