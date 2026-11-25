"""606: a cross-module wire is one *conductor*, not one `LayoutSegment`.

570-A2-H2 measured the hole: `_cross_module_wires` read `points[0]` / `points[-1]`
of a single segment, so the same run cut into two at a junction in the island gap
had no cross entry at all, and a segment with `net=""` was filtered out of the
main-path test by name even though the page draws it from one pin to the other.

The rule pinned here: aggregate the segments `_derive` already unions into one
conductor and take that conductor's **true outer ends**; name the conductor only
from evidence (a label / power symbol on it, member segments agreeing on one
non-empty `segment.net`, or — on a full page check — a CircuitSpec net whose
member set is *exactly* the conductor's pins). A bare run between two islands is
not named by geometry: "it crosses two frames" is not evidence of VIN.
"""

from __future__ import annotations

from boardwise.core.circuitspec import CircuitSpec, SpecNet, SpecPart
from boardwise.core.layoutplan import (
    LayoutLabel,
    LayoutPart,
    LayoutPlan,
    LayoutSegment,
    LayoutSource,
)
from boardwise.core.pagelayoutplan import PageLayoutPlan, PageModule
from boardwise.core.presentationspec import (
    FlowEdge,
    PresentationModule,
    PresentationSpec,
)
from boardwise.core.symbolprofile import SymbolPin, SymbolProfile
from boardwise.engines import readability
from boardwise.engines.readability import (
    KIND_MAIN_PATH_EDGE_NOT_WIRED,
    KIND_SHARED_NET_EXPRESSION_SPLIT,
    check_page,
    derive_netlist,
    _check_main_paths,
    _cross_module_wires,
)

HASH = "a" * 64
RES = "RES-2P"

RES_PROFILE = SymbolProfile(
    symbol_ref=RES, title="Resistor", body=(-10.0, -20.0, 10.0, 20.0),
    pins=[
        SymbolPin(number="1", tip=(0.0, 50.0), name="1", direction="up"),
        SymbolPin(number="2", tip=(0.0, -50.0), name="2", direction="down"),
    ],
)
PROFILES = {RES: RES_PROFILE}

#: Two 100-wide islands with a 100-unit gap: a junction at (150, 50) is in no frame.
FRAMES = {"A": (0.0, 0.0, 100.0, 100.0), "B": (200.0, 0.0, 300.0, 100.0)}


def _plan(*segments, labels=(), parts=()) -> LayoutPlan:
    return LayoutPlan(
        source=LayoutSource(circuit_sha256=HASH, presentation_sha256=HASH),
        parts=list(parts),
        segments=list(segments),
        labels=list(labels),
    )


def seg(net: str, *points) -> LayoutSegment:
    return LayoutSegment(net=net, points=[tuple(point) for point in points])


def _main_path_spec() -> PresentationSpec:
    return PresentationSpec(
        modules=[
            PresentationModule(id="A", parts=["U1"]),
            PresentationModule(id="B", parts=["U2"]),
        ],
        grammar_ref="voltage-divider",
        flow=[FlowEdge(from_module="A", to_module="B", main_path=True)],
    )


def _vin_circuit() -> CircuitSpec:
    return CircuitSpec(
        parts=[
            SpecPart(id="U1", symbol_ref=RES, value="10k"),
            SpecPart(id="U2", symbol_ref=RES, value="10k"),
        ],
        nets=[SpecNet(id="VIN", cls="power", members=["U1.1", "U2.1"])],
    )


# ---------------------------------------------------------------- conductors


def test_the_same_conductor_cut_at_the_gap_junction_still_crosses():
    """2b: two segments, one wire — the junction is not an outer end."""
    plan = _plan(
        seg("VIN", (90.0, 50.0), (150.0, 50.0)),
        seg("VIN", (150.0, 50.0), (210.0, 50.0)),
    )
    assert _cross_module_wires(plan, FRAMES) == [(0, "VIN", "A", "B")]


def test_the_main_path_edge_is_wired_by_the_split_conductor():
    """2b's consequence: `_check_main_paths` no longer invents "no wire joins"."""
    plan = _plan(
        seg("VIN", (90.0, 50.0), (150.0, 50.0)),
        seg("VIN", (150.0, 50.0), (210.0, 50.0)),
    )
    cross = _cross_module_wires(plan, FRAMES)
    found = _check_main_paths(_main_path_spec(), _vin_circuit(), FRAMES, cross)
    assert found == [], [item.render() for item in found]


def test_a_conductor_of_three_segments_is_one_cross_entry():
    """Both gap junctions are interior; only the two far ends are outer."""
    plan = _plan(
        seg("VIN", (90.0, 50.0), (130.0, 50.0)),
        seg("VIN", (130.0, 50.0), (170.0, 50.0)),
        seg("VIN", (170.0, 50.0), (210.0, 50.0)),
    )
    assert _cross_module_wires(plan, FRAMES) == [(0, "VIN", "A", "B")]


def test_a_t_stub_in_the_gap_does_not_add_a_false_module():
    """A third segment hanging off the junction has an outer end in no frame.

    All outer ends are read (the stub is one), so the pair is still exactly A-B
    and the stub end is not reported as a module.
    """
    plan = _plan(
        seg("VIN", (90.0, 50.0), (150.0, 50.0)),
        seg("VIN", (150.0, 50.0), (210.0, 50.0)),
        seg("VIN", (150.0, 50.0), (150.0, 10.0)),
    )
    cross = _cross_module_wires(plan, FRAMES)
    assert cross == [(0, "VIN", "A", "B")]
    derived = readability.derive_netlist(plan, {})
    conductor = derived.segment_conductors[0]
    assert conductor == (0, 1, 2)
    assert len(readability._outer_ends(plan, conductor)) == 3


def test_two_nets_that_only_cross_in_the_gap_stay_two_conductors():
    """Measured editor behaviour: a proper crossing is not a junction."""
    plan = _plan(
        seg("VIN", (90.0, 50.0), (210.0, 50.0)),
        seg("GND", (150.0, 20.0), (150.0, 80.0)),
    )
    cross = _cross_module_wires(plan, FRAMES)
    assert cross == [(0, "VIN", "A", "B")]
    derived = derive_netlist(plan, {})
    assert derived.segment_conductors[0] == (0,)
    assert derived.segment_conductors[1] == (1,)


# ------------------------------------------------------------- naming rules


def test_a_bare_cross_island_run_is_not_named_vin():
    """2c: the original probe's shape — no label, no flag, no spec — is unnamed."""
    plan = _plan(seg("", (90.0, 50.0), (210.0, 50.0)))
    assert _cross_module_wires(plan, FRAMES) == [(0, "", "A", "B")]


def test_a_label_on_the_conductor_names_it():
    plan = _plan(
        seg("", (90.0, 50.0), (150.0, 50.0)),
        seg("", (150.0, 50.0), (210.0, 50.0)),
    )
    plan.labels.append(LayoutLabel(net="VIN", text="VIN", x=150.0, y=50.0,
                                   bbox=(140.0, 60.0, 160.0, 70.0)))
    derived = derive_netlist(plan, {})
    assert _cross_module_wires(plan, FRAMES, derived) == [(0, "VIN", "A", "B")]


def test_conflicting_names_on_one_conductor_name_nothing():
    plan = _plan(seg("", (90.0, 50.0), (210.0, 50.0)))
    plan.labels.append(LayoutLabel(net="VIN", text="VIN", x=100.0, y=50.0,
                                   bbox=(90.0, 60.0, 110.0, 70.0)))
    plan.labels.append(LayoutLabel(net="GND", text="GND", x=200.0, y=50.0,
                                   bbox=(190.0, 60.0, 210.0, 70.0)))
    derived = derive_netlist(plan, {})
    assert _cross_module_wires(plan, FRAMES, derived) == [(0, "", "A", "B")]


def test_a_pin_set_that_is_only_a_subset_of_a_spec_net_does_not_borrow_its_name():
    """U1.1 alone is *inside* VIN, not VIN: a proper subset proves nothing."""
    plan = _plan(
        seg("", (50.0, 100.0), (250.0, 100.0)),
        parts=[
            LayoutPart(part_id="U1", symbol_ref=RES, symbol_hash=HASH,
                       x=50.0, y=50.0),
        ],
    )
    frames = {"A": (0.0, 0.0, 200.0, 200.0), "B": (200.0, 50.0, 400.0, 150.0)}
    derived = derive_netlist(plan, PROFILES)
    assert derived.conductor_pins[(0,)] == ("U1.1",)
    cross = _cross_module_wires(plan, frames, derived, _vin_circuit())
    assert cross == [(0, "", "A", "B")]


def test_member_segments_that_agree_on_one_net_name_it_without_a_spec():
    plan = _plan(
        seg("", (90.0, 50.0), (150.0, 50.0)),
        seg("VIN", (150.0, 50.0), (210.0, 50.0)),
    )
    assert _cross_module_wires(plan, FRAMES) == [(0, "VIN", "A", "B")]


def test_member_segments_that_disagree_on_their_net_name_nothing():
    plan = _plan(
        seg("VIN", (90.0, 50.0), (150.0, 50.0)),
        seg("GND", (150.0, 50.0), (210.0, 50.0)),
    )
    assert _cross_module_wires(plan, FRAMES) == [(0, "", "A", "B")]


# --------------------------------------------------- the real page check


def _page(*, first_net: str, second_net: str) -> PageLayoutPlan:
    """U1 in A and U2 in B, joined pin to pin by two segments across the gap.

    U1 sits at (50, 50) so pin 1's tip is (50, 100); U2 at (350, 50) so its
    pin 1 is (350, 100). The conductor is cut at (250, 100), in the gap.
    """
    return PageLayoutPlan(
        plan=_plan(
            seg(first_net, (50.0, 100.0), (250.0, 100.0)),
            seg(second_net, (250.0, 100.0), (350.0, 100.0)),
            parts=[
                LayoutPart(part_id="U1", symbol_ref=RES, symbol_hash=HASH,
                           x=50.0, y=50.0),
                LayoutPart(part_id="U2", symbol_ref=RES, symbol_hash=HASH,
                           x=350.0, y=50.0),
            ],
        ),
        modules=[
            PageModule(id="A", parts=["U1"], frame=(0.0, 0.0, 200.0, 200.0)),
            PageModule(id="B", parts=["U2"], frame=(300.0, 0.0, 500.0, 200.0)),
        ],
        page_box=(-100.0, -100.0, 700.0, 400.0),
    )


def _page_violations(page: PageLayoutPlan) -> list:
    result = check_page(page, _vin_circuit(), _main_path_spec(), PROFILES)
    return list(result.hard_violations)


def test_the_real_page_check_wires_a_split_conductor_whose_segments_are_unnamed():
    """Both segments name nothing: only the CircuitSpec's exact pin set does."""
    page = _page(first_net="", second_net="")
    derived = derive_netlist(page.plan, PROFILES)
    assert derived.conductor_pins[(0, 1)] == ("U1.1", "U2.1")
    assert derived.pin_group["U1.1"] == ("U1.1", "U2.1")
    found = [
        item for item in _page_violations(page)
        if item.kind in (KIND_MAIN_PATH_EDGE_NOT_WIRED,
                         KIND_SHARED_NET_EXPRESSION_SPLIT)
    ]
    assert found == [], [item.render() for item in found]


def test_the_real_page_check_still_wires_when_one_segment_is_unnamed_and_one_says_vin():
    page = _page(first_net="", second_net="VIN")
    found = [
        item for item in _page_violations(page)
        if item.kind in (KIND_MAIN_PATH_EDGE_NOT_WIRED,
                         KIND_SHARED_NET_EXPRESSION_SPLIT)
    ]
    assert found == [], [item.render() for item in found]


def test_the_real_page_check_ignores_a_conductor_of_another_net():
    """The negative control: an unnamed run whose pins are a net the page does
    not own (here the conductor has no pin at all) must not become VIN."""
    page = PageLayoutPlan(
        plan=_plan(seg("", (50.0, 100.0), (350.0, 100.0))),
        modules=[
            PageModule(id="A", parts=[], frame=(0.0, 0.0, 200.0, 200.0)),
            PageModule(id="B", parts=[], frame=(300.0, 0.0, 500.0, 200.0)),
        ],
        page_box=(-100.0, -100.0, 700.0, 400.0),
    )
    frames = {module.id: module.frame for module in page.modules}
    derived = readability._derive(page.plan, readability._placed_parts(page.plan, {}))
    assert _cross_module_wires(page.plan, frames, derived, _vin_circuit()) == [
        (0, "", "A", "B")
    ]
