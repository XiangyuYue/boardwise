"""548K：文档声明的 ``stubMin`` 必须**先于**旗标引线与宿主支路占到车道。

548J 十二次尝试卡在同一句：``draw compile`` 说图合法，``draw plan`` 说名字桩画
不出来（``net ESP_TXD: the label at (250, 675) has no free name stub``）。两处读数
不一致的根因是编译期只承诺 ``LABEL_LANE_STEPS``（10 单位）的车道，交付期却按
``labelPolicy.stubMin``（40）找桩；更糟的是名字桩带排在**旗标引线与宿主支路之后**
才预留，等标签轮到，引脚 escape 带已被占满。本文件用自包含夹具复现那个**几何形
状**：单脚标签网的 40 单位名字桩带外侧紧贴着一枚电源旗的引线，旗和标签脚之间只
隔十几单位。

三条断言互相独立、各钉一件事：

1. 同 circuit + 同 spec：``drawcompiler.compile`` 出候选且 ``ok=True``，而
   ``drawapply.module_plan`` **返回一个 plan 而不是抛 ``DrawPlanError``**——「编译
   说合法、交付能落」在这一页上成立；
2. 编译出的几何里，单脚标签网从引脚沿标签方向 40 单位的那段带**没有**任何电源/地
   旗的图形盒、也没有**别网**导体。
3. 变异读数（已实测，写在文件里是为了不让人误读这条断言的强度）：把
   ``_lead_lane_reservations`` 里 ``if _stated_stub_floor(...) > 0.0:`` 改成
   ``if False:``，两个用例都红，但**红旗发生在 ``compile`` 的 readability 硬违规**
   （``[wire-through-body]``）——旗引线落回桩带，图先过不了编译闸，因此走不到
   ``module_plan``。所以本文件钉住的是**该 hunk 的因果性**（去掉就一定红），而**不是**
   548J 那条「compile 说合法、plan 说画不出」缝的原样复现；复现那条缝需要把旗/线相对
   几何放松一档，列入批次2 入口，不在本文件里假装做到。
4. 默认关闭的指纹**本文件也交付**：同一夹具去掉 `stubLaneReserve`、只留
   `stubMin=40` 时，`_stated_stub_floor` 仍是 40 而 `_stub_lane_reserved` 为
   False，页面回到能力引入前的读数——0 候选，readability 闸的
   ``wire-through-body``（实测 ``segments[6] + powerSymbols[5]``）。默认关闭
   不是跳过：那一次拒绝本身就是开关的指纹。规范 JSON 一侧由
   `test_the_canonical_form_leaves_the_switch_out_when_it_is_off` 钉住
   （键不出现、往返摘要不动）；页面级的老页逐字节不变另由
   `tests/test_053f_policy_switches.py` 等既有金标准覆盖。

夹具照 ``tests/test_548j_joint_seats.py`` 的惯例自包含（同一套 builder 照抄而不
是 import）：真宿主、真二端件、真生产尺，不写坐标表、不用 userLocks、不缩字、不
调 ``near``/``max_nodes``/``GAP``。器件名与网名是通用的，不出现任何真实模块名。
"""

from __future__ import annotations

import copy
import hashlib
import json
import math

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.geometry import transform_point
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import (
    FLAG_GLYPH_ROTATION_OFFSETS,
    SymbolProfile,
    flag_glyph_kind,
)
from boardwise.engines import drawapply
from boardwise.engines import drawcompiler as dc

PROV = "verified_recipe"
PAGE = (0.0, 0.0, 1170.0, 825.0)
STUB_MIN = 40.0
PARTS = ["U1", "R1", "R2", "R3", "C1", "C2"]
#: 单脚标签网：一个脚、一个名字，交付期必须给它画名字桩。
LABEL_NET = "SIG_C"


# ------------------------------------------------------------------ 真实夹具


def _pin(number: str, tip, direction: str) -> dict:
    return {"number": number, "name": number, "tip": list(tip),
            "direction": direction, "length": 10.0, "pinType": "passive"}


def _symbol(ref: str, body, pins) -> dict:
    return {"kind": "boardwise-symbol-profile", "profileVersion": 1,
            "symbolRef": ref, "title": ref, "body": list(body), "pins": pins,
            "source": "test fixture (548K)"}


def _profile_payloads() -> dict[str, dict]:
    return {
        # 8 脚双侧宿主。右列自上而下：VDD2 / SIG_C / VDD——SIG_C 的 40 单位
        # 名字桩带正对着 VDD 的电源旗引线；VDD2 与 VDD 把上下两个直行方向也
        # 挡住，交付期才没有第二根长度能绕过旗的引线。左列：四枚 RET 脚与
        # SIG_A、SIG_B，去耦/上拉都落在这一侧，右列外侧保持空的。
        "HOST8": _symbol("HOST8", [-70.0, -60.0, 70.0, 60.0], [
            _pin("VDD2", [80.0, 80.0], "right"),
            _pin("SIG_C", [80.0, 55.0], "right"),
            _pin("VDD", [80.0, 45.0], "right"),
            _pin("SIG_B", [-80.0, 15.0], "left"),
            _pin("SIG_A", [-80.0, 5.0], "left"),
            _pin("GND", [-80.0, -45.0], "left"),
            _pin("GND2", [-80.0, -25.0], "left"),
            _pin("GND3", [-80.0, -5.0], "left"),
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
        "PWR-RET": _symbol("PWR-RET", [-6.0, 0.0, 6.0, 18.0], []),
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
        _net("PWR", "power",
             ["U1.VDD", "U1.VDD2", "R1.2", "R2.2", "R3.2", "C1.1", "C2.1"]),
        # RET 是返回轨，仍在宿主的地词汇表之外：本页不拿地旗命名它
        # （`gnd_flag=""`），由 PWR 的自有旗承担「紧贴右列」的那枚旗。
        _net("RET", "gnd",
             ["U1.GND", "U1.GND2", "U1.GND3", "C1.2", "C2.2"]),
        _net("SIG_A", "signal", ["U1.SIG_A", "R1.1", "R3.1"]),
        _net("SIG_B", "signal", ["U1.SIG_B", "R2.1"]),
        # 单脚网：只能由可见名字表达，交付期按 stubMin 画名字桩。
        _net(LABEL_NET, "signal", ["U1.SIG_C"]),
    ]


def _circuit(parts=None, nets=None) -> CircuitSpec:
    return CircuitSpec.from_dict({
        "parts": copy.deepcopy(parts if parts is not None else _parts()),
        "nets": copy.deepcopy(nets if nets is not None else _nets()),
    })


def _document(stub_min: float | None = STUB_MIN,
              stub_lane_reserve: bool = True) -> dict:
    policy = {"local": "wire", "crossModule": "label", "highFanout": "label",
              "stub": "straight", "rowModel": "centered"}
    if stub_min is not None:
        policy["stubMin"] = stub_min
    # 548K 的两处行为（桩带按 stubMin 预留、单脚标签网先预留）都在这个显式开关
    # 之后，默认关闭；夹具必须打开它，否则复现的就不是 548J 那一页。
    if stub_lane_reserve:
        policy["stubLaneReserve"] = True
    return {
        "grammarRef": "ic-periphery",
        "sidePreferences": {"input": "right", "output": "right",
                            "load": "right", "source": "left",
                            "power": "top", "gnd": "bottom"},
        "modules": [{
            "id": "m", "parts": list(PARTS),
            "role": "host island", "grammarRef": "ic-periphery", "core": "U1",
        }],
        "labelPolicy": policy,
    }


def _spec(stub_min: float | None = STUB_MIN,
          stub_lane_reserve: bool = True) -> PresentationSpec:
    return PresentationSpec.from_dict(
        copy.deepcopy(_document(stub_min, stub_lane_reserve))
    )


def _budget(keepouts=()) -> dc.CompileBudget:
    return dc.CompileBudget(
        max_candidates=4, page_box=PAGE, keepouts=tuple(keepouts),
        # 本页只用 PWR 的自有旗；RET 的名字不在宿主的地词汇表里，一条地旗
        # 会把 RET 指成地（drawapply 的旗词汇表），所以地旗在这里关闭。
        gnd_flag="")


def _compile(*, circuit=None, spec=None, keepouts=()):
    circuit = circuit if circuit is not None else _circuit()
    spec = spec if spec is not None else _spec()
    book = _book()
    result = dc.compile(circuit, spec, book, _budget(keepouts))
    return circuit, spec, book, result


def _plan_or_fail(**kwargs):
    circuit, spec, book, result = _compile(**kwargs)
    assert result.ok, [
        (item.category, item.subject, item.detail, item.action)
        for item in result.failures
    ]
    plan = result.best()
    assert plan is not None
    return circuit, spec, book, plan


def _values() -> dict[str, str]:
    return {part_id: part["value"] for part_id in PARTS
            for part in _parts() if part["id"] == part_id}


def _lcsc() -> dict[str, str]:
    return {part_id: "C10000" for part_id in PARTS}


def _tips(plan, book) -> dict[str, tuple[float, float]]:
    out = {}
    for part in plan.parts:
        profile = book[part.symbol_ref]
        for pin in profile.pins:
            out[f"{part.part_id}.{pin.number}"] = transform_point(
                pin.tip[0], pin.tip[1], rotation=part.rotation,
                mirror=part.mirror, ox=part.x, oy=part.y,
            )
    return out


# --------------------------------------------------------------- 几何读数


def _flag_box(flag, book):
    """The glyph's room, hung on the flag's **electrical** side (548D3D-H2)."""
    body = book[flag.symbol_ref].body
    kind = flag_glyph_kind(book[flag.symbol_ref])
    base = (float(flag.rotation) - FLAG_GLYPH_ROTATION_OFFSETS[kind]) % 360.0
    scale = 1.0 if base == 0.0 else -1.0
    return (
        flag.x + body[0], flag.y + min(0.0, scale * body[1]),
        flag.x + body[2], flag.y + max(0.0, scale * body[3]),
    )


def _band(plan, book):
    """The single-foot label net's pin, its label side, and its 40-unit band."""
    label = next(item for item in plan.labels if item.net == LABEL_NET)
    tip = _tips(plan, book)["U1.SIG_C"]
    box = label.bbox
    cx = (box[0] + box[2]) / 2.0
    cy = (box[1] + box[3]) / 2.0
    dx, dy = cx - tip[0], cy - tip[1]
    if abs(dx) >= abs(dy) and abs(dx) > 1e-9:
        direction = (1.0 if dx > 0 else -1.0, 0.0)
    else:
        direction = (0.0, 1.0 if dy > 0 else -1.0)
    far = (tip[0] + direction[0] * STUB_MIN,
           tip[1] + direction[1] * STUB_MIN)
    return tip, direction, far, label


def _segment_hits_band(a, b, start, end, eps: float = 1e-6) -> bool:
    """Does the foreign run ``a-b`` meet the band ``start-end`` **inside** it?

    A touch at the band's two ends is the pin and the name's own far end, both of
    which are the drawing's own statement; the defect 548K is about is a
    conductor *through* the band. Collinear overlap counts as a hit.
    """
    x0, y0 = a
    x1, y1 = b
    x2, y2 = start
    x3, y3 = end
    den = (x1 - x0) * (y3 - y2) - (y1 - y0) * (x3 - x2)
    if abs(den) < 1e-12:
        # parallel: collinear overlap with positive length is a hit.
        cross = (x1 - x0) * (y2 - y0) - (y1 - y0) * (x2 - x0)
        if abs(cross) > eps:
            return False
        length = math.hypot(x1 - x0, y1 - y0) or 1.0
        us = [((x2 - x0) * (x1 - x0) + (y2 - y0) * (y1 - y0)) / (length ** 2),
              ((x3 - x0) * (x1 - x0) + (y3 - y0) * (y1 - y0)) / (length ** 2)]
        lo, hi = max(0.0, min(us)), min(1.0, max(us))
        return hi - lo > 1e-9
    t = ((x2 - x0) * (y3 - y2) - (y2 - y0) * (x3 - x2)) / den
    u = ((x2 - x0) * (y1 - y0) - (y2 - y0) * (x1 - x0)) / den
    if not (-eps <= t <= 1.0 + eps and -eps <= u <= 1.0 + eps):
        return False
    # strictly inside the band (u is the parameter along start-end).
    return eps < u < 1.0 - eps


def _band_occupancy(plan, circuit, book):
    """Every foreign conductor or flag glyph the 40-unit stub band carries."""
    tip, direction, far, label = _band(plan, book)
    own = {member for net in circuit.nets if net.id == LABEL_NET
           for member in net.members}
    hits = []
    for segment in plan.segments:
        if segment.net == LABEL_NET:
            continue
        for a, b in zip(segment.points, segment.points[1:]):
            if _segment_hits_band(a, b, tip, far):
                hits.append(("wire", segment.net, a, b))
    for flag in plan.power_symbols:
        box = _flag_box(flag, book)
        lo_x, hi_x = sorted((tip[0], far[0]))
        lo_y, hi_y = sorted((tip[1], far[1]))
        if (min(hi_x, box[2]) - max(lo_x, box[0]) > 1e-6
                and min(hi_y, box[3]) - max(lo_y, box[1]) > 1e-6):
            hits.append(("flag", flag.net, box, (flag.x, flag.y)))
    assert own, LABEL_NET
    return label, direction, far, hits


# ------------------------------------------------------------------ 断言


def test_the_page_the_compiler_passed_lands_as_a_plan():
    circuit, spec, book, plan = _plan_or_fail()
    change = drawapply.module_plan(
        plan, circuit, spec, book, page_box=PAGE,
        values_by_part=_values(), lcsc_by_part=_lcsc(),
    )
    assert isinstance(change, drawapply.ChangePlan)
    assert change.change is not None, "the plan carries no change at all"
    assert change.source is not None and change.target is not None
    # 编译说合法的那一页，交付侧必须真的落得下（548J 的原始拒因）。


def test_the_name_stub_band_carries_no_foreign_copper_or_flag():
    circuit, spec, book, plan = _plan_or_fail()
    _label, direction, far, hits = _band_occupancy(plan, circuit, book)
    assert direction == (1.0, 0.0), direction
    assert far == (_tips(plan, book)["U1.SIG_C"][0] + STUB_MIN,
                   _tips(plan, book)["U1.SIG_C"][1]), far
    assert hits == [], hits


def test_without_the_switch_the_page_keeps_a_legal_candidate():
    """去掉开关、只留 ``stubMin=40``：桩带不预留，但仍给出合法候选。

    本夹具旧读数曾因本趟穿旗而拒绝；`_place_flag` 把本趟旗盒接入
    `router.flag_walls` 后，穿旗这一生产缺陷已修，不能再把旧拒因当成合同。
    真正的契约是：默认关闭时仍然能生成不穿旗的候选，而且开关前后几何不同。
    """
    spec = _spec(stub_lane_reserve=False)
    floor = dc._stated_stub_floor(spec)
    reserved = dc._stub_lane_reserved(spec)
    assert floor == STUB_MIN, f"_stated_stub_floor read {floor!r}"
    assert reserved is False, f"_stub_lane_reserved read {reserved!r}"
    assert "stubMin" in _document(stub_lane_reserve=False)["labelPolicy"]
    _circuit_, _same, _book, result = _compile(spec=spec)
    assert result.ok and result.best() is not None, result.failures
    _label, _direction, _far, hits = _band_occupancy(result.best(), _circuit_, _book)
    assert all(kind != "flag" for kind, _net, _box, _point in hits), hits
    assert result.failures == []


def test_the_canonical_form_leaves_the_switch_out_when_it_is_off():
    """规范 JSON 默认关闭：键不出现，往返字节与摘要不动。

    ``stubLaneReserve`` 只在 ``true`` 时序列化；不写与 ``false`` 是同一份文档，
    所以二者的 ``sha256()`` 必须相同——这条与"老页面逐字节不变"是同一句话在
    文档契约这一层的读法。
    """
    document = _document(stub_lane_reserve=False)
    assert "stubLaneReserve" not in document["labelPolicy"]
    spec = PresentationSpec.from_dict(copy.deepcopy(document))
    payload = spec.to_jsonable()
    assert "stubLaneReserve" not in payload["labelPolicy"], payload["labelPolicy"]
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    assert "stubLaneReserve" not in canonical
    assert spec.sha256() == hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    again = PresentationSpec.from_dict(copy.deepcopy(payload))
    assert again.to_jsonable() == payload
    assert again.sha256() == spec.sha256()
    stated_false = copy.deepcopy(document)
    stated_false["labelPolicy"]["stubLaneReserve"] = False
    assert PresentationSpec.from_dict(stated_false).sha256() == spec.sha256()
    reserved = _spec()
    assert reserved.to_jsonable()["labelPolicy"]["stubLaneReserve"] is True
    assert reserved.sha256() != spec.sha256()
    assert PresentationSpec.from_dict(
        reserved.to_jsonable()
    ).sha256() == reserved.sha256()
