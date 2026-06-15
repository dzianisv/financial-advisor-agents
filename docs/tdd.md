# TDD — AI Agent Investment Advisor

Aligns to `docs/prd.md`. RECOMMEND-ONLY. Never trades. Honest-or-`[UNAVAILABLE]`. Same-day DM for next Google/SanDisk/BTC-dip before window closes.

## 1. Architecture

Four layers. Data flows up, decision down, alert out.

```
 (d) NOTIFY        agent-native delivery on the cron job's own target (NO osascript)
                        ▲  openclaw `cron --target telegram` | claude-code push+connector | hermes `--target telegram`; SILENT/[SILENT] else
 (c) SCHEDULER     each backend's NATIVE cron (heartbeat is only a stuck-task nudge)
                        ▲  openclaw `cron create --cron` | claude-code /loop+CronCreate+Routines | hermes `cron create`
 (b) SKILL         agent READS skill, EXECUTES it (a script .py OR pure web_fetch/agent tools — NOT all skills are python), applies gate
                        ▲  regime gate, F&G gate, ≥2-source gate, risk VETO
 (a) DATA          a skill's script (.py) OR the agent's web_fetch/browser tools — deterministic where scripted, no fabrication, [UNAVAILABLE] on fail
                        live web: yfinance / FRED / alternative.me / SEC EDGAR / FT-WSJ / Polymarket
```

- (a) Data: scripted skills (`.py`, `--json` contract, exceptions → skip/empty, never invent) AND prompt-only skills that fetch via the agent's `web_fetch`/browser (e.g. fomc-monitor, trend-stock-research, 13f-watch). Mixed by design.
- (b) Skill: the judgment layer. Runs its script or web tools, checks gates, writes pools or emits a result.
- (c) Scheduler: the backend's NATIVE cron fires the agent (§3). Heartbeat is NOT the scheduler — it only nudges a stuck/overdue task.
- (d) Notify: agent-native delivery on the job's configured target; non-`SILENT` output → owner channel. DM = something real fired.

### 1a. Complete wiring — DAILY (every skill, where it plugs in)

The backend's NATIVE CRON fires the agent on each slot. The agent runs the skill (a `.py` script for
the scanners, OR pure `web_fetch`/agent tools for fomc-monitor / trend-stock-research / 13f-watch — not
all skills are python), applies the gate, then either DMs the owner or writes a pool row. Cron state
persists in the backend's own store (openclaw SQLite / hermes `jobs.json`) — no separate state file.

> NOTE (v1, being superseded): the daily scanners below are LOOSELY coupled — each fires its own DM and
> drops rows into `/tmp` pools that convergence + the weekly brief read. §8 specifies the v2 redesign:
> a hedge-fund ORG of role-owned agent-employees, fan-out → aggregate → investor panel → one decision.

```
 SCHEDULER PRIMITIVE  ── openclaw AGENT CRON (heartbeat = light backup) │ claude-code /loop+CronCreate (durable: Routine) │ hermes sched
        │  each cron job fires at its own fixed UTC time (state in backend store, not a file)
        ▼
 ┌──07:45────────┐ ┌──07:50──────────┐ ┌──08:00──────────┐ ┌──08:15──────────┐ ┌──08:30──────────────┐
 │ dip-screener  │ │ crypto-dip-     │ │ regime-detection│ │ trend-stock-    │ │ signal-convergence- │
 │ dip_screener  │ │ scanner         │ │  + fomc-monitor │ │ research(broad) │ │ alert  convergence  │
 │ .py           │ │ crypto_dip_     │ │ regime_monitor  │ │ web/browser     │ │ .py                 │
 │               │ │ scanner.py      │ │ .py + web_fetch │ │ tools           │ │                     │
 │ yfinance      │ │ yfinance +      │ │ yfinance SPY/   │ │ FT/WSJ/SA       │ │ reads pools+ledgers │
 │ SP100[100]    │ │ alternative.me  │ │ ^VIX/^VIX3M +   │ │ paywall-aware   │ │                     │
 │               │ │ + binance(451)  │ │ FRED OAS        │ │                 │ │                     │
 │ GATE:         │ │ GATE:           │ │ GATE:           │ │ GATE: none      │ │ GATE:               │
 │ ≤-30% (52w high)     │ │ ≤-30% (52w high)       │ │ regime flip vs  │ │ (collect only)  │ │ ticker in ≥2        │
 │ AND RISK_ON   │ │ AND F&G<25      │ │ yesterday OR    │ │                 │ │ ≥2 pools (may correlate)   │
 │               │ │ (funding=bonus) │ │ new FOMC stmt   │ │                 │ │ (≥3 → quorum)       │
 └───┬───────┬───┘ └───┬─────────────┘ └───┬─────────────┘ └───┬─────────────┘ └───┬─────────────────┘
     │       │         │                   │                   │                   │
   DM◄┘    MED→        DM◄─ (extreme       DM◄─ (if changed)  append ticker      DM◄─ (≥2 src)
   (HIGH)  pools/dip_   fear+dip)           else SILENT        pools/narrative      else SILENT
           candidates                                          .jsonl
           .jsonl │                                              │
                  └───────────────► POOLS ◄───────────────────────┘
                          ~/.openclaw/workspace/investor/pools/dip_candidates.jsonl, ~/.openclaw/workspace/investor/pools/narrative.jsonl,
                          13f ledger, congress ledger  ──► read by convergence (08:30) + weekly brief
```

Reused signal skills feeding the pools/brief: `13f-watch` + `congressman-stock-watch` (write their
dedup ledgers, deduped, weekly), `portfolio-monitor` (holdings triggers → PRIORITY ACTIONS in brief),
`prediction-market-odds` (Fed/Polymarket odds, consumed by fomc + weekly macro context).

### 1b. Complete wiring — WEEKLY brief (the dynamic workflow)

> **v1 — SUPERSEDED by §8** (`.agents/workflows/hedge-fund-committee.workflow.js`, 5-phase org). The
> 3-phase sketch below is kept only to illustrate the fan-out/fan-in shape.

`09:30 Mon` fires the committee workflow (claude-code dynamic workflow; openclaw/hermes run the
same pipeline serially in-agent). Parallelism is the design: independent lenses never block.

```
 09:30 Mon  ──►  hedge-fund-committee.workflow.js   (3 phases, fan-out/fan-in)
 ───────────────────────────────────────────────────────────────────────────────────────
 PHASE 1  COLLECT          parallel() × 6 agents — one skill each
   regime-detection ┐ fomc-monitor ┐ 13f-watch ┐ congressman-stock-watch ┐ trend(narrative) ┐ dips ┐
        each → CAND_SCHEMA {candidates[], summary}                                                  │
        cross-ref:  bySources[ticker] → Set(source)   ──►  rank by n_sources  ──►  TOP 5            │
                    (ticker in ≥2 sources = elevated conviction)                                    ▼
 PHASE 2  QUORUM           parallel: 5 candidates × 4 lenses  (multi-lens-quorum)                   │
   ┌ analytics-warren-buffett ┐                                                                     │
   ┤ analytics-stanley-druckenmiller ├ each → VERDICT {verdict, conviction1-5, reason,              │
   ┤ analytics-lyn-alden            │              invalidation, dissent}                           │
   └ fundamental-analysis ──────────┘   (macro-panel = macro backdrop; dissent preserved)           ▼
 PHASE 3  SYNTHESIZE       per candidate → risk-management VETO  (name>10% book OR RISK_OFF → VETO)  │
        final agent writes INVESTMENT BRIEF:                                                        │
        header(REGIME/FED) · PRIORITY ACTIONS · NEW BUY IDEAS(risk=PASS only) · HOLDS · CANT VERIFY ▼
                                                              ──────────────────────────────► DM owner
```

### 1c. Skill → wiring map (honest: wired vs roster-only)

| Skill | Wired at | Role |
|---|---|---|
| `dip-screener` | daily 07:45 | stock dip alert + MED→pool |
| `crypto-dip-scanner` | daily 07:50 | crypto dip alert |
| `regime-detection` | daily 08:00 + weekly P1 | RISK_ON/OFF gate (gates every buy) |
| `fomc-monitor` | daily 08:00 + weekly P1 | Fed tone delta |
| `trend-stock-research` | daily 08:15 + weekly P1 | narrative pool (catches SanDisk buildup) |
| `signal-convergence-alert` | daily 08:30 | ≥2-source DM (the SanDisk pattern) |
| `13f-watch` | weekly P1 | new institutional buys → ledger → convergence |
| `congressman-stock-watch` | weekly P1 | STOCK Act buys → ledger → convergence |
| `multi-lens-quorum` | weekly P2 | buy/sell/hold verdict engine |
| `macro-panel` + `analytics-*` | weekly P2 | the quorum lenses + macro backdrop |
| `fundamental-analysis` | weekly P2 | valuation lens |
| `risk-management` | weekly P3 (+ daily gate) | VETO authority |
| `portfolio-monitor` | weekly P3 | holdings triggers → PRIORITY ACTIONS |
| `prediction-market-odds` | weekly P1 (via fomc) | crowd odds for Fed/macro |
| `forecast-ledger` | weekly committee cron (logs each DM'd buy, scores 30/60/90d) | the feedback loop — WIRED, but no scored cycles yet |
| `superforecasting` | roster — not yet wired | dated probability/timing; future per-candidate use |
| `mention_velocity.py` (in trend-stock-research) | daily 08:10 | narrative-velocity counter → feeds convergence pool (BUILT) |
| `liveness-monitor` | daily 09:00 health cron | dead-man's-switch over the daily jobs (BUILT) |
| watchlist-monitor / recommendation-journal | CUT (folded into portfolio-monitor / forecast-ledger) | not separate skills — see AGENTS.md anti-bloat |

## 2. Skills

| skill | script | data source (exact) | failure mode | alert trigger |
|---|---|---|---|---|
| dip-screener | `dip_screener.py` | yfinance, `SP100[]` (100 tickers), 1y `Close` | batch try/except → skip batch; ticker drop → skip | HIGH (`≤−30%` from 52w high) AND regime=RISK_ON → DM. MEDIUM (`−25..−30%`) → `~/.openclaw/workspace/investor/pools/dip_candidates.jsonl` |
| crypto-dip-scanner | `crypto_dip_scanner.py` | yfinance BTC/ETH/SOL/BNB/AVAX/LINK `-USD`; F&G `api.alternative.me/fng/?limit=1`; funding `fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT` | F&G/funding fetch fail → `None` (omit line); funding 451 geo-block → omit | PRIMARY: any coin `≤−30%` from ATH AND F&G `<25` → DM. Funding = bonus only, never required |
| signal-convergence-alert | `convergence.py` | reads `~/.openclaw/workspace/investor/pools/dip_candidates.jsonl`, `~/.openclaw/workspace/investor/pools/narrative.jsonl`, 13F ledger (`~/.openclaw/workspace/investor/13f/recommended.jsonl`, 14d), congress ledger (`…/congress/recommended.jsonl`, 14d) | missing pool → skipped silently; bad JSON line → skipped | `n_sources ≥ 2` same ticker → DM; `≥ 3` → route `/multi-lens-quorum` |
| regime-detection | `regime_monitor.py` | yfinance `SPY`,`^VIX`,`^VIX3M`; FRED CSV `BAMLH0A0HYM2` | FRED fail → `credit=0`; VIX NaN → `vix_ts=0` | weights: sma200×3, vix_ts×2, credit×2 → score → RISK_ON/NEUTRAL/RISK_OFF |

Tiers — dip stock: HIGH `≤−30`, MED `≤−25`, WATCH `≤−20`. Crypto: HIGH `≤−40`, MED `≤−30`, WATCH `≤−20`.
Regime map: `score≥0.5`→1.0x RISK_ON | `≥0.0`→0.7x NEUTRAL | `≥−0.5`→0.5x RISK_OFF(mild) | `<−0.5`→0.3x RISK_OFF.

## 3. Proactive Scheduling — 3 backends

Same skills, same 6 slots. Each backend uses its NATIVE primitive — no shared scheduler. **TZ caveat:**
openclaw HEARTBEAT.md checks **UTC**; claude-code `/loop`/`CronCreate`/Routines fire in **local TZ**;
hermes per its scheduler. Pick the slot times per backend so they land at the same wall-clock moment.

### openclaw — AGENT CRON (primary) + heartbeat (light backup) (`setup-openclaw.md`)
- **Reality (verified live 2026-06-14): the investor agent HAS native cron and it is the primary scheduler.**
  It already runs ~13 jobs (e.g. `0 8 * * 1-5 UTC` regime+Fed, `15 8 * * 1-5` journalism, `0/5/30 9 * * 1`
  weekly 13F/congress/brief). We added the 3 missing dip jobs:
  `45 7 * * 1-5` stock dip · `50 7 * * *` crypto dip · `30 8 * * 1-5` convergence — each SILENT-unless-alert.
- Cron prompt pattern: "Run `python3 ~/.openclaw/workspace/investor/skills/<skill>/<script>.py --json`,
  apply the gate, DM only if it fires, else `NO_REPLY`." Fixed UTC, reliable, survives restart.
- **heartbeat** (`agents.defaults.heartbeat { every:15m, lightContext, target:last }`) stays as a LIGHT
  "did anything urgent change" backup — NOT the full scans (a per-agent `HEARTBEAT.md` that re-ran the
  scans was removed to avoid double-firing what cron owns).
- Skills + scripts live in the agent sandbox at `/home/node/.openclaw/workspace/investor/skills/<skill>/`
  (python3.12 + yfinance + Yahoo reachable there — distinct from the `kubectl exec` container).

### claude-code — `/loop` + `/goal` + workflows (`setup-claudecode.md`)
- NOT OS crontab → `claude -p`: that's stateless and writes to stdout, no native notify path back to the owner.
- **In-session recurring:** `/loop` + `CronCreate`/`CronList`/`CronDelete` (5-field cron, session-scoped). Agent stays ALIVE between turns → notifies via its own tools. Daily playbook in `.claude/loop.md` (same time-gated logic as openclaw `HEARTBEAT.md`). Self-paced `/loop` (no interval) lets Claude pick the gap each iteration. **Limits: 7-day expiry, fires only while session running+idle, cleared on new convo (restored on `--resume`).**
- **Completion driver:** `/goal "<brief produced via /hedge-fund-committee AND pushed> or stop after 25 turns"` — a fast-model Stop-hook evaluator re-runs turns until the condition holds. Pair with auto mode.
- **Durable unattended:** **Routines** (Anthropic cloud, min 1h, runs machine-off, fresh clone) or **Desktop scheduled tasks** (local, min 1m, local files+venv) — one task per cadence slot. This is the production path; `/loop` is for an open session.
- **Weekly brief = dynamic workflow:** `ultracode` keyword (or saved `/hedge-fund-committee`) authors+runs `hedge-fund-committee.workflow.js`, fanning quorum lenses in PARALLEL; returns the brief, loop/routine pushes it.
- **Notify:** in-session/routine agent is alive → mobile **push** (ping) + messaging connector (Telegram MCP, full brief text). No external sender.
- Auth: `ANTHROPIC_API_KEY` (or routine/connector creds). Subscription headless draws Agent SDK credit (effective 2026-06-15).

### hermes-ai — hermes scheduler / crontab (`setup-hermes.md`)
- `hermes -s <skills> -p "$1"` one-shot. Register slots in native scheduler, else crontab (`CRON_TZ=UTC`).
- Mandate: paste `AGENTS.template.md` into hermes investor system prompt (persists across sessions).
- URL skill install pulls SKILL.md only → vendor `.py` via `npx skills add … --copy`.

### Cadence (identical across backends)
| UTC | Days | Task | DM only if |
|---|---|---|---|
| 07:45 | M–F | dip-screener | HIGH dip AND RISK_ON |
| 07:50 | M–F | crypto-dip-scanner | coin `≤−30%` AND F&G`<25` |
| 08:00 | M–F | regime + fomc | regime flipped OR new FOMC |
| 08:15 | M–F | trend-stock-research broad | never — append `~/.openclaw/workspace/investor/pools/narrative.jsonl` |
| 08:30 | M–F | signal-convergence-alert | ticker in ≥2 sources |
| 09:30 | Mon | weekly brief | always |

## 4. Data Contracts

`dip_screener.py --json` → array:
```json
[{"ticker":"GOOGL","current":150.2,"ath_52w":214.0,"pct_from_ath":-29.8,"sma200":175.1,"pct_vs_200d":-14.2,"conviction":"MEDIUM"}]
```

`crypto_dip_scanner.py --json`:
```json
{"dips":[{"ticker":"BTC","current_usd":61000,"ath_52w_usd":108000,"pct_from_ath":-43.5,"sma200_usd":78000,"pct_vs_200d":-21.8,"conviction":"HIGH"}],
 "fear_greed":{"value":18,"label":"Extreme Fear"},"btc_funding_rate_pct":-0.012}
```
`fear_greed`/`btc_funding_rate_pct` may be `null` (fetch fail / geo-block).

`convergence.py --json`:
```json
{"min_sources":2,"convergences":[{"ticker":"WDC","sources":["13f","dip","journalism"],"n_sources":3,"notes":["dip: -31% from 52w high","journalism: 3 FT/WSJ mentions"]}],"pools_read":["~/.openclaw/workspace/investor/pools/dip_candidates.jsonl"]}
```

`regime_monitor.py --json`:
```json
{"regime":"RISK_ON","exposure_multiplier":1.0,"score":0.71,"signals":{"sma200":1,"vix_ts":0,"credit":1},
 "weights":{"sma200":3,"vix_ts":2,"credit":2},"price":..,"sma200":..,"vix":..,"vix3m":..,"hy_oas_pct":..,"note":".."}
```

Pool files = JSONL, one obj/line, each needs `ticker` (or `symbol`); optional `note`/`reason`/`why`; ledgers add `date`/`recorded`/`ts` for 14d window. Convergence keys on `ticker` upper-cased.

`.heartbeat-state.json` = flat `task→YYYY-MM-DD`:
```json
{"dip-screener":"2026-06-14","crypto-dip-scanner":"2026-06-14","regime-fed":"2026-06-14","journalism":"2026-06-14","convergence":"2026-06-14","weekly-brief":"2026-06-08"}
```

## 5. Weekly committee = the SLOW-tier decision engine

**The authoritative spec is §8** (`.agents/workflows/hedge-fund-committee.workflow.js`, the 5-phase org).
The old 3-phase sketch that used to live here is superseded — do not implement it. In short, the weekly
run is: analyst fan-out (parallel, open-universe discovery) → aggregate by conviction (n_sources, flow_only
down-weight) → 4-lens panel voting INDEPENDENTLY with **code-enforced dissent** (`minorityVote()`) → CRO
`/risk-management` veto + sizing ceilings → CIO **ranked BUY memo**. See §8 for phases, schemas, and the
anti-groupthink protocol.

## 6. Known Limitations / Failure Modes

- **Capitol Trades (congressman-stock-watch):** 403/429 from pod network (Cloudflare/Vercel bot-block) → degrades to `[SIGNAL UNAVAILABLE]`, no fabrication. Convergence simply loses that pool.
- **Binance funding (`fapi.binance.com`):** geo-blocked 451 from US/pod → crypto scanner omits funding line. Alert logic does NOT require funding — dip+F&G is primary trigger.
- **regime-detection single point of failure:** lost stooq fallback → now Yahoo `query2`/yfinance single source. Robustness regression. FRED CSV verified working.
- **yfinance multi-download drops a ticker** (e.g. MMC "delisted") → handled gracefully (`if col not in data.columns: skip`), no crash, that name silently absent.
- **A SKILL.md on disk is NOT validated.** Every modification MUST run the execute→evaluate→improve loop (AGENTS.md). Verify load: `node openclaw.mjs skills list --agent investor --json` → `eligible:true && modelVisible:true`.

## 7. Security / Invariants

- **RECOMMEND-ONLY.** No trade tools wired. Output = candidates for quorum, never orders.
- **No secrets in skills.** Free data only (yfinance/FRED/alternative.me). Auth (API key) lives in cron/pod env, never in SKILL.md or `.py`.
- **No fabricated numbers.** Fetch fail → `[UNAVAILABLE]`/`null`. Honest or silent.
- **risk-management VETO** over every buy: any name >10% book OR RISK_OFF → VETO all buys.
- **Dedup ledgers idempotent.** Never re-propose a ticker already in 13F / congress ledger.
- **Silence default.** A DM = a real fired condition; no "all quiet" chatter.

## 8. v2 — Hedge-fund ORG of agent-employees (the decision architecture)

The v1 daily scanners are LOOSELY coupled (each DMs alone, /tmp pools). v2 models a hedge fund: every
skill is an **employee with a role and ownership**; signals fan out, aggregate, and a **panel decides one
coherent call**. Grounded in TradingAgents (arXiv:2412.20138 — analysts→bull/bear debate→trader→risk→fund
manager), FinRobot (Director-over-specialists), Anthropic orchestrator-workers, and real IC practice
(analysts→CIO chair→PM owns→CRO veto). Reuse-first: the employees already exist as skills.

### The org chart (existing skills = employees)
| Desk | Employees (skills) | Owns | Decides? |
|------|--------------------|------|:--------:|
| Research analysts | 13f-watch, congressman-stock-watch, trend-stock-research, regime-detection, fomc-monitor, prediction-market-odds, dip-screener, crypto-dip-scanner, fundamental-analysis | gather a structured report | NO |
| Chief of staff | signal-convergence-alert + the workflow aggregator | cluster by ticker, build ONE briefing packet | NO |
| Investment committee | multi-lens-quorum lenses (Buffett/Graham/Druckenmiller/Lyn-Alden/**Lacy-Hunt dissent seat**), macro-panel, superforecasting | debate the packet, vote independently | advise |
| CRO | risk-management | binding VETO + sizing | gate |
| PM / CIO | hedge-fund-manager | integrate, write the memo, own it | YES |

### Two tiers (do NOT collapse into one)
- **FAST / interrupt** = the v1 daily cron alerts (dip ≤−30%+RISK_ON, F&G<25, ≥2-source convergence,
  FOMC surprise) → SAME-DAY DM, labelled "raw signal, not yet vetted". Runs even if the committee is down.
- **SLOW / committee** = `.agents/workflows/hedge-fund-committee.workflow.js` (Claude Code dynamic workflow):
  `Analysts (parallel fan-out) → Aggregate (cluster, convergence-weight) → Committee (lenses vote
  INDEPENDENTLY, parallel = no anchoring) → Risk (CRO veto+size) → CIO memo`. Run weekly, or on one
  ticker via `args:{ticker}`. Supersedes the thin `hedge-fund-committee.workflow.js`.

### Anti-failure protocol (from the research — these are not optional)
- **Cost ~15× (Anthropic).** Panel runs ONCE per aggregated cycle, not per signal; only top-5 / ≥3-desk
  clusters reach full quorum.
- **Groupthink = 59.5% of debate failures (confident consensus on wrong).** Each lens commits its verdict
  INDEPENDENTLY before seeing peers (parallel); **dissent log is MANDATORY**; the Lacy-Hunt deflation seat
  is structurally protected; a unanimous panel is a FLAG.
- **Non-determinism.** Same input → different output. This is a rigor scaffold, NOT an alpha machine —
  every actionable trade still passes the backtest gate + human approval (GOAL.md invariants).
