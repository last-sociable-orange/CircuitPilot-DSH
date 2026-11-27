# Output contract — files and JSON

## Directory layout

`--out` is the only place anything is written.

```
<out>/
  symbols/<part>_<mpn>.kicad_sym                     one part per library
  footprints/<part>_<mpn>.pretty/<part>_<mpn>.kicad_mod
  Step/<part>_<mpn>.step                             ISO-10303-21
  datasheets/<mpn>.pdf                               %PDF
  manifest.json                                      merged across runs, keyed by part
```

Names: bundle = `<LCSC number>_<MPN>` (e.g. `C8734_STM32F103C8T6`). The symbol name is
the MPN; the footprint name equals the bundle, so the `.pretty` folder, the
`.kicad_mod` file and the `(footprint "…")` identifier are identical. The EasyEDA
package name (e.g. `LQFP-48_L7.0-W7.0-P0.50-LS9.0-BL`) is preserved in the footprint's
`tags`.

## `manifest.json`

One entry per part, keyed by part number; re-running a part replaces its entry.

```json
{
  "C25804": {
    "part": {
      "lcsc": "C25804",
      "title": "0603WAF1002T5E",
      "mpn": "0603WAF1002T5E",
      "manufacturer": "UNI-ROYAL(厚声)",
      "package": "R0603",
      "description": "10KΩ (1002) ±1%",
      "product_url": "https://lcsc.com/product-detail/…C25804.html"
    },
    "output": "…/WIP",
    "artefacts": [
      {"kind": "sym", "path": "…/symbols/C25804_0603WAF1002T5E.kicad_sym",
       "bytes": 2253, "sha256": "…"}
    ],
    "model": {
      "reference": "${KIPRJMOD}/../kicad_lib/Step/C25804_0603WAF1002T5E.step",
      "written":   "…/WIP/Step/C25804_0603WAF1002T5E.step",
      "prefix":    "${KIPRJMOD}/../kicad_lib/Step"
    },
    "sources": {
      "component": "https://easyeda.com/api/products/C25804/components",
      "model": "https://modules.easyeda.com/qAxj6KHrDKw4blvCG8QJPs7Y/{uuid}",
      "datasheet": "https://datasheet.lcsc.com/datasheet/pdf/{hash}.pdf?productCode=C25804"
    },
    "warnings": []
  }
}
```

Field notes:

- `artefacts[].kind` is the file extension without the dot — `kicad_sym`,
  `kicad_mod`, `step`, `pdf`; use `path` as the authority;
- `sha256` lets you prove a file was not edited after generation;
- `model.written` vs `model.reference` differ whenever `--model-prefix` points
  somewhere else — that gap is the thing to explain to a user;
- `warnings` is always present; an empty list means the bundle is complete.

## `--json` output

`fetch --json` prints the same structures as a list (or a single object for one part).
Failures appear as `{"part": "C…", "error": "message"}` and set exit code 1.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | every requested part produced its artefacts (warnings may still exist) |
| 1 | at least one part failed outright |
| 2 | bad arguments (e.g. an unknown `--parts` value) |

Warnings alone never change the exit code — a part with no published symbol is a
successful fetch of a part that has no symbol.
