"""Make sure the project's library tables actually resolve what a page uses.

The tables are **not** a constant list here. What a page needs is discovered from its parts:
the nickname of every symbol the database points at, the database library itself, and the
nickname of every footprint the rows name. Those are then checked against the project's own
`sym-lib-table` / `fp-lib-table`:

* an entry that is **missing** is added, with a URI computed from the project layout
  (`config.py`) and the `kicad_lib` the build actually used;
* an entry that exists but **does not resolve** is reported and left untouched — that is a
  project setting, and silently rewriting it would hide the mistake;
* anything the tables declare beyond that is preserved byte for byte.

So the cad agent picks the project's settings up and verifies them; it never imposes a
hardcoded table.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from . import config

SYMBOL_TABLE = "sym-lib-table"
FOOTPRINT_TABLE = "fp-lib-table"


@dataclass(frozen=True)
class Need:
    """One library a page cannot load without."""

    table: str          # SYMBOL_TABLE or FOOTPRINT_TABLE
    name: str           # nickname as it appears in lib_id / footprint
    kind: str           # "KiCad" or "Database"
    target: Path        # what the URI must resolve to


@dataclass
class Report:
    """What the check found and what it changed."""

    added: list[str]
    unresolved: list[str]
    path: str | None = None
    changed: bool = False

    @property
    def ok(self) -> bool:
        return not self.unresolved

    @property
    def fatal(self) -> bool:
        """A missing symbol/database library blocks the page; a footprint one only warns."""
        return any("fp-lib-table" not in line for line in self.unresolved)


def needs(parts, database, libs_root: str | Path, dbl_path: str | Path | None) -> list[Need]:
    """Every library this page's parts require, discovered from the rows themselves."""
    libs_root = Path(libs_root).resolve()
    found: dict[tuple[str, str], Need] = {}

    def add(table: str, name: str, kind: str, target: Path) -> None:
        found.setdefault((table, name), Need(table, name, kind, target))

    for part in parts:
        nickname, _, symbol = (part.symbol_id or "").partition(":")
        if not nickname:
            continue
        # Two shapes exist: a monolithic `.kicad_sym` (Standard) and a directory holding one
        # file per symbol (Symbol). Declaring a single file for the directory shape makes
        # every other part in that library unresolvable.
        relative = config.SYMBOL_FILES.get(nickname)
        target = (
            libs_root / config.SYMBOL_DIR / relative
            if relative
            else libs_root / config.SYMBOL_DIR / nickname
        )
        add(SYMBOL_TABLE, nickname, "KiCad", target)

        foot_nick, _, foot_name = (part.footprint or "").partition(":")
        if foot_nick:
            folder = config.FOOTPRINT_FILES.get(foot_nick, f"{foot_nick}.pretty")
            add(
                FOOTPRINT_TABLE,
                foot_nick,
                "KiCad",
                libs_root / config.FOOTPRINT_DIR / folder,
            )

    if dbl_path:
        nickname = getattr(database, "nickname", None) or Path(dbl_path).stem
        add(
            SYMBOL_TABLE,
            nickname,
            "Database",
            Path(dbl_path).resolve(),
        )
    return sorted(found.values(), key=lambda need: (need.table, need.name))


def _uri(out_dir: Path, target: Path) -> str:
    try:
        return "${KIPRJMOD}/" + Path(os.path.relpath(target, out_dir)).as_posix()
    except ValueError:                     # different drive on Windows
        return target.as_posix()


def _entry(out_dir: Path, need: Need) -> str:
    if need.kind == "Database":
        description = "LCSC component database"
    elif need.table == FOOTPRINT_TABLE:
        description = config.FOOTPRINT_DESCR.get(need.name, f"{need.name} footprints")
    else:
        description = config.SYMBOL_DESCR.get(need.name, f"{need.name} symbols")
    uri = _uri(out_dir, need.target)
    return (
        f'\t(lib (name "{need.name}") (type "{need.kind}") (uri "{uri}") '
        f'(options "") (descr "{description}"))'
    )


def _declared(text: str) -> dict[str, str]:
    """`{nickname: uri}` for the entries a table already declares."""
    out: dict[str, str] = {}
    for match in re.finditer(
        r'\(lib\s+\(name\s+"([^"]+)"\).*?\(uri\s+"([^"]+)"\)', text
    ):
        out[match.group(1)] = match.group(2)
    return out


def _resolve(out_dir: Path, uri: str) -> Path:
    return Path(uri.replace("${KIPRJMOD}", str(out_dir)))


def check(
    out_dir: str | Path,
    needs_: list[Need],
    *,
    repair: bool = True,
) -> list[Report]:
    """Verify both tables; add what is missing, report what does not resolve."""
    out_dir = Path(out_dir).resolve()
    reports: list[Report] = []

    for table in (SYMBOL_TABLE, FOOTPRINT_TABLE):
        wanted = [need for need in needs_ if need.table == table]
        if not wanted:
            continue
        path = out_dir / table
        text = path.read_text(encoding="utf-8") if path.is_file() else f"({table.replace('-', '_')}\n)\n"
        declared = _declared(text)
        report = Report(added=[], unresolved=[], path=str(path))

        for need in wanted:
            if need.name in declared:
                if not _resolve(out_dir, declared[need.name]).exists():
                    report.unresolved.append(
                        f"{table}: '{need.name}' is declared but "
                        f"{_resolve(out_dir, declared[need.name])} does not exist"
                    )
                continue
            if not need.target.exists():
                report.unresolved.append(
                    f"{table}: '{need.name}' is not declared and {need.target} is missing too"
                )
                continue
            if not repair:
                report.added.append(f"{table}: '{need.name}' is not declared")
                continue
            entry = _entry(out_dir, need)
            cut = text.rstrip().rfind(")")
            text = text[:cut] + entry + "\n" + text[cut:]
            declared[need.name] = _uri(out_dir, need.target)
            report.added.append(f"{table}: added '{need.name}'")
            report.changed = True

        if report.changed:
            path.write_text(text, encoding="utf-8", newline="\n")
        reports.append(report)

    return reports


def summary(reports: list[Report]) -> dict:
    """The `lib_tables` block of the build report."""
    return {
        "added": [line for report in reports for line in report.added],
        "unresolved": [line for report in reports for line in report.unresolved],
        "files": [report.path for report in reports if report.path],
    }
