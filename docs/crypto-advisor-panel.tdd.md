# TDD — Crypto-Advisor Panel (School-Based Quorum)

Implements the redesign specified in `docs/crypto-advisor-panel.prd.md`.
Educational only. Not financial advice. No leverage. Ever.

---

## Decisions (resolved from PRD open questions)

| Question | Decision |
|---|---|
| State / storage | **Stateless v1** — fresh data package each run; no rolling thesis |
| Seat prompt ownership | **Shared `analysis-{school}` skills** — reusable by hedge-fund-committee and any other panel skill |
| Openclaw plugin granularity | **One `crypto-advisor` plugin** that internally spawns seats; per-seat model override via seat config inside single plugin |

---

## 1. Data Package Schema

Each run builds one `DataPackage` per token. No interpretation — raw facts only.

```json
{
  "token": "string",
  "price_usd": "number",
  "rsi_14": "number (0–100)",
  "ema20": "number | null",
  "sma50": "number | null",
  "sma200": "number | null",
  "wma200": "number | null",
  "weekly_closes": "integer",
  "zone": "DEEP_VALUE | FAIR_VALUE | ELEVATED | EXTREME | UNKNOWN",
  "pct_below_ath": "number",
  "pct_below_200wma": "number | null",
  "death_cross": "boolean",
  "defi_llama": {
    "protocol_revenue_30d": "number | null",
    "tvl": "number | null",
    "fees_30d": "number | null",
    "fee_distribution": "string | null"
  },
  "fg_index": "integer (0–100)",
  "fg_regime": "EXTREME_FEAR | FEAR | NEUTRAL | GREED | EXTREME_GREED",
  "news_headlines": [
    { "title": "string", "source": "string", "url": "string" }
  ],
  "market_context": "string"
}
```

### Field rules

| Field | Rule |
|---|---|
| `zone` | Computed from `pct_below_ath` + `pct_below_200wma`; descriptive only — no signal logic here |
| `weekly_closes` | Count of actual weekly OHLCV bars available; governs `wma200` availability |
| `wma200` | `null` when `weekly_closes < 200` |
| `pct_below_200wma` | `null` when `wma200` is null |
| `death_cross` | `true` when `sma50 < sma200`; `false` otherwise; `null` when either MA is null |
| `news_headlines` | Max 3 items; empty array if none fetched |
| `market_context` | One-line string: ETF flows, macro events, or dominant narrative |

### Zone computation

```
zone =
  UNKNOWN       if wma200 is null
  DEEP_VALUE    if pct_below_ath >= 50 AND pct_below_200wma >= 30
  FAIR_VALUE    if pct_below_ath >= 20
  ELEVATED      if pct_below_ath >= 0 (i.e. price below ATH but < 20%)
  EXTREME       if pct_below_ath < 0  (price at or above ATH)
```

### F&G regime mapping

| fg_index | fg_regime |
|---|---|
| 0–24 | EXTREME_FEAR |
| 25–49 | FEAR |
| 50–74 | NEUTRAL |
| 75–89 | GREED |
| 90–100 | EXTREME_GREED |

---

## 2. Seat Contract

### Input

Each seat receives the full `DataPackage` (defined above). Seats are stateless — no prior run state is passed.

### Output

```json
{
  "vote": "BULLISH | NEUTRAL | BEARISH",
  "reason": "string"
}
```

**Reason format rule:** The reason MUST cite the school framework by name, e.g.:

- `"Graham: price at 40% discount to protocol TVL — margin of safety present"`
- `"Marks: Extreme Fear regime — Templeton entry condition met"`
- `"Druckenmiller: death cross active, RSI 28 — don't fight the tape"`

The orchestrator does NOT interpret or summarize reasons. It passes them verbatim to output.

---

## 3. Seat Skill Specs

### Seat 1 — `analysis-value`

| Attribute | Value |
|---|---|
| Skill path | `.agents/skills/analysis-value/SKILL.md` |
| School anchoring | Benjamin Graham (*The Intelligent Investor* ch.20 — Margin of Safety); Seth Klarman (*Margin of Safety*) |
| Primary signals | `zone`, `pct_below_ath`, `pct_below_200wma`, `defi_llama.protocol_revenue_30d` |
| BULLISH trigger | `zone` is `DEEP_VALUE` or (`FAIR_VALUE` AND `protocol_revenue_30d > 0`) — margin of safety present |
| BEARISH trigger | `zone` is `ELEVATED` or `EXTREME` |
| NEUTRAL trigger | `FAIR_VALUE` with no revenue data, or signals conflict |

### Seat 2 — `analysis-quality`

| Attribute | Value |
|---|---|
| Skill path | `.agents/skills/analysis-quality/SKILL.md` |
| School anchoring | Phil Fisher (*Common Stocks and Uncommon Profits*); Peter Lynch (*One Up on Wall Street* ch.9) |
| Primary signals | `defi_llama.protocol_revenue_30d`, `defi_llama.tvl`, `defi_llama.fees_30d`, `defi_llama.fee_distribution` |
| BULLISH trigger | Strong and growing revenue + fee buyback or burn mechanism confirmed in `fee_distribution` |
| BEARISH trigger | No revenue model (`protocol_revenue_30d` null or zero) or declining `tvl` |
| NEUTRAL trigger | Revenue exists but no fee accrual mechanism, or mixed signals |

### Seat 3 — `analysis-cycle`

| Attribute | Value |
|---|---|
| Skill path | `.agents/skills/analysis-cycle/SKILL.md` |
| School anchoring | Howard Marks (*The Most Important Thing* ch.5–7); John Templeton (maximum pessimism principle) |
| Primary signals | `fg_index`, `fg_regime`, `zone` |
| BULLISH trigger | `fg_regime` is `EXTREME_FEAR` AND `zone` is not `EXTREME` |
| BEARISH trigger | `fg_regime` is `EXTREME_GREED` OR `zone` is `EXTREME` |
| NEUTRAL trigger | `fg_regime` is `NEUTRAL`, `GREED`, or `FEAR` without extremes |

### Seat 4 — `analysis-trend`

| Attribute | Value |
|---|---|
| Skill path | `.agents/skills/analysis-trend/SKILL.md` |
| School anchoring | Stanley Druckenmiller (trend-following framing from Soros *Alchemy of Finance*); Robert Carver (*Systematic Trading*) |
| Primary signals | `ema20`, `sma50`, `sma200`, `death_cross`, `rsi_14`, `weekly_closes` |
| BULLISH trigger | Golden cross (`sma50 > sma200`, i.e. `death_cross = false`) AND `rsi_14` recovering from oversold (< 40 → rising) |
| BEARISH trigger | `death_cross = true` AND `rsi_14 < 40` |
| NEUTRAL trigger | MAs are null (`weekly_closes < 200`), or MA alignment and RSI conflict |

### Seat 5 — `analysis-onchain`

| Attribute | Value |
|---|---|
| Skill path | `.agents/skills/analysis-onchain/SKILL.md` |
| School anchoring | Chris Burniske & Jack Tatar (*Cryptoassets* — value-accrual framework); DeFiLlama methodology |
| Primary signals | `defi_llama.tvl`, `defi_llama.protocol_revenue_30d`, `defi_llama.fee_distribution` |
| BULLISH trigger | Value accrual verified: `fee_distribution` confirms buyback or burn mechanism AND `tvl` growing AND `protocol_revenue_30d > 0` |
| BEARISH trigger | No value accrual mechanism (`fee_distribution` null or "treasury only") |
| NEUTRAL trigger | Revenue exists but accrual mechanism unconfirmed, or data partially missing |

---

## 4. Signal Table

```
seats_bull = count of BULLISH votes from 5 seats
seats_bear = count of BEARISH votes from 5 seats

if seats_bear >= 4:                                    → SELL
elif seats_bull >= 4 and weekly_closes >= 200:         → BUY
elif seats_bull >= 3 and weekly_closes >= 200:         → BUY(small)
elif seats_bull >= 3 and weekly_closes < 200:          → BUY(small)  [note: history<200w, size down]
else:                                                  → HOLD
```

**No zone conditions.** Zone is seat input only — it has no role in this table.

Priority: `SELL` check runs first (seats_bear ≥ 4 overrides any bull count).

---

## 5. Governor Cap

Runs after signal table produces `raw_signal` for each token.

### Cap table

| fg_regime | Max simultaneous (BUY + BUY(small)) |
|---|---|
| EXTREME_FEAR | 3 |
| FEAR | 5 |
| NEUTRAL, GREED, EXTREME_GREED | ∞ (no cap) |

### Ranking and downgrade algorithm

```
1. Collect all tokens where raw_signal ∈ {BUY, BUY(small)}
2. Sort descending by: seats_bull DESC, then price_usd DESC (tiebreak)
3. Take top MAX_ACTIVE → status = ACTIVE
4. Remaining → status = WATCH (downgraded from BUY/BUY(small))
5. Tokens with HOLD or SELL are unaffected
```

### Output contract

For each token, governor produces:
- `final_signal`: `BUY | BUY(small) | HOLD | SELL`
- `governor_status`: `ACTIVE | WATCH | N/A`

`N/A` for HOLD and SELL tokens. `ACTIVE`/`WATCH` only applies to BUY and BUY(small).

---

## 6. Orchestrator Flow

```
INPUT: token_list[]

STEP 1 — Fetch data
  for each token in token_list (parallel):
    fetch price, RSI, EMA20, SMA50, SMA200, WMA200, weekly_closes
    fetch pct_below_ath, compute zone
    fetch defi_llama { protocol_revenue_30d, tvl, fees_30d, fee_distribution }
    fetch fg_index → compute fg_regime
    fetch top-3 news_headlines
    fetch market_context (one-line global summary)
    → build data_package[token]

STEP 2 — Seat voting (per token, all tokens in parallel)
  for each token:
    spawn 5 seat agents in parallel: [value, quality, cycle, trend, onchain]
    each seat receives: data_package[token]
    each seat returns: { vote, reason }
    collect votes[] for token

STEP 3 — Signal table
  for each token:
    seats_bull = count(v.vote == "BULLISH" for v in votes)
    seats_bear = count(v.vote == "BEARISH" for v in votes)
    raw_signal = apply_signal_table(seats_bull, seats_bear, weekly_closes)

STEP 4 — Governor cap
  fg_regime = data_package[token_list[0]].fg_regime  # same for all tokens in a run
  MAX_ACTIVE = governor_cap(fg_regime)
  candidates = tokens where raw_signal in {BUY, BUY(small)}
  sorted_candidates = sort by seats_bull DESC, price_usd DESC
  for i, token in enumerate(sorted_candidates):
    if i < MAX_ACTIVE: final_signal = raw_signal, governor_status = ACTIVE
    else:              final_signal = raw_signal, governor_status = WATCH

STEP 5 — Output
  produce formatted report (see §9)
```

---

## 7. Runtime Adapters

Both adapters receive the same `data_package` and return the same `{ seat, vote, reason }[]` array. Core signal logic runs identically after.

### Claude Code adapter

```python
# Pseudo-code

seats = ["value", "quality", "cycle", "trend", "onchain"]

MODEL_MAP = {
    "trend":   "claude-haiku-4-5-20251001",   # mechanical/fast
    "value":   "claude-sonnet-4-6",
    "quality": "claude-sonnet-4-6",
    "cycle":   "claude-sonnet-4-6",
    "onchain": "claude-sonnet-4-6",
}

def run_seat(seat_name, data_package):
    skill_path = f"~/.agents/skills/analysis-{seat_name}/SKILL.md"
    system_prompt = read(skill_path)
    result = Agent(
        model=MODEL_MAP[seat_name],
        system=system_prompt,
        prompt=json.dumps(data_package),
    )
    return { "seat": seat_name, **parse_vote(result) }

# All 5 seats for one token spawned in parallel:
votes = parallel_map(run_seat, seats, data_package)
```

### Openclaw adapter

```python
# Pseudo-code

MODEL_MAP = {
    "value":   "gpt-5",          # strong valuation math
    "quality": "claude-sonnet-4-6",
    "cycle":   "gemini-pro",     # macro/news corpus
    "trend":   "claude-haiku",   # fast, deterministic
    "onchain": "claude-sonnet-4-6",
}

def run_seat(seat_name, data_package):
    result = invoke(
        plugin=f"analysis-{seat_name}",
        data=data_package,
        model=MODEL_MAP[seat_name],   # per-seat model override via plugin config
    )
    return { "seat": seat_name, "vote": result.vote, "reason": result.reason }

# Plugin router handles parallel execution:
votes = plugin_parallel_map(run_seat, seats, data_package)
```

### Shared contract

Both adapters return to core:

```json
[
  { "seat": "value",   "vote": "BULLISH | NEUTRAL | BEARISH", "reason": "..." },
  { "seat": "quality", "vote": "...", "reason": "..." },
  { "seat": "cycle",   "vote": "...", "reason": "..." },
  { "seat": "trend",   "vote": "...", "reason": "..." },
  { "seat": "onchain", "vote": "...", "reason": "..." }
]
```

---

## 8. File Layout

```
.agents/skills/
  crypto-advisor/SKILL.md          ← orchestrator — rewrite target
  analysis-value/SKILL.md          ← new (Graham/Klarman)
  analysis-quality/SKILL.md        ← new (Fisher/Lynch)
  analysis-cycle/SKILL.md          ← new (Marks/Templeton)
  analysis-trend/SKILL.md          ← new (Druckenmiller/Carver)
  analysis-onchain/SKILL.md        ← new (Burniske)
```

`analysis-{school}` skills are global — shared across `crypto-advisor`, `hedge-fund-committee`, and any future panel skill. Do not embed them inside `crypto-advisor/`.

---

## 9. Output Format

The orchestrator MUST produce output in this exact format:

```
=== CRYPTO ADVISOR RUN — {DATE} ===
F&G: {fg_index} ({fg_regime})
Governor: max {MAX_ACTIVE} active buys

TOKEN    SEATS    SIGNAL         VALUE  QUALITY  CYCLE  TREND  ONCHAIN
BTC      1B/4N    HOLD           N      N        N      B      N
ETH      3B/2N    BUY(small)     B      N        B      N      B
AERO     5B/0N    BUY(small)✅   B      B        B      B      B
JUP      4B/1N    BUY✅          B      B        B      N      B
HYPE     2B/3N    HOLD           N      N        B      N      B
SOL      1B/2N    HOLD           N      B        N      N      N

ACTIVE (governor picks):
  1. JUP   $0.22 — 4/5 | Value: Graham: 38% below ATH, TVL growing | Quality: ... | ...
  2. AERO  $0.47 — 5/5 | Value: ... | ...
  3. ETH   $2450 — 3/5 | ...

WATCH (downgraded by governor):
  (none at current cap)

HOLD:
  BTC, HYPE, SOL
```

### Column rules

| Column | Value |
|---|---|
| `SEATS` | `{seats_bull}B/{seats_neutral}N` where neutral = 5 - bull - bear; add `/XS` if bears exist |
| `SIGNAL` | Raw signal from §4; `✅` suffix when `governor_status = ACTIVE` |
| Seat columns | `B` = BULLISH, `N` = NEUTRAL, `S` = BEARISH |
| ACTIVE section | One line per token; pipe-separated seat reasons verbatim |
| WATCH section | Token names only (no seat reasons needed) |

---

## 10. Eval Update

### Current rubric dimension to retire

`zone_discipline` — defined as "BUY signals respect zone gates" — is invalid after this redesign because zone gates are removed from the signal table.

### Replacement dimension

**`seat_attribution`** — defined as:

> Each seat's vote output includes a one-line reason that cites the seat's named school or framework. The orchestrator's signal table contains no market opinions — it only counts votes and applies mechanical governor logic.

**Scoring rubric (0–2):**

| Score | Criterion |
|---|---|
| 2 | All 5 seat reasons cite the school by name; orchestrator output contains no opinion language |
| 1 | Majority of seats cite school; or orchestrator includes minor opinion framing |
| 0 | Seat reasons are generic (no school citation); or orchestrator embeds market opinions in signal table |

Update in: `.cache/crypto-advisor/crypto-advisor.eval.csv` (column rename) and the judge prompt in `crypto-advisor` eval harness.
