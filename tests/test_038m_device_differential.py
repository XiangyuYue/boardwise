"""038M — the `device-library-sample` differential contract, Python half.

One case kind, one projection: the input is ``{schema, name, text}`` and both
runners derive the same ``boardwise.device-library/1`` document from ``text``.
This file pins the Python side of that document, and pins the rule the batch
exists for: the projection is a **view**.

Both the device map and the one counter come from the real reader —
:func:`boardwise.parsers.epru_stream.iter_epru_records` decodes the stream into
the records the schematic parser consumes, and
:func:`boardwise.parsers.schematic._collect_device_meta` groups them exactly as
the review path does — so a differential mismatch can only ever be about the
projection, never about a second copy of the document/attribute rules.

The expected projection below is written out twice — here and as ``EXPECTED`` in
``rust/crates/boardwise-core/tests/device_library.rs``. The two literals are the
contract; a change on one side has to change both.

Everything here is synthetic: no real project content, no fixture file.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools import differential
from tools.contract_validate import ContractValidationError, assert_valid, load_path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "contracts" / "json" / "device-library-sample-v1.schema.json"
KIND = "device-library-sample"

#: The sample `rust/crates/boardwise-core/tests/device_library.rs:SAMPLE` projects.
#: One line per shape that matters: a dropped ``SCH`` document, a DEVICE with every
#: declared field padded with whitespace, a DEVICE whose attributes are all empty
#: or the editor's ``"null"``, a document with two METAs (the first wins), a DEVICE
#: with no uuid, a copy that differs only in ``editVersion``/record order, a copy
#: that differs in what the model reads (first wins, counted), a device with no
#: ``Designator``, a truthy non-object ``attributes``, a **falsy** non-object
#: ``attributes`` (the empty array — ``or {}`` makes it the empty object), a
#: META with no attributes at all, and a float literal beyond ``f64``'s range
#: (``1e309``) next to a bare big integer that keeps every digit.
SAMPLE = "\n".join([
    '{"type":"DOCHEAD","ticket":1}||{"docType":"SCH","uuid":"sch-1"}|',
    '{"type":"META","ticket":2}||{"title":"Board","attributes":{"Designator":"A?"}}|',
    '{"type":"DOCHEAD","ticket":3}||{"docType":"DEVICE","uuid":"dev-full","editVersion":"1"}|',
    '{"type":"META","ticket":4}||{"title":"  USB-C Receptacle  ","attributes":{"Supplier Part":" C12345 ","Manufacturer Part":"MPN-1","Manufacturer":"ACME Corp","Datasheet":" https://example.invalid/usb-c.pdf ","Supplier Footprint":"0805","Name":"{{Value}}","Symbol":" sym-1 ","Type":" Connector ","LCSC Part Name":"Type-C 16P","Designator":" J? "}}|',
    '{"type":"DOCHEAD","ticket":5}||{"docType":"DEVICE","uuid":"dev-empty"}|',
    '{"type":"META","ticket":6}||{"title":"   ","attributes":{"Supplier Part":"","Manufacturer Part":"null","Manufacturer":null,"Datasheet":"  ","Name":" null ","Symbol":"null","Type":"null","Designator":"   "}}|',
    '{"type":"DOCHEAD","ticket":7}||{"docType":"DEVICE","uuid":"dev-first-meta"}|',
    '{"type":"META","ticket":8}||{"title":"First","attributes":{"Designator":"R?"}}|',
    '{"type":"META","ticket":9}||{"title":"Second","attributes":{"Designator":"C?"}}|',
    '{"type":"DOCHEAD","ticket":10}||{"docType":"DEVICE"}|',
    '{"type":"META","ticket":11}||{"title":"No-Uuid","attributes":{"Designator":"U?"}}|',
    '{"type":"DOCHEAD","ticket":12}||{"docType":"DEVICE","uuid":"dev-same","editVersion":"1"}|',
    '{"type":"META","ticket":13}||{"title":"Same","attributes":{"Supplier Part":"C1","Designator":"D?"}}|',
    '{"type":"DOCHEAD","ticket":14}||{"docType":"DEVICE","uuid":"dev-same","editVersion":"2"}|',
    '{"type":"ATTR","ticket":15}||{"key":"Convert to PCB","value":"1"}|',
    '{"type":"META","ticket":16}||{"attributes":{"Designator":"D?","Supplier Part":"C1"},"title":"Same"}|',
    '{"type":"DOCHEAD","ticket":17}||{"docType":"DEVICE","uuid":"dev-conflict","editVersion":"1"}|',
    '{"type":"META","ticket":18}||{"title":"First Wins","attributes":{"Designator":"R?","Supplier Part":"C100"}}|',
    '{"type":"DOCHEAD","ticket":19}||{"docType":"DEVICE","uuid":"dev-conflict","editVersion":"2"}|',
    '{"type":"META","ticket":20}||{"title":"Second Loses","attributes":{"Designator":"R?","Supplier Part":"C200"}}|',
    '{"type":"DOCHEAD","ticket":21}||{"docType":"DEVICE","uuid":"dev-no-designator"}|',
    '{"type":"META","ticket":22}||{"title":"GND","attributes":{"Symbol":"sym-pwr","Name":"GND"}}|',
    '{"type":"DOCHEAD","ticket":23}||{"docType":"DEVICE","uuid":"dev-odd-attrs"}|',
    '{"type":"META","ticket":24}||{"title":"Odd","attributes":["not","an","object"]}|',
    '{"type":"DOCHEAD","ticket":25}||{"docType":"DEVICE","uuid":"dev-empty-array"}|',
    '{"type":"META","ticket":26}||{"title":"Empty Array","attributes":[]}|',
    '{"type":"DOCHEAD","ticket":27}||{"docType":"DEVICE","uuid":"dev-bare"}|',
    '{"type":"META","ticket":28}||{"title":"Bare"}|',
    # A float literal beyond f64's range: Python's `float()` reads `1e309` as
    # infinity, so the reader's `str()` spells `inf`/`-inf`; `1e-400` underflows
    # to `0.0`. A bare integer literal keeps every digit instead.
    '{"type":"DOCHEAD","ticket":29}||{"docType":"DEVICE","uuid":"dev-overflow"}|',
    '{"type":"META","ticket":30}||{"title":"Overflow","attributes":{"Supplier Part":1e309,"Manufacturer Part":-1e309,"Datasheet":1e-400}}|',
    '{"type":"DOCHEAD","ticket":31}||{"docType":"DEVICE","uuid":"dev-big-int"}|',
    '{"type":"META","ticket":32}||{"title":"Big Integer","attributes":{"Supplier Part":123456789012345678901234567890}}|',
])

#: The Rust half states this document as `EXPECTED`.
EXPECTED = {
    "schema": "boardwise.device-library/1",
    "devices": {
        "dev-full": {
            "title": "USB-C Receptacle",
            "lcsc_part": "C12345",
            "mpn": "MPN-1",
            "manufacturer": "ACME Corp",
            "datasheet": "https://example.invalid/usb-c.pdf",
            "footprint": "0805",
            "name_template": "{{Value}}",
            "symbol": "sym-1",
            "declared_type": {
                "Type": "Connector",
                "LCSC Part Name": "Type-C 16P",
                "Supplier Footprint": "0805",
            },
            "is_part": "yes",
        },
        "dev-empty": {"title": "", "is_part": "no"},
        "dev-first-meta": {"title": "First", "is_part": "yes"},
        "dev-same": {"title": "Same", "lcsc_part": "C1", "is_part": "yes"},
        "dev-conflict": {"title": "First Wins", "lcsc_part": "C100", "is_part": "yes"},
        "dev-no-designator": {
            "title": "GND",
            "name_template": "GND",
            "symbol": "sym-pwr",
            "is_part": "no",
        },
        "dev-odd-attrs": {"title": "Odd"},
        "dev-empty-array": {"title": "Empty Array", "is_part": "no"},
        "dev-bare": {"title": "Bare", "is_part": "no"},
        "dev-overflow": {
            "title": "Overflow",
            "lcsc_part": "inf",
            "mpn": "-inf",
            "datasheet": "0.0",
            "is_part": "no",
        },
        "dev-big-int": {
            "title": "Big Integer",
            "lcsc_part": "123456789012345678901234567890",
            "is_part": "no",
        },
    },
    "conflictingDocuments": 1,
}


def _project(text: str, name: str = "synthetic") -> dict:
    return differential.project_payload(
        KIND,
        {
            "schema": "boardwise.device-library-sample/1",
            "name": name,
            "text": text,
        },
    )


def test_the_projection_is_the_language_neutral_contract_document() -> None:
    """The exact document the Rust runner has to reproduce, key for key."""
    assert _project(SAMPLE) == EXPECTED


def test_a_document_that_is_not_a_device_is_skipped() -> None:
    """The ``SCH`` META at the top of the sample belongs to no device."""
    text = "\n".join([
        '{"type":"DOCHEAD"}||{"docType":"SCH","uuid":"sch-1"}|',
        '{"type":"META"}||{"title":"Board","attributes":{"Designator":"A?"}}|',
        '{"type":"DOCHEAD"}||{"docType":"DEVICE","uuid":"dev"}|',
        '{"type":"META"}||{"title":"R0402"}|',
    ])
    assert _project(text) == {
        "schema": "boardwise.device-library/1",
        "devices": {"dev": {"title": "R0402", "is_part": "no"}},
        "conflictingDocuments": 0,
    }


def test_every_declared_field_travels_with_the_pythons_readers_own_name() -> None:
    """The six `DEVICE_ATTR_FIELDS` values, the symbol, the declared type, is_part."""
    device = _project(SAMPLE)["devices"]["dev-full"]
    assert device == {
        "title": "USB-C Receptacle",
        "lcsc_part": "C12345",
        "mpn": "MPN-1",
        "manufacturer": "ACME Corp",
        "datasheet": "https://example.invalid/usb-c.pdf",
        "footprint": "0805",
        "name_template": "{{Value}}",
        "symbol": "sym-1",
        "declared_type": {
            "Type": "Connector",
            "LCSC Part Name": "Type-C 16P",
            "Supplier Footprint": "0805",
        },
        "is_part": "yes",
    }
    # The reader's own field names, never the DEVICE attribute spellings.
    assert "Supplier Part" not in device
    assert "Name" not in device


def test_an_empty_or_null_attribute_is_absent() -> None:
    """``""``, whitespace, ``"null"``, ``" null "`` and JSON ``null`` are no value."""
    assert _project(SAMPLE)["devices"]["dev-empty"] == {"title": "", "is_part": "no"}
    # A `null` value is skipped before `str()` runs: `str(None)` would spell
    # "None" and be kept as if it were a value.
    text = "\n".join([
        '{"type":"DOCHEAD"}||{"docType":"DEVICE","uuid":"d"}|',
        '{"type":"META"}||{"title":"t","attributes":'
        '{"Manufacturer":null,"Symbol":null,"Type":null,"LCSC Part Name":"","Designator":null}}|',
    ])
    assert _project(text)["devices"]["d"] == {"title": "t", "is_part": "no"}


def test_the_first_meta_of_a_document_wins() -> None:
    text = "\n".join([
        '{"type":"DOCHEAD"}||{"docType":"DEVICE","uuid":"d"}|',
        '{"type":"META"}||{"title":"First","attributes":{"Supplier Part":"C1"}}|',
        '{"type":"META"}||{"title":"Second","attributes":{"Supplier Part":"C2"}}|',
    ])
    assert _project(text)["devices"]["d"] == {
        "title": "First",
        "lcsc_part": "C1",
        "is_part": "no",
    }


def test_a_device_without_a_uuid_is_no_device() -> None:
    text = "\n".join([
        '{"type":"DOCHEAD"}||{"docType":"DEVICE"}|',
        '{"type":"META"}||{"title":"No uuid","attributes":{"Designator":"U?"}}|',
        '{"type":"DOCHEAD"}||{"docType":"DEVICE","uuid":"kept"}|',
        '{"type":"META"}||{"title":"Kept"}|',
    ])
    assert _project(text) == {
        "schema": "boardwise.device-library/1",
        "devices": {"kept": {"title": "Kept", "is_part": "no"}},
        "conflictingDocuments": 0,
    }


def test_an_identical_duplicate_is_not_a_conflict() -> None:
    """Same uuid twice, another ``editVersion`` and another record order: no drift."""
    text = "\n".join([
        '{"type":"DOCHEAD"}||{"docType":"DEVICE","uuid":"d","editVersion":"1"}|',
        '{"type":"META"}||{"title":"R","attributes":{"Supplier Part":"C1","Designator":"R?"}}|',
        '{"type":"DOCHEAD"}||{"docType":"DEVICE","uuid":"d","editVersion":"7"}|',
        '{"type":"ATTR"}||{"key":"Convert to PCB","value":"1"}|',
        '{"type":"META"}||{"attributes":{"Designator":"R?","Supplier Part":"C1"},"title":"R"}|',
    ])
    projection = _project(text)
    assert projection["conflictingDocuments"] == 0
    assert projection["devices"]["d"] == {
        "title": "R",
        "lcsc_part": "C1",
        "is_part": "yes",
    }


def test_a_differing_duplicate_is_one_conflict_and_the_first_wins() -> None:
    text = "\n".join([
        '{"type":"DOCHEAD"}||{"docType":"DEVICE","uuid":"d"}|',
        '{"type":"META"}||{"title":"First Wins","attributes":{"Supplier Part":"C100"}}|',
        '{"type":"DOCHEAD"}||{"docType":"DEVICE","uuid":"d"}|',
        '{"type":"META"}||{"title":"Second Loses","attributes":{"Supplier Part":"C200"}}|',
    ])
    projection = _project(text)
    assert projection["devices"]["d"] == {
        "title": "First Wins",
        "lcsc_part": "C100",
        "is_part": "no",
    }
    assert projection["conflictingDocuments"] == 1


def test_a_device_without_a_designator_is_not_a_part() -> None:
    text = "\n".join([
        '{"type":"DOCHEAD"}||{"docType":"DEVICE","uuid":"pwr"}|',
        '{"type":"META"}||{"title":"GND","attributes":{"Symbol":"sym-pwr","Designator":"  "}}|',
        '{"type":"DOCHEAD"}||{"docType":"DEVICE","uuid":"part"}|',
        '{"type":"META"}||{"title":"R0402","attributes":{"Designator":"R?"}}|',
    ])
    devices = _project(text)["devices"]
    assert devices["pwr"]["is_part"] == "no"
    assert devices["part"]["is_part"] == "yes"


def test_attributes_that_are_not_an_object_keep_the_title_only() -> None:
    """A truthy non-object skips the whole block — and writes no ``is_part``."""
    text = "\n".join([
        '{"type":"DOCHEAD"}||{"docType":"DEVICE","uuid":"list"}|',
        '{"type":"META"}||{"title":"Odd","attributes":["not","an","object"]}|',
        '{"type":"DOCHEAD"}||{"docType":"DEVICE","uuid":"word"}|',
        '{"type":"META"}||{"title":"Word","attributes":"nope"}|',
    ])
    devices = _project(text)["devices"]
    assert devices["list"] == {"title": "Odd"}
    assert devices["word"] == {"title": "Word"}
    assert "is_part" not in devices["list"]


def test_falsy_attributes_are_the_empty_object_not_a_non_object() -> None:
    """``or {}`` makes an empty array (and an empty string) the empty object.

    So ``is_part`` is written — ``"no"`` — where a truthy non-object leaves it
    out entirely. The two readings must not collapse into one another.
    """
    text = "\n".join([
        '{"type":"DOCHEAD"}||{"docType":"DEVICE","uuid":"arr"}|',
        '{"type":"META"}||{"title":"Empty Array","attributes":[]}|',
        '{"type":"DOCHEAD"}||{"docType":"DEVICE","uuid":"blank"}|',
        '{"type":"META"}||{"title":"Blank","attributes":""}|',
    ])
    devices = _project(text)["devices"]
    assert devices["arr"] == {"title": "Empty Array", "is_part": "no"}
    assert devices["blank"] == {"title": "Blank", "is_part": "no"}


def test_the_projection_states_no_document_text_or_edit_version() -> None:
    rendered = repr(_project(SAMPLE))
    assert "editVersion" not in rendered
    assert "ticket" not in rendered
    assert "docType" not in rendered


def test_the_projection_reads_the_existing_parser_and_never_a_second_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`iter_epru_records` and `_collect_device_meta` are the only readers called,
    and the counter comes from the **same** `ParseStats` the collector filled."""
    calls: list[str] = []
    real_collect = differential._collect_device_meta
    real_iter = differential.iter_epru_records
    stats_seen: list[object] = []

    def iter_spy(text: str, stats: object | None = None) -> list:
        calls.append("iter")
        stats_seen.append(stats)
        return list(real_iter(text, stats))

    def collect_spy(records: list, parse_stats: object | None = None) -> dict:
        calls.append("collect")
        stats_seen.append(parse_stats)
        return real_collect(records, parse_stats)

    monkeypatch.setattr(differential, "_collect_device_meta", collect_spy)
    monkeypatch.setattr(differential, "iter_epru_records", iter_spy)

    assert _project(SAMPLE) == EXPECTED
    assert calls == ["iter", "collect"]
    # One ParseStats instance, handed from the decoder to the device collector:
    # the counter cannot come from a second reading of the same text.
    assert stats_seen[0] is stats_seen[1]
    assert stats_seen[0] is not None


def test_the_sample_contract_requires_its_tag_a_name_and_the_text() -> None:
    schema = load_path(SCHEMA_PATH)
    good = {
        "schema": "boardwise.device-library-sample/1",
        "name": "s",
        "text": SAMPLE,
    }
    assert_valid(good, schema)

    refused = [
        {"schema": "boardwise.device-library-sample/1", "name": "s"},
        {"schema": "boardwise.device-library-sample/1", "text": SAMPLE},
        {"schema": "boardwise.device-library-sample/1", "name": "", "text": SAMPLE},
        {"schema": "boardwise.device-library-sample/2", "name": "s", "text": SAMPLE},
        # A DEVICE is addressed by its own uuid: the SYMBOL sample's key selector
        # is not part of this contract.
        {**good, "pinKey": "zIndex"},
        {**good, "extra": 1},
    ]
    for payload in refused:
        with pytest.raises(ContractValidationError):
            assert_valid(payload, schema)


def test_the_kind_is_the_eighth_kind_the_runner_gates() -> None:
    """The Python schema table carries the kind, and the case book publishes it."""
    assert differential.SCHEMAS[KIND] == "device-library-sample-v1.schema.json"
    assert len(differential.SCHEMAS) == 10


# ------------------------------------------------------- the two published cases

CASES = ROOT / "contracts" / "differential" / "cases.json"
INPUTS = ROOT / "contracts" / "differential" / "inputs"
DEVICE_SOURCES = (
    ROOT / "contracts" / "differential" / "sources" / "device-library-samples.json"
)

V3_META = "device-library-v3-meta"
V4_COPIES = "device-library-v4-copies"

#: The nine case rows published **before** this batch, in book order, with the
#: sha256 of the input bytes each one published then. The batch only adds: these
#: are checked, not promised in prose.
#:
#: `review-report-projection` was re-generated by the batch's own official
#: generator run (`tools/build_differential_fixtures.py`), so its bytes — and
#: only those — are the new digest; the other eight are untouched.
PRE_EXISTING = {
    "review-report-projection": (
        "f0818da8b3832bbaeda0c7a8b2e1df27c154ab5c0cbb29fa877eb46555bbd54a"
    ),
    "layout-plan-geometry": (
        "5241c07f5f0417ea8226720cfbd39f74c813c2a0513635fb1d83cf866f48a233"
    ),
    "compile-result-projection": (
        "2b91af1b5bdac828b08f5b471a565ad6e37c7734c71e3ea5f8344623733e71c1"
    ),
    "compile-page-result-projection": (
        "e1b32d0b7b6280f411dc0741d97e4091ec0c4ef60251afbad6e2e4ec8bce42ab"
    ),
    "lint-result-projection": (
        "15cc8a152471395e2354a6de6f5fd1c29bb6e671a7d217f62be887e7082fd465"
    ),
    "epru-stream-v3-eof": (
        "13e4c8ec9beffc0a70b1cfcd237d82620081e6647fd2bb12d4112fb5a6ac46c1"
    ),
    "epru-stream-v4-eof-truncated": (
        "b2647d6c445f97ad5c0a64bb15cfea0e2428c8da0b00873085a386a904c2bee2"
    ),
    "symbol-library-v3-zindex": (
        "824c6940dad0629a784952013ede4e454bfb416c49a593737ba589ee759e951d"
    ),
    "symbol-library-v4-pin-id": (
        "2c22270ea308c8f9bc2c5a2e5175edbc6360aa8c3649a194c4ef68bea42fd5ea"
    ),
}


def _declared() -> dict[str, dict]:
    return {entry["caseId"]: entry for entry in load_path(DEVICE_SOURCES)["samples"]}


def test_the_published_cases_are_the_declared_samples_and_their_projection() -> None:
    """Publish the declared stream, project it — nothing is re-derived on the way,
    and the case row's golden is that projection."""
    declared = _declared()
    assert sorted(declared) == [V3_META, V4_COPIES]
    assert load_path(DEVICE_SOURCES)["schema"] == "boardwise.device-library-samples/1"
    rows = {row["id"]: row for row in load_path(CASES)["cases"]}

    for case_id, entry in declared.items():
        published = load_path(INPUTS / entry["input"])
        assert set(published) == {"schema", "name", "text"}
        assert published["schema"] == "boardwise.device-library-sample/1"
        assert published["name"] == entry["name"]
        assert published["text"] == entry["text"], "the golden must publish the declared text"

        row = rows[case_id]
        assert row["kind"] == KIND
        assert row["input"] == f"contracts/differential/inputs/{entry['input']}"
        assert row["expected"] == _project(published["text"])
        assert differential.project_case(row, ROOT) == row["expected"]


def test_the_two_cases_are_appended_after_the_nine_that_came_before() -> None:
    """A case book is keyed by id, and the batch only *adds*: the nine earlier
    rows keep their order, their kind and their input bytes."""
    book = load_path(CASES)
    ids = [row["id"] for row in book["cases"]]
    assert ids[:9] == list(PRE_EXISTING)
    assert ids[9:11] == [V3_META, V4_COPIES]
    assert len(ids) == len(set(ids)) == 15
    for row in book["cases"][:9]:
        published = INPUTS / row["input"].rsplit("/", 1)[-1]
        assert hashlib.sha256(published.read_bytes()).hexdigest() == PRE_EXISTING[row["id"]]


def test_the_v3_case_states_every_field_once_and_the_second_meta_loses() -> None:
    """One DEVICE: the first META wins, an empty and a ``"null"`` attribute are not
    emitted, and the second META's title never reaches the golden."""
    published = load_path(INPUTS / f"{V3_META}.json")
    lines = published["text"].split("\n")
    assert sum(1 for line in lines if '"docType":"DEVICE"' in line) == 1
    assert sum(1 for line in lines if '"type":"META"' in line) == 2

    projection = _project(published["text"])
    assert projection["conflictingDocuments"] == 0
    assert list(projection["devices"]) == ["dev-v3-buck-synth"]
    device = projection["devices"]["dev-v3-buck-synth"]
    assert device == {
        "title": "BUCK-5V0-SYNTH",
        "lcsc_part": "C000001",
        "mpn": "SYN-MPN-5V0",
        "datasheet": "https://example.invalid/synth-buck.pdf",
        "footprint": "SOP-8",
        "name_template": "{{Value}}",
        "symbol": "sym-v3-buck-synth",
        "declared_type": {"Type": "DC-DC", "Supplier Footprint": "SOP-8"},
        "is_part": "yes",
    }
    # The sample states an empty `Manufacturer` and a `"null"` `LCSC Part Name`
    # precisely so the golden can show neither becomes a key, and the second META
    # it states is not read at all.
    assert "manufacturer" not in device
    assert "SHOULD-NOT-WIN" not in json.dumps(projection)


def test_the_v4_case_copies_one_device_three_times_and_counts_only_the_drift() -> None:
    """V4 copies a page's DEVICE into every page that places it: the second copy
    differs only in ``editVersion``/record order (0 conflicts), the third changed a
    model-visible value (1 conflict) and loses to the first."""
    published = load_path(INPUTS / f"{V4_COPIES}.json")
    lines = published["text"].split("\n")
    documents = [line for line in lines if '"docType":"DEVICE"' in line]
    assert len(documents) == 3
    assert all('"uuid":"dev-v4-res-0603-synth"' in line for line in documents)
    assert [line.split('"editVersion":"')[1].split('"')[0] for line in documents] == [
        "4.0.1",
        "4.0.2",
        "4.0.3",
    ]
    # The middle copy moved a record and reordered its attributes; none of that is
    # a reading, so it is not a conflict.
    assert any('"key":"Convert to PCB"' in line for line in lines)

    projection = _project(published["text"])
    assert list(projection["devices"]) == ["dev-v4-res-0603-synth"]
    device = projection["devices"]["dev-v4-res-0603-synth"]
    assert device["lcsc_part"] == "C000002", "the first copy wins, the drift is dropped"
    assert device["declared_type"] == {"Type": "Chip Resistor", "Supplier Footprint": "0603"}
    assert device["is_part"] == "yes"
    assert projection["conflictingDocuments"] == 1



def test_a_float_literal_beyond_f64s_range_spells_inf_not_the_literal() -> None:
    """`1e309` denotes no `f64`: Python's `float()` saturates it to an infinity,
    so the reader's `str()` gives ``inf``/``-inf`` — never the literal. The Rust
    half (``device_library.rs``) states the same document."""
    text = "\n".join([
        '{"type":"DOCHEAD"}||{"docType":"DEVICE","uuid":"d"}|',
        '{"type":"META"}||{"title":"t","attributes":'
        '{"Supplier Part":1e309,"Manufacturer Part":-1e309,"Datasheet":1e-400}}|',
    ])
    assert _project(text)["devices"]["d"] == {
        "title": "t",
        "lcsc_part": "inf",
        "mpn": "-inf",
        "datasheet": "0.0",
        "is_part": "no",
    }


def test_a_bare_integer_literal_keeps_every_digit() -> None:
    """An integer literal is not a float: Python prints the exact integer, so the
    reader must not route it through a double."""
    text = "\n".join([
        '{"type":"DOCHEAD"}||{"docType":"DEVICE","uuid":"d"}|',
        '{"type":"META"}||{"title":"t","attributes":'
        '{"Supplier Part":123456789012345678901234567890}}|',
    ])
    assert _project(text)["devices"]["d"] == {
        "title": "t",
        "lcsc_part": "123456789012345678901234567890",
        "is_part": "no",
    }
