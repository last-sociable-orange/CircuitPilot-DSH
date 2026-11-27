#!/usr/bin/env python3
"""Storefront transport policy: cooldowns, Retry-After and failure classification.

The vendored client in ``lcsc_client/`` is refreshed by ``scripts/refresh_client.py``
and says so in its header, so this module never edits it: :class:`ResilientSession`
subclasses the vendored ``HttpSession`` and replaces only the request loop.

The policy is taken from **LCSC3D** (``app/lcsc3d/services/backend.py``:
``ResourceCooldowns`` and ``NetworkApi.fetch``), which drives whole libraries of parts
against these same storefronts. What carries over, in the same order:

* a cooldown is **shared per origin**, so one 429 pauses every caller, not just the
  unlucky one, and it never shortens an existing deadline;
* ``Retry-After`` is honoured for both forms (seconds and HTTP-date) with urllib3's
  parser, falls back to exponential ``5 * 2**attempt`` when absent, and a header that
  asks for more than :data:`RESOURCE_MAX_AUTOMATIC_WAIT` fails fast instead of parking
  the run;
* 5xx gets at most :data:`TRANSIENT_STATUS_ATTEMPTS` attempts, other 4xx none;
* the response is closed **before** anybody waits, otherwise the small connection pool
  deadlocks with every caller asleep holding a socket;
* a page that asks for a sign-in is not a throttle: it raises :class:`AuthRequired`
  immediately, because retrying a login wall only wastes the run.

LCSC3D runs its batch through a ``ThreadPoolExecutor``; this client does not need one.
Our detail call already carries many part numbers per request, so a pool would only
multiply the request rate against a limiter that counts requests per origin.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any
from urllib.parse import urlsplit

import requests
from urllib3.exceptions import InvalidHeader
from urllib3.util import Retry

from lcsc_client import session as _vendored
from lcsc_client.errors import (
    NetworkError,
    ParseError,
    RateLimitError,
    SearchError,
    ServerError,
)

logger = logging.getLogger(__name__)

#: Attempts per request, as in LCSC3D's ``RESOURCE_REQUEST_ATTEMPTS``.
RESOURCE_REQUEST_ATTEMPTS = 5
#: Exponential fallback when the storefront sends no usable Retry-After.
RESOURCE_RETRY_BACKOFF = 5.0
#: Never sit out a longer request than this; fail and let the caller decide.
RESOURCE_MAX_AUTOMATIC_WAIT = 120.0
#: Total time this call may spend waiting on cooldowns before giving up.
#:
#: LCSC3D needs no such bound: it is a GUI with per-part progress and a cancel button.
#: A CLI that blocks is a different animal — five attempts under 120s cooldowns is ten
#: minutes of silence, so the whole call gets a budget instead.
RESOURCE_MAX_TOTAL_WAIT = 90.0
#: 5xx is retried at most this many times before giving up.
TRANSIENT_STATUS_ATTEMPTS = 2
#: Pacing floor between requests; 0 means "no pacing" and exists for offline tests.
DEFAULT_INTERVAL = 1.0
MIN_INTERVAL_FLOOR = 0.5

#: Markers that mean "the storefront wants a signed-in browser", not "slow down".
LOGIN_MARKERS = ("用户登录", "请登录", "login", "signin", "sign in", "passport", "captcha")


class AuthRequired(SearchError):
    """The storefront answered with a sign-in page; retrying will not help."""


class Cooldowns:
    """Shared per-origin backoff, the way LCSC3D spreads one 429 across all workers.

    The wait budget lives here too, not in the session: one ``lcsc.py detail A B C``
    process issues a request per part, so a per-request budget would let a 12-part run
    stack twelve of them. The budget belongs to the process.
    """

    def __init__(self) -> None:
        self.deadlines: dict[tuple[str, str, int | None], float] = {}
        self.lock = threading.Lock()
        self.spent = 0.0
        self.budget = RESOURCE_MAX_TOTAL_WAIT

    @staticmethod
    def origin(url: str) -> tuple[str, str, int | None]:
        parsed = urlsplit(url)
        return parsed.scheme, parsed.hostname or "", parsed.port

    def defer(self, url: str, seconds: float) -> None:
        now = time.monotonic()
        origin = self.origin(url)
        with self.lock:
            # Drop expired deadlines so the map cannot grow without bound.
            self.deadlines = {key: deadline for key, deadline in self.deadlines.items()
                              if deadline > now}
            self.deadlines[origin] = max(self.deadlines.get(origin, now), now + seconds)

    def remaining(self, url: str) -> float:
        with self.lock:
            return self.deadlines.get(self.origin(url), 0.0) - time.monotonic()

    def wait(self, url: str, sleep=time.sleep) -> None:
        delay = self.remaining(url)
        if delay <= 0:
            return
        if delay > RESOURCE_MAX_AUTOMATIC_WAIT:
            # Do not retry early, and do not sit on an unbounded header.
            raise RateLimitError(
                "The storefront asked for a long pause "
                f"({delay:.0f}s). Wait it out, then rerun.",
                retry_after=int(delay),
            )
        with self.lock:
            if self.spent + delay > self.budget:
                spent, budget = self.spent, self.budget
                raise RateLimitError(
                    f"The storefront asked for a {delay:.0f}s pause, and this run has "
                    f"already waited {spent:.0f}s of its {budget:.0f}s budget. "
                    "Rerun later, or raise --max-wait.",
                    retry_after=int(delay),
                )
            self.spent += delay
        logger.warning("Storefront cooldown: waiting %.1fs before the next request", delay)
        sleep(delay)


COOLDOWNS = Cooldowns()


def _retry_after_delay(response: Any) -> float:
    """Seconds requested by Retry-After (delta or HTTP-date), via urllib3's parser."""
    try:
        value = Retry(retry_after_max=float("inf")).get_retry_after(response)
    except (InvalidHeader, ValueError, OverflowError, TypeError):
        return 0.0
    try:
        return max(0.0, float(value or 0.0))
    except (TypeError, ValueError):
        return 0.0


def _looks_like_login(body: bytes) -> bool:
    """True when the page is a sign-in wall: retrying that is pointless."""
    head = (body or b"")[:4000].decode("utf-8", "replace").lower()
    return any(marker.lower() in head for marker in LOGIN_MARKERS)


def _looks_like_refusal(body: bytes) -> bool:
    """True when a body is an HTML page, which is how these storefronts throttle."""
    head = (body or b"")[:400].lstrip().lower()
    return head.startswith(b"<!doctype") or head.startswith(b"<html") or b"<html" in head[:200]


def _refusal_message(body: bytes, interval: float, url: str) -> str:
    """Explain a throttle page as a throttle page, not as a missing part."""
    snippet = " ".join((body or b"")[:160].decode("utf-8", "replace").split())
    return (
        f"{urlsplit(url).hostname or 'The storefront'} refused the request: it answered "
        "with an HTML page instead of JSON, which is what its rate limiter does. Wait a "
        f"minute and retry, or raise --interval (currently {interval:.1f}s between "
        f"requests). The reply began: {snippet!r}"
    )


class ResilientSession(_vendored.HttpSession):
    """The vendored HTTP session with LCSC3D's backoff policy in the request loop."""

    def __init__(self, *, min_interval: float = DEFAULT_INTERVAL,
                 max_total_wait: float = RESOURCE_MAX_TOTAL_WAIT, **kwargs: Any) -> None:
        value = max(0.0, float(min_interval))
        # A positive interval never goes below the floor: sub-second loops are what
        # trips the throttle in the first place. 0 stays 0 so offline tests are fast.
        super().__init__(min_interval=max(MIN_INTERVAL_FLOOR, value) if value > 0 else 0.0,
                         **kwargs)
        COOLDOWNS.budget = float(max_total_wait)

    def get_bytes(self, url: str, *, headers: Any = None, params: Any = None,
                  max_bytes: int = _vendored.MAX_RESPONSE_BYTES, method: str = "GET",
                  payload: Any = None, cache_ttl: float = 0.0) -> bytes:
        cache_key = None
        if cache_ttl > 0 and getattr(self.cache, "enabled", False):
            cache_key = _vendored._cache_key(method, url, params, payload)
            cached = self.cache.get(cache_key)
            if cached is not None:
                logger.debug("Cache hit for %s", url)
                return cached

        transient_failures = 0
        body = b""
        last = RESOURCE_REQUEST_ATTEMPTS - 1
        for attempt in range(RESOURCE_REQUEST_ATTEMPTS):
            # Shared across every caller of this origin and budgeted per process: a CLI
            # must not sit silent for minutes. Cooldowns.wait() enforces both caps.
            COOLDOWNS.wait(url)
            self._pace()
            response = None
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
            except (requests.Timeout, requests.RequestException) as exc:
                transient_failures += 1
                if transient_failures >= TRANSIENT_STATUS_ATTEMPTS or attempt == last:
                    raise NetworkError(details=str(exc)) from exc
                continue

            try:
                status = getattr(response, "status_code", 200)
                if status == 429 or (status == 503 and response.headers.get("Retry-After")):
                    delay = (_retry_after_delay(response)
                             or RESOURCE_RETRY_BACKOFF * 2 ** attempt)
                    COOLDOWNS.defer(url, delay)
                    logger.warning("Storefront rate limited (HTTP %s); cooling down %.1fs",
                                   status, delay)
                    _vendored._close(response)
                    response = None
                    if attempt == last:
                        raise RateLimitError(
                            f"LCSC is rate limiting requests (HTTP {status}). "
                            f"Wait {delay:.0f}s and retry.",
                            retry_after=int(delay),
                        )
                    continue
                if status >= 500:
                    transient_failures += 1
                    _vendored._close(response)
                    response = None
                    if transient_failures >= TRANSIENT_STATUS_ATTEMPTS or attempt == last:
                        raise ServerError(
                            f"LCSC is temporarily unavailable (HTTP {status}). "
                            "Retry in a moment."
                        )
                    continue
                self._raise_for_status(response)   # 401/403/404 and friends: no retry
                body = self._read_body(response, max_bytes)
            finally:
                if response is not None:
                    # Release before anybody sleeps: the pool is small and shared.
                    _vendored._close(response)

            if _looks_like_login(body):
                raise AuthRequired(
                    f"{urlsplit(url).hostname or 'The storefront'} answered with a sign-in "
                    "page, so no data came back. This CLI has no browser session: use the "
                    "other storefront (--lang en_US / --lang zh_CN) or authenticate first.",
                    details="login wall",
                )
            if _looks_like_refusal(body):
                delay = RESOURCE_RETRY_BACKOFF * 2 ** attempt
                COOLDOWNS.defer(url, delay)
                if attempt == last:
                    raise ParseError(_refusal_message(body, self.min_interval, url))
                continue

            if cache_key is not None:
                self.cache.put(cache_key, body)
            return body

        raise ParseError(_refusal_message(body, self.min_interval, url))
