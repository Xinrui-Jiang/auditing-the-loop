"""Response cache keyed by sha256(model, prompt, media). Payloads are raw JSON responses."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cache_key(model: str, prompt: str, media_sha256: str = "") -> str:
    return sha256_text(f"{model}\n{prompt}\n{media_sha256}")


class Cache:
    def __init__(self, directory: Path):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)

    def path(self, key: str) -> Path:
        return self.directory / f"{key}.json"

    def get(self, key: str) -> dict | None:
        """None means not cached. A miss is the normal case for a new call, not an error."""
        p = self.path(key)
        if not p.exists():
            return None
        return json.loads(p.read_text())

    def put(self, key: str, payload: dict) -> Path:
        p = self.path(key)
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
        return p
