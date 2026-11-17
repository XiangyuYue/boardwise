"""548D3D-H5：候选枚举、池、最终回放消费同一个「锚点+引线+旋转+真实盒」。

任务书 `tasks/548d_flag_orientation.md`。本文件只钉三件事，全部从夹具的真实脚点、
库字形与 `_flag_rotation` 复算，不写实例坐标：

* **旗的方向由它自己的引线读**：每一枚自动旗位的 `rotation` 都是 0/180 的竖直阅读，
  且字挂在引线**末段**指向的那一侧（末段竖直 ⇒ 字不跨过锚点压回引线上）。"离 pad 更远"
  不是合法方向，也不是二次选择——`_rail_flag_seat` 已经按 room/ruler 量过它自己的答案。
* **池与最终座位是同一个字形**：`_seat_first_candidate_seats`（池）对只有一条候选的组
  记下的节点，与最终候选自己的 `occupancy` 逐节点相同；有两条以上候选的组不进池
  （池是页面事实，不是某次选择的回声）。同一页上被选中的座位两两不相交。
* **未启用 `localSeats` 的页面照旧**：不进这套分配，`_seat_first_seat_alternates` 仍只回答
  梯子的第一条（旧路径的枚举面没有被这一批扩大）。
"""

from __future__ import annotations

import test_548d_host_binding as hb

from boardwise.core.symbolprofile import (
    FLAG_GLYPH_ROTATION_OFFSETS,
    flag_glyph_kind,
)
from boardwise.engines import drawcompiler as dc

EPS = 1e-6
RAIL_NETS = ("3V3", "GND")


# --------------------------------------------------------------- 读数（库字形侧）


def _reading(seat, profile) -> float:
    """``+1`` = the glyph stands **above** its anchor, ``-1`` = below.

    方向不是 rotation 这个数本身：每种族的字形在库里有自己的偏移，所以先减去
    `FLAG_GLYPH_ROTATION_OFFSETS[kind]` 再读 0/180（`_flag_rotation` 的逆读）。
    """
    kind = flag_glyph_kind(profile)
    base = (float(seat.rotation) - FLAG_GLYPH_ROTATION_OFFSETS[kind]) % 360.0
    assert base in (0.0, 180.0), (
        f"{seat.net} flag of {seat.owner} at ({seat.anchor[0]:g}, "
        f"{seat.anchor[1]:g}) is turned {seat.rotation:g}° for a {kind!r} glyph, "
        "which is not an upright 0/180 reading")
    return 1.0 if base == 0.0 else -1.0


def _lead_hang(lead) -> float:
    """The direction the lead's **last leg** runs: ``+1`` up, ``-1`` down."""
    previous, anchor = lead[-2], lead[-1]
    assert abs(float(previous[0]) - float(anchor[0])) < EPS, (
        f"the flag's last leg {previous} -> {anchor} is not vertical: a horizontal "
        "pad escapes horizontally and turns a short vertical stub into its flag")
    step = float(anchor[1]) - float(previous[1])
    assert abs(step) > EPS, f"the flag's last leg {previous} -> {anchor} has no length"
    return 1.0 if step > 0.0 else -1.0


def _glyph_box(seat, profile):
    """The glyph alone (no name row, no clearance): what the reader sees hanging."""
    return dc.flag_glyph_box(profile, rotation=seat.rotation, anchor=seat.anchor)


# --------------------------------------------------------------- 夹具入口


def _plans(ctx, placed):
    plans, failure = dc._seat_first_plans(ctx, placed)
    assert failure is None, failure.detail
    return plans


def _seat_candidates(plans):
    """(net, group) -> every enumerated candidate that owns a real seat."""
    out: dict[tuple[str, str], list] = {}
    for plan in plans:
        for candidate in plan.candidates:
            if candidate.seat is None or candidate.seat.fixed:
                continue
            out.setdefault((plan.net, candidate.group), []).append(candidate)
    return out


def _adjacent_rail_feet(ctx, placed):
    """Pairs of **adjacent** rail feet on one part: same column, one pin pitch apart.

    This is the shape the batch is about — a power foot and a ground foot a single
    row apart on the same side, whose flags have to leave the same column. The
    pitch is read off the compile budget's lattice, not written down here.
    """
    feet = []
    for net_id in RAIL_NETS:
        for member, point in dc._seat_first_points(ctx, placed, net_id):
            if point is None:
                continue
            feet.append((
                member.partition(".")[0], round(float(point[0]), 6),
                round(float(point[1]), 6), net_id, member))
    pitch = ctx.budget.grid * 2.0
    pairs = []
    for part in sorted({item[0] for item in feet}):
        mine = sorted((item for item in feet if item[0] == part),
                      key=lambda item: (item[1], item[2]))
        for first, second in zip(mine, mine[1:]):
            if first[3] == second[3]:
                continue
            if (abs(first[1] - second[1]) < EPS
                    and abs(second[2] - first[2]) <= pitch + EPS):
                pairs.append((part, first, second))
    return pairs


# --------------------------------------------------------------- 1. 方向由引线读


def test_a_flag_hangs_along_the_last_leg_of_its_own_lead():
    ctx = hb._context()
    placed = hb._base(ctx)
    plans = _plans(ctx, placed)
    checked = 0
    for plan in plans:
        profile, ref = dc._flag_plan(ctx, plan.net, plan.cls)
        assert profile is not None, ref
        for candidate in plan.candidates:
            seat = candidate.seat
            if seat is None:
                continue
            reading = _reading(seat, profile)
            assert reading == _lead_hang(seat.lead), (
                f"{plan.net} seat of {candidate.owner} at ({seat.anchor[0]:g}, "
                f"{seat.anchor[1]:g}) hangs "
                f"{'up' if reading > 0 else 'down'} while its lead's last leg runs "
                f"{'up' if _lead_hang(seat.lead) > 0 else 'down'}: the glyph must "
                "stand on the side its own lead turns into, not on the side that "
                "happens to be farther from the pad")
            glyph = _glyph_box(seat, profile)
            assert glyph is not None, candidate.owner
            if reading > 0.0:
                assert glyph[1] >= float(seat.anchor[1]) - EPS, (
                    f"{plan.net} seat of {candidate.owner} hangs up but its glyph "
                    f"{glyph} reaches back across the anchor {seat.anchor}")
            else:
                assert glyph[3] <= float(seat.anchor[1]) + EPS, (
                    f"{plan.net} seat of {candidate.owner} hangs down but its glyph "
                    f"{glyph} reaches back across the anchor {seat.anchor}")
            checked += 1
    assert checked, "the fixture enumerated no real seat at all"


def test_an_adjacent_rail_pair_escapes_horizontally_before_it_turns():
    ctx = hb._context()
    placed = hb._base(ctx)
    plans = _plans(ctx, placed)
    pairs = _adjacent_rail_feet(ctx, placed)
    assert pairs, (
        "the fixture has no adjacent power/ground feet, so this batch's shape — a "
        "horizontal escape whose short vertical stub carries the flag — is not "
        "exercised at all")
    by_net = {plan.net: plan for plan in plans}
    covered = 0
    for _part, first, _second in pairs:
        # 每一对相邻的电源/地脚：电源侧的旗（若由这只脚承旗）必须先是水平逃逸段，
        # 再短竖直段接旗；末段与字形方向一致（上面那条测试逐枚核）。
        for _part_id, _x, _y, net_id, member in (first,):
            plan = by_net.get(net_id)
            assert plan is not None, net_id
            for candidate in plan.candidates:
                seat = candidate.seat
                if seat is None or candidate.owner != member:
                    continue
                covered += 1
                if len(seat.lead) == 3:
                    pad, corner, anchor = (
                        seat.lead[0], seat.lead[1], seat.lead[2])
                    assert abs(float(pad[1]) - float(corner[1])) < EPS, (
                        f"{net_id} flag of {member} leaves its pad "
                        f"{pad} in a slanted first leg: a horizontal foot escapes "
                        "along its own row")
                    assert (abs(float(corner[0]) - float(anchor[0])) < EPS
                            and abs(float(corner[1]) - float(anchor[1])) > EPS), (
                        f"{net_id} flag of {member} turns its lead into "
                        f"{corner} -> {anchor}, which is not the short vertical "
                        "stub a horizontal escape ends on")
                else:
                    assert len(seat.lead) == 2, (
                        f"{net_id} flag of {member} has a lead of "
                        f"{len(seat.lead)} legs: {seat.lead}")
    assert covered, (
        "no adjacent rail foot owned a flag seat on this page, so the horizontal "
        "escape shape was never measured")


# ------------------------------------------------- 1b. 备选不再被旧引线自锁


def _foot_alternates(ctx, placed, net_id, member):
    """One foot's real alternates, with the scene they were measured on."""
    solids, bodies, failure = dc._seat_first_scene(ctx, placed, ())
    assert failure is None, failure.detail
    points = dc._seat_first_points(ctx, placed, net_id)
    point = dict(points)[member]
    net = ctx.circuit.net(net_id)
    profile, ref = dc._flag_plan(
        ctx, net_id, net.cls if net is not None else "gnd")
    assert profile is not None, ref
    router, blocked = dc._seat_first_router(
        ctx, placed, net_id, solids, points)
    answers, _stop = dc._seat_first_seat_alternates(
        ctx, placed, net_id, member, point, profile, router, blocked,
        solids, bodies)
    return answers, {
        "solids": solids, "bodies": bodies, "blocked": blocked,
        "profile": profile, "point": point, "router": router, "points": points,
    }


def _escape_column(lead) -> float:
    """The x a seat's lead turns at: the corner of a bent lead, else the anchor."""
    corner = lead[1] if len(lead) > 2 else lead[-1]
    return round(float(corner[0]), 6)


def test_an_adjacent_rail_foot_is_not_locked_to_a_single_escape_column():
    ctx = hb._context()
    placed = hb._base(ctx)
    pairs = _adjacent_rail_feet(ctx, placed)
    assert pairs, "the fixture has no adjacent power/ground feet"
    two_column = []
    for _part, first, second in pairs:
        for _p, _x, _y, net_id, member in (first, second):
            answers, scene = _foot_alternates(ctx, placed, net_id, member)
            assert answers, f"{net_id} foot {member} has no seat at all"
            # 第一答案必须就是单旗默认图：同一场景下单独问一次梯子，逐值相同。
            anchor, rotation, lead, failure = dc._rail_flag_seat(
                ctx, placed, net_id, member, scene["point"],
                scene["profile"], scene["router"], scene["blocked"],
                scene["solids"], scene["bodies"])
            assert failure is None
            assert answers[0] == (anchor, float(rotation), tuple(lead)), (
                f"{net_id} foot {member}: the first alternate is not the seat the "
                "single-call ladder answers, so the default drawing would move")
            # 每条备选都在**原始场景**里各自合法：盒子不压场景墙、引线不穿场景墙。
            for answer_anchor, answer_rotation, answer_lead in answers:
                glyph = dc._flag_box(
                    scene["profile"], answer_rotation, answer_anchor, net_id)
                assert not dc._seat_first_box_problem(glyph, scene["solids"]), (
                    f"{net_id} alternate of {member} at {answer_anchor} stands on a "
                    "scene wall: an alternative must be legal on its own page")
                assert not dc._seat_first_lead_problem(
                    answer_lead, scene["solids"], scene["blocked"]), (
                    f"{net_id} alternate of {member} runs through a scene wall")
            columns = {_escape_column(lead) for _a, _r, lead in answers}
            if len(columns) > 1:
                two_column.append((net_id, member, sorted(columns)))
    assert two_column, (
        "no adjacent rail foot offered a second escape column: the walk is still "
        "locked to the first answer's turn, which is the defect this batch fixes "
        "(the real 64-pin host could then not separate U1's adjacent 3V3/GND feet)")


# --------------------------------------------------------------- 2. 池 = 最终


def _fixed_seats(ctx, placed, solids):
    """The page's fixed terminal seats, rebuilt the way the allocator enters them."""
    seats, failure = dc._seat_first_terminal_seats(ctx, placed)
    assert failure is None, failure.detail
    fixed, walls = {}, []
    for net_id, member in sorted(seats):
        anchor, lead, hang, source = seats[(net_id, member)]
        net = ctx.circuit.net(net_id)
        profile, ref = dc._flag_plan(
            ctx, net_id, net.cls if net is not None else "gnd")
        assert profile is not None, ref
        lead = tuple(tuple(point) for point in lead)
        rotation = dc._flag_rotation((0.0, hang), flag_glyph_kind(profile))
        glyph = dc._flag_box(profile, rotation, anchor, net_id)
        router, _blocked = dc._seat_first_router(
            ctx, placed, net_id, [*solids, *walls],
            dc._seat_first_points(ctx, placed, net_id))
        fixed[(net_id, member)] = dc._SeatFirstSeat(
            net=net_id, owner=member, anchor=tuple(anchor), rotation=rotation,
            lead=lead, fixed=True, source=source, glyph=glyph,
            occupancy=dc._seat_first_seat_nodes(router, lead, glyph))
        walls.append(glyph)
    return fixed, walls


def _the_pool(ctx, placed):
    """The page-wide candidate pool, on the same inputs the allocator gives it."""
    solids, bodies, failure = dc._seat_first_scene(ctx, placed, ())
    assert failure is None, failure.detail
    points_of = {
        net_id: dc._seat_first_points(ctx, placed, net_id)
        for net_id in (net.id for net in ctx.circuit.nets
                       if net.cls in ("gnd", "power") and net.members)
    }
    rails = [net_id for net_id in sorted(points_of)
             if any(point is not None for _member, point in points_of[net_id])]
    fixed, walls = _fixed_seats(ctx, placed, solids)
    expressions = dc._expressions(ctx, placed)
    detached_of = {
        net_id: frozenset(
            getattr(expressions.get(net_id), "detached", ()) or ())
        for net_id in rails
    }
    return dc._seat_first_candidate_seats(
        ctx, placed, rails, points_of, solids, bodies, fixed, {}, detached_of,
        walls)


def test_the_pool_reads_the_same_glyph_the_final_seat_was_chosen_from():
    ctx = hb._context()
    placed = hb._base(ctx)
    plans = _plans(ctx, placed)
    pool = _the_pool(ctx, placed)
    candidates = _seat_candidates(plans)
    assert candidates, "no automatic group was enumerated"

    forced = {key: value[0] for key, value in candidates.items()
              if len(value) == 1}
    alternatives = {key for key, value in candidates.items() if len(value) > 1}
    assert forced, (
        "no group has a forced seat, so the pool comparison below would be vacuous")

    # 最终回放的座位必须是**已枚举候选**的同一条（anchor/lead/rotation 逐值相同），
    # 且它的盒子就是那个 rotation 在库字形上的盒子——"候选、池、回放同一个字形"。
    for plan in plans:
        for assignment in plan.assignments:
            seat = assignment.seat
            if seat.fixed:
                continue
            profile, ref = dc._flag_plan(ctx, plan.net, plan.cls)
            assert profile is not None, ref
            assert seat.glyph == dc._flag_box(
                profile, seat.rotation, seat.anchor, plan.net), (
                f"{plan.net}/{assignment.group}: the replayed glyph is not the "
                "glyph of the rotation the seat carries")
            same = [
                candidate for candidate in plan.candidates
                if candidate.seat is not None
                and tuple(candidate.seat.anchor) == tuple(seat.anchor)
                and tuple(candidate.seat.lead) == tuple(seat.lead)
                and abs(float(candidate.seat.rotation) - float(seat.rotation)) < EPS
            ]
            assert same, (
                f"{plan.net}/{assignment.group}: the seat the joint selection "
                "replayed was not one of the enumerated candidates, so some "
                "consumer re-derived it")

    # 池里每一个 (net, group) 都必须是"页面上只有一条候选"的组——有备选的组不进池，
    # 否则会用自己的另一条答案把自己拒掉。被钉住的组，节点必须逐点等于最终候选自己的
    # 座位（同一个 anchor/lead/rotation/glyph）。本夹具在 H6 之后每个自动组都有备选，
    # 池因此是空的、判断落在联合分配上；规则本身仍逐条核。
    pooled = {key for owners in pool.values() for key in owners}
    assert pooled <= set(forced), (
        f"the pool pinned {sorted(pooled - set(forced))} although those groups have "
        "several candidates: a group with alternatives is resolved by the joint "
        "selection, not pinned page-wide")
    for key in pooled:
        pool_nodes = {node for node, owners in pool.items() if key in owners}
        assert pool_nodes == set(forced[key].seat.occupancy), (
            f"the pool and the final candidate of {key} disagree by "
            f"{len(pool_nodes ^ set(forced[key].seat.occupancy))} node(s): the pool "
            "must be built from the same anchor/lead/rotation/glyph the final "
            "seat was chosen from")
    for key in alternatives:
        assert not any(key in owners for owners in pool.values()), (
            f"{key} has several candidates and must not be pinned in the pool: "
            "pinning every alternative refuses the group with its own other answer")

    # 被选中的座位之间两两不相交：联合分配给出的答案是一张没有两旗相压的图。
    chosen = [assignment.seat
              for plan in plans for assignment in plan.assignments]
    for index, first in enumerate(chosen):
        for second in chosen[index + 1:]:
            assert not (set(first.occupancy) & set(second.occupancy)), (
                f"the chosen seats of {first.net}/{first.owner} and "
                f"{second.net}/{second.owner} claim the same lattice node")


# --------------------------------------------------------------- 3. 旧路径不变


def test_a_page_without_local_seats_keeps_the_old_single_answer_ladder():
    ctx = hb._context(local_seats=False)
    placed = hb._base(ctx)
    assert dc._service_layout_page(ctx.presentation) is False
    assert dc._service_seats_stated(ctx.presentation) is False
    plans, failure = dc._seat_first_plans(ctx, placed)
    assert failure is None and plans == (), (
        "a page without localSeats must not enter the seat-first allocation")

    solids, bodies, failure = dc._seat_first_scene(ctx, placed, ())
    assert failure is None, failure.detail
    points = dc._seat_first_points(ctx, placed, "3V3")
    member, point = next(
        (member, point) for member, point in points if point is not None)
    profile, ref = dc._flag_plan(ctx, "3V3", "power")
    assert profile is not None, ref
    router, blocked = dc._seat_first_router(
        ctx, placed, "3V3", solids, points)
    answers, _stop = dc._seat_first_seat_alternates(
        ctx, placed, "3V3", member, point, profile, router, blocked,
        solids, bodies)
    assert len(answers) <= 1, (
        "the old path must keep asking the flag ladder once: it has no alternate "
        f"enumeration, but {len(answers)} answers came back for {member}")
    for anchor, rotation, lead in answers:
        assert abs(float(rotation) % 180.0) < EPS, (
            f"the old path turned a flag to {rotation:g}°, which is not an upright "
            "0/180 reading")
        assert abs(float(anchor[1]) - float(lead[-1][1])) < EPS
