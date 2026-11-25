"""619: five `docs/pits.md` rows must match what the tree can actually check.

570-E (``outputs/hole570/e/REPRO.md``) found five rows whose provenance or
wording no longer describes this repo:

* E-01 — pits 41/48/49/50/51 point at ``outputs/``/``evidence/`` files that are
  not in the tree at all.  The readings stay historical; the rows must say the
  raw files were not preserved and send the reader to the mechanism that *is*
  here.
* E-02 — pit 12 still calls the daemon-down ``edit apply`` exit code a known
  implementation deviation; 018 §C.1 fixed it (3) and left a test.
* E-03 — pit 15 credited the six drawing sections to 570 and to the working
  tree; 566-A-2 landed them and HEAD contains them.
* E-04 — pit 43 said every flag profile in this repo carries the same ideal
  box; since 147 the flyback book carries per-family measured boxes.
* E-05 — pit 2's 3.7 s/part is an empty-queue reading and must point at pit 53.

Every assertion below is either a fact about the current files (parsed, not
quoted) or the absence of a dead path.
"""

from __future__ import annotations

import pathlib
import re

from boardwise.core.symbolprofile import flag_glyph_box, flag_glyph_kind
from boardwise.engines.drawapply import DRAWING_SECTIONS, load_library

REPO = pathlib.Path(__file__).resolve().parents[1]
PITS = REPO / "docs" / "pits.md"
SKILLS = (
    REPO / ".kimi-code" / "skills" / "boardwise" / "SKILL.md",
    REPO / ".agents" / "skills" / "boardwise" / "SKILL.md",
)


def _row(number: int) -> str:
    rows = [
        line
        for line in PITS.read_text(encoding="utf-8").splitlines()
        if line.startswith(f"| {number} |")
    ]
    assert len(rows) == 1, f"docs/pits.md lost its pit {number} row"
    return rows[0]


# --------------------------------------------------------------- E-01 死链


DEAD_PROVENANCE = (
    "outputs/057_live/e1/plan2.txt",
    "evidence/530f/report.md",
    "evidence/532/532_page_a.svg",
    "evidence/533/",
    "evidence/530a/report.md",
)


def test_e01_the_five_dead_provenance_paths_are_gone_from_the_table():
    """Raw files that were never tracked cannot stay cited as if they were."""
    text = PITS.read_text(encoding="utf-8")
    still = [path for path in DEAD_PROVENANCE if path in text]
    assert still == [], "docs/pits.md still cites missing raw files: " + ", ".join(still)


def test_e01_each_row_says_the_raw_evidence_was_not_preserved():
    for number in (41, 48, 49, 50, 51):
        row = _row(number)
        assert "raw not preserved" in row or "原始件未保留" in row, (
            f"pit {number} must say its raw evidence was not preserved"
        )


def test_e01_the_rows_point_at_mechanisms_that_exist_today():
    """The replacement provenance is code/tests in this tree, checked here."""
    layoutplan = (REPO / "src" / "boardwise" / "core" / "layoutplan.py").read_text(
        encoding="utf-8"
    )
    assert "grammarFindings" in layoutplan
    assert "grammarFindings" in _row(41)

    cli = (REPO / "src" / "boardwise" / "cli.py").read_text(encoding="utf-8")
    for symbol in ("island_page_title_block_not_reserved", "sheet_attrs_from_text"):
        assert symbol in cli
    for number in (48, 49):
        for symbol in ("sheet_attrs_from_text",):
            assert symbol in _row(number), f"pit {number} lost its current gate {symbol}"
    assert "island_page_title_block_not_reserved" in _row(48)

    for name in ("test_533_island_guard.py", "test_569_title_block.py"):
        assert (REPO / "tests" / name).is_file(), f"tests/{name} is the cited gate test"
    assert "test_533_island_guard.py" in _row(48)

    connector = (REPO / "connector" / "src" / "actions.ts").read_text(encoding="utf-8")
    assert "sys.identity" in connector
    assert "sys.identity" in _row(50)

    addcomponent = (REPO / "src" / "boardwise" / "engines" / "addcomponent.py").read_text(
        encoding="utf-8"
    )
    assert "def netflag_count" in addcomponent
    assert "netflag_count" in _row(51)


# ------------------------------------------------------- E-02 坑 12 已修


EDIT_APPLY_TEST = "test_edit_apply_exits_3_when_the_daemon_is_unreachable"


def test_e02_pit_12_records_the_018_c1_fix_and_names_its_test():
    row = _row(12)
    assert "已修" in row
    assert "018 §C.1" in row
    assert EDIT_APPLY_TEST in row
    assert "已知实现偏差" not in row
    test_file = (
        REPO / "tests" / "test_018_cli_review.py"
    ).read_text(encoding="utf-8")
    assert f"def {EDIT_APPLY_TEST}(" in test_file


def test_e02_both_skill_copies_index_pit_12_as_fixed_and_are_byte_identical():
    first, second = (path.read_bytes() for path in SKILLS)
    assert first == second, "the two boardwise SKILL.md copies must stay identical"
    text = first.decode("utf-8")
    rows = [line for line in text.splitlines() if line.startswith("| 12 |")]
    assert len(rows) == 1, "the skill index lost its pit 12 line"
    assert "已修" in rows[0]
    assert "实现偏差" not in rows[0]


# ------------------------------------------- E-03 坑 15 六类图元（566-A-2）


DRAWING_KEYS = ("texts", "buses", "circles", "rectangles", "arcs", "polygons")


def test_e03_pit_15_credits_566_a_2_and_the_current_version():
    row = _row(15)
    assert "566-A-2" in row
    assert "570 加入" not in row
    assert "仅工作树" not in row
    assert "当前" in row


def test_e03_the_connector_and_the_engine_really_produce_the_six_sections():
    connector = (REPO / "connector" / "src" / "actions.ts").read_text(encoding="utf-8")
    for key in DRAWING_KEYS:
        assert re.search(rf"^\s*{key}: {key}\.items,", connector, re.M), (
            f"connector sch.geometry lost the {key} section"
        )
    for key in DRAWING_KEYS:
        assert key in DRAWING_SECTIONS, f"drawapply.DRAWING_SECTIONS lost {key!r}"
    drawapply = (REPO / "src" / "boardwise" / "engines" / "drawapply.py").read_text(
        encoding="utf-8"
    )
    assert "DRAWING_SECTIONS" in drawapply


# ------------------------------------------------------ E-04 坑 43 旗盒按书


SPECS = REPO / "blocklib" / "specs"
FLAG_BOOKS = ("ch340_serial", "power_entry_xt30", "flyback_uc3845")


def _flag_boxes(book: str) -> dict[str, tuple[str, tuple[float, float, float, float]]]:
    profiles = load_library(SPECS / f"{book}.library.json")
    boxes = {}
    for ref, profile in profiles.items():
        if profile.pins:
            continue
        box = flag_glyph_box(profile, rotation=0.0, anchor=(0.0, 0.0))
        boxes[ref] = (flag_glyph_kind(profile), (box[0], box[1], box[2], box[3]))
    return boxes


def test_e04_the_two_old_books_still_share_the_ideal_box():
    ideal = {"rail": (-6.0, 0.0, 6.0, 18.0), "gnd": (-6.0, -18.0, 6.0, 0.0)}
    for book in ("ch340_serial", "power_entry_xt30"):
        boxes = _flag_boxes(book)
        assert boxes, f"blocklib/specs/{book}.library.json has no flag profiles"
        for ref, (kind, box) in boxes.items():
            assert box == ideal[kind], f"{book}:{ref} no longer sits in the ideal box"


def test_e04_the_flyback_book_is_measured_per_family():
    measured = {
        "gnd": (-10.5, -19.5, 10.5, 0.0),
        "rail": (-5.5, 0.0, 5.5, 10.5),
    }
    boxes = _flag_boxes("flyback_uc3845")
    assert {"PWR-GND", "PWR-PGND", "PWR-SEC_GND"} <= set(boxes)
    assert {"PWR-HVDC", "PWR-SEC_12V"} <= set(boxes)
    for ref, (kind, box) in boxes.items():
        assert box == measured[kind], f"flyback_uc3845:{ref} left its measured box"
    assert len({box for _kind, box in boxes.values()}) == 2, (
        "the flyback book must keep two distinct family boxes"
    )


def test_e04_pit_43_states_the_boxes_by_book_and_keeps_the_four_pose_check():
    row = _row(43)
    assert "ch340_serial" in row and "power_entry_xt30" in row
    assert "flyback_uc3845" in row
    for box in ("(-6,0,6,18)", "(-10.5,0,10.5,19.5)", "(-5.5,0,5.5,10.5)"):
        assert box in row, f"pit 43 lost the measured box {box}"
    assert "四姿态" in row, "pit 43 must keep the four-pose render check"
    assert "每颗旗标 profile 都写同一个约定盒" not in row


# ------------------------------------------- E-05 坑 2 指向坑 53


def test_e05_pit_2_sends_its_rate_to_pit_53():
    row = _row(2)
    assert "3.7" in row
    assert "坑 53" in row
    assert "队列" in row
    assert "先回读" in row, "pit 2 must keep the read-before-retry rule"
    other = _row(53)
    assert "15 s/件" in other and "0.15 s/件" in other
