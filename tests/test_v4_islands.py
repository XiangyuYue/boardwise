"""V4 facts -> islands judgement -> compile, including an independent pin census."""
from __future__ import annotations

import json
from pathlib import Path

from boardwise import cli
from boardwise.core.circuitspec import CircuitSpec, SpecOpenInterface
from boardwise.core.layoutplan import LayoutPlan
from boardwise.core.presentationspec import DirectWiringObligation, PresentationSpec
from boardwise.engines import drawapply

FIXTURE = Path(__file__).parent / "fixtures" / "eprj3_synth"


def _profile(symbol_ref: str) -> dict:
    return {
        "kind": "boardwise-symbol-profile", "profileVersion": 1,
        "symbolRef": symbol_ref, "title": "Synthetic R for V4 fixture",
        "body": [-10.0, -20.0, 10.0, 20.0],
        "pins": [
            {"number": "1", "name": "P1", "tip": [0.0, 50.0], "direction": "up"},
            {"number": "2", "name": "P2", "tip": [0.0, -50.0], "direction": "down"},
        ],
    }


def test_v4_seed_reaches_a_compiled_divider_and_covers_every_source_pin(tmp_path):
    circuit = tmp_path / "generated.circuit.json"
    seed = tmp_path / "seed.presentation.json"
    facts = tmp_path / "facts.json"
    profiles = tmp_path / "profiles.json"
    proposal_path = tmp_path / "islands-proposal.json"
    applied = tmp_path / "applied.presentation.json"
    report = tmp_path / "compile.json"
    assert cli.main([
        "draw", "v4-facts", "--file", str(FIXTURE),
        "--out-circuit", str(circuit), "--out-presentation", str(seed),
        "-o", str(facts),
    ]) == 0
    profiles.write_text(json.dumps({"profiles": [
        _profile("dev-U1"), _profile("dev-U2"),
        {
            "kind": "boardwise-symbol-profile", "profileVersion": 1,
            "symbolRef": "PWR-GND", "title": "Ground-GND",
            "body": [-6.0, 0.0, 6.0, 18.0], "pins": [],
        },
    ]}, indent=2), encoding="utf-8")
    assert cli.main([
        "draw", "islands", "propose", "--circuit", str(circuit),
        "--presentation", str(seed), "--profiles", str(profiles),
        "-o", str(proposal_path),
    ]) == 0
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    assert proposal["clusters"]
    first = proposal["clusters"][0]
    proposal["judgement"] = [{
        "islandId": first["islandId"], "verdict": "accept", "name": "Shared signal",
        "role": "primary", "reason": first["evidence"]["anchorCandidate"],
    }]
    proposal_path.write_text(json.dumps(proposal), encoding="utf-8")
    assert cli.main([
        "draw", "islands", "apply", "--proposal", str(proposal_path),
        "--presentation", str(seed), "--out-spec", str(applied),
    ]) == 0

    circuit_obj = CircuitSpec.load(circuit)
    ground = circuit_obj.net("NET2")
    ground.id = "GND"
    ground.cls = "gnd"
    ground.provenance = "ai_asserted"
    circuit_obj.open_interfaces = [
        SpecOpenInterface(net="NET1", direction="input", role="input", provenance="ai_asserted"),
        SpecOpenInterface(net="SIG_A", direction="output", role="output", provenance="ai_asserted"),
    ]
    circuit_obj.dump(circuit)
    presentation_obj = PresentationSpec.load(applied)
    presentation_obj.grammar_ref = "voltage-divider"
    presentation_obj.port_roles = {"NET1": "input", "SIG_A": "output"}
    presentation_obj.direct_wiring_obligations = [DirectWiringObligation(
        nets=["NET1", "SIG_A", "GND"],
        note="AI judgement for the synthetic two-resistor divider",
    )]
    presentation_obj.dump(applied)

    assert cli.main([
        "draw", "compile", "--circuit", str(circuit), "--presentation", str(applied),
        "--profiles", str(profiles), "--page-box", "0,0,1170,825",
        "--json", str(report), "--out", str(tmp_path / "previews"),
    ]) == 0
    result = json.loads(report.read_text(encoding="utf-8"))
    assert result["ok"] is True and result["failures"] == []
    assert len(result["candidates"]) == 1
    assert result["candidates"][0]["verdict"] == "pass"

    plan = LayoutPlan.load(tmp_path / "previews" / "cand1.layout.json")
    change_plan = drawapply.module_plan(
        plan, circuit_obj, presentation_obj, drawapply.load_library(profiles),
        candidate_index=0, lcsc_by_part={"U1": "C1", "U2": "C2"},
        values_by_part={"U1": "10k", "U2": "10k"},
        label_stubs=True, page_box=(0.0, 0.0, 1170.0, 825.0),
    )
    points = {
        part.designator: drawapply.expected_pin_points(part)
        for part in change_plan.change.draw_parts
    }
    for net in circuit_obj.nets:
        for member in net.members:
            part_id, pin = member.split(".", 1)
            point = points[part_id][pin]
            assert any(
                segment.net == net.id and drawapply._on_polyline(point, segment.points)
                for segment in plan.segments
            ), (net.id, member, point)
    assert any(symbol.net == "GND" for symbol in plan.power_symbols)
