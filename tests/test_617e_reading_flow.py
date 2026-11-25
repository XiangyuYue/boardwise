"""617E: the main signal chain reads left-to-right on one row (agent-adjusted input).

617C's fix left every candidate at `backflow > 0`: `moduleColumns=2` folded
`usb_c -> ch343 -> hdr` over two rows, leaving the right half of the sheet empty.
The 617D page is otherwise unchanged. This batch does **not** touch production;
it pins an agent-adjusted presentation (`evidence/617e/effective.presentation.json`)
that differs from the 543d input in exactly one field, `moduleColumns: 3`, and
asks the real page compiler what that input draws.

What the tests hold, and why each one can fail:

* the adjusted input differs from 543d by that one line and nothing else;
* every candidate's `page_backflow_length` is 0 (the 2-column input measured
  574.5..606, so this is a causal reading, not a count of candidates);
* the chain's origins run `usb_c < ch343 < hdr` on one row and `led` sits on
  the second row; the delivered page puts H1 to the right of U1 with its
  pin-1 column (TXD/RTS/DTR/DCD) facing the bridge;
* 617D's RXD repair survives: stub 20 (< the 96-unit defect), C3 reference
  gap >= 2;
* every pin still lands and every net is one run: 11 parts / 58 pins / 17 nets,
  the same classes 617C reported.

The input is agent-adjusted, not an automatic replay: the PROVENANCE in
`evidence/617e/` records both SHAs and the single-field diff.
"""
from __future__ import annotations

import difflib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from boardwise.core.circuitspec import CircuitSpec  # noqa: E402
from boardwise.core.presentationspec import PresentationSpec  # noqa: E402
from boardwise.engines import drawapply, drawcompiler as dc  # noqa: E402
from boardwise.engines import pagecompiler as pc  # noqa: E402

SPECS = ROOT / "blocklib" / "specs"
CIRCUIT = SPECS / "ch343_uart_534a.circuit.json"
LIBRARY = SPECS / "ch343_uart_v4.library.json"
PRESENTATION = ROOT / "evidence" / "617e" / "effective.presentation.json"
ORIGINAL = ROOT / "evidence" / "543d" / "effective.presentation.json"
PAGE_BOX = (0.0, 0.0, 1170.0, 825.0)

#: 617D reserved `U1.3 RXD` 96 units from its pin; the repair sits at 20.
PRE_FIX_STUB = 96.0
#: S-21's text floor, the number 617D used for the C3 reference gap.
TEXT_FLOOR = 2.0
#: The 617C landing/connectivity outcome this batch must not move.
CLASSES = {"wire-end": 35, "wire": 2, "nc": 3, "named": 18}
#: H1's pin-1 column (odd pins 1,3,5,7) and pin-2 column (even pins 2,4,6,8).
ODD_PIN_NETS = {"TXD", "RTS", "DTR", "DCD"}
EVEN_PIN_NETS = {"RXD", "CTS", "DSR", "RI"}

_CACHE: list = []


def _compile():
    if not _CACHE:
        circuit = CircuitSpec.load(CIRCUIT)
        presentation = PresentationSpec.load(PRESENTATION)
        library = drawapply.load_library(LIBRARY)
        budget = pc.PageCompileBudget(page_box=PAGE_BOX)
        result = pc.compile_page(circuit, presentation, library, budget)
        assert result.ok, result.render_failures()
        _CACHE.append((circuit, library, result))
    return _CACHE[0]


def _parts(plan) -> dict[str, object]:
    return {part.part_id: part for part in plan.parts}


def _box_gap(one, other) -> float:
    dx = max(one[0] - other[2], other[0] - one[2], 0.0)
    dy = max(one[1] - other[3], other[1] - one[3], 0.0)
    return (dx * dx + dy * dy) ** 0.5


class _Union:
    def __init__(self):
        self.parent = {}

    def find(self, item):
        self.parent.setdefault(item, item)
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def join(self, one, other):
        root_one, root_other = self.find(one), self.find(other)
        if root_one != root_other:
            self.parent[root_other] = root_one


def _on_segment(point, start, stop, tol=1e-6) -> bool:
    (px, py), (ax, ay), (bx, by) = point, start, stop
    if abs((bx - ax) * (py - ay) - (by - ay) * (px - ax)) > 1e-6:
        return False
    return (
        min(ax, bx) - tol <= px <= max(ax, bx) + tol
        and min(ay, by) - tol <= py <= max(ay, by) + tol
    )


def _landing(plan, circuit, library) -> dict:
    """617C's per-pin re-check (landing + connectivity), re-implemented here."""
    tips: dict[str, tuple[float, float]] = {}
    for part in plan.parts:
        pose = dc.SymbolPose(part.rotation, part.mirror)
        for pin in library[part.symbol_ref].pins:
            dx, dy = dc._posed_tip(pin, pose)
            tips[f"{part.part_id}.{pin.number}"] = (
                round(part.x + dx, 6), round(part.y + dy, 6))
    segments_by_net: dict[str, list] = {}
    for segment in plan.segments:
        points = [(round(x, 6), round(y, 6)) for x, y in segment.points]
        for start, stop in zip(points, points[1:]):
            segments_by_net.setdefault(segment.net, []).append((start, stop))
    flag_nets = {symbol.net for symbol in plan.power_symbols}
    label_nets = {label.net for label in plan.labels}
    nc_pins = {item.pin for item in circuit.nc}
    unlanded, classes = [], {}
    for key, point in tips.items():
        if key in nc_pins:
            classes["nc"] = classes.get("nc", 0) + 1
            continue
        net_ids = [net.id for net in circuit.nets if key in net.members]
        own = segments_by_net.get(net_ids[0], []) if net_ids else []
        if any(abs(point[0] - a[0]) <= 1e-6 and abs(point[1] - a[1]) <= 1e-6
               for seg in own for a in seg):
            kind = "wire-end"
        elif any(_on_segment(point, *seg) for seg in own):
            kind = "wire"
        elif any(other != key
                 and abs(point[0] - q[0]) <= 1e-6
                 and abs(point[1] - q[1]) <= 1e-6
                 for other, q in tips.items()):
            kind = "abut"
        elif net_ids and (net_ids[0] in flag_nets or net_ids[0] in label_nets):
            kind = "named"
        else:
            kind = "UNLANDED"
            unlanded.append(key)
        classes[kind] = classes.get(kind, 0) + 1
    broken = []
    for net in circuit.nets:
        members = [name for name in tips if name in net.members and name not in nc_pins]
        if len(members) < 2:
            continue
        union = _Union()
        for member in members:
            union.find(tips[member])
        for start, stop in segments_by_net.get(net.id, []):
            union.join(start, stop)
        for member in members:
            for start, stop in segments_by_net.get(net.id, []):
                if _on_segment(tips[member], start, stop):
                    union.join(tips[member], start)
        if len({union.find(tips[member]) for member in members}) > 1 \
                and net.id not in flag_nets and net.id not in label_nets:
            broken.append(net.id)
    return {
        "parts": len(plan.parts), "pins": len(tips), "nets": len(circuit.nets),
        "unlanded": unlanded, "broken": broken, "classes": classes,
    }


def _rxd(plan) -> dict:
    label = next(item for item in plan.labels
                 if item.net == "RXD" and item.part_id == "U1")
    box = tuple(float(value) for value in label.bbox)
    anchor = (float(label.x), float(label.y))
    centre = ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)
    c3 = next(item for item in plan.texts if item.text == "C3")
    return {
        "box": box, "anchor": anchor,
        "stub": abs(centre[0] - anchor[0]) + abs(centre[1] - anchor[1]),
        "c3_gap": _box_gap(box, tuple(float(v) for v in c3.bbox)),
    }


def test_input_is_agent_adjusted_by_one_field():
    before = ORIGINAL.read_text(encoding="utf-8").splitlines(keepends=True)
    after = PRESENTATION.read_text(encoding="utf-8").splitlines(keepends=True)
    changed = [line for line in difflib.unified_diff(before, after, n=0)
               if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))]
    assert changed == ['-  "moduleColumns": 2,\n', '+  "moduleColumns": 3,\n'], changed
    old = json.loads(ORIGINAL.read_text(encoding="utf-8"))
    new = json.loads(PRESENTATION.read_text(encoding="utf-8"))
    assert old.pop("moduleColumns") == 2
    assert new.pop("moduleColumns") == 3
    assert old == new


def test_every_candidate_reads_forward():
    _, _, result = _compile()
    assert len(result.ranked) == 4, [c.metrics for c in result.ranked]
    for index, candidate in enumerate(result.ranked):
        assert candidate.metrics["page_backflow_length"] == 0, (
            f"candidate {index} runs {candidate.metrics['page_backflow_length']} "
            f"units against the reading direction")


def test_main_chain_is_one_left_to_right_row():
    _, _, result = _compile()
    for index, candidate in enumerate(result.ranked):
        parts = _parts(candidate.page.plan)
        usb, bridge, header, led = (parts[name] for name in ("USB1", "U1", "H1", "D1"))
        assert usb.x < bridge.x < header.x, (
            f"candidate {index}: main-chain origins "
            f"{usb.x:g} / {bridge.x:g} / {header.x:g} do not run left to right")
        assert abs(bridge.y - usb.y) <= 60 and abs(header.y - bridge.y) <= 60, (
            f"candidate {index}: the chain is not one row "
            f"(y {usb.y:g} / {bridge.y:g} / {header.y:g})")
        assert led.y < min(usb.y, bridge.y, header.y) - 200, (
            f"candidate {index}: indicator y {led.y:g} is not on a second row")


def test_header_turns_its_pin_one_column_towards_the_bridge():
    _, _, result = _compile()
    header = _parts(result.ranked[0].page.plan)["H1"]
    assert header.rotation == 0 and not header.mirror, (
        f"H1 pose {(header.rotation, header.mirror)} is not the unmirrored pin-1 pose")
    facing = {
        label.net: (float(label.x), float(label.y))
        for label in result.ranked[0].page.plan.labels
        if label.part_id == "H1" and float(label.x) < header.x
    }
    away = {
        label.net for label in result.ranked[0].page.plan.labels
        if label.part_id == "H1" and float(label.x) > header.x
    }
    assert set(facing) == ODD_PIN_NETS, (
        f"H1's column towards CH343 is {sorted(facing)}, not the pin-1 column")
    assert away == EVEN_PIN_NETS, f"H1's far column is {sorted(away)}"
    bridge = _parts(result.ranked[0].page.plan)["U1"]
    for net, (x, _y) in facing.items():
        assert bridge.x < x < header.x, (
            f"{net} at x={x:g} does not stand between CH343 ({bridge.x:g}) "
            f"and H1 ({header.x:g})")


def test_rxd_keeps_617d_stub_and_c3_clearance():
    _, _, result = _compile()
    for index, candidate in enumerate(result.ranked):
        rxd = _rxd(candidate.page.plan)
        assert rxd["stub"] < PRE_FIX_STUB, (
            f"candidate {index}: RXD sits {rxd['stub']:g} units from its pin")
        assert rxd["stub"] <= 20.0, (
            f"candidate {index}: RXD stub {rxd['stub']:g} is past 617D's 20")
        assert rxd["box"][2] <= rxd["anchor"][0], (
            f"candidate {index}: RXD box {rxd['box']} stands past its pin")
        assert rxd["c3_gap"] >= TEXT_FLOOR, (
            f"candidate {index}: RXD is {rxd['c3_gap']:g} from C3's reference")


def test_pins_nets_and_landing_are_the_617c_reading():
    circuit, library, result = _compile()
    for index, candidate in enumerate(result.ranked):
        report = _landing(candidate.page.plan, circuit, library)
        assert report["parts"] == 11 and report["pins"] == 58, report
        assert report["nets"] == 17, report
        assert report["unlanded"] == [], report
        assert report["broken"] == [], report
        assert report["classes"] == CLASSES, report
