#!/usr/bin/env python3
"""
Quarterly-Starts Backtest
==========================
Tests the dip-tranche strategy starting on the first trading day of each quarter
from Q1-2020 through Q4-2024 (20 starting points), all ending on 2026-05-27.

Answers: "does lump-sum always win, or only if you happened to start at a lucky moment?"
"""

import sys
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

try:
    import yfinance as yf
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "yfinance", "-q"])
    import yfinance as yf

# ─────────────────────────────  CONFIG  ─────────────────────────────────────
PORTFOLIO        = 1_000_000
DATA_START       = "2020-01-01"
END_DATE         = "2026-05-27"
DCA_MONTHS       = 18
MM_YIELD_ANNUAL  = 0.04
COOLDOWN_WEEKS   = 3
MAX_REARMS_PER_YEAR = 2

LUMP_PCT  = 0.50
DCA_PCT   = 0.30
RES_PCT   = 0.20

TIER1_SHARE = 0.20
TIER2_SHARE = 0.30
TIER3_SHARE = 0.50

BASE_T1    = [-0.070, -0.085, -0.100]
BASE_T2    = [-0.120, -0.140, -0.160]
BASE_T3    = [-0.200, -0.250, -0.300]
BASE_REARM = -0.050

SYMBOLS = {
    "VOO":  {"name": "Vanguard S&P 500 ETF",           "mult": 1.0,  "color": "#4f81bd"},
    "QQQ":  {"name": "Invesco Nasdaq-100 ETF",          "mult": 1.40, "color": "#c0504d"},
    "VXUS": {"name": "Vanguard Total International ETF","mult": 1.0,  "color": "#9bbb59"},
}

# 20 quarter start dates (nominal — will snap to first available trading day)
QUARTER_STARTS = [
    "2020-01-01", "2020-04-01", "2020-07-01", "2020-10-01",
    "2021-01-01", "2021-04-01", "2021-07-01", "2021-10-01",
    "2022-01-01", "2022-04-01", "2022-07-01", "2022-10-01",
    "2023-01-01", "2023-04-01", "2023-07-01", "2023-10-01",
    "2024-01-01", "2024-04-01", "2024-07-01", "2024-10-01",
]

QUARTER_LABELS = [
    "Q1-20","Q2-20","Q3-20","Q4-20",
    "Q1-21","Q2-21","Q3-21","Q4-21",
    "Q1-22","Q2-22","Q3-22","Q4-22",
    "Q1-23","Q2-23","Q3-23","Q4-23",
    "Q1-24","Q2-24","Q3-24","Q4-24",
]


def scaled_triggers(mult: float) -> dict:
    return {
        "t1": [v * mult for v in BASE_T1],
        "t2": [v * mult for v in BASE_T2],
        "t3": [v * mult for v in BASE_T3],
        "t1_weeks": 2,
        "t2_weeks": 3,
        "t3_weeks": 4,
        "rearm": BASE_REARM * mult,
    }


# ─────────────────────────────  DATA  ───────────────────────────────────────
def fetch_symbol(symbol: str) -> pd.DataFrame:
    """Download full weekly data once per symbol."""
    print(f"  Downloading {symbol} …", end=" ", flush=True)
    df = yf.Ticker(symbol).history(
        start=DATA_START, end="2026-05-28", interval="1wk", auto_adjust=True
    )
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df = df[["Close"]].dropna()
    print(f"{len(df)} weekly bars")
    return df


def slice_df(df: pd.DataFrame, start_str: str) -> pd.DataFrame:
    """Return a slice of df from the first available bar >= start_str to END_DATE."""
    start_dt = pd.Timestamp(start_str)
    end_dt   = pd.Timestamp(END_DATE)
    mask     = (df.index >= start_dt) & (df.index <= end_dt)
    sliced   = df[mask]
    if sliced.empty:
        raise ValueError(f"No data for start={start_str}")
    return sliced


# ─────────────────────────────  ENGINE  ─────────────────────────────────────
def run_strategy(df_slice: pd.DataFrame, mult: float) -> dict:
    closes  = df_slice["Close"].values
    dates   = df_slice.index
    n       = len(closes)
    trg     = scaled_triggers(mult)

    lump_amt   = PORTFOLIO * LUMP_PCT
    dca_total  = PORTFOLIO * DCA_PCT
    res_total  = PORTFOLIO * RES_PCT
    dca_weekly = dca_total / (DCA_MONTHS * 4.33)

    t1_amt = res_total * TIER1_SHARE
    t2_amt = res_total * TIER2_SHARE
    t3_amt = res_total * TIER3_SHARE

    tranche_usd = {}
    for tier, pool in [(1, t1_amt), (2, t2_amt), (3, t3_amt)]:
        for sub in range(4):
            tranche_usd[(tier, sub)] = pool / 4.0

    shares    = lump_amt / closes[0]
    res_cash  = res_total
    dca_cash  = dca_total
    fired     = set()
    tier_bar  = {}
    last_buy  = -COOLDOWN_WEEKS
    rearms_yr = 0
    cur_year  = dates[0].year
    mm_weekly = (1 + MM_YIELD_ANNUAL) ** (1 / 52) - 1

    portfolio_vals = np.zeros(n)
    dca_end = min(int(DCA_MONTHS * 4.33), n)

    for i, (date, price) in enumerate(zip(dates, closes)):
        yr = date.year
        if yr != cur_year:
            cur_year  = yr
            rearms_yr = 0

        # 52-week high: rolling only within this window (no look-back before start)
        h52 = closes[max(0, i - 52): i + 1].max()
        dd  = (price - h52) / h52

        res_cash *= (1 + mm_weekly)

        if 0 < i < dca_end and dca_cash > 0:
            buy       = min(dca_weekly, dca_cash)
            shares   += buy / price
            dca_cash -= buy

        if dd > trg["rearm"] and fired and rearms_yr < MAX_REARMS_PER_YEAR:
            fired     = set()
            tier_bar  = {}
            rearms_yr += 1

        def fire(tier, sub):
            nonlocal res_cash, shares, last_buy
            key = (tier, sub)
            if key in fired or res_cash < 1:
                return False
            amt = min(tranche_usd[key], res_cash)
            shares   += amt / price
            res_cash -= amt
            fired.add(key)
            last_buy  = i
            return True

        ok = (i - last_buy) >= COOLDOWN_WEEKS

        for sub_i, thr in enumerate(trg["t1"]):
            if ok and dd <= thr:
                if fire(1, sub_i):
                    ok = False
                    tier_bar.setdefault(1, i)

        if 1 in tier_bar and ok:
            if (i - tier_bar[1]) >= trg["t1_weeks"] and dd <= trg["t1"][0]:
                if fire(1, 3):
                    ok = False

        for sub_i, thr in enumerate(trg["t2"]):
            if ok and dd <= thr:
                if fire(2, sub_i):
                    ok = False
                    tier_bar.setdefault(2, i)

        if 2 in tier_bar and ok:
            if (i - tier_bar[2]) >= trg["t2_weeks"] and dd <= trg["t2"][0]:
                if fire(2, 3):
                    ok = False

        for sub_i, thr in enumerate(trg["t3"]):
            if ok and dd <= thr:
                if fire(3, sub_i):
                    ok = False
                    tier_bar.setdefault(3, i)

        if 3 in tier_bar and ok:
            if (i - tier_bar[3]) >= trg["t3_weeks"] and dd <= trg["t3"][0]:
                fire(3, 3)

        portfolio_vals[i] = shares * price + res_cash + dca_cash

    return dict(portfolio=portfolio_vals, dates=dates)


def run_lumpsum(df_slice: pd.DataFrame) -> np.ndarray:
    closes = df_slice["Close"].values
    return (PORTFOLIO / closes[0]) * closes


def run_dca(df_slice: pd.DataFrame) -> np.ndarray:
    closes  = df_slice["Close"].values
    n       = len(closes)
    n_weeks = min(int(DCA_MONTHS * 4.33), n)
    weekly  = PORTFOLIO / n_weeks
    shares, cash = 0.0, float(PORTFOLIO)
    out = np.zeros(n)
    for i, price in enumerate(closes):
        if i < n_weeks and cash > 0:
            buy    = min(weekly, cash)
            shares += buy / price
            cash  -= buy
        out[i] = shares * price + cash
    return out


def calc_metrics(vals: np.ndarray, dates) -> dict:
    yrs      = (dates[-1] - dates[0]).days / 365.25
    end_val  = vals[-1]
    tot_ret  = (end_val - PORTFOLIO) / PORTFOLIO
    cagr     = (end_val / PORTFOLIO) ** (1 / max(yrs, 1e-6)) - 1
    run_max  = np.maximum.accumulate(vals)
    max_dd   = ((vals - run_max) / run_max).min()
    return dict(end=end_val, total_ret=tot_ret, cagr=cagr, max_dd=max_dd, yrs=yrs)


# ─────────────────────────────  RUN ALL QUARTERS  ───────────────────────────
def run_all_quarters(df: pd.DataFrame, mult: float) -> list[dict]:
    rows = []
    for qs, ql in zip(QUARTER_STARTS, QUARTER_LABELS):
        try:
            sl   = slice_df(df, qs)
        except ValueError:
            continue
        s_res  = run_strategy(sl, mult)
        l_vals = run_lumpsum(sl)
        d_vals = run_dca(sl)

        sm = calc_metrics(s_res["portfolio"], sl.index)
        lm = calc_metrics(l_vals,             sl.index)
        dm = calc_metrics(d_vals,             sl.index)

        # Who wins?
        best_end = max(sm["end"], lm["end"], dm["end"])
        if sm["end"] == best_end:
            winner = "Strategy"
        elif lm["end"] == best_end:
            winner = "Lump Sum"
        else:
            winner = "DCA"

        rows.append(dict(
            label=ql, start=sl.index[0].date(),
            s_cagr=sm["cagr"], s_ret=sm["total_ret"], s_end=sm["end"], s_dd=sm["max_dd"],
            l_cagr=lm["cagr"], l_ret=lm["total_ret"], l_end=lm["end"], l_dd=lm["max_dd"],
            d_cagr=dm["cagr"], d_ret=dm["total_ret"], d_end=dm["end"], d_dd=dm["max_dd"],
            winner=winner,
            cagr_diff=sm["cagr"] - lm["cagr"],   # positive = strategy better
            ret_diff=sm["total_ret"] - lm["total_ret"],
            yrs=sm["yrs"],
        ))
    return rows


# ─────────────────────────────  PRINT TABLE  ────────────────────────────────
def print_table(symbol: str, rows: list[dict]):
    hdr = (f"\n{'═'*100}\n"
           f"  {symbol} — Quarterly Starting-Date Backtest  |  All runs end {END_DATE}\n"
           f"{'─'*100}\n"
           f"  {'Quarter':<8} {'Start':<12} "
           f"{'S-CAGR':>8} {'S-Ret%':>8} {'S-EndVal':>11} {'S-MaxDD':>8}  "
           f"{'L-CAGR':>8} {'L-Ret%':>8} {'L-EndVal':>11}  "
           f"{'D-CAGR':>8}  {'Winner':<10}\n"
           f"{'─'*100}")
    print(hdr)
    for r in rows:
        win_flag = "  ◄" if r["winner"] == "Strategy" else ""
        print(
            f"  {r['label']:<8} {str(r['start']):<12} "
            f"{r['s_cagr']:>8.2%} {r['s_ret']:>8.1%} ${r['s_end']:>10,.0f} {r['s_dd']:>8.1%}  "
            f"{r['l_cagr']:>8.2%} {r['l_ret']:>8.1%} ${r['l_end']:>10,.0f}  "
            f"{r['d_cagr']:>8.2%}  {r['winner']:<10}{win_flag}"
        )
    print(f"{'═'*100}")


# ─────────────────────────────  SUMMARY  ────────────────────────────────────
def print_summary(all_symbol_rows: dict):
    print(f"\n{'═'*80}")
    print("  CROSS-SYMBOL SUMMARY")
    print(f"{'─'*80}")
    print(f"  {'Symbol':<8} {'Strategy':>10} {'Lump Sum':>10} {'DCA':>8} "
          f"{'Avg CAGR Diff (S-L)':>22} {'Avg S-CAGR':>12}")
    print(f"{'─'*80}")
    for sym, rows in all_symbol_rows.items():
        n_strat = sum(1 for r in rows if r["winner"] == "Strategy")
        n_lump  = sum(1 for r in rows if r["winner"] == "Lump Sum")
        n_dca   = sum(1 for r in rows if r["winner"] == "DCA")
        avg_diff = np.mean([r["cagr_diff"] for r in rows])
        avg_s    = np.mean([r["s_cagr"]    for r in rows])
        print(f"  {sym:<8} {n_strat:>10} {n_lump:>10} {n_dca:>8} "
              f"{avg_diff:>22.2%} {avg_s:>12.2%}")
    print(f"{'═'*80}")

    # Bear-start vs bull-start breakdown
    bear_starts = {"Q1-20","Q2-20","Q1-22","Q2-22","Q3-22"}
    print(f"\n  Bear-start quarters (COVID crash / 2022 bear): {', '.join(sorted(bear_starts))}")
    for sym, rows in all_symbol_rows.items():
        bear_rows = [r for r in rows if r["label"] in bear_starts]
        bull_rows = [r for r in rows if r["label"] not in bear_starts]
        b_wins = sum(1 for r in bear_rows if r["winner"] == "Strategy")
        u_wins = sum(1 for r in bull_rows if r["winner"] == "Strategy")
        print(f"  {sym}: Strategy wins {b_wins}/{len(bear_rows)} bear-start quarters, "
              f"{u_wins}/{len(bull_rows)} non-bear-start quarters")
    print(f"{'─'*80}")


# ─────────────────────────────  CHART  ──────────────────────────────────────
def plot_symbol(symbol: str, cfg: dict, rows: list[dict]):
    labels   = [r["label"] for r in rows]
    x        = np.arange(len(labels))
    s_ret    = np.array([r["s_ret"]    * 100 for r in rows])
    l_ret    = np.array([r["l_ret"]    * 100 for r in rows])
    d_ret    = np.array([r["d_ret"]    * 100 for r in rows])
    s_cagr   = np.array([r["s_cagr"]  * 100 for r in rows])
    l_cagr   = np.array([r["l_cagr"]  * 100 for r in rows])
    diff     = np.array([r["cagr_diff"]* 100 for r in rows])

    fig, axes = plt.subplots(3, 1, figsize=(16, 14))
    fig.suptitle(
        f"{symbol} — {cfg['name']}\nStrategy Win Rate by Starting Quarter  |  End date: {END_DATE}",
        fontsize=13, fontweight="bold"
    )

    # ── Panel 1: Total Return % lines ───────────────────────────────────
    ax = axes[0]
    ax.plot(x, s_ret, color="#1f77b4",  linewidth=2.2, marker="o", markersize=5, label="Strategy")
    ax.plot(x, l_ret, color="#ff7f0e",  linewidth=1.8, marker="s", markersize=5,
            linestyle="--", label="Lump Sum")
    ax.plot(x, d_ret, color="#2ca02c",  linewidth=1.5, marker="^", markersize=5,
            linestyle="-.", label="DCA 18m")

    # Shade regions
    ax.fill_between(x, s_ret, l_ret,
                    where=(s_ret >= l_ret), interpolate=True,
                    color="#1f77b4", alpha=0.15, label="Strategy > Lump Sum")
    ax.fill_between(x, s_ret, l_ret,
                    where=(s_ret < l_ret),  interpolate=True,
                    color="#ff7f0e", alpha=0.15, label="Lump Sum > Strategy")

    ax.axhline(0, color="black", linewidth=0.7, linestyle=":")
    ax.set_ylabel("Total Return (%)", fontsize=10)
    ax.set_title("Total Return % by Starting Quarter", fontsize=10)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(True, alpha=0.25)

    # ── Panel 2: CAGR grouped bars ───────────────────────────────────────
    ax = axes[1]
    width = 0.35
    bar_colors_s = ["#2ca02c" if diff[i] >= 0 else "#d62728" for i in range(len(x))]
    bar_colors_l = ["#aec7e8"] * len(x)

    bars_l = ax.bar(x - width/2, l_cagr, width, color=bar_colors_l,
                    label="Lump Sum", edgecolor="white", linewidth=0.5)
    bars_s = ax.bar(x + width/2, s_cagr, width, color=bar_colors_s,
                    label="Strategy (green=wins, red=loses)", edgecolor="white", linewidth=0.5)

    ax.axhline(0, color="black", linewidth=0.7)
    ax.set_ylabel("CAGR (%)", fontsize=10)
    ax.set_title("CAGR by Starting Quarter — Grouped Bars", fontsize=10)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.25, axis="y")

    # ── Panel 3: CAGR diff (Strategy minus Lump Sum) ─────────────────────
    ax = axes[2]
    pos_colors = ["#1f77b4" if d >= 0 else "#ff7f0e" for d in diff]
    bars = ax.bar(x, diff, color=pos_colors, edgecolor="white", linewidth=0.5)
    ax.axhline(0, color="black", linewidth=1.2)

    # Annotate each bar with value
    for xi, d in zip(x, diff):
        va = "bottom" if d >= 0 else "top"
        offset = 0.05 if d >= 0 else -0.05
        ax.text(xi, d + offset, f"{d:+.1f}%", ha="center", va=va, fontsize=6.5)

    blue_patch  = mpatches.Patch(color="#1f77b4", label="Strategy wins (positive)")
    orange_patch= mpatches.Patch(color="#ff7f0e", label="Lump Sum wins (negative)")
    ax.legend(handles=[blue_patch, orange_patch], fontsize=8)
    ax.set_ylabel("Strategy CAGR − Lump Sum CAGR (pp)", fontsize=10)
    ax.set_title("CAGR Advantage: Strategy vs Lump Sum", fontsize=10)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.grid(True, alpha=0.25, axis="y")

    plt.tight_layout()
    out = Path(f"{symbol}_quarterly.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Chart saved → {out}")


# ─────────────────────────────  MAIN  ───────────────────────────────────────
def main():
    print("\nQuarterly-Starts Dip-Tranche Backtest")
    print(f"20 starting quarters × 3 symbols  |  End date: {END_DATE}")
    print(f"Portfolio: ${PORTFOLIO:,.0f}\n")

    all_symbol_rows = {}

    for symbol, cfg in SYMBOLS.items():
        print(f"\n── {symbol} ─────────────────────────────────────────────────────")
        df   = fetch_symbol(symbol)
        rows = run_all_quarters(df, cfg["mult"])
        print_table(symbol, rows)
        plot_symbol(symbol, cfg, rows)
        all_symbol_rows[symbol] = rows

    print_summary(all_symbol_rows)
    print("\nDone. PNG charts saved: VOO_quarterly.png, QQQ_quarterly.png, VXUS_quarterly.png\n")


if __name__ == "__main__":
    main()
