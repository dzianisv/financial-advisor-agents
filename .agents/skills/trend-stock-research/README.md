# trend-stock-research

A research-first skill that helps an AI agent **find trendy stocks before they become obvious** —
the way the people who caught NVDA (2021) or SanDisk (2025) did: by *reading* quality financial
journalism and reasoning about it, not by running a price scanner.

> Hypothesis generation, not a buy signal. Never auto-trades. Educational, not financial advice.

## What it does for the agent

A price scanner can only tell you what already moved. The edge is in reading *why* something is
forming — a demand inflection, a supply-chain bottleneck, the non-obvious company that controls a
scarce input but screens as something else (a "food company" that has a 95% monopoly on chip
packaging film). This skill gives the agent a repeatable method to find those.

The agent runs a 5-step loop:

1. **Pre-screen** — run `scripts/emerging_scan.py` to see which sectors are hot right now (directs
   *where* to read; it is not the answer).
2. **Read journalism** — fan out subagents across Seeking Alpha / WSJ / FT / SEC filings / earnings
   calls; extract specific facts (a quote, a number, a date) — no "citation theater".
3. **Map the non-obvious beneficiary** — obvious leader → scarce input → who controls it → does it
   hide in another sector.
4. **Skeptic filter** — kill anything already priced (>150% in 12mo), with no concrete catalyst, or
   no nameable risk. Most candidates die here.
5. **Rank & route** — hand the survivors to `multi-lens-quorum` for the buy/wait/late-chase call.
   This skill only *nominates*; it never decides.

It also has stateful modes (daily **ingest** into a SQLite article DB, weekly **synthesis** to find
themes converging across 3+ independent sources, on-demand **search**).

## How to use it

Just ask in natural language — the skill self-triggers on phrases like:

> "find trendy stocks" · "what's the next NVDA?" · "scan for emerging stocks" · "research robotics
> for winners" · "what am I missing?" · "build a weekly trend watchlist"

The full operating instructions live in [`SKILL.md`](SKILL.md). The agent reads that and executes
the method; you read the table of nominated tickers (with demand inflection, catalyst, why-hidden,
confidence, and sources) at the end.

## Auto-research: the skill improves itself

The skill ships with a self-improvement loop (`scripts/auto_research.py`) inspired by Karpathy's
[autoresearch](https://github.com/karpathy/autoresearch) — *"one file, one metric, keep what wins."*

- **one editable file** → `SKILL.md`
- **one metric** → the mean score of [`evals/RUBRIC.md`](evals/RUBRIC.md) across the test cases in
  `evals/cases/`
- **one round** → edit `SKILL.md` to fix the weakest rubric dimension, run the skill on the cases,
  have an LLM judge score the output, then **keep the edit if the score rose, else auto-revert it**
- repeat on a budget until it ships (mean ≥ 4.2, no dimension below 3.0)

Trigger it by asking the agent to *"auto-research this skill"* / *"self-improve until it ships"*, or
drive the harness directly:

```bash
SK=scripts/auto_research.py
python3 $SK init --budget 10     # snapshot SKILL.md as the baseline
python3 $SK next-target          # which rubric dimension is weakest?
# (agent edits SKILL.md, runs the cases, judges the output)
python3 $SK snapshot 1
python3 $SK record 1 --dims source_grounding=4 non_obvious_discovery=5 skeptic_discipline=5 \
                            actionability=4 quorum_routing=5 prescreen_usage=5
python3 $SK status               # ship? or loop again
```

The harness is pure bookkeeping (zero API cost); the agent does the reading and judging. So the same
agent that uses the skill to do research can also use it to make the skill better — and every change
is kept only if the rubric says it helped. The audit trail lives in `evals/scores.md`,
`evals/iterations/`, and `TrendPickingEval.csv`.

## Layout

| Path | What |
|------|------|
| `SKILL.md` | the operating instructions the agent follows |
| `scripts/emerging_scan.py`, `weekly_scout.py`, … | the quantitative pre-screen / radar |
| `scripts/db/research_db.py` | SQLite + BM25 article store for the stateful modes |
| `scripts/auto_research.py` | the self-improvement (keep/discard) harness |
| `evals/RUBRIC.md`, `evals/cases/` | how the skill is scored, and on what |
| `evals/scores.md`, `evals/iterations/` | the improvement history |
