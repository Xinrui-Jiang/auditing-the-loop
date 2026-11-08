"""Generation backend (PLAN.md §7 M2): send one prompt to OpenRouter's video API, wait for the result,
download it, and record the real cost. Failures raise; nothing is retried or faked."""
from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

from .cache import sha256_file, sha256_text
from .config import ASPECT_RATIO, DEFAULT_BACKEND, DURATION_S, GENERATION_BACKENDS, OPENROUTER_BASE, RESOLUTION, openrouter_key
from .cost import fetch_generation_cost
from .schemas import Take

POLL_EVERY_S = 10
TIMEOUT_S = 600
COST_WAIT_S = 90  # the /generation record can lag the finished job by a minute


class GenerationError(RuntimeError):
    pass


def _wait(poll_url: str, headers: dict[str, str], job_id: str, started: float) -> dict:
    while True:
        if time.time() - started > TIMEOUT_S:
            raise GenerationError(f"job {job_id}: no result after {TIMEOUT_S} s")
        time.sleep(POLL_EVERY_S)
        status = httpx.get(poll_url, headers=headers, timeout=60).raise_for_status().json()
        if status["status"] == "completed":
            return status
        if status["status"] in ("failed", "cancelled", "expired"):
            raise GenerationError(f"job {job_id}: {json.dumps(status)[:500]}")


def estimated_cost(backend: str, duration_s: int, resolution: str) -> float:
    spec = GENERATION_BACKENDS[backend]
    return round(spec.usd_per_second[resolution] * duration_s, 4)


def _cost(job_id: str, key: str, backend: str, duration_s: int, resolution: str, out_dir: Path) -> float:
    """The billed cost from /generation. If the record has not appeared after COST_WAIT_S, the price-table
    estimate is used and the fact is written to cost_estimated.json so it is never mistaken for a billed number."""
    started = time.time()
    while True:
        try:
            return fetch_generation_cost(job_id, key).total_cost_usd
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 404:
                raise
            if time.time() - started > COST_WAIT_S:
                estimate = estimated_cost(backend, duration_s, resolution)
                (out_dir / "cost_estimated.json").write_text(json.dumps({"job_id": job_id, "estimated_cost_usd": estimate,
                                                                         "reason": f"/generation still 404 after {COST_WAIT_S} s"}))
                return estimate
            time.sleep(5)


def generate(prompt: str, shot_id: str, round_: int, out_dir: Path, backend: str = DEFAULT_BACKEND,
             seed: int | None = None, duration_s: int = DURATION_S, resolution: str = RESOLUTION) -> Take:
    spec = GENERATION_BACKENDS[backend]
    lo, hi = spec.durations
    if not lo <= duration_s <= hi:
        raise GenerationError(f"{backend} supports {lo}-{hi} s, not {duration_s} s")
    key = openrouter_key()
    headers = {"Authorization": f"Bearer {key}"}
    path = out_dir / "take.mp4"
    record = out_dir / "generation.json"
    if path.exists() and record.exists():  # resumed run: the take was downloaded before the run stopped
        job = json.loads(record.read_text())["job"]
        return Take(shot_id=shot_id, round=round_, path=str(path), backend=backend, seed=seed, duration_s=duration_s,
                    resolution=resolution, aspect_ratio=ASPECT_RATIO, prompt_sha256=sha256_text(prompt), sha256=sha256_file(path),
                    cost_usd=_cost(job["id"], key, backend, duration_s, resolution, out_dir), request_id=job["id"], latency_s=0.0)
    body = {"model": spec.model, "prompt": prompt, "duration": duration_s, "resolution": resolution,
            "aspect_ratio": ASPECT_RATIO, "generate_audio": True}
    if seed is not None:
        body["seed"] = seed
    started = time.time()
    job = httpx.post(f"{OPENROUTER_BASE}/videos", headers=headers, json=body, timeout=120).raise_for_status().json()
    poll_url = job["polling_url"] if job["polling_url"].startswith("http") else "https://openrouter.ai" + job["polling_url"]
    status = _wait(poll_url, headers, job["id"], started)
    urls = status.get("unsigned_urls")  # absent for some providers; the content endpoint always works
    url = urls[0] if urls else f"{OPENROUTER_BASE}/videos/{job['id']}/content?index=0"
    data = httpx.get(url, headers=headers if "openrouter.ai" in url else {}, timeout=300, follow_redirects=True).raise_for_status().content
    out_dir.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    record.write_text(json.dumps({"request": body, "job": job, "status": status}, indent=1))
    return Take(shot_id=shot_id, round=round_, path=str(path), backend=backend, seed=seed, duration_s=duration_s,
                resolution=resolution, aspect_ratio=ASPECT_RATIO, prompt_sha256=sha256_text(prompt),
                sha256=sha256_file(path), cost_usd=_cost(job["id"], key, backend, duration_s, resolution, out_dir),
                request_id=job["id"], latency_s=round(time.time() - started, 1))
