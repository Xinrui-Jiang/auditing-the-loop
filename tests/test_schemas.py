"""M0: every object round-trips through JSON; validators reject bad data; blocks() follows PLAN.md §4."""
import pytest
from pydantic import ValidationError

from loopauditor.schemas import (
    Checklist, ChecklistItem, FeedbackSheet, HandOffReport, ItemParams, Observation, RawVerdict,
    RevisionPlan, Round, Signals, Take, Trajectory, Verdict,
)

PROMPT = 'INT. ROOM - DAY. ANNA (30). She closes the door. ANNA, quietly, says: "Leave me alone."'


def item(id="A1.1", check="A1", **params):
    defaults = {"A1": dict(line="Leave me alone.", language="en"), "A2": dict(element="closes the door"),
                "A3": dict(element="door"), "C2": dict(target_interval=(0, 1))}
    p = {**defaults.get(check, {}), **params}
    return ChecklistItem(id=id, check_id=check, kind="must", text="q", priority="major", evidence="panel",
                         params=ItemParams(**p))


def checklist(items=None, spans=None):
    return Checklist(shot_id="T-1", prompt=PROMPT, script_spans=spans or ["She closes the door.", "Leave me alone."],
                     items=items or [item()], author="manual")


def signals():
    return Signals(order_swap_agree=True, second_family_agree=True, tool_agree=None, visibility="seen_clearly")


def verdict(severity="error", state="confident", fix="prompt_fixable", status="fail"):
    return Verdict(item_id="A1.1", status=status, severity=severity, uncertainty_state=state, fixability=fix,
                   signals=signals(), evidence=["0.0-2.0s: line spoken in Chinese"])


def test_round_trip_all_objects():
    objects = [
        checklist(),
        Take(shot_id="T-1", round=0, path="runs/T-1/rounds/0/take.mp4", backend="seedance-2.0", seed=None,
             duration_s=8, resolution="480p", aspect_ratio="9:16", prompt_sha256="a" * 64, sha256="b" * 64,
             cost_usd=0.54, request_id="gen-1", latency_s=61.2),
        Observation(source="tool/asr", model_id="mlx-whisper large-v3", request_id=None, cost_usd=0.0,
                    text="Leave me alone.", raw_path=None),
        RawVerdict(item_id="A1.1", source="A/primary/order1", status="pass", visibility="seen_clearly",
                   evidence="line heard", span=(1.0, 2.5)),
        verdict(),
        FeedbackSheet(shot_id="T-1", round=0, take_sha256="b" * 64, verdicts=[verdict()], cost_usd=0.04),
        Round(round=0, prompt=PROMPT, branched_from=None, rationale="", targets=[], take_path="t", sheet_path="s",
              cost_usd=0.58),
        RevisionPlan(branch_from=0, revised_prompt=PROMPT + " She speaks English.", rationale="r", targets=["A1.1"]),
        Trajectory(shot_id="T-1", checklist_path="c.json"),
        HandOffReport(shot_id="T-1", best_round=2, reason="round cap", open_item_ids=["A1.1"], trajectory_path="t.json"),
    ]
    for obj in objects:
        again = type(obj).model_validate_json(obj.model_dump_json())
        assert again == obj


def test_checklist_rejects_duplicate_ids():
    with pytest.raises(ValidationError, match="unique"):
        checklist(items=[item(), item()])


def test_checklist_rejects_span_missing_from_prompt():
    with pytest.raises(ValidationError, match="missing from the prompt"):
        checklist(spans=["She opens the window."])


def test_missing_spans_ignores_whitespace():
    assert checklist().missing_spans("she  closes the\ndoor.".replace("she", "She") + ' "Leave me alone."') == []


def test_a1_needs_line_and_language():
    with pytest.raises(ValidationError, match="needs params.language"):
        ChecklistItem(id="A1.1", check_id="A1", kind="must", text="q", priority="critical", evidence="tool",
                      params=ItemParams(line="x"))


def test_interval_and_intensity_ranges():
    with pytest.raises(ValidationError):
        ItemParams(target_interval=(3, 5))
    with pytest.raises(ValidationError):
        RawVerdict(item_id="C2.1", source="C/primary/order1", status="pass", visibility="seen_clearly",
                   evidence="", face_intensity=5)


@pytest.mark.parametrize("severity,state,fix,expected", [
    ("error", "confident", "prompt_fixable", True),
    ("error", "uncertain", "retry_fixable", True),
    ("error", "confident", "backend_limited", True),  # blocks the output; the loop hands off instead of retrying
    ("error", "not_observable", "prompt_fixable", False),
    ("warning", "confident", "prompt_fixable", False),
    ("info", "confident", "prompt_fixable", False),
])
def test_blocks_follows_stop_rule(severity, state, fix, expected):
    assert verdict(severity, state, fix).blocks() is expected


def test_unfixable_is_the_hand_off_condition():
    sheet = FeedbackSheet(shot_id="T-1", round=2, take_sha256="b" * 64, cost_usd=0.0,
                          verdicts=[verdict("error", "confident", "backend_limited"), verdict("info", "confident", "prompt_fixable", status="pass")])
    assert [v.item_id for v in sheet.unfixable()] == ["A1.1"] and len(sheet.unfixable()) == len(sheet.blocking())


def test_trajectory_round_order_and_branching():
    r0 = Round(round=0, prompt="p", branched_from=None, rationale="", targets=[], take_path="t", sheet_path="s", cost_usd=0)
    r1 = Round(round=1, prompt="p2", branched_from=0, rationale="fix A1", targets=["A1.1"], take_path="t", sheet_path="s", cost_usd=0)
    Trajectory(shot_id="T-1", checklist_path="c", rounds=[r0, r1])
    with pytest.raises(ValidationError, match="cannot branch"):
        Trajectory(shot_id="T-1", checklist_path="c", rounds=[r0, r1.model_copy(update={"branched_from": 1})])
    with pytest.raises(ValidationError, match="output_round"):
        Trajectory(shot_id="T-1", checklist_path="c", rounds=[r0], status="output")


def test_hand_off_without_any_take_has_no_output_round():
    Trajectory(shot_id="T-1", checklist_path="c", status="hand_off")
    with pytest.raises(ValidationError, match="does not exist"):
        r0 = Round(round=0, prompt="p", branched_from=None, rationale="", targets=[], take_path="t", sheet_path="s", cost_usd=0)
        Trajectory(shot_id="T-1", checklist_path="c", rounds=[r0], status="output", output_round=3)
