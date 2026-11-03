"""038P — a folder project with several boards, read board by board.

The real V4 sample (`test V4`) ships two boards as two files — `pcb/PCB1.epcb2`
and `pcb/PCB2.epcb2` — and before this batch the adapter refused the project
outright at `load_eprj3_pcb_source`, *before* any mapping was even read, so
`checkup --file` lost the whole PCB half of the report on a project the online
path (which hands the same reader a whole-project archive) reviews without
complaint. The fix is the container and only the container: the adapter reads
every `pcb/**/*.epcb2` in `pcb_files` order into **one** multi-document stream,
which is the shape an `.epro2` of a multi-board project already has.

Everything below therefore pins the seam, not a new architecture:

* both boards arrive, each with its own title and its own `META.board`;
* the order is the files', never the index's and never a count;
* a board file with no PCB document is still refused **by name** — the other
  board does not excuse it;
* `_pcb_documents` prefers the project's own names (`pcbTitles`, a list in
  PCB-document order since 038P1), and
  `boardUuid` stays the `META.board` link rather than being guessed from a title;
* `checkup --file` produces one `boards[]` entry and one findings slice per
  board, so an empty board still discloses itself instead of disappearing;
* `_load_model(view="pcb")` — one model, one board — refuses several **by name**
  and points at the per-board path, instead of answering with the first board;
* one board reads exactly as it did before.

All shapes here are anonymous synthetic streams in the real record frame; the
sample project is read-only evidence and is not copied into the repo.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from boardwise import cli
from boardwise.engines.pcbreview import _pcb_documents, run_pcb_review
from boardwise.parsers.eprj3 import Eprj3Error, load_eprj3_pcb_source, pcb_files

SHELF = Path(__file__).resolve().parents[1] / "blocklib" / "parts.json"


# --------------------------------------------------------------------------
# a folder project: an index and the board files the caller spells out
# --------------------------------------------------------------------------


def _record(envelope: dict, body: dict | None = None) -> str:
    head = json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))
    if body is None:
        return head + "|||"
    return head + "||" + json.dumps(body, ensure_ascii=False, separators=(",", ":")) + "|"


def _head(doc_type: str, uuid: str, version: str = "4.1.60") -> str:
    return _record({"type": "DOCHEAD"},
                   {"docType": doc_type, "uuid": uuid, "editVersion": version})


def _pcb_stream(
    *,
    uuid: str,
    title: str,
    board: str = "",
    designator: str | None = None,
) -> str:
    """One board document: its DOCHEAD, its own META, and an optional placed part.

    ``board`` is the ``META.board`` link to the schematic ``BOARD`` document (151)
    — the one thing a board's **identity** comes from. ``designator=None`` leaves
    the board with no placement at all, which is what an un-laid-out board in the
    sample looks like.
    """
    lines = [
        _head("PCB", uuid),
        _record({"type": "META", "id": "META"},
                {"title": title, "board": board, "docType": 3}),
        _record({"type": "CANVAS", "id": "CANVAS"},
                {"originX": 0, "originY": 1000.0, "yAxisDirection": "up"}),
    ]
    if designator is not None:
        lines += [
            _record({"type": "COMPONENT", "id": "part-u1"},
                    {"partId": "part-u1", "x": 10.0, "y": 20.0, "rotation": 0,
                     "zIndex": 1}),
            _record({"type": "ATTR", "id": "attr-u1"},
                    {"parentId": "part-u1", "key": "Designator", "value": designator}),
        ]
    return "\n".join(lines) + "\n"


def _page() -> str:
    """One page placing U1 on a two-pin symbol — enough for a schematic model."""
    lines = [_head("SCH_PAGE", "page-1"),
             _record({"type": "CANVAS"},
                     {"originX": 0, "originY": 0, "unit": "0.01inch"}),
             _head("SYMBOL", "sym-1", "1.0.0"),
             _record({"type": "META", "id": "META"}, {"title": "R", "docType": "SYMBOL"})]
    for index, number in enumerate(("1", "2")):
        pin_id = f"e{index + 1}"
        lines.append(_record({"type": "PIN", "id": pin_id},
                             {"x": 0.0, "y": float(index) * 20.0, "zIndex": index + 2}))
        lines.append(_record({"type": "ATTR", "id": f"n{index}"},
                             {"parentId": pin_id, "key": "Pin Number", "value": number}))
    lines += [
        _record({"type": "COMPONENT", "id": "c-inst"},
                {"partId": "inst-u1", "x": 300.0, "y": -500.0, "rotation": 0,
                 "isMirror": False, "zIndex": 10}),
        _record({"type": "ATTR", "id": "d-inst"},
                {"parentId": "inst-u1", "key": "Designator", "value": "U1"}),
        _record({"type": "ATTR", "id": "s-inst"},
                {"parentId": "inst-u1", "key": "Symbol", "value": "sym-1"}),
    ]
    return "\n".join(lines) + "\n"


def _write_project(
    root: Path,
    *,
    boards: dict[str, str] | None = None,
    pcb_titles: dict[str, str] | None = None,
    page: bool = True,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    index: dict = {
        "name": root.name,
        "owner_uuid": "0123456789abcdef0123456789abcdef",
        "format": "folder",
        "profile": {"schematics": {}, "sheets": {}, "pcbs": {}},
    }
    for uuid, title in (pcb_titles or {}).items():
        index["profile"]["pcbs"][uuid] = {"uuid": uuid, "title": title}
    (root / f"{root.name}.eprj3").write_text(
        json.dumps(index, ensure_ascii=False), encoding="utf-8")
    if page:
        page_dir = root / "sch" / "Schematic1"
        page_dir.mkdir(parents=True, exist_ok=True)
        (page_dir / "P1.esch2").write_text(_page(), encoding="utf-8")
    for relative, text in (boards or {}).items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return root


def _two_boards() -> dict[str, str]:
    return {
        "pcb/PCB1.epcb2": _pcb_stream(
            uuid="doc-a", title="PCB1", board="board-a", designator="U1"),
        "pcb/PCB2.epcb2": _pcb_stream(
            uuid="doc-b", title="PCB2", board="board-b", designator="U2"),
    }


# --------------------------------------------------------------------------
# 1. both boards arrive, each with its own identity, in file order
# --------------------------------------------------------------------------


def test_both_boards_are_read_into_one_stream(tmp_path):
    root = _write_project(tmp_path / "proj", boards=_two_boards())

    source = load_eprj3_pcb_source(root)

    assert [document.uuid for document in source.documents_of_type("PCB")] == [
        "doc-a", "doc-b"
    ]
    assert source.project_meta["pcbPaths"] == [
        str(root / "pcb" / "PCB1.epcb2"), str(root / "pcb" / "PCB2.epcb2")
    ]
    assert "title" not in source.project_meta, (
        "a single `title` here would name the project after its first board"
    )


def test_the_order_is_the_files_not_the_index(tmp_path):
    """The index lists PCB2 first; the stream follows `pcb_files`, which is sorted."""
    root = _write_project(
        tmp_path / "proj",
        boards=_two_boards(),
        pcb_titles={"doc-b": "PCB2", "doc-a": "PCB1"},
    )
    first = load_eprj3_pcb_source(root)
    second = load_eprj3_pcb_source(root)

    order = [document.uuid for document in first.documents_of_type("PCB")]
    assert order == ["doc-a", "doc-b"], "PCB1.epcb2 sorts before PCB2.epcb2"
    assert order == [document.uuid for document in second.documents_of_type("PCB")], (
        "two reads of one project give one order"
    )
    assert [path.name for path in pcb_files(root)] == ["PCB1.epcb2", "PCB2.epcb2"]


def test_each_board_keeps_its_own_title_and_board_link(tmp_path):
    root = _write_project(tmp_path / "proj", boards=_two_boards())
    source = load_eprj3_pcb_source(root)

    named = [(title, uuid) for title, uuid, _document in _pcb_documents(source)]

    assert named == [("PCB1", "board-a"), ("PCB2", "board-b")], (
        "the title is the document's META; the board uuid is its META.board link"
    )


# --------------------------------------------------------------------------
# 2. a board file with no board in it is still refused, by name
# --------------------------------------------------------------------------


def test_a_board_file_without_a_pcb_document_is_named(tmp_path):
    root = _write_project(
        tmp_path / "proj",
        boards={
            "pcb/PCB1.epcb2": _pcb_stream(uuid="doc-a", title="PCB1", board="board-a"),
            "pcb/PCB2.epcb2": "\n".join([
                _head("FOOTPRINT", "fp-1"),
                _record({"type": "META", "id": "META"}, {"title": "LIB", "docType": 4}),
                _record({"type": "RECT", "id": "r1"}, {"dotX1": 0, "dotY1": 0}),
            ]) + "\n",
        },
    )

    with pytest.raises(Eprj3Error) as caught:
        load_eprj3_pcb_source(root)
    message = str(caught.value)
    assert "PCB2.epcb2" in message, "the refusal names the file it cannot read as a board"
    assert "PCB document" in message
    assert "PCB1.epcb2" not in message, (
        "the good board is not blamed for the empty one"
    )


# --------------------------------------------------------------------------
# 3. the project's own names win; identity is never guessed from a name
# --------------------------------------------------------------------------


def test_the_project_index_names_the_boards(tmp_path):
    root = _write_project(
        tmp_path / "proj",
        boards=_two_boards(),
        pcb_titles={"doc-a": "Main", "doc-b": "Aux"},
    )
    source = load_eprj3_pcb_source(root)

    assert source.project_meta["pcbTitles"] == ["Main", "Aux"], (
        "the index's titles, in PCB-document order — 038P1 moved this table from "
        "a uuid→name dict to a positional list so a uuid-less board can be named"
    )
    assert [title for title, _uuid, _doc in _pcb_documents(source)] == ["Main", "Aux"], (
        "the index's title is the project's word for the board"
    )
    assert [uuid for _title, uuid, _doc in _pcb_documents(source)] == [
        "board-a", "board-b"
    ], "boardUuid still comes from META.board — a title never implies a board"


def test_an_unnamed_board_falls_back_to_its_own_meta(tmp_path):
    root = _write_project(
        tmp_path / "proj",
        boards=_two_boards(),
        pcb_titles={"doc-a": "Main"},
    )
    source = load_eprj3_pcb_source(root)

    assert [title for title, _uuid, _doc in _pcb_documents(source)] == ["Main", "PCB2"]


# --------------------------------------------------------------------------
# 4. the runner: one entry per board, reviewed independently
# --------------------------------------------------------------------------


def test_the_runner_reports_both_boards_with_their_own_readings(tmp_path):
    root = _write_project(tmp_path / "proj", boards=_two_boards())

    findings, section = run_pcb_review(root)

    assert section is not None and section["available"] is True
    titles = [entry["title"] for entry in section["boards"]]
    assert titles == ["PCB1", "PCB2"]
    assert [entry["boardUuid"] for entry in section["boards"]] == ["board-a", "board-b"]
    assert [entry["components"] for entry in section["boards"]] == [1, 1]
    assert all(entry["checksRun"] for entry in section["boards"])
    indexes = [index for entry in section["boards"] for index in entry["findings"]]
    assert len(indexes) == len(set(indexes)), "no board re-reports the other's rows"
    assert [findings[index].board for index in indexes][0] in ("PCB1", "PCB2")


# --------------------------------------------------------------------------
# 5. `checkup --file`: the per-board path, end to end
# --------------------------------------------------------------------------


def _run_checkup(tmp_path: Path, monkeypatch, project: Path, name: str) -> tuple[int, dict]:
    monkeypatch.setenv("BOARDWISE_HOME", str(tmp_path / f"home-{name}"))
    out = tmp_path / name
    code = cli.main([
        "checkup", "--file", str(project), "--out", str(out), "--library", str(SHELF),
    ])
    return code, json.loads((out / "report.json").read_text(encoding="utf-8"))


def test_checkup_reviews_both_boards_and_indexes_their_findings(tmp_path, monkeypatch):
    """Both boards are un-laid-out: the sample's shape, and still two reviewed boards."""
    root = _write_project(
        tmp_path / "proj",
        boards={
            "pcb/PCB1.epcb2": _pcb_stream(
                uuid="doc-a", title="PCB1", board="board-a"),
            "pcb/PCB2.epcb2": _pcb_stream(
                uuid="doc-b", title="PCB2", board="board-b"),
        },
    )

    code, report = _run_checkup(tmp_path, monkeypatch, root, "multi")

    review = report["pcb_review"]
    assert [entry["title"] for entry in review["boards"]] == ["PCB1", "PCB2"]
    assert [entry["boardUuid"] for entry in review["boards"]] == ["board-a", "board-b"]
    assert [entry["components"] for entry in review["boards"]] == [0, 0], (
        "an un-laid-out board reads 0 placed parts — a reading, not a missing board"
    )
    assert all(entry["outlineNote"] for entry in review["boards"]), (
        "and it discloses that it has no board outline rather than passing silently"
    )
    rows = report["findings"]
    for entry in review["boards"]:
        assert entry["findings"], "a board with schematic parts and no placement is checked"
        rules = set()
        for index in entry["findings"]:
            assert rows[index]["board"] == entry["title"], (
                "each finding index lands on a row stamped with that board's title"
            )
            rules.add(rows[index]["rule_id"])
        assert "pcb-footprint-consistency" in rules, (
            "an empty board still reports the parts the schematic placed on it"
        )
    assert report["completion"]["coverage"]["pcbReviewMissing"] is False
    assert code == report["conclusion"]["exitCode"]


# --------------------------------------------------------------------------
# 6. `_load_model(view="pcb")`: one model is one board — refuse, do not pick
# --------------------------------------------------------------------------


def test_load_model_refuses_several_boards_instead_of_taking_the_first(tmp_path):
    root = _write_project(tmp_path / "proj", boards=_two_boards())

    with pytest.raises(ValueError) as caught:
        cli._load_model(root, view="pcb")
    message = str(caught.value)
    assert "2 块板" in message
    assert "PCB1" in message and "PCB2" in message, "the boards are listed by name"
    assert "checkup" in message, "the refusal points at the per-board path"


# --------------------------------------------------------------------------
# 7. one board still reads exactly as before
# --------------------------------------------------------------------------


def test_a_single_board_keeps_the_historic_shape(tmp_path):
    root = _write_project(
        tmp_path / "proj",
        boards={"pcb/PCB1.epcb2": _pcb_stream(
            uuid="doc-a", title="PCB1", board="board-a", designator="U1")},
    )
    source = load_eprj3_pcb_source(root)

    assert source.project_meta["title"] == "PCB1"
    assert "pcbTitles" not in source.project_meta, "one board has no table to consult"
    model, board = cli._load_model(root, view="pcb")
    assert "U1" in model.components
    assert board is not None and board.name == "PCB1"
