# Strategy v3 — Bubble-Aware All-Weather (current)

> **Status: CURRENT recommendation.** Educational analysis, not financial advice. Before deploying
> real capital at this size, talk to a fee-only fiduciary and write a one-page Investment Policy
> Statement you'll actually follow through a −40% drawdown.

## The thesis

v1 showed entry timing barely matters. v2 showed selection doesn't reliably beat the index. So the
edge isn't *when* you buy or *what* you pick — it's **structure**:

1. **De-concentrate the equity core** (away from ~40% AI-correlated mega-caps).
2. **Add uncorrelated diversifiers and crisis-alpha** that don't depend on a market call (gold, trend).
3. **Keep dry powder** and deploy it *into* declines by rule.
4. **Govern it with deterministic risk management** and an agentic team.

You participate if the bull continues, and you survive — with ammo — if it breaks. No prediction required.

## The evidence it's built on — the **actual v3 allocation**, backtested

Earlier versions of this doc borrowed the crisis numbers of generic textbook portfolios
(Permanent / Golden Butterfly / All-Weather) and implied they were v3's. They were not. v3 has now been
backtested **as specified** — the exact Balanced weights, each sleeve mapped to a long-history proxy and
return-spliced onto the real ETF, with the dip-reserve ladder simulated. Script:
[`backtests/v3_proxy_backtest.py`](../backtests/v3_proxy_backtest.py); full output (incl. every proxy
caveat): [`results/v3_proxy_summary.txt`](../backtests/results/v3_proxy_summary.txt).

**Full period, $1M, 2000-2026:**

| Strategy | CAGR | Sharpe | Max DD | 2000-09 "lost decade" |
|---|:--:|:--:|:--:|:--:|
| **v3 Balanced (static)** | 6.8% | **0.53** | **−27%** | **+73%** |
| v3 + dip ladder | 7.8% | 0.55 | −32% | +84% |
| v3 (no trend sleeve) | 6.8% | 0.49 | −31% | +68% |
| S&P 500 Buy&Hold | 8.3% | 0.38 | **−55%** | **−9%** |
| QQQ Buy&Hold | 8.7% | 0.35 | **−83%** | **−50%** |

**Per crisis (total return / max drawdown):**

| Event | v3 static | S&P 500 | QQQ |
|---|:--:|:--:|:--:|
| Dot-com 2000-02 | −12% / −13% | −47% / −47% | −83% / −83% |
| GFC 2007-09 | −26% / −27% | −55% / −55% | −52% / −53% |
| COVID 2020 | −17% / −17% | −34% / −34% | −28% / −29% |
| 2022 stocks+bonds | −8% / −9% | −25% / −25% | −34% / −34% |

**What v3's own numbers say — honestly:**

1. **The crash protection is real.** v3 roughly **halves the max drawdown** (−27% vs −55%) and was
   **+73% through the 2000-09 lost decade while the S&P was −9%**. In every crisis window it fell far
   less than the index. This is the whole point, and it holds up on v3's actual weights.
2. **The cost is steep in bulls.** v3 lags the index lifetime (**6.8% vs 8.3% CAGR**) — and in the
   **real-ETF era 2019-2026 (no proxies, real funds only):** v3 **8.6%** CAGR vs S&P **16.8%** / QQQ
   **23.3%**, with v3's drawdown −17% vs −34%/−35%. v3's Sharpe edge over the index (0.53 vs 0.38
   lifetime) is **earned almost entirely in the 2000-09 crisis decade** — in the recent bull v3's Sharpe
   (0.71) was *below* the S&P's (0.75). If no crash comes, you will underperform, possibly for years.
3. **The dip ladder is not free downside protection.** Deploying the reserve *into* declines raises
   equity exposure, so it **adds long-run return (7.8% vs 6.8%) but also adds drawdown (−32% vs −27%)**.
   It's a return enhancer with a risk cost, not a hedge. Size it to the drawdown you can stomach.
4. **The trend sleeve helps risk-adjusted, modestly.** Dropping it leaves CAGR flat (6.8%) but lowers
   Sharpe (0.49 vs 0.53) and deepens drawdown — consistent with managed futures earning its keep in
   crises, not bulls.

⚠️ **Proxy honesty:** pre-2019 most sleeves use long-history proxies (RSP/USMV→S&P, AVUV→VISVX,
DBMF→a 3-asset trend proxy, BTAL→cash). Several **understate** v3's real protection (min-vol, anti-beta)
and the trend proxy is a simplification. The 2019-2026 real-ETF table is the no-proxy cross-check. Full
list of substitutions and what each over/understates is in the caveats block of
[`results/v3_proxy_summary.txt`](../backtests/results/v3_proxy_summary.txt). Broader context:
[`../research/03-backtest-evidence.md`](../research/03-backtest-evidence.md),
[`../research/08-the-1M-playbook.md`](../research/08-the-1M-playbook.md).

## The portfolio — pick a risk tier

Each column is a **target allocation** for the fully-deployed portfolio. **Balanced is the default.**
Every ETF choice — the principle behind the sleeve and the verified fund facts — is sourced in
[`v3-etf-rationale.md`](v3-etf-rationale.md). To turn this into **today's dollar buy list** from live
prices (allocation + regime + active dip tier), run
[`backtests/v3_allocate_today.py`](../backtests/v3_allocate_today.py) `--capital 1000000`.

| Sleeve | ETF examples | Defensive | **Balanced** | Growth-tilt |
|--------|--------------|:-----:|:-----:|:-----:|
| US large cap | VOO / RSP (equal-wt) | 12% | 18% | 26% |
| International | VXUS / VEA+VWO | 10% | 12% | 12% |
| US small/mid **value** | AVUV / VBR | 6% | 8% | 10% |
| Min-vol / quality equity | USMV / QUAL | 8% | 7% | 6% |
| **Gold** | GLD / IAU | 12% | 10% | 8% |
| **Trend / managed futures** | DBMF / KMLM | 12% | 10% | 8% |
| Long/intermediate Treasuries | TLT / IEF | 8% | 7% | 4% |
| TIPS / commodities | SCHP / PDBC | 5% | 3% | 2% |
| **Dry powder (T-bills)** | SGOV / BIL | 25% | 22% | 22% |
| Tail / anti-beta (optional) | TAIL / BTAL | 2% | 3% | 2% |
| **Total equity beta** | | ~36% | **~45%** | ~54% |

**Why this shape:** equity is de-concentrated (equal-weight, international, value, min-vol) instead of
~40% AI mega-caps; **gold + trend** are the two diversifiers that *worked in 2022 when bonds failed*;
Treasuries are kept modest (the 2022 duration lesson); ~22-25% dry powder is deployed into declines and
earns ~4-5% in T-bills while it waits; the optional tail sleeve covers the *fast* crash that breaks trend.

## The deployment schedule (cash → invested)

Don't dump $1M in at all-time highs. Tranche the whole portfolio:

| Bucket | % of $1M | How |
|--------|:--------:|-----|
| **Foundation** | 50% ($500K) | Buy the target mix now (or spread over 4-8 weeks). |
| **Systematic DCA** | 28% ($280K) | Equal monthly buys over 12-18 months. |
| **Dip Reserve** | 22% ($220K) | Held in SGOV; deployed on S&P drawdowns by tier (below). |

**Dip-reserve tiers** (from the 52-week high, weekly closes, don't skip tiers):

| Tier | Trigger | % of reserve | Sub-tranches |
|------|:--:|:--:|:--:|
| Tier 1 | −7% | 20% | −7% / −8.5% / −10% / time |
| Tier 2 | −12% | 30% | −12% / −14% / −16% / time |
| Tier 3 | −20%+ | 50% | −20% / −25% / −30% / time |

If 18-24 months pass with no dip, fold the unused reserve into the DCA stream (cash drag is real).
Deploy dip cash into the **de-concentrated mix**, not just into QQQ.

## Operating rules

- **Rebalance** on a calendar check (quarterly) but **act only on threshold breach** (sleeve drifts
  >±20% relative or >±5% absolute). Low turnover, tax-aware (harvest losses).
- **Sell discipline (write it down now):** you do *not* sell on headlines — you rebalance mechanically
  and let trend/min-vol do the de-risking. The only discretionary pause is the last dip sub-tranche in a
  genuine 2008-style systemic event (VIX > 40, credit spreads blowing out) — then reassess.
- **What would change the thesis:** AI capex starts earning clear ROI and breadth broadens durably →
  drift toward Growth-tilt. Concentration + CAPE keep rising on debt-funded capex → stay Defensive.

## How it runs — the agentic team

Implemented as the [`../skills/`](../skills/README.md) `SKILL.md` set, coordinated by
`agentic-fund-orchestration` in a daily, **notification-first** loop:

```
INGEST (yfinance+FRED) → REGIME (exposure dial) → ANALYZE (context + backtest gate)
→ SIGNALS (trend) → CONSTRUCT (target weights) → RISK (veto/de-risk, deterministic)
→ DIP (deploy reserve) → REBALANCE → TAX → NOTIFY (human approves) → EXECUTE → LOG
```

| Role | Skill |
|---|---|
| Regime analyst | `regime-detection` |
| Research analyst | `fundamental-analysis` (sources + mandatory backtest gate) |
| Signal analyst | `trend-following` |
| Portfolio manager | `portfolio-construction` + `rebalancing` |
| Risk manager (veto) | `risk-management` |
| Cash deployer | `dip-tranches-strategy` |
| Tax agent | `tax-loss-harvesting` |
| Orchestrator | `agentic-fund-orchestration` |

**Guardrails (non-negotiable):** notification-first for 6+ months; paper-trade before live; human
approval for go-live, large trades, and leverage changes; the kill switch + hard exposure caps live in
**deterministic code outside any LLM** — agents propose, the risk layer disposes; full immutable audit log.

## The honest trade-off

In a continued AI bull, this **will** lag a 100% QQQ holder — possibly by a lot. v3's own backtest shows
it: 2009-2026 recovery **+345% (static) vs S&P +1398% / QQQ +3187%**, and real funds 2019-2026 **8.6% vs
16.8% / 23.3% CAGR**. That underperformance is the **premium you pay** to not lose 50-80% and a decade if
the bubble bursts. If your honest answer is "20-year horizon, I'll never sell,
I can stomach −80%," a larger cap-weight slice is defensible. For a $1M windfall when you're *already
worried about a bubble*, capping the left tail is worth the premium. Choose the column that matches the
drawdown you can actually live through.

## Provenance
`backtests/crash_protection_backtest.py` + `backtests/results/crash_protection_summary.txt`;
`research/` notes 01-08; the agent team in `skills/`.
