"""Self-contained LCSC / SZLCSC client used by the lcsc-parts skill.

Vendored from KiCad LibGen LCSC 1.0.0 at commit 60c89f8 on 2026-11-21.
Do not edit these modules by hand: run ``scripts/refresh_client.py`` instead.
Provenance and the list of dropped modules are in ``README.md``.
"""

from .base import Backend, Category, SearchPage, page_count
from .errors import AppError, DetailError, ParseError, SearchError
from .models import ALL_COLUMNS, PARAM_COUNT, ProductInfo
from .routing import (
    DEFAULT_LANGUAGE,
    LANGUAGES,
    create_backend,
    currency_for,
    normalise_language,
    site_for,
    storefront_url,
)
from .service import SearchService

__all__ = [
    "ALL_COLUMNS",
    "Backend",
    "Category",
    "DEFAULT_LANGUAGE",
    "DetailError",
    "LANGUAGES",
    "PARAM_COUNT",
    "ParseError",
    "ProductInfo",
    "SearchError",
    "SearchPage",
    "SearchService",
    "AppError",
    "create_backend",
    "currency_for",
    "normalise_language",
    "page_count",
    "site_for",
    "storefront_url",
]
