"""Symbol geometry from an EasyEDA symbol document.

Conversion follows LCSC3D's rules (re-implemented, not copied), verified against
symbols that open correctly in KiCad:

* the **pin dot** (segment 1) is the electrical connection point — not the header
  ``x``/``y`` and not the first point of the drawn path, whose direction carries no
  meaning;
* the pin's ``body`` end is the path endpoint farthest from the dot, and the KiCad
  angle comes from ``body - connection``: ``dx > 0`` → 0, ``dx < 0`` → 180, ``dy > 0``
  → 90, ``dy < 0`` → 270 (KiCad's own ``Device:D``: left pin 0, right pin 180);
* stroke width/style come from the record's own fields, not from a constant;
* an ellipse with ``rx != ry`` is tessellated, a circle stays a circle.

**One deliberate improvement over LCSC3D:** the finished symbol is centred on the
origin in both axes (LCSC3D keeps EasyEDA's head origin, which can leave a part
noticeably off-centre in the schematic). The shift is snapped to 1.27 mm so pins stay
on their 100-mil grid.

Units: one canvas unit is 10 mil (0.254 mm); EasyEDA's Y axis grows downwards.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from .document import Record, document, head_of, number, parse_records

UNIT_MM = 0.254
DEFAULT_PIN_LENGTH = 10 * UNIT_MM
DEFAULT_TEXT_SIZE = 1.27
GRID_MM = 1.27

#: EasyEDA stroke style id -> KiCad stroke type.
STYLES = {0: "default", 1: "dash", 2: "dot", 3: "dash_dot"}

#: EasyEDA pin electrical code -> KiCad pin type. EasyEDA's ``power`` is written
#: ``power_in`` because that is the token KiCad accepts.
PIN_TYPES = {
    "0": "unspecified",
    "1": "input",
    "2": "output",
    "3": "bidirectional",
    "4": "power_in",
}

_PATH_TOKEN = re.compile(r"[MmLlHhVvZzAaQqTtCcSs]|-?\d+(?:\.\d+)?")


@dataclass(frozen=True)
class Stroke:
    width: float = UNIT_MM
    style: str = "default"


@dataclass(frozen=True)
class Pin:
    number: str
    name: str
    etype: str
    x: float          # connection point, canvas units
    y: float
    angle: int
    length: float     # millimetres
    visible: bool = True
    name_visible: bool = True
    number_visible: bool = True
    graphic: str = "line"
    name_size: float = DEFAULT_TEXT_SIZE
    number_size: float = DEFAULT_TEXT_SIZE


@dataclass(frozen=True)
class Rect:
    x1: float
    y1: float
    x2: float
    y2: float
    stroke: Stroke = Stroke()


@dataclass(frozen=True)
class Circle:
    cx: float
    cy: float
    radius: float
    rx: float
    ry: float
    stroke: Stroke = Stroke()
    fill: str = "none"


@dataclass(frozen=True)
class Polyline:
    points: tuple[tuple[float, float], ...]
    stroke: Stroke = Stroke()
    fill: str = "none"


@dataclass(frozen=True)
class Text:
    text: str
    x: float
    y: float
    angle: int
    size: float
    justify: str = ""
    visible: bool = True


@dataclass
class Symbol:
    name: str
    prefix: str
    pins: list[Pin] = field(default_factory=list)
    rects: list[Rect] = field(default_factory=list)
    circles: list[Circle] = field(default_factory=list)
    polylines: list[Polyline] = field(default_factory=list)
    texts: list[Text] = field(default_factory=list)
    properties: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    offset: tuple[float, float] = (0.0, 0.0)
    head: tuple[float, float] = (0.0, 0.0)

    def to_mm(self, x: float, y: float) -> tuple[float, float]:
        ox, oy = self.offset
        return ((x - ox) * UNIT_MM, -(y - oy) * UNIT_MM)

    def body_bounds_canvas(self) -> tuple[float, float, float, float] | None:
        """Bounding box of the drawn body, in canvas units."""
        xs: list[float] = []
        ys: list[float] = []
        for rect in self.rects:
            xs.extend((rect.x1, rect.x2))
            ys.extend((rect.y1, rect.y2))
        for circle in self.circles:
            xs.extend((circle.cx - circle.rx, circle.cx + circle.rx))
            ys.extend((circle.cy - circle.ry, circle.cy + circle.ry))
        for poly in self.polylines:
            xs.extend(point[0] for point in poly.points)
            ys.extend(point[1] for point in poly.points)
        if not xs or not ys:
            return None
        return min(xs), min(ys), max(xs), max(ys)

    def bounds_mm(self) -> tuple[float, float, float, float] | None:
        """Everything drawn (body, pins, texts) in millimetres."""
        xs: list[float] = []
        ys: list[float] = []
        for pin in self.pins:
            px, py = self.to_mm(pin.x, pin.y)
            xs.extend((px, px))
            ys.extend((py, py))
        bounds = self.body_bounds_canvas()
        if bounds is not None:
            for x, y in ((bounds[0], bounds[1]), (bounds[2], bounds[3])):
                px, py = self.to_mm(x, y)
                xs.append(px)
                ys.append(py)
        if not xs or not ys:
            return None
        return min(xs), min(ys), max(xs), max(ys)

    def centre_on_origin(self) -> None:
        """Centre the drawn body on (0, 0), keeping pins on the 1.27 mm grid.

        Improvement over LCSC3D, which keeps EasyEDA's head origin. The shift is
        snapped to a whole grid step, so the body may end up within 0.635 mm of dead
        centre but pin coordinates stay on the grid a schematic wants.
        """
        bounds = self.body_bounds_canvas()
        if bounds is None:
            return
        ox, oy = self.offset
        centre_x = ((bounds[0] + bounds[2]) / 2 - ox) * UNIT_MM
        centre_y = -((bounds[1] + bounds[3]) / 2 - oy) * UNIT_MM
        shift_x = -round(centre_x / GRID_MM) * GRID_MM
        shift_y = -round(centre_y / GRID_MM) * GRID_MM
        self.offset = (ox - shift_x / UNIT_MM, oy + shift_y / UNIT_MM)


# --------------------------------------------------------------------------
# path parsing
# --------------------------------------------------------------------------


def path_points(path: str) -> list[tuple[float, float]]:
    """Endpoints of a path, in canvas coordinates (absolute or relative commands)."""
    tokens = _PATH_TOKEN.findall(path or "")
    counts = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7}
    x = y = 0.0
    points: list[tuple[float, float]] = []
    command = ""
    index = 0
    while index < len(tokens):
        if tokens[index].isalpha():
            command = tokens[index]
            index += 1
            continue
        op = command.upper()
        if op == "Z":
            command = ""
            continue
        count = counts.get(op)
        if count is None or index + count > len(tokens):
            break
        values = [float(value) for value in tokens[index:index + count]]
        index += count
        relative = command.islower()
        if op in {"M", "L", "T", "C", "S", "Q"}:
            px, py = values[-2], values[-1]
            x, y = (x + px, y + py) if relative else (px, py)
            points.append((x, y))
        elif op == "A":
            px, py = values[5], values[6]
            x, y = (x + px, y + py) if relative else (px, py)
            points.append((x, y))
        elif op == "H":
            x = x + values[0] if relative else values[0]
            points.append((x, y))
        elif op == "V":
            y = y + values[0] if relative else values[0]
            points.append((x, y))
    return points


def _point_size(text: str, default: float = DEFAULT_TEXT_SIZE) -> float:
    """``'5.8pt'`` -> millimetres."""
    cleaned = str(text or "").removesuffix("pt").strip()
    try:
        return max(0.5, float(cleaned) * 25.4 / 72.0)
    except ValueError:
        return default


def _stroke(width_text: str, style_text: str) -> Stroke:
    try:
        width = float(width_text) if str(width_text).strip() else 1.0
    except ValueError:
        width = 1.0
    try:
        style = STYLES.get(int(float(style_text)), "default")
    except (TypeError, ValueError):
        style = "default"
    return Stroke(width=max(0.0, width) * UNIT_MM, style=style)


def _fill(value: str) -> str:
    """EasyEDA fill -> KiCad fill type (``none`` / ``background`` / ``outline``)."""
    text = str(value or "").strip()
    if not text or text.casefold() == "none":
        return "none"
    colour = text.lstrip("#")
    if len(colour) == 3:
        colour = "".join(char * 2 for char in colour)
    try:
        average = sum(bytes.fromhex(colour)) / 3
    except ValueError:
        return "none"
    return "background" if average >= 192 else "outline"


def _pin_from_record(record: Record) -> Pin | None:
    header = record.segment(0)
    if not header:
        return None
    dot = record.segment(1)
    line = record.segment(2)
    label = record.segment(3)
    designator = record.segment(4)

    endpoints = path_points(line[0] if line else "")
    if len(endpoints) < 2:
        return None
    start, end = endpoints[0], endpoints[-1]
    if start == end:
        return None

    if len(dot) >= 2 and dot[0].strip() and dot[1].strip():
        anchor = (number(dot[0]), number(dot[1]))
    elif len(header) > 5 and header[4].strip() and header[5].strip():
        anchor = (number(header[4]), number(header[5]))
    else:
        return None

    near = min(endpoints, key=lambda point: math.dist(anchor, point))
    if math.dist(anchor, near) > 1e-4:
        # The dot should sit on an endpoint; if it does not, trust the geometry.
        near = start
    far = end if near == start else start

    dx = (far[0] - anchor[0]) * UNIT_MM
    dy = -(far[1] - anchor[1]) * UNIT_MM
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return None
    if abs(dx) > 1e-9 and abs(dy) > 1e-9:
        if abs(dx) >= abs(dy):
            dy = 0.0
        else:
            dx = 0.0
    angle = (0 if dx > 0 else 180) if abs(dx) > 1e-9 else (90 if dy > 0 else 270)

    number_text = designator[4] if len(designator) > 4 else header[3]
    name_text = label[4] if len(label) > 4 else ""
    inverted = bool(record.segment(5)) and record.segment(5)[0].strip() == "1"
    clock = bool(record.segment(6)) and record.segment(6)[0].strip() == "1"
    graphic = ("inverted_clock" if inverted and clock else
               "inverted" if inverted else "clock" if clock else "line")

    return Pin(
        number=str(number_text).strip(),
        name=str(name_text).strip(),
        etype=PIN_TYPES.get(str(header[2]).strip(), "unspecified"),
        x=anchor[0],
        y=anchor[1],
        angle=angle,
        length=abs(dx) + abs(dy),
        visible=len(header) > 1 and header[1].strip() == "show",
        name_visible=bool(label) and label[0].strip() == "1",
        number_visible=bool(designator) and designator[0].strip() == "1",
        graphic=graphic,
        name_size=_point_size(label[7] if len(label) > 7 else ""),
        number_size=_point_size(designator[7] if len(designator) > 7 else ""),
    )


def _ellipse_points(cx: float, cy: float, rx: float, ry: float) -> tuple[tuple[float, float], ...]:
    """Tessellate an ellipse the way LCSC3D does (sagitta-based vertex count)."""
    largest = max(rx, ry, 1e-9)
    sagitta = 0.00127 / UNIT_MM
    try:
        count = max(16, math.ceil(math.pi / math.acos(max(-1.0, 1 - sagitta / largest))))
    except (ValueError, ZeroDivisionError):
        count = 16
    count = min(count, 512)
    return tuple(
        (cx + rx * math.cos(2 * math.pi * index / count),
         cy + ry * math.sin(2 * math.pi * index / count))
        for index in range(count)
    )


def parse_symbol(result: dict) -> Symbol | None:
    """Build the symbol IR, or ``None`` when the part publishes no symbol."""
    records = parse_records(result.get("dataStr"))
    if not records:
        return None
    head = head_of(result.get("dataStr"))
    params = document(head.get("c_para"))

    symbol = Symbol(
        name=str(result.get("title") or params.get("name") or "").strip(),
        prefix=str(params.get("pre") or "U?").strip() or "U?",
        head=(number(head.get("x")), number(head.get("y"))),
    )
    symbol.offset = symbol.head
    for key, value in params.items():
        if isinstance(value, str) and value.strip():
            symbol.properties[str(key)] = value.strip()

    for record in records:
        op = record.op
        if op == "P":
            pin = _pin_from_record(record)
            if pin is not None:
                symbol.pins.append(pin)
        elif op == "R":
            x = number(record.field(1))
            y = number(record.field(2))
            width = number(record.field(5))
            height = number(record.field(6))
            if width and height:
                symbol.rects.append(Rect(
                    x1=x, y1=y, x2=x + width, y2=y + height,
                    stroke=_stroke(record.field(8), record.field(9))))
            else:
                symbol.warnings.append("skipped a rectangle with no size")
        elif op in {"C", "E"}:
            is_circle = op == "C"
            rx = number(record.field(3))
            ry = number(record.field(3) if is_circle else record.field(4))
            stroke_index = 4 if is_circle else 5
            stroke = _stroke(record.field(stroke_index + 1), record.field(stroke_index + 2))
            fill = _fill(record.field(stroke_index + 3))
            cx, cy = number(record.field(1)), number(record.field(2))
            if is_circle or abs(rx - ry) < 1e-9:
                symbol.circles.append(Circle(cx=cx, cy=cy, radius=rx, rx=rx, ry=ry,
                                             stroke=stroke, fill=fill))
            else:
                symbol.warnings.append("an ellipse was tessellated into a polyline")
                symbol.polylines.append(Polyline(points=_ellipse_points(cx, cy, rx, ry),
                                                 stroke=stroke, fill=fill))
        elif op == "T":
            text = record.field(12)
            if text:
                symbol.texts.append(Text(
                    text=text,
                    x=number(record.field(2)),
                    y=number(record.field(3)),
                    angle=round(number(record.field(4)) * 10),
                    size=_point_size(record.field(7)),
                    justify={"start": "left", "end": "right"}.get(record.field(10), ""),
                    visible=record.field(13) != "0",
                ))
        elif op in {"PL", "PG"}:
            coords = [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", record.field(1))]
            points = tuple((coords[i], coords[i + 1]) for i in range(0, len(coords) - 1, 2))
            if len(points) >= 2:
                symbol.polylines.append(Polyline(
                    points=points,
                    stroke=_stroke(record.field(3), record.field(4)),
                    fill=_fill(record.field(5))))
        elif op == "PT":
            # A path of M/L/Z (and sometimes arc) segments; the LED packages draw their
            # triangle and arrows this way, so dropping it leaves a symbol with missing
            # lines.  path_points() understands the whole SVG subset EasyEDA emits.
            points = path_points(record.field(1))
            if len(points) >= 2:
                symbol.polylines.append(Polyline(
                    points=points,
                    stroke=_stroke(record.field(3), record.field(4)),
                    fill=_fill(record.field(5))))
            else:
                symbol.warnings.append("skipped a PT path with fewer than two points")
        elif op == "A":
            # A bare arc record: EasyEDA writes it either as a path string or as
            # start/end/centre fields.  Try the path form first; otherwise report it.
            points = path_points(record.field(1))
            if len(points) >= 2:
                symbol.polylines.append(Polyline(
                    points=points,
                    stroke=_stroke(record.field(3), record.field(4)),
                    fill=_fill(record.field(5))))
            else:
                symbol.warnings.append("skipped symbol drawing op 'A'")
        elif op == "SVGNODE":
            pass
        else:
            symbol.warnings.append(f"skipped unsupported symbol op {op!r}")

    if not symbol.pins:
        symbol.warnings.append("the symbol has no pins")
    symbol.centre_on_origin()
    return symbol


def to_mm(symbol: Symbol, x: float, y: float) -> tuple[float, float]:
    return symbol.to_mm(x, y)
