"""631A-03 / 630A-01：`power-entry` 的支路**值**判据（耐压与钳位）。

两条洞的实测（`outputs/hole630/a/REPRO.md`、`outputs/hole631/a/REPRO.md`）：

* `power_entry` 对 `part.value` / `.mpn` / `.params` 的读取点是 **0 处**，于是
  `D1.value='5V'`（24 V 母线上的 5 V 钳位）与 `C115.value='330uF/6.3V'`（24 V 母线上的
  6.3 V 电解）两遍读数与正确值**逐字节相同**、`ok=True f=0`；
* 判据需要的数字解析器现成可读，缺的只是调用点。

本批落的判据只有一条（J1 的口径，不发明余量）：

* **电容**：`额定 ≥ 声明母线电压`，低于即 `circuit-invalid`；
* **钳位（TVS）**：`钳位 > 声明母线电压`，**等于或低于即红**——低于母线的钳位等于常态导通；
* **值读不出**：`facts-missing`（查不了 ≠ 通过）；
* **母线未声明**：判不了，句子写进证据（UNDECIDABLE 是读数，不是通过，也不是拒绝——
  095 的「没有契约的 bind 与以前逐字节相同」不许被推翻）。

支路种类按**值字段本身**判，不按 `symbolRef`：630A-06 实测这个包里没有一处读符号类别，
而 088 的夹具给 TVS 用的就是电容符号（`CAP-TH_BD10.0-P5.00`）。
"""

from __future__ import annotations

import pytest

import test_088_power_entry as pe

from boardwise.core import designintent as di
from boardwise.engines import grammar
from boardwise.engines.grammar import base, power_entry

RAIL = pe.RAIL


# ------------------------------------------------------------------ 合同夹具


def contract(*, rails=None, path="<mem>"):
    """An in-memory contract carrying only the `rails` section it is asked for."""
    body = {"intentVersion": di.INTENT_VERSION}
    if rails is not None:
        body["requirements"] = {"rails": list(rails)}
    return di.IntentSource(document=di.DesignIntent.from_dict(body), path=path)


def rail_entry(volts=24.0, net=RAIL, **extra):
    """One `requirements.rails[]` row; `volts=None` writes a row with no voltage."""
    row = {"net": net, "provenance": "user_stated"}
    if volts is not None:
        row["voltage"] = f"{volts:g}V"
    row.update(extra)
    return row


def bind(values: dict[str, str], *, intent=None, shunts=("D1", "C115", "C116")):
    spec = pe.inlet_circuit(shunts=shunts, values=values)
    return grammar.grammar_for("power-entry").bind(
        spec, pe.inlet_presentation(), intent=intent
    )


def entry_evidence(result) -> str:
    return next(
        item.evidence for item in result.bindings if item.role == "entry"
    )


def failure_for(result, part_id):
    return next(
        (item for item in result.failures if item.subject == part_id), None
    )


GOOD = {"D1": "36V", "C115": "330uF/35V", "C116": "330uF/35V"}


# ------------------------------------------------------- 值的三种形状怎么读


def test_the_value_field_decides_which_question_is_asked():
    """电容问耐压、只有电压的当钳位、两样都没有就是查不了。"""
    capacitor = power_entry._shunt_kind("330uF/6.3V")
    assert capacitor[0] == "capacitor"
    assert capacitor[2] == pytest.approx(6.3)
    assert power_entry._shunt_kind("5V")[0] == "clamp"
    assert power_entry._shunt_kind("SMCJ28CA")[0] == "unknown"
    assert power_entry._shunt_kind("banana")[0] == "unknown"


# ----------------------------------------------------------- 631A-03 电容耐压


def test_a_capacitor_rated_below_the_declared_bus_is_refused():
    """`330uF/6.3V` 挂在声明 24 V 的母线上：这条以前 `ok=True f=0`。"""
    result = bind({**GOOD, "C115": "330uF/6.3V"}, intent=contract(rails=[rail_entry()]))
    assert not result.ok, result.render_failures()
    failure = failure_for(result, "C115")
    assert failure is not None, result.render_failures()
    assert failure.category == base.FAILURE_CIRCUIT_INVALID
    assert "6.3" in failure.detail and "24" in failure.detail, failure.detail


def test_a_capacitor_rated_at_the_bus_is_enough():
    """J1：「额定 ≥ 声明母线」，等于就算过——不发明 1.5× 之类的余量。"""
    result = bind({**GOOD, "C115": "330uF/24V"}, intent=contract(rails=[rail_entry()]))
    assert result.ok, result.render_failures()


def test_a_capacitor_with_no_stated_rating_is_facts_missing():
    """有电容、没耐压：查不了，不许当通过。"""
    result = bind({**GOOD, "C115": "330uF"}, intent=contract(rails=[rail_entry()]))
    assert not result.ok, result.render_failures()
    failure = failure_for(result, "C115")
    assert failure.category == base.FAILURE_FACTS_MISSING
    assert "no voltage rating" in failure.detail, failure.detail
    assert failure.action, "a facts-missing failure has to say where to write the fact"


# ------------------------------------------------------------- 630A-01 钳位


def test_a_clamp_at_the_bus_is_refused():
    """J1：钳位 ≤ 母线即红——5 V 钳位挂在 24 V 母线上等于常态导通。"""
    result = bind({**GOOD, "D1": "5V"}, intent=contract(rails=[rail_entry()]))
    assert not result.ok, result.render_failures()
    failure = failure_for(result, "D1")
    assert failure.category == base.FAILURE_CIRCUIT_INVALID
    assert "5" in failure.detail and "24" in failure.detail, failure.detail


def test_a_clamp_above_the_bus_passes():
    result = bind({**GOOD, "D1": "28V"}, intent=contract(rails=[rail_entry()]))
    assert result.ok, result.render_failures()


def test_a_shunt_whose_value_states_no_rating_is_facts_missing():
    """`SMCJ28CA` 是个料号，不是额定：这一格以前什么都不发生。

    断言钉的是**那一条分支**，不只是「有个 facts-missing」——两条分支都产
    `facts-missing`，而把一只 TVS 说成「电容没写耐压」是另一个错误。
    """
    result = bind({**GOOD, "D1": "SMCJ28CA"}, intent=contract(rails=[rail_entry()]))
    assert not result.ok, result.render_failures()
    failure = failure_for(result, "D1")
    assert failure.category == base.FAILURE_FACTS_MISSING
    assert "states neither a capacitance nor a voltage" in failure.detail, failure.detail
    assert "is a capacitor" not in failure.detail, failure.detail
    assert "SMCJ28CA" in failure.detail, failure.detail


# ------------------------------------ UNDECIDABLE：判不了就是读数，不是通过


def test_without_a_contract_nothing_is_judged_and_nothing_is_added():
    """095 的硬约束：没有契约的 bind **逐字节**与以前相同——连一句提示都不加。

    这不是「沉默地跳过」：读者要的「没查」由推出契约的调用方（`edit plan` /
    绘制报告）说，而不是让每一个没有契约的 drawing 多出一句没人要的解释。
    """
    result = bind({"D1": "5V", "C115": "330uF/6.3V", "C116": "330uF/6.3V"})
    assert result.ok, result.render_failures()
    evidence = entry_evidence(result)
    assert "rated voltage unjudged" not in evidence, evidence
    # 088b 的判据：入口绑定只带它本来就有的那几句话。
    assert "inlet chosen:" in evidence, evidence


def test_a_contract_without_this_rail_says_which_rail_is_missing():
    result = bind(
        {"D1": "5V", "C115": "330uF/6.3V", "C116": "330uF/6.3V"},
        intent=contract(rails=[rail_entry(net="+5V", volts=5.0)]),
    )
    assert result.ok, result.render_failures()
    evidence = entry_evidence(result)
    assert "declares no voltage" in evidence, evidence
    assert RAIL in evidence, evidence


def test_a_declared_voltage_this_build_cannot_read_is_named():
    """合同写 `twenty-four`：句子要引用原文，否则读者找不对文件。"""
    result = bind(
        GOOD, intent=contract(rails=[rail_entry(volts=None, voltage="twenty-four")])
    )
    assert result.ok, result.render_failures()
    evidence = entry_evidence(result)
    assert "twenty-four" in evidence, evidence
    assert "cannot read" in evidence, evidence


def test_the_settled_slot_wins_over_the_target_slot():
    """`voltage` 先于 `targetVoltage`（与 `railquery.set_rail_voltage` 同序）。"""
    result = bind(
        {**GOOD, "C115": "330uF/20V"},
        intent=contract(
            rails=[rail_entry(volts=12.0, targetVoltage="24V")]
        ),
    )
    assert result.ok, result.render_failures()
    assert "voltage" in (power_entry.declared_rail_voltage(
        contract(rails=[rail_entry(volts=12.0, targetVoltage="24V")]), RAIL
    ).where)
