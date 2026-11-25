"""563B — the verifiable circuit semantics compiled from a netlist view.

What this file pins, in the order the register (563 §3–§4) states it:

1. ``parts`` / ``pins`` / ``nets`` / ``unconnected`` are the **raw facts**:
   repeated instances stay two parts, two pins of one number stay two pins,
   net members the model can no longer resolve stay listed, an empty net is
   ``unconnected`` and a one-pin *named* net is not;
2. ``two_pin`` keeps pin identity and nets and says nothing about type,
   ``parallel`` needs both ends to agree, ``series`` needs internal nets with
   exactly two device pins of two different parts, and a ring of three or more
   is an ``unknown`` cycle instead of a chain with an arbitrary start;
3. every name the view cannot resolve, and every net the model calls unproven,
   stays in the raw facts but derives no relation;
4. ``verify_semantics`` compares the whole program (so one edited pin, net,
   unknown, relation or NC entry fails) and ``roundtrip_members`` compares the
   raw facts alone; ``to_c`` is deterministic and carries the relations.
"""

from __future__ import annotations

import json

from boardwise.core.circuitsemantics import (
    SCHEMA,
    SCHEMA_HEADER,
    SemanticProgram,
    compile_semantics,
    roundtrip_members,
    verify_semantics,
)
from boardwise.core.model import Component, DesignModel, Net, Pin
from boardwise.core.netlist import NetlistView, read_netlist_document


def _pin(number: str, net: str, name: str | None = None) -> dict:
    return {"name": number if name is None else name, "number": number, "net": net}


def _component(designator: str, pins: dict[str, dict]) -> dict:
    return {"props": {"Designator": designator}, "pinInfoMap": pins}


def _two(designator: str, first: str, second: str) -> dict:
    return _component(designator, {"1": _pin("1", first), "2": _pin("2", second)})


def _view(components: dict) -> NetlistView:
    return NetlistView.from_netlist(
        read_netlist_document({"version": "2.0.0", "components": components})
    )


def _relations(program: SemanticProgram) -> dict:
    return program.as_dict()["relations"]


def _unknowns(program: SemanticProgram) -> list[dict]:
    return program.as_dict()["unknowns"]


def _assert_series_shape(series: list[dict]) -> None:
    """Every chain states its two ends plus every internal net: parts + 1."""
    for record in series:
        assert len(record["nets"]) == len(record["parts"]) + 1, record


# ------------------------------------------------------------- the raw facts


def test_parts_pins_and_nets_are_the_raw_facts_not_a_summary():
    view = _view(
        {
            "r1": _two("R1", "A", "B"),
            "u1": _component(
                "U1",
                {
                    "1": _pin("1", "A", "VIN"),
                    "2": _pin("2", ""),
                    "10": _pin("10", "NC_MARK", "EN"),
                },
            ),
        }
    )
    program = compile_semantics(view)
    payload = program.as_dict()

    assert payload["schema"] == SCHEMA == "boardwise.circuitSemantics/1"
    assert payload["parts"] == [
        {"designator": "R1", "source_id": "r1", "pin_count": 2},
        {"designator": "U1", "source_id": "u1", "pin_count": 3},
    ]
    assert [(pin["designator"], pin["number"], pin["source_id"], pin["pin_key"],
             pin["name"], pin["net"]) for pin in payload["pins"]] == [
        ("R1", "1", "r1", "1", "1", "A"),
        ("R1", "2", "r1", "2", "2", "B"),
        ("U1", "1", "u1", "1", "VIN", "A"),
        ("U1", "2", "u1", "2", "2", ""),
        ("U1", "10", "u1", "10", "EN", "NC_MARK"),
    ]
    assert [net["name"] for net in payload["nets"]] == ["A", "B", "NC_MARK"]
    # Membership keeps host order and full identity, not just the designator.
    assert payload["nets"][0]["members"] == [
        {"designator": "R1", "number": "1", "source_id": "r1", "pin_key": "1"},
        {"designator": "U1", "number": "1", "source_id": "u1", "pin_key": "1"},
    ]


def test_empty_nets_are_unconnected_and_one_pin_named_nets_are_not():
    view = _view(
        {
            "r1": _component(
                "R1",
                {"1": _pin("1", "VCC"), "2": _pin("2", ""), "10": _pin("10", "R1_ONLY")},
            )
        }
    )
    payload = compile_semantics(view).as_dict()

    assert payload["unconnected"] == [
        {"designator": "R1", "number": "2", "source_id": "r1", "pin_key": "2"}
    ]
    # A named one-pin net is a statement of intent: a net, not a dangling stub.
    assert [net["name"] for net in payload["nets"]] == ["VCC", "R1_ONLY"]
    assert "" not in [net["name"] for net in payload["nets"]]
    assert payload["unconnected"][0]["number"] == "2"


def test_two_pins_of_one_number_stay_two_pins_with_their_own_keys():
    view = _view(
        {
            "u1": _component(
                "U1", {"1": _pin("1", "A", "FIRST"), "2": _pin("1", "B", "SECOND")}
            )
        }
    )
    payload = compile_semantics(view).as_dict()

    assert [(pin["number"], pin["pin_key"], pin["net"]) for pin in payload["pins"]] == [
        ("1", "1", "A"),
        ("1", "2", "B"),
    ]
    assert [net["name"] for net in payload["nets"]] == ["A", "B"]
    # The part is still one two-pin part, and the pins are not folded by number.
    assert payload["parts"] == [{"designator": "U1", "source_id": "u1", "pin_count": 2}]
    assert roundtrip_members(view, compile_semantics(view)) is True


# --------------------------------------------------------------- two_pin


def test_two_pin_keeps_pin_identity_and_nets_and_infers_no_type():
    view = _view(
        {
            "r1": _component(
                "R1", {"1": _pin("1", "A", "P1"), "2": _pin("2", "B", "P2")}
            ),
            "u1": _component(
                "U1", {"1": _pin("1", "A"), "2": _pin("2", "B"), "3": _pin("3", "C")}
            ),
        }
    )
    two_pin = _relations(compile_semantics(view))["two_pin"]

    assert two_pin == [
        {
            "part": {"designator": "R1", "source_id": "r1"},
            "pins": [
                {"number": "1", "pin_key": "1", "name": "P1", "net": "A"},
                {"number": "2", "pin_key": "2", "name": "P2", "net": "B"},
            ],
        }
    ]
    # No type, no polarity, no direction key anywhere in the projection.
    for key in ("type", "kind", "value", "mpn", "direction", "role"):
        assert key not in two_pin[0]


def test_parallel_needs_the_whole_net_pair_not_one_shared_end():
    view = _view(
        {
            "r1": _two("R1", "A", "B"),
            "r2": _two("R2", "A", "B"),
            "r3": _two("R3", "A", "C"),
        }
    )
    program = compile_semantics(view)

    assert _relations(program)["parallel"] == [
        {
            "parts": [
                {"designator": "R1", "source_id": "r1"},
                {"designator": "R2", "source_id": "r2"},
            ],
            "between": ["A", "B"],
        }
    ]
    # Both ends equal is also the parallel case, and it is not a series ring:
    # the pair is stated once, as parallel, and chained nowhere.
    assert _relations(program)["series"] == []
    assert [item["kind"] for item in _unknowns(program)] == []
    # A half-shared end and an unwired end never group.
    assert all(
        record["between"] != ["A", "C"] for record in _relations(program)["parallel"]
    )


def test_a_two_pin_part_with_one_empty_end_is_never_parallel():
    view = _view({"r1": _two("R1", "", "B"), "r2": _two("R2", "B", "B")})
    program = compile_semantics(view)

    assert _relations(program)["parallel"] == []
    # Raw fact: both parts are still two-pin parts with their own nets.
    assert [
        [pin["net"] for pin in record["pins"]]
        for record in _relations(program)["two_pin"]
    ] == [["", "B"], ["B", "B"]]


# ----------------------------------------------------------------- series


def test_series_linearises_two_pin_parts_through_a_two_degree_net():
    view = _view(
        {
            "r2": _two("R2", "MID", "B"),
            "r1": _two("R1", "A", "MID"),
        }
    )
    series = _relations(compile_semantics(view))["series"]

    # Canonical by identity, not by source order and not by signal direction;
    # the two end nets travel with the chain, so a reader sees the whole path.
    assert series == [
        {
            "parts": [
                {"designator": "R1", "source_id": "r1"},
                {"designator": "R2", "source_id": "r2"},
            ],
            "nets": ["A", "MID", "B"],
        }
    ]
    _assert_series_shape(series)


def test_a_series_states_both_end_nets_even_when_one_end_is_unconnected():
    """``A - R1 - MID - R2 - (nothing)``: the empty end net is a stated end."""
    view = _view({"r1": _two("R1", "A", "MID"), "r2": _two("R2", "MID", "")})
    series = _relations(compile_semantics(view))["series"]

    assert series == [
        {
            "parts": [
                {"designator": "R1", "source_id": "r1"},
                {"designator": "R2", "source_id": "r2"},
            ],
            "nets": ["A", "MID", ""],
        }
    ]
    _assert_series_shape(series)


def test_a_mid_net_with_a_third_pin_does_not_produce_a_series():
    view = _view(
        {
            "r1": _two("R1", "A", "MID"),
            "r2": _two("R2", "MID", "B"),
            "r3": _two("R3", "MID", "C"),
        }
    )
    program = compile_semantics(view)

    assert _relations(program)["series"] == []
    # The facts are untouched: three two-pin parts, MID with its three members.
    assert [record["part"]["designator"] for record in _relations(program)["two_pin"]] == [
        "R1",
        "R2",
        "R3",
    ]
    mid = next(net for net in program.as_dict()["nets"] if net["name"] == "MID")
    assert len(mid["members"]) == 3


def test_series_chain_is_maximal_and_repeats_no_part_or_net():
    view = _view(
        {
            "r1": _two("R1", "A", "N1"),
            "r2": _two("R2", "N1", "N2"),
            "r3": _two("R3", "N2", "B"),
        }
    )
    series = _relations(compile_semantics(view))["series"]

    assert len(series) == 1
    assert [part["designator"] for part in series[0]["parts"]] == ["R1", "R2", "R3"]
    assert series[0]["nets"] == ["A", "N1", "N2", "B"]
    _assert_series_shape(series)


def test_a_third_pin_on_the_shared_end_net_does_not_turn_a_loop_into_a_chain():
    """R1(GND,N1) - R2(N1,N2) - R3(N2,GND) with a third part on GND.

    The GND pin makes that net no two-degree link, so the three parts look like
    a chain — but both ends carry the same net, which closes the loop. A chain
    may repeat neither a part nor a net, so this is a cycle, not a series.
    """
    view = _view(
        {
            "r1": _two("R1", "GND", "N1"),
            "r2": _two("R2", "N1", "N2"),
            "r3": _two("R3", "N2", "GND"),
            "u1": _component("U1", {"1": _pin("1", "GND")}),
        }
    )
    program = compile_semantics(view)
    payload = program.as_dict()

    assert _relations(program)["series"] == []
    cycles = [item for item in _unknowns(program) if item["kind"] == "cycle"]
    assert len(cycles) == 1
    assert {part["designator"] for part in cycles[0]["parts"]} == {"R1", "R2", "R3"}
    assert len(cycles[0]["nets"]) == len(cycles[0]["parts"])
    assert sorted(cycles[0]["nets"]) == ["GND", "N1", "N2"]
    assert len(set(cycles[0]["nets"])) == len(cycles[0]["nets"])
    # The raw fact still states all three GND members.
    gnd = next(net for net in payload["nets"] if net["name"] == "GND")
    assert [member["designator"] for member in gnd["members"]] == ["R1", "R3", "U1"]


def test_a_series_chain_and_a_parallel_group_coexist():
    """Removing the parallel-pair switch must not swallow either relation."""
    view = _view(
        {
            "r1": _two("R1", "A", "MID"),
            "r2": _two("R2", "MID", "B"),
            "r3": _two("R3", "X", "Y"),
            "r4": _two("R4", "X", "Y"),
            "r5": _two("R5", "Y", "Z"),
        }
    )
    relations = _relations(compile_semantics(view))

    assert [record["nets"] for record in relations["series"]] == [["A", "MID", "B"]]
    assert [
        [part["designator"] for part in record["parts"]]
        for record in relations["series"]
    ] == [["R1", "R2"]]
    assert relations["parallel"] == [
        {
            "parts": [
                {"designator": "R3", "source_id": "r3"},
                {"designator": "R4", "source_id": "r4"},
            ],
            "between": ["X", "Y"],
        }
    ]
    # The parallel pair is stated once, as parallel: it is not also a chain,
    # because its two far ends sit on the same net (Y).
    assert all(
        {part["designator"] for part in record["parts"]} != {"R3", "R4"}
        for record in relations["series"]
    )
    _assert_series_shape(relations["series"])


def test_a_ring_of_three_does_not_get_an_arbitrary_start():
    view = _view(
        {
            "r1": _two("R1", "N3", "N1"),
            "r2": _two("R2", "N1", "N2"),
            "r3": _two("R3", "N2", "N3"),
        }
    )
    program = compile_semantics(view)

    assert _relations(program)["series"] == []
    assert _relations(program)["parallel"] == []
    cycles = [item for item in _unknowns(program) if item["kind"] == "cycle"]
    assert len(cycles) == 1
    assert {part["designator"] for part in cycles[0]["parts"]} == {"R1", "R2", "R3"}
    # Every ring net is listed once, and the ring is closed: one net per part.
    assert sorted(cycles[0]["nets"]) == ["N1", "N2", "N3"]
    assert len(cycles[0]["nets"]) == len(cycles[0]["parts"])


# ---------------------------------------------------- refused names and nets


def test_same_name_instances_keep_every_fact_and_derive_nothing():
    view = _view(
        {
            "p1": _two("U15", "A", "B"),
            "p2": _two("U15", "A", "C"),
        }
    )
    program = compile_semantics(view)
    payload = program.as_dict()

    # Two instances, not one part and not two merged members.
    assert payload["parts"] == [
        {"designator": "U15", "source_id": "p1", "pin_count": 2},
        {"designator": "U15", "source_id": "p2", "pin_count": 2},
    ]
    assert len(payload["pins"]) == 4
    assert {pin["source_id"] for pin in payload["pins"]} == {"p1", "p2"}
    assert payload["nets"][0]["members"] == [
        {"designator": "U15", "number": "1", "source_id": "p1", "pin_key": "1"},
        {"designator": "U15", "number": "1", "source_id": "p2", "pin_key": "1"},
    ]
    # Disclosure, not conclusion: no functional projection for the name.
    assert _unknowns(program) == [{"kind": "ambiguous_designator", "designator": "U15"}]
    assert _relations(program)["two_pin"] == []
    assert _relations(program)["parallel"] == []
    assert _relations(program)["series"] == []


def _unproven_model(pages: tuple[str, ...]) -> DesignModel:
    model = DesignModel()
    model.components["R1"] = Component(
        uid="r1",
        designator="R1",
        pins=[Pin("1", "1", "A"), Pin("2", "2", "B")],
    )
    model.components["R2"] = Component(
        uid="r2",
        designator="R2",
        pins=[Pin("1", "1", "A"), Pin("2", "2", "B")],
    )
    model.nets["A"] = Net("A", [("R1", "1"), ("R2", "1")])
    model.nets["B"] = Net("B", [("R1", "2"), ("R2", "2")])
    model.unproven_nets["A"] = pages
    return model


def test_unproven_nets_derive_nothing_and_are_disclosed():
    view = NetlistView.from_model(_unproven_model(("page-a", "page-b")))
    program = compile_semantics(view)

    assert _relations(program)["parallel"] == []
    assert _relations(program)["series"] == []
    # The raw facts survive; only the derivation is withheld.
    assert [record["part"]["designator"] for record in _relations(program)["two_pin"]] == [
        "R1",
        "R2",
    ]
    assert _unknowns(program) == [
        {"kind": "unproven_net", "net": "A", "pages": ["page-a", "page-b"]}
    ]


def test_the_same_model_without_unproven_nets_is_parallel_again():
    model = _unproven_model(())
    del model.unproven_nets["A"]
    program = compile_semantics(NetlistView.from_model(model))

    assert _relations(program)["parallel"] == [
        {
            "parts": [
                {"designator": "R1", "source_id": "r1"},
                {"designator": "R2", "source_id": "r2"},
            ],
            "between": ["A", "B"],
        }
    ]
    assert _unknowns(program) == []


def test_net_members_the_model_cannot_resolve_stay_in_the_raw_facts():
    model = DesignModel()
    model.components["U1"] = Component(
        uid="u1", designator="U1", pins=[Pin("1", "1", "VCC")]
    )
    model.nets["VCC"] = Net("VCC", [("U1", "1"), ("U9", "1")])
    view = NetlistView.from_model(model)
    payload = compile_semantics(view).as_dict()

    assert payload["nets"] == [
        {
            "name": "VCC",
            "members": [
                {"designator": "U1", "number": "1", "source_id": "u1", "pin_key": "0"},
                {"designator": "U9", "number": "1", "source_id": "", "pin_key": ""},
            ],
        }
    ]
    # Not addressable, therefore not a pin fact — but the net states it.
    assert [pin["designator"] for pin in payload["pins"]] == ["U1"]
    assert roundtrip_members(view, compile_semantics(view)) is True


def test_a_designator_carrying_dots_keeps_its_own_pins():
    view = _view(
        {
            "a": _component(
                "U9", {"3": _pin("3", "PIN3", "N3"), "33": _pin("33", "PIN33", "N33")}
            ),
            "b": _component("U9.3", {"1": _pin("1", "DOTTED", "D1")}),
        }
    )
    payload = compile_semantics(view).as_dict()

    assert [(pin["designator"], pin["number"], pin["name"], pin["net"])
            for pin in payload["pins"]] == [
        ("U9", "3", "N3", "PIN3"),
        ("U9", "33", "N33", "PIN33"),
        ("U9.3", "1", "D1", "DOTTED"),
    ]
    # `U9.3` is the part literally called that, and it is a unique two-pin-part
    # candidate only if it has two pins — here it has one, so it is not one.
    assert [record["part"]["designator"] for record in _relations(compile_semantics(view))["two_pin"]] == [
        "U9"
    ]


# ------------------------------------------------------------ verification


def _tampered(payload: dict, path: list, value) -> dict:
    node = payload
    for step in path[:-1]:
        node = node[step]
    if value is None:
        del node[path[-1]]
    else:
        node[path[-1]] = value
    return payload


def test_as_dict_is_a_deep_copy_and_the_program_stays_verifiable():
    view = _view({"r1": _two("R1", "A", "B"), "r2": _two("R2", "A", "B")})
    program = compile_semantics(view)

    payload = program.as_dict()
    payload["relations"]["parallel"][0]["between"][0] = "Z"
    payload["pins"].append({"designator": "X"})

    assert verify_semantics(view, program) is True
    assert program.as_dict()["relations"]["parallel"][0]["between"] == ["A", "B"]
    assert len(program.as_dict()["pins"]) == 4


def test_verify_rejects_every_edit_including_unknowns_relations_and_nc():
    view = _view(
        {
            "r1": _two("R1", "A", "MID"),
            "r2": _two("R2", "MID", "B"),
            "r3": _two("R3", "MID", "C"),
            "u15a": _two("U15", "X", "Y"),
            "u15b": _two("U15", "X", "Z"),
            "r4": _component("R4", {"1": _pin("1", ""), "2": _pin("2", "A")}),
        }
    )
    program = compile_semantics(view)
    assert verify_semantics(view, program) is True
    # A plain dict copy is as good as the object it came from.
    assert verify_semantics(view, program.as_dict()) is True

    def rejected(payload: dict) -> bool:
        return verify_semantics(view, payload) is False

    # one pin edited
    assert rejected(_tampered(program.as_dict(), ["pins", 0, "net"], "ELSEWHERE"))
    assert rejected(_tampered(program.as_dict(), ["pins", 1, "pin_key"], "9"))
    # one net member dropped, and one pin dropped from the part table
    doubled = program.as_dict()
    doubled["nets"][0]["members"].pop()
    assert rejected(doubled)
    assert rejected(_tampered(program.as_dict(), ["parts", 0, "pin_count"], 3))
    # the NC entry
    assert rejected(_tampered(program.as_dict(), ["unconnected", 0], None))
    # the unknowns
    assert rejected(_tampered(program.as_dict(), ["unknowns", 0], None))
    assert rejected(_tampered(program.as_dict(), ["unknowns"], []))
    # the relations
    assert rejected(_tampered(program.as_dict(), ["relations", "two_pin"], []))
    assert rejected(
        _tampered(program.as_dict(), ["relations", "parallel"], [{"parts": [], "between": []}])
    )
    # the schema
    assert rejected(_tampered(program.as_dict(), ["schema"], "boardwise.circuitSemantics/2"))
    # a tampered program object fails the same way, and junk is refused
    assert rejected(SemanticProgram(_tampered(program.as_dict(), ["unknowns"], [])))
    assert verify_semantics(view, None) is False
    assert verify_semantics(view, {"schema": SCHEMA}) is False


def _series_view() -> NetlistView:
    return _view(
        {
            "r1": _two("R1", "A", "MID"),
            "r2": _two("R2", "MID", "B"),
            "r3": _two("R3", "C", ""),
            "u15a": _two("U15", "X", "Y"),
            "u15b": _two("U15", "X", "Z"),
        }
    )


def test_roundtrip_members_verifies_the_raw_pin_and_net_facts():
    view = _series_view()
    program = compile_semantics(view)

    assert roundtrip_members(view, program) is True
    assert roundtrip_members(view, program.as_dict()) is True

    # An NC entry, a repeated-instance member and a whole pin all matter here.
    assert roundtrip_members(view, _tampered(program.as_dict(), ["unconnected"], [])) is False
    doubled = program.as_dict()
    doubled["nets"][1]["members"].pop()
    assert roundtrip_members(view, doubled) is False
    assert roundtrip_members(view, _tampered(program.as_dict(), ["pins", 3, "pin_key"], "7")) is False

    # Relations are verify's business, not this reading's: the facts still
    # round-trip when only a relation was edited.
    relations_edited = _tampered(program.as_dict(), ["relations", "series"], [])
    assert roundtrip_members(view, relations_edited) is True
    assert verify_semantics(view, relations_edited) is False


def test_roundtrip_sees_an_unresolvable_model_member_go_missing():
    model = DesignModel()
    model.components["U1"] = Component(
        uid="u1", designator="U1", pins=[Pin("1", "1", "VCC")]
    )
    model.nets["VCC"] = Net("VCC", [("U1", "1"), ("U9", "1")])
    view = NetlistView.from_model(model)
    program = compile_semantics(view)

    assert roundtrip_members(view, program) is True
    dropped = program.as_dict()
    dropped["nets"][0]["members"].pop()
    assert roundtrip_members(view, dropped) is False


# ---------------------------------------------------------------- the C text


def test_to_c_starts_with_the_schema_header_and_is_byte_deterministic():
    view = _view(
        {
            "r1": _two("R1", "A", "MID"),
            "r2": _two("R2", "MID", "B"),
            "r3": _two("R3", "A", "B"),
            "r4": _two("R4", "A", "B"),
            "r5": _two("R5", "", "C"),
            "u15a": _two("U15", "Y", "Z"),
            "u15b": _two("U15", "Y", "W"),
        }
    )
    program = compile_semantics(view)
    text = program.to_c()

    assert text.splitlines()[0] == SCHEMA_HEADER == "// boardwise.circuitSemantics/1"
    assert text.encode("utf-8") == program.to_c().encode("utf-8")
    assert text == compile_semantics(view).to_c()
    for call in ("part(", "pin(", "net(", "two_pin(", "parallel(", "series(",
                 "unconnected(", "unknown("):
        assert call in text
    assert 'series(["R1@r1", "R2@r2"], ["A", "MID", "B"]);' in text
    assert 'parallel(["R3@r3", "R4@r4"], ["A", "B"]);' in text
    assert 'unconnected("R5.1@r5#1");' in text
    assert 'unknown("ambiguous_designator", "U15");' in text
    assert text.endswith("\n")


def test_to_c_escapes_strings_so_one_net_name_cannot_forge_a_line():
    awkward = 'A"B\\C\nD\tE'
    view = _view({"r1": _two("R1", awkward, "B"), "r2": _two("R2", awkward, "B")})
    text = compile_semantics(view).to_c()

    # The literal is escaped, so a net name cannot inject a new statement.
    assert json.dumps(awkward) in text
    assert len(text.splitlines()) == len(text.rstrip("\n").splitlines())
    for line in text.rstrip("\n").splitlines():
        assert line.endswith(";") or line.startswith("// ")
    # Escaped and deterministic, and the relation still reads.
    assert text == compile_semantics(view).to_c()
    assert 'parallel(["R1@r1", "R2@r2"]' in text


def test_two_pin_text_keeps_same_number_pins_apart_by_key():
    """``1#1:A`` and ``1#2:B``: one number, two keys, two readable pins."""
    view = _view(
        {
            "u1": _component(
                "U1", {"1": _pin("1", "A", "FIRST"), "2": _pin("1", "B", "SECOND")}
            )
        }
    )
    text = compile_semantics(view).to_c()

    assert 'two_pin("U1@u1", ["1#1:A", "1#2:B"]);' in text
    # A pin with no key gets no invented `#`. Clear the parsed keys directly
    # to exercise that projection branch (list input itself uses stable indices).
    parsed = read_netlist_document(
        {"version": "2.0.0", "components": {"r1": _two("R1", "A", "B")}}
    )
    for pin in parsed.parts[0].pins:
        pin.key = ""
    elsewhere = compile_semantics(NetlistView(parsed)).to_c()
    assert 'two_pin("R1@r1", ["1:A", "2:B"]);' in elsewhere


def test_to_c_renders_the_unknowns_it_was_given():
    view = _view(
        {
            "r1": _two("R1", "N3", "N1"),
            "r2": _two("R2", "N1", "N2"),
            "r3": _two("R3", "N2", "N3"),
            "u15a": _two("U15", "X", "Y"),
            "u15b": _two("U15", "X", "Z"),
        }
    )
    text = compile_semantics(view).to_c()

    assert 'unknown("ambiguous_designator", "U15");' in text
    assert 'unknown("cycle", ["R1@r1"' in text
