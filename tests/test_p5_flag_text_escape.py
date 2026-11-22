"""548D3D-H4, page-wide half: the pads that really carry a flag keep their run.

548D3D-H4 taught ``_part_texts`` to keep a part's **own** rows out of its own
horizontal pins' first escape run, but only on a `localSeats` page: a page-wide
reserve of every pin regressed 26 pages (h3 sec.6). The narrow statement that
reserve was standing in for is this batch's subject — a pad that is actually
given a **flag** needs the :data:`FLAG_LEAD` run it leaves on
(:func:`_flag_anchor`, 069 sec.10), so a text row printed across it costs that
pad every rung of its ladder. Board2 P5 measured it on the real page: U30.36's
right-hand run sat under the part's own value row and U30.9's left-hand run
under C30's, and the full ``PWR-+3V3`` profile had no candidate left.

What this file pins:

* :func:`_flag_escape_bands` lists every pad of a net the expressions decided to
  express as a **flag**, and every pad :func:`_wire_flag_seats` enumerates for a
  **wire-style** rail's own symbol (548D3D-H5: that symbol is seated after the rows
  have landed, so nothing else reserved its pad), and nothing else: a signal drawn
  as a wire and a flag the library has no profile for add no band. A **vertical**
  pad's band is the run's own strip — ``x ± FLAG_CLEARANCE``, ``y = tip … far`` —
  the counterpart of the horizontal ``y ± FLAG_CLEARANCE`` box, and R67 is why it
  exists: the E MCU seats ``R67.1`` at ``(65, 0)`` escaping ``(0, +1)`` while
  ``C73``'s free value row prints at ``61.5, -1.5 - 98.5, 7.5`` straight across the
  pad row, so every rung of the up ladder dies in the lead's span test and length
  cannot help;
* on a hand-written MCU page with a four-member ``3V3`` (above `high_fanout`, so
  a flag at every pad) the rows the historical ladder prints really do cross the
  pads' escape run, and the walls the production build hands ``_part_texts``
  keep them off it — the pads' own :data:`FLAG_LEAD` run is then free and
  :func:`_flag_anchor` reaches it;
* on the R67-shaped page a **neighbour's** free row is the wall: without the
  vertical band the row prints across the pad row and the up lead has no span,
  with it the row steps to its other side and the same :func:`_flag_anchor` call
  reaches the 30-unit run;
* a page whose rails are local **wires** (three members) reserves exactly those
  rails' own seats — the run each symbol hangs on — and the no-band input keeps the
  historical right-hand rung byte for byte; a **signal** wire adds nothing.

The geometry is hand-written and the escape band is recomputed here from the
symbol's own direction and the placement's pose — never read back from the
helper's output. Full-page acceptance (the readability gate, page frame, ladder)
is not this file's claim; it grades the text/flag-pad corridor only.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import test_548d_cross_side_host as h3  # noqa: E402

from boardwise.core.circuitspec import CircuitSpec  # noqa: E402
from boardwise.core.presentationspec import PresentationSpec  # noqa: E402
from boardwise.core.symbolprofile import SymbolProfile, SymbolPose  # noqa: E402
from boardwise.engines import drawcompiler as dc  # noqa: E402

BODY = (-60.0, -40.0, 60.0, 60.0)
#: four members > `dc.HIGH_FANOUT`, so the rail is a flag at every pad; the
#: three-member variant is 053 sec.7's local wire and must stay untouched.
FLAG_MEMBERS = ["U1.1", "U1.2", "C1.1", "C2.1"]
WIRE_MEMBERS = ["U1.1", "U1.2", "C1.1"]
ORIGINS = {"U1": (0.0, 0.0), "C1": (-100.0, -140.0), "C2": (100.0, -140.0)}


def _pin(number, tip, direction):
    return h3._pin(number, tip, direction)


def _book(*, power_flag: bool = True) -> dict:
    book = {
        "XU": SymbolProfile.from_dict(copy.deepcopy(h3._symbol("XU", BODY, [
            _pin("1", (70.0, 50.0), "right"),
            _pin("2", (70.0, 0.0), "right"),
            _pin("3", (70.0, -25.0), "right"),
            _pin("4", (70.0, -50.0), "right"),
            _pin("5", (-70.0, 10.0), "left"),
        ]))),
        "C0402": SymbolProfile.from_dict(copy.deepcopy(h3._symbol(
            "C0402", (-8.0, -12.0, 8.0, 12.0), [
                _pin("1", (0.0, 40.0), "up"),
                _pin("2", (0.0, -40.0), "down")]))),
        "PWR-GND": SymbolProfile(
            symbol_ref="PWR-GND", title="PWR-GND",
            body=(-10.0, 0.0, 10.0, -19.0), pins=[]),
    }
    if power_flag:
        book["PWR-3V3"] = SymbolProfile(
            symbol_ref="PWR-3V3", title="PWR-3V3",
            body=(-6.0, 0.0, 6.0, 18.0), pins=[])
    return book


def _circuit(members: list[str]) -> CircuitSpec:
    return CircuitSpec.from_dict({
        "parts": [h3._part("U1", "XU", "MCU"), h3._part("C1", "C0402", "100n"),
                  h3._part("C2", "C0402", "1u")],
        "nets": [
            h3._net("3V3", "power", members),
            h3._net("GND", "gnd", ["U1.3", "C1.2", "C2.2"]),
            h3._net("SIG", "signal", ["U1.5"]),
            h3._net("SPARE", "signal", ["U1.4"]),
        ],
    })


def _spec() -> PresentationSpec:
    return PresentationSpec.from_dict({
        "grammarRef": "ic-periphery",
        "modules": [{"id": "host", "parts": ["U1", "C1", "C2"],
                     "role": "host island", "grammarRef": "ic-periphery",
                     "core": "U1"}],
    })


def _context(members: list[str], *, power_flag: bool = True) -> dc._Context:
    circuit, spec, book = _circuit(members), _spec(), _book(power_flag=power_flag)
    binding = dc.bind_grammar(circuit, spec, book)
    assert binding.ok, [item.detail for item in binding.failures]
    binding = dc._with_panel_groups(binding, spec, circuit)
    prepared = dc._prepare(
        circuit, spec, binding, book, dc.CompileBudget(max_candidates=4))
    assert prepared.context is not None, [item.detail for item in prepared.failures]
    return prepared.context


def _opt_in(ctx):
    """Explicitly enable the build's native-attr-only seat/text plan."""
    ctx.presentation.text_placement = "native-attr"
    return ctx


def _placement() -> dc._Placement:
    return dc._Placement(
        origins=dict(ORIGINS),
        poses={part: SymbolPose(0, False) for part in ORIGINS},
    )


def _captured_text_walls(ctx, placed, monkeypatch) -> list:
    """The walls the production build hands `_part_texts` on this placement.

    `_build_one_variant` is driven with the placement stated here (no ladder), so
    the page is the same every run; the walls are read off the real call, not
    rebuilt from constants in this file.
    """
    seen: list[list] = []
    original = dc._part_texts

    def spy(inner_ctx, inner_placed, occupied, walls):
        if not seen:
            seen.append(list(walls))
        return original(inner_ctx, inner_placed, occupied, walls)

    monkeypatch.setattr(dc, "_part_texts", spy)
    try:
        dc._build_one_variant(
            ctx, dc._Variant(label="p5-flag-text", scale=1.0, pose_index=0), [],
            placement_override=placed,
        )
    finally:
        monkeypatch.setattr(dc, "_part_texts", original)
    assert seen, "the production build never reached the text pass"
    return seen[0]


def _texts(ctx, placed, walls):
    texts, failure = dc._part_texts(
        ctx, placed, list(ctx.budget.keepouts), list(walls))
    assert failure is None, (failure.category, failure.detail)
    return texts


def _rows(texts, part_id: str):
    rows = [(item.kind, item.text, item.bbox)
            for item in texts if item.part_id == part_id]
    assert rows, f"no text rows for {part_id!r}"
    return rows


def _expected_bands(ctx, placed, members) -> list:
    """Every member's first `FLAG_LEAD` run, recomputed here.

    Direction comes from the symbol pin and the placement's pose, the pad from
    the placement's own transform — the same two facts the drawing is made from —
    and the length/clearance are the compiler's published constants. A horizontal
    run keeps ``y ± FLAG_CLEARANCE`` over its exact ``x`` span; a vertical run is
    the same statement turned a quarter turn (``x ± FLAG_CLEARANCE`` over its
    exact ``y`` span).
    """
    out = []
    for member in members:
        part_id, _, token = member.partition(".")
        pin = next(item for item in ctx.profile(part_id).pins
                   if item.number == token)
        pose, origin = placed.poses[part_id], placed.origins[part_id]
        from boardwise.core.geometry import transform_point

        tip = transform_point(pin.tip[0], pin.tip[1], rotation=pose.rotation,
                              mirror=pose.mirror, ox=origin[0], oy=origin[1])
        unit = {"left": (-1.0, 0.0), "right": (1.0, 0.0),
                "up": (0.0, 1.0), "down": (0.0, -1.0)}[pin.direction]
        ahead = transform_point(pin.tip[0] + unit[0], pin.tip[1] + unit[1],
                                rotation=pose.rotation, mirror=pose.mirror,
                                ox=origin[0], oy=origin[1])
        dx, dy = ahead[0] - tip[0], ahead[1] - tip[1]
        if abs(dx) >= abs(dy):
            east = 1.0 if dx > 0.0 else -1.0
            far = tip[0] + east * dc.FLAG_LEAD
            out.append((min(tip[0], far), tip[1] - dc.FLAG_CLEARANCE,
                        max(tip[0], far), tip[1] + dc.FLAG_CLEARANCE))
        else:
            north = 1.0 if dy > 0.0 else -1.0
            far = tip[1] + north * dc.FLAG_LEAD
            out.append((tip[0] - dc.FLAG_CLEARANCE, min(tip[1], far),
                        tip[0] + dc.FLAG_CLEARANCE, max(tip[1], far)))
    return out


def _wire_bands(ctx, placed, expressions, members=None) -> list:
    """Every rung of the **seat ladder**, as the old reservation listed it.

    The pads are the ones :func:`_wire_flag_seats` enumerates (the production
    ladder, not a list written here), and the run is the shape the ladder reaches
    for first: a straight vertical run off the pad, up for a rail and down for a
    ground, or — for an 088b outlet — the pin's own side. ``members`` restricts
    the list to named pads, which is how the tests state "this rung was *not*
    chosen, so its corridor must not be reserved". The length and clearance are
    the compiler's published constants.
    """
    out = []
    direction_of = {
        "left": (-1.0, 0.0), "right": (1.0, 0.0),
        "up": (0.0, 1.0), "down": (0.0, -1.0),
    }
    for net_id, member, point, profile, _ref, _cls, vertical, _key in (
        dc._wire_flag_seats(ctx, expressions, sorted(expressions))
    ):
        if members is not None and member not in members:
            continue
        part_id, _, token = member.partition(".")
        if vertical:
            natural = (
                -1.0 if dc.flag_glyph_kind(profile) == dc.FLAG_GLYPH_KIND_GND
                else 1.0
            )
            far = point[1] + natural * dc.FLAG_LEAD
            out.append((point[0] - dc.FLAG_CLEARANCE, min(point[1], far),
                        point[0] + dc.FLAG_CLEARANCE, max(point[1], far)))
            continue
        pin = next(item for item in ctx.profile(part_id).pins
                   if item.number == token)
        pose, origin = placed.poses[part_id], placed.origins[part_id]
        from boardwise.core.geometry import transform_point

        tip = transform_point(pin.tip[0], pin.tip[1], rotation=pose.rotation,
                              mirror=pose.mirror, ox=origin[0], oy=origin[1])
        unit = direction_of[pin.direction]
        ahead = transform_point(pin.tip[0] + unit[0], pin.tip[1] + unit[1],
                                rotation=pose.rotation, mirror=pose.mirror,
                                ox=origin[0], oy=origin[1])
        dx, dy = ahead[0] - tip[0], ahead[1] - tip[1]
        if abs(dx) >= abs(dy):
            east = 1.0 if dx > 0.0 else -1.0
            far = tip[0] + east * dc.FLAG_LEAD
            out.append((min(tip[0], far), tip[1] - dc.FLAG_CLEARANCE,
                        max(tip[0], far), tip[1] + dc.FLAG_CLEARANCE))
        else:
            north = 1.0 if dy > 0.0 else -1.0
            far = tip[1] + north * dc.FLAG_LEAD
            out.append((tip[0] - dc.FLAG_CLEARANCE, min(tip[1], far),
                        tip[0] + dc.FLAG_CLEARANCE, max(tip[1], far)))
    return out


def _selected_bands(ctx, placed, expressions, plan=None) -> list:
    """The corridors the **chosen** seats reserve, recomputed here (548D3D-H6).

    One lead strip and one :func:`_flag_box` per seat group, built from the seat's
    own settled lead — the strip keeps ``FLAG_CLEARANCE`` sideways only, exactly
    the shape :func:`_wire_flag_lead_band` states, but this copy is derived from
    the anchor/lead pairs rather than read back from the helper under test.
    """
    from boardwise.core.geometry import transform_point  # noqa: F401

    if plan is None:
        plan = dc._wire_flag_seat_plan(
            ctx, placed, expressions, sorted(expressions))
    out = []
    for seat in plan.values():
        xs = [point[0] for point in seat.lead]
        ys = [point[1] for point in seat.lead]
        if max(xs) - min(xs) <= 1e-9:
            out.append((xs[0] - dc.FLAG_CLEARANCE, min(ys),
                        xs[0] + dc.FLAG_CLEARANCE, max(ys)))
        elif max(ys) - min(ys) <= 1e-9:
            out.append((min(xs), ys[0] - dc.FLAG_CLEARANCE,
                        max(xs), ys[0] + dc.FLAG_CLEARANCE))
        else:
            out.append((min(xs) - dc.FLAG_CLEARANCE,
                        min(ys) - dc.FLAG_CLEARANCE,
                        max(xs) + dc.FLAG_CLEARANCE,
                        max(ys) + dc.FLAG_CLEARANCE))
        out.append(dc._flag_box(seat.profile, seat.rotation, seat.anchor, seat.net))
    return out


def _crossings(rows, bands):
    return [(kind, tuple(box)) for kind, _text, box in rows
            for band in bands if dc._overlaps(box, band)]


def _legacy_rows(ctx, placed, part_id: str):
    """The documented historical answer for this placement: right-hand rung 1."""
    box = dc._part_box(
        ctx.profile(part_id), placed.poses[part_id], placed.origins[part_id])
    lines = [text for _kind, text in dc._part_lines(ctx, part_id)]
    return [(kind, text, tuple(box))
            for (kind, text), box in zip(
                dc._part_lines(ctx, part_id),
                dc._line_boxes(box, lines, "right", 1))]


# =========== 1. the helper's own scope: flag pads, horizontal and vertical, profiled


def test_the_helper_lists_only_real_flag_pads():
    ctx = _context(FLAG_MEMBERS)
    placed = _placement()
    expressions = dc._expressions(ctx, placed)
    assert expressions["3V3"].style == "flag", (
        "premise: four members are above high_fanout, so the rail is flagged")

    bands = dc._flag_escape_bands(ctx, placed, expressions)
    members = [member for member, _point in expressions["3V3"].points]
    expected = _expected_bands(ctx, placed, members)
    plan = dc._wire_flag_seat_plan(ctx, placed, expressions, sorted(expressions))
    selected = _selected_bands(ctx, placed, expressions, plan)
    assert bands == expected + selected, (
        "every flag pad's own first run (four of them) plus the **chosen** "
        f"wire-style seats' corridors: got {bands}, "
        f"expected {expected + selected}")
    assert len(expected) == 4, (
        "the rail's two vertical capacitor pads carry a flag too (R67), so "
        f"their run is a vertical band: {expected}")
    vertical = [box for box in expected
                if box[2] - box[0] == 2 * dc.FLAG_CLEARANCE]
    assert len(vertical) == 2, (
        "a vertical run's band is the strip `x ± FLAG_CLEARANCE` over the run's "
        f"`y` span: {expected}")
    assert all(
        box[3] - box[1] == dc.FLAG_LEAD for box in vertical
    ), f"the vertical band must be the FLAG_LEAD run itself: {vertical}"

    wire = {"3V3": dc._Expression(
        net="3V3", style="wire", points=expressions["3V3"].points,
        reason="this test states a wire expression")}
    wire_plan = dc._wire_flag_seat_plan(ctx, placed, wire, sorted(wire))
    assert wire_plan, "premise: the rail's seat ladder finds a pad"
    wire_bands = dc._flag_escape_bands(ctx, placed, wire)
    assert wire_bands == _selected_bands(ctx, placed, wire, wire_plan), (
        "548D3D-H6: a wire-style rail reserves the run of the pad its seat "
        "**takes** and that flag's box — and nothing else")
    assert len(wire_bands) == 2 * len(wire_plan), (
        f"one lead strip and one flag box per seat group: {wire_bands}")
    ladder_pads = {row[1] for row in dc._wire_flag_seats(
        ctx, wire, sorted(wire))}
    others = _wire_bands(
        ctx, placed, wire, members=ladder_pads - {s.member for s in wire_plan.values()})
    assert others and not any(box in wire_bands for box in others), (
        "the rungs the seat did not take must not be reserved: the old helper "
        f"walled every one of them ({others})")

    # the ground here is drawn as one rail (style wire) and carries one symbol
    # (201A sec.1): its pads reserve the run the symbol is hung on
    assert expressions["GND"].style == "wire"
    assert _wire_bands(ctx, placed, {"GND": expressions["GND"]}), (
        "premise: the three-pad ground rail is stated by one ground symbol")
    gnd = {"GND": expressions["GND"]}
    gnd_plan = dc._wire_flag_seat_plan(ctx, placed, gnd, sorted(gnd))
    assert gnd_plan and dc._flag_escape_bands(ctx, placed, gnd) == (
        _selected_bands(ctx, placed, gnd, gnd_plan)), (
        "a ground rail's one symbol reserves its chosen seat's corridor only")

    # a **signal** drawn as a wire is not a rail and carries no symbol
    signal = {"SIG": dc._Expression(
        net="SIG", style="wire", points=expressions["SIG"].points,
        reason="this test states a wire expression")}
    assert dc._flag_escape_bands(ctx, placed, signal) == [], (
        "a signal wire is not a flag pad and must add no band")
    assert dc._wire_flag_seats(ctx, signal, ["SIG"]) == [], (
        "premise: a signal net has no seat in the wire-style ladder")

    # a library that carries no 3V3 flag falls back to a wire; no band
    no_profile = _context(FLAG_MEMBERS, power_flag=False)
    assert dc._flag_plan(no_profile, "3V3", "power")[0] is None
    assert dc._flag_escape_bands(
        no_profile, placed, {"3V3": expressions["3V3"]}) == [], (
        "a flag the book has no profile for is not a flag pad")


# ==================== 2. the rows step off the run the flag pads need


def test_the_host_rows_step_off_the_flag_escape_run(monkeypatch):
    ctx = _opt_in(_context(FLAG_MEMBERS))
    placed = _placement()
    expressions = dc._expressions(ctx, placed)
    bands = dc._flag_escape_bands(ctx, placed, expressions)
    plan = dc._wire_flag_seat_plan(ctx, placed, expressions, sorted(expressions))
    rail = _selected_bands(ctx, placed, expressions, plan)
    flag_bands = [box for box in bands if box not in rail]
    assert len(flag_bands) == 4, (
        f"premise: four 3V3 flag pads state a run: {bands}")

    walls = _captured_text_walls(ctx, placed, monkeypatch)
    assert walls[len(walls) - len(bands):] == bands, (
        "the build did not hand the flag pads' escape bands to the text pass; "
        f"walls tail is {walls[len(walls) - len(bands):]}")

    legacy_rows = _rows(_texts(ctx, placed, walls[:len(walls) - len(bands)]), "U1")
    assert _crossings(legacy_rows, bands), (
        "premise: the historical ladder no longer prints the host's rows across "
        f"a flag pad's run: {legacy_rows}")

    rows = _rows(_texts(ctx, placed, walls), "U1")
    assert _crossings(rows, bands) == [], (
        "the host's rows still stand on a flag pad's first run, so the pad's "
        f"ladder is still refused: rows {rows}, bands {bands}")

    # and the run is really reachable now: the first rung of each pad's ladder
    # lands on a page with these rows as obstacles
    router = dc._Router(
        grid=5.0, residue=placed.residue,
        boxes=[item.bbox for item in _texts(ctx, placed, walls)],
        bounds=(0.0, 0.0, 800.0, 800.0),
    )
    for member, point in expressions["3V3"].points:
        part_id, _, token = member.partition(".")
        if part_id != "U1":
            continue
        direction = dc._pin_escape(
            ctx.profile(part_id), token, placed.poses[part_id])
        if direction is None or direction[0] == 0.0:
            continue
        _anchor, lead, _hang = dc._flag_anchor(
            router, point, direction, set(), only_length=dc.FLAG_LEAD)
        assert lead is not None, (
            f"the pad {member} still has no room for a {dc.FLAG_LEAD:g}-unit "
            "first run with these rows on the page")


# ====== 3. R67: a vertical flag pad's run, with a neighbour's row across it

#: The R67 shape on a hand-written page: ``F.1`` is a vertical flag pad at the
#: origin; ``N``'s free value row is long enough to print across it (the row's
#: right-hand answer reaches x = 85 from a body at x = -20); ``U1`` is the module
#: core on the same rail so binding accepts the page, and C1–C3 are far members
#: that keep the rail above `high_fanout`.
VERT_ORIGINS = {"U1": (0.0, -400.0), "F": (0.0, 0.0), "N": (0.0, 0.0),
                "C1": (300.0, 0.0), "C2": (400.0, 0.0), "C3": (700.0, -300.0)}


def _vertical_book() -> dict:
    book = _book()
    book["XV"] = SymbolProfile.from_dict(h3._symbol(
        "XV", (-8.0, -90.0, 8.0, -62.0), [_pin("1", (0.0, 0.0), "up")]))
    book["XN"] = SymbolProfile.from_dict(h3._symbol(
        "XN", (-70.0, -11.0, -20.0, 49.0), []))
    book["XR"] = SymbolProfile.from_dict(h3._symbol(
        "XR", (-10.0, -4.0, 10.0, 4.0),
        [_pin("1", (-20.0, 0.0), "left"), _pin("2", (20.0, 0.0), "right")]))
    return book


def _vertical_circuit() -> CircuitSpec:
    return CircuitSpec.from_dict({
        "parts": [
            h3._part("U1", "XU", "MCU"), h3._part("F", "XV", "10k"),
            h3._part("N", "XN", "100nF 0603 C0G"),
            h3._part("C1", "XR", "100n"),
            h3._part("C2", "XR", "1u"), h3._part("C3", "XR", "1u"),
        ],
        "nets": [
            h3._net("3V3", "power", ["F.1", "C1.1", "C2.1", "C3.1", "U1.1"]),
            h3._net("GND", "gnd", ["U1.4"]),
            h3._net("RET", "signal", ["C1.2", "C2.2", "C3.2"]),
            h3._net("SIG", "signal", ["U1.5"]),
            h3._net("SPARE", "signal", ["U1.2", "U1.3"]),
        ],
    })


def _vertical_spec() -> PresentationSpec:
    return PresentationSpec.from_dict({
        "grammarRef": "ic-periphery",
        "modules": [{"id": "host",
                     "parts": ["U1", "F", "N", "C1", "C2", "C3"],
                     "role": "host island", "grammarRef": "ic-periphery",
                     "core": "U1"}],
    })


def _vertical_context() -> dc._Context:
    circuit, spec, book = _vertical_circuit(), _vertical_spec(), _vertical_book()
    binding = dc.bind_grammar(circuit, spec, book)
    assert binding.ok, [item.detail for item in binding.failures]
    binding = dc._with_panel_groups(binding, spec, circuit)
    prepared = dc._prepare(
        circuit, spec, binding, book, dc.CompileBudget(max_candidates=4))
    assert prepared.context is not None, [item.detail for item in prepared.failures]
    return prepared.context


def _vertical_placement() -> dc._Placement:
    return dc._Placement(
        origins=dict(VERT_ORIGINS),
        poses={part: SymbolPose(0, False) for part in VERT_ORIGINS},
    )


def _captured_text_walls_and_build(ctx, placed, monkeypatch):
    """``(walls, built, failure)`` from the one production build of this placement."""
    seen: list[list] = []
    original = dc._part_texts

    def spy(inner_ctx, inner_placed, occupied, walls):
        if not seen:
            seen.append(list(walls))
        return original(inner_ctx, inner_placed, occupied, walls)

    monkeypatch.setattr(dc, "_part_texts", spy)
    try:
        built, failure, _notes = dc._build_one_variant(
            ctx, dc._Variant(label="r67-vertical", scale=1.0, pose_index=0), [],
            placement_override=placed,
        )
    finally:
        monkeypatch.setattr(dc, "_part_texts", original)
    assert seen, "the production build never reached the text pass"
    return seen[0], built, failure


def test_a_vertical_flag_pad_keeps_a_neighbours_row_out_of_its_run(monkeypatch):
    ctx = _opt_in(_vertical_context())
    placed = _vertical_placement()
    expressions = dc._expressions(ctx, placed)
    assert expressions["3V3"].style == "flag", (
        "premise: five members are above high_fanout, so the rail is flagged")
    point = dict(expressions["3V3"].points)["F.1"]
    assert dc._pin_escape(ctx.profile("F"), "1", placed.poses["F"]) == (0.0, 1.0), (
        "premise: F.1 is the page's vertical flag pad")

    bands = dc._flag_escape_bands(ctx, placed, expressions)
    band = (point[0] - dc.FLAG_CLEARANCE, point[1],
            point[0] + dc.FLAG_CLEARANCE, point[1] + dc.FLAG_LEAD)
    assert band in bands, (
        "the vertical flag pad's own run is not in the helper's bands: "
        f"{bands}")

    walls = _captured_text_walls_and_build(ctx, placed, monkeypatch)[0]
    assert walls[len(walls) - len(bands):] == bands, (
        "the build did not hand the vertical flag pad's band to the text pass; "
        f"walls tail is {walls[len(walls) - len(bands):]}")

    # the helper *before* R67 listed no vertical band; dropping this one band
    # from the production walls is the unfixed input, and it must be red
    legacy_walls = [box for box in walls if box != band]
    legacy = _rows(_texts(ctx, placed, legacy_walls), "N")
    assert _crossings(legacy, [band]), (
        "premise: the neighbour's free row no longer prints across the vertical "
        f"pad row: {legacy}")

    rows = _rows(_texts(ctx, placed, walls), "N")
    assert _crossings(rows, [band]) == [], (
        "the neighbour's row still stands on the vertical flag pad's run: "
        f"rows {rows}, band {band}")

    def _router(texts):
        return dc._Router(
            grid=5.0, residue=placed.residue,
            boxes=[item.bbox for item in texts],
            bounds=(0.0, 0.0, 800.0, 800.0),
        )

    _anchor, refused, _hang = dc._flag_anchor(
        _router(_texts(ctx, placed, legacy_walls)), point, (0.0, 1.0), set(),
        only_length=dc.FLAG_LEAD)
    assert refused is None, (
        "premise: with the unfixed walls the vertical pad's 30-unit run must be "
        f"refused, got {_anchor}")

    anchor, lead, _hang = dc._flag_anchor(
        _router(_texts(ctx, placed, walls)), point, (0.0, 1.0), set(),
        only_length=dc.FLAG_LEAD)
    assert lead is not None, (
        f"the vertical flag pad still has no {dc.FLAG_LEAD:g}-unit run with the "
        f"neighbour's row moved off it: anchor {anchor}")
    assert anchor == (point[0], point[1] + dc.FLAG_LEAD)

    # the readability contract this corridor must satisfy (`text-on-wire`, the
    # same box overlap `readability` measures): no production text row may stand
    # on the lead the flag will be drawn on. Full-page grading of this synthetic
    # page is not this file's claim — its distant GND flag trips an unrelated
    # wire-through-body at U1 here; the E page is the page-level attempt.
    run = (min(point[0], anchor[0]), min(point[1], anchor[1]),
           max(point[0], anchor[0]), max(point[1], anchor[1]))
    assert not any(
        dc._overlaps(item.bbox, run) for item in _texts(ctx, placed, walls)
    ), "a production text row still stands on the flag lead's run"


# ============ 4. no flag pad: no band and the historical rows, byte for byte


def test_a_page_whose_rails_are_wires_reserves_their_seats_and_no_more(monkeypatch):
    ctx = _opt_in(_context(WIRE_MEMBERS))
    placed = _placement()
    expressions = dc._expressions(ctx, placed)
    assert expressions["3V3"].style == "wire", (
        "premise: three members are a local rail, drawn as a wire")

    bands = dc._flag_escape_bands(ctx, placed, expressions)
    assert bands, "premise: this page's wire-style rails carry their own symbols"
    plan = dc._wire_flag_seat_plan(ctx, placed, expressions, sorted(expressions))
    assert bands == _selected_bands(ctx, placed, expressions, plan), (
        "a page whose rails are wires reserves exactly the seats those rails take")
    assert len(bands) == 2 * len(plan), (
        f"one lead strip and one flag box per seat group: {bands}")
    rows3 = [row for row in dc._wire_flag_seats(ctx, expressions, sorted(expressions))
             if row[0] == "3V3"]
    assert len(rows3) > 1, f"premise: the rail has a multi-pad ladder: {rows3}"
    assert plan["3V3"].member == rows3[0][1], (
        "premise: the supplying pad (069 sec.7's `_power_flag_pin`) is the first "
        f"rung of the ladder: {rows3[0]}")
    others = _wire_bands(
        ctx, placed, expressions,
        members={row[1] for row in rows3} - {plan["3V3"].member})
    assert others and not any(box in bands for box in others), (
        "548D3D-H6: the rungs the rail did not take are no longer walled off: "
        f"{others} — the over-reservation that starved C72/C76 on the E page")
    walls = _captured_text_walls(ctx, placed, monkeypatch)
    assert walls[len(walls) - len(bands):] == bands, (
        "the build did not hand the rails' bands to the text pass")
    rows = _rows(_texts(ctx, placed, walls[:len(walls) - len(bands)]), "U1")
    assert rows == _legacy_rows(ctx, placed, "U1"), (
        "the no-band input must keep the historical right-hand rung; got "
        f"{rows}")

# ===== 5. 548D3D-R67: a blind first side over a flag band refuses the text part
#
# The bad page below seats ``N``'s rows so tightly that every side of the
# ordinary ladder is blocked, and the historical last resort (``TEXT_SIDES[0]``,
# rung 1) prints the value row straight across ``F.1``'s vertical flag run:
# the row straddles ``y = 0``, exactly the R67 shape. The unfixed tree therefore
# blames the flag pad and reports ``3V3``/``F.1``; the honest subject is the
# part whose rows have no side, ``N``. The good page keeps the same flag pad and
# the same blind row, but leaves one side of ``N`` free, so the refusal must not
# fire and the ordinary production build must still return a candidate.

R67_BAD_ORIGINS = {"U1": (0.0, -80.0), "F": (30.0, 0.0), "N": (0.0, -12.0),
                   "C1": (-150.0, 0.0), "C2": (-50.0, 64.0),
                   "C3": (-50.0, 83.0)}


def _flag_book() -> dict:
    """The vertical page's book without the ground flag.

    The GND flag on this hand-written page trips an unrelated
    ``wire-through-body`` gate; removing its profile turns the one-member GND
    into labels and keeps this file's claim on the text/flag corridor only.
    """
    book = dict(_vertical_book())
    book.pop("PWR-GND", None)
    return book


def _flag_context() -> dc._Context:
    circuit, spec, book = _vertical_circuit(), _vertical_spec(), _flag_book()
    binding = dc.bind_grammar(circuit, spec, book)
    assert binding.ok, [item.detail for item in binding.failures]
    binding = dc._with_panel_groups(binding, spec, circuit)
    prepared = dc._prepare(
        circuit, spec, binding, book, dc.CompileBudget(max_candidates=4))
    assert prepared.context is not None, [item.detail for item in prepared.failures]
    return prepared.context


def _bad_placement() -> dc._Placement:
    return dc._Placement(
        origins=dict(R67_BAD_ORIGINS),
        poses={part: SymbolPose(0, False) for part in R67_BAD_ORIGINS},
    )


def _f_band(ctx, placed, expressions):
    point = dict(expressions["3V3"].points)["F.1"]
    return (point[0] - dc.FLAG_CLEARANCE, point[1],
            point[0] + dc.FLAG_CLEARANCE, point[1] + dc.FLAG_LEAD)


def _n_blocked(ctx, placed, walls):
    """Every side of ``N`` at every standard rung hits a wall on the bad page."""
    box = dc._part_box(
        ctx.profile("N"), placed.poses["N"], placed.origins["N"])
    lines = [text for _kind, text in dc._part_lines(ctx, "N")]
    blocked = [*walls, box]
    free = []
    for rung in range(1, dc.TEXT_ESCALATION_STEPS + 1):
        for side in dc.TEXT_SIDES:
            boxes = dc._line_boxes(box, lines, side, rung)
            if not any(dc._overlaps(candidate, other)
                       for candidate in boxes for other in blocked):
                free.append((side, rung))
    return box, lines, free


def test_a_blind_first_side_over_a_flag_band_refuses_the_text_part(monkeypatch):
    ctx = _opt_in(_flag_context())
    placed = _bad_placement()
    expressions = dc._expressions(ctx, placed)
    assert expressions["3V3"].style == "flag", (
        "premise: five members are above high_fanout, so the rail is flagged")
    band = _f_band(ctx, placed, expressions)
    bands = dc._flag_escape_bands(ctx, placed, expressions)
    assert band in bands, f"premise: F.1's vertical run is a band: {bands}"

    walls, built, failure = _captured_text_walls_and_build(ctx, placed, monkeypatch)
    assert walls[len(walls) - len(bands):] == bands, (
        "the build did not hand F.1's band to the text pass")

    box, lines, free = _n_blocked(ctx, placed, walls)
    assert free == [], (
        "premise: N must have no free side at any standard rung on the bad "
        f"page, but {free} remained free")
    blind = dc._line_boxes(box, lines, dc.TEXT_SIDES[0])
    assert any(dc._overlaps(candidate, band) for candidate in blind), (
        "premise: the historical first-side answer must print N across F.1's "
        f"run; blind {blind}, band {band}")

    assert built is None, "the bad page built a candidate"
    assert failure is not None
    assert failure.category == dc.FAILURE_LAYOUT_UNSAT
    assert failure.subject == "N", (
        "the refusal must name the text part whose rows have no side, not the "
        f"flag pad that inherits the consequence; got subject {failure.subject!r}: "
        f"{failure.detail}")
    assert "first flag run" in failure.detail, failure.detail
    assert f"({band[0]:g}, {band[1]:g})" in failure.detail, failure.detail
    assert "leave one side" in failure.action, failure.action


def test_a_free_side_keeps_the_near_miss_legal_and_builds(monkeypatch):
    ctx = _opt_in(_flag_context())
    placed = _vertical_placement()
    expressions = dc._expressions(ctx, placed)
    band = _f_band(ctx, placed, expressions)
    bands = dc._flag_escape_bands(ctx, placed, expressions)
    assert band in bands

    walls, built, failure = _captured_text_walls_and_build(ctx, placed, monkeypatch)
    box = dc._part_box(
        ctx.profile("N"), placed.poses["N"], placed.origins["N"])
    lines = [text for _kind, text in dc._part_lines(ctx, "N")]
    blind = dc._line_boxes(box, lines, dc.TEXT_SIDES[0])
    assert any(dc._overlaps(candidate, band) for candidate in blind), (
        "premise: the good page's blind row also crosses the band, so only a "
        "free side keeps it legal")

    assert failure is None, (failure.category, failure.subject, failure.detail)
    assert built is not None, "a page with a legal side was refused"
    rows = [(item.kind, item.text, tuple(item.bbox))
            for item in built.plan.texts if item.part_id == "N"]
    assert rows, "N printed no rows on the built page"
    assert _crossings(rows, bands) == [], (
        f"N's rows stand on a flag band: rows {rows}, bands {bands}")


def test_a_fallback_that_misses_every_band_keeps_the_historical_answer(monkeypatch):
    ctx = _opt_in(_flag_context())
    placed = _bad_placement()
    walls, _built, _failure = _captured_text_walls_and_build(
        ctx, placed, monkeypatch)
    box, lines, free = _n_blocked(ctx, placed, list(walls))
    assert free == [], f"premise: a side of N is free: {free}"
    historical = dc._line_boxes(box, lines, dc.TEXT_SIDES[0])
    far = ((1000.0, 1000.0, 1010.0, 1010.0),)
    texts, refusal = dc._part_texts(
        ctx, placed, list(ctx.budget.keepouts),
        dc._FlagBandWalls(walls, far))
    assert refusal is None, (refusal.category, refusal.subject, refusal.detail)
    rows = [(item.kind, item.text, tuple(item.bbox))
            for item in texts if item.part_id == "N"]
    expected = [(kind, text, tuple(candidate)) for (kind, text), candidate
                in zip(dc._part_lines(ctx, "N"), historical)]
    assert rows == expected, (
        "a fallback that misses every flag band must keep the historical "
        f"first-side answer byte for byte; got {rows}, expected {expected}")

# ==== 7. 548D3D-H5: a WIRE-style rail's own flag keeps its run (the +3V3 shape)
#
# Sections 1-3 grade the `flag` style, whose pads the expressions themselves name.
# A rail drawn as a **wire** gets its symbol from `_wire_flag_seats` after the rows
# have landed, so before this batch nothing reserved the pad it hangs on. The
# measured shape is the radar page's `+3V3` shared rail: `C75.1` at (75, 40) sat
# inside its own value row [71.5, 37.5, 93.5, 46.5], and every pair of the declared
# share group walked `inf` — the walk starts inside a text box.
#
# The page below is section 3's, with `3V3` cut to three members: 053 sec.7's local
# rail, so the expression is `wire` and the symbol comes from the seat ladder.

WIRE_RAIL = ["F.1", "C1.1", "U1.1"]


def _wire_rail_circuit() -> CircuitSpec:
    return CircuitSpec.from_dict({
        "parts": [
            h3._part("U1", "XU", "MCU"), h3._part("F", "XV", "10k"),
            h3._part("N", "XN", "100nF 0603 C0G"),
            h3._part("C1", "XR", "100n"), h3._part("C2", "XR", "1u"),
            h3._part("C3", "XR", "1u"),
        ],
        "nets": [
            h3._net("3V3", "power", WIRE_RAIL),
            h3._net("GND", "gnd", ["U1.4"]),
            h3._net("RET", "signal", ["C1.2"]),
            h3._net("AUX", "signal", ["C2.1", "C2.2", "C3.1", "C3.2"]),
            h3._net("SIG", "signal", ["U1.2"]),
            h3._net("SPARE", "signal", ["U1.3"]),
        ],
    })


def _wire_rail_context() -> dc._Context:
    circuit, spec, book = _wire_rail_circuit(), _vertical_spec(), _flag_book()
    binding = dc.bind_grammar(circuit, spec, book)
    assert binding.ok, [item.detail for item in binding.failures]
    binding = dc._with_panel_groups(binding, spec, circuit)
    prepared = dc._prepare(
        circuit, spec, binding, book, dc.CompileBudget(max_candidates=4))
    assert prepared.context is not None, [item.detail for item in prepared.failures]
    return prepared.context


def test_a_wire_rail_flag_keeps_its_pad_out_of_its_own_rows(monkeypatch):
    ctx = _opt_in(_wire_rail_context())
    placed = _vertical_placement()
    expressions = dc._expressions(ctx, placed)
    assert expressions["3V3"].style == "wire", (
        "premise: three members are 053 sec.7's local rail, drawn as a wire")

    ladder = [row for row in dc._wire_flag_seats(ctx, expressions, sorted(expressions))
              if row[0] == "3V3"]
    assert len(ladder) > 1, f"premise: the rail has a multi-pad ladder: {ladder}"
    plan = dc._wire_flag_seat_plan(ctx, placed, expressions, sorted(expressions))
    seat = plan["3V3"]
    assert seat.member in {row[1] for row in ladder}, (
        "the chosen seat is one of the rail's own ladder rungs, not an invention")
    xs = [point[0] for point in seat.lead]
    ys = [point[1] for point in seat.lead]
    band = (min(xs) - dc.FLAG_CLEARANCE, min(ys),
            max(xs) + dc.FLAG_CLEARANCE, max(ys))

    bands = dc._flag_escape_bands(ctx, placed, expressions)
    assert band in bands, (
        f"the chosen seat states no corridor: bands {bands}")

    walls, built, failure = _captured_text_walls_and_build(ctx, placed, monkeypatch)
    assert walls[len(walls) - len(bands):] == bands, (
        "the build did not hand the rail flag's band to the text pass")
    assert failure is None, (failure.category, failure.subject, failure.detail)
    assert built is not None, "the page with the rail's corridor built nothing"

    rows = [(item.kind, item.text, tuple(item.bbox))
            for item in built.plan.texts]
    assert _crossings(rows, bands) == [], (
        f"a production row still stands on a rail flag's run: rows {rows}")
    # the end state, measured against the corridor recomputed here rather than
    # against the helper's own list: the seat pad must be free on the landed page
    assert _crossings(rows, [band]) == [], (
        "the landed page prints a row across the wire-style rail's own run; "
        f"rows {rows}, run {band}")
    # the over-reservation this batch removes: the rungs the seat did not take
    assert len(_wire_bands(ctx, placed, expressions)) > len(bands), (
        "premise: the old helper listed every ladder rung, the new one lists the "
        "chosen seats")

# ====== 8. 548D3D-H6: the seat is chosen, not the whole ladder ======
#
# The old wire-style reservation walled off every rung of the seat ladder, which on
# the E page left C72/C76 no free side at all. The batch's rule is narrower: one
# corridor per seat group, for the pad the ladder really reaches. Two properties
# pin it besides section 1's, and each is red under a different regression:
#
# * a **blocked** first rung must move the choice (and the corridor) to the next
#   pad that holds a flag — never "the first pad anyway", never "all of them";
# * the seat pass must **take the planned rung**, not run its own ladder from the
#   top — otherwise the corridor was reserved for a symbol that stands elsewhere.


def test_a_blocked_first_rung_moves_the_seat_and_only_the_new_rung_is_reserved():
    ctx = _context(WIRE_MEMBERS)
    placed = _placement()
    expressions = dc._expressions(ctx, placed)
    ladder = [row for row in dc._wire_flag_seats(
        ctx, expressions, sorted(expressions)) if row[0] == "3V3"]
    assert len(ladder) >= 2, f"premise: the rail has a multi-pad ladder: {ladder}"
    first = ladder[0]
    solids, bodies = dc._placed_flag_obstacles(ctx, placed)
    # a pin-sized wall on the first rung's own pad: every lead out of that tip
    # crosses it, so the production ladder cannot seat the flag there
    blocker = (first[2][0] - 4.0, first[2][1] - 4.0,
               first[2][0] + 4.0, first[2][1] + 4.0)
    plan = dc._wire_flag_seat_plan(
        ctx, placed, expressions, sorted(expressions),
        [*solids, blocker], [*bodies, blocker])
    assert plan["3V3"].member != first[1], (
        "a blocked first rung must move the seat down the ladder: "
        f"{plan['3V3'].member} is still the blocked pad {first[1]}")
    bands = dc._flag_escape_bands(
        ctx, placed, expressions,
        solids=[*solids, blocker], bodies=[*bodies, blocker], plan=plan)
    assert bands == _selected_bands(ctx, placed, expressions, plan), (
        f"the corridor must be the chosen rung's own: bands {bands}")
    blocked_corridor = _wire_bands(
        ctx, placed, expressions, members={first[1]})
    assert blocked_corridor, "premise: the blocked rung's corridor is computable"
    assert not any(box in bands for box in blocked_corridor), (
        "the blocked first rung's corridor is still reserved — the old "
        f"all-candidates reservation: {blocked_corridor} in {bands}")
    chosen = plan["3V3"]
    xs = [point[0] for point in chosen.lead]
    ys = [point[1] for point in chosen.lead]
    chosen_corridor = (min(xs) - dc.FLAG_CLEARANCE, min(ys),
                       max(xs) + dc.FLAG_CLEARANCE, max(ys))
    assert chosen_corridor in bands, (
        "the rung the seat really takes must be the one reserved; "
        f"bands {bands}, chosen {chosen.member}")


def test_the_seat_pass_takes_the_planned_rung_and_not_its_own_first():
    ctx = _context(WIRE_MEMBERS)
    placed = _placement()
    expressions = dc._expressions(ctx, placed)
    ladder = [row for row in dc._wire_flag_seats(
        ctx, expressions, sorted(expressions)) if row[0] == "3V3"]
    assert len(ladder) >= 2, f"premise: the rail has a multi-pad ladder: {ladder}"
    solids, bodies = dc._placed_flag_obstacles(ctx, placed)
    points = [point for expression in expressions.values()
              for _member, point in expression.points]

    def router():
        return dc._Router(
            grid=ctx.budget.grid, residue=placed.residue,
            boxes=list(solids),
            bounds=dc._search_bounds(ctx, list(solids), points),
        )

    free = router()
    dc._seat_wire_flags(
        ctx, placed, expressions, sorted(expressions), free, solids, bodies,
        set(), {})
    assert ("3V3", ladder[0][1]) in free.flag_seats, (
        "premise: with no plan the pass takes the ladder's first rung: "
        f"{free.flag_seats}")

    planned = router()
    planned.wire_flag_plan = {
        "3V3": dc._WireFlagSeat(
            net="3V3", member=ladder[1][1], point=ladder[1][2],
            profile=ladder[1][3], ref=ladder[1][4], cls=ladder[1][5],
            vertical=ladder[1][6], seat_key=ladder[1][7],
            anchor=(0.0, 0.0), rotation=0.0, lead=((0.0, 0.0), (0.0, 0.0)),
        ),
    }
    dc._seat_wire_flags(
        ctx, placed, expressions, sorted(expressions), planned, solids, bodies,
        set(), {})
    assert ("3V3", ladder[1][1]) in planned.flag_seats, (
        "the seat pass ignored the planned rung the text pass reserved: "
        f"{planned.flag_seats}")
    assert ("3V3", ladder[0][1]) not in planned.flag_seats, (
        "the seat pass hung the flag on its own first rung, not the planned one: "
        f"{planned.flag_seats}")
