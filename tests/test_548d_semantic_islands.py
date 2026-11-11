"""548D3B7：KEY / LED 各自独立功能岛的**合同**（共同电源回路＋纵向阅读）。

任务书：`evidence/548D/service-seat/coreless-bank-charter.md`；语义规格
`evidence/548D/service-seat/semantic-islands-spec.json`。本文件只钉两件事：

* **语义规格**（`semantic-islands-spec.json` 同一份）：`mcu` / `keys` / `led` 三岛，
  没有坐标、没有 `userLocks`、没有 `panelGroups`；`keys` 在模块 `presentation` 里声明
  `power/right + output/left`，`led` 声明 `gnd/right + output/left`——共同回流的
  **阅读方向是文档声明的**，不是解释器猜的；
* **画出来的图**：`keys` 四条支路回到同一根 3V3（`rail`，不是 `gnd`），四个按键同向、
  纵向等节距、公共端同 x、名字各贴本支路；`led` 两条支路回到同一根 GND，同样的纵向读法。
  三岛页逐脚分区、页闸全过，跨岛只有名字没有导线；共同电源被拆成两根不同轨的组
  **不得**被当成一个 bank；旧 GND 路径（CH34 出货页）的几何摘要逐字节不变。

夹具：电路用 `test_548d_panel_validation` 的冻结 `_parts()/_nets()`（本文件不新增器件、
不改网），符号库同它的 `_book()` 加两枚旗标。全程离线。

**本批实测**（`drawcompiler.py=45a9370c…`、`grammar/ic_periphery.py=09f30507…`）：
11 条全绿，没有 xfail——G1（共同电源回路）与 G2（名字联合选档）在真实编译里都已经成立，
按 `coreless-bank-charter.md` 的规矩摘除标记，而不是留着「两边都能过」。生产这两个文件
在本批期间由另一条线改动，若它们的 hash 变了，读数以本文件重新跑出来的为准。
"""

from __future__ import annotations

import copy
import dataclasses

import pytest

import test_053b_drawcompiler as b053
import test_548d_panel_validation as p32

from boardwise.core.geometry import transform_point
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawcompiler as dc
from boardwise.engines import pagecompiler as pc
from boardwise.engines import readability

PAGE = pc.PageCompileBudget(page_box=(0.0, 0.0, 1169.0, 826.0))
PAGE_PARTS = ("U1", "C1", "R1", "D1", "D2")
KEY_PARTS = tuple(f"S{index}" for index in range(1, 5))
#: The two island readings the document states: the common return on the right,
#: the signal the branch holds on the left.  A bank without these keys keeps the
#: old horizontal row (the default is top/bottom, unchanged).
KEY_SIDES = {"power": "right", "output": "left"}
LED_SIDES = {"gnd": "right", "output": "left"}


def _book() -> dict[str, SymbolProfile]:
    book = dict(p32._book())
    book["PWR-3V3"] = SymbolProfile(
        symbol_ref="PWR-3V3", title="PWR-3V3", body=(-6.0, 0.0, 6.0, 18.0), pins=[])
    book["PWR-GND"] = b053.flag("PWR-GND")
    return book


def _circuit():
    return p32.CircuitSpec.from_dict({
        "parts": copy.deepcopy(p32._parts()),
        "nets": copy.deepcopy(p32._nets()),
    })


def _slice(circuit, keep):
    """The page's sub-circuit: the kept parts and the nets they still touch."""
    parts = [p for p in circuit.parts if p.id in set(keep)]
    nets = []
    for net in circuit.nets:
        members = [m for m in net.members if m.split(".")[0] in set(keep)]
        if members:
            nets.append({"id": net.id, "class": net.cls, "members": members,
                         "provenance": "verified_recipe"})
    return p32.CircuitSpec.from_dict({
        "parts": [{"id": p.id, "symbolRef": p.symbol_ref, "value": p.value,
                   "provenance": "verified_recipe"} for p in parts],
        "nets": nets,
    })


def _module(module_id, parts, role, sides=None, core=None) -> dict:
    """One module: semantics plus the reading direction the document states."""
    body = {"id": module_id, "parts": list(parts), "role": role,
            "grammarRef": "ic-periphery"}
    if core:
        body["core"] = core
    if sides:
        body["presentation"] = {"sidePreferences": dict(sides)}
    return body


def _island_spec():
    """The three semantic islands: semantics only, no coordinates anywhere."""
    return PresentationSpec.from_dict({
        "grammarRef": "ic-periphery",
        "modules": [
            _module("mcu", ["U1", "C1", "R1"], "host island", core="U1"),
            _module("keys", KEY_PARTS, "key inputs", KEY_SIDES),
            _module("led", ["D1", "D2"], "indicators", LED_SIDES),
        ],
        "moduleOrder": ["mcu", "keys", "led"],
        "flow": [{"from": "mcu", "to": "keys"}, {"from": "mcu", "to": "led"}],
        # The explicit construction intent (§17): local service seats, one
        # 30-unit interval. It is a statement, not a coordinate.
        "serviceLayout": {"pinGap": 30, "localSeats": True},
    })


def _led_ledger():
    return _slice(_circuit(), ("D1", "D2"))


def _keys_ledger():
    return _slice(_circuit(), KEY_PARTS)


def _led_spec():
    return PresentationSpec.from_dict({
        "grammarRef": "ic-periphery",
        "modules": [_module("led", ["D1", "D2"], "indicators", LED_SIDES)]})


def _keys_spec():
    return PresentationSpec.from_dict({
        "grammarRef": "ic-periphery",
        "modules": [_module("keys", KEY_PARTS, "key inputs", KEY_SIDES)]})


def _page():
    """The mcu + led page: the two islands production already draws together."""
    board = _slice(_circuit(), PAGE_PARTS)
    spec = PresentationSpec.from_dict({
        "grammarRef": "ic-periphery",
        "modules": [
            _module("mcu", ["U1", "C1", "R1"], "host island", core="U1"),
            _module("led", ["D1", "D2"], "indicators", LED_SIDES),
        ],
        "moduleOrder": ["mcu", "led"],
        "flow": [{"from": "mcu", "to": "led"}],
        "serviceLayout": {"pinGap": 30, "localSeats": True},
    })
    return board, spec, pc.compile_page(board, spec, _book(), PAGE)


def _per_pin_problems(plan, board, book):
    """The independent reading: every pin belongs to the net the circuit states."""
    derived = readability.derive_netlist(plan, book)
    return [
        {"net": net.id, "pin": member, "expected": tuple(sorted(net.members)),
         "actual": derived.pin_group.get(member)}
        for net in board.nets for member in net.members
        if derived.pin_group.get(member) != tuple(sorted(net.members))
    ]


def _pin_at(part, number):
    """Where one pin of a placed part lands, posed by the plan's own transform."""
    profile = _book()[part.symbol_ref]
    pin = next(item for item in profile.pins if item.number == number)
    return transform_point(pin.tip[0], pin.tip[1], rotation=part.rotation,
                           mirror=part.mirror, ox=part.x, oy=part.y)


def _names_on_pins(plan, board):
    """The independent reading: which name is printed at each circuit pin.

    Reads only the plan's geometry and the frozen circuit — no compiler state —
    so a name moved onto the wrong branch is visible as a pin whose printed name
    is not the net the circuit states for it.
    """
    tips = {}
    for part in plan.parts:
        for pin in _book()[part.symbol_ref].pins:
            x, y = _pin_at(part, pin.number)
            tips[(round(x, 1), round(y, 1))] = f"{part.part_id}.{pin.number}"
    printed = {}
    for label in plan.labels:
        key = (round(label.x, 1), round(label.y, 1))
        if key in tips:
            printed[tips[key]] = label.net
    stated = {member: net.id for net in board.nets for member in net.members}
    return printed, stated


def _misnamed(plan, board):
    printed, stated = _names_on_pins(plan, board)
    return {pin: {"printed": name, "stated": stated.get(pin)}
            for pin, name in printed.items() if stated.get(pin) != name}


def _label_offsets(plan, pairs):
    """``{net: (part_id, dx, dy, distance)}`` — box centre against its own pin."""
    parts = {part.part_id: part for part in plan.parts}
    out = {}
    for net, part_id in pairs:
        placed = next(item for item in plan.labels if item.net == net)
        tip = _pin_at(parts[part_id], "1")
        centre = ((placed.bbox[0] + placed.bbox[2]) / 2,
                  (placed.bbox[1] + placed.bbox[3]) / 2)
        out[net] = (placed.part_id,
                    round(centre[0] - tip[0], 1), round(centre[1] - tip[1], 1),
                    round(centre[0] - tip[0], 1) ** 2
                    + round(centre[1] - tip[1], 1) ** 2)
    return out


def _nearest_owner(plan, nets_to_parts):
    """For each named net, is the closest pin of all the branches its own pin?"""
    parts = {part.part_id: part for part in plan.parts}
    tips = {part_id: _pin_at(parts[part_id], "1") for part_id in nets_to_parts.values()}
    wrong = {}
    for net, part_id in nets_to_parts.items():
        placed = next(item for item in plan.labels if item.net == net)
        centre = ((placed.bbox[0] + placed.bbox[2]) / 2,
                  (placed.bbox[1] + placed.bbox[3]) / 2)
        distances = {owner: (centre[0] - x) ** 2 + (centre[1] - y) ** 2
                     for owner, (x, y) in tips.items()}
        nearest = min(distances, key=distances.get)
        if nearest != part_id:
            wrong[net] = {"nearest": nearest, "stated": part_id}
    return wrong


def _pose(part):
    return (part.rotation, part.mirror)


def _pitch(values):
    """The gap between neighbours: one number only when they are equal."""
    gaps = {round(b - a, 6) for a, b in zip(values, values[1:])}
    return gaps.pop() if len(gaps) == 1 else None


# ----------------------------------------------------------- 1. 语义规格本身


def test_the_island_spec_states_semantics_only():
    spec = _island_spec()
    payload = spec.to_jsonable()
    assert [module["id"] for module in payload["modules"]] == ["mcu", "keys", "led"]
    assert payload["moduleOrder"] == ["mcu", "keys", "led"]
    assert payload["userLocks"] == []
    assert "panelGroups" not in payload
    # 548D3C1: the page states one construction intent and nothing positional.
    assert payload["serviceLayout"] == {"pinGap": 30, "localSeats": True}
    assert set(payload["serviceLayout"]) == {"pinGap", "localSeats"}
    for key in ("x", "y", "rotation", "points", "segments"):
        assert key not in payload
    stated = sorted(part for module in payload["modules"] for part in module["parts"])
    assert stated == sorted(p32._MCU_PARTS), (
        "the three islands must cover the frozen circuit's parts exactly once")
    # The reading direction is stated by the document, per island: keys read the
    # 3V3 rail on the right, led reads GND on the right, both hold their signal
    # on the left.  Nothing here is a coordinate.
    sides = {module["id"]: module.get("presentation", {}).get("sidePreferences")
             for module in payload["modules"]}
    assert sides["keys"] == {"power": "right", "output": "left"}
    assert sides["led"] == {"gnd": "right", "output": "left"}
    assert sides["mcu"] is None, "the host island states no override"


def test_the_document_on_disk_says_the_same_thing():
    """The evidence spec is the same document, not a different one."""
    from pathlib import Path

    path = (Path(__file__).resolve().parents[1]
            / "evidence" / "548D" / "service-seat" / "semantic-islands-spec.json")
    on_disk = PresentationSpec.load(path)
    mine = _island_spec().to_jsonable()
    assert on_disk.to_jsonable()["modules"] == mine["modules"]
    assert on_disk.to_jsonable()["serviceLayout"] == mine["serviceLayout"]


# ------------------------------------------- 2. 生产能画的两岛：自动、逐脚、页闸


def test_the_mcu_and_led_islands_are_drawn_automatically_and_every_pin_lands():
    board, spec, result = _page()
    assert result.ok, result.render_failures()
    page = result.best()
    assert _per_pin_problems(page.plan, board, _book()) == []
    assert readability.check_page(page, board, spec, _book()).hard_violations == []
    assert not [item for item in page.plan.segments
                if item.net in ("LED1", "LED2")], (
        "a cross-island signal is named at each end, never drawn as a page wire")
    named = [item.net for item in page.plan.labels]
    assert named.count("LED1") == 2 and named.count("LED2") == 2, named


def test_the_led_pair_shares_pose_and_each_name_anchors_on_its_own_pin():
    result = dc.compile(_led_ledger(), _led_spec(), _book(),
                        dc.CompileBudget(max_candidates=8))
    assert result.ok, result.render_failures()
    plan = result.candidates[0]
    parts = {part.part_id: part for part in plan.parts}
    assert _pose(parts["D1"]) == _pose(parts["D2"]), "the two branches share a pose"
    for label, part_id in (("LED1", "D1"), ("LED2", "D2")):
        placed = next(item for item in plan.labels if item.net == label)
        assert placed.part_id == part_id
        assert (placed.x, placed.y) == _pin_at(parts[part_id], "1"), (
            f"{label} is anchored off its own input pin")
    assert _nearest_owner(plan, {"LED1": "D1", "LED2": "D2"}) == {}


def test_the_led_bank_stacks_vertically_on_the_common_return_side():
    """`gnd/right + output/left`: branches along y, common ends on one x."""
    result = dc.compile(_led_ledger(), _led_spec(), _book(),
                        dc.CompileBudget(max_candidates=8))
    assert result.ok, result.render_failures()
    plan = result.candidates[0]
    parts = {part.part_id: part for part in plan.parts}
    assert _pose(parts["D1"]) == _pose(parts["D2"])
    common = [_pin_at(parts[part_id], "2") for part_id in ("D1", "D2")]
    assert {round(x, 6) for x, _ in common} == {round(common[0][0], 6)}, (
        "the common return end is one x")
    ys = [parts[part_id].y for part_id in ("D1", "D2")]
    assert ys[0] != ys[1], "the branches are stacked, not on one row"
    assert _pitch(sorted(ys)) is not None and _pitch(sorted(ys)) > 0, ys
    offsets = _label_offsets(plan, (("LED1", "D1"), ("LED2", "D2")))
    assert offsets["LED1"][1:] == offsets["LED2"][1:], offsets
    assert offsets["LED1"][0] == "D1" and offsets["LED2"][0] == "D2"
    assert not [item.net for item in plan.labels if item.net == "GND"], (
        "a ground is a flag, never a net label")
    assert "GND" in {item.net for item in plan.power_symbols}, (
        "the island states its ground locally")
    roles = {item.role: item.part_id for item in result.grammar.bindings}
    assert roles.get("gnd") == "GND" and "rail" not in roles, roles


def test_the_keys_island_draws_four_branches_on_one_rail():
    """Four keys from their own signal to 3V3: one `rail` return, not a ground."""
    result = dc.compile(_keys_ledger(), _keys_spec(), _book(),
                        dc.CompileBudget(max_candidates=8))
    assert result.ok, result.render_failures()
    plan = result.candidates[0]
    parts = {part.part_id: part for part in plan.parts}
    assert set(parts) == set(KEY_PARTS), sorted(parts)
    assert len({_pose(parts[part_id]) for part_id in KEY_PARTS}) == 1, (
        "the four branches read the same way")
    common = {part_id: _pin_at(parts[part_id], "2") for part_id in KEY_PARTS}
    assert len({round(x, 6) for x, _ in common.values()}) == 1, common
    ys = sorted(parts[part_id].y for part_id in KEY_PARTS)
    assert len(set(ys)) == 4, "the four branches are stacked"
    assert _pitch(ys) is not None and _pitch(ys) > 0, ys
    pairs = tuple((f"KEY{index}", f"S{index}") for index in range(1, 5))
    offsets = _label_offsets(plan, pairs)
    assert len({entry[1:] for entry in offsets.values()}) == 1, offsets
    assert {net: entry[0] for net, entry in offsets.items()} == dict(pairs), offsets
    assert _nearest_owner(plan, dict(pairs)) == {}
    assert not [item.net for item in plan.labels if item.net in ("3V3", "GND")], (
        "a power rail is a flag, never a net label")
    assert "3V3" in {item.net for item in plan.power_symbols}, (
        "the rail is stated locally by the flag")
    roles = {item.role: item.part_id for item in result.grammar.bindings}
    assert roles.get("rail") == "3V3", (
        "the common node is bound as the rail it is, never as a ground")
    assert "gnd" not in roles, roles
    outs = {item.part_id for item in result.grammar.bindings if item.role == "out"}
    assert outs == {f"KEY{index}" for index in range(1, 5)}, outs
    assert _per_pin_problems(plan, _keys_ledger(), _book()) == []


def test_the_four_rail_flag_leads_are_one_length_and_one_direction():
    """548D3B7b: like branches state their common return with **one** lead.

    Read from the plan's own drawn runs (`plan.segments`), not from the flag
    count: a lead 10 long on three branches and 30 on the fourth is four flags
    and one drawing that says two things about the same rail. The four runs
    must start on their own branch's rail pin, be equal in length, leave in one
    direction, and stay separate (no shared run that would read as a short).
    """
    result = dc.compile(_keys_ledger(), _keys_spec(), _book(),
                        dc.CompileBudget(max_candidates=8))
    assert result.ok, result.render_failures()
    plan = result.candidates[0]
    parts = {part.part_id: part for part in plan.parts}
    runs = [item.points for item in plan.segments if item.net == "3V3"]
    assert len(runs) == len(KEY_PARTS), runs
    for run in runs:
        assert len(run) == 2, run
    lengths = {round(abs(end[0] - start[0]) + abs(end[1] - start[1]), 6)
               for start, end in ((run[0], run[1]) for run in runs)}
    assert len(lengths) == 1, (
        f"the four rail flags do not share one lead length: {sorted(lengths)}")
    directions = {
        (round(abs(end[0] - start[0]) and (end[0] - start[0])
               / abs(end[0] - start[0]), 6),
         round(abs(end[1] - start[1]) and (end[1] - start[1])
               / abs(end[1] - start[1]), 6))
        for start, end in ((run[0], run[1]) for run in runs)
    }
    assert len(directions) == 1, f"the four rail leads leave different ways: {directions}"
    starts = [tuple(round(value, 6) for value in run[0]) for run in runs]
    assert len(set(starts)) == len(KEY_PARTS), starts
    assert set(starts) == {
        tuple(round(value, 6) for value in _pin_at(parts[part_id], "2"))
        for part_id in KEY_PARTS
    }, "a rail lead does not leave its own branch's rail pin"


# ----------------------------------------------------- 3. 三岛页：一页装三岛


def test_the_three_island_page_is_drawn_with_each_part_in_its_own_island():
    board = _circuit()
    spec = _island_spec()
    result = pc.compile_page(board, spec, _book(), PAGE)
    assert result.ok, result.render_failures()
    assert all(result.modules[module_id].ok
               for module_id in ("mcu", "keys", "led")), (
        {module_id: module.ok for module_id, module in result.modules.items()})
    page = result.best()
    assert {part.part_id for part in page.plan.parts} == set(p32._MCU_PARTS)
    assert _per_pin_problems(page.plan, board, _book()) == []
    assert readability.check_page(page, board, spec, _book()).hard_violations == []
    cross = [f"KEY{index}" for index in range(1, 5)] + ["LED1", "LED2"]
    assert not [item for item in page.plan.segments if item.net in cross], (
        "an island boundary is a name at each end, never a page wire")
    named = [item.net for item in page.plan.labels]
    for net in cross:
        assert named.count(net) == 2, (net, named.count(net))
    assert not [item.net for item in page.plan.labels if item.net in ("3V3", "GND")]
    flags = {item.net for item in page.plan.power_symbols}
    assert {"3V3", "GND"} <= flags, flags


# ------------------------------------------------- 4. 独立负控（不经过编译器）


def test_a_wire_drawn_across_the_island_boundary_is_refused():
    board, spec, result = _page()
    plan = result.best()
    host = next(part for part in plan.plan.parts if part.part_id == "U1")
    load = next(part for part in plan.plan.parts if part.part_id == "D1")
    bent = copy.deepcopy(plan)
    bent.plan.segments.append(dataclasses.replace(
        plan.plan.segments[0], net="LED1",
        points=[(host.x, host.y), (load.x, load.y)]))
    violations = readability.check_page(bent, board, spec, _book()).hard_violations
    assert any("shared-net-expression-split" in item.kind or
               "shared-net-expression-split" in item.render()
               for item in violations), [item.render() for item in violations]


def test_a_led_name_on_the_other_branch_or_a_missing_name_is_caught():
    ledger = _led_ledger()
    result = dc.compile(ledger, _led_spec(), _book(),
                        dc.CompileBudget(max_candidates=8))
    assert result.ok, result.render_failures()
    plan = result.candidates[0]
    assert _per_pin_problems(plan, ledger, _book()) == []

    swapped = copy.deepcopy(plan)
    for label in swapped.labels:
        if label.net in ("LED1", "LED2"):
            label.net = label.text = "LED2" if label.net == "LED1" else "LED1"
    assert _misnamed(swapped, ledger) == {
        "D1.1": {"printed": "LED2", "stated": "LED1"},
        "D2.1": {"printed": "LED1", "stated": "LED2"},
    }

    dropped = copy.deepcopy(plan)
    dropped.labels = [item for item in dropped.labels if item.net != "LED1"]
    assert _misnamed(dropped, ledger) == {}, (
        "a dropped name leaves the pin unnamed, not mis-named")
    assert "D1.1" not in _names_on_pins(dropped, ledger)[0]


def test_two_different_rails_are_not_one_bank():
    """Split the common rail in two: that group has two returns, not one."""
    base = _keys_ledger()
    nets = []
    for net in base.nets:
        members = list(net.members)
        if net.id == "3V3":
            members = [member for member in members
                       if member.split(".")[0] in ("S1", "S2")]
        nets.append({"id": net.id, "class": net.cls, "members": members,
                     "provenance": "verified_recipe"})
    nets.append({"id": "3V3B", "class": "power",
                 "members": ["S3.2", "S4.2"], "provenance": "verified_recipe"})
    split = p32.CircuitSpec.from_dict({
        "parts": [{"id": part.id, "symbolRef": part.symbol_ref,
                   "value": part.value, "provenance": "verified_recipe"}
                  for part in base.parts],
        "nets": nets,
    })
    result = dc.compile(split, _keys_spec(), _book(),
                        dc.CompileBudget(max_candidates=4))
    assert not result.ok, "two common rails are two banks, not one"
    assert result.candidates == []
    text = " ".join(f"{item.category} {item.subject} {item.detail}"
                    for item in result.failures)
    assert "3V3B" in text and "3V3" in text, text


# ------------------------------------ 5. 旧路径不变：CH34 出货页逐字节相同


def test_the_ch34_shipping_page_keeps_its_pinned_geometry():
    """The ground bank that ships today (CH34 serial) is byte-identical."""
    import test_520j_islands as i520
    from gate_skip import skip_if_the_147_gate_refused

    from boardwise.core.circuitspec import CircuitSpec
    from boardwise.engines.drawapply import load_library

    stem = "ch340_serial"
    spec = PresentationSpec.load(i520.SPECS / f"{stem}.presentation.json")
    circuit = CircuitSpec.load(i520.SPECS / f"{stem}.circuit.json")
    result = dc.compile(
        circuit, spec, load_library(i520.SPECS / f"{stem}.library.json"),
        dc.CompileBudget(page_box=(0.0, 0.0, 1170.0, 825.0)))
    skip_if_the_147_gate_refused(result, "548D3B7, the ch340_serial ship page")
    assert result.ok and result.candidates, result.render_failures()
    assert result.candidates[0].geometry_sha256() == (
        i520._BEFORE_520J["ch340_serial.plan.geometry"])
