# Data model — what the script returns and where it comes from

Reference for `scripts/lcsc.py search | detail | bom --json`. Agents can rely on
these keys; they are produced by one function (`product_payload`) for every
command, so a field never changes meaning between them.

## Part object

| Field | Type | Meaning | Notes |
|---|---|---|---|
| `lcsc` | string | LCSC part number, `C25804` | the identity you put in a BOM |
| `mpn` | string | manufacturer part number | may equal `lcsc` on cheap passives |
| `manufacturer` | string | brand as the store names it | `en_US`: `UNI-ROYAL`; `zh_CN`: `UNI-ROYAL(厚声)` |
| `description` | string | one-line description | best human summary |
| `package` | string | package / footprint name | `0603`, `LQFP-48(7x7)` |
| `category` | string | store category | first segment of the `ID` column |
| `status` | string | `Active`, `Obsolete`, `Pre-order`, `No stock` | only design in `Active` |
| `stock` | int | units in stock at lookup time | snapshot, not a promise |
| `value` | string | value for schematic use | `10K` for a `10kΩ` resistor, else the MPN |
| `currency` | string | `¥` or `US$` | taken from the price text |
| `price_tiers` | array | `[{qty, price}]`, ascending | first entry's `qty` is the MOQ |
| `price_text` | string | the ladder as stored, `US$1.0968@1/…` | order of magnitude check |
| `datasheet` | string | PDF URL, or `""` | may be absent on obscure parts |
| `product_url` | string | storefront product page | `lcsc.com/product-detail/…` or `item.szlcsc.com/{id}.html` |
| `distributor` | string | `LCSC` or `LCSC International` | tells you which site answered |
| `parameters` | array | `[{name, value}]` | headline specs first, then store order |
| `parameters_reported` | int | how many the store reported | `detail` uses the full set |
| `detail` | string | `search`, `enriched`, `failed` | `enriched` means the detail source was read |

## Search result

| Field | Meaning |
|---|---|
| `query`, `lang`, `site` | what was asked, and where it was asked |
| `page`, `pages`, `total`, `page_size` | paging context (`total` is capped at 5000 on lcsc.com) |
| `category` | the category actually used |
| `categories` | `[{id, name, count}]` — pass `id` back as `--category` |
| `scene` | `en_US` classification: `FULL_MATCH`, `PARTIAL_MATCH`, `NO_RESULT`, `PART_NUMBER`, `REDIRECT_PRODUCT_DETAIL` |
| `note` | store hint, e.g. that the result set was capped |
| `parts` | array of part objects |

## BOM result

| Field | Meaning |
|---|---|
| `lang`, `currency` | storefront used and the symbol found in the prices |
| `lines[]` | `ref`, `qty`, `request`, `part` (or `null`), `unit_price`, `extended_price`, `warnings[]` |
| `total` | sum of extended prices for resolved lines |
| `notes[]` | currency/`snapshot` caveats |

`part` is `null` when nothing relevant was found — never treat that as a zero-cost
line.

## Where the data comes from

Both sites are anonymous public storefronts; no login or key is involved.

| | `zh_CN` — szlcsc.com | `en_US` — lcsc.com |
|---|---|---|
| Search | `POST so.szlcsc.com/query/product` (fixed 24-key body, ≤30 rows) | `POST wmsc.lcsc.com/ftps/wm/search/v3/global` (classify) → `POST /ftps/wm/product/query/list` (category-scoped, ≤100 rows) |
| Detail | `GET item.szlcsc.com/{numericId}.html` → `props.pageProps.webData` | `GET wmsc.lcsc.com/ftps/wm/product/detail?productCode=C…` |
| Datasheet | `pdf_property` group → `atta.szlcsc.com` | `pdfUrl` |

Request budget: `en_US` search = 2 requests/page, detail = 1; `zh_CN` search =
1 request/page, detail = 2 (search row + item page). The client paces itself and
retries a 429/5xx once.

The full verified protocol, including the traps this script works around
(highlight markup in domestic values, case-sensitive part codes, the 5000 cap,
the mandatory `catalogIdList`, fuzzy matches), is in the project's
`KicadLibGui-LCSC/docs/PROTOCOL.md`.

## Self-contained client

`scripts/lcsc.py` imports everything from `scripts/lcsc_client/`, a vendored copy
of the KiCad LibGen LCSC storefront client (MIT, commit recorded in
`lcsc_client/README.md`). The skill needs no other project on disk — only Python
3.10+ and `requests` — so it behaves the same wherever the folder is copied.

Skill-level behaviour (candidate ranking, the confidence gate, the BOM format)
lives in `scripts/lcsc.py`; the storefront protocol lives in `lcsc_client/` and is
refreshed deliberately with `scripts/refresh_client.py` rather than edited by hand.
If the storefronts change, refresh the vendored copy and run `selftest` plus one
live search per language.
