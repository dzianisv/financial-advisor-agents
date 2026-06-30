# crypto-advisor

Multi-token crypto portfolio analyzer. Runs a **3-layer hedge fund structure** (Research → Panel → Report) per token and outputs BUY / BUY(small) / HOLD / SELL signals with a F&G-governed position cap.

> Educational only. Not financial advice. No leverage. Ever.

## Architecture

```mermaid
flowchart TD
    CIO["🎯 CIO\n11 tokens · one at a time (chart slot)"]

    CIO -->|"token + price_usd"| RESEARCH

    subgraph RESEARCH["① Research Desk — parallel, each analyst owns its data"]
        TA["analyse-technical\n📊 TradingView MCP\nOHLCV · RSI · BB · MACD · MAs"]
        FUND["analyse-onchain\n🌐 MVRV-Z · realized price · NUPL\nPuell · LTH/STH · exchange flows"]
        OC["analyse-defi\n🌐 DeFiLlama\nTVL · fee distribution · accrual"]
        MACRO["analyse-macro\n🌐 GLI · M2 · DXY · ETF flows\nmacro headlines · halving cycle"]
        SM["analyse-smartmoney\n🌐 whale flows · exchange inflows\nOTC · positioning"]
    end

    BRIEF["📄 CIO consolidates\none briefing package per token"]

    TA -->|"technical brief"| BRIEF
    FUND -->|"fundamental brief"| BRIEF
    OC -->|"on-chain brief"| BRIEF
    MACRO -->|"macro brief"| BRIEF
    SM -->|"smart money brief"| BRIEF

    BRIEF -->|"briefing"| PANEL

    subgraph PANEL["② Investment Panel — parallel, each seat reads the brief + votes"]
        G["investor-benjamin-graham\nValue school\nGraham / Klarman"]
        B["investor-warren-buffett\nQuality school\nBuffett / Fisher"]
        D["investor-ray-dalio\nCycle school\nDalio / Templeton"]
        DR["investor-stanley-druckenmiller\nTrend school\nDruckenmiller / Carver"]
        BU["analyse-defi\nOn-chain school\nBurniske"]
    end

    G -->|"BULLISH / NEUTRAL / BEARISH + reason"| QUORUM
    B -->|"vote"| QUORUM
    D -->|"vote"| QUORUM
    DR -->|"vote"| QUORUM
    BU -->|"vote"| QUORUM

    QUORUM["③ CIO counts votes\nseats_bull ≥ 4 → BUY\n≥ 3 → BUY(small)\nbear ≥ 4 → SELL\nelse → HOLD"]

    QUORUM --> GOV["F&G Governor Cap\nExtreme Fear → max 3\nFear → max 5"]
    GOV --> OUT["📋 Final Report\nper-token: analyst briefs + panel reasoning + signal\nACTIVE / WATCH / HOLD / SELL"]
```

## Layers

### Layer 1 — Research Desk (data gatherers, no votes)

| Analyst | Skill | Data source |
|---|---|---|
| Technical | [`analyse-technical`](../analyse-technical/SKILL.md) | TradingView MCP — OHLCV, RSI, BB, MACD, MAs |
| BTC valuation | [`analyse-onchain`](../analyse-onchain/SKILL.md) | MVRV-Z, realized price, NUPL, Puell, LTH/STH supply, exchange flows |
| On-chain DeFi | [`analyse-defi`](../analyse-defi/SKILL.md) | DeFiLlama: TVL, fee distribution, protocol accrual |
| Macro | [`analyse-macro`](../analyse-macro/SKILL.md) | GLI, M2, DXY, ETF flows, halving cycle, macro headlines |
| Smart money | [`analyse-smartmoney`](../analyse-smartmoney/SKILL.md) | Whale flows, exchange inflows/outflows, OTC desk, positioning |

> **`analyse-onchain` vs `analyse-defi` — two layers of "on-chain", different assets.** `analyse-onchain` reads the cost-basis and holder behavior of a monetary asset (BTC/ETH/SOL); `analyse-defi` reads protocol fundamentals of a DeFi token (AAVE/UNI/JUP/AERO…). They are complementary seats, not duplicates.
>
> | | `analyse-onchain` | `analyse-defi` |
> |---|---|---|
> | **Question** | "Is **BTC** cheap or expensive in its cycle?" | "Does **this protocol's token** capture real value?" |
> | **Asset** | Bitcoin / L1 monetary assets | DeFi protocol tokens |
> | **Framework** | Cycle/valuation — MVRV-Z, NUPL, realized price, Puell, LTH/STH, exchange flows | Burniske value-accrual — revenue, TVL, fee distribution |
> | **Data source** | `crypto-onchain-data` (Glassnode/CryptoQuant style) | DeFiLlama |
> | **Output** | Zone verdict (DEEP VALUE → EXTREME) + confidence | BULLISH / NEUTRAL / BEARISH vote + reason |

### Layer 2 — Investment Panel (read briefing, vote per school)

| Seat | Skill | School |
|---|---|---|
| Value | [`investor-benjamin-graham`](../investor-benjamin-graham/SKILL.md) | Graham (*The Intelligent Investor* ch.20) / Klarman |
| Quality | [`investor-warren-buffett`](../investor-warren-buffett/SKILL.md) | Buffett / Fisher (*Common Stocks and Uncommon Profits*) |
| Cycle | [`investor-ray-dalio`](../investor-ray-dalio/SKILL.md) | Dalio / Templeton ("maximum pessimism") |
| Trend | [`investor-stanley-druckenmiller`](../investor-stanley-druckenmiller/SKILL.md) | Druckenmiller / Carver (*Systematic Trading*) |
| On-chain | [`analyse-defi`](../analyse-defi/SKILL.md) | Burniske (*Cryptoassets* value-accrual) — dual role: research + vote |

### Layer 3 — CIO (vote count → signal → governor → report)

## Signal table

```
seats_bear ≥ 4   → SELL
seats_bull ≥ 4   → BUY
seats_bull ≥ 3   → BUY(small)
else             → HOLD
```

## Governor cap

| F&G regime | Max simultaneous active buys |
|---|---|
| Extreme Fear (0–24) | 3 |
| Fear (25–49) | 5 |
| Neutral+ (50–100) | no cap |

Rank by seats_bull DESC, downgrade lowest-conviction buys to WATCH.

## Token universe

BTC · ETH · SOL · TON · HYPE · AAVE · JUP · UNI · AERO · PUMP · LINK

## Related docs

- [`docs/crypto-advisor-panel.prd.md`](../../docs/crypto-advisor-panel.prd.md) — design rationale, school citations
- [`docs/crypto-advisor-panel.tdd.md`](../../docs/crypto-advisor-panel.tdd.md) — data contracts, runtime adapters
- [`SKILL.md`](SKILL.md) — full orchestration instructions for the agent
