"""547C1: N >= 3 repeated two-terminal shunts must not short across their nets.

The 547A page is the measured trigger: one MCU island carrying four identical
key switches (each onto its own GPIO pad, other foot on +3V3), two status LEDs
and a buzzer (each onto its own GPIO pad, other foot on GND), plus the other
modules of the page whose signals make the MCU island state ~18 cross-module
labels. The current branch seater refuses that island — and, in one
configuration, draws two of the four key nets as one node
(``netlist-partition-mismatch`` on ``S3.1/S4.1/U1.PB13/U1.PB14``).

The trigger below was a **strict xfail reproduction of a known gap** (547C1
stopped after its last implementation attempt without a green). 548A's
repeat-bank gate (G9) now lets a row of three or more same-return shunts on one
host take its row body, and the island compiles with the four KEY nets as four
separate nodes. The assertions are the real regression; the pair control below
stays an ordinary passing test.
"""

from __future__ import annotations

import copy

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawcompiler as dc
from boardwise.engines import pagecompiler as pc
from boardwise.engines import readability


def _pin(number, name, tip, direction, length=10.0):
    return {"number": number, "name": name, "tip": tip, "direction": direction,
            "length": length, "pinType": "passive"}


def _symbol(ref, body, pins):
    return {"kind": "boardwise-symbol-profile", "profileVersion": 1,
            "symbolRef": ref, "title": ref, "body": body, "pins": pins,
            "source": "test fixture (547C1): the 547A logical library, inlined"}


_MCU_LEFT = ["VDD", "VSS", "VDDA", "VSSA", "VBAT", "NRST", "BOOT0", "PA13",
             "PA14", "PA8", "PA9", "PC8", "PC9", "PA6", "PC0"]
_MCU_RIGHT = ["PC4", "PC5", "PB0", "PA5", "PA7", "PA3", "PA4", "PC6", "PB15",
              "PB14", "PB13", "PB10", "PB11", "PD2", "PC12", "PB3", "PB6", "PB7"]


def _profiles():
    mcu = _symbol(
        "MCU32", [-70.0, -100.0, 70.0, 100.0],
        [_pin(n, n, [-80.0, 85 - 10 * i], "left") for i, n in enumerate(_MCU_LEFT)]
        + [_pin(n, n, [80.0, 85 - 10 * i], "right") for i, n in enumerate(_MCU_RIGHT)],
    )
    two = [-10.5, -4.5, 10.5, 4.5]
    cap = [-5.5, -8.5, 5.5, 8.5]
    return {
        "MCU32": mcu,
        "KEY": _symbol("KEY", [-12.0, -6.5, 12.0, 6.5],
                       [_pin("1", "1", [0.0, 20.0], "up"),
                        _pin("2", "2", [0.0, -20.0], "down")]),
        "LED": _symbol("LED", [-7.0, -5.5, 7.0, 5.5],
                       [_pin("1", "A", [-20.0, 0.0], "left"),
                        _pin("2", "K", [20.0, 0.0], "right")]),
        "BZ": _symbol("BZ", [-10.0, -10.0, 10.0, 10.0],
                      [_pin("1", "1", [-20.0, 0.0], "left"),
                       _pin("2", "2", [20.0, 0.0], "right")]),
        "R": _symbol("R", two, [_pin("1", "1", [-20.0, 0.0], "left"),
                                _pin("2", "2", [20.0, 0.0], "right")]),
        "C": _symbol("C", cap, [_pin("1", "1", [-20.0, 0.0], "left"),
                                _pin("2", "2", [20.0, 0.0], "right")]),
        "LCD": _symbol("LCD", [-20.0, -50.0, 20.0, 50.0],
                       [_pin(str(i), n, [-30.0, 40 - 10 * i], "left") for i, n in
                        enumerate(["VCC", "GND", "SCL", "SDA", "RES", "DC", "CS",
                                   "BLK"], start=1)]),
        "HDR4": _symbol("HDR4", [-20.0, -30.0, 20.0, 30.0],
                        [_pin("1", "3V3", [-30.0, 20.0], "left"),
                         _pin("2", "A", [-30.0, 10.0], "left"),
                         _pin("3", "B", [-30.0, 0.0], "left"),
                         _pin("4", "GND", [-30.0, -10.0], "left")]),
        "HDR6": _symbol("HDR6", [-20.0, -40.0, 20.0, 40.0],
                        [_pin(str(i), n, [-30.0, 30 - 10 * i], "left") for i, n in
                         enumerate(["VCC", "GND", "SCL", "SDA", "CSB", "SDO"], start=1)]),
        "HDR8": _symbol("HDR8", [-20.0, -45.0, 20.0, 45.0],
                        [_pin(str(i), n, [-30.0, 35 - 10 * i], "left") for i, n in
                         enumerate(["3V3", "GND", "TXD", "RXD", "EN", "RST", "IO0",
                                    "IO2"], start=1)]),
        "SEN4": _symbol("SEN4", [-25.0, -25.0, 25.0, 25.0],
                        [_pin(n, n, [-35.0, 15 - 10 * i], "left") for i, n in
                         enumerate(["VDD", "GND", "SCL", "SDA"])]),
    }


#: The 547A island, inlined: MCU + supply/BOOT0 support + four keys + two LEDs
#: + the buzzer. Eleven branches onto the host, five of them on one rail.
_MCU_PARTS = ["U1", "C1", "R1", "D1", "D2", "S1", "S2", "S3", "S4", "BZ1"]


def _circuit(with_panel: bool = True, with_page: bool = True):
    parts = [{"id": "U1", "symbolRef": "MCU32", "value": "STM32G431RBT6"}]
    nets = [
        {"id": "3V3", "class": "power",
         "members": ["U1.VDD", "U1.VDDA", "U1.VBAT", "C1.1"]},
        {"id": "GND", "class": "gnd",
         "members": ["U1.VSS", "U1.VSSA", "C1.2", "R1.2"]},
        {"id": "BOOT0", "class": "signal", "members": ["U1.BOOT0", "R1.1"]},
    ]
    parts += [{"id": "C1", "symbolRef": "C", "value": "100nF"},
              {"id": "R1", "symbolRef": "R", "value": "10k"}]
    if with_panel:
        for i, pin in enumerate(["PC6", "PB15", "PB14", "PB13"], start=1):
            parts.append({"id": f"S{i}", "symbolRef": "KEY", "value": "KEY"})
            nets.append({"id": f"KEY{i}", "class": "signal",
                         "members": [f"U1.{pin}", f"S{i}.1"]})
            nets[0]["members"].append(f"S{i}.2")
        for i, pin in enumerate(["PA3", "PA4"], start=1):
            parts.append({"id": f"D{i}", "symbolRef": "LED", "value": "LED"})
            nets.append({"id": f"LED{i}", "class": "signal",
                         "members": [f"U1.{pin}", f"D{i}.1"]})
            nets[1]["members"].append(f"D{i}.2")
        parts.append({"id": "BZ1", "symbolRef": "BZ", "value": "BUZZER"})
        nets.append({"id": "BUZZ", "class": "signal",
                     "members": ["U1.PC0", "BZ1.1"]})
        nets[1]["members"].append("BZ1.2")

    # the page's other modules: their signals are what give the MCU island its
    # cross-module labels, exactly as on the 547A page
    if with_page:
        parts += [
            {"id": "J1", "symbolRef": "LCD", "value": "ST7789"},
            {"id": "J2", "symbolRef": "HDR8", "value": "ESP-01S"},
            {"id": "J3", "symbolRef": "HDR4", "value": "UART1"},
            {"id": "J4", "symbolRef": "HDR4", "value": "SWD"},
            {"id": "U2", "symbolRef": "SEN4", "value": "AHT20"},
            {"id": "U3", "symbolRef": "HDR6", "value": "BMP280"},
            {"id": "C2", "symbolRef": "C", "value": "100nF"},
            {"id": "C3", "symbolRef": "C", "value": "100nF"},
            {"id": "C4", "symbolRef": "C", "value": "100nF"},
            {"id": "R2", "symbolRef": "R", "value": "10k"},
            {"id": "R3", "symbolRef": "R", "value": "10k"},
        ]
        nets[0]["members"] += ["J1.VCC", "J2.3V3", "J3.1", "J4.1", "U2.VDD",
                               "U3.VCC", "C2.1", "C3.1", "C4.1", "R2.1", "R3.1"]
        nets[1]["members"] += ["J1.GND", "J1.CS", "J2.GND", "J3.4", "J4.4",
                               "U2.GND", "U3.GND", "U3.SDO", "C2.2", "C3.2", "C4.2"]
    for net_id, members in (
        ("LCD_SCK", ["U1.PA5", "J1.SCL"]),
        ("LCD_SDA", ["U1.PA7", "J1.SDA"]),
        ("LCD_RES", ["U1.PC4", "J1.RES"]),
        ("LCD_DC", ["U1.PC5", "J1.DC"]),
        ("LCD_BLK", ["U1.PB0", "J1.BLK"]),
        ("I2C2_SCL", ["U1.PA9", "J2.RXD"]),
        ("I2C2_SDA", ["U1.PA8", "J2.TXD"]),
        ("I2C3_SCL", ["U1.PC8", "U2.SCL", "U3.SCL"]),
        ("I2C3_SDA", ["U1.PC9", "U2.SDA", "U3.SDA"]),
        ("ESP_EN", ["U1.PD2", "J2.EN", "R2.2"]),
        ("ESP_RST", ["U1.PC12", "J2.RST", "R3.2"]),
        ("ESP_IO0", ["U1.PB3", "J2.IO0"]),
        ("USART1_TX", ["U1.PB6", "J3.2"]),
        ("USART1_RX", ["U1.PB7", "J3.3"]),
        ("SWDIO", ["U1.PA13", "J4.2"]),
        ("SWCLK", ["U1.PA14", "J4.3"]),
    ) if with_page else ():
        nets.append({"id": net_id, "class": "signal", "members": members})
    return {"kind": "boardwise-circuit-spec", "specVersion": 1, "parts": parts,
            "nets": [dict(n, provenance="ai_asserted") for n in nets], "nc": []}


def _presentation(with_panel: bool = True, with_page: bool = True):
    return {
        "kind": "boardwise-presentation-spec", "specVersion": 1,
        "grammarRef": "ic-periphery",
        "sidePreferences": {"input": "right", "output": "right", "load": "right",
                            "source": "left", "power": "top", "gnd": "bottom"},
        "modules": [
            {"id": "mcu", "parts": list(_MCU_PARTS) if with_panel else ["U1", "C1", "R1"],
             "role": "host island", "grammarRef": "ic-periphery", "core": "U1"},
        ] + ([
            {"id": "lcd", "parts": ["J1"], "role": "lcd", "grammarRef": "ic-periphery",
             "core": "J1"},
            {"id": "wifi", "parts": ["J2", "C2"], "role": "wifi",
             "grammarRef": "ic-periphery", "core": "J2"},
            {"id": "uart1", "parts": ["J3"], "role": "uart", "grammarRef": "ic-periphery",
             "core": "J3"},
            {"id": "swd", "parts": ["J4"], "role": "swd", "grammarRef": "ic-periphery",
             "core": "J4"},
            {"id": "env", "parts": ["U2", "C3"], "role": "env", "grammarRef": "ic-periphery",
             "core": "U2"},
            {"id": "bmp", "parts": ["U3", "C4"], "role": "optional bmp",
             "grammarRef": "ic-periphery", "core": "U3"},
        ] if with_page else []),
        "moduleOrder": (["mcu", "lcd", "wifi", "uart1", "swd", "env", "bmp"]
                        if with_page else ["mcu"]),
        "moduleColumns": 3,
        "labelPolicy": {"local": "wire", "crossModule": "label", "highFanout": "label",
                        "stub": "straight", "stubMin": 40, "rowModel": "centered"},
        "flagLeadLimit": 120,
        "gndClustering": {"radius": 100},
        "serviceLayout": {"pinGap": 30},
    }


def _book():
    return {p.symbol_ref: p for p in
            (SymbolProfile.from_dict(copy.deepcopy(v)) for v in _profiles().values())}


def _module_documents(circuit_payload, presentation_payload):
    """The MCU island's own view of both documents (the pair `_compile` draws)."""
    circuit = CircuitSpec.from_dict(copy.deepcopy(circuit_payload))
    presentation = PresentationSpec.from_dict(copy.deepcopy(presentation_payload))
    return pc._module_view(circuit, presentation, presentation.module("mcu"))


def _compile(circuit_payload, presentation_payload):
    local_circuit, local_presentation = _module_documents(
        circuit_payload, presentation_payload)
    return dc.compile(local_circuit, local_presentation, _book())


def _pin_points(plan, book):
    """Every placed part's pin tips, in page coordinates (canvas space)."""
    from boardwise.core.geometry import transform_point

    out = {}
    for placed in plan.parts:
        profile = book[placed.symbol_ref]
        for pin in profile.pins:
            out[(placed.part_id, pin.number)] = transform_point(
                pin.tip[0], pin.tip[1], rotation=placed.rotation,
                mirror=placed.mirror, ox=placed.x, oy=placed.y,
            )
            out[(placed.part_id, pin.name)] = out[(placed.part_id, pin.number)]
    return out


def _partition(plan, book):
    """Connected components of the drawn conductors, by geometry only.

    Pin tips, wire vertices and every wire's interior are joined where they
    touch, so two pins are one node only when the drawing really joins them —
    the reading the host's own netlist takes.
    """
    points = _pin_points(plan, book)
    parent = {}

    def find(key):
        parent.setdefault(key, key)
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    def on_segment(p, a, b):
        (px, py), (ax, ay), (bx, by) = p, a, b
        if abs((bx - ax) * (py - ay) - (by - ay) * (px - ax)) > 1e-6:
            return False
        return (min(ax, bx) - 1e-6 <= px <= max(ax, bx) + 1e-6
                and min(ay, by) - 1e-6 <= py <= max(ay, by) + 1e-6)

    for index, segment in enumerate(plan.segments):
        points[("wire", index)] = tuple(segment.points[0])
        for point in segment.points:
            union(("wire", index), ("pt", tuple(point)))
        for key, tip in list(points.items()):
            for a, b in zip(segment.points, segment.points[1:]):
                if on_segment(tip, tuple(a), tuple(b)):
                    union(key, ("wire", index))
    for key_a, tip_a in list(points.items()):
        for key_b, tip_b in list(points.items()):
            if key_a != key_b and tip_a == tip_b:
                union(key_a, key_b)
    return {key: find(key) for key in points}


def test_four_keys_two_lamps_and_a_buzzer_draw_without_a_cross_net_short():
    """The 547A trigger: the MCU island must have a candidate, every panel
    branch must be placed, and the four KEY nets must be four different nodes."""
    result = _compile(_circuit(), _presentation())
    assert result.ok, result.render_failures()
    plan = result.candidates[0]
    book = {p.symbol_ref: p for p in
            (SymbolProfile.from_dict(copy.deepcopy(v)) for v in _profiles().values())}
    nodes = _partition(plan, book)
    for part in ("S1", "S2", "S3", "S4", "D1", "D2", "BZ1"):
        assert plan.part(part) is not None, f"{part} is not placed"
    components = {}
    for i, (mcu_pin, switch_pin) in enumerate(
        [("PC6", "S1"), ("PB15", "S2"), ("PB14", "S3"), ("PB13", "S4")], start=1
    ):
        assert plan.part(switch_pin) is not None, f"{switch_pin} is not placed"
        here = nodes.get(("U1", mcu_pin))
        there = nodes.get((switch_pin, "1"))
        assert here is not None and there is not None, f"KEY{i} pin is not drawn"
        assert here == there, (
            f"KEY{i}: U1.{mcu_pin} and {switch_pin}.1 are drawn as different nodes")
        components[f"KEY{i}"] = here
        # the switch's return pin may not share the key's node: that is the
        # own-two-pins short the viewer reads as `S1.1 + S1.2 + S2.1 ...`
        ret = nodes.get((switch_pin, "2"))
        assert ret is not None and ret != here, (
            f"KEY{i}: {switch_pin}'s return pin is drawn as its own KEY node")
    assert len(set(components.values())) == 4, (
        "the four KEY nets were drawn as one or more merged nodes: "
        + repr({k: v for k, v in components.items()}))


def test_two_branches_keep_the_pair_drawing():
    """The unpressed control: with no panel branches the island still compiles."""
    result = _compile(_circuit(with_panel=False, with_page=False),
                      _presentation(with_panel=False, with_page=False))
    assert result.ok, result.render_failures()


def test_lamps_and_buzzer_are_two_terminal_branches_of_a_fully_declared_island():
    """548A-R: the gap the 547C1 test leaves — it proves D1/D2/BZ1 are *placed*
    and reads only the four KEY nets, so "the lamps and the buzzer are right"
    was never asserted. Here each of the three branches is read back as a branch
    (host pin on the signal node, return pin on the return node, the two never
    one node), the seven panel signals are seven nodes, and the drawing's whole
    partition is compared against the local CircuitSpec's — every declared part
    placed, every declared pin drawn, 0 undeclared node, 0 split net.

    The netlist is ``readability.derive_netlist``: the host's own reading of the
    picture (pin tips, wire taps, label and flag names, no spec input). Being
    the host's reading and not a second guess from the fixture, an editor-legal
    same-name joining shows up as the single node the editor would build rather
    than as a short this test invented.
    """
    circuit_payload, presentation_payload = _circuit(), _presentation()
    result = _compile(circuit_payload, presentation_payload)
    assert result.ok, result.render_failures()
    plan = result.candidates[0]
    net = readability.derive_netlist(plan, _book())
    local_circuit, _ = _module_documents(circuit_payload, presentation_payload)

    # 0 unplaced — and nothing on the page the island does not declare
    placed = {part.part_id for part in plan.parts}
    declared_parts = {part.id for part in local_circuit.parts}
    assert placed == declared_parts, (
        f"parts drawn {sorted(placed)} vs parts declared {sorted(declared_parts)}")

    # every declared pin is on the page and has a conductor on it
    declared = {member: spec_net.id for spec_net in local_circuit.nets
                for member in spec_net.members}
    absent = sorted(pin for pin in declared if pin not in net.pin_points)
    assert not absent, f"declared pins are missing from the drawing: {absent}"
    floating = sorted(pin for pin in declared if pin not in net.wired_pins)
    assert not floating, f"declared pins are drawn with nothing on them: {floating}"

    # 0 undeclared node: a node holding two pins is one declared net, or the
    # drawing has added a connection the spec does not make
    joined = [(group, {declared.get(pin) for pin in group})
              for group in net.groups if len(group) > 1]
    undeclared = [(group, names) for group, names in joined
                  if len(names) != 1 or None in names]
    assert not undeclared, (
        f"the drawing joins pins the spec keeps apart: {undeclared}")

    # 0 split net: every declared net of two or more pins is exactly one node
    split = [(spec_net.id, sorted(spec_net.members))
             for spec_net in local_circuit.nets if len(spec_net.members) > 1
             and len({net.group_of(member) for member in spec_net.members}) != 1]
    assert not split, f"declared nets are drawn as several nodes: {split}"

    # the names the drawing states on a node are the net the spec puts there
    misnamed = [(group, net.node_names[group],
                 tuple(sorted({declared[pin] for pin in group if pin in declared})))
                for group in net.node_names]
    misnamed = [item for item in misnamed if item[1] != item[2]]
    assert not misnamed, f"a node states a net name the spec does not: {misnamed}"

    gnd = net.group_of("U1.VSS")
    assert gnd is not None, "the MCU's ground pin is not drawn"
    for host_pin, device, signal_net in (
        ("U1.PA3", "D1", "LED1"), ("U1.PA4", "D2", "LED2"),
        ("U1.PC0", "BZ1", "BUZZ"),
    ):
        signal = net.group_of(host_pin)
        assert declared[host_pin] == signal_net, (
            f"{host_pin} is not declared on {signal_net}")
        assert signal == net.group_of(f"{device}.1"), (
            f"{signal_net}: {host_pin} and {device}.1 are drawn as different nodes")
        assert set(signal) == {host_pin, f"{device}.1"}, (
            f"{signal_net} is drawn with more than the branch's two pins: {signal}")
        # the branch's own return pin is on the return node, and the branch is
        # not a wire across the device
        assert net.group_of(f"{device}.2") == gnd, (
            f"{signal_net}: {device}.2 is not on the return node {gnd}")
        assert signal != gnd, (
            f"{signal_net}: {device}'s signal and return pins are one node")

    # the seven panel signals are seven nodes: a lamp, the buzzer and the four
    # keys may not share a GPIO node, and none of them sits on the return node
    panel = {"LED1": "U1.PA3", "LED2": "U1.PA4", "BUZZ": "U1.PC0",
             "KEY1": "U1.PC6", "KEY2": "U1.PB15", "KEY3": "U1.PB14",
             "KEY4": "U1.PB13"}
    nodes = {name: net.group_of(pin) for name, pin in panel.items()}
    assert len(set(nodes.values())) == len(nodes), (
        f"panel signals were drawn onto fewer nodes: {nodes}")
    assert gnd not in set(nodes.values()), (
        f"a panel signal was drawn onto the return node {gnd}")
