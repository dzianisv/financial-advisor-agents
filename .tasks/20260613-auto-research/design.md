## Problem
trend-stock-research has eval scaffolding (RUBRIC, cases, scores.md, TrendPickingEval.csv) but
no autonomous loop to drive self-improvement against its own rubric. Iteration was manual.

## Goal
Add karpathy/autoresearch loop applied to a skill instead of a model: edit ONE file (SKILL.md),
score ONE metric (RUBRIC mean over eval cases), keep the edit iff mean rose else auto-revert,
iterate on a budget.

## Success Metric
- `scripts/auto_research.py` harness works: init / next-target / snapshot / record (keep-or-revert)
  / status / reset.
- A REAL round executed end-to-end: actor subagents run eval cases, judges score vs RUBRIC,
  harness records + decides keep/discard, stop-condition reported.
- SKILL.md documents the loop as an `<auto_research>` mode.

## Current State
- skill dir: .agents/skills/trend-stock-research/
- evals/RUBRIC.md (6 dims 0–5), evals/cases/train/01-04, evals/scores.md, TrendPickingEval.csv.

## Proposed Design
Pure-python bookkeeping harness owns greedy keep/discard + checkpoint/revert + audit trail
(zero API cost). The expensive RUN (actor) + JUDGE steps are done by the agent orchestrator,
which hands per-dimension scores to `record`. Karpathy mapping: train.py→SKILL.md,
val_bpb→RUBRIC mean, keep-iff-improved→keep-iff-mean-rose, wallclock budget→--budget rounds.
State: evals/auto_research_state.json (gitignored). Variants: evals/variants/ (gitignored).

## Alternatives Considered
- Fully-automated python loop (no agent): rejected — judging stock-research quality needs an LLM
  reading real journalism; cannot be a pure script.
- Vector-DB / external tracker for scores: rejected — scores.md + json is zero-dep, resumable.

## Risks
- Re-running init mid-loop could clobber best baseline → guarded (--force required).
- Off-protocol record (no snapshot, bad score) corrupts the one metric → validated + refused.

## Touched Surface
- NEW scripts/auto_research.py
- NEW .gitignore (skill-local), evals/iterations/iter-5-auto-research-baseline.md
- MOD SKILL.md (<auto_research> block), evals/scores.md (round-1 row), TrendPickingEval.csv (row 3)
- generated (gitignored): evals/auto_research_state.json, evals/variants/

## Result
round-1 real eval mean 4.75 (min dim 4.25) → KEEP → SHIP. Weakest dims source_grounding +
actionability (4.25), capped by no paywall access. verify: harness CLI green on disk.
