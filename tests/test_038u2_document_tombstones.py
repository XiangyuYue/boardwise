"""038U2 — whole-document deletion and revival in the ``.epru`` record stream.

038U1 settled how two versions of **one element id** coexist. This batch is the
other half of the same format rule (``tasks/038u2_document_tombstones.md`` §2):

    ``{"type":"DELETE_DOC","ticket":N}||{"isDelete":true}``

retires a whole **document**; ``isDelete: false`` revokes that; and a
``DELETE_DOC`` whose body is **empty** is *not* a deletion — that empty body is
the *element* tombstone's shape and the two may never be conflated.

The scope is deliberately narrow. Documents are **not merged**, ``pend``/
``revoke`` is not implemented, and the raw frame log is untouched: only what a
model consumer receives changes. So every test below is asked of a public entry
— ``split_documents``, ``resolve_records``, ``build_project_model``,
``collect_page_layout``, ``parse_epru_text`` — over a synthetic one-stream
``.epro2`` in ``tmp_path``. No fixture is written, and the two archived pages
that matter are only **read**.

The last group pins the two archived deletions the ruling accepted knowingly:
the 毕设板's and the 高速电机控制器's empty P2 pages disappear from their boards'
page lists, one document each, and nothing else about those files moves.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from boardwise.core.geometry import ParseStats
from boardwise.parsers.epru import parse_epru_text
from boardwise.parsers.epru_stream import (
    Document,
    EpruRecord,
    iter_epru_records,
    load_epru_text,
    resolve_document,
    resolve_records,
    split_documents,
)
from boardwise.parsers.schematic import build_project_model, collect_page_layout

FIXTURES = Path(__file__).parent / "fixtures"
#: The two archived projects that really carry a ``DELETE_DOC`` (measured over all
#: 14 ``.epro2`` fixtures: exactly these two, one marker each, both ``isDelete:
#: true``, both on a three-record empty ``SCH_PAGE`` whose title is ``P2``).
ARCHIVED_DELETIONS = {
    # project file -> (board title, page uuid the file retired)
    "ProPrj_毕设FOC驱动板_2026-09-17.epro2": ("Board1", "b0342c521c674ddab8dcc8aaf269ca59"),
    "ProPrj_高速电机控制器_2026-09-16.epro2": ("控制板", "0c399818fb0c5cf7"),
}

# --------------------------------------------------------------------------
# record / stream synthesis
# --------------------------------------------------------------------------


def _rec(type_: str, *, ticket=None, id=None, client=None, body=None) -> str:
    """One record line. ``body=None`` writes the empty-body shape ``{env}|||``."""
    envelope: dict = {"type": type_}
    if ticket is not None:
        envelope["ticket"] = ticket
    if id is not None:
        envelope["id"] = id
    if client is not None:
        envelope["client"] = client
    text = json.dumps(envelope)
    return f"{text}|||" if body is None else f"{text}||{json.dumps(body)}|"


def _head(doc_type: str = "PCB", uuid: str = "u1", client=None, ticket: int = 0) -> str:
    body: dict = {"docType": doc_type, "uuid": uuid}
    if client is not None:
        body["client"] = client
    return _rec("DOCHEAD", ticket=ticket, body=body)


def _delete(ticket, *, client=None, flag: object = True) -> str:
    """A ``DELETE_DOC`` marker; ``flag=...`` writes whatever ``isDelete`` holds."""
    body: dict = {} if flag is ... else {"isDelete": flag}
    return _rec("DELETE_DOC", ticket=ticket, client=client, body=body)


def _split(*lines: str, consistent: bool = False):
    stats = ParseStats()
    return split_documents("\n".join(lines), stats, consistent=consistent), stats


def _epro2(tmp_path: Path, lines: list[str], name: str = "synth.epro2") -> Path:
    path = tmp_path / name
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("synth.epru", "\n".join(lines) + "\n")
        archive.writestr("project2.json", json.dumps({"title": "synthetic"}))
    return path


def _sch_part(uid: str, ticket: int, *, x: float = 0.0, y: float = 0.0) -> str:
    return _rec("COMPONENT", ticket=ticket, id=uid, body={
        "partId": "R0402.1", "x": x, "y": y, "rotation": 0, "isMirror": False,
        "zIndex": 5,
    })


def _attr(uid: str, parent: str, key: str, value: str, *, ticket: int = 1) -> str:
    return _rec("ATTR", ticket=ticket, id=uid,
                body={"parentId": parent, "key": key, "value": value})


def _board_part(uid: str, ticket: int, *, x: float = 0.0, y: float = 0.0) -> str:
    return _rec("COMPONENT", ticket=ticket, id=uid, body={
        "x": x, "y": y, "angle": 0, "layerId": 1,
    })


# --------------------------------------------------------------------------
# the raw layer: a known type, and nothing else moves
# --------------------------------------------------------------------------


def test_delete_doc_is_a_known_record_type():
    """It was reported as format drift before this batch (``unknown_types``).

    The raw counts are the point of the assertion: ``DELETE_DOC`` is *counted*
    (``records_by_type``) and no longer flagged, while every pre-existing raw
    counter keeps its pre-038U2 meaning — a marker is neither a malformed line
    nor an empty-*element* body, and the total is every line read.
    """
    _docs, stats = _split(
        _head(), _rec("COMPONENT", ticket=1, id="c1", body={"x": 1}), _delete(9)
    )

    assert stats.records_by_type["DELETE_DOC"] == 1
    assert "DELETE_DOC" not in stats.unknown_types
    assert stats.total_records == 3
    assert stats.malformed_records == 0
    assert stats.empty_body_records == 0, "the marker's body is a body, not an empty one"
    assert stats.deleted_documents == 0, "the raw split never decides the document state"


def test_the_raw_view_keeps_a_deleted_document_and_the_view_drops_it():
    """``consistent`` is the switch; the default is the byte-for-byte frame log."""
    lines = (
        _head("PCB", uuid="live"),
        _rec("COMPONENT", ticket=1, id="c1", body={"x": 1}),
        _head("PCB", uuid="gone"),
        _rec("COMPONENT", ticket=2, id="c2", body={"x": 2}),
        _delete(9),
    )

    raw, raw_stats = _split(*lines)
    kept, stats = _split(*lines, consistent=True)

    assert [document.uuid for document in raw] == ["live", "gone"]
    assert [len(document.records) for document in raw] == [2, 3]
    assert [document.deleted for document in raw] == [False, False]
    assert raw_stats.deleted_documents == 0

    assert [document.uuid for document in kept] == ["live"], (
        "a tombstoned document is not something a model reader may see"
    )
    assert stats.deleted_documents == 1
    # The raw counters are still the raw counters in the consistent run: the view
    # decides what a reader gets, it never re-counts the file.
    for name in ("total_records", "empty_body_records", "malformed_records"):
        assert getattr(stats, name) == getattr(raw_stats, name), name
    assert stats.records_by_type == raw_stats.records_by_type


def test_a_deleted_document_keeps_its_own_metadata_and_loses_only_its_records():
    """``deleted=True`` is a tombstone, not a document that happened to be empty."""
    document = Document(
        doc_type="PCB", uuid="pcb1", edit_version="3.2.1", client="c0",
        records=[
            EpruRecord(line_no=0, type="DOCHEAD", ticket=0),
            EpruRecord(line_no=1, type="COMPONENT", ticket=2, id="c1", body={"x": 1}),
            EpruRecord(line_no=2, type="DELETE_DOC", ticket=9, body={"isDelete": True}),
        ],
    )
    stats = ParseStats()

    resolved = resolve_document(document, stats)

    assert resolved is not document
    assert (resolved.doc_type, resolved.uuid, resolved.edit_version, resolved.client) == (
        "PCB", "pcb1", "3.2.1", "c0",
    )
    assert resolved.records == [] and resolved.deleted is True
    assert stats.deleted_documents == 1


# --------------------------------------------------------------------------
# the document-state rule: true / false / several markers
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "markers,expected",
    [
        ((_delete(10, flag=True), _delete(20, flag=False)), True),
        ((_delete(20, flag=False), _delete(10, flag=True)), True),
        ((_delete(20, flag=True), _delete(10, flag=False)), False),
        ((_delete(10, flag=False), _delete(20, flag=True)), False),
    ],
    ids=["true-then-false", "false-then-true", "false-then-true-higher", "true-then-false-higher"],
)
def test_the_highest_ticket_decides_the_document_state_not_the_arrival_order(markers, expected):
    """``isDelete:false`` revokes a deletion — when it carries the winning ticket.

    Stream order is never the answer (038U1's rule, reused here): the two cases
    where ``false`` arrives last and the two where ``true`` does must be decided
    by the ticket alone.
    """
    kept, stats = _split(_head(), _rec("ATTR", ticket=1, id="a1", body={"Value": "R1"}),
                         *markers, consistent=True)

    assert [document.deleted for document in kept] == ([False] if expected else []), markers
    assert stats.deleted_documents == (0 if expected else 1)
    assert stats.consistency_unresolved == 0


@pytest.mark.parametrize("sequence", [("a0", "b0"), ("b0", "a0")])
def test_a_same_ticket_tie_goes_to_the_larger_client(sequence):
    """The official tie-break, on the document markers, in both arrival orders."""
    flags = {"a0": False, "b0": True}
    markers = [_delete(10, client=client, flag=flags[client]) for client in sequence]
    kept, stats = _split(_head(), *markers, consistent=True)

    assert [document.deleted for document in kept] == [], (
        "b0 owns the larger client, so its `true` is the answer either way"
    )
    assert stats.deleted_documents == 1
    assert stats.consistency_duplicate_groups == 0, (
        "a document marker is not an element id: several `DELETE_DOC` rows about "
        "one document are one document-level question, so they never land in the "
        "element duplicate-group count"
    )


@pytest.mark.parametrize(
    "line",
    [
        _rec("DELETE_DOC", ticket=9),
        f"{json.dumps({'type': 'DELETE_DOC', 'ticket': 9})}||",
        _delete(9, flag=...),
    ],
    ids=["empty-body", "empty-body-no-terminator", "empty-object"],
)
def test_an_empty_delete_doc_body_is_not_a_deletion(line):
    """The format's explicit warning: the empty body is the *element* tombstone.

    A ``DELETE_DOC`` with no payload says nothing about the document, and reading
    it as a document delete would silently retire a page the editor never
    retired. It stays, and the element shape keeps its own meaning.
    """
    kept, stats = _split(_head(), line, consistent=True)

    assert [document.deleted for document in kept] == [False]
    assert stats.deleted_documents == 0
    assert stats.consistency_unresolved == 0, "an empty body is legal, not an anomaly"


@pytest.mark.parametrize(
    "markers",
    [
        (_rec("DELETE_DOC", body={"isDelete": True}),),                       # no ticket
        (_delete("10", flag=True),),                                          # numeric string
        (_delete(True, flag=True),),                                          # bool ticket
        (_delete(3.5, flag=True),),                                           # fractional
        (_delete(10, flag="true"),),                                          # string flag
        (_delete(10, flag=1),),                                               # int flag
        (_delete(10, flag=None),),                                            # null flag
        (_rec("DELETE_DOC", ticket=10, body={"note": "x"}),),                 # no isDelete key
        (_delete(10, flag=True), _delete(10, flag=False)),                    # tie, no client
        (_delete(10, client="c0", flag=True),
         _delete(10, client="c0", flag=False)),                               # one client, two answers
    ],
    ids=[
        "no-ticket", "string-ticket", "bool-ticket", "fractional-ticket",
        "string-flag", "int-flag", "null-flag", "missing-flag",
        "tie-no-client", "same-client-conflict",
    ],
)
def test_an_unsettled_document_state_keeps_the_whole_document(markers):
    """Neither delete nor revive: the document stays **whole** and says so.

    The last assertion is the load-bearing one — the document also carries a
    duplicate id, and an unsettled document must **not** have its elements
    adjudicated: a partial repair presented as a complete conclusion is exactly
    what the ruling forbids.
    """
    stats = ParseStats()
    documents = split_documents("\n".join((
        _head(),
        _rec("ATTR", ticket=1, id="a1", body={"Value": "R_OLD"}),
        _rec("ATTR", ticket=5, id="a1", body={"Value": "R_NEW"}),
        *markers,
    )), stats, consistent=True)

    (document,) = documents
    assert document.deleted is False
    assert stats.deleted_documents == 0
    assert stats.consistency_unresolved == 1
    assert stats.consistency_duplicate_groups == 0, "no content adjudication on an unsettled document"
    assert [record.body["Value"] for record in document.records if record.type == "ATTR"] == [
        "R_OLD", "R_NEW",
    ], "both versions stay: the question is open, so nothing was decided"


def test_a_document_without_a_marker_is_returned_as_the_same_object():
    document = Document(
        doc_type="PCB", uuid="u1", edit_version=None,
        records=[
            EpruRecord(line_no=0, type="DOCHEAD", ticket=0),
            EpruRecord(line_no=1, type="ATTR", ticket=3, id="a1", body={"Value": "R1"}),
        ],
    )
    assert resolve_document(document) is document


# --------------------------------------------------------------------------
# the model consumers: pages, parts, findings, and an empty board
# --------------------------------------------------------------------------


def _two_pages_with_a_repeat() -> list[str]:
    """p1 holds R1 and C1; p2 holds R2 **and a second R1** (a cross-page repeat)."""
    return [
        _head("SCH_PAGE", uuid="p1"),
        _sch_part("c1", 10, x=0.0, y=0.0),
        _attr("a11", "c1", "Designator", "R1", ticket=11),
        _attr("a12", "c1", "Value", "10k", ticket=12),
        _sch_part("c2", 20, x=50.0, y=0.0),
        _attr("a21", "c2", "Designator", "C1", ticket=21),
        _head("SCH_PAGE", uuid="p2"),
        _sch_part("c3", 30, x=100.0, y=0.0),
        _attr("a31", "c3", "Designator", "R2", ticket=31),
        _sch_part("c4", 40, x=150.0, y=0.0),
        _attr("a41", "c4", "Designator", "R1", ticket=41),
        _delete(50),
    ]


def test_a_deleted_page_takes_its_uuid_parts_and_duplicate_finding_with_it(tmp_path):
    """One page retired, the board's other page untouched, the repeat gone."""
    from boardwise.rules.connectivity import DuplicateDesignators

    path = _epro2(tmp_path, _two_pages_with_a_repeat())
    stats = ParseStats()

    project = build_project_model(path, parse_stats=stats)

    (board,) = project.boards
    assert board.board.page_uuids == ("p1",), "the deleted page left the page list"
    assert sorted(board.components) == ["C1", "R1"], "p1's own parts are all still there"
    assert board.cross_page_designators == {}, (
        "R1 was repeated only across the deleted page, so the repeat is gone too"
    )
    assert DuplicateDesignators().check(board) == []
    assert stats.deleted_documents == 1, "exactly one document, counted once"


def test_collect_page_layout_does_not_draw_the_deleted_page(tmp_path):
    """The drawing line reads the same view, so it cannot draw a retired page."""
    path = _epro2(tmp_path, _two_pages_with_a_repeat())

    parts = collect_page_layout(path).parts

    assert [(part.designator, part.x) for part in parts] == [("R1", 0.0), ("C1", 50.0)], (
        "p1's two parts at p1's own coordinates; p2's R2/R1 are not on the sheet"
    )


def test_a_board_whose_only_page_was_deleted_keeps_its_identity(tmp_path):
    """An empty board is not a deleted board — and not a list with no board.

    The ruling (§3.6) is explicit: when every page is gone the ``BoardModel``
    stays, with an empty ``page_uuids``, and no page is guessed into it. The
    existing empty-board disclosure (``boardsEmpty``, #30 ⑥) is what says the
    board now holds nothing.
    """
    path = _epro2(tmp_path, [
        _head("SCH_PAGE", uuid="p1"),
        _sch_part("c1", 10),
        _attr("a11", "c1", "Designator", "R1", ticket=11),
        _delete(20),
    ])
    stats = ParseStats()

    project = build_project_model(path, parse_stats=stats)

    (board,) = project.boards
    assert board.board.page_uuids == ()
    assert board.components == {} and board.nets == {}
    assert project.board_titles() == ["Board1"], "the container's own identity survives"
    assert stats.deleted_documents == 1


def test_the_pcb_document_goes_and_comes_back_with_isdelete_false():
    """The board consumer, both directions, on the public text entry.

    ``true`` leaves no placement at all (the document is not in the model), and
    the *same* stream with ``false`` restores the placement — which is what makes
    this a revival rather than a parse difference.
    """
    lines = [
        _head("PCB", uuid="pcb1"),
        _board_part("c1", 100, x=1000.0, y=-500.0),
        _attr("a1", "c1", "Designator", "R2", ticket=20),
        _delete(90),
    ]

    deleted = parse_epru_text("\n".join(lines))
    assert deleted.components == []
    assert deleted.stats.deleted_documents == 1

    revived = parse_epru_text("\n".join(lines[:-1] + [_delete(90, flag=False)]))
    (component,) = revived.components
    assert (component.designator, component.x, component.y) == ("R2", 1000.0, -500.0)
    assert revived.stats.deleted_documents == 0


def test_a_deleted_document_is_not_adjudicated_so_nothing_is_lost_from_it(tmp_path):
    """A deleted document's duplicate ids are not counted as settled groups.

    There is no model view for them to be duplicated *in* — the document is gone,
    so ``consistency_duplicate_groups`` (a count of disagreements a reader had to
    settle) must not grow, and ``deleted_documents`` is the only number that
    moved. Both halves are asserted here because "the counter is not raised" is
    trivially true if the document were never read: the live document's own
    duplicate *is* settled and counted, in the same pass.
    """
    path = _epro2(tmp_path, [
        _head("PCB", uuid="live"),
        _board_part("c1", 10),
        _attr("a1", "c1", "Designator", "R2", ticket=20),
        _attr("a1", "c1", "Designator", "R1", ticket=21),
        _head("PCB", uuid="gone"),
        _board_part("c2", 30),
        _attr("a2", "c2", "Designator", "R3", ticket=40),
        _attr("a2", "c2", "Designator", "R4", ticket=41),
        _delete(99),
    ])
    from boardwise.parsers.epru import load_epro2_source

    source = load_epro2_source(path)

    assert [document.uuid for document in source.documents] == ["live"]
    assert source.stats.deleted_documents == 1
    assert source.stats.consistency_duplicate_groups == 1, (
        "the live document's duplicate was settled; the deleted one's never was"
    )


# --------------------------------------------------------------------------
# coverage: a normal deletion is disclosed, an unsettled one gates
# --------------------------------------------------------------------------


def _coverage_for(stats: ParseStats) -> dict:
    """``_coverage_section`` over a reading that did produce a model."""
    from boardwise.cli import _coverage_section
    from boardwise.core.model import Component, DesignModel, Net, Pin

    model = DesignModel()
    model.components["U1"] = Component(uid="u1", designator="U1", pins=[Pin("1", "VIN", "VCC")])
    model.nets = {"VCC": Net("VCC", [("U1", "1")])}
    return _coverage_section(
        model=model, board=None, attempts=[], parse_stats=stats, rules_errored=[],
    )


def test_a_normal_deletion_is_disclosed_and_gates_nothing(tmp_path):
    """Two documents, one deleted: the coverage section says so and moves nothing.

    ``deletedDocuments`` is a *reading*, not a gate — the document is gone
    because the file deleted it, so no reading is short. It must not join
    ``recordsDropped`` (nothing was lost) and must not set ``parseIncomplete``
    (nothing failed to parse), and it adds no ``verdictWhy`` clause.
    """
    from boardwise.cli import _coverage_reasons

    path = _epro2(tmp_path, [
        _head("PCB", uuid="live"),
        _board_part("c1", 10),
        _attr("a1", "c1", "Designator", "R2", ticket=20),
        _head("PCB", uuid="gone"),
        _board_part("c2", 30),
        _attr("a2", "c2", "Designator", "R3", ticket=40),
        _delete(99),
    ])
    from boardwise.parsers.epru import load_epro2_source

    stats = load_epro2_source(path).stats

    assert stats.deleted_documents == 1
    coverage = _coverage_for(stats)

    assert coverage["deletedDocuments"] == 1
    assert coverage["recordsDropped"] == 0, "a deleted document was never a lost record"
    assert coverage["parseIncomplete"] is False
    assert coverage["modelEmpty"] is False
    assert _coverage_reasons(coverage) == [], "no new finding, clause, severity or verdict move"


def test_an_unsettled_document_state_goes_through_parse_incomplete():
    """The other direction: an anomaly is not this field, it is the 038U1 gate."""
    from boardwise.cli import _coverage_reasons

    stats = ParseStats()
    split_documents("\n".join((
        _head(), _rec("ATTR", ticket=1, id="a1", body={"Value": "R1"}),
        _delete(10, flag="true"),
    )), stats, consistent=True)

    coverage = _coverage_for(stats)

    assert "deletedDocuments" not in coverage, (
        "nothing was deleted, so nothing is disclosed as deleted — absent, not 0"
    )
    assert coverage["parseIncomplete"] is True
    assert coverage["consistencyUnresolved"] == 1
    assert len(_coverage_reasons(coverage)) == 1


# --------------------------------------------------------------------------
# the two archived deletions (the accepted delta, measured)
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(ARCHIVED_DELETIONS), ids=sorted(ARCHIVED_DELETIONS))
def test_the_archived_deletion_retires_exactly_one_page(name):
    """The two real deletions, read from the read-only fixtures.

    Both files carry one ``DELETE_DOC`` on an empty ``SCH_PAGE``, so exactly one
    document leaves per file and the board loses exactly that page. This is the
    delta the ruling accepted; every other reading of these files is pinned by
    ``test_040b_boards`` / ``test_040_page_scope`` and may not move.
    """
    title, page_uuid = ARCHIVED_DELETIONS[name]
    path = FIXTURES / name
    stats = ParseStats()

    project = build_project_model(path, parse_stats=stats)

    board = next(b for b in project.boards if b.board.title == title)
    assert page_uuid not in board.board.page_uuids
    assert stats.deleted_documents == 1
    assert stats.consistency_unresolved == 0, "the markers are well formed, so nothing is open"
    assert "DELETE_DOC" not in stats.unknown_types
    # The deleted page was empty (no part, no wire): the board's parts are not
    # what changed here, and `test_040_page_scope`'s signatures keep proving it.
    assert board.components, "the board still reads its own pages"
