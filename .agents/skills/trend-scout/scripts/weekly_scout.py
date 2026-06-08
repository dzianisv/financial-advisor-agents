#!/usr/bin/env python3
"""
trend-scout Stage 3 — the weekly run. One command -> one report.

Fetches prices once, scores themes (Stage 1 radar), picks strongest names within each
confirmed-strong theme (Stage 2, buy-strength), assembles cross-theme FINALISTS to hand to
multi-lens-quorum, and DIFFS vs last week. Writes reports/<YYYY-MM-DD>.md + a state JSON
used for next week's diff.

The quorum is NOT run here — that's an agent step (can't honestly call a multi-lens LLM panel
from a script). The report emits the finalists and instructs the operator/agent to run
multi-lens-quorum on them. That handoff is the conviction gate; this script is the screener.

Usage: python3 weekly_scout.py [--period 400d]
Educational, not advice. Weak-edge momentum screener — backtest with costs before trading.
"""
import os, sys, json, glob, argparse, warnings
from datetime import datetime
warnings.filterwarnings("ignore")
from theme_radar import (load_baskets, fetch, theme_metrics, heat_scores,
                         classify_stage, HERE)
from stock_picker import rank_theme, valuation_flag, is_strong

REPORTS = os.path.join(HERE, "..", "reports")


def prev_state():
    os.makedirs(REPORTS, exist_ok=True)
    states = sorted(glob.glob(os.path.join(REPORTS, "*_state.json")))
    if not states:
        return None
    with open(states[-1]) as f:
        return json.load(f)


def vstr(p):
    return f" [{p['valuation'][0]} {p['valuation'][1]}]" if p.get("valuation") else ""


def build_finalists(close, strong_metrics, bythme, n=6):
    """Top strongest above-trend name per strong theme, then top-n across themes by 6m RS."""
    cands = []
    for m in strong_metrics:
        picks = rank_theme(close, bythme[m["theme"]], top=1)
        if picks:
            p = picks[0]; p["theme"] = m["theme"]; p["theme_heat"] = m["heat"]
            cands.append(p)
    cands.sort(key=lambda x: x["ret_6m"], reverse=True)
    return cands[:n]


def diff_block(cur_themes, cur_finalists, prev):
    if not prev:
        return "_First run — no prior week to diff against (baseline)._"
    lines = []
    pst = {t["theme"]: t["stage"] for t in prev["themes"]}
    for t in cur_themes:
        old = pst.get(t["theme"])
        if old and old != t["stage"]:
            lines.append(f"- **{t['theme']}**: stage {old} → {t['stage']}")
    pf = {f["ticker"] for f in prev.get("finalists", [])}
    cf = {f["ticker"] for f in cur_finalists}
    added, dropped = cf - pf, pf - cf
    if added:
        lines.append(f"- finalists ADDED: {', '.join(sorted(added))}")
    if dropped:
        lines.append(f"- finalists DROPPED: {', '.join(sorted(dropped))}")
    return "\n".join(lines) if lines else "_No stage flips or finalist changes vs last week._"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", default="400d")
    args = ap.parse_args()

    b = load_baskets(); bench = b["_meta"]["benchmark"]
    bythme = {t["theme"]: t for t in b["themes"]}
    tickers = sorted({t for th in b["themes"]
                      for t in th["core"] + th["second_derivative"]} | {bench})
    close = fetch(tickers, args.period)
    if bench not in close.columns:
        sys.exit(f"ERROR: benchmark {bench} not fetched — aborting (no report written).")
    spy = close[bench]

    metrics = heat_scores([theme_metrics(t, close, spy) for t in b["themes"]])
    for m in metrics:
        m["stage"] = classify_stage(m)
    metrics.sort(key=lambda m: (m["heat"] or -1), reverse=True)
    strong = [m for m in metrics if is_strong(m)]

    finalists = build_finalists(close, strong, bythme)
    for f in finalists:
        if "valuation" not in f:
            f["valuation"] = valuation_flag(f["ticker"])

    prev = prev_state()
    date = datetime.now().strftime("%Y-%m-%d")
    os.makedirs(REPORTS, exist_ok=True)

    # ---- report markdown ----
    L = [f"# trend-scout weekly — {date}", "",
         "_Momentum theme screener (buy-strength). Weak edge; hypothesis only. "
         "Educational, not advice. Route finalists through multi-lens-quorum before acting._",
         "", "## Theme radar (ranked by heat)", "",
         "| theme | heat | stage | RS_3m | RS_6m | breadth (n) | leader |",
         "|---|---|---|---|---|---|---|"]
    for m in metrics:
        lp = m.get("leader_pick")
        lead = f"{lp['ticker']} ({lp['ret_6m']*100:+.0f}%)" if lp else "-"
        L.append(f"| {m['theme']} | {m['heat']:.0f} | {m['stage']} | "
                 f"{(m['rs_3m'] or 0)*100:+.0f}% | {(m['rs_6m'] or 0)*100:+.0f}% | "
                 f"{(m['breadth'] or 0)*100:.0f}% (n={m.get('n_breadth', 0)}) | {lead} |")
    L += ["", "_breadth (n) = % of constituents above their 200d MA, over n names with ≥200d "
          "history; a small n (IPO-heavy theme) makes breadth unreliable._",
          "_Stage is descriptive only — EARLY>LATE was not predictive OOS. (Stage 0 tested a "
          "momentum-recency proxy, not this exact formula; directionally informative.)_", ""]

    L += ["## Picks within confirmed-strong themes (buy-strength)", ""]
    if not strong:
        L.append("_No theme is confirmed-strong this week (RS_6m>0 and breadth≥50%)._")
    for m in strong:
        L.append(f"**{m['theme']}** (heat {m['heat']:.0f}, RS_6m {m['rs_6m']*100:+.0f}%)")
        for p in rank_theme(close, bythme[m["theme"]]):
            L.append(f"- {p['ticker']} {p['ret_6m']*100:+.0f}% 6m · {p['role']}{vstr(p)}")
        L.append("")

    L += ["## FINALISTS → run multi-lens-quorum", "",
          "Strongest above-trend name per strong theme. Hand these to `multi-lens-quorum` "
          "for the buy/size/timing call; valuation in brackets is a RISK flag (overpay caution).", ""]
    for f in finalists:
        L.append(f"- **{f['ticker']}** ({f['theme']}) {f['ret_6m']*100:+.0f}% 6m{vstr(f)}")
    L += ["", "## Diff vs last week", "", diff_block(metrics, finalists, prev), ""]

    report_path = os.path.join(REPORTS, f"{date}.md")
    with open(report_path, "w") as fh:
        fh.write("\n".join(L))

    state = {"date": date,
             "themes": [{"theme": m["theme"], "stage": m["stage"], "heat": m["heat"]} for m in metrics],
             "finalists": [{"ticker": f["ticker"], "theme": f["theme"]} for f in finalists]}
    with open(os.path.join(REPORTS, f"{date}_state.json"), "w") as fh:
        json.dump(state, fh, indent=2)

    print(f"wrote {os.path.relpath(report_path)}")
    print(f"strong themes: {[m['theme'] for m in strong]}")
    print(f"finalists: {[f['ticker'] for f in finalists]}")


if __name__ == "__main__":
    main()
