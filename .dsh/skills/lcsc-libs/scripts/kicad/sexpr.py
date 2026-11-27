"""Minimal S-expression helpers for writing KiCad files.

KiCad's own writer uses tabs, numbers without trailing zeros, and quoted strings for
identifiers that may contain spaces. These helpers reproduce that style so the
output is byte-stable and diffs cleanly.
"""

from __future__ import annotations

TAB = "\t"

#: KiCad 10 stamps, read from the installed 10.0.8 libraries.
SYMBOL_VERSION = 20251024
FOOTPRINT_VERSION = 20260206
GENERATOR = "lcsc-libs"
GENERATOR_VERSION = "10.0"


def q(text: object) -> str:
    """A quoted KiCad string."""
    escaped = str(text).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def n(value: float) -> str:
    """A number without trailing zeros, never ``-0``."""
    rounded = round(float(value), 4)
    if rounded == 0:
        rounded = 0.0
    text = f"{rounded:.4f}".rstrip("0").rstrip(".")
    return text or "0"


def indent(level: int) -> str:
    return TAB * level


def line(level: int, text: str) -> str:
    return f"{indent(level)}{text}"
