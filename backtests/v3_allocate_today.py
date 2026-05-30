#!/usr/bin/env python3
"""
v3_allocate_today.py — "What do I buy today?" for the v3 Balanced allocation.

Prints a dated, actionable buy list for the v3 Balanced ETF portfolio, augmented
with live regime and dip-tranche signals. Notification-first: this places no trades.

Usage:
    python backtests/v3_allocate_today.py
    python backtests/v3_allocate_today.py --capital 500000
    python backtests/v3_allocate_today.py --json

Requires: pip install yfinance pandas numpy
Educational analysis only — not financial advice.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError:
    sys.exit("pip install yfinance pandas numpy")

# ---------------------------------------------------------------------------
# Path setup — import skills without copying their logic
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "skills" / "regime-detection"))
sys.path.insert(0, str(_REPO_ROOT / "skills" / "dip-tranches-strategy"))

_REGIME_OK = False
_DIP_OK = False

try:
    from regime_monitor import compute_regime  # type: ignore
    _REGIME_OK = True
except Exception as _e:
    print(f"WARNING: could not import regime_monitor ({_e}). Regime block will be skipped.", file=sys.stderr)

try:
    from check_drawdown import fetch_price_data, build_plan, evaluate  # type: ignore
    _DIP_OK = True
except Exception as _e:
    print(f"WARNING: could not import check_drawdown ({_e}). Dip block will be skipped.", file=sys.stderr)

# ---------------------------------------------------------------------------
# V3 Balanced — strategic weights (must sum to 1.0)
# ---------------------------------------------------------------------------
V3_SLEEVES = [
    # (ticker, weight, role)
    ("RSP",  0.18, "US large-cap equal-weight"),
    ("VXUS", 0.12, "international developed + EM equity"),
    ("AVUV", 0.08, "US small-cap value (factor tilt)"),
    ("USMV", 0.07, "US low-volatility equity"),
    ("GLD",  0.10, "gold / inflation hedge"),
    ("DBMF", 0.10, "trend / managed futures"),
    ("TLT",  0.07, "long-duration Treasuries"),
    ("SCHP", 0.03, "TIPS / inflation-linked bonds"),
    ("SGOV", 0.22, "dry powder / dip reserve (T-bills)"),
    ("BTAL", 0.03, "market-neutral / tail hedge"),
]

# Deployment tranches (of total capital)
FOUNDATION_PCT  = 0.50   # deploy immediately into strategic weights
DCA_PCT         = 0.28   # systematic DCA over 15 months
DIP_RESERVE_PCT = 0.22   # held in SGOV; deployed via dip tiers
DCA_MONTHS      = 15

# Sanity-check: weights must be exactly 1.0
_weight_sum = sum(w for _, w, _ in V3_SLEEVES)
assert abs(_weight_sum - 1.0) < 1e-9, f"V3 weights sum to {_weight_sum}, not 1.0"


# ---------------------------------------------------------------------------
# Price download
# ---------------------------------------------------------------------------

def _download_prices(tickers: list[str]) -> tuple[dict[str, float | None], str]:
    """
    Download the latest close for each ticker.
    Returns ({ticker: price_or_None}, as_of_date_str).
    Missing tickers are flagged but don't crash.
    as_of_date_str is the last valid index date across the downloaded frame,
    or "unknown" if the download fails or the frame is empty.
    """
    result: dict[str, float | None] = {t: None for t in tickers}
    as_of = "unknown"
    try:
        raw = yf.download(
            tickers,
            period="5d",
            auto_adjust=True,
            progress=False,
        )["Close"]

        # yf may return a Series (single ticker) or DataFrame
        if isinstance(raw, pd.Series):
            raw = raw.to_frame(name=tickers[0])

        for ticker in tickers:
            if ticker in raw.columns:
                col = raw[ticker].dropna()
                if len(col):
                    result[ticker] = float(col.iloc[-1])

        idx = raw.dropna(how="all").index
        if len(idx):
            as_of = str(idx[-1].date())
    except Exception as exc:
        print(f"WARNING: price download error — {exc}", file=sys.stderr)

    return result, as_of


# ---------------------------------------------------------------------------
# Core allocation calculation
# ---------------------------------------------------------------------------

def compute_allocation(capital: float) -> dict:
    """
    Returns a structured dict with all allocation, regime, and dip data.
    All numeric values are plain Python float/int (JSON-serializable).
    """
    tickers = [t for t, _, _ in V3_SLEEVES]
    prices, as_of = _download_prices(tickers)

    # --- Per-sleeve calculation ---
    allocation = []
    total_residual = 0.0
    total_target = 0.0

    for ticker, weight, role in V3_SLEEVES:
        target_dollar = weight * capital
        price = prices.get(ticker)
        if price is not None and price > 0:
            shares = math.floor(target_dollar / price)
            actual_dollar = shares * price
            residual = target_dollar - actual_dollar
        else:
            shares = None
            actual_dollar = None
            residual = 0.0  # can't compute residual without price

        total_target += target_dollar
        if residual:
            total_residual += residual

        allocation.append({
            "ticker": ticker,
            "role": role,
            "weight_pct": round(weight * 100, 1),
            "target_dollar": round(target_dollar, 2),
            "price": round(price, 4) if price is not None else None,
            "shares": int(shares) if shares is not None else None,
            "actual_dollar": round(actual_dollar, 2) if actual_dollar is not None else None,
            "residual": round(residual, 2),
            "price_ok": price is not None,
        })

    # --- Deployment tranches ---
    foundation_dollar   = round(FOUNDATION_PCT * capital, 2)
    dca_dollar          = round(DCA_PCT * capital, 2)
    dip_reserve_dollar  = round(DIP_RESERVE_PCT * capital, 2)
    dca_per_month       = round(dca_dollar / DCA_MONTHS, 2)

    tranches = {
        "foundation_pct": FOUNDATION_PCT * 100,
        "foundation_dollar": foundation_dollar,
        "dca_pct": DCA_PCT * 100,
        "dca_dollar": dca_dollar,
        "dca_months": DCA_MONTHS,
        "dca_per_month": dca_per_month,
        "dip_reserve_pct": DIP_RESERVE_PCT * 100,
        "dip_reserve_dollar": dip_reserve_dollar,
    }

    # Reconciliation
    tranche_sum = foundation_dollar + dca_dollar + dip_reserve_dollar
    assert abs(tranche_sum - capital) < 1.0, (
        f"Foundation+DCA+DipReserve={tranche_sum:.2f} != capital={capital:.2f}"
    )
    assert abs(total_target - capital) < 1.0, (
        f"Sleeve target sum={total_target:.2f} != capital={capital:.2f}"
    )

    # --- Regime ---
    regime_data: dict | None = None
    if _REGIME_OK:
        try:
            regime_data = compute_regime("^GSPC")
            # ensure JSON-serializable
            for k, v in list(regime_data.items()):
                if isinstance(v, (np.integer,)):
                    regime_data[k] = int(v)
                elif isinstance(v, (np.floating,)):
                    regime_data[k] = float(v)
                elif isinstance(v, dict):
                    regime_data[k] = {
                        kk: (int(vv) if isinstance(vv, np.integer) else
                             float(vv) if isinstance(vv, np.floating) else vv)
                        for kk, vv in v.items()
                    }
        except Exception as exc:
            print(f"WARNING: compute_regime failed — {exc}", file=sys.stderr)
            regime_data = None

    # --- Dip ---
    dip_data: dict | None = None
    dip_price_info: dict | None = None
    if _DIP_OK:
        try:
            cur, high52, ddate = fetch_price_data("^GSPC")
            plan = build_plan(dip_reserve_dollar)
            res = evaluate(cur, high52, plan)
            dip_price_info = {
                "ticker": "^GSPC",
                "current": round(float(cur), 2),
                "high_52w": round(float(high52), 2),
                "as_of": ddate,
            }
            # ensure JSON-serializable
            def _clean(obj):
                if isinstance(obj, list):
                    return [_clean(x) for x in obj]
                if isinstance(obj, dict):
                    return {k: _clean(v) for k, v in obj.items()}
                if isinstance(obj, np.integer):
                    return int(obj)
                if isinstance(obj, np.floating):
                    return float(obj)
                return obj

            dip_data = _clean(res)
            if as_of == "unknown" and ddate:
                as_of = ddate
        except Exception as exc:
            print(f"WARNING: dip evaluation failed — {exc}", file=sys.stderr)
            dip_data = None

    return {
        "as_of": as_of,
        "capital": float(capital),
        "allocation": allocation,
        "residual_cash": round(total_residual, 2),
        "tranches": tranches,
        "regime": regime_data,
        "dip_price_info": dip_price_info,
        "dip": dip_data,
    }


# ---------------------------------------------------------------------------
# Human-readable report
# ---------------------------------------------------------------------------

def _fmt_dollar(v: float | None) -> str:
    if v is None:
        return "N/A"
    return f"${v:>12,.2f}"


def print_report(data: dict) -> None:
    cap = data["capital"]
    as_of = data["as_of"]

    print()
    print("=" * 72)
    print(f"  v3 BALANCED — TODAY'S ALLOCATION")
    print(f"  As of: {as_of}    Capital: ${cap:,.0f}")
    print("=" * 72)

    # --- Allocation table ---
    print()
    hdr = f"{'ETF':<6}  {'Role':<38}  {'Wt%':>5}  {'$ Target':>12}  {'Price':>9}  {'Shares':>7}  {'Actual $':>12}"
    print(hdr)
    print("-" * len(hdr))

    for s in data["allocation"]:
        price_str = f"${s['price']:>8,.2f}" if s["price"] is not None else "   N/A    "
        shares_str = f"{s['shares']:>7,}" if s["shares"] is not None else "    n/a"
        actual_str = _fmt_dollar(s["actual_dollar"])
        flag = " !" if not s["price_ok"] else "  "
        print(
            f"{s['ticker']:<6}  {s['role']:<38}  {s['weight_pct']:>4.1f}%"
            f"  {_fmt_dollar(s['target_dollar'])}  {price_str}  {shares_str}  {actual_str}{flag}"
        )

    print("-" * len(hdr))
    print(f"{'TOTAL':<6}  {'':<38}  {'100.0%':>5}  {_fmt_dollar(cap)}  {'':>9}  {'':>7}  {''}")
    print(f"\n  Residual cash (fractional-share remainder): {_fmt_dollar(data['residual_cash'])}")
    print("  Note: fractional shares accepted at most brokers — residual can be swept.")

    # --- Deployment tranches ---
    t = data["tranches"]
    print()
    print("─" * 72)
    print("  DEPLOYMENT SCHEDULE")
    print("─" * 72)
    print(f"  Foundation   ({t['foundation_pct']:.0f}%)  — deploy immediately into strategic weights:")
    print(f"      {_fmt_dollar(t['foundation_dollar'])}")
    print(f"  Systematic DCA ({t['dca_pct']:.0f}%) — {t['dca_months']} equal monthly buys:")
    print(f"      Total  {_fmt_dollar(t['dca_dollar'])}")
    print(f"      Per mo {_fmt_dollar(t['dca_per_month'])}  (approx. {t['dca_months']} months)")
    print(f"  Dip Reserve  ({t['dip_reserve_pct']:.0f}%)  — held in SGOV; deploy via dip tiers:")
    print(f"      {_fmt_dollar(t['dip_reserve_dollar'])}")
    print(f"\n  [reconciled] Foundation + DCA + Dip Reserve = ${t['foundation_dollar'] + t['dca_dollar'] + t['dip_reserve_dollar']:,.2f}  ✓")

    # --- Regime ---
    print()
    print("─" * 72)
    print("  REGIME SIGNAL  (tactical dial — v3 weights are the strategic target)")
    print("─" * 72)
    r = data.get("regime")
    if r:
        score_bar = "▓" * int(abs(r["score"]) * 10) + "░" * (10 - int(abs(r["score"]) * 10))
        print(f"  Index:   ^GSPC   {r['price']}   |   200d MA: {r['sma200']}")
        print(f"  Regime:  {r['regime'].upper():20s}  score {r['score']:+.3f}   [{score_bar}]")
        print(f"  Exposure multiplier: {r['exposure_multiplier']}x")
        signals_str = "  ".join(f"{k}={v:+d}" for k, v in r["signals"].items())
        print(f"  Signals: {signals_str}")
        interp = {
            "risk-on":       "All signals green — full strategic weight deployment appropriate.",
            "neutral":       "Mixed signals — proceed with Foundation tranche; hold DCA cadence.",
            "risk-off (mild)": "Mild caution — prioritize defensive sleeves; slow DCA.",
            "risk-off":      "Stress regime — lean defensive; hold Dip Reserve in SGOV.",
        }.get(r["regime"], "Regime data available; see score above.")
        print(f"  Interpretation: {interp}")
        print(f"  {r['note']}")
    else:
        print("  [regime data unavailable — helper import failed or download error]")

    # --- Dip ---
    print()
    print("─" * 72)
    print("  DIP-TRANCHE SIGNAL  (SGOV reserve deployment guide)")
    print("─" * 72)
    dip = data.get("dip")
    dpi = data.get("dip_price_info")
    t_dict = data["tranches"]
    if dip and dpi:
        dd = dip["drawdown_pct"]
        print(f"  ^GSPC current: ${dpi['current']:,.2f}   52w high: ${dpi['high_52w']:,.2f}   as of: {dpi['as_of']}")
        print(f"  Drawdown from 52w high: {dd:.2f}%")
        print(f"  Dip reserve (SGOV): {_fmt_dollar(t_dict['dip_reserve_dollar'])}")
        print()
        if dip["triggered"]:
            print(f"  *** {len(dip['triggered'])} SUB-TRANCHE(S) ACTIVE — consider deploying from SGOV ***")
            for tr in dip["triggered"]:
                print(
                    f"    Tier {tr['tier']}-{tr['sub_tranche']}:  deploy {_fmt_dollar(tr['amount_usd'])}"
                    f"  (trigger: {tr['trigger_pct']:.1f}%  price: ${tr['trigger_price']:,.2f})"
                )
        else:
            print("  No dip tier active — hold reserve in SGOV.")

        if dip["pending"]:
            print()
            print("  Next price-based triggers (set limit alerts):")
            for p in dip["pending"][:6]:
                print(
                    f"    Tier {p['tier']}-{p['sub_tranche']}:  {_fmt_dollar(p['amount_usd'])}"
                    f"  @ ${p['trigger_price']:,.2f}  ({p['trigger_pct']:.1f}%)"
                )
        print()
        print("  Note: time-based sub-tranches (xd, yd weeks below threshold) require")
        print("  weekly monitoring — not evaluable from today's single-snapshot close.")
    else:
        print("  [dip data unavailable — helper import failed or download error]")

    # --- Reconciliation confirmation ---
    print()
    print("─" * 72)
    sleeve_sum = sum(s["target_dollar"] for s in data["allocation"])
    tranche_sum = t_dict["foundation_dollar"] + t_dict["dca_dollar"] + t_dict["dip_reserve_dollar"]
    ok1 = abs(sleeve_sum - cap) < 1.0
    ok2 = abs(tranche_sum - cap) < 1.0
    print(f"  RECONCILIATION")
    print(f"  Sum of sleeve targets:           ${sleeve_sum:>12,.2f}  {'✓' if ok1 else '✗ MISMATCH'}")
    print(f"  Foundation + DCA + Dip Reserve:  ${tranche_sum:>12,.2f}  {'✓' if ok2 else '✗ MISMATCH'}")
    print(f"  Note: the deployment tranches and the sleeve table describe the SAME ${cap:,.0f} two ways —")
    print(f"  the SGOV sleeve (22%) IS the dip reserve. They are not additive.")
    if ok1 and ok2:
        print("  reconciled ✓")

    # --- Disclaimer ---
    print()
    print("=" * 72)
    print("  DISCLAIMER: Educational analysis only — not financial advice.")
    print("  Notification-first: this places no trades.")
    print("  Validate with a fee-only fiduciary before deploying real capital.")
    print("=" * 72)
    print()


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------

def _to_json_safe(obj):
    """Recursively cast numpy types to Python native."""
    if isinstance(obj, dict):
        return {k: _to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_json_safe(x) for x in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


def print_json(data: dict) -> None:
    # Build a clean, subset dict suitable for automation
    out = {
        "as_of": data["as_of"],
        "capital": data["capital"],
        "allocation": data["allocation"],
        "residual_cash": data["residual_cash"],
        "tranches": data["tranches"],
        "regime": data["regime"],
        "dip_price_info": data["dip_price_info"],
        "dip": data["dip"],
    }
    print(json.dumps(_to_json_safe(out), indent=2))


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="v3 Balanced — today's dollar allocation + regime + dip signal."
    )
    ap.add_argument(
        "--capital",
        type=float,
        default=1_000_000,
        help="Total capital to allocate in USD (default: 1,000,000)",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of the human report",
    )
    args = ap.parse_args()

    data = compute_allocation(args.capital)

    if args.json:
        print_json(data)
    else:
        print_report(data)


if __name__ == "__main__":
    main()
