---
name: schwrite
description: "Turn a designer netlist JSON into a KiCad 10 schematic page, and prove the page with KiCad's own read-back and ERC. Use when a task says 'build/produce the schematic page for <subsystem>', 'run schwrite', 'verify the page against the netlist', 'ERC the page', or when a netlist under Document/Netlist/ has to become Design/<page>.kicad_sch. Phase 1 places parts only: no wires, no net labels. Do NOT use it to hand-edit a .kicad_sch, to wire a page, or to extract information from an existing schematic (use kicad-sch-analyzer)."
allowed-tools: Bash(schwrite:*), Bash(python:*), Bash(uv:*)
---

# schwrite — netlist to KiCad page, with gates

`schwrite` writes `Design/<page>.kicad_sch` from `Document/Netlist/<page>.json`. Every part is
resolved against `components.db`; the page carries the whole database row, the Reference and
Value visible, everything on a 50 mil grid.

**Phase 1 is placement only.** No wires, no net labels, no space reserved for them.
Unconnected and undriven pins are therefore normal — they are not a defect to fix.

**Never hand-write or patch a `.kicad_sch`.** If a page is wrong, the netlist or the database
is wrong; fix that and rebuild. An agent editing S-expressions is how electrically-wrong
pages get shipped.

## Setup — nothing to install

This folder is self-contained: the package lives in `src/`, and the one third-party module it
needs (an S-expression reader) is vendored beside it. Any Python 3.10+ runs it directly, and
the folder can be copied anywhere.

```pwsh
$SCHWRITE = ".dsh/skills/schwrite/run.py"        # wherever you copied the folder
python $SCHWRITE --help
```

`verify` and `erc` additionally need **`kicad-cli`** (KiCad 8+). It is found on `PATH` and in
the usual install locations, or point at it with `$env:SCHWRITE_KICAD_CLI`. Never start the
KiCad GUI for these commands.

## The three commands

```pwsh
python .dsh/skills/schwrite/run.py build  --netlist Document/Netlist/Sync.json --out Design/Sync.kicad_sch
python .dsh/skills/schwrite/run.py verify --page Design/Sync.kicad_sch --netlist Document/Netlist/Sync.json
python .dsh/skills/schwrite/run.py erc    --page Design/Sync.kicad_sch
```

If you prefer a `schwrite` command, `python -m pip install <this folder>` gives you one; the
launcher and the installed command behave identically.

| command | does | exits |
|---|---|---|
| `build` | writes the page atomically; discovers which libraries the parts need and adds only the missing `sym-lib-table` / `fp-lib-table` entries; refuses a page that will not fit the sheet | `0` ok · `2` netlist bad · `3` build refused |
| `verify` | KiCad's netlist export vs the netlist: every reference, value and footprint | `0` match · `6` mismatch or tool error |
| `erc` | ERC through the project root, every violation classified | `0` only expected classes · `5` anything else |

Useful flags: `--json` on all three (machine-readable report), `--paper auto` on `build`
(pick the smallest sheet that holds the page), `--libs` / `--db` when the project is not the
default layout.

**Run all three, in that order, for every page.** A page is finished only when `verify` and
`erc` both exit 0.

## Reading the results

`verify` names its differences; act on the netlist, never on the page:

```
missing from the page: R7            → the netlist lists a part the page does not have
not in the netlist: C9               → the page has a part the netlist does not
R12: value '100k' on the page, '10k' in the netlist
R2: footprint 'Standard:R_0603' on the page, 'Standard:R_0402' in the netlist
```

`erc` accepts only the classes a placement-only page may have (`pin_not_connected`,
`pin_not_driven`, `power_pin_not_driven`, `duplicate_sheet_names`, `isolated_pin_label`,
`unconnected_wire_endpoint`, `multiple_net_names`). Everything else fails, especially:

| class | meaning | what to do |
|---|---|---|
| `lib_symbol_issues` | a library does not resolve | stop; the project's tables or `kicad_lib` are wrong |
| `lib_symbol_mismatch` | the cached copy differs from the library | re-save/re-export that symbol, rebuild |
| `footprint_link_issues` | the footprint library is not resolvable | fix `fp-lib-table` or stage the footprint |

### Pitfalls seen in practice

- **ERC judges the page you built, and only that page.** It runs on the file you pass. If KiCad
  cannot resolve the libraries — it matches a project to a schematic by *basename*, so a child
  page beside `MainController.kicad_pro` resolves nothing — `schwrite` retries the same page
  in a scratch project carrying the project's library tables. Either way the report holds this
  page's violations and nothing from the rest of the hierarchy. `--json` says which path was
  taken (`mode: direct` or `mode: scratch-project`) and what was checked (`checked`).
- **`build` was refused for the sheet**: the plan needed more room than the paper has. Re-run
  with `--paper auto`, or report that the subsystem needs splitting.
- ERC does not check that the page is wired into the hierarchy; that is the parent page's
  business. The gate is: this page builds, reads back correctly and ERC-clean.

## Rules

- One netlist → one page. Never squeeze or silently drop a component to make it fit.
- Only `schwrite` writes pages. `Design/` may be written during a test run, but nothing else
  in it (`.kicad_pro`, `.kicad_pcb`, unrelated pages) may be touched; copy aside anything the
  user cares about before overwriting.
- Never "fix" a verify mismatch by changing the netlist to match what was built. The netlist
  is the design. If you believe it is wrong, say which net and why, and stop.
- Never delete or move files in `Document/`, `kicad_lib/` or `Datasheet/`.
- Report in full: page path, `N components read back, all N correct`, ERC class counts, and
  anything the designer or worker must fix.

## Where things are

| | |
|---|---|
| this folder | `run.py` (launcher), `src/schwrite/` (the package), `MANIFEST.json` (what it was cut from) |
| upstream | `dsh-kicad/schwrite/` — `tools/sync_skill.py` regenerates this copy; `--check` proves it is current |
| tests | `dsh-kicad/schwrite/tests/` — `pytest`, 116 tests |
| format facts | `dsh-kicad/schwrite/docs/format-notes.md` |
| phase 1 scope + numbers | `dsh-kicad/schwrite/CHANGELOG.md`, `README.md` |
| plan | `Document/DesignDoc/SchWrite_Software_Plan/SchWrite_Software_Plan.md` |

Not in phase 1: `pages` (batch), `lint`, `preview`, and any wiring. Do not invent those
steps — build, verify and ERC one page at a time.
