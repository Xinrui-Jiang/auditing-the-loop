"""Copy the small result files of the loop runs (no videos) into results/<run>/ so they can be committed."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEEP = {"trajectory.json", "checklist.json", "handoff.json", "report.md", "checklist_observations.json",
        "sheet.json", "next_plan.json", "raw_verdicts.json", "observations.json", "generation.json", "cost_estimated.json", "generation_refused.json"}


def main(name: str) -> None:
    dst = ROOT / "results" / name
    if dst.exists():
        shutil.rmtree(dst)
    for src in (ROOT / "runs/loop").rglob("*"):
        if src.is_file() and (src.name in KEEP or src.name.startswith("metrics")):
            target = dst / src.relative_to(ROOT / "runs/loop")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
    (dst / "checklists").mkdir(exist_ok=True)
    for src in (ROOT / "runs/checklists").glob("*.json"):
        shutil.copy2(src, dst / "checklists" / src.name)
    n = sum(1 for _ in dst.rglob("*") if _.is_file())
    print(f"copied {n} files to {dst.relative_to(ROOT)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "loop_2026-11-08")
