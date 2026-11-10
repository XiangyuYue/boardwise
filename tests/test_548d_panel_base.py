"""548D3X3C（33C2）：drawcompiler 的 panel 模板与 base 消费者。

本批只在 `drawcompiler.py` 里接一个集成点：由合法 `panelGroups` 生成与 33C1 相同的
`placement.PanelSeatTemplate`，base 在 series 之后、anchor 之前用**同一** binder 绑定并
seat，`_Placement` 携带计划；topology 请求消费同一模板并复核。最终 route/text/flag 不在
本批。测试走既有内部入口（`grammar.bind` + `dc._prepare`），不要求整张 LayoutPlan 通过。
"""

from __future__ import annotations

import copy
import dataclasses

import pytest

import test_053b_drawcompiler as b053
import test_548d_panel_placement as p33
import test_548d_panel_validation as p32

from boardwise.core.presentationspec import PresentationSpec, UserLock
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawcompiler as dc
from boardwise.engines import placement
from boardwise.engines.grammar.base import GrammarFailure


def _presentation(panels=None, modules=None) -> PresentationSpec:
    payload = {
        "grammarRef": "ic-periphery",
        "sidePreferences": {"input": "right", "output": "right", "load": "right",
                            "source": "left", "power": "top", "gnd": "bottom"},
        "modules": modules if modules is not None else [{
            "id": "mcu", "parts": list(p32._MCU_PARTS), "role": "host island",
            "grammarRef": "ic-periphery", "core": "U1",
        }],
    }
    if panels is not None:
        payload["panelGroups"] = panels
    return PresentationSpec.from_dict(payload)


def _panel_payload(**overrides) -> dict:
    entry = {
        "id": "keys", "side": "bottom", "columns": 2,
        "branches": [
            {"from": f"KEY{i}", "to": "3V3", "part": f"S{i}"}
            for i in range(1, 5)
        ],
    }
    entry.update(overrides)
    return entry


def _context(panels=None, modules=None) -> dc._Context:
    circuit = p32.CircuitSpec.from_dict({
        "parts": copy.deepcopy(p32._parts()),
        "nets": copy.deepcopy(p32._nets()),
    })
    presentation = _presentation(panels, modules)
    book = p32._book()
    # The terminal is a rail, so the library must carry its flag symbol — the
    # template reserves the flag's room from `_flag_seats`, not from air.
    book["PWR-3V3"] = SymbolProfile(
        symbol_ref="PWR-3V3", title="PWR-3V3", body=(-6.0, 0.0, 6.0, 18.0), pins=[])
    # And the ground, from the same library 053/056 use: without the real glyph
    # the page falls back to a wire for GND and the "trunk" is not a drawing
    # decision but a missing symbol.
    book["PWR-GND"] = b053.flag("PWR-GND")
    binding = dc.bind_grammar(circuit, presentation, book)
    assert binding.ok, [item.detail for item in binding.failures]
    binding = dc._with_panel_groups(binding, presentation, circuit)
    prepared = dc._prepare(
        circuit, presentation, binding, book,
        dc.CompileBudget(max_candidates=4),
    )
    assert prepared.context is not None, [f.detail for f in prepared.failures]
    return prepared.context


def _base(ctx):
    """The first ladder variant that produces a placement (the compile's own walk)."""
    first = None
    for variant in dc._variants(ctx):
        placed, failure = dc._place_chain_and_shelf(ctx, variant)
        if failure is None:
            return placed, None
        if first is None:
            first = failure
    return None, first


# ============================================== 1. base：真实 2×2 + 计划

def test_the_base_layout_carries_a_two_by_two_panel_and_no_mismatch():
    ctx = _context([_panel_payload()])
    placed, failure = _base(ctx)
    assert failure is None, failure.detail if failure else ""
    assert isinstance(placed, dc._Placement)
    assert len(placed.panel_plans) == 1
    plan = placed.panel_plans[0]
    assert plan.seated, plan.refusal
    assert plan.mismatches(placed.origins, placed.poses) == ()

    xs = sorted({round(cell.origin[0], 6) for cell in plan.cells})
    ys = sorted({round(cell.origin[1], 6) for cell in plan.cells})
    assert len(xs) == 2 and len(ys) == 2, (xs, ys)
    for value in xs:
        assert sum(1 for c in plan.cells if round(c.origin[0], 6) == value) == 2
    for value in ys:
        assert sum(1 for c in plan.cells if round(c.origin[1], 6) == value) == 2
    for cell in plan.cells:
        assert placed.origins[cell.part_id] == cell.origin
        assert placed.poses[cell.part_id] == cell.pose
        assert cell.from_seat[1] > cell.to_seat[1]


def test_the_base_and_the_topology_request_share_one_template():
    ctx = _context([_panel_payload()])
    templates, failure = dc._panel_templates(
        ctx, (0.0, 0.0), tuple(sorted(ctx.slots)))
    assert failure is None and len(templates) == 1
    request = dc._topology_request(ctx)
    assert request.panel_templates == templates, (
        "base and topology must consume the same conversion, not two grids")
    assert request.panel_templates[0].columns == 2
    assert request.panel_templates[0].side == "bottom"


def test_the_topology_placement_carries_a_seated_two_by_two_panel():
    """A named refusal is not the pass condition: the search must seat the panel.

    A refused plan is a hard cost (`panel-plan:<id>`) in the search, so the
    answer cannot be one where the panel was quietly dropped.
    """
    ctx = _context([_panel_payload()])
    answer = dc._topology_placement(ctx)
    assert not isinstance(answer, GrammarFailure), (
        "the topology search refused the panel: " + answer.detail)
    assert isinstance(answer, dc._Placement)
    assert answer.panel_plans, "the topology consumer dropped its panel plans"
    plan = answer.panel_plans[0]
    assert plan.seated, plan.refusal
    assert plan.mismatches(answer.origins, answer.poses) == ()
    xs = sorted({cell.origin[0] for cell in plan.cells})
    ys = sorted({cell.origin[1] for cell in plan.cells})
    assert len(xs) == 2 and len(ys) == 2, (xs, ys)
    for cell in plan.cells:
        assert answer.origins[cell.part_id] == cell.origin
        assert answer.poses[cell.part_id] == cell.pose
    # No residual panel problem is left on the winning answer: every plan is
    # seated and matches, which is what the hard terms were pricing.
    assert all(item.seated for item in answer.panel_plans)
    assert not [
        line for item in answer.panel_plans
        for line in item.mismatches(answer.origins, answer.poses)
    ]


def test_a_refused_panel_plan_is_a_hard_cost_not_a_zero():
    """The negative: an un-seated plan must price the candidate, not vanish."""
    ctx = _context([_panel_payload()])
    templates, failure = dc._panel_templates(
        ctx, (0.0, 0.0), tuple(sorted(ctx.slots)))
    assert failure is None and templates
    sealed = dataclasses.replace(templates[0], side="top")
    poses = {part: ctx.accepted[part][0]
             for part in ["U1", "S1", "S2", "S3", "S4"]}
    request = dc._series_placement_request(ctx, (), poses)
    request = dataclasses.replace(request, panel_templates=(sealed,))
    plans = placement.bind_panel_plans(request, {"U1": (0.0, 0.0)}, {})
    assert plans and not plans[0].seated and plans[0].refusal is not None
    terms = placement._panel_reservation_terms(  # noqa: SLF001 - the term under test
        request, {"U1": (0.0, 0.0, 1.0, 1.0)}, plans)
    hard = [term for term in terms if term.hard and term.name.startswith("panel-plan:")]
    assert hard and hard[0].value > 0.0
    assert plans[0].refusal.render() in hard[0].detail


# ============================================== 2. 负例（具名，不抛）

def test_a_side_other_than_bottom_is_refused_before_any_binding():
    ctx = _context([_panel_payload(side="top")])
    placed, failure = _base(ctx)
    assert placed is None and failure is not None
    assert failure.category == "layout-unsat"
    assert "bottom" in (failure.detail + failure.action)
    assert "'top'" in failure.detail


def test_a_locked_panel_part_is_refused_by_name():
    ctx = _context([_panel_payload()])
    ctx.presentation.user_locks = [UserLock(part_id="S1", x=5000.0, y=5000.0)]
    placed, failure = _base(ctx)
    assert placed is None and failure is not None
    assert "user lock" in failure.detail


def test_a_page_anchor_that_drifts_a_cell_is_refused(monkeypatch):
    real = dc._anchor_to_page

    def drifting(ctx, origins, poses, residue):
        real(ctx, origins, poses, residue)
        moved = origins["S1"]
        origins["S1"] = (moved[0] + 20.0, moved[1])

    monkeypatch.setattr(dc, "_anchor_to_page", drifting)
    placed, failure = _base(_context([_panel_payload()]))
    assert placed is None and failure is not None
    assert "page anchor" in failure.detail and "S1" in failure.detail


def test_the_ordinary_spread_pass_leaves_panel_cells_alone():
    ctx = _context([_panel_payload()])
    placed, failure = _base(ctx)
    assert failure is None
    plan = placed.panel_plans[0]
    origins = dict(placed.origins)
    poses = dict(placed.poses)
    panel_parts = frozenset(cell.part_id for cell in plan.cells)
    result = dc._spread_band_collisions(ctx, origins, poses, panel_parts)
    assert result is None
    for cell in plan.cells:
        assert origins[cell.part_id] == cell.origin, (
            f"the spread pass moved panel cell {cell.part_id}")
    assert [item.part_id for item in placed.panel_plans[0].cells] == [
        cell.part_id for cell in plan.cells]


def test_a_series_yield_cannot_take_a_panel_cell():
    ctx = _context([_panel_payload()])
    yielded = dc._series_yield_parts(ctx, ())
    assert "S1" not in yielded and "S4" not in yielded, (
        "a panel cell was offered as an ordinary yield")


# ============================================== 3. 空 panel / 轻量旧文档

def test_a_page_without_panels_keeps_the_old_placement():
    ctx = _context(None)
    templates, failure = dc._panel_templates(ctx, (0.0, 0.0), tuple(sorted(ctx.slots)))
    assert (templates, failure) == ((), None)
    placed, failure = _base(ctx)
    assert failure is None and placed.panel_plans == ()
    assert placed.series_plans == ()


def test_a_lightweight_presentation_without_the_key_is_not_broken():
    ctx = _context([_panel_payload()])
    ctx.presentation = type("P", (), {
        "series_branches": (), "modules": ctx.presentation.modules,
    })()
    templates, failure = dc._panel_templates(ctx, (0.0, 0.0), tuple(sorted(ctx.slots)))
    assert (templates, failure) == ((), None)

# ============================================ 4. 33C2b：near 过滤 + 具体座位核对

def test_the_cell_host_near_relation_is_replaced_by_the_concrete_panel_check():
    """自动 near 只对 cell/host 对过滤；显式 below 保留；其它关系不动。"""
    circuit = p32.CircuitSpec.from_dict({
        "parts": copy.deepcopy(p32._parts()),
        "nets": copy.deepcopy(p32._nets()),
    })
    presentation = _presentation([_panel_payload()])
    book = p32._book()
    book["PWR-3V3"] = SymbolProfile(
        symbol_ref="PWR-3V3", title="PWR-3V3", body=(-6.0, 0.0, 6.0, 18.0), pins=[])
    binding = dc.bind_grammar(circuit, presentation, book)
    raw = list(binding.constraints)
    assert any(item.kind == "near" and {item.subject, item.object} == {"S1", "U1"}
               for item in raw), "the grammar no longer binds the branch near its host"
    replaced = dc._with_panel_groups(binding, presentation, circuit)
    pair = [item for item in replaced.constraints
            if {item.subject, item.object} == {"S1", "U1"}]
    assert [item.kind for item in pair] == ["below"], pair
    assert pair[0].subject == "S1" and pair[0].object == "U1"
    assert "panelGroups" in pair[0].reason
    cells = {f"S{index}" for index in range(1, 5)} | {"U1"}
    kept = [item for item in replaced.constraints
            if not ({item.subject, item.object} & cells)]
    assert kept == [item for item in raw
                    if not ({item.subject, item.object} & cells)], (
        "the panel replacement touched a relation between other parts")
    # A page with no panel gets the binding back untouched.
    plain = _presentation(None)
    plain_binding = dc.bind_grammar(circuit, plain, book)
    assert dc._with_panel_groups(plain_binding, plain, circuit) is plain_binding


def test_a_cell_that_is_not_below_its_host_is_still_refused():
    """错位不被放过：below 仍是真关系，关系闸用真实几何判它。"""
    ctx = _context([_panel_payload()])
    placed, failure = _base(ctx)
    assert failure is None
    moved = dict(placed.origins)
    host = moved["U1"]
    moved["S1"] = (host[0] + 200.0, host[1])
    broken = dc._Placement(origins=moved, poses=dict(placed.poses))
    conflict = dc._relation_failures(ctx, broken)
    assert conflict, "a cell moved beside its host was accepted"
    assert "S1" in conflict[0].detail and "below" in conflict[0].detail

def test_the_reserve_hard_value_is_the_intersected_area():
    """Same foreign part, small vs large overlap: both hard, area orders them."""
    ctx = _context([_panel_payload()])
    placed, failure = _base(ctx)
    assert failure is None
    plan = placed.panel_plans[0]
    assert plan.seated
    reserve = plan.reserved_boxes[0]

    def term_for(box):
        return placement._panel_reservation_terms(  # noqa: SLF001
            ctx_request, {"X1": box}, (plan,))[0]

    ctx_request = dc._series_placement_request(
        ctx, (), {part: placed.poses[part] for part in placed.poses})
    sliver = (reserve[2] - 1.0, reserve[1] + 1.0, reserve[2] + 20.0,
              reserve[1] + 2.0)
    deep = (reserve[0] + 1.0, reserve[1] + 1.0,
            min(reserve[0] + 6.0, reserve[2]), min(reserve[1] + 6.0, reserve[3]))
    outside = (reserve[2] + 50.0, reserve[3] + 50.0,
               reserve[2] + 60.0, reserve[3] + 60.0)
    small_term, big_term, none_term = term_for(sliver), term_for(deep), term_for(outside)
    assert small_term.hard and big_term.hard
    assert small_term.value > 0.0 and big_term.value > 0.0
    assert big_term.value > small_term.value
    assert none_term.value == 0.0 and not none_term.violated
    assert small_term.name == big_term.name == "panel-reserve:keys"

def test_a_host_pin_without_a_drawable_direction_is_refused_by_name():
    """No guessed +x escape: an unreadable pin side is a named refusal."""
    ctx = _context([_panel_payload()])
    templates, failure = dc._panel_templates(
        ctx, (0.0, 0.0), tuple(sorted(ctx.slots)))
    assert failure is None and templates
    poses = {part: ctx.accepted[part][0]
             for part in ["U1", "S1", "S2", "S3", "S4"]}
    request = dc._series_placement_request(ctx, (), poses,
                                           panel_templates=templates)
    host_part = request.part("U1")
    token = templates[0].cells[0].host_token
    pins = tuple(
        dataclasses.replace(pin, direction="") if pin.number == token else pin
        for pin in host_part.profile.pins
    )
    broken_profile = dataclasses.replace(host_part.profile, pins=pins)
    assert any(pin.number == token and pin.direction == "" for pin in broken_profile.pins)
    parts = tuple(
        dataclasses.replace(part, profile=broken_profile)
        if part.part_id == "U1" else part
        for part in request.parts
    )
    broken = dataclasses.replace(request, parts=parts)
    plan = placement.bind_panel_plans(broken, {"U1": (0.0, 0.0)}, poses)[0]
    assert not plan.seated and plan.refusal is not None
    rendered = plan.refusal.render()
    assert "no drawable direction" in rendered and token in rendered

# ==================================================== 5. §34-2：host path 回放

def test_panel_channels_replay_the_plan_point_for_point():
    """Each cell's host lead becomes its from net's run — the plan's own path,
    or the final candidate's legal pin-wall repair of it."""
    ctx = _context([_panel_payload()])
    placed, failure = _base(ctx)
    assert failure is None
    plan = placed.panel_plans[0]
    channels, problem = dc._panel_channels(ctx, placed)
    assert problem is None
    assert sum(len(items) for items in channels.values()) == len(plan.cells)
    runs = [item for items in channels.values() for item in items]
    final = {}
    for cell in plan.cells:
        nets = dc._part_nets(ctx.circuit, cell.part_id)
        at = dc._pin_point(
            ctx, cell.part_id,
            next(token for token, _net in nets.items()
                 if dc._key(dc._pin_point(
                     ctx, cell.part_id, token, placed.poses, placed.origins))
                 == dc._key(cell.from_seat)),
            placed.poses, placed.origins,
        )
        assert dc._key(at) == dc._key(cell.from_seat)
        others = [
            final[item.part_id] if item.part_id in final
            else tuple(item.host_path)
            for item in plan.cells if item.part_id != cell.part_id
        ]
        expected = dc._panel_lead_detour(
            ctx, placed, plan, cell, tuple(cell.host_path), others)
        assert not isinstance(expected, GrammarFailure), getattr(expected, "detail", "")
        final[cell.part_id] = expected
        assert any(list(item.points) == list(expected) for item in runs), (
            f"{cell.part_id}'s run is neither the plan's path nor its legal repair")
        for start, stop in zip(expected, expected[1:]):
            assert dc._key(expected[0]) == dc._key(cell.host_path[0])
            assert dc._key(expected[-1]) == dc._key(cell.from_seat)


def test_connect_net_keeps_the_panel_channel_and_adds_no_second_route():
    ctx = _context([_panel_payload()])
    placed, failure = _base(ctx)
    assert failure is None
    channels, problem = dc._panel_channels(ctx, placed)
    assert problem is None
    net_id, runs = next(iter(channels.items()))
    cell = placed.panel_plans[0].cells[0]
    nets = dc._part_nets(ctx.circuit, cell.part_id)
    from_token = next(token for token, net in nets.items()
                      if dc._key(dc._pin_point(
                          ctx, cell.part_id, token, placed.poses, placed.origins))
                      == dc._key(cell.from_seat))
    host_pin = dc._pin_point(
        ctx, placed.panel_plans[0].host_part, cell.host_token,
        placed.poses, placed.origins)
    expression = dc._Expression(
        net=net_id, style="wire",
        points=((f"{cell.part_id}.{from_token}", cell.from_seat),
                (f"{placed.panel_plans[0].host_part}.{cell.host_token}", host_pin)),
        reason="panel cell",
    )
    router = dc._Router(
        grid=ctx.budget.grid, residue=placed.residue, boxes=[],
        bounds=dc._search_bounds(ctx, [], [cell.from_seat, host_pin]),
    )
    drawn = dc._connect_net(ctx, router, expression, set(), list(runs))
    assert not isinstance(drawn, dc._Unrouted)
    segments, reason = drawn
    assert len(segments) == len(runs), (
        "the net loop drew a second route over the plan's own channel")
    assert [list(item.points) for item in segments] == [
        list(item.points) for item in runs]
    assert "already joins" in reason


def test_a_misplaced_or_broken_panel_channel_is_refused_by_name():
    ctx = _context([_panel_payload()])
    placed, failure = _base(ctx)
    assert failure is None
    plan = placed.panel_plans[0]
    cell = plan.cells[0]

    def failure_for(path):
        broken_cell = dataclasses.replace(cell, host_path=path)
        broken_plan = dataclasses.replace(plan, cells=(broken_cell,) + plan.cells[1:])
        broken = dataclasses.replace(placed, panel_plans=(broken_plan,))
        channels, problem = dc._panel_channels(ctx, broken)
        assert problem is not None
        assert problem.category == "layout-unsat"
        assert cell.part_id in problem.detail
        return problem

    # start off the host foot
    failure_for((((cell.host_path[0][0] + 20.0, cell.host_path[0][1]),)
                 + tuple(cell.host_path[1:])))
    # non-orthogonal leg
    diagonal = ((cell.host_path[0][0] + 7.0, cell.host_path[0][1] + 7.0),)
    failure_for((cell.host_path[0],) + diagonal + tuple(cell.host_path[1:]))
    # broken chain: the end no longer reaches the from seat
    failure_for(tuple(cell.host_path[:-1]))

# ================================================ 6. §34-3：terminal 旗预留

def test_panel_terminal_seats_hang_down_from_the_to_foot():
    """Anchor/lead/hang are the template's own downward flag geometry."""
    ctx = _context([_panel_payload()])
    placed, failure = _base(ctx)
    assert failure is None
    seats, problem = dc._panel_terminal_seats(ctx, placed)
    assert problem is None
    plan = placed.panel_plans[0]
    assert len(seats) == len(plan.cells)
    for cell in plan.cells:
        nets = dc._part_nets(ctx.circuit, cell.part_id)
        to_token = next(
            token for token in sorted(nets)
            if dc._key(dc._pin_point(
                ctx, cell.part_id, token, placed.poses, placed.origins))
            == dc._key(cell.to_seat)
        )
        net_id = nets[to_token]
        anchor, lead, hang = seats[(net_id, f"{cell.part_id}.{to_token}")]
        assert anchor == (cell.to_seat[0], cell.to_seat[1] - dc.FLAG_LEAD)
        assert hang == -1.0
        assert [tuple(point) for point in lead] == [tuple(cell.to_seat), anchor]
        profile, _ref = dc._flag_plan(ctx, net_id, ctx.circuit.net(net_id).cls)
        expected = dc._flag_box(
            profile, dc._flag_rotation((0.0, -1.0), dc.flag_glyph_kind(profile)),
            (0.0, -dc.FLAG_LEAD), net_id,
        )
        assert (
            min(expected[0], 0.0), min(expected[1] - dc.FLAG_LEAD, 0.0),
            max(expected[2], 0.0), max(expected[3] - dc.FLAG_LEAD, 0.0),
        ) == pytest.approx(tuple(
            templates_cell_box(ctx, cell.part_id)
        )), "the seat and the template reserve two different flags"


def templates_cell_box(ctx, part_id):
    templates, failure = dc._panel_templates(
        ctx, (0.0, 0.0), tuple(sorted(ctx.slots)))
    assert failure is None
    for template in templates:
        for cell in template.cells:
            if cell.part_id == part_id:
                assert cell.flag_box is not None
                return cell.flag_box
    raise AssertionError(part_id)


def test_a_panel_terminal_without_a_flag_symbol_is_refused_by_name():
    ctx = _context([_panel_payload()])
    placed, failure = _base(ctx)
    assert failure is None
    # Drop the rail flag symbol from the render context's book and re-bind: the
    # seat builder must name the missing symbol instead of hanging nothing.
    previous = ctx.book.pop("PWR-3V3")
    try:
        seats, problem = dc._panel_terminal_seats(ctx, placed)
    finally:
        ctx.book["PWR-3V3"] = previous
    assert problem is not None and problem.category == "layout-unsat"
    assert "no flag symbol" in problem.detail

# ================================================ 7. §34-4：panel 文字相对盒

def test_panel_text_map_replays_the_template_boxes():
    ctx = _context([_panel_payload()])
    placed, failure = _base(ctx)
    assert failure is None
    rows, problem = dc._panel_text_map(ctx, placed)
    assert problem is None
    templates, _ = dc._panel_templates(
        ctx, placed.residue, tuple(sorted(placed.origins)))
    for template in templates:
        for cell in template.cells:
            got = rows[cell.part_id]
            origin = placed.origins[cell.part_id]
            assert [(kind, text) for kind, text, _box in got] == [
                (kind, text) for kind, text in dc._part_lines(ctx, cell.part_id)]
            assert [box for _k, _t, box in got] == [
                (box[0] + origin[0], box[1] + origin[1],
                 box[2] + origin[0], box[3] + origin[1])
                for box in cell.text_boxes
            ]


def test_part_texts_prints_panel_cells_where_the_reserve_is():
    ctx = _context([_panel_payload()])
    placed, failure = _base(ctx)
    assert failure is None
    rows, _problem = dc._panel_text_map(ctx, placed)
    texts, failure = dc._part_texts(ctx, placed, [], [])
    assert failure is None
    for part_id, expected in rows.items():
        got = [(item.kind, item.text, item.bbox)
               for item in texts if item.part_id == part_id]
        assert got == list(expected), part_id


def test_a_panel_cell_with_declared_rows_that_disagree_is_refused(monkeypatch):
    ctx = _context([_panel_payload()])
    placed, failure = _base(ctx)
    assert failure is None
    real = dc._declared_rows

    def wrong(ctx_, part_id, profile, pose, origin):
        if part_id == "S1":
            return [("reference", "NOPE", (0.0, 0.0, 1.0, 1.0))]
        return real(ctx_, part_id, profile, pose, origin)

    monkeypatch.setattr(dc, "_declared_rows", wrong)
    texts, failure = dc._part_texts(ctx, placed, [], [])
    assert texts == [] and failure is not None
    assert failure.category == "layout-unsat"
    assert "declares different text rows" in failure.detail

# ================================================ 8. §34-4b：host path 几何

def test_every_panel_host_path_enters_from_the_cell_above_and_never_cuts_it():
    ctx = _context([_panel_payload()])
    placed, failure = _base(ctx)
    assert failure is None
    plan = placed.panel_plans[0]
    for cell in plan.cells:
        path = cell.host_path
        for start, stop in zip(path, path[1:]):
            assert (abs(start[0] - stop[0]) <= 1e-9
                    or abs(start[1] - stop[1]) <= 1e-9), path
        assert path[-1] == cell.from_seat
        assert path[-2][0] == cell.from_seat[0], (
            "the last leg into the from foot must be vertical")
        assert path[-2][1] > cell.from_seat[1], (
            "the lead must reach the from foot from above (towards the host)")
        body = placement.pose_box(
            ctx.profile(cell.part_id).body, rotation=cell.pose.rotation,
            mirror=cell.pose.mirror, ox=cell.origin[0], oy=cell.origin[1],
        )
        assert not placement._panel_path_crosses(path, body, 0.0), (
            f"the lead into {cell.part_id} crosses its own body")


def test_a_lead_that_drops_below_the_foot_and_climbs_back_is_caught():
    """The measured defect, as a path: down past the body, then up through it."""
    body = (-77.0, -156.5, -53.0, -143.5)
    from_seat = (-65.0, -130.0)
    bad = ((-96.0, -150.0), (-65.0, -150.0), from_seat)
    assert placement._panel_path_crosses(bad, body, 0.0), (
        "a lead that enters the body from below was not seen by the own-body check")
    good = ((-96.0, -110.0), (-65.0, -110.0), from_seat)
    assert not placement._panel_path_crosses(good, body, 0.0)


# ==================================================== 9. 宿主相对 route cache

def _request_and_seat(ctx):
    templates, failure = dc._panel_templates(
        ctx, (0.0, 0.0), tuple(sorted(ctx.slots)))
    assert failure is None and templates
    poses = {part: ctx.accepted[part][0] for part in sorted(ctx.accepted)}
    request = dc._series_placement_request(ctx, (), poses)
    request = dataclasses.replace(request, panel_templates=tuple(templates))
    return request, poses


def test_repeated_binds_of_one_pose_route_the_panel_once(monkeypatch):
    """The joint router is spent once per host pose, not once per candidate."""
    ctx = _context([_panel_payload()])
    request, poses = _request_and_seat(ctx)
    placement._PANEL_SOLVE_CACHE.clear()
    calls = []
    real = placement._router._Router.route

    def spy(self, start, goal, **kwargs):
        calls.append((start, goal))
        return real(self, start, goal, **kwargs)

    monkeypatch.setattr(placement._router._Router, "route", spy)
    first = placement.bind_panel_plans(request, {"U1": (0.0, 0.0)}, poses)[0]
    assert first.seated, first.refusal
    after_first = len(calls)
    assert 0 < after_first <= 4, after_first
    for _ in range(79):
        again = placement.bind_panel_plans(request, {"U1": (0.0, 0.0)}, poses)[0]
        assert again.seated
    assert len(calls) == after_first, (
        f"{len(calls) - after_first} extra _Router.route calls for 79 repeated "
        "binds of one pose — the cache is not being consulted")


def test_a_cached_panel_translates_with_the_host_and_rechecks_foreign_parts():
    """The cache is template geometry: a rigid move drags it; the environment
    is checked on every call and is never answered from the cache."""
    ctx = _context([_panel_payload()])
    request, poses = _request_and_seat(ctx)
    placement._PANEL_SOLVE_CACHE.clear()
    here = placement.bind_panel_plans(request, {"U1": (0.0, 0.0)}, poses)[0]
    assert here.seated, here.refusal
    delta = (37.0, 53.0)
    moved = placement.bind_panel_plans(request, {"U1": delta}, poses)[0]
    assert moved.seated, moved.refusal
    for left, right in zip(here.cells, moved.cells):
        assert right.origin == (left.origin[0] + delta[0], left.origin[1] + delta[1])
        assert right.from_seat == (
            left.from_seat[0] + delta[0], left.from_seat[1] + delta[1])
        assert right.to_seat == (
            left.to_seat[0] + delta[0], left.to_seat[1] + delta[1])
        assert right.host_path == tuple(
            (point[0] + delta[0], point[1] + delta[1]) for point in left.host_path)
    assert moved.host_paths == tuple(
        tuple((point[0] + delta[0], point[1] + delta[1]) for point in path)
        for path in here.host_paths)

    # Move a foreign part onto a cell's reserved room; the *cached* solve must
    # not excuse it.
    plan = here
    owned = set(plan.owned_parts)
    foreign = next(
        item.part_id for item in request.parts if item.part_id not in owned)
    reserve = plan.reserved_boxes[0]
    origins = {"U1": (0.0, 0.0), foreign: (reserve[0], reserve[1])}
    blocked = placement.bind_panel_plans(request, origins, poses)[0]
    assert not blocked.seated and blocked.refusal is not None
    assert "intrudes" in blocked.refusal.detail


def test_the_topology_search_spends_a_bounded_number_of_routes(monkeypatch):
    """A whole topology search may not call the router once per candidate."""
    ctx = _context([_panel_payload()])
    placement._PANEL_SOLVE_CACHE.clear()
    calls = []
    solves = []
    real = placement._router._Router.route
    real_solve = placement._solve_panel_relative

    def spy(self, start, goal, **kwargs):
        calls.append((start, goal))
        return real(self, start, goal, **kwargs)

    def solve_spy(request, template, pose):
        solves.append((template.group_id, pose.label()))
        return real_solve(request, template, pose)

    monkeypatch.setattr(placement._router._Router, "route", spy)
    monkeypatch.setattr(placement, "_solve_panel_relative", solve_spy)
    answer = dc._topology_placement(ctx)
    assert isinstance(answer, dc._Placement), getattr(answer, "detail", answer)
    assert answer.panel_plans and all(item.seated for item in answer.panel_plans)
    assert len(solves) <= 8, (
        f"{len(solves)} panel solves for {len({pose for _g, pose in solves})} "
        "host pose(s); a pose's geometry is solved once")
    assert len(calls) <= 4 * len(solves), (
        f"{len(calls)} _Router.route calls for {len(solves)} solve(s) — more "
        "than the four cells one solve may route")

# ======================= 11. 最终候选：共享顶点/两段局部修补


def _lead_interior_point(path):
    """A lattice point strictly inside the lead's longest horizontal leg."""
    legs = [(a, b) for a, b in zip(path, path[1:]) if abs(a[1] - b[1]) <= 1e-9]
    a, b = max(legs, key=lambda pair: abs(pair[0][0] - pair[1][0]))
    return (round((a[0] + b[0]) / 2.0 / 5.0) * 5.0, a[1])

def _patch_bodies(monkeypatch, ctx, cell, extra):
    real = dc._panel_lead_obstacles

    def patched(ctx_, placed_, plan_, cell_, **kwargs):
        allowed, points, bodies = real(ctx_, placed_, plan_, cell_, **kwargs)
        if cell_.part_id == cell.part_id:
            bodies = [*bodies, *extra]
        return allowed, points, bodies

    monkeypatch.setattr(dc, "_panel_lead_obstacles", patched)


def test_a_body_on_a_shared_vertex_is_repaired_by_moving_the_vertex(monkeypatch):
    # S2 isolation: this test measures the panel's own geometry, not the
    # service seats that now share the page. The service capability is switched
    # off **for this test only**; no assertion or geometry below changes.
    monkeypatch.setattr(dc, "_service_templates", lambda *a, **k: ((), None))
    monkeypatch.setattr(dc, "_service_branch_parts", lambda *a, **k: frozenset())
    ctx = _context([_panel_payload()])
    placed, failure = _base(ctx)
    assert failure is None
    plan = placed.panel_plans[0]
    cell = plan.cells[0]
    path = tuple(cell.host_path)
    vertex = path[2]
    body = (vertex[0] - 2.0, vertex[1] - 2.0,
            vertex[0] + 2.0, vertex[1] + 2.0)
    _patch_bodies(monkeypatch, ctx, cell, [body])
    out = dc._panel_lead_detour(ctx, placed, plan, cell, path, ())
    assert not isinstance(out, GrammarFailure), getattr(out, "detail", out)
    assert tuple(out) != path, "the covered shared vertex was not moved"
    for start, stop in zip(out, out[1:]):
        assert not dc._segment_hits_box(start, stop, body), out


def test_a_shared_conflict_vertex_is_solved_or_refused_by_name(monkeypatch):
    ctx = _context([_panel_payload()])
    placed, failure = _base(ctx)
    assert failure is None
    plan = placed.panel_plans[0]
    first, second = plan.cells[0], plan.cells[1]
    extra = []
    for cell in (first, second):
        v = tuple(cell.host_path)[2]
        extra.append((v[0] - 2.0, v[1] - 2.0, v[0] + 2.0, v[1] + 2.0))
    real = dc._panel_lead_obstacles

    def patched(ctx_, placed_, plan_, cell_, **kwargs):
        allowed, points, bodies = real(ctx_, placed_, plan_, cell_, **kwargs)
        if cell_.part_id == first.part_id:
            bodies = [*bodies, extra[0]]
        elif cell_.part_id == second.part_id:
            bodies = [*bodies, extra[1]]
        return allowed, points, bodies

    monkeypatch.setattr(dc, "_panel_lead_obstacles", patched)
    a = dc._panel_lead_detour(
        ctx, placed, plan, first, tuple(first.host_path),
        (tuple(second.host_path),))
    if isinstance(a, GrammarFailure):
        assert "no local vertex/leg repair" in a.detail or "covered" in a.detail
        return
    b = dc._panel_lead_detour(
        ctx, placed, plan, second, tuple(second.host_path), (tuple(a),))
    if isinstance(b, GrammarFailure):
        assert "no local vertex/leg repair" in b.detail or "covered" in b.detail
        return
    assert not placement._panel_leads_meet(tuple(a), tuple(b))


def test_a_foreign_body_on_the_from_foot_is_refused_not_moved(monkeypatch):
    ctx = _context([_panel_payload()])
    placed, failure = _base(ctx)
    assert failure is None
    plan = placed.panel_plans[0]
    cell = plan.cells[0]
    foot = cell.from_seat
    body = (foot[0] - 3.0, foot[1] - 3.0, foot[0] + 3.0, foot[1] + 3.0)
    _patch_bodies(monkeypatch, ctx, cell, [body])
    out = dc._panel_lead_detour(
        ctx, placed, plan, cell, tuple(cell.host_path), ())
    assert isinstance(out, GrammarFailure)
    assert "covered by a foreign body" in out.detail


def test_a_host_pin_lead_wall_on_a_lead_is_bent_around(monkeypatch):
    # S2 isolation: this test measures the panel's own geometry, not the
    # service seats that now share the page. The service capability is switched
    # off **for this test only**; no assertion or geometry below changes.
    monkeypatch.setattr(dc, "_service_templates", lambda *a, **k: ((), None))
    monkeypatch.setattr(dc, "_service_branch_parts", lambda *a, **k: frozenset())
    """The obstacle is the drawn pin lead box, not only its tip point."""
    ctx = _context([_panel_payload()])
    placed, failure = _base(ctx)
    assert failure is None
    plan = placed.panel_plans[0]
    cell = plan.cells[0]
    path = tuple(cell.host_path)
    target = _lead_interior_point(path)
    wall = (target[0] - 0.5, target[1] - 5.0,
            target[0] + 0.5, target[1] + 5.0)
    _patch_bodies(monkeypatch, ctx, cell, [wall])
    out = dc._panel_lead_detour(ctx, placed, plan, cell, path, ())
    assert not isinstance(out, GrammarFailure), getattr(out, "detail", out)
    assert tuple(out) != path, "the drawn pin lead wall was only a point test"
    for start, stop in zip(out, out[1:]):
        assert not dc._segment_hits_box(start, stop, wall), out


# ======================= 12. 最终候选的外国件让位

def _foreign_on_the_panel(ctx, placed):
    plan = placed.panel_plans[0]
    owned = set(plan.owned_parts)
    foreign = next(
        part for part in sorted(placed.origins)
        if part not in owned and part in {item.id for item in ctx.circuit.parts})
    target = plan.reserved_boxes[0]
    placed.origins[foreign] = (target[0], target[1])
    return foreign, target


def test_a_foreign_part_on_the_panel_is_yielded_to_a_clear_origin(monkeypatch):
    # S2 isolation: this test measures the panel's own geometry, not the
    # service seats that now share the page. The service capability is switched
    # off **for this test only**; no assertion or geometry below changes.
    monkeypatch.setattr(dc, "_service_templates", lambda *a, **k: ((), None))
    monkeypatch.setattr(dc, "_service_branch_parts", lambda *a, **k: frozenset())
    ctx = _context([_panel_payload()])
    placed, failure = _base(ctx)
    assert failure is None
    foreign, target = _foreign_on_the_panel(ctx, placed)
    before = placed.origins[foreign]
    refusal = dc._yield_panel_foreign_parts(ctx, placed)
    assert refusal is None, refusal.detail
    assert placed.origins[foreign] != before
    box = dc._part_box(
        ctx.profile(foreign), placed.poses[foreign], placed.origins[foreign])
    for reserve in placed.panel_plans[0].reserved_boxes:
        assert not dc._panel_boxes_overlap(box, reserve)


def test_a_locked_foreign_part_on_the_panel_is_refused(monkeypatch):
    # S2 isolation: this test measures the panel's own geometry, not the
    # service seats that now share the page. The service capability is switched
    # off **for this test only**; no assertion or geometry below changes.
    monkeypatch.setattr(dc, "_service_templates", lambda *a, **k: ((), None))
    monkeypatch.setattr(dc, "_service_branch_parts", lambda *a, **k: frozenset())
    ctx = _context([_panel_payload()])
    placed, failure = _base(ctx)
    assert failure is None
    foreign, _target = _foreign_on_the_panel(ctx, placed)
    from boardwise.core.presentationspec import UserLock
    ctx.presentation.user_locks = [UserLock(part_id=foreign, x=0.0, y=0.0)]
    refusal = dc._yield_panel_foreign_parts(ctx, placed)
    assert refusal is not None
    assert "locked" in refusal.detail


def test_a_yielded_foreign_part_keeps_the_declared_relations():
    ctx = _context([_panel_payload()])
    placed, failure = _base(ctx)
    assert failure is None
    foreign, _target = _foreign_on_the_panel(ctx, placed)
    refusal = dc._yield_panel_foreign_parts(ctx, placed)
    assert refusal is None, refusal.detail
    assert dc._relation_failures(ctx, placed) == []


# ======================= 13. 最终候选正交路径简化

def test_a_staircase_panel_lead_is_shortened_keeping_its_endpoints():
    path = ((15.0, 15.0), (15.0, 10.0), (20.0, 10.0),
            (20.0, 5.0), (25.0, 5.0), (25.0, 0.0))
    allowed = {dc._key(path[0]), dc._key(path[-1])}
    out = dc._panel_simplify(path, allowed, (), (), ())
    assert out[0] == path[0] and out[-1] == path[-1]
    assert len(out) < len(path), out
    for start, stop in zip(out, out[1:]):
        assert abs(start[0] - stop[0]) <= 1e-9 or abs(start[1] - stop[1]) <= 1e-9


def test_a_path_that_cannot_be_shortened_stays_legal_and_unchanged():
    path = ((0.0, 10.0), (0.0, 5.0), (5.0, 5.0), (5.0, 0.0))
    allowed = {dc._key(path[0]), dc._key(path[-1])}
    body = (2.0, 8.0, 8.0, 12.0)
    out = dc._panel_simplify(path, allowed, (), (body,), ())
    assert out[0] == path[0] and out[-1] == path[-1]
    for start, stop in zip(out, out[1:]):
        assert not dc._segment_hits_box(start, stop, body), out


# ======================= 14. panel 供电旗聚簇（显式 opt-in）

def test_a_panel_page_compiles_with_its_supply_flags_grouped():
    ctx = _context([_panel_payload()])
    assert dc._flag_grouping(ctx) is True
    result = dc.compile(
        ctx.circuit, ctx.presentation, ctx.book,
        dc.CompileBudget(max_candidates=4))
    assert result.ok, result.render_failures()[:600]
    plan = result.candidates[0]
    assert plan.evidence.hard_violations == []
    assert plan.evidence.verdict == "pass"


def test_a_page_without_panels_keeps_flag_grouping_off():
    ctx = _context(None)
    assert dc._flag_grouping(ctx) is False


def test_panel_terminal_seats_win_over_the_grouping_pass():
    """The plan's explicit terminal anchors are the drawn flag anchors."""
    ctx = _context([_panel_payload()])
    result = dc.compile(
        ctx.circuit, ctx.presentation, ctx.book,
        dc.CompileBudget(max_candidates=4))
    assert result.ok, result.render_failures()[:600]
    plan = result.candidates[0]
    symbols = {(dc._key((item.x, item.y)), item.net)
               for item in plan.power_symbols}
    placed, failure = _base(ctx)
    assert failure is None
    for cell in placed.panel_plans[0].cells:
        nets = dc._part_nets(ctx.circuit, cell.part_id)
        to_token = next(
            token for token in sorted(nets)
            if dc._key(dc._pin_point(
                ctx, cell.part_id, token, placed.poses, placed.origins))
            == dc._key(cell.to_seat))
        net_id = nets[to_token]
        anchors = [anchor for anchor, _lead, _hang in [next(
            value for (net, member), value in
            dc._panel_terminal_seats(ctx, placed)[0].items()
            if member == f"{cell.part_id}.{to_token}")]]
        assert anchors and (dc._key(anchors[0]), net_id) in symbols
