"""CLI behaviour that already holds in M2: exit codes, report shape, atomic write.

The gates (`verify`, `lint`, `pages`) are M4; what is tested here is what they will build on.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import DBL, LIBRARIES, NETLISTS, REFERENCE
from schwrite import cli


def run(argv: list[str]) -> int:
    return cli.main(argv)


def base_args(tmp_path: Path, netlist: str = "Sync") -> list[str]:
    return [
        "build",
        "--netlist", str(NETLISTS / f"{netlist}.json"),
        "--out", str(tmp_path / f"{netlist}.kicad_sch"),
        "--libs", str(LIBRARIES),
        "--db", str(DBL),
        "--root-page", str(REFERENCE / "MainController.kicad_sch"),
    ]


def test_build_writes_a_page_and_reports_success(tmp_path, capsys) -> None:
    out = tmp_path / "Sync.kicad_sch"
    code = run(base_args(tmp_path) + ["--json"])
    assert code == cli.EXIT_OK
    report = json.loads(capsys.readouterr().out)
    assert report["verdict"] == "pass"
    assert report["page"] == "Sync"
    assert report["parts"] == 16
    assert report["path"].startswith("/")
    assert report["project"] == "MainController"
    assert report["layout"]["fits"] is True
    assert out.is_file()
    assert out.read_text(encoding="utf-8").startswith("(kicad_sch\n")


def test_build_leaves_no_temporary_file_behind(tmp_path) -> None:
    run(base_args(tmp_path))
    leftovers = [p.name for p in tmp_path.iterdir() if p.suffix == ".tmp" or p.name.startswith(".")]
    assert leftovers == []


def test_bad_netlist_exits_2_and_writes_nothing(tmp_path, capsys) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text('{"components": [], "nets": []}', encoding="utf-8")
    out = tmp_path / "Page.kicad_sch"
    code = run(
        ["build", "--netlist", str(bad), "--out", str(out), "--libs", str(LIBRARIES), "--db", str(DBL), "--json"]
    )
    assert code == cli.EXIT_NETLIST
    report = json.loads(capsys.readouterr().out)
    assert report["verdict"] == "fail"
    assert report["error"]["kind"] == "netlist"
    assert not out.exists()


def test_unknown_part_exits_3_names_the_part_and_writes_nothing(tmp_path, capsys) -> None:
    netlist_text = {
        "design": "T",
        "subsystem": "T",
        "components": [{"ref": "R1", "lcsc": "C000000"}],
        "nets": [{"name": "N1", "members": [{"ref": "R1", "pin": "1"}]}],
    }
    path = tmp_path / "n.json"
    path.write_text(json.dumps(netlist_text), encoding="utf-8")
    out = tmp_path / "Page.kicad_sch"
    code = run(
        ["build", "--netlist", str(path), "--out", str(out), "--libs", str(LIBRARIES), "--db", str(DBL), "--json"]
    )
    assert code == cli.EXIT_BUILD
    report = json.loads(capsys.readouterr().out)
    assert "C000000" in report["error"]["detail"]
    assert not out.exists()


def test_missing_root_page_is_reported_not_guessed(tmp_path, capsys) -> None:
    """With no root page the page is written as a root page â€” and the report says so."""
    code = run(
        [
            "build", "--netlist", str(NETLISTS / "Sync.json"),
            "--out", str(tmp_path / "Sync.kicad_sch"),
            "--libs", str(LIBRARIES), "--db", str(DBL), "--json",
        ]
    )
    assert code == cli.EXIT_OK
    report = json.loads(capsys.readouterr().out)
    assert report["path"] == "/"


def test_rebuild_overwrites_atomically(tmp_path) -> None:
    out = tmp_path / "Sync.kicad_sch"
    run(base_args(tmp_path))
    first = out.read_text(encoding="utf-8")
    run(base_args(tmp_path) + ["--uuid-seed", "seeded"])
    second = out.read_text(encoding="utf-8")
    assert first != second and second.startswith("(kicad_sch")
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".")]


def test_default_paper_is_a4_and_small_pages_build_on_it(tmp_path, capsys) -> None:
    """§10: A4 is the default sheet — Sync fits it without any --paper flag."""
    code = run(base_args(tmp_path) + ["--json"])
    assert code == cli.EXIT_OK
    report = json.loads(capsys.readouterr().out)
    assert report["paper"] == "A4"
    assert report["paper_requested"] == "A4"


def test_a_page_that_does_not_fit_fails_and_names_the_sheet_it_needs(
    monkeypatch, tmp_path, capsys
) -> None:
    """An overflowing page is refused, never written half on the sheet.

    Every real page now fits A4, so the fit gate is exercised with a deliberately tiny
    sheet rather than by finding a page that overflows.
    """
    from schwrite import layout

    monkeypatch.setitem(layout.PAGE_SIZES, "A7", (60.0, 40.0))
    out = tmp_path / "Sync.kicad_sch"
    code = run(
        [
            "build", "--netlist", str(NETLISTS / "Sync.json"), "--out", str(out),
            "--libs", str(LIBRARIES), "--db", str(DBL), "--paper", "A7", "--json",
        ]
    )
    assert code == cli.EXIT_BUILD
    report = json.loads(capsys.readouterr().out)
    detail = report["error"]["detail"]
    assert "does not fit A7" in detail and "A4" in detail and "--paper auto" in detail
    assert not out.exists()


def test_paper_auto_picks_the_smallest_sheet_that_holds_the_page(tmp_path, capsys) -> None:
    out = tmp_path / "Power.kicad_sch"
    code = run(
        [
            "build", "--netlist", str(NETLISTS / "Power.json"), "--out", str(out),
            "--libs", str(LIBRARIES), "--db", str(DBL), "--paper", "auto", "--json",
        ]
    )
    assert code == cli.EXIT_OK
    report = json.loads(capsys.readouterr().out)
    assert report["paper"] == "A4"          # measured: the biggest page needs 168 x 144 mm
    assert report["paper_requested"] == "auto"
    assert report["layout"]["fits"] is True
    assert out.is_file()


def test_seeded_build_is_reproducible(tmp_path) -> None:
    a = tmp_path / "a.kicad_sch"
    b = tmp_path / "b.kicad_sch"
    for target in (a, b):
        run(
            [
                "build", "--netlist", str(NETLISTS / "USB.json"), "--out", str(target),
                "--libs", str(LIBRARIES), "--db", str(DBL), "--uuid-seed", "same",
                "--project", "P", "--sheet-path", "/r/s", "--paper", "auto",
            ]
        )
    assert a.read_text(encoding="utf-8").replace("a.kicad_sch", "") == b.read_text(
        encoding="utf-8"
    ).replace("b.kicad_sch", "")
