"""527C2 片 2: the geometry disclosure of the cross-view rows, and its note.

片 1 hands the parser's per-page projection over in
``DesignModel.pin_wires``; this file pins what the **engine and the note line**
do with it. The question it answers is the one the netlist rows cannot: *is this
lonely foot on a line at all, and if it is, do the two archives call that line
the same thing?*

What the contract holds, and what these tests hold it to:

* ``cross_view_section`` grows **one** optional key, ``geometry``, appended after
  every existing key and only when ``checked: true`` **and** ``lonely`` is
  non-empty **and** the schematic model really carries ``pin_wires``. The three
  old shapes are character-for-character what they were, and a ``lonely`` row
  keeps its six keys — nothing is added to a row;
* inside it, four classes that do not overlap: 图纸没画线 (``noWire``, including a
  sheet that holds no wire at all — ``distance: None``, which is **not** 0), 落线
  但网名不同 (``differentNet``), 整块未落线 (``allOffWire``, a designator whose
  lonely feet are *every one* off a line), and 几何缺读数 (``unresolved``, a foot
  with no coordinate — never counted as 「没画线」);
* the note line names **every** row (the ``[:6]`` + ``…`` cut is gone) and, with
  geometry, every foot in each class with its reading; the wording is
  observation only — no 「已证明陈旧板」, and 「整块未落线」 carries
  「落位嫌疑」 and nothing stronger;
* one real archived fixture (``ProPrj_毕设FOC驱动板_v1.0.0``) as **consumer**
  evidence: its 6 real 落线别名 rows survive ``review_read_section`` verbatim and
  ``review_finalize``'s suspected scan still sees the board as ``suspected``.

``ProPrj_ROBOT ctrl FOC`` is deliberately **not** asserted: 038W corrected that
board's vacuum feet, so an expectation copied from the old 「7 条」 reading would
be a fixture-shaped guess rather than a reading (527C2 §4).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from boardwise.core.model import Component, DesignModel, Net, Pin
from boardwise.engines.pcbreview import (
    CROSS_VIEW_MIN_PINS,
    cross_view_geometry,
    cross_view_section,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FOC_V100 = FIXTURES / "ProPrj_毕设FOC驱动板_v1.0.0_2026-10-07.epro2"

ROW_KEYS = [
    "designator",
    "pin",
    "schematicNet",
    "schematicMembers",
    "pcbNet",
    "pcbMembers",
]
GEOMETRY_KEYS = [
    "binding",
    "noWire",
    "differentNet",
    "allOffWire",
    "unresolved",
    "counts",
]

# --------------------------------------------------------------------------
# synthesised models
# --------------------------------------------------------------------------


def _model(
    parts: dict[str, list[str]],
    nets: dict[str, list[tuple[str, str]]] | None = None,
    *,
    pin_wires: dict | None = None,
) -> DesignModel:
    """A ``DesignModel``: pin numbers per designator, then ``name -> members``.

    ``pin_wires`` is passed whole, so a test can state a geometry the parser
    would not have produced (a missing foot, a sheet with no wire) — the engine
    has to read those states correctly, not only the archive's own.
    """
    model = DesignModel()
    for designator, numbers in parts.items():
        model.components[designator] = Component(
            uid=f"uid-{designator}",
            designator=designator,
            pins=[Pin(number=number, name=f"n{number}") for number in numbers],
        )
    for name, members in (nets or {}).items():
        model.nets[name] = Net(name=name, pins=list(members))
    model.pin_wires = pin_wires
    return model


def _pcb(parts: dict[str, list[str]], nets: dict[str, list[tuple[str, str]]]) -> DesignModel:
    """The PCB view: same parts, nets with company. It carries no geometry."""
    return _model(parts, nets)


def _pin_wires(
    pins: dict[tuple[str, str], tuple[str, float, float]],
    wires: dict[str, list[tuple[tuple[float, float], tuple[float, float]]]],
    *,
    binding: str = "endpoint",
) -> dict:
    return {"binding": binding, "pins": pins, "wires": wires}


def _one_foot_each(parts: dict[str, list[str]], prefix: str) -> dict[str, list[tuple[str, str]]]:
    """One one-member net per pin — so every pin of every part is a lonely row."""
    return {
        f"{prefix}{designator}{number}": [(designator, number)]
        for designator, numbers in parts.items()
        for number in numbers
    }


def _pcb_nets(parts: dict[str, list[str]], prefix: str) -> dict[str, list[tuple[str, str]]]:
    """One two-member net per pin: the board says every pin has company."""
    return {
        f"{prefix}{designator}{number}": [
            (designator, number), ("J1", f"{designator}{number}")
        ]
        for designator, numbers in parts.items()
        for number in numbers
    }


def _section(geometry_pins, wires, parts=None, *, binding="endpoint", pcb=None):
    parts = parts or {"U9": ["1", "2", "3"]}
    schematic = _model(
        parts,
        _one_foot_each(parts, "S"),
        pin_wires=_pin_wires(geometry_pins, wires, binding=binding),
    )
    pcb = pcb or _model(parts, _pcb_nets(parts, "N"))
    return cross_view_section(schematic, pcb)


# --------------------------------------------------------------------------
# 1. the four classes, one at a time
# --------------------------------------------------------------------------


def test_a_foot_off_the_lines_and_a_sheet_with_no_wires_are_two_readings():
    """``distance > 0`` is 没画线; a sheet holding no wire is 该页无导线, not 0.

    The second one is the state a reader must not see as 「距离 0」: nobody
    measured a miss there — that sheet simply has no lines to miss. And a foot
    that *is* on a line whose two names disagree is the third reading, listed
    separately with both names. 「On a line」 means on a **segment end**
    (``binding=endpoint``), which is why the third foot sits at ``x=100``.
    """
    section = _section(
        {
            ("U9", "1"): ("page-1", 0.0, 0.0),     # 50 canvas units below the only line
            ("U9", "2"): ("page-2", 10.0, 10.0),   # that sheet has no wire at all
            ("U9", "3"): ("page-1", 100.0, 50.0),  # exactly on the line's far end
        },
        {"page-1": [((0.0, 50.0), (100.0, 50.0))], "page-2": []},
    )

    assert list(section) == [
        "checked", "minPins", "lonely", "status", "candidateMappings", "geometry",
    ], "geometry goes after every existing key"
    geometry = section["geometry"]
    assert list(geometry) == GEOMETRY_KEYS
    assert geometry["binding"] == "endpoint"

    assert [(row["designator"], row["pin"]) for row in geometry["noWire"]] == [
        ("U9", "1"), ("U9", "2")
    ]
    assert geometry["noWire"][0]["distance"] == pytest.approx(50.0)
    assert geometry["noWire"][1]["distance"] is None, "no wire is not distance 0"
    assert geometry["noWire"][1]["page"] == "page-2"

    assert [(row["pin"], row["schematicNet"], row["pcbNet"]) for row in geometry["differentNet"]] == [
        ("3", "SU93", "NU93")
    ]
    assert geometry["unresolved"] == []
    assert geometry["allOffWire"] == [], "one foot is on a line, so not the whole block"
    assert geometry["counts"] == {
        "noWire": 2, "differentNet": 1, "allOffWire": 0, "unresolved": 0,
    }


def test_a_foot_in_the_middle_of_a_line_is_off_the_line_not_an_alias():
    """``binding=endpoint``: only a segment's two **ends** count (B5 fixA).

    The foot sits at (5, 0) in the middle of the line (0, 0)-(10, 0), and the two
    views call its net two different things. Measuring to the segment itself
    would read distance 0 and file it as 落线但网名不同 — a landed alias the
    parser's own ``endpoint`` connectivity rule never claims. The endpoint
    reading is distance 5, so the foot is 图纸没画线, and the two feet that *are*
    on the line's ends keep their alias.
    """
    section = _section(
        {("U9", "1"): ("page-1", 5.0, 0.0),
         ("U9", "2"): ("page-1", 0.0, 0.0),
         ("U9", "3"): ("page-1", 10.0, 0.0)},
        {"page-1": [((0.0, 0.0), (10.0, 0.0))]},
    )
    geometry = section["geometry"]

    assert [row["pin"] for row in geometry["noWire"]] == ["1"]
    assert geometry["noWire"][0]["distance"] == pytest.approx(5.0), (
        "the distance is to the nearest segment end, not to the segment"
    )
    assert [row["pin"] for row in geometry["differentNet"]] == ["2", "3"], (
        "a foot on a segment end is still a landed alias"
    )
    assert geometry["counts"] == {
        "noWire": 1, "differentNet": 2, "allOffWire": 0, "unresolved": 0,
    }


def test_two_sheets_sharing_one_line_are_still_two_sheets():
    """A foot is measured against its **own** sheet's lines, never the whole file.

    Two pages can hold the same coordinates (片 1's negative control), so a
    reader that welds every page's wires into one list turns 「另一个页上有一条
    同坐标的线」 into 「这个脚落在线上」 — the two readings this check must keep
    apart.
    """
    section = _section(
        {("U9", "1"): ("page-1", 100.0, 50.0), ("U9", "2"): ("page-2", 60.0, 50.0)},
        {"page-1": [((0.0, 50.0), (100.0, 50.0))], "page-2": []},
        parts={"U9": ["1", "2", "3"]},
    )
    geometry = section["geometry"]
    assert [(row["designator"], row["pin"], row["distance"]) for row in geometry["noWire"]] == [
        ("U9", "2", None)
    ], "page-2 has no lines of its own, whatever page-1 holds at those coordinates"
    assert [row["pin"] for row in geometry["differentNet"]] == ["1"]
    assert [row["pin"] for row in geometry["unresolved"]] == ["3"]


def test_the_same_name_on_a_line_is_a_difference_the_netlist_already_states():
    """Distance 0 **and** the same name: not a geometry class, and not a silence.

    The row is already disclosed by ``lonely`` — the two views disagree about its
    net's *membership*, not its name. Putting it in ``differentNet`` would state
    a name difference that does not exist.
    """
    schematic = _model(
        {"U9": ["1", "2", "3"]},
        {"ALPHA": [("U9", "1")], "S2": [("U9", "2")], "S3": [("U9", "3")]},
        pin_wires=_pin_wires(
            {("U9", "1"): ("page-1", 100.0, 0.0),
             ("U9", "2"): ("page-1", 0.0, 0.0),
             ("U9", "3"): ("page-1", 0.0, 0.0)},
            {"page-1": [((0.0, 0.0), (100.0, 0.0))]},
        ),
    )
    pcb = _model(
        {"U9": ["1", "2", "3"]},
        {"ALPHA": [("U9", "1"), ("J1", "1")], "N2": [("U9", "2"), ("J1", "2")],
         "N3": [("U9", "3"), ("J1", "3")]},
    )
    section = cross_view_section(schematic, pcb)
    geometry = section["geometry"]

    assert [row["pin"] for row in geometry["differentNet"]] == ["2", "3"]
    assert all(row["schematicNet"] != row["pcbNet"] for row in geometry["differentNet"])
    # pin 1 is on a line and both views call it ALPHA: no class claims it
    assert "1" not in [row["pin"] for row in geometry["differentNet"]]
    assert geometry["counts"]["noWire"] == 0

    from boardwise.cli import _note_cross_view_lonely

    notes: list[str] = []
    _note_cross_view_lonely(notes, {"boards": [{"title": "B", "crossView": section}]})
    assert "落在线上且两视图网名相同 1 个" in notes[0], (
        "a foot on a line with the same name is stated, not left as silence"
    )


def test_a_whole_block_off_the_lines_is_a_hint_and_a_partial_one_is_not():
    """``allOffWire`` is the designator's **every** lonely foot, raw counts only.

    No ratio threshold anywhere: U9 has three feet off a line and one on it, so
    it is not this shape at all — which is what keeps a high-speed part with
    10/16 feet drawn from being read as 「整块落位」.
    """
    parts = {"U9": ["1", "2", "3", "4"], "U7": ["1", "2", "3"]}
    geometry_pins = {
        ("U9", "1"): ("page-1", 0.0, 500.0),
        ("U9", "2"): ("page-1", 10.0, 500.0),
        ("U9", "3"): ("page-1", 20.0, 500.0),
        ("U9", "4"): ("page-1", 100.0, 0.0),
        ("U7", "1"): ("page-1", 0.0, 900.0),
        ("U7", "2"): ("page-1", 10.0, 900.0),
        ("U7", "3"): ("page-1", 20.0, 900.0),
    }
    section = _section(geometry_pins, {"page-1": [((0.0, 0.0), (100.0, 0.0))]}, parts=parts)
    geometry = section["geometry"]

    assert geometry["allOffWire"] == [{"designator": "U7", "offWire": 3, "pins": 3}]
    assert [row["pin"] for row in geometry["noWire"]] == ["1", "2", "3", "1", "2", "3"]
    assert geometry["counts"] == {
        "noWire": 6, "differentNet": 1, "allOffWire": 1, "unresolved": 0,
    }

    from boardwise.cli import _note_cross_view_lonely

    notes: list[str] = []
    _note_cross_view_lonely(notes, {"boards": [{"title": "B", "crossView": section}]})
    note = notes[0]
    assert "整块未落线（落位嫌疑，只报观测）1 个器件：U7（3/3 脚）" in note
    assert "已证明" not in note and "陈旧" not in note, (
        "the hint describes the drawing; it may not sentence the board"
    )


def test_a_missing_coordinate_is_its_own_state_and_never_no_wire():
    """「没看」 ≠ 「看了，没有」: no coordinate is ``unresolved``, not ``noWire``.

    Two gaps are named separately — the model carries no point for the foot
    (``missingPin``), or it carries one on a sheet the geometry never projected
    (``missingPage``). Both may be counted as neither off a line nor on one.
    """
    section = _section(
        {
            ("U9", "1"): ("page-1", 100.0, 0.0),  # on the line's far end, names differ
            # U9.2: no coordinate at all
            ("U9", "3"): ("page-9", 10.0, 0.0),   # sheet never projected
        },
        {"page-1": [((0.0, 0.0), (100.0, 0.0))]},
    )
    geometry = section["geometry"]

    assert [(row["pin"], row["reason"]) for row in geometry["unresolved"]] == [
        ("2", "missingPin"), ("3", "missingPage"),
    ]
    assert geometry["noWire"] == [], "a gap may not be reported as 没画线"
    assert [row["pin"] for row in geometry["differentNet"]] == ["1"]
    assert geometry["counts"]["unresolved"] == 2
    assert geometry["allOffWire"] == [], "a gap is not an off-wire foot"

    from boardwise.cli import _note_cross_view_lonely

    notes: list[str] = []
    _note_cross_view_lonely(notes, {"boards": [{"title": "B", "crossView": section}]})
    note = notes[0]
    assert "几何缺读数 2 个：U9.2（模型无该脚坐标）、U9.3（该页几何未投影）" in note
    assert "图纸没画线" not in note


def test_the_helper_reads_none_for_a_model_with_no_drawing_behind_it():
    """``None`` is 「没几何」, and a model with no ``pin_wires`` is never 「没画线」."""
    assert cross_view_geometry(_model({"U9": ["1"]}), []) is None
    assert cross_view_geometry(DesignModel(), []) is None
    assert cross_view_geometry(object(), []) is None


# --------------------------------------------------------------------------
# 2. the old shapes, byte for byte
# --------------------------------------------------------------------------


def test_a_model_without_geometry_keeps_the_old_section_and_the_old_note():
    """KiCad/``.enet``/manual models state no ``pin_wires``: no key, no clause."""
    parts = {"U9": ["1", "2", "3"]}
    section = cross_view_section(
        _model(parts, _one_foot_each(parts, "S")), _pcb(parts, _pcb_nets(parts, "N"))
    )
    assert list(section) == ["checked", "minPins", "lonely", "status", "candidateMappings"]
    assert "geometry" not in section

    from boardwise.cli import _note_cross_view_lonely

    notes: list[str] = []
    _note_cross_view_lonely(notes, {"boards": [{"title": "B", "crossView": section}]})
    assert "几何读数" not in notes[0] and "geometry" not in notes[0]


def test_an_empty_lonely_list_never_grows_a_geometry():
    """「一致」 acquires no geometry — even when the model does carry one."""
    keys = {"1": "ALPHA", "2": "BETA", "3": "GAMMA"}
    parts = {"U9": ["1", "2", "3"]}
    nets = {name: [("U9", number), ("J1", number)] for number, name in keys.items()}
    schematic = _model(
        parts,
        nets,
        pin_wires=_pin_wires(
            {("U9", "1"): ("page-1", 0.0, 0.0),
             ("U9", "2"): ("page-1", 0.0, 0.0),
             ("U9", "3"): ("page-1", 0.0, 0.0)},
            {"page-1": [((0.0, 0.0), (100.0, 0.0))]},
        ),
    )
    pcb = _model(parts, nets)
    section = cross_view_section(schematic, pcb)
    assert section == {"checked": True, "minPins": CROSS_VIEW_MIN_PINS, "lonely": []}
    assert list(section) == ["checked", "minPins", "lonely"]


def test_every_unchecked_shape_is_untouched():
    parts = {"U9": ["1", "2", "3"]}
    schematic = _model(
        parts, _one_foot_each(parts, "S"),
        pin_wires=_pin_wires(
            {("U9", "1"): ("page-1", 0.0, 0.0)}, {"page-1": []}
        ),
    )
    pcb = _pcb(parts, _pcb_nets(parts, "N"))
    for section in (
        cross_view_section(None, pcb),
        cross_view_section(schematic, None),
    ):
        assert list(section) == ["checked", "reason"]
        assert "geometry" not in section


def test_a_lonely_row_keeps_its_six_keys_even_with_geometry():
    """The row is 189A2's contract; the geometry is the section's, not the row's."""
    section = _section(
        {("U9", "1"): ("page-1", 0.0, 90.0),
         ("U9", "2"): ("page-1", 0.0, 90.0),
         ("U9", "3"): ("page-1", 0.0, 0.0)},
        {"page-1": [((0.0, 0.0), (100.0, 0.0))]},
    )
    assert "geometry" in section
    for row in section["lonely"]:
        assert list(row) == ROW_KEYS


# --------------------------------------------------------------------------
# 3. the note line names every row and every class
# --------------------------------------------------------------------------


def test_the_note_names_every_row_not_the_first_six():
    """The cut at six is what a reader cannot act on: the pin cut is the one to check."""
    parts = {"U9": [str(number) for number in range(1, 9)]}
    # 8 pins, one per designator net; every foot sits 500 canvas units above the only line
    geometry_pins = {("U9", number): ("page-1", 0.0, 500.0 * float(number))
                     for number in parts["U9"]}
    section = _section(geometry_pins, {"page-1": [((0.0, 0.0), (100.0, 0.0))]}, parts=parts)
    assert len(section["lonely"]) == 8

    from boardwise.cli import _note_cross_view_lonely

    notes: list[str] = []
    _note_cross_view_lonely(notes, {"boards": [{"title": "B", "crossView": section}]})
    note = notes[0]
    for number in parts["U9"]:
        assert f"U9.{number}" in note, f"row U9.{number} was cut from the note"
    assert "…" not in note, "the ellipsis was the truncation"
    assert note.count("距最近线端") == 8, "every off-line foot states its distance"
    assert section["geometry"]["counts"]["noWire"] == 8


def test_the_clause_is_observation_only():
    """No 「已证明陈旧板」: the note states what was drawn and picks no side."""
    section = _section(
        {("U9", "1"): ("page-1", 0.0, 0.0),
         ("U9", "2"): ("page-1", 0.0, 40.0),
         ("U9", "3"): ("page-1", 100.0, 0.0)},
        {"page-1": [((0.0, 0.0), (100.0, 0.0)), ((0.0, 40.0), (100.0, 40.0))]},
    )
    from boardwise.cli import _note_cross_view_lonely

    notes: list[str] = []
    _note_cross_view_lonely(notes, {"boards": [{"title": "B", "crossView": section}]})
    note = notes[0]
    assert "落线但两视图网名不同 3 个：" in note
    assert "U9.1（SU91→NU91）" in note
    assert "都不是天然权威" in note
    for claim in ("已证明", "确定是陈旧", "旧板", "确认"):
        assert claim not in note


# --------------------------------------------------------------------------
# 4. the consumer half: a real archive, verbatim through review-read
# --------------------------------------------------------------------------


def test_the_real_v100_board_carries_its_landed_aliases_through_the_reader():
    """``ProPrj_毕设FOC驱动板_v1.0.0``: 6 real 落线别名 rows, read verbatim.

    This is the consumer evidence 527C2 §4 asks for, on the fixture the task book
    names: U10's six gate/sense feet are **on** the drawing (distance 0) and the
    two archives call each of those nets two different things — so the section
    gains a ``differentNet`` list and nothing else. The reader copies the whole
    section verbatim (``geometry`` included), the board is still ``suspected``,
    and the report object is not mutated.
    """
    from boardwise.engines.pcbreview import run_pcb_review
    from boardwise.engines.reviewfinalize import _suspected_boards
    from boardwise.engines.reviewread import review_read_section
    from boardwise.parsers.schematic import build_project_model

    model = build_project_model(FOC_V100)
    _findings, section = run_pcb_review(FOC_V100, model=model)
    assert section is not None
    boards = section["boards"]
    assert [entry["title"] for entry in boards] == ["PCB1", "PCB2"]

    first = boards[0]["crossView"]
    assert first["checked"] is True and first["status"] == "suspected"
    assert len(first["lonely"]) == 6
    geometry = first["geometry"]
    assert geometry["binding"] == "endpoint"
    assert geometry["counts"] == {
        "noWire": 0, "differentNet": 6, "allOffWire": 0, "unresolved": 0,
    }
    assert [(row["designator"], row["pin"]) for row in geometry["differentNet"]] == [
        ("U10", "6"), ("U10", "8"), ("U10", "9"),
        ("U10", "11"), ("U10", "14"), ("U10", "16"),
    ]
    assert geometry["differentNet"][0]["schematicNet"] == "SHA"
    assert geometry["differentNet"][0]["pcbNet"] == "MOTA"

    # PCB2's one row is on a line and the two views agree on the name: a real
    # 同名落线 foot, so its geometry states the zero counts rather than a class.
    second = boards[1]["crossView"]
    assert len(second["lonely"]) == 1
    assert second["geometry"]["counts"] == {
        "noWire": 0, "differentNet": 0, "allOffWire": 0, "unresolved": 0,
    }

    report = {"pcb_review": section}
    before = repr(report)
    payload = review_read_section(report, "crossView")
    assert repr(report) == before, "the reader may not mutate the report"
    copied = payload["boards"][0]["crossView"]
    assert copied == first, "verbatim: geometry travels whole, nothing filtered"
    assert copied is not first
    assert copied["status"] == "suspected"
    assert copied["geometry"] == geometry

    # finalize's own reading of the same report: still suspected, nothing derived
    # from the geometry may upgrade it.
    assert _suspected_boards(report) == [0, 1]


def test_the_note_clause_on_the_real_board_names_all_six_aliases():
    """The note half, on real bytes: six feet, six names, no truncation."""
    from boardwise.cli import _note_cross_view_lonely
    from boardwise.engines.pcbreview import run_pcb_review
    from boardwise.parsers.schematic import build_project_model

    model = build_project_model(FOC_V100)
    _findings, section = run_pcb_review(FOC_V100, model=model)
    notes: list[str] = []
    _note_cross_view_lonely(notes, section)
    assert len(notes) == 1
    note = notes[0]
    assert "落线但两视图网名不同 6 个：U10.6（SHA→MOTA）" in note
    assert "U10.16（SLC→IC+）" in note
    assert "几何读数（binding=endpoint" in note
    assert "…" not in note
