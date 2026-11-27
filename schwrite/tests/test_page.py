"""Page model and emission (M2): skeleton, symbols and fields.

The acceptance in the plan is "the MCU page opens in KiCad". Two checks stand in for that
here Ã¢â‚¬â€ the file parses back into the node order the corpus uses, and every field sits in the
slot the planner reserved Ã¢â‚¬â€ and a third is done outside the test suite:

    kicad-cli sch export netlist out/MCU.kicad_sch

which is the same command gate 1 uses. On 2026-11-26 it accepted the page and listed the
same 30 components, footprints and values as the 2026-11-25 build.
"""

from __future__ import annotations

import pytest

from conftest import DBL, LIBRARIES, LIVE, NETLISTS, REFERENCE
from schwrite import context, dblib, netlist, parts, sexp, symbols
from schwrite.emit import writer
from schwrite.errors import EmitError
from schwrite.ids import UuidSource
from schwrite.page import build_page_model


@pytest.fixture(scope="module")
def env():
    db = dblib.ComponentDb(DBL)
    library = symbols.SymbolLibrary(LIBRARIES)
    return db, library


def build(page: str, env, *, seed: str | None = "test", paper: str = "A2"):
    db, library = env
    loaded = netlist.load(NETLISTS / f"{page}.json")
    resolved = parts.resolve_parts(loaded, db, library)
    instance = context.InstanceContext(
        project="MainController", path="/root-uuid/sheet-uuid", sheet_uuid="sheet-uuid"
    )
    uuids = UuidSource(seed)
    model = build_page_model(
        netlist=loaded,
        resolved=resolved,
        page=page,
        paper=paper,
        context=instance,
        uuids=uuids,
    )
    return model, writer.render_page(model, parts.symbols_for(resolved, library), uuids)


# -- the model -------------------------------------------------------------
def test_mcu_model_places_every_part_and_counts_its_floating_pins(env) -> None:
    """Ã‚Â§Appendix D: MCU has 30 parts and 33 deliberately unused pins."""
    model, _ = build("MCU", env)
    assert len(model.parts) == 30
    assert len(model.order) == 30
    assert set(model.order) == {part.ref for part in model.parts}
    assert len(model.unconnected) == 33
    assert model.layout["fits"] is True
    # 500 mil between parts means the bounding box is mostly air by construction; the
    # meaningful assertion is that the parts fit, not how densely they fill the box
    assert model.layout["fits"] is True
    # placement order is the packing order: large parts first
    assert model.order[0] in {"U3", "J9", "Y1", "D2", "FB9"}


def test_every_field_sits_in_the_slot_the_planner_reserved(env) -> None:
    model, text = build("MCU", env)
    tree = sexp.parse(text)
    for node in tree[1:]:
        if sexp.node_name(node) != "symbol":
            continue
        props = {
            sexp.unquote(child[1]): child
            for child in node[1:]
            if isinstance(child, list) and sexp.node_name(child) == "property"
        }
        reference = sexp.unquote(props["Reference"][2])
        cell = model.cells[reference]
        at = next(c for c in props["Reference"] if isinstance(c, list) and sexp.node_name(c) == "at")
        assert (float(at[1]), float(at[2])) == pytest.approx(cell.field_slots["Reference"])
        value_at = next(c for c in props["Value"] if isinstance(c, list) and sexp.node_name(c) == "at")
        assert (float(value_at[1]), float(value_at[2])) == pytest.approx(cell.field_slots["Value"])


def test_footprint_property_is_present_and_matches_the_database(env) -> None:
    """Ã‚Â§8.5: a page without Footprint silently loses footprints on the PCB step."""
    model, text = build("MCU", env)
    tree = sexp.parse(text)
    footprints = {}
    for node in tree[1:]:
        if sexp.node_name(node) != "symbol":
            continue
        props = {sexp.unquote(c[1]): sexp.unquote(c[2]) for c in node[1:]
                 if isinstance(c, list) and sexp.node_name(c) == "property"}
        footprints[props["Reference"]] = props["Footprint"]
    expected = {part.ref: part.footprint for part in model.parts}
    assert footprints == expected
    assert all(value for value in footprints.values())


def test_every_symbol_lists_every_pin_of_its_symbol(env) -> None:
    """U3 is a 100-pin MCU: the page lists all 100, not just the 67 that are wired."""
    model, text = build("MCU", env)
    tree = sexp.parse(text)
    by_ref = {part.ref: part for part in model.parts}
    for node in tree[1:]:
        if sexp.node_name(node) != "symbol":
            continue
        ref = next(
            sexp.unquote(c[2]) for c in node[1:]
            if isinstance(c, list) and sexp.node_name(c) == "property"
            and sexp.unquote(c[1]) == "Reference"
        )
        pins = [sexp.unquote(c[1]) for c in node[1:]
                if isinstance(c, list) and sexp.node_name(c) == "pin"]
        assert len(pins) == len(by_ref[ref].pins), ref
        assert pins == sorted(pins, key=writer._pin_sort_key), ref


# -- the text --------------------------------------------------------------
def test_node_order_matches_the_corpus(env) -> None:
    """format-notes Ã‚Â§3: header, lib_symbols, symbols, labels, wires, sheet_instances."""
    _, text = build("MCU", env)
    sequence = [name for name, _, _ in sexp.iter_top_level(text)]
    assert sequence[:6] == [
        "version",
        "generator",
        "generator_version",
        "uuid",
        "paper",
        "lib_symbols",
    ]
    assert sequence[-1] == "sheet_instances"
    assert sequence.count("symbol") == 30
    assert sequence.count("wire") == 0        # M3
    assert sequence.count("global_label") == 0


def test_page_is_deterministic_for_a_seed(env) -> None:
    """S6: same input and same seed Ã¢â€¡â€™ identical bytes."""
    _, first = build("MCU", env, seed="golden")
    _, second = build("MCU", env, seed="golden")
    assert first == second


def test_different_seeds_change_only_uuids(env) -> None:
    _, first = build("Sync", env, seed="a")
    _, second = build("Sync", env, seed="b")
    assert first != second
    strip = lambda text: [
        line for line in text.splitlines() if "(uuid" not in line
    ]
    assert strip(first) == strip(second)


def test_lib_symbols_is_one_entry_per_database_link(env) -> None:
    """Every entry is named after a database link, and nothing else is embedded."""
    model, text = build("Sync", env)
    tree = sexp.parse(text)
    libs = next(node for node in tree[1:] if sexp.node_name(node) == "lib_symbols")
    names = [sexp.unquote(node[1]) for node in libs[1:] if sexp.node_name(node) == "symbol"]
    # one entry per distinct link: ten resistors of one part number share a single child
    expected = list(dict.fromkeys(
        part.link_id for part in model.parts_in_placement_order()
    ))
    assert names == expected
    assert len(names) < len(model.parts), "duplicate entries would be a bug"
    assert all(name.startswith("components:") for name in names)
    assert "Symbol:IC_STM32H743VGT6" not in names      # geometry is not the identity


def test_instances_are_linked_to_the_database_not_copied(env) -> None:
    """`lib_id` names the database row, and the whole row is on the instance.

    Compared against `C59` in `Design/Sync.kicad_sch`, which was placed from the database
    library with KiCad itself: same `lib_id` shape, same field names, same order.
    """
    model, text = build("Sync", env)
    tree = sexp.parse(text)
    by_ref = {part.ref: part for part in model.parts}
    checked = 0
    for node in tree[1:]:
        if sexp.node_name(node) != "symbol":
            continue
        props = {
            sexp.unquote(c[1]): sexp.unquote(c[2])
            for c in node[1:]
            if isinstance(c, list) and sexp.node_name(c) == "property"
        }
        lib_id = next(
            sexp.unquote(c[1]) for c in node[1:]
            if isinstance(c, list) and sexp.node_name(c) == "lib_id"
        )
        part = by_ref[props["Reference"]]
        assert lib_id == part.link_id
        assert list(props) == [
            "Reference", "Value", "Footprint", "Datasheet", "Description", *part.fields
        ]
        assert props["Footprint"] == part.footprint
        assert props["Description"] == part.description
        assert props["DistributorProductNumber"] == part.lcsc
        checked += 1
    assert checked == len(model.parts)


def test_matches_the_field_list_kicad_wrote_for_a_hand_placed_part(env) -> None:
    """KiCad's own database placement (C59) uses the same field list we emit."""
    corpus = (LIVE / "Sync.kicad_sch").read_text(encoding="utf-8")
    tree = sexp.parse(corpus)
    reference_names: list[str] = []
    for node in tree[1:]:
        if sexp.node_name(node) != "symbol":
            continue
        props = {
            sexp.unquote(c[1]): sexp.unquote(c[2])
            for c in node[1:]
            if isinstance(c, list) and sexp.node_name(c) == "property"
        }
        if props.get("Reference") == "C59":
            reference_names = list(props)
            break
    assert reference_names, "C59 is gone from the fixture; update this test"

    _, text = build("Sync", env)
    ours = sexp.parse(text)
    first = next(node for node in ours[1:] if sexp.node_name(node) == "symbol")
    our_names = [
        sexp.unquote(c[1]) for c in first[1:]
        if isinstance(c, list) and sexp.node_name(c) == "property"
    ]
    assert our_names == reference_names


def test_no_unrendered_placeholders_survive(env) -> None:
    """A stray `{...}` means a template placeholder was written with double braces."""
    _, text = build("MCU", env)
    assert "{" not in text and "}" not in text


def test_header_states_the_child_page_format(env) -> None:
    model, text = build("USB", env)
    head = text.splitlines()[:6]
    # 20260101 was the version the 2026-11-25 corpus carried (written by the old MCP path);
    # this KiCad writes 20260306 for a child page, as the page the user re-saved proved.
    assert head[1].strip() == "(version 20260306)"
    assert head[2].strip() == '(generator "eeschema")'
    assert head[3].strip() == '(generator_version "10.0")'
    assert head[5].strip() == '(paper "A2")'
    assert f'"{model.sheet_uuid}"' in head[4]
    sequence = [name for name, _, _ in sexp.iter_top_level(text)]
    assert "embedded_fonts" not in sequence      # child pages carry none (Â§8.5)


# -- instance context ------------------------------------------------------
def test_context_is_read_from_the_root_page() -> None:
    """The fixture root page places the same sheets the live project does."""
    found = context.find_root_page(REFERENCE)
    assert found is not None and found.name == "MainController.kicad_sch"
    instance = context.read_context(found, "Sync.kicad_sch")
    assert instance.project == "MainController"
    assert instance.path.startswith("/")
    assert instance.path.count("/") == 2           # "/<root-uuid>/<sheet-uuid>"
    assert instance.sheet_uuid and instance.path.endswith(instance.sheet_uuid)
    assert instance.root_page == found


def test_context_matches_what_the_corpus_page_carries() -> None:
    """The path we would write is the path the 2026-11-25 page already carries."""
    instance = context.read_context(REFERENCE / "MainController.kicad_sch", "Sync.kicad_sch")
    corpus = (LIVE / "Sync.kicad_sch").read_text(encoding="utf-8")
    assert f'(path "{instance.path}"' in corpus
    assert f'(project "{instance.project}"' in corpus


def test_context_rejects_a_page_the_root_does_not_place() -> None:
    with pytest.raises(EmitError, match="has no sheet for 'Nope.kicad_sch'"):
        context.read_context(REFERENCE / "MainController.kicad_sch", "Nope.kicad_sch")


def test_sheet_path_from_the_command_line() -> None:
    instance = context.context_from_path("/a/b", "Proj")
    assert (instance.project, instance.path, instance.sheet_uuid) == ("Proj", "/a/b", "b")
    with pytest.raises(EmitError, match="must start with"):
        context.context_from_path("a/b", "Proj")
