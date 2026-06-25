import { test, expect } from "bun:test";
import { parseWsjRss, normalizeUrl, stripHtml, cleanTitle, filterAndRank } from "./fetch_wsj.ts";

// Fixture mirrors real Dow Jones public RSS: CDATA <title>/<description>, ?mod=rss_* tracking on
// <link>, and a non-URL <guid> (WSJ uses opaque ids like "WP-WSJ-0003688412" — must NOT be used as url).
const WSJ_RSS = `<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel>
  <title>WSJ.com: Markets</title>
  <item>
    <title><![CDATA[JPMorgan Shakes Up Dimon Succession Race - The Wall Street Journal]]></title>
    <link>https://www.wsj.com/finance/banking/jpmorgan-co-presidents-aafb5c27?mod=rss_markets_main</link>
    <description><![CDATA[JPMorgan named two co-presidents, laying groundwork to find a successor for Jamie Dimon]]></description>
    <category><![CDATA[Finance]]></category>
    <guid isPermaLink="false">WP-WSJ-0003688412</guid>
    <pubDate>Thu, 25 Jun 2026 16:28:00 GMT</pubDate>
  </item>
  <item>
    <title><![CDATA[Stocks Climb as Micron Disappoints &amp; Oil Slides]]></title>
    <link>https://www.wsj.com/livecoverage/stock-market-today-06-25-2026?mod=rss_markets_main</link>
    <description><![CDATA[]]></description>
    <guid isPermaLink="false">lc-wsj-stock-market-today-06-25-2026</guid>
    <pubDate>Thu, 25 Jun 2026 07:43:33 GMT</pubDate>
  </item>
</channel></rss>`;

test("parseWsjRss extracts headline + real wsj.com URL + teaser, unwrapping CDATA", () => {
  const a = parseWsjRss(WSJ_RSS);
  expect(a.length).toBe(2);

  expect(a[0].source).toBe("wsj");
  expect(a[0].title).toBe("JPMorgan Shakes Up Dimon Succession Race"); // publisher suffix stripped
  expect(a[0].url).toBe("https://www.wsj.com/finance/banking/jpmorgan-co-presidents-aafb5c27"); // ?mod= stripped
  expect(a[0].summary).toBe("JPMorgan named two co-presidents, laying groundwork to find a successor for Jamie Dimon");
  expect(a[0].tags).toEqual(["Finance"]);
  expect(a[0].published_at).toBe("2026-06-25T16:28:00.000Z");
});

test("non-URL <guid> is never used as the url (only <link>)", () => {
  const a = parseWsjRss(WSJ_RSS);
  const blob = JSON.stringify(a);
  expect(blob).not.toContain("WP-WSJ-0003688412");
  expect(blob).not.toContain("lc-wsj-");
  expect(a.every((x) => x.url.startsWith("https://www.wsj.com/"))).toBe(true);
});

test("no leftover CDATA markers or HTML entities in output", () => {
  const a = parseWsjRss(WSJ_RSS);
  const blob = JSON.stringify(a);
  expect(blob).not.toContain("CDATA");
  expect(blob).not.toContain("&amp;");
  expect(a[1].title).toBe("Stocks Climb as Micron Disappoints & Oil Slides"); // entity decoded
});

test("absent teaser -> [UNAVAILABLE - paywall], never fabricated", () => {
  const a = parseWsjRss(WSJ_RSS);
  expect(a[1].summary).toBe("[UNAVAILABLE - paywall]");
});

test("parseWsjRss returns [] on garbage XML (no throw)", () => {
  expect(parseWsjRss("not xml at all")).toEqual([]);
  expect(parseWsjRss("")).toEqual([]);
});

test("cleanTitle strips WSJ publisher suffixes", () => {
  expect(cleanTitle("Foo Bar - The Wall Street Journal")).toBe("Foo Bar");
  expect(cleanTitle("Foo Bar - WSJ")).toBe("Foo Bar");
  expect(cleanTitle("Foo Bar")).toBe("Foo Bar");
});

test("normalizeUrl strips ?mod= and other trackers", () => {
  expect(normalizeUrl("https://www.wsj.com/articles/abc?mod=rss_markets_main&utm_source=x")).toBe(
    "https://www.wsj.com/articles/abc",
  );
  expect(normalizeUrl("https://www.wsj.com/articles/abc")).toBe("https://www.wsj.com/articles/abc");
});

test("stripHtml unwraps CDATA and strips tags", () => {
  expect(stripHtml("<![CDATA[<b>Hi</b> there]]>")).toBe("Hi there");
});

const NOW = Date.parse("2026-06-25T12:00:00Z");
const sample: ReturnType<typeof parseWsjRss> = [
  { source: "wsj", url: "https://www.wsj.com/a", title: "Fed holds rates", published_at: "2026-06-25T06:00:00.000Z", summary: "FOMC keeps policy steady", tags: [] },
  { source: "wsj", url: "https://www.wsj.com/a", title: "Fed holds rates", published_at: "2026-06-25T06:00:00.000Z", summary: "dupe", tags: [] }, // duplicate url
  { source: "wsj", url: "https://www.wsj.com/b", title: "Oil slides", published_at: "2026-06-24T06:00:00.000Z", summary: "crude lower", tags: [] },
  { source: "wsj", url: "https://www.wsj.com/c", title: "Old news", published_at: "2026-06-01T06:00:00.000Z", summary: "stale", tags: [] }, // outside 7d
];

test("filterAndRank dedups by url, drops stale, sorts newest-first", () => {
  const r = filterAndRank(sample, { days: 7, nowMs: NOW });
  expect(r.map((x) => x.url)).toEqual(["https://www.wsj.com/a", "https://www.wsj.com/b"]);
});

test("filterAndRank query is AND-of-words over title+summary", () => {
  const r = filterAndRank(sample, { days: 7, nowMs: NOW, query: "fed fomc" });
  expect(r.length).toBe(1);
  expect(r[0].url).toBe("https://www.wsj.com/a");
  expect(filterAndRank(sample, { days: 7, nowMs: NOW, query: "nonexistent" }).length).toBe(0);
});

test("filterAndRank respects limit", () => {
  expect(filterAndRank(sample, { days: 7, nowMs: NOW, limit: 1 }).length).toBe(1);
});
