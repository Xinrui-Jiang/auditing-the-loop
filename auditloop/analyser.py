"""Analyser, round 0: writes the checklist for one shot (PLAN.md §7 M1).

Structured fields of the prompt row become items by rule. A text LLM reads the script and lists
actions, elements, the other people the script puts in the scene, and premise facts, each tied to a
verbatim span of the script. Who belongs in the frame is therefore decided here, per shot, from the
script. Rules then assign check ids and priorities from CHECK_DEFAULTS; the LLM never sets a priority.
"""
from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel

from .cache import Cache
from .config import ANALYSER_MODEL
from .openrouter import chat_json
from .schemas import CHECK_DEFAULTS, Checklist, ChecklistItem, ItemParams, Observation, Priority, normalise

MIN_ITEMS, MAX_ITEMS = 8, 24
SPAN_FIELDS = ("setting", "character_description_source", "preceding_action", "speaker_role", "parenthetical",
               "line", "following_action")

SYSTEM = """You read the script of one short-drama shot: one speaker, one spoken line, a few actions.
List what a video verifier must check. Answer with JSON only, in exactly this shape:
{"actions": [{"span": "<text copied exactly from the script>", "check": "<one sentence: what must be seen on screen>"}],
 "elements": [{"span": "<copied exactly>", "kind": "prop" | "setting" | "sound", "check": "<one sentence>"}],
 "other_people": ["<each person other than the speaker whom the script shows physically in the scene, seen or acting, written as the script names them (a name or a role such as HUSBAND); never a pronoun; never someone only mentioned, addressed, remembered or heard on a phone>"],
 "premise": [{"fact": "<one sentence a viewer must not see contradicted, e.g. 'the memory shows only on her face; the shot stays in the present'>", "span": "<copied exactly>"}],
 "transition_scripted": true | false,
 "physics_involved": true | false}
Rules: every span is copied exactly from the script, character for character, never reworded or shortened in the
middle. Do not list the spoken line as an action. Do not invent props, sounds or people. Only what the script states
or clearly implies. Keep the lists short."""


class ChecklistError(ValueError):
    """The extraction cannot be turned into a valid checklist. Nothing is dropped silently."""


class SpanCheck(BaseModel):
    span: str
    check: str


class Element(SpanCheck):
    kind: Literal["prop", "setting", "sound"]


class Premise(BaseModel):
    fact: str
    span: str


class Extraction(BaseModel):
    actions: list[SpanCheck]
    elements: list[Element]
    other_people: list[str]
    premise: list[Premise]
    transition_scripted: bool
    physics_involved: bool


def script_text(row: dict) -> str:
    return (f"SCRIPT (verbatim):\n{row['prompt_raw']}\n\n"
            f"Speaker: {row['speaker_role']}\nSpoken line: \"{row['line']}\"\n"
            f"Delivery cue: {row['parenthetical'] or 'none'}\nSound cue: {row['sfx_cue'] or 'none'}")


def bad_spans(extraction: Extraction, script: str) -> list[str]:
    text = normalise(script)
    spans = [a.span for a in extraction.actions] + [e.span for e in extraction.elements] + [p.span for p in extraction.premise]
    return [s for s in spans if normalise(s) not in text]


def _item(id: str, kind: str, text: str, priority: Priority | None = None, **params) -> ChecklistItem:
    check = id.split(".")[0]
    default_priority, evidence = CHECK_DEFAULTS[check]
    return ChecklistItem(id=id, check_id=check, kind=kind, text=text, priority=priority or default_priority,
                         evidence=evidence, params=ItemParams(**params))


OTHER_GENDER_PRONOUNS = {"female": ("he", "his", "him"), "male": ("she", "her", "hers")}


def _unnamed_other_person(row: dict) -> str | None:
    """Scripts often show a second person only through a pronoun ("He smashes the jade" while a woman speaks).
    A pronoun of the other gender in the action lines means someone else is in the scene."""
    pronouns = OTHER_GENDER_PRONOUNS.get(row["speaker_gender"])
    if not pronouns:
        return None
    words = {w.strip(".,;:!?—\"'()").lower() for f in ("preceding_action", "following_action") if row[f] for w in row[f].split()}
    if words & set(pronouns):
        return "the man" if row["speaker_gender"] == "female" else "the woman"
    return None


def _script_items(row: dict, x: Extraction) -> tuple[list[ChecklistItem], list[str]]:
    speaker = row["speaker_role"]  # the cue may carry (CONT'D), which the prompt does not render
    line = normalise(row["line"])
    cue = normalise(row["parenthetical"] or "")
    items = [_item("A1.1", "must", f'The line "{row["line"]}" is spoken in English, complete and verbatim.',
                   line=row["line"], language="en")]
    # the spoken line is checked by A1; the delivery cue is checked by C4
    actions = [a for a in x.actions if line not in normalise(a.span) and not (cue and normalise(a.span).strip("()") in cue)]
    items += [_item(f"A2.{k}", "must", a.check, element=a.span) for k, a in enumerate(actions, 1)]
    elements: list[tuple[str, str]] = []
    if row["setting"]:
        elements.append((f"The setting matches the heading: {row['setting']}.", row["setting"]))
    if row["sfx_cue"]:
        elements.append((f"The scripted sound is audible: {row['sfx_cue']}", row["sfx_cue"]))
    for e in x.elements:
        if (e.kind == "setting" and row["setting"]) or (e.kind == "sound" and row["sfx_cue"]):
            continue  # the rule item above already covers it
        elements.append((e.check, e.span))
    items += [_item(f"A3.{k}", "must", check, element=span) for k, (check, span) in enumerate(elements, 1)]
    conflicts: list[str] = []
    cast = [speaker] + list(x.other_people)
    unnamed = _unnamed_other_person(row)
    if unnamed and not x.other_people:
        cast.append(unnamed)
        conflicts.append(f"a pronoun in the action line refers to someone other than {speaker}; '{unnamed}' added to the cast")
    items.append(_item("A4.1", "must_not", f"Everyone on screen is in the script's cast: {', '.join(cast)}. Nobody else appears."))
    items.append(_item("A4.2", "must_not", f"Only {speaker} speaks; no other voice says a line.", "major"))
    items.append(_item("A4.3", "must_not", "No unscripted event changes the scene: nobody enters, no cut to another place.", "major"))
    items += [_item(f"A5.{k}", "premise", p.fact) for k, p in enumerate(x.premise, 1)]
    items.append(_item("A6.1", "must", f"{row['shot_scale']}, {row['camera']}, vertical 9:16, {speaker} centred."))
    return items, conflicts


def _rendering_items(physics_involved: bool) -> list[ChecklistItem]:
    return [
        _item("B1.1", "must_not", "Objects and liquids move plausibly: gravity, contact and momentum look normal.",
              "major" if physics_involved else None),
        _item("B2.1", "must_not", "Hands, face and limbs stay anatomically normal; nothing morphs; no garbled text."),
        _item("B3.1", "must_not", "The same face, voice and clothing persist through the whole take."),
        _item("B4.1", "must_not", "No unintended cut, freeze, jump or loop."),
        _item("B5.1", "must", "Lip movement matches the spoken line and the voice belongs to the person on screen."),
        _item("B6.1", "must", f"8 s, 9:16, 480p, audio track present."),
        _item("B7.1", "must_not", "No subtitles, captions or watermarks."),
    ]


def _performance_items(row: dict, x: Extraction) -> list[ChecklistItem]:
    lo, hi = row["target_intensity_interval"]
    items = [
        _item("C1.1", "must", f"The emotion is {row['emotion_class']} (cues: {', '.join(row['emotion_cue'])})."),
        _item("C2.1", "must", f"Face and voice intensity within [{lo}, {hi}] on the 0-4 scale ({row['native_intensity_bin']}).",
              target_interval=(lo, hi)),
    ]
    if x.transition_scripted:
        items.append(_item("C3.1", "must", "The scripted emotional turn happens, at the moment the script places it."))
    if row["parenthetical"]:
        items.append(_item("C4.1", "must", f"Delivery matches the cue '{row['parenthetical']}'."))
    return items


def assemble(row: dict, extraction: Extraction, author: str) -> Checklist:
    items, conflicts = _script_items(row, extraction)
    items += _rendering_items(extraction.physics_involved)
    items += _performance_items(row, extraction)
    if not MIN_ITEMS <= len(items) <= MAX_ITEMS:
        raise ChecklistError(f"{row['shot_id']}: {len(items)} items, expected {MIN_ITEMS}-{MAX_ITEMS}")
    spans = [row[f] for f in SPAN_FIELDS if row[f]]
    return Checklist(shot_id=row["shot_id"], prompt=row["prompt"], script_spans=spans, items=items,
                     conflicts=conflicts, author=author)


MAX_ATTEMPTS = 3


def write_checklist(row: dict, model: str = ANALYSER_MODEL, cache: Cache | None = None) -> tuple[Checklist, list[Observation]]:
    """Round 0 of the Analyser. Up to two retries when the LLM reworded spans; then an explicit error."""
    user = script_text(row)
    observations: list[Observation] = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        data, observation = chat_json(model, SYSTEM, user, source=f"analyser/checklist/attempt{attempt}", cache=cache)
        observations.append(observation)
        extraction = Extraction.model_validate(data)
        bad = bad_spans(extraction, row["prompt_raw"])
        if not bad:
            return assemble(row, extraction, author=observation.model_id), observations
        user = script_text(row) + "\n\nYour previous answer contained spans that are not in the script: " + json.dumps(bad) + \
            ". A span must be copied character for character. Copy from these script lines only:\n" + \
            "\n".join(f"- {line}" for line in row["prompt_raw"].split("\n"))
    raise ChecklistError(f"{row['shot_id']}: spans not in the script after {MAX_ATTEMPTS} attempts: {bad}")
