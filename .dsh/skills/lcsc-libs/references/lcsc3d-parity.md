# LCSC3D parity — rule by rule

The converter is our own code, but the conversion **logic** follows LCSC3D, which was
verified to produce symbols that open correctly in KiCad. This table is the audit: what
LCSC3D does, what we do, and how each rule is checked. Two entries are deliberate
improvements (marked *improved*).

Reference files read: `eda/easyeda_import.py` (source parsing) and `eda/kicad.py`
(target emission).

## Geometry

| Rule | LCSC3D | Here | Check |
|---|---|---|---|
| Canvas unit | `length(v) = v * UNIT`, UNIT = 10 mil | 0.254 mm | R0603 pads match KiCad's land pattern |
| Y axis | `(head.y - y) * UNIT` | same | rendered SVGs look upright |
| Symbol origin | document head `x`/`y` | head origin, then **centre the body on (0,0)**, shift snapped to 1.27 mm | *improved*: body centre measured at (±0.000, ±0.000) mm for all 5 fixtures; pins still on the 1.27 mm grid |
| Footprint origin | — (not in LCSC3D's scope here) | pad bounding-box centre | pad centres symmetric; R0603 ±0.7534 mm |
| Pin connection point | **the pin dot** (segment 1), header as fallback | same | `M315,185h10` and reversed paths give the same pin |
| Pin body end | endpoint farthest from the dot | same | far end lands on the body edge, gap 0.000 mm |
| Pin angle | `body - connection`: `dx>0→0, dx<0→180, dy>0→90, dy<0→270` | same | LQFP-48 = 24 × 0 + 24 × 180; matches KiCad `Device:D` (left 0, right 180) |
| Pin length | `abs(dx) + abs(dy)` | same | 2.54 mm on the fixtures |
| Pin drawing | `P` groups: header/path/name/number/inverted/clock | same | inverted/clock → `inverted`/`clock`/`inverted_clock` |
| Pin name/number source | `label[4]` / `designator[4]`, number falls back to `header[3]` | same | names and numbers render |
| Pin visibility | `header[1] == 'show'`, label/number `== '1'` | same | hidden pins get `(hide yes)` |
| Pin label size | `min(size, 1.27)` mm, hidden → **size 0** (no `hide` flag) | same | dense parts no longer collide |
| Pin electrical | `1→input, 2→output, 3→bidirectional, 4→power` | same, with `power_in` (the token KiCad accepts) | — |
| Rectangle | anchor `(x, y+h)`, size `(w, h)`; fill `background`; stroke from fields | same | R0603 body 5.08 × 2.032 mm |
| Stroke width/style | field width × UNIT, styles `0..3 → default/dash/dot/dash_dot` | same | emitted per shape |
| Circle | `C`: radius = field 3 for both axes | same | — |
| Ellipse | `E` with `rx != ry` → **tessellated polyline** | same (sagitta-based vertex count) | warning recorded |
| Fill type | `background` if mean RGB ≥ 192 else `outline`, `none` when absent | same | — |
| Text | `(at x y rotation*10)`, justify mapped from start/end | same | — |
| Unsupported op | raises / records | skipped **with a warning**, never silent | manifest lists them |

## Layers (footprint)

EasyEDA numbers **5/6 as paste and 7/8 as mask** — the reverse is an easy mistake, and
this converter had it backwards until the parity audit. Layer 99 is component shape
(`Dwgs.User`), 100/101 are component shape/mark (`F.Fab`).

| id | EasyEDA | KiCad |
|---|---|---|
| 1 / 2 | top/bottom copper | `F.Cu` / `B.Cu` |
| 3 / 4 | top/bottom silk | `F.SilkS` / `B.SilkS` |
| 5 / 6 | top/bottom **paste** | `F.Paste` / `B.Paste` |
| 7 / 8 | top/bottom **mask** | `F.Mask` / `B.Mask` |
| 10 | outline | `Edge.Cuts` |
| 12, 15 | documentation, mechanical | `Dwgs.User` |
| 13 / 14 | top/bottom assembly | `F.Fab` / `B.Fab` |
| 99 | component shape | `Dwgs.User` |
| 100 / 101 | component shape / mark | `F.Fab` |

## Output format (differs on purpose)

LCSC3D writes KiCad 6/7-era stamps (`SYMBOL_VERSION 20211014`, `FOOTPRINT_VERSION
20240108`). This skill targets the installed **KiCad 10.0.8**: `20251024` for symbols,
`20260206` for footprints, `(hide yes)` as a child token, `(fill yes|no)` for footprint
graphics, `(embedded_fonts no)` per symbol. KiCad 10 accepts both, but only one is
native.

## Verification commands

```bash
python scripts/lcsc_libs.py selftest            # 24 offline geometry/writer checks
pytest tests -q                                 # 35 offline tests
kicad-cli sym upgrade --output out lib.kicad_sym   # parse (from a shell, not Python)
kicad-cli sym export svg --output out lib.kicad_sym
kicad-cli fp  upgrade --output out dir.pretty
```

Current state: all three libraries parse and render; every pin's far end sits on the
body edge (0.000 mm) for all five fixtures; bodies centred at (0, 0).
