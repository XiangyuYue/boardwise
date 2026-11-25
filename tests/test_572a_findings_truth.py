"""572A: the three facts this batch repaired, pinned against the plan itself.

`outputs/hole572/a/REPRO.md` recorded the readings at `f5083286`; these tests
re-take them on the current tree and assert the **fixed** reading. Every causal
leg compares the note / finding / action with the plan's own objects
(`power_symbols`, `labels`, `evidence.grammar_findings`), so a mutation that
restores the old line turns the matching test red (see
`evidence/572a/REPORT.md` for the two mutations and their red counts).
"""
from pathlib import Path

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.engines import drawcompiler
from boardwise.engines.drawapply import load_library

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "blocklib" / "specs"
SHARED_BOOK = ROOT / "blocklib" / "symbols" / "profiles.json"
SY8089_CIRCUIT = ROOT / "blocklib" / "modules" / "circuits" / "sy8089_buck_3v3.circuit.json"
BOX = (0.0, 0.0, 1170.0, 825.0)


def _compile(name, profiles, circuit_path=None, spec_path=None):
    circuit = CircuitSpec.load(circuit_path or (SPECS / f"{name}.circuit.json"))
    presentation = PresentationSpec.load(SPECS / f"{name}.presentation.json")
    return drawcompiler.compile(
        circuit,
        presentation,
        load_library(profiles),
        drawcompiler.CompileBudget(page_box=BOX),
        spec_path=spec_path,
    )


def _sy8089():
    return _compile("sy8089_buck_3v3", SHARED_BOOK, circuit_path=SY8089_CIRCUIT)


def test_h1_a_flag_sentence_only_appears_when_the_plan_carries_the_flag():
    """572A-H1: sy8089 has no flag at all, so no note may promise one."""
    result = _sy8089()
    assert result.ok and result.candidates
    exercised = False
    for plan in result.candidates:
        flagged = {symbol.net for symbol in plan.power_symbols if symbol.net}
        promised = [
            note for note in plan.notes
            if "expressed by its **flag** at each of its pins" in note
        ]
        if "port.GND" in flagged:
            continue
        assert promised == [], (
            "the plan places no port.GND power symbol, so a note promising a "
            f"flag at each pin is false: {promised}"
        )
        truthful = [
            note for note in plan.notes
            if "net label(s) carry port.GND" in note
        ]
        if not truthful:
            continue
        exercised = True
        carrying = sum(
            1 for item in plan.labels if getattr(item, "net", "") == "port.GND"
        )
        assert carrying > 0
        assert f"{carrying} net label(s) carry port.GND" in truthful[0], truthful[0]
    assert exercised, (
        "no candidate carries the gnd downgrade note this test is about — the "
        "reading moved and the test would be vacuous"
    )


def test_h2_a_ground_drawn_as_labels_gets_a_flag_obligation_finding():
    """572A-H2: the label-only ground net must be the one the check reports."""
    result = _sy8089()
    assert result.ok and result.candidates
    hits = [
        finding
        for plan in result.candidates
        for finding in plan.evidence.grammar_findings
        if "circuitSpec.nets[port.GND]" in finding
    ]
    assert hits, (
        "a ground net drawn with 5 net labels and no flag produced no finding; "
        "the class filter still skips `gnd`"
    )
    assert any("net label(s) carry its name" in finding for finding in hits), hits


def test_h3_facts_missing_action_names_the_sibling_library_before_rebuilding():
    """572A-H3: a wrong book is an input pairing, not a missing profile."""
    circuit = SPECS / "ch340_serial.circuit.json"
    result = _compile(
        "ch340_serial", SHARED_BOOK, circuit_path=circuit, spec_path=str(circuit),
    )
    assert not result.ok and result.failures
    facts = [
        failure for failure in result.failures
        if failure.category == "facts-missing"
    ]
    assert facts, [failure.category for failure in result.failures]
    action = facts[0].action
    assert "ch340_serial.library.json" in action, action
    assert action.index("ch340_serial.library.json") < action.index(
        "from_parsed_symbol"
    ), action
    # A caller that cannot name the file still gets the rule, not a bare rebuild
    # order.
    plain = _compile("ch340_serial", SHARED_BOOK, circuit_path=circuit)
    assert ".library.json" in plain.failures[0].action
    # The diagnosis is proved by the repair it names: the sibling book compiles.
    right = _compile(
        "ch340_serial", SPECS / "ch340_serial.library.json", circuit_path=circuit,
    )
    assert right.ok and right.candidates
