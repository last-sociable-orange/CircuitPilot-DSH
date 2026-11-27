# KiCad 10 `.kicad_sch` — what the corpus actually says

Scope: what is needed to *write* a child page of the MCB-01 project (`Design/*.kicad_sch`,
built 2026-11-25, KiCad 10.0.8) and have KiCad read it back unchanged.

Everything below was measured on the seven reference pages, not recalled. Commands in
`spike/`. If a KiCad update changes one of these facts, this file is wrong and the golden
test in `tests/test_templates.py` fails — fix the templates, then fix this file.

---

## 1. Page header

```sexp
(kicad_sch
	(version 20260101)
	(generator "eeschema")
	(generator_version "10.0")
	(uuid "ff51e3ae-…")
	(paper "A2")
	(lib_symbols
```

| Fact | Value |
|---|---|
| `version` on the seven child pages | `20260101` |
| `version` on the root page `MainController.kicad_sch` | `20260306` |
| `generator` | quoted string `"eeschema"` (not a bare symbol) |
| `generator_version` | quoted string `"10.0"` |
| paper | `A2` on all seven pages; `A4` on the root |

The version token is **per file**, not per project, and KiCad accepts both values. Write
`20260101` for a child page; take the token from a `--format-version` option if a page ever
has to match a different KiCad.

There is **no** `(embedded_fonts no)` node in any child page — only the root page carries
one. Do not emit it in a child page.

## 2. Child page vs root page — the instance path

The seven pages are **not** root pages. `MainController.kicad_sch` (root, 7 `(sheet ...)`
symbols) references them by `(property "Sheetfile" "Sync.kicad_sch")`, and each child
symbol instance carries the parent's path:

```sexp
(instances
	(project "MainController"
		(path "/3a8b2593-6306-48f5-a7ff-359d385d6996/285127f6-8998-47ef-b429-f72b63176921"
			(reference "U6")
			(unit 1)
		)
	)
)
```

`/` + root-page uuid + `/` + sheet-symbol uuid. The child file's own
`(sheet_instances (path "/" (page "1")))` is a placeholder and is the same in all seven
pages regardless of which sheet they are.

**Consequence for the emitter:** the instance path is a *build input*, not a constant. A
page written with `(path "/")` will load, but KiCad will not match it to the parent sheet
symbol and the references/units are lost on the next save. The path is therefore read from
the parent page (or passed as `--sheet-path`), and the project name comes from the
`(project "...")` value — both found once per build.

## 3. Node inventory (facts the geometry claims depend on)

Counts across the seven pages:

| node | MCU | Power | USB | Channel_1-4 | Channel_5-8 | Sync | Indicator |
|---|---|---|---|---|---|---|---|
| `symbol` | 30 | 49 | 12 | 32 | 32 | 16 | 25 |
| `wire` | 129 | 127 | 59 | 96 | 96 | 38 | 96 |
| `global_label` | 129 | 127 | 59 | 96 | 96 | 38 | 96 |
| `junction` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `no_connect` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `text` / `hierarchical_label` / `label` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Wires equal labels on every page: one stub wire and one global label per connected pin.
No junction is needed anywhere, which matches the argument in the plan (Â§8.4) that a stub
meets a pin and never another wire. **MCU is 129/129, not 131** as the plan's Appendix D
states; the seven-page total is 641 wire/label pairs.

## 4. Symbol instance

```sexp
(symbol
	(lib_id "Symbol:IC_SN74LVC1G125DCKR")
	(at 91.44 33.02 0)
	(unit 1)
	(body_style 1)
	(exclude_from_sim no)
	(in_bom yes)
	(on_board yes)
	(in_pos_files yes)
	(dnp no)
	(uuid "33d25361-…")
	(property "Reference" "U6"      (at 91.44 43.18 0) …)
	(property "Value" "SN74LVC1G125DCKR" …)
	(property "Footprint" "Footprint:IC_SN74LVC1G125DCKR" …)
	(property "Datasheet" "" …)
	(property "Description" "" …)
	(pin "1" (uuid "1c25f2f7-…"))
	…
	(instances (project "MainController" (path "/…/…" (reference "U6") (unit 1))))
)
```

* `(in_pos_files yes)` is a KiCad 10 addition next to `in_bom`/`on_board`/`dnp`.
* Every pin listed in the netlist gets a `(pin "n" (uuid …))` child, in symbol pin order.
* **All 214 symbol instances in the corpus are placed at angle 0.** An earlier measurement
  in this file claimed a 0/90/180/270 spread; that count was matching every
  `(at x y angle)` node, most of which are global labels. Instances are unrotated, so the
  emitter writes angle 0 and the label direction is decided by the *pin* angle (Â§5).
* **No** `(mirror …)`, **no** `(unit 2)`, **no** `(body_style 2)` anywhere — the plan's
  non-goals (no multi-unit, no mirrored parts) match the corpus.
* Every pin of the symbol gets a `(pin …)` child, not just the wired ones: the 100-pin
  STM32 lists 100, the 33-pin CH132B device lists 33.

### Field hide flags are inconsistent in the corpus

Of 266 instance fields:

| field | top-level `(hide yes)` | `(effects (hide yes))` | visible |
|---|---|---|---|
| `Reference` | 0 | 0 | 266 |
| `Value` | 0 | 57 | 209 |
| `Footprint` | 241 | 23 | 2 |
| `Datasheet` | 241 | 23 | 2 |
| `Description` | 241 | 15 | 2 |

Every page mixes both spellings, so no single template reproduces the corpus byte-for-byte.
KiCad treats both as hidden. The emitter therefore canonicalises: `Value` → `effects`-hide,
`Footprint`/`Datasheet`/`Description` → top-level hide, `Reference` → visible; and the
golden test compares field *meaning* (name, value, position, hidden-or-not).

Instance fields also carry `(show_name no)` and `(do_not_autoplace no)` before `(effects)`.

## 5. Wire and global label

```sexp
(wire
	(pts
		(xy 82.55 33.02) (xy 80.01 33.02)
	)
	(stroke
		(width 0)
		(type default)
	)
	(uuid "edfec058-…")
)
```

```sexp
(global_label "SYNC"
	(at 80.01 33.02 180)
	(effects
		(font
			(size 1.27 1.27)
		)
		(justify right)
	)
	(uuid "0a4bc1f0-…")
)
```

* Both `xy` points share one line — the corpus writes them on a single line.
* `(stroke (width 0) (type default))` on every wire; no colour.
* **No `Intersheetrefs` property.** The plan (Â§8.4) says to emit
  `(property "Intersheetrefs" "${INTERSHEET_REFS}" … (hide yes))`; there is no occurrence
  of `Intersheetrefs` in any of the seven pages. Do not emit it.
* Label angle is the outward pin direction, and `(justify …)` follows it: angle 180 →
  `justify right`, angle 0 → `justify left`, angle 90 → `justify left`, angle 270 →
  `justify right` (text is placed above/below by vertical justification).
  The four rotations of the plan's Â§8.2 table are corroborated by the corpus.

## 6. Library symbol block

```sexp
(symbol "Symbol:IC_SN74LVC1G125DCKR"
	(pin_names (offset 1.016))
	(exclude_from_sim no)
	(in_bom yes)
	(on_board yes)
	(in_pos_files yes)
	(duplicate_pin_numbers_are_jumpers no)
	(property "Reference" "U" …)
	(property "Value" "SN74LVC1G125DCKR" …)
	(symbol "IC_SN74LVC1G125DCKR_0_1"
		(rectangle (start -6.35 -5.08) (end 6.35 5.08) (stroke (width 0.254) (type default)) (fill (type background)))
		(circle    (center -5.08 3.81) (radius 0.381) …)
	)
	(symbol "IC_SN74LVC1G125DCKR_1_1"
		(pin power_in line
			(at 8.89 2.54 180)
			(length 2.54)
			(name "VCC"   (effects (font (size 1.27 1.27))))
			(number "5"   (effects (font (size 1.27 1.27))))
		)
		…
	)
)
```

* Sub-symbol naming is `<name>_<unit>_<body_style>`: `_0_1` holds graphics, `_1_1` holds
  pins.
* `(duplicate_pin_numbers_are_jumpers no)` is a KiCad 10 addition.
* Library-level properties carry `show_name`/`do_not_autoplace` too, and hide with
  `effects` only (e.g. `Footprint` with `(effects (font …) (hide yes))`).
* **Pin direction:** `(at x y angle)` is the pin's *connection point*; `angle` points from
  that point **toward the body**. Verified: VCC at `(8.89, 2.54, 180)`, length 2.54, body
  right edge at `+6.35` — the pin line runs from 8.89 back to 6.35. The outward direction
  (where the label goes) is therefore `angle + 180`, which is what the plan's Â§8.2
  formula computes.

### The symbol library is generated by LCSC3D (2026-11-26)

`kicad_lib/Symbol/Symbol/*.kicad_sym` is **not hand-written and not produced by this repo's
own code**: `tools/export_symbols.py` runs LCSC3D's converter (vendored byte-identical under
`vendor/lcsc3d/`, see `vendor/VENDOR.md`) on the EasyEDA document cached in
`kicad_lib/source/<part>.json`. Two consequences that matter when reading a page:

* The library files carry **LCSC3D's stamps**: `(kicad_symbol_lib (version 20211014)
  (generator lcsc3d))`, properties with `(id N)`, and `hide` as a bare token inside
  `effects`. KiCad 10 parses this — verified with `kicad-cli 10.0.8 sch export netlist` on a
  page that embeds them — but eeschema rewrites them to the current syntax the first time a
  human opens and saves the page. A diff of a generated page against `Design/` therefore
  shows large textual differences for every part whose symbol came from EasyEDA.
* `Standard.kicad_sym` is **KiCad's own** (`(generator "kicad_symbol_editor")`) and is left
  alone: R, C, L, FB and FUSE_PTC are not EasyEDA parts.

Why the change: the library used to be written by the `lcsc-libs` skill, a *reimplementation*
of LCSC3D's conversion. It diverged in ways that showed on the page — filled polygon paths
were emitted open (so an LED's emission arrows rendered as broken strokes) and a
"body centring" step moved graphics 1.27 mm relative to the pins. The audit is in
`vendor/VENDOR.md`; the fix is to stop reimplementing and call LCSC3D.

### A placed part is *linked* to its database row, not copied from it

KiCad's database library does not paste values into a schematic and forget the source. A
symbol placed from it carries a link, and the page must reproduce that or the part stops
being refreshable. Measured on `C59` in `Design/Sync.kicad_sch`, which the user placed from
the database library with KiCad 10 itself:

```sexp
(symbol
	(lib_id "components:components/Ceramic Capacitors/TCC0805X5R106K250FT")
	… (dnp no) (fields_autoplaced yes) (uuid …)
	(property "Reference" "C59" …)
	(property "Value" "10uF" …)            ← database Value
	(property "Footprint" "Standard:C_0805" …)     ← database KicadFootprintLibrary
	(property "Datasheet" "" …)            ← stays empty; the URL is its own field
	(property "Description" "10uF ±10% 25V …" …)   ← database Description
	(property "ID" "Ceramic Capacitors/TCC0805X5R106K250FT" …)
	(property "Keywords" "" …)             ← empty columns are written, not omitted
	… 78 more, Param01/Value01 … Param32/Value32 …
)
```

Four rules follow, and `schwrite` follows all four (`emit/writer.py`, `symbols.database_entry`):

1. **`lib_id` is `<nickname>:<nickname>/<key>`** — KiCad names an item inside a database
   library `<library>/<key>`, so the full id repeats the nickname
   (`components:components/Ceramic Capacitors/TCC0805X5R106K250FT`). Measured, not assumed:
   with this form `kicad-cli sch erc` reports **zero** `lib_symbol_issues`; with
   `<nickname>:<key>` it reports one per symbol.
2. **The project next to the page must declare the libraries.** Without a `sym-lib-table`
   naming `components` as a Database library, KiCad cannot resolve the link at all —
   `lib_symbol_issues` for every symbol. `schwrite` writes that table beside the page
   (`src/schwrite/symlib.py`), with `${KIPRJMOD}`-relative URIs, rewriting only the three
   entries it owns and preserving anything else in the file. Verified: 196 library issues
   across the seven pages before the table, **0** after.
3. **The `lib_symbols` entry is named after the link**, and its sub-symbols are renamed
   `<library>/<key>_<unit>_<style>`. One entry per link, not per geometry file: two resistor
   part numbers share `Standard:R` but are two `lib_id`s.
4. **The field list is the database schema** — every field the `.kicad_dbl` declares, in
   declaration order, empty strings included. A shortlist of "interesting" columns would
   silently stop the symbol being a full database part.
5. **`(fields_autoplaced yes)`** is written, as KiCad writes it.

Verified structurally: our instance for `R51` and KiCad's own `C59` have the same 83
property names in the same order.

### `lib_symbol_mismatch` — closed, and how

Three pages the user refreshed in KiCad (`MCU_updated.kicad_sch` for `U3`,
`MCU_update1.kicad_sch` for `C1`) were used as the oracle. Comparing them entry by entry gave
the full list of what KiCad writes when it resolves a database symbol:

1. property flags in the order `(at)`, `(show_name)`, `(do_not_autoplace)`, `(hide yes)`,
   `(effects)`;
2. `(embedded_fonts no)` **last**, after the sub-symbols — not in the header;
3. every property of the library symbol kept, with value **and** `(at)` position, including
   the EasyEDA extras (`SupplierPart`, `Source`, `Contributor`, `Supplier`,
   `Supplier Part`, `Manufacturer Part`, `JLCPCB Part Class`);
4. database-only columns appended after those, at `(0, 0)`;
5. a library property's **`(justify …)`** survives — the capacitor carries `(justify left)`
   on Reference and Value;
6. **`ki_fp_filters` takes the row's footprint**, not the library's wildcard (`Standard:C_0402`
   rather than `C_*`);
7. `(version 20260306)` for a child page — this KiCad's own number.

All seven are implemented. Measured on the seven pages: `lib_symbol_mismatch` **196 → 0**.
For `C1` the cached entry is now identical to the copy KiCad wrote for that symbol, name
aside.

Two things worth knowing about `MCU_update1.kicad_sch`: it has **29 instances, not 30** —
`C1` was deleted, not re-linked — and it still carries two cache entries for that part
(`…CC0402JRNPO9BN150` and an orphaned `…CC0402JRNPO9BN150_1`). `schwrite` never leaves
orphans: a page is regenerated, so its `lib_symbols` block holds exactly the links in use.

Also measured: `kicad-cli` associates a schematic with a project by basename
(`Sync.kicad_sch` → `Sync.kicad_pro`); with a project file under another name it ignores the
`sym-lib-table` entirely and reports every library as missing.

## 7. `kicad-skip` 0.2.5, measured 2026-11-26

| Question (Â§12) | Answer |
|---|---|
| Q1 create a symbol instance? | **No.** `sch.symbol.new(id)` raises `NotImplementedError`. |
| Q2 append wire / global label? | **Yes**, `sch.wire.new()` and `sch.global_label.new()` both return objects (no property-set probe was needed once Q1 settled the emitter). |
| Q3 round-trip preserves untouched nodes? | **Yes.** Original and round-tripped pages parse to equal trees (`sexpdata`), top-level ordering identical. |
| Q4 stable ordering for golden diffs? | Ordering yes, *formatting no*: saving rewrites the file (2754 lines → 607), so its output never matches KiCad's own spelling. |
| Q5 load+save cost, 30-part page | load 345 ms + save 129 ms â‰ˆ **474 ms** — affordable, but unnecessary for a text emitter. |
| Extras | A save is idempotent (second save is byte-identical to the first), which is worth knowing for any future use. |

**Decision taken from this:** the emitter is the frozen-template text path; `kicad-skip` is
not on the write path at all. `sexpdata` does the independent read side. This removes R1 and
R10 from the critical path rather than mitigating them.

## 8. Upgrade checklist

When KiCad changes version:

1. `uv run pytest tests -q` — `test_templates.py` fails on the first template that drifted.
2. Re-cut the failing template from a freshly saved page (`spike/extract_nodes.py`).
3. Re-run the contract tests; re-read Â§3's node inventory for new node types.
4. Update this file, and the version token in `emit/templates.py`.
