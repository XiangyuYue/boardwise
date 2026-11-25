"""mixed-island：`freeParts` —— 工程师声明的"本岛自由支路"。

真实智能门锁 MCU 岛的 serviceGroup 联合席位 + `stubLaneReserve` 仍然零候选：
若干去耦/复位/BOOT/晶体负载的两端支路被 grammar 绑成 shunt，于是 `NEAR<=300`
把它们拉向核心；本岛里它们与核心之间没有可画的近关系。把它们从本岛删掉是错的
（电路上它们就在本岛），全局放宽 `NEAR_LIMIT` 也是错的（其它岛靠它）。

本批只加一条**显式合同**：`modules[].freeParts` —— 工程师逐件声明"这些两端支路
属于本岛，但不绑定核心角色"。

合同（本文件钉住的全部内容）：

1. 可选字段，缺省 `[]`，**序列化时省略**：不声明的文档逐字节不变（digest 不动）；
2. 元素必须是**本模块自己 `parts` 里的**部件 id，重复/非字符串/别人家的部件在
   解析期按既有 schema 风格拒绝；
3. 只有 `mixed-island` 读它（`IcPeripheryGrammar.free_parts()` 默认空）。被声明的
   部件不获 `bridge`/`shunt`/`stray` 角色，也不生成由这些角色派生的 `NEAR`/
   `ADJACENT` 约束；其它支路仍按原规则绑定并保留 `NEAR`；
4. 它**不是删除器件**：CircuitSpec/页面仍放置并连接它们（小型 compile 集成钉住）；
5. 编译期发现声明的件不是两端件（例如把核心写进 freeParts）→ `circuit-invalid`，
   不静默忽略；
6. `pagecompiler._module_view` 原样携带它，否则分页编译会丢掉这条声明。

RED 顺序：先写本文件（未实现时解析即拒绝 `freeParts`），再实现，再绿。
"""

from __future__ import annotations

import pytest

import test_053b_drawcompiler as b053

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import (
    GRAMMARS,
    PresentationSpec,
    PresentationSpecError,
)
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawcompiler as dc
from boardwise.engines import grammar, pagecompiler
from boardwise.engines.grammar import ic_periphery
from boardwise.engines.grammar.base import FAILURE_CIRCUIT_INVALID

PROV = "verified_recipe"
MIXED = "mixed-island"
RAIL = "VCC"
GND = "GND"


# ------------------------------------------------------------------ 手写夹具


def connector(ref: str = "CONN-4P") -> SymbolProfile:
    """四脚连接器：脚全朝左。它不是"电源"，只是一个多脚实体。"""
    return SymbolProfile(
        symbol_ref=ref, title="Connector", body=(-40.0, -50.0, 40.0, 50.0),
        pins=b053._pins((
            ("1", (-60.0, -30.0), "left"),
            ("2", (-60.0, -10.0), "left"),
            ("3", (-60.0, 10.0), "left"),
            ("4", (-60.0, 30.0), "left"),
        )),
    )


def library(**overrides: SymbolProfile) -> dict[str, SymbolProfile]:
    book = b053.library()
    book.update({connector().symbol_ref: connector()})
    book.update(overrides)
    return book


def part(part_id: str, symbol: str, value: str = "") -> dict:
    return {"id": part_id, "symbolRef": symbol, "value": value,
            "provenance": PROV}


def net(net_id: str, cls: str, members: list[str]) -> dict:
    return {"id": net_id, "class": cls, "members": list(members),
            "provenance": PROV}


def circuit(parts: list[dict], nets: list[dict]) -> CircuitSpec:
    return CircuitSpec.from_dict({"parts": parts, "nets": nets})


def sheet(
    parts: tuple[str, ...],
    core: str = "J1",
    grammar_ref: str = MIXED,
    free_parts: list[str] | None = None,
    **overrides,
) -> PresentationSpec:
    module: dict = {
        "id": "island", "parts": list(parts), "role": "the island",
        "grammarRef": grammar_ref, "core": core,
    }
    # Only stated when the caller states it: the default is "no key at all",
    # which is exactly the byte shape every pre-existing spec has.
    if free_parts is not None:
        module["freeParts"] = list(free_parts)
    payload: dict = {"grammarRef": grammar_ref, "modules": [module]}
    payload.update(overrides)
    return PresentationSpec.from_dict(payload)


#: 两个同形 shunt：C9 从 J1.1 回 GND，C10 从 J1.2 回 GND。核心 J1 在这条 GND
#: 上（J1.4），所以 GND 是它绑定的 return；A/B 是 core pin net。声明 C9 自由后
#: 只有 C10 应仍是 shunt + NEAR。
def two_shunts(*, free_parts: list[str] | None) -> tuple[CircuitSpec, PresentationSpec]:
    circuit_spec = circuit(
        [
            part("J1", "CONN-4P"), part("J2", "CONN-4P"),
            part("C9", "C0402", "100nF"),
            part("C10", "C0402", "1uF"),
        ],
        [
            net("A", "signal", ["J1.1", "C9.1"]),
            net("B", "signal", ["J1.2", "C10.1"]),
            net("C", "signal", ["J1.3", "J2.1"]),
            net(GND, "gnd", ["J1.4", "C9.2", "C10.2"]),
        ],
    )
    return circuit_spec, sheet(("J1", "C9", "C10"), free_parts=free_parts)


#: 有真实 rail/gnd 的岛（ic-periphery 原读法使用）：C1 从 J1.1 回 GND，C2 从
#: J1.2 回 VCC。
def supplied_group(*, free_parts: list[str] | None = None,
                   grammar_ref: str = MIXED) -> tuple[CircuitSpec, PresentationSpec]:
    circuit_spec = circuit(
        [
            part("J1", "CONN-4P"), part("C1", "C0402", "100nF"),
            part("C2", "C0402", "100nF"),
        ],
        [
            net(RAIL, "power", ["J1.3", "C2.2"]),
            net(GND, "gnd", ["J1.4", "C1.2"]),
            net("A", "signal", ["J1.1", "C1.1"]),
            net("B", "signal", ["J1.2", "C2.1"]),
        ],
    )
    return circuit_spec, sheet(
        ("J1", "C1", "C2"), grammar_ref=grammar_ref, free_parts=free_parts,
    )


def bind(circuit_spec, presentation_spec, grammar_name: str = MIXED):
    return grammar.bind(
        circuit_spec, presentation_spec, library(), grammar_name=grammar_name,
    )


def roles(result) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for binding in result.bindings:
        out.setdefault(binding.role, []).append(binding.part_id)
    return out


def constraints_for(result, part_id: str):
    return [
        item for item in result.constraints
        if item.subject == part_id or item.object == part_id
    ]


# ------------------------------------------------------------------- a) 合同


def test_a_a_declared_free_part_earns_no_role_and_no_near_constraint():
    circuit_spec, presentation_spec = two_shunts(free_parts=["C9"])
    assert presentation_spec.modules[0].free_parts == ["C9"]

    result = bind(circuit_spec, presentation_spec)
    assert result.ok, [item.render() for item in result.failures]

    # The core and the other branch are bound exactly as before.
    assert result.parts_of("core") == ("J1",)
    assert result.parts_of("shunt") == ("C10",)
    assert "C9" not in {binding.part_id for binding in result.bindings}
    assert "C9" not in roles(result).get("bridge", [])

    # No constraint derived from a role C9 never got — including `near`.
    assert constraints_for(result, "C9") == [], (
        "a free part must not be the subject or the object of any constraint: "
        "NEAR is exactly the constraint that made the real MCU island refuse"
    )
    assert [item.kind for item in constraints_for(result, "C10") if item.kind == "near"], (
        "the undeclared C10 keeps its near constraint"
    )


# ------------------------------------------------------- b) schema / 编译期拒绝


def test_b1_an_undeclared_part_of_this_module_is_a_schema_error():
    with pytest.raises(PresentationSpecError) as caught:
        sheet(("J1", "C10"), free_parts=["C9"])
    text = str(caught.value)
    assert "freeParts" in text and "C9" in text


def test_b2_a_part_of_another_module_is_a_schema_error():
    payload = {
        "modules": [
            {"id": "a", "parts": ["J1", "C10"], "role": "a", "core": "J1",
             "freeParts": ["C1"]},
            {"id": "b", "parts": ["C1"], "role": "b"},
        ],
    }
    with pytest.raises(PresentationSpecError) as caught:
        PresentationSpec.from_dict(payload)
    assert "freeParts" in str(caught.value)


def test_b3_a_repeated_or_non_string_element_is_refused():
    with pytest.raises(PresentationSpecError) as caught:
        sheet(("J1", "C9", "C10"), free_parts=["C9", "C9"])
    assert "C9" in str(caught.value)

    with pytest.raises(PresentationSpecError) as caught:
        PresentationSpec.from_dict({
            "modules": [{"id": "island", "parts": ["J1", "C9"], "role": "x",
                         "core": "J1", "freeParts": [1]}],
        })
    assert "freeParts" in str(caught.value)


def test_b4_a_non_two_terminal_free_part_is_circuit_invalid_not_ignored():
    circuit_spec, presentation_spec = two_shunts(free_parts=None)
    declared = sheet(("J1", "J2", "C9", "C10"), free_parts=["J2"])
    result = bind(circuit_spec, declared)
    assert not result.ok
    assert len(result.failures) == 1
    failure = result.failures[0]
    assert failure.category == FAILURE_CIRCUIT_INVALID
    assert failure.subject == "J2"
    assert "freeParts" in failure.detail and "two-terminal" in failure.detail


# ---------------------------------------- c) ic-periphery 的默认读法一个字节不动


def test_c1_ic_periphery_without_free_parts_is_unchanged():
    circuit_spec, presentation_spec = supplied_group(grammar_ref=ic_periphery.NAME)
    result = bind(circuit_spec, presentation_spec, ic_periphery.NAME)
    assert result.ok, [item.render() for item in result.failures]
    assert result.net_of("rail") == RAIL
    assert result.net_of("gnd") == GND
    assert set(result.parts_of("shunt")) == {"C1", "C2"}
    for part_id in ("C1", "C2"):
        assert [item for item in constraints_for(result, part_id)
                if item.kind == "near"], part_id


def test_c2_ic_periphery_ignores_the_optional_key_byte_for_byte():
    circuit_spec, without = supplied_group(grammar_ref=ic_periphery.NAME)
    _, declared = supplied_group(
        grammar_ref=ic_periphery.NAME, free_parts=["C1"],
    )
    plain = bind(circuit_spec, without, ic_periphery.NAME)
    with_free = bind(circuit_spec, declared, ic_periphery.NAME)
    assert plain.to_jsonable() == with_free.to_jsonable(), (
        "`freeParts` is mixed-island's reading; ic-periphery must keep its "
        "binding byte for byte"
    )


# ------------------------------------------------------------ d) 序列化与视图


def test_d1_the_default_is_omitted_and_a_declaration_round_trips():
    _, plain = two_shunts(free_parts=None)
    body = plain.to_jsonable()["modules"][0]
    assert "freeParts" not in body
    assert plain.modules[0].free_parts == []
    assert PresentationSpec.from_dict(plain.to_jsonable()).sha256() == plain.sha256()

    _, declared = two_shunts(free_parts=["C9"])
    body = declared.to_jsonable()["modules"][0]
    assert body["freeParts"] == ["C9"]
    again = PresentationSpec.from_dict(declared.to_jsonable())
    assert again.to_jsonable() == declared.to_jsonable()
    assert again.sha256() == declared.sha256()
    # Only a stated declaration moves the digest.
    assert declared.sha256() != plain.sha256()


def test_d2_the_module_view_carries_free_parts():
    circuit_spec, declared = two_shunts(free_parts=["C9"])
    module = declared.modules[0]
    _, sub = pagecompiler._module_view(circuit_spec, declared, module)
    assert sub.modules[0].free_parts == ["C9"]

    _, plain = two_shunts(free_parts=None)
    _, sub_plain = pagecompiler._module_view(circuit_spec, plain, plain.modules[0])
    assert sub_plain.modules[0].free_parts == []


# ------------------------------------------------- e) 自由件仍被放置并连线

def _announced(plan, point, net_id: str) -> bool:
    """Is this pin on a conductor, or exactly at a label/flag anchor of its net?"""
    if b053.on_a_wire(plan, point):
        return True
    return any(
        abs(x - point[0]) < 1e-6 and abs(y - point[1]) < 1e-6
        for x, y in b053.anchors_with(plan, net_id)
    )


def test_e_a_free_part_is_still_placed_and_connected():
    circuit_spec, presentation_spec = two_shunts(free_parts=["C9"])
    result = dc.compile(
        circuit_spec, presentation_spec, library(), dc.CompileBudget(),
    )
    assert result.grammar is not None and result.grammar.ok
    assert result.ok, result.render_failures()
    assert result.candidates, result.render_failures()

    plan = result.candidates[0]
    for part_id in ("C9", "C10"):
        assert plan.part(part_id) is not None, (
            f"{part_id} is a part of this island and must still be placed — "
            "freeParts is not a delete"
        )
    for token, net_id in (("1", "A"), ("2", GND)):
        point = b053.pin_point(plan, f"C9.{token}")
        assert point is not None
        assert _announced(plan, point, net_id), (
            f"C9.{token} ({net_id}) is placed but nothing states its connection"
        )
    assert set(b053.plan_net_names(plan)) >= {"A", GND}


def test_mixed_island_free_parts_name_is_registered():
    assert MIXED in GRAMMARS
    from boardwise.engines.grammar import mixed_island

    instance = grammar.grammar_for(MIXED, library())
    assert isinstance(instance, mixed_island.MixedIslandGrammar)
    # Default and read: the parent hook states no free parts, mixed reads the scope module.
    assert grammar.grammar_for(ic_periphery.NAME).free_parts(
        two_shunts(free_parts=["C9"])[1], "island"
    ) == ()
    assert instance.free_parts(two_shunts(free_parts=["C9"])[1], "island") == ("C9",)
