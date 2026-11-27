"""Small, defensive conversions shared by both storefront backends.

The storefronts mix types freely (``productId`` is an ``int`` in search rows and
a ``str`` on item pages; prices arrive as ``int``, ``float`` or ``str``) and wrap
matched text in highlight markup, so every value goes through these helpers.
"""

# Vendored from KiCad LibGen LCSC (KicadLibGui-LCSC 1.0.0) at commit 60c89f8.
# Do not edit: refresh with scripts/refresh_client.py.
from __future__ import annotations

import html
import re
from decimal import Decimal, InvalidOperation
from typing import Any

#: An LCSC part number: ``C`` followed by up to 18 digits.
PART_RE = re.compile(r"^C[0-9]{1,18}$")

_TAG_RE = re.compile(r"<[^>]*>")
_SQUEEZE_RE = re.compile(r"[ \t\r\n]+")
_DIGITS_RE = re.compile(r"^[0-9]{1,18}$")
#: Resistance units stripped when deriving a KiCad ``Value``.  Only ohms are
#: stripped, mirroring upstream's ``"Ohms" in value`` rule: stripping ``F``/``H``
#: would turn ``100nF`` into ``100n`` and lose the unit entirely.
_OHM_UNITS = ("ohms", "ohm", "Ω")



def strip_markup(value: Any) -> str:
    """Remove highlight markup and decode entities.

    Domestic search results wrap a value that matched the keyword, e.g.
    ``<SPAN CLASS='LUCENE_HIGHLIGHT_CLASS'>10kΩ</SPAN>``; storing that in the
    database would be useless.
    """
    if value is None:
        return ""
    text = str(value)
    if "<" in text or "&" in text:
        text = _TAG_RE.sub("", text)
        text = html.unescape(text)
    return text


def text(value: Any, limit: int = 240) -> str:
    """Trimmed, markup-free, length-capped string (``""`` for non-scalars)."""
    if value is None or isinstance(value, (dict, list, tuple, bool, bytes)):
        return ""
    cleaned = _SQUEEZE_RE.sub(" ", strip_markup(value)).strip()
    return cleaned[:limit]


def long_text(value: Any, limit: int = 16384) -> str:
    """Like :func:`text` but keeps line structure for descriptions."""
    if value is None or isinstance(value, (dict, list, tuple, bool, bytes)):
        return ""
    cleaned = strip_markup(value).strip()
    return cleaned[:limit]


def public_url(value: Any) -> str:
    """Return *value* only when it is an https URL without credentials.

    Protocol-relative URLs (``//host/path``) are upgraded.  Anything else -
    ``javascript:``, ``http:``, ``file:``, ``user:pass@host`` - becomes ``""``.
    """
    if not isinstance(value, str):
        return ""
    candidate = value.strip()
    if candidate.startswith("//"):
        candidate = "https:" + candidate
    if not candidate.lower().startswith("https://"):
        return ""
    rest = candidate[len("https://"):]
    host = rest.split("/", 1)[0]
    if not host or "@" in host:
        return ""
    return candidate


def product_id(value: Any) -> str:
    """The storefront's numeric product identity (digits only), else ``""``."""
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return ""
    candidate = str(value).strip()
    return candidate if _DIGITS_RE.match(candidate) else ""


def part_number(value: Any) -> str:
    """Upper-cased, validated LCSC part number, else ``""``."""
    candidate = text(value, 24).upper()
    return candidate if PART_RE.match(candidate) else ""


def decimal_number(value: Any) -> Decimal | None:
    """Parse a price/quantity defensively; ``None`` when it is not a usable number."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        return None
    raw = str(value).strip()
    if not raw or len(raw) > 64:
        return None
    try:
        number = Decimal(raw)
    except InvalidOperation:
        return None
    if not number.is_finite() or number < 0 or not -30 <= number.adjusted() <= 18:
        return None
    return number


def quantity(value: Any) -> int | None:
    """An integral quantity, or ``None`` for ``-1``/``null``/fractions."""
    number = decimal_number(value)
    if number is None or number != number.to_integral_value():
        return None
    return int(number)


def format_price(value: Any) -> str:
    """Fixed-point price text with no exponent and no rounding beyond the source."""
    number = decimal_number(value)
    if number is None:
        return ""
    return format(number, "f")


def derive_value(mpn: str, pairs: list[tuple[str, str]], names: frozenset[str]) -> str:
    """Derive the KiCad ``Value`` column from a value-type parameter.

    DigiKey reported ``10kOhms`` and upstream stripped the unit; LCSC reports
    ``10kΩ``, which becomes ``10K``.  Other value kinds are returned verbatim
    (``100nF`` stays ``100nF``), which is also what upstream did for them.
    """
    for name, value in pairs:
        if name.strip().lower() not in names:
            continue
        candidate = strip_markup(value).strip()
        if not candidate:
            continue
        lowered = candidate.lower()
        for unit in _OHM_UNITS:
            if not lowered.endswith(unit.lower()):
                continue
            remainder = candidate[: -len(unit)].strip()
            if remainder:
                return remainder.upper()
            break
        return candidate
    return mpn
