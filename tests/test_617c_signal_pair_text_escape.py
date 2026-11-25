"""617C: an opt-in signal pair may lie horizontal only where the page states the
host's own text side.

543K pinned the horizontal pair on a page whose `partTexts` states `USB1:left`;
the hole570 H2-01 page (`evidence/543d/effective.presentation.json`) states no
side for the same connector, and there the horizontal pair plus the text placed
beside the right pin column filled the corridor the `+5V` flag and the `D+`/`D-`
labels need — the page came out with no candidate at all.

The rule pinned here is the structural gate inside
:func:`drawcompiler._signal_pair_body_direction`: when the pair's **owner**
stands a flag seat on its own pins and prints rows of its own (the anchors
:func:`boardwise.core.textmetrics.symbol_rows` declares), the horizontal pose is
only taken when the presentation states the owner's text side as ``left`` or
``right``. Everywhere else the branch keeps the vertical pose it always had.
Silence is the historical drawing, so a page that says nothing cannot lose the
pose it had.
"""

from __future__ import annotations

import copy
import pathlib

from boardwise.core import textmetrics
from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.engines import drawapply
from boardwise.engines import drawcompiler as dc
from boardwise.engines import pagecompiler as pc

import test_543h3b_stated_text_lane as t3b

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPECS = ROOT / "blocklib" / "specs"
CIRCUIT = SPECS / "ch343_uart_534a.circuit.json"
LIBRARY = SPECS / "ch343_uart_v4.library.json"
RECORDED = ROOT / "evidence" / "543d" / "effective.presentation.json"
PAGE_BOX = (0.0, 0.0, 1170.0, 825.0)


def _library():
    return drawapply.load_library(LIBRARY)


def _payload(*drop):
    payload = copy.deepcopy(t3b.PAYLOAD)
    for key in drop:
        payload.pop(key, None)
    return payload


def _without_stated_side(payload, part_id):
    payload["partTexts"].pop(part_id, None)
    return payload


def _context(presentation):
    circuit = CircuitSpec.load(CIRCUIT)
    local_circuit, local_presentation = pc._module_view(
        circuit, presentation, presentation.module("usb_c")
    )
    binding = dc.bind_grammar(local_circuit, local_presentation, _library())
    return dc._prepare(
        local_circuit, local_presentation, binding, _library(), dc.CompileBudget(),
    ).context


def _pair(context, part_id):
    slot = context.slots[part_id]
    return (
        dc._signal_pair_body_direction(context, slot),
        context.body_dirs[part_id],
    )


def test_the_recorded_page_without_a_stated_side_keeps_the_pair_upright():
    """hole570 H2-01: no `USB1` side stated -> the pair keeps its old pose."""
    context = _context(PresentationSpec.load(RECORDED))
    assert dc._pair_bands(context) is True
    assert {seat.part_id for seat in dc._flag_seats(context)} >= {"USB1"}
    assert dc._stated_part_text_side(context, "USB1") == ""
    for part_id in ("R1", "R2"):
        rule, body = _pair(context, part_id)
        assert rule is None, (part_id, rule)
        assert body == (0.0, -1.0), (part_id, body)
    result = pc.compile_page(
        CircuitSpec.load(CIRCUIT), PresentationSpec.load(RECORDED),
        _library(), pc.PageCompileBudget(page_box=PAGE_BOX),
    )
    assert result.ok, result.render_failures()
    assert result.pages, "the recorded page drew no candidate"


def test_a_stated_side_keeps_the_pinned_pair_horizontal():
    """543K's own page states `USB1:left`, and the pair stays horizontal."""
    context = _context(PresentationSpec.from_dict(_payload()))
    assert dc._stated_part_text_side(context, "USB1") == "left"
    for part_id in ("R1", "R2"):
        assert _pair(context, part_id) == ((1.0, 0.0), (1.0, 0.0)), part_id


def test_the_gate_answers_to_the_stated_side_not_to_the_page():
    """The only difference between the two pages is the one stated side."""
    stated = _context(PresentationSpec.from_dict(_payload()))
    silent = _context(
        PresentationSpec.from_dict(_without_stated_side(_payload(), "USB1"))
    )
    for part_id in ("R1", "R2"):
        assert _pair(stated, part_id) == ((1.0, 0.0), (1.0, 0.0)), part_id
        assert _pair(silent, part_id) == (None, (0.0, -1.0)), part_id


def test_one_key_alone_still_says_nothing():
    """543H-5's gate outranks this one: one key keeps every pose it had."""
    for drop in (("serviceLayout",), ("textPlacement",)):
        context = _context(PresentationSpec.from_dict(_payload(*drop)))
        assert dc._pair_bands(context) is False, drop
        for part_id in ("R1", "R2"):
            assert _pair(context, part_id) == (None, (0.0, -1.0)), (drop, part_id)


def test_no_flag_seat_or_no_declared_rows_keeps_the_horizontal_pose(monkeypatch):
    """The gate is the pair of structures, not the silence alone."""
    silent = _without_stated_side(_payload(), "USB1")
    seats = dc._flag_seats
    monkeypatch.setattr(dc, "_flag_seats", lambda ctx: ())
    context = _context(PresentationSpec.from_dict(copy.deepcopy(silent)))
    for part_id in ("R1", "R2"):
        assert _pair(context, part_id) == ((1.0, 0.0), (1.0, 0.0)), part_id
    monkeypatch.setattr(dc, "_flag_seats", seats)

    rows = textmetrics.symbol_rows
    monkeypatch.setattr(
        textmetrics, "symbol_rows",
        lambda *a, **kw: [] if kw.get("pose") is None else rows(*a, **kw),
    )
    context = _context(PresentationSpec.from_dict(copy.deepcopy(silent)))
    for part_id in ("R1", "R2"):
        assert _pair(context, part_id) == ((1.0, 0.0), (1.0, 0.0)), part_id
