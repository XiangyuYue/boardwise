"""625B — 部件类的两条高危误读、全角位号、缺引脚计数（625 缝 B 的洞）。

来源 `outputs/hole625/b/REPRO.md`（625B-01 / 02 / 03 / 06）。这一批只钉**读数**：

* 625B-01：`MOS管` / `TVS管` 这种「ASCII 缩写 + 中文后缀」在 192B ① 的 `\\w` 边界下整词
  漏配，`U` 位号兜底成 IC —— 功率 MOSFET 被要旁路电容，就是 190f 的假阳原路返回；
* 625B-02：目录名里有接口词（`USB 转串口 CH340C`）就被读成 connector，真 IC 离开 IC 集合；
* 625B-03：全角位号 `Ｒ１` 两个前缀读取器各读各的，静默 `unknown` 且 `basis=''`；
* 625B-06：`pins` 没人读时引脚地板不生效 —— 本批复核后**不是修**（见最后一条测试的说明）。

保护既有钉子的是 `tests/test_192b_judgment_gates.py`：`USB和CAN` 是句子里的接口罗列，
不是部件事实，这条边界不能被本批改掉。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from boardwise.core.model import Component, Pin
from boardwise.core.partkind import (
    KIND_CONNECTOR,
    KIND_DIODE,
    KIND_IC,
    KIND_RESISTOR,
    KIND_TRANSISTOR,
    classify_part,
)

#: 192B ① 的那句原文，逐字：接口词 `USB` 与 `和` 相邻。
MCU_TEXT = (
    "主流增强型ARM Cortex-M3 MCU，具有64 KB Flash、72 MHz CPU、电机控制、USB和CAN "
    "LQFP-48(7x7)"
)


def _component(designator: str, *, pins: int = 3, props: dict | None = None, **kwargs):
    return Component(
        uid=designator.lower(),
        designator=designator,
        props=dict(props or {}),
        pins=[Pin(str(index + 1), f"P{index + 1}", f"N{index + 1}") for index in range(pins)],
        **kwargs,
    )


# ---------------------------------------------------------------- 625B-01


def test_a_mosfet_named_in_chinese_is_a_transistor_not_an_ic() -> None:
    """`MOS管`：缩写在 `管` 前面构成一个词，不是「在更长的词里面」。

    修前读数（REPRO §625B-01）：`ic` / `basis=prefix`，reason 是「no device fact
    classifies it either way」——一份指名 MOSFET 的值被判成没人认领。
    """
    read = classify_part(_component("U5", value="MOS管", pins=3))
    assert read.kind == KIND_TRANSISTOR
    assert read.basis == "metadata"
    assert "MOS" in read.reason


def test_the_same_shape_reads_a_tvs_as_a_diode() -> None:
    """`TVS管` 同族：修前也是 `ic`/`prefix`（`D` 位号能掩盖它，`U` 位号不能）。"""
    read = classify_part(_component("U6", value="TVS管", pins=3))
    assert read.kind == KIND_DIODE
    assert read.basis == "metadata"


def test_a_chinese_prefix_before_the_acronym_also_holds() -> None:
    """`功率MOS管`：左边是汉字也不能把命中挡掉，右边才是构词的那一半。"""
    read = classify_part(_component("U7", value="功率MOS管 60V", pins=3))
    assert read.kind == KIND_TRANSISTOR


def test_the_cjk_sentence_listing_interfaces_is_still_not_a_part_fact() -> None:
    """192B ① 的钉子必须留着：`USB和CAN` 里的 `USB` 是罗列，不是连接器。

    构词后缀的名单只收「与缩写构词的名词」（`管`），`和` 这类连词仍挡住——这正是
    本批不走「改成 ASCII 边界」的原因。
    """
    from boardwise.core.partkind import _kind_of_words

    assert _kind_of_words("cpu、usb和can")[0] == "unknown"
    assert _kind_of_words(MCU_TEXT.lower())[0] == KIND_IC
    assert classify_part(_component("U1", props={"LCSC Part Name": MCU_TEXT}, pins=48)).kind == KIND_IC


# ---------------------------------------------------------------- 625B-02


def test_a_bridge_chip_whose_name_says_usb_is_still_an_ic() -> None:
    """`USB 转串口 CH340C` 是一颗桥接芯片，不是连接器。

    修前读数（REPRO §625B-02）：`connector` / `basis=metadata`（hit `'USB'`），于是
    `decap` 用 `.kind` 判 IC 时真 IC 离开 IC 集合——**假阴**：这一脚不再被要求旁路电容。
    """
    read = classify_part(
        _component("U9", props={"LCSC Part Name": "USB 转串口 CH340C"}, pins=3)
    )
    assert read.kind == KIND_IC


def test_the_word_usb_still_names_a_connector_when_the_designator_does() -> None:
    """接口词只在**不否掉 IC 位号**时不说话；`USB1` 这种连接器位号照旧读 connector。

    同一份词表、同一套边界：换的是位号，不是词。
    """
    read = classify_part(_component("USB1", props={"LCSC Part Name": "USB 母座"}, pins=4))
    assert read.kind == KIND_CONNECTOR
    assert "'USB'" in read.reason


def test_the_bare_word_still_reads_a_connector_at_the_word_reader() -> None:
    """192B ① 的正面钉子：`_kind_of_words("usb 连接器")` 是 connector，不变。

    位号门槛在 :func:`classify_part` 的读序里，不在词表读取器里——后者没有位号可看。
    """
    from boardwise.core.partkind import _kind_of_words

    assert _kind_of_words("usb 连接器")[0] == KIND_CONNECTOR


# ---------------------------------------------------------------- 625B-03


def test_a_full_width_designator_names_its_own_family() -> None:
    """`Ｒ１`：两个前缀读取器必须读同一个（归一后的）身份串。

    修前读数（REPRO §625B-03）：`unknown` / `basis=''`——`_prefix_of` 拿到 `Ｒ`，
    `designator_category` 的 `^([A-Za-z]+)` 在 `Ｒ` 上不匹配，两个读取器各读各的。
    """
    resistor = classify_part(_component("Ｒ１", value="10k", pins=2))
    assert resistor.kind == KIND_RESISTOR
    assert resistor.basis == "prefix"

    ic = classify_part(_component("Ｕ３", pins=8))
    assert ic.kind == KIND_IC
    assert ic.basis == "prefix"


def test_an_ascii_designator_reads_exactly_as_it_did() -> None:
    """归一的对照：ASCII 位号一位不变，理由文本里的位号也还是原文。"""
    read = classify_part(_component("R2", value="0R", pins=2))
    assert read.kind == KIND_RESISTOR
    assert "the designator prefix 'R'" in read.reason


# ---------------------------------------------------------------- 625B-06


def test_the_pin_floor_fires_on_a_count_of_zero_but_not_on_an_absent_count() -> None:
    """625B-06 复核：**不修**，把两种「没有脚」分开钉住。

    * 模型件 `Component.pins` 是 `list[Pin]`（`core/model.py:142`，`default_factory=list`），
      生产路径上永远有计数；空表 = 0 脚，地板照常生效（`unknown` / `pin-floor`）；
    * 鸭子类型调用方**没有** `pins` 属性时读不到计数，`_refuse_a_two_pin_ic` 只对着一个
      「没有的数字」不判（`partkind.py:819`）。把这一支也判 unknown，`decap` 就会对每一颗
      「调用方没数脚」的 IC 都不再要旁路电容——那是 127b 地板明确不覆盖的**假阴**方向。
    """
    zero = _component("U13", pins=0)
    read = classify_part(zero)
    assert read.kind == "unknown"
    assert read.basis == "pin-floor"

    duck = SimpleNamespace(designator="U13", value="", footprint="", mpn="", props={})
    duck_read = classify_part(duck)
    assert duck_read.kind == KIND_IC
    assert duck_read.basis == "prefix"

    # 声明了 `pin_floor=False` 的调用方（问的不是脚数）照旧绕开地板，见 classify_part 文档。
    assert classify_part(_component("U13", pins=0), pin_floor=False).kind == KIND_IC
