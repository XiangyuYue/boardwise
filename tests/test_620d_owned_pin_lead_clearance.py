"""620D: a native seat's 10-unit clearance, split by where the conductor comes from.

617D dropped `_native_label_seat`'s distance to every other-net conductor from 10
to 5, and 534z caught it: the 10-unit contract is **not** the page's to relax for
an arbitrary wire. 620C restored 10 and stopped, with an exhaustive measurement:
on the CH343 page the `RXD` name can stand 20 units from its own pin only if the
lead of the *same part's* neighbouring V3 pin may come as close as 5.5 — 8 units
of text gap and 4.5 units of half a text row against a 10-unit pin pitch, both
constants the symbol owns. With 10 everywhere the nearest legal seat is 97 units
out (617D refuses >= 96, 617E refuses > 20). This batch keeps 10 for every wire
and states the one class that is not a wire: a run that terminates on a pin of
the label's **own** part, on that pin's own net.

What the tests hold, and how each can fail:

* the default call is unchanged: 534z's 5.5-unit foreign conductor is still
  skipped and a seat >= 10 is taken (a global 5 turns this red);
* a run that really ends on the label's part's pin, carrying that pin's net, may
  be read at `FLAG_BODY_CLEARANCE` — but touching it or crossing the stub is
  still a refusal, and a *different* part's pin lead at the same 5.5 is not
  widened (the ownership proof is part + profile + pin + net + termination, not
  a name or a `part_id`);
* a fabricated `part_id`, an unplaced part, or a missing profile yields no
  owned site, so convenience callers and unknown data stay at 10;
* the real 543d and 617E pages compile `ok` with 4 candidates each, every
  candidate puts `RXD` <= 20 units out on the pin's outward side, clear of C3
  and every drawn body, with every foreign run >= 10 and its own part's V3 lead
  >= 5; 58 pins / 17 nets still land and connect, and 617E's `moduleColumns: 3`
  reading (backflow 0) is unchanged.

The real-page numbers are read from the compiled page, not from the helper; the
connectivity sweep is 617E's own (copied deliberately: two rulers for one claim
would be two truths).
"""
from __future__ import annotations

import difflib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from boardwise.core.circuitspec import CircuitSpec  # noqa: E402
from boardwise.core.layoutplan import (  # noqa: E402
    LayoutLabel,
    LayoutPart,
    LayoutPlan,
    LayoutSegment,
    TEXT_MODE_NATIVE,
)
from boardwise.core.presentationspec import PresentationSpec  # noqa: E402
from boardwise.engines import drawapply, drawcompiler as dc  # noqa: E402
from boardwise.engines import pagecompiler as pc  # noqa: E402
from boardwise.engines import readability  # noqa: E402

SPECS = ROOT / "blocklib" / "specs"
CIRCUIT = SPECS / "ch343_uart_534a.circuit.json"
LIBRARY = SPECS / "ch343_uart_v4.library.json"
PAGE_BOX = (0.0, 0.0, 1170.0, 825.0)
PAGES = {
    "543d": ROOT / "evidence" / "543d" / "effective.presentation.json",
    "617e": ROOT / "evidence" / "617e" / "effective.presentation.json",
}
U1_REF = "CH343G-C2844153"
C3_REF = "C0603-100nF-C1590"
#: The 617d defect this batch must stay clear of, and 617E's stub bound.
PRE_FIX_STUB = 96.0
RXD_STUB = 20.0
TEXT_FLOOR = 2.0
#: 617C's landing outcome for the adjusted input (617E pins these).
CLASSES = {"wire-end": 35, "wire": 2, "nc": 3, "named": 18}

_CACHE: dict[str, tuple] = {}


def _compile(name: str):
    if name not in _CACHE:
        circuit = CircuitSpec.load(CIRCUIT)
        presentation = PresentationSpec.load(PAGES[name])
        library = drawapply.load_library(LIBRARY)
        budget = pc.PageCompileBudget(page_box=PAGE_BOX)
        result = pc.compile_page(circuit, presentation, library, budget)
        assert result.ok, result.render_failures()
        _CACHE[name] = (circuit, library, result)
    return _CACHE[name]


# ------------------------------------------------------------ 5.5-unit rulers


def _near_rxd(anchor=(640.0, 740.0)):
    """The 20-unit outward seat 617E requires, and the real page's U1 origin."""
    centre = (anchor[0] - (dc.text_width("RXD") / 2.0 + dc.TEXT_GAP), anchor[1])
    return anchor, dc.font_text_box("RXD", x=centre[0], y=centre[1])


def _synthetic_plan(runs, owner="U1", label_net="RXD"):
    anchor, near = _near_rxd()
    plan = LayoutPlan(
        parts=[
            LayoutPart(part_id="U1", symbol_ref=U1_REF, x=685.0, y=725.0),
            LayoutPart(part_id="C3", symbol_ref=C3_REF, x=630.0, y=730.0),
        ],
        segments=[LayoutSegment(net=net, points=list(points)) for net, points in runs],
        labels=[LayoutLabel(
            net=label_net, text=label_net, bbox=near, x=anchor[0], y=anchor[1],
            part_id=owner, text_mode=TEXT_MODE_NATIVE,
        )],
    )
    return plan, plan.labels[0], near


def _seat(plan, label, circuit, library, strict: bool):
    wires = pc._plan_wires(plan)
    sites = () if strict else pc._owned_pin_sites(plan, label, library, circuit)
    return pc._native_label_seat(
        label.net, (label.x, label.y), (-1.0, 0.0), [], wires,
        owned_pin_sites=sites,
    ), sites


def _gap(box, points) -> float:
    return readability._box_run_gap(box, tuple(tuple(p) for p in points))


# ------------------------------------------- 1. the strict path did not move


def test_an_unowned_foreign_run_at_5_5_is_still_skipped():
    """534z's ruler: a wire this page cannot prove is the part's own stays 10."""
    circuit = CircuitSpec.load(CIRCUIT)
    library = drawapply.load_library(LIBRARY)
    _, near = _near_rxd()
    run = [("TXD", ((near[0], near[3] + 5.5), (near[2] + 40.0, near[3] + 5.5)))]
    plan, label, _ = _synthetic_plan(run)
    assert _gap(near, run[0][1]) < readability.NATIVE_LABEL_CARRIER_LIMIT
    seat, sites = _seat(plan, label, circuit, library, strict=False)
    assert sites, "the fixture must still offer U1's own pin sites"
    assert seat is not None and seat != near, (
        f"the 5.5-unit foreign run was read as the part's own lead: seat {seat}")
    assert _gap(seat, run[0][1]) >= readability.NATIVE_LABEL_CARRIER_LIMIT


def test_the_default_signature_is_the_strict_seat():
    """An old caller passes four arguments and gets the 053Z/534z ladder."""
    anchor, near = _near_rxd()
    run = [("TXD", ((near[0], near[3] + 5.5), (near[2] + 40.0, near[3] + 5.5)))]
    strict = pc._native_label_seat("RXD", anchor, (-1.0, 0.0), [], run)
    assert strict != near and _gap(strict, run[0][1]) >= (
        readability.NATIVE_LABEL_CARRIER_LIMIT)


def test_a_fake_part_id_buys_nothing():
    """`part_id` alone is not a proof: an unplaced owner yields no owned site."""
    circuit = CircuitSpec.load(CIRCUIT)
    library = drawapply.load_library(LIBRARY)
    _, near = _near_rxd()
    run = [("V3", ((610.0, 730.0), (640.0, 730.0)))]
    plan, label, _ = _synthetic_plan(run, owner="U9")
    assert pc._owned_pin_sites(plan, label, library, circuit) == []
    seat, _sites = _seat(plan, label, circuit, library, strict=False)
    assert seat != near, f"a fabricated part_id widened the seat to {seat}"


def test_a_run_in_the_owner_net_that_does_not_end_on_its_pin_stays_foreign():
    """U1 is on V3, but a V3 run elsewhere is still a wire: no name-level pass."""
    circuit = CircuitSpec.load(CIRCUIT)
    library = drawapply.load_library(LIBRARY)
    _, near = _near_rxd()
    # Ends at (620, 730): on V3's row, 20 units short of U1.4's tip (640, 730).
    run = [("V3", ((600.0, 730.0), (620.0, 730.0)))]
    plan, label, _ = _synthetic_plan(run)
    sites = pc._owned_pin_sites(plan, label, library, circuit)
    assert ("V3", (640.0, 730.0)) in sites, sites
    seat, _sites = _seat(plan, label, circuit, library, strict=False)
    assert seat != near, f"a non-terminating V3 run was read as U1's lead: {seat}"


def test_another_parts_pin_lead_at_5_5_is_still_foreign():
    """C3's own pin lead ends on a real tip — but not on the label part's pin."""
    circuit = CircuitSpec.load(CIRCUIT)
    library = drawapply.load_library(LIBRARY)
    _, near = _near_rxd()
    # C3 sits at (630, 730); its pin 1 tip is (615, 730), net V3 in the spec.
    run = [("V3", ((600.0, 730.0), (615.0, 730.0)))]
    plan, label, _ = _synthetic_plan(run)
    assert _gap(near, run[0][1]) < readability.NATIVE_LABEL_CARRIER_LIMIT
    seat, sites = _seat(plan, label, circuit, library, strict=False)
    assert ("V3", (640.0, 730.0)) in sites
    assert seat != near, f"C3's pin lead was read as U1's: {seat}"


def test_a_missing_profile_or_net_yields_no_owned_site():
    circuit = CircuitSpec.load(CIRCUIT)
    library = drawapply.load_library(LIBRARY)
    run = [("V3", ((610.0, 730.0), (640.0, 730.0)))]
    plan, label, _ = _synthetic_plan(run)
    plan.parts[0].symbol_ref = "NOT-IN-THE-LIBRARY"
    assert pc._owned_pin_sites(plan, label, library, circuit) == []
    plan.parts[0].symbol_ref = U1_REF
    label.part_id = ""
    assert pc._owned_pin_sites(plan, label, library, circuit) == []


# ------------------------------------ 2. the one class that may come to 5


def test_the_own_parts_adjacent_pin_lead_may_seat_at_5_but_not_be_touched():
    """The 543d `RXD` case, as geometry: U1's V3 lead, 5.5 from the near seat."""
    circuit = CircuitSpec.load(CIRCUIT)
    library = drawapply.load_library(LIBRARY)
    _, near = _near_rxd()
    run = [("V3", ((610.0, 730.0), (640.0, 730.0)))]
    plan, label, _ = _synthetic_plan(run)
    gap = _gap(near, run[0][1])
    assert readability.FLAG_BODY_CLEARANCE <= gap < (
        readability.NATIVE_LABEL_CARRIER_LIMIT), gap
    seat, sites = _seat(plan, label, circuit, library, strict=False)
    assert ("V3", (640.0, 730.0)) in sites
    assert seat == near, f"the owned lead did not open the near rung: {seat}"


def test_an_owned_lead_that_touches_the_seat_still_refuses_it():
    """The 5-unit floor is a floor: contact is zero, not "own"."""
    circuit = CircuitSpec.load(CIRCUIT)
    library = drawapply.load_library(LIBRARY)
    _, near = _near_rxd()
    # Ends on U1.4's tip, then runs along the seat's top edge before it.
    run = [("V3", ((608.0, 735.5), (600.0, 735.5), (600.0, 730.0), (640.0, 730.0)))]
    plan, label, _ = _synthetic_plan(run)
    assert _gap(near, run[0][1]) <= readability.TOL
    seat, _sites = _seat(plan, label, circuit, library, strict=False)
    assert seat != near, f"a touching owned lead was accepted: {seat}"


def test_an_owned_lead_across_the_stub_still_refuses_the_seat():
    """Ownership relaxes the distance, never the "stub may not cross" rule."""
    circuit = CircuitSpec.load(CIRCUIT)
    library = drawapply.load_library(LIBRARY)
    anchor, near = _near_rxd()
    # Ends on U1.4's tip, then turns and runs through the stub's own corridor —
    # 6 units clear of the box, so only the crossing can refuse this seat.
    run = [("V3", ((640.0, 730.0), (638.0, 730.0), (638.0, 750.0)))]
    plan, label, _ = _synthetic_plan(run)
    stub_start, stub_stop = anchor, ((near[0] + near[2]) / 2.0, anchor[1])
    assert readability._run_on_polyline(
        stub_start, stub_stop, tuple(tuple(p) for p in run[0][1]))
    assert _gap(near, run[0][1]) >= readability.FLAG_BODY_CLEARANCE
    seat, _sites = _seat(plan, label, circuit, library, strict=False)
    assert seat != near, f"the stub was allowed to cross an owned lead: {seat}"


# ------------------------------------------ 3. the real pages, per candidate


def _rxd(plan):
    label = next(
        item for item in plan.labels if item.net == "RXD" and item.part_id == "U1")
    box = tuple(float(value) for value in label.bbox)
    anchor = (float(label.x), float(label.y))
    centre = ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)
    return label, box, anchor, centre


def _box_gap(one, other) -> float:
    dx = max(one[0] - other[2], other[0] - one[2], 0.0)
    dy = max(one[1] - other[3], other[1] - one[3], 0.0)
    return (dx * dx + dy * dy) ** 0.5


def _drawn_bodies(plan, library):
    out = []
    for part in plan.parts:
        pose = dc.SymbolPose(part.rotation, part.mirror)
        body = dc._body_box(library[part.symbol_ref], pose, (part.x, part.y))
        if body is not None:
            out.append((part.part_id, tuple(float(value) for value in body)))
    return out


def _tip_sites(plan, label, library, circuit):
    """`(endpoint, net)` for the label part's pins — the drawing's own fold."""
    sites = {}
    for part in plan.parts:
        if part.part_id != getattr(label, "part_id", ""):
            continue
        pose = dc.SymbolPose(part.rotation, part.mirror)
        for pin in library[part.symbol_ref].pins:
            net = circuit.net_of_pin(f"{part.part_id}.{pin.number}")
            if not net:
                continue
            dx, dy = dc._posed_tip(pin, pose)
            sites[(round(part.x + dx, 6), round(part.y + dy, 6))] = net
    return sites


def _read_stranded(label, plan, library, circuit):
    """Every run's gap to the label box, split by ownership (for the report)."""
    box = tuple(float(value) for value in label.bbox)
    sites = _tip_sites(plan, label, library, circuit)
    foreign, owned = [], []
    for segment in plan.segments:
        if segment.net == label.net or len(segment.points) < 2:
            continue
        points = tuple((float(p[0]), float(p[1])) for p in segment.points)
        ends = ((round(points[0][0], 6), round(points[0][1], 6)),
                (round(points[-1][0], 6), round(points[-1][1], 6)))
        own = any(sites.get(end) == segment.net for end in ends)
        (owned if own else foreign).append(
            (segment.net, readability._box_run_gap(box, points)))
    return foreign, owned


def test_both_pages_compile_with_four_candidates():
    for name in PAGES:
        _circuit, _library, result = _compile(name)
        assert len(result.pages) == 4, (name, len(result.pages))
        assert len(result.ranked) == 4, (name, len(result.ranked))


def test_every_candidate_prints_rxd_on_its_pins_outward_side():
    for name in PAGES:
        _circuit, library, result = _compile(name)
        for index, candidate in enumerate(result.ranked):
            plan = candidate.page.plan
            _label, box, anchor, centre = _rxd(plan)
            stub = abs(centre[0] - anchor[0]) + abs(centre[1] - anchor[1])
            assert abs(centre[1] - anchor[1]) <= readability.TOL, (name, index)
            assert 0.0 < stub <= RXD_STUB, (
                f"{name} candidate {index}: RXD stub {stub:g} is past 617E's "
                f"{RXD_STUB:g} (617D's defect was {PRE_FIX_STUB:g})")
            assert box[2] <= anchor[0] + readability.TOL, (
                f"{name} candidate {index}: RXD box {box} stands past its pin "
                f"{anchor}, towards the part body")
            for part_id, body in _drawn_bodies(plan, library):
                assert not (
                    min(box[2], body[2]) - max(box[0], body[0]) > readability.TOL
                    and min(box[3], body[3]) - max(box[1], body[1]) > readability.TOL
                ), f"{name} candidate {index}: RXD lands on {part_id} {body}"
            c3 = next(item for item in plan.texts if item.text == "C3")
            gap = _box_gap(box, tuple(float(v) for v in c3.bbox))
            assert gap >= TEXT_FLOOR, (
                f"{name} candidate {index}: RXD is {gap:g} from C3's reference")


def test_every_candidate_keeps_foreign_10_and_own_part_5():
    """The stratification, measured per candidate on the compiled page."""
    for name in PAGES:
        circuit, library, result = _compile(name)
        for index, candidate in enumerate(result.ranked):
            plan = candidate.page.plan
            label, _box, _anchor, _centre = _rxd(plan)
            foreign, owned = _read_stranded(label, plan, library, circuit)
            assert owned, (
                f"{name} candidate {index}: no own-part pin lead is measured — "
                "the exception this batch adds is not in the drawing")
            for net, gap in foreign:
                assert gap >= readability.NATIVE_LABEL_CARRIER_LIMIT - readability.TOL, (
                    f"{name} candidate {index}: foreign {net} comes to {gap:g} "
                    f"of RXD's box; 620D keeps 10 for every wire it cannot prove "
                    "is the part's own")
            for net, gap in owned:
                assert gap >= readability.FLAG_BODY_CLEARANCE - readability.TOL, (
                    f"{name} candidate {index}: U1's own {net} lead is {gap:g} "
                    f"from RXD's box, under the 5-unit grazing distance")


class _Union:
    def __init__(self):
        self.parent = {}

    def find(self, item):
        self.parent.setdefault(item, item)
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def join(self, one, other):
        root_one, root_other = self.find(one), self.find(other)
        if root_one != root_other:
            self.parent[root_other] = root_one


def _on_segment(point, start, stop, tol=1e-6) -> bool:
    (px, py), (ax, ay), (bx, by) = point, start, stop
    if abs((bx - ax) * (py - ay) - (by - ay) * (px - ax)) > 1e-6:
        return False
    return (
        min(ax, bx) - tol <= px <= max(ax, bx) + tol
        and min(ay, by) - tol <= py <= max(ay, by) + tol
    )


def _landing(plan, circuit, library) -> dict:
    """617C/617E's per-pin re-check (landing + connectivity), unchanged."""
    tips: dict[str, tuple[float, float]] = {}
    for part in plan.parts:
        pose = dc.SymbolPose(part.rotation, part.mirror)
        for pin in library[part.symbol_ref].pins:
            dx, dy = dc._posed_tip(pin, pose)
            tips[f"{part.part_id}.{pin.number}"] = (
                round(part.x + dx, 6), round(part.y + dy, 6))
    segments_by_net: dict[str, list] = {}
    for segment in plan.segments:
        points = [(round(x, 6), round(y, 6)) for x, y in segment.points]
        for start, stop in zip(points, points[1:]):
            segments_by_net.setdefault(segment.net, []).append((start, stop))
    flag_nets = {symbol.net for symbol in plan.power_symbols}
    label_nets = {label.net for label in plan.labels}
    nc_pins = {item.pin for item in circuit.nc}
    unlanded, classes = [], {}
    for key, point in tips.items():
        if key in nc_pins:
            classes["nc"] = classes.get("nc", 0) + 1
            continue
        net_ids = [net.id for net in circuit.nets if key in net.members]
        own = segments_by_net.get(net_ids[0], []) if net_ids else []
        if any(abs(point[0] - a[0]) <= 1e-6 and abs(point[1] - a[1]) <= 1e-6
               for seg in own for a in seg):
            kind = "wire-end"
        elif any(_on_segment(point, *seg) for seg in own):
            kind = "wire"
        elif any(other != key
                 and abs(point[0] - q[0]) <= 1e-6
                 and abs(point[1] - q[1]) <= 1e-6
                 for other, q in tips.items()):
            kind = "abut"
        elif net_ids and (net_ids[0] in flag_nets or net_ids[0] in label_nets):
            kind = "named"
        else:
            kind = "UNLANDED"
            unlanded.append(key)
        classes[kind] = classes.get(kind, 0) + 1
    broken = []
    for net in circuit.nets:
        members = [name for name in tips if name in net.members and name not in nc_pins]
        if len(members) < 2:
            continue
        union = _Union()
        for member in members:
            union.find(tips[member])
        for start, stop in segments_by_net.get(net.id, []):
            union.join(start, stop)
        for member in members:
            for start, stop in segments_by_net.get(net.id, []):
                if _on_segment(tips[member], start, stop):
                    union.join(tips[member], start)
        if len({union.find(tips[member]) for member in members}) > 1 \
                and net.id not in flag_nets and net.id not in label_nets:
            broken.append(net.id)
    return {
        "parts": len(plan.parts), "pins": len(tips), "nets": len(circuit.nets),
        "unlanded": unlanded, "broken": broken, "classes": classes,
    }


def test_pins_nets_and_landing_do_not_regress():
    for name in PAGES:
        circuit, library, result = _compile(name)
        for index, candidate in enumerate(result.ranked):
            report = _landing(candidate.page.plan, circuit, library)
            assert report["pins"] == 58, (name, index, report)
            assert report["nets"] == 17, (name, index, report)
            assert report["unlanded"] == [], (name, index, report)
            assert report["broken"] == [], (name, index, report)
            if name == "617e":
                assert report["classes"] == CLASSES, (name, index, report)


def test_617e_reads_forward_from_the_single_field_adjustment():
    _circuit, _library, result = _compile("617e")
    for index, candidate in enumerate(result.ranked):
        assert candidate.metrics["page_backflow_length"] == 0, (index, candidate.metrics)
    before = PAGES["543d"].read_text(encoding="utf-8").splitlines(keepends=True)
    after = PAGES["617e"].read_text(encoding="utf-8").splitlines(keepends=True)
    changed = [line for line in difflib.unified_diff(before, after, n=0)
               if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))]
    assert changed == ['-  "moduleColumns": 2,\n', '+  "moduleColumns": 3,\n'], changed
    old = json.loads(PAGES["543d"].read_text(encoding="utf-8"))
    new = json.loads(PAGES["617e"].read_text(encoding="utf-8"))
    assert old.pop("moduleColumns") == 2
    assert new.pop("moduleColumns") == 3
    assert old == new
