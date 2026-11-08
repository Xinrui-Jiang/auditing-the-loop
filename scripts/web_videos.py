"""Make small web copies of every take under runs/loop (360x640, H.264, AAC) for publishing the trajectory
page as an artifact; writes docs/pages/web_videos/<shot>_r<k>.mp4 and a manifest mapping take paths to copies."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from loopauditor.schemas import Trajectory

ROOT = Path(__file__).resolve().parents[1]
LOOP = ROOT / "runs/loop"
OUT = ROOT / "docs/pages/web_videos"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for shot_dir in sorted(p for p in LOOP.iterdir() if (p / "trajectory.json").exists()):
        tr = Trajectory.model_validate_json((shot_dir / "trajectory.json").read_text())
        for r in tr.rounds:
            src = Path(r.take_path)
            src = src if src.is_absolute() else ROOT / src
            dst = OUT / f"{tr.shot_id}_r{r.round}.mp4"
            if not dst.exists():
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vf", "scale=360:-2", "-c:v", "libx264",
                                "-crf", "30", "-preset", "veryfast", "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", str(dst)], check=True)
            manifest[(src.relative_to(ROOT)).as_posix()] = str(dst.relative_to(ROOT))
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1))
    sizes = sum(p.stat().st_size for p in OUT.glob("*.mp4"))
    print(f"{len(manifest)} web copies, {sizes / 1e6:.1f} MB total")


if __name__ == "__main__":
    main()
