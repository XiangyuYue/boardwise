"""038Q11: the SY8089 block compiles offline, and its six nets survive pin by pin.

The task book asks for four things this file can answer without an editor:

* the presentation document is the **minimal** `ic-periphery` statement — one
  module, the circuit's own seven parts, real net ids in `portRoles`, no
  `userLocks`, no coordinate, no designator special case;
* the real compiler turns the pair into legal candidates whose derived netlist
  holds each source net member by member (readability's number-first ruler, the
  same one `_check_netlist` uses) — not merely `ok=True`;
* the gap the grammar leaves is *named*: the output-side parts the ic-periphery
  role table cannot bind (its rail is the core's own supply pin net, not the
  regulator's output rail) are exactly the four this file pins, so a later
  grammar change cannot quietly move them;
* the four negative controls are caught — by the machine gate where the drawing
  really is illegal, and by the source-net reconciliation where it is not.

Nothing here modifies the real inputs: every negative control mutates a parsed
copy in memory. No `outputs/` is read, no editor, no bridge.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec, PresentationSpecError
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawcompiler
from boardwise.engines import readability
from boardwise.engines.readability import derive_netlist

ROOT = Path(__file__).resolve().parents[1]
CIRCUIT = ROOT / "blocklib/modules/circuits/sy8089_buck_3v3.circuit.json"
PRESENTATION = ROOT / "blocklib/specs/sy8089_buck_3v3.presentation.json"
PROFILES = ROOT / "blocklib/symbols/profiles.json"

#: The seven parts, and the one the drawing is arranged around.
PARTS = {"U", "L", "C_IN", "C_OUT", "C_HF", "R_FBT", "R_FBB"}
CORE = "U"
#: What `ic-periphery` leaves unbound on this circuit, and why: its `rail` is the
#: `power` net on the **core's own pins** (`port.VIN`, U pin 4), so a part whose
#: one net is the *output* rail `port.3V3` and whose other net is a core pin net
#: (L on LX, R_FBT on FB) is neither bridge nor shunt, and a part between the
#: output rail and ground (C_OUT, C_HF) touches no core pin net but ground. They
#: are left on the free shelf, not refused. 038Q11 records the gap; closing it is
#: a grammar batch, not this one.
UNBOUND_BY_GRAMMAR = {"C_HF", "C_OUT", "L", "R_FBT"}

#: The real net ids of the CircuitSpec — a `portRoles` key that is a display name
#: ("VIN") rather than one of these addresses nothing.
PORT_NET_IDS = {"port.VIN", "port.3V3", "port.EN", "port.GND"}


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
    """Member-by-member comparison of one drawing against a source net list.

    Returns the flat facts a caller asserts on: which source nets came out
    exactly, which members are missing from the drawing's node, which pins it
    joined that the source did not, whether two source nets ended up on one
    node (a short), and which declared members have no placed part at all.
    """
    derived = derive_netlist(plan, profiles)
    placed = {part.part_id for part in plan.parts}
    owner: dict[str, str] = {}
    for net_id, members in reference.items():
        for pin in members:
            owner[pin] = net_id
    missing: list[str] = []
    extra: dict[str, list[str]] = {}
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
        "shorts": shorts,
        "unplaceable": sorted(unplaceable),
    }


def _compile(circuit: CircuitSpec, presentation: PresentationSpec | None = None):
    return drawcompiler.compile(circuit, presentation or _presentation(),
                                _profiles())


# --------------------------------------------------------------- the document


def test_the_document_is_the_minimal_ic_periphery_statement():
    raw = json.loads(PRESENTATION.read_text(encoding="utf-8"))
    spec = _presentation()
    assert spec.grammar_ref == "ic-periphery"
    assert len(spec.modules) == 1
    module = spec.modules[0]
    assert module.core == CORE
    assert set(module.parts) == PARTS
    assert set(module.parts) == {part.id for part in _circuit().parts}
    # 053 sec.4: `userLocks` is the only coordinate entry, and this drawing
    # states none — a buck that needs a locked pose is a drawing that did not
    # come out of the grammar.
    assert spec.user_locks == []
    assert raw.get("userLocks", []) == []
    for key in ("islands", "seriesBranches", "panelGroups", "serviceLayout"):
        assert key not in raw


def test_port_roles_are_keyed_by_the_circuits_real_net_ids():
    spec = _presentation()
    circuit_ids = {net.id for net in _circuit().nets}
    assert set(spec.port_roles) <= circuit_ids
    assert set(spec.port_roles) == {"port.VIN", "port.3V3", "port.EN"}
    assert spec.port_roles["port.EN"] == "input"
    assert spec.port_roles["port.VIN"] == "source"
    assert spec.port_roles["port.3V3"] == "load"
    # `port.GND` is a real net id but has no direction this schema can state:
    # `portRoles` values are `PORT_DIRECTIONS`, which has no "gnd", and
    # `_port_roles` refuses an empty one. The ground is stated by the net's own
    # class and by `sidePreferences["gnd"]`, so a direction here would be a
    # second, false statement rather than a fuller one.
    with pytest.raises(PresentationSpecError):
        PresentationSpec.from_dict({
            "kind": "boardwise-presentation-spec",
            "specVersion": 1,
            "modules": [],
            "portRoles": {"port.GND": "gnd"},
        })
    # And a display name is not a net id: nothing binds it.
    assert "VIN" not in spec.port_roles


# ---------------------------------------------------------- machine gate + net


def test_the_real_compiler_returns_legal_candidates():
    result = _compile(_circuit())
    assert result.ok, [failure.as_dict() for failure in result.failures]
    assert result.failures == []
    best = result.candidates[0]
    assert best.evidence.hard_violations == []
    assert result.grammar is not None
    roles = {}
    for binding in result.grammar.bindings:
        roles.setdefault(binding.part_id, []).append(binding.role)
    assert roles[CORE] == ["core"]
    assert roles["port.VIN"] == ["rail"]
    assert roles["port.GND"] == ["gnd"]


def test_every_source_net_is_held_member_by_member():
    circuit, profiles = _circuit(), _profiles()
    reference = _reference_nets(circuit, profiles)
    result = _compile(circuit)
    assert result.ok
    for plan in result.candidates:
        report = _reconcile(reference, plan, profiles)
        assert report["missing"] == [], report
        assert report["extra"] == {}, report
        assert report["shorts"] == [], report
        assert report["exact"] == report["total"] == 6


def test_the_grammars_unbound_output_side_is_exactly_the_recorded_gap():
    result = _compile(_circuit())
    # `rail` and `gnd` bindings name their **net**, not a part, so only the
    # part-shaped bindings are compared here.
    bound = {binding.part_id for binding in result.grammar.bindings} & PARTS
    assert PARTS - bound == UNBOUND_BY_GRAMMAR
    assert bound == {CORE, "C_IN", "R_FBB"}
    assert result.grammar.bindings
    # No part was refused as a stray: the grammar's answer for these four is
    # "not mine", not "illegal", which is why the gate cannot be the whole check.
    assert result.failures == []


# --------------------------------------------------------------- negative gates


def _mutate(change) -> CircuitSpec:
    """A parsed copy of the real CircuitSpec with one named change applied."""
    payload = json.loads(CIRCUIT.read_text(encoding="utf-8"))
    change(payload)
    return CircuitSpec.from_dict(payload)


def _move_member(payload: dict, member: str, from_net: str, to_net: str) -> None:
    for net in payload["nets"]:
        if net["id"] == from_net:
            net["members"] = [pin for pin in net["members"] if pin != member]
        if net["id"] == to_net:
            net["members"] = sorted([*net["members"], member])


def _drop_part(payload: dict, part_id: str) -> None:
    payload["parts"] = [part for part in payload["parts"] if part["id"] != part_id]
    for net in payload["nets"]:
        net["members"] = [
            pin for pin in net["members"] if pin.split(".")[0] != part_id
        ]
    payload["nets"] = [net for net in payload["nets"] if net["members"]]


def test_the_inductor_wired_to_vin_is_caught_by_the_source_net_reconciliation():
    """The machine gate accepts it — `VIN→3V3` is still a rail-to-rail shunt shape.

    So the control records *which* check owns this class of error: the per-pin
    comparison against the source net list, not the compiler's legality gate.
    """
    circuit = _mutate(lambda payload: _move_member(
        payload, "L.1", "auto:L.1|U.LX", "port.VIN"))
    profiles = _profiles()
    reference = _reference_nets(_circuit(), profiles)
    result = _compile(circuit)
    assert result.ok, "the gate is not expected to refuse this shape"
    assert result.failures == []
    for plan in result.candidates:
        report = _reconcile(reference, plan, profiles)
        assert report["missing"], report
        # The switch node broke: the core's own LX pin is no longer on L.1's
        # node, and the drawing puts L on the input rail instead.
        assert "U.3" in report["missing"], report
        derived = derive_netlist(plan, profiles)
        assert "C_IN.1" in derived.group_of("L.1"), report
        assert report["exact"] < report["total"]


def test_en_merged_into_vin_is_caught_one_way_or_the_other():
    """Two arms, because two different checks own this error depending on the doc.

    With `portRoles` stating `port.EN` (this block's own document) the vanished
    port is a `facts-missing` refusal — the declaration is what makes a missing
    boundary falsifiable. Without the declaration the compiler draws a merged
    port happily, and then only the source-net reconciliation sees it.
    """
    def merge(payload: dict) -> None:
        _move_member(payload, "U.EN", "port.EN", "port.VIN")
        payload["nets"] = [net for net in payload["nets"] if net["members"]]
        payload["openInterfaces"] = [
            item for item in payload["openInterfaces"] if item["net"] != "port.EN"
        ]

    circuit = _mutate(merge)
    profiles = _profiles()
    reference = _reference_nets(_circuit(), profiles)

    # arm 1: the declared port is gone → the machine gate refuses it
    result = _compile(circuit)
    assert not result.ok
    assert any(
        failure.category == "facts-missing" and "port.EN" in failure.detail
        for failure in result.failures
    ), [failure.as_dict() for failure in result.failures]

    # arm 2: the same merge with the declaration removed → legal drawing of a
    # different circuit, caught by the per-pin comparison
    undeared = json.loads(PRESENTATION.read_text(encoding="utf-8"))
    undeared.pop("portRoles")
    quiet = PresentationSpec.from_dict(undeared)
    plain = _compile(circuit, quiet)
    assert plain.ok, [failure.as_dict() for failure in plain.failures]
    for plan in plain.candidates:
        report = _reconcile(reference, plan, profiles)
        assert report["missing"] or report["extra"] or report["shorts"], report
        derived = derive_netlist(plan, profiles)
        # U.EN is pin 1; it now sits on the input rail's node, which the source
        # never says (the derived netlist keys every pin by its number)
        assert "C_IN.1" in derived.group_of("U.1"), report


def test_dropping_the_top_feedback_resistor_is_refused_by_the_machine_gate():
    circuit = _mutate(lambda payload: _drop_part(payload, "R_FBT"))
    result = _compile(circuit)
    assert not result.ok, "a missing part is a drawing of a different circuit"
    assert result.failures


def test_dropping_the_output_capacitor_is_refused_by_the_machine_gate():
    circuit = _mutate(lambda payload: _drop_part(payload, "C_OUT"))
    result = _compile(circuit)
    assert not result.ok
    assert result.failures
