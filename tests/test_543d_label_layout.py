"""543D: the paired signals and the label columns, as declarations.

The batch starts from the 543C page (agent islands, no locks, `pinGap: 30`) and
adds three *declarative* statements, none of them a coordinate:

* `textPlacement: native-attr` — the host prints a net's name as an attribute
  row, so one name per module view is enough and no second row is ink;
* `labelPolicy.stub: straight` — the name stub is a straight run;
* each module's own `presentation.sidePreferences` — the USB receptacle reads
  its `load` net to the **right** and the CH343 core to the **left**, so the
  `D+`/`D-` pair faces across the empty space between the two islands.

Those declarations alone make the page legal, the UART column horizontal and
non-overlapping, and one visible name per net per module. One narrow engine
choice is still needed: 053V's "keep the name farthest from its pin" kept the
USB pair's **long carrier** — the side pointing away from the CH343 — printed,
while the name the page states at its port was hidden. `drawcompiler`'s
visibility pass now reads the module's stated side, but only when the document
states `serviceLayout` (the 543B/C opt-in), so a page that only states
`textPlacement` keeps 053V's answer exactly.

The tests pin the page, the final ChangePlan (`drawapply.module_plan`) and the
negative controls, because a compile-time SVG is not the thing that lands.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.geometry import transform_point
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawapply
from boardwise.engines import drawcompiler as dc
from boardwise.engines import grammar
from boardwise.engines import pagecompiler as pc
from boardwise.engines import readability

ROOT = Path(__file__).resolve().parents[1]
CIRCUIT_PATH = ROOT / "blocklib" / "specs" / "ch343_uart_534a.circuit.json"
LIBRARY_PATH = ROOT / "blocklib" / "specs" / "ch343_uart_v4.library.json"
PAGE_BOX = (0.0, 0.0, 1170.0, 825.0)
UART = {"TXD", "RXD", "RTS", "CTS", "DTR", "DSR", "DCD", "RI"}

MODULES = [
    {"id": "usb_c", "parts": ["USB1", "C1", "C2"],
     "role": "USB receptacle + +5V decoupling", "grammarRef": "ic-periphery",
     "core": "USB1",
     "presentation": {"sidePreferences": {"load": "right"}}},
    {"id": "ch343", "parts": ["U1", "C3", "C4"], "role": "CH343 core",
     "grammarRef": "ic-periphery", "core": "U1",
     "presentation": {"sidePreferences": {"load": "left"}}},
    # 543D-2: the CC pull-downs are their own island (agent partition), so a
    # flipped receptacle pose no longer drags the CC branches with it.
    {"id": "cc", "parts": ["R1", "R2"], "role": "CC pull-downs",
     "grammarRef": "ic-periphery"},
    {"id": "hdr", "parts": ["H1"], "role": "header", "grammarRef": "ic-periphery",
     "core": "H1"},
    {"id": "led", "parts": ["D1", "R3"], "role": "indicator",
     "grammarRef": "voltage-divider"},
]
PORT_ROLES = {
    "D+": "load", "D-": "load", "VCC": "input", "TXD": "output", "RXD": "input",
    "RTS": "output", "CTS": "input", "DTR": "output", "DSR": "input",
    "DCD": "input", "RI": "input",
}
PAYLOAD = {
    "grammarRef": "ic-periphery",
    "textPlacement": "native-attr",
    "sidePreferences": {
        "input": "left", "output": "right", "load": "left", "source": "left",
        "power": "top", "gnd": "bottom",
    },
    "portRoles": PORT_ROLES,
    "flow": [["usb_c", "ch343"], ["ch343", "hdr"]],
    "modules": MODULES,
    "labelPolicy": {
        "local": "wire", "crossModule": "label", "highFanout": "label",
        "stub": "straight", "stubMin": 40, "rowModel": "centered",
    },
    "directWiringObligations": [
        {"nets": ["LED_A"], "note": "the lamp and R3 are one conductor inside usb_c"}
    ],
    "localLabelObligations": [
        {"nets": ["D+", "D-"],
         "note": "the Type-C mirrored data pins are named on each pin instead of "
                 "being joined by a U-line"}
    ],
    "moduleOrder": ["usb_c", "ch343", "cc", "hdr", "led"],
    "moduleColumns": 2,
    "flagLeadLimit": 120,
    "partTexts": {
        "USB1": "left", "H1": "above", "U1": "above", "C3": "right",
        "C4": "right",
    },
    "gndClustering": {"radius": 100},
    "serviceLayout": {"pinGap": 30},
}


def _book() -> dict[str, SymbolProfile]:
    data = json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))
    return {item["symbolRef"]: SymbolProfile.from_dict(item) for item in data["profiles"]}


BOOK = _book()
CIRCUIT = CircuitSpec.load(CIRCUIT_PATH)


def _presentation(
    *, native: bool = True, sides: bool = True, service: bool = True,
) -> PresentationSpec:
    payload = copy.deepcopy(PAYLOAD)
    if not native:
        payload.pop("textPlacement", None)
    if not service:
        payload.pop("serviceLayout", None)
    if not sides:
        for module in payload["modules"]:
            module.pop("presentation", None)
    return PresentationSpec.from_dict(payload)


def _compile(**flags):
    return pc.compile_page(
        CIRCUIT, _presentation(**flags), BOOK,
        pc.PageCompileBudget(page_box=PAGE_BOX),
    )


_PLAN_CACHE: dict[str, object] = {}


def _plan_for(page):
    key = page.page_geometry_sha256()
    if key not in _PLAN_CACHE:
        _PLAN_CACHE[key] = drawapply.module_plan(
            page.plan,
            CIRCUIT,
            _presentation(),
            BOOK,
            candidate_index=1,
            keep_names=True,
            label_stubs=True,
        )
    return _PLAN_CACHE[key]


def _page():
    result = _compile()
    assert result.ok, result.render_failures()
    assert result.pages
    # The page compiler may rank a candidate whose H1 rows leave no free name
    # stub; the batch selects the first candidate that also builds the landing
    # plan (the same "at least one" rule the compile gate states).
    for page in result.pages:
        try:
            _plan_for(page)
        except drawapply.DrawPlanError:
            continue
        return page
    raise AssertionError("no page candidate builds a ChangePlan")


def _pin(plan, member: str) -> tuple[float, float]:
    part_id, _, token = member.partition(".")
    part = next(item for item in plan.parts if item.part_id == part_id)
    profile = BOOK[part.symbol_ref]
    pin = next(item for item in profile.pins if str(item.number) == token)
    return transform_point(
        pin.tip[0], pin.tip[1], rotation=part.rotation, mirror=part.mirror,
        ox=part.x, oy=part.y,
    )


def _module_of(page, part_id: str) -> str:
    for module in page.modules:
        if part_id in module.parts:
            return module.id
    return ""


def _visible(label) -> bool:
    return getattr(label, "text_mode", "") != "native-hidden"


def _labels(page, net: str, module: str) -> list:
    return [
        label for label in page.plan.labels
        if label.net == net and _module_of(page, label.part_id) == module
    ]


def _overlap(a, b) -> bool:
    return (
        min(a[2], b[2]) - max(a[0], b[0]) > 1e-6
        and min(a[3], b[3]) - max(a[1], b[1]) > 1e-6
    )


def _segment_between(plan, net: str, start, end):
    wanted = {tuple(start), tuple(end)}
    for segment in plan.segments:
        if segment.net != net:
            continue
        if len(segment.points) == 2 and {tuple(segment.points[0]),
                                         tuple(segment.points[1])} == wanted:
            return segment
    return None


def _run_crosses_x(points, low: float, high: float) -> bool:
    for start, stop in zip(points, points[1:]):
        left, right = sorted((start[0], stop[0]))
        if right > low and left < high:
            return True
    return False


# --------------------------------------------------------------- the page


def test_the_declared_page_is_legal_with_zero_hard_violations():
    result = _compile()
    assert result.ok, result.render_failures()
    assert len(result.pages) >= 1
    for page in result.pages:
        assert page.verdict == "pass", page.plan.evidence.hard_violations
        assert page.plan.evidence.hard_violations == []
        assert page.page_evidence.hard_violations == []


def test_both_service_connections_stay_at_thirty():
    page = _page()
    for cap, host_pin, net in (("C3", "4", "V3"), ("C4", "15", "VCC")):
        cap_point = _pin(page.plan, f"{cap}.1")
        host_point = _pin(page.plan, f"U1.{host_pin}")
        assert cap_point[1] == host_point[1], (
            f"{cap} and U1.{host_pin} are not on one row: {cap_point} / {host_point}"
        )
        assert abs(cap_point[0] - host_point[0]) == 30.0
        assert _segment_between(page.plan, net, cap_point, host_point) is not None


def test_uart_names_are_horizontal_and_do_not_overlap():
    page = _page()
    uart = [label for label in page.plan.labels if label.net in UART]
    assert {label.net for label in uart} == UART
    for label in uart:
        assert label.rotation == 0.0, f"{label.net} is rotated"
        assert (label.bbox[2] - label.bbox[0]) >= (label.bbox[3] - label.bbox[1]), (
            f"{label.net} is not a horizontal row: {label.bbox}"
        )
    for index, left in enumerate(uart):
        for right in uart[index + 1:]:
            assert not _overlap(left.bbox, right.bbox), (
                f"{left.net} and {right.net} overlap: {left.bbox} / {right.bbox}"
            )


def test_every_net_prints_once_per_module_view():
    page = _page()
    groups: dict[tuple[str, str], list] = {}
    for label in page.plan.labels:
        groups.setdefault((_module_of(page, label.part_id), label.net), []).append(
            label
        )
    for (module, net), group in groups.items():
        printed = [label for label in group if _visible(label)]
        assert len(printed) == 1, (
            f"{module}/{net} prints {len(printed)} names, expected one: "
            f"{[label.bbox for label in group]}"
        )
        assert len(group) - len(printed) == sum(
            1 for label in group if not _visible(label)
        )
    # The four reversible Type-C pins keep their own carrier wires: one visible
    # name per net per module does not delete the runs that carry the net.
    for net in ("D+", "D-"):
        usb = _labels(page, net, "usb_c")
        assert len(usb) == 2
        assert sum(1 for label in usb if _visible(label)) == 1
        assert sum(1 for label in usb if not _visible(label)) == 1


def test_d_pair_faces_across_the_module_gap():
    page = _page()
    usb = next(module for module in page.modules if module.id == "usb_c")
    ch343 = next(module for module in page.modules if module.id == "ch343")
    assert usb.frame[2] < ch343.frame[0], "the islands are not left-to-right"

    visible: dict[tuple[str, str], object] = {}
    ports: dict[tuple[str, str], object] = {}
    for module in (usb, ch343):
        for net in ("D+", "D-"):
            printed = [
                label for label in _labels(page, net, module.id) if _visible(label)
            ]
            assert len(printed) == 1, (
                f"{module.id}/{net} prints {len(printed)} names, expected one"
            )
            visible[(module.id, net)] = printed[0]
            port = next(
                item for item in module.ports if item.net == net
            )
            ports[(module.id, net)] = port
            # The name the reader sees at the boundary is the name the page
            # states at its port — not a hidden duplicate elsewhere.
            assert (printed[0].x, printed[0].y) == (port.x, port.y), (
                f"{module.id}/{net}: printed at {printed[0].x},{printed[0].y}, "
                f"the page states the port at {port.x},{port.y}"
            )

    for net in ("D+", "D-"):
        usb_box = visible[("usb_c", net)].bbox
        ch_box = visible[("ch343", net)].bbox
        assert usb.frame[0] <= usb_box[0] and usb_box[2] <= usb.frame[2]
        assert ch343.frame[0] <= ch_box[0] and ch_box[2] <= ch343.frame[2]
        # Facing across the empty space: the USB name is on the right island's
        # near side, the CH343 name on the left, and nothing of the pair's
        # conductor runs through the gap between the frames.
        assert usb_box[2] < ch_box[0], (
            f"{net} names are not ordered across the gap: {usb_box} / {ch_box}"
        )
        for segment in page.plan.segments:
            if segment.net == net:
                assert not _run_crosses_x(
                    segment.points, usb.frame[2], ch343.frame[0],
                ), f"{net} has a conductor across the island gap"

    # The pair reads in the same vertical order at both ends: D+ above D-.
    for module in (usb, ch343):
        assert (
            visible[(module.id, "D+")].y - visible[(module.id, "D-")].y
        ) > 0, f"{module.id}: D+ is not above D-"

    # 543D hard direction: the printed box must lie **beyond its own service
    # pin**, not merely somewhere inside its island. The USB name is right of
    # A6/A7, the CH343 name left of U1.5/U1.6 — the two ends point at each
    # other across the gap. (The client rejected the first submission precisely
    # because this was not asserted: both names sat left of their own pin.)
    service_pin = {
        ("usb_c", "D+"): _pin(page.plan, "USB1.A6"),
        ("usb_c", "D-"): _pin(page.plan, "USB1.A7"),
        ("ch343", "D+"): _pin(page.plan, "U1.5"),
        ("ch343", "D-"): _pin(page.plan, "U1.6"),
    }
    for key, point in service_pin.items():
        box = visible[key].bbox
        centre_x = (box[0] + box[2]) / 2.0
        if key[0] == "usb_c":
            assert centre_x > point[0], (
                f"{key[0]}/{key[1]}: box centre x={centre_x:g} is not right of "
                f"service pin x={point[0]:g} ({box})"
            )
        else:
            assert centre_x < point[0], (
                f"{key[0]}/{key[1]}: box centre x={centre_x:g} is not left of "
                f"service pin x={point[0]:g} ({box})"
            )


# ---------------------------------------------------------- the ChangePlan


def _change_plan(page):
    return _plan_for(page).to_jsonable()["change"]


def test_the_change_plan_carries_straight_stubs_and_attr_targets():
    page = _page()
    change = _change_plan(page)
    wires = change["wires"]
    moves = [
        move for move in change["attributeMoves"]
        if move["owner"]["kind"] == "wire"
    ]
    by_wire = {move["owner"]["index"]: move for move in moves}
    assert len(by_wire) == len(moves), "two attribute moves claim one wire"

    watched = {"D+", "D-", *UART}
    labelled = [
        label for label in page.plan.labels
        if label.net in watched and _visible(label)
    ]
    assert labelled

    for label in labelled:
        carrying = [
            index for index, wire in enumerate(wires)
            if wire.get("net") == label.net
            and any(
                abs(point[0] - label.x) < 1e-6 and abs(point[1] - label.y) < 1e-6
                for point in wire["points"]
            )
        ]
        assert len(carrying) == 1, (
            f"{label.net} at ({label.x:g}, {label.y:g}) is on {len(carrying)} wires"
        )
        index = carrying[0]
        wire = wires[index]
        # 543D's stub is straight: one orthogonal run.
        assert len(wire["points"]) == 2, wire
        (x1, y1), (x2, y2) = wire["points"]
        assert (x1 == x2) != (y1 == y2), f"{label.net} stub is not orthogonal: {wire}"
        assert move_wire_target(by_wire, index) == (
            round((label.bbox[0] + label.bbox[2]) / 2.0, 6),
            round((label.bbox[1] + label.bbox[3]) / 2.0, 6),
        ), f"{label.net}'s attribute row does not land on its reserved box"

    # 543D hard direction in the landing plan too: the stub runs away from the
    # service pin toward the module's stated side, and the ATTR target lies on
    # that side of the pin — not just inside the island.
    service_pin = {
        ("usb_c", "D+"): _pin(page.plan, "USB1.A6"),
        ("usb_c", "D-"): _pin(page.plan, "USB1.A7"),
        ("ch343", "D+"): _pin(page.plan, "U1.5"),
        ("ch343", "D-"): _pin(page.plan, "U1.6"),
    }
    for label in labelled:
        if label.net not in ("D+", "D-"):
            continue
        key = (_module_of(page, label.part_id), label.net)
        point = service_pin[key]
        index = next(
            index for index, wire in enumerate(wires)
            if wire.get("net") == label.net
            and any(
                abs(p[0] - label.x) < 1e-6 and abs(p[1] - label.y) < 1e-6
                for p in wire["points"]
            )
        )
        (x1, _y1), (x2, _y2) = wires[index]["points"]
        target_x = by_wire[index]["to"]["x"]
        if key[0] == "usb_c":
            assert max(x1, x2) > point[0], (
                f"{key}: stub {wires[index]['points']} does not run right of "
                f"pin x={point[0]:g}"
            )
            assert target_x > point[0], (
                f"{key}: ATTR x={target_x:g} is not right of pin x={point[0]:g}"
            )
        else:
            assert min(x1, x2) < point[0], (
                f"{key}: stub {wires[index]['points']} does not run left of "
                f"pin x={point[0]:g}"
            )
            assert target_x < point[0], (
                f"{key}: ATTR x={target_x:g} is not left of pin x={point[0]:g}"
            )

    # The hidden duplicates keep their conductors and hide only their own text.
    for module in ("usb_c",):
        for net in ("D+", "D-"):
            hidden = [
                label for label in _labels(page, net, module) if not _visible(label)
            ]
            assert len(hidden) == 1
            index = next(
                index for index, wire in enumerate(wires)
                if wire.get("net") == net
                and any(
                    abs(point[0] - hidden[0].x) < 1e-6
                    and abs(point[1] - hidden[0].y) < 1e-6
                    for point in wire["points"]
                )
            )
            move = by_wire[index]
            assert move["to"] == {"valueVisible": False}, move


def move_wire_target(by_wire, index):
    move = by_wire[index]
    target = move["to"]
    return (round(target["x"], 6), round(target["y"], 6))


# -------------------------------------------------- the opt-in and its off


def test_the_side_reading_needs_the_service_key():
    presentation = _presentation()
    usb_ctx = _context(CIRCUIT, presentation, presentation.module("usb_c"))
    ch_ctx = _context(CIRCUIT, presentation, presentation.module("ch343"))
    assert dc._native_label_sides(usb_ctx)["D+"] == (1.0, 0.0)
    assert dc._native_label_sides(ch_ctx)["D-"] == (-1.0, 0.0)

    without = _presentation(service=False)
    off_ctx = _context(CIRCUIT, without, without.module("usb_c"))
    assert dc._native_label_sides(off_ctx) == {}


def test_without_native_both_usb_pairs_print_twice():
    result = _compile(native=False)
    assert result.ok, result.render_failures()
    page = result.pages[0]
    for net in ("D+", "D-"):
        usb = _labels(page, net, "usb_c")
        assert len(usb) == 2
        assert sum(1 for label in usb if _visible(label)) == 2, (
            "without native-attr the duplicate names print, which 543D forbids"
        )


def test_without_the_cc_island_the_usb_pair_stays_left_of_its_pins():
    """The unsplit island with the same declarations, minus the module sides.

    This is the pre-543D-2 shape: R1/R2 live in `usb_c`, so the receptacle has
    no legal right-pointing pose (the CC branches and R1's GND flag block it).
    The document keeps `native-attr` + `serviceLayout` but drops the module
    sidePreferences, so the pose filter stays on the left pose and the page
    compiles — and the printed D+ box is left of A6, i.e. the hard direction
    assertion fails. That is what makes the split island load-bearing.
    """
    payload = copy.deepcopy(PAYLOAD)
    usb = next(module for module in payload["modules"] if module["id"] == "usb_c")
    usb["parts"] = ["USB1", "C1", "C2", "R1", "R2"]
    payload["modules"] = [
        module for module in payload["modules"] if module["id"] != "cc"
    ]
    for module in payload["modules"]:
        module.pop("presentation", None)
    payload["moduleOrder"] = ["usb_c", "ch343", "hdr", "led"]
    payload["partTexts"].pop("USB1", None)

    result = pc.compile_page(
        CIRCUIT, PresentationSpec.from_dict(payload), BOOK,
        pc.PageCompileBudget(page_box=PAGE_BOX),
    )
    assert result.ok, result.render_failures()
    page = result.pages[0]
    printed = [
        label for label in _labels(page, "D+", "usb_c") if _visible(label)
    ][0]
    centre_x = (printed.bbox[0] + printed.bbox[2]) / 2.0
    pin_x = _pin(page.plan, "USB1.A6")[0]
    assert centre_x < pin_x, (
        "without the CC island the name cannot be right of its pin: "
        f"box centre {centre_x:g}, pin {pin_x:g}"
    )


# ------------------------------------------------------------ connectivity


def test_every_pin_stays_on_its_net_node():
    page = _page()
    derived = readability.derive_netlist(page.plan, BOOK)
    pin_net = {member: net.id for net in CIRCUIT.nets for member in net.members}
    for net in CIRCUIT.nets:
        group = set(derived.group_of(net.members[0]))
        assert group == set(net.members), (
            f"net {net.id!r} draws {sorted(group)}, spec says {sorted(net.members)}"
        )
    for group in derived.groups:
        nets = {pin_net[pin] for pin in group if pin in pin_net}
        assert len(nets) <= 1, f"one node mixes spec nets {sorted(nets)}: {group}"


def _context(circuit_spec, presentation_spec, module):
    local_circuit, local_presentation = pc._module_view(
        circuit_spec, presentation_spec, module
    )
    binding = grammar.bind(
        local_circuit, local_presentation, BOOK, grammar_name="ic-periphery"
    )
    prepared = dc._prepare(
        local_circuit, local_presentation, binding, BOOK, dc.CompileBudget()
    )
    assert prepared.context is not None
    return prepared.context
