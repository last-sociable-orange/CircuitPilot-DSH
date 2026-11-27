"""Raw storefront JSON to :class:`~kicad_core.models.ProductInfo`.

Both backends produce the same 80-column record, so every rule that is not
site-specific lives here: the price ladder grammar, the 32 parameter slots, the
``Value`` derivation, the status wording and the image handling.
"""

# Vendored from KiCad LibGen LCSC (KicadLibGui-LCSC 1.0.0) at commit 60c89f8.
# Do not edit: refresh with scripts/refresh_client.py.
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .errors import DetailError, ParseError
from .models import PARAM_COUNT, ProductInfo

from .text import (
    derive_value,
    format_price,
    long_text,
    part_number,
    product_id,
    public_url,
    quantity,
    text,
)

CNY = "¥"
USD = "US$"

#: At most this many price tiers are written into ``UnitPrice``.
MAX_PRICE_TIERS = 6

#: Parameters whose value is also the KiCad ``Value`` (matched case-insensitively).
VALUE_PARAMETER_NAMES = frozenset(
    {
        "阻值",
        "容值",
        "感值",
        "阻抗",
        "resistance",
        "capacitance",
        "inductance",
        "impedance",
        "resistance - ",
    }
)

#: Headline specifications float to the front of the 32 slots so that a part with
#: more than 32 parameters never loses the values a component library needs.
KEY_SPEC_ORDER_ZH = (
    "阻值", "容值", "感值", "阻抗", "容差", "精度", "功率", "额定功率",
    "工作电压", "额定电压", "耐压", "工作电流", "输出电流", "饱和电流",
    "工作温度", "温度系数", "封装", "类型", "商品目录",
)
KEY_SPEC_ORDER_EN = (
    "Resistance", "Capacitance", "Inductance", "Impedance", "Tolerance",
    "Power(Watts)", "Power", "Voltage - Supply", "Voltage Rating", "Rated Voltage",
    "Current - Output", "Current - Saturation", "Operating Temperature",
    "Temperature Coefficient", "Package / Case", "Type", "Category",
)

_STOP_SALE_CYCLES = frozenset({"sold_out", "stop_product"})


def _pairs_from_map(mapping: Any) -> list[tuple[str, str]]:
    """``{"阻值": "10kΩ"}`` -> ``[("阻值", "10kΩ")]``, markup-free and de-duped."""
    if not isinstance(mapping, dict):
        return []
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for name, value in mapping.items():
        clean_name = text(name, 120)
        clean_value = long_text(value, 4096)
        if not clean_name or not clean_value or clean_name in seen:
            continue
        seen.add(clean_name)
        pairs.append((clean_name, clean_value))
    return pairs


def _pairs_from_list(rows: Any, *, name_key: str, value_keys: tuple[str, ...]) -> list[tuple[str, str]]:
    if not isinstance(rows, list):
        return []
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = text(row.get(name_key), 120)
        if not name or name in seen:
            continue
        value = ""
        for key in value_keys:
            value = long_text(row.get(key), 4096)
            if value:
                break
        if not value:
            continue
        seen.add(name)
        pairs.append((name, value))
    return pairs


def order_parameters(pairs: Iterable[tuple[str, str]], priority: tuple[str, ...]) -> list[tuple[str, str]]:
    """Put the headline specifications first, then keep the store's own order."""
    materialised = list(pairs)
    ranked: dict[str, int] = {name.lower(): index for index, name in enumerate(priority)}
    unranked = len(ranked)

    def sort_key(item: tuple[int, tuple[str, str]]) -> tuple[int, int]:
        index, (name, _value) = item
        return (ranked.get(name.strip().lower(), unranked), index)

    return [pair for _index, pair in sorted(enumerate(materialised), key=sort_key)]


def parameter_slots(pairs: Iterable[tuple[str, str]]) -> list[dict[str, str]]:
    """Exactly :data:`PARAM_COUNT` ``{"param", "value"}`` slots, ``-`` when unused."""
    slots = [{"param": name or "-", "value": value or "-"} for name, value in pairs]
    slots = slots[:PARAM_COUNT]
    while len(slots) < PARAM_COUNT:
        slots.append({"param": "-", "value": "-"})
    return slots


def all_parameters(pairs: Iterable[tuple[str, str]]) -> list[dict[str, str]]:
    """Every reported parameter, for the "view all" dialog."""
    return [{"param": name, "value": value} for name, value in pairs]


# ---------------------------------------------------------------------------
# prices
# ---------------------------------------------------------------------------


def _join_tiers(tiers: list[tuple[int, str]], symbol: str) -> str:
    shown = tiers[:MAX_PRICE_TIERS]
    return "/".join(f"{symbol}{price}@{start}" for start, price in shown)


def domestic_price(vo: dict[str, Any]) -> str:
    """CNY ladder from a domestic ``productVO``; ``""`` when the store hides it."""
    if vo.get("isShowPrice") is False:
        return ""
    rows = vo.get("productPriceList")
    if not isinstance(rows, list):
        return ""
    tiers: list[tuple[int, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        start = quantity(row.get("startPurchasedNumber"))
        if start is None:
            start = quantity(row.get("spNumber"))
        price = format_price(row.get("productPrice") if row.get("productPrice") is not None
                             else row.get("thePrice"))
        if not start or not price:
            continue
        tiers.append((start, price))
    tiers.sort(key=lambda item: item[0])
    deduped: dict[int, str] = {}
    for start, price in tiers:
        deduped.setdefault(start, price)
    return _join_tiers(list(deduped.items()), CNY)


def international_price(row: dict[str, Any]) -> str:
    """USD ladder from an international product row.

    ``usdPrice`` is the price; ``productPrice`` is the CNY figure and must never be
    substituted, or one record would mix two currencies.  An empty ladder is a
    valid answer (``isShowForeignPrice: false``).
    """
    if row.get("isShowForeignPrice") is False:
        return ""
    rows = row.get("productPriceList")
    if not isinstance(rows, list):
        return ""
    tiers: list[tuple[int, str]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        start = quantity(item.get("ladder"))
        price = format_price(item.get("usdPrice"))
        if not start or not price:
            continue
        tiers.append((start, price))
    tiers.sort(key=lambda item: item[0])
    deduped: dict[int, str] = {}
    for start, price in tiers:
        deduped.setdefault(start, price)
    return _join_tiers(list(deduped.items()), USD)


# ---------------------------------------------------------------------------
# lifecycle
# ---------------------------------------------------------------------------


def domestic_status(vo: dict[str, Any]) -> str:
    """Wording for ``PartStatus`` from the store's stop-sale flags."""
    if vo.get("productUnsealVendition") == "no":
        return "Obsolete"
    cycle = str(vo.get("productCycle") or "").strip().lower()
    if cycle in _STOP_SALE_CYCLES:
        return "Obsolete"
    if cycle and cycle != "normal":
        return cycle.replace("_", " ").title()
    if vo.get("productStockStatus") == "no":
        return "No stock"
    return "Active"


def international_status(row: dict[str, Any]) -> str:
    if row.get("isPreSale") is True:
        return "Pre-order"
    if row.get("isForbid") is True:
        return "Obsolete"
    cycle = str(row.get("productCycle") or "").strip().lower()
    if cycle in _STOP_SALE_CYCLES:
        return "Obsolete"
    return "Active"


# ---------------------------------------------------------------------------
# images
# ---------------------------------------------------------------------------


def domestic_images(vo: dict[str, Any]) -> list[str]:
    """Product photographs only, at full size.

    ``luceneBreviaryImageUrls`` is a ``<$>``-joined list that also contains brand
    certificates; those live under ``/upload/public/brand/`` and are dropped.
    """
    raw = vo.get("luceneBreviaryImageUrls") or vo.get("breviaryImageUrl") or ""
    candidates = raw.split("<$>") if isinstance(raw, str) else raw if isinstance(raw, list) else []
    found: list[str] = []
    for candidate in candidates:
        url = public_url(candidate)
        if not url or "/upload/public/product/" not in url:
            continue
        url = url.replace("/product/breviary/", "/product/source/")
        if url not in found:
            found.append(url)
    return found


def international_images(row: dict[str, Any]) -> list[str]:
    raw = row.get("productImages")
    candidates = raw if isinstance(raw, list) else []
    if not candidates:
        candidates = [row.get("productImageUrlBig") or row.get("productImageUrl")]
    found: list[str] = []
    for candidate in candidates:
        url = public_url(candidate)
        if url and url not in found:
            found.append(url)
    return found


# ---------------------------------------------------------------------------
# datasheets
# ---------------------------------------------------------------------------


def _datasheet_from_file(file: Any) -> str:
    if not isinstance(file, dict):
        return ""
    for key in ("linkAddress", "fileUrl"):
        raw = file.get(key)
        url = public_url(raw)
        if url:
            return url
        if isinstance(raw, str) and raw.startswith("/upload/public/pdf/"):
            return "https://atta.szlcsc.com" + raw
    return ""


def _datasheet_from_record(record: Any) -> str:
    """First file of the ``pdf_property`` group of a product record.

    Both the search rows and the item page use the same ``fileTypeVOList``
    structure, so this helper serves both.  Certification, MSDS and industry
    notices live in sibling groups and are ignored.
    """
    if not isinstance(record, dict):
        return ""
    for group in record.get("fileTypeVOList") or []:
        if not isinstance(group, dict) or group.get("fileType") != "pdf_property":
            continue
        for file in group.get("detailVOList") or []:
            url = _datasheet_from_file(file)
            if url:
                return url
    return ""


def domestic_datasheet(webdata: dict[str, Any]) -> str:
    """The item page's ``pdf_property`` group, then the legacy single-PDF field."""
    record = webdata.get("productRecord")
    found = _datasheet_from_record(record)
    if found:
        return found
    return _datasheet_from_file(webdata.get("pdfFileDetailVO"))



# ---------------------------------------------------------------------------
# products
# ---------------------------------------------------------------------------


def _identity(category: str, mpn: str, part: str) -> str:
    """``ID`` keeps the DigiKey-style ``category/MPN`` shape KiCad users expect."""
    category = category or "LCSC"
    return f"{category}/{mpn or part}"


def _stock(*candidates: Any) -> str:
    for candidate in candidates:
        value = quantity(candidate)
        if value is not None:
            return str(value)
    return "0"


def domestic_product(row: dict[str, Any]) -> ProductInfo | None:
    """Map one ``productRecordList`` entry, or ``None`` when it is not a part."""
    if not isinstance(row, dict):
        return None
    vo = row.get("productVO")
    if not isinstance(vo, dict):
        return None
    part = part_number(vo.get("productCode"))
    if not part:
        return None

    pairs = order_parameters(_pairs_from_map(row.get("paramLinkedMap")), KEY_SPEC_ORDER_ZH)
    mpn = text(vo.get("productModel"), 160)
    category = text(vo.get("productType"), 120)

    product = ProductInfo()
    base = product.base
    base.id = _identity(category, mpn, part)
    base.description = text(vo.get("productName"), 500) or mpn or part
    base.keywords = long_text(vo.get("productIntro") or vo.get("remark"), 4000)
    base.value = text(derive_value(mpn, pairs, VALUE_PARAMETER_NAMES), 160) or mpn
    base.manufacturer = text(vo.get("productGradePlateName"), 160)
    base.manufacturer_product_number = mpn or part
    base.package = text(vo.get("encapsulationModel"), 120)
    base.part_status = domestic_status(vo)
    base.qty_available = _stock(row.get("totalStockNumber"), vo.get("validStockNumber"),
                                vo.get("stockNumber"))
    base.distributor = "LCSC"
    base.distributor_product_number = part
    base.unit_price = domestic_price(vo)
    identity = product_id(vo.get("productId"))
    base.product_url = f"https://item.szlcsc.com/{identity}.html" if identity else (
        f"https://so.szlcsc.com/global.html?k={part}"
    )
    # Search rows already carry the document groups, so the datasheet link is
    # usable before (and without) the item-page enrichment.
    base.datasheet_url = _datasheet_from_record(vo)

    product.params = parameter_slots(pairs)
    product.source_product_id = identity
    product.source_parameters = all_parameters(pairs)
    product.detail_state = "search"
    return product


def apply_domestic_detail(product: ProductInfo, webdata: dict[str, Any]) -> ProductInfo:
    """Merge an item page into a search-row product.

    The item page owns the full parameter set, the datasheet and the description;
    it has **no** price ladder and a stale numeric id is possible, so commercial
    fields and the identity stay as the search row reported them.
    """
    if not isinstance(webdata, dict):
        raise DetailError()
    record = webdata.get("productRecord")
    record = record if isinstance(record, dict) else {}
    if not record:
        raise DetailError("LCSC returned no product details for this part.")
    part = part_number(record.get("productCode"))
    if not part or part != product.base.distributor_product_number:
        raise ParseError("LCSC returned a different product than requested.")

    pairs = order_parameters(
        _pairs_from_list(webdata.get("paramList"),
                         name_key="parameterName",
                         value_keys=("parameterDetailValue", "parameterValue")),
        KEY_SPEC_ORDER_ZH,
    )
    if pairs:
        product.params = parameter_slots(pairs)
        product.source_parameters = all_parameters(pairs)
        product.base.value = text(derive_value(product.mpn, pairs, VALUE_PARAMETER_NAMES), 160) or product.mpn

    if not product.base.description or len(product.base.description) < 12:
        product.base.description = text(record.get("productName"), 500) or product.base.description
    product.base.keywords = product.base.keywords or long_text(record.get("remark"), 4000)
    product.base.package = text(record.get("encapsulationModel"), 120) or product.base.package
    product.base.manufacturer = text(record.get("productGradePlateName"), 160) or product.base.manufacturer
    if record.get("fileTypeVOList") is not None or record.get("productName"):
        # Only trust the item page's stop-sale flags when it reports them.
        if record.get("productCycle"):
            product.base.part_status = domestic_status(record)
    stock = _stock(webdata.get("totalStockNumber"), record.get("validStockNumber"),
                   record.get("stockNumber"))
    if stock != "0" or product.base.qty_available in ("", "0"):
        product.base.qty_available = stock
    product.base.datasheet_url = domestic_datasheet(webdata) or product.base.datasheet_url
    product.source_product_id = product_id(record.get("productId")) or product.source_product_id
    product.detail_state = "enriched"
    return product


def international_product(row: dict[str, Any]) -> ProductInfo | None:
    """Map one international product object (search row or detail payload)."""
    if not isinstance(row, dict):
        return None
    part = part_number(row.get("productCode"))
    if not part:
        return None

    pairs = order_parameters(
        _pairs_from_list(row.get("paramVOList"), name_key="paramNameEn",
                         value_keys=("paramValueEn", "paramValue")),
        KEY_SPEC_ORDER_EN,
    )
    mpn = text(row.get("productModel"), 160)
    category = text(row.get("wmCatalogNameEn") or row.get("catalogName"), 120)
    intro = text(row.get("productIntroEn"), 500)
    name = text(row.get("productNameEn"), 500)

    product = ProductInfo()
    base = product.base
    base.id = _identity(category, mpn, part)
    # ``productNameEn`` is often a one-liner ("A microcontroller") while
    # ``productIntroEn`` carries the real specification; keep the more useful one.
    base.description = max((name, intro), key=len) or mpn or part
    base.keywords = (long_text(row.get("productDescEn"), 4000)
                     or (intro if base.description != intro else ""))
    base.value = text(derive_value(mpn, pairs, VALUE_PARAMETER_NAMES), 160) or mpn
    base.manufacturer = text(row.get("brandNameEn"), 160)
    base.manufacturer_product_number = mpn or part
    base.package = text(row.get("encapStandard"), 120)
    base.part_status = international_status(row)
    base.qty_available = _stock(row.get("stockNumber"), row.get("stockSz"))
    base.distributor = "LCSC International"
    base.distributor_product_number = part
    base.unit_price = international_price(row)
    base.product_url = f"https://www.lcsc.com/product-detail/{part}.html"
    base.datasheet_url = public_url(row.get("pdfUrl"))

    product.params = parameter_slots(pairs)
    product.source_product_id = product_id(row.get("productId"))
    product.source_parameters = all_parameters(pairs)
    product.detail_state = "search"
    return product


def international_merge(search: ProductInfo, detail: ProductInfo) -> ProductInfo:
    """Fold a detail payload into an already-mapped search row."""
    merged = search.copy()
    if detail.base.datasheet_url:
        merged.base.datasheet_url = detail.base.datasheet_url
    if detail.base.description and len(detail.base.description) > len(merged.base.description):
        merged.base.description = detail.base.description
    if len(detail.source_parameters) >= len(merged.source_parameters):
        merged.params = [dict(item) for item in detail.params]
        merged.source_parameters = [dict(item) for item in detail.source_parameters]
        merged.base.value = detail.base.value
    merged.source_product_id = detail.source_product_id or merged.source_product_id
    merged.detail_state = "enriched"
    return merged
