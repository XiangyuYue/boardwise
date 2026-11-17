"""548D3D-P1A：service 页用 `labelPolicy.stubMin` 声明端口列时的**几何合同**。

任务书 `tasks/548d_host_port_columns.md`（P1A 裁决）。本文件只钉可观察的几何事实：

* 同一 `(part, 实际出脚方向)` 的端口**一条桩长、一列锚点**——不是逐脚偶然值；
* 每个名字都站在**自己原脚**发出来的一段真实 conductor 的 far 端（anchor 与 box 一起走）；
* 首选长度就是文档写的那个数（17/25/40 都逐值照做），生产不硬编码 40；
* 不写 `stubMin` 的页保持旧行为：名字仍在脚上、没有 carrier；
* 审计对"名字没有自己的段"具名拒绝（缺段负例）；
* 同输入两次调用 labels 与 carriers 一致。

几何期望全部由本文件从夹具（`test_548d_semantic_islands` + `test_548d_host_binding` 的
模块视图）重算：脚点由 `transform_point` 按 plan 自己的位姿落到页面，不写坐标表。
"""

from __future__ import annotations

import dataclasses

import test_548d_host_binding as hb
import test_548d_semantic_islands as t

from boardwise.core.geometry import transform_point
from boardwise.engines import drawcompiler as dc

STATED = 40.0
EPS = 1e-6


# ------------------------------------------------------------------ 夹具入口


def _spec(stub_min: float):
    circuit, spec = hb._module_view()
    policy = dataclasses.replace(spec.label_policy, stub_min=stub_min)
    return circuit, dataclasses.replace(spec, label_policy=policy)


def _plan(stub_min: float):
    circuit, spec = _spec(stub_min)
    book = t._book()
    result = dc.compile(circuit, spec, book, dc.CompileBudget(max_candidates=1))
    assert result.ok, [f.detail for f in result.failures]
    return circuit, book, result.best()


def _placed(stub_min: float):
    circuit, spec = _spec(stub_min)
    book = t._book()
    binding = dc.bind_grammar(circuit, spec, book)
    assert binding.ok, [item.detail for item in binding.failures]
    binding = dc._with_panel_groups(binding, spec, circuit)
    prepared = dc._prepare(
        circuit, spec, binding, book, dc.CompileBudget(max_candidates=4))
    assert prepared.context is not None, [f.detail for f in prepared.failures]
    return prepared.context, hb._base(prepared.context)


# ------------------------------------------------------------------ 独立几何


def _members(circuit):
    """每个 label-style 网在本页上的脚（`part.token`），按网名排序。"""
    return {
        net.id: tuple(sorted(net.members))
        for net in circuit.nets if len(net.members) == 1
    }


def _tip(plan, book, circuit, net_id):
    _part_id, _dot, token = _members(circuit)[net_id][0].partition(".")
    part = next(item for item in plan.parts if item.part_id == _part_id)
    profile = book[circuit.part(_part_id).symbol_ref]
    pin = next(item for item in profile.pins
               if item.number == token or item.name == token)
    return transform_point(
        pin.tip[0], pin.tip[1], rotation=part.rotation, mirror=part.mirror,
        ox=part.x, oy=part.y,
    )


def _runs(plan, net_id):
    return [item for item in plan.segments if item.net == net_id]


def _length(start, end):
    return abs(end[0] - start[0]) + abs(end[1] - start[1])


# --------------------------------------------------------------------- 合同


def test_one_part_side_takes_one_stub_length_and_one_column():
    """同侧六个端口：一条桩长、一列锚点（成对/同类支路默认一致）。"""
    circuit, book, plan = _plan(STATED)
    lengths, columns = {}, set()
    for net_id, _member in _members(circuit).items():
        runs = _runs(plan, net_id)
        assert len(runs) == 1, (net_id, runs)
        start, end = runs[0].points[0], runs[0].points[-1]
        assert abs(_length(start, end) - STATED) < EPS, (net_id, start, end)
        lengths[net_id] = round(_length(start, end), 6)
        columns.add(round(end[0], 6))
    assert set(lengths.values()) == {STATED}, lengths
    assert len(columns) == 1, columns


def test_every_port_name_stands_at_the_far_end_of_its_own_run():
    """原脚 → far → label：名字的 anchor 与 box 都在 far，段从原脚起。"""
    circuit, book, plan = _plan(STATED)
    for net_id in _members(circuit):
        label = next(item for item in plan.labels if item.net == net_id)
        tip = _tip(plan, book, circuit, net_id)
        runs = _runs(plan, net_id)
        start, end = runs[0].points[0], runs[0].points[-1]
        assert (abs(start[0] - tip[0]) < EPS and abs(start[1] - tip[1]) < EPS), (
            net_id, start, tip)
        assert abs(label.x - end[0]) < EPS and abs(label.y - end[1]) < EPS, (
            net_id, (label.x, label.y), end)
        assert label.stub_min == STATED, (net_id, label.stub_min)
        # the box is typography beside the far end, never back on the pin
        near = min(abs(label.bbox[0] - label.x), abs(label.bbox[2] - label.x))
        assert near > 0.0 and not (label.bbox[0] <= tip[0] <= label.bbox[2]), (
            net_id, label.bbox, tip)


def test_the_stated_length_is_drawn_verbatim_not_a_production_constant():
    """首选长度是文档的数：17、25 都逐值照做，整组同一个数。"""
    for stated in (17.0, 25.0):
        circuit, _book, plan = _plan(stated)
        lengths = set()
        for net_id in _members(circuit):
            runs = _runs(plan, net_id)
            assert len(runs) == 1, (stated, net_id, runs)
            lengths.add(round(_length(runs[0].points[0], runs[0].points[-1]), 6))
        assert lengths == {stated}, (stated, lengths)


def test_a_page_without_a_stated_length_keeps_its_bare_labels():
    """不写 stubMin：名字仍在脚上，没有 carrier（旧行为逐字节）。"""
    circuit, book, plan = _plan(0.0)
    for net_id in _members(circuit):
        label = next(item for item in plan.labels if item.net == net_id)
        tip = _tip(plan, book, circuit, net_id)
        assert abs(label.x - tip[0]) < EPS and abs(label.y - tip[1]) < EPS, (
            net_id, (label.x, label.y), tip)
        assert label.stub_min == 0.0, (net_id, label.stub_min)
        assert not _runs(plan, net_id), (net_id, _runs(plan, net_id))


def test_a_port_name_with_no_run_of_its_own_is_refused():
    """缺段负例：拆掉一条 carrier，审计必须具名拒绝，不许静默通过。"""
    circuit, _book, plan = _plan(STATED)
    ctx, placed = _placed(STATED)
    terminal = dc._seat_first_path_first_terminal(ctx, placed)
    assert terminal.ok, [item.detail for item in terminal.refusals]
    assert not dc._path_first_audit(ctx, placed, terminal, plan), [
        item.detail for item in dc._path_first_audit(ctx, placed, terminal, plan)]
    target = sorted(_members(circuit))[0]
    broken = dataclasses.replace(
        plan, segments=[item for item in plan.segments if item.net != target])
    failures = dc._path_first_audit(ctx, placed, terminal, broken)
    assert any(
        item.subject == f"net {target!r}" and "no carrier" in item.detail
        for item in failures), [item.detail for item in failures]


def test_the_same_page_replays_the_same_columns():
    """同输入两次：labels 与 carriers 逐值一致（terminal 自己的 replay 也核）。"""
    ctx, placed = _placed(STATED)
    first = dc._seat_first_path_first_terminal(ctx, placed)
    second = dc._seat_first_path_first_terminal(ctx, placed)
    assert first.ok and second.ok, (
        [item.detail for item in first.refusals],
        [item.detail for item in second.refusals])
    assert first.labels == second.labels
    assert first.carriers == second.carriers
    assert first.carriers, "the replay page states no carrier at all"


def test_a_conductor_wall_moves_the_whole_group_off_the_preferred_rung():
    """导体墙负例：首选档被既有导线挡住 → 整组换档，且所有段与该墙无交。

    旧缺陷识别器：P1A 的 `_local_label_candidate` 只量格点/名字行/占道，看不见
    "整条直桩跨过一道既有导体"——真实 64 页 LED1/2 的 40 桩就是这样横穿了两条电源/
    地引线，机器闸仍全绿。本用例把一道真实墙体（旗引线/通道的盒子形状）放在首选 40
    档的跨度中央：整组必须一起退到能过 `_span_free` 的档，且没有任何段压在这道墙上。
    """
    ctx, placed = _placed(STATED)
    terminal = dc._seat_first_path_first_terminal(ctx, placed)
    assert terminal.ok, [item.detail for item in terminal.refusals]
    labels = dc._seat_first_label_map(ctx, placed, terminal.scene, (), (), ())
    # the names' own page: parts, rows and texts, but **not** this pass's own
    # carrier spans (the terminal's scene holds those, and a carrier is never an
    # obstacle to itself)
    bare = dc._seat_first_scene_of(ctx, placed, terminal.scene.texts)
    # the preferred rung, with nothing in the way
    _labels, carriers_free, failure = dc._seat_first_port_columns(
        ctx, placed, bare, (), labels, ())
    assert failure is None
    clear = {round(_length(item.points[0], item.points[-1]), 6)
             for item in carriers_free}
    assert clear == {STATED}, clear
    # a real conductor wall across the 40-unit rung of the top pin only
    wall = (103.0, 36.0, 112.0, 44.0)
    out, carriers, failure = dc._seat_first_port_columns(
        ctx, placed, bare, (wall,), labels, ())
    assert failure is None, failure.detail
    lengths = {round(_length(item.points[0], item.points[-1]), 6)
               for item in carriers}
    assert len(lengths) == 1, lengths
    assert STATED not in lengths, lengths
    assert max(lengths) < STATED, lengths
    for item in carriers:
        for start, end in zip(item.points, item.points[1:]):
            assert not dc._segment_hits_box(start, end, wall), (item.net, wall)
    # the label states the run that was drawn, not the page's first preference:
    # otherwise the apply layer would leave a stub of a different length
    stated = {label.net: label.stub_min for _net, _point, label in out}
    assert set(stated.values()) == lengths, (stated, lengths)
    assert all(item != STATED for item in stated.values()), stated


def test_one_part_side_reads_in_one_box_column():
    """同 (part, 出脚方向) 的 label **阅读盒近边**也同列，不只 anchor 同列。

    P1B 只钉了 anchor 同列；主代理放大图看到 LED1 近边 -128、LED2 近边 -151.5，
    根因是旗位按裸 label 场景先定，port 生成最终 label 后没有重跑联合分配。P1C 把
    label 盒与 carrier 跨度墙放回 scene 重排旗位后，同侧的名字必须落在一条近边上。
    """
    circuit, _book, plan = _plan(STATED)
    groups: dict[tuple[str, tuple[float, float]], set[float]] = {}
    for net_id, member in _members(circuit).items():
        label = next(item for item in plan.labels if item.net == net_id)
        part_id, _, token = member[0].partition(".")
        direction = next(
            (item for item in plan.parts if item.part_id == part_id), None)
        assert direction is not None
        side = (part_id, 0)  # one page side: the fixture's ports share one
        near = round(label.bbox[0] if label.bbox[0] > label.x else label.bbox[2], 6)
        groups.setdefault(side, set()).add(near)
    assert all(len(edges) == 1 for edges in groups.values()), groups


def _native_plan(stub_min: float):
    circuit, spec = _spec(stub_min)
    spec = dataclasses.replace(spec, text_placement="native-attr")
    book = t._book()
    result = dc.compile(circuit, spec, book, dc.CompileBudget(max_candidates=1))
    assert result.ok, [f.detail for f in result.failures]
    return circuit, book, result.best()


def test_native_attr_marks_each_port_name_and_keeps_its_own_carrier():
    """native-attr：每个端口 label 带 native text mode，anchor 仍站在自己的 carrier 上。

    旧缺陷：path-first 的 plan 在 `_native_label_dedupe` 之后才组装，六个名字进 plan
    却没有 label text（CLI `draw plan` 实测）。现在同一 pass 在这条组装路径上也跑一次：
    独立 carrier 各留一个名字并标 `native`；普通（非 native-attr）页的 `text_mode` 仍为空。
    """
    circuit, _book, plan = _native_plan(STATED)
    for net_id in _members(circuit):
        label = next(item for item in plan.labels if item.net == net_id)
        assert label.text_mode == dc.TEXT_MODE_NATIVE, (net_id, label.text_mode)
        runs = _runs(plan, net_id)
        assert len(runs) == 1, (net_id, runs)
        end = runs[0].points[-1]
        assert abs(label.x - end[0]) < EPS and abs(label.y - end[1]) < EPS, (
            net_id, (label.x, label.y), end)
    _c, _b, plain = _plan(STATED)
    for net_id in _members(circuit):
        label = next(item for item in plain.labels if item.net == net_id)
        assert label.text_mode == "", (net_id, label.text_mode)
