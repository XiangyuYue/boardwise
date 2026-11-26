"""627B：分压器与 RC 低通的十条洞（`outputs/hole627/TRIAGE.md` 缝 B）。

一条主题贯穿十条：**被丢掉的件与没做的判断必须说出来**，理由句不许断言代码没做过的事。
三处尤其明显——`_no_lowpass_failure` 说「两端都没有到地支路」而那条支路只是被 module
过滤掉了；`in` 的证据说「没有支路的那一端」而两端都有；`order` 的理由无条件印
`sidePreferences.power=top`，而那个 `top` 是默认值不是声明值。

约定与既有文法测试一致（`test_053b_grammar.py`）：电路、图纸、符号库全部手写字面量，
夹具复用它的构造器，测试之间不共享可变状态。
"""

from __future__ import annotations

import test_053b_grammar as t053

from boardwise.core.symbolprofile import SymbolPin, SymbolProfile
from boardwise.engines.grammar import base
from boardwise.engines.grammar.base import ABOVE, SAME_COLUMN, SAME_ROW

PROV = t053.PROV


# --------------------------------------------------------------------- inputs


def _rc_grammar():
    from boardwise.engines.grammar import rc_lowpass

    return rc_lowpass.RcLowpassGrammar


def _divider_grammar():
    from boardwise.engines.grammar import voltage_divider

    return voltage_divider.VoltageDividerGrammar


def _shunt_on_both_ends_circuit() -> t053.CircuitSpec:
    """R1 VIN→OUT with a cap on **each** end (the input-side cap is a real filter)."""
    return t053._circuit(
        [
            t053._part("R1"),
            t053._part("C1", "C0402", "100n"),
            t053._part("C2", "C0402", "10n"),
        ],
        [
            t053._net("VIN", "power", ["R1.1", "C2.1"]),
            t053._net("OUT", "signal", ["R1.2", "C1.1"]),
            t053._net("GND", "gnd", ["C1.2", "C2.2"]),
        ],
    )


def _two_ladders_circuit() -> t053.CircuitSpec:
    """Two dividers on one page: R1/R2 on VIN→GND, R3/R4 on VIN2→GND."""
    return t053._circuit(
        [t053._part("R1"), t053._part("R2"), t053._part("R3"), t053._part("R4")],
        [
            t053._net("VIN", "power", ["R1.1"]),
            t053._net("TAP1", "signal", ["R1.2", "R2.1"]),
            t053._net("VIN2", "power", ["R3.1"]),
            t053._net("TAP2", "signal", ["R3.2", "R4.1"]),
            t053._net("GND", "gnd", ["R2.2", "R4.2"]),
        ],
    )


def _two_lowpass_circuit() -> t053.CircuitSpec:
    """Two low-passes sharing nothing but the grounds: R1/C1 and R2/C2."""
    return t053._circuit(
        [t053._part("R1"), t053._part("C1", "C0402", "100n"),
         t053._part("R2"), t053._part("C2", "C0402", "100n")],
        [
            t053._net("VIN", "power", ["R1.1"]),
            t053._net("OUT1", "signal", ["R1.2", "C1.1"]),
            t053._net("VIN2", "power", ["R2.1"]),
            t053._net("OUT2", "signal", ["R2.2", "C2.1"]),
            t053._net("GND", "gnd", ["C1.2", "C2.2"]),
        ],
    )


def _three_pin_profile(symbol_ref: str) -> SymbolProfile:
    return SymbolProfile(
        symbol_ref=symbol_ref,
        pins=[
            SymbolPin(number="1", tip=(0.0, -20.0)),
            SymbolPin(number="2", tip=(0.0, 20.0)),
            SymbolPin(number="3", tip=(20.0, 0.0)),
        ],
    )


def _book(**extra: SymbolProfile) -> dict:
    book = {
        name: t053._small_profile(name)
        for name in ("R0402", "C0402", "C0805")
    }
    book.update(extra)
    return book


def _text(result) -> str:
    return " ".join(item.evidence for item in result.bindings)


def _reasons(result) -> str:
    return " | ".join(item.reason for item in result.constraints)


# ================================================================== 627B-01
# 分路被 module 过滤掉之后，拒因改口成「两端都没有到地支路」。


def test_b01_a_branch_in_another_module_is_named_not_denied():
    """C1 就挂在 OUT→GND，只是声明在 mB 而串联件在 mA。

    旧读数：`neither of its ends carries a branch to ground` —— 一句与电路
    直接相反的话；真因是 052 sec.5 的模块边界，必须点名两个 module。
    """
    presentation = t053._presentation(
        "rc-lowpass",
        modules=[
            {"id": "mA", "parts": ["R1"], "role": "trunk"},
            {"id": "mB", "parts": ["C1"], "role": "branch"},
        ],
    )
    result = _rc_grammar()().bind(t053._rc_circuit(), presentation)

    assert result.ok is False
    detail = " ".join(item.detail for item in result.failures)
    assert "C1" in detail, detail
    assert "mB" in detail and "mA" in detail, detail
    assert "neither of its ends carries a branch to ground" not in detail


# ================================================================== 627B-02
# 两端都有分路时，`in` 的证据陈述的是相反事实。


def test_b02_when_both_ends_carry_a_branch_the_in_evidence_says_so():
    """输入端也有一颗到地的电容（输入侧滤波电容是真实存在的形状）。

    旧读数：`in` 的证据写 `the side with no branch to ground`，而 VIN 上就有
    C2→GND。方向仍要定下来（电源端优先），但理由必须列出输入端那条支路，
    并说清是什么决定了方向。
    """
    result = _rc_grammar()().bind(
        _shunt_on_both_ends_circuit(), t053._presentation("rc-lowpass")
    )

    assert result.ok is True
    in_evidence = result.bindings_for("in")[0].evidence
    assert "C2" in in_evidence, in_evidence
    assert "the side with no branch to ground" not in in_evidence
    assert "direction" in in_evidence.lower() or "decided" in in_evidence.lower()


# ================================================================== 627B-03
# 三脚符号有一脚未被提及就被当二端件（`BIND shunt=U1`）。


def test_b03_a_three_pin_symbol_with_one_leg_unmentioned_is_not_a_shunt():
    """Q1 是 SOT-23，只把两只脚画到 OUT/GND 上，第三只没提。

    旧读数：`shunt` 里出现 Q1 —— 臂集只数被提到的脚。有符号库时臂必须按符号
    脚数判，且被排除的件要在证据里点名（与 627A-08 同一把尺）。
    """
    circuit = t053._circuit(
        [
            t053._part("R1"),
            t053._part("C1", "C0402", "100n"),
            t053._part("Q1", "SOT23", "MMBT3904"),
        ],
        [
            t053._net("VIN", "power", ["R1.1"]),
            t053._net("OUT", "signal", ["R1.2", "C1.1", "Q1.1"]),
            t053._net("GND", "gnd", ["C1.2", "Q1.2"]),
        ],
    )
    book = _book(SOT23=_three_pin_profile("SOT23"))
    result = _rc_grammar()(book).bind(circuit, t053._presentation("rc-lowpass"))

    assert result.ok is True
    assert result.parts_of("shunt") == ("C1",)
    assert "Q1" in _text(result), _text(result)


# ================================================================== 627B-04
# 不在任何已声明 module 里的第二条梯被静默丢弃。


def test_b04_a_ladder_outside_every_module_is_named_in_the_bound_result():
    """mA 里一条梯，另一条梯一件都不在任何 module 里。

    旧读数：`ok=True`、无拒因、无 runner-up note —— `found = scoped` 把另一条
    整条丢掉，`others` 里也没有它。绑上一条是对的，另一条必须点名。
    """
    presentation = t053._presentation(
        "voltage-divider",
        modules=[{"id": "mA", "parts": ["R1", "R2"], "role": "divider"}],
    )
    result = _divider_grammar()().bind(_two_ladders_circuit(), presentation)

    assert result.ok is True
    text = _text(result)
    assert "R3" in text, text
    assert "outside every declared module" in text, text


# ================================================================== 627B-05
# 一页两条独立低通，另一条只活在自由文本里。


def test_b05_two_independent_lowpasses_are_refused_not_half_bound():
    """R1/C1 与 R2/C2 没有任何共用件：这是两个岛，不是一个低通。

    旧读数：`candidates[0]` 绑一条，另一条只出现在 runner-up 的散文里，
    于是画布上只会有一个岛，另一条连约束都没有。一个文法实例绑一条，两条
    互不相交时必须拒绝并指路 `modules[]`。
    """
    result = _rc_grammar()().bind(
        _two_lowpass_circuit(), t053._presentation("rc-lowpass")
    )

    assert result.ok is False
    detail = " ".join(item.detail for item in result.failures)
    assert "R1" in detail and "R2" in detail, detail
    assert "modules[]" in " ".join(item.action for item in result.failures)


# ================================================================== 627B-06
# 默认侧被印成 `sidePreferences.power=top`。


def test_b06_a_mixed_declaration_says_the_default_axis_was_used():
    """`power: left` 与默认的 `gnd: bottom` 是一对混轴声明（不是链的方向）。

    旧读数：理由里照印 `sidePreferences.power=left, sidePreferences.gnd=bottom`，
    而约束发的是 `ABOVE`（书里的默认：电源在上、地在下）—— 约束与那句话互相
    矛盾。理由必须说明「这对声明不是链方向，用的是书的默认」。
    """
    presentation = t053._presentation(
        "voltage-divider", sidePreferences={"power": "left"}
    )
    result = _divider_grammar()().bind(t053._divider_circuit(), presentation)

    assert result.ok is True
    reasons = _reasons(result)
    assert "sidePreferences.power=left" in reasons, reasons
    assert "not a chain direction" in reasons, reasons
    assert "book's default" in reasons, reasons
    # 约束本身仍是书里的默认方向（电源在上），这句话现在解释得了它。
    assert ABOVE in {item.kind for item in result.constraints}, reasons


# ================================================================== 627B-07
# `input=right` 只改理由里的一个词，照样印「input right / output right」。


def test_b07_the_undeclared_output_side_is_not_printed_as_right_by_choice():
    """图纸只声明 `input: right`，`output` 没写，默认 `right`。

    旧读数：`input right / output right per sidePreferences` —— 同一句话里
    两个 right，读者会以为图纸要求两端都在右边。未声明的一侧要写明是默认。
    """
    result = _rc_grammar()().bind(
        t053._rc_circuit(),
        t053._presentation("rc-lowpass", sidePreferences={"input": "right"}),
    )

    assert result.ok is True
    trunk = result.obligations[0].reason
    assert "input right / output right per sidePreferences" not in trunk, trunk
    assert "unset" in trunk or "default" in trunk, trunk


# ================================================================== 627B-08
# 声明纵向主干仍发 `same-row`，而理由写「input top / output bottom」。


def test_b08_a_vertical_trunk_asks_for_one_column_not_one_row():
    """`input=top` + `output=bottom` 就是纵向主干：支路该并在一列上。

    旧读数：仍发 `SAME_ROW`，理由却写 `input top / output bottom` —— 约束与
    理由互相矛盾，布局引擎按行摆，读者按列看。
    """
    presentation = t053._presentation(
        "rc-lowpass", sidePreferences={"input": "top", "output": "bottom"}
    )
    result = _rc_grammar()().bind(t053._rc_circuit(), presentation)

    assert result.ok is True
    kinds = {item.kind for item in result.constraints}
    assert SAME_COLUMN in kinds, kinds
    assert SAME_ROW not in kinds, kinds
    column = [item for item in result.constraints if item.kind == SAME_COLUMN][0]
    assert "column" in column.reason, column.reason


# ================================================================== 627B-09
# 不在任何 module 里的串联件仍被绑上，而分压器对同一形状会拒。


def test_b09_a_series_element_outside_every_module_is_refused():
    """声明了 modules，但串联件不在任何 module 里，支路在 mB。

    旧读数：照绑（`scope` 为空就不做模块过滤），而 `voltage_divider` 对同一
    形状报 `cross-module`。两本必须同一把尺：拒，并点名「no module」。
    """
    presentation = t053._presentation(
        "rc-lowpass", modules=[{"id": "mB", "parts": ["C1"], "role": "branch"}]
    )
    result = _rc_grammar()().bind(t053._rc_circuit(), presentation)

    assert result.ok is False
    detail = " ".join(item.detail for item in result.failures)
    assert "R1" in detail and "no module" in detail, detail


# ================================================================== 627B-10
# 成功绑定时，非二端件与短路件既不拒、也不绑、也不提。


def test_b10_a_short_and_a_three_pin_part_are_named_on_success():
    """分压器成功绑上，页面上还躺着一只三脚件和一只两脚同网的「短路件」。

    旧读数：两件都零字。它们不是臂是**对的**，但读者必须看见它们被谁挡在
    门外、为什么 —— 否则「被丢掉」和「不存在」长得一模一样。
    """
    circuit = t053._circuit(
        [
            t053._part("R1"), t053._part("R2"),
            t053._part("Q1", "SOT23", "MMBT3904"),
            t053._part("R9"),
        ],
        [
            t053._net("VIN", "power", ["R1.1", "Q1.1"]),
            t053._net("TAP", "signal", ["R1.2", "R2.1", "R9.1", "R9.2"]),
            t053._net("GND", "gnd", ["R2.2", "Q1.2"]),
        ],
    )
    book = _book(SOT23=_three_pin_profile("SOT23"))
    result = _divider_grammar()(book).bind(
        circuit, t053._presentation("voltage-divider")
    )

    assert result.ok is True
    text = _text(result)
    assert "Q1" in text, text
    assert "R9" in text, text
    assert "not usable as a branch" in text, text
    assert base.two_terminal_parts(circuit, book).keys() == {"R1", "R2"}
