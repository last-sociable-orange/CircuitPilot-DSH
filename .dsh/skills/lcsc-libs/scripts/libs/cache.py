"""On-disk response cache so re-runs and ``--offline`` never touch the network.

Entries are keyed by a hash of the URL and stored as raw bytes with a small JSON
sidecar, so a cached STEP file can be re-used verbatim and an API response can be
re-parsed after a parser change.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TTL = 7 * 24 * 3600.0


def default_cache_dir() -> Path:
    override = os.environ.get("LCSC_LIBS_CACHE", "").strip()
    if override:
        return Path(override).expanduser()
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CACHE_HOME")
    if base:
        return Path(base) / "lcsc-libs" / "cache"
    return Path.home() / ".cache" / "lcsc-libs"


@dataclass
class CacheEntry:
    path: Path
    meta: dict


class ResponseCache:
    """Content cache with a TTL; ``ttl=0`` disables reads and writes entirely."""

    def __init__(self, directory: Path | str | None = None, *, ttl: float = DEFAULT_TTL) -> None:
        self.directory = Path(directory).expanduser() if directory else default_cache_dir()
        self.ttl = max(0.0, float(ttl))

    @property
    def enabled(self) -> bool:
        return self.ttl > 0

    def _paths(self, url: str) -> tuple[Path, Path]:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]
        return self.directory / f"{digest}.bin", self.directory / f"{digest}.json"

    def get(self, url: str) -> bytes | None:
        if not self.enabled:
            return None
        body, meta = self._paths(url)
        if not body.exists() or not meta.exists():
            return None
        try:
            info = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if info.get("url") != url:
            return None
        stored = float(info.get("stored_at") or 0)
        if self.ttl and (time.time() - stored) > self.ttl:
            return None
        try:
            return body.read_bytes()
        except OSError:
            return None

    def put(self, url: str, payload: bytes, *, extension: str = ".bin") -> None:
        if not self.enabled:
            return
        body, meta = self._paths(url)
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            body.write_bytes(payload)
            meta.write_text(json.dumps({
                "url": url,
                "stored_at": time.time(),
                "bytes": len(payload),
                "extension": extension,
            }), encoding="utf-8")
        except OSError:
            # A read-only cache directory must never break a fetch.
            self.ttl = 0.0

    def clear(self) -> int:
        removed = 0
        if not self.directory.exists():
            return 0
        for entry in self.directory.glob("*"):
            try:
                entry.unlink()
                removed += 1
            except OSError:
                continue
        return removed
