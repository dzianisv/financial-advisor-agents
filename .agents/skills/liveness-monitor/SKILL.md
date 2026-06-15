---
name: liveness-monitor
description: Dead-man's-switch for the advisor's SILENT-unless-alert cron jobs. Each daily scan logs a heartbeat so "nothing fired" is distinguishable from "everything broke"; a daily health check DMs the owner ONLY when an expected job has gone stale (hasn't logged within max-age). Use when asked "are my advisor jobs running", "did the scans run today", "health check the cron", or on the daily health schedule.
license: MIT
compatibility: opencode
metadata:
  audience: operators
  domain: cron-liveness-monitoring
  role: dead-mans-switch
---

# Liveness Monitor (so the advisor can't fail silently)

The advisor is **SILENT-unless-alert** by design — which means a broken scan looks exactly like a calm
market. Both produce no DM. This skill makes the two distinguishable.

## Hard rule
Ops tooling only — no market data, no fabrication, no trades.

## 1. Every daily cron LOGS a heartbeat (even on NO_REPLY)

Add this as the LAST step of each daily scan's cron prompt, so a run is recorded whether or not it alerted:
```bash
python3 ~/.openclaw/workspace/investor/skills/liveness-monitor/liveness.py \
  log --job <job-name> --detail "<one line: what it checked + whether it alerted>"
```
e.g. `--job dip-screener --detail "10 HIGH dips, regime RISK_ON, 0 alerted"`.
Ledger: `$LIVENESS_LEDGER` or `~/.openclaw/workspace/investor/liveness.jsonl` (persists across runs).

## 2. A daily HEALTH cron checks freshness and alerts only on failure

Schedule one cron (e.g. `0 9 * * 1-5` UTC, after the morning scans) running:
```bash
python3 ~/.openclaw/workspace/investor/skills/liveness-monitor/liveness.py \
  check --expect dip-screener,crypto-dip-scanner,signal-convergence,narrative-velocity --max-age-hours 26
```
**The `--expect` names MUST exactly match the `--job` strings each cron logs** (else a real job looks
"never logged" → false alarm, or an outage is missed). Only list jobs that actually call `liveness.py log`.
Currently: `dip-screener, crypto-dip-scanner, signal-convergence, narrative-velocity`. (Add `regime-fed`
/ `journalism` only once those crons also log.)

> **GAP — the health check can itself die silently.** It's one cron on one bot; if the bot is down, it
> emits nothing and you learn nothing. For true coverage, add an EXTERNAL dead-man's-switch (e.g.
> healthchecks.io or a cron on another host) that expects the bot's daily check-in and alarms if absent.

- exit 0 / `"status":"ALL_FRESH"` → every expected job logged within 26h → **NO_REPLY** (stay silent).
- exit 1 / `"status":"STALE"` → **DM the owner**: "⚠️ advisor jobs stale: <list>" so a silent outage is caught
  in a day, not weeks.

## Why 26h
Daily jobs run ~24h apart; 26h tolerates jitter/weekends-skip without false alarms. Tune per cadence.

## Success criteria
- [ ] Every daily scan calls `liveness.py log` as its final step.
- [ ] The health cron runs `check` and DMs ONLY on `STALE`.
- [ ] A deliberately-skipped job shows up as STALE within max-age (test it once).

## Schedule
Health check: daily **09:00 UTC (Mon–Fri)**, after the 07:45–08:30 scan window.
