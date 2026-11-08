"""Per-shot markdown report (PLAN.md §7 M8): the outcome, the final take's full sheet (blocking, reported-only,
passed), and the round history with the Analyser's reasoning."""
from __future__ import annotations

from pathlib import Path

from .schemas import Checklist, FeedbackSheet, Trajectory


def write_report(shot_dir: Path, trajectory: Trajectory, checklist: Checklist, sheets: list[FeedbackSheet], root: Path) -> Path:
    final_k = trajectory.output_round if trajectory.output_round is not None else len(trajectory.rounds) - 1
    final = sheets[final_k]
    blocking = {v.item_id for v in final.blocking()}
    lines = [f"# {trajectory.shot_id}: {'output' if trajectory.status == 'output' else 'hand-off'} at round {final_k}",
             "", f"Rounds: {len(trajectory.rounds)}. Total cost: ${sum(r.cost_usd for r in trajectory.rounds):.2f}. "
             f"Take: `{trajectory.rounds[final_k].take_path}`.", "", "## Final take: feedback sheet", "",
             "| item | status | severity | uncertainty | fixability | note |", "|---|---|---|---|---|---|"]
    for v in final.verdicts:
        note = "BLOCKING" if v.item_id in blocking else ("reported, not blocking" if v.severity == "error" else "")
        lines.append(f"| {v.item_id} | {v.status} | {v.severity} | {v.uncertainty_state} | {v.fixability} | {note} |")
    lines += ["", "Errors that did not block (backend-limited) and warnings are listed above; the checklist text per item:", ""]
    lines += [f"- {i.id}: {i.text}" for i in checklist.items if final.verdict(i.id).severity != "info"]
    lines += ["", "## Rounds", ""]
    for r, s in zip(trajectory.rounds, sheets):
        b = [v.item_id for v in s.blocking()]
        lines.append(f"### Round {r.round}" + ("" if r.branched_from is None else f" (branched from round {r.branched_from})"))
        lines.append(f"Blocking after this round: {', '.join(b) or 'none'}. Cost ${r.cost_usd:.2f}.")
        if r.rationale:
            lines.append(f"\nAnalyser: {r.rationale}\n\nTargets: {', '.join(r.targets)}")
        lines.append(f"\nPrompt:\n\n```\n{r.prompt}\n```\n")
    path = shot_dir / "report.md"
    path.write_text("\n".join(lines))
    return path
