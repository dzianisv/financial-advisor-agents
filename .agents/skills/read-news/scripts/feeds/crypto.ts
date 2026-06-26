/**
 * crypto.ts — 7 crypto/news generic-RSS feeds, self-contained.
 * Imports parseRSS/stripHtml/toISO from ../types (no npm deps).
 */

import type { Article } from "../types";
import { parseRSS, stripHtml, toISO } from "../types";

const UA = "FeedBot/1.0 (news aggregator; +https://example.invalid)";

export const CRYPTO_FEED_URLS: Record<string, string> = {
  decrypt: "https://decrypt.co/feed",
  coindesk: "https://www.coindesk.com/arc/outboundfeeds/rss/",
  cointelegraph: "https://cointelegraph.com/rss",
  theblock: "https://www.theblock.co/rss.xml",
  bitcoinmagazine: "https://bitcoinmagazine.com/feed",
  // Direct coinbase.com/blog RSS is Cloudflare-gated (403); use Google News proxy instead.
  coinbase:
    "https://news.google.com/rss/search?q=(site%3Acoinbase.com%2Fblog+OR+site%3Acoinbase.com%2Finstitutional)+when%3A14d&hl=en-US&gl=US&ceid=US%3Aen",
  bloomberg: "https://www.bloomberg.com/feed/podcast/etf-report.xml", // podcast feed; often 403
};

// Feeds that carry full body text in content:encoded
const HAS_CONTENT_ENCODED = new Set(["decrypt", "coindesk", "cointelegraph", "bitcoinmagazine"]);

export async function fetchCryptoFeed(
  name: string,
): Promise<{ source: string; articles: Article[]; errors: string[] }> {
  const errors: string[] = [];
  const url = CRYPTO_FEED_URLS[name];
  if (!url) {
    errors.push(`unknown feed: ${name}`);
    return { source: name, articles: [], errors };
  }

  let xml: string;
  try {
    const ac = new AbortController();
    const timer = setTimeout(() => ac.abort(), 15_000);
    const res = await fetch(url, {
      headers: { "User-Agent": UA, Accept: "application/rss+xml, application/xml, text/xml, */*" },
      signal: ac.signal,
    });
    clearTimeout(timer);
    if (!res.ok) {
      errors.push(`HTTP ${res.status} from ${url}`);
      return { source: name, articles: [], errors };
    }
    xml = await res.text();
  } catch (e) {
    errors.push(e instanceof Error ? e.message : String(e));
    return { source: name, articles: [], errors };
  }

  const items = parseRSS(xml);
  const articles: Article[] = [];

  for (const item of items) {
    if (!item.link) continue;
    const body =
      HAS_CONTENT_ENCODED.has(name) && item.contentEncoded
        ? stripHtml(item.contentEncoded)
        : null;
    articles.push({
      source: name,
      url: item.link,
      title: item.title,
      summary: stripHtml(item.description),
      body,
      published_at: toISO(item.pubDate),
      lang: "en",
      tags: item.categories,
    });
  }

  return { source: name, articles, errors };
}
