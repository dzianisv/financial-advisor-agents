---
name: signal-convergence-alert
description: Cross-reference the day's signal pools (dip-screener, journalism/narrative, 13F buys, congressional buys) and fire an immediate alert when the SAME ticker is surfaced by 2+ sources. Convergence = elevated (NOT proven) conviction, time-sensitive — sources may be CORRELATED (a stock dips BECAUSE of the headlines), so treat n_sources as crowdedness, not independent triangulation. Use when asked "anything converging", "what's showing up across signals", "run the convergence check", or on the daily proactive schedule after the other scans.
license: MIT
compatibility: opencode
metadata:
  audience: multi-signal-investors
  domain: signal-convergence
  role: cross-signal-conviction-detector
---

# Signal Convergence Alert

The killer feature: catch the next **SanDisk** — where a ticker appears in journalism AND a 13F buy
AND a dip screen in the same window. One signal is noise; three independent signals on the same name
is conviction. This skill is the glue that ties the daily scans together and decides what's worth an
immediate DM vs the Monday brief.

## Hard rule

**RECOMMEND-ONLY.** Reports only what is actually in the pools — never invents a convergence.
Educational, not advice.

## How it works

It reads the day's accumulated pools (whichever exist):

| Source | Pool file | Written by |
|--------|-----------|------------|
| `dip` | `~/.openclaw/workspace/investor/pools/dip_candidates.jsonl` (≤5d) | dip-screener (07:45, `--emit-pool`) |
| `journalism` | `~/.openclaw/workspace/investor/pools/narrative.jsonl` (≤5d) | mention_velocity (08:10) |
| `13f` | 13F dedup ledger (last 14d) | 13f-watch |
| `congress` | congress dedup ledger (last 14d) | congressman-stock-watch |

**A. Local backend (Python present):**
```bash
python3 .agents/skills/signal-convergence-alert/convergence.py --min-sources 2 --json
```

**B. openclaw pod (NO Python):** read the pool files yourself — they are small JSONL. For each file,
read each line's `ticker` (or `symbol`), tag it with that pool's source name, build a
`ticker → {sources}` map (ledgers: keep only rows whose `date`/`recorded`/`ts` is within 14d), then
emit any ticker whose source-set size ≥ min-sources. No script needed — it's a count.

Each output row: `ticker`, `sources` (which pools), `n_sources`, `notes`.

## Alert logic

- **n_sources >= 2 → IMMEDIATE DM.** This is the whole point — don't wait for Monday.
- **n_sources >= 3 → flag as HIGH conviction**, route straight to `/multi-lens-quorum`.

DM format:
```
🎯 CONVERGENCE — [TICKER] surfaced by [n] sources today (may be correlated, not independent)
  Sources: [dip + journalism + 13F]
  Notes:
    - dip: -31% from 52w high, RISK_ON
    - journalism: 3 FT/WSJ mentions this week (AI supply chain)
    - 13f: new Scion initiation, $5M+
  → This is the SanDisk pattern. Run /multi-lens-quorum on [TICKER]? Reply YES.
```

## Why convergence beats any single signal

- A dip alone could be a value trap.
- A journalism mention alone could be hype.
- A 13F buy alone is 45 days stale.
- All three on the same ticker, same week → the independent errors don't correlate. That's signal.

## Success criteria

- [ ] Read every available pool (named the ones it found).
- [ ] Only reported tickers genuinely present in >= min-sources pools (no fabrication).
- [ ] n>=2 → immediate DM; n>=3 → routed to quorum.
- [ ] Notes preserved per source so the owner sees WHY each signal fired.

## Schedule

Run **daily 08:30 UTC (Mon–Fri)** — after dip (07:45), crypto (07:50), regime (08:00), journalism
(08:15) have populated the pools.
