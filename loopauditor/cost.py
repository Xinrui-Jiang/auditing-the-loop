"""Cost of one OpenRouter request, read back from GET /generation?id=... after the call."""
from __future__ import annotations

import httpx
from pydantic import BaseModel

from .config import OPENROUTER_BASE


class GenerationCost(BaseModel):
    request_id: str
    model: str
    total_cost_usd: float
    tokens_prompt: int | None  # None for video generations, which OpenRouter bills by the second
    tokens_completion: int | None


def fetch_generation_cost(request_id: str, api_key: str) -> GenerationCost:
    """Raises httpx.HTTPStatusError when OpenRouter does not know the id yet or at all."""
    response = httpx.get(
        f"{OPENROUTER_BASE}/generation",
        params={"id": request_id},
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    response.raise_for_status()
    d = response.json()["data"]
    return GenerationCost(
        request_id=d["id"],
        model=d["model"],
        total_cost_usd=float(d["total_cost"]),
        tokens_prompt=d["tokens_prompt"],
        tokens_completion=d["tokens_completion"],
    )
