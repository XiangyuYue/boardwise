"""548P116: an open port's run is only half its ink.

The port's conductor may be clear while the **name the host prints on it** is
not: `textmetrics.wire_name_box` centres that row on the run's midpoint and
prints it towards +x, so a run that leaves the pin to the left still writes its
name back to the right, into a body standing beside the port (measured on the
WiFi page: a 40-unit `ESP_RXD` at x385 reaching x418.368 into J2 at x415).
`_reserve_open_ports` therefore walks the printer's existing rungs
(`LOCAL_LABEL_RUNGS` x grid) up from the stated `stubMin`, keeps the stated
length verbatim whenever its own row is clear, and refuses by name when no rung
fits. Nothing here is hand-picked: the length follows from the page's grid.
"""

from __future__ import annotations

import copy

from boardwise.core import textmetrics
from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawcompiler as dc

PROV = "verified_recipe"
PAGE = (0.0, 0.0, 1170.0, 825.0)
BODY = (-40.0, -40.0, 40.0, 40.0)
PARTS = ["U1", "R1", "R2"]
OPEN = "SIG_OUT"


# --------------------------------------------------------------- 合成夹具


def _pin(number: str, tip, direction: str) -> dict:
    return {"number": number, "name": number, "tip": list(tip),
            "direction": direction, "length": 10.0, "pinType": "passive"}


def _symbol(ref: str, body, pins) -> dict:
    return {"kind": "boardwise-symbol-profile", "profileVersion": 1,
            "symbolRef": ref, "title": ref, "body": list(body), "pins": pins,
            "source": "test fixture (548P116)"}


def _book() -> dict[str, SymbolProfile]:
    payloads = {
        # 开放脚在**左侧**：40 单位的 run 向左离开 pin，宿主却把名字从 run 中点
        # 向右印，正好回撞自身 body（x = -40）。
        "HOST4L": _symbol("HOST4L", BODY, [
            _pin("VDD", [50.0, 30.0], "right"),
            _pin("CFG_A", [50.0, 20.0], "right"),
            _pin("CFG_B", [50.0, 10.0], "right"),
            _pin("TX", [-50.0, -20.0], "left"),
            _pin("GND", [0.0, 50.0], "up"),
        ]),
        "R": _symbol("R", [-10.5, -4.5, 10.5, 4.5], [
            _pin("1", [-20.0, 0.0], "left"),
            _pin("2", [20.0, 0.0], "right"),
        ]),
        "PWR-PWR": _symbol("PWR-PWR", [-6.0, 0.0, 6.0, 18.0], []),
        "PWR-GND": _symbol("PWR-GND", [-10.0, 0.0, 10.0, 19.0], []),
    }
    return {
        ref: SymbolProfile.from_dict(copy.deepcopy(payload))
        for ref, payload in payloads.items()
    }


def _part(part_id: str, symbol: str, value: str = "") -> dict:
    return {"id": part_id, "symbolRef": symbol, "value": value,
            "provenance": PROV}


def _net(net_id: str, cls: str, members) -> dict:
    return {"id": net_id, "class": cls, "members": list(members),
            "provenance": PROV}


def _circuit(open_net: str = OPEN) -> CircuitSpec:
    return CircuitSpec.from_dict({
        "parts": [
            _part("U1", "HOST4L", "HOST"),
            _part("R1", "R", "10k"),
            _part("R2", "R", "10k"),
        ],
        "nets": [
            _net("CFG_A", "signal", ["U1.CFG_A", "R1.1"]),
            _net("CFG_B", "signal", ["U1.CFG_B", "R2.1"]),
            _net("PWR", "power", ["U1.VDD", "R1.2", "R2.2"]),
            _net("GND", "gnd", ["U1.GND"]),
            _net(open_net, "signal", ["U1.TX"]),
        ],
    })


def _spec() -> PresentationSpec:
    return PresentationSpec.from_dict({
        "grammarRef": "ic-periphery",
        "sidePreferences": {"input": "right", "output": "right",
                            "load": "right", "source": "left",
                            "power": "top", "gnd": "bottom"},
        "modules": [{
            "id": "m", "parts": list(PARTS), "role": "host island",
            "grammarRef": "ic-periphery", "core": "U1",
        }],
        "labelPolicy": {"local": "wire", "crossModule": "label",
                        "highFanout": "label", "stubMin": 40.0},
    })


def _prepared(open_net: str = OPEN) -> dc._Context:
    circuit, spec, book = _circuit(open_net), _spec(), _book()
    binding = dc.bind_grammar(circuit, spec, book)
    assert binding.ok, [item.detail for item in binding.failures]
    binding = dc._with_panel_groups(binding, spec, circuit)
    binding = dc._with_service_groups(binding, spec, circuit, book)
    budget = dc.CompileBudget(max_candidates=4, page_box=PAGE, grid=10.0)
    prepared = dc._prepare(circuit, spec, binding, book, budget)
    assert prepared.context is not None, [
        item.detail for item in prepared.failures]
    return prepared.context


def _reserved(open_net: str = OPEN):
    ctx = _prepared(open_net)
    placed, failure = dc._place(
        ctx, dc._variants(ctx)[0], seat_service_groups=False)
    assert placed is not None, failure
    ports = dc._reserve_open_ports(ctx, placed)
    assert not isinstance(ports, dc.GrammarFailure), ports.detail
    port = next(item for item in ports if item.net == open_net)
    return ctx, placed, port


def _straight(start, direction, length):
    reach = float(length)
    return [
        (start[0], start[1]),
        (start[0] + direction[0] * reach, start[1] + direction[1] * reach),
    ]


def _length(points) -> float:
    return sum(
        abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in zip(points, points[1:]))


def test_stated_stub_length_is_extended_only_until_its_name_row_clears_the_body():
    ctx, placed, port = _reserved()
    grid = ctx.budget.grid
    start = dc._pin_point(ctx, "U1", "TX", placed.poses, placed.origins)
    direction = dc._pin_direction(ctx, "U1", "TX", placed.poses)
    body = dc._body_box(
        ctx.profile("U1"), placed.poses["U1"], placed.origins["U1"])
    assert body is not None

    # 反向实验：stated 40 单位的 run 本身合法，但宿主行（真正的印字位置）回撞 body。
    stated_row = textmetrics.wire_name_box(
        [list(p) for p in _straight(start, direction, 40.0)], OPEN)
    assert stated_row is not None
    assert dc._overlaps(stated_row, body), stated_row

    # 新 run：从 pin 出发，宿主的真实 name row 不再压到 body。
    assert port.run[0] == start
    host_row = textmetrics.wire_name_box([list(p) for p in port.run], OPEN)
    assert host_row is not None
    assert not dc._overlaps(host_row, body), host_row

    # 长度不是手填的：它是「上一档仍撞、这一档才清」的第一个既有梯级。
    total = _length(port.run)
    assert total == 50.0
    assert abs((total - 40.0) / grid - round((total - 40.0) / grid)) < 1e-9
    previous = total - grid
    previous_row = textmetrics.wire_name_box(
        [list(p) for p in _straight(start, direction, previous)], OPEN)
    assert previous_row is not None
    assert dc._overlaps(previous_row, body), previous_row

    # 后续文本/电气锚保持原样：label 仍锚在 run 的远端。
    assert port.label.x == port.run[-1][0]
    assert port.label.y == port.run[-1][1]


def test_a_clear_stated_run_keeps_its_original_geometry_verbatim():
    """The same left-hand port with a short name keeps the historical 40 units.

    The stated length is only left behind when its own printed row collides;
    here `TX_RX` stays inside the gap beside the body, so the run is the stated
    one, straight from the pin, unchanged.
    """

    ctx, placed, port = _reserved("TX_RX")
    start = dc._pin_point(ctx, "U1", "TX", placed.poses, placed.origins)
    direction = dc._pin_direction(ctx, "U1", "TX", placed.poses)
    body = dc._body_box(
        ctx.profile("U1"), placed.poses["U1"], placed.origins["U1"])
    row = textmetrics.wire_name_box([list(p) for p in port.run], "TX_RX")
    assert row is not None
    assert not dc._overlaps(row, body), row
    assert _length(port.run) == 40.0
    assert port.run[-1] == _straight(start, direction, 40.0)[-1]

