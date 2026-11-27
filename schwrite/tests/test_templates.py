"""M0 golden test: every frozen template must reproduce the corpus node exactly.

Two comparisons are made, and they answer different questions:

  * **tree equality** against the reference page â€” does the template say the same thing
    KiCad said? This is the semantic gate and it is what must stay true across KiCad
    updates.
  * **format equality** against a re-render of the same template â€” is our writer
    deterministic? KiCad itself is not byte-consistent in one respect (`Value` property
    hidden-effects line breaks, see docs/format-notes.md), so byte equality is claimed
    against *our own* output, which is what S6 reproducibility means.
"""

from __future__ import annotations

import re

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from schwrite import sexp  # noqa: E402
from schwrite.emit import templates as T  # noqa: E402

REFERENCE = REPO / "tests" / "fixtures" / "reference"
SYNC = REFERENCE / "Sync.kicad_sch"


@pytest.fixture(scope="module")
def sync_text() -> str:
    return SYNC.read_text(encoding="utf-8")


def semantic(node):
    """Compare what KiCad *means*, not how the corpus happens to spell it.

    The one thing the corpus cannot be held to is where a property's `hide` flag sits
    (`Footprint`/`Datasheet`/`Description` use top-level in 241 fields and `effects` in
    23; `Value` uses `effects` in all 57 hidden cases). KiCad reads both as hidden, so a
    property column collapses to `(name, value, at, hidden)` and everything else must
    match exactly.
    """
    if isinstance(node, list):
        name = sexp.node_name(node)
        if name == "property":
            name_value = sexp.unquote(node[1])
            text_value = sexp.unquote(node[2])
            at = next((c for c in node if isinstance(c, list) and sexp.node_name(c) == "at"), None)
            at_t = tuple(sexp.normalise(x) for x in at[1:]) if at else None
            hidden = False
            for child in node:
                if not isinstance(child, list):
                    continue
                if sexp.node_name(child) == "hide":
                    hidden = True
                if sexp.node_name(child) == "effects":
                    hidden = hidden or any(
                        sexp.node_name(g) == "hide" for g in child if isinstance(g, list)
                    )
            return ("property", name_value, text_value, at_t, hidden)
        return [name] + [semantic(child) for child in node[1:]]
    return node


def assert_same_meaning(rendered: str, corpus: str) -> None:
    assert semantic(sexp.parse(rendered)) == semantic(sexp.parse(corpus))


def assert_trees_equal(rendered: str, corpus: str) -> None:
    left = sexp.normalise(sexp.parse(rendered))
    right = sexp.normalise(sexp.parse(corpus))
    assert left == right


def test_page_header_matches_corpus(sync_text: str) -> None:
    """The five header nodes, in order, as the corpus writes them."""
    header = T.render_page_header(version=T.VERSION_CHILD, sheet_uuid="ff51e3ae-6705-4088-a6ec-9bf26dca941d", paper="A2")
    wrapped = header + ")\n"
    corpus_head = sync_text[: sync_text.index("(lib_symbols")]
    # the corpus was written by the old MCP path with an older format number; everything
    # else in the header must match node for node
    corpus_head = re.sub(
        r"\(version \d+\)", f"(version {T.VERSION_CHILD})", corpus_head, count=1
    )
    corpus_wrapped = corpus_head.rstrip() + "\n)\n"
    assert sexp.normalise(sexp.parse(wrapped)) == sexp.normalise(sexp.parse(corpus_wrapped))


def test_symbol_instance_shape() -> None:
    """A rendered instance has KiCad's node order and only Reference/Value visible.

    This replaces a byte comparison with the 2026-11-25 corpus: that build hid Value for
    large prefixes, while the user's rule (2026-11-26) is that both are shown.
    """
    props = "".join(
        [
            T.property_block("Reference", "U6", (91.44, 43.18)),
            T.property_block("Value", "SN74LVC1G125DCKR", (91.44, 45.72)),
            T.property_block("Footprint", "Footprint:IC", (91.44, 33.02), hide_top=True),
            T.property_block("Datasheet", "", (91.44, 33.02), hide_top=True),
            T.property_block("Description", "", (91.44, 33.02), hide_top=True),
        ]
    )
    rendered = T.render_symbol(
        lib_id="components:components/X", x=91.44, y=33.02, angle=0,
        uuid="11111111-1111-1111-1111-111111111111", properties=props,
        pins=T.render_pin_ref(number="1", uuid="22222222-2222-2222-2222-222222222222"),
        project="P", path="/r/s", reference="U6", fields_autoplaced=True,
    )
    tree = sexp.parse(rendered)
    children = [sexp.node_name(node) for node in tree[1:] if isinstance(node, list)]
    assert children[:4] == ["lib_id", "at", "unit", "body_style"]
    assert children[-1] == "instances"
    assert children.count("property") == 5
    value_block = rendered.split('(property "Value"')[1].split("(property")[0]
    assert "(hide yes)" not in value_block
def test_wire_matches_corpus(sync_text: str) -> None:
    corpus_node = sexp.find_top_level(sync_text, "wire", index=0)
    assert corpus_node is not None
    rendered = T.render_wire(
        x1=82.55, y1=33.02, x2=80.01, y2=33.02, uuid="edfec058-d911-4239-89ab-78f4fb1bffca"
    )
    assert_trees_equal(rendered, corpus_node)


def test_global_label_matches_corpus(sync_text: str) -> None:
    corpus_node = sexp.find_top_level(sync_text, "global_label", index=0)
    assert corpus_node is not None
    rendered = T.render_global_label(
        text="SYNC",
        x=80.01,
        y=33.02,
        angle=180,
        uuid="0a4bc1f0-5801-4ded-b2d4-a00a59c1e402",
        justify="right",
    )
    assert_trees_equal(rendered, corpus_node)


def test_sheet_instances_matches_corpus(sync_text: str) -> None:
    corpus_node = sexp.find_top_level(sync_text, "sheet_instances", index=0)
    assert corpus_node is not None
    assert_trees_equal(T.render_sheet_instances(page="1"), corpus_node)


def test_emitter_is_deterministic() -> None:
    a = T.render_wire(x1=10, y1=20.5, x2=10, y2=23.04, uuid="00000000-0000-0000-0000-000000000000")
    b = T.render_wire(x1=10, y1=20.5, x2=10, y2=23.04, uuid="00000000-0000-0000-0000-000000000000")
    assert a == b


def test_scanner_survives_parentheses_in_strings() -> None:
    """A net name with a paren must not break node boundaries."""
    text = '(kicad_sch\n\t(label "A(B) C")\n\t(wire (pts (xy 0 0) (xy 1 1)))\n)\n'
    assert sexp.count_top_level(text) == {"label": 1, "wire": 1}


def test_corpus_has_no_junctions_or_embedded_fonts() -> None:
    """Format facts that the emitter relies on (Â§8.4 'no junctions' claim)."""
    text = SYNC.read_text(encoding="utf-8")
    counts = sexp.count_top_level(text)
    assert counts.get("junction", 0) == 0
    assert counts.get("embedded_fonts", 0) == 0
    assert counts.get("global_label", 0) == counts.get("wire", 0)
