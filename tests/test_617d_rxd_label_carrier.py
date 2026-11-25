"""617D: a native name may not be printed in the neighbour part's text band.

The 543d page printed `U1.3 RXD` at `(532, 735.5)-(556, 744.5)` with its anchor
at `(640, 740)` — 84 units out on a horizontal stub, one unit from C3's
reference row, so the pin read as C3's name. The box was the module compiler's
own reservation (its ladder rejects against that module's *coarse* part box),
and the page's re-seat only asked "is the box on the anchor's axis" — which it
was — so the drift was never measured.

The fix is in `pagecompiler`: an on-axis box past the seat ladder's own reach
that also stands inside another part's text band (S-21's floor) goes back on
`_native_label_seat`, whose distance is the own-carrier limit
(`readability.NATIVE_LABEL_CARRIER_LIMIT`, 10) for every wire the page cannot
prove is the label's own part's pin lead, and the grazing distance
(`readability.FLAG_BODY_CLEARANCE`, 5) only for a run that terminates on that
part's pin on that pin's own net (620D: part + profile + posed pin + net
membership, never a `part_id` or a net name alone). The page keeps its
candidates; the name moves to the near rung beside its own pin.

These tests read the compiled page, not the helper: the numbers below are the
drawing's, and both mutations of the fix (old seat rule, band question answered
"no") turn the first one red.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from boardwise.core.circuitspec import CircuitSpec  # noqa: E402
from boardwise.core.presentationspec import PresentationSpec  # noqa: E402
from boardwise.engines import drawapply, drawcompiler as dc  # noqa: E402
from boardwise.engines import pagecompiler as pc  # noqa: E402
from boardwise.engines import readability  # noqa: E402

SPECS = ROOT / "blocklib" / "specs"
CIRCUIT = SPECS / "ch343_uart_534a.circuit.json"
PRESENTATION = ROOT / "evidence" / "543d" / "effective.presentation.json"
LIBRARY = SPECS / "ch343_uart_v4.library.json"
PAGE_BOX = (0.0, 0.0, 1170.0, 825.0)

_CACHE: list = []


def _compile():
    if not _CACHE:
        circuit = CircuitSpec.load(CIRCUIT)
        presentation = PresentationSpec.load(PRESENTATION)
        budget = pc.PageCompileBudget(page_box=PAGE_BOX)
        result = pc.compile_page(
            circuit, presentation, drawapply.load_library(LIBRARY), budget)
        assert result.ok, result.render_failures()
        _CACHE.append((circuit, result))
    return _CACHE[0]


def _box_gap(one, other) -> float:
    dx = max(one[0] - other[2], other[0] - one[2], 0.0)
    dy = max(one[1] - other[3], other[1] - one[3], 0.0)
    return (dx * dx + dy * dy) ** 0.5


def _rxd(plan):
    label = next(
        item for item in plan.labels if item.net == "RXD" and item.part_id == "U1")
    box = tuple(float(value) for value in label.bbox)
    anchor = (float(label.x), float(label.y))
    centre = ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)
    return label, box, anchor, centre


def _reach(net: str) -> float:
    half = dc.text_width(net) / 2.0 + dc.TEXT_GAP
    return max(pc._NATIVE_LABEL_SEATS) * half


#: The box the 543d page reserved for `U1.3 RXD` before this batch: 96 units
#: from the pin, one unit from C3's reference. The test asks for strictly less,
#: so a "repair" that lands the name on another free-but-wrong seat cannot pass
#: by being merely different.
PRE_FIX_STUB = 96.0


def _drawn_bodies(plan, library):
    """Every part's drawn body box on the page, from the library and the pose."""
    out = []
    for part in plan.parts:
        pose = dc.SymbolPose(part.rotation, part.mirror)
        body = dc._body_box(library[part.symbol_ref], pose, (part.x, part.y))
        if body is not None:
            out.append((part.part_id, tuple(float(value) for value in body)))
    return out


def test_every_page_prints_rxd_beside_its_own_pin_and_off_c3():
    _, result = _compile()
    library = drawapply.load_library(LIBRARY)
    assert result.pages, "the real page must keep at least one candidate"
    for page in result.pages:
        plan = page.plan
        _, box, anchor, centre = _rxd(plan)
        assert abs(centre[1] - anchor[1]) <= readability.TOL, (
            f"RXD's box {box} left its anchor's row {anchor}")
        stub = abs(centre[0] - anchor[0]) + abs(centre[1] - anchor[1])
        assert 0.0 < stub < PRE_FIX_STUB, (
            f"RXD's name stands {stub:g} units from its pin at {anchor} "
            f"(box {tuple(round(v, 1) for v in box)}); this batch's whole claim "
            f"is a shorter stub than the 543d page's {PRE_FIX_STUB:g} units, "
            f"and the seat ladder's own reach is {_reach('RXD'):g}")
        # A name "on its carrier's axis" is not enough: this batch's failure mode
        # (gap_limit left at the own-carrier limit) makes the ladder hand back the
        # first *free* box, which on this page is U1's own body — 40 units away,
        # inside the IC. Fewer units from the anchor must therefore also mean the
        # outward side of its own pin, with no drawn body under the row.
        assert box[2] <= anchor[0] + readability.TOL, (
            f"RXD's box {tuple(round(v, 1) for v in box)} stands past its pin "
            f"{anchor} (towards the part body), not on the pin's outward side")
        for part_id, body in _drawn_bodies(plan, library):
            assert not (
                min(box[2], body[2]) - max(box[0], body[0]) > readability.TOL
                and min(box[3], body[3]) - max(box[1], body[1]) > readability.TOL
            ), (
                f"RXD's box {tuple(round(v, 1) for v in box)} lands on "
                f"{part_id}'s drawn body {tuple(round(v, 1) for v in body)}")
        c3 = next(item for item in plan.texts if item.text == "C3")
        gap = _box_gap(box, tuple(float(value) for value in c3.bbox))
        assert gap >= readability.SOFT_FLOOR_TEXT_GAP, (
            f"RXD's box {tuple(round(v, 1) for v in box)} stands {gap:g} units "
            f"from C3's reference "
            f"{tuple(round(v, 1) for v in c3.bbox)}: S-21 asks "
            f"{readability.SOFT_FLOOR_TEXT_GAP:g}, or the name reads as C3's")


def test_the_page_still_draws_every_pin_and_net():
    circuit, result = _compile()
    library = drawapply.load_library(LIBRARY)
    named = {net.id for net in circuit.nets}
    assert len(named) == 17, sorted(named)
    for page in result.pages:
        plan = page.plan
        pins = sum(len(library[part.symbol_ref].pins) for part in plan.parts)
        assert pins == 58, f"the page draws {pins} pins, not the fixture's 58"
        drawn = (
            {segment.net for segment in plan.segments}
            | {label.net for label in plan.labels if label.net}
            | {symbol.net for symbol in plan.power_symbols if symbol.net}
        )
        assert drawn <= named, sorted(drawn - named)
        assert {label.net for label in plan.labels if label.net} >= {
            "RXD", "TXD", "D+", "D-", "RTS", "CTS", "DTR", "DSR", "DCD", "RI"}
