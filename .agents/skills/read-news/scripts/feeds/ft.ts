#!/usr/bin/env bun
/**
 * feed-ft — on-demand Financial Times news fetcher (self-contained).
 *
 * Invoke this when an agent needs FT news RIGHT NOW. It fetches FT's native section RSS
 * (`https://www.ft.com/<section>?format=rss`), normalizes each item, dedups across sections,
 * and PRINTS the result to stdout — no database, no npm deps (Bun built-ins only).
 *
 * Honest ceiling (FT is paywalled): each record is headline + REAL ft.com/content URL + FT's own
 * 1-sentence RSS teaser. Bodies are NOT in the feed and are NEVER fabricated — if a teaser is
 * absent the summary is "[UNAVAILABLE - paywall]". For full body text use the logged-in-Chrome
 * reader: `bun ../../scripts/feeds/read_article.ts "<ft-url>"` (see SKILL.md "Reading the BODY").
 *
 * Usage:
 *   bun fetch_ft.ts [--section markets,companies] [--query "AI chips"] [--days 7] [--limit 30] [--text]
 *
 * Flags:
 *   --section a,b,c   Comma-separated FT sections (default: markets,companies,global-economy,world).
 *                     Any ft.com/<section> works: technology, lex, unhedged, alphaville, ...
 *   --query "terms"   Case-insensitive substring filter over title+teaser (space = AND of words).
 *   --days N          Keep only items published within N days (default 7).
 *   --limit N         Cap the number of records returned (default 50).
 *   --text            Human-readable lines instead of JSON (default: JSON array).
 *
 * Output: JSON array of {source,url,title,published_at,summary,tags}. Newest first.
 * Exit:   0 if >=1 article; 1 (and a [{status:"[UNAVAILABLE]"}] record) if every section failed.
 */

export const DEFAULT_SECTIONS = ["markets", "companies", "global-economy", "world"];
const UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36";

export interface FtArticle {
  source: "ft";
  url: string;
  title: string;
  published_at: string; // ISO-8601 UTC
  summary: string; // FT teaser, or "[UNAVAILABLE - paywall]"
  tags: string[];
}

// ── pure helpers (unit-tested in fetch_ft.test.ts) ───────────────────────────

function unwrapCDATA(text: string): string {
  const m = text.match(/<!\[CDATA\[([\s\S]*?)\]\]>/);
  return m ? m[1] : text;
}

function decodeCodePoint(cp: number): string {
  // Guard invalid/out-of-range code points — String.fromCodePoint throws RangeError on those.
  if (!Number.isFinite(cp) || cp < 0 || cp > 0x10ffff) return "";
  try {
    return String.fromCodePoint(cp);
  } catch {
    return "";
  }
}

export function stripHtml(html: string): string {
  return unwrapCDATA(html)
    .replace(/<[^>]+>/g, "")
    // Numeric entities first — decimal (&#8217;) AND hexadecimal (&#x2019;); WSJ uses hex heavily.
    .replace(/&#x([0-9a-fA-F]+);/g, (_m, h) => decodeCodePoint(parseInt(h, 16)))
    .replace(/&#(\d+);/g, (_m, n) => decodeCodePoint(parseInt(n, 10)))
    // Then named entities; decode &amp; LAST so "&amp;lt;" stays literal rather than becoming "<".
    .replace(/&apos;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&nbsp;/g, " ")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&")
    .replace(/\s+/g, " ")
    .trim();
}

function tag(block: string, name: string): string {
  const m = block.match(new RegExp(`<${name}(?:\\s[^>]*)?>([\\s\\S]*?)</${name}>`, "i"));
  return m ? unwrapCDATA(m[1]).trim() : "";
}

/** Strip tracking params so the same article dedups to one canonical URL. */
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

/** Parse FT section RSS into normalized records. Pure — no network. */
export function parseFtRss(xml: string): FtArticle[] {
  const out: FtArticle[] = [];
  const blocks = xml.match(/<item[\s>][\s\S]*?<\/item>/gi) || [];
  for (const b of blocks) {
    // Decode XML entities (FT escapes `&` as `&amp;` in multi-param links) before normalizing,
    // otherwise the query string mis-parses (e.g. `&amp;ns=1` -> a bogus `amp;ns` param).
    const link = (stripHtml(tag(b, "link")) || stripHtml(tag(b, "guid"))).replace(/\s+/g, "");
    if (!link) continue;
    const title = stripHtml(tag(b, "title"));
    if (!title) continue;
    const teaser = stripHtml(tag(b, "description"));
    const tags: string[] = [];
    for (const cm of b.matchAll(/<category[^>]*>([\s\S]*?)<\/category>/gi)) {
      const c = stripHtml(cm[1]);
      if (c) tags.push(c);
    }
    out.push({
      source: "ft",
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
  articles: FtArticle[],
  opts: { query?: string; days?: number; limit?: number; nowMs?: number },
): FtArticle[] {
  const now = opts.nowMs ?? Date.now();
  const days = opts.days ?? 7;
  const limit = opts.limit ?? 50;
  const cutoff = now - days * 86_400_000;
  const terms = (opts.query ?? "").toLowerCase().split(/\s+/).filter(Boolean);

  const seen = new Set<string>();
  const kept: FtArticle[] = [];
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

export async function fetchSection(
  section: string,
): Promise<{ articles: FtArticle[]; error?: string }> {
  const url = `https://www.ft.com/${encodeURIComponent(section)}?format=rss`;
  try {
    const ac = new AbortController();
    const timer = setTimeout(() => ac.abort(), 15_000);
    const res = await fetch(url, {
      headers: { "User-Agent": UA, Accept: "application/rss+xml, application/xml, text/xml" },
      signal: ac.signal,
    });
    clearTimeout(timer);
    if (!res.ok) return { articles: [], error: `${section}: HTTP ${res.status}` };
    const xml = await res.text();
    const articles = parseFtRss(xml);
    if (!articles.length) return { articles: [], error: `${section}: 0 items parsed` };
    return { articles };
  } catch (e) {
    return { articles: [], error: `${section}: ${e instanceof Error ? e.message : String(e)}` };
  }
}

// ── CLI ───────────────────────────────────────────────────────────────────────

/**
 * Fetch every section sequentially and return the combined (un-ranked) records plus any
 * per-section errors. Reused by the trend-stock-research ingest pipeline (feed_ft.ts) so FT
 * endpoints + parsing live in exactly ONE place. Callers apply their own filter/dedup
 * (e.g. filterAndRank, or DB upsert).
 */
export async function fetchAllSections(
  sections: string[] = DEFAULT_SECTIONS,
): Promise<{ articles: FtArticle[]; errors: string[] }> {
  const articles: FtArticle[] = [];
  const errors: string[] = [];
  for (const section of sections) {
    const r = await fetchSection(section);
    articles.push(...r.articles);
    if (r.error) errors.push(r.error);
    await new Promise((res) => setTimeout(res, 300)); // polite, sequential
  }
  return { articles, errors };
}

function parseCliArgs(argv: string[]) {
  let sections = DEFAULT_SECTIONS;
  let query = "";
  let days = 7;
  let limit = 50;
  let text = false;
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--section" && argv[i + 1]) sections = argv[++i].split(",").map((s) => s.trim()).filter(Boolean);
    else if (a === "--query" && argv[i + 1]) query = argv[++i];
    else if (a === "--days" && argv[i + 1]) days = parseInt(argv[++i], 10);
    else if (a === "--limit" && argv[i + 1]) limit = parseInt(argv[++i], 10);
    else if (a === "--text") text = true;
  }
  return { sections, query, days, limit, text };
}

async function main() {
  const { sections, query, days, limit, text } = parseCliArgs(Bun.argv.slice(2));

  const all: FtArticle[] = [];
  const errors: string[] = [];
  for (const section of sections) {
    const { articles, error } = await fetchSection(section);
    all.push(...articles);
    if (error) errors.push(error);
    await new Promise((r) => setTimeout(r, 300)); // polite, sequential
  }

  const ranked = filterAndRank(all, { query, days, limit });

  if (!ranked.length) {
    // Every section failed OR nothing matched. Distinguish the two for the caller.
    const allFailed = errors.length === sections.length;
    const rec = allFailed
      ? { source: "ft", status: "[UNAVAILABLE]", reason: errors.join("; ") || "fetch failed" }
      : { source: "ft", status: "[]", reason: `no FT items in last ${days}d${query ? ` matching "${query}"` : ""}` };
    console.log(JSON.stringify([rec], null, 2));
    if (errors.length) console.error(`feed-ft: ${errors.length} section error(s): ${errors.join("; ")}`);
    process.exit(allFailed ? 1 : 0);
  }

  if (text) {
    for (const a of ranked) {
      const when = a.published_at ? a.published_at.slice(0, 16).replace("T", " ") : "????-??-??";
      console.log(`• [${when}] ${a.title}\n  ${a.url}\n  ${a.summary}`);
    }
    console.error(`\nfeed-ft: ${ranked.length} article(s) from ${sections.join(",")}${errors.length ? ` (${errors.length} section error(s))` : ""}`);
  } else {
    console.log(JSON.stringify(ranked, null, 2));
    if (errors.length) console.error(`feed-ft: ${ranked.length} article(s); ${errors.length} section error(s): ${errors.join("; ")}`);
  }
  process.exit(0);
}

if (import.meta.main) {
  await main();
}
