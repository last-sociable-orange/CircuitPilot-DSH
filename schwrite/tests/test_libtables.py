"""Library tables are discovered from the parts, then checked against the project."""

from pathlib import Path

import pytest

from schwrite import dblib, libtables, netlist, parts, symbols
from conftest import DBL, LIBRARIES, NETLISTS


@pytest.fixture()
def resolved():
    db = dblib.ComponentDb(DBL)
    library = symbols.SymbolLibrary(LIBRARIES)
    return parts.resolve_parts(netlist.load(NETLISTS / "Sync.json"), db, library), db


def test_needs_are_discovered_from_the_parts(resolved) -> None:
    parts_, db = resolved
    needs = libtables.needs(parts_, db, LIBRARIES, DBL)
    symbol_names = {n.name for n in needs if n.table == libtables.SYMBOL_TABLE}
    footprint_names = {n.name for n in needs if n.table == libtables.FOOTPRINT_TABLE}
    # every symbol nickname a part uses, plus the database library itself
    assert {"Symbol", "Standard"} & symbol_names
    assert "components" in symbol_names
    assert footprint_names                       # the rows name footprints too
    assert all(need.name for need in needs)


def test_missing_entries_are_added(resolved, tmp_path) -> None:
    parts_, db = resolved
    needs = libtables.needs(parts_, db, LIBRARIES, DBL)
    reports = libtables.check(tmp_path, needs, repair=True)
    table = (tmp_path / libtables.SYMBOL_TABLE).read_text(encoding="utf-8")
    assert "(sym_lib_table" in table
    assert 'name "components"' in table
    assert any("added" in line for report in reports for line in report.added)


def test_foreign_entries_are_preserved(resolved, tmp_path) -> None:
    parts_, db = resolved
    (tmp_path / libtables.SYMBOL_TABLE).write_text(
        "(sym_lib_table\n\t(version 7)\n"
        '\t(lib (name "HandMade") (type "KiCad") (uri "/elsewhere/HandMade.kicad_sym")'
        ' (options "") (descr "mine"))\n)\n',
        encoding="utf-8",
    )
    libtables.check(tmp_path, libtables.needs(parts_, db, LIBRARIES, DBL), repair=True)
    table = (tmp_path / libtables.SYMBOL_TABLE).read_text(encoding="utf-8")
    assert 'name "HandMade"' in table


def test_an_entry_that_does_not_resolve_is_reported_not_rewritten(resolved, tmp_path) -> None:
    parts_, db = resolved
    (tmp_path / libtables.SYMBOL_TABLE).write_text(
        "(sym_lib_table\n\t(version 7)\n"
        '\t(lib (name "Symbol") (type "KiCad") (uri "${KIPRJMOD}/nowhere/Symbol")'
        ' (options "") (descr "broken"))\n)\n',
        encoding="utf-8",
    )
    reports = libtables.check(tmp_path, libtables.needs(parts_, db, LIBRARIES, DBL), repair=True)
    symbol_report = next(r for r in reports if r.path and "sym-lib-table" in r.path)
    assert symbol_report.unresolved                     # reported
    table = (tmp_path / libtables.SYMBOL_TABLE).read_text(encoding="utf-8")
    assert "nowhere/Symbol" in table                    # left exactly as the project had it


def test_symbol_libraries_are_fatal_footprints_are_not(resolved, tmp_path) -> None:
    parts_, db = resolved
    reports = libtables.check(tmp_path, libtables.needs(parts_, db, LIBRARIES, DBL))
    for report in reports:
        if report.unresolved:
            assert report.fatal == any("sym-lib-table" in line for line in report.unresolved)
