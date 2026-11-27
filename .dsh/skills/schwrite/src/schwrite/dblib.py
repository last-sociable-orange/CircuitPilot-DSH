"""KiCad database-library resolution — the only source of parts (§2, §8.1).

A database library is a `.kicad_dbl` (JSON) that names an SQLite table and the columns
carrying symbol, footprint and value. This module reads that description, opens the SQLite
file it points at, and resolves a netlist component to the row that defines it.

The rule the whole tool lives by: **only parts that exist in this database may be placed.**
A component that does not resolve is a hard failure (`PartError`), never a fallback to an
ad-hoc library id.

Ported from `schgen.dblib` (2026-11-25) with three changes: the error type is `DbError`
from `errors.py`; a missing `Database=` target falls back to a sibling `components.db` so a
copied fixture tree still resolves; and rows expose their columns verbatim (`columns`) so
the field block can be driven by the DB rather than by a hardcoded list (§8.5 amendment G).
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import DbError, PartError

DEFAULT_DBL_NAMES = (
    "components_db_windows.kicad_dbl",
    "components_db_linux.kicad_dbl",
    "components_db_macos.kicad_dbl",
)


@dataclass
class DbRow:
    """One `components` row, reduced to what the page builder needs."""

    key: str
    symbol: str            # "Standard:R" — the geometry library id
    footprint: str         # "Standard:R_0402"
    value: str
    mpn: str
    lcsc: str = ""
    columns: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "symbol": self.symbol,
            "footprint": self.footprint,
            "value": self.value,
            "mpn": self.mpn,
            "lcsc": self.lcsc,
            "columns": dict(self.columns),
        }


def default_dbl_path(project: Path, platform: str | None = None) -> Path:
    """``<project>/kicad_lib/components_db_<os>.kicad_dbl`` for the running platform."""
    name = platform or ("windows" if os.name == "nt" else "linux")
    return Path(project) / "kicad_lib" / f"components_db_{name}.kicad_dbl"


def _resolve_db_path(dbl_path: Path, description: dict[str, Any]) -> Path:
    """Turn the dbl's ODBC connection string into a real SQLite file path.

    The shipped files use ``Database=${CWD}\\..\\kicad_lib\\components.db`` and KiCad
    expands ``${CWD}`` to the directory holding the ``.kicad_dbl``. When the expanded path
    does not exist (a fixture tree with the database sitting next to the `.kicad_dbl`), the
    sibling `components.db` is used — the same file, reached without the `..\\kicad_lib`.
    """
    source = description.get("source") or {}
    connection = source.get("connection_string") or ""
    sibling = dbl_path.parent / "components.db"
    match = re.search(r"Database=([^;]+)", connection)
    if not match:
        if sibling.is_file():
            return sibling
        raise DbError(f"no Database= entry in {dbl_path.name} and no sibling components.db")

    raw = match.group(1).strip().strip("{}")
    raw = raw.replace("${CWD}", str(dbl_path.parent)).replace("${KIPRJMOD}", str(dbl_path.parent))
    raw = raw.replace("\\\\", "\\")     # Windows separators escaped inside the JSON string
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = (dbl_path.parent / candidate).resolve()
    if candidate.is_file():
        return candidate
    if sibling.is_file():
        return sibling
    return candidate


class ComponentDb:
    """A `.kicad_dbl` plus the SQLite file behind it."""

    def __init__(self, dbl_path: Path) -> None:
        self.dbl_path = Path(dbl_path).resolve()
        if not self.dbl_path.is_file():
            raise DbError(f"database library not found: {self.dbl_path}")
        try:
            description = json.loads(self.dbl_path.read_text(encoding="utf-8"))
        except Exception as error:  # noqa: BLE001 - report, never guess
            raise DbError(f"{self.dbl_path.name} is not readable JSON: {error}") from error

        libraries = description.get("libraries") or []
        if not libraries:
            raise DbError(f"{self.dbl_path.name} declares no libraries")
        library = libraries[0]
        self.nickname = str(library.get("name") or "")
        self.table = str(library.get("table") or "")
        self.key_column = str(library.get("key") or "ID")
        self.symbol_column = str(library.get("symbols") or "KicadSymbolLibrary")
        self.footprint_column = str(library.get("footprints") or "KicadFootprintLibrary")
        self.field_columns: list[str] = [
            str(entry.get("column") or "") for entry in library.get("fields") or []
        ]
        #: `(property name, column)` in the order the `.kicad_dbl` declares them. KiCad
        #: writes every one of these onto a symbol placed from this library, empty or not,
        #: so the schema — not our taste — decides which fields a page carries.
        self.field_specs: list[tuple[str, str]] = [
            (str(entry.get("name") or entry.get("column") or ""), str(entry.get("column") or ""))
            for entry in library.get("fields") or []
            if entry.get("column")
        ]
        if not (self.nickname and self.table):
            raise DbError(f"{self.dbl_path.name}: library name/table missing")

        self.db_path = _resolve_db_path(self.dbl_path, description)
        if not self.db_path.is_file():
            raise DbError(
                f"SQLite database referenced by {self.dbl_path.name} is missing: {self.db_path}"
            )

    # -- queries -------------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        return connection

    def columns(self) -> list[str]:
        with self._connect() as connection:
            return [row[1] for row in connection.execute(f"PRAGMA table_info({self.table})")]

    def count(self) -> int:
        with self._connect() as connection:
            return int(connection.execute(f"SELECT COUNT(*) FROM {self.table}").fetchone()[0])

    def all_keys(self) -> list[str]:
        with self._connect() as connection:
            return [
                str(row[0])
                for row in connection.execute(f"SELECT {self.key_column} FROM {self.table}")
            ]

    def lookup(self, identifier: str) -> DbRow | None:
        """Find a row by MPN, by distributor (LCSC) number, or by primary key."""
        if not identifier:
            return None
        columns = set(self.columns())
        clauses = [f"{self.key_column} = ?"]
        params: list[str] = [identifier]
        for column in ("ManufacturerProductNumber", "DistributorProductNumber"):
            if column in columns:
                clauses.append(f"{column} = ?")
                params.append(identifier)
        sql = f"SELECT * FROM {self.table} WHERE " + " OR ".join(clauses) + " LIMIT 1"
        with self._connect() as connection:
            row = connection.execute(sql, params).fetchone()
        if row is None:
            return None
        return self._to_row(row)

    def _to_row(self, row: sqlite3.Row) -> DbRow:
        data = {key: row[key] for key in row.keys()}
        symbol = str(data.get(self.symbol_column) or "").strip()
        footprint = str(data.get(self.footprint_column) or "").strip()
        if not symbol:
            raise DbError(f"row {data.get(self.key_column)!r} has no {self.symbol_column}")
        return DbRow(
            key=str(data.get(self.key_column) or ""),
            symbol=symbol,
            footprint=footprint,
            value=str(data.get("Value") or ""),
            mpn=str(data.get("ManufacturerProductNumber") or ""),
            lcsc=str(data.get("DistributorProductNumber") or ""),
            # every column verbatim, empty values included: a database-linked symbol
            # carries the whole row, which is how KiCad writes it
            columns={key: "" if value is None else str(value) for key, value in data.items()},
        )

    # -- netlist integration -------------------------------------------------
    def resolve_component(self, component: dict[str, Any]) -> DbRow:
        """Resolve one netlist component, or explain why it cannot be placed."""
        ref = str(component.get("ref", "?"))
        identifier = component.get("lcsc") or component.get("mpn") or component.get("db_id")
        if identifier is None:
            lib_id = component.get("lib_id")
            if lib_id:
                raise PartError(
                    ref,
                    f"lib_id {lib_id!r} given without mpn/lcsc — components must be "
                    f"identified by a database part (mpn or lcsc), not by a library id",
                )
            raise PartError(ref, f"no mpn, lcsc or db_id — cannot look the part up in {self.dbl_path.name}")

        row = self.lookup(str(identifier))
        if row is None:
            raise PartError(
                ref,
                f"{identifier!r} is not in the component database "
                f"({self.dbl_path.name} / {self.db_path.name}); add it with the kicad_db_llm skill",
            )
        return row

    def resolve_all(self, components: list[dict[str, Any]]) -> list[DbRow]:
        """Resolve every component, or fail listing all the ones that did not resolve."""
        rows: list[DbRow] = []
        problems: list[str] = []
        for component in components:
            try:
                rows.append(self.resolve_component(component))
            except PartError as error:
                problems.append(str(error))
        if problems:
            raise DbError("components not placeable from the database:\n  - " + "\n  - ".join(problems))
        return rows
