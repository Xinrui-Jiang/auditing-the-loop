"""M0 on real data: hand-written checklists for two shots, the five pilot feedback sheets re-expressed
in the new objects, the stop rule on them, a cache key, and one live cost record. Writes
data/examples/ and docs/pages/M0.html."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from module_page import Panel, Section, render  # noqa: E402

from loopauditor import schemas as S  # noqa: E402
from loopauditor.cache import cache_key, sha256_file  # noqa: E402
from loopauditor.config import PRIMARY_VERIFIER, PROMPT_SET_30, openrouter_key  # noqa: E402
from loopauditor.cost import fetch_generation_cost  # noqa: E402

PILOT_RUNS = ROOT.parent / "avharness/runs/pilot5_2026-11-07"
EXAMPLES = ROOT / "data/examples"
ROWS = {json.loads(l)["shot_id"]: json.loads(l) for l in PROMPT_SET_30.open()}


def item(id: str, kind: S.ItemKind, text: str, priority: S.Priority | None = None, **params) -> S.ChecklistItem:
    check = id.split(".")[0]
    default_priority, evidence = S.CHECK_DEFAULTS[check]
    return S.ChecklistItem(id=id, check_id=check, kind=kind, text=text, priority=priority or default_priority,
                           evidence=evidence, params=S.ItemParams(**params))


def rendering_items() -> list[S.ChecklistItem]:
    """B-family defaults, the same for every shot."""
    return [
        item("B1.1", "must_not", "Objects and liquids move plausibly: gravity, contact and momentum look normal."),
        item("B2.1", "must_not", "Hands, face and limbs stay anatomically normal; nothing morphs; no garbled text."),
        item("B3.1", "must_not", "The same face, voice and clothing persist through the whole take."),
        item("B4.1", "must_not", "No unintended cut, freeze, jump or loop."),
        item("B5.1", "must", "Lip movement matches the spoken line and the voice belongs to the person on screen."),
        item("B6.1", "must", "8 s, 9:16, 480p, audio track present."),
        item("B7.1", "must_not", "No subtitles, captions or watermarks."),
    ]


def spans(row: dict) -> list[str]:
    fields = ["setting", "character_description_source", "preceding_action", "speaker_cue", "parenthetical", "line",
              "following_action"]
    return [row[f] for f in fields if row.get(f)]


def checklist_db38(row: dict) -> S.Checklist:
    items = [
        item("A1.1", "must", 'The line "Grandma, they found me." is spoken in English, complete and verbatim.',
             line=row["line"], language="en"),
        item("A2.1", "must", "The phone call ends: she lowers or hangs up the phone.", element="The call ends."),
        item("A2.2", "must", "Haitong's portfolio slips out of her hands.", element="Haitong's portfolio slips."),
        item("A2.3", "must", "Pages scatter out of the portfolio.", element="Pages scatter"),
        item("A3.1", "must", "The setting is the stairwell of an old building, interior, daytime.", element=row["setting"]),
        item("A3.2", "must", "The scattering pages are audible (paper rustling or falling).", element=row["sfx_cue"]),
        item("A4.1", "must_not", "Only one person, Haitong, is on camera; nobody else appears."),
        item("A4.2", "must_not", "No unscripted event changes the scene (nobody enters, no cut to another place).", "major"),
        item("A5.1", "premise", "Haitong is 17 and has just lost a job offer over the phone; 'Grandma' is addressed but not present."),
        item("A6.1", "must", "Medium close-up, static camera at eye level, vertical 9:16, Haitong centred."),
        *rendering_items(),
        item("C1.1", "must", "The emotion is sadness (cue: crying)."),
        item("C2.1", "must", "Intensity is strong but not hysterical: face and voice within [2, 3] on the 0-4 scale.",
             target_interval=tuple(row["target_intensity_interval"])),
        item("C4.1", "must", "Delivery sounds like crying: broken voice, uneven pace."),
    ]
    return S.Checklist(shot_id=row["shot_id"], prompt=row["prompt"], script_spans=spans(row), items=items, author="manual")


def checklist_db16(row: dict) -> S.Checklist:
    items = [
        item("A1.1", "must", 'The line "He won\'t help us. Not after what I did." is spoken in English, complete and verbatim.',
             line=row["line"], language="en"),
        item("A2.1", "must", "She stares at the door.", element="She stares at the door."),
        item("A2.2", "must", "She blinks the memory away: a blink that clears her expression.", element="She blinks it away."),
        item("A3.1", "must", "The setting is the entrance of a house, exterior, daytime.", element=row["setting"]),
        item("A4.1", "must_not", "Only one person, Xu Zhiyi, is on camera; nobody else appears."),
        item("A4.2", "must_not", "No unscripted event changes the scene.", "major"),
        item("A5.1", "premise", "The memory (falling snow, another door, a betrayal) shows only on her face; the shot does not cut to a flashback."),
        item("A5.2", "premise", "Xu Zhiyi is 28 and looks exhausted but determined."),
        item("A6.1", "must", "Medium close-up, static camera at eye level, vertical 9:16, Xu Zhiyi centred."),
        *rendering_items(),
        item("C1.1", "must", f"The emotion class is {row['emotion_class']} (lexicon cue: {', '.join(row['emotion_cue'])})."),
        item("C2.1", "must", "Intensity is calm: face and voice within [0, 1] on the 0-4 scale.",
             target_interval=tuple(row["target_intensity_interval"])),
        item("C4.1", "must", "Delivery is quiet: low volume, soft tone."),
    ]
    return S.Checklist(shot_id=row["shot_id"], prompt=row["prompt"], script_spans=spans(row), items=items, author="manual")


OLD_TYPE_TO_CHECK = {"dialogue": "A1", "action": "A2", "sfx": "A3", "setting": "A3", "single_speaker": "A4",
                     "shot": "A6", "emotion": "C2"}


def import_pilot_sheet(shot_id: str) -> tuple[S.FeedbackSheet, str, str]:
    """Re-express a 2026-11-07 prototype report in M0 objects. Returns (sheet, old decision, old verdict table)."""
    report = json.loads((PILOT_RUNS / shot_id / "report.json").read_text())
    counters: dict[str, int] = {}
    new_id: dict[str, str] = {}
    for req in report["contract"]["requirements"]:
        check = OLD_TYPE_TO_CHECK[req["type"]]
        counters[check] = counters.get(check, 0) + 1
        new_id[req["id"]] = f"{check}.{counters[check]}"
    verdicts = []
    for v in report["verdicts"]:
        sig = v["confidence_signals"]
        verdicts.append(S.Verdict(
            item_id=new_id[v["requirement_id"]], status=v["status"], severity=v["severity"],
            uncertainty_state=v["uncertainty_state"], fixability=v["fixability"],
            signals=S.Signals(order_swap_agree=sig["order_swap_agree"], second_family_agree=sig["second_family_agree"],
                              tool_agree=sig["tool_agree"], visibility=sig["visibility"]),
            evidence=v["evidence"], deviation=v["deviation"], reinspected=v["escalated"]))
    meta = json.loads((ROOT / f"data/pilot_takes/{shot_id}/attempt1_seedance480.json").read_text())
    sheet = S.FeedbackSheet(shot_id=shot_id, round=0, take_sha256=meta["sha256"], verdicts=verdicts, cost_usd=report["cost_usd"])
    table = "\n".join(f"{v['requirement_id']:>3} {req['type']:<14} {v['status']:<9} {v['severity']:<8} {v['uncertainty_state']:<14} {v['fixability']}"
                      for v, req in zip(report["verdicts"], report["contract"]["requirements"]))
    return sheet, report["decision"], table


def schema_overview() -> str:
    lines = []
    for model in (S.ChecklistItem, S.Checklist, S.Take, S.Observation, S.RawVerdict, S.Signals, S.Verdict,
                  S.FeedbackSheet, S.Round, S.RevisionPlan, S.Trajectory, S.HandOffReport):
        fields = ", ".join(f"{n}: {str(f.annotation).replace('typing.', '').replace('loopauditor.schemas.', '')}"
                           for n, f in model.model_fields.items())
        lines.append(f"{model.__name__}\n    {fields}")
    return "\n\n".join(lines)


def main() -> None:
    (EXAMPLES / "checklists").mkdir(parents=True, exist_ok=True)
    (EXAMPLES / "sheets").mkdir(parents=True, exist_ok=True)
    sections = [Section("What M0 defines", "All objects later modules exchange. Priorities and evidence types come from "
                        "CHECK_DEFAULTS (PLAN.md §2); the stop rule lives in Verdict.blocks() / FeedbackSheet.blocking().",
                        inputs=[Panel("PLAN.md §7 M0", "schemas.py 271 lines, config.py 50, cache.py 43, cost.py 34; 13 tests pass.")],
                        outputs=[Panel("Objects and fields", schema_overview())])]

    for shot_id, build in (("DB-38", checklist_db38), ("DB-16", checklist_db16)):
        row = ROWS[shot_id]
        cl = build(row)
        path = EXAMPLES / "checklists" / f"{shot_id}.json"
        path.write_text(cl.model_dump_json(indent=2))
        row_view = {k: row[k] for k in ("shot_id", "line", "speaker_cue", "parenthetical", "emotion_class", "emotion_cue",
                                       "native_intensity_bin", "target_intensity_interval", "sfx_cue", "shot_scale", "camera")}
        sections.append(Section(
            f"Checklist for {shot_id} (hand-written, the way M1's Analyser will write it)",
            f"{len(cl.items)} items; {len(cl.script_spans)} script spans all found in the prompt (rule 2 check). Saved to {path.relative_to(ROOT)}.",
            inputs=[Panel("prompt", row["prompt"]), Panel("structured fields", json.dumps(row_view, ensure_ascii=False, indent=2))],
            outputs=[Panel("Checklist (JSON)", cl.model_dump_json(indent=2))]))

    for shot_id in ("DB-38", "DB-60", "DB-16", "DB-35", "SB-01"):
        sheet, old_decision, table = import_pilot_sheet(shot_id)
        path = EXAMPLES / "sheets" / f"{shot_id}.json"
        path.write_text(sheet.model_dump_json(indent=2))
        blocking = sheet.blocking()
        outcome = "continue the loop" if blocking else "output the video"
        sections.append(Section(
            f"Feedback sheet for {shot_id}, imported from the 2026-11-07 pilot",
            f"Stop rule: {outcome}; prototype decision was '{old_decision}'. Saved to {path.relative_to(ROOT)}.",
            inputs=[Panel("prototype verdicts (id, type, status, severity, uncertainty, fixability)", table)],
            outputs=[Panel("blocking items (error + confident/uncertain + prompt/retry-fixable)",
                           json.dumps([{"item_id": v.item_id, "severity": v.severity, "uncertainty_state": v.uncertainty_state,
                                        "fixability": v.fixability, "evidence": v.evidence} for v in blocking], indent=2) or "[]"),
                     Panel("FeedbackSheet (JSON)", sheet.model_dump_json(indent=1))]))

    take = ROOT / "data/pilot_takes/DB-38/attempt1_seedance480.mp4"
    meta = json.loads((ROOT / "data/pilot_takes/DB-38/attempt1_seedance480.json").read_text())
    media_sha = sha256_file(take)
    key = cache_key(PRIMARY_VERIFIER, ROWS["DB-38"]["prompt"], media_sha)
    cost = fetch_generation_cost(meta["job_id"], openrouter_key())
    sections.append(Section(
        "Cache key and cost record",
        "The cache key fixes one (model, prompt, media) triple; the cost record is read back live from OpenRouter for the DB-38 pilot take.",
        inputs=[Panel("inputs", f"model: {PRIMARY_VERIFIER}\nprompt sha256: {ROWS['DB-38']['prompt_sha256']}\nmp4 sha256: {media_sha}\nrequest id: {meta['job_id']}")],
        outputs=[Panel("cache_key", key), Panel("GenerationCost (live)", cost.model_dump_json(indent=2))]))

    out = ROOT / "docs/pages/M0.html"
    out.write_text(render("LoopAuditor M0 — data objects", "Real data: two hand-written checklists, five pilot feedback sheets, the stop rule, a cache key, a live cost record.", sections))
    print(f"wrote {out} and {len(list(EXAMPLES.rglob('*.json')))} example files")


if __name__ == "__main__":
    main()
