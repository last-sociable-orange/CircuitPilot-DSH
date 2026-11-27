#!/usr/bin/env python3
"""LCSC / SZLCSC part search, detail lookup and BOM resolving for agents.

Self-contained: the storefront client lives in ``lcsc_client/`` next to this file
(a vendored copy of the KiCad LibGen LCSC implementation), so the skill needs no
other project, only Python 3.10+ and ``requests``.

    python lcsc.py check                     # verify interpreter + client
    python lcsc.py search "10k 0603 1%"      # human-readable table
    python lcsc.py search "C25804" --json    # machine-readable
    python lcsc.py detail C25804 C2040       # full parameters + datasheet
    python lcsc.py bom needs.csv             # resolve a BOM spec
    python lcsc.py selftest                  # offline check (no network)

Every part number printed comes from a storefront response: nothing is invented
or cached from assumptions.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path


def _force_utf8_streams() -> None:
    """Make the CLI independent of the console code page.

    The storefront returns Chinese category and parameter text on ``zh_CN``. On a
    Windows console ``sys.stdout`` is the locale codec (cp1252), so the first
    ``print`` of such a string raised ``UnicodeEncodeError`` and killed the whole
    lookup — which callers then reported as "no such part". ``errors="replace"``
    keeps a hostile terminal from ever turning data into a crash; the machine
    readers use ``--json``, which this does not affect.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            if (getattr(stream, "encoding", "") or "").lower().replace("-", "") != "utf8":
                stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError, OSError):
            pass


_force_utf8_streams()

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

#: Response cache next to the skill, never in the user's home: a BOM run re-reads the
#: same parts, and with cooldowns in play an uncached repeat can cost a minute.
CACHE_DIR = SCRIPTS_DIR.parent / ".cache"

try:
    from lcsc_client import parsers as _parsers
    from lcsc_client.cache import ResponseCache
    from lcsc_client.service import SearchService
    from net_policy import DEFAULT_INTERVAL, ResilientSession
except ImportError as exc:  # a missing dependency, not a missing project
    raise SystemExit(
        "This skill needs Python 3.10+ and the 'requests' package.\n"
        f"Import failed: {exc}\n"
        "Run it with an interpreter that has requests, e.g. a project virtualenv's "
        "python executable."
    ) from None


# --------------------------------------------------------------------------
# price ladders
# --------------------------------------------------------------------------

_PRICE_TIER = re.compile(r"^(?P<symbol>US\$|¥|\$)(?P<price>[0-9]+(?:\.[0-9]+)?)@(?P<qty>[0-9]+)$")


def parse_price(text: str) -> tuple[str, list[dict[str, object]]]:
    """``"¥0.0101@1/¥0.0079@10"`` -> ``("¥", [{"qty":1,"price":"0.0101"}, ...])``."""
    symbol = ""
    tiers: list[dict[str, object]] = []
    for chunk in (text or "").split("/"):
        match = _PRICE_TIER.match(chunk.strip())
        if not match:
            continue
        symbol = symbol or match.group("symbol")
        tiers.append({"qty": int(match.group("qty")), "price": match.group("price")})
    tiers.sort(key=lambda item: item["qty"])
    return symbol, tiers


def price_at(tiers: list[dict[str, object]], quantity: int) -> Decimal | None:
    """Unit price for *quantity*, using the highest tier reached."""
    chosen: Decimal | None = None
    for tier in tiers:
        if int(tier["qty"]) <= max(1, quantity):
            try:
                chosen = Decimal(str(tier["price"]))
            except InvalidOperation:
                continue
        else:
            break
    if chosen is None and tiers:
        try:
            chosen = Decimal(str(tiers[0]["price"]))
        except InvalidOperation:
            chosen = None
    return chosen


def money(value: Decimal | None, symbol: str) -> str:
    if value is None:
        return "-"
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return f"{symbol}{text}"


# --------------------------------------------------------------------------
# product serialisation
# --------------------------------------------------------------------------


def product_payload(product, *, full_parameters: bool = False) -> dict[str, object]:
    base = product.base
    symbol, tiers = parse_price(base.unit_price)
    pairs = list(product.reported_parameter_pairs()) if full_parameters else [
        (item["param"], item["value"]) for item in product.params
        if item["param"] not in ("-", "")
    ]
    return {
        "lcsc": base.distributor_product_number,
        "mpn": base.manufacturer_product_number,
        "manufacturer": base.manufacturer,
        "description": base.description,
        "package": base.package,
        "category": base.id.split("/", 1)[0] if base.id else "",
        "status": base.part_status,
        "stock": _int_or_zero(base.qty_available),
        "value": base.value,
        "currency": symbol or "",
        "price_tiers": tiers,
        "price_text": base.unit_price,
        "datasheet": base.datasheet_url,
        "product_url": base.product_url,
        "distributor": base.distributor,
        "parameters": [{"name": name, "value": value} for name, value in pairs],
        "parameters_reported": len(pairs),
        "detail": product.detail_state,
    }


def _int_or_zero(value: object) -> int:
    try:
        return int(str(value).replace(",", "").strip() or 0)
    except (TypeError, ValueError):
        return 0


def search_payload(page, *, full_parameters: bool = False) -> dict[str, object]:
    return {
        "query": page.query if hasattr(page, "query") else "",
        "page": page.page,
        "pages": page.pages,
        "total": page.total,
        "page_size": page.page_size,
        "category": page.category_id,
        "categories": [{"id": item.id, "name": item.name, "count": item.count}
                       for item in page.categories],
        "scene": page.scene,
        "note": page.note,
        "parts": [product_payload(item, full_parameters=full_parameters)
                  for item in page.items],
    }


# --------------------------------------------------------------------------
# ranking
# --------------------------------------------------------------------------

ACTIVE_WORDS = ("active", "pre-order")

#: Words that carry no identifying information in a BOM line.
_STOPWORDS = frozenset({"the", "and", "with", "for", "of", "a", "an", "smd", "smd."})


def _tokens(text: str) -> list[str]:
    """Identifying words of a query: digits kept, single characters dropped."""
    found = []
    for raw in re.split(r"[^0-9A-Za-zΩμµ%±.]+", (text or "").lower()):
        token = raw.strip(".")
        if len(token) < 2 or token in _STOPWORDS:
            continue
        found.append(token)
    return found


def confident(part: dict[str, object], query: str) -> bool:
    """Whether *part* plausibly answers *query*.

    The international storefront answers a nonsense keyword with a fuzzy
    ``PARTIAL_MATCH`` across unrelated categories, so a BOM line must be able to
    reject a candidate that shares nothing with what was asked for.  Every
    identifying token of the query must appear in the part's identity, package,
    description or parameters.
    """
    tokens = _tokens(query)
    haystack = " ".join([
        str(part.get("lcsc") or ""),
        str(part.get("mpn") or ""),
        str(part.get("description") or ""),
        str(part.get("package") or ""),
        str(part.get("value") or ""),
        " ".join(f"{item.get('name')} {item.get('value')}"
                 for item in part.get("parameters") or []),  # type: ignore[union-attr]
    ]).lower()
    if not tokens:
        return query.strip().lower() in haystack
    return all(token in haystack for token in tokens)


def score_part(part: dict[str, object], *, query: str, package: str, quantity: int):
    """Sort key: usable parts first, then exact MPN, then price, then stock."""
    status = str(part["status"] or "").lower()
    stock = int(part["stock"])
    tiers = part["price_tiers"]  # type: ignore[assignment]
    unit = price_at(tiers, quantity)  # type: ignore[arg-type]
    mpn = str(part["mpn"] or "").upper()
    wanted = query.strip().upper()

    unusable = 0
    if status and status not in ACTIVE_WORDS:
        unusable += 1
    if stock < quantity:
        unusable += 1
    if package and package.lower() not in str(part["package"] or "").lower():
        unusable += 1
    return (
        unusable,
        0 if mpn == wanted else 1,
        unit if unit is not None else Decimal("1e9"),
        -stock,
        str(part["lcsc"]),
    )


def pick_best(parts: list[dict[str, object]], *, query: str, package: str, quantity: int):
    if not parts:
        return None
    return min(parts, key=lambda item: score_part(
        item, query=query, package=package, quantity=quantity))


# --------------------------------------------------------------------------
# the client
# --------------------------------------------------------------------------


class Client:
    def __init__(self, *, language: str, interval: float, timeout: float,
                 cache_ttl: float = 0, max_wait: float = 90.0) -> None:
        # The session carries the backoff policy (see net_policy.py): shared per-origin
        # cooldowns, Retry-After, and a sign-in page is reported instead of retried.
        # With cooldowns in play a repeat lookup can cost a minute, so the vendored
        # response cache is switched on by default for the batch case.
        cache = ResponseCache(CACHE_DIR, cache_ttl) if cache_ttl > 0 else None
        session = ResilientSession(timeout=timeout, min_interval=interval, cache=cache,
                                   max_total_wait=max_wait)
        self.service = SearchService(language, timeout=timeout,
                                     min_interval=session.min_interval,
                                     cache_ttl=cache_ttl, session=session)
        self.language = language

    def search(self, query: str, *, page: int = 1, category: str = "") -> dict[str, object]:
        result = self.service.search(query, page, category_id=category)
        payload = search_payload(result)
        payload["query"] = query
        payload["lang"] = self.language
        payload["site"] = self.service.site
        return payload

    def detail(self, part: str) -> dict[str, object]:
        page = self.service.search(part, 1)
        match = next((item for item in page.items
                      if item.base.distributor_product_number == part.upper()), None)
        if match is None:
            # An empty page is not proof the part is missing: the two storefronts hold
            # different catalogues, and a refused (HTML) response also parses to zero.
            # The transport raises for refusals, so reaching here means the storefront
            # answered and simply does not list this number.
            raise SystemExit(
                f"{part} is not in {self.service.site}'s catalogue "
                f"({page.total} result(s) for that number). "
                "Check the number, or try the other storefront with --lang zh_CN / --lang en_US."
            )
        enriched, warning = self.service.enrich_safely(match)
        payload = product_payload(enriched, full_parameters=True)
        if warning:
            payload["warning"] = warning
        return payload

    def close(self) -> None:
        self.service.close()


# --------------------------------------------------------------------------
# BOM
# --------------------------------------------------------------------------


def read_spec(path: Path) -> list[dict[str, object]]:
    """A BOM spec is JSON or CSV: reference designators, a query, an optional package."""
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".csv":
        rows = []
        for row in csv.DictReader(text.splitlines()):
            rows.append({
                "ref": (row.get("ref") or row.get("reference") or "").strip(),
                "query": (row.get("query") or row.get("spec") or row.get("value") or "").strip(),
                "qty": _int_or_zero(row.get("qty") or row.get("quantity") or 1) or 1,
                "package": (row.get("package") or "").strip(),
            })
        return rows
    data = json.loads(text)
    if isinstance(data, dict):
        data = data.get("lines") or data.get("parts") or []
    return [dict(item) for item in data]


def build_bom(client: Client, spec: list[dict[str, object]], *, limit: int) -> dict[str, object]:
    lines = []
    totals = Decimal(0)
    currency = ""
    for row in spec:
        query = str(row.get("query") or "").strip()
        if not query:
            continue
        refs = str(row.get("ref") or "")
        quantity = max(1, _int_or_zero(row.get("qty") or 1))
        package = str(row.get("package") or "")
        warnings: list[str] = []

        is_part_number = bool(re.fullmatch(r"C[0-9]{1,18}", query.upper()))
        if is_part_number:
            candidates = [client.detail(query.upper())]
        else:
            page = client.search(query, page=1)
            candidates = list(page["parts"])[: max(1, limit)]
            if not page["parts"]:
                warnings.append(f"no result for {query!r}")
        best = pick_best(candidates, query=query, package=package, quantity=quantity)
        # An exact part number was already verified by detail(); a keyword must
        # still prove it matches, because the storefront answers nonsense with
        # fuzzy results from unrelated categories.
        if best is not None and not is_part_number and not confident(best, query):
            warnings.append(
                f"no confident match for {query!r} — the storefront returned "
                f"unrelated parts (closest was {best['lcsc']} {best['mpn']}); "
                "refine the query"
            )
            best = None
        if best is None:
            lines.append({"ref": refs, "qty": quantity, "request": query,
                          "part": None, "warnings": warnings or ["no candidate"]})
            continue

        stock = int(best["stock"])
        if stock < quantity:
            warnings.append(f"stock {stock} < needed {quantity}")
        tiers = best["price_tiers"] or []  # type: ignore[assignment]
        minimum = int(tiers[0]["qty"]) if tiers else 1
        if minimum > quantity:
            warnings.append(f"min order {minimum} > needed {quantity}")
        status = str(best["status"] or "")
        if status and status.lower() not in ACTIVE_WORDS:
            warnings.append(f"status is {status!r}")
        if package and package.lower() not in str(best["package"] or "").lower():
            warnings.append(f"package {best['package']!r} does not match {package!r}")
        if not best["datasheet"]:
            warnings.append("no datasheet link")

        symbol = str(best["currency"] or "")
        currency = currency or symbol
        unit = price_at(best["price_tiers"], quantity)  # type: ignore[arg-type]
        extended = (unit * quantity) if unit is not None else None
        if extended is not None:
            totals += extended
        lines.append({
            "ref": refs,
            "qty": quantity,
            "request": query,
            "part": best,
            "unit_price": money(unit, symbol),
            "extended_price": money(extended, symbol),
            "warnings": warnings,
        })
    return {
        "lang": client.language,
        "currency": currency,
        "lines": lines,
        "total": money(totals if totals else None, currency),
        "notes": [
            "Prices and stock are storefront snapshots, in "
            + ("USD" if currency == "US$" else "CNY" if currency == "¥" else "the listing currency")
            + ".",
        ],
    }


def bom_table(bom: dict[str, object]) -> str:
    header = ("| Ref | Qty | Request | LCSC # | MPN | Package | Unit | Ext. | Notes |\n"
              "|---|---|---|---|---|---|---|---|---|\n")
    rows = []
    for line in bom["lines"]:  # type: ignore[index]
        part = line.get("part")
        if not part:
            rows.append(f"| {line['ref']} | {line['qty']} | {line['request']} | "
                        f"- | - | - | - | - | {'; '.join(line['warnings'])} |")
            continue
        rows.append(
            f"| {line['ref']} | {line['qty']} | {line['request']} | {part['lcsc']} | "
            f"{part['mpn']} | {part['package']} | {line['unit_price']} | "
            f"{line['extended_price']} | {'; '.join(line['warnings'])} |"
        )
    return header + "\n".join(rows) + f"\n\n**Total:** {bom['total']}\n"


# --------------------------------------------------------------------------
# human-readable output
# --------------------------------------------------------------------------


def parts_table(parts: list[dict[str, object]], *, limit: int = 12) -> str:
    header = ("| # | LCSC # | MPN | Manufacturer | Package | Stock | From | Status "
              "| Description |\n"
              "|---|---|---|---|---|---|---|---|---|\n")
    rows = []
    for index, part in enumerate(parts[:limit], start=1):
        from_price = (part["price_tiers"] or [{}])[0]  # type: ignore[index]
        price = money(Decimal(str(from_price.get("price"))), str(part["currency"])) \
            if from_price.get("price") else "-"
        description = str(part["description"] or "")[:60]
        rows.append(f"| {index} | {part['lcsc']} | {part['mpn']} | {part['manufacturer']} | "
                    f"{part['package']} | {part['stock']:,} | {price} | {part['status']} | "
                    f"{description} |")
    return header + "\n".join(rows)


def detail_text(part: dict[str, object]) -> str:
    lines = [
        f"{part['lcsc']}  {part['mpn']}  [{part['manufacturer']}]",
        f"  {part['description']}",
        (f"  package : {part['package']}    status: {part['status']}    "
         f"stock: {int(part['stock']):,}"),
        f"  price   : {part['price_text'] or '-'}",
        f"  datasheet: {part['datasheet'] or '-'}",
        f"  product : {part['product_url'] or '-'}",
        f"  parameters ({part['parameters_reported']}):",
    ]
    for item in part["parameters"]:  # type: ignore[index]
        lines.append(f"      {item['name']:<28} {item['value']}")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# self test
# --------------------------------------------------------------------------


def selftest() -> int:
    """Offline check: price ladders, tier selection and both parser mappings."""
    fixtures = SCRIPTS_DIR.parent / "tests" / "fixtures"

    symbol, tiers = parse_price("¥0.0101@1/¥0.0079@10/¥0.0058@500")
    assert symbol == "¥" and len(tiers) == 3, "price ladder parsing"
    assert price_at(tiers, 20) == Decimal("0.0079"), "tier selection"
    assert money(Decimal("0.0101"), "¥") == "¥0.0101"

    if fixtures.exists():
        domestic = json.loads((fixtures / "domestic_search.json").read_text(encoding="utf-8"))
        row = domestic["result"]["searchResult"]["productRecordList"][0]
        payload = product_payload(_parsers.domestic_product(row), full_parameters=True)
        assert payload["lcsc"] == "C25804", "domestic mapping"
        assert payload["currency"] == "¥", "CNY symbol"

        intl = json.loads((fixtures / "international_list.json").read_text(encoding="utf-8"))
        payload = product_payload(_parsers.international_product(intl["result"]["dataList"][0]),
                                  full_parameters=True)
        assert payload["lcsc"] == "C8734", "international mapping"
        assert payload["currency"] == "US$", "USD symbol"
        best = pick_best([payload, dict(payload, stock=0, lcsc="C0")],
                         query="STM32F103C8T6", package="", quantity=1)
        assert best is not None and best["lcsc"] == "C8734", "ranking prefers in-stock"
    print("selftest OK - client in " + str(SCRIPTS_DIR / "lcsc_client"))
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lcsc.py",
        description="Search LCSC/szlcsc, read part details and resolve a BOM.",
    )
    parser.add_argument("--lang", default="en_US", choices=("en_US", "zh_CN"),
                        help="en_US searches lcsc.com (USD); zh_CN searches szlcsc.com (CNY)")
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL,
                        help="minimum seconds between storefront requests "
                             "(raised to 0.5 when positive; lower it only knowingly)")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--cache-ttl", type=float, default=0.0,
                        help="seconds to cache storefront responses (0 = always fresh). "
                             "Opt-in: the vendored client only passes cache_ttl on detail "
                             "requests, and 'detail' resolves each part through an uncached "
                             "search first, so a BOM run still hits the store per part.")
    parser.add_argument("--max-wait", type=float, default=90.0,
                        help="total seconds this call may spend waiting out storefront "
                             "cooldowns before failing (default 90)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="report interpreter and the bundled client")

    search = sub.add_parser("search", help="search by keyword or part number")
    search.add_argument("query")
    search.add_argument("--page", type=int, default=1)
    search.add_argument("--limit", type=int, default=12, help="rows to print/show")
    search.add_argument("--category", default="", help="category id from a previous search")
    search.add_argument("--json", action="store_true")

    detail = sub.add_parser("detail", help="full details for one or more part numbers")
    detail.add_argument("parts", nargs="+")
    detail.add_argument("--json", action="store_true")

    bom = sub.add_parser("bom", help="resolve a BOM spec (JSON or CSV) to part numbers")
    bom.add_argument("spec", help="path to the BOM spec file")
    bom.add_argument("--limit", type=int, default=8,
                     help="candidate results considered per line")
    bom.add_argument("--json", action="store_true")

    sub.add_parser("selftest", help="offline check, no network")

    args = parser.parse_args(argv)

    if args.command == "check":
        import requests

        print(f"python  : {sys.executable}")
        print(f"requests: {requests.__version__}")
        print(f"client  : {SCRIPTS_DIR / 'lcsc_client'}")
        return 0
    if args.command == "selftest":
        return selftest()

    client = Client(language=args.lang, interval=args.interval,
                    timeout=args.timeout, cache_ttl=args.cache_ttl,
                    max_wait=args.max_wait)
    try:
        if args.command == "search":
            payload = client.search(args.query, page=args.page, category=args.category)
            payload["parts"] = payload["parts"][: max(1, args.limit)]
            if args.json:
                print(json.dumps(payload, indent=2, ensure_ascii=False))
            else:
                print(f"{payload['query']!r} on {payload['site']}: {payload['total']} matches, "
                      f"page {payload['page']}/{payload['pages']}")
                if payload["categories"]:
                    shown = ", ".join(f"{item['name']} ({item['count']})"
                                      for item in payload["categories"][:6])
                    print(f"categories: {shown}")
                if payload["note"]:
                    print(f"note: {payload['note']}")
                print()
                print(parts_table(payload["parts"], limit=args.limit))
            return 0

        if args.command == "detail":
            results = [client.detail(part.upper()) for part in args.parts]
            if args.json:
                print(json.dumps(results if len(results) > 1 else results[0],
                                 indent=2, ensure_ascii=False))
            else:
                for payload in results:
                    print(detail_text(payload))
                    print()
            return 0

        if args.command == "bom":
            spec = read_spec(Path(args.spec).expanduser())
            bom_result = build_bom(client, spec, limit=args.limit)
            if args.json:
                print(json.dumps(bom_result, indent=2, ensure_ascii=False))
            else:
                print(bom_table(bom_result))
                for note in bom_result["notes"]:  # type: ignore[index]
                    print(f"- {note}")
            return 0
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
