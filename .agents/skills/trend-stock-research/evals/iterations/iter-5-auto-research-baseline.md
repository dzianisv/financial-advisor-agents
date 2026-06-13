# Iteration 5 — auto-research harness baseline (round 1, real run)

First REAL end-to-end run of the karpathy-style auto-research loop (`scripts/auto_research.py`):
4 parallel Sonnet 4.6 actor subagents (skill preloaded) executed all 4 train cases; 4 independent
Sonnet 4.6 judges scored each output against `evals/RUBRIC.md`. Harness recorded the round and
applied the keep/discard rule.

Environment: no browser / paywall bypass available to actors (WebSearch + WebFetch only).
Actors compensated with SEC EDGAR, IR press releases, free trade press, and honest gap disclosure —
no citation theater observed by any judge.

## Scores (judge per case, 0–5)

| Dimension | C01 ai-infra | C02 weekly | C03 robotics | C04 trap | Dim mean |
|---|---|---|---|---|---|
| source_grounding | 4 | 4 | 4 | 5 | 4.25 |
| non_obvious_discovery | 5 | — | 5 | — | 5.0 |
| skeptic_discipline | 5 | 5 | 5 | 5 | 5.0 |
| actionability | 4 | 4 | 4 | 5 | 4.25 |
| quorum_routing | 5 | 5 | 5 | 5 | 5.0 |
| prescreen_usage | 5 | 5 | — | — | 5.0 |
| **Case mean** | **4.67** | **4.60** | **4.60** | **5.00** | **4.75** |

## Harness decision
- Round 1 `v3-auto-research-baseline`: mean **4.750** → KEEP (baseline best).
- Stop condition: train mean ≥ 4.2 PASS; no dim < 3.0 PASS → **SHIP** state reached at baseline.

## Notable actor outcomes
- C04 trap case: perfect 5.0 — all four user-named tickers (MU/SK Hynix/Samsung/SNDK) killed on
  hard thresholds, zero finalists, refused to fabricate a non-obvious pivot without sources.
- C01 found CLF (GOES) and LIN (helium) — CLF matches the skill's canonical example independently.
- C03 produced the SKILL.md Schaeffler example LIVE (May 2026 actuator contract confirmed by fresh
  sources) plus NOVT and MP as new non-obvious candidates, all honestly LOW confidence.
- C02 surfaced LEU (HALEU enrichment chokepoint) as the non-obvious nuclear play vs consensus CCJ/URA.

## Remaining gap (next round target)
source_grounding and actionability tie at 4.25 — both capped by paywall inaccessibility (FT/WSJ/SA)
and occasional missing catalyst dates. Next lever: strengthen the fallback-source ladder
(archive.today instructions, EDGAR full-text retry guidance) in Step 2 to lift source_grounding
without a browser.
