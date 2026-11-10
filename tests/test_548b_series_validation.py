"""548B2：`seriesBranches` 的跨文档校验（V1–V8），以及两个消费者是否真的接上了它。

548B1 只做了**文档语法**：一条支路声明两个件、两端和两件之间的节点，解析器不判断这
两件在电路里是不是真的那样连着。判据 `evidence/548B2/criteria.md` 把那一半交给
「同时持有两份文档的消费者」：`drawcompiler.validate_series_branches(circuit,
presentation)` 返回拒因列表（退化为空），standalone `dc.compile` 与
`pc.compile_page` 都必须先过它、再进几何。

本文件分三层，故意不混：

1. **校验合同**（本文件的手写 CircuitSpec + PresentationSpec，不需要符号库、不编译）：
   一条合法支路返回 `[]`，高边 `GPIO→R→LED→GND` 与低边 `GPIO→R→LED→3V3` 都要过；
   V1–V8 每条一个具体反例，断言**类别**与**关键对象**（哪个件、哪个网、哪两条条目），
   不是"报了个错"。类别只许是 053 §4 的四类。
2. **消费者接入**：非法声明必须在几何之前被拒（零候选/零页），且页面切片不得把
   跨模块声明静默丢掉——`_module_view` 只携带两件同属一个模块的声明，其余先由 V7
   具名拒绝。合法声明的正例**不要求本批几何通过**（串联几何是 548B3）。
3. **零新增行为**：未声明 / `[]` 的文档，校验为空、编译读数与今天一致。

本文件不跑真机、不读 `evidence/` 作为输入、不 import `connector` / `cli` / `rules`，
也不对生产代码做任何 monkeypatch：前红就是"接口不存在"，不是把它假装成存在。
"""

from __future__ import annotations

import copy
import json

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolPin, SymbolProfile
from boardwise.engines import drawcompiler as dc
from boardwise.engines import pagecompiler as pc
from boardwise.engines.grammar.base import GrammarFailure

PROV = "verified_recipe"

#: "the caller said nothing" — distinct from "the caller declared an empty list",
#: which is a statement of its own (548B1: `[]` == no key, but both mean "no arm").
_UNSET = object()

#: 053 §4 的四类拒因，本批不许有第五类。
CATEGORIES = (
    "facts-missing",
    "circuit-invalid",
    "layout-unsat",
    "presentation-poor",
)

#: 056 场景 1 用的那张页：页级编译必须拿到一张纸，否则连"装不装得下"都问不出来。
PAGE = pc.PageCompileBudget(page_box=(0.0, 0.0, 1169.0, 826.0))


# ------------------------------------------------------------------ 手写文档
#
# 高低边两支 LED 是判据 §「正例」的原文：`U1` 是宿主，`R2/LED1` 是支路上的两件，
# `LED_A` 是这一对私有的中间节点。网表只有无向分区，阅读方向由 `parts` 的次序说，
# 所以**低边那一支的 `from` 仍是 GPIO**，电流方向不进合同。


def _part(part_id: str, symbol: str, value: str = "") -> dict:
    return {"id": part_id, "symbolRef": symbol, "value": value, "provenance": PROV}


def _net(net_id: str, cls: str, members: list[str]) -> dict:
    return {"id": net_id, "class": cls, "members": list(members), "provenance": PROV}


_HIGH_PARTS = [
    _part("U1", "MCU32", "MCU"),
    _part("R2", "R0402", "1k"),
    _part("LED1", "LED0805", "red"),
]

_HIGH_NETS = [
    _net("GPIO_STAT", "signal", ["U1.PA5", "R2.1"]),
    _net("LED_A", "signal", ["R2.2", "LED1.A"]),
    _net("GND", "gnd", ["U1.VSS", "LED1.K"]),
    _net("3V3", "power", ["U1.VDD"]),
]

_LOW_PARTS = _HIGH_PARTS + [
    _part("R4", "R0402", "1k"),
    _part("LED2", "LED0805", "red"),
]

_LOW_NETS = [
    _net("LED_N", "signal", ["U1.PB0", "R4.1"]),
    _net("LED_B", "signal", ["R4.2", "LED2.K"]),
    _net("3V3", "power", ["LED2.A", "U1.VDD"]),
    _net("GND", "gnd", ["U1.VSS"]),
]


def _module(module_id: str, parts: list[str], role: str = "status led") -> dict:
    return {
        "id": module_id,
        "parts": list(parts),
        "role": role,
        "grammarRef": "ic-periphery",
        "core": parts[0],
    }


_HIGH_MODULES = [_module("mcu", ["U1", "R2", "LED1"])]


def _branch(**overrides) -> dict:
    entry = {
        "id": "status-led",
        "from": "GPIO_STAT",
        "to": "GND",
        "parts": ["R2", "LED1"],
        "middleNet": "LED_A",
    }
    entry.update(overrides)
    return entry


def _nets(**members_by_net) -> list[dict]:
    """The high-side netlist with the named nets replaced; a new id is appended.

    Replacing `members` rather than adding a net keeps every negative fixture one
    sentence long: the test names only the net it means to break.
    """
    nets = copy.deepcopy(_HIGH_NETS)
    for net_id, members in members_by_net.items():
        for item in nets:
            if item["id"] == net_id:
                item["members"] = list(members)
                break
        else:
            nets.append(_net(net_id, "signal", members))
    return nets


def _documents(parts=None, nets=None, modules=None, branches=None):
    """One circuit and one presentation, both hand-written (no library needed)."""
    circuit = CircuitSpec.from_dict({
        "parts": copy.deepcopy(parts if parts is not None else _HIGH_PARTS),
        "nets": copy.deepcopy(nets if nets is not None else _HIGH_NETS),
    })
    payload = {
        "grammarRef": "ic-periphery",
        "modules": copy.deepcopy(
            modules if modules is not None else _HIGH_MODULES
        ),
    }
    if branches is not None:
        payload["seriesBranches"] = copy.deepcopy(branches)
    return circuit, PresentationSpec.from_dict(payload)


# --------------------------------------------------------------- 断言小工具


def _refusals(circuit: CircuitSpec, presentation: PresentationSpec) -> list:
    """The one call this batch introduces, through the public engine module."""
    validate = getattr(dc, "validate_series_branches", None)
    assert validate is not None, (
        "drawcompiler 没有 validate_series_branches：548B2 的跨文档校验还没有"
        "消费者入口，V1–V8 无从谈起"
    )
    answer = validate(circuit, presentation)
    assert isinstance(answer, list), (
        f"validate_series_branches 必须返回拒因列表（合法时为空表），得到 "
        f"{type(answer).__name__}"
    )
    for item in answer:
        assert isinstance(item, GrammarFailure), (
            "拒因必须是 GrammarFailure：类别、实测细节与动作是既有的那一套，"
            f"得到 {type(item).__name__}"
        )
    return answer


def _text(item: GrammarFailure) -> str:
    return " ".join(
        str(part) for part in (item.category, item.subject, item.detail, item.action)
    )


def _assert_refused(
    refusals: list, category: str, *tokens: str, where: str = ""
) -> None:
    """A refusal of this category that names every token the caller asked for.

    Category alone is not the contract: 053 §4 asks each refusal to say **which**
    part, net or entry. ``tokens`` are the objects the rule's own message owes.
    """
    same = [item for item in refusals if item.category == category]
    assert same, (
        f"{where or 'the declaration'} must be refused as {category}; got "
        f"{[(item.category, item.detail) for item in refusals] or 'no refusal'}"
    )
    joined = " ".join(_text(item) for item in same)
    missing = [token for token in tokens if token not in joined]
    assert not missing, (
        f"the {category} refusal must name {missing}; its message was {joined!r}"
    )


def _validate(*, parts=None, nets=None, modules=None, branches=_UNSET):
    """The high-side declaration against the given documents unless one is passed.

    Every V1–V8 fixture changes **one** fact and keeps the rest of the legal arm,
    otherwise a refusal could come from a different rule than the test names.
    """
    if branches is _UNSET:
        branches = [_branch()]
    circuit, presentation = _documents(
        parts=parts, nets=nets, modules=modules, branches=branches
    )
    return _refusals(circuit, presentation)


# =========================================================== 正例（阅读方向）
#
# 两条都是"引脚出发、终端收尾"，与电流方向无关：低边那一支电流从 3V3 流向 PB0，
# 合同却从 LED_N 读起——同一块板上两种极性不许要两套规则。


def test_a_high_side_led_arm_is_accepted():
    """GPIO → R → LED → GND：零拒因。"""
    assert _validate(branches=[_branch()]) == []


def test_a_low_side_led_arm_is_accepted_with_its_power_rail_as_the_far_end():
    """GPIO → R → LED → 3V3：`to` 不必是地，也不按电流方向重排。"""
    assert _validate(
        parts=_LOW_PARTS,
        nets=_LOW_NETS,
        modules=[_module("mcu", ["U1", "R4", "LED2"])],
        branches=[{
            "id": "run-led",
            "from": "LED_N",
            "to": "3V3",
            "parts": ["R4", "LED2"],
            "middleNet": "LED_B",
        }],
    ) == []


def test_two_legal_arms_in_one_module_are_both_accepted():
    """两条各占一对私有中间节点：不是"同名网焊接"，是两条独立的串联。"""
    assert _validate(
        parts=_HIGH_PARTS + [_part("R3", "R0402", "1k"), _part("LED2", "LED0805", "green")],
        nets=_nets(
            GPIO_STAT2=["U1.PB0", "R3.1"],
            LED_B=["R3.2", "LED2.A"],
            GND=["U1.VSS", "LED1.K", "LED2.K"],
        ),
        modules=[_module("mcu", ["U1", "R2", "LED1", "R3", "LED2"])],
        branches=[
            _branch(),
            _branch(id="power-led", **{"from": "GPIO_STAT2"},
                    parts=["R3", "LED2"], middleNet="LED_B"),
        ],
    ) == []


def test_nothing_declared_and_an_empty_list_are_the_same_statement():
    """未声明与 `[]`：校验为空，规范 JSON 里也没有这个键（548B1 的合同不移动）。"""
    undeclared_circuit, undeclared = _documents()
    declared_circuit, empty = _documents(branches=[])
    assert _refusals(undeclared_circuit, undeclared) == []
    assert _refusals(declared_circuit, empty) == []
    canonical = json.dumps(empty.to_jsonable(), sort_keys=True,
                           separators=(",", ":"), ensure_ascii=False)
    assert "seriesBranches" not in canonical
    assert empty.to_jsonable() == undeclared.to_jsonable()


# =================================================================== V1 事实存在


def test_v1_a_missing_middle_net_is_facts_missing_and_names_where_to_write_it():
    """`middleNet` 不在 `CircuitSpec.nets` 里：点名网与 `nets[]`。"""
    refusals = _validate(branches=[_branch(middleNet="LED_X")])
    _assert_refused(refusals, "facts-missing", "LED_X", "nets", where="LED_X")


def test_v1_a_missing_part_is_facts_missing_and_names_where_to_write_it():
    """`parts` 里的件不在 `CircuitSpec.parts` 里：点名件与 `parts[]`。

    `LED9` 被模块收录（所以 V7 的"恰好一个共同模块"成立），但电路里没有它——
    这正是"声明不能创建连接"的入口。
    """
    refusals = _validate(
        modules=[_module("mcu", ["U1", "R2", "LED1", "LED9"])],
        branches=[_branch(parts=["R2", "LED9"])],
    )
    _assert_refused(refusals, "facts-missing", "LED9", "parts", where="LED9")


# =================================================================== V2 两脚两网


def test_v2_a_three_pin_part_is_circuit_invalid_and_shows_the_third_pin():
    """`R2` 被网表提到三个脚：串联臂必须两脚两网，第三脚要出现在拒因里。"""
    refusals = _validate(nets=_nets(SPARE=["R2.3"]))
    _assert_refused(refusals, "circuit-invalid", "R2", "SPARE", where="R2.3")


def test_v2_a_part_with_both_pins_on_one_net_is_circuit_invalid():
    """`R2.1`/`R2.2` 短在同一网：给实际 pin→net，不是只说"连错了"。

    两个脚都落在 `LED_A` 上时 `GPIO_STAT` 上已经没有被声明的那一件——这不影响
    本条的读数：短路先被点出来，而`R2` 的实际 pin→net 表是它必须说的话。
    """
    refusals = _validate(nets=_nets(
        GPIO_STAT=["U1.PA5"],
        LED_A=["R2.1", "R2.2", "LED1.A"],
    ))
    _assert_refused(refusals, "circuit-invalid", "R2.1", "R2.2",
                    where="a short across R2")


# =================================================================== V3 声明顺序


def test_v3_the_declared_order_must_match_the_netlist():
    """声明写成 `LED1 → R2`，网表只支持 `R2 → LED1`：逐脚对照，不按声明相信。"""
    refusals = _validate(branches=[_branch(parts=["LED1", "R2"])])
    _assert_refused(refusals, "circuit-invalid", "LED1", "GPIO_STAT", "LED_A",
                    where="the reversed order")


def test_v3_a_pin_outside_the_three_declared_nets_is_circuit_invalid():
    """`LED1` 还有一脚落在第三网：链只允许 from/middle/to 三个网。"""
    refusals = _validate(nets=_nets(SPARE=["LED1.X"]))
    _assert_refused(refusals, "circuit-invalid", "LED1", "SPARE",
                    where="LED1.X")


# =================================================================== V4 中间节点私有


def test_v4_one_middle_net_claimed_by_two_arms_is_circuit_invalid():
    """两条支路把同一个网当中点：点名网与两条条目——不许拿同名网把两支焊成一点。"""
    refusals = _validate(
        parts=_HIGH_PARTS + [_part("R3", "R0402", "1k"),
                            _part("LED2", "LED0805", "green")],
        nets=_nets(
            GPIO_STAT2=["U1.PB0", "R3.1"],
            LED_A=["R2.2", "LED1.A", "R3.2", "LED2.A"],
            GND=["U1.VSS", "LED1.K", "LED2.K"],
        ),
        modules=[_module("mcu", ["U1", "R2", "LED1", "R3", "LED2"])],
        branches=[
            _branch(),
            _branch(id="status-led-2", **{"from": "GPIO_STAT2"},
                    parts=["R3", "LED2"], middleNet="LED_A"),
        ],
    )
    _assert_refused(refusals, "circuit-invalid", "LED_A",
                    "status-led", "status-led-2", where="the shared middle net")


def test_v4_a_middle_net_with_a_third_member_is_circuit_invalid():
    """中点上有第三个脚（测试点）：那已经是带分支的节点，不是两件串联。"""
    refusals = _validate(
        parts=_HIGH_PARTS + [_part("TP1", "TP", "test point")],
        nets=_nets(LED_A=["R2.2", "LED1.A", "TP1.1"]),
    )
    _assert_refused(refusals, "circuit-invalid", "LED_A", "TP1",
                    where="a third member on LED_A")


# ======================================================================= V5 两端


def test_v5_the_same_net_at_both_ends_is_a_loop_not_a_series():
    """`from == to`：同网两端是环/并联，拒绝并点名那条支路。"""
    refusals = _validate(
        nets=_nets(GND=["U1.VSS", "LED1.K", "R2.1"],
                   GPIO_STAT=["U1.PA5"]),
        branches=[_branch(to="GND", **{"from": "GND"})],
    )
    _assert_refused(refusals, "circuit-invalid", "GND", "status-led",
                    where="from == to")


def test_v5_a_middle_net_equal_to_an_endpoint_is_circuit_invalid():
    """`middleNet == from`：中间节点不能是端点本身。"""
    refusals = _validate(branches=[_branch(middleNet="GPIO_STAT")])
    _assert_refused(refusals, "circuit-invalid", "GPIO_STAT", where="middle == from")


# ======================================================================= V6 宿主


def test_v6_zero_hosts_on_the_from_net_is_circuit_invalid():
    """`GPIO_STAT` 上除了 `R2` 没有别的脚：支路悬空，点名那个网。"""
    refusals = _validate(nets=_nets(GPIO_STAT=["R2.1"]))
    _assert_refused(refusals, "circuit-invalid", "GPIO_STAT", where="a dangling arm")


def test_v6_two_hosts_on_the_from_net_are_refused_with_both_candidates():
    """宿主歧义：列出候选宿主脚，不猜。"""
    refusals = _validate(nets=_nets(GPIO_STAT=["U1.PA5", "U1.PB0", "R2.1"]))
    _assert_refused(refusals, "circuit-invalid", "U1.PA5", "U1.PB0",
                    where="two candidate hosts")


# =================================================================== V7 模块归属


def test_v7_zero_common_modules_is_facts_missing_and_names_both_owners():
    """`R2` 在 `mcu`、`LED1` 在 `panel`：一条支路不跨岛，点名各件归属。"""
    refusals = _validate(
        modules=[_module("mcu", ["U1", "R2"]), _module("panel", ["LED1"])],
    )
    _assert_refused(refusals, "facts-missing", "R2", "LED1", "mcu", "panel",
                    where="a cross-module arm")


def test_v7_two_common_modules_is_facts_missing_too():
    """两件同时被两个模块收录：不是"随便挑一个"，是归属不唯一。"""
    refusals = _validate(
        modules=[_module("mcu", ["U1", "R2", "LED1"]),
                 _module("panel", ["R2", "LED1"])],
    )
    _assert_refused(refusals, "facts-missing", "mcu", "panel",
                    where="two owning modules")


# ================================================================= V8 一件一支路


def test_v8_the_same_pair_declared_twice_in_reverse_is_circuit_invalid():
    """反向重写同一对件：一件只能有一种串联读法，点名两条条目。

    这条形状同时也触发 V4（`LED_A` 被两条支路声明）——两脚世界里没法把"共享
    中点"和"重复声明"完全分开，所以断言是"两条条目的 id 与共用件都出现在同一条
    拒因里"，而不只是"拒了"。
    """
    refusals = _validate(branches=[
        _branch(),
        _branch(id="status-led-rev", **{"from": "GND", "to": "GPIO_STAT"},
                parts=["LED1", "R2"]),
    ])
    _assert_refused(refusals, "circuit-invalid",
                    "status-led", "status-led-rev", "R2",
                    where="the reversed duplicate")


def test_no_fifth_failure_category_is_invented():
    """V1/V2/V7 三种拒因都落在 053 §4 的四类里，本批不新增类别。"""
    seen: list[str] = []
    for refusals in (
        _validate(branches=[_branch(middleNet="LED_X")]),
        _validate(nets=_nets(SPARE=["R2.3"])),
        _validate(modules=[_module("mcu", ["U1", "R2"]),
                           _module("panel", ["LED1"])]),
    ):
        assert refusals, "每一种反例都必须被拒"
        seen.extend(item.category for item in refusals)
    unknown = sorted(set(seen) - set(CATEGORIES))
    assert not unknown, f"本批不许新开拒因类别，得到 {unknown}"


# ======================================================== 符号库（消费者才需要）


def _pins(rows) -> list[SymbolPin]:
    return [
        SymbolPin(number=number, tip=tip, name=number, direction=direction)
        for number, tip, direction in rows
    ]


def _flag(ref: str) -> SymbolProfile:
    return SymbolProfile(
        symbol_ref=ref, title=ref, body=(-6.0, 0.0, 6.0, 18.0), pins=[]
    )


def _resistor() -> SymbolProfile:
    return SymbolProfile(
        symbol_ref="R0402", title="Resistor", body=(-10.0, -20.0, 10.0, 20.0),
        pins=_pins((("1", (0.0, 50.0), "up"), ("2", (0.0, -50.0), "down"))),
    )


def _capacitor() -> SymbolProfile:
    return SymbolProfile(
        symbol_ref="C0402", title="Capacitor", body=(-8.0, -12.0, 8.0, 12.0),
        pins=_pins((("1", (0.0, 40.0), "up"), ("2", (0.0, -40.0), "down"))),
    )


def _regulator() -> SymbolProfile:
    return SymbolProfile(
        symbol_ref="AMS1117-3.3", title="AMS1117-3.3",
        body=(-40.0, -30.0, 40.0, 30.0),
        pins=[
            SymbolPin(number="3", tip=(-60.0, 0.0), name="VIN", direction="left",
                      electrical_role="VIN", role_source="pin-name"),
            SymbolPin(number="2", tip=(60.0, 0.0), name="VOUT", direction="right",
                      electrical_role="VOUT", role_source="pin-name"),
            SymbolPin(number="1", tip=(0.0, -60.0), name="GND", direction="down",
                      electrical_role="GND", role_source="pin-name"),
        ],
    )


def _library() -> dict[str, SymbolProfile]:
    book = {
        "R0402": _resistor(),
        "C0402": _capacitor(),
        "AMS1117-3.3": _regulator(),
    }
    for name in ("PWR-GND", "PWR-VIN", "PWR-3V3", "PWR-VIN5"):
        book[name] = _flag(name)
    return book


# --------------------------------------------- 消费者夹具（056 场景 1 的形状）


def _divider_circuit() -> CircuitSpec:
    """一条独立的分压器：两件两网一抽头，`dc.compile` 今天就能画。"""
    return CircuitSpec.from_dict({
        "parts": [
            _part("R1", "R0402", "10k"),
            _part("R2", "R0402", "10k"),
        ],
        "nets": [
            _net("VIN", "power", ["R1.1"]),
            _net("TAP", "signal", ["R1.2", "R2.1"]),
            _net("GND", "gnd", ["R2.2"]),
        ],
    })


def _divider_presentation(branches=None) -> PresentationSpec:
    payload = {
        "grammarRef": "voltage-divider",
        "modules": [{"id": "div", "parts": ["R1", "R2"], "role": "divider",
                     "grammarRef": "voltage-divider"}],
        "portRoles": {"VIN": "input"},
    }
    if branches is not None:
        payload["seriesBranches"] = branches
    return PresentationSpec.from_dict(payload)


def _page_circuit() -> CircuitSpec:
    """056 场景 1：稳压器与分压器共一条轨、一个地，两个模块。"""
    return CircuitSpec.from_dict({
        "parts": [
            _part("U1", "AMS1117-3.3", "AMS1117-3.3"),
            _part("C1", "C0402", "10u"),
            _part("C2", "C0402", "22u"),
            _part("R1", "R0402", "10k"),
            _part("R2", "R0402", "10k"),
        ],
        "nets": [
            _net("VIN", "power", ["U1.VIN", "C1.1", "R1.1"]),
            _net("3V3", "power", ["U1.VOUT", "C2.1"]),
            _net("TAP", "signal", ["R1.2", "R2.1"]),
            _net("GND", "gnd", ["U1.GND", "C1.2", "C2.2", "R2.2"]),
        ],
    })


def _page_presentation(branches=None) -> PresentationSpec:
    payload = {
        "grammarRef": "ldo",
        "modules": [
            {"id": "pwr", "parts": ["U1", "C1", "C2"], "role": "regulator",
             "grammarRef": "ldo"},
            {"id": "sense", "parts": ["R1", "R2"], "role": "divider",
             "grammarRef": "voltage-divider"},
        ],
        "flow": [["pwr", "sense"]],
        "portRoles": {"VIN": "input", "3V3": "output"},
        "directWiringObligations": [
            {"nets": ["VIN", "3V3"],
             "note": "the regulator's own rails are wired"},
        ],
    }
    if branches is not None:
        payload["seriesBranches"] = branches
    return PresentationSpec.from_dict(payload)


# ======================================================= 消费者：standalone dc.compile
#
# 两种读数对照：同一份文档**不声明**时今天能编译出候选（控制组），一加非法声明
# 就必须在几何之前变成零候选 + 对应类别的拒因。控制组是这条测试的一半——没有它，
# "拒绝了"可能只是这份文档本来就不合格。


def test_standalone_compile_refuses_a_branch_whose_net_the_circuit_lacks():
    control = dc.compile(_divider_circuit(), _divider_presentation(), _library())
    assert control.ok, [failure.detail for failure in control.failures]

    refused = dc.compile(
        _divider_circuit(),
        _divider_presentation(branches=[{
            "id": "divider",
            "from": "NOPE",
            "to": "GND",
            "parts": ["R1", "R2"],
            "middleNet": "TAP",
        }]),
        _library(),
    )
    assert refused.ok is False, "非法声明不许出候选——校验必须在几何之前"
    assert refused.candidates == []
    _assert_refused(refused.failures, "facts-missing", "NOPE",
                    where="dc.compile")


def test_standalone_compile_still_compiles_an_undeclared_document():
    """未声明（以及 `[]`）：候选数与今天一致，校验不产生新行为。"""
    bare = dc.compile(_divider_circuit(), _divider_presentation(), _library())
    empty = dc.compile(
        _divider_circuit(), _divider_presentation(branches=[]), _library()
    )
    assert bare.ok and empty.ok
    assert len(empty.candidates) == len(bare.candidates)
    assert empty.categories() == bare.categories() == []


# ========================================================= 消费者：pc.compile_page


def test_page_compile_refuses_an_illegal_declaration_before_any_page():
    control = pc.compile_page(_page_circuit(), _page_presentation(), _library(), PAGE)
    assert control.ok, [failure.detail for failure in control.failures]

    refused = pc.compile_page(
        _page_circuit(),
        _page_presentation(branches=[{
            "id": "divider",
            "from": "NOPE",
            "to": "GND",
            "parts": ["R1", "R2"],
            "middleNet": "TAP",
        }]),
        _library(),
        PAGE,
    )
    assert refused.pages == [], "非法声明不许出页——校验在几何之前，不是布局失败"
    _assert_refused(refused.failures, "facts-missing", "NOPE",
                    where="pc.compile_page")


def test_page_compile_refuses_a_cross_module_branch_instead_of_dropping_it():
    """`C1` 在 `pwr`、`R1` 在 `sense`：V7 先具名拒绝，页面不许静默吞掉。

    今天 `_module_view` 会把两件各自留下、把声明整个丢掉——页面照样编译成功，
    声明就这么没了。这就是本条要挡的失败模式：不是"画不出来"，是"说了却没人报"。
    """
    control = pc.compile_page(_page_circuit(), _page_presentation(), _library(), PAGE)
    assert control.ok, [failure.detail for failure in control.failures]

    refused = pc.compile_page(
        _page_circuit(),
        _page_presentation(branches=[{
            "id": "cross-module",
            "from": "VIN",
            "to": "GND",
            "parts": ["C1", "R1"],
            "middleNet": "TAP",
        }]),
        _library(),
        PAGE,
    )
    assert refused.pages == []
    _assert_refused(refused.failures, "facts-missing", "C1", "R1", "pwr", "sense",
                    where="the cross-module declaration")
    assert refused.categories() == ["facts-missing"], (
        "跨模块声明是一条具名的归属拒绝，不该被别的类别盖住："
        f"{refused.categories()}"
    )


# --------------------------------------------------- 页面切片：携带与不携带


def test_the_module_view_carries_a_branch_both_of_whose_parts_it_owns():
    """两件同属 `mcu` 的声明必须跟着切片走，否则模块编译看不见它。"""
    circuit, presentation = _documents(branches=[_branch()])
    module = presentation.module("mcu")
    _sub_circuit, sub_presentation = pc._module_view(circuit, presentation, module)

    assert [item.id for item in sub_presentation.series_branches] == ["status-led"], (
        "同模块的两件声明被切片丢掉了：模块编译拿到的文档里没有这条支路"
    )
    assert sub_presentation.series_branches[0] == presentation.series_branches[0]


def test_the_module_view_does_not_carry_a_branch_it_cannot_own():
    """跨模块声明不进任何切片——它已经在页面上被 V7 具名拒绝，不是被悄悄丢掉。"""
    circuit, presentation = _documents(
        modules=[_module("mcu", ["U1", "R2"]), _module("panel", ["LED1"])],
        branches=[_branch()],
    )
    for module_id in ("mcu", "panel"):
        module = presentation.module(module_id)
        _sub_circuit, sub_presentation = pc._module_view(
            circuit, presentation, module
        )
        assert sub_presentation.series_branches == [], (
            f"{module_id} 只拥有两件中的一件，声明不该被它携带"
        )
