"""Assemble a bundle for one part: artefacts on disk plus a manifest.

One part number in, a folder of KiCad material out. Every step records what it did
in the manifest, including what it could **not** produce — a part with no published
symbol is a normal outcome, not an error.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from easyeda import client as http
from easyeda.document import document, head_of, parse_records
from easyeda.model3d import Model3D, parse_model

from libs import naming
from libs.cache import ResponseCache

PARTS = ("symbol", "footprint", "model", "datasheet")
DEFAULT_MODEL_PREFIX = "${KIPRJMOD}/../kicad_lib/Step"
MAX_PDF_BYTES = 40 * 1024 * 1024


@dataclass
class PartIdentity:
    """What the store says about the part, independent of KiCad."""

    part: str
    title: str
    mpn: str
    manufacturer: str
    package: str
    szlcsc_id: object
    description: str = ""
    product_url: str = ""

    @property
    def bundle(self) -> str:
        return naming.bundle_name(self.part, self.mpn)

    @property
    def symbol_name(self) -> str:
        return naming.symbol_name(self.mpn, self.part)

    @property
    def footprint_name(self) -> str:
        """Same identifier as the ``.pretty`` folder and the ``.kicad_mod`` file."""
        return naming.footprint_name(self.part, self.mpn)


@dataclass
class Artefact:
    kind: str
    path: str
    bytes: int
    sha256: str


@dataclass
class Manifest:
    part: PartIdentity
    output: str
    model_prefix: str
    artefacts: list[Artefact] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sources: dict[str, str] = field(default_factory=dict)
    model_reference: str = ""
    model_written: str = ""

    def as_dict(self) -> dict:
        return {
            "part": {
                "lcsc": self.part.part,
                "title": self.part.title,
                "mpn": self.part.mpn,
                "manufacturer": self.part.manufacturer,
                "package": self.part.package,
                "description": self.part.description,
                "product_url": self.part.product_url,
            },
            "output": self.output,
            "artefacts": [vars(item) for item in self.artefacts],
            "model": {
                "reference": self.model_reference,
                "written": self.model_written,
                "prefix": self.model_prefix,
            },
            "sources": self.sources,
            "warnings": self.warnings,
        }


def identity_of(part: str, result: dict) -> PartIdentity:
    symbol_head = head_of(result.get("dataStr"))
    params = document(symbol_head.get("c_para"))
    package_detail = result.get("packageDetail") or {}
    package_head = head_of(package_detail.get("dataStr"))
    package_params = document(package_head.get("c_para"))
    szlcsc = result.get("szlcsc") or result.get("lcsc") or {}
    mpn = str(params.get("Manufacturer Part") or result.get("title") or part).strip()
    return PartIdentity(
        part=part.upper(),
        title=str(result.get("title") or "").strip(),
        mpn=mpn or part.upper(),
        manufacturer=str(params.get("Manufacturer") or "").strip(),
        package=str(package_detail.get("title")
                    or package_params.get("package")
                    or params.get("package") or "").strip(),
        szlcsc_id=szlcsc.get("id") if isinstance(szlcsc, dict) else None,
        description=str(result.get("description") or "").strip(),
        product_url=str((result.get("lcsc") or {}).get("url") or "")
        if isinstance(result.get("lcsc"), dict) else "",
    )


def _write(path: Path, payload: bytes) -> Artefact:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return Artefact(kind=path.suffix.lstrip("."), path=str(path), bytes=len(payload),
                    sha256=hashlib.sha256(payload).hexdigest())


class Fetcher:
    """Fetch one part's artefacts into an output folder."""

    def __init__(self, client: http.HttpClient, cache: ResponseCache, *,
                 model_prefix: str = DEFAULT_MODEL_PREFIX) -> None:
        self.client = client
        self.cache = cache
        self.model_prefix = model_prefix

    def _cached(self, url: str, *, max_bytes: int | None = None) -> bytes:
        hit = self.cache.get(url)
        if hit is not None:
            return hit
        response = self.client.get(url, max_bytes=max_bytes)
        self.cache.put(url, response.body)
        return response.body

    def product(self, part: str) -> dict:
        return http.fetch_product(self.client, part)

    def fetch(self, part: str, out: Path, parts: tuple[str, ...]) -> Manifest:
        part = part.strip().upper()
        result = self.product(part)
        identity = identity_of(part, result)
        manifest = Manifest(part=identity, output=str(out), model_prefix=self.model_prefix)
        manifest.sources["component"] = http.product_url(part)

        footprint_records = parse_records((result.get("packageDetail") or {}).get("dataStr"))
        model = parse_model(footprint_records)

        # The symbol records the datasheet URL, so it is resolved first when wanted.
        datasheet_url = ""
        if "datasheet" in parts:
            datasheet_url = self._datasheet_url(manifest, identity)

        if "symbol" in parts:
            self._symbol(manifest, result, identity, out, datasheet_url)
        if "footprint" in parts:
            self._footprint(manifest, result, identity, out, model)
        if "model" in parts:
            self._model(manifest, identity, out, model)
        if "datasheet" in parts:
            self._datasheet(manifest, identity, out, datasheet_url)

        manifest_path = out / "manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        existing = _load_manifest(manifest_path)
        existing[identity.part] = manifest.as_dict()
        manifest_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")
        return manifest

    # -- artefacts ------------------------------------------------------

    def _symbol(self, manifest: Manifest, result: dict, identity: PartIdentity,
                out: Path, datasheet: str = "") -> None:
        from kicad.symbol_writer import write_symbol_library

        footprint_lib = f"{identity.bundle}:{identity.footprint_name}"
        text, warnings = write_symbol_library(result, identity, datasheet=datasheet,
                                              footprint_lib=footprint_lib)
        if text is not None:
            from kicad.validate import check_symbol_library

            try:
                check_symbol_library(text, expected_symbol=identity.symbol_name)
            except Exception as exc:
                manifest.warnings.append(f"symbol failed validation: {exc}")
                return
        manifest.warnings.extend(warnings)
        if text is None:
            manifest.warnings.append("no symbol published for this part")
            return
        path = out / "symbols" / f"{identity.bundle}.kicad_sym"
        manifest.artefacts.append(_write(path, text.encode("utf-8")))

    def _footprint(self, manifest: Manifest, result: dict, identity: PartIdentity,
                   out: Path, model: Model3D | None) -> None:
        from kicad.footprint_writer import write_footprint
        from kicad.validate import check_footprint

        reference = ""
        if model is not None:
            reference = f"{self.model_prefix}/{identity.bundle}.step"
            manifest.model_reference = reference
        text, warnings = write_footprint(result, identity, reference)
        if text is not None:
            try:
                check_footprint(text, expected_name=identity.footprint_name)
            except Exception as exc:
                manifest.warnings.append(f"footprint failed validation: {exc}")
                return
        manifest.warnings.extend(warnings)
        if text is None:
            manifest.warnings.append("no footprint published for this part")
            return
        path = out / "footprints" / f"{identity.bundle}.pretty" / f"{identity.footprint_name}.kicad_mod"
        manifest.artefacts.append(_write(path, text.encode("utf-8")))

    def _model(self, manifest: Manifest, identity: PartIdentity, out: Path,
               model: Model3D | None) -> None:
        if model is None:
            manifest.warnings.append("no 3D model published for this part")
            return
        url = http.step_url(model.uuid)
        manifest.sources["model"] = url
        payload = self._cached(url, max_bytes=http.MAX_MODEL_BYTES)
        if not payload.startswith(b"ISO-10303-21"):
            manifest.warnings.append("the model endpoint did not return a STEP file")
            return
        path = out / "Step" / f"{identity.bundle}.step"
        manifest.artefacts.append(_write(path, payload))
        manifest.model_written = str(path)

    def _datasheet_url(self, manifest: Manifest, identity: PartIdentity) -> str:
        """Resolve (and record) the datasheet URL without downloading the PDF."""
        try:
            url = http.fetch_datasheet_url(self.client, identity.part)
        except http.LibsError as exc:
            manifest.warnings.append(f"datasheet: {exc}")
            return ""
        manifest.sources["datasheet"] = url
        return url

    def _datasheet(self, manifest: Manifest, identity: PartIdentity, out: Path,
                   url: str) -> None:
        if not url:
            return
        payload = self._cached(url, max_bytes=MAX_PDF_BYTES)
        if not payload.startswith(b"%PDF"):
            manifest.warnings.append("the datasheet link did not return a PDF")
            return
        path = out / "datasheets" / f"{naming.sanitise(identity.mpn)}.pdf"
        manifest.artefacts.append(_write(path, payload))


def _load_manifest(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}
