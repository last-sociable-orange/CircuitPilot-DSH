---
name: kicad-sch-analyzer
description: "Use this skill whenever analyzing, inspecting, or extracting data from KiCad EDA schematic files (.kicad_sch) using the skip library. Triggers include: requests to list components in a KiCad schematic with manufacturer part numbers (MPN), list nets and pin connections, inspect pin-level connectivity of a specific component, compare schematic against a netlist (.net), or convert KiCad schematic data to JSON. Also use when user asks about connectivity of a part (e.g. 'how is U3 connected') in a KiCad design, or wants BOM-like data extracted from schematics. Do NOT use for PCB layout files (.kicad_pcb), gerber files, or non-KiCad EDA formats."
license: MIT
---

# kicad-sch-analyzer — KiCad Schematic Analysis

Cross-references a `.kicad_sch` file against an OrcadPCB2-format netlist (`.net`)
to list components, nets, and pin connections with correct KiCad net names.
Powered by the [kicad-skip](https://github.com/psychogenic/kicad-skip) library.

## Project location

```
kicad-sch-analyzer/          # sibling of kicad-skip/
├── script/pyproject.toml
├── SKILL.md
├── script/src/kicad_sch_analyzer/__main__.py
```

A **uv-managed** project. Run commands from the project root:

```bash
cd kicad-sch-analyzer
uv run kicad-sch-analyzer <schematic.kicad_sch> <netlist.net> [options]
```

## Arguments

| Position | Description |
|---|---|
| `schematic` | Path to `.kicad_sch` file |
| `netlist` | Path to OrcadPCB2 netlist (`.net`) file — **required** |

## Options

| Flag | Description |
|---|---|
| `--list-components` | List components (Ref, Value, MPN, DNP). Power symbols filtered out. |
| `--list-nets` | List all nets with connected pins |
| `--list-pins <ref>` | List all pins and nets for a component (e.g. `U3`) |
| `--json` | JSON output. Components get **all** properties + `dnp` boolean. |
| `--hierarchical` | Recursively load sub-sheets referenced by the main sheet |

Default (no list flag): `--list-components` + `--list-nets`.

## Typical workflows

### Get all components with MPNs
```bash
uv run kicad-sch-analyzer board.kicad_sch board.net --list-components
```

### Check how a chip is connected (by pin number)
```bash
uv run kicad-sch-analyzer board.kicad_sch board.net --list-pins U3
```

### Get all nets and what's on them
```bash
uv run kicad-sch-analyzer board.kicad_sch board.net --list-nets
```

### Full machine-readable dump
```bash
uv run kicad-sch-analyzer board.kicad_sch board.net --json --list-components
uv run kicad-sch-analyzer board.kicad_sch board.net --json --list-nets
uv run kicad-sch-analyzer board.kicad_sch board.net --json --list-pins U3
```

### Hierarchical design (main sheet + subsheets)
```bash
uv run kicad-sch-analyzer main.kicad_sch board.net --hierarchical --list-pins U3
```

## Output notes

- **Net names** come from the `.net` file (KiCad-generated, authoritative).
- **Power symbols** (`#PWRxxx`, `Standard:PWR`, `Standard:GND`) are filtered out of component listing.
- **Unconnected pins** show `<unconnected>`.
- Pins in schematic but missing from netlist are reported as warnings on stderr.

## Dependency

The tool depends on `kicad-skip` (editable path dependency in `pyproject.toml`):

```toml
[tool.uv.sources]
kicad-skip = { path = "../kicad-skip", editable = true }
```

`uv sync` installs both `kicad-skip` and its dependency `sexpdata`.

Source entry point: `src/kicad_sch_analyzer/__main__.py`
