"""548D3X3B：`panelGroups` 的电路校验，以及 standalone / page 两个消费者。

31 只做了**数据合同**：一组二端支路，写在文档里，解析器保证形状。这一批做
`drawcompiler.validate_panel_groups(circuit, presentation)`——把每条支路放回电路核对：

1. **事实存在**：part / from / to 必须在 `CircuitSpec` 里（`facts-missing`）；
2. **同组同模块**：组内每个件恰好属于一个模块，且全组是同一个模块（`facts-missing`）；
3. **两端不同、两脚两网**：`from != to`，该件电路脚恰好两个、分别落在两端，且没有
   no-connect 脚（`circuit-invalid`，给出真实 pin→net）；
4. **唯一宿主**：在该模块内，`from` 除本支路件外恰好一个脚，且全组解析到同一个宿主件
   （`circuit-invalid`，列出候选、不猜）。

判定顺序就是拒因依赖顺序：拒了一条就不再问依赖它的问题。正例是四个键各接一个 GPIO、
另一脚共 3V3——**同一宿主件 U1、四个不同的宿主脚**（31B/32A 的原文夹具；「全组同一宿主脚」
若按字面读会让这份夹具无法声明，见交卷说明）。本文件聚焦电气/切片校验；33C 的
base/topology 2×2 座位另有专项测试，校验通过不等于整张 LayoutPlan 已通过。
"""

from __future__ import annotations

import copy
import dataclasses

import pytest

import test_053b_drawcompiler as b053

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawcompiler as dc
from boardwise.engines import pagecompiler as pc

PROV = "verified_recipe"
_UNSET = object()
CATEGORIES = ("facts-missing", "circuit-invalid", "layout-unsat", "presentation-poor")
PAGE = pc.PageCompileBudget(page_box=(0.0, 0.0, 1169.0, 826.0))


# ------------------------------------------------------------------ 手写文档
#
# 547A 岛的最小形状（MCU + 去耦 + 上拉 + 四个键 + 两个灯），符号库是本文件自己的
# 最小轮廓：不 import 别人的夹具，避免两批对同一颗件的脚数产生分歧。


def _pin(number: str, tip, direction: str) -> dict:
    return {"number": number, "name": number, "tip": list(tip),
            "direction": direction, "length": 10.0, "pinType": "passive"}


def _symbol(ref: str, body, pins) -> dict:
    return {"kind": "boardwise-symbol-profile", "profileVersion": 1,
            "symbolRef": ref, "title": ref, "body": list(body), "pins": pins,
            "source": "test fixture (548D3X3B)"}


_MCU_LEFT = ["VDD", "VSS", "VBAT", "BOOT0", "PA13", "PA14", "PA5", "PA7"]
_MCU_RIGHT = ["PC6", "PB15", "PB14", "PB13", "PA3", "PA4", "PC0"]


def _profile_payloads() -> dict[str, dict]:
    return {
        "MCU32": _symbol(
            "MCU32", [-70.0, -90.0, 70.0, 90.0],
            [_pin(n, [-80.0, 70 - 10 * i], "left") for i, n in enumerate(_MCU_LEFT)]
            + [_pin(n, [80.0, 40 - 10 * i], "right") for i, n in enumerate(_MCU_RIGHT)],
        ),
        "C": _symbol("C", [-5.5, -8.5, 5.5, 8.5],
                     [_pin("1", [0.0, 20.0], "up"), _pin("2", [0.0, -20.0], "down")]),
        "R": _symbol("R", [-10.5, -4.5, 10.5, 4.5],
                     [_pin("1", [-20.0, 0.0], "left"), _pin("2", [20.0, 0.0], "right")]),
        "KEY": _symbol("KEY", [-12.0, -6.5, 12.0, 6.5],
                       [_pin("1", [0.0, 20.0], "up"), _pin("2", [0.0, -20.0], "down")]),
        "LED": _symbol("LED", [-7.0, -5.5, 7.0, 5.5],
                       [_pin("1", [-20.0, 0.0], "left"), _pin("2", [20.0, 0.0], "right")]),
        "LCD": _symbol("LCD", [-20.0, -30.0, 20.0, 30.0],
                       [_pin("1", [-30.0, 20.0], "left"), _pin("2", [-30.0, 10.0], "left"),
                        _pin("3", [-30.0, 0.0], "left"), _pin("4", [-30.0, -10.0], "left")]),
    }


def _book() -> dict[str, SymbolProfile]:
    return {ref: SymbolProfile.from_dict(copy.deepcopy(payload))
            for ref, payload in _profile_payloads().items()}


def _part(part_id: str, symbol: str, value: str = "") -> dict:
    return {"id": part_id, "symbolRef": symbol, "value": value, "provenance": PROV}


def _net(net_id: str, cls: str, members: list[str]) -> dict:
    return {"id": net_id, "class": cls, "members": list(members),
            "provenance": PROV}


_KEY_PINS = ("PC6", "PB15", "PB14", "PB13")


def _parts() -> list[dict]:
    return (
        [_part("U1", "MCU32", "STM32G431"), _part("C1", "C", "100nF"),
         _part("R1", "R", "10k")]
        + [_part(f"S{i}", "KEY", "KEY") for i in range(1, 5)]
        + [_part("D1", "LED", "red"), _part("D2", "LED", "green")]
    )


def _nets() -> list[dict]:
    rail = ["U1.VDD", "U1.VBAT", "C1.1"] + [f"S{i}.2" for i in range(1, 5)]
    ground = ["U1.VSS", "C1.2", "R1.2", "D1.2", "D2.2"]
    nets = [
        _net("3V3", "power", rail),
        _net("GND", "gnd", ground),
        _net("BOOT0", "signal", ["U1.BOOT0", "R1.1"]),
        _net("LED1", "signal", ["U1.PA3", "D1.1"]),
        _net("LED2", "signal", ["U1.PA4", "D2.1"]),
    ]
    nets += [
        _net(f"KEY{i}", "signal", [f"U1.{pin}", f"S{i}.1"])
        for i, pin in enumerate(_KEY_PINS, start=1)
    ]
    return nets


_MCU_PARTS = ["U1", "C1", "R1", "S1", "S2", "S3", "S4", "D1", "D2"]


def _module(module_id: str = "mcu", parts=None) -> dict:
    payload = {"id": module_id, "parts": list(parts if parts is not None else _MCU_PARTS),
               "role": "host island", "grammarRef": "ic-periphery", "core": "U1"}
    return payload


def _branch(index: int, **overrides) -> dict:
    entry = {"from": f"KEY{index}", "to": "3V3", "part": f"S{index}"}
    entry.update(overrides)
    return entry


def _panel(**overrides) -> dict:
    entry = {
        "id": "keys",
        "side": "bottom",
        "columns": 2,
        "branches": [_branch(index) for index in range(1, 5)],
    }
    entry.update(overrides)
    return entry


def _documents(parts=None, nets=None, modules=None, panels=_UNSET):
    """One circuit and one presentation, hand-written (no library, no compile)."""
    circuit = CircuitSpec.from_dict({
        "parts": copy.deepcopy(parts if parts is not None else _parts()),
        "nets": copy.deepcopy(nets if nets is not None else _nets()),
    })
    payload = {
        "grammarRef": "ic-periphery",
        "modules": copy.deepcopy(modules if modules is not None else [_module()]),
    }
    if panels is not _UNSET:
        payload["panelGroups"] = copy.deepcopy(panels)
    return circuit, PresentationSpec.from_dict(payload)


def _nets_edit(**changes: list[str]) -> list[dict]:
    """The key netlist with named nets' members replaced (one sentence per break)."""
    nets = copy.deepcopy(_nets())
    for net_id, members in changes.items():
        for item in nets:
            if item["id"] == net_id:
                item["members"] = list(members)
                break
        else:  # a new id is appended, so a negative can name a fresh node
            nets.append(_net(net_id, "signal", members))
    return nets


def _validate(circuit, presentation) -> list:
    validate = getattr(dc, "validate_panel_groups", None)
    assert validate is not None, (
        "drawcompiler 没有 validate_panel_groups：32A 的跨文档校验还没有消费者入口"
    )
    answer = validate(circuit, presentation)
    assert isinstance(answer, list)
    for item in answer:
        assert isinstance(item, dc.GrammarFailure)
    return answer


def _text(item) -> str:
    return " ".join(str(x) for x in
                    (item.category, item.subject, item.detail, item.action))


def _assert_refused(refusals, category: str, *tokens: str) -> None:
    same = [item for item in refusals if item.category == category]
    assert same, (f"必须报 {category}；实际 "
                  f"{[(item.category, item.detail) for item in refusals] or '无拒因'}")
    joined = " ".join(_text(item) for item in same)
    missing = [token for token in tokens if token not in joined]
    assert not missing, f"拒因必须点名 {missing}；实际 {joined!r}"


# ================================================================ 1. 正例


def test_a_four_branch_key_panel_on_one_host_is_accepted():
    """四键各接一个 GPIO、另一脚共 3V3：零拒因。"""
    circuit, presentation = _documents(panels=[_panel()])
    assert _validate(circuit, presentation) == []


def test_a_legal_panel_is_seated_as_a_two_by_two_panel():
    """548D3X3C 后：合法 panel 真的排座位——四格 2×2 在宿主本体下方，
    服务座精确移动 C1/R1/D1/D2，其余普通件保持普通布局；最终 route/text/flag 回放属 §34，本项不据此断言整图通过。"""
    book = dict(_book())
    # The terminal is a rail, so the library carries its flag symbol (the cell's
    # terminal flag room is measured from the real `FlagReservation`).
    book["PWR-3V3"] = SymbolProfile(
        symbol_ref="PWR-3V3", title="PWR-3V3", body=(-6.0, 0.0, 6.0, 18.0), pins=[])
    # 548D3S：service 终端的 GND 旗要真实旗形（与 test_548d_panel_base 同一本
    # 053 图元、同一几何），库缺它时所有 variant 都只能拒；断言不动。
    book["PWR-GND"] = b053.flag("PWR-GND")
    circuit, plain = _documents()
    with_panel_circuit, with_panel = _documents(panels=[_panel()])

    def placement_of(target_circuit, presentation):
        binding = dc.bind_grammar(target_circuit, presentation, book)
        assert binding.ok, [item.detail for item in binding.failures]
        binding = dc._with_panel_groups(binding, presentation, target_circuit)
        prepared = dc._prepare(
            target_circuit, presentation, binding, book,
            dc.CompileBudget(max_candidates=4),
        )
        assert prepared.context is not None, [f.detail for f in prepared.failures]
        ctx = prepared.context
        for variant in dc._variants(ctx):
            placed, failure = dc._place_chain_and_shelf(ctx, variant)
            if failure is None:
                return placed, None
        raise AssertionError("no ladder variant placed the module")

    control, _ = placement_of(circuit, plain)
    declared, _ = placement_of(with_panel_circuit, with_panel)
    cells = {f"S{index}" for index in range(1, 5)}
    # 548D3S2/§35C：服务座是**声明**的座位，不是"普通布局被悄悄搬动"。先把声明的
    # 服务件集合钉死（四支路恰为 C1/R1/D1/D2 且都 seated），再只对真正的普通件
    # 逐件比较——不跳过服务件以外的任何件，也不放宽 2×2/宿主关系断言。
    service_parts = {
        cell.part_id for plan in declared.service_plans for cell in plan.cells
    }
    assert service_parts == {"C1", "R1", "D1", "D2"}, service_parts
    for plan in declared.service_plans:
        assert plan.seated, plan.refusal.render() if plan.refusal else ""
    for part_id, origin in control.origins.items():
        if part_id in cells or part_id in service_parts:
            continue
        assert declared.origins[part_id] == origin, (
            f"the panel seat moved the ordinary part {part_id}")
    assert declared.panel_plans and all(plan.seated for plan in declared.panel_plans)
    assert declared.panel_plans[0].mismatches(declared.origins, declared.poses) == ()

    host = declared.origins["U1"]
    xs = sorted({declared.origins[cell][0] for cell in cells})
    ys = sorted({declared.origins[cell][1] for cell in cells})
    assert len(xs) == 2 and len(ys) == 2, (xs, ys)
    for value in xs:
        assert sum(1 for cell in cells if declared.origins[cell][0] == value) == 2
    for value in ys:
        assert sum(1 for cell in cells if declared.origins[cell][1] == value) == 2
    assert all(declared.origins[cell][1] < host[1] for cell in cells), (
        "the panel cells are not below the host origin")


# ================================================== 2. 页面切片：整组携带


def _page_documents(panels=_UNSET, modules=None):
    """The MCU island plus one satellite module, so a slice has something to drop."""
    parts = _parts() + [_part("J1", "LCD", "ST7789")]
    nets = _nets() + [
        _net("LCD_SCK", "signal", ["U1.PA5", "J1.1"]),
        _net("LCD_SDA", "signal", ["U1.PA7", "J1.2"]),
    ]
    payload_modules = [
        _module("mcu", _MCU_PARTS + []),
        {"id": "lcd", "parts": ["J1"], "role": "lcd", "grammarRef": "ic-periphery",
         "core": "J1"},
    ] if modules is None else modules
    return _documents(parts=parts, nets=nets, modules=payload_modules, panels=panels)


def test_the_page_slice_carries_the_whole_group_to_its_owning_module_only():
    circuit, presentation = _page_documents(panels=[_panel()])
    mcu_circuit, mcu_view = pc._module_view(  # noqa: SLF001 - the slice under test
        circuit, presentation, presentation.module("mcu"))
    lcd_circuit, lcd_view = pc._module_view(  # noqa: SLF001
        circuit, presentation, presentation.module("lcd"))

    assert len(mcu_view.panel_groups) == 1
    assert lcd_view.panel_groups == [], (
        "a module owning none of the group's parts must not carry the group")
    kept = mcu_view.panel_groups[0]
    stated = presentation.panel_groups[0]
    assert (kept.id, kept.side, kept.columns) == (
        stated.id, stated.side, stated.columns)
    assert [
        (branch.from_net, branch.to_net, branch.part) for branch in kept.branches
    ] == [
        (branch.from_net, branch.to_net, branch.part) for branch in stated.branches
    ], "the slice and the document must state the same branches in the same order"
    # The slice is a document of its own: the same group validates against the
    # module-local circuit, and the local host feet are the same three pins.
    assert _validate(mcu_circuit, mcu_view) == []


def test_a_page_compile_of_a_legal_panel_reports_no_panel_refusal():
    circuit, presentation = _page_documents(panels=[_panel()])
    result = pc.compile_page(circuit, presentation, _book(), PAGE)
    assert all("panelGroups" not in failure.detail for failure in result.failures), (
        [failure.detail for failure in result.failures])


# ============================================ 3. 负例：在 bind/placement 之前退出


def _negative_documents(spec: dict):
    parts = spec.get("parts")
    nets = spec.get("nets")
    modules = spec.get("modules")
    panels = spec.get("panels", [_panel()])
    circuit = CircuitSpec.from_dict({
        "parts": copy.deepcopy(parts if parts is not None else _parts()),
        "nets": copy.deepcopy(nets if nets is not None else _nets()),
        **({"nc": copy.deepcopy(spec["nc"])} if "nc" in spec else {}),
    })
    payload = {
        "grammarRef": "ic-periphery",
        "modules": copy.deepcopy(modules if modules is not None else [_module()]),
        "panelGroups": copy.deepcopy(panels),
    }
    presentation = PresentationSpec.from_dict(payload)
    if "replace" in spec:
        presentation = spec["replace"](presentation)
    return circuit, presentation


def _four(first: dict) -> list[dict]:
    """The key panel with its first branch replaced and the rest untouched."""
    return [first] + [_branch(index) for index in range(2, 5)]


def _negative_cases():
    """Every refusal shape, each changing one fact of the legal four-key panel."""
    mcu_and_lcd = [
        _module("mcu", [p for p in _MCU_PARTS if p != "S4"]),
        {"id": "lcd", "parts": ["J1", "S4"], "role": "lcd",
         "grammarRef": "ic-periphery", "core": "J1"},
    ]
    cases = {
        "unknown-part": (
            # The parser refuses a panel part no module declares, so the part is
            # declared by a module and left out of the circuit: exactly the
            # "declaration cannot create a connection" case.
            dict(
                modules=[_module("mcu", _MCU_PARTS + ["S9"])],
                panels=[_panel(branches=_four(_branch(1, part="S9")))],
            ),
            ("facts-missing", "'S9'"),
        ),
        "unknown-net": (
            dict(panels=[_panel(branches=_four(_branch(1, **{"to": "NOPE"})))]),
            ("facts-missing", "'NOPE'"),
        ),
        "part-in-no-module": (
            # Parsed with S3 declared, then the module drops it: the panel still
            # names it, which is the document a page slice must not read.
            dict(
                panels=[_panel()],
                replace=lambda spec: dataclasses.replace(
                    spec, modules=[dataclasses.replace(
                        spec.modules[0],
                        parts=[p for p in spec.modules[0].parts if p != "S3"],
                    )]),
            ),
            ("facts-missing", "S3", "no module"),
        ),
        "cross-module": (
            dict(
                parts=_parts() + [_part("J1", "LCD", "ST7789")],
                nets=_nets() + [
                    _net("LCD_SCK", "signal", ["U1.PA5", "J1.1"]),
                    _net("LCD_SDA", "signal", ["U1.PA7", "J1.2"]),
                ],
                modules=mcu_and_lcd,
            ),
            ("facts-missing", "spans modules", "lcd"),
        ),
        "duplicate-part-across-groups": (
            dict(
                panels=[_panel()],
                # The parser refuses this shape (548D3X3A), so the document is
                # built as a hand-written one: a consumer must still not read the
                # same part as two panel cells.
                replace=lambda spec: dataclasses.replace(
                    spec, panel_groups=[*spec.panel_groups, *spec.panel_groups]),
            ),
            ("circuit-invalid", "panelGroups ['keys']", "S1"),
        ),
        "from-equals-to": (
            dict(panels=[_panel(branches=_four(_branch(1, **{"to": "KEY1"})))]),
            ("circuit-invalid", "KEY1", "same net"),
        ),
        "three-foot-part": (
            dict(panels=[_panel(branches=_four(_branch(1, part="U1")))]),
            ("circuit-invalid", "U1", "pin(s)"),
        ),
        "third-net": (
            dict(
                nets=_nets_edit(
                    **{"3V3": ["U1.VDD", "U1.VBAT", "C1.1", "S1.2", "S3.2", "S4.2"],
                       "BOOT0": ["U1.BOOT0", "R1.1", "S2.2"]},
                ),
            ),
            ("circuit-invalid", "S2", "KEY2"),
        ),
        "both-feet-one-net": (
            dict(
                nets=_nets_edit(
                    **{"3V3": ["U1.VDD", "U1.VBAT", "C1.1", "S2.2", "S3.2",
                               "S4.2"],
                       "KEY1": ["U1.PC6", "S1.1", "S1.2"]},
                ),
            ),
            ("circuit-invalid", "S1", "both feet on one net"),
        ),
        "no-connect-foot": (
            # A three-foot device whose extra foot is declared unconnected: the
            # partition shows the part with two feet, so only the circuit's own
            # `nc` list can tell this is not a two-terminal panel cell.
            dict(panels=[_panel()], nc=[{"pin": "S1.3", "provenance": PROV}]),
            ("circuit-invalid", "S1.3", "no-connect"),
        ),
        "no-host": (
            dict(nets=_nets_edit(**{"KEY1": ["S1.1"]})),
            ("circuit-invalid", "KEY1", "host foot"),
        ),
        "two-hosts": (
            dict(nets=_nets_edit(**{
                "KEY1": ["U1.PC6", "U1.PA13", "S1.1"],
            })),
            ("circuit-invalid", "U1.PC6", "U1.PA13"),
        ),
        "host-is-another-panel-part": (
            dict(
                nets=_nets_edit(**{
                    "KEY1": ["U1.PC6"],
                    "KEY2": ["U1.PB15"],
                    "KEYX": ["S1.1", "S2.1"],
                }),
                panels=[_panel(branches=[
                    _branch(1, **{"from": "KEYX"}),
                    _branch(2, **{"from": "KEYX"}),
                    _branch(3),
                    _branch(4),
                ])],
            ),
            ("circuit-invalid", "S2.1", "another part"),
        ),
        "two-host-parts": (
            dict(nets=_nets_edit(**{
                "KEY2": ["R1.1", "S2.1"], "BOOT0": ["U1.BOOT0"],
            })),
            ("circuit-invalid", "R1.1", "host part"),
        ),
    }
    return cases


@pytest.mark.parametrize("name", sorted(_negative_cases()))
def test_every_negative_is_refused_before_the_grammar_is_bound(name, monkeypatch):
    spec, (category, *tokens) = _negative_cases()[name]
    circuit, presentation = _negative_documents(spec)
    refusals = _validate(circuit, presentation)
    _assert_refused(refusals, category, *tokens)

    calls = {"bind": 0}

    def spy(*args, **kwargs):
        calls["bind"] += 1
        raise AssertionError("the grammar was bound for a refused panel")

    monkeypatch.setattr(dc, "bind_grammar", spy)
    result = dc.compile(circuit, presentation, _book())
    assert not result.ok and result.candidates == [], name
    assert calls["bind"] == 0, f"{name}: the refusal came after the grammar bind"
    assert {item.category for item in result.failures} <= set(CATEGORIES)


@pytest.mark.parametrize("name", sorted(_negative_cases()))
def test_the_page_refuses_the_same_declaration_before_any_module_is_compiled(
    name, monkeypatch,
):
    spec, (category, *tokens) = _negative_cases()[name]
    circuit, presentation = _negative_documents(spec)
    calls = {"modules": 0}

    def spy(*args, **kwargs):
        calls["modules"] += 1
        raise AssertionError("a module was compiled for a refused panel")

    monkeypatch.setattr(pc, "_compile_modules", spy)  # noqa: SLF001
    result = pc.compile_page(circuit, presentation, _book(), PAGE)
    assert not result.ok and result.pages == [], name
    assert calls["modules"] == 0, f"{name}: the page compiled before refusing"
    _assert_refused(result.failures, category, *tokens)


# ============================================= 4. 缺省 / [] / 轻量旧 presentation


def test_a_document_without_the_key_reads_as_no_panel():
    circuit, presentation = _documents()
    assert _validate(circuit, presentation) == []
    assert presentation.panel_groups == []
    assert "panelGroups" not in presentation.to_jsonable()


def test_an_explicit_empty_list_is_the_same_statement():
    circuit, empty = _documents(panels=[])
    plain_circuit, plain = _documents()
    assert _validate(circuit, empty) == []
    control = dc.compile(plain_circuit, plain, _book())
    declared = dc.compile(circuit, empty, _book())
    assert control.ok and declared.ok
    assert len(declared.candidates) == len(control.candidates)


def test_a_lightweight_presentation_without_the_attribute_is_not_broken():
    """`getattr(..., 'panel_groups', ())`：没有这个属性的旧对象照样返回空表。"""
    from types import SimpleNamespace

    circuit, _ = _documents()
    stub = SimpleNamespace(modules=[], series_branches=())
    assert _validate(circuit, stub) == []
