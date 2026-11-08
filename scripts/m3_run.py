"""M3 on real data: run the evidence tools on the five pilot takes with their M1 checklists; write docs/pages/M3.html."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from module_page import Panel, Section, render  # noqa: E402

from loopauditor.schemas import Checklist  # noqa: E402
from loopauditor.tools import tool_verdicts  # noqa: E402

PILOT = ROOT / "data/pilot_takes"
OUT = ROOT / "runs/m3_tools"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sections = []
    for sid in ("DB-38", "DB-60", "DB-16", "DB-35", "SB-01"):
        cl = Checklist.model_validate_json((ROOT / "runs/checklists" / f"{sid}.json").read_text())
        video = PILOT / sid / "attempt1_seedance480.mp4"
        t0 = time.time()
        verdicts, observations = tool_verdicts(video, cl, expected_duration_s=8, expected_short_side=480)
        elapsed = time.time() - t0
        (OUT / f"{sid}.json").write_text(json.dumps({"verdicts": [v.model_dump() for v in verdicts], "observations": [o.model_dump() for o in observations]}, indent=1))
        covered = [cl.item(v.item_id) for v in verdicts]
        sections.append(Section(f"{sid} — {len(verdicts)} tool verdicts in {elapsed:.1f} s",
                                "Tools answer only the items they cover: B6 from ffprobe, B4 from ffmpeg scene and freeze detection, A1 from whisper (language + WER).",
                                inputs=[Panel("take", str(video.relative_to(ROOT))),
                                        Panel("checklist items the tools cover", "\n".join(f"{i.id} [{i.priority}] {i.text}" + (f"\n      expected line: {i.params.line!r}, language {i.params.language}" if i.params.line else "") for i in covered))],
                                outputs=[Panel("RawVerdicts", json.dumps([v.model_dump() for v in verdicts], indent=1))]))
        print(sid, [(v.item_id, v.status, v.evidence[:70]) for v in verdicts], f"{elapsed:.1f}s")
    page = ROOT / "docs/pages/M3.html"
    page.write_text(render("LoopAuditor M3 — evidence tools", "Five pilot takes; deterministic tools only.", sections))
    print("wrote", page)


if __name__ == "__main__":
    main()
