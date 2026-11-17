"""548D3D-F1：同一模块内**互不重叠的独立链族**（`voltage-divider`）。

实测缺口：`evidence/548D/full-page/semantic-split/` 的 LED 岛用 `voltage-divider`
可以电气闭合，但 `_result` 只消费 `chains[0]`——第二条同类支路（R3/D2）没有绑定，
回落到通用布局后与 R2/D1 姿态不一致（一竖一横、一有抽头标签一裸线），按
`boardwise-draw` §3/§5 判废。

这一批钉住四件事：

1. **独立链族都绑**：每条链都有自己的 upper/lower/tap/in/gnd 绑定、几何约束和
   DIRECT_WIRE/VISIBLE_TAP 义务；两条同类链的关系种类与方向一致（同向、同阅读规则）；
2. **不是独立链的读法不得重复绑定**：共用一条臂、或共用抽头（臂不同）的读法都
   只能算同一条链；跨模块的两条链不同族；
3. **缺省页逐字节不变**：`serviceLayout` 存在 **且** `labelPolicy.stubMin>0`
   才启用多链（548D3D-F1A：`textPlacement: native-attr` 不再是条件——它曾把整页
   成对读法对无关岛打开），且只对**信号顶端**启用；电源分压仍只取第一条链；
4. **共享 in/gnd 去重**：两条链回同一个地，`gnd` 角色只绑一次，不重复两条。

CircuitSpec / PresentationSpec 全部手写字面量（与 053b 一致：这一批判的是语法，
夹具会把解析器的行为绑进来）。
"""

from __future__ import annotations

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.engines.grammar import voltage_divider
from boardwise.engines.grammar.base import (
    ABOVE,
    DIRECT_WIRE,
    HORIZONTAL_TAP,
    LEFT_OF,
    OWNED_BRANCH,
    SAME_COLUMN,
    SAME_ROW,
    VISIBLE_TAP,
)


# --------------------------------------------------------------------- inputs


def _part(part_id: str, symbol: str = "R0402", value: str = "10k") -> dict:
    return {"id": part_id, "symbolRef": symbol, "value": value}


def _net(net_id: str, cls: str, members: list[str]) -> dict:
    return {"id": net_id, "class": cls, "members": list(members)}


def _circuit(parts: list[dict], nets: list[dict]) -> CircuitSpec:
    return CircuitSpec.from_dict({"parts": parts, "nets": nets})


def _presentation(**overrides) -> PresentationSpec:
    payload: dict = {"grammarRef": "voltage-divider"}
    payload.update(overrides)
    return PresentationSpec.from_dict(payload)


def _bind(circuit: CircuitSpec, presentation: PresentationSpec):
    return voltage_divider.grammar().bind(circuit, presentation)


def _nets_of(result, kind: str) -> list[tuple[str, ...]]:
    return [item.nets for item in result.obligations if item.kind == kind]


def _evidence_text(result) -> str:
    return "\n".join(item.evidence for item in result.bindings)


#: The two layout declarations the family reading is opted in by (548D3D-F1A):
#: served seats (`serviceLayout`) and a real name stub (`labelPolicy.stubMin`).
#: `textPlacement: native-attr` is deliberately **not** one of them — keying on it
#: turned the compiler's page-wide paired reading on for unrelated islands.
EXPLICIT = {"serviceLayout": {"pinGap": 30}, "labelPolicy": {"stubMin": 40}}


def _led_circuit() -> CircuitSpec:
    """R2/D1 and R3/D2: two LED branches, each `net→R→tap→D→GND`."""
    return _circuit(
        [_part("R2"), _part("R3"), _part("D1", "LED0603"), _part("D2", "LED0603")],
        [
            _net("LED1_K", "signal", ["R2.1"]),
            _net("LED1_A", "signal", ["R2.2", "D1.1"]),
            _net("LED2_K", "signal", ["R3.1"]),
            _net("LED2_A", "signal", ["R3.2", "D2.1"]),
            _net("GND", "gnd", ["D1.2", "D2.2"]),
        ],
    )


def _led_presentation(**overrides) -> PresentationSpec:
    """The LED island: `LED1_K`/`LED2_K` are the island's declared inputs."""
    payload = {
        "portRoles": {"LED1_K": "input", "LED2_K": "input"},
    }
    payload.update(overrides)
    return _presentation(**payload)


# ------------------------------------------------------- the family is bound


def test_led_island_binds_both_branches_when_the_page_declares_the_pair_reading():
    result = _bind(_led_circuit(), _led_presentation(**EXPLICIT))

    assert result.ok is True
    assert result.parts_of("upper_arm") == ("R2", "R3")
    assert result.parts_of("lower_arm") == ("D1", "D2")
    assert result.parts_of("tap") == ("LED1_A", "LED2_A")
    # 两条链各自的第一脚：in 按网去重后是两条，回同一个地则只绑一次。
    assert result.parts_of("in") == ("LED1_K", "LED2_K")
    assert result.parts_of("gnd") == ("GND",)
    # 家族里没有第四件器件：每一条臂都已经属于某条链，不做别人的抽头支路。
    assert result.parts_of("tap_branch") == ()


def test_each_chain_states_its_own_wire_and_its_own_visible_tap():
    result = _bind(_led_circuit(), _led_presentation(**EXPLICIT))

    assert _nets_of(result, DIRECT_WIRE) == [
        ("LED1_K", "LED1_A", "GND"),
        ("LED2_K", "LED2_A", "GND"),
    ]
    assert _nets_of(result, VISIBLE_TAP) == [("LED1_A",), ("LED2_A",)]


def test_the_two_branches_are_read_by_one_rule_and_one_direction():
    result = _bind(_led_circuit(), _led_presentation(**EXPLICIT))

    pairs = [(item.kind, item.subject, item.object) for item in result.constraints]
    assert pairs == [
        (SAME_COLUMN, "R2", "D1"), (ABOVE, "R2", "D1"),
        (HORIZONTAL_TAP, "R2", "D1"),
        (SAME_COLUMN, "R3", "D2"), (ABOVE, "R3", "D2"),
        (HORIZONTAL_TAP, "R3", "D2"),
        # 同族并列：对应臂同排（同向、对齐，boardwise-draw §3）。
        (SAME_ROW, "R2", "R3"), (SAME_ROW, "D1", "D2"),
    ]


def test_a_horizontal_family_aligns_on_columns_instead_of_rows():
    presentation = _led_presentation(
        sidePreferences={"power": "left", "gnd": "right"}, **EXPLICIT
    )
    result = _bind(_led_circuit(), presentation)

    pairs = [(item.kind, item.subject, item.object) for item in result.constraints]
    assert (LEFT_OF, "R2", "D1") in pairs
    assert (SAME_ROW, "R2", "D1") in pairs
    assert (SAME_COLUMN, "R2", "R3") in pairs
    assert (SAME_COLUMN, "D1", "D2") in pairs


def test_a_bound_chain_is_not_named_as_an_unbound_runner_up():
    result = _bind(_led_circuit(), _led_presentation(**EXPLICIT))

    # 两条都绑了，就没有 "found but not bound" 的读法可报。
    assert "not bound" not in _evidence_text(result)


def test_three_branches_bind_two_and_name_only_the_third_as_a_runner_up():
    # D3 与 D1 并联在 LED1_A 上：它和第一条链共用臂 R2，不是第三条独立链。
    circuit = _circuit(
        [
            _part("R2"), _part("R3"),
            _part("D1", "LED0603"), _part("D2", "LED0603"),
            _part("D3", "LED0603"),
        ],
        [
            _net("LED1_K", "signal", ["R2.1"]),
            _net("LED1_A", "signal", ["R2.2", "D1.1", "D3.1"]),
            _net("LED2_K", "signal", ["R3.1"]),
            _net("LED2_A", "signal", ["R3.2", "D2.1"]),
            _net("GND", "gnd", ["D1.2", "D2.2", "D3.2"]),
        ],
    )
    result = _bind(circuit, _led_presentation(**EXPLICIT))

    assert result.ok is True
    assert result.parts_of("upper_arm") == ("R2", "R3")
    assert result.parts_of("lower_arm") == ("D1", "D2")
    note = _evidence_text(result)
    assert "bound 2 independent chains" in note
    # 未绑定名单里只有共臂的那条读法；两条已绑定链不在名单里（名单只有一项）。
    assert (
        "bound 2 independent chains): LED1_K→R2→LED1_A→D3→GND" in note
    )
    assert "): LED1_K→R2→LED1_A→D1→GND" not in note
    assert "): LED2_K→R3→LED2_A→D2→GND" not in note


def test_shared_arm_is_one_ladder_not_two_chains():
    # VIN→R1→T1 之后分成 R2→T2→R3 与 R4 两条去地路径：共用 R1，不是两条独立链。
    circuit = _circuit(
        [_part("R1"), _part("R2"), _part("R3"), _part("R4")],
        [
            _net("VIN", "signal", ["R1.1"]),
            _net("T1", "signal", ["R1.2", "R2.1", "R4.1"]),
            _net("T2", "signal", ["R2.2", "R3.1"]),
            _net("GND", "gnd", ["R3.2", "R4.2"]),
        ],
    )
    result = _bind(
        circuit, _presentation(portRoles={"VIN": "input"}, **EXPLICIT)
    )

    assert result.ok is True
    assert result.parts_of("upper_arm") == ("R1",)
    assert result.parts_of("middle_arm") == ("R2",)
    assert result.parts_of("lower_arm") == ("R3",)
    assert "not bound" in _evidence_text(result)


def test_shared_tap_with_different_arms_is_one_divider_not_two():
    # 两条支路各用两个电阻，但都挂在同一个 T 上：那不是两条独立链。
    circuit = _circuit(
        [_part("R1"), _part("R2"), _part("R3"), _part("R4")],
        [
            _net("S", "signal", ["R1.1", "R3.1"]),
            _net("T", "signal", ["R1.2", "R2.1", "R3.2", "R4.1"]),
            _net("GND", "gnd", ["R2.2", "R4.2"]),
        ],
    )
    result = _bind(
        circuit, _presentation(portRoles={"S": "input"}, **EXPLICIT)
    )

    assert result.ok is True
    assert result.parts_of("upper_arm") == ("R1",)
    assert result.parts_of("lower_arm") == ("R2",)
    assert (
        "bound one chain): S→R1→T→R4→GND; S→R3→T→R2→GND; S→R3→T→R4→GND"
        in _evidence_text(result)
    )


def test_chains_in_two_declared_modules_are_not_one_family():
    circuit = _circuit(
        [_part("R1"), _part("R2"), _part("R3"), _part("R4")],
        [
            _net("S", "signal", ["R1.1", "R3.1"]),
            _net("T1", "signal", ["R1.2", "R2.1"]),
            _net("T2", "signal", ["R3.2", "R4.1"]),
            _net("GND", "gnd", ["R2.2", "R4.2"]),
        ],
    )
    presentation = _presentation(
        portRoles={"S": "input"},
        modules=[
            {"id": "a", "parts": ["R1", "R2"], "role": "indicator"},
            {"id": "b", "parts": ["R3", "R4"], "role": "indicator"},
        ],
        **EXPLICIT,
    )
    result = _bind(circuit, presentation)

    assert result.ok is True
    assert result.parts_of("upper_arm") == ("R1",)
    assert result.parts_of("lower_arm") == ("R2",)
    assert (
        "bound one chain): S→R3→T2→R4→GND" in _evidence_text(result)
    )


# -------------------------------------------------- the old reading is kept


def test_the_family_needs_a_stub_switch_plus_served_seats_and_a_signal_top():
    plain = _bind(_led_circuit(), _led_presentation())
    only_seats = _bind(
        _led_circuit(), _led_presentation(serviceLayout={"pinGap": 30})
    )
    # 548D3D-F1's first gate: `native-attr` alone does not buy the family — it
    # changed two unrelated islands' page-wide paired reading.
    only_native = _bind(
        _led_circuit(), _led_presentation(textPlacement="native-attr")
    )
    native_and_seats = _bind(
        _led_circuit(),
        _led_presentation(
            textPlacement="native-attr", serviceLayout={"pinGap": 30}
        ),
    )
    # `stubMin` without a stated serviceLayout is one declaration, not two.
    stub_only = _bind(
        _led_circuit(), _led_presentation(labelPolicy={"stubMin": 40})
    )
    family = _bind(_led_circuit(), _led_presentation(**EXPLICIT))

    for single in (plain, only_seats, only_native, native_and_seats, stub_only):
        assert single.ok is True
        assert single.parts_of("upper_arm") == ("R2",)
        assert single.to_jsonable() == plain.to_jsonable()
    # 两个布局声明都写了：第二条链被读进家族。
    assert family.to_jsonable() != plain.to_jsonable()
    assert family.parts_of("upper_arm") == ("R2", "R3")


def test_a_power_divider_keeps_the_first_chain_even_with_the_pair_reading():
    circuit = _circuit(
        [_part("R1"), _part("R2"), _part("R3"), _part("R4")],
        [
            _net("VIN", "power", ["R1.1", "R3.1"]),
            _net("T1", "signal", ["R1.2", "R2.1"]),
            _net("T2", "signal", ["R3.2", "R4.1"]),
            _net("GND", "gnd", ["R2.2", "R4.2"]),
        ],
    )
    result = _bind(circuit, _presentation(**EXPLICIT))

    assert result.ok is True
    assert result.parts_of("upper_arm") == ("R1",)
    assert result.parts_of("lower_arm") == ("R2",)
    assert "not bound" in _evidence_text(result)


def test_one_chain_under_the_pair_reading_is_the_old_result():
    circuit = _circuit(
        [_part("R2"), _part("D1", "LED0603")],
        [
            _net("LED1_K", "signal", ["R2.1"]),
            _net("LED1_A", "signal", ["R2.2", "D1.1"]),
            _net("GND", "gnd", ["D1.2"]),
        ],
    )
    plain = _bind(circuit, _led_presentation())
    family = _bind(circuit, _led_presentation(**EXPLICIT))

    assert family.to_jsonable() == plain.to_jsonable()


def test_two_runs_of_one_input_are_the_same_binding():
    first = _bind(_led_circuit(), _led_presentation(**EXPLICIT))
    second = _bind(_led_circuit(), _led_presentation(**EXPLICIT))

    assert first.to_jsonable() == second.to_jsonable()


def test_the_shared_ground_does_not_own_a_branch():
    # D1/D2 都是链上的臂，所以任何一条链的抽头都没有"并联支路"可报。
    result = _bind(_led_circuit(), _led_presentation(**EXPLICIT))

    assert [item.nets for item in result.obligations if item.kind == OWNED_BRANCH] == []
