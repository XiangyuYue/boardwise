"""038N — the `footprint-library-sample` differential contract, Python half.

One case kind, one projection: the input is ``{schema, name, text}`` and both
runners derive the same ``boardwise.footprint-library/1`` document from ``text``.
This file pins the Python side of that document, and pins the rule the batch
exists for: the projection is a **view** of the reader the review path already
uses, not a second reading of the record stream.

The whole map comes from the real reader —
:func:`boardwise.parsers.schematic._collect_footprint_titles` — which walks
:func:`boardwise.parsers.epru_stream.iter_epru_records` itself and returns
``uuid -> META.title``. It is called with no :class:`ParseStats` and counts
nothing, so the projection has no counter either: "no conflict count" is the
reader's own shape, not an oversight of this batch.

The expected projection below is written out twice — here and as ``EXPECTED`` in
``rust/crates/boardwise-core/tests/footprint_library.rs``. The two literals are
the contract; a change on one side has to change both.

Everything here is synthetic: no real project content, no fixture file.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from boardwise.parsers import schematic
from tools import differential
from tools.contract_validate import ContractValidationError, assert_valid, load_path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "contracts" / "json" / "footprint-library-sample-v1.schema.json"
KIND = "footprint-library-sample"
SAMPLE_SCHEMA = "boardwise.footprint-library-sample/1"

#: The sample ``rust/crates/boardwise-core/tests/footprint_library.rs:SAMPLE``
#: projects. One line per shape that matters: a dropped ``SCH`` document and its
#: ``META``, a FOOTPRINT whose title is padded (and whose ``ATTR`` comes first, so
#: a non-``META`` record must neither become an entry nor block the first one), a
#: FOOTPRINT whose first title is blank and whose second must be blocked anyway, a
#: document with two ``META``s (the first wins), a FOOTPRINT with no uuid, a copy
#: that differs only in ``editVersion``/record order, a copy that states another
#: title (first wins), a ``META`` with no title key, a JSON ``null`` title, the
#: editor's literal ``"null"`` title (kept — this reader has no such exclusion),
#: and a FOOTPRINT document with no ``META`` at all.
SAMPLE = "\n".join([
    '{"type":"DOCHEAD","ticket":1}||{"docType":"SCH","uuid":"sch-1"}|',
    '{"type":"META","ticket":2}||{"title":"Board"}|',
    '{"type":"DOCHEAD","ticket":3}||{"docType":"FOOTPRINT","uuid":"fp-full","editVersion":"1"}|',
    '{"type":"ATTR","ticket":4}||{"key":"Footprint Name","value":"ignored"}|',
    '{"type":"META","ticket":5}||{"title":"  SMD-0402  ","attributes":{"Footprint Name":"whatever"}}|',
    '{"type":"DOCHEAD","ticket":6}||{"docType":"FOOTPRINT","uuid":"fp-empty-title"}|',
    '{"type":"META","ticket":7}||{"title":"   "}|',
    '{"type":"META","ticket":8}||{"title":"Blocked"}|',
    '{"type":"DOCHEAD","ticket":9}||{"docType":"FOOTPRINT","uuid":"fp-first-meta"}|',
    '{"type":"META","ticket":10}||{"title":"First"}|',
    '{"type":"META","ticket":11}||{"title":"Second"}|',
    '{"type":"DOCHEAD","ticket":12}||{"docType":"FOOTPRINT"}|',
    '{"type":"META","ticket":13}||{"title":"No-Uuid"}|',
    '{"type":"DOCHEAD","ticket":14}||{"docType":"FOOTPRINT","uuid":"fp-dup","editVersion":"1"}|',
    '{"type":"META","ticket":15}||{"title":"Same"}|',
    '{"type":"DOCHEAD","ticket":16}||{"docType":"FOOTPRINT","uuid":"fp-dup","editVersion":"2"}|',
    '{"type":"ATTR","ticket":17}||{"key":"Layer","value":"1"}|',
    '{"type":"META","ticket":18}||{"attributes":{"Pads":"2"},"title":"Same"}|',
    '{"type":"DOCHEAD","ticket":19}||{"docType":"FOOTPRINT","uuid":"fp-conflict"}|',
    '{"type":"META","ticket":20}||{"title":"First Wins"}|',
    '{"type":"DOCHEAD","ticket":21}||{"docType":"FOOTPRINT","uuid":"fp-conflict"}|',
    '{"type":"META","ticket":22}||{"title":"Second Loses"}|',
    '{"type":"DOCHEAD","ticket":23}||{"docType":"FOOTPRINT","uuid":"fp-bare"}|',
    '{"type":"META","ticket":24}||{"attributes":{"Pads":"4"}}|',
    '{"type":"DOCHEAD","ticket":25}||{"docType":"FOOTPRINT","uuid":"fp-null-title"}|',
    '{"type":"META","ticket":26}||{"title":null}|',
    '{"type":"DOCHEAD","ticket":27}||{"docType":"FOOTPRINT","uuid":"fp-literal-null"}|',
    '{"type":"META","ticket":28}||{"title":" null "}|',
    '{"type":"DOCHEAD","ticket":29}||{"docType":"FOOTPRINT","uuid":"fp-no-meta"}|',
    '{"type":"ATTR","ticket":30}||{"title":"Attr Title"}|',
])

#: The Rust half states this document as `EXPECTED`.
EXPECTED = {
    "schema": "boardwise.footprint-library/1",
    "footprints": {
        "fp-full": "SMD-0402",
        "fp-empty-title": "",
        "fp-first-meta": "First",
        "fp-dup": "Same",
        "fp-conflict": "First Wins",
        "fp-bare": "",
        "fp-null-title": "",
        "fp-literal-null": "null",
    },
}


def _project(text: str, name: str = "synthetic") -> dict:
    return differential.project_payload(
        KIND,
        {"schema": SAMPLE_SCHEMA, "name": name, "text": text},
    )


def test_the_projection_is_the_language_neutral_contract_document() -> None:
    """The exact document the Rust runner has to reproduce, key for key."""
    assert _project(SAMPLE) == EXPECTED


def test_a_document_that_is_not_a_footprint_is_skipped() -> None:
    """The ``SCH`` document at the top of the sample owns no footprint."""
    text = "\n".join([
        '{"type":"DOCHEAD"}||{"docType":"SCH","uuid":"sch-1"}|',
        '{"type":"META"}||{"title":"Board"}|',
        '{"type":"DOCHEAD"}||{"docType":"FOOTPRINT","uuid":"fp"}|',
        '{"type":"META"}||{"title":"QFN-32"}|',
    ])
    assert _project(text) == {
        "schema": "boardwise.footprint-library/1",
        "footprints": {"fp": "QFN-32"},
    }


def test_the_title_is_stripped_and_the_rest_of_the_meta_is_not_read() -> None:
    """``str((body or {}).get("title") or "").strip()`` — and nothing else."""
    assert _project(SAMPLE)["footprints"]["fp-full"] == "SMD-0402"
    text = "\n".join([
        '{"type":"DOCHEAD"}||{"docType":"FOOTPRINT","uuid":"fp"}|',
        '{"type":"META"}||{"title":"  QFN 32  ","attributes":{"Footprint Name":"other"},'
        '"editVersion":"9"}|',
    ])
    assert _project(text)["footprints"] == {"fp": "QFN 32"}


def test_the_first_meta_of_a_document_wins() -> None:
    text = "\n".join([
        '{"type":"DOCHEAD"}||{"docType":"FOOTPRINT","uuid":"fp"}|',
        '{"type":"META"}||{"title":"First"}|',
        '{"type":"META"}||{"title":"Second"}|',
    ])
    assert _project(text)["footprints"] == {"fp": "First"}


def test_an_empty_title_still_occupies_the_entry_and_blocks_the_next() -> None:
    """``""`` is a reading ("named nothing"), not an absence — so it is written
    under the uuid and the document's later ``META`` never gets in."""
    text = "\n".join([
        '{"type":"DOCHEAD"}||{"docType":"FOOTPRINT","uuid":"fp"}|',
        '{"type":"META"}||{"title":"   "}|',
        '{"type":"META"}||{"title":"Late Winner"}|',
    ])
    projection = _project(text)
    assert projection["footprints"] == {"fp": ""}
    assert "Late Winner" not in repr(projection)
    # The same shape inside the sample: a blank first title holds the entry.
    assert _project(SAMPLE)["footprints"]["fp-empty-title"] == ""


def test_a_footprint_without_a_uuid_is_no_footprint() -> None:
    text = "\n".join([
        '{"type":"DOCHEAD"}||{"docType":"FOOTPRINT"}|',
        '{"type":"META"}||{"title":"No uuid"}|',
        '{"type":"DOCHEAD"}||{"docType":"FOOTPRINT","uuid":"kept"}|',
        '{"type":"META"}||{"title":"Kept"}|',
    ])
    assert _project(text)["footprints"] == {"kept": "Kept"}


def test_a_record_that_is_not_a_meta_is_not_read() -> None:
    """An ``ATTR`` before the ``META`` neither becomes an entry nor blocks it, and
    a document with only ``ATTR`` records states no footprint at all."""
    text = "\n".join([
        '{"type":"DOCHEAD"}||{"docType":"FOOTPRINT","uuid":"fp-attr-first"}|',
        '{"type":"ATTR"}||{"title":"Attr Title"}|',
        '{"type":"META"}||{"title":"Real"}|',
        '{"type":"DOCHEAD"}||{"docType":"FOOTPRINT","uuid":"fp-no-meta"}|',
        '{"type":"ATTR"}||{"title":"Attr Only"}|',
    ])
    assert _project(text)["footprints"] == {"fp-attr-first": "Real"}


def test_a_repeated_uuid_is_first_wins_across_documents() -> None:
    """Two copies of one footprint: the second loses, and there is no counter to
    disagree about — the Python reader takes no ``ParseStats``."""
    text = "\n".join([
        '{"type":"DOCHEAD"}||{"docType":"FOOTPRINT","uuid":"fp","editVersion":"1"}|',
        '{"type":"META"}||{"title":"First Wins"}|',
        '{"type":"DOCHEAD"}||{"docType":"FOOTPRINT","uuid":"fp","editVersion":"2"}|',
        '{"type":"ATTR"}||{"key":"Layer","value":"1"}|',
        '{"type":"META"}||{"title":"Second Loses"}|',
    ])
    projection = _project(text)
    assert projection["footprints"] == {"fp": "First Wins"}
    assert set(projection) == {"schema", "footprints"}


def test_the_projection_states_no_counter_and_no_extra_field() -> None:
    """The reader has no stats: the document is the tag and the map, nothing else."""
    projection = _project(SAMPLE)
    assert set(projection) == {"schema", "footprints"}
    rendered = repr(projection)
    for absent in ("conflictingDocuments", "pinsDropped", "editVersion", "docType"):
        assert absent not in rendered


def test_the_projection_calls_the_existing_reader_and_returns_it_verbatim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One call, with ``payload["text"]`` as written, and the map it returns is
    the map that is emitted — the Rust side compares the same three keys."""
    # The name the runner holds is the reader itself, not a private copy of it.
    assert differential._collect_footprint_titles is schematic._collect_footprint_titles

    seen: list[str] = []

    def spy(text: str) -> dict[str, str]:
        seen.append(text)
        return {"synthetic": "kept", "blank": ""}

    monkeypatch.setattr(differential, "_collect_footprint_titles", spy)
    assert _project("A||B|") == {
        "schema": "boardwise.footprint-library/1",
        "footprints": {"synthetic": "kept", "blank": ""},
    }
    assert seen == ["A||B|"]


def test_the_sample_contract_requires_its_tag_a_name_and_the_text() -> None:
    schema = load_path(SCHEMA_PATH)
    good = {"schema": SAMPLE_SCHEMA, "name": "s", "text": SAMPLE}
    assert_valid(good, schema)

    refused = [
        {"schema": SAMPLE_SCHEMA, "name": "s"},
        {"schema": SAMPLE_SCHEMA, "text": SAMPLE},
        {"schema": SAMPLE_SCHEMA, "name": "", "text": SAMPLE},
        {"schema": "boardwise.footprint-library-sample/2", "name": "s", "text": SAMPLE},
        # A FOOTPRINT is addressed by its own uuid: the SYMBOL sample's key
        # selector is not part of this contract.
        {**good, "pinKey": "zIndex"},
        {**good, "extra": 1},
    ]
    for payload in refused:
        with pytest.raises(ContractValidationError):
            assert_valid(payload, schema)


def test_the_kind_is_the_ninth_kind_the_runner_gates() -> None:
    assert differential.SCHEMAS[KIND] == "footprint-library-sample-v1.schema.json"
    assert len(differential.SCHEMAS) == 10

# ------------------------------------------------------- the two published cases

CASES = ROOT / "contracts" / "differential" / "cases.json"
INPUTS = ROOT / "contracts" / "differential" / "inputs"
MANIFEST = ROOT / "contracts" / "differential" / "manifest.json"
FOOTPRINT_SOURCES = (
    ROOT / "contracts" / "differential" / "sources" / "footprint-library-samples.json"
)

V3_TITLE = "footprint-library-v3-title"
V4_COPIES = "footprint-library-v4-copies"

#: The eleven case rows published **before** this batch, in book order, with the
#: sha256 of the input bytes each one published then. The batch only adds: the two
#: DEVICE inputs are uncommitted working-tree files and are pinned here exactly
#: like the nine committed ones, so a regenerated byte cannot slip past unnoticed.
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
    "device-library-v3-meta": (
        "ee08146e8d070c54142f1df2936901d236243819e8b415d7ba167d02f7a4ecc1"
    ),
    "device-library-v4-copies": (
        "e77c0fb87068cde8163e700f387c7e516e74d8914136585e3ee6c8c52bd57992"
    ),
}


def _declared() -> dict[str, dict]:
    return {entry["caseId"]: entry for entry in load_path(FOOTPRINT_SOURCES)["samples"]}


def test_the_published_cases_are_the_declared_samples_and_their_projection() -> None:
    """Publish the declared stream, project the published file — the golden is the
    projection of the bytes on disk, not of the declaration it came from."""
    declared = _declared()
    assert sorted(declared) == [V3_TITLE, V4_COPIES]
    assert load_path(FOOTPRINT_SOURCES)["schema"] == "boardwise.footprint-library-samples/1"
    rows = {row["id"]: row for row in load_path(CASES)["cases"]}

    for case_id, entry in declared.items():
        published = load_path(INPUTS / entry["input"])
        # A FOOTPRINT sample states no pinKey and no projection: the stream alone.
        assert set(published) == {"schema", "name", "text"}
        assert published["schema"] == SAMPLE_SCHEMA
        assert published["name"] == entry["name"]
        assert published["text"] == entry["text"], "the input must publish the declared text"

        row = rows[case_id]
        assert row["kind"] == KIND
        assert row["input"] == f"contracts/differential/inputs/{entry['input']}"
        assert row["expected"] == _project(published["text"])
        assert differential.project_case(row, ROOT) == row["expected"]


def test_the_two_cases_are_appended_after_the_eleven_that_came_before() -> None:
    """A case book is keyed by id, and the batch only *adds*: the eleven earlier
    rows keep their order, their kind and their input bytes."""
    book = load_path(CASES)
    ids = [row["id"] for row in book["cases"]]
    assert ids[:11] == list(PRE_EXISTING)
    assert ids[11:13] == [V3_TITLE, V4_COPIES]
    assert len(ids) == len(set(ids)) == 15
    for row in book["cases"][:11]:
        published = INPUTS / row["input"].rsplit("/", 1)[-1]
        assert hashlib.sha256(published.read_bytes()).hexdigest() == PRE_EXISTING[row["id"]]


def test_the_manifest_pins_the_declared_source_and_the_two_inputs() -> None:
    """The published bytes are traceable: the declaration is a hashed source and
    both inputs are hashed under their repo-relative names."""
    manifest = load_path(MANIFEST)
    source = "contracts/differential/sources/footprint-library-samples.json"
    assert source in manifest["sources"]
    for name in ("footprint-library-v3-title.json", "footprint-library-v4-copies.json"):
        relative = f"contracts/differential/inputs/{name}"
        assert manifest["inputs"][relative] == hashlib.sha256(
            (INPUTS / name).read_bytes()
        ).hexdigest()
    assert "contracts/json/footprint-library-sample-v1.schema.json" in manifest["schemas"]


def test_the_v3_case_is_one_footprint_whose_first_meta_wins() -> None:
    """One FOOTPRINT: a padded title is trimmed, an ATTR carrying a title-like
    value is not read, and the second META states another title that never wins."""
    published = load_path(INPUTS / f"{V3_TITLE}.json")
    lines = published["text"].split("\n")
    assert sum(1 for line in lines if '"docType":"FOOTPRINT"' in line) == 1
    assert sum(1 for line in lines if '"type":"META"' in line) == 2
    assert sum(1 for line in lines if '"type":"ATTR"' in line) == 1
    # The ATTR comes before the first META, so "not read" is the thing proven.
    assert '"type":"ATTR"' in lines[1]

    projection = _project(published["text"])
    assert set(projection) == {"schema", "footprints"}
    assert projection["footprints"] == {"fp-v3-qfn32-synth": "QFN-32-5X5-SYNTH"}
    rendered = repr(projection)
    assert "SHOULD-NOT-WIN" not in rendered
    assert "ATTR-SHOULD-NOT-WIN" not in rendered


def test_the_v4_case_copies_one_uuid_and_a_blank_title_holds_its_entry() -> None:
    """V4 copies a used document: the second copy differs only in ``editVersion``
    and record order, the third states another title and loses to the first, and a
    second uuid states a blank title first so the entry is ``""`` and the later,
    non-empty title never gets in. There is no conflict counter to state either
    way — the reader this projection calls takes no ``ParseStats``."""
    published = load_path(INPUTS / f"{V4_COPIES}.json")
    lines = published["text"].split("\n")
    documents = [line for line in lines if '"docType":"FOOTPRINT"' in line]
    assert len(documents) == 5
    copied = [line for line in documents if '"uuid":"fp-v4-0402-synth"' in line]
    assert [line.split('"editVersion":"')[1].split('"')[0] for line in copied] == [
        "4.0.1",
        "4.0.2",
        "4.0.3",
    ]
    # The middle copy moved a record and reordered its META body; neither is read.
    assert any('"key":"Footprint Name"' in line for line in lines)

    projection = _project(published["text"])
    assert set(projection) == {"schema", "footprints"}
    assert projection["footprints"] == {
        "fp-v4-0402-synth": "RES-0402-SYNTH",
        "fp-v4-blank-synth": "",
    }
    rendered = repr(projection)
    assert "SHOULD-NOT-WIN-0402" not in rendered
    assert "LATE-TITLE-SHOULD-NOT-WIN" not in rendered
