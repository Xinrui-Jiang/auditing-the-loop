"""The verify-repair loop (PLAN.md §7 M8): the pseudo-code of PLAN.md §4, one shot at a time."""
from __future__ import annotations

import json
from pathlib import Path

from . import panel, tools
from .analyser import write_checklist
from .cache import Cache
from .config import CACHE_DIR, DEFAULT_BACKEND, MAX_ROUNDS, RESOLUTION
from .generate import GenerationError, generate
from .labels import feedback_sheet
from .report import write_report
from .revise import pick_best, revise
from .schemas import Checklist, FeedbackSheet, HandOffReport, Observation, RawVerdict, Round, Status, Take, Trajectory
from .trajectory import TrajectoryStore

SHORT_SIDE = {"480p": 480, "720p": 720}


def verify_take(take: Take, checklist: Checklist, previous: dict[str, list[Status]], round_dir: Path, cache: Cache) -> tuple[FeedbackSheet, list[Observation]]:
    """Panel + tools -> labels."""
    video = Path(take.path)
    raws, observations = panel.verify(video, checklist, cache)
    tool_raws, tool_obs = tools.tool_verdicts(video, checklist, take.duration_s, SHORT_SIDE[take.resolution])
    raws += tool_raws
    observations += tool_obs
    cost = round(sum(o.cost_usd for o in observations), 6)
    sheet = feedback_sheet(checklist, raws, previous, take.round, take.sha256, cost)
    (round_dir / "raw_verdicts.json").write_text(json.dumps([r.model_dump() for r in raws], indent=1))
    (round_dir / "observations.json").write_text(json.dumps([o.model_dump() for o in observations], indent=1))
    (round_dir / "sheet.json").write_text(sheet.model_dump_json(indent=2))
    return sheet, observations


def run_shot(row: dict, out_root: Path, max_rounds: int = MAX_ROUNDS, backend: str = DEFAULT_BACKEND, cache: Cache | None = None, log=print) -> Trajectory:
    cache = cache or Cache(CACHE_DIR)
    shot_id = row["shot_id"]
    shot_dir = out_root / shot_id
    if (shot_dir / "trajectory.json").exists():
        store = TrajectoryStore.load(shot_dir)
        checklist = store.checklist()
        log(f"[{shot_id}] resuming at round {len(store.trajectory.rounds)}")
    else:
        checklist, obs = write_checklist(row, cache=cache)
        store = TrajectoryStore.start(shot_dir, checklist)
        (shot_dir / "checklist_observations.json").write_text(json.dumps([o.model_dump() for o in obs], indent=1))
        log(f"[{shot_id}] checklist: {len(checklist.items)} items")
    if store.trajectory.status != "running":
        return store.trajectory
    plan = store.pending_plan()
    prompt, branched_from, rationale, targets = (row["prompt"], None, "", []) if plan is None else \
        (plan.revised_prompt, plan.branch_from, plan.rationale, plan.targets)
    for k in range(len(store.trajectory.rounds), max_rounds):
        round_dir = store.round_dir(k)
        try:
            take = generate_with_one_retry(prompt, shot_id, k, round_dir, backend, log)
        except GenerationError as refusal:
            return hand_off(store, checklist, shot_dir, out_root, f"the backend refused the prompt twice at round {k}: {refusal}", log)
        log(f"[{shot_id}] round {k}: take in {take.latency_s}s, ${take.cost_usd:.2f}")
        sheet, _ = verify_take(take, checklist, store.previous_statuses(), round_dir, cache)
        store.append(Round(round=k, prompt=prompt, branched_from=branched_from, rationale=rationale, targets=targets,
                           take_path=take.path, sheet_path=str(round_dir / "sheet.json"), cost_usd=round(take.cost_usd + sheet.cost_usd, 6)))
        blocking = sheet.blocking()
        log(f"[{shot_id}] round {k}: blocking = {[v.item_id for v in blocking] or 'none'}")
        if not blocking:
            store.finish("output", k)
            write_report(shot_dir, store.trajectory, checklist, store.sheets(), out_root.parent)
            return store.trajectory
        if len(sheet.unfixable()) == len(blocking):
            ids = ", ".join(v.item_id for v in blocking)
            return hand_off(store, checklist, shot_dir, out_root, f"at round {k} every remaining error is backend-limited ({ids}); neither a prompt change nor a retry is expected to fix it.", log, cache)
        if k + 1 == max_rounds:
            break
        plan, _ = revise(checklist, store, cache=cache)
        store.save_plan(k, plan)
        prompt, branched_from, rationale, targets = plan.revised_prompt, plan.branch_from, plan.rationale, plan.targets
    return hand_off(store, checklist, shot_dir, out_root, "", log, cache)


def generate_with_one_retry(prompt: str, shot_id: str, k: int, round_dir: Path, backend: str, log) -> Take:
    """Video generation is stochastic and providers refuse some outputs after the fact (e.g. an audio
    copyright filter). One retry of the same prompt; the refusal text stays in generation_refused.json."""
    try:
        return generate(prompt, shot_id, k, round_dir, backend)
    except GenerationError as first:
        (round_dir / "generation_refused.json").write_text(json.dumps({"attempt": 1, "error": str(first)}, indent=1))
        log(f"[{shot_id}] round {k}: generation refused once, retrying the same prompt")
        return generate(prompt, shot_id, k, round_dir, backend)


def hand_off(store: TrajectoryStore, checklist: Checklist, shot_dir: Path, out_root: Path, refusal: str, log, cache: Cache | None = None) -> Trajectory:
    """Round cap reached, or the backend refused twice. The Analyser names the best round when there is one."""
    shot_id = checklist.shot_id
    if store.trajectory.rounds:
        pick, _ = pick_best(checklist, store, cache=cache or Cache(CACHE_DIR))
        best, reason = pick.best_round, pick.reason
        open_items = [v.item_id for v in store.sheets()[best].blocking()]
    else:
        best, reason, open_items = None, "no take was produced", [i.id for i in checklist.items]
    store.finish("hand_off", best)
    report = HandOffReport(shot_id=shot_id, best_round=best, reason=(refusal + " " + reason).strip(), open_item_ids=open_items,
                           trajectory_path=str(shot_dir / "trajectory.json"))
    (shot_dir / "handoff.json").write_text(report.model_dump_json(indent=2))
    if store.trajectory.rounds:
        write_report(shot_dir, store.trajectory, checklist, store.sheets(), out_root.parent)
    log(f"[{shot_id}] hand-off: best round {best}; open {open_items}; {refusal}")
    return store.trajectory
