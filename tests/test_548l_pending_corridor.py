"""548L：``style=wire`` 的两脚正交网，其直线走廊必须先于旗位被预留。

548J 的 WiFi 页在 548K 之后仍有两句自述：

    net ESP_EN: wired route not found; labelled instead
    net ESP_RST: wired route not found; labelled instead

两条都是宿主本地、恰好两脚的 ``wire`` 网，本该是一条直线。挡住直线的不是「没
空间」，而是去耦电容那枚「就近挂在自己焊盘旁」的地旗：它的图形盒与 25 单位引线
正好压在这两条水平走廊上，布线趟找不到路，落成两截各自带名的裸长桩。

本文件用自包含夹具复现那个**几何形状**：八脚宿主右侧两枚相邻信号脚，各自连到
一枚上拉电阻；两枚去耦电容落在宿主与电阻列之间，其中一枚的地焊盘正好在两条信号
直线下方，地旗从该焊盘向上挂 25 单位、盒高 19 单位，于是压住两条走廊。器件名与
网名是通用的，不出现任何真实模块名；不写坐标表、不用 userLocks、不缩字、不调
``near``/``max_nodes``/``GAP``/``stubMin``。

三条断言各钉一件事：

1. **正例**：开关打开时编译出合法候选，``SIG_A``/``SIG_B`` 各只有**一条**导体、
   没有标签兜底，且两条直线走廊的格点上没有**任何**旗盒或别网导体；
2. **默认关闭**：同一夹具不写 ``stubLaneReserve``（只留 ``stubMin``）时，页面回到
   能力引入前的读数——notes 原文出现两条 ``wired route not found; labelled
   instead``，每个网各两枚标签，地旗盒确实压住走廊（这条同时证明夹具真的复现了
   缺口），几何摘要等于下面的 ``PRE_548L_SHA``；
3. **开关的指纹**：同一夹具只差一个 ``stubLaneReserve``，两档几何摘要不同——开关
   承重，不是装饰。

``PRE_548L_SHA`` 是**改动前后同一读数**：去掉本批新增的
``_reserve_pending_runs`` 调用（或把调用条件改成假）时，本夹具在开关关闭档的
布局逐字节不变，摘要仍是这个常量；它钉住「默认关闭 = 老页面逐字节不变」。
"""

from __future__ import annotations

import copy

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.geometry import transform_point
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawcompiler as dc

PROV = "verified_recipe"
PAGE = (0.0, 0.0, 1170.0, 825.0)
STUB_MIN = 40.0
GRID = 5.0
PARTS = ["U1", "C1", "C2", "R1", "R2", "R3"]
#: 两脚 ``wire`` 网：宿主脚 -> 上拉电阻脚，两条水平直线。
CORRIDORS = {
    "SIG_A": ("U1.EN", "R1.2"),
    "SIG_B": ("U1.RST", "R2.2"),
}
#: 默认关闭档的布局摘要（``python -c`` 实测；改动前后同一读数，见模块 docstring）。
PRE_548L_SHA = "3ce51bcaf171abce19587ba46ae83c0d48f1e50749e916f6f58b565fa1480f0b"


# ------------------------------------------------------------------ 真实夹具


def _pin(number: str, tip, direction: str, name: str | None = None) -> dict:
    return {"number": number, "name": name or number, "tip": list(tip),
            "direction": direction, "length": 10.0, "pinType": "passive"}


def _symbol(ref: str, body, pins) -> dict:
    return {"kind": "boardwise-symbol-profile", "profileVersion": 1,
            "symbolRef": ref, "title": ref, "body": list(body), "pins": pins,
            "source": "test fixture (548L)"}


def _profile_payloads() -> dict[str, dict]:
    return {
        # 八脚双侧宿主，与 548J 那页的 ESP-01S 同形（50x50 体、±35 引脚）。
        "HOST8": _symbol("HOST8", [-25.0, -25.0, 25.0, 25.0], [
            _pin("1", [-35.0, 15.0], "left", "GND"),
            _pin("2", [-35.0, 5.0], "left", "NC"),
            _pin("3", [-35.0, -5.0], "left", "IO0"),
            _pin("4", [-35.0, -15.0], "left", "RXD"),
            _pin("5", [35.0, -15.0], "right", "TXD"),
            _pin("6", [35.0, -5.0], "right", "EN"),
            _pin("7", [35.0, 5.0], "right", "RST"),
            _pin("8", [35.0, 15.0], "right", "VCC"),
        ]),
        "R": _symbol("R", [-10.5, -4.5, 10.5, 4.5], [
            _pin("1", [-20.0, 0.0], "left"),
            _pin("2", [20.0, 0.0], "right"),
        ]),
        "C10": _symbol("C10", [-5.5, -8.5, 5.5, 8.5], [
            _pin("1", [-20.0, 0.0], "left"),
            _pin("2", [20.0, 0.0], "right"),
        ]),
        "C100": _symbol("C100", [-5.5, -8.5, 5.5, 8.5], [
            _pin("1", [-20.0, 0.0], "left"),
            _pin("2", [20.0, 0.0], "right"),
        ]),
        "PWR-PWR": _symbol("PWR-PWR", [-10.0, 0.0, 10.0, 19.0], []),
        "PWR-GND": _symbol("PWR-GND", [-10.0, 0.0, 10.0, 19.0], []),
    }


def _book() -> dict[str, SymbolProfile]:
    return {
        ref: SymbolProfile.from_dict(copy.deepcopy(payload))
        for ref, payload in _profile_payloads().items()
    }


def _part(part_id: str, symbol: str, value: str = "") -> dict:
    return {"id": part_id, "symbolRef": symbol, "value": value,
            "provenance": PROV}


def _net(net_id: str, cls: str, members) -> dict:
    return {"id": net_id, "class": cls, "members": list(members),
            "provenance": PROV}


def _parts() -> list[dict]:
    return [
        _part("U1", "HOST8", "HOST"),
        _part("C1", "C10", "10uF"),
        _part("C2", "C100", "100nF"),
        _part("R1", "R", "10k"),
        _part("R2", "R", "10k"),
        _part("R3", "R", "10k"),
    ]


def _nets() -> list[dict]:
    return [
        _net("PWR", "power",
             ["U1.VCC", "C1.1", "C2.1", "R1.1", "R2.1", "R3.1"]),
        _net("GND", "gnd", ["U1.GND", "C1.2", "C2.2"]),
        _net("SIG_A", "signal", ["U1.EN", "R1.2"]),
        _net("SIG_B", "signal", ["U1.RST", "R2.2"]),
        _net("SIG_C", "signal", ["U1.IO0", "R3.2"]),
        _net("NS_A", "signal", ["U1.TXD"]),
        _net("NS_B", "signal", ["U1.RXD"]),
    ]


def _circuit() -> CircuitSpec:
    return CircuitSpec.from_dict({
        "parts": _parts(), "nets": _nets(),
        "nc": [{"pin": "U1.NC", "provenance": PROV}],
    })


def _document(stub_lane_reserve: bool = True) -> dict:
    policy = {"local": "wire", "crossModule": "label", "highFanout": "label",
              "stub": "straight", "stubMin": STUB_MIN, "rowModel": "centered"}
    # 548K 的开关默认关闭：夹具关时**不写这个键**，与老文档逐字节同形。
    if stub_lane_reserve:
        policy["stubLaneReserve"] = True
    return {
        "grammarRef": "ic-periphery",
        "sidePreferences": {"input": "left", "output": "right",
                            "load": "right", "source": "left",
                            "power": "top", "gnd": "bottom"},
        "modules": [{
            "id": "m", "parts": list(PARTS),
            "role": "host island", "grammarRef": "ic-periphery", "core": "U1",
        }],
        "portRoles": {"SIG_A": "output", "SIG_B": "output", "SIG_C": "output",
                      "NS_A": "output", "NS_B": "output"},
        "directWiringObligations": [],
        "labelPolicy": policy,
        # 548J 那页的 `serviceLayout.pinGap` 是宿主与去耦/电阻列的距离来源；
        # 本夹具保留它，否则摆放会把电容挪走、缺口不再复现。
        "serviceLayout": {"pinGap": 30.0},
        "partTexts": {"U1": "below"},
    }


def _spec(stub_lane_reserve: bool = True) -> PresentationSpec:
    return PresentationSpec.from_dict(
        copy.deepcopy(_document(stub_lane_reserve))
    )


def _budget() -> dc.CompileBudget:
    return dc.CompileBudget(max_candidates=4, page_box=PAGE)


def _compile(*, stub_lane_reserve: bool = True):
    circuit = _circuit()
    spec = _spec(stub_lane_reserve)
    book = _book()
    result = dc.compile(circuit, spec, book, _budget())
    return circuit, spec, book, result


def _plan_or_fail(**kwargs):
    _circuit_, _spec_, book, result = _compile(**kwargs)
    assert result.ok, [
        (item.category, item.subject, item.detail, item.action)
        for item in result.failures
    ]
    plan = result.best()
    assert plan is not None
    return book, plan


def _tips(plan, book) -> dict[str, tuple[float, float]]:
    """Pin tips by the member token a CircuitSpec names (part.pin *name*)."""
    out = {}
    for part in plan.parts:
        profile = book[part.symbol_ref]
        for pin in profile.pins:
            token = pin.name or pin.number
            out[f"{part.part_id}.{token}"] = transform_point(
                pin.tip[0], pin.tip[1], rotation=part.rotation,
                mirror=part.mirror, ox=part.x, oy=part.y,
            )
    return out


# --------------------------------------------------------------- 几何读数


def _flag_box(flag, book):
    """The compiler's own flag box — glyph, name row and ``FLAG_CLEARANCE``.

    This is the production ruler (:func:`drawcompiler._flag_box`), not a second
    model: the box a flag reserves is exactly the box a wire may not stand in.
    """
    return dc._flag_box(
        book[flag.symbol_ref], float(flag.rotation), (flag.x, flag.y), flag.net,
    )


def _corridor(plan, book, net: str):
    tips = _tips(plan, book)
    a_member, b_member = CORRIDORS[net]
    start, end = tips[a_member], tips[b_member]
    assert (
        abs(start[0] - end[0]) < 1e-6 or abs(start[1] - end[1]) < 1e-6
    ), f"{net}: the two pads are not on one axis: {start} -> {end}"
    return start, end


def _nodes(start, end):
    """Every lattice node of the straight corridor, ends included."""
    length = max(abs(end[0] - start[0]), abs(end[1] - start[1]))
    steps = max(1, int(round(length / GRID)))
    return [
        (start[0] + (end[0] - start[0]) * index / steps,
         start[1] + (end[1] - start[1]) * index / steps)
        for index in range(steps + 1)
    ]


def _inside(point, box) -> bool:
    return (box[0] - 1e-9 <= point[0] <= box[2] + 1e-9
            and box[1] - 1e-9 <= point[1] <= box[3] + 1e-9)


def _on_segment(point, start, end, eps: float = 1e-6) -> bool:
    if abs(start[0] - end[0]) < eps:  # vertical
        return (abs(point[0] - start[0]) < eps
                and min(start[1], end[1]) - eps <= point[1]
                <= max(start[1], end[1]) + eps)
    if abs(start[1] - end[1]) < eps:  # horizontal
        return (abs(point[1] - start[1]) < eps
                and min(start[0], end[0]) - eps <= point[0]
                <= max(start[0], end[0]) + eps)
    return False


def _corridor_hits(plan, book, net: str):
    """Flag boxes and **foreign** conductor nodes standing on the straight run."""
    start, end = _corridor(plan, book, net)
    nodes = _nodes(start, end)
    hits = []
    for flag in plan.power_symbols:
        box = _flag_box(flag, book)
        for point in nodes:
            if _inside(point, box):
                hits.append(("flag", flag.net, (flag.x, flag.y), box, point))
                break
    for segment in plan.segments:
        if segment.net == net:
            continue
        for a, b in zip(segment.points, segment.points[1:]):
            for point in nodes:
                if _on_segment(point, a, b):
                    hits.append(("wire", segment.net, a, b, point))
                    break
    return hits


# ------------------------------------------------------------------ 断言


def test_the_pending_corridor_is_promised_and_drawn_as_one_wire():
    """开关打开：两条两脚网各自只有一条导体，直线走廊上没有旗盒/别网导体。"""
    book, plan = _plan_or_fail(stub_lane_reserve=True)
    notes = list(plan.notes)
    assert not [note for note in notes if "wired route not found" in note], notes
    for net in CORRIDORS:
        segments = [segment for segment in plan.segments if segment.net == net]
        assert len(segments) == 1, [
            (segment.net, segment.points) for segment in plan.segments
        ]
        assert not [label for label in plan.labels if label.net == net], [
            (label.net, label.x, label.y) for label in plan.labels
        ]
        # The conductor must really join the two pads, not a stub pair.
        points = segments[0].points
        start, end = _corridor(plan, book, net)
        ends = {tuple(round(value, 6) for value in point)
                for point in (points[0], points[-1])}
        assert {tuple(round(value, 6) for value in start),
                tuple(round(value, 6) for value in end)} == ends, points
        hits = _corridor_hits(plan, book, net)
        assert hits == [], (net, hits)
        # The flag that used to stand on the corridor is still drawn: it moved.
    # The decoupling pad's ground flag was moved off the corridor, not removed.
    assert any(flag.net == "GND" for flag in plan.power_symbols), [
        (flag.net, flag.x, flag.y) for flag in plan.power_symbols
    ]


def test_without_the_switch_the_page_keeps_the_pre_548l_reading():
    """默认关闭：不写 ``stubLaneReserve``，页面回到能力引入前的读数。

    这一档就是**所有老页面**走的路径。实测原文（写进断言消息，免得把「被拒」
    误读成「测试坏了」）：编译仍 ``ok=True``，但两条两脚网的 notes 是
    ``wired route not found; labelled instead``，两个网各落两枚标签，地旗盒
    压在走廊上；布局摘要等于 ``PRE_548L_SHA``（改动前后同一读数）。
    """
    book, plan = _plan_or_fail(stub_lane_reserve=False)
    notes = list(plan.notes)
    for net in CORRIDORS:
        assert any(
            f"net {net}: wired route not found; labelled instead" in note
            for note in notes
        ), (net, notes)
        labels = [label for label in plan.labels if label.net == net]
        assert len(labels) == 2, [(label.net, label.x, label.y) for label in labels]
        assert not [segment for segment in plan.segments if segment.net == net], [
            (segment.net, segment.points) for segment in plan.segments
        ]
        # The fixture's premise: the ground flag (glyph box or its 25-unit lead)
        # really stands on the corridor the straight run would take.
        hits = _corridor_hits(plan, book, net)
        assert hits, (net, hits)
        assert any(hit[1] == "GND" for hit in hits), (net, hits)
    assert plan.geometry_sha256() == PRE_548L_SHA, plan.geometry_sha256()


def test_the_switch_alone_moves_the_page():
    """只差一个开关：两档布局摘要必须不同（开关承重，不是装饰）。"""
    _book_on, on = _plan_or_fail(stub_lane_reserve=True)
    _book_off, off = _plan_or_fail(stub_lane_reserve=False)
    assert on.geometry_sha256() != off.geometry_sha256()
    assert dc._stub_lane_reserved(_spec(True)) is True
    assert dc._stub_lane_reserved(_spec(False)) is False
    assert "stubLaneReserve" not in _document(False)["labelPolicy"]
    assert "stubLaneReserve" in _document(True)["labelPolicy"]
