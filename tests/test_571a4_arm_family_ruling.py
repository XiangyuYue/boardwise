"""571-A-H4 决策钉：分压语法的臂按**拓扑**定义，不读器件族。

053 §3 的表里写的是「两电阻竖排同轴」，但那是**画法示例**（相对位置与可见拓扑），
不是器件类型合同；全仓没有可校验的族表（`SpecPart` 只有 `id/value/lcsc/params` +
`symbol_ref`，`base.two_terminal_parts` 只数脚与网）。所以「R 串 + C 对地」被
`voltage-divider` 绑成 `ok=True` 是**设计行为**：画法拓扑
（in→upper→tap→lower→gnd）与分压一致，功能差异由作者的 `CircuitSpec` 和所选的
`grammarRef` 表达。

本文件故意钉住现状：**若有人把器件族加成硬合同**（例如按 `symbolRef` 前缀拒电容臂），
第 1 条会先红——那时必须先补一张经校准的族表与两条反向断言，再改裁决。

裁决原文：`tasks/053-drawing-compiler-ab.md` §3「571-A-H4 裁决」。
裁决前的洞表状态：`outputs/hole571/a/REPRO.md` 的 571A-H4 行（`suspect`：缺的正是这一句）。
"""

from __future__ import annotations

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.engines.grammar import voltage_divider

PROV = "verified_recipe"


def _part(part_id: str, symbol: str, value: str) -> dict:
    return {"id": part_id, "symbolRef": symbol, "value": value, "provenance": PROV}


def _net(net_id: str, cls: str, members: list[str]) -> dict:
    return {
        "id": net_id,
        "class": cls,
        "members": list(members),
        "provenance": PROV,
    }


def _circuit(parts: list[dict], nets: list[dict]) -> CircuitSpec:
    return CircuitSpec.from_dict({"parts": parts, "nets": nets})


def _presentation(grammar_ref: str) -> PresentationSpec:
    return PresentationSpec.from_dict({"grammarRef": grammar_ref})


def _rc_lowpass_as_divider() -> CircuitSpec:
    """电气是 RC 低通（R 串 + C 对地），拓扑与分压同形：VIN→RS→OUT→CS→GND。"""
    return _circuit(
        [_part("RS", "R0402", "10k"), _part("CS", "C0402", "100n")],
        [
            _net("VIN", "power", ["RS.1"]),
            _net("OUT", "signal", ["RS.2", "CS.1"]),
            _net("GND", "gnd", ["CS.2"]),
        ],
    )


def test_a_capacitor_arm_is_bound_by_topology_and_the_ruling_is_pinned():
    """决策钉：电容臂按拓扑被绑定，`ok=True` 保持不变（不是缺陷）。"""
    result = voltage_divider.grammar().bind(
        _rc_lowpass_as_divider(), _presentation("voltage-divider")
    )

    assert result.ok is True
    assert result.failures == ()
    assert result.parts_of("upper_arm") == ("RS",)
    # 器件族**没有**参与判定：这条臂声明的是 C0402，仍然作为 lower_arm 参与拓扑。
    assert result.parts_of("lower_arm") == ("CS",)


def test_the_capacitor_really_declares_a_capacitor_family():
    """前置：如果这条臂不是电容，上一条的「族未参与」就没有意义。"""
    circuit = _rc_lowpass_as_divider()
    part = next(item for item in circuit.parts if item.id == "CS")

    assert part.symbol_ref == "C0402"
    assert part.symbol_ref.lower().startswith("c")


def test_a_resistor_divider_is_the_same_binding_without_the_cap():
    """负控：把电容换回电阻，绑定与角色完全相同（拓扑是唯一判据）。"""
    circuit = _circuit(
        [_part("R1", "R0402", "10k"), _part("R2", "R0402", "4k7")],
        [
            _net("VIN", "power", ["R1.1"]),
            _net("TAP", "signal", ["R1.2", "R2.1"]),
            _net("GND", "gnd", ["R2.2"]),
        ],
    )

    result = voltage_divider.grammar().bind(
        circuit, _presentation("voltage-divider")
    )

    assert result.ok is True
    assert result.parts_of("upper_arm") == ("R1",)
    assert result.parts_of("lower_arm") == ("R2",)
