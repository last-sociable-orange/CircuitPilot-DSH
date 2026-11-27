# schwrite

Netlist JSON in → KiCad 10 schematic page out, verified by KiCad's own netlist read-back.

Development plan: `../Document/DesignDoc/SchWrite_Software_Plan/SchWrite_Software_Plan.md`
(document `SW-PLAN-SCHWRITE-001`). Format facts learned from the corpus:
[`docs/format-notes.md`](docs/format-notes.md).

## Phase 1 (`v1.0.0`) — what it is

**Placement only.** `schwrite` reads a designer netlist, resolves every reference against
`components.db`, and writes a KiCad page that holds exactly those parts: correct symbols, the
whole database row as fields, Reference and Value visible beside the graphic, all on a 50 mil
grid with fixed 500 mil gaps. It draws **no wires and no net labels** — unconnected and
undriven pins are expected and are not defects.

A page is accepted only when two independent checks pass:

| gate | command | passes when |
|---|---|---|
| read-back | `schwrite verify` | KiCad's own netlist export lists exactly the netlist's references, values and footprints |
| ERC | `schwrite erc` | no violation class that means the page is wrong (`lib_symbol_issues`, `lib_symbol_mismatch`, `footprint_link_issues`, …) |

Both need `kicad-cli` (KiCad 8+). It is discovered automatically; set `SCHWRITE_KICAD_CLI` for
an unusual install.

## Install

```pwsh
uv sync --extra dev           # creates .venv from uv.lock
# or, into an existing environment:
python -m venv .venv; .venv\Scripts\pip install -e .
```

Only runtime dependency: `sexpdata`. Python ≥ 3.10.

## Commands

```pwsh
schwrite build  --netlist Document/Netlist/Sync.json --out Design/Sync.kicad_sch
schwrite verify --page Design/Sync.kicad_sch --netlist Document/Netlist/Sync.json
schwrite erc    --page Design/Sync.kicad_sch
```

| command | what it does | exit codes |
|---|---|---|
| `build` | writes the page atomically, discovers the project's library tables and adds only what is missing | 0 ok · 2 netlist bad · 3 build refused |
| `verify` | KiCad read-back vs netlist, field by field | 0 match · 6 mismatch or tool error |
| `erc` | ERC through the project root, classified | 0 only expected classes · 5 anything else |

All three accept `--json` for machine-readable reports.

## Symbol library = LCSC3D's converter, vendored

`kicad_lib/Symbol/Symbol/*.kicad_sym` is produced by **LCSC3D's own conversion code**, copied
byte-identically into [`vendor/lcsc3d/`](vendor/lcsc3d) and driven by
[`tools/export_symbols.py`](tools/export_symbols.py) over the EasyEDA documents cached in
`kicad_lib/source/`. Nothing in this repo reimplements that conversion — the earlier
reimplementation (`lcsc-libs` skill) dropped path-closing points and shifted symbol graphics
1.27 mm off their pins, which is why LEDs drew broken arrows. See
[`vendor/VENDOR.md`](vendor/VENDOR.md) for the file list, hashes and the measured difference.

```pwsh
uv run python tools/export_symbols.py --dry-run     # what would change
uv run python tools/export_symbols.py               # fetch missing sources, rewrite symbols
uv run python tools/export_symbols.py --offline     # cache only, no network
```



## Every symbol is linked to its database row

`schwrite` writes what KiCad itself writes when a part is placed from a database library:

* `(lib_id "components:components/<ID column>")` — the link. KiCad names an item inside a
  database library `<library>/<key>`, so the id repeats the nickname; measured with ERC,
  `<nickname>:<key>` resolves nothing while `<nickname>:<nickname>/<key>` resolves everything;
* a `sym-lib-table` **beside the page** declaring `Standard`, `Symbol` and `components` (the
  Database library). Without it KiCad cannot resolve a single symbol; `src/schwrite/symlib.py`
  writes it with `${KIPRJMOD}`-relative URIs, touching only the three entries it owns;
* a `lib_symbols` entry named after that link, holding the geometry with its sub-symbols
  renamed to `<library>/<key>_<unit>_<style>`;
* the standard five fields plus **every field the `.kicad_dbl` declares**, in declaration
  order, values taken from the row (empty columns included, as KiCad does);
* `(fields_autoplaced yes)`.

`tests/test_page.py::test_matches_the_field_list_kicad_wrote_for_a_hand_placed_part` pins
this to a symbol the user placed by hand (`C59` in `Design/Sync.kicad_sch`): our instance
field list must equal KiCad's, name for name, in order.

## Status

- **M0 complete** (2026-11-26): templates frozen against the seven reference pages, graded
  by `tests/test_templates.py`.
- **M1 complete** (2026-11-26): netlist, database, symbol and layout layers. All 196 parts
  of the seven pages resolve (45 distinct parts), every netlist pin exists on its symbol,
  and cells/positions reproduce the 2026-11-25 build — exactly on five pages, and on USB
  and MCU only where a Reference is wider than the Value (see `test_layout.py`).
- **M2 complete** (2026-11-26): `page.py`, `emit/writer.py`, `context.py`, `cli.py build`.
  Symbols and fields are placed at the planner's slots and the page parses: `kicad-cli sch
  export netlist` on the generated MCU page lists the same 30 components, footprints and
  values as the 2026-11-25 build (wires and labels arrive in M3, so every pin is still
  `unconnected-*`). Exit codes 0/2/3, atomic write, JSON report.
- `verify`, `lint`, `pages` and the gates themselves are M4.

## Quick look

```pwsh
uv run python -m schwrite.cli build --netlist tests/fixtures/netlists/MCU.json `
  --out out/MCU.kicad_sch --libs tests/fixtures/libraries `
  --db tests/fixtures/libraries/components_db_windows.kicad_dbl `
  --root-page ..\Design\MainController.kicad_sch --uuid-seed demo
```

## Quick start

```pwsh
# one environment, one cache — never the global uv cache
$env:UV_CACHE_DIR = "..\.uv-cache"
uv venv .venv
uv pip install -e . pytest
.\.venv\Scripts\python.exe -m pytest tests -q
```

## What this will do

Default sheet is **A4**; pages that need more room are refused rather than written off the
sheet (`build` exits 3 and names the smallest sheet that holds it, `--paper auto` picks it).
Parts are packed with a skyline packer and then spread to fill the drawing band, so a page
uses its sheet instead of hugging the top-left corner; the title-block corner is a keep-out.

```text
schwrite build  --netlist <json> --out <page.kicad_sch> [--libs <dir>] [--db <.kicad_dbl>]
                [--paper A4|A3|A2|auto]
schwrite verify --netlist <json> --sch <page.kicad_sch>
schwrite lint   --sch <page.kicad_sch>
schwrite pages  --netlist-dir <dir> --out-dir <dir> [--jobs N]
```

Four gates decide whether a page is done: netlist parity against KiCad's read-back, ERC
triage, self-lint before writing, independent lint after writing. A page that fails is
regenerated, never patched.

## Design decisions so far

| Decision | Why |
|---|---|
| Frozen text templates, not a library writer | `kicad-skip` 0.2.5 cannot create a symbol instance, and its writer reformats the whole file, so it can never match KiCad's own spelling. |
| `sexpdata` for the independent read side | It parses; it does not pretend to model KiCad. |
| Golden test compares field *meaning*, not bytes | The reference corpus uses two spellings of the hidden-field flag, so no template reproduces it byte-for-byte. |
| Instance path is a build input | The pages are children of `MainController.kicad_sch`; a page written with `path "/"` loses its references on the next save. |

## Layout

```text
spike/            M0 investigation scripts + their output (kept: they are the evidence)
docs/             format-notes.md, this repo's plan and acceptance notes
src/schwrite/     the package (sexp.py scanner, emit/templates.py so far)
tests/fixtures/   reference pages, netlists and libraries copied read-only from the project
tests/            golden tests against the frozen corpus
```
