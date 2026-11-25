"""571-D: a pin keeps its four-field identity on the drawing line (or is refused).

The hole batch (571 §1 「会造假结果」 row 2) measured the drawing line folding
:class:`boardwise.core.netlist.PinRef` — ``(designator, number, source_id,
pin_key)`` — onto the pair ``(designator, number)`` and keeping whichever entry
came last. On the P4 payload two units of ``U1`` both carry pin ``"1"`` on
``NET_A`` / ``NET_B``; the pair projection returned one entry reading ``NET_B``,
``NET_A`` vanished, and ``islands`` then read that pin as connected to nothing —
a fabricated answer, not a missing one.

Three claims, one ruler:

* ``live_pin_nets`` keeps its ``(designator, number)`` shape (twelve CLI call
  sites read it) but **refuses** a collision of two different pins on different
  nets instead of overwriting. Two pins of one number on the *same* net still
  answer once — that pair is a faithful reading;
* ``live_pin_refs`` answers in ``PinRef``, so two units stay two pins;
* ``moveblock.pin_key``, ``subcircuit._pin_key`` and both of subcircuit's former
  ``partition(".")`` sites split on the **last** dot and re-spell the pin number
  (``"01"`` is ``"1"``, ``"10"`` is not), which is
  :meth:`boardwise.core.netlist.PinRef.parse`'s documented law.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from boardwise.core.changeplan import PlanConnection
from boardwise.core.netlist import PinRef
from boardwise.engines import moveblock, patchpin, subcircuit

#: The probe payload from ``outputs/hole571/d/probes/probe_pinid.py`` (P4).
TWO_UNITS_TWO_NETS = {
    "components": {
        "uidA": {"props": {"Designator": "U1"}, "pinInfoMap": {"1": {"net": "NET_A"}}},
        "uidB": {"props": {"Designator": "U1"}, "pinInfoMap": {"1": {"net": "NET_B"}}},
    }
}

#: The same two units, agreeing on the net: one pair is then the whole truth.
TWO_UNITS_ONE_NET = {
    "components": {
        "uidA": {"props": {"Designator": "U1"}, "pinInfoMap": {"1": {"net": "NET_A"}}},
        "uidB": {"props": {"Designator": "U1"}, "pinInfoMap": {"1": {"net": "NET_A"}}},
    }
}


# ------------------------------------------------------- D-1: refuse, never fake


def test_two_units_on_two_nets_are_refused_by_name() -> None:
    """The P4 reading: one pair, two pins, two nets — a named ValueError, no pick."""
    with pytest.raises(ValueError) as caught:
        patchpin.live_pin_nets(TWO_UNITS_TWO_NETS)
    assert isinstance(caught.value, patchpin.LivePinConflict)
    message = str(caught.value)
    for token in ("U1", "'1'", "uidA", "uidB", "NET_A", "NET_B"):
        assert token in message, f"{token!r} missing from the refusal: {message}"


def test_the_refusal_reaches_the_islands_reading() -> None:
    """`moveblock.islands` is the consumer that used to report 「connects to nothing」."""
    with pytest.raises(ValueError) as caught:
        moveblock.islands(patchpin.live_pin_nets(TWO_UNITS_TWO_NETS))
    assert "NET_A" in str(caught.value) and "NET_B" in str(caught.value)


def test_live_pin_refs_keeps_both_units_apart() -> None:
    """The identity-keeping entry point: two same-number pins, two entries."""
    refs = patchpin.live_pin_refs(TWO_UNITS_TWO_NETS)
    assert len(refs) == 2, f"the pair projection came back: {refs!r}"
    assert set(refs) == {
        PinRef(designator="U1", number="1", source_id="uidA", pin_key="1"),
        PinRef(designator="U1", number="1", source_id="uidB", pin_key="1"),
    }
    assert refs[PinRef("U1", "1", "uidA", "1")] == "NET_A"
    assert refs[PinRef("U1", "1", "uidB", "1")] == "NET_B"


def test_two_units_on_one_net_answer_once() -> None:
    """Negative control: identical nets are not a conflict — no false refusal."""
    live = patchpin.live_pin_nets(TWO_UNITS_ONE_NET)
    assert live == {("U1", "1"): "NET_A"}
    assert len(patchpin.live_pin_refs(TWO_UNITS_ONE_NET)) == 2


def test_a_normal_payload_reads_exactly_as_before() -> None:
    """The twelve call sites' contract: same keys, same order, same names."""
    payload = {
        "components": {
            "u2": {
                "props": {"Designator": "R1"},
                "pinInfoMap": {"2": {"net": "VOUT"}, "1": {"net": ""}},
            }
        }
    }
    live = patchpin.live_pin_nets(payload)
    assert live == {("R1", "2"): "VOUT", ("R1", "1"): ""}
    assert list(live) == [("R1", "2"), ("R1", "1")]
    assert patchpin.live_pin_nets({"text": json.dumps(payload)}) == live


# -------------------------------------------------- D-3: the last dot is the split


def test_a_dotted_designator_keeps_its_dot() -> None:
    """``U1.1.2`` is designator ``U1.1`` pin ``2`` — never designator ``U1`` pin ``1.2``."""
    assert moveblock.pin_key("U1.1.2") == ("U1.1", "2")
    assert moveblock.pin_key("U1.1.2") != ("U1", "1.2")
    assert moveblock.pin_key("U9.3.1") == ("U9.3", "1")


def test_subcircuit_reads_to_pin_with_the_same_ruler() -> None:
    """Both former ``partition(".")`` sites now go through the one helper."""
    plan = SimpleNamespace(
        change=SimpleNamespace(
            connections=[
                PlanConnection(
                    designator="R1",
                    pin="2",
                    net=subcircuit.NODE_X,
                    kind="wire",
                    to_pin="U1.1.2",
                )
            ]
        )
    )
    assert subcircuit.node_members(plan) == [("R1", "2"), ("U1.1", "2")]
    assert subcircuit.wire_target(
        plan.change.connections[0], {("U1.1", "2"): (10.0, 20.0)}
    ) == (10.0, 20.0)


def test_a_bare_designator_is_not_a_pin_reference() -> None:
    """No dot: refused by name rather than read as a pin called ``""``."""
    with pytest.raises(ValueError):
        moveblock.pin_key("U1")
    with pytest.raises(ValueError):
        moveblock.pin_key("U1.")


# ----------------------------------------------- D-2: one spelling per pin number


def test_leading_zeros_are_one_pin_and_ten_is_not_one() -> None:
    """``01`` == ``1``; ``10`` stays ``10``; a spelled pin number is left alone."""
    assert moveblock.pin_key("U1.01") == moveblock.pin_key("U1.1") == ("U1", "1")
    assert moveblock.pin_key("U1.10") == ("U1", "10")
    assert moveblock.pin_key("U1.10") != moveblock.pin_key("U1.1")
    assert moveblock.pin_key("U1. 1 ") == ("U1", "1")
    assert moveblock.pin_key("U1.NC1") == ("U1", "NC1")
    assert moveblock.pin_key("U1.PAD.01") == ("U1.PAD", "1")
    assert subcircuit._pin_key("U1", "01") == ("U1", "1") == subcircuit._pin_key(" U1 ", "1")
