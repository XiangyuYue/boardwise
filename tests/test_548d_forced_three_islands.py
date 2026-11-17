"""548D3D-T1: 强制 topology 轮的三岛组合 —— **真实产图**，不许 base 梯子兜底。

任务书 `tasks/548d_forced_three_islands.md`（含 T1A 根因裁决），证据
`evidence/548D/host-binding/three-island/analysis/README.md` 与
`.../implementation/report.json`。

本文件钉四件事：

1. **禁止 base 兜底**：`dc._variants` / `dc._widened_variants` 都置空后，`baseline` 与
   `port-native` 两例仍然 ok，mcu/keys/led 三岛全出真实候选——图是 topology 轮
   （`placement.place` + 回放）画的，不是构造梯子画的；`_place_chain_and_shelf` 一次都不许被调用。
2. **图本身**：keys 四支同姿、同列、同节距，四支共同回流旗同 x、同向、同节距（节距 = 支路节距）；
   逐脚 `_per_pin_problems` 空、`readability.check_page` hard 空。
3. **base 不变**：同一规格走正常梯子时，页几何摘要仍是本批前的那一个。
4. **同网兄弟旗的真实盒防线**（T1A 第二道）：预占与回放都不得让两面同网旗站进同一个 glyph
   ——预占重盒被拒（只留一个座位），回放重盒被丢弃（落回普通梯），绝不交给 readability 收尾。
"""

from __future__ import annotations

import dataclasses

import pytest

import test_548d_semantic_islands as t

from boardwise.engines import grammar
from boardwise.engines import drawcompiler as dc
from boardwise.engines import pagecompiler as pc
from boardwise.engines import readability


#: The page geometry the constructive ladder draws for `_island_spec()` — pinned
#: so a change in the topology projection cannot move the base drawing.
BASE_GEOMETRY = (
    "5e05808383e642639b0d73b9c3e25673025c71f955f61ce6e4b5f7d0c1d2de21"
)


class _Forced:
    """The forced topology round: both constructive ladders are emptied."""

    def __enter__(self):
        self._variants, self._widened = dc._variants, dc._widened_variants
        dc._variants = lambda _ctx: []
        dc._widened_variants = lambda _ctx, _result: []
        return self

    def __exit__(self, *exc):
        dc._variants, dc._widened_variants = self._variants, self._widened
        return False


def _cases():
    """The two readings the probe compiles: default text and native attribute."""
    spec = t._island_spec()
    return {
        "baseline": spec,
        "port-native": dataclasses.replace(
            spec,
            label_policy=dataclasses.replace(spec.label_policy, stub_min=40.0),
            text_placement="native-attr",
        ),
    }


def _keys_geometry(plan):
    """The keys island as a reader sees it: seats, poses, flags, leads."""
    parts = sorted(
        (part for part in plan.parts if part.part_id in t.KEY_PARTS),
        key=lambda part: part.part_id,
    )
    flags = [item for item in plan.power_symbols if item.net == "3V3"]
    leads = [item for item in plan.segments if item.net == "3V3"]
    return parts, flags, leads


def _gaps(values):
    return [round(b - a, 6) for a, b in zip(values, values[1:])]


# ------------------------------------------------------- 1. 强制 topology 真出图


@pytest.mark.parametrize("name", ["baseline", "port-native"])
def test_the_forced_topology_round_draws_both_readings(name, monkeypatch):
    spec = _cases()[name]
    constructed = []
    real_chain = dc._place_chain_and_shelf

    def refused(*args, **kwargs):
        constructed.append(args)
        return real_chain(*args, **kwargs)

    monkeypatch.setattr(dc, "_place_chain_and_shelf", refused)
    board = t._circuit()
    with _Forced():
        result = pc.compile_page(board, spec, t._book(), t.PAGE)

    assert constructed == [], (
        "the constructive ladder was called although both variant lists were "
        "emptied — the base ladder is not allowed to draw this page"
    )
    assert result.ok, result.render_failures()
    assert {key: value.ok for key, value in result.modules.items()} == {
        "mcu": True, "keys": True, "led": True,
    }, result.render_failures()
    page = result.best()
    plan = page.plan
    notes = result.modules["keys"].notes
    assert any("topology search was run" in note for note in notes), notes

    # The independent readings: every pin on its own net, no page hard at all.
    assert t._per_pin_problems(plan, board, t._book()) == []
    check = readability.check_page(page, board, spec, t._book())
    assert check.hard_violations == [], [
        item.render() for item in check.hard_violations
    ]

    parts, flags, _leads = _keys_geometry(plan)
    # the mcu island states 3V3 too: this reading is the keys column's own flags
    flags = [item for item in flags
             if any(abs(item.x - part.x) <= 1e-6 for part in parts)]
    assert [part.part_id for part in parts] == list(t.KEY_PARTS)
    # one pose, one column, one pitch
    assert len({(part.rotation, part.mirror) for part in parts}) == 1, [
        (part.part_id, part.rotation, part.mirror) for part in parts
    ]
    assert len({round(part.x, 6) for part in parts}) == 1, [
        (part.part_id, part.x, part.y) for part in parts
    ]
    pitch = _gaps([part.y for part in parts])
    assert len(set(pitch)) == 1 and abs(pitch[0]) > 0.0, pitch
    # ... and the four common-return flags are one family on that column
    assert len(flags) == len(t.KEY_PARTS), [
        (item.net, item.x, item.y) for item in plan.power_symbols
    ]
    assert len({round(item.x, 6) for item in flags}) == 1, [
        (item.x, item.y, item.rotation) for item in flags
    ]
    assert len({item.rotation for item in flags}) == 1, [
        (item.x, item.y, item.rotation) for item in flags
    ]
    flag_pitch = _gaps(sorted(item.y for item in flags))
    assert len(set(flag_pitch)) == 1, flag_pitch


def test_the_drawing_is_the_topology_rounds_own_not_the_base_page():
    board = t._circuit()
    spec = t._island_spec()
    base = pc.compile_page(board, spec, t._book(), t.PAGE)
    assert base.ok, base.render_failures()
    assert base.best().plan.geometry_sha256() == BASE_GEOMETRY, (
        "the constructive ladder's page moved: "
        f"{base.best().plan.geometry_sha256()}"
    )
    with _Forced():
        forced = pc.compile_page(board, spec, t._book(), t.PAGE)
    assert forced.ok, forced.render_failures()
    assert forced.best().plan.geometry_sha256() != BASE_GEOMETRY, (
        "the forced page is the base page — the base ladder drew it after all"
    )


def test_without_the_projection_the_gate_passes_but_the_island_is_a_scatter(monkeypatch):
    """Why the projection is load-bearing: the machine gate alone says nothing.

    With the projection switched off the page compiles — but the keys island is
    the search's own scatter (mixed poses, two rows, four flags in four places),
    which is exactly the "no hard error but not a column" drawing 548D3B7 exists
    to prevent. The column is asserted in the test above, not here.
    """
    monkeypatch.setattr(dc, "_project_coreless_column", lambda *_args: None)
    board = t._circuit()
    for name, spec in _cases().items():
        with _Forced():
            result = pc.compile_page(board, spec, t._book(), t.PAGE)
        if not result.ok:
            # A refused reading is not a column either; the claim below is about
            # what a passing unprojected drawing looks like.
            continue
        parts, flags, _leads = _keys_geometry(result.best().plan)
        poses = {(part.rotation, part.mirror) for part in parts}
        assert len(poses) > 1, f"{name}: the unprojected drawing is a column"
        assert len({round(part.x, 6) for part in parts}) > 1, name


# ------------------------------------------- 2. 同网兄弟旗：预占与回放的真实盒防线


def _keys_placement():
    """The keys island's base placement — the picture the reservation pass sees."""
    circuit, presentation, book = t._keys_ledger(), t._keys_spec(), t._book()
    binding = grammar.bind(circuit, presentation, book)
    ctx = dc._prepare(
        circuit, presentation, binding, book, dc.CompileBudget(),
    ).context
    assert ctx is not None
    placed, failure = dc._place(ctx, dc._variants(ctx)[0])
    assert failure is None and placed is not None
    return ctx, placed, circuit, presentation, book


def _reserve(ctx, placed):
    router = dc._Router(
        grid=ctx.budget.grid, residue=placed.residue, boxes=[],
        bounds=(0.0, 0.0, 1169.0, 826.0),
    )
    expressions = dc._expressions(ctx, placed)
    dc._lead_lane_reservations(
        ctx, placed, expressions, dc._net_order(ctx, expressions), router,
        list(ctx.budget.keepouts), list(ctx.budget.keepouts), [],
    )
    return router


def test_the_port_native_page_draws_no_lead_across_a_foreign_run():
    """548D3D-T1B: the port reading's BOOT0 run may not cut the service leads.

    The flag seats and the ordinary signals are two halves of one picture. The
    machine gate measures neither the crossing (it is legal ink) nor the pair;
    the port page therefore grades the spans itself — measured before the fix,
    `BOOT0` cut both service leads on this very page.
    """
    board = t._circuit()
    spec = _cases()["port-native"]
    with _Forced():
        result = pc.compile_page(board, spec, t._book(), t.PAGE)
    assert result.ok, result.render_failures()
    plan = result.best().plan
    anchors = {(round(item.x, 6), round(item.y, 6)) for item in plan.power_symbols}
    leads, wires = [], []
    for segment in plan.segments:
        points = [(round(x, 6), round(y, 6)) for x, y in segment.points]
        (leads if any(point in anchors for point in points) else wires).append(
            (segment.net, points))
    hits = []
    for net_a, a in leads:
        for net_b, b in wires:
            if net_a == net_b:
                continue
            for start, end in zip(a, a[1:]):
                for other_start, other_end in zip(b, b[1:]):
                    point = dc._proper_crossing(start, end, other_start, other_end)
                    if point is not None:
                        hits.append((net_a, net_b, start, end, point))
    assert hits == [], f"a flag lead is cut by a foreign run: {hits}"
    boot0 = [
        (net, [point for point in points]) for net, points in wires
        if net == "BOOT0"
    ]
    assert len(boot0) == 1, boot0
    for net, points in boot0:
        for other_net, runs in leads:
            if other_net not in ("3V3", "GND"):
                continue
            for start, end in zip(points, points[1:]):
                for lead_start, lead_end in zip(runs, runs[1:]):
                    assert dc._proper_crossing(
                        start, end, lead_start, lead_end) is None, (
                        f"{net} cuts {other_net}'s lead at "
                        f"{dc._proper_crossing(start, end, lead_start, lead_end)}"
                    )


def test_a_same_net_sibling_may_not_reserve_a_drawn_flags_room(monkeypatch):
    """Two members of one net forced onto one seat: the **second** is refused.

    The same-net exemption in `_take_lane` is about a wire of one net crossing
    its own lead — it is not a licence for two sibling flags to stand in one
    glyph. The guard is the real flag box, so it holds whatever cells the lanes
    happen to share.
    """
    ctx, placed, _circuit, _presentation, _book = _keys_placement()
    real = dc._flag_pin_lead
    first: dict[str, object] = {}

    def alias(ctx_, placed_, net_id, profile, member, point, router, blocked,
              solids, bodies=None, **kwargs):
        answer = real(ctx_, placed_, net_id, profile, member, point, router,
                      blocked, solids, bodies, **kwargs)
        if net_id != "3V3":
            return answer
        first.setdefault("seat", answer)
        return first["seat"]

    monkeypatch.setattr(dc, "_flag_pin_lead", alias)
    router = _reserve(ctx, placed)
    seats = [key for key in router.flag_seats if key[0] == "3V3"]
    assert len(seats) == 1, (
        "two same-net flags reserved one room: "
        f"{[(key, router.flag_seats[key][0]) for key in seats]}"
    )
    boxes = [
        dc._flag_box(_book["PWR-3V3"], router.flag_seats[key][1],
                     router.flag_seats[key][0], "3V3")
        for key in seats
    ]
    assert not any(
        dc._overlaps(box, other) for index, box in enumerate(boxes)
        for other in boxes[index + 1:]
    ), boxes


def test_a_replayed_lane_that_holds_a_siblings_flag_is_dropped(monkeypatch):
    """A duplicate promised seat is dropped at replay, never drawn twice.

    The picture is the unprojected forced round — the scatter the replay branch
    exists for — with every member of the return net handed the **same** promised
    seat. Only the first may keep it: the replay now measures its box against the
    sibling flags this call already drew (`occupied`/`solids`), not just against
    `router.boxes`, which held no flag at all.
    """
    real_lanes = dc._lead_lane_reservations
    duplicated: list[tuple[float, float]] = []

    def lanes(ctx, placed, expressions, order, router, occupied, solids, bodies,
              ordinary_seats=None):
        result = real_lanes(ctx, placed, expressions, order, router, occupied,
                            solids, bodies, ordinary_seats)
        keys = [key for key in sorted(router.flag_seats) if key[0] == "3V3"]
        for key in keys[1:]:
            router.flag_seats[key] = router.flag_seats[keys[0]]
        if keys:
            duplicated.append(tuple(router.flag_seats[keys[0]][0]))
        return result

    monkeypatch.setattr(dc, "_lead_lane_reservations", lanes)
    monkeypatch.setattr(dc, "_project_coreless_column", lambda *_args: None)

    circuit, presentation, book = t._keys_ledger(), t._keys_spec(), t._book()
    with _Forced():
        result = pc.compile_page(circuit, presentation, book, t.PAGE)
    assert duplicated, "the reservation pass never promised a 3V3 lane"
    assert result.ok, result.render_failures()
    flags = [
        item for item in result.best().plan.power_symbols if item.net == "3V3"
    ]
    assert len(flags) == len(t.KEY_PARTS), [
        (item.net, item.x, item.y) for item in flags
    ]
    assert len({(item.x, item.y) for item in flags}) == len(flags), (
        "two same-net flags were drawn in one room: "
        f"{[(item.x, item.y) for item in flags]}"
    )
    # 548D3D-B 负例：本趟画下的旗是后续导线的墙。没有这条，replay 自己那枚
    # powerSymbol 会被同趟的线穿过（实测 `wire-through-body segments[2] +
    # powerSymbols[1]`）——所以这里直接量「没有任何线穿任何已画旗的图元盒」。
    plan = result.best().plan
    glyphs = [
        dc.flag_glyph_box(book[symbol.symbol_ref], rotation=symbol.rotation,
                          anchor=(symbol.x, symbol.y))
        for symbol in plan.power_symbols
    ]
    for segment in plan.segments:
        for start, stop in zip(segment.points, segment.points[1:]):
            for box in glyphs:
                assert box is None or not dc._segment_hits_box(start, stop, box), (
                    f"a conductor of {segment.net!r} runs through the drawn "
                    f"extent of a flag at {box}"
                )
