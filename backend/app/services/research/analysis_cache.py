from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path


class AnalysisCache:
    def __init__(self, directory: Path, ttl_seconds: int) -> None:
        self.directory = directory
        self.ttl_seconds = ttl_seconds

    def key(self, identity: dict) -> str:
        canonical = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _path(self, key: str) -> Path:
        return self.directory / f"{key}.json"

    def get(self, key: str) -> dict | None:
        try:
            document = json.loads(self._path(key).read_text(encoding="utf-8"))
            if time.time() - float(document["created_at"]) > self.ttl_seconds:
                return None
            payload = document.get("payload")
            return payload if isinstance(payload, dict) else None
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return None

    def put(self, key: str, payload: dict) -> None:
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = self._path(key)
        temporary = path.with_suffix(f".{os.getpid()}.tmp")
        document = {"created_at": time.time(), "payload": payload}
        try:
            temporary.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            temporary.chmod(0o600)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
