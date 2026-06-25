---
name: portfolio-memory
description: "Cross-run BM25 memory store for stocks-portfolio-manager and crypto-portfolio-manager. Stores per-ticker verdicts and durable user preferences. On each run: (1) recall() retrieves relevant prior context ranked by BM25 × exponential recency decay (half-life 45 days); (2) after analysis, remember_verdict() appends the new verdict. Prevents agents from forgetting prior calls (COIN=HOLD, PYPL=EXIT, crypto-bullish pref). SQLite FTS5 stdlib only — no embeddings, no external APIs. Triggers: 'what did we decide about COIN last time?', 'recall prior verdicts', 'inject memory context', 'remember this verdict', used internally by stocks/crypto-portfolio-manager."
license: MIT
compatibility: opencode
metadata:
  audience: portfolio-managers
  domain: cross-run-memory
  role: memory-store
---

# Portfolio Memory

Cross-run BM25 + recency-decay memory store. The PM skills forget everything between sessions — this
skill fixes that. Architecture mirrors `crypto-news-store/news_store.py` (stdlib SQLite FTS5 only).

## What it is

`memory.py` — stdlib python3 + sqlite3 only. Single SQLite file, default `.db/portfolio_memory.db`.

- **`memory`** — one row per verdict or analysis, indexed by FTS5 for BM25 recall.
- **`memory_fts`** (FTS5 virtual table) — BM25 over `ticker + body`; ticker column weighted 10×.
- **`preferences`** — durable user preferences (always injected, not BM25-gated).

## Schema

```sql
CREATE TABLE IF NOT EXISTS memory (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  kind        TEXT NOT NULL,        -- 'verdict' | 'analysis' | 'preference'
  desk        TEXT NOT NULL,        -- 'stocks' | 'crypto'
  ticker      TEXT,
  verdict     TEXT,
  body        TEXT NOT NULL,        -- what BM25 ranks
  meta        TEXT,                 -- JSON: entry, stop, target, conviction, theme, seats
  run_id      TEXT,
  created_at  TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts
  USING fts5(ticker, body, content='memory', content_rowid='id',
             tokenize='porter unicode61');

CREATE TRIGGER IF NOT EXISTS mem_ai AFTER INSERT ON memory BEGIN
  INSERT INTO memory_fts(rowid, ticker, body) VALUES (new.id, new.ticker, new.body);
END;

CREATE TABLE IF NOT EXISTS preferences (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  desk        TEXT,
  scope       TEXT,
  text        TEXT NOT NULL,
  created_at  TEXT NOT NULL
);
```

## Recency decay formula

```
score = -bm25(memory_fts, 10.0, 1.0)  ×  decay(created_at, 45.0)
decay(iso, half_life) = 0.5 ^ (age_days / half_life)
```

- `bm25()` returns **negative** numbers in SQLite FTS5 → flip with leading minus.
- Ticker column is weighted **10×** body — symbol queries (`COIN`, `PYPL`) dominate.
- `half_life = 45 days`: a verdict from 45 days ago is weighted 0.5×; 90 days → 0.25×.
- Fresh verdicts (same day) approach full BM25 weight.

## Write path

```python
from memory import connect, remember_verdict, remember_preference

con = connect(".db/portfolio_memory.db")

# Append a verdict after each stock analysis
remember_verdict(
    con,
    desk="stocks",
    ticker="COIN",
    verdict="HOLD",
    body="COIN stocks HOLD — crypto bullish, above 200d, entry 230-245; conviction 3/5",
    meta={"entry_low": 230, "entry_high": 245, "stop": 205, "conviction": 3, "theme": "FINTECH"},
    run_id="2026-06-24",
)

# Write a durable preference
remember_preference(con, text="crypto bullish", desk=None, scope="COIN,HOOD,CRCL")
```

## Read path

```python
from memory import connect, recall, load_preferences, format_context

con = connect(".db/portfolio_memory.db")

# BM25 × decay recall for a ticker or theme query
memories = recall(con, query="COIN crypto", desk="stocks", k=8, half_life_days=45.0)

# Always-injected preferences (not BM25-gated)
prefs = load_preferences(con, desk="stocks")

# Format into a <prior_context> block for seat injection
context = format_context(prefs, memories)
```

Exact SQL executed by `recall()`:

```sql
SELECT
    m.id, m.kind, m.desk, m.ticker, m.verdict, m.body, m.meta, m.run_id, m.created_at,
    (-bm25(memory_fts, 10.0, 1.0)) * decay(m.created_at, 45.0) AS score
FROM memory_fts
JOIN memory m ON memory_fts.rowid = m.id
WHERE memory_fts MATCH '"coin" OR "crypto"'   -- sanitized from query
  AND m.desk = 'stocks'
ORDER BY score DESC
LIMIT 8;
```

FTS5 MATCH queries are sanitized: `re.findall(r"[a-z0-9$]+", query.lower())` → each token wrapped in
double quotes → joined with ` OR `. Wrapped in `try/except sqlite3.OperationalError` — degrades
gracefully to recency-only fallback if the FTS table is empty.

## CLI usage

```bash
S="python3 .agents/skills/portfolio-memory/memory.py --db .db/portfolio_memory.db"

# Recall prior verdicts for COIN
$S recall --q "COIN" --desk stocks --k 8

# Write a verdict
$S remember \
  --desk stocks \
  --ticker COIN \
  --verdict HOLD \
  --body "COIN stocks HOLD — crypto bullish, above 200d, entry 230-245; conviction 3/5" \
  --meta '{"entry_low":230,"entry_high":245,"stop":205,"conviction":3,"theme":"FINTECH"}' \
  --run-id 2026-06-24

# Add a durable preference
$S pref-add --text "crypto bullish" --scope "COIN,HOOD,CRCL"
$S pref-add --text "RSP over VOO for new US equity" --desk stocks

# List preferences
$S pref-list --desk stocks

# Row counts by desk / kind
$S stats
```

All output is valid JSON — easy for agents to parse.

## inject_context.py helper

`scripts/inject_context.py` is the one-liner the PM skills call at the start of every run:

```bash
python3 .agents/skills/portfolio-memory/scripts/inject_context.py \
  --db .db/portfolio_memory.db \
  --desk stocks \
  --tickers AVGO MRVL COIN PYPL
```

Prints a `<prior_context>` block ready to inject into every seat prompt. Deduplicates across
tickers (same row can rank for multiple symbols) and also recalls a desk-level query for
cross-ticker themes.

## Integration with portfolio managers

### stocks-portfolio-manager

**Step -1 (before seeding todos):** call `inject_context.py` for the run's tickers.

**Step 1g (after persisting to `stock_analysis`):** call `memory.py remember` with the verdict.

### crypto-portfolio-manager

**Step -1 (before seeding todos):** call `inject_context.py` for the run's tokens.

**Step 1g (after persisting to `token_analysis`):** call `memory.py remember` with the verdict.

See the integration hooks appended to each PM's SKILL.md for the exact commands.

## Worked example (self-test — run to verify BM25 × decay)

```bash
DB=.db/pm_test.db
S="python3 .agents/skills/portfolio-memory/memory.py --db $DB"

# Seed 3 verdicts with different ages
$S remember --desk stocks --ticker COIN --verdict HOLD \
  --body "COIN stocks HOLD — crypto bullish, above 200d, entry 230-245; conviction 3/5" \
  --meta '{"conviction":3}' --run-id 2026-06-24

$S remember --desk stocks --ticker COIN --verdict WATCH \
  --body "COIN stocks WATCH — below 200d, wait for reclaim; no trigger yet" \
  --meta '{"conviction":2}' --run-id 2026-06-17

$S remember --desk stocks --ticker PYPL --verdict EXIT \
  --body "PYPL stocks EXIT — value trap confirmed; revenue decel + margin compression" \
  --meta '{"conviction":5}' --run-id 2026-06-24

# Recall: COIN should rank above PYPL (ticker match 10×); most recent COIN first (decay)
$S recall --q "COIN" --desk stocks --k 8
```

Expected: COIN HOLD (2026-06-24) ranks #1, COIN WATCH (2026-06-17) ranks #2 with lower score
(older → lower decay), PYPL EXIT may appear if body mentions related terms but will rank lower
(no ticker match).

Verify:
- Row 1: `ticker=COIN`, `verdict=HOLD`, score highest
- Row 2: `ticker=COIN`, `verdict=WATCH`, score < row 1 (same BM25 bucket × lower decay)
- Preferences always injected regardless of BM25 match

> Educational, not advice. Memory is context + disconfirmation, never a trigger.
