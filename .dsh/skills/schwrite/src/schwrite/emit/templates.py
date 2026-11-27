"""Frozen node templates for KiCad 10 `.kicad_sch` (SW-PLAN-SCHWRITE-001 Â§9).

Every template below was cut from the 2026-11-25 reference corpus and is graded
against it byte-for-byte by `tests/test_templates.py` â€” if KiCad's writer changes,
that test fails and the template gets re-cut. Nothing here is written from a schema
description.

Indentation convention: a node template *starts at column 0* for its opening paren and
indents its children by two tabs, because in the corpus a top-level node opens at one
tab and its children at two. The page assembler supplies the outer tab. Getting this
wrong is a diff, not a corruption, which is why the golden test exists.

Facts baked in here, learned in M0 (see `docs/format-notes.md`):
  * child pages carry `(version 20260101)`, the root page carries `(version 20260306)`
  * `(generator "eeschema")` and `(generator_version "10.0")` are quoted strings
  * a symbol instance's `(path ...)` is the **parent sheet's** path, not "/"
  * global labels in the corpus carry no `Intersheetrefs` property
  * child pages carry no `embedded_fonts` node
"""

from __future__ import annotations

T1 = "\t"
T2 = "\t\t"
T3 = "\t\t\t"
T4 = "\t\t\t\t"
T5 = "\t\t\t\t\t"

#: KiCad 10 child-page format token, as written by eeschema 10.0 in the corpus.
VERSION_CHILD = 20260306   # what this KiCad writes for a child page; see notes below
#: The root page of the same project was written as 20260306; kept for reference.
VERSION_ROOT = 20260306
GENERATOR = "eeschema"
GENERATOR_VERSION = "10.0"


PAGE_HEADER = (
    "(kicad_sch\n"
    f"{T1}(version {{version}})\n"
    f'{T1}(generator "{GENERATOR}")\n'
    f'{T1}(generator_version "{GENERATOR_VERSION}")\n'
    f'{T1}(uuid "{{sheet_uuid}}")\n'
    f'{T1}(paper "{{paper}}")\n'
)

LIB_SYMBOLS_OPEN = f"{T1}(lib_symbols\n"
LIB_SYMBOLS_CLOSE = f"{T1})\n"

PAGE_FOOTER = ")"


def property_block(
    name: str,
    value: str,
    at: tuple[float, float],
    angle: int = 0,
    *,
    hide_top: bool = False,
    justify: str | None = None,
    show_name: bool = False,
    do_not_autoplace: bool = False,
    level: int = 2,
) -> str:
    """One `(property ...)` node.

    `level` is the indentation of the `(property` line in tabs: 2 for an instance field
    (child of a symbol instance), 3 for a field inside a `lib_symbols` entry.

    **Hide flags live in two places and the corpus mixes them** (M0 finding, see
    `docs/format-notes.md`). Of 266 instance fields across the seven pages:
    `Footprint`/`Datasheet`/`Description` are hidden with a top-level `(hide yes)` only
    in 241 cases, with `(effects ... (hide yes))` only in 23, and are visible in 2;
    `Value` is hidden with `effects`-only in all 57 hidden cases and never top-hidden;
    `Reference` is always visible. KiCad reads either placement as hidden, so we emit one
    canonical shape per field and the golden test compares **semantics**.
    """
    tabs = "\t" * level
    x, y = at
    lines = [f'{tabs}(property "{name}" "{value}"', f"{tabs}\t(at {x:g} {y:g} {angle})"]
    lines.append(f"{tabs}\t(show_name {'yes' if show_name else 'no'})")
    lines.append(f"{tabs}\t(do_not_autoplace {'yes' if do_not_autoplace else 'no'})")
    if hide_top:
        lines.append(f"{tabs}\t(hide yes)")
    lines.append(f"{tabs}\t(effects")
    lines.append(f"{tabs}\t\t(font")
    lines.append(f"{tabs}\t\t\t(size 1.27 1.27)")
    lines.append(f"{tabs}\t\t)")
    if justify:
        lines.append(f"{tabs}\t\t(justify {justify})")
    lines.append(f"{tabs}\t)")
    lines.append(f"{tabs})")
    return "\n".join(lines)


SYMBOL = (
    "(symbol\n"
    f'{T2}(lib_id "{{lib_id}}")\n'
    f"{T2}(at {{x:g}} {{y:g}} {{angle:g}})\n"
    f"{T2}(unit {{unit}})\n"
    f"{T2}(body_style 1)\n"
    f"{T2}(exclude_from_sim no)\n"
    f"{T2}(in_bom yes)\n"
    f"{T2}(on_board yes)\n"
    f"{T2}(in_pos_files yes)\n"
    f"{T2}(dnp no)\n"
    # plain (non-f) fragment: single braces are the {format} placeholder. Writing
    # "{{...}}" here silently emits the literal braces — that bug cost a debugging round.
    "{fields_autoplaced}"
    f'{T2}(uuid "{{uuid}}")\n'
    "{properties}"
    "{pins}"
    f"{T2}(instances\n"
    f'{T3}(project "{{project}}"\n'
    f'{T4}(path "{{path}}"\n'
    f'{T5}(reference "{{reference}}")\n'
    f"{T5}(unit {{unit}})\n"
    f"{T4})\n"
    f"{T3})\n"
    f"{T2})\n"
    f"{T1})"
)

PIN_REF = f'{T2}(pin "{{number}}"\n' f'{T3}(uuid "{{uuid}}")\n' f"{T2})\n"

WIRE = (
    "(wire\n"
    f"{T2}(pts\n"
    f"{T3}(xy {{x1:g}} {{y1:g}}) (xy {{x2:g}} {{y2:g}})\n"
    f"{T2})\n"
    f"{T2}(stroke\n"
    f"{T3}(width 0)\n"
    f"{T3}(type default)\n"
    f"{T2})\n"
    f'{T2}(uuid "{{uuid}}")\n'
    f"{T1})"
)

GLOBAL_LABEL = (
    '(global_label "{text}"\n'
    f"{T2}(at {{x:g}} {{y:g}} {{angle}})\n"
    f"{T2}(effects\n"
    f"{T3}(font\n"
    f"{T4}(size 1.27 1.27)\n"
    f"{T3})\n"
    "{justify}"
    f"{T2})\n"
    f'{T2}(uuid "{{uuid}}")\n'
    f"{T1})"
)

#: The `justify` line inside a global label's effects, or nothing for centred text.
JUSTIFY = f"{T3}(justify {{value}})\n"

SHEET_INSTANCES = f'{T1}(sheet_instances\n' f'{T2}(path "/"\n' f'{T3}(page "{{page}}")\n' f"{T2})\n" f"{T1})\n"


def render_page_header(*, version: int, sheet_uuid: str, paper: str) -> str:
    return PAGE_HEADER.format(version=version, sheet_uuid=sheet_uuid, paper=paper)


def render_symbol(
    *,
    lib_id: str,
    x: float,
    y: float,
    angle: int,
    uuid: str,
    properties: str,
    pins: str,
    project: str,
    path: str,
    reference: str,
    unit: int = 1,
    fields_autoplaced: bool = False,
) -> str:
    return SYMBOL.format(
        lib_id=lib_id,
        x=x,
        y=y,
        angle=angle,
        uuid=uuid,
        properties=properties,
        pins=pins,
        project=project,
        path=path,
        reference=reference,
        unit=unit,
        fields_autoplaced=f"{T2}(fields_autoplaced yes)\n" if fields_autoplaced else "",
    )


def render_pin_ref(*, number: str, uuid: str) -> str:
    return PIN_REF.format(number=number, uuid=uuid)


def render_wire(*, x1: float, y1: float, x2: float, y2: float, uuid: str) -> str:
    return WIRE.format(x1=x1, y1=y1, x2=x2, y2=y2, uuid=uuid)


def render_global_label(*, text: str, x: float, y: float, angle: int, uuid: str, justify: str | None) -> str:
    just = "" if not justify else JUSTIFY.format(value=justify)
    return GLOBAL_LABEL.format(text=text, x=x, y=y, angle=angle, uuid=uuid, justify=just)


def render_sheet_instances(*, page: str = "1") -> str:
    return SHEET_INSTANCES.format(page=page)
