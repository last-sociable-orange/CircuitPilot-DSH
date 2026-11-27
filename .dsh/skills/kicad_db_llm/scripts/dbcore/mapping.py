"""Decide the symbol/footprint pair for a part, and prove the decision.

The rules this encodes (they are the project's rules, not preferences):

1. **Passives use the standard library.** A resistor/capacitor/inductor/ferrite/
   fuse/NTC/crystal is represented by a symbol in ``Standard.kicad_sym`` and, when
   a matching footprint exists, by a footprint in ``Standard.pretty``.
2. **Actives use the downloaded files.** An IC, connector or switch keeps the
   symbol and footprint that came from LCSC, because no standard equivalent can
   be assumed to match its pinout.
3. **Nothing is assumed silently.** A standard symbol is only used when its pins
   exist on the footprint, and — for anything with polarity or named functions —
   when the downloaded symbol's own pin names agree with it. When they do not,
   the downloaded symbol is used and the report says why.

The standard symbols/footprints are only ever *read*.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import classify as classify_mod
from .classify import Classification
from .libraries import FootprintInfo, LibrarySet, SymbolInfo
from .parts import BomLine, Part
from .schema import Record

_UNSAFE = re.compile(r"[^A-Za-z0-9._+-]+")

#: Symbols whose name states the package they were drawn for.
_PACKAGE_LOCKED = (
    (re.compile(r"_SOT23$"), ("sot23", "sot23-3")),
    (re.compile(r"_SOT23-5$"), ("sot23-5",)),
    (re.compile(r"_SOT23-6$"), ("sot23-6",)),
    (re.compile(r"_SO8$"), ("soic8", "sop8", "so8")),
    (re.compile(r"_DFN8$"), ("dfn8",)),
)

#: Classes where a two-terminal part carries no polarity, so an unnamed-pin
#: standard symbol is safe by construction.
POLARITY_FREE = {
    "RESISTOR",
    "CAPACITOR",
    "INDUCTOR",
    "FERRITE_BEAD",
    "FUSE",
    "FUSE_PTC",
    "THERMISTOR_NTC",
    "TESTPOINT",
    "MOUNTING",
    "DIODE_TVS_BIDIR",
}

MODES = ("auto", "all", "off")


def sanitise_name(text: str, *, fallback: str = "PART") -> str:
    cleaned = _UNSAFE.sub("_", (text or "").strip()).strip("._")
    cleaned = re.sub(r"_{2,}", "_", cleaned)
    return cleaned or fallback


def library_name(product_type: str, part: Part) -> str:
    """``IC`` + ``STM32G431C6T6`` → ``IC_STM32G431C6T6``."""
    identity = sanitise_name(part.mpn or part.lcsc, fallback=part.lcsc or "PART")
    prefix = sanitise_name(product_type, fallback="X").upper()
    if identity.upper().startswith(prefix + "_"):
        return identity
    return f"{prefix}_{identity}"


@dataclass
class Mapping:
    part: Part
    classification: Classification
    name: str
    symbol: str = ""
    footprint: str = ""
    symbol_source: str = "downloaded"  # "standard" | "downloaded" | "override"
    footprint_source: str = "downloaded"
    evidence: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    assumed: list[str] = field(default_factory=list)
    symbol_info: SymbolInfo | None = None
    footprint_info: FootprintInfo | None = None

    @property
    def ok(self) -> bool:
        return not self.blockers

    @property
    def uses_standard_symbol(self) -> bool:
        return self.symbol_source == "standard"

    @property
    def uses_standard_footprint(self) -> bool:
        return self.footprint_source == "standard"


def decide(
    part: Part,
    line: BomLine,
    libs: LibrarySet,
    *,
    mode: str = "auto",
    bundle_symbol: Path | None = None,
    bundle_footprint: Path | None = None,
) -> Mapping:
    """Work out ``KicadSymbolLibrary``/``KicadFootprintLibrary`` for *part*."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, not {mode!r}")

    classification = classify_mod.classify(part)
    product_type = (line.product_type or classification.product_type).strip()
    name = (line.name or library_name(product_type, part)).strip()
    mapping = Mapping(part=part, classification=classification, name=name)
    mapping.evidence.extend(classification.evidence)

    # Downloaded material: staged in kicad_lib, or still in the lcsc-libs bundle.
    downloaded_symbol = libs.part_symbol(name)
    if downloaded_symbol is None and bundle_symbol is not None and bundle_symbol.is_file():
        from .libraries import read_symbol_file

        symbols = read_symbol_file(bundle_symbol)
        downloaded_symbol = symbols.get(name) or (next(iter(symbols.values())) if symbols else None)

    downloaded_footprint = libs.part_footprint(name)
    if downloaded_footprint is None and bundle_footprint is not None and bundle_footprint.is_file():
        from .libraries import read_footprint_file

        downloaded_footprint = read_footprint_file(bundle_footprint)

    _decide_footprint(mapping, line, libs, downloaded_footprint, bundle_footprint)
    _decide_symbol(mapping, line, libs, downloaded_symbol, bundle_symbol, mode)
    _cross_check(mapping, libs, downloaded_symbol)
    _part_warnings(mapping)
    return mapping


# -- footprint -------------------------------------------------------------


def _decide_footprint(
    mapping: Mapping,
    line: BomLine,
    libs: LibrarySet,
    downloaded: FootprintInfo | None,
    bundle_path: Path | None,
) -> None:
    override = line.override_footprint()
    if override:
        _use_footprint_override(mapping, libs, override)
        return

    candidates = classify_mod.standard_footprint_candidates(mapping.classification)
    for candidate in candidates:
        info = libs.standard_footprint(candidate)
        if info is None:
            mapping.evidence.append(
                f"standard footprint {candidate!r} is not in {libs.standard_footprint_folder}"
            )
            continue
        if not info.electrical_pads:
            mapping.warnings.append(f"standard footprint {candidate} has no pads; ignored")
            continue
        mapping.footprint = f"{libs.config.standard_footprints.nickname}:{candidate}"
        mapping.footprint_source = "standard"
        mapping.footprint_info = info
        mapping.evidence.append(
            f"footprint {candidate} from the standard library "
            f"({len(info.electrical_pads)} pads, package {mapping.classification.chip_size})"
        )
        return

    nickname = libs.part_footprint_nickname(mapping.name)
    target = libs.part_footprint_path(mapping.name)
    if downloaded is not None:
        mapping.footprint = f"{nickname}:{mapping.name}"
        mapping.footprint_source = "downloaded"
        mapping.footprint_info = downloaded
        mapping.evidence.append(f"footprint from the downloaded file {downloaded.path.name}")
        return
    if bundle_path is not None and bundle_path.is_file():
        mapping.footprint = f"{nickname}:{mapping.name}"
        mapping.footprint_source = "downloaded"
        mapping.evidence.append(
            f"footprint not in the standard library for {mapping.classification.label}; "
            f"the bundle has {bundle_path.name}"
        )
        mapping.blockers.append(
            f"footprint {bundle_path.name} is not staged at {target}; "
            f"run 'stage' first (or copy it there as {mapping.name}.kicad_mod)"
        )
        return
    mapping.blockers.append(
        f"no footprint for {mapping.part.identity}: the standard library has none for "
        f"{mapping.classification.label!r} in package {mapping.part.package!r}, and "
        f"{target} does not exist. Download the part with the lcsc-libs skill, then stage it."
    )


def _use_footprint_override(mapping: Mapping, libs: LibrarySet, reference: str) -> None:
    info, problem = libs.resolve_footprint(reference)
    if info is None:
        mapping.blockers.append(f"footprint override {reference!r} does not resolve: {problem}")
        mapping.footprint = reference
        return
    mapping.footprint = reference
    mapping.footprint_source = (
        "standard"
        if reference.split(":", 1)[0] == libs.config.standard_footprints.nickname
        else "downloaded"
    )
    mapping.footprint_info = info
    mapping.evidence.append(f"footprint {reference} given explicitly in the BOM")


# -- symbol ----------------------------------------------------------------


def _decide_symbol(
    mapping: Mapping,
    line: BomLine,
    libs: LibrarySet,
    downloaded: SymbolInfo | None,
    bundle_path: Path | None,
    mode: str,
) -> None:
    override = line.override_symbol()
    if override:
        info, problem = libs.resolve_symbol(override)
        if info is None:
            mapping.blockers.append(f"symbol override {override!r} does not resolve: {problem}")
            mapping.symbol = override
            return
        mapping.symbol = override
        mapping.symbol_source = (
            "standard"
            if override.split(":", 1)[0] == libs.config.standard_symbol.nickname
            else "downloaded"
        )
        mapping.symbol_info = info
        mapping.evidence.append(f"symbol {override} given explicitly in the BOM")
        _complain_about_pin_mismatch(mapping, info)
        return

    if not _standard_symbol_allowed(mapping, mode):
        _use_downloaded_symbol(mapping, libs, downloaded, bundle_path)
        return

    pads = _pad_numbers(mapping)
    for candidate in classify_mod.standard_symbol_candidates(mapping.classification):
        info = libs.standard_symbols().get(candidate)
        if info is None:
            mapping.evidence.append(
                f"standard symbol {candidate!r} is not in {libs.standard_symbol_file.name}"
            )
            continue
        problem = _gate_standard_symbol(mapping, info, pads, downloaded, mode)
        if problem:
            mapping.evidence.append(f"standard symbol {candidate} rejected: {problem}")
            continue
        mapping.symbol = f"{libs.config.standard_symbol.nickname}:{candidate}"
        mapping.symbol_source = "standard"
        mapping.symbol_info = info
        mapping.evidence.append(f"symbol {candidate} from the standard library")
        return

    _use_downloaded_symbol(mapping, libs, downloaded, bundle_path)


def _standard_symbol_allowed(mapping: Mapping, mode: str) -> bool:
    if mode == "off":
        return False
    if not classify_mod.standard_symbol_candidates(mapping.classification):
        return False
    if mode == "auto":
        return mapping.classification.passive
    return True  # mode == "all"


def _use_downloaded_symbol(
    mapping: Mapping,
    libs: LibrarySet,
    downloaded: SymbolInfo | None,
    bundle_path: Path | None,
) -> None:
    nickname = libs.part_symbol_nickname(mapping.name)
    target = libs.part_symbol_path(mapping.name)
    if downloaded is not None:
        mapping.symbol = f"{nickname}:{mapping.name}"
        mapping.symbol_source = "downloaded"
        mapping.symbol_info = downloaded
        mapping.evidence.append(f"symbol from the downloaded file {downloaded.path.name}")
        return
    if bundle_path is not None and bundle_path.is_file():
        mapping.symbol = f"{nickname}:{mapping.name}"
        mapping.symbol_source = "downloaded"
        mapping.evidence.append(f"symbol would come from the bundle file {bundle_path.name}")
        mapping.blockers.append(
            f"symbol {bundle_path.name} is not staged at {target}; "
            f"run 'stage' first (or copy it there as {mapping.name}.kicad_sym)"
        )
        return
    mapping.blockers.append(
        f"no symbol for {mapping.part.identity}: no standard symbol fits "
        f"({mapping.classification.label}), and {target} does not exist. "
        f"Download the part with the lcsc-libs skill, then stage it."
    )


def _gate_standard_symbol(
    mapping: Mapping,
    info: SymbolInfo,
    pads: list[str],
    downloaded: SymbolInfo | None,
    mode: str,
) -> str:
    """Return the reason this standard symbol cannot be used, or ``""``."""
    if not info.pins:
        return "the symbol has no pins"
    pins = [pin.number for pin in info.pins]

    locked = _package_lock_failure(info.name, mapping.classification.package_family)
    if locked:
        return locked

    if pads and sorted(pins) != sorted(pads):
        return (
            f"pins {sorted(pins)} do not match the footprint pads {sorted(pads)}"
        )

    roles = info.roles()
    if not roles:
        if mapping.classification.code not in POLARITY_FREE:
            if mode != "force":
                return (
                    "the standard symbol's pins are unnamed, so its polarity/function cannot be "
                    "matched against the part"
                )
            mapping.assumed.append(
                f"{info.name} used for a {mapping.classification.label} on request; "
                "pin polarity was NOT verified"
            )
        return ""

    # The standard symbol names its pins: the downloaded symbol must agree.
    if downloaded is None:
        if mode == "force":
            mapping.assumed.append(
                f"{info.name} pin roles {roles} were assumed (no downloaded symbol to check)"
            )
            return ""
        return (
            "the standard symbol uses named pins and there is no downloaded symbol "
            "to confirm the pin mapping against"
        )
    downloaded_roles = downloaded.roles()
    if not downloaded_roles:
        if mode == "force":
            mapping.assumed.append(
                f"{info.name} pin roles {roles} were assumed; the downloaded symbol "
                f"({downloaded.name}) names its pins by number only"
            )
            return ""
        return (
            f"the downloaded symbol ({downloaded.name}) names its pins by number only, "
            f"so it cannot confirm {info.name}'s pin roles {roles}"
        )
    mismatched = [
        f"{number}: {downloaded_roles.get(number, '?')}≠{role}"
        for number, role in roles.items()
        if downloaded_roles.get(number) != role
    ]
    if mismatched:
        return f"pin roles disagree ({', '.join(mismatched)})"
    mapping.evidence.append(
        "pin roles confirmed against the downloaded symbol: "
        + ", ".join(f"{number}={role}" for number, role in roles.items())
    )
    return ""


def _package_lock_failure(symbol_name: str, package_family: str) -> str:
    for pattern, families in _PACKAGE_LOCKED:
        if pattern.search(symbol_name) and package_family not in families:
            return (
                f"{symbol_name} is drawn for {families[0].upper()}, "
                f"but the part is {package_family or 'an unknown package'}"
            )
    return ""


def _pad_numbers(mapping: Mapping) -> list[str]:
    info = mapping.footprint_info
    if info is None:
        return []
    return list(info.pad_numbers())


def _complain_about_pin_mismatch(mapping: Mapping, symbol: SymbolInfo) -> None:
    pads = _pad_numbers(mapping)
    pins = [pin.number for pin in symbol.pins]
    if not pads or not pins:
        return
    missing = [pin for pin in pins if pin not in pads]
    if missing:
        mapping.blockers.append(
            f"symbol {symbol.name} has pin(s) {missing} that the footprint "
            f"{mapping.footprint} does not have (pads: {pads})"
        )


# -- cross checks ----------------------------------------------------------


def _cross_check(mapping: Mapping, libs: LibrarySet, downloaded: SymbolInfo | None) -> None:
    """Report what KiCad will and will not find for this row."""
    if mapping.symbol and not mapping.blockers:
        info, problem = libs.resolve_symbol(mapping.symbol)
        if info is None:
            mapping.blockers.append(f"{mapping.symbol} does not resolve: {problem}")
    if mapping.footprint and not mapping.blockers:
        info, problem = libs.resolve_footprint(mapping.footprint)
        if info is None:
            mapping.blockers.append(f"{mapping.footprint} does not resolve: {problem}")

    if mapping.symbol and mapping.symbol_source == "downloaded":
        _nickname, _, symbol_name = mapping.symbol.partition(":")
        if mapping.symbol_info is not None and mapping.symbol_info.name != symbol_name:
            mapping.blockers.append(
                f"{mapping.symbol_info.path.name} declares symbol "
                f"{mapping.symbol_info.name!r}; KiCad looks it up as {symbol_name!r}"
            )

    if mapping.footprint and mapping.footprint_source == "downloaded":
        if mapping.footprint_info is not None:
            model = mapping.footprint_info.model
            if not model:
                mapping.warnings.append(
                    "the footprint has no 3D model reference; the board will show no model"
                )
            else:
                step = libs.step_file(mapping.name)
                if step is None:
                    mapping.warnings.append(
                        f"the footprint references {model} but {libs.config.step_folder}/"
                        f"{mapping.name}.stp is missing"
                    )

    if downloaded is None and mapping.symbol_source == "standard":
        info = mapping.symbol_info
        if info is not None and info.roles():
            # Belt and braces: a standard symbol with named pins is only chosen
            # when a downloaded symbol confirmed them, so this should not fire.
            mapping.warnings.append(
                f"{info.name} names its pins but no downloaded symbol was available to "
                "confirm them"
            )


def _part_warnings(mapping: Mapping) -> None:
    part = mapping.part
    status = part.status.strip()
    if status and status.lower() != "active":
        mapping.warnings.append(f"part status is {status!r}, not Active")
    if part.stock <= 0:
        mapping.warnings.append("no stock reported at lookup time")
    if not part.datasheet:
        mapping.warnings.append("the storefront published no datasheet link")
    if not part.unit_price():
        mapping.warnings.append("no price ladder reported")


# -- the row ---------------------------------------------------------------


def build_record(part: Part, line: BomLine, mapping: Mapping) -> Record:
    """Turn a decided mapping into the 80-column row."""
    record = Record()
    record.set("ID", part.id_column())
    record.set("Description", part.description or f"{part.identity} {part.package}".strip())
    record.set("Keywords", line.keywords or part.keywords)
    record.set("Value", line.value or part.value or part.identity)
    record.set("Manufacturer", part.manufacturer)
    record.set("ManufacturerProductNumber", part.identity)
    record.set("Package", part.package)
    record.set("KicadSymbolLibrary", mapping.symbol)
    record.set("KicadFootprintLibrary", mapping.footprint)
    record.set("PartStatus", part.status)
    record.set("QtyAvailable", str(part.stock) if part.stock else "0")
    record.set("Distributor", part.distributor)
    record.set("DistributorProductNumber", part.lcsc)
    record.set("UnitPrice", part.unit_price())
    record.set("ProductUrl", part.product_url)
    record.set("DatasheetUrl", part.datasheet)
    record.set_parameters(part.parameter_pairs())
    return record
