---
name: narrative-news
description: The DATA-ONLY news gather seat for the crypto panel. Orchestrates the read-news pipeline (fetch + dedup + state) → emits ONLY the NEW or materially-updated EVENTS (not articles) for the consolidated brief, each tagged PRICED_IN vs ACTIONABLE_CONTEXT with a source_count. Use when running the research-crypto-market gather phase, when asked "what crypto news/narrative matters right now", "any new catalysts", "narrative seat", or for the FR1.8 news/narrative category. Depends on read-news. Data only — no opinions, no buy/sell.
license: MIT
compatibility: opencode
metadata:
  audience: crypto-research-pipeline
  domain: news-narrative-gather-seat
  role: gather-seat
---

# narrative-news (the news/narrative gather seat — FR1.8)

The **data-only** Gather seat the `research-crypto-market` workflow calls for the REQUIRED news/narrative
category (PRD FR1.8). It produces **EVENTS, not articles, not opinions** — the panel debates; this seat
only reports what happened, deduped and state-aware.

**Depends on:** [[read-news]] — one Bun/TS pipeline that fetches all 9 feeds (Decrypt, CoinTelegraph,
CoinDesk, The Block, Bitcoin Magazine, Coinbase, FT, WSJ, Bloomberg), normalizes, dedups, and keeps
cross-run state.

## Hard rules

- **Data only.** No buy/sell, no verdict, no price target. News is **lagging/reflexive → context +
  disconfirmation, never a trigger** (PRD FR1.8 guardrail).
- **Never fabricate.** Only emit what `feed-*` actually returned; paywalled bodies stay `[UNAVAILABLE]`.
- **Events, not articles** — the same event across N outlets is ONE event with `source_count=N` (NFR2).
- **Never re-surface** an event already `surfaced_to_panel_on` a prior run (the no-re-alert rule).

## Pipeline — ONE deterministic command (preferred; reliable)

Do NOT hand-orchestrate 8 WebFetch calls (that path is fragile and failed in iteration 1). Run the
deterministic fetcher: it pulls every crypto-native RSS feed via urllib, normalizes, ingests (dedup +
state), and returns the **ranked, question-relevant** deduped events in one shot.

```bash
bun .agents/skills/read-news/scripts/read_news.ts \
  --db .db/news.db --days 5 \
  --query "<key entities from the question: e.g. bitcoin BTC ETF Strategy MicroStrategy treasury Fed Coinbase COIN>"
# → {fetched, feeds_ok, unavailable:[...], events:[ {title, source_count, ...} ranked by relevance ]}
```
`--query` returns the hybrid (BM25 + near-dup) **relevant** events and cuts the new-since noise; omit it to
get everything new-since. Build `--query` from the asset(s)/entities in the workflow question. Per-feed
failures come back in `unavailable` (loud, NFR6) — never silently dropped.

After the brief is written, the workflow marks events surfaced so they don't repeat next run:
```bash
bun .agents/skills/read-news/scripts/news_store.ts --db .db/news.db mark-surfaced --ids <ids...>
```

**Fallback (only if read_news fails):** pull a single source to stdout with
`bun .agents/skills/read-news/scripts/feeds/ft.ts --text` (or `feeds/wsj.ts`, `feeds/crypto.ts`), then
`bun .agents/skills/read-news/scripts/news_store.ts ingest --json records.json` and `query`/`new-since` as above.

## Recency + materiality filter (NFR3)

Keep an event as a **catalyst** only if: `first_seen`/`last_updated` within **36h** (24–48h window) **AND**
it clears a materiality bar — moves price/odds, is a hard event (ETF flow, SEC filing, hack/exploit,
exchange event, corporate treasury buy), or comes from a top-tier source. Older or trivial items → label
`context`, not catalyst.

## Priced-in heuristic (the one judgment this seat makes)

Compare each catalyst against signals **already in the brief context** (the price seat's move + the odds
seat's shift):
- **`PRICED_IN`** — price already moved in the catalyst's direction **OR** the relevant odds already
  shifted. The market has absorbed it.
- **`ACTIONABLE_CONTEXT`** — fresh + unreacted within the recency window, no matching price/odds move yet.
  (Still context/disconfirmation per FR1.8 — *not* a buy signal.)

When the price/odds context is unavailable, tag `PRICED_IN=unknown` rather than guessing.

## Output (DATA_SCHEMA record — one per event, NEW/updated only)

```json
{
  "category": "news_narrative",
  "events": [
    {
      "event": "Strategy raises reserves to $11B, buys more BTC",
      "event_cluster_id": 1,
      "sources": [
        {"outlet": "decrypt", "url": "https://decrypt.co/...", "published_at": "2026-06-15T08:00:00Z"},
        {"outlet": "coindesk", "url": "https://www.coindesk.com/...", "published_at": "2026-06-15T09:10:00Z"}
      ],
      "url": "https://decrypt.co/...",
      "source_count": 2,
      "first_seen": "2026-06-15T08:00:00Z",
      "last_updated": "2026-06-15T09:10:00Z",
      "materiality": "high",
      "priced_in": "PRICED_IN",
      "priced_in_basis": "BTC already +3% on the session; Polymarket MSTR-buy odds unchanged"
    }
  ],
  "window_hours": 36,
  "feeds_unavailable": ["ft", "bloomberg"],
  "run_id": "<from workflow>", "git_sha": "<from workflow>"
}
```
Carry `run_id` + `git_sha` + per-figure timestamps from the workflow (NFR7). If a required feed is down,
list it in `feeds_unavailable` (loud, per NFR6) — never silently drop.

## Velocity (optional)

For narrative *velocity* only (rate of mention growth), `mention_velocity.py` exists under
`stocks-trend-screener/` but is a **stock tool** — it needs a crypto-universe adaptation (BTC/ETH/MSTR/ETF
tickers, crypto outlets) before use here. Do not run it on the crypto universe as-is.

## Citation rule — no URL = not a source

Every external claim (news event, data point, quote, analysis) MUST include ALL THREE:
1. **Full URL** fetched: `https://exact-page-url` (specific article, not homepage or search page)
2. **Date** (ISO): `YYYY-MM-DD` (publication or as-of date)
3. **Verbatim quote**: exact words from the page, copied not paraphrased

Format in output: `[TIER] https://exact-url (YYYY-MM-DD) — "verbatim quote"`

**Never write:**
- Source name alone (`CoinDesk`, `Bloomberg`) — without URL it is hallucination bait
- A quote without its URL
- A URL without a date
- Anything paraphrased from memory without a prior web_fetch call

**If fetch failed:** `[FETCH FAILED: https://...] — not counted toward minimum`
**If < 2 real sources:** output `INSUFFICIENT_DATA — do not guess`

## Fit

Phase-1 Gather seat in `research-crypto-market`. Feeds the consolidate step the deduped event list; the panel
(analyst-crypto, derivatives, Druckenmiller, Alden, Hunt, Napier) reads the brief, not this seat directly.

> Educational, not advice. Events are context + disconfirmation, never a trigger.
