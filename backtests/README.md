# backtests/ — the evidence scripts

Self-contained Python backtests behind the strategy. Each downloads its own data (yfinance), runs the
strategy, prints a report, and saves a chart to `../report/img/`. Cached text output lives in
[`results/`](results/).

> **Educational analysis only — not financial advice.**

## How to run

Always run **from the repo root** so the `report/img/` output path resolves:

```bash
# from /Users/engineer/workspace/backtest
python3 backtests/crash_protection_backtest.py
```

Deps: `yfinance matplotlib pandas numpy requests`. pandas freq string is `'M'` (not `'ME'`). yfinance's
sqlite cache occasionally throws "database is locked" / all-NaN tickers — `robust_download()` retries;
if a ticker still comes back empty, just re-run.

## Act on it today

| Script | What it does |
|--------|--------------|
| **`v3_allocate_today.py`** | Reads live prices and prints **today's** v3 Balanced allocation in actual dollars + shares for a given `--capital` (default $1M), the deployment schedule (Foundation/DCA/Dip-reserve), the current market regime, and the live S&P drawdown → which dip tier fires now. `--json` for automation. Notification-first; places no trades. Run: `python3 backtests/v3_allocate_today.py --capital 1000000` |

## The two that matter (current strategy — v3)

| Script | What it shows | Result file |
|--------|---------------|-------------|
| **`v3_proxy_backtest.py`** | **The actual v3 Balanced allocation** (each sleeve → long-history proxy, spliced onto the real ETF) + dip-reserve ladder, through dot-com/GFC/COVID/2022, plus a real-ETF-only 2019-2026 cross-check. Proves v3 on its own numbers (DD −27% vs S&P −55%; +73% lost decade; but lags in bulls). | `results/v3_proxy_summary.txt` |
| **`crash_protection_backtest.py`** | Generic all-weather / permanent / golden-butterfly / trend vs S&P & QQQ across dot-com, GFC, COVID, 2022 (2000-2026). The structural-edge evidence v3 is derived from. | `results/crash_protection_summary.txt` |
| **`fundamental_screens_backtest.py`** | Investable factor/selection ETFs (MOAT, COWZ, RPV, VLUE, SPHQ, QUAL, MTUM, SCHD, NOBL, USMV) vs SPY — survivorship/look-ahead safe. Shows selection ≠ alpha. | `results/fundamental_screens_summary.txt` |

## Exploratory backtests (the v1/v2 journey)

These tested entry-timing and selection ideas that were **superseded** (see
[`../strategy/`](../strategy/README.md)). Kept as the evidence trail; many have known biases (see
caveats in `../AGENTS.md`).

| Script | Strategy | Note |
|--------|----------|------|
| `backtest.py` | Dip-tranche vs lump-sum / DCA (VOO/QQQ/VXUS) | v1 — beat benchmarks on VXUS only |
| `quarterly_fan_chart.py`, `quarterly_starts_backtest.py` | Entry-point sensitivity | v1 |
| `value_factor_backtest.py`, `quality_factor_backtest.py`, `momentum_backtest.py` | Classic factors | v2 |
| `sector_rotation_backtest.py`, `tech_concentration_backtest.py` | Rotation / concentration | v2 |
| `congressional_backtest.py`, `congressional_quarterly_starts.py`, `congress_combined_quarterly.py`, `insider_backtest.py` | "Smart money" copy | v2 — weak/noisy |
| `pead_backtest.py`, `social_momentum_backtest.py`, `wheel_strategy_backtest.py` | Event/social/options | v2 — weak or biased |
| `morningstar_backtest.py` | Price-proxy "undervalued" screen | v2 — lost to VOO (the flawed proxy that motivated the clean test) |
| `era_2005_2020_backtest.py`, `alternatives_quarterly.py`, `tldr_chart.py` | Multi-era + master comparison | v2 |
| `publish_report.py`, `publish_report_v2.py` | Telegraph publishers | tooling (see `../AGENTS.md`) |

Full strategy index with key numbers and known biases: [`../AGENTS.md`](../AGENTS.md).
