"""M2 on real data: generate one take for DB-38 with seedance-2.0 and write docs/pages/M2.html."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from module_page import Panel, Section, render  # noqa: E402

from loopauditor.config import ASPECT_RATIO, DEFAULT_BACKEND, DURATION_S, GENERATION_BACKENDS, PROMPT_SET_30, RESOLUTION  # noqa: E402
from loopauditor.generate import generate  # noqa: E402
from loopauditor.tools import ffprobe  # noqa: E402

SHOT = sys.argv[1] if len(sys.argv) > 1 else "DB-38"


def main() -> None:
    row = {json.loads(l)["shot_id"]: json.loads(l) for l in PROMPT_SET_30.open()}[SHOT]
    out_dir = ROOT / "runs/m2_test" / SHOT
    take = generate(row["prompt"], SHOT, 0, out_dir)
    info = ffprobe(Path(take.path))
    print(take.model_dump_json(indent=2))
    print(info.model_dump_json())
    request = {"model": GENERATION_BACKENDS[DEFAULT_BACKEND].model, "duration": DURATION_S, "resolution": RESOLUTION,
               "aspect_ratio": ASPECT_RATIO, "generate_audio": True, "prompt": row["prompt"]}
    page = ROOT / "docs/pages/M2.html"
    page.write_text(render("LoopAuditor M2 — generation backend", f"One take for {SHOT} with {DEFAULT_BACKEND}.",
                           [Section(f"{SHOT}, round 0", f"Latency {take.latency_s} s, cost ${take.cost_usd:.4f}. File: {Path(take.path).relative_to(ROOT)}",
                                    inputs=[Panel("request", json.dumps(request, indent=2, ensure_ascii=False))],
                                    outputs=[Panel("Take", take.model_dump_json(indent=2)), Panel("ffprobe", info.model_dump_json(indent=2))])]))
    print("wrote", page)


if __name__ == "__main__":
    main()
