"""The 3D model reference carried inside an EasyEDA footprint.**

The footprint's ``shape`` list ends with one ``SVGNODE~{json}`` record whose
``attrs`` hold the model UUID, the canvas origin, the rotation and a title. The
geometry itself is a separate download (STEP or OBJ).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from .document import Record, document, number


@dataclass(frozen=True)
class Model3D:
    """A published 3D model, identified by its EasyEDA UUID."""

    uuid: str
    title: str
    origin: tuple[float, float] = (0.0, 0.0)
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0)
    z: float = 0.0

    @property
    def step_filename(self) -> str:
        return f"{self.title or self.uuid}.step"


def _vector(text: str, size: int) -> tuple[float, ...]:
    values = [number(part) for part in (text or "").split(",")]
    while len(values) < size:
        values.append(0.0)
    return tuple(values[:size])


def parse_model(records: list[Record]) -> Model3D | None:
    """Return the model referenced by a footprint, or ``None`` when it has none."""
    for record in records:
        if record.op != "SVGNODE":
            continue
        payload = record.fields[1] if len(record.fields) > 1 else ""
        try:
            raw = json.loads(payload)
        except json.JSONDecodeError:
            continue
        attrs = document(raw.get("attrs") if isinstance(raw, dict) else None)
        if not attrs:
            continue
        uuid = str(attrs.get("uuid") or "").strip()
        if not uuid:
            continue
        origin = _vector(str(attrs.get("c_origin") or ""), 2)
        rotation = _vector(str(attrs.get("c_rotation") or ""), 3)
        return Model3D(
            uuid=uuid,
            title=str(attrs.get("title") or "").strip(),
            origin=(origin[0], origin[1]),
            rotation=(rotation[0], rotation[1], rotation[2]),
            z=number(str(attrs.get("z") or "0")),
        )
    return None
