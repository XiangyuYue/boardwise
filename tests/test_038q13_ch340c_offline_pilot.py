"""038Q13: the CH340C block compiles offline, and its eleven nets survive pin by pin.

The task book asks for four things this file can answer without an editor:

* the presentation document is the `ic-periphery` statement of the structure the
  task book fixes — a `usb` island around the Type-C receptacle (both CC
  pull-downs on their own receptacle pins, the ESD array beside them) feeding a
  `serial` island around the bridge, whose two decoupling capacitors serve VCC
  and V3, and **no crystal**, because a CH340C clocks itself. `portRoles` speaks
  the circuit's own net ids, never a display name and never a direction for a
  ground;
* the real page compiler turns the pair into legal candidates whose derived
  netlist holds each of the eleven source nets member by member *and* under the
  right name (readability's number-first ruler, the same one `_check_netlist`
  uses) — not merely `ok=True`;
* the one NC the circuit declares (U.7) is still nc in the drawing: unwired, on
  its own node, carrying no name;
* the gap the grammar leaves is *named*: `D_ESD` is the part `ic-periphery`'s
  role table cannot bind, and the `localLabelObligations` the task book allows
  for the two reversible data nets cannot be honoured on this symbol at all — the
  six-pin ESD has no free side for the short carrier 534 asks for. Both are
  pinned here so a later grammar change cannot quietly move them;
* the four negative controls are caught — by the machine gate where the drawing
  really is illegal, by the source-net reconciliation where it is not, and by the
  NC reconciliation where the wiring moved a pin the spec had declared NC.

Nothing here modifies the real inputs: every negative control mutates a parsed
copy in memory. No `outputs/` is read, no editor, no bridge.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from boardwise.core.circuitspec import PORT_DIRECTIONS, CircuitSpec, CircuitSpecError
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import pagecompiler
from boardwise.engines import readability
from boardwise.engines.readability import derive_netlist

ROOT = Path(__file__).resolve().parents[1]
CIRCUIT = ROOT / "blocklib/modules/circuits/ch340c_usb_serial.circuit.json"
PRESENTATION = ROOT / "blocklib/specs/ch340c_usb_serial.presentation.json"
PROFILES = ROOT / "blocklib/symbols/profiles.json"

#: The seven parts, the two islands, and the part each island is arranged around.
PARTS = {"J_USB", "R_CC1", "R_CC2", "D_ESD", "U", "C_VCC", "C_V3"}
ISLANDS = {
    "usb": ({"J_USB", "R_CC1", "R_CC2", "D_ESD"}, "J_USB"),
    "serial": ({"U", "C_VCC", "C_V3"}, "U"),
}
#: What `ic-periphery` leaves unbound on this circuit: the ESD array is not the
#: core, is not a two-terminal part across two core pin nets (bridge) and is not
#: a two-terminal part from one core pin net to ground (shunt) — it touches the
#: two data nets and the rails at once, and the role table has no name for that.
UNBOUND_BY_GRAMMAR = {"D_ESD"}

#: The real net ids of the CircuitSpec. `port.DTR` / `port.RTS` are the *port*
#: names; the pins they carry are the physical `U.DTR#` / `U.RTS#`.
PORT_NET_IDS = {
    "port.TXD", "port.RXD", "port.DTR", "port.RTS", "port.VBUS_5V", "port.GND",
}
D_PLUS = "auto:D_ESD.3|D_ESD.4|J_USB.DP1|J_USB.DP2|U.D+"
D_MINUS = "auto:D_ESD.1|D_ESD.6|J_USB.DN1|J_USB.DN2|U.D-"
V3_NET = "auto:C_V3.1|U.V3"
VBUS_NET = "port.VBUS_5V"


def _profiles() -> dict[str, SymbolProfile]:
    payload = json.loads(PROFILES.read_text(encoding="utf-8"))
    items = payload["profiles"] if isinstance(payload, dict) else payload
    out: dict[str, SymbolProfile] = {}
    for item in items:
        profile = SymbolProfile.from_dict(item)
        out[profile.symbol_ref] = profile
    return out


def _circuit() -> CircuitSpec:
    return CircuitSpec.load(CIRCUIT)


def _presentation() -> PresentationSpec:
    return PresentationSpec.load(PRESENTATION)


def _canonical(circuit: CircuitSpec, profiles, pin: str) -> str:
    return readability._canonical_pin(circuit, profiles, pin)


def _reference_nets(circuit: CircuitSpec, profiles) -> dict[str, set[str]]:
    """The source net list in the derived netlist's own spelling."""
    return {
        net.id: {_canonical(circuit, profiles, pin) for pin in net.members}
        for net in circuit.nets
    }


def _reconcile(reference: dict[str, set[str]], plan, profiles) -> dict:
    """Member-by-member, and name-by-name, comparison against a source net list.

    Returns the flat facts a caller asserts on: which source nets came out
    exactly, which members are missing from the drawing's node, which pins it
    joined that the source did not, whether two source nets ended up on one node
    (a short), which declared members have no placed part at all, and — the
    check a swapped pair needs — which source net's node the drawing has filed
    under a *different* net id. Pin membership alone cannot see D+ and D-
    exchanged: each node still holds a consistent set of pins, they are just on
    the wrong net.
    """
    derived = derive_netlist(plan, profiles)
    placed = {part.part_id for part in plan.parts}
    owner: dict[str, str] = {}
    for net_id, members in reference.items():
        for pin in members:
            owner[pin] = net_id
    missing: list[str] = []
    extra: dict[str, list[str]] = {}
    misnamed: list[dict] = []
    exact = 0
    unplaceable: list[str] = []
    for net_id, members in reference.items():
        placed_members = {pin for pin in members if pin.split(".")[0] in placed}
        unplaceable.extend(sorted(members - placed_members))
        if not placed_members:
            continue
        base = sorted(placed_members)[0]
        drawn = set(derived.group_of(base))
        gone = placed_members - drawn
        added = drawn - placed_members
        if gone:
            missing.extend(sorted(gone))
        if added:
            extra[net_id] = sorted(added)
        names = derived.node_names.get(derived.group_of(base), ())
        if names and net_id not in names:
            misnamed.append({"net": net_id, "named": sorted(names)})
        if not gone and not added:
            exact += 1
    shorts = []
    for group in derived.groups:
        owners = sorted({owner.get(pin, "<undeclared>") for pin in group})
        if len(owners) > 1:
            shorts.append({"pins": list(group), "nets": owners})
    return {
        "exact": exact,
        "total": len(reference),
        "missing": sorted(missing),
        "extra": extra,
        "misnamed": misnamed,
        "shorts": shorts,
        "unplaceable": sorted(unplaceable),
    }


def _nc_report(circuit: CircuitSpec, plan, profiles) -> dict:
    """The spec's declared NC pins, and what the drawing did with each.

    Answering against the **declared** list (not against the drawing) is the
    point: a drawing that quietly wired a pin the spec called NC must be caught,
    and only the declaration knows which pin that was.
    """
    derived = derive_netlist(plan, profiles)
    report: dict[str, dict] = {}
    for pin in sorted(readability._canonical_nc_pins(circuit, profiles)):
        node = derived.group_of(pin)
        report[pin] = {
            "in_drawing": pin in derived.pin_group,
            "node": list(node),
            "wired": pin in derived.wired_pins,
            "named": sorted(derived.node_names.get(node, ())),
            "alone": len(node) == 1,
        }
    return report


def _compile_page(circuit: CircuitSpec, presentation: PresentationSpec | None = None):
    return pagecompiler.compile_page(
        circuit,
        presentation or _presentation(),
        _profiles(),
        pagecompiler.PageCompileBudget(page_box=(0, 0, 1170, 825)),
    )


def _categories(result) -> list[str]:
    return list(result.categories())


# --------------------------------------------------------------- the document


def test_the_document_states_the_two_islands_the_task_book_fixes():
    raw = json.loads(PRESENTATION.read_text(encoding="utf-8"))
    spec = _presentation()
    assert spec.grammar_ref == "ic-periphery"
    assert [module.id for module in spec.modules] == ["usb", "serial"]
    for module in spec.modules:
        parts, core = ISLANDS[module.id]
        assert set(module.parts) == parts, module.id
        assert module.core == core, module.id
    assert [part.id for part in _circuit().parts] and (
        {part.id for part in _circuit().parts} == PARTS
    )
    assert sorted(p for module in spec.modules for p in module.parts) == sorted(PARTS)
    # One flow edge, usb -> serial: the receptacle is the inlet, the bridge the load.
    assert [(edge.from_module, edge.to_module) for edge in spec.flow] == [("usb", "serial")]
    # No crystal island and no crystal: a CH340C clocks itself (its XI/XO pads
    # are not even in the CircuitSpec), and a drawing that invented one would be
    # drawing a part that is not in the circuit.
    assert "crystal" not in raw and "X1" not in json.dumps(raw)
    assert all("XI" not in pin and "XO" not in pin
               for net in _circuit().nets for pin in net.members)


def test_the_document_carries_no_lock_no_coordinate_and_no_designator_special_case():
    raw = json.loads(PRESENTATION.read_text(encoding="utf-8"))
    spec = _presentation()
    # 053 sec.4: `userLocks` is the only coordinate entry, and this drawing
    # states none — a page that needs a locked pose is a page the grammar did
    # not draw.
    assert spec.user_locks == []
    assert raw.get("userLocks", []) == []
    assert "partTexts" not in raw, "a per-designator text side is a special case, not a rule"
    for key in ("islands", "seriesBranches", "panelGroups", "serviceLayout"):
        assert key not in raw
    # No pixel coordinate anywhere in the document: the only numbers it states
    # are the flag lead limit and nothing else.
    def numbers(node):
        if isinstance(node, dict):
            for value in node.values():
                yield from numbers(value)
        elif isinstance(node, list):
            for value in node:
                yield from numbers(value)
        elif isinstance(node, (int, float)) and not isinstance(node, bool):
            yield node
    # The only numbers the document states are structural: the schema version,
    # the column count, the stub minimum and the flag lead limit. No coordinate.
    stated = sorted(numbers(raw))
    assert stated == [1, 1, 40, 120], stated
    assert not any(key in raw for key in ("x", "y", "position", "at")), sorted(raw)


def test_port_roles_are_the_circuits_real_net_ids_and_never_a_ground_direction():
    spec = _presentation()
    circuit_ids = {net.id for net in _circuit().nets}
    assert set(spec.port_roles) <= circuit_ids, "a display name is not a net id"
    assert set(spec.port_roles) == {
        "port.TXD", "port.RXD", "port.DTR", "port.RTS", "port.VBUS_5V",
    }
    assert spec.port_roles["port.TXD"] == "output"
    assert spec.port_roles["port.RXD"] == "input"
    assert spec.port_roles["port.DTR"] == "output"
    assert spec.port_roles["port.RTS"] == "output"
    assert spec.port_roles["port.VBUS_5V"] == "load"
    assert set(spec.port_roles.values()) <= set(PORT_DIRECTIONS)
    # The port is `port.DTR`; the pin it carries is the physical `U.DTR#`. The
    # two spellings are allowed to differ, the *net* is what `portRoles` keys.
    members = {net.id: set(net.members) for net in _circuit().nets}
    assert members["port.DTR"] == {"U.DTR#"}
    assert members["port.RTS"] == {"U.RTS#"}
    assert "DTR#" not in spec.port_roles and "RTS" not in spec.port_roles
    # `port.GND` is a real net id but has no direction this schema can state:
    # grounding is carried by the net's class and `sidePreferences["gnd"]`.
    assert "port.GND" not in spec.port_roles
    assert spec.side_for("gnd") == "bottom"


# ---------------------------------------------------------- machine gate + net


def test_the_real_page_compiler_returns_legal_candidates():
    result = _compile_page(_circuit())
    assert result.failures == [], [f.detail for f in result.failures]
    assert _categories(result) == []
    assert result.pages, "a page with no candidate is a refusal, not a success"
    for page in result.pages:
        assert page.verdict == "pass"
        assert page.plan.evidence.hard_violations == []
        assert page.page_evidence.hard_violations == []
    assert result.modules["usb"].ok and result.modules["serial"].ok


def test_every_source_net_is_held_member_by_member_and_under_its_own_name():
    circuit, profiles = _circuit(), _profiles()
    reference = _reference_nets(circuit, profiles)
    result = _compile_page(circuit)
    assert result.pages
    for page in result.pages:
        report = _reconcile(reference, page.plan, profiles)
        assert report["missing"] == [], report
        assert report["extra"] == {}, report
        assert report["shorts"] == [], report
        assert report["unplaceable"] == [], report
        assert report["misnamed"] == [], report
        assert report["exact"] == report["total"] == 11


def test_all_seven_parts_are_really_placed():
    result = _compile_page(_circuit())
    assert result.pages
    for page in result.pages:
        placed = {part.part_id for part in page.plan.parts}
        assert placed == PARTS, sorted(PARTS - placed)
        # A placed part with no pin in the drawing would be a ghost: every one
        # of the seven keeps at least one of its pins on the page.
        derived = derive_netlist(page.plan, _profiles())
        assert {pin.split(".")[0] for pin in derived.pin_points} == PARTS


def test_the_grammars_unbound_part_is_exactly_the_recorded_gap():
    result = _compile_page(_circuit())
    bound = set()
    for module_id in ("usb", "serial"):
        compiled = result.modules[module_id]
        for binding in compiled.grammar.bindings:
            bound.add(binding.part_id)
    # `rail` and `gnd` bindings name their **net**, not a part.
    assert (bound & PARTS) == PARTS - UNBOUND_BY_GRAMMAR
    assert UNBOUND_BY_GRAMMAR == {"D_ESD"}
    # The ESD is left on the free shelf, not refused: the grammar's answer for
    # it is "not mine", which is why the gate cannot be the whole check.
    assert result.failures == []
    # The roles that *are* bound are the ones the role table names.
    usb = {b.part_id: b.role for b in result.modules["usb"].grammar.bindings}
    serial = {b.part_id: b.role for b in result.modules["serial"].grammar.bindings}
    assert usb == {"J_USB": "core", VBUS_NET: "rail", "port.GND": "gnd",
                   "R_CC1": "shunt", "R_CC2": "shunt"}
    assert serial == {"U": "core", VBUS_NET: "rail", "port.GND": "gnd",
                      "C_VCC": "shunt", "C_V3": "shunt"}


def test_the_declared_nc_pin_stays_nc_in_every_candidate():
    circuit, profiles = _circuit(), _profiles()
    result = _compile_page(circuit)
    assert result.pages
    for page in result.pages:
        report = _nc_report(circuit, page.plan, profiles)
        assert report == {
            "U.7": {"in_drawing": True, "node": ["U.7"], "wired": False,
                    "named": [], "alone": True},
        }, report


def test_the_reversible_data_nets_have_no_short_carrier_on_this_esd_symbol():
    """The one structural statement this grammar cannot keep, stated as a test.

    The task book allows `localLabelObligations` for the two mirrored data nets
    (each receptacle pin and each ESD pin named on its own short straight
    carrier). Declared, the `usb` module is refused by the compiler's own 534
    rule: the six-pin ESD array gives `D_ESD.1` no free side, so every candidate
    lane for its short carrier lands on a neighbouring pin tip. The document
    therefore states no obligation, and the gap belongs to the grammar.
    """
    raw = json.loads(PRESENTATION.read_text(encoding="utf-8"))
    assert "localLabelObligations" not in raw, "the gap is recorded, not papered over"
    obliged = dict(raw)
    obliged["localLabelObligations"] = [{
        "nets": [D_PLUS, D_MINUS],
        "note": "each reversible pin is named on its own short straight carrier",
    }]
    result = _compile_page(_circuit(), PresentationSpec.from_dict(obliged))
    assert not result.pages
    assert _categories(result) == ["layout-unsat"]
    detail = result.failures[0].detail
    assert "usb" in result.failures[0].subject
    assert "local-label exception" in detail and "D_ESD.1" in detail


# --------------------------------------------------------------- negative gates


def _mutate(change) -> CircuitSpec:
    """A parsed copy of the real CircuitSpec with one named change applied."""
    payload = json.loads(CIRCUIT.read_text(encoding="utf-8"))
    change(payload)
    return CircuitSpec.from_dict(payload)


def _net(payload: dict, net_id: str) -> dict:
    for item in payload["nets"]:
        if item["id"] == net_id:
            return item
    raise KeyError(net_id)


def test_the_two_data_pairs_exchanged_are_caught_by_the_name_comparison():
    """The gate accepts it: each node is a legal node either way.

    Pin membership alone cannot see this one — the DP node still holds exactly
    the DP pins — so the control records what *does* own the error: the drawing
    files each node under the other net's id, and the name comparison says so.
    """
    def swap(payload: dict) -> None:
        plus, minus = _net(payload, D_PLUS), _net(payload, D_MINUS)
        plus["members"], minus["members"] = minus["members"], plus["members"]

    circuit, profiles = _mutate(swap), _profiles()
    reference = _reference_nets(_circuit(), profiles)
    result = _compile_page(circuit)
    assert result.pages, "the gate is not expected to refuse this shape"
    assert result.failures == []
    for page in result.pages:
        report = _reconcile(reference, page.plan, profiles)
        assert report["missing"] == [] and report["extra"] == {}
        assert {item["net"] for item in report["misnamed"]} == {D_PLUS, D_MINUS}, report
        assert report["misnamed"][0]["named"] != [report["misnamed"][0]["net"]]


def test_the_regulated_v3_pin_tied_to_vbus_is_caught_by_the_source_net_reconciliation():
    def tie(payload: dict) -> None:
        _net(payload, V3_NET)["members"] = [
            pin for pin in _net(payload, V3_NET)["members"] if pin != "U.V3"
        ]
        _net(payload, VBUS_NET)["members"] = sorted(
            [*_net(payload, VBUS_NET)["members"], "U.V3"])
        payload["nets"] = [net for net in payload["nets"] if net["members"]]

    circuit, profiles = _mutate(tie), _profiles()
    reference = _reference_nets(_circuit(), profiles)
    result = _compile_page(circuit)
    assert result.pages, "the gate is not expected to refuse this shape"
    assert result.failures == []
    for page in result.pages:
        report = _reconcile(reference, page.plan, profiles)
        assert report["exact"] < report["total"]
        # U.V3 is pin 4; the source says C_V3.1 is on its node and the drawing
        # says the VBUS rail is.
        assert "U.4" in report["missing"], report
        assert "U.4" in report["extra"][VBUS_NET], report
        assert report["shorts"], report


def test_dropping_a_cc_pull_down_is_refused_by_the_machine_gate():
    def drop(payload: dict) -> None:
        payload["parts"] = [part for part in payload["parts"] if part["id"] != "R_CC1"]
        for net in payload["nets"]:
            net["members"] = [pin for pin in net["members"]
                              if not pin.startswith("R_CC1.")]
        payload["nets"] = [net for net in payload["nets"] if net["members"]]

    result = _compile_page(_mutate(drop))
    assert not result.pages, "a missing part is a drawing of a different circuit"
    assert result.failures
    assert _categories(result) == ["facts-missing"]
    assert "R_CC1" in result.failures[0].detail


def test_wiring_the_nc_pin_to_ground_is_caught_at_parse_and_by_the_nc_reconciliation():
    """Two arms, because the error is refused on two different rungs.

    With the circuit's own `nc[]` standing, `CircuitSpec` will not even load the
    contradiction ("NC is explicit precisely so it cannot contradict the
    wiring"). With the contradiction removed — the wiring kept, the NC dropped —
    the page compiler draws it happily, and then only the NC reconciliation
    against the *declared* NC sees that U.7 left its own node.
    """
    def wire(payload: dict) -> None:
        _net(payload, "port.GND")["members"] = sorted(
            [*_net(payload, "port.GND")["members"], "U.7"])

    payload = json.loads(CIRCUIT.read_text(encoding="utf-8"))
    wire(payload)
    with pytest.raises(CircuitSpecError) as refused:
        CircuitSpec.from_dict(payload)
    assert "U.7" in str(refused.value)

    def wire_and_forget(payload: dict) -> None:
        wire(payload)
        payload["nc"] = []

    circuit, profiles = _mutate(wire_and_forget), _profiles()
    declared = _circuit()
    result = _compile_page(circuit)
    assert result.pages, "the gate is not expected to refuse this shape"
    assert result.failures == []
    for page in result.pages:
        report = _nc_report(declared, page.plan, profiles)
        assert report["U.7"]["wired"] is True, report
        assert report["U.7"]["alone"] is False, report
        assert report["U.7"]["named"] == ["port.GND"], report
