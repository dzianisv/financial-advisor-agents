---
name: crypto-onchain-data
description: Data-only gather seat — pull BTC (or an alt's) market structure + on-chain valuation for a research brief. Use when a workflow/agent needs spot, 52w high, 200d & 200-week MA, MVRV-Z, NUPL, realized price, Puell, hashrate as raw inputs (no buy/sell opinion). Triggers — "pull on-chain data", "BTC valuation metrics", "MVRV/NUPL/Puell", crypto-panel Gather phase.
license: MIT
compatibility: opencode
metadata:
  role: data-source-reference
  domain: crypto-market-data
---

# Crypto on-chain + price-structure data (gather seat)

DATA ONLY. No buy/sell call, no thesis. Return numbers with `as-of` + `source`; mark `[UNAVAILABLE]` when gated — **never fabricate**.

## Pull these (for the asset in the question; default BTC)

**Market structure**
- Spot price; 52-week high + % from it; 200-day MA + % vs it; **200-week MA** + % vs it (the cycle-bottom pivot).

**On-chain valuation** (the decision-relevant core — fetch via the sources below)
- **MVRV-Z score** (tops >7, accumulation <1)
- **NUPL** (euphoria >0.75, capitulation <0)
- **Realized price** (aggregate cost basis)
- **Puell multiple** (miner stress / capitulation)
- **Hashrate trend** (rising/falling 30d)

**Spot-BTC-ETF net flows — REQUIRED, never silently omit** (the dominant marginal-demand read for "buy BTC today")
- Aggregate net daily flow (IBIT/FBTC/etc., creations − redemptions) + 5-day direction (inflow/outflow).
- Try via WebFetch (not urllib — these block bots): `farside.co.uk/btc/`, `sosovalue.com` ETF dashboard, `coinglass.com/bitcoin-etf`. If ALL are blocked, emit the metric anyway with `value: "[UNAVAILABLE]"` + which sources you tried. **Do NOT drop the line** — its absence must be loud, not silent.

## Sources (preferred = deterministic; the JS-gated charts are flaky run-to-run)
- **On-chain valuation core → run the script** (reliable JSON API, no key, no JS-gating):
  ```bash
  python3 .agents/skills/crypto-onchain-data/onchain_fetch.py   # MVRV-Z, NUPL, Puell, realized price + as-of
  ```
  This replaces the flaky `checkonchain`/`lookintobitcoin` WebFetch path that returned `[UNAVAILABLE]` (403/428)
  intermittently. If the script reports a metric in its `unavailable` list, THEN best-effort WebFetch
  `newhedge.io/bitcoin/*` as fallback; if still gated, mark that metric `[UNAVAILABLE]` — never infer it.
- **Price + 200d/200-week MA:** `yfinance` (`BTC-USD`, `range=5y` for the 200-week) or Yahoo chart API.
- If MVRV-Z and price disagree wildly, re-pull; report both, don't average.

## Output contract (one record per metric)
`{metric, value, asof, source}` plus a one-line `summary` naming the valuation zone (cheap / fair / expensive) **as a factual read of the metrics**, not advice. List anything `[UNAVAILABLE]` explicitly.

## Done when
Every metric above is either a sourced number with as-of, or an explicit `[UNAVAILABLE]`. No metric silently omitted.
