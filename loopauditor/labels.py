"""Label aggregation (PLAN.md §7 M5): RawVerdicts + tool evidence -> one Verdict per item with the three labels,
following the tables in PLAN.md §5 exactly. No model-reported confidence takes part."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import yaml

from .schemas import Checklist, ChecklistItem, FeedbackSheet, Fixability, RawVerdict, Severity, Signals, Status, UncertaintyState, Verdict

FIXABILITY_PRIOR: dict[str, Fixability] = yaml.safe_load((Path(__file__).parent / "fixability_prior.yaml").read_text())
TOOL_DECIDES = {"A1", "B6"}  # the tool's answer is the status; models only add agreement


def _majority(statuses: list[Status]) -> Status:
    votes = Counter(s for s in statuses if s != "not_applicable")
    if not votes:
        return "not_applicable"
    (top, n), *rest = votes.most_common()
    if rest and rest[0][1] == n:
        return "uncertain"
    return top


def _intensity_status(item: ChecklistItem, runs: list[RawVerdict]) -> tuple[Status | None, float | None]:
    """C2: the mean of the reported intensities decides, when at least two runs rated it."""
    readings = [x for r in runs for x in (r.face_intensity, r.voice_intensity) if x is not None]
    if item.check_id != "C2" or len(readings) < 2:
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
    """Prior per check, then the trajectory: two prompt revisions without effect -> backend_limited;
    pass/fail flipping across rounds -> retry_fixable."""
    prior = FIXABILITY_PRIOR[check_id]
    if status == "fail" and len(previous) >= 2 and previous[-1] == previous[-2] == "fail":
        return "backend_limited"
    if "pass" in previous and "fail" in previous:
        return "retry_fixable"
    return prior


def aggregate(item: ChecklistItem, raws: list[RawVerdict], previous: list[Status]) -> Verdict:
    mine = [r for r in raws if r.item_id == item.id]
    primary = [r for r in mine if "/primary/" in r.source]
    second = [r for r in mine if r.source.endswith("/second")]
    entail = [r for r in mine if r.source.endswith("/entailment")]
    tools = [r for r in mine if r.source.startswith("tool/")]
    reinspect = [r for r in mine if r.source.endswith("/reinspect")]
    model_runs = primary + second
    if not model_runs and not tools:
        raise ValueError(f"no evidence for item {item.id}")
    visibility = "not_observable" if model_runs and sum(r.visibility == "not_observable" for r in model_runs) * 2 > len(model_runs) \
        else ("seen_clearly" if all(r.visibility == "seen_clearly" for r in model_runs) else "partially_seen")
    model_status = _majority([r.status for r in model_runs + entail]) if model_runs or entail else None
    status, deviation = _intensity_status(item, model_runs)
    if status is None:
        status = model_status if model_status is not None else tools[0].status
    if tools and item.check_id in TOOL_DECIDES:
        status, deviation = tools[0].status, tools[0].value
    order_swap = (primary[0].status == primary[1].status) if len(primary) == 2 else None
    second_agree = (second[0].status == _majority([r.status for r in primary])) if second and primary else None
    tool_agree = (tools[0].status == model_status) if tools and model_status is not None else None
    if visibility == "not_observable":
        state: UncertaintyState = "not_observable"
    elif tools:
        state = "confident" if tool_agree else "uncertain"
    else:
        state = "confident" if order_swap and second_agree else "uncertain"
    if reinspect and state == "uncertain" and reinspect[-1].status == status:
        state = "confident"
    evidence = [f"{r.source}: {r.evidence}" for r in mine if r.evidence]
    return Verdict(item_id=item.id, status=status, severity=severity_of(item.priority, status, state), uncertainty_state=state,
                   fixability=fixability_of(item.check_id, status, previous),
                   signals=Signals(order_swap_agree=order_swap, second_family_agree=second_agree, tool_agree=tool_agree, visibility=visibility),
                   evidence=evidence, deviation=deviation, reinspected=bool(reinspect))


def feedback_sheet(checklist: Checklist, raws: list[RawVerdict], previous: dict[str, list[Status]], round_: int, take_sha256: str, cost_usd: float) -> FeedbackSheet:
    verdicts = [aggregate(i, raws, previous.get(i.id, [])) for i in checklist.items]
    return FeedbackSheet(shot_id=checklist.shot_id, round=round_, take_sha256=take_sha256, verdicts=verdicts, cost_usd=cost_usd)
