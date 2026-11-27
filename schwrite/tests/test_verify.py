"""verify: KiCad's read-back must match the netlist, field by field."""

import shutil

import pytest

from schwrite import kicad_cli, verify

ORCAD = """( { EESchema Netlist Version 1.1 created  2026-11-27 }
 ( /09403160-fcf3-5823-ad2d-345de8ee3de4 Standard:R_0402  R60 10k
  (    1 unconnected-(R60-Pad1) )
 )
 ( /169cd627-9643-522c-bb4b-f09a463833ac Standard:C_0402  C54 100pF
  (    1 unconnected-(C54-Pad1) )
 )
)
"""


def test_parse_orcad_reads_ref_value_and_footprint() -> None:
    found = verify.parse_orcad(ORCAD)
    assert found == {"R60": ("10k", "Standard:R_0402"), "C54": ("100pF", "Standard:C_0402")}


def test_compare_passes_when_everything_matches() -> None:
    expected = {"R60": ("10k", "Standard:R_0402")}
    assert verify.compare(expected, dict(expected)).ok


def test_compare_reports_a_missing_part() -> None:
    result = verify.compare({"R60": ("10k", "Standard:R_0402")}, {})
    assert result.ok is False
    assert result.missing == ["R60"]
    assert "missing from the page: R60" in result.problems()


def test_compare_reports_an_extra_part() -> None:
    result = verify.compare({}, {"R60": ("10k", "Standard:R_0402")})
    assert result.extra == ["R60"]
    assert "not in the netlist" in result.problems()[0]


def test_compare_reports_a_wrong_value() -> None:
    result = verify.compare(
        {"R60": ("10k", "Standard:R_0402")}, {"R60": ("100k", "Standard:R_0402")}
    )
    assert result.wrong_value == [("R60", "10k", "100k")]
    assert "value '100k' on the page, '10k' in the netlist" in result.problems()[0]


def test_compare_reports_a_wrong_footprint() -> None:
    result = verify.compare(
        {"R60": ("10k", "Standard:R_0402")}, {"R60": ("10k", "Standard:R_0603")}
    )
    assert result.wrong_footprint == [("R60", "Standard:R_0402", "Standard:R_0603")]


def test_expected_from_parts_uses_the_database_values() -> None:
    class Part:
        def __init__(self, ref, value, footprint):
            self.ref, self.value, self.footprint = ref, value, footprint

    expected = verify.expected_from_parts([Part("R1", "10k", "Standard:R_0402")])
    assert expected == {"R1": ("10k", "Standard:R_0402")}


needs_kicad = pytest.mark.skipif(
    shutil.which("kicad-cli") is None and not kicad_cli.find(),
    reason="kicad-cli is not installed",
)


@needs_kicad
def test_readback_of_a_real_page(tmp_path) -> None:
    """A page built by schwrite reads back as exactly the parts it was built from."""
    from schwrite import cli, dblib, netlist, parts, symbols
    from conftest import DBL, LIBRARIES, NETLISTS

    page = tmp_path / "Sync.kicad_sch"
    code = cli.main(
        [
            "build", "--netlist", str(NETLISTS / "Sync.json"), "--out", str(page),
            "--libs", str(LIBRARIES), "--db", str(DBL), "--json",
        ]
    )
    assert code == cli.EXIT_OK
    database = dblib.ComponentDb(DBL)
    library = symbols.SymbolLibrary(LIBRARIES)
    expected = verify.expected_from_parts(
        parts.resolve_parts(netlist.load(NETLISTS / "Sync.json"), database, library)
    )
    result = verify.compare(expected, verify.readback(page))
    assert result.ok, result.problems()
