# Changelog

## 1.0.2 — standalone skill, no dependencies

The `schwrite` skill folder now carries the code, so it works when copied anywhere: `run.py`
launches the package from `src/`, and the one third-party module it used (an S-expression
reader) is vendored. `python run.py --help` works with `-S`, i.e. with no site-packages at all.

`tools/sync_skill.py` regenerates the copy and writes a manifest (version, source commit,
sha256 per file); `--check` proves it is current, and the test suite runs that check so the
copy cannot rot.

Fixed: ERC in a folder with no `.kicad_pro` reported `lib_symbol_issues` for every symbol —
the scratch project is now always written (an empty one is enough), so a page dropped in a
bare directory still gets a page-scoped verdict.

The project itself is now stdlib-only: `dependencies = []`, sexpdata vendored under
`src/schwrite/_vendor/` with its licence.


## 1.0.1 — page-scoped ERC

`schwrite erc` judges **the page under review**, not the project. It runs ERC on the file that
was named; only when KiCad cannot resolve the libraries (it matches project to page by
basename, so a child page in a differently named project resolves nothing) does it retry the
same page in a scratch project carrying the project's tables with absolute URIs. Either way the
report holds this page's violations and nothing else: no `duplicate_sheet_names` from the
parent page, no other sheet's pins. The expected classes shrink to the three pin classes, and
`--json` gained `checked` and `mode` so the caller can see what ran and how.

Also fixed, found while testing the above: `libtables` declared a **directory-shaped** symbol
library (`Symbol`, one file per part) as a single file, so every part but the first failed to
resolve. It now declares the directory, which is what the project's own table always said.

Per-page counts on MCB-01: MCU 162+4, Power 127, USB 72+4, Channel_1-4 100, Channel_5-8 100,
Sync 38, Indicator 97 — the same numbers the old project-wide run used to report per sheet,
now without the project-wide noise.


## 1.0.0 — phase 1 product

Placement-only schematic generation, with two verification gates.

### Commands

- `schwrite build` — netlist JSON → KiCad page. Resolves every reference against
  `components.db`, embeds one `lib_symbols` entry per database link, writes the whole database
  row as fields in KiCad's own order, places Reference and Value beside the graphic, and packs
  parts in columns on a 50 mil grid with 500 mil gaps. Writes atomically; refuses a page that
  does not fit the requested sheet.
- `schwrite verify` — gate S3. Runs `kicad-cli sch export netlist` on the page and compares
  every reference, value and footprint with the netlist. Exit 6 on any difference.
- `schwrite erc` — gate S4. Runs ERC through the project root (a child page cannot resolve
  libraries on its own) and fails on any violation class that means the page is wrong. The
  classes phase 1 is expected to report — `pin_not_connected`, `pin_not_driven`,
  `duplicate_sheet_names`, … — are named in the source, not tolerated by accident.

### What a page contains

- one `lib_symbols` child per database link (not per part), byte-identical to the form KiCad
  writes when it resolves a database symbol itself;
- Reference and Value visible, every other field hidden;
- no wires, no net labels, no space reserved for them.

### Measured on the seven MCB-01 pages

```
verify : 196 components read back, all correct
erc    : duplicate_sheet_names 3 · pin_not_connected 696 · pin_not_driven 8
         lib_symbol_mismatch 0 · footprint_link_issues 0
```

### Packaging

- runtime dependency reduced to `sexpdata` (the unused `kicad-skip` pin is gone);
- `uv.lock` committed, so `uv sync` is reproducible;
- console script `schwrite` via `[project.scripts]`.

### Known limitations

- placement only, by design: pages are inputs to wiring, not finished schematics;
- `pages` (batch build), `lint` and `preview` are not in this release;
- component placement is a single column rule; there is no manual placement override.
