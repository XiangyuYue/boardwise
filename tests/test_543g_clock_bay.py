"""543G-12b: the bridge's oscillator as **one bay**, seated from its host pins.

543G-10/11 measured the gap the ladder leaves: a crystal across two of its host's
pins and the two capacitors on those pins are one branch of the circuit, but the
seater sees three siblings of one owner and hands each the next rung — 60, 120,
180 from the *same* anchor — so the two clock nets ran 240 and 210 units back to
the bridge. The rung index is a statement about three branches sharing one pad;
here the pads are what separate them.

What is pinned here, on the document that asks for the explicit reading
(``native-attr`` + ``serviceLayout``, 543H-5's ``_pair_bands``):

* **both clock nets inside 120 units**, each one continuous run;
* **one orthogonal jog at most, and it is the bridge's own pin pitch** — the
  crystal's two feet are 40 apart and the host's two pins 10, so 30 is the
  leftover; a U-line drawn to equalise the two lengths is refused here;
* **every pin of each net lands on the run's own vertices** — the netlist, not
  the picture — and neither load's ground pin is on either clock net;
* **the two loads are one pair**: one pose, one length each way, one local
  ground flag apiece;
* **nothing else moved**: the page's other nets and every other island keep
  their runs (543H/543I/543J's measured shapes are re-read here off the same
  page).

The negative controls say what a bay is *not*: a document that did not ask for
it, an owner missing one of the two loads, and an owner with two bridges. Each
is compared against the same sheet drawn with the bay neutered, so "no bay"
means **the old drawing**, not a second new one.
"""

from __future__ import annotations

import copy
import json
import pathlib

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.geometry import transform_point
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawcompiler as dc
from boardwise.engines import pagecompiler as pc

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPECS = ROOT / "blocklib" / "specs"
STEM = "ch340_uart_543g"
PAGE_BOX = (0.0, 0.0, 1170.0, 825.0)

#: The clock's own parts, named here only because this sheet has them: the
#: contract is read off the netlist below, never off these ids.
BRIDGE = "X1"
LOADS = ("C5", "C6")
HOST = "U1"
CLOCK_NETS = ("XI", "XO")

#: S-05's corridor, and the whole budget a bay may spend on one net (543G-12b's
#: `2 * lane`). Stated here as the acceptance, not as a compiler constant.
NET_LIMIT = 120.0
JOG_LIMIT = 30.0


# ------------------------------------------------------------------ fixtures


def _raw(name: str) -> dict:
    return json.loads((SPECS / f"{STEM}.{name}.json").read_text(encoding="utf-8"))


def _book():
    payload = _raw("library")
    items = payload["profiles"] if isinstance(payload, dict) else payload
    return {p.symbol_ref: p for p in (SymbolProfile.from_dict(i) for i in items)}


def _presentation(payload: dict | None = None) -> PresentationSpec:
    return PresentationSpec.from_dict(copy.deepcopy(payload or _raw("presentation")))


def _circuit(payload: dict | None = None) -> CircuitSpec:
    return CircuitSpec.from_dict(copy.deepcopy(payload or _raw("circuit")))


def _compile(circuit=None, presentation=None, book=None):
    return pc.compile_page(
        circuit or _circuit(),
        presentation or _presentation(),
        book or _book(),
        pc.PageCompileBudget(page_box=PAGE_BOX),
    )


def _pages(circuit=None, presentation=None):
    result = _compile(circuit, presentation)
    assert result.ok, result.render_failures()
    assert result.pages, "no page candidate"
    return result.pages


def _pin(plan, book, member: str) -> tuple[float, float]:
    part_id, _, token = member.partition(".")
    placed = plan.part(part_id)
    assert placed is not None, f"{member} is not placed"
    profile = book[placed.symbol_ref]
    pin = profile.pin(token)
    if pin is None:
        pin = next(item for item in profile.pins if item.name == token)
    return transform_point(
        pin.tip[0], pin.tip[1], rotation=placed.rotation, mirror=placed.mirror,
        ox=placed.x, oy=placed.y,
    )


def _runs(plan, net_id: str):
    """Every drawn run of one net as ``(length, [(x, y), …])``."""
    out = []
    for segment in plan.segments:
        if segment.net != net_id:
            continue
        points = [(round(float(x), 1), round(float(y), 1)) for x, y in segment.points]
        length = sum(
            abs(points[i + 1][0] - points[i][0]) + abs(points[i + 1][1] - points[i][1])
            for i in range(len(points) - 1)
        )
        out.append((round(length, 1), points))
    return out


def _on_run(point, points) -> bool:
    """Is ``point`` on this orthogonal run (a vertex, or on one of its legs)?"""
    for start, stop in zip(points, points[1:]):
        same_x = abs(start[0] - stop[0]) < 1e-6 and abs(point[0] - start[0]) < 1e-6
        same_y = abs(start[1] - stop[1]) < 1e-6 and abs(point[1] - start[1]) < 1e-6
        if same_x and min(start[1], stop[1]) - 1e-6 <= point[1] <= max(start[1], stop[1]) + 1e-6:
            return True
        if same_y and min(start[0], stop[0]) - 1e-6 <= point[0] <= max(start[0], stop[0]) + 1e-6:
            return True
    return False


def _geometry(result) -> list[object]:
    """Every candidate's geometry digest — the byte-level comparison."""
    return [page.plan.geometry_sha256() for page in result.pages]


# ------------------------------------------------------------- the bay itself


def test_both_clock_nets_are_drawn_inside_120_units():
    """XI and XO: one continuous run each, ≤120 units, at most one 30-unit jog.

    The ladder's answer on the same sheet is 240 and 210 (543G-10's point
    table). What replaces it is not "a shorter line": it is the same three pins
    per net, drawn from the seats the host pins give.
    """
    book = _book()
    for index, page in enumerate(_pages()):
        plan = page.plan
        for net_id in CLOCK_NETS:
            runs = _runs(plan, net_id)
            assert len(runs) == 1, (index, net_id, runs)
            length, points = runs[0]
            assert length <= NET_LIMIT, (index, net_id, length, points)

            # the run is one continuous orthogonal polyline, and the only
            # perpendicular travel it may do is the bridge's own leftover
            ys = [point[1] for point in points]
            xs = [point[0] for point in points]
            assert max(ys) - min(ys) <= JOG_LIMIT, (index, net_id, points)
            assert max(xs) - min(xs) <= NET_LIMIT, (index, net_id, points)
            # no U-line: the run never doubles back along the net's own axis
            forward = [xs[i + 1] - xs[i] for i in range(len(xs) - 1)]
            assert all(step * forward[0] >= 0 for step in forward), (index, net_id, points)

            # every pin of this net, on the netlist's own coordinates, is on the run
            members = [m for net in _circuit().nets if net.id == net_id
                       for m in net.members]
            for member in members:
                tip = tuple(round(float(v), 1) for v in _pin(plan, book, member))
                assert _on_run(tip, points), (index, net_id, member, tip, points)


def test_the_clock_loads_are_one_pair_and_their_ground_pins_are_not_on_the_nets():
    """One pose, one local ground flag each, and no pad crossed between nets."""
    book = _book()
    circuit = _circuit()
    clock_members = {
        member for net in circuit.nets if net.id in CLOCK_NETS
        for member in net.members
    }
    ground = {
        member for net in circuit.nets if net.id == "GND" for member in net.members
    }
    for index, page in enumerate(_pages()):
        plan = page.plan
        poses = {load: (plan.part(load).rotation, plan.part(load).mirror) for load in LOADS}
        assert len(set(poses.values())) == 1, (index, poses)

        # The loads return through their own ground pin, and those pins are on
        # neither clock net: a shared flag here would be a cross-net short drawn
        # as a picture, and the compiler would still say ok.
        returns = {}
        for load in LOADS:
            pin = next(
                member for member in ground if member.startswith(f"{load}.")
            )
            returns[load] = pin
            assert pin not in clock_members
            tip = tuple(round(float(v), 1) for v in _pin(plan, book, pin))
            for net_id in CLOCK_NETS:
                for _length, points in _runs(plan, net_id):
                    assert not _on_run(tip, points), (index, pin, net_id, points)

        flags = {}
        for load in LOADS:
            tip = _pin(plan, book, returns[load])
            below = [
                (round(float(flag.x), 1), round(float(flag.y), 1))
                for flag in plan.power_symbols
                if flag.net == "GND"
                and abs(float(flag.x) - float(tip[0])) < 1e-6
                and float(flag.y) < float(tip[1])
            ]
            assert len(below) == 1, (index, load, below)
            flags[load] = below[0]
        assert len(set(flags.values())) == len(LOADS), (index, flags)


def test_the_bridge_and_its_loads_keep_their_pins_off_each_others_geometry():
    """The bay is compact but the parts do not sit on each other's bodies.

    Read off the drawn page: no clock run passes through the interior of any of
    the four parts' bodies, and the loads' own ground pins are clear of the
    bridge's box.
    """
    book = _book()
    for index, page in enumerate(_pages()):
        plan = page.plan
        bodies = {}
        for part_id in (BRIDGE, *LOADS, HOST):
            placed = plan.part(part_id)
            profile = book[placed.symbol_ref]
            assert profile.body is not None, part_id
            low = transform_point(
                profile.body[0], profile.body[1], rotation=placed.rotation,
                mirror=placed.mirror, ox=placed.x, oy=placed.y,
            )
            high = transform_point(
                profile.body[2], profile.body[3], rotation=placed.rotation,
                mirror=placed.mirror, ox=placed.x, oy=placed.y,
            )
            bodies[part_id] = (
                min(low[0], high[0]), min(low[1], high[1]),
                max(low[0], high[0]), max(low[1], high[1]),
            )
        for net_id in CLOCK_NETS:
            for _length, points in _runs(plan, net_id):
                for part_id, box in bodies.items():
                    for start, stop in zip(points, points[1:]):
                        assert not _segment_enters(start, stop, box), (
                            index, net_id, part_id, box, points
                        )


def _segment_enters(start, stop, box) -> bool:
    """Does this orthogonal leg pass through the box's **interior**?"""
    eps = 1e-6
    if abs(start[0] - stop[0]) < eps:  # vertical
        x = start[0]
        low, high = sorted((start[1], stop[1]))
        return box[0] + eps < x < box[2] - eps and high > box[1] + eps and low < box[3] - eps
    y = start[1]
    low, high = sorted((start[0], stop[0]))
    return box[1] + eps < y < box[3] - eps and high > box[0] + eps and low < box[2] - eps


# --------------------------------------------------------------- the page


def test_the_rest_of_the_page_keeps_its_measured_shapes():
    """543H/543I/543J/543L: the bay moves the clock and nothing else.

    The CC pair, the D± carriers, the two 30-unit decoupling services and the
    VBUS pair are re-read on the same page: a compacted clock may not buy its
    room out of another island's runs.
    """
    book = _book()
    for index, page in enumerate(_pages()):
        plan = page.plan
        for net_id in ("CC1", "CC2"):
            runs = _runs(plan, net_id)
            assert len(runs) == 1 and runs[0][0] == 130.0, (index, net_id, runs)
        for net_id, service, host in (("V3", "C4.1", "U1.4"), ("+5V", "C3.1", "U1.16")):
            here = _pin(plan, book, service)
            there = _pin(plan, book, host)
            assert abs(here[0] - there[0]) + abs(here[1] - there[1]) == 30.0, (
                index, net_id, here, there
            )
        for net_id in ("D+", "D-"):
            runs = _runs(plan, net_id)
            assert runs, (index, net_id)
            assert max(length for length, _ in runs) <= 120.0, (index, net_id, runs)


# ------------------------------------------------------- negative controls


def _without(payload: dict, key: str) -> dict:
    out = copy.deepcopy(payload)
    out.pop(key, None)
    return out


def _neutered(monkeypatch):
    monkeypatch.setattr(dc, "_place_clock_bays", lambda *args, **kwargs: frozenset())


def test_the_bay_is_off_for_a_document_that_did_not_ask(monkeypatch):
    """No ``native-attr`` or no ``serviceLayout`` = the ladder, byte for byte.

    The gate is 543H-5's ``_pair_bands``: both keys, or neither. Each half is
    compiled twice — once with the bay, once with it neutered — and the two must
    agree on every candidate's geometry digest.
    """
    for key in ("textPlacement", "serviceLayout"):
        payload = _without(_raw("presentation"), key)
        asked = _compile(presentation=_presentation(payload))
        saved = dc._place_clock_bays
        dc._place_clock_bays = lambda *args, **kwargs: frozenset()
        try:
            plain = _compile(presentation=_presentation(payload))
        finally:
            dc._place_clock_bays = saved
        assert _geometry(asked) == _geometry(plain), key
        assert len(asked.pages) == len(plain.pages), key

    # …and the old geometry is still what an unasked document draws: the clock
    # ladder's first sibling is a lane out and the net reaches 240.
    payload = _without(_raw("presentation"), "textPlacement")
    page = _compile(presentation=_presentation(payload)).pages[0]
    lengths = [length for length, _ in _runs(page.plan, "XI")]
    assert lengths and lengths[0] == 240.0, lengths


def test_a_bay_needs_a_load_on_each_of_the_bridge_nets(monkeypatch):
    """One load is not a bay: the ladder keeps the clock it would have drawn.

    The circuit copy drops the second load and every pin it held; the spec
    members follow. Nothing is deleted from the fixtures.
    """
    circuit = _raw("circuit")
    circuit["parts"] = [part for part in circuit["parts"] if part["id"] != "C6"]
    for net in circuit["nets"]:
        net["members"] = [
            member for member in net["members"] if not member.startswith("C6.")
        ]
    payload = copy.deepcopy(_raw("presentation"))
    for module in payload["modules"]:
        if module["id"] == "serial":
            module["parts"] = [part for part in module["parts"] if part != "C6"]
    payload["partTexts"].pop("C6", None)

    asked = _compile(_circuit(circuit), _presentation(payload))
    saved = dc._place_clock_bays
    dc._place_clock_bays = lambda *args, **kwargs: frozenset()
    try:
        plain = _compile(_circuit(circuit), _presentation(payload))
    finally:
        dc._place_clock_bays = saved
    assert asked.ok and asked.pages, asked.render_failures()
    assert _geometry(asked) == _geometry(plain)
    # the ladder's answer is still the long one — no bay was seated
    assert [length for length, _ in _runs(asked.pages[0].plan, "XI")][0] > NET_LIMIT


def test_two_bridges_on_one_owner_are_not_a_bay(monkeypatch):
    """Two parts across the same two pins are not "one bridge plus its loads"."""
    circuit = _raw("circuit")
    circuit["parts"].append({
        "id": "X1B", "symbolRef": "HC-49S-12M-C389706", "value": "12MHz",
        "lcsc": "C389706", "provenance": "verified_recipe",
    })
    for net in circuit["nets"]:
        if net["id"] == "XI":
            net["members"].append("X1B.1")
        if net["id"] == "XO":
            net["members"].append("X1B.2")
    payload = copy.deepcopy(_raw("presentation"))
    for module in payload["modules"]:
        if module["id"] == "serial":
            module["parts"] = module["parts"] + ["X1B"]
    payload["partTexts"]["X1B"] = "above"

    asked = _compile(_circuit(circuit), _presentation(payload))
    saved = dc._place_clock_bays
    dc._place_clock_bays = lambda *args, **kwargs: frozenset()
    try:
        plain = _compile(_circuit(circuit), _presentation(payload))
    finally:
        dc._place_clock_bays = saved
    assert asked.ok and asked.pages, asked.render_failures()
    assert _geometry(asked) == _geometry(plain)


def test_the_measurement_catches_the_ladder(monkeypatch):
    """The positive control for this file: with the bay off, the sheet fails.

    543G-10's point table is the reference: XI 240 as a single row and XO 210
    with one 30-unit jog. The contract above refuses exactly that drawing.
    """
    _neutered(monkeypatch)
    page = _pages()[0]
    lengths = {net: [length for length, _ in _runs(page.plan, net)] for net in CLOCK_NETS}
    assert lengths == {"XI": [240.0], "XO": [210.0]}, lengths
    assert max(lengths["XI"]) > NET_LIMIT


# ----------------------------------------------- 543G-12c: the ink, not the body


def _glyph_box(plan, book, flag):
    """The box a net flag's glyph draws (its profile body, posed)."""
    profile = book.get(flag.symbol_ref)
    assert profile is not None and profile.body is not None, flag.symbol_ref
    low = transform_point(
        profile.body[0], profile.body[1], rotation=flag.rotation, mirror=False,
        ox=flag.x, oy=flag.y,
    )
    high = transform_point(
        profile.body[2], profile.body[3], rotation=flag.rotation, mirror=False,
        ox=flag.x, oy=flag.y,
    )
    return (
        min(low[0], high[0]), min(low[1], high[1]),
        max(low[0], high[0]), max(low[1], high[1]),
    )


def _gap(left, right) -> float:
    """Signed room between two boxes: negative means they overlap."""
    return max(left[0] - right[2], right[0] - left[2],
               left[1] - right[3], right[1] - left[3])


#: How much clear page the clock's own rows and flag glyphs must keep between
#: them. Not a constant of the compiler: S-05's corridor (30) is what a *net*
#: gets; two rows of text need a readable separation and one row's height is 9,
#: so 4 is "not touching and visibly apart".
INK_CLEAR = 4.0


def test_the_three_clock_parts_keep_their_own_rows_clear_of_each_other():
    """543G-12c: measured on the **ink** the host will print, not the bodies.

    The bay's 90/90 runs were right while the group was unreadable: C5's ground
    flag sat 0.2 units from X1's reference row and 1.7 from the crystal's value
    row (543G-12c's measurement of the rejected candidate). A row is ink: the
    host prints it at the box the plan states, so this reads `plan.texts` and
    the flag **glyph** boxes (the PWR-GND profile draws no name), and refuses
    any pair of them — across parts — that overlaps or comes closer than
    :data:`INK_CLEAR`, plus any clock run that passes through one.

    The two rows **of one part** are stacked by construction and are not a
    collision; every other pair here is.
    """
    book = _book()
    for index, page in enumerate(_pages()):
        plan = page.plan
        rows: dict[str, Box] = {}
        for text in plan.texts:
            if text.part_id not in (*LOADS, BRIDGE):
                continue
            kind = (text.kind or "").lower()
            assert kind in ("reference", "value"), (index, text.part_id, kind)
            key = f"{text.part_id}.{kind}"
            assert key not in rows, (index, "two rows of one kind", key)
            rows[key] = tuple(round(float(v), 3) for v in text.bbox)
        for part_id in (*LOADS, BRIDGE):
            for kind in ("reference", "value"):
                assert f"{part_id}.{kind}" in rows, (index, part_id, kind, sorted(rows))

        ground = {
            member for net in _circuit().nets if net.id == "GND"
            for member in net.members
        }
        flags = {}
        for load in LOADS:
            member = next(m for m in ground if m.startswith(f"{load}."))
            tip = _pin(plan, book, member)
            below = [
                flag for flag in plan.power_symbols
                if flag.net == "GND"
                and abs(float(flag.x) - float(tip[0])) < 1e-6
                and float(flag.y) < float(tip[1])
            ]
            assert len(below) == 1, (index, load, below)
            flag = below[0]
            flags[f"GND@{round(float(flag.x), 1)},{round(float(flag.y), 1)}"] = (
                _glyph_box(plan, book, flag)
            )
        assert len(flags) == len(LOADS), (index, flags)

        boxes = {**rows, **flags}
        names = sorted(boxes)
        for i, one in enumerate(names):
            for other in names[i + 1:]:
                if one.split(".")[0] == other.split(".")[0] and one in rows and other in rows:
                    continue  # one part's own two rows, stacked on purpose
                room = _gap(boxes[one], boxes[other])
                assert room >= INK_CLEAR, (index, one, other, round(room, 2), boxes)

        # …and the rows read **away** from the group: C5's to its left, X1's and
        # C6's to their right. That is the `partTexts` statement the document now
        # carries, measured where the reader sees it.
        c5_body = _body_box(plan, book, "C5")
        x1_body = _body_box(plan, book, BRIDGE)
        c6_body = _body_box(plan, book, "C6")
        assert rows["C5.value"][2] <= c5_body[0] + 1e-6, (index, rows["C5.value"], c5_body)
        assert rows["X1.reference"][0] >= x1_body[2] - 1e-6, (index, rows["X1.reference"], x1_body)
        assert rows["C6.value"][0] >= c6_body[2] - 1e-6, (index, rows["C6.value"], c6_body)

        for net_id in CLOCK_NETS:
            for _length, points in _runs(plan, net_id):
                for name, box in boxes.items():
                    for start, stop in zip(points, points[1:]):
                        assert _gap(_leg_box(start, stop), box) >= 2.0, (
                            index, net_id, name, box, points
                        )


def _body_box(plan, book, part_id):
    """A part's drawn body box on this page."""
    placed = plan.part(part_id)
    profile = book[placed.symbol_ref]
    assert profile.body is not None, part_id
    low = transform_point(
        profile.body[0], profile.body[1], rotation=placed.rotation,
        mirror=placed.mirror, ox=placed.x, oy=placed.y,
    )
    high = transform_point(
        profile.body[2], profile.body[3], rotation=placed.rotation,
        mirror=placed.mirror, ox=placed.x, oy=placed.y,
    )
    return (
        min(low[0], high[0]), min(low[1], high[1]),
        max(low[0], high[0]), max(low[1], high[1]),
    )


def _leg_box(start, stop):
    return (
        min(start[0], stop[0]), min(start[1], stop[1]),
        max(start[0], stop[0]), max(start[1], stop[1]),
    )
