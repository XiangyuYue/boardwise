"""548C7：库内旗标补全拆分网陈述——探针结论与永久回归。

岳 2026-11-08 裁定：548C2①/B3 **不允许网络标签**，可以把旗标收入库中。
本文件把「库只多了 `PWR-GND` / `PWR-3V3` 两个实测旗形族条目」这一个变量下的
真实读数钉住（`evidence/548C7/criteria.md`）：

* 旗标入库**不移动**任何既有几何（库没变 = 字节没变，另见 C6 的各批零移动）。
* 旗标入库**没有**让 547A 的 mcu 在页面预算 `gndClustering.radius=100` 下出图，
  也没有让 E2/E3 出页或 B3 长文本变体出图——它们仍被结构化拒绝，且拒因落在
  **旗标自己的引线**上（`U1.VSSA` / `DECOUPLE_3V3_1.1` 那一脚），不是标签兜底、
  不是跨体母线、也不是「拆成 4 个节点」。
* 地/电源网在这些读数里**没有**任何网络标签陈述：拒稿的路径把 GND 降级成
  「每脚一面旗」（530A 的地规则），旗挂不上就拒绝，绝不退回 label。

因此本批生产代码零改动；这些用例是缺口证据的回归，旗标路径一旦真正打通即转红，
提示回改 548C7 的账（与 C3 的 strict xfail 同一纪律：实测通过才摘标）。
"""

from __future__ import annotations

import json

import pytest

import test_547_repeated_shunts as m547

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawcompiler as dc
from boardwise.engines import pagecompiler as pc
from boardwise.engines import readability as rd
from boardwise.engines.drawapply import load_library

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "evidence/548A/fixture"
CH343 = ROOT / "blocklib/specs/ch343_uart_v4.library.json"
PAGE_BUDGET = pc.PageCompileBudget(page_box=(0.0, 0.0, 1170.0, 825.0))


# --------------------------------------------------------------------------
# 旗标条目：CH343 实测的两个，加一个明确标注「离线别名」的 PWR-3V3
# --------------------------------------------------------------------------


def _ch343_flags() -> list[dict]:
    """`PWR-GND` (measured) and `PWR-3V3` (offline alias of the rail family).

    `PWR-3V3` reuses `PWR-+5V`'s measured extent because the rail flag family is
    one glyph; this is an **offline drawing alias** and is not a calibration of
    the host's own 3V3 flag (548C7 criteria: 不得据此宣称真机可用).
    """
    doc = json.loads(CH343.read_text(encoding="utf-8"))
    by_ref = {item["symbolRef"]: item for item in doc["profiles"]}
    gnd = json.loads(json.dumps(by_ref["PWR-GND"]))
    alias = json.loads(json.dumps(by_ref["PWR-+5V"]))
    alias["symbolRef"] = "PWR-3V3"
    alias["title"] = "PWR-3V3"
    alias["source"] = (
        "548C7 offline alias: rail-flag family extent (-5, 0, 5, 10) copied from "
        "PWR-+5V (534 r1 render measurement). The host's 3V3 flag was NOT "
        "measured in this batch; offline drawing aid only."
    )
    return [gnd, alias]


def _load_profiles(directory) -> dict[str, SymbolProfile]:
    return load_library(directory / "profiles.json")


def _load_flagged(directory) -> dict[str, SymbolProfile]:
    book = dict(_load_profiles(directory))
    assert set(book) & {"PWR-GND", "PWR-3V3"} == set(), (
        "the fixture library must not already carry the flags under test: "
        f"{sorted(set(book) & {'PWR-GND', 'PWR-3V3'})}")
    for payload in _ch343_flags():
        book[payload["symbolRef"]] = SymbolProfile.from_dict(payload)
    return book


def _document(directory, radius: int = 0):
    circuit = CircuitSpec.load(directory / "circuit.json")
    presentation = PresentationSpec.load(directory / "presentation.json")
    return circuit, presentation


def _mcu_view(directory, radius: int):
    circuit, presentation = _document(directory)
    module = presentation.module("mcu")
    sub_circuit, sub_presentation = pc._module_view(circuit, presentation, module)
    budget = dc.CompileBudget(gnd_cluster_radius=float(radius))
    return circuit, presentation, sub_circuit, sub_presentation, budget


def _refusal(result) -> dc.GrammarFailure:
    assert not result.ok, "this scenario is expected to be refused (548C7 gap)"
    assert result.failures, "a refusing compile must name its reason"
    return result.failures[0]


def _no_flag_label(plan, profiles, nets=("GND", "3V3")) -> None:
    """No declared ground/rail may be stated by a net label on the canvas.

    岳's ruling for this batch: 548C2①/B3 不许用网络标签。A plan that states these
    nets with `labels` is the rejected shape, whatever its other numbers say.
    """
    stated = {label.net for label in plan.labels}
    assert not (stated & set(nets)), (
        f"nets {sorted(stated & set(nets))} are stated by net labels; a ground or "
        "a rail must be a flag (530A) or be refused, never labelled")


# --------------------------------------------------------------------------
# 1. 模块：radius=100 的页面预算下，旗标入库仍被拒——拒因是旗的引线，不是拆网
# --------------------------------------------------------------------------


def test_the_page_budget_still_refuses_the_island_with_the_flags_in_the_library():
    _c, _p, sub_circuit, sub_presentation, budget = _mcu_view(FIXTURE, 100)
    book = _load_flagged(FIXTURE)
    result = dc.compile(sub_circuit, sub_presentation, book, budget)
    failure = _refusal(result)
    assert failure.category == dc.FAILURE_LAYOUT_UNSAT
    assert failure.subject == "GND"
    # The refusal is the flag's own lead at the pad the outlet rule names — the
    # first concrete gap. It is *not* the 548C2 "4 separate node(s)" reading:
    # the library can now state a ground with a flag, and the flag has nowhere
    # legal to hang at U1.VSSA.
    assert "flag of its own on U1.VSSA" in failure.detail, failure.detail
    assert "no lead fits anywhere around that pad" in failure.detail
    assert "netlist-partition-mismatch" not in failure.detail, (
        "the split-node refusal returned: this test's gap is the flag lead, "
        + failure.detail)
    # And the fallback did not become a label: the ground was downgraded to
    # flag-at-each-pin (530A), which is what got refused.
    assert "downgraded from a wire to a name at each pin (GND)" in failure.detail


def test_the_same_refusal_happens_without_the_cluster_radius():
    """radius=0 has one ground cluster: the gap is not the page splitting it."""
    _c, _p, sub_circuit, sub_presentation, budget = _mcu_view(FIXTURE, 0)
    result = dc.compile(sub_circuit, sub_presentation, _load_flagged(FIXTURE), budget)
    failure = _refusal(result)
    assert failure.subject == "GND"
    assert "flag of its own on U1.VSSA" in failure.detail, failure.detail


# --------------------------------------------------------------------------
# 2. 页面：E2/E3 仍 0 页，拒因落在 mcu 模块的同一条旗标引线
# --------------------------------------------------------------------------


@pytest.mark.parametrize("variant", ["e2-two-islands", "e3-three-islands"])
def test_the_two_and_three_island_pages_still_refuse_at_the_mcu_flag(variant):
    directory = ROOT / "evidence/548C/variants" / variant
    circuit, presentation = _document(directory)
    result = pc.compile_page(circuit, presentation, _load_flagged(directory),
                             PAGE_BUDGET)
    assert not result.ok, f"{variant}: a page is not expected to be drawn yet"
    assert result.pages == []
    failure = result.failures[0]
    assert failure.category == dc.FAILURE_LAYOUT_UNSAT
    assert failure.subject == "modules[mcu]", failure.subject
    assert "flag of its own on U1.VSSA" in failure.detail, failure.detail


# --------------------------------------------------------------------------
# 3. B3：长位号 + 长值行——库无旗时已能出图（26 网），旗标入库后卡在 3V3 引线
# --------------------------------------------------------------------------


def test_b3_long_text_compiles_without_flags_and_keeps_every_net():
    directory = ROOT / "evidence/548C/variants/b3-long-both"
    _c, _p, sub_circuit, sub_presentation, budget = _mcu_view(directory, 0)
    book = _load_profiles(directory)
    result = dc.compile(sub_circuit, sub_presentation, book, budget)
    assert result.ok, [
        f"[{failure.category}] {failure.subject}: {failure.detail[:200]}"
        for failure in result.failures]
    plan = result.best()
    _no_flag_label(plan, book)
    derived = rd.derive_netlist(plan, book)
    assert len(sub_circuit.nets) == 26
    # Every declared net is one node on the drawing: all of its member pins in
    # this module's view share one derived group.
    for net in sub_circuit.nets:
        declared = set(net.members)
        groups = {derived.pin_group[pin] for pin in declared
                  if pin in derived.pin_group}
        assert len(groups) <= 1, (
            f"net {net.id} is split across {len(groups)} groups: {sorted(declared)}")
    check = rd.check(plan, sub_circuit, sub_presentation, book)
    assert check.hard_violations == [], [
        violation.render() for violation in check.hard_violations]


def test_b3_long_text_with_the_flags_in_the_library_refuses_at_the_rail():
    directory = ROOT / "evidence/548C/variants/b3-long-both"
    _c, _p, sub_circuit, sub_presentation, budget = _mcu_view(directory, 0)
    result = dc.compile(sub_circuit, sub_presentation, _load_flagged(directory),
                        budget)
    failure = _refusal(result)
    assert failure.subject == "3V3"
    assert "flag of its own on DECOUPLE_3V3_1.1" in failure.detail, failure.detail
    assert "no lead fits anywhere around that pad" in failure.detail


# --------------------------------------------------------------------------
# 4. 无旗库：条目不在一律结构化披露，绝不静默退成网络标签
# --------------------------------------------------------------------------


def test_a_library_without_the_flag_entry_says_so_and_never_labels_the_net():
    directory = ROOT / "evidence/548C/variants/b3-long-both"
    _c, _p, sub_circuit, sub_presentation, budget = _mcu_view(directory, 0)
    book = _load_profiles(directory)
    ctx = type("C", (), {})()
    ctx.book = dc.profile_book(book)
    ctx.budget = dc.CompileBudget()
    ctx.ground_domains = frozenset({"GND"})
    ctx.circuit = sub_circuit
    profile, ref = dc._flag_plan(ctx, "3V3", "power")
    assert profile is None and ref == "PWR-3V3"
    profile, ref = dc._flag_plan(ctx, "GND", "gnd")
    assert profile is None and ref == "PWR-GND"
    result = dc.compile(sub_circuit, sub_presentation, book, budget)
    assert result.ok, "the long-text island compiles when its rails stay wires"
    plan = result.best()
    _no_flag_label(plan, book)
    # The absence is disclosed in the plan's own notes, not left to be inferred:
    # the rail is drawn with its name on the wire and **no symbol of its own**.
    assert any("carries no flag symbol 'PWR-3V3'" in note for note in plan.notes), (
        [note for note in plan.notes if "flag" in note][:4])
    assert any("carries no flag symbol 'PWR-GND'" in note for note in plan.notes), (
        [note for note in plan.notes if "flag" in note][:4])
