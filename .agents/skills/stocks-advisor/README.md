# stocks-advisor

Analyzes individual stocks one at a time — runs a **5-seat analyst panel** (fundamental / technical / narrative / sentiment / smart-money) per stock and outputs a concrete **entry plan** (price zone + bar-close trigger + market-based stop) with a **BUY / WATCH / SKIP** decision.

For portfolio reviews: outputs HOLD / ADD / TRIM / EXIT per position with a tax-harvest table, cash deployment plan, and a cross-portfolio synthesis seat.

Input: user-supplied ticker list, a Google Sheet of holdings, or stocks discovered live from a named market theme.

> Educational analysis, not financial advice. Single stocks are satellites; the index is the bar.

## Architecture

```mermaid
flowchart TD
    USER(["User prompt"])

    MEM["Step -1 · Load prior memory
bun portfolio-memory/recall.ts"]
    SHEET["Step 0 · Load Google Sheet (optional)
gws sheets +read
ticker, qty, cost_basis, pnl_pct"]
    EDGE["Step 0.85 · Cohen Edge Gate
Must name edge type:
INFORMATION / ANALYTICAL / TIMING / STRUCTURAL
NO_EDGE → fundamentals-only WATCH, skip panel"]
    MACRO["Step 0.9 · Macro-regime synthesis — run ONCE
feeds/wsj.ts + feeds/ft.ts + Yahoo Finance
→ 5-sentence paragraph · RUN_DIR/macro_regime.txt"]

    SEED["Step 1 · Seed ticker queue"]

    subgraph SEQ ["Sequential per-ticker loop — one ticker at a time (TradingView single slot)"]
        direction TB

        subgraph SEATS ["Step 2 · 5 investor seats — PARALLEL subagents per ticker"]
            direction LR

            subgraph SF ["Seat 1 · Fundamental
investor-warren-buffett"]
                direction TB
                SF_FY["fundamentals.py
fwdPE · PEG · FCF yield
rev growth · ROE · margins"]
                SF_WEB["web_fetch
IR page · SEC 10-Q/10-K
moat evidence"]
                SF_OUT["STRONG / GOOD
FAIR / POOR"]
                SF_FY --> SF_OUT
                SF_WEB --> SF_OUT
            end

            subgraph ST ["Seat 2 · Technical
investor-stanley-druckenmiller"]
                direction TB
                ST_TV["TradingView MCP
RSI · MACD · BB · EMA
OHLCV · 52w hi/lo · screenshot"]
                ST_FY["fundamentals.py
ma50 · ma200 · vs200d"]
                ST_OUT["SETUP_NAMED
NO_SETUP / BROKEN
+ entry zone · trigger · stop"]
                ST_TV --> ST_OUT
                ST_FY --> ST_OUT
            end

            subgraph SN ["Seat 3 · Narrative / Macro
investor-lyn-alden"]
                direction TB
                SN_MR["Read macro_regime.txt
fiscal dominance · liquidity cycle"]
                SN_NEWS["read_news.ts --source ft,wsj
feeds/wsj.ts · feeds/ft.ts
No URL = not a source"]
                SN_OUT["EARLY / MID
LATE / FADING"]
                SN_MR --> SN_OUT
                SN_NEWS --> SN_OUT
            end

            subgraph SS ["Seat 4 · Cycle / Regime
investor-ray-dalio"]
                direction TB
                SS_FY["fundamentals.py
short_pct · inst_pct · rec_mean
All-Weather quadrant context"]
                SS_OUT["QUIET_ACCUM
NEUTRAL · CROWDED
EXTREME"]
                SS_FY --> SS_OUT
            end

            subgraph SM ["Seat 5 · Smart-Money
research-smartmoney"]
                direction TB
                SM_FETCH["web_fetch per-ticker:
openinsider.com Form 4
13f.info · EDGAR 13D/13G
capitoltrades.com PTR"]
                SM_OUT["ACCUMULATING
DISTRIBUTING
NEUTRAL"]
                SM_FETCH --> SM_OUT
            end
        end

        subgraph BSC ["BSC Decision Chain (default hierarchy)"]
            direction TB
            SKEP["Step 2.3 · Skeptic
research-lacy-hunt
Adversarial challenge · [LIVE]/[FILED]/[MEM] tags
-30% / -50% tail stress · deflation dissent"]
            CIO["Step 2.5 · CIO Synthesis
Weighs 5 seats vs Skeptic
DISSENT LOGGED even when Skeptic overruled"]
            RISK["Step 2.7 · Risk Manager
risk-management
APPROVED $X (N% book) or BLOCKED
Required for every BUY / ADD"]
            SKEP --> CIO --> RISK
        end

        PERSIST["bun portfolio-memory/remember.ts"]

        SF_OUT & ST_OUT & SN_OUT & SS_OUT & SM_OUT --> SKEP
        RISK --> PERSIST
    end

    EXEC["Step 3.6 · P0/P1/P2/P3 Execution Table
Soros format — share counts · entry zones
triggers · falsification condition per row"]

    SYNTH["Step 4 · Portfolio-synthesis seat — once after loop
model opus / effort xhigh

1. FACTOR CORRELATION MAP — flag any factor > 25% book
2. OVER-DIVERSIFICATION CRITIQUE — > 40 names = index noise
3. CROSS-POSITION CONFLICTS — ADD + TRIM on same factor
4. PORTFOLIO STRUCTURE VERDICT — biggest risk + one action
5. CASH DEPLOYMENT PRIORITY — top 3 ADD candidates"]

    SIGNAL["Signal table
Ticker · Decision · Conv · Entry · Trigger · Theme"]
    CHAIR[["stock-chair
sizing · concentration"]]

    USER --> MEM --> SHEET --> EDGE --> MACRO --> SEED --> SEQ
    PERSIST --> EXEC --> SYNTH --> SIGNAL --> CHAIR
```

## Two input modes

| Mode | Input | Verdicts |
|---|---|---|
| **Watchlist / Theme discovery** | Explicit tickers or live theme discovery | BUY / WATCH / SKIP |
| **Portfolio review** | Google Sheet URL (holdings + cost basis) | HOLD / ADD / TRIM / EXIT + tax-harvest table + portfolio synthesis |

## The 5 seats

Each seat is grounded in a named investor skill from `.agents/skills/`. The skill's SKILL.md and `references/` provide the framework; the seat injects the per-ticker data package and asks the lens to apply its method.

| Seat | Investor skill | Framework | Data source | Output |
|---|---|---|---|---|
| **Fundamental** | `investor-warren-buffett` | Moat → owner earnings → margin of safety. FCF yield, PE, PEG, ROE. Circle of competence gate. | Injected — `fundamentals.py` (yfinance) | STRONG / GOOD / FAIR / POOR |
| **Technical** | `investor-stanley-druckenmiller` | STF: Set-Up → Trigger → Follow-Through. Liquidity + momentum + timing. Named setup + bar-close trigger + market-based stop. No trigger = no trade. | Injected — TradingView MCP | SETUP_NAMED / NO_SETUP / BROKEN |
| **Narrative / Macro** | `investor-lyn-alden` | Fiscal dominance + broad-money cycle + theme phase. `read_news.ts` for discovery; feed scripts for verbatim citation. No fabrication. | Injected — `macro_regime.txt` + live news | EARLY / MID / LATE / FADING |
| **Cycle / Regime** | `investor-ray-dalio` | Debt-cycle quadrant (growth/inflation rising/falling). Contrarian positioning read: short%, institutional%, analyst consensus. All-Weather regime context. | Injected — `fundamentals.py` (yfinance) | QUIET_ACCUM / NEUTRAL / CROWDED / EXTREME |
| **Smart-Money** | `research-smartmoney` | Disclosed institutional flows: Form 4 (openinsider), 13F (13f.info), 13D (EDGAR), PTR (capitoltrades). ≥2 classes agreeing → verdict. | Live `web_fetch` | ACCUMULATING / DISTRIBUTING / NEUTRAL |

**BSC Hierarchy — additional named seats after the 5-seat panel:**

| Role | Skill | Function |
|---|---|---|
| **Skeptic** | `research-lacy-hunt` | Deflation / over-indebtedness dissent. Adversarial challenge of every thesis before CIO decides. Tags every unverified claim `[MEM]`. |
| **CIO** | BSC Hybrid logic | Weighs 5-seat panel + Skeptic. DISSENT LOGGED even when Skeptic is overruled. |
| **Risk Manager** | `risk-management` | APPROVED / BLOCKED per BUY/ADD. Dollar amount, % book, position limit enforcement. |

**Optional extended panel (skills available, not wired by default):**

| Skill | When to add |
|---|---|
| `investor-benjamin-graham` | Deep-value screens — sub-book or net-net candidates where strict quantitative gates apply |
| `research-michael-pettis` | International / EM names — global trade imbalances, China exposure, FX flow lens |
| `research-russell-napier` | Financial repression plays — forced-savers, regulated capital, long-duration sovereign debt |
| `research-morgan-housel` | Behavioral guardrail — non-voting, flags recency bias and sizing psychology |

## Step 0.9 — Macro-regime synthesis

Runs **once** before the per-stock loop. Produces a shared 5-sentence paragraph injected into every seat's data package:

| Dimension | Content |
|---|---|
| Fed/rates | Fed stance + next meeting expectation + one named CME/FOMC data point |
| Growth/earnings | Current earnings season signal or GDP read, specific number |
| Inflation | Latest CPI/PCE print with date |
| Geopolitics | Single most market-relevant geopolitical fact this week |
| Liquidity/risk appetite | Equity trend + vol signal (VIX level, index weekly move) |

Anti-hallucination rule: every sentence names a source and a specific, dateable fact. No training-memory claims.

## Step 4 — Portfolio-synthesis seat

Runs **once** after the per-stock loop completes. A single `/model opus /effort xhigh` subagent that reasons across all positions simultaneously — the cross-portfolio view the per-stock loop structurally cannot produce:

1. **Factor correlation map** — groups holdings by shared risk factor; flags >25% concentration
2. **Over-diversification critique** — if >40 names, identifies index-like positions (Carver: marginal diversification benefit falls past ~20 uncorrelated instruments)
3. **Cross-position conflicts** — ADD/TRIM pairs sharing the same factor exposure
4. **Portfolio structure verdict** — biggest structural risk + single highest-impact action
5. **Cash deployment priority** — top 3 ADD candidates ranked by portfolio-level fit

## Verdict rules

```
BUY   = Fundamental ≥ GOOD  AND  SETUP_NAMED  AND  phase ∈ {EARLY,MID}  AND  Sentiment ≠ EXTREME
WATCH = Fundamental ≥ GOOD  BUT  NO_SETUP (wait for trigger)
SKIP  = Fundamental = POOR  OR   phase ∈ {LATE,FADING}  OR  Technical = BROKEN
SKIP dominates all other signals.
Conviction 1–5: start at 3, ±1 per alignment signal.
Smart-money is a conviction modifier (not a primary driver):
  +1 if ACCUMULATING with ≥2 other seats aligned
  −1 if DISTRIBUTING (also caps BUY conviction at 3/5)
```

## Hard constraints

- **TradingView MCP lives only in the orchestrator** — subagents receive injected data, cannot call MCP.
- **One chart slot** — data pull is strictly sequential, one ticker at a time.
- **ETF / sleeve allocation** → `tradfi-portfolio-manager`. This skill is individual stocks only.
- **Portfolio synthesis** → `stock-chair`. This skill provides the synthesis input; `stock-chair` owns sizing decisions.

## Layout

| Path | What |
|---|---|
| `SKILL.md` | Full operating instructions with source citations |
| `scripts/fundamentals.py` | yfinance data helper — writes `{TICKER}.json.out.json` |
| `references/seat-prompts.md` | Per-seat subagent prompt templates |
