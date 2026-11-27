"""Where things live: the library tree, the database, and the sibling skills.

Defaults describe the ``kicad_lib`` layout this skill was written for:

    kicad_lib/
      Symbol/Standard/Standard.kicad_sym     read-only standard symbols
      Symbol/Symbol/<NAME>.kicad_sym         one downloaded symbol per file
      Footprint/Standard.pretty/<NAME>.kicad_mod
      Footprint/Footprint.pretty/<NAME>.kicad_mod
      Step/<NAME>.stp
      components.db                          the database library

Everything is overridable, because another project may name its tree
differently. Override order, lowest priority first:

1. the defaults below,
2. ``kicad_db.json`` next to this skill's ``SKILL.md``,
3. ``--config <file>``,
4. explicit command-line flags (``--libs-root``, ``--db``).
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = SKILL_ROOT / "scripts"

DEFAULTS: dict[str, Any] = {
    #: root of the library tree; resolved at runtime when left empty
    "libs_root": "",
    #: the SQLite file KiCad's database library reads; resolved from libs_root
    "database": "",
    "symbols": {
        "standard": {
            "nickname": "Standard",
            "file": "Symbol/Standard/Standard.kicad_sym",
        },
        "parts": {
            "nickname": "Symbol",
            "folder": "Symbol/Symbol",
            "suffix": ".kicad_sym",
        },
    },
    "footprints": {
        "standard": {
            "nickname": "Standard",
            "folder": "Footprint/Standard.pretty",
        },
        "parts": {
            "nickname": "Footprint",
            "folder": "Footprint/Footprint.pretty",
            "suffix": ".kicad_mod",
        },
    },
    "models": {
        "folder": "Step",
        "suffixes": [".stp", ".step"],
        #: written into a staged footprint's (model …) block
        "reference": "${KIPRJMOD}/../kicad_lib/Step/{name}.stp",
    },
    #: sibling skills, called as subprocesses
    "lcsc_parts": "",
    "lcsc_libs": "",
    #: en_US (lcsc.com, USD, English parameters) or zh_CN (szlcsc.com, CNY)
    "language": "en_US",
}


class ConfigProblem(RuntimeError):
    """A configuration the skill cannot act on."""


def _default_libs_root() -> str:
    """Find ``kicad_lib`` by walking up from the skill; empty when not found."""
    for parent in [SKILL_ROOT, *SKILL_ROOT.parents]:
        candidate = parent / "kicad_lib"
        if candidate.is_dir():
            return str(candidate)
    return ""


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise ConfigProblem(f"cannot read config {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigProblem(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigProblem(f"{path} must contain a JSON object")
    return data


@dataclass
class Location:
    """One library: a nickname plus the file or folder behind it."""

    nickname: str
    path: Path
    is_folder: bool

    def describe(self) -> str:
        kind = "folder" if self.is_folder else "file"
        return f"{self.nickname} ({kind}: {self.path})"


@dataclass
class Config:
    data: dict[str, Any] = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)

    # -- paths ---------------------------------------------------------

    @property
    def libs_root(self) -> Path:
        raw = str(self.data.get("libs_root") or "").strip()
        if not raw:
            raise ConfigProblem(
                "no kicad_lib folder found. Pass --libs-root <path to kicad_lib> "
                "or set 'libs_root' in kicad_db.json."
            )
        return Path(raw).expanduser()

    @property
    def database(self) -> Path:
        raw = str(self.data.get("database") or "").strip()
        if raw:
            return Path(raw).expanduser()
        return self.libs_root / "components.db"

    def path(self, relative: str) -> Path:
        candidate = Path(relative).expanduser()
        return candidate if candidate.is_absolute() else self.libs_root / candidate

    # -- libraries -----------------------------------------------------

    @property
    def standard_symbol(self) -> Location:
        section = self.data["symbols"]["standard"]
        return Location(str(section["nickname"]), self.path(str(section["file"])), False)

    @property
    def part_symbols(self) -> Location:
        section = self.data["symbols"]["parts"]
        return Location(str(section["nickname"]), self.path(str(section["folder"])), True)

    @property
    def standard_footprints(self) -> Location:
        section = self.data["footprints"]["standard"]
        return Location(str(section["nickname"]), self.path(str(section["folder"])), True)

    @property
    def part_footprints(self) -> Location:
        section = self.data["footprints"]["parts"]
        return Location(str(section["nickname"]), self.path(str(section["folder"])), True)

    @property
    def symbol_suffix(self) -> str:
        return str(self.data["symbols"]["parts"].get("suffix") or ".kicad_sym")

    @property
    def footprint_suffix(self) -> str:
        return str(self.data["footprints"]["parts"].get("suffix") or ".kicad_mod")

    @property
    def step_folder(self) -> Path:
        return self.path(str(self.data["models"]["folder"]))

    @property
    def step_suffixes(self) -> tuple[str, ...]:
        return tuple(str(item) for item in self.data["models"]["suffixes"])

    def model_reference(self, name: str) -> str:
        # ``{name}`` is substituted; ``${KIPRJMOD}`` and any other braces are left
        # alone, which ``str.format`` would not do.
        return str(self.data["models"]["reference"]).replace("{name}", name)

    # -- sibling skills -------------------------------------------------

    @property
    def lcsc_parts_cli(self) -> Path:
        raw = str(self.data.get("lcsc_parts") or "").strip()
        if raw:
            return Path(raw).expanduser()
        return SKILL_ROOT.parent / "lcsc-parts" / "scripts" / "lcsc.py"

    @property
    def lcsc_libs_cli(self) -> Path:
        raw = str(self.data.get("lcsc_libs") or "").strip()
        if raw:
            return Path(raw).expanduser()
        return SKILL_ROOT.parent / "lcsc-libs" / "scripts" / "lcsc_libs.py"

    @property
    def language(self) -> str:
        return str(self.data.get("language") or "en_US")


def load(
    *,
    config_path: str | Path | None = None,
    libs_root: str | Path | None = None,
    database: str | Path | None = None,
    language: str | None = None,
) -> Config:
    data = copy.deepcopy(DEFAULTS)
    sources: list[str] = []
    if not data["libs_root"]:
        found = _default_libs_root()
        if found:
            data["libs_root"] = found
            sources.append(f"auto-detected libs_root: {found}")

    local = SKILL_ROOT / "kicad_db.json"
    if local.is_file():
        data = _deep_merge(data, _read_json(local))
        sources.append(f"merged {local}")
    if config_path:
        path = Path(config_path).expanduser()
        data = _deep_merge(data, _read_json(path))
        sources.append(f"merged {path}")
    if libs_root:
        data["libs_root"] = str(Path(libs_root).expanduser())
        data["database"] = ""  # follow the new root unless --db says otherwise
        sources.append(f"libs_root from command line: {data['libs_root']}")
    if database:
        data["database"] = str(Path(database).expanduser())
        sources.append(f"database from command line: {data['database']}")
    if language:
        # The CLI flag must beat both the default and the config file, otherwise a part
        # that only exists on one storefront reads as a missing part.
        data["language"] = str(language)
        sources.append(f"language from command line: {data['language']}")
    return Config(data=data, sources=sources)
