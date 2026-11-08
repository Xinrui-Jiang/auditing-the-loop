"""Trajectory store (PLAN.md §7 M6): one folder per shot. Every round's prompt, take, feedback sheet and the
Analyser's reasoning are on disk, so a run can resume and the Analyser can read the whole history."""
from __future__ import annotations

import json
from pathlib import Path

from .schemas import Checklist, FeedbackSheet, RevisionPlan, Round, Status, Trajectory


class TrajectoryStore:
    def __init__(self, shot_dir: Path, trajectory: Trajectory):
        self.dir = shot_dir
        self.trajectory = trajectory

    @classmethod
    def start(cls, shot_dir: Path, checklist: Checklist) -> "TrajectoryStore":
        shot_dir.mkdir(parents=True, exist_ok=True)
        (shot_dir / "checklist.json").write_text(checklist.model_dump_json(indent=2))
        store = cls(shot_dir, Trajectory(shot_id=checklist.shot_id, checklist_path=str(shot_dir / "checklist.json")))
        store.save()
        return store

    @classmethod
    def load(cls, shot_dir: Path) -> "TrajectoryStore":
        return cls(shot_dir, Trajectory.model_validate_json((shot_dir / "trajectory.json").read_text()))

    def save(self) -> None:
        (self.dir / "trajectory.json").write_text(self.trajectory.model_dump_json(indent=2))

    def checklist(self) -> Checklist:
        return Checklist.model_validate_json(Path(self.trajectory.checklist_path).read_text())

    def round_dir(self, k: int) -> Path:
        d = self.dir / "rounds" / str(k)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def append(self, round_: Round) -> None:
        self.trajectory.rounds.append(round_)
        self.trajectory = Trajectory.model_validate(self.trajectory.model_dump())  # re-run the consistency checks
        self.save()

    def finish(self, status: str, output_round: int) -> None:
        self.trajectory = self.trajectory.model_copy(update={"status": status, "output_round": output_round})
        self.save()

    def sheets(self) -> list[FeedbackSheet]:
        return [FeedbackSheet.model_validate_json(Path(r.sheet_path).read_text()) for r in self.trajectory.rounds]

    def previous_statuses(self) -> dict[str, list[Status]]:
        out: dict[str, list[Status]] = {}
        for sheet in self.sheets():
            for v in sheet.verdicts:
                out.setdefault(v.item_id, []).append(v.status)
        return out

    def save_plan(self, k: int, plan: RevisionPlan) -> None:
        (self.round_dir(k) / "next_plan.json").write_text(plan.model_dump_json(indent=2))

    def pending_plan(self) -> RevisionPlan | None:
        """The plan written after the last recorded round, if the run stopped before generating from it."""
        if not self.trajectory.rounds:
            return None
        p = self.round_dir(self.trajectory.rounds[-1].round) / "next_plan.json"
        return RevisionPlan.model_validate_json(p.read_text()) if p.exists() else None

    def render_for_analyser(self) -> str:
        """The whole history as text: per round the prompt, the branch point, the reasoning and the sheet."""
        parts = []
        for r, sheet in zip(self.trajectory.rounds, self.sheets()):
            head = f"ROUND {r.round}" + ("" if r.branched_from is None else f" (prompt branched from round {r.branched_from})")
            lines = [head, f"PROMPT:\n{r.prompt}"]
            if r.rationale:
                lines.append(f"YOUR REASONING FOR THIS ROUND: {r.rationale}\nTARGETS: {', '.join(r.targets)}")
            lines.append("FEEDBACK SHEET (item | status | severity | uncertainty | fixability | evidence):")
            for v in sheet.verdicts:
                first = v.evidence[0] if v.evidence else ""
                lines.append(f"  {v.item_id} | {v.status} | {v.severity} | {v.uncertainty_state} | {v.fixability} | {first[:220]}")
            blocking = [v.item_id for v in sheet.blocking()]
            lines.append(f"BLOCKING ITEMS: {', '.join(blocking) if blocking else 'none'}")
            parts.append("\n".join(lines))
        return "\n\n".join(parts)
