"""Loop metrics from the trajectories under runs/loop (PLAN.md §7 M9, the part that needs no human labels):
per shot the rounds, outcome and cost; overall the output rate, hand-off rate, rounds to output, cost per
output shot, and which checklist items blocked most often. Writes runs/loop/metrics.md and metrics.json."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from loopauditor.schemas import FeedbackSheet, Trajectory

ROOT = Path(__file__).resolve().parents[1]
LOOP = ROOT / "runs/loop"


def main() -> None:
    shots = []
    blocked = Counter()
    first_round_blocked = Counter()
    for shot_dir in sorted(p for p in LOOP.iterdir() if (p / "trajectory.json").exists()):
        tr = Trajectory.model_validate_json((shot_dir / "trajectory.json").read_text())
        sheets = [FeedbackSheet.model_validate_json((ROOT / r.sheet_path).read_text()) for r in tr.rounds]
        per_round = [[v.item_id for v in s.blocking()] for s in sheets]
        for k, ids in enumerate(per_round):
            blocked.update(i.split(".")[0] for i in ids)
            if k == 0:
                first_round_blocked.update(i.split(".")[0] for i in ids)
        branches = sum(1 for r in tr.rounds[1:] if r.branched_from != r.round - 1)
        shots.append({"shot": tr.shot_id, "status": tr.status, "rounds": len(tr.rounds), "output_round": tr.output_round,
                      "backtracks": branches, "cost_usd": round(sum(r.cost_usd for r in tr.rounds), 3),
                      "blocking_per_round": [len(x) for x in per_round]})
    done = [s for s in shots if s["status"] != "running"]
    out = [s for s in done if s["status"] == "output"]
    summary = {
        "shots": len(shots), "finished": len(done), "output": len(out), "hand_off": len(done) - len(out),
        "output_rate": round(len(out) / len(done), 3) if done else None,
        "mean_rounds_to_output": round(sum(s["rounds"] for s in out) / len(out), 2) if out else None,
        "mean_cost_per_output_shot": round(sum(s["cost_usd"] for s in out) / len(out), 3) if out else None,
        "total_cost_usd": round(sum(s["cost_usd"] for s in shots), 3),
        "blocking_checks_all_rounds": dict(blocked.most_common()), "blocking_checks_round0": dict(first_round_blocked.most_common()),
    }
    lines = ["| shot | status | rounds | output round | backtracks | blocking per round | cost |", "|---|---|---|---|---|---|---|"]
    lines += [f"| {s['shot']} | {s['status']} | {s['rounds']} | {s['output_round']} | {s['backtracks']} | {s['blocking_per_round']} | ${s['cost_usd']:.2f} |" for s in shots]
    lines += ["", "| metric | value |", "|---|---|"] + [f"| {k} | {v} |" for k, v in summary.items() if not isinstance(v, dict)]
    lines += ["", "Blocking checks, all rounds: " + ", ".join(f"{k} {v}" for k, v in blocked.most_common()),
              "Blocking checks, round 0: " + ", ".join(f"{k} {v}" for k, v in first_round_blocked.most_common())]
    (LOOP / "metrics.md").write_text("\n".join(lines))
    (LOOP / "metrics.json").write_text(json.dumps({"shots": shots, "summary": summary}, indent=1))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
