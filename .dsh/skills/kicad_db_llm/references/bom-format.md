# BOM input and report output

The input is whatever the designer agent produced — a BOM with LCSC part numbers —
plus the bundle folder `lcsc-libs` wrote. The output is the same table in the
terminal, optionally as Markdown and JSON.

## CSV

The first row is a header. Header names are matched case-insensitively, with spaces
and dashes folded to underscores, against these aliases:

| Canonical | Accepted headers |
|---|---|
| `lcsc` | `lcsc`, `lcsc#`, `lcsc_part`, `lcsc_number`, `c`, `cno`, `c_number`, `part`, `part_number`, `supplier_part`, `pn` |
| `mpn` | `mpn`, `manufacturer_part_number`, `mfr_part_number`, `manufacturer_pn`, `mpn_manufacturer`, `model` |
| `value` | `value`, `val`, `schematic_value`, `design_value` |
| `ref` | `ref`, `refs`, `reference`, `references`, `designator`, `designators`, `refdes` |
| `qty` | `qty`, `quantity`, `count` |
| `symbol` | `symbol`, `kicad_symbol`, `symbol_library`, `symbol_lib` |
| `footprint` | `footprint`, `kicad_footprint`, `footprint_library`, `footprint_lib`, `package_footprint` |
| `name` | `name`, `library_name`, `file_name`, `stem` |
| `type` | `type`, `product_type`, `prefix` |
| `keywords` | `keywords`, `tags` |
| `notes` | `notes`, `note`, `comment`, `comments`, `description_note` |

Unknown columns are ignored. A file whose header contains none of these is rejected
with the list of expected names rather than being read as an empty BOM.

```csv
ref,qty,lcsc,value
"R1,R2",4,C2906982,10k
"C1,C2",2,C52711259,100nF
U1,1,C8734,
L1,1,C6808014,10uH
D2,1,C12345,5V
```

Rows with neither `lcsc` nor `mpn` are skipped. A leading `C` number is not
required: an `mpn`-only line is resolved with a storefront search that must return
the **same** MPN, case-insensitively — a fuzzy hit is rejected instead of being
silently accepted.

## JSON

```json
{"lines": [
  {"ref": "R1,R2", "qty": 4, "lcsc": "C2906982", "value": "10k"},
  {"lcsc": "C8734", "symbol": "Symbol:IC_STM32F103C8T6"}
]}
```

A bare list of objects works too; `bom`, `items` and `lines` are all accepted as the
wrapper key.

## Overrides

| Field | Effect |
|---|---|
| `value` | `Value` column; otherwise the store's derived value, then the MPN |
| `symbol` / `footprint` | explicit `Library:Name`; validated like everything else (unresolved or pin-mismatched values block the row) |
| `name` | stem used for the downloaded symbol/footprint/STEP files; default `<TYPE>_<MPN>` |
| `type` | product-type prefix when classification picks the wrong one |
| `keywords` | `Keywords` column, since the store payload has no keywords |

## Report

```
#  lcsc      part             class     symbol      footprint                    action
-  --------  ---------------  --------  ----------  ---------------------------  -------
1  C6808014  AHW1608FE100KTF  INDUCTOR  Standard:L  Footprint:L_AHW1608FE100KTF  INSERT
2  C8734     STM32F103C8T6    IC        Symbol:IC_STM32F103C8T6  Footprint:IC_STM32F103C8T6  BLOCKED

  2. BLOCKED  symbol C8734_STM32F103C8T6.kicad_sym is not staged at …/Symbol/Symbol/IC_STM32F103C8T6.kicad_sym; run 'stage' first
  2. WARNING  no downloaded symbol was available for the pin-role check
```

| Line prefix | Meaning |
|---|---|
| `evidence:` | why this class/symbol/footprint was chosen — one line per fact |
| `WARNING` | the row is still written: non-Active status, no stock, no datasheet, no price, missing 3D model |
| `ASSUMED` | a claim taken on trust (`--mode all`, a forced override); never present in the default mode |
| `BLOCKED` | the row is **not** written; the text says which file is missing or which evidence failed |

`--report path.md` writes the same content as a Markdown document with the decision
table, the reasons per line and the run summary. `--json` prints the machine
readable form, including the full 80-column `columns` object for each line — useful
for review before a write.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | every line is `INSERT`, `UPDATE` or `SKIP` |
| 1 | at least one line is `BLOCKED`/`ERROR`, or `verify` found problems |
| 2 | usage or configuration problem (no library root, bad BOM header, foreign database schema) |

A non-zero exit is informative, not fatal: the rows that could be decided have
already been written in one transaction, and the report names the ones that were not.
