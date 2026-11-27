"""Bundled naming rules for the lcsc-libs skill."""

from __future__ import annotations

import re

_UNSAFE = re.compile(r"[^A-Za-z0-9._+-]+")


def sanitise(text: str, *, fallback: str = "part") -> str:
    """Make a string safe for a file name and a KiCad identifier."""
    cleaned = _UNSAFE.sub("_", (text or "").strip()).strip("._")
    return cleaned or fallback


def bundle_name(part: str, mpn: str) -> str:
    """``C8734`` + ``STM32F103C8T6`` -> ``C8734_STM32F103C8T6``.

    The LCSC number keeps bundles unique; the MPN keeps them readable.
    """
    part = sanitise(part.upper(), fallback="C").upper()
    mpn = sanitise(mpn or part, fallback=part)
    if mpn.upper() == part:
        return part
    return f"{part}_{mpn}"


def symbol_name(mpn: str, part: str) -> str:
    """KiCad symbol names use the MPN, falling back to the LCSC number."""
    return sanitise(mpn or part, fallback=part)


def footprint_name(part: str, mpn: str) -> str:
    """The footprint is named after the bundle.

    KiCad identifies a footprint by its file name inside the ``.pretty`` folder, so
    naming it after the bundle keeps ``<bundle>.pretty/<bundle>.kicad_mod`` and the
    footprint inside it all identical — the EasyEDA package name is kept in the
    footprint's tags instead.
    """
    return bundle_name(part, mpn)
