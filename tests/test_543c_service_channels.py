"""543C: the label/flag/GND channels of a served shunt's island.

The batch's subject is the CH343 page with `serviceLayout.pinGap = 30` and no
user locks. Before this batch the page was refused: the shorter shunt moved
C3's GND return into the column occupied by the `D+` label's name box, and with
the label box made a wall the return then crossed C3's own return pad and shorted
to +5V.

These tests pin what the drawing now has to show:

* at least one `ok=True` page, every page with zero hard violations;
* C3.1 → U1.4 on V3 and C4.1 → U1.15 on VCC, each one straight horizontal run of
  30 units (the stated interval);
* no GND conductor inside any label's name box (D+/D- and every other label);
* the same page without `serviceLayout` keeps the old 60-unit branch, and the
  USB module's own drawing is byte-identical with and without the key — the
  channel work is scoped to the island that has a uniquely served shunt;
* every spec pin is on the drawing's node for its net, and no derived node mixes
  two spec nets (the per-pin connectivity evidence).

The real `.tmp_543b/gap30.presentation.json` is an ignored work artifact; its
module structure is embedded here so the test does not depend on it.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.geometry import transform_point
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawcompiler as dc
from boardwise.engines import grammar
from boardwise.engines import pagecompiler as pc
from boardwise.engines import readability

ROOT = Path(__file__).resolve().parents[1]
CIRCUIT_PATH = ROOT / "blocklib" / "specs" / "ch343_uart_534a.circuit.json"
LIBRARY_PATH = ROOT / "blocklib" / "specs" / "ch343_uart_v4.library.json"
PAGE_BOX = (0.0, 0.0, 1170.0, 825.0)

#: The module structure of the lock-free merged CH343 page (`serviceLayout`
#: added by `_presentation`). Everything else is the document the batch runs.
MODULES = [
    {"id": "usb_c", "parts": ["USB1", "C1", "C2", "R1", "R2"],
     "role": "USB + +5V decoupling + CC", "grammarRef": "ic-periphery",
     "core": "USB1"},
    {"id": "ch343", "parts": ["U1", "C3", "C4"], "role": "CH343 core",
     "grammarRef": "ic-periphery", "core": "U1"},
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
    "sidePreferences": {
        "input": "left", "output": "right", "load": "left", "source": "left",
        "power": "top", "gnd": "bottom",
    },
    "portRoles": PORT_ROLES,
    "flow": [["usb_c", "ch343"], ["ch343", "hdr"]],
    "modules": MODULES,
    "labelPolicy": {
        "local": "wire", "crossModule": "label", "highFanout": "label",
        "stubMin": 40, "rowModel": "centered",
    },
    "directWiringObligations": [
        {"nets": ["LED_A"], "note": "the lamp and R3 are one conductor inside usb_c"}
    ],
    "localLabelObligations": [
        {"nets": ["D+", "D-"],
         "note": "the Type-C mirrored data pins are named on each pin instead of "
                 "being joined by a U-line"}
    ],
    "moduleOrder": ["usb_c", "ch343", "hdr", "led"],
    "moduleColumns": 2,
    "flagLeadLimit": 120,
    "partTexts": {"U1": "above", "C3": "right", "C4": "right"},
    "gndClustering": {"radius": 100},
}


def _book() -> dict[str, SymbolProfile]:
    data = json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))
    return {item["symbolRef"]: SymbolProfile.from_dict(item) for item in data["profiles"]}


BOOK = _book()
CIRCUIT = CircuitSpec.load(CIRCUIT_PATH)


def _presentation(with_key: bool) -> PresentationSpec:
    payload = copy.deepcopy(PAYLOAD)
    if with_key:
        payload["serviceLayout"] = {"pinGap": 30}
    return PresentationSpec.from_dict(payload)


def _compile(with_key: bool = True):
    return pc.compile_page(
        CIRCUIT, _presentation(with_key), BOOK,
        pc.PageCompileBudget(page_box=PAGE_BOX),
    )


def _pin(plan, member: str) -> tuple[float, float]:
    part_id, _, token = member.partition(".")
    part = next(item for item in plan.parts if item.part_id == part_id)
    profile = BOOK[part.symbol_ref]
    pin = next(item for item in profile.pins if str(item.number) == token)
    return transform_point(
        pin.tip[0], pin.tip[1], rotation=part.rotation, mirror=part.mirror,
        ox=part.x, oy=part.y,
    )


def _picture(plan) -> dict:
    """The drawn picture without the input digests `geometry_json` also carries."""
    doc = plan.to_jsonable()
    for key in ("source", "target", "evidence", "verdict", "notes", "kind",
                "planVersion", "geometrySha256"):
        doc.pop(key, None)
    return doc


def _segment_between(plan, net: str, start, end):
    wanted = {tuple(start), tuple(end)}
    for segment in plan.segments:
        if segment.net != net:
            continue
        if len(segment.points) == 2 and {tuple(segment.points[0]),
                                         tuple(segment.points[1])} == wanted:
            return segment
    return None


def _segment_hits_box(points, box) -> bool:
    """Does an axis-aligned run pass through the interior of ``box``?"""
    (x1, y1), (x2, y2) = points[0], points[-1]
    if x1 == x2:
        if not (box[0] < x1 < box[2]):
            return False
        low, high = sorted((y1, y2))
        return min(high, box[3]) - max(low, box[1]) > 1e-6
    if y1 == y2:
        if not (box[1] < y1 < box[3]):
            return False
        low, high = sorted((x1, x2))
        return min(high, box[2]) - max(low, box[0]) > 1e-6
    return False


def _pages(result):
    assert result.ok, result.render_failures()
    assert result.pages
    return result.pages


# ------------------------------------------------------------------ geometry


def test_the_gap30_page_is_legal_and_serves_each_shunt_at_thirty():
    result = _compile(True)
    pages = _pages(result)

    for page in pages:
        assert page.verdict == "pass", page.plan.evidence.hard_violations
        assert page.plan.evidence.hard_violations == []
        assert page.page_evidence.hard_violations == []
        for cap, host_pin, net in (("C3", "4", "V3"), ("C4", "15", "VCC")):
            cap_point = _pin(page.plan, f"{cap}.1")
            host_point = _pin(page.plan, f"U1.{host_pin}")
            assert cap_point[1] == host_point[1], (
                f"{cap} and U1.{host_pin} are not on one row: {cap_point} / {host_point}"
            )
            assert abs(cap_point[0] - host_point[0]) == 30.0
            run = _segment_between(page.plan, net, cap_point, host_point)
            assert run is not None, (
                f"{cap}.1 -> U1.{host_pin} is not one straight {net} run"
            )


def test_no_gnd_conductor_runs_through_a_label_name_box():
    page = _pages(_compile(True))[0]
    gnd_runs = [
        segment.points for segment in page.plan.segments if segment.net == "GND"
    ]
    assert gnd_runs
    crossed = [
        (label.net, label.bbox, points)
        for label in page.plan.labels
        for points in gnd_runs
        if _segment_hits_box(points, label.bbox)
    ]
    assert crossed == []
    named = {label.net for label in page.plan.labels}
    assert {"D+", "D-"} <= named


def test_without_the_key_the_branch_keeps_its_old_sixty_units():
    page = _pages(_compile(False))[0]
    assert page.verdict == "pass"
    for cap, host_pin in (("C3", "4"), ("C4", "15")):
        cap_point = _pin(page.plan, f"{cap}.1")
        host_point = _pin(page.plan, f"U1.{host_pin}")
        assert cap_point[1] == host_point[1]
        assert abs(cap_point[0] - host_point[0]) == 60.0


# -------------------------------------------------------------------- scope


def test_the_usb_module_draws_the_same_with_and_without_the_key():
    presentation = _presentation(True)
    without = _presentation(False)

    with_module = presentation.module("usb_c")
    without_module = without.module("usb_c")
    with_circuit, with_spec = pc._module_view(CIRCUIT, presentation, with_module)
    without_circuit, without_spec = pc._module_view(CIRCUIT, without, without_module)

    with_result = dc.compile(with_circuit, with_spec, BOOK, dc.CompileBudget())
    without_result = dc.compile(without_circuit, without_spec, BOOK, dc.CompileBudget())
    assert with_result.ok, with_result.render_failures()
    assert without_result.ok, without_result.render_failures()
    assert _picture(with_result.candidates[0]) == _picture(without_result.candidates[0]), (
        "the USB island moved when the CH343 service key was stated"
    )

    with_ctx = _context(CIRCUIT, presentation, with_module)
    without_ctx = _context(CIRCUIT, without, without_module)
    assert dc._service_channels(with_ctx) is False
    assert dc._service_channels(without_ctx) is False


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


def test_the_ch343_slice_is_the_one_that_gets_channels():
    presentation = _presentation(True)
    ch343 = _context(CIRCUIT, presentation, presentation.module("ch343"))
    usb = _context(CIRCUIT, presentation, presentation.module("usb_c"))
    without = _context(CIRCUIT, _presentation(False),
                       _presentation(False).module("ch343"))

    assert dc._service_channels(ch343) is True
    assert dc._service_channels(usb) is False
    assert dc._service_channels(without) is False


def test_a_label_box_is_a_router_wall_only_on_the_service_island():
    presentation = _presentation(True)
    ctx = _context(CIRCUIT, presentation, presentation.module("ch343"))
    usb = _context(CIRCUIT, presentation, presentation.module("usb_c"))
    box = (0.0, 0.0, 10.0, 10.0)

    class _Router:
        def __init__(self):
            self.boxes = []

    router, walls = _Router(), []
    dc._reserve_service_label_box(ctx, router, box, walls)
    assert router.boxes == [box]
    assert walls == [box]

    router, walls = _Router(), []
    dc._reserve_service_label_box(usb, router, box, walls)
    assert router.boxes == [] and walls == []


# ------------------------------------------------------------ connectivity


def test_every_pin_is_on_its_net_node_and_no_node_mixes_two_nets():
    page = _pages(_compile(True))[0]
    derived = readability.derive_netlist(page.plan, BOOK)

    pin_net = {
        member: net.id for net in CIRCUIT.nets for member in net.members
    }
    for net in CIRCUIT.nets:
        group = set(derived.group_of(net.members[0]))
        assert group == set(net.members), (
            f"net {net.id!r} draws {sorted(group)}, spec says {sorted(net.members)}"
        )
    for group in derived.groups:
        nets = {pin_net[pin] for pin in group if pin in pin_net}
        assert len(nets) <= 1, f"one node mixes spec nets {sorted(nets)}: {group}"
