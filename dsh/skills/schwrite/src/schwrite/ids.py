"""UUIDs for the nodes we create.

KiCad needs a uuid on the page, on every symbol, every pin, every wire and every label.
Fresh v4 uuids are the default. A **seeded** source exists because S6 (reproducibility) and
the tier-1 golden test both need the same page to come out byte-identical twice: with a
seed, uuids are derived deterministically from it and a counter.
"""

from __future__ import annotations

import uuid

#: fixed namespace so a seed always maps to the same uuid
_NAMESPACE = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")


class UuidSource:
    """Fresh v4 uuids, or deterministic uuids derived from `seed`."""

    def __init__(self, seed: str | None = None) -> None:
        self.seed = seed
        self._counter = 0

    def next(self) -> str:
        self._counter += 1
        if self.seed is None:
            return str(uuid.uuid4())
        return str(uuid.uuid5(_NAMESPACE, f"{self.seed}:{self._counter}"))

    def reset(self) -> None:
        self._counter = 0

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"UuidSource(seed={self.seed!r}, n={self._counter})"
