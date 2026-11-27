"""Language to storefront routing.

The language setting decides both the interface language and the site that is
queried: Chinese uses ``szlcsc.com`` (CNY, Chinese parameters), English uses
``lcsc.com`` (USD, English parameters).  Nothing else in the program branches on
the language, so a flip is a single setting.
"""

# Vendored from KiCad LibGen LCSC (KicadLibGui-LCSC 1.0.0) at commit 60c89f8.
# Do not edit: refresh with scripts/refresh_client.py.
from __future__ import annotations

from .base import Backend
from .text import part_number

LANGUAGES: tuple[tuple[str, str], ...] = (
    ("zh_CN", "中文 · 立创商城"),
    ("en_US", "English · LCSC"),
)
DEFAULT_LANGUAGE = "zh_CN"
_LANGUAGE_IDS = frozenset(code for code, _label in LANGUAGES)


def normalise_language(value: object) -> str:
    """Accept only a known language code, defaulting to Chinese."""
    candidate = str(value or "").strip()
    return candidate if candidate in _LANGUAGE_IDS else DEFAULT_LANGUAGE


def site_for(language: str) -> str:
    return "lcsc.com" if normalise_language(language) == "en_US" else "szlcsc.com"


def currency_for(language: str) -> str:
    return "US$" if normalise_language(language) == "en_US" else "¥"


def create_backend(language: str, *, session=None) -> Backend:
    """Build the backend for *language*; the caller owns the session."""
    from .domestic import DomesticBackend
    from .international import InternationalBackend

    if normalise_language(language) == "en_US":
        return InternationalBackend(session)
    return DomesticBackend(session)


def storefront_url(language: str, part: str) -> str:
    """The product page a record should link to, per language."""
    code = part_number(part)
    if normalise_language(language) == "en_US":
        return f"https://www.lcsc.com/product-detail/{code}.html" if code else "https://www.lcsc.com"
    if code:
        return "https://so.szlcsc.com/global.html?k=" + code
    return "https://www.szlcsc.com"
