# LoopAuditor

An agentic verification harness for video generation. LoopAuditor sits between a text-to-video model and delivery. For one short-drama shot it writes a checklist from the prompt, generates a take, has a panel of verifiers check the take against the checklist, labels every problem with three labels (severity, uncertainty state, fixability), revises the prompt and generates again. It keeps the whole trajectory, so the revision step can branch from an earlier round. It stops when no blocking problem remains, or hands the shot to a human when the remaining problems are ones the system cannot fix.

Course project for CS329Z (Stanford, Fall 2026). Design: `docs/DESIGN.md`. Implementation plan and decision log: `docs/PLAN.md`.

## What is in this repository

| path | content |
|---|---|
| `loopauditor/` | the package (about 1,500 lines): `analyser.py` (checklist writer and revision), `generate.py` (video backend), `tools.py` (ASR, ffprobe, cut/freeze detection), `panel.py` (verifier panel), `labels.py` (three labels), `trajectory.py`, `revise.py`, `loop.py`, `report.py`, `cli.py` |
| `data/prompts/` | the 90-shot prompt set and the 30-shot working set, with manifests and selection scores |
| `data/sources/` | the three source datasets as downloaded (DramaBench, SEAM-Bench, FilmBench) and derived candidate files |
| `data/pilot_takes/` | metadata of the five pilot clips of 2026-11-07 (videos not included) |
| `scripts/` | data pipeline (`extract_dramabench_shots.py`, `build_prompt_set_v2.py`, `select_prompt_subset.py`), per-module inspection runs (`m0_demo.py` … `m45_run.py`), `trajectory_page.py`, `loop_metrics.py`, `figures.py`, `export_results.py` |
| `results/loop_2026-11-08/` | the five end-to-end runs: checklists, per-round feedback sheets, raw verdicts, revision plans, hand-off reports, metrics (videos not included) |
| `docs/pages/` | inspection pages per module and `trajectories.html` (prompt → take → feedback sheet, round by round; small web copies of the takes are in `docs/pages/web_videos/`) |
| `docs/figures/` | figures for the report |
| `tests/` | 40 offline tests (no API calls) |

## Requirements

- macOS on Apple Silicon (the ASR tool uses `mlx-whisper`; on other machines replace `tools.transcribe` with another whisper backend).
- Python 3.12 and [uv](https://docs.astral.sh/uv/).
- `ffmpeg` and `ffprobe` on the PATH (`brew install ffmpeg`).
- An [OpenRouter](https://openrouter.ai) API key with credit. One take with `bytedance/seedance-2.0` at 480p costs about $0.57; verifying it costs about $0.03.

## Install

```bash
git clone <this repository> && cd loopauditor
uv sync
uv run pytest -q
```

The first ASR call downloads `mlx-community/whisper-small-mlx` (about 500 MB) into the Hugging Face cache.

## Configure the API key

```bash
cp .env.example .env
```

Put your key in `.env` as `OPENROUTER_API_KEY=...`. The file is ignored by git. Every OpenRouter call reads the key from this file; nothing else is needed. Models used (all through OpenRouter): `openai/gpt-5.6-luna` for the Analyser, `google/gemini-3.5-flash-lite` as the primary verifier, `qwen/qwen3.8-omni-flash` as the second verifier family, `bytedance/seedance-2.0` for generation. They are set in `loopauditor/config.py`.

## Run the agent

Write the checklist for one shot (no video generation, about $0.001):

```bash
uv run loopauditor checklist DB-38
```

Run the full loop on one or more shots (each round generates one take and verifies it; up to 8 rounds):

```bash
uv run loopauditor run --shot DB-38 --shot DB-16 --out runs/loop
```

Everything is written under `runs/loop/<shot>/`: `checklist.json`, `trajectory.json`, `rounds/<k>/{take.mp4, sheet.json, raw_verdicts.json, observations.json, next_plan.json}`, `report.md`, and `handoff.json` when the shot is handed off. A stopped run resumes from disk with the same command. Model responses are cached under `runs/_cache/`, so re-running a finished round costs nothing.

Shot ids come from `data/prompts/prompt_set_v2_30.jsonl` (`DB-…` DramaBench, `SB-…` SEAM-Bench, `FB-…` FilmBench). Pass `--prompt-set data/prompts/prompt_set_v2.jsonl` to use all 90.

## Reproduce the evaluation

The numbers in the report come from `results/loop_2026-11-08/` (five shots: DB-16, DB-35, DB-38, DB-60, SB-01). To recompute them without any API call:

```bash
uv run python scripts/loop_metrics.py        # reads runs/loop; copy results/loop_2026-11-08/* into runs/loop/ first
uv run python scripts/figures.py             # docs/figures/*.png and *.pdf
uv run python scripts/trajectory_page.py --video-url-map docs/pages/web_videos/local_map.json
```

To rerun the five shots from scratch (about $10 and 60 minutes):

```bash
uv run loopauditor run --shot DB-16 --shot DB-35 --shot DB-38 --shot DB-60 --shot SB-01 --out runs/loop
uv run python scripts/export_results.py loop_<date>
```

Generation is stochastic, so a rerun gives different takes and possibly different round counts; the checklists and the verification of any given take are cached and deterministic at temperature 0.

To rebuild the prompt set from the sources:

```bash
uv run python scripts/build_prompt_set_v2.py      # data/prompts/prompt_set_v2.jsonl + manifest
uv run python scripts/select_prompt_subset.py     # the 30-shot working set
```

## How a round works

1. **Analyser, round 0** writes the checklist: rules turn the structured fields of the shot into items (the spoken line, setting, sound cue, framing, all rendering checks, emotion class and intensity); a text model lists actions, props, the people the script places in the scene and premise facts, each tied to a span copied from the script. Items map to 19 checks in three families: A script fidelity, B rendering integrity, C dramatic performance (`docs/DESIGN.md` §4).
2. **Generation** produces take k.
3. **Verifier panel**: two blind descriptions of the take; three specialist verifiers (A, B, C), each run twice on the primary model with the item order swapped and once on the second model family; a text entailment pass for the A items; deterministic tools for dialogue (whisper: language and word error rate), technical delivery (ffprobe) and cuts/freezes (ffmpeg); a re-inspect of uncertain items on a cut of the cited interval.
4. **Labels**: per item a status and three labels. Uncertainty comes from agreement (order swap, second family, tools), never from a model-reported probability. Severity follows priority × uncertainty. Fixability starts from a prior per check and is revised by the trajectory.
5. **Stop rule**: no blocking error → release; a blocking error that a prompt change or a retry may fix → next round; only backend-limited errors left → hand off to a human.
6. **Analyser, round k** reads the whole trajectory and decides which round to branch from and how to revise the prompt. It may not change the script spans.

## Data and licences

Prompts are verbatim lines and action text from three public datasets, inside a fixed technical frame: DramaBench (MIT; HF `FutureMa/DramaBench`), SEAM-Bench (CC BY-NC 4.0; HF `Jackyqq/SEAM-Bench`; episodes 1, 2, 7, 8 and 9 excluded), FilmBench (Apache-2.0; HF `skylenage/FilmBench`). Each prompt row carries its source id, file, licence and excerpt. See `data/prompts/prompt_set_v2_manifest.md` and `docs/DESIGN.md` §7.

## Known limitations

- Seedance 2.0 sometimes speaks Chinese for pinyin-named characters even when the prompt asks for English; the loop then hands the shot off.
- The provider can refuse an output after generation (audio copyright filter); the loop retries once.
- Human-label evaluation of the verifiers (precision and recall per check) and the baselines are not yet run.
