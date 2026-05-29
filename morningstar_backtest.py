"""
Morningstar-Proxy DCA Backtest
Proxy rule: stock is "undervalued" if price >= 20% below 52-week high at quarter start
"""

import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import yfinance as yf
from datetime import timedelta

# ── Config ─────────────────────────────────────────────────────────────────
SP500_SUBSET = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN",
    "JNJ", "UNH", "LLY", "ABBV",
    "JPM", "BAC", "GS", "BRK-B",
    "XOM", "CVX",
    "PG", "KO", "WMT", "COST",
    "CAT", "HON", "UNP",
    "DIS", "NFLX", "T",
    "LIN", "APD",
    "AMT", "PLD",
]

ALL_TICKERS = SP500_SUBSET + ["VOO"]
TOTAL_CAPITAL = 100_000
DOWNLOAD_START = "2019-01-01"
DOWNLOAD_END   = "2026-05-28"
END_DATE       = pd.Timestamp("2026-05-27")
MM_RATE        = 0.04          # 4% annual MM yield on uninvested cash
RF_WEEKLY      = MM_RATE / 52  # risk-free rate per week

# Quarterly start dates
STARTS = pd.date_range("2020-01-01", "2024-10-01", freq="QS")
NUM_QUARTERS = len(STARTS)          # 20
INSTALLMENT  = TOTAL_CAPITAL / NUM_QUARTERS

print(f"Number of quarters: {NUM_QUARTERS}")
print(f"Installment per quarter: ${INSTALLMENT:,.0f}")

# ── Download price data (once) ─────────────────────────────────────────────
print("\nDownloading price data …")
raw = yf.download(
    ALL_TICKERS,
    start=DOWNLOAD_START,
    end=DOWNLOAD_END,
    interval="1wk",
    auto_adjust=True,
    progress=False,
)["Close"]

# Normalise column names (yfinance may return MultiIndex)
if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.get_level_values(0)

prices = raw.copy()
prices.index = pd.to_datetime(prices.index)
prices = prices.sort_index()

print(f"Price data shape: {prices.shape}")
print(f"Date range: {prices.index[0].date()} → {prices.index[-1].date()}")
missing_tickers = [t for t in ALL_TICKERS if t not in prices.columns]
print(f"Missing tickers: {missing_tickers if missing_tickers else 'none'}")

# ── Helper: nearest weekly close on or after a date ────────────────────────
def nearest_close_on_or_after(date, price_series):
    """Return (actual_date, price) for the first available weekly close >= date."""
    future = price_series[price_series.index >= date].dropna()
    if future.empty:
        return None, np.nan
    return future.index[0], future.iloc[0]

# ── Screener: stocks ≥20% below 52-week high at quarter start ──────────────
def screen_stocks(quarter_start, prices_df, tickers):
    """
    Return list of tickers that are >= 20% below their 52-week high
    as of the first available weekly close on/after quarter_start.
    """
    # 52-week window: [quarter_start - 365 days, quarter_start]
    window_start = quarter_start - timedelta(days=365)

    selected = []
    for ticker in tickers:
        if ticker not in prices_df.columns:
            continue
        series = prices_df[ticker].dropna()

        # Current price: first close on/after quarter_start
        _, current_price = nearest_close_on_or_after(quarter_start, series)
        if np.isnan(current_price):
            continue

        # 52-week high up to (but not including) the buy date
        hist = series[(series.index >= window_start) & (series.index < quarter_start)]
        if hist.empty:
            continue
        high_52w = hist.max()

        # Dip threshold
        if current_price <= high_52w * 0.80:   # >= 20% below high
            selected.append(ticker)

    return selected

# ── Single backtest run ─────────────────────────────────────────────────────
def run_backtest(first_quarter_start, prices_df):
    """
    Runs the strategy from first_quarter_start to END_DATE.
    Returns dict with portfolio series, VOO series, stats.
    """
    # All quarter starts from first_quarter_start up to the last one in STARTS
    # that is >= first_quarter_start
    q_starts = [q for q in STARTS if q >= first_quarter_start]

    # Holdings: {ticker: shares}
    strategy_holdings = {}
    voo_holdings = 0.0

    # Cash (uninvested)
    strategy_cash = 0.0
    voo_cash = 0.0

    # Track what was deployed at each quarter
    quarterly_log = []

    for i, q_start in enumerate(q_starts):
        selected = screen_stocks(q_start, prices_df, SP500_SUBSET)

        # Buy date: first weekly close on/after q_start
        if "VOO" not in prices_df.columns:
            break
        buy_date, voo_price = nearest_close_on_or_after(q_start, prices_df["VOO"].dropna())
        if buy_date is None:
            continue

        # ── Cash interest up to this quarter's buy date ──────────────────
        if i > 0:
            prev_buy = quarterly_log[-1]["buy_date"]
            weeks_elapsed = max(0, (buy_date - prev_buy).days / 7)
            strategy_cash *= (1 + RF_WEEKLY) ** weeks_elapsed
            voo_cash      *= (1 + RF_WEEKLY) ** weeks_elapsed

        # ── Receive installment ──────────────────────────────────────────
        strategy_cash += INSTALLMENT
        voo_cash      += INSTALLMENT

        # ── Strategy: buy selected stocks ────────────────────────────────
        if selected:
            alloc_per_stock = strategy_cash / len(selected)  # invest ALL cash
            for ticker in selected:
                _, price = nearest_close_on_or_after(q_start, prices_df[ticker].dropna())
                if np.isnan(price) or price <= 0:
                    continue
                shares = alloc_per_stock / price
                strategy_holdings[ticker] = strategy_holdings.get(ticker, 0) + shares
                strategy_cash -= alloc_per_stock
            # If some tickers had bad prices, leftover cash stays
        else:
            # Fallback: buy VOO
            shares = strategy_cash / voo_price
            strategy_holdings["VOO"] = strategy_holdings.get("VOO", 0) + shares
            strategy_cash = 0.0

        # ── Benchmark: buy VOO ────────────────────────────────────────────
        voo_shares = voo_cash / voo_price
        voo_holdings += voo_shares
        voo_cash = 0.0

        quarterly_log.append({
            "quarter": q_start,
            "buy_date": buy_date,
            "selected": selected,
            "n_selected": len(selected),
        })

    # ── Build weekly portfolio value series ──────────────────────────────
    eval_dates = prices_df.index[prices_df.index >= first_quarter_start]

    strategy_values = []
    voo_values      = []

    for date in eval_dates:
        # Strategy equity
        equity = 0.0
        for ticker, shares in strategy_holdings.items():
            if ticker in prices_df.columns:
                price_row = prices_df.loc[:date, ticker].dropna()
                if not price_row.empty:
                    equity += shares * price_row.iloc[-1]

        # Cash: approximate — track interest to this date from last buy
        # (simplified: treat cash as of last quarter buy earning MM)
        strategy_values.append(equity + strategy_cash)

        # VOO benchmark
        voo_row = prices_df.loc[:date, "VOO"].dropna()
        if not voo_row.empty:
            voo_val = voo_holdings * voo_row.iloc[-1] + voo_cash
        else:
            voo_val = 0
        voo_values.append(voo_val)

    port_series = pd.Series(strategy_values, index=eval_dates)
    voo_series  = pd.Series(voo_values,      index=eval_dates)

    return {
        "port": port_series,
        "voo":  voo_series,
        "log":  quarterly_log,
    }

# ── Stats helper ────────────────────────────────────────────────────────────
def compute_stats(series):
    """CAGR, max drawdown, Sharpe (weekly)."""
    series = series.dropna()
    if len(series) < 2 or series.iloc[0] == 0:
        return np.nan, np.nan, np.nan

    years = (series.index[-1] - series.index[0]).days / 365.25
    total_ret = series.iloc[-1] / series.iloc[0] - 1
    cagr = (1 + total_ret) ** (1 / years) - 1 if years > 0 else np.nan

    # Max drawdown
    rolling_max = series.cummax()
    drawdown    = (series - rolling_max) / rolling_max
    max_dd      = drawdown.min()

    # Sharpe
    weekly_ret = series.pct_change().dropna()
    excess     = weekly_ret - RF_WEEKLY
    sharpe     = (excess.mean() / excess.std() * np.sqrt(52)) if excess.std() > 0 else np.nan

    return cagr, max_dd, sharpe

# ── Run all 20 backtests ─────────────────────────────────────────────────────
print("\nRunning backtests …")
results = []

for start in STARTS:
    res = run_backtest(start, prices)

    s_cagr, s_dd, s_sharpe = compute_stats(res["port"])
    v_cagr, v_dd, v_sharpe = compute_stats(res["voo"])

    n_quarters  = len(res["log"])
    avg_selected = np.mean([q["n_selected"] for q in res["log"]]) if res["log"] else 0
    pct_ge3     = np.mean([q["n_selected"] >= 3 for q in res["log"]]) * 100 if res["log"] else 0

    results.append({
        "start_date":               start,
        "strategy_cagr":            s_cagr,
        "benchmark_cagr":           v_cagr,
        "strategy_wins":            (s_cagr > v_cagr) if not np.isnan(s_cagr) and not np.isnan(v_cagr) else False,
        "avg_stocks_per_quarter":   avg_selected,
        "pct_quarters_ge3_stocks":  pct_ge3,
        "port_series":              res["port"],
        "voo_series":               res["voo"],
        "log":                      res["log"],
    })
    print(f"  {start.date()}: strategy CAGR={s_cagr:.2%} | VOO CAGR={v_cagr:.2%} | avg stocks={avg_selected:.1f}")

# ── Print results table ───────────────────────────────────────────────────────
print("\n" + "="*90)
print(f"{'Start':>12} | {'Strat CAGR':>10} | {'VOO CAGR':>9} | {'Wins?':>6} | {'Avg Stocks':>10}")
print("-"*90)

summary_lines = []
header = f"{'Start':>12} | {'Strat CAGR':>10} | {'VOO CAGR':>9} | {'Wins?':>6} | {'Avg Stocks':>10}"
summary_lines.append(header)
summary_lines.append("-"*90)

wins = 0
cagr_diffs = []

for r in results:
    s_cagr = r["strategy_cagr"]
    v_cagr = r["benchmark_cagr"]
    wins  += int(r["strategy_wins"])
    if not np.isnan(s_cagr) and not np.isnan(v_cagr):
        cagr_diffs.append(s_cagr - v_cagr)

    line = (f"  {r['start_date'].date()!s:>10} | "
            f"{s_cagr:>10.2%} | "
            f"{v_cagr:>9.2%} | "
            f"{'YES' if r['strategy_wins'] else 'NO':>6} | "
            f"{r['avg_stocks_per_quarter']:>10.1f}")
    print(line)
    summary_lines.append(line)

print("="*90)
footer_lines = [
    "",
    f"Strategy wins: {wins}/{len(results)} quarters ({wins/len(results):.0%})",
    f"Average CAGR advantage (strategy - VOO): {np.mean(cagr_diffs):.2%}",
    f"Quarters with ≥3 stocks selected: "
      f"{np.mean([r['pct_quarters_ge3_stocks'] for r in results]):.1f}% avg per run",
]
for l in footer_lines:
    print(l)
    summary_lines.append(l)

# ── Chart ─────────────────────────────────────────────────────────────────────
print("\nGenerating chart …")

cagr_advantages = [r["strategy_cagr"] - r["benchmark_cagr"]
                   for r in results
                   if not np.isnan(r["strategy_cagr"]) and not np.isnan(r["benchmark_cagr"])]
labels = [r["start_date"].strftime("Q%q-%Y") for r in results
          if not np.isnan(r["strategy_cagr"]) and not np.isnan(r["benchmark_cagr"])]

fig, axes = plt.subplots(1, 2, figsize=(18, 7))
fig.suptitle("Morningstar-Proxy DCA Backtest  (≥20% below 52-week high)\nvs VOO DCA Benchmark",
             fontsize=13, fontweight="bold", y=1.01)

# ── Left: CAGR advantage bar chart ──────────────────────────────────────────
ax1 = axes[0]
colors = ["#2ecc71" if x >= 0 else "#e74c3c" for x in cagr_advantages]
bars = ax1.bar(range(len(cagr_advantages)), [x*100 for x in cagr_advantages], color=colors, edgecolor="white")
ax1.axhline(0, color="black", linewidth=0.8)
ax1.set_xticks(range(len(labels)))
ax1.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
ax1.set_ylabel("CAGR Advantage (Strategy − VOO)  [pp]")
ax1.set_title(f"CAGR Advantage per Start Quarter  ({wins}/{len(results)} wins)")
ax1.grid(axis="y", alpha=0.3)
# Add value labels
for i, (bar, v) in enumerate(zip(bars, cagr_advantages)):
    ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + (0.3 if v >= 0 else -0.6),
             f"{v*100:+.1f}", ha="center", va="bottom" if v >= 0 else "top", fontsize=7)

# ── Right: scatter of final CAGRs ────────────────────────────────────────────
ax2 = axes[1]
s_cagrs = [r["strategy_cagr"]*100 for r in results if not np.isnan(r["strategy_cagr"])]
v_cagrs = [r["benchmark_cagr"]*100 for r in results if not np.isnan(r["benchmark_cagr"])]
ax2.scatter(v_cagrs, s_cagrs, c=["#2ecc71" if s > v else "#e74c3c" for s, v in zip(s_cagrs, v_cagrs)],
            s=80, edgecolors="black", linewidths=0.5, zorder=3)
mn = min(min(s_cagrs), min(v_cagrs)) - 2
mx = max(max(s_cagrs), max(v_cagrs)) + 2
ax2.plot([mn, mx], [mn, mx], "k--", linewidth=0.8, label="y=x (break-even)")
ax2.set_xlabel("VOO DCA CAGR (%)")
ax2.set_ylabel("Strategy CAGR (%)")
ax2.set_title("Strategy vs VOO CAGR (green = strategy wins)")
ax2.legend(fontsize=8)
ax2.grid(alpha=0.3)
for i, (lbl, sx, vx) in enumerate(zip(labels, s_cagrs, v_cagrs)):
    ax2.annotate(lbl, (vx, sx), textcoords="offset points", xytext=(4, 2), fontsize=6)

plt.tight_layout()
out_png = "/home/ubuntu/projects/investor/morningstar_proxy_backtest.png"
plt.savefig(out_png, dpi=150, bbox_inches="tight")
print(f"Chart saved: {out_png}")

# ── Save summary text ─────────────────────────────────────────────────────────
out_txt = "/home/ubuntu/projects/investor/morningstar_summary.txt"
with open(out_txt, "w") as f:
    f.write("MORNINGSTAR-PROXY DCA BACKTEST SUMMARY\n")
    f.write("="*90 + "\n")
    f.write("Proxy rule: S&P500 stock selected each quarter if price >= 20% below 52-week high\n")
    f.write("Benchmark:  VOO DCA with equal quarterly installments\n")
    f.write("Capital:    $100,000 | Installment: $5,000/quarter\n")
    f.write("="*90 + "\n\n")
    f.write("\n".join(summary_lines))
print(f"Summary saved: {out_txt}")

# ── Final key findings ────────────────────────────────────────────────────────
print("\n" + "="*60)
print("KEY FINDINGS")
print("="*60)
print(f"  Strategy beats VOO: {wins}/{len(results)} start quarters ({wins/len(results):.0%})")
print(f"  Avg CAGR advantage: {np.mean(cagr_diffs)*100:+.2f} percentage points")
print(f"  Median CAGR advantage: {np.median(cagr_diffs)*100:+.2f} pp")

# Pct quarters with >=3 stocks
all_pct_ge3 = []
for r in results:
    for q in r["log"]:
        all_pct_ge3.append(q["n_selected"] >= 3)
print(f"  % of all individual quarters with ≥3 stocks selected: {np.mean(all_pct_ge3)*100:.1f}%")

# Average stocks per quarter across all runs
all_n = [q["n_selected"] for r in results for q in r["log"]]
print(f"  Avg stocks selected per quarter: {np.mean(all_n):.1f} (range {min(all_n)}–{max(all_n)})")
