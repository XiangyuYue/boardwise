"""548K：`labelPolicy.stubMin` 的声明地板——声明了就让路，没声明一字节不动。

`src/boardwise/engines/drawcompiler.py` 的 548K 机制有三处：`_stated_stub_floor`
只从文档读 `labelPolicy.stubMin`（缺省 0）；`_reserve_label_stubs` 的 `reach`
抬到该地板；`_lead_lane_reservations` 在地板 > 0 时把**单脚** `style == "label"`
的网提前一趟预留。交付侧（`drawapply._label_stub_candidates`）按同一把尺子起名字桩，
所以编译器承诺的 lane 必须够长，否则会出现「编译说合法、落图说没有空位」的假绿。

本文件钉三件事：

A **单位键**：`dc._stated_stub_floor` 写 `stubMin: 40.0` 读 40.0，不写读 0.0。
   这是「默认关闭」的唯一开关，读错单位/读错键都会让 B、C 失去意义。
B **默认关闭逐字节**：同一份文档不写 `stubMin` 时，`dc.compile` 最佳候选的
   `geometry_sha256()` 必须等于 :data:`PINNED_NO_FLOOR_GEOMETRY`。该常量是改动后
   的实测读数，且与改动前逐字节相同（lead 已用 M1 变异核过：把 `reach` 退回
   `LABEL_LANE_STEPS * grid`、并去掉提前一趟，该常量不变）——所以它同时是
   「新开关不许动老页面」的回归钉。
C **声明后退让**：同一文档写 `stubMin: 40.0` 后页面仍 `ok=True`、至少 1 个候选，
   且每个单脚 label 网的计划标签 `stub_min >= 40`——声明的地板要真的进到计划里，
   不是只被解析出来。

夹具照 `tests/test_548j_joint_seats.py` 的惯例**照抄而不是 import**：一颗 8 脚
双侧宿主、三颗同型上拉、一对去耦，网名用通用名，不写任何真实器件/模块名。
真机、页面、placement/shared 合同都不碰。
"""

from __future__ import annotations

import copy

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawcompiler as dc

PROV = "verified_recipe"
PAGE = (0.0, 0.0, 1170.0, 825.0)
PARTS = ["U1", "R1", "R2", "R3", "C1", "C2"]
STUB_FLOOR = 40.0
#: B 的钉子：文档不写 `labelPolicy.stubMin` 时最佳候选的 ``geometry_sha256()``。
#: `cb44c2e..d4c6fa4` 的整树实测值（git archive 复核）；548P 各批均未改变它。
#: 旧值 21436616 来自 548K 的未提交脏工作树，版本树上不可复现，不能作为回归基线。
PINNED_NO_FLOOR_GEOMETRY = (
    "6d4d134d45a97b695259295d19d6e5a3ef00215d1dd59ef7edf157244e97075f"
)


# ------------------------------------------------------------------ 真实夹具


def _pin(number: str, tip, direction: str) -> dict:
    return {"number": number, "name": number, "tip": list(tip),
            "direction": direction, "length": 10.0, "pinType": "passive"}


def _symbol(ref: str, body, pins) -> dict:
    return {"kind": "boardwise-symbol-profile", "profileVersion": 1,
            "symbolRef": ref, "title": ref, "body": list(body), "pins": pins,
            "source": "test fixture (548K stub floor)"}


def _profile_payloads() -> dict[str, dict]:
    return {
        # 8 脚双侧宿主：右 VDD/CFG_A/CFG_B/RX，左 GND/BOOT0/BOOT1/TX。
        "HOST8": _symbol("HOST8", [-70.0, -60.0, 70.0, 60.0], [
            _pin("VDD", [80.0, 45.0], "right"),
            _pin("CFG_A", [80.0, 15.0], "right"),
            _pin("CFG_B", [80.0, 5.0], "right"),
            _pin("RX", [-80.0, 55.0], "left"),
            _pin("GND", [-80.0, -45.0], "left"),
            _pin("BOOT0", [-80.0, -15.0], "left"),
            _pin("BOOT1", [-80.0, -5.0], "left"),
            _pin("TX", [-80.0, 35.0], "left"),
        ]),
        "R": _symbol("R", [-10.5, -4.5, 10.5, 4.5], [
            _pin("1", [-20.0, 0.0], "left"),
            _pin("2", [20.0, 0.0], "right"),
        ]),
        "C": _symbol("C", [-5.5, -8.5, 5.5, 8.5], [
            _pin("1", [0.0, 20.0], "up"),
            _pin("2", [0.0, -20.0], "down"),
        ]),
        "PWR-PWR": _symbol("PWR-PWR", [-6.0, 0.0, 6.0, 18.0], []),
        "PWR-GND": _symbol("PWR-GND", [-6.0, 0.0, 6.0, 18.0], []),
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
        _part("R1", "R", "10k"), _part("R2", "R", "10k"),
        _part("R3", "R", "10k"),
        _part("C1", "C", "100n"), _part("C2", "C", "100n"),
    ]


def _nets() -> list[dict]:
    return [
        _net("CFG_A", "signal", ["U1.CFG_A", "R1.1"]),
        _net("CFG_B", "signal", ["U1.CFG_B", "R2.1"]),
        # 共享启动脚：同一个启动网落在宿主两个脚上。
        _net("BOOT", "signal", ["U1.BOOT0", "U1.BOOT1", "R3.1"]),
        _net("PWR", "power",
             ["U1.VDD", "R1.2", "R2.2", "R3.2", "C1.1", "C2.1"]),
        _net("GND", "gnd", ["U1.GND", "C1.2", "C2.2"]),
        # 开放信号：单脚网，只能由可见名字表达——C 的观察对象。
        _net("TX", "signal", ["U1.TX"]),
        _net("RX", "signal", ["U1.RX"]),
    ]


def _circuit(parts=None, nets=None) -> CircuitSpec:
    return CircuitSpec.from_dict({
        "parts": copy.deepcopy(parts if parts is not None else _parts()),
        "nets": copy.deepcopy(nets if nets is not None else _nets()),
    })


def _groups() -> list[dict]:
    return [
        {"id": "config-right", "branches": [
            {"part": "R1", "from": "CFG_A", "to": "PWR"},
            {"part": "R2", "from": "CFG_B", "to": "PWR"},
        ]},
        {"id": "boot-left", "branches": [
            {"part": "R3", "from": "BOOT", "to": "PWR"},
        ]},
        {"id": "decoupling", "branches": [
            {"part": "C1", "from": "PWR", "to": "GND"},
            {"part": "C2", "from": "PWR", "to": "GND"},
        ]},
    ]


def _label_policy(stub_min) -> dict:
    policy = {"local": "wire", "crossModule": "label", "highFanout": "label"}
    # 只有文档真的写了才落这个键；`stubMin: 0` 本身是非法文档（解析器要求正数），
    # 所以「关闭」的唯一写法就是没有这个键。
    if stub_min is not None:
        policy["stubMin"] = float(stub_min)
    return policy


def _document(groups=_groups(), modules=None, stub_min=None) -> dict:
    payload = {
        "grammarRef": "ic-periphery",
        "sidePreferences": {"input": "right", "output": "right",
                            "load": "right", "source": "left",
                            "power": "top", "gnd": "bottom"},
        "modules": modules if modules is not None else [{
            "id": "m", "parts": list(PARTS),
            "role": "host island", "grammarRef": "ic-periphery", "core": "U1",
        }],
        "labelPolicy": _label_policy(stub_min),
    }
    if groups is not None:
        payload["serviceGroups"] = copy.deepcopy(groups)
    return payload


def _spec(groups=_groups(), modules=None, stub_min=None) -> PresentationSpec:
    return PresentationSpec.from_dict(
        copy.deepcopy(_document(groups, modules, stub_min)))


def _budget(keepouts=()) -> dc.CompileBudget:
    return dc.CompileBudget(
        max_candidates=4, page_box=PAGE, keepouts=tuple(keepouts))


def _compile(*, groups=_groups(), circuit=None, spec=None, keepouts=()):
    circuit = circuit if circuit is not None else _circuit()
    spec = spec if spec is not None else _spec(groups)
    book = _book()
    result = dc.compile(circuit, spec, book, _budget(keepouts))
    return circuit, spec, book, result


def _plan_or_fail(**kwargs):
    circuit, spec, book, result = _compile(**kwargs)
    assert result.ok, [
        (item.category, item.subject, item.detail, item.action)
        for item in result.failures
    ]
    return circuit, spec, book, result.best()


def _single_foot_nets(circuit: CircuitSpec) -> set[str]:
    """电路里只有一脚的网——只能由可见名字表达的网。"""
    return {net.id for net in circuit.nets if len(net.members) == 1}


# ------------------------------------------------------------------- A 单位键


def test_the_stated_floor_reads_the_document_key_and_nothing_else():
    stated = dc._stated_stub_floor(_spec(stub_min=STUB_FLOOR))
    assert stated == STUB_FLOOR, (
        "文档写了 labelPolicy.stubMin: 40.0，_stated_stub_floor 必须原样读出 "
        f"40.0（单位就是画布单位的名字桩长度）；实读 {stated!r}。"
    )
    silent = dc._stated_stub_floor(_spec(stub_min=None))
    assert silent == 0.0, (
        "文档根本没写 labelPolicy.stubMin 时，_stated_stub_floor 必须返回 0.0"
        "（历史行为，也就是「开关关闭」）；实读 "
        f"{silent!r}——读成非零会让所有老页面凭空让出 lane。"
    )


# -------------------------------------------------------- B 默认关闭逐字节


def test_a_page_that_states_no_stubMin_keeps_its_geometry_bytes():
    circuit, spec, book, plan = _plan_or_fail()
    digest = plan.geometry_sha256()
    assert digest == PINNED_NO_FLOOR_GEOMETRY, (
        "不写 labelPolicy.stubMin 的页面必须与 548K 之前的读法逐字节相同："
        "最佳候选的 geometry_sha256 必须等于钉住的常量 "
        f"{PINNED_NO_FLOOR_GEOMETRY}；实读 {digest}。"
        "若这是有意的版式改动，请附证据并显式改钉子，而不是让它漂。"
    )
    # 关闭状态下地板的另一面：计划里的标签不带 stubMin（0 不落盘，摘要才不动）。
    stray = sorted(
        label.net for label in plan.labels if label.stub_min != 0.0)
    assert not stray, (
        "文档没声明 stubMin，计划标签却带了 stub_min != 0：" f"{stray}——"
        "这会把默认页面的几何摘要也一起改掉。"
    )


# ----------------------------------------------------------- C 声明后退让


def test_a_stated_floor_leaves_the_page_and_lengthens_every_single_foot_stub():
    circuit, spec, book, result = _compile(spec=_spec(stub_min=STUB_FLOOR))
    assert result.ok and len(result.candidates) >= 1, (
        "声明 labelPolicy.stubMin: 40 后页面仍必须至少交出 1 个候选："
        "地板是「预留更长的 lane」，不是「拒绝可得性」；失败读数 "
        f"{[(item.category, item.subject, item.detail) for item in result.failures]}"
    )
    plan = result.best()
    single_foot = _single_foot_nets(circuit)
    assert single_foot, "夹具里应当有单脚 label 网（TX/RX）可观察"
    seen = {label.net for label in plan.labels if label.net in single_foot}
    assert seen == single_foot, (
        "单脚网必须都由标签表达，否则 C 观察不到声明的地板；"
        f"期望 {sorted(single_foot)}，实际 {sorted(seen)}。"
    )
    short = {
        label.net: label.stub_min
        for label in plan.labels
        if label.net in single_foot and label.stub_min < STUB_FLOOR
    }
    assert not short, (
        "文档声明 stubMin: 40，每个单脚 label 网的布局标签 stub_min 必须 >= 40，"
        "否则预留的 lane 短于交付侧要起的名桩，`draw plan` 会在落图时再拒一次；"
        f"偏短的：{short}。"
    )
    # 声明了地板就必须留下痕迹：默认页面的常量不能同时适用于声明页面。
    assert plan.geometry_sha256() != PINNED_NO_FLOOR_GEOMETRY, (
        "声明 stubMin: 40 的候选与不声明的默认候选几何摘要完全相同——"
        "说明地板没进计划，C 的 stub_min 断言只是空转。"
    )
