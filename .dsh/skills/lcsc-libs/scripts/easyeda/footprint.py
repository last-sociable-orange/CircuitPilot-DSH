"""Footprint geometry from an EasyEDA package document.

Units are canvas units (10 mil). The footprint is translated so the centre of the pad
bounding box sits on the origin, which is KiCad's convention.

Two EasyEDA details are recorded as assumptions because the data does not state them
and only a visual check in KiCad can settle them:

* layer ids ``100`` and ``101`` carry manufacturing/assembly drawing. They are mapped
  to ``F.Fab`` so they never pollute the silkscreen.
* ``CIRCLE`` radius/width are taken as millimetres already: a 0.1181 value sitting
  next to a 0.6-unit track width cannot both be canvas units.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .document import Record, numbers, parse_records

UNIT_MM = 0.254

#: EasyEDA footprint layer id -> KiCad layer. Mirrors LCSC3D's map, including its
#: ordering: 5/6 are **paste**, 7/8 are **mask**, 99 is component shape (Dwgs.User),
#: 100/101 are component shape/mark (F.Fab).
LAYERS = {
    "1": "F.Cu",
    "2": "B.Cu",
    "3": "F.SilkS",
    "4": "B.SilkS",
    "5": "F.Paste",
    "6": "B.Paste",
    "7": "F.Mask",
    "8": "B.Mask",
    "10": "Edge.Cuts",
    "12": "Dwgs.User",
    "13": "F.Fab",
    "14": "B.Fab",
    "15": "Dwgs.User",
    "99": "Dwgs.User",
    "100": "F.Fab",
    "101": "F.Fab",
}


@dataclass(frozen=True)
class Pad:
    number: str
    shape: str
    x: float
    y: float
    width: float
    height: float
    rotation: float
    layer: str
    hole: float
    points: tuple[tuple[float, float], ...] = ()

    @property
    def plated(self) -> bool:
        return self.hole > 0

    @property
    def kind(self) -> str:
        return "thru_hole" if self.plated else "smd"

    def kicad_shape(self) -> str:
        shape = self.shape.upper()
        if shape in {"ELLIPSE", "OVAL", "CIRCLE"}:
            return "circle" if abs(self.width - self.height) < 1e-6 else "oval"
        if shape == "POLYGON":
            return "custom"
        return "rect"


@dataclass(frozen=True)
class Track:
    width: float
    layer: str
    points: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class Circle:
    cx: float
    cy: float
    radius_mm: float
    width_mm: float
    layer: str


@dataclass(frozen=True)
class Region:
    layer: str
    points: tuple[tuple[float, float], ...]
    fill: str = "solid"


@dataclass
class Footprint:
    name: str
    pads: list[Pad] = field(default_factory=list)
    tracks: list[Track] = field(default_factory=list)
    circles: list[Circle] = field(default_factory=list)
    regions: list[Region] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    offset: tuple[float, float] = (0.0, 0.0)

    def bounds(self) -> tuple[float, float, float, float] | None:
        """Pad bounding box in canvas units."""
        if not self.pads:
            return None
        left = min(pad.x - pad.width / 2 for pad in self.pads)
        right = max(pad.x + pad.width / 2 for pad in self.pads)
        top = min(pad.y - pad.height / 2 for pad in self.pads)
        bottom = max(pad.y + pad.height / 2 for pad in self.pads)
        return left, top, right, bottom

    def to_mm(self, x: float, y: float) -> tuple[float, float]:
        ox, oy = self.offset
        return ((x - ox) * UNIT_MM, -(y - oy) * UNIT_MM)

    def pad_centres_mm(self) -> list[tuple[str, float, float, float, float, float]]:
        return [
            (pad.number, *self.to_mm(pad.x, pad.y), pad.width * UNIT_MM,
             pad.height * UNIT_MM, pad.rotation)
            for pad in self.pads
        ]


def _num(record: Record, index: int) -> float:
    try:
        return float(record.field(index))
    except (TypeError, ValueError):
        return 0.0


def _pairs(text: str) -> tuple[tuple[float, float], ...]:
    values = numbers(text)
    return tuple((values[i], values[i + 1]) for i in range(0, len(values) - 1, 2))


def parse_footprint(result: dict) -> Footprint | None:
    package = result.get("packageDetail") or {}
    records = parse_records(package.get("dataStr"))
    if not records:
        return None
    footprint = Footprint(name=str(package.get("title") or "").strip())

    for record in records:
        op = record.op
        if op == "PAD":
            number = record.field(8).strip()
            layer_id = record.field(6).strip()
            layer = LAYERS.get(layer_id)
            if layer not in {"F.Cu", "B.Cu"}:
                layer = "F.Cu"
                if layer_id:
                    footprint.warnings.append(
                        f"pad {number or '(unnumbered)'} had layer id {layer_id}, used F.Cu")
            footprint.pads.append(Pad(
                number=number,
                shape=record.field(1, "RECT").upper(),
                x=_num(record, 2),
                y=_num(record, 3),
                width=_num(record, 4),
                height=_num(record, 5),
                rotation=_num(record, 11),
                layer=layer,
                hole=_num(record, 9),
                points=_pairs(record.field(10)),
            ))
        elif op == "TRACK":
            points = _pairs(record.field(4))
            if len(points) >= 2:
                footprint.tracks.append(Track(
                    width=_num(record, 1) * UNIT_MM,
                    layer=LAYERS.get(record.field(2).strip(), "F.SilkS"),
                    points=points,
                ))
        elif op == "CIRCLE":
            footprint.circles.append(Circle(
                cx=_num(record, 1),
                cy=_num(record, 2),
                radius_mm=_num(record, 3),
                width_mm=_num(record, 4) or 0.15,
                layer=LAYERS.get(record.field(5).strip(), "F.Fab"),
            ))
        elif op == "SOLIDREGION":
            points = _pairs(record.field(3))
            if len(points) >= 3:
                footprint.regions.append(Region(
                    layer=LAYERS.get(record.field(1).strip(), "F.Fab"),
                    points=points,
                    fill=record.field(4) or "solid",
                ))
        elif op in {"RECT", "ARC", "SVGNODE"}:
            # RECT/ARC are rare decorations with unverified field layouts; SVGNODE is
            # the 3D reference and is handled by easyeda.model3d.
            continue
        else:
            footprint.warnings.append(f"skipped unsupported footprint op {op!r}")

    if not footprint.pads:
        footprint.warnings.append("the footprint has no pads")
    bounds = footprint.bounds()
    if bounds is not None:
        footprint.offset = ((bounds[0] + bounds[2]) / 2.0, (bounds[1] + bounds[3]) / 2.0)
    return footprint


def distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])
