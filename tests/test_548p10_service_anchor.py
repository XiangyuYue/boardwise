"""548P10: the existing page anchor consumes the complete service-seat bounds."""

from __future__ import annotations

import copy
from dataclasses import replace

import pytest

from boardwise.engines import drawcompiler as dc
from boardwise.engines import readability
from test_548n_group_seat import _tip
from test_548p6_service_feedback import _assert_connected, _fixture


def _recorded_build(monkeypatch, *, locked=False):
    circuit, spec, book, ctx = _fixture(locked=locked)
    ctx.budget = replace(ctx.budget, max_candidates=3)
    anchors = []
    original = dc._anchor_seats_to_page

    def measured_anchor(context, placed):
        before = copy.deepcopy(placed)
        original(context, placed)
        anchors.append((before, copy.deepcopy(placed)))

    monkeypatch.setattr(dc, "_anchor_seats_to_page", measured_anchor)
    built, failure, violations = dc._build_candidate(ctx, dc._variants(ctx)[0])
    return circuit, spec, book, ctx, built, failure, violations, anchors


def _coordinates(placed):
    """Read coordinates independently; do not use the production shift helpers."""
    for part, point in sorted(placed.origins.items()):
        yield f"origin {part}", point
    for record in placed.service_group_plans:
        yield f"frame {record.group_id} low", record.frame[:2]
        yield f"frame {record.group_id} high", record.frame[2:]
        for index, path in enumerate(record.host_paths):
            for vertex, point in enumerate(path):
                yield f"group path {index}/{vertex}", point
        for cell in record.cells:
            for name in ("origin", "from_seat", "to_seat"):
                yield f"cell {cell.part_id} {name}", getattr(cell, name)
            for index, path in enumerate(cell.host_paths):
                for vertex, point in enumerate(path):
                    yield f"cell path {cell.part_id}/{index}/{vertex}", point
            for kind, text, box in cell.text_boxes:
                yield f"text {cell.part_id}/{kind}/{text} low", box[:2]
                yield f"text {cell.part_id}/{kind}/{text} high", box[2:]
        for rail in record.rails:
            yield f"rail {rail.net} anchor", rail.anchor
            yield f"rail {rail.net} glyph low", rail.flag_box[:2]
            yield f"rail {rail.net} glyph high", rail.flag_box[2:]
            for name, runs in (("run", rail.runs), ("lead", (rail.lead,))):
                for index, run in enumerate(runs):
                    for vertex, point in enumerate(run):
                        yield f"rail {rail.net}/{name}/{index}/{vertex}", point
    for port in placed.service_group_ports:
        for index, point in enumerate(port.run):
            yield f"port {port.net}/{index}", point
        yield f"port {port.net} label anchor", (port.label.x, port.label.y)
        yield f"port {port.net} label low", port.label.bbox[:2]
        yield f"port {port.net} label high", port.label.bbox[2:]


def _inside(box, page):
    assert box[0] >= page[0] and box[1] >= page[1], box
    assert box[2] <= page[2] and box[3] <= page[3], box


def test_unlocked_page_builds_with_real_names_inside_the_margin(monkeypatch):
    circuit, spec, book, ctx, built, failure, violations, anchors = _recorded_build(monkeypatch)
    assert built is not None, (failure, violations)
    plan = built.plan
    _assert_connected(circuit, book, plan)
    derived = readability.derive_netlist(plan, book)
    assert len(derived.pin_points) == 9
    assert ctx.service_build_attempts <= 3
    inner = (ctx.budget.page_box[0] + dc.PAGE_MARGIN,
             ctx.budget.page_box[1] + dc.PAGE_MARGIN,
             ctx.budget.page_box[2] - dc.PAGE_MARGIN,
             ctx.budget.page_box[3] - dc.PAGE_MARGIN)
    seated = anchors[-1][1]
    for record in seated.service_group_plans:
        _inside(record.frame, inner)
    names = []
    for index, flag in enumerate(plan.power_symbols):
        glyph = readability._flag_glyph_box(book, flag)
        name = readability._flag_name_row(plan, book, index, flag, glyph)
        if name is not None:
            names.append(name)
            _inside(name, inner)
    assert names, "the regression must measure the actual printed PWR name"
    port = next(port for port in seated.service_group_ports if port.net == "TX")
    assert port.run[0] == _tip(plan, book, "U1.TX")
    assert any(segment.net == "TX" and tuple(segment.points) == port.run
               for segment in plan.segments)
    checked = readability.check(plan, circuit, spec, book,
                                page_box=ctx.budget.page_box, grid=ctx.budget.grid)
    assert not checked.hard_violations


def test_every_record_and_port_moves_by_the_origins_one_delta(monkeypatch):
    _circuit, _spec, _book, _ctx, _built, _failure, _violations, anchors = _recorded_build(monkeypatch)
    before, after = anchors[-1]
    delta = tuple(after.origins["U1"][axis] - before.origins["U1"][axis]
                  for axis in (0, 1))
    assert delta != (0.0, 0.0), "a high real flag name must cause an inward move"
    old_coordinates = list(_coordinates(before))
    new_coordinates = list(_coordinates(after))
    assert len(old_coordinates) == len(new_coordinates)
    for (old_name, old), (new_name, new) in zip(old_coordinates, new_coordinates):
        assert new_name == old_name
        assert new == pytest.approx((old[0] + delta[0], old[1] + delta[1])), old_name
    assert before.poses == after.poses
    assert [cell.pose for record in before.service_group_plans for cell in record.cells] == [
        cell.pose for record in after.service_group_plans for cell in record.cells]


def test_a_locked_service_page_keeps_every_coordinate(monkeypatch):
    _circuit, _spec, _book, _ctx, built, failure, _violations, anchors = _recorded_build(
        monkeypatch, locked=True)
    assert built is not None, failure
    assert anchors
    for before, after in anchors:
        assert after == before
        assert after.origins["U1"] == (300.0, 400.0)


def test_missing_groups_keep_the_original_placement_and_empty_extra_is_default():
    _circuit, _spec, _book, ctx = _fixture(groups=False, locked=False)
    variant = dc._variants(ctx)[0]
    original, failure = dc._place_chain_and_shelf(ctx, variant)
    assert original is not None, failure
    ordinary, failure = dc._place(ctx, variant)
    assert ordinary == original, failure
    explicit = copy.deepcopy(original)
    implicit = copy.deepcopy(original)
    dc._anchor_to_page(ctx, explicit.origins, explicit.poses, explicit.residue,
                       extra_boxes=())
    dc._anchor_to_page(ctx, implicit.origins, implicit.poses, implicit.residue)
    assert explicit == implicit
