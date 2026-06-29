# crypto-daily — Modification Guide for Agents

> Read this file completely before editing SKILL.md. It is the contract between the skill and its users.
> Any modification that breaks the validation checklist at the bottom is **rejected** — revert and fix.

---

## What this skill produces

Three outputs per daily run:
1. **Notion** — full analyst report (signal table + per-token Block 2 with researcher recaps + Block 3 sources)
2. **Telegram** (@CryptoAiInvestor) — multi-part messages, one per-token block each
3. **X.com** — ≤280 char tweet summary

---

## How to modify this skill

### Allowed changes (no special approval needed)
- Fix broken bash commands or CLI flags
- Update Notion MCP tool names if they change
- Fix telegram-cli invocation flags
- Improve clarity of instructions without changing output format
- Add error-handling steps

### Changes that require preserving the Telegram format contract
- Any edit to Step 3 (Telegram) must keep the per-token block structure intact (see contract below)
- You may add content but may NOT remove or collapse the 5 researcher lines per token
- You may reorder sections within a part but may NOT merge parts or reduce to a single message

### Changes that require explicit user approval before committing
- Removing any of the 5 researcher lines (Technical / On-Chain / DeFi / Macro / Smart Money)
- Changing signal emoji mapping (🟢/🟡/🔴)
- Switching back to a single-message format
- Renaming researcher labels
- Moving the Notion link out of the final part

---

## Telegram format contract

The Telegram output is the primary user-facing product. It was deliberately designed after multiple regressions where the signal was shown but the reasoning was not. **Every token must show WHY, not just WHAT.**

### Per-token block — exact structure, mandatory

```
{SIGNAL_EMOJI} {TICKER} ${PRICE} — {SIGNAL}
  📈 Technical:   {1 sentence — chart indicator (plain explanation in parens)}
  ⛓ On-Chain:    {1 sentence — on-chain metric (plain explanation in parens)}
  🏛 DeFi:        {1 sentence — protocol revenue/TVL (plain explanation in parens); or "n/a — base layer asset"}
  🌍 Macro:       {1 sentence — macro driver (plain explanation in parens)}
  🐋 Smart Money: {1 sentence — exchange flows/whale activity (plain explanation in parens)}
```

All 5 lines are mandatory for every token. If a researcher had no data, write `no data this run` — never omit the line.

### Signal emoji — hard rule

| Signal | Emoji |
|---|---|
| BUY / BUY(small) active | 🟢 |
| HOLD / WATCH / gov-downgraded BUY | 🟡 |
| SELL | 🔴 |

🔴 means SELL. Never use it for HOLD. This confused readers and was explicitly corrected.

### Language rules — hard

- **Keep the technical term** (RSI, death cross, MACD, EMA20, TVL, MVRV-Z…) — do not rename or drop it
- **Follow every jargon term with `(plain English explanation)`** — e.g. `RSI 30 (oversold — near historical buy zone)`
- **Ban from Telegram output**: `DEEP_VALUE`, `FAIR_VALUE`, `ELEVATED`, `EXTREME`, `BULLISH`, `BEARISH`, `UNCERTAIN`, `SPLIT`, `seats_bull`, `seats_bear`, `quorum_verdict`, `0B/4Br`, `INSUFFICIENT` — translate these to plain English
- Use numbers ($, %, timeframes) over adjectives

### Multi-part split — required

11 tokens × 5 lines each exceeds 4096 bytes. Always split:
- **Part 1**: header + macro context + BUY/BUY(small) active tokens
- **Part 2**: gov-downgraded HOLD tokens (would be BUY in normal regime)
- **Part 3**: remaining HOLDs + group summary + Notion link + disclaimer

Notion link goes in Part 3 only. No raw URLs in Parts 1 or 2.

---

## Validation checklist — run before every commit to SKILL.md

An edit to SKILL.md is only complete when ALL of these pass. Check each one explicitly:

```
[ ] 1. TOKEN BLOCK STRUCTURE
        grep the Telegram section: does every token block have exactly 5 indented lines?
        Labels present: "Technical:", "On-Chain:", "DeFi:", "Macro:", "Smart Money:"

[ ] 2. SIGNAL EMOJI
        grep for 🔴.*HOLD — must return 0 matches
        HOLD/WATCH/gov-cap tokens use 🟡 only

[ ] 3. JARGON BAN
        grep Telegram section for: DEEP_VALUE FAIR_VALUE BULLISH BEARISH UNCERTAIN SPLIT
        Must return 0 matches

[ ] 4. PARENS RULE
        Each researcher line in the example must contain at least one (...) explanation
        e.g. "RSI 30 (oversold)" — not "RSI 30"

[ ] 5. MULTI-PART SPLIT
        Skill still instructs splitting into 3 parts
        Part 3 is where the Notion link appears
        No instruction to send a single message

[ ] 6. RESEARCHER LABELS UNCHANGED
        Labels must be exactly: Technical / On-Chain / DeFi / Macro / Smart Money
        Not renamed to Chart / Value / Protocol / Market / Flows or anything else

[ ] 7. NO RESEARCHER LINE COLLAPSE
        Skill does not say "summarise the 5 seats in one line" or equivalent
        Each seat gets its own line

[ ] 8. NOTION LINK NOT HARDCODED
        Notion parent page ID must be read from .cache/crypto-daily/notion.yaml at runtime
        Not hardcoded anywhere in SKILL.md
```

If any check fails → fix before committing. Do not merge a SKILL.md that fails this checklist.

---

## Regression history — do not repeat

| Date | What broke | Cause | Fix |
|---|---|---|---|
| 2026-06-28 | Telegram had zero reasoning ("HOLD BTC" with no why) | `b1cd3e9` refactor dropped Research Desk briefs from output | `bd26185` added 5-researcher lines to Telegram |
| 2026-06-28 | Researcher labels renamed to Chart/Value/Protocol/Market/Flows | Attempted "plain English" renaming | `fa5eab1` reverted — keep names, add `()` explanations instead |
| pre-2026-06-28 | Single-message rule led to truncated output | 11 tokens can't fit in 4096 bytes | Removed single-message rule; split into 3 parts |

---

## Files owned by this skill

| Path | Purpose |
|---|---|
| `.agents/skills/crypto-daily/SKILL.md` | Agent instructions (this is what you edit) |
| `.agents/skills/crypto-daily/AGENTS.md` | This file — modification contract |
| `.cache/crypto-daily/notion.yaml` | Notion target page (runtime, never hardcode) |
| `.cache/crypto-daily/portfolio.csv` | Optional token universe override |
