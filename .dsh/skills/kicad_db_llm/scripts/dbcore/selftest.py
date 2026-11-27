"""Offline self-test: no network, no storefront, no user data touched.

Everything the skill claims is mechanical, so it can be asserted:

* the S-expression reader finds symbols, pins, pads and model paths;
* the database layer writes exactly 80 columns and refuses a foreign schema;
* classification maps a description/package to the expected class;
* a standard symbol is only chosen when its pins and pin *roles* match;
* staging renames the symbol, the footprint and the model reference;
* verification notices a reference that does not resolve.

The fixture library is synthetic and lives in a temporary directory — it is test
data, never a source of geometry claims about a real part.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from . import classify as classify_mod
from . import schema, sexpr
from .config import Config
from .libraries import LibraryProblem, LibrarySet, assert_writable
from .mapping import decide
from .parts import BomLine, Part
from .stage import BundlePart, stage

# -- fixture text ----------------------------------------------------------

STANDARD_SYMBOLS = """(kicad_symbol_lib
	(version 20251024)
	(generator "selftest")
	(generator_version "10.0")
{body}
)
"""

SYMBOL_TEMPLATE = """	(symbol "{name}"
		(property "Reference" "{ref}" (at 0 0 0) (effects (font (size 1.27 1.27))))
		(property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27))))
{units}
	)
"""

PIN_TEMPLATE = """			(pin passive line (at -1.27 0 0) (length 1.27)
				(name "{pin_name}" (effects (font (size 1.27 1.27))))
				(number "{number}" (effects (font (size 1.27 1.27))))
			)
"""

FOOTPRINT_TEMPLATE = """(footprint "{name}"
	(version 20260206)
	(generator "selftest")
	(generator_version "10.0")
	(layer "F.Cu")
	(property "Reference" "REF**" (at 0 0 0) (layer "F.SilkS"))
{model}{pads}
)
"""

PAD_TEMPLATE = (
    '\t(pad "{number}" smd roundrect (at {x} 0) (size 0.9 0.95) '
    '(layers "F.Cu" "F.Paste" "F.Mask"))\n'
)


def _symbol(name: str, ref: str, pins: list[tuple[str, str]]) -> str:
    units = "\t\t(symbol \"" + name + "_0_1\"\n"
    for number, pin_name in pins:
        units += PIN_TEMPLATE.format(number=number, pin_name=pin_name)
    units += "\t\t)\n"
    return SYMBOL_TEMPLATE.format(name=name, ref=ref, units=units)


def _library(*symbols: str) -> str:
    return STANDARD_SYMBOLS.format(body="".join(symbols))


def _footprint(name: str, pads: list[str], model: str = "") -> str:
    model_block = ""
    if model:
        model_block = (
            f'\t(model "{model}"\n\t\t(offset (xyz 0 0 0))\n\t\t(scale (xyz 1 1 1))\n'
            "\t\t(rotate (xyz 0 0 0))\n\t)\n"
        )
    body = ""
    for index, number in enumerate(pads):
        body += PAD_TEMPLATE.format(number=number, x=-0.8 + index * 1.6)
    return FOOTPRINT_TEMPLATE.format(name=name, model=model_block, pads=body)


def build_tree(root: Path) -> Path:
    """Create a miniature library tree and return the kicad_lib root."""
    libs = root / "kicad_lib"
    (libs / "Symbol" / "Standard").mkdir(parents=True)
    (libs / "Symbol" / "Symbol").mkdir(parents=True)
    (libs / "Footprint" / "Standard.pretty").mkdir(parents=True)
    (libs / "Footprint" / "Footprint.pretty").mkdir(parents=True)
    (libs / "Step").mkdir(parents=True)

    (libs / "Symbol" / "Standard" / "Standard.kicad_sym").write_text(
        _library(
            _symbol("R", "R", [("1", "~"), ("2", "~")]),
            _symbol("C", "C", [("1", "~"), ("2", "~")]),
            _symbol("L", "L", [("1", "~"), ("2", "~")]),
            _symbol("FB", "FB", [("1", "~"), ("2", "~")]),
            _symbol("D_TVS_BIDIR", "D", [("1", "~"), ("2", "~")]),
            _symbol("D_SCHOTTKY_A1C2", "D", [("1", "A"), ("2", "K")]),
            _symbol("D_SCHOTTKY_A2C1", "D", [("1", "K"), ("2", "A")]),
            _symbol("Q_NMOS_SOT23", "Q", [("1", "G"), ("2", "S"), ("3", "D")]),
        ),
        encoding="utf-8",
    )
    (libs / "Footprint" / "Standard.pretty" / "R_0603.kicad_mod").write_text(
        _footprint("R_0603", ["1", "2"]), encoding="utf-8"
    )
    (libs / "Footprint" / "Standard.pretty" / "C_0603.kicad_mod").write_text(
        _footprint("C_0603", ["1", "2"]), encoding="utf-8"
    )
    (libs / "Footprint" / "Standard.pretty" / "SOT23.kicad_mod").write_text(
        _footprint("SOT23", ["1", "2", "3"]), encoding="utf-8"
    )

    # a downloaded symbol with named pins (A/K), one with numbered pins
    (libs / "Symbol" / "Symbol" / "D_TEST002.kicad_sym").write_text(
        _library(_symbol("D_TEST002", "D", [("1", "A"), ("2", "K")])), encoding="utf-8"
    )
    (libs / "Footprint" / "Footprint.pretty" / "D_TEST002.kicad_mod").write_text(
        _footprint("D_TEST002", ["1", "2"], "${KIPRJMOD}/../kicad_lib/Step/D_TEST002.stp"),
        encoding="utf-8",
    )
    (libs / "Step" / "D_TEST002.stp").write_text("ISO-10303-21;\n", encoding="utf-8")

    (libs / "Symbol" / "Symbol" / "D_TEST003.kicad_sym").write_text(
        _library(_symbol("D_TEST003", "D", [("1", "~"), ("2", "~")])), encoding="utf-8"
    )
    (libs / "Footprint" / "Footprint.pretty" / "D_TEST003.kicad_mod").write_text(
        _footprint("D_TEST003", ["1", "2"]), encoding="utf-8"
    )

    (libs / "Symbol" / "Symbol" / "IC_TEST001.kicad_sym").write_text(
        _library(_symbol("IC_TEST001", "U", [("1", "IN"), ("2", "GND"), ("3", "OUT")])),
        encoding="utf-8",
    )
    (libs / "Footprint" / "Footprint.pretty" / "IC_TEST001.kicad_mod").write_text(
        _footprint("IC_TEST001", ["1", "2", "3"], "${KIPRJMOD}/../kicad_lib/Step/IC_TEST001.stp"),
        encoding="utf-8",
    )
    (libs / "Step" / "IC_TEST001.stp").write_text("ISO-10303-21;\n", encoding="utf-8")
    return libs


def make_config(libs: Path, root: Path) -> Config:
    return Config(
        data={
            "libs_root": str(libs),
            "database": str(root / "components.db"),
            "symbols": {
                "standard": {"nickname": "Standard", "file": "Symbol/Standard/Standard.kicad_sym"},
                "parts": {"nickname": "Symbol", "folder": "Symbol/Symbol", "suffix": ".kicad_sym"},
            },
            "footprints": {
                "standard": {"nickname": "Standard", "folder": "Footprint/Standard.pretty"},
                "parts": {
                    "nickname": "Footprint",
                    "folder": "Footprint/Footprint.pretty",
                    "suffix": ".kicad_mod",
                },
            },
            "models": {
                "folder": "Step",
                "suffixes": [".stp", ".step"],
                "reference": "${KIPRJMOD}/../kicad_lib/Step/{name}.stp",
            },
        }
    )


def part(**overrides) -> Part:
    base = {
        "lcsc": "C900001",
        "mpn": "TESTMPN",
        "manufacturer": "Test Mfr",
        "description": "",
        "package": "",
        "category": "",
        "status": "Active",
        "stock": 100,
        "value": "",
        "price_tiers": [{"qty": 1, "price": 0.1}],
        "datasheet": "https://example.invalid/ds.pdf",
        "product_url": "https://example.invalid/p",
        "distributor": "LCSC",
        "parameters": [],
    }
    base.update(overrides)
    return Part(**base)


# -- checks ----------------------------------------------------------------


def check_sexpr() -> None:
    text = _library(_symbol("R", "R", [("1", "~"), ("2", "~")]))
    roots = sexpr.parse(text)
    library = roots[0]
    assert sexpr.head(library) == "kicad_symbol_lib"
    symbol = sexpr.find(library, "symbol")
    assert sexpr.atom(symbol, 1) == "R"
    pins = list(sexpr.walk(symbol, "pin"))
    assert len(pins) == 2, pins

    renamed, changed = sexpr.rename_symbol(text, "R", "IC_RENAMED")
    assert changed == 2, changed
    renamed_roots = sexpr.parse(renamed)  # the rewritten file must still parse
    renamed_symbol = sexpr.find(renamed_roots[0], "symbol")
    assert sexpr.atom(renamed_symbol, 1) == "IC_RENAMED"
    units = [sexpr.atom(node, 1) for node in sexpr.children(renamed_symbol, "symbol")]
    assert units == ["IC_RENAMED_0_1"], units
    assert len(list(sexpr.walk(renamed_symbol, "pin"))) == 2

    pointed, count = sexpr.set_footprint_field(renamed, "Footprint:IC_RENAMED")
    assert count == 1
    assert '"Footprint:IC_RENAMED"' in pointed

    try:
        sexpr.parse("(a (b)")
    except sexpr.SexprError:
        pass
    else:  # pragma: no cover
        raise AssertionError("an unbalanced file must not parse")


def check_schema(root: Path) -> None:
    db = root / "schema.db"
    connection = schema.open_database(db)
    record = schema.Record()
    record.set("ManufacturerProductNumber", "X1")
    record.set("ID", "Cat/X1")
    record.set("Description", "d")
    record.set("Keywords", "")
    record.set("Value", "v")
    record.set("Manufacturer", "m")
    record.set("Package", "0603")
    record.set("KicadSymbolLibrary", "Standard:R")
    record.set("KicadFootprintLibrary", "Standard:R_0603")
    record.set("PartStatus", "Active")
    record.set_parameters([("Resistance", "10k")])
    schema.insert_record(connection, record)
    assert len(record.to_values()) == 80
    rows = schema.all_rows(connection)
    assert len(rows) == 1
    assert rows[0]["Param01"] == "Resistance"
    assert rows[0]["Value01"] == "10k"
    assert rows[0]["Param32"] == schema.UNUSED
    found = schema.find_by_mpn(connection, "X1")
    assert found is not None and found.values["KicadSymbolLibrary"] == "Standard:R"
    connection.close()

    # a database whose table is not the 80-column one must be refused
    foreign = root / "foreign.db"
    other = schema.connect(foreign)
    other.execute('CREATE TABLE "components" ("ID" TEXT)')
    other.close()
    try:
        schema.open_database(foreign, create=False)
    except schema.DatabaseProblem:
        pass
    else:  # pragma: no cover
        raise AssertionError("a foreign schema must not be opened for writing")


def check_libraries(config: Config) -> None:
    libs = LibrarySet(config)
    standard = libs.standard_symbols()
    assert "R" in standard and "D_SCHOTTKY_A1C2" in standard
    assert standard["D_SCHOTTKY_A1C2"].roles() == {"1": "A", "2": "K"}
    assert standard["R"].roles() == {}
    footprints = libs.standard_footprints()
    assert sorted(footprints["R_0603"].pad_numbers()) == ["1", "2"]

    info, problem = libs.resolve_symbol("Symbol:D_TEST002")
    assert info is not None, problem
    assert info.roles() == {"1": "A", "2": "K"}

    info, problem = libs.resolve_footprint("Footprint:IC_TEST001")
    assert info is not None, problem
    assert info.model.endswith("IC_TEST001.stp")

    info, problem = libs.resolve_symbol("Standard:NOT_THERE")
    assert info is None and "NOT_THERE" in problem

    info, problem = libs.resolve_footprint("Wrong:Anything")
    assert info is None and "unknown footprint nickname" in problem

    try:
        assert_writable(config, config.standard_symbol.path)
    except LibraryProblem:
        pass
    else:  # pragma: no cover
        raise AssertionError("the standard symbol file must be read-only")
    try:
        assert_writable(config, config.standard_footprints.path / "R_0603.kicad_mod")
    except LibraryProblem:
        pass
    else:  # pragma: no cover
        raise AssertionError("standard footprints must be read-only")
    assert_writable(config, config.part_symbols.path / "X.kicad_sym")


def check_classification() -> None:
    cases = [
        ({'category': "Resistors", 'description': "RES 10K OHM 1% 1/16W 0402", 'package': "0402"},
         "RESISTOR"),
        ({'category': "Capacitors", 'description': "CAP CER 100nF 50V X7R 0603", 'package': "0603"},
         "CAPACITOR"),
        ({'category': "Capacitors",
              'description': "CAP ALUM 100uF 25V 20% SMD", 'package': "SMD"}, "CAPACITOR_POL"),
        ({'category': "Inductors", 'description': "FIXED IND 10uH 1A SMD", 'package': "6030"},
         "INDUCTOR"),
        ({'category': "Inductors", 'description': "FERRITE BEAD 600 OHM 0603", 'package': "0603"},
         "FERRITE_BEAD"),
        ({'category': "Diodes", 'description': "DIODE SCHOTTKY 40V 1A SOD-323", 'package': "SOD-323"},
         "DIODE_SCHOTTKY"),
        ({'category': "Circuit Protection", 'description': "TVS DIODE 5VWM 14VC SOD523",
              'package': "SOD-523"}, "DIODE_TVS"),
        ({'category': "Circuit Protection",
              'description': "TVS DIODE 24VWM 38.9VC SOD323", 'package': "SOD-323",
              'parameters': [{"name": "Bidirectional Channels", "value": "1"}]},
         "DIODE_TVS_BIDIR"),
        ({'category': "Transistors", 'description': "MOSFET N-CH 30V 5.8A SOT-23",
              'package': "SOT-23"}, "TRANSISTOR_NMOS"),
        ({'category': "Integrated Circuits", 'description': "IC REG LINEAR 3.3V 500mA SOT-23-5",
              'package': "SOT-23-5"}, "IC"),
        ({'category': "Connectors", 'description': "CONN HEADER VERT 4POS 2.54MM",
              'package': "Through Hole"}, "CONNECTOR"),
        ({'category': "Crystals", 'description': "CRYSTAL 16MHZ 8PF SMD", 'package': "3225"},
         "CRYSTAL"),
        ({'category': "Fuses", 'description': "FUSE BOARD MOUNT 2A 32VDC 0603", 'package': "0603"},
         "FUSE"),
    ]
    for overrides, expected in cases:
        got = classify_mod.classify(part(**overrides)).code
        assert got == expected, f"{overrides.get('description')}: expected {expected}, got {got}"


def check_mapping(config: Config) -> None:
    libs = LibrarySet(config)
    line = BomLine(lcsc="C900001", mpn="TESTMPN")

    resistor = decide(
        part(category="Resistors", description="RES 10K OHM 1% 0603", package="0603"),
        line, libs,
    )
    assert resistor.symbol == "Standard:R", resistor.symbol
    assert resistor.footprint == "Standard:R_0603", resistor.footprint
    assert resistor.ok, resistor.blockers

    capacitor = decide(
        part(mpn="CAP1", lcsc="C900002", category="Capacitors",
             description="CAP CER 1uF 0603", package="0603"),
        line, libs,
    )
    assert capacitor.symbol == "Standard:C"
    assert capacitor.footprint == "Standard:C_0603"

    # a diode whose downloaded symbol names its pins A/K proves D_SCHOTTKY_A1C2
    diode_known = decide(
        part(mpn="D_TEST002", lcsc="C900003", category="Diodes",
             description="DIODE SCHOTTKY 40V SOD-323", package="SOD-323"),
        BomLine(lcsc="C900003", mpn="D_TEST002"), libs, mode="all",
    )
    assert diode_known.symbol == "Standard:D_SCHOTTKY_A1C2", diode_known.evidence
    assert diode_known.footprint == "Footprint:D_TEST002"
    assert diode_known.ok, diode_known.blockers

    # the same class with a symbol that names its pins by number only must not
    # be assumed to match a polarised standard symbol
    diode_unknown = decide(
        part(mpn="D_TEST003", lcsc="C900004", category="Diodes",
             description="DIODE SCHOTTKY 40V SOD-323", package="SOD-323"),
        BomLine(lcsc="C900004", mpn="D_TEST003"), libs, mode="all",
    )
    assert diode_unknown.symbol == "Symbol:D_TEST003", diode_unknown.evidence
    assert diode_unknown.ok, diode_unknown.blockers

    # actives never take a standard symbol in the default mode
    ic = decide(
        part(mpn="IC_TEST001", lcsc="C900005", category="Integrated Circuits",
             description="IC REG LINEAR 3.3V SOT-23-5", package="SOT-23-5"),
        BomLine(lcsc="C900005", mpn="IC_TEST001"), libs, mode="auto",
    )
    assert ic.symbol == "Symbol:IC_TEST001", ic.symbol
    assert ic.footprint == "Footprint:IC_TEST001"

    # an inductor has a standard symbol but no standard footprint, so without a
    # downloaded footprint the row is blocked with an actionable message
    inductor = decide(
        part(mpn="IND1", lcsc="C900006", category="Inductors",
             description="FIXED IND 10uH", package="6030"),
        BomLine(lcsc="C900006", mpn="IND1"), libs,
    )
    assert not inductor.ok
    assert any("no footprint" in blocker for blocker in inductor.blockers), inductor.blockers

    # an explicit override that does not resolve is a blocker, not a silent swap
    broken = decide(
        part(mpn="R9", lcsc="C900007", category="Resistors", description="RES 1K 0603",
             package="0603"),
        BomLine(lcsc="C900007", mpn="R9", symbol="Standard:NOT_THERE"), libs,
    )
    assert not broken.ok and any("does not resolve" in item for item in broken.blockers)

    # mode off always uses the downloaded files
    off = decide(
        part(mpn="D_TEST002", lcsc="C900003", category="Diodes",
             description="DIODE SCHOTTKY 40V SOD-323", package="SOD-323"),
        BomLine(lcsc="C900003", mpn="D_TEST002"), libs, mode="off",
    )
    assert off.symbol == "Symbol:D_TEST002", off.symbol


def check_stage(config: Config, root: Path) -> None:
    bundle_dir = root / "bundle"
    (bundle_dir / "symbols").mkdir(parents=True)
    (bundle_dir / "footprints" / "C900010_TESTIC.pretty").mkdir(parents=True)
    (bundle_dir / "Step").mkdir(parents=True)

    symbol_file = bundle_dir / "symbols" / "C900010_TESTIC.kicad_sym"
    symbol_file.write_text(_library(_symbol("TESTIC", "U", [("1", "IN"), ("2", "OUT")])),
                           encoding="utf-8")
    footprint_file = bundle_dir / "footprints" / "C900010_TESTIC.pretty" / "C900010_TESTIC.kicad_mod"
    footprint_file.write_text(
        _footprint("C900010_TESTIC", ["1", "2"],
                   "${KIPRJMOD}/../kicad_lib/Step/C900010_TESTIC.step"), encoding="utf-8"
    )
    model_file = bundle_dir / "Step" / "C900010_TESTIC.step"
    model_file.write_text("ISO-10303-21;\n", encoding="utf-8")

    bundle = BundlePart(
        lcsc="C900010", symbol=symbol_file, footprint=footprint_file, model=model_file
    )
    result = stage(config, "IC_TESTIC", bundle, apply=True)
    assert result.ok, result.problems
    assert (config.part_symbols.path / "IC_TESTIC.kicad_sym").is_file()
    assert (config.part_footprints.path / "IC_TESTIC.kicad_mod").is_file()
    assert (config.step_folder / "IC_TESTIC.stp").is_file()

    text = (config.part_symbols.path / "IC_TESTIC.kicad_sym").read_text(encoding="utf-8")
    staged_roots = sexpr.parse(text)  # a rewritten symbol file must still parse
    staged_symbol = sexpr.find(staged_roots[0], "symbol")
    assert sexpr.atom(staged_symbol, 1) == "IC_TESTIC"
    units = [sexpr.atom(node, 1) for node in sexpr.children(staged_symbol, "symbol")]
    assert units == ["IC_TESTIC_0_1"], units
    assert len(list(sexpr.walk(staged_symbol, "pin"))) == 2
    assert '"Footprint:IC_TESTIC"' in text
    assert '"TESTIC"' not in text

    footprint_text = (config.part_footprints.path / "IC_TESTIC.kicad_mod").read_text(
        encoding="utf-8"
    )
    assert '(footprint "IC_TESTIC"' in footprint_text
    assert "kicad_lib/Step/IC_TESTIC.stp" in footprint_text

    # staging again must not overwrite the reviewed file
    again = stage(config, "IC_TESTIC", bundle, apply=True)
    assert all(item.action == "skip-exists" for item in again.files if item.kind != "missing")
    assert (config.part_symbols.path / "IC_TESTIC.kicad_sym").is_file()

    # and the staged files must now satisfy the mapping gate
    libs = LibrarySet(make_config(config.libs_root, root))
    decided = decide(
        part(mpn="TESTIC", lcsc="C900010", category="Integrated Circuits",
             description="IC REG LINEAR 1.8V", package="SOT-23-5"),
        BomLine(lcsc="C900010", mpn="TESTIC"), libs, mode="auto",
    )
    assert decided.symbol == "Symbol:IC_TESTIC", decided.symbol
    assert decided.ok, decided.blockers


def check_verify(config: Config, root: Path) -> None:
    from . import runner

    connection = schema.open_database(config.database)
    good = schema.Record()
    good.set("ManufacturerProductNumber", "GOOD")
    good.set("KicadSymbolLibrary", "Standard:R")
    good.set("KicadFootprintLibrary", "Standard:R_0603")
    schema.insert_record(connection, good)
    bad = schema.Record()
    bad.set("ManufacturerProductNumber", "BAD")
    bad.set("KicadSymbolLibrary", "Symbol:NOPE")
    bad.set("KicadFootprintLibrary", "Footprint:NOPE")
    schema.insert_record(connection, bad)
    connection.close()

    result = runner.verify(config, LibrarySet(config))
    assert result.rows == 2, result.rows
    assert [item.mpn for item in result.problems] == ["BAD"], result.problems
    assert result.ok == 1


def check_commit(config: Config, root: Path) -> None:
    """A second run must skip, never duplicate — the bug this check exists for."""
    import json

    from . import runner
    from .lcsc import Lookup

    payload = [
        {
            "lcsc": "C2906982",
            "mpn": "FRC0603F1002TS",
            "manufacturer": "FOJAN",
            "description": "RES 10K OHM 1% 0603",
            "package": "0603",
            "category": "Resistors",
            "status": "Active",
            "stock": 1000,
            "value": "10k",
            "currency": "US$",
            "price_tiers": [{"qty": 100, "price": 0.001}, {"qty": 1, "price": 0.01}],
            "datasheet": "https://example.invalid/ds.pdf",
            "product_url": "https://example.invalid/p",
            "distributor": "LCSC",
            "parameters": [{"name": "Resistance", "value": "10k"}],
        }
    ]
    path = root / "parts.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    lookup = Lookup(config)
    assert lookup.load_json(path) == 1

    libs = LibrarySet(config)
    lines = [BomLine(lcsc="C2906982", value="10k", row=1)]

    first = runner.plan(lines, libs, lookup, find_existing=runner.existing_lookup(config))
    assert first[0].action == "insert", first[0].action
    first_summary = runner.commit(config, first, on_exist="skip")
    assert first_summary.inserted == 1, vars(first_summary)
    assert first[0].record is not None
    assert first[0].record.values["KicadSymbolLibrary"] == "Standard:R"
    assert first[0].record.values["KicadFootprintLibrary"] == "Standard:R_0603"
    assert first[0].record.values["UnitPrice"] == "0.001@100/0.01@1", first[0].record.values[
        "UnitPrice"
    ]

    second = runner.plan(lines, libs, lookup, find_existing=runner.existing_lookup(config))
    assert second[0].action == "skip", second[0].action
    second_summary = runner.commit(config, second, on_exist="skip")
    assert second_summary.inserted == 0 and second_summary.skipped == 1, vars(second_summary)

    connection = schema.open_database(config.database, create=False)
    stored = connection.execute(
        f'SELECT COUNT(*) FROM "{schema.TABLE_NAME}" WHERE ManufacturerProductNumber = ?',
        ("FRC0603F1002TS",),
    ).fetchone()[0]
    connection.close()
    assert stored == 1, f"{stored} rows for FRC0603F1002TS — the second run duplicated it"

    third = runner.plan(lines, libs, lookup, find_existing=runner.existing_lookup(config))
    third[0].record.values["Value"] = "10k 1%"  # type: ignore[union-attr]
    updated = runner.commit(config, third, on_exist="update")
    assert updated.updated == 1, vars(updated)
    assert updated.changed_fields.get("FRC0603F1002TS") == ["Value"], updated.changed_fields


def check_payload_shapes() -> None:
    """``lcsc-parts`` prints a part, a list of parts, or a search/BOM envelope."""
    from .lcsc import _iter_payloads

    part = {"lcsc": "C1", "mpn": "X"}
    assert list(_iter_payloads(part)) == [part]
    assert list(_iter_payloads([part])) == [part]
    assert list(_iter_payloads({"parts": [part]})) == [part]
    assert list(_iter_payloads({"part": part})) == [part]
    assert list(_iter_payloads({"query": "x", "parts": [part, part]})) == [part, part]
    assert list(_iter_payloads({"nothing": 1})) == []


# -- run -------------------------------------------------------------------


def _work_root(explicit: str | Path | None) -> tuple[Path, bool]:
    """A writable directory for the fixture tree, and whether we created it.

    Prefers the system temp folder, but a sandbox that allows creating a temp
    directory and not writing inside it is common on Windows; the fallback is
    ``<cwd>/.wip/kicad_db_selftest``, which is where this project keeps scratch
    files anyway.
    """
    if explicit:
        root = Path(explicit).expanduser()
        root.mkdir(parents=True, exist_ok=True)
        return root, False

    try:
        candidate = Path(tempfile.mkdtemp(prefix="kicad_db_selftest_"))
        probe = candidate / "probe"
        probe.mkdir()
        (probe / "x").write_text("x", encoding="utf-8")
        return candidate, True
    except OSError:
        pass
    fallback = Path.cwd() / ".wip" / "kicad_db_selftest"
    if fallback.exists():
        import shutil

        shutil.rmtree(fallback, ignore_errors=True)
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback, True


def run(workdir: str | Path | None = None) -> int:
    import shutil

    checks: list[tuple[str, callable]] = []
    failures = 0
    root, temporary = _work_root(workdir)
    try:
        libs = build_tree(root)
        config = make_config(libs, root)

        checks.append(("sexpr", check_sexpr))
        checks.append(("schema", lambda: check_schema(root)))
        checks.append(("libraries", lambda: check_libraries(config)))
        checks.append(("classification", check_classification))
        checks.append(("mapping", lambda: check_mapping(config)))
        checks.append(("stage", lambda: check_stage(config, root)))
        checks.append(("verify", lambda: check_verify(config, root)))
        checks.append(("commit", lambda: check_commit(config, root)))
        checks.append(("payload shapes", check_payload_shapes))

        for name, check in checks:
            try:
                check()
            except AssertionError as exc:
                failures += 1
                print(f"FAIL {name}: {exc}")
            except Exception as exc:  # pragma: no cover - unexpected
                failures += 1
                print(f"ERROR {name}: {type(exc).__name__}: {exc}")
            else:
                print(f"ok   {name}")
    finally:
        if temporary:
            shutil.rmtree(root, ignore_errors=True)
    print("")
    if failures:
        print(f"{failures} check(s) failed")
        return 1
    print(f"{len(checks)} checks passed")
    return 0



if __name__ == "__main__":  # pragma: no cover
    sys.exit(run())
