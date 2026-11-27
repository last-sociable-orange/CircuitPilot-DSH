"""Plan a BOM, commit it, and check a database against the library tree."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import schema
from .config import Config
from .lcsc import Lookup, LookupProblem, StorefrontRefused
from .libraries import LibrarySet
from .mapping import Mapping, build_record, decide
from .parts import BomLine, Part
from .stage import BundlePart


@dataclass
class Outcome:
    line: BomLine
    action: str = "blocked"  # insert | update | skip | blocked | error
    part: Part | None = None
    mapping: Mapping | None = None
    record: schema.Record | None = None
    existing: schema.Record | None = None
    message: str = ""

    @property
    def label(self) -> str:
        if self.part is not None:
            return self.part.identity or self.part.lcsc
        return self.line.identifier or f"row {self.line.row}"

    @property
    def blocked(self) -> bool:
        return self.action in ("blocked", "error")


def _prefetch(lookup: Lookup, identifiers: list[str]) -> None:
    """Ask the storefront once for every part the batch has not looked up yet.

    Before this, ``plan`` called ``fetch([identifier])`` inside the loop: a 40-line BOM
    was 40 child processes, 40 HTTP requests and 40 chances to be throttled. One call
    for the whole batch is also what lets a refusal stop the run instead of repeating
    on every line.
    """
    missing: list[str] = []
    seen: set[str] = set()
    for identifier in identifiers:
        key = (identifier or "").upper()
        if not key or key in seen:
            continue          # several refs can share one part: ask for it once
        seen.add(key)
        if lookup.get(identifier) is None:
            missing.append(identifier)
    if not missing:
        return
    try:
        lookup.fetch(missing)
    except StorefrontRefused:
        raise                     # run-level stop: the storefront said no
    except LookupProblem:
        pass                      # individual misses are reported per line below


def plan(
    lines: list[BomLine],
    libs: LibrarySet,
    lookup: Lookup,
    *,
    mode: str = "auto",
    find_existing=None,
    bundles: dict[str, BundlePart] | None = None,
) -> list[Outcome]:
    """Decide every line, without writing anything.

    A line is never dropped silently: an unresolvable part becomes an ``error``
    outcome with the reason, a part whose mapping cannot be proven becomes
    ``blocked`` with the files it needs, and a part already in the database
    becomes ``skip`` — the plan says so *before* anything is written, so a dry
    run and a write cannot disagree.

    ``find_existing`` is called with an MPN and returns the row already stored
    (or ``None``); pass :func:`existing_lookup` for the configured database.
    """
    bundles = bundles or {}
    outcomes: list[Outcome] = []
    _prefetch(lookup, [line.identifier for line in lines if line.identifier])
    for line in lines:
        outcome = Outcome(line=line)
        outcomes.append(outcome)
        identifier = line.identifier
        if not identifier:
            outcome.action = "error"
            outcome.message = "row names no part (neither lcsc nor mpn)"
            continue
        try:
            part = lookup.get(identifier) or lookup.fetch([identifier])[identifier.upper()]
        except (LookupProblem, KeyError) as exc:
            outcome.action = "error"
            outcome.message = str(exc)
            continue
        outcome.part = part

        bundle = bundles.get(part.lcsc.upper())
        mapping = decide(
            part,
            line,
            libs,
            mode=mode,
            bundle_symbol=bundle.symbol if bundle else None,
            bundle_footprint=bundle.footprint if bundle else None,
        )
        outcome.mapping = mapping
        if mapping.blockers:
            outcome.action = "blocked"
            outcome.message = " | ".join(mapping.blockers)
            continue

        record = build_record(part, line, mapping)
        outcome.record = record
        previous = find_existing(record.mpn) if find_existing is not None else None
        outcome.existing = previous
        if previous is not None:
            outcome.action = "skip"
            outcome.message = "already in the database (skipped; no changes written)"
        else:
            outcome.action = "insert"
    return outcomes


def existing_lookup(config: Config):
    """A cached ``mpn -> Record`` lookup for the configured database, or ``None``.

    Returns ``None`` when the database file does not exist yet, so a first run
    plans every line as an insert instead of creating an empty file early.
    """
    if not Path(config.database).is_file():
        return None
    connection = schema.open_database(config.database, create=False)
    cache: dict[str, schema.Record | None] = {}

    def find(mpn: str) -> schema.Record | None:
        if mpn not in cache:
            cache[mpn] = schema.find_by_mpn(connection, mpn)
        return cache[mpn]

    find.close = connection.close  # type: ignore[attr-defined]
    return find


@dataclass
class CommitSummary:
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    changed_fields: dict[str, list[str]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def commit(
    config: Config,
    outcomes: list[Outcome],
    *,
    on_exist: str = "skip",
) -> CommitSummary:
    """Write the planned rows in one transaction.

    ``on_exist`` decides what a *conflict* means. The plan already marks existing
    MPNs as ``skip``; ``update`` and ``fail`` are applied here so that a dry run
    and a write agree about what will happen.
    """
    if on_exist not in ("skip", "update", "fail"):
        raise ValueError("on_exist must be skip, update or fail")
    summary = CommitSummary()
    connection = schema.open_database(config.database)

    try:
        conflicts = [item for item in outcomes if item.existing is not None]
        if on_exist == "fail" and conflicts:
            summary.failed = len(conflicts)
            summary.errors.append(
                "refusing to write: "
                + ", ".join(item.label for item in conflicts)
                + " already exist (--on-exist fail)"
            )
            return summary

        for item in outcomes:
            if item.blocked or item.record is None:
                summary.failed += 1
                if item.message:
                    summary.errors.append(f"{item.label}: {item.message}")
                continue
            if item.existing is not None:
                if on_exist == "skip":
                    # mark the outcome, not just the counter: the write loop below
                    # selects on ``action`` and would otherwise insert a duplicate
                    item.action = "skip"
                    item.message = "already in the database (skipped; no changes written)"
                    summary.skipped += 1
                    continue
                item.action = "update"

        writes = [item for item in outcomes if item.action in ("insert", "update")]
        with schema.transaction(connection):
            for item in writes:
                assert item.record is not None
                if item.action == "insert":
                    schema.insert_record(connection, item.record)
                    summary.inserted += 1
                else:
                    schema.update_record(connection, item.record)
                    summary.updated += 1
                    changed = _changed_fields(item.existing, item.record)
                    if changed:
                        summary.changed_fields[item.label] = changed
    finally:
        connection.close()
    return summary


def _changed_fields(before: schema.Record | None, after: schema.Record) -> list[str]:
    if before is None:
        return []
    changed: list[str] = []
    for name in schema.ALL_COLUMNS:
        if before.values.get(name, "") != after.values.get(name, ""):
            changed.append(name)
    return changed


# -- database verification --------------------------------------------------


@dataclass
class RowProblem:
    mpn: str
    rowid: int
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class VerifyReport:
    rows: int = 0
    ok: int = 0
    problems: list[RowProblem] = field(default_factory=list)
    warnings: list[RowProblem] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def verify(config: Config, libs: LibrarySet) -> VerifyReport:
    """Check every row's symbol/footprint reference against the files on disk."""
    report = VerifyReport()
    connection = schema.open_database(config.database, create=False)
    try:
        rows = schema.all_rows(connection)
    finally:
        connection.close()
    report.rows = len(rows)
    for row in rows:
        record = schema.record_from_row(row)
        problems: list[str] = []
        warnings: list[str] = []
        seen: set[str] = set()
        for column in ("KicadSymbolLibrary", "KicadFootprintLibrary"):
            reference = record.values.get(column, "").strip()
            if not reference:
                problems.append(f"{column} is empty")
                continue
            symbol = column == "KicadSymbolLibrary"
            key = f"{column}:{reference}"
            if key in seen:
                continue
            seen.add(key)
            if symbol:
                info, problem = libs.resolve_symbol(reference)
            else:
                info, problem = libs.resolve_footprint(reference)
            if info is None:
                problems.append(f"{reference}: {problem}")
            elif not symbol:
                model = getattr(info, "model", "")
                if model:
                    step = _step_from_reference(config, model)
                    if step is not None and not step.is_file():
                        warnings.append(f"{reference} references a missing model {step}")
        if problems:
            report.problems.append(RowProblem(record.mpn, int(row["rowid"]), problems))
        elif warnings:
            report.warnings.append(RowProblem(record.mpn, int(row["rowid"]), [], warnings))
            report.ok += 1
        else:
            report.ok += 1
    duplicates = _duplicates(rows)
    if duplicates:
        report.notes.append(
            "duplicate MPNs: " + ", ".join(f"{mpn} (x{count})" for mpn, count in duplicates)
        )
    return report


def _step_from_reference(config: Config, reference: str) -> Path | None:
    """Turn ``${KIPRJMOD}/../kicad_lib/Step/X.stp`` into a local path."""
    text = reference.strip()
    marker = "kicad_lib/"
    if marker in text:
        tail = text.split(marker, 1)[1]
        return config.libs_root / tail
    candidate = Path(text)
    return candidate if candidate.is_absolute() else None


def _duplicates(rows) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for row in rows:
        mpn = str(row["ManufacturerProductNumber"] or "")
        if mpn:
            counts[mpn] = counts.get(mpn, 0) + 1
    return sorted(
        ((mpn, count) for mpn, count in counts.items() if count > 1),
        key=lambda item: (-item[1], item[0]),
    )
