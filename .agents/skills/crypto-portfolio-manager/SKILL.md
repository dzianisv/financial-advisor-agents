---
name: crypto-portfolio-manager
description: "Manages the crypto portfolio — runs analysis on every token in the universe (BTC/ETH/SOL/UNI/HYPE/AAVE/LINK) and outputs a BUY/SELL/HOLD decision per token. Run on demand or via /loop. Educational, not advice."
license: MIT
compatibility: opencode
metadata:
  audience: crypto-allocators
  domain: crypto-portfolio-management
  role: portfolio-manager
---

# Crypto Portfolio Manager

Analyze every token in the universe **sequentially** → decide BUY/SELL/HOLD per token → print the signal table.

> Educational analysis, not financial advice. No leverage. Ever.

## Quickstart

### Default daily run
```
Run the crypto portfolio manager
```
The skill analyzes the default token universe, pulls live TradingView data, runs a 5-seat quorum per token, and prints the full 3-block report (signal table + plain-English verdicts + ranked news sources). **Attach a TradingView screenshot for each token.**

### Custom token set
```
Run the crypto portfolio manager on: TON, PUMP, JUP, HYPE
```

### Full prompt (copy-paste for any session)
```
Invoke the crypto-portfolio-manager skill. Token universe for this run: [TOKEN1, TOKEN2, ...].
Follow all skill instructions:
- chart_get_state → dedup indicators → set_symbol → D OHLCV (365 summary + 210 bars) → study values → W OHLCV → capture_screenshot
- Compute MAs via .agents/skills/crypto-portfolio-manager/scripts/indicators.py
- Run 5-seat quorum inline (on-chain, sentiment, macro, order-flow, narrative)
- Narrative seat: web-fetch ≥3 sources, rank T1/T2/T3, quote exact sentences
- Print 3-block report: signal table | plain-English verdicts | news sources
- Attach TradingView screenshot for each token in the reply
Educational, not financial advice.
```

### Scheduling (continuous)
```
/loop interval=6h    ← re-runs every 6 hours, resumes from last pending todo
/stop                ← cancel the loop
```

---

## Token universe

BTC, ETH, SOL, UNI, HYPE, AAVE, LINK — edit this list to add/remove tokens.

---

## Hard constraints — read before running (these dictate the whole design)

1. **TradingView MCP tools live ONLY in the orchestrator (you).** Subagents spawned via the task tool get a fresh toolset with **no** `tradingview-*` tools — verified. So **YOU** must pull every chart datum yourself. Never tell a subagent to "pull TradingView data" — it cannot. Subagents may only *receive* an already-assembled data package and reason over it (they can still web-fetch F&G / on-chain).
2. **The chart is a single shared symbol slot.** `chart_set_symbol` changes the one global chart, so two tokens cannot be pulled at once. **Therefore the data loop is strictly sequential, one token at a time.** Track progress in the `todos` table so a `/loop` or an interrupted run resumes cleanly.
3. **Read every indicator TradingView can give from TradingView — don't recompute it.** `data_get_study_values` returns RSI(14), Bollinger(20,2), MACD(12,26,9) and Volume correctly at their standard lengths. Use those values verbatim. The **only** gap is moving averages: `chart_manage_indicator` ignores the MA `length` input (an added MA exposes `inputs:[]` and stays stuck at a short default ≈ price; verified BTC read $64,540 when SMA200 was ~$76,600) and has no `update` action. So EMA20 / SMA50 / SMA200 / 200-week-MA — and only those — are computed by `scripts/indicators.py` from the MCP's **own** returned closes (plain rolling means / EWMs; the data source stays 100% TradingView).

TradingView symbol mapping: `BINANCE:{TOKEN}USDT` (e.g. `BINANCE:BTCUSDT`). If a symbol is missing on Binance, try `OKX:{TOKEN}USDT`.

---

## Step 0 — Seed the todo list (one row per token)

```sql
INSERT INTO todos (id, title, description) VALUES
 ('tok-BTC','Analyzing BTC','Pull TradingView D/W OHLCV+studies, compute pkg, run 5-seat quorum, decide signal'),
 ('tok-ETH','Analyzing ETH','idem'), ('tok-SOL','Analyzing SOL','idem'),
 ('tok-UNI','Analyzing UNI','idem'), ('tok-HYPE','Analyzing HYPE','idem'),
 ('tok-AAVE','Analyzing AAVE','idem'), ('tok-LINK','Analyzing LINK','idem');
```

Create the verdict tracker once:

```sql
CREATE TABLE IF NOT EXISTS token_analysis (
  symbol TEXT PRIMARY KEY, quorum_verdict TEXT, dominant_zone TEXT,
  seats_bull INTEGER, seats_bear INTEGER, key_support REAL, key_resistance REAL,
  confidence TEXT, signal TEXT, status TEXT DEFAULT 'pending');
```

---

## Step 1 — Sequential per-token loop (orchestrator does this; do NOT parallelize the data pull)

Pick the next `pending` todo and `UPDATE todos SET status='in_progress'`. Then, for that token:

**1a. Pull TradingView data (MCP, in this session):**

First, call `tradingview-chart_get_state` and inspect the `studies` list.  
**Only add an indicator if its name is NOT already present** — adding a duplicate pushes a second identical series onto the chart, inflates context, and produces duplicate rows in `data_get_study_values`. Use `chart_manage_indicator action=remove` on the extra entity_id if duplicates already exist.

Required studies (add only if absent): **Relative Strength Index**, **Bollinger Bands**, **MACD**. Do NOT add length-N EMAs — the length input is ignored (constraint 3). Volume is always present.

```
tradingview-chart_get_state                                → inspect studies list; deduplicate before proceeding
tradingview-chart_set_symbol     symbol="BINANCE:{TOKEN}USDT"
tradingview-chart_set_timeframe  timeframe="D"
tradingview-data_get_ohlcv       count=365 summary=true   → 52w high/low + avg volume
tradingview-data_get_ohlcv       count=210 summary=false  → >=200 daily closes (for SMA200)
tradingview-data_get_study_values                          → RSI(14), BB(20,2), MACD, Volume (one of each)
tradingview-chart_set_timeframe  timeframe="W"
tradingview-data_get_ohlcv       count=210 summary=false  → weekly closes (for 200-week MA)
tradingview-chart_set_timeframe  timeframe="D"             → reset to daily
tradingview-capture_screenshot                             → **REQUIRED** attach this image in the reply for this token
```

**1b. Read the indicators from TradingView; compute only the moving averages.** From `data_get_study_values` take RSI(14), Bollinger(20,2), MACD line/signal/hist, Volume — verbatim, no recompute. From the daily `summary=true` pull take 52w high/low + avg volume. Then fill the MA gap (computed MAs match TradingView's own values):
```bash
/Users/engineer/.venv/bin/python3 .agents/skills/crypto-portfolio-manager/scripts/indicators.py /tmp/{TOKEN}.json
```
Helper input: `{"symbol","price","daily_closes":[...],"weekly_closes":[...]}`. Helper output: EMA20, SMA50, SMA200, 200-week MA, and the death cross (classic SMA50/SMA200, exact). Nothing else — it does not recompute RSI/BB/MACD.

**1c. Assemble the data package** by merging the TradingView study values (RSI, BB, MACD, Volume, 52w hi/lo) with the helper's moving-average block: price, %from-52wh, EMA20, SMA50, SMA200, death_cross, RSI, MACD line/signal/hist, BB upper/mid/lower + position, volume vs 30d avg, 200-week MA + %vs it.

**1d. Run the 5-seat quorum on the package.** Either reason through the 5 seats inline, or spawn the five `analysis-*` seat subagents **in parallel** (on-chain, sentiment, macro, order-flow, narrative) with the package **injected** — seats per token may be parallel because they share nothing; only the *data pull* must be serial. Each seat returns: zone, posture (BULLISH|NEUTRAL|BEARISH), confidence, 1-line bull, 1-line bear, invalidation.

**Narrative seat — mandatory sourcing protocol.** The narrative seat MUST web-fetch at least 3 recent articles/sources before forming its posture. For every source used:
1. **Fetch it** (web-fetch the URL or the feed).
2. **Quote the specific sentence or data point** that informed the verdict.
3. **Rank sources by signal quality** using this rubric:
   - **Tier 1 — Primary signal** (ranks first): on-chain data with timestamps, exchange/ETF flow reports with actual numbers, regulatory filings, protocol announcements. Weight: 3×.
   - **Tier 2 — Credible context** (ranks second): Seeking Alpha deep-dives, Bloomberg/Reuters/FT/WSJ analysis with named sources, CoinDesk/TheBlock with on-chain citations. Weight: 2×.
   - **Tier 3 — Noise / sentiment gauge** (ranks last): social media, unnamed "analysts say", vague macro opinions, recycled press releases. Weight: 0.5×. These inform sentiment only, never the posture verdict.
4. **Show the reasoning** for each rank: one sentence explaining why this source is Tier 1/2/3 for this token at this moment (e.g. "T1: Glassnode shows 14-day ETF outflow of $3.8B — hard number, directly moves price").
5. **State what would have changed the verdict** if the evidence were reversed (invalidation anchor).

Narrative seat output format (inline, per token):
```
NARRATIVE — {TOKEN}
Posture: BULLISH | NEUTRAL | BEARISH
Sources used (ranked):
  [T1] <title or URL> — "<exact quote>" → why T1: <one sentence>
  [T2] <title or URL> — "<exact quote>" → why T2: <one sentence>
  [T3] <title or URL> — "<exact quote>" → why T3: <one sentence>
Bull: <1-line>
Bear: <1-line>
Invalidation: <what reverses this verdict>
```

**1e. Aggregate into the compact verdict and persist:**
```json
{"symbol":"BTC","quorum_verdict":"BULLISH|SPLIT|BEARISH|UNCERTAIN",
 "dominant_zone":"DEEP_VALUE|FAIR_VALUE|ELEVATED|EXTREME|UNKNOWN",
 "seats_bull":3,"seats_bear":2,"key_support":60000,"key_resistance":66000,"confidence":"HIGH|MED|LOW"}
```
```sql
UPDATE token_analysis SET quorum_verdict=?, dominant_zone=?, seats_bull=?, seats_bear=?,
  key_support=?, key_resistance=?, confidence=?, signal=?, status='done' WHERE symbol=?;
UPDATE todos SET status='done' WHERE id='tok-{TOKEN}';
```

**1f. Repeat** for the next `pending` todo until none remain.

---

## Step 2 — Decide per token

| Signal | Condition |
|---|---|
| **BUY** | `quorum_verdict = BULLISH`, seats_bull ≥ 3 |
| **BUY (small)** | `quorum_verdict = SPLIT`, `dominant_zone = DEEP_VALUE` |
| **SELL** | `quorum_verdict = BEARISH`, seats_bear ≥ 4 |
| **HOLD** | everything else |

## Step 3 — Print the full run report

Print **three blocks** in this exact order:

### Block 1 — Signal table (one-glance summary)
```
=== CRYPTO PORTFOLIO RUN — {timestamp} ===   (data: TradingView MCP)

Token | Signal      | Zone       | Quorum | Bulls/Bears
------|-------------|------------|--------|------------
BTC   | HOLD        | FAIR_VALUE | SPLIT  | 2 / 2
ETH   | BUY (small) | DEEP_VALUE | SPLIT  | 1 / 2
SOL   | BUY (small) | DEEP_VALUE | SPLIT  | 3 / 1
...
```

### Block 2 — Plain-English verdict per token
For every token write 3–5 sentences a non-expert can understand. Cover:
- **Why this signal**: what 1–2 facts drove the decision (price vs 200w MA, RSI, death cross, on-chain zone).
- **Main risk**: the single biggest thing that could make this call wrong.
- **What to watch**: the one trigger that would change the signal (e.g. "close above SMA50" → HOLD flips to BUY).

Example:
```
BTC — HOLD
BTC is down 42% from its all-time high and is sitting right on the 200-week
moving average (~$62k), the historical long-term floor. The RSI has recovered
to neutral (42.6) and the MACD is starting to turn up — early signs the
selling pressure is fading. However a death cross is active (50-day below
200-day), macro is hostile (Fed holding rates, strong dollar), and ETF flows
are still negative. Not cheap enough on-chain to force a buy, not broken
enough to sell. Watch for a daily close above the 50-day SMA ($71.9k) to
upgrade to BUY, or a weekly close below $60k to reassess.

ETH — BUY (small)
ETH has crashed 63% from its 52-week high and is now 30% below its 200-week
moving average — a level historically associated with cycle bottoms. One panel
seat is bullish (on-chain deep value), two are bearish (macro headwinds and
compressed fee revenue from L2 competition). The split verdict with extreme
undervaluation triggers the "small position" rule: start a toe-hold, don't
go large. Key risk: ETH could continue losing ground vs BTC if L2 fee erosion
persists. Upgrade to BUY if price reclaims the 200-week MA (~$2,472).
```

### Block 3 — News & sources used by the Narrative seat
List every URL the narrative seat fetched, with a one-line plain-English
summary of what it said and why it was ranked T1/T2/T3.

```
--- NEWS SOURCES ---

BTC narrative (posture: BEARISH)
  [T1] https://... — "..." — ETF outflows: hard flow numbers that directly
       move price. Ranked T1 because it is a primary data source with
       specific dollar figures.
  [T2] https://... — "..." — Bloomberg analysis of Fed rate path. Ranked T2:
       credible named-source journalism giving macro context.
  [T3] https://... — "..." — Twitter thread on BTC dominance. Ranked T3:
       social/opinion, used only to gauge retail sentiment, not to drive verdict.

ETH narrative (posture: BEARISH)
  [T1] https://...
  ...
```

Self-check before printing: every token has `status='done'` in `token_analysis`, `seats_bull + seats_bear <= 5` for each, every narrative source block has ≥3 URLs with actual links (not placeholders), and a TradingView screenshot is attached for every token.

## Running continuously

```
/loop interval=6h
/stop
```

On each loop, re-seed any `pending`/missing todos and resume the sequential pull — never start a second data pull while one is in flight.
