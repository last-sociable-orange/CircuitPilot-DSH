"""One polite HTTP client for both storefronts.

The storefronts are ordinary public web front ends, so this layer is deliberate
about being a good citizen: one request at a time, a minimum gap between
requests, one deliberate retry on 429/5xx (honouring ``Retry-After``), a hard cap
on how many bytes it will read, and typed errors that never echo a query string,
a cookie or a signed URL.
"""

# Vendored from KiCad LibGen LCSC (KicadLibGui-LCSC 1.0.0) at commit 60c89f8.
# Do not edit: refresh with scripts/refresh_client.py.
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Mapping
from typing import Any

import requests

from .errors import (
    NetworkError,
    ParseError,
    RateLimitError,
    SearchError,
    ServerError,
)

logger = logging.getLogger(__name__)

#: A normal desktop browser identifies itself; the storefronts reject or throttle
#: obviously automated clients.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
)

DEFAULT_TIMEOUT = 20.0
DEFAULT_MIN_INTERVAL = 0.35
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_BYTES = 16 * 1024 * 1024
_READ_CHUNK = 65536
_MAX_RETRY_AFTER = 60
#: Statuses worth one retry: rate limiting and transient gateway/server errors.
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


def _close(response: Any) -> None:
    try:
        response.close()
    except Exception:  # pragma: no cover - best effort
        pass



def _retry_after_seconds(response: requests.Response) -> int:
    try:
        raw = str(response.headers.get("Retry-After", "") or "")
    except AttributeError:  # pragma: no cover - unusual stub
        raw = ""
    try:
        return max(1, int(float(raw)))
    except (TypeError, ValueError):
        return 5


class HttpSession:
    """Serialised, paced HTTP access to the storefronts.

    ``session`` is injectable so the test suite can run entirely offline: any
    object exposing ``request(method, url, ...)`` returning a response-like
    object with ``status_code``/``headers``/``iter_content``/``json``/``url``
    will do.
    """

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        min_interval: float = DEFAULT_MIN_INTERVAL,
        user_agent: str = USER_AGENT,
        session: Any | None = None,
        cache: Any | None = None,
    ) -> None:
        self.timeout = max(5.0, float(timeout))
        self.min_interval = max(0.0, float(min_interval))
        self.cache = cache
        self._session = session if session is not None else requests.Session()
        self._lock = threading.RLock()
        self._last_request = 0.0
        if session is None:
            self._session.headers.update(
                {
                    "User-Agent": user_agent,
                    "Accept": "application/json,text/html,*/*",
                    "Cache-Control": "no-cache",
                }
            )

    # -- lifecycle -------------------------------------------------------

    def close(self) -> None:
        try:
            self._session.close()
        except Exception:  # pragma: no cover - best effort
            pass

    def __enter__(self) -> HttpSession:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- public API ------------------------------------------------------

    def get_json(self, url: str, *, headers: Mapping[str, str] | None = None,
                 params: Mapping[str, Any] | None = None,
                 max_bytes: int = MAX_RESPONSE_BYTES,
                 cache_ttl: float = 0.0) -> dict[str, Any]:
        body = self.get_bytes(url, headers=headers, params=params, max_bytes=max_bytes,
                              cache_ttl=cache_ttl)
        return _decode_json(body)

    def post_json(self, url: str, payload: Mapping[str, Any], *,
                  headers: Mapping[str, str] | None = None,
                  max_bytes: int = MAX_RESPONSE_BYTES,
                  cache_ttl: float = 0.0) -> dict[str, Any]:
        body = self.get_bytes(url, headers=headers, params=None, max_bytes=max_bytes,
                              method="POST", payload=payload, cache_ttl=cache_ttl)
        return _decode_json(body)

    def get_bytes(self, url: str, *, headers: Mapping[str, str] | None = None,
                  params: Mapping[str, Any] | None = None,
                  max_bytes: int = MAX_RESPONSE_BYTES, method: str = "GET",
                  payload: Mapping[str, Any] | None = None,
                  cache_ttl: float = 0.0) -> bytes:
        """Perform one request, retrying a 429/5xx (or a dropped connection) once.

        ``cache_ttl`` above zero opts this request into the on-disk response
        cache; search requests never do, so prices and stock stay live.
        """
        cache_key = None
        if cache_ttl > 0 and getattr(self.cache, "enabled", False):
            cache_key = _cache_key(method, url, params, payload)
            cached = self.cache.get(cache_key)
            if cached is not None:
                logger.debug("Cache hit for %s", url)
                return cached
        attempt = 0
        while True:
            self._pace()
            try:
                response = self._session.request(
                    method,
                    url,
                    params=params,
                    json=payload,
                    headers=dict(headers or {}),
                    timeout=(self.timeout, self.timeout),
                    stream=True,
                    allow_redirects=True,
                )
            except requests.Timeout as exc:
                if attempt == 0:
                    attempt += 1
                    self._backoff(2)
                    continue
                raise NetworkError(
                    "LCSC did not answer in time. Check your network and retry.",
                    details=str(exc),
                ) from exc
            except requests.RequestException as exc:
                if attempt == 0:
                    attempt += 1
                    self._backoff(2)
                    continue
                raise NetworkError(details=str(exc)) from exc

            status = getattr(response, "status_code", 200)
            if status in _RETRYABLE_STATUS and attempt == 0:
                # One deliberate retry, honouring Retry-After.  POST bodies are
                # never replayed more than once so the store is not hammered.
                attempt += 1
                delay = _retry_after_seconds(response)
                _close(response)
                self._backoff(delay)
                continue
            try:
                self._raise_for_status(response)
                body = self._read_body(response, max_bytes)
            finally:
                _close(response)
            if cache_key is not None:
                self.cache.put(cache_key, body)
            return body

    # -- internals -------------------------------------------------------

    def _pace(self) -> None:
        with self._lock:
            if self.min_interval > 0:
                elapsed = time.monotonic() - self._last_request
                if 0 < elapsed < self.min_interval:
                    time.sleep(self.min_interval - elapsed)
            self._last_request = time.monotonic()

    def _backoff(self, seconds: float) -> None:
        delay = max(1.0, min(_MAX_RETRY_AFTER, float(seconds)))
        logger.info("Waiting %.0fs before retrying a storefront request", delay)
        time.sleep(delay)

    @staticmethod
    def _raise_for_status(response: requests.Response) -> None:
        status = getattr(response, "status_code", 200)
        if status < 300:
            return
        if status == 429:
            raise RateLimitError(
                f"LCSC is rate limiting requests. Wait {_retry_after_seconds(response)} "
                "seconds and retry.",
                retry_after=_retry_after_seconds(response),
            )
        if 500 <= status < 600:
            raise ServerError("LCSC is temporarily unavailable. Retry in a moment.")
        if status in (401, 403):
            raise SearchError(
                "LCSC refused the request. The site may be blocking automated "
                "access; wait a while and retry.",
                details=f"HTTP {status}",
            )
        if status == 404:
            raise SearchError("LCSC has no such page.", details="HTTP 404")
        raise SearchError(f"LCSC returned HTTP {status}.", details=f"HTTP {status}")

    @staticmethod
    def _read_body(response: requests.Response, max_bytes: int) -> bytes:
        chunks: list[bytes] = []
        total = 0
        try:
            iterator = response.iter_content(chunk_size=_READ_CHUNK)
        except AttributeError:  # pragma: no cover - unusual stub
            content = getattr(response, "content", b"") or b""
            return content[:max_bytes]
        for chunk in iterator:
            if not chunk:
                continue
            total += len(chunk)
            if total > max_bytes:
                raise SearchError(
                    "LCSC returned more data than expected; the response was "
                    "discarded.",
                    details=f"limit {max_bytes} bytes",
                )
            chunks.append(chunk)
        return b"".join(chunks)


def _decode_json(body: bytes) -> dict[str, Any]:
    import json

    if not body:
        raise ParseError("LCSC returned an empty response.")
    try:
        value = json.loads(body)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ParseError(
            "LCSC returned an unexpected response.",
            details=f"invalid JSON: {exc}",
        ) from exc
    if not isinstance(value, dict):
        raise ParseError("LCSC returned an unexpected response.",
                         details="top-level JSON is not an object")
    return value


def _cache_key(method: str, url: str, params: Mapping[str, Any] | None,
               payload: Mapping[str, Any] | None) -> str:
    from .cache import cache_key

    return cache_key(method, url, dict(params or {}), dict(payload or {}))
