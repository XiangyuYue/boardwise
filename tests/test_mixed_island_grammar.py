"""mixed-island：ic-periphery 的"通用岛"入口——核心可以没有已声明的电源/地。

098 的 `ic-periphery` 把"核心必须落在一条 power 和一条 gnd 上"写成硬前提，
于是智能门锁 V4 P1 的七岛自动编译在 HMI（J5 无 power/gnd）与蜂鸣（Q1 无 power）
两岛上零候选。本批不另造 builder/router/flagger：`mixed-island` 只把同一条
`IcPeripheryGrammar` 的判定复用成两个**策略开关**的另一种组合。

策略（默认保持原行为，一个字节不动）：

* `require_core_supply=True` / `allow_unowned_branches=False` — `ic-periphery`；
* `False` / `True` — `mixed-island`：缺 rail/gnd 不拒绝、不虚构；不 touch core
  的两端支路保持 unbound（编译器的 free shelf），不得给它们发明角色。

测试先写的 RED 顺序与判据（每条钉一个因果项）：

1. connector 核心没有 power/gnd → mixed 可 bind，rail/gnd 角色与两条义务按缺省省略；
2. 有 stray 的 mixed 可 bind，且 stray 不获任何角色；
3. 同一输入原 `ic-periphery` 仍拒绝 —— 默认策略没有被这批改掉；
4. 有真实 rail/gnd 时 mixed 仍生成对应角色/义务；
5. 小型 compile 集成：mixed 字面量走完 `drawcompiler.compile` + `readability.check`
   （checker 自己会重绑语法，所以它证明的是"语法名整条链可用"，不是只 bind 一次）。
"""

from __future__ import annotations

import test_053b_drawcompiler as b053

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import GRAMMARS, PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawcompiler as dc
from boardwise.engines import grammar
from boardwise.engines import readability
from boardwise.engines.grammar import ic_periphery
from boardwise.engines.grammar.base import (
    FAILURE_CIRCUIT_INVALID,
    FAILURE_FACTS_MISSING,
    OWNED_BRANCH,
    UNIFORM_GND,
)

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


def sheet(parts: tuple[str, ...], core: str = "J1",
          grammar_ref: str = MIXED, **overrides) -> PresentationSpec:
    payload: dict = {
        "grammarRef": grammar_ref,
        "modules": [{
            "id": "island", "parts": list(parts), "role": "the island",
            "grammarRef": grammar_ref, "core": core,
        }],
    }
    payload.update(overrides)
    return PresentationSpec.from_dict(payload)


#: 没有 power/gnd 的岛：J1 的四脚各自成网，R1 跨 J1.1↔J1.2（bridge）。
def no_supply_group():
    return (
        circuit(
            [part("J1", "CONN-4P"), part("R1", "R0402", "10k")],
            [
                net("A", "signal", ["J1.1", "R1.1"]),
                net("B", "signal", ["J1.2", "R1.2"]),
                net("C", "signal", ["J1.3"]),
                net("D", "signal", ["J1.4"]),
            ],
        ),
        sheet(("J1", "R1")),
    )


#: 同一个无电源岛，再加一条完全不 touch J1 的两端支路 R2。
def stray_group():
    circuit_spec, presentation_spec = no_supply_group()
    payload = circuit_spec.to_jsonable()
    payload["parts"].append(part("R2", "R0402", "1k"))
    payload["nets"].extend([
        net("X", "signal", ["R2.1"]),
        net("Y", "signal", ["R2.2"]),
    ])
    return (
        CircuitSpec.from_dict(payload),
        sheet(("J1", "R1", "R2")),
    )


#: 有真实 rail/gnd 的岛：C1 从 J1.1 回 VCC，C2 从 J1.2 回 GND。
def supplied_group():
    return (
        circuit(
            [
                part("J1", "CONN-4P"), part("C1", "C0402", "100nF"),
                part("C2", "C0402", "100nF"),
            ],
            [
                net(RAIL, "power", ["J1.3", "C1.2"]),
                net(GND, "gnd", ["J1.4", "C2.2"]),
                net("A", "signal", ["J1.1", "C1.1"]),
                net("B", "signal", ["J1.2", "C2.1"]),
            ],
        ),
        sheet(("J1", "C1", "C2")),
    )


def bind_mixed(circuit_spec, presentation_spec):
    return grammar.bind(
        circuit_spec, presentation_spec, library(), grammar_name=MIXED,
    )


def bind_ic(circuit_spec, presentation_spec):
    return grammar.bind(
        circuit_spec, presentation_spec, library(), grammar_name=ic_periphery.NAME,
    )


def roles(result) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for binding in result.bindings:
        out.setdefault(binding.role, []).append(binding.part_id)
    return out


def obligation_kinds(result) -> list[str]:
    return [item.kind for item in result.obligations]


# -------------------------------------------------------------------- 注册面


def test_mixed_island_is_registered_on_every_face_a_grammar_must_be():
    assert MIXED in GRAMMARS
    assert grammar.NAMES[-1] == MIXED
    assert grammar.NAMES == tuple(grammar._CLASSES)
    assert grammar.NAMES == tuple(grammar.ROLES_BY_GRAMMAR)
    assert grammar.NAMES == GRAMMARS
    assert grammar.ROLES_BY_GRAMMAR[MIXED] == ic_periphery.ROLES

    from boardwise.engines.grammar import mixed_island

    instance = grammar.grammar_for(MIXED, library())
    assert isinstance(instance, mixed_island.MixedIslandGrammar)
    assert isinstance(instance, ic_periphery.IcPeripheryGrammar)
    assert instance.name == MIXED
    assert instance.require_core_supply is False
    assert instance.allow_unowned_branches is True


def test_ic_periphery_keeps_its_strict_policy_by_default():
    instance = grammar.grammar_for(ic_periphery.NAME)
    assert instance.require_core_supply is True
    assert instance.allow_unowned_branches is False


# ------------------------------------------------------- a) 无 power/gnd 的岛


def test_a_mixed_island_binds_a_core_without_a_stated_supply():
    result = bind_mixed(*no_supply_group())
    assert result.ok, [item.render() for item in result.failures]

    # 核心仍按声明选择，bridge 仍是核心自己两脚之间的两端件。
    assert result.parts_of("core") == ("J1",)
    assert result.parts_of("bridge") == ("R1",)

    # 缺的 rail/gnd 不拒绝、不虚构：没有角色，没有两条以网为名的义务。
    assert result.net_of("rail") == ""
    assert result.net_of("gnd") == ""
    assert "rail" not in roles(result)
    assert "gnd" not in roles(result)
    assert OWNED_BRANCH not in obligation_kinds(result)
    assert UNIFORM_GND not in obligation_kinds(result)

    # core evidence 不硬说"two supplies"。
    core_evidence = result.bindings_for("core")[0].evidence
    assert "two supplies" not in core_evidence
    assert "no supply or ground" in core_evidence


# ------------------------------------------------------ b) stray 保持 unbound


def test_b_a_stray_is_left_unbound_and_earns_no_role():
    result = bind_mixed(*stray_group())
    assert result.ok, [item.render() for item in result.failures]

    bound = {binding.part_id for binding in result.bindings}
    assert "R2" not in bound, "a stray must stay on the compiler's free shelf"
    for binding in result.bindings:
        assert binding.part_id != "R2"
    # 没有为它发明任何新角色：全部角色仍来自 ic-periphery 的 ROLES。
    assert set(roles(result)) <= set(ic_periphery.ROLES)


# ------------------------------------------- c) 原 ic-periphery 的默认仍拒绝


def test_c_the_original_ic_periphery_still_refuses_the_same_input():
    circuit_spec, presentation_spec = no_supply_group()
    result = bind_ic(circuit_spec, presentation_spec)
    assert not result.ok
    assert {item.category for item in result.failures} == {
        FAILURE_FACTS_MISSING
    }
    detail = " ".join(item.detail for item in result.failures)
    assert "power" in detail and "gnd" in detail

    stray_circuit, stray_sheet = stray_group()
    stray_result = bind_ic(stray_circuit, stray_sheet)
    assert not stray_result.ok
    # The no-supply island is refused at the supply facts first (the stray
    # refusal is exercised with a supplied island in c2, where supply is not
    # the missing fact).
    assert stray_result.failures[0].category == FAILURE_FACTS_MISSING
    assert "power" in stray_result.failures[0].detail


def test_c2_the_original_ic_periphery_still_refuses_a_stray_of_a_supplied_island():
    """有真实供电时原语法的拒绝仍是 stray 而非 supply，证明两条默认都原样。"""
    circuit_spec, presentation_spec = supplied_group()
    payload = circuit_spec.to_jsonable()
    payload["parts"].append(part("R9", "R0402", "1k"))
    payload["nets"].extend([
        net("P", "signal", ["R9.1"]),
        net("Q", "signal", ["R9.2"]),
    ])
    stray_circuit = CircuitSpec.from_dict(payload)
    stray_sheet = sheet(("J1", "C1", "C2", "R9"))

    result = bind_ic(stray_circuit, stray_sheet)
    assert not result.ok
    assert result.failures[0].category == FAILURE_CIRCUIT_INVALID
    assert "R9" in result.failures[0].detail

    assert bind_mixed(stray_circuit, stray_sheet).ok


# ------------------------------------------------- d) 真实 rail/gnd 的角色义务


def test_d_a_mixed_island_with_real_supplies_still_binds_them():
    result = bind_mixed(*supplied_group())
    assert result.ok, [item.render() for item in result.failures]

    assert result.net_of("rail") == RAIL
    assert result.net_of("gnd") == GND
    assert set(result.parts_of("shunt")) == {"C1", "C2"}

    owned = result.obligation_for(OWNED_BRANCH)
    uniform = result.obligation_for(UNIFORM_GND)
    assert owned is not None and owned.nets == (RAIL,)
    assert uniform is not None and uniform.nets == (GND,)

    core_evidence = result.bindings_for("core")[0].evidence
    assert "two supplies" in core_evidence


# --------------------------------------------------- e) 完整 compile + checker


def test_e_the_mixed_name_reaches_the_whole_compile_and_checker_chain():
    circuit_spec, presentation_spec = no_supply_group()
    assert presentation_spec.grammar_ref == MIXED

    result = dc.compile(
        circuit_spec, presentation_spec, library(), dc.CompileBudget(),
    )
    assert result.grammar is not None and result.grammar.ok
    assert result.ok, result.render_failures()
    assert result.candidates, result.render_failures()

    plan = result.candidates[0]
    checked = readability.check(
        plan, circuit_spec, presentation_spec, library(),
        page_box=None, keepouts=(),
    )
    assert checked.hard_violations == [], [
        item.render() for item in checked.hard_violations
    ]
