"""565b — the six holes 565 opened in 563's semantic projection layer.

Each test pins the parent's ruling in ``tasks/565b_semantics_holes.md`` §④, and
each one is written to fail on the pre-fix tree:

S1-1 a part with a designator and **no pins** vanished from ``parts`` and from
     the C text, although ``_facts`` claims to state every part;
S1-2 ``verify_semantics`` / ``roundtrip_members`` compared with ``==``, so
     ``true`` (a JSON bool) or ``1.0`` could stand in for ``1``;
S1-3 ``to_c()`` interpolated ``parts[].pin_count`` raw, so an outside program
     could forge a whole ``net("FORGED", ["X"]);`` statement;
S1-4 ``read_netlist_document`` silently skipped a component row it could not
     read (non-object row, missing/blank ``Designator``);
S1-5 ``nets_of`` merged two instances sharing designator *and* source_id while
     ``net_of`` refused the very same ambiguity;
S1-6 pin names were re-read live from the mutable ``view.source`` on every
     compile, so one view compiled to two different documents.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from boardwise.core.circuitsemantics import (
    SemanticProgram,
    compile_semantics,
    roundtrip_members,
    verify_semantics,
)
from boardwise.core.netlist import (
    AmbiguousPinError,
    Netlist,
    NetlistPart,
    NetlistPin,
    NetlistView,
    PinRef,
    UnknownPinError,
    read_netlist_document,
)


def _pin(number: str, net: str, name: str | None = None) -> dict:
    return {"name": number if name is None else name, "number": number, "net": net}


def _component(designator: str, pins: dict[str, dict]) -> dict:
    return {"props": {"Designator": designator}, "pinInfoMap": pins}


def _two(designator: str, first: str, second: str) -> dict:
    return _component(designator, {"1": _pin("1", first), "2": _pin("2", second)})


def _doc(components: dict) -> dict:
    return {"version": "2.0.0", "components": components}


def _view(components: dict) -> NetlistView:
    return NetlistView.from_netlist(read_netlist_document(_doc(components)))


# ---------------------------------------------------------------------- S1-1


@pytest.mark.parametrize("pin_map", [{}, []], ids=["empty-map", "empty-list"])
def test_s1_1_a_part_with_a_designator_and_no_pins_is_still_stated(pin_map):
    """A zero-pin part is a part: stated with ``pin_count: 0``, and rendered.

    The rest of the projection is unchanged — no pin, no net, no relation is
    invented for it, and the pin-bearing facts stay exactly what they were.
    """
    view = _view(
        {
            "r1": _two("R1", "A", "B"),
            "u9": {"props": {"Designator": "U9"}, "pinInfoMap": pin_map},
        }
    )
    program = compile_semantics(view)
    payload = program.as_dict()

    assert payload["parts"] == [
        {"designator": "R1", "source_id": "r1", "pin_count": 2},
        {"designator": "U9", "source_id": "u9", "pin_count": 0},
    ]
    # Nothing else is invented or taken away for the pin-less part.
    assert [(pin["designator"], pin["number"], pin["net"]) for pin in payload["pins"]] == [
        ("R1", "1", "A"),
        ("R1", "2", "B"),
    ]
    assert [net["name"] for net in payload["nets"]] == ["A", "B"]
    assert payload["unconnected"] == []
    assert [
        record["part"]["designator"] for record in payload["relations"]["two_pin"]
    ] == ["R1"]
    assert payload["unknowns"] == []
    assert view.duplicate_designators() == ()

    # The text states the part, and only in its own ``part(...)`` line.
    text = program.to_c()
    assert "part(\"U9\", \"u9\", pins=0);" in text
    assert "part(\"R1\", \"r1\", pins=2);" in text
    assert [line for line in text.splitlines() if '"U9"' in line] == [
        'part("U9", "u9", pins=0);'
    ]
    assert roundtrip_members(view, program) is True
    assert verify_semantics(view, program) is True


# ---------------------------------------------------------------------- S1-2

#: The template fixture's one-pin part: ``pin_count`` is the int ``1``.
LAUNDERED = [True, 1.0, "1", [1], 1.0000000001]


@pytest.mark.parametrize(
    "laundered",
    LAUNDERED,
    ids=["json-true", "float-1.0", "string-1", "list-1", "float-just-past"],
)
def test_s1_2_verify_and_roundtrip_compare_types_strictly(laundered):
    """``true`` / ``1.0`` / ``'1'`` / ``[1]`` never stand in for the int ``1``."""
    view = _view({"r1": _component("R1", {"1": _pin("1", "A")})})
    program = compile_semantics(view)
    assert program.as_dict()["parts"] == [
        {"designator": "R1", "source_id": "r1", "pin_count": 1}
    ]
    assert verify_semantics(view, program) is True
    assert roundtrip_members(view, program) is True

    tampered = program.as_dict()
    tampered["parts"][0]["pin_count"] = laundered

    assert verify_semantics(view, tampered) is False
    assert roundtrip_members(view, tampered) is False


def test_s1_2_dict_keys_and_list_order_are_compared_strictly():
    """The same strict comparison covers dict key sets and list order/length."""
    view = _view({"r1": _two("R1", "A", "B")})
    program = compile_semantics(view)
    assert verify_semantics(view, program) is True

    extra_key = program.as_dict()
    extra_key["parts"][0]["pin_count_again"] = 2
    assert verify_semantics(view, extra_key) is False

    missing_key = program.as_dict()
    del missing_key["pins"][0]["pin_key"]
    assert verify_semantics(view, missing_key) is False

    reordered = program.as_dict()
    reordered["pins"].reverse()
    assert verify_semantics(view, reordered) is False

    longer = program.as_dict()
    longer["nets"].append({"name": "Z", "members": []})
    assert verify_semantics(view, longer) is False


# ---------------------------------------------------------------------- S1-3

#: The legal rendering of the two-pin fixture, pinned byte for byte: the fix
#: must not move one character of a legitimate program.
LEGAL_TEXT = (
    "// boardwise.circuitSemantics/1\n"
    'part("R1", "r1", pins=2);\n'
    'pin("R1", "1", "r1", "1", "1", "A");\n'
    'pin("R1", "2", "r1", "2", "2", "B");\n'
    'net("A", ["R1.1@r1#1"]);\n'
    'net("B", ["R1.2@r1#2"]);\n'
    'two_pin("R1@r1", ["1#1:A", "2#2:B"]);\n'
)

FORGED = '1); net("FORGED", ["X"]); //'


@pytest.mark.parametrize(
    "forged",
    [FORGED, True, 2.0, "2", None],
    ids=["forged-line", "json-true", "float", "string", "none"],
)
def test_s1_3_to_c_refuses_a_pin_count_that_is_not_an_int(forged):
    """Only a real ``int`` may be rendered; nothing is emitted otherwise."""
    view = _view({"r1": _two("R1", "A", "B")})
    program = compile_semantics(view)

    assert program.to_c() == LEGAL_TEXT
    assert 'net("FORGED"' not in program.to_c()

    tampered = program.as_dict()
    tampered["parts"][0]["pin_count"] = forged
    outside = SemanticProgram(tampered)

    with pytest.raises(ValueError) as refused:
        outside.to_c()
    assert "pin_count" in str(refused.value)
    assert "R1" in str(refused.value)

    # The legal program is untouched, and the tampering still fails verification.
    assert program.to_c() == LEGAL_TEXT
    assert verify_semantics(view, tampered) is False


# ---------------------------------------------------------------------- S1-4

_GOOD_ROW = {
    "props": {"Designator": "R1"},
    "pinInfoMap": {"1": _pin("1", "A"), "2": _pin("2", "B")},
}


def test_s1_4_the_reader_refuses_a_component_row_it_cannot_read():
    """A row this reader cannot account for is a ``ValueError``, not a skip."""
    for key, row in (("b", None), ("c", "not-a-component"), ("g", 17)):
        document = _doc({"a": _GOOD_ROW, key: row})
        with pytest.raises(ValueError) as refused:
            read_netlist_document(document)
        message = str(refused.value)
        assert repr(key) in message or f"'{key}'" in message, message
        assert "not a component" in message

    for key, row in (
        ("d", {"pinInfoMap": {"1": _pin("1", "C")}}),
        ("e", {"props": {"Designator": "   "}, "pinInfoMap": {"1": _pin("1", "D")}}),
        ("f", {"props": {}, "pinInfoMap": {"1": _pin("1", "E")}}),
    ):
        document = _doc({"a": _GOOD_ROW, key: row})
        with pytest.raises(ValueError) as refused:
            read_netlist_document(document)
        message = str(refused.value)
        assert f"'{key}'" in message or f'"{key}"' in message, message
        assert "Designator" in message


def test_s1_4_the_two_17_part_fixtures_still_read_unchanged():
    """The stricter reader does not touch the two real 17-part samples."""
    fixtures = Path(__file__).with_name("fixtures")
    for name in ("ch340_p1_editor_netlist.json", "ch340_drawn_page_netlist.json"):
        document = json.loads((fixtures / name).read_text(encoding="utf-8"))
        parsed = read_netlist_document(document)
        assert len(parsed.parts) == 17, name
        assert parsed.pin_count() == 66, name
        assert all(part.designator for part in parsed.parts), name


# ---------------------------------------------------------------------- S1-5


def _two_instances(first_source_id: str, second_source_id: str) -> NetlistView:
    return NetlistView(
        Netlist(
            parts=[
                NetlistPart(
                    "U1", [NetlistPin("1", "1", "A", "1")], source_id=first_source_id
                ),
                NetlistPart(
                    "U1", [NetlistPin("1", "1", "B", "2")], source_id=second_source_id
                ),
            ]
        )
    )


def test_s1_5_nets_of_refuses_the_ambiguity_net_of_refuses():
    """One refusal law for both doors, even when the source_ids are identical."""
    merged = _two_instances("", "")
    assert merged.duplicate_designators() == ("U1",)
    with pytest.raises(AmbiguousPinError):
        merged.net_of("U1", "1")
    # The hole: this used to answer ('A', 'B'), merging two instances.
    with pytest.raises(AmbiguousPinError):
        merged.nets_of("U1")
    # Naming the shared source_id does not disambiguate two instances under it.
    with pytest.raises(AmbiguousPinError):
        merged.nets_of("U1", source_id="")

    distinct = _two_instances("a", "b")
    with pytest.raises(AmbiguousPinError):
        distinct.nets_of("U1")
    assert distinct.nets_of("U1", source_id="a") == ("A",)
    assert distinct.nets_of("U1", source_id="b") == ("B",)
    with pytest.raises(UnknownPinError):
        distinct.nets_of("U1", source_id="c")


# ---------------------------------------------------------------------- S1-6


def test_s1_6_pin_names_are_snapshotted_when_the_view_is_built():
    """A view answers names from its own snapshot, never from a live source."""
    netlist = read_netlist_document(_doc({"r1": _two("R1", "A", "B")}))
    view = NetlistView(netlist)
    assert view.pin_names() == {
        PinRef("R1", "1", "r1", "1"): "1",
        PinRef("R1", "2", "r1", "2"): "2",
    }

    first = compile_semantics(view)
    assert [pin["name"] for pin in first.as_dict()["pins"]] == ["1", "2"]

    netlist.parts[0].pins[0].raw_name = "FORGED"

    second = compile_semantics(view)
    assert second.as_dict() == first.as_dict()
    assert second.to_c() == first.to_c()
    assert [pin["name"] for pin in second.as_dict()["pins"]] == ["1", "2"]
    assert view.pin_names()[PinRef("R1", "1", "r1", "1")] == "1"
    assert verify_semantics(view, first) is True


def test_s1_6_model_pin_names_are_snapshotted_too():
    """The ``DesignModel`` source is snapshotted by the same constructor."""
    from boardwise.core.model import Component, DesignModel, Pin

    model = DesignModel()
    model.components["U1"] = Component(
        uid="u1", designator="U1", pins=[Pin("1", "VIN", "A"), Pin("2", "", None)]
    )
    view = NetlistView.from_model(model)
    assert view.pin_names() == {
        PinRef("U1", "1", "u1", "0"): "VIN",
        PinRef("U1", "2", "u1", "1"): "",
    }

    first = compile_semantics(view)
    assert [pin["name"] for pin in first.as_dict()["pins"]] == ["VIN", ""]

    model.components["U1"].pins[0].name = "FORGED"

    assert compile_semantics(view).as_dict() == first.as_dict()
    assert verify_semantics(view, first) is True


# ------------------------------------------ S1-4 追加: the pin row (565b §⑦)


def test_s1_4_the_reader_refuses_a_pin_row_it_cannot_read():
    """A pin row that is not an object is refused, naming component and key.

    Three stated pin rows used to read as two pins with nothing said about the
    third — the same silent-drop path S1-4 closed for component rows.
    """
    document = _doc(
        {
            "r1": {
                "props": {"Designator": "R1"},
                "pinInfoMap": {
                    "1": _pin("1", "A"),
                    "2": _pin("2", "B"),
                    "3": "not-a-pin",
                },
            }
        }
    )
    with pytest.raises(ValueError) as refused:
        read_netlist_document(document)
    message = str(refused.value)
    assert "R1" in message
    assert "'3'" in message
    assert "not a pin object" in message

    # A list-shaped map has no host keys: the positional index is the key.
    listed = _doc(
        {
            "r1": {
                "props": {"Designator": "R2"},
                "pinInfoMap": [
                    _pin("1", "A"),
                    {"number": "2", "net": "B"},
                    "not-a-pin",
                ],
            }
        }
    )
    with pytest.raises(ValueError) as refused_list:
        read_netlist_document(listed)
    message = str(refused_list.value)
    assert "R2" in message
    assert "'2'" in message
    assert "not a pin object" in message


@pytest.mark.parametrize("member", ["pinInfoMap", "pins"])
def test_s1_4_a_pin_map_member_of_the_wrong_type_is_refused(member):
    """A present-but-unreadable pin map is a refusal, not a zero-pin part."""
    document = _doc({"r1": {"props": {"Designator": "R1"}, member: 17}})
    with pytest.raises(ValueError) as refused:
        read_netlist_document(document)
    message = str(refused.value)
    assert "R1" in message
    assert member in message
    assert "not a mapping" in message


def test_s1_4_json_null_pin_map_without_pins_is_zero_pin():
    """JSON ``null`` means 「not written」: no pins stated, so a zero-pin part."""
    program = compile_semantics(
        NetlistView(
            read_netlist_document(
                _doc({"u9": {"props": {"Designator": "U9"}, "pinInfoMap": None}})
            )
        )
    )
    assert program.as_dict()["parts"] == [
        {"designator": "U9", "source_id": "u9", "pin_count": 0}
    ]
    assert 'part("U9", "u9", pins=0);' in program.to_c()


def test_s1_4_json_null_pin_map_falls_back_to_the_pins_member():
    """``pinInfoMap: null`` plus a real ``pins`` mapping reads that mapping."""
    document = _doc(
        {
            "r1": {
                "props": {"Designator": "R1"},
                "pinInfoMap": None,
                "pins": {"1": _pin("1", "A"), "2": _pin("2", "B")},
            }
        }
    )
    payload = compile_semantics(NetlistView(read_netlist_document(document))).as_dict()
    assert payload["parts"] == [
        {"designator": "R1", "source_id": "r1", "pin_count": 2}
    ]
    assert [(pin["number"], pin["net"]) for pin in payload["pins"]] == [
        ("1", "A"),
        ("2", "B"),
    ]


def test_s1_4_a_part_with_no_pin_map_member_is_still_a_zero_pin_part():
    """The S1-1 contract stands: no pin map member is a legal, pin-less part."""
    for row in (
        {"props": {"Designator": "U9"}},
        {"props": {"Designator": "U9"}, "pinInfoMap": {}},
        {"props": {"Designator": "U9"}, "pins": []},
    ):
        program = compile_semantics(
            NetlistView(read_netlist_document(_doc({"u9": row})))
        )
        assert program.as_dict()["parts"] == [
            {"designator": "U9", "source_id": "u9", "pin_count": 0}
        ]
        assert 'part("U9", "u9", pins=0);' in program.to_c()

