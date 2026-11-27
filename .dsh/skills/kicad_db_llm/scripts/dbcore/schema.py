"""The KiCad ``components`` table: 80 columns, one row per part.

The schema is the one ``KicadLibGui-LCSC`` (and upstream ``kicad_lib_gen``)
writes, byte for byte: 16 metadata columns followed by 32 ``Param``/``Value``
pairs. KiCad's database-library reader is told about these names by a
``.kicad_dbl`` file, so **renaming or reordering a column breaks every existing
design that uses the database.** This module therefore never alters an existing
table; it only creates the table when it is absent and refuses to work with a
table that does not match.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PARAM_COUNT = 32

METADATA_COLUMNS: tuple[str, ...] = (
    "ID",
    "Description",
    "Keywords",
    "Value",
    "Manufacturer",
    "ManufacturerProductNumber",
    "Package",
    "KicadSymbolLibrary",
    "KicadFootprintLibrary",
    "PartStatus",
    "QtyAvailable",
    "Distributor",
    "DistributorProductNumber",
    "UnitPrice",
    "ProductUrl",
    "DatasheetUrl",
)

PARAM_COLUMNS: tuple[str, ...] = tuple(
    name
    for index in range(1, PARAM_COUNT + 1)
    for name in (f"Param{index:02d}", f"Value{index:02d}")
)

ALL_COLUMNS: tuple[str, ...] = METADATA_COLUMNS + PARAM_COLUMNS

UNUSED = "-"

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS "components" (
    "ID" TEXT NOT NULL,
    "Description" TEXT NOT NULL,
    "Keywords" TEXT NOT NULL,
    "Value" TEXT NOT NULL,
    "Manufacturer" TEXT NOT NULL,
    "ManufacturerProductNumber" TEXT NOT NULL,
    "Package" TEXT NOT NULL,
    "KicadSymbolLibrary" TEXT NOT NULL,
    "KicadFootprintLibrary" TEXT NOT NULL,
    "PartStatus" TEXT NOT NULL,
    "QtyAvailable" TEXT,
    "Distributor" TEXT,
    "DistributorProductNumber" TEXT,
    "UnitPrice" TEXT,
    "ProductUrl" TEXT,
    "DatasheetUrl" TEXT,
""" + ",\n".join(
    f'    "Param{index:02d}" TEXT,\n    "Value{index:02d}" TEXT'
    for index in range(1, PARAM_COUNT + 1)
) + """
)
"""

TABLE_NAME = "components"


class DatabaseProblem(RuntimeError):
    """A database this skill refuses to write."""


def connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), timeout=10, isolation_level=None)
    connection.row_factory = sqlite3.Row
    return connection


def table_names(connection: sqlite3.Connection) -> list[str]:
    rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    return [str(row[0]) for row in rows]


def columns(connection: sqlite3.Connection, table: str = TABLE_NAME) -> list[str]:
    rows = connection.execute(f'PRAGMA table_info("{table}")')
    return [str(row[1]) for row in rows]


def missing_columns(connection: sqlite3.Connection, table: str = TABLE_NAME) -> list[str]:
    present = set(columns(connection, table))
    return [name for name in ALL_COLUMNS if name not in present]


def open_database(path: str | Path, *, create: bool = True) -> sqlite3.Connection:
    """Open *path*, creating the components table only when the file is new.

    An existing table that does not match the 80-column schema is an error:
    writing into it would produce rows KiCad cannot read.
    """
    connection = connect(path)
    present = table_names(connection)
    if TABLE_NAME not in present:
        if not create:
            connection.close()
            raise DatabaseProblem(
                f"{path} has no '{TABLE_NAME}' table. Run without --no-create to create it."
            )
        connection.execute(_CREATE_TABLE_SQL)
        return connection
    missing = missing_columns(connection)
    if missing:
        connection.close()
        shown = ", ".join(missing[:8]) + (" …" if len(missing) > 8 else "")
        raise DatabaseProblem(
            f"{path} has a '{TABLE_NAME}' table that does not match the 80-column schema "
            f"({len(missing)} column(s) missing: {shown}). This skill will not write into it."
        )
    return connection


# -- records ---------------------------------------------------------------


@dataclass
class Record:
    """One row's worth of data, in column order."""

    values: dict[str, str] = field(default_factory=dict)

    # convenience accessors, used by reports and by the mapping layer

    @property
    def mpn(self) -> str:
        return self.values.get("ManufacturerProductNumber", "")

    @property
    def lcsc(self) -> str:
        return self.values.get("DistributorProductNumber", "")

    def set(self, column: str, value: Any) -> None:
        if column not in ALL_COLUMNS:
            raise KeyError(f"unknown column {column!r}")
        self.values[column] = _text(value)

    def set_parameters(self, pairs: Iterable[tuple[str, str]]) -> None:
        """Fill ``Param01..32``/``Value01..32`` from ordered (name, value) pairs."""
        slots = [(_text(name) or UNUSED, _text(value) or UNUSED) for name, value in pairs]
        slots = slots[:PARAM_COUNT]
        while len(slots) < PARAM_COUNT:
            slots.append((UNUSED, UNUSED))
        for index, (name, value) in enumerate(slots, start=1):
            self.values[f"Param{index:02d}"] = name
            self.values[f"Value{index:02d}"] = value

    def to_values(self) -> list[str]:
        return [self.values.get(name, "") for name in ALL_COLUMNS]

    def row_dict(self) -> dict[str, str]:
        return {name: self.values.get(name, "") for name in ALL_COLUMNS}

    def parameters(self) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for index in range(1, PARAM_COUNT + 1):
            name = self.values.get(f"Param{index:02d}", UNUSED)
            value = self.values.get(f"Value{index:02d}", UNUSED)
            if name != UNUSED or value != UNUSED:
                out.append((name, value))
        return out


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def record_from_row(row: Mapping[str, Any] | sqlite3.Row) -> Record:
    keys = row.keys() if hasattr(row, "keys") else []
    return Record({name: _text(row[name]) for name in keys if name in ALL_COLUMNS})  # type: ignore[index]


# -- reads -----------------------------------------------------------------


def find_by_mpn(connection: sqlite3.Connection, mpn: str) -> Record | None:
    if not mpn.strip():
        return None
    row = connection.execute(
        f'SELECT * FROM "{TABLE_NAME}" WHERE ManufacturerProductNumber = ? ORDER BY rowid LIMIT 1',
        (mpn,),
    ).fetchone()
    return record_from_row(row) if row is not None else None


def count_rows(connection: sqlite3.Connection) -> int:
    row = connection.execute(f'SELECT COUNT(*) FROM "{TABLE_NAME}"').fetchone()
    return int(row[0]) if row else 0


def all_rows(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(connection.execute(f'SELECT rowid, * FROM "{TABLE_NAME}" ORDER BY rowid'))


def duplicate_mpns(connection: sqlite3.Connection) -> list[tuple[str, int]]:
    rows = connection.execute(
        f"""
        SELECT ManufacturerProductNumber AS mpn, COUNT(*) AS n
        FROM "{TABLE_NAME}"
        GROUP BY ManufacturerProductNumber
        HAVING COUNT(*) > 1
        ORDER BY n DESC, mpn
        """
    )
    return [(str(row[0]), int(row[1])) for row in rows]


# -- writes ----------------------------------------------------------------


def insert_record(connection: sqlite3.Connection, record: Record) -> None:
    placeholders = ", ".join("?" for _ in ALL_COLUMNS)
    names = ", ".join(f'"{name}"' for name in ALL_COLUMNS)
    connection.execute(
        f'INSERT INTO "{TABLE_NAME}" ({names}) VALUES ({placeholders})',
        record.to_values(),
    )


def update_record(connection: sqlite3.Connection, record: Record) -> int:
    """Update every column except the MPN, which identifies the row."""
    assign_columns = [name for name in ALL_COLUMNS if name != "ManufacturerProductNumber"]
    assignments = ", ".join(f'"{name}" = ?' for name in assign_columns)
    cursor = connection.execute(
        f'UPDATE "{TABLE_NAME}" SET {assignments} WHERE ManufacturerProductNumber = ?',
        [record.values.get(name, "") for name in assign_columns] + [record.mpn],
    )
    return cursor.rowcount


class transaction:
    """``with transaction(connection):`` — explicit begin/commit/rollback."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def __enter__(self) -> sqlite3.Connection:
        self.connection.execute("BEGIN IMMEDIATE")
        return self.connection

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is None:
            self.connection.execute("COMMIT")
        else:
            self.connection.execute("ROLLBACK")
