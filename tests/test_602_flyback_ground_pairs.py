"""602：`_short_failure` 必须检查**所有**异名地网对，而不是排序前两个。

570-C2-N1（`outputs/hole570/c2/REPRO.md`）实测：`_short_failure` 用
`sorted(state.ground)[:2]` 取一对地网，于是 `minimal_circuit()` 上再加一个与隔离
无关的第三地网（`AUXGND`，只经 `R98` 接 `VOUT2`）后，跨 `PGND↔SEC_GND` 的
`Y99` 短路会被**放行**（`ok=True`，17 条 binding 全绑）；同一电路把第三地网改名
`ZGND`（排序在后）又恢复拒绝。答案由网名排序决定，不是由电路决定。

这一批的判据：**任何**两端都是 gnd 类、且分属不同网的两脚件（wide 器件除外）
都是跨隔离带短路，与有几个地网、网名怎么排无关。同时**不许**把"有三个地网"本身
当成错误：第三个地网只挂一颗无关电阻时电路照常绑定（贯穿 110 的"两族"语义，
第三个 gnd 类是电路自己的事实，不是短路）。
"""

from __future__ import annotations

import test_113_flyback_grammar as t113

from boardwise.core.circuitspec import CircuitSpec
from boardwise.engines.grammar import base, flyback
from boardwise.engines.grammar.base import FAILURE_CIRCUIT_INVALID

PROV = "engineer_confirmed"

PGND_MEMBERS = ["R5.2", "U5.3"]
SEC_GND_MEMBERS = ["T1.S2", "C11.2", "R8.2", "U4.A"]


# ------------------------------------------------------------------ helpers


def _bind(circuit: CircuitSpec):
    return flyback.FlybackGrammar(t113.library()).bind(
        circuit, t113.flyback_presentation()
    )


def _with_third_ground(
    third_id: str | None = "AUXGND",
    extra_grounds: tuple[str, ...] = (),
    bridge: tuple[str, str] | None = None,
) -> CircuitSpec:
    """`minimal_circuit()` + inert extra ground net(s) + one optional bridge.

    `third_id`/`extra_grounds` are ground-class nets carrying nothing but one
    resistor leg to their own signal net — the exact shape the 570 probe used
    (`outputs/hole570/c2/probes/probe_c2.py:96-112`). `bridge=(net_a, net_b)`
    puts `Y99` across those two nets.
    """
    payload = t113.minimal_circuit().to_jsonable()
    parts = []
    nets = []
    ground_ids = [g for g in (third_id, *extra_grounds) if g]
    for index, gid in enumerate(ground_ids):
        pid = f"R{98 + index}"
        parts.append({"id": pid, "symbolRef": "R", "provenance": PROV})
        nets.append({"id": gid, "class": "gnd", "members": [f"{pid}.1"],
                     "provenance": PROV})
        nets.append({"id": f"VOUT_{gid}", "class": "signal",
                     "members": [f"{pid}.2"], "provenance": PROV})
    payload["parts"] += parts
    payload["nets"] += nets
    if bridge is not None:
        left, right = bridge
        payload["parts"].append({"id": "Y99", "symbolRef": "C",
                                 "provenance": PROV})
        for net in payload["nets"]:
            if net["id"] == left:
                net["members"].append("Y99.1")
            if net["id"] == right:
                net["members"].append("Y99.2")
    return CircuitSpec.from_dict(payload)


def _short(result) -> str:
    """The one failure, asserted to be the cross-ground short, as a sentence."""
    assert not result.ok, "this circuit states a short across the barrier"
    invalid = [f for f in result.failures if f.category == FAILURE_CIRCUIT_INVALID]
    assert invalid, [f.category for f in result.failures]
    return invalid[0].detail


# ============================================ 1 先红：第三地网不能放行短路


def test_a_short_is_refused_even_with_an_innocuous_third_ground_net():
    """570-C2-N1 本体：`minimal_circuit()` + `Y99`(PGND↔SEC_GND) + `AUXGND`+`R98`。

    修前实测 `ok=True`（17 条 binding），因为 `AUXGND` 排在地网序前两位。
    修后必须以 `circuit-invalid` 拒绝、点名 `Y99`，并在 detail 里写清它跨的
    两个真地网——只查 `not ok` 不够：别的缺件拒因会让这条空转。
    """
    result = _bind(_with_third_ground(bridge=("PGND", "SEC_GND")))
    assert not result.ok
    failure = [f for f in result.failures if f.category == FAILURE_CIRCUIT_INVALID][0]
    assert failure.subject == "Y99"
    assert "PGND" in failure.detail
    assert "SEC_GND" in failure.detail


def test_the_third_ground_net_name_does_not_decide_the_answer():
    """同一短路，第三地网叫 `AUXGND` 还是 `ZGND`（排序前一后）：拒因必须一致。"""
    aux = _bind(_with_third_ground(third_id="AUXGND", bridge=("PGND", "SEC_GND")))
    z = _bind(_with_third_ground(third_id="ZGND", bridge=("PGND", "SEC_GND")))
    a = [f for f in aux.failures if f.category == FAILURE_CIRCUIT_INVALID][0]
    b = [f for f in z.failures if f.category == FAILURE_CIRCUIT_INVALID][0]
    assert (a.category, a.subject) == (b.category, b.subject) == (
        FAILURE_CIRCUIT_INVALID, "Y99")
    assert "PGND" in a.detail and "SEC_GND" in a.detail
    assert "PGND" in b.detail and "SEC_GND" in b.detail


# ============================================ 2 绕过前两个地网的短路


def test_a_bridge_between_the_third_ground_and_the_secondary_ground_is_refused():
    """`Y99` 跨 `AUXGND↔SEC_GND`：一脚根本不在排序前两位，也必须具名拒绝。"""
    detail = _short(_bind(_with_third_ground(bridge=("AUXGND", "SEC_GND"))))
    assert "Y99" in detail
    assert "AUXGND" in detail
    assert "SEC_GND" in detail


def test_a_bridge_between_two_ground_nets_that_sort_last_is_refused():
    """四个地网、桥接排序最末的两个（`ZZ_A↔ZZ_B`）：全对枚举的直接证据。

    这一条在修前实测 `ok=True`——它不可能被"取排序前两项"的实现碰到。
    """
    result = _bind(_with_third_ground(
        third_id="ZZ_A", extra_grounds=("ZZ_B",), bridge=("ZZ_A", "ZZ_B")))
    assert not result.ok
    failure = [f for f in result.failures if f.category == FAILURE_CIRCUIT_INVALID][0]
    assert failure.subject == "Y99"
    assert "ZZ_A" in failure.detail and "ZZ_B" in failure.detail


# ============================================ 3 负对照：没有新增规则


def test_a_third_ground_that_only_carries_an_inert_part_still_binds():
    """第三个地网本身不是错误：只挂一颗 `R98` 时电路照常绑定。

    这条钉住"修的是对枚举、不是'第三地网非法'"：修后仍然 `ok=True`。
    """
    assert _bind(_with_third_ground()).ok


def test_the_minimal_circuit_still_binds():
    """正常 flyback 的绑定不受影响。"""
    assert _bind(t113.minimal_circuit()).ok


def test_the_two_family_y_capacitor_refusal_is_unchanged():
    """既有 `YC1` 双地网拒绝（`test_113` 那条）行为不变。"""
    payload = t113.minimal_circuit().to_jsonable()
    payload["parts"].append({"id": "YC1", "symbolRef": "C", "provenance": PROV})
    for net in payload["nets"]:
        if net["id"] == "PGND":
            net["members"].append("YC1.1")
        if net["id"] == "SEC_GND":
            net["members"].append("YC1.2")
    result = _bind(CircuitSpec.from_dict(payload))
    failure = [f for f in result.failures if f.category == FAILURE_CIRCUIT_INVALID][0]
    assert failure.subject == "YC1"
    assert "PGND" in failure.detail and "SEC_GND" in failure.detail


def test_a_two_pin_part_with_both_pins_on_one_ground_net_is_not_reported():
    """同网两脚件不是跨带短路（它不是 `base.two_terminal_parts` 的边）。"""
    payload = t113.minimal_circuit().to_jsonable()
    payload["parts"].append({"id": "R97", "symbolRef": "R", "provenance": PROV})
    for net in payload["nets"]:
        if net["id"] == "PGND":
            net["members"] += ["R97.1", "R97.2"]
    assert _bind(CircuitSpec.from_dict(payload)).ok


def test_a_wide_part_across_the_two_ground_families_is_exempt():
    """变压器豁免语义不变：四脚件（aux 冷端回原边地、副边冷端回副边地）不是短路。

    四脚件不在 `two_terminal_parts` 的边上，`_short_failure` 对它必须返回 `None`。
    """
    payload = t113.minimal_circuit().to_jsonable()
    payload["parts"].append({"id": "T9", "symbolRef": "T_3W", "provenance": PROV})
    for net in payload["nets"]:
        if net["id"] == "PGND":
            net["members"].append("T9.S2")
        if net["id"] == "SEC_GND":
            net["members"].append("T9.S1")
        if net["id"] == "HVDC":
            net["members"].append("T9.P1")
        if net["id"] == "SW":
            net["members"].append("T9.P2")
    circuit = CircuitSpec.from_dict(payload)
    state = flyback._State(
        circuit,
        base.two_terminal_parts(circuit),
        base.nets_of_class(circuit, "power"),
        base.nets_of_class(circuit, "gnd"),
    )
    assert "T9" not in state.edges
    assert flyback._short_failure(circuit, state) is None
