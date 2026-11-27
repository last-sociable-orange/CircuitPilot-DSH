"""Gate S4: ERC, with the expected classes named rather than hoped for.

Phase 1 places parts and wires nothing, so a page is *supposed* to report unconnected and
undriven pins — 696 of the latter across the seven MCB-01 pages. What must not appear is a
class that means the page is wrong: a library that does not resolve, a symbol whose cached
copy differs from the library, a footprint that does not link.

So the check is: every violation must be of a class listed here, and the counts are reported
either way. An unexpected class fails the gate and prints its first examples.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from . import kicad_cli

#: Violation classes a placement-only page may legitimately report.
#:
#: ERC runs on the page alone (`_scratch_project`), so nothing about the parent page or the
#: rest of the hierarchy can appear here: `duplicate_sheet_names` is out of scope by
#: construction, and a label/wire class can only mean something is wrong.
EXPECTED: dict[str, str] = {
    "pin_not_connected": "no wires are drawn in phase 1",
    "pin_not_driven": "no drivers, same reason",
    "power_pin_not_driven": "no power symbols placed",
}


@dataclass
class Report:
    """ERC outcome: counts per class, plus the unexpected ones in detail."""

    counts: dict[str, int] = field(default_factory=dict)
    unexpected: list[dict] = field(default_factory=list)
    checked: str = ""                     # the page ERC ran on
    mode: str = "direct"                  # "direct" or "scratch-project"

    @property
    def ok(self) -> bool:
        return not self.unexpected

    def problems(self) -> list[str]:
        lines = []
        for violation in self.unexpected[:10]:
            description = violation.get("description") or violation.get("type")
            lines.append(f"{violation.get('type')}: {description}")
        if len(self.unexpected) > 10:
            lines.append(f"… and {len(self.unexpected) - 10} more")
        return lines


def classify(violations: list[dict]) -> Report:
    """Split violations into expected classes and everything else."""
    report = Report()
    for violation in violations:
        kind = violation.get("type") or "unknown"
        report.counts[kind] = report.counts.get(kind, 0) + 1
        if kind not in EXPECTED:
            report.unexpected.append(violation)
    return report


def _scratch_project(page: Path, scratch: Path) -> Path:
    """A one-page project that resolves the same libraries as the real one.

    `kicad-cli` matches project to page by *basename*, so ERC on `Sync.kicad_sch` beside
    `MainController.kicad_pro` resolves nothing and reports `lib_symbol_issues` for every
    symbol. Copying the page under its own `.kicad_pro`, with the table URIs made absolute,
    gives ERC exactly one sheet — the page under review — and working libraries.
    """
    project = next(iter(sorted(page.parent.glob("*.kicad_pro"))), None)
    target = scratch / page.name
    target.write_text(page.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    # KiCad needs *a* project named after the page; without one it ignores the tables.
    content = project.read_text(encoding="utf-8") if project is not None else "{}\n"
    (scratch / f"{page.stem}.kicad_pro").write_text(content, encoding="utf-8", newline="\n")
    for table_name in ("sym-lib-table", "fp-lib-table"):
        table = page.parent / table_name
        if not table.is_file():
            continue
        text = table.read_text(encoding="utf-8").replace(
            "${KIPRJMOD}", str(page.parent.resolve()).replace("\\", "/")
        )
        (scratch / table_name).write_text(text, encoding="utf-8", newline="\n")
    return target


def _erc(target: Path, *, timeout: int) -> list[dict]:
    """Run ERC on exactly this file and return its violations."""
    with tempfile.TemporaryDirectory(prefix="schwrite-erc-") as scratch_dir:
        output = Path(scratch_dir) / "erc.json"
        result = kicad_cli.run(
            "sch", "erc", "--format", "json", "--output", str(output), str(target),
            timeout=timeout,
        )
        if result.returncode not in (0, 5):        # kicad-cli reports violations as 5
            raise kicad_cli.ToolError(
                f"kicad-cli erc failed: {(result.stderr or result.stdout).strip()[:300]}"
            )
        if not output.is_file():
            raise kicad_cli.ToolError("kicad-cli wrote no ERC report")
        data = json.loads(output.read_text(encoding="utf-8"))
    violations: list[dict] = []
    for sheet in data.get("sheets") or []:
        violations.extend(sheet.get("violations") or [])
    return violations


def _unresolved(violations: list[dict]) -> bool:
    """True when the run could not see the libraries — `kicad-cli` matched no project.

    It associates a project with a schematic by *basename*, so a child page in a directory
    whose project is called something else resolves nothing and reports `lib_symbol_issues`
    for every symbol. That is the only case that needs a copy.
    """
    return any(v.get("type") == "lib_symbol_issues" for v in violations)


def run(page: str | Path, *, timeout: int = 300) -> Report:
    """ERC **this page**, on the file that was named; a copy only if libraries do not resolve."""
    page = Path(page).resolve()
    if not page.is_file():
        raise kicad_cli.ToolError(f"no page at {page}")

    violations = _erc(page, timeout=timeout)
    mode = "direct"
    if _unresolved(violations):
        # give KiCad a project whose basename matches the page, carrying the project's own
        # library tables with absolute URIs so they still resolve from the scratch directory
        with tempfile.TemporaryDirectory(prefix="schwrite-erc-") as scratch_dir:
            target = _scratch_project(page, Path(scratch_dir))
            violations = _erc(target, timeout=timeout)
        mode = "scratch-project"

    report = classify(violations)
    report.checked = str(page)
    report.mode = mode
    return report
