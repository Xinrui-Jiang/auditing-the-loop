"""Verifier panel (PLAN.md §7 M4): three specialist verifiers, one per family (A script fidelity, B rendering
integrity, C dramatic performance). Each is one call to the verifier model with the take and that family's
items. The panel sees the take and the checklist only; it never sees the trajectory."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .cache import Cache, sha256_file
from .config import VERIFIER_MODEL
from .openrouter import chat_json_video
from .schemas import Checklist, ChecklistItem, Family, Observation, RawVerdict

STATUSES = ("pass", "fail", "uncertain", "not_applicable")
VISIBILITIES = ("seen_clearly", "partially_seen", "not_observable")

FAMILY_BRIEF: dict[str, str] = {
    "A": "You check whether the clip shows what the script asks. Rely only on what is visible and audible. "
         "An event that never appears is status fail with visibility seen_clearly, not uncertain. A named object "
         "must be that object: a clipboard is not a portfolio, a cup is not a bottle.",
    "B": "You check picture and sound integrity: anatomy, morphing, identity continuity, unintended cuts or freezes, "
         "lip sync, on-screen text. Look at hands and faces closely across the whole clip.",
    "C": "You check the performance: emotion class, intensity, timing, delivery and tone. Rate face and voice "
         "intensity from 0 to 4 (0 flat, 1 mild, 2 clear, 3 strong, 4 extreme) for every item that names an emotion.",
}

OUTPUT_SHAPE = """Watch and listen to the whole clip first. Then answer every item. Return JSON only:
{"items": {"<item id>": {"status": "pass" | "fail" | "uncertain" | "not_applicable",
                         "visibility": "seen_clearly" | "partially_seen" | "not_observable",
                         "evidence": "<one sentence citing MM:SS>",
                         "span": [start_seconds, end_seconds] | null,
                         "face_intensity": 0-4 | null, "voice_intensity": 0-4 | null}}}
"visibility" says how well the clip lets you check the item: seen_clearly when the relevant moment is well visible
or audible, partially_seen when it is partly visible or ambiguous, not_observable when the clip cannot show it.
An absent event is seen_clearly + fail. Use uncertain only when the clip could contain it and you cannot tell."""


class PanelError(RuntimeError):
    pass


def _item_line(i: ChecklistItem) -> str:
    extra = ""
    if i.params.line:
        extra = f' (expected line: "{i.params.line}", language {i.params.language})'
    if i.params.target_interval:
        extra = f" (target intensity {list(i.params.target_interval)} on the 0-4 scale)"
    return f"- {i.id} [{i.kind}]: {i.text}{extra}"


def specialist_prompt(family: Family, items: list[ChecklistItem]) -> str:
    return f"{FAMILY_BRIEF[family]}\n\nITEMS:\n" + "\n".join(_item_line(i) for i in items) + "\n\n" + OUTPUT_SHAPE


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


def _ask(family: Family, items: list[ChecklistItem], video: Path, sha: str, cache: Cache) -> tuple[list[RawVerdict], list[Observation]]:
    """One specialist call; one retry with the parse error quoted; then PanelError."""
    source = f"{family}/verifier"
    prompt = specialist_prompt(family, items)
    data, obs = chat_json_video(VERIFIER_MODEL, prompt, video, sha, source, cache)
    try:
        return parse_items(data, items, source), [obs]
    except PanelError as first:
        retry = prompt + f"\n\nYour previous answer was rejected: {first}. Answer every item in the exact shape."
        data, obs2 = chat_json_video(VERIFIER_MODEL, retry, video, sha, source + "/retry", cache)
        return parse_items(data, items, source), [obs, obs2]


def verify(video: Path, checklist: Checklist, cache: Cache | None = None) -> tuple[list[RawVerdict], list[Observation]]:
    """The three specialist calls, in parallel."""
    cache = cache or Cache()
    sha = sha256_file(video)
    families = [f for f in ("A", "B", "C") if checklist.family(f)]
    raws: list[RawVerdict] = []
    observations: list[Observation] = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        for v, o in pool.map(lambda f: _ask(f, checklist.family(f), video, sha, cache), families):
            raws += v
            observations += o
    return raws, observations
