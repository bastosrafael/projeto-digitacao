from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from pathlib import Path


def normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", query)).strip().casefold()


class SearchCache:
    def __init__(self, directory: Path, ttl_seconds: int) -> None:
        self.directory = directory
        self.ttl = timedelta(seconds=ttl_seconds)

    def _path(self, provider: str, query: str) -> Path:
        identity = f"{provider.casefold()}\0{normalize_query(query)}".encode("utf-8")
        return self.directory / f"{hashlib.sha256(identity).hexdigest()}.json"

    def get(self, provider: str, query: str) -> dict | None:
        path = self._path(provider, query)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            stored_at = datetime.fromisoformat(payload["stored_at"])
            if stored_at.tzinfo is None:
                stored_at = stored_at.replace(tzinfo=UTC)
            if datetime.now(UTC) - stored_at > self.ttl:
                return None
            if payload.get("provider") != provider or payload.get("normalized_query") != normalize_query(query):
                return None
            response = payload.get("response")
            return response if isinstance(response, dict) else None
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def put(self, provider: str, query: str, response: dict) -> None:
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = self._path(provider, query)
        temporary = path.with_suffix(f".{os.getpid()}.tmp")
        payload = {
            "schema_version": 1,
            "provider": provider,
            "query": query,
            "normalized_query": normalize_query(query),
            "stored_at": datetime.now(UTC).isoformat(),
            "status": "OK",
            "response": response,
        }
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(path)
