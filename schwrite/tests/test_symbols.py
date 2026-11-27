"""Symbol reading and embedding (§8.1) — pin pairing is the thing under test."""

from __future__ import annotations

import pytest

from conftest import LIBRARIES, REFERENCE
from schwrite import sexp, symbols
from schwrite.errors import PartError


@pytest.fixture(scope="module")
def library() -> symbols.SymbolLibrary:
    return symbols.SymbolLibrary(LIBRARIES)


def test_pins_are_paired_with_their_own_block(library: symbols.SymbolLibrary) -> None:
    """IC_SN74LVC1G125DCKR: 5 pins whose numbers and positions must not drift apart.

    The 2026-11-25 builder zipped two independent regex scans, which silently pairs the
    wrong number with the wrong position as soon as a symbol nests a node the regex does
    not expect. The library is now written by LCSC3D (`tools/export_symbols.py`), so these
    are LCSC3D's coordinates: inputs on the left at -10.16, outputs on the right at +7.62.
    """
    symbol = library.load("Symbol:IC_SN74LVC1G125DCKR")
    assert len(symbol.pins) == 5
    assert {number: (p.x, p.y) for number, p in symbol.pins.items()} == {
        "1": (-10.16, 2.54),
        "2": (-10.16, 0.0),
        "3": (-10.16, -2.54),
        "4": (7.62, -2.54),
        "5": (7.62, 2.54),
    }
    assert symbol.pins["5"].name == "VCC"
    assert symbol.pins["1"].name == "OE#"
    assert symbol.pins["5"].angle == 180
    assert symbol.pins["5"].length == 2.54
    assert symbol.pins["1"].angle == 0


def test_outward_angle_is_180_from_the_stored_angle(library: symbols.SymbolLibrary) -> None:
    """VCC sits on the right, so its label leaves to the right: 180 + 180 = 0 (§8.2)."""
    symbol = library.load("Symbol:IC_SN74LVC1G125DCKR")
    assert symbol.pins["5"].outward_angle == 0
    assert symbol.pins["1"].outward_angle == 180     # left-side pin leaves left


def test_standard_library_resolves_parts_from_one_file(library: symbols.SymbolLibrary) -> None:
    """`Standard:R` and `Standard:C` share Standard.kicad_sym; each must get its own pins.

    Both happen to sit at the same coordinates (0, ±2.54) but with different pin lengths,
    so the check is length — coordinates alone would pass even if the wrong symbol's pins
    were returned.
    """
    resistor = library.load("Standard:R")
    capacitor = library.load("Standard:C")
    assert resistor.path.name == "Standard.kicad_sym"
    assert capacitor.path.name == "Standard.kicad_sym"
    assert len(resistor.pins) == 2
    assert len(capacitor.pins) == 2
    assert resistor.pins["1"].length != capacitor.pins["1"].length


def test_page_block_is_the_library_block_renamed_and_indented(
    library: symbols.SymbolLibrary,
) -> None:
    """Embedding must rename the symbol and shift indentation uniformly — nothing else.

    Library files in use come from two sources: LCSC3D's exporter (symbol at column 0) and
    KiCad's own `Standard.kicad_sym` (symbol at one tab). The shift is therefore relative to
    the source depth, which is what `LibSymbol.page_block` computes.
    """
    for lib_id in ("Symbol:IC_SN74LVC1G125DCKR", "Standard:R"):
        symbol = library.load(lib_id)
        page_block = symbol.page_block()
        source_lines = symbol.block.splitlines()
        page_lines = page_block.splitlines()
        assert len(page_lines) == len(source_lines)
        assert page_lines[0].startswith("\t\t(" + f'symbol "{lib_id}"')
        for index, (source, embedded) in enumerate(zip(source_lines, page_lines)):
            source_depth = len(source) - len(source.lstrip("\t"))
            if index == 0:
                source_depth = symbol.indent      # the block starts at its own paren
            embedded_depth = len(embedded) - len(embedded.lstrip("\t"))
            assert embedded_depth == source_depth - symbol.indent + 2, lib_id
            if index == 0:
                # the one intended difference: the nickname is prefixed to the name
                assert embedded.lstrip("\t").replace(f'"{lib_id}"', f'"{symbol.name}"', 1) == (
                    source.lstrip("\t")
                ), lib_id
            else:
                assert embedded.lstrip("\t") == source.lstrip("\t"), lib_id


def test_page_block_is_byte_faithful_to_the_library_file(library: symbols.SymbolLibrary) -> None:
    """The embedded block is the library block, renaming aside.

    With the library now written by LCSC3D, the corpus pages no longer compare directly:
    they were upgraded to KiCad 10 syntax by eeschema when they were saved. What must hold
    is that we embed the library *verbatim* — no re-serialisation, no dropped node.
    """
    symbol = library.load("Symbol:IC_SN74LVC1G125DCKR")
    from_library = sexp.normalise(sexp.parse(symbol.block))
    from_page = sexp.normalise(sexp.parse(symbol.page_block()))
    assert from_library[0] == from_page[0] == "symbol"
    assert from_page[1] == "Symbol:IC_SN74LVC1G125DCKR"
    assert from_library[2:] == from_page[2:]


def test_missing_library_file_is_a_named_error(library: symbols.SymbolLibrary) -> None:
    with pytest.raises(PartError, match="symbol library file not found"):
        library.load("Symbol:NO_SUCH_PART")


def test_missing_symbol_in_an_existing_file_is_a_named_error(
    library: symbols.SymbolLibrary,
) -> None:
    with pytest.raises(PartError, match="is not in"):
        library.load("Standard:NO_SUCH_STANDARD_PART")


def test_check_pins_names_the_missing_pin(library: symbols.SymbolLibrary) -> None:
    with pytest.raises(PartError, match="pin\\(s\\) 9"):
        library.check_pins("Standard:R", ["1", "9"])


def test_every_netlist_pin_exists_on_its_symbol() -> None:
    """The whole corpus, resolved: no netlist may name a pin its symbol does not have."""
    from conftest import DBL, NETLISTS
    from schwrite import dblib, netlist, parts

    db = dblib.ComponentDb(DBL)
    library = symbols.SymbolLibrary(LIBRARIES)
    for path in sorted(NETLISTS.glob("*.json")):
        loaded = netlist.load(path)
        resolved = parts.resolve_parts(loaded, db, library)   # raises on any missing pin
        assert len(resolved) == len(loaded.components)


def test_page_has_one_lib_symbols_entry_per_link(tmp_path) -> None:
    """Ten resistors of one part number share a single entry, not ten.

    Duplicate `lib_symbols` children were what made KiCad report one mismatch per part.
    """
    import re
    from pathlib import Path

    from schwrite import dblib, netlist, page, parts, symbols
    from schwrite.emit import writer
    from schwrite.parts import symbols_for
    from schwrite.context import InstanceContext

    fixtures = Path(__file__).parent / "fixtures"
    db = dblib.ComponentDb(fixtures / "libraries" / "components_db_windows.kicad_dbl")
    library = symbols.SymbolLibrary(fixtures / "libraries")
    loaded = netlist.load(fixtures / "netlists" / "Sync.json")
    resolved = parts.resolve_parts(loaded, db, library)
    model = page.build_page_model(
        netlist=loaded, resolved=resolved, page="Sync", paper="A4",
        context=InstanceContext(project="P", path="/r/s"),
    )
    text = writer.render_page(model, symbols_for(resolved, library))
    names = re.findall(r'\n\t\t\(symbol "([^"]+)"', text)
    assert len(names) == len(set(names)), names
    assert len(names) == len({part.link_id for part in resolved})
