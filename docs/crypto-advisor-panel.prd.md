# PRD — Crypto-Advisor Panel (School-Based Quorum)

Aligns to `docs/prd.md` §SLOW tier. Redesigns the 5-seat quorum inside `crypto-advisor`
so that every opinion lives in a named investment school, not in hardcoded signal-table rules.
Educational only. Not financial advice. No leverage. Ever.

---

## Problem

The current `crypto-advisor` skill mixes orchestration logic with investment opinions:

- Zone gates (`BUY blocked at ELEVATED`) embed Howard Marks' cycle view as a hard rule.
- The SPLIT-quorum gate (`needs DEEP_VALUE`) embeds Graham's margin-of-safety view as a hard rule.
- These schools conflict with Lynch/Fisher (quality at fair price is fine), and the conflict is
  silently resolved by whoever wrote the rule last — not by deliberate design.
- No rule in the skill cites a book or article. Reviewers (human or judge) cannot audit the
  reasoning, only the outcome.
- When the run produces a questionable signal (HYPE: FAIR_VALUE → BUY(small) on 2/5 seats),
  the failure is invisible because the opinion is buried in a rule, not surfaced as a seat vote.

---

## Goal

A crypto-advisor skill where:

1. **The orchestrator is non-opinionated** — it collects data, distributes it, counts votes,
   applies a mechanical governor, and outputs a signal. It makes no market judgements.
2. **The panel is opinionated** — each seat is a named investment school with a book citation.
   The school decides what the data means for its framework and casts a vote.
3. **Conflicts between schools surface in the quorum** — not hidden in rule collisions.
4. **Every opinion is attributable** — each seat's vote comes with the school's one-line
   reasoning so the output is auditable.

---

## Investment Schools → Seats

Five seats. One per school. Each seat is a separate skill/subagent with its own system prompt
grounded in its school's canonical text.

| Seat | School | Core question | Primary reference |
|---|---|---|---|
| **Value** | Benjamin Graham / Seth Klarman | Is there a margin of safety? Is price sufficiently below intrinsic value to protect the downside? | *The Intelligent Investor* ch.20 (Margin of Safety); *Margin of Safety* (Klarman) |
| **Quality** | Phil Fisher / Peter Lynch | Is this a high-quality protocol with durable revenue growth available at a reasonable price? | *Common Stocks and Uncommon Profits* (Fisher); *One Up on Wall Street* ch.9 (Lynch) |
| **Cycle** | Howard Marks / John Templeton | Where are we in the market cycle? Is this genuine maximum pessimism or a falling knife? | *The Most Important Thing* ch.5–7 (Marks); Templeton's "buy at the point of maximum pessimism" |
| **Trend** | Stanley Druckenmiller / Robert Carver | What does price structure say? MA alignment, MACD, death cross vs golden cross. Don't fight the tape. | Druckenmiller interviews (George Soros *The Alchemy of Finance* trend-following framing); *Systematic Trading* (Carver) |
| **On-chain** | Crypto-native fundamentals | Does the token accrue real value? Protocol revenue, TVL, fee distribution mechanism, token sink. | *Cryptoassets* (Burniske & Tatar) §value-accrual; DeFiLlama methodology |

---

## Orchestrator Responsibilities (non-opinionated)

The main `crypto-advisor` skill does exactly this — nothing more:

1. **Fetch raw data** for each token: price, RSI, MAs (EMA20/SMA50/SMA200/200wMA or proxy),
   zone label (purely descriptive: % below ATH, % below 200wMA), weekly bar count,
   DeFiLlama protocol revenue/TVL/fees, F&G index, top-3 news headlines with source URLs.
2. **Build a data package** — a structured object containing all raw facts. No interpretation.
3. **Distribute in parallel** — send the same data package to all 5 seats simultaneously.
4. **Collect votes** — each seat returns: `vote ∈ {BULLISH, NEUTRAL, BEARISH}` + one-line reason.
5. **Count and map to signal**:

   | seats_bull | weekly_closes | Signal |
   |---|---|---|
   | ≥ 4 | ≥ 200 | BUY |
   | ≥ 3 | ≥ 200 | BUY(small) |
   | ≥ 3 | < 200 | BUY(small) — insufficient history, size down |
   | < 3 | any | HOLD |
   | seats_bear ≥ 4 | any | SELL |

   No zone conditions in this table. Zone is in the data package; seats decide what it means.

6. **Apply F&G governor cap** — mechanical position-sizing rule, not a market opinion:

   | F&G Regime | Max simultaneous BUY + BUY(small) |
   |---|---|
   | Extreme Fear (0–24) | 3 |
   | Fear (25–49) | 5 |
   | Neutral+ (50–100) | no cap |

   Rank by seats_bull descending, downgrade lowest-conviction BUYs until within cap. Print ranking.

7. **Output signal table + per-token verdict** with each seat's vote and reason line visible.

---

## What Changes vs Today

| Area | Today | After |
|---|---|---|
| Zone gate in signal table | BUY blocked at ELEVATED/EXTREME; BUY(small) blocked for SPLIT unless DEEP_VALUE | Removed — zone is raw input to seats only |
| Seat identity | On-chain / Sentiment / Macro / Order-flow / Narrative | Value / Quality / Cycle / Trend / On-chain |
| Opinion location | Hardcoded rules in signal table | Named seat prompts with book citations |
| Conflict resolution | Last rule wins (silent) | Quorum vote (visible) |
| Auditability | "HYPE got BUY(small)" — reason unclear | "Value: NEUTRAL (FAIR_VALUE, no margin of safety); Quality: BULLISH (best revenue/buyback ratio); Cycle: BULLISH (Extreme Fear = Templeton entry); Trend: BULLISH (golden cross); On-chain: BULLISH ($874M verified). 4/5 → BUY(small)" |
| Governor cap number | 4 (Extreme Fear) | 3 (tighter — Extreme Fear = Marks "move to caution") |

---

## Dual Runtime — Claude Code + Openclaw

The skill must run identically on both backends. The separation is:

- **Core** (runtime-agnostic): seat prompt templates, data package schema, vote schema,
  signal table, governor logic. Pure text + JSON. No Anthropic-specific primitives.
- **Adapter** (runtime-specific): how seats are invoked, how results are collected,
  how scheduling and delivery work.

### Runtime comparison

| Concern | Claude Code | Openclaw |
|---|---|---|
| **Models available** | Anthropic only (claude-sonnet-4-6, claude-opus-4-8, claude-haiku-4-5) | Any configured provider (Anthropic, OpenAI, Gemini, Mistral, local) |
| **Seat invocation** | `Agent` tool — one subagent per seat, parallel | openclaw plugin SDK call — one plugin per seat, parallel via plugin router |
| **Scheduling** | `CronCreate` / `ScheduleWakeup` | `cron create --cron` via openclaw native cron |
| **Delivery** | `telegram-cli` python script + Notion MCP | openclaw channel layer (`--target telegram`, `--target notion`) |
| **State / storage** | `.cache/` flat files + SQLite under `backtest/` | plugin storage API or shared `.cache/` mount |
| **Seat prompt location** | `~/.agents/skills/analysis-{school}/SKILL.md` | same files, loaded by plugin at runtime |

### Model diversity opportunity (openclaw only)

Because openclaw is not Anthropic-locked, each seat can run on a different provider,
giving genuine model diversity in the quorum — not just prompt diversity:

| Seat | Suggested model (openclaw) | Rationale |
|---|---|---|
| Value | GPT-5 / o3 | Strong structured reasoning for valuation math |
| Quality | Claude Sonnet | Best at synthesizing qualitative revenue narratives |
| Cycle | Gemini Pro | Strong macro/news corpus; Templeton framing fits retrieval |
| Trend | Claude Haiku | Fast, deterministic — MA alignment is mechanical |
| On-chain | Claude Sonnet | DeFiLlama data parsing + revenue accrual logic |

In Claude Code mode all seats run on Claude (model specified per seat via `model=` param).
The vote outcome should be comparable; model diversity is a bonus, not a requirement.

### Adapter interface (what core hands to the adapter)

```json
{
  "data_package": { ... },   // raw token data — same in both runtimes
  "seats": ["value", "quality", "cycle", "trend", "onchain"],
  "return_schema": {
    "vote": "BULLISH | NEUTRAL | BEARISH",
    "reason": "string (one line, cites school framework)"
  }
}
```

The adapter resolves how to execute each seat and returns an array of `{seat, vote, reason}`.
Core then counts votes and applies the signal table — identical in both runtimes.

---

## Out of Scope

- Changing the data sources (DeFiLlama, F&G, news fetchers) — those stay as-is.
- Changing the Telegram / Notion / X publish flow — that stays in `crypto-daily`.
- Changing the eval harness — judge rubric will update separately once seats stabilise.
- Adding new tokens to the universe — separate decision.

---

## Open Questions (block TDD)

~~1. Execution runtime~~ — **Resolved**: dual mode, Claude Code + openclaw. See §Dual Runtime.

2. **State / storage** — are seats stateless (fresh data package each run) or do they
   accumulate a rolling thesis across runs ("Value seat has been NEUTRAL on HYPE for 3 weeks")?
   Stateful seats produce richer longitudinal reasoning but need a storage contract and
   migration path between runtimes. Lean: stateless v1, stateful v2.

3. **Seat prompt ownership** — do school-seat prompts live in shared `analysis-{school}` skills
   (reusable by hedge-fund-committee and other skills) or inline in `crypto-advisor` only?
   Lean: shared skills — the same Graham seat should be usable by any panel skill.

4. **Openclaw plugin granularity** — is the entire `crypto-advisor` one openclaw plugin that
   internally spawns seats, or is each school seat its own plugin? One plugin is simpler to
   ship; separate plugins enable per-seat model override and independent versioning.

These three questions can be decided during TDD authoring — they do not block starting it.
