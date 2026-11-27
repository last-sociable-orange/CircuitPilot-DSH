"""UI-free search orchestration.

Owns the storefront backend for the active language, keeps a small cache of
detail lookups, and turns every failure into a typed :class:`AppError` the GUI can
show.  The GUI calls this from a worker thread; the backend serialises its own
requests, so concurrent calls are safe but never parallel.
"""

# Vendored from KiCad LibGen LCSC (KicadLibGui-LCSC 1.0.0) at commit 60c89f8.
# Do not edit: refresh with scripts/refresh_client.py.
from __future__ import annotations

import logging
import threading
from collections import OrderedDict

from .errors import AppError
from .models import ProductInfo
from .base import SearchPage
from .cache import ResponseCache
from .routing import create_backend, normalise_language, site_for
from .session import HttpSession

logger = logging.getLogger(__name__)

_DETAIL_CACHE_SIZE = 200


class SearchService:
    def __init__(
        self,
        language: str = "zh_CN",
        *,
        timeout: float = 20,
        min_interval: float = 0.35,
        cache_ttl: float = 0,
        cache_directory: str | None = None,
        session: HttpSession | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self._language = normalise_language(language)
        self._timeout = timeout
        self._min_interval = min_interval
        self._cache_ttl = float(cache_ttl)
        self._cache_directory = cache_directory
        self._session = session
        self._backend = None
        self._details: OrderedDict[tuple[str, str], ProductInfo] = OrderedDict()
        self._build()

    # -- backend lifecycle ----------------------------------------------

    def _build(self) -> None:
        if self._session is None:
            cache = None
            if self._cache_ttl > 0 and self._cache_directory:
                cache = ResponseCache(self._cache_directory, self._cache_ttl)
            self._session = HttpSession(timeout=self._timeout, min_interval=self._min_interval,
                                        cache=cache)
        if self._backend is not None:
            try:
                self._backend.close()
            except Exception:  # pragma: no cover - best effort
                pass
        self._backend = create_backend(self._language, session=self._session)
        self._backend.cache_ttl = self._cache_ttl
        self._details.clear()
        logger.info("Search backend: %s (%s, cache %ss)", site_for(self._language),
                    self._language, int(self._cache_ttl))

    @property
    def language(self) -> str:
        return self._language

    @property
    def site(self) -> str:
        return site_for(self._language)

    @property
    def currency(self) -> str:
        return self._backend.currency if self._backend is not None else "¥"

    def set_language(self, language: str) -> bool:
        """Switch storefront.  Returns ``True`` when the language changed."""
        code = normalise_language(language)
        with self._lock:
            if code == self._language and self._backend is not None:
                return False
            self._language = code
            self._build()
            return True

    def configure(self, *, timeout: float | None = None, min_interval: float | None = None,
                  cache_ttl: float | None = None) -> None:
        """Apply new transport settings to the live session and backend."""
        with self._lock:
            if timeout is not None:
                self._timeout = float(timeout)
            if min_interval is not None:
                self._min_interval = float(min_interval)
            if cache_ttl is not None:
                self._cache_ttl = float(cache_ttl)
            if self._session is not None:
                self._session.timeout = max(5.0, self._timeout)
                self._session.min_interval = max(0.0, self._min_interval)
                cache = self._session.cache
                if cache is not None and hasattr(cache, "ttl"):
                    cache.ttl = max(0.0, self._cache_ttl)
                elif self._cache_ttl > 0 and self._cache_directory:
                    self._session.cache = ResponseCache(self._cache_directory, self._cache_ttl)
            if self._backend is not None:
                self._backend.cache_ttl = max(0.0, self._cache_ttl)

    def close(self) -> None:
        with self._lock:
            if self._backend is not None:
                self._backend.close()
                self._backend = None

    # -- queries ---------------------------------------------------------

    def search(self, query: str, page: int = 1, *, category_id: str = "") -> SearchPage:
        with self._lock:
            backend = self._backend
        result = backend.search(query, page, category_id=category_id)
        logger.info("Search %r on %s: %s matches (page %s/%s)", query, self.site,
                    result.total, result.page, result.pages)
        return result

    def detail(self, product: ProductInfo) -> ProductInfo:
        """Enrich *product* once per session; failures fall back to what we have."""
        key = (self._language, product.base.distributor_product_number)
        with self._lock:
            cached = self._details.get(key)
            if cached is not None:
                self._details.move_to_end(key)
                merged = product.copy()
                merged.params = [dict(item) for item in cached.params]
                merged.source_parameters = [dict(item) for item in cached.source_parameters]
                merged.base.value = cached.base.value
                merged.base.datasheet_url = cached.base.datasheet_url or merged.base.datasheet_url
                merged.base.description = cached.base.description or merged.base.description
                merged.detail_state = "enriched"
                return merged
            backend = self._backend
        enriched = backend.detail(product)
        if enriched.detail_state == "enriched":
            with self._lock:
                self._details[key] = enriched.copy()
                while len(self._details) > _DETAIL_CACHE_SIZE:
                    self._details.popitem(last=False)
        return enriched

    def enrich_safely(self, product: ProductInfo) -> tuple[ProductInfo, str]:
        """Enrich without raising: returns ``(product, warning)``."""
        try:
            return self.detail(product), ""
        except AppError as exc:
            logger.info("Detail unavailable for %s: %s",
                        product.base.distributor_product_number, exc)
            return product, str(exc)

    # -- helpers for the GUI --------------------------------------------

    def supports_detail(self) -> bool:
        with self._lock:
            return bool(self._backend is not None and self._backend.supports_detail())

    def clear_cache(self) -> int:
        """Drop the in-memory detail cache and the on-disk response cache."""
        with self._lock:
            self._details.clear()
            cache = getattr(self._session, "cache", None)
            removed = cache.clear() if cache is not None and hasattr(cache, "clear") else 0
        logger.info("Cleared %s cached responses", removed)
        return removed
