"""Render a `PageModel` to `.kicad_sch` text.

Node order is the corpus order (Â§3 of `format-notes.md`): header, `lib_symbols`, all
symbols, then global labels, then wires, then `sheet_instances`. Labels before wires is
unusual but it is what eeschema writes, and matching it keeps a diff against the reference
pages short.

Every field is placed at a slot the planner reserved, so a symbol's text can never land on
a label: that is gate 3's "by construction" claim made concrete.
"""

from __future__ import annotations

from .. import layout
from ..ids import UuidSource
from ..model import PageModel
from ..schema import PropertyTable
from ..symbols import LibSymbol, database_entry, page_lib_symbols
from . import templates as T

#: pin numbers sort naturally: 1, 2, 10, and A4B9 after the pure numbers
def _pin_sort_key(number: str) -> tuple[int, int, str]:
    return (0, int(number), "") if number.isdigit() else (1, 0, number)


def render_fields(part, cell, uuids: UuidSource) -> str:
    """Instance properties, built by the same validated table as the cache entry.

    A placed part carries the five standard fields and the database columns only — measured
    on a page KiCad re-saved: the cache entry for U3 has 91 properties, its instance 83.
    Only Reference and Value are visible (user rule, 2026-11-26), and everything the planner
    did not place sits at the anchor, which is already on the 50 mil grid.
    """
    x, y = cell.anchor
    table = PropertyTable.build(
        part=part,
        standard_values={
            "Reference": part.ref,
            "Value": part.value,
            "Footprint": part.footprint,
            "Datasheet": "",
            "Description": part.description,
        },
        standard_positions={"Reference": (x, y), "Value": (x, y)},
        use_library_positions=False,
        default_at=(x, y),
        include_derived=False,
        field_positions={
            "Reference": cell.field_slots.get("Reference", (x, y)),
            "Value": cell.field_slots.get("Value", (x, y)),
        },
    )
    table.validate(part, require_grid=True, include_derived=False)
    return table.render(2) + "\n"


def render_symbol_instance(part, cell, model: PageModel, uuids: UuidSource) -> str:
    x, y = cell.anchor
    pins = "".join(
        T.render_pin_ref(number=number, uuid=uuids.next())
        for number in sorted(part.pins, key=_pin_sort_key)
    )
    return T.render_symbol(
        lib_id=part.link_id or part.symbol_id,   # the database link, not the file name
        x=x,
        y=y,
        angle=0,                # every instance in the reference build is unrotated
        uuid=uuids.next(),
        properties=render_fields(part, cell, uuids),
        pins=pins,
        project=model.project or "schwrite",
        path=model.path,
        reference=part.ref,
        fields_autoplaced=True,
    )


def render_page(
    model: PageModel,
    symbols: dict[str, LibSymbol],
    uuids: UuidSource | None = None,
) -> str:
    """The whole page as text, ready to be written once (S8: one write, atomic)."""
    uuids = uuids or UuidSource()
    # One entry per database link, not one per part: ten resistors of the same part number
    # share a single `lib_symbols` child. Emitting one entry per part produced duplicate
    # `lib_symbols` children, and KiCad then reported `lib_symbol_mismatch` once per part.
    entries: list[str] = []
    seen_links: set[str] = set()
    for part in model.parts_in_placement_order():
        link = part.link_id or part.symbol_id
        if link in seen_links:
            continue
        seen_links.add(link)
        entries.append(database_entry(symbols[link], part))
    chunks = [
        T.render_page_header(
            version=T.VERSION_CHILD, sheet_uuid=model.sheet_uuid, paper=model.paper
        ),
        page_lib_symbols(entries),
    ]
    for part in model.parts_in_placement_order():
        chunks.append(render_symbol_instance(part, model.cells[part.ref], model, uuids))
        chunks.append("\n")
    for label in model.labels:
        chunks.append(
            T.render_global_label(
                text=label.text,
                x=label.at[0],
                y=label.at[1],
                angle=label.angle,
                uuid=label.uuid or uuids.next(),
                justify=label.justify,
            )
        )
        chunks.append("\n")
    for wire in model.wires:
        chunks.append(
            T.render_wire(
                x1=wire.start[0],
                y1=wire.start[1],
                x2=wire.end[0],
                y2=wire.end[1],
                uuid=wire.uuid or uuids.next(),
            )
        )
        chunks.append("\n")
    chunks.append(T.render_sheet_instances(page="1"))
    chunks.append(T.PAGE_FOOTER + "\n")
    return "".join(chunks)


def justify_for(angle: int) -> str | None:
    """Global-label justification for a sheet angle, as the corpus writes it (Â§8.2)."""
    return {0: "left", 90: "left", 180: "right", 270: "right"}.get(int(angle) % 360)
