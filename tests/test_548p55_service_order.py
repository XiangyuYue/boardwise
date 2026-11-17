"""Explicit service branch order selects existing physical rows, not coordinates.

All symbol geometry here is synthetic; these cases do not certify EasyEDA art.
"""
from dataclasses import replace
from functools import partial

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawcompiler as dc, readability
from test_548j_joint_seats import _book, _circuit, _document, _pin, _prepared, _symbol, _tip


def _case(*, order=("R2", "R1"), host=(400.0, 400.0), rename=False, reverse_pin_rows=False):
    book = _book()
    book["HOST8"] = SymbolProfile.from_dict(_symbol(
        "HOST8", [-25.5, -25.5, 25.5, 25.5], [
            _pin("GND", [-35.0, 15.0], "left"),
            _pin("BOOT0", [-35.0, -5.0], "left"),
            _pin("BOOT1", [-35.0, 5.0], "left"),
            _pin("RX", [-35.0, -15.0], "left"),
            _pin("TX", [35.0, -15.0], "right"),
            _pin("CFG_A", [35.0, 5.0 if reverse_pin_rows else -5.0], "right"),
            _pin("CFG_B", [35.0, -5.0 if reverse_pin_rows else 5.0], "right"),
            _pin("VDD", [35.0, 15.0], "right"),
        ]))
    for ref, body in (("C", [-10.5, -8.5, 10.5, 8.5]),
                      ("PWR-GND", [-10.5, 9.5, 10.5, 19.5]),
                      ("PWR-PWR", [-5.5, 4.5, 5.5, 14.5])):
        pins = [_pin("1", [-20, 0], "left"), _pin("2", [20, 0], "right")] if ref == "C" else []
        book[ref] = SymbolProfile.from_dict(_symbol(ref, body, pins))
    circuit = _circuit()
    payload = _document()
    payload["textPlacement"] = "native-attr"
    payload["userLocks"] = [{"partId": "U1", "x": host[0], "y": host[1]}]
    if order:
        payload["modules"][0]["branchOrder"] = list(order)
    if rename:
        names = {"R1": "Z9", "R2": "A4", "R3": "M8", "U1": "IC7"}
        raw = circuit.to_jsonable()
        for part in raw["parts"]:
            part["id"] = names.get(part["id"], part["id"])
        for net in raw["nets"]:
            net["members"] = [names.get(member.split(".")[0], member.split(".")[0]) + "." + member.split(".")[1]
                              for member in net["members"]]
        circuit = CircuitSpec.from_dict(raw)
        module = payload["modules"][0]
        module["parts"] = [names.get(part, part) for part in module["parts"]]
        module["core"] = names[module["core"]]
        if order:
            module["branchOrder"] = [names[part] for part in order]
        payload["userLocks"][0]["partId"] = names["U1"]
        for group in payload["serviceGroups"]:
            for branch in group["branches"]:
                branch["part"] = names.get(branch["part"], branch["part"])
    spec = PresentationSpec.from_dict(payload)
    ctx = _prepared(circuit, spec, book)
    ctx.budget = replace(ctx.budget, max_candidates=8)
    return circuit, spec, book, ctx


def _build(case):
    circuit, spec, book, ctx = case
    built, failure, violations = dc._build_candidate(ctx, dc._variants(ctx)[0])
    assert built is not None, (failure, violations)
    checked = readability.check(
        built.plan, circuit, spec, book,
        grammar_checker=partial(dc.check_grammar, budget=ctx.budget),
        page_box=ctx.budget.page_box, grid=ctx.budget.grid)
    assert checked.ok and not checked.grammar_findings
    derived = readability.derive_netlist(built.plan, book)
    assert len(derived.pin_points) == len(derived.wired_pins) == 18
    for net in circuit.nets:
        for member in net.members:
            assert set(derived.group_of(member)) == set(net.members)
    return built.plan, ctx


@pytest.mark.parametrize("host,rename", [((400.0, 400.0), False), ((465.0, 435.0), True)])
def test_stated_near_order_and_shared_rail_reach_the_real_row(host, rename):
    case = _case(host=host, rename=rename)
    plan, ctx = _build(case)
    book = case[2]
    owner, low, high, left = ("IC7", "Z9", "A4", "M8") if rename else ("U1", "R1", "R2", "R3")
    row = _tip(plan, book, owner + ".CFG_B")[1]
    assert all(_tip(plan, book, part + ".1")[1] == row for part in (low, high, left))
    assert plan.part(high).x < plan.part(low).x
    assert plan.part(left).x - plan.part(owner).x == -70.0
    assert ctx.service_build_attempts == 2, "the preferred row must consume real GND column feedback"
    assert ctx.service_build_attempts <= ctx.budget.max_candidates


def test_reversing_intent_selects_the_other_natural_pin_row():
    case = _case(order=("R1", "R2"))
    built, failure, _violations = dc._build_candidate(case[3], dc._variants(case[3])[0])
    # The original geometry may refuse every matching row. It must then refuse
    # honestly rather than return the old high-row picture with reversed order.
    if built is not None:
        assert built.plan.part("R1").x < built.plan.part("R2").x
    else:
        assert failure is not None and "branchOrder" in failure.detail
    placed, failure = dc._place(case[3], dc._variants(case[3])[0], seat_service_groups=False)
    assert failure is None
    choices = dict(dc._service_group_row_choices(case[3], placed))
    assert dc._preferred_service_group_rows(case[3], placed) == [{
        "config-right": choices["config-right"][1],
        "boot-left": choices["boot-left"][1],
    }]


def test_reversed_intent_is_drawn_when_its_natural_row_is_physically_reachable():
    case = _case(order=("R1", "R2"), reverse_pin_rows=True)
    plan, _ctx = _build(case)
    row = _tip(plan, case[2], "U1.CFG_A")[1]
    assert all(_tip(plan, case[2], part + ".1")[1] == row for part in ("R1", "R2", "R3"))
    assert plan.part("R1").x < plan.part("R2").x


def test_branch_array_order_cannot_change_the_stated_reading():
    original = _case()
    plan, _ctx = _build(original)
    payload = original[1].to_jsonable()
    payload["serviceGroups"][0]["branches"].reverse()
    spec = PresentationSpec.from_dict(payload)
    context = _prepared(original[0], spec, original[2])
    context.budget = replace(context.budget, max_candidates=8)
    reordered, _ctx = _build((original[0], spec, original[2], context))
    # source.presentationSha256 names the intentionally reordered input;
    # every actual drawing object must remain identical.
    for field in ("parts", "segments", "labels", "power_symbols", "texts", "junctions"):
        assert getattr(plan, field) == getattr(reordered, field)


def test_no_statement_keeps_the_preexisting_success_byte_for_byte():
    from test_548j_joint_seats import _spec as historical_spec

    circuit, spec, book = _circuit(), historical_spec(), _book()
    ctx = _prepared(circuit, spec, book)
    original, failure, _notes = dc._build_one_variant(ctx, dc._variants(ctx)[0], [])
    assert original is not None, failure
    built, failure, _notes = dc._build_candidate(ctx, dc._variants(ctx)[0])
    assert built is not None, failure
    assert built.plan.to_jsonable() == original.plan.to_jsonable()
    assert ctx.service_build_attempts == 1


def test_a_pull_on_another_terminal_is_not_aligned_by_its_neighbour():
    circuit, spec, book, _ctx = _case()
    raw = circuit.to_jsonable()
    power = next(net for net in raw["nets"] if net["id"] == "PWR")
    power["members"].remove("R3.2")
    raw["nets"].append({"id": "OTHER", "class": "power", "members": ["R3.2"],
                        "provenance": "verified_recipe"})
    circuit = CircuitSpec.from_dict(raw)
    document = spec.to_jsonable()
    document["serviceGroups"][1]["branches"][0]["to"] = "OTHER"
    spec = PresentationSpec.from_dict(document)
    ctx = _prepared(circuit, spec, book)
    placed, failure = dc._place(ctx, dc._variants(ctx)[0], seat_service_groups=False)
    assert failure is None
    preferences = dc._preferred_service_group_rows(ctx, placed)
    assert preferences and all(set(row) == {"config-right"} for row in preferences)


def test_no_common_real_row_does_not_invent_a_shared_coordinate():
    circuit, spec, book, _ctx = _case()
    host = book["HOST8"]
    book["HOST8"] = replace(host, pins=[
        replace(pin, tip=(pin.tip[0], pin.tip[1] + 20.0))
        if pin.number in ("BOOT0", "BOOT1") else pin
        for pin in host.pins
    ])
    ctx = _prepared(circuit, spec, book)
    placed, failure = dc._place(ctx, dc._variants(ctx)[0], seat_service_groups=False)
    assert failure is None
    assert dc._preferred_service_group_rows(ctx, placed) == []


def test_pull_down_order_does_not_enable_the_pull_up_preference():
    circuit, spec, book, _ctx = _case()
    raw = circuit.to_jsonable()
    power = next(net for net in raw["nets"] if net["id"] == "PWR")
    ground = next(net for net in raw["nets"] if net["id"] == "GND")
    for member in ("R1.2", "R2.2", "R3.2"):
        power["members"].remove(member)
        ground["members"].append(member)
    circuit = CircuitSpec.from_dict(raw)
    document = spec.to_jsonable()
    for group in document["serviceGroups"][:2]:
        for branch in group["branches"]:
            branch["to"] = "GND"
    spec = PresentationSpec.from_dict(document)
    ctx = _prepared(circuit, spec, book)
    placed, failure = dc._place(ctx, dc._variants(ctx)[0], seat_service_groups=False)
    assert failure is None
    assert dc._preferred_service_group_rows(ctx, placed) == []
