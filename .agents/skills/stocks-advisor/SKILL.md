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

Analyze individual stocks **one at a time** → run a 5-seat analyst panel per stock → output a concrete
**entry plan** (zone + trigger + stop) and a BUY / WATCH / SKIP decision. The stock list is user-supplied
or **discovered live** from the market themes currently driving institutional flows. Hardcode nothing — no
positions, no themes.

> Educational analysis, not financial advice. Single stocks are satellites; the index is the bar.

## The job is the ENTRY, not the company

The question is **not** "is this a good company" — it is **"is NOW a good time to enter, and where
exactly?"** A great company at the wrong entry is a wrong trade. Every output ends with a price zone, a
bar-close trigger, and a market-based stop, or it is incomplete.

## Quickstart

### Review your existing portfolio (Google Sheet)
```
Invoke the stocks-advisor skill.
Holdings: https://docs.google.com/spreadsheets/d/1aunLbpNGo85WqrMHiIsy6nFUija4Lnjot-rIhE-pGU8/edit?gid=1914937017
Tab: IBKR
Cash to deploy: $26,320
```
Reads positions (ticker, qty, cost basis) from the sheet, runs the 5-seat panel per position. Verdicts
become **HOLD / ADD / TRIM / EXIT** (not BUY/WATCH/SKIP) since cost basis and P&L are known. Output adds a
tax-harvest table and cash-deployment plan.

### Analyze a supplied watchlist
```
Run stocks-advisor on: AVGO, MRVL, VRT, CEG
```

### Discover stocks within a theme, then analyze
```
Find stocks in the AI supply chain theme and run the stock panel
```
Discovers the theme's constituents live (web_fetch — §Theme discovery), then runs the per-stock panel on
the discovered names.

**Full per-run loop:** see Step 1.5 (Sequential per-stock loop).

---

## Hard constraints — read before running (these dictate the whole design)

1. **TradingView MCP + yfinance live ONLY in the orchestrator (you).** Subagents spawned via the task tool
   get a fresh toolset with **no** `tradingview-*` tools and **no** yfinance. So YOU pull every chart datum,
   run `fundamentals.py`, assemble one data package per stock, and **inject** it into each seat. Never tell
   a subagent to "pull TradingView data" or "run yfinance" — it cannot. Seats only *receive* the package and
   reason; the narrative seat may still `web_fetch` news.
2. **The chart is a single shared symbol slot.** `chart_set_symbol` mutates the one global chart — two
   tickers cannot be pulled at once. **Pull data strictly sequentially, one ticker at a time.** Track
   progress in the `todos` table so an interrupted run resumes cleanly.
3. **Sequential data pull, parallel analysis.** The five seats per stock share nothing — spawn them **in
   parallel** once the package is assembled.
4. **TradingView symbol mapping:** use `NASDAQ:{TICKER}` or `NYSE:{TICKER}` for US stocks. On exchange-lookup
   failure, fall back to bare `{TICKER}`. When unsure of the exchange, call `tradingview-symbol_search` to
   resolve it before `chart_set_symbol`.
5. **Indicators from TradingView; fundamentals + MA levels from yfinance.** `data_get_study_values` returns
   RSI(14), Bollinger(20,2), MACD(12,26,9), Volume at standard lengths — use them verbatim, do not recompute.
   Price levels (`ma50`, `ma200`, `52w_high/low`, `dd_from_52wh`, `vs_200d_ma`) and all fundamentals come
   from `scripts/fundamentals.py` (yfinance). This sidesteps the TradingView MA-length bug entirely (its
   `chart_manage_indicator` ignores the MA `length` input).
6. **Individual stocks only.** ETF / sleeve allocation belongs in `tradfi-portfolio-manager`. Portfolio-level
   synthesis across the analyzed names is the `stock-chair` skill's job (§Step 4).

---

## CONFIG — optional Notion publish target

Notion publishing is **opt-in**. The target lives in `.cache/stocks-advisor/notion.yaml`:

```yaml
page_url: "https://app.notion.com/p/..."
page_id: "<32-char hex id>"
```

Read `page_id` at publish time (§Step 5) — never hardcode it here. If the file is missing OR `page_id` is
empty, **skip publishing silently** and finish the run; absence is not an error.

---

## The honest base rate (state this every run)

From the `fundamental-analysis` skill, on full-history backtests of the investable stock-selection methods
vs SPY: **only 1 of 10 methods beat SPY on return (momentum); 0 of 10 beat it on Sharpe — including the ETF
that implements Morningstar's own stock-picking.** Single-stock selection is a low-base-rate bet. So:
- Single names are **satellites**, the index is the **core and the bar**.

> Source: Carver, *Systematic Trading*, Ch.2 — single-equity Sharpe ratio ≈ 0.15; a diversified equity index SR ≈ 0.20; each additional uncorrelated instrument raises the portfolio Sharpe; individual stock selection is structurally at a disadvantage to indexing on a risk-adjusted basis.

- A passing panel is a **hypothesis**, not validated alpha. TA setups are **hypothesis generation** —
  validate any mechanical rule with `strategy-discovery-backtest` (full costs, walk-forward) before risking
  real capital.
- yfinance fundamentals are **point-in-time UNSAFE** (today's numbers) — fine for *current* entry analysis,
  never for backtesting a screen.

> Source: Housel, *Psychology of Money*, Ch.1 — "doing well with money has a little to do with how smart you are and a lot to do with how you behave"; systematic checklists and fixed decision rules enforce the behavioral discipline that discretionary portfolios consistently lack.

---

## Theme discovery — discovered live, never hardcoded

Market narratives rotate. **Do not hardcode a theme list.** When the user asks "find stocks in theme X" /
"what should I look at this week", discover live themes and constituents by fetching and reading real pages:

1. **Identify the live themes.** Pull WSJ + FT first via the **paywall-free feed scripts** (the
   `wsj.com`/`ft.com` listing pages are bot-blocked from agent IPs — the feed scripts return real article
   URLs + a verbatim publisher teaser + date, no login):
   ```bash
   bun .agents/skills/read-news/scripts/feeds/wsj.ts --feed markets,business --days 5 --limit 25 --text
   bun .agents/skills/read-news/scripts/feeds/ft.ts  --section markets,companies,global-economy --days 5 --limit 25 --text
   ```
   Then `web_fetch` 1–2 of the **non-paywalled** listings for breadth:
   - `https://www.bloomberg.com/markets`
   - `https://finance.yahoo.com/topic/latest-news/` (sector/thematic trend listings)
2. **Map names to themes.** Tag each candidate ticker with one bucket:
   `AI_SUPPLY_CHAIN | ROBOTICS | ENERGY | DEFENSE | FINTECH | HEALTHCARE | OTHER`. Buckets are a
   classification convention, not a fixed universe — add one if the evidence supports it.
3. **Anti-hallucination rule (same as the narrative seat):** name a theme or constituent only if you found it
   this run in a page you actually `web_fetch`ed **or** in feed-script output you actually ran
   (`feeds/wsj.ts`/`feeds/ft.ts` print real URLs + verbatim teasers — those count as fetched). No fetched
   URL / no feed record = not a theme. Never list a "current narrative" from memory.

If the user supplies an explicit ticker list, skip discovery and analyze that list (still tag each name with
a theme in the output).

---

## Step 0 — Classify the request, then route (do this first)

Route BEFORE running any per-name panel. Do not run a full 5-seat panel on a question that is really an
allocation/deployment question.

| Intent (detect from the ask) | Route |
|---|---|
| "analyze these tickers / find entries / is now a good time to buy X" | This skill — per-name 5-seat panel (rest of this doc) |
| "review my portfolio" + holdings sheet | This skill per-name on the triaged subset → then hand to `stock-chair` for sizing/concentration |
| "deploy $X / what ETFs should I buy / which big-caps to avoid / sleeve allocation" | ALLOCATION question. Route to `tradfi-portfolio-manager` for the ETF/sleeve plan FIRST; use this skill only for the single-name satellite slice. Do NOT front-load a per-name panel. |

A portfolio review asking "what to buy/sell" is BOTH: triage the book here, but route the cash-deployment /
ETF-allocation answer to `tradfi-portfolio-manager` — do not improvise sleeve allocation here.

---

## Step 0.3 — Load prior memory

Before seeding the todo list, pull prior verdicts and user preferences for this run's tickers:

```bash
bun .agents/skills/portfolio-memory/recall.ts --desk stocks \
  --tickers "AVGO MRVL COIN PYPL"
```

Inject the printed `<prior_context>` block into EVERY seat's data package. It has two parts: the
**canonical** current stance per ticker (the latest verdict, which physically overwrote any older one — you
cannot follow a stale call) and **episodic** dated history newest-first. If there is no prior memory the
script prints `[no prior memory for this run]` — continue normally. See `portfolio-memory` for the model.

Inspect the printed `source=` attribute. If `source="grep-fallback"` (the structured store was missed and it
fell back to grepping daily logs), set **MEMORY_DEGRADED** and print: "Memory: DEGRADED (grep-fallback) — no
canonical per-ticker stance; treat any recalled verdict as low-confidence, not an authoritative supersede."
Continue the run, but do not present a grep-fallback stance as the canonical current call.

---

## Step 0.5 — Load holdings from Google Sheet (if provided)

If the user passed a Google Sheet URL, read holdings before seeding the todo list. Use the `gws-sheets-read`
skill (https://www.skills.sh/googleworkspace/cli/gws-sheets-read):

```bash
gws sheets +read \
  --spreadsheet <ID extracted from URL> \
  --range "<Tab>!A:E"
```

Extract the spreadsheet ID from the URL (the long alphanumeric string between `/d/` and `/edit`). Parse the
response into `[{ticker, qty, cost_basis, market_value, pnl_pct, cash}]`:
- Rows where Type = "Cash" → set as `cash_to_deploy`
- Rows where Type = "Stock" → build the ticker universe for this run

When holdings are loaded:
- Add `cost_basis`, `qty`, `pnl_pct`, `dd_from_cost` to each ticker's data package
- Seat verdicts shift to **HOLD / ADD / TRIM / EXIT** (not BUY/WATCH/SKIP)
- After the signal table, output a **tax-harvest section** (positions with largest unrealized losses) and a
  **cash deployment section** (where to put `cash_to_deploy`)

If no sheet URL was provided, skip this step and use the user-supplied ticker list or theme discovery.

---

## Step 0.6 — Create the run artifact directory

Run once before the per-ticker loop. All per-ticker data packages, seat results, and the final report land
here.

```bash
RUN_DIR=".cache/stocks-advisor/research/$(date +%Y-%m-%d_%H-%M)"
mkdir -p "$RUN_DIR"
echo "Artifacts: $RUN_DIR"
```

Every ticker gets its own subdirectory `$RUN_DIR/{TICKER}/`. Layout after a complete run:
```
.cache/stocks-advisor/research/2026-06-27_14-30/
├── report.md
├── AVGO/
│   ├── data_package.json          # merged TV + fundamentals.py output
│   ├── seat_fundamental.json
│   ├── seat_technical.json
│   ├── seat_narrative_macro.json
│   ├── seat_sentiment.json
│   ├── seat_smart_money.json
│   └── verdict.json               # decision, entry_low/high, trigger, stop, target, conviction
├── MRVL/
│   └── ...
└── ...
```

---

## Step 0.7 — Preflight: is TradingView alive? (run before the per-ticker loop)

Call `tradingview-tv_health_check` ONCE before the loop.
- PASS → normal mode (pull live charts per Step 1).
- FAIL (CDP down, or `tv_launch` returns "not found") → enter **DEGRADED_TECH** for the whole run:
  - Technical read comes from `fundamentals.py` ONLY: `ma50`, `ma200`, `vs_200d_ma`, `vs_50d_ma`,
    `52w_high/low`, `dd_from_52wh`.
  - RSI / Bollinger / MACD = **UNAVAILABLE** — do not guess them. Technical STATE collapses to
    `{ABOVE_TREND, BELOW_TREND, UNKNOWN}` (above/below the 200d).

> Source: Carver, *Systematic Trading*, Ch.7 (Forecasts / EWMAC) — exponentially weighted moving average crossovers are the primary evidence-based trend-following rule class; above/below a long-period MA is the simplest valid trend-state signal, grounded in the same prospect-theory behavioral rationale as all trend following.

  - No live bar-close trigger is computable → every name is **WATCH-only, never BUY**; entry zones come from
    MA levels.
  - Skip `capture_screenshot`; the screenshot self-check item does NOT apply in this mode.
  - Tag every output block: `DEGRADED: TradingView down — trend-only read, no live trigger.`

---

## Step 0.8 — Screen every name with fundamentals.py; reserve TradingView for deep dives

`fundamentals.py` (yfinance) is the DEFAULT source for the WHOLE book — cheap, no chart slot, runs for every
name. TradingView (live RSI/BB/MACD + screenshot) is the single-chart-slot bottleneck — running it for every
name does not scale (a 50-80 name book = thousands of MCP calls). So TradingView is SELECTIVE, not default.

1. **Screen ALL names with `fundamentals.py` first** — the baseline for every holding/candidate. Run it for
   the entire list (parallelizable; it is a plain script, not an MCP call). Produce a one-line read per name:
   trend (above/below 200d & 50d), valuation, growth, drawdown.
2. **Rank by decision-relevance** from that screen: concentration weight (% of book), |unrealized P&L %|,
   cash-deploy candidate, proximity to a key level (near 50d/200d or a 52w extreme), or a fundamental/thesis
   break.
3. **Select the deep-dive subset** — the names that warrant a chart: the top decision-relevant names (default
   K ≈ 10) PLUS any name the screen flags (sitting on a trigger level, a TRIM/EXIT candidate, a deploy
   target). Everything else stays fundamentals-only.
4. **Run TradingView (Step 1.5, sequential single slot) + the full 5-seat panel ONLY on the deep-dive
   subset.** Every other name gets its verdict from the fundamentals screen alone (HOLD/TRIM/EXIT, or WATCH
   for a watchlist) — no TradingView, no 5 seats.
5. If TradingView is down (DEGRADED_TECH, Step 0.7), the deep-dive subset also falls back to
   fundamentals-only — the whole book is screen-level, nothing blocks.
6. State explicitly which names got the TradingView deep dive vs the fundamentals-only screen, and the K
   used. Never silently drop a name.

---

## Step 2 — Decision Hierarchy (pluggable)

The decision chain (how per-stock panel verdicts get turned into a final call) is **pluggable** — load the appropriate module based on the user's `--hierarchy` flag:

```bash
HIERARCHY="${HIERARCHY_FLAG:-bsc}"   # default: bsc
HIERARCHY_FILE=".agents/skills/stocks-advisor/references/hierarchies/${HIERARCHY}.md"
if [[ ! -f "$HIERARCHY_FILE" ]]; then
  echo "Unknown hierarchy: $HIERARCHY. Available: bsc, bridgewater, berkshire, point72, soros"
  exit 1
fi
# Load and follow the steps in $HIERARCHY_FILE — they replace Steps 2–2.7 entirely
cat "$HIERARCHY_FILE"
```

Available hierarchies (see `references/hierarchies/`):

| Name | Key mechanism | Best for |
|---|---|---|
| `bsc` (default) | Edge Gate + Skeptic [MEM audit] + P0/P1/P2/P3 | Full portfolio reviews — broadest coverage, highest eval score (25/25) |
| `bridgewater` | Skeptic → CIO → Risk Manager | Standard equity analysis — strong adversarialism without edge gate overhead |
| `berkshire` | Circle of Competence → Moat → Munger → Margin of Safety | Long-term concentrated conviction positions only |
| `point72` | Edge Gate → Conviction → Cohen Seat | Idea-generation / new positions with strong edge hypothesis |
| `soros` | Macro thesis → Reflexivity → P0/P1/P2/P3 | Macro-driven positions where regime is the primary driver |

**Invoking with a specific hierarchy:**
```
Run stocks-advisor with --hierarchy berkshire on: AAPL, KO, AXP
```
or for portfolio review:
```
Review my portfolio [sheet URL] using --hierarchy bsc
```

**Invoking the comparison mode** (runs all hierarchies on the same input, blind-scored):
```
Compare hierarchies on: AAPL, KO — use all
```
→ Routes to the `hierarchy-compare` workflow (see `.claude/workflows/hierarchy-compare.js`).

After loading $HIERARCHY_FILE, follow its steps exactly. The file contains the full decision chain (subagent prompts, output shapes, hard constraints). Do not improvise or mix steps from different hierarchies.

---

## Output format per stock

> **TOP RECAP rule (MANDATORY — chat output AND Notion page).** Every run's report OPENS with a 2–3 sentence
> prose RECAP, before any per-stock block or the signal table, stating in plain English: (a) the
> highest-confidence BUY/SELL actions to take now, each with one-line reasoning; (b) the current market
> narrative in one sentence. This is a prose TL;DR — **distinct** from the Step 3.6 RECAP *table* at the end.

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
 Skeptic     : {SKIP/WATCH/BUY} — {one line: strongest objection}

 CIO DECISION: {BUY / WATCH / SKIP / PASS}   (or ADD / HOLD / TRIM / EXIT on holdings path)
 Entry zone  : ${low}–${high}
 Trigger     : {bar-close above/below X on timeframe Y}
 Stop        : ${level} ({basis: support/MA/range})
 Target      : ${level} (risk:reward {X}:1)
 Conviction  : {1-5}/5
 Dissent     : {Skeptic's best objection — printed even when overruled}
 CIO memo    : {one sentence — controlling factor and what would change this call}
 Risk status : {APPROVED $X (N% book) | BLOCKED: reason | N/A (not BUY/ADD)}
 Invalidation: {3 falsifiable conditions from Skeptic — thesis-break, not just the price stop}
═══════════════════════════════════════════════════════
```

**Citation rule (per stock):** any narrative/news claim in the block carries an inline
`[source: https://exact-article-url]`. Technical indicators (RSI, MACD, MAs) computed from price data need no
source; news facts, theme claims, and fund-flow figures DO. No URL = remove the claim.

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

After the signal table, ALWAYS print a consolidated **SOURCES & DATA** block so every news claim and
market-data point is traceable. Aggregate from every seat that fetched:

1. **News / narrative sources** — every URL the narrative seat web_fetched OR got from the feed scripts
   (`feeds/wsj.ts`, `feeds/ft.ts`, `read_news.ts`). One per line: `[Tn] https://url (date) — "verbatim teaser/quote"`.
2. **Smart-money / filing sources** — every URL the smart-money seat actually web_fetched (openinsider,
   13f.info, EDGAR, capitoltrades, finviz/marketbeat fallbacks). One per line.
3. **Market-data provenance** — state the origin of prices/indicators/fundamentals: `fundamentals.py
   (yfinance) per ticker: {tickers run}` and `Technicals: TradingView studies RSI/BB/MACD/Volume` (or, in
   DEGRADED_TECH mode: `Technicals: DEGRADED — MA levels from fundamentals.py only, no TradingView`).
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

Never print a verdict that depends on a source you cannot list here. No source listed = remove the claim.
Required in BOTH normal and DEGRADED_TECH mode.

---

## Step 3.6 — High-confidence recap + setup-alerts table (MANDATORY — final output, print LAST)

End EVERY run with these two tables so the user sees the actionable subset at a glance.

**RECAP — high-confidence only.** Include ONLY decisions with conviction ≥ 4/5 (or, for a holdings review,
the unambiguous ADD / EXIT calls). Drop everything WATCH-without-a-trigger, NEUTRAL, or conviction ≤ 3 —
those live in the full table above. If nothing clears the bar, print "No high-confidence actions today — all
names are WATCH (see table above)" rather than padding the list.

```
RECAP — high-confidence ({DATE})
Asset   Action            Why (one line, plain English)
-----   ------            -----------------------------
{TICK}  BUY/ADD/EXIT/TRIM {≤12-word plain-English reason}
...
```

**SETUP ALERTS — buy/sell only when a condition fires.** Every WATCH name with a *defined* trigger (a price
reclaim, a level, an indicator like RSI) goes here — not as a buy-now. State the exact condition and the
action it unlocks. Register these with the `mkt` skill so the user is pinged with the thesis when the
condition hits (see *Set a buy-alert*).

```
SETUP ALERTS ({DATE})
Asset   Condition (exact)               Then do        Thesis (one line)
-----   -----------------               -------        -----------------
{TICK}  close > ${level} (reclaim)      BUY {zone}     {≤12-word reason}
{TICK}  RSI(14) < 30 / pullback ${lvl}  ADD            {≤12-word reason}
...
```

A name is in RECAP **or** SETUP ALERTS, never both — high-confidence-now and buy-on-condition are mutually
exclusive. After printing SETUP ALERTS, offer to register them via the `mkt` skill. Required in BOTH normal
and DEGRADED_TECH mode; in DEGRADED mode the alert conditions are MA/price levels (no live bar-close trigger).

**EXECUTION TABLE — P0/P1/P2/P3 (Soros format — cross-portfolio priority, runs after SETUP ALERTS)**

Rank all BUY/ADD/EXIT/TRIM verdicts by portfolio urgency, with exact share counts and triggers. This is the
actionable to-do list — one row per decision, ordered from most-urgent to watchlist:

```
EXECUTION TABLE ({DATE})
Priority  Ticker  Action    Shares  Entry zone    Trigger                  Port %   Falsification
--------  ------  ------    ------  ----------    -------                  ------   -------------
P0        {TICK}  EXIT      all     market open   immediately — thesis broken (state the break)
P1        {TICK}  ADD       N shr   $X–$Y         close > $Z on D ({date})   +X%    {specific condition that kills the add}
P2        {TICK}  ADD       N shr   $X–$Y         pullback to $W + RSI<40    +X%    {specific condition}
P3        {TICK}  WATCH     —       —             RSI<30 / close > $Z        —      {alert registered via mkt}
```

Priority tiers:
- **P0** — act at open, no conditions. Triggered by a thesis break already confirmed (disclosed earnings miss, management departure, position limit breach). No P0 without a named trigger already fired.
- **P1** — act this week if trigger fires. Conviction ≥ 4/5, setup named, Risk Manager APPROVED.
- **P2** — act this quarter if condition met. Conviction 3/5, waiting for a cleaner entry level.
- **P3** — watchlist, alert registered via `mkt` skill. Conviction ≤ 2/5 or condition is multi-week away.

**Share count rule:** use Risk Manager's APPROVED size ($amount) ÷ entry_high. Round to nearest 5 shares. State the dollar amount alongside the share count.

> Source: Soros/Druckenmiller Quantum Fund operating model — explicit P0/P1/P2/P3 execution table forces ranking of actions by urgency; prevents the common failure mode where all BUY signals are treated as equally urgent and nothing gets executed. Adding to winners (P1 = market confirms thesis) is systematic, not discretionary. Bridgewater All Weather allocation principle: cash deployment priority is determined by portfolio-level fit (fills a gap, reduces concentration) rather than ticker-level conviction alone.

---

## Step 4 — Portfolio-synthesis seat (run inline AFTER per-stock loop completes)

After all per-stock panels finish, run a dedicated **portfolio-synthesis seat** — a single subagent that
receives ALL per-stock verdicts + the full holdings list and reasons across positions holistically. This is
the step the per-stock loop structurally cannot do.

**Input to the synthesis seat:**
- Full holdings list (ticker, qty, cost_basis, market_value, weight_pct)
- All per-stock verdicts from `$RUN_DIR/*/verdict.json`
- The macro_regime paragraph from `$RUN_DIR/macro_regime.txt`
- Theme map (how many names per theme bucket)

**Synthesis seat prompt (spawn as a subagent `/model opus /effort xhigh`):**

```
Produce a portfolio synthesis with EXACTLY these five sections, in order:

1. FACTOR CORRELATION MAP
   Group all holdings by primary risk factor (Fed/rates, USD, oil, AI-capex, China exposure, etc.). Per
   group: list holdings, total weight %, and the tail scenario ("if [factor] moves -20%, these all fall
   together"). Flag any factor whose combined weight > 25% of book as a CONCENTRATION RISK.

2. OVER-DIVERSIFICATION CRITIQUE
   Count positions. If > 40, state: "N positions means individual-stock selection creates noise, not signal
   — each name must earn its place or become index." List positions that are index-like (correlation > 0.85
   to SPY, market cap > $500B) and could be replaced with VOO for lower cost and less monitoring overhead.

> Source: Carver, *Systematic Trading*, Ch.2 & Ch.6 — "the law of active management shows diversification is the best source of additional risk-adjusted returns"; beyond ~20 uncorrelated instruments, marginal diversification benefit falls sharply; very large equity-only books approximate the index, making passive ETFs a cheaper substitute for index-like names.

3. CROSS-POSITION CONFLICTS
   Identify pairs where one seat says ADD and another says TRIM on names sharing the same factor exposure —
   these conflict at the portfolio level even if individually correct.

4. PORTFOLIO STRUCTURE VERDICT
   One paragraph: the biggest structural risk in this book right now, and the single action that reduces it
   most. Name the risk, name the action.

5. CASH DEPLOYMENT PRIORITY
   Given the per-stock ADD verdicts and cash available ($CASH), rank ADD candidates by portfolio-level fit
   (fills a gap, reduces concentration, best risk:reward). Maximum 3 names.

> Source: Carver, *Systematic Trading*, Ch.9 (Volatility Targeting) — "positions should be sized based on how volatile markets are, how confident your price forecasts are, and the amount of capital you wish to gamble"; staged entry (tranching cash into ranked ADD candidates) is the practical implementation of volatility-scaled position building. George (2004), *52-Week High and Momentum* — proximity to the 52-week high is a positive momentum predictor; used here as a tie-breaker when ranking ADD candidates by technical strength.

Do NOT re-analyze individual stocks — the per-stock panels already did that. Reason ACROSS positions and
surface what the per-stock loop structurally cannot see.

Holdings: {HOLDINGS_JSON}
Per-stock verdicts: {ALL_VERDICTS_JSON}
Macro regime: {MACRO_REGIME}
Theme map: {THEME_MAP}
```

This seat's output goes into the final report between the signal table and the SOURCES appendix.

**After this step, if the user asked a portfolio-aware question, invoke `stock-chair`** with the synthesis
seat's output for position sizing.

---

## Step 5 — Publish to Notion (if configured)

This skill is the **single owner** of Notion publishing for stock research (`stocks-daily` delegates here).
Publishing is opt-in and silent-skip — never fail the run because of it.

1. **Read the publish target:**
   ```sh
   PAGE_ID=$(grep '^page_id:' .cache/stocks-advisor/notion.yaml 2>/dev/null | sed -E 's/.*"([a-f0-9]+)".*/\1/')
   ```
   If `.cache/stocks-advisor/notion.yaml` is missing OR `PAGE_ID` is empty → **skip silently** and finish
   the run (do NOT stop, do NOT warn).
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
   - **Title format `YYYY-MM-DD <narrative>`** — run date + a short narrative descriptor of the dominant
     theme (e.g. `2026-06-26 AI-bubble derisking — rotate to healthcare/defense`). Not a generic title.
   - Content: the full run output as Notion-flavored Markdown — the 2–3 sentence TOP RECAP first (§Output
     format per stock), then the narrative, the per-name decision tables, the SOURCES & DATA appendix
     (§Step 3.5), and the high-confidence RECAP + SETUP ALERTS (§Step 3.6). Use real Notion table blocks, not
     code-fenced text.
5. On any Notion error, report it and **continue** — never fail the run because publishing failed.
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

- [ ] The report **OPENS with the 2–3 sentence prose RECAP** (highest-confidence buy/sell to take now +
      one-line reasoning + the market narrative in one sentence) before any per-stock block or the signal table.
- [ ] Every FULL-PANEL ticker has `status='done'` in `stock_analysis`; one-line-screened names (N>12 triage)
      carry a one-line note and are listed, not dropped.
- [ ] Each stock block ends with a concrete **entry zone + bar-close trigger + market-based stop** — never a
      vague "looks good". WATCH/SKIP names what would change it.
- [ ] The technical seat **named a setup or said there is none**; no BUY without a live trigger.
- [ ] The narrative seat cited ≥2 real article URLs it **actually web_fetched or got from the feed scripts**
      (`feeds/wsj.ts`/`feeds/ft.ts`).
- [ ] **Inline citations:** every material news/market claim in the report body carries `[source: https://url
      (date)]` immediately after the claim — not appendix-only (the SOURCES appendix is in addition, not
      instead). Any claim without an inline source was removed or marked "(unverified)".
- [ ] **Macro regime paragraph** is present at the top of the report (Step 0.9) — 5 sentences, each with a
      named source and dateable fact; not from memory.
- [ ] **Portfolio-synthesis seat output** is present (Step 4) — factor correlation map, over-diversification
      critique, cross-position conflicts, portfolio structure verdict, cash deployment priority.
- [ ] Themes and constituents were **discovered live this run** (or the user supplied the list) — none
      asserted from memory.
- [ ] The honest base-rate note is present: single names are satellites, index is the bar; passing panels are
      hypotheses to be backtested in `strategy-discovery-backtest`.
- [ ] A TradingView screenshot is embedded inline per stock — UNLESS DEGRADED_TECH mode, where screenshots
      are skipped and each block is tagged DEGRADED.
- [ ] The smart-money seat cited ≥1 real filing/trade URL it actually web_fetched (openinsider, 13f.info,
      EDGAR, capitoltrades), or returned `NEUTRAL — INSUFFICIENT DATA`; no filing is fabricated.
- [ ] Portfolio sizing/concentration was deferred to `stock-chair`; ETF allocation to
      `tradfi-portfolio-manager`. This skill stayed on individual-stock entries only.
- [ ] recall.ts `source` was checked; if `grep-fallback`, the run is tagged MEMORY_DEGRADED and recalled
      stances flagged low-confidence.
- [ ] A consolidated **SOURCES & DATA** appendix is printed (Step 3.5) listing every web_fetched news/filing
      URL, every feed-script record, and the market-data provenance — required in normal AND DEGRADED mode.
- [ ] A final **RECAP (high-confidence only)** + **SETUP ALERTS** table is printed (Step 3.6); high-conviction-
      now and buy-on-condition names are split, never duplicated; if nothing clears the bar, that is stated.
- [ ] **Skeptic ran on every ticker** (Step 2) — no ticker skipped the adversarial challenge, even when all 5
      analysts agreed. Skeptic JSON cached at `$RUN_DIR/{TICKER}/seat_skeptic.json`.
- [ ] **CIO Synthesis ran after Skeptic** (Step 2.5) — final verdict came from the CIO prompt, not the old
      deterministic table. DISSENT LOGGED field is present in every output block (even when Skeptic was
      overruled). CIO JSON cached at `$RUN_DIR/{TICKER}/seat_cio.json`.
- [ ] **Risk Manager Check ran for every BUY/ADD verdict** (Step 2.7) — APPROVED or BLOCKED with reason in the
      output block. BUY/ADD verdicts without a Risk Manager result are invalid. Risk JSON at `seat_risk.json`.
- [ ] **Circle of Competence check passed** — the CIO stated the revenue model in 2 sentences before proceeding;
      PASS verdicts list "circle of competence: unclear" as the block reason, not a score.
- [ ] **Edge Articulation Gate ran** (Step 0.85) — every deep-dive ticker has a named edge (INFORMATION/ANALYTICAL/TIMING/STRUCTURAL) in its output block header. Tickers with NO_EDGE stayed fundamentals-only and are listed as WATCH in the signal table with the NO_EDGE note.
- [ ] **Citation audit tags present** — Skeptic's TAIL RISK and HISTORICAL ANALOG carry [LIVE]/[FILED]/[MEM] tags. Any [MEM]-only claim is flagged ⚠️[MEM-only] and the CIO addressed it in DISSENT LOGGED.
- [ ] **Portfolio tail stress numbers present** — Skeptic output includes explicit -30% and -50% dollar impact at current weight for every BUY/ADD ticker (Step 2 Skeptic prompt).
- [ ] **P0/P1/P2/P3 Execution Table present** — printed after SETUP ALERTS (Step 3.6); all BUY/ADD/EXIT/TRIM verdicts appear in the table with share counts, entry zones, triggers, and falsification conditions. No P0 without a named trigger already fired.

## Set a buy-alert (notify-me-when) — for WATCH verdicts

A WATCH verdict ("good company, wrong price — buy near $X / when RSI < V") is when to register a durable
alert that pings the user **with your entry thesis** on trigger. Use the **`mkt`** skill — it carries the
reasoning into the notification (mkt's native message cannot). Register the entry plan as a job:

```bash
cd .agents/skills/mkt/scripts
bun mkt-alert.ts add --desk stocks --symbol NVDA \
  --condition below --value 142 \
  --reason "Buy-zone = prior breakout retest + 50d reclaim; add to core, not a new satellite." \
  --channel telegram:@CryptoAiInvestor --expiry 2026-09-30
# oversold add: --condition rsi_below --value 30 --period 14 --cooldown 21600
```

A scheduled `bun check.ts` (runtime cron) fires the notification with the reasoning when the zone/indicator
hits. See `.agents/skills/mkt/SKILL.md` for trigger patterns and the per-runtime scheduler cookbook.
Recommend-only and backtest-gated — an alert is a reminder to re-evaluate, not an order.

## Done when

- Each analyzed stock has a 5-seat panel → Skeptic challenge → CIO verdict → Risk Manager gate (if BUY/ADD),
  and a concrete entry plan (zone + trigger + stop + conviction + invalidation).
- The output block shows DISSENT LOGGED for every ticker (Skeptic's best objection, even when overruled).
- The signal table with the theme map is printed; every news claim is sourced inline.
- The SOURCES & DATA appendix (Step 3.5) lists all web_fetched URLs, feed-script records, and market-data
  provenance.
- The output is flagged as an educational, backtest-gated hypothesis — not advice.
- The high-confidence RECAP + SETUP ALERTS table (Step 3.6) is printed last, splitting immediate
  high-conviction actions from buy-on-condition names.
- If `.cache/stocks-advisor/notion.yaml` is configured, a dated Notion page (title `YYYY-MM-DD <narrative>`,
  Step 5) was created and its URL returned; if not configured, publishing was skipped silently (not an error).
</content>
</invoke>
