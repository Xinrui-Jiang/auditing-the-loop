"""M4 + M5 on real data: the verifier panel and the label aggregation on pilot takes; writes docs/pages/M4_M5.html."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from module_page import Panel, Section, render  # noqa: E402

from loopauditor.cache import Cache  # noqa: E402
from loopauditor.config import CACHE_DIR  # noqa: E402
from loopauditor.loop import verify_take  # noqa: E402
from loopauditor.schemas import Checklist, Take  # noqa: E402

SHOTS = sys.argv[1:] or ["DB-38", "DB-16"]


def sheet_table(sheet, checklist) -> str:
    lines = [f"{'item':<6} {'status':<9} {'severity':<8} {'uncertainty':<14} {'fixability':<16} {'swap':<5} {'2nd':<5} {'tool':<5} evidence"]
    for v in sheet.verdicts:
        s = v.signals
        flag = lambda b: "-" if b is None else ("yes" if b else "no")
        first = v.evidence[0][:150] if v.evidence else ""
        lines.append(f"{v.item_id:<6} {v.status:<9} {v.severity:<8} {v.uncertainty_state:<14} {v.fixability:<16} {flag(s.order_swap_agree):<5} {flag(s.second_family_agree):<5} {flag(s.tool_agree):<5} {first}")
    blocking = [v.item_id for v in sheet.blocking()]
    lines += ["", f"BLOCKING: {blocking or 'none'}  ->  stop rule: {'continue' if blocking else 'OUTPUT'}", f"verification cost ${sheet.cost_usd:.4f}"]
    return "\n".join(lines)


def main() -> None:
    cache = Cache(CACHE_DIR)
    sections = []
    for sid in SHOTS:
        meta = json.loads((ROOT / f"data/pilot_takes/{sid}/attempt1_seedance480.json").read_text())
        checklist = Checklist.model_validate_json((ROOT / "runs/checklists" / f"{sid}.json").read_text())
        take = Take(shot_id=sid, round=0, path=str(ROOT / f"data/pilot_takes/{sid}/attempt1_seedance480.mp4"), backend="seedance-1-5-pro (pilot)",
                    seed=None, duration_s=8, resolution="480p", aspect_ratio="9:16", prompt_sha256="pilot", sha256=meta["sha256"],
                    cost_usd=meta["cost_usd"], request_id=meta["job_id"], latency_s=0.0)
        round_dir = ROOT / "runs/m45" / sid
        round_dir.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        sheet, observations = verify_take(take, checklist, {}, round_dir, cache)
        elapsed = time.time() - t0
        raws = json.loads((round_dir / "raw_verdicts.json").read_text())
        sources = {}
        for r in raws:
            sources[r["source"]] = sources.get(r["source"], 0) + 1
        descriptions = [o for o in observations if o.source.startswith("describe/")]
        print(sid, f"{elapsed:.0f}s", f"${sheet.cost_usd:.4f}", "blocking:", [v.item_id for v in sheet.blocking()], "calls:", len(observations))
        sections.append(Section(
            f"{sid}: panel + labels in {elapsed:.0f} s, {len(observations)} model/tool calls, ${sheet.cost_usd:.4f}",
            "Left: the take and the checklist the panel received (never the trajectory). Right: the feedback sheet after aggregation and re-inspects, then the blind descriptions and the raw verdicts per source.",
            inputs=[Panel("take", f"{take.path}\nsha256 {take.sha256}"),
                    Panel("checklist items", "\n".join(f"{i.id} [{i.kind}, {i.priority}] {i.text}" for i in checklist.items))],
            outputs=[Panel("feedback sheet (M5)", sheet_table(sheet, checklist)),
                     Panel("raw verdicts per source (M4 + tools)", json.dumps(sources, indent=1)),
                     *[Panel(f"blind description: {o.source}", o.text[:6000]) for o in descriptions],
                     Panel("all raw verdicts", json.dumps(raws, indent=1, ensure_ascii=False)[:40000])]))
    page = ROOT / "docs/pages/M4_M5.html"
    page.write_text(render("LoopAuditor M4 + M5 — verifier panel and labels", "Pilot takes, M1 checklists; panel never sees any history.", sections))
    print("wrote", page)


if __name__ == "__main__":
    main()
