import { test, expect } from "bun:test";
import { parseFtRss, normalizeUrl, stripHtml, filterAndRank } from "./ft.ts";

// Fixture mirrors real FT section RSS: CDATA-wrapped <title>/<description>, RFC-822 <pubDate>.
const FT_RSS = `<?xml version="1.0"?>
<rss version="2.0"><channel>
  <title>FT Markets</title>
  <item>
    <title><![CDATA[EasyJet in talks with Castlelake after rejecting £4.9bn offer]]></title>
    <link>https://www.ft.com/content/155406ff-e4fc-470a-abaa-d9526c5b3e59?utm_source=rss&amp;ns=1</link>
    <description><![CDATA[Budget airline turned down offer that US private credit group submitted on Tuesday]]></description>
    <category><![CDATA[Companies]]></category>
    <pubDate>Tue, 24 Jun 2026 14:30:00 GMT</pubDate>
  </item>
  <item>
    <title><![CDATA[They think it&#039;s oil over]]></title>
    <link>https://www.ft.com/content/410bb8e5-dc93-459d-af41-bef7eeafdfc8</link>
    <description><![CDATA[]]></description>
    <pubDate>Wed, 25 Jun 2026 06:00:00 GMT</pubDate>
  </item>
</channel></rss>`;

test("parseFtRss extracts headline + real URL + teaser, unwrapping CDATA", () => {
  const a = parseFtRss(FT_RSS);
  expect(a.length).toBe(2);

  expect(a[0].source).toBe("ft");
  expect(a[0].title).toBe("EasyJet in talks with Castlelake after rejecting £4.9bn offer");
  expect(a[0].url).toBe("https://www.ft.com/content/155406ff-e4fc-470a-abaa-d9526c5b3e59"); // tracking stripped
  expect(a[0].summary).toBe("Budget airline turned down offer that US private credit group submitted on Tuesday");
  expect(a[0].tags).toEqual(["Companies"]);
  expect(a[0].published_at).toBe("2026-06-24T14:30:00.000Z");
});

test("no leftover CDATA markers or HTML entities in output", () => {
  const a = parseFtRss(FT_RSS);
  const blob = JSON.stringify(a);
  expect(blob).not.toContain("CDATA");
  expect(blob).not.toContain("&#039;");
  expect(a[1].title).toBe("They think it's oil over"); // entity decoded
});

test("absent teaser -> [UNAVAILABLE - paywall], never fabricated", () => {
  const a = parseFtRss(FT_RSS);
  expect(a[1].summary).toBe("[UNAVAILABLE - paywall]");
});

test("parseFtRss returns [] on garbage XML (no throw)", () => {
  expect(parseFtRss("not xml at all")).toEqual([]);
  expect(parseFtRss("")).toEqual([]);
});

test("normalizeUrl strips utm_* and publisher trackers", () => {
  expect(normalizeUrl("https://www.ft.com/content/abc?utm_source=x&mod=rss_markets&ns=1")).toBe(
    "https://www.ft.com/content/abc",
  );
  expect(normalizeUrl("https://www.ft.com/content/abc")).toBe("https://www.ft.com/content/abc");
});

test("stripHtml unwraps CDATA and strips tags", () => {
  expect(stripHtml("<![CDATA[<b>Hi</b> there]]>")).toBe("Hi there");
});

test("stripHtml decodes hexadecimal AND decimal numeric entities", () => {
  expect(stripHtml("BMW&#x2019;s shares rose to&#xa0;record")).toBe("BMW\u2019s shares rose to record");
  expect(stripHtml("oil&#x2014;and gas")).toBe("oil\u2014and gas");
  expect(stripHtml("it&#039;s 5 &#8211; 6 &amp; rising")).toBe("it's 5 \u2013 6 & rising");
});

const NOW = Date.parse("2026-06-25T12:00:00Z");
const sample: ReturnType<typeof parseFtRss> = [
  { source: "ft", url: "https://www.ft.com/content/a", title: "AI chips rally", published_at: "2026-06-25T06:00:00.000Z", summary: "semiconductors surge", tags: [] },
  { source: "ft", url: "https://www.ft.com/content/a", title: "AI chips rally", published_at: "2026-06-25T06:00:00.000Z", summary: "dupe", tags: [] }, // duplicate url
  { source: "ft", url: "https://www.ft.com/content/b", title: "Bond market calm", published_at: "2026-06-24T06:00:00.000Z", summary: "gilts steady", tags: [] },
  { source: "ft", url: "https://www.ft.com/content/c", title: "Old news", published_at: "2026-06-01T06:00:00.000Z", summary: "stale", tags: [] }, // outside 7d
];

test("filterAndRank dedups by url, drops stale, sorts newest-first", () => {
  const r = filterAndRank(sample, { days: 7, nowMs: NOW });
  expect(r.map((x) => x.url)).toEqual(["https://www.ft.com/content/a", "https://www.ft.com/content/b"]);
});

test("filterAndRank query is AND-of-words over title+summary", () => {
  const r = filterAndRank(sample, { days: 7, nowMs: NOW, query: "ai semiconductors" });
  expect(r.length).toBe(1);
  expect(r[0].url).toBe("https://www.ft.com/content/a");
  expect(filterAndRank(sample, { days: 7, nowMs: NOW, query: "nonexistent" }).length).toBe(0);
});

test("filterAndRank respects limit", () => {
  expect(filterAndRank(sample, { days: 7, nowMs: NOW, limit: 1 }).length).toBe(1);
});
