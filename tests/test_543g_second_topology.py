"""543G-3: the second topology — CH340G + USB-C 16P with a real UART header.

The first topology (CH343, ``ch343_uart_534a``) is the page every 543 rule was
tuned on. A rule that only works because it was written for CH343 is not a rule,
so this sheet is a second, publicly stated board with a different bridge: the
same roles must come out of the netlist, and the two facts that differ must come
out differently.

What is pinned here, and why each one is a *contract* rather than a snapshot:

* **the spec is one real board** — twelve parts, every symbol from a measured
  profile, every pin either on a net or declared NC, so nothing is drawn on a
  pin that the circuit never mentions;
* **the decoupling service is read with the roles renamed** — the CH340G's VCC
  is pin 16 and its V3 is pin 4, i.e. the opposite assignment from the CH343's
  V3(4)/VCC(15). A relation that is right for the wrong reason (a designator, a
  net name, "the second capacitor") cannot pass both sheets; this one is stated
  in terms of "the cap on the net the core is fed from" and "the cap on the
  internally regulated pin", which the netlist answers;
* **the two oscillator capacitors are not decoupling** — they share XI/XO with
  X1, which is not a capacitor (543G-1's guard). If this ever reads `served`,
  `serviceLayout` will pull them off the crystal;
* **the Type-C island keeps its paired branches apart** — CC1/CC2 are two
  independent pull-downs on two signal nets (543J's negative branch: same return
  net is not a reason to share a flag), and the 100nF+10uF VBUS pair has *both*
  ends in common (543J's positive branch: its return may join);
* **the reversible data pins are mirrored pairs** — D+ on A6/B6, D- on A7/B7,
  each pair reaching U1.5/U1.6 by name (543L pairs by placed geometry, so the
  circuit has to state the four pins, not a U-to-U wire).

The last test records what the page pipeline **cannot** draw yet. It is written
as a refusal so the gap is visible in CI; when the two grammar readings below
are extended, it has to be replaced by the geometry contract (island frames,
CC pair same row / same text side, separate GND flags, equal D± carriers), not
deleted.
"""

from __future__ import annotations

import copy
import json
import pathlib

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawapply
from boardwise.engines import pagecompiler as pc
from boardwise.engines.layoutroles import analyze_decoupling

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPECS = ROOT / "blocklib" / "specs"
STEM = "ch340_uart_543g"
PAGE_BOX = (0.0, 0.0, 1170.0, 825.0)
GND = "GND"
VBUS = "+5V"


def _raw(name: str) -> dict:
    return json.loads((SPECS / f"{STEM}.{name}.json").read_text(encoding="utf-8"))


def _book():
    raw = _raw("library")
    items = raw["profiles"] if isinstance(raw, dict) else raw
    return {p.symbol_ref: p for p in (SymbolProfile.from_dict(i) for i in items)}


def _circuit() -> CircuitSpec:
    return CircuitSpec.load(SPECS / f"{STEM}.circuit.json")


def _presentation() -> PresentationSpec:
    return PresentationSpec.from_dict(copy.deepcopy(_raw("presentation")))


def _net(circuit: CircuitSpec, net_id: str):
    return next(net for net in circuit.nets if net.id == net_id)


def _members(circuit: CircuitSpec, net_id: str) -> set[str]:
    return {member for member in _net(circuit, net_id).members}


# ------------------------------------------------------------- the board


def test_the_spec_is_one_real_board():
    """Every part is a measured symbol and every pin is accounted for."""
    circuit = _circuit()
    book = _book()
    assert len(circuit.parts) == 12, [part.id for part in circuit.parts]
    for part in circuit.parts:
        assert part.symbol_ref in book, f"{part.id}: {part.symbol_ref} is not a profile"
        assert part.lcsc, f"{part.id} states no LCSC number"
        assert part.value, f"{part.id} states no value"

    # The pin sets are the library's own: a pin the symbol draws must be wired
    # or declared NC, or the drawing would show a pin the circuit never mentions.
    for part in circuit.parts:
        profile = book[part.symbol_ref]
        declared = {str(pin.number) for pin in profile.pins}
        wired = {
            member.partition(".")[2]
            for net in circuit.nets
            for member in net.members
            if member.partition(".")[0] == part.id
        }
        nc = {item.pin.partition(".")[2] for item in circuit.nc
              if item.pin.partition(".")[0] == part.id}
        assert wired <= declared, f"{part.id}: wired pins outside the symbol {wired - declared}"
        assert wired | nc == declared, (
            f"{part.id}: pins neither wired nor NC {sorted(declared - wired - nc)}"
        )
    # Both ends of every net exist in the circuit.
    part_ids = {part.id for part in circuit.parts}
    for net in circuit.nets:
        for member in net.members:
            assert member.partition(".")[0] in part_ids, f"{net.id}: {member}"


def test_the_bridge_is_the_second_bridge_and_its_pins_are_not_the_first():
    """CH340G VCC is 16 and V3 is 4 — the mirror of the CH343 sheet's 15/4."""
    circuit = _circuit()
    assert "U1.16" in _members(circuit, VBUS), "the bridge is not fed on pin 16"
    assert _members(circuit, "V3") == {"U1.4", "C4.1"}
    assert "U1.15" not in _members(circuit, VBUS)
    assert _presentation().module("serial") is not None


#: Every MPN this sheet states, with the LCSC number it must agree with. Each
#: value is copied from the public `ch343_uart_534a.circuit.json`, which carries
#: the same symbolRef for that part — an MPN is a fact about the part, and a
#: second sheet may not invent one.
CONFIRMED_MPN = {
    "USB1": ("TYPE-C-31-M-12", "C165948"),
    "R1": ("0603WAF5101T5E", "C23186"),
    "R2": ("0603WAF5101T5E", "C23186"),
    "C1": ("CL10B104KA8NNNC", "C1590"),
    "C2": ("CL21A106KAYNNNE", "C15850"),
    "U1": ("CH340G", "C14267"),
    "C3": ("CL10B104KA8NNNC", "C1590"),
    "C4": ("CL10B104KA8NNNC", "C1590"),
    "H1": ("PZ254V-22-10-A60-3000", "C49056209"),
}


def test_every_stated_mpn_matches_its_lcsc_and_no_part_guesses_one():
    """Placing a part needs the exact MPN; a wrong one places nothing.

    The live editor resolved ``CL10B104KA8NNNC`` by exact MPN, so the sheet has
    to state the real manufacturer part number next to every LCSC number it
    already states — and has to leave it out where nobody has confirmed one.
    The 12 MHz crystal (and its two 22pF loads) have no confirmed MPN: absent is
    the honest answer, a plausible-looking string would not be.
    """
    circuit = _circuit()
    for part_id, (mpn, lcsc) in CONFIRMED_MPN.items():
        part = circuit.part(part_id)
        assert part is not None, part_id
        assert part.lcsc == lcsc, (part_id, part.lcsc)
        assert part.mpn == mpn, (part_id, part.mpn)
        assert part.mpn.upper() != part.lcsc.upper(), (
            f"{part_id}: the MPN is the LCSC number, which places nothing"
        )
    for part_id in ("X1", "C5", "C6"):
        part = circuit.part(part_id)
        assert not (part.mpn or "").strip(), (part_id, part.mpn)


# -------------------------------------------------- roles, read from the netlist


def test_the_decoupling_service_is_read_with_the_roles_renamed():
    analysis = analyze_decoupling(_circuit(), _presentation(), None)

    vcc = analysis.for_part("C3")
    assert vcc is not None and vcc.resolved, vcc
    assert (vcc.net_id, vcc.host_id) == (VBUS, "U1")
    assert vcc.host_pins == ("16",), vcc.host_pins
    assert vcc.has_unique_host_pin

    v3 = analysis.for_part("C4")
    assert v3 is not None and v3.resolved, v3
    assert (v3.net_id, v3.host_id) == ("V3", "U1")
    assert v3.host_pins == ("4",), v3.host_pins

    # The connector's own pair serves the receptacle and keeps both equivalent
    # VBUS contacts as candidates instead of picking one.
    for part_id in ("C1", "C2"):
        service = analysis.for_part(part_id)
        assert service is not None and service.resolved, service
        assert service.net_id == VBUS and service.host_id == "USB1"
        assert set(service.host_pins) == {"A4B9", "B4A9"}
        assert not service.has_unique_host_pin


def test_the_two_oscillator_capacitors_are_not_decoupling():
    """543G-1: a shunt on a net X1 also carries is a load, not a bypass."""
    analysis = analyze_decoupling(_circuit(), _presentation(), None)
    for part_id in ("C5", "C6"):
        service = analysis.for_part(part_id)
        assert service is not None, part_id
        assert not service.resolved, service.reason
        assert service.status == "not_decoupling", service.status
        assert "X1" in service.reason, service.reason
    # The oscillator is a branch of the bridge, not an island of its own: the
    # crystal and its two loads are declared inside `serial`, with U1's core in
    # the same scope, which is what makes the bridge reading legal (boardwise-draw
    # §2: an auxiliary branch stays with its host island).
    serial = _presentation().module("serial")
    assert serial is not None and serial.core == "U1"
    assert {"X1", "C5", "C6"} <= set(serial.parts), serial.parts
    assert _presentation().module("clock") is None


# ------------------------------------------------------------- the USB edges


def test_the_cc_pull_downs_are_two_independent_branches():
    circuit = _circuit()
    assert _members(circuit, "CC1") == {"USB1.A5", "R1.1"}
    assert _members(circuit, "CC2") == {"USB1.B5", "R2.1"}
    assert _net(circuit, "CC1").cls == "signal"
    assert _net(circuit, "CC2").cls == "signal"
    # Each branch returns to ground on its own pin: same return net, two
    # branches — 543J's negative branch, so they may not share a flag.
    assert "R1.2" in _members(circuit, GND)
    assert "R2.2" in _members(circuit, GND)
    assert _members(circuit, "CC1") & _members(circuit, "CC2") == set()


def test_the_vbus_decoupling_pair_has_both_ends_in_common():
    """543J's positive branch: same host, same two nets, so the return may join."""
    circuit = _circuit()
    vbus = _members(circuit, VBUS)
    gnd = _members(circuit, GND)
    assert {"C1.1", "C2.1"} <= vbus
    assert {"C1.2", "C2.2"} <= gnd
    assert {"USB1.A4B9", "USB1.B4A9"} <= vbus
    assert _net(circuit, VBUS).cls == "power"


def test_the_usb_data_pins_are_mirrored_pairs():
    circuit = _circuit()
    assert _members(circuit, "D+") == {"USB1.A6", "USB1.B6", "U1.5"}
    assert _members(circuit, "D-") == {"USB1.A7", "USB1.B7", "U1.6"}
    # The two halves of one pair are two receptacle pins, not one pin twice.
    assert len([m for m in _members(circuit, "D+") if m.startswith("USB1.")]) == 2
    assert len([m for m in _members(circuit, "D-") if m.startswith("USB1.")]) == 2
    obligations = _raw("presentation")["localLabelObligations"]
    assert any(set(entry["nets"]) == {"D+", "D-"} for entry in obligations)


def test_the_uart_lines_leave_the_bridge_for_the_header():
    circuit = _circuit()
    assert _members(circuit, "TXD") == {"U1.2", "H1.1"}
    assert _members(circuit, "RXD") == {"U1.3", "H1.2"}
    # The header is the board's boundary: 5 V and ground come out with the data
    # lines, and only the pins past the ground are left unconnected.
    assert "H1.9" in _members(circuit, VBUS)
    assert "H1.10" in _members(circuit, GND)
    assert _members(circuit, GND) >= {"H1.10", "U1.1"}
    header_nc = {item.pin for item in circuit.nc if item.pin.startswith("H1.")}
    assert header_nc == {f"H1.{index}" for index in range(3, 9)}, header_nc


# ------------------------------------------------- the page that does exist


def _pin(plan, book, member: str) -> tuple[float, float]:
    from boardwise.core.geometry import transform_point

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
        points = [(round(float(x), 3), round(float(y), 3)) for x, y in segment.points]
        length = sum(
            abs(points[i + 1][0] - points[i][0]) + abs(points[i + 1][1] - points[i][1])
            for i in range(len(points) - 1)
        )
        out.append((round(length, 3), points))
    return out


def test_the_page_compiles_as_three_islands_with_the_clock_in_the_bridge():
    """543G-4: the corrected semantics — three islands, all twelve parts drawn.

    ``usb_c`` keeps the receptacle with its CC pull-downs and the VBUS pair;
    ``serial`` keeps the bridge **with** its oscillator branch (X1 and its two
    loads hang off U1's own XI/XO pins, so they are the bridge's own sub-circuit,
    not an island — boardwise-draw §2); ``uart`` is the header's own boundary,
    supplied through pin 9 and returned through pin 10.

    What is pinned here is the geometry that is already right: the CC pair as one
    straight run per net at the same length on the same row, and the two
    decoupling service runs at the stated 30 units on their own host pin. The
    page's known open gaps are **not** accepted here and are deliberately not
    asserted: the near D± pair (`A6`/`A7`) still settles on 5 units — the joint
    ladder's first rung, below the document's own 40 — and the header lands below
    ``usb_c`` instead of downstream of ``serial``. (XI/XO used to be on this list
    at 240/210; 543G-12b's bay now seats the oscillator from its host pins and
    ``test_543g_clock_bay`` owns that contract.) This test says nothing about
    visual quality.
    """
    book = _book()
    result = pc.compile_page(
        _circuit(), _presentation(), book, pc.PageCompileBudget(page_box=PAGE_BOX)
    )
    assert result.ok, result.render_failures()
    assert result.pages, "no page candidate"
    page = result.pages[0]

    assert {module.id for module in page.modules} == {"usb_c", "serial", "uart"}
    parts = {module.id: set(module.parts) for module in page.modules}
    assert parts["usb_c"] == {"USB1", "R1", "R2", "C1", "C2"}
    assert parts["serial"] == {"U1", "C3", "C4", "X1", "C5", "C6"}
    assert parts["uart"] == {"H1"}

    plan = page.plan
    assert {part.part_id for part in plan.parts} == set().union(*parts.values())

    # The CC pair: one run each, equal, horizontal, pin to pin (543K/543D).
    for net_id, branch in (("CC1", "R1.1"), ("CC2", "R2.1")):
        runs = _runs(plan, net_id)
        assert len(runs) == 1, (net_id, runs)
        length, points = runs[0]
        assert length == 130.0, (net_id, length)
        here = _pin(plan, book, f"USB1.A5" if net_id == "CC1" else "USB1.B5")
        there = _pin(plan, book, branch)
        assert points[0] == here and points[-1] == there, (net_id, points, here, there)
        assert here[1] == there[1], (net_id, here, there)

    # The service runs the netlist decided: V3 → C4 at pin 4, +5V → C3 at pin 16.
    for net_id, service, host in (("V3", "C4.1", "U1.4"), (VBUS, "C3.1", "U1.16")):
        here = _pin(plan, book, service)
        there = _pin(plan, book, host)
        assert abs(here[0] - there[0]) + abs(here[1] - there[1]) == 30.0, (net_id, here, there)
        assert (round(here[0], 3), round(here[1], 3)) in [p for _, pts in _runs(plan, net_id) for p in pts]
        assert (round(there[0], 3), round(there[1], 3)) in [p for _, pts in _runs(plan, net_id) for p in pts]


# --------------------------------------- the reversible data pairs (543G-5)

#: 543L's reading unit: two **mirrored pins of one part**, one length per pair.
#: The A and the B group are two decisions and are not made to agree — the whole
#: point of the joint choice is that neither pin of *one* pair is placed first
#: and the other matched to it afterwards.
DATA_PAIRS = (
    (("D+", "USB1.A6"), ("D-", "USB1.A7")),
    (("D+", "USB1.B6"), ("D-", "USB1.B7")),
)
DATA_PINS = tuple(member for pair in DATA_PAIRS for _net, member in pair) + (
    "U1.5", "U1.6",
)


def _data_carriers(plan, book):
    """``(tips, carriers)`` — each D± run keyed by the pin its near end lands on."""
    tips = {
        member: tuple(round(float(v), 3) for v in _pin(plan, book, member))
        for member in DATA_PINS
    }
    carriers: dict[str, tuple[float, list[tuple[float, float]]]] = {}
    for net_id in ("D+", "D-"):
        for length, points in _runs(plan, net_id):
            member = next((m for m, tip in tips.items() if tip == points[0]), None)
            assert member is not None, (net_id, points, tips)
            carriers[member] = (length, points)
    return tips, carriers


def _pages():
    result = pc.compile_page(
        _circuit(), _presentation(), _book(), pc.PageCompileBudget(page_box=PAGE_BOX)
    )
    assert result.ok, result.render_failures()
    assert result.pages, "no page candidate"
    return result.pages


def test_the_two_data_nets_are_paired_from_the_placed_geometry(monkeypatch):
    """543G-5: `_local_label_pin_pairs` **does** pair the reversible pins here.

    The G-4 note read the page's `5 / 60` as "the pairs were never made", so the
    first question this batch had to answer is whether the pairing fires on the
    second topology at all. It does: both pairs come back from the placed geometry
    alone (one side of one part, mirrored rows about its centre, pitches 10 and
    30), which is the same shape the CH343 sheet yields. What the page then does
    with the decision is a different question, pinned below.
    """
    from boardwise.engines import drawcompiler as dc

    seen: list[dict] = []
    original = dc._local_label_pin_pairs

    def record(ctx, placed, nets, expressions):
        pairs = original(ctx, placed, nets, expressions)
        if "D+" in nets:
            seen.append(dict(pairs))
        return pairs

    monkeypatch.setattr(dc, "_local_label_pin_pairs", record)
    pc.compile_page(
        _circuit(), _presentation(), _book(), pc.PageCompileBudget(page_box=PAGE_BOX)
    )

    assert seen, "the two-net obligation was never paired"
    pairs = seen[0]
    assert len(pairs) == 4, pairs
    for point, partner in pairs.items():
        assert pairs[partner[2]][2] == point
    mirrored = [(point, partner[2]) for point, partner in pairs.items() if point < partner[2]]
    assert len(mirrored) == 2, mirrored
    centres = {(point[1] + partner[1]) / 2.0 for point, partner in mirrored}
    assert len(centres) == 1, mirrored
    pitches = sorted(abs(point[1] - partner[1]) for point, partner in mirrored)
    assert pitches == [10.0, 30.0], pitches


def test_the_data_pins_are_equal_inside_each_mirrored_pair():
    """543G-9: the 543L reading, measured on the **final draw plan**.

    The page's drawn wires are the landing plan's, not the compiler's: the
    compiler reserves a 5-unit carrier per Type-C data pin and the landing pass
    gives each of those names the document's 40-unit stand-off
    (``200→205→240``, the same shape the reference sheet has). Measuring
    `page.plan.segments` alone reports 5 and invents a floor gap that the drawn
    page does not have. Measured where the reader sees it: A pair 40/40, B pair
    60/60, one length per mirrored pair, every run starting at its own pin tip
    with the name at its far end, and the two groups free to differ.
    """
    circuit, book = _circuit(), _book()
    presentation = _presentation()
    floor = presentation.label_policy.stub_min
    landed = 0
    for index, page in enumerate(_pages()):
        try:
            plan = drawapply.module_plan(
                page.plan, circuit, presentation, book, candidate_index=index,
                label_stubs=True, page_box=PAGE_BOX, module_label=f"page {index}",
            )
        except drawapply.DrawPlanError:
            continue
        landed += 1
        wires = {
            (str(wire.net), str(wire.from_pin)): (
                round(sum(
                    abs(float(b[0]) - float(a[0])) + abs(float(b[1]) - float(a[1]))
                    for a, b in zip(wire.points, wire.points[1:])
                ), 1),
                [(round(float(p[0]), 1), round(float(p[1]), 1))
                 for p in wire.points],
            )
            for wire in plan.change.draw_wires
            if str(wire.net) in ("D+", "D-")
        }
        for (net_one, member_one), (net_two, member_two) in DATA_PAIRS:
            assert (net_one, member_one) in wires, (index, member_one, sorted(wires))
            assert (net_two, member_two) in wires, (index, member_two, sorted(wires))
            one, two = wires[(net_one, member_one)], wires[(net_two, member_two)]
            assert one[0] == two[0], (index, member_one, member_two, one, two)
            for key, (length, points) in (
                ((net_one, member_one), one), ((net_two, member_two), two),
            ):
                tip = tuple(round(float(v), 1) for v in _pin(page.plan, book, key[1]))
                assert points[0] == tip, (index, key, points, tip)
                assert length >= floor, (index, key, length, floor)
                # the name the compiler placed sits on this run
                assert (205.0 in [p[0] for p in points]) or (
                    points[-1][0] == 260.0
                ), (index, key, points)
        # The two groups are two decisions: nothing forces A to meet B.
        assert wires[("D+", "USB1.A6")][0] != wires[("D+", "USB1.B6")][0], index
        # Every Type-C data pin is named on its own run, never across the symbol.
        assert len([key for key in wires if key[1].startswith("USB1.")]) == 4, index
    assert landed >= 1, "no candidate lands the page"


def test_the_bridge_data_pins_are_named_on_their_own_carriers():
    """543G-9: `U1.5`/`U1.6` are named on 40-unit carriers, not on the pin.

    G-5/G-6 read the compiler plan and found no run out of the bridge's data
    pins; the landing pass draws one for each (40 units, westwards, the name at
    its far end). Recorded here at the stage it happens in, so the two stages
    cannot be confused again.
    """
    circuit, book = _circuit(), _book()
    presentation = _presentation()
    floor = presentation.label_policy.stub_min
    landed = 0
    for index, page in enumerate(_pages()):
        try:
            plan = drawapply.module_plan(
                page.plan, circuit, presentation, book, candidate_index=index,
                label_stubs=True, page_box=PAGE_BOX, module_label=f"page {index}",
            )
        except drawapply.DrawPlanError:
            continue
        landed += 1
        wires = {
            (str(wire.net), str(wire.from_pin)): round(sum(
                abs(float(b[0]) - float(a[0])) + abs(float(b[1]) - float(a[1]))
                for a, b in zip(wire.points, wire.points[1:])
            ), 1)
            for wire in plan.change.draw_wires
            if str(wire.net) in ("D+", "D-")
        }
        for key in (("D+", "U1.5"), ("D-", "U1.6")):
            assert key in wires, (index, key, sorted(wires))
            assert wires[key] >= floor, (index, key, wires[key])
    assert landed >= 1, "no candidate lands the page"


# ------------------------------ the crossing label's carrier (543G-6)


def _p38():
    """The reference page's own document: circuit, presentation, library.

    543G-6 needs one comparison and it is the sheet every rule was tuned on, so
    the fixtures come from the 543h3b payload the 543L batch already compiles
    against — no coordinate, no net name and no part is read out of it here.
    """
    import test_543h3b_stated_text_lane as t3b

    return (
        CircuitSpec.load(SPECS / "ch343_uart_534a.circuit.json"),
        PresentationSpec.from_dict(copy.deepcopy(t3b.PAYLOAD)),
        {
            p.symbol_ref: p
            for p in (
                SymbolProfile.from_dict(i)
                for i in json.loads(
                    (SPECS / "ch343_uart_v4.library.json").read_text(
                        encoding="utf-8"
                    )
                )["profiles"]
            )
        },
    )


CROSSING_NETS = ("D+", "D-", "TXD", "RXD")


def _crossing_plan_facts(circuit, presentation, book):
    """``(labels, runs)`` for the crossing nets of one page's **compiler** plan.

    053's original meaning: inside an island a multi-pin net is a wire; across
    islands a signal is *named*, and a single-pin crossing label sits **at** its
    pin. The run that carries that name on the page is not this plan's — it is
    the landing pass's (`drawapply`, pinned below). Measuring a page's cross-island
    carriers must therefore not read `plan.segments` alone.
    """
    result = pc.compile_page(
        circuit, presentation, book, pc.PageCompileBudget(page_box=PAGE_BOX)
    )
    assert result.ok, result.render_failures()
    plan = result.pages[0].plan
    labels = sorted(
        (label.net, label.part_id, round(float(label.x), 1),
         round(float(label.y), 1))
        for label in plan.labels if label.net in CROSSING_NETS
    )
    runs = sorted(
        (segment.net, tuple(tuple(round(float(v), 1) for v in p) for p in segment.points))
        for segment in plan.segments if segment.net in CROSSING_NETS
    )
    return labels, runs


def test_a_single_pin_crossing_label_is_named_at_the_pin_on_both_topologies():
    """543G-6: the reference sheet's plan does the same thing — so 543G is not it.

    G-5 reported "`U1.5`/`U1.6` have no carrier" from `page.plan.segments`. The
    reference P38 plan, measured with the same ruler, carries **exactly the same
    four USB1 runs and nothing else**: the bridge-side and header-side crossing
    labels are bare labels at their pins on both pages. What differs is that the
    reference page *lands* (its landing pass finds a stub for every label) and
    543G's does not — one label, `H1`'s TXD, which is pinned in the next test.
    """
    ch343 = _crossing_plan_facts(*_p38())
    ch340 = _crossing_plan_facts(_circuit(), _presentation(), _book())
    for name, (labels, runs) in (("p38", ch343), ("543g", ch340)):
        bridge = [row for row in labels if row[1] == "U1"]
        header = [row for row in labels if row[1] == "H1"]
        assert {row[0] for row in bridge} == set(CROSSING_NETS), (name, bridge)
        assert {row[0] for row in header} == {"TXD", "RXD"}, (name, header)
        # Every drawn run on these nets starts at a USB1 data pin: the crossing
        # labels are named at the pin, never wired across the symbol.
        assert len(runs) == 4, (name, runs)
        # …and the four runs are the receptacle's own: none of them reaches the
        # bridge or the header, so no crossing was drawn as a wire.
        assert len({run[1][0][0] for run in runs}) == 1, runs
        assert len({run[1][0][1] for run in runs}) == 4, runs
    assert {row[1] for row in ch340[0]} == {row[1] for row in ch343[0]}


def test_the_page_puts_the_header_downstream_of_the_bridge():
    """543G-7: the header sits on the flow's own path, not back under the port.

    The document states ``flow: usb_c → serial → uart`` and ``moduleColumns: 2``
    and names **every** module on that flow, so the flow is the page's reading
    order: the grid is filled down a column and on into the next one, and the
    header lands in the column **after** the bridge instead of at the page's
    left edge under the receptacle. The frames are read here, not a score.
    """
    ch340 = _presentation()
    assert [edge.from_module + ">" + edge.to_module for edge in ch340.flow] == [
        "usb_c>serial", "serial>uart",
    ], ch340.flow
    assert ch340.module_columns == 2
    for index, page in enumerate(_pages()):
        frames = {module.id: module.frame for module in page.modules}
        usb_c, serial, uart = frames["usb_c"], frames["serial"], frames["uart"]
        # usb_c at the reading start; serial under it, in the same column.
        assert serial[3] <= usb_c[1], (index, "serial is not below usb_c", frames)
        assert serial[0] < usb_c[2] and serial[2] > usb_c[0], (
            index, "serial is not in usb_c's column", frames,
        )
        # uart in the next column: never back under the receptacle / page edge.
        assert uart[0] >= serial[2], (index, "uart is not downstream of serial", frames)
        assert uart[0] > usb_c[2], (index, "uart is back under usb_c", frames)
        assert {module.id for module in page.modules} == {"usb_c", "serial", "uart"}


def test_a_page_whose_flow_names_every_module_is_the_only_one_that_moves():
    """The opt-in boundary: without ``moduleColumns`` the fill is the old one.

    ``moduleColumns`` **and** a flow that names every module are the two keys the
    reading direction needs. A document that drops either keeps 056's fill, left
    to right and row by row — the exact frame the reference sheets and every
    pre-543G page have. That is the isolation this rule buys: no new spec key,
    no page moved that did not ask.

    Read on the fill's **order**, not on where the wrap happens: 543G-12b's bay
    narrowed the ``serial`` island by 130 units, so the old fill now fits all
    three modules on one row instead of pushing the header back under the
    receptacle. The distinction the rule buys is unchanged and is what is
    asserted — beside each other (056's row-major fill) versus the flow's own
    reading, which stacks ``serial`` **below** ``usb_c`` and puts ``uart`` in the
    next column (the test above).
    """
    for drop in ("moduleColumns", "flow"):
        payload = copy.deepcopy(_raw("presentation"))
        payload.pop(drop)
        presentation = PresentationSpec.from_dict(payload)
        result = pc.compile_page(
            _circuit(), presentation, _book(),
            pc.PageCompileBudget(page_box=PAGE_BOX),
        )
        assert result.ok, result.render_failures()
        frames = {module.id: module.frame for module in result.pages[0].modules}
        # The old fill lays the modules **out along the page**, one after the
        # next in the module's own order, instead of stacking the next one under
        # the previous column — that is the difference the opt-in buys.
        assert frames["serial"][0] >= frames["usb_c"][2] - 1.0, (
            drop, "the old fill no longer lays serial beside usb_c", frames,
        )
        # …and the third module either takes the next cell to the right, or the
        # next row's first cell, which is the receptacle's own band again.
        beside = frames["uart"][0] >= frames["serial"][2] - 1.0
        wrapped = (
            frames["uart"][0] <= frames["usb_c"][0] + 1.0
            and frames["uart"][2] <= frames["usb_c"][2]
        )
        assert beside or wrapped, (
            drop, "the old fill is neither the row fill nor the wrapped one", frames,
        )


def test_every_crossing_label_lands_on_a_real_carrier():
    """543G-8: the six cross-island carriers, measured on the landed page.

    `drawapply.module_plan` is the landing pass: it gives every label at a pin its
    own short run, the document's `stubMin` floor first. With the header's parts
    text stated on its **outer** side (`partTexts.H1 = "right"`, 543G-8) the
    header's TXD stops being walled in by its own value row, and **all six**
    cross-island names land on carriers of at least 40 units: the bridge's four
    data lines to the west and the header's two UART lines outwards. The two
    landing candidates are the ones the page search keeps; the other two differ
    only by a lattice step and still refuse the header's TXD, which the ranking
    can afford because a candidate that lands is required (below).
    """
    presentation = _presentation()
    assert presentation.part_texts.get("H1") == "right", presentation.part_texts
    floor = presentation.label_policy.stub_min
    circuit, book = _circuit(), _book()
    result = pc.compile_page(
        circuit, presentation, book, pc.PageCompileBudget(page_box=PAGE_BOX)
    )
    assert result.ok, result.render_failures()

    original = drawapply._place_label_stub
    landed_pages = 0
    for index, page in enumerate(result.pages):
        landed: list[tuple] = []

        def record(label, built, bodies, pins, label_boxes=(), page_box=None):
            run, blockers = original(
                label, built, bodies, pins, label_boxes, page_box,
            )
            if getattr(label, "net", "") in CROSSING_NETS:
                landed.append((
                    label.net, getattr(label, "part_id", ""),
                    None if run is None else round(
                        sum(
                            abs(b[0] - a[0]) + abs(b[1] - a[1])
                            for a, b in zip(run, run[1:])
                        ), 1),
                    len(blockers),
                ))
            return run, blockers

        monkey = pytest.MonkeyPatch()
        monkey.setattr(drawapply, "_place_label_stub", record)
        try:
            try:
                drawapply.module_plan(
                    page.plan, circuit, presentation, book,
                    candidate_index=index, label_stubs=True, page_box=PAGE_BOX,
                    module_label=f"page {index}",
                )
            except drawapply.DrawPlanError:
                continue
        finally:
            monkey.undo()
        landed_pages += 1
        by_key = {(net, part): (length, blockers)
                  for net, part, length, blockers in landed}
        assert len(by_key) == 6, (index, sorted(by_key))
        for key in (("D+", "U1"), ("D-", "U1"), ("TXD", "U1"), ("RXD", "U1"),
                    ("TXD", "H1"), ("RXD", "H1")):
            length, blockers = by_key[key]
            assert length is not None and length >= floor, (index, key, length, blockers)
    assert landed_pages >= 1, "no candidate lands the page"

# ------------------------------ branchOrder is a statement, not a note (543G-11)


def _runs_of(plan, net_id):
    out = []
    for segment in plan.segments:
        if segment.net != net_id:
            continue
        out.append([(round(float(x), 1), round(float(y), 1)) for x, y in segment.points])
    return out


def test_a_stated_branch_order_is_consumed_and_an_unstated_one_is_not(monkeypatch):
    """543G-11: `branchOrder` decides the sequence; absent builds the same list.

    Until this change only the `power-entry` grammar read the key, so the 543G
    bridge's four permutations of `X1`/`C5`/`C6` drew byte-identical pages. The
    seater now reads the module's statement before it reads rank: the crystal
    takes the first rung and the XI run shortens from 240 to 120. A module that
    states nothing keeps the designator order and the shipped geometry exactly.

    **Read on the ladder**, i.e. with 543G-12b's bay neutered: that seat measures
    the three members from their host pins and no longer walks the rungs at all,
    so on the shipped document (both keys stated) the rung order has nothing
    left to decide — which is the third part of this test, and the reason the
    consumption contract has to be measured where the rungs still seat.
    """
    from boardwise.engines import drawcompiler as dc

    with monkeypatch.context() as ladder:
        ladder.setattr(dc, "_place_clock_bays", lambda *args, **kwargs: frozenset())
        _assert_stated_order_moves_the_crystal(dc)
    _assert_the_bay_supersedes_the_rung_order()


def _assert_stated_order_moves_the_crystal(dc):
    """The 543G-11 measurement, taken on the ladder itself."""

    circuit, book = _circuit(), _book()
    shipped = _presentation()
    stated_payload = copy.deepcopy(_raw("presentation"))
    for module in stated_payload["modules"]:
        if module["id"] == "serial":
            module["branchOrder"] = ["X1", "C5", "C6"]
    stated = PresentationSpec.from_dict(stated_payload)

    # 1) the read itself: the statement is indexed for the branches it names
    branches = {"X1", "C5", "C6", "C3", "C4"}
    ctx = type("Ctx", (), {"presentation": stated})()
    assert dc._stated_branch_order(ctx, branches) == {"X1": 0, "C5": 1, "C6": 2}
    ctx_shipped = type("Ctx", (), {"presentation": shipped})()
    assert dc._stated_branch_order(ctx_shipped, branches) == {}

    # 2) it is consumed: the crystal moves to the first rung
    before = pc.compile_page(
        circuit, shipped, book, pc.PageCompileBudget(page_box=PAGE_BOX)
    )
    after = pc.compile_page(
        circuit, stated, book, pc.PageCompileBudget(page_box=PAGE_BOX)
    )
    assert before.ok, before.render_failures()
    assert after.ok, after.render_failures()
    xi_before = _runs_of(before.pages[0].plan, "XI")
    xi_after = _runs_of(after.pages[0].plan, "XI")
    assert len(xi_before) == 1 and len(xi_after) == 1, (xi_before, xi_after)
    length = lambda points: sum(
        abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in zip(points, points[1:])
    )
    assert round(length(xi_before[0]), 1) == 240.0, xi_before
    assert round(length(xi_after[0]), 1) == 120.0, xi_after
    # …and the unstated document is the shipped **shape**: one straight XI leg
    # and one XO leg with its single 30-unit jog. The absolute x of both moved by
    # 35 when 543G-12c stated the clock's text sides (X1/C6 right, C5 left) — a
    # text statement, so the shape is what this pins, not the offset.
    assert len(xi_before[0]) == 2, xi_before
    assert xi_before[0][0][1] == xi_before[0][1][1], xi_before
    xo_before = _runs_of(before.pages[0].plan, "XO")
    assert len(xo_before) == 1, xo_before
    assert round(length(xo_before[0]), 1) == 210.0, xo_before
    # the whole perpendicular travel of the run is the two host pins' 30
    assert sum(abs(b[1] - a[1]) for a, b in zip(xo_before[0], xo_before[0][1:])) == 30.0, xo_before
    # The declaration has a price on the other net: the XO load is pushed to the
    # far rung and its run has to come back round the cluster (340 with a three
    # bend detour). That is why the document does not state this order: the
    # report carries the measurement, the spec stays as it was.
    xo_after = _runs_of(after.pages[0].plan, "XO")
    assert sum(round(length(points), 1) for points in xo_after) > 210.0, xo_after


def _assert_the_bay_supersedes_the_rung_order():
    """543G-12b: with the bay on, a stated order has no rung left to move.

    The bay is not "the rungs, drawn better": its three members are seated from
    the host pins (:func:`boardwise.engines.drawcompiler._place_clock_bays`), so
    both arms of the document — stated order and no order — draw the same clock.
    Pinned so that a future change that silently starts reading `branchOrder`
    for bay members is caught here rather than in a drawing review.
    """
    circuit, book = _circuit(), _book()
    shipped = _presentation()
    stated_payload = copy.deepcopy(_raw("presentation"))
    for module in stated_payload["modules"]:
        if module["id"] == "serial":
            module["branchOrder"] = ["X1", "C5", "C6"]
    stated = PresentationSpec.from_dict(stated_payload)

    arms = {}
    for name, spec in (("shipped", shipped), ("stated", stated)):
        result = pc.compile_page(
            circuit, spec, book, pc.PageCompileBudget(page_box=PAGE_BOX)
        )
        assert result.ok, result.render_failures()
        arms[name] = result.pages[0].plan
    for net_id in ("XI", "XO"):
        assert _runs_of(arms["shipped"], net_id) == _runs_of(arms["stated"], net_id), net_id
        length = sum(
            abs(b[0] - a[0]) + abs(b[1] - a[1])
            for points in _runs_of(arms["shipped"], net_id)
            for a, b in zip(points, points[1:])
        )
        assert round(length, 1) <= 120.0, (net_id, length)
