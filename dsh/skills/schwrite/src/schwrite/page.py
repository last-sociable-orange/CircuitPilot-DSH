"""Build the page model: netlist + parts + layout → everything the page will contain.

M2 covers the skeleton, the symbols and their fields. Wires and global labels are added by
`add_connectivity` in M3; the model is the same object either way, which is what lets `lint`
re-derive every box before a file exists.
"""

from __future__ import annotations

from . import layout
from .context import InstanceContext
from .ids import UuidSource
from .model import Cell, PageModel, Part
from .netlist import Netlist


def build_page_model(
    *,
    netlist: Netlist,
    resolved: list[Part],
    page: str,
    paper: str = "A4",
    context: InstanceContext | None = None,
    sheet_uuid: str | None = None,
    uuids: UuidSource | None = None,
) -> PageModel:
    """Place every part and describe the page. Deterministic for a given input."""
    uuids = uuids or UuidSource()
    pin_nets = netlist.pin_net_map()
    cells, summary = layout.plan_layout(resolved, page_size=paper)
    model = PageModel(
        page=page or netlist.subsystem,
        paper=paper.upper(),
        sheet_uuid=sheet_uuid or uuids.next(),
        project=context.project if context else "",
        path=context.path if context else "/",
        parts=resolved,
        order=[ref for ref in cells],          # dict insertion order is the packing order
        cells=cells,
        nets=netlist.net_members(),
        pin_to_net={
            (ref, pin): net for ref, pins in pin_nets.items() for pin, net in pins.items()
        },
        unconnected=[
            (part.ref, number)
            for part in resolved
            for number in part.pins
            if number not in pin_nets.get(part.ref, {})
        ],
        layout=summary,
    )
    return model


def cell_of(model: PageModel, ref: str) -> Cell:
    try:
        return model.cells[ref]
    except KeyError as error:  # pragma: no cover - defensive
        raise KeyError(f"{ref} was not placed on page {model.page}") from error
