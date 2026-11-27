"""A small on-disk cache for detail responses.

Search results are always fetched fresh (prices and stock must be current), but a
detailed part description does not change minute to minute.  Caching those keeps
re-opening a part cheap and keeps the storefront load low.

Entries are one JSON file each, keyed by a hash of the request, so the cache can
be inspected and cleared by hand.
"""

# Vendored from KiCad LibGen LCSC (KicadLibGui-LCSC 1.0.0) at commit 60c89f8.
# Do not edit: refresh with scripts/refresh_client.py.
from __future__ import annotations

import base64
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MAX_ENTRIES = 500


def cache_key(method: str, url: str, params: dict[str, Any] | None = None,
              payload: dict[str, Any] | None = None) -> str:
    """A stable identity for a request."""
    material = json.dumps(
        {"m": method.upper(), "u": url, "p": params or {}, "b": payload or {}},
        sort_keys=True, ensure_ascii=False, default=str,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:40]


class ResponseCache:
    """Time-limited response bodies stored as individual JSON files."""

    def __init__(self, directory: str | Path, ttl: float) -> None:
        self.directory = Path(directory)
        self.ttl = float(ttl)

    @property
    def enabled(self) -> bool:
        return self.ttl > 0

    def path_for(self, key: str) -> Path:
        return self.directory / f"{key}.json"

    def get(self, key: str) -> bytes | None:
        if not self.enabled:
            return None
        path = self.path_for(key)
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        stored = entry.get("stored")
        body = entry.get("body")
        if not isinstance(stored, (int, float)) or not isinstance(body, str):
            return None
        if time.time() - stored > self.ttl:
            self._discard(path)
            return None
        try:
            return base64.b64decode(body)
        except (ValueError, TypeError):  # pragma: no cover - corrupt entry
            self._discard(path)
            return None

    def put(self, key: str, body: bytes) -> None:
        if not self.enabled or not body:
            return
        self.directory.mkdir(parents=True, exist_ok=True)
        entry = {
            "stored": time.time(),
            "body": base64.b64encode(body).decode("ascii"),
        }
        path = self.path_for(key)
        try:
            path.write_text(json.dumps(entry), encoding="utf-8")
        except OSError as exc:
            logger.debug("Could not write cache entry %s: %s", path.name, exc)
            return
        self._trim()

    def clear(self) -> int:
        if not self.directory.exists():
            return 0
        removed = 0
        for item in self.directory.glob("*.json"):
            if self._discard(item):
                removed += 1
        return removed

    # -- internals -------------------------------------------------------

    def _trim(self) -> None:
        try:
            entries = sorted(self.directory.glob("*.json"),
                             key=lambda item: item.stat().st_mtime)
        except OSError:  # pragma: no cover - racing cleanup
            return
        for item in entries[: max(0, len(entries) - MAX_ENTRIES)]:
            self._discard(item)

    @staticmethod
    def _discard(path: Path) -> bool:
        try:
            path.unlink()
            return True
        except OSError:
            return False
