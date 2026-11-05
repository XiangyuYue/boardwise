"""038U1 — the pure record-consistency view over one document's records.

The official format settles how two versions of **one element id** coexist in a
record stream: the comparison key is "document + normalised id" (``type`` is not
part of it), the higher ``ticket`` wins, and a ticket tie goes to the larger
source ``client``. An empty body under the winning ticket is an *element*
tombstone: it deletes that id's live versions but stays in the stream as an
ordering boundary. Anything the rule cannot settle — a missing or non-integer
ticket, a top-ticket tie with no client, a same-client tie whose payloads
disagree — must stay visibly unresolved rather than being won by stream order.

These tests read only the **view**: `split_documents(consistent=True)` /
`resolve_documents` / `resolve_records`. The second half of the file then reads
the same streams through the **public model entries** that now consume the view
— `build_project_model`, `collect_page_layout`, `parse_epru_text` — because a
view nothing reads is not a fix.

038U2 added whole-document deletion on top of this rule (a winning
`DELETE_DOC`/`isDelete: true` retires a document, `false` revokes it); its own
tests live in `test_038u2_document_tombstones.py`. The two assertions here that
had to move for it say so where they sit — the element rule itself is unchanged.

No real project file carries two versions of one id (measured over all 14
``.epro2`` fixtures: zero duplicate ids, zero cross-type same ids), so the
multi-version streams below are synthesized from hand-written records. The last
test holds the other half of the contract: the 14 archives must come through
the view *bit-identical*, with the new diagnostics at zero.
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
    resolve_documents,
    resolve_records,
    split_documents,
)
from boardwise.parsers.schematic import build_project_model, collect_page_layout

# --------------------------------------------------------------------------
# record / stream synthesis
# --------------------------------------------------------------------------


def _rec(
    type_: str,
    *,
    ticket=None,
    id=None,
    client=None,
    first_ticket=None,
    body=None,
) -> str:
    """One record line. ``body=None`` writes the empty-body shape ``{env}|||``."""
    envelope: dict = {"type": type_}
    if ticket is not None:
        envelope["ticket"] = ticket
    if id is not None:
        envelope["id"] = id
    if client is not None:
        envelope["client"] = client
    if first_ticket is not None:
        envelope["firstTicket"] = first_ticket
    text = json.dumps(envelope)
    return f"{text}|||" if body is None else f"{text}||{json.dumps(body)}|"


def _head(doc_type: str = "PCB", uuid: str = "u1", client=None, ticket: int = 0) -> str:
    body: dict = {"docType": doc_type, "uuid": uuid}
    if client is not None:
        body["client"] = client
    return _rec("DOCHEAD", ticket=ticket, body=body)


def _split(*lines: str, consistent: bool = False):
    stats = ParseStats()
    documents = split_documents("\n".join(lines), stats, consistent=consistent)
    return documents, stats


def _view(*lines: str):
    documents, stats = _split(*lines, consistent=True)
    assert len(documents) == 1, "the synthesized stream is one document"
    return documents[0].records, stats


def _shape(records: list[EpruRecord]) -> list[tuple]:
    return [(r.type, r.ticket, r.id, r.body) for r in records]


# --------------------------------------------------------------------------
# the rule the format states
# --------------------------------------------------------------------------


def test_a_higher_ticket_wins_even_when_it_arrives_first():
    """The 038U probe: ticket 20 ahead of ticket 10 must not lose to stream order."""
    records, stats = _view(
        _head(),
        _rec("ATTR", ticket=20, id="a1", body={"Value": "R_NEW"}),
        _rec("ATTR", ticket=10, id="a1", body={"Value": "R_OLD"}),
    )

    assert _shape(records) == [
        ("DOCHEAD", 0, None, {"docType": "PCB", "uuid": "u1"}),
        ("ATTR", 20, "a1", {"Value": "R_NEW"}),
    ]
    assert (stats.consistency_duplicate_groups, stats.consistency_unresolved) == (1, 0)


def test_type_is_not_part_of_the_key():
    """A TEXT and an ATTR under one id are one chain: the newer TEXT wins."""
    records, _ = _view(
        _head(),
        _rec("ATTR", ticket=10, id="x", body={"Value": "R_STALE"}),
        _rec("TEXT", ticket=20, id="x", body={"text": "R_LIVE"}),
    )

    assert [(r.type, r.id, r.body) for r in records[1:]] == [
        ("TEXT", "x", {"text": "R_LIVE"}),
    ]


@pytest.mark.parametrize("sequence", [("b", "a"), ("a", "b")])
def test_a_ticket_tie_goes_to_the_larger_client_in_both_arrival_orders(sequence):
    """Official 3.0: same ticket -> larger client wins, never "the later one"."""
    rows = [
        _rec("ATTR", ticket=10, id="a1", client=client,
             body={"Value": f"R_CLIENT_{client.upper()}"})
        for client in sequence
    ]
    documents, stats = _split(_head(), *rows, consistent=True)
    kept = documents[0].records[1:]

    assert len(kept) == 1, sequence
    assert kept[0].body == {"Value": "R_CLIENT_B"}, sequence
    assert stats.consistency_duplicate_groups == 1


def test_a_record_without_a_client_falls_back_to_the_document_client():
    """``record.client`` if it has one, else the ``DOCHEAD`` client it arrived under."""
    records, stats = _view(
        _head(client="b0"),
        _rec("ATTR", ticket=10, id="a1", client="a0", body={"Value": "R_EXPLICIT_A"}),
        _rec("ATTR", ticket=10, id="a1", body={"Value": "R_INHERITS_B"}),
    )

    assert [r.body for r in records[1:]] == [{"Value": "R_INHERITS_B"}]
    assert stats.consistency_duplicate_groups == 1

    records, stats = _view(
        _head(client="a0"),
        _rec("ATTR", ticket=10, id="a1", client="b0", body={"Value": "R_EXPLICIT_B"}),
        _rec("ATTR", ticket=10, id="a1", body={"Value": "R_INHERITS_A"}),
    )

    assert [r.body for r in records[1:]] == [{"Value": "R_EXPLICIT_B"}]
    assert stats.consistency_duplicate_groups == 1


def test_a_top_ticket_tie_with_no_client_anywhere_is_unresolved():
    records, stats = _view(
        _head(),
        _rec("ATTR", ticket=10, id="a1", body={"Value": "R_A"}),
        _rec("ATTR", ticket=10, id="a1", body={"Value": "R_B"}),
    )

    assert [r.body for r in records[1:]] == [{"Value": "R_A"}, {"Value": "R_B"}]
    assert (stats.consistency_duplicate_groups, stats.consistency_unresolved) == (0, 1)


def test_one_client_missing_at_the_top_tie_is_unresolved():
    """A half-known tie is not a tie the format's rule can order."""
    records, stats = _view(
        _head(),
        _rec("ATTR", ticket=10, id="a1", client="b0", body={"Value": "R_B"}),
        _rec("ATTR", ticket=10, id="a1", body={"Value": "R_NONE"}),
    )

    assert len(records) == 3, "both versions stay, no client invents a winner"
    assert stats.consistency_unresolved == 1


def test_identical_copies_under_one_client_collapse_to_the_first():
    records, stats = _view(
        _head(client="c0"),
        _rec("ATTR", ticket=10, id="a1", body={"Value": "R_SAME"}, first_ticket=4),
        _rec("ATTR", ticket=10, id="a1", body={"Value": "R_SAME"}, first_ticket=4),
    )

    assert _shape(records)[1:] == [("ATTR", 10, "a1", {"Value": "R_SAME"})]
    assert records[1].line_no == 1, "the surviving copy keeps its own line_no"
    assert (stats.consistency_duplicate_groups, stats.consistency_unresolved) == (1, 0)


def test_a_same_client_tie_with_different_payloads_is_unresolved_not_last_wins():
    records, stats = _view(
        _head(client="c0"),
        _rec("ATTR", ticket=10, id="a1", body={"Value": "R_FIRST"}),
        _rec("ATTR", ticket=10, id="a1", body={"Value": "R_SECOND"}),
    )

    assert [r.id for r in records] == [None, "a1", "a1"]
    assert [r.body for r in records[1:]] == [{"Value": "R_FIRST"}, {"Value": "R_SECOND"}]
    assert (stats.consistency_duplicate_groups, stats.consistency_unresolved) == (0, 1)


@pytest.mark.parametrize(
    "bad_ticket",
    [None, "10", True, 3.5, float("nan"), [10]],
    ids=["missing", "numeric-string", "bool", "fractional", "nan", "list"],
)
def test_a_group_with_any_unusable_ticket_is_unresolved(bad_ticket):
    """``True`` is an ``int`` in Python but not a ticket; a string is not either."""
    records, stats = _view(
        _head(),
        _rec("ATTR", ticket=5, id="a1", body={"Value": "R_OK"}),
        _rec("ATTR", ticket=bad_ticket, id="a1", body={"Value": "R_BAD"}),
    )

    assert [r.id for r in records] == [None, "a1", "a1"]
    assert (stats.consistency_duplicate_groups, stats.consistency_unresolved) == (0, 1)


# --------------------------------------------------------------------------
# tombstones (empty body = element delete)
# --------------------------------------------------------------------------


def test_a_winning_tombstone_deletes_the_live_versions_and_keeps_its_slot():
    records, stats = _view(
        _head(),
        _rec("ATTR", ticket=10, id="a1", body={"Value": "R_STALE"}),
        _rec("ATTR", ticket=20, id="a1"),
        _rec("COMPONENT", ticket=1, id="c1", body={"designator": "R1"}),
    )

    assert [r.type for r in records] == ["DOCHEAD", "ATTR", "COMPONENT"]
    assert records[1].body is None and records[1].ticket == 20
    assert records[1].line_no == 2, "the winner keeps its own line_no for provenance"
    assert [r.line_no for r in records] == [0, 2, 3]
    assert stats.empty_body_records == 1, "the raw count is still the raw count"
    assert (stats.consistency_duplicate_groups, stats.consistency_unresolved) == (1, 0)


def test_a_losing_tombstone_never_deletes_a_newer_live_version():
    records, stats = _view(
        _head(),
        _rec("ATTR", ticket=10, id="a1"),
        _rec("ATTR", ticket=20, id="a1", body={"Value": "R_LIVE"}),
    )

    assert [r.body for r in records[1:]] == [{"Value": "R_LIVE"}]
    assert stats.empty_body_records == 1
    assert stats.consistency_duplicate_groups == 1


def test_a_lone_tombstone_comes_back_untouched():
    """The structural zero-drift guarantee: one version means the same objects."""
    documents, stats = _split(_head(), _rec("ATTR", ticket=7, id="a1"), consistent=True)
    document = documents[0]
    raw, _ = _split(_head(), _rec("ATTR", ticket=7, id="a1"))

    assert len(document.records) == 2 and document.records[1].body is None
    assert [r.line_no for r in document.records] == [0, 1]
    assert all(a == b for a, b in zip(document.records, raw[0].records))
    assert (stats.consistency_duplicate_groups, stats.consistency_unresolved) == (0, 0)


def test_a_document_without_duplicates_is_returned_as_the_same_object():
    document = Document(
        doc_type="PCB",
        uuid="u1",
        edit_version=None,
        records=[
            EpruRecord(line_no=0, type="DOCHEAD", ticket=0),
            EpruRecord(line_no=1, type="ATTR", ticket=3, id="a1", body={"Value": "R1"}),
            EpruRecord(line_no=2, type="ATTR", ticket=4, id="a2", body=None),
        ],
    )

    assert resolve_document(document) is document


# --------------------------------------------------------------------------
# what must never enter the competition
# --------------------------------------------------------------------------


def test_document_level_records_without_an_id_are_never_grouped():
    """``DELETE_DOC`` markers never join **element** competition, even together.

    Both markers here say ``isDelete: false``, so 038U2's document-state rule
    keeps the document and both rows come back verbatim. What the test pins is
    unchanged from 038U1: the markers are not element versions, so neither is
    dropped in favour of the other and neither moves — only their *document*
    answer is adjudicated, and that answer is not an element duplicate group.
    """
    records, stats = _view(
        _head(),
        _rec("DELETE_DOC", ticket=10, body={"isDelete": False}),
        _rec("DELETE_DOC", ticket=5, body={"isDelete": False}),
        _rec("META", ticket=3, body={"schematic": "s1"}),
        _rec("META", ticket=1, body={"schematic": "s0"}),
    )

    assert _shape(records) == [
        ("DOCHEAD", 0, None, {"docType": "PCB", "uuid": "u1"}),
        ("DELETE_DOC", 10, None, {"isDelete": False}),
        ("DELETE_DOC", 5, None, {"isDelete": False}),
        ("META", 3, None, {"schematic": "s1"}),
        ("META", 1, None, {"schematic": "s0"}),
    ]
    # 038U2: the two markers are one *document-state* question, settled by
    # ticket — and it is **not** counted as an element duplicate group, because a
    # ``DELETE_DOC`` marker has no element id (038U1 scopes that counter to
    # element-id groups). Neither marker is removed from the record list: only a
    # deleted document's records leave the view at all.
    assert (stats.consistency_duplicate_groups, stats.consistency_unresolved) == (0, 0)
    assert stats.deleted_documents == 0, "false is a revocation: nothing was deleted"
    assert stats.total_records == 5


def test_a_json_array_id_compares_as_canonical_json():
    records, stats = _view(
        _head(),
        _rec("LAYER", ticket=1, id='["LAYER", 1]', body={"layerName": "TOP"}),
        _rec("LAYER", ticket=9, id='["LAYER",1]', body={"layerName": "BOTTOM"}),
    )

    assert [r.body for r in records[1:]] == [{"layerName": "BOTTOM"}]
    assert stats.consistency_duplicate_groups == 1


def test_a_json_array_id_keeps_its_element_types():
    """``1`` and ``"1"`` are different composite keys — no coercion, no trimming."""
    records, stats = _view(
        _head(),
        _rec("LAYER", ticket=1, id='["LAYER",1]', body={"layerName": "TOP"}),
        _rec("LAYER", ticket=2, id='["LAYER","1"]', body={"layerName": "BOTTOM"}),
    )

    assert [r.id for r in records[1:]] == ['["LAYER",1]', '["LAYER","1"]']
    assert (stats.consistency_duplicate_groups, stats.consistency_unresolved) == (0, 0)


def test_a_plain_id_is_compared_exactly():
    records, stats = _view(
        _head(),
        _rec("ATTR", ticket=1, id="a1", body={"Value": "R_A"}),
        _rec("ATTR", ticket=2, id=" a1", body={"Value": "R_SPACE"}),
        _rec("ATTR", ticket=3, id="A1", body={"Value": "R_CASE"}),
    )

    assert [r.id for r in records[1:]] == ["a1", " a1", "A1"]
    assert stats.consistency_duplicate_groups == 0


def test_an_empty_id_is_no_id_so_unrelated_records_never_compete():
    """``""`` is what a record writes when it declares no id — not a shared key.

    Grouping on it would merge two different graphics that both omitted their id
    and drop one of them as "the older version", which is a delete the file never
    stated. They pass through verbatim and count nothing.
    """
    records, stats = _view(
        _head(),
        _rec("LINE", ticket=1, id="", body={"points": [0, 0, 10, 0]}),
        _rec("RECT", ticket=9, id="", body={"x": 40, "y": 20}),
    )

    assert [(r.type, r.ticket, r.id) for r in records[1:]] == [
        ("LINE", 1, ""), ("RECT", 9, ""),
    ]
    assert (stats.consistency_duplicate_groups, stats.consistency_unresolved) == (0, 0)

    # A non-empty id is unchanged: it still competes and still settles.
    records, stats = _view(
        _head(),
        _rec("ATTR", ticket=1, id="a1", body={"Value": "R_OLD"}),
        _rec("ATTR", ticket=9, id="a1", body={"Value": "R_NEW"}),
    )

    assert [r.body for r in records[1:]] == [{"Value": "R_NEW"}]
    assert (stats.consistency_duplicate_groups, stats.consistency_unresolved) == (1, 0)


def test_a_non_string_id_compares_as_canonical_json():
    """Synthesised only — no real export writes a list id — but the rule holds."""
    records, stats = _view(
        _head(),
        _rec("LAYER", ticket=1, id=[2, "A"], body={"layerName": "TOP"}),
        _rec("LAYER", ticket=9, id=[2, "A"], body={"layerName": "BOTTOM"}),
        _rec("LAYER", ticket=1, id="[2,\"A\"]", body={"layerName": "TOP_STRING"}),
    )

    assert [r.body for r in records[1:]] == [{"layerName": "BOTTOM"}]
    assert stats.consistency_duplicate_groups == 1, "the list and its string form are one key"


def test_two_documents_never_compete_for_one_id():
    documents, stats = _split(
        _head(uuid="u1"),
        _rec("ATTR", ticket=10, id="a1", body={"Value": "R_PAGE1"}),
        _head(uuid="u2"),
        _rec("ATTR", ticket=10, id="a1", body={"Value": "R_PAGE2"}),
        consistent=True,
    )

    assert [d.uuid for d in documents] == ["u1", "u2"]
    assert [d.records[1].body for d in documents] == [
        {"Value": "R_PAGE1"},
        {"Value": "R_PAGE2"},
    ]
    assert (stats.consistency_duplicate_groups, stats.consistency_unresolved) == (0, 0)


# --------------------------------------------------------------------------
# ordering, provenance, and the raw/consistent split
# --------------------------------------------------------------------------


def test_the_winner_takes_the_first_slot_of_its_id():
    records, _ = _view(
        _head(),
        _rec("ATTR", ticket=10, id="a1", body={"Value": "R_OLD"}),
        _rec("ATTR", ticket=20, id="a2", body={"Value": "R_OTHER"}),
        _rec("ATTR", ticket=30, id="a1", body={"Value": "R_NEW"}),
        _rec("TEXT", ticket=1, id="t1", body={"text": "label"}),
    )

    assert [(r.id, r.ticket) for r in records[1:]] == [
        ("a1", 30), ("a2", 20), ("t1", 1),
    ]
    assert [r.line_no for r in records] == [0, 3, 2, 4]


def test_the_source_client_is_decoded_where_the_format_writes_it():
    documents, _ = _split(
        _head(client="doc-client"),
        _rec("ATTR", ticket=1, id="a1", client="rec-client", body={"Value": "R1"}),
    )
    document = documents[0]

    assert document.client == "doc-client"
    assert document.records[1].client == "rec-client"
    assert documents[0].records[0].client is None, "a DOCHEAD envelope carries none"


def test_consistent_is_opt_in_and_the_raw_view_keeps_every_version():
    lines = (
        _head(),
        _rec("ATTR", ticket=10, id="a1", body={"Value": "R_OLD"}),
        _rec("ATTR", ticket=20, id="a1", body={"Value": "R_NEW"}),
        _rec("ATTR", ticket=5, id="a1"),
    )

    raw_documents, raw_stats = _split(*lines)
    explicit_raw, explicit_stats = _split(*lines, consistent=False)
    documents, stats = _split(*lines, consistent=True)

    assert [r.ticket for r in raw_documents[0].records[1:]] == [10, 20, 5]
    assert [r.ticket for r in explicit_raw[0].records[1:]] == [10, 20, 5]
    assert [r.ticket for r in documents[0].records[1:]] == [20]

    # The raw frame counters are the same in both runs: the view only decides
    # what a reader gets, it never re-counts the file.
    for name in ("total_records", "empty_body_records", "malformed_records"):
        assert getattr(raw_stats, name) == getattr(stats, name), name
    assert raw_stats.records_by_type == stats.records_by_type
    assert stats.total_records == 4 and stats.empty_body_records == 1
    assert (raw_stats.consistency_duplicate_groups, raw_stats.consistency_unresolved) == (0, 0)
    assert (stats.consistency_duplicate_groups, stats.consistency_unresolved) == (1, 0)
    assert explicit_stats.consistency_duplicate_groups == 0


def test_resolve_documents_counts_each_group_once():
    documents = [
        Document(
            doc_type="PCB",
            uuid="u1",
            edit_version=None,
            records=[
                EpruRecord(line_no=0, type="ATTR", ticket=1, id="a1", body={"Value": "A"}),
                EpruRecord(line_no=1, type="ATTR", ticket=2, id="a1", body={"Value": "B"}),
                EpruRecord(line_no=2, type="ATTR", ticket=3, id="a2", body={"Value": "C"}),
                EpruRecord(line_no=3, type="ATTR", ticket=3, id="a2", body={"Value": "D"}),
            ],
        ),
        Document(
            doc_type="PCB",
            uuid="u2",
            edit_version=None,
            records=[
                EpruRecord(line_no=4, type="ATTR", ticket=1, id="a1", body={"Value": "E"}),
            ],
        ),
    ]
    stats = ParseStats()

    resolved = resolve_documents(documents, stats)

    assert [len(d.records) for d in resolved] == [3, 1], "a1 settled, a2 left whole"
    assert [r.body for r in resolved[0].records] == [
        {"Value": "B"}, {"Value": "C"}, {"Value": "D"},
    ]
    assert (stats.consistency_duplicate_groups, stats.consistency_unresolved) == (1, 1)


def test_the_new_diagnostics_only_append_to_the_stats_view():
    stats = ParseStats()
    stats.total_records = 3
    payload = stats.as_dict()

    assert payload["consistency_duplicate_groups"] == 0
    assert payload["consistency_unresolved"] == 0
    assert payload["deleted_documents"] == 0, "038U2 appends its counter last"
    assert list(payload)[-3:] == [
        "consistency_duplicate_groups", "consistency_unresolved", "deleted_documents",
    ], "old keys keep their order, the new ones are appended"
    assert payload["total_records"] == 3
    for name in ("empty_body_records", "malformed_records", "records_by_type",
                 "unknown_types", "conflicting_library_documents"):
        assert name in payload


# --------------------------------------------------------------------------
# the archived fixtures must not move
# --------------------------------------------------------------------------

FIXTURES = sorted(Path(__file__).parent.joinpath("fixtures").glob("*.epro2"))


def test_the_archive_sweep_covers_all_fourteen_fixtures():
    assert len(FIXTURES) == 14, "the zero-drift claim is measured on all of them"


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_no_archived_fixture_changes_under_the_consistency_view(path):
    text, _meta = load_epru_text(path)

    raw_stats = ParseStats()
    raw = split_documents(text, raw_stats)
    stats = ParseStats()
    consistent = split_documents(text, stats, consistent=True)

    assert [d.doc_type for d in consistent] == [d.doc_type for d in raw]
    assert [d.uuid for d in consistent] == [d.uuid for d in raw]
    assert [d.client for d in consistent] == [d.client for d in raw]
    for before, after in zip(raw, consistent):
        assert after.records == before.records, "records, order and line_no all identical"

    assert stats.total_records == raw_stats.total_records
    assert stats.empty_body_records == raw_stats.empty_body_records
    assert stats.malformed_records == raw_stats.malformed_records
    assert stats.records_by_type == raw_stats.records_by_type
    assert stats.unknown_types == raw_stats.unknown_types
    assert stats.document_types == raw_stats.document_types
    assert (stats.consistency_duplicate_groups, stats.consistency_unresolved) == (0, 0)


# --------------------------------------------------------------------------
# the public consumers read the view (038U1 integration)
# --------------------------------------------------------------------------
#
# A view nothing reads is not a fix, so these tests read **only** public model
# entries — ``build_project_model``, ``collect_page_layout``, ``parse_epru_text``
# and ``resolve_records`` — over a real one-stream ``.epro2`` written into
# ``tmp_path``. Nothing here calls ``_split_page`` or a comparison helper.


def _epro2(tmp_path: Path, lines: list[str], name: str = "synth.epro2") -> Path:
    """A one-stream ``.epro2`` archive holding ``lines``."""
    path = tmp_path / name
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("synth.epru", "\n".join(lines) + "\n")
        archive.writestr("project2.json", json.dumps({"title": "synthetic"}))
    return path


def _part(uid: str, ticket: int, *, x: float = 0.0, y: float = 0.0, z_index=5) -> str:
    """A schematic ``COMPONENT``: a placement, so it carries a ``zIndex``."""
    return _rec("COMPONENT", ticket=ticket, id=uid, body={
        "partId": "R0402.1", "x": x, "y": y, "rotation": 0, "isMirror": False,
        "zIndex": z_index,
    })


def _board_part(uid: str, ticket: int, *, x: float = 0.0, y: float = 0.0) -> str:
    """A PCB ``COMPONENT``: the board document's own field names."""
    return _rec("COMPONENT", ticket=ticket, id=uid, body={
        "x": x, "y": y, "angle": 0, "layerId": 1,
    })


def _attr(uid: str, parent: str, key: str, value: str, *, ticket: int = 1,
          client=None) -> str:
    """One ``ATTR``, parented the way both documents parent them."""
    return _rec("ATTR", ticket=ticket, id=uid, client=client,
                body={"parentId": parent, "key": key, "value": value})


def _page(*lines: str) -> list[str]:
    return [_head("SCH_PAGE", uuid="p1"), *lines]


# --- the schematic model --------------------------------------------------


def test_the_schematic_model_reads_the_higher_ticket_designator(tmp_path):
    """The 038U probe, at the model entry: ``R_NEW`` arrives first and wins.

    ``_split_page`` files an ATTR by the id its ``parentId`` names and lets the
    **later** copy overwrite the value, so the raw stream gave this component the
    name of its older version. The view decides first, and there is one copy to
    read by the time the grouper runs.
    """
    path = _epro2(tmp_path, _page(
        _part("c1", 100, x=10.0, y=-20.0),
        _attr("a1", "c1", "Designator", "R_NEW", ticket=20),
        _attr("a1", "c1", "Designator", "R_OLD", ticket=10),
        _attr("a2", "c1", "Value", "10k", ticket=21),
    ))

    stats = ParseStats()
    project = build_project_model(path, parse_stats=stats)

    assert {name: part.value for name, part in project.boards[0].components.items()} == {
        "R_NEW": "10k",
    }
    # One group, counted once: the model's own second read of the stream (the
    # footprint-title pass) resolves without a counter, so the diagnostic is not
    # doubled by how many readers the model happens to have.
    assert (stats.consistency_duplicate_groups, stats.consistency_unresolved) == (1, 0)


def test_a_winning_tombstone_stops_the_schematic_reading_an_old_designator(tmp_path):
    """An empty body under the winning ticket deletes the id's live versions.

    The part is still drawn — a ``COMPONENT`` is not what was deleted — but its
    designator is gone, so it leaves the model and is counted as such instead of
    keeping a name the stream had already retired.
    """
    path = _epro2(tmp_path, _page(
        _part("c1", 100, x=10.0, y=-20.0),
        _attr("a1", "c1", "Designator", "R1", ticket=10),
        _rec("ATTR", ticket=20, id="a1"),
    ))
    stats = ParseStats()

    project = build_project_model(path, parse_stats=stats)

    assert project.boards[0].components == {}, "the retired designator names nothing"
    assert stats.instances_without_designator == 1
    assert stats.empty_body_records == 1, "the raw count is still the raw count"


def test_one_component_id_is_one_part_not_two_with_one_name(tmp_path):
    """Two versions of a ``COMPONENT`` are one placement, at the winner's position.

    Read raw, the second ``COMPONENT`` is a second instance: the page would show
    two parts both named ``R1`` — a fake duplicate-designator finding whose one
    real cause is an id the file had already superseded. ``collect_page_layout``
    is the reader the drawing line uses, so it is the one asserted.
    """
    path = _epro2(tmp_path, _page(
        _part("c1", 10, x=10.0, y=-10.0),
        _attr("d1", "c1", "Designator", "R1", ticket=11),
        _part("c1", 30, x=90.0, y=-90.0),
        _attr("d2", "c1", "Designator", "R1", ticket=31),
        _attr("v1", "c1", "Value", "1k", ticket=32),
    ))

    parts = collect_page_layout(path).parts

    assert [(part.designator, part.x, part.y) for part in parts] == [("R1", 90.0, 90.0)], (
        "one part, at the position of the version that won (stored y=-90 -> canvas 90)"
    )


def test_the_042_parentid_fallback_still_places_attrs_after_the_view(tmp_path):
    """042's adjacency fallback keeps working *through* the view.

    Neither ATTR here names a component (an empty ``parentId`` and one that
    matches nothing), so the block is filed by adjacency exactly as before —
    and the duplicate id inside it is still settled by ticket, which is what
    042's rule alone could not have done.
    """
    path = _epro2(tmp_path, _page(
        _part("c-u3", 1, x=0.0, y=0.0, z_index=7),
        _attr("x1", "", "Designator", "U3", ticket=5),
        _attr("x2", "no-such-record", "Value", "LM358", ticket=9),
        _attr("x2", "no-such-record", "Value", "OPA2340", ticket=3),
    ))

    project = build_project_model(path)

    assert project.boards[0].components["U3"].value == "LM358"


# --- the board model ------------------------------------------------------


def test_the_board_model_reads_the_higher_ticket_designator():
    """The PCB document competes by the same rule, on the same entry as the tests above.

    ``ATTR`` used to be applied in stream order (last copy wins), so the older
    ``R1`` would have named this placement.
    """
    board = parse_epru_text("\n".join([
        _head("PCB", uuid="pcb1"),
        _board_part("c1", 100, x=1000.0, y=-500.0),
        _attr("a1", "c1", "Designator", "R2", ticket=20),
        _attr("a1", "c1", "Designator", "R1", ticket=10),
        _attr("a2", "c1", "Value", "10k", ticket=21),
    ]))

    (component,) = board.components
    assert (component.designator, component.value) == ("R2", "10k")
    assert (board.stats.consistency_duplicate_groups, board.stats.consistency_unresolved) == (1, 0)


def test_a_winning_tombstone_deletes_the_boards_old_value():
    """A tombstone that wins is a delete of the *value*, not of the placement."""
    board = parse_epru_text("\n".join([
        _head("PCB", uuid="pcb1"),
        _board_part("c1", 100, x=1000.0, y=-500.0),
        _attr("a1", "c1", "Value", "10k", ticket=10),
        _rec("ATTR", ticket=20, id="a1"),
    ]))

    (component,) = board.components
    assert component.value is None
    assert component.designator is None
    assert board.stats.empty_body_records == 1


def test_one_component_id_keeps_the_higher_ticket_position():
    """The surviving placement is the winning version's, geometry included."""
    board = parse_epru_text("\n".join([
        _head("PCB", uuid="pcb1"),
        _board_part("c2", 10, x=100.0, y=-100.0),
        _board_part("c2", 30, x=900.0, y=-900.0),
        _attr("a3", "c2", "Designator", "C5", ticket=40),
    ]))

    (component,) = board.components
    assert (component.x, component.y, component.designator) == (900.0, -900.0, "C5")


def test_a_ticket_tie_goes_to_the_larger_client_on_the_board_entry():
    """The official tie-break, accepted at a public entry (not only in the view).

    ``b`` arrives **first** and ``a`` second, so a last-wins reader picks ``a``;
    the rule says ``b``.
    """
    board = parse_epru_text("\n".join([
        _head("PCB", uuid="pcb1"),
        _board_part("c1", 100, x=1000.0, y=-500.0),
        _attr("a1", "c1", "Designator", "R_CLIENT_B", ticket=10, client="b0"),
        _attr("a1", "c1", "Designator", "R_CLIENT_A", ticket=10, client="a0"),
    ]))

    (component,) = board.components
    assert component.designator == "R_CLIENT_B"
    assert board.stats.consistency_duplicate_groups == 1


# --- the flat-record entry ------------------------------------------------


def test_resolve_records_keeps_sch_pages_and_filters_a_deleted_one():
    """Two properties of the flat entry, both outside ``split_documents``' remit.

    ``split_documents`` drops every document type it does not keep, ``SCH_PAGE``
    among them, so the schematic's own reader cannot get its page records from
    it — the flat entry has to cut by ``DOCHEAD`` itself.

    038U2 changed the second half of this test **on purpose**: the page's
    ``DELETE_DOC`` says ``isDelete: true``, so the page is retired and none of
    its rows reach the view any more (the ruling in
    ``tasks/038u2_document_tombstones.md`` §3.2/§3.6 — a deleted page's page
    uuid, parts, nets and findings all leave the model). What did **not** change
    is the raw view: the same stream still carries the page, its duplicate id and
    the marker, and nothing is filtered there.
    """
    text = "\n".join([
        _head("SCH_PAGE", uuid="p1"),
        _rec("ATTR", ticket=20, id="a1", body={"Value": "R_NEW"}),
        _rec("ATTR", ticket=10, id="a1", body={"Value": "R_OLD"}),
        _rec("DELETE_DOC", ticket=30, body={"isDelete": True}),
        _head("SYMBOL", uuid="s1"),
        _rec("ATTR", ticket=5, id="a1", body={"Value": "SYMBOL_A1"}),
    ])

    assert [d.doc_type for d in split_documents(text, ParseStats())] == ["SYMBOL"], (
        "the archive reader keeps SYMBOL, not SCH_PAGE — hence the flat entry"
    )
    raw = list(iter_epru_records(text))
    assert [r.type for r in raw].count("DELETE_DOC") == 1, (
        "the raw frame log keeps the marker: the view decides, the log does not"
    )

    stats = ParseStats()
    resolved = resolve_records(iter_epru_records(text), stats)

    values = [r.body.get("Value") for r in resolved if r.type == "ATTR"]
    assert values == ["SYMBOL_A1"], (
        "the deleted page is gone whole, so its duplicate never had to be "
        "settled — and the same id under another document is a different chain"
    )
    assert [r.type for r in resolved].count("DELETE_DOC") == 0
    assert stats.deleted_documents == 1
    assert stats.consistency_duplicate_groups == 0, (
        "a deleted document's elements are not adjudicated: nothing to settle"
    )

    # The counter-evidence the ruling keeps: ``isDelete: false`` revokes the
    # deletion, and the very same page comes back with both versions settled by
    # ticket and the marker still visible in the stream.
    kept = text.replace('{"isDelete": true}', '{"isDelete": false}')
    stats = ParseStats()
    resolved = resolve_records(iter_epru_records(kept), stats)

    values = [r.body.get("Value") for r in resolved if r.type == "ATTR"]
    assert values == ["R_NEW", "SYMBOL_A1"]
    (marker,) = [r for r in resolved if r.type == "DELETE_DOC"]
    assert marker.body == {"isDelete": False}
    assert stats.deleted_documents == 0
    assert stats.consistency_duplicate_groups == 1


def test_records_before_the_first_head_have_no_document_to_compete_in():
    """A record outside any document is passed through, never grouped.

    Inventing a document for it would let two records that the file put in
    different places compete — the opposite of the "document + id" key.
    """
    text = "\n".join([
        _rec("META", ticket=1, body={"a": 1}),
        _rec("META", ticket=2, id="m1", body={"a": 2}),
        _rec("META", ticket=3, id="m1", body={"a": 3}),
        _head("PCB", uuid="p1"),
        _rec("META", ticket=1, id="m1", body={"a": 4}),
        _rec("META", ticket=9, id="m1", body={"a": 5}),
    ])
    stats = ParseStats()

    resolved = resolve_records(iter_epru_records(text), stats)

    assert [(r.id, (r.body or {}).get("a")) for r in resolved[:3]] == [
        (None, 1), ("m1", 2), ("m1", 3),
    ], "no head yet: verbatim, both copies kept"
    assert resolved[3].type == "DOCHEAD"
    assert [(r.id, (r.body or {}).get("a")) for r in resolved[4:]] == [("m1", 5)]
    assert (stats.consistency_duplicate_groups, stats.consistency_unresolved) == (1, 0)
