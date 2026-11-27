"""kicad_db_llm — fill a KiCad database-library SQLite file from LCSC parts.

The package is deliberately dependency-free (standard library only). Network
access, when used at all, happens through the sibling ``lcsc-parts`` skill's CLI
as a subprocess, never by importing a storefront client here.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "1.0.0"
