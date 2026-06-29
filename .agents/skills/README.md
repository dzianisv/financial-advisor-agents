# Skills — Agentic Investment Portfolio Manager

opencode-compatible `SKILL.md` modules for an automated, agent-driven investment portfolio.
Each is self-contained with YAML frontmatter (`name`, `description`, `license`, `compatibility: opencode`).

**All skills are educational frameworks, not personalized financial advice.**

---

## Quick Install (any AI agent)

One command installs the full skill set from `dzianisv/backtest`:

```bash
# Claude Code
npx -y skills add dzianisv/backtest --agent claude-code

# opencode
npx -y skills add dzianisv/backtest --agent opencode

# hermes-agent
npx -y skills add dzianisv/backtest --agent hermes-agent

# openclaw  (with script files — required for watch.py / ledger.py)
npx --yes skills add dzianisv/backtest \
  --agent openclaw --yes --copy --dangerously-accept-openclaw-risks
```

Or install individual skills by adding `--skill <name>`:
```bash
npx -y skills add dzianisv/backtest --skill analyst-smartmoney-13f --agent claude-code
npx -y skills add dzianisv/backtest --skill analyst-smartmoney-13d --agent claude-code
npx -y skills add dzianisv/backtest --skill analyst-smartmoney-ptr --agent opencode
npx -y skills add dzianisv/backtest --skill analyst-smartmoney-form4 --agent claude-code
```

> The `skills` npm package (v1.5+) supports all agents above. If `npx` isn't available, install once:
> `npm install -g skills`

### hermes-agent (alternative: URL install)

```bash
# Install individual skills by raw URL
hermes skills install https://raw.githubusercontent.com/dzianisv/backtest/main/.agents/skills/analyst-smartmoney-13f/SKILL.md
hermes skills install https://raw.githubusercontent.com/dzianisv/backtest/main/.agents/skills/analyst-smartmoney-ptr/SKILL.md
hermes skills install https://raw.githubusercontent.com/dzianisv/backtest/main/.agents/skills/stocks-trend-screener/SKILL.md
hermes skills install https://raw.githubusercontent.com/dzianisv/backtest/main/.agents/skills/hedge-fund-manager/SKILL.md
```

### Setup prompt (all agents)

After installing, paste **[INVESTOR-SETUP-PROMPT.md](INVESTOR-SETUP-PROMPT.md)** to your agent — works on openclaw, hermes-agent, Claude Code, opencode, or any agent with the skills loaded.

The prompt tells the agent to:
1. Verify all skills loaded
2. Run 13F + congressional + trending stock research immediately
3. Register 4 recurring cron jobs (daily regime, weekly 13F, weekly congress, weekly trend research)

---

## Architecture — how skills delegate

> **Naming convention:** `analyst-*` = analytical lens (methodology), `investor-*` = investor-persona thinker lens (a person's worldview; bottom-up/capital allocator), `research-*` = researcher-persona thinker lens (a person's worldview; macro/thematic), `*-chair` = final decision synthesizer, `*-desk` = evidence consolidator, `feed-*` = news source adapter, `*-monitor/*-screener/*-scanner` = data/alerting, `*-connector` = broker execution bridge.

### The top-level orchestrators

```
USER QUESTION
     │
     ├── "run the fund / daily cycle"
     │        → hedge-fund-manager (PM/CIO — delegates everything)
     │
     ├── "weekly portfolio review"
     │        → tradfi-portfolio-manager (REVIEW→ASSESS→RESEARCH→DECIDE→ORDER)
     │
     ├── "should I buy/sell X?" (known ticker)
     │        → research-market workflow (manager → gather → consolidate → panel → chair)
     │
     ├── "what should I buy this week?" (open universe)
     │        → hedge-fund-committee workflow (fan-out → rank → panel → veto → brief)
     │
     ├── "should I buy/sell/hold X?" (judgment call)
     │        → multi-lens-quorum (4-7 independent lenses → synthesis)
     │
     ├── "where does X go by [date]?" (probability)
     │        → superforecasting (scenarios + probabilities + invalidation)
     │
     ├── "what does the macro panel think?"
     │        → macro-panel (7 thinker lenses → agreement/disagreement)
     │
     ├── "is it risk-on or risk-off?"
     │        → regime-detection (weighted signal ensemble → exposure dial)
     │
     ├── "manage my crypto/DeFi book"
     │        → crypto-advisor (orchestrates research-onchain + regime + dip + risk)
     │        → defi-portfolio-manager (DeFi-native: yield + risk + protocol audit)
     │
     └── "find trending stocks / any convergence?"
              → stocks-trend-screener → signal-convergence-alert
```

---

### 1. hedge-fund-manager (PM/CIO — the delegator)

The top-level orchestrator. Never analyzes directly — delegates each function to a specialist subagent, integrates findings, applies the Risk Manager's binding veto, owns the decision.

```
hedge-fund-manager (PM/CIO)
│
├── REGIME  ──────────────→ regime-detection
│                           ├── S&P vs 200d MA
│                           ├── VIX term structure
│                           ├── credit spreads
│                           ├── breadth
│                           └── yield curve
│                           → risk-on / risk-off / transition + exposure multiplier
│
├── RESEARCH ─────────────→ research-manager (triage desk head)
│                           ├── discovers available skills live
│                           ├── assembles gather seats for THIS query
│                           └── returns structured research PLAN
│
├── MACRO PANEL ──────────→ macro-panel (see §4 below)
│
├── PORTFOLIO ────────────→ portfolio-construction
│                           └── bubble-aware all-weather target weights (3 tiers)
│
├── RISK (binding veto) ──→ risk-management
│                           ├── vol target (10-12% ann)
│                           ├── drawdown de-risk (CPPI floor)
│                           ├── position cap (5% single, 15% sector)
│                           ├── gross exposure cap (from regime dial)
│                           └── DETERMINISTIC — code outside the LLM
│
├── CASH DEPLOYMENT ──────→ dip-tranches-strategy
│                           └── tiered entry at -5%/-7%/-10%/-20% from highs
│
├── REBALANCE ────────────→ rebalancing
│                           ├── calendar-check / threshold-act
│                           ├── no-trade bands
│                           └── tax-aware (new cashflows first)
│
├── TAX ──────────────────→ tax-loss-harvesting
│                           └── harvest losses without wash-sale trips
│
├── FORECASTING ──────────→ superforecasting + forecast-ledger
│                           └── Brier-scored probabilistic calls
│
└── WEEKLY NOTE ──────────→ tradfi-portfolio-manager
                            └── REVIEW → ASSESS → RESEARCH → DECIDE → ORDER
```

---

### 2. research-market workflow (unified crypto + equity research)

A single workflow handles both crypto and equity questions. The research-manager reads the query and dynamically assembles the right gather seats from the live skill catalog.

```
USER QUESTION + PORTFOLIO + DATE
          │
     ┌────┴────┐
     │ INTAKE  │ → research-manager
     └────┬────┘   (reads query + discovers skills → structured PLAN)
          │
     ┌────┴──────────────────────────────────────────────┐
     │                  GATHER (parallel)                │
     │                                                   │
     │  CRYPTO path:              EQUITY path:           │
     │  ├── crypto-onchain-data   ├── fundamental-analysis│
     │  ├── crypto-liquidity-data ├── trend-following     │
     │  ├── narrative-news        ├── dip-screener       │
     │  │   └── read-news         ├── feed-fomc          │
     │  │       (9 feeds)         └── portfolio-monitor   │
     │  ├── analyst-derivatives-positioning              │
     │  ├── analyst-smartmoney-polymarket                       │
     │  └── regime-detection                             │
     └────┬──────────────────────────────────────────────┘
          │
     ┌────┴────────┐
     │ CONSOLIDATE │ → crypto-research-desk (crypto)
     │             │   stock-research-desk  (equity)
     └────┬────────┘   (merge raw data → ONE clean sourced brief)
          │
     ┌────┴────────┐
     │    PANEL    │ → multi-lens-quorum (4-7 independent lenses)
     │             │   Each lens reads the SAME brief, votes independently
     └────┬────────┘
          │
     ┌────┴────────┐
     │   DECIDE    │ → crypto-chair (crypto) / stock-chair (equity)
     │             │   Receives: consolidated brief + panel verdicts + portfolio
     └────┬────────┘   Returns: portfolio-aware buy/sell/hold/trim/add
          │
     ┌────┴────────┐
     │   RECORD    │ → forecast-ledger (log dated call for Brier scoring)
     └─────────────┘
```

---

### 3. crypto-advisor (the crypto desk orchestrator)

Routes any crypto buy/sell/allocation question through the right sub-skills. Loads `research-onchain` internally — do NOT run both in parallel (redundant).

```
USER → crypto-advisor (classifier + invariant enforcer)
       │
       ├── research-onchain (brain — 4-pillar methodology)
       │   ├── pillar 1: global liquidity (Howell, Capital Wars)
       │   ├── pillar 2: on-chain valuation (MVRV-Z, realized price, NUPL, Puell)
       │   ├── pillar 3: sentiment/cycle (Fear & Greed, 4-phase cycle)
       │   └── pillar 4: execution (valuation-tilted DCA + vol-target sizing)
       │
       ├── regime-detection (dial — risk-on/off read)
       │
       ├── dip-tranches-strategy (ladder — tiered entry levels)
       │
       ├── risk-management (veto — leverage/sizing guardrails)
       │
       └── [optional] feed-fomc, analyst-derivatives-positioning,
                      crypto-token-screener
       │
       → packaged actionable answer (notification-first; human executes)
```

**Efficient run pattern:** `crypto-advisor` + `macro-panel` = 2 calls, zero redundancy.
Running `research-onchain` separately alongside `crypto-advisor` double-counts the same lens.

---

### 4. macro-panel (the thinker debate conductor)

Convenes 7-9 independent thinker-personas on a macro/market question. Each reads the SAME facts, judges independently, then the panel surfaces AGREEMENT vs DISAGREEMENT — not a consensus average.

```
macro-panel (conductor)
│
├── investor-lyn-alden ──────── fiscal dominance / broad money / BTC-as-hurdle
├── investor-ray-dalio ──────── debt cycles / all-weather / changing world order
├── investor-stanley-druckenmiller  liquidity / timing / "go for the jugular"
├── research-lacy-hunt ──────── deflation DISSENT seat (debt→low velocity→disinflation)
├── research-michael-pettis ─── trade / capital flows / China / S-I=CA
├── research-russell-napier ─── financial repression / structural inflation
├── investor-warren-buffett ─── bubble discipline / quality value / cash as option
├── investor-benjamin-graham ── margin of safety / Mr. Market / net-nets
└── research-morgan-housel ─── behavioral guardrail (non-voting — "enough" / room for error)
│
→ structured output:
  ├── WHERE THEY AGREE (high conviction)
  ├── WHERE THEY DISAGREE (examine both sides)
  └── DISSENT REGISTER (Lacy Hunt is the permanent bear/deflation seat)
```

---

### 5. multi-lens-quorum (the general judgment method)

The GENERAL method for any buy/hold/sell/size call. Distinct from macro-panel (which is macro-thinker-specific). Spawns 4-7 analyst subagents, each reads ONE lens/skill, judges independently on identical facts.

```
multi-lens-quorum (method — not a fixed roster)
│
│  For a CRYPTO question, might convene:
│  ├── research-onchain
│  ├── investor-lyn-alden
│  ├── investor-stanley-druckenmiller
│  └── analyst-derivatives-positioning
│
│  For an EQUITY question, might convene:
│  ├── investor-warren-buffett
│  ├── investor-benjamin-graham
│  ├── analyst-systematic-trading
│  └── fundamental-analysis
│
│  For a TIMING question, might convene:
│  ├── research-technical
│  ├── analyst-derivatives-positioning
│  ├── regime-detection
│  └── trend-following
│
→ synthesis: consensus + named dissents (never averaged away)
→ routes to: superforecasting (probability) or forecast-ledger (scoring)
```

**Three non-overlapping jobs — keep them distinct:**
- `stocks-trend-screener` finds WHICH names (discovery → watchlist)
- `multi-lens-quorum` judges WHETHER / how much (buy/hold/size verdict)
- `superforecasting` predicts WHAT happens by a date (graded probability)

They chain: scout picks → quorum judges → superforecaster times.

---

### 6. hedge-fund-committee workflow (weekly open-universe)

The SLOW tier. Runs weekly to find the next stocks to buy — open universe, no ticker needed.

```
hedge-fund-committee.workflow.js
│
├── 1. COLLECT (x6 parallel fan-out)
│      ├── regime-detection
│      ├── feed-fomc
│      ├── analyst-smartmoney-13f + analyst-smartmoney-13d
│      ├── analyst-smartmoney-ptr
│      ├── narrative-news (via feed-* adapters)
│      └── dip-screener + crypto-dip-scanner
│
├── 2. AGGREGATE by conviction
│      └── signal-convergence-alert (≥2 sources → elevated)
│
├── 3. PANEL (multi-lens-quorum)
│      └── 4+ analyst lenses, independent vote
│      └── code-enforced dissent (no groupthink)
│
├── 4. RISK VETO (binding)
│      └── risk-management (deterministic caps + CPPI)
│
└── 5. CIO DECISION
       └── ranked BUY MEMO with staged entry plans
       → reports/hedge-fund-brief-<date>.md
```

---

### 7. Discovery & alerting pipeline (FAST tier — daily cron)

Silent unless something fires. Each scanner runs independently; convergence cross-references.

```
                    DAILY CRON (parallel, independent)
                    │
    ┌───────────────┼───────────────┬──────────────────┐
    │               │               │                  │
dip-screener   crypto-dip-     analyst-smartmoney-13f          trend-stock-
(S&P 100,      scanner         (weekly 13F)       research
≥-20% from     (BTC/ETH/SOL    analyst-smartmoney-13d          (journalism →
52w high)      /BNB/AVAX,      (real-time          mention velocity)
               F&G < 25)       activist >5%)
    │               │               │                  │
    └───────┬───────┴───────┬───────┘                  │
            │               │                          │
    congressman-stock-  portfolio-monitor               │
    watch (STOCK Act    (discipline: triggers           │
    purchases)          fired? euphoria?                │
                        concentration?)                 │
            │                                          │
            └──────────────┬───────────────────────────┘
                           │
                signal-convergence-alert
                (same ticker in ≥2 pools → elevated conviction)
                           │
                     ┌─────┴─────┐
                     │ ≥2 hits   │ → DM owner (time-sensitive)
                     │ ≥3 hits   │ → auto-route to multi-lens-quorum
                     └───────────┘
```

---

### 8. News pipeline (read-news → narrative-news)

One Bun/TypeScript skill fetches every feed, normalizes to a common article record, dedups into EVENTS,
and keeps cross-run state. The narrative-news skill reads those events and tags them.

```
                          read-news (one unified pipeline)
    ┌─────────────────────────────────────────────────────────────┐
    │  feeds/  — 9 source adapters in one registry                 │
    │    crypto.ts: coindesk decrypt cointelegraph theblock        │
    │               bitcoinmagazine coinbase bloomberg             │
    │    ft.ts · wsj.ts  (canonical paywalled-macro fetchers)      │
    │                          │                                   │
    │  read_news.ts — fetch all → ingest → query / new-since       │
    │                          │                                   │
    │  news_store.ts — SQLite + FTS5 BM25                          │
    │    ├── deterministic near-dup (SimHash/Jaccard) clustering   │
    │    ├── RRF hybrid retrieval (BM25 + cluster rank)            │
    │    ├── cross-run state (event_cluster_id)                    │
    │    └── emits EVENTS (not articles) — "what's new since last" │
    └─────────────────────────────────────────────────────────────┘
                                   │
                          narrative-news / analysis-narrative
                          ├── reads NEW/updated events
                          └── tags PRICED_IN vs ACTIONABLE_CONTEXT vs NEW_CATALYST
                                   │
                          → consumed by: crypto-research-desk, stock-research-desk,
                                          crypto-advisor, stocks-advisor
```

---

### 9. Forecasting & scoring loop

```
superforecasting (Tetlock methodology)
├── constructs reference class
├── anchors to analyst-smartmoney-polymarket
│   ├── Polymarket (Gamma API)
│   ├── Kalshi
│   └── CME FedWatch / ZQ-futures-implied
├── adjusts from base rate
├── produces: scenarios × probabilities × invalidation triggers
│
└── logs to → forecast-ledger
              ├── dated probabilistic call
              ├── resolution on target date
              ├── Brier score + calibration curve
              └── per-lens/source accuracy tracking
              → "a forecast unscored is just an opinion"
```

---

### 10. Trading desks + backtest gate

```
USER: "trade X" / "day-trade for income"
       │
       ├── ALWAYS FIRST ──→ strategy-discovery-backtest (**THE GATE**)
       │                    ├── hypothesis → data → backtest
       │                    ├── no look-ahead, realistic costs
       │                    ├── walk-forward / out-of-sample
       │                    ├── deflated Sharpe
       │                    └── PASS / FAIL verdict
       │                    ("no edge found" is a valid result)
       │
       ├── PASS + crypto ──→ crypto-daytrading
       │                    ├── 24/7 bars, taker/maker fees, funding
       │                    ├── thin alt liquidity awareness
       │                    └── notification-first daily loop
       │                    └── execution: coinbase-cdp-connector
       │                        ├── DEFAULT: notification mode (human approves)
       │                        ├── testnet: base-sepolia faucet
       │                        └── live: hard-gated (creds + daily confirm + PASS + caps)
       │
       └── PASS + equity ──→ stock-daytrading
                            ├── RTH only, PDT rule, spread/slippage
                            ├── halts, hard-to-borrow shorts
                            └── notification-first daily loop
                            └── execution: robinhood-connector
                                ├── DEFAULT: notification mode (human approves)
                                └── live: hard-gated (Robinhood Agentic + daily confirm + PASS + caps)
```

---

### 11. Portfolio operations pipeline

```
portfolio-construction (target weights — bubble-aware all-weather)
├── 3 tiers: conservative / balanced / growth
├── de-concentrated equity (equal-weight, intl, value, min-vol)
├── uncorrelated diversifiers (gold, trend-following, TIPS)
└── dry-powder reserve
    │
    ├── regime-detection ──→ exposure multiplier
    │
    ├── trend-following ───→ crisis alpha overlay
    │   ├── 200d MA rule
    │   ├── dual momentum (Antonacci GEM)
    │   └── managed futures ETFs (DBMF, KMLM)
    │
    ├── dip-tranches-strategy ──→ when/how much to deploy dry powder
    │   └── tiers at -5% / -7% / -10% / -20% from 52w high
    │
    ├── rebalancing ──→ threshold-act + calendar-check
    │   ├── no-trade bands (minimize turnover)
    │   └── tax-aware (use new cashflows first)
    │
    ├── tax-loss-harvesting ──→ harvest losses w/o wash sale
    │   └── VOO↔IVV↔SPLG partner swaps
    │
    ├── risk-management ──→ DETERMINISTIC VETO (code, not LLM)
    │   ├── vol target 10-12% ann
    │   ├── max drawdown → CPPI floor
    │   ├── position cap: 5% single / 15% sector / 100% gross
    │   └── per-trade / per-day loss limits
    │
    └── portfolio-monitor ──→ discipline enforcement
        ├── trigger-fired detection (regex on Price_Flag/Next_Step)
        ├── euphoria flag (>30% above 200dMA + HIGH bubble fragility)
        ├── concentration flag (>10% of book)
        └── → materially-changed → multi-lens-quorum for verdict
```

---

### 12. DeFi portfolio manager (crypto-native, separate from tradfi)

```
defi-portfolio-manager (PM — delegates to subagent team)
│
├── portfolio analyst ──── assess current book (tokens + positions)
├── yield researcher ───── find safer/better yield opportunities
├── risk/incident auditor  protocol risk, hack history, oracle deps
├── strategy constructor ─ from→to tickets for the week
└── execution planner ──── read-only; investor signs
│
├── uses: crypto-token-screener (6-point value-accrual + BTC hurdle)
├── uses: risk-assessment (protocol/DeFi risk evaluation)
└── uses: yield-strategies (DeFi yield pool queries)
│
→ weekly cycle: assess → research → ticket → investor executes
→ NEVER holds shitty assets; reasons from crypto-native risk
```

---

### 13. Analyst lenses (independent — consumed by quorum/panel)

```
ANALYTICAL LENSES (methodology-based):
├── research-onchain ──────── 4-pillar: liquidity + on-chain + sentiment + execution
├── analyst-systematic-trading  Carver: vol-target, forecast scalars, cost speed limit
├── research-technical  long-term entry timing: Weinstein stage, 200d/30wk, RSI/MACD/vol confirm (scripts/ta.py)
├── investor-bernstein-intraday  Bernstein day-trading: set-up→trigger→follow-through (intraday only)
├── analyst-derivatives-positioning  funding, basis, OI, skew, gamma, VIX, COT, max pain
└── fundamental-analysis ── value/quality/FCF screens + backtest gate

THINKER-PERSONA LENSES (worldview-based):
├── investor-lyn-alden ─── fiscal dominance / debasement / BTC-as-hurdle
├── investor-ray-dalio ─── big debt cycle / all-weather / holy grail of diversification
├── investor-stanley-druckenmiller  "earnings don't move the market, the Fed does"
├── research-lacy-hunt ─── deflation dissent (debt→low velocity→disinflation)
├── research-michael-pettis  S-I=CA / "trade wars are class wars" / China
├── research-russell-napier  financial repression / credit guarantees / structural inflation
├── investor-warren-buffett  circle of competence / moat / margin of safety / Buffett Indicator
├── investor-benjamin-graham  Mr. Market / net-nets / Graham number / 7 criteria
└── research-morgan-housel  behavioral guardrail (non-voting) — "enough" / room for error

Each lens is a LENS, not gospel — carry per-skill Caveats.
Consumed by: multi-lens-quorum, macro-panel, research-market workflow
```

---

### 14. Evaluation & quality (the anti-reward-hacking layer)

```
skill-supervisor (propose/dispose improvement loop)
├── supervisor scores and selects
├── SEPARATE blind executor does every prompt edit + run
├── evals/ harness (evals/pm, evals/hf)
└── reject if score drops or invariant trips
    "never let one agent both edit and grade"

hedge-fund-committee-eval ── blind LLM-as-judge for committee runs (0-100)
crypto-workflow-eval ─────── blind LLM-as-judge for crypto workflow (0-100)
forecast-ledger ──────────── Brier + calibration scoring (the REAL ground truth)
                             "LLM-judges are coarse; the ledger validates over time"
```

---

### 15. Operational / infrastructure

```
liveness-monitor (DEPRECATED — retained for openclaw compat)
├── dead-man's-switch: each scan logs heartbeat
└── DMs owner ONLY when a job goes stale

bypass-paywalls (interactive — not for cron)
├── chrome-use + bypass-paywalls-clean extension
└── for FT, WSJ, Bloomberg full article body

coinbase-cdp-connector ── Coinbase CDP CLI/MCP (notification → testnet → live)
robinhood-connector ───── Robinhood agentic MCP (notification → live)
```

---

## Skill index (all ~68 skills)

### Watchlist / discovery (the inbound pipeline)

| Skill | Role | Cadence |
|-------|------|---------|
| [research-smartmoney](research-smartmoney/SKILL.md) | Smart-money family orchestrator — runs all spokes and consolidates signals | on-demand |
| [analyst-smartmoney-13f](analyst-smartmoney-13f/SKILL.md) | Pull new institutional 13F buys; dedupe ledger | weekly |
| [analyst-smartmoney-13d](analyst-smartmoney-13d/SKILL.md) | Real-time SEC 13D/13G activist filings (>5% stake) | weekly |
| [analyst-smartmoney-ptr](analyst-smartmoney-ptr/SKILL.md) | Pull STOCK Act purchase disclosures; dedupe ledger | weekly |
| [analyst-smartmoney-form4](analyst-smartmoney-form4/SKILL.md) | Pull insider Form 4 buy disclosures; dedupe ledger | weekly |
| [stocks-trend-screener](stocks-trend-screener/SKILL.md) | Read financial journalism; surface emerging tickers | weekly |
| [hedge-fund-13f-analysis](hedge-fund-13f-analysis/SKILL.md) | Deep-read a single 13F filing (EDGAR) | on-demand |
| [signal-convergence-alert](signal-convergence-alert/SKILL.md) | Cross-reference ≥2 source pools → elevated conviction | daily |

### Judgment (quorum + forecasting)

| Skill | Role |
|-------|------|
| [multi-lens-quorum](multi-lens-quorum/SKILL.md) | Convene 4-7 lenses → verdict without averaging away dissent |
| [superforecasting](superforecasting/SKILL.md) | Dated market-outcome → scored probability + falsifiable triggers |
| [analyst-smartmoney-polymarket](analyst-smartmoney-polymarket/SKILL.md) | Polymarket / Kalshi / FedWatch crowd odds |
| [analyst-smartmoney-positioning](analyst-smartmoney-positioning/SKILL.md) | Futures + options positioning, OI, skew, funding, COT |
| [analyst-smartmoney-options](analyst-smartmoney-options/SKILL.md) | Options flow, unusual activity, dark-pool prints, GEX |
| [analyst-smartmoney-darkpool](analyst-smartmoney-darkpool/SKILL.md) | Dark-pool / block-print analysis; institutional accumulation |
| [analyst-derivatives-positioning](analyst-derivatives-positioning/SKILL.md) | Futures + options positioning, OI, skew |
| [forecast-ledger](forecast-ledger/SKILL.md) | Brier + calibration scoring loop (ledger.py) |

### Portfolio operations

| Skill | Role |
|-------|------|
| [hedge-fund-manager](hedge-fund-manager/SKILL.md) | PM/CIO delegating to specialist sub-skills |
| [tradfi-portfolio-manager](tradfi-portfolio-manager/SKILL.md) | Weekly portfolio note (REVIEW→ASSESS→RESEARCH→DECIDE→ORDER) |
| [regime-detection](regime-detection/SKILL.md) | Risk-on/off → gross-exposure dial |
| [portfolio-construction](portfolio-construction/SKILL.md) | Bubble-aware all-weather target weights |
| [risk-management](risk-management/SKILL.md) | Vol target, drawdown de-risk, CPPI, caps — deterministic veto |
| [rebalancing](rebalancing/SKILL.md) | Calendar-check / threshold-act, tax-aware |
| [dip-tranches-strategy](dip-tranches-strategy/SKILL.md) | Tiered dip-buying of dry powder |
| [tax-loss-harvesting](tax-loss-harvesting/SKILL.md) | Harvest losses without wash-sale trips |
| [fundamental-analysis](fundamental-analysis/SKILL.md) | Valuation research + backtest gate |
| [trend-following](trend-following/SKILL.md) | 200d-MA / dual-momentum / managed-futures signals |
| [portfolio-monitor](portfolio-monitor/SKILL.md) | Discipline: triggers fired? euphoria? concentration? |

### Dip screeners & monitors

| Skill | Role | Cadence |
|-------|------|---------|
| [dip-screener](dip-screener/SKILL.md) | S&P 100 stocks ≥20/25/30% below 52w high; RISK_ON gate | daily |
| [crypto-dip-scanner](crypto-dip-scanner/SKILL.md) | BTC/ETH/SOL/BNB/AVAX dip + Fear&Greed + funding | daily |
| [feed-fomc](feed-fomc/SKILL.md) | Fed calendar, statement tone shift, hawkish/dovish delta | daily |

### Macro analyst panel (thinker lenses)

| Skill | Thinker |
|-------|---------|
| [macro-panel](macro-panel/SKILL.md) | Conductor — convenes the panel, surfaces agreement vs disagreement |
| [investor-lyn-alden](investor-lyn-alden/SKILL.md) | Fiscal dominance / broad-money / BTC-as-hurdle |
| [investor-ray-dalio](investor-ray-dalio/SKILL.md) | Debt cycles / all-weather risk-parity |
| [investor-stanley-druckenmiller](investor-stanley-druckenmiller/SKILL.md) | Liquidity / timing / position-sizing |
| [research-lacy-hunt](research-lacy-hunt/SKILL.md) | Deflation dissent — debt→low-velocity→disinflation |
| [research-michael-pettis](research-michael-pettis/SKILL.md) | Trade / capital-flows / China |
| [research-russell-napier](research-russell-napier/SKILL.md) | Financial repression / structural-inflation |
| [investor-warren-buffett](investor-warren-buffett/SKILL.md) | Bubble-discipline / quality-value / cash-as-option |
| [investor-benjamin-graham](investor-benjamin-graham/SKILL.md) | Rules-based value origin — margin of safety, Mr. Market |
| [research-morgan-housel](research-morgan-housel/SKILL.md) | Behavioral-finance / investor-psychology guardrail |

### Analytics / book-grounded lenses

| Skill | Source |
|-------|--------|
| [analyst-systematic-trading](analyst-systematic-trading/SKILL.md) | Robert Carver *Systematic Trading* |
| [research-technical](research-technical/SKILL.md) | Weinstein stage analysis + Grimes + Murphy (public TA frameworks) |
| [investor-bernstein-intraday](investor-bernstein-intraday/SKILL.md) | Jacob Bernstein *The Ultimate Day Trader* |
| [research-onchain](research-onchain/SKILL.md) | Michael Howell *Capital Wars* + on-chain |

### Crypto desk

| Skill | Role |
|-------|------|
| [crypto-advisor](crypto-advisor/SKILL.md) | Crypto buy-the-dip / DCA orchestrator (loads research-onchain internally) |
| [crypto-chair](crypto-chair/SKILL.md) | Final crypto decision synthesis (brief + panel → recommendation) |
| [crypto-research-desk](crypto-research-desk/SKILL.md) | Consolidate crypto gather seats → one sourced brief |
| [crypto-token-screener](crypto-token-screener/SKILL.md) | 6-point value-accrual filter + BTC hurdle rate |
| [crypto-liquidity-data](crypto-liquidity-data/SKILL.md) | Howell global liquidity, Fed BS, RRP, TGA, M2, DXY |
| [crypto-onchain-data](crypto-onchain-data/SKILL.md) | MVRV-Z, NUPL, realized price, Puell, hashrate |
| [defi-portfolio-manager](defi-portfolio-manager/SKILL.md) | DeFi book: yield + risk + protocol audit (crypto-native) |

### Equity desk

| Skill | Role |
|-------|------|
| [stock-chair](stock-chair/SKILL.md) | Final equity decision synthesis (brief + panel → recommendation) |
| [stock-research-desk](stock-research-desk/SKILL.md) | Consolidate equity gather seats → one sourced brief |
| [research-manager](research-manager/SKILL.md) | Intake/triage — discovers skills live, assembles desk for query |

### News feeds

| Skill | Source |
|-------|--------|
| [read-news](read-news/SKILL.md) | Unified Bun/TS pipeline — fetch 9 feeds (CoinDesk, Decrypt, CoinTelegraph, The Block, Bitcoin Magazine, Coinbase, FT, WSJ, Bloomberg) → dedup → SQLite/FTS5 BM25 store → query |
| [narrative-news](narrative-news/SKILL.md) | Reads read-news events → deduped events (PRICED_IN/ACTIONABLE) |

### Trading desks + execution

| Skill | Role |
|-------|------|
| [strategy-discovery-backtest](strategy-discovery-backtest/SKILL.md) | **THE GATE** — hypothesis→backtest→PASS/FAIL |
| [crypto-daytrading](crypto-daytrading/SKILL.md) | Crypto intraday income desk (24/7, fees, funding) |
| [stock-daytrading](stock-daytrading/SKILL.md) | Equity intraday income desk (RTH, PDT rule) |
| [coinbase-cdp-connector](coinbase-cdp-connector/SKILL.md) | Coinbase CDP CLI/MCP execution bridge |
| [robinhood-connector](robinhood-connector/SKILL.md) | Robinhood agentic MCP execution bridge |

### Evaluation & quality

| Skill | Role |
|-------|------|
| [skill-supervisor](skill-supervisor/SKILL.md) | Propose/dispose improvement loop (anti-reward-hacking) |
| [hedge-fund-committee-eval](hedge-fund-committee-eval/SKILL.md) | Blind LLM-as-judge for committee runs (0-100) |
| [crypto-workflow-eval](crypto-workflow-eval/SKILL.md) | Blind LLM-as-judge for crypto workflow (0-100) |

### Operational / infrastructure

| Skill | Role |
|-------|------|
| [liveness-monitor](liveness-monitor/SKILL.md) | ⚠️ DEPRECATED — dead-man's-switch for openclaw cron |
| [agentic-fund-orchestration](agentic-fund-orchestration/SKILL.md) | ⚠️ DEPRECATED — superseded by hedge-fund-manager |
| [bypass-paywalls](bypass-paywalls/SKILL.md) | Interactive paywall bypass (chrome-use + extension) |

---

## Runnable helpers

- `analyst-smartmoney-13f/watch.py` — dedup ledger + roster for institutional filings.
- `analyst-smartmoney-ptr/watch.py` — STOCK Act fetch + dedup ledger.
- `forecast-ledger/ledger.py` — Brier/calibration scoring for dated forecasts.
- `regime-detection/regime_monitor.py` — daily regime score → exposure multiplier.
- `dip-tranches-strategy/check_drawdown.py` — drawdown-from-52w-high → which tranche fires.
- `dip-screener/dip_screener.py` — S&P 100 dip scan with convergence pool output.
- `crypto-dip-scanner/crypto_dip_scanner.py` — crypto dip scan + Fear & Greed.
- `signal-convergence-alert/convergence.py` — cross-pool convergence detection.
- `portfolio-monitor/scripts/portfolio_monitor.py` — discipline check on reviewed CSV book.

## Provenance

Backtest evidence in `../research/` and `../backtests/`. Strategy written up in `../strategy/` (v3 current).
Run notification-first; paper-trade before live; hard caps in code outside the LLM.
