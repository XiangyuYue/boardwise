"""628A：`flyback.py` 的五条洞（A-02/A-03 本轮未修，见 `evidence/628a/REPORT.md`）。

这一批的判词与前面几批同族：**跨隔离带的件必须被点名**（无论它几只脚）、
**关系跟声明的侧走**（纵向也是侧）、**判据不许拿件 id 比网 id**、**开关不是恰好三网**、
**拒绝文书不许把本语法的限制写成电路的定律**。

夹具复用 `test_113_flyback_grammar`（岳 110 的最小可绑电路与库），只在字面量上加件/改网。
"""

from __future__ import annotations

import test_113_flyback_grammar as t113

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.engines.grammar.base import (
    ABOVE,
    BELOW,
    FAILURE_FACTS_MISSING,
)

PROV = t113.PROV


# --------------------------------------------------------------------- inputs


def _payload() -> dict:
    return t113.minimal_circuit().to_jsonable()


def _add_part(payload: dict, part_id: str, symbol: str, pins: dict[str, str]) -> None:
    """Add a part and put its pins on the named nets (`{net: pin}`)."""
    payload["parts"].append({"id": part_id, "symbolRef": symbol, "provenance": PROV})
    for net in payload["nets"]:
        pin = pins.get(net["id"])
        if pin:
            net["members"].append(f"{part_id}.{pin}")


def _bind(payload: dict, presentation: PresentationSpec | None = None):
    return t113._bind(CircuitSpec.from_dict(payload), presentation)


def _detail(result) -> str:
    return " ".join(item.detail for item in result.failures)


# ================================================================== 628A-01
# 隔离边界的短路检查只对二端件成立。


def test_a01_a_three_net_part_across_the_barrier_is_refused_by_name():
    """Y3 一脚在 PGND、一脚在 SEC_GND，第三脚在 COMP：三脚件，跨了两族地。

    旧读数：`_short_failure` 只遍历 `state.edges`（二端件），Y3 不在表里，
    于是 `ok=True` 且证据零字 —— 而角色表与 docstring 把「哪件允许跨带」写成已判。
    """
    payload = _payload()
    _add_part(payload, "Y3", "C", {"PGND": "1", "SEC_GND": "2", "COMP": "3"})
    result = _bind(payload)

    assert result.ok is False
    detail = _detail(result)
    assert "Y3" in detail, detail
    assert "isolation" in detail, detail


def test_a01b_a_four_net_part_with_no_power_net_is_refused_too():
    """Y9 有四个网（PGND/SEC_GND/COMP/GATE），一个 power 网都没有。

    旧读数：`wide` 的豁免写成 `len(nets) >= 4`，于是**任何**四网件都被当成
    合法跨带件 —— 只有真正绑成变压器的那一件才该被豁免。
    """
    payload = _payload()
    _add_part(payload, "Y9", "C",
              {"PGND": "1", "SEC_GND": "2", "COMP": "3", "GATE": "4"})
    result = _bind(payload)

    assert result.ok is False
    assert "Y9" in _detail(result), _detail(result)


def test_a01c_the_two_terminal_short_keeps_its_own_wording():
    """对照组：二端跨族件仍被拒，且仍说「is a two-terminal element」。"""
    payload = _payload()
    _add_part(payload, "C99", "C", {"PGND": "1", "SEC_GND": "2"})
    result = _bind(payload)

    assert result.ok is False
    detail = _detail(result)
    assert "C99" in detail and "two-terminal" in detail, detail


# ================================================================== 628A-04
# 三处按 `out_side == "left"/"right"` 派生横向关系。


def test_a04_a_vertical_output_side_gives_a_vertical_band_relation():
    """`sidePreferences.output='top'`：光耦与误差放大器的带关系该是上下。

    旧读数：`band_side = LEFT_OF if out_side == "right" else RIGHT_OF`，纵向值
    落进 else，得到 `right-of U5->U4`，理由串却自称「input-side half」——
    约束与理由互相矛盾（同一页 `left-of R7` 与 `right-of U5` 分居两侧）。
    """
    presentation = t113.minimal_presentation().to_jsonable()
    presentation["sidePreferences"]["output"] = "top"
    result = _bind(_payload(), PresentationSpec.from_dict(presentation))

    assert result.ok is True
    band = {
        (item.subject, item.object): item for item in result.constraints
    }[("U5", "U4")]
    assert band.kind in (ABOVE, BELOW), band.kind
    assert "right of" not in band.reason and "left of" not in band.reason, band.reason


# ================================================================== 628A-05
# `_sense_on` 的排除守卫拿件 id 比网 id。


def test_a05_a_sense_part_named_like_a_net_is_still_the_sense():
    """把采样电阻 `R5` 改名成 `SW`（与开关节点网同名）——电路没变。

    旧读数：`if part_id in switch_nets` 命中，采样电阻被跳过，整条链读不出，
    拒因说「the flyback chain does not close」。答案由拼写决定。
    """
    payload = _payload()
    for part in payload["parts"]:
        if part["id"] == "R5":
            part["id"] = "SW"
    for net in payload["nets"]:
        net["members"] = [member.replace("R5.", "SW.") for member in net["members"]]

    result = _bind(payload)

    assert result.ok is True, _detail(result)
    assert "SW" in {item.part_id for item in result.bindings}, result.bindings


# ================================================================== 628A-06
# 四网开关（Kelvin 源）让合法反激被拒。


def test_a06_a_four_net_switch_is_still_the_switch():
    """Q1 多一只 Kelvin 源脚（第四个网），仍是开关。

    旧读数：`_switches_on` 硬要求「恰好三个网」，四网开关不被认作开关，
    整条链读不出，拒因说「the flyback chain does not close」并让用户查拓扑。
    """
    payload = _payload()
    payload["nets"].append({
        "id": "KELVIN", "class": "signal", "members": ["Q1.4"], "provenance": PROV,
    })
    result = _bind(payload)

    assert result.ok is True, _detail(result)
    assert result.parts_of("switch") == ("Q1",)


# ================================================================== 628A-07
# 无光耦的 PSR 反激被拒，拒因断言「a flyback's regulation crosses optically」。


def test_a07_a_psr_board_is_refused_as_this_grammars_limit_not_the_topology():
    """拆掉光耦：原边反馈（PSR/辅助绕组）反激是合法设计类。

    旧读数：`circuit-invalid` + 「a flyback's regulation crosses optically」——
    把「本语法只认光耦」写成「反激的稳压靠光耦」。应改 `facts-missing` 并
    把断言限定到本语法（110 的 TL431+PC817 页）。
    """
    result = t113._bind(t113._without_part(t113.minimal_circuit(), "U5"))

    assert result.ok is False
    (failure,) = result.failures
    assert failure.category == FAILURE_FACTS_MISSING, failure.category
    assert "a flyback's regulation crosses optically" not in failure.detail
    assert "this grammar" in failure.detail, failure.detail
