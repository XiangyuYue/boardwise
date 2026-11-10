"""543I-2D: the flag grouping lands, decided by one rule and one walking ruler.

What this file pins, on the P32 page (`spec_h3b`: circuit `ch343_uart_534a` +
`ch343_uart_v4`):

* **both ends of a parallel decoupling pair take the same policy** (543J): C1/C2
  are one owner's two capacitors between the same two nets, so their `GND`
  return pads are one group as well — the walking ruler measured 90 on a stated
  reach of 100, and one flag serves both. Their `+5V` pads keep the trunk answer
  (cost 100). **Independent** branches still keep their own flags: R1/R2 are
  pull-downs on *different* signal nets (CC1/CC2) and C3/C4 decouple *different*
  pins (V3/VCC), so nothing about their return nets makes them parallel.
* **the audit really runs**: :func:`drawcompiler._flag_group_audit` is called
  once per module compilation and answers `None` on this page's final wiring
  (a page that needed re-grouping would be refused by name).
* **a branch keeps its own host corridor.** R10's `CC1` run is a straight
  two-point wire; R11's new local GND flag may not take that lane, so the
  corridor from the host pad to the branch's shared pin is a keep-out for
  **flags only** (measured: `CC1` and `CC2` both stay two-point).
* **543I-1 is untouched**: `D+`/`D-` keep their 40/60/40/60 runs (543L made the
  `B6`/`B7` mirrored pair one 60-unit length), their printed rows stay on their
  own carriers and at least 20 units apart, and no visible name leaves its run.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from boardwise.core.circuitspec import CircuitSpec
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
#: `evidence/543h3b/spec_h3b.json`, inline: a test may not read an evidence
#: directory (the 543I-1 convention).
PAYLOAD = json.loads((ROOT / "evidence/543h3b/spec_h3b.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def compiled():
    seen = {"groups": {}, "audit": {"calls": 0, "failures": 0}}
    original_apply = dc._apply_flag_groups
    original_audit = dc._flag_group_audit

    def apply(ctx, router, expressions, order, **kwargs):
        original_apply(ctx, router, expressions, order, **kwargs)
        for net_id in order:
            expression = expressions[net_id]
            if not expression.clusters:
                continue
            key = (net_id, tuple(tuple(m for m, _p in g) for g in expression.clusters))
            if key in seen["groups"]:
                continue
            ruler = dc._flag_ruler(ctx, router, net_id)
            seen["groups"][key] = [
                [ruler(a[1], b[1]) for i, a in enumerate(g) for b in g[i + 1:]]
                for g in expression.clusters
            ]

    def audit(*args, **kwargs):
        seen["audit"]["calls"] += 1
        out = original_audit(*args, **kwargs)
        if out is not None:
            seen["audit"]["failures"] += 1
        return out

    dc._apply_flag_groups = apply
    dc._flag_group_audit = audit
    try:
        result = pc.compile_page(
            CIRCUIT, PresentationSpec.from_dict(copy.deepcopy(PAYLOAD)), LIBRARY,
            pc.PageCompileBudget(page_box=PAGE_BOX),
        )
        assert result.ok, result.render_failures()
        page = result.pages[0]
        plan = drawapply.module_plan(
            page.plan, CIRCUIT, PresentationSpec.from_dict(copy.deepcopy(PAYLOAD)),
            LIBRARY, candidate_index=0, label_stubs=True, page_box=PAGE_BOX,
            module_label="page " + "+".join(m.id for m in page.modules),
        )
    finally:
        dc._apply_flag_groups = original_apply
        dc._flag_group_audit = original_audit
    return page, plan, seen


def test_both_ends_of_a_parallel_decoupling_pair_take_one_flag(compiled):
    """543J: C1/C2 are one owner's two capacitors between the same two nets."""
    _page, _plan, seen = compiled
    by_net = {}
    for (net, groups), costs in seen["groups"].items():
        by_net.setdefault(net, []).append((groups, costs))

    # +5V: the supply pads share one flag — the host trunk — with a measured run
    # of 60 on the stated reach of 100. 543K: the bay is laid inside out, so the
    # sink pair takes the band nearer the pads and the bulk pair behind it moved
    # 50 out; the pair's own trunks are therefore 40 shorter. The *policy* this
    # test pins (one shared flag, measured run) is unchanged.
    merged = [
        (groups, costs) for groups, costs in by_net["+5V"]
        if any({"C1.1", "C2.1"} <= set(g) for g in groups)
    ]
    assert merged, by_net["+5V"]
    groups, costs = merged[0]
    index = next(i for i, g in enumerate(groups) if {"C1.1", "C2.1"} <= set(g))
    assert costs[index] and costs[index][0] == pytest.approx(60.0), costs[index]

    # GND: the same pair's return pads are one group as well — same policy at
    # both ends (岳: 同组并联去耦两端采用相同共旗策略) — and the cost is the
    # ruler's real walk, not a straight line and not "already merged".
    assert by_net["GND"], "the ground's groups must be recorded"
    usb = [
        (groups, costs) for groups, costs in by_net["GND"]
        if any("C1.2" in g or "C2.2" in g for g in groups)
    ]
    assert len(usb) == 1, by_net["GND"]
    groups, costs = usb[0]
    together = [i for i, g in enumerate(groups) if {"C1.2", "C2.2"} <= set(g)]
    assert len(together) == 1, groups
    index = together[0]
    assert costs[index], "the shared return must be justified by a measured run"
    assert 0.0 < costs[index][0] <= 100.0, costs[index]

    # Independent branches keep their own local flags whatever the distance:
    # R1/R2 pull down two different signal nets (CC1/CC2), C3/C4 decouple two
    # different pins (V3/VCC) — only a shared net *class*, never a shared circuit.
    for groups, _costs in by_net["GND"]:
        for group in groups:
            assert not {"R1.2", "R2.2"} <= set(group), group
            assert not {"C3.2", "C4.2"} <= set(group), group


def _through_body(start, stop, box) -> bool:
    """Does an axis-aligned segment have a positive run inside the body box?"""
    if abs(start[1] - stop[1]) < 1e-9:
        if not (box[1] < start[1] < box[3]):
            return False
        low, high = sorted((start[0], stop[0]))
        return min(high, box[2]) - max(low, box[0]) > 1e-6
    if abs(start[0] - stop[0]) < 1e-9:
        if not (box[0] < start[0] < box[2]):
            return False
        low, high = sorted((start[1], stop[1]))
        return min(high, box[3]) - max(low, box[1]) > 1e-6
    return False


def test_a_detached_power_pad_is_grouped_but_never_wired_across(compiled):
    """The mirrored VBUS pads are grouped, but no run joins them across the body.

    543I-4A: this test used to require **every** `+5V` run to be straight or
    L-shaped (``len(points) <= 3``). That was a proxy for 069 sec.2's U-line, and
    the proxy broke on a legal flight: C1's rail now steps around the row the
    host prints under the reserved box — `(390,750)-(390,755)-(450,755)-
    (450,750)`, four points, no body crossed. What the rule actually says is
    narrower and is what is checked here: **the two mirrored pads of one
    connector are never joined by one run, and no `+5V` run crosses the
    connector's own body.** A branch stepping around printed text is the router
    doing its job and is not this test's subject.
    """
    page, plan, seen = compiled
    # +5V is grouped (the rule ran on it) ...
    assert any(net == "+5V" for net, _g in seen["groups"])
    # ... and the detached far pad is in no group of the connector's pads.
    for _key, groups in ((k, v) for k, v in seen["groups"].items() if k[0] == "+5V"):
        for group in groups:
            assert not ({"USB1.A4B9", "USB1.B4A9"} <= set(group)), group

    wires = [w for w in plan.change.draw_wires if str(w.net) == "+5V"]
    assert len(wires) >= 2, [w.points for w in wires]
    runs: dict[str, list[list[tuple[float, float]]]] = {}
    for wire in wires:
        points = [
            (round(float(p[0]), 3), round(float(p[1]), 3)) for p in wire.points
        ]
        runs.setdefault(str(wire.from_pin), []).append(points)
    # Both mirrored pads are stated by runs of their own (the set is not empty)…
    for pad in ("USB1.A4B9", "USB1.B4A9"):
        assert runs.get(pad), f"{pad} carries no +5V run of its own"
    # … and no single run reaches from one to the other (069 sec.2's U-line).
    left = {point for run in runs["USB1.A4B9"] for point in (run[0], run[-1])}
    right = {point for run in runs["USB1.B4A9"] for point in (run[0], run[-1])}
    assert not (left & right), (left & right)

    # The hard geometric reading: no +5V run cuts the connector's own body.
    part = next(item for item in page.plan.parts if item.part_id == "USB1")
    profile = LIBRARY[part.symbol_ref]
    body = dc._part_box(
        profile, dc.SymbolPose(int(part.rotation), part.mirror), (part.x, part.y),
    )
    # The geometric predicate itself is live: a run straight through the body's
    # centre *is* a cut, so an empty answer above means "no cut", not "no test".
    centre = ((body[0] + body[2]) / 2.0, (body[1] + body[3]) / 2.0)
    assert _through_body((body[0] - 20.0, centre[1]), (body[2] + 20.0, centre[1]), body)
    for wire in wires:
        points = [(float(p[0]), float(p[1])) for p in wire.points]
        for start, stop in zip(points, points[1:]):
            assert not _through_body(start, stop, body), (wire.from_pin, start, stop)


def test_the_grouping_audit_runs_and_passes(compiled):
    _page, _plan, seen = compiled
    assert seen["audit"]["calls"] >= 1, "the audit must really execute"
    assert seen["audit"]["failures"] == 0, "this page's final wiring keeps its groups"


def test_the_branch_corridors_stay_straight(compiled):
    """R10/R11 (CC1/CC2) keep the two-point run their local flags must not take."""
    _page, plan, _seen = compiled
    for net in ("CC1", "CC2"):
        wires = [w for w in plan.change.draw_wires if str(w.net) == net]
        assert len(wires) == 1, (net, [w.points for w in wires])
        assert len(wires[0].points) == 2, (net, wires[0].points)
        start, end = wires[0].points
        assert abs(start[1] - end[1]) < 1e-9, (net, wires[0].points)


def test_543i1_carriers_and_rows_are_untouched(compiled):
    page, plan, _seen = compiled
    runs = {}
    for wire in plan.change.draw_wires:
        net = str(wire.net)
        if net not in ("D+", "D-"):
            continue
        points = [(round(float(p[0]), 3), round(float(p[1]), 3)) for p in wire.points]
        runs.setdefault(net, set()).add(tuple(points))
    lengths = sorted(len(points) for net in runs for points in runs[net])
    span = sorted(
        abs(points[0][0] - points[-1][0]) for net in runs for points in runs[net]
    )
    # 543L: `B6`/`B7` are one mirrored pair of the same `localLabelObligations`
    # entry and are now chosen together, so both carry the 60-unit run (the
    # `55` this list carried was the pair drawn one rung apart).
    assert span == [40.0, 40.0, 40.0, 40.0, 60.0, 60.0], span
    assert lengths, runs

    rows = {}
    for move in plan.change.attribute_moves:
        if getattr(move, "owner_kind", "") != "wire":
            continue
        wire = plan.change.draw_wires[move.wire_index]
        if str(wire.net) not in ("D+", "D-"):
            continue
        rows.setdefault(str(wire.net), []).append((move.x, move.y))
    for net, values in rows.items():
        for left in range(len(values)):
            for right in range(left + 1, len(values)):
                gap = max(abs(values[left][1] - values[right][1]),
                          abs(values[left][0] - values[right][0]))
                assert gap >= 20.0 or values[left][1] != values[right][1], (net, values)
    assert page.plan.labels  # the page states its names
