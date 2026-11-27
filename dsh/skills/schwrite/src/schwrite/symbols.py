"""Symbol library reading: pin geometry and the `lib_symbols` block (Â§8.1, Â§8.2).

Two jobs, both text-faithful:

1. **Read** a `.kicad_sym` file and pull one symbol out of it â€” its pins, in symbol
   coordinates, paired *by block* (a pin's number comes from the same `(pin â€¦)` node as its
   position, never from a second parallel scan; that pairing bug is what the old regex
   zip got wrong).
2. **Embed** that symbol into a page: copy the raw text block, rewrite the name to
   `<nickname>:<name>`, and indent it by two tabs. M0 verified that this is *all* KiCad
   keeps â€” a page's `lib_symbols` entry equals the library symbol except for the name
   (`docs/format-notes.md` Â§6), so the copy is byte-faithful and survives format drift
   better than a re-serialisation would.

Nothing here draws anything; the page builder asks for pins and a block.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from . import sexp
from .emit import templates as T
from .errors import PartError
from .model import Part, Pin
from .schema import PropertyTable

#: A page's `lib_symbols` children sit at two tabs (verified against the corpus, Â§6).
PAGE_INDENT = 2


@dataclass(frozen=True)
class LibSymbol:
    """One library symbol: its identity, its raw block and its pin table."""

    lib_id: str                 # "Symbol:IC_CH132B"
    name: str                   # "IC_CH132B"
    path: Path
    block: str                  # raw text, starting at the node's own "("
    indent: int                 # how many tabs the node sat at in its file (1 in a library)
    pins: dict[str, Pin]

    def page_block(self) -> str:
        """The block as a `lib_symbols` child: name prefixed, re-indented to two tabs.

        Re-indenting is relative, not additive: a library symbol sits at one tab with its
        children at two, a page's `lib_symbols` child sits at two with its children at
        three. Adding a constant instead would double the depth on the first line only,
        which is exactly the sort of drift the golden test then has to explain.
        """
        renamed = self.block.replace(f'(symbol "{self.name}"', f'(symbol "{self.lib_id}"', 1)
        out: list[str] = []
        for index, line in enumerate(renamed.splitlines()):
            depth = len(line) - len(line.lstrip("\t"))
            if index == 0:
                depth = self.indent
            out.append("\t" * (depth - self.indent + PAGE_INDENT) + line.lstrip("\t"))
        return "\n".join(out)


def _find_symbol_text(text: str, name: str) -> tuple[str, int] | None:
    """`(raw_text, indent)` of the top-level `(symbol "<name>" â€¦)` node.

    `indent` is how many tabs preceded the node's own paren in the source, which is what
    lets `page_block` re-indent by *difference* rather than by a constant.
    """
    needle = f'(symbol "{name}"'
    start = text.find(needle)
    if start < 0:
        return None
    line_start = text.rfind("\n", 0, start) + 1
    prefix = text[line_start:start]
    indent = len(prefix) if prefix.strip() == "" and set(prefix) <= {"\t"} else 0
    depth = 0
    in_string = False
    i = start
    while i < len(text):
        ch = text[i]
        if in_string:
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return text[start : i + 1], indent
        i += 1
    return None


def _num(value) -> float:
    return float(sexp.unquote(value))


def parse_pins(block: str, *, where: str = "symbol") -> dict[str, Pin]:
    """Pin table, pairing each `(number â€¦)` with the `(pin â€¦)` block that contains it.

    A symbol's pins live inside its sub-symbols (`<name>_<unit>_<body_style>`), which is why
    this walks the tree instead of scanning text: the number, the name and the `(at â€¦)`
    must come from one node or the geometry is silently wrong for string pin numbers
    (`A4B9`) and multi-row parts.
    """
    tree = sexp.parse(block)
    pins: dict[str, Pin] = {}
    for sub in tree[1:]:
        if not isinstance(sub, list) or sexp.node_name(sub) != "symbol":
            continue
        for node in sub[1:]:
            if not isinstance(node, list) or sexp.node_name(node) != "pin":
                continue
            at = next((c for c in node if isinstance(c, list) and sexp.node_name(c) == "at"), None)
            if at is None:
                continue
            length = next(
                (c for c in node if isinstance(c, list) and sexp.node_name(c) == "length"), None
            )
            name_node = next(
                (c for c in node if isinstance(c, list) and sexp.node_name(c) == "name"), None
            )
            number_node = next(
                (c for c in node if isinstance(c, list) and sexp.node_name(c) == "number"), None
            )
            if number_node is None:
                continue
            number = str(sexp.unquote(number_node[1]))
            etype = str(sexp.unquote(node[1])) if len(node) > 1 else ""
            pins[number] = Pin(
                number=number,
                name=str(sexp.unquote(name_node[1])) if name_node is not None else "",
                etype=etype,
                x=_num(at[1]),
                y=_num(at[2]),
                angle=int(round(_num(at[3]))) % 360 if len(at) > 3 else 0,
                length=_num(length[1]) if length is not None else 0.0,
            )
    if not pins:
        raise PartError(where, "symbol has no pins in its (pin â€¦) blocks â€” unreadable library")
    return pins


class SymbolLibrary:
    """Reads `<libs>/Symbol/*` and caches every symbol by file mtime (Â§8.1 step 4).

    `libs_root` is the project's `kicad_lib` directory; `Standard:x` resolves to
    `Symbol/Standard/Standard.kicad_sym` and `Nick:x` to `Symbol/Nick/x.kicad_sym`.
    """

    def __init__(self, libs_root: str | Path) -> None:
        self.root = Path(libs_root)
        self._cache: dict[tuple[str, float], LibSymbol] = {}

    # -- resolution ---------------------------------------------------------
    def symbol_path(self, lib_id: str) -> Path:
        nickname, _, name = str(lib_id).partition(":")
        if not name:
            raise PartError(lib_id, "lib_id must be 'Library:Symbol'")
        if nickname == "Standard":
            return self.root / "Symbol" / "Standard" / "Standard.kicad_sym"
        return self.root / "Symbol" / nickname / f"{name}.kicad_sym"

    def load(self, lib_id: str) -> LibSymbol:
        """Load one symbol, or raise `PartError` naming the file that was missing."""
        nickname, _, name = str(lib_id).partition(":")
        path = self.symbol_path(lib_id)
        if not path.is_file():
            raise PartError(
                lib_id,
                f"symbol library file not found: {path} â€” the part must be staged into "
                f"kicad_lib/Symbol before a page can use it",
            )
        mtime = path.stat().st_mtime
        key = (lib_id, mtime)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        text = path.read_text(encoding="utf-8")
        found = _find_symbol_text(text, name)
        if found is None:
            raise PartError(
                lib_id,
                f"symbol {name!r} is not in {path.name} â€” the database points at a symbol "
                f"that the library does not define",
            )
        block, indent = found
        symbol = LibSymbol(
            lib_id=lib_id,
            name=name,
            path=path,
            block=block,
            indent=indent,
            pins=parse_pins(block, where=lib_id),
        )
        self._cache[key] = symbol
        return symbol

    # -- validation ---------------------------------------------------------
    def check_pins(self, lib_id: str, wanted: list[str]) -> None:
        """Every pin the netlist names must exist on the symbol (Â§8.1 step 5)."""
        symbol = self.load(lib_id)
        missing = [pin for pin in wanted if pin not in symbol.pins]
        if missing:
            raise PartError(
                lib_id,
                f"netlist uses pin(s) {', '.join(sorted(missing))} that {lib_id} does not "
                f"have (it has: {', '.join(sorted(symbol.pins))})",
            )


def page_lib_symbols(entries: list[str]) -> str:
    """The whole `lib_symbols` block for a page, corpus indentation included."""
    body = "\n".join(entries)
    return f"\t(lib_symbols\n{body}\n\t)\n"


# -- database-linked entries -------------------------------------------------
def _children(block: str) -> list[tuple[str, str]]:
    """`(name, raw_text)` for each direct child of a symbol block."""
    return [(name, block[start:end]) for name, start, end in sexp.iter_top_level(block)]


def _reindent(raw: str, level: int) -> str:
    """Shift a node that was sliced at column 0 down to `level` tabs."""
    prefix = "\t" * level
    out = []
    for line in raw.splitlines():
        if not line.strip():
            out.append(line)
            continue
        out.append(prefix + line)
    return "\n".join(out)


def _property_at(block: str, name: str) -> tuple[float, float] | None:
    """Where the library puts a property, so the page keeps the library's own layout."""
    for child_name, raw in _children(block):
        if child_name != "property":
            continue
        node = sexp.parse(raw)
        if len(node) > 2 and sexp.unquote(node[1]) == name:
            at = next(
                (c for c in node if isinstance(c, list) and sexp.node_name(c) == "at"), None
            )
            if at is not None and len(at) > 2:
                return (float(sexp.unquote(at[1])), float(sexp.unquote(at[2])))
    return None


def _property_value(block: str, name: str) -> str:
    for child_name, raw in _children(block):
        if child_name != "property":
            continue
        node = sexp.parse(raw)
        if len(node) > 2 and sexp.unquote(node[1]) == name:
            return sexp.unquote(node[2])
    return ""



def _normalise(raw: str) -> list[str]:
    """Re-indent one sliced child so it sits one tab under its parent.

    Slices keep the absolute indentation of the library file; pasting them under a new
    parent without this leaves grandchildren at six tabs.
    """
    lines = raw.splitlines()
    if len(lines) == 1:
        return [lines[0].strip()]
    body = [line for line in lines[1:] if line.strip()]
    indent = min(len(line) - len(line.lstrip("\t")) for line in body) if body else 0
    out = [lines[0].strip()]
    for line in lines[1:]:
        out.append("" if not line.strip() else "\t" + line[indent:])
    return out


#: `(justify …)` per library property name, filled in by `_library_properties`. The cached
#: copy keeps it: the capacitor the user refreshed carries `(justify left)` on Reference and
#: Value, and dropping it is one of the two differences that remained.
JUSTIFY: dict[str, str] = {}   # legacy map, kept for the old call sites

#: The five properties KiCad treats specially; their values come from the database row.
STANDARD_PROPERTY_NAMES = ("Reference", "Value", "Footprint", "Datasheet", "Description")


def _property_justify(raw: str) -> str | None:
    """The `(justify …)` a library property carries, if any."""
    match = re.search(r"\(justify ([a-z ]+)\)", raw)
    return match.group(1).strip() if match else None


def _library_properties(block: str) -> list[tuple[str, str, tuple[float, float], str | None]]:
    """Every `(name, value, at)` of a library symbol, in the file's own order.

    KiCad keeps them all in the cached copy — including the LCSC extras an EasyEDA import
    leaves behind (`SupplierPart`, `Source`, `Contributor`, `Manufacturer Part`, …) at the
    position the library gave them. Dropping them is what made the cache differ from the
    library for the one symbol that has them.
    """
    found: list[tuple[str, str, tuple[float, float], str | None]] = []
    JUSTIFY.clear()
    for child, raw in _children(block):
        if child != "property":
            continue
        node = sexp.parse(raw)
        if len(node) < 3:
            continue
        name = sexp.unquote(node[1])
        value = sexp.unquote(node[2])
        at = (0.0, 0.0)
        for part in node[3:]:
            if isinstance(part, list) and sexp.node_name(part) == "at" and len(part) > 2:
                at = (float(part[1]), float(part[2]))
                break
        found.append((name, value, at, _property_justify(raw)))
        justify = _property_justify(raw)
        if justify:
            JUSTIFY[name] = justify
    return found


def database_entry(lib: LibSymbol, part: Part) -> str:
    """The `lib_symbols` entry for a **database-linked** symbol, as KiCad writes it.

    KiCad does not embed the library symbol unchanged when a part comes from a database
    library. It:

    * names the entry `<database nickname>:<row key>` â€” the link itself;
    * renames the sub-symbols to `<row key>_<unit>_<body style>`;
    * keeps the geometry and the library header nodes (`pin_names`, `in_bom`, â€¦);
    * replaces the properties with the **whole database row**: the standard five first
      (Reference keeps the library's prefix, Value/Footprint/Datasheet/Description come
      from the row), then every declared field, then the library's own `ki_*` properties.

    Verified against `C59` in `Design/Sync.kicad_sch`, which the user placed from the
    database library with KiCad itself.
    """
    base = PAGE_INDENT + 1                       # children of a lib_symbols entry
    indent = "\t" * PAGE_INDENT
    children = _children(lib.block)
    header = [raw for name, raw in children
              if name not in ("property", "symbol", "embedded_fonts")]
    # KiCad writes `embedded_fonts` *after* the sub-symbols, not up with the header flags;
    # leaving it in the header is one of the two things that made ERC report
    # lib_symbol_mismatch for every part (the other is the property flag order).
    trailing = [raw for name, raw in children if name == "embedded_fonts"]
    subs = [raw for name, raw in children if name == "symbol"]

    key = part.link_id.split(":", 1)[1]
    lib_props = _library_properties(lib.block)
    table = PropertyTable.build(
        part=part,
        library_properties=lib_props,
        standard_values={
            "Reference": _property_value(lib.block, "Reference") or part.prefix,
            "Value": part.value,
            "Footprint": part.footprint,
            "Datasheet": "",
            "Description": part.description,
        },
        standard_positions={name: at for name, _, at, _ in lib_props},
    )
    table.validate(part)          # a cache entry may not lose a field

    lines = [f'{indent}(symbol "{part.link_id}"']
    for raw in header:
        lines.extend(_reindent(line, base) for line in _normalise(raw))
    lines.extend(table.render(base).splitlines())

    for raw in subs:
        renamed = raw.replace(f'(symbol "{lib.name}_', f'(symbol "{key}_', 1)
        lines.append(_reindent(renamed, base))
    for raw in trailing:
        lines.extend(_reindent(line, base) for line in _normalise(raw))
    lines.append("\t" * PAGE_INDENT + ")")
    return "\n".join(lines)
