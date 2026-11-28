"""629A 后半：多路反馈三条（629A-02 / -06 / -07）。

三条同源：**一条 reading 的身份里少了反馈那一半**。

* 629A-02：双输出各自带分压时，绑哪一路由**抽头网名的字典序**决定（`FB2 < FB_SENSE`），
  声明为 `output` 的 `VOUT` 落进 runner-up；更糟的是 `_feedback_readings` 在所有分压器
  之间共用同一个误差放大器，于是产出「`U4` 读 `FB2`」这种结构上不存在的配对（`U4` 只接
  `FB_SENSE`）；
* 629A-06：第二路的分压器与滤波电容即使被 runner-up 点名也零字——`describe()` 只写到
  `sec_d→vout`；
* 629A-07：`_reading_key` 不含 `vout`/`divider`，共用抽头时 4 条 reading 里有两条
  `describe()` 逐字相同，绑定顺序落回整流管的 designator 序。

夹具是**独立小电路**（与 `test_113_flyback_grammar` 的 110 页不同形状：两路输出需要
第二条副边绕组），照 `outputs/hole629/a/REPRO.md` 的 `d1`/`d1b`/`d2` 三个探针用例写成
字面量；110 页留一条对照，确保它绑的还是 `SEC_12V` + `R7/R8`。
"""

from __future__ import annotations

import json

import test_113_flyback_grammar as t113

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.engines.grammar import flyback as fb

PROV = "engineer_confirmed"

SIDES = {"input": "left", "output": "right", "power": "top", "gnd": "bottom"}

#: 单输出反激的最小网表（`REPRO.md` 的 `BASE`）：三绕组变压器、原边开关与采样、
#: 副边整流滤波、`R7/R8` 分压到 `FB_SENSE`、`U4` 误差放大、`U5` 光耦。
BASE = {
    "kind": "boardwise-circuit-spec",
    "specVersion": 1,
    "parts": [
        {"id": "T1", "symbolRef": "T_3W", "provenance": PROV},
        {"id": "Q1", "symbolRef": "Q_NMOS", "provenance": PROV},
        {"id": "R5", "symbolRef": "R", "provenance": PROV},
        {"id": "D3", "symbolRef": "D", "provenance": PROV},
        {"id": "C11", "symbolRef": "C", "provenance": PROV},
        {"id": "R7", "symbolRef": "R", "provenance": PROV},
        {"id": "R8", "symbolRef": "R", "provenance": PROV},
        {"id": "R9", "symbolRef": "R", "provenance": PROV},
        {"id": "U4", "symbolRef": "U_TL431", "provenance": PROV},
        {"id": "U5", "symbolRef": "U_OPTO", "provenance": PROV},
    ],
    "nets": [
        {"id": "HVDC", "class": "power", "members": ["T1.P1"], "provenance": PROV},
        {"id": "SW", "class": "signal", "members": ["Q1.2", "T1.P2"],
         "provenance": PROV},
        {"id": "SRC", "class": "signal", "members": ["Q1.1", "R5.1"],
         "provenance": PROV},
        {"id": "GATE", "class": "signal", "members": ["Q1.3"], "provenance": PROV},
        {"id": "PGND", "class": "gnd", "members": ["R5.2", "U5.3"],
         "provenance": PROV},
        {"id": "SEC_SW", "class": "signal", "members": ["T1.S1", "D3.1"],
         "provenance": PROV},
        {"id": "VOUT", "class": "power",
         "members": ["D3.2", "C11.1", "R7.1", "R9.1"], "provenance": PROV},
        {"id": "SEC_GND", "class": "gnd",
         "members": ["T1.S2", "C11.2", "R8.2", "U4.A"], "provenance": PROV},
        {"id": "FB_SENSE", "class": "signal",
         "members": ["R7.2", "R8.1", "U4.REF"], "provenance": PROV},
        {"id": "LED_K", "class": "signal", "members": ["U4.K", "U5.2"],
         "provenance": PROV},
        {"id": "LED_A", "class": "signal", "members": ["R9.2", "U5.1"],
         "provenance": PROV},
        {"id": "COMP", "class": "signal", "members": ["U5.4"], "provenance": PROV},
    ],
}


# ------------------------------------------------------------------ 网表手术


def _payload() -> dict:
    return json.loads(json.dumps(BASE))


def _add_net(payload: dict, net_id: str, cls: str) -> None:
    payload["nets"].append(
        {"id": net_id, "class": cls, "members": [], "provenance": PROV}
    )


def _add_part(payload: dict, part_id: str, symbol: str, ends: dict) -> None:
    payload["parts"].append(
        {"id": part_id, "symbolRef": symbol, "provenance": PROV}
    )
    for net_id, pins in ends.items():
        next(net for net in payload["nets"] if net["id"] == net_id)[
            "members"].extend(f"{part_id}.{pin}" for pin in pins)


def _second_output(payload: dict, rect_id: str) -> None:
    """第二条副边绕组 + 整流管 + 输出电容（`REPRO.md` 的 `_second_output`）。"""
    next(net for net in payload["nets"] if net["id"] == "SEC_GND")[
        "members"].append("T1.B2")
    _add_net(payload, "5V_SEC", "signal")
    _add_net(payload, "5VOUT", "power")
    _add_part(payload, rect_id, "D", {"5V_SEC": ["1"], "5VOUT": ["2"]})
    _add_part(payload, "C12", "C", {"5VOUT": ["1"], "SEC_GND": ["2"]})
    next(net for net in payload["nets"] if net["id"] == "5V_SEC")[
        "members"].append("T1.B1")


def _two_dividers(tap_of_second: str) -> dict:
    """两路输出各有自己的分压器；第二路的抽头网名由参数给。"""
    payload = _payload()
    _second_output(payload, "D5")
    _add_net(payload, tap_of_second, "signal")
    _add_part(payload, "R10", "R", {"5VOUT": ["1"], tap_of_second: ["2"]})
    _add_part(payload, "R11", "R", {tap_of_second: ["1"], "SEC_GND": ["2"]})
    return payload


def _shared_tap(rect_id: str = "D2") -> dict:
    """加权双反馈：两路分压接到**同一个**抽头 `FB_SENSE`。

    `rect_id` 可改：A-07 要证的是「顺序不跟整流管的 designator 走」，而这正是
    改一个 id 就能测出来的事（旧树的 `sorted(edges)` 让它决定插入序）。
    """
    payload = _payload()
    _second_output(payload, rect_id)
    _add_part(payload, "R10", "R", {"5VOUT": ["1"], "FB_SENSE": ["2"]})
    _add_part(payload, "R11", "R", {"FB_SENSE": ["1"], "SEC_GND": ["2"]})
    return payload


def _presentation(port_roles: dict | None = None) -> PresentationSpec:
    return PresentationSpec.from_dict({
        "kind": "boardwise-presentation-spec",
        "specVersion": 1,
        "grammarRef": "flyback",
        "sidePreferences": dict(SIDES),
        "portRoles": (
            port_roles if port_roles is not None
            else {"VOUT": "output", "HVDC": "input"}
        ),
    })


def _bind(payload: dict, port_roles: dict | None = None):
    return t113._bind(
        CircuitSpec.from_dict(json.loads(json.dumps(payload))),
        _presentation(port_roles),
    )


def _readings(payload: dict):
    circuit = CircuitSpec.from_dict(json.loads(json.dumps(payload)))
    state = fb._State(
        circuit, fb.two_terminal_parts(circuit),
        fb.nets_of_class(circuit, "power"), fb.nets_of_class(circuit, "gnd"),
    )
    return fb._readings(state)


def _unbound_sentence(result) -> str:
    blob = " ".join(binding.evidence for binding in result.bindings)
    marker = "unbound ("
    return blob[blob.index(marker):] if marker in blob else ""


# ------------------------------------------------------------------ 629A-02


def test_a02_the_declared_output_wins_whatever_the_tap_is_called():
    """抽头网名参与决定时：`d1` 绑 `5VOUT`（`FB2 < FB_SENSE`），改名叫 `ZFB` 又翻回来。"""
    for tap in ("FB2", "ZFB"):
        payload = _two_dividers(tap)
        result = _bind(payload)
        assert result.ok, (tap, result.failures)
        assert result.net_of("vout") == "VOUT", tap
        assert result.net_of("fb-sense") == "FB_SENSE", tap
        assert set(result.parts_of("feedback-divider")) == {"R7", "R8"}, tap
        assert result.parts_of("error-amp") == ("U4",), tap


def test_a02b_a_divider_no_amplifier_reads_is_not_paired_with_one():
    """`U4` 只接 `FB_SENSE`：旧读数却产出一条「`U4` 读 `FB2`」的 reading。"""
    payload = _two_dividers("FB2")
    nets = _part_nets(payload)
    readings = _readings(payload)
    assert readings, "这一页有一条可读的 reading"
    for reading in readings:
        assert reading.sense_tap in nets[reading.error_amp], (
            f"amplifier {reading.error_amp} does not touch its tap "
            f"{reading.sense_tap}"
        )


def _part_nets(payload: dict) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for net in payload["nets"]:
        for member in net["members"]:
            out.setdefault(member.split(".", 1)[0], set()).add(net["id"])
    return out


# ------------------------------------------------------------------ 629A-06


def test_a06_the_second_outputs_divider_and_filter_are_named():
    """第二路既没被绑，也不许零字：抽头、两只分压臂、输出电容都要点名。"""
    result = _bind(_two_dividers("ZFB"))
    assert result.ok
    said = _unbound_sentence(result)
    for token in ("R10", "R11", "ZFB", "C12"):
        assert token in said, (token, said)


# ------------------------------------------------------------------ 629A-07


def test_a07_the_reading_order_does_not_follow_the_rectifiers_designator():
    """共用抽头时 4 条 reading；旧树里键分不开，顺序落回 `sorted(edges)` 的 id 序。

    判据不是「四条文本互不相同」（`describe()` 补了分压器之后自然不同，会把本洞
    盖住），而是**改一个 id 不改读数顺序**：`D2` 排在前与 `Z2` 排在后的同一页，
    必须给出同一串 reading。
    """
    def shape(readings):
        return [(reading.vout, reading.divider) for reading in readings]

    first = _readings(_shared_tap("D2"))
    second = _readings(_shared_tap("Z2"))
    assert len(first) == 4, [reading.describe() for reading in first]
    assert shape(first) == shape(second), (shape(first), shape(second))
    assert len({(r.vout, r.divider) for r in first}) == len(first), shape(first)
    bound = _bind(_shared_tap())
    assert bound.net_of("vout") == "VOUT", "声明的输出必须赢"


# ------------------------------------------------------------------ 对照


def test_the_110_page_still_binds_its_declared_output_and_divider():
    result = t113._bind(t113.flyback_circuit())
    assert result.ok
    assert result.net_of("vout") == "SEC_12V"
    assert set(result.parts_of("feedback-divider")) == {"R7", "R8"}
    assert result.net_of("fb-sense") == "FB_SENSE"
