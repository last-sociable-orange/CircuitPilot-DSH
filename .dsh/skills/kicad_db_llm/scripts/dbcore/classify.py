"""What kind of part is this, and which standard symbol could represent it?

The classification is deliberately conservative and evidence-based: every answer
carries the text it was derived from, so a wrong call is visible in the report
instead of hiding behind a plausible-looking library name. Nothing here
fuzzy-matches a symbol name; :mod:`dbcore.mapping` only ever uses the candidate
names produced here, and then proves each candidate against the actual files.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .parts import Part


@dataclass(frozen=True)
class PartClass:
    code: str
    product_type: str
    label: str
    #: passive parts may use standard symbols/footprints (rule 1); actives may not
    passive: bool


CLASSES: dict[str, PartClass] = {
    "RESISTOR": PartClass("RESISTOR", "R", "resistor", True),
    "RESISTOR_NETWORK": PartClass("RESISTOR_NETWORK", "RN", "resistor network", False),
    "CAPACITOR": PartClass("CAPACITOR", "C", "capacitor", True),
    "CAPACITOR_POL": PartClass("CAPACITOR_POL", "C", "polarised capacitor", True),
    "CAPACITOR_NETWORK": PartClass("CAPACITOR_NETWORK", "C", "capacitor network", False),
    "INDUCTOR": PartClass("INDUCTOR", "L", "inductor", True),
    "FERRITE_BEAD": PartClass("FERRITE_BEAD", "FB", "ferrite bead", True),
    "FUSE": PartClass("FUSE", "F", "fuse", True),
    "FUSE_PTC": PartClass("FUSE_PTC", "F", "resettable fuse", True),
    "THERMISTOR_NTC": PartClass("THERMISTOR_NTC", "RT", "NTC thermistor", True),
    "CRYSTAL": PartClass("CRYSTAL", "XTAL", "crystal", True),
    "OSCILLATOR": PartClass("OSCILLATOR", "XTAL", "oscillator", False),
    "DIODE": PartClass("DIODE", "D", "diode", False),
    "DIODE_SCHOTTKY": PartClass("DIODE_SCHOTTKY", "D", "schottky diode", False),
    "DIODE_ZENER": PartClass("DIODE_ZENER", "D", "zener diode", False),
    "DIODE_TVS": PartClass("DIODE_TVS", "D", "TVS diode", False),
    "DIODE_TVS_BIDIR": PartClass("DIODE_TVS_BIDIR", "D", "bidirectional TVS diode", False),
    "DIODE_LED": PartClass("DIODE_LED", "D", "LED", False),
    "TRANSISTOR_NMOS": PartClass("TRANSISTOR_NMOS", "Q", "N-channel MOSFET", False),
    "TRANSISTOR_PMOS": PartClass("TRANSISTOR_PMOS", "Q", "P-channel MOSFET", False),
    "TRANSISTOR_NPN": PartClass("TRANSISTOR_NPN", "Q", "NPN transistor", False),
    "TRANSISTOR_PNP": PartClass("TRANSISTOR_PNP", "Q", "PNP transistor", False),
    "TRANSISTOR": PartClass("TRANSISTOR", "Q", "transistor", False),
    "IC": PartClass("IC", "IC", "integrated circuit", False),
    "CONNECTOR": PartClass("CONNECTOR", "CON", "connector", False),
    "SWITCH": PartClass("SWITCH", "SW", "switch", False),
    "RELAY": PartClass("RELAY", "RLY", "relay", False),
    "TESTPOINT": PartClass("TESTPOINT", "TP", "test point", True),
    "MOUNTING": PartClass("MOUNTING", "M", "mechanical part", True),
    "OTHER": PartClass("OTHER", "X", "unclassified", False),
}

#: Candidate standard symbols per class, most specific first. Empty = the class
#: has no standard representation, so the downloaded files are used (rule 2).
STANDARD_SYMBOLS: dict[str, list[str]] = {
    "RESISTOR": ["R"],
    "CAPACITOR": ["C"],
    "CAPACITOR_POL": ["C_POL_P1N2"],
    "INDUCTOR": ["L"],
    "FERRITE_BEAD": ["FB"],
    "FUSE": ["FUSE"],
    "FUSE_PTC": ["FUSE_PTC"],
    "THERMISTOR_NTC": ["Thermistor_NTC"],
    "CRYSTAL": ["XTAL", "XTAL13_GND24", "XTAL13_GND24_Small"],
    "DIODE_SCHOTTKY": ["D_SCHOTTKY_A1C2", "D_SCHOTTKY_A2C1"],
    "DIODE_ZENER": ["D_Zener_A1C2", "D_Zener_A2C1"],
    "DIODE_TVS": ["D_TVS_A1C2", "D_TVS_A2C1"],
    "DIODE_TVS_BIDIR": ["D_TVS_BIDIR"],
    "TRANSISTOR_NMOS": ["Q_NMOS_SOT23"],
    "TRANSISTOR_PMOS": ["Q_PMOS_SOT23"],
    "TRANSISTOR_NPN": ["Q_NPN_SOT23"],
    "TRANSISTOR_PNP": ["Q_PNP_SOT23"],
    "TESTPOINT": ["TP"],
    "MOUNTING": ["MountingHole"],
}

#: Standard chip footprints, as ``(prefix, sizes)``. Only the two families whose
#: land pattern is genuinely package-defined: a 0603 MLCC and a 0603 resistor share
#: the geometry KiCad's standard library encodes. Tantalum/electrolytic capacitors
#: and every other class keep the downloaded footprint, because their land patterns
#: differ from an MLCC of the same nominal size.
CHIP_FOOTPRINTS: dict[str, tuple[str, tuple[str, ...]]] = {
    "RESISTOR": ("R_", ("0201", "0402", "0603", "0805", "1206", "1210", "2512")),
    "CAPACITOR": ("C_", ("0201", "0402", "0603", "0805", "1206", "1210", "2220")),
}

_TRANSISTOR_FOOTPRINTS: dict[str, list[str]] = {
    # Kept for reference and for an explicit BOM override; never chosen
    # automatically, because rule 2 gives actives the downloaded footprint.
    "TRANSISTOR_NMOS": ["SOT23"],
    "TRANSISTOR_PMOS": ["SOT23"],
    "TRANSISTOR_NPN": ["SOT23"],
    "TRANSISTOR_PNP": ["SOT23"],
}

_CHIP_SIZE = re.compile(r"(?<!\d)(01005|0201|0402|0603|0805|1206|1210|1812|2010|2220|2512)(?!\d)")
_METRIC_TO_IMPERIAL = {
    "0402": "01005",
    "0603": "0201",
    "1005": "0402",
    "1608": "0603",
    "2012": "0805",
    "3216": "1206",
    "3225": "1210",
    "4532": "1812",
    "5025": "2010",
    "5750": "2220",
    "6332": "2512",
}


@dataclass
class Classification:
    cls: PartClass
    evidence: list[str] = field(default_factory=list)
    chip_size: str = ""
    package_family: str = ""

    @property
    def code(self) -> str:
        return self.cls.code

    @property
    def product_type(self) -> str:
        return self.cls.product_type

    @property
    def label(self) -> str:
        return self.cls.label

    @property
    def passive(self) -> bool:
        return self.cls.passive


def chip_size_of(package: str) -> str:
    """Imperial chip size for a package string such as ``0603`` or ``1608 Metric``."""
    text = package.strip()
    if not text:
        return ""
    match = _CHIP_SIZE.search(text)
    if match:
        return match.group(1)
    for metric, imperial in _METRIC_TO_IMPERIAL.items():
        if metric in text and "metric" in text.lower():
            return imperial
    return ""


def package_family_of(package: str) -> str:
    """Coarse package family, e.g. ``sot23``, ``sot23-5``, ``sod323``, ``lqfp48``."""
    text = package.strip().lower()
    if not text:
        return ""
    text = text.replace(" ", "")
    text = re.sub(r"\(.*?\)", "", text)
    aliases = (
        ("sot-23-5", "sot23-5"),
        ("sot23-5", "sot23-5"),
        ("sot-23-6", "sot23-6"),
        ("sot23-6", "sot23-6"),
        ("sot-23", "sot23"),
        ("sot23", "sot23"),
        ("sot-323", "sot323"),
        ("sot323", "sot323"),
        ("sot-523", "sot523"),
        ("sot523", "sot523"),
        ("sod-323", "sod323"),
        ("sod323", "sod323"),
        ("sod-523", "sod523"),
        ("sod523", "sod523"),
        ("sod-123", "sod123"),
        ("sod123", "sod123"),
    )
    for needle, family in aliases:
        if needle in text:
            return family
    for family in ("sma", "smb", "smc", "smf", "dpak", "d2pak", "to-220", "to-252"):
        if family in text:
            return family.replace("-", "")
    match = re.search(r"(lqfp|tqfp|qfn|dfn|msop|tssop|ssop|sop|soic|bga|lga)[-_]?(\d+)", text)
    if match:
        return f"{match.group(1)}{match.group(2)}"
    return ""


def classify(part: Part) -> Classification:
    """Decide the class of *part*, recording the text each decision used."""
    text = part.textual()
    params = {item.get("name", "").lower(): item.get("value", "") for item in part.parameters}
    package = part.package
    chip = chip_size_of(package)
    family = package_family_of(package)

    def result(code: str, evidence: str) -> Classification:
        return Classification(
            cls=CLASSES[code], evidence=[evidence], chip_size=chip, package_family=family
        )

    # -- mechanical and test accessories ------------------------------
    if "mounting hole" in text or "mountinghole" in text:
        return result("MOUNTING", "description or category mentions a mounting hole")
    if "test point" in text or "测试点" in text:
        return result("TESTPOINT", "description or category mentions a test point")

    # -- magnetics ------------------------------------------------------
    if "ferrite" in text or "磁珠" in text:
        return result("FERRITE_BEAD", "ferrite bead in category/description")
    if "common mode" in text and ("choke" in text or "filter" in text):
        return result("INDUCTOR", "common-mode choke, represented by the standard inductor")
    if "inductor" in text or "电感" in text or re.search(r"\b(fixed )?ind\b", text):
        return result("INDUCTOR", "inductor in category/description")

    # -- resistors and thermistors -------------------------------------
    if "thermistor" in text or "ntc" in text or "热敏" in text:
        return result("THERMISTOR_NTC", "NTC thermistor in category/description")
    if ("resistor" in text or "电阻" in text) and (
        "network" in text or "array" in text or "排阻" in text
    ):
        return result("RESISTOR_NETWORK", "resistor network/array: no standard single-symbol equivalent")
    if "resistor" in text or "电阻" in text or "res " in f" {text} ":
        return result("RESISTOR", "resistor in category/description")
    if "resistance" in params:
        return result("RESISTOR", "parameters carry a Resistance value")

    # -- capacitors -----------------------------------------------------
    if "capacitor" in text or "电容" in text:
        if "network" in text or "array" in text or "排容" in text:
            return result("CAPACITOR_NETWORK", "capacitor network: no standard single-symbol equivalent")
        polar_markers = (
            "electrolytic",
            "tantalum",
            "aluminum",
            "aluminium",
            "polymer",
            "polar",
            "电解",
            "钽",
        )
        if any(marker in text for marker in polar_markers) or re.search(r"\balum\b", text):
            return result("CAPACITOR_POL", "polarised capacitor in category/description")
        return result("CAPACITOR", "capacitor in category/description")

    # -- protection -----------------------------------------------------
    if "ptc" in text and ("resettable" in text or "fuse" in text or "自恢复" in text):
        return result("FUSE_PTC", "resettable PTC fuse")
    if "fuse" in text or "保险丝" in text:
        return result("FUSE", "fuse in category/description")

    # -- timing ---------------------------------------------------------
    if "oscillator" in text or "振荡器" in text:
        return result("OSCILLATOR", "oscillator: active device, uses the downloaded symbol")
    if "crystal" in text or "晶体" in text or "谐振器" in text:
        return result("CRYSTAL", "crystal in category/description")

    # -- diodes ---------------------------------------------------------
    if "tvs" in text or "transient voltage" in text:
        bidirectional = any(
            key in params and str(params[key]).strip() not in ("", "0", "-")
            for key in ("bidirectional channels", "双向")
        )
        if bidirectional:
            return result("DIODE_TVS_BIDIR", "TVS with a bidirectional channel")
        return result("DIODE_TVS", "TVS diode")
    if "led" in text or "发光二极管" in text:
        return result("DIODE_LED", "LED: no standard LED symbol in the library")
    if "zener" in text or "稳压二极管" in text:
        return result("DIODE_ZENER", "zener diode")
    if "schottky" in text or "肖特基" in text:
        return result("DIODE_SCHOTTKY", "schottky diode")
    if "diode" in text or "二极管" in text or "rectifier" in text:
        return result("DIODE", "diode/rectifier: no exact standard symbol")

    # -- transistors ----------------------------------------------------
    if any(word in text for word in ("mosfet", "transistor", "bjt", "igbt", "三极管", "场效应")):
        p_channel = (
            "p-channel" in text
            or "p channel" in text
            or "pmos" in text
            or "p沟道" in text
            or re.search(r"\bp[-_ ]?ch\b", text)
        )
        n_channel = (
            "n-channel" in text
            or "n channel" in text
            or "nmos" in text
            or "n沟道" in text
            or re.search(r"\bn[-_ ]?ch\b", text)
        )
        if p_channel:
            return result("TRANSISTOR_PMOS", "P-channel MOSFET")
        if n_channel:
            return result("TRANSISTOR_NMOS", "N-channel MOSFET")
        if "pnp" in text:
            return result("TRANSISTOR_PNP", "PNP bipolar transistor")
        if "npn" in text:
            return result("TRANSISTOR_NPN", "NPN bipolar transistor")
        return result("TRANSISTOR", "transistor without an identified polarity")

    # -- interconnect and the rest --------------------------------------
    if "connector" in text or "连接器" in text or "header" in text or "socket" in text:
        return result("CONNECTOR", "connector in category/description")
    if "switch" in text or "开关" in text or "button" in text:
        return result("SWITCH", "switch in category/description")
    if "relay" in text or "继电器" in text:
        return result("RELAY", "relay in category/description")
    if any(
        word in text
        for word in (
            "integrated circuit",
            "ic ",
            "集成电路",
            "pmic",
            "mcu",
            "microcontroller",
            "regulator",
            "amplifier",
            "op amp",
            "opamp",
            "logic",
            "adc",
            "dac",
            "driver",
            "sensor",
            "memory",
            "gate",
        )
    ):
        return result("IC", "integrated circuit in category/description")
    return result("OTHER", "no recognisable part class; uses the downloaded symbol")


def standard_symbol_candidates(classification: Classification) -> list[str]:
    return list(STANDARD_SYMBOLS.get(classification.code, ()))


def standard_footprint_candidates(classification: Classification) -> list[str]:
    """Standard footprint names this part could use, most specific first.

    Only the chip resistor/capacitor families: their land patterns are defined by
    the package alone. Everything else keeps the downloaded footprint.
    """
    candidates: list[str] = []
    entry = CHIP_FOOTPRINTS.get(classification.code)
    if entry and classification.chip_size:
        prefix, sizes = entry
        if classification.chip_size in sizes:
            candidates.append(f"{prefix}{classification.chip_size}")
    return candidates


def product_type_for(part: Part, classification: Classification) -> str:
    """The ``<TYPE>_<MPN>`` prefix used for downloaded file names."""
    return classification.product_type
