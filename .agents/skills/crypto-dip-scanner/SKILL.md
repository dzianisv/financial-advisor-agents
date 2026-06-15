---
name: crypto-dip-scanner
description: Daily crypto dip scanner — checks BTC/ETH/SOL/BNB/AVAX for % below 52-week high, cross-referenced with Fear & Greed index and BTC funding rates. Fires immediate alert when extreme fear (F&G < 25) coincides with a major dip (>= -30% from 52w high). Use when asked "is crypto cheap", "BTC dip opportunity", "should I buy the crypto dip", "crypto fear and greed", "when to buy crypto", or on the daily proactive schedule.
license: MIT
compatibility: opencode
metadata:
  audience: crypto-investors
  domain: crypto-dip-detection
  role: crypto-opportunity-scanner
---

# Crypto Dip Scanner

Monitors BTC, ETH, SOL, BNB, AVAX daily for dip opportunities. The goal: never miss a **BTC at $61k** (April 2025) because you weren't watching. This scanner runs before you wake up.

## Why this matters

BTC dropped -43% from its ATH to $61k in Spring 2025. Fear & Greed was sub-20 (extreme fear). Funding rates were negative (shorts dominant). Every historical metric screamed "accumulation zone." No proactive alert existed. This skill fixes that.

## Hard rule

**RECOMMEND ONLY.** No trades. Educational analysis, not advice.

## Two execution paths (pick by backend)

**A. Local backend (claude-code / hermes — Python + yfinance present):** fast path.
```bash
python3 .agents/skills/crypto-dip-scanner/crypto_dip_scanner.py --threshold 20
```

**B. openclaw pod (NO Python — node+curl only): use `web_fetch`, one call at a time.** Do NOT call the
`.py`; it will fail (`python3: not found`). Fetch sequentially (parallel → 429):
```
1. F&G:   web_fetch https://api.alternative.me/fng/?limit=1   → data[0].value (int), value_classification
2. BTC:   web_fetch https://query2.finance.yahoo.com/v8/finance/chart/BTC-USD?range=1y&interval=1d
            → q=result[0].indicators.quote[0] ; current=last(q.close) ; high_52w=max(q.high)
            ; sma200=mean(last 200 closes, else null) ; pct_from_high=(current-high_52w)/high_52w*100
3. ETH:   …/chart/ETH-USD?range=1y&interval=1d     (repeat parse)
4. SOL:   …/chart/SOL-USD?range=1y&interval=1d
5. BNB:   …/chart/BNB-USD?range=1y&interval=1d
6. AVAX:  …/chart/AVAX-USD?range=1y&interval=1d
7. LINK:  …/chart/LINK-USD?range=1y&interval=1d
```
Funding (`fapi.binance.com`) is geo-blocked from the pod — skip it, it's bonus only.
If a chart fetch 429s: retry once, then mark that coin `[UNAVAILABLE]` and continue. Never fabricate.

Output fields per coin: `pct_from_high`, `current_usd`, `high_52w_usd`, `sma200_usd`, `pct_vs_200d`, `conviction`. (`high_52w` = trailing-1y intraday high, not all-time; `sma200_usd` null if <200d history.)

Also outputs:
- **Fear & Greed index** (0–100): < 25 = Extreme Fear = historically good entry
- **BTC funding rate**: negative = shorts dominant = squeeze setup

Conviction tiers:
- `HIGH`: >= -40% from 52w high
- `MEDIUM`: -30% to -40%
- `WATCH`: -20% to -30%

## Alert logic

**PRIMARY trigger = IMMEDIATE DM (don't wait for weekly brief).** Fire when BOTH hold:
1. Any coin is >= -30% from 52w high, AND
2. Fear & Greed < 25 (extreme fear)

These two are the reliable, always-available signals. **Funding rate is a BONUS confirmation, not a requirement** — `fapi.binance.com` is geo-blocked from many networks (incl. the openclaw pod), so the script prints no funding line when it can't fetch. NEVER suppress a valid dip+fear alert just because funding is missing. If funding IS available and < 0% (shorts dominant), add it to the alert as extra weight.

Fire:
```
🚨 CRYPTO DIP ALERT — [COIN] [pct]% below 52w high
  52w high: $[high_52w]  Now: $[price]  200dMA: $[sma]
  Fear & Greed: [n]/100 ([label])  ← EXTREME FEAR
  BTC Funding: [rate]% [or "unavailable — Binance geo-blocked"]
  Historical context: BTC/ETH extreme-fear zones (F&G<25) have historically been net-positive
    entry points over 6-12m horizons. NOT a guarantee — regime can stay fearful for weeks.
  → Run /multi-lens-quorum on [COIN]? Reply YES.
```

**Single signal (dip without extreme fear, OR fear without a -30% dip):** add to weekly brief as WATCH — do not fire an immediate DM.

## Macro cross-check

After firing alert: check TradFi regime (`regime_monitor.py`). If TradFi is also RISK_OFF (equity sell-off), crypto dip may be correlated → note this. If TradFi recovers first, crypto often follows → heightens urgency.

## Success criteria

- [ ] Script ran, output includes F&G + funding rate.
- [ ] Three-signal convergence: immediate DM sent.
- [ ] Single/double signal: added to weekly pool.
- [ ] No fabricated prices — all from yfinance.

## Schedule

Run **daily 07:50 UTC** — 5 minutes after dip-screener, before US pre-market.
