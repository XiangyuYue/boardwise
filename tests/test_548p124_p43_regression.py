"""548P124 P43 回归：已验收的 64 脚 MCU 单岛必须在**当前生产码**上重新编出来。

P43（`evidence/548D/host-binding/p43/ACCEPTANCE.md`）在真机上验收过：真实 64 脚
automatic 单岛，1 候选、20/20 声明脚 + 48/48 NC、lint 0/0/0。P122 基线之后用**同一
电路、同一 presentation、同一 profiles** 离线回放，生产码给出 exit 5 / 0 候选 / 7 变体
拒绝，首拒 `[flag-body-on-wire] powerSymbols[7] + segments[8]`。

本文件钉三件事，都走真实入口，不钉旧几何哈希：

1. `boardwise draw compile` 的入口 `dc.compile` 必须重新给出至少一个候选（0 hard）；
2. 生产可读性尺 `readability.check` 对那个候选必须 0 hard —— 编译闸自己的答案不算第二遍；
3. **本次因果对象**：一条旗标自己的 lead 不得穿进自己 glyph 的 5 单位 clearance。P43 旧
   合法座位是「水平桩 + 25 单位竖直尾段」，旗挂在尾段末端；退化成的「桩停在转角、旗坐在
   转角」会让桩沿 glyph 上下边缘穿过自己的图形（0 距离），这正是三条 hard 的来源。
   这里用生产尺 `readability._flag_body_offence` 对**候选自己的**每段 lead 逐段量，不写死
   任何坐标；
4. 20/20 声明脚与 48/48 NC 的精确分区（`evidence/548D/host-binding/p43/verify_netlist.py`
   的真机读数同一口径，离线用 plan 几何复算）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.engines import drawapply, drawcompiler as dc, readability

ROOT = Path(__file__).resolve().parents[1]
CIRCUIT = ROOT / "evidence/548D/host-binding/live-reference/circuit_hostbound.json"
SPEC = ROOT / "evidence/548D/host-binding/p43/presentation_hostbound.json"
PROFILES = ROOT / "evidence/548D/host-binding/live-reference/profiles_hostbound.json"
PAGE_BOX = (0.0, 0.0, 1170.0, 825.0)
INPUTS = (CIRCUIT, SPEC, PROFILES)

_missing = [str(path.relative_to(ROOT)) for path in INPUTS if not path.exists()]
if _missing:
    pytest.skip(
        "requires local 548P124 (P43 host-binding) evidence (gitignored, "
        f"local-only); missing: {_missing}",
        allow_module_level=True,
    )

#: P43 ACCEPTANCE.md 的真机读数：20 条声明脚（U1 16 + C1/R1 4），U1 其余 48 脚 NC。
DECLARED_PINS = 20
NC_PINS = 48

TOLERANCE = 1e-6


@pytest.fixture(scope="module")
def compiled():
    circuit = CircuitSpec.load(CIRCUIT)
    spec = PresentationSpec.load(SPEC)
    profiles = drawapply.load_library(PROFILES)
    result = dc.compile(
        circuit, spec, profiles, dc.CompileBudget(page_box=PAGE_BOX))
    return result, circuit, profiles


def _on_polyline(point, points) -> bool:
    for start, end in zip(points, points[1:]):
        if (min(start[0], end[0]) - TOLERANCE <= point[0]
                <= max(start[0], end[0]) + TOLERANCE
                and min(start[1], end[1]) - TOLERANCE <= point[1]
                <= max(start[1], end[1]) + TOLERANCE):
            return True
    return False


def test_p43_replay_compiles_to_a_candidate(compiled):
    """P122 基线一次 0 候选：已验收的这张图必须还能编出来。"""
    result, _circuit, _profiles = compiled
    assert result.ok, [item.detail for item in result.failures]
    assert len(result.candidates) >= 1, [item.detail for item in result.failures]


def test_p43_candidate_passes_the_production_readability_gate(compiled):
    """独立复算：编译闸之外的第二次 `readability.check`，0 hard。"""
    _result, circuit, profiles = compiled
    plan = _result.candidates[0]
    checked = readability.check(
        plan, circuit, PresentationSpec.load(SPEC),
        dc._profile_book(profiles), page_box=PAGE_BOX,
    )
    assert not checked.hard_violations, [
        item.render() for item in checked.hard_violations]


def test_p43_a_flags_own_lead_leaves_its_own_glyph_clear(compiled):
    """本次因果对象：同网导线（旗自己的 lead）不得进入旗 glyph 的 5 单位 clearance。

    生产尺逐段量：`:func:`readability._flag_body_offence` 就是 gate 的
    `flag-body-on-wire` 用的那一把，lead 豁免（端点落在锚点、背离 glyph）由它自己判。
    P43 的合法座位让竖直尾段把锚点推离转角，因此每段 lead 都是 0 offence；退化成
    「桩停在转角」时，桩沿 glyph 边缘穿过，offence 距离 0。
    """
    result, _circuit, profiles = compiled
    plan = result.candidates[0]
    book = dc._profile_book(profiles)
    problems = []
    for symbol in plan.power_symbols:
        profile = book.get(symbol.symbol_ref)
        assert profile is not None, symbol.symbol_ref
        glyph = dc.flag_glyph_box(
            profile, rotation=symbol.rotation, anchor=(symbol.x, symbol.y))
        if glyph is None:
            continue
        for segment in plan.segments:
            if segment.net != symbol.net:
                continue
            for start, end in zip(segment.points, segment.points[1:]):
                offence = readability._flag_body_offence(
                    symbol.net, (symbol.x, symbol.y), [start, end], glyph)
                if offence is not None:
                    problems.append(
                        f"{symbol.symbol_ref} (net {symbol.net}, rotation "
                        f"{symbol.rotation}, glyph {glyph}) has its own wire "
                        f"{tuple(start)}-{tuple(end)} inside the 5-unit clearance: "
                        f"{offence}")
    assert not problems, problems


def test_p43_declared_pins_and_nc_partition(compiled):
    """20/20 声明脚各落在自己网的导体上；U1 其余 48 脚一点导体都不碰。

    与 P43 真机 `verify_netlist.py` 同一口径，离线用 plan 几何复算（不用宿主网表）。
    """
    result, circuit, profiles = compiled
    plan = result.candidates[0]
    book = dc._profile_book(profiles)
    parts = readability._placed_parts(plan, book)
    pins = {
        f"{part.part_id}.{number}": point
        for part in parts for number, point in part.pins.items()
    }

    conductors: dict[str, list[list[tuple[float, float]]]] = {}
    for segment in plan.segments:
        conductors.setdefault(segment.net, []).append(
            [(float(x), float(y)) for x, y in segment.points])
    stated: dict[str, list[tuple[float, float]]] = {}
    for symbol in plan.power_symbols:
        stated.setdefault(symbol.net, []).append((symbol.x, symbol.y))
    for label in plan.labels:
        if label.net:
            stated.setdefault(label.net, []).append((label.x, label.y))

    declared = [
        (net.id, member) for net in circuit.nets for member in net.members]
    assert len(declared) == DECLARED_PINS, sorted(declared)

    problems = []
    declared_u1 = set()
    for net_id, member in declared:
        point = pins.get(member)
        if point is None:
            problems.append(f"{member}: the plan carries no pin tip for it")
            continue
        if member.startswith("U1."):
            declared_u1.add(member.split(".", 1)[1])
        on_own_net = any(
            _on_polyline(point, run) for run in conductors.get(net_id, ())
        ) or any(
            abs(point[0] - x) <= TOLERANCE and abs(point[1] - y) <= TOLERANCE
            for x, y in stated.get(net_id, ())
        )
        if not on_own_net:
            problems.append(
                f"{member}: no conductor of net {net_id!r} at its pin tip {point}")
    assert not problems, problems

    untouched = []
    nc = []
    for part in parts:
        if part.part_id != "U1":
            continue
        for number, point in part.pins.items():
            if number in declared_u1:
                continue
            nc.append(number)
            touched = any(
                _on_polyline(point, run)
                for runs in conductors.values() for run in runs
            ) or any(
                abs(point[0] - x) <= TOLERANCE and abs(point[1] - y) <= TOLERANCE
                for points in stated.values() for x, y in points
            )
            if touched:
                untouched.append(f"U1.{number} at {point} is drawn, but is NC")
    assert len(nc) == NC_PINS, sorted(nc, key=lambda item: int(item))
    assert not untouched, untouched
