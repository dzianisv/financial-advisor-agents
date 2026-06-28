export const meta = {
  name: 'hierarchy-compare',
  description: 'Run the same portfolio prompt through multiple stocks-advisor decision hierarchies and blind-score them /25',
  phases: [
    { title: 'Run', detail: 'Fan out one agent per hierarchy on the same input' },
    { title: 'Judge', detail: 'Blind-score each output /25 using 5-dimension rubric' },
    { title: 'Synthesize', detail: 'Produce comparison table + winner recommendation' },
  ],
}

// Normalize args — workflow tool may pass args as JSON string (not object)
const _args = (typeof args === 'string') ? JSON.parse(args) : (args || {})
const INPUT = _args.input || ''
const HIERARCHIES = _args.hierarchies || ['bsc', 'bridgewater', 'berkshire', 'point72', 'soros']
const MODEL = 'claude-sonnet-4'

if (!INPUT) {
  throw new Error('hierarchy-compare requires args.input — the portfolio prompt to analyze')
}

// ── Schemas ──────────────────────────────────────────────────────────────────

// Judge schema — blind: the judge does not see the hierarchy name; orchestrator injects it after
const JUDGE_SCHEMA = {
  type: 'object',
  properties: {
    hierarchy: {
      type: 'string',
      description: 'Set this to "BLIND" — the orchestrator will replace it with the real hierarchy name',
    },
    scores: {
      type: 'object',
      properties: {
        data_grounding:  { type: 'number', minimum: 0, maximum: 5 },
        actionability:   { type: 'number', minimum: 0, maximum: 5 },
        insight:         { type: 'number', minimum: 0, maximum: 5 },
        risk_honesty:    { type: 'number', minimum: 0, maximum: 5 },
        decisiveness:    { type: 'number', minimum: 0, maximum: 5 },
      },
      required: ['data_grounding', 'actionability', 'insight', 'risk_honesty', 'decisiveness'],
    },
    total:     { type: 'number', minimum: 0, maximum: 25 },
    strengths: { type: 'array', items: { type: 'string' }, minItems: 1 },
    weaknesses: { type: 'array', items: { type: 'string' }, minItems: 1 },
  },
  required: ['hierarchy', 'scores', 'total', 'strengths', 'weaknesses'],
}

// ── Prompts ───────────────────────────────────────────────────────────────────

const runPrompt = (name) =>
  `You are running the stocks-advisor skill with --hierarchy ${name} on this input:

${INPUT}

Follow the SKILL.md at /Users/engineer/workspace/backtest/.agents/skills/stocks-advisor/SKILL.md.
For the decision chain (Step 2), load and follow /Users/engineer/workspace/backtest/.agents/skills/stocks-advisor/references/hierarchies/${name}.md INSTEAD OF the hardcoded steps.
Do not run the full TradingView loop — produce a simulated output showing what each seat would conclude and what the hierarchy's decision chain would decide.
Output the full formatted report including signal table, sources, and recap.`

const judgePrompt = (report) =>
  `You are a blind evaluator scoring a stock analysis report /25 across 5 dimensions. You do NOT know which decision framework produced this report — that information has been withheld to prevent bias.

Score each dimension 0–5 (integers preferred; halves allowed). Compute total = sum of 5 scores.

SCORING RUBRIC:

1. Data Grounding (0–5)
   5 = every factual claim has a named source (URL, filing, data feed, fundamentals.py output); no assertion from memory
   3 = most claims sourced; 1–2 unattributed assertions in low-stakes positions
   1 = majority of claims are unverified memory recalls; sources missing or vague
   0 = no sourcing whatsoever

2. Actionability (0–5)
   5 = concrete entry zone + bar-close trigger + market-based stop + share count for every BUY/ADD; WATCH names have exact conditions that unlock action
   3 = entry zones present but triggers or stops are vague; WATCH names lack conditions
   1 = directional verdicts only (BUY/SKIP) with no entry/exit mechanics
   0 = no actionable output at all

3. Insight (0–5)
   5 = identifies a non-obvious connection or mispricing the consensus would miss; thesis is differentiated, not restatement of the narrative
   3 = solid analysis but stays within well-known facts; no new angle
   1 = mostly repeats surface-level information; no synthesis
   0 = factually incorrect or incoherent

4. Risk Honesty (0–5)
   5 = adversarial challenge present and named; invalidation conditions are falsifiable; portfolio tail-stress dollar amounts stated; dissent logged even when overruled
   3 = risks mentioned but not quantified; invalidation conditions are vague or generic
   1 = risks are boilerplate ("macro could deteriorate"); no adversarial challenge
   0 = no risk discussion; pure bull case only

5. Decisiveness (0–5)
   5 = every name ends with a clear BUY/WATCH/SKIP (or ADD/HOLD/TRIM/EXIT for holdings); P0/P1/P2/P3 execution table with share counts and triggers; no hedged non-answers
   3 = most names have verdicts but some are left open ("further research needed")
   1 = majority of names end as WATCH with no conditions that would change them
   0 = no verdicts reached; pure analysis with no conclusion

After scoring, list 1–3 key strengths (what this report does notably well) and 1–3 key weaknesses (where it fell short).

Report to evaluate:
---
${report}
---`

const synthesisPrompt = (judgedResults) => {
  const rows = judgedResults.map(r => {
    const s = r.score.scores
    return `| ${r.hierarchy.padEnd(12)} | ${s.data_grounding}/5 | ${s.actionability}/5 | ${s.insight}/5 | ${s.risk_honesty}/5 | ${s.decisiveness}/5 | **${r.score.total}/25** |`
  }).join('\n')

  const details = judgedResults.map(r =>
    `### ${r.hierarchy} (${r.score.total}/25)\nStrengths: ${r.score.strengths.join('; ')}\nWeaknesses: ${r.score.weaknesses.join('; ')}`
  ).join('\n\n')

  return `You are producing the final comparison report for a multi-hierarchy stocks-advisor evaluation.

Below are the hierarchies tested, their blind scores, and their full reports. Produce:

1. A formatted comparison table (markdown)
2. A winner declaration with reasoning (which hierarchy scored highest and WHY it won — cite specific rubric dimensions)
3. A recommendation: which hierarchy to use for which use case, based on the eval results

SCORES SUMMARY:
| Hierarchy    | Data | Action | Insight | Risk | Decisive | Total    |
|:-------------|:-----|:-------|:--------|:-----|:---------|:---------|
${rows}

DETAIL BY HIERARCHY:
${details}

FULL REPORTS (for cross-reference):
${judgedResults.map(r => `### ${r.hierarchy}\n${r.report}`).join('\n\n---\n\n')}

Output format:
- ## Comparison Table (the markdown table above, reformatted if needed)
- ## Winner: [name] ([score]/25) — [one paragraph explaining why]
- ## Use-Case Routing — which hierarchy to use when (≤5 bullets)
- ## Full Score Breakdown (detail by hierarchy)
`
}

// ── Phase: Run + Judge (pipelined — judge fires immediately per hierarchy, no barrier) ──

phase('Run')
const judgedResults = await parallel(
  HIERARCHIES.map(name => async () => {
    // Run the hierarchy
    const report = await agent(
      runPrompt(name),
      { label: `run-${name}`, phase: 'Run', model: MODEL },
    )

    // Pipeline: judge immediately without waiting for other hierarchies
    const judgeResult = await agent(
      judgePrompt(typeof report === 'string' ? report : JSON.stringify(report)),
      { label: `judge-${name}`, phase: 'Judge', schema: JUDGE_SCHEMA, model: MODEL },
    )

    // Orchestrator injects the real hierarchy name (judge set it to "BLIND")
    const score = { ...judgeResult, hierarchy: name }

    return { hierarchy: name, report, score }
  }),
)

// ── Phase: Synthesize ─────────────────────────────────────────────────────────

phase('Synthesize')
const synthesis = await agent(
  synthesisPrompt(judgedResults),
  { label: 'synthesize', phase: 'Synthesize', model: MODEL },
)

// Determine winner by total score
const sorted = [...judgedResults].sort((a, b) => b.score.total - a.score.total)
const winner = sorted[0]

log(`Winner: ${winner.hierarchy} (${winner.score.total}/25)`)
judgedResults.forEach(r => log(`  ${r.hierarchy}: ${r.score.total}/25`))

return {
  winner: winner.hierarchy,
  winner_score: winner.score.total,
  scores: judgedResults.map(r => ({ hierarchy: r.hierarchy, total: r.score.total, scores: r.score.scores })),
  comparison: synthesis,
}
