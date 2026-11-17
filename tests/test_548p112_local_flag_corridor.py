"""548P112/P115: a local flag is repaired only after the original compile fails.

The refused run is not a permanent wall: ``_final_joint_rails`` already replaces
it after the local flag exists. The post-search repair sees exactly that same
replaceable set, keeps the flag inside the stated page, and leaves every page
that already compiles on its original path.
"""

from __future__ import annotations

from boardwise.engines import drawcompiler as dc
from test_548n_group_seat import (
    _book,
    _budget,
    _circuit,
    _prepared,
    _spec,
    _tip,
)

PAGE = (0.0, 0.0, 1170.0, 825.0)
TOLERANCE = 1e-6


def _legs(points):
    return list(zip(points, points[1:]))


def _foreign_legs(plan, net_id):
    for segment in plan.segments:
        if segment.net == net_id:
            continue
        points = dc._compress([tuple(point) for point in segment.points])
        yield from (
            (segment.net, start, stop) for start, stop in _legs(points)
        )


def test_post_search_repair_keeps_one_near_independent_gnd_flag_inside_page():
    circuit, spec, book = _circuit(), _spec(), _book()
    result = dc.compile(circuit, spec, book, _budget())
    assert result.ok, [item.detail for item in result.failures]
    assert any("local_flag_repair_attempts=1" in note for note in result.notes)
    plan = result.best()
    assert plan is not None

    flags = [item for item in plan.power_symbols if item.net == "GND"]
    assert len(flags) == 1, [item.net for item in plan.power_symbols]
    flag = flags[0]
    tip = _tip(plan, book, "U1.GND")
    anchor = (float(flag.x), float(flag.y))
    assert abs(anchor[0] - tip[0]) <= TOLERANCE, (tip, anchor)
    assert 0.0 < abs(anchor[1] - tip[1]) <= (
        dc.FLAG_LEAD_LIMIT + 2.0 * dc.GAP + TOLERANCE)

    gnd_runs = [segment for segment in plan.segments if segment.net == "GND"]
    assert len(gnd_runs) == 1
    lead = dc._compress([tuple(point) for point in gnd_runs[0].points])
    assert lead and lead[0] == tip and lead[-1] == anchor
    assert all(abs(point[0] - tip[0]) <= TOLERANCE for point in lead)

    glyph = dc.flag_glyph_box(
        book[flag.symbol_ref], rotation=flag.rotation, anchor=anchor)
    assert glyph is not None
    assert PAGE[0] <= glyph[0] <= glyph[2] <= PAGE[2]
    assert PAGE[1] <= glyph[1] <= glyph[3] <= PAGE[3]
    assert all(
        PAGE[0] <= point[0] <= PAGE[2]
        and PAGE[1] <= point[1] <= PAGE[3]
        for point in lead
    )
    for net_id, start, stop in _foreign_legs(plan, "GND"):
        assert not dc._segment_hits_box(start, stop, glyph), (
            f"{net_id} run {start}->{stop} stands in the GND glyph {glyph}")
        for first, second in _legs(lead):
            assert dc._proper_crossing(first, second, start, stop) is None
            assert not dc._collinear_overlap(first, second, start, stop)
            assert not dc._strictly_on_segment(start, first, second)
            assert not dc._strictly_on_segment(first, start, stop)


def test_repair_filters_exactly_the_runs_final_pass_replaces(monkeypatch):
    circuit, spec, book = _circuit(), _spec(), _book()
    ctx = _prepared(circuit, spec, book)
    placed, failure = dc._place(ctx, dc._variants(ctx)[0])
    assert failure is None, failure.detail
    expected = set()
    trunks = set()
    for record in placed.service_group_plans:
        for rail in record.rails:
            trunks.add((rail.net, rail.runs[0]))
            replaceable = dc._replaceable_host_runs(ctx, record, rail, placed)
            assert all(run in rail.runs[1:] for run in replaceable)
            assert rail.runs[0] not in replaceable
            expected.update((rail.net, run) for run in replaceable)
    assert expected

    calls = {}
    page_boxes = {}
    original = dc._joint_local_flag

    def spy(context, net_id, cls, part_id, token, point, placement,
            occupied, solids, segments, symbols, texts=(), page_box=None):
        if part_id == "U1" and token == "GND":
            mode = "repair" if context.local_flag_repair_active else "original"
            calls.setdefault(mode, {
                (segment.net, tuple(segment.points)) for segment in segments
            })
            page_boxes.setdefault(mode, page_box)
        return original(
            context, net_id, cls, part_id, token, point, placement,
            occupied, solids, segments, symbols, texts, page_box=page_box)

    monkeypatch.setattr(dc, "_joint_local_flag", spy)
    result = dc.compile(circuit, spec, book, _budget())
    assert result.ok, [item.detail for item in result.failures]
    assert set(calls) == {"original", "repair"}, calls.keys()
    assert expected < calls["original"]
    assert calls["original"] - expected == calls["repair"]
    assert expected.isdisjoint(calls["repair"])
    assert trunks <= calls["repair"]
    assert page_boxes == {"original": None, "repair": PAGE}

    final = {
        (segment.net, tuple(segment.points))
        for segment in result.best().segments
    }
    assert expected.isdisjoint(final)


def test_an_existing_success_never_calls_post_search_repair(monkeypatch):
    from test_548p54_service_columns import _fixture

    circuit, spec, book, ctx = _fixture()
    def unexpected(*args, **kwargs):
        raise AssertionError("an original success must not enter the repair")

    monkeypatch.setattr(dc, "_try_local_flag_repair", unexpected)
    result = dc.compile(circuit, spec, book, ctx.budget)
    assert result.ok, [item.detail for item in result.failures]
    assert not any("local_flag_repair_attempts" in note for note in result.notes)


def test_no_service_groups_never_calls_post_search_repair(monkeypatch):
    calls = []
    original = dc._try_local_flag_repair

    def spy(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(dc, "_try_local_flag_repair", spy)
    result = dc.compile(_circuit(), _spec(groups=[]), _book(), _budget())
    assert result.ok, [item.detail for item in result.failures]
    assert calls == []
