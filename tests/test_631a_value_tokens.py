"""631A-04：`Value` 字段是复合串，而四个解析器的契约是「整串一个量」。

洞的原文（`outputs/hole631/a/REPRO.md` §631A-04）：`parse_voltage_volts('330uF/6.3V')`、
`parse_capacitance_farads('1nF/1kV')`、`parse_resistance_ohms('75k 1% 0603')` **全部 `None`**——
blocklib 的 9 条真实值串里 7 条读不出。而复合串的切分口径当时只活在 `rules/railratings.py`
一个私有常量里，绘制侧要用就是第三份拷贝（`validate_spec.py` 文档点名的 #51/#52 缺陷类）。

本批的做法**不动四个 `parse_*` 的整串契约**（它们的文档承诺就是「一个量」），
在 `core/values.py` 补一层「整串 → 切分 → 逐 token」的读入口，并让 `railratings` 改用它。

两条容易被读错的形状在切分处就挡掉，因为错的方向是危险的那一边
（假读数让规则**更不容易**告警）：

* 封装码（`0603`）：裸数字，读成电压就是 603 V；
* 公差（`1%`）：`%` 不进 token，只剩裸 `1`，而裸数字是合法电阻（1 Ω）。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from boardwise.core import values
from boardwise.rules import railratings


# ---------------------------------------------------------------- 切分口径


def test_a_compound_field_splits_on_anything_that_is_not_a_unit():
    assert values.value_tokens("1nF/1kV") == ("1nF", "1kV")
    assert values.value_tokens("10uF 25V") == ("10uF", "25V")
    assert values.value_tokens("1uF,16V") == ("1uF", "16V")


def test_a_package_size_is_not_a_quantity():
    """`0603` 读成电压就是 603 V——而 603 V 会让欠压的电容**通过**（issue #72）。"""
    assert values.value_tokens("75k 1% 0603") == ("75k",)
    assert values.value_tokens("100nF 0603") == ("100nF",)
    assert values.value_tokens("100pF 0603 C0G") == ("100pF", "C0G")


def test_a_tolerance_is_not_a_quantity():
    """`1%` 的 `1` 曾经是一条 1 Ω 的电阻。"""
    assert values.value_tokens("1%") == ()
    assert values.value_tokens("4.7k 1% 0603") == ("4.7k",)
    assert values.value_tokens("17.8k 1% TH") == ("17.8k", "TH")


# ------------------------------------------------------- 整串优先，再切分


@pytest.mark.parametrize(
    "text,farads",
    [
        ("10µF", 1e-05),          # the whole string answers, µ sign and all
        ("100nF 0603", 1e-07),
        ("100pF 0603 C0G", 1e-10),
        ("1nF/1kV", 1e-09),
        ("220uF/25V", 2.2e-04),
        ("330uF/6.3V", 3.3e-04),
        ("1.2nF", 1.2e-09),
    ],
)
def test_a_capacitance_is_found_in_the_real_value_strings(text, farads):
    found = values.find_capacitance_farads(text)
    assert found is not None, text
    assert found[0] == pytest.approx(farads), (text, found)


@pytest.mark.parametrize(
    "text,ohms",
    [
        ("75k 1% 0603", 75000.0),
        ("4.7k 1% 0603", 4700.0),
        ("17.8k 1% TH", 17800.0),
        ("10k 0603", 10000.0),
        ("1k 1% 0805", 1000.0),
        ("100kΩ", 100000.0),
        ("0.1Ω", 0.1),
    ],
)
def test_a_resistance_is_found_in_the_real_value_strings(text, ohms):
    found = values.find_resistance_ohms(text)
    assert found is not None, text
    assert found[0] == pytest.approx(ohms), (text, found)


@pytest.mark.parametrize(
    "text,volts",
    [("1nF/1kV", 1000.0), ("220uF/25V", 25.0), ("330uF/6.3V", 6.3),
     ("1nF/50V", 50.0), ("5V", 5.0)],
)
def test_a_rating_voltage_is_found_in_the_real_value_strings(text, volts):
    found = values.find_voltage_volts(text)
    assert found is not None, text
    assert found[0] == pytest.approx(volts), (text, found)


def test_the_token_comes_back_with_the_number():
    """证据要能引用「读的是哪一个 token」，否则核不了 50 V 是从哪来的。"""
    assert values.find_voltage_volts("1nF/1kV") == (1000.0, "1kV")
    assert values.find_resistance_ohms("75k 1% 0603") == (75000.0, "75k")
    assert values.find_capacitance_farads("330uF/6.3V") == (3.3e-04, "330uF")


def test_a_value_no_reader_can_read_answers_none_not_zero():
    """`banana` 是「读不出」，不是 0——这是 fail closed 的那一半。"""
    for text in ("banana", "apple", "", "   ", "TH"):
        assert values.find_capacitance_farads(text) is None, text
        assert values.find_resistance_ohms(text) is None, text
        assert values.find_voltage_volts(text) is None, text


def test_a_current_is_read_out_of_a_compound_field():
    """保险丝额定电流的读法（631A-06 的原料）：`3A`、`100mA`、`2A 慢断`。"""
    assert values.find_current_amps("3A") == (3.0, "3A")
    assert values.find_current_amps("100mA") == (0.1, "100mA")
    assert values.find_current_amps("2A 慢断") == (2.0, "2A")


# ------------------------------------------------------ 一份口径，两个消费者


def test_the_rule_reads_the_same_tokens_the_reader_reports():
    """`railratings` 改用它之后，读数与切分口径不再分叉。"""
    comp = SimpleNamespace(value="1nF/1kV", mpn="")
    volts, where = railratings.cap_voltage_rating(comp, None)
    assert volts == pytest.approx(1000.0), (volts, where)
    assert "1kV" in where or "1nF/1kV" in where, where


def test_a_package_size_does_not_become_a_rating_through_the_rule():
    """`100nF/0402` 曾经能让一条欠压电容读到 402 V 而**通过**（issue #72）。"""
    comp = SimpleNamespace(value="100nF/0402", mpn="")
    volts, _where = railratings.cap_voltage_rating(comp, None)
    assert volts is None, volts
