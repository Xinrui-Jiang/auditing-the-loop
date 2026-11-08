"""Calls to OpenRouter chat completions that must answer in JSON: text-only and video+text. Cached; cost from usage."""
from __future__ import annotations

import base64
import json
import time
from pathlib import Path

import httpx

from .cache import Cache, cache_key
from .config import CACHE_DIR, OPENROUTER_BASE, openrouter_key
from .schemas import Observation

RETRY_STATUS = (429, 500, 502, 503)
RETRIES = 3


class ChatJSONError(RuntimeError):
    """The model answered, but not with the JSON we asked for, or OpenRouter returned an error body."""


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
        t = t.rsplit("```", 1)[0]
    return t.strip()


def _post(body: dict) -> dict:
    """One request with a bounded retry on rate limits and upstream errors; anything else raises."""
    for attempt in range(RETRIES):
        response = httpx.post(f"{OPENROUTER_BASE}/chat/completions", json=body, timeout=300,
                              headers={"Authorization": f"Bearer {openrouter_key()}"})
        if response.status_code in RETRY_STATUS and attempt < RETRIES - 1:
            time.sleep(8 * (attempt + 1))
            continue
        response.raise_for_status()
        payload = response.json()
        if "error" in payload:
            raise ChatJSONError(f"{body['model']}: {payload['error']}")
        return payload
    raise ChatJSONError(f"{body['model']}: gave up after {RETRIES} attempts")


def _complete(body: dict, key: str, source: str, cache: Cache) -> tuple[dict, Observation]:
    payload = cache.get(key)
    cached = payload is not None
    if payload is None:
        payload = _post(body)
        cache.put(key, payload)
    content = payload["choices"][0]["message"]["content"]
    try:
        data = json.loads(_strip_fences(content))
    except json.JSONDecodeError as e:
        raise ChatJSONError(f"{body['model']} answered with non-JSON text: {content[:300]!r}") from e
    observation = Observation(source=source, model_id=payload["model"], request_id=payload["id"],
                              cost_usd=0.0 if cached else float(payload["usage"]["cost"]),
                              text=content, raw_path=str(cache.path(key)))
    return data, observation


def chat_json(model: str, system: str, user: str, source: str, cache: Cache | None = None) -> tuple[dict, Observation]:
    """Text-only chat completion with JSON output. A cache hit is reported with cost 0."""
    body = {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_object"}, "temperature": 0, "usage": {"include": True}}
    return _complete(body, cache_key(model, f"{system}\n---\n{user}"), source, cache or Cache(CACHE_DIR))


def chat_json_video(model: str, prompt: str, video: Path, video_sha256: str, source: str, cache: Cache | None = None,
                    max_tokens: int = 3000) -> tuple[dict, Observation]:
    """Video + text in, JSON out. The video goes inline as base64; OpenRouter forwards audio with it."""
    data_url = "data:video/mp4;base64," + base64.b64encode(video.read_bytes()).decode()
    body = {"model": model,
            "messages": [{"role": "user", "content": [{"type": "video_url", "video_url": {"url": data_url}},
                                                       {"type": "text", "text": prompt}]}],
            "temperature": 0, "max_tokens": max_tokens, "usage": {"include": True}}
    return _complete(body, cache_key(model, prompt, video_sha256), source, cache or Cache(CACHE_DIR))
