"""The paired signal-input repair consumes existing intent and preserves legacy binds."""
from copy import deepcopy

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawcompiler as dc
from boardwise.engines.grammar import voltage_divider as vd


def _case(*, count=2, unequal=False, renamed=False, side="left", mode="input"):
    parts, nets, ids, roles = [], [], [], {}
    ground_members = []
    for branch in range(count):
        prefix = f"UNIT{branch}" if renamed else f"B{branch}"
        top = prefix + "_IN"
        roles[top] = mode
        arm_count = 3 if unequal and branch == 1 else 2
        arms = [prefix + f"_ARM{i}" for i in range(arm_count)]
        ids.extend(arms)
        parts.extend({"id": arm, "symbolRef": "R", "value": "1k"} for arm in arms)
        nets.append({"id": top, "class": "signal", "members": [arms[0] + ".1"]})
        nets.extend({"id": prefix + f"_TAP{i}", "class": "signal",
                     "members": [arms[i] + ".2", arms[i + 1] + ".1"]}
                    for i in range(arm_count - 1))
        ground_members.append(arms[-1] + ".2")
    nets.append({"id": "GND", "class": "gnd", "members": ground_members})
    circuit = {"parts": parts, "nets": nets}
    spec = {"grammarRef": "voltage-divider",
            "modules": [{"id": "indicators", "parts": ids, "role": "paired status chains"}],
            "portRoles": roles, "serviceLayout": {"pinGap": 30},
            "labelPolicy": {"stub": "straight", "stubMin": 40},
            "sidePreferences": {"power": "top", "input": side,
                                "gnd": "right" if side == "left" else "left"}}
    return circuit, spec


def _bind(circuit, spec):
    return vd.grammar().bind(CircuitSpec.from_dict(circuit), PresentationSpec.from_dict(spec))


def _relations(binding):
    return [(item.kind, item.subject, item.object) for item in binding.constraints]


def _book():
    return {"R": SymbolProfile.from_dict({
        "symbolRef": "R", "body": [-10, -5, 10, 5],
        "pins": [{"number": "1", "name": "1", "tip": [-20, 0], "direction": "left", "length": 10},
                 {"number": "2", "name": "2", "tip": [20, 0], "direction": "right", "length": 10}],
    })}


def _physical_led_case(side):
    """The real module's numeric pin mapping; no evidence-folder dependency."""
    circuit, spec = _case(side=side)
    names = {"B0_ARM0": "R2", "B0_ARM1": "D1", "B1_ARM0": "R3", "B1_ARM1": "D2",
             "B0_IN": "LED1_K", "B1_IN": "LED2_K", "B0_TAP0": "LED1_A", "B1_TAP0": "LED2_A"}
    for part in circuit["parts"]:
        part["id"] = names[part["id"]]
    for net in circuit["nets"]:
        net["id"] = names.get(net["id"], net["id"])
        members = []
        for member in net["members"]:
            owner, token = member.split(".")
            owner = names[owner]
            if owner.startswith("D"):
                token = "2" if token == "1" else "1"
            members.append(owner + "." + token)
        net["members"] = members
    spec["portRoles"] = {names[net]: role for net, role in spec["portRoles"].items()}
    spec["modules"][0]["parts"] = [names[part] for part in spec["modules"][0]["parts"]]
    return circuit, spec


@pytest.mark.parametrize("renamed", [False, True])
@pytest.mark.parametrize("side,order,progress", [("left", "left-of", (1., 0.)),
                                                  ("right", "right-of", (-1., 0.))])
def test_pair_uses_declared_input_for_relations_and_original_context(renamed, side, order, progress):
    circuit, spec = _case(renamed=True, side=side) if renamed else _physical_led_case(side)
    bound = _bind(circuit, spec)
    first_upper, first_lower, second_upper, second_lower = (
        ("UNIT0_ARM0", "UNIT0_ARM1", "UNIT1_ARM0", "UNIT1_ARM1")
        if renamed else ("R2", "D1", "R3", "D2")
    )
    assert bound.ok
    assert _relations(bound) == [
        ("same-row", first_upper, first_lower),
        (order, first_upper, first_lower),
        ("vertical-tap", first_upper, first_lower),
        ("same-row", second_upper, second_lower),
        (order, second_upper, second_lower),
        ("vertical-tap", second_upper, second_lower),
        ("same-column", first_upper, second_upper),
        ("same-column", first_lower, second_lower),
    ]
    order_constraints = [item for item in bound.constraints if item.kind == order]
    assert len(order_constraints) == 2
    assert all(f"sidePreferences.input={side}" in item.reason for item in order_constraints)
    assert all("sidePreferences.power=" not in item.reason for item in order_constraints)
    prepared = dc._prepare(CircuitSpec.from_dict(circuit), PresentationSpec.from_dict(spec),
                           bound, _book(), dc.CompileBudget(page_box=None))
    assert prepared.failures == []
    assert prepared.context is not None
    assert (prepared.context.axis, prepared.context.progress) == ("h", progress)


@pytest.mark.parametrize("declaration", ["open", "both"])
def test_all_actual_input_declarations_agree(declaration):
    circuit, spec = _case()
    circuit["openInterfaces"] = [{"net": net, "direction": "input", "role": "host input"}
                                 for net in spec["portRoles"]]
    if declaration == "open":
        spec["portRoles"] = {}
    bound = _bind(circuit, spec)
    assert ("left-of", "B0_ARM0", "B0_ARM1") in _relations(bound)
    assert ("same-column", "B0_ARM0", "B1_ARM0") in _relations(bound)


@pytest.mark.parametrize("case,axis,order", [
    ("default", "column", "above"),
    ("legacy-reverse", "row", "right-of"),
    ("same-axis", "row", "left-of"),
    ("source", "column", "above"),
    ("mixed-role", "column", "above"),
    ("conflict-source", "column", "above"),
    ("conflict-output", "column", "above"),
    ("no-service", "column", "above"),
    ("no-stub", "column", "above"),
    ("single", "column", "above"),
    ("four", "column", "above"),
    ("unequal", "column", "above"),
    ("vertical-mixed", "column", "above"),
    ("same-side", "column", "above"),
    ("power", "column", "above"),
])
def test_outside_the_pair_repair_keeps_complete_legacy_binding(monkeypatch, case, axis, order):
    circuit, spec = _case(count=4 if case == "four" else 1 if case == "single" else 2,
                          unequal=case == "unequal", mode="source" if case == "source" else "input")
    if case == "default":
        spec.pop("sidePreferences")
    elif case == "legacy-reverse":
        spec["sidePreferences"] = {"power": "right", "gnd": "left"}
    elif case == "same-axis":
        spec["sidePreferences"]["power"] = "left"
    elif case == "source":
        spec["sidePreferences"]["source"] = "right"
    elif case == "mixed-role":
        spec["portRoles"]["B1_IN"] = "source"
    elif case.startswith("conflict-"):
        circuit["openInterfaces"] = [{"net": "B1_IN", "direction": case.partition("-")[2],
                                      "role": "conflicting declaration"}]
    elif case == "no-service":
        spec.pop("serviceLayout")
    elif case == "no-stub":
        spec.pop("labelPolicy")
    elif case == "vertical-mixed":
        spec["sidePreferences"] = {"power": "left", "input": "top", "gnd": "bottom"}
    elif case == "same-side":
        spec["sidePreferences"]["input"] = "right"
    elif case == "power":
        for net in circuit["nets"]:
            if net["id"].endswith("_IN"):
                net["class"] = "power"
    bound = _bind(circuit, spec)
    # These literal geometric obligations do not depend on the disabled-helper
    # comparison. They expose an overly broad repair, including the four-chain
    # axis-vote counterexample, rather than comparing the implementation to itself.
    assert ("same-" + axis, "B0_ARM0", "B0_ARM1") in _relations(bound)
    assert (order, "B0_ARM0", "B0_ARM1") in _relations(bound)
    if case == "four":
        assert ("same-row", "B0_ARM0", "B3_ARM0") in _relations(bound)
    current = bound.to_jsonable()
    monkeypatch.setattr(vd, "_input_pair_side", lambda *_: None, raising=False)
    assert _bind(deepcopy(circuit), deepcopy(spec)).to_jsonable() == current


def test_default_input_value_is_consumed_without_inventing_explicit_metadata():
    circuit, spec = _case()
    spec["sidePreferences"].pop("input")
    assert ("left-of", "B0_ARM0", "B0_ARM1") in _relations(_bind(circuit, spec))
