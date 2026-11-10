"""548D3X3C（33C1）：placement 层的真实 panel 座位计划。

本批只做 **topology 侧**：`placement.PlacementInput.panel_templates` →
`placement.place()` 绑定唯一 binder → `PlacementResult.panel_plans`。
base 消费者、页锚点与最终 route/text/flag 回放不在本批（33C2/§34）。

夹具复用 `tests/test_548d_panel_validation.py` 的真实 MCU32/KEY 电路；文本相对盒用
`drawcompiler._line_boxes`、姿态用 `drawcompiler._arm_pose` 构造（生产 placement 不
import drawcompiler）。所有断言都只看结果自身的 plan/坐标关系，不断言参考绝对坐标。
"""

from __future__ import annotations

import math

import pytest

import test_548d_panel_validation as p32

from boardwise.engines import drawcompiler as dc
from boardwise.engines import placement

KEY_BOOK = p32._book()
_MCU_PINS = ("PC6", "PB15", "PB14", "PB13")


def _cell(index: int, *, text_boxes=None, flag_box=(0.0, -50.0, 0.0, -20.0)):
    profile = KEY_BOOK["KEY"]
    pose = dc._arm_pose(profile, "1", "2", (0.0, -1.0))
    assert pose is not None, "the KEY symbol has no from-top/to-bottom pose"
    rel = placement.part_box(profile, pose, (0.0, 0.0))
    boxes = dc._line_boxes(rel, [f"S{index}", "KEY"], "right")
    return placement.PanelCell(
        part_id=f"S{index}", from_net=f"KEY{index}", to_net="3V3",
        from_token="1", to_token="2", host_token=_MCU_PINS[index - 1],
        pose=pose, text_boxes=tuple(boxes if text_boxes is None else text_boxes),
        flag_box=flag_box,
    )


def _templates(**overrides) -> tuple[placement.PanelSeatTemplate, ...]:
    entry = dict(
        group_id="keys", host_part="U1",
        cells=tuple(_cell(index) for index in range(1, 5)),
        columns=2, side="bottom", grid=5.0, lattice=(0.0, 0.0),
    )
    entry.update(overrides)
    return (placement.PanelSeatTemplate(**entry),)


def _placement_part(part_id: str, symbol: str) -> placement.PlacementPart:
    profile = KEY_BOOK[symbol]
    return placement.PlacementPart(
        part_id=part_id, profile=profile, poses=tuple(profile.poses))


def _nets() -> tuple[placement.PlacementNet, ...]:
    return tuple(
        placement.PlacementNet(
            net_id=net["id"],
            members=tuple(
                (member.partition(".")[0], member.partition(".")[2])
                for member in net["members"]
            ),
            cls=net["class"],
        )
        for net in p32._nets()
    )


def _request(panels=(), *, extra=(), iterations: int = 120) -> placement.PlacementInput:
    by_id = {"U1": _placement_part("U1", "MCU32")}
    for index in range(1, 5):
        by_id[f"S{index}"] = _placement_part(f"S{index}", "KEY")
    for part in extra:
        by_id[part.part_id] = part
    return placement.PlacementInput(
        parts=tuple(by_id.values()), nets=_nets(), grid=5.0,
        iterations=iterations, restarts=1, panel_templates=tuple(panels),
    )


# ================================================== 1. 真实 2×2（四格两带）

def test_a_real_place_result_carries_a_two_by_two_panel():
    result = placement.place(_request(_templates()))
    assert len(result.panel_plans) == 1
    plan = result.panel_plans[0]
    assert plan.seated, plan.refusal
    assert result.panel_mismatches() == ()
    assert plan.owned_parts == frozenset({"U1", "S1", "S2", "S3", "S4"})

    origins = {cell.part_id: cell.origin for cell in plan.cells}
    xs = sorted({round(cell.origin[0], 6) for cell in plan.cells})
    ys = sorted({round(cell.origin[1], 6) for cell in plan.cells})
    assert len(xs) == 2 and len(ys) == 2, (xs, ys)
    for x in xs:
        assert sum(1 for cell in plan.cells if round(cell.origin[0], 6) == x) == 2
    for y in ys:
        assert sum(1 for cell in plan.cells if round(cell.origin[1], 6) == y) == 2

    # 身份、姿态与网：每格仍是自己的 part / pose / from-to 网。
    for cell, template_cell in zip(plan.cells, _templates()[0].cells):
        assert cell.part_id == template_cell.part_id
        assert cell.pose == template_cell.pose
        assert result.origins[cell.part_id] == cell.origin
        assert result.poses[cell.part_id] == cell.pose
    # from 朝宿主（上方）、to 朝外（下方）。
    for cell in plan.cells:
        assert cell.from_seat[1] > cell.to_seat[1]

    # host path 正交，且不穿宿主本体。
    for path in plan.host_paths:
        for start, stop in zip(path, path[1:]):
            assert (abs(start[0] - stop[0]) <= 1e-9
                    or abs(start[1] - stop[1]) <= 1e-9), path
    # 文本/旗/零件的预留都在 plan 里，且文本盒在格预留内。
    for cell, template_cell in zip(plan.cells, _templates()[0].cells):
        assert cell.reserved
        for box in template_cell.text_boxes:
            moved = (box[0] + cell.origin[0], box[1] + cell.origin[1],
                     box[2] + cell.origin[0], box[3] + cell.origin[1])
            assert any(
                reserve[0] <= moved[0] and moved[2] <= reserve[2]
                and reserve[1] <= moved[1] and moved[3] <= reserve[3]
                for reserve in cell.reserved
            ), (cell.part_id, moved)


def test_the_panel_is_under_the_host_body_not_between_its_pins():
    result = placement.place(_request(_templates()))
    plan = result.panel_plans[0]
    host = placement.part_box(
        KEY_BOOK["MCU32"], result.poses["U1"], result.origins["U1"])
    assert all(cell.origin[1] < host[1] for cell in plan.cells)


# ================================================== 2. 负例（具名拒绝，不抛）

def test_a_side_other_than_bottom_is_refused_by_name():
    result = placement.place(_request(_templates(side="top")))
    plan = result.panel_plans[0]
    assert not plan.seated and plan.refusal is not None
    text = plan.refusal.render()
    assert "not a panel this build can seat" in text
    assert "'top'" in text


def test_a_foreign_part_inside_the_reserve_is_refused_by_name():
    first = placement.place(_request(_templates(), iterations=0))
    reserve = first.panel_plans[0].reserved_boxes[0]
    point = ((reserve[0] + reserve[2]) / 2.0, (reserve[1] + reserve[3]) / 2.0)
    foreign = placement.PlacementPart(
        part_id="D1", profile=KEY_BOOK["LED"], poses=tuple(KEY_BOOK["LED"].poses),
        locked_origin=point,
    )
    request = _request(_templates(), extra=(foreign,), iterations=0)
    result = placement.place(request)
    plan = result.panel_plans[0]
    assert not plan.seated and plan.refusal is not None
    text = plan.refusal.render()
    assert "foreign part 'D1'" in text and "intrudes" in text
    # The same intrusion is a hard cost while a seated plan is being searched.
    seated = first.panel_plans[0]
    terms = placement._panel_reservation_terms(
        request, {"D1": (point[0] - 5, point[1] - 5, point[0] + 5, point[1] + 5)},
        (seated,),
    )
    assert terms and terms[0].hard and terms[0].name == "panel-reserve:keys"


def test_a_host_lead_that_must_cross_the_host_body_is_refused(monkeypatch):
    host = placement.PlacementPart(
        part_id="H1", profile=KEY_BOOK["KEY"], poses=tuple(KEY_BOOK["KEY"].poses))
    panels = _templates(host_part="H1", cells=tuple(
        placement.PanelCell(
            part_id=f"S{index}", from_net=f"KEY{index}", to_net="3V3",
            from_token="1", to_token="2", host_token="1",
            pose=_cell(index).pose, text_boxes=_cell(index).text_boxes,
            flag_box=_cell(index).flag_box,
        )
        for index in range(1, 5)
    ))
    # The *joint* router now finds a legal way round the host body for most
    # shapes, so this negative is stated as what it claims: if a route **does**
    # cross the host body, the post-route host-body check refuses it by name.
    # (A legal route that first meets another lead is a different negative and
    # is proved elsewhere.)
    def through_the_host(self, start, goal, **kwargs):
        body = self.boxes[-2] if len(self.boxes) > 1 else self.boxes[-1]
        centre = ((body[0] + body[2]) / 2.0, (body[1] + body[3]) / 2.0)
        return [
            start,
            (start[0], centre[1]),
            (centre[0], centre[1]),
            (centre[0], goal[1]),
            goal,
        ]

    monkeypatch.setattr(
        placement._router._Router, "route", through_the_host)
    result = placement.place(_request(panels, extra=(host,), iterations=0))
    plan = result.panel_plans[0]
    assert not plan.seated and plan.refusal is not None
    assert "cross the host's own body" in plan.refusal.render()


def test_a_locked_cell_part_is_refused_instead_of_bent():
    template = _templates()[0]
    cell = template.cells[0]
    locked = placement.PlacementPart(
        part_id=cell.part_id, profile=KEY_BOOK["KEY"],
        poses=tuple(KEY_BOOK["KEY"].poses), locked_origin=(5000.0, 5000.0),
    )
    request = _request(_templates(), extra=(locked,), iterations=0)
    plan = placement.place(request).panel_plans[0]
    assert not plan.seated and plan.refusal is not None
    assert "user lock" in plan.refusal.render()


# ================================================== 3. 空输入 = 旧行为

def test_no_templates_keep_the_old_answer_and_json():
    control = placement.place(_request(iterations=60))
    empty = placement.place(_request((), iterations=60))
    assert control.origins == empty.origins
    assert control.poses == empty.poses
    assert [term.name for term in control.costs] == [
        term.name for term in empty.costs]
    assert control.panel_plans == () and empty.panel_plans == ()
    assert "panelPlans" not in control.to_jsonable()
    assert empty.panel_mismatches() == ()


# ================================================== 4. 候选级投影（33C1 修正）

def _seeded_plan(iterations: int = 0):
    request = _request(_templates(), iterations=iterations)
    result = placement.place(request)
    return request, result


def test_binding_follows_a_host_translation_by_the_same_delta():
    request, result = _seeded_plan()
    plan = result.panel_plans[0]
    delta = (35.0, -40.0)
    moved = dict(result.origins)
    moved["U1"] = (moved["U1"][0] + delta[0], moved["U1"][1] + delta[1])
    shifted = placement.bind_panel_plans(request, moved, result.poses)[0]
    placement.seat_panel_plans((shifted,), moved, result.poses)
    assert shifted.seated and shifted.mismatches(moved, result.poses) == ()
    for before, after in zip(plan.cells, shifted.cells):
        for one, two in (
            (before.origin, after.origin),
            (before.from_seat, after.from_seat),
            (before.to_seat, after.to_seat),
        ):
            assert (abs((two[0] - one[0]) - delta[0]) <= 1e-9
                    and abs((two[1] - one[1]) - delta[1]) <= 1e-9), (
                before.part_id, one, two)
    for before, after in zip(plan.host_paths, shifted.host_paths):
        assert len(before) == len(after)
        for one, two in zip(before, after):
            assert (abs((two[0] - one[0]) - delta[0]) <= 1e-9
                    and abs((two[1] - one[1]) - delta[1]) <= 1e-9)


def test_every_candidate_is_bound_before_it_is_evaluated(monkeypatch):
    """The anneal itself must bind per candidate — the end-of-place re-bind of
    the best answer is not evidence about the candidates.

    So this test does not go through `place`: it takes a legal seed state and its
    seed-bound plans from one `place` call, then runs `_anneal_with_seed` alone
    with `bind_panel_plans`/`evaluate` spied. The anneal's first evaluation is
    the seed's, before any candidate bind (count 0); at least one later
    evaluation must come after a candidate-level bind (count ≥ 1). Disabling that
    per-candidate bind leaves the count at 0 for the whole anneal — red.
    """
    request = _request(_templates(), iterations=60)
    seeded = placement.place(request)          # only for a legal state + plans
    events: list[tuple[str, int]] = []
    real_bind = placement.bind_panel_plans
    real_eval = placement.evaluate
    binds = {"count": 0}

    def spy_bind(request, origins, poses):
        binds["count"] += 1
        events.append(("bind", binds["count"]))
        return real_bind(request, origins, poses)

    def spy_eval(request, state, plans=(), panels=()):
        events.append(("eval", binds["count"]))
        return real_eval(request, state, plans, panels)

    monkeypatch.setattr(placement, "bind_panel_plans", spy_bind)
    monkeypatch.setattr(placement, "evaluate", spy_eval)
    placement._anneal_with_seed(  # noqa: SLF001 - the search under test
        request, seeded, request.seed, (), seeded.panel_plans,
    )
    evaluated = [count for kind, count in events if kind == "eval"]
    assert evaluated and evaluated[0] == 0, (
        "the anneal's first evaluation is the seed's, before any candidate bind")
    assert any(count >= 1 for count in evaluated[1:]), (
        "no candidate was evaluated after a candidate-level re-bind: inside the "
        "anneal the panels are still the seed's, so a moved host is priced "
        "against stale seats (the end-of-place re-bind cannot stand in for this)")
    assert [kind for kind, _count in events][0] == "eval"


def test_panel_cells_never_enter_the_search_moved(monkeypatch):
    """The exclusion is load-bearing: observe each candidate *before* the bind.

    A candidate's cells can only come from an earlier binder answer — the move
    set never writes one. The snapshot every candidate brings into the binder
    must therefore be one of the plans already returned (the accepted answer's;
    a rejected candidate leaves `current` on the last accepted one) and never a
    hand-moved position. With the guard disabled a move intervenes and a snapshot
    matches no earlier plan — the final re-bind cannot hide that.
    """
    real_bind = placement.bind_panel_plans
    seen_plans: list[dict[str, tuple[float, float]]] = []
    drift: list[str] = []

    def recording_bind(request, origins, poses):
        snapshot = {
            cell.part_id: tuple(origins[cell.part_id])
            for template in request.panel_templates
            for cell in template.cells
        }
        if seen_plans and snapshot not in seen_plans:
            drift.append(f"{sorted(snapshot.items())}")
        plan = real_bind(request, origins, poses)
        for template in plan:
            if template.seated:
                seen_plans.append({
                    cell.part_id: tuple(cell.origin) for cell in template.cells})
        placement.seat_panel_plans(plan, origins, poses)
        return plan

    monkeypatch.setattr(placement, "bind_panel_plans", recording_bind)
    placement.place(_request(_templates(), iterations=150))
    assert len(seen_plans) >= 2, "the binder was never consulted per candidate"
    assert not drift, (
        "a candidate entered the binder with panel cells from no earlier plan "
        "(they were moved between binds): " + "; ".join(drift[:2])[:400])

    # Sensitivity: disable the move guard and the same observation must catch it.
    monkeypatch.setattr(placement, "panel_parts_of", lambda plans: frozenset())
    drift.clear()
    seen_plans.clear()
    placement.place(_request(_templates(), iterations=150))
    assert drift, (
        "disabling the move guard left every cell on a plan seat, so this test "
        "cannot tell the guard from a lucky seed")
