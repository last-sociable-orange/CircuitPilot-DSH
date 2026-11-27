"""Part data: what the storefront said, and what a BOM line asks for.

Two shapes live here:

``Part``
    one LCSC part, built from ``lcsc-parts detail --json`` (or a file holding the
    same payload). Every field the database needs comes from here.

``BomLine``
    one row of the designer's BOM: the part number, optionally a value, an
    explicit symbol/footprint override, and nothing else that the skill would
    have to guess.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Parameters that would duplicate a dedicated column if they were also stored
#: as ParamNN/ValueNN. Everything else the store reported is kept.
COLUMN_DUPLICATES = {
    "manufacturer",
    "manufacturer part number",
    "mfr",
    "mfr part number",
    "mfrpartnumber",
    "category",
    "类别",
    "商品编号",
}

#: The store's category field, used for the ``ID`` column's first segment.
DEFAULT_CATEGORY = "LCSC"


@dataclass
class Part:
    lcsc: str = ""
    mpn: str = ""
    manufacturer: str = ""
    description: str = ""
    package: str = ""
    category: str = ""
    status: str = ""
    stock: int = 0
    value: str = ""
    currency: str = ""
    price_tiers: list[dict[str, Any]] = field(default_factory=list)
    price_text: str = ""
    datasheet: str = ""
    product_url: str = ""
    distributor: str = "LCSC"
    parameters: list[dict[str, str]] = field(default_factory=list)
    keywords: str = ""

    # -- construction ---------------------------------------------------

    @classmethod
    def from_detail(cls, payload: dict[str, Any]) -> Part:
        """Build from one ``lcsc-parts`` part object.

        Missing keys are tolerated field by field: a storefront that stops
        returning ``price_tiers`` must degrade to an empty ladder, not to a
        crash in the middle of a BOM.
        """
        tiers = payload.get("price_tiers") or []
        clean_tiers: list[dict[str, Any]] = []
        for tier in tiers:
            if not isinstance(tier, dict):
                continue
            price = _float(tier.get("price"))
            qty = _int(tier.get("qty"))
            if price is not None and qty is not None:
                clean_tiers.append({"qty": qty, "price": price})
        parameters: list[dict[str, str]] = []
        for item in payload.get("parameters") or []:
            if not isinstance(item, dict):
                continue
            parameters.append(
                {"name": str(item.get("name") or ""), "value": str(item.get("value") or "")}
            )
        return cls(
            lcsc=str(payload.get("lcsc") or "").strip().upper(),
            mpn=str(payload.get("mpn") or "").strip(),
            manufacturer=str(payload.get("manufacturer") or "").strip(),
            description=str(payload.get("description") or "").strip(),
            package=str(payload.get("package") or "").strip(),
            category=str(payload.get("category") or "").strip(),
            status=str(payload.get("status") or "").strip(),
            stock=_int(payload.get("stock")) or 0,
            value=str(payload.get("value") or "").strip(),
            currency=str(payload.get("currency") or "").strip(),
            price_tiers=clean_tiers,
            price_text=str(payload.get("price_text") or "").strip(),
            datasheet=str(payload.get("datasheet") or "").strip(),
            product_url=str(payload.get("product_url") or "").strip(),
            distributor=str(payload.get("distributor") or "LCSC").strip() or "LCSC",
            parameters=parameters,
            keywords=str(payload.get("keywords") or "").strip(),
        )

    # -- derived --------------------------------------------------------

    @property
    def identity(self) -> str:
        """What the row is looked up by: the MPN, falling back to the C-number."""
        return self.mpn or self.lcsc

    def id_column(self) -> str:
        category = self.category.strip() or DEFAULT_CATEGORY
        return f"{category}/{self.identity}"

    def parameter_pairs(self, limit: int = 32) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        for item in self.parameters:
            name = item.get("name", "").strip()
            value = item.get("value", "").strip()
            if not name and not value:
                continue
            if name.lower() in COLUMN_DUPLICATES:
                continue
            pairs.append((name, value))
            if len(pairs) >= limit:
                break
        return pairs

    def unit_price(self) -> str:
        """``price@qty/…``, largest quantity first — the layout the existing DB uses."""
        if self.price_tiers:
            ordered = sorted(self.price_tiers, key=lambda item: int(item["qty"]), reverse=True)
            return "/".join(f"{_short(item['price'])}@{item['qty']}" for item in ordered)
        return self.price_text

    def textual(self) -> str:
        return " ".join(
            part for part in (self.category, self.description, self.package) if part
        ).lower()


def _float(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None


def _short(value: Any) -> str:
    """Trim trailing zeros so ``0.10000`` becomes ``0.1``."""
    number = _float(value)
    if number is None:
        return str(value)
    text = f"{number:.6f}".rstrip("0").rstrip(".")
    return text or "0"


# -- BOM lines -------------------------------------------------------------

_ALIASES: dict[str, tuple[str, ...]] = {
    "lcsc": (
        "lcsc", "lcsc#", "lcsc_part", "lcsc_number", "c", "cno", "c_number",
        "part", "part_number", "supplier_part", "pn",
    ),
    "mpn": (
        "mpn", "manufacturer_part_number", "mfr_part_number", "manufacturer_pn",
        "mpn_manufacturer", "model",
    ),
    "value": ("value", "val", "schematic_value", "design_value"),
    "ref": ("ref", "refs", "reference", "references", "designator", "designators", "refdes"),
    "qty": ("qty", "quantity", "count"),
    "symbol": ("symbol", "kicad_symbol", "symbol_library", "symbol_lib"),
    "footprint": (
        "footprint", "kicad_footprint", "footprint_library", "footprint_lib",
        "package_footprint",
    ),
    "name": ("name", "library_name", "file_name", "stem"),
    "type": ("type", "product_type", "prefix"),
    "keywords": ("keywords", "tags"),
    "notes": ("notes", "note", "comment", "comments", "description_note"),
}


def _canonical(header: str) -> str:
    cleaned = header.strip().lower().replace(" ", "_").replace("-", "_")
    for canonical, aliases in _ALIASES.items():
        if cleaned in aliases:
            return canonical
    return ""


@dataclass
class BomLine:
    lcsc: str = ""
    mpn: str = ""
    value: str = ""
    ref: str = ""
    qty: str = ""
    symbol: str = ""
    footprint: str = ""
    name: str = ""
    product_type: str = ""
    keywords: str = ""
    notes: str = ""
    row: int = 0

    @property
    def identifier(self) -> str:
        return self.lcsc or self.mpn

    def is_empty(self) -> bool:
        return not self.lcsc and not self.mpn

    def override_symbol(self) -> str:
        return self.symbol.strip()

    def override_footprint(self) -> str:
        return self.footprint.strip()


def load_bom(path: str | Path) -> list[BomLine]:
    """Read a CSV or JSON BOM.

    CSV headers are matched case-insensitively against a list of common names,
    so a designer's existing export usually needs no editing. JSON may be a list
    of objects or ``{"lines": [...]}``.
    """
    file = Path(path)
    if not file.is_file():
        raise FileNotFoundError(f"no BOM at {file}")
    text = file.read_text(encoding="utf-8-sig")
    stripped = text.lstrip()
    if file.suffix.lower() == ".json" or stripped.startswith(("{", "[")):
        return _load_json_bom(text, file)
    return _load_csv_bom(text, file)


def _load_json_bom(text: str, file: Path) -> list[BomLine]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{file} is not valid JSON: {exc}") from exc
    if isinstance(data, dict):
        data = data.get("lines") or data.get("bom") or data.get("items") or []
    if not isinstance(data, list):
        raise ValueError(f"{file} must contain a list of lines")
    lines: list[BomLine] = []
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            continue
        line = BomLine(row=index)
        for key, value in item.items():
            canonical = _canonical(str(key))
            if canonical and hasattr(line, canonical):
                setattr(line, canonical, str(value).strip() if value is not None else "")
        if not line.is_empty():
            lines.append(line)
    return lines


def _load_csv_bom(text: str, file: Path) -> list[BomLine]:
    reader = csv.reader(text.splitlines())
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        return []
    header = rows[0]
    mapping: dict[int, str] = {}
    for index, name in enumerate(header):
        canonical = _canonical(name)
        if canonical:
            mapping[index] = canonical
    if not mapping:
        raise ValueError(
            f"{file}: none of the header names look like an LCSC column. "
            "Expected one of: lcsc, mpn, value, ref, qty, symbol, footprint, name, type."
        )
    lines: list[BomLine] = []
    for row_index, row in enumerate(rows[1:], start=2):
        line = BomLine(row=row_index)
        for index, canonical in mapping.items():
            if index < len(row) and hasattr(line, canonical):
                setattr(line, canonical, row[index].strip())
        if not line.is_empty():
            lines.append(line)
    return lines
