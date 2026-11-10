"""548B3-R：声明过的臂**构造不出合法座位**时，必须被具名拒绝，不许静默留下旧布局。

548B3 的正例（`test_548b_series_geometry.py`）证明：声明能在**能落座**的页面上
决定几何。它没有覆盖失败路径——`_seat_series_arms` 在缺 host、缺合法 pose、
座位撞到别的器件时一律 `continue`，于是"声明"在这些页面上等于没写：编译照旧
返回候选，候选里画的还是那条折返的旧布局，而 `compile` 报 ok。本文件用**两条
真实负例**把这条路封住：

* **① 没有可用合法 pose**：同一份 548B1/B2 合法的高边文档，符号库声明 LED 只能
  以 rotation 0 画（两条脚水平）。这张图的链方向是竖直的（`progress` 由文档自己
  的 side preference 决定），于是 `parts[1]` 没有任何合法姿态能让 A→K 顺着链走。
  今天它照旧编译成功、返回候选；修好后该 variant 被拒绝，失败里点名臂与件。
* **② 座位撞上别的器件**：同一条 548B1/B2 合法的高边文档，3V3/GND 上再加一颗
  10u 电解 C1（去耦，跟这条臂无关）。链方向由文档自己的 side preference 决定，
  而某些 variant 里 `parts[0]` 的座位正好落在 C1 身上——今天这个 variant 悄悄
  退回旧布局、把那条折返的图当候选交出去；修好后它被具名拒绝（点名臂与撞到的
  C1），而其它能干净落座的 variant 仍然是候选，且**任何返回的候选都不许是
  那条旧布局**。

两条负例的电路与声明本身都先过 548B1/B2（`compile` 已经走到布局阶段，548B2 的
跨文档校验没有报错），不是拿非法输入冒充几何失败。这里不写 `userLocks`、不指定
坐标、不动硬闸/排序/候选集合；读图只用 `readability.derive_netlist` 与符号自己的
引脚表，按声明的顺序取五个点问"有没有回退"。
"""

from __future__ import annotations

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolPin, SymbolPose, SymbolProfile
from boardwise.engines import drawcompiler as dc
from boardwise.engines import readability

PROV = "verified_recipe"

#: 与几何正例同一条容差：两个点在同一档上（差值 ≤ 1 单位）不算回退。
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


def _bulk_cap() -> SymbolProfile:
    """10u 电解：体 50×70、两脚 120 高——一颗真的会挡住座位的大件。"""
    return SymbolProfile(
        symbol_ref="C-ELEC", title="Electrolytic", body=(-25.0, -35.0, 25.0, 35.0),
        pins=_pins((("1", "1", (0.0, 60.0), "up"), ("2", "2", (0.0, -60.0), "down"))),
    )


def _flag(ref: str) -> SymbolProfile:
    return SymbolProfile(
        symbol_ref=ref, title=ref, body=(-6.0, 0.0, 6.0, 18.0), pins=[]
    )


def _library(led_poses: list[SymbolPose] | None = None) -> dict[str, SymbolProfile]:
    led = _led()
    if led_poses is not None:
        # 库的一声明说：这颗 LED 只有这些合法姿态（声明式，不是伪造的几何）。
        led = SymbolProfile(
            symbol_ref=led.symbol_ref, title=led.title, body=led.body,
            pins=list(led.pins), poses=list(led_poses), pose_source="declared",
        )
    book = {"MCU32": _mcu(), "R0402": _resistor(), "LED0805": led,
            "C-ELEC": _bulk_cap()}
    for name in ("PWR-GND", "PWR-3V3", "PWR-VIN", "PWR-VIN5"):
        book[name] = _flag(name)
    return book


# ---------------------------------------------------------------- 手写文档
def _part(part_id: str, symbol: str, value: str = "") -> dict:
    return {"id": part_id, "symbolRef": symbol, "value": value, "provenance": PROV}


def _net(net_id: str, cls: str, members: list[str]) -> dict:
    return {"id": net_id, "class": cls, "members": list(members), "provenance": PROV}


MODULE = {"id": "mcu", "role": "status led", "grammarRef": "ic-periphery", "core": "U1"}

#: 548B1/B2 的高边正例文档：GPIO → R → LED → GND。
_HIGH_PARTS = [_part("U1", "MCU32", "MCU"), _part("R2", "R0402", "1k"),
               _part("LED1", "LED0805", "red")]
_HIGH_NETS = [_net("GPIO_STAT", "signal", ["U1.PA5", "R2.1"]),
              _net("LED_A", "signal", ["R2.2", "LED1.A"]),
              _net("GND", "gnd", ["U1.VSS", "LED1.K"]),
              _net("3V3", "power", ["U1.VDD"])]
_HIGH_ARM = {"id": "status-led", "from": "GPIO_STAT", "to": "GND",
             "parts": ["R2", "LED1"], "middleNet": "LED_A"}

#: 负例 ②：同一条高边电路，3V3/GND 上多一颗 10u 电解 C1（去耦，与臂无关）。
#: 某些 variant 里臂的座位会压在这颗电容身上。
_CLASH_PARTS = _HIGH_PARTS + [_part("C1", "C-ELEC", "10u")]
_CLASH_NETS = [_net("GPIO_STAT", "signal", ["U1.PA5", "R2.1"]),
               _net("LED_A", "signal", ["R2.2", "LED1.A"]),
               _net("GND", "gnd", ["U1.VSS", "LED1.K", "C1.2"]),
               _net("3V3", "power", ["U1.VDD", "C1.1"])]
_CLASH_ARM = dict(_HIGH_ARM)


def _presentation(arm: dict, parts: list[str]) -> PresentationSpec:
    return PresentationSpec.from_dict({
        "grammarRef": "ic-periphery",
        "modules": [dict(MODULE, parts=list(parts))],
        "seriesBranches": [dict(arm)],
    })


def _compile(parts, nets, arm, members, book) -> dc.CompileResult:
    circuit = CircuitSpec.from_dict({"parts": parts, "nets": nets})
    presentation = _presentation(arm, members)
    return dc.compile(circuit, presentation, book)


def _pose_starved():
    """① 高边正例的电路与声明，但库只许 LED 以 rotation 0 画。"""
    return _compile(
        _HIGH_PARTS, _HIGH_NETS, _HIGH_ARM, ["U1", "R2", "LED1"],
        _library(led_poses=[SymbolPose(rotation=0, mirror=False)]),
    )


def _seat_clash():
    """② 高边臂 + 同轨 10u 电解 C1。"""
    return _compile(
        _CLASH_PARTS, _CLASH_NETS, _CLASH_ARM, ["U1", "R2", "LED1"], _library(),
    )


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


def _arm_points(circuit, book, arm, plan, members):
    """宿主 + `parts[0]` 两脚 + `parts[1]` 两脚，按声明的顺序，从图上取。

    "宿主"与 548B2 的 V6 同一条读法：from 网上**同模块内**、臂以外的那只脚。
    """
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
    return [derived.pin_points[hosts[0]]] + [
        derived.pin_points[pin] for pin in wanted
    ]


def _steps_back(points) -> list[str]:
    """按声明顺序走，是否有任何一步沿着链轴回退（方向由第一步决定）。"""
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    axis = 0 if (max(xs) - min(xs)) >= (max(ys) - min(ys)) else 1
    values = [point[axis] for point in points]
    steps = [values[index + 1] - values[index] for index in range(len(values) - 1)]
    first = next((step for step in steps if abs(step) > TOLERANCE), 0.0)
    if abs(first) <= TOLERANCE:
        return [f"the arm has no extent along {'xy'[axis]}: {values}"]
    direction = 1.0 if first > 0 else -1.0
    return [
        f"step {index} goes back along {'xy'[axis]}: {values[index]:g} -> "
        f"{values[index + 1]:g} while the arm starts at {values[0]:g} -> "
        f"{values[1]:g}"
        for index, step in enumerate(steps)
        if direction * step < -TOLERANCE
    ]


# ============================================================ ① 没有合法 pose


def test_an_arm_with_no_legal_pose_is_refused_by_name():
    """`parts[1]` 没有任何合法 pose 能顺着链画 → 该 variant 被具名拒绝。"""
    result = _pose_starved()
    drawn = [
        [(item.part_id, item.x, item.y) for item in plan.parts]
        for plan in result.candidates
    ]
    assert not result.ok, (
        "a declared arm the layout cannot seat still compiled: the pass kept the "
        f"old layout and the declaration is only graded, never drawn — {drawn}"
    )
    assert result.candidates == []
    assert result.failures, "refused with no reason at all"
    failure = result.failures[0]
    assert failure.category == dc.FAILURE_LAYOUT_UNSAT, (
        f"refused under a category that is not the existing one: {failure.category}"
    )
    rendered = " ".join([failure.subject, failure.detail, failure.action])
    assert _HIGH_ARM["id"] in rendered, (
        f"the refusal does not name the arm: {failure.subject!r} / {failure.detail}"
    )
    assert "LED1" in failure.detail, (
        f"the refusal does not name the part with no usable pose: {failure.detail}"
    )
    assert "pose" in failure.detail.lower()
    assert failure.action.strip(), "a refusal without an action a reader can take"


# ============================================================== ② 座位冲突


def test_a_seat_that_would_bury_another_part_is_refused_by_name():
    """座位会压在 C1 上的 variant 被拒绝，失败里点名臂与那颗件。"""
    result = _seat_clash()
    refused = [
        rejected.failure for rejected in result.rejected
        if rejected.failure is not None
        and rejected.failure.category == dc.FAILURE_LAYOUT_UNSAT
    ]
    named = [
        failure for failure in refused
        if _CLASH_ARM["id"] in " ".join(
            [failure.subject, failure.detail, failure.action]
        )
    ]
    assert named, (
        "no variant was refused for the seat it could not take: the clashing "
        f"variant kept the old layout and returned a candidate — refused={refused}"
    )
    failure = named[0]
    assert "C1" in failure.detail, (
        f"the refusal does not name the part the seat would bury: {failure.detail}"
    )
    assert failure.action.strip(), "a refusal without an action a reader can take"


def test_no_candidate_keeps_the_layout_the_arm_replaces():
    """任何返回的候选都必须按声明顺序画这条臂——旧的折返布局不许当候选。"""
    result = _seat_clash()
    assert result.ok, (
        "the variants that can seat the arm still have to compile: "
        f"{[(f.category, f.detail) for f in result.failures]}"
    )
    circuit = CircuitSpec.from_dict({"parts": _CLASH_PARTS, "nets": _CLASH_NETS})
    book = _library()
    problems = []
    for index, plan in enumerate(result.candidates):
        points = _arm_points(circuit, book, _CLASH_ARM, plan, ["U1", "R2", "LED1"])
        if points is None:
            problems.append(f"candidate {index}: the arm's five points are not on the page")
            continue
        for problem in _steps_back(points):
            problems.append(f"candidate {index}: {problem}")
    assert not problems, (
        "a candidate keeps the layout the declaration is supposed to replace:\n  "
        + "\n  ".join(problems)
    )
