"""543H-1: a shunt's seat follows the **page** side its own pad leaves on.

The measured defect (`evidence/543g_skill_trial/`): with the USB-C module's
connector drawn mirrored, both CC pull-downs were seated *behind* their own pads
(R1 at x=135, R2 at x=85 against pads at x=225), so `CC1`/`CC2` had to walk
around the 51×131 connector body — 3 and 4 elbows, one branch over the part and
the other under it.

The cause is one frame, not one role. The `ic-periphery` binder states a hanging
part's side from the core's **SymbolProfile** pin direction (symbol frame) and
turns that statement into a page side only when the group's cross-module signals
tell it which mirror the drawing takes. Here both D+ and D− are **mirrored pin
pairs**, so that set is empty, no flip is read, and `left-of(R1, USB1)` is
emitted although every pose of this symbol puts A5/B5 on the page's right. The
compiler then put the branch on the stated side, and the wire doubled back
across the owner's own body.

543H reads such a relation in the page frame (:func:`drawcompiler.
_order_across_its_pad`): when the owner's pad on the shared net sits on the far
side of the owner's origin from the side the relation asks the branch for, the
relation is read as its twin. The seat (`_order_direction`) and both graders
(`_relation_violations`, shared by the placement stage and `check_grammar`) get
that one reading, so they cannot disagree.

What this batch does **not** fix, measured and left as evidence: the two branch
lanes are still indexed per (owner, direction), so the paired shunts are not yet
one row apart (R1 x=375, R2 x=260 on the same page), and `CC1` still takes
elbows because the VBUS pair occupies the corridor. That is the H1 follow-up
("成对支路对齐") and is not claimed here.
"""

from __future__ import annotations

import pathlib

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.engines import drawapply
from boardwise.engines import drawcompiler as dc
from boardwise.engines import pagecompiler as pc
from boardwise.engines.grammar.base import LEFT_OF, RIGHT_OF

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPECS = ROOT / "blocklib" / "specs"
CIRCUIT = SPECS / "ch343_uart_534a.circuit.json"
LIBRARY = SPECS / "ch343_uart_v4.library.json"


def _library():
    return drawapply.load_library(LIBRARY)


def _page_payload() -> dict:
    """`evidence/543g_skill_trial/spec_v1.json`, restated so the test carries it."""
    return {
        "grammarRef": "ic-periphery",
        "textPlacement": "native-attr",
        "sidePreferences": {
            "input": "left", "output": "right", "load": "left",
            "source": "left", "power": "top", "gnd": "bottom",
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
                "role": "USB-C receptacle, VBUS bulk/decoupling and CC sink "
                        "pull-downs",
                "core": "USB1",
                "presentation": {"sidePreferences": {"load": "right"}},
            },
            {
                "id": "ch343", "parts": ["U1", "C3", "C4"],
                "role": "CH343 USB-UART bridge with V3 and VCC decoupling",
                "core": "U1",
                "presentation": {"sidePreferences": {"load": "left"}},
            },
            {
                "id": "hdr", "parts": ["H1"], "role": "2x5 UART header",
                "core": "H1",
                "presentation": {"sidePreferences": {
                    "input": "left", "output": "left"}},
            },
            {
                "id": "led", "parts": ["D1", "R3"], "role": "VBUS presence "
                "indicator", "grammarRef": "voltage-divider",
                "attach": {"to": "usb_c", "side": "bottom", "gap": 10},
            },
        ],
        "labelPolicy": {
            "local": "wire", "crossModule": "label", "highFanout": "label",
            "stub": "straight", "stubMin": 40, "rowModel": "centered",
        },
        "directWiringObligations": [{"nets": ["LED_A"]}],
        "localLabelObligations": [{"nets": ["D+", "D-"]}],
        "moduleOrder": ["usb_c", "ch343", "hdr", "led"],
        "flagLeadLimit": 120,
        "partTexts": {"USB1": "left", "U1": "above", "H1": "above",
                      "C3": "right", "C4": "right"},
        "gndClustering": {"radius": 100},
        "serviceLayout": {"pinGap": 30},
    }


@pytest.fixture(scope="module")
def page():
    result = pc.compile_page(
        CircuitSpec.load(CIRCUIT),
        PresentationSpec.from_dict(_page_payload()),
        _library(),
        pc.PageCompileBudget(page_box=(0.0, 0.0, 1170.0, 825.0)),
    )
    assert result.pages, result.render_failures()
    return result.pages[0]


def _part(plan, part_id):
    found = plan.part(part_id)
    assert found is not None, f"{part_id} not placed"
    return found


def _pin_point(plan, token):
    part_id, _, name = token.partition(".")
    part = _part(plan, part_id)
    pin = dc._pin_of_token(_library()[part.symbol_ref], name)
    assert pin is not None, f"{token} is not in {part.symbol_ref}"
    dx, dy = dc._posed_tip(pin, dc.SymbolPose(part.rotation, part.mirror))
    return (part.x + dx, part.y + dy)


_SYMBOL_OF = {"USB1": "TYPE-C-31-M-12-C165948", "U1": "CH343G-C2844153"}


def _pin_tips(plan, part_id):
    """Every pin tip of a placed part, relative to its own origin (543K)."""
    part = _part(plan, part_id)
    profile = _library()[part.symbol_ref]
    pose = dc.SymbolPose(part.rotation, part.mirror)
    return {
        pin.number: dc._posed_tip(pin, pose) for pin in profile.pins
    }


def _frame_escape(part_id, token):
    """The pad's escape in the **symbol's** frame (no pose), for the ruler."""
    profile = _library()[_SYMBOL_OF[part_id]]
    return dc._pin_escape(profile, token, dc.SymbolPose(0.0, False))


def _only_one_key(**drop) -> PresentationSpec:
    payload = _page_payload()
    for key in drop:
        payload.pop(key, None)
    return PresentationSpec.from_dict(payload)


def _compile_payload(presentation):
    return pc.compile_page(
        CircuitSpec.load(CIRCUIT), presentation, _library(),
        pc.PageCompileBudget(page_box=(0.0, 0.0, 1170.0, 825.0)),
    )


def test_the_cc_pair_is_one_column_with_one_straight_run_each(page):
    """543H-1b + 543K: R1/R2 share x and pose, each **horizontal**, one leg each.

    The pair hangs off two pads one pin pitch apart, so "aligned" means: same
    column, same pose, and the y pitch equal to the pads' own pitch. 543K adds
    the pose: the pads leave sideways, so the pair is drawn as two horizontal
    parts whose shared pin is the near end — the body continues *away* from the
    connector instead of dropping into a vertical symbol, which is what the
    543C shunts one island over already did. Each run stays a single horizontal
    segment from its USB pad to its own resistor pad — no elbow, and no detour
    over or under the connector.
    """
    plan = page.plan
    r1, r2 = _part(plan, "R1"), _part(plan, "R2")
    assert r1.x == r2.x, f"the pair is not one column: R1 x={r1.x:g}, R2 x={r2.x:g}"
    assert (r1.rotation, r1.mirror) == (r2.rotation, r2.mirror), (
        "the pair is not drawn in one pose: "
        f"{r1.rotation}/{r1.mirror} against {r2.rotation}/{r2.mirror}"
    )
    a5 = _pin_point(plan, "USB1.A5")
    b5 = _pin_point(plan, "USB1.B5")
    assert abs(abs(r2.y - r1.y) - abs(b5[1] - a5[1])) < 1e-9, (
        "the pair does not keep its pads' pitch: "
        f"resistors {r1.y:g}/{r2.y:g}, pads {a5[1]:g}/{b5[1]:g}"
    )
    for part_id in ("R1", "R2"):
        tips = _pin_tips(plan, part_id)
        assert abs(tips["1"][1]) < 1e-9 and abs(tips["2"][1]) < 1e-9, (
            f"{part_id} is not drawn horizontal: its pins sit at {tips} "
            "from its own origin"
        )
        assert tips["1"][0] < tips["2"][0], (
            f"{part_id}'s shared pin must be the end facing its pad: {tips}"
        )
    for net, pad, branch in (
        ("CC1", a5, _pin_point(plan, "R1.1")),
        ("CC2", b5, _pin_point(plan, "R2.1")),
    ):
        runs = [item for item in plan.segments if item.net == net]
        assert len(runs) == 1, f"{net} is drawn as {len(runs)} runs"
        assert len(runs[0].points) == 2, (
            f"{net} has {len(runs[0].points) - 2} elbow(s): {runs[0].points}"
        )
        start, end = runs[0].points
        assert abs(start[1] - end[1]) < 1e-9, f"{net} is not one straight row"
        assert {tuple(start), tuple(end)} == {tuple(pad), tuple(branch)}, (
            f"{net} does not run from its USB pad {pad} to its own pad {branch}"
        )


def test_no_cc_run_touches_a_part_it_does_not_serve(page):
    """The two runs stay clear of every other part on the row they cross."""
    plan = page.plan
    for net in ("CC1", "CC2"):
        for run in [item for item in plan.segments if item.net == net]:
            for (x0, y0), (x1, y1) in zip(run.points, run.points[1:]):
                for part in plan.parts:
                    if part.part_id in ("USB1", "R1", "R2"):
                        continue
                    box = _part_box(plan, part.part_id)
                    if abs(y0 - y1) < 1e-9:
                        hits = (
                            box[0] - 1e-9 < max(x0, x1) and min(x0, x1) < box[2] + 1e-9
                            and box[1] - 1e-9 < y0 < box[3] + 1e-9
                        )
                    else:
                        hits = (
                            box[1] - 1e-9 < max(y0, y1) and min(y0, y1) < box[3] + 1e-9
                            and box[0] - 1e-9 < x0 < box[2] + 1e-9
                        )
                    assert not hits, (
                        f"{net} {run.points} runs into {part.part_id} {box}"
                    )


def test_the_mirrored_connector_keeps_the_pair_too():
    """Both connector poses the island can take draw the pair the same way.

    543H-5's contrast this test was written for — "the column does not depend on
    which mirror the page picks" — is measured here where the poses are actually
    enumerated: the **island** compile keeps every legal candidate, so both
    connector families it accepts are read as real plans (part poses, pin tips,
    drawn `CC1`/`CC2` runs), not as a set of directions. The page ranking may
    keep only one of them (the horizontal pair needs the corridor), which is a
    page-level deduction and not this statement.
    """
    module = _usb_compile()
    seen = set()
    for plan in module.candidates:
        usb = _part(plan, "USB1")
        seen.add((usb.rotation, usb.mirror))
        r1, r2 = _part(plan, "R1"), _part(plan, "R2")
        assert r1.x == r2.x, (
            f"USB1 {usb.rotation}/{usb.mirror}: R1 x={r1.x:g}, R2 x={r2.x:g}"
        )
        assert (r1.rotation, r1.mirror) == (r2.rotation, r2.mirror), (
            f"USB1 {usb.rotation}/{usb.mirror}: the pair has two poses"
        )
        for part_id in ("R1", "R2"):
            tips = _pin_tips(plan, part_id)
            assert abs(tips["1"][1]) < 1e-9 and abs(tips["2"][1]) < 1e-9, (
                f"USB1 {usb.rotation}/{usb.mirror}: {part_id} is not horizontal"
            )
            assert tips["1"][0] < tips["2"][0], (
                f"USB1 {usb.rotation}/{usb.mirror}: {part_id}'s shared pin "
                f"faces away from its pad: {tips}"
            )
        for net, token in (("CC1", "USB1.A5"), ("CC2", "USB1.B5")):
            runs = [s for s in plan.segments if s.net == net]
            assert len(runs) == 1 and len(runs[0].points) == 2, (
                f"USB1 {usb.rotation}/{usb.mirror}: {net} is not one straight run"
            )
            start, end = runs[0].points
            assert abs(start[1] - end[1]) < 1e-9, (
                f"USB1 {usb.rotation}/{usb.mirror}: {net} is not one row"
            )
            assert tuple(start) == tuple(_pin_point(plan, token)), (
                f"USB1 {usb.rotation}/{usb.mirror}: {net} does not start at the pad"
            )
    assert len(seen) > 1, f"only one connector pose was drawn: {seen}"


def _usb_compile():
    """The usb_c island compiled on its own: every legal candidate, not the page.

    The page's own payload is used, not the reduced `_usb_module()` view: that
    one carries `partTexts = {USB1: left}` only and its island keeps a single
    connector pose, so it cannot answer "does the other mirror draw the pair the
    same way".
    """
    import test_543h3b_stated_text_lane as t3b

    presentation = PresentationSpec.from_dict(t3b.PAYLOAD)
    circuit, local = pc._module_view(
        CircuitSpec.load(CIRCUIT), presentation, presentation.module("usb_c")
    )
    return dc.compile(circuit, local, _library(), dc.CompileBudget())


def _r1_seat(drop=()):
    """Where the ladder puts R1 under one of the four key combinations."""
    payload = _page_payload()
    for key in drop:
        payload.pop(key, None)
    presentation = PresentationSpec.from_dict(payload)
    circuit = CircuitSpec.load(CIRCUIT)
    local_circuit, local_presentation = pc._module_view(
        circuit, presentation, presentation.module("usb_c")
    )
    binding = dc.bind_grammar(local_circuit, local_presentation, _library())
    ctx = dc._prepare(
        local_circuit, local_presentation, binding, _library(),
        dc.CompileBudget(),
    ).context
    poses: dict = {}
    origins: dict = {}
    for variant in dc._variants(ctx):
        layout = dc._chain_and_shelf_layout(ctx, variant)
        if isinstance(layout, dc.GrammarFailure):
            continue
        origins, poses, _ = layout
        break
    return dc._pair_bands(ctx), origins["R1"], origins["USB1"]


def test_one_key_alone_keeps_the_stated_seat():
    """543H-5: the page-frame reading needs **both** keys, seat included.

    With both keys R1 stands on the side its pad leaves on; with only one of the
    two it stands where the stated ``left-of`` puts it — the old ladder, measured
    on the module's own origins.
    """
    enabled, r1, usb1 = _r1_seat()
    assert enabled is True
    assert r1[0] > usb1[0], f"with both keys the pad's escape must win: {r1}"
    for drop in (("serviceLayout",), ("textPlacement",)):
        enabled, r1, usb1 = _r1_seat(drop)
        assert enabled is False
        assert r1[0] < usb1[0], (
            f"one key ({drop}) moved the seat off the stated side: {r1}"
        )


def _part_box(plan, part_id):
    part = _part(plan, part_id)
    profile = _library()[part.symbol_ref]
    return dc._part_box(
        profile, dc.SymbolPose(int(part.rotation), part.mirror), (part.x, part.y)
    )


def _pin_escape(plan, part_id, token):
    part = _part(plan, part_id)
    return dc._pin_escape(
        _library()[part.symbol_ref], token,
        dc.SymbolPose(int(part.rotation), part.mirror),
    )


def _body_box(plan, part_id):
    part = _part(plan, part_id)
    profile = _library()[part.symbol_ref]
    return dc._part_box(
        profile, dc.SymbolPose(part.rotation, part.mirror), (part.x, part.y)
    )


# ----------------------------------------------------------------- the defect


def test_both_cc_pull_downs_sit_on_the_side_their_pads_leave_on(page):
    """R1/R2 are drawn beside A5/B5, not behind them through the connector."""
    plan = page.plan
    for token, branch in (("USB1.A5", "R1"), ("USB1.B5", "R2")):
        pad = _pin_point(plan, token)
        seat = _pin_point(plan, f"{branch}.1")
        assert seat[0] > pad[0], (
            f"{branch} sits at x={seat[0]:g}, behind its own pad {token} at "
            f"x={pad[0]:g}: the seat has to be on the side the pad leaves on"
        )


def test_neither_cc_run_crosses_the_connector_body(page):
    plan = page.plan
    box = _body_box(plan, "USB1")
    assert box[2] - box[0] > 40.0, box
    for net in ("CC1", "CC2"):
        runs = [item for item in plan.segments if item.net == net]
        assert runs, f"{net} is not drawn"
        for run in runs:
            for (x0, y0), (x1, y1) in zip(run.points, run.points[1:]):
                if abs(y0 - y1) < 1e-9:
                    across = min(x0, x1) < box[2] - 1e-9 and max(x0, x1) > box[0] + 1e-9
                    depth = box[1] + 1e-9 < y0 < box[3] - 1e-9
                elif abs(x0 - x1) < 1e-9:
                    across = box[0] + 1e-9 < x0 < box[2] - 1e-9
                    depth = min(y0, y1) < box[3] - 1e-9 and max(y0, y1) > box[1] + 1e-9
                else:
                    pytest.fail(f"{net} has a diagonal run: {run.points}")
                assert not (across and depth), (
                    f"{net} runs through the connector body {box}: {run.points}"
                )


# --------------------------------------------------------- the frame reading


def test_the_symbol_frame_relation_is_read_as_its_twin(page):
    """`left-of(R1, USB1)` was written in the symbol frame; the page turns it."""
    circuit = CircuitSpec.load(CIRCUIT)
    presentation = PresentationSpec.from_dict(_page_payload())
    module = presentation.module("usb_c")
    local_circuit, local_presentation = pc._module_view(
        circuit, presentation, module
    )
    binding = dc.bind_grammar(local_circuit, local_presentation, _library())
    item = next(
        entry for entry in binding.constraints
        if entry.kind == LEFT_OF and entry.subject == "R1"
    )
    plan = page.plan
    escape_of = lambda part_id, token: _pin_escape(plan, part_id, token)  # noqa: E731

    assert dc._ORDER_TWIN[item.kind] == RIGHT_OF
    assert dc._order_across_its_pad(
        local_circuit, item, escape_of=escape_of, frame_of=_frame_escape,
        branches=dc._branch_parts(binding),
    ), "A5 leaves the connector's body rightward on this page"
    seat = _part(plan, "R1").x
    assert seat > _part(plan, "USB1").x, (
        "read in the page frame the branch stands on the side its pad leaves on"
    )


def test_a_relation_that_agrees_with_the_pad_is_left_alone():
    """A pad on the side the relation asks is not a contradiction."""
    circuit, presentation = _usb_module()
    binding = dc.bind_grammar(circuit, presentation, _library())
    item = next(
        entry for entry in binding.constraints
        if entry.kind == LEFT_OF and entry.subject == "R1"
    )
    # The un-mirrored reading: A5 leaves the body leftward, which is the side
    # `left-of(R1, USB1)` asks for, so nothing is turned.
    profile = _library()["TYPE-C-31-M-12-C165948"]
    unmirrored = dc._pin_escape(profile, "A5", dc.SymbolPose(0.0, False))
    assert unmirrored == (-1.0, 0.0)
    assert not dc._order_across_its_pad(
        circuit, item, escape_of=lambda _part_id, _token: unmirrored,
        frame_of=lambda _part_id, _token: unmirrored,
        branches=dc._branch_parts(binding),
    )


def test_a_pad_the_profile_cannot_orient_says_nothing():
    """No escape, no statement: the stated kind is kept (052 sec.4)."""
    circuit, presentation = _usb_module()
    binding = dc.bind_grammar(circuit, presentation, _library())
    item = next(
        entry for entry in binding.constraints
        if entry.kind == LEFT_OF and entry.subject == "R1"
    )
    assert not dc._order_across_its_pad(
        circuit, item, escape_of=lambda *_: None, frame_of=lambda *_: (1.0, 0.0),
        branches=dc._branch_parts(binding),
    )


def test_a_non_branch_end_is_not_read_in_another_frame():
    """Only a part the grammar binds as a branch has a pad to hang off."""
    circuit, presentation = _usb_module()
    binding = dc.bind_grammar(circuit, presentation, _library())
    item = next(
        entry for entry in binding.constraints
        if entry.kind == LEFT_OF and entry.subject == "R1"
    )
    mirrored = dc._pin_escape(
        _library()["TYPE-C-31-M-12-C165948"], "A5", dc.SymbolPose(0.0, True)
    )
    assert not dc._order_across_its_pad(
        circuit, item, escape_of=lambda _part_id, _token: mirrored,
        frame_of=lambda _part_id, _token: (-1.0, 0.0),
        branches=frozenset(),
    )


# --------------------------------------------------------- the default input


def test_a_group_without_the_mirrored_pair_keeps_its_stated_relation():
    """The 543B sample: a core drawn as the symbol has it keeps the old seat."""
    import test_543b_service_layout as t543b

    spec = t543b._spec()
    presentation = PresentationSpec.from_dict(t543b._payload(30))
    binding = dc.bind_grammar(spec, presentation, t543b.e098.library())
    result = t543b._compile(spec, presentation)
    assert result.ok, result.render_failures()
    plan = result.candidates[0]
    book = t543b.e098.library()
    placed = {item.part_id: item for item in plan.parts}
    escape_of = lambda part_id, token: dc._pin_escape(  # noqa: E731
        book[placed[part_id].symbol_ref], token,
        dc.SymbolPose(int(placed[part_id].rotation), placed[part_id].mirror),
    )
    turned = [
        entry for entry in binding.constraints
        if entry.kind in dc._ORDER_TWIN
        and dc._order_across_its_pad(
            spec, entry, escape_of=escape_of, frame_of=_frame_escape,
            branches=dc._branch_parts(binding),
        )
    ]
    assert turned == [], turned


# -------------------------------------------------------------------- helpers


def _usb_module():
    payload = _page_payload()
    payload["modules"] = [payload["modules"][0]]
    payload["flow"] = []
    payload["moduleOrder"] = ["usb_c"]
    payload["partTexts"] = {"USB1": "left"}
    circuit = CircuitSpec.load(CIRCUIT)
    presentation = PresentationSpec.from_dict(payload)
    return pc._module_view(circuit, presentation, presentation.module("usb_c"))


def _usb_context():
    """The usb_c island prepared exactly as the page prepares it (543K)."""
    circuit, presentation = _usb_module()
    binding = dc.bind_grammar(circuit, presentation, _library())
    return dc._prepare(
        circuit, presentation, binding, _library(), dc.CompileBudget(),
    ).context
