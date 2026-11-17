"""548P18: final service geometry replaces provisional host-to-rail runs."""

from __future__ import annotations

import copy
import math

import pytest

from boardwise.engines import drawcompiler as dc
from test_548p14_rail_entry import _assert_canonical_connectivity, _fixture


def _seated(*, second_supply=False):
    case = _fixture(second_supply=second_supply)
    circuit, spec, book, ctx, variant, placed = case
    refusal = dc._seat_service_groups(ctx, placed, row_offsets={"config": 80.0})
    assert refusal is None, refusal
    return case


@pytest.mark.parametrize("second_supply", [False, True])
def test_final_geometry_replaces_the_old_detour_with_one_short_run(second_supply):
    circuit, _spec, book, ctx, variant, placed = _seated(second_supply=second_supply)
    before = copy.deepcopy(placed)
    built, failure, violations = dc._build_one_variant(ctx, variant, [], placement_override=placed)
    assert built is not None, (failure, violations)
    _assert_canonical_connectivity(circuit, book, built.plan)
    assert not built.checked.hard_violations
    start = dc._pin_point(ctx, "U1", "VDD", placed.poses, placed.origins)
    expected = (start, (start[0], 460.0), (365.0, 460.0))
    runs = [tuple(segment.points) for segment in built.plan.segments
            if segment.net == "PWR" and segment.points[0] == start]
    assert runs == [expected], "replace the provisional route; do not keep a parallel detour"
    assert sum(math.dist(a, b) for a, b in zip(runs[0], runs[0][1:])) == 45.0
    final = next(record for record in placed.service_group_plans if record.group_id == "config")
    old = next(record for record in before.service_group_plans if record.group_id == "config")
    assert expected in final.rails[0].runs
    assert len(final.rails[0].runs) == len(old.rails[0].runs)
    assert final.rails[0].runs[:2] == old.rails[0].runs[:2]
    assert placed.origins == before.origins and placed.poses == before.poses
    assert final.cells == old.cells
    assert [(rail.anchor, rail.rotation, rail.flag_box) for rail in final.rails] == [
        (rail.anchor, rail.rotation, rail.flag_box) for rail in old.rails]
    assert final.notes[0] in built.plan.notes
    assert final.notes[0] in violations
    if second_supply:
        second = dc._pin_point(ctx, "U1", "VDD2", placed.poses, placed.origins)
        assert sum(run[0] == second for run in final.rails[0].runs) == 1


def test_final_printed_wall_is_consumed_and_failed_build_keeps_records(monkeypatch):
    _circuit, _spec, _book, ctx, variant, placed = _seated()
    before = copy.deepcopy(placed)
    original = dc._part_texts
    wall = (340.0, 450.0, 380.0, 470.0)
    routes = []
    original_route = dc._Router.route

    def printed_wall(*args, **kwargs):
        texts, refusal = original(*args, **kwargs)
        assert refusal is None
        return [*texts, dc.LayoutText(kind="value", text="FINAL WALL", bbox=wall, part_id="U1")], None

    def observe(router, start, end, *args, **kwargs):
        result = original_route(router, start, end, *args, **kwargs)
        if start == (350.0, 430.0):
            routes.append((end, tuple(router.boxes), result))
        return result

    monkeypatch.setattr(dc, "_part_texts", printed_wall)
    monkeypatch.setattr(dc._Router, "route", observe)
    built, failure, violations = dc._build_one_variant(ctx, variant, [], placement_override=placed)
    assert routes, "the final printed row must reach the original route consumer"
    assert all(wall in boxes for _end, boxes, _path in routes)
    assert routes[0][0] == (365.0, 460.0) and routes[0][2] is None
    for _end, _boxes, path in routes:
        if path is not None:
            assert not any(dc._segment_hits_box(a, b, wall) for a, b in zip(path, path[1:]))
    assert built is None and failure is not None
    assert placed == before, "a later full-gate refusal must not commit replacement records"


def test_final_foreign_copper_stays_a_wall(monkeypatch):
    _circuit, _spec, _book, ctx, variant, placed = _seated()
    original = dc._Router.route
    observed = []

    def route(router, start, end, *args, **kwargs):
        result = original(router, start, end, *args, **kwargs)
        if start == (350.0, 430.0):
            observed.append((tuple(router.edge_nets), result))
        return result

    monkeypatch.setattr(dc._Router, "route", route)
    built, failure, violations = dc._build_one_variant(ctx, variant, [], placement_override=placed)
    assert built is not None, (failure, violations)
    assert observed and all("CFG_A" in nets and "CFG_B" in nets for nets, _route in observed)


def test_no_group_page_does_not_enter_final_rail_consumer(monkeypatch):
    from test_548p6_service_feedback import _fixture as plain_fixture

    def unexpected(*args, **kwargs):
        raise AssertionError("no service groups must keep the ordinary builder")

    monkeypatch.setattr(dc, "_final_joint_rails", unexpected, raising=False)
    _circuit, _spec, _book, ctx = plain_fixture(groups=False)
    dc._build_candidate(ctx, dc._variants(ctx)[0])
