"""Netlist loading and validation (plan §Appendix A).

The netlist is the design authority: connectivity comes from here, never from a page.
This module does structure and consistency checks only — whether a part exists is the
database's business (`dblib.py`), and whether a pin exists is the symbol's (`symbols.py`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import NetlistError


@dataclass
class Netlist:
    design: str
    subsystem: str
    components: list[dict[str, Any]]
    nets: list[dict[str, Any]]
    source: str = ""
    path: Path | None = None

    # -- derived -----------------------------------------------------------
    def pin_net_map(self) -> dict[str, dict[str, str]]:
        """``{ref: {pin: net}}`` — one pin on one net, or this raises."""
        mapping: dict[str, dict[str, str]] = {}
        for net in self.nets:
            name = str(net["name"])
            for member in net["members"]:
                ref = str(member["ref"])
                pin = str(member["pin"])
                bucket = mapping.setdefault(ref, {})
                existing = bucket.get(pin)
                if existing is not None and existing != name:
                    raise NetlistError(
                        f"{ref} pin {pin} is on two nets ({existing!r} and {name!r}); "
                        f"a pin belongs to exactly one net"
                    )
                bucket[pin] = name
        return mapping

    def net_members(self) -> dict[str, list[tuple[str, str]]]:
        """``{net: [(ref, pin), ...]}`` in netlist order."""
        members: dict[str, list[tuple[str, str]]] = {}
        for net in self.nets:
            name = str(net["name"])
            bucket = members.setdefault(name, [])
            for member in net["members"]:
                bucket.append((str(member["ref"]), str(member["pin"])))
        return members

    def refs(self) -> list[str]:
        return [str(component["ref"]) for component in self.components]


def load(path: str | Path) -> Netlist:
    """Read and validate a netlist file. Raises `NetlistError` with the offending item."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise NetlistError(f"cannot read netlist {path}: {error}") from error
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise NetlistError(f"{path.name}: not valid JSON: {error}") from error
    return parse(data, path=path)


def parse(data: Any, *, path: Path | None = None) -> Netlist:
    where = f"{path.name}: " if path else ""
    if not isinstance(data, dict):
        raise NetlistError(f"{where}netlist must be a JSON object")

    components = data.get("components")
    nets = data.get("nets")
    if not isinstance(components, list) or not components:
        raise NetlistError(f"{where}components must be a non-empty list")
    if not isinstance(nets, list) or not nets:
        raise NetlistError(f"{where}nets must be a non-empty list")

    seen: set[str] = set()
    for component in components:
        if not isinstance(component, dict):
            raise NetlistError(f"{where}component must be an object: {component!r}")
        ref = component.get("ref")
        if not ref:
            raise NetlistError(f"{where}component without ref: {component!r}")
        if ref in seen:
            raise NetlistError(f"{where}duplicate reference {ref}")
        seen.add(ref)
        if not (component.get("lcsc") or component.get("mpn")):
            raise NetlistError(
                f"{where}{ref}: give an lcsc or mpn — a part is identified by a database "
                f"part, never by a library id"
            )
        if component.get("lib_id"):
            raise NetlistError(
                f"{where}{ref}: lib_id {component['lib_id']!r} is not allowed in a netlist; "
                f"the component database decides the symbol"
            )

    for net in nets:
        if not isinstance(net, dict):
            raise NetlistError(f"{where}net must be an object: {net!r}")
        name = net.get("name")
        if not name:
            raise NetlistError(f"{where}net without name: {net!r}")
        members = net.get("members")
        if not isinstance(members, list) or not members:
            raise NetlistError(f"{where}net {name}: members must be a non-empty list")
        for member in members:
            if not isinstance(member, dict):
                raise NetlistError(f"{where}net {name}: member must be an object: {member!r}")
            ref = member.get("ref")
            pin = member.get("pin")
            if ref not in seen:
                raise NetlistError(f"{where}net {name}: unknown component {ref!r}")
            if pin in (None, ""):
                raise NetlistError(f"{where}net {name}: component {ref} has no pin")

    result = Netlist(
        design=str(data.get("design") or ""),
        subsystem=str(data.get("subsystem") or (path.stem if path else "")),
        components=components,
        nets=nets,
        source=str(data.get("source") or ""),
        path=path,
    )
    result.pin_net_map()   # raises on a pin in two nets, at load time not at draw time
    return result
