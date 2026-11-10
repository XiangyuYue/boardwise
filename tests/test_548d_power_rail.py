"""548D3：模块本地电源旗 + ``PWR-+3V3`` 精确别名。

两条裁决都只看文档，不看器件 id 或网名：

* **别名**：rail 的旗标先按原名 ``PWR-<net>`` 查；书名里没有时才退到
  ``PWR-+<net>``——只对 rail、只对 net id 不含 ``+`` 的网。判定
  （:func:`drawcompiler._flag_ref`）、缺失检查（:func:`drawcompiler._flag_plan` /
  :func:`drawcompiler._missing_flag_symbol`）和落笔用同一个真实 ref。地网不起别名，
  已有原名的网不受影响。
* **本地电源旗**：声明了两条及以上 ``seriesBranches``、且一条 power 网的所有成员
  都在同一个声明模块里时，该网按 wire 表达，由既有的 wire-style 旗梯挂**一枚**
  本地电源旗（069 sec.7）。这是旗汇聚本地支路，不是把全板母线拉过页面；GND、
  未声明、单臂的页面逐字节不变。
"""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import (
    PresentationSpec,
    SeriesBranch,
)
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawcompiler as dc

CIRCUIT_PAYLOAD = {
    "kind": "boardwise-circuit-spec",
    "specVersion": 1,
    "parts": [
        {"id": "U1", "symbolRef": "U", "value": "U", "provenance": "ai_asserted"},
        {"id": "C1", "symbolRef": "C", "value": "C", "provenance": "ai_asserted"},
    ],
    "nets": [
        {"id": "VBUS_LOCAL", "class": "power",
         "members": ["U1.1", "C1.1", "U1.2", "U1.3"], "provenance": "ai_asserted"},
        {"id": "GND", "class": "gnd", "members": ["U1.4", "C1.2"],
         "provenance": "ai_asserted"},
    ],
    "nc": [], "openInterfaces": [], "operatingConditions": {}, "draft": True,
}

PRESENTATION_PAYLOAD = {
    "kind": "boardwise-presentation-spec",
    "specVersion": 1,
    "modules": [{"id": "m1", "parts": ["U1", "C1"],
                 "role": "the rail's own supply island"}],
    "seriesBranches": [],
}

_FLAG_ROW = {"title": "power flag", "body": [-5.0, 0.0, 5.0, 10.0], "pins": []}


def _book(*refs: str) -> dict[str, SymbolProfile]:
    return {
        ref: SymbolProfile.from_dict({"symbolRef": ref, **_FLAG_ROW})
        for ref in refs
    }


def _context(book, presentation=None, ground_domains=None) -> SimpleNamespace:
    return SimpleNamespace(
        circuit=CircuitSpec.from_dict(CIRCUIT_PAYLOAD),
        presentation=presentation or PresentationSpec.from_dict(PRESENTATION_PAYLOAD),
        book=book,
        budget=SimpleNamespace(
            high_fanout=3,
            power_flag_prefix="PWR-",
            gnd_flag="PWR-GND",
            gnd_cluster_radius=0.0,
        ),
        ground_domains=ground_domains,
    )


def _arms(count: int) -> list[SeriesBranch]:
    return [
        SeriesBranch(
            id=f"arm{index}", from_net="VBUS_LOCAL", to_net="GND",
            parts=("U1", "C1"), middle_net=f"MID{index}",
        )
        for index in range(count)
    ]


# ------------------------------------------------------------------ 别名


def test_the_own_name_wins_over_the_alias():
    """书名里同时有原名与别名时，绝不换名。"""
    book = _book("PWR-VBUS_LOCAL", "PWR-+VBUS_LOCAL")
    ctx = _context(book)
    assert dc._flag_ref(ctx, "VBUS_LOCAL", "power") == "PWR-VBUS_LOCAL"
    profile, ref = dc._flag_plan(ctx, "VBUS_LOCAL", "power")
    assert ref == "PWR-VBUS_LOCAL"
    assert profile is book["PWR-VBUS_LOCAL"]
    assert not dc._missing_flag_symbol(ctx, "VBUS_LOCAL")


def test_the_alias_answers_only_when_the_own_name_is_absent():
    """原名缺席、别名在场：判定、缺失检查和落笔是同一个真实 ref。"""
    book = _book("PWR-+VBUS_LOCAL")
    ctx = _context(book)
    assert dc._flag_ref(ctx, "VBUS_LOCAL", "power") == "PWR-+VBUS_LOCAL"
    profile, ref = dc._flag_plan(ctx, "VBUS_LOCAL", "power")
    assert ref == "PWR-+VBUS_LOCAL"
    assert profile is book["PWR-+VBUS_LOCAL"]
    net = ctx.circuit.net("VBUS_LOCAL")
    assert dc._net_flag_profile(ctx, net) is book["PWR-+VBUS_LOCAL"]
    assert not dc._missing_flag_symbol(ctx, "VBUS_LOCAL")


def test_a_rail_with_neither_name_stays_missing():
    book = _book("PWR-GND")
    ctx = _context(book)
    assert dc._flag_ref(ctx, "VBUS_LOCAL", "power") == "PWR-VBUS_LOCAL"
    assert dc._missing_flag_symbol(ctx, "VBUS_LOCAL")


def test_a_ground_is_never_aliased():
    book = _book("PWR-GND", "PWR-+GND")
    ctx = _context(book)
    assert dc._flag_ref(ctx, "GND", "gnd") == "PWR-GND"
    profile, ref = dc._flag_plan(ctx, "GND", "gnd")
    assert ref == "PWR-GND"
    assert profile is book["PWR-GND"]


def test_a_net_id_that_already_carries_the_plus_keeps_its_own_name():
    """``+5V`` 的原名已经是 ``PWR-+5V``，不再拼第二个 ``+``。"""
    book = _book("PWR-+5V")
    ctx = _context(book)
    circuit = CircuitSpec.from_dict({
        **CIRCUIT_PAYLOAD,
        "nets": [
            {"id": "+5V", "class": "power", "members": ["U1.1", "C1.1"],
             "provenance": "ai_asserted"},
            {"id": "GND", "class": "gnd", "members": ["U1.4", "C1.2"],
             "provenance": "ai_asserted"},
        ],
    })
    ctx.circuit = circuit
    assert dc._flag_ref(ctx, "+5V", "power") == "PWR-+5V"
    assert dc._flag_plan(ctx, "+5V", "power")[1] == "PWR-+5V"


# ------------------------------------------------------- 模块本地电源旗


def test_a_multi_arm_page_wires_a_module_local_rail():
    presentation = replace(
        PresentationSpec.from_dict(PRESENTATION_PAYLOAD),
        series_branches=_arms(2),
    )
    ctx = _context(_book("PWR-+VBUS_LOCAL"), presentation)
    style, reason = dc._expression_style(ctx, "VBUS_LOCAL", "power", 4, set())
    assert style == "wire", reason
    assert "548D3" in reason


def test_one_arm_keeps_the_per_pin_answer():
    presentation = replace(
        PresentationSpec.from_dict(PRESENTATION_PAYLOAD),
        series_branches=_arms(1),
    )
    ctx = _context(_book("PWR-+VBUS_LOCAL"), presentation)
    style, reason = dc._expression_style(ctx, "VBUS_LOCAL", "power", 4, set())
    assert style == "flag", reason
    assert "548D3" not in reason


def test_an_undeclared_page_keeps_the_per_pin_answer():
    ctx = _context(_book("PWR-+VBUS_LOCAL"))
    style, reason = dc._expression_style(ctx, "VBUS_LOCAL", "power", 4, set())
    assert style == "flag", reason
    assert "548D3" not in reason


def test_a_rail_that_reaches_past_the_module_keeps_the_per_pin_answer():
    presentation = replace(
        PresentationSpec.from_dict(PRESENTATION_PAYLOAD),
        series_branches=_arms(2),
    )
    # 把 C1 拆到第二个声明模块：这条 rail 越过了模块边界。
    split = replace(
        presentation,
        modules=[
            replace(presentation.modules[0], id="m1", parts=["U1"]),
            replace(presentation.modules[0], id="m2", parts=["C1"]),
        ],
    )
    ctx = _context(_book("PWR-+VBUS_LOCAL"), split)
    style, reason = dc._expression_style(ctx, "VBUS_LOCAL", "power", 4, set())
    assert style == "flag", reason
    assert "548D3" not in reason


def test_a_ground_keeps_its_ground_reason_on_a_multi_arm_page():
    presentation = replace(
        PresentationSpec.from_dict(PRESENTATION_PAYLOAD),
        series_branches=_arms(2),
    )
    ctx = _context(_book("PWR-GND"), presentation)
    style, reason = dc._expression_style(ctx, "GND", "gnd", 2, set())
    assert style == "wire", reason
    assert "a ground is a **rail**" in reason
    assert "548D3" not in reason
