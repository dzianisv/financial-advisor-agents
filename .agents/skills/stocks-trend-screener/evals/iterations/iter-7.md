# Iteration 7 — round 7 — v5 grounding-gate validation (case 05 holdout + case 02 train over-correction check)

v5 change (committed 6a099d8, already on main): Step 4.5 grounding gate + EDGAR-primary-body-route +
headline-as-quote ban. This round is validation-only — actor+judge run, keep-or-revert verdict,
and named residuals for the next lever.

Two cases run:
- **case 05 (holdout):** CONVICTION_MODE dual-theme (robotics AND ai supply chain) — the case that
  exposed the mode-detection gap in round 6. Confirms source_grounding improvement and checks
  over-correction on other dims.
- **case 02 (train, over-correction check):** RESEARCH_MODE weekly scan (frozen 2026-06-08) — re-run
  to confirm the gate did NOT degrade RESEARCH_MODE quality.

## Isolation

- Actor: sonnet, given ONLY the v5 skill body (SKILL.md at 6a099d8) + the case request. No rubric.
- Judge: sonnet, given ONLY case + actor response + RUBRIC.md. Blind to skill body.
- No prior-score anchoring shown to judge — blind scoring on each case independently.

## Raw judge output — CASE 05 (holdout, CONVICTION dual-theme)

- **source_grounding: 4** — the gate worked: RMBS carries Source(BODY) with resolved rambus.com URLs
  + verbatim body quotes + Source(DATA). Haircuts: the 2 RMBS URLs are company IR press-releases, not
  independent journalism; one verbatim quote is from MatX CEO (third party) not Rambus primary; DATA
  source (yfinance) is unnamed.
- **non_obvious_discovery: 5** — RMBS = IP-licensing layer hiding in "semiconductor"; clean
  demand→bottleneck→controller chain identified; actor killed obvious semis first before surfacing the
  non-obvious angle.
- **skeptic_discipline: 5** — majority of candidates killed with stated reasons; UUUU killed on
  body-source gate (G1+G2 fail) rather than passing a headline-cited name as HIGH; no extended surgers
  slipped through.
- **actionability: 4** — RMBS has ticker/inflection/catalyst+quarter/kills/confidence; minor haircut:
  HIGH flag appears only in the closing line, not inline with the candidate block.
- **quorum_routing: 4** — routing stated twice, no buy call; marginal haircut: "HIGH confidence flag"
  language is marginally directive rather than nomination-style.
- **prescreen_usage: 4** — scanner used to identify extended names before deep-reading; haircut:
  not explicitly labeled "pre-screen only" in the output.
- **MEAN: 4.3**
- **Judge's top fix:** source_grounding — replace IR press-release URLs with independent journalism
  (SA/Bloomberg/Reuters/WSJ) that corroborates the numbers, each with a verbatim body sentence.

## Raw judge output — CASE 02 (train, RESEARCH_MODE, over-correction check)

- **source_grounding: 2** — one genuine body read (IONQ) vs six BODY_NOT_REACHED RSS teasers = citation
  theater at scale. The gate caps confidence for these names but does not block them from routing to
  quorum.
- **skeptic_discipline: 4** — 3-question filter applied on every candidate; FLR/PWR survive LOW with
  revenue UNKNOWN rather than being killed; minor shortfall vs a strict kill-on-unknown standard.
- **actionability: 4** — table has ticker/inflection/catalyst+quarter/kill/confidence; PWR/LYC lack a
  specific catalyst date.
- **quorum_routing: 5** — explicit tiered routing, no buy call, nomination-style; BODY_NOT_REACHED
  names flagged as LOW confidence before forwarding.
- **prescreen_usage: 5** — scanner run as Step 1, 72/182 candidates enumerated, EARLY vs EXTENDED split
  performed before any deep reading.
- **MEAN: 4.0**
- **Judge's top fix:** BODY_NOT_REACHED candidates should be held as watchlist-only and NOT routed to
  quorum until body confirmed; gate currently only caps confidence, not routing.

## Insight block — read first next round

1. **KEEP v5.** Holdout 3.83→4.3 (+0.47). Target dim source_grounding 3→4. Over-correction guard
   PASSED: actionability 3→4 (did not drop as the prior-round diagnosis feared). The gate's real win
   is that the actor now KILLS ungrounded names (UUUU on G1+G2 body-source fail) instead of letting
   citation-theater names advance as HIGH.

2. **Gate real win detail:** lone HIGH finalist RMBS carries Source(BODY) resolved rambus.com URLs +
   verbatim body quotes + Source(DATA) — meaningful step up from v4's RSS-stub citations. skeptic
   and non_obvious both held 5 (no regression from the mode-detection fix).

3. **NEW residual from case 02 — v6 single lever:** in RESEARCH_MODE the grounding gate only CAPS
   confidence; it does not block routing. So BODY_NOT_REACHED names still route to quorum (6 of 7
   names had only RSS teasers); source_grounding stuck at 2 in RESEARCH_MODE. v6 fix = extend the
   routing-block: a BODY_NOT_REACHED name = watchlist-only, must NOT route to quorum until body
   confirmed.

4. **Real cost confirmed:** case 02 actor ran ~26 minutes (~3× normal runtime). Score held but the
   gate is slow at RESEARCH_MODE scale. Note as residual for now — do NOT make it a fix target until
   the routing-block is validated.

5. **Secondary residual (carry forward):** even grounded finalists lean on company IR press-releases.
   v7 could require ≥1 independent-journalism body quote (SA/Bloomberg/Reuters/WSJ) corroborating IR
   numbers per finalist. Do NOT bundle with the RESEARCH_MODE routing-block — one lever per round.

6. **Do NOT fix two levers in one round.** Next single lever = RESEARCH_MODE routing-block. Defer
   journalism-corroboration to v7.

## Status

v5 archived at `archive/v5-grounding-gate.md`, already committed in SKILL.md at 6a099d8 and merged
to main. This round = validation only. eval.csv carries commit-linked rows per (case, variant) per
the new ledger format.
