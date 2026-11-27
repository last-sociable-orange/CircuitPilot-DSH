"""Cell sizing and row packing (§8.3) — the algorithm kept from the 2026-11-25 builder.

The invariant is geometric, not cosmetic: a part gets a cell big enough for its body, the
the symbol graphic plus its Reference/Value text. Columns are packed top-down and
to right on the 2.54 mm grid, so no two cells overlap and no wire can reach another part's
text — which is what lets `lint` assert overlaps *by construction* (§11 gate 3).

Every constant here is measured from the working pages; changing one changes the golden
positions in `tests/test_layout.py` and must be justified against a page.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .model import Cell, Part

GRID = 1.27            # 50 mil: KiCad's schematic grid, and the grid every library pin sits on

#: Sheet geometry lives in `config.py`; re-exported so callers keep one name.
from .config import GRID, PAGE_MARGIN, PAGE_SIZES, PAPER_ORDER, TITLE_BLOCK_MM  # noqa: E402

FIELD_TEXT = 1.27        # 50 mil text, KiCad's default and the grid we place it on
TEXT_GAP = 2.54          # 100 mil between the symbol graphic and its reference/value text
TEXT_ROW = 2.54          # 100 mil between the Reference and Value lines
MIN_GUTTER = 12.7        # 500 mil: the gap between neighbouring parts, both axes
COLUMN_GAP = 12.7        # 500 mil between placement columns
COLUMN_INSET = 12.7      # 500 mil extra to the left of the first column
COLUMN_TOP_INSET = 12.7  # 500 mil extra above the first part of every column
CHAR_WIDTH = 1.0         # mm per glyph, deliberately generous (see §11 limitation D)

#: prefixes that are physically large; placed in the first rows
LARGE_PREFIXES = ("U", "J", "SW", "Q", "L", "Y", "FB", "TP", "F", "D")


def prefix_rank(ref: str) -> tuple[int, str]:
    head = "".join(ch for ch in ref if ch.isalpha())
    return (0 if head in LARGE_PREFIXES else 1, head + ref)


@dataclass
class CellSize:
    """Padding around a symbol anchor, before the anchor is known."""

    left: float
    right: float
    top: float
    bottom: float
    horizontal_labels: bool
    band: float
    text_width: float = 0.0     # width of the Reference/Value block, right of the graphic

    @property
    def width(self) -> float:
        return self.left + self.right

    @property
    def height(self) -> float:
        return self.top + self.bottom


def _ceil(value: float) -> float:
    """Round up to the grid, so cell dimensions are whole grid steps."""
    return -(-value // GRID) * GRID if value > 0 else 0.0


def cell_size(part: Part) -> CellSize:
    """Room one placed part needs: its symbol graphic plus its Reference/Value text.

    No space is reserved for wires or net labels — `schwrite` places parts only. The text
    block sits to the right of the graphic, `TEXT_GAP` (100 mil) away, two rows tall.
    `pin_nets` is accepted for call compatibility and ignored.
    """
    min_x, min_y, max_x, max_y = part.pin_box if part.pins else (0.0, 0.0, 0.0, 0.0)
    text_width = max(len(part.ref), len(part.value)) * CHAR_WIDTH
    half_block = TEXT_ROW / 2 + FIELD_TEXT / 2      # two rows, centred on the symbol

    # every dimension is rounded up to a whole grid step, so a 500 mil gap between cells
    # stays exactly 500 mil after the anchors are snapped
    return CellSize(
        left=_ceil(-min_x),
        right=_ceil(max_x + TEXT_GAP + text_width),
        top=_ceil(max(max_y, half_block)),
        bottom=_ceil(max(-min_y, half_block)),
        horizontal_labels=True,                      # no labels are drawn any more
        band=0.0,
        text_width=text_width,
    )


def _snap(value: float) -> float:
    return round(value / GRID) * GRID


def field_slots(anchor: tuple[float, float], size: CellSize) -> dict[str, tuple[float, float]]:
    """Reference and Value, immediately right of the graphic, 100 mil clear of it.

    Both are centred horizontally on their own text and stacked `TEXT_ROW` apart around the
    symbol's vertical centre, then snapped to the 50 mil grid.
    """
    x, y = anchor
    centre_x = _snap(x + size.right - size.text_width / 2)
    return {
        "Reference": (centre_x, _snap(y - TEXT_ROW / 2)),
        "Value": (centre_x, _snap(y + TEXT_ROW / 2)),
    }


def symbol_extent(part: Part) -> float:
    """The drawn size of a symbol, in mm: its widest pin span, at least one grid step.

    This is what "sort by symbol size" means here — the geometry alone, from the pin table.
    It is *not* the cell: a cell also carries room for the net-name labels and the
    reference/value band, so a small LED with long net names has a big cell and a small
    symbol. Examples from the MCB-01 set: STM32 124.5 mm, CH132B 40.6, TYPE-C 25.4,
    LED 22.9, crystal 15.2, diode 10.2, resistor/capacitor 5.1.
    """
    min_x, min_y, max_x, max_y = part.pin_box
    return max(max_x - min_x, max_y - min_y, GRID)


def part_size(size: CellSize) -> float:
    """How much room a cell claims: its larger dimension, labels and band included."""
    return max(size.width, size.height)


#: A column's pitch is this multiple of the column's widest part.


def plan_layout(
    parts: list[Part],
    *,
    page_size: str = "A4",
    margin: float = PAGE_MARGIN,
) -> tuple[dict[str, Cell], dict]:
    """Column packing (v1.8). Returns `({ref: Cell}, layout_summary)`.

    The rule, in the user's words: sort the parts by size, fill the first column from the
    top-left with the largest that fit, then start the next column spaced from the previous
    one by `COLUMN_PITCH` x that column's widest part, and repeat until every part is placed.

    This replaces the skyline packer. Skyline was better at raw density but it interleaved
    parts unpredictably — passives landed beside and below an IC at whatever gap the profile
    happened to leave. Columns read the way a schematic is read: biggest at the top-left,
    related parts stacked below it, next group to the right.
    """
    width, height = PAGE_SIZES.get(page_size.upper(), PAGE_SIZES["A4"])
    usable_width = width - 2 * margin - COLUMN_INSET
    # the title block owns the bottom-right corner: the drawing band stops above it
    usable_height = height - 2 * margin - TITLE_BLOCK_MM[1] - COLUMN_TOP_INSET

    sizes = {part.ref: cell_size(part) for part in parts}
    # largest first; ties broken by width then by reference so a rebuild is identical
    order = sorted(
        sizes, key=lambda ref: (-part_size(sizes[ref]), -sizes[ref].width, prefix_rank(ref))
    )

    positions: dict[str, tuple[float, float]] = {}
    column_x = 0.0
    columns = 0
    column_starts: list[float] = []
    column_widths: list[float] = []
    while order:
        placed_here: list[str] = []
        column_width = 0.0
        y = 0.0
        remaining: list[str] = []
        for ref in order:
            size = sizes[ref]
            if y + size.height > usable_height + 1e-6:
                remaining.append(ref)                 # no room left in this column
                continue
            positions[ref] = (column_x, y)
            placed_here.append(ref)
            column_width = max(column_width, size.width)
            y += size.height + MIN_GUTTER
        if not placed_here:
            # a single part taller than the band: it gets a column and overflows it
            ref = order[0]
            size = sizes[ref]
            positions[ref] = (column_x, 0.0)
            placed_here = [ref]
            column_width = size.width
            remaining = order[1:]
        columns += 1
        column_starts.append(round(column_x, 3))
        column_widths.append(round(column_width, 3))
        column_x += column_width + COLUMN_GAP       # 500 mil clear of the previous column
        order = remaining

    cells: dict[str, Cell] = {}
    for part in parts:
        size = sizes[part.ref]
        left, top = positions[part.ref]
        anchor = (
            _snap(margin + COLUMN_INSET + left + size.left),
            _snap(margin + COLUMN_TOP_INSET + top + size.top),
        )
        cells[part.ref] = Cell(
            ref=part.ref,
            anchor=anchor,
            left=size.left,
            right=size.right,
            top=size.top,
            bottom=size.bottom,
            horizontal_labels=size.horizontal_labels,
            band=size.band,
            field_slots=field_slots(anchor, size),
        )

    used_width = max(
        (positions[ref][0] + sizes[ref].width for ref in positions), default=0.0
    )
    used_height = max(
        (positions[ref][1] + sizes[ref].height for ref in positions), default=0.0
    )
    content_area = sum(size.width * size.height for size in sizes.values())
    summary = {
        "columns": columns,
        "column_starts": column_starts,
        "column_widths": column_widths,
        "width_mm": round(used_width, 1),
        "height_mm": round(used_height, 1),
        "page": page_size.upper(),
        "usable_mm": [width, height],
        "band_mm": [round(usable_width, 1), round(usable_height, 1)],
        "fits": used_width <= usable_width + 1e-6 and used_height <= usable_height + 1e-6,
        "fill": round(content_area / max(used_width * used_height, 1.0), 3),
    }
    return cells, summary


def smallest_fitting_page(
    parts: list[Part],
    *,
    smallest: str = "A4",
) -> tuple[str, dict] | None:
    """The smallest sheet that holds this page, or None if no sheet does.

    `--paper auto` uses this. It is also what the fit gate names when an explicit paper is
    too small, so the error message can say "needs A3" instead of just "does not fit".
    """
    start = PAPER_ORDER.index(smallest.upper()) if smallest.upper() in PAPER_ORDER else 0
    for paper in PAPER_ORDER[start:]:
        _, summary = plan_layout(parts, page_size=paper)
        if summary["fits"]:
            return paper, summary
    return None
