"""M1 on real data: the Analyser writes a checklist for each of the 30 shots.
Writes runs/checklists/<shot>.json (+ .extraction.json) and docs/pages/M1.html."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from module_page import Panel, Section, render  # noqa: E402

from loopauditor.analyser import ChecklistError, script_text, write_checklist  # noqa: E402
from loopauditor.cache import Cache  # noqa: E402
from loopauditor.config import ANALYSER_MODEL, CACHE_DIR, PROMPT_SET_30  # noqa: E402
from loopauditor.openrouter import ChatJSONError  # noqa: E402
from loopauditor.schemas import Checklist  # noqa: E402

OUT = ROOT / "runs/checklists"
HANDWRITTEN = ROOT / "data/examples/checklists"


def items_table(cl: Checklist) -> str:
    lines = [f"{'id':<6} {'kind':<9} {'priority':<9} {'evidence':<11} text"]
    for i in cl.items:
        extra = ""
        if i.params.element:
            extra = f'  [span: {i.params.element}]'
        if i.params.target_interval:
            extra = f"  [interval {list(i.params.target_interval)}]"
        lines.append(f"{i.id:<6} {i.kind:<9} {i.priority:<9} {i.evidence:<11} {i.text}{extra}")
    if cl.conflicts:
        lines += ["", "conflicts: " + "; ".join(cl.conflicts)]
    return "\n".join(lines)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(l) for l in PROMPT_SET_30.open()]
    cache = Cache(CACHE_DIR)
    summary, sections, failures, total_cost = [], [], [], 0.0
    for row in rows:
        sid = row["shot_id"]
        try:
            cl, obs = write_checklist(row, cache=cache)
        except (ChecklistError, ValidationError, ChatJSONError) as e:
            failures.append(f"{sid}: {type(e).__name__}: {str(e)[:400]}")
            sections.append(Section(f"{sid}: FAILED", str(e)[:600], inputs=[Panel("script", script_text(row))], outputs=[]))
            continue
        (OUT / f"{sid}.json").write_text(cl.model_dump_json(indent=2))
        (OUT / f"{sid}.extraction.json").write_text(obs[-1].text)
        cost = sum(o.cost_usd for o in obs)
        total_cost += cost
        fam = {f: len(cl.family(f)) for f in "ABC"}
        summary.append(f"{sid:<6} A{fam['A']:>2} B{fam['B']:>2} C{fam['C']:>2}  total {len(cl.items):>2}  "
                       f"retry {'yes' if len(obs) > 1 else 'no ':<3}  conflicts {len(cl.conflicts)}  ${cost:.4f}")
        sections.append(Section(f"{sid} — {len(cl.items)} items" + (" — conflict recorded" if cl.conflicts else ""),
                                f"Analyser model {obs[-1].model_id}; {len(obs)} call(s); ${cost:.4f}.",
                                inputs=[Panel("what the Analyser reads", script_text(row))],
                                outputs=[Panel("checklist items", items_table(cl)),
                                         Panel("LLM extraction (raw JSON answer)", obs[-1].text)]))
    head = [Section("Run summary",
                    f"{len(summary)} of {len(rows)} shots produced a checklist; {len(failures)} failed; total LLM cost ${total_cost:.4f}. "
                    "Rules write A1, the setting and sound items, A4, A6, all B items and C1/C2/C4; the LLM supplies actions, "
                    "props, other people, premise facts and implied must-nots, each tied to a span copied from the script.",
                    inputs=[Panel("settings", f"model: {ANALYSER_MODEL}\nprompt set: {PROMPT_SET_30.relative_to(ROOT)}\nitem range: 8-24\nspan check: every LLM span must be a substring of prompt_raw; one retry, then error")],
                    outputs=[Panel("per shot: items by family, retry, conflicts, cost", "\n".join(summary) or "(none)"),
                             Panel("failures", "\n".join(failures) or "(none)")])]
    for sid in ("DB-38", "DB-16"):
        hand = Checklist.model_validate_json((HANDWRITTEN / f"{sid}.json").read_text())
        auto_path = OUT / f"{sid}.json"
        if auto_path.exists():
            auto = Checklist.model_validate_json(auto_path.read_text())
            head.append(Section(f"{sid}: hand-written (M0) vs Analyser (M1)", "Same shot, two checklists. Left: written by hand on 2026-11-07. Right: written by the Analyser.",
                                inputs=[Panel("hand-written", items_table(hand))], outputs=[Panel("Analyser", items_table(auto))]))
    page = ROOT / "docs/pages/M1.html"
    page.write_text(render("LoopAuditor M1 — Analyser writes the checklist", "30 shots of prompt_set_v2_30; one checklist each.", head + sections))
    print(f"wrote {page}; {len(summary)} ok, {len(failures)} failed, ${total_cost:.4f}")
    for f in failures:
        print("FAIL", f)


if __name__ == "__main__":
    main()
