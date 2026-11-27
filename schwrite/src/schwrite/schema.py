"""Structured schema for a schematic part and for the page that holds it.

The point of this module: a part's field set is **computed and checked as data** before a
single character is written, so a new part cannot silently lose a field or emit one in the
wrong shape. Everything the emitter needs is a `Property`, and `PropertyTable.validate()`
refuses a table that is missing a database column, duplicates a name, breaks the five-field
prefix, or makes anything but Reference/Value visible.

What KiCad actually writes (measured against pages the user refreshed from the library):

* the five standard fields first, in order;
* then every column the `.kicad_dbl` declares, in declaration order;
* then whatever else the library symbol carries, at the library's own position;
* finally the derived `ki_*` hints;
* Reference and Value visible, everything else `(hide yes)`.

`PropertyTable.build()` produces exactly that list; `validate()` proves it is complete.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

from .config import GRID

Point = tuple[float, float]

#: The five fields KiCad always has, in the order it writes them.
STANDARD_FIELDS: tuple[str, ...] = (
    "Reference",
    "Value",
    "Footprint",
    "Datasheet",
    "Description",
)

#: The only two fields a placed part shows (user rule, 2026-11-26).
VISIBLE_FIELDS: tuple[str, ...] = ("Reference", "Value")

#: Properties KiCad derives rather than copies from the row.
DERIVED_FIELDS: tuple[str, ...] = ("ki_fp_filters", "ki_keywords")


class SchemaError(ValueError):
    """A part or page would be written with a field missing, duplicated or malformed."""


@dataclass(frozen=True)
class Property:
    """One `(property ...)` node, with every flag it can carry."""

    name: str
    value: str
    at: Point = (0.0, 0.0)
    hide: bool = True
    show_name: bool = False
    do_not_autoplace: bool = False
    justify: str | None = None
    size: float = 1.27
    angle: int = 0

    def render(self, level: int) -> list[str]:
        """The node as text, at `level` tabs — the shape this KiCad writes, flag order and all."""
        tabs = "\t" * level
        x, y = self.at
        lines = [
            f'{tabs}(property "{self.name}" "{self.value}"',
            f"{tabs}\t(at {x:g} {y:g} {self.angle})",
            f"{tabs}\t(show_name {'yes' if self.show_name else 'no'})",
            f"{tabs}\t(do_not_autoplace {'yes' if self.do_not_autoplace else 'no'})",
        ]
        if self.hide:
            lines.append(f"{tabs}\t(hide yes)")
        lines += [
            f"{tabs}\t(effects",
            f"{tabs}\t\t(font",
            f"{tabs}\t\t\t(size {self.size:g} {self.size:g})",
            f"{tabs}\t\t)",
        ]
        if self.justify:
            lines.append(f"{tabs}\t\t(justify {self.justify})")
        lines += [f"{tabs}\t)", f"{tabs})"]
        return lines


@dataclass(frozen=True)
class PropertyTable:
    """A part's complete field set, in the order KiCad writes it."""

    properties: tuple[Property, ...] = ()

    # -- construction ------------------------------------------------------
    @classmethod
    def build(
        cls,
        *,
        part,
        library_properties: Sequence[tuple[str, str, Point, str | None]] = (),
        standard_values: Mapping[str, str] | None = None,
        standard_positions: Mapping[str, Point] | None = None,
        field_positions: Mapping[str, Point] | None = None,
        use_library_positions: bool = True,
        default_at: Point = (0.0, 0.0),
        include_derived: bool = True,
    ) -> "PropertyTable":
        """Assemble the table: standard five, database columns, library extras, `ki_*`.

        `library_properties` is `(name, value, at, justify)` for every property the library
        symbol declares; `standard_values` overrides the five with row/derived values;
        `field_positions` relocates individual database columns (the page moves Reference and
        Value next to the graphic, the cache keeps the library's positions).
        """
        standard_values = dict(standard_values or {})
        standard_positions = dict(standard_positions or {})
        field_positions = dict(field_positions or {})
        library_at = {name: (at, justify) for name, _, at, justify in library_properties}
        library_value = {name: value for name, value, _, _ in library_properties}

        items: list[Property] = []
        seen: set[str] = set()

        for name in STANDARD_FIELDS:
            at = field_positions.get(name) or standard_positions.get(name) or default_at
            items.append(
                Property(
                    name=name,
                    value=standard_values.get(name, library_value.get(name, "")),
                    at=at,
                    hide=name not in VISIBLE_FIELDS,
                    justify=library_at.get(name, (None, None))[1],
                )
            )
            seen.add(name)

        # KiCad's order, measured against a page it re-saved: the library's own properties
        # come straight after the five standard fields, and the database-only columns
        # follow. A name both sides declare keeps the library's slot and takes the database
        # value.
        for name, value, at, justify in library_properties:
            if name in seen:
                continue
            if name == "ki_fp_filters" and part.footprint:
                value = part.footprint
            elif name in (part.fields or {}):
                value = part.fields[name]
            place = field_positions.get(name, at if use_library_positions else default_at)
            items.append(Property(name=name, value=value, at=place, hide=True, justify=justify))
            seen.add(name)

        for name, value in (part.fields or {}).items():
            if name in seen:
                continue
            at = library_at[name][0] if use_library_positions and name in library_at \
                else default_at
            items.append(
                Property(name=name, value=value, at=field_positions.get(name, at), hide=True)
            )
            seen.add(name)

        # `ki_fp_filters` comes last: KiCad writes the library's `ki_*` hints first, then
        # points this one at the row's footprint.
        if include_derived and part.footprint and "ki_fp_filters" not in seen:
            items.append(Property(name="ki_fp_filters", value=part.footprint, hide=True))
            seen.add("ki_fp_filters")

        return cls(tuple(items))

    # -- inspection --------------------------------------------------------
    def names(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.properties)

    def get(self, name: str) -> Property | None:
        return next((item for item in self.properties if item.name == name), None)

    def render(self, level: int) -> str:
        lines: list[str] = []
        for item in self.properties:
            lines.extend(item.render(level))
        return "\n".join(lines)

    # -- the guarantee -----------------------------------------------------
    def validate(self, part, *, require_grid: bool = False, include_derived: bool = True) -> None:
        """Prove the table covers everything the part and its library demand.

        Raises `SchemaError` naming the missing or misplaced field, so a new part cannot be
        written with a hole in it.
        """
        names = self.names()

        for expected in STANDARD_FIELDS:
            if expected not in names:
                raise SchemaError(f"{part.ref}: the standard field {expected!r} is missing")

        prefix = names[: len(STANDARD_FIELDS)]
        if prefix != STANDARD_FIELDS:
            raise SchemaError(
                f"{part.ref}: the five standard fields must come first and in order, got {prefix}"
            )

        duplicates = [name for name in set(names) if names.count(name) > 1]
        if duplicates:
            raise SchemaError(f"{part.ref}: duplicated field(s) {sorted(duplicates)}")

        required = set(STANDARD_FIELDS) | set(part.fields or {})
        if include_derived:
            # the cache entry carries the library's `ki_*` hints; a placed instance does not
            required |= set(part.library_properties or {})
        missing = sorted(required - set(names))
        if missing:
            raise SchemaError(f"{part.ref}: field(s) {missing} missing from the table")

        for item in self.properties:
            if not item.hide and item.name not in VISIBLE_FIELDS:
                raise SchemaError(
                    f"{part.ref}: {item.name!r} would be visible; only {VISIBLE_FIELDS} may be"
                )

        if require_grid:
            # Only what *we* place must be on the grid. The cache entry keeps the library's
            # own positions, and an EasyEDA-sourced library puts them at values like
            # (0.254, 1.778) — KiCad copies those verbatim, so demanding the grid there
            # would refuse a correct page.
            for item in self.properties:
                for value in item.at:
                    steps = value / GRID
                    if abs(steps - round(steps)) > 1e-6:
                        raise SchemaError(
                            f"{part.ref}: {item.name!r} sits off the 50 mil grid at {item.at}"
                        )


@dataclass(frozen=True)
class PageSpec:
    """The node order a page must have, and the invariants that make it loadable."""

    #: order KiCad writes top-level nodes in (§3 of docs/format-notes.md)
    NODE_ORDER: tuple[str, ...] = field(
        default=(
            "version",
            "generator",
            "generator_version",
            "uuid",
            "paper",
            "lib_symbols",
            "symbol",
            "wire",
            "global_label",
            "sheet_instances",
        )
    )

    @staticmethod
    def check(parts: Iterable, cache_links: Sequence[str]) -> None:
        """Every placed part must have a `lib_symbols` entry, and nothing may be dangling."""
        cache = set(cache_links)
        for part in parts:
            link = part.link_id or part.symbol_id
            if link not in cache:
                raise SchemaError(f"{part.ref}: no lib_symbols entry for {link!r}")
        missing = sorted({p.link_id for p in parts if p.link_id} - cache)
        if missing:
            raise SchemaError(f"lib_symbols is missing {missing}")
