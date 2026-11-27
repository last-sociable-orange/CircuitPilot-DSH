---
name: lcsc-parts
description: "Search LCSC / SZLCSC (立创商城) for electronic components by keyword, part number or spec, read full part details (parameters, price ladder, stock, datasheet URL), and resolve a circuit's parts list to LCSC part numbers with prices. Use this skill whenever a task needs LCSC parts: choosing components for a circuit, sourcing a BOM, checking stock/price/MOQ, finding a datasheet by part, or when the user says 'find a part on LCSC', '立创商城找料', 'LCSC part number for <value>', 'source this BOM'. Do NOT use it for DigiKey/Mouser lookups (use digikey-search), for general web search, or to answer questions that need no live part data."
allowed-tools: Bash(python:*), Bash(python3:*)
---

# LCSC parts — search, details, BOM

One script does the work, and it is **self-contained**: the storefront client is
vendored inside the skill (`scripts/lcsc_client/`), so nothing else in the
workspace is required — only Python 3.10+ and `requests`. It talks to the real
storefronts, so every part number it prints exists and was just looked up.

**Hard rule: never invent or "remember" an LCSC part number.** Every `C…` number
you put in a design or a BOM must come from a tool result in this session. If a
search returns nothing usable, say so — do not substitute a plausible part.

## Setup check (do this once per session)

```bash
python scripts/lcsc.py check      # interpreter, requests version, client location
python scripts/lcsc.py selftest   # offline, no network
```

`check` prints the interpreter, the `requests` version and the bundled client
path; `selftest` asserts the price/tier logic and both parser mappings against
bundled fixtures.

- If `requests` is missing, run the script with an interpreter that has it (a
  project virtualenv, or `pip install requests`). Nothing else is needed.
- Paths above are relative to this skill's folder; from the workspace root they
  are `skills/lcsc-parts/scripts/lcsc.py`.

## Which storefront

`--lang` picks both the site and the parameter language. Default `en_US`.

| `--lang` | Site | Currency | Parameters | Use when |
|---|---|---|---|---|
| `en_US` | lcsc.com | `US$` | English (`Resistance`, `Voltage - Supply`) | the design/BOM is in English, or you want USD pricing |
| `zh_CN` | szlcsc.com | `¥` | Chinese (`阻值`, `工作电压`) | the user writes Chinese or wants CNY prices and domestic stock |

The same MPN usually exists on both, but the price ladders, stock and MOQ figures
differ — state which one a number came from.

## Workflow 1 — find parts

```bash
python skills/lcsc-parts/scripts/lcsc.py search "10k 0603 1%"
python skills/lcsc-parts/scripts/lcsc.py search "STM32F103C8T6" --limit 5 --json
python skills/lcsc-parts/scripts/lcsc.py search "100nF 0603 50V" --category 1199
```

- Argue in **spec terms**, not marketing terms: `10k 0603 1%`, `100nF 0603 50V X7R`,
  `LDO 3.3V 500mA SOT-23-5`, `USB-C receptacle 16P`.
- The output lists the matching **categories** with counts. The store is
  category-scoped, so if the top category is wrong, re-run with
  `--category <id>` from that list.
- `--page N` walks further pages; both stores return 30 raw rows per page.
- Exact part number: `search "C25804"` or `detail C25804` (one request, no guessing).

## Workflow 2 — verify one part

```bash
python skills/lcsc-parts/scripts/lcsc.py detail C25804
python skills/lcsc-parts/scripts/lcsc.py detail C8734 C2040 --json
```

Check, in this order, before you commit to a part:

1. **Status** — `Active` only. `Obsolete` / `Pre-order` / `No stock` are red flags.
2. **Stock** ≥ quantity you need (`stock` field).
3. **MOQ** — the first price tier's `qty` is the minimum order; a 100-piece
   minimum is normal for passives and changes how you quote a 4-piece BOM.
4. **Package** matches the footprint you will use (`0603`, `LQFP-48(7x7)`, …).
5. **Parameters** — the electrical spec you actually need (voltage rating,
   tolerance, current, temperature range). Read them, don't assume.
6. **Datasheet** — `datasheet` URL is present and points at a PDF.

## Workflow 3 — resolve a BOM

Write the needs as JSON or CSV, then let the script pick real parts, price them at
the requested quantity and flag anything doubtful.

```json
{"lines": [
  {"ref": "R1,R2", "query": "10k 0603 1%", "qty": 4, "package": "0603"},
  {"ref": "C1,C2", "query": "100nF 0603 50V X7R", "qty": 2, "package": "0603"},
  {"ref": "U1", "query": "STM32F103C8T6", "qty": 1},
  {"ref": "D1", "query": "C25804", "qty": 10}
]}
```

```csv
ref,qty,query,package
R1;R2,4,10k 0603 1%,0603
U1,1,STM32F103C8T6,
```

```bash
python skills/lcsc-parts/scripts/lcsc.py bom needs.json
python skills/lcsc-parts/scripts/lcsc.py bom needs.csv --json
```

Selection order per line: usable parts first (active, in stock, package match) →
exact MPN → lowest unit price at the requested quantity → highest stock.

A line is left **unresolved** (`-`) rather than guessed when the storefront's
answer shares nothing with the query — see the fuzzy-match note under *Limits*.
Warnings you will see, and what they mean:

| Warning | Meaning |
|---|---|
| `stock N < needed M` | Not enough on hand at the time of the lookup |
| `min order N > needed M` | MOQ above what the design needs (buy extra or pick another part) |
| `status is 'Obsolete'` | Do not design it in |
| `package 'X' does not match 'Y'` | Footprint mismatch — the wrong variant was returned |
| `no datasheet link` | Verify the part another way before designing it in |
| `no confident match for …` | Nothing relevant was found; refine the query |

## Workflow 4 — design a circuit and emit a BOM

1. **Decompose** the requirement into blocks (power entry, regulation, MCU,
   interfaces, protection) and write down the *numbers* each block needs.
2. **Turn each block into search specs** — value, package preference, rating,
   tolerance. Prefer generic, widely stocked parts for passives.
3. **Search and verify** every candidate with `detail` before using it.
4. **Assemble** `needs.json`, run `bom`, and read every warning.
5. **Review** the result for what a parts tool cannot know: decoupling per power
   pin, pull-ups on I²C/reset/boot, ESD and reverse-polarity protection, connector
   pinout, voltage derating, and whether a substitute is pin-compatible.
6. **Report** the BOM table plus: currency and storefront, lookup date, every
   unresolved line, and every MOQ/stock warning. Never hide a warning.

A worked example (all numbers verified in this session, `en_US`):

```
| Ref | Qty | Request | LCSC # | MPN | Package | Unit | Ext. |
| R1,R2 | 4 | 10k 0603 1% | C2906982 | FRC0603F1002TS | 0603 | US$0.0016 | US$0.0064 |
| C1,C2 | 2 | 100nF 0603 50V X7R | C52711259 | CGA0603X7R104M500JT | 0603 | US$0.0037 | US$0.0074 |
| U1 | 1 | STM32F103C8T6 | C8734 | STM32F103C8T6 | LQFP-48(7x7) | US$1.4756 | US$1.4756 |
```

## Reading the JSON

`--json` on `search`, `detail` and `bom` emits a stable shape: `lcsc`, `mpn`,
`manufacturer`, `package`, `description`, `status`, `stock`, `value`,
`currency`, `price_tiers[{qty, price}]`, `price_text`, `datasheet`, `product_url`,
`parameters[{name, value}]`. The full contract and the field semantics are in
[`references/data-model.md`](references/data-model.md).

`parameters` are ordered with the headline specs (value, tolerance, power,
voltage, temperature, package) first, so the first few entries are usually the
ones that matter.

## Limits and pitfalls

- **The international store is category-scoped.** A keyword search resolves to
  one category (the largest match). If the part you want is in another category,
  pass `--category` from the reported list.
- **Nonsense queries are not "no results".** lcsc.com answers a meaningless
  keyword with a fuzzy match across thousands of unrelated products. `bom`
  refuses such a candidate; when you use `search` yourself, check that the
  category and description actually match what you asked for.
- **Result sets are capped at 5000** on the international store, and 30 rows come
  back per page on both. Narrow the query or use a category instead of paging
  deep.
- **Prices and stock are snapshots**, not quotes. `US$0.0016@100` means "0.16 cents
  each when buying 100"; `from` prices in the table are the cheapest tier entry.
- **No JLCPCB "basic/extended" flag.** This tool reports LCSC data only; if the
  board will be assembled by JLCPCB, confirm part availability in JLCPCB's own
  parts library before relying on it.
- **No login, no account, no personal data.** The endpoints are the public
  storefront front ends (documented in the project's `docs/PROTOCOL.md`), so they
  can change without notice; if a call starts failing structurally, re-run the
  project's `tools/probe_endpoints.py`.
- **Be polite.** Default 350 ms between requests (`--interval`). Do not run a
  search loop over hundreds of queries; refine instead.
- `zh_CN` spends two requests per detailed part (search row + item page). Search
  rows alone already carry price, stock and the datasheet.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `This skill needs Python 3.10+ and the 'requests' package` | run with an interpreter that has `requests`, or `pip install requests` |
| `LCSC is rate limiting requests` | wait the suggested seconds, then retry once; don't tighten `--interval` |
| Empty result list | drop constraints (drop the tolerance, widen the package), or the value may not exist on that storefront |
| Wrong-looking parts | add `--category`, or search by exact MPN / LCSC number |
| `stock 0` everywhere | the part exists but is out of stock; pick an equivalent MPN |
| Datasheet link 404s | give the user `product_url` instead; do not fabricate a datasheet URL |

## Do / Don't

- **Do** verify every part with `detail` before it enters a design.
- **Do** quote the storefront and currency for any price you repeat.
- **Do** surface every BOM warning and every unresolved line.
- **Do** prefer parts with healthy stock and an `Active` status.
- **Don't** invent LCSC numbers, MPNs, prices, stock figures or datasheets.
- **Don't** treat a fuzzy match as a hit — check the description.
- **Don't** claim a part is JLCPCB-basic, RoHS-certified at JLCPCB level, or in
  stock beyond what the tool returned.
