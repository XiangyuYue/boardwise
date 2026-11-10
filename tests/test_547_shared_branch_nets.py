"""547S: one contract for "which net does this pair share" (the 547C1 split).

Before this batch four readers answered that question independently:

* ``drawcompiler._branch_slot`` / ``_shared_nets`` — the seat,
* ``placement.relation_points_between`` — the ruler the search and the gate
  measure every pin-kind relation with,
* ``drawcompiler._shared_net_of`` — the repair pass that walks a broken relation,
* ``drawcompiler._branch_lane_edges`` — the net a same-line lane is levelled on.

**What was actually wrong (measured, not assumed).** The old ``_shared_nets``
did not seat on the signal: its "prefer a non-return net" rule treated ``power``
as non-return, so a branch sharing ``KEY1`` and ``3V3`` seated on **``3V3``** —
on the 547 page all four keys anchored on one supply pin. The old sorted ruler
in ``relation_points_between`` also read ``3V3`` there (``3V3`` sorts before
``KEY1``), so seat and ``near`` happened to agree on *that* pair while the
index/lane and the repair reading could still disagree with them; the measured
symptom was the four keys pulled onto one column by a ``near`` measured on the
rail. Nothing was "seated on the signal and measured on the rail" — the split
was between *which net a reader picked* (sorted first vs non-return) and *how
far apart the readings were allowed to drift*.

**547S's answer** is one order for all four readers — declared **signal** first,
then every other **non-``gnd``** net in the old sorted order, then **``gnd``**
last — applied by the seat, the search and gate ruler
(``relation_points_between``), the repair pass (``_shared_net_of``) and the lane
edges (``_branch_lane_edges``). That keeps ``VCC``+``GND`` on ``VCC`` and
``undeclared``+``GND`` on the non-ground net, exactly as the old non-return rule
did, and it puts ``KEY``+``3V3`` on the ``KEY`` pad.

This module pins the contract and its four readers. It is written against the
**shape** — a two-terminal part with a declared signal net and a rail in common
— never against the 547 names; the fixture uses KEY/LED/C ids only because that
is the shape, and the rule itself reads nothing but the net class.

The negative control lives outside the file (task book 547S): forcing the
contract back to plain ``sorted`` must turn these tests red; the run is recorded
in ``evidence/547/s/negative_control_sorted_retry.txt``.
"""

from __future__ import annotations

import copy
from types import SimpleNamespace

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core import presentationspec as ps
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawcompiler as dc
from boardwise.engines import placement


def _pin(number, name, tip, direction, length=10.0):
    return {"number": number, "name": name, "tip": tip, "direction": direction,
            "length": length, "pinType": "passive"}


def _symbol(ref, body, pins):
    return {"kind": "boardwise-symbol-profile", "profileVersion": 1,
            "symbolRef": ref, "title": ref, "body": body, "pins": pins,
            "source": "test fixture (547S)"}


def _profiles():
    return {
        "MCU": _symbol(
            "MCU", [-40.0, -40.0, 40.0, 40.0],
            [_pin("PC6", "PC6", [50.0, 5.0], "right"),
             _pin("PB15", "PB15", [50.0, -5.0], "right"),
             _pin("PB13", "PB13", [50.0, -15.0], "right"),
             _pin("PA4", "PA4", [50.0, -25.0], "right"),
             _pin("PA3", "PA3", [50.0, -35.0], "right"),
             _pin("VDD", "VDD", [-50.0, 25.0], "left"),
             _pin("VSS", "VSS", [-50.0, 15.0], "left")],
        ),
        "KEY": _symbol("KEY", [-12.0, -6.5, 12.0, 6.5],
                       [_pin("1", "1", [0.0, 20.0], "up"),
                        _pin("2", "2", [0.0, -20.0], "down")]),
        "LED": _symbol("LED", [-7.0, -5.5, 7.0, 5.5],
                       [_pin("1", "A", [-20.0, 0.0], "left"),
                        _pin("2", "K", [20.0, 0.0], "right")]),
        "C": _symbol("C", [-5.5, -8.5, 5.5, 8.5],
                     [_pin("1", "1", [-20.0, 0.0], "left"),
                      _pin("2", "2", [20.0, 0.0], "right")]),
    }


#: Where each pin of the fixture sits, in symbol-local terms — what the ruler
#: turns into a point, so a test can say **which pin** was measured.
PIN_POINTS = {
    "U1.PC6": (50.0, 5.0), "U1.PB15": (50.0, -5.0), "U1.PB13": (50.0, -15.0),
    "U1.PA4": (50.0, -25.0), "U1.PA3": (50.0, -35.0),
    "U1.VDD": (-50.0, 25.0), "U1.VSS": (-50.0, 15.0),
    "S1.1": (60.0, 5.0), "S2.1": (60.0, -5.0), "S3.1": (60.0, -15.0),
    "S4.1": (60.0, -25.0), "D1.1": (60.0, -35.0), "C1.1": (-20.0, 6.0),
}


def _circuit(extra_nets=()):
    parts = [
        {"id": "U1", "symbolRef": "MCU", "value": "MCU"},
        {"id": "S1", "symbolRef": "KEY", "value": "KEY"},
        {"id": "S2", "symbolRef": "KEY", "value": "KEY"},
        {"id": "S3", "symbolRef": "KEY", "value": "KEY"},
        {"id": "S4", "symbolRef": "KEY", "value": "KEY"},
        {"id": "D1", "symbolRef": "LED", "value": "LED"},
        {"id": "C1", "symbolRef": "C", "value": "100nF"},
        {"id": "C2", "symbolRef": "C", "value": "100nF"},
    ]
    nets = [
        {"id": "3V3", "class": "power",
         "members": ["U1.VDD", "C1.1", "S1.2", "S2.2", "S3.2", "S4.2"]},
        {"id": "VCC", "class": "power", "members": ["C2.1"]},
        {"id": "GND", "class": "gnd",
         "members": ["U1.VSS", "C1.2", "C2.2", "D1.2"]},
        {"id": "KEY1", "class": "signal", "members": ["U1.PC6", "S1.1"]},
        {"id": "KEY2", "class": "signal", "members": ["U1.PB15", "S2.1"]},
        {"id": "KEY3", "class": "signal", "members": ["U1.PB13", "S3.1"]},
        {"id": "KEY4", "class": "signal", "members": ["U1.PA4", "S4.1"]},
        {"id": "LED1", "class": "signal", "members": ["U1.PA3", "D1.1"]},
    ]
    nets += [dict(n) for n in extra_nets]
    return {"kind": "boardwise-circuit-spec", "specVersion": 1, "parts": parts,
            "nets": [dict(n, provenance="ai_asserted") for n in nets], "nc": []}


def _circuit_spec(extra_nets=()):
    return CircuitSpec.from_dict(copy.deepcopy(_circuit(extra_nets)))


def _book():
    return {p.symbol_ref: p for p in
            (SymbolProfile.from_dict(copy.deepcopy(v)) for v in _profiles().values())}


def _presentation():
    return ps.PresentationSpec.from_dict({
        "kind": "boardwise-presentation-spec", "specVersion": 1,
        "grammarRef": "ic-periphery",
        "sidePreferences": {"input": "right", "output": "right", "load": "right",
                            "source": "left", "power": "top", "gnd": "bottom"},
        "modules": [{"id": "mcu", "role": "host island", "grammarRef": "ic-periphery",
                     "core": "U1",
                     "parts": ["U1", "S1", "S2", "S3", "S4", "D1", "C1", "C2"]}],
        "moduleOrder": ["mcu"],
    })


def _binding(circuit, presentation):
    return dc.bind_grammar(circuit, presentation, _book())


def _slot(circuit, presentation, part_id, owner="U1"):
    return dc._branch_slot(
        circuit, presentation, _binding(circuit, presentation),
        part_id, "shunt", owner, "h", {},
    )


def _points(circuit, part_id, owner="U1"):
    """The two points the compiler's ruler measures a branch's ``near`` on."""
    return dc._points_for_relation(
        circuit,
        SimpleNamespace(kind="near", subject=part_id, object=owner),
        origin_of=lambda pid: {"U1": (0.0, 0.0), "S1": (80.0, 0.0),
                               "S2": (80.0, -10.0), "S3": (80.0, -20.0),
                               "S4": (80.0, -30.0), "D1": (80.0, -40.0),
                               "C1": (-40.0, 0.0)}.get(pid),
        pin_of=lambda pid, token: PIN_POINTS.get(f"{pid}.{token}"),
    )


# --------------------------------------------------------------- 1. the seat


def test_key_branch_seats_on_its_own_signal_net():
    """A branch sharing ``KEY1`` and ``3V3`` is seated from the KEY pad."""
    circuit, presentation = _circuit_spec(), _presentation()
    slot = _slot(circuit, presentation, "S1")
    assert slot is not None
    assert slot.shared_net == "KEY1"
    assert slot.pin_shared == "1"
    assert slot.other_net == "3V3"


def test_led_branch_keeps_the_old_reading():
    """A branch sharing ``LED1`` and ``GND`` reads exactly as it always did.

    The old rule already preferred a non-ground common net, so this case is the
    proof that the new contract did not re-order anything else.
    """
    circuit, presentation = _circuit_spec(), _presentation()
    slot = _slot(circuit, presentation, "D1")
    assert slot is not None
    assert slot.shared_net == "LED1"
    assert slot.pin_shared == "1"
    assert slot.other_net == "GND"


def test_pure_rail_fallback_is_unchanged():
    """With only rails in common the answer is the old sorted one (``3V3``)."""
    circuit, presentation = _circuit_spec(), _presentation()
    slot = _slot(circuit, presentation, "C1")
    assert slot is not None
    assert slot.shared_net == "3V3"
    assert slot.pin_shared == "1"
    assert slot.other_net == "GND"


def test_all_four_siblings_read_their_own_pad():
    """Four identical branches: none of them may seat on the shared rail."""
    circuit, presentation = _circuit_spec(), _presentation()
    seats = {part: _slot(circuit, presentation, part) for part in
             ("S1", "S2", "S3", "S4")}
    assert [seats[part].shared_net for part in ("S1", "S2", "S3", "S4")] == [
        "KEY1", "KEY2", "KEY3", "KEY4"]
    assert len({seats[part].shared_net for part in seats}) == 4
    assert {seats[part].pin_shared for part in seats} == {"1"}


# ------------------------------------------------------- 2. the four readers


def test_relation_points_measure_the_seat_net():
    """The ruler reads the pin of the seat's net — the 547C1 split is closed."""
    circuit, presentation = _circuit_spec(), _presentation()
    expected = {"S1": "U1.PC6", "S2": "U1.PB15", "S3": "U1.PB13",
                "S4": "U1.PA4"}
    for part_id, owner_pin in expected.items():
        slot = _slot(circuit, presentation, part_id)
        points = _points(circuit, part_id)
        assert points is not None, part_id
        assert points[0] == PIN_POINTS[f"{part_id}.1"], part_id
        assert points[1] == PIN_POINTS[owner_pin], part_id
        # the rail pad is the reading this batch removed: VDD is what the old
        # sorted-first ruler measured every one of these four on
        assert points[1] != PIN_POINTS["U1.VDD"], part_id
        assert slot is not None and slot.shared_net == f"KEY{part_id[1:]}"


def test_repair_reading_agrees_with_the_seat():
    """``_shared_net_of`` (the repair pass) walks the seat's net."""
    circuit, presentation = _circuit_spec(), _presentation()
    binding = _binding(circuit, presentation)
    prepare = dc._prepare(circuit, presentation, binding, _book(),
                          dc.CompileBudget())
    ctx = prepare.context
    assert ctx is not None
    for part_id in ("S1", "S2", "S3", "S4", "D1", "C1"):
        slot = _slot(circuit, presentation, part_id)
        assert dc._shared_net_of(ctx, part_id, "U1") == slot.shared_net


def test_lane_edge_is_levelled_on_the_seat_net():
    """``_branch_lane_edges`` carries the same net the seat used."""
    circuit = _circuit_spec()
    lanes = {"S1": ("h", "row-1", ["S1", "U1"]),
             "U1": ("h", "row-1", ["S1", "U1"]),
             "S4": ("h", "row-1", ["S1", "S4"])}
    binding = SimpleNamespace(constraints=[
        SimpleNamespace(kind=dc.SAME_ROW, subject="S1", object="U1"),
    ])
    edges = dc._branch_lane_edges(circuit, binding, lanes)
    # S1 and U1 share KEY1 *and* 3V3: the lane is levelled on the signal
    assert edges["row-1"] == [("S1", "U1", "KEY1")]

    # S1 and S4 share only the rail — no signal in common, so the old sorted
    # order stands and the edge keeps the rail
    binding = SimpleNamespace(constraints=[
        SimpleNamespace(kind=dc.SAME_ROW, subject="S1", object="S4"),
    ])
    edges = dc._branch_lane_edges(circuit, binding, lanes)
    assert edges["row-1"] == [("S1", "S4", "3V3")]


# --------------------------------------------------- 3. the contract itself


def test_signal_first_order_is_the_one_contract():
    circuit = _circuit_spec()
    order = placement.shared_net_order(
        ["KEY1", "3V3"], ["3V3", "KEY1"],
        lambda net: dc._circuit_net_class(circuit, net))
    assert order == ["KEY1", "3V3"]
    # the same call with no resolver is the old sorted reading, verbatim
    assert placement.shared_net_order(["KEY1", "3V3"], ["3V3", "KEY1"]) == [
        "3V3", "KEY1"]


def test_no_ambiguity_keeps_the_old_order():
    """Rails only, and a resolver that declares nothing, both stay as they were."""
    circuit = _circuit_spec()
    assert placement.shared_net_order(
        ["3V3", "GND"], ["GND", "3V3"],
        lambda net: dc._circuit_net_class(circuit, net)) == ["3V3", "GND"]
    assert placement.shared_net_order(
        ["3V3", "GND"], ["GND", "3V3"]) == ["3V3", "GND"]
    assert placement.shared_net_order(
        ["A_UNNAMED", "B_UNNAMED"], ["B_UNNAMED", "A_UNNAMED"],
        lambda net: "") == ["A_UNNAMED", "B_UNNAMED"]


def test_undeclared_class_is_not_promoted():
    """A net with no stated class is not a signal: the old sorted order stands.

    ``CircuitSpec`` fills an omitted class with ``signal`` while parsing, so the
    empty class is held at the two places it can actually occur — the search's
    own netlist view (:class:`placement.PlacementNet`, whose default is ``""``)
    and a resolver that answers nothing. Neither may be promoted over a rail.
    """
    assert placement.PlacementNet(net_id="X").cls == ""
    classes = {"X": "", "3V3": "power"}
    assert placement.shared_net_order(
        ["X", "3V3"], ["3V3", "X"],
        lambda net_id: classes[net_id]) == ["3V3", "X"]
    assert placement.shared_net_order(
        ["X", "3V3"], ["3V3", "X"], lambda net_id: "") == ["3V3", "X"]
    assert dc._circuit_net_class(_circuit_spec(), "no-such-net") == ""


def test_undeclared_never_beats_a_declared_signal():
    """Promotion is for declared signals only; undeclared keeps its sorted place."""
    classes = {"SIG_B": "signal", "0_UNNAMED": ""}
    assert placement.shared_net_order(
        ["0_UNNAMED", "SIG_B"], ["SIG_B", "0_UNNAMED"],
        lambda net: classes[net]) == ["SIG_B", "0_UNNAMED"]
    # ... and a rail-first page with no declared signal is byte-for-byte old
    assert placement.shared_net_order(
        ["3V3", "0_UNNAMED"], ["0_UNNAMED", "3V3"],
        lambda net: classes.get(net, "power")) == ["0_UNNAMED", "3V3"]


def test_vcc_and_gnd_keep_the_non_ground_rail():
    """``VCC``+``GND`` seats on ``VCC`` — a decoupling anchor may not move to GND.

    The regression this pins: a first 547S shape returned sorted order whenever
    no *signal* was in common, which put a capacitor on ``GND`` instead of
    ``VCC`` (``GND`` sorts before ``VCC``). Ground always sorts last.
    """
    circuit = _circuit_spec()
    seat = dc._shared_nets(
        circuit, dc._part_nets(circuit, "C2"), {"VCC", "GND"},
    )
    assert seat == ["VCC", "GND"]
    # the old `_shared_nets` "prefer a non-return net" rule says VCC too; the
    # regression shape said GND, and that is the one line this test pins
    assert seat[0] == "VCC"
    assert placement.shared_net_order(
        dc._part_nets(circuit, "C2").values(), ["VCC", "GND"],
        lambda net: dc._circuit_net_class(circuit, net)) == ["VCC", "GND"]


def test_undeclared_and_gnd_keep_the_non_ground_net():
    """An undeclared net + ``GND`` keeps the old "prefer the non-return" answer."""
    classes = {"X": "", "GND": "gnd"}
    assert placement.shared_net_order(
        ["X", "GND"], ["GND", "X"], lambda net: classes[net]) == ["X", "GND"]
    # ... and the declared-signal band still leads when there is one
    classes["SIG"] = "signal"
    assert placement.shared_net_order(
        ["GND", "SIG", "X"], ["X", "GND", "SIG"],
        lambda net: classes[net]) == ["SIG", "X", "GND"]
