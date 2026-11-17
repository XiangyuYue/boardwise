"""548P6: real service rows are tried only after a complete build refuses."""

from __future__ import annotations

import copy
import math
from dataclasses import replace

import pytest

from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawcompiler as dc
from boardwise.engines import readability
from test_548n_group_seat import (
    _book, _circuit, _document, _groups, _pin, _prepared, _symbol, _tip,
)


def _fixture(groups=True, *, trapped_ground=True, locked=True):
    circuit, book = _circuit(), _book()
    # The low signal row traps the host's ground between the TX stub above and
    # the config tracks below. Real config-pin rows leave its lower hang free.
    book["HOST4"] = SymbolProfile.from_dict(_symbol(
        "HOST4", [-40.0, -40.0, 40.0, 40.0], [
            _pin("VDD", [50.0, 30.0], "right"),
            _pin("CFG_A", [50.0, 20.0], "right"),
            _pin("CFG_B", [50.0, 10.0], "right"),
            _pin("TX", [50.0, -25.0], "right"),
            (_pin("GND", [50.0, -35.0], "right") if trapped_ground
             else _pin("GND", [0.0, 50.0], "up")),
        ]))
    payload = _document(_groups() if groups else None)
    payload["partTexts"] = {"U1": "below"}
    if locked:
        # Isolate row selection from the separately recorded page-anchor gap:
        # the original anchor does not include a high service rail's name row.
        payload["userLocks"] = [{"partId": "U1", "x": 300.0, "y": 400.0}]
    spec = PresentationSpec.from_dict(payload)
    return circuit, spec, book, _prepared(circuit, spec, book)


def _assert_connected(circuit, book, plan):
    derived = readability.derive_netlist(plan, book)
    for net in circuit.nets:
        for member in net.members:
            assert set(derived.group_of(member)) == set(net.members)
    assert set(derived.pin_points) == set(derived.wired_pins)
    assert {text.part_id for text in plan.texts} == {part.id for part in circuit.parts}
    assert any(flag.net == "GND" for flag in plan.power_symbols)


def _assert_short_paths(plan, book, near_part, near_token):
    row = _tip(plan, book, f"U1.{near_token}")[1]
    assert _tip(plan, book, "R1.1")[1] == row
    assert _tip(plan, book, "R2.1")[1] == row
    far_part = "R2" if near_part == "R1" else "R1"
    assert _tip(plan, book, f"{near_part}.1")[0] < _tip(
        plan, book, f"{far_part}.1")[0]
    for part, token in (("R1", "CFG_A"), ("R2", "CFG_B")):
        start, stop = _tip(plan, book, f"U1.{token}"), _tip(plan, book, f"{part}.1")
        paths = [segment.points for segment in plan.segments if segment.net == token]
        length = sum(math.dist(first, second) for path in paths
                     for first, second in zip(path, path[1:]))
        assert length == abs(stop[0] - start[0]) + abs(stop[1] - start[1])


@pytest.mark.parametrize("max_candidates", [2, 3, 4])
def test_real_pin_row_survives_the_complete_builder(max_candidates):
    circuit, spec, book, ctx = _fixture()
    ctx.budget = replace(ctx.budget, max_candidates=max_candidates)
    built, failure, violations = dc._build_candidate(ctx, dc._variants(ctx)[0])
    assert ctx.service_build_attempts == min(max_candidates, 3)
    assert ctx.service_build_attempts <= max_candidates
    if max_candidates == 2:
        assert built is None and failure is not None
        assert "GND" in failure.detail
        return
    assert built is not None, (failure, violations)
    _assert_connected(circuit, book, built.plan)
    assert sum(flag.net == "GND" for flag in built.plan.power_symbols) == 1
    _assert_short_paths(built.plan, book, "R1", "CFG_A")
    checked = readability.check(
        built.plan, circuit, spec, book, page_box=ctx.budget.page_box,
        grid=ctx.budget.grid)
    assert not checked.hard_violations


def test_whole_build_feedback_reaches_a_later_row_without_leaking(monkeypatch):
    # Use the already successful 548J page: the N fixture's first real pin row
    # is separately refused by VDD routing, so it cannot supply two legal rows.
    from test_548j_joint_seats import _book as joint_book
    from test_548j_joint_seats import _circuit as joint_circuit
    from test_548j_joint_seats import _prepared as joint_context
    from test_548j_joint_seats import _spec as joint_spec

    circuit, book = joint_circuit(), joint_book()
    payload = joint_spec().to_jsonable()
    payload["userLocks"] = [{"partId": "U1", "x": 400.0, "y": 400.0}]
    spec = PresentationSpec.from_dict(payload)
    ctx = joint_context(circuit, spec, book)
    original = dc._build_service_group_variant
    trials = []
    refused_legal_row = False

    def measured_build(context, variant, placed):
        nonlocal refused_legal_row
        snapshot = copy.deepcopy(placed)
        result = original(context, variant, placed)
        trials.append((snapshot, result[0] is not None, result[1]))
        if result[0] is None:
            # A failed full build may have written local state. The next row
            # still has to start from the original, unanchored placement.
            placed.origins["U1"] = (99999.0, 99999.0)
            return result
        if not refused_legal_row:
            refused_legal_row = True
            placed.origins["U1"] = (99999.0, 99999.0)
            return None, dc._joint_refusal(
                "$.serviceGroups", "test gate refuses the first legal row",
                "try the remaining real pin row"), []
        return result

    monkeypatch.setattr(dc, "_build_service_group_variant", measured_build)
    built, failure, violations = dc._build_candidate(ctx, dc._variants(ctx)[0])
    assert built is not None, (failure, violations)
    assert len(trials) >= 2
    assert trials[0][1] is True and trials[-1][1] is True
    assert all(item[0].origins["U1"] == (400.0, 400.0) for item in trials)
    first_rows = [record.cells[0].from_seat[1]
                  for record in trials[0][0].service_group_plans]
    final_rows = [record.cells[0].from_seat[1]
                  for record in trials[-1][0].service_group_plans]
    assert final_rows != first_rows
    _assert_connected(circuit, book, built.plan)
    assert len(trials) <= ctx.budget.max_candidates


def test_complete_build_budget_is_shared_across_variants(monkeypatch):
    _circuit, _spec, _book, ctx = _fixture()
    # Isolate the shared budget from the number of legal row/column candidates:
    # one seed and its outward column leave complete builds for another variant.
    monkeypatch.setattr(dc, "_service_group_row_choices", lambda *_args: [])
    original = dc._build_service_group_variant
    builds = []

    def refuse_after_measuring(context, variant, placed):
        result = original(context, variant, placed)
        builds.append((variant.label, result[0] is not None))
        return None, dc._joint_refusal(
            "$.serviceGroups", "test gate keeps this complete candidate refused",
            "respect the original complete build budget"), []

    monkeypatch.setattr(dc, "_build_service_group_variant", refuse_after_measuring)
    variants = dc._variants(ctx)
    for variant in [*variants, *variants]:
        built, failure, _notes = dc._build_candidate(ctx, variant)
        assert built is None and failure is not None
    assert len(builds) == ctx.budget.max_candidates
    assert len({label for label, _success in builds}) > 1


def test_missing_or_empty_groups_never_generate_row_alternatives(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("a page without service groups must not retry rows")

    monkeypatch.setattr(dc, "_service_group_row_choices", unexpected, raising=False)
    circuit, spec, book, ctx = _fixture(groups=False)
    absent = dc._build_candidate(ctx, dc._variants(ctx)[0])
    empty_spec = PresentationSpec.from_dict({**spec.to_jsonable(), "serviceGroups": []})
    empty_ctx = _prepared(circuit, empty_spec, book)
    empty = dc._build_candidate(empty_ctx, dc._variants(empty_ctx)[0])
    assert (absent[0] is None) == (empty[0] is None)
    if absent[0] is not None:
        assert absent[0].plan.geometry_sha256() == empty[0].plan.geometry_sha256()
    else:
        assert absent[1] == empty[1]


def test_an_existing_success_does_not_generate_row_alternatives(monkeypatch):
    from test_548j_joint_seats import _book as joint_book
    from test_548j_joint_seats import _circuit as joint_circuit
    from test_548j_joint_seats import _prepared as joint_context
    from test_548j_joint_seats import _spec as joint_spec

    circuit, spec, book = joint_circuit(), joint_spec(), joint_book()
    ctx = joint_context(circuit, spec, book)
    original, failure, _notes = dc._build_one_variant(ctx, dc._variants(ctx)[0], [])
    assert original is not None, failure

    def unexpected(*args, **kwargs):
        raise AssertionError("a successful old build must return immediately")

    monkeypatch.setattr(dc, "_service_group_row_choices", unexpected, raising=False)
    built, failure, _notes = dc._build_candidate(ctx, dc._variants(ctx)[0])
    assert built is not None, failure
    assert built.plan.to_jsonable() == original.plan.to_jsonable()
