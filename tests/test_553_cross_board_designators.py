"""553: a designator shared across boards is a project fact, not a defect.

岳 2026-11-19: 「跨板共用位号不算问题，以后不要报错」. Before this batch
`conn-duplicate-designators` walked `model.cross_board_designators` and raised one
ERROR per name, so the 高速电机控制器 project (two boards, each numbering its own
C1/U1…) produced 18 ERRORs for a board whose own netlist has no repeat at all.

What this file pins:

* the pure cross-board case reports nothing (it used to report ERROR — see
  040/040b, whose old assertions were the red half of this batch);
* the project fact survives untouched: `cross_board_designators`,
  `ProjectModel.multi_board_designators()` and `repeated_designators()` keep
  naming every shared designator, because BOM/report/board addressing need it;
* the two same-board classes still ERROR, asserted **by subject** on a model
  that carries all three at once, so a shrinking total cannot hide a same-board
  repeat behind the cross-board removal;
* the DCDC archive's same-page copy and the injected R24 cross-page copy still
  fire, so the negative controls live in the same file as the zero.
"""

from __future__ import annotations

from pathlib import Path

from boardwise.core.model import BoardModel, BoardRef
from boardwise.parsers.schematic import build_project_model
from boardwise.rules.connectivity import DuplicateDesignators

FIXTURES = Path(__file__).parent / "fixtures"
FOC = FIXTURES / "ProPrj_毕设FOC驱动板_2026-09-17.epro2"
MOTOR = FIXTURES / "ProPrj_高速电机控制器_2026-09-16.epro2"
DCDC = FIXTURES / "DCDC-12V9V转5V3V3_2026-09-27.epro2"
INJECTED = Path("reviewsets") / "injected" / "duplicate-designator.epro2"


def _board(title: str = "Board1") -> BoardModel:
    return BoardModel(board=BoardRef(uuid=title.lower(), title=title))


def _pure_cross_board() -> BoardModel:
    """One board whose only repeat is a name a second board also carries."""
    board = _board()
    board.cross_board_designators = {"C1": ["Board1", "Board2"]}
    return board


def _findings(model):
    return [
        finding
        for board_model in model.boards
        for finding in DuplicateDesignators().check(board_model)
    ]


def test_a_name_shared_across_boards_is_not_a_finding():
    """Before 553 this board produced exactly one ERROR ("C1 is placed on more
    than one board"); now it produces the OK row, and the fact is still there."""
    board = _pure_cross_board()
    assert board.cross_board_designators == {"C1": ["Board1", "Board2"]}
    assert DuplicateDesignators().check(board) == []
    (outcome,) = DuplicateDesignators().outcomes(board)
    assert outcome.state == "OK"
    assert outcome.subject == "designator uniqueness"


def test_the_ok_row_only_claims_uniqueness_on_this_board():
    """The clean reading must not claim more than it measured: another board may
    carry the same names, so the rule speaks for one board's netlist."""
    board = _pure_cross_board()
    (outcome,) = DuplicateDesignators().outcomes(board)
    assert "on this board" in outcome.message
    assert "project" not in outcome.message.lower()
    assert "parsed pages" not in outcome.message
    title = DuplicateDesignators.title.lower()
    assert "project" not in title and "whole" not in title
    assert "board" in title


def test_the_three_board_archive_keeps_the_facts_and_drops_the_error():
    """28 names are on more than one board (040b); all 28 stay facts, none is a
    finding, and the two same-board classes have no instance on this archive."""
    project = build_project_model(FOC)
    assert len(project.multi_board_designators()) == 28
    assert project.multi_board_designators()["C1"] == [
        "Board1", "Board2", "Board3",
    ]
    assert len(project.repeated_designators()) == 28
    assert project.repeated_designators() == sorted(project.multi_board_designators())
    board3 = next(b for b in project.boards if b.board.title == "Board3")
    assert len(board3.cross_board_designators) == 28
    assert board3.cross_board_designators["C1"] == ["Board1", "Board2", "Board3"]
    assert _findings(project) == []


def test_the_two_board_archive_reports_none_of_its_eighteen_names():
    """高速电机控制器: 18 shared names, 0 findings (was 18 ERRORs)."""
    project = build_project_model(MOTOR)
    assert len(project.multi_board_designators()) == 18
    assert project.multi_board_designators()["C8"] == ["控制板", "驱动板"]
    for board_model in project.boards:
        assert board_model.duplicate_designators == []
        assert board_model.cross_page_designators == {}
    assert _findings(project) == []


def test_three_kinds_at_once_report_only_the_same_board_ones():
    """The anti-total control: one model, all three classes, and the verdict is
    asserted by subject — R7 (same page) and R24 (same board, another page) are
    the only subjects, while C1 stays a cross-board fact."""
    board = _board()
    board.duplicate_designators = ["R7"]
    board.cross_page_designators = {"R24": ["pageA", "pageB"]}
    board.cross_board_designators = {"C1": ["Board1", "Board2"]}

    rows = [(outcome.subject, severity) for outcome, severity in DuplicateDesignators()._rows(board)]
    assert rows == [("R7", "ERROR"), ("R24", "ERROR")]

    findings = DuplicateDesignators().check(board)
    assert len(findings) == 2 and {f.severity for f in findings} == {"ERROR"}
    assert {f.severity for f in findings} == {"ERROR"}
    same_page = next(f for f in findings if f.message.startswith("R7 "))
    assert "one page" in same_page.message
    cross_page = next(f for f in findings if f.message.startswith("R24 "))
    assert "pages of one board" in cross_page.message
    assert not any("more than one board" in f.message for f in findings)
    # the third class is still a fact on the same model, just not a verdict
    assert board.cross_board_designators == {"C1": ["Board1", "Board2"]}


def test_the_same_page_copy_on_the_dcdc_archive_still_errors():
    """Negative control 1 (105 measures the same two names): the archives that
    repeat a designator inside one netlist are untouched by 553."""
    project = build_project_model(DCDC)
    (board_model,) = project.boards
    assert board_model.duplicate_designators == ["100NF", "10UF"]
    assert board_model.cross_board_designators == {}
    findings = DuplicateDesignators().check(board_model)
    assert [(o.subject, s) for o, s in DuplicateDesignators()._rows(board_model)] == [
        ("100NF", "ERROR"), ("10UF", "ERROR"),
    ]
    assert {f.severity for f in findings} == {"ERROR"}


def test_the_injected_cross_page_r24_still_errors():
    """Negative control 2: the signed variant's second page repeats R24, and the
    ruling it demands is still ERROR after the cross-board rows are gone."""
    project = build_project_model(INJECTED)
    (board_model,) = project.boards
    assert board_model.duplicate_designators == []
    assert sorted(board_model.cross_page_designators) == ["R24"]
    (finding,) = DuplicateDesignators().check(board_model)
    assert finding.severity == "ERROR" and "R24" in finding.message
