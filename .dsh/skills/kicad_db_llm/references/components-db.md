# The `components` table — 80 columns and what fills them

KiCad's **database library** does not read a `.db` file directly. It reads a
`.kicad_dbl` description that names the table, the columns that carry the symbol
and the footprint, and the columns it should show. That file
(`components_db_windows.kicad_dbl` in the library folder) is fixed by whoever set
the library up, so **the table's column names and order are a contract**: rename
one and every existing design loses that field.

This skill writes the 16 metadata columns plus 32 `Param`/`Value` pairs, and never
alters the table.

## Metadata columns

| # | Column | Filled from | Notes |
|---|---|---|---|
| 1 | `ID` | `<store category>/<MPN>` | matches what `KicadLibGui-LCSC` writes; the category is the first segment of the store's category path |
| 2 | `Description` | store description | falls back to `"<MPN> <package>"` |
| 3 | `Keywords` | BOM `keywords` only | `lcsc-parts --json` does not publish the storefront's keyword text, so this stays empty rather than inventing tags |
| 4 | `Value` | BOM `value`, else the store's derived value, else the MPN | for a resistor the store already derives `10k` |
| 5 | `Manufacturer` | store brand | |
| 6 | `ManufacturerProductNumber` | MPN (falls back to the C-number) | **the identity**: upserts, duplicate reports and `show` all key on it |
| 7 | `Package` | store package | e.g. `0603`, `LQFP-48(7x7)` — used by the classifier |
| 8 | `KicadSymbolLibrary` | `Nick:Symbol` | must resolve on disk; see [`library-layout.md`](library-layout.md) |
| 9 | `KicadFootprintLibrary` | `Nick:Footprint` | must resolve on disk |
| 10 | `PartStatus` | store status | `Active` expected; anything else is reported as a warning |
| 11 | `QtyAvailable` | stock at lookup time | a snapshot, not a promise |
| 12 | `Distributor` | `LCSC` / `LCSC International` | as the storefront reports it |
| 13 | `DistributorProductNumber` | the `C…` number | |
| 14 | `UnitPrice` | `price@qty/price@qty/…` | **largest quantity first**, e.g. `0.0007@50000/0.0015@100`; the existing database uses this order, and readers treat it as an opaque string |
| 15 | `ProductUrl` | store product page | |
| 16 | `DatasheetUrl` | store PDF link | empty when none is published; never guessed |

## Parameters

`Param01`/`Value01` … `Param32`/`Value32` hold the store's parameter pairs in the
order `lcsc-parts` returns them (headline specs first). A parameter that would
duplicate a dedicated column — `Manufacturer`, `Manufacturer Part Number`,
`Category` — is skipped so the row is not self-contradictory. Unused slots are
`-`/`-`, matching what the GUI writes.

A name with an empty value is kept (`Param14` = `Mating Cycles`, `Value14` = ``),
because the existing database does the same and the parameter list is information
about the part.

## Price ladders

The store returns ascending tiers (`1 @ 0.01`, `100 @ 0.001`). The skill writes
them **descending** to match every row already in `components.db`:

```
UnitPrice = 0.001@100/0.01@1
```

Currency is recorded in the run report, not in the column — the column has no
currency field, and the storefront used (`--lang`) is part of the run, not of the
part.

## What KiCad actually does with the row

| Column | Effect in the schematic |
|---|---|
| `KicadSymbolLibrary` | the symbol that is placed; KiCad splits it at `:` into library nickname and symbol name |
| `KicadFootprintLibrary` | the footprint a placed symbol gets; same `nickname:name` split |
| `Value`, `Description` | what the chooser shows |
| every other column listed in the `.kicad_dbl` | becomes a symbol **field** on the schematic symbol, so the BOM carries MPN, price and stock without extra work |
| `Datasheet` property in the `.kicad_dbl` | mapped from `DatasheetUrl` in this workspace's file |

## Not this skill's job

- Editing or regenerating the `.kicad_dbl` (`tools/gen_dbl.py` upstream does that).
- Migrating an existing database; the schema check refuses anything that is not
  the 80 columns rather than guessing.
- ODBC driver setup (`SQLite3 ODBC Driver` on Windows, `libsqliteodbc` on Linux).
