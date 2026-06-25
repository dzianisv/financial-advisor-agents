#!/usr/bin/env bun
/**
 * feed-wsj — on-demand Wall Street Journal news fetcher (self-contained).
 *
 * Invoke this when an agent needs WSJ news RIGHT NOW. It fetches Dow Jones' official PUBLIC RSS
 * (the new `feeds.content.dowjones.io` host — the old `feeds.a.dj.com` froze 2025-01-27), normalizes
 * each item, dedups across feeds, and PRINTS to stdout — no database, no npm deps (Bun built-ins only).
 *
 * Honest ceiling (WSJ is paywalled): each record is headline + REAL www.wsj.com URL + WSJ's own
 * 1-sentence RSS teaser. Bodies are NOT in the feed and are NEVER fabricated — if a teaser is absent
 * the summary is "[UNAVAILABLE - paywall]". For full body text use the logged-in-Chrome reader:
 * `bun ../../scripts/feeds/read_article.ts "<wsj-url>"` (see SKILL.md "Reading the BODY").
 *
 * Usage:
 *   bun fetch_wsj.ts [--feed markets,business] [--query "Fed rates"] [--days 7] [--limit 30] [--text]
 *
 * Flags:
 *   --feed a,b,c      Comma-separated WSJ feeds (default: markets,world,business,tech).
 *                     Names: markets world business tech opinion lifestyle (mapped to DJ feed codes).
 *   --query "terms"   Case-insensitive substring filter over title+teaser (space = AND of words).
 *   --days N          Keep only items published within N days (default 7).
 *   --limit N         Cap the number of records returned (default 50).
 *   --text            Human-readable lines instead of JSON (default: JSON array).
 *
 * Output: JSON array of {source,url,title,published_at,summary,tags}. Newest first.
 * Exit:   0 if >=1 article; 1 (and a [{status:"[UNAVAILABLE]"}] record) if every feed failed.
 */

// Friendly name -> Dow Jones public RSS feed code (feeds.content.dowjones.io/public/rss/<CODE>).
const FEED_CODES: Record<string, string> = {
  markets: "RSSMarketsMain",
  world: "RSSWorldNews",
  business: "WSJcomUSBusiness",
  tech: "RSSWSJD",
  opinion: "RSSOpinion",
  lifestyle: "RSSLifestyle",
};
const DEFAULT_FEEDS = ["markets", "world", "business", "tech"];
const UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36";

export interface WsjArticle {
  source: "wsj";
  url: string;
  title: string;
  published_at: string; // ISO-8601 UTC
  summary: string; // WSJ teaser, or "[UNAVAILABLE - paywall]"
  tags: string[];
}

// ── pure helpers (unit-tested in fetch_wsj.test.ts) ──────────────────────────

function unwrapCDATA(text: string): string {
  const m = text.match(/<!\[CDATA\[([\s\S]*?)\]\]>/);
  return m ? m[1] : text;
}

export function stripHtml(html: string): string {
  return unwrapCDATA(html)
    .replace(/<[^>]+>/g, "")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#0?39;|&apos;/g, "'")
    .replace(/&nbsp;/g, " ")
    .replace(/&#(\d+);/g, (_m, n) => String.fromCharCode(Number(n)))
    .replace(/\s+/g, " ")
    .trim();
}

function tag(block: string, name: string): string {
  const m = block.match(new RegExp(`<${name}(?:\\s[^>]*)?>([\\s\\S]*?)</${name}>`, "i"));
  return m ? unwrapCDATA(m[1]).trim() : "";
}

/** WSJ titles sometimes carry a publisher suffix; strip it. */
export function cleanTitle(raw: string): string {
  return raw.replace(/\s*[-–—]\s*(The Wall Street Journal|WSJ)\s*$/i, "").trim();
}

/** Strip tracking params (WSJ links carry ?mod=rss_*) so the same article dedups to one URL. */
export function normalizeUrl(url: string): string {
  try {
    const u = new URL(url);
    u.hostname = u.hostname.toLowerCase();
    const TRACKING = new Set(["mod", "reflink", "mc_cid", "mc_eid", "ns", "fbclid", "gclid"]);
    for (const k of [...u.searchParams.keys()]) {
      if (k.startsWith("utm_") || TRACKING.has(k)) u.searchParams.delete(k);
    }
    u.hash = "";
    let s = u.toString();
    if (s.endsWith("/") && u.pathname !== "/") s = s.slice(0, -1);
    return s;
  } catch {
    return url;
  }
}

function toISO(dateStr: string): string {
  const d = new Date(dateStr);
  return isNaN(d.getTime()) ? "" : d.toISOString();
}

/** Parse WSJ Dow Jones RSS into normalized records. Pure — no network. */
export function parseWsjRss(xml: string): WsjArticle[] {
  const out: WsjArticle[] = [];
  const blocks = xml.match(/<item[\s>][\s\S]*?<\/item>/gi) || [];
  for (const b of blocks) {
    // WSJ <guid> is NOT a URL (e.g. "WP-WSJ-0003688412") — only use <link>; entity-decode it first.
    let link = stripHtml(tag(b, "link")).replace(/\s+/g, "");
    if (!link) {
      const guid = stripHtml(tag(b, "guid")).replace(/\s+/g, "");
      if (/^https?:\/\//i.test(guid)) link = guid;
    }
    if (!link) continue;
    const title = cleanTitle(stripHtml(tag(b, "title")));
    if (!title) continue;
    const teaser = stripHtml(tag(b, "description"));
    const tags: string[] = [];
    for (const cm of b.matchAll(/<category[^>]*>([\s\S]*?)<\/category>/gi)) {
      const c = stripHtml(cm[1]);
      if (c) tags.push(c);
    }
    out.push({
      source: "wsj",
      url: normalizeUrl(link),
      title,
      published_at: toISO(tag(b, "pubDate") || tag(b, "dc:date")),
      summary: teaser || "[UNAVAILABLE - paywall]",
      tags,
    });
  }
  return out;
}

/** Dedup (by url), recency-filter, keyword-filter, sort newest-first, cap. Pure. */
export function filterAndRank(
  articles: WsjArticle[],
  opts: { query?: string; days?: number; limit?: number; nowMs?: number },
): WsjArticle[] {
  const now = opts.nowMs ?? Date.now();
  const days = opts.days ?? 7;
  const limit = opts.limit ?? 50;
  const cutoff = now - days * 86_400_000;
  const terms = (opts.query ?? "").toLowerCase().split(/\s+/).filter(Boolean);

  const seen = new Set<string>();
  const kept: WsjArticle[] = [];
  for (const a of articles) {
    if (seen.has(a.url)) continue;
    seen.add(a.url);
    if (a.published_at) {
      const t = new Date(a.published_at).getTime();
      if (!isNaN(t) && t < cutoff) continue;
    }
    if (terms.length) {
      const hay = (a.title + " " + a.summary).toLowerCase();
      if (!terms.every((w) => hay.includes(w))) continue;
    }
    kept.push(a);
  }
  kept.sort((x, y) => (y.published_at || "").localeCompare(x.published_at || ""));
  return kept.slice(0, limit);
}

// ── network ──────────────────────────────────────────────────────────────────

async function fetchFeed(name: string): Promise<{ articles: WsjArticle[]; error?: string }> {
  const code = FEED_CODES[name] ?? name; // allow raw DJ codes too
  const url = `https://feeds.content.dowjones.io/public/rss/${encodeURIComponent(code)}`;
  try {
    const ac = new AbortController();
    const timer = setTimeout(() => ac.abort(), 15_000);
    const res = await fetch(url, {
      headers: { "User-Agent": UA, Accept: "application/rss+xml, application/xml, text/xml" },
      signal: ac.signal,
    });
    clearTimeout(timer);
    if (!res.ok) return { articles: [], error: `${name}: HTTP ${res.status}` };
    const xml = await res.text();
    const articles = parseWsjRss(xml);
    if (!articles.length) return { articles: [], error: `${name}: 0 items parsed` };
    return { articles };
  } catch (e) {
    return { articles: [], error: `${name}: ${e instanceof Error ? e.message : String(e)}` };
  }
}

// ── CLI ───────────────────────────────────────────────────────────────────────

function parseCliArgs(argv: string[]) {
  let feeds = DEFAULT_FEEDS;
  let query = "";
  let days = 7;
  let limit = 50;
  let text = false;
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--feed" && argv[i + 1]) feeds = argv[++i].split(",").map((s) => s.trim()).filter(Boolean);
    else if (a === "--query" && argv[i + 1]) query = argv[++i];
    else if (a === "--days" && argv[i + 1]) days = parseInt(argv[++i], 10);
    else if (a === "--limit" && argv[i + 1]) limit = parseInt(argv[++i], 10);
    else if (a === "--text") text = true;
  }
  return { feeds, query, days, limit, text };
}

async function main() {
  const { feeds, query, days, limit, text } = parseCliArgs(Bun.argv.slice(2));

  const all: WsjArticle[] = [];
  const errors: string[] = [];
  for (const name of feeds) {
    const { articles, error } = await fetchFeed(name);
    all.push(...articles);
    if (error) errors.push(error);
    await new Promise((r) => setTimeout(r, 300)); // polite, sequential
  }

  const ranked = filterAndRank(all, { query, days, limit });

  if (!ranked.length) {
    const allFailed = errors.length === feeds.length;
    const rec = allFailed
      ? { source: "wsj", status: "[UNAVAILABLE]", reason: errors.join("; ") || "fetch failed" }
      : { source: "wsj", status: "[]", reason: `no WSJ items in last ${days}d${query ? ` matching "${query}"` : ""}` };
    console.log(JSON.stringify([rec], null, 2));
    if (errors.length) console.error(`feed-wsj: ${errors.length} feed error(s): ${errors.join("; ")}`);
    process.exit(allFailed ? 1 : 0);
  }

  if (text) {
    for (const a of ranked) {
      const when = a.published_at ? a.published_at.slice(0, 16).replace("T", " ") : "????-??-??";
      console.log(`• [${when}] ${a.title}\n  ${a.url}\n  ${a.summary}`);
    }
    console.error(`\nfeed-wsj: ${ranked.length} article(s) from ${feeds.join(",")}${errors.length ? ` (${errors.length} feed error(s))` : ""}`);
  } else {
    console.log(JSON.stringify(ranked, null, 2));
    if (errors.length) console.error(`feed-wsj: ${ranked.length} article(s); ${errors.length} feed error(s): ${errors.join("; ")}`);
  }
  process.exit(0);
}

if (import.meta.main) {
  await main();
}
