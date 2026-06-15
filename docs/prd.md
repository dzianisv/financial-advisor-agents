# PRD — AI Agent Investment Advisor

Built on existing agentic systems (openclaw, hermes-ai, claude-code) via their native primitives — heartbeat, cron jobs, AGENTS.md, memory tools, browser tools, dynamic workflows. Same skills on all three; only the scheduling/notification wiring differs.


Outcome: owner gets same-day DM for next Google/SanDisk/BTC-dip — quorum verdict attached — before window closes. RECOMMEND-ONLY. Never trades.

## Problem

Owner runs $1M tradfi book + ~$177k crypto book. No time to research. Nothing watches proactively. Misses time-sensitive setups:

| Miss | When | What happened | Why missed |
|---|---|---|---|
| Google (GOOGL) | Spring 2025 | quality stock -30% from 52w high | no dip alert existed |
| SanDisk (WDC) | Sept 2025 | FT/WSJ AI-supply-chain narrative built over WEEKS | one-pass weekly scan missed buildup |
| BTC | April 2025 | $61k, -43% from $108k ATH, F&G sub-20, funding neg | textbook accumulation, no alert |

Root cause: agent REACTIVE (Monday weekly brief), opportunities TIME-SENSITIVE (-30% dip / F&G<20 lasts days). Skills don't talk across asset classes. No daily proactive alert layer.

## Goal

Proactive advisor. Monitors stocks+crypto daily. Reads news, builds context, DMs owner immediately when conditions align. Educational, not advice. Human-in-the-loop.

## Users / Personas

| Persona | Need |
|---|---|
| Owner-PM (sole user) | no research time; wants same-day DM when quality setup appears; final trade decision stays human |

## Gaps → Features

Ranked by impact.

| # | Feature | Catches | Trigger | Status |
|---|---|---|---|---|
| 1 | dip-screener | Google -30% | scan S&P100 daily, >=20/25/30% below 52w high; HIGH tier >=-30% | BUILT |
| 2 | crypto-dip-scanner | BTC $61k | BTC/ETH/SOL/BNB/AVAX % below 52w high + F&G + funding; primary = dip>=-30% AND F&G<25 | BUILT |
| 3 | narrative-velocity | SanDisk buildup | rolling mention-rate vs own baseline; spike feeds convergence | BUILT (`mention_velocity.py` in trend-stock-research) |
| 4 | signal-convergence-alert | SanDisk multi-signal | DM when 2+ sources same ticker (may be correlated) | BUILT |
| 5 | watchlist-monitor | — | standing price triggers on candidates | CUT → folded into `portfolio-monitor` |
| 6 | recommendation-journal | — | log every rec + 30/60/90d outcome | CUT → `forecast-ledger` already does this |
| 7 | liveness-monitor | silent outage | dead-man's-switch: scans log heartbeats, health cron DMs if stale | BUILT |

## Reused Signal Skills

Already shipped: regime-detection (RISK_ON/OFF from SPY 200dMA+VIX+HY spread), fomc-monitor, prediction-market-odds, trend-stock-research, 13f-watch, congressman-stock-watch, macro-panel, multi-lens-quorum (buy/sell/hold verdict engine), superforecasting, risk-management (VETO authority), portfolio-monitor.

## Cadence — Proactive Layer

| Time (UTC) | Job | DM condition |
|---|---|---|
| Daily 07:45 | dip-screener | HIGH dip + RISK_ON |
| Daily 07:50 | crypto-dip-scanner | dip + extreme fear |
| Daily 08:00 | regime + fomc | only if changed |
| Daily 08:15 | trend-stock-research broad scan | accumulate narrative velocity (no DM) |
| Daily 08:30 | signal-convergence | 2+ signals same ticker |
| Weekly Mon 09:30 | full brief | always — regime+fed+13F+congress+journalism cross-ref, quorum top 5, risk veto |

## Target Agents

3 backends, same skills. All RECOMMEND-ONLY.

| Backend | Proactive mechanism |
|---|---|
| openclaw | agent-native cron (primary; SILENT-unless-alert) + heartbeat as light backup |
| claude-code | `/loop` + `/goal` + dynamic workflows (durable: Routines / Desktop scheduled tasks); notify via mobile push + messaging connector |
| hermes-ai | hermes scheduler |

## Constraints

- RISK_OFF regime → no new buys.
- Never re-propose deduped ticker.
- Mark unverifiable as [unverified]. Never fabricate.
- Every forecast needs resolution date + invalidation trigger.
- risk-management has VETO.
- State lag in every brief: 13F 45d, STOCK Act 30-45d.

## Success Metrics

- Same-day DM for next Google/SanDisk/BTC-dip scenario, before window closes.
- DM carries quorum verdict.
- Zero fabricated claims (all unverifiable flagged).

## Out of Scope

- No auto-trading. Recommend-only.
- No paid data feeds.
