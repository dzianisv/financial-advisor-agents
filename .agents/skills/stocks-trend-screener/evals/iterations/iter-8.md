# Iteration 8 — round 8 — v6 research-mode routing-block validation (case 01 + case 02, both RESEARCH_MODE)

v6 change: extend the INSUFFICIENT_GROUNDING routing-block to RESEARCH_MODE — BODY_NOT_REACHED names
are watchlist-only and are NOT routed to quorum. Only names passing the gate (G1+G2) may be routed.
CONVICTION_MODE kill behavior unchanged.

Two RESEARCH_MODE cases run:
- **case 01 (train, generalization):** "find who benefits that nobody is talking about ... non-obvious
  in AI infrastructure ... monopoly on a scarce input the AI buildout needs" (RESEARCH_MODE, 2026-06-08).
  Tests that the routing-block generalizes to a second RESEARCH_MODE case, not just the exposing case.
- **case 02 (train, the exposing case):** "Run the weekly trend scan ... surface what's EARLY, not
  already extended" (RESEARCH_MODE, frozen 2026-06-08). The case that exposed the v5 gap (source_grounding=2
  with BODY_NOT_REACHED names routing to quorum). v6 is targeted directly at this case.

## Isolation

- Actor: sonnet, given ONLY the v6 skill body (worktree path) + the case request (no rubric, no prior scores).
- Judge: sonnet, given ONLY case + actor response + RUBRIC.md. Blind to skill body and prior scores.
- No prior-score anchoring shown to judge — blind scoring on each case independently.
- **CAVEAT (case 02):** the case-02 actor was auto-backgrounded and its case-02 judge scored the actor's
  FINAL SUMMARY (not the full output table) — lower fidelity. Re-score case 02 on full output next round.

## Raw judge output — CASE 01 (train, RESEARCH_MODE AI-infra hidden, MEAN 4.7)

- **source_grounding: 4** — AFMJF carries a verbatim IR body quote + URL + date. Haircuts: kill-side
  citations (Reuters/WSJ/Nikkei) are headline-only with no extracted body sentence; the AI-demand Nikkei
  claim is body-unconfirmed.
- **non_obvious_discovery: 5** — Alphamin = DRC tin miner screening as commodity; full chain
  AI servers→more solder→tin demand tripling→LME +55%→Bisie lowest-cost single-source→not in any AI ETF.
  Clean, specific, non-consensus chain.
- **skeptic_discipline: 5** — 9 of 13 candidates killed with hard % figures + consistent >150%/12m
  threshold; AFMJF AI-demand explicitly downgraded where body unconfirmed.
- **actionability: 4** — ticker/inflection/catalyst+quarter/kill/confidence present; missing explicit
  entry price zone.
- **quorum_routing: 5** — CLF + ETN explicitly held to watchlist with stated reasons; only AFMJF routed
  at LOW; no buy call made.
- **prescreen_usage: 5** — scanner run as Step 1, used to kill extended names before reading, framed
  as pre-screen.
- **MEAN: 4.7**
- **Judge's top fix:** source_grounding — extract verbatim body sentences on the kill-side citations
  (Reuters/WSJ/Nikkei) rather than relying on headline-only references.

## Raw judge output — CASE 02 (train, RESEARCH_MODE weekly scan, MEAN 4.2, scored from summary)

- **source_grounding: 4** — LEU/QBTS/UUUU/LHX body-grounded via EDGAR 10-K with verbatim figures
  (e.g. QBTS +178% $8.8M→$24.6M); BWXT press-tier only; FT/Bloomberg gaps transparently disclosed.
- **skeptic_discipline: 4** — large explicit kill list (IONQ/OKTA/GEV/CCJ/VLO-PSX-MPC/RTX-LMT-NOC)
  with stated reasons; BWXT press-only could have been killed rather than routed to quorum (borderline).
- **actionability: 3** — tickers/thesis/confidence present but kill conditions implicit and catalyst
  timelines generic ("next earnings") not per-ticker quarters. NOTE: likely a SUMMARY-fidelity artifact —
  summary lacked per-ticker catalyst quarters that may have been present in the full run; not a confirmed
  regression.
- **quorum_routing: 5** — explicit non-execution, confidence flags, 5 nominees, zero self-deciding;
  BODY_NOT_REACHED names held to watchlist (the v6 fix working).
- **prescreen_usage: 5** — emerging_scan.py Step 1 directed reading.
- **MEAN: 4.2**
- **Judge's top fix:** actionability — per-ticker catalyst quarter + explicit per-name kill condition.

## Insight block — read first next round

1. **KEEP v6.** The RESEARCH-mode routing-block lifted case-02 source_grounding 2→4 (the exact gap
   round 7 flagged) while quorum_routing held at 5. Case 01 at 4.7 confirms no over-correction.

2. **Mechanism confirmed:** actors now route ONLY body-grounded (EDGAR/IR) names to quorum and put
   headline/RSS-only names under "Watchlist — body not reached (NOT routed to quorum)". This is the
   structural fix v5 left incomplete.

3. **v7 candidate levers (pick ONE next round):**
   - **(a) Independent-journalism bodies:** require ≥1 INDEPENDENT journalism body quote (not just
     company IR/press) per routed finalist — both judges flagged IR/press reliance (AFMJF IR, BWXT
     press-tier). This is the more impactful lever.
   - **(b) Per-ticker catalyst quarter + explicit kill condition:** for the actionability dim — addresses
     the case-02 judge finding (though may be a summary-fidelity artifact, not a confirmed regression).

4. **Methodology debt:** there is NO RESEARCH-mode holdout case — v6 was measured on train (01, 02)
   only. Freeze a real RESEARCH holdout from a session that predates v6 before trusting the
   generalization claim. This is a blocker before shipping v6 as "validated on holdout."

5. **Process note:** don't let actors auto-background then score from a summary. Capture the full
   deliverable for the judge before scoring. Case 02 actionability score is suspect for this reason
   and must be re-scored on full output next round.

## Status

v6 archived at `archive/v6-research-routing.md`; SKILL.md edited; KEPT this round.
eval.csv updated with 2 new rows (rows 5 and 6, both __V6SHA__ → replaced with actual commit SHA after commit 1).
