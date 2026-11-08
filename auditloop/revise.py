"""Analyser, round k >= 1 (PLAN.md §7 M7): read the checklist and the whole trajectory, choose the round to
continue from, revise the prompt. Rules only check that the script spans survive and the branch point exists."""
from __future__ import annotations

from pydantic import BaseModel, ValidationError

from .cache import Cache
from .config import ANALYSER_MODEL
from .openrouter import chat_json
from .schemas import Checklist, Observation, RevisionPlan
from .trajectory import TrajectoryStore

MAX_ATTEMPTS = 2

SYSTEM_REVISE = """You are the Analyser of Auditing the Loop, a loop that generates a short-drama shot, verifies the take
against a checklist, and generates again. You receive the checklist, the script spans, and the full trajectory so
far: for every round its prompt, which earlier round it branched from, your reasoning at the time, and the feedback
sheet (per item: status, severity, uncertainty state, fixability, evidence). Decide where to continue from and how to
change the prompt so the next take fixes the blocking items without losing what already passes.
Rules:
1. Never change the script. Every span listed under SCRIPT SPANS must appear unchanged in the new prompt. You may
   add, reword or remove guidance sentences anywhere else (for example "She speaks English.", "Nobody else is in
   frame.", "Keep the rain sound.").
2. You may branch from any earlier round, not only the last one. A later prompt that has become over-specified or
   that broke things that used to pass is a reason to go back. Say why.
3. Prefer changes aimed at the blocking items. Note what passed so far and protect it.
Return JSON only: {"branch_from": <round index>, "revised_prompt": "<full prompt>", "rationale": "<why this round, why these changes>", "targets": ["<item ids you aim to fix>"]}"""

SYSTEM_BEST = """You are the Analyser of Auditing the Loop. The loop has reached its round cap without passing. Read the
trajectory and name the round whose take is the best one to hand to a human, with a short reason.
Return JSON only: {"best_round": <round index>, "reason": "<one or two sentences>"}"""


class RevisionError(RuntimeError):
    pass


class BestPick(BaseModel):
    best_round: int
    reason: str


def _context(checklist: Checklist, store: TrajectoryStore) -> str:
    items = "\n".join(f"- {i.id} [{i.kind}, {i.priority}]: {i.text}" for i in checklist.items)
    spans = "\n".join(f"- {s}" for s in checklist.script_spans)
    return f"CHECKLIST:\n{items}\n\nSCRIPT SPANS (must stay verbatim):\n{spans}\n\nTRAJECTORY:\n{store.render_for_analyser()}"


def revise(checklist: Checklist, store: TrajectoryStore, model: str = ANALYSER_MODEL, cache: Cache | None = None) -> tuple[RevisionPlan, list[Observation]]:
    n_rounds = len(store.trajectory.rounds)
    user = _context(checklist, store)
    observations: list[Observation] = []
    problem = ""
    for attempt in range(MAX_ATTEMPTS):
        data, obs = chat_json(model, SYSTEM_REVISE, user + problem, f"analyser/revise/attempt{attempt + 1}", cache)
        observations.append(obs)
        try:
            plan = RevisionPlan.model_validate(data)
        except ValidationError as e:
            problem = f"\n\nYour previous answer did not match the JSON shape: {str(e)[:300]}"
            continue
        missing = checklist.missing_spans(plan.revised_prompt)
        if not 0 <= plan.branch_from < n_rounds:
            problem = f"\n\nYour previous answer named branch_from={plan.branch_from}; rounds 0..{n_rounds - 1} exist."
            continue
        if missing:
            problem = "\n\nYour previous prompt dropped or changed these script spans, which must stay verbatim: " + "; ".join(missing)
            continue
        return plan, observations
    raise RevisionError(f"{checklist.shot_id}: no valid revision after {MAX_ATTEMPTS} attempts: {problem.strip()}")


def pick_best(checklist: Checklist, store: TrajectoryStore, model: str = ANALYSER_MODEL, cache: Cache | None = None) -> tuple[BestPick, Observation]:
    data, obs = chat_json(model, SYSTEM_BEST, _context(checklist, store), "analyser/pick_best", cache)
    pick = BestPick.model_validate(data)
    if not 0 <= pick.best_round < len(store.trajectory.rounds):
        raise RevisionError(f"{checklist.shot_id}: pick_best named round {pick.best_round}, which does not exist")
    return pick, obs
