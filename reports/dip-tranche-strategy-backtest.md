# Dip-Tranche Strategy: S&P 500, Nasdaq-100, International — Backtest 2020-2026

> Source: [https://telegra.ph/Dip-Tranche-Strategy-SP-500-Nasdaq-100-International--Backtest-20202026-05-28](https://telegra.ph/Dip-Tranche-Strategy-SP-500-Nasdaq-100-International--Backtest-20202026-05-28)

> Saved: 2026-05-28


---


> Disclaimer: This report is for educational and analytical purposes only. Nothing here constitutes financial advice. Past backtest performance does not guarantee future results. Consult a licensed fiduciary advisor before making any investment decisions.


Source code & data: [github.com/dvashchuk/backtest](https://github.com/dvashchuk/backtest)


### TL;DR


> Strategy: Split $1M into three buckets — 50% lump-sum on day one, 30% DCA over 18 months, 20% held in a money-market fund as a tiered dip reserve. Deploy the reserve in tranches as the market falls: Tier 1 at −7/−8.5/−10%, Tier 2 at −12/−14/−16%, Tier 3 at −20/−25/−30% from the 52-week high. QQQ thresholds are scaled ×1.4 for its higher volatility.


Does it beat lump-sum? Rarely on raw CAGR — but that's not the point.


- VOO (S&P 500): Strategy 15.1% CAGR vs Lump Sum 15.8%. Lump sum wins, but strategy's max drawdown is −22.5% vs −27.4% — nearly 5pp shallower.
- QQQ (Nasdaq-100): Strategy 19.6% vs Lump Sum 21.7%. Similar story — lump sum wins on returns, strategy cushions the −34% QQQ crash.
- VXUS (International): Strategy 10.6% vs Lump Sum 10.2%. Strategy wins — slower international recoveries reward tiered entry.
- Across 20 starting quarters (2020–2024): lump sum wins 45/60 combinations. Strategy's edge is consistent drawdown reduction, not alpha generation.
- The 2022 bear market was the strategy's best showcase — all tiers deployed as markets ground down −25% to −38%, with every tranche profitable by 2023.
- The COVID crash (Mar 2020) was the worst case — too fast; the lump-sum buyer caught the full recovery from day one.


Bottom line: Use this strategy if you want shallower drawdowns and can tolerate slightly lower expected returns. The 20% dip reserve earns ~4% in a money-market fund while waiting — the opportunity cost is real but bounded. It is a risk-management tool, not an alpha tool.


---


### Executive Summary


This report backtests a tiered "dip-buying" deployment strategy against two benchmarks (lump-sum and pure DCA) across three ETFs — VOO (S&P 500), QQQ (Nasdaq-100), and VXUS (Total International) — using weekly closing data from January 2020 through May 2026.


The core finding: the strategy did not beat lump-sum on raw returns for US equities in this particular window (which started just before the fastest crash-and-recovery in market history), but it consistently reduced maximum portfolio drawdown by 3–5 percentage points and outperformed lump-sum on VXUS, where recoveries are slower. The strategy is best understood as a risk-management tool that trades some upside for shallower drawdowns and psychological staying power during corrections.


---


### Strategy Overview


#### The 50 / 30 / 20 Allocation


A $1,000,000 portfolio is divided into three buckets at inception:


- Bucket 1 — Foundation (50% = $500K): deployed as a lump sum on day one. Captures upside if the market continues higher; accepts the risk of buying near a local top.
- Bucket 2 — DCA (30% = $300K): deployed in equal weekly instalments over 18 months (~$3,840/week). Smooths cost basis, removes decision fatigue, keeps capital working.
- Bucket 3 — Dip Reserve (20% = $200K): held in a money-market fund earning ~4% annualised while waiting for drawdown triggers. Deployed in tranches as the market falls.


#### Tiered Dip Reserve — How It Works


The reserve is split into three tiers based on drawdown severity from the rolling 52-week high. Each tier has four sub-tranches: three price-triggered and one time-triggered (fires if price remains below the tier entry threshold for N weeks without recovering).


```
VOO / VXUS triggers (β-mult 1.0)         QQQ triggers (β-mult 1.4)
─────────────────────────────────         ────────────────────────────
Tier 1  20% of reserve  ($40K)            Tier 1  20%  ($40K)
  T1a   -7.0%  from 52w high  $10K          T1a  -9.8%            $10K
  T1b   -8.5%                 $10K          T1b -11.9%            $10K
  T1c  -10.0%                 $10K          T1c -14.0%            $10K
  T1d   time (2 wks below T1a)$10K          T1d  time             $10K

Tier 2  30% of reserve  ($60K)            Tier 2  30%  ($60K)
  T2a  -12.0%                 $15K          T2a -16.8%            $15K
  T2b  -14.0%                 $15K          T2b -19.6%            $15K
  T2c  -16.0%                 $15K          T2c -22.4%            $15K
  T2d   time (3 wks below T2a)$15K          T2d  time             $15K

Tier 3  50% of reserve ($100K)            Tier 3  50% ($100K)
  T3a  -20.0%                 $25K          T3a -28.0%            $25K
  T3b  -25.0%                 $25K          T3b -35.0%            $25K
  T3c  -30.0%                 $25K          T3c -42.0%            $25K
  T3d   time (4 wks below T3a)$25K          T3d  time             $25K
```


#### Guard Rules


- Cooldown: minimum 3 weeks between any two sub-tranche fills — prevents panic-buying every bar on the way down.
- Re-arm: if the market recovers above the re-arm threshold (-5% from new 52w high for VOO/VXUS, -7% for QQQ), all fired tiers reset. Capped at 2 re-arms per calendar year to avoid chasing noise.
- MM yield: idle reserve earns 4% annualised (money-market rate), accrued weekly — modelled conservatively.
- Triggers use weekly closes, not intraday wicks, to avoid flash-crash false triggers.


#### Why Different Triggers for QQQ?


QQQ has roughly 1.4× the volatility of VOO. Its 2022 drawdown (-38%) was ~13 percentage points deeper than VOO's (-25%) in the same event. Using VOO triggers on QQQ would fire Tier 3 too easily, depleting the reserve during routine corrections. Scaling all thresholds by 1.4× keeps the tier system calibrated to the asset's actual behaviour.


---


### Backtest Parameters


```
Period:          2020-01-01 → 2026-05-27  (6.4 years)
Data:            Weekly closes, adjusted for splits and dividends
Source:          Yahoo Finance via yfinance 1.4.0
Starting capital: $1,000,000
Benchmarks:
  Lump Sum  — 100% deployed on the first bar (2020-01-01)
  DCA 18m   — equal weekly instalments over 18 months
52-week high:    rolling max of prior 52 weekly closes
MM yield:        4.00% p.a. accrued weekly on reserve cash
Commissions:     not modelled (negligible for ETFs at this scale)
Taxes:           not modelled (tax wrapper dependent)
```


---


### VOO — Vanguard S&P 500 ETF


![VOO: price with entry points (top), portfolio value comparison (middle), drawdown vs tier triggers (bottom)](https://i.imgur.com/vAVtqEm.png)
*VOO: price with entry points (top), portfolio value comparison (middle), drawdown vs tier triggers (bottom)*


```
Metric                    Strategy    Lump Sum    DCA 18m
─────────────────────────────────────────────────────────
End value ($)           2,465,730   2,553,705  2,388,899
Total return              +146.6%     +155.4%    +138.9%
CAGR                       15.1%       15.8%      14.6%
Max portfolio drawdown    -22.5%      -27.4%     -24.3%
─────────────────────────────────────────────────────────
Strategy detail:
  Avg cost basis          $280.15     (last price $689.96)
  Unrealised gain/share   +146.3%
  Dip sub-tranches fired  18  (T1:12  T2:5  T3:1)
  Reserve deployed        $214,646 / $200,000  (100%)
```


VOO fired Tier 1 repeatedly through the COVID crash (Feb–Jun 2020) and again through the 2022 Fed-tightening bear market. Tier 2 filled across mid-2020 and mid-2022. Tier 3 fired just once: the Sept 2022 capitulation week at $329. The reserve was fully deployed by Q4 2022 — exactly the intended behaviour. Lump-sum edged the strategy by ~0.7% CAGR because the 2020 crash recovered so quickly that later tranches bought at higher prices than the initial lump-sum entry.


### QQQ — Invesco Nasdaq-100 ETF


![QQQ: price with entry points (top), portfolio value comparison (middle), drawdown vs tier triggers (bottom)](https://i.imgur.com/70ceMQc.png)
*QQQ: price with entry points (top), portfolio value comparison (middle), drawdown vs tier triggers (bottom)*


```
Metric                    Strategy    Lump Sum    DCA 18m
─────────────────────────────────────────────────────────
End value ($)           3,151,199   3,511,861  2,821,844
Total return              +215.1%     +251.2%    +182.2%
CAGR                       19.6%       21.7%      17.6%
Max portfolio drawdown    -31.2%      -34.3%     -34.3%
─────────────────────────────────────────────────────────
Strategy detail:
  Avg cost basis          $226.22     (last price $729.45)
  Unrealised gain/share   +222.4%
  Dip sub-tranches fired  17  (T1:11  T2:4  T3:2)
  Reserve deployed        $219,784 / $200,000  (100%)
```


QQQ had the highest absolute returns across the period (+251% lump-sum, +215% strategy), but also the deepest drawdowns (-34%). The strategy softened the portfolio drawdown to -31.2% versus -34.3% for lump-sum. Tier 3 fired twice in 2022 (the QQQ bear market bottomed at -38% from its high). The 2024 yen-carry unwind and 2025 tariff selloff both triggered Tier 1 buys that were profitable. The lump-sum gap is wider here than VOO because QQQ compounded faster — earlier capital worked harder for longer.


### VXUS — Vanguard Total International ETF


![VXUS: price with entry points (top), portfolio value comparison (middle), drawdown vs tier triggers (bottom)](https://i.imgur.com/DDabFAP.png)
*VXUS: price with entry points (top), portfolio value comparison (middle), drawdown vs tier triggers (bottom)*


```
Metric                    Strategy    Lump Sum    DCA 18m
─────────────────────────────────────────────────────────
End value ($)           1,909,517   1,860,850  1,871,948
Total return               +91.0%      +86.1%     +87.2%
CAGR                       10.6%       10.2%      10.3%
Max portfolio drawdown    -26.6%      -29.3%     -29.3%
─────────────────────────────────────────────────────────
Strategy detail:
  Avg cost basis           $45.36     (last price $85.85)
  Unrealised gain/share    +89.3%
  Dip sub-tranches fired  16  (T1:8  T2:5  T3:3)
  Reserve deployed        $215,663 / $200,000  (100%)
```


VXUS is the only symbol where the dip-tranche strategy beat both benchmarks on CAGR (+10.6% vs +10.2% lump-sum and +10.3% DCA). International markets recover more slowly from corrections — the 2022 bear market on VXUS was prolonged, allowing Tier 2 and Tier 3 tranches to accumulate at $40–$46 before the eventual recovery to $85+. This is precisely the environment the strategy is designed for: slow, grinding drawdowns with extended bottoms.


---


### Summary: All Symbols


```
Symbol   CAGR   Total Ret   End Value    Max DD   Reserve
──────   ────   ─────────   ─────────    ──────   ───────
VOO     15.1%    +146.6%   $2,465,730   -22.5%    100%
QQQ     19.6%    +215.1%   $3,151,199   -31.2%    100%
VXUS    10.6%     +91.0%   $1,909,517   -26.6%    100%

Benchmarks (same period, lump-sum):
VOO     15.8%    +155.4%   $2,553,705   -27.4%
QQQ     21.7%    +251.2%   $3,511,861   -34.3%
VXUS    10.2%     +86.1%   $1,860,850   -29.3%
```


---


### Key Takeaways


- Lump-sum wins on raw returns in strong bull markets — Vanguard's research holds up here. If you started in 2020 with perfect hindsight that markets would recover quickly, you'd have gone all-in. Nobody has that hindsight.
- The strategy's edge is risk management, not alpha. It consistently reduced max portfolio drawdown by 3–5 percentage points versus lump-sum — meaningful when you're watching a $1M portfolio become $650K.
- VXUS is the natural home for this strategy. International equities have slower, deeper drawdowns with longer recovery cycles — exactly what tiered entry is built for.
- The 2022 bear market was the strategy's best showcase: Tier 1 fired 5–12 times per symbol as markets ground down, Tier 2 accumulated in the -12% to -16% zone, and Tier 3 deployed at the capitulation lows in Sep–Oct 2022. Every tranche was profitable by end of 2023.
- The COVID crash (Mar 2020) was the worst case for this strategy: too fast and too deep. Tier 1 fired near the top of the decline, Tier 2 near the middle, and then the market recovered before Tier 3 could deploy at the real bottom. The lump-sum buyer caught the full recovery from day 1.
- QQQ's higher triggers (-9.8% / -16.8% / -28%) were correct: without recalibration, the VOO triggers would have exhausted the reserve on routine Nasdaq noise. Always scale triggers to each asset's volatility.
- Re-arming matters: the cap of 2 re-arms per year prevented the strategy from being triggered every few weeks during 2022's volatile sideways grind.


---


### Automating the Strategy


The companion Python script (backtest.py) implements the full engine. To run it live as a daily monitor:


- Pull weekly closes each Friday after market close via yfinance or a paid source (Alpha Vantage, Polygon.io for reliability).
- Compute rolling 52-week high and current drawdown percentage.
- Check which sub-tranches should fire per the trigger table above.
- Send an alert (Telegram bot, email, or Slack) with the triggered tranche, recommended dollar amount, and current drawdown context.
- Place limit orders manually or via broker API (Alpaca or IBKR) — notification-only mode is strongly recommended until you have 6+ months of live observation.


A TradingView Pine Script v6 strategy visualising all tier trigger lines, entry markers, and a live status panel is available as a companion asset.


---


> Full disclaimer: This backtest was conducted using publicly available historical data. Results are hypothetical — they do not account for taxes, bid/ask spreads, slippage, or behavioural drag (the tendency to deviate from rules under stress). Past performance does not predict future returns. The authors are not licensed financial advisors. This document is shared for educational purposes. Before deploying real capital, consult a fee-only fiduciary CFP and a CPA familiar with your tax situation.


---


### Robustness Check: Does the Starting Date Matter?


A single backtest starting January 2020 is not representative — it happens to begin just before the fastest market crash-and-recovery in modern history. To stress-test the strategy, we ran it starting on the first trading day of every quarter from Q1-2020 through Q4-2024 (20 start dates per symbol), all ending on 2026-05-27.


#### VOO — S&P 500


![VOO: total return % and CAGR advantage (strategy vs lump-sum) across all 20 start quarters](https://i.imgur.com/6Pm7ehP.png)
*VOO: total return % and CAGR advantage (strategy vs lump-sum) across all 20 start quarters*


#### QQQ — Nasdaq-100


![QQQ: total return % and CAGR advantage across all 20 start quarters](https://i.imgur.com/d9aZmDd.png)
*QQQ: total return % and CAGR advantage across all 20 start quarters*


#### VXUS — Total International


![VXUS: total return % and CAGR advantage across all 20 start quarters](https://i.imgur.com/Kj7c0OL.png)
*VXUS: total return % and CAGR advantage across all 20 start quarters*


#### Summary across all 60 quarter-symbol combinations


```
               Strategy wins   Lump Sum wins   DCA wins
VOO                0 / 20          16 / 20      4 / 20
QQQ                1 / 20          17 / 20      2 / 20
VXUS               3 / 20          12 / 20      5 / 20
─────────────────────────────────────────────────────
Total              4 / 60          45 / 60     11 / 60

Avg CAGR gap (Strategy minus Lump Sum):
  VOO:  −2.58%   QQQ: −3.21%   VXUS: −1.61%
```


#### What this means


- Lump sum wins in trending bull markets — opportunity cost of holding the 20% reserve in cash drags the strategy in most quarters.
- The strategy's edge on VXUS (3 wins) confirms the finding from the main backtest: slower, choppier international recoveries reward tiered entry more than US markets.
- Even starting in bear-market quarters (Q1-22, Q2-22), lump sum often still wins — because lump sum also deploys at depressed prices and rides the same recovery. The strategy only wins when dips extend long enough for the reserve to accumulate at materially lower prices.
- DCA wins in 11/60 cases — specifically when you start right before a significant drawdown (Q3-21 through Q2-22 for VOO), where spreading deployment over 18 months builds a lower cost basis than the strategy's 50% lump-sum on day one.
- The strategy's consistent advantage is max drawdown reduction (−3 to −5 pp vs lump-sum), not CAGR — it is a risk tool, not an alpha tool.


---


Code: [Full backtest source on GitHub →](https://github.com/dvashchuk/backtest)


---


### Experiment 2: Copying Congressional Trades (Pelosi, McCaul, Green)


Insider trading laws don't apply to Congress. The STOCK Act requires disclosure within 45 days. We simulated copying three top traders' disclosed trades with a 30-day execution lag.


Rules: $1M starting capital. Buy each disclosed trade at min(notional, 15% of portfolio). Execute 30 days after trade date. Uninvested cash earns 4% MM yield. No selling.


![Congressional copy strategy vs VOO lump sum / DCA / Dip-Tranche (2020-2026)](https://i.imgur.com/uC7Lae9.png)
*Congressional copy strategy vs VOO lump sum / DCA / Dip-Tranche (2020-2026)*


```
Strategy          Final Value    CAGR    Max DD   Sharpe
-----------------------------------------------------------
McCaul (R-TX)     $4,914,174    28.3%   -43.9%    0.91
Pelosi (D-CA)     $3,196,671    20.0%   -42.7%    0.68
VOO Lump Sum      $2,517,120    15.6%   -27.4%    0.69
Dip-Tranche (ref) $2,461,030    15.2%   -22.5%    ~0.70
VOO DCA           $2,209,643    13.2%   -18.7%    0.71
Green (R-TN)      $2,024,399    11.7%   -26.7%    0.47

```


#### Key findings


- McCaul turned $1M to $4.9M (28.3% CAGR). Bought GOOGL/AMZN/MSFT at the COVID bottom and NVDA in May 2023 just before the AI supercycle.
- Pelosi's 20% CAGR was driven by NVDA (June 2021, Nov 2023) and the CHIPS Act AAPL+NVDA buys.
- Green underperformed plain VOO (11.7% vs 15.6%). Energy overweight dragged; Pfizer bought on vaccine day lost 40% by 2024.
- All congressional portfolios have far worse max drawdowns (-43% to -44%) than the Dip-Tranche strategy (-22.5%).
- Caveat: options (LEAPS/calls) in actual disclosures are not modeled here and would amplify returns further.


---


### Experiment 3: Morningstar-Proxy Screener + Quarterly DCA


We approximated Morningstar's 5-star screener with a simple rule: at each quarter start, select S&P 500 stocks >= 20% below their 52-week high. DCA equal amounts into selected stocks. Compare to VOO DCA.


Universe: 30 liquid S&P 500 stocks across all 11 sectors. 20 starting quarters (Q1-2020 through Q4-2024). $100K capital.


![CAGR advantage (strategy minus VOO DCA) per starting quarter - nearly all negative](https://i.imgur.com/yx6oFPJ.png)
*CAGR advantage (strategy minus VOO DCA) per starting quarter - nearly all negative*


```
       Start | Strat CAGR | VOO CAGR | Wins? | Avg Stocks
---------------------------------------------------------
  2020-01-01 |    14.63%  |  15.54%  |   NO  |    5.1
  2020-10-01 |    16.95%  |  15.99%  |  YES  |    4.7  <- only win
  2023-04-01 |    11.99%  |  22.83%  |   NO  |    2.1
  2024-01-01 |    13.82%  |  22.55%  |   NO  |    0.5
  ... (strategy wins 1 of 20 quarters; avg lag vs VOO: -4.26 pp CAGR)
```


#### Why it fails


- Wins 1 of 20 start quarters. Average CAGR drag vs VOO DCA: -4.26 percentage points.
- Screener dried up after 2022. From 2023 onward, avg stocks selected fell to 0.5-2 per quarter as mega-cap tech recovered above 52-week highs. Portfolio sat in 4% MM while VOO returned 20-25% CAGR.
- Value trap effect: stocks >= 20% below highs often stay there (DIS, T, PFE). Real Morningstar adds DCF fair value + moat ratings - price dip alone is noise.
- Verdict: the quality/valuation filter does the heavy lifting in Morningstar's methodology. A pure price-dip proxy does not replicate it.


---


### What's Next: AI/News-Driven Stock Selection (Research Survey)


Based on research across r/algotrading, Hacker News, and academic papers. Ranked by strength of evidence.


#### 1. GPT News Headline Sentiment


Score news headlines with GPT-4 (positive/negative/neutral per stock). Key paper: [Lopez-Lira & Tang 2023 (arXiv:2304.07619)](https://arxiv.org/abs/2304.07619) - ~90% portfolio-day hit rate for initial reaction. Community verdict: real signal in 2022-2023 but the paper itself notes 'returns decline as LLM adoption rises.' Likely crowded out now.


#### 2. PEAD + LLM (Most backtestable - recommended)


Post-Earnings Announcement Drift is the most academically solid foundation (Ball & Brown 1968). Modern twist: score SEC 8-K filings with GPT-3.5 within 60 min of release. Entry: stock moves <1.5% intraday despite strongly positive score AND EPS beat. Hold 5 days. Filter to small-cap. Free data: SEC EDGAR RSS + Alpha Vantage earnings.


#### 3. FinBERT on Earnings Call Transcripts


Apply [FinBERT (ProsusAI, 2.1k stars)](https://github.com/ProsusAI/finBERT) to management guidance sentences in quarterly 8-K transcripts. Score sentiment delta vs prior quarter. Long top-quintile, short bottom-quintile, monthly rebalance. Less crowded than headline sentiment. Li (2010) showed most alpha eroded post-2018 - treat as a screening layer, not standalone signal.


#### 4. Reddit/Social Sentiment (Largely played out)


Aggregate WSB mention counts + sentiment. Best on meme/small-cap and crypto. Tools: Tickerrain (r/algotrading: 922 upvotes). Community: mostly played out for equities since GME 2021.


#### 5. Multi-Agent LLM Consensus (Experimental - caution)


Run GPT-4, Claude, Gemini on the same news; trade on consensus. Warning: [arXiv:2311.07590](https://arxiv.org/abs/2311.07590) showed a GPT-4 autonomous trading agent committed simulated insider trading and hid it from its manager under performance pressure. No unmonitored live access recommended.


#### Top open-source repos


- [FinGPT (20.3k stars)](https://github.com/AI4Finance-Foundation/FinGPT)
- [FinRL - DRL trading (15.3k stars)](https://github.com/AI4Finance-Foundation/FinRL)
- [pybroker - ML backtesting with walkforward](https://github.com/edtechre/pybroker)


Bottom line: Academic signal is real. Practical alpha after costs, slippage, and crowding is unproven for retail. Best use today: LLMs as a screening/filtering layer, not autonomous trade execution.
