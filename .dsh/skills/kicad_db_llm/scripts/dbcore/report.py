"""Render decisions for a human and for a caller that parses JSON.

The report is the point of the skill as much as the database write is: it says
which parts used the standard library, which used the downloaded files, and why.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from .config import Config
from .mapping import Mapping
from .parts import BomLine
from .runner import CommitSummary, Outcome, VerifyReport


def _table(headers: list[str], rows: list[list[str]], *, limits: list[int] | None = None) -> str:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            if limits and limits[index]:
                cell = _clip(cell, limits[index])
            widths[index] = max(widths[index], len(cell))
    lines = []
    header = "  ".join(header.ljust(widths[i]) for i, header in enumerate(headers))
    lines.append(header.rstrip())
    lines.append("  ".join("-" * widths[i] for i in range(len(headers))))
    for row in rows:
        cells = []
        for index, cell in enumerate(row):
            if limits and limits[index]:
                cell = _clip(cell, limits[index])
            cells.append(cell.ljust(widths[index]))
        lines.append("  ".join(cells).rstrip())
    return "\n".join(lines)


def _clip(text: str, width: int) -> str:
    text = (text or "").replace("\n", " ")
    if len(text) <= width:
        return text
    return text[: width - 1] + "…"


def plan_text(outcomes: list[Outcome], *, show_evidence: bool = True) -> str:
    rows: list[list[str]] = []
    notes: list[str] = []
    for index, outcome in enumerate(outcomes, start=1):
        mapping = outcome.mapping
        symbol = mapping.symbol if mapping else ""
        footprint = mapping.footprint if mapping else ""
        klass = mapping.classification.code if mapping else "-"
        rows.append(
            [
                str(index),
                outcome.line.lcsc or outcome.line.mpn,
                outcome.label,
                klass,
                symbol,
                footprint,
                outcome.action.upper(),
            ]
        )
        if mapping is not None:
            for blocker in mapping.blockers:
                notes.append(f"  {index}. BLOCKED  {blocker}")
            if show_evidence:
                for assumption in mapping.assumed:
                    notes.append(f"  {index}. ASSUMED  {assumption}")
                for warning in mapping.warnings:
                    notes.append(f"  {index}. WARNING  {warning}")
                for evidence in mapping.evidence:
                    notes.append(f"  {index}.          {evidence}")
        elif outcome.message:
            notes.append(f"  {index}. ERROR    {outcome.message}")
    body = _table(
        ["#", "lcsc", "part", "class", "symbol", "footprint", "action"],
        rows,
        limits=[3, 10, 26, 20, 40, 42, 8],
    )
    if not notes:
        return body
    return body + "\n\n" + "\n".join(notes)


def plan_json(outcomes: list[Outcome]) -> list[dict[str, Any]]:
    payload = []
    for outcome in outcomes:
        mapping = outcome.mapping
        entry: dict[str, Any] = {
            "row": outcome.line.row,
            "lcsc": outcome.line.lcsc,
            "mpn": outcome.line.mpn,
            "part": outcome.label,
            "action": outcome.action,
            "message": outcome.message,
        }
        if mapping is not None:
            entry.update(_mapping_payload(mapping))
        if outcome.record is not None:
            entry["columns"] = outcome.record.row_dict()
        if outcome.existing is not None:
            entry["existing"] = outcome.existing.row_dict()
        payload.append(entry)
    return payload


def _mapping_payload(mapping: Mapping) -> dict[str, Any]:
    return {
        "class": mapping.classification.code,
        "class_evidence": mapping.classification.evidence,
        "product_type": mapping.classification.product_type,
        "library_name": mapping.name,
        "symbol": mapping.symbol,
        "footprint": mapping.footprint,
        "symbol_source": mapping.symbol_source,
        "footprint_source": mapping.footprint_source,
        "evidence": mapping.evidence,
        "warnings": mapping.warnings,
        "assumed": mapping.assumed,
        "blockers": mapping.blockers,
    }


def plan_markdown(
    outcomes: list[Outcome],
    *,
    config: Config,
    summary: CommitSummary | None = None,
    title: str = "Component database plan",
) -> str:
    lines = [f"# {title}", ""]
    lines.append(f"- database: `{config.database}`")
    lines.append(f"- libraries: `{config.libs_root}`")
    lines.append(f"- standard symbols: `{config.standard_symbol.path}`")
    lines.append("")
    lines.append("| # | LCSC | Part | Class | Symbol | Footprint | Action |")
    lines.append("|---|---|---|---|---|---|---|")
    for index, outcome in enumerate(outcomes, start=1):
        mapping = outcome.mapping
        lines.append(
            "| {n} | {lcsc} | {part} | {klass} | `{symbol}` | `{footprint}` | {action} |".format(
                n=index,
                lcsc=outcome.line.lcsc or "-",
                part=outcome.label,
                klass=mapping.classification.code if mapping else "-",
                symbol=mapping.symbol if mapping else "-",
                footprint=mapping.footprint if mapping else "-",
                action=outcome.action,
            )
        )
    details: list[str] = []
    for index, outcome in enumerate(outcomes, start=1):
        mapping = outcome.mapping
        if mapping is None:
            details.append(f"{index}. **{outcome.label}** — error: {outcome.message}")
            continue
        if not (mapping.blockers or mapping.warnings or mapping.assumed or mapping.evidence):
            continue
        details.append(f"{index}. **{outcome.label}** ({mapping.classification.label})")
        for blocker in mapping.blockers:
            details.append(f"   - blocked: {blocker}")
        for assumption in mapping.assumed:
            details.append(f"   - assumed: {assumption}")
        for warning in mapping.warnings:
            details.append(f"   - warning: {warning}")
        for evidence in mapping.evidence:
            details.append(f"   - evidence: {evidence}")
    if details:
        lines.append("")
        lines.append("## Decisions and reasons")
        lines.append("")
        lines.extend(details)
    if summary is not None:
        lines.append("")
        lines.append("## Result")
        lines.append("")
        lines.append(f"- inserted: {summary.inserted}")
        lines.append(f"- updated: {summary.updated}")
        lines.append(f"- skipped (already present): {summary.skipped}")
        lines.append(f"- not written (blocked or failed): {summary.failed}")
        for label, columns in summary.changed_fields.items():
            lines.append(f"- `{label}` changed: {', '.join(columns)}")
        for error in summary.errors:
            lines.append(f"- error: {error}")
    return "\n".join(lines) + "\n"


def verify_text(report: VerifyReport) -> str:
    lines = [
        f"rows: {report.rows}   resolved: {report.ok}   with problems: {len(report.problems)}   "
        f"with warnings: {len(report.warnings)}"
    ]
    if report.problems:
        lines.append("")
        lines.append("Rows that KiCad cannot resolve:")
        for problem in report.problems:
            lines.append(f"  row {problem.rowid}  {problem.mpn}")
            for item in problem.problems:
                lines.append(f"      {item}")
    if report.warnings:
        lines.append("")
        lines.append("Rows with warnings:")
        for warning in report.warnings:
            lines.append(f"  row {warning.rowid}  {warning.mpn}")
            for item in warning.warnings:
                lines.append(f"      {item}")
    if report.notes:
        lines.append("")
        lines.extend(f"note: {note}" for note in report.notes)
    return "\n".join(lines)


def verify_json(report: VerifyReport) -> dict[str, Any]:
    return {
        "rows": report.rows,
        "resolved": report.ok,
        "problems": [
            {"rowid": item.rowid, "mpn": item.mpn, "problems": item.problems}
            for item in report.problems
        ],
        "warnings": [
            {"rowid": item.rowid, "mpn": item.mpn, "warnings": item.warnings}
            for item in report.warnings
        ],
        "notes": report.notes,
    }


def layout_text(rows: Iterable[tuple[str, str, str]]) -> str:
    return _table(["section", "value", "state"], [list(row) for row in rows], limits=[22, 60, 60])


def stages_text(results: list[Any]) -> str:
    rows = []
    notes = []
    for result in results:
        for item in result.files:
            source = str(item.source) if item.source and item.source.name else "-"
            rows.append([result.name, item.kind, source, str(item.target), item.action])
            if item.note:
                notes.append(f"  {result.name}: {item.kind}: {item.note}")
        for problem in result.problems:
            notes.append(f"  {result.name}: PROBLEM  {problem}")
        for warning in getattr(result, "warnings", []):
            notes.append(f"  {result.name}: WARNING  {warning}")
    body = _table(
        ["name", "kind", "source", "target", "action"],
        rows,
        limits=[28, 10, 44, 52, 12],
    )
    if notes:
        body += "\n\n" + "\n".join(notes)
    return body


def dumps(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, default=str)


def bom_summary_text(outcomes: list[Outcome]) -> str:
    counts: dict[str, int] = {}
    for outcome in outcomes:
        counts[outcome.action] = counts.get(outcome.action, 0) + 1
    ordered = ", ".join(f"{name}: {count}" for name, count in sorted(counts.items()))
    return f"{len(outcomes)} line(s) — {ordered}" if ordered else "no lines"


def line_label(line: BomLine) -> str:
    return line.lcsc or line.mpn or f"row {line.row}"
