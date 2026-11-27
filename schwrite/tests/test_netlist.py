"""Netlist contract tests (§Appendix A)."""

from __future__ import annotations

import json

import pytest

from conftest import NETLISTS, PAGES
from schwrite import netlist
from schwrite.errors import NetlistError


def minimal(**overrides) -> dict:
    data = {
        "design": "MCB-01",
        "subsystem": "T",
        "components": [{"ref": "R1", "lcsc": "C25744"}, {"ref": "R2", "lcsc": "C25744"}],
        "nets": [{"name": "N1", "members": [{"ref": "R1", "pin": "1"}, {"ref": "R2", "pin": "1"}]}],
    }
    data.update(overrides)
    return data


# -- the real corpus -------------------------------------------------------
@pytest.mark.parametrize("page", sorted(PAGES))
def test_every_project_netlist_loads(page: str) -> None:
    loaded = netlist.load(NETLISTS / f"{page}.json")
    assert len(loaded.components) == PAGES[page]
    assert loaded.subsystem == page
    assert loaded.nets
    # every referenced pin exists exactly once, and the inversion is total
    mapping = loaded.pin_net_map()
    assert sum(len(pins) for pins in mapping.values()) == sum(
        len(net["members"]) for net in loaded.nets
    )


def test_net_members_preserves_order_and_groups_by_net() -> None:
    loaded = netlist.parse(minimal())
    members = loaded.net_members()
    assert list(members) == ["N1"]
    assert members["N1"] == [("R1", "1"), ("R2", "1")]


# -- rejections ------------------------------------------------------------
def test_rejects_a_pin_on_two_nets() -> None:
    data = minimal()
    data["nets"].append({"name": "N2", "members": [{"ref": "R1", "pin": "1"}]})
    with pytest.raises(NetlistError, match="two nets"):
        netlist.parse(data)


def test_rejects_unknown_component_in_a_net() -> None:
    data = minimal()
    data["nets"][0]["members"].append({"ref": "R9", "pin": "1"})
    with pytest.raises(NetlistError, match="unknown component 'R9'"):
        netlist.parse(data)


@pytest.mark.parametrize("field", ["lcsc", "mpn"])
def test_rejects_a_component_without_any_database_identifier(field: str) -> None:
    data = minimal(components=[{"ref": "R1"}])
    with pytest.raises(NetlistError, match="give an lcsc or mpn"):
        netlist.parse(data)


def test_rejects_lib_id_in_a_netlist() -> None:
    """The database decides the symbol; a netlist may not name one (§2)."""
    data = minimal(components=[{"ref": "R1", "lcsc": "C25744", "lib_id": "Standard:R"}])
    with pytest.raises(NetlistError, match="lib_id"):
        netlist.parse(data)


def test_rejects_duplicate_reference() -> None:
    data = minimal(components=[{"ref": "R1", "lcsc": "C1"}, {"ref": "R1", "lcsc": "C1"}])
    with pytest.raises(NetlistError, match="duplicate reference R1"):
        netlist.parse(data)


def test_rejects_empty_members() -> None:
    data = minimal()
    data["nets"] = [{"name": "N1", "members": []}]
    with pytest.raises(NetlistError, match="members must be a non-empty list"):
        netlist.parse(data)


def test_rejects_member_without_pin() -> None:
    data = minimal()
    data["nets"][0]["members"][0] = {"ref": "R1"}
    with pytest.raises(NetlistError, match="has no pin"):
        netlist.parse(data)


def test_rejects_net_without_name() -> None:
    data = minimal(nets=[{"members": [{"ref": "R1", "pin": "1"}]}])
    with pytest.raises(NetlistError, match="net without name"):
        netlist.parse(data)


def test_rejects_non_json(tmp_path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(NetlistError, match="not valid JSON"):
        netlist.load(bad)


def test_rejects_missing_file(tmp_path) -> None:
    with pytest.raises(NetlistError, match="cannot read netlist"):
        netlist.load(tmp_path / "nope.json")


def test_string_pin_numbers_are_kept_as_text() -> None:
    """`A4B9` is a legal pin number; nothing may coerce it to a number."""
    data = minimal(
        components=[{"ref": "U1", "lcsc": "C1"}],
        nets=[{"name": "N1", "members": [{"ref": "U1", "pin": "A4B9"}]}],
    )
    loaded = netlist.parse(data)
    assert loaded.pin_net_map()["U1"] == {"A4B9": "N1"}
