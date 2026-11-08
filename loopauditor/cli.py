"""Command line: run the loop on one or more shots, or write a checklist only."""
from __future__ import annotations

import json
from pathlib import Path

import typer

from .analyser import write_checklist
from .config import MAX_ROUNDS, PROMPT_SET_30, RUNS
from .loop import run_shot

app = typer.Typer(add_completion=False, help="LoopAuditor: an agentic verification harness for video generation.")


def _rows(prompt_set: Path) -> dict[str, dict]:
    return {json.loads(l)["shot_id"]: json.loads(l) for l in prompt_set.open()}


@app.command()
def run(shot: list[str] = typer.Option(..., help="shot ids, e.g. DB-16"), max_rounds: int = MAX_ROUNDS,
        out: Path = RUNS / "loop", prompt_set: Path = PROMPT_SET_30) -> None:
    rows = _rows(prompt_set)
    for sid in shot:
        trajectory = run_shot(rows[sid], out, max_rounds=max_rounds)
        typer.echo(f"{sid}: {trajectory.status} at round {trajectory.output_round}; rounds {len(trajectory.rounds)}; "
                   f"cost ${sum(r.cost_usd for r in trajectory.rounds):.2f}")


@app.command()
def checklist(shot: str, prompt_set: Path = PROMPT_SET_30) -> None:
    cl, obs = write_checklist(_rows(prompt_set)[shot])
    typer.echo(cl.model_dump_json(indent=2))


if __name__ == "__main__":
    app()
