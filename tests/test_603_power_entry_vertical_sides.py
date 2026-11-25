"""603：`power_entry` 的 top/bottom 声明必须真的落到几何上。

570-C2-N2 实测：`PowerEntryGrammar._result` 只把 `sidePreferences.input=="right"`
映射成 `right-of`，`top` / `bottom` 静默折回 `left-of`，而理由串照样打印
`sidePreferences.input=top` —— 声明与几何不符，且出处是伪造的。

方向语义按 603 任务书裁定（`RelativeConstraint` 的 subject 是 entry）：
入口声明在上方 = entry 在 shunt 上方，所以 `top→above`、`bottom→below`，
与 `flyback._side_kind` / `ldo._side_kind` 的四值表逐项相同。570-C2 报告
表格里那一处 `input=top → below` 与其 §3 FIX 自相矛盾，本文件按 §3 与
flyback 的同义表钉住。

最小输入复用 `outputs/hole570/c2/probes/probe_c2.py` 的 power_entry 构造
（只抄构造字面量，不执行探针、不改原文件）：CN1 是入口（VIN 的
openInterfaces 声明 direction=input），C1 是跨 VIN/GND 的 shunt，F1 是串在
VIN→VIN2 的两脚件，U1 是 IC。

分工一句话一条：四个合法值各自钉住正确的 kind（不是"四个值互不相同"），
未声明的默认仍是 `left-of`，非法值的既有回退不变，除 side kind 外绑定与
约束编号不变。
"""

from __future__ import annotations

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.engines.grammar import power_entry as pe
from boardwise.engines.grammar.base import (
    ABOVE,
    BELOW,
    LEFT_OF,
    NEAR,
    RIGHT_OF,
    SAME_ROW,
)

PROV = "engineer_confirmed"


# --------------------------------------------------------------- 最小输入


def pe_pres(sides=None):
    return PresentationSpec.from_dict({
        "kind": "boardwise-presentation-spec", "specVersion": 1,
        "grammarRef": "power-entry",
        "sidePreferences": {"input": "left", "gnd": "bottom"}
        if sides is None else sides,
        "portRoles": {"VIN": "input"},
    })


def pe_circuit(interfaces, extra_shunt=False):
    parts = [
        {"id": "CN1", "symbolRef": "CN", "provenance": PROV},
        {"id": "F1", "symbolRef": "F", "provenance": PROV},
        {"id": "C1", "symbolRef": "C", "provenance": PROV},
        {"id": "U1", "symbolRef": "IC", "provenance": PROV},
    ]
    rail_members = ["CN1.1", "F1.1", "C1.1"]
    gnd_members = ["CN1.2", "C1.2", "U1.4"]
    if extra_shunt:
        parts.append({"id": "C2", "symbolRef": "C", "provenance": PROV})
        rail_members.append("C2.1")
        gnd_members.append("C2.2")
    return CircuitSpec.from_dict({
        "kind": "boardwise-circuit-spec", "specVersion": 1,
        "parts": parts,
        "nets": [
            {"id": "VIN", "class": "power",
             "members": rail_members, "provenance": PROV},
            {"id": "VIN2", "class": "power",
             "members": ["F1.2", "U1.8"], "provenance": PROV},
            {"id": "GND", "class": "gnd",
             "members": gnd_members, "provenance": PROV},
        ],
        "openInterfaces": interfaces,
    })


def pe_entry():
    return [{"net": "VIN", "role": "rail", "part": "CN1",
             "direction": "input", "provenance": PROV}]


def pe_bind(circuit, presentation):
    return pe.PowerEntryGrammar({}).bind(circuit, presentation)


def bind_one(sides, extra_shunt=False):
    result = pe_bind(pe_circuit(pe_entry(), extra_shunt=extra_shunt),
                     pe_pres(sides))
    assert result.ok, [f.detail for f in result.failures]
    return result


def side_constraints(result, subject="CN1", obj="C1"):
    """`subject→object` 上除 same-row 之外的成对约束（今天恰好一条）。"""
    found = [
        c for c in result.constraints
        if c.subject == subject and c.object == obj and c.kind != SAME_ROW
    ]
    assert len(found) == 1, [(c.subject, c.object, c.kind)
                             for c in result.constraints]
    return found[0]


#: 四个合法声明各自的 kind —— 与 `flyback._side_kind` / `ldo._side_kind`
#: 的同义表逐项相同（603 裁定：subject 是 entry，声明在上方 = entry 在上）。
EXPECTED = {
    "left": LEFT_OF,
    "right": RIGHT_OF,
    "top": ABOVE,
    "bottom": BELOW,
}


# --------------------------------------------------------------- 四个合法值


@pytest.mark.parametrize("side", sorted(EXPECTED))
def test_declared_side_reaches_the_geometry(side):
    result = bind_one({"input": side, "gnd": "bottom"})
    constraint = side_constraints(result)
    assert constraint.kind == EXPECTED[side], (
        f"sidePreferences.input={side} bound {constraint.kind!r}, "
        f"expected {EXPECTED[side]!r}"
    )
    # 声明与 kind 必须同现：理由串引用声明，几何就必须是那个方向。
    assert f"sidePreferences.input={side}" in constraint.reason


def test_top_is_above_the_entry_not_below():
    """方向不能整体对调：top 是 entry 在上方（570-C2 报告表格那一处写反）。"""
    assert side_constraints(bind_one({"input": "top"})).kind == ABOVE
    assert side_constraints(bind_one({"input": "bottom"})).kind == BELOW


def test_horizontal_reason_does_not_name_a_vertical_kind():
    """理由串仍只说声明值，不额外编造别的方向词。"""
    for side in ("top", "bottom"):
        constraint = side_constraints(bind_one({"input": side}))
        assert "left-of" not in constraint.reason
        assert "right-of" not in constraint.reason


# --------------------------------------------------------------- negative controls


def test_undeclared_side_keeps_the_left_default():
    result = bind_one({"gnd": "bottom"})
    assert side_constraints(result).kind == LEFT_OF


def test_illegal_side_keeps_the_left_fallback():
    """解析层拒绝非法值；直接构造的 spec 仍走既有回退（`in_side not in SIDES`）。"""
    spec = PresentationSpec(
        port_roles={"VIN": "input"},
        grammar_ref="power-entry",
        side_preferences={"input": "diagonal"},
    )
    result = pe_bind(pe_circuit(pe_entry()), spec)
    assert result.ok, [f.detail for f in result.failures]
    assert side_constraints(result).kind == LEFT_OF


# --------------------------------------------------------------- 除 kind 外不变


def test_binding_shape_is_the_same_for_every_side():
    baseline = bind_one({"input": "left"})
    base_roles = [(b.role, b.part_id) for b in baseline.bindings]
    base_other = [
        (c.subject, c.object, c.kind) for c in baseline.constraints
        if c.kind != LEFT_OF and c.kind not in (RIGHT_OF, ABOVE, BELOW)
    ]
    for side in EXPECTED:
        result = bind_one({"input": side})
        assert [(b.role, b.part_id) for b in result.bindings] == base_roles
        other = [
            (c.subject, c.object, c.kind) for c in result.constraints
            if c.kind != LEFT_OF and c.kind not in (RIGHT_OF, ABOVE, BELOW)
        ]
        assert other == base_other
        assert len(result.constraints) == len(baseline.constraints)


def test_shunt_order_is_the_designator_order_for_every_side():
    for side in EXPECTED:
        result = bind_one({"input": side}, extra_shunt=True)
        assert [b.part_id for b in result.bindings if b.role == "shunt"] == [
            "C1", "C2",
        ]
        assert sorted(
            c.kind for c in result.constraints
            if c.subject == "CN1" and c.kind != SAME_ROW
        ) == sorted([EXPECTED[side], EXPECTED[side]])
        assert [
            c.kind for c in result.constraints if c.kind == NEAR
        ] == [NEAR, NEAR]
