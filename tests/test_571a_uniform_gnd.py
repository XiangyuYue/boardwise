"""571-A-H1: 一个标记都没有的地网，`uniform-gnd` 不许判通过。

挖洞批 571（`outputs/hole571/TRIAGE.md` §1、`outputs/hole571/a/REPRO.md` 的 571A-H1
行）：`uniform-gnd` 只比「旗标 vs 标签」混用，从不问地网到底有没有被表达 —— 0 个
标记时 `styles` 为空，函数直接 `return None`。同一条地网于是有两把尺：相邻的
`_gnd_outlet_finding`（088b）把「0 个出处符号」当不合格，`uniform-gnd` 说「统一」。

本批只修这半句：0 个标记（既无 `power_symbols` 也无 `labels` 表达该地网）必须返回
finding。**不加第二把尺**：判据仍是 net 级「表达」，一处标签即已表达 —— 电气连通由
导线表达，053 sec.3 的「地表达统一」说的是不混用，不是每个引脚都要挂标记。

每条断言都在变异下先红（见 `evidence/571a1/REPORT.md`）：把 0 标记分支改回
`return None` → 第 1 条红；让 0 标记的 detail 不含网名 / 用别的 kind → 第 1 条红；
让 0 标记与 1 标记都报 → 三条负控红。
"""

from __future__ import annotations

from boardwise.core.circuitspec import CircuitSpec, SpecNet
from boardwise.core.layoutplan import LayoutLabel, LayoutPlan, LayoutPowerSymbol
from boardwise.engines import drawcompiler as dc

#: 一条地网，一个成员 —— 图纸侧表达才是本批的争论点，成员不参与判定。
GND = SpecNet(id="GND", cls="gnd", members=["C1.2"])
SIGNAL = SpecNet(id="OUT", cls="signal", members=["R1.2"])


def _circuit(*nets: SpecNet) -> CircuitSpec:
    return CircuitSpec(nets=list(nets))


def _label(net: str = "GND") -> LayoutLabel:
    return LayoutLabel(net=net, text=net, bbox=(0.0, 0.0, 10.0, 4.0))


def _flag(net: str = "GND") -> LayoutPowerSymbol:
    return LayoutPowerSymbol(symbol_ref=f"PWR-{net}", net=net)


# ------------------------------------------------------- 先红：0 标记必须报


def test_a_ground_expressed_by_nothing_at_all_is_a_finding():
    """571-A-H1 的因果项：0 个标记 = 没有任何表达的裸导体，不是「统一」。

    同一个计划、同一条地网，088b 的 `_gnd_outlet_finding` 早就判不合格；一条地网
    不能同时被判「统一」和「无人命名」。
    """
    finding = dc._uniform_gnd_finding(LayoutPlan(), _circuit(GND), "GND")
    assert finding is not None, "一条既无旗标也无标签的地网被判了通过（571-A-H1）"
    assert finding.kind == dc.KIND_OBLIGATION_MISSING
    assert finding.objects == ("circuitSpec.nets[GND]",)
    # detail 必须点名是哪条网、并引同源裁决，读者才知道该去表达什么
    assert "GND" in finding.detail
    assert "053" in finding.detail and "088b" in finding.detail


def test_the_two_rulers_no_longer_answer_opposite_on_one_bare_ground():
    """同一条地网、同一个计划：uniform-gnd 与 gnd-outlet 都说不合格。"""
    plan, circuit = LayoutPlan(), _circuit(GND)
    assert dc._uniform_gnd_finding(plan, circuit, "GND") is not None
    assert dc._gnd_outlet_finding(plan, "GND") is not None


# ------------------------------------------------- 负控：net 级「已表达」即通过


def test_one_label_and_no_flag_still_passes():
    """一处标签、其余光脚 → 不报（本批明确不发明「逐脚标记」的第二把尺）。"""
    plan = LayoutPlan(labels=[_label()])
    assert dc._uniform_gnd_finding(plan, _circuit(GND), "GND") is None


def test_one_flag_and_no_label_still_passes():
    """一处旗标、无标签 → 不报（旗标是地网的常态表达）。"""
    plan = LayoutPlan(power_symbols=[_flag()])
    assert dc._uniform_gnd_finding(plan, _circuit(GND), "GND") is None


def test_a_net_that_is_not_ground_is_out_of_scope():
    """非 gnd 类网不归这条义务管（既有早退不许被 0 标记分支吃掉）。"""
    assert dc._uniform_gnd_finding(LayoutPlan(), _circuit(SIGNAL), "OUT") is None
    assert dc._uniform_gnd_finding(LayoutPlan(), _circuit(GND), "NO_SUCH_NET") is None


# ------------------------------------------- 既有语义：旗标 + 标签仍判「混用」


def test_flag_and_label_together_is_still_mixed():
    """既有 `len(styles) > 1` 语义不许被 0 标记分支破坏。"""
    plan = LayoutPlan(power_symbols=[_flag()], labels=[_label()])
    finding = dc._uniform_gnd_finding(plan, _circuit(GND), "GND")
    assert finding is not None
    assert finding.kind == dc.KIND_OBLIGATION_MISSING
    assert "flag:PWR-GND" in finding.detail and "label" in finding.detail
