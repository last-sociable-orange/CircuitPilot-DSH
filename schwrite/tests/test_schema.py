"""The schema's job: a part cannot be written with a field missing or misplaced."""

import pytest

from schwrite import dblib, netlist, parts, symbols
from schwrite.schema import (
    STANDARD_FIELDS,
    Property,
    PropertyTable,
    SchemaError,
)
from conftest import DBL, LIBRARIES, NETLISTS


@pytest.fixture()
def sync_parts():
    db = dblib.ComponentDb(DBL)
    library = symbols.SymbolLibrary(LIBRARIES)
    loaded = netlist.load(NETLISTS / "Sync.json")
    return parts.resolve_parts(loaded, db, library), library


def _table(part, library):
    lib = library.load(part.symbol_id)
    return PropertyTable.build(
        part=part,
        library_properties=symbols._library_properties(lib.block),
        standard_values={
            "Reference": part.ref,
            "Value": part.value,
            "Footprint": part.footprint,
            "Datasheet": "",
            "Description": part.description,
        },
    )


def test_a_complete_table_validates(sync_parts) -> None:
    resolved, library = sync_parts
    for part in resolved:
        table = _table(part, library)
        table.validate(part)                      # must not raise
        assert table.names()[: len(STANDARD_FIELDS)] == STANDARD_FIELDS
        assert len(table.names()) == len(set(table.names()))


def test_every_database_column_is_present(sync_parts) -> None:
    resolved, library = sync_parts
    part = resolved[0]
    names = set(_table(part, library).names())
    missing = set(part.fields) - names
    assert not missing, missing


def test_a_missing_field_is_refused(sync_parts) -> None:
    resolved, library = sync_parts
    part = resolved[0]
    table = _table(part, library)
    trimmed = PropertyTable(tuple(p for p in table.properties if p.name != "Footprint"))
    with pytest.raises(SchemaError, match="Footprint"):
        trimmed.validate(part)


def test_a_visible_hidden_field_is_refused(sync_parts) -> None:
    resolved, library = sync_parts
    part = resolved[0]
    table = _table(part, library)
    leaking = PropertyTable(
        tuple(
            Property(name=p.name, value=p.value, at=p.at, hide=False)
            if p.name == "Footprint"
            else p
            for p in table.properties
        )
    )
    with pytest.raises(SchemaError, match="visible"):
        leaking.validate(part)


def test_duplicate_fields_are_refused(sync_parts) -> None:
    resolved, library = sync_parts
    part = resolved[0]
    table = _table(part, library)
    doubled = PropertyTable(table.properties + (table.properties[1],))
    with pytest.raises(SchemaError, match="duplicated"):
        doubled.validate(part)


def test_placed_fields_must_be_on_the_grid(sync_parts) -> None:
    """Only what *we* place: the cache keeps the library's own off-grid positions."""
    resolved, library = sync_parts
    part = resolved[0]
    table = _table(part, library)
    off = PropertyTable(
        tuple(
            Property(name=p.name, value=p.value, at=(p.at[0], p.at[1] + 0.3), hide=p.hide)
            if p.name == "Value"
            else p
            for p in table.properties
        )
    )
    off.validate(part)                             # cache entry: allowed
    with pytest.raises(SchemaError, match="grid"):
        off.validate(part, require_grid=True)      # placed instance: not allowed


def test_ki_fp_filters_follows_the_footprint(sync_parts) -> None:
    resolved, library = sync_parts
    for part in resolved:
        table = _table(part, library)
        item = table.get("ki_fp_filters")
        if item is not None and part.footprint:
            assert item.value == part.footprint
