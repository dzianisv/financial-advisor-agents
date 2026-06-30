---
name: stocks-daily
description: >
  Weekly stocks publishing workflow. Reads the user's cached positions
  (.cache/stocks-daily/positions.csv), runs the stocks-advisor 5-seat holdings panel,
  then publishes three outputs: (1) a dated Notion page (via stocks-advisor), (2) a
  per-stock recap to the configured Telegram channel (target read from
  .cache/stocks-daily/telegram.yaml at runtime, never hardcoded), and (3) optionally a
  short X.com tweet. Despite the `daily` name the cadence is WEEKLY. Triggers on:
  "/stocks-daily", "run weekly stocks report", "publish stocks weekly report",
  "post stocks to telegram". Educational, not financial advice.
license: MIT
compatibility: opencode
metadata:
  audience: equity-allocators
  domain: equity-portfolio-management
---

# stocks-daily

**One-liner:** Weekly portfolio review. Reads cached positions, runs the stocks-advisor 5-seat panel, then publishes the result to three outputs: (1) a dated Notion page (via stocks-advisor), (2) a per-stock recap to the **Telegram channel** (config-driven target), and (3) optionally a short X.com tweet. Despite the `daily` name, the cadence is WEEKLY (user chose the command name). Educational, not investment advice.

**Triggers:** `/stocks-daily`, "run weekly stocks report", "publish stocks weekly report", "post stocks to telegram"

---

> **Disclaimer:** Output is educational analysis for a backtesting research environment. Nothing here is financial advice. All verdicts must be validated against your own risk tolerance and a licensed advisor before acting.

---

## CONFIG

```
POSITIONS_CSV  = /Users/engineer/workspace/backtest/.cache/stocks-daily/positions.csv
TELEGRAM_YAML  = /Users/engineer/workspace/backtest/.cache/stocks-daily/telegram.yaml   # channel target (read at runtime)
NOTION_YAML    = /Users/engineer/workspace/backtest/.cache/stocks-advisor/notion.yaml    # Notion target (owned by stocks-advisor)
```

- `POSITIONS_CSV` — the user maintains this file; the skill NEVER invents or edits it.
- `TELEGRAM_YAML` — holds `channel_id` (e.g. `-1004393946155`) + `invite_link`. **Read the channel id at
  runtime — never hardcode it in this file or in a message.** If the file is missing or `channel_id` is
  empty, **skip the Telegram step silently** (absence is not an error).
- `NOTION_YAML` — read by stocks-advisor; Notion publishing is delegated there (Step 4).

---

## Step 1 — Load positions

1. Read `POSITIONS_CSV`. Schema: `Position,Quantity,Type,Unrealized_PnL`.
2. If the file is missing or empty, stop immediately. Tell the user:
   > "Create `{POSITIONS_CSV}` with columns: Position,Quantity,Type,Unrealized_PnL. One row per holding."
3. Parse into a holdings list: ticker, qty, type, pnl.
4. Tag crypto-adjacent names as HOLD-ONLY. The user is crypto-bullish; never recommend selling these:
   `COIN, TONX, CRCL, HOOD, SOFI, IBKR, BTC` (and any ticker the user has flagged crypto-related in the CSV `Type` column as `crypto-beta`).
   Pass these through to analysis but mark them exempt from EXIT/TRIM recommendations.

---

## Step 2 — Run the analysis (delegate to stocks-advisor; do NOT reimplement)

1. Read the project daily log (`.agents/memory/YYYY-MM-DD.md`) to extract any prior weekly context for these tickers — pass it as `prior_context` to bias the run toward changed names.
2. Invoke the `stocks-advisor` skill in **holdings-review mode** on the parsed positions list.
   stocks-advisor handles: Step -1 memory recall, Step 0.7 TradingView health check (DEGRADED fallback = MA-only, WATCH-only verdicts), Step 0.8 triage (N>12 → full-panel top K≈10, one-line screen the rest), 5-seat panel analysis, Step 3.5 SOURCES & DATA appendix, Step 3.6 high-confidence RECAP + SETUP ALERTS.
3. Do NOT pull TradingView data, yfinance, or fundamentals yourself — stocks-advisor's orchestrator does that.
4. Collect stocks-advisor's full output for assembly in Step 3.

---

## Step 3 — Assemble the weekly report

Compose a single Markdown document in this order:

### (a) Date + Book Snapshot
- Report date
- Total equity (sum of positions × approximate price or use PnL + cost basis from CSV if available)
- Top-10 concentration % (top 10 positions as % of total book)
- Crypto-beta % (HOLD-ONLY names as % of total book)

### (b) Financial Narrative
- Sourced narrative from stocks-advisor's narrative seat.
- Every factual claim MUST include a URL citation. Reuse stocks-advisor's narrative output verbatim where possible.

### (c) High-Confidence RECAP Table
- Source: stocks-advisor Step 3.6 output.
- Only verdicts with conviction ≥ 4.
- Columns: Asset | Action (ADD/TRIM/EXIT) | One-line reason.
- HOLD-ONLY names: show as HOLD regardless of analysis output.

### (d) SETUP ALERTS Table
- Source: stocks-advisor Step 3.6 setup alerts.
- Columns: Asset | Exact condition | Then-do | Thesis.
- After the table, add: "Register these alerts via the `mkt` skill."

### (e) DROP List
- Non-crypto-beta EXIT and TRIM candidates with one-line reasoning.
- Never include HOLD-ONLY names here.

### (f) ETF Section
- Which ETFs in the portfolio are fair/undervalued vs extended, per stocks-advisor ETF analysis.
- Note if only trend/MA data was available (no fundamental data for ETFs).

### (g) SOURCES & DATA Appendix
- All web-fetched URLs used in analysis.
- Fundamentals.py provenance (which tickers used live data vs cached).
- Reuse stocks-advisor Step 3.5 output verbatim.

---

## Step 4 — Publishing (delegated to stocks-advisor)

Notion publishing is owned by `stocks-advisor`. When `.cache/stocks-advisor/notion.yaml` is configured, the Step 2 delegation to stocks-advisor publishes the research as a dated Notion page (title `YYYY-MM-DD <narrative>`) and returns its URL. stocks-daily does NOT publish separately — this avoids duplicated publish logic. Capture the URL stocks-advisor returns for the Telegram link (Step 4.5) and the memory step. If stocks-advisor's Notion config is absent, no page is published (publishing is opt-in there); surface that to the user rather than re-implementing publishing here.

---

## Step 4.5 — Post the per-stock recap to the Telegram channel

This is the user-facing deliverable. The Telegram message stays short and links to the full Notion report.

**4.5a — Read the channel target at runtime (never hardcode):**
```bash
TELEGRAM_CLI=~/.agents/skills/telegram-cli/telegram-cli.py
CHANNEL=$(grep '^channel_id:' .cache/stocks-daily/telegram.yaml 2>/dev/null | sed -E 's/.*"([-0-9]+)".*/\1/')
[ -z "$CHANNEL" ] && echo "No telegram.yaml channel_id — skipping Telegram (not an error)" # then skip 4.5
```

**4.5b — Build the per-stock recap message(s).** Each FULL-PANEL stock block carries **one sentence from each
of the 5 seats** (pulled from stocks-advisor's per-stock verdict). No seat line may be omitted. Use the exact
stocks-advisor seat labels — Fundamental / Technical / Narrative / Sentiment / Smart-Money — NOT the crypto
seats.

```
📊 Stocks Weekly — {TODAY} | Regime: {one phrase, e.g. "risk-off, debasement unwind"}
{1-sentence macro context — the single dominant driver this week}

━━━━━━━━━━━━━━━━━━━━━━
{EMOJI} {TICKER} ${PRICE} — {DECISION}
  📊 Fundamental:  {1 sentence — key metric (plain explanation in parens)}
  📈 Technical:    {1 sentence — chart indicator (plain explanation in parens)}
  📰 Narrative:    {1 sentence — theme/catalyst (plain explanation in parens)}
  🌡 Sentiment:    {1 sentence — crowding/positioning (plain explanation in parens)}
  🐋 Smart-Money:  {1 sentence — flows/filings (plain explanation in parens); or "no data this run"}
━━━━━━━━━━━━━━━━━━━━━━
...repeat for each FULL-PANEL stock...
━━━━━━━━━━━━━━━━━━━━━━

🟢 BUY/ADD:  {space-separated tickers WITH price, e.g. META $562 · HOOD $102}
🟡 HOLD:     {space-separated tickers}
🔴 TRIM/EXIT:{space-separated tickers}

📋 Full 5-seat report (Notion):
{NOTION_PUBLIC_URL}

DYOR. Educational only. Not financial advice. #Stocks #Investing
```

**Concrete stock block example:**
```
🔴 COIN $149 — TRIM
  📊 Fundamental:  Fwd P/E 38, FCF yield 1.1% (rich); rev tied to crypto volume (cyclical, not steady).
  📈 Technical:    Below 200d MA ($178 long-term avg), RSI 41 (weak), MACD bearish — downtrend intact.
  📰 Narrative:    Debasement trade unwinding (gold −12% MTD, BTC down) — crypto-beta out of favor this week.
  🌡 Sentiment:    22.7% of the book in one name — extreme single-name concentration risk.
  🐋 Smart-Money:  No clean filing signal this run (openinsider 403) — flows inconclusive.

🟢 META $562 — ADD
  📊 Fundamental:  Fwd P/E 24, 22% rev growth, $50B+ FCF (cheap for the growth) — best risk:reward in book.
  📈 Technical:    Reclaimed 50d MA (short-term avg $548), RSI 58 (room to run) — trend turning up.
  📰 Narrative:    AI-capex monetization (ads + Llama) confirming in earnings — real beneficiary, not hype.
  🌡 Sentiment:    Rec_mean 1.6 across 60 analysts — well-owned but not euphoric.
  🐋 Smart-Money:  Net institutional accumulation per 13F roll-up — large buyers still adding.
```

**⛔ Rules (mirror crypto-daily):**
- Every seat line is **mandatory** — never omit a seat, never collapse to one summary line.
- Keep the technical term, then follow it with `(plain explanation)` in parentheses — write for a non-expert.
- Use concrete numbers where available ($, %, P/E, RSI).
- Signal emoji: **🟢 BUY / ADD · 🟡 HOLD / WATCH · 🔴 TRIM / EXIT / SELL**. HOLD is 🟡, never 🔴 — red is
  reserved for reduce-the-position actions only.
- **Crypto-beta HOLD-ONLY names** (Step 1: COIN-family the user is bullish on) — if the panel said EXIT/TRIM
  but the name is HOLD-ONLY, show it as 🟡 HOLD on Telegram. The one exception: if the user's own review
  this run explicitly approved a TRIM (e.g. trimming a 22% concentration down to target), honor that TRIM.
- If a seat returned no data, write "no data this run" — do not invent.
- The BUY/ADD summary line MUST include price for every ticker.
- No raw URLs inline — the Notion link is the ONLY URL in the message.
- **Length:** many stocks × 5 lines each will exceed 4096 bytes — split at stock boundaries into multiple
  messages. Send action names (TRIM/EXIT/BUY/ADD) first, HOLDs second:
  - Part 1: header + macro + every TRIM/EXIT/BUY/ADD stock block
  - Part 2: HOLD stock blocks + the group-summary lines + Notion link + disclaimer
  - Verify each part: `echo -n "$PART" | wc -c` — must be ≤ 4096.

**4.5c — Send via telegram-cli (numeric channel id from config):**
```bash
python3 "$TELEGRAM_CLI" send "$CHANNEL" "$PART1"
python3 "$TELEGRAM_CLI" send "$CHANNEL" "$PART2"   # if multi-part
```

**4.5d — Verify delivery:**
```bash
python3 "$TELEGRAM_CLI" read "$CHANNEL" --limit 1
```
The sent message appears as the most recent. Confirm the Notion URL is live before sending.

**Error handling:**
| Error | Fix |
|---|---|
| `session not authenticated` | `python3 "$TELEGRAM_CLI" login` |
| `ChatWriteForbiddenError` | The account must be a member with post rights on the channel |
| `Cannot find any entity corresponding to` | Re-confirm `channel_id` in telegram.yaml; the account must have joined the invite link first |
| Notion URL not accessible | Enable "Share to web" in Notion before sending |

---

## Step 5 — Persist memory (mandatory; do BEFORE replying to user)

Append to `.agents/memory/$(date +%F).md` using the standard workflow_memory_format:

```markdown
## stocks-daily — YYYY-MM-DD
**Query:** Weekly portfolio review
**Assets found:** [comma-separated tickers reviewed]
**Verdicts:**
- TICKER: [T1/T2/T3/AVOID] [ACCUMULATE/WAIT/AVOID/HOLD] | entry: [price zone or condition] | catalyst: [trigger] | invalidation: [kill condition]
**Key delta:** [what changed vs prior week — one sentence]
**Report:** [Notion page URL returned by stocks-advisor, or "inline" if unpublished]
```

stocks-advisor writes per-ticker detail memory; this step adds the weekly roll-up. Do not skip.

---

## Scheduling (document only; do not auto-create)

To automate: use the `schedule` skill or configure a cron that fires `/stocks-daily` once a week (e.g., Sunday evening).

The skill is **idempotent per week** — re-running creates another dated Notion page; no harm done.

---

## Done when

- [ ] `positions.csv` read and parsed without inventing data
- [ ] stocks-advisor analysis completed (holdings-review mode)
- [ ] Weekly report assembled: narrative + RECAP table + SETUP ALERTS + DROP list + ETF section + SOURCES appendix
- [ ] Notion publishing left to stocks-advisor (no duplicate publish here); captured the returned page URL if one was produced
- [ ] **Telegram recap posted to the channel** (id from `telegram.yaml`, read at runtime) with every stock's
      5 seat lines, correct signal emoji (🟢/🟡/🔴), multi-part split ≤4096 bytes, Notion link only in the
      final part — or skipped silently if `telegram.yaml` is absent
- [ ] Memory entry appended to daily log
- [ ] Response to user flags output as educational, not advice
