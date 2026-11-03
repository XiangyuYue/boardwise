"""053W: a flag's glyph is not a place to draw a conductor — and not a place to
grazed either (053W 续, 岳's ruling).

The claims, one test each:

1. **reported when it happens** — the page 岳 rejected (P20: the GND glyph pressed
   into the RXD and +5V wires) is reproduced as a plan and the hard kind
   `flag-body-on-wire` names the flag (net, `symbolRef`, measured box) and the
   wire (index, net);
2. **touch is a defect** — the box is measured with :data:`FLAG_BODY_CLEARANCE`
   (5 units, the same ruler `drawcompiler.FLAG_CLEARANCE` states): a wire along an
   edge, a corner touch or a run 2 units off the box is reported with the gap it
   leaves; only beyond 5 units is it clean;
3. **the normal lead is the one exemption** — same net, an endpoint on the anchor,
   the first step away from the glyph: not reported even though five units of it
   run beside the box;
4. **a same-net trunk is not exempt** — `_flag_room` already refuses to thread a
   flag with its own net, and a trunk that merely passes near the anchor is
   reported like the foreign net it cannot be told apart from;
5. **an unmeasurable flag is not a measured clean one** — no profile/body means
   no box and no verdict;
6. **the native page moves the flag instead of printing it on the wire** — the
   nearest legal grid position, `symbolRef`/net/rotation kept, a straight same-net
   run from the old anchor, the port and the module frame in step, a note that
   says where it came from, and the **same** clearance rule for the candidate as
   for the finished page (`_check_flag_body_on_wire` finds nothing after the
   move);
7. **no legal position refuses the page** — a `GrammarFailure`, never the old
   printing and never a deleted flag;
8. **a spec without `textPlacement` never moves a flag** — the helper is the
   switch's single reader, so a plain page is untouched.

Nothing under ``tests/fixtures/`` is written: the geometry is the measured
`PWR-GND` / `PWR-+5V` profile read from the CH343 library, and the layouts are
built in process.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from boardwise.core.layoutplan import LayoutPlan, LayoutPowerSymbol, LayoutSegment
from boardwise.core.pagelayoutplan import PAGE_PORT_FLAG, PagePort
from boardwise.core.symbolprofile import flag_glyph_box
from boardwise.engines import drawapply, pagecompiler, readability

LIBRARY = (
    Path(__file__).resolve().parents[1] / "blocklib" / "specs" / "ch343_uart_v4.library.json"
)
GND_ANCHOR = (205.0, 747.5)


@pytest.fixture(scope="module")
def profiles():
    return drawapply.load_library(LIBRARY)


def _flag(net="GND", x=GND_ANCHOR[0], y=GND_ANCHOR[1]) -> LayoutPowerSymbol:
    return LayoutPowerSymbol(
        symbol_ref="PWR-GND" if net == "GND" else "PWR-+5V",
        symbol_hash="",
        net=net,
        x=x,
        y=y,
        rotation=0.0,
    )


def _plan(segments, *flags) -> LayoutPlan:
    return LayoutPlan(segments=list(segments), power_symbols=list(flags))


def _glyph(profiles, symbol):
    return flag_glyph_box(
        profiles[symbol.symbol_ref],
        rotation=symbol.rotation,
        anchor=(symbol.x, symbol.y),
    )


def _gnd_on_rxd_and_plus5(profiles):
    """The rejected page in miniature: GND's bars under RXD and beside +5V."""
    flag = _flag()
    return _plan(
        [
            LayoutSegment(net="RXD", points=[(180.0, 735.0), (230.0, 735.0)]),
            LayoutSegment(net="+5V", points=[(210.0, 720.0), (210.0, 760.0)]),
            # the flag's own lead, leaving the connection point downwards
            LayoutSegment(net="GND", points=[(205.0, 760.0), GND_ANCHOR]),
        ],
        flag,
    ), flag


# --------------------------------------------------------- 1. the reproduction


def test_gnd_glyph_on_rxd_and_plus5_is_reported(profiles):
    plan, flag = _gnd_on_rxd_and_plus5(profiles)
    got = readability._check_flag_body_on_wire(plan, dict(profiles))
    assert len(got) == 2, [item.evidence for item in got]
    assert {item.kind for item in got} == {readability.KIND_FLAG_BODY_ON_WIRE}
    assert {item.objects[1] for item in got} == {"segments[0]", "segments[1]"}
    for item in got:
        assert item.objects[0] == "powerSymbols[0]"
        assert "GND" in item.evidence and "PWR-GND" in item.evidence
        assert "RXD" in item.evidence or "+5V" in item.evidence
        assert "0 units from the glyph" in item.evidence
    box = _glyph(profiles, flag)
    assert f"{box[0]:g}" in got[0].evidence or f"{box[2]:g}" in got[0].evidence


def test_the_check_is_a_hard_kind_and_reaches_check(profiles):
    """The gate runs the rule on a **native** page only (0534ad)."""
    assert readability.KIND_FLAG_BODY_ON_WIRE == "flag-body-on-wire"
    assert readability.KIND_FLAG_BODY_ON_WIRE in readability.HARD_KINDS
    assert readability.FLAG_BODY_CLEARANCE == 5.0
    assert "FLAG_BODY_CLEARANCE" in readability.__all__
    plan, _flag_symbol = _gnd_on_rxd_and_plus5(profiles)
    from dataclasses import replace

    from boardwise.core.circuitspec import CircuitSpec
    from boardwise.core.presentationspec import (
        TEXT_PLACEMENT_NATIVE,
        PresentationSpec,
    )

    fixtures = Path(__file__).resolve().parent / "fixtures" / "drawapply"
    native = replace(
        PresentationSpec.load(fixtures / "divider.presentation.json"),
        text_placement=TEXT_PLACEMENT_NATIVE,
    )
    result = readability.check(
        plan,
        CircuitSpec.load(fixtures / "divider.circuit.json"),
        native,
        tuple(profiles.values()),
        page_box=(0.0, 0.0, 600.0, 900.0),
    )
    assert any(
        item.kind == readability.KIND_FLAG_BODY_ON_WIRE
        for item in result.hard_violations
    ), [item.kind for item in result.hard_violations]


def test_a_non_native_page_keeps_the_old_behaviour(profiles):
    """Negative control for 0534ad: the rule is the native model's, not the gate's.

    The same colliding plan still trips the specialist audit, but a spec that
    never wrote `textPlacement` must pass the gate exactly as it did before the
    5-unit clearance existed — the old layout is a contract, not an oversight.
    """
    plan, _flag_symbol = _gnd_on_rxd_and_plus5(profiles)
    from dataclasses import replace

    from boardwise.core.circuitspec import CircuitSpec
    from boardwise.core.presentationspec import (
        TEXT_PLACEMENT_NATIVE,
        PresentationSpec,
    )

    fixtures = Path(__file__).resolve().parent / "fixtures" / "drawapply"
    circuit = CircuitSpec.load(fixtures / "divider.circuit.json")
    legacy = PresentationSpec.load(fixtures / "divider.presentation.json")
    assert legacy.text_placement == ""

    direct = readability._check_flag_body_on_wire(plan, dict(profiles))
    assert direct, "the audited plan is supposed to collide"

    plain = readability.check(
        plan, circuit, legacy, tuple(profiles.values()),
        page_box=(0.0, 0.0, 600.0, 900.0),
    )
    assert not any(
        item.kind == readability.KIND_FLAG_BODY_ON_WIRE
        for item in plain.hard_violations
    ), [item.kind for item in plain.hard_violations]

    native = readability.check(
        plan, circuit, replace(legacy, text_placement=TEXT_PLACEMENT_NATIVE),
        tuple(profiles.values()),
        page_box=(0.0, 0.0, 600.0, 900.0),
    )
    assert any(
        item.kind == readability.KIND_FLAG_BODY_ON_WIRE
        for item in native.hard_violations
    ), [item.kind for item in native.hard_violations]


# --------------------------------- 2. touching the outline is now a defect too


def test_outline_and_corner_contacts_are_reported(profiles):
    """053W 续: the old "edge/corner is forgiven" test is inverted.

    The host's stroke is one unit wide: a conductor running along the box reads
    as a conductor through the flag on the landed page, which is what 岳 saw on
    P20 while every gate said "0 crossings".
    """
    flag = _flag()
    box = _glyph(profiles, flag)
    plan = _plan(
        [
            # the normal lead stays exempt
            LayoutSegment(net="GND", points=[(205.0, 760.0), GND_ANCHOR]),
            # a wire running along the box's left edge, and one along the top
            LayoutSegment(net="RXD", points=[(box[0], box[1]), (box[0], box[3])]),
            LayoutSegment(net="+5V", points=[(box[0], box[1]), (box[2], box[1])]),
            # a corner touch
            LayoutSegment(net="CC1", points=[(box[0], box[1]), (box[0] - 20.0, box[1] - 20.0)]),
        ],
        flag,
    )
    got = readability._check_flag_body_on_wire(plan, dict(profiles))
    assert {item.objects[1] for item in got} == {
        "segments[1]", "segments[2]", "segments[3]",
    }
    for item in got:
        assert "0 units from the glyph" in item.evidence


def test_a_wire_inside_the_clearance_band_is_reported(profiles):
    flag = _flag()
    box = _glyph(profiles, flag)
    plan = _plan(
        [
            LayoutSegment(net="GND", points=[(205.0, 760.0), GND_ANCHOR]),
            LayoutSegment(
                net="RXD",
                points=[(box[0] - 2.0, box[1] - 10.0), (box[0] - 2.0, box[3] + 10.0)],
            ),
        ],
        flag,
    )
    got = readability._check_flag_body_on_wire(plan, dict(profiles))
    assert len(got) == 1, [item.evidence for item in got]
    assert got[0].objects[1] == "segments[1]"
    assert "2 units from the glyph" in got[0].evidence


def test_a_wire_beyond_the_clearance_is_clean(profiles):
    flag = _flag()
    box = _glyph(profiles, flag)
    plan = _plan(
        [
            LayoutSegment(net="GND", points=[(205.0, 760.0), GND_ANCHOR]),
            LayoutSegment(
                net="RXD",
                points=[(box[0] - 6.0, box[1] - 10.0), (box[0] - 6.0, box[3] + 10.0)],
            ),
        ],
        flag,
    )
    assert readability._check_flag_body_on_wire(plan, dict(profiles)) == []


# --------------------------------------------- 3/4. lead exempt, trunk is not


def test_the_normal_lead_is_exempt(profiles):
    flag = _flag()
    plan = _plan(
        [
            LayoutSegment(net="GND", points=[(205.0, 760.0), GND_ANCHOR]),
        ],
        flag,
    )
    assert readability._check_flag_body_on_wire(plan, dict(profiles)) == []


def test_a_same_net_trunk_inside_the_band_is_reported(profiles):
    flag = _flag()
    box = _glyph(profiles, flag)
    plan = _plan(
        [
            LayoutSegment(net="GND", points=[(205.0, 760.0), GND_ANCHOR]),
            # same net, parallel two units off the box, not the flag's own lead
            LayoutSegment(
                net="GND",
                points=[(box[0] - 2.0, box[1] - 10.0), (box[0] - 2.0, box[3] + 10.0)],
            ),
        ],
        flag,
    )
    got = readability._check_flag_body_on_wire(plan, dict(profiles))
    assert len(got) == 1, [item.evidence for item in got]
    assert got[0].objects[1] == "segments[1]"
    assert "own net" in got[0].evidence
    assert "2 units from the glyph" in got[0].evidence


def test_the_flags_own_trunk_through_the_glyph_is_reported(profiles):
    plan, _flag_symbol = _gnd_on_rxd_and_plus5(profiles)
    plan.segments.append(
        LayoutSegment(net="GND", points=[(196.0, 700.0), (196.0, 760.0)])
    )
    got = readability._check_flag_body_on_wire(plan, dict(profiles))
    own = [item for item in got if item.objects[1] == "segments[3]"]
    assert len(own) == 1 and "own net" in own[0].evidence


# -------------------------------------------------- 5. no profile, no verdict


def test_an_unknown_profile_is_not_a_measured_zero(profiles):
    symbol = LayoutPowerSymbol(
        symbol_ref="PWR-NOWHERE", symbol_hash="", net="GND", x=205.0, y=747.5,
        rotation=0.0,
    )
    plan = _plan(
        [LayoutSegment(net="RXD", points=[(180.0, 735.0), (230.0, 735.0)])],
        symbol,
    )
    assert readability._check_flag_body_on_wire(plan, dict(profiles)) == []


# ----------------------------------------------- 6/7/8. the native page's move


def _native_ctx(profiles, page_box=(0.0, 0.0, 600.0, 900.0), placement="native-attr"):
    return SimpleNamespace(
        book=dict(profiles),
        budget=pagecompiler.PageCompileBudget(page_box=page_box, grid=5.0),
        presentation=SimpleNamespace(text_placement=placement),
    )


def _drawn(plan, ports=None):
    return pagecompiler._Drawn(
        segments=list(plan.segments),
        symbols=list(plan.power_symbols),
        ports={"ch343": list(ports or [])},
    )


def _frame() -> dict:
    return {"ch343": (100.0, 600.0, 400.0, 850.0)}


def test_native_page_moves_the_flag_to_the_nearest_legal_position(profiles):
    plan, flag = _gnd_on_rxd_and_plus5(profiles)
    drawn = _drawn(
        plan,
        [PagePort(module="ch343", net="GND", kind=PAGE_PORT_FLAG, x=205.0, y=747.5)],
    )
    frames = _frame()
    moved = pagecompiler._relocate_native_flags(
        _native_ctx(profiles), drawn, frames, {}
    )
    assert isinstance(moved, list) and len(moved) == 1, moved

    got = drawn.symbols[0]
    assert got.symbol_ref == "PWR-GND" and got.net == "GND"
    assert got.rotation == 0.0  # upright posture kept
    assert (got.x, got.y) != GND_ANCHOR
    assert got.x == GND_ANCHOR[0] and got.y < GND_ANCHOR[1]
    distance = GND_ANCHOR[1] - got.y
    assert distance % 5.0 == 0 and distance > 0

    # every run that is not the flag's own lead keeps the full clearance, and
    # the gate that will read the page agrees (one ruler, not two)
    glyph = _glyph(profiles, got)
    leads = [
        segment for segment in drawn.segments
        if segment.net == "GND" and segment.points[-1] == (got.x, got.y)
    ]
    assert len(leads) == 1
    lead_ids = {id(segment) for segment in leads}
    for segment in drawn.segments:
        offence = readability._flag_body_offence(
            got.net, (got.x, got.y), list(segment.points), glyph
        )
        if id(segment) in lead_ids:
            assert offence is None, offence  # the lead itself is exempt
            continue
        assert (
            readability._polyline_box_gap(list(segment.points), glyph)
            >= readability.FLAG_BODY_CLEARANCE
        ), segment
        assert offence is None, offence
    after = _plan(drawn.segments, got)
    assert readability._check_flag_body_on_wire(after, dict(profiles)) == []

    # the lead is one straight same-net run from the old anchor, no dangling end
    assert len(leads[0].points) == 2
    assert leads[0].points[0] == (205.0, 760.0)
    assert leads[0].points[1] == (got.x, got.y)
    assert readability._on_polyline(GND_ANCHOR, leads[0].points)

    assert drawn.ports["ch343"][0].x == got.x
    assert drawn.ports["ch343"][0].y == got.y
    assert frames["ch343"][1] <= glyph[1] and frames["ch343"][3] >= glyph[3]
    assert "moved from (205, 747.5)" in moved[0]
    assert "PWR-GND" in moved[0]
    assert "units from segments" in moved[0]


def test_no_legal_position_refuses_the_page(profiles):
    plan, _flag_symbol = _gnd_on_rxd_and_plus5(profiles)
    drawn = _drawn(plan)
    # a sheet exactly the size of the glyph: no move can keep it inside
    ctx = _native_ctx(profiles, page_box=(195.0, 728.5, 215.0, 747.5))
    got = pagecompiler._relocate_native_flags(ctx, drawn, _frame(), {})
    assert isinstance(got, pagecompiler.GrammarFailure)
    assert got.category == pagecompiler.FAILURE_LAYOUT_UNSAT
    assert "no position within" in got.detail
    assert "clearance" in got.detail
    # nothing was deleted, nothing was re-pointed: the refusal is honest
    assert drawn.symbols[0].x == GND_ANCHOR[0]
    assert drawn.symbols[0].y == GND_ANCHOR[1]
    assert drawn.segments[2].net == "GND"


def test_a_plain_spec_never_moves_a_flag(profiles):
    plan, _flag_symbol = _gnd_on_rxd_and_plus5(profiles)
    drawn = _drawn(plan)
    frames = _frame()
    before = [(seg.net, list(seg.points)) for seg in drawn.segments]
    assert pagecompiler._relocate_native_flags(
        _native_ctx(profiles, placement=""), drawn, frames, {}
    ) == []
    assert drawn.symbols[0].x == GND_ANCHOR[0]
    assert drawn.symbols[0].y == GND_ANCHOR[1]
    assert [(seg.net, list(seg.points)) for seg in drawn.segments] == before
    assert frames == _frame()


# ------------------- 9/10. the ladder asks the gate's ruler (053W续二)
#
# 053W续 measured the cost of two rulers: the usb_c `R1.2` ground sat where
# `_flag_room` was happy, the gate refused it at 1 unit (a wire routed one unit
# past the flag's own wall), and v45 compiled to **no candidate at all**. The
# ladder now asks `readability._flag_body_offence` — the gate's own function —
# of the candidate glyph, so a seat the ladder takes is a seat the gate accepts.

from boardwise.engines import drawcompiler


def _run_below(glyph, gap):
    """A foreign run parallel to the glyph's bottom edge, `gap` units off it."""
    y = glyph[3] + gap
    return [(glyph[0] - 20.0, y), (glyph[2] + 20.0, y)]


def test_the_ladder_ruler_is_the_gate_rule(profiles):
    profile = profiles["PWR-GND"]
    anchor = (0.0, 0.0)
    glyph = flag_glyph_box(profile, rotation=0.0, anchor=anchor)
    assert glyph is not None
    near = _run_below(glyph, 1.0)
    far = _run_below(glyph, 6.0)
    ctx = _native_ctx(profiles)
    plain = _native_ctx(profiles, placement="")

    def ruler(edges, own_edges, context=ctx):
        router = SimpleNamespace(edges=list(edges), own_edges=list(own_edges))
        return drawcompiler._flag_wire_ruler(context, "GND", profile, router)

    # the same numbers the gate reports, one unit inside and one over the band
    assert readability._flag_body_offence("GND", anchor, near, glyph) is not None
    assert readability._flag_body_offence("GND", anchor, far, glyph) is None
    assert ruler([near], [])(anchor, 0.0) is False
    assert ruler([far], [])(anchor, 0.0) is True
    # a same-net trunk is the case v45 died on: not a lead, not exempt
    assert ruler([], [near])(anchor, 0.0) is False
    # the flag's own lead leaves the anchor away from the glyph: exempt, as the gate
    lead = [anchor, (anchor[0], glyph[3] + 40.0)]
    assert ruler([], [lead])(anchor, 0.0) is True
    # a plain spec keeps the old answer: nothing about its drawing is measured
    assert ruler([near], [])(anchor, 0.0) is False
    assert ruler([near], [], plain)(anchor, 0.0) is True


V45 = Path(__file__).resolve().parents[1] / ".tmp_fix/v45.presentation.json"


def _v45_page(profiles):
    """053W's own input, compiled with the native text model (v45).

    The v45 document lives under `.tmp_fix/` (ignored, like every probe input);
    a checkout that does not carry it skips this pair rather than pretending the
    scene was measured. The circuit and the symbol library are the repo's.
    """
    from boardwise.core.circuitspec import CircuitSpec
    from boardwise.core.presentationspec import PresentationSpec
    from boardwise.engines import pagecompiler as pager

    root = Path(__file__).resolve().parents[1]
    circuit = CircuitSpec.load(root / "blocklib/specs/ch343_uart_534a.circuit.json")
    presentation = PresentationSpec.load(V45)
    return pager.compile_page(
        circuit, presentation, profiles,
        pager.PageCompileBudget(page_box=(0.0, 0.0, 1170.0, 825.0)),
    )


@pytest.mark.skipif(not V45.exists(), reason="053W's v45 input is a local probe file")
def test_the_v45_page_keeps_every_flag_clear(profiles):
    """053W续二: the usb_c R1.2 ground seat v45 could not take is now legal.

    Before this batch the same input built 0 candidates — `_flag_room` seated the
    ground where the gate then refused it at 1 unit, and no variant survived. A
    page that comes back must keep every flag a full clearance from every run
    (its own lead the one exemption), which is what the gate says here.
    """
    result = _v45_page(profiles)
    assert result.failures == [], [f.detail[:400] for f in result.failures]
    assert result.pages, "the v45 page lost every candidate again"
    profile_map = dict(profiles)
    for page in result.pages:
        assert readability._check_flag_body_on_wire(page.plan, profile_map) == []


@pytest.mark.skipif(not V45.exists(), reason="053W's v45 input is a local probe file")
def test_the_ladder_asks_the_gate_ruler(profiles, monkeypatch):
    """`fits` consults the ruler — the gate's function, not a copy of it."""
    calls = []
    original = drawcompiler._flag_wire_ruler

    def counting(*args, **kwargs):
        clear = original(*args, **kwargs)

        def clear_logged(anchor, rotation):
            calls.append((anchor, rotation))
            return clear(anchor, rotation)

        return clear_logged

    monkeypatch.setattr(drawcompiler, "_flag_wire_ruler", counting)
    assert _v45_page(profiles).pages
    assert calls, "the native ladder never asked the gate's ruler"
