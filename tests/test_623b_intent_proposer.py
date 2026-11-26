"""623B: what the propose report could not answer about its own draft.

Four readings, each named after the digging entry that found it:

* 623B-03 — a flow edge carried `from`/`to`/`mainPath` and no net evidence; the
  nets were computed to build the edge and then dropped, so a reader could not
  ask "on which net".
* 623B-02 — two groups that meet only on a ground net were turned into an arrow.
  Ground is the reference, not a direction; the pair is named as undetermined.
* 623B-01 — a part declared by two blocks is written into both modules (the
  contract says so), but the report never said so: the robot contract's `U1` is
  in `senseU` and `senseW` and both cores name it.
* 623B-04 — a block part the netlist does not carry was silently dropped.
"""

from __future__ import annotations

import test_109_intent_proposer as t109

from boardwise.core import designintent as di
from boardwise.core.circuitspec import CIRCUIT_SPEC_VERSION, CircuitSpec
from boardwise.engines import intentproposer as ip

PROV = "verified_recipe"


def _block(block_id: str, kind: str, parts) -> dict:
    return t109.block(block_id, kind, parts)


def _gnd_only_circuit() -> CircuitSpec:
    """Two groups that meet on nothing but GND."""

    def part(part_id: str, symbol: str, value: str) -> dict:
        return {"id": part_id, "symbolRef": symbol, "value": value, "provenance": PROV}

    def net(net_id: str, cls: str, members: list[str]) -> dict:
        return {"id": net_id, "class": cls, "members": members, "provenance": PROV}

    return CircuitSpec.from_dict({
        "kind": "boardwise-circuit-spec",
        "specVersion": CIRCUIT_SPEC_VERSION,
        "parts": [
            part("USB1", "USB-A-C1", "USB-A"),
            part("U4", "AMS1117-C1", "AMS1117-3.3"),
            part("U1", "STM32-C1", "STM32F103"),
            part("C1", "C0603-C1", "100nF"),
        ],
        "nets": [
            net("VCC", "power", ["USB1.1", "U4.1"]),
            net("+5V", "power", ["U1.1"]),
            net("GND", "gnd", ["USB1.4", "U4.2", "U1.2", "C1.2"]),
        ],
        "openInterfaces": [
            {"net": "VCC", "direction": "input", "role": "rail", "part": "USB1",
             "provenance": PROV},
        ],
    })


def test_a_flow_edge_names_the_net_that_carried_it():
    proposal = t109.robot_proposal()
    rows = proposal.report["flow"]["edges"]
    assert rows, proposal.report["flow"]
    for row in rows:
        assert isinstance(row["nets"], list) and row["nets"], row
    inlet_to_sense = next(
        row for row in rows if (row["from"], row["to"]) == ("inlet", "senseU")
    )
    assert "VCC" in inlet_to_sense["nets"], inlet_to_sense


def test_a_pair_that_meets_only_on_ground_is_marked_not_read_as_flow():
    proposal = ip.propose(
        t109.contract(blocks=[
            _block("inlet", "power-entry", ["USB1", "U4"]),
            _block("sense", t109.di.KIND_CURRENT_SENSE, ["U1", "C1"]),
        ]),
        _gnd_only_circuit(),
    )
    rows = proposal.report["flow"]["edges"]
    assert len(rows) == 1, rows
    edge = rows[0]
    assert edge["nets"] == ["GND"], edge
    assert edge["groundOnly"] is True, edge
    # Adjacency stays a reading; what the reader gets is the truth about it: this
    # pair is connected through the reference net, not through a signal.
    assert all(not item["mainPath"] for item in rows), rows


def test_a_part_two_blocks_declare_is_named_in_the_report():
    proposal = t109.robot_proposal()
    assert proposal.report["sharedParts"] == [
        {"part": "U1", "modules": ["senseU", "senseW"]}
    ]
    # The membership and the contract's own `core` statement are NOT erased: the
    # disclosure is additive, both modules still list the part and name it.
    for module_id in ("senseU", "senseW"):
        module = t109.module_of(proposal, module_id)
        assert "U1" in module.parts
        assert module.core == "U1", t109.row_of(proposal, module_id)


def test_a_block_part_the_netlist_does_not_carry_is_named():
    proposal = ip.propose(
        t109.contract(blocks=[_block("front", "ldo", ["U1", "J9"])]),
        t109.robot_circuit(),
    )
    assert proposal.report["unresolvedParts"] == [
        {"part": "J9", "modules": ["front"]}
    ]
    assert any("J9" in note for note in proposal.notes), proposal.notes
    assert any("J9" in note for note in proposal.report["notes"]), proposal.report["notes"]


def test_without_a_circuit_nothing_is_claimed_about_parts():
    proposal = ip.propose(
        di.DesignIntent.load(t109.FOC_CONTRACT),
    )
    assert proposal.report["unresolvedParts"] == []
    assert proposal.report["sharedParts"] == [
        {"part": "U1", "modules": ["senseU", "senseW"]}
    ]
