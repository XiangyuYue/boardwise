"""A declared single-pin signal input keeps its visible-wire promise."""
from collections import Counter
from dataclasses import replace

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawcompiler as dc
from test_548d_divider_families import _led_circuit, _led_presentation
from test_548j_joint_seats import _pin, _symbol


def _case(*, renamed=False, declaration="port"):
    circuit = _led_circuit()
    document = _led_presentation(
        serviceLayout={"pinGap": 30}, textPlacement="native-attr",
        labelPolicy={"stub": "straight", "stubMin": 40,
                     "stubLaneReserve": True, "rowModel": "centered"},
    ).to_jsonable()
    payload = circuit.to_jsonable()
    inputs = ["LED1_K", "LED2_K"]
    if renamed:
        names = {part["id"]: f"DEVICE_{index}" for index, part in enumerate(payload["parts"])}
        nets = {net["id"]: f"NODE_{index}" for index, net in enumerate(payload["nets"])}
        for part in payload["parts"]:
            part["id"] = names[part["id"]]
        for net in payload["nets"]:
            net["id"] = nets[net["id"]]
            net["members"] = [names[m.partition(".")[0]] + "." + m.partition(".")[2]
                              for m in net["members"]]
        inputs = [nets[net] for net in inputs]
        document["portRoles"] = dict.fromkeys(inputs, "input")
    if declaration == "open":
        document["portRoles"] = {}
        payload["openInterfaces"] = [{"net": net, "direction": "source", "role": "signal input"}
                                     for net in inputs]
    circuit = CircuitSpec.from_dict(payload)
    document["userLocks"] = [
        {"partId": part["id"], "x": (index % 2) * 160.,
         "y": 160. if index < 2 else 40., "rotation": 270.}
        for index, part in enumerate(payload["parts"])
    ]
    spec = PresentationSpec.from_dict(document)
    book = {name: SymbolProfile.from_dict(_symbol(name, [-10.5, -4.5, 10.5, 4.5], [
        _pin("1", [-20, 0], "left"), _pin("2", [20, 0], "right")]))
        for name in ("R0402", "LED0603")}
    book["PWR-GND"] = SymbolProfile.from_dict(_symbol("PWR-GND", [-6, 0, 6, 18], []))
    binding = dc.bind_grammar(circuit, spec, book)
    assert binding.ok
    binding = dc._with_series_arms(binding, spec)
    binding = dc._with_panel_groups(binding, spec, circuit)
    binding = dc._with_service_groups(binding, spec, circuit, book)
    prepared = dc._prepare(circuit, spec, binding, book, dc.CompileBudget(page_box=None))
    assert prepared.context is not None and not prepared.failures
    return prepared.context, inputs


@pytest.mark.parametrize("renamed,declaration,group_first", [
    (False, "port", False), (True, "open", True),
])
def test_declared_input_replays_its_reserved_nonzero_carrier(monkeypatch, renamed, declaration, group_first):
    ctx, inputs = _case(renamed=renamed, declaration=declaration)
    if group_first:
        ctx.budget = replace(ctx.budget, flag_lead_limit=120., gnd_cluster_radius=100.)
    original = dc._reserve_label_stubs
    selected = {}
    calls = Counter()

    def reserve(*args, **kwargs):
        result = original(*args, **kwargs)
        if args[2] in inputs:
            calls[args[2]] += 1
            selected.update(result[0])
        return result

    monkeypatch.setattr(dc, "_reserve_label_stubs", reserve)
    built, failure, _ = dc._build_candidate(ctx, dc._variants(ctx)[0])
    assert built is not None, failure
    for net in inputs:
        segment, = [item for item in built.plan.segments if item.net == net]
        label, = [item for item in built.plan.labels if item.net == net]
        assert len(segment.points) == 2
        assert segment.points[0] != segment.points[-1]
        assert list(segment.points) == list(selected[(net, segment.points[0])][2])
        assert abs(segment.points[-1][0] - segment.points[0][0]) >= 40
        assert segment.points[-1] == (label.x, label.y)
        assert (label.stub, label.stub_min, label.row_model) == ("straight", 40, "centered")
        assert calls[net] == 1
        assert dc._direct_wire_finding(built.plan, ctx.circuit, ctx.book, None, net) is None


@pytest.mark.parametrize("net,cls,count,obligated,role,expected", [
    ("LED1_K", "signal", 1, True, "input", "label"),
    ("LED1_K", "signal", 1, True, "source", "label"),
    ("LED1_K", "signal", 1, False, "input", "label"),
    ("LED1_K", "signal", 1, True, "output", "flag"),
    ("LED1_K", "power", 1, True, "input", "flag"),
    ("LED1_K", "gnd", 1, True, "input", "flag"),
    ("LED1_K", "signal", 2, True, "input", "wire"),
])
def test_expression_boundary(net, cls, count, obligated, role, expected):
    ctx, _ = _case()
    ctx.presentation.port_roles[net] = role
    assert dc._expression_style(ctx, net, cls, count, {net} if obligated else set())[0] == expected


def test_missing_reserved_carrier_is_named_refusal(monkeypatch):
    ctx, inputs = _case()
    original = dc._lead_lane_reservations

    def drop(*args, **kwargs):
        plan, failure = original(*args, **kwargs)
        return {key: value for key, value in plan.items() if key[0] not in inputs}, failure

    monkeypatch.setattr(dc, "_lead_lane_reservations", drop)
    built, failure, _ = dc._build_candidate(ctx, dc._variants(ctx)[0])
    assert built is None
    assert failure is not None
    assert "reserved" in failure.detail and failure.subject in inputs


def test_zero_length_reserved_carrier_is_refused(monkeypatch):
    ctx, inputs = _case()
    original = dc._lead_lane_reservations

    def collapse(*args, **kwargs):
        plan, failure = original(*args, **kwargs)
        for key in list(plan):
            if key[0] in inputs:
                direction, _far, _path = plan[key]
                plan[key] = direction, key[1], [key[1], key[1]]
        return plan, failure

    monkeypatch.setattr(dc, "_lead_lane_reservations", collapse)
    built, failure, _ = dc._build_candidate(ctx, dc._variants(ctx)[0])
    assert built is None
    assert failure.subject in inputs and "legal visible wire" in failure.detail


@pytest.mark.parametrize("declaration", ["no-obligation", "output"])
def test_ordinary_singleton_keeps_its_original_bare_name(declaration):
    ctx, inputs = _case()
    if declaration == "no-obligation":
        ctx.binding = replace(ctx.binding, obligations=())
    else:
        ctx.presentation.port_roles.update(dict.fromkeys(inputs, "output"))
    built, failure, _ = dc._build_candidate(ctx, dc._variants(ctx)[0])
    assert built is not None, failure
    assert not [item for item in built.plan.segments if item.net in inputs]
    assert len([item for item in built.plan.labels if item.net in inputs]) == 2
