---
name: kicad_db_llm
description: "Fill a KiCad database-library SQLite file (components_db / components.db, the 80-column `components` table) from a BOM of LCSC part numbers, using the symbol, footprint and STEP files already in the kicad_lib tree. Use when a BOM exists and the parts must become placeable KiCad database symbols: 'add these parts to the component database', 'fill components.db from this BOM', 'make KiCad's database library show this part', or after lcsc-libs download + worker file staging. Standard library only — no packages, no KiCad needed. Do NOT use it to search parts (use lcsc-parts), to download library files (use lcsc-libs), or to edit `.kicad_dbl` files."
allowed-tools: Bash(python:*), Bash(python3:*)
---

# KiCad database library — fill `components.db` from a BOM

One command turns a BOM line into a row KiCad's **database library** can place:
the symbol, footprint, parameters, price, stock and datasheet, written into the
same 80-column `components` table that `KicadLibGui-LCSC` writes by hand.

The skill decides one thing that a GUI user decides by typing: **which symbol and
which footprint**. It does that from the files on disk, never from a guess.

## The two rules, and how they are enforced

| Rule | How the skill enforces it |
|---|---|
| **Passives use the standard library.** Resistor, capacitor, inductor, ferrite bead, fuse, NTC, crystal. | Candidate names come from `Symbol/Standard/Standard.kicad_sym` and `Footprint/Standard.pretty`. A candidate is only used when its **pins exist on the footprint** and — for anything polarised or with named pins — when the **downloaded symbol's own pin names agree** (`1=A 2=K`, `1=+ 2=−`, `1=G 2=S 3=D`, …). Otherwise it falls back and says why. |
| **Actives use the downloaded files.** ICs, connectors, switches, modules. | No standard candidate is ever proposed for them; the row points at `Symbol/<TYPE>_<MPN>` and `Footprint/<TYPE>_<MPN>`, which must exist. |

`Standard.kicad_sym` and `Standard.pretty` are **read-only** for this skill
(`assert_writable` refuses them). Downloaded material goes where the worker agent
puts it: one symbol per file in `Symbol/Symbol/`, one footprint per file in
`Footprint/Footprint.pretty/`, STEP in `Step/`.

## Setup check (once per session)

```bash
python skills/kicad_db_llm/scripts/kicad_db.py check
python skills/kicad_db_llm/scripts/kicad_db.py selftest      # offline, 9 checks
python skills/kicad_db_llm/scripts/kicad_db.py catalog        # standard library + mapping table
```

`check` prints the library root, the database, the two sibling CLIs and the counts
of standard symbols/footprints and downloaded files. `selftest` builds a miniature
library in a scratch folder and asserts the reader, the writer, the mapping gates,
staging and verification — no network, no user data.

## Workflow

1. **Design done, BOM known** — the designer agent's BOM with LCSC part numbers
   (`C…`). An MPN-only line is resolved by exact match on the storefront; a fuzzy
   match is never accepted.
2. **Download** with the `lcsc-libs` skill:
   ```bash
   python skills/lcsc-libs/scripts/lcsc_libs.py --out <project>/WIP fetch C25804 C8734
   ```
3. **Worker agent organises the files** into `kicad_lib/` (its naming:
   `<ProductType>_<FullProductNumber>`). Verify it wrote what the row will point at:
   ```bash
   python skills/kicad_db_llm/scripts/kicad_db.py verify
   ```
4. **Plan — no writes** (this is where mismatches show up):
   ```bash
   python skills/kicad_db_llm/scripts/kicad_db.py plan bom.csv --bundle <project>/WIP --show-evidence
   ```
5. **Stage** anything the plan reports as blocked because the files are still in the
   bundle (dry run first; existing files are never replaced):
   ```bash
   python skills/kicad_db_llm/scripts/kicad_db.py stage C8734 --bundle <project>/WIP --dry-run
   python skills/kicad_db_llm/scripts/kicad_db.py stage C8734 --bundle <project>/WIP
   ```
6. **Apply** the BOM:
   ```bash
   python skills/kicad_db_llm/scripts/kicad_db.py apply bom.csv --report WIP/db-report.md
   ```
7. **Verify** the database against the tree, then register nothing: the
   `.kicad_dbl` is read-only for this skill.

## Commands

| Command | Writes? | Purpose |
|---|---|---|
| `check` | no | configuration, library tree, database, sibling CLIs |
| `catalog` | no | every standard symbol/footprint, and the class → candidate table |
| `plan <bom>` | no | decide every line; `--show-evidence` prints the reasoning |
| `apply <bom>` | **yes** | decide and write; `--dry-run` to preview |
| `add <part>` | **yes** | one part from the command line; `--dry-run` to preview |
| `stage <part> --bundle DIR` | **yes** | copy/rename bundle files into the tree; `--dry-run` |
| `verify` | no | check every row's symbol/footprint/model against the files |
| `show <mpn\|C…>` | no | print one row |
| `selftest` | no | offline checks in a scratch folder |

Common options: `--libs-root`, `--db`, `--config`, `--json`, `--lang en_US|zh_CN`,
`--detail-json FILE` (repeatable), `--offline`, `--mode auto|all|off`,
`--on-exist skip|update|fail`, `--auto-stage`.

## Reading the report

```
#  lcsc      part             class     symbol      footprint                    action
1  C6808014  AHW1608FE100KTF  INDUCTOR  Standard:L  Footprint:L_AHW1608FE100KTF  INSERT
```

| Action | Meaning |
|---|---|
| `INSERT` | a new row will be written / was written |
| `SKIP` | the MPN is already in the database; nothing overwritten |
| `BLOCKED` | the mapping cannot be proven or the files are missing — the note names the file it wants |
| `ERROR` | the part could not be looked up (bad number, storefront down, CLI missing) |

Under the table, each line gets `evidence:` (why this symbol), `WARNING:`
(non-Active status, no datasheet, missing 3D model), `ASSUMED:` (only with
`--mode all` or a forced override) and `BLOCKED:` (what to do next). **Never hide a
`BLOCKED` line** — it is a part that would not appear in KiCad.

## BOM input

CSV or JSON; headers are matched case-insensitively:

```csv
ref,qty,lcsc,value
"R1,R2",4,C2906982,10k
"C1,C2",2,C52711259,100nF
U1,1,C8734,
L1,1,C6808014,10uH
```

| Column | Meaning |
|---|---|
| `lcsc` | LCSC part number (`C…`) — the authoritative identity |
| `mpn` | manufacturer part number; used when `lcsc` is absent (exact match only) |
| `value` | schematic value; defaults to the storefront's value, then the MPN |
| `symbol` / `footprint` | explicit `Library:Name` override — still validated |
| `name` | file/symbol stem for downloaded material (default `<TYPE>_<MPN>`) |
| `type` | product-type prefix (`IC`, `CON`, `D`, …) when classification is wrong |
| `keywords` | `Keywords` column (the storefront payload has none) |
| `ref`, `qty`, `notes` | reported only; not columns |

Honest gap: `lcsc-parts --json` does not publish storefront **keywords**, so the
`Keywords` column stays empty unless the BOM supplies them.

## Existing rows

Default `--on-exist skip`: an MPN already in the database is reported and left
**untouched**; a second run never duplicates it. `--on-exist update` rewrites every
column except the MPN and lists the changed fields; `--on-exist fail` refuses the
whole batch.

## What lands in a row

`ID` = `<store category>/<MPN>`, `ManufacturerProductNumber` = MPN (the key KiCad
and the GUI upsert use), `KicadSymbolLibrary`/`KicadFootprintLibrary` = `Lib:Name`,
`UnitPrice` = `price@qty/…` (largest quantity first, the layout the existing
database uses), the 32 `ParamNN`/`ValueNN` pairs from the store, unused slots `-`.
Full column table: [`references/components-db.md`](references/components-db.md).

## Verify

```bash
python skills/kicad_db_llm/scripts/kicad_db.py verify
```

Reports rows whose symbol or footprint does not resolve, whose symbol file declares
a different name than the row references, or whose footprint points at a missing
STEP file. It also lists duplicate MPNs. On the database that shipped with this
workspace it found 20 pre-existing broken references (renamed symbols, MPNs with a
`/` in them) — that is the kind of error the check exists for.

## Limits

- **Not a parts tool.** Part numbers come from `lcsc-parts`; this skill never
  invents one, and `--offline` + `--detail-json` lets it run purely on data already
  fetched.
- **Cannot prove what the vendor did not write.** If a downloaded symbol names its
  pins by number only, a polarised standard symbol is refused (use `--mode all` with
  a human decision, or keep the downloaded symbol).
- **Symbol fit is checked, not simulated.** Pin/pad numbers and pin *roles* are
  compared; whether the body is pretty, or the land pattern good, is not judged.
- **One nickname convention per tree.** Defaults are `Standard`, `Symbol`,
  `Footprint` for `Symbol/Standard/Standard.kicad_sym`, `Symbol/Symbol/`,
  `Footprint/Footprint.pretty/`. A tree that registers every `.kicad_sym` as its own
  library sets `"parts": {"nickname": "{name}"}` and rows read `IC_X:IC_X`.
- **`.kicad_dbl` is not written.** Registering the database, the nickname table and
  the ODBC driver stay a human step.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `no kicad_lib folder found` | `--libs-root <path>` or `"libs_root"` in `kicad_db.json` |
| `the lcsc-parts skill is not at …` | `--detail-json parts.json`, or set `lcsc_parts` in the config |
| `BLOCKED … does not exist` | the files are still in the bundle: `stage <part> --bundle DIR`, then re-apply |
| `declares symbol 'X', not 'Y'` | the file and the symbol inside disagree; staging renames both, a hand-edited file needs its `(symbol "…")` fixed |
| `pins [1,2] do not match the footprint pads [1,2,3]` | wrong part variant or wrong override |
| `standard symbol … rejected: pin roles disagree` | the part's pinout differs from the standard symbol — keep the downloaded one |
| Storefront lookups fail with `UnicodeEncodeError` | the child needs `PYTHONIOENCODING=utf-8`; the skill sets it, a manual `lcsc.py` call needs it too |
| `verify` reports duplicates | merge them by hand; this skill only ever writes one row per MPN |

## Do / Don't

- **Do** run `plan` (or `--dry-run`) and read every `BLOCKED`/`WARNING` before `apply`.
- **Do** keep `Standard.kicad_sym` and `Standard.pretty` read-only — a standard
  symbol edit changes every design that uses it.
- **Do** read the `evidence:` lines when a part class looks wrong; the fix is a BOM
  `type`/`symbol`/`footprint` override, not an edit to the library.
- **Do** run `verify` after a batch; it catches pre-existing damage too.
- **Don't** invent a symbol/footprint name to make a row insert — a row that KiCad
  cannot resolve is worse than a missing row.
- **Don't** hand-edit the 80-column schema or the `.kicad_dbl`.
