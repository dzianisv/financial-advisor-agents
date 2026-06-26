/**
 * index.ts — unified registry for all 9 news feeds.
 *
 * fetchAllNews({ sources }) fetches EVERY requested feed sequentially (polite ~300ms gap)
 * and returns normalized Article records plus a list of per-feed failures.
 */

import type { Article } from "../types";
import { sleep } from "../types";
import { fetchAllSections } from "./ft";
import type { FtArticle } from "./ft";
import { fetchAllFeeds } from "./wsj";
import type { WsjArticle } from "./wsj";
import { fetchCryptoFeed, CRYPTO_FEED_URLS } from "./crypto";

const CRYPTO_SOURCES = Object.keys(CRYPTO_FEED_URLS);

export const NEWS_FEEDS: string[] = ["ft", "wsj", ...CRYPTO_SOURCES];

function ftToArticle(a: FtArticle): Article {
  return {
    source: a.source,
    url: a.url,
    title: a.title,
    summary: a.summary,
    body: null,
    published_at: a.published_at,
    lang: "en",
    tags: a.tags,
  };
}

function wsjToArticle(a: WsjArticle): Article {
  return {
    source: a.source,
    url: a.url,
    title: a.title,
    summary: a.summary,
    body: null,
    published_at: a.published_at,
    lang: "en",
    tags: a.tags,
  };
}

export async function fetchAllNews(opts?: {
  sources?: string[];
}): Promise<{ records: Article[]; unavailable: string[] }> {
  const requested = opts?.sources ?? NEWS_FEEDS;
  const records: Article[] = [];
  const unavailable: string[] = [];

  for (const name of requested) {
    if (name === "ft") {
      const { articles, errors } = await fetchAllSections();
      records.push(...articles.map(ftToArticle));
      if (errors.length) unavailable.push(`ft:${errors.join("; ")}`);
    } else if (name === "wsj") {
      const { articles, errors } = await fetchAllFeeds();
      records.push(...articles.map(wsjToArticle));
      if (errors.length) unavailable.push(`wsj:${errors.join("; ")}`);
    } else if (CRYPTO_FEED_URLS[name] !== undefined) {
      const { articles, errors } = await fetchCryptoFeed(name);
      records.push(...articles);
      if (errors.length) unavailable.push(`${name}:${errors.join("; ")}`);
    } else {
      unavailable.push(`${name}:unknown feed`);
    }
    await sleep(300);
  }

  return { records, unavailable };
}
