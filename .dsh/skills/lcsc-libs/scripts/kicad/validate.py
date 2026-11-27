"""Structural checks for generated KiCad files.

These do not replace KiCad itself — they catch the mistakes KiCad would report as a
hard parse failure (unbalanced parentheses, empty roots) before you open the file.
"""

from __future__ import annotations


class ValidationError(Exception):
    """A generated file failed a structural check."""


def check_balanced(text: str, *, label: str = "file") -> None:
    """Parentheses must balance outside of quoted strings."""
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                raise ValidationError(f"{label}: unbalanced ')' at offset {index}")
    if in_string:
        raise ValidationError(f"{label}: unterminated string")
    if depth != 0:
        raise ValidationError(f"{label}: {depth} unclosed '('")


def check_symbol_library(text: str, *, expected_symbol: str | None = None) -> None:
    check_balanced(text, label="symbol library")
    if not text.startswith("(kicad_symbol_lib"):
        raise ValidationError("symbol library must start with (kicad_symbol_lib")
    if "(version " not in text:
        raise ValidationError("symbol library has no (version …)")
    if expected_symbol and f'(symbol "{expected_symbol}"' not in text:
        raise ValidationError(f"symbol {expected_symbol!r} not found in the library")


def check_footprint(text: str, *, expected_name: str | None = None) -> None:
    check_balanced(text, label="footprint")
    if not text.lstrip().startswith("(footprint "):
        raise ValidationError("footprint must start with (footprint …")
    if expected_name and f'(footprint "{expected_name}"' not in text:
        raise ValidationError(f"footprint name {expected_name!r} not found")


def count_pads(text: str) -> int:
    return text.count("\n\t(pad ")
