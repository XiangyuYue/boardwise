"""627A：文法共享框架的九条洞（`outputs/hole627/TRIAGE.md` 缝 A）。

这一批只修缝 A 的文件域——`engines/grammar/base.py` 与 `engines/grammar/ldo.py`。
洞表里的 04-H 家族七条中，**H2/H5/H7 是 `base.py` 的共享缺陷**，六本文法都继承；
626A-03/04 与 627A-08 因此是同一个根（`base.two_terminal_parts` 只数**被提到**的脚），
627B-03（三脚符号缺一脚被当二端件）是它的反向形态。

每条用例钉两件事：洞表里的**现状读数**不再成立，以及**理由说的是真的那一面**
（拒因/证据里出现的那句话必须是它真做了的事，而不是它想做却没做的事）。

约定与既有文法测试一致（`test_053b_grammar.py`）：电路、图纸、符号库全部手写字面量，
夹具复用 `test_053b_grammar` 的构造器，测试之间不共享可变状态。
"""

from __future__ import annotations

import test_053b_grammar as t053

from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolPin, SymbolProfile
from boardwise.engines.grammar import base, ldo
from boardwise.engines.grammar.base import (
    FAILURE_PRESENTATION_POOR,
    PROVENANCE_AI,
    PROVENANCE_UNSTATED,
    PROVENANCE_USER_STATED,
    PROVENANCE_VERIFIED,
)

PROV = t053.PROV


# --------------------------------------------------------------------- inputs


def _profile(*rows: tuple[str, str, str]) -> SymbolProfile:
    """``(number, role, side)`` per pin — the role is the name and the electricalRole."""
    pins = [
        SymbolPin(
            number=number,
            name=role,
            tip=(float(-40 + 20 * index), 0.0),
            direction=side,
            direction_source="body-box",
            electrical_role=role,
            role_source="pin-name",
        )
        for index, (number, role, side) in enumerate(rows)
    ]
    return SymbolProfile(symbol_ref="SYM", title="SYM", pins=pins)


def _duplicate_vin_profile() -> SymbolProfile:
    """A regulator whose VIN is drawn twice (the measured AMS1117 VOUT shape)."""
    return _profile(
        ("1", "VIN", "left"),
        ("2", "VOUT", "right"),
        ("3", "GND", "left"),
        ("4", "VIN", "right"),
    )


def _two_core_circuit() -> t053.CircuitSpec:
    """U1 a readable regulator, U2 a regulator whose VIN and VOUT are shorted."""
    return t053._circuit(
        [
            t053._part("U1", "AMS1117-3.3", "AMS1117-3.3"),
            t053._part("U2", "AMS1117-3.3", "AMS1117-3.3"),
            t053._part("C1", "C0805", "10u"),
            t053._part("C2", "C0402", "100n"),
        ],
        [
            t053._net("VIN5", "power", ["U1.3", "C1.1"]),
            t053._net("3V3", "power", ["U1.2", "C2.1"]),
            t053._net("GND", "gnd", ["U1.1", "C1.2", "C2.2", "U2.1"]),
            t053._net("SHRT", "power", ["U2.2", "U2.3"]),
        ],
    )


def _same_net_aux_circuit() -> tuple[t053.CircuitSpec, SymbolProfile]:
    """EN and NR resolved onto **one** net, with one capacitor on it."""
    profile = t053._regulator_profile(
        symbol_ref="AMS1117-ADJ", extra=(("4", "EN"), ("5", "NR"))
    )
    circuit = t053._circuit(
        [
            t053._part("U1", "AMS1117-ADJ", "AMS1117-ADJ"),
            t053._part("C1", "C0805", "10u"),
            t053._part("C2", "C0402", "100n"),
            t053._part("C3", "C0402", "10n"),
        ],
        [
            t053._net("VIN5", "power", ["U1.3", "C1.1"]),
            t053._net("3V3", "power", ["U1.2", "C2.1"]),
            t053._net("GND", "gnd", ["U1.1", "C1.2", "C2.2", "C3.2"]),
            t053._net("AUX", "signal", ["U1.4", "U1.5", "C3.1"]),
        ],
    )
    return circuit, profile


def _text(result) -> str:
    return " ".join(item.evidence for item in result.bindings)


# ================================================================== 627A-01
# 拒因说「既不是 net member 也不是 explicit nc」，而那只脚**就在** nc[] 里。


def test_a01_a_pin_listed_in_nc_is_named_as_such_not_denied():
    """U1 的 VIN 画成两只脚：一只在 nc[] 里，一只根本没提。

    旧读数：`U1 (LDO-DUPVIN) has a VIN pin (number='1'…) but the CircuitSpec
    states no connection for it — neither a net member nor an explicit nc`
    ——与输入里 `nc: ["U1.1"]` 直接矛盾。拒得对（VIN 没有网就不成调压器），
    但理由必须说出「1 在 nc[]、4 没提」这两件不同的事。
    """
    circuit = t053._circuit(
        [t053._part("U1", "LDO-DUPVIN", "LDO-DUPVIN")],
        [
            t053._net("3V3", "power", ["U1.2"]),
            t053._net("GND", "gnd", ["U1.3"]),
        ],
        nc=["U1.1"],
    )
    book = {"LDO-DUPVIN": _duplicate_vin_profile()}
    result = t053._bind(circuit, t053._presentation("ldo"), book)

    assert result.ok is False
    (failure,) = result.failures
    assert failure.subject == "U1"
    assert "VIN" in failure.detail
    assert "no net on any VIN pin" in failure.detail, failure.detail
    # 这两句是事实的两半：一只在 nc[]，一只没提。
    assert "listed in nc[]" in failure.detail, failure.detail
    assert "not mentioned at all" in failure.detail, failure.detail
    # 旧句否认 nc[] 的存在，必须消失。
    assert "neither a net member nor an explicit nc" not in failure.detail


# ================================================================== 627A-02
# reason 断言「input 与 output 在相反两侧」，而代码从不检查，同侧声明照样绑。


def test_a02_same_side_input_and_output_is_refused_instead_of_asserted_opposite():
    """图纸把 input 与 output 都声明在 left：053 sec.3 的要求被违反。

    旧读数：`ok=True`，每一条约束的 reason 都写着「an LDO's input and output
    are on opposite sides」——一句代码没有核过、图纸正好相反的话。
    """
    presentation = t053._presentation(
        "ldo", sidePreferences={"input": "left", "output": "left"}
    )
    result = t053._bind(
        t053._ldo_circuit(), presentation, t053._ldo_profiles()
    )

    assert result.ok is False
    (failure,) = result.failures
    assert failure.category == FAILURE_PRESENTATION_POOR
    assert "left" in failure.detail
    assert "opposite" in failure.detail
    assert "sidePreferences" in failure.action


# ================================================================== 627A-03
# 第二颗「读得出但被拒」的核心在另一颗绑上之后无痕消失。


def test_a03_a_readable_core_that_is_refused_is_named_while_another_binds():
    """U2 的 VIN/VOUT 同网（`_core_from` 自报 circuit-invalid），U1 正常。

    旧读数：`ok=True`，`evidence mentions U2: False`——同一份 `problems` 在
    `if candidates: return candidates, []` 处被丢掉，读者不知道还有一颗调压器
    被读出来又拒掉了。
    """
    result = t053._bind(
        _two_core_circuit(), t053._presentation("ldo"), t053._ldo_profiles()
    )

    assert result.ok is True
    text = _text(result)
    assert "U2" in text, text
    assert "shorted" in text, text


# ================================================================== 627A-04
# 两把尺：`shared_module` 对「一件两 module」答 'A'，`module_of_part` 答 ''。


def test_a04_shared_module_answers_only_when_every_part_agrees_on_one():
    """`module_of_part` 的 docstring 说「没有单一答案时答空串」，`shared_module` 违背它。

    交集的正确读法：一个件声明在两个 module、另一个只在一个，交集是一个
    ⇒ 仍然有单一答案；只有交集本身多于一个 module 才是「没有单一答案」。
    """
    presentation = t053._presentation(
        "ldo",
        modules=[
            {"id": "mA", "parts": ["U1"], "role": "core"},
            {"id": "mB", "parts": ["U1", "C1"], "role": "core"},
        ],
    )

    assert base.module_of_part(presentation, "U1") == ""
    assert base.shared_module(presentation, ["U1"]) == ""
    assert base.shared_module(presentation, ["U1", "C1"]) == "mB"


# ================================================================== 627A-05
# 核心声明在两个 module 时 `module_of_part` 答 ''，模块守卫整段失效。


def test_a05_a_core_declared_in_two_modules_is_refused_and_both_are_named():
    """跨 module 的电容守卫靠 `core.module` 的真值，空串把它关掉。

    旧读数：`module_of_part=''` 时 `if core.module and …` 整段为假，别的 module
    里的电容照样被绑成 `in_caps`。核心自己不唯一时，唯一诚实的答复是拒绝并
    点名两个 module（与电压分压器跨 module 的拒法一致）。
    """
    presentation = t053._presentation(
        "ldo",
        modules=[
            {"id": "mA", "parts": ["U1", "C1"], "role": "core"},
            {"id": "mB", "parts": ["U1"], "role": "supply"},
            {"id": "mC", "parts": ["C2"], "role": "supply"},
        ],
    )
    result = t053._bind(
        t053._ldo_circuit(), presentation, t053._ldo_profiles()
    )

    assert result.ok is False
    detail = " ".join(item.detail for item in result.failures)
    assert "mA" in detail and "mB" in detail, detail


# ================================================================== 627A-06
# 04-H7：预算只在递归入口查，返回值没有「预算用尽」这一档。


def test_a06_series_paths_says_which_budget_stopped_it():
    """三种旧读数：70 条平行臂出 70 条链（`MAX_CHAINS=64` 没生效）、真存在的
    7 臂链得 `[]`（与「没有链」不可分）、`start == goal` 得 `[]`。

    `:299-300` 的承诺是「预算用尽时说 not found inside the budget，永不说
    no solution」——返回值因此必须带档位，而不是让调用者猜。
    """
    search = getattr(base, "series_paths_with_status")

    parallel = {f"R{index:02d}": ("N0", "N1") for index in range(70)}
    many = search(parallel, "N0", "N1")
    assert len(many.paths) == base.MAX_CHAINS
    assert many.outcome == "budget-paths"
    # 包装函数与带档位的那个必须是同一次搜索的两种写法。
    assert base.series_paths(parallel, "N0", "N1") == list(many.paths)

    chain = {f"R{index}": (f"N{index}", f"N{index + 1}") for index in range(7)}
    deep = search(chain, "N0", "N7")
    assert deep.paths == ()
    assert deep.outcome == "budget-arms"

    assert search(chain, "N0", "N0").outcome == "start-is-goal"
    assert search({"R1": ("A", "B")}, "A", "C").outcome == "none"

    # 不超预算的正常链仍然是 found，且内容不变。
    ok = search(chain, "N0", "N6")
    assert ok.outcome == "found"
    assert [len(path) for path, _nets in ok.paths] == [6]


# ================================================================== 627A-07
# 一条网上两个非核心角色，把同一颗电容绑两次。


def test_a07_one_capacitor_on_one_aux_net_is_bound_once():
    """EN 与 NR 解析到同一张网 AUX：一颗 C3 只能有一次 aux_branch 绑定。

    旧读数：`aux_branch: ['C5','C5']`——`_aux_caps` 按 role 循环、按网匹配，
    网相同就 append 两次；`near` 与 `owned-branch` 跟着各重复一份。
    """
    circuit, profile = _same_net_aux_circuit()
    book = t053._ldo_profiles(symbol_ref="AMS1117-ADJ", profile=profile)
    result = t053._bind(circuit, t053._presentation("ldo"), book)

    assert result.ok is True
    assert result.parts_of(ldo.AUX_BRANCH) == ("C3",)
    near = [
        item
        for item in result.constraints
        if item.kind == base.NEAR and item.subject == "C3"
    ]
    assert len(near) == 1


# ================================================================== 627A-08
# 04-H2 的正身：`two_terminal_parts` 只数**被提到**的脚，丢掉的件从不出现。


def test_a08_the_arm_reader_names_the_parts_it_could_not_use():
    """Q1 是 SOT-23（符号三个脚），电路只提了两只 → 旧读数把它当二端件。

    有符号库时臂必须按**符号的脚数**判：三个脚的符号不是二端件，
    并把「为什么不是」写出来，让读者看到它存在过；没有符号库时只能按
    spec 数，那时也必须说明尺子是哪一把（`None` 与「两脚」不是同一件事）。
    """
    circuit = t053._circuit(
        [
            t053._part("U1", "AMS1117-3.3", "AMS1117-3.3"),
            t053._part("C1", "C0805", "10u"),
            t053._part("Q1", "SOT23", "MMBT3904"),
        ],
        [
            t053._net("VIN5", "power", ["U1.3", "C1.1", "Q1.1"]),
            t053._net("3V3", "power", ["U1.2"]),
            t053._net("GND", "gnd", ["U1.1", "C1.2", "Q1.2"]),
        ],
    )
    q_profile = SymbolProfile(
        symbol_ref="SOT23",
        pins=[
            SymbolPin(number="1", tip=(0.0, -20.0)),
            SymbolPin(number="2", tip=(0.0, 20.0)),
            SymbolPin(number="3", tip=(20.0, 0.0)),
        ],
    )
    book = t053._ldo_profiles()
    book["SOT23"] = q_profile

    arms = base.two_terminal_parts(circuit, book)
    assert "Q1" not in arms
    excluded = getattr(base, "arm_exclusions")(circuit, book)
    assert "Q1" in excluded
    assert "3" in excluded["Q1"], excluded["Q1"]

    # 文法侧：被排除的件必须在证据里出现一次，不能零字。
    result = t053._bind(circuit, t053._presentation("ldo"), book)
    assert result.ok is True
    assert "Q1" in _text(result), _text(result)

    # 没有符号库时尺子只有 spec：那时它**是**二端件，答案要随输入变。
    assert "Q1" in base.two_terminal_parts(circuit)


# ================================================================== 627A-09
# 04-H5：未登记的 token 被当成档位写进证据，下一轮比较抛 KeyError。


def test_a09_an_unregistered_provenance_token_is_unstated_and_never_raises():
    """`('verified_recipe','contract')` 曾回 `'contract'`，`('contract','ai_asserted')` 曾抛
    `KeyError: 'contract'`。

    未登记的 token 不是档位：它比 `unstated` 更弱（连事实都没陈述），所以
    秩取 `unstated`，且**永不原样回传**——证据串里出现一个没人认得的档位比
    说「没陈述」更糟。
    """
    assert base.weakest_provenance(PROVENANCE_VERIFIED, "contract") == (
        PROVENANCE_UNSTATED
    )
    # 未登记 token 的秩比每一档都弱，所以它与任何一档同列时，答案都是「没陈述」，
    # 两种排序都不许抛、也不许把 'contract' 原样回传。
    assert base.weakest_provenance("contract", PROVENANCE_AI) == PROVENANCE_UNSTATED
    assert base.weakest_provenance(PROVENANCE_AI, "contract") == PROVENANCE_UNSTATED
    assert "contract" not in base.weakest_provenance(PROVENANCE_AI, "contract")
    # 同一张表里的正常档位不受影响（这是 095 A4 钉住的那一列）。
    assert base.weakest_provenance(PROVENANCE_VERIFIED, PROVENANCE_USER_STATED) == (
        PROVENANCE_USER_STATED
    )
    assert base.weakest_provenance() == PROVENANCE_UNSTATED
