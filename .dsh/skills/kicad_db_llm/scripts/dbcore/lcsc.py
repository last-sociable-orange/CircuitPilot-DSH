"""Get part data without ever inventing any.

Two sources, one shape:

* the sibling ``lcsc-parts`` skill, called as a subprocess
  (``lcsc.py detail C25804 --json``) — the authoritative path;
* a JSON file someone already captured from that same command, so a lead agent
  can hand over data it fetched earlier and this skill can run offline.

Nothing here parses a storefront response itself. If the numbers are wrong, they
are wrong in the one place that already owns them.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from .config import Config
from .parts import Part


class LookupProblem(RuntimeError):
    """A part could not be looked up, or the lookup returned nothing usable."""


class StorefrontRefused(LookupProblem):
    """The storefront refused to answer at all — a run-level stop, not a bad part.

    ``lcsc-parts`` reports these distinctly now (rate limit, sign-in wall, an
    over-long Retry-After), and retrying them once per BOM line only deepens the
    block, so the batch stops the first time it happens.
    """


#: Phrases the lcsc-parts CLI prints when the store answered with a refusal, not data.
REFUSAL_MARKERS = (
    "refused the request",
    "sign-in page",
    "asked for a long pause",
    "is rate limiting requests",
)


def is_refusal(text: str) -> bool:
    """True when a failed child call was a storefront refusal rather than a bad part."""
    return any(marker in (text or "") for marker in REFUSAL_MARKERS)


class Lookup:
    """Resolve part identifiers to :class:`Part` objects."""

    def __init__(self, config: Config, *, python: str | None = None, timeout: float = 120.0):
        self.config = config
        self.python = python or sys.executable
        self.timeout = timeout
        self._cache: dict[str, Part] = {}

    # -- pre-captured data ---------------------------------------------

    def load_json(self, path: str | Path) -> int:
        """Merge a captured payload file into the cache; returns how many parts."""
        file = Path(path)
        try:
            data = json.loads(file.read_text(encoding="utf-8-sig"))
        except OSError as exc:
            raise LookupProblem(f"cannot read {file}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise LookupProblem(f"{file} is not valid JSON: {exc}") from exc
        count = 0
        for payload in _iter_payloads(data):
            part = Part.from_detail(payload)
            if not part.identity:
                continue
            self._cache[part.lcsc.upper()] = part
            self._cache[part.identity.upper()] = part
            count += 1
        return count

    # -- live lookup ----------------------------------------------------

    def fetch(self, identifiers: list[str], *, lang: str | None = None) -> dict[str, Part]:
        """Look up every identifier that is not already cached."""
        wanted = [item for item in identifiers if item and item.upper() not in self._cache]
        codes = [item.upper() for item in wanted if _looks_like_lcsc(item)]
        mpns = [item for item in wanted if not _looks_like_lcsc(item)]
        if codes:
            self._run_detail(codes, lang or self.config.language)
        for mpn in mpns:
            self._resolve_mpn(mpn, lang or self.config.language)
        missing = [item for item in wanted if item.upper() not in self._cache]
        if missing:
            raise LookupProblem(
                "no data for: "
                + ", ".join(missing)
                + ". The part number may be wrong, or the CLI could not reach the store."
            )
        return {item.upper(): self._cache[item.upper()] for item in wanted}

    def get(self, identifier: str) -> Part | None:
        return self._cache.get(identifier.upper())

    def _run_detail(self, codes: list[str], lang: str) -> None:
        # ``--lang`` is a global option of the lcsc-parts CLI: it must come first.
        payloads = self._call(["--lang", lang, "detail", *codes, "--json"])
        for payload in _iter_payloads(payloads):
            part = Part.from_detail(payload)
            if part.identity:
                self._cache[part.lcsc.upper()] = part
                self._cache[part.identity.upper()] = part

    def _resolve_mpn(self, mpn: str, lang: str) -> None:
        payloads = self._call(["--lang", lang, "search", mpn, "--json", "--limit", "10"])
        target = mpn.strip().upper()
        for candidate in _iter_payloads(payloads):  # already flattened to parts
            if not isinstance(candidate, dict):
                continue
            if str(candidate.get("mpn") or "").strip().upper() != target:
                continue
            part = Part.from_detail(candidate)
            if part.lcsc:
                self._cache[part.lcsc.upper()] = part
                self._cache[part.identity.upper()] = part
                return

    def _call(self, arguments: list[str]) -> Any:
        cli = self.config.lcsc_parts_cli
        if not cli.is_file():
            raise LookupProblem(
                f"the lcsc-parts skill is not at {cli}. Pass --detail-json with captured "
                "data, or point 'lcsc_parts' in kicad_db.json at scripts/lcsc.py."
            )
        command = [self.python, str(cli), *arguments]
        # The child prints part data containing Ω and ℃. Without these two
        # variables a Windows child inherits cp1252 and dies on the first such
        # character, which looks like a storefront failure but is not.
        environment = dict(os.environ)
        environment["PYTHONIOENCODING"] = "utf-8"
        environment["PYTHONUTF8"] = "1"
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
                env=environment,
            )
        except subprocess.TimeoutExpired as exc:
            raise LookupProblem(f"lcsc-parts timed out after {self.timeout:.0f}s") from exc
        except OSError as exc:
            raise LookupProblem(f"cannot run {cli}: {exc}") from exc
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip().splitlines()
            tail = " / ".join(detail[-3:]) if detail else "no output"
            if is_refusal(tail):
                # Not a bad part: the storefront said no. Stop the batch here rather
                # than replaying the same refusal once per remaining BOM line.
                raise StorefrontRefused(
                    "the storefront refused the batch — wait a minute (or raise "
                    f"--interval) and rerun. Its answer: {tail}"
                )
            raise LookupProblem(f"lcsc-parts failed ({completed.returncode}): {tail}")
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise LookupProblem(f"lcsc-parts returned non-JSON output: {exc}") from exc


def _iter_payloads(data: Any):
    """Yield part objects from the shapes ``lcsc-parts`` can print."""
    if isinstance(data, list):
        for item in data:
            yield from _iter_payloads(item)
        return
    if not isinstance(data, dict):
        return
    if "parts" in data and isinstance(data["parts"], list):
        yield from _iter_payloads(data["parts"])
        return
    if "part" in data and isinstance(data["part"], dict):
        yield data["part"]
        return
    if "lcsc" in data or "mpn" in data:
        yield data


def _looks_like_lcsc(identifier: str) -> bool:
    text = identifier.strip().upper()
    return len(text) > 1 and text[0] == "C" and text[1:].isdigit()
