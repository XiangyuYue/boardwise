"""548R2：长位号岛（548C B1）的正向回归与未改名基线的零移动。

548C 的 B1 变体只换表面：把 547A 岛内每个器件的位号换成 12–16 字符的长位号，
电气、值行、网名与符号一概不动。它的第一次测量是 **0 候选**，拒因是文字座椅把
器件的 value 行放进 `LCD_SCK` 标签即将占下的车道：

    [text-overlap] texts[7] 'LED' [113.5,51,137.5,60]
                 × labels[10] 'LCD_SCK' [92,50.5,147,59.5]

548C4 给文字座椅加了一条**有界**的重座椅梯子（`drawcompiler.TEXT_LABEL_REPAIR_ROUNDS`，
只补闸自己点名的 `texts[i] × labels[j]` 盒），B1 随后 `ok=True`、1 候选。548R 的
两次独立变异证明既有聚焦测试抓不住这条回退（把该常量置 0，B1 回到 0 候选，而
82 条聚焦仍全绿），所以这里把它钉成永久回归。

输入只用 `test_547_repeated_shunts` 的内联 547A 夹具：先按 548C 的 `LONG_IDS`
改长位号（映射与 `evidence/548C/variants/build_variants.py` 同表，这里**内联**，
测试运行不读 `evidence/`），再取 `pagecompiler._module_view` 的 mcu 单岛视图，
用真实 `drawcompiler.compile` 编译。没有人工几何、没有 `userLocks`、没有任何
元件坐标；值行、网名、符号、网表与基线逐字相同。

钉住的是：B1 的 `ok`、候选数、几何指纹、hard violation 数、独立重推的电气连通
（26 网各一个节点、0 短路、0 未放置）、长位号与值行**整行印出**；以及未改名
基线仍然编译成**原来的几何指纹**（证明这条修复对不相撞的页面零移动）。
不钉：页层拼装、视觉可读性、真机——这些不在本文件的证据范围内。
"""

from __future__ import annotations

import copy
from collections import Counter

import test_547_repeated_shunts as m547

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawcompiler as dc
from boardwise.engines import pagecompiler as pc
from boardwise.engines import readability as rd

#: 548C B1's surface change, verbatim from
#: ``evidence/548C/variants/build_variants.py`` (``LONG_IDS``). Inlined on
#: purpose: a test may not depend on ignored evidence to run.
LONG_IDS = {
    "U1": "MCU_HOST_U1",
    "C1": "DECOUPLE_3V3_1",
    "R1": "BOOT0_PULLDOWN_1",
    "S1": "SW_PUSH_KEY_1",
    "S2": "SW_PUSH_KEY_2",
    "S3": "SW_PUSH_KEY_3",
    "S4": "SW_PUSH_KEY_4",
    "D1": "LED_STATUS_1",
    "D2": "LED_STATUS_2",
    "BZ1": "BEEP_DRIVER_1",
    "J1": "LCD_HEADER_1",
    "J2": "WIFI_HEADER_1",
    "J3": "UART_HEADER_1",
    "J4": "SWD_HEADER_1",
    "U2": "ENV_SENSOR_1",
    "U3": "BMP_SENSOR_1",
    "C2": "DECOUPLE_ESP_1",
    "C3": "DECOUPLE_ENV_1",
    "C4": "DECOUPLE_BMP_1",
    "R2": "ESP_EN_PULLUP_1",
    "R3": "ESP_RST_PULLUP_1",
}

#: The 547A mcu module view as this worktree measures it. Both fingerprints were
#: read off the real compiler, never transcribed from a report: the baseline is
#: what `test_547_repeated_shunts` draws today, and B1 is the same island after
#: only the designators got long.
BASELINE_GEOMETRY = (
    "b71fcbcf21ce4584a8f6cb982b1d6a47235d4137aed8da7d1eb48942f5815d9d"
)
LONG_GEOMETRY = (
    "868cc95b5570e55a0b7292edd3b5a71ac59ee7f4589ded1524382882735127fa"
)

#: The island's own size, stated so a silent input drift (a part dropped by the
#: module view, a net that lost its members) fails here and not as a puzzle.
ISLAND_PARTS = 10
ISLAND_NETS = 26


def _profiles():
    return {
        profile.symbol_ref: profile
        for profile in (
            SymbolProfile.from_dict(copy.deepcopy(payload))
            for payload in m547._profiles().values()
        )
    }


def _rename_parts(circuit: dict, presentation: dict, mapping: dict) -> None:
    """Rename parts everywhere this fixture speaks a part id (in place).

    The same four places `build_variants._rename_ids` writes: the part list,
    every net member, the no-connect declarations (this fixture has none) and
    the presentation's module membership plus `core`.
    """
    for part in circuit["parts"]:
        part["id"] = mapping.get(part["id"], part["id"])
    for net in circuit["nets"]:
        members = []
        for member in net["members"]:
            prefix, sep, pin = member.partition(".")
            members.append(mapping.get(prefix, prefix) + sep + pin)
        net["members"] = members
    for item in circuit.get("nc") or []:
        prefix, sep, pin = item["pin"].partition(".")
        item["pin"] = mapping.get(prefix, prefix) + sep + pin
    for module in presentation["modules"]:
        module["parts"] = [mapping.get(part, part) for part in module["parts"]]
        if module.get("core"):
            module["core"] = mapping.get(module["core"], module["core"])


def _module_view(circuit_payload: dict, presentation_payload: dict):
    """The 547A mcu island, compiled the way the page's own module view is."""
    circuit = CircuitSpec.from_dict(copy.deepcopy(circuit_payload))
    presentation = PresentationSpec.from_dict(copy.deepcopy(presentation_payload))
    return pc._module_view(circuit, presentation, presentation.module("mcu"))


_CACHE: dict[bool, tuple] = {}


def _island(long_designators: bool):
    """``(result, circuit, presentation, book)`` for the 547A mcu island.

    Compiled once per surface and cached: both are deterministic pure functions
    of the documents, and the whole file then costs two compiles instead of six.
    """
    if long_designators not in _CACHE:
        circuit_payload = copy.deepcopy(m547._circuit())
        presentation_payload = copy.deepcopy(m547._presentation())
        if long_designators:
            _rename_parts(circuit_payload, presentation_payload, LONG_IDS)
        circuit, presentation = _module_view(circuit_payload, presentation_payload)
        book = _profiles()
        _CACHE[long_designators] = (
            dc.compile(circuit, presentation, book), circuit, presentation, book,
        )
    return _CACHE[long_designators]


def _drawn_netlist(spec, plan, book):
    """What the picture's own geometry makes of the spec's nets.

    ``readability.derive_netlist`` reads wires, labels, flags and pin tips and
    consults no spec, so agreeing with it is evidence about the drawing: every
    declared net lands on exactly one node, no node carries two nets, and no
    declared pin is missing from the drawing.
    """
    derived = rd.derive_netlist(plan, book)
    split: dict[str, int] = {}
    undrawn: list[str] = []
    node_nets: dict[tuple, set[str]] = {}
    for net in spec.nets:
        nodes: list[tuple] = []
        for pin in net.members:
            node = derived.group_of(pin)
            if not node:
                undrawn.append(pin)
                continue
            if node not in nodes:
                nodes.append(node)
            node_nets.setdefault(node, set()).add(net.id)
        split[net.id] = len(nodes)
    shorts = {
        node: sorted(names) for node, names in node_nets.items() if len(names) > 1
    }
    return derived, split, undrawn, shorts


def test_the_long_designator_island_draws_one_candidate():
    """B1's contract: a legal candidate, and the exact geometry this worktree
    draws for it. The designators are the only surface that moved."""
    result, spec, _presentation, _book = _island(True)

    assert result.ok, result.render_failures()
    assert result.failures == []
    assert len(result.candidates) == 1, (
        f"B1 drew {len(result.candidates)} candidates; the measured page is one")
    plan = result.candidates[0]
    assert plan.geometry_sha256() == LONG_GEOMETRY, (
        "B1's geometry moved: " + plan.geometry_sha256())

    assert len(spec.parts) == ISLAND_PARTS
    assert len(spec.nets) == ISLAND_NETS
    assert sorted(part.id for part in spec.parts) == sorted(LONG_IDS[p]
                                                            for p in m547._MCU_PARTS)
    assert min(len(part.id) for part in spec.parts) > 10
    for part in ("SW_PUSH_KEY_1", "SW_PUSH_KEY_4", "LED_STATUS_1", "LED_STATUS_2",
                 "BEEP_DRIVER_1", "MCU_HOST_U1"):
        assert plan.part(part) is not None, f"{part} is not placed"


def test_the_long_designator_island_keeps_the_netlist_and_the_gate():
    """The surface change must not buy a candidate with a broken drawing: the
    gate has no hard violation and the picture's own netlist is the spec's."""
    result, spec, presentation, book = _island(True)
    assert result.ok, result.render_failures()
    plan = result.candidates[0]

    checked = rd.check(plan, spec, presentation, book)
    assert [item.render() for item in checked.hard_violations] == []
    assert checked.ok

    derived, split, undrawn, shorts = _drawn_netlist(spec, plan, book)
    assert undrawn == []
    assert {net: count for net, count in split.items() if count != 1} == {}
    assert shorts == {}
    assert len(split) == ISLAND_NETS

    # The 547A trigger's own reading survives the rename: four KEY branches onto
    # four different GPIO pads are four different nodes, and each switch's
    # return pin is *not* on its own key node.
    keys = {}
    for i, pin in enumerate(["PC6", "PB15", "PB14", "PB13"], start=1):
        here = derived.group_of(f"MCU_HOST_U1.{pin}")
        there = derived.group_of(f"SW_PUSH_KEY_{i}.1")
        assert here and there and here == there, f"KEY{i} is not drawn as one node"
        back = derived.group_of(f"SW_PUSH_KEY_{i}.2")
        assert back and back != here, f"KEY{i}'s return pin sits on its key node"
        keys[f"KEY{i}"] = here
    assert len(set(keys.values())) == 4, (
        "the four KEY nets were drawn as one or more merged nodes: " + repr(keys))


def test_every_long_designator_and_value_row_is_printed_whole():
    """No shortening, abbreviation, wrapping or hiding: the printed rows are
    exactly one reference row per part and exactly the spec's value rows."""
    result, spec, _presentation, _book = _island(True)
    assert result.ok, result.render_failures()
    plan = result.candidates[0]

    references = [text.text for text in plan.texts if text.kind == "reference"]
    values = [text.text for text in plan.texts if text.kind == "value"]
    assert Counter(references) == Counter(part.id for part in spec.parts), (
        "the reference rows are not the parts' own long designators: "
        + repr(references))
    assert Counter(values) == Counter(part.value for part in spec.parts if part.value), (
        "the value rows are not the spec's value lines: " + repr(values))
    assert len(references) == ISLAND_PARTS
    assert len(values) == ISLAND_PARTS

    printed = {text.text for text in plan.texts}
    printed |= {label.text for label in plan.labels}
    printed |= {symbol.text for symbol in plan.power_symbols
                if getattr(symbol, "text", "")}
    missing = [part.id for part in spec.parts if part.id not in printed]
    missing += [part.value for part in spec.parts
                if part.value and part.value not in printed]
    assert missing == [], f"rows the drawing never prints whole: {missing}"


def test_the_unrenamed_island_has_not_moved():
    """The repair is structural, so the page that never collides is byte-for-byte
    the drawing it was: same candidate, same geometry as before 548C4."""
    result, spec, _presentation, _book = _island(False)
    assert result.ok, result.render_failures()
    assert len(result.candidates) == 1
    plan = result.candidates[0]
    assert plan.geometry_sha256() == BASELINE_GEOMETRY, (
        "the unrenamed 547A island moved: " + plan.geometry_sha256())
    assert plan.geometry_sha256() != LONG_GEOMETRY
    assert sorted(part.id for part in spec.parts) == sorted(m547._MCU_PARTS)
