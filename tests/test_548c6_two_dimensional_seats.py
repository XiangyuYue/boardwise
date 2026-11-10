"""548C6: the 548C B2 island needs branch seats that are not one column.

548C's B2 variant only moves surface text: every value row on the 547A mcu
island becomes the full unit/tolerance/package line (`LONG_VALUES`, the same
table as `evidence/548C/variants/build_variants.py`, inlined here and imported
from `test_548c5_text_pitch` so the two files cannot drift). Nothing electrical
changes: same parts, same nets, same designators, same symbols.

Measured, not assumed — the island compiles to **0 candidates**, and the first
refusal is the 159.5-unit value row printed across the neighbouring LED:

    [text-overlap] texts[5] 'Red LED 2.0 V 20 mA 0603' [188, 23.5, 347.5, 32.5]
                 × parts[D2] [213, 19.5, 227, 30.5]

548C5 then measured that the island's branches all hang off the one chain
(`ctx.chain == ['U1']`), so widening the single column's pitch either leaves the
row in the neighbour or pushes a seat past `NEAR_LIMIT = 300`; the probe that
did compile injected `x=210/top=115/row=40` by hand and is **not** a generator.
This file pins the *generator* contract (548C6): the seats must be computed from
the real text boxes, symbol bodies, pin tips and the existing channel/grid, and
the island must come out with a legal candidate that keeps its grammar.

What is pinned here, and what is deliberately not:

* the positive: at least one candidate, every candidate passes the independent
  gates (`readability.check` hard violations empty, `check_grammar` findings
  empty), the drawing's own netlist is the spec's (26 nets, one node each, no
  short, no undrawn pin), and all ten reference rows and ten value rows are
  printed whole — no pinned coordinate, no pinned geometry fingerprint, no
  pinned candidate count beyond "at least one";
* zero movement: the unrenamed island and 548C's long-designator island (B1)
  keep the exact geometry this worktree draws for them, because their seats
  already hold their text and no two-dimensional assignment may fire there;
* the boundaries that must survive: a page frame too small for the island, a
  near budget nothing can meet, a second shunt on one host pin, and a served
  shunt's same-row seat are all still answered with a structured refusal or the
  unchanged seat — never with an overlapping `ok=True`.

The last two reuse the existing 543E/543E-2 fixtures rather than restating
them: a boundary control is only meaningful if it measures the same geometry
the owning file measures.
"""

from __future__ import annotations

import copy
import dataclasses
import math
from collections import Counter

import test_543e2_service_siblings as e2_543
import test_543e_perturbations as e543
import test_547_repeated_shunts as m547
from test_548c4_text_label_repair import (
    BASELINE_GEOMETRY,
    LONG_GEOMETRY,
    _drawn_netlist,
    _module_view,
    _profiles,
)
from test_548c5_text_pitch import LONG_VALUES

from boardwise.engines import drawcompiler as dc
from boardwise.engines import readability as rd
from boardwise.engines.grammar.base import SAME_ROW, RelativeConstraint

#: The island's own size, stated so a silent input drift fails here and not as a
#: puzzle further down.
ISLAND_PARTS = 10
ISLAND_NETS = 26

#: What `ic-periphery` states about this island's branches: each of the nine
#: branch parts is `near` the core and on the side its own pin leaves by. They
#: are the relations a two-dimensional seat could revoke by moving a branch to a
#: free row — the reason this file counts them instead of trusting "no findings"
#: (an empty constraint set would make the check vacuous).
NEAR_CONSTRAINTS = 9
SIDE_CONSTRAINTS = {"left-of": 2, "right-of": 6}

_CACHE: dict[tuple, tuple] = {}


def _island(long_values: bool, **budget_kwargs):
    """``(result, circuit, presentation, book)`` for the 547A mcu island.

    ``budget_kwargs`` is handed to `drawcompiler.CompileBudget` unchanged; only
    the boundary controls below pass any. Compiled once per shape: a compile is
    deterministic, and the cache is what keeps this file to a handful of them.
    """
    key = (long_values, tuple(sorted(budget_kwargs.items())))
    if key not in _CACHE:
        circuit_payload = copy.deepcopy(m547._circuit())
        presentation_payload = copy.deepcopy(m547._presentation())
        if long_values:
            for part in circuit_payload["parts"]:
                if part["id"] in LONG_VALUES:
                    part["value"] = LONG_VALUES[part["id"]]
        circuit, presentation = _module_view(circuit_payload, presentation_payload)
        book = _profiles()
        budget = dc.CompileBudget(**budget_kwargs) if budget_kwargs else None
        _CACHE[key] = (
            dc.compile(circuit, presentation, book, budget),
            circuit,
            presentation,
            book,
        )
    return _CACHE[key]


def _refused(result) -> str:
    """The rendered refusal, with the assertion that there is one to read."""
    assert not result.ok, "the compiler returned a candidate where it must refuse"
    assert result.candidates == []
    assert result.failures, "a refusal that names no reason is not a refusal"
    return result.render_failures()


# --------------------------------------------------------------- the positive

def test_the_long_value_island_draws_a_legal_candidate():
    """B2's contract: at least one candidate, and no candidate bought by a
    broken drawing. The generator may choose any legal seats — no coordinate,
    geometry fingerprint or candidate count is pinned here."""
    result, spec, _presentation, _book = _island(True)
    assert result.ok, result.render_failures()
    assert result.failures == []

    assert len(spec.parts) == ISLAND_PARTS
    assert len(spec.nets) == ISLAND_NETS
    assert len(result.candidates) >= 1
    for plan in result.candidates:
        for part in spec.parts:
            assert plan.part(part.id) is not None, f"{part.id} is not placed"


def test_every_long_value_candidate_passes_both_independent_gates():
    """The two gates are asked separately, from the plan and the two documents:
    the readability gate has no hard violation, and the grammar — re-bound
    independently — finds **nothing new**. The one finding this module view
    already carries on the one-column page (the 3V3 power-flag obligation,
    548C2①'s, outside this batch) is pinned by kind and object, so a
    two-dimensional seat that broke a relation or an obligation — or that added a
    second missing-row finding — fails here."""
    result, spec, presentation, book = _island(True)
    assert result.ok, result.render_failures()

    binding = dc.bind_grammar(spec, presentation, book)
    assert binding.ok
    kinds = Counter(item.kind for item in binding.constraints)
    assert kinds["near"] == NEAR_CONSTRAINTS, (
        "the island's near relations changed, so the check below is measuring "
        "something else: " + repr(kinds))
    for kind, count in SIDE_CONSTRAINTS.items():
        assert kinds[kind] == count, (
            f"the island's {kind} relations changed: " + repr(kinds))

    # What the grammar finds is measured **against the one-column page**: this
    # module view prints no power flag at all, so the unrenamed 547A island's own
    # candidate already carries `[grammar-obligation-missing] 3V3`. That one
    # finding is pinned **by kind and by object** rather than compared as an
    # arbitrary set — 548C2① owns it and is outside this batch — and the
    # two-dimensional seats may then add nothing at all on top of it.
    baseline_result, baseline_spec, baseline_presentation, baseline_book = _island(False)
    baseline_findings = dc.check_grammar(
        baseline_result.candidates[0], baseline_spec, baseline_presentation,
        baseline_book,
    )
    assert [item.kind for item in baseline_findings] == [dc.KIND_OBLIGATION_MISSING], (
        "the one-column island's grammar findings changed; this file pins the "
        "single known module-level 3V3 power-flag obligation (548C2①, outside "
        "this batch): "
        + repr([item.render() for item in baseline_findings]))
    known = baseline_findings[0]
    assert any("3V3" in name for name in known.objects), known.render()
    assert "power flag" in known.detail, known.render()

    for plan in result.candidates:
        checked = rd.check(plan, spec, presentation, book)
        assert [item.render() for item in checked.hard_violations] == []
        assert checked.ok
        findings = dc.check_grammar(plan, spec, presentation, book)
        assert [(item.kind, item.objects) for item in findings] == [
            (known.kind, known.objects)
        ], (
            "the two-dimensional seats changed what the grammar finds: "
            + repr([item.render() for item in findings]))


def test_every_long_value_candidate_draws_the_specs_own_netlist():
    """The picture's own geometry, re-derived with `readability.derive_netlist`
    (which consults no spec): each of the 26 nets is one node, no node carries
    two nets, and no declared pin is missing from the drawing."""
    result, spec, _presentation, book = _island(True)
    assert result.ok, result.render_failures()

    for plan in result.candidates:
        _derived, split, undrawn, shorts = _drawn_netlist(spec, plan, book)
        assert undrawn == []
        assert {net: count for net, count in split.items() if count != 1} == {}
        assert shorts == {}
        assert len(split) == ISLAND_NETS


def test_every_long_value_row_is_printed_whole():
    """No shortening, abbreviation, wrapping, hiding or side-splitting: each
    candidate prints exactly one reference row per part and exactly the spec's
    value rows, character for character."""
    result, spec, _presentation, _book = _island(True)
    assert result.ok, result.render_failures()

    for plan in result.candidates:
        references = [text.text for text in plan.texts if text.kind == "reference"]
        values = [text.text for text in plan.texts if text.kind == "value"]
        assert Counter(references) == Counter(part.id for part in spec.parts), (
            "the reference rows are not the parts' own designators: "
            + repr(references))
        assert Counter(values) == Counter(
            part.value for part in spec.parts if part.value), (
            "the value rows are not the spec's own lines: " + repr(values))
        assert len(references) == ISLAND_PARTS
        assert len(values) == ISLAND_PARTS

        printed = {text.text for text in plan.texts}
        printed |= {label.text for label in plan.labels}
        printed |= {symbol.text for symbol in plan.power_symbols
                    if getattr(symbol, "text", "")}
        missing = [part.id for part in spec.parts if part.id not in printed]
        missing += [part.value for part in spec.parts
                    if part.value and part.value not in printed]
        assert missing == [], f"rows the drawing never prints whole: {missing}"


# ------------------------------------------------------------ zero movement

def test_the_unrenamed_island_has_not_moved():
    """547A keeps the drawing it had: one candidate, the same geometry. Nothing
    about the two-dimensional seats may fire on a page whose seats already hold
    their text."""
    result, spec, _presentation, _book = _island(False)
    assert result.ok, result.render_failures()
    assert len(result.candidates) == 1
    plan = result.candidates[0]
    assert plan.geometry_sha256() == BASELINE_GEOMETRY, (
        "the unrenamed 547A island moved: " + plan.geometry_sha256())
    assert sorted(part.id for part in spec.parts) == sorted(m547._MCU_PARTS)


def test_the_long_designator_island_has_not_moved():
    """548C's B1 island (long designators, short value rows) was repaired by
    548C4 and is measured today as one candidate at a fixed geometry. Its seats
    hold their own text, so the same zero-move argument applies to it."""
    import test_548c4_text_label_repair as c4

    result, _spec, _presentation, _book = c4._island(True)
    assert result.ok, result.render_failures()
    assert len(result.candidates) == 1
    plan = result.candidates[0]
    assert plan.geometry_sha256() == LONG_GEOMETRY, (
        "the long-designator B1 island moved: " + plan.geometry_sha256())


# ------------------------------------------------------- boundaries and seats

def test_a_page_frame_that_cannot_hold_the_island_is_refused():
    """The seats may not buy a candidate by leaving the stated page. The island
    states what it needs in the same units the compiler measures, so a 200x200
    frame is refused rather than drawn out of bounds."""
    result, _spec, _presentation, _book = _island(
        True, page_box=(-100.0, -100.0, 100.0, 100.0))
    rendered = _refused(result)
    assert "smallest legal layout" in rendered, rendered
    assert "stated region" in rendered, rendered


def test_a_near_budget_nothing_can_meet_is_still_refused():
    """`NEAR_LIMIT` is a hard boundary, not a target the seats may trade away:
    with a one-unit budget the branches cannot be near their host, and the
    refusal is the relation's own, named."""
    result, _spec, _presentation, _book = _island(True, near_limit=1.0)
    rendered = _refused(result)
    assert "near(" in rendered, rendered
    assert "not honoured" in rendered, rendered


def test_a_second_shunt_on_one_host_pin_is_still_a_named_refusal():
    """543E-2's boundary, measured on its own fixture: a later shunt on the same
    host pin may not share the first shunt's origin. There is no legal
    perpendicular seat here, so the page is refused by name — never returned as
    an overlapping `ok=True` by a two-dimensional seater."""
    _circuit, _presentation, result = e2_543._add_c5_result()
    assert not result.ok
    assert result.pages == []
    failure = result.failures[0]
    assert failure.category == "layout-unsat"
    assert "C5" in failure.detail
    assert "U1.15" in failure.detail
    assert "first shunt's origin" in failure.detail


def test_a_served_shunt_still_sits_on_its_host_row():
    """The same-row / same-line relation a served shunt has today (543E-1): a
    straight 30-unit run along the host pin's own row. A two-dimensional seater
    that moved branches to free rows would show up here first."""
    circuit = e543._circuit()
    page = e543._first_page(
        e543._compile(circuit, e543._presentation(), e543._book()))
    service = e543._service(page, "C4", "15", "VCC", e543._book())
    assert service["manhattan"] == 30.0
    assert service["same_row"] and service["straight"]
    assert service["cap_point"][1] == service["host_point"][1]
    assert service["cap_point"][0] != service["host_point"][0]


# ---------------------------- the pass's own controls (548C6, from the review)

def _prepared(declared=None):
    """A real `_Context` for the long-value island, through bind → prepare.

    ``declared`` is an optional :class:`RelativeConstraint` added to the binding
    **before** `_prepare`, so the same-line relation is the grammar's and
    `_branch_lane_groups` fills `ctx.lane_groups` on the production path —
    nothing here writes that membership by hand.
    """
    circuit_payload = copy.deepcopy(m547._circuit())
    presentation_payload = copy.deepcopy(m547._presentation())
    for part in circuit_payload["parts"]:
        if part["id"] in LONG_VALUES:
            part["value"] = LONG_VALUES[part["id"]]
    circuit, presentation = _module_view(circuit_payload, presentation_payload)
    book = _profiles()
    binding = dc.bind_grammar(circuit, presentation, book)
    assert binding.ok
    if declared is not None:
        binding = dataclasses.replace(
            binding, constraints=binding.constraints + (declared,))
    prepare = dc._prepare(
        circuit, presentation, binding, book, dc.CompileBudget())
    assert prepare.context is not None, prepare.failures
    return prepare.context


def _ladder(ctx):
    """The constructive layout of the first variant, as ``(origins, poses, residue)``."""
    origins, poses, residue = dc._chain_and_shelf_layout(
        ctx, dc._variants(ctx)[0])
    return dict(origins), dict(poses), residue


def _on_run(point, start, end):
    """Is `point` on the straight run ``start -> end`` (the dodge's own ruler)?"""
    (px, py), (ax, ay), (bx, by) = point, start, end
    cross = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
    if abs(cross) > 1e-6:
        return False
    return (min(ax, bx) - 1e-6 <= px <= max(ax, bx) + 1e-6
            and min(ay, by) - 1e-6 <= py <= max(ay, by) + 1e-6)


def test_a_declared_same_row_group_is_left_to_the_bay_and_the_alignment():
    """When the grammar has already declared a same-line relation between two of a
    group's members, the two-dimensional seat must not touch that group:
    `_share_one_bay` and `_align_branch_lanes` own it (the pass's own guard).

    The control is the **same island without the declaration**: there the seat
    does move the group, which is what proves the guard — not the trigger — is
    what stopped it. The declaration travels the production path
    (`RelativeConstraint` → `_prepare` → `ctx.lane_groups`)."""
    plain = _prepared()
    plain.two_dimensional_seats = False
    plain_off, _poses, _residue = _ladder(plain)
    plain.two_dimensional_seats = True
    plain_on, _poses, _residue = _ladder(plain)
    moved = sorted(p for p in plain_on if plain_on[p] != plain_off[p])
    assert len(moved) >= 2, (
        "the trigger itself changed, so this control measures nothing: " + repr(moved))

    declared = _prepared(declared=RelativeConstraint(
        kind=SAME_ROW, subject="D1", object="D2",
        reason="548C6 control: an explicit same-row between two siblings"))
    assert "D1" in declared.lane_groups and "D2" in declared.lane_groups, (
        "the declaration never reached ctx.lane_groups: "
        + repr(declared.lane_groups))
    declared.two_dimensional_seats = False
    declared_off, _poses, _residue = _ladder(declared)
    declared.two_dimensional_seats = True
    declared_on, _poses, _residue = _ladder(declared)
    assert declared_on == declared_off, (
        "the two-dimensional seat moved a declared same-row group: "
        + repr(sorted(p for p in declared_on
                      if declared_on[p] != declared_off[p])))


def test_a_foreign_pin_on_the_new_run_is_dodged_or_the_group_rolls_back():
    """114/117① re-run on the **new** root (548C6): a row seat moves the endpoint
    of the run the ladder dodges, so the pass must dodge again.

    A real part of the island (C1) is put with one pin tip exactly on a member's
    straight run and the group is seated twice, with and without it. Both legal
    outcomes are pinned: either the seat is taken — and the foreign pin is no
    longer on any run, nothing overlaps and every member is still inside `near` —
    or the whole group is rolled back and its seats stand unchanged. A half-
    applied or illegal seat fails both."""
    ctx = _prepared()
    seen: dict = {}
    original = dc._share_one_bay

    def record(*args, **kwargs):
        # observation only: record the rungs the ladder handed the bay pass.
        seen["rungs"] = dict(args[4])
        return original(*args, **kwargs)

    dc._share_one_bay = record
    try:
        origins, poses, residue = dc._chain_and_shelf_layout(
            ctx, dc._variants(ctx)[0])
    finally:
        dc._share_one_bay = original
    ladder = dict(origins)
    poses = dict(poses)
    rungs = seen["rungs"]
    boxes = {p: dc._part_box(ctx.profile(p), poses[p]) for p in ctx.slots}

    seated_origins = dict(ladder)
    seated = dc._seat_branch_stack(
        ctx, seated_origins, poses, boxes, dict(rungs), residue)
    assert len(seated) >= 4, "the trigger changed: " + repr(sorted(seated))
    member = max(seated, key=lambda p: abs(seated_origins[p][0] - ladder[p][0]))
    shared = rungs[member].shared
    anchor = rungs[member].anchor
    root = (seated_origins[member][0] + (shared[0] if shared else 0.0),
            seated_origins[member][1] + (shared[1] if shared else 0.0))
    # A point **on** the run, a fifth of the way out: far enough from the owner's
    # own pin column to stand a part, close enough that the part's body clears
    # both the core and the new rows.
    point = (anchor[0] + (root[0] - anchor[0]) * 0.2,
             anchor[1] + (root[1] - anchor[1]) * 0.2)
    foreign = {p: origin for p, origin in ladder.items() if p != "C1"}
    placed_pin = None
    for token in ("1", "2"):
        local = dc._pin_local(ctx, "C1", token, poses)
        if local is None:
            continue
        origin = (point[0] - local[0], point[1] - local[1])
        box = dc._part_box(ctx.profile("C1"), poses["C1"], origin)
        if any(
            dc._overlaps(box, dc._part_box(ctx.profile(other), poses[other],
                                          ladder[other]))
            for other in ladder if other != "C1"
        ):
            continue
        foreign["C1"] = origin
        placed_pin = token
        break
    assert placed_pin is not None, "no legal place for the foreign pin"
    middle = tuple(_pin for _pin in (point,))[0]
    before = dict(foreign)
    second = dc._seat_branch_stack(
        ctx, foreign, poses, boxes, dict(rungs), residue)

    if second:
        ids = sorted(foreign)
        for index, here in enumerate(ids):
            box = dc._part_box(ctx.profile(here), poses[here], foreign[here])
            for there in ids[index + 1:]:
                assert not dc._overlaps(
                    box, dc._part_box(ctx.profile(there), poses[there],
                                      foreign[there])), (here, there)
        for part_id in second:
            own = rungs[part_id].shared
            point = (foreign[part_id][0] + (own[0] if own else 0.0),
                     foreign[part_id][1] + (own[1] if own else 0.0))
            start = rungs[part_id].anchor
            assert not _on_run(middle, start, point), (
                "the seat kept the foreign pin on its run: " + part_id)
            assert math.hypot(point[0] - start[0], point[1] - start[1]) <= (
                ctx.budget.near_limit)
        assert foreign[member] != ladder[member], "the dodge never moved the seat"
    else:
        for part_id in rungs:
            assert foreign[part_id] == before[part_id], (
                "a refused group must keep the ladder's answer: " + part_id)


# ------------------------- the tail's far end (548C6R, from the tail audit)

def _cross_net_pin_points(ctx, poses, origins):
    """Every page point carrying pin tips of **more than one** declared net.

    Written out here instead of read from the compiler, so the test cannot agree
    with a wrong compiler: two pin tips on one coordinate are one node
    (`readability._derive` unions by point — 117①), which is a short this file
    may not accept as a seat.
    """
    by_point: dict[tuple[float, float], list[tuple[str, str]]] = {}
    for part_id in sorted(ctx.slots):
        if part_id not in origins:
            continue
        nets = dc._part_nets(ctx.circuit, part_id)
        for pin in ctx.profile(part_id).pins:
            point = dc._pin_point(ctx, part_id, pin.number, poses, origins)
            if point is None:
                continue
            net = nets.get(pin.number) or nets.get(pin.name, "")
            by_point.setdefault((round(point[0], 4), round(point[1], 4)),
                                []).append((f"{part_id}.{pin.number}", net))
    return {point: pins for point, pins in by_point.items()
            if len({net for _, net in pins}) > 1}


def _foreign_pins_on(ctx, poses, origins, part_id, start, end):
    """Foreign pin tips on ``start -> end``, this branch's own nets excluded.

    The dodge's own ruler (114/117①): per **pin**, not per part, and a pin on a
    net this branch also draws is not foreign.
    """
    own = set(dc._part_nets(ctx.circuit, part_id).values())
    found = []
    for other in sorted(ctx.slots):
        if other == part_id or other not in origins:
            continue
        nets = dc._part_nets(ctx.circuit, other)
        for pin in ctx.profile(other).pins:
            if (nets.get(pin.number) or nets.get(pin.name, "")) in own:
                continue
            point = dc._pin_point(ctx, other, pin.number, poses, origins)
            if point is None:
                continue
            if dc._on_polyline(point, (start, end)):
                found.append(f"{other}.{pin.number}")
    return found


def _branch_span(ctx, poses, rungs, origins, part_id):
    """``(anchor, shared root, other pin tip)`` for a placed branch."""
    slot = ctx.slots[part_id]
    shared = dc._pin_local(ctx, part_id, slot.pin_shared, poses)
    other = dc._pin_local(ctx, part_id, slot.pin_other, poses)
    origin = origins[part_id]
    root = (origin[0] + shared[0], origin[1] + shared[1])
    return (rungs[part_id].anchor, root,
            (origin[0] + other[0], origin[1] + other[1]))


def test_a_foreign_pin_on_the_new_tail_is_dodged_or_the_group_rolls_back():
    """548C6R: 117①'s **trail**, re-measured on the two-dimensional seat.

    The run a branch draws is not the leg from its owner's pin to its shared pad
    only: past that pad the branch's **other** pin lands 40 units further out
    (0603's two tips), and a foreign pin tip *there* is the same coordinate
    collapse 117① is about (`C7.2` on `T1.A1`).

    The seat dodges the root it computed and the dodge's trail walk is bounded by
    the part's own reach, so it can come back with the tip still occupied. The
    pass must then not keep the seat: measured on this island, the unguarded
    `S4` seat at `(160, -55)` puts its other pad on `(180, -55)` — exactly where
    a real `C1.2`/`R1.2` (GND) stands — and all six members were seated anyway.

    Both legal outcomes are pinned and neither is free: if the seat is taken, no
    cross-net pin point may exist anywhere and no foreign pin may lie on any
    member's leg or tail; if it is not, the **whole** group keeps the ladder's
    answer. A test that accepted either outcome unconditionally would pass on
    the compiler that produced the coincidence.
    """
    ctx = _prepared()
    seen: dict = {}
    original = dc._share_one_bay

    def record(*args, **kwargs):
        seen["rungs"] = dict(args[4])
        return original(*args, **kwargs)

    dc._share_one_bay = record
    try:
        origins, poses, residue = dc._chain_and_shelf_layout(
            ctx, dc._variants(ctx)[0])
    finally:
        dc._share_one_bay = original
    ladder = dict(origins)
    poses = dict(poses)
    rungs = seen["rungs"]
    boxes = {p: dc._part_box(ctx.profile(p), poses[p]) for p in ctx.slots}

    reference = dict(ladder)
    assert dc._seat_branch_stack(
        ctx, reference, poses, boxes, dict(rungs), residue), (
        "the two-dimensional seat no longer fires on this island, so this "
        "control measures nothing")

    cases = 0
    for member in ("S2", "S3", "S4"):
        # These three draw 3V3 on the pad past their shared one, and C1.2/R1.2
        # are GND: a tip coincidence here is a **cross-net** one. D1/D2's other
        # pad is GND too, so they cannot stand in for this case.
        anchor, root, tip = _branch_span(ctx, poses, rungs, reference, member)
        assert _on_run(tip, root, tip) and tip != root
        for foreign, token in (("C1", "2"), ("R1", "2")):
            local = dc._pin_local(ctx, foreign, token, poses)
            origin = (tip[0] - local[0], tip[1] - local[1])
            if any(
                dc._overlaps(
                    dc._part_box(ctx.profile(foreign), poses[foreign], origin),
                    dc._part_box(ctx.profile(other), poses[other],
                                 reference[other]))
                for other in ctx.slots if other != foreign
            ):
                continue      # no real part can stand with a pin tip there
            cases += 1
            trial = dict(ladder)          # the pass's own entry point
            trial[foreign] = origin
            before = dict(trial)          # the planted part is the test's, not the pass's
            seated = dc._seat_branch_stack(
                ctx, trial, poses, boxes, dict(rungs), residue)
            if seated:
                bad = _cross_net_pin_points(ctx, poses, trial)
                assert not bad, (
                    f"{member}: the seat was taken with {foreign}.{token} on its "
                    f"tail tip {tip} and kept a cross-net pin point: {bad}")
                for part_id in seated:
                    a, r, t = _branch_span(ctx, poses, rungs, trial, part_id)
                    hits = _foreign_pins_on(ctx, poses, trial, part_id, a, r)
                    assert not hits, (
                        f"the seat kept a foreign pin on {part_id}'s run: {hits}")
                    hits = _foreign_pins_on(ctx, poses, trial, part_id, r, t)
                    assert not hits, (
                        f"the seat kept a foreign pin on {part_id}'s tail "
                        f"({r} -> {t}): {hits}")
            else:
                for part_id in before:
                    assert trial[part_id] == before[part_id], (
                        "a refused group must keep the ladder's answer: "
                        + part_id)
    assert cases >= 2, (
        f"only {cases} tail construction(s) were reachable: the control went "
        "vacuous")
