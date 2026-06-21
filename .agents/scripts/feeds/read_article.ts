#!/usr/bin/env bun
// read_article.ts — fetch full body of a (possibly paywalled) article URL.
//
// Usage: bun read_article.ts <url> [--no-cache]
// Outputs: article body text to stdout
// Side effect: ingests into article cache via fetch_article.py
// Exit code: 0=success, 1=unavailable

import { $ } from "bun";

const FETCH_PY = "/Users/engineer/workspace/backtest/.agents/scripts/feeds/fetch_article.py";
const CHROME = "/Users/engineer/.agents/skills/chrome-use/scripts/chrome-use";

const argv = process.argv.slice(2);
const url = argv.find((a) => !a.startsWith("--"));
const noCache = argv.includes("--no-cache");

if (!url) {
  console.error("Usage: bun read_article.ts <url> [--no-cache]");
  process.exit(1);
}

// 1. Cache check — exact URL lookup (avoids FTS5 syntax errors from dots in URLs)
if (!noCache) {
  try {
    const cached = await $`python3 ${FETCH_PY} --by-url ${url}`.json();
    if (cached && cached.body && !cached.body.startsWith("[UNAVAILABLE")) {
      process.stdout.write(cached.body);
      process.exit(0);
    }
  } catch {
    // cache miss or unavailable — continue
  }
}

// 2. Methods

async function archivePhChrome(targetUrl: string): Promise<string> {
  try {
    await $`${CHROME} open ${"https://archive.ph/newest/" + targetUrl}`.quiet();
  } catch {
    throw new Error("chrome-use open failed — is Chrome running?");
  }

  await Bun.sleep(10_000);

  const extractJs = `(() => {
    const a = document.querySelector('#CONTENT, #article, article, main, .article-wrap, .article-body');
    if (a) return a.innerText.substring(0, 8000);
    const b = document.body.cloneNode(true);
    b.querySelectorAll('header,nav,footer,[id="HEAD"],#shareTools,.archiveMetadata').forEach(e => e.remove());
    return b.innerText.substring(0, 8000);
  })()`;

  const body = await $`${CHROME} eval ${extractJs}`.text();
  const title = await $`${CHROME} eval ${"document.title"}`.text();

  if (/security check|captcha|cloudflare|ddos/i.test(body)) {
    throw new Error(
      "[UNAVAILABLE - archive.ph CAPTCHA: open https://archive.ph in Chrome and solve it, then retry]"
    );
  }
  if (!body.trim()) {
    throw new Error("[UNAVAILABLE - archive.ph returned empty body]");
  }

  await $`python3 ${FETCH_PY} --ingest --url ${targetUrl} --title ${title.trim()} --body ${body} --source archive.ph`
    .quiet()
    .nothrow();

  return body;
}

async function wayback(targetUrl: string): Promise<string> {
  const archiveUrl = `https://web.archive.org/web/2/${targetUrl}`;
  const resp = await fetch(archiveUrl, {
    headers: {
      "User-Agent":
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    },
  });
  if (!resp.ok) throw new Error(`Wayback returned HTTP ${resp.status}`);

  const html = await resp.text();
  const body = html
    .replace(/<(script|style|nav|header|footer)[^>]*>[\s\S]*?<\/\1>/gi, "")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .substring(0, 8000);

  if (/subscribe to read|sign in to read/i.test(body)) {
    throw new Error("[UNAVAILABLE - Wayback only has paywall snapshot]");
  }

  const titleMatch = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
  const title = titleMatch ? titleMatch[1].trim() : "";

  await $`python3 ${FETCH_PY} --ingest --url ${targetUrl} --title ${title} --body ${body} --source wayback`
    .quiet()
    .nothrow();

  return body;
}

// 3. Dispatch — WSJ: Wayback first; all others: archive.ph first
const isWSJ = /wsj\.com/i.test(url);
const [primary, fallback] = isWSJ
  ? [wayback, archivePhChrome]
  : [archivePhChrome, wayback];

try {
  process.stdout.write(await primary(url));
} catch (e1) {
  try {
    process.stdout.write(await fallback(url));
  } catch (e2) {
    console.error(`[UNAVAILABLE - all methods failed for ${url}]`);
    console.error(e1);
    console.error(e2);
    process.exit(1);
  }
}
