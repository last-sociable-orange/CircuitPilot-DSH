# KiCad Schematic Analyzer

Cross-references a `.kicad_sch` file against an OrcadPCB2-format netlist (`.net`)
to list components, nets, and pin connections with correct KiCad net names.
Powered by the [kicad-skip](https://github.com/psychogenic/kicad-skip) library.

## Usage

```bash
uv run kicad-sch-analyzer <schematic.kicad_sch> <netlist.net> [options]
```

### Arguments

| Argument | Description |
|---|---|
| `schematic` | Path to `.kicad_sch` file |
| `netlist` | Path to OrcadPCB2 netlist (`.net`) file |

### Options

| Option | Description |
|---|---|
| `--list-components` | List all components with value, MPN, DNP status |
| `--list-nets` | List all nets and the pins connected to each |
| `--list-pins <ref>` | List all pins and connected nets for a component (e.g. `U3`) |
| `--json` | Output in JSON format |
| `--hierarchical` | Also parse sub-sheets referenced by the main sheet |
| `--help` | Show help message |

If no list option is given, the default is `--list-components` + `--list-nets`.

---

## Examples

### Default mode — components + nets

```bash
uv run kicad-sch-analyzer sys_power.kicad_sch FlightController.net
```

```
Loading:   sys_power.kicad_sch
Parsed    1 sheet(s), 80 symbol(s).
Netlist:   FlightController.net
          242 components, 164 nets

Ref              Value                          MPN                                                DNP
--------------------------------------------------------------------------------------------------------------
C10              1µF                            CC0201MRX5R6BB105                                  
C3               10µF                           CC0402MRX5R6BB106                                  
...
U3               TPS62130AQRGTRQ1               TPS62130AQRGTRQ1                                  
U4               LP590733QDQNRQ1                LP590733QDQNRQ1                                   
U5               LP590718QDQNRQ1                LP590718QDQNRQ1                                   

Total: 40 components

Net Name                                           Connected Pins
------------------------------------------------------------------------------------------------------------------------
5V_SYS                                             C10.1, C5.1, C6.1, D12.6 (VOUT), D13.6 (VOUT), ...
GND                                                C10.2, C3.2, C4.2, ..., U3.6 (AGND), U3.15 (PGND_1), ...
Net-(U3-SW_1)                                      L1.1 (1), U3.1 (SW_1), U3.2 (SW_2), U3.3 (SW_3), U3.14 (VOS)
...

Total: 21 nets (11 named), 101 pin connections
```

### Inspect a component's pins

```bash
uv run kicad-sch-analyzer sys_power.kicad_sch FlightController.net --list-pins U3
```

```
Component: U3  =  TPS62130AQRGTRQ1
...
Pin #        Pin Name                 Net Name
--------------------------------------------------------------------------------
U3.1         SW_1                     Net-(U3-SW_1)
U3.2         SW_2                     Net-(U3-SW_1)
U3.3         SW_3                     Net-(U3-SW_1)
U3.4         PG                       Net-(U3-PG)
U3.5         FB                       Net-(U3-FB)
U3.6         AGND                     GND
...
U3.13        EN                       Net-(U3-EN)
U3.14        VOS                      Net-(U3-SW_1)
U3.15        PGND_1                   GND
...
```

### JSON output

```bash
uv run kicad-sch-analyzer sys_power.kicad_sch FlightController.net --json --list-components
```

```json
[
    {
        "Reference": "U3",
        "Value": "TPS62130AQRGTRQ1",
        "Footprint": "Footprint:IC_TPS62130AQRGTRQ1",
        "Manufacturer_Name": "Texas Instruments",
        "Manufacturer_Part_Number": "TPS62130AQRGTRQ1",
        "Package": "16-VFQFN Exposed Pad",
        "Description": "IC REG BUCK ADJ 3A 16VQFN",
        ...
        "dnp": false
    },
    ...
]
```

```bash
uv run kicad-sch-analyzer sys_power.kicad_sch FlightController.net --json --list-pins U3
```

```json
{
    "reference": "U3",
    "value": "TPS62130AQRGTRQ1",
    "mpn": "TPS62130AQRGTRQ1",
    "pins": [
        {"pin": "U3.1", "name": "SW_1", "net": "Net-(U3-SW_1)"},
        {"pin": "U3.6", "name": "AGND", "net": "GND"},
        {"pin": "U3.13", "name": "EN", "net": "Net-(U3-EN)"},
        ...
    ]
}
```

```bash
uv run kicad-sch-analyzer sys_power.kicad_sch FlightController.net --json --list-nets
```

```json
[
    {
        "net": "5V_SYS",
        "pins": [
            {"ref": "C10", "pin": "1", "name": ""},
            {"ref": "U3", "pin": "10", "name": "AVIN"},
            ...
        ]
    },
    ...
]
```

### Hierarchical designs

```bash
uv run kicad-sch-analyzer FlightController.kicad_sch FlightController.net --hierarchical --list-pins U3
```

---

## How it works

1. **Netlist is the ground truth.** Every pin in the schematic is looked up in the
   OrcadPCB2 netlist (`.net`). Net names from the netlist are authoritative.
2. **Power symbols** (`#PWRxxx`, `Standard:PWR`, `Standard:GND`) are filtered out
   from the component listing.
3. **Unconnected pins** (marked `unconnected-` in the netlist) are shown as
   `<unconnected>` in text mode or `"net": null` in JSON mode.
4. **Hierarchical support** follows `(property Sheetfile ...)` references to load
   sub-sheets recursively.

### Project structure

```
kicad-sch-analyzer/
├── pyproject.toml              # uv-managed project
├── README.md
├── TEST_RESULTS.md
├── src/
│   └── kicad_sch_analyzer/
│       ├── __init__.py
│       └── __main__.py         # CLI entry point
└── .venv/                      # uv virtual environment
```

Dependency `kicad-skip` is referenced as an editable path in `pyproject.toml`:

```toml
[tool.uv.sources]
kicad-skip = { path = "../kicad-skip", editable = true }
```

## License

MIT
