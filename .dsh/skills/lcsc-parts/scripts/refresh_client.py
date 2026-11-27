#!/usr/bin/env python3
"""Vendor the LCSC client modules from KiCad LibGen LCSC into the skill.

The skill must work on its own, so it carries its own copy of the protocol code.
This script performs the copy and the import rewriting, and records provenance so
the copy can be refreshed deliberately instead of drifting.

    python scripts/refresh_client.py                 # refresh from ../KicadLibGui-LCSC
    python scripts/refresh_client.py --source <path> --check

Only needs to be run when the parent project's protocol code changes; using the
skill never needs this script.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent          # .../skills/lcsc-parts
DEFAULT_SOURCE = SKILL.parent.parent / "KicadLibGui-LCSC"
DEST = SKILL / "scripts" / "lcsc_client"

#: (source relative path, destination module name)
MODULES = (
    ("kicad_core/models.py", "models.py"),
    ("kicad_core/errors.py", "errors.py"),
    ("lcsc_core/text.py", "text.py"),
    ("lcsc_core/cache.py", "cache.py"),
    ("lcsc_core/session.py", "session.py"),
    ("lcsc_core/base.py", "base.py"),
    ("lcsc_core/parsers.py", "parsers.py"),
    ("lcsc_core/domestic.py", "domestic.py"),
    ("lcsc_core/international.py", "international.py"),
    ("lcsc_core/routing.py", "routing.py"),
    ("services/search_service.py", "service.py"),
)

#: Rewrites that make the copied modules a self-contained package.
REWRITES = (
    (r"^from kicad_core\.models import", "from .models import"),
    (r"^from kicad_core\.errors import", "from .errors import"),
    (r"^from lcsc_core\.(\w+) import", r"from .\1 import"),
    (r"^from lcsc_core import", "from . import"),
)

INIT = '''"""Self-contained LCSC / SZLCSC client used by the lcsc-parts skill.

Vendored from KiCad LibGen LCSC {version} at commit {commit} on {date}.
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
'''

BANNER = (
    "# Vendored from KiCad LibGen LCSC ({origin}) at commit {commit}.\n"
    "# Do not edit: refresh with scripts/refresh_client.py.\n"
)


def git(source: Path, *args: str) -> str:
    try:
        result = subprocess.run(("git", "-C", str(source), *args),
                                capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return ""
    return result.stdout.strip()


def version_of(source: Path) -> str:
    text = (source / "version.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    return match.group(1) if match else "unknown"


def rewrite(text: str, *, origin: str, commit: str) -> str:
    for pattern, replacement in REWRITES:
        text = re.sub(pattern, replacement, text, flags=re.MULTILINE)
    # A shebang or encoding line must stay first, so the banner follows the
    # module docstring instead: keep the docstring, then the banner.
    banner = BANNER.format(origin=origin, commit=commit)
    if text.startswith('"""'):
        end = text.find('"""', 3)
        if end != -1:
            end += 3
            return text[:end] + "\n\n" + banner + text[end:].lstrip("\n")
    return banner + text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", default=str(DEFAULT_SOURCE))
    parser.add_argument("--check", action="store_true",
                        help="report differences without writing")
    args = parser.parse_args(argv)

    source = Path(args.source).expanduser().resolve()
    if not (source / "lcsc_core").exists():
        raise SystemExit(f"{source} does not look like the KiCad LibGen LCSC project")

    commit = git(source, "rev-parse", "--short", "HEAD") or "unknown"
    date = git(source, "log", "-1", "--format=%cs") or "unknown"
    version = version_of(source)
    origin = f"{source.name} {version}"

    changed = []
    for src_rel, dest_name in MODULES:
        src = source / src_rel
        if not src.exists():
            raise SystemExit(f"missing source module: {src_rel}")
        text = rewrite(src.read_text(encoding="utf-8"), origin=origin, commit=commit)
        dest = DEST / dest_name
        if dest.exists() and dest.read_text(encoding="utf-8") == text:
            continue
        changed.append(dest_name)
        if not args.check:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding="utf-8")

    init_text = INIT.format(version=version, commit=commit, date=date)
    init_path = DEST / "__init__.py"
    if not init_path.exists() or init_path.read_text(encoding="utf-8") != init_text:
        changed.append("__init__.py")
        if not args.check:
            init_path.write_text(init_text, encoding="utf-8")

    verb = "would update" if args.check else "updated"
    print(f"source : {source} ({version}, commit {commit}, {date})")
    print(f"dest   : {DEST.relative_to(SKILL)}")
    print(f"{verb}: {', '.join(changed) if changed else 'nothing (already in sync)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
