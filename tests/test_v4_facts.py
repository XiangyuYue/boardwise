"""Read-only V4 facts (``boardwise.v4-facts/1``) — the evidence layer, not an interpreter.

Each assertion here pins one thing the V4 audit said must not be invented: a
``Global Net Name`` flag stays a project-scope *flag* (it does not prove the
pages are connected), a page ``NET`` label stays page-scope, ``Pin Type`` is
kept verbatim, ``class`` comes only from a symbol's own ``META.title`` and never
from the net name, and BUS records are counted without extracting members.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from boardwise.engines.v4facts import (
    open_questions,
    power_rails,
    read_v4_facts,
    signal_interfaces,
)

FIXTURE = Path(__file__).parent / "fixtures" / "eprj3_synth"


def _net(facts: dict, name: str) -> dict:
    matching = [net for net in facts["nets"] if net["name"] == name]
    assert len(matching) == 1, f"expected exactly one net {name!r}, got {matching}"
    return matching[0]


def _record(record_type: str, body: dict, record_id: str | None = None) -> str:
    envelope: dict = {"type": record_type}
    if record_id is not None:
        envelope["id"] = record_id
    return (
        json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))
        + "||"
        + json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        + "|"
    )


def _attr(parent: str, key: str, value: str, record_id: str) -> str:
    return _record(
        "ATTR", {"parentId": parent, "key": key, "value": value}, record_id
    )


def _make_project(root: Path) -> Path:
    """Two pages: a flag and a same-named label on different pages, plus a BUS.

    PageA carries a ``Power-5V`` flag symbol and a ``Global Net Name`` of
    ``V5``; PageB carries a ``NET`` label of the same ``V5`` and a plain
    ``POWER`` label (so "POWER" must stay classless — the name is not evidence).
    """

    (root / "sch" / "Schematic1").mkdir(parents=True)
    page_a = [
        _record(
            "DOCHEAD",
            {"docType": "SCH_PAGE", "uuid": "page-a", "editVersion": "2.3.0"},
        ),
        _record(
            "DOCHEAD",
            {"docType": "SYMBOL", "uuid": "sym-v5", "editVersion": "2.3.0"},
        ),
        _record("META", {"title": "Power-5V", "docType": "SYMBOL"}, "META"),
        _record("PIN", {"x": 0.0, "y": 0.0, "zIndex": 2}, "p1"),
        _attr("p1", "Pin Number", "1", "p1-num"),
        _attr("p1", "Pin Name", "V5", "p1-name"),
        _attr("p1", "Pin Type", "Power", "p1-type"),
        _record(
            "COMPONENT",
            {
                "partId": "flag-v5",
                "x": 100.0,
                "y": 100.0,
                "rotation": 0,
                "isMirror": False,
                "zIndex": 10,
            },
            "c-flag",
        ),
        _attr("flag-v5", "Symbol", "sym-v5", "flag-sym"),
        _attr("flag-v5", "Global Net Name", "V5", "flag-net"),
        _record("BUS", {"busEntry": [{"pointX": 0.0, "pointY": 0.0}]}, "bus-1"),
        _record("BUSENTRY", {"pointX": 0.0, "pointY": 0.0}, "be-1"),
    ]
    page_b = [
        _record(
            "DOCHEAD",
            {"docType": "SCH_PAGE", "uuid": "page-b", "editVersion": "2.3.0"},
        ),
        _record("WIRE", {"zIndex": 40}, "grp-v5"),
        _record(
            "LINE",
            {
                "lineGroup": "grp-v5",
                "startX": 0.0,
                "startY": 0.0,
                "endX": 10.0,
                "endY": 0.0,
            },
        ),
        _attr("grp-v5", "NET", "V5", "net-v5"),
        _record("WIRE", {"zIndex": 40}, "grp-power"),
        _record(
            "LINE",
            {
                "lineGroup": "grp-power",
                "startX": 0.0,
                "startY": 10.0,
                "endX": 10.0,
                "endY": 10.0,
            },
        ),
        _attr("grp-power", "NET", "POWER", "net-power"),
    ]
    (root / "sch" / "Schematic1" / "PageA.esch2").write_text(
        "\n".join(page_a), encoding="utf-8"
    )
    (root / "sch" / "Schematic1" / "PageB.esch2").write_text(
        "\n".join(page_b), encoding="utf-8"
    )
    index = {
        "name": root.name,
        "owner_uuid": "0" * 32,
        "profile": {
            "schematics": {"sch-1": {"uuid": "sch-1", "name": "Schematic1"}},
            "sheets": {},
            "pcbs": {},
        },
    }
    (root / f"{root.name}.eprj3").write_text(json.dumps(index), encoding="utf-8")
    return root


def test_fixture_flag_is_project_scope_and_flag_evidence() -> None:
    facts = read_v4_facts(FIXTURE)

    assert facts["schema"] == "boardwise.v4-facts/1"
    assert facts["meta"]["format"] == "eprj3"
    assert [(page["uuid"], page["name"]) for page in facts["pages"]] == [
        ("page-1", "P1")
    ]

    gnd = _net(facts, "GND")
    assert gnd["scope"] == "project"
    assert gnd["class"] == "gnd"
    assert gnd["key"] == "Global Net Name"
    assert gnd["pageUuid"] == "page-1"
    assert gnd["page"] == "P1"
    assert gnd["parentId"] == "flag-gnd"
    assert gnd["crossPageConnectivityProven"] is False
    assert [entry["kind"] for entry in gnd["evidence"]] == ["flag"]
    assert gnd["evidence"][0]["symbolUuid"] == "sym-gnd"
    assert gnd["evidence"][0]["symbolTitle"] == "Ground-GND"


def test_fixture_label_is_page_scope_and_label_evidence() -> None:
    facts = read_v4_facts(FIXTURE)

    sig = _net(facts, "SIG_A")
    assert sig["scope"] == "page"
    assert sig["class"] == ""
    assert sig["key"] == "NET"
    assert sig["pageUuid"] == "page-1"
    assert sig["page"] == "P1"
    assert sig["parentId"] == "grp-1"
    assert sig["crossPageConnectivityProven"] is False
    assert [entry["kind"] for entry in sig["evidence"]] == ["label"]
    assert sig["evidence"][0]["value"] == "SIG_A"


def test_fixture_pin_type_is_kept_verbatim() -> None:
    facts = read_v4_facts(FIXTURE)

    assert [symbol["uuid"] for symbol in facts["symbols"]] == ["sym-1", "sym-gnd"]
    assert facts["symbols"][0]["title"] == "R"
    assert facts["symbols"][0]["pins"] == [
        {"number": "1", "name": "P1", "pinType": "1"},
        {"number": "2", "name": "P2", "pinType": "1"},
    ]
    # "1" is not translated to an input/output/electrical function anywhere.
    assert facts["symbols"][1]["pins"] == [
        {"number": "1", "name": "P1", "pinType": "1"}
    ]


def test_power_rails_and_signal_interfaces_are_deep_copies() -> None:
    facts = read_v4_facts(FIXTURE)

    rails = power_rails(facts)
    assert [rail["name"] for rail in rails] == ["GND"]
    rails[0]["name"] = "MUTATED"
    assert _net(facts, "GND")["name"] == "GND"

    signals = signal_interfaces(facts)
    assert [signal["name"] for signal in signals] == ["SIG_A"]
    assert signals[0]["direction"] == ""
    assert signals[0]["directionProvenance"] == ""
    signals[0]["scope"] = "project"
    assert _net(facts, "SIG_A")["scope"] == "page"


def test_fixture_open_questions_state_the_unknowns() -> None:
    facts = read_v4_facts(FIXTURE)
    questions = open_questions(facts)

    assert all(set(question) == {"kind", "detail"} for question in questions)
    assert all(question["detail"] for question in questions)
    kinds = [question["kind"] for question in questions]
    assert "pin-type-uncalibrated" in kinds
    assert any("'1'" in question["detail"] for question in questions)


def test_same_name_flag_and_label_across_pages_is_not_a_connectivity_proof(
    tmp_path: Path,
) -> None:
    facts = read_v4_facts(_make_project(tmp_path / "proj"))

    assert [page["name"] for page in facts["pages"]] == ["PageA", "PageB"]
    v5 = _net(facts, "V5")
    assert v5["scope"] == "project"
    assert v5["class"] == "power"
    assert v5["key"] == "Global Net Name"
    assert v5["page"] == "PageA"
    assert v5["pageUuid"] == "page-a"
    assert v5["parentId"] == "flag-v5"
    assert v5["crossPageConnectivityProven"] is False
    assert [entry["kind"] for entry in v5["evidence"]] == ["flag", "label"]
    assert {entry["page"] for entry in v5["evidence"]} == {"PageA", "PageB"}

    # The class is not guessed from the net name: "POWER" has no flag symbol.
    power = _net(facts, "POWER")
    assert power["scope"] == "page"
    assert power["class"] == ""

    assert facts["bus"] == {
        "recordCounts": {"BUS": 1, "BUSENTRY": 1},
        "memberSemanticsProven": False,
    }
    questions = open_questions(facts)
    kinds = [question["kind"] for question in questions]
    assert "bus-members-unproven" in kinds
    assert "cross-page-connectivity-unproven" in kinds
    assert "pin-type-uncalibrated" in kinds
    # Nowhere does a question turn "not proven" into a passing statement.
    assert all(
        not question["detail"].startswith("ok")
        for question in questions
    )


def test_two_reads_serialise_to_the_same_bytes(tmp_path: Path) -> None:
    for path in (FIXTURE, _make_project(tmp_path / "proj")):
        first = json.dumps(
            read_v4_facts(path), ensure_ascii=False, sort_keys=True
        ).encode("utf-8")
        second = json.dumps(
            read_v4_facts(path), ensure_ascii=False, sort_keys=True
        ).encode("utf-8")
        assert first == second


def test_circuit_enrichment_fills_scope_and_class_without_inventing_nets() -> None:
    from boardwise.core.circuitspec import CircuitSpec, SpecNet
    from boardwise.engines.v4facts import enrich_circuit_spec

    base = CircuitSpec(nets=[
        SpecNet(id="GND"), SpecNet(id="SIG_A"), SpecNet(id="UNCHANGED"),
    ])
    enriched, report = enrich_circuit_spec(read_v4_facts(FIXTURE), base)
    assert enriched is not base
    by_name = {net.id: net for net in enriched.nets}
    assert (by_name["GND"].scope, by_name["GND"].cls) == ("project", "gnd")
    assert (by_name["SIG_A"].scope, by_name["SIG_A"].cls) == ("page", "signal")
    assert by_name["UNCHANGED"].scope == ""
    assert [net.id for net in enriched.nets] == ["GND", "SIG_A", "UNCHANGED"]
    assert report["conflicts"] == []
    assert report["unmatchedFacts"] == []


def test_circuit_enrichment_keeps_conflicts_and_names_unmatched_facts() -> None:
    from boardwise.core.circuitspec import CircuitSpec, SpecNet
    from boardwise.engines.v4facts import enrich_circuit_spec

    base = CircuitSpec(nets=[
        SpecNet(id="GND", cls="power", scope="page"),
        SpecNet(id="SIG_A", cls="other", scope="project"),
    ])
    enriched, report = enrich_circuit_spec(read_v4_facts(FIXTURE), base)
    by_name = {net.id: net for net in enriched.nets}
    assert by_name["GND"].cls == "power"
    assert by_name["GND"].scope == "project"
    assert by_name["SIG_A"].cls == "other"
    assert by_name["SIG_A"].scope == "project"
    fields = {(item["net"], item["field"]) for item in report["conflicts"]}
    assert ("GND", "class") in fields
    assert ("SIG_A", "class") not in fields  # no class evidence for this label
    assert ("SIG_A", "scope") in fields
    assert report["unmatchedFacts"] == []


def test_circuit_enrichment_does_not_add_facts_missing_from_the_circuit() -> None:
    from boardwise.core.circuitspec import CircuitSpec, SpecNet
    from boardwise.engines.v4facts import enrich_circuit_spec

    base = CircuitSpec(nets=[SpecNet(id="GND")])
    enriched, report = enrich_circuit_spec(read_v4_facts(FIXTURE), base)
    assert [net.id for net in enriched.nets] == ["GND"]
    assert report["unmatchedFacts"] == ["SIG_A"]


def test_instances_keep_page_identity_without_turning_pose_into_layout() -> None:
    facts = read_v4_facts(FIXTURE)
    by_id = {item["partId"]: item for item in facts["instances"]}
    assert by_id["inst-u1"]["designator"] == "U1"
    assert by_id["inst-u1"]["symbolUuid"] == "sym-1"
    assert by_id["inst-u1"]["pageUuid"] == "page-1"
    assert by_id["inst-u1"]["page"] == "P1"
    assert by_id["flag-gnd"]["symbolTitle"] == "Ground-GND"
    assert all("x" not in item and "y" not in item for item in facts["instances"])


def test_presentation_evidence_groups_page_facts_without_claiming_modules() -> None:
    from boardwise.engines.v4facts import presentation_evidence

    evidence = presentation_evidence(read_v4_facts(FIXTURE))
    assert evidence["schema"] == "boardwise.v4-presentation-evidence/1"
    assert "modules" not in evidence
    group = evidence["pageGroups"][0]
    assert (group["pageUuid"], group["page"]) == ("page-1", "P1")
    assert {item["designator"] for item in group["instances"]} >= {"U1", "U2"}
    nets = {item["name"]: item for item in group["nets"]}
    assert nets["GND"]["scope"] == "project"
    assert nets["SIG_A"]["scope"] == "page"
    assert all(
        not net["crossPageConnectivityProven"] for net in group["nets"]
    )
    assert evidence["openQuestions"]


def test_presentation_evidence_keeps_multi_page_proof_separate(tmp_path: Path) -> None:
    from boardwise.engines.v4facts import presentation_evidence

    evidence = presentation_evidence(read_v4_facts(_make_project(tmp_path / "proj")))
    groups = {group["page"]: group for group in evidence["pageGroups"]}
    assert set(groups) == {"PageA", "PageB"}
    for page in ("PageA", "PageB"):
        v5 = next(net for net in groups[page]["nets"] if net["name"] == "V5")
        assert v5["crossPageConnectivityProven"] is False
        assert len(v5["evidence"]) == 1
        assert v5["evidence"][0]["page"] == page


def test_design_model_becomes_a_valid_circuit_spec_with_open_questions() -> None:
    from boardwise.core.circuitspec import CircuitSpec
    from boardwise.engines.v4circuitspec import circuit_spec_from_design_model
    from boardwise.parsers.schematic import build_schematic_model

    spec, report = circuit_spec_from_design_model(build_schematic_model(FIXTURE))
    assert [part.id for part in spec.parts] == ["U1", "U2"]
    assert [part.symbol_ref for part in spec.parts] == ["dev-U1", "dev-U2"]
    sig = spec.net("SIG_A")
    assert sig is not None and sig.members == ["U1.1", "U2.1"]
    assert spec.net("GND") is None  # a flag with no model net is not invented
    assert report["singleMemberNets"] == ["NET1", "NET2"]
    kinds = {item["kind"] for item in report["openQuestions"]}
    assert "nc-status-unproven" in kinds
    assert "open-interface-unproven" in kinds
    CircuitSpec.from_dict(spec.to_jsonable())


def test_design_model_with_repeated_designators_is_not_silently_truncated() -> None:
    from boardwise.core.model import DesignModel
    from boardwise.engines.v4circuitspec import circuit_spec_from_design_model
    import pytest

    with pytest.raises(ValueError, match="U1"):
        circuit_spec_from_design_model(DesignModel(duplicate_designators=["U1"]))


def test_cross_board_reuse_is_reported_not_merged_or_refused() -> None:
    from boardwise.core.model import Component, DesignModel, Net
    from boardwise.engines.v4circuitspec import circuit_spec_from_design_model

    model = DesignModel(
        components={"C4": Component(
            uid="c4", designator="C4", lcsc_part="C15850",
            props={"device_uuid": "d1"},
        )},
        nets={"SIG": Net(name="SIG", pins=[("C4", "1")])},
    )
    model.cross_board_designators = ["C4"]
    _spec, report = circuit_spec_from_design_model(model)
    assert report["crossBoardDesignators"] == ["C4"]
    assert any(q["kind"] == "cross-board-designator-shared" for q in report["openQuestions"])


def test_presentation_seed_is_only_a_page_grouped_input_for_islands() -> None:
    from boardwise.engines.v4circuitspec import circuit_spec_from_design_model
    from boardwise.engines.v4facts import presentation_seed_from_facts
    from boardwise.parsers.schematic import build_schematic_model

    circuit, _production = circuit_spec_from_design_model(build_schematic_model(FIXTURE))
    seed, report = presentation_seed_from_facts(read_v4_facts(FIXTURE), circuit)
    assert len(seed.modules) == 1
    module = seed.modules[0]
    assert module.parts == ["U1", "U2"]
    assert module.role == "unassigned" and module.core == ""
    assert seed.islands is None and seed.flow == []
    assert report["modules"][0]["pageUuid"] == "page-1"
    assert report["openQuestions"]


def test_profile_binding_uses_lcsc_not_device_uuid() -> None:
    from types import SimpleNamespace
    from boardwise.core.model import Component, DesignModel, Net
    from boardwise.engines.v4circuitspec import circuit_spec_from_design_model

    model = DesignModel(
        components={"U1": Component(
            uid="u", designator="U1", lcsc_part="C2844153",
            props={"device_uuid": "device-uuid-is-not-a-profile"},
        )},
        nets={"SIG": Net(name="SIG", pins=[("U1", "1")])},
    )
    book = {"CH343G-C2844153": SimpleNamespace(symbol_ref="CH343G-C2844153")}
    spec, _report = circuit_spec_from_design_model(model, profiles=book)
    assert spec.parts[0].symbol_ref == "CH343G-C2844153"


def test_multi_board_requires_an_explicit_board(monkeypatch) -> None:
    from types import SimpleNamespace
    from boardwise.engines.v4facts import select_board_model

    boards = [
        SimpleNamespace(board=SimpleNamespace(uuid="b1", title="Board1", page_uuids=("p1",))),
        SimpleNamespace(board=SimpleNamespace(uuid="b2", title="Board2", page_uuids=("p2",))),
    ]
    project = SimpleNamespace(boards=boards, board_titles=lambda: ["Board1", "Board2"])
    monkeypatch.setattr("boardwise.engines.v4facts.build_project_model", lambda path: project)
    with pytest.raises(ValueError, match="multi-board"):
        select_board_model("x")
    selected, ref = select_board_model("x", "Board2")
    assert selected is boards[1] and ref.title == "Board2"


def test_instance_poses_are_added_without_remeasuring_geometry() -> None:
    from boardwise.core.symbolprofile import SymbolProfile, SymbolPose
    from boardwise.engines.v4circuitspec import circuit_spec_from_design_model
    from boardwise.engines.v4facts import with_instance_poses
    from boardwise.parsers.schematic import build_schematic_model

    circuit, _report = circuit_spec_from_design_model(build_schematic_model(FIXTURE))
    profiles = {
        "dev-U1": SymbolProfile(
            symbol_ref="dev-U1", poses=[SymbolPose(rotation=270, mirror=False)],
        ),
        "dev-U2": SymbolProfile(
            symbol_ref="dev-U2", poses=[SymbolPose(rotation=270, mirror=False)],
        ),
    }
    augmented, report = with_instance_poses(profiles, read_v4_facts(FIXTURE), circuit)
    assert report["geometryVerified"] is False
    assert report["addedPoses"]
    assert report["addedPoses"][0]["rotation"] == 0
    assert all(len(profile.poses) == 2 for profile in augmented.values())
    assert all(len(profile.poses) == 1 for profile in profiles.values())
