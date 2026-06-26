---
name: stocks-advisor
description: "Portfolio-agnostic equity advisor. Analyzes a user-supplied ticker list, a Google Sheet of holdings, OR discovers stocks via current market themes (AI supply chain, robotics, energy transition, defense, fintech) discovered LIVE via web_fetch. Runs a 5-seat analyst panel per stock (fundamental / technical / narrative-macro / sentiment-positioning / smart-money-institutional-flows) in parallel subagents. When holdings are provided (Google Sheet URL), outputs HOLD/ADD/TRIM/EXIT per position with tax harvest table and cash deployment plan. When discovering or analyzing a watchlist, outputs entry zone, bar-close trigger, market-based stop, conviction, theme tag. Triggers: \"run the stock panel\", \"analyze these stocks: [list]\", \"review my portfolio: [sheet URL]\", \"find stocks in the AI supply chain theme\", \"what stocks should I look at this week\", \"find entry points for my watchlist\". Individual stocks only. Educational, not advice."
license: MIT
compatibility: opencode
metadata:
  audience: equity-allocators
  domain: equity-portfolio-management
  role: portfolio-manager
  source: "Architecture mirrors crypto-advisor (2026); seats grounded in fundamental-analysis + analyst-technical-analysis (Bernstein 2009)"
---

# Stocks Portfolio Manager

Analyze a set of individual stocks **one at a time** → run a 5-seat analyst panel per stock → output a
concrete **entry plan** (zone + trigger + stop) and a BUY / WATCH / SKIP decision. The stock list is
either supplied by the user or **discovered live** from the market themes currently driving institutional
flows. Nothing is hardcoded — no positions, no themes.

> Educational analysis, not financial advice. Single stocks are satellites; the index is the bar.

## The job is the ENTRY, not the company

The primary question this skill answers is **not** "is this a good company" — it is **"is NOW a good time
to enter, and where exactly?"** A great company at the wrong entry is still a wrong trade. Every output
must end with a price zone, a bar-close trigger, and a market-based stop, or it is incomplete.

## Quickstart

### Review your existing portfolio (Google Sheet)
```
Invoke the stocks-advisor skill.
Holdings: https://docs.google.com/spreadsheets/d/1aunLbpNGo85WqrMHiIsy6nFUija4Lnjot-rIhE-pGU8/edit?gid=1914937017
Tab: IBKR
Cash to deploy: $26,320
```
The skill reads your positions from the sheet (ticker, qty, cost basis), then runs the 5-seat panel
per position. Verdicts become **HOLD / ADD / TRIM / EXIT** (not BUY/WATCH/SKIP) because cost basis
and P&L context are known. Output includes a tax-harvest table and cash deployment plan.

### Analyze a supplied watchlist
```
Run stocks-advisor on: AVGO, MRVL, VRT, CEG
```

### Discover stocks within a theme, then analyze
```
Find stocks in the AI supply chain theme and run the stock panel
```
The skill first **discovers the theme's constituents live** (web_fetch — §Theme discovery), then runs the
full per-stock panel on the discovered names.

### Full prompt (copy-paste for any session)
```
Invoke the stocks-advisor skill.
Tickers for this run: [TICKER1, TICKER2, ...]   (or: "discover via theme: AI supply chain")
Follow all skill instructions:
- Per ticker, sequentially: chart_get_state → dedup studies → set_symbol (NASDAQ:/NYSE:) →
  D OHLCV (365 summary + 250 bars) → study values → W OHLCV → capture_screenshot
- Run scripts/fundamentals.py per ticker; inject its JSON into the data package
- Spawn the 5 seats in PARALLEL subagents (fundamental / technical / narrative / sentiment / smart-money),
  data package injected — subagents NEVER call TradingView or yfinance
- Narrative seat: read_news.ts (--source ft,wsj) for event discovery + feed scripts for verbatim citation + web_fetch Bloomberg/Reuters, classify theme phase
- Smart-money seat: web_fetch openinsider/13f.info/EDGAR/capitoltrades per ticker for disclosed flows
- Apply the verdict decision table → BUY / WATCH / SKIP with entry zone + trigger + stop
- Print per-stock blocks + the final signal table with the theme map
Educational, not financial advice.
```

---

## Hard constraints — read before running (these dictate the whole design)

1. **TradingView MCP tools live ONLY in the orchestrator (you).** Subagents spawned via the task tool get
   a fresh toolset with **no** `tradingview-*` tools and **no** yfinance — verified for crypto-PM, same
   runtime here. So **YOU** pull every chart datum and run `fundamentals.py` yourself, assemble one data
   package per stock, and **inject** it into each seat. Never tell a subagent to "pull TradingView data"
   or "run yfinance" — it cannot. Subagents may only *receive* the package and reason; the narrative seat
   may still `web_fetch` news.
2. **The chart is a single shared symbol slot.** `chart_set_symbol` mutates the one global chart, so two
   tickers cannot be pulled at once. **The data pull is strictly sequential, one ticker at a time.** Track
   progress in the `todos` table so an interrupted run resumes cleanly.
3. **Sequential data pull, parallel analysis.** The TradingView pull must be serial (single slot); the
   five seats per stock share nothing, so spawn them **in parallel** once the package is assembled.
4. **TradingView symbol mapping:** use `NASDAQ:{TICKER}` or `NYSE:{TICKER}` for US stocks. If the exchange
   lookup fails, fall back to bare `{TICKER}`. When unsure of the exchange, call `tradingview-symbol_search`
   to resolve it before `chart_set_symbol`.
5. **Read indicators from TradingView; read fundamentals + MA levels from yfinance.**
   `data_get_study_values` returns RSI(14), Bollinger(20,2), MACD(12,26,9) and Volume at standard lengths —
   use them verbatim, do not recompute. Price levels (`ma50`, `ma200`, `52w_high/low`, `dd_from_52wh`,
   `vs_200d_ma`) and all fundamentals come from `scripts/fundamentals.py` (yfinance). This sidesteps the
   TradingView MA-length bug (its `chart_manage_indicator` ignores the MA `length` input) entirely.
6. **This skill analyzes INDIVIDUAL STOCKS only.** ETF / sleeve allocation decisions belong in
   `tradfi-portfolio-manager`. The portfolio-level synthesis across the analyzed names is the
   `stock-chair` skill's job (§Step 4).

---

## The honest base rate (state this every run)

From the `fundamental-analysis` skill, on full-history backtests of the investable stock-selection methods
vs SPY: **only 1 of 10 methods beat SPY on return (momentum); 0 of 10 beat it on Sharpe — including the ETF
that implements Morningstar's own stock-picking.** Single-stock selection is a low-base-rate bet. So:
- Single names are **satellites**, the index is the **core and the bar**.
- A passing panel is a **hypothesis**, not validated alpha. TA setups are **hypothesis generation** —
  validate any mechanical rule with `strategy-discovery-backtest` (full costs, walk-forward) before
  risking real capital.
- yfinance fundamentals are **point-in-time UNSAFE** (today's numbers) — fine for *current* entry
  analysis, never for backtesting a screen.

---

## Theme discovery — discovered live, never hardcoded

Market narratives rotate; what leads flows this quarter may fade next. **Do not hardcode a theme list.**
When the user asks to "find stocks in theme X" or "what should I look at this week", discover the live
themes and their constituents by fetching, then reading, real pages:

1. **Identify the live themes.** Pull WSJ + FT first via the **paywall-free feed scripts** (the
   `wsj.com`/`ft.com` listing pages below are bot-blocked from agent IPs — the feed scripts return real
   article URLs + a verbatim publisher teaser + date, no login needed):
   ```bash
   bun .agents/skills/read-news/scripts/feeds/wsj.ts --feed markets,business --days 5 --limit 25 --text
   bun .agents/skills/read-news/scripts/feeds/ft.ts  --section markets,companies,global-economy --days 5 --limit 25 --text
   ```
   Then `web_fetch` 1–2 of the **non-paywalled** listings for breadth:
   - `https://www.bloomberg.com/markets`
   - `https://finance.yahoo.com/topic/latest-news/` (sector/thematic trend listings)
2. **Map names to themes.** For each candidate ticker, tag it with one theme bucket:
   `AI_SUPPLY_CHAIN | ROBOTICS | ENERGY | DEFENSE | FINTECH | HEALTHCARE | OTHER`. The buckets are a
   classification convention, not a fixed universe — add a bucket if the evidence supports a new one.
3. **Anti-hallucination rule (same as the narrative seat):** you may only name a theme or a constituent
   you found this run in a page you actually `web_fetch`ed **or in feed-script output you actually ran**
   (`feeds/wsj.ts`/`feeds/ft.ts` print real URLs + verbatim teasers — those count as fetched). No fetched
   URL / no feed record = not a theme. Never list a "current narrative" from memory — narratives are
   exactly the thing that goes stale.

If the user supplies an explicit ticker list, skip discovery and analyze that list (still tag each name
with a theme in the output).

---

## Step -1 — Load prior memory (before anything else)

Before seeding the todo list, pull prior verdicts and user preferences for this run's tickers:

```bash
bun .agents/skills/portfolio-memory/recall.ts --desk stocks \
  --tickers "AVGO MRVL COIN PYPL"
```

Inject the printed `<prior_context>` block into EVERY seat's data package. It has two parts: the
**canonical** current stance per ticker (evergreen — the latest verdict, which physically overwrote
any older one, so you can never follow a stale call), and **episodic** dated history newest-first.
This is how the agent remembers: COIN=HOLD (crypto bullish), prior entry zones, previous theme
classifications, user preferences like "RSP over VOO". If there is no prior memory the script prints
`[no prior memory for this run]` — continue normally. See `portfolio-memory` skill for the model.

---

## Step 0 — Load holdings from Google Sheet (if provided)

If the user passed a Google Sheet URL, read the holdings before seeding the todo list.
Use the `gws-sheets-read` skill (https://www.skills.sh/googleworkspace/cli/gws-sheets-read):

```bash
gws sheets +read \
  --spreadsheet <ID extracted from URL> \
  --range "<Tab>!A:E"
```

Extract the spreadsheet ID from the URL (the long alphanumeric string between `/d/` and `/edit`).
Parse the response into a holdings list: `[{ticker, qty, cost_basis, market_value, pnl_pct, cash}]`.
- Rows where Type = "Cash" → set as `cash_to_deploy`
- Rows where Type = "Stock" → build the ticker universe for this run

When holdings are loaded:
- Add `cost_basis`, `qty`, `pnl_pct`, `dd_from_cost` to each ticker's data package
- Seat verdicts shift to **HOLD / ADD / TRIM / EXIT** (not BUY/WATCH/SKIP)
- After the signal table, output a **tax-harvest section** (positions with largest unrealized losses)
  and a **cash deployment section** (where to put `cash_to_deploy`)

If no sheet URL was provided, skip this step and use the user-supplied ticker list or theme discovery.

---

## Step 1 — Seed the todo list (one row per ticker)

```sql
INSERT INTO todos (id, title, description) VALUES
 ('stk-AVGO', 'Analyzing AVGO', 'Pull TradingView D/W + studies, run fundamentals.py, 5-seat panel, decide'),
 ('stk-MRVL', 'Analyzing MRVL', 'idem'),
 ('stk-VRT',  'Analyzing VRT',  'idem');
-- one row per ticker in this run's list
```

Create the verdict tracker once:

```sql
CREATE TABLE IF NOT EXISTS stock_analysis (
  symbol TEXT PRIMARY KEY, company TEXT, theme TEXT, theme_phase TEXT,
  fundamental TEXT, technical TEXT, narrative TEXT, sentiment TEXT, smartmoney TEXT,
  decision TEXT, entry_low REAL, entry_high REAL, trigger TEXT,
  stop REAL, target REAL, conviction INTEGER, status TEXT DEFAULT 'pending');
```

```bash
# Back-compat: pre-existing 4-seat tables lack the smartmoney column; idempotent — error suppressed if column already exists
sqlite3 "$DB" 'ALTER TABLE stock_analysis ADD COLUMN smartmoney TEXT;' 2>/dev/null || true
```

---

## Step 1 — Sequential per-stock loop (orchestrator only; do NOT parallelize the data pull)

Pick the next `pending` todo and `UPDATE todos SET status='in_progress'`. Then, for that ticker:

**1a. Pull TradingView data (MCP, in this session):**

First call `tradingview-chart_get_state` and inspect the `studies` list. **Only add a study if its name is
NOT already present** — a duplicate pushes a second identical series, inflates context, and produces
duplicate rows. Required studies (add only if absent): **Relative Strength Index**, **Bollinger Bands**,
**MACD**. Volume is always present. Do NOT add MA studies (length input is ignored — use yfinance MAs).

```
tradingview-symbol_search    query="{TICKER}"          → resolve NASDAQ:/NYSE: prefix if unknown
tradingview-chart_get_state                            → inspect studies; dedup before proceeding
tradingview-chart_set_symbol   symbol="NASDAQ:{TICKER}" (or NYSE:, or bare {TICKER} on failure)
tradingview-chart_set_timeframe timeframe="D"
tradingview-data_get_ohlcv     count=365 summary=true  → 52w structure + avg volume
tradingview-data_get_ohlcv     count=250 summary=false → daily closes for the technical seat
tradingview-data_get_study_values                       → RSI(14), BB(20,2), MACD, Volume (one each)
tradingview-chart_set_timeframe timeframe="W"
tradingview-data_get_ohlcv     count=210 summary=false → weekly closes (long-term structure)
tradingview-chart_set_timeframe timeframe="D"          → reset to daily
tradingview-capture_screenshot                          → save; then `view` the file_path to embed inline
```

**1b. Pull fundamentals (yfinance helper, in this session):**
```bash
echo '{"symbol":"{TICKER}","period":"1y"}' > .agents/skills/stocks-advisor/scripts/{TICKER}.json
/Users/engineer/.venv/bin/python3 .agents/skills/stocks-advisor/scripts/fundamentals.py \
  .agents/skills/stocks-advisor/scripts/{TICKER}.json
```
The helper writes `{TICKER}.json.out.json` with: price, 52w_high/low, ma50, ma200, forward_pe, trailing_pe,
peg_ratio, revenue_growth, earnings_growth, gross_margin, operating_margin, fcf, market_cap, fcf_yield, roe,
short_percent, institutional_pct, recommendation_mean, analyst_count, dd_from_52wh, vs_200d_ma, vs_50d_ma.
Any field yfinance lacks is `null` — never fill a null with a guess.

**1c. Assemble the data package** by merging the TradingView study values (RSI, BB, MACD, Volume, 52w hi/lo
from `summary=true`, the daily/weekly close arrays) with the full `fundamentals.py` JSON. This single
package is what every seat receives — seats add nothing to it except the narrative seat's fetched news.

**1d. Spawn the 5 seats IN PARALLEL** (task subagents), each with the **same** package injected. Each seat
reads ONE lens and returns the fixed shape below. Seats share nothing, so they run concurrently.

---

## The 5-seat panel (subagent prompts — reuse verbatim, fill the blanks)

> The data package is injected into every seat. Subagents are a **context firewall**: they reason over the
> package only and never pull MCP/yfinance data. External calls allowed: the **narrative seat** may
> web_fetch news + run paywall-free feed scripts (`feeds/wsj.ts`/`feeds/ft.ts`); the **smart-money seat**
> may web_fetch disclosed-flow sources (openinsider.com, 13f.info, EDGAR, capitoltrades.com). All other seats: injected data only.

### Seat 1 — Fundamental (grounded in `fundamental-analysis`)
```
You are the FUNDAMENTAL seat. Read ONLY this lens:
  /Users/engineer/workspace/backtest/.agents/skills/fundamental-analysis/SKILL.md
Judge ONE stock on the injected data package — do not pull any data.

DATA PACKAGE:
  <inject the full package: fundamentals.py JSON + TradingView studies>

Assess: FCF yield, forward P/E, PEG, revenue & earnings growth, gross/operating margin, ROE/ROIC proxy,
and moat quality (qualitative, from the numbers + what you know of the business model). Anchor on whether
the VALUATION leaves a margin of safety at the CURRENT price — a great business at a rich multiple is not
a fundamental BUY.

Return ONLY this shape:
  RATING: STRONG | GOOD | FAIR | POOR
  KEY METRIC: <the one number that drives the rating, e.g. "FCF yield 4.2%, fwd P/E 19, PEG 0.7">
  MOAT: <one line — durable advantage or commodity?>
  MARGIN OF SAFETY: <yes/no + one line on price vs value>
  BLIND SPOT: <one line — what fundamentals structurally cannot see here>
```

### Seat 2 — Technical (grounded in `analyst-technical-analysis`, Bernstein Set-Up→Trigger→Follow-Through)
```
You are the TECHNICAL seat. Read ONLY this lens:
  /Users/engineer/workspace/backtest/.agents/skills/analyst-technical-analysis/SKILL.md
Judge ONE stock on the injected data package + the chart description — do not pull any data.

DATA PACKAGE:
  <inject the full package: price, ma50, ma200, vs_200d_ma, RSI, BB, MACD, Volume, 52w hi/lo,
   daily & weekly close arrays, and a one-paragraph read of the screenshot>

Apply Set-Up → Trigger → Follow-Through:
1. NAME the set-up (or say there is none): e.g. base breakout, pullback-to-200d, bull-flag, range,
   momentum divergence. A pattern alone is NOT a signal.
2. Define the BAR-CLOSE TRIGGER — the exact completed-bar event that confirms (e.g. "daily close above
   $280 on above-avg volume"). No trigger = no trade.
3. Set a MARKET-BASED STOP from structure/range/MA — never an arbitrary dollar amount.
4. State follow-through: first target + risk:reward.

Return ONLY this shape:
  STATE: SETUP_NAMED | NO_SETUP | BROKEN   (BROKEN = below 200d with no base, or failed breakdown)
  SETUP: <name, or "no recognizable setup">
  TRIGGER: <bar-close event on timeframe, or "none yet — WATCH">
  STOP: <price level + basis (support / MA / range low)>
  TARGET: <price + risk:reward X:1>
  BLIND SPOT: <one line — TA is weak-evidence; this is a hypothesis, not validated alpha>
```

### Seat 3 — Narrative / Macro (theme durability + cycle phase)
```
You are the NARRATIVE/MACRO seat. Judge whether this stock rides a DURABLE theme or is noise, and where
the theme sits in its cycle. You MUST web_fetch before citing any news.

DATA PACKAGE:
  <inject the package + the theme tag assigned in discovery>

⛔ HARD RULE: call web_fetch on a real URL before citing it. No fetched URL = not a source.
A fabricated headline invalidates the whole verdict.

GET NEWS IN TWO STEPS (read_news.ts for discovery; feed scripts for citation — why: read_news.ts events
cluster multi-outlet coverage into deduplicated events but sources(json) lacks a single canonical URL
per event, so use read_news.ts for topic breadth, then pull verbatim-citeable teasers via feed scripts):
  bun .agents/skills/read-news/scripts/read_news.ts --source ft,wsj --query "<theme/ticker entities>" --days 7
  bun .agents/skills/read-news/scripts/feeds/wsj.ts --feed markets,business --query "<theme/ticker>" --days 7 --text
  bun .agents/skills/read-news/scripts/feeds/ft.ts  --section markets,companies --query "<theme/ticker>" --days 7 --text
Each feed-script record = real wsj.com/ft.com URL + verbatim publisher teaser + date. Cite as:
  [T1]/[T2] url (date) — "<teaser>" (teaser is verbatim publisher text — no paywalled body needed).
Then web_fetch ≥1 non-paywalled outlet for additional breadth:
Bloomberg (https://www.bloomberg.com/markets), Reuters (https://www.reuters.com/markets/), Yahoo Finance
topic pages. Quote verbatim — never paraphrase from memory.

Classify the theme phase:
  EARLY_CYCLE  — theme just forming, few names, skeptics dominate, flows starting
  MID_CYCLE    — theme established, broad participation, earnings confirming, not yet euphoric
  LATE_CYCLE   — consensus, every fund owns it, valuations stretched, marginal buyer thinning
  FADING       — narrative breaking down, flows reversing, story no longer moves the stock

Return ONLY this shape:
  PHASE: EARLY_CYCLE | MID_CYCLE | LATE_CYCLE | FADING
  THEME: <the durable theme this rides, or "no durable theme — idiosyncratic/noise">
  SOURCES (ranked, ≥2 real):
    [T1] https://<article-url — web_fetched, or a wsj.com/ft.com URL from the feed scripts> — "<verbatim quote or publisher teaser>" → T1 because: <one line>
    [T2] https://<article-url — web_fetched, or a wsj.com/ft.com URL from the feed scripts> — "<verbatim quote or publisher teaser>" → T2 because: <one line>
  WHY: <one line — is the theme durable and is this name a real beneficiary?>
  BLIND SPOT: <one line — news is lagging/reflexive; what this lens misreads>
If <2 real fetched sources: PHASE defaults to the technical read; write "INSUFFICIENT DATA — do not guess".
```

### Seat 4 — Sentiment / Positioning (contrarian)
```
You are the SENTIMENT/POSITIONING seat. Read the crowd's positioning as a CONTRARIAN signal — extreme
bullishness = caution; quiet accumulation with no euphoria = signal. Use the injected package only.

DATA PACKAGE:
  <inject the package: short_percent, institutional_pct, recommendation_mean, analyst_count,
   RSI, vs_200d_ma, dd_from_52wh, volume vs avg>

Read: short interest (high + rising into a base = squeeze fuel; high + falling = thesis breaking),
institutional ownership % (very high = crowded, little marginal buyer left), analyst consensus
(recommendation_mean near 1.0 with 40+ analysts = everyone already bullish = contrarian caution; mean
>2.5 = ignored/hated = contrarian interest), and RSI/extension as a froth gauge.

Return ONLY this shape:
  READ: QUIET_ACCUM | NEUTRAL | CROWDED | EXTREME
  KEY: <the one positioning fact, e.g. "rec_mean 1.3 across 45 analysts, inst 80% — fully crowded">
  CONTRARIAN TILT: <one line — does positioning support or warn against entry now?>
  BLIND SPOT: <one line — positioning can stay crowded for years in a strong trend>
```

### Seat 5 — Smart-Money / Institutional Flows (disclosed-flows)
```
You are the SMART-MONEY seat. Fetch ONLY via web_fetch — NO TradingView, NO yfinance.
Cover 4 per-ticker disclosed-flow classes for a US equity: Form 4 insider buys, 13F institutional
holders, 13D/13G activist stakes, congressional PTR buys. Skip market-implied spokes
(options/dark-pool/polymarket — not per-equity queryable at this resolution; the full
analyst-smartmoney lens covers them).

⛔ HARD RULE: web_fetch a real URL before citing any filing, holder, or transaction.
No fetched URL = not a source. Fabricated filing or transaction → verdict invalidated.
<2 fetched sources OR no signal found → output NEUTRAL + "INSUFFICIENT DATA — do not guess".

DATA PACKAGE: <inject: company name + ticker (your query inputs)>

FETCH (web_fetch each URL; stop early if signal is clear):
  Form 4: https://openinsider.com/screener?s={TICKER}   — code P only, last 30d
     ≥3 distinct insiders → ACC | 2 incl. CEO/CFO → ACC | 1 buy → NEUTRAL | sells → ignore
  13F:    https://13f.info/stock/{TICKER}  (fallback: https://www.hedgefollow.com/{TICKER})
     net adds > net trims last Q → ACC | mixed → NEUTRAL | net trims dominant → DIST
  13D:    https://efts.sec.gov/LATEST/search-index?q=%22{TICKER}%22&forms=SC+13D,SC+13G&dateRange=custom&startdt={90d_ago}
     new 13D/13G in last 90d → ACC | none → NEUTRAL
  PTR:    https://www.capitoltrades.com/trades?ticker={TICKER}&txType=buy
     ≥3 different members buying → ACC | fewer → NEUTRAL

SYNTHESIS (analyst-smartmoney verdict contract):
  ACCUMULATING if ≥2 classes ACC | DISTRIBUTING if ≥2 classes DIST | else NEUTRAL
  CONVICTION: HIGH ≥3 aligned | MED 2 aligned | LOW 1 | N/A on conflict or NEUTRAL
  Hedge-as-signal check: a 13F put or institutional put block is NOT a buy — never count as ACC.

Return ONLY:
  VERDICT:      ACCUMULATING | DISTRIBUTING | NEUTRAL
  CONVICTION:   HIGH | MED | LOW | N/A
  Form 4:       [ACC/DIST/NEUTRAL/UNAVAIL] — {one line: cluster_size or "no open-market purchases"}
  13F:          [ACC/DIST/NEUTRAL/UNAVAIL] — {one line: net adds vs trims, key fund if notable}
  13D:          [ACC/DIST/NEUTRAL/UNAVAIL] — {one line: activist + stake % or "none in 90d"}
  PTR:          [ACC/DIST/NEUTRAL/UNAVAIL] — {one line: member names + count or "none"}
  CONFIRMATION: {N classes agreeing — e.g. "2 of 4: Form4 + 13F both ACC"}
  INVALIDATION: {e.g. "Form 4 cluster sell or 13F net reduction >20% next Q flips DIST"}
  SOURCES:      [every URL actually fetched — never omit; or "INSUFFICIENT DATA"]
  NOTE: Educational only. 13F: 45-day lagged long-only. PTR: alpha contested post-STOCK Act.
```

**1e. Persist the seat verdicts and decision:**
```sql
UPDATE stock_analysis SET company=?, theme=?, theme_phase=?, fundamental=?, technical=?,
  narrative=?, sentiment=?, smartmoney=?, decision=?, entry_low=?, entry_high=?, trigger=?, stop=?, target=?,
  conviction=?, status='done' WHERE symbol=?;
UPDATE todos SET status='done' WHERE id='stk-{TICKER}';
```

**1f. Repeat** for the next `pending` todo until none remain.

**1g. Write verdict to memory:**

After each ticker completes, persist the verdict. This upserts the canonical one-line stance (the
new verdict overwrites any prior one for this ticker — supersede is enforced here, not left to the
agent) and appends to the dated episodic log:

```bash
bun .agents/skills/portfolio-memory/remember.ts \
  --desk stocks --ticker {TICKER} --verdict {BUY|ADD|WATCH|HOLD|TRIM|EXIT|SKIP} \
  --date {YYYY-MM-DD} --conviction {N} \
  --body "{cause-first thesis ≤200 chars}: fundamental {RATING} {KEY_METRIC}; technical {STATE}; narrative {PHASE}; entry {entry_low}-{entry_high}, stop {stop}. Theme {theme}."
```

---

## Step 2 — Verdict decision table (seat votes → BUY / WATCH / SKIP)

| Decision | Condition |
|---|---|
| **BUY** | Fundamental ≥ GOOD **AND** Technical = SETUP_NAMED (has a named setup + live trigger) **AND** Narrative phase ∈ {EARLY_CYCLE, MID_CYCLE} **AND** Sentiment ≠ EXTREME |
| **WATCH** | Fundamental ≥ GOOD **but** Technical = NO_SETUP (no trigger yet) — the entry is not here yet; wait for the trigger |
| **SKIP** | Fundamental = POOR **OR** Narrative phase ∈ {LATE_CYCLE, FADING} **OR** Technical = BROKEN (below 200d with no base, no setup) |

Tie-break / precedence: **SKIP dominates** (any single SKIP trigger forces SKIP). Then, between BUY and
WATCH, the **technical trigger** decides — *no trigger, no trade* (Bernstein). A strong fundamental with no
bar-close trigger is always a WATCH, never a BUY.

**Conviction (1–5):** start at 3. +1 if ≥3 seats align; +1 if EARLY_CYCLE with QUIET_ACCUM positioning;
−1 if Sentiment CROWDED; −1 if PEG > 2 or negative FCF yield; −1 if LATE_CYCLE;
+1 if Smart-money ACCUMULATING with ≥2 other seats aligned; −1 if Smart-money DISTRIBUTING (also caps
any BUY conviction at 3/5 — insiders/institutions distributing is a hard ceiling). Clamp to 1–5.

**Smart-money as confirming/conflicting input:** Smart-money (Seat 5) is NOT a primary BUY/WATCH/SKIP
driver — the verdict table above governs the decision. It is a conviction modifier: DISTRIBUTING caps
a BUY conviction at 3/5; ACCUMULATING adds +1 conviction when ≥2 other seats agree; NEUTRAL has no effect.

**A WATCH verdict is an alert trigger** — "good company, wrong price; buy near $X / when RSI < V"
is exactly when to register a notify-me job carrying the entry thesis via the **`mkt`** skill, so
the user is pinged when the zone/indicator fires. See *Set a buy-alert* below.

---

## Output format per stock

```
═══════════════════════════════════════════════════════
 {TICKER} — {COMPANY} — {DATE}
 Theme: {AI_SUPPLY_CHAIN | ROBOTICS | ENERGY | DEFENSE | FINTECH | HEALTHCARE | OTHER}
 Theme phase: {EARLY_CYCLE | MID_CYCLE | LATE_CYCLE | FADING}
═══════════════════════════════════════════════════════
 SEAT VERDICTS
 Fundamental : {STRONG/GOOD/FAIR/POOR} — {one line: key metric}
 Technical   : {SETUP_NAMED/NO_SETUP/BROKEN} — {setup name or "no trigger"}
 Narrative   : {EARLY/MID/LATE/FADING} — {one line: why}
 Sentiment   : {QUIET_ACCUM/NEUTRAL/CROWDED/EXTREME} — {one line}
 Smart-money : {ACCUMULATING/DISTRIBUTING/NEUTRAL} — {CONVICTION: HIGH/MED/LOW | one line: key signal}

 DECISION: {BUY / WATCH / SKIP}
 Entry zone : ${low}–${high}
 Trigger    : {bar-close above/below X on timeframe Y}
 Stop       : ${level} ({basis: support/MA/range})
 Target     : ${level} (risk:reward {X}:1)
 Conviction : {1-5}/5
 Invalidation: {what kills the thesis — thesis-break, not just the price stop}
═══════════════════════════════════════════════════════
```

**Citation rule (per stock):** any narrative/news claim in the block must carry an inline
`[source: https://exact-article-url]`. Technical indicators (RSI, MACD, MAs) computed from price data need
no source; news facts, theme claims, and fund-flow figures DO. No URL = remove the claim.

---

## Step 3 — Final signal table

```
STOCKS PANEL — {DATE} — {N} stocks analyzed
Theme map: [AI_SUPPLY_CHAIN: X] [ROBOTICS: Y] [ENERGY: Z] [DEFENSE: W] ...

Ticker  Company         Decision  Conv  Entry zone     Trigger            Theme
------  -------         --------  ----  ----------     -------            -----
AVGO    Broadcom        WATCH     4/5   $350-380       Reclaim $390       AI_SUPPLY_CHAIN
MRVL    Marvell Tech    BUY       4/5   $255-270       Bar close >$280    AI_SUPPLY_CHAIN
CEG     Constellation   SKIP      2/5   —              none (LATE_CYCLE)  ENERGY
...
```

---

## Step 4 — Portfolio-level synthesis (hand off to `stock-chair`)

The per-stock blocks answer "where do I enter each name." The **portfolio view** — concentration, hidden
factor/sector correlation across the BUY/WATCH names, what to fund a new buy by trimming — is the
`stock-chair` skill's job. After the signal table, if the user asked a portfolio-aware question ("what
should I buy given what I hold"), invoke `stock-chair` with: the user's holdings, the per-stock decisions,
and the theme map. `stock-chair` returns the buy-AND-sell, sizing, and concentration check. This skill
stops at per-name entry plans; it never sizes the book.

---

## Worked example (one stock)

<example>
User: "Run stocks-advisor on MRVL."

Orchestrator (sequential): resolves `NASDAQ:MRVL`; pulls D/W OHLCV + RSI/BB/MACD/Volume + screenshot;
runs `fundamentals.py` → `{price: 264.71, ma200: 116.31, vs_200d_ma: +127.6%, fwd_pe: 42.9, peg: 1.58,
fcf_yield: 0.98, rev_growth: 27.6%, earnings_growth: -80.4%, short: 4.7%, inst: 85.5%, rec_mean: 1.45,
analysts: 41, dd_from_52wh: -19.8%}`. Assembles the package, spawns 5 seats in parallel.

Seat verdicts:
- Fundamental: **FAIR** — fwd P/E 42.9, PEG 1.58, FCF yield 0.98% (rich); but rev +27.6% AI-driven. Thin
  margin of safety at this price.
- Technical: **SETUP_NAMED** — pullback off 52w high, holding well above rising 200d ($116). Trigger:
  daily close > $280 on above-avg volume. Stop: $245 (range low / 50d). Target $320, R:R ~2.4:1.
- Narrative: **MID_CYCLE** — custom-silicon / AI accelerator theme, broad participation, earnings
  confirming [source: https://www.ft.com/...]. Real beneficiary, not noise.
- Sentiment: **CROWDED** — rec_mean 1.45 across 41 analysts, inst 85.5% — little marginal buyer left.

Decision: Fundamental only FAIR (not ≥ GOOD) → fails the BUY gate → **WATCH**. Output a WATCH block: enter
$255–270 only if a daily close > $280 confirms; conviction 3/5 (CROWDED −1; MID_CYCLE neutral).
Invalidation: loss of the 200d trend or AI-capex guidance cut. Honest note: "this is a hypothesis — the
$280 trigger rule must clear strategy-discovery-backtest before risking capital."
</example>

---

## Self-check before printing the signal table

- [ ] Every ticker has `status='done'` in `stock_analysis`.
- [ ] Each stock block ends with a concrete **entry zone + bar-close trigger + market-based stop** — never
      a vague "looks good". WATCH/SKIP names what would change it.
- [ ] The technical seat **named a setup or said there is none**; no BUY without a live trigger.
- [ ] The narrative seat cited ≥2 real article URLs it **actually web_fetched or got from the feed scripts**
      (`feeds/wsj.ts`/`feeds/ft.ts`); every news claim carries an inline `[source: https://...]`; no URL = the claim was removed.
- [ ] Themes and constituents were **discovered live this run** (or the user supplied the list) — none
      asserted from memory.
- [ ] The honest base-rate note is present: single names are satellites, index is the bar; passing panels
      are hypotheses to be backtested in `strategy-discovery-backtest`.
- [ ] A TradingView screenshot is embedded inline (via the `view` tool on the `file_path`) per stock.
- [ ] The smart-money seat cited ≥1 real filing/trade URL it actually web_fetched (openinsider, 13f.info,
      EDGAR, or capitoltrades), or returned `NEUTRAL — INSUFFICIENT DATA`; no filing is fabricated.
- [ ] Portfolio sizing/concentration was deferred to `stock-chair`; ETF allocation was deferred to
      `tradfi-portfolio-manager`. This skill stayed on individual-stock entries only.

## Set a buy-alert (notify-me-when) — for WATCH verdicts

A WATCH verdict ("good company, wrong price — buy near $X / when RSI < V") is exactly when to
register a durable alert so the user is pinged **with your entry thesis** when it triggers.
Use the **`mkt`** skill — it carries the reasoning into the notification (mkt's native alert
message cannot). Register the entry plan as a job:

```bash
cd .agents/skills/mkt/scripts
bun mkt-alert.ts add --desk stocks --symbol NVDA \
  --condition below --value 142 \
  --reason "Buy-zone = prior breakout retest + 50d reclaim; add to core, not a new satellite." \
  --channel telegram:@CryptoAiInvestor --expiry 2026-09-30
# oversold add: --condition rsi_below --value 30 --period 14 --cooldown 21600
```

A scheduled `bun check.ts` (runtime cron) fires the notification with the reasoning when the
zone/indicator is hit. See `.agents/skills/mkt/SKILL.md` for the trigger patterns and
per-runtime scheduler cookbook. This stays recommend-only and backtest-gated — an alert is a
reminder to re-evaluate, not an order.

## Done when

Each analyzed stock has a 5-seat panel, a BUY/WATCH/SKIP decision from the verdict table, and a concrete
entry plan (zone + trigger + stop + conviction + invalidation); the signal table with the theme map is
printed; every news claim is sourced; and the output is flagged as an educational, backtest-gated
hypothesis — not advice.
