"""Offline tests for the lcsc-libs skill.

Everything here runs against the recorded EasyEDA fixtures: no network, no KiCad
installation. The geometry assertions are the ones that would catch a silently wrong
conversion (units, origin, axes), which is the failure mode that matters.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from easyeda import footprint as easyfp
from easyeda.document import document, parse_records
from easyeda.model3d import parse_model
from easyeda.symbol import parse_symbol, to_mm
from kicad.footprint_writer import write_footprint
from kicad.symbol_writer import write_symbol_library
from kicad.validate import ValidationError, check_balanced, check_symbol_library, count_pads
from libs import naming
from libs.bundle import identity_of
from libs.cache import ResponseCache

FIXTURES = Path(__file__).resolve().parent / "fixtures"
UNIT = easyfp.UNIT_MM


def fixture(part: str) -> dict:
    return json.loads((FIXTURES / f"{part}.json").read_text(encoding="utf-8"))["result"]


def identity(part: str):
    return identity_of(part, fixture(part))


# -- document format -------------------------------------------------------


class TestDocument:
    def test_accepts_both_string_and_object_documents(self):
        part = fixture("C25804")
        assert parse_records(part["dataStr"])
        assert isinstance(document(part["dataStr"]), dict)

    def test_splits_segments_and_fields(self):
        records = parse_records(fixture("C8734")["dataStr"])
        pins = [record for record in records if record.op == "P"]
        assert len(pins) == 48
        pin = pins[0]
        assert pin.segment_field(0, 0) == "P"
        assert len(pin.segments) >= 5, "a pin carries its name/number segments"

    def test_unknown_ops_are_reported_not_fatal(self):
        symbol = parse_symbol({"dataStr": json.dumps({"shape": ["ZZZ~1~2", "R~0~0~~ ~4~2"]})})
        assert symbol is not None
        assert any("ZZZ" in warning for warning in symbol.warnings)

    def test_empty_document_yields_none(self):
        assert parse_symbol({"dataStr": json.dumps({"shape": []})}) is None


# -- symbol geometry ------------------------------------------------------


class TestSymbol:
    def test_two_pin_part_geometry(self):
        symbol = parse_symbol(fixture("C25804"))
        assert symbol is not None
        assert sorted(pin.number for pin in symbol.pins) == ["1", "2"]
        assert len(symbol.rects) == 1
        rect = symbol.rects[0]
        x1, y1 = to_mm(symbol, rect.x1, rect.y1)
        x2, y2 = to_mm(symbol, rect.x2, rect.y2)
        assert abs(abs(x2 - x1) - 5.08) < 0.01
        assert abs(abs(y2 - y1) - 2.032) < 0.01

    def test_pin_angles_follow_the_connection_to_body_direction(self):
        """KiCad's pin angle points from the connection point towards the body.

        Reference: KiCad 10's own ``Device:D`` puts its left pin (connection at
        x = -3.81) at angle 0 and its right pin at 180. C25804's pins land at -5.08 and
        +5.08 after conversion, so the same angles must appear here.
        """
        symbol = parse_symbol(fixture("C25804"))
        by_number = {pin.number: pin for pin in symbol.pins}
        assert by_number["1"].angle == 0      # connection on the left of the body
        assert by_number["2"].angle == 180    # connection on the right of the body
        assert by_number["1"].length == pytest.approx(2.54, abs=0.01)
        assert by_number["2"].length == pytest.approx(2.54, abs=0.01)

    def test_every_pin_reaches_the_body_edge(self):
        """The invariant that catches a wrong angle: the far end must touch the body."""
        for part in ("C25804", "C8734", "C2040", "C351427", "C5380687"):
            symbol = parse_symbol(fixture(part))
            assert symbol is not None and symbol.rects
            rect = symbol.rects[0]
            ax, ay = symbol.to_mm(rect.x1, rect.y1)
            bx, by = symbol.to_mm(rect.x2, rect.y2)
            left, right = min(ax, bx), max(ax, bx)
            bottom, top = min(ay, by), max(ay, by)
            for pin in symbol.pins:
                x, y = symbol.to_mm(pin.x, pin.y)
                if pin.angle == 0:
                    fx, fy = x + pin.length, y
                elif pin.angle == 180:
                    fx, fy = x - pin.length, y
                elif pin.angle == 90:
                    fx, fy = x, y + pin.length
                else:
                    fx, fy = x, y - pin.length
                on_vertical = ((abs(fx - left) < 0.01 or abs(fx - right) < 0.01)
                               and bottom - 0.01 <= fy <= top + 0.01)
                on_horizontal = ((abs(fy - top) < 0.01 or abs(fy - bottom) < 0.01)
                                 and left - 0.01 <= fx <= right + 0.01)
                assert on_vertical or on_horizontal, (
                    f"{part} pin {pin.number} angle {pin.angle} lands at "
                    f"({fx:.2f}, {fy:.2f}), body {left:.2f}..{right:.2f} x "
                    f"{bottom:.2f}..{top:.2f}")

    def test_pins_sit_on_the_1_27_mm_grid(self):
        """The origin is EasyEDA's own, so pins must stay on their drawing grid."""
        for part in ("C25804", "C8734", "C2040"):
            symbol = parse_symbol(fixture(part))
            for pin in symbol.pins:
                x, y = symbol.to_mm(pin.x, pin.y)
                assert abs(x / 1.27 - round(x / 1.27)) < 1e-6, (part, pin.number, x)
                assert abs(y / 1.27 - round(y / 1.27)) < 1e-6, (part, pin.number, y)

    def test_fine_pitch_part_splits_pins_between_left_and_right(self):
        symbol = parse_symbol(fixture("C8734"))
        angles = [pin.angle for pin in symbol.pins]
        assert angles.count(0) == 24 and angles.count(180) == 24

    def test_drawing_is_centred_on_the_origin(self):
        symbol = parse_symbol(fixture("C8734"))
        xs = [to_mm(symbol, pin.x, pin.y)[0] for pin in symbol.pins]
        assert abs(min(xs) + max(xs)) < 0.01, "pins should be symmetric about the origin"

    def test_fine_pitch_part_keeps_all_pins(self):
        symbol = parse_symbol(fixture("C8734"))
        assert symbol is not None
        assert len(symbol.pins) == 48
        numbers = {pin.number for pin in symbol.pins}
        assert numbers == {str(index) for index in range(1, 49)}


# -- footprint geometry ---------------------------------------------------


class TestFootprint:
    def test_r0603_pads_match_the_known_land_pattern(self):
        footprint = easyfp.parse_footprint(fixture("C25804"))
        assert footprint is not None
        pads = sorted(footprint.pad_centres_mm())
        assert len(pads) == 2
        for _number, _x, y, width, height, rotation in pads:
            assert width == pytest.approx(0.8065, abs=0.005)
            assert height == pytest.approx(0.8640, abs=0.005)
            assert y == pytest.approx(0.0, abs=0.005)
            assert rotation == 0
        assert pads[0][1] == pytest.approx(-0.7534, abs=0.005)
        assert pads[1][1] == pytest.approx(+0.7534, abs=0.005)

    def test_lqfp48_pitch_and_rows(self):
        footprint = easyfp.parse_footprint(fixture("C8734"))
        assert footprint is not None
        assert len(footprint.pads) == 48
        columns: dict[float, list[float]] = {}
        for pad in footprint.pads:
            columns.setdefault(round(pad.x, 3), []).append(pad.y)
        widest = max(columns.values(), key=len)
        assert len(widest) == 12
        ys = sorted(widest)
        pitch = (ys[-1] - ys[0]) / (len(ys) - 1) * UNIT
        assert pitch == pytest.approx(0.5, abs=0.01)

    def test_footprint_is_centred_on_the_pad_field(self):
        footprint = easyfp.parse_footprint(fixture("C8734"))
        assert footprint is not None
        xs = [footprint.to_mm(pad.x, pad.y)[0] for pad in footprint.pads]
        assert abs(min(xs) + max(xs)) < 0.02

    def test_silk_and_fab_layers_are_separated(self):
        footprint = easyfp.parse_footprint(fixture("C25804"))
        assert footprint is not None
        assert any(track.layer == "F.SilkS" for track in footprint.tracks)
        # Regions land on copper, mask or drawing layers (LCSC3D's mapping, which also
        # sends EasyEDA's component-shape layer 99 to Dwgs.User).
        allowed = {"F.Cu", "B.Cu", "F.Mask", "B.Mask", "F.Paste", "B.Paste",
                   "F.Fab", "B.Fab", "F.SilkS", "B.SilkS", "Dwgs.User", "Edge.Cuts"}
        assert all(region.layer in allowed for region in footprint.regions)

    def test_every_layer_used_is_a_known_kicad_layer(self):
        allowed = {"F.Cu", "B.Cu", "F.SilkS", "B.SilkS", "F.Mask", "B.Mask",
                   "F.Paste", "B.Paste", "Edge.Cuts", "F.Fab", "B.Fab", "Dwgs.User"}
        for part in ("C25804", "C8734", "C2040", "C351427", "C5380687"):
            footprint = easyfp.parse_footprint(fixture(part))
            assert footprint is not None
            layers = ({pad.layer for pad in footprint.pads}
                      | {track.layer for track in footprint.tracks}
                      | {circle.layer for circle in footprint.circles}
                      | {region.layer for region in footprint.regions})
            assert layers <= allowed, (part, layers - allowed)

    def test_paste_and_mask_ids_match_easyeda(self):
        """EasyEDA numbers 5/6 as paste and 7/8 as mask — easy to swap by accident."""
        assert easyfp.LAYERS["5"] == "F.Paste"
        assert easyfp.LAYERS["6"] == "B.Paste"
        assert easyfp.LAYERS["7"] == "F.Mask"
        assert easyfp.LAYERS["8"] == "B.Mask"
        assert easyfp.LAYERS["99"] == "Dwgs.User"

    def test_pads_live_on_copper(self):
        footprint = easyfp.parse_footprint(fixture("C8734"))
        assert footprint is not None
        assert {pad.layer for pad in footprint.pads} == {"F.Cu"}


# -- 3D model ------------------------------------------------------------


class TestModel:
    def test_model_reference_is_found(self):
        part = fixture("C8734")
        records = parse_records((part.get("packageDetail") or {}).get("dataStr"))
        model = parse_model(records)
        assert model is not None
        assert model.uuid == "a4b96ad857dc48c08dab3d0efdf20aec"
        assert model.title

    def test_absent_model_is_none(self):
        assert parse_model([]) is None


# -- writers -------------------------------------------------------------


class TestWriters:
    def test_symbol_file_is_valid_and_stamped(self):
        text, _ = write_symbol_library(fixture("C8734"), identity("C8734"))
        assert text is not None
        check_symbol_library(text, expected_symbol="STM32F103C8T6")
        assert "(version 20251024)" in text
        assert "(embedded_fonts no)" in text
        assert text.count("(pin ") == 48

    def test_footprint_file_is_valid_and_stamped(self):
        text, _ = write_footprint(fixture("C8734"), identity("C8734"), "P/f.step")
        assert text is not None
        assert "(version 20260206)" in text
        assert "(embedded_fonts no)" in text
        assert count_pads(text) == 48
        assert "(model \"P/f.step\"" in text

    def test_graphics_use_the_enumerated_fill_form(self):
        """KiCad 10 rejects `(fill solid)` / `(fill none)` and then loads nothing.

        Regression guard: only `(fill yes)` and `(fill no)` exist in KiCad's own
        50k-footprint library, and a bad form makes the whole `.pretty` unreadable.
        """
        for part in ("C25804", "C8734", "C2040"):
            text, _ = write_footprint(fixture(part), identity(part), "")
            assert text is not None
            assert "(fill solid)" not in text, part
            assert "(fill none)" not in text, part
            fills = {line.strip() for line in text.splitlines() if line.strip().startswith("(fill ")}
            assert fills <= {"(fill yes)", "(fill no)"}, (part, fills)

    def test_footprint_name_matches_folder_and_file(self):
        part = identity("C8734")
        assert part.footprint_name == part.bundle == "C8734_STM32F103C8T6"

    def test_no_model_block_without_a_model(self):
        text, _ = write_footprint(fixture("C25804"), identity("C25804"), "")
        assert text is not None
        assert "(model " not in text

    def test_part_without_symbol_is_none_not_an_exception(self):
        text, warnings = write_symbol_library({"dataStr": json.dumps({"shape": []})},
                                              identity("C25804"))
        assert text is None
        assert warnings

    def test_balance_check_catches_broken_output(self):
        with pytest.raises(ValidationError):
            check_balanced("(a (b)")
        with pytest.raises(ValidationError):
            check_balanced("(a))")


# -- naming, cache, manifest ---------------------------------------------


class TestNaming:
    def test_bundle_name_combines_part_and_mpn(self):
        assert naming.bundle_name("C8734", "STM32F103C8T6") == "C8734_STM32F103C8T6"

    def test_bundle_name_does_not_repeat_the_part_number(self):
        assert naming.bundle_name("C25804", "C25804") == "C25804"

    def test_unsafe_characters_are_replaced(self):
        assert naming.bundle_name("C1", "A/B C:D") == "C1_A_B_C_D"


class TestCache:
    def test_round_trip(self, workdir):
        cache = ResponseCache(workdir, ttl=60)
        cache.put("https://example.invalid/x", b"payload")
        assert cache.get("https://example.invalid/x") == b"payload"

    def test_ttl_zero_disables_the_cache(self, workdir):
        cache = ResponseCache(workdir, ttl=0)
        cache.put("https://example.invalid/x", b"payload")
        assert cache.get("https://example.invalid/x") is None

    def test_unknown_url_misses(self, workdir):
        assert ResponseCache(workdir, ttl=60).get("https://example.invalid/other") is None


class TestManifest:
    def test_identity_reads_the_store_fields(self):
        part = identity("C5380687")
        assert part.part == "C5380687"
        assert part.mpn
        assert part.package
        assert part.bundle.startswith("C5380687")

    def test_manifest_serialises(self):
        from libs.bundle import Manifest

        manifest = Manifest(part=identity("C25804"), output="/tmp/out", model_prefix="/m")
        payload = manifest.as_dict()
        assert payload["part"]["lcsc"] == "C25804"
        assert payload["artefacts"] == []
        json.dumps(payload)  # must be JSON-serialisable
