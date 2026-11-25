"""563A — the shared netlist reader and the instance-aware view.

The reader moved out of ``engines/drawlint.py`` into ``core/netlist.py``; this
file pins the three things that move could silently break:

1. the old drawlint surface still reads the same documents and reports the same
   fields (L12's input), and
2. a pin is addressed **by instance**: two host entries called ``U15`` are two
   same-designator instances — multi-unit packaging or a repeated placement,
   and the name does not decide which — so an unnamed query is refused rather
   than answered by the first one, and two pins of one number inside one entry
   stay two pins;
3. ``candidate_from_netlist`` is now a projection over that same reader and
   keeps its historical numbers — ``R?`` skipped, later instance owns the
   component, **every** instance still contributes its net members, pins ordered
   by the host key length, empty net ``None``, raw tail blocks kept, and the
   entry-level ``Unique ID`` still wins over the property one.
"""

from __future__ import annotations

import json

import pytest

from boardwise.core import netlist as shared_netlist
from boardwise.core.candidate import NetlistFormatError, candidate_from_netlist
from boardwise.core.model import Component, DesignModel, Net, Pin
from boardwise.core.netlist import (
    AmbiguousPinError,
    NetlistView,
    PinRef,
    UnknownPinError,
    read_netlist_document,
)
from boardwise.engines import drawlint


def _doc(components: dict, **extra) -> dict:
    return {"version": "2.0.0", "components": components, **extra}


def _pin(number: str, net: str, name: str | None = None) -> dict:
    return {"name": number if name is None else name, "number": number, "net": net}


def _duplicate_designator_document() -> dict:
    """``U15`` stated twice, plus a resistor and a one-pin net."""
    return _doc(
        {
            "p1": {
                "props": {"Designator": "U15", "Value": "u1"},
                "pinInfoMap": {
                    "1": _pin("1", "GND", "OUT1"),
                    "8": _pin("8", "VCC", "V+"),
                },
            },
            "p2": {
                "props": {"Designator": "U15", "Value": "u2"},
                "pinInfoMap": {
                    "1": _pin("1", "GND", "OUT2"),
                    "2": _pin("2", "VCC", "IN2-"),
                },
            },
            "p3": {
                "props": {"Designator": "R1", "Value": "10k"},
                "pinInfoMap": {
                    "1": _pin("1", "VCC"),
                    "2": _pin("2", ""),
                    "10": _pin("10", "R1_ONLY"),
                },
            },
        }
    )


# ------------------------------------------------------- the reader is shared


def test_drawlint_names_are_the_shared_reader_not_a_second_copy():
    assert drawlint.read_netlist_document is shared_netlist.read_netlist_document
    assert drawlint.NetlistPin is shared_netlist.NetlistPin
    assert drawlint.NetlistPart is shared_netlist.NetlistPart
    assert drawlint.Netlist is shared_netlist.Netlist


def test_the_reader_still_answers_the_wrapper_and_the_raw_document():
    """L12's input: wrapper ``{type, text}`` and the decoded netlist both read,
    garbage is refused rather than read as 「no connections」."""
    wrapper = {"type": "EasyEDA", "text": json.dumps(_duplicate_designator_document())}
    from_wrapper = read_netlist_document(wrapper)
    from_raw = read_netlist_document(_duplicate_designator_document())
    for parsed in (from_wrapper, from_raw):
        assert [(p.designator, p.source_id) for p in parsed.parts] == [
            ("U15", "p1"),
            ("U15", "p2"),
            ("R1", "p3"),
        ]
        part = parsed.parts[0]
        assert [(p.number, p.name, p.net, p.key) for p in part.pins] == [
            ("1", "OUT1", "GND", "1"),
            ("8", "V+", "VCC", "8"),
        ]
        assert parsed.pin_nets() == {"GND", "VCC", "R1_ONLY"}
        assert parsed.pin_count() == 7
    for broken in ({"text": "{not json"}, {"nope": 1}, 42, _doc({})):
        with pytest.raises(ValueError):
            read_netlist_document(broken)


# ------------------------------------------------- instance identity queries


def test_same_designator_instances_are_not_merged_and_stay_addressable():
    view = NetlistView(read_netlist_document(_duplicate_designator_document()))

    # Nothing is merged and nothing is raised as a defect: the two entries stay
    # two instances, and the clash is disclosed by name only.
    assert view.duplicate_designators() == ("U15",)
    assert view.ambiguous_designators() == ("U15",)

    with pytest.raises(AmbiguousPinError) as refused:
        view.net_of("U15", "1")
    assert "U15.1" in str(refused.value)
    assert "p1" in str(refused.value) and "p2" in str(refused.value)

    assert view.net_of("U15", "1", source_id="p1") == "GND"
    assert view.net_of("U15", "1", source_id="p2") == "GND"
    assert view.net_of("U15", "2", source_id="p2") == "VCC"
    with pytest.raises(UnknownPinError):
        view.net_of("U15", "2", source_id="p1")

    with pytest.raises(AmbiguousPinError):
        view.nets_of("U15")
    assert view.nets_of("U15", source_id="p1") == ("GND", "VCC")
    assert view.nets_of("U15", source_id="p2") == ("GND", "VCC")

    with pytest.raises(AmbiguousPinError):
        view.neighbors("U15", "1")
    assert view.neighbors("U15", "1", source_id="p1") == (
        PinRef("U15", "1", "p2", "1"),
    )

    assert view.members("GND") == (
        PinRef("U15", "1", "p1", "1"),
        PinRef("U15", "1", "p2", "1"),
    )
    assert view.members("VCC") == (
        PinRef("U15", "8", "p1", "8"),
        PinRef("U15", "2", "p2", "2"),
        PinRef("R1", "1", "p3", "1"),
    )


def test_two_pins_of_one_number_inside_one_entry_stay_two_pins():
    """One host entry, two ``pinInfoMap`` keys, one number, two nets.

    The keys are the identity here: folding by number would drop a pin and let
    the first net answer for the second.
    """
    view = NetlistView(
        read_netlist_document(
            _doc(
                {
                    "p1": {
                        "props": {"Designator": "U1"},
                        "pinInfoMap": {
                            "1": _pin("1", "A", "FIRST"),
                            "2": _pin("1", "B", "SECOND"),
                        },
                    }
                }
            )
        )
    )

    assert view.members("A") == (PinRef("U1", "1", "p1", "1"),)
    assert view.members("B") == (PinRef("U1", "1", "p1", "2"),)
    assert view.pin_refs() == (
        PinRef("U1", "1", "p1", "1"),
        PinRef("U1", "1", "p1", "2"),
    )
    with pytest.raises(AmbiguousPinError):
        view.net_of("U1", "1")
    with pytest.raises(AmbiguousPinError):
        view.net_of("U1", "1", source_id="p1")
    assert view.net_of(PinRef("U1", "1", "p1", "1")) == "A"
    assert view.net_of(PinRef("U1", "1", "p1", "2")) == "B"
    assert view.nets_of("U1", source_id="p1") == ("A", "B")
    assert view.unconnected() == ()


def test_a_dotted_designator_splits_on_its_last_dot():
    assert PinRef.parse("U15.1") == PinRef("U15", "1")
    assert PinRef.parse("U9.33") == PinRef("U9", "33")
    assert PinRef.parse("U9.3.1") == PinRef("U9.3", "1")
    with pytest.raises(ValueError):
        PinRef.parse("U15")
    with pytest.raises(ValueError):
        PinRef.parse("U15.")

    document = _doc(
        {
            "a": {
                "props": {"Designator": "U9"},
                "pinInfoMap": {
                    "3": _pin("3", "PIN3", "N3"),
                    "33": _pin("33", "PIN33", "N33"),
                },
            },
            "b": {
                "props": {"Designator": "U9.3"},
                "pinInfoMap": {"1": _pin("1", "DOTTED")},
            },
        }
    )
    view = NetlistView(read_netlist_document(document))

    # `U9.3` is designator U9, pin 3 — never U9's pin 33, and never the part
    # that is literally called `U9.3`.
    assert view.net_of("U9.3") == "PIN3"
    assert view.net_of("U9", "33") == "PIN33"
    assert view.net_of(PinRef("U9", "33", "a", "33")) == "PIN33"
    assert view.members("PIN3") == (PinRef("U9", "3", "a", "3"),)
    assert view.members("PIN33") == (PinRef("U9", "33", "a", "33"),)
    # The dotted designator is reachable only by naming the instance's pin.
    assert view.net_of(PinRef("U9.3", "1")) == "DOTTED"
    assert view.members("DOTTED") == (PinRef("U9.3", "1", "b", "1"),)


def test_empty_nets_and_one_pin_named_nets_are_different_readings():
    view = NetlistView(read_netlist_document(_duplicate_designator_document()))

    assert view.unconnected() == (PinRef("R1", "2", "p3", "2"),)
    assert PinRef("U15", "8", "p1", "8") not in view.unconnected()

    # A named net with one pin is intent, not a dangling stub.
    assert view.members("R1_ONLY") == (PinRef("R1", "10", "p3", "10"),)
    assert view.neighbors("R1", "10", source_id="p3") == ()
    # Empty nets never become net names.
    assert "" not in view.net_names()
    assert set(view.net_names()) == {"GND", "VCC", "R1_ONLY"}
    assert view.nets_of("R1", source_id="p3") == ("VCC", "R1_ONLY")
    assert view.net_of("R1", "2", source_id="p3") == ""


def test_neighbors_is_only_the_other_pins_on_the_same_net():
    view = NetlistView(read_netlist_document(_duplicate_designator_document()))

    assert view.neighbors("R1", "1", source_id="p3") == (
        PinRef("U15", "8", "p1", "8"),
        PinRef("U15", "2", "p2", "2"),
    )
    with pytest.raises(UnknownPinError):
        view.net_of("R9", "1")
    with pytest.raises(UnknownPinError):
        view.nets_of("R9")


# -------------------------------------------------------- from a DesignModel


def test_from_model_keeps_the_models_facts_and_discloses_unproven_names():
    model = DesignModel()
    model.components["U1"] = Component(
        uid="u1",
        designator="U1",
        pins=[Pin("1", "VCC", "VCC"), Pin("2", "NC", None)],
    )
    model.components["R1"] = Component(
        uid="r1",
        designator="R1",
        pins=[Pin("1", "1", "VCC"), Pin("2", "2", "GND")],
    )
    model.nets["VCC"] = Net("VCC", [("U1", "1"), ("R1", "1")])
    model.nets["GND"] = Net("GND", [("R1", "2")])
    model.nets["VCC_FROM_OTHER_PAGE"] = Net("VCC_FROM_OTHER_PAGE", [("U9", "1")])
    model.unproven_nets["VCC"] = ()
    model.duplicate_designators.append("U9")
    model.cross_page_designators["U7"] = ["page-a", "page-b"]

    view = NetlistView.from_model(model)

    assert view.members("VCC") == (
        PinRef("U1", "1", "u1", "0"),
        PinRef("R1", "1", "r1", "0"),
    )
    assert view.net_of("U1", "1") == "VCC"
    assert view.nets_of("U1", source_id="u1") == ("VCC",)
    assert view.unconnected() == (PinRef("U1", "2", "u1", "1"),)
    # Disclosure only: the unproven name is named, and nothing is derived.
    assert view.unproven_nets == {"VCC": ()}
    # `duplicate_designators` is the model's own clash list; the wider
    # `ambiguous_designators` also carries the same-name cross-page placement.
    assert view.duplicate_designators() == ("U9",)
    assert view.ambiguous_designators() == ("U7", "U9")
    # A member the model's component table no longer holds is listed as the
    # model states it, and is NOT turned into a component that can be queried.
    assert view.members("VCC_FROM_OTHER_PAGE") == (PinRef("U9", "1", "", ""),)
    with pytest.raises(UnknownPinError):
        view.net_of("U9", "1")
    assert PinRef("U9", "1", "", "") not in view.unconnected()


def test_from_model_numbers_its_pins_and_admits_when_it_cannot_resolve_one():
    model = DesignModel()
    model.components["U1"] = Component(
        uid="u1",
        designator="U1",
        pins=[Pin("1", "A", "A"), Pin("1", "B", "B")],
    )
    model.nets["A"] = Net("A", [("U1", "1")])

    view = NetlistView.from_model(model)

    # The model's own pin order is the stable key, so both pins survive …
    assert view.pin_refs() == (
        PinRef("U1", "1", "u1", "0"),
        PinRef("U1", "1", "u1", "1"),
    )
    assert view.net_of(PinRef("U1", "1", "u1", "0")) == "A"
    assert view.net_of(PinRef("U1", "1", "u1", "1")) == "B"
    with pytest.raises(AmbiguousPinError):
        view.net_of("U1", "1")
    # … and a net member that matches two pins keeps no key: it stays listed
    # but does not pretend to be a resolved pin.
    assert view.members("A") == (PinRef("U1", "1", "u1", ""),)
    with pytest.raises(AmbiguousPinError):
        view.net_of(PinRef("U1", "1", "u1", ""))


# ------------------------------------------------- the candidate projection


def test_candidate_keeps_every_duplicate_instance_member():
    document = _doc(
        {
            "p1": {
                "props": {"Designator": "U15", "Value": "u1"},
                "pinInfoMap": {
                    "1": _pin("1", "GND", "OUT1"),
                    "8": _pin("8", "VCC", "V+"),
                },
            },
            "p2": {
                "props": {"Designator": "U15", "Value": "u2"},
                "pinInfoMap": {
                    "1": _pin("1", "GND", "OUT2"),
                    "2": _pin("2", "VCC", "IN2-"),
                },
            },
            "p3": {
                "props": {"Designator": "R1", "Value": "10k"},
                "pinInfoMap": {
                    "1": _pin("1", "VCC"),
                    "2": _pin("2", ""),
                    "10": _pin("10", "R1_ONLY"),
                },
            },
            "p4": {"props": {"Designator": "R?"}, "pinInfoMap": {"1": _pin("1", "VCC")}},
            "p5": {
                "props": {"Designator": "U2", "DeviceName": "opamp"},
                "pinInfoMap": {
                    "10": _pin("10", "VCC"),
                    "1": _pin("1", "GND"),
                    "2": _pin("2", ""),
                },
            },
            # UID provenance: the entry-level `Unique ID` wins over the
            # property one, and a property-only UID still reads.
            "p6": {"props": {"Designator": "U3"}, "Unique ID": "entry-uid"},
            "p7": {"props": {"Designator": "U4", "Unique ID": "props-uid"}},
            "p8": {
                "props": {"Designator": "U5", "Unique ID": "props-uid"},
                "Unique ID": "entry-wins",
            },
        },
        designRule={"traceWidth": 8},
        netClass=[{"name": "Default"}],
    )

    model = candidate_from_netlist(json.dumps(document))

    assert sorted(model.components) == ["R1", "U15", "U2", "U3", "U4", "U5"]
    assert model.duplicate_designators == ["U15"]
    assert model.components["U3"].uid == "entry-uid"
    assert model.components["U4"].uid == "props-uid"
    assert model.components["U5"].uid == "entry-wins"
    # The later placement owns the component (historical rule) …
    assert model.components["U15"].value == "u2"
    assert [(p.number, p.name, p.net) for p in model.components["U15"].pins] == [
        ("1", "OUT2", "GND"),
        ("2", "IN2-", "VCC"),
    ]
    # … and every same-designator instance still contributes its net members.
    assert model.nets["GND"].pins == [("U15", "1"), ("U2", "1")]
    assert model.nets["VCC"].pins == [
        ("U15", "8"),
        ("U15", "2"),
        ("R1", "1"),
        ("U2", "10"),
    ]
    assert model.nets["R1_ONLY"].pins == [("R1", "10")]
    # Empty net is `None`, never a net called "".
    assert model.components["R1"].pins[1].net is None
    assert "" not in model.nets
    # Pin order is by the host key's length: 1, 2, 10.
    assert [p.number for p in model.components["U2"].pins] == ["1", "2", "10"]
    # The four historical tail blocks stay on `raw`.
    assert model.raw == {"designRule": {"traceWidth": 8}, "netClass": [{"name": "Default"}]}
    assert model.components["U2"].props["device_name"] == "opamp"

    # The same document keeps its own refusals.
    with pytest.raises(NetlistFormatError):
        candidate_from_netlist("{not json}")
    with pytest.raises(NetlistFormatError):
        candidate_from_netlist(json.dumps({"components": {}}))
    with pytest.raises(NetlistFormatError):
        candidate_from_netlist(json.dumps(_doc({"p1": {"props": {"Designator": "R?"}}})))
