"""Decode EasyEDA's tilde-delimited document format.

A document is a JSON object whose ``shape`` is a list of records. Each record is a
string: ``~`` separates fields, ``^^`` separates segments (a pin carries seven).
Values are plain strings; this module keeps them as-is and gives the callers small
typed helpers, because the same record type means different things in a symbol and
in a footprint.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

#: One EasyEDA canvas unit is 10 mil.
UNIT_MM = 0.254


class DocumentError(Exception):
    """A record could not be decoded."""


@dataclass(frozen=True)
class Record:
    """One decoded shape line."""

    op: str
    segments: tuple[tuple[str, ...], ...]

    @property
    def fields(self) -> tuple[str, ...]:
        return self.segments[0]

    def field(self, index: int, default: str = "") -> str:
        fields = self.fields
        return fields[index] if index < len(fields) else default

    def segment(self, index: int) -> tuple[str, ...]:
        segments = self.segments
        return segments[index] if index < len(segments) else ()

    def segment_field(self, segment: int, index: int, default: str = "") -> str:
        fields = self.segment(segment)
        return fields[index] if index < len(fields) else default

    def __str__(self) -> str:  # pragma: no cover - debugging aid
        return f"Record({self.op}, {len(self.segments)} segment(s))"


def document(value: Any) -> dict:
    """Return a document dict, accepting the string-or-object forms the API uses."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise DocumentError(f"document is not JSON: {exc}") from exc
        if isinstance(parsed, dict):
            return parsed
    return {}


def parse_records(document_value: Any) -> list[Record]:
    """All records of a document, in source order."""
    doc = document(document_value)
    shapes = doc.get("shape") or []
    records: list[Record] = []
    for line in shapes:
        if not isinstance(line, str) or not line.strip():
            continue
        segments = tuple(tuple(segment.split("~")) for segment in line.split("^^"))
        records.append(Record(op=segments[0][0], segments=segments))
    return records


def head_of(document_value: Any) -> dict:
    doc = document(document_value)
    return document(doc.get("head"))


def number(text: str, default: float = 0.0) -> float:
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


def numbers(text: str) -> list[float]:
    """Parse a whitespace/comma separated number list, ignoring junk."""
    cleaned = text.replace(",", " ")
    found: list[float] = []
    for token in cleaned.split():
        try:
            found.append(float(token))
        except ValueError:
            continue
    return found


def points(text: str) -> list[tuple[float, float]]:
    """Parse ``"x y x y …"`` into coordinate pairs."""
    values = numbers(text)
    return [(values[i], values[i + 1]) for i in range(0, len(values) - 1, 2)]


def millimetres(value: float) -> float:
    return value * UNIT_MM


def millimetre_points(text: str) -> list[tuple[float, float]]:
    return [(x * UNIT_MM, y * UNIT_MM) for x, y in points(text)]
