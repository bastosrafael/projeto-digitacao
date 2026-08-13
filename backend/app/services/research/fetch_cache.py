from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path


PARSER_VERSION = "web-evidence-v1"


@dataclass(frozen=True)
class FetchCacheLookup:
    status: str
    payload: dict | None


class FetchCache:
    def __init__(self, directory: Path, ttl_seconds: int) -> None:
        self.directory = directory
        self.ttl_seconds = ttl_seconds

    def _path(self, url: str) -> Path:
        key = hashlib.sha256(f"{PARSER_VERSION}\0{url}".encode()).hexdigest()
        return self.directory / f"{key}.json"

    def get(self, url: str) -> FetchCacheLookup:
        path = self._path(url)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            created_at = float(data["created_at"])
            if data.get("parser_version") != PARSER_VERSION:
                return FetchCacheLookup("EXPIRED", None)
            if time.time() - created_at > self.ttl_seconds:
                return FetchCacheLookup("EXPIRED", None)
            payload = data.get("payload")
            return FetchCacheLookup("HIT", payload if isinstance(payload, dict) else None)
        except FileNotFoundError:
            return FetchCacheLookup("MISS", None)
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return FetchCacheLookup("EXPIRED", None)

    def put(self, url: str, payload: dict) -> None:
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = self._path(url)
        temporary = path.with_suffix(".part")
        document = {
            "parser_version": PARSER_VERSION,
            "created_at": time.time(),
            "url": url,
            "payload": payload,
        }
        try:
            temporary.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            os.chmod(temporary, 0o600)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
