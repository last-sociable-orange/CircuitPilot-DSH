# EasyEDA document format — what this skill consumes

Everything here was derived from live responses recorded in
`tests/fixtures/` (five parts, 233 KB), not from another project's source.

## Where the data comes from

| Purpose | Request | Notes |
|---|---|---|
| Symbol + footprint + model reference | `GET https://easyeda.com/api/products/{C…}/components` | ~20–90 KB; needs `Accept: */*` — `application/json` returns **403** |
| STEP model | `GET https://modules.easyeda.com/qAxj6KHrDKw4blvCG8QJPs7Y/{uuid}` | `ISO-10303-21`; 1 MB (R0603) … 9.8 MB (LQFP-48) |
| OBJ model (unused) | `GET https://modules.easyeda.com/3dmodel/{uuid}` | `v x y z` text |
| Datasheet | `GET https://wmsc.lcsc.com/ftps/wm/product/detail?productCode={C…}` → `result.pdfUrl` | JSON, no HTML scraping |

The component response has `result.dataStr` (symbol) and `result.packageDetail.dataStr`
(footprint). Either can be a **JSON string or an already-parsed object** — handle both.

## The document

```json
{"head": "{...}", "shape": ["P~show~3~9~525~230~0~gge461~0^^...", "R~325~175~2~2~150~250~#880000~..."],
 "subparts": []}
```

`shape` is a list of strings. Within a record, `~` separates fields and `^^` separates
segments. A pin therefore splits into seven segments; everything else has one.

## Ops, with the field layout actually observed

### Symbol

| Op | Fields | Meaning |
|---|---|---|
| `P` | segment 0: `P, show, c_etype, number, x, y, rotation, id, locked` | one schematic pin |
| | segment 1: `x, y` | pin end point |
| | segment 2: `path, colour` | e.g. `M 525 230 h -10` (length in canvas units) |
| | segment 3: `visible, x, y, rotation, name, anchor, font, size, colour` | pin name |
| | segment 4: same layout | pin number |
| | segments 5–6: dot position, clock/inversion decoration | ignored |
| `R` | `R, x, y, rx, ry, width, height, colour, …` | `(x, y)` is one corner, `width`/`height` the size |
| `E` | `E, cx, cy, rx, ry, colour, …` | ellipse → KiCad circle (warns when rx ≠ ry) |
| `T` | `T, …, x, y, …, text, …` | free text |

Pin electrical codes seen: `0` (68), `3` (51), `1` (4), `2` (2), empty (2). Mapping
used: `0`/empty → `unspecified`, `1` → `input`, `2` → `output`, `3` → `bidirectional`,
`4` → `power_in`, anything else → `unspecified`.

### Pins: the dot is authoritative

Three details decide whether a converted symbol's pins line up. All three follow
LCSC3D's converter, which was verified against symbols that open correctly in KiCad:

1. **The connection point is the pin dot** — segment 1 (`^^`-separated), *not* the
   header `x`/`y` and *not* the start of the drawn path. The path's drawing order
   carries no meaning: `M315,185h10` and `M325,185h-10` describe the same pin.
2. **The body end is the path endpoint farthest from the dot**, and the KiCad angle
   comes from `body - connection` in converted coordinates:
   `dx > 0 → 0`, `dx < 0 → 180`, `dy > 0 → 90`, `dy < 0 → 270`.
   KiCad's own `Device:D` is the reference: its left pin (connection at x = −3.81) is
   angle 0, its right pin 180. Getting this backwards detaches every pin from the body.
3. **The symbol origin is the document head's `x`/`y`**, not a computed bounding box.
   EasyEDA draws pins on a 100 mil grid relative to that origin; recentring on a
   bounding box shifts everything by half a pitch and pins land off-grid.

Pin text: the label size is **clamped to 1.27 mm** (50 mil) so labels fit a 100 mil pin
pitch, and a hidden label is written with **size 0** rather than KiCad's text `hide`
flag, which pin effects do not support.

### Footprint

| Op | Fields | Meaning |
|---|---|---|
| `PAD` | `PAD, shape, x, y, width, height, layer, net, number, hole, points, rotation, id, locked, …, plated` | `shape` ∈ `RECT`/`ELLIPSE`/`POLYGON`; `hole` > 0 means a plated hole |
| `TRACK` | `TRACK, width, layer, net, points, id, locked` | polyline; one `fp_line` per segment |
| `CIRCLE` | `CIRCLE, cx, cy, radius, width, layer, id, locked, …` | `fp_circle` |
| `SOLIDREGION` | `SOLIDREGION, layer, net, points, fill, id, …` | `fp_poly` with `(fill yes)` |
| `ARC` | `ARC, width, layer, net, "M … A …", …` | **not converted** (layout not verified) |
| `RECT` | `RECT, x, y, w, h, layer, …` | **not converted** (rare decoration) |
| `SVGNODE` | `SVGNODE~{json}` | 3D model reference: `attrs.uuid/title/c_origin/c_rotation/z` |

## Units, origin and axes

- One canvas unit is **10 mil = 0.254 mm**. Confirmed numerically, not assumed:
  C25804's pads (3.1751 × 3.4016 units) become 0.8065 × 0.8640 mm, next to KiCad's own
  0.80 × 0.95 mm for the same package.
- **Symbols** keep EasyEDA's own origin: the document head's `x`/`y` (see *Pins* above).
  A bounding-box recentre shifts pins off their 100 mil grid.
- **Footprints** are recentred on the pad bounding box, which is KiCad's convention for
  a package.
- EasyEDA's Y axis grows downwards; both symbol and footprint geometry are Y-negated.

## Layer ids

Mirrors LCSC3D's table, including its ordering: EasyEDA numbers **5/6 as paste and 7/8
as mask**.

| id | EasyEDA | KiCad | evidence |
|---|---|---|---|
| 1 / 2 | top / bottom copper | `F.Cu` / `B.Cu` | all pads |
| 3 / 4 | top / bottom silk | `F.SilkS` / `B.SilkS` | all `TRACK`s |
| 5 / 6 | top / bottom **paste** | `F.Paste` / `B.Paste` | LCSC3D's `LAYERS` |
| 7 / 8 | top / bottom **mask** | `F.Mask` / `B.Mask` | LCSC3D's `LAYERS` |
| 10 | outline | `Edge.Cuts` | — |
| 12, 15 | documentation, mechanical | `Dwgs.User` | — |
| 13 / 14 | top / bottom assembly | `F.Fab` / `B.Fab` | — |
| 99 | component shape | `Dwgs.User` | 96–116 regions per part |
| 100 / 101 | component shape / mark | `F.Fab` | same |

## Rate limiting

`easyeda.com` answers repeated product requests with an HTML **403** (919 bytes). A
3 s → 6 s backoff recovered on the third attempt; `modules.easyeda.com` was never
throttled. The client paces (350 ms), retries once, and caches responses for a week.
