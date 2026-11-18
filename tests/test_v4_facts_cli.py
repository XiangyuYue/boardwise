"""The offline `draw v4-facts` command surface and its honest failures."""
from __future__ import annotations

import json
from pathlib import Path

from boardwise import cli

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "eprj3_synth"


def test_v4_facts_is_registered_without_changing_the_legacy_draw_invocation():
    parsed = cli.build_parser().parse_args(["draw", "v4-facts", "--file", "x"])
    assert (parsed.command, parsed.draw_command, parsed.file) == ("draw", "v4-facts", "x")
    legacy = cli.build_parser().parse_args(["draw", "--spec", "x.json", "--from", "y.epro2"])
    assert legacy.draw_command is None


def test_v4_facts_emits_machine_json_and_keeps_the_summary_on_stderr(capsys):
    code = cli.main(["draw", "v4-facts", "--file", str(FIXTURE)])
    printed = capsys.readouterr()
    assert code == 0, printed.err
    payload = json.loads(printed.out)
    assert payload["schema"] == "boardwise.v4-facts/1"
    assert {item["name"] for item in payload["nets"]} >= {"GND", "SIG_A"}
    assert "open question(s)" in printed.err


def test_v4_facts_out_is_deterministic_and_bad_input_is_quiet(tmp_path, capsys):
    out = tmp_path / "facts.json"
    code = cli.main(["draw", "v4-facts", "--file", str(FIXTURE), "-o", str(out)])
    assert code == 0
    first = out.read_bytes()
    assert cli.main(["draw", "v4-facts", "--file", str(FIXTURE), "-o", str(out)]) == 0
    assert out.read_bytes() == first
    capsys.readouterr()
    assert cli.main(["draw", "v4-facts", "--file", str(tmp_path / "missing")]) == 2
    printed = capsys.readouterr()
    assert "draw v4-facts:" in printed.err
    assert "Traceback" not in printed.err


def test_v4_facts_can_emit_an_enriched_circuit_spec(tmp_path, capsys):
    from boardwise.core.circuitspec import CircuitSpec, SpecNet, SpecPart

    source = tmp_path / "base.circuit.json"
    CircuitSpec(
        parts=[SpecPart(id="U1", symbol_ref="R")],
        nets=[
            SpecNet(id="GND", members=["U1.1"]),
            SpecNet(id="SIG_A", members=["U1.2"]),
        ],
    ).dump(source)
    out_circuit = tmp_path / "enriched.circuit.json"
    out_facts = tmp_path / "facts.json"
    code = cli.main([
        "draw", "v4-facts", "--file", str(FIXTURE),
        "--circuit", str(source), "--out-circuit", str(out_circuit),
        "-o", str(out_facts),
    ])
    printed = capsys.readouterr()
    assert code == 0, printed.err
    enriched = CircuitSpec.load(out_circuit)
    by_name = {net.id: net for net in enriched.nets}
    assert (by_name["GND"].scope, by_name["GND"].cls) == ("project", "gnd")
    assert (by_name["SIG_A"].scope, by_name["SIG_A"].cls) == ("page", "signal")
    report = json.loads(out_facts.read_text(encoding="utf-8"))["circuitEnrichment"]
    assert report["conflicts"] == []


def test_out_circuit_without_a_base_builds_the_full_model_netlist(tmp_path, capsys):
    from boardwise.core.circuitspec import CircuitSpec

    out_circuit = tmp_path / "generated.circuit.json"
    out_facts = tmp_path / "facts.json"
    code = cli.main([
        "draw", "v4-facts", "--file", str(FIXTURE),
        "--out-circuit", str(out_circuit), "-o", str(out_facts),
    ])
    printed = capsys.readouterr()
    assert code == 0, printed.err
    spec = CircuitSpec.load(out_circuit)
    assert [part.id for part in spec.parts] == ["U1", "U2"]
    assert spec.net("SIG_A").members == ["U1.1", "U2.1"]
    facts = json.loads(out_facts.read_text(encoding="utf-8"))
    assert facts["circuitProduction"]["singleMemberNets"] == ["NET1", "NET2"]
    assert facts["circuitEnrichment"]["unmatchedFacts"] == ["GND"]


def test_out_presentation_writes_a_seed_not_a_functional_partition(tmp_path, capsys):
    from boardwise.core.presentationspec import PresentationSpec

    out = tmp_path / "seed.presentation.json"
    facts_out = tmp_path / "facts.json"
    code = cli.main([
        "draw", "v4-facts", "--file", str(FIXTURE),
        "--out-presentation", str(out), "-o", str(facts_out),
    ])
    printed = capsys.readouterr()
    assert code == 0, printed.err
    seed = PresentationSpec.load(out)
    assert len(seed.modules) == 1
    assert seed.modules[0].parts == ["U1", "U2"]
    assert seed.islands is None
    report = json.loads(facts_out.read_text(encoding="utf-8"))["presentationSeed"]
    assert report["modules"][0]["pageUuid"] == "page-1"
    assert report["openQuestions"]


def test_out_profiles_augments_only_with_instance_pose_evidence(tmp_path, capsys):
    from boardwise.core.symbolprofile import SymbolPose

    source = tmp_path / "profiles.json"
    source.write_text(json.dumps({"profiles": [
        {
            "kind": "boardwise-symbol-profile", "profileVersion": 1,
            "symbolRef": "dev-U1", "poses": [SymbolPose(rotation=270).to_jsonable()],
        },
        {
            "kind": "boardwise-symbol-profile", "profileVersion": 1,
            "symbolRef": "dev-U2", "poses": [SymbolPose(rotation=270).to_jsonable()],
        },
    ]}), encoding="utf-8")
    out = tmp_path / "augmented.json"
    facts_out = tmp_path / "facts.json"
    code = cli.main([
        "draw", "v4-facts", "--file", str(FIXTURE), "--profiles", str(source),
        "--out-profiles", str(out), "-o", str(facts_out),
    ])
    printed = capsys.readouterr()
    assert code == 0, printed.err
    augmented = json.loads(out.read_text(encoding="utf-8"))["profiles"]
    assert all(len(profile["poses"]) == 2 for profile in augmented)
    assert json.loads(facts_out.read_text(encoding="utf-8"))["profilePoses"]["geometryVerified"] is False


def test_v4_facts_can_emit_presentation_evidence_sidecar(tmp_path, capsys):
    out = tmp_path / "presentation-evidence.json"
    code = cli.main([
        "draw", "v4-facts", "--file", str(FIXTURE), "--out-evidence", str(out),
    ])
    printed = capsys.readouterr()
    assert code == 0, printed.err
    evidence = json.loads(out.read_text(encoding="utf-8"))
    assert evidence["schema"] == "boardwise.v4-presentation-evidence/1"
    assert "modules" not in evidence
    assert evidence["pageGroups"][0]["page"] == "P1"
    assert evidence["openQuestions"]


def test_existing_circuit_and_profiles_emit_instance_poses(tmp_path, capsys):
    from boardwise.core.circuitspec import CircuitSpec, SpecPart
    from boardwise.core.symbolprofile import SymbolPose

    circuit_path = tmp_path / "base.circuit.json"
    CircuitSpec(parts=[SpecPart(id="U1", symbol_ref="known-U1")]).dump(circuit_path)
    library_path = tmp_path / "library.json"
    library = {"profiles": [{
        "kind": "boardwise-symbol-profile", "profileVersion": 1,
        "symbolRef": "known-U1", "poses": [SymbolPose(rotation=270).to_jsonable()],
    }]}
    library_path.write_text(json.dumps(library), encoding="utf-8")
    original_library = library_path.read_bytes()
    output = tmp_path / "poses.json"
    facts_path = tmp_path / "facts.json"

    code = cli.main([
        "draw", "v4-facts", "--file", str(FIXTURE),
        "--circuit", str(circuit_path), "--profiles", str(library_path),
        "--out-profiles", str(output), "-o", str(facts_path),
    ])
    printed = capsys.readouterr()
    assert code == 0, printed.err
    assert library_path.read_bytes() == original_library
    profiles = json.loads(output.read_text(encoding="utf-8"))["profiles"]
    assert len(profiles) == 1 and profiles[0]["symbolRef"] == "known-U1"
    assert profiles[0]["poses"][0] == library["profiles"][0]["poses"][0]
    assert len(profiles[0]["poses"]) == 2
    report = json.loads(facts_path.read_text(encoding="utf-8"))["profilePoses"]
    assert report["geometryVerified"] is False
    assert report["addedPoses"] == [{
        "part": "U1", "symbolRef": "known-U1", "rotation": 0, "mirror": False,
        "pageUuid": "page-1",
    }]


def test_existing_circuit_with_invalid_profiles_returns_input_error(tmp_path, capsys):
    from boardwise.core.circuitspec import CircuitSpec, SpecPart

    circuit_path = tmp_path / "base.circuit.json"
    CircuitSpec(parts=[SpecPart(id="U1", symbol_ref="known-U1")]).dump(circuit_path)
    library_path = tmp_path / "invalid-library.json"
    library_path.write_text("not valid JSON", encoding="utf-8")
    output = tmp_path / "poses.json"
    code = cli.main([
        "draw", "v4-facts", "--file", str(FIXTURE),
        "--circuit", str(circuit_path), "--profiles", str(library_path),
        "--out-profiles", str(output),
    ])
    printed = capsys.readouterr()
    assert code == 2
    assert "draw v4-facts:" in printed.err and "Traceback" not in printed.err
    assert not output.exists()
