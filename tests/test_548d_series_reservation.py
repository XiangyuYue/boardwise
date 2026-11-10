"""548D2：声明串联座位必须在普通支路定座之前预留，否则 MCU 岛永远 0 候选。

诊断（`evidence/548D/power-flag/report.md`）：`_seat_series_arms` 在普通支路全部
落座**之后**才把一串两件摆到 `host + progress*pitch/2`，而那条走廊在 MCU 岛上
早被四个键与另一条灯支路占住——base 轮 `R3` 压 `S1`，topology 轮 `R2` 压 `S2`，
于是本岛在 548B3-R 生产下 0 候选。

本文件内联 548D0 的 MCU 模块视图：14 件、31 网、NC `U1.PA6`、两条
`seriesBranches`（`R2→D1`、`R3→D2`），符号几何取自冻结 547A 库的同一批 profile，
预算照 `compile_page` 给模块的那一份（`PageCompileBudget(page_box)` +
文档 `flagLeadLimit=120` / `gndClustering=100` + `_module_budget_for`），整页 GND
域。不读任何 evidence 文件、不写 `userLocks`、不填坐标。

判据（实现后每条都必须成立，全部从图上重算）：

* 至少 1 个候选；两条臂的六点（宿主、两件四脚、终端）在链轴上单调，`middleNet`
  至多 2 段、至多 2 个实测节距；
* 任两件 box 不重叠；四键各在自己 `KEYn` 网；`check_grammar` 不报；
* hard 0、分区与本地 CircuitSpec 一致（0 短路/分裂/未放置、每件一次）、
  位号与值行完整。
"""

from __future__ import annotations

import json
import math
from dataclasses import replace

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolPose, SymbolProfile
from boardwise.engines import drawcompiler as dc
from boardwise.engines import pagecompiler as pc
from boardwise.engines import readability

#: 画布容差：同一档上的两个点（≤1 单位）不算一步。
TOLERANCE = 1.0

_PART_ROWS = (
    ("U1", "MCU-STM32G431RBT6", "STM32G431RBT6"),
    ("C1", "C0603-100nF", "100nF"),
    ("C2", "C0603-4u7", "4.7uF"),
    ("C3", "C0603-100nF", "100nF"),
    ("R1", "R0603-10k", "10k"),
    ("R2", "R0603-1k", "1k"),
    ("R3", "R0603-1k", "1k"),
    ("D1", "LED0603", "LED"),
    ("D2", "LED0603", "LED"),
    ("S1", "KEY-PTSM", "KEY"),
    ("S2", "KEY-PTSM", "KEY"),
    ("S3", "KEY-PTSM", "KEY"),
    ("S4", "KEY-PTSM", "KEY"),
    ("BZ1", "BUZZER-PASSIVE", "BUZZER"),
)

PARTS = [
    {"id": part_id, "symbolRef": symbol, "value": value, "mpn": "", "lcsc": "",
     "params": {}, "provenance": "ai_asserted"}
    for part_id, symbol, value in _PART_ROWS
]

_NET_ROWS = (
    ("3V3", "power", ["U1.VDD", "U1.VDDA", "U1.VBAT", "C1.1", "C2.1", "C3.1",
                      "R1.1", "S1.2", "S2.2", "S3.2", "S4.2"]),
    ("GND", "gnd", ["U1.VSS", "U1.VSSA", "C1.2", "C2.2", "C3.2", "R1.2",
                    "D1.2", "D2.2", "BZ1.2"]),
    ("LED1_K", "signal", ["U1.PA3", "R2.1"]),
    ("LED1_A", "signal", ["R2.2", "D1.1"]),
    ("LED2_K", "signal", ["U1.PA4", "R3.1"]),
    ("LED2_A", "signal", ["R3.2", "D2.1"]),
    ("KEY1", "signal", ["U1.PC6", "S1.1"]),
    ("KEY2", "signal", ["U1.PB15", "S2.1"]),
    ("KEY3", "signal", ["U1.PB14", "S3.1"]),
    ("KEY4", "signal", ["U1.PB13", "S4.1"]),
    ("BUZZ", "signal", ["U1.PC0", "BZ1.1"]),
    ("LCD_SCK", "signal", ["U1.PA5"]),
    ("LCD_SDA", "signal", ["U1.PA7"]),
    ("LCD_RES", "signal", ["U1.PC4"]),
    ("LCD_DC", "signal", ["U1.PC5"]),
    ("LCD_BLK", "signal", ["U1.PB0"]),
    ("I2C2_SDA", "signal", ["U1.PA8"]),
    ("I2C2_SCL", "signal", ["U1.PA9"]),
    ("I2C3_SCL", "signal", ["U1.PC8"]),
    ("I2C3_SDA", "signal", ["U1.PC9"]),
    ("ESP_TXD", "signal", ["U1.PB10"]),
    ("ESP_RXD", "signal", ["U1.PB11"]),
    ("ESP_EN", "signal", ["U1.PD2"]),
    ("ESP_RST", "signal", ["U1.PC12"]),
    ("ESP_IO0", "signal", ["U1.PB3"]),
    ("USART1_TX", "signal", ["U1.PB6"]),
    ("USART1_RX", "signal", ["U1.PB7"]),
    ("SWDIO", "signal", ["U1.PA13"]),
    ("SWCLK", "signal", ["U1.PA14"]),
    ("NRST", "signal", ["U1.NRST"]),
    ("BOOT0", "signal", ["U1.BOOT0"]),
)

NETS = [
    {"id": net_id, "class": cls, "members": list(members),
     "provenance": "ai_asserted", "scope": ""}
    for net_id, cls, members in _NET_ROWS
]

CIRCUIT_PAYLOAD = {
    "kind": "boardwise-circuit-spec", "specVersion": 1,
    "parts": PARTS, "nets": NETS,
    "nc": [{"pin": "U1.PA6", "provenance": "ai_asserted"}],
    "openInterfaces": [], "operatingConditions": {}, "draft": True,
}

ARMS = (
    {"id": "led1_series", "from": "LED1_K", "to": "GND",
     "parts": ["R2", "D1"], "middleNet": "LED1_A"},
    {"id": "led2_series", "from": "LED2_K", "to": "GND",
     "parts": ["R3", "D2"], "middleNet": "LED2_A"},
)

PRESENTATION_PAYLOAD = {
    "kind": "boardwise-presentation-spec", "specVersion": 1,
    "modules": [{
        "id": "mcu",
        "parts": [row[0] for row in _PART_ROWS],
        "role": "Host MCU island: STM32G431RBT6 with its decoupling pair, NRST "
                "capacitor and BOOT0 pull-down; the panel items hang on their own "
                "GPIO pins, so they stay here.",
        "core": "U1",
    }],
    "serviceLayout": {"pinGap": 30.0},
    "mainPaths": [], "feedbackPaths": [],
    "portRoles": {
        "LCD_SCK": "output", "LCD_SDA": "output", "LCD_RES": "output",
        "LCD_DC": "output", "LCD_BLK": "output", "I2C2_SCL": "output",
        "I2C2_SDA": "load", "I2C3_SCL": "output", "I2C3_SDA": "load",
        "ESP_TXD": "output", "ESP_RXD": "input", "ESP_EN": "output",
        "ESP_RST": "output", "ESP_IO0": "output", "USART1_TX": "output",
        "USART1_RX": "input", "SWDIO": "input", "SWCLK": "input",
        "BUZZ": "output", "LED1_K": "output", "LED2_K": "output",
        "KEY1": "input", "KEY2": "input", "KEY3": "input", "KEY4": "input",
        "NRST": "input", "BOOT0": "input",
    },
    "grammarRef": "ic-periphery",
    "directWiringObligations": [],
    "seriesBranches": [dict(arm) for arm in ARMS],
    "labelPolicy": {"local": "wire", "crossModule": "label", "highFanout": "label",
                    "stub": "straight", "stubMin": 40.0, "rowModel": "centered"},
    "sidePreferences": {"input": "left", "output": "right", "power": "top",
                        "gnd": "bottom", "load": "right", "source": "left"},
    "userLocks": [],
    "partTexts": {part_id: "right" for part_id in
                  ("U1", "BZ1", "D1", "D2", "S1", "S2", "S3", "S4")},
}

#: 冻结 547A 库中本岛用到的 10 个 profile（8 个器件 + 2 个电源旗），几何逐字。
_PROFILE_ROWS = (
    '{"symbolRef":"BUZZER-PASSIVE","title":"passive buzzer, 2 terminals, uncalibrated","body":[-10.0,-10.0,10.0,10.0],"pins":[{"number":"1","name":"1","tip":[-20.0,0.0],"direction":"left","length":10.0,"pinType":"passive"},{"number":"2","name":"2","tip":[20.0,0.0],"direction":"right","length":10.0,"pinType":"passive"}]}',
    '{"symbolRef":"C0603-100nF","title":"100 nF capacitor 0603, uncalibrated","body":[-5.5,-8.5,5.5,8.5],"pins":[{"number":"1","name":"1","tip":[-20.0,0.0],"direction":"left","length":10.0,"pinType":"passive"},{"number":"2","name":"2","tip":[20.0,0.0],"direction":"right","length":10.0,"pinType":"passive"}]}',
    '{"symbolRef":"C0603-4u7","title":"4.7 uF capacitor 0603, uncalibrated","body":[-5.5,-8.5,5.5,8.5],"pins":[{"number":"1","name":"1","tip":[-20.0,0.0],"direction":"left","length":10.0,"pinType":"passive"},{"number":"2","name":"2","tip":[20.0,0.0],"direction":"right","length":10.0,"pinType":"passive"}]}',
    '{"symbolRef":"KEY-PTSM","title":"momentary push button, 2 terminals, uncalibrated","body":[-12.0,-6.5,12.0,6.5],"pins":[{"number":"1","name":"1","tip":[0.0,20.0],"direction":"up","length":10.0,"pinType":"passive"},{"number":"2","name":"2","tip":[0.0,-20.0],"direction":"down","length":10.0,"pinType":"passive"}]}',
    '{"symbolRef":"LED0603","title":"LED 0603, anode pin 1, cathode pin 2, uncalibrated","body":[-7.0,-5.5,7.0,5.5],"pins":[{"number":"1","name":"A","tip":[-20.0,0.0],"direction":"left","length":10.0,"pinType":"passive"},{"number":"2","name":"K","tip":[20.0,0.0],"direction":"right","length":10.0,"pinType":"passive"}]}',
    '{"symbolRef":"MCU-STM32G431RBT6","title":"STM32G431RBT6 LQFP64, logical pin map (firmware-used pins only), uncalibrated","body":[-70.0,-100.0,70.0,100.0],"pins":[{"number":"VDD","name":"VDD","tip":[-30.0,110.0],"direction":"up","length":10.0,"pinType":"passive"},{"number":"VDDA","name":"VDDA","tip":[0.0,110.0],"direction":"up","length":10.0,"pinType":"passive"},{"number":"VBAT","name":"VBAT","tip":[30.0,110.0],"direction":"up","length":10.0,"pinType":"passive"},{"number":"VSS","name":"VSS","tip":[-20.0,-110.0],"direction":"down","length":10.0,"pinType":"passive"},{"number":"VSSA","name":"VSSA","tip":[20.0,-110.0],"direction":"down","length":10.0,"pinType":"passive"},{"number":"NRST","name":"NRST","tip":[-80.0,85],"direction":"left","length":10.0,"pinType":"passive"},{"number":"BOOT0","name":"BOOT0","tip":[-80.0,75],"direction":"left","length":10.0,"pinType":"passive"},{"number":"PA13","name":"PA13","tip":[-80.0,65],"direction":"left","length":10.0,"pinType":"passive"},{"number":"PA14","name":"PA14","tip":[-80.0,55],"direction":"left","length":10.0,"pinType":"passive"},{"number":"PA8","name":"PA8","tip":[-80.0,45],"direction":"left","length":10.0,"pinType":"passive"},{"number":"PA9","name":"PA9","tip":[-80.0,35],"direction":"left","length":10.0,"pinType":"passive"},{"number":"PC8","name":"PC8","tip":[-80.0,25],"direction":"left","length":10.0,"pinType":"passive"},{"number":"PC9","name":"PC9","tip":[-80.0,15],"direction":"left","length":10.0,"pinType":"passive"},{"number":"PA6","name":"PA6","tip":[-80.0,5],"direction":"left","length":10.0,"pinType":"passive"},{"number":"PC0","name":"PC0","tip":[-80.0,-5],"direction":"left","length":10.0,"pinType":"passive"},{"number":"PB6","name":"PB6","tip":[-80.0,-15],"direction":"left","length":10.0,"pinType":"passive"},{"number":"PB7","name":"PB7","tip":[-80.0,-25],"direction":"left","length":10.0,"pinType":"passive"},{"number":"PB3","name":"PB3","tip":[-80.0,-35],"direction":"left","length":10.0,"pinType":"passive"},{"number":"PC4","name":"PC4","tip":[80.0,85],"direction":"right","length":10.0,"pinType":"passive"},{"number":"PC5","name":"PC5","tip":[80.0,75],"direction":"right","length":10.0,"pinType":"passive"},{"number":"PB0","name":"PB0","tip":[80.0,65],"direction":"right","length":10.0,"pinType":"passive"},{"number":"PA5","name":"PA5","tip":[80.0,55],"direction":"right","length":10.0,"pinType":"passive"},{"number":"PA7","name":"PA7","tip":[80.0,45],"direction":"right","length":10.0,"pinType":"passive"},{"number":"PA3","name":"PA3","tip":[80.0,35],"direction":"right","length":10.0,"pinType":"passive"},{"number":"PA4","name":"PA4","tip":[80.0,25],"direction":"right","length":10.0,"pinType":"passive"},{"number":"PC6","name":"PC6","tip":[80.0,15],"direction":"right","length":10.0,"pinType":"passive"},{"number":"PB15","name":"PB15","tip":[80.0,5],"direction":"right","length":10.0,"pinType":"passive"},{"number":"PB14","name":"PB14","tip":[80.0,-5],"direction":"right","length":10.0,"pinType":"passive"},{"number":"PB13","name":"PB13","tip":[80.0,-15],"direction":"right","length":10.0,"pinType":"passive"},{"number":"PB10","name":"PB10","tip":[80.0,-25],"direction":"right","length":10.0,"pinType":"passive"},{"number":"PB11","name":"PB11","tip":[80.0,-35],"direction":"right","length":10.0,"pinType":"passive"},{"number":"PD2","name":"PD2","tip":[80.0,-45],"direction":"right","length":10.0,"pinType":"passive"},{"number":"PC12","name":"PC12","tip":[80.0,-55],"direction":"right","length":10.0,"pinType":"passive"}]}',
    '{"symbolRef":"R0603-10k","title":"10 kOhm resistor 0603, uncalibrated","body":[-10.5,-4.5,10.5,4.5],"pins":[{"number":"1","name":"1","tip":[-20.0,0.0],"direction":"left","length":10.0,"pinType":"passive"},{"number":"2","name":"2","tip":[20.0,0.0],"direction":"right","length":10.0,"pinType":"passive"}]}',
    '{"symbolRef":"R0603-1k","title":"1 kOhm resistor 0603, uncalibrated","body":[-10.5,-4.5,10.5,4.5],"pins":[{"number":"1","name":"1","tip":[-20.0,0.0],"direction":"left","length":10.0,"pinType":"passive"},{"number":"2","name":"2","tip":[20.0,0.0],"direction":"right","length":10.0,"pinType":"passive"}]}',
    '{"symbolRef":"PWR-+3V3","title":"power flag +3V3","body":[-5.0,0.0,5.0,10.0],"pins":[]}',
    '{"symbolRef":"PWR-GND","title":"power flag GND","body":[-10.0,0.0,10.0,19.0],"pins":[]}',
)

PROFILES = tuple(json.loads(row) for row in _PROFILE_ROWS)


def _book() -> dict[str, SymbolProfile]:
    return {row["symbolRef"]: SymbolProfile.from_dict(row) for row in PROFILES}


def _budget():
    """`compile_page` 给模块的那一份预算，逐行同 548D0 探针。"""
    budget = pc.PageCompileBudget(page_box=(0.0, 0.0, 1170.0, 825.0))
    budget = replace(
        budget,
        module_budget=replace(budget.module_budget, flag_lead_limit=120.0),
    )
    budget = replace(
        budget,
        module_budget=replace(budget.module_budget, gnd_cluster_radius=100.0),
    )
    return pc._module_budget_for(budget.module_budget, budget)


def _documents(declared: bool = True):
    circuit = CircuitSpec.from_dict(CIRCUIT_PAYLOAD)
    payload = dict(PRESENTATION_PAYLOAD)
    payload["seriesBranches"] = [dict(arm) for arm in ARMS] if declared else []
    return circuit, PresentationSpec.from_dict(payload)


_CACHE: dict[bool, tuple] = {}


def _compiled(declared: bool = True):
    if declared not in _CACHE:
        circuit, presentation = _documents(declared)
        ground = frozenset(
            dc._ground_domain(net.id) for net in circuit.nets if net.cls == "gnd"
        )
        result = dc.compile(
            circuit, presentation, _book(), _budget(), page_ground_domains=ground,
        )
        _CACHE[declared] = (circuit, presentation, result)
    return _CACHE[declared]


def _accepted():
    circuit, presentation, result = _compiled()
    assert result.ok, (
        "the series MCU island still draws nothing: "
        f"{[(f.category, f.subject, f.detail) for f in result.failures]}"
    )
    assert result.candidates, "ok with no candidate"
    return circuit, presentation, result


# ------------------------------------------------------- 从图上读，不从编译器读
def _numbers(book, symbol_ref: str) -> dict[str, str]:
    profile = book[symbol_ref]
    out = {pin.number: pin.number for pin in profile.pins}
    out.update({pin.name: pin.number for pin in profile.pins})
    return out


def _expected_pins(circuit: CircuitSpec, book) -> dict[str, str]:
    out: dict[str, str] = {}
    for spec_part in circuit.parts:
        numbers = _numbers(book, spec_part.symbol_ref)
        for net in circuit.nets:
            for member in net.members:
                pid, _, pin = member.partition(".")
                if pid == spec_part.id:
                    out[f"{pid}.{numbers.get(pin, pin)}"] = net.id
    return out


def _pin_on(expected: dict[str, str], part: str, net_id: str) -> str | None:
    return next(
        (pin for pin, net in expected.items()
         if net == net_id and pin.split(".")[0] == part),
        None,
    )


def _chain_points(circuit, book, arm, plan, members):
    """宿主 → `parts[0]` 两脚 → `parts[1]` 两脚 → 终端，按声明顺序，从图上取。"""
    derived = readability.derive_netlist(plan, book)
    expected = _expected_pins(circuit, book)
    first, second = arm["parts"]
    hosts = [pin for pin, net in expected.items()
             if net == arm["from"] and pin.split(".")[0] in members
             and pin.split(".")[0] not in arm["parts"]]
    wanted = [
        _pin_on(expected, first, arm["from"]),
        _pin_on(expected, first, arm["middleNet"]),
        _pin_on(expected, second, arm["middleNet"]),
        _pin_on(expected, second, arm["to"]),
    ]
    if len(hosts) != 1 or any(pin is None for pin in wanted):
        return None
    terminal = None
    anchors = []
    for pin, net_id in expected.items():
        if net_id == arm["to"] and pin.split(".")[0] not in arm["parts"]:
            anchors.append(derived.pin_points[pin])
    for symbol in plan.power_symbols:
        if symbol.net == arm["to"]:
            anchors.append((symbol.x, symbol.y))
    for label in plan.labels:
        if label.net == arm["to"] and label.kind != "net":
            anchors.append((label.x, label.y))
    last = derived.pin_points[wanted[-1]]
    if anchors:
        terminal = min(
            anchors,
            key=lambda item: abs(item[0] - last[0]) + abs(item[1] - last[1]),
        )
    points = [("host " + hosts[0], derived.pin_points[hosts[0]])]
    for label, pin in zip(("p0 from", "p0 middle", "p1 middle", "p1 to"), wanted):
        points.append((f"{label} {pin}", derived.pin_points[pin]))
    if terminal is not None:
        points.append(("terminal", terminal))
    return points


def _reading_problems(circuit, book, arm, plan, members) -> list[str]:
    points = _chain_points(circuit, book, arm, plan, members)
    if points is None:
        return [f"{arm['id']}: the six points are not on the page"]
    xs = [point[1][0] for point in points]
    ys = [point[1][1] for point in points]
    axis = 0 if (max(xs) - min(xs)) >= (max(ys) - min(ys)) else 1
    values = [point[1][axis] for point in points]
    labels = [point[0] for point in points]
    steps = [values[index + 1] - values[index] for index in range(len(values) - 1)]
    first = next((step for step in steps if abs(step) > TOLERANCE), 0.0)
    if abs(first) <= TOLERANCE:
        return [f"{arm['id']}: the arm has no extent along {'xy'[axis]}"]
    direction = 1.0 if first > 0 else -1.0
    problems = [
        f"{arm['id']}: {labels[index]} -> {labels[index + 1]} steps back along "
        f"{'xy'[axis]} ({values[index]:g} -> {values[index + 1]:g})"
        for index, step in enumerate(steps)
        if direction * step < -TOLERANCE
    ]
    if direction * (values[-1] - values[0]) <= TOLERANCE:
        problems.append(
            f"{arm['id']}: the arm does not advance overall "
            f"({values[0]:g} -> {values[-1]:g} on {'xy'[axis]})"
        )
    return problems


def _middle_path(plan, net_id: str) -> tuple[int, float]:
    pieces = 0
    length = 0.0
    for segment in plan.segments:
        if segment.net != net_id:
            continue
        for start, end in zip(segment.points, segment.points[1:]):
            pieces += 1
            length += abs(end[0] - start[0]) + abs(end[1] - start[1])
    return pieces, length


def _pitch(plan, arm) -> float:
    places = {item.part_id: (item.x, item.y) for item in plan.parts}
    first, second = arm["parts"]
    return math.hypot(places[second][0] - places[first][0],
                      places[second][1] - places[first][1])


# =============================================================== ① 能画出来


def test_the_series_mcu_island_draws_a_candidate():
    """当前前红：0 候选，base 轮点名 `R3` 压 `S1`。实现后至少 1 个候选。"""
    circuit, presentation, result = _compiled()
    assert result.candidates, (
        "the series MCU island draws nothing — the arm's corridor is taken by the "
        "keys before the arm is seated: "
        f"{[(f.category, f.subject, f.detail) for f in result.failures]}"
    )
    assert len(result.candidates) >= 1
    assert circuit.parts and presentation.modules


# ==================================================== ② 两条臂的阅读顺序


def test_every_candidate_reads_both_arms_in_the_declared_order():
    circuit, _presentation, result = _accepted()
    book = _book()
    members = ["U1", "C1", "C2", "C3", "R1", "R2", "R3", "D1", "D2",
               "S1", "S2", "S3", "S4", "BZ1"]
    problems = []
    for index, plan in enumerate(result.candidates):
        for arm in ARMS:
            for problem in _reading_problems(circuit, book, arm, plan, members):
                problems.append(f"candidate {index}: {problem}")
    assert not problems, "\n  ".join(["the declared order is not the drawing:"] + problems)


def test_every_candidate_draws_the_middle_node_as_a_short_link():
    _circuit, _presentation, result = _accepted()
    problems = []
    for index, plan in enumerate(result.candidates):
        for arm in ARMS:
            pieces, length = _middle_path(plan, arm["middleNet"])
            pitch = _pitch(plan, arm)
            if pieces == 0:
                problems.append(
                    f"candidate {index}: {arm['middleNet']} is not drawn as a link"
                )
            if pieces > 2:
                problems.append(
                    f"candidate {index}: {arm['middleNet']} is {pieces} pieces"
                )
            if pitch > 0 and length > 2.0 * pitch:
                problems.append(
                    f"candidate {index}: {arm['middleNet']} runs {length:g} for a "
                    f"{pitch:g}-unit pitch"
                )
    assert not problems, "\n  ".join(["the middle node is not a link:"] + problems)


# ========================================================= ③ 不压、不串、不断


def _part_boxes(plan, book):
    out = {}
    for item in plan.parts:
        profile = book[item.symbol_ref]
        pose = SymbolPose(rotation=int(item.rotation), mirror=bool(item.mirror))
        out[item.part_id] = dc._part_box(profile, pose, (item.x, item.y))
    return out


def test_no_two_parts_share_the_same_space():
    _circuit, _presentation, result = _accepted()
    book = _book()
    problems = []
    for index, plan in enumerate(result.candidates):
        boxes = _part_boxes(plan, book)
        for first in sorted(boxes):
            for second in sorted(boxes):
                if first >= second:
                    continue
                a, b = boxes[first], boxes[second]
                if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                    problems.append(
                        f"candidate {index}: {first} {a} overlaps {second} {b}"
                    )
    assert not problems, "\n  ".join(["two parts are drawn on each other:"] + problems)


def test_every_candidate_says_exactly_the_circuit():
    circuit, presentation, result = _accepted()
    book = _book()
    expected = _expected_pins(circuit, book)
    problems = []
    for index, plan in enumerate(result.candidates):
        derived = readability.derive_netlist(plan, book)
        placed = [item.part_id for item in plan.parts]
        if len(placed) != len(set(placed)):
            problems.append(f"candidate {index}: a part is placed twice: {sorted(placed)}")
        missing = sorted({part.id for part in circuit.parts} - set(placed))
        if missing:
            problems.append(f"candidate {index}: not placed: {missing}")
        unplaced = sorted(set(expected) - set(derived.pin_group))
        if unplaced:
            problems.append(f"candidate {index}: pins never placed: {unplaced}")
        for group in set(derived.pin_group.values()):
            nets = {expected.get(pin) for pin in group}
            if len(nets) > 1:
                problems.append(
                    f"candidate {index}: short: {group} joins nets {sorted(nets)}"
                )
        by_net: dict[str, set[str]] = {}
        for pin, net_id in expected.items():
            by_net.setdefault(net_id, set()).add(pin)
        for net_id, feet in sorted(by_net.items()):
            if len(feet) < 2:
                continue
            groups = {frozenset(derived.pin_group.get(pin, (pin,))) for pin in feet}
            if len(groups) > 1:
                problems.append(
                    f"candidate {index}: split: net {net_id} is {len(groups)} nodes"
                )
        hard = readability.check(plan, circuit, presentation, book).hard_violations
        for violation in hard:
            problems.append(f"candidate {index}: hard violation: {violation}")
        rules = [(text.kind, text.text) for text in plan.texts]
        for spec_part in circuit.parts:
            if ("reference", spec_part.id) not in rules:
                problems.append(f"candidate {index}: no reference row for {spec_part.id}")
            if spec_part.value and ("value", spec_part.value) not in rules:
                problems.append(
                    f"candidate {index}: no value row {spec_part.value!r} for "
                    f"{spec_part.id}"
                )
    assert not problems, "\n  ".join(["the drawing and the circuit disagree:"] + problems)


# ================================================ ④ 四键、语法层、未声明基线


def test_every_key_keeps_its_own_key_net():
    circuit, _presentation, result = _accepted()
    book = _book()
    expected = _expected_pins(circuit, book)
    problems = []
    for index, plan in enumerate(result.candidates):
        derived = readability.derive_netlist(plan, book)
        for key in ("S1", "S2", "S3", "S4"):
            key_net = f"KEY{key[-1]}"
            for pin, net_id in expected.items():
                if pin.split(".")[0] != key:
                    continue
                group = derived.pin_group.get(pin)
                if group is None:
                    problems.append(f"candidate {index}: {pin} is not placed")
                    continue
                others = {expected.get(other) for other in group}
                if others != {net_id}:
                    problems.append(
                        f"candidate {index}: {pin} sits with {sorted(others)} "
                        f"instead of {net_id!r} ({key_net})"
                    )
    assert not problems, "\n  ".join(["a key is wired to the wrong net:"] + problems)


def test_the_independent_checker_has_nothing_to_say():
    circuit, presentation, result = _accepted()
    book = _book()
    problems = []
    for index, plan in enumerate(result.candidates):
        findings = dc.check_grammar(plan, circuit, presentation, book)
        for finding in findings:
            problems.append(f"candidate {index}: {finding.render()}")
    assert not problems, "\n  ".join(["check_grammar reports:"] + problems)


def test_an_undeclared_page_keeps_the_old_refusal():
    """未声明必须逐项旧行为：同一文档今天本来就不出候选（GND 旗落在 D1.2 上，
    548D0 基线读数），声明路径不许把它的拒因换掉、也不许偷偷塞进串联座位。"""
    _circuit, _presentation, result = _compiled(declared=False)
    assert not result.candidates, (
        "an undeclared page gained a candidate — the reservation leaked into the "
        "no-declaration path"
    )
    assert result.failures, "refused with no reason"
    failure = result.failures[0]
    assert failure.category == dc.FAILURE_LAYOUT_UNSAT
    assert failure.subject == "GND", (
        "the undeclared refusal changed shape: "
        f"{[(f.category, f.subject) for f in result.failures]}"
    )
    assert "seriesBranches" not in failure.detail
