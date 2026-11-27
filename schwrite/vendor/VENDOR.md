# Vendored from LCSC3D — provenance

These files are **byte-identical copies** of LCSC3D's conversion code. They are not adapted,
not renamed and not reimplemented: the whole point is that a symbol written by
`tools/export_symbols.py` is the same symbol LCSC3D itself would export.

| | |
|---|---|
| Source | `C:\Users\semia\Downloads\Workspace\LCSC3D\app\lcsc3d\` |
| Copied | 2026-11-26 |
| Files | 14, listed with SHA-256 in `SHA256SUMS.txt` |
| Verified | `import lcsc3d.eda.kicad` from this directory prints `SYMBOL_VERSION 20211014` |

## Why this exists

Before this vendoring, the KiCad libraries in `kicad_lib/` were produced by the
`lcsc-libs` skill — a **reimplementation** of LCSC3D's conversion that documents itself as
"our own code, but the conversion logic follows LCSC3D" (`lcsc-libs/references/lcsc3d-parity.md`).
It diverged in at least two ways that show on the page:

| | LCSC3D | `lcsc-libs` |
|---|---|---|
| Polyline/polygon paths | closes the path by repeating the first point when the shape is filled or a polygon | emits the raw points only |
| Symbol origin | graphics and pins share the EasyEDA origin | "centres the body" and shifts graphics, snapping to 1.27 mm — which moves the body relative to its pins |

Measured on the project's LED (C965839, `D_XL-1615SURUGC`): LCSC3D emits
`((-4.32,-5.59), (-3.81,-4.57), (-3.3,-5.08), (-4.32,-5.59))` — a closed 4-point filled
arrow; `lcsc-libs` emitted `((-3.05,-5.59), (-2.54,-4.57), (-2.03,-5.08))` — three points,
open, and 1.27 mm to the right. The LED's arrows therefore render as broken strokes sitting
off the diode body.

## Files included, and why not more

| File | Needed for |
|---|---|
| `core/errors.py`, `core/app_paths.py`, `core/app_logging.py` | the error types and the `traced` decorator the EDA modules import |
| `eda/eda_ir.py`, `eda/eda_geometry.py`, `eda/eda_targets.py`, `eda/symbol_style.py` | the intermediate representation the importer builds and the exporter consumes |
| `eda/easyeda_import.py` | EasyEDA document → IR (`parse_component`) |
| `eda/kicad.py` | IR → `.kicad_sym` (`symbol_definition`, `symbol_library`) |
| `models/model3d.py`, `models/model_cache.py` | imported by the two modules above (3D model references, not used for symbols) |

Deliberately **not** copied: the GUI (`ui/`), the storefront/backend services, and
`eda/library_files.py` (file publication, which needs LCSC3D's own transaction layer).
`tools/export_symbols.py` writes the files itself, so publication policy stays ours and the
conversion stays LCSC3D's.

## Updating

Re-copy the same 14 files from LCSC3D, regenerate `SHA256SUMS.txt`, and re-run
`tools/export_symbols.py --all`; then `pytest tests -q` and the gate in
`tools/export_symbols.py --check-existing` must both pass.
