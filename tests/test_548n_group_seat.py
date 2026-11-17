"""548N2：联合座位必须让开**已预留的开放端口房间**，否则换档或具名拒绝。

548J 的座位方程先摆支路、后报冲突：真实 WiFi 页上 `R4` 的候选列正好压在
`ESP_TXD` 的预留房间上，于是整页 `layout-unsat`。548N 把「已预留端口」从
**事后冲突**改成**座位搜索里的墙**：命中就沿宿主脚侧向外退一档 `GAP`，退到清空
为止；退无可退仍是既有具名拒绝，不退回散姿。

本文件只钉这条缺陷，用最小合成夹具（一颗宿主 + 两颗同型上拉 + 一个右侧开放
信号），不新增合同字段、不碰页框/`near`/`max_nodes`/GAP/字号：

1. **正例**：开放端口的 run + 名字盒正好落在宿主右侧、与座位列同一 y 带；去掉
   换档时座位会压上去（见 3），现在**座位必须让位**：两个支路盒与那份预留房间逐盒
   不相交，同组同向、共享一条端子行，frame 含全部文字与旗。整页还有一层**二阶**
   冲突（让位后座位与宿主自己的 GND 旗争地，`the pin U1.GND has no clear upright
   hang` —— 校准 WiFi 页同样复现），不属本批的端口缺陷，故这里钉座位本身并把该
   事实写在此处，不假装整页通过。
2. **负例**：把开放信号的名字拉长到盖住整条候选带（8 档），每一档都仍压房间 →
   必须复现具名拒绝（点名 `serviceGroups` 与 `reserved port`），且 0 候选。
3. **默认关闭**：不写 `serviceGroups` 的同夹具不产生联合座位记录，摘要与几何
   路径不变（此条由 `_place` 不写 `service_group_plans` 直接钉住）。
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
PARTS = ["U1", "R1", "R2"]


# --------------------------------------------------------------- 合成夹具


def _pin(number: str, tip, direction: str) -> dict:
    return {"number": number, "name": number, "tip": list(tip),
            "direction": direction, "length": 10.0, "pinType": "passive"}


def _symbol(ref: str, body, pins) -> dict:
    return {"kind": "boardwise-symbol-profile", "profileVersion": 1,
            "symbolRef": ref, "title": ref, "body": list(body), "pins": pins,
            "source": "test fixture (548N2)"}


def _book() -> dict[str, SymbolProfile]:
    payloads = {
        # 双侧宿主：右侧 VDD/CFG_A/CFG_B + 一个开放 TX；GND 在顶边，旗朝上。
        "HOST4": _symbol("HOST4", [-40.0, -40.0, 40.0, 40.0], [
            _pin("VDD", [50.0, 30.0], "right"),
            _pin("CFG_A", [50.0, 20.0], "right"),
            _pin("CFG_B", [50.0, 10.0], "right"),
            _pin("TX", [50.0, -25.0], "right"),
            _pin("GND", [0.0, 50.0], "up"),
        ]),
        "R": _symbol("R", [-10.5, -4.5, 10.5, 4.5], [
            _pin("1", [-20.0, 0.0], "left"),
            _pin("2", [20.0, 0.0], "right"),
        ]),
        "PWR-PWR": _symbol("PWR-PWR", [-6.0, 0.0, 6.0, 18.0], []),
        "PWR-GND": _symbol("PWR-GND", [-10.0, 0.0, 10.0, 19.0], []),
    }
    return {
        ref: SymbolProfile.from_dict(copy.deepcopy(payload))
        for ref, payload in payloads.items()
    }


def _part(part_id: str, symbol: str, value: str = "") -> dict:
    return {"id": part_id, "symbolRef": symbol, "value": value,
            "provenance": PROV}


def _net(net_id: str, cls: str, members) -> dict:
    return {"id": net_id, "class": cls, "members": list(members),
            "provenance": PROV}


def _circuit(open_net: str = "TX") -> CircuitSpec:
    return CircuitSpec.from_dict({
        "parts": [
            _part("U1", "HOST4", "HOST"),
            _part("R1", "R", "10k"),
            _part("R2", "R", "10k"),
        ],
        "nets": [
            _net("CFG_A", "signal", ["U1.CFG_A", "R1.1"]),
            _net("CFG_B", "signal", ["U1.CFG_B", "R2.1"]),
            _net("PWR", "power", ["U1.VDD", "R1.2", "R2.2"]),
            _net("GND", "gnd", ["U1.GND"]),
            # 单脚开放网：`_reserve_open_ports` 会先给它预留 run + 名字盒。
            _net(open_net, "signal", ["U1.TX"]),
        ],
    })


def _document(groups=None, open_net: str = "TX") -> dict:
    payload = {
        "grammarRef": "ic-periphery",
        "sidePreferences": {"input": "right", "output": "right",
                            "load": "right", "source": "left",
                            "power": "top", "gnd": "bottom"},
        "modules": [{
            "id": "m", "parts": list(PARTS), "role": "host island",
            "grammarRef": "ic-periphery", "core": "U1",
        }],
        "labelPolicy": {"local": "wire", "crossModule": "label",
                        "highFanout": "label", "stubMin": 40.0},
    }
    if groups is not None:
        payload["serviceGroups"] = copy.deepcopy(groups)
    return payload


def _groups() -> list[dict]:
    return [{
        "id": "config", "branches": [
            {"part": "R1", "from": "CFG_A", "to": "PWR"},
            {"part": "R2", "from": "CFG_B", "to": "PWR"},
        ],
    }]


def _spec(groups=None, open_net: str = "TX") -> PresentationSpec:
    return PresentationSpec.from_dict(
        copy.deepcopy(_document(_groups() if groups is None else groups,
                                open_net)))


def _budget() -> dc.CompileBudget:
    return dc.CompileBudget(max_candidates=4, page_box=PAGE)


def _prepared(circuit, spec, book) -> dc._Context:
    binding = dc.bind_grammar(circuit, spec, book)
    assert binding.ok, [item.detail for item in binding.failures]
    binding = dc._with_panel_groups(binding, spec, circuit)
    binding = dc._with_service_groups(binding, spec, circuit, book)
    prepared = dc._prepare(circuit, spec, binding, book, _budget())
    assert prepared.context is not None, [
        item.detail for item in prepared.failures]
    return prepared.context


def _tip(plan, book, member: str) -> tuple[float, float]:
    part_id, _, token = member.partition(".")
    part = plan.part(part_id)
    assert part is not None, member
    profile = book[part.symbol_ref]
    pin = next(item for item in profile.pins
               if item.number == token or item.name == token)
    return transform_point(
        pin.tip[0], pin.tip[1], rotation=part.rotation, mirror=part.mirror,
        ox=part.x, oy=part.y,
    )


def _inside(box, point) -> bool:
    return box[0] - 1e-6 <= point[0] <= box[2] + 1e-6 and (
        box[1] - 1e-6 <= point[1] <= box[3] + 1e-6)


def _inside_box(frame, box) -> bool:
    return (_inside(frame, (box[0], box[1]))
            and _inside(frame, (box[2], box[3])))


def _place_or_fail(**kwargs):
    """Placement-level read: the seat must exist before any page-level flag noise.

    548N2 changes the seat search; the page-level plan is a later consumer. The
    synthetic page's host GND flag has no room once the seat stands beside its
    host — the same second-order blocker the calibrated WiFi page reports — so
    these tests pin the seat itself and say so, instead of pretending the page
    passes.
    """
    circuit = _circuit(kwargs.get("open_net", "TX"))
    spec = _spec(groups=kwargs.get("groups"), open_net=kwargs.get("open_net", "TX"))
    book = _book()
    ctx = _prepared(circuit, spec, book)
    placed, failure = dc._place(ctx, dc._variants(ctx)[0])
    assert failure is None, (
        failure.subject, failure.detail, failure.action)
    return circuit, spec, book, ctx, placed


# ---------------------------------------------------------------- 正例


def test_the_seat_stands_clear_of_a_reserved_open_port_room():
    """端口房间是座位的墙：座位必须整列让开，且仍是同一个联合座位。"""
    circuit, spec, book, ctx, placed = _place_or_fail()
    record = placed.service_group_plans[0]
    assert record.group_id == "config"
    assert placed.service_group_ports, "夹具必须让页面留下一份预留端口记录"
    walls = [
        box for port in placed.service_group_ports
        for box in (*dc._run_boxes(port.run), port.label.bbox)
    ]
    for cell in record.cells:
        box = dc._part_box(ctx.profile(cell.part_id), cell.pose, cell.origin)
        for wall in walls:
            assert not dc._overlaps(box, wall), (cell.part_id, box, wall)
    # 让位之后仍是同一个联合座位：同向、同一端子行、列序按宿主脚。
    seats = [cell.to_seat for cell in record.cells]
    assert len({round(seat[1], 6) for seat in seats}) == 1, seats
    assert len({round(seat[0], 6) for seat in seats}) == 2, seats
    assert all(cell.pose == record.cells[0].pose for cell in record.cells)


def test_the_group_frame_holds_every_printed_row_and_flag():
    """frame 是整组的实测外框：文字行、旗盒、器件体都在里面。"""
    _circuit_, _spec_, book, ctx, placed = _place_or_fail(groups=_groups())
    record = placed.service_group_plans[0]
    for cell in record.cells:
        for _kind, _text, box in cell.text_boxes:
            assert _inside_box(record.frame, box), (cell.part_id, box)
        assert _inside_box(
            record.frame,
            dc._part_box(ctx.profile(cell.part_id), cell.pose, cell.origin))
    for rail in record.rails:
        assert _inside_box(record.frame, rail.flag_box), rail.net
    assert record.host_paths, "每个支路都必须有真实宿主路径"


# ---------------------------------------------------------------- 负例


def test_a_port_room_filling_the_whole_band_is_a_named_refusal():
    """每一档都压在端口房间上：具名拒绝、0 候选，不回散姿。

    名字长到盖住 8 档候选带（每档 `GAP`），座位搜索退无可退，只能按既有
    `layout-unsat` 点名组与端口。
    """
    circuit = _circuit(open_net="OPEN_SIGNAL_ROOM_CONSUMER")
    spec = _spec(open_net="OPEN_SIGNAL_ROOM_CONSUMER")
    book = _book()
    result = dc.compile(circuit, spec, book, _budget())
    assert not result.ok and result.candidates == []
    text = " ".join(
        (item.subject or "") + " " + item.detail + " " + item.action
        for item in result.failures)
    assert "serviceGroups" in text, text
    assert "reserved port" in text, text
    assert "stands on" in text, text


# ------------------------------------------------------------ 默认关闭


def test_a_page_without_the_key_records_no_joint_seat():
    """不写 `serviceGroups` 的同夹具：不产生座位记录，几何原样。"""
    circuit = _circuit()
    spec = _spec(groups=[])
    book = _book()
    ctx = _prepared(circuit, spec, book)
    placed, failure = dc._place(ctx, dc._variants(ctx)[0])
    assert failure is None, failure.detail
    assert placed.service_group_plans == ()
    assert placed.service_group_ports == ()
