"""Label aggregation (PLAN.md §7 M5): the verifier's answers and the tools' answers -> one Verdict per item with
the three labels, following the tables in PLAN.md §5. No model-reported confidence takes part."""
from __future__ import annotations

from pathlib import Path

import yaml

from .schemas import Checklist, ChecklistItem, FeedbackSheet, Fixability, RawVerdict, Severity, Signals, Status, UncertaintyState, Verdict

FIXABILITY_PRIOR: dict[str, Fixability] = yaml.safe_load((Path(__file__).parent / "fixability_prior.yaml").read_text())
TOOL_DECIDES = {"A1", "B6"}  # the tool's answer is the status; the verifier only adds agreement
BACKEND_LIMITED_AFTER = 2  # failed prompt revisions before an item counts as backend-limited


def _intensity_status(item: ChecklistItem, run: RawVerdict) -> tuple[Status | None, float | None]:
    """C2: the mean of the two reported intensities decides."""
    readings = [x for x in (run.face_intensity, run.voice_intensity) if x is not None]
    if item.check_id != "C2" or not readings:
        return None, None
    lo, hi = item.params.target_interval
    mean = sum(readings) / len(readings)
    deviation = 0.0 if lo <= mean <= hi else (mean - hi if mean > hi else mean - lo)
    return ("pass" if deviation == 0 else "fail"), round(deviation, 2)


def severity_of(priority: str, status: Status, state: UncertaintyState) -> Severity:
    if state == "not_observable" or status != "fail":
        return "info"
    if priority == "critical":
        return "error"
    if priority == "major":
        return "error" if state == "confident" else "warning"
    return "warning"


def fixability_of(check_id: str, status: Status, previous: list[Status]) -> Fixability:
    """Prior per check, then the trajectory: BACKEND_LIMITED_AFTER failed revisions -> backend_limited;
    pass/fail flipping across rounds -> retry_fixable."""
    if status == "fail" and len(previous) >= BACKEND_LIMITED_AFTER and all(s == "fail" for s in previous[-BACKEND_LIMITED_AFTER:]):
        return "backend_limited"
    if "pass" in previous and "fail" in previous:
        return "retry_fixable"
    return FIXABILITY_PRIOR[check_id]


def aggregate(item: ChecklistItem, raws: list[RawVerdict], previous: list[Status]) -> Verdict:
    mine = [r for r in raws if r.item_id == item.id]
    verifier = [r for r in mine if r.source.endswith("/verifier")]
    tools = [r for r in mine if r.source.startswith("tool/")]
    if not verifier and not tools:
        raise ValueError(f"no evidence for item {item.id}")
    run = verifier[0] if verifier else None
    visibility = run.visibility if run else "seen_clearly"
    status, deviation = _intensity_status(item, run) if run else (None, None)
    if status is None:
        status = run.status if run else tools[0].status
    if tools and item.check_id in TOOL_DECIDES:
        status, deviation = tools[0].status, tools[0].value
    tool_agree = (tools[0].status == run.status) if tools and run else None
    # uncertainty: a tool that agrees with the verifier settles it; without a tool, the verifier's own
    # observability judgement decides (seen clearly -> confident, partly seen -> uncertain, else not observable)
    if visibility == "not_observable":
        state: UncertaintyState = "not_observable"
    elif tools:
        state = "confident" if tool_agree or run is None else "uncertain"
    else:
        state = "confident" if visibility == "seen_clearly" and status != "uncertain" else "uncertain"
    evidence = [f"{r.source}: {r.evidence}" for r in mine if r.evidence]
    return Verdict(item_id=item.id, status=status, severity=severity_of(item.priority, status, state), uncertainty_state=state,
                   fixability=fixability_of(item.check_id, status, previous),
                   signals=Signals(order_swap_agree=None, second_family_agree=None, tool_agree=tool_agree, visibility=visibility),
                   evidence=evidence, deviation=deviation)


def feedback_sheet(checklist: Checklist, raws: list[RawVerdict], previous: dict[str, list[Status]], round_: int, take_sha256: str, cost_usd: float) -> FeedbackSheet:
    verdicts = [aggregate(i, raws, previous.get(i.id, [])) for i in checklist.items]
    return FeedbackSheet(shot_id=checklist.shot_id, round=round_, take_sha256=take_sha256, verdicts=verdicts, cost_usd=cost_usd)
