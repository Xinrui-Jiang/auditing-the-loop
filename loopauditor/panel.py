"""Verifier panel (PLAN.md §7 M4): a blind description of the take, three specialist verifiers (A script,
B rendering, C performance) run twice with the item order swapped on the primary model and once on a second
model family, a text entailment pass for the A items, and a targeted re-inspect for uncertain items.
The panel sees the take and the checklist only; it never sees the trajectory."""
from __future__ import annotations

import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .cache import Cache, sha256_file
from .config import ANALYSER_MODEL, PRIMARY_VERIFIER, SECOND_FAMILY_VERIFIER
from .openrouter import chat_json, chat_json_video
from .schemas import Checklist, ChecklistItem, Family, Observation, RawVerdict

STATUSES = ("pass", "fail", "uncertain", "not_applicable")
VISIBILITIES = ("seen_clearly", "partially_seen", "not_observable")

DESCRIBE = """Watch and listen to the whole clip. Describe only what you see and hear, in time order. Do not guess
intentions or story. Return JSON only:
{"people": [{"id": "P1", "description": "<looks, clothing>", "on_screen": "MM:SS-MM:SS"}],
 "events": [{"start": "MM:SS", "end": "MM:SS", "channel": "visual" | "audio", "description": "<what happens or sounds>"}],
 "speech": [{"start": "MM:SS", "end": "MM:SS", "speaker": "P1", "text": "<exact words heard>", "language": "<language>"}],
 "face_over_time": [{"start": "MM:SS", "end": "MM:SS", "expression": "<what the face does>"}],
 "camera": "<shot scale, movement, framing>",
 "artifacts": ["<any visual or audio glitch: extra fingers, morphing, flicker, cuts, freezes, garbled text, desync>"]}"""

FAMILY_BRIEF: dict[str, str] = {
    "A": "You check whether the clip shows what the script asks. Rely only on what is visible and audible. "
         "An event that never appears is status fail with visibility seen_clearly, not uncertain.",
    "B": "You check picture and sound integrity: anatomy, morphing, identity continuity, unintended cuts or freezes, "
         "lip sync, on-screen text. Look at hands and faces closely across the whole clip.",
    "C": "You check the performance: emotion class, intensity, timing, delivery and tone. Rate face and voice "
         "intensity from 0 to 4 (0 flat, 1 mild, 2 clear, 3 strong, 4 extreme) for every item that names an emotion.",
}

OUTPUT_SHAPE = """Return JSON only:
{"items": {"<item id>": {"status": "pass" | "fail" | "uncertain" | "not_applicable",
                         "visibility": "seen_clearly" | "partially_seen" | "not_observable",
                         "evidence": "<one sentence citing MM:SS>",
                         "span": [start_seconds, end_seconds] | null,
                         "face_intensity": 0-4 | null, "voice_intensity": 0-4 | null}}}
Every item id must appear. "visibility" says how well the clip lets you check the item; an absent event is
seen_clearly + fail. Use uncertain only when the clip could contain it and you cannot tell."""


class PanelError(RuntimeError):
    pass


def _item_line(i: ChecklistItem) -> str:
    extra = ""
    if i.params.line:
        extra = f' (expected line: "{i.params.line}", language {i.params.language})'
    if i.params.target_interval:
        extra = f" (target intensity {list(i.params.target_interval)} on the 0-4 scale)"
    return f"- {i.id} [{i.kind}]: {i.text}{extra}"


def specialist_prompt(family: Family, items: list[ChecklistItem], description: str) -> str:
    return (f"{FAMILY_BRIEF[family]}\n\nA description of the clip, written by a model that did not see the checklist, "
            f"is given for reference. Verify against the clip itself.\nDESCRIPTION:\n{description}\n\nITEMS:\n"
            + "\n".join(_item_line(i) for i in items) + "\n\n" + OUTPUT_SHAPE)


def parse_items(data: dict, items: list[ChecklistItem], source: str) -> list[RawVerdict]:
    """Strict: every item must be answered with a valid status and visibility."""
    block = data.get("items")
    if not isinstance(block, dict):
        raise PanelError(f"{source}: no 'items' object in the answer")
    out = []
    for i in items:
        a = block.get(i.id)
        if not isinstance(a, dict) or a.get("status") not in STATUSES or a.get("visibility") not in VISIBILITIES:
            raise PanelError(f"{source}: item {i.id} missing or malformed: {a!r}")
        span = a.get("span")
        out.append(RawVerdict(item_id=i.id, source=source, status=a["status"], visibility=a["visibility"],
                              evidence=str(a.get("evidence", "")), span=tuple(span) if span else None,
                              face_intensity=a.get("face_intensity"), voice_intensity=a.get("voice_intensity")))
    return out


def _ask(model: str, prompt: str, video: Path, sha: str, items: list[ChecklistItem], source: str, cache: Cache) -> tuple[list[RawVerdict], list[Observation]]:
    """One specialist call; one retry with the parse error quoted; then PanelError."""
    data, obs = chat_json_video(model, prompt, video, sha, source, cache)
    try:
        return parse_items(data, items, source), [obs]
    except PanelError as first:
        retry = prompt + f"\n\nYour previous answer was rejected: {first}. Answer every item in the exact shape."
        data, obs2 = chat_json_video(model, retry, video, sha, source + "/retry", cache)
        return parse_items(data, items, source), [obs, obs2]


def describe(video: Path, sha: str, model: str, cache: Cache) -> tuple[str, Observation]:
    data, obs = chat_json_video(model, DESCRIBE, video, sha, f"describe/{model}", cache)
    return json.dumps(data, ensure_ascii=False), obs


def entailment(items: list[ChecklistItem], descriptions: list[str], cache: Cache) -> tuple[list[RawVerdict], Observation]:
    """A-family items judged from the blind descriptions alone, by a text model."""
    system = ("You judge whether descriptions of a video clip, written without any checklist, support each item. "
              "pass = the descriptions show it; fail = the descriptions show it did not happen or something contradicts it; "
              "uncertain = the descriptions do not say. Quote the description in the evidence. Return JSON only: "
              '{"items": {"<id>": {"status": "pass" | "fail" | "uncertain", "evidence": "<quote>"}}}')
    user = "DESCRIPTIONS:\n" + "\n\n".join(descriptions) + "\n\nITEMS:\n" + "\n".join(_item_line(i) for i in items)
    data, obs = chat_json(ANALYSER_MODEL, system, user, "A/entailment", cache)
    block = data.get("items")
    if not isinstance(block, dict):
        raise PanelError("A/entailment: no 'items' object")
    out = []
    for i in items:
        a = block.get(i.id)
        if not isinstance(a, dict) or a.get("status") not in ("pass", "fail", "uncertain"):
            raise PanelError(f"A/entailment: item {i.id} missing or malformed: {a!r}")
        visibility = "partially_seen" if a["status"] == "uncertain" else "seen_clearly"
        out.append(RawVerdict(item_id=i.id, source="A/entailment", status=a["status"], visibility=visibility, evidence=str(a.get("evidence", ""))))
    return out, obs


def verify(video: Path, checklist: Checklist, cache: Cache | None = None) -> tuple[list[RawVerdict], list[Observation]]:
    """All panel evidence for one take, before aggregation (M5) and before any re-inspect.
    The two descriptions run in parallel, then the nine specialist calls run in parallel."""
    cache = cache or Cache()
    sha = sha256_file(video)
    raws: list[RawVerdict] = []
    observations: list[Observation] = []
    with ThreadPoolExecutor(max_workers=9) as pool:
        described = list(pool.map(lambda m: (m, describe(video, sha, m, cache)), (PRIMARY_VERIFIER, SECOND_FAMILY_VERIFIER)))
        descriptions = {m: text for m, (text, _) in described}
        observations += [obs for _, (_, obs) in described]
        calls = []
        for family in ("A", "B", "C"):
            items = checklist.family(family)
            if not items:
                continue
            for order, ordered in (("order1", items), ("order2", list(reversed(items)))):
                calls.append((PRIMARY_VERIFIER, specialist_prompt(family, ordered, descriptions[PRIMARY_VERIFIER]), items, f"{family}/primary/{order}"))
            calls.append((SECOND_FAMILY_VERIFIER, specialist_prompt(family, items, descriptions[SECOND_FAMILY_VERIFIER]), items, f"{family}/second"))
        for v, o in pool.map(lambda c: _ask(c[0], c[1], video, sha, c[2], c[3], cache), calls):
            raws += v
            observations += o
    a_items = checklist.family("A")
    if a_items:
        v, o = entailment(a_items, list(descriptions.values()), cache)
        raws += v
        observations.append(o)
    return raws, observations


def reinspect(video: Path, item: ChecklistItem, span: tuple[float, float] | None, out_dir: Path, cache: Cache | None = None) -> tuple[RawVerdict, list[Observation]]:
    """Cut the cited interval (one second of margin) and ask the primary model about this item only."""
    cache = cache or Cache()
    start, end = (max(0.0, span[0] - 1.0), span[1] + 1.0) if span else (0.0, 999.0)
    clip = out_dir / f"reinspect_{item.id}.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.2f}", "-to", f"{end:.2f}", "-i", str(video),
                    "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", str(clip)], check=True)
    family = item.family
    prompt = (f"{FAMILY_BRIEF[family]}\nThis clip is the part of the take from {start:.1f}s to {end:.1f}s. "
              f"Watch it several times and answer this one item. Times in your evidence are relative to this clip.\n\nITEMS:\n"
              + _item_line(item) + "\n\n" + OUTPUT_SHAPE)
    verdicts, obs = _ask(PRIMARY_VERIFIER, prompt, clip, sha256_file(clip), [item], f"{family}/reinspect", cache)
    return verdicts[0], obs
