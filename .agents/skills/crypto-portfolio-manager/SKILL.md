---
name: crypto-portfolio-manager
description: "Portfolio manager for the crypto book — runs 4x/day, pulls live analysis for every token in the universe (BTC/ETH/SOL/UNI/HYPE/AAVE/LINK + expandable), applies full-desk decision rules (quorum posture + dip-tranche ladder + regime + risk veto), generates BUY/SELL/HOLD signals, and fires TradingView alert webhooks (brokerage-agnostic) to route execution to whatever broker the user has connected. Use when asked to 'run the crypto portfolio check', 'what should I do with my positions', 'run the full portfolio scan', or when cron fires. Educational, not advice."
license: MIT
compatibility: opencode
metadata:
  audience: crypto-allocators
  domain: crypto-portfolio-management
  role: portfolio-manager-and-signal-router
  source: "crypto-desk + analysis-comprehensive-crypto + TradingView MCP alerts (2026-06)"
---

# Crypto Portfolio Manager

Monitors the entire crypto book on a 4x/day cadence, runs parallel analysis across every token in
the universe, applies full-desk decision rules (regime + dip-tranche + quorum posture + risk veto),
and generates BUY/SELL/HOLD signals. Execution is brokerage-agnostic: signals are routed via
TradingView `alert_create` with a JSON payload; the user's webhook closes the loop to their broker
(IBKR, Binance, Coinbase, etc.). When `WEBHOOK_URL` is configured in TradingView, alerts fire
automatically — otherwise the skill prints the signal table and the human places orders. Runs
`0 0,6,12,18 * * *`; scheduling is the user's responsibility.

> **Educational analysis, not financial advice.** Notification-first by default: you recommend;
> the human (or webhook) disposes. No leverage. Ever.

---

## Execution architecture

```
skill
  └─► analysis-comprehensive-crypto (one subagent per token, all parallel)
        └─► returns compact quorum verdict per token
  └─► decision engine (regime + dip-tranche + quorum + risk veto)
        └─► BUY / SELL / HOLD per token
  └─► TradingView alert_create (JSON payload per BUY/SELL signal)
        └─► user's TradingView webhook → broker API
  └─► SIGNALS-{date}.jsonl (all signals logged)
  └─► POSITIONS.json updated_at refreshed
```

TradingView MCP provides `tradingview-alert_create(condition, price, message)`.
The `message` field carries the full JSON order payload.
The user connects their broker to TradingView (Settings → Notifications → Webhook URL) and
implements a thin handler that parses `action`, `symbol`, `size_usd` and calls the broker API.
This skill never calls a broker API directly.

---

## Portfolio state

Positions live in `crypto/POSITIONS.json`. Schema:

```json
{
  "updated_at": "2026-06-22T12:00:00Z",
  "portfolio_usd": 100000,
  "dry_powder_pct": 30,
  "positions": [
    {"symbol": "BTC", "size_usd": 20000, "entry_price": 60000, "target_pct": 25},
    {"symbol": "ETH", "size_usd": 8000,  "entry_price": 2200,  "target_pct": 10},
    {"symbol": "SOL", "size_usd": 0,     "entry_price": 0,     "target_pct": 5},
    {"symbol": "UNI", "size_usd": 0,     "entry_price": 0,     "target_pct": 3},
    {"symbol": "HYPE","size_usd": 0,     "entry_price": 0,     "target_pct": 3},
    {"symbol": "AAVE","size_usd": 0,     "entry_price": 0,     "target_pct": 3},
    {"symbol": "LINK","size_usd": 0,     "entry_price": 0,     "target_pct": 3}
  ],
  "token_universe": ["BTC", "ETH", "SOL", "UNI", "HYPE", "AAVE", "LINK"]
}
```

If the file does not exist, create it with the schema above (all `size_usd` and `entry_price` set to
0), then **stop and prompt the user** to fill in their actual positions before continuing.

---

## Step 1 — Load positions + config

1. Read `crypto/POSITIONS.json`.
2. Validate:
   - `portfolio_usd > 0` — abort if zero; prompt user to set it.
   - `token_universe` non-empty — abort if missing.
   - `dry_powder_pct` between 0–100.
3. Compute `dry_powder_usd = portfolio_usd * dry_powder_pct / 100`.
4. For each token in `token_universe`, find its entry in `positions` (or treat as unpositioned:
   `size_usd=0, entry_price=0`).

---

## Step 2 — Run analysis for every token in parallel

Spawn one `analysis-comprehensive-crypto` subagent per token **simultaneously** (background mode).
Do NOT await one before launching the next.

**Subagent prompt template (substitute {SYMBOL} and {TVSYMBOL}):**

```
Load skill: analysis-comprehensive-crypto

Analyze {TVSYMBOL} (e.g. BINANCE:BTCUSDT).

Run Steps 1–3 of analysis-comprehensive-crypto:
  - Pull TradingView MCP data (OHLCV daily + weekly + 4H, RSI, MACD, BB, EMAs).
  - Spawn all five analysis seats (on-chain, sentiment, macro, orderflow, narrative) in parallel.
  - Synthesize the quorum.

Return ONLY this compact verdict block (JSON, no extra prose):
{
  "symbol": "BTC",
  "quorum_verdict": "BULLISH | SPLIT | BEARISH | UNCERTAIN",
  "dominant_zone":  "DEEP_VALUE | FAIR_VALUE | ELEVATED | EXTREME | UNKNOWN",
  "posture":        "BULLISH | NEUTRAL | BEARISH",
  "seats_bull":     3,
  "seats_bear":     2,
  "top_bull":       "one-line strongest bull signal",
  "top_bear":       "one-line strongest bear signal",
  "key_support":    95000,
  "key_resistance": 108000,
  "confidence":     "HIGH | MED | LOW",
  "data_gap":       false,
  "data_gap_reason": null
}
```

**TradingView symbol mapping** (append USDT, use BINANCE prefix):

| Universe token | TradingView symbol |
|---|---|
| BTC  | `BINANCE:BTCUSDT`  |
| ETH  | `BINANCE:ETHUSDT`  |
| SOL  | `BINANCE:SOLUSDT`  |
| UNI  | `BINANCE:UNIUSDT`  |
| HYPE | `BINANCE:HYPEUSDT` |
| AAVE | `BINANCE:AAVEUSDT` |
| LINK | `BINANCE:LINKUSDT` |

For tokens not on Binance, substitute the appropriate exchange prefix (e.g. `COINBASE:BTCUSD`).

**Fallback (TradingView unavailable or seat timeout):** use TradingView OHLCV + technical
indicators only (skip the 5-seat panel). Mark `confidence: LOW` and `data_gap: true` with reason.

---

## Step 3 — Decision engine (per token)

Apply these rules **in order**. First rule that matches wins. Log the matched rule as `reason`.

### Hard veto — skip entirely if:
- Token is not in `token_universe`.
- Analysis subagent returned an error → signal `HOLD`, log `"analysis unavailable: {error}"`.
- `quorum_verdict = UNCERTAIN` AND `confidence = LOW` → signal `HOLD`, log `"low confidence uncertain"`.
- Signal would require leverage → **hard veto, HOLD, log `"leverage veto"`.**

### SELL signal — fires if ALL of:
1. `size_usd > 0` (currently have a position).
2. `quorum_verdict = BEARISH` AND `seats_bear >= 4`.
3. Price is **above** `entry_price` (profit exit) OR drawdown from `entry_price` exceeds −35% (stop).
4. `dominant_zone` is `ELEVATED` or `EXTREME`.

Size: full position (`size_usd`). Never partial-sell unless target allocation requires it.

### BUY signal — fires if any of:
| Trigger | Condition | Tranche size |
|---|---|---|
| Strong bullish quorum | `quorum_verdict = BULLISH` AND `seats_bull >= 3` | Full dip-tranche per ladder (see below) |
| Opportunistic split | `quorum_verdict = SPLIT` AND `dominant_zone = DEEP_VALUE` AND `dry_powder_pct > 20` | Half tranche (50% of ladder size) |
| Dip-tranche ladder rung | Drawdown from cycle high hits a tier threshold (C1–C5) | Per-tier deploy % of `dry_powder_usd` |

Also require: position `size_usd` is below `target_pct * portfolio_usd` (room to add).

### HOLD — all other cases.

---

## Dip-tranche ladder

Drawdown measured from the token's cycle high (52-week high as proxy). Deploy from `dry_powder_usd`.
Trigger on **weekly closes**, not intraday wicks.

| Tier | Drawdown from cycle high | Deploy (of dry powder) | Notes |
|---|---|---|---|
| C1 | −20% | 15–20% | First nibble |
| C2 | −35% | 25–30% | Core tranche |
| C3 | −50% | 30–35% | Aggressive add |
| C4 | −65% | ~0% (hold ~25% reserve) | Preserve reserve |
| C5 | −75%+ | deepest reserve only | BTC/ETH only |

At C4/C5: deploy into **BTC and ETH only** — not alts. In a real crash, concentrate in what recovers.

---

## Size cap rules (hard — cannot be overridden)

| Token | Max % of portfolio |
|---|---|
| BTC | 40% |
| ETH | 40% |
| SOL | 10% |
| UNI / HYPE / AAVE / LINK (each) | 5% |

- **No leverage. Ever. Hard-coded veto.**
- **Never deploy >25% of dry powder in a single run** (across all tokens combined).
- Compute `run_deploy_budget = dry_powder_usd * 0.25` before sizing any BUY.
- Size each BUY: `min(tranche_size, remaining_run_deploy_budget, cap_headroom)`.
- If a BUY would breach any cap, reduce size to the cap or skip (log reason).

---

## Step 4 — Fire TradingView alerts

For each BUY or SELL signal:

1. Set the symbol on the chart:
   ```
   tradingview-chart_set_symbol  symbol="BINANCE:{SYMBOL}USDT"
   ```

2. Fire the alert:
   ```
   tradingview-alert_create
     condition: "crossing"
     price:     {key_support for BUY | key_resistance for SELL}
     message:   {JSON payload — see below}
   ```

**Alert message JSON payload:**
```json
{
  "action":              "buy",
  "symbol":             "BTCUSDT",
  "size_usd":           5000,
  "size_pct_portfolio": 5.0,
  "reason":             "C2 dip tranche — drawdown -38%, quorum BULLISH 4/5",
  "quorum":             "BULLISH",
  "zone":               "FAIR_VALUE",
  "confidence":         "MED",
  "run_id":             "2026-06-22T12:00:00Z",
  "no_leverage":        true
}
```

For **HOLD** signals: no alert fired. Log only (see Step 5).

**All alerts in a single run share the same `run_id`** (ISO timestamp of run start).

---

## Step 5 — Write signal log

Append one JSON line per token to `crypto/signals/SIGNALS-{YYYY-MM-DD}.jsonl`.
Create the directory if it doesn't exist. Never overwrite existing lines — append only.

**JSONL line schema:**
```json
{"ts": "2026-06-22T12:01:34Z", "symbol": "BTC", "action": "HOLD", "size_usd": 0, "reason": "quorum SPLIT, zone FAIR_VALUE, insufficient conviction", "quorum": "SPLIT", "zone": "FAIR_VALUE", "confidence": "MED", "alert_fired": false, "run_id": "2026-06-22T12:00:00Z"}
{"ts": "2026-06-22T12:01:38Z", "symbol": "SOL", "action": "SELL", "size_usd": 3200, "reason": "BEARISH 4/5 seats, zone ELEVATED, drawdown -12% (profit exit)", "quorum": "BEARISH", "zone": "ELEVATED", "confidence": "HIGH", "alert_fired": true, "run_id": "2026-06-22T12:00:00Z"}
```

After writing all signal lines, update `crypto/POSITIONS.json`:
- Set `updated_at` to the run timestamp.
- For executed BUY signals: increase `size_usd` by `size_usd` of the signal (optimistic — actual fill confirmed by webhook).
- For executed SELL signals: set `size_usd` to 0 (full position cleared).
- Recalculate `dry_powder_pct` accordingly.

---

## Routing table

| Question | Action |
|---|---|
| "Run the portfolio check" | Full Steps 1–5 |
| "What does [TOKEN] look like?" | Single token: spawn `analysis-comprehensive-crypto` only, no sizing |
| "Add [TOKEN] to universe" | Edit `crypto/POSITIONS.json` → append to `token_universe` and add zero entry to `positions` |
| "What signals fired today?" | Read `crypto/signals/SIGNALS-{today}.jsonl` and print summary table |
| "Set up webhook execution" | See Webhook wiring section below |
| Buy/sell sizing override | Route to [[crypto-desk]] for manual override |
| Backtest a strategy | Route to [[strategy-discovery-backtest]] |
| Coinbase execution wiring | Route to [[coinbase-cdp-connector]] |

---

## Webhook wiring (brokerage-agnostic)

To enable auto-execution via TradingView alerts:

1. In TradingView → Settings → Notifications → add your webhook URL (e.g. `https://your-server.com/hook`).
2. The alert `message` JSON (from Step 4) is what TradingView POSTs to your webhook as the request body.
3. Your webhook handler parses `action`, `symbol`, `size_usd`, `no_leverage` and routes to your broker's API.
4. For Coinbase: use [[coinbase-cdp-connector]] as the webhook handler adapter.
5. For any other broker: implement a thin adapter that reads the JSON and calls the broker's order API.
   The minimum required fields are `action` (`"buy"` | `"sell"`), `symbol`, and `size_usd`.

The skill fires the alert; the webhook closes the loop. This is intentional — it keeps the skill
brokerage-agnostic and puts execution control with the user.

**Cron schedule** (scheduling is the user's responsibility):
```
0 0,6,12,18 * * *
```

---

## Hard rules

- **No leverage — ever.** Veto any signal that implies borrowing, margin, or futures.
- **Never deploy >25% of dry powder in a single run** (across all tokens combined).
- **BUY requires ≥3/5 seats BULLISH.** No conviction → HOLD. Do not chase.
- **SELL requires ≥4/5 seats BEARISH** + position in profit OR stop hit. No panic-selling on 3/5.
- **Mark data gaps loudly.** If a token's analysis fails or returns `data_gap: true`, signal HOLD and
  log the reason. Never silently skip.
- **Update `POSITIONS.json` after every run** — `updated_at` at minimum, positions if signals fired.
- **All signals logged** to `SIGNALS-{date}.jsonl` regardless of action (BUY, SELL, or HOLD).
- **TradingView MCP requires Chrome CDP on port 9222.** If connection fails, see
  `analysis-comprehensive-crypto` for the launch command.
- Educational analysis, not financial advice. You recommend; the human (or webhook) disposes.

---

## Done when

1. All tokens in `token_universe` have been analyzed (or marked `UNAVAILABLE` with reason).
2. Decision engine applied to every token — each has a logged BUY/SELL/HOLD verdict.
3. TradingView alerts fired for all BUY and SELL signals (`alert_fired: true` in log).
4. `crypto/signals/SIGNALS-{YYYY-MM-DD}.jsonl` updated with one line per token.
5. `crypto/POSITIONS.json` `updated_at` timestamp refreshed.
6. Summary table printed to stdout:

```
=== PORTFOLIO RUN — 2026-06-22T12:00:00Z ===

Token  | Quorum  | Zone       | Conf | Signal | Size     | Alert
-------|---------|------------|------|--------|----------|----------
BTC    | BEARISH | FAIR_VALUE | MED  | HOLD   | —        | —
ETH    | SPLIT   | FAIR_VALUE | MED  | HOLD   | —        | —
SOL    | BEARISH | ELEVATED   | HIGH | SELL   | $3,200   | ✓ fired
UNI    | BULLISH | DEEP_VALUE | MED  | BUY    | $1,500   | ✓ fired
HYPE   | BEARISH | ELEVATED   | LOW  | HOLD   | —        | — (low conf)
AAVE   | BULLISH | FAIR_VALUE | MED  | BUY    | $1,000   | ✓ fired
LINK   | UNCERTAIN| UNKNOWN   | LOW  | HOLD   | —        | — (data gap)

Dry powder deployed this run: $5,700 / $7,500 budget (76%)
POSITIONS.json updated_at: 2026-06-22T12:01:55Z
Signal log: crypto/signals/SIGNALS-2026-06-22.jsonl
```
