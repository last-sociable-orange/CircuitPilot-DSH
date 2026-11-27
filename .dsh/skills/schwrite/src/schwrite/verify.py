"""Gate S3: does an independent reader see the parts we intended?

`verify` builds nothing. It takes a page that already exists, asks KiCad to read it back,
and compares what KiCad found with what the netlist asked for: same references, same values,
same footprints. Nets are out of scope by design — phase 1 places parts and wires nothing —
so a page passes when the *component* list matches exactly and every footprint agrees.

The comparison lives here as plain functions so it can be tested without KiCad installed;
`readback()` is the only part that needs the tool.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import kicad_cli

#: `( /<uuid> <footprint> <ref> <value> )` — one line per component in an OrCAD netlist.
_COMPONENT = re.compile(r"^\s*\(\s*/\S+\s+(\S+)\s+(\S+)\s+(\S+)\s*$", re.M)


@dataclass
class Comparison:
    """What the page says versus what the netlist asked for."""

    expected: dict[str, tuple[str, str]]          # ref -> (value, footprint)
    actual: dict[str, tuple[str, str]]
    missing: list[str] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)
    wrong_value: list[tuple[str, str, str]] = field(default_factory=list)
    wrong_footprint: list[tuple[str, str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (self.missing or self.extra or self.wrong_value or self.wrong_footprint)

    def problems(self) -> list[str]:
        """Human-readable lines, empty when the page matches."""
        lines: list[str] = []
        if self.missing:
            lines.append(f"missing from the page: {', '.join(sorted(self.missing))}")
        if self.extra:
            lines.append(f"not in the netlist: {', '.join(sorted(self.extra))}")
        for ref, want, got in sorted(self.wrong_value):
            lines.append(f"{ref}: value {got!r} on the page, {want!r} in the netlist")
        for ref, want, got in sorted(self.wrong_footprint):
            lines.append(f"{ref}: footprint {got!r} on the page, {want!r} in the netlist")
        return lines


def parse_orcad(text: str) -> dict[str, tuple[str, str]]:
    """`{ref: (value, footprint)}` from an OrCAD-format netlist."""
    found: dict[str, tuple[str, str]] = {}
    for footprint, ref, value in _COMPONENT.findall(text):
        found[ref] = (value, footprint)
    return found


def expected_from_parts(parts) -> dict[str, tuple[str, str]]:
    """`{ref: (value, footprint)}` for the parts the netlist resolves to."""
    return {part.ref: (part.value, part.footprint) for part in parts}


def compare(expected: dict[str, tuple[str, str]], actual: dict[str, tuple[str, str]]) -> Comparison:
    """Field-by-field comparison; the page must hold exactly the intended parts."""
    result = Comparison(expected=expected, actual=actual)
    result.missing = sorted(set(expected) - set(actual))
    result.extra = sorted(set(actual) - set(expected))
    for ref in sorted(set(expected) & set(actual)):
        want_value, want_footprint = expected[ref]
        got_value, got_footprint = actual[ref]
        if want_value != got_value:
            result.wrong_value.append((ref, want_value, got_value))
        if want_footprint != got_footprint:
            result.wrong_footprint.append((ref, want_footprint, got_footprint))
    return result


def readback(page: str | Path, *, timeout: int = 300) -> dict[str, tuple[str, str]]:
    """Ask KiCad to read the page back and return its component list.

    KiCad resolves the page through the `sym-lib-table` beside it, so a page built with
    `--no-sym-lib-table` in a bare directory reads back empty — that is a real failure, not
    an empty page, and the caller's comparison will say so.
    """
    page = Path(page).resolve()
    if not page.is_file():
        raise kicad_cli.ToolError(f"no page at {page}")
    output = page.with_suffix(".verify.net")
    try:
        result = kicad_cli.run(
            "sch", "export", "netlist",
            "--format", "orcadpcb2",
            "--output", str(output),
            str(page),
            timeout=timeout,
        )
        if result.returncode != 0:
            raise kicad_cli.ToolError(
                f"kicad-cli could not read {page.name}: "
                f"{(result.stderr or result.stdout).strip()[:300]}"
            )
        if not output.is_file():
            return {}
        return parse_orcad(output.read_text(encoding="utf-8", errors="replace"))
    finally:
        output.unlink(missing_ok=True)
