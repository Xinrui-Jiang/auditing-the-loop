"""M5: the three label tables of PLAN.md §5 on synthetic verifier and tool answers."""
import pytest

from loopauditor.labels import aggregate, fixability_of, severity_of
from loopauditor.schemas import ChecklistItem, ItemParams, RawVerdict


def item(check="A2", priority="critical", **params):
    if check == "A2":
        params.setdefault("element", "closes the door")
    return ChecklistItem(id=f"{check}.1", check_id=check, kind="must", text="q", priority=priority, evidence="panel", params=ItemParams(**params))


def raw(source, status, visibility="seen_clearly", **kw):
    return RawVerdict(item_id=kw.pop("item_id", "A2.1"), source=source, status=status, visibility=visibility, evidence="e", **kw)


@pytest.mark.parametrize("priority,status,state,expected", [
    ("critical", "fail", "confident", "error"), ("critical", "fail", "uncertain", "error"),
    ("major", "fail", "confident", "error"), ("major", "fail", "uncertain", "warning"),
    ("minor", "fail", "confident", "warning"), ("major", "fail", "not_observable", "info"),
    ("critical", "pass", "confident", "info"),
])
def test_severity_table(priority, status, state, expected):
    assert severity_of(priority, status, state) == expected


def test_uncertainty_from_visibility_without_tool():
    assert aggregate(item(), [raw("A/verifier", "fail")], []).uncertainty_state == "confident"
    assert aggregate(item(), [raw("A/verifier", "fail", "partially_seen")], []).uncertainty_state == "uncertain"
    v = aggregate(item(), [raw("A/verifier", "fail", "not_observable")], [])
    assert v.uncertainty_state == "not_observable" and v.severity == "info"


def test_tool_decides_a1_and_sets_state():
    a1 = item("A1", line="x", language="en")
    runs = [raw("A/verifier", "pass", item_id="A1.1"), raw("tool/asr", "fail", item_id="A1.1", value=1.0)]
    v = aggregate(a1, runs, [])
    assert v.status == "fail" and v.uncertainty_state == "uncertain" and v.deviation == 1.0 and v.signals.tool_agree is False
    runs[-1] = raw("tool/asr", "pass", item_id="A1.1", value=0.0)
    assert aggregate(a1, runs, []).uncertainty_state == "confident"


def test_c2_intensity_mean_decides():
    c2 = item("C2", priority="major", target_interval=(0, 1))
    v = aggregate(c2, [raw("C/verifier", "pass", item_id="C2.1", face_intensity=3, voice_intensity=2)], [])
    assert v.status == "fail" and v.deviation == 1.5 and v.severity == "error"


def test_fixability_prior_and_history():
    assert fixability_of("A1", "fail", []) == "prompt_fixable"
    assert fixability_of("A1", "fail", ["fail", "fail"]) == "backend_limited"
    assert fixability_of("A2", "fail", ["pass", "fail"]) == "retry_fixable"
    assert fixability_of("B5", "fail", []) == "backend_limited"


def test_no_evidence_is_an_error():
    with pytest.raises(ValueError):
        aggregate(item(), [], [])
