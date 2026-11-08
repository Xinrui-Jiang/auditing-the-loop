"""Fixed settings: paths, model ids, prices, loop constants (PLAN.md §6)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PROMPT_SET_90 = DATA / "prompts/prompt_set_v2.jsonl"
PROMPT_SET_30 = DATA / "prompts/prompt_set_v2_30.jsonl"
RUNS = ROOT / "runs"
CACHE_DIR = RUNS / "_cache"

OPENROUTER_BASE = "https://openrouter.ai/api/v1"


class Backend(BaseModel):
    model: str
    usd_per_second: dict[str, float]  # by resolution, audio on (OpenRouter, 2026-11-07)
    durations: tuple[int, int]  # inclusive range in seconds


GENERATION_BACKENDS: dict[str, Backend] = {
    "seedance-2.0": Backend(
        model="bytedance/seedance-2.0",
        usd_per_second={"480p": 0.067256, "720p": 0.1512},
        durations=(4, 15),
    ),
}
DEFAULT_BACKEND = "seedance-2.0"
DURATION_S = 8
RESOLUTION = "480p"
ASPECT_RATIO = "9:16"
MAX_ROUNDS = 8

# One model family for every reasoning role. OpenRouter samples video at 1 frame per second for Gemini and does
# not forward a frame-rate setting (checked 2026-11-08: 898 prompt tokens for an 8 s clip with or without fps).
ANALYSER_MODEL = "google/gemini-4-argon"
VERIFIER_MODEL = "google/gemini-4-argon"


def openrouter_key() -> str:
    load_dotenv(ROOT / ".env")
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set; copy .env.example to .env and fill it in")
    return key
