"""The Chinese storefront: ``szlcsc.com``.

Search is one POST to ``so.szlcsc.com``; the full parameter set and a fresher
datasheet come from the server-rendered item page on ``item.szlcsc.com``.
See ``docs/PROTOCOL.md`` §2 for the verified request and response shapes.
"""

# Vendored from KiCad LibGen LCSC (KicadLibGui-LCSC 1.0.0) at commit 60c89f8.
# Do not edit: refresh with scripts/refresh_client.py.
from __future__ import annotations

import json
import logging
import re
from html.parser import HTMLParser
from typing import Any

from .errors import DetailError, ParseError, SearchError
from .models import ProductInfo

from .base import Backend, Category, SearchPage, page_count
from .parsers import apply_domestic_detail, domestic_product
from .text import part_number, product_id

logger = logging.getLogger(__name__)

SEARCH_URL = "https://so.szlcsc.com/query/product"
ITEM_URL = "https://item.szlcsc.com/{product_id}.html"
SEARCH_ORIGIN = "https://so.szlcsc.com"
#: The storefront answers ``code: 200`` with a null ``pageSize`` above 30.
PAGE_SIZE = 30
MAX_KEYWORD = 160

SEARCH_HEADERS = {
    "Content-Type": "application/json;charset=UTF-8",
    "Origin": SEARCH_ORIGIN,
    "Referer": SEARCH_ORIGIN + "/",
}


def _search_body(keyword: str, page: int, size: int, category_id: str) -> dict[str, Any]:
    """The storefront's fixed 24-key body; empty strings mean "no filter"."""
    return {
        "catalogIdFilter": category_id or "",
        "brandIdFilter": "",
        "standardFilter": "",
        "arrangeFilter": "",
        "labelFilter": "",
        "authenticationFilter": "",
        "sortNumber": 0,
        "satisfyStockType": "",
        "startPrice": "",
        "endPrice": "",
        "demandNumber": "",
        "spotFilter": 1,
        "discountFilter": 1,
        "hasDataFile": False,
        "brandPlaceFilter": "",
        "brandOriginFilter": "",
        "secondKeyword": "",
        "smtLabelFilter": "",
        "queryProductTypeCode": "",
        "lastParamName": "",
        "keyword": keyword,
        "currentPage": page,
        "pageSize": size,
        "queryParameterValue": "",
    }


class _NextDataParser(HTMLParser):
    """Collect the character data of ``<script id="__NEXT_DATA__">``."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.inside = False
        self.chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("id") == "__NEXT_DATA__":
            self.inside = True

    def handle_data(self, data):
        if self.inside:
            self.chunks.append(data)

    def handle_endtag(self, tag):
        if tag == "script":
            self.inside = False


def item_webdata(html: bytes) -> dict[str, Any]:
    """Extract ``props.pageProps.webData`` from a server-rendered item page."""
    parser = _NextDataParser()
    try:
        parser.feed(html.decode("utf-8", errors="replace"))
    except Exception as exc:  # pragma: no cover - html.parser is very forgiving
        raise DetailError(details=str(exc)) from exc
    if not parser.chunks:
        raise DetailError("LCSC did not return the product page in the expected form.")
    try:
        payload = json.loads("".join(parser.chunks))
    except ValueError as exc:
        raise DetailError(details=f"invalid embedded JSON: {exc}") from exc
    webdata = ((payload.get("props") or {}).get("pageProps") or {}).get("webData")
    if not isinstance(webdata, dict):
        raise DetailError("LCSC returned a product page without product data.")
    return webdata


def _categories(page: dict[str, Any]) -> list[Category]:
    """The category facets this result set can be narrowed to."""
    rows = page.get("catalogGroup")
    if not isinstance(rows, list):
        return []
    found: list[Category] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("label") or "").strip()
        value = str(row.get("value") or "").strip()
        if not name or not value or value in seen:
            continue
        seen.add(value)
        count = row.get("count")
        found.append(Category(id=value, name=name,
                              count=int(count) if isinstance(count, int) else 0))
    found.sort(key=lambda item: -item.count)
    return found


class DomesticBackend(Backend):
    language = "zh_CN"
    site = "szlcsc.com"
    currency = "¥"
    page_size = PAGE_SIZE

    # -- search ----------------------------------------------------------

    def search(self, query: str, page: int = 1, *, category_id: str = "") -> SearchPage:
        keyword = (query or "").strip()[:MAX_KEYWORD]
        if not keyword and not category_id:
            raise SearchError("Enter a part number or keyword to search for.")
        page = max(1, int(page))
        logger.debug("szlcsc search keyword=%r page=%s", keyword, page)
        payload = self.session.post_json(
            SEARCH_URL, _search_body(keyword, page, PAGE_SIZE, category_id),
            headers=SEARCH_HEADERS,
        )
        if payload.get("code") != 200:
            message = str(payload.get("msg") or "").strip()
            raise SearchError(
                message or "The LCSC search failed. Retry in a moment.",
                details=f"code={payload.get('code')}",
            )
        result = payload.get("result")
        page_data = result.get("searchResult") if isinstance(result, dict) else None
        if not isinstance(page_data, dict):
            raise ParseError("LCSC returned search data this program does not understand.")
        rows = page_data.get("productRecordList")
        if not isinstance(rows, list):
            raise ParseError("LCSC returned a result page without a product list.")

        total = _as_int(page_data.get("totalCount"))
        returned_page = _as_int(page_data.get("currePage"))
        size = _as_int(page_data.get("pageSize"))
        declared_pages = _as_int(page_data.get("countPage"))
        if total is None or total < 0:
            raise ParseError("LCSC returned an invalid result count.")
        if returned_page is not None and returned_page != page:
            raise SearchError(
                "LCSC returned a different page than requested. Search again.",
                details=f"asked {page}, got {returned_page}",
            )
        if size is not None and size != PAGE_SIZE:
            raise SearchError(
                "LCSC changed its page size. Search again.",
                details=f"pageSize={size}",
            )
        if not rows and total > (page - 1) * PAGE_SIZE:
            # An empty page that claims to have results would silently hide parts.
            raise SearchError("LCSC returned an empty page. Retry the search.")

        items: list[ProductInfo] = []
        seen: set[str] = set()
        for row in rows:
            product = domestic_product(row)
            if product is None:
                continue
            key = product.base.distributor_product_number
            if key in seen:
                continue
            seen.add(key)
            items.append(product)

        pages = declared_pages if declared_pages and declared_pages > 0 else page_count(
            total, PAGE_SIZE)
        return SearchPage(
            items=items,
            total=total,
            page=page,
            page_size=PAGE_SIZE,
            pages=pages,
            categories=_categories(page_data),
            category_id=category_id,
            exact=bool(part_number(keyword) and len(items) == 1),
        )

    # -- detail ----------------------------------------------------------

    def supports_detail(self) -> bool:
        return True

    def detail(self, product: ProductInfo, *, fetch: bool = True) -> ProductInfo:
        """Enrich *product* with the item page's parameters and datasheet."""
        candidate = product.copy()
        if not fetch:
            return candidate
        identity = product_id(product.source_product_id)
        if not identity:
            identity = _identity_from_url(product.base.product_url)
        if not identity:
            identity = self._identity_from_search(product.base.distributor_product_number)
        if not identity:
            raise DetailError(
                "LCSC has no product page for this part.",
                details="no numeric product id",
            )
        try:
            body = self.session.get_bytes(ITEM_URL.format(product_id=identity),
                                          cache_ttl=self.cache_ttl)
        except SearchError as exc:
            raise DetailError(str(exc), details=exc.details) from exc
        webdata = item_webdata(body)
        enriched = apply_domestic_detail(candidate, webdata)
        logger.debug("szlcsc detail enriched %s", enriched.base.distributor_product_number)
        return enriched

    def _identity_from_search(self, part: str) -> str:
        """A last resort for a product that arrived without its numeric id."""
        if not part:
            return ""
        try:
            page = self.search(part, 1)
        except SearchError:
            return ""
        for item in page.items:
            if item.base.distributor_product_number == part:
                return product_id(item.source_product_id)
        return ""


def _identity_from_url(url: str) -> str:
    match = re.fullmatch(r"https://item\.szlcsc\.com/([0-9]{1,18})\.html", url or "")
    return match.group(1) if match else ""


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value
