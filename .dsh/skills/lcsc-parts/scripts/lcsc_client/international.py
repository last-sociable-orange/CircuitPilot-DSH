"""The international storefront: ``lcsc.com``.

A keyword search is two calls — a discovery call that says what the query *is*
(one exact product, a category tree, or nothing) and then a category-scoped list
call.  Search rows already carry English parameters, the USD price ladder, the
datasheet and images, so a detail request is only needed to fill a gap.
See ``docs/PROTOCOL.md`` §3.
"""

# Vendored from KiCad LibGen LCSC (KicadLibGui-LCSC 1.0.0) at commit 60c89f8.
# Do not edit: refresh with scripts/refresh_client.py.
from __future__ import annotations

import logging
from typing import Any

from .errors import DetailError, ParseError, SearchError
from .models import ProductInfo

from .base import Backend, Category, SearchPage, page_count
from .parsers import international_merge, international_product
from .text import part_number

logger = logging.getLogger(__name__)

HOME = "https://www.lcsc.com"
DISCOVERY_URL = "https://wmsc.lcsc.com/ftps/wm/search/v3/global"
LIST_URL = "https://wmsc.lcsc.com/ftps/wm/product/query/list"
DETAIL_URL = "https://wmsc.lcsc.com/ftps/wm/product/detail"
#: Verified: 20/30/50/100 are accepted and echoed in ``pageRow``.
PAGE_SIZE = 30
#: The list endpoint caps ``totalRow`` at this value.
MAX_TOTAL = 5000
MAX_KEYWORD = 160
_DISCOVERY_CACHE = 8

HEADERS = {
    "Content-Type": "application/json",
    "Origin": HOME,
    "Referer": HOME + "/",
    "Accept-Language": "en-US,en;q=0.9",
}

_EMPTY_SCENES = frozenset({"NO_RESULT", ""})


def flatten_catalogs(rows: Any, out: list[Category] | None = None) -> list[Category]:
    """Leaves of a ``catalogVOS`` tree, largest category first."""
    out = [] if out is None else out
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        children = row.get("childCatelogs") or row.get("childCatalogs")
        if children:
            flatten_catalogs(children, out)
            continue
        catalog_id = row.get("catalogId")
        if not isinstance(catalog_id, int):
            continue
        name = str(row.get("catalogNameEn") or row.get("catalogName") or "").strip()
        count = row.get("productNum")
        out.append(Category(id=str(catalog_id), name=name or f"Category {catalog_id}",
                            count=count if isinstance(count, int) else 0))
    out.sort(key=lambda item: -item.count)
    return out


class InternationalBackend(Backend):
    language = "en_US"
    site = "lcsc.com"
    currency = "US$"
    page_size = PAGE_SIZE

    def __init__(self, session=None) -> None:
        super().__init__(session)
        self._discovery: dict[str, dict[str, Any]] = {}

    # -- discovery -------------------------------------------------------

    def _discover(self, keyword: str) -> dict[str, Any]:
        cached = self._discovery.get(keyword)
        if cached is not None:
            return cached
        payload = self.session.post_json(DISCOVERY_URL, {"keyword": keyword}, headers=HEADERS)
        if payload.get("code") != 200:
            raise SearchError(
                str(payload.get("msg") or "") or "The LCSC search failed. Retry in a moment.",
                details=f"code={payload.get('code')}",
            )
        result = payload.get("result")
        if not isinstance(result, dict):
            raise ParseError("LCSC returned search data this program does not understand.")
        if len(self._discovery) >= _DISCOVERY_CACHE:
            self._discovery.pop(next(iter(self._discovery)))
        self._discovery[keyword] = result
        return result

    def _list(self, keyword: str, catalog_id: str, page: int, *, scene: str = "") -> dict[str, Any]:
        body: dict[str, Any] = {
            "keyword": "",
            "globalKeyword": keyword,
            "catalogIdList": [int(catalog_id)] if catalog_id.isdigit() else [],
            "brandIdList": [],
            "encapValueList": [],
            "isStock": False,
            "isOtherSuppliers": False,
            "isAsianBrand": False,
            "isDeals": False,
            "isRohsCert": False,
            "paramNameValueMap": {},
            "currentPage": page,
            "pageSize": PAGE_SIZE,
        }
        if scene == "FULL_MATCH":
            body["scene"] = "FULL_MATCH"
        payload = self.session.post_json(LIST_URL, body, headers=HEADERS)
        if payload.get("code") != 200:
            raise SearchError(
                str(payload.get("msg") or "") or "The LCSC product list failed. Retry in a moment.",
                details=f"code={payload.get('code')}",
            )
        result = payload.get("result")
        if not isinstance(result, dict):
            raise ParseError("LCSC returned a product list this program does not understand.")
        return result

    # -- search ----------------------------------------------------------

    def search(self, query: str, page: int = 1, *, category_id: str = "") -> SearchPage:
        keyword = (query or "").strip()[:MAX_KEYWORD]
        if not keyword:
            raise SearchError("Enter a part number or keyword to search for.")
        page = max(1, int(page))

        part = part_number(keyword)
        if part and page == 1:
            shortcut = self._single(part)
            if shortcut is not None:
                return shortcut

        logger.debug("lcsc discovery keyword=%r page=%s category=%r", keyword, page, category_id)
        result = self._discover(keyword)
        scene = str(result.get("scene") or "")

        redirect = result.get("tipProductDetailUrlVO") or {}
        if result.get("isToDetail") is True and isinstance(redirect, dict):
            target = part_number(redirect.get("productCode"))
            if target:
                single = self._single(target, scene="REDIRECT_PRODUCT_DETAIL")
                if single is not None:
                    return single

        categories = flatten_catalogs(result.get("catalogVOS"))
        if categories:
            chosen = next((item for item in categories if item.id == category_id), categories[0])
            listing = self._list(keyword, chosen.id, page, scene=scene)
            return self._page_from_list(listing, keyword, page, categories, chosen, scene)

        rows = _product_search_rows(result)
        if rows is not None:
            products = [p for p in (international_product(row) for row in rows) if p is not None]
            total = _as_int(result.get("totalCount")) or len(products)
            return SearchPage(
                items=products,
                total=total,
                page=page,
                page_size=PAGE_SIZE,
                pages=page_count(total, PAGE_SIZE),
                scene=scene,
                note=self._note(scene),
            )

        if scene in _EMPTY_SCENES or result.get("totalCount") in (0, None):
            return SearchPage(items=[], total=0, page=page, page_size=PAGE_SIZE, pages=1,
                              scene=scene, note=self._note(scene))
        raise SearchError(
            "The query was too broad for the LCSC catalogue. Try a part number or "
            "a more specific keyword.",
            details=f"scene={scene}",
        )

    def _page_from_list(self, listing: dict[str, Any], keyword: str, page: int,
                        categories: list[Category], chosen: Category, scene: str) -> SearchPage:
        rows = listing.get("dataList")
        if not isinstance(rows, list):
            raise ParseError("LCSC returned a product page without a list.")
        returned_page = _as_int(listing.get("currPage"))
        row_size = _as_int(listing.get("pageRow"))
        total = _as_int(listing.get("totalRow"))
        if total is None:
            total = _as_int(listing.get("actualTotalRow"))
        if returned_page is not None and returned_page != page:
            raise SearchError("LCSC returned a different page than requested. Search again.",
                              details=f"asked {page}, got {returned_page}")
        if row_size is not None and row_size != PAGE_SIZE:
            raise SearchError("LCSC changed its page size. Search again.",
                              details=f"pageRow={row_size}")
        if total is None or total < 0:
            raise ParseError("LCSC returned an invalid result count.")

        items: list[ProductInfo] = []
        seen: set[str] = set()
        for row in rows:
            product = international_product(row)
            if product is None:
                continue
            key = product.base.distributor_product_number
            if key in seen:
                continue
            seen.add(key)
            items.append(product)
        if not items and total > (page - 1) * PAGE_SIZE:
            raise SearchError("LCSC returned an empty page. Retry the search.")

        capped = min(total, MAX_TOTAL)
        pages = page_count(capped, PAGE_SIZE)
        note = self._note(scene)
        if total > MAX_TOTAL:
            note = (note + " " if note else "") + (
                f"LCSC only exposes the first {MAX_TOTAL} matches; narrow the keyword "
                "or pick a category."
            )
        return SearchPage(
            items=items,
            total=capped,
            page=page,
            page_size=PAGE_SIZE,
            pages=pages,
            categories=categories,
            category_id=chosen.id,
            scene=scene,
            note=note,
        )

    @staticmethod
    def _note(scene: str) -> str:
        if scene in ("PARTIAL_MATCH", "REDIRECT_PRODUCT_DETAIL"):
            return ""
        if scene == "FULL_MATCH":
            return ""
        return ""

    def _single(self, part: str, *, scene: str = "") -> SearchPage | None:
        """A one-row page for a known LCSC part number, or ``None`` if unknown."""
        product = self._fetch_detail(part)
        if product is None:
            return None
        return SearchPage(items=[product], total=1, page=1, page_size=PAGE_SIZE, pages=1,
                          scene=scene or "PART_NUMBER", exact=True)

    # -- detail ----------------------------------------------------------

    def supports_detail(self) -> bool:
        return True

    def detail(self, product: ProductInfo, *, fetch: bool = True) -> ProductInfo:
        candidate = product.copy()
        if not fetch or candidate.detail_state == "enriched":
            return candidate
        part = part_number(product.base.distributor_product_number)
        if not part:
            raise DetailError("This record has no LCSC part number.")
        full = self._fetch_detail(part)
        if full is None:
            raise DetailError("LCSC has no details for this part number.")
        if full.base.distributor_product_number != part:
            # Never merge a stale or redirected page into another record.
            raise DetailError("LCSC returned a different product than requested.")
        merged = international_merge(candidate, full)
        if not merged.base.datasheet_url and full.base.datasheet_url:
            merged.base.datasheet_url = full.base.datasheet_url
        return merged

    def _fetch_detail(self, part: str) -> ProductInfo | None:
        """``None`` when the store answers with an empty result (unknown part)."""
        try:
            payload = self.session.get_json(DETAIL_URL, headers=HEADERS,
                                            params={"productCode": part},
                                            cache_ttl=self.cache_ttl)
        except SearchError as exc:
            raise DetailError(str(exc), details=exc.details) from exc
        if payload.get("code") != 200:
            raise DetailError("LCSC could not return this product's details.",
                              details=f"code={payload.get('code')}")
        row = payload.get("result")
        if not isinstance(row, dict) or not (row.get("productCode") or row.get("productModel")):
            return None
        product = international_product(row)
        if product is None:
            return None
        product.detail_state = "enriched"
        return product


def _product_search_rows(result: dict[str, Any]) -> list[Any] | None:
    """Rows from the ``productSearchResultVO`` branch, or ``None`` if absent."""
    block = result.get("productSearchResultVO")
    if not isinstance(block, dict):
        return None
    rows = block.get("productList")
    return rows if isinstance(rows, list) else None


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value
