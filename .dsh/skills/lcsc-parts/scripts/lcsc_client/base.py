"""The backend contract shared by both storefronts.

The GUI never talks to a site directly: it asks a :class:`Backend` for a
:class:`SearchPage` of :class:`~kicad_core.models.ProductInfo` records, exactly as
it would for DigiKey, so the tables, the detail panel and the database code stay
source-agnostic.
"""

# Vendored from KiCad LibGen LCSC (KicadLibGui-LCSC 1.0.0) at commit 60c89f8.
# Do not edit: refresh with scripts/refresh_client.py.
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from .models import ProductInfo


@dataclass(frozen=True)
class Category:
    """One category the current result set can be narrowed to."""

    id: str
    name: str
    count: int = 0


@dataclass
class SearchPage:
    """One page of results plus the paging and filtering context."""

    items: list[ProductInfo] = field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 30
    pages: int = 1
    categories: list[Category] = field(default_factory=list)
    category_id: str = ""
    scene: str = ""
    note: str = ""
    #: True when the query was an exact LCSC part number rather than a keyword.
    exact: bool = False

    @property
    def has_more(self) -> bool:
        return self.page < self.pages

    @property
    def empty(self) -> bool:
        return not self.items


def page_count(total: int, page_size: int) -> int:
    if total <= 0 or page_size <= 0:
        return 1
    return max(1, math.ceil(total / page_size))


class Backend(ABC):
    """A storefront that can search and describe parts."""

    #: ``zh_CN`` or ``en_US``.
    language: str = ""
    #: Host the user is being queried, for the status bar and error messages.
    site: str = ""
    #: ``¥`` or ``US$``.
    currency: str = ""
    #: Native page size to request; both sites cap this differently.
    page_size: int = 30
    #: Seconds a detail response may be served from the on-disk cache (0 = off).
    cache_ttl: float = 0.0

    def __init__(self, session=None) -> None:
        from .session import HttpSession

        self.session = session if session is not None else HttpSession()

    # -- required --------------------------------------------------------

    @abstractmethod
    def search(self, query: str, page: int = 1, *, category_id: str = "") -> SearchPage:
        """Search the storefront and map the result to :class:`ProductInfo`."""

    @abstractmethod
    def detail(self, product: ProductInfo, *, fetch: bool = True) -> ProductInfo:
        """Return *product* enriched with everything the detail source knows.

        Implementations may already have all the data; ``fetch=False`` means
        "answer from what you already have, do not spend a request".
        """

    # -- optional --------------------------------------------------------

    def supports_detail(self) -> bool:
        """Whether :meth:`detail` can add value over the search row."""
        return False

    def close(self) -> None:
        self.session.close()
