"""038I — the `epru-stream-sample` differential contract, Python half.

One case kind, one projection: the input is ``{schema, name, text}`` and both
runners derive the same ``boardwise.epru-stream/1`` document from ``text``. This
file pins the Python side of that document, and pins the two rules the batch
exists for:

* the projection is a **view** built from the existing readers
  (:func:`boardwise.parsers.epru_stream.split_documents` for the counts and the
  document split, :func:`~boardwise.parsers.epru_stream.iter_epru_records` per
  line for what each record decoded to) — never a second parser, so the framing
  rules and the 038F1 line shapes have exactly one implementation;
* it states nothing the other side cannot derive: no body, no unknown-record-type
  drift signal, and no *reason* a line was malformed (Python never classifies it).

The expected projection below is written out twice — here and as
``SAMPLE_EXPECTED`` in ``rust/crates/boardwise-core/tests/epru_stream.rs``. The
two literals are the contract; a change on one side has to change both.

Everything here is synthetic: no real project content, no fixture file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools import differential
from tools.contract_validate import ContractValidationError, assert_valid, load_path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "contracts" / "json" / "epru-stream-sample-v1.schema.json"
KIND = "epru-stream-sample"

#: Ten lines: a dropped document, a kept one, a terminated empty body
#: (``{env}|||``), a truncated line (``{env}``, no separator), a DOCHEAD without
#: its terminator, the V4 EOF shape (``{env}||``) mid-stream *and* at EOF, and a
#: terminated last line with a body.
SAMPLE = "\n".join([
    '{"type":"DOCHEAD","ticket":1}||{"docType":"SCH"}|',
    '{"type":"WIRE","ticket":2}||{"id":7}|',
    '{"type":"DOCHEAD","ticket":3}||{"docType":"PCB"}|',
    '{"type":"PAD","ticket":4}||{"number":"1"}|',
    '{"type":"PAD","ticket":5}|||',
    '{"type":"META","ticket":6}',
    '{"type":"DOCHEAD","ticket":7}||{"docType":"FOOTPRINT"}',
    '{"type":"PAD","ticket":8}||',
    '{"type":"DOCHEAD","ticket":9}||{"docType":"SYMBOL"}|',
    '{"type":"PIN","ticket":10}||',
])

EXPECTED = {
    "schema": "boardwise.epru-stream/1",
    "records": [
        {
            "lineNo": 0, "type": "DOCHEAD", "hasBody": True,
            "emptyBody": False, "malformed": False, "docType": "SCH",
        },
        {
            "lineNo": 1, "type": "WIRE", "hasBody": True,
            "emptyBody": False, "malformed": False,
        },
        {
            "lineNo": 2, "type": "DOCHEAD", "hasBody": True,
            "emptyBody": False, "malformed": False, "docType": "PCB",
            "document": 0,
        },
        {
            "lineNo": 3, "type": "PAD", "hasBody": True,
            "emptyBody": False, "malformed": False, "document": 0,
        },
        {
            "lineNo": 4, "type": "PAD", "hasBody": False,
            "emptyBody": True, "malformed": False, "document": 0,
        },
        {
            "lineNo": 5, "type": "", "hasBody": False,
            "emptyBody": False, "malformed": True,
        },
        {
            "lineNo": 6, "type": "DOCHEAD", "hasBody": True,
            "emptyBody": False, "malformed": False, "docType": "FOOTPRINT",
            "document": 1,
        },
        {
            "lineNo": 7, "type": "PAD", "hasBody": False,
            "emptyBody": True, "malformed": False, "document": 1,
        },
        {
            "lineNo": 8, "type": "DOCHEAD", "hasBody": True,
            "emptyBody": False, "malformed": False, "docType": "SYMBOL",
            "document": 2,
        },
        {
            "lineNo": 9, "type": "PIN", "hasBody": False,
            "emptyBody": True, "malformed": False, "document": 2,
        },
    ],
    "total": 10,
    "malformed": 1,
    "emptyBody": 3,
    "documents": [
        {"docType": "PCB", "recordCount": 3},
        {"docType": "FOOTPRINT", "recordCount": 2},
        {"docType": "SYMBOL", "recordCount": 2},
    ],
    "documentTypes": {"SCH": 1, "PCB": 1, "FOOTPRINT": 1, "SYMBOL": 1},
    "recordsByType": {"DOCHEAD": 4, "PAD": 3, "PIN": 1, "WIRE": 1},
}


def _project(text: str, name: str = "synthetic") -> dict:
    return differential.project_payload(
        KIND, {"schema": "boardwise.epru-stream-sample/1", "name": name, "text": text}
    )


def test_projection_is_the_language_neutral_contract_document() -> None:
    """The exact document the Rust runner has to reproduce, key for key."""
    projection = _project(SAMPLE)

    assert projection == EXPECTED
    assert projection["schema"] == differential.EPRU_STREAM_SCHEMA
    assert set(projection) == {
        "schema", "records", "total", "malformed", "emptyBody",
        "documents", "documentTypes", "recordsByType",
    }
    # No body is published: presence only, and no drift signal either.
    assert set(projection["records"][3]) == {
        "lineNo", "type", "hasBody", "emptyBody", "malformed", "document",
    }


def test_every_non_empty_line_is_a_record_with_its_file_line_number() -> None:
    """Malformed lines keep their entry: the differential has to see the same lines."""
    text = "\n" + SAMPLE + "\n" + "   "

    projection = _project(text)

    # Line 0 is blank, the sample occupies lines 1..10, and the whitespace-only
    # line is line 11 — a record, while the blank one is not.
    assert [record["lineNo"] for record in projection["records"]] == [
        1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11,
    ]
    assert projection["total"] == len(projection["records"]) == 11
    assert projection["malformed"] == 2
    assert projection["records"][-1] == {
        "lineNo": 11, "type": "", "hasBody": False,
        "emptyBody": False, "malformed": True,
    }


def test_a_terminated_final_line_with_a_body_is_a_decoded_record() -> None:
    """V3 shape: the last line may end ``{env}||{body}|`` like every other one."""
    text = "\n".join([
        '{"type":"DOCHEAD","ticket":1}||{"docType":"PCB"}|',
        '{"type":"ARC","ticket":2}||{"id":"a1"}|',
    ])
    projection = _project(text)

    assert projection["total"] == 2
    assert projection["malformed"] == 0
    last = projection["records"][-1]
    assert (last["type"], last["hasBody"], last["emptyBody"]) == ("ARC", True, False)
    assert projection["documents"] == [{"docType": "PCB", "recordCount": 2}]


def test_both_empty_body_shapes_are_legal_and_a_missing_separator_is_not() -> None:
    """``{env}|||`` and ``{env}||`` are empty bodies; ``{env}`` / ``{env}|`` are not."""
    text = "\n".join([
        '{"type":"DOCHEAD"}||{"docType":"FOOTPRINT"}|',
        '{"type":"PAD"}|||',
        '{"type":"PAD"}||',
    ])
    projection = _project(text)

    assert projection["malformed"] == 0
    assert projection["emptyBody"] == 2
    assert [record["emptyBody"] for record in projection["records"][1:]] == [True, True]
    assert [record["hasBody"] for record in projection["records"][1:]] == [False, False]
    assert projection["documents"] == [{"docType": "FOOTPRINT", "recordCount": 3}]

    truncated = _project("\n".join([
        '{"type":"DOCHEAD"}||{"docType":"PCB"}|',
        '{"type":"PAD","ticket":9}',
        '{"type":"PAD"}|',
    ]))
    assert truncated["malformed"] == 2
    assert truncated["emptyBody"] == 0
    assert truncated["documents"] == [{"docType": "PCB", "recordCount": 1}]
    for line_no, record in enumerate(truncated["records"][1:], start=1):
        assert record == {
            "lineNo": line_no, "type": "", "hasBody": False,
            "emptyBody": False, "malformed": True,
        }


def test_records_of_a_dropped_document_belong_to_no_document() -> None:
    """``SCH`` is counted in ``documentTypes`` yet kept nowhere; a docType-less
    DOCHEAD drops the records that follow it."""
    projection = _project(SAMPLE)

    assert projection["documentTypes"]["SCH"] == 1
    assert [document["docType"] for document in projection["documents"]] == [
        "PCB", "FOOTPRINT", "SYMBOL",
    ]
    assert "document" not in projection["records"][0]
    assert "document" not in projection["records"][1]
    # The malformed line belongs to nothing and does not break the document it
    # interrupts: the splitter never saw it.
    assert "document" not in projection["records"][5]
    assert projection["records"][6]["document"] == 1
    # A record's document is its place in `documents`, DOCHEAD included.
    assert projection["documents"][0]["recordCount"] == 3


def test_the_projection_reads_the_existing_parser_and_never_a_second_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`split_documents` and `iter_epru_records` are the only readers called."""
    calls: list[tuple[str, str]] = []
    real_split = differential.split_documents
    real_iter = differential.iter_epru_records

    def split_spy(text: str, stats: object) -> list:
        calls.append(("split", text))
        return real_split(text, stats)

    def iter_spy(text: str, stats: object | None = None) -> list:
        calls.append(("iter", text))
        return list(real_iter(text, stats))

    monkeypatch.setattr(differential, "split_documents", split_spy)
    monkeypatch.setattr(differential, "iter_epru_records", iter_spy)

    assert _project(SAMPLE) == EXPECTED
    # The split runs once, on the whole text — every count and every document
    # comes from it, not from the per-line pass.
    assert [text for kind, text in calls if kind == "split"] == [SAMPLE]
    # The per-line pass calls the real decoder once per non-empty line.
    assert [text for kind, text in calls if kind == "iter"] == [
        line for line in SAMPLE.split("\n") if line
    ]


def test_the_sample_contract_requires_its_tag_a_name_and_the_text() -> None:
    schema = load_path(SCHEMA_PATH)
    good = {"schema": "boardwise.epru-stream-sample/1", "name": "s", "text": SAMPLE}
    assert_valid(good, schema)

    refused = [
        {"schema": "boardwise.epru-stream-sample/1", "text": SAMPLE},
        {"schema": "boardwise.epru-stream-sample/1", "name": "", "text": SAMPLE},
        {"schema": "boardwise.epru-stream-sample/1", "name": "s"},
        {"schema": "boardwise.epru-stream-sample/2", "name": "s", "text": SAMPLE},
        {**good, "extra": 1},
    ]
    for payload in refused:
        with pytest.raises(ContractValidationError):
            assert_valid(payload, schema)


# ------------------------------------------------------- the two published cases

CASES = ROOT / "contracts" / "differential" / "cases.json"
INPUTS = ROOT / "contracts" / "differential" / "inputs"
SAMPLE_SOURCES = ROOT / "contracts" / "differential" / "sources" / "epru-stream-samples.json"

#: The two case ids the case book publishes for this kind. Two cases of one kind
#: are why the generator keys its table by case id and keeps the kind beside it.
V3_EOF = "epru-stream-v3-eof"
V4_EOF_TRUNCATED = "epru-stream-v4-eof-truncated"


def _declared() -> dict[str, dict]:
    return {entry["caseId"]: entry for entry in load_path(SAMPLE_SOURCES)["samples"]}


def _declared_text(case_id: str) -> str:
    return _declared()[case_id]["text"]


def test_the_published_cases_are_the_declared_samples_and_their_projection() -> None:
    """Publish the declared text, project it — nothing is re-derived on the way."""
    declared = _declared()
    assert sorted(declared) == [V3_EOF, V4_EOF_TRUNCATED]
    rows = {row["id"]: row for row in load_path(CASES)["cases"]}

    for case_id, entry in declared.items():
        published = load_path(INPUTS / entry["input"])
        assert set(published) == {"schema", "name", "text"}
        assert published["schema"] == "boardwise.epru-stream-sample/1"
        assert published["name"] == entry["name"]
        assert published["text"] == entry["text"], "the golden must publish the declared text"

        row = rows[case_id]
        assert row["kind"] == KIND
        assert row["input"] == f"contracts/differential/inputs/{entry['input']}"
        assert row["expected"] == _project(published["text"])
        assert differential.project_case(row, ROOT) == row["expected"]


def test_both_cases_carry_one_kind_and_two_ids() -> None:
    """A case book is keyed by id: one kind cannot be two rows under one name."""
    rows = {row["id"]: row for row in load_path(CASES)["cases"]}
    sample_rows = [row for row in rows.values() if row["kind"] == KIND]

    assert sorted(row["id"] for row in sample_rows) == [V3_EOF, V4_EOF_TRUNCATED]
    assert len({row["input"] for row in sample_rows}) == 2


def test_the_v3_eof_case_ends_with_a_body_and_no_terminator() -> None:
    """V3: the last line may drop its terminator, and that is not a truncation."""
    projection = _project(_declared_text(V3_EOF))

    assert projection["total"] == 5
    assert projection["malformed"] == 0
    assert projection["emptyBody"] == 0
    last = projection["records"][-1]
    assert (last["type"], last["hasBody"], last["emptyBody"]) == ("TEXT", True, False)
    assert last["document"] == 0
    assert projection["documents"] == [{"docType": "PCB", "recordCount": 3}]
    # SCH is still counted, and kept nowhere.
    assert projection["documentTypes"] == {"SCH": 1, "PCB": 1}


def test_the_v4_eof_case_separates_an_empty_body_a_truncation_and_a_terminator() -> None:
    """V4: ``{env}|||`` is an empty body, ``{env}`` is a truncation, ``{env}||`` is
    the end of a stream. Three shapes one character apart, three different records."""
    projection = _project(_declared_text(V4_EOF_TRUNCATED))

    assert projection["total"] == 4
    assert projection["malformed"] == 1
    assert projection["emptyBody"] == 2
    empty_body, truncated, terminator = projection["records"][1:]
    assert (empty_body["type"], empty_body["hasBody"], empty_body["emptyBody"]) == (
        "PAD", False, True,
    )
    assert truncated == {
        "lineNo": 2, "type": "", "hasBody": False,
        "emptyBody": False, "malformed": True,
    }
    assert (terminator["type"], terminator["hasBody"], terminator["emptyBody"]) == (
        "PAD", False, True,
    )
    assert terminator["malformed"] is False
    # The truncated line interrupts nothing: the splitter never saw it, so the
    # document still holds its other three records.
    assert projection["documents"] == [{"docType": "FOOTPRINT", "recordCount": 3}]
