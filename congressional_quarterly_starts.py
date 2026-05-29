"""
Congressional Trading Backtest — Quarterly Start Date Sensitivity
Tests 20 quarterly start dates (Q1-2020 through Q4-2024).
For each start: investor starts with $1M, copies only trades executed AFTER start date.
Missed-trade capital stays in money-market at 4% annual until deployed.
Benchmark: $1M lump sum into VOO on same start date, held to 2026-05-27.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from datetime import timedelta
import warnings
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────
END_DATE           = "2026-05-27"
INITIAL_CASH       = 1_000_000.0
MM_RATE_ANNUAL     = 0.04
WEEKS_PER_YEAR     = 52
DISCLOSURE_LAG_DAYS = 30
POSITION_CAP_PCT   = 0.15

# 20 quarterly start dates: Q1-2020 through Q4-2024
STARTS = pd.date_range("2020-01-01", "2024-10-01", freq="QS")  # 20 dates

# ─────────────────────────────────────────────
# TRADE DATA (copied from congressional_backtest.py)
# ─────────────────────────────────────────────
PELOSI_TRADES = [
    ("AAPL",  "2020-02-28", 500_000),
    ("MSFT",  "2020-02-28", 250_000),
    ("GOOGL", "2020-07-02", 500_000),
    ("TSLA",  "2020-12-18", 500_000),
    ("AAPL",  "2021-01-29", 750_000),
    ("TSLA",  "2021-03-19", 250_000),
    ("NVDA",  "2021-06-18", 500_000),
    ("MSFT",  "2021-10-22", 500_000),
    ("AAPL",  "2022-07-26", 750_000),
    ("NVDA",  "2022-07-26", 1_000_000),
    ("AMZN",  "2022-11-17", 250_000),
    ("GOOGL", "2023-03-17", 500_000),
    ("NVDA",  "2023-11-10", 1_000_000),
    ("AAPL",  "2024-01-12", 500_000),
    ("MSFT",  "2024-06-14", 250_000),
]

GREEN_TRADES = [
    ("XOM",  "2020-03-20", 100_000),
    ("CVX",  "2020-03-20", 100_000),
    ("JNJ",  "2020-04-15", 100_000),
    ("PFE",  "2020-11-09", 200_000),
    ("MRNA", "2020-11-09", 200_000),
    ("XOM",  "2021-01-07", 150_000),
    ("SLB",  "2021-06-18", 100_000),
    ("PFE",  "2021-11-26", 150_000),
    ("ABBV", "2022-03-04", 100_000),
    ("XOM",  "2022-06-10", 200_000),
    ("CVX",  "2022-06-10", 100_000),
    ("LLY",  "2023-02-14", 200_000),
    ("PFE",  "2023-06-21", 100_000),
    ("XOM",  "2024-01-19", 150_000),
]

MCCAUL_TRADES = [
    ("GOOGL", "2020-03-18", 500_000),
    ("AMZN",  "2020-03-18", 500_000),
    ("MSFT",  "2020-03-18", 500_000),
    ("META",  "2020-09-03", 250_000),
    ("AAPL",  "2021-02-12", 500_000),
    ("NVDA",  "2021-06-30", 250_000),
    ("META",  "2022-02-04", 500_000),
    ("GOOGL", "2022-05-20", 500_000),
    ("MSFT",  "2022-10-28", 250_000),
    ("AMZN",  "2023-04-28", 500_000),
    ("NVDA",  "2023-05-25", 500_000),
    ("META",  "2023-10-27", 250_000),
    ("AAPL",  "2024-02-16", 500_000),
]

POLITICIANS = {
    "Pelosi": PELOSI_TRADES,
    "Green":  GREEN_TRADES,
    "McCaul": MCCAUL_TRADES,
}

# ─────────────────────────────────────────────
# DOWNLOAD PRICE DATA (once)
# ─────────────────────────────────────────────
ALL_TICKERS = sorted(set(
    [t for t,_,_ in PELOSI_TRADES] +
    [t for t,_,_ in GREEN_TRADES]  +
    [t for t,_,_ in MCCAUL_TRADES] +
    ["VOO"]
))

print(f"Downloading weekly price data for: {ALL_TICKERS} …")
raw_weekly = yf.download(
    ALL_TICKERS,
    start="2019-01-01",
    end="2026-05-28",
    interval="1wk",
    auto_adjust=True,
    progress=False,
)["Close"]
if isinstance(raw_weekly, pd.Series):
    raw_weekly = raw_weekly.to_frame(name=ALL_TICKERS[0])
prices_weekly: pd.DataFrame = raw_weekly.ffill()

print("Downloading daily price data …")
raw_daily = yf.download(
    ALL_TICKERS,
    start="2019-01-01",
    end="2026-05-28",
    interval="1d",
    auto_adjust=True,
    progress=False,
)["Close"]
if isinstance(raw_daily, pd.Series):
    raw_daily = raw_daily.to_frame(name=ALL_TICKERS[0])
prices_daily: pd.DataFrame = raw_daily.ffill()

trading_days = prices_daily.index
print(f"  Weekly bars: {len(prices_weekly)} | Daily bars: {len(prices_daily)}")

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def next_trading_day(target_date: pd.Timestamp) -> pd.Timestamp:
    mask = trading_days >= target_date
    if mask.any():
        return trading_days[mask][0]
    return trading_days[-1]

def next_monday_after(date: pd.Timestamp) -> pd.Timestamp:
    days_ahead = (7 - date.weekday()) % 7
    candidate = date + timedelta(days=days_ahead)
    return next_trading_day(candidate)

def get_price_daily(ticker: str, date: pd.Timestamp) -> float | None:
    if ticker not in prices_daily.columns:
        return None
    col = prices_daily[ticker].dropna()
    mask = col.index >= date
    if not mask.any():
        return None
    return float(col[mask].iloc[0])

def quarter_label(ts: pd.Timestamp) -> str:
    return f"Q{ts.quarter}-{str(ts.year)[2:]}"

def cagr_from_series(s: pd.Series) -> float:
    s = s.dropna()
    if len(s) < 2:
        return 0.0
    n_years = (s.index[-1] - s.index[0]).days / 365.25
    if n_years <= 0:
        return 0.0
    return ((s.iloc[-1] / s.iloc[0]) ** (1 / n_years) - 1) * 100

def max_drawdown(s: pd.Series) -> float:
    s = s.dropna()
    if len(s) < 2:
        return 0.0
    peak = s.cummax()
    dd = (s - peak) / peak * 100
    return float(dd.min())

# ─────────────────────────────────────────────
# BUILD EXECUTION SCHEDULE (once per politician)
# Execution date = trade_date + 30 days, next Monday / trading day
# ─────────────────────────────────────────────
def build_schedule(trades: list) -> list:
    """Returns list of (exec_date, ticker, notional) sorted by exec_date."""
    schedule = []
    for ticker, trade_date_str, notional in trades:
        if ticker not in prices_daily.columns:
            continue
        trade_dt = pd.Timestamp(trade_date_str)
        exec_dt  = next_monday_after(trade_dt + timedelta(days=DISCLOSURE_LAG_DAYS))
        schedule.append((exec_dt, ticker, notional))
    schedule.sort(key=lambda x: x[0])
    return schedule

SCHEDULES = {name: build_schedule(trades) for name, trades in POLITICIANS.items()}

# ─────────────────────────────────────────────
# SIMULATE ONE (start_date, politician) PAIR
# ─────────────────────────────────────────────
def simulate(start_date: pd.Timestamp, schedule: list) -> dict:
    """
    Run the copy strategy from start_date to END_DATE.
    Only trades with exec_date > start_date are included.
    Returns dict with portfolio metrics.
    """
    end_ts = pd.Timestamp(END_DATE)

    # Filter to weekly dates in [start_date, end_date]
    wk_dates = prices_weekly.loc[start_date:end_ts].index
    if len(wk_dates) == 0:
        return {}

    # Trades eligible = exec_date >= wk_dates[0] (first weekly bar on/after start)
    first_wk = wk_dates[0]
    eligible   = [(ed, tk, no) for ed, tk, no in schedule if ed >= first_wk]
    n_total    = len(schedule)
    n_eligible = len(eligible)

    cash = INITIAL_CASH
    holdings: dict[str, float] = {}
    port_values = {}
    mm_weekly = 1 + MM_RATE_ANNUAL / 52

    trade_ptr = 0

    for wk_date in wk_dates:
        # 1. Accrue MM yield
        cash *= mm_weekly

        # 2. Execute trades due this week
        while trade_ptr < len(eligible) and eligible[trade_ptr][0] <= wk_date:
            exec_dt, ticker, notional = eligible[trade_ptr]
            trade_ptr += 1

            # Portfolio value at this moment
            equity = 0.0
            for t, sh in holdings.items():
                if t in prices_weekly.columns:
                    col = prices_weekly[t].loc[:wk_date].dropna()
                    if not col.empty:
                        equity += sh * float(col.iloc[-1])
            port_val  = cash + equity
            max_spend = min(notional, port_val * POSITION_CAP_PCT, cash)

            if max_spend < 1:
                continue

            price = get_price_daily(ticker, exec_dt)
            if price is None or price <= 0:
                continue

            shares_bought = max_spend / price
            holdings[ticker] = holdings.get(ticker, 0.0) + shares_bought
            cash -= max_spend

        # 3. Mark-to-market
        equity = 0.0
        for t, sh in holdings.items():
            if t in prices_weekly.columns and pd.notna(prices_weekly[t].get(wk_date)):
                equity += sh * float(prices_weekly[t].loc[wk_date])
        port_values[wk_date] = cash + equity

    s = pd.Series(port_values)
    if s.empty:
        return {}

    # VOO lump sum benchmark from same start
    voo_col = prices_weekly["VOO"].loc[first_wk:end_ts].dropna()
    voo_buy_price = float(voo_col.iloc[0])
    voo_shares    = INITIAL_CASH / voo_buy_price
    voo_series    = voo_col * voo_shares

    strat_cagr = cagr_from_series(s)
    voo_cagr   = cagr_from_series(voo_series)
    total_ret  = (s.iloc[-1] / s.iloc[0] - 1) * 100

    return {
        "start":       start_date,
        "start_label": quarter_label(start_date),
        "final_value": s.iloc[-1],
        "total_return": total_ret,
        "cagr":        strat_cagr,
        "voo_cagr":    voo_cagr,
        "max_dd":      max_drawdown(s),
        "n_trades":    n_eligible,
        "n_total":     n_total,
        "beats_voo":   strat_cagr > voo_cagr,
        "series":      s,
    }

# ─────────────────────────────────────────────
# RUN ALL (start_date × politician) COMBINATIONS
# ─────────────────────────────────────────────
print(f"\nRunning {len(STARTS)} × {len(POLITICIANS)} = {len(STARTS)*len(POLITICIANS)} simulations …")

results: dict[str, list] = {name: [] for name in POLITICIANS}

for i, start_dt in enumerate(STARTS):
    for name, schedule in SCHEDULES.items():
        r = simulate(start_dt, schedule)
        if r:
            results[name].append(r)
    print(f"  [{i+1:2d}/20] {quarter_label(start_dt)} done")

# ─────────────────────────────────────────────
# PRINT TABLES + COMPUTE ALPHA HALF-LIFE
# ─────────────────────────────────────────────
output_lines = []

def pline(s=""):
    print(s)
    output_lines.append(s)

def alpha_half_life(rows: list) -> str:
    """First quarter where strategy stops beating VOO (and stays under)."""
    last_win = None
    for r in rows:
        if r["beats_voo"]:
            last_win = r["start_label"]
    if last_win is None:
        return "NEVER beats VOO"
    # Find first quarter after which it never wins again
    past_last_win = False
    for r in rows:
        if r["start_label"] == last_win:
            past_last_win = True
            continue
        if past_last_win:
            return r["start_label"]
    return "Beats VOO in all tested quarters"

COL_W = [10, 10, 9, 10, 9, 10]

def hdr():
    h = f"{'Start':<10}  {'Trades':^10}  {'CAGR':^9}  {'VOO CAGR':^10}  {'Wins?':^9}  {'Max DD':^10}"
    return h

def divider_str():
    return "-" * 66

for name, rows in results.items():
    pline()
    pline("=" * 66)
    pline(f"  {name.upper()} — Quarterly Start Date Sensitivity")
    pline("=" * 66)
    pline(hdr())
    pline(divider_str())
    for r in rows:
        trade_str = f"{r['n_trades']}/{r['n_total']}"
        wins_str  = "YES ✓" if r["beats_voo"] else "NO  ✗"
        pline(
            f"{r['start_label']:<10}  {trade_str:^10}  "
            f"{r['cagr']:>6.1f}%   {r['voo_cagr']:>7.1f}%    "
            f"{wins_str:<9}  {r['max_dd']:>6.1f}%"
        )
    pline(divider_str())

    ahl = alpha_half_life(rows)
    wins_count = sum(1 for r in rows if r["beats_voo"])
    pline(f"  Alpha half-life: strategy stops beating VOO from → {ahl}")
    pline(f"  Beats VOO in {wins_count}/{len(rows)} starting quarters")

    # Q1-2022+ analysis
    late_rows = [r for r in rows if r["start"] >= pd.Timestamp("2022-01-01")]
    late_wins  = sum(1 for r in late_rows if r["beats_voo"])
    if late_rows:
        avg_alpha  = np.mean([r["cagr"] - r["voo_cagr"] for r in late_rows])
        pline(f"  Q1-2022 or later: beats VOO {late_wins}/{len(late_rows)} times | avg alpha = {avg_alpha:+.1f}%")

# ─────────────────────────────────────────────
# KEY FINDINGS
# ─────────────────────────────────────────────
pline()
pline("=" * 66)
pline("  KEY FINDINGS")
pline("=" * 66)

for name, rows in results.items():
    early_rows = [r for r in rows if r["start"] < pd.Timestamp("2020-07-01")]
    late_rows  = [r for r in rows if r["start"] >= pd.Timestamp("2022-01-01")]

    early_alpha = np.mean([r["cagr"] - r["voo_cagr"] for r in early_rows]) if early_rows else 0
    late_alpha  = np.mean([r["cagr"] - r["voo_cagr"] for r in late_rows])  if late_rows  else 0

    pline(f"\n  {name}:")
    pline(f"    Early starts (Q1/Q2-2020) avg alpha vs VOO : {early_alpha:+.1f}%")
    pline(f"    Late starts  (Q1-2022+)   avg alpha vs VOO : {late_alpha:+.1f}%")

    never_beats = all(not r["beats_voo"] for r in rows)
    if never_beats:
        pline(f"    → Strategy NEVER beats VOO for any starting quarter")
    else:
        ahl = alpha_half_life(rows)
        pline(f"    → Alpha half-life cutoff: {ahl}")

pline()

# ─────────────────────────────────────────────
# SAVE TEXT SUMMARY
# ─────────────────────────────────────────────
txt_path = "/home/ubuntu/projects/investor/congressional_quarterly_summary.txt"
with open(txt_path, "w") as f:
    f.write("\n".join(output_lines))
print(f"\nSummary saved → {txt_path}")

# ─────────────────────────────────────────────
# PLOT: 3 subplots, bar chart of CAGR per quarter
# ─────────────────────────────────────────────
fig, axes = plt.subplots(1, 3, figsize=(20, 7), sharey=False)
fig.suptitle(
    "Congressional Copy Strategy — CAGR by Starting Quarter\n"
    "Green bars = beats VOO | Red bars = underperforms VOO",
    fontsize=13, fontweight="bold", y=1.01
)

for ax, (name, rows) in zip(axes, results.items()):
    labels    = [r["start_label"] for r in rows]
    cagrs     = [r["cagr"] for r in rows]
    voo_cagrs = [r["voo_cagr"] for r in rows]
    colors    = ["#2ca02c" if r["beats_voo"] else "#d62728" for r in rows]
    n_trades  = [r["n_trades"] for r in rows]

    x = np.arange(len(labels))
    bars = ax.bar(x, cagrs, color=colors, alpha=0.82, edgecolor="white", linewidth=0.5, zorder=3)

    # VOO CAGR as a step/scatter overlay — use unique VOO CAGRs per bar
    for i, (xi, vc) in enumerate(zip(x, voo_cagrs)):
        ax.plot([xi - 0.4, xi + 0.4], [vc, vc], color="#ff7f0e", linewidth=2.0, zorder=4)

    # Annotate trade count above/below each bar
    for i, (bar, n) in enumerate(zip(bars, n_trades)):
        ypos  = bar.get_height()
        va    = "bottom" if ypos >= 0 else "top"
        yoff  = 0.3 if ypos >= 0 else -0.3
        ax.text(bar.get_x() + bar.get_width() / 2, ypos + yoff,
                f"{n}t", ha="center", va=va, fontsize=6.5, color="#333333")

    ax.axhline(0, color="black", linewidth=0.6, linestyle=":")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=7.5)
    ax.set_title(name, fontsize=12, fontweight="bold")
    ax.set_ylabel("CAGR (%)")
    ax.grid(True, axis="y", alpha=0.3, zorder=0)
    ax.set_xlabel("Start Quarter")

    # Legend
    green_patch  = mpatches.Patch(color="#2ca02c", alpha=0.82, label="Strategy CAGR (beats VOO)")
    red_patch    = mpatches.Patch(color="#d62728", alpha=0.82, label="Strategy CAGR (lags VOO)")
    voo_line     = plt.Line2D([0], [0], color="#ff7f0e", linewidth=2, label="VOO CAGR (same start)")
    ax.legend(handles=[green_patch, red_patch, voo_line], fontsize=7, loc="upper right")

plt.tight_layout()
png_path = "/home/ubuntu/projects/investor/congressional_quarterly_starts.png"
plt.savefig(png_path, dpi=150, bbox_inches="tight")
plt.close()
print(f"Chart saved → {png_path}")
