#!/usr/bin/env python3
"""
auto_research — autonomous skill self-improvement loop (karpathy/autoresearch applied to a skill).

Inspired by Andrej Karpathy's AutoResearch (https://github.com/karpathy/autoresearch):
"One GPU, one file, one metric." An agent edits a single file (train.py), runs an experiment
under a fixed budget, scores ONE metric (val_bpb), and keeps the change only if the metric
improved — iterating ~100 experiments overnight.

We apply the SAME loop to improving THIS skill instead of training a model:
  - one editable file ...... SKILL.md   (was: train.py)
  - one metric ............. RUBRIC mean across eval cases   (was: val_bpb)
  - one experiment ......... run the actor on eval cases + LLM-judge the output
  - keep/discard ........... keep the SKILL.md edit iff mean rose, else revert to best
  - fixed budget ........... --budget rounds (was: 5-min wallclock / ~100 runs overnight)

This script is the bookkeeping + checkpoint/revert machinery ONLY — pure-python, zero API cost.
The two expensive steps of each round (RUN the actor, JUDGE the output) are done by the agent
orchestrator (see the <auto_research> section of SKILL.md) which then calls `record` here with
the resulting scores. This file owns the greedy keep-or-revert decision and the audit trail so
the loop is deterministic and resumable.

Loop (one round):
  1. next-target   -> agent reads which RUBRIC dimension is lowest, edits SKILL.md to fix it
  2. snapshot N    -> freeze the edited SKILL.md as round-N variant
  3. (agent runs actor on eval cases, judges with RUBRIC -> per-dimension scores)
  4. record N ...  -> append scores to scores.md; KEEP (new best) or DISCARD (revert SKILL.md)
  5. status        -> stop-condition check; if not met and budget remains, go to 1

State: evals/auto_research_state.json    Variants: evals/variants/round-N.md
"""

import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent
SKILL_MD = SKILL_DIR / "SKILL.md"
EVALS = SKILL_DIR / "evals"
SCORES_MD = EVALS / "scores.md"
VARIANTS = EVALS / "variants"
STATE = EVALS / "auto_research_state.json"

# RUBRIC dimensions, in scores.md column order.
DIMS = [
    "source_grounding",
    "non_obvious_discovery",
    "skeptic_discipline",
    "actionability",
    "quorum_routing",
    "prescreen_usage",
]
# Short labels used in the scores.md header (matches the existing hand-written table) -> full dim key.
DIM_COLS = ["source_grounding", "non_obvious", "skeptic", "actionability", "quorum_routing", "prescreen"]
SHORT2FULL = {
    "source_grounding": "source_grounding",
    "non_obvious": "non_obvious_discovery",
    "skeptic": "skeptic_discipline",
    "actionability": "actionability",
    "quorum_routing": "quorum_routing",
    "prescreen": "prescreen_usage",
}

# Stop condition (from evals/RUBRIC.md).
TRAIN_MEAN_MIN = 4.2
MIN_DIM = 3.0


def _load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {
        "round": 0,
        "best_mean": None,
        "best_variant": None,
        "best_dims": None,
        "budget": None,
        "history": [],  # list of {round, variant, mean, dims, decision}
    }


def _save_state(state: dict) -> None:
    EVALS.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2) + "\n")


def _mean(dims: dict) -> float:
    vals = [v for v in dims.values() if v is not None]
    return round(sum(vals) / len(vals), 3) if vals else 0.0


def cmd_init(args):
    """Snapshot the current SKILL.md as the baseline best (round 0)."""
    state = _load_state()
    VARIANTS.mkdir(parents=True, exist_ok=True)
    best_path = VARIANTS / "best.md"
    # Guard: a loop already in progress. Re-running init would clobber the best baseline
    # with the current (possibly mid-edit / reverted-worse) SKILL.md. Only update budget.
    if best_path.exists() and not args.force:
        state["budget"] = args.budget
        _save_state(state)
        print(f"init: already initialized (best_mean={state['best_mean']}). "
              f"budget updated to {args.budget}. baseline best.md left intact.")
        print("      Pass --force to re-snapshot the baseline from current SKILL.md (destroys best).")
        return
    shutil.copyfile(SKILL_MD, best_path)
    state["budget"] = args.budget
    if state["best_variant"] is None:
        state["best_variant"] = "best.md"
    _save_state(state)
    print(f"init: snapshotted SKILL.md -> {best_path.relative_to(SKILL_DIR)}")
    print(f"      budget = {args.budget} rounds. best_mean = {state['best_mean']}")
    print("Next: `next-target` to see which dimension to attack.")


def cmd_next_target(args):
    """Print the lowest-scoring RUBRIC dimension (the one to fix next)."""
    state = _load_state()
    dims = state.get("best_dims")
    if not dims:
        print("No scored round yet. Run a baseline round first (snapshot -> record).")
        print("Attack order until then: prescreen_usage, skeptic_discipline (historically weakest).")
        return
    ranked = sorted((v, k) for k, v in dims.items() if v is not None)  # ascending: weakest first
    if not ranked:
        print("Scored round has no applicable dimensions (all N/A). Nothing to target.")
        return
    worst_v, worst_k = ranked[0]
    print("Current best per-dimension means:")
    for v, k in reversed(ranked):
        flag = "  <-- WEAKEST" if (v, k) == ranked[0] else ""
        print(f"  {k:24s} {v:.2f}{flag}")
    print(f"\nNEXT TARGET: {worst_k} (mean {worst_v:.2f}). Edit SKILL.md to fix ONLY this, then snapshot.")


def cmd_snapshot(args):
    """Freeze the current (just-edited) SKILL.md as round-N variant."""
    VARIANTS.mkdir(parents=True, exist_ok=True)
    dst = VARIANTS / f"round-{args.round}.md"
    shutil.copyfile(SKILL_MD, dst)
    print(f"snapshot: SKILL.md -> {dst.relative_to(SKILL_DIR)}")


def cmd_record(args):
    """Record a round's scores; KEEP (new best) or DISCARD (revert SKILL.md to best)."""
    state = _load_state()
    dims = {}
    for pair in args.dims:
        if "=" not in pair:
            sys.exit(f"bad --dims token '{pair}': expected DIM=SCORE (e.g. skeptic_discipline=4 or =NA)")
        k, _, v = pair.partition("=")
        if k not in DIMS:
            sys.exit(f"unknown dimension '{k}'. valid: {', '.join(DIMS)}")
        if k in dims:
            sys.exit(f"dimension '{k}' specified twice")
        if v.upper() in ("NA", "N/A"):
            dims[k] = None
            continue
        try:
            score = float(v)
        except ValueError:
            sys.exit(f"dimension '{k}': score '{v}' is not a number (or NA)")
        if not (0.0 <= score <= 5.0):
            sys.exit(f"dimension '{k}': score {score} out of RUBRIC range 0–5")
        dims[k] = score
    for d in DIMS:
        dims.setdefault(d, None)

    mean = _mean(dims)
    variant = args.variant or f"round-{args.round}"
    best = state.get("best_mean")
    improved = best is None or mean > best
    decision = "KEEP" if improved else "DISCARD"

    # The snapshot is the source of truth for what was scored. Without it, a KEEP would
    # advance the state pointer while best.md stays stale — a later DISCARD would then
    # revert SKILL.md to content that doesn't match best_dims. Refuse rather than diverge.
    src = VARIANTS / f"round-{args.round}.md"
    if not src.exists():
        sys.exit(f"no snapshot for round {args.round} (run `snapshot {args.round}` first). "
                 f"Refusing to record without the scored SKILL.md frozen.")

    if improved:
        state["best_mean"] = mean
        state["best_variant"] = variant
        state["best_dims"] = dims
        # promote this variant to best.md (the new baseline to edit from)
        shutil.copyfile(src, VARIANTS / "best.md")
    else:
        # revert the editable file to the best-known SKILL.md
        best_md = VARIANTS / "best.md"
        if best_md.exists():
            shutil.copyfile(best_md, SKILL_MD)

    state["round"] = args.round
    state["history"].append(
        {"round": args.round, "variant": variant, "mean": mean, "dims": dims, "decision": decision}
    )
    _save_state(state)
    _append_scores_row(args.round, variant, dims, mean, best, decision)

    arrow = "%+.2f" % (mean - best) if best is not None else "baseline"
    print(f"record round {args.round} [{variant}]: mean={mean:.3f} ({arrow}) -> {decision}")
    if decision == "DISCARD":
        print("  reverted SKILL.md to best.md (greedy keep/discard, like karpathy keeps iff val_bpb drops)")
    else:
        print(f"  new best. promoted round-{args.round}.md -> best.md")
    _print_stop(state)


def _append_scores_row(rnd, variant, dims, mean, prev_best, decision):
    if not SCORES_MD.exists():
        return
    change = "—" if prev_best is None else ("%+.2f" % (mean - prev_best))
    cells = []
    for short in DIM_COLS:
        v = dims.get(SHORT2FULL[short])
        cells.append("—" if v is None else f"{v:.2f}")
    row = f"| {rnd} | {variant} ({decision}) | " + " | ".join(cells) + f" | {mean:.2f} | {change} |"
    text = SCORES_MD.read_text().rstrip() + "\n" + row + "\n"
    SCORES_MD.write_text(text)
    print(f"  appended row to {SCORES_MD.relative_to(SKILL_DIR)}")


def _print_stop(state):
    dims = state.get("best_dims") or {}
    mean = state.get("best_mean")
    applicable = [v for v in dims.values() if v is not None]
    min_dim = min(applicable) if applicable else None
    ok_mean = mean is not None and mean >= TRAIN_MEAN_MIN
    ok_dim = min_dim is not None and min_dim >= MIN_DIM
    print("\nstop-condition (best variant):")
    print(f"  train mean >= {TRAIN_MEAN_MIN}: {'PASS' if ok_mean else 'FAIL'} ({mean})")
    print(f"  no dim < {MIN_DIM}:        {'PASS' if ok_dim else 'FAIL'} (min={min_dim})")
    rounds_left = None if state.get("budget") is None else state["budget"] - state.get("round", 0)
    if ok_mean and ok_dim:
        print(f"  => SHIP best variant: {state.get('best_variant')}")
    elif rounds_left is not None and rounds_left <= 0:
        print(f"  => BUDGET EXHAUSTED. ship best so far: {state.get('best_variant')} (mean {mean})")
    else:
        left = "?" if rounds_left is None else rounds_left
        print(f"  => CONTINUE. {left} rounds left. run `next-target`.")


def cmd_status(args):
    state = _load_state()
    print(f"round={state.get('round')}  budget={state.get('budget')}  "
          f"best_mean={state.get('best_mean')}  best_variant={state.get('best_variant')}")
    if state.get("history"):
        print("history:")
        for h in state["history"]:
            print(f"  r{h['round']:>2} {h['decision']:7s} mean={h['mean']:.3f} [{h['variant']}]")
    _print_stop(state)


def cmd_reset(args):
    """Wipe loop state + variants (keeps SKILL.md as-is). For starting a fresh loop."""
    if STATE.exists():
        STATE.unlink()
    if VARIANTS.exists():
        shutil.rmtree(VARIANTS)
    print("reset: cleared auto_research_state.json and evals/variants/")


def main():
    p = argparse.ArgumentParser(description="autonomous skill self-improvement loop (karpathy autoresearch style)")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init", help="snapshot SKILL.md as baseline best + set budget")
    pi.add_argument("--budget", type=int, default=10, help="max rounds (default 10)")
    pi.add_argument("--force", action="store_true",
                    help="re-snapshot baseline from current SKILL.md even if already initialized (destroys best)")
    pi.set_defaults(func=cmd_init)

    pn = sub.add_parser("next-target", help="print lowest-scoring dimension to fix next")
    pn.set_defaults(func=cmd_next_target)

    ps = sub.add_parser("snapshot", help="freeze current SKILL.md as round-N variant")
    ps.add_argument("round", type=int)
    ps.set_defaults(func=cmd_snapshot)

    pr = sub.add_parser("record", help="record round scores; keep-or-revert by mean")
    pr.add_argument("round", type=int)
    pr.add_argument("--variant", help="variant label (default round-N)")
    pr.add_argument("--dims", nargs="+", required=True,
                    metavar="DIM=SCORE",
                    help="e.g. source_grounding=4 skeptic_discipline=5 prescreen_usage=NA")
    pr.set_defaults(func=cmd_record)

    pst = sub.add_parser("status", help="show loop state + stop-condition")
    pst.set_defaults(func=cmd_status)

    prst = sub.add_parser("reset", help="wipe loop state + variants")
    prst.set_defaults(func=cmd_reset)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
