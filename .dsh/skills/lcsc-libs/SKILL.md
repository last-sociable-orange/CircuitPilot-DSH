---
name: lcsc-libs
description: "Download an LCSC/SZLCSC part's datasheet, KiCad symbol, KiCad footprint and STEP 3D model from its part number (C…), converted to native KiCad 10 files. Use when a task needs a KiCad library for a real part: 'get the KiCad symbol/footprint for C25804', 'add this part to KiCad', 'download the 3D model and datasheet for <LCSC part>', or after choosing parts for a board and needing library files. Standard library only — no KiCad installation, no requests, no external tools. Do NOT use it to search for parts (use lcsc-parts) or to design circuits."
allowed-tools: Bash(python:*), Bash(python3:*)
---

# LCSC libs — datasheet, symbol, footprint, STEP

One command turns an LCSC part number into usable KiCad 10 material. The data comes
from the part's EasyEDA record (the same library LCSC publishes), converted locally.

**Never invent a part number.** Every `C…` you pass must come from a real lookup —
the `lcsc-parts` skill or the user. This skill only converts what the storefront
actually published.

## What you get

| Artefact | File | Source |
|---|---|---|
| Symbol | `symbols/<part>_<mpn>.kicad_sym` | EasyEDA symbol document |
| Footprint | `footprints/<part>_<mpn>.pretty/<part>_<mpn>.kicad_mod` | EasyEDA package document |
| 3D model | `Step/<part>_<mpn>.step` | `modules.easyeda.com` (ISO-10303-21) |
| Datasheet | `datasheets/<mpn>.pdf` | LCSC product-detail JSON `pdfUrl` |
| Manifest | `manifest.json` | what was fetched, hashes, warnings |

Everything is **KiCad 10 native**: `(version 20251024)` for symbols, `(version 20260206)`
for footprints, read from the installed KiCad 10.0.8 libraries.

## Setup check (once per session)

```bash
python scripts/lcsc_libs.py check       # interpreter, cache dir, fixtures
python scripts/lcsc_libs.py selftest    # offline: 24 geometry/writer checks, no network
```

`selftest` is the fast sanity gate: it asserts R0603 pad geometry (0.8065 × 0.8640 mm
at ±0.7534 mm) and LQFP-48 pitch (0.5 mm) straight from the recorded fixtures, so a
broken conversion is caught without touching the network.

## Fetch a part

```bash
python scripts/lcsc_libs.py fetch C25804 --out <project>/WIP          # everything
python scripts/lcsc_libs.py fetch C8734 --parts symbol,footprint      # subset
python scripts/lcsc_libs.py fetch C25804 C8734 C2040 --out <project>/WIP --json
```

`--out` is required in practice: nothing is written outside it. Typical choice is a
scratch folder such as `<project>/WIP`.

| Option | Meaning |
|---|---|
| `--parts symbol,footprint,model,datasheet` | subset of artefacts (default: all) |
| `--json` | machine-readable report instead of the table |
| `--offline` | rebuild from the cache; no network requests |
| `--model-prefix` | path written into the footprint's `(model …)` block |
| `--cache-dir`, `--cache-ttl` | response cache (default TTL 7 days, `0` disables) |
| `--interval` | seconds between requests (default 0.35) |

The default model prefix is `${KIPRJMOD}/../kicad_lib/Step`, and the STEP file is
written to the output folder's own `Step/` directory. The manifest records both where
the STEP landed and the path the footprint references — copy the file into
`<project>/../kicad_lib/Step/` (or pass `--model-prefix`) if you want KiCad to resolve
it exactly as written.

## Using the result in KiCad

1. **Symbol library**: *Preferences → Manage Symbol Libraries → Add*, pick the
   `.kicad_sym`. The symbol appears under that library's nickname.
2. **Footprint library**: *Preferences → Manage Footprint Libraries → Add*, pick the
   `.pretty` folder.
3. **3D model**: already referenced by the footprint; keep the STEP where
   `--model-prefix` says.
4. The symbol carries `LCSC`, `Manufacturer` and `Datasheet` fields, so a schematic is
   traceable back to the storefront part number.

## Read the warnings — they are the honest part of the output

A fetch can succeed partially. These warnings have specific meanings:

| Warning | Meaning |
|---|---|
| `no symbol published for this part` | EasyEDA has no symbol for this part (seen on 7 of 18 sampled parts). Footprint and STEP may still exist. |
| `no 3D model published for this part` | No STEP; the footprint is written without a `(model …)` block |
| `datasheet: no datasheet link published` | The storefront lists no PDF |
| `skipped unsupported footprint op '…'` | An op outside the mapped set was dropped — report it rather than pretending the footprint is complete |
| `an ellipse was approximated by a circle` | Kirsch/oval drawing detail lost |
| `the footprint has no silkscreen drawing` | Source has no silk; not an error |

**Do not silently paper over a warning.** If a user needs a symbol and the part has
none, say so and offer the alternatives (another C-number for the same MPN often has
one).

## Verified vs assumed — tell the user which is which

Verified by measurement (safe to state):

- **KiCad 10.0.8 itself accepts every generated file**: `kicad-cli sym upgrade` /
  `fp upgrade` parse them (reporting "not updated", i.e. already current format) and
  `sym export svg` / `fp export svg` render them, for the C25804, C8734 and C2040
  libraries;
- **pins are attached**: every pin's far end lands on the body edge (0.000 mm) for all
  five fixtures, pins sit on the 1.27 mm grid, none are stacked, and an LQFP-48 splits
  24 left / 24 right;
- **the conversion logic follows LCSC3D**, audited rule by rule in
  [`references/lcsc3d-parity.md`](references/lcsc3d-parity.md): pin dot as connection
  point, angle from connection towards the body (KiCad's `Device:D`: left 0, right 180),
  stroke width/style from the record, ellipse tessellation, pin labels clamped to
  1.27 mm with hidden labels sized 0, and EasyEDA's layer numbering (5/6 paste, 7/8
  mask, 99 → `Dwgs.User`);
- **symbols are centred on the origin** in both axes — *an improvement over LCSC3D*,
  which keeps EasyEDA's head origin and can leave a part off-centre. The centring shift
  is snapped to 1.27 mm so pins stay on grid; all five fixtures measure (±0.000,
  ±0.000) mm;
- unit factor 0.254 mm per canvas unit, confirmed against KiCad's own R0603 pads;
- pad sizes/positions/rotation and 0.5 mm LQFP-48 pitch;
- STEP files really are `ISO-10303-21`, PDFs really are `%PDF`;
- footprints use `(fill yes|no)` only — the form KiCad's own 50k-footprint library uses.

Assumed (worth a visual check in KiCad, and say so if asked):

- EasyEDA layer ids **99/100/101** are mapped to `F.Fab` — they carry manufacturing and
  assembly drawing, and this keeps them off the silkscreen. KiCad loads and plots them
  happily; whether the *content* belongs on Fab is a judgement call;
- **CIRCLE** radius/width are treated as millimetres already (a 0.1181 value beside a
  0.6-unit track width cannot both be canvas units);
- the 3D model uses `(offset 0 0 0)`; EasyEDA STEPs are usually origin-aligned, but if
  a model sits visibly wrong, that is the first thing to correct;
- EasyEDA pin electrical code **1** is mapped to `passive` (it appears on 2-pin
  passives such as C25804; mapping it to `input` would make every resistor trip ERC).

Multi-unit symbols: LCSC's EasyEDA data is **flat**. Zero `subparts` in 18 sampled
multi-section parts (LM324, TL074, LM358, 74HC00, MMDT3904, LM339), so a quad op-amp
arrives as one 14-pin symbol, exactly as published. The converter would handle
`subparts` if a part carried them, but it does not invent A/B/C/D units.

## Limits

- Standard library only; needs **Python 3.10+** (no `requests`, no KiCad).
- One part per `.kicad_sym` (by design, so parts can be added/removed independently).
- `easyeda.com` throttles: repeated product calls return an HTML 403. The client paces
  requests, retries once with backoff, and caches; if it still fails, wait and retry.
- Large STEP files (up to ~10 MB) are streamed to disk with a size cap.
- To re-verify a generated library against KiCad itself (recommended after changing the
  converter), run from a normal shell — `kicad-cli` cannot open its registry key when
  started from a Python subprocess:

```bash
mkdir -p /tmp/out
kicad-cli sym upgrade --output /tmp/out symbols/C8734_STM32F103C8T6.kicad_sym
kicad-cli fp  upgrade --output /tmp/out footprints/C8734_STM32F103C8T6.pretty
```

"… was not updated" with exit 0 means KiCad accepted the file and found it already
current.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `easyeda.com has no component record for C…` | part number wrong, or the part has no EDA data at all |
| `easyeda.com returned something other than JSON` | throttled (HTML 403): wait a minute, re-run; the cache makes retries cheap |
| `no symbol published for this part` | try another C-number for the same MPN |
| Footprint pads look offset | check `selftest` still passes; if it does, report the part number — that is data, not conversion |
| `(model …)` path does not resolve in KiCad | copy the STEP to `<project>/../kicad_lib/Step/` or re-run with `--model-prefix` |
| Cache seems stale | `python scripts/lcsc_libs.py clear-cache --yes` |

## Do / Don't

- **Do** run `selftest` first; it proves the converters still match known geometry.
- **Do** report every warning and which artefacts are missing.
- **Do** keep the manifest with the files — it records sources and hashes.
- **Do** say "assumed" when repeating the layer/subpart caveats above.
- **Don't** claim a library is KiCad-verified unless `kicad-cli` or KiCad itself accepted it.
- **Don't** invent part numbers, pin numbers, pad dimensions or datasheet links.
- **Don't** edit the generated `.kicad_sym`/`.kicad_mod` to "fix" geometry — report it.
