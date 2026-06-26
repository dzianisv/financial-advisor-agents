---
name: read-news
description: The ONE front door for the financial-news pipeline — fetch + normalize + dedup + store + query, in a single Bun/TypeScript stack. Pulls every wired RSS feed (CoinDesk, Decrypt, CoinTelegraph, The Block, Bitcoin Magazine, Coinbase, FT, WSJ, Bloomberg) via `read_news.ts`, collapses multi-outlet coverage of the same story into ONE event (SQLite + FTS5 BM25 + near-dup Jaccard clustering), keeps cross-run state so the panel never re-reads news it already saw, and answers ranked hybrid queries. Use when gathering the crypto/macro news feed, when narrative-news / analysis-narrative needs deduped events, when an advisor needs FT/WSJ headlines on demand, or when asked to "get the news", "what's new since last run", "dedup crypto news", "cluster multi-outlet coverage", "query the news store", "FT headlines", "WSJ markets news", or "what is the news saying about X". Keyless, no API key, no embedding model required. NEVER fabricates a headline or body.
license: MIT
compatibility: opencode
metadata:
  audience: crypto-research-pipeline
  domain: news-fetch-dedup-store-query
  role: unified-news-pipeline
---

# Read News (fetch → dedup → store → query — events, not articles, and never twice)

The single news pipeline the [[narrative-news]] and [[analysis-narrative]] gather seats read. It
**fetches** every wired feed, **normalizes** each article into the common record, **collapses
multi-outlet coverage of the same event into ONE event** carrying a `source_count` (crowdedness), and
**keeps state across runs** so the panel never re-reads news it already saw — the same "no re-alert"
discipline as [[13f-watch]] / [[dip-scanner]].

This skill replaces the old `feed-*` per-source adapters and the `crypto-news-store` Python store: one
Bun/TypeScript stack, one SQLite file, one front door.

## Hard rule

Never fabricate. The store only ever holds what the feeds actually fetched. Paywalled sources with no
teaser surface `[UNAVAILABLE - paywall]`; a feed that fails to fetch surfaces loudly in `unavailable` —
never silently dropped, never invented.

## One command (preferred — fetch + ingest + ranked events in one shot)

```bash
bun .agents/skills/read-news/scripts/read_news.ts \
  --db .db/news.db --days 5 \
  --query "bitcoin BTC ETF regulation treasury strategy"
# → {fetched, feeds_ok, unavailable:[...], events:[ {title, source_count, ...} ranked by relevance ]}
```

`--query` returns the hybrid (BM25 + near-dup) **relevant** events and cuts the new-since noise; omit it
to get everything new-since. Build `--query` from the asset(s)/entities in the workflow question. Per-feed
failures come back in `unavailable` (loud) — never silently dropped.

| Flag | Default | Meaning |
|---|---|---|
| `--db` | `.db/news.db` (env `CRYPTO_NEWS_DB`) | SQLite file |
| `--days` | `3` | recency window for new-since / query |
| `--k` | `15` | max events returned by `--query` |
| `--query` | `""` | if set → ranked relevant events; else → all new-since |
| `--source` | all | CSV to restrict feeds, e.g. `--source ft,wsj` |

After the brief is written, mark events surfaced so they don't repeat next run:

```bash
bun .agents/skills/read-news/scripts/news_store.ts --db .db/news.db mark-surfaced --ids 1 4 --on 2026-06-15
```

## Targeted single-source pulls (FT / WSJ on demand)

When an advisor wants only FT or only WSJ headlines (no DB, prints to stdout):

```bash
bun .agents/skills/read-news/scripts/feeds/ft.ts  --section markets,global-economy --query bitcoin --days 5 --text
bun .agents/skills/read-news/scripts/feeds/wsj.ts --feed markets --days 5 --limit 20 --text
```

## What it is

`scripts/` — **Bun + `bun:sqlite` only** (no network at store layer, no embedding model, zero npm deps).

- `read_news.ts` — the orchestrator: fetch all feeds → ingest (dedup + state) → query / new-since → JSON.
- `news_store.ts` — the SQLite store (single file, default `.db/news.db`):
  - **`articles`** — one row per ingested article (+ `canonical_url`, `content_hash`, `simhash`).
  - **`articles_fts`** (FTS5) — BM25 over `title + summary` for named entities/tickers (`MSTR`, `$11B`, `ETF`).
  - **`events`** — one row per event cluster carrying cross-run state: `{first_seen, last_updated,
    sources(json), source_count, surfaced_to_panel_on}`.
- `feeds/` — fetch + normalize adapters: `ft.ts`, `wsj.ts`, `crypto.ts` (7 generic-RSS feeds), unified by
  `feeds/index.ts` → `fetchAllNews({sources?}) → {records, unavailable}`.

### Two-layer dedup
1. **Exact** — canonical URL (utm/tracking stripped) **OR** `sha256(normalized(title+summary))` already
   present → skip re-ingest.
2. **Near-dup** — token-shingle (word + bigram) **Jaccard** over normalized text; `>= 0.15`
   (env `CRYPTO_NEWS_JACCARD`) attaches the article to the existing event and bumps its `source_count`.
   **Jaccard, not SimHash Hamming, is the deciding metric** — on short news text (headline + summary)
   same-event Jaccard ≈ 0.27 vs different-event ≈ 0.03–0.05 (clean separation); SimHash Hamming on the
   same text was 21 vs 30 (too close). A 64-bit SimHash is still computed and stored as a coarse signature.

### OPTIONAL dense-vector upgrade (graceful, never crashes)
Set env `CRYPTO_NEWS_EMBED_CMD` to a shell command that reads text on stdin and prints a JSON float array
on stdout. If set **and** it works, near-dup uses cosine `>= CRYPTO_NEWS_EMBED_COS` (default 0.85) and the
vector is stored on the event. If absent **or** the command errors, it silently falls back to Jaccard.

### Hybrid retrieval (query)
BM25 (FTS5) **fused with** near-dup-cluster Jaccard rank via **RRF** (reciprocal-rank fusion, k=60).
Returns **events, not raw rows**.

## News sources (keyless, verified 2026-06)

| Source | Signal | Notes |
|---|---|---|
| CoinDesk | ETF approvals, institutional, macro | Full RSS content |
| Decrypt | DeFi, retail narrative, culture | Full RSS content |
| CoinTelegraph | Broad crypto news, regulatory | Full RSS content |
| The Block | Institutional, data-driven | Full RSS content |
| Bitcoin Magazine | BTC-native, halving, protocol | Full RSS content |
| Coinbase blog | Institutional research, policy | Via Google News proxy (direct 403) |
| FT | Macro, rates, global risk-off | RSS teaser (paywall — headline only) |
| WSJ | US regulatory, Fed, institutional | Dow Jones RSS |
| Bloomberg | Rates, macro, ETF (podcast feed) | Best-effort — often 403 |

**Supplementary keyless sources (call directly when targeted fetch needed):**

```bash
# Google News RSS — on-demand entity search; also captures Reuters, AP
curl -sL "https://news.google.com/rss/search?q=bitcoin+ETF+regulation+when:2d&hl=en-US&gl=US&ceid=US:en"

# SEC EDGAR — hard primary-source 8-K filings (treasury buys, ETF S-1s, enforcement)
curl -sL -A "research@example.invalid" \
  "https://efts.sec.gov/LATEST/search-index?q=%22bitcoin%22&forms=8-K&startdt=$(date -v-7d +%Y-%m-%d)"

# CoinGecko trending — retail attention / narrative-rotation proxy
curl -sL "https://api.coingecko.com/api/v3/search/trending"

# Fear & Greed Index — crowd sentiment cross-check
curl -s "https://api.alternative.me/fng/?limit=7"

# ETF flows — farside.co.uk is Cloudflare-gated (403 to curl).
#   (a) read_news.ts events already contain ETF flow headlines, or
#   (b) WebFetch/Chrome-CDP: https://farside.co.uk/btc/  (JS render required)
```

**Source priority for narrative analysis:**
1. `read_news.ts` — primary; run first, covers 9 feeds
2. Google News RSS — targeted entity search and Reuters/AP coverage
3. SEC EDGAR — hard, timestamped primary-source regulatory/treasury events
4. CoinGecko trending — retail attention signal
5. farside.co.uk — ETF flows; WebFetch/CDP path only (not curl-able)

## Store commands

```bash
S="bun .agents/skills/read-news/scripts/news_store.ts"   # add --db <path> for a throwaway store

$S --db .db/news.db ingest --json records.json   # idempotent → {new, duplicate, events_touched}
$S query --q "strategy bitcoin" --days 2 --k 10           # HYBRID BM25+near-dup, fused via RRF → events
$S new-since --days 2                                     # events in window AND not yet surfaced (panel feed)
$S mark-surfaced --ids 1 4 --on 2026-06-15                # stamp surfaced; excludes from future new-since
```

`records.json` is a JSON list of normalized records `{source, url, title, summary, published_at, lang,
tags}` (optional `body`). `ingest` accepts a bare list or `{"records": [...]}`.

## Self-test (run to verify the install)

```bash
bun test ./.agents/skills/read-news/scripts/
# news_store.test.ts includes a GOLDEN PARITY gate: a frozen snapshot of the retired Python store's
# exact ingest counts, new-since set, and query ranking (captured before retirement). The TS store must
# reproduce them — the regression guard that lets the Python pipeline stay retired.
```

## Fit

`read_news.ts` (fetch + normalize via `feeds/`) → **`ingest`** (dedup + cluster) → **`new-since` / `query`**
→ [[narrative-news]] / [[analysis-narrative]] emit the NEW/updated events to the panel and own the
priced-in judgment. This skill owns fetch + dedup + recency + cross-run state; it does not judge.

> Educational, not advice. Events are context + disconfirmation, never a trigger.
