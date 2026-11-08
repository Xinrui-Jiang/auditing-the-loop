"""Tables for the midway report, computed from the prompt set, the checklists and the loop runs. Writes docs/report_tables.md."""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from auditloop.schemas import Checklist, FeedbackSheet, Trajectory

ROOT = Path(__file__).resolve().parents[1]
LOOP = ROOT / "runs/loop"
OUT = ROOT / "docs/report_tables.md"
SOURCES = ["DramaBench", "SEAM-Bench", "FilmBench"]
BINS = ["calm", "strong", "exaggerated"]
FAMILY_NAME = {"A": "script fidelity", "B": "rendering integrity", "C": "dramatic performance"}


def md(rows: list[list], header: list[str]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def table_data(r30):
    rows = []
    for s in SOURCES:
        c = Counter(x["native_intensity_bin"] for x in r30 if x["source_dataset"] == s)
        sfx = sum(1 for x in r30 if x["source_dataset"] == s and x["sfx_cue"])
        rows.append([s, c["calm"], c["strong"], c["exaggerated"], sfx, sum(c.values())])
    c = Counter(x["native_intensity_bin"] for x in r30)
    rows.append(["total", c["calm"], c["strong"], c["exaggerated"], sum(1 for x in r30 if x["sfx_cue"]), len(r30)])
    emo = Counter(x["emotion_class"] for x in r30)
    extra = "Emotion classes: " + ", ".join(f"{k} {v}" for k, v in emo.most_common()) + ". " \
            f"Spoken line 3–12 words (median {sorted(len(x['line'].split()) for x in r30)[len(r30)//2]}); prompt median {sorted(len(x['prompt'].split()) for x in r30)[len(r30)//2]} words."
    return md(rows, ["source", "calm", "strong", "exaggerated", "with sound cue", "shots"]) + "\n\n" + extra


def table_checklists():
    cls = [Checklist.model_validate_json(p.read_text()) for p in sorted((ROOT / "runs/checklists").glob("*.json")) if not p.name.endswith(".extraction.json")]
    per_family = {f: [len(c.family(f)) for c in cls] for f in "ABC"}
    rows = [[f"{f} {FAMILY_NAME[f]}", f"{sum(v)/len(v):.1f}", min(v), max(v)] for f, v in per_family.items()]
    totals = [len(c.items) for c in cls]
    rows.append(["all", f"{sum(totals)/len(totals):.1f}", min(totals), max(totals)])
    checks = Counter(i.check_id for c in cls for i in c.items)
    per_check = ", ".join(f"{k} {v}" for k, v in sorted(checks.items()))
    casts = sum(1 for c in cls if "cast:" in c.item("A4.1").text and "," in c.item("A4.1").text.split("cast:")[1])
    return (md(rows, ["family", "items per shot, mean", "min", "max"]) + f"\n\nItems per check across the {len(cls)} checklists: {per_check}. "
            f"Checklists whose cast has more than the speaker: {casts} of {len(cls)}.")


def table_loop():
    rows, r0, exit_counter, fix_counter, latencies = [], Counter(), Counter(), Counter(), []
    for log in ROOT.glob("runs/loop_*.log"):
        latencies += [float(x) for x in re.findall(r"take in ([0-9.]+)s", log.read_text()) if float(x) > 1]
    for shot_dir in sorted(p for p in LOOP.iterdir() if (p / "trajectory.json").exists()):
        tr = Trajectory.model_validate_json((shot_dir / "trajectory.json").read_text())
        sheets = [FeedbackSheet.model_validate_json((ROOT / r.sheet_path).read_text()) for r in tr.rounds]
        k = tr.output_round
        b0 = [v.item_id for v in sheets[0].blocking()]
        bk = [v.item_id for v in sheets[k].blocking()]
        r0.update(i.split(".")[0] for i in b0)
        exit_counter.update(i.split(".")[0] for i in bk)
        fix_counter.update(v.fixability for v in sheets[k].blocking())
        backtracks = sum(1 for r in tr.rounds[1:] if r.branched_from != r.round - 1)
        gen = sum(r.cost_usd - s.cost_usd for r, s in zip(tr.rounds, sheets))
        ver = sum(s.cost_usd for s in sheets)
        rows.append([tr.shot_id, k + 1, "release" if tr.status == "output" else "hand-off", ", ".join(b0) or "none", ", ".join(bk) or "none",
                     backtracks, f"{gen:.2f}", f"{ver:.2f}"])
    t3 = md(rows, ["shot", "takes", "outcome", "blocking after take 1", "blocking at exit", "branches to an earlier round", "generation $", "verification $"])
    t4 = md([[c, r0[c], exit_counter[c]] for c in sorted(set(r0) | set(exit_counter))], ["check", "blocking after take 1", "blocking at exit"])
    fixes = ", ".join(f"{k} {v}" for k, v in fix_counter.most_common())
    lat = f"Generation latency per take: {min(latencies):.0f}–{max(latencies):.0f} s, median {sorted(latencies)[len(latencies)//2]:.0f} s ({len(latencies)} takes)." if latencies else ""
    return t3, t4 + f"\n\nFixability of the items still blocking at exit: {fixes}. {lat}"


def table_pilot_vs_panel():
    """The 2026-11-07 pilot take of DB-38: the single-prompt prototype judge vs the verifier panel."""
    proto = json.loads((ROOT.parent / "avharness/runs/pilot5_2026-11-07/DB-38/report.json").read_text())
    panel = FeedbackSheet.model_validate_json((ROOT / "runs/m45/DB-38/sheet.json").read_text())
    rows = [["prototype, one call with the checklist in the prompt", proto["decision"], sum(1 for v in proto["verdicts"] if v["status"] == "fail"), len(proto["verdicts"])],
            ["verifier panel", "continue" if panel.blocking() else "release", sum(1 for v in panel.verdicts if v.status == "fail"), len(panel.verdicts)]]
    return md(rows, ["verifier", "decision", "items failed", "items checked"]) + \
        "\n\nThe panel failed the phone call, the slipping portfolio, the scattering pages, the sound cue and the garbled on-paper text; a frame-by-frame check of the take confirmed all five."


def main() -> None:
    r30 = [json.loads(l) for l in (ROOT / "data/prompts/prompt_set_v2_30.jsonl").open()]
    t3, t4 = table_loop()
    text = "\n\n".join([
        "# Tables for the midway report\n\nGenerated by `scripts/report_tables.py` from the prompt set, the 30 checklists and the five loop runs of 2026-11-07/08. "
        "The runs used the panel configuration of 2026-11-07: verifiers gemini-3.5-flash-lite (two runs per family, item order swapped) and qwen3.8-omni-flash (one run), two blind descriptions, a text entailment pass for the A items, one re-inspect per uncertain item; Analyser gpt-5.6-luna. "
        "The code now defaults to one gemini-4-argon call per family and gemini-4-argon as the Analyser; that configuration has not been run end to end. Outcomes follow the stop rule of 2026-11-08: a shot is released only when no error remains; when every remaining error is backend-limited it is handed off.",
        "## Table 1. Prompt set\n\n" + table_data(r30),
        "## Table 2. Checklists written by the Analyser\n\n" + table_checklists(),
        "## Table 3. Loop runs, five shots, round cap 8\n\n" + t3,
        "## Table 4. Which checks blocked\n\n" + t4,
        "## Table 5. One take, two verifiers\n\n" + table_pilot_vs_panel(),
    ])
    OUT.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
