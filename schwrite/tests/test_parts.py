"""Part resolution: netlist + database + library â†’ `Part` (M1 acceptance)."""

from __future__ import annotations

import pytest

from conftest import DBL, LIBRARIES, NETLISTS, PAGES
from schwrite import dblib, netlist, parts, symbols
from schwrite.errors import DbError, PartError


@pytest.fixture(scope="module")
def db() -> dblib.ComponentDb:
    return dblib.ComponentDb(DBL)


@pytest.fixture(scope="module")
def library() -> symbols.SymbolLibrary:
    return symbols.SymbolLibrary(LIBRARIES)


def test_every_page_resolves_to_parts(db, library) -> None:
    """M1 acceptance: the whole MCB-01 netlist set resolves, page by page."""
    total = 0
    lcsc_numbers: set[str] = set()
    for page, expected in PAGES.items():
        loaded = netlist.load(NETLISTS / f"{page}.json")
        resolved = parts.resolve_parts(loaded, db, library)
        assert len(resolved) == expected, page
        total += len(resolved)
        lcsc_numbers |= {part.lcsc for part in resolved}
        for part in resolved:
            assert part.symbol_id and ":" in part.symbol_id
            assert part.pins, f"{page}/{part.ref} has no pins"
            assert part.value, f"{page}/{part.ref} has no value"
    assert total == 196           # Â§Appendix D
    assert len(lcsc_numbers) == 45
    assert db.count() == 45


def test_database_decides_symbol_footprint_and_value(db, library) -> None:
    """A netlist hint must not override the database (Â§2)."""
    loaded = netlist.parse(
        {
            "subsystem": "T",
            "components": [{"ref": "R1", "lcsc": "C25744", "value": "999k"}],
            "nets": [{"name": "N1", "members": [{"ref": "R1", "pin": "1"}]}],
        }
    )
    part = parts.resolve_parts(loaded, db, library)[0]
    row = db.lookup("C25744")
    assert part.value == row.value != "999k"
    assert part.footprint == row.footprint
    assert part.symbol_id == row.symbol


def test_symbols_for_is_keyed_by_the_database_link(db, library) -> None:
    """One `lib_symbols` entry per **link**, not per geometry file.

    Channel_1-4 has several resistor part numbers that share `Standard:R` geometry; KiCad
    embeds one entry per database key, so the count follows the links.
    """
    loaded = netlist.load(NETLISTS / "Channel_1-4.json")
    resolved = parts.resolve_parts(loaded, db, library)
    keyed = parts.symbols_for(resolved, library)
    assert set(keyed) == {part.link_id for part in resolved}
    assert len(keyed) > len({part.symbol_id for part in resolved})
    assert all(link.startswith("components:") for link in keyed)
    assert list(keyed) == list(dict.fromkeys(part.link_id for part in resolved))


def test_every_part_links_to_its_database_row(db, library) -> None:
    """The link is `<database nickname>:<row key>` â€” what KiCad writes for a DB placement."""
    loaded = netlist.load(NETLISTS / "Sync.json")
    resolved = parts.resolve_parts(loaded, db, library)
    for part in resolved:
        link = f"{db.nickname}:{db.nickname}/{db.lookup(part.lcsc).key}"
        assert part.link_id == link
        assert part.link_id.startswith("components:")


def test_fields_follow_the_database_schema_not_a_shortlist(db, library) -> None:
    """Every field the `.kicad_dbl` declares is carried, empty values included."""
    declared = [name for name, _ in db.field_specs if name not in ("Value", "Description")]
    loaded = netlist.parse(
        {
            "subsystem": "T",
            "components": [{"ref": "R1", "lcsc": "C2906860"}],
            "nets": [{"name": "N1", "members": [{"ref": "R1", "pin": "1"}]}],
        }
    )
    part = parts.resolve_parts(loaded, db, library)[0]
    assert list(part.fields) == declared
    assert part.fields["DistributorProductNumber"] == "C2906860"
    assert part.fields["ID"] == db.lookup("C2906860").key
    assert part.description  # from the Description column, carried as a standard field
    # an empty column is still present (KiCad writes it)
    assert part.fields["Keywords"] == ""


def test_unknown_part_is_named_and_blocks_the_page(db, library) -> None:
    loaded = netlist.parse(
        {
            "subsystem": "T",
            "components": [{"ref": "R1", "lcsc": "C000000"}],
            "nets": [{"name": "N1", "members": [{"ref": "R1", "pin": "1"}]}],
        }
    )
    with pytest.raises(PartError, match="C000000.*not in the component database"):
        parts.resolve_parts(loaded, db, library)


def test_one_bad_part_reports_every_problem_at_once(db, library) -> None:
    loaded = netlist.parse(
        {
            "subsystem": "T",
            "components": [
                {"ref": "R1", "lcsc": "C25744"},
                {"ref": "R2", "lcsc": "C000001"},
                {"ref": "R3", "lcsc": "C000002"},
            ],
            "nets": [
                {"name": "N1", "members": [{"ref": "R1", "pin": "1"}, {"ref": "R2", "pin": "1"}]},
                {"name": "N2", "members": [{"ref": "R3", "pin": "1"}]},
            ],
        }
    )
    with pytest.raises(PartError) as caught:
        parts.resolve_parts(loaded, db, library)
    message = str(caught.value)
    assert "C000001" in message and "C000002" in message


def test_a_pin_the_symbol_does_not_have_is_a_named_error(db, library) -> None:
    loaded = netlist.parse(
        {
            "subsystem": "T",
            "components": [{"ref": "R1", "lcsc": "C25744"}],
            "nets": [{"name": "N1", "members": [{"ref": "R1", "pin": "9"}]}],
        }
    )
    with pytest.raises(PartError, match="pin\\(s\\) 9"):
        parts.resolve_parts(loaded, db, library)


def test_database_library_must_exist(tmp_path) -> None:
    with pytest.raises(DbError, match="database library not found"):
        dblib.ComponentDb(tmp_path / "nope.kicad_dbl")


def test_database_resolves_from_a_copied_fixture_tree(db) -> None:
    """The fixtures keep the database beside the `.kicad_dbl`, not at `${CWD}\\..\\kicad_lib`."""
    assert db.db_path.name == "components.db"
    assert db.db_path.is_file()
    assert db.nickname == "components"
