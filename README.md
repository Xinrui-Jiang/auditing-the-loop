# Auditing the Loop

Auditing the Loop is a verification loop for text-to-video generation. For one short-drama shot it writes a checklist from the prompt, generates a take, has three verifiers check the take against the checklist, labels every problem with severity, uncertainty and fixability, revises the prompt and generates again. It keeps the whole trajectory, so a revision can branch from an earlier round. A shot is released when no error remains. When the remaining errors are ones that neither a prompt change nor a retry can fix, the shot is handed to a human.

Design: `docs/DESIGN.md`. Decisions and implementation log: `docs/PLAN.md`. Tables for the report: `docs/report_tables.md`.

## Layout

| path | content |
|---|---|
| `auditloop/` | the package: `analyser.py`, `generate.py`, `tools.py`, `panel.py`, `labels.py`, `trajectory.py`, `revise.py`, `loop.py`, `report.py`, `cli.py` |
| `data/prompts/` | the 30-shot prompt set with manifests and selection scores |
| `data/sources/` | DramaBench, SEAM-Bench and FilmBench as downloaded, plus derived candidate files |
| `results/loop_2026-11-08/` | the five end-to-end runs: checklists, feedback sheets, raw verdicts, revision plans, reports, metrics |
| `docs/pages/` | inspection pages per module and `trajectories.html` |
| `docs/figures/` | figures for the report |
| `scripts/` | data pipeline, inspection runs, metrics, figures |
| `tests/` | offline tests |

## Requirements

macOS on Apple Silicon for the ASR tool, Python 3.12, [uv](https://docs.astral.sh/uv/), `ffmpeg` and `ffprobe` on the PATH, and an [OpenRouter](https://openrouter.ai) API key with credit. One take costs about $0.57 and its verification about $0.03.

## Install and configure

```bash
uv sync
uv run pytest -q
cp .env.example .env
```

Write your key into `.env` as `OPENROUTER_API_KEY=...`. The models are set in `auditloop/config.py`: `google/gemini-4-argon` for the Analyser and the verifiers, `bytedance/seedance-2.0` for generation.

## Run

Write a checklist for one shot:

```bash
uv run auditloop checklist DB-38
```

Run the loop on one or more shots, up to 8 rounds each:

```bash
uv run auditloop run --shot DB-38 --shot DB-16 --out runs/loop
```

Output goes to `runs/loop/<shot>/`: `checklist.json`, `trajectory.json`, one folder per round with the take, the feedback sheet and the next revision, `report.md`, and `handoff.json` when the shot is handed off. A stopped run resumes with the same command. Shot ids are in `data/prompts/prompt_set_v2_30.jsonl`.

## Reproduce the reported results

The report uses the five runs in `results/loop_2026-11-08/`. To recompute the tables and figures from them:

```bash
cp -r results/loop_2026-11-08/* runs/loop/
uv run python scripts/loop_metrics.py
uv run python scripts/report_tables.py
uv run python scripts/figures.py
```

Those runs used the verifier configuration of 2026-11-07, described in `docs/DESIGN.md` §6 and §10. Rerunning the five shots from scratch costs about $10 and takes about an hour; takes differ between runs because generation is stochastic.

To rebuild the prompt set from the sources:

```bash
uv run python scripts/build_prompt_set_v2.py
uv run python scripts/select_prompt_subset.py
```

## Data

Prompts are verbatim lines and action text from DramaBench, SEAM-Bench and FilmBench inside a fixed technical frame. Each row carries its source id, file, licence and excerpt. Details: `data/prompts/prompt_set_v2_manifest.md` and `docs/DESIGN.md` §7.
