"""548D3F §21C：已落定旗引线必须在对线上真正被预留（一条漏检）。

实测缺口（`evidence/548D/full-page/wifi-ground.md` §7）：WiFi 岛的 `3V3` 旗引线是
`(-30,40) -> (-60,40) -> (-60,27.5)`——末点是半档 `FLAG_JOG/2`，不在格线上。
`_remember_lead` 只按格步采样再取整，登记到了 `(-60,30)`，而路由器随后沿 `y=35`
布出的 GND 主干**真实穿过** `(-60,35)`，那个点谁也没预留，闸也不查「导线穿已落旗引线」，
于是整页机器全绿、图上跨线。21C 的修法是：把已落定引线的**连续段与格线的真实交点**
登记进既有的预留簿（`_Router.reserved`），不移动锚、不加半格车道、不改引线选择。

本文件从图上/从簿上独立读，不信 `ok`：预留点、外来网拒绝、同网豁免、绕行合法、
外来针脚不覆盖、无引线时旧行为，以及真实 WiFi 几何的拒绝与「无跨线」不变量。
"""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import FLAG_GLYPH_KIND_RAIL, SymbolProfile
from boardwise.engines import drawcompiler as dc
from boardwise.engines import pagecompiler as pc

FROZEN = "evidence/547/a"
GRID = 5.0


def _router():
    return dc._Router(
        grid=GRID, residue=(0.0, 0.0), boxes=[], bounds=(-400.0, -200.0, 400.0, 200.0)
    )


# ------------------------------------------------ 簿上的直接读数（不跑编译）
def test_a_settled_lead_promises_the_points_its_run_really_crosses():
    router = _router()
    lead = [(-30.0, 40.0), (-60.0, 40.0), (-60.0, 27.5)]
    dc._remember_lead(router, "3V3", FLAG_GLYPH_KIND_RAIL, lead)
    # 竖直段 y 27.5..40 真正穿过 y=35 与 y=30 两条格线；端点 27.5 不在格线上
    assert (-60.0, 35.0) in router.reserved, sorted(router.reserved)
    assert router.reserved[(-60.0, 35.0)] == "3V3"
    assert (-60.0, 30.0) in router.reserved
    # 水平段的交点也在簿上（y=40 这一行）
    assert router.reserved[(-50.0, 40.0)] == "3V3"
    # 引线自身不在格线上的那一段没有伪造车道
    assert (-60.0, 27.5) not in router.reserved


def test_a_foreign_wire_that_crosses_the_lead_is_refused_and_a_detour_is_not():
    router = _router()
    dc._remember_lead(router, "3V3", FLAG_GLYPH_KIND_RAIL,
                      [(-30.0, 40.0), (-60.0, 40.0), (-60.0, 27.5)])
    # 21C 前实测跨过的那条：y=35 从 -75 到 -30
    assert dc._reserved_hits(router, (-75.0, 35.0), (-30.0, 35.0)) is True
    # 合法绕行：从引线端点 27.5 以下过去（y=25），不穿过引线
    assert dc._reserved_hits(router, (-75.0, 25.0), (-30.0, 25.0)) is False
    # 引线自己的网不被自己挡住（`reserved_exempt`）
    router.reserved_exempt = "3V3"
    assert dc._reserved_hits(router, (-75.0, 35.0), (-30.0, 35.0)) is False
    router.reserved_exempt = ""
    assert dc._reserved_hits(router, (-75.0, 35.0), (-30.0, 35.0)) is True


def test_an_earlier_owner_and_a_foreign_pin_are_never_covered():
    router = _router()
    router.reserved[(-60.0, 35.0)] = "GND"          # 已有预留：先到先得
    router.blocked.add((-60.0, 30.0))               # 外来针脚/标签/旗
    dc._remember_lead(router, "3V3", FLAG_GLYPH_KIND_RAIL,
                      [(-30.0, 40.0), (-60.0, 40.0), (-60.0, 27.5)])
    assert router.reserved[(-60.0, 35.0)] == "GND"
    assert (-60.0, 30.0) not in router.reserved


def test_without_a_settled_lead_nothing_is_promised():
    router = _router()
    dc._remember_lead(router, "3V3", FLAG_GLYPH_KIND_RAIL, None)
    assert router.reserved == {}
    # 一条落在格线上的水平引线只登记它自己那一行的交点，不散布到别行
    dc._remember_lead(router, "3V3", FLAG_GLYPH_KIND_RAIL,
                      [(-30.0, 40.0), (-60.0, 40.0)])
    assert set(router.reserved) == {
        (-60.0, 40.0), (-55.0, 40.0), (-50.0, 40.0), (-45.0, 40.0),
        (-40.0, 40.0), (-35.0, 40.0), (-30.0, 40.0),
    }


# ------------------------------------------------ 真实 WiFi 几何（冻结 547A）
def _wifi():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    circuit = CircuitSpec.from_dict(json.loads(
        (root / FROZEN / "smart_medicine_box.circuit.json").read_text(encoding="utf-8")))
    presentation = PresentationSpec.from_dict(json.loads(
        (root / FROZEN / "smart_medicine_box.presentation.json").read_text(encoding="utf-8")))
    library = json.loads(
        (root / FROZEN / "smart_medicine_box.library.json").read_text(encoding="utf-8"))
    rows = library.get("symbols") or library.get("profiles") or library
    if isinstance(rows, dict):
        rows = list(rows.values())
    book = {row["symbolRef"]: SymbolProfile.from_dict(row)
            for row in rows if isinstance(row, dict) and "symbolRef" in row}
    idx = {module.id: module for module in presentation.modules}
    sub_circuit, sub_presentation = pc._module_view(circuit, presentation, idx["wifi"])
    page = pc.PageCompileBudget(page_box=(0.0, 0.0, 1170.0, 825.0))
    page = replace(page, module_budget=replace(
        page.module_budget,
        flag_lead_limit=sub_presentation.flag_lead_limit or 120.0,
        gnd_cluster_radius=sub_presentation.gnd_cluster_radius or 100.0,
    ))
    return sub_circuit, sub_presentation, book, pc._module_budget_for(
        page.module_budget, page)


def _context():
    circuit, presentation, book, budget = _wifi()
    binding = dc._with_series_arms(
        dc.bind_grammar(circuit, presentation, book, intent=None), presentation)
    prepared = dc._prepare(circuit, presentation, binding, book, budget, intent=None)
    assert not prepared.failures, prepared.failures
    ctx = prepared.context
    ctx.ground_domains = frozenset({"logic"})
    return circuit, presentation, book, budget, ctx


def _wire_lead_crossings(plan) -> list[str]:
    """Every place a wire of one net cuts another net's flag lead, from the plan."""
    anchors = {(symbol.x, symbol.y): symbol.net for symbol in plan.power_symbols}
    leads, wires = [], []
    for segment in plan.segments:
        points = [tuple(point) for point in segment.points]
        owner = anchors.get(points[-1])
        if owner is not None and owner == segment.net and len(points) <= 3:
            leads.append(segment)
        else:
            wires.append(segment)

    def crosses(a, b, c, d):
        def side(p, q, r):
            value = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
            return 0 if abs(value) < 1e-9 else (1 if value > 0 else -1)
        return (side(a, b, c) != side(a, b, d)) and (side(c, d, a) != side(c, d, b))

    out = []
    for wire in wires:
        wp = [tuple(point) for point in wire.points]
        for lead in leads:
            if lead.net == wire.net:
                continue
            lp = [tuple(point) for point in lead.points]
            for i in range(len(wp) - 1):
                for j in range(len(lp) - 1):
                    if crosses(wp[i], wp[i + 1], lp[j], lp[j + 1]):
                        out.append(f"{wire.net} {wp[i]}->{wp[i + 1]} x "
                                   f"{lead.net} {lp[j]}->{lp[j + 1]}")
    return out


def test_the_real_wifi_island_either_draws_without_a_crossing_or_refuses_by_name():
    circuit, presentation, book, budget, ctx = _context()
    variant = dc._variants(ctx)[0]
    built, failure, violations = dc._build_one_variant(ctx, variant, [])
    if built is None:
        # 如实拒绝：必须点名那只落不了座的脚，而不是画一张跨线的图
        assert failure is not None
        assert "J2.GND" in failure.detail or "J2.3V3" in failure.detail
        assert failure.category == dc.FAILURE_LAYOUT_UNSAT
    else:
        assert _wire_lead_crossings(built.plan) == []


def test_the_branch_shift_that_exposed_the_leak_no_longer_crosses_the_3v3_lead():
    """§21B 的 C8 一格平移只作**漏检暴露**，不是生产座位：修后要么合法候选，要么如实拒绝。"""
    circuit, presentation, book, budget, ctx = _context()
    variant = dc._variants(ctx)[0]
    placed, failure = dc._place(ctx, variant)
    assert placed is not None, failure
    layout = dc._chain_and_shelf_layout(ctx, variant)
    poses, origins = layout[1], layout[0]
    direction = dc._branch_offset_direction(ctx, ctx.slots["C8"], poses, origins)
    shifted = dict(placed.origins)
    origin = shifted["C8"]
    shifted["C8"] = (origin[0] + direction[0] * budget.grid,
                     origin[1] + direction[1] * budget.grid)
    trial = dc._Placement(origins=shifted, poses=dict(placed.poses),
                          residue=placed.residue, series_plans=placed.series_plans)
    built, refusal, violations = dc._build_one_variant(
        ctx, variant, [], placement_override=trial)
    if built is None:
        assert refusal is not None
        assert "GND" in refusal.subject
    else:
        assert _wire_lead_crossings(built.plan) == []


# ------------------------------------------- §22D：真实 WiFi 必须出候选（严格）
def test_the_real_wifi_island_draws_both_adjacent_flags_and_every_gate_passes():
    """联合旗位后，WiFi 岛必须真的画出来——不是「拒绝也算过」。

    独立读数：`built.checked` 是 `readability.check` 的结果（含 netlist 逐脚、
    导线端点、分区、短路、文字），`check_grammar` 单独再跑，旗引线交叉与本文件
    自己的扫描对齐，SVG 真渲染并核对两面旗的名字都在图里。
    """
    circuit, presentation, book, budget, ctx = _context()
    variant = dc._variants(ctx)[0]
    built, failure, violations = dc._build_one_variant(ctx, variant, [])
    assert built is not None, failure
    assert violations == []
    assert [item.render() for item in built.checked.hard_violations] == []
    assert _wire_lead_crossings(built.plan) == []
    flags = {(symbol.net, (symbol.x, symbol.y))
             for symbol in built.plan.power_symbols}
    rail = sorted(point for net, point in flags if net == "3V3")
    ground = sorted(point for net, point in flags if net == "GND")
    assert rail, "the 3V3 pad has no flag"
    assert ground, "the GND pad has no flag"
    assert rail[-1] != ground[-1]
    from boardwise.engines import svgpreview

    svg = svgpreview.render_svg(built.plan, list(book.values()))
    assert "3V3" in svg and "GND" in svg
    grammar = dc.check_grammar(built.plan, circuit, presentation, book)
    assert grammar == [], grammar
