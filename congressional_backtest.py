"""
Congressional Trader Copy Strategy Backtest
Compares copying disclosed trades of Pelosi, Green, McCaul
vs. VOO Lump Sum, VOO DCA, and a reference Dip-Tranche line.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────
START_DATE    = "2020-01-02"
END_DATE      = "2026-05-27"
INITIAL_CASH  = 1_000_000.0
MM_RATE_ANNUAL = 0.04          # 4 % money-market on uninvested cash
WEEKS_PER_YEAR = 52
RISK_FREE_WEEKLY = MM_RATE_ANNUAL / WEEKS_PER_YEAR
DISCLOSURE_LAG_DAYS = 30       # simulate typical late-filer 30-day lag
POSITION_CAP_PCT    = 0.15     # max 15% of portfolio per trade

# ─────────────────────────────────────────────
# HARD-CODED TRADE DATA
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

# ─────────────────────────────────────────────
# DOWNLOAD PRICE DATA
# ─────────────────────────────────────────────
all_tickers = sorted(set(
    [t for t,_,_ in PELOSI_TRADES] +
    [t for t,_,_ in GREEN_TRADES]  +
    [t for t,_,_ in MCCAUL_TRADES] +
    ["VOO"]
))

print(f"Downloading weekly price data for: {all_tickers} …")
raw = yf.download(
    all_tickers,
    start="2020-01-01",
    end="2026-05-28",
    interval="1wk",
    auto_adjust=True,
    progress=False,
)["Close"]

# If only one ticker yfinance returns a Series — normalise to DataFrame
if isinstance(raw, pd.Series):
    raw = raw.to_frame(name=all_tickers[0])

# Forward-fill so we have a price on every weekly bar
prices_weekly: pd.DataFrame = raw.ffill()

# Also get daily closes (needed for accurate cash accrual date handling)
print("Downloading daily price data …")
raw_daily = yf.download(
    all_tickers,
    start="2020-01-01",
    end="2026-05-28",
    interval="1d",
    auto_adjust=True,
    progress=False,
)["Close"]
if isinstance(raw_daily, pd.Series):
    raw_daily = raw_daily.to_frame(name=all_tickers[0])
prices_daily: pd.DataFrame = raw_daily.ffill()

# Note which tickers had data issues
failed_tickers = [t for t in all_tickers if t not in prices_weekly.columns or prices_weekly[t].isna().all()]
if failed_tickers:
    print(f"  WARNING — no data for: {failed_tickers}")
available_tickers = [t for t in all_tickers if t not in failed_tickers]

print(f"  Data loaded. Weekly bars: {len(prices_weekly)}, Daily bars: {len(prices_daily)}")

# ─────────────────────────────────────────────
# HELPER UTILITIES
# ─────────────────────────────────────────────
trading_days = prices_daily.index  # DatetimeIndex of all trading days in data

def next_trading_day(target_date: pd.Timestamp) -> pd.Timestamp:
    """Return target_date itself if a trading day, else the next one."""
    mask = trading_days >= target_date
    if mask.any():
        return trading_days[mask][0]
    return trading_days[-1]

def next_monday_after(date: pd.Timestamp) -> pd.Timestamp:
    """Return the Monday >= date (i.e., next Monday or same day if already Monday)."""
    days_ahead = (7 - date.weekday()) % 7   # 0 if already Monday
    candidate = date + timedelta(days=days_ahead)
    return next_trading_day(candidate)

def weekly_index_from(start: pd.Timestamp, prices_wk: pd.DataFrame) -> pd.DatetimeIndex:
    return prices_wk.loc[start:].index

def get_price(ticker: str, date: pd.Timestamp, frame: pd.DataFrame) -> float | None:
    """Get adjusted close for ticker on or after date."""
    if ticker not in frame.columns:
        return None
    col = frame[ticker].dropna()
    mask = col.index >= date
    if not mask.any():
        return None
    return float(col[mask].iloc[0])

def compute_metrics(portfolio_series: pd.Series, label: str) -> dict:
    """Compute performance metrics from a weekly portfolio value series."""
    s = portfolio_series.dropna()
    if len(s) < 2:
        return {}

    total_return = (s.iloc[-1] / s.iloc[0] - 1) * 100
    n_years = (s.index[-1] - s.index[0]).days / 365.25
    cagr = ((s.iloc[-1] / s.iloc[0]) ** (1 / n_years) - 1) * 100 if n_years > 0 else 0

    weekly_ret = s.pct_change().dropna()
    excess     = weekly_ret - RISK_FREE_WEEKLY
    sharpe     = (excess.mean() / excess.std() * np.sqrt(WEEKS_PER_YEAR)) if excess.std() > 0 else 0

    running_max = s.cummax()
    drawdown    = (s - running_max) / running_max * 100
    max_dd      = drawdown.min()

    return {
        "Strategy":      label,
        "Final Value":   f"${s.iloc[-1]:,.0f}",
        "Total Return":  f"{total_return:.1f}%",
        "CAGR":          f"{cagr:.1f}%",
        "Max Drawdown":  f"{max_dd:.1f}%",
        "Sharpe":        f"{sharpe:.2f}",
        "_final":        s.iloc[-1],
        "_cagr":         cagr,
        "_max_dd":       max_dd,
        "_sharpe":       sharpe,
        "_series":       s,
    }

# ─────────────────────────────────────────────
# CONGRESSIONAL COPY STRATEGY
# ─────────────────────────────────────────────
def run_congressional_strategy(trades: list, label: str) -> pd.Series:
    """
    Simulate a buy-and-hold congressional copy portfolio.
    Returns a weekly portfolio value Series.
    """
    # Build execution schedule: (execution_date, ticker, notional)
    schedule = []
    for ticker, trade_date_str, notional in trades:
        if ticker not in available_tickers:
            print(f"  [{label}] Skipping {ticker} — no price data")
            continue
        trade_dt = pd.Timestamp(trade_date_str)
        # Add disclosure lag then find next Monday/trading day
        exec_dt  = next_monday_after(trade_dt + timedelta(days=DISCLOSURE_LAG_DAYS))
        schedule.append((exec_dt, ticker, notional))
    schedule.sort(key=lambda x: x[0])

    # Simulate on weekly index
    weekly_dates = prices_weekly.loc[START_DATE:END_DATE].index
    cash = INITIAL_CASH
    holdings: dict[str, float] = {}   # ticker -> shares held
    port_values = {}

    # Weekly money-market factor
    mm_weekly = (1 + MM_RATE_ANNUAL / 52)

    # Index upcoming trades
    trade_ptr = 0

    for wk_date in weekly_dates:
        # Accrue money-market on cash (weekly approximation)
        cash *= mm_weekly

        # Execute any trades due this week (on or before this weekly bar)
        while trade_ptr < len(schedule) and schedule[trade_ptr][0] <= wk_date:
            exec_dt, ticker, notional = schedule[trade_ptr]
            trade_ptr += 1

            # Current portfolio value at this moment (approx using this weekly close)
            equity = sum(
                shares * float(prices_weekly[t].loc[:wk_date].dropna().iloc[-1])
                for t, shares in holdings.items()
                if t in prices_weekly.columns and not prices_weekly[t].loc[:wk_date].dropna().empty
            )
            port_val = cash + equity
            max_spend = min(notional, port_val * POSITION_CAP_PCT, cash)

            if max_spend < 1:
                continue

            price = get_price(ticker, exec_dt, prices_daily)
            if price is None or price <= 0:
                print(f"  [{label}] No price for {ticker} on {exec_dt.date()} — skipping")
                continue

            shares_bought = max_spend / price
            holdings[ticker] = holdings.get(ticker, 0.0) + shares_bought
            cash -= max_spend

        # Mark-to-market portfolio value
        equity = sum(
            shares * float(prices_weekly[t].loc[wk_date])
            for t, shares in holdings.items()
            if t in prices_weekly.columns and pd.notna(prices_weekly[t].loc[wk_date])
        )
        port_values[wk_date] = cash + equity

    series = pd.Series(port_values, name=label)
    return series

# ─────────────────────────────────────────────
# BENCHMARK: VOO LUMP SUM
# ─────────────────────────────────────────────
def run_voo_lumpsum() -> pd.Series:
    weekly_dates = prices_weekly.loc[START_DATE:END_DATE].index
    voo = prices_weekly["VOO"].loc[START_DATE:END_DATE].dropna()
    buy_price = float(voo.iloc[0])
    shares = INITIAL_CASH / buy_price
    port = (voo * shares).reindex(weekly_dates).ffill()
    port.name = "VOO Lump Sum"
    return port

# ─────────────────────────────────────────────
# BENCHMARK: VOO DCA (spread $1M equally over 156 weeks)
# ─────────────────────────────────────────────
def run_voo_dca() -> pd.Series:
    weekly_dates = prices_weekly.loc[START_DATE:END_DATE].index
    voo = prices_weekly["VOO"].loc[START_DATE:END_DATE].dropna()
    n_weeks = len(weekly_dates)
    weekly_invest = INITIAL_CASH / min(n_weeks, 156)

    cash = INITIAL_CASH
    shares = 0.0
    mm_weekly = (1 + MM_RATE_ANNUAL / 52)
    port_values = {}

    for i, wk_date in enumerate(weekly_dates):
        cash *= mm_weekly
        if wk_date in voo.index and i < 156:
            price = float(voo.loc[wk_date])
            invest = min(weekly_invest, cash)
            if invest > 0 and price > 0:
                shares += invest / price
                cash   -= invest
        if wk_date in voo.index:
            equity = shares * float(voo.loc[wk_date])
        else:
            equity = 0.0
        port_values[wk_date] = cash + equity

    s = pd.Series(port_values, name="VOO DCA")
    return s

# ─────────────────────────────────────────────
# RUN ALL STRATEGIES
# ─────────────────────────────────────────────
print("\nRunning strategies …")
pelosi_series = run_congressional_strategy(PELOSI_TRADES, "Pelosi")
green_series  = run_congressional_strategy(GREEN_TRADES,  "Green")
mccaul_series = run_congressional_strategy(MCCAUL_TRADES, "McCaul")
voo_ls_series = run_voo_lumpsum()
voo_dca_series= run_voo_dca()

# Dip-Tranche reference (hard-coded from prior analysis)
DIP_TRANCHE_CAGR   = 15.1   # %
DIP_TRANCHE_MAX_DD = -22.5  # %
# Build synthetic series at CAGR 15.1% for chart
_weeks = pd.date_range(start=START_DATE, end=END_DATE, freq="W-FRI")
_n = len(_weeks)
_weekly_growth = (1 + DIP_TRANCHE_CAGR / 100) ** (1 / 52)
dip_series = pd.Series(
    INITIAL_CASH * _weekly_growth ** np.arange(_n),
    index=_weeks,
    name="Dip-Tranche (ref)"
)

# ─────────────────────────────────────────────
# COMPUTE METRICS
# ─────────────────────────────────────────────
all_metrics = []
for series, lbl in [
    (pelosi_series,  "Pelosi"),
    (green_series,   "Green"),
    (mccaul_series,  "McCaul"),
    (voo_ls_series,  "VOO Lump Sum"),
    (voo_dca_series, "VOO DCA"),
    (dip_series,     "Dip-Tranche (ref)"),
]:
    m = compute_metrics(series, lbl)
    if m:
        all_metrics.append(m)
        # Override Dip-Tranche stats with hard-coded reference values
        if lbl == "Dip-Tranche (ref)":
            m["Max Drawdown"] = f"{DIP_TRANCHE_MAX_DD:.1f}%"
            m["Sharpe"]       = "~0.70 (ref)"   # approximate, not re-computed

# ─────────────────────────────────────────────
# PRINT METRICS TABLE
# ─────────────────────────────────────────────
cols = ["Strategy", "Final Value", "Total Return", "CAGR", "Max Drawdown", "Sharpe"]
col_w = [22, 16, 14, 10, 14, 8]

def row_str(values):
    return "  ".join(str(v).ljust(w) for v, w in zip(values, col_w))

header = row_str(cols)
divider = "-" * len(header)

print("\n" + "=" * len(header))
print(" CONGRESSIONAL TRADE COPY BACKTEST  |  2020-01-02 → 2026-05-27")
print("=" * len(header))
print(header)
print(divider)
for m in all_metrics:
    print(row_str([m[c] for c in cols]))
print(divider)
print("* Risk-free rate: 4% annual | Uninvested cash accrues at MM rate")
print("* Disclosure lag: 30 calendar days, execute on next Monday/trading day")
print("* Dip-Tranche is a reference line (CAGR/Max-DD from prior analysis)\n")

# ─────────────────────────────────────────────
# DRAWDOWN HELPER
# ─────────────────────────────────────────────
def drawdown_series(s: pd.Series) -> pd.Series:
    peak = s.cummax()
    return (s - peak) / peak * 100

# ─────────────────────────────────────────────
# PLOT
# ─────────────────────────────────────────────
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True,
                                gridspec_kw={"height_ratios": [2, 1]})
fig.suptitle("Congressional Trade Copy Backtest  (2020 – May 2026)", fontsize=14, fontweight="bold")

COLORS = {
    "Pelosi":           "#1f77b4",
    "Green":            "#2ca02c",
    "McCaul":           "#d62728",
    "VOO Lump Sum":     "#ff7f0e",
    "VOO DCA":          "#9467bd",
    "Dip-Tranche (ref)":"#8c564b",
}
STYLES = {
    "Dip-Tranche (ref)": "--",
}

strategies = [
    (pelosi_series,  "Pelosi"),
    (green_series,   "Green"),
    (mccaul_series,  "McCaul"),
    (voo_ls_series,  "VOO Lump Sum"),
    (voo_dca_series, "VOO DCA"),
    (dip_series,     "Dip-Tranche (ref)"),
]

# Normalise to $1M start
for series, lbl in strategies:
    s = series.dropna()
    if s.empty:
        continue
    norm = s / s.iloc[0] * INITIAL_CASH
    ls = STYLES.get(lbl, "-")
    ax1.plot(norm.index, norm / 1e6, label=lbl, color=COLORS.get(lbl, None),
             linestyle=ls, linewidth=1.8)

ax1.axhline(1.0, color="gray", linewidth=0.6, linestyle=":")
ax1.set_ylabel("Portfolio Value ($M)", fontsize=11)
ax1.yaxis.set_major_formatter(mticker.FormatStrFormatter("$%.1fM"))
ax1.legend(fontsize=9, loc="upper left")
ax1.grid(True, alpha=0.3)
ax1.set_title("Portfolio Growth (starting from $1M)", fontsize=11)

# Bottom: drawdown for congressional strategies + VOO LS only (not dip-tranche reference)
dd_strategies = [
    (pelosi_series,  "Pelosi"),
    (green_series,   "Green"),
    (mccaul_series,  "McCaul"),
    (voo_ls_series,  "VOO Lump Sum"),
]
for series, lbl in dd_strategies:
    s = series.dropna()
    if s.empty:
        continue
    dd = drawdown_series(s)
    ax2.plot(dd.index, dd, label=lbl, color=COLORS.get(lbl, None), linewidth=1.5)

ax2.axhline(DIP_TRANCHE_MAX_DD, color=COLORS["Dip-Tranche (ref)"], linestyle="--",
            linewidth=1.2, label=f"Dip-Tranche max DD ({DIP_TRANCHE_MAX_DD}%)")
ax2.fill_between(pelosi_series.dropna().index, drawdown_series(pelosi_series.dropna()), 0,
                 alpha=0.08, color=COLORS["Pelosi"])
ax2.set_ylabel("Drawdown from Peak (%)", fontsize=11)
ax2.set_xlabel("Date", fontsize=11)
ax2.legend(fontsize=9, loc="lower right")
ax2.grid(True, alpha=0.3)
ax2.set_title("Drawdown from Peak", fontsize=11)

plt.tight_layout()
out_png = "/home/ubuntu/projects/investor/congressional_backtest.png"
plt.savefig(out_png, dpi=150, bbox_inches="tight")
plt.close()
print(f"Chart saved → {out_png}")

# ─────────────────────────────────────────────
# SAVE TEXT SUMMARY
# ─────────────────────────────────────────────
out_txt = "/home/ubuntu/projects/investor/congressional_summary.txt"
lines = [
    "CONGRESSIONAL TRADE COPY BACKTEST  |  2020-01-02 → 2026-05-27",
    "=" * len(header),
    header,
    divider,
]
for m in all_metrics:
    lines.append(row_str([m[c] for c in cols]))
lines += [
    divider,
    "* Risk-free rate: 4% annual | Uninvested cash accrues at MM rate",
    "* Disclosure lag: 30 calendar days, execute on next Monday/trading day",
    "* Dip-Tranche is a reference line (CAGR/Max-DD from prior analysis)",
    "",
    "DATA NOTES:",
    f"  Tickers downloaded: {available_tickers}",
    f"  Failed/skipped: {failed_tickers if failed_tickers else 'None'}",
]
with open(out_txt, "w") as f:
    f.write("\n".join(lines))
print(f"Summary saved → {out_txt}")

# ─────────────────────────────────────────────
# KEY FINDINGS
# ─────────────────────────────────────────────
print("\n─── KEY FINDINGS ───")
ranked = sorted(all_metrics, key=lambda m: m["_cagr"], reverse=True)
for i, m in enumerate(ranked, 1):
    print(f"  {i}. {m['Strategy']:22s}  CAGR={m['CAGR']:>7}  Final={m['Final Value']:>14}  Sharpe={m['Sharpe']}")
print()
