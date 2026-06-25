---
name: portfolio-memory
description: "Cross-run memory for stocks-advisor and crypto portfolio agents. Reuses OpenClaw memory-core's two-tier model: a canonical evergreen surface (.agents/memory/positions.md — one line per <desk>:<TICKER>, overwritten on every new verdict so latest always wins) plus dated episodic logs (.agents/memory/YYYY-MM-DD.md — decay by filename date, newer outranks older). Recall via recall.ts (tries `openclaw memory search` hybrid ranker, else greps). Write via remember.ts (mechanical upsert of the canonical line). Replaces the old bespoke SQLite/BM25 store. Triggers: stocks/crypto advisor Step -1 (load) and Step 1g (write)."
license: MIT
compatibility: opencode
metadata:
  domain: agent-memory
  role: cross-run-state
  source: "Reuses OpenClaw memory-core architecture (extensions/memory-core/src/memory/{hybrid,temporal-decay,mmr}.ts, short-term-promotion.ts); decision logged .agents/memory/2026-06-24.md"
---

# Portfolio Memory — two-tier, ranked (OpenClaw model)

Cross-run memory for the portfolio agents, reusing OpenClaw memory-core's design instead of a bespoke store. The agent never re-derives that COIN is a hold, that PYPL is a value trap, or what the user prefers — and it can never follow a stale verdict over the current one, because the current stance physically overwrites the old one.

## Why two tiers (the architecture we reuse)

OpenClaw memory-core splits memory by **whether it should decay** (`temporal-decay.ts:71-95`):

| Tier | File | Decay | Role |
|---|---|---|---|
| **Canonical / evergreen** | `.agents/memory/positions.md` | never | current stance — one line per `<desk>:<TICKER>`, overwritten on change |
| **Episodic / dated** | `.agents/memory/YYYY-MM-DD.md` | `0.5^(age/halfLife)` by **filename date** | history — newer notes outrank older |

The canonical surface is the supersede mechanism. When a verdict changes, `remember.ts` **replaces** that ticker's one line — it is enforced by code, not by asking the agent to remember to cross out the old note (which it would forget to do). This is exactly OpenClaw's "evergreen MEMORY.md overwrite-on-change": latest write wins by construction. The dated logs keep the full audit trail (HOLD→TRIM both visible), ranked by recency.

> The old store kept two contradictory same-day COIN notes with equal weight, so the next run could follow the dead one. The canonical surface makes that impossible: COIN has exactly one current line.

## Recall — `recall.ts` (replaces inject_context.py)

```bash
bun .agents/skills/portfolio-memory/recall.ts --desk stocks --tickers "AVGO MRVL COIN PYPL" [--q "AI supply chain"] [--k 8]
```

Ranking, best available first:
1. **OpenClaw hybrid** — if the `openclaw` CLI is built *and* configured to index `.agents/memory` (set `memorySearch.extraPaths` to include it), recall.ts shells out to `openclaw memory search --json`, which ranks with normalize-then-weighted-sum hybrid BM25+vector × temporal-decay × MMR. Evergreen files are exempt from decay automatically.
2. **Grep fallback** (default today — the local checkout is unbuilt) — canonical lines always shown; dated logs grepped newest-file-first (recency) for exact ticker match. A deliberate subset: exact-match + recency only.

Inject the printed `<prior_context>` block into EVERY analyst seat's data package.

## Write — `remember.ts` (replaces memory.py remember)

After each ticker's panel completes:

```bash
bun .agents/skills/portfolio-memory/remember.ts \
  --desk stocks --ticker COIN --verdict TRIM --date 2026-06-24 \
  --conviction 2 --body "REVISED: harvest half, keep core; rev -30.8%; below 200d -36%; fwd PE 30"
```

`--verdict` one of `BUY|ADD|WATCH|HOLD|TRIM|EXIT|SELL|SKIP`. Two writes happen:
1. **Canonical UPSERT** into `positions.md` — replaces the `stocks:COIN |` line if present, else appends. `[superseded]` vs `[new]` is printed.
2. **Append** a compact line to `.agents/memory/<date>.md` under `## verdicts` — episodic history.

**body contract:** lead with the cause, keep ≤200 chars, include the key metric + theme. The canonical line is what the next run reads first, so make it self-explanatory.

## Durable user preferences

Preferences ("crypto bullish — do not sell COIN", "RSP over VOO") are durable, never-decay facts → they belong in the evergreen tier. Store them as canonical lines with a `pref` pseudo-ticker, e.g.:

```bash
bun .agents/skills/portfolio-memory/remember.ts --desk stocks --ticker PREF_CRYPTO --verdict HOLD --date <date> --body "crypto bullish — do not force-sell COIN/HOOD/CRCL on drawdown"
```

recall.ts surfaces all `stocks:*` canonical lines when called with no `--tickers`, so preferences are seen every run.

## One-time OpenClaw wiring (optional, enables the hybrid ranker)

The grep fallback works with zero setup. To upgrade recall to OpenClaw's full ranker:
1. Build/install the CLI (`npm i -g openclaw@latest`, or `pnpm build` in the checkout).
2. Add `.agents/memory` to `memorySearch.extraPaths` in OpenClaw config so it indexes the canonical + dated files.
3. `openclaw memory index --force` once. recall.ts auto-detects and uses it.

Never hard-depend on the CLI — recall.ts always degrades to grep.

## Tests

`bun test ./.agents/skills/portfolio-memory/memory.test.ts` — 10 end-to-end tests over the real
CLIs: supersede-by-overwrite, dated-history preservation, desk isolation, recall ordering
(canonical-first then dated newest-first), preferences, empty-memory sentinel, word-boundary ticker
matching, arg validation. Re-run after any edit to recall.ts/remember.ts.

## Done when

- `remember.ts` for an existing ticker prints `[superseded]` and `positions.md` still has exactly ONE line for that `<desk>:<TICKER>`.
- The dated log keeps both the old and new verdict (history preserved).
- `recall.ts --tickers "COIN"` prints the current canonical stance first, then dated history newest-first.
- `recall.ts` with no `--tickers` returns all canonical lines (preferences included).
- With no prior memory, `recall.ts` prints `[no prior memory for this run]` and the run continues.
