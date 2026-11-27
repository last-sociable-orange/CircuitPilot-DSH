"""Emit a native KiCad 10 symbol library for one part.

Grammar from the installed KiCad 10.0.8 libraries: ``(version 20251024)``, properties
carrying ``(show_name …)``/``(do_not_autoplace …)``, ``(hide yes)`` as a child, and
``(embedded_fonts no)`` at the end of the symbol.

Graphics follow LCSC3D's rules: a rectangle always fills ``background``, another
filled shape picks ``background`` or ``outline`` from its colour brightness, stroke
width and style come from the source record, and an ellipse with unequal radii is a
tessellated polyline rather than a circle.
"""

from __future__ import annotations

from easyeda import symbol as easysym

from kicad.sexpr import (
    GENERATOR,
    GENERATOR_VERSION,
    SYMBOL_VERSION,
    indent,
    n,
    q,
)

#: c_para keys that must not become properties (used for naming instead).
_SKIP_PARAMS = {"name", "pre", "package", "Contributor"}
_RESERVED = {"Reference", "Value", "Footprint", "Datasheet", "SupplierPart",
             "Description", "Source"}


def _effects(level: int, size: float, *, justify: str = "") -> list[str]:
    lines = [f"{indent(level)}(effects"]
    lines.append(f"{indent(level + 1)}(font")
    lines.append(f"{indent(level + 2)}(size {n(max(size, 0.5))} {n(max(size, 0.5))})")
    lines.append(f"{indent(level + 1)})")
    if justify:
        lines.append(f"{indent(level + 1)}(justify {justify})")
    lines.append(f"{indent(level)})")
    return lines


def _pin_label(level: int, size: float, *, visible: bool) -> list[str]:
    """Pin name/number effects.

    Pin effects do not support KiCad's text ``hide`` flag, so a hidden label is written
    with size 0, and the size is clamped to 1.27 mm so labels fit a 100 mil pin pitch —
    both rules are what LCSC3D's writer does.
    """
    effective = min(max(size, 0.0), 1.27) if visible else 0.0
    return [
        f"{indent(level)}(effects",
        f"{indent(level + 1)}(font",
        f"{indent(level + 2)}(size {n(effective)} {n(effective)})",
        f"{indent(level + 1)})",
        f"{indent(level)})",
    ]


def _property(level: int, name: str, value: str, x: float, y: float, *,
              hide: bool = False) -> list[str]:
    lines = [f"{indent(level)}(property {q(name)} {q(value)}"]
    lines.append(f"{indent(level + 1)}(at {n(x)} {n(y)} 0)")
    lines.append(f"{indent(level + 1)}(show_name no)")
    lines.append(f"{indent(level + 1)}(do_not_autoplace no)")
    effects = _effects(level + 1, 1.27)
    if hide:
        effects.insert(-1, f"{indent(level + 2)}(hide yes)")
    lines.extend(effects)
    lines.append(f"{indent(level)})")
    return lines


def _stroke(level: int, stroke: easysym.Stroke) -> list[str]:
    return [
        f"{indent(level)}(stroke",
        f"{indent(level + 1)}(width {n(stroke.width)})",
        f"{indent(level + 1)}(type {stroke.style})",
        f"{indent(level)})",
    ]


def _fill(level: int, kind: str) -> list[str]:
    return [
        f"{indent(level)}(fill",
        f"{indent(level + 1)}(type {kind})",
        f"{indent(level)})",
    ]


def _pin(level: int, pin: easysym.Pin, x: float, y: float) -> list[str]:
    lines = [f"{indent(level)}(pin {pin.etype} {pin.graphic}"]
    lines.append(f"{indent(level + 1)}(at {n(x)} {n(y)} {pin.angle})")
    lines.append(f"{indent(level + 1)}(length {n(pin.length)})")
    if not pin.visible:
        lines.append(f"{indent(level + 1)}(hide yes)")
    lines.append(f"{indent(level + 1)}(name {q(pin.name)}")
    lines.extend(_pin_label(level + 2, pin.name_size, visible=pin.name_visible))
    lines.append(f"{indent(level + 1)})")
    lines.append(f"{indent(level + 1)}(number {q(pin.number)}")
    lines.extend(_pin_label(level + 2, pin.number_size, visible=pin.number_visible))
    lines.append(f"{indent(level + 1)})")
    lines.append(f"{indent(level)})")
    return lines


def write_symbol_library(result: dict, identity, *, datasheet: str = "",
                         footprint_lib: str = "") -> tuple[str | None, list[str]]:
    """Return ``(library text, warnings)``; text is ``None`` when no symbol exists."""
    symbol = easysym.parse_symbol(result)
    if symbol is None or not symbol.pins:
        return None, (symbol.warnings if symbol else ["no symbol data published"])

    warnings = list(symbol.warnings)
    bounds = symbol.bounds_mm() or (0.0, 0.0, 0.0, 0.0)
    top_mm, bottom_mm = bounds[3], bounds[1]

    lines: list[str] = ["(kicad_symbol_lib"]
    lines.append(f"{indent(1)}(version {SYMBOL_VERSION})")
    lines.append(f"{indent(1)}(generator {q(GENERATOR)})")
    lines.append(f"{indent(1)}(generator_version {q(GENERATOR_VERSION)})")
    lines.append(f"{indent(1)}(symbol {q(identity.symbol_name)}")

    if all(not pin.number_visible for pin in symbol.pins):
        lines.append(f"{indent(2)}(pin_numbers")
        lines.append(f"{indent(3)}(hide yes)")
        lines.append(f"{indent(2)})")
    lines.append(f"{indent(2)}(pin_names")
    lines.append(f"{indent(3)}(offset {n(1.016)})")
    if all(not pin.name_visible for pin in symbol.pins):
        lines.append(f"{indent(3)}(hide yes)")
    lines.append(f"{indent(2)})")
    lines.append(f"{indent(2)}(exclude_from_sim no)")
    lines.append(f"{indent(2)}(in_bom yes)")
    lines.append(f"{indent(2)}(on_board yes)")
    lines.append(f"{indent(2)}(in_pos_files yes)")
    lines.append(f"{indent(2)}(duplicate_pin_numbers_are_jumpers no)")

    lines.extend(_property(2, "Reference", symbol.prefix, 0.0, top_mm + 2.54))
    lines.extend(_property(2, "Value", identity.symbol_name, 0.0, bottom_mm - 2.54))
    lines.extend(_property(2, "Footprint", footprint_lib, 0.0, 0.0, hide=True))
    lines.extend(_property(2, "Datasheet", datasheet, 0.0, 0.0, hide=True))
    lines.extend(_property(2, "SupplierPart", identity.part, 0.0, 0.0, hide=True))
    if identity.description:
        lines.extend(_property(2, "Description", identity.description[:240], 0.0, 0.0,
                               hide=True))
    if identity.product_url:
        lines.extend(_property(2, "Source", identity.product_url, 0.0, 0.0, hide=True))
    for key, value in symbol.properties.items():
        if key in _SKIP_PARAMS or key in _RESERVED:
            continue
        lines.extend(_property(2, key, value[:120], 0.0, 0.0, hide=True))

    # Graphics unit.
    lines.append(f"{indent(2)}(symbol {q(identity.symbol_name + '_0_1')}")
    for rect in symbol.rects:
        x1, y1 = symbol.to_mm(rect.x1, rect.y1)
        x2, y2 = symbol.to_mm(rect.x2, rect.y2)
        start = (min(x1, x2), min(y1, y2))
        end = (max(x1, x2), max(y1, y2))
        lines.append(f"{indent(3)}(rectangle")
        lines.append(f"{indent(4)}(start {n(start[0])} {n(start[1])})")
        lines.append(f"{indent(4)}(end {n(end[0])} {n(end[1])})")
        lines.extend(_stroke(4, rect.stroke))
        lines.extend(_fill(4, "background"))
        lines.append(f"{indent(3)})")
    for circle in symbol.circles:
        cx, cy = symbol.to_mm(circle.cx, circle.cy)
        lines.append(f"{indent(3)}(circle")
        lines.append(f"{indent(4)}(center {n(cx)} {n(cy)})")
        lines.append(f"{indent(4)}(radius {n(circle.radius * easysym.UNIT_MM)})")
        lines.extend(_stroke(4, circle.stroke))
        lines.extend(_fill(4, circle.fill))
        lines.append(f"{indent(3)})")
    for poly in symbol.polylines:
        lines.append(f"{indent(3)}(polyline")
        lines.append(f"{indent(4)}(pts")
        for x, y in poly.points:
            px, py = symbol.to_mm(x, y)
            lines.append(f"{indent(5)}(xy {n(px)} {n(py)})")
        lines.append(f"{indent(4)})")
        lines.extend(_stroke(4, poly.stroke))
        lines.extend(_fill(4, poly.fill))
        lines.append(f"{indent(3)})")
    for text in symbol.texts:
        if not text.visible:
            continue
        x, y = symbol.to_mm(text.x, text.y)
        lines.append(f"{indent(3)}(text {q(text.text)}")
        lines.append(f"{indent(4)}(at {n(x)} {n(y)} {text.angle})")
        lines.extend(_effects(4, text.size, justify=text.justify))
        lines.append(f"{indent(3)})")
    lines.append(f"{indent(2)})")

    # Pin unit.
    lines.append(f"{indent(2)}(symbol {q(identity.symbol_name + '_1_1')}")
    seen: set[str] = set()
    for pin in symbol.pins:
        if pin.number in seen:
            warnings.append(f"duplicate pin number {pin.number} kept as-is")
        seen.add(pin.number)
        x, y = symbol.to_mm(pin.x, pin.y)
        lines.extend(_pin(3, pin, x, y))
    lines.append(f"{indent(2)})")

    lines.append(f"{indent(2)}(embedded_fonts no)")
    lines.append(f"{indent(1)})")
    lines.append(")")
    return "\n".join(lines) + "\n", warnings
