"""The page model: the single source of truth for emit, lint and the report (Â§7).

Everything is a plain dataclass. `PageModel` is what `page.py` builds, what `emit`
renders, and what `lint` can re-derive every box from before a file exists â€” which is why
it holds geometry (cells, wires, labels) rather than the netlist it came from.
"""

from __future__ import annotations

from dataclasses import dataclass, field

Point = tuple[float, float]


@dataclass(frozen=True)
class Pin:
    """One symbol pin, in symbol coordinates (y up, KiCad convention)."""

    number: str
    name: str
    etype: str          # power_in, passive, bidirectional, ...
    x: float
    y: float
    angle: int          # 0/90/180/270; points from the connection point toward the body
    length: float

    @property
    def outward_angle(self) -> int:
        """Sheet direction a label leaves along, symbol frame (before instance rotation)."""
        return (self.angle + 180) % 360


@dataclass(frozen=True)
class Part:
    """A resolved component: the database row it links to, its geometry and its fields.

    `link_id` is the *link*: `<database library nickname>:<row key>`, the same form KiCad
    writes when a symbol is placed from a database library. `symbol_id` is only where the
    geometry comes from, and is never written to the page.
    """

    ref: str
    symbol_id: str                  # geometry source: "Symbol:IC_CH132B" | "Standard:R"
    footprint: str                  # "Footprint:IC_CH132B" | "Standard:R_0402"
    value: str
    description: str = ""
    link_id: str = ""               # "components:Ceramic Capacitors/TCC0805X5R106K250FT"
    mpn: str = ""
    lcsc: str = ""
    pins: dict[str, Pin] = field(default_factory=dict)
    #: every declared database field except Value/Description, in declaration order,
    #: empty values included â€” this is what KiCad writes on a database-linked symbol
    fields: dict[str, str] = field(default_factory=dict)
    #: library-owned properties the geometry keeps (`ki_keywords`, `ki_fp_filters`)
    library_properties: dict[str, str] = field(default_factory=dict)

    @property
    def prefix(self) -> str:
        return "".join(ch for ch in self.ref if ch.isalpha())

    @property
    def pin_box(self) -> tuple[float, float, float, float]:
        """(min_x, min_y, max_x, max_y) over pin connection points, symbol frame."""
        if not self.pins:
            return (0.0, 0.0, 0.0, 0.0)
        xs = [p.x for p in self.pins.values()]
        ys = [p.y for p in self.pins.values()]
        return (min(xs), min(ys), max(xs), max(ys))


@dataclass
class Cell:
    """Placement result for one part: where it sits and how much room it claimed."""

    ref: str
    anchor: Point                       # sheet mm, grid-snapped
    left: float
    right: float
    top: float
    bottom: float
    horizontal_labels: bool
    band: float
    field_slots: dict[str, Point] = field(default_factory=dict)   # "Reference"/"Value"

    @property
    def width(self) -> float:
        return self.left + self.right

    @property
    def height(self) -> float:
        return self.top + self.bottom

    @property
    def box(self) -> tuple[float, float, float, float]:
        """(x_min, y_min, x_max, y_max) in sheet mm, y down."""
        x, y = self.anchor
        return (x - self.left, y - self.top, x + self.right, y + self.bottom)


@dataclass(frozen=True)
class Wire:
    start: Point
    end: Point
    uuid: str = ""

    @property
    def box(self) -> tuple[float, float, float, float]:
        (x1, y1), (x2, y2) = self.start, self.end
        return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))


@dataclass(frozen=True)
class Label:
    text: str
    at: Point
    angle: int
    justify: str | None = None
    uuid: str = ""


@dataclass
class PageModel:
    """Every node the page will contain, plus the bookkeeping the report needs."""

    page: str                       # subsystem name, e.g. "MCU"
    paper: str                      # "A2"
    sheet_uuid: str
    project: str
    path: str                       # instance path "/<root-uuid>/<sheet-uuid>" or "/"
    parts: list[Part] = field(default_factory=list)
    order: list[str] = field(default_factory=list)      # refs in placement (packing) order
    cells: dict[str, Cell] = field(default_factory=dict)
    nets: dict[str, list[tuple[str, str]]] = field(default_factory=dict)   # net -> [(ref, pin)]
    pin_to_net: dict[tuple[str, str], str] = field(default_factory=dict)
    wires: list[Wire] = field(default_factory=list)
    labels: list[Label] = field(default_factory=list)
    unconnected: list[tuple[str, str]] = field(default_factory=list)
    layout: dict = field(default_factory=dict)

    def part(self, ref: str) -> Part:
        for part in self.parts:
            if part.ref == ref:
                return part
        raise KeyError(ref)

    def parts_in_placement_order(self) -> list[Part]:
        by_ref = {part.ref: part for part in self.parts}
        return [by_ref[ref] for ref in self.order]
