"""629A：反激语法深水四条 —— 钳位（A-01/A-04）与辅助/启动（A-03/A-05）。

夹具复用 `test_113_flyback_grammar` 的 110 页网表（`flyback_circuit()`）：它的钳位
恰好是「C5 直连母线 + R3→R15 串联」，所以**本批四种形态都是在它上面改出来**，
不是另起一套电路——110 那条读数（`clamp-C=C5`、`clamp-R={R3,R15}`）必须逐字不动。

四条洞的共同形状：**形状判据读不出的东西，被当成了不存在**。

* 629A-01：并联 RCD（C 与放电电阻并联回母线）里，两支的远端网相同，`_chain_from`
  按远端网去重，第二支永不进串 ⇒ 放电电阻零字，而留下的那支被叫 `clamp-C`；
* 629A-04：只有 D+R 时，`_line_through` 把跨 start 累积的件一起返回、`skip` 又被
  加进网名集合（对 `set(pair)` 比较无效），二极管被走回串里 ⇒ `clamp-D` 与
  `clamp-R` 同时绑 `D1`；
* 629A-03：`_aux` 只要求「一端是变压器的网」，而母线自己就是变压器的网 ⇒ 一只
  HVDC→VCC 的启动电阻被读成辅助整流管，`aux` 被绑成 `HVDC`；
* 629A-05：两电阻串联的启动串两个端都不是「变压器的网」，于是整条支路零字。

A-04 的裁决与 REPRO 的「应有」有一处不同，写在 §证据里：单支跨钳位节点与母线，
结构上分不出是电容还是放电电阻，本语法把它读作电容（既有形状规则），并在证据里
明说这条规则；改判成电阻会让每一块「只有一颗电容的简单 RCD」失去 `clamp-C`。
真正改掉的是**同一只二极管被绑两次**与**并联那支的静默**。
"""

from __future__ import annotations

import json

import test_113_flyback_grammar as t113

from boardwise.core.circuitspec import CircuitSpec

PROV = t113.PROV


# ------------------------------------------------------------------ 网表手术


def _payload() -> dict:
    return json.loads(json.dumps(t113.flyback_circuit().to_jsonable()))


def _net(payload: dict, net_id: str) -> dict:
    return next(net for net in payload["nets"] if net["id"] == net_id)


def _rewire(payload: dict, net_id: str, members: list[str]) -> None:
    _net(payload, net_id)["members"] = list(members)


def _drop_part(payload: dict, part_id: str) -> None:
    payload["parts"] = [p for p in payload["parts"] if p["id"] != part_id]
    for net in payload["nets"]:
        net["members"] = [
            member for member in net["members"]
            if not member.startswith(f"{part_id}.")
        ]


def _drop_net(payload: dict, net_id: str) -> None:
    payload["nets"] = [n for n in payload["nets"] if n["id"] != net_id]


def _add_part(payload: dict, part_id: str, symbol: str, **ends: str) -> None:
    payload["parts"].append(
        {"id": part_id, "symbolRef": symbol, "provenance": PROV}
    )
    for net_id, pin in ends.items():
        _net(payload, net_id)["members"].append(f"{part_id}.{pin}")


def _bind(payload: dict):
    return t113._bind(CircuitSpec.from_dict(payload))


def _evidence(result) -> str:
    return " ".join(binding.evidence for binding in result.bindings)


def _unbound_sentence(result) -> str:
    """`_stray_note` 的那一句（从 `unbound (` 起），空串表示它没写。

    判据必须钉在这一句上，不能钉在整段证据里：`part_clause`/`_spec_net_clause`
    会把网的成员逐个印出来，所以任何件名（`R16`、`R1`…）在整段证据里本来就可能
    以 `R16.1` 的形式出现——「因错误原因通过」正是这么来的。
    """
    blob = _evidence(result)
    marker = "unbound ("
    return blob[blob.index(marker):] if marker in blob else ""


def _drop_the_series_discharge_string(payload: dict) -> None:
    """R3+R15 与 `CLAMP_B` 去掉：钳位节点上只剩电容那一支。"""
    _drop_part(payload, "R3")
    _drop_part(payload, "R15")
    _drop_net(payload, "CLAMP_B")


# ------------------------------------------------------------------ 629A-01


def _parallel_rcd() -> dict:
    """D1 SW→CLAMP，C5 与 R6 **都**从 CLAMP 直连 HVDC（教科书 RCD）。"""
    payload = _payload()
    _drop_the_series_discharge_string(payload)
    _rewire(payload, "HVDC", ["BR1.4", "C4.1", "C5.2", "T1.P1"])
    _add_part(payload, "R6", "R", CLAMP="1", HVDC="2")
    return payload


def test_a01_the_parallel_discharge_resistor_is_not_dropped_silently():
    """两支并联共享远端网 `HVDC`：按远端网去重，第二支（R6）整条消失。"""
    result = _bind(_parallel_rcd())
    assert result.ok
    assert result.parts_of("clamp-D") == ("D1",)
    # 形状分不出「并联的电容」与「并联的放电电阻」⇒ 两支都不绑，但都不许静默。
    assert result.parts_of("clamp-C") == (), "并联支不许被猜成电容"
    assert result.parts_of("clamp-R") == (), "并联支不许被猜成电阻"
    blob = _evidence(result)
    assert "parallel" in blob, "并列的两支必须在证据里被说清（clamp_note）"


# ------------------------------------------------------------------ 629A-04


def _clamp_without_capacitor() -> dict:
    """只有 D1 与 R6：没有电容的钳位。"""
    payload = _payload()
    _drop_part(payload, "C5")
    _drop_the_series_discharge_string(payload)
    _rewire(payload, "HVDC", ["BR1.4", "C4.1", "T1.P1"])
    _rewire(payload, "CLAMP", ["D1.2"])
    _add_part(payload, "R6", "R", CLAMP="1", HVDC="2")
    return payload


def test_a04_the_clamp_diode_is_never_bound_as_its_own_string():
    """旧读数 `clamp D1/D1/R6`：`clamp-R` 里是二极管自己。"""
    result = _bind(_clamp_without_capacitor())
    assert result.ok
    assert result.parts_of("clamp-D") == ("D1",)
    assert result.parts_of("clamp-R") == (), "二极管不许进放电串"
    assert result.parts_of("clamp-C") == ("R6",)
    # 单支的判据是**形状规则**，不是读符号：证据必须自己说出来。
    blob = _evidence(result)
    assert "lone arm" in blob and "shape rule" in blob, blob


# ------------------------------------------------------------------ 629A-03


def _startup_only() -> dict:
    """没有辅助绕组，只有一只 HVDC→VCC 的启动电阻与它的去耦电容。"""
    payload = _payload()
    _drop_part(payload, "D2")
    _rewire(payload, "AUX", ["T1.A1"])
    _rewire(payload, "VCC", ["U3.7", "C7.1", "R2.2", "R14.2"])
    _add_part(payload, "R16", "R", HVDC="1", VCC="2")
    return payload


def test_a03_a_startup_resistor_on_the_bus_is_not_an_auxiliary_rectifier():
    """母线自己也是变压器的网：旧读数把 R16 读成 aux-D、把 `aux` 绑成 `HVDC`。"""
    result = _bind(_startup_only())
    assert result.ok
    assert result.parts_of("aux-D") == (), "启动电阻不是辅助整流管"
    assert result.net_of("aux") == "", "母线不是辅助绕组网"
    assert "R16" in _unbound_sentence(result), "它不绑，但必须在未绑定那句里被点名"


def _startup_and_late_aux() -> dict:
    """真的辅助整流管叫 `Z7`（排在后）、启动电阻叫 `R16`（排在前）。"""
    payload = _payload()
    for part in payload["parts"]:
        if part["id"] == "D2":
            part["id"] = "Z7"
    for net in payload["nets"]:
        net["members"] = [member.replace("D2.", "Z7.") for member in net["members"]]
    _add_part(payload, "R16", "R", HVDC="1", VCC="2")
    return payload


def test_a03b_the_real_aux_diode_wins_whatever_the_designator_order():
    """旧读数：`R16 < Z7`，启动电阻抢走 `aux-D`，真的辅助整流管零字。"""
    result = _bind(_startup_and_late_aux())
    assert result.ok
    assert result.parts_of("aux-D") == ("Z7",)
    assert result.net_of("aux") == "AUX"
    blob = _evidence(result)
    assert "Z7" in blob and "R16" in blob, "判给谁与没判给谁都要在证据里"


# ------------------------------------------------------------------ 629A-05


def _startup_string_only() -> dict:
    """两电阻串联的启动支路：HVDC→ST_A→VCC，没有辅助绕组。"""
    payload = _payload()
    _drop_part(payload, "D2")
    _rewire(payload, "AUX", ["T1.A1"])
    _rewire(payload, "VCC", ["U3.7", "C7.1", "R2.2", "R14.2"])
    _rewire(
        payload, "HVDC",
        ["BR1.4", "C4.1", "C5.2", "R15.2", "T1.P1", "R1.1"],
    )
    return payload


def test_a05_an_unbound_startup_string_is_named_not_silent():
    """旧读数：R1/R2/C7/VCC 全部零字——「读不出」被当成了「不存在」。"""
    result = _bind(_startup_string_only())
    assert result.ok
    assert result.parts_of("aux-D") == ()
    said = _unbound_sentence(result)
    assert "R1" in said and "R2" in said, "串联启动支路的两只件都要点名"
    assert "VCC" in said, "VCC 是一个真实节点，不许零字"


def test_the_110_page_clamp_and_aux_readings_do_not_move():
    """对照组：110 页（C5 直连 + R3→R15 串联）逐字不动。"""
    result = t113._bind(t113.flyback_circuit())
    assert result.ok
    assert result.parts_of("clamp-D") == ("D1",)
    assert set(result.parts_of("clamp-R")) == {"R3", "R15"}
    assert result.parts_of("clamp-C") == ("C5",)
    assert result.parts_of("aux-D") == ("D2",)
    assert result.net_of("aux") == "AUX"
