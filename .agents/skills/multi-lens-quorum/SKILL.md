---
name: multi-lens-quorum
description: ALWAYS use for any investment or trading advice — convene a quorum of independent lenses instead of one opinion. Auto-trigger on "should I buy/sell/hold X", "is X a good investment", "what do I do with my portfolio", "how should I allocate", "rebalance", "how much should I buy / position sizing", "when should I buy/sell", "DCA or lump", "take profit?", "is now a good time", "what's your call on X", plus the explicit "convene/run the quorum", "get multiple lenses", "what would the analysts say", "don't just give me your opinion". Method: spawn 4-7 subagents, each reads ONE lens/skill and judges the SAME question on IDENTICAL facts, then synthesize consensus WITHOUT averaging away dissent. Cost gate — answer DIRECTLY (no quorum) for facts, lookups, definitions, arithmetic, code fixes, data pulls, or when one lens clearly owns the domain. Distinct from macro-panel (macro-thinker convener); this is the GENERAL method over ANY lenses. Educational, not advice; each lens is a lens, not gospel.
license: MIT
compatibility: opencode
metadata:
  audience: anyone-facing-a-multi-lens-judgment-call
  domain: decision-method-and-orchestration
  role: orchestration/decision-method
  source: codifies the quorum method proven 2026-06-08 (BTC-cadence), blogged in report/writeups/how-we-built-a-multi-lens-analyst-agent.md
---

# Multi-Lens Quorum — The Method

Answer a hard judgment call by making the system **disagree with itself first**, then synthesize. Spawn
N subagents; each reads **exactly one** lens/skill and judges the **same** question on **identical**
facts through **only** that lens. The main agent collects fixed-shape verdicts and synthesizes the
**consensus (the overlap) while preserving the dissent (the spread)**. The disagreement is the signal —
a blended "balanced view" averages a bear and a bull into a shrug that protects against nothing.

This is a **general method** (sibling to `macro-panel`, which is the macro-thinker-specific convener).
Use it over any mix of the repo's lens skills for any reversible-expensive judgment.

## When to convene vs not (the cost gate — read this first)

A quorum is **expensive**: ~4-7 subagents, >100k tokens, minutes of latency. Spend it only when the
answer is worth it.

**Convene when ALL hold:**
- It's a genuine **judgment call** (buy/sell, allocation, strategy selection, "should I…", cadence,
  timing) — not a fact.
- It's **reversible-expensive**: getting it wrong costs real money/time but isn't a one-way door.
- **Multiple lenses would genuinely disagree** — the question spans liquidity / value / behavior /
  trend, etc.

**Do NOT convene — answer directly — when:**
- It's a **fact, lookup, definition, or arithmetic** ("what's the 200d MA", "what does MVRV mean").
- It's a **code fix, data pull, or mechanical task**.
- **One lens clearly owns the domain** (a position-sizing question → just `analyst-systematic-trading`;
  a backtest-validity question → that lens alone). Convening a quorum to rubber-stamp the obvious owner
  is theater.
- The lenses would all say the same thing (no live disagreement = no signal).

Default to a direct answer. The quorum is the exception, not the reflex.

## How to pick the lenses (4-7 that would actually DISAGREE)

Pick **4-7** lenses chosen for **non-overlapping return-drivers / worldviews**, so the spread is real.
**Include at least one dissent/contrarian seat** — the bear, the deflationist, the value "this is
uninvestable", the "do nothing / hold cash" seat. A quorum with no built-in dissenter manufactures false
consensus. Don't stack correlated lenses (three inflationists outvoting one deflationist isn't 3-to-1
signal — it's one view counted thrice).

Naming convention: **thinker-lenses = `analytics-*`**, **discipline lenses = `analyst-*`**, and there are
method/conductor skills. The repo's available lens menu (`.agents/skills/`):

| Lens skill | Brings (the seat) | Natural role in a quorum |
|---|---|---|
| `analyst-systematic-trading` | Carver — rules, vol-target, Half-Kelly, cost speed limit, overfit gate | The discipline/sizing seat; kills the narrative trade |
| `analyst-technical-analysis` | Bernstein — setup→trigger→follow-through, "no trigger, no trade" | The timing/trigger seat (weak evidence — carry as hypothesis) |
| `analyst-crypto` | Howell — global liquidity → on-chain → sentiment → tilted-DCA | The liquidity-tide seat (often the WAIT/dissent) |
| `analytics-benjamin-graham` | Margin of safety, intrinsic value, Mr. Market | The value/"is this even an investment" dissent seat |
| `analytics-morgan-housel` | Behavior > intelligence, tails, enough, room for error | The behavioral guardrail / "don't blow up" seat |
| `analytics-warren-buffett` | Moats, circle of competence, cash-as-option, bubble-discipline | The quality/discipline / hold-cash seat |
| `analytics-lyn-alden` | Fiscal dominance, debasement, BTC-as-hurdle | The structural-inflation / scarce-asset bull |
| `analytics-ray-dalio` | Big debt cycle, world order, all-weather | The cycle-architect / balance-risk seat |
| `analytics-stanley-druckenmiller` | Liquidity drives markets, bet big & rarely | The tactician / timing & sizing seat |
| `analytics-lacy-hunt` | Debt → low velocity → disinflation, long bonds | The **designed deflation dissent** |
| `analytics-michael-pettis` | S−I=CA, capital flows, China rebalancing | The trade/imbalances seat |
| `analytics-russell-napier` | Financial repression, structural inflation by policy | The repression/inflationist-via-policy seat |
| `macro-panel` | Convener of the macro seats specifically | Use that skill directly for a pure-macro question |

If the question is **purely macro**, prefer `macro-panel` (it already routes the macro seats). Reach for
this general method when the right seats **mix disciplines** (e.g. Carver + Graham + Howell + Alden +
Housel on a single allocation call) or include non-macro lenses.

## The subagent prompt template (reuse verbatim, fill the blanks)

Spawn one subagent per lens. Each gets the **same** facts and the **same** question; only the lens path
differs. Pin everything; force a fixed return shape; forbid cross-contamination.

```
Read ONLY this lens and judge through ONLY it:
  /Users/engineer/workspace/backtest/.agents/skills/<LENS>/SKILL.md
  (load the relevant references/ file before any load-bearing claim)

SHARED FACTS (identical for every seat — do not add or assume others):
  <verbatim fact block: prices, dates, holdings, constraints, the exact situation>

THE ONE QUESTION:
  <the single decision, phrased identically for every seat>

Return ONLY this shape, terse, in your final message (nothing else):
  VERDICT: <one clear call>
  CONVICTION: low | med | high
  REASONING: 3-5 lines, grounded in THIS lens (cite its framework/numbers)
  WHAT WOULD CHANGE MY MIND: <the specific trigger/observation that flips you>
  THIS LENS'S BLIND SPOT: <one line — what this lens structurally cannot see>

Do NOT bring in other authors/frameworks. Stay in this one lens. Be terse;
final message only. You are a context firewall — do not echo the source material.
```

Why this shape: VERDICT + CONVICTION make the table; WHAT-WOULD-CHANGE-MY-MIND gives the synthesis its
triggers; THIS-LENS'S-BLIND-SPOT stops any seat being treated as gospel. The "one lens, no other authors"
rule is what makes the disagreement real instead of every agent regressing to a balanced mush.
**Subagents are a context firewall** — the main agent must never load all the source material itself.

## The synthesis rule (the heart — do not average)

1. **Build the verdict table**: one row per lens — Verdict / Conviction / one-line reasoning.
2. **Find the consensus = the OVERLAP, not the average.** What do lenses that "barely speak the same
   language" nonetheless all land on? That intersection is the durable answer. (In the BTC case: *nobody
   lumps; start small; gate on confirmation.*)
3. **Preserve dissent explicitly.** Name each minority view, who holds it, at what conviction, and
   **state what would flip the majority toward it.** Dissent is parked, never deleted.
4. **Resolve conflicts by decision, not by vote-count.** State the decision, **which lens(es) it honors**,
   and **which minority view is parked and why** — with the trigger that would un-park it.
5. **Never let a high-conviction minority get silently outvoted.** A lone high-conviction dissenter
   (e.g. the liquidity seat screaming WAIT) must be surfaced, not buried under 4 mediums. It often names
   the real risk.
6. **Flag false consensus.** If the "agreement" is really 3 correlated lenses (e.g. three inflationists),
   say so — that's one view, not three. Real consensus crosses worldviews.

## Honesty rules (non-negotiable)

- **Actually RUN it before reporting a quorum result.** Prior failure: an agent once started writing up a
  quorum that had **not been run** in-session — it flagged the gap, ran it for real, then wrote. Never
  narrate a quorum you didn't execute. If you haven't spawned the subagents, you don't have a result.
- **Each lens is a lens, not gospel.** Every seat carries its own blind spot by design.
- **Don't strawman a seat** to manufacture consensus — give each its strongest grounded form.
- **Date the verdict.** Tactical/market calls decay; stamp the date and the facts they rest on, and say
  what would force a re-run.
- **Ground each seat** in its skill's references + primary source; flag extrapolation beyond the source.

## Example

<example>
User: "I'm starting the BTC position — $6k for the first tranche. What cadence should I buy at? Convene a
quorum."

This is a reversible-expensive judgment call spanning sizing, cost, value, liquidity, and behavior —
convene. Six lenses chosen to disagree, each reads ONE skill, identical facts, one question:

**Shared facts (2026-06-08):** $6k allocated to a first BTC tranche; book otherwise built; BTC ~$66k,
~48% below the Oct-2025 top, below 200d MA, Extreme Fear; self-custody assumed. Question: *over what
cadence should the $6k be deployed?*

| Lens | Verdict | Conviction | One-line reasoning |
|---|---|---|---|
| `analyst-systematic-trading` (Carver) | Fewer, bigger clips | med | Cost speed limit — many tiny buys waste the budget on fees/spread; size to keep costs ≤⅓ of edge |
| `analyst-technical-analysis` (Bernstein) | Calendar DCA, no timed entry | low | No trigger yet (below trend); "no trigger, no trade" — so don't time, just space it |
| `analytics-benjamin-graham` | Slow, small, quarantined | high | No intrinsic value → no margin of safety; deploy slowly and cap exposure regardless |
| `analytics-lyn-alden` | Steady DCA, don't overthink | high | Structural debasement; idle cash is the risk — get invested on a calendar, hold cycles |
| `analytics-morgan-housel` | Automate it, remove yourself | med | Behavior is the weak link; a fixed schedule beats discretion under Extreme Fear |
| `analyst-crypto` (Howell) | Deploy ~half now, gate the rest | med | Liquidity tide still out; commit a base, condition the remainder on liquidity turning |

**Consensus (the overlap, not the average):** **$1,000/week × 6 weeks, on the calendar.** Six lenses
that barely share a vocabulary all land on *spaced, calendar-based, removed-from-emotion* deployment.

**Unanimous kills:** no **$100/day** (fee drag — Carver's speed limit, and pointless granularity); no
**lump sum** (every seat stages, even the structural bull); no **accelerate-on-fear** (Extreme Fear is
not a trigger while price is below trend and the tide is out — Howell + Bernstein veto it).

**Preserved dissent (parked, with flip-triggers):**
- **Howell (med):** deploy only ~half the $6k now, **gate the rest on liquidity turning** (200d reclaim /
  liquidity re-crossing trend), not on the calendar. *Flips the plan to front-loaded if liquidity turns
  before week 6.*
- **Carver (med):** prefers **fewer, bigger clips** on pure fee grounds — would rather do 2-3 larger buys
  than 6. *Honored partially:* weekly (not daily) clips already respect the cost limit; if fees on $1k
  buys are material on the chosen venue, collapse to 3×$2k.

**Decision (2026-06-08):** $1,000/week × 6 weeks calendar DCA, self-custody. Honors Alden/Housel/Graham/
Bernstein (spaced, automated, capped). Howell's gate is **parked, not dismissed** — if liquidity turns
before week 6, switch the remaining tranches to confirmation-paced. Carver's fee point is satisfied by
weekly-not-daily; revisit clip size if venue fees bite. **Re-run if** BTC reclaims the 200d, liquidity
turns, or the facts above stop holding.
</example>

## Done when

- [ ] Convened **only** for a real, reversible-expensive **judgment** call (not a fact/lookup/code fix,
      and not a question one lens clearly owns).
- [ ] **4-7 genuinely-divergent** lenses, including **at least one dissent/contrarian seat**.
- [ ] **Identical facts + one identical question** sent to every seat (context-firewall subagents).
- [ ] Every seat returned the **fixed shape** (verdict / conviction / reasoning / what-flips-me / blind
      spot).
- [ ] Synthesis reports the **consensus as overlap**, **preserves each dissent with its flip-trigger**,
      and surfaces (never silently outvotes) any high-conviction minority; flags false/correlated
      consensus.
- [ ] Result is **dated** with the facts it rests on.
- [ ] You **actually ran it** — real subagents, real verdicts — before reporting.
