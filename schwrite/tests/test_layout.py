"""Layout (Â§8.3): cells, field slots and row packing.

Two kinds of test live here:

* **unit** â€” the geometry rules, with numbers worked out by hand from the constants;
* **parity** â€” the 2026-11-25 builder's positions, replayed from
  `.dsh/skills/kicad-sch-build/scripts/schgen/build.py`. That build passed the netlist gate
  on every page, so its positions are the reference. Where we deliberately differ, the test
  says exactly why instead of tolerating a drift.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from conftest import DBL, LIBRARIES, NETLISTS, PAGES
from schwrite import dblib, layout, netlist, parts, symbols

REPO = Path(__file__).resolve().parents[1]
OLD_BUILDER = REPO.parent / ".dsh" / "skills" / "kicad-sch-build" / "scripts" / "schgen" / "build.py"


@pytest.fixture(scope="module")
def db() -> dblib.ComponentDb:
    return dblib.ComponentDb(DBL)


@pytest.fixture(scope="module")
def library() -> symbols.SymbolLibrary:
    return symbols.SymbolLibrary(LIBRARIES)


@pytest.fixture(scope="module")
def old_builder():
    if not OLD_BUILDER.is_file():
        pytest.skip("2026-11-25 builder not present; parity replay unavailable")
    spec = importlib.util.spec_from_file_location("old_schgen_build", OLD_BUILDER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


# -- unit: the rules -------------------------------------------------------
# -- the cell: symbol graphic + Reference/Value only -----------------------
def test_cell_size_for_a_resistor(db, library) -> None:
    """Hand arithmetic: a resistor claims its graphic plus its text block.

    R1 is 0 mm wide (both pins on one vertical line) and 5.08 mm tall. Its text block is
    max(len("R1"), len("10k")) = 3 characters wide, sitting TEXT_GAP = 2.54 mm to the right:
        2.54 + 3.0 = 5.54  ->  rounded up to the 1.27 grid  ->  6.35
    """
    loaded = netlist.load(NETLISTS / "MCU.json")
    resolved = parts.resolve_parts(loaded, db, library)
    r1 = next(part for part in resolved if part.ref == "R1")     # 10 k
    assert r1.value == "10k"
    size = layout.cell_size(r1)
    assert size.left == 0.0
    assert size.right == 6.35
    assert size.top == 2.54 and size.bottom == 2.54
    assert (size.width, size.height) == (6.35, 5.08)


def test_cell_does_not_reserve_room_for_net_labels(db, library) -> None:
    """No wiring, no labels: net names must not change a cell's size."""
    loaded = netlist.load(NETLISTS / "Sync.json")
    resolved = parts.resolve_parts(loaded, db, library)
    for part in resolved:
        bare = layout.cell_size(part)
        loaded_nets = layout.cell_size(part)
        assert (bare.width, bare.height) == (loaded_nets.width, loaded_nets.height), part.ref


def test_field_slots_sit_beside_the_graphic_on_the_grid(db, library) -> None:
    """Reference and Value go right of the graphic, 100 mil clear of it, on the 50 mil grid."""
    loaded = netlist.load(NETLISTS / "Sync.json")
    resolved = parts.resolve_parts(loaded, db, library)
    for part in resolved:
        size = layout.cell_size(part)
        anchor = (25.4, 50.8)
        slots = layout.field_slots(anchor, size)
        for name in ("Reference", "Value"):
            x, y = slots[name]
            assert abs(x / layout.GRID - round(x / layout.GRID)) < 1e-6, (part.ref, name, x)
            assert abs(y / layout.GRID - round(y / layout.GRID)) < 1e-6, (part.ref, name, y)
        # the text block starts 100 mil right of the graphic, within one snap of the grid
        text_left = slots["Reference"][0] - size.text_width / 2
        graphic_right = anchor[0] + (part.pin_box[2] if part.pins else 0.0)
        clearance = text_left - graphic_right
        assert layout.TEXT_GAP - layout.GRID - 1e-6 <= clearance <= layout.TEXT_GAP + layout.GRID + 1e-6, (
            part.ref, clearance
        )
        # Reference above Value, TEXT_ROW apart
        assert slots["Value"][0] == slots["Reference"][0]
        assert slots["Value"][1] - slots["Reference"][1] == pytest.approx(layout.TEXT_ROW)


def test_parts_are_separated_by_500_mil(db, library) -> None:
    """Every neighbour gap is exactly 500 mil, vertically and between columns."""
    for page in PAGES:
        loaded = netlist.load(NETLISTS / f"{page}.json")
        resolved = parts.resolve_parts(loaded, db, library)
        cells, _ = layout.plan_layout(resolved, page_size="A4")
        by_col: dict[float, list] = {}
        for cell in cells.values():
            by_col.setdefault(round(cell.box[0], 3), []).append(cell)
        for members in by_col.values():
            members.sort(key=lambda cell: cell.box[1])
            for upper, lower in zip(members, members[1:]):
                assert lower.box[1] - upper.box[3] == pytest.approx(layout.MIN_GUTTER), page
        starts = sorted(by_col)
        for left, right in zip(starts, starts[1:]):
            widest = max(cell.box[2] for cell in by_col[left])
            assert right - widest == pytest.approx(layout.COLUMN_GAP), page
        assert layout.MIN_GUTTER == pytest.approx(12.7)     # 500 mil
        assert layout.COLUMN_GAP == pytest.approx(12.7)


def test_every_page_fits_a4(db, library) -> None:
    """With no label room and 500 mil gaps, every page fits the default sheet."""
    for page in PAGES:
        loaded = netlist.load(NETLISTS / f"{page}.json")
        resolved = parts.resolve_parts(loaded, db, library)
        _, summary = layout.plan_layout(resolved, page_size="A4")
        assert summary["fits"] is True, (page, summary)
        assert summary["width_mm"] <= summary["band_mm"][0]
        assert summary["height_mm"] <= summary["band_mm"][1]


def _cells_for(page, db, library, paper="A4"):
    loaded = netlist.load(NETLISTS / f"{page}.json")
    resolved = parts.resolve_parts(loaded, db, library)
    return layout.plan_layout(resolved, page_size=paper)


@pytest.mark.parametrize("page", sorted(PAGES))
def test_every_anchor_is_on_the_grid(page, db, library) -> None:
    cells, _ = _cells_for(page, db, library)
    for ref, cell in cells.items():
        for value in cell.anchor:
            steps = value / layout.GRID
            assert abs(steps - round(steps)) < 1e-6, (ref, cell.anchor)


def test_smallest_fitting_page_prefers_a4(db, library) -> None:
    for page in PAGES:
        loaded = netlist.load(NETLISTS / f"{page}.json")
        resolved = parts.resolve_parts(loaded, db, library)
        found = layout.smallest_fitting_page(resolved)
        assert found is not None and found[0] == "A4", page


def test_cells_never_overlap_on_any_page(db, library) -> None:
    for page in PAGES:
        loaded = netlist.load(NETLISTS / f"{page}.json")
        resolved = parts.resolve_parts(loaded, db, library)
        cells, _ = layout.plan_layout(resolved, page_size="A4")
        boxes = [(cell.box, ref) for ref, cell in cells.items()]
        for index, (first, ref_a) in enumerate(boxes):
            for second, ref_b in boxes[index + 1:]:
                overlap_x = min(first[2], second[2]) - max(first[0], second[0])
                overlap_y = min(first[3], second[3]) - max(first[1], second[1])
                assert not (overlap_x > 1e-6 and overlap_y > 1e-6), (page, ref_a, ref_b)


def test_layout_is_deterministic(db, library) -> None:
    loaded = netlist.load(NETLISTS / "Sync.json")
    resolved = parts.resolve_parts(loaded, db, library)
    first, _ = layout.plan_layout(resolved, page_size="A4")
    second, _ = layout.plan_layout(resolved, page_size="A4")
    assert {ref: cell.anchor for ref, cell in first.items()} == {
        ref: cell.anchor for ref, cell in second.items()
    }
