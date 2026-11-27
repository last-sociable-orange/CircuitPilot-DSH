"""Product dataclasses and column definitions.

The shapes here mirror upstream ``kicad_cip.py`` exactly so the CLI and the
GUI write identical rows into the KiCad ``components`` table.
"""

# Vendored from KiCad LibGen LCSC (KicadLibGui-LCSC 1.0.0) at commit 60c89f8.
# Do not edit: refresh with scripts/refresh_client.py.
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from typing import Any

PARAM_COUNT = 32

#: The 16 non-parametric columns, in the order created by ``create_tbl()``.
#: ``ID`` is first; ``main_category`` is a parser-only field and is not stored.
METADATA_COLUMNS: tuple[str, ...] = (
    "ID",
    "Description",
    "Keywords",
    "Value",
    "Manufacturer",
    "ManufacturerProductNumber",
    "Package",
    "KicadSymbolLibrary",
    "KicadFootprintLibrary",
    "PartStatus",
    "QtyAvailable",
    "Distributor",
    "DistributorProductNumber",
    "UnitPrice",
    "ProductUrl",
    "DatasheetUrl",
)

PARAM_COLUMNS: tuple[str, ...] = tuple(
    column
    for index in range(1, PARAM_COUNT + 1)
    for column in (f"Param{index:02d}", f"Value{index:02d}")
)

#: All 80 columns of the ``components`` table, in physical order.
ALL_COLUMNS: tuple[str, ...] = METADATA_COLUMNS + PARAM_COLUMNS

#: Placeholder used when a parameter slot is unused.
DEFAULT_PARAM: dict[str, str] = {"param": "-", "value": "-"}

_UNSET = "-"


def _clean(value: Any) -> str:
    """Coerce any API/database value to a string, never ``None``."""
    if value is None:
        return ""
    return str(value)


@dataclass
class ProductInfoBase:
    """One product's metadata (everything except the 32 parameters)."""

    main_category: str = ""
    id: str = ""
    description: str = ""
    keywords: str = ""
    value: str = ""
    manufacturer: str = ""
    manufacturer_product_number: str = ""
    package: str = ""
    kicad_symbol_library: str = ""
    kicad_footprint_library: str = ""
    part_status: str = ""
    qty_available: str = ""
    distributor: str = ""
    distributor_product_number: str = ""
    unit_price: str = ""
    product_url: str = ""
    datasheet_url: str = ""


@dataclass
class ProductInfo:
    """A search result / database record.

    ``params`` always holds 32 ``{"param": ..., "value": ...}`` dictionaries.
    """

    base: ProductInfoBase = field(default_factory=ProductInfoBase)
    params: list[dict[str, str]] = field(
        default_factory=lambda: [dict(DEFAULT_PARAM) for _ in range(PARAM_COUNT)]
    )

    #: Transient provenance used by the GUI.  None of these are column values:
    #: ``to_row`` never reads them, so they cannot disturb the 80-column schema.
    #: ``source_product_id`` is the storefront's numeric/product identity used to
    #: build a detail URL; ``source_parameters`` keeps every parameter the store
    #: reported so the "view all" dialog is not limited to the 32 stored slots;
    #: ``source_scene`` records how the international search classified the query;
    #: ``detail_state`` is ``""``, ``"enriched"`` or ``"failed"``.
    source_product_id: str = ""
    source_parameters: list[dict[str, str]] = field(default_factory=list)
    source_scene: str = ""
    detail_state: str = ""

    def __post_init__(self) -> None:
        self.normalise_params()

    # -- convenience -----------------------------------------------------

    @property
    def mpn(self) -> str:
        return self.base.manufacturer_product_number

    @mpn.setter
    def mpn(self, value: str) -> None:
        self.base.manufacturer_product_number = _clean(value)

    def normalise_params(self) -> None:
        """Pad/truncate parameters to exactly :data:`PARAM_COUNT` slots."""
        params: list[dict[str, str]] = []
        for item in self.params[:PARAM_COUNT]:
            params.append(
                {
                    "param": _clean(item.get("param", _UNSET)) or _UNSET,
                    "value": _clean(item.get("value", _UNSET)) or _UNSET,
                }
            )
        while len(params) < PARAM_COUNT:
            params.append(dict(DEFAULT_PARAM))
        self.params = params

    def parameter_pairs(self) -> Iterable[tuple[str, str]]:
        """Yield the non-empty parameter pairs in slot order."""
        for item in self.params:
            name = item.get("param", "")
            value = item.get("value", "")
            if name not in ("", _UNSET) or value not in ("", _UNSET):
                yield name, value

    def parameter_count(self) -> int:
        return sum(1 for _ in self.parameter_pairs())

    def reported_parameter_pairs(self) -> Iterable[tuple[str, str]]:
        """Every parameter the store reported, not just the 32 stored slots.

        The "view all" dialog uses this so a part with 40 parameters can still be
        inspected in full; it falls back to the stored slots for a part loaded
        from the database.
        """
        if self.source_parameters:
            for item in self.source_parameters:
                name = item.get("param", "")
                value = item.get("value", "")
                if name or value:
                    yield name, value
            return
        yield from self.parameter_pairs()

    def resolved_mapping(self) -> tuple[str, str]:
        """Return ``(symbol, footprint)`` with ``?`` replaced by the MPN."""
        return (
            resolve_mapping(self.base.kicad_symbol_library, self.mpn),
            resolve_mapping(self.base.kicad_footprint_library, self.mpn),
        )

    def with_mapping(self, symbol: str, footprint: str) -> ProductInfo:
        self.base.kicad_symbol_library = symbol
        self.base.kicad_footprint_library = footprint
        return self

    def copy(self) -> ProductInfo:
        return ProductInfo(
            base=replace(self.base),
            params=[dict(item) for item in self.params],
            source_product_id=self.source_product_id,
            source_parameters=[dict(item) for item in self.source_parameters],
            source_scene=self.source_scene,
            detail_state=self.detail_state,
        )

    # -- row conversion --------------------------------------------------

    def to_row(self) -> tuple[str, ...]:
        """Return the 80 column values in physical table order."""
        self.normalise_params()
        values: list[str] = [
            _clean(self.base.id),
            _clean(self.base.description),
            _clean(self.base.keywords),
            _clean(self.base.value),
            _clean(self.base.manufacturer),
            _clean(self.base.manufacturer_product_number),
            _clean(self.base.package),
            _clean(self.base.kicad_symbol_library),
            _clean(self.base.kicad_footprint_library),
            _clean(self.base.part_status),
            _clean(self.base.qty_available),
            _clean(self.base.distributor),
            _clean(self.base.distributor_product_number),
            _clean(self.base.unit_price),
            _clean(self.base.product_url),
            _clean(self.base.datasheet_url),
        ]
        for item in self.params:
            values.append(_clean(item.get("param", _UNSET)))
            values.append(_clean(item.get("value", _UNSET)))
        return tuple(values)

    def row_dict(self) -> dict[str, str]:
        return dict(zip(ALL_COLUMNS, self.to_row(), strict=True))

    def display_name(self) -> str:
        return self.mpn or self.base.description or "(unnamed product)"


def resolve_mapping(value: str, mpn: str) -> str:
    """Replace every ``?`` in a mapping field with the manufacturer part number."""
    return _clean(value).replace("?", _clean(mpn))


def validate_mapping(symbol: str, footprint: str, *, required: bool = True) -> tuple[str, str]:
    """Trim and validate KiCad mapping fields for a GUI save.

    Returns the cleaned ``(symbol, footprint)`` or raises :class:`ValueError`
    with a message suitable for an inline banner.
    """
    symbol = _clean(symbol).strip()
    footprint = _clean(footprint).strip()
    for label, value in (("Symbol library", symbol), ("Footprint library", footprint)):
        if required and not value:
            raise ValueError(f"{label} is required.")
        if "\n" in value or "\r" in value:
            raise ValueError(f"{label} cannot contain line breaks.")
        if len(value) > 255:
            raise ValueError(f"{label} is too long (max 255 characters).")
        if value.lower() in ("none", "null"):
            raise ValueError(f"{label} must be a library name, not '{value}'.")
    return symbol, footprint
