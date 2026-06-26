/**
 * Shared types and utilities for feed ingestion.
 * Zero npm deps — uses Bun built-ins only.
 */

import { resolve, join } from "node:path";

// ── Types ───────────────────────────────────────────────────────────────────

export interface Article {
  source: string;        // feed name: "decrypt", "coindesk", "ft", "wsj"
  url: string;           // article URL
  title: string;         // cleaned title
  summary: string;       // RSS description/teaser
  body: string | null;   // full article body (null if paywalled)
  published_at: string;  // ISO datetime
  lang: string;          // default "en"
  tags: string[];        // from RSS categories
}

export interface FeedResult {
  source: string;
  fetched: number;       // total articles parsed from RSS
  inserted: number;      // new articles inserted (not dupes)
  enriched: number;      // articles where body was fetched
  withinWindow: number;  // articles whose date was within --days filter
  errors: string[];      // any errors encountered
}

export interface RSSItem {
  title: string;
  link: string;
  description: string;
  pubDate: string;
  categories: string[];
  contentEncoded: string | null;
  sourceUrl?: string;  // <source url="..."> attribute (Google News RSS)
}

// ── HTML / XML helpers ──────────────────────────────────────────────────────

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
  return html
    .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1")
    .replace(/<[^>]+>/g, "")
    // Numeric entities first — decimal (&#8217;) AND hexadecimal (&#x2019;); WSJ/Dow Jones emit hex
    // almost exclusively, so a decimal-only decoder leaves teasers garbled ("Vance&#x2019;s").
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

function extractCDATA(text: string): string {
  const m = text.match(/<!\[CDATA\[([\s\S]*?)\]\]>/);
  return m ? m[1] : text;
}

function getTag(xml: string, tag: string): string | null {
  const re = new RegExp(`<${tag}(?:\\s[^>]*)?>([\\s\\S]*?)</${tag}>`, "i");
  const m = xml.match(re);
  return m ? extractCDATA(m[1]).trim() : null;
}

function getAttr(xml: string, tag: string, attr: string): string | null {
  const re = new RegExp(`<${tag}[^>]*\\s${attr}\\s*=\\s*["']([^"']*)["']`, "i");
  const m = xml.match(re);
  return m ? m[1] : null;
}

// ── RSS parser (handles RSS 2.0 + Atom) ─────────────────────────────────────

export function parseRSS(xml: string): RSSItem[] {
  const items: RSSItem[] = [];

  // RSS 2.0: <item>...</item>
  const rssBlocks = xml.match(/<item[\s>][\s\S]*?<\/item>/gi) || [];
  for (const block of rssBlocks) {
    const title = getTag(block, "title") || "";
    let link = getTag(block, "link") || getTag(block, "guid") || "";
    link = link.replace(/\s+/g, "");
    const description = getTag(block, "description") || "";
    const pubDate = getTag(block, "pubDate") || getTag(block, "dc:date") || "";
    const contentEncoded = getTag(block, "content:encoded");

    const categories: string[] = [];
    for (const cm of block.matchAll(/<category[^>]*>([\s\S]*?)<\/category>/gi)) {
      const cat = stripHtml(extractCDATA(cm[1]).trim());
      if (cat) categories.push(cat);
    }

    // Google News RSS: <source url="https://www.wsj.com/...">WSJ</source>
    const sourceUrl = getAttr(block, "source", "url") || undefined;

    items.push({
      title: stripHtml(title),
      link,
      description,
      pubDate,
      categories,
      contentEncoded,
      sourceUrl,
    });
  }

  // Atom fallback: <entry>...</entry>
  if (!items.length) {
    const atomBlocks = xml.match(/<entry[\s>][\s\S]*?<\/entry>/gi) || [];
    for (const block of atomBlocks) {
      const title = getTag(block, "title") || "";
      const link = getAttr(block, "link", "href") || getTag(block, "link") || "";
      const description = getTag(block, "summary") || getTag(block, "content") || "";
      const pubDate = getTag(block, "published") || getTag(block, "updated") || "";

      const categories: string[] = [];
      for (const cm of block.matchAll(/<category[^>]*term\s*=\s*["']([^"']*)["']/gi)) {
        if (cm[1]) categories.push(cm[1]);
      }

      items.push({
        title: stripHtml(title),
        link: link.trim(),
        description,
        pubDate,
        categories,
        contentEncoded: null,
      });
    }
  }

  return items;
}

// ── URL normalization ───────────────────────────────────────────────────────

export function normalizeUrl(url: string): string {
  try {
    const u = new URL(url);
    u.hostname = u.hostname.toLowerCase();
    // Drop tracking params: utm_*, and known publisher trackers (WSJ/Dow Jones `mod`/`reflink`,
    // mailchimp mc_cid/mc_eid). Stripping these makes the same article dedup to one canonical_url
    // even when it arrives via different feeds with different tracking suffixes.
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

// ── Content hash ────────────────────────────────────────────────────────────

export function contentHash(title: string, summary: string): string {
  const h = new Bun.CryptoHasher("sha256");
  h.update((title + "\n" + summary).toLowerCase());
  return h.digest("hex");
}

// ── Date utilities ──────────────────────────────────────────────────────────

export function toISO(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return isNaN(d.getTime()) ? new Date().toISOString() : d.toISOString();
  } catch {
    return new Date().toISOString();
  }
}

export function isWithinDays(iso: string, days: number): boolean {
  return new Date(iso).getTime() >= Date.now() - days * 86_400_000;
}

// ── CLI arg parser ──────────────────────────────────────────────────────────

export function repoRoot(): string {
  return resolve(import.meta.dir, "..", "..", "..");
}

export function parseArgs(): { dbPath: string; days: number; noEnrich: boolean } {
  const args = Bun.argv.slice(2);
  let dbPath = "";
  let days = 7;
  let noEnrich = false;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--db" && args[i + 1]) dbPath = args[++i];
    else if (args[i] === "--days" && args[i + 1]) days = parseInt(args[++i], 10);
    else if (args[i] === "--no-enrich") noEnrich = true;
  }

  if (!dbPath) dbPath = join(repoRoot(), ".db", "news.db");
  return { dbPath, days, noEnrich };
}

// ── Misc ────────────────────────────────────────────────────────────────────

export const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

// ── Wayback Machine enrichment ──────────────────────────────────────────────

export function extractArticleBody(html: string): string | null {
  let c = html
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/<style[\s\S]*?<\/style>/gi, "")
    .replace(/<nav[\s\S]*?<\/nav>/gi, "")
    .replace(/<header[\s\S]*?<\/header>/gi, "")
    .replace(/<footer[\s\S]*?<\/footer>/gi, "")
    .replace(/<aside[\s\S]*?<\/aside>/gi, "");

  // Prefer <article> content if present
  const am = c.match(/<article[\s\S]*?>([\s\S]*?)<\/article>/i);
  if (am) c = am[1];

  const text = stripHtml(c);
  if (text.length < 200) return null;
  if (/subscribe to read|sign in to read|already a subscriber|keep reading/i.test(text))
    return null;
  return text;
}

export async function fetchWaybackBody(
  url: string,
  timeoutMs = 5000,
): Promise<string | null> {
  try {
    const ac1 = new AbortController();
    const t1 = setTimeout(() => ac1.abort(), timeoutMs);
    const r1 = await fetch(
      `https://archive.org/wayback/available?url=${encodeURIComponent(url)}`,
      { signal: ac1.signal },
    );
    clearTimeout(t1);
    if (!r1.ok) return null;

    const data = (await r1.json()) as {
      archived_snapshots?: { closest?: { available?: boolean; status?: string; url?: string } };
    };
    const snap = data?.archived_snapshots?.closest;
    if (!snap?.available || String(snap.status) !== "200" || !snap.url) return null;

    const ac2 = new AbortController();
    const t2 = setTimeout(() => ac2.abort(), timeoutMs);
    const r2 = await fetch(snap.url, { signal: ac2.signal });
    clearTimeout(t2);
    if (!r2.ok) return null;

    return extractArticleBody(await r2.text());
  } catch {
    return null;
  }
}
