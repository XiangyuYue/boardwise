"""543K: an opt-in **signal** pair is drawn as two horizontal parts.

Measured on the Type-C sink pair (岳's review, P37): the CC pull-downs were the
only parts in the USB island standing upright while the CH343 shunts one island
over lay on the run that serves them. Both were correct under their own rules —
the CH343 pair is a *uniquely served* shunt and 543C hangs its body on the
service axis, while the CC pair hangs off two pads of a connector and took the
pose its **return** net states (ground below, so vertical). The page then read
as two horizontal runs each ending at the near pad of an upright part whose
other pad dropped away.

The rule pinned here (`drawcompiler._signal_pair_body_direction`) reads
structure, not names: with both opt-in keys stated (``native-attr`` +
``serviceLayout``, the 543H-5 reading), a **two-terminal** branch whose shared
net is a **signal**, which has a sibling on the same owner/role/symbol and a
different pad, and whose owner's accepted poses all put the shared pad on one
**horizontal** side, is drawn with its body along that side. Rails and returns
keep their supply/return pose, a served shunt keeps its service axis, and a page
that states one key or neither keeps every pose it had.
"""

from __future__ import annotations

import copy
import pathlib

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
PAGE_BOX = (0.0, 0.0, 1170.0, 825.0)


def _library():
    return drawapply.load_library(LIBRARY)


def _payload(*drop) -> dict:
    payload = copy.deepcopy(t3b.PAYLOAD)
    for key in drop:
        payload.pop(key, None)
    return payload


def _compile(payload):
    return pc.compile_page(
        CircuitSpec.load(CIRCUIT), PresentationSpec.from_dict(payload),
        _library(), pc.PageCompileBudget(page_box=PAGE_BOX),
    )


def _module_context(payload):
    """The `usb_c` island's own slots, prepared exactly as the page prepares it."""
    presentation = PresentationSpec.from_dict(payload)
    circuit = CircuitSpec.load(CIRCUIT)
    local_circuit, local_presentation = pc._module_view(
        circuit, presentation, presentation.module("usb_c")
    )
    binding = dc.bind_grammar(local_circuit, local_presentation, _library())
    return dc._prepare(
        local_circuit, local_presentation, binding, _library(),
        dc.CompileBudget(),
    ).context


def _part(plan, part_id):
    found = plan.part(part_id)
    assert found is not None, f"{part_id} not placed"
    return found


def _tips(plan, part_id):
    """The placed part's pin tips, relative to its own origin."""
    part = _part(plan, part_id)
    profile = _library()[part.symbol_ref]
    pose = dc.SymbolPose(part.rotation, part.mirror)
    return {pin.number: dc._posed_tip(pin, pose) for pin in profile.pins}


def _horizontal(plan, part_id) -> bool:
    tips = _tips(plan, part_id)
    return all(abs(tip[1]) < 1e-9 for tip in tips.values())


def _vertical(plan, part_id) -> bool:
    tips = _tips(plan, part_id)
    return all(abs(tip[0]) < 1e-9 for tip in tips.values())


def test_the_opted_in_signal_pair_is_horizontal_and_its_pads_pitch_is_kept():
    result = _compile(_payload())
    assert result.ok, result.render_failures()
    plan = result.pages[0].plan
    r1, r2 = _part(plan, "R1"), _part(plan, "R2")
    for part_id in ("R1", "R2"):
        assert _horizontal(plan, part_id), (
            f"{part_id} is not horizontal: pins at {_tips(plan, part_id)}"
        )
        tips = _tips(plan, part_id)
        assert tips["1"][0] < tips["2"][0], (
            f"{part_id}'s shared pin is not the end facing its pad: {tips}"
        )
    assert (r1.rotation, r1.mirror) == (r2.rotation, r2.mirror), (
        "the pair is not drawn in one pose: "
        f"{r1.rotation}/{r1.mirror} against {r2.rotation}/{r2.mirror}"
    )
    assert r1.x == r2.x, f"the pair is not one column: {r1.x:g} against {r2.x:g}"
    a5 = _part(plan, "USB1")
    assert abs(abs(r2.y - r1.y) - 60.0) < 1e-9, (
        "the pair does not keep its pads' 60-unit pitch: "
        f"R1 y={r1.y:g}, R2 y={r2.y:g}, USB1 origin y={a5.y:g}"
    )


def test_the_bulk_capacitors_keep_their_vertical_pose():
    """A rail's shunt is a supply branch: it keeps the pose it always had."""
    result = _compile(_payload())
    assert result.ok, result.render_failures()
    plan = result.pages[0].plan
    for part_id in ("C1", "C2"):
        assert _vertical(plan, part_id), (
            f"{part_id} left its vertical pose: pins at {_tips(plan, part_id)}"
        )


def test_the_served_shunts_keep_the_axis_their_service_takes():
    """C3/C4 are 543C shunts — this batch may not turn them either way."""
    result = _compile(_payload())
    assert result.ok, result.render_failures()
    plan = result.pages[0].plan
    for part_id in ("C3", "C4"):
        assert _horizontal(plan, part_id), (
            f"{part_id} left the service axis: pins at {_tips(plan, part_id)}"
        )


def test_the_rule_reads_structure_not_part_names():
    """It answers for the signal pair only, and only under both keys."""
    ctx = _module_context(_payload())
    for part_id in ("R1", "R2"):
        assert dc._signal_pair_body_direction(ctx, ctx.slots[part_id]) == (1.0, 0.0)
    # A rail's shunt (C1/C2 are +5V) and a served shunt (C3/C4 live in the
    # CH343 module) are not signal pairs, so the rule says nothing to them.
    for part_id in ("C1", "C2"):
        assert dc._signal_pair_body_direction(ctx, ctx.slots[part_id]) is None
        assert ctx.body_dirs[part_id] == (0.0, -1.0), ctx.body_dirs[part_id]


def test_one_key_alone_keeps_the_old_pose():
    """543H-5's gate: without both opt-in keys the pair stays upright.

    543K hangs off the same predicate as the rest of the explicit reading, and
    its bay re-order lives inside that branch too, so a document stating one key
    runs exactly the code path it ran before this batch — the pair prepares
    vertical here, and nothing else in the placement was touched.
    """
    assert dc._pair_bands(_module_context(_payload())) is True
    for drop in (("serviceLayout",), ("textPlacement",)):
        ctx = _module_context(_payload(*drop))
        assert dc._pair_bands(ctx) is False, drop
        for part_id in ("R1", "R2"):
            assert dc._signal_pair_body_direction(ctx, ctx.slots[part_id]) is None, drop
            assert ctx.body_dirs[part_id] == (0.0, -1.0), (drop, ctx.body_dirs[part_id])


def _row_sides(plan) -> dict[str, set[str]]:
    """Which side of its own body each branch prints its rows on."""
    sides: dict[str, set[str]] = {}
    for part_id in ("R1", "R2"):
        part = _part(plan, part_id)
        profile = _library()[part.symbol_ref]
        box = dc._part_box(
            profile, dc.SymbolPose(part.rotation, part.mirror), (part.x, part.y),
        )
        rows = [text for text in plan.texts if text.part_id == part_id]
        assert rows, f"{part_id} prints no row"
        for text in rows:
            if text.bbox[2] <= box[0]:
                sides.setdefault(part_id, set()).add("left")
            elif text.bbox[0] >= box[2]:
                sides.setdefault(part_id, set()).add("right")
            else:
                sides.setdefault(part_id, set()).add("inline")
            for other in plan.parts:
                if other.part_id == part_id:
                    continue
                other_box = dc._part_box(
                    _library()[other.symbol_ref],
                    dc.SymbolPose(other.rotation, other.mirror),
                    (other.x, other.y),
                )
                assert not dc._overlaps(text.bbox, other_box), (
                    f"{part_id} {text.kind} runs into {other.part_id}: "
                    f"{text.bbox} against {other_box}"
                )
    return sides


def test_the_pair_reads_its_rows_from_one_side():
    """The pair's designator and value print on the same side of both parts.

    543K: the pose follows the run that serves the pair, and the rows follow the
    pose. A pair whose rows read from opposite sides is exactly the picture this
    batch removed — one member's text has to cross the corridor its own run
    occupies — so the rows are seated together by
    `drawcompiler._paired_text_seats` and this pins it on the page.
    """
    result = _compile(_payload())
    assert result.ok, result.render_failures()
    sides = _row_sides(result.pages[0].plan)
    assert sides["R1"] == sides["R2"], sides
    assert sides["R1"] in ({"left"}, {"right"}), sides


def test_the_pair_reads_from_one_side_in_both_connector_poses():
    """The same statement on every legal island candidate, both poses included."""
    circuit, presentation = pc._module_view(
        CircuitSpec.load(CIRCUIT), PresentationSpec.from_dict(_payload()),
        PresentationSpec.from_dict(_payload()).module("usb_c"),
    )
    module = dc.compile(circuit, presentation, _library(), dc.CompileBudget())
    assert module.ok, module.render_failures()
    poses = set()
    for plan in module.candidates:
        usb = _part(plan, "USB1")
        poses.add((usb.rotation, usb.mirror))
        sides = _row_sides(plan)
        assert sides["R1"] == sides["R2"], (usb.rotation, usb.mirror, sides)
    assert len(poses) > 1, poses
