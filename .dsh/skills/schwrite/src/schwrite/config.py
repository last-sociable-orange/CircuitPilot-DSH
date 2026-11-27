"""Drawing-sheet geometry and library layout: the facts that are not algorithm.

Nothing here is a rule about our parts. These are facts about a KiCad sheet and about the
`kicad_lib` directory layout — they belong in one editable place so that a different drawing
sheet, or a project whose libraries live elsewhere, is a config change rather than a code
change.
"""

from __future__ import annotations

from pathlib import Path

# -- drawing sheet ---------------------------------------------------------

#: true paper size in mm, landscape
PAGE_SIZES: dict[str, tuple[float, float]] = {
    "A4": (297.0, 210.0),
    "A3": (420.0, 297.0),
    "A2": (594.0, 420.0),
    "A1": (841.0, 594.0),
    "A0": (1189.0, 841.0),
}

#: smallest first: `--paper auto` walks this list
PAPER_ORDER: tuple[str, ...] = ("A4", "A3", "A2", "A1", "A0")

#: border kept clear on every side, mm
PAGE_MARGIN = 12.7

#: the corner KiCad draws its title block in, mm from the bottom-right corner of the sheet.
#: Measured on a plotted A4/A3 page (~108 x 33 mm) with a margin of safety.
TITLE_BLOCK_MM: tuple[float, float] = (115.0, 40.0)

#: KiCad's schematic grid, and the grid every library pin sits on
GRID = 1.27

# -- library layout (`kicad_lib`) ------------------------------------------

#: Directory holding the staged symbol libraries, relative to the `kicad_lib` root.
SYMBOL_DIR = Path("Symbol")

#: Directory holding the staged footprint libraries, relative to the `kicad_lib` root.
FOOTPRINT_DIR = Path("Footprint")

#: Nickname -> file inside `kicad_lib/Symbol/`. A nickname that is not listed resolves to
#: `Symbol/<nickname>/<symbol>.kicad_sym` (one symbol per file).
SYMBOL_FILES: dict[str, str] = {"Standard": "Standard/Standard.kicad_sym"}

#: Nickname -> directory inside `kicad_lib/Footprint/`.
FOOTPRINT_FILES: dict[str, str] = {
    "Standard": "Standard.pretty",
    "Footprint": "Footprint.pretty",
}

#: What a table entry looks like when the project has none. Descriptions are cosmetic.
SYMBOL_DESCR: dict[str, str] = {
    "Standard": "Standard symbols: passives and discretes",
    "Symbol": "Project symbols, one per file (LCSC parts)",
}
FOOTPRINT_DESCR: dict[str, str] = {
    "Standard": "Standard footprints: chip passives and packages",
    "Footprint": "Project footprints, one per file (LCSC parts)",
}

#: Where the database library definition normally lives, relative to `kicad_lib`.
DBL_DIR = Path(".")
