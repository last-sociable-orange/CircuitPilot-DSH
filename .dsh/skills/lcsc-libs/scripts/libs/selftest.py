"""Offline self-test: parsers, writers and geometry, using the bundled fixtures.

Run via ``python lcsc_libs.py selftest``. No network, no KiCad installation needed.
Assertions are the ones that catch a broken conversion: pin counts, pad geometry
against a known land pattern, and structural validity of the emitted files.
"""

from __future__ import annotations

import collections
import json
from pathlib import Path

from easyeda import footprint as easyfp
from easyeda.document import parse_records
from easyeda.model3d import parse_model
from easyeda.symbol import parse_symbol
from kicad.footprint_writer import write_footprint
from kicad.symbol_writer import write_symbol_library
from kicad.validate import check_footprint, check_symbol_library, count_pads

from libs.bundle import identity_of

TOLERANCE = 0.01


class SelftestFailure(AssertionError):
    pass


def _fixture(fixtures: Path, part: str) -> dict:
    path = fixtures / f"{part}.json"
    if not path.exists():
        raise SelftestFailure(f"missing fixture {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))["result"]


def _close(actual: float, expected: float, label: str) -> None:
    if abs(actual - expected) > TOLERANCE:
        raise SelftestFailure(f"{label}: expected {expected:.4f}, got {actual:.4f}")


def run_selftest(fixtures: Path) -> int:
    checks = 0

    # -- symbol conversion -------------------------------------------------
    result = _fixture(fixtures, "C25804")
    identity = identity_of("C25804", result)
    symbol = parse_symbol(result)
    if symbol is None or len(symbol.pins) != 2:
        raise SelftestFailure("C25804 should have a 2-pin symbol")
    numbers = sorted(pin.number for pin in symbol.pins)
    if numbers != ["1", "2"]:
        raise SelftestFailure(f"C25804 pin numbers: {numbers}")
    if len(symbol.rects) != 1:
        raise SelftestFailure("C25804 should have one body rectangle")
    rect = symbol.rects[0]
    x1, y1 = symbol_to_mm(symbol, rect.x1, rect.y1)
    x2, y2 = symbol_to_mm(symbol, rect.x2, rect.y2)
    _close(abs(x2 - x1), 5.08, "C25804 body width")
    _close(abs(y2 - y1), 2.032, "C25804 body height")
    checks += 4

    text, warnings = write_symbol_library(result, identity)
    if text is None:
        raise SelftestFailure(f"C25804 symbol not written: {warnings}")
    check_symbol_library(text, expected_symbol=identity.symbol_name)
    if text.count("(pin ") != 2:
        raise SelftestFailure("C25804 symbol file should contain two pins")
    if "(version 20251024)" not in text:
        raise SelftestFailure("symbol library must carry the KiCad 10 version stamp")
    if "(embedded_fonts no)" not in text:
        raise SelftestFailure("symbol library must end its symbol with (embedded_fonts no)")
    checks += 4

    # -- footprint conversion ---------------------------------------------
    footprint = easyfp.parse_footprint(result)
    if footprint is None or len(footprint.pads) != 2:
        raise SelftestFailure("C25804 should have a 2-pad footprint")
    centres = sorted(footprint.pad_centres_mm())
    for _number, _x, y, width, height, _rotation in centres:
        _close(width, 0.8065, "C25804 pad width")
        _close(height, 0.8640, "C25804 pad height")
        _close(y, 0.0, "C25804 pad y")
    if centres[0][1] > 0:
        raise SelftestFailure("C25804 pads should be ordered by x")
    checks += 5
    # Pad 1 is on the negative side, pad 2 on the positive side.
    if centres[0][0] != "1":
        raise SelftestFailure(f"C25804 pad order: {[pad[0] for pad in centres]}")
    checks += 1

    fp_text, fp_warnings = write_footprint(result, identity, "PREFIX/test.step")
    if fp_text is None:
        raise SelftestFailure(f"C25804 footprint not written: {fp_warnings}")
    check_footprint(fp_text, expected_name=identity.footprint_name)
    if count_pads(fp_text) != 2:
        raise SelftestFailure("C25804 footprint file should contain two pads")
    if "(version 20260206)" not in fp_text:
        raise SelftestFailure("footprint must carry the KiCad 10 version stamp")
    if "(model " not in fp_text:
        raise SelftestFailure("footprint should reference the model when one is given")
    checks += 4

    # -- a fine-pitch package ---------------------------------------------
    lqfp = _fixture(fixtures, "C8734")
    lqfp_fp = easyfp.parse_footprint(lqfp)
    if lqfp_fp is None or len(lqfp_fp.pads) != 48:
        raise SelftestFailure("C8734 should have 48 pads")
    # A QFP has pads on all four sides: the two x values with the most pads are the
    # left and right columns, twelve pads each.
    columns = collections.Counter(round(pad.x, 3) for pad in lqfp_fp.pads)
    column_x, column_pads = columns.most_common(1)[0]
    if column_pads != 12:
        raise SelftestFailure(f"LQFP-48 columns should hold 12 pads, got {column_pads}")
    ys = sorted(pad.y for pad in lqfp_fp.pads if round(pad.x, 3) == column_x)
    pitch = (ys[-1] - ys[0]) / (len(ys) - 1) * easyfp.UNIT_MM
    _close(pitch, 0.5, "LQFP-48 pin pitch")
    span = (max(columns) - min(columns)) * easyfp.UNIT_MM
    if not 8.0 < span < 10.0:
        raise SelftestFailure(f"LQFP-48 pad-row span should be about 9 mm, got {span:.2f}")
    lqfp_text, _ = write_footprint(lqfp, identity_of("C8734", lqfp))
    if lqfp_text is None or count_pads(lqfp_text) != 48:
        raise SelftestFailure("LQFP-48 footprint should contain 48 pads")
    checks += 5

    # -- 3D model reference ----------------------------------------------
    model = parse_model(parse_records((result.get("packageDetail") or {}).get("dataStr")))
    if model is None or not model.uuid:
        raise SelftestFailure("C25804 should reference a 3D model")
    checks += 1

    print(f"selftest OK — {checks} checks passed against {len(list(fixtures.glob('C*.json')))} "
          f"fixtures")
    return 0


def symbol_to_mm(symbol, x: float, y: float) -> tuple[float, float]:
    from easyeda.symbol import to_mm

    return to_mm(symbol, x, y)
