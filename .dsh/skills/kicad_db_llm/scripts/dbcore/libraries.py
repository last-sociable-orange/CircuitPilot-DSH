"""Read the KiCad library tree and answer one question well:

    does ``Nickname:Name`` point at something that exists, and what is inside it?

Nothing here writes to the standard libraries. :func:`assert_writable` refuses any
path that lands in ``Standard.kicad_sym`` or ``Standard.pretty`` so a bug cannot
silently edit the user's curated library.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import sexpr
from .config import Config, Location


class LibraryProblem(RuntimeError):
    """The library tree is missing something the caller needs."""


@dataclass(frozen=True)
class Pin:
    number: str
    name: str
    electrical_type: str

    @property
    def label(self) -> str:
        name = self.name.strip()
        if name in ("", "~"):
            return f"{self.number}"
        return f"{self.number}={name}"


@dataclass(frozen=True)
class Pad:
    number: str
    kind: str  # smd | thru_hole | np_thru_hole | connect

    @property
    def is_mechanical(self) -> bool:
        """Pads with no electrical number (mounting, shield, paste-only)."""
        if not self.number:
            return True
        return not any(char.isdigit() for char in self.number)


@dataclass
class SymbolInfo:
    name: str
    path: Path
    pins: list[Pin] = field(default_factory=list)

    @property
    def pin_numbers(self) -> list[str]:
        return [pin.number for pin in self.pins]

    def pins_by_number(self) -> dict[str, Pin]:
        return {pin.number: pin for pin in self.pins}

    def roles(self) -> dict[str, str]:
        """Pin number → normalised role, inferred from the pin *name*.

        ``{"1": "A", "2": "K"}`` for a diode written with named pins. Pins named
        with bare numbers yield no roles at all, which is the honest answer: the
        file does not say what they are.
        """
        out: dict[str, str] = {}
        for pin in self.pins:
            role = normalise_role(pin.name)
            if role:
                out[pin.number] = role
        return out


@dataclass
class FootprintInfo:
    name: str
    path: Path
    pads: list[Pad] = field(default_factory=list)
    model: str = ""

    @property
    def electrical_pads(self) -> list[Pad]:
        return [pad for pad in self.pads if not pad.is_mechanical]

    def pad_numbers(self) -> list[str]:
        return [pad.number for pad in self.electrical_pads]

    @property
    def attributes(self) -> set[str]:
        return {pad.kind for pad in self.pads}


_ROLE_ALIASES: dict[str, str] = {
    "+": "POS",
    "POS": "POS",
    "POSITIVE": "POS",
    "V+": "POS",
    "-": "NEG",
    "NEG": "NEG",
    "NEGATIVE": "NEG",
    "V-": "NEG",
    "A": "A",
    "ANODE": "A",
    "K": "K",
    "C": "K",
    "CATHODE": "K",
    "G": "G",
    "GATE": "G",
    "S": "S",
    "SOURCE": "S",
    "D": "D",
    "DRAIN": "D",
    "GND": "GND",
    "VSS": "GND",
    "X": "XTAL",
    "XI": "XTAL",
    "XO": "XTAL",
    "XTAL": "XTAL",
    "IN+": "IN+",
    "IN-": "IN-",
    "OUT": "OUT",
    "VCC": "V+",
    "VDD": "V+",
}


def normalise_role(name: str) -> str:
    """Map a pin name to a coarse role, or ``""`` when it says nothing useful."""
    cleaned = name.strip().upper().replace(" ", "")
    if not cleaned or cleaned in {"~", "1", "2", "3", "4", "5", "6", "7", "8"}:
        return ""
    if cleaned.isdigit():
        return ""
    return _ROLE_ALIASES.get(cleaned, "")


def _pins_of_symbol(node: sexpr.Node) -> list[Pin]:
    pins: list[Pin] = []
    for pin_node in sexpr.walk(node, "pin"):
        number = ""
        name = ""
        name_node = sexpr.find(pin_node, "number")
        if name_node is not None:
            number = sexpr.atom(name_node, 1)
        label_node = sexpr.find(pin_node, "name")
        if label_node is not None:
            name = sexpr.atom(label_node, 1)
        if not number:
            continue
        pins.append(
            Pin(
                number=number,
                name=name,
                electrical_type=sexpr.atom(pin_node, 1),
            )
        )
    return pins


def read_symbol_file(path: Path) -> dict[str, SymbolInfo]:
    """Every top-level symbol in a ``.kicad_sym`` file, keyed by name."""
    roots = sexpr.load(path)
    library = next((node for node in roots if sexpr.head(node) == "kicad_symbol_lib"), None)
    if library is None:
        raise LibraryProblem(f"{path} is not a kicad_symbol_lib file")
    symbols: dict[str, SymbolInfo] = {}
    for node in sexpr.children(library, "symbol"):
        name = sexpr.atom(node, 1)
        if not name:
            continue
        symbols[name] = SymbolInfo(name=name, path=path, pins=_pins_of_symbol(node))
    return symbols


def read_footprint_file(path: Path) -> FootprintInfo:
    roots = sexpr.load(path)
    node = next((item for item in roots if sexpr.head(item) in ("footprint", "module")), None)
    if node is None:
        raise LibraryProblem(f"{path} is not a footprint file")
    name = sexpr.atom(node, 1) or path.stem
    pads: list[Pad] = []
    for pad_node in sexpr.children(node, "pad"):
        pads.append(Pad(number=sexpr.atom(pad_node, 1), kind=sexpr.atom(pad_node, 2)))
    model_node = sexpr.find(node, "model")
    model = sexpr.atom(model_node, 1) if model_node is not None else ""
    return FootprintInfo(name=name, path=path, pads=pads, model=model)


class LibrarySet:
    """The configured library tree, with lazily parsed contents."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self._standard_symbols: dict[str, SymbolInfo] | None = None
        self._standard_footprints: dict[str, FootprintInfo] | None = None
        self._part_symbols: dict[str, SymbolInfo] | None = None
        self._footprints: dict[Path, FootprintInfo] = {}

    # -- locations -----------------------------------------------------

    @property
    def standard_symbol_file(self) -> Path:
        return self.config.standard_symbol.path

    @property
    def part_symbol_folder(self) -> Path:
        return self.config.part_symbols.path

    @property
    def standard_footprint_folder(self) -> Path:
        return self.config.standard_footprints.path

    @property
    def part_footprint_folder(self) -> Path:
        return self.config.part_footprints.path

    def part_symbol_path(self, name: str) -> Path:
        return self.part_symbol_folder / f"{name}{self.config.symbol_suffix}"

    def part_symbol_nickname(self, name: str) -> str:
        """Nickname a downloaded symbol is reached through.

        Usually one shared nickname for the whole folder (``Symbol``). A tree that
        registers each ``.kicad_sym`` as its own library sets the template to
        ``"{name}"``, and the nickname becomes the part's own name.
        """
        return str(self.config.part_symbols.nickname).replace("{name}", name)

    def part_footprint_nickname(self, name: str) -> str:
        return str(self.config.part_footprints.nickname).replace("{name}", name)

    def part_footprint_path(self, name: str) -> Path:
        return self.part_footprint_folder / f"{name}{self.config.footprint_suffix}"

    def step_file(self, name: str) -> Path | None:
        for suffix in self.config.step_suffixes:
            candidate = self.config.step_folder / f"{name}{suffix}"
            if candidate.is_file():
                return candidate
        # case-insensitive fallback: some vendors ship ``.STEP``
        folder = self.config.step_folder
        if folder.is_dir():
            lowered = {item.name.lower(): item for item in folder.iterdir() if item.is_file()}
            for suffix in self.config.step_suffixes:
                hit = lowered.get(f"{name}{suffix}".lower())
                if hit is not None:
                    return hit
        return None

    # -- standard library ----------------------------------------------

    def standard_symbols(self) -> dict[str, SymbolInfo]:
        if self._standard_symbols is None:
            path = self.standard_symbol_file
            self._standard_symbols = read_symbol_file(path) if path.is_file() else {}
        return self._standard_symbols

    def standard_footprints(self) -> dict[str, FootprintInfo]:
        if self._standard_footprints is None:
            folder = self.standard_footprint_folder
            found: dict[str, FootprintInfo] = {}
            if folder.is_dir():
                for item in sorted(folder.iterdir()):
                    if item.is_file() and item.suffix == ".kicad_mod":
                        found[item.stem] = read_footprint_file(item)
            self._standard_footprints = found
        return self._standard_footprints

    # -- per-part library ----------------------------------------------

    def part_symbols(self) -> dict[str, SymbolInfo]:
        """Downloaded symbols on disk, keyed by file stem (= symbol name)."""
        if self._part_symbols is None:
            folder = self.part_symbol_folder
            found: dict[str, SymbolInfo] = {}
            if folder.is_dir():
                for item in sorted(folder.iterdir()):
                    if not item.is_file() or item.suffix != self.config.symbol_suffix:
                        continue
                    try:
                        symbols = read_symbol_file(item)
                    except (LibraryProblem, sexpr.SexprError):
                        continue
                    info = symbols.get(item.stem)
                    if info is None and symbols:
                        # the file is named differently from the symbol in it;
                        # keep it so verify can report the mismatch
                        info = next(iter(symbols.values()))
                    if info is not None:
                        found[item.stem] = info
            self._part_symbols = found
        return self._part_symbols

    def part_symbol(self, name: str) -> SymbolInfo | None:
        path = self.part_symbol_path(name)
        if not path.is_file():
            return None
        try:
            symbols = read_symbol_file(path)
        except (LibraryProblem, sexpr.SexprError):
            return None
        return symbols.get(name) or (next(iter(symbols.values())) if symbols else None)

    def footprint(self, path: Path) -> FootprintInfo | None:
        cached = self._footprints.get(path)
        if cached is not None:
            return cached
        if not path.is_file():
            return None
        info = read_footprint_file(path)
        self._footprints[path] = info
        return info

    def part_footprint(self, name: str) -> FootprintInfo | None:
        return self.footprint(self.part_footprint_path(name))

    def standard_footprint(self, name: str) -> FootprintInfo | None:
        return self.standard_footprints().get(name)

    # -- reference resolution ------------------------------------------

    def resolve_symbol(self, reference: str) -> tuple[SymbolInfo | None, str]:
        """Resolve ``Nickname:Name`` to a symbol; returns (info, problem)."""
        nickname, _, name = reference.partition(":")
        if not _:
            return None, f"{reference!r} is not 'library:symbol'"
        if nickname == self.config.standard_symbol.nickname:
            info = self.standard_symbols().get(name)
            if info is None:
                return None, f"no symbol {name!r} in {self.standard_symbol_file}"
            return info, ""
        if nickname == self.part_symbol_nickname(name):
            if not self.part_symbol_path(name).is_file():
                return None, f"missing {self.part_symbol_path(name)}"
            info = self.part_symbol(name)
            if info is None:
                return None, f"{self.part_symbol_path(name)} could not be parsed"
            if info.name != name:
                return None, (
                    f"{self.part_symbol_path(name)} declares symbol {info.name!r}, "
                    f"not {name!r} — KiCad looks symbols up by their declared name"
                )
            return info, ""
        known = ", ".join(
            sorted({self.config.standard_symbol.nickname, self.part_symbol_nickname(name)})
        )
        return None, f"unknown symbol nickname {nickname!r} (configured: {known})"

    def resolve_footprint(self, reference: str) -> tuple[FootprintInfo | None, str]:
        nickname, _, name = reference.partition(":")
        if not _:
            return None, f"{reference!r} is not 'library:footprint'"
        if nickname == self.config.standard_footprints.nickname:
            info = self.standard_footprint(name)
            if info is None:
                return None, f"no footprint {name!r} in {self.standard_footprint_folder}"
            return info, ""
        if nickname == self.part_footprint_nickname(name):
            info = self.part_footprint(name)
            if info is None:
                return None, f"missing {self.part_footprint_path(name)}"
            return info, ""
        known = ", ".join(
            sorted(
                {
                    self.config.standard_footprints.nickname,
                    self.part_footprint_nickname(name),
                }
            )
        )
        return None, f"unknown footprint nickname {nickname!r} (configured: {known})"

    # -- tree overview -------------------------------------------------

    def layout_report(self) -> list[tuple[str, str, str]]:
        """(nickname, kind, status) rows describing the configured tree."""
        standard = self.config.standard_symbol
        parts = self.config.part_symbols
        std_fp = self.config.standard_footprints
        part_fp = self.config.part_footprints
        rows = [
            ("symbols/standard", f"{standard.nickname}:…", _state(standard)),
            ("symbols/parts", f"{parts.nickname}:…", _state(parts)),
            ("footprints/standard", f"{std_fp.nickname}:…", _state(std_fp)),
            ("footprints/parts", f"{part_fp.nickname}:…", _state(part_fp)),
            ("models", str(self.config.step_folder), _state_dir(self.config.step_folder)),
        ]
        if self.standard_symbol_file.is_file():
            rows.append(
                (
                    "standard symbol count",
                    str(len(self.standard_symbols())),
                    "ok",
                )
            )
        if self.standard_footprint_folder.is_dir():
            rows.append(
                (
                    "standard footprint count",
                    str(len(self.standard_footprints())),
                    "ok",
                )
            )
        if self.part_symbol_folder.is_dir():
            rows.append(
                ("downloaded symbol count", str(len(self.part_symbols())), "ok")
            )
        if self.part_footprint_folder.is_dir():
            count = sum(
                1
                for item in self.part_footprint_folder.iterdir()
                if item.is_file() and item.suffix == self.config.footprint_suffix
            )
            rows.append(("downloaded footprint count", str(count), "ok"))
        return rows


def _state(location: Location) -> str:
    if location.path.exists():
        return f"ok ({location.path})"
    return f"MISSING ({location.path})"


def _state_dir(path: Path) -> str:
    return f"ok ({path})" if path.is_dir() else f"MISSING ({path})"


def assert_writable(config: Config, path: Path) -> None:
    """Refuse to write into the read-only standard libraries."""
    resolved = path.resolve()
    standard_symbol = config.standard_symbol.path.resolve()
    standard_footprints = config.standard_footprints.path.resolve()
    if resolved == standard_symbol:
        raise LibraryProblem(
            f"{standard_symbol} is the standard symbol library and is read-only for this skill"
        )
    if standard_footprints in resolved.parents or resolved == standard_footprints:
        raise LibraryProblem(
            f"{standard_footprints} holds the standard footprints and is read-only for this skill"
        )
