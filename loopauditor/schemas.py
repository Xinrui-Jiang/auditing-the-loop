"""Data objects for VGLoop (PLAN.md §7 M0).

Every object is written to disk as JSON by the step that produces it, so a run can be replayed.
Priorities and the stop rule are data and rules here, never model output.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

CheckId = Literal[
    "A1", "A2", "A3", "A4", "A5", "A6",
    "B1", "B2", "B3", "B4", "B5", "B6", "B7",
    "C1", "C2", "C3", "C4", "C5", "C6",
]
Family = Literal["A", "B", "C"]
ItemKind = Literal["must", "must_not", "premise"]
Priority = Literal["critical", "major", "minor", "info"]
Evidence = Literal["tool", "description", "panel", "tool_panel"]
Status = Literal["pass", "fail", "uncertain", "not_applicable"]
Visibility = Literal["seen_clearly", "partially_seen", "not_observable"]
UncertaintyState = Literal["confident", "uncertain", "not_observable"]
Severity = Literal["error", "warning", "info"]
Fixability = Literal["prompt_fixable", "retry_fixable", "backend_limited"]
LoopStatus = Literal["running", "output", "hand_off"]

# Default priority and evidence per check (PLAN.md §2). The Analyser copies these; it may raise
# B1 to major when the scripted action involves physics, and A4 is critical for a second person.
CHECK_DEFAULTS: dict[str, tuple[Priority, Evidence]] = {
    "A1": ("critical", "tool"), "A2": ("critical", "description"), "A3": ("major", "description"),
    "A4": ("critical", "description"), "A5": ("major", "description"), "A6": ("minor", "tool_panel"),
    "B1": ("minor", "panel"), "B2": ("major", "panel"), "B3": ("major", "tool_panel"),
    "B4": ("major", "tool_panel"), "B5": ("major", "panel"), "B6": ("info", "tool"),
    "B7": ("minor", "panel"),
    "C1": ("major", "panel"), "C2": ("major", "panel"), "C3": ("minor", "panel"),
    "C4": ("minor", "panel"), "C5": ("minor", "panel"), "C6": ("info", "panel"),
}

# Which params a check cannot work without.
REQUIRED_PARAMS: dict[str, tuple[str, ...]] = {
    "A1": ("line", "language"), "A2": ("element",), "A3": ("element",), "C2": ("target_interval",),
}


def normalise(text: str) -> str:
    """Collapse whitespace so that substring checks ignore line wrapping."""
    return " ".join(text.split())


class ItemParams(BaseModel):
    """Inputs a check needs. A1 uses line and language, A2/A3 name the element they are about,
    C2 uses target_interval on the 0-4 scale. Fields a check does not use stay None."""

    line: str | None = None
    language: str | None = None
    element: str | None = None
    target_interval: tuple[int, int] | None = None

    @model_validator(mode="after")
    def _interval_in_scale(self) -> "ItemParams":
        if self.target_interval is not None:
            lo, hi = self.target_interval
            if not 0 <= lo <= hi <= 4:
                raise ValueError(f"target_interval {self.target_interval} must satisfy 0 <= lo <= hi <= 4")
        return self


class ChecklistItem(BaseModel):
    id: str
    check_id: CheckId
    kind: ItemKind
    text: str
    priority: Priority
    evidence: Evidence
    params: ItemParams = Field(default_factory=ItemParams)

    @property
    def family(self) -> Family:
        return self.check_id[0]  # type: ignore[return-value]

    @model_validator(mode="after")
    def _required_params_present(self) -> "ChecklistItem":
        for name in REQUIRED_PARAMS.get(self.check_id, ()):
            if getattr(self.params, name) is None:
                raise ValueError(f"item {self.id}: check {self.check_id} needs params.{name}")
        return self


class Checklist(BaseModel):
    """What the verifier panel checks for one shot. Written once at round 0, never edited."""

    shot_id: str
    prompt: str
    # Verbatim source spans that every revised prompt must keep (DESIGN.md §3.2 rule 2).
    script_spans: list[str]
    items: list[ChecklistItem]
    conflicts: list[str] = Field(default_factory=list)
    author: str  # "manual" or the model id that wrote it

    @model_validator(mode="after")
    def _ids_unique_and_spans_present(self) -> "Checklist":
        ids = [i.id for i in self.items]
        if len(set(ids)) != len(ids):
            raise ValueError("checklist item ids must be unique")
        missing = self.missing_spans(self.prompt)
        if missing:
            raise ValueError(f"script spans missing from the prompt: {missing}")
        return self

    def missing_spans(self, prompt: str) -> list[str]:
        text = normalise(prompt)
        return [s for s in self.script_spans if normalise(s) not in text]

    def item(self, item_id: str) -> ChecklistItem:
        for i in self.items:
            if i.id == item_id:
                return i
        raise KeyError(item_id)

    def family(self, family: Family) -> list[ChecklistItem]:
        return [i for i in self.items if i.family == family]


class Take(BaseModel):
    """One generated video."""

    shot_id: str
    round: int
    path: str
    backend: str
    seed: int | None  # None when the provider returns no seed
    duration_s: int
    resolution: str
    aspect_ratio: str
    prompt_sha256: str
    sha256: str
    cost_usd: float
    request_id: str
    latency_s: float


class Observation(BaseModel):
    """One model call or tool run. The caller saves the raw response next to it."""

    source: str  # e.g. "blind_description/primary", "tool/asr", "tool/cut_detector"
    model_id: str  # exact model id, or tool name and version
    request_id: str | None  # None for local tools
    cost_usd: float
    text: str  # what later steps read: transcript, description, or a one-line tool result
    raw_path: str | None  # None for tools without a raw payload


class RawVerdict(BaseModel):
    """What one run (one specialist call, one tool, one re-inspect) said about one item."""

    item_id: str
    source: str  # e.g. "A/primary/order1", "A/primary/order2", "A/second", "A/entailment", "tool/asr"
    status: Status
    visibility: Visibility
    evidence: str
    span: tuple[float, float] | None = None  # seconds; None when the source gives no time
    value: float | None = None  # a tool's number, e.g. WER for A1
    face_intensity: int | None = None  # C family only, 0-4
    voice_intensity: int | None = None

    @model_validator(mode="after")
    def _ranges(self) -> "RawVerdict":
        for name in ("face_intensity", "voice_intensity"):
            value = getattr(self, name)
            if value is not None and not 0 <= value <= 4:
                raise ValueError(f"{name} {value} must be in 0..4")
        if self.span is not None and self.span[0] > self.span[1]:
            raise ValueError(f"span {self.span} must be ordered")
        return self


class Signals(BaseModel):
    """Agreement signals the uncertainty state is computed from (PLAN.md §5)."""

    order_swap_agree: bool | None  # None when only one primary run exists
    second_family_agree: bool | None  # None when the second family did not run
    tool_agree: bool | None  # None when no tool covers this item
    visibility: Visibility


class Verdict(BaseModel):
    """One checklist item after aggregation: status plus the three labels."""

    item_id: str
    status: Status
    severity: Severity
    uncertainty_state: UncertaintyState
    fixability: Fixability
    signals: Signals
    evidence: list[str]
    deviation: float | None = None  # A1: WER; C2: signed distance to the target interval

    def blocks(self) -> bool:
        """An error we believe (PLAN.md §4). It blocks the output; whether the loop keeps trying or hands off
        depends on fixability, see FeedbackSheet.unfixable()."""
        return self.severity == "error" and self.uncertainty_state in ("confident", "uncertain")


class FeedbackSheet(BaseModel):
    shot_id: str
    round: int
    take_sha256: str
    verdicts: list[Verdict]
    cost_usd: float

    def blocking(self) -> list[Verdict]:
        return [v for v in self.verdicts if v.blocks()]

    def unfixable(self) -> list[Verdict]:
        """Blocking errors that neither a prompt change nor a retry is expected to fix. When every blocking
        error is one of these, the loop hands the shot to a human instead of releasing it."""
        return [v for v in self.blocking() if v.fixability == "backend_limited"]

    def verdict(self, item_id: str) -> Verdict:
        for v in self.verdicts:
            if v.item_id == item_id:
                return v
        raise KeyError(item_id)


class Round(BaseModel):
    round: int
    prompt: str
    branched_from: int | None  # None for round 0
    rationale: str  # the Analyser's reasoning; empty for round 0
    targets: list[str]  # item ids the revision aimed at; empty for round 0
    take_path: str
    sheet_path: str
    cost_usd: float


class RevisionPlan(BaseModel):
    """The Analyser's output at round k >= 1 (PLAN.md §4)."""

    branch_from: int
    revised_prompt: str
    rationale: str
    targets: list[str]


class Trajectory(BaseModel):
    shot_id: str
    checklist_path: str
    rounds: list[Round] = Field(default_factory=list)
    status: LoopStatus = "running"
    output_round: int | None = None  # set when status is output or hand_off

    @model_validator(mode="after")
    def _rounds_consistent(self) -> "Trajectory":
        for k, r in enumerate(self.rounds):
            if r.round != k:
                raise ValueError(f"round {r.round} stored at position {k}")
            if (r.branched_from is None) != (k == 0):
                raise ValueError(f"round {k}: branched_from must be None exactly for round 0")
            if r.branched_from is not None and r.branched_from >= k:
                raise ValueError(f"round {k} cannot branch from round {r.branched_from}")
        ended_with_take = self.status == "output" or (self.status == "hand_off" and self.rounds)
        if (self.output_round is None) == bool(ended_with_take):
            raise ValueError("output_round is set exactly when the loop ended with at least one take")
        if self.output_round is not None and not 0 <= self.output_round < len(self.rounds):
            raise ValueError(f"output_round {self.output_round} does not exist")
        return self


class HandOffReport(BaseModel):
    shot_id: str
    best_round: int | None  # None when the backend refused every attempt and no take exists
    reason: str
    open_item_ids: list[str]
    trajectory_path: str
