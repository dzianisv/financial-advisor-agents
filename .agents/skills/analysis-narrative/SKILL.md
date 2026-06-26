---
name: analysis-narrative
description: "Analyst lens for crypto narrative and news catalysts — ETF flow news, regulatory events, institutional adoption, corporate treasury buys, protocol upgrades, macro policy statements, exchange events. Classifies events as PRICED_IN vs ACTIONABLE_CONTEXT vs CATALYST. Use when asked \"what news is moving crypto\", \"is this priced in\", \"narrative catalysts\", \"regulatory risk\", \"institutional news\", \"what changed this week\", \"MicroStrategy/BlackRock/ETF news\", \"is this a real catalyst or noise\". Depends on [[narrative-news]] for raw events; this skill interprets their market impact. News is lagging/reflexive — context and disconfirmation, never a primary trigger. Educational, not advice."
license: MIT
compatibility: opencode
metadata:
  audience: crypto-allocators-and-treasury-managers
  domain: crypto-narrative-analysis
  role: narrative-and-news-catalyst-lens
  source: "Market microstructure + reflexivity theory (distilled 2026-06)"
---

# Analyst: The Crypto Narrative & News Catalyst Lens

Apply a **reflexivity-first classification framework** to *how narrative and news events move crypto prices*.
This skill is the **interpretation layer** over raw events; raw event fetching lives in `[[narrative-news]]`
and `[[read-news]]`. The core analytical discipline: **news is lagging, not leading** — classify the
information state of the market before assigning any market impact, and always ask what would *disconfirm*
the dominant narrative before assigning a posture.

## The unifying worldview

Narratives move markets but they are **reflexive** — by the time something is news, much of the move has
already happened. The analytical question is never "is this good news?" but **"how much of this is already in
the price, and what would *surprise* the market?"** A known catalyst (scheduled ETF decision, FOMC meeting,
halving) is priced in; its absence or reversal is the actual tradeable event. Unknown catalysts (surprise
treasury buy, sudden regulatory clarity, exchange hack) are the only pure informational shocks.

The framework: **classify FIRST** (priced_in vs new) → **measure source_count** (how many outlets ≈ how
priced_in) → **ask what would DISCONFIRM** the narrative. A bullish narrative that cannot be disconfirmed is
religion, not analysis. ETF flows are the one near-real-time institutional demand signal that can cut through
narrative noise: if narrative is bullish but flows are negative, the market is telling a different story.

## Core mental models (the load-bearing ones)

1. **Priced-in vs new.** If >3 top-tier sources (Bloomberg, Reuters, WSJ, FT, CoinDesk) covered an event
   >24 h ago, assume **priced in**. The surprise is the tradeable unit — the absence of an expected catalyst
   (e.g., ETF approval delayed) is often the actual event.
2. **Hard events > soft events.** ETF flow data (farside.co.uk), SEC/CFTC filings, exchange hacks, treasury
   purchases = **hard** (verifiable, timestamped, primary source). "Analyst says BTC to $200k" = **soft
   noise**. Weight only hard events in classification; log soft events as sentiment, not catalyst.
3. **Regulatory news: jurisdiction and clarity class.** Classify as **CLARITY** (bullish — rules known,
   industry can comply), **AMBIGUITY** (neutral — guidance unclear, enforcement risk open), or
   **RESTRICTION** (bearish — ban, enforcement action, hostile legislation). Specify jurisdiction: US
   SEC/CFTC news moves global markets; obscure-jurisdiction news rarely does.
4. **ETF flow narrative check.** Weekly cumulative flow trend is the institutional demand story in
   near-real-time. Primary fetch: ETF flow headlines returned by `read_news.ts` (FT, Bloomberg, CoinDesk).
   Raw daily table: farside.co.uk/btc/ — requires WebFetch/Chrome-CDP (403 to plain curl). If unavailable,
   derive direction from news headline tone and mark `etf_flow_alignment: UNKNOWN`.
   Rule: **narrative bullish + outflows = divergence, bearish signal**; narrative bearish + inflows =
   divergence, bullish signal. Alignment reinforces; divergence warns.
5. **Corporate treasury buys (MicroStrategy, Metaplanet, etc.).** Pattern is **immediate spike then
   digestion**. Watch for "buy the rumor, sell the fact" — if an announcement was telegraphed (public HODL
   strategy, ATM offering filed), classify as priced_in; unannounced first-time buyers are new_catalyst.
6. **Protocol/network events (halving, major upgrade, fork).** Long public lead time = mostly priced in by
   announcement; check social volume via CoinGecko trending (keyless proxy — see `[[read-news]]`
   for curl command) for residual retail FOMO as execution date nears. LunarCrush/Santiment require paid
   keys — use CoinGecko trending as the keyless alternative.
   Post-event "nothing happened" = priced_in_confirmed; post-event "technical issue" = new_catalyst (bearish).
7. **Disconfirmation discipline.** For every bullish narrative, state explicitly what would prove it wrong.
   Narratives that cannot be disconfirmed are **religion, not analysis** — flag and discount them.

## How to apply the lens (decision procedure)

1. **Fetch raw events — run `read_news.ts` first.** This is the single entry point for all news sources
   (CoinDesk, Decrypt, CoinTelegraph, The Block, Bitcoin Magazine, Coinbase blog, FT, WSJ, Bloomberg).
   Full source list, supplementary curl commands (Google News RSS, SEC EDGAR, CoinGecko trending), and
   the ETF-flow fetch workaround all live in **`[[read-news]]`** — read that skill for details.
   ```bash
   bun .agents/skills/read-news/scripts/read_news.ts \
     --db .db/news.db --days 5 \
     --query "bitcoin BTC ETF regulation treasury strategy"
   # Returns deduped events ranked by query. ~270 articles across 9 feeds. Keyless, no API key needed.
   # For targeted search: append Google News RSS (see read-news skill)
   # For hard regulatory events: SEC EDGAR endpoint (see read-news skill)
   ```
2. **Classify each event.** For every event assign:
   - `PRICED_IN` — covered >24 h ago by >3 top-tier outlets, or scheduled/expected event that occurred as anticipated.
   - `ACTIONABLE_CONTEXT` — known background factor (regulatory environment, macro posture) that sets the
     range of outcomes but is not itself a trigger.
   - `NEW_CATALYST` — surprise, unannounced, or primary-source-only (≤1 major outlet, <24 h old).
   - Record `source_count` (number of top-tier outlets) and a one-line `market_impact`.
3. **Identify the dominant narrative of the week** (1 sentence). The narrative is the story the market is
   telling itself — it may be different from the factual summary of events.
4. **Check ETF flow reality vs narrative.** `read_news.ts` events already surface ETF flow headlines
   (e.g. *"Bitcoin ETF outflow pain eases"*) — classify these as `HARD` if the source is primary
   (Bloomberg/FT citing farside data). For the raw daily table: farside.co.uk/btc/ requires
   WebFetch/Chrome-CDP (Cloudflare blocks plain curl). State `etf_flow_alignment` as `ALIGNED`,
   `DIVERGENT`, or `UNKNOWN` if the farside table can't be fetched.
5. **State the disconfirmation condition** for the top narrative. What single event or data point would
   falsify it? If none can be stated, flag the narrative as **unfalsifiable** and discount it.
6. **Assign narrative posture:**
   - `BULLISH_NARRATIVE` / `NEUTRAL` / `BEARISH_NARRATIVE`
   - Momentum: `strengthening` / `weakening` / `stable`
   - Confidence: `high` (hard events, flow alignment) / `medium` (mixed) / `low` (soft events only, divergence)

## Routing table

| Question is about… | Action |
|---|---|
| Raw event fetch, news DB, latest headlines | `[[narrative-news]]` / `[[read-news]]` |
| "Is this priced in?" / classification of a specific event | Apply mental model 1 (source_count + age) |
| ETF flows, institutional demand trend, BlackRock/Fidelity | Mental model 4; headlines via `read_news.ts`; raw table via WebFetch farside.co.uk/btc/ (CDP only — see `[[read-news]]`) |
| Regulatory news (SEC, CFTC, MiCA, Asia) | Mental model 3 (jurisdiction + clarity class) |
| Corporate treasury / MicroStrategy / Metaplanet | Mental model 5 (rumor vs fact, telegraphed vs surprise) |
| Halving, protocol upgrade, fork | Mental model 6 (lead time → priced_in check, social volume) |
| Macro policy (FOMC, CPI, dollar) | `[[analyst-crypto]]` → liquidity governor; here note only direct crypto narrative overlap |
| Sentiment vs narrative divergence | Mental model 4 (flow check) + mental model 7 (disconfirmation) |
| "What changed this week?" summary | Steps 1–6 full run; output the full contract block |

## Output contract

Structured output for every full run:

```
events: [
  {
    title: string,
    classification: PRICED_IN | ACTIONABLE_CONTEXT | NEW_CATALYST,
    source_count: int,           # top-tier outlets covering it
    market_impact: string,       # one line, hard events only
    url: string,                 # full https:// URL of primary source article
    published_at: "YYYY-MM-DDThh:mm:ssZ"  # publication or as-of datetime
  },
  ...
]
dominant_narrative: string       # 1 sentence
etf_flow_alignment: ALIGNED | DIVERGENT | UNKNOWN
  flow_detail: string            # e.g. "+$312M weekly net inflow vs bullish narrative → ALIGNED"
disconfirmation_condition: string  # what would falsify the dominant narrative
narrative_posture: BULLISH_NARRATIVE | NEUTRAL | BEARISH_NARRATIVE
  momentum: strengthening | weakening | stable
  confidence: high | medium | low
```

No buy/sell call. Classification only. Soft events logged but not weighted in `market_impact`.

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

## Done when

The analysis (1) classifies **every fetched event** as PRICED_IN / ACTIONABLE_CONTEXT / NEW_CATALYST with
`source_count`, (2) states the **dominant narrative** in one sentence, (3) checks **ETF flow alignment or
divergence** against that narrative, (4) provides a **falsifiable disconfirmation condition** for the top
narrative (or flags it as unfalsifiable), and (5) assigns a **narrative posture + momentum + confidence**
grounded only in hard events and flow data — not analyst projections or social hype.
