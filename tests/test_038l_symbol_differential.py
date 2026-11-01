"""038L — the `symbol-library-sample` differential contract, Python half.

One case kind, one projection: the input is ``{schema, name, text, pinKey}`` and
both runners derive the same ``boardwise.symbol-library/1`` document from
``text``. This file pins the Python side of that document, and pins the rule the
batch exists for: the projection is a **view**.

Both the pin map and both counters come from the real reader —
:func:`boardwise.parsers.epru_stream.iter_epru_records` decodes the stream into
the records the schematic parser consumes, and
:func:`boardwise.parsers.schematic._collect_symbols` groups them exactly as the
review path does — so a differential mismatch can only ever be about the
projection, never about a second copy of the two-phase attribution rules.

The expected projection below is written out twice — here and as
``ZINDEX_EXPECTED``/``PIN_ID_EXPECTED`` in
``rust/crates/boardwise-core/tests/symbol_library.rs``. The two literals are the
contract; a change on one side has to change both.

Everything here is synthetic: no real project content, no fixture file.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from tools import differential
from tools.contract_validate import ContractValidationError, assert_valid, load_path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "contracts" / "json" / "symbol-library-sample-v1.schema.json"
KIND = "symbol-library-sample"

#: The sample `rust/crates/boardwise-core/tests/symbol_library.rs:SAMPLE`
#: projects. One line per shape that matters: a dropped ``SCH`` document, a
#: SYMBOL whose ``PIN`` row carries an ``id`` that is *not* ``e<zIndex>``, an
#: ``ATTR`` before its ``PIN``, an ``ATTR`` addressed by the format's ref as well
#: as by the row's id, an ``ATTR`` with no ``parentId`` (open-run fallback),
#: numeric-string coordinates, a by_id/by_ref collision, a run with no number, an
#: empty-body ``PIN``, a SYMBOL with no uuid, an identical copy (record order
#: swapped, other ``editVersion``), a copy that differs (and loses, first-wins),
#: and a ``DEVICE`` document that is not read at all.
SAMPLE = "\n".join([
    '{"type":"DOCHEAD","ticket":1}||{"docType":"SCH"}|',
    '{"type":"PIN","ticket":2}||{"zIndex":99,"x":1,"y":1}|',
    '{"type":"DOCHEAD","ticket":3}||{"docType":"SYMBOL","uuid":"sym-a","editVersion":"1"}|',
    '{"type":"META","ticket":4}||{"title":"USB-C"}|',
    '{"type":"ATTR","ticket":5}||{"key":"Pin Number","value":"A1","parentId":"e9"}|',
    '{"type":"PIN","ticket":6,"id":"e9"}||{"zIndex":5,"x":12.25,"y":-30.5}|',
    '{"type":"ATTR","ticket":7}||{"key":"Pin Name","value":"VBUS","parentId":"e5"}|',
    '{"type":"ATTR","ticket":8}||{"key":"Pin Type","value":"Power"}|',
    '{"type":"PIN","ticket":9,"id":"p1"}||{"zIndex":1,"x":"7","y":"3"}|',
    '{"type":"ATTR","ticket":10}||{"key":"Pin Number","value":"1","parentId":"p1"}|',
    '{"type":"PIN","ticket":11,"id":"e1"}||{"zIndex":4,"x":0.1234567,"y":5.5}|',
    '{"type":"ATTR","ticket":12}||{"key":"Pin Number","value":"4","parentId":"e4"}|',
    '{"type":"ATTR","ticket":13}||{"key":"Pin Name","value":"SENSE","parentId":"e1"}|',
    '{"type":"PIN","ticket":14}||{"zIndex":6,"x":4.5,"y":4.5}|',
    '{"type":"ATTR","ticket":15}||{"key":"Pin Number","value":"6"}|',
    '{"type":"PIN","ticket":16,"id":"p8"}||{"zIndex":8,"x":2,"y":2}|',
    '{"type":"ATTR","ticket":17}||{"key":"Pin Name","value":"NC"}|',
    '{"type":"PIN","ticket":18,"id":"p9"}||',
    '{"type":"ATTR","ticket":19}||{"key":"Pin Name","value":""}|',
    '{"type":"ATTR","ticket":20}||{"key":"Pin Type","value":"null"}|',
    '{"type":"DOCHEAD","ticket":21}||{"docType":"SYMBOL"}|',
    '{"type":"PIN","ticket":22,"id":"d1"}||{"zIndex":1,"x":0,"y":0}|',
    '{"type":"ATTR","ticket":23}||{"key":"Pin Number","value":"1","parentId":"d1"}|',
    '{"type":"DOCHEAD","ticket":24}||{"docType":"SYMBOL","uuid":"sym-b","editVersion":"1"}|',
    '{"type":"META","ticket":25}||{"title":"R"}|',
    '{"type":"PIN","ticket":26,"id":"b1"}||{"zIndex":1,"x":-1.5,"y":2.25}|',
    '{"type":"ATTR","ticket":27}||{"key":"Pin Number","value":"1","parentId":"b1"}|',
    '{"type":"DOCHEAD","ticket":28}||{"docType":"SYMBOL","uuid":"sym-b","editVersion":"2"}|',
    '{"type":"ATTR","ticket":29}||{"key":"Pin Number","value":"1","parentId":"b1"}|',
    '{"type":"PIN","ticket":30,"id":"b1"}||{"zIndex":1,"x":-1.5,"y":2.25}|',
    '{"type":"META","ticket":31}||{"title":"R"}|',
    '{"type":"DOCHEAD","ticket":32}||{"docType":"SYMBOL","uuid":"sym-b","editVersion":"3"}|',
    '{"type":"META","ticket":33}||{"title":"R"}|',
    '{"type":"PIN","ticket":34,"id":"b1"}||{"zIndex":1,"x":-1.5,"y":2.25}|',
    '{"type":"ATTR","ticket":35}||{"key":"Pin Number","value":"1","parentId":"b1"}|',
    '{"type":"ATTR","ticket":36}||{"key":"Pin Name","value":"OUT","parentId":"b1"}|',
    '{"type":"DOCHEAD","ticket":37}||{"docType":"DEVICE","uuid":"dev"}|',
    '{"type":"ATTR","ticket":38}||{"key":"Pin Number","value":"99"}|',
])

#: The Rust half states this document as `ZINDEX_EXPECTED`.
ZINDEX_EXPECTED = {
    "schema": "boardwise.symbol-library/1",
    "pinKey": "zIndex",
    "symbols": {
        "sym-a": {
            "title": "USB-C",
            "pins": {
                "A1": {
                    "point": [12.25, 30.5], "ref": "e5",
                    "name": "VBUS", "type": "Power",
                },
                "1": {"point": [7.0, -3.0], "ref": "e1"},
                "4": {"point": [0.123457, -5.5], "ref": "e4", "name": "SENSE"},
                "6": {"point": [4.5, -4.5], "ref": "e6"},
            },
        },
        "sym-b": {"title": "R", "pins": {"1": {"point": [-1.5, -2.25], "ref": "e1"}}},
    },
    "pinsDroppedNoNumber": 1,
    "conflictingDocuments": 1,
}

#: The Rust half states this document as `PIN_ID_EXPECTED`.
PIN_ID_EXPECTED = {
    "schema": "boardwise.symbol-library/1",
    "pinKey": "pin_id",
    "symbols": {
        "sym-a": {
            "title": "USB-C",
            "pins": {
                "A1": {
                    "point": [12.25, 30.5], "ref": "e9",
                    "name": "VBUS", "type": "Power",
                },
                "1": {"point": [7.0, -3.0], "ref": "p1"},
                "4": {"point": [0.123457, -5.5], "ref": "e1", "name": "SENSE"},
                "6": {"point": [4.5, -4.5], "ref": "e6"},
            },
        },
        "sym-b": {"title": "R", "pins": {"1": {"point": [-1.5, -2.25], "ref": "b1"}}},
    },
    "pinsDroppedNoNumber": 1,
    "conflictingDocuments": 1,
}


def _project(text: str, pin_key: str = "zIndex", name: str = "synthetic") -> dict:
    return differential.project_payload(
        KIND,
        {
            "schema": "boardwise.symbol-library-sample/1",
            "name": name,
            "text": text,
            "pinKey": pin_key,
        },
    )


def test_the_projection_is_the_language_neutral_contract_document() -> None:
    """The exact documents the Rust runner has to reproduce, key for key."""
    assert _project(SAMPLE, "zIndex") == ZINDEX_EXPECTED
    assert _project(SAMPLE, "pin_id") == PIN_ID_EXPECTED

    projection = _project(SAMPLE)
    assert projection["schema"] == differential.SYMBOL_LIBRARY_SCHEMA
    assert set(projection) == {
        "schema", "pinKey", "symbols", "pinsDroppedNoNumber", "conflictingDocuments",
    }
    # A named pin states four fields; an unnamed one states two. Nothing else.
    named = projection["symbols"]["sym-a"]["pins"]["A1"]
    assert set(named) == {"point", "ref", "name", "type"}
    assert set(projection["symbols"]["sym-a"]["pins"]["6"]) == {"point", "ref"}


def test_a_pin_id_ref_is_the_rows_own_id_not_the_synthesised_zindex() -> None:
    """V3: the PIN row's ``id`` is ``e9`` while its zIndex makes the ref ``e5``."""
    text = "\n".join([
        '{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u"}|',
        '{"type":"PIN","id":"e9"}||{"zIndex":5,"x":1,"y":2}|',
        '{"type":"ATTR"}||{"key":"Pin Number","value":"1","parentId":"e9"}|',
    ])

    assert _project(text, "zIndex")["symbols"]["u"]["pins"]["1"]["ref"] == "e5"
    assert _project(text, "pin_id")["symbols"]["u"]["pins"]["1"]["ref"] == "e9"

    # A PIN with no envelope id has no other spelling: both modes fall back to
    # ``e<zIndex>``, which is Python's ``str`` of the zIndex value.
    without_id = "\n".join([
        '{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u"}|',
        '{"type":"PIN"}||{"zIndex":5,"x":1,"y":2}|',
        '{"type":"ATTR"}||{"key":"Pin Number","value":"1"}|',
    ])
    assert _project(without_id, "pin_id")["symbols"]["u"]["pins"]["1"]["ref"] == "e5"


def test_an_attribute_before_its_pin_is_filed_by_parent_id() -> None:
    text = "\n".join([
        '{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u"}|',
        '{"type":"ATTR"}||{"key":"Pin Number","value":"A1","parentId":"e9"}|',
        '{"type":"PIN","id":"e9"}||{"zIndex":5,"x":1,"y":2}|',
    ])

    assert _project(text)["symbols"]["u"]["pins"] == {
        "A1": {"point": [1.0, -2.0], "ref": "e5"},
    }


def test_an_attribute_after_the_last_pin_is_filed_by_parent_id() -> None:
    """3.2.186's shape: the numbers sit in one block after the last PIN."""
    text = "\n".join([
        '{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u"}|',
        '{"type":"PIN","id":"p1"}||{"zIndex":1,"x":0,"y":0}|',
        '{"type":"PIN","id":"p2"}||{"zIndex":2,"x":0,"y":0}|',
        '{"type":"ATTR"}||{"key":"Pin Number","value":"2","parentId":"p2"}|',
        '{"type":"ATTR"}||{"key":"Pin Number","value":"1","parentId":"p1"}|',
    ])

    pins = _project(text)["symbols"]["u"]["pins"]
    assert sorted(pins) == ["1", "2"]
    assert pins["1"]["ref"] == "e1"
    assert pins["2"]["ref"] == "e2"


def test_an_attribute_naming_nothing_falls_back_to_the_open_run() -> None:
    text = "\n".join([
        '{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u"}|',
        '{"type":"PIN","id":"p1"}||{"zIndex":1,"x":0,"y":0}|',
        '{"type":"ATTR"}||{"key":"Pin Number","value":"1","parentId":"nobody"}|',
        '{"type":"ATTR"}||{"key":"Pin Name","value":"NAME","parentId":""}|',
    ])

    assert _project(text)["symbols"]["u"]["pins"] == {
        "1": {"point": [0.0, -0.0], "ref": "e1", "name": "NAME"},
    }


def test_a_parent_id_naming_two_pins_resolves_by_id_first() -> None:
    """``p1``'s ref is ``e1`` and the *next* row's own id is ``e1``: one spelling,
    two pins. The id owner takes the attribute, exactly like ``by_id or by_ref``,
    and the field it fills cannot be stolen back afterwards."""
    text = "\n".join([
        '{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u"}|',
        '{"type":"PIN","id":"p1"}||{"zIndex":1,"x":0,"y":0}|',
        '{"type":"ATTR"}||{"key":"Pin Number","value":"1","parentId":"p1"}|',
        '{"type":"PIN","id":"e1"}||{"zIndex":4,"x":0,"y":0}|',
        '{"type":"ATTR"}||{"key":"Pin Number","value":"4","parentId":"e4"}|',
        '{"type":"ATTR"}||{"key":"Pin Name","value":"SENSE","parentId":"e1"}|',
    ])

    pins = _project(text)["symbols"]["u"]["pins"]
    assert pins["1"]["ref"] == "e1"
    assert "name" not in pins["1"], "the ref owner keeps none"
    assert pins["4"]["ref"] == "e4"
    assert pins["4"]["name"] == "SENSE"


def test_a_run_without_a_number_is_dropped_and_counted() -> None:
    text = "\n".join([
        '{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u"}|',
        '{"type":"PIN","id":"p1"}||{"zIndex":1,"x":0,"y":0}|',
        '{"type":"ATTR"}||{"key":"Pin Name","value":"ONLY_A_NAME"}|',
        '{"type":"PIN","id":"p2"}||{"zIndex":2,"x":1,"y":1}|',
        '{"type":"ATTR"}||{"key":"Pin Number","value":"2","parentId":"p2"}|',
    ])

    projection = _project(text)
    assert projection["pinsDroppedNoNumber"] == 1
    assert projection["symbols"]["u"]["pins"] == {
        "2": {"point": [1.0, -1.0], "ref": "e2"},
    }


def test_an_empty_body_record_is_neither_a_run_nor_a_drop() -> None:
    """``{env}||`` and ``{env}|||`` are legal empty bodies: nothing to read, so no
    run, no ``parentId``, and — because no run exists — no dropped-pin count."""
    text = "\n".join([
        '{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u"}|',
        '{"type":"PIN","id":"p1"}||',
        '{"type":"PIN"}||{"zIndex":1,"x":2,"y":3}|',
        '{"type":"ATTR"}|||',
        '{"type":"ATTR"}||{"key":"Pin Number","value":"1"}|',
    ])

    projection = _project(text)
    assert projection["pinsDroppedNoNumber"] == 0
    assert projection["symbols"]["u"]["pins"] == {
        "1": {"point": [2.0, -3.0], "ref": "e1"},
    }


def test_an_identical_duplicate_document_is_not_a_conflict() -> None:
    """Same symbol, other ``editVersion``, records written in another order."""
    text = "\n".join([
        '{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u","editVersion":"1"}|',
        '{"type":"META"}||{"title":"R"}|',
        '{"type":"PIN","id":"b1"}||{"zIndex":1,"x":1,"y":2}|',
        '{"type":"ATTR"}||{"key":"Pin Number","value":"1","parentId":"b1"}|',
        '{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u","editVersion":"2"}|',
        '{"type":"ATTR"}||{"key":"Pin Number","value":"1","parentId":"b1"}|',
        '{"type":"PIN","id":"b1"}||{"zIndex":1,"x":1,"y":2}|',
        '{"type":"META"}||{"title":"R"}|',
    ])

    projection = _project(text)
    assert projection["conflictingDocuments"] == 0
    assert projection["pinsDroppedNoNumber"] == 0


def test_a_different_duplicate_document_is_one_conflict_and_the_first_wins() -> None:
    text = "\n".join([
        '{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u"}|',
        '{"type":"META"}||{"title":"R"}|',
        '{"type":"PIN","id":"b1"}||{"zIndex":1,"x":1,"y":2}|',
        '{"type":"ATTR"}||{"key":"Pin Number","value":"1","parentId":"b1"}|',
        '{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u"}|',
        '{"type":"META"}||{"title":"R"}|',
        '{"type":"PIN","id":"b1"}||{"zIndex":1,"x":1,"y":2}|',
        '{"type":"ATTR"}||{"key":"Pin Number","value":"1","parentId":"b1"}|',
        '{"type":"ATTR"}||{"key":"Pin Name","value":"OUT","parentId":"b1"}|',
    ])

    projection = _project(text)
    assert projection["conflictingDocuments"] == 1
    # First-wins: the later copy's extra name never lands.
    assert projection["symbols"]["u"]["pins"] == {
        "1": {"point": [1.0, -2.0], "ref": "e1"},
    }


def test_a_document_without_a_uuid_is_no_symbol() -> None:
    text = "\n".join([
        '{"type":"DOCHEAD"}||{"docType":"SYMBOL"}|',
        '{"type":"PIN","id":"d1"}||{"zIndex":1,"x":0,"y":0}|',
        '{"type":"ATTR"}||{"key":"Pin Number","value":"1","parentId":"d1"}|',
    ])

    projection = _project(text)
    assert projection["symbols"] == {}
    # The pin had a number, so nothing was dropped either.
    assert projection["pinsDroppedNoNumber"] == 0


def test_the_stored_y_is_negated_once_and_rounded_to_six_decimals() -> None:
    text = "\n".join([
        '{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u"}|',
        '{"type":"PIN","id":"p1"}||{"zIndex":1,"x":12.25,"y":-30.5}|',
        '{"type":"ATTR"}||{"key":"Pin Number","value":"1"}|',
        '{"type":"PIN","id":"p2"}||{"zIndex":2,"x":0.1234567,"y":"-0"}|',
        '{"type":"ATTR"}||{"key":"Pin Number","value":"2"}|',
        '{"type":"PIN","id":"p3"}||{"zIndex":3}|',
        '{"type":"ATTR"}||{"key":"Pin Number","value":"3"}|',
    ])

    pins = _project(text)["symbols"]["u"]["pins"]
    # Canvas space: the file stores y opposite to the canvas, so it is negated
    # exactly once — flipping again would put the pin at the top of the page.
    assert pins["1"]["point"] == [12.25, 30.5]
    assert pins["2"]["point"] == [0.123457, 0.0]
    # A missing coordinate is 0, and ``-0`` is still zero — with its sign kept.
    assert pins["3"]["point"] == [0.0, -0.0]
    assert math.copysign(1.0, pins["3"]["point"][1]) == -1.0
    assert math.copysign(1.0, pins["2"]["point"][1]) == 1.0


def test_an_unknown_pin_key_is_refused() -> None:
    with pytest.raises(ValueError, match="pinKey"):
        _project(SAMPLE, "pinId")


def test_the_projection_reads_the_existing_parser_and_never_a_second_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`iter_epru_records` and `_collect_symbols` are the only readers called, and
    both counters come from the **same** `ParseStats` the symbol parser filled."""
    calls: list[tuple[str, object]] = []
    real_collect = differential._collect_symbols
    real_iter = differential.iter_epru_records
    stats_seen: list[object] = []

    def iter_spy(text: str, stats: object | None = None) -> list:
        calls.append(("iter", text))
        stats_seen.append(stats)
        return list(real_iter(text, stats))

    def collect_spy(records: list, parse_stats: object | None = None, *, pin_key: str = "zIndex"):
        calls.append(("collect", pin_key))
        stats_seen.append(parse_stats)
        return real_collect(records, parse_stats, pin_key=pin_key)

    monkeypatch.setattr(differential, "_collect_symbols", collect_spy)
    monkeypatch.setattr(differential, "iter_epru_records", iter_spy)

    projection = _project(SAMPLE)
    assert projection == ZINDEX_EXPECTED
    assert [kind for kind, _ in calls] == ["iter", "collect"]
    assert calls[0][1] == SAMPLE
    assert calls[1][1] == "zIndex"
    # One ParseStats instance, handed from the decoder to the symbol parser: the
    # two counters cannot come from two different readings of the same text.
    assert stats_seen[0] is stats_seen[1]
    assert stats_seen[0] is not None


def test_the_sample_contract_requires_its_tag_a_name_the_text_and_the_pin_key() -> None:
    schema = load_path(SCHEMA_PATH)
    good = {
        "schema": "boardwise.symbol-library-sample/1",
        "name": "s",
        "text": SAMPLE,
        "pinKey": "zIndex",
    }
    assert_valid(good, schema)
    assert_valid({**good, "pinKey": "pin_id"}, schema)

    refused = [
        {"schema": "boardwise.symbol-library-sample/1", "name": "s", "pinKey": "zIndex"},
        {"schema": "boardwise.symbol-library-sample/1", "name": "s", "text": SAMPLE},
        {"schema": "boardwise.symbol-library-sample/1", "text": SAMPLE, "pinKey": "zIndex"},
        {"schema": "boardwise.symbol-library-sample/1", "name": "", "text": SAMPLE,
         "pinKey": "zIndex"},
        {"schema": "boardwise.symbol-library-sample/2", "name": "s", "text": SAMPLE,
         "pinKey": "zIndex"},
        {**good, "pinKey": "pinId"},
        {**good, "extra": 1},
    ]
    for payload in refused:
        with pytest.raises(ContractValidationError):
            assert_valid(payload, schema)


def test_the_kind_is_the_seventh_kind_the_runner_gates() -> None:
    """The Python schema table now carries the kind: the two declared samples are
    published, so `project_case` resolves them instead of refusing the name."""
    assert differential.SCHEMAS[KIND] == "symbol-library-sample-v1.schema.json"
    assert len(differential.SCHEMAS) == 7


# ------------------------------------------------------- the two published cases

CASES = ROOT / "contracts" / "differential" / "cases.json"
INPUTS = ROOT / "contracts" / "differential" / "inputs"
SYMBOL_SOURCES = (
    ROOT / "contracts" / "differential" / "sources" / "symbol-library-samples.json"
)

V3_ZINDEX = "symbol-library-v3-zindex"
V4_PIN_ID = "symbol-library-v4-pin-id"


def _declared() -> dict[str, dict]:
    return {entry["caseId"]: entry for entry in load_path(SYMBOL_SOURCES)["samples"]}


def test_the_published_cases_are_the_declared_samples_and_their_projection() -> None:
    """Publish the declared stream and pinKey, project them — nothing is
    re-derived on the way, and the case row's golden is that projection."""
    declared = _declared()
    assert sorted(declared) == [V3_ZINDEX, V4_PIN_ID]
    rows = {row["id"]: row for row in load_path(CASES)["cases"]}

    for case_id, entry in declared.items():
        published = load_path(INPUTS / entry["input"])
        assert set(published) == {"schema", "name", "text", "pinKey"}
        assert published["schema"] == "boardwise.symbol-library-sample/1"
        assert (published["name"], published["pinKey"]) == (entry["name"], entry["pinKey"])
        assert published["text"] == entry["text"], "the golden must publish the declared text"

        row = rows[case_id]
        assert row["kind"] == KIND
        assert row["input"] == f"contracts/differential/inputs/{entry['input']}"
        assert row["expected"] == _project(published["text"], published["pinKey"])
        assert differential.project_case(row, ROOT) == row["expected"]


def test_the_two_cases_are_appended_after_the_seven_that_came_before() -> None:
    """A case book is keyed by id, and the batch only *adds*: the seven earlier
    rows keep their order, their kind and their input."""
    ids = [row["id"] for row in load_path(CASES)["cases"]]
    assert ids[:7] == [
        "review-report-projection",
        "layout-plan-geometry",
        "compile-result-projection",
        "compile-page-result-projection",
        "lint-result-projection",
        "epru-stream-v3-eof",
        "epru-stream-v4-eof-truncated",
    ]
    assert ids[7:] == [V3_ZINDEX, V4_PIN_ID]
    assert len(ids) == len(set(ids)) == 9


def test_the_v3_case_keys_its_pins_by_the_synthesised_ref_not_the_envelope_id() -> None:
    """V3: every PIN row's envelope ``id`` is a GUID, so ``e<zIndex>`` is the only
    spelling the attributes can name — and they arrive **after** the last PIN."""
    published = load_path(INPUTS / "symbol-library-v3-zindex.json")
    assert published["pinKey"] == "zIndex"
    lines = published["text"].split("\n")

    pins = [line for line in lines if '"type":"PIN"' in line]
    assert len(pins) == 3
    for index, line in enumerate(pins, start=1):
        # The id is never `e<zIndex>`: that is the whole reason the ref exists.
        assert "4f2c9d1e-" in line
        assert f'"id":"e{index}"' not in line
    last_pin = max(line_no for line_no, line in enumerate(lines) if '"type":"PIN"' in line)
    first_attr = min(line_no for line_no, line in enumerate(lines) if '"type":"ATTR"' in line)
    assert first_attr > last_pin, "every attribute is appended after the last PIN"

    projection = _project(published["text"], published["pinKey"])
    assert list(projection["symbols"]) == ["sym-v3-ldo"]
    pins_out = projection["symbols"]["sym-v3-ldo"]["pins"]
    assert {number: pin["ref"] for number, pin in pins_out.items()} == {
        "1": "e1", "2": "e2", "3": "e3",
    }
    assert {number: pin.get("name") for number, pin in pins_out.items()} == {
        "1": "VIN", "2": "GND", "3": "VOUT",
    }
    assert pins_out["3"]["type"] == "Power"
    # The DEVICE document that follows is counted by the stream scan and read by
    # nothing: it cannot become a second symbol.
    assert projection["pinsDroppedNoNumber"] == 0
    assert projection["conflictingDocuments"] == 0


def test_the_v4_case_copies_one_library_three_times_and_counts_only_the_drift() -> None:
    """V4 copies a page's SYMBOL into every page that places it: two copies are the
    same symbol (0 conflicts), the third moved a pin name (1 conflict) and loses to
    the first — while each copy's number-less run is counted on its own."""
    published = load_path(INPUTS / "symbol-library-v4-pin-id.json")
    assert published["pinKey"] == "pin_id"
    documents = [
        line for line in published["text"].split("\n")
        if '"docType":"SYMBOL"' in line
    ]
    assert len(documents) == 3
    assert all('"uuid":"sym-v4-opamp"' in line for line in documents)
    assert [line.split('"editVersion":"')[1].split('"')[0] for line in documents[:2]] == [
        "3.2.186", "3.2.186",
    ]

    projection = _project(published["text"], published["pinKey"])
    assert projection["pinKey"] == "pin_id"
    assert list(projection["symbols"]) == ["sym-v4-opamp"]
    pins = projection["symbols"]["sym-v4-opamp"]["pins"]
    # `pin_id` uses the row's own id, which here is not `e<zIndex>`.
    assert {number: pin["ref"] for number, pin in pins.items()} == {
        "1": "n1", "2": "n2",
    }
    assert pins["1"]["name"] == "IN+"
    assert pins["2"]["name"] == "IN-", "the first document wins, so the drift is dropped"
    assert projection["conflictingDocuments"] == 1
    # One nameless `NC` run per copy: three documents, three dropped pins.
    assert projection["pinsDroppedNoNumber"] == 3


# ------------------------------------------------- repeated numbers, renumbering


def test_a_repeated_number_keeps_the_name_and_type_its_duplicate_omits() -> None:
    """A number is filed per **field**: point and ref are last-wins, a name or
    type only moves when the duplicate run actually carries one."""
    text = "\n".join([
        '{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u"}|',
        '{"type":"PIN","id":"r1"}||{"zIndex":1,"x":0,"y":0}|',
        '{"type":"ATTR"}||{"key":"Pin Number","value":"1","parentId":"r1"}|',
        '{"type":"ATTR"}||{"key":"Pin Name","value":"VCC","parentId":"r1"}|',
        '{"type":"ATTR"}||{"key":"Pin Type","value":"Power","parentId":"r1"}|',
        '{"type":"PIN","id":"r2"}||{"zIndex":2,"x":10,"y":10}|',
        '{"type":"ATTR"}||{"key":"Pin Number","value":"1","parentId":"r2"}|',
    ])

    assert _project(text)["symbols"]["u"]["pins"] == {
        "1": {"point": [10.0, -10.0], "ref": "e2", "name": "VCC", "type": "Power"},
    }, "a nameless duplicate cannot clear a name that is already placed"

    # A duplicate that carries a value overwrites that field — and only it.
    carrying = "\n".join([
        '{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u"}|',
        '{"type":"PIN","id":"r1"}||{"zIndex":1,"x":0,"y":0}|',
        '{"type":"ATTR"}||{"key":"Pin Number","value":"1","parentId":"r1"}|',
        '{"type":"ATTR"}||{"key":"Pin Name","value":"VCC","parentId":"r1"}|',
        '{"type":"ATTR"}||{"key":"Pin Type","value":"Power","parentId":"r1"}|',
        '{"type":"PIN","id":"r2"}||{"zIndex":2,"x":10,"y":10}|',
        '{"type":"ATTR"}||{"key":"Pin Number","value":"1","parentId":"r2"}|',
        '{"type":"ATTR"}||{"key":"Pin Name","value":"GND","parentId":"r2"}|',
    ])

    assert _project(carrying)["symbols"]["u"]["pins"] == {
        "1": {"point": [10.0, -10.0], "ref": "e2", "name": "GND", "type": "Power"},
    }


def test_a_renumbered_copy_is_the_same_definition_and_a_moved_pin_is_not() -> None:
    """The conflict count compares *definitions*: title, pin number → point, name
    and type. A `ref` is a handle inside one document, so renumbering the
    elements — with every ``parentId`` following — is not a conflict."""
    renumbered = "\n".join([
        '{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u"}|',
        '{"type":"PIN","id":"a1"}||{"zIndex":1,"x":3,"y":4}|',
        '{"type":"ATTR"}||{"key":"Pin Number","value":"1","parentId":"a1"}|',
        '{"type":"ATTR"}||{"key":"Pin Name","value":"IN","parentId":"a1"}|',
        '{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u"}|',
        '{"type":"PIN","id":"b7"}||{"zIndex":9,"x":3,"y":4}|',
        '{"type":"ATTR"}||{"key":"Pin Number","value":"1","parentId":"b7"}|',
        '{"type":"ATTR"}||{"key":"Pin Name","value":"IN","parentId":"b7"}|',
    ])

    projection = _project(renumbered)
    assert projection["conflictingDocuments"] == 0
    # First-wins keeps the first copy's ref, renumbering or not.
    assert projection["symbols"]["u"]["pins"]["1"]["ref"] == "e1"

    moved = renumbered.replace('"zIndex":9,"x":3,"y":4', '"zIndex":9,"x":3,"y":5')
    assert _project(moved)["conflictingDocuments"] == 1, "a moved pin is another part"
