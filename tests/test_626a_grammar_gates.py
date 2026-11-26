"""626A：`ic_periphery` / `mixed_island` 六条洞（`outputs/hole626/TRIAGE.md` 缝 A）。

同一把尺继续量：**被丢掉的件、没绑的轨、没读的方向，都必须说出来**，而理由句不许
把「没读」写成「没写」。六条里有三条是「零字消失」（三脚件、两脚同网件、stray），
两条是「空串冒充事实」（mixed-island 的 rail/gnd），一条是「默认旁证」（第二张电源网）。

约定与既有文法测试一致：电路、图纸、符号库全部手写字面量，夹具复用
`test_098_ic_periphery.py` 的构造器（岳样板与库），测试之间不共享可变状态。
"""

from __future__ import annotations

import test_098_ic_periphery as t098

from boardwise.engines.grammar import mixed_island

PROV = t098.PROV


def _mixed(profiles=None):
    return mixed_island.MixedIslandGrammar(profiles or t098.library())


def _mixed_presentation(parts: list[str], core: str = "U1"):
    return t098.presentation(
        modules=[
            {
                "id": "island",
                "parts": list(parts),
                "role": "the HMI island",
                "grammarRef": "mixed-island",
                "core": core,
            }
        ]
    )


def _text(result) -> str:
    return " ".join(item.evidence for item in result.bindings)


# ================================================================== 626A-01
# mixed-island 核心不坐任何 power/gnd 时，挂真实 GND 的二端件静默失去角色。


def test_a01_a_branch_to_a_ground_the_core_is_not_on_is_named_not_lost():
    """U1 一条脚都没有落在 power/gnd 上，C1 却挂在 XI 与真正的 GND 之间。

    旧读数：`ok=True`、`roles=[('core','U1')]`、C1 零字 —— 空串 `gnd=""` 让
    `here & {rail, gnd}` 判不成 shunt，`here <= signals` 也判不成 bridge，
    于是它既不绑也不拒也不提。mixed-island 不发明轨/回流是对的，但那条支路
    必须被点名（它是接在真实地网上的，只是这块岛不引用它）。
    """
    circuit = t098.circuit(
        [t098.part("U1", "SOIC-16-CORE", "CH340G"),
         t098.part("C1", "C0402", "100nF")],
        [
            t098.net("XI", "signal", ["U1.4", "C1.1"]),
            t098.net("XO", "signal", ["U1.5"]),
            t098.net("SIG2", "signal", ["U1.6"]),
            t098.net("SIG3", "signal", ["U1.7"]),
            t098.net("GND", "gnd", ["C1.2"]),
        ],
    )
    result = _mixed().bind(circuit, _mixed_presentation(["U1", "C1"]))

    assert result.ok is True
    text = _text(result)
    assert "C1" in text, text
    assert "this core does not sit on" in text, text


# ================================================================== 626A-02
# 纵向 sidePreferences 被丢弃，证据却说「portRoles 什么都没写」。


def test_a02_a_vertical_declared_side_is_not_reported_as_undeclared():
    """`portRoles` 声明了 RXD=input，而 `sidePreferences.input` 是 `top`（纵向）。

    旧读数：`_orientation` 因为不是左右而返回 None，`_signal_note` 便写成
    「no declared direction — portRoles states none」，与**真的没写 portRoles**
    的图纸逐字相同。声明了却读不成左右，与没声明是两件事。
    """
    circuit, presentation = t098.sample(
        sides={"input": "top", "output": "left", "load": "right"}
    )
    result = t098.bind(circuit, presentation)

    assert result.ok is True
    core = t098.core_evidence(result)
    assert "RXD" in core, core
    assert "RXD (no declared direction" not in core, core
    assert "vertical side" in core, core
    assert "sidePreferences['input']='top'" in core or "input]= 'top'" in core or (
        "top" in core
    ), core


# ================================================================== 626A-03
# 模块内三脚以上器件从不进入 `_periphery`：三脚接上核心与三脚全悬空读数相同。


def test_a03_a_three_pin_part_of_the_module_is_named_on_success():
    """J5 是四脚座，三只脚画在 VCC/GND/XI 上。

    旧读数：`roles` 只有 core/bridge/shunt 里那些两脚件，J5 零字 —— 它「不是
    二端件」是对的（臂集只数被提到的脚），但读者必须看见它被谁挡在门外、
    为什么。这把尺 627A 已经提到 `base.arm_note`，本批接上。
    """
    circuit = t098.circuit(
        [t098.part("U1", "SOIC-16-CORE", "CH340G"),
         t098.part("C3", "C0402", "100nF"),
         t098.part("J5", "USB-A-4P", "USB")],
        [
            t098.net("VCC", "power", ["U1.16", "C3.1"]),
            t098.net("GND", "gnd", ["U1.1", "C3.2", "J5.2"]),
            t098.net("XI", "signal", ["U1.4", "J5.1"]),
            t098.net("XO", "signal", ["U1.5", "J5.3"]),
        ],
    )
    result = t098.bind(circuit, t098.presentation())

    assert result.ok is True
    text = _text(result)
    assert "J5" in text, text
    assert "not usable as a branch" in text, text
    assert "4 pins" in text, text


# ================================================================== 626A-04
# 两脚同挂一张网的二端件在 `two_terminal_parts` 之后静默消失。


def test_a04_a_two_pin_part_on_one_net_is_named_as_a_short():
    """R9 的两只脚都画在 XI 上（短路件），臂集按设计不收它。

    旧读数：零字。它与「这个件不存在」在输出里长得一模一样，而它其实是一个
    需要人看一眼的短路。
    """
    circuit = t098.circuit(
        [t098.part("U1", "SOIC-16-CORE", "CH340G"),
         t098.part("C3", "C0402", "100nF"),
         t098.part("R9", "R0402", "0R")],
        [
            t098.net("VCC", "power", ["U1.16", "C3.1"]),
            t098.net("GND", "gnd", ["U1.1", "C3.2"]),
            t098.net("XI", "signal", ["U1.4", "R9.1", "R9.2"]),
        ],
    )
    result = t098.bind(circuit, t098.presentation())

    assert result.ok is True
    text = _text(result)
    assert "R9" in text, text
    assert "both pins are on one net" in text, text


# ================================================================== 626A-05
# `allow_unowned_branches` 把 strays 直接吞掉。


def test_a05_a_stray_is_named_even_when_the_policy_allows_it():
    """D1 两只脚都在信号网上，一只也不碰核心的脚 —— 策略允许它不被绑定。

    旧读数：允许时（mixed-island 的默认）`strays` 被整段跳过，D1 零字。
    「允许不绑」不等于「不需要说」：读者分不清它是被放过还是不存在。
    """
    circuit = t098.circuit(
        [t098.part("U1", "SOIC-16-CORE", "CH340G"),
         t098.part("D1", "C0402", "LED")],
        [
            t098.net("XI", "signal", ["U1.4"]),
            t098.net("XO", "signal", ["U1.5"]),
            t098.net("SIG2", "signal", ["U1.6"]),
            t098.net("SIG3", "signal", ["U1.7"]),
            t098.net("A", "signal", ["D1.1"]),
            t098.net("K", "signal", ["D1.2"]),
        ],
    )
    result = _mixed().bind(circuit, _mixed_presentation(["U1", "D1"]))

    assert result.ok is True
    text = _text(result)
    assert "D1" in text, text
    assert "unbound" in text, text


# ================================================================== 626A-06
# 核心同时坐两张电源网时只留 id 序第一张，另一张在任何输出里都不出现。


def test_a06_a_second_rail_the_core_sits_on_is_named():
    """U1.16 在 VCC、U1.15 在 AVCC，两张都是 power。

    旧读数：`_net_on_core` 只回 id 序第一张（AVCC < VCC），另一张在任何
    binding/obligation/证据里都不出现。绑一张是对的（一块岛一个轨），
    但另一张必须点名。
    """
    circuit = t098.circuit(
        [t098.part("U1", "SOIC-16-CORE", "CH340G"),
         t098.part("C3", "C0402", "100nF"),
         t098.part("C4", "C0402", "100nF")],
        [
            t098.net("VCC", "power", ["U1.16", "C3.1"]),
            t098.net("AVCC", "power", ["U1.15", "C4.1"]),
            t098.net("GND", "gnd", ["U1.1", "C3.2", "C4.2"]),
        ],
    )
    result = t098.bind(circuit, t098.presentation())

    assert result.ok is True
    text = _text(result)
    assert "also sits on" in text, text
    assert "also sits on VCC" in text, text
