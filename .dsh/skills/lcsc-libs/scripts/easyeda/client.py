"""Typed failures and the HTTP transport for the lcsc-libs skill.

Standard library only: ``urllib`` with gzip, a per-host minimum interval, one
deliberate retry on transient failures, a hard response-size cap, and errors that
never echo the query string or a signed URL.
"""

from __future__ import annotations

import contextlib
import gzip
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from dataclasses import dataclass, field

API_PRODUCT = "https://easyeda.com/api/products/{part}/components"
API_STEP = "https://modules.easyeda.com/qAxj6KHrDKw4blvCG8QJPs7Y/{uuid}"
API_OBJ = "https://modules.easyeda.com/3dmodel/{uuid}"
API_WMS_DETAIL = "https://wmsc.lcsc.com/ftps/wm/product/detail"

USER_AGENT = "lcsc-libs/1.0 (+https://github.com/last-sociable-orange/KicadLibGui-LCSC)"
# The API rejects `Accept: application/json` with 403; cosmetics matter here.
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate",
}

DEFAULT_INTERVAL = 0.35
MAX_API_BYTES = 8 * 1024 * 1024
MAX_MODEL_BYTES = 48 * 1024 * 1024
_RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})


class LibsError(Exception):
    """Base class for every failure this skill reports."""


class TransportError(LibsError):
    """Network, TLS, timeout or HTTP-level failure."""


class NotFoundError(LibsError):
    """The part has no such artefact (no symbol, no model, no datasheet)."""


class ParseError(LibsError):
    """A response did not have the expected shape."""


@dataclass
class Response:
    url: str
    status: int
    body: bytes
    content_type: str = ""

    def text(self) -> str:
        return self.body.decode("utf-8", "replace")

    def json(self) -> object:
        try:
            return json.loads(self.text())
        except json.JSONDecodeError as exc:
            raise ParseError(f"expected JSON from {_host(self.url)}: {exc}") from exc


def _host(url: str) -> str:
    try:
        return urllib.parse.urlsplit(url).netloc or "server"
    except ValueError:  # pragma: no cover
        return "server"


def _decompress(body: bytes, encoding: str) -> bytes:
    encoding = (encoding or "").lower()
    try:
        if encoding == "gzip":
            return gzip.decompress(body)
        if encoding == "deflate":
            return zlib.decompress(body)
    except (OSError, zlib.error) as exc:  # pragma: no cover
        raise TransportError(f"could not decompress response: {exc}") from exc
    return body


@dataclass
class HttpClient:
    """A deliberately boring HTTP client: paced, bounded, retried once."""

    interval: float = DEFAULT_INTERVAL
    timeout: float = 30.0
    max_bytes: int = MAX_API_BYTES
    user_agent: str = USER_AGENT
    _last: dict[str, float] = field(default_factory=dict, repr=False)
    calls: int = 0

    def _throttle(self, url: str) -> None:
        host = _host(url)
        previous = self._last.get(host, 0.0)
        wait = self.interval - (time.monotonic() - previous)
        if wait > 0:
            time.sleep(wait)
        self._last[host] = time.monotonic()

    def get(self, url: str, *, max_bytes: int | None = None) -> Response:
        cap = max_bytes or self.max_bytes
        headers = dict(HEADERS)
        headers["User-Agent"] = self.user_agent
        last_error: Exception | None = None
        for attempt in (1, 2):
            self._throttle(url)
            request = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as handle:
                    self.calls += 1
                    declared = handle.headers.get("Content-Length")
                    if declared and int(declared) > cap:
                        raise TransportError(
                            f"{_host(url)} returned {int(declared) // 1024} KB, above the "
                            f"{cap // 1024} KB cap")
                    body = handle.read(cap + 1)
                    if len(body) > cap:
                        raise TransportError(
                            f"{_host(url)} response exceeded the {cap // 1024} KB cap")
                    body = _decompress(body, handle.headers.get("Content-Encoding", ""))
                    return Response(url=url, status=handle.status, body=body,
                                    content_type=handle.headers.get("Content-Type", ""))
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code not in _RETRYABLE_STATUS or attempt == 2:
                    raise TransportError(
                        f"{_host(url)} answered HTTP {exc.code}") from None
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                delay = 3.0 * attempt
                with contextlib.suppress(TypeError, ValueError):
                    delay = max(delay, float(retry_after or 0))
                time.sleep(min(delay, 30.0))
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = exc
                if attempt == 2:
                    raise TransportError(
                        f"could not reach {_host(url)}: {exc}") from None
                time.sleep(3.0)
        raise TransportError(f"request to {_host(url)} failed: {last_error}")  # pragma: no cover


# --------------------------------------------------------------------------
# endpoint helpers
# --------------------------------------------------------------------------


def product_url(part: str) -> str:
    return API_PRODUCT.format(part=part)


def step_url(uuid: str) -> str:
    return API_STEP.format(uuid=uuid)


def obj_url(uuid: str) -> str:
    return API_OBJ.format(uuid=uuid)


def item_url(numeric_id: object) -> str:
    return f"https://item.szlcsc.com/{numeric_id}.html"


def fetch_product(client: HttpClient, part: str) -> dict:
    """The EasyEDA component record for *part* (symbol, footprint, model refs)."""
    response = client.get(product_url(part))
    if response.status != 200:
        raise TransportError(f"easyeda.com answered HTTP {response.status} for {part}")
    try:
        payload = response.json()
    except ParseError:
        raise ParseError(
            f"easyeda.com returned something other than JSON for {part} "
            "(the API throttles with an HTML page; retry later)") from None
    if not isinstance(payload, dict) or not payload.get("success"):
        raise NotFoundError(f"easyeda.com has no component record for {part}")
    result = payload.get("result")
    if not isinstance(result, dict):
        raise NotFoundError(f"easyeda.com returned an empty record for {part}")
    return result


def fetch_step(client: HttpClient, uuid: str) -> bytes:
    response = client.get(step_url(uuid), max_bytes=MAX_MODEL_BYTES)
    if response.status != 200:
        raise NotFoundError(f"no STEP model published (HTTP {response.status})")
    if not response.body.startswith(b"ISO-10303-21"):
        raise ParseError("the model endpoint did not return a STEP file")
    return response.body


def fetch_datasheet_url(client: HttpClient, part: str) -> str:
    """The datasheet PDF link for *part*, from the LCSC product-detail JSON.

    The storefront's item page carries the same link inside an embedded HTML data
    block; the JSON endpoint is smaller, structured, and cannot change shape without
    also breaking the store's own front end.
    """
    url = f"{API_WMS_DETAIL}?productCode={urllib.parse.quote(part)}"
    response = client.get(url)
    if response.status != 200:
        raise NotFoundError(f"lcsc.com product detail answered HTTP {response.status}")
    try:
        payload = response.json()
    except ParseError:
        raise ParseError("lcsc.com product detail returned something other than JSON") from None
    result = (payload.get("result") if isinstance(payload, dict) else None) or {}
    pdf = str(result.get("pdfUrl") or "").strip()
    if not pdf.startswith("http"):
        raise NotFoundError("no datasheet link published for this part")
    return pdf
