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

**Full per-run loop:** see Step 1.5 (Sequential per-stock loop).

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

## CONFIG — optional Notion publish target

Publishing the run to Notion is **OPT-IN**. The target lives in
`.cache/stocks-advisor/notion.yaml`, a YAML file with two fields:

```yaml
page_url: "https://app.notion.com/p/..."
page_id: "<32-char hex id>"
```

The skill reads `page_id` at publish time (§Step 5) — never hardcode a page id in this file. If the
file is missing OR `page_id` is empty, the skill **skips publishing silently** and finishes the run;
absence is NOT an error (unlike stocks-daily, which stopped — this skill continues).

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

## Step 0 — Classify the request, then route (do this first)

Detect the user's intent from their ask and route BEFORE running any per-name panel. Do not run a full 5-seat panel on a question that is really an allocation/deployment question.

| Intent (detect from the ask) | Route |
|---|---|
| "analyze these tickers / find entries / is now a good time to buy X" | This skill — per-name 5-seat panel (the rest of this doc) |
| "review my portfolio" + holdings sheet | This skill per-name on the triaged subset → then hand to `stock-chair` for sizing/concentration |
| "deploy $X / what ETFs should I buy / which big-caps to avoid / sleeve allocation" | This is an ALLOCATION question. Route to `tradfi-portfolio-manager` for the ETF/sleeve plan FIRST; use this skill only for the single-name satellite slice. Do NOT front-load a per-name panel. |

Resolve routing up front. A portfolio review that asks "what to buy/sell" is BOTH: triage the book here, but the cash-deployment / ETF-allocation answer belongs in `tradfi-portfolio-manager` — say so and route, rather than improvising sleeve allocation inside this skill.

---

## Step 0.3 — Load prior memory

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

Inspect the printed `source=` attribute. If `source="grep-fallback"` (the structured portfolio-memory store was missed and it fell back to grepping daily logs), set **MEMORY_DEGRADED** and print: "Memory: DEGRADED (grep-fallback) — no canonical per-ticker stance; treat any recalled verdict as low-confidence, not an authoritative supersede." Continue the run, but do not present a grep-fallback stance as the canonical current call.

---

## Step 0.5 — Load holdings from Google Sheet (if provided)

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

## Step 0.7 — Preflight: is TradingView alive? (run before the per-ticker loop)

Call `tradingview-tv_health_check` ONCE before starting the loop.
- PASS → normal mode (pull live charts per Step 1).
- FAIL (CDP down, or `tv_launch` returns "not found") → enter **DEGRADED_TECH** for the whole run:
  - Technical read comes from `fundamentals.py` ONLY: `ma50`, `ma200`, `vs_200d_ma`, `vs_50d_ma`, `52w_high/low`, `dd_from_52wh`.
  - RSI / Bollinger / MACD = **UNAVAILABLE** — do not guess them. Technical STATE collapses to `{ABOVE_TREND, BELOW_TREND, UNKNOWN}` (above/below the 200d).
  - No live bar-close trigger is computable → every name is **WATCH-only, never BUY**; entry zones come from MA levels.
  - Skip `capture_screenshot`; the screenshot self-check item does NOT apply in this mode.
  - Tag every output block: `DEGRADED: TradingView down — trend-only read, no live trigger.`

---

## Step 0.8 — Screen every name with fundamentals.py; reserve TradingView for deep dives

`fundamentals.py` (yfinance) is the DEFAULT data source for the WHOLE book — it is cheap, needs no chart slot, and runs for every name (price, ma50, ma200, vs_200d_ma, vs_50d_ma, 52w_high/low, dd_from_52wh, valuation, growth). TradingView (live RSI/BB/MACD + screenshot) is the single-chart-slot bottleneck — pulling it for every name does not scale (a 50-80 name book = thousands of MCP calls). So TradingView is SELECTIVE, not default: use it only when a name needs a deeper technical look. Not all names do.

1. **Screen ALL names with `fundamentals.py` first.** This is the baseline for every holding/candidate — run it for the entire list (parallelizable; it is a plain script, not an MCP call). Produce a one-line read per name: trend (above/below 200d & 50d), valuation, growth, drawdown.
2. **Rank by decision-relevance** from that screen: concentration weight (% of book), |unrealized P&L %|, cash-deploy candidate, proximity to a key level (near 50d/200d or a 52w extreme), or a fundamental/thesis break.
3. **Select the deep-dive subset** — the names that actually warrant a chart: the top decision-relevant names (default K ≈ 10) PLUS any name the screen flags (sitting on a trigger level, a TRIM/EXIT candidate, or a deploy target). Everything else stays fundamentals-only.
4. **Run TradingView (Step 1.5, sequential single slot) + the full 5-seat panel ONLY on the deep-dive subset.** Every other name gets its verdict from the fundamentals screen alone (HOLD/TRIM/EXIT, or WATCH for a watchlist) — no TradingView, no 5 seats.
5. If TradingView is down (DEGRADED_TECH, Step 0.7), the deep-dive subset also falls back to fundamentals-only — the whole book is screen-level, nothing blocks.
6. State explicitly in the output which names got the TradingView deep dive vs the fundamentals-only screen, and the K used. Never silently drop a name.

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

## Step 1.5 — Sequential per-stock loop (orchestrator only; do NOT parallelize the data pull)

This loop runs ONLY for the deep-dive subset selected in Step 0.8 — not every name. Names that stayed fundamentals-only never enter this loop. Pick the next `pending` todo and `UPDATE todos SET status='in_progress'`. Then, for that ticker:

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

| Seat | Lens file (read ONLY this) | Output shape |
|---|---|---|
| 1 Fundamental | `.agents/skills/fundamental-analysis/SKILL.md` | RATING / KEY METRIC / MOAT / MARGIN OF SAFETY / BLIND SPOT |
| 2 Technical | `.agents/skills/analyst-technical-analysis/SKILL.md` | STATE / SETUP / TRIGGER / STOP / TARGET / BLIND SPOT |
| 3 Narrative-Macro | web_fetch + feed scripts (read_news.ts, feeds/wsj.ts, feeds/ft.ts) | PHASE / THEME / SOURCES(≥2 real) / WHY / BLIND SPOT |
| 4 Sentiment | injected package only | READ / KEY / CONTRARIAN TILT / BLIND SPOT |
| 5 Smart-Money | web_fetch openinsider/13f.info/EDGAR/capitoltrades | VERDICT / CONVICTION / Form4·13F·13D·PTR / SOURCES |

**Full subagent prompts — copy verbatim from `references/seat-prompts.md`.** Each seat receives the same injected data package; only Seats 3 and 5 may make external calls.

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

### Holdings decision table (when cost basis is known — Google-Sheet path)

When positions are loaded with cost basis, map seat votes to HOLD/ADD/TRIM/EXIT (not BUY/WATCH/SKIP):

| Decision | Condition |
|---|---|
| **EXIT** | Fundamental POOR **OR** Narrative FADING **OR** Technical BROKEN **OR** thesis invalidated. Harvest the loss if underwater. (SKIP-equivalent.) |
| **TRIM** | Position weight > concentration cap (default >15% of book) **OR** Sentiment EXTREME **OR** LATE_CYCLE while extended. Trim to target weight; thesis may still be intact. |
| **ADD** | The BUY gate (Fundamental ≥ GOOD, Technical SETUP_NAMED with live trigger, Narrative EARLY/MID, Sentiment ≠ EXTREME) is met **AND** current weight < cap. (BUY-equivalent, sized as an add to an existing position.) |
| **HOLD** | Thesis intact (Fundamental ≥ FAIR, not FADING) but no add trigger or already at target weight. |

(LATE_CYCLE → TRIM here, not EXIT: with cost basis and an intact thesis, you reduce rather than fully exit — unlike the no-position SKIP.)

Precedence: EXIT dominates, then TRIM (concentration is its own lever, independent of the entry signal), then ADD vs HOLD on the trigger. In DEGRADED_TECH mode (TradingView down), ADD is unavailable (no live trigger) — the holdings verdict is limited to HOLD/TRIM/EXIT.

---

## Output format per stock

> **TOP RECAP rule (MANDATORY — applies to BOTH the chat output and the Notion page).** EVERY run's
> report MUST OPEN with a 2–3 sentence prose RECAP at the very top, before any per-stock block and
> before the signal table. In plain English it states: (a) the highest-confidence STRONG BUY / SELL
> actions to take right now, each with one-line reasoning; and (b) the current market narrative in one
> sentence. This is a prose TL;DR — the first thing the reader sees — and is **distinct** from the
> Step 3.6 high-confidence RECAP *table* printed at the end. Keep it tight.

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

## Step 3.5 — Sources & data provenance appendix (MANDATORY — always print)

After the signal table, ALWAYS print a consolidated **SOURCES & DATA** block — non-negotiable transparency so every news claim and market-data point is traceable to its origin. Aggregate from every seat that fetched:

1. **News / narrative sources** — every URL the narrative seat web_fetched OR got from the feed scripts (`feeds/wsj.ts`, `feeds/ft.ts`, `read_news.ts`). One per line: `[Tn] https://url (date) — "verbatim teaser/quote"`.
2. **Smart-money / filing sources** — every URL the smart-money seat actually web_fetched (openinsider, 13f.info, EDGAR, capitoltrades, finviz/marketbeat fallbacks — whatever was really used). One per line.
3. **Market-data provenance** — state the origin of prices/indicators/fundamentals explicitly: `fundamentals.py (yfinance) per ticker: {tickers run}` and `Technicals: TradingView studies RSI/BB/MACD/Volume` (or, in DEGRADED_TECH mode: `Technicals: DEGRADED — MA levels from fundamentals.py only, no TradingView`).
4. If any seat returned `INSUFFICIENT DATA`, list it here explicitly rather than omitting it.

Format:
```
SOURCES & DATA — {DATE}
News ({n}):
  [T1] https://... (date) — "verbatim teaser"
  ...
Filings/flows ({n}):
  https://...
Market data:
  fundamentals.py (yfinance): {tickers}
  Technicals: {TradingView studies | DEGRADED MA-only}
```

Rule: never print a verdict that depends on a source you cannot list here. No source listed = the claim must be removed. This appendix is required in BOTH normal and DEGRADED_TECH mode.

---

## Step 3.6 — High-confidence recap + setup-alerts table (MANDATORY — final output, print LAST)

The per-stock blocks and the signal table are the full record. End EVERY run with a tight recap so the user sees the actionable subset at a glance. Print these two tables as the final output.

**RECAP — high-confidence only.** Include ONLY decisions with conviction ≥ 4/5 (or, for a holdings review, the unambiguous ADD / EXIT calls). Drop everything that is WATCH-without-a-trigger, NEUTRAL, or conviction ≤ 3 — those live in the full table above, not here. If nothing clears the bar, print "No high-confidence actions today — all names are WATCH (see table above)" rather than padding the list.

```
RECAP — high-confidence ({DATE})
Asset   Action            Why (one line, plain English)
-----   ------            -----------------------------
{TICK}  BUY/ADD/EXIT/TRIM {≤12-word plain-English reason}
...
```

**SETUP ALERTS — buy/sell only when a condition fires.** Every WATCH name that has a *defined* trigger (a price reclaim, a level, an indicator like RSI) goes here — not as a buy-now. State the exact condition and the action it unlocks. These are the names to register with the `mkt` skill so the user is pinged with the thesis when the condition hits (see "Set a buy-alert" section).

```
SETUP ALERTS ({DATE})
Asset   Condition (exact)               Then do        Thesis (one line)
-----   -----------------               -------        -----------------
{TICK}  close > ${level} (reclaim)      BUY {zone}     {≤12-word reason}
{TICK}  RSI(14) < 30 / pullback ${lvl}  ADD            {≤12-word reason}
...
```

Rule: a name is in RECAP **or** SETUP ALERTS, never both — high-confidence-now vs buy-on-condition are mutually exclusive. After printing SETUP ALERTS, offer to register them via the `mkt` skill (the alert carries the thesis into the notification). This recap is required in BOTH normal and DEGRADED_TECH mode; in DEGRADED mode the alert conditions are MA/price levels (no live bar-close trigger).

---

## Step 4 — Portfolio-level synthesis (hand off to `stock-chair`)

The per-stock blocks answer "where do I enter each name." The **portfolio view** — concentration, hidden
factor/sector correlation across the BUY/WATCH names, what to fund a new buy by trimming — is the
`stock-chair` skill's job. After the signal table, if the user asked a portfolio-aware question ("what
should I buy given what I hold"), invoke `stock-chair` with: the user's holdings, the per-stock decisions,
and the theme map. `stock-chair` returns the buy-AND-sell, sizing, and concentration check. This skill
stops at per-name entry plans; it never sizes the book.

---

## Step 5 — Publish to Notion (if configured)

This skill is the **single owner** of Notion publishing for stock research (`stocks-daily` delegates
here). Publishing is opt-in and silent-skip — never fail the run because of it.

1. **Read the publish target:**
   ```sh
   PAGE_ID=$(grep '^page_id:' .cache/stocks-advisor/notion.yaml 2>/dev/null | sed -E 's/.*"([a-f0-9]+)".*/\1/')
   ```
   If `.cache/stocks-advisor/notion.yaml` is missing OR `PAGE_ID` is empty → **skip this step silently**
   and finish the run. Publishing is opt-in; absence is not an error (do NOT stop, do NOT warn).
2. **Load Notion tools via ToolSearch:**
   `select:mcp__claude_ai_Notion__notion-create-pages,mcp__claude_ai_Notion__notion-fetch`
3. **Save to local file** (always — even if `PAGE_ID` is empty):
   - Filename: `YYYY-MM-DD <narrative>.md` — same title that would be used for Notion.
   - Path: `.cache/stocks-advisor/research/<title>.md`
   ```bash
   mkdir -p .cache/stocks-advisor/research
   # TITLE = computed title string, e.g. "2026-06-26 AI-bubble derisking — rotate to healthcare"
   # CONTENT = full report markdown (top recap + per-stock + sources + setup-alerts)
   python3 -c "
   import sys
   title, content = sys.argv[1], sys.argv[2]
   open(f'.cache/stocks-advisor/research/{title}.md', 'w').write(content)
   " "$TITLE" "$CONTENT"
   ```
4. **Create a NEW child page under `PAGE_ID`** (only if `PAGE_ID` non-empty):
   - **Title format: `YYYY-MM-DD <narrative>`** — the run date followed by a short narrative descriptor
     of the run's dominant theme (e.g. `2026-06-26 AI-bubble derisking — rotate to healthcare/defense`).
     Not a generic title.
   - Content: the full run output as Notion-flavored Markdown — the 2–3 sentence TOP RECAP first (§Output
     format per stock), then the narrative, the per-name decision tables, the SOURCES & DATA appendix
     (§Step 3.5), and the high-confidence RECAP + SETUP ALERTS (§Step 3.6). Use real Notion table blocks,
     not code-fenced text.
5. On any Notion error, report it to the user and **continue** — never fail the run because publishing
   failed.
6. Print: `✅ Saved: .cache/stocks-advisor/research/<title>.md` and (if published) the Notion page URL.

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

- [ ] The report **OPENS with the 2–3 sentence prose RECAP** (highest-confidence buy/sell to take now + one-line reasoning + the market narrative in one sentence) before any per-stock block or the signal table.
- [ ] Every FULL-PANEL ticker has `status='done'` in `stock_analysis`; one-line-screened names (N>12 triage) carry a one-line note and are listed, not dropped.
- [ ] Each stock block ends with a concrete **entry zone + bar-close trigger + market-based stop** — never
      a vague "looks good". WATCH/SKIP names what would change it.
- [ ] The technical seat **named a setup or said there is none**; no BUY without a live trigger.
- [ ] The narrative seat cited ≥2 real article URLs it **actually web_fetched or got from the feed scripts**
      (`feeds/wsj.ts`/`feeds/ft.ts`); every news claim carries an inline `[source: https://...]`; no URL = the claim was removed.
- [ ] Themes and constituents were **discovered live this run** (or the user supplied the list) — none
      asserted from memory.
- [ ] The honest base-rate note is present: single names are satellites, index is the bar; passing panels
      are hypotheses to be backtested in `strategy-discovery-backtest`.
- [ ] A TradingView screenshot is embedded inline per stock — UNLESS in DEGRADED_TECH mode (TradingView down), where screenshots are skipped and each block is tagged DEGRADED.
- [ ] The smart-money seat cited ≥1 real filing/trade URL it actually web_fetched (openinsider, 13f.info,
      EDGAR, or capitoltrades), or returned `NEUTRAL — INSUFFICIENT DATA`; no filing is fabricated.
- [ ] Portfolio sizing/concentration was deferred to `stock-chair`; ETF allocation was deferred to
      `tradfi-portfolio-manager`. This skill stayed on individual-stock entries only.
- [ ] recall.ts `source` was checked; if `grep-fallback`, the run is tagged MEMORY_DEGRADED and recalled stances flagged low-confidence.
- [ ] A consolidated **SOURCES & DATA** appendix is printed (Step 3.5) listing every web_fetched news/filing URL, every feed-script record, and the market-data provenance (fundamentals.py tickers + technicals mode) — required in normal AND DEGRADED mode.
- [ ] A final **RECAP (high-confidence only)** + **SETUP ALERTS** table is printed (Step 3.6); high-conviction-now and buy-on-condition names are split, never duplicated; if nothing clears the bar, that is stated explicitly.

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
printed; every news claim is sourced; the consolidated SOURCES & DATA appendix (Step 3.5) is printed listing all web_fetched URLs, feed-script records, and market-data provenance; and the output is flagged as an educational, backtest-gated
hypothesis — not advice; and a high-confidence RECAP + SETUP ALERTS table (Step 3.6) is printed last, splitting immediate high-conviction actions from buy-on-condition names. If `.cache/stocks-advisor/notion.yaml` is configured, a dated Notion page (title `YYYY-MM-DD <narrative>`, Step 5) was created and its URL returned to the user; if it is not configured, publishing was skipped silently (not an error).
