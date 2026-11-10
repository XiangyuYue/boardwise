"""548B3：一条声明过的 `seriesBranches` 必须真的决定这张图的读法。

548B1 把支路写进了文档，548B2 让它被 V1–V8 校验并在两个消费者里拒掉非法声明。
两批之后，**声明对几何还没有任何作用**：`evidence/548B3/geometry-probe.md` 的读数
是——合法支路今天也能出 hard=0 的候选，但

* 画面与不声明**逐字节相同**（声明只是被校验，没有被读）；
* 全部候选把 LED 画在 R 的靠宿主一侧，`middleNet` 画成一条从 R 的远端掉头回 LED
  的折返线（高边 3 段 175 单位），读起来不是"宿主 → R → LED → 终端"的一条链。

所以本文件不用"bends/wire_length 小于某个数"来冒充结论，而是逐条候选问五个问题，
每个问题都能从图上重算：

1. **阅读顺序**：按 `seriesBranches` 的声明顺序取六个点——宿主、`parts[0]` 的两脚、
   `parts[1]` 的两脚、终端——在链轴（跨度较大的那一轴）上必须**单调**，方向由实际
   progress 决定（整体递增或递减都行），**中途不许回退**；
2. **中间节点**：`middleNet` 的绘制路径至多 2 段，长度至多 2 个**实测**节距
   （节距 = 两件中心在链轴上的距离，从这张图量，不写死坐标）；
3. **网表**：`readability.check` hard 0、`derive_netlist` 的分区与 `CircuitSpec`
   逐组相同（0 短路、0 分裂）、0 未放置、每件恰好一次；
4. **文字**：每个件的位号与值行都在图上；
5. **语法层**：绑定里有一条**把两件连起来**的关系（不是两个独立角色绑定），且独立的
   `check_grammar` 对"折返的候选"必须报、对"单调的候选"必须不报——方向关系不能只
   活在排序分数里。

两条文档都是 548B2 的正例（高边 `GPIO→R→LED→GND`、低边 `GPIO→R→LED→3V3`），
真实 `SymbolProfile`（MCU32 / R0402 / LED0805 / PWR-GND / PWR-3V3）内联在本文件里，
不写 `userLocks`、不指定坐标、不 import 探针或 evidence 下的任何文件。

另一条断言单独成测：**声明必须对几何有可观察效果**（声明版的首选候选与不声明版的
首选候选不是同一张图）。它与第 1 条是一对：只有前者，任何改动都能让它变绿；只有后者，
无法证明"是声明造成的"。未声明/`[]` 的旧读数由 548B2 的控制测试守着，本文件不重复。
"""

from __future__ import annotations

import json
import math
from collections import defaultdict

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolPin, SymbolProfile
from boardwise.engines import drawcompiler as dc
from boardwise.engines import readability

PROV = "verified_recipe"

#: Canvas tolerance: one fifth of the compilation lattice (5 units). Two points
#: closer than this along the chain axis are "on the same rank", not a step back.
TOLERANCE = 1.0


# ---------------------------------------------------------------- 符号库（内联）
def _pins(rows):
    return [
        SymbolPin(number=number, name=name, tip=tip, direction=direction)
        for number, name, tip, direction in rows
    ]


def _mcu() -> SymbolProfile:
    return SymbolProfile(
        symbol_ref="MCU32", title="MCU32", body=(-70.0, -60.0, 70.0, 60.0),
        pins=_pins((
            ("1", "VDD", (-80.0, 40.0), "left"),
            ("2", "VSS", (-80.0, 20.0), "left"),
            ("3", "PA5", (-80.0, 0.0), "left"),
            ("4", "PB0", (80.0, 0.0), "right"),
        )),
    )


def _resistor() -> SymbolProfile:
    return SymbolProfile(
        symbol_ref="R0402", title="Resistor", body=(-10.0, -20.0, 10.0, 20.0),
        pins=_pins((("1", "1", (0.0, 50.0), "up"), ("2", "2", (0.0, -50.0), "down"))),
    )


def _led() -> SymbolProfile:
    return SymbolProfile(
        symbol_ref="LED0805", title="LED", body=(-12.0, -8.0, 12.0, 8.0),
        pins=_pins((("1", "A", (-30.0, 0.0), "left"), ("2", "K", (30.0, 0.0), "right"))),
    )


def _flag(ref: str) -> SymbolProfile:
    return SymbolProfile(
        symbol_ref=ref, title=ref, body=(-6.0, 0.0, 6.0, 18.0), pins=[]
    )


def _library() -> dict[str, SymbolProfile]:
    book = {"MCU32": _mcu(), "R0402": _resistor(), "LED0805": _led()}
    for name in ("PWR-GND", "PWR-3V3", "PWR-VIN", "PWR-VIN5"):
        book[name] = _flag(name)
    return book


# ---------------------------------------------------------------- 手写文档
def _part(part_id: str, symbol: str, value: str = "") -> dict:
    return {"id": part_id, "symbolRef": symbol, "value": value, "provenance": PROV}


def _net(net_id: str, cls: str, members: list[str]) -> dict:
    return {"id": net_id, "class": cls, "members": list(members), "provenance": PROV}


_HIGH = {
    "parts": [_part("U1", "MCU32", "MCU"), _part("R2", "R0402", "1k"),
              _part("LED1", "LED0805", "red")],
    "nets": [_net("GPIO_STAT", "signal", ["U1.PA5", "R2.1"]),
             _net("LED_A", "signal", ["R2.2", "LED1.A"]),
             _net("GND", "gnd", ["U1.VSS", "LED1.K"]),
             _net("3V3", "power", ["U1.VDD"])],
    "modules": ["U1", "R2", "LED1"],
    "arm": {"id": "status-led", "from": "GPIO_STAT", "to": "GND",
            "parts": ["R2", "LED1"], "middleNet": "LED_A"},
}

_LOW = {
    "parts": [_part("U1", "MCU32", "MCU"), _part("R4", "R0402", "1k"),
              _part("LED2", "LED0805", "red")],
    "nets": [_net("LED_N", "signal", ["U1.PB0", "R4.1"]),
             _net("LED_B", "signal", ["R4.2", "LED2.K"]),
             _net("3V3", "power", ["LED2.A", "U1.VDD"]),
             _net("GND", "gnd", ["U1.VSS"])],
    "modules": ["U1", "R4", "LED2"],
    "arm": {"id": "run-led", "from": "LED_N", "to": "3V3",
            "parts": ["R4", "LED2"], "middleNet": "LED_B"},
}

CASES = ("high-side", "low-side")
_DOCUMENTS = {"high-side": _HIGH, "low-side": _LOW}

_MODULE = {"id": "mcu", "role": "status led", "grammarRef": "ic-periphery", "core": "U1"}


def _documents(case: str, declared: bool = True):
    payload = _DOCUMENTS[case]
    circuit = CircuitSpec.from_dict(
        {"parts": payload["parts"], "nets": payload["nets"]}
    )
    module = dict(_MODULE, parts=list(payload["modules"]))
    presentation_payload = {"grammarRef": "ic-periphery", "modules": [module]}
    if declared:
        presentation_payload["seriesBranches"] = [dict(payload["arm"])]
    presentation = PresentationSpec.from_dict(presentation_payload)
    return circuit, presentation


_CACHE: dict[tuple[str, bool], tuple] = {}


def _compiled(case: str, declared: bool = True):
    key = (case, declared)
    if key not in _CACHE:
        circuit, presentation = _documents(case, declared)
        result = dc.compile(circuit, presentation, _library())
        _CACHE[key] = (circuit, presentation, result)
    return _CACHE[key]


def _arm(case: str) -> dict:
    return _DOCUMENTS[case]["arm"]


# ------------------------------------------------------- 从图上读，不从编译器读
def _numbers(book, symbol_ref: str) -> dict[str, str]:
    """The symbol's own pin numbers, keyed by both number and name."""
    profile = book[symbol_ref]
    out = {pin.number: pin.number for pin in profile.pins}
    out.update({pin.name: pin.number for pin in profile.pins})
    return out


def _expected_pins(circuit: CircuitSpec, book) -> dict[str, str]:
    """``part.number -> circuit net``: the partition, with names resolved."""
    out: dict[str, str] = {}
    for spec_part in circuit.parts:
        numbers = _numbers(book, spec_part.symbol_ref)
        for net in circuit.nets:
            for member in net.members:
                pid, _, pin = member.partition(".")
                if pid == spec_part.id:
                    out[f"{pid}.{numbers.get(pin, pin)}"] = net.id
    return out


def _feet(expected: dict[str, str], part: str) -> dict[str, str]:
    return {pin: net for pin, net in expected.items() if pin.split(".")[0] == part}


def _pin_on(feet: dict[str, str], net_id: str) -> str | None:
    """The foot of this part the circuit puts on that net, if there is one."""
    return next((pin for pin, net in feet.items() if net == net_id), None)


def _terminal_anchor(plan, derived, expected, arm) -> tuple[str, tuple[float, float]] | None:
    """The drawn end of the `to` net: the anchor nearest the arm's last foot.

    A terminal may be a pin of a part outside the arm, a flag or a label; the one
    the arm actually ends on is the nearest, because that is the anchor the last
    run reaches. Nothing here is a coordinate from a fixture — they are read off
    the plan.
    """
    anchors: list[tuple[str, tuple[float, float]]] = []
    for pin, net_id in expected.items():
        if net_id == arm["to"] and pin.split(".")[0] not in arm["parts"]:
            anchors.append((pin, derived.pin_points[pin]))
    for symbol in plan.power_symbols:
        if symbol.net == arm["to"]:
            anchors.append((f"flag:{symbol.net}", (symbol.x, symbol.y)))
    for label in plan.labels:
        if label.net == arm["to"]:
            anchors.append((f"label:{label.text}", (label.x, label.y)))
    if not anchors:
        return None
    last = derived.pin_points[_pin_on(_feet(expected, arm["parts"][1]), arm["to"])]
    return min(
        anchors,
        key=lambda item: abs(item[1][0] - last[0]) + abs(item[1][1] - last[1]),
    )


def _chain_points(circuit, book, arm, plan, derived):
    """Host → parts[0] two feet → parts[1] two feet → terminal, as drawn."""
    expected = _expected_pins(circuit, book)
    first, second = arm["parts"]
    first_feet, second_feet = _feet(expected, first), _feet(expected, second)
    hosts = [pin for pin, net_id in expected.items()
             if net_id == arm["from"] and pin.split(".")[0] not in arm["parts"]]
    wanted = [
        ("parts[0] on from", _pin_on(first_feet, arm["from"])),
        ("parts[0] on middle", _pin_on(first_feet, arm["middleNet"])),
        ("parts[1] on middle", _pin_on(second_feet, arm["middleNet"])),
        ("parts[1] on to", _pin_on(second_feet, arm["to"])),
    ]
    if len(hosts) != 1 or any(pin is None for _label, pin in wanted):
        return None
    terminal = _terminal_anchor(plan, derived, expected, arm)
    if terminal is None:
        return None
    points = [("host " + hosts[0], derived.pin_points[hosts[0]])]
    for label, pin in wanted:
        points.append((f"{label} {pin}", derived.pin_points[pin]))
    points.append((f"terminal {terminal[0]}", terminal[1]))
    return points


def _chain_axis(points) -> tuple[int, float]:
    """Which axis the arm runs along, and which way — decided from the drawing.

    The axis is the one with the larger spread over the six points; the
    direction is the displacement between the arm's two **ends** (host and
    terminal), because those are the two points a reader enters and leaves by.
    A drawing that folds has ends that disagree with its middle steps, and that
    is exactly what the reading-order check reports.
    """
    xs = [point[1][0] for point in points]
    ys = [point[1][1] for point in points]
    axis = 0 if (max(xs) - min(xs)) >= (max(ys) - min(ys)) else 1
    first = points[0][1][axis]
    last = points[-1][1][axis]
    if abs(last - first) <= TOLERANCE:
        last = points[-2][1][axis]
    return axis, (1.0 if last >= first else -1.0)


def _reading_order_violations(circuit, book, arm, plan) -> list[str]:
    """① Every step of the declared traversal must advance, never step back.

    Monotone **either** way: which way the arm runs is the layout's decision (the
    side preferences decide it), but a reader who starts at the host must never
    meet a foot that goes back towards the host. The direction is taken from the
    first step (host → `parts[0]`), because that is where the reading starts; the
    steps that contradict it are the fold.
    """
    derived = readability.derive_netlist(plan, book)
    points = _chain_points(circuit, book, arm, plan, derived)
    if points is None:
        return ["the arm's six points cannot be identified on this drawing"]
    axis, _hint = _chain_axis(points)
    values = [point[1][axis] for point in points]
    labels = [point[0] for point in points]
    axis_name = "x" if axis == 0 else "y"
    problems: list[str] = []

    steps = [values[index + 1] - values[index] for index in range(len(values) - 1)]
    first_step = next((step for step in steps if abs(step) > TOLERANCE), 0.0)
    direction = 1.0 if first_step >= 0 else -1.0

    for index, step in enumerate(steps):
        if direction * step < -TOLERANCE:
            problems.append(
                f"{labels[index]} -> {labels[index + 1]} steps back along "
                f"{axis_name} ({values[index]:g} -> {values[index + 1]:g}); the arm "
                f"starts {'forward' if direction > 0 else 'back'} from its host "
                f"({values[0]:g} -> {values[1]:g}), so every following foot must "
                "keep going that way"
            )
    if direction * (values[-1] - values[0]) <= TOLERANCE:
        problems.append(
            f"the arm does not advance along {axis_name} overall: {labels[0]} at "
            f"{values[0]:g}, {labels[-1]} at {values[-1]:g}"
        )
    return problems


def _pitch(plan, arm, axis: int) -> float:
    """The spacing *this* layout gives the two parts, in canvas units.

    Centre-to-centre, because that is the spacing the layout actually chose for
    the pair; projecting on one axis would make a diagonal offset look like a
    smaller pitch than the reader sees.
    """
    places = {item.part_id: (item.x, item.y) for item in plan.parts}
    first, second = places[arm["parts"][0]], places[arm["parts"][1]]
    return math.hypot(second[0] - first[0], second[1] - first[1])


def _middle_path(plan, net_id: str) -> tuple[int, float]:
    """Pieces and Manhattan length of the drawn middle node."""
    pieces = 0
    length = 0.0
    for segment in plan.segments:
        if segment.net != net_id:
            continue
        for start, end in zip(segment.points, segment.points[1:]):
            pieces += 1
            length += abs(end[0] - start[0]) + abs(end[1] - start[1])
    return pieces, length


def _middle_violations(circuit, book, arm, plan) -> list[str]:
    """② The private node is a short link between the two parts, not a detour."""
    derived = readability.derive_netlist(plan, book)
    points = _chain_points(circuit, book, arm, plan, derived)
    axis = _chain_axis(points)[0] if points else 0
    pitch = _pitch(plan, arm, axis)
    pieces, length = _middle_path(plan, arm["middleNet"])
    problems = []
    if pieces == 0:
        problems.append(
            f"the middle node {arm['middleNet']} is not drawn as one link — it is "
            "expressed by a name at each foot instead"
        )
    if pieces > 2:
        problems.append(
            f"the middle node {arm['middleNet']} is drawn in {pieces} pieces "
            "(a link between two adjacent parts is one or two)"
        )
    if pitch > 0 and length > 2.0 * pitch:
        problems.append(
            f"the middle node {arm['middleNet']} runs {length:g} units for a "
            f"{pitch:g}-unit pitch between the two parts (limit {2 * pitch:g})"
        )
    return problems


def _netlist_violations(circuit, presentation, book, plan) -> list[str]:
    """③ The drawing says the same netlist as the circuit, and says all of it."""
    derived = readability.derive_netlist(plan, book)
    expected = _expected_pins(circuit, book)
    problems: list[str] = []

    placed = [item.part_id for item in plan.parts]
    if len(placed) != len(set(placed)):
        problems.append(f"a part is placed twice: {sorted(placed)}")
    missing = sorted({pin.split(".")[0] for pin in expected} - set(placed))
    if missing:
        problems.append(f"not placed at all: {missing}")
    extra = sorted(set(placed) - {pin.split(".")[0] for pin in expected})
    if extra:
        problems.append(f"placed but not in the circuit: {extra}")

    unplaced = sorted(set(expected) - set(derived.pin_group))
    if unplaced:
        problems.append(f"pins the drawing never places: {unplaced}")

    seen_groups: set[tuple[str, ...]] = set()
    for group in derived.pin_group.values():
        if group in seen_groups:
            continue
        seen_groups.add(group)
        nets = {expected.get(pin) for pin in group}
        if len(nets) > 1:
            problems.append(f"short: one node joins {group} across nets {sorted(nets)}")

    by_net: dict[str, set[str]] = defaultdict(set)
    for pin, net_id in expected.items():
        by_net[net_id].add(pin)
    for net_id, feet in sorted(by_net.items()):
        if len(feet) < 2:
            continue
        groups = {frozenset(derived.pin_group.get(pin, (pin,))) for pin in feet}
        if len(groups) > 1:
            problems.append(f"split: net {net_id} is {len(groups)} nodes on the page")

    hard = readability.check(plan, circuit, presentation, book).hard_violations
    for violation in hard:
        problems.append(f"hard violation: {violation}")
    return problems


def _text_violations(circuit, plan) -> list[str]:
    """④ Every reference, and every stated value, is written on the page."""
    rules = [(text.kind, text.text) for text in plan.texts]
    problems = []
    for spec_part in circuit.parts:
        if ("reference", spec_part.id) not in rules:
            problems.append(f"no reference row for {spec_part.id}")
        if spec_part.value and ("value", spec_part.value) not in rules:
            problems.append(f"no value row {spec_part.value!r} for {spec_part.id}")
    return problems


def _pair_bindings(result, arm) -> list[str]:
    """⑤a Which grammar-layer statements couple the arm's two parts.

    Two independent role bindings are not a relation: the declaration says these
    two parts are one chain in one order, so the layer that owns relations has to
    carry them *as one statement*. A constraint is the natural carrier; an
    obligation that names both parts counts too, and nothing here reads a score.
    """
    pair = set(arm["parts"])
    found: list[str] = []
    grammar = result.grammar
    if grammar is None:
        return found
    # A `RelativeConstraint` is the layer's own vocabulary for "a relation two
    # parts must satisfy", which is exactly what a declared arm is. A role
    # binding cannot count — it names one id by construction — and free text
    # (a binding's evidence, an obligation's reason) is not a relation either.
    for constraint in grammar.constraints:
        if {constraint.subject, constraint.object} == pair:
            found.append(f"constraint {constraint.kind}: {constraint.reason}")
    return found


def _arm_findings(finding_list, arm) -> list:
    """The checker's findings that are about this arm, not about something else."""
    out = []
    for finding in finding_list:
        rendered = " ".join([*finding.objects, finding.detail])
        if all(part in rendered for part in arm["parts"]) or arm["middleNet"] in rendered:
            out.append(finding)
    return out


def _accepted(case: str):
    circuit, presentation, result = _compiled(case)
    assert result.ok, (
        f"{case}: a legal arm must still compile; it was refused with "
        f"{[(f.category, f.detail) for f in result.failures]}"
    )
    assert result.candidates, f"{case}: ok with no candidate"
    return circuit, presentation, result


# ================================================================ ① 阅读顺序


@pytest.mark.parametrize("case", CASES)
def test_every_candidate_reads_the_arm_in_the_declared_order(case):
    """宿主 → parts[0] → middle → parts[1] → 终端：每一步都向前，不回退。"""
    circuit, _presentation, result = _accepted(case)
    book = _library()
    problems = []
    for index, plan in enumerate(result.candidates):
        for problem in _reading_order_violations(circuit, book, _arm(case), plan):
            problems.append(f"candidate {index}: {problem}")
    assert not problems, (
        f"{case}: the declared arm is not the shape drawn —\n  " + "\n  ".join(problems)
    )


# ============================================================== ② 中间节点


@pytest.mark.parametrize("case", CASES)
def test_every_candidate_draws_the_middle_node_as_a_short_link(case):
    """中间节点至多 2 段、至多 2 个实测节距（不写死坐标、不用 bends 阈值）。"""
    circuit, _presentation, result = _accepted(case)
    book = _library()
    problems = []
    for index, plan in enumerate(result.candidates):
        for problem in _middle_violations(circuit, book, _arm(case), plan):
            problems.append(f"candidate {index}: {problem}")
    assert not problems, (
        f"{case}: the private node is not a link between two adjacent parts —\n  "
        + "\n  ".join(problems)
    )


# ==================================================== ③ 网表 / ④ 文字


@pytest.mark.parametrize("case", CASES)
def test_every_candidate_draws_exactly_the_circuit(case):
    """hard 0；图的分区与 CircuitSpec 相同（0 短路、0 分裂、0 未放置、每件一次）。"""
    circuit, presentation, result = _accepted(case)
    book = _library()
    problems = []
    for index, plan in enumerate(result.candidates):
        for problem in _netlist_violations(circuit, presentation, book, plan):
            problems.append(f"candidate {index}: {problem}")
    assert not problems, (
        f"{case}: the drawing and the circuit disagree —\n  " + "\n  ".join(problems)
    )


@pytest.mark.parametrize("case", CASES)
def test_every_candidate_writes_every_reference_and_value(case):
    """位号与值行完整：每个件一条 reference，每个声明的值一条 value。"""
    circuit, _presentation, result = _accepted(case)
    problems = []
    for index, plan in enumerate(result.candidates):
        for problem in _text_violations(circuit, plan):
            problems.append(f"candidate {index}: {problem}")
    assert not problems, (
        f"{case}: text is missing —\n  " + "\n  ".join(problems)
    )


# ==================================================== ⑤ 语法层看得见声明


@pytest.mark.parametrize("case", CASES)
def test_the_grammar_binds_the_two_parts_as_one_relation(case):
    """⑤a 绑定里有一条把两件连起来的关系，不是两个各说各的角色绑定。"""
    _circuit, _presentation, result = _compiled(case)
    assert result.ok, "a legal arm must bind"
    found = _pair_bindings(result, _arm(case))
    assert found, (
        f"{case}: the declared arm is not one relation in the grammar layer — "
        "today the binding names the host and the rails only, so the declaration "
        "lives nowhere but the ranking"
    )


@pytest.mark.parametrize("case", CASES)
def test_the_independent_checker_sees_the_declared_direction(case):
    """⑤b 独立 check_grammar：单调的候选不报，**折返的候选必须报**。

    这一条与 ① 是一对：① 说"这张图折返了"，⑤b 说"语法层的独立检查器自己也
    看得出来"。只让排序分数变化、检查器看不见，等于把声明藏进调参。

    两半都是真测，缺一半都会留下洞：

    * **好图不得被报**：本 case 声明版返回的每个候选都必须不被 `check_grammar`
      点名这条臂——否则"报"就成了噪声，折返图被报也不说明任何事；
    * **坏图必须被报**：同一份文档**不声明**时返回的候选里，挑出第一个由
      `_reading_order_violations` / `_middle_violations` 判为折返的图（先断言它
      真的折返），再拿**声明版**的 circuit/presentation/book 去调
      `dc.check_grammar`，断言它点名这条臂。

    负例来自同一条电路的真实绘制，不是手工摆的坐标：删掉检查器里的关系注入，
    这一段就会红——这正是"检查器看不见声明"的那一半。
    """
    circuit, presentation, result = _accepted(case)
    book = _library()
    arm = _arm(case)
    problems = []
    for index, plan in enumerate(result.candidates):
        violates = bool(_reading_order_violations(circuit, book, arm, plan))
        violations = bool(_middle_violations(circuit, book, arm, plan))
        findings = _arm_findings(
            dc.check_grammar(plan, circuit, presentation, book), arm
        )
        if violates or violations:
            problems.append(
                f"candidate {index}: a returned candidate folds the arm, so ① is "
                "red for a reason this test is not meant to explain"
            )
        if findings:
            problems.append(
                f"candidate {index}: the checker names the arm on a drawing that "
                f"keeps it: {[f.render() for f in findings]}"
            )
    assert not problems, (
        f"{case}: the independent checker does not see the declared direction —\n  "
        + "\n  ".join(problems)
    )

    # --- the real negative: a folded drawing of the same circuit -------------
    _undeclared_circuit, _undeclared_presentation, undeclared = _compiled(
        case, declared=False
    )
    assert undeclared.ok, (
        f"{case}: the same document without the arm no longer compiles, so no "
        "folded drawing is available to grade"
    )
    folded = None
    for plan in undeclared.candidates:
        if _reading_order_violations(circuit, book, arm, plan) or _middle_violations(
            circuit, book, arm, plan
        ):
            folded = plan
            break
    assert folded is not None, (
        f"{case}: no undeclared candidate folds the arm, so this test would have "
        "no negative to grade — the fixture needs a drawing the declaration is "
        "supposed to fix"
    )
    findings = _arm_findings(dc.check_grammar(folded, circuit, presentation, book), arm)
    assert findings, (
        f"{case}: the checker grades a folded drawing of the declared arm and says "
        "nothing about it — it never read the declaration, so its silence on the "
        "good drawings proves nothing"
    )


# ============================================== 声明必须改变画出来的东西


def _picture(plan) -> str:
    """The plan as a picture, minus the two source digests (which always move)."""
    payload = plan._geometry_payload()
    payload.pop("source", None)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


@pytest.mark.parametrize("case", CASES)
def test_the_declaration_changes_the_drawing(case):
    """声明过的文档与不声明的同一份文档，不能画出同一张图。

    这是 ① 的伴生断言：① 说"这张图是单调的链"，本条说"这张图是声明造成的"。
    只有本条，任何改动都能让它变绿；只有 ①，无法区分"链是碰巧摆对的"与
    "链是被声明决定的"。未声明/`[]` 的旧读数由 548B2 的控制测试守着。
    """
    _circuit, _presentation, declared = _accepted(case)
    _c2, _p2, undeclared = _compiled(case, declared=False)
    assert undeclared.ok, (
        f"{case}: the same document without the arm no longer compiles: "
        f"{[(f.category, f.detail) for f in undeclared.failures]}"
    )
    assert _picture(declared.candidates[0]) != _picture(undeclared.candidates[0]), (
        f"{case}: declaring an arm drew the very same picture as declaring "
        "nothing — the declaration is validated and then ignored"
    )
