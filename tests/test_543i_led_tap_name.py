"""543I: a promised island-local tap is one conductor, and no name beside it.

P35's indicator island (`D1` → `R3`, net `LED_A`) is stated by the document as a
`directWiringObligations` net — "lamp cathode and R3 are one conductor inside the
indicator island". The grammar also reads the pair as a `voltage-divider` tap, so
`053 sec.3`'s stub-and-name was drawn on top of that conductor: a 30-unit T-stub
with the name at its far end, and the printed row stood 12 units past the stub's
end (543I-7 §11). The net was already one visible wire; the second statement cost
a T and a name in open paper.

What this file pins:

* the conduction rule: a `directWiringObligations` net whose parts all sit in one
  declared module is drawn as **one** run that reaches its pads, with no stub and
  no printed name — and the obligation is the switch (drop it and the stub comes
  back);
* the gate's half: `native_carrier_problems` no longer exempts a single run, so
  the old `LED_A` row (30-unit stub, 39-wide box 12 units past its end) is refused
  by name, and the page this compiler draws passes `module_plan` clean;
* the boundary of the rule: a net that spans two modules (or is a stated local
  label exception) is **not** listed, and the page keeps its cross-module names.

`spec_h3b`'s payload, circuit and library are the 543I-1 file's own — one inline
copy, not a second one to keep in step.
"""

from __future__ import annotations

import copy

import pytest

import test_543i_visible_labels as labels_543i
from boardwise.core.presentationspec import PresentationSpec
from boardwise.engines import drawapply
from boardwise.engines import drawcompiler as dc
from boardwise.engines import pagecompiler as pc

PAYLOAD = labels_543i.PAYLOAD
CIRCUIT = labels_543i.CIRCUIT
LIBRARY = labels_543i.LIBRARY
PAGE_BOX = labels_543i.PAGE_BOX


def _page(payload: dict | None = None):
    result = pc.compile_page(
        CIRCUIT, PresentationSpec.from_dict(copy.deepcopy(payload or PAYLOAD)),
        LIBRARY, pc.PageCompileBudget(page_box=PAGE_BOX),
    )
    assert result.ok, result.render_failures()
    return result.pages[0]


def _led_a(page):
    return (
        [item for item in page.plan.segments if item.net == "LED_A"],
        [item for item in page.plan.labels if item.net == "LED_A"],
    )


def test_the_obligated_island_tap_keeps_one_conductor_and_no_name():
    """`LED_A` is a wire the reader follows — not a stub with a printed name."""
    page = _page()
    segments, labels = _led_a(page)
    assert labels == [], labels
    assert len(segments) == 1, [item.points for item in segments]
    points = [(float(x), float(y)) for x, y in segments[0].points]
    assert len(points) == 2 and points[0][0] == points[1][0], points
    pins = dc._net_member_points(page.plan, CIRCUIT, LIBRARY, "LED_A")
    assert {member for member, _point in pins} == {"D1.2", "R3.1"}
    assert all(dc._on_polyline(point, points) for _member, point in pins), pins
    # No T: the junction the stubbed version teed into is gone with the stub.
    assert not [item for item in page.plan.junctions if item.net == "LED_A"]

    # The page the compiler draws goes through the landing gate unchanged, and
    # the conductor lands with no net name (岳's ruling A: names live on flags
    # and labels, and this net has neither).
    plan = drawapply.module_plan(
        page.plan, CIRCUIT, PresentationSpec.from_dict(copy.deepcopy(PAYLOAD)),
        LIBRARY, candidate_index=0, label_stubs=True, page_box=PAGE_BOX,
    )
    carried = {
        str(wire.net) for wire in plan.change.draw_wires
        if "carries this net's label" in (wire.purpose or "")
    }
    assert "LED_A" not in carried, carried
    led_wires = [
        wire for wire in plan.change.draw_wires
        if str(wire.net) == "LED_A" and len(wire.points) >= 2
    ]
    assert len(led_wires) == 1, [wire.points for wire in led_wires]


def test_without_the_obligation_the_tap_keeps_its_stub_and_name():
    """The switch is the document's promise, not a shape the net happens to have."""
    payload = copy.deepcopy(PAYLOAD)
    payload.pop("directWiringObligations")
    segments, labels = _led_a(_page(payload))
    assert labels, "the unstated tap still carries its printed name"
    assert len(segments) == 2, [item.points for item in segments]


def test_the_old_led_a_row_is_refused_by_name():
    """30-unit stub, 39-wide box 12 units past its end — one run, no exemption."""
    wires = [
        labels_543i._Wire("LED_A", [(220, 435), (250, 435)]),
        labels_543i._Wire("LED_A", [(220, 415), (220, 455)]),
    ]
    labels = [
        labels_543i._Label("LED_A", 250, 435, (262, 430.5, 301, 439.5)),
    ]
    problems = drawapply.native_carrier_problems(labels, wires, PAGE_BOX)
    assert problems, "a name in open paper is a refusal"
    assert len(problems) == 1 and "LED_A" in problems[0], problems
    assert "is not on the x 220..250 run" in problems[0], problems[0]
    assert "(262, 430.5)-(301, 439.5)" in problems[0], problems[0]


def test_a_cross_island_or_locally_named_net_is_not_the_rule():
    """Only the undivided island-local promise takes the tap's name away."""
    spec = PresentationSpec.from_dict(copy.deepcopy(PAYLOAD))
    assert dc._one_conductor_nets(spec, CIRCUIT) == {"LED_A"}

    stated = copy.deepcopy(PAYLOAD)
    stated["directWiringObligations"] = [
        {"nets": ["LED_A", "RXD"], "note": "one conductor, no name beside it"},
    ]
    widened = PresentationSpec.from_dict(stated)
    # `RXD` runs usb_c ↔ ch343, `D+` is a stated local-label exception: both keep
    # their names, so neither may take the tap's opt-out.
    assert dc._one_conductor_nets(widened, CIRCUIT) == {"LED_A"}

    # The pass is the explicit construction's (543B): a page that states no
    # `serviceLayout` keeps its drawing, tap stub and printed name included.
    plain = copy.deepcopy(PAYLOAD)
    plain.pop("serviceLayout")
    assert dc._one_conductor_nets(PresentationSpec.from_dict(plain), CIRCUIT) == set()

    # And on the page, the cross-module names are still printed.
    names = {str(label.net) for label in _page().plan.labels}
    assert {"RXD", "TXD"} <= names, names
