"""erc: only the classes a placement-only page may have are accepted."""

import shutil

import pytest

from pathlib import Path

from schwrite import erc, kicad_cli


def test_expected_classes_pass() -> None:
    report = erc.classify(
        [
            {"type": "pin_not_connected", "description": "Pin not connected"},
            {"type": "pin_not_connected", "description": "Pin not connected"},
            {"type": "power_pin_not_driven", "description": "Power pin not driven"},
        ]
    )
    assert report.ok is True
    assert report.counts == {"pin_not_connected": 2, "power_pin_not_driven": 1}


def test_an_unexpected_class_fails_and_is_named() -> None:
    report = erc.classify(
        [{"type": "lib_symbol_issues", "description": "Symbol library 'X' not found"}]
    )
    assert report.ok is False
    assert "lib_symbol_issues" in report.problems()[0]


def test_many_unexpected_violations_are_truncated() -> None:
    violations = [{"type": "something_new", "description": f"case {i}"} for i in range(14)]
    problems = erc.classify(violations).problems()
    assert len(problems) == 11                     # ten shown, plus the "and N more" line
    assert problems[-1].startswith("… and 4 more")


def test_a_clean_page_passes() -> None:
    assert erc.classify([]).ok is True


def test_the_page_is_erd_in_its_own_project(tmp_path) -> None:
    """ERC judges one page: the scratch project carries the page and the real libraries."""
    (tmp_path / "MainController.kicad_pro").write_text("{}", encoding="utf-8")
    page = tmp_path / "Sync.kicad_sch"
    page.write_text("(kicad_sch)", encoding="utf-8")
    (tmp_path / "sym-lib-table").write_text(
        '(lib (name "Symbol") (uri "${KIPRJMOD}/x") (type "KiCad"))', encoding="utf-8"
    )
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    target = erc._scratch_project(page, scratch)
    assert target.name == "Sync.kicad_sch"
    assert (scratch / "Sync.kicad_pro").is_file()          # named after the page
    table = (scratch / "sym-lib-table").read_text(encoding="utf-8")
    assert "${KIPRJMOD}" not in table                      # absolute, so it resolves
    assert str(tmp_path.resolve()).replace("\\", "/") in table


def test_only_pin_classes_are_expected() -> None:
    """A page-scoped ERC may report unconnected pins and nothing else."""
    assert set(erc.EXPECTED) == {"pin_not_connected", "pin_not_driven", "power_pin_not_driven"}
    for wrong in ("lib_symbol_issues", "lib_symbol_mismatch", "footprint_link_issues",
                  "duplicate_sheet_names"):
        assert wrong not in erc.EXPECTED


def test_library_failures_trigger_the_copy() -> None:
    """`lib_symbol_issues` means KiCad could not associate a project with the page."""
    assert erc._unresolved([{"type": "lib_symbol_issues"}]) is True
    assert erc._unresolved([{"type": "pin_not_connected"}, {"type": "footprint_link_issues"}]) is False


def test_the_copy_keeps_the_page_name() -> None:
    """The scratch project must be named after the page: that is how KiCad associates them."""
    page = Path("Design/Sync.kicad_sch")
    assert f"{page.stem}.kicad_pro" == "Sync.kicad_pro"
