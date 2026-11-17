"""548P54: real service builds may escape by one existing outward column.

Synthetic geometry: it proves the production search, not EasyEDA appearance.
The two right open ports leave the left GND/BOOT corridor to the actual seat.
"""
from dataclasses import replace
from functools import partial

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawcompiler as dc, readability
from test_548n_group_seat import _book, _pin, _prepared, _symbol


def _fixture(*, host=(400.0, 400.0)):
    book = _book()
    book["HOST6"] = SymbolProfile.from_dict(_symbol(
        "HOST6", [-25.5, -25.5, 25.5, 25.5], [
            _pin("GND", [-35.0, 15.0], "left"),
            _pin("BOOT0", [-35.0, 5.0], "left"),
            _pin("BOOT1", [-35.0, -5.0], "left"),
            _pin("RX", [35.0, -5.0], "right"),
            _pin("TX", [35.0, -15.0], "right"),
            _pin("VDD", [35.0, 15.0], "right"),
        ]))
    book["PWR-GND"] = SymbolProfile.from_dict(_symbol(
        "PWR-GND", [-10.5, 9.5, 10.5, 19.5], []))
    book["PWR-PWR"] = SymbolProfile.from_dict(_symbol(
        "PWR-PWR", [-5.5, 4.5, 5.5, 14.5], []))
    circuit = CircuitSpec.from_dict({
        "parts": [
            {"id": "U1", "symbolRef": "HOST6", "value": "HOST", "provenance": "ai_asserted"},
            {"id": "R3", "symbolRef": "R", "value": "10k", "provenance": "ai_asserted"},
        ],
        "nets": [
            {"id": name, "class": cls, "members": members, "provenance": "ai_asserted"}
            for name, cls, members in (
                ("BOOT", "signal", ["U1.BOOT0", "U1.BOOT1", "R3.1"]),
                ("PWR", "power", ["U1.VDD", "R3.2"]),
                ("GND", "gnd", ["U1.GND"]),
                ("RX", "signal", ["U1.RX"]),
                ("TX", "signal", ["U1.TX"]),
            )
        ],
    })
    spec = PresentationSpec.from_dict({
        "grammarRef": "ic-periphery",
        "modules": [{"id": "m", "parts": ["U1", "R3"], "core": "U1", "role": "host island"}],
        "serviceGroups": [{"id": "boot", "branches": [{"part": "R3", "from": "BOOT", "to": "PWR"}]}],
        "labelPolicy": {"local": "wire", "crossModule": "label", "highFanout": "label", "stubMin": 40.0},
        "textPlacement": "native-attr",
        "userLocks": [{"partId": "U1", "x": host[0], "y": host[1]}],
    })
    ctx = _prepared(circuit, spec, book)
    ctx.budget = replace(ctx.budget, max_candidates=8)
    return circuit, spec, book, ctx


@pytest.mark.parametrize("host", [(400.0, 400.0), (465.0, 435.0)])
def test_one_outward_column_reaches_the_complete_builder(host):
    circuit, spec, book, ctx = _fixture(host=host)
    built, failure, violations = dc._build_candidate(ctx, dc._variants(ctx)[0])
    assert built is not None, (failure, violations)
    assert ctx.service_build_attempts == 4
    assert len(built.series_trials) == 3
    assert all("GND" in trial for trial in built.series_trials)
    branch = built.plan.part("R3")
    owner = built.plan.part("U1")
    assert branch.x - owner.x == -70.0
    assert branch.y - owner.y == -25.0
    _assert_complete(circuit, spec, book, ctx, built.plan)


def _assert_complete(circuit, spec, book, ctx, plan):
    derived = readability.derive_netlist(plan, book)
    assert len(derived.pin_points) == len(derived.wired_pins) == 8
    for net in circuit.nets:
        for member in net.members:
            assert set(derived.group_of(member)) == set(net.members)
    assert any(flag.net == "GND" for flag in plan.power_symbols)
    checked = readability.check(plan, circuit, spec, book,
                                grammar_checker=partial(dc.check_grammar, budget=ctx.budget),
                                page_box=ctx.budget.page_box, grid=ctx.budget.grid)
    assert checked.ok
    assert not checked.grammar_findings


def test_refused_complete_build_cannot_move_the_next_columns_seed(monkeypatch):
    circuit, spec, book, ctx = _fixture()
    original = dc._build_service_group_variant
    hosts = []

    def measured(context, variant, placed):
        hosts.append(placed.origins["U1"])
        result = original(context, variant, placed)
        if result[0] is None:
            # Keep the actual failed verdict; poison only its disposable input.
            placed.origins["U1"] = (99999.0, 99999.0)
        return result

    monkeypatch.setattr(dc, "_build_service_group_variant", measured)
    built, failure, violations = dc._build_candidate(ctx, dc._variants(ctx)[0])
    assert built is not None, (failure, violations)
    assert hosts == [(400.0, 400.0)] * 4
    _assert_complete(circuit, spec, book, ctx, built.plan)


def test_complete_build_budget_can_stop_before_the_new_column():
    _circuit, _spec, _book, ctx = _fixture()
    ctx.budget = replace(ctx.budget, max_candidates=3)
    for variant in dc._variants(ctx):
        built, failure, _violations = dc._build_candidate(ctx, variant)
        assert built is None and failure is not None
    assert ctx.service_build_attempts == 3


def test_existing_success_keeps_its_original_plan(monkeypatch):
    from test_548j_joint_seats import _book as old_book
    from test_548j_joint_seats import _circuit as old_circuit
    from test_548j_joint_seats import _prepared as old_context
    from test_548j_joint_seats import _spec as old_spec

    circuit, spec, book = old_circuit(), old_spec(), old_book()
    ctx = old_context(circuit, spec, book)
    original, failure, _notes = dc._build_one_variant(ctx, dc._variants(ctx)[0], [])
    assert original is not None, failure

    def unexpected(*args, **kwargs):
        raise AssertionError("old success must not enumerate column combinations")

    monkeypatch.setattr(dc, "_joint_lane_combinations", unexpected)
    built, failure, _notes = dc._build_candidate(ctx, dc._variants(ctx)[0])
    assert built is not None, failure
    assert built.plan.to_jsonable() == original.plan.to_jsonable()
    assert ctx.service_build_attempts == 1


def test_missing_and_empty_groups_keep_the_ordinary_path(monkeypatch):
    circuit, spec, book, _ctx = _fixture()
    payload = spec.to_jsonable()
    payload.pop("serviceGroups")
    absent = PresentationSpec.from_dict(payload)
    empty = PresentationSpec.from_dict({**payload, "serviceGroups": []})

    def unexpected(*args, **kwargs):
        raise AssertionError("no groups must not enumerate service columns")

    monkeypatch.setattr(dc, "_joint_lane_combinations", unexpected)
    results = []
    for document in (absent, empty):
        context = _prepared(circuit, document, book)
        built, failure, _notes = dc._build_candidate(context, dc._variants(context)[0])
        assert context.service_build_attempts == 0
        results.append(built.plan.to_jsonable() if built else failure)
    assert results[0] == results[1]
