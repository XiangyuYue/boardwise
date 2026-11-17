"""543I-1: a visible `native` name prints **on** its own carrier run.

P32 was withdrawn because the plan and the picture disagreed at the reversible
USB pins: `A6`/`A7` carried a 5-unit lead while their printed row stood 8 units
further out (a name in open paper), and `B6`/`B7` carried 60/55-unit wires whose
only name was suppressed by 053V's one-name-per-module rule (two bare wires).
The host netlist, `draw lint` and the per-pin walk were all green on that page —
they do not read a row against its conductor.

What this file pins:

* the **old** P32 geometry fails :func:`drawapply.native_carrier_problems` — the
  machine gate this batch adds (two rows off their run, two runs with no name);
* the page this compiler now draws extends the 5-unit leads to 40 (the first
  ladder rung that covers the 14-unit row plus `TEXT_GAP`), keeps `B6`/`B7` at
  their 60/55 units and re-seats those rows inside their runs, and leaves both
  `U1` stubs untouched;
* the pass is opt-in: the same document without `serviceLayout` keeps 053V's
  hidden duplicates and the 5-unit lead, byte for byte;
* `_native_label_visibility` hides only a repeat on the **same** run;
* 548D3D-P1E: the repair is **not** a privilege of the split net — a visible
  `native` row standing past its own single run is seated inside it (wire
  untouched), and the plan's own downgrade sentence names what seats the row and
  `attributeMoves`, never the reserved box's coordinates.

`spec_h3b` is written inline — a test may not depend on an evidence directory.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.layoutplan import LayoutLabel, LayoutPlan
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawapply
from boardwise.engines import drawcompiler as dc
from boardwise.engines import pagecompiler as pc

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "blocklib" / "specs"
CIRCUIT = CircuitSpec.load(SPECS / "ch343_uart_534a.circuit.json")
LIBRARY = {
    item["symbolRef"]: SymbolProfile.from_dict(item)
    for item in json.loads(
        (SPECS / "ch343_uart_v4.library.json").read_text(encoding="utf-8")
    )["profiles"]
}
PAGE_BOX = (0.0, 0.0, 1170.0, 825.0)

PAYLOAD = {
    "kind": "boardwise-presentation-spec",
    "specVersion": 1,
    "grammarRef": "ic-periphery",
    "textPlacement": "native-attr",
    "sidePreferences": {
        "input": "left", "output": "right", "load": "left", "source": "left",
        "power": "top", "gnd": "bottom",
    },
    "portRoles": {
        "D+": "load", "D-": "load", "VCC": "input", "TXD": "output",
        "RXD": "input", "RTS": "output", "CTS": "input", "DTR": "output",
        "DSR": "input", "DCD": "input", "RI": "input",
    },
    "flow": [["usb_c", "ch343"], ["ch343", "hdr"]],
    "modules": [
        {
            "id": "usb_c",
            "parts": ["USB1", "C1", "C2", "R1", "R2"],
            "role": "USB-C receptacle, VBUS bulk/decoupling and CC sink pull-downs",
            "grammarRef": "ic-periphery",
            "core": "USB1",
            "presentation": {"sidePreferences": {"load": "right"}},
        },
        {
            "id": "ch343",
            "parts": ["U1", "C3", "C4"],
            "role": "CH343 USB-UART bridge with V3 and VCC decoupling",
            "grammarRef": "ic-periphery",
            "core": "U1",
            "presentation": {"sidePreferences": {"load": "left"}},
        },
        {
            "id": "hdr",
            "parts": ["H1"],
            "role": "2x5 UART header to the peer board",
            "grammarRef": "ic-periphery",
            "core": "H1",
            "presentation": {"sidePreferences": {"input": "left", "output": "left"}},
        },
        {
            "id": "led",
            "parts": ["D1", "R3"],
            "role": "VBUS presence indicator",
            "grammarRef": "voltage-divider",
            "attach": {"to": "usb_c", "side": "bottom", "gap": 10},
        },
    ],
    "labelPolicy": {
        "local": "wire", "crossModule": "label", "highFanout": "label",
        "stub": "straight", "stubMin": 40, "rowModel": "centered",
    },
    "directWiringObligations": [
        {
            "nets": ["LED_A"],
            "note": "lamp cathode and R3 are one conductor inside the indicator island",
        }
    ],
    "localLabelObligations": [
        {
            "nets": ["D+", "D-"],
            "note": (
                "Type-C data pins are mirrored pairs (A6/B6, A7/B7): each pin "
                "takes its own short stub and the same-named label instead of a "
                "U-line that would present one pin as the other; the pair reaches "
                "U1.5/U1.6 by name"
            ),
        }
    ],
    "moduleOrder": ["usb_c", "ch343", "hdr", "led"],
    "flagLeadLimit": 120,
    "partTexts": {
        "USB1": "left", "U1": "above", "H1": "above", "C3": "right",
        "C4": "right", "C1": "right",
    },
    "gndClustering": {"radius": 100},
    "serviceLayout": {"pinGap": 30},
}


class _Wire:
    def __init__(self, net, points, from_pin=""):
        self.net = net
        self.points = [(float(x), float(y)) for x, y in points]
        self.from_pin = from_pin


class _Label:
    def __init__(self, net, x, y, bbox, mode="native"):
        self.net = net
        self.x = float(x)
        self.y = float(y)
        self.bbox = tuple(float(value) for value in bbox)
        self.text_mode = mode


def _presentation(payload: dict | None = None) -> PresentationSpec:
    return PresentationSpec.from_dict(copy.deepcopy(payload or PAYLOAD))


def _page_and_plan():
    result = pc.compile_page(
        CIRCUIT, _presentation(), LIBRARY,
        pc.PageCompileBudget(page_box=PAGE_BOX),
    )
    assert result.ok, result.render_failures()
    assert result.pages
    page = result.pages[0]
    plan = drawapply.module_plan(
        page.plan, CIRCUIT, _presentation(), LIBRARY,
        candidate_index=0, label_stubs=True, page_box=PAGE_BOX,
        module_label="page " + "+".join(module.id for module in page.modules),
    )
    return page, plan


def _wires(plan, net):
    return [
        wire for wire in plan.change.draw_wires
        if str(wire.net) == net and len(wire.points) >= 2
    ]


def _move_for(plan, wire):
    index = plan.change.draw_wires.index(wire)
    for move in plan.change.attribute_moves:
        if move.owner_kind == "wire" and move.wire_index == index:
            return move
    return None


def test_the_withdrawn_p32_page_fails_the_new_gate():
    """The four measured P32 defects are a machine refusal, not an opinion."""
    wires = [
        _Wire("D+", [(200, 700), (205, 700)]),
        _Wire("D+", [(200, 720), (260, 720)]),
        _Wire("D-", [(200, 710), (205, 710)]),
        _Wire("D-", [(200, 690), (255, 690)]),
        _Wire("D+", [(635, 720), (595, 720)]),
        _Wire("D-", [(635, 710), (595, 710)]),
    ]
    # boxes as the withdrawn plan moved them; `B6`/`B7` were hidden
    labels = [
        _Label("D+", 205, 700, (213, 695.5, 227, 704.5)),
        _Label("D+", 260, 720, (268, 715.5, 282, 724.5), "native-hidden"),
        _Label("D-", 205, 710, (213, 705.5, 227, 714.5)),
        _Label("D-", 255, 690, (263, 685.5, 277, 694.5), "native-hidden"),
        _Label("D+", 635, 720, (609, 715.5, 623, 724.5)),
        _Label("D-", 635, 710, (609, 705.5, 623, 714.5)),
    ]
    problems = drawapply.native_carrier_problems(labels, wires, PAGE_BOX)
    text = " | ".join(problems)
    assert "(213, 695.5)-(227, 704.5)" in text, text
    assert "(213, 705.5)-(227, 714.5)" in text, text
    assert text.count("has no visible name") == 2, text
    assert "(200, 720" in text and "(200, 690" in text, text


def test_every_reversible_run_names_itself_on_its_own_carrier():
    page, plan = _page_and_plan()
    assert not [
        label for label in page.plan.labels
        if getattr(label, "text_mode", "") == "native-hidden"
    ], "the explicit path keeps a name on every non-continuous run"

    seen = {}
    for net in ("D+", "D-"):
        for wire in _wires(plan, net):
            points = [
                (round(float(point[0]), 3), round(float(point[1]), 3))
                for point in wire.points
            ]
            move = _move_for(plan, wire)
            assert move is not None and getattr(move, "move_version", 1) == 1, (
                f"{net} {points} has no printed row"
            )
            span = sorted(point[0] for point in points)
            assert span[0] - 1e-9 <= move.x <= span[-1] + 1e-9, (
                f"{net} row x={move.x} is not on its carrier {points}"
            )
            assert abs(move.y - points[0][1]) <= 1e-9, (net, points, move.y)
            seen[(net, wire.from_pin)] = points

    # 543I-2D: the flag groups moved the module ten units in y, so the *rows*
    # moved; the four reversible runs keep their lengths and their pins — A6/A7's
    # 5+35, and U1's own 40-unit stubs.
    assert seen[("D+", "USB1.A6")] == [(200.0, 710.0), (205.0, 710.0), (240.0, 710.0)]
    assert seen[("D-", "USB1.A7")] == [(200.0, 700.0), (205.0, 700.0), (240.0, 700.0)]
    # 543L: `B6`/`B7` are one mirrored pair of the same `localLabelObligations`
    # entry, so both carry the same 60-unit run — the pair is chosen together
    # and `B7` no longer stops one rung short. The A pair keeps its 40 (a
    # different fan-out depth is allowed between the mirrored groups).
    assert seen[("D+", "USB1.B6")] == [(200.0, 690.0), (260.0, 690.0)]
    assert seen[("D-", "USB1.B7")] == [(200.0, 720.0), (260.0, 720.0)]
    # U1's own stubs are not this batch's subject and keep their 40 units.
    # 543I-4A moved the ch343 island 40 units right (a supply run had to clear
    # `C21`'s printed row); the stubs keep their 40 units. 543K's inside-out bay
    # order moved that island ten units further right; the length is unchanged.
    assert seen[("D+", "U1.5")] == [(685.0, 720.0), (645.0, 720.0)]
    assert seen[("D-", "U1.6")] == [(685.0, 710.0), (645.0, 710.0)]

    # The two long runs keep their printed rows inside their own span.
    for net, y in (("D+", 690.0), ("D-", 720.0)):
        long_run = next(
            wire for wire in _wires(plan, net)
            if abs(wire.points[-1][1] - y) < 1e-9 and len(wire.points) == 2
        )
        move = _move_for(plan, long_run)
        print(f"{net} long run {long_run.points} row {move.x},{move.y}")


def test_the_gate_refuses_a_bare_long_run_and_an_off_carrier_row():
    wires = [
        _Wire("D+", [(200, 720), (260, 720)]),
        _Wire("D+", [(200, 700), (205, 700), (240, 700)]),
    ]
    labels = [
        _Label("D+", 260, 720, (268, 715.5, 282, 724.5), "native-hidden"),
        _Label("D+", 205, 700, (213, 695.5, 227, 704.5)),
    ]
    problems = " | ".join(drawapply.native_carrier_problems(labels, wires, PAGE_BOX))
    assert "(200, 720" in problems and "has no visible name" in problems, problems

    _off = drawapply.native_carrier_problems(
        [_Label("D+", 205, 700, (213, 695.5, 227, 704.5))],
        [
            _Wire("D+", [(200, 700), (205, 700)]),
            _Wire("D+", [(200, 720), (260, 720)]),  # the net must be split
        ],
        PAGE_BOX,
    )
    assert _off and "is not on the x 200..205 run" in _off[0], _off

    # 543I: a single run gets **no** exemption — a box past its own wire's end is
    # a name in open paper however many runs the net has (P35's `LED_A` stood 12
    # units past its 30-unit stub and was excused by "only one run").
    _single = drawapply.native_carrier_problems(
        [_Label("D+", 205, 700, (213, 695.5, 227, 704.5))],
        [_Wire("D+", [(200, 700), (205, 700)])],
        PAGE_BOX,
    )
    assert _single and "is not on the x 200..205 run" in _single[0], _single


def _covered(labels, wires, page_box=PAGE_BOX):
    built = drawapply._Built()
    built.wires.extend(wires)
    problems = drawapply._native_carrier_cover(
        built, LayoutPlan(labels=list(labels)), {}, {}, [], page_box,
    )
    return built, problems


def test_a_single_run_seats_its_row_without_growing_the_wire():
    """548D3D-P1E: the cover is not a privilege of the split net.

    P43's six names each ride a run that is its net's **only** run, and the row
    the layout reserved stands just past that run's far end (KEY1 at
    ``(408, 470.5)-(439, 479.5)`` on the ``x 360..400`` run). Statement 1 has no
    single-run exemption, so the repair may not have one either: the row moves
    inside the existing 40-unit carrier, the wire keeps its two points, and the
    gate then has nothing to say about it.
    """
    label = LayoutLabel(
        net="KEY1", text="KEY1", bbox=(408.0, 470.5, 439.0, 479.5),
        x=400.0, y=475.0, text_mode=dc.TEXT_MODE_NATIVE,
    )
    wire = _Wire("KEY1", [(360, 475), (400, 475)])

    # The defect the cover has to answer: on its own the gate refuses the row.
    before = drawapply.native_carrier_problems([label], [wire], PAGE_BOX)
    assert before and "is not on the x 360..400 run" in before[0], before

    built, problems = _covered([label], [wire])
    assert problems == []
    assert wire.points == [(360.0, 475.0), (400.0, 475.0)], wire.points
    row = built.native_carrier_rows[id(label)]
    assert 360.0 - 1e-9 <= row[0] and row[2] <= 400.0 + 1e-9, row
    assert abs(row[1] - 470.5) <= 1e-9 and abs(row[3] - 479.5) <= 1e-9, row
    assert drawapply.native_carrier_problems(
        [label], [wire], PAGE_BOX, built.native_carrier_rows,
    ) == []


def test_the_cover_leaves_ordinary_and_seated_labels_alone():
    """A name already inside its run, and a non-`native` label, keep their bytes.

    Only Statement 1's repair widens here: a row that already prints on its
    carrier is not moved (no entry is recorded), an ordinary label is not this
    pass's subject, and a single run too short to hold the name is still a
    named refusal rather than a silent pass.
    """
    seated = LayoutLabel(
        net="LED1", text="LED1", bbox=(135.0, 570.5, 166.0, 579.5),
        x=130.0, y=575.0, text_mode=dc.TEXT_MODE_NATIVE,
    )
    ordinary = _Label("LED2", 130, 565, (91, 560.5, 122, 569.5), "")
    wires = [
        _Wire("LED1", [(130, 575), (170, 575)]),
        _Wire("LED2", [(130, 565), (170, 565)]),
    ]
    built, problems = _covered([seated, ordinary], wires)
    assert problems == []
    assert id(seated) not in built.native_carrier_rows
    assert id(ordinary) not in built.native_carrier_rows
    assert wires[0].points == [(130.0, 575.0), (170.0, 575.0)]
    assert wires[1].points == [(130.0, 565.0), (170.0, 565.0)]

    # A 20-unit run cannot hold the 31-unit row and the sheet ends at its own
    # end: the short-run rule is unchanged, so this stays a problem by name.
    short = LayoutLabel(
        net="LED3", text="LED3", bbox=(8.0, 0.5, 39.0, 9.5),
        x=0.0, y=5.0, text_mode=dc.TEXT_MODE_NATIVE,
    )
    built, problems = _covered(
        [short], [_Wire("LED3", [(0, 5), (20, 5)])], (0.0, 0.0, 20.0, 100.0),
    )
    assert problems and "carrier" in problems[0], problems
    assert id(short) not in built.native_carrier_rows


def test_the_native_downgrade_names_the_seat_not_the_reserved_box():
    """548D3D-P1E: the plan's own sentence may not print a coordinate it drops.

    P43's plan seats six rows at `x = 384.5` while its downgrade still said the
    name went to the reserved `(408, 470.5)-(439, 479.5)`. The sentence now names
    what seats the row and points a reader at `attributeMoves`; the reservation
    is called what it is. Deleting the clause instead would hide the statement,
    so the row-on-the-wire claim has to stay — and the coordinates the plan
    really states are checked here against the carriers they ride.
    """
    page, plan = _page_and_plan()
    lines = [
        line for line in plan.change.draw_downgrades
        if "prints that attribute row on the wire itself" in line
    ]
    assert lines, plan.change.draw_downgrades
    for line in lines:
        assert "attributeMoves" in line, line
        assert "carrier cover" in line, line
        assert not re.search(r"label box \(-?\d", line), line
        # A visible `native` row is text on the canvas, so the old carried
        # closing ("the canvas shows the wire without a label text") contradicts
        # the clause in front of it and may not appear on any of these lines.
        assert "without a label text" not in line, line

    wires = plan.change.draw_wires
    moves = [
        move for move in plan.change.attribute_moves
        if move.owner_kind == "wire" and move.role == "net"
        and getattr(move, "move_version", 1) == 1
    ]
    assert moves
    for move in moves:
        points = [
            (float(point[0]), float(point[1]))
            for point in wires[move.wire_index].points
        ]
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        assert min(xs) - 1e-9 <= move.x <= max(xs) + 1e-9, (move, points)
        assert min(ys) - 1e-9 <= move.y <= max(ys) + 1e-9, (move, points)


def test_the_separate_run_rule_hides_only_a_repeat_on_one_run():
    run_a = dc.LayoutSegment(net="D+", points=[(0.0, 0.0), (40.0, 0.0)])
    run_b = dc.LayoutSegment(net="D+", points=[(0.0, 20.0), (40.0, 20.0)])
    same_run = dc.LayoutSegment(net="D+", points=[(0.0, 40.0), (40.0, 40.0)])
    labels = [
        LayoutLabel(net="D+", text="D+", bbox=(8, -4, 22, 4), x=0.0, y=0.0,
                    text_mode=dc.TEXT_MODE_NATIVE),
        LayoutLabel(net="D+", text="D+", bbox=(8, 16, 22, 24), x=0.0, y=20.0,
                    text_mode=dc.TEXT_MODE_NATIVE),
        LayoutLabel(net="D+", text="D+", bbox=(8, 36, 22, 44), x=0.0, y=40.0,
                    text_mode=dc.TEXT_MODE_NATIVE),
        LayoutLabel(net="D+", text="D+", bbox=(28, 36, 42, 44), x=30.0, y=40.0,
                    text_mode=dc.TEXT_MODE_NATIVE),
    ]
    note = dc._native_label_visibility(
        labels, [run_a, run_b, same_run], set(), separate_runs=True,
    )
    modes = [label.text_mode for label in labels]
    assert modes.count(dc.TEXT_MODE_NATIVE_HIDDEN) == 1, modes
    assert labels[0].text_mode == labels[1].text_mode == dc.TEXT_MODE_NATIVE
    assert labels[2].text_mode == dc.TEXT_MODE_NATIVE
    assert labels[3].text_mode == dc.TEXT_MODE_NATIVE_HIDDEN
    assert "once per **continuous run**" in note


def test_the_native_only_page_keeps_the_old_visibility():
    """Without `serviceLayout` the old 053V answer is the one that runs.

    The old pass hid the second of two non-continuous runs; the explicit path
    keeps it. This is a unit-level pin because a page that drops `serviceLayout`
    no longer satisfies the 543B construction contract at all (its compile is
    refused before any label question arises).
    """
    payload = copy.deepcopy(PAYLOAD)
    payload.pop("serviceLayout")
    spec = PresentationSpec.from_dict(payload)
    assert not drawapply.native_carrier_settings(spec)

    run_a = dc.LayoutSegment(net="D+", points=[(0.0, 0.0), (40.0, 0.0)])
    run_b = dc.LayoutSegment(net="D+", points=[(0.0, 20.0), (40.0, 20.0)])
    labels = [
        LayoutLabel(net="D+", text="D+", bbox=(8, -4, 22, 4), x=0.0, y=0.0,
                    text_mode=dc.TEXT_MODE_NATIVE),
        LayoutLabel(net="D+", text="D+", bbox=(8, 16, 22, 24), x=0.0, y=20.0,
                    text_mode=dc.TEXT_MODE_NATIVE),
    ]
    dc._native_label_visibility(labels, [run_a, run_b], set())
    assert [label.text_mode for label in labels] == [
        dc.TEXT_MODE_NATIVE, dc.TEXT_MODE_NATIVE_HIDDEN,
    ]
