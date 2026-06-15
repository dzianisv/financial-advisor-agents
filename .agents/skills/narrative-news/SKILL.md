---
name: narrative-news
description: The DATA-ONLY news gather seat for the crypto panel. Orchestrates the feed-* source adapters → crypto-news-store (dedup + state) → emits ONLY the NEW or materially-updated EVENTS (not articles) for the consolidated brief, each tagged PRICED_IN vs ACTIONABLE_CONTEXT with a source_count. Use when running the crypto-panel-review gather phase, when asked "what crypto news/narrative matters right now", "any new catalysts", "narrative seat", or for the FR1.8 news/narrative category. Depends on feed-* + crypto-news-store. Data only — no opinions, no buy/sell.
license: MIT
compatibility: opencode
metadata:
  audience: crypto-research-pipeline
  domain: news-narrative-gather-seat
  role: gather-seat
---

# narrative-news (the news/narrative gather seat — FR1.8)

The **data-only** Gather seat the `crypto-panel-review` workflow calls for the REQUIRED news/narrative
category (PRD FR1.8). It produces **EVENTS, not articles, not opinions** — the panel debates; this seat
only reports what happened, deduped and state-aware.

**Depends on:** [[feed-decrypt]] · [[feed-cointelegraph]] · [[feed-coindesk]] · [[feed-theblock]] ·
[[feed-bitcoinmagazine]] · [[feed-ft]] · [[feed-wsj]] · [[feed-bloomberg]] (input adapters) →
[[crypto-news-store]] (dedup + cross-run state).

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
python3 .agents/skills/crypto-news-store/news_fetch.py \
  --db crypto/news/news.db --days 5 \
  --query "<key entities from the question: e.g. bitcoin BTC ETF Strategy MicroStrategy treasury Fed Coinbase COIN>"
# → {fetched, feeds_ok, unavailable:[...], events:[ {title, source_count, ...} ranked by relevance ]}
```
`--query` returns the hybrid (BM25 + near-dup) **relevant** events and cuts the new-since noise; omit it to
get everything new-since. Build `--query` from the asset(s)/entities in the workflow question. Per-feed
failures come back in `unavailable` (loud, NFR6) — never silently dropped.

After the brief is written, the workflow marks events surfaced so they don't repeat next run:
```bash
python3 .agents/skills/crypto-news-store/news_store.py --db crypto/news/news.db mark-surfaced --ids <ids...>
```

**Fallback (only if news_fetch fails):** call the individual [[feed-decrypt]]…/[[feed-ft]] adapters by hand,
merge their `{source,url,title,published_at,summary,...}` records into one JSON, then
`news_store.py ingest --json records.json` and `query`/`new-since` as above.

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
      "sources": ["decrypt", "coindesk"],
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
`trend-stock-research/` but is a **stock tool** — it needs a crypto-universe adaptation (BTC/ETH/MSTR/ETF
tickers, crypto outlets) before use here. Do not run it on the crypto universe as-is.

## Fit

Phase-1 Gather seat in `crypto-panel-review`. Feeds the consolidate step the deduped event list; the panel
(analyst-crypto, derivatives, Druckenmiller, Alden, Hunt, Napier) reads the brief, not this seat directly.

> Educational, not advice. Events are context + disconfirmation, never a trigger.
