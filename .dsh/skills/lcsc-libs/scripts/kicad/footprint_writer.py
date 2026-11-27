"""Emit a native KiCad 10 footprint (``.kicad_mod``) for one part.

Grammar from the installed KiCad 10.0.8 libraries: ``(version 20260206)``, properties
carrying ``(layer …)`` and ``(effects …)``, ``(attr smd)``, ``(pad … smd|thru_hole …)``,
and ``(embedded_fonts no)`` before the model block.
"""

from __future__ import annotations

import itertools

from easyeda import footprint as easyfp

from kicad.sexpr import (
    FOOTPRINT_VERSION,
    GENERATOR,
    GENERATOR_VERSION,
    indent,
    n,
    q,
)

_SILK_WIDTH = 0.12
_TEXT_SIZE = 1.0


def _effects(level: int, *, size: float = _TEXT_SIZE, thickness: float = 0.15) -> list[str]:
    return [
        f"{indent(level)}(effects",
        f"{indent(level + 1)}(font",
        f"{indent(level + 2)}(size {n(size)} {n(size)})",
        f"{indent(level + 2)}(thickness {n(thickness)})",
        f"{indent(level + 1)})",
        f"{indent(level)})",
    ]


def _property(level: int, name: str, value: str, x: float, y: float, layer: str) -> list[str]:
    lines = [f"{indent(level)}(property {q(name)} {q(value)}"]
    lines.append(f"{indent(level + 1)}(at {n(x)} {n(y)} 0)")
    lines.append(f"{indent(level + 1)}(layer {q(layer)})")
    lines.extend(_effects(level + 1))
    lines.append(f"{indent(level)})")
    return lines


def _stroke(level: int, width: float) -> list[str]:
    return [
        f"{indent(level)}(stroke",
        f"{indent(level + 1)}(width {n(width)})",
        f"{indent(level + 1)}(type solid)",
        f"{indent(level)})",
    ]


def _layers_for(kind: str, layer: str) -> str:
    if kind == "thru_hole":
        return '"*.Cu" "*.Mask"'
    if layer == "B.Cu":
        return '"B.Cu" "B.Paste" "B.Mask"'
    return '"F.Cu" "F.Paste" "F.Mask"'


def write_footprint(result: dict, identity, model_reference: str = "") -> tuple[str | None, list[str]]:
    """Return ``(footprint text, warnings)``; text is ``None`` when none was published."""
    footprint = easyfp.parse_footprint(result)
    if footprint is None or not footprint.pads:
        return None, (footprint.warnings if footprint else ["no footprint data published"])

    warnings = list(footprint.warnings)
    bounds = footprint.bounds() or (0.0, 0.0, 0.0, 0.0)
    _, top = footprint.to_mm(0.0, bounds[1])
    _, bottom = footprint.to_mm(0.0, bounds[3])

    kinds = {pad.kind for pad in footprint.pads}
    attr = "smd" if kinds == {"smd"} else "through_hole" if kinds == {"thru_hole"} else "smd through_hole"

    lines = [f"(footprint {q(identity.footprint_name)}"]
    lines.append(f"{indent(1)}(version {FOOTPRINT_VERSION})")
    lines.append(f"{indent(1)}(generator {q(GENERATOR)})")
    lines.append(f"{indent(1)}(generator_version {q(GENERATOR_VERSION)})")
    lines.append(f"{indent(1)}(layer {q('F.Cu')})")
    if identity.description:
        lines.append(f"{indent(1)}(descr {q(identity.description[:200])})")
    tags = " ".join(part for part in (identity.mpn, identity.package, "LCSC", identity.part) if part)
    lines.append(f"{indent(1)}(tags {q(tags)})")
    lines.extend(_property(1, "Reference", "REF**", 0.0, top - 1.27, "F.SilkS"))
    lines.extend(_property(1, "Value", identity.mpn or identity.footprint_name, 0.0,
                           bottom + 1.27, "F.Fab"))
    lines.append(f"{indent(1)}(attr {attr})")
    lines.append(f"{indent(1)}(duplicate_pad_numbers_are_jumpers no)")

    for track in footprint.tracks:
        width = track.width or _SILK_WIDTH
        points = [footprint.to_mm(x, y) for x, y in track.points]
        for start, end in itertools.pairwise(points):
            lines.append(f"{indent(1)}(fp_line")
            lines.append(f"{indent(2)}(start {n(start[0])} {n(start[1])})")
            lines.append(f"{indent(2)}(end {n(end[0])} {n(end[1])})")
            lines.extend(_stroke(2, width))
            lines.append(f"{indent(2)}(layer {q(track.layer)})")
            lines.append(f"{indent(1)})")

    for circle in footprint.circles:
        cx, cy = footprint.to_mm(circle.cx, circle.cy)
        radius = circle.radius_mm
        lines.append(f"{indent(1)}(fp_circle")
        lines.append(f"{indent(2)}(center {n(cx)} {n(cy)})")
        lines.append(f"{indent(2)}(end {n(cx + radius)} {n(cy)})")
        lines.extend(_stroke(2, circle.width_mm or 0.15))
        lines.append(f"{indent(2)}(fill no)")
        lines.append(f"{indent(2)}(layer {q(circle.layer)})")
        lines.append(f"{indent(1)})")

    for region in footprint.regions:
        points = [footprint.to_mm(x, y) for x, y in region.points]
        lines.append(f"{indent(1)}(fp_poly")
        lines.append(f"{indent(2)}(pts")
        for x, y in points:
            lines.append(f"{indent(3)}(xy {n(x)} {n(y)})")
        lines.append(f"{indent(2)})")
        lines.extend(_stroke(2, 0.0))
        # KiCad 10 footprints only accept the enumerated fill form: (fill yes|no).
        filled = str(region.fill).strip().lower() in {"solid", "yes", "true"}
        lines.append(f"{indent(2)}(fill {'yes' if filled else 'no'})")
        lines.append(f"{indent(2)}(layer {q(region.layer)})")
        lines.append(f"{indent(1)})")

    for pad in footprint.pads:
        x, y = footprint.to_mm(pad.x, pad.y)
        shape = pad.kicad_shape()
        pad_number = pad.number or ""
        lines.append(f"{indent(1)}(pad {q(pad_number)} {pad.kind} {shape}")
        rotation = pad.rotation
        lines.append(f"{indent(2)}(at {n(x)} {n(y)} {n(rotation)})"
                     if rotation else f"{indent(2)}(at {n(x)} {n(y)})")
        lines.append(f"{indent(2)}(size {n(pad.width * easyfp.UNIT_MM)} "
                     f"{n(pad.height * easyfp.UNIT_MM)})")
        if pad.plated:
            diameter = min(pad.width, pad.height) * easyfp.UNIT_MM * 0.5
            lines.append(f"{indent(2)}(drill {n(pad.hole * easyfp.UNIT_MM) if pad.hole else n(diameter)})")
        lines.append(f"{indent(2)}(layers {_layers_for(pad.kind, pad.layer)})")
        lines.append(f"{indent(1)})")

    if not footprint.tracks and not footprint.circles:
        warnings.append("the footprint has no silkscreen drawing")
    lines.append(f"{indent(1)}(embedded_fonts no)")
    if model_reference:
        lines.append(f"{indent(1)}(model {q(model_reference)}")
        lines.append(f"{indent(2)}(offset")
        lines.append(f"{indent(3)}(xyz 0 0 0)")
        lines.append(f"{indent(2)})")
        lines.append(f"{indent(2)}(scale")
        lines.append(f"{indent(3)}(xyz 1 1 1)")
        lines.append(f"{indent(2)})")
        lines.append(f"{indent(2)}(rotate")
        lines.append(f"{indent(3)}(xyz 0 0 0)")
        lines.append(f"{indent(2)})")
        lines.append(f"{indent(1)})")
    lines.append(")")
    return "\n".join(lines) + "\n", warnings
