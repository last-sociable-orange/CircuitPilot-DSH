"""Move an ``lcsc-libs`` bundle into the library tree, under the project's name.

``lcsc-libs`` writes a bundle named after the LCSC number::

    C8734_STM32F103C8T6.kicad_sym        symbol named "STM32F103C8T6"
    C8734_STM32F103C8T6.pretty/…kicad_mod
    Step/C8734_STM32F103C8T6.step

The library tree wants ``<TYPE>_<MPN>`` with the *symbol name equal to the file
name*, and a model path KiCad can resolve. Staging is a rename, nothing more:

* the symbol is renamed (``STM32F103C8T6`` → ``IC_STM32F103C8T6``) and its
  ``Footprint`` field is pointed at the new name,
* the footprint is renamed and its ``(model …)`` path is set to
  ``${KIPRJMOD}/../kicad_lib/Step/<NAME>.stp``,
* the STEP file is copied under the new name.

Existing files are never replaced. If the target already exists the file is
skipped and reported, because someone may have reviewed and edited it by hand.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from . import sexpr
from .config import Config
from .libraries import LibraryProblem, assert_writable


@dataclass
class BundlePart:
    lcsc: str
    symbol: Path | None = None
    footprint: Path | None = None
    model: Path | None = None
    datasheet: Path | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class StagedFile:
    kind: str
    source: Path
    target: Path
    action: str  # "copy" | "skip-exists" | "missing"
    note: str = ""


@dataclass
class StageResult:
    name: str
    files: list[StagedFile] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    #: vendor-data notes from lcsc-libs (a skipped drawing op, a missing symbol);
    #: worth reporting, but they do not mean staging failed
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def read_bundle(folder: str | Path) -> dict[str, BundlePart]:
    """Index an ``lcsc-libs`` output folder, keyed by LCSC part number."""
    root = Path(folder)
    if not root.is_dir():
        raise LibraryProblem(f"no bundle folder at {root}")
    parts: dict[str, BundlePart] = {}
    manifest = root / "manifest.json"
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            data = {}
        if isinstance(data, dict):
            for key, entry in data.items():
                if not isinstance(entry, dict):
                    continue
                lcsc = str((entry.get("part") or {}).get("lcsc") or key).upper()
                bundle = BundlePart(lcsc=lcsc)
                for artefact in entry.get("artefacts") or []:
                    if not isinstance(artefact, dict):
                        continue
                    path = _bundle_path(root, str(artefact.get("path") or ""))
                    _assign(bundle, path)
                for warning in entry.get("warnings") or []:
                    bundle.warnings.append(str(warning))
                parts[lcsc] = bundle
    if parts:
        return parts

    # No manifest: fall back to scanning the conventional sub-folders.
    for folder_name in ("symbols", "footprints", "Step", "datasheets"):
        directory = root / folder_name
        if not directory.is_dir():
            continue
        for item in directory.rglob("*"):
            if not item.is_file():
                continue
            lcsc = _lcsc_from_name(item.stem)
            if not lcsc:
                continue
            bundle = parts.setdefault(lcsc, BundlePart(lcsc=lcsc))
            _assign(bundle, item)
    for bundle in parts.values():
        if bundle.symbol is None:
            bundle.warnings.append("no symbol in the bundle")
        if bundle.footprint is None:
            bundle.warnings.append("no footprint in the bundle")
    return parts


def _bundle_path(root: Path, recorded: str) -> Path:
    """Locate an artefact the manifest names, tolerating a repeated folder prefix.

    ``lcsc-libs`` records the path it wrote, which may already start with the
    output folder (``WIP/lcsc-libs-out/symbols/x.kicad_sym``). Joining that to the
    bundle root would look in ``WIP/lcsc-libs-out/WIP/lcsc-libs-out/…``, so the
    suffixes of the recorded path are tried against the root as well.
    """
    candidate = Path(recorded)
    if not recorded:
        return candidate
    attempts: list[Path] = []
    if candidate.is_absolute():
        attempts.append(candidate)
    else:
        attempts.append(root / candidate)
        attempts.append(candidate)
        parts = candidate.parts
        for start in range(1, len(parts)):
            attempts.append(root.joinpath(*parts[start:]))
    for attempt in attempts:
        if attempt.is_file():
            return attempt
    return attempts[0]


def _assign(bundle: BundlePart, path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix == ".kicad_sym":
        bundle.symbol = path
    elif suffix == ".kicad_mod":
        bundle.footprint = path
    elif suffix in (".stp", ".step"):
        bundle.model = path
    elif suffix == ".pdf":
        bundle.datasheet = path


def _lcsc_from_name(stem: str) -> str:
    for token in stem.replace("-", "_").split("_"):
        if token[:1].upper() == "C" and token[1:].isdigit():
            return token.upper()
    return ""


def stage(
    config: Config,
    name: str,
    bundle: BundlePart,
    *,
    apply: bool,
) -> StageResult:
    """Copy *bundle* into the library tree as *name* (dry run unless ``apply``)."""
    result = StageResult(name=name)
    symbol_target = config.part_symbols.path / f"{name}{config.symbol_suffix}"
    footprint_target = config.part_footprints.path / f"{name}{config.footprint_suffix}"
    model_target = config.step_folder / f"{name}.stp"

    for path in (symbol_target, footprint_target, model_target):
        assert_writable(config, path)

    # -- symbol -------------------------------------------------------
    if bundle.symbol is None:
        result.problems.append("the bundle has no symbol; nothing to stage for the symbol")
    elif not bundle.symbol.is_file():
        result.problems.append(f"the bundle's symbol is missing: {bundle.symbol}")
    else:
        if symbol_target.exists():
            result.files.append(
                StagedFile("symbol", bundle.symbol, symbol_target, "skip-exists")
            )
        else:
            text = bundle.symbol.read_text(encoding="utf-8-sig", errors="replace")
            roots = sexpr.parse(text)
            library = next(
                (node for node in roots if sexpr.head(node) == "kicad_symbol_lib"), None
            )
            symbol_node = sexpr.find(library, "symbol") if library else None
            old_name = sexpr.atom(symbol_node, 1) if symbol_node else ""
            if not old_name:
                result.problems.append(f"{bundle.symbol.name} declares no symbol")
            else:
                text, changed = sexpr.rename_symbol(text, old_name, name)
                if not changed:
                    result.problems.append(
                        f"could not rename symbol {old_name!r} in {bundle.symbol.name}"
                    )
                text, field_changed = sexpr.set_footprint_field(
                    text, f"{config.part_footprints.nickname}:{name}"
                )
                if not field_changed:
                    result.problems.append(
                        f"{bundle.symbol.name} has no Footprint field to point at {name}"
                    )
                result.files.append(
                    StagedFile(
                        "symbol",
                        bundle.symbol,
                        symbol_target,
                        "copy",
                        note=f"symbol {old_name} → {name}",
                    )
                )
                if apply:
                    symbol_target.parent.mkdir(parents=True, exist_ok=True)
                    symbol_target.write_text(text, encoding="utf-8")

    # -- footprint ----------------------------------------------------
    if bundle.footprint is None:
        result.problems.append(
            "the bundle has no footprint; the row cannot reference Footprint:" + name
        )
    elif not bundle.footprint.is_file():
        result.problems.append(f"the bundle's footprint is missing: {bundle.footprint}")
    elif footprint_target.exists():
        result.files.append(
            StagedFile("footprint", bundle.footprint, footprint_target, "skip-exists")
        )
    else:
        text = bundle.footprint.read_text(encoding="utf-8-sig", errors="replace")
        text, changed = sexpr.rename_footprint(text, name)
        if not changed:
            result.problems.append(f"{bundle.footprint.name} has no footprint header")
        if bundle.model is not None:
            text, model_changed = sexpr.set_model_path(
                text, config.model_reference(name)
            )
            if not model_changed:
                result.problems.append(
                    f"{bundle.footprint.name} has no (model …) block to repoint"
                )
        result.files.append(StagedFile("footprint", bundle.footprint, footprint_target, "copy"))
        if apply:
            footprint_target.parent.mkdir(parents=True, exist_ok=True)
            footprint_target.write_text(text, encoding="utf-8")

    # -- model --------------------------------------------------------
    if bundle.model is None:
        result.files.append(StagedFile("model", Path(), model_target, "missing",
                                       note="the bundle has no STEP file"))
    elif model_target.exists():
        result.files.append(StagedFile("model", bundle.model, model_target, "skip-exists"))
    else:
        result.files.append(StagedFile("model", bundle.model, model_target, "copy"))
        if apply:
            model_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(bundle.model, model_target)

    for warning in bundle.warnings:
        result.warnings.append(f"lcsc-libs: {warning}")
    return result
