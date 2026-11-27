# Library layout, nicknames and the checks behind a mapping

A database row does not contain a symbol. It contains **`nickname:name`**, and KiCad
resolves that through its library tables. So a row is only correct if
(a) the nickname resolves to a library that actually holds that name, and
(b) the file that library points at really exists in the tree.

This skill checks both; it never assumes either.

## The tree it expects

```
kicad_lib/
  Symbol/
    Standard/Standard.kicad_sym          Standard nickname — curated, READ-ONLY
    Symbol/<TYPE>_<MPN>.kicad_sym        one downloaded symbol per file
  Footprint/
    Standard.pretty/<NAME>.kicad_mod     curated land patterns — READ-ONLY
    Footprint.pretty/<TYPE>_<MPN>.kicad_mod
  Step/<TYPE>_<MPN>.stp                  referenced as ${KIPRJMOD}/../kicad_lib/Step/…
  components.db                           the database library
  components_db_windows.kicad_dbl         maps the table for KiCad (not written here)
```

Every path, nickname and suffix is configurable in `kicad_db.json`:

```json
{
  "libs_root": "C:/path/to/kicad_lib",
  "database": "C:/path/to/kicad_lib/components.db",
  "symbols": {
    "standard": { "nickname": "Standard", "file": "Symbol/Standard/Standard.kicad_sym" },
    "parts":    { "nickname": "Symbol",   "folder": "Symbol/Symbol", "suffix": ".kicad_sym" }
  },
  "footprints": {
    "standard": { "nickname": "Standard", "folder": "Footprint/Standard.pretty" },
    "parts":    { "nickname": "Footprint", "folder": "Footprint/Footprint.pretty",
                  "suffix": ".kicad_mod" }
  },
  "models": { "folder": "Step", "suffixes": [".stp", ".step"],
              "reference": "${KIPRJMOD}/../kicad_lib/Step/{name}.stp" },
  "lcsc_parts": "../lcsc-parts/scripts/lcsc.py",
  "language": "en_US"
}
```

## Nickname conventions

| Row value | Resolves to |
|---|---|
| `Standard:R` | a symbol inside `Symbol/Standard/Standard.kicad_sym` |
| `Standard:R_0603` | `Footprint/Standard.pretty/R_0603.kicad_mod` |
| `Symbol:IC_STM32G431C6T6` | `Symbol/Symbol/IC_STM32G431C6T6.kicad_sym`, whose declared symbol is `IC_STM32G431C6T6` |
| `Footprint:IC_STM32G431C6T6` | `Footprint/Footprint.pretty/IC_STM32G431C6T6.kicad_mod` |

The same nickname (`Standard`) appears in both tables; symbol and footprint tables
are separate.

Two registration styles are common, and the row value differs between them:

1. **One library per part** (KiCad 6–9 style). Each `.kicad_sym` is added
   separately, so the nickname is the file stem and the row must read
   `IC_STM32G431C6T6:IC_STM32G431C6T6`. Set
   `"parts": {"nickname": "{name}"}` and the skill writes that form.
2. **One library holding a folder of files** (what this workspace's
   `Symbol:CON_2086581051` rows assume). KiCad 10 can register a *folder* of
   `.kicad_sym` files as a single library — the Add-Library browse menu offers
   "folder with .kicad_sym files", and the official sources now ship
   `*.kicad_symdir` folders — so all the per-part symbols appear under one
   nickname, `Symbol`. Footprints have always worked this way (`*.pretty`).

Either way the **declared** symbol name inside the file must equal the name in the
row; KiCad looks symbols up by the name inside, not by the file name. `verify` and
the mapping gate both enforce that, which is why staging renames the symbol and the
file together.

## What the skill will not do

- Write to `Standard.kicad_sym` or anything in `Standard.pretty` — editing a
  standard symbol silently changes every design that uses it.
- Create a row that points at a file it has not seen.
- Guess a nickname: if a row's nickname is not the configured standard or part
  nickname, the reference is reported as unresolved.

## The mapping gate, in order

For a part the classifier recognises as a candidate for a standard symbol:

1. the candidate name must exist in `Standard.kicad_sym` (the real file is parsed,
   so the table cannot drift from the library);
2. a package-locked symbol must match the part: `*_SOT23` requires a SOT-23
   package, `*_SOT23-5` SOT-23-5, `*_SO8` SOIC-8/SOP-8, `*_DFN8` DFN-8;
3. the symbol's **pin numbers must equal the footprint's electrical pad numbers**
   (mechanical/shield pads are ignored);
4. if the standard symbol names its pins (`1=A 2=K`, `1=+ 2=−`, `1=G 2=S 3=D`,
   `1,3=XTAL 2,4=GND`), the **downloaded symbol's pin names must agree**; if the
   downloaded symbol only numbers its pins, the standard symbol is refused and the
   downloaded one is used;
5. a polarity-free class (resistor, capacitor, inductor, ferrite bead, fuse, NTC,
   bipolar TVS, test point) needs no role evidence — a two-terminal passive has no
   polarity to get wrong.

Failure at any step falls back to the downloaded symbol/footprint and records the
reason in `evidence:`. `--mode all` only widens step 1 to non-passive classes; it
never widens the pin-role evidence requirement. `--mode off` skips the standard
library entirely.

## Staging = renaming, nothing else

`lcsc-libs` writes `C8734_STM32F103C8T6.kicad_sym` containing symbol
`STM32F103C8T6`. The tree wants `IC_STM32F103C8T6`. `stage` therefore:

- renames the top-level `(symbol "…")` and its `<name>_<unit>_<style>` units,
- points the symbol's `Footprint` property at `Footprint:<NAME>`,
- renames the footprint and repoints its `(model …)` to
  `${KIPRJMOD}/../kicad_lib/Step/<NAME>.stp`,
- copies the STEP file as `<NAME>.stp`.

Existing files are **skipped, not replaced** — a staged file may have been reviewed
and hand-cleaned.

## 3D models

A downloaded footprint references its STEP file through `${KIPRJMOD}`. If the file
is missing, `plan` and `verify` warn (they do not block): the board still works, it
just shows no model. KiCad resolves `${KIPRJMOD}` against the design project, so the
`Step/` folder must sit next to the project folder as the reference says.
