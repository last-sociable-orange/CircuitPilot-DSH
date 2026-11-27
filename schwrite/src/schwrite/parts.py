"""From netlist + database + libraries to `Part` objects â€” the one place they meet.

Three sources decide one placed part, and this module keeps their precedence explicit:

* the **netlist** says which reference exists and which pins are used (Â§Appendix A),
* the **database** decides symbol id, footprint and value (Â§2 â€” the netlist may not),
* the **symbol library** supplies geometry, and must actually own every pin the netlist
  mentions (Â§8.1 step 5; a missing pin is a `PartError`, never a drawn stub).
"""

from __future__ import annotations

from . import sexp
from .dblib import ComponentDb, DbRow
from .errors import PartError
from .model import Part
from .netlist import Netlist
from .symbols import LibSymbol, SymbolLibrary

#: Fields KiCad treats as the standard five. `Value` and `Description` are taken from the
#: database columns of the same name and are emitted first, so they are not repeated.
STANDARD_FIELDS = ("Reference", "Value", "Footprint", "Datasheet", "Description")

#: Properties a library symbol owns and a database refresh must not drop.
LIBRARY_PROPERTIES = ("ki_keywords", "ki_fp_filters")


def database_fields(row: DbRow, db: ComponentDb) -> dict[str, str]:
    """Every field the `.kicad_dbl` declares, in declaration order, values verbatim.

    This is the schema of the database, not a shortlist: KiCad writes the whole row onto a
    symbol placed from a database library (empty strings and `-` included), and a page that
    omits a column silently stops being a database-linked part for that column.
    """
    fields: dict[str, str] = {}
    for name, column in db.field_specs:
        if name in ("Value", "Description"):
            continue                      # carried as standard fields, values below
        fields[name] = row.columns.get(column, "")
    return fields


def resolve_parts(netlist: Netlist, db: ComponentDb, library: SymbolLibrary) -> list[Part]:
    """Resolve every component to a `Part`, failing with all problems at once."""
    pin_nets = netlist.pin_net_map()
    parts: list[Part] = []
    problems: list[str] = []

    for component in netlist.components:
        ref = str(component.get("ref", "?"))
        try:
            row: DbRow = db.resolve_component(component)
            symbol: LibSymbol = library.load(row.symbol)
            used_pins = sorted(pin_nets.get(ref, {}).keys())
            library.check_pins(row.symbol, used_pins)
        except PartError as error:
            problems.append(str(error))
            continue

        parts.append(
            Part(
                ref=ref,
                symbol_id=row.symbol,
                footprint=row.footprint,
                # value, footprint and every field come from the row (Â§2). The netlist
                # carries `value` only as a display hint and is never consulted.
                value=row.value,
                description=_column(row, db, "Description"),
                # The link. KiCad names an item inside a database library "<library>/<key>",
                # so the LIB_ID is "<nickname>:<nickname>/<key>" — verified by ERC: this form
                # resolves every symbol, "<nickname>:<key>" resolves none.
                link_id=f"{db.nickname}:{db.nickname}/{row.key}",
                mpn=row.mpn,
                lcsc=row.lcsc,
                pins=dict(symbol.pins),
                fields=database_fields(row, db),
                library_properties={
                    name: value
                    for name in LIBRARY_PROPERTIES
                    if (value := _library_property(symbol, name))
                },
            )
        )

    if problems:
        raise PartError(
            netlist.subsystem or "netlist",
            "cannot place these components:\n  - " + "\n  - ".join(problems),
        )
    return parts


def _column(row: DbRow, db: ComponentDb, field_name: str) -> str:
    """A field's value, looked up through the database schema rather than by guesswork."""
    for name, column in db.field_specs:
        if name == field_name:
            return row.columns.get(column, "")
    return row.columns.get(field_name, "")


def _library_property(symbol: LibSymbol, name: str) -> str:
    """A property the geometry itself carries (e.g. `ki_keywords`), if any."""
    for child in sexp.parse(symbol.block)[1:]:
        if isinstance(child, list) and sexp.node_name(child) == "property":
            if len(child) > 2 and sexp.unquote(child[1]) == name:
                return sexp.unquote(child[2])
    return ""


def symbols_for(parts: list[Part], library: SymbolLibrary) -> dict[str, LibSymbol]:
    """`{link_id: geometry}` â€” one entry per database-linked symbol the page needs.

    Keyed by link rather than by geometry because that is what KiCad embeds: two resistors
    of different part numbers share `Standard:R` geometry but are two `lib_id`s, and each
    needs its own `lib_symbols` entry under its own database key.
    """
    resolved: dict[str, LibSymbol] = {}
    for part in parts:
        if part.link_id not in resolved:
            resolved[part.link_id] = library.load(part.symbol_id)
    return resolved
