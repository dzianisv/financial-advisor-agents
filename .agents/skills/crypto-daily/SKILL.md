---
name: crypto-daily
description: >
  Daily crypto publishing workflow. Finds today's completed crypto-advisor analysis,
  then publishes three outputs: (1) Notion page with full report, (2) Telegram post to the
  @CryptoAiInvestor channel, (3) short tweet on X.com. If today's analysis is missing or stale
  (>12h), re-runs crypto-advisor first. Triggers on: "/crypto-daily", "post crypto
  daily", "publish today's crypto report", "send telegram crypto update", "tweet crypto signals".
compatibility: opencode
---

# /crypto-daily

Publish today's crypto portfolio analysis to Notion, Telegram, and X.com.

> Educational only. Not financial advice. No leverage. Ever.

---

## Prerequisites (one-time setup)

| Credential / Skill | Where it lives | Used for |
|---|---|---|
| **Notion MCP** | Built-in session tools (`notion-API-*`) | Creating Notion pages — no token needed |
| **telegram-cli skill** | `~/.agents/skills/telegram-cli/` | Posting to Telegram channel |
| **chrome-use skill** | `~/.agents/skills/chrome-use/` | Tweeting on X.com |
| Chrome running + logged into X.com | Real Chrome with DevTools allowed | chrome-use requires live Chrome session |

Telegram-cli script: `~/.agents/skills/telegram-cli/telegram-cli.py`  
Chrome-use binary: `~/.agents/skills/chrome-use/scripts/chrome-use`  
Notion parent page ID: read at runtime from `.cache/crypto-daily/notion.yaml` (`page_id` field) — **never hardcoded**

---

## Step 0 — Find today's analysis

**0a. Determine today's date** (never call `Date.now()` directly in skill instructions — use shell):
```bash
TODAY=$(date +%F)   # e.g. 2026-06-23
```

**0b. Check if today's run exists:**
```bash
REPORT="research/crypto-portfolio-${TODAY}.md"
MEMORY=".agents/memory/${TODAY}.md"

# Check report file exists and is fresh (< 12h)
if [ -f "$REPORT" ]; then
  AGE_SECS=$(( $(date +%s) - $(stat -f %m "$REPORT" 2>/dev/null || stat -c %Y "$REPORT") ))
  [ "$AGE_SECS" -lt 43200 ] && FRESH=true || FRESH=false
else
  FRESH=false
fi
```

**0c. Read the token universe from `.cache/crypto-daily/portfolio.csv`:**
```bash
PORTFOLIO_CSV=".cache/crypto-daily/portfolio.csv"
if [ -f "$PORTFOLIO_CSV" ]; then
  TICKERS=$(grep -v '^#' "$PORTFOLIO_CSV" | tail -n +2 | cut -d, -f1 | grep -v '^$' | paste -sd' ' -)
fi

if [ -z "$TICKERS" ]; then
  echo "LOG: $PORTFOLIO_CSV missing or yields zero tickers — falling back to crypto-advisor default universe."
  TICKERS=""   # empty string signals crypto-advisor to use its own default
fi
```

If `$TICKERS` is non-empty, pass it to crypto-advisor using the documented custom-run prompt:
```
Invoke the crypto-advisor skill. Token universe for this run: [<TICKERS space-separated>].
Follow all skill instructions: ...
```
If `$TICKERS` is empty (file missing or no rows), invoke crypto-advisor with no token override — it runs its built-in default universe.

**0d. If NOT fresh:** invoke `crypto-advisor` first (with the token universe determined in 0c), then return here.
**If fresh:** continue to Step 1 with the existing `$REPORT` file.

---

## Step 1 — Extract content from today's report

Read the report file and extract:
```bash
REPORT_CONTENT=$(cat "$REPORT")
```

Pull the three payload sections from the report:
1. **Signal table** — the `=== CRYPTO PORTFOLIO RUN ===` block
2. **Telegram recap** — the block starting with `📊 Daily Crypto Brief`
3. **Key facts for tweet** — top signal + top catalyst from Block 2

If the Telegram recap section is missing from the report, construct it per the `crypto-advisor` Step 6 format using the signal table and Block 2 verdicts already in the report.

---

## Step 2 — Create full Notion report via Notion MCP

Post the **complete per-token analyst report** (all 11 tokens × 5 seats + DeFiLlama data + news references) as a Notion page. This becomes the canonical URL that Telegram links to — the Telegram message itself stays short.

**2a. Read the Notion target from config** (STOP if missing or empty):
```bash
NOTION_CONFIG=".cache/crypto-daily/notion.yaml"
NOTION_PARENT_PAGE_ID=$(grep '^page_id:' "$NOTION_CONFIG" | sed -E 's/.*"([a-f0-9]+)".*/\1/')
[ -z "$NOTION_PARENT_PAGE_ID" ] && echo "ERROR: page_id empty in $NOTION_CONFIG" && exit 1
```

**2b. Build the full report content** from the run report file.

The Notion page MUST include (in order):
1. Signal table with price/RSI/zone/signal for all tokens
2. Portfolio governor decision (F&G regime → max buy count → top picks)
3. For EACH token: price, all MAs (EMA20/SMA50/SMA200/200wMA), death cross, RSI, MACD, then 5 seats (one sentence each with POSTURE label), bull/bear case, news references
4. News reference list at the bottom (numbered [¹][²]... matching inline citations in token sections)

**Reference formatting rule (applies to BOTH Notion and Telegram):**  
Do NOT embed raw URLs inline. Use numbered footnote-style references:
- Inline: "ETF outflows $1.79B [¹]" or "DTCC selected Chainlink [³]"
- Footer: `[¹] theblock.co/post/406451 — IBIT 2nd worst outflow week`  
This keeps text readable and compact.

**2c. Create page with full Notion Markdown content:**
```
mcp__claude_ai_Notion__notion-create-pages
  parent: {"type": "page_id", "page_id": "{NOTION_PARENT_PAGE_ID}"}
  pages: [{"properties": {"title": "📊 Crypto Daily — {TODAY}"},
           "icon": "📊",
           "content": "{FULL_REPORT_MARKDOWN}"}]
```
Save the returned `id` as `PAGE_ID` and `url` as `NOTION_PAGE_URL`.

**2d. Share the page publicly** — the Notion page URL from creation is workspace-scoped by default. To make it web-accessible:
- The MCP does not expose a "Share to web" toggle directly.
- The canonical public URL format is: `https://www.notion.so/{PAGE_ID_no_hyphens}`
- If the workspace has "Share to web" enabled by default, this URL is immediately shareable.
- If not: open the page in Notion → Share → "Share to web" → enable. Then use the public URL.
- Save the public URL as `NOTION_PUBLIC_URL`.

**2e. Print the page URL:**
```
✅ Notion page (public): {NOTION_PUBLIC_URL}
```

---

## Step 3 — Post ONE Telegram message with Notion link

**⛔ SINGLE MESSAGE RULE:** Send exactly ONE Telegram message per run. All per-token detail lives in Notion. The Telegram post links to the Notion page — it does NOT repeat per-token analysis inline. Multiple messages with different token analyses create inconsistency and confusion.

**3a. Build the single recap message:**

```
📊 Crypto Daily — {TODAY} | F&G {VALUE} {EMOJI} {LABEL}

{SIGNAL TABLE — compact, one token per line, format: EMOJI TICKER $PRICE — SIGNAL}

🔴 HOLD:             {space-separated tokens, e.g. BTC · PUMP}
🟡 BUY(small) WATCH: {governor-downgraded tokens, e.g. ETH · SOL · LINK}
⭐ BUY(small) ACTIVE: {top N governor picks WITH price, e.g. AERO $0.47 · JUP $0.22 · HYPE $62}

⚙️ Governor: F&G {VALUE} → max {N} active buys
{1-line macro context, e.g. "ETF -$1.79B week — Warsh hawkish, debasement trade unwinding"}

📋 Full analyst report (5 seats · DeFiLlama · news sources):
{NOTION_PUBLIC_URL}

DYOR. Educational only. Not financial advice. #Bitcoin #DeFi #Crypto
```

Rules:
- Signal table: one line per token — format exactly `EMOJI TICKER $PRICE — SIGNAL`
- Group summary: three lines — HOLD / BUY(small) WATCH / BUY(small) ACTIVE. **Never shorten labels** (🟡 WATCH: is wrong; must be 🟡 BUY(small) WATCH:)
- **ACTIVE line MUST include price for every token** — `AERO $0.47 · JUP $0.22 · HYPE $62` not just tickers. This is the only actionable line; price is mandatory.
- Macro context: ONE sentence max — the single most important driver today
- No raw URLs inline — the Notion link is the ONLY URL in the message
- Total message ≤ 4096 chars (verify: `echo -n "$RECAP" | wc -c`)

**3b. Send via telegram-cli:**
```bash
TELEGRAM_CLI=~/.agents/skills/telegram-cli/telegram-cli.py
python3 "$TELEGRAM_CLI" send @CryptoAiInvestor "$RECAP"
```

**3c. Verify delivery:**
```bash
python3 "$TELEGRAM_CLI" read @CryptoAiInvestor --limit 1
```
The sent message appears as the most recent message. Confirm the Notion URL is live before sending.

**Error handling:**
| Error | Fix |
|---|---|
| `session not authenticated` | `python3 "$TELEGRAM_CLI" login` |
| `ChatWriteForbiddenError` | Account must be admin of @CryptoAiInvestor |
| Notion URL not accessible | Enable "Share to web" in Notion before sending |

---

## Step 4 — Post tweet on X.com via chrome-use skill

**Invoke the `chrome-use` skill**, then compose and post a ≤ 280 char tweet.

**4a. Build the tweet (≤ 280 chars):**

Template:
```
🔮 Crypto {DATE} | F&G {value} Extreme Fear
BUY(small): {top 2-3 tokens} {price + 1-word catalyst each}
{dominant macro driver in 1 line}
DYOR. Not advice. #Bitcoin #DeFi #Crypto #quantarena.xyz
```

Example:
```
🔮 Crypto 2026-06-23 | F&G 23 Extreme Fear
BUY(small): AAVE $71 (RWA catalyst), LINK $7.6 (RSI 23), BTC $62k
AI/tech selloff = dip. Trend bearish — tranches only.
DYOR. Not advice. #Bitcoin #DeFi #quantarena.xyz
```

**Always verify ≤ 280 chars before proceeding:**
```bash
echo -n "$TWEET" | wc -c   # must be ≤ 280
```

**4b. Post via chrome-use — step by step:**

```bash
CHROME=~/.agents/skills/chrome-use/scripts/chrome-use

# 1. Open the X.com compose URL (requires Chrome to be running + logged in)
$CHROME open "https://x.com/compose/tweet"
sleep 4

# 2. Snapshot interactive elements to get @eN refs
$CHROME snapshot -i
# Look for: [textbox] "Post text" → assign it @e_compose

# 3. Use `fill` (NOT `type`, NOT `eval execCommand`) — fill clears first, then types once
#    ⛔ NEVER use execCommand('insertText') — it appends on every call and causes hashtag spam
#    ⛔ NEVER call type/fill/eval more than ONCE on the textbox
$CHROME fill @e_compose "$TWEET"
sleep 1

# 4. Verify the content is correct (must match TWEET, not contain repeats)
$CHROME eval "document.querySelectorAll('[contenteditable]')[0]?.innerText?.slice(0,100)"
# If output doesn't match the start of $TWEET → STOP, do not click Post

# 5. Re-snapshot to get fresh refs after typing
$CHROME snapshot -i
# Look for: [button] "Post" → assign it @e_post

# 6. Click Post ONCE
$CHROME click @e_post
sleep 3

# If click fails (button unresponsive after 2s), use keyboard fallback:
$CHROME left_click @e_compose   # re-focus textbox
sleep 0.5
$CHROME key "cmd+Return"       # Cmd+Enter submits on X.com compose
sleep 3

# 7. Screenshot proof of the posted tweet
$CHROME screenshot /tmp/tweet_proof_$(date +%F).png
```

> **@eN refs are dynamic** — read from `snapshot -i` output each run. Never hardcode.

> **⛔ Anti-spam rule:** Call `fill` or `type` **exactly once** on the textbox. If you see the textbox already contains text (from a draft), clear it first: `$CHROME eval "document.execCommand('selectAll');document.execCommand('delete')"` — then `fill` once.

> **If x.com redirects to login:** open `https://x.com` in Chrome manually, log in, then retry.

**4c. Embed the screenshot inline:**
```
view /tmp/tweet_proof_{date}.png
```
(Call the `view` tool on the file path to embed the image in your reply.)

---

## Step 5 — Report results

Print a summary of all three publishing actions:

```
=== /crypto-daily COMPLETE — {DATE} ===

📓 Notion:   ✅ https://www.notion.so/Crypto-Daily-{date}-{id}
             (or ❌ <error message>)

💬 Telegram: ✅ Sent to @CryptoAiInvestor (msg_id={id})
             (or ❌ <error message>)

🐦 X.com:    ✅ Posted (screenshot attached)
             (or ❌ <error message>)
```

Attach the tweet screenshot inline (call `view` tool on the screenshot path).  
If any step failed, report the error clearly — do NOT silently skip.

---

## Step 6 — Auto-eval

Run after Step 5 completes. Scores today's report against the crypto-advisor rubric and appends a row to the eval CSV.

**6a. Spawn a Judge subagent** (Agent tool, model=sonnet):

Pass the Judge this prompt (substitute `$REPORT` content inline):

```
You are a Judge evaluating a crypto-advisor run. Score the report against this rubric.

RUBRIC:
7 dimensions, each scored 0–5.

Score anchors (global):
5 = Perfect — no deviation from SKILL.md rule
4 = Correct approach, minor gap
3 = Right direction, soft on specifics or misses one named requirement
2 = Partial — roughly half right; material omission or error
1 = Mostly wrong — violates the principle more than follows it
0 = Violates the principle outright

Dimensions:
1. signal_correctness — quorum_verdict truth table applied correctly; signal decision rule applied correctly.
2. zone_discipline — zone guard enforced before signal; BUY blocked when zone=ELEVATED/EXTREME/UNKNOWN; BUY(small) blocked when zone≠DEEP_VALUE.
3. data_sufficiency — 200wMA marked INSUFFICIENT when weekly_closes<200; fallback data tagged; zone forced UNKNOWN when data insufficient.
4. source_discipline — no listing/search pages cited as final sources; every citation has https:// + verbatim quote; FETCH FAILED for non-fetched sources; ≥3 T1/T2/T3 sources ranked.
5. critic_coverage — critic spawned for ALL N tokens; INCOMPLETE printed if any skipped; FLAGs acted on.
6. portfolio_governor — buy count capped by F&G regime; downgrades applied ranked by conviction; governor result printed.
7. no_fabrication — no unverified claims; no hallucinated URLs; no news facts without [source: https://...]; HOLD default when uncertain.

REPORT TO EVALUATE:
<report>
{paste full content of research/crypto-portfolio-{TODAY}.md here}
</report>

For each dimension, give a score 0–5 and one-line failure mode (or PASS).
Return ONLY this JSON (no prose):
{
  "signal_correctness": {"score": N, "note": "..."},
  "zone_discipline": {"score": N, "note": "..."},
  "data_sufficiency": {"score": N, "note": "..."},
  "source_discipline": {"score": N, "note": "..."},
  "critic_coverage": {"score": N, "note": "..."},
  "portfolio_governor": {"score": N, "note": "..."},
  "no_fabrication": {"score": N, "note": "..."},
  "overall": N,
  "summary": "one sentence"
}
```

Save the returned JSON as `$JUDGE_JSON`.

**6b. Parse the JSON and append a row to the eval CSV:**

```bash
TODAY=$(date +%F)
COMMIT=$(git rev-parse --short HEAD)

python3 - << 'PY'
import json, csv, os, sys

judge_json = os.environ.get("JUDGE_JSON", "")
try:
    result = json.loads(judge_json)
except Exception as e:
    print(f"ERROR parsing judge JSON: {e}", file=sys.stderr)
    sys.exit(1)

today = os.environ["TODAY"]
commit = os.environ["COMMIT"]

row = {
    "commit_id": commit,
    "iteration": f"auto-{today}",
    "prompt_summary": f"crypto-daily auto-eval {today}",
    "output_summary": f"live run: {result.get('summary', '')}",
    "score_correctness": result["signal_correctness"]["score"],
    "score_completeness": result["zone_discipline"]["score"],
    "score_clarity": result["data_sufficiency"]["score"],
    "score_overall": result["overall"],
    "judge_feedback": " | ".join(
        f"{k}: {v['note']}"
        for k, v in result.items()
        if isinstance(v, dict) and "note" in v
    )[:300]
}

csv_path = ".cache/crypto-advisor/crypto-advisor.eval.csv"
write_header = not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0
with open(csv_path, "a", newline="") as f:
    w = csv.DictWriter(f, fieldnames=row.keys())
    if write_header:
        w.writeheader()
    w.writerow(row)

print(f"Eval recorded: overall={row['score_overall']}/5")
PY
```

Export `TODAY`, `COMMIT`, and `JUDGE_JSON` as env vars before running the script:
```bash
export TODAY COMMIT JUDGE_JSON
```

**6c. Print the eval summary:**

```
=== AUTO-EVAL — {DATE} ===
signal_correctness: {N}/5
zone_discipline:    {N}/5
data_sufficiency:   {N}/5
source_discipline:  {N}/5
critic_coverage:    {N}/5
portfolio_governor: {N}/5
no_fabrication:     {N}/5
─────────────────────
OVERALL:            {N}/5
{summary sentence}
CSV: .cache/crypto-advisor/crypto-advisor.eval.csv
```

**6d. Low-score warning:**

If `overall < 3.0`, print:
```
WARNING: LOW SCORE — consider re-running crypto-advisor with stricter guardrails before next publish.
```

---

## Scheduling

```
/loop interval=24h   ← runs once per day at this interval
/stop                ← cancel
```

For cron, add to `crontab`:
```
0 9 * * * cd /Users/engineer/workspace/backtest && copilot "run /crypto-daily"
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Notion: `401 Unauthorized` | Re-check `NOTION_TOKEN` in `~/.env.d/notion.env` |
| Notion: `404 object not found` | `NOTION_PARENT_PAGE_ID` wrong — re-copy from Notion URL |
| Telegram: `session not authenticated` | `python3 telegram-cli.py login` |
| Telegram: `ChatWriteForbiddenError` | Add account as admin of @CryptoAiInvestor |
| X.com: wrong `@eN` ref | Re-run `$CHROME snapshot -i` and use the new ref |
| X.com: not logged in | Log in manually in Chrome, then retry |
| Analysis stale | Delete `research/crypto-portfolio-{today}.md` and re-invoke |
