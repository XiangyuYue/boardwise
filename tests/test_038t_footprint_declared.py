"""038T — the `footprint-declared-sample` differential contract, Python half.

One case kind, one projection: the input is ``{schema, name, text, value}`` and both
runners derive the same ``boardwise.footprint-declared/1`` document from it. This
file pins the Python side, and pins the rule the batch exists for: the projection is
a **view** of the two readers the model path already uses —
:func:`boardwise.parsers.schematic._collect_footprint_titles` for the archive's
``uuid -> title`` table and
:func:`boardwise.parsers.schematic._resolve_declared_footprint` for what the field
declares — not a second reading of either.

``value`` is the field verbatim and may be empty: the contract states it, so there
is no default spelling for an absent field, and the projection has no branch name
either — ``""`` as ``libraryId`` is how "not resolved" is spelled.

The sample, its field value and the expected document below are written out twice —
here and as ``SAMPLE``/``SAMPLE_VALUE``/``EXPECTED`` in
``rust/crates/boardwise-core/tests/footprint_declared.rs``. The two literals are the
contract; a change on one side has to change both.

Everything here is synthetic: no real project content, no fixture file.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from boardwise.parsers import schematic
from boardwise.rules.pcb.footprint import LIBRARY_ID_RE
from tools import differential
from tools.contract_validate import ContractValidationError, assert_valid, load_path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "contracts" / "json" / "footprint-declared-sample-v1.schema.json"
KIND = "footprint-declared-sample"
SAMPLE_SCHEMA = "boardwise.footprint-declared-sample/1"
DECLARED_SCHEMA = "boardwise.footprint-declared/1"

#: The sample ``rust/crates/boardwise-core/tests/footprint_declared.rs:SAMPLE``
#: projects. One document per shape that matters: a ``SCH`` document whose
#: ``META`` must not become a title, a 16-digit id whose title is padded (the
#: resolved case), a 32-digit id, a two-segment id (a screw footprint), an id whose
#: title is blank (the archive names it nothing) and an id whose title is the
#: editor's literal ``"null"`` — non-empty, so it *is* a name this reader keeps.
SAMPLE = "\n".join([
    '{"type":"DOCHEAD","ticket":1}||{"docType":"SCH","uuid":"sch-1"}|',
    '{"type":"META","ticket":2}||{"title":"Board"}|',
    '{"type":"DOCHEAD","ticket":3}||{"docType":"FOOTPRINT","uuid":"0733d61b8033ac9c","editVersion":"1"}|',
    '{"type":"META","ticket":4}||{"title":"  CAP-SMD_L8.0-W6.0-LS11.4  "}|',
    '{"type":"DOCHEAD","ticket":5}||{"docType":"FOOTPRINT","uuid":"c4dc0f6ef1616584702a893414cd16c7"}|',
    '{"type":"META","ticket":6}||{"title":"PWR-QFN-32-SYNTH"}|',
    '{"type":"DOCHEAD","ticket":7}||{"docType":"FOOTPRINT","uuid":"308cffdb9f930ec1_c4dc0f6ef1616584702a893414cd16c7"}|',
    '{"type":"META","ticket":8}||{"title":"SCREW-M3-SYNTH"}|',
    '{"type":"DOCHEAD","ticket":9}||{"docType":"FOOTPRINT","uuid":"aabbccddeeff0011"}|',
    '{"type":"META","ticket":10}||{"title":"   "}|',
    '{"type":"DOCHEAD","ticket":11}||{"docType":"FOOTPRINT","uuid":"0123456789abcdef"}|',
    '{"type":"META","ticket":12}||{"title":" null "}|',
])

#: The field value the Rust half states as `SAMPLE_VALUE`: the 16-digit id above,
#: padded — the one branch that resolves.
SAMPLE_VALUE = " 0733d61b8033ac9c "

#: The Rust half states this document as `EXPECTED`.
EXPECTED = {
    "schema": DECLARED_SCHEMA,
    "footprint": "CAP-SMD_L8.0-W6.0-LS11.4",
    "libraryId": "0733d61b8033ac9c",
}

#: The matcher corpus the Rust half states as `ID_CORPUS`: every shape either side
#: of the boundary, so the hand-written Rust matcher and the two Python regexes
#: cannot drift apart unnoticed.
ID_CORPUS = [
    "0733d61b8033ac9c",
    "0733D61B8033AC9C",
    "c4dc0f6ef1616584702a893414cd16c7",
    "308cffdb9f930ec1_c4dc0f6ef1616584702a893414cd16c7",
    "0733d61b8033ac9c_0733d61b8033ac9c_0733d61b8033ac9c",
    "c4dc0f6ef1616584702a893414cd16c7_c4dc0f6ef1616584702a893414cd16c7_c4dc0f6ef1616584702a893414cd16c7",
    "0733d61b8033ac9",
    "0733d61b8033ac9cz",
    "0733d61b8033ac9c_",
    "_0733d61b8033ac9c",
    "0733d61b8033ac9c__c4dc0f6ef1616584702a893414cd16c7",
    "ｃ4dc0f6ef1616584702a893414cd16c7",
    "CAP-SMD_L8.0-W6.0-LS11.4",
    "0603",
    "",
    " ",
    "null",
]


def _project(text: str, value: str = SAMPLE_VALUE, name: str = "synthetic") -> dict:
    return differential.project_payload(
        KIND,
        {"schema": SAMPLE_SCHEMA, "name": name, "text": text, "value": value},
    )


def _resolved(value: str) -> tuple[str, str]:
    projection = _project(SAMPLE, value)
    return projection["footprint"], projection["libraryId"]


def test_the_projection_is_the_language_neutral_contract_document() -> None:
    """The exact document the Rust runner has to reproduce, key for key."""
    assert _project(SAMPLE) == EXPECTED


def test_a_plain_name_is_trimmed_and_stays_unresolved() -> None:
    """A name is not an id: it comes back trimmed, with no library id beside it."""
    assert _resolved("  CAP-SMD_L8.0-W6.0-LS11.4  ") == (
        "CAP-SMD_L8.0-W6.0-LS11.4", "",
    )
    assert _resolved("0603") == ("0603", "")


def test_an_empty_field_states_nothing() -> None:
    """``""`` is a value the contract states, and it resolves to nothing at all."""
    assert _resolved("") == ("", "")
    assert _resolved("   ") == ("", "")
    assert _resolved("\t\n ") == ("", "")


def test_ids_of_every_allowed_shape_resolve_to_the_title_the_archive_states() -> None:
    """16 digits, 32 digits and ``_``-joined segments are one shape, and the title
    is the document's first ``META`` title, trimmed."""
    assert _resolved("c4dc0f6ef1616584702a893414cd16c7") == (
        "PWR-QFN-32-SYNTH", "c4dc0f6ef1616584702a893414cd16c7",
    )
    assert _resolved(" 308cffdb9f930ec1_c4dc0f6ef1616584702a893414cd16c7 ") == (
        "SCREW-M3-SYNTH", "308cffdb9f930ec1_c4dc0f6ef1616584702a893414cd16c7",
    )


def test_uppercase_hex_is_legal_and_the_title_table_still_matches_exact_case() -> None:
    """``[0-9a-fA-F]`` accepts both cases; the archive keys its table by the uuid as
    written, so this is a legal id that names nothing — not an illegal one."""
    assert schematic.FOOTPRINT_ID_RE.match("C4DC0F6EF1616584702A893414CD16C7")
    assert _resolved("C4DC0F6EF1616584702A893414CD16C7") == (
        "C4DC0F6EF1616584702A893414CD16C7", "",
    )


def test_an_id_the_archive_does_not_name_stays_an_id() -> None:
    """"Not resolvable" must not be readable as "resolved to nothing"."""
    assert _resolved("deadbeefdeadbeef") == ("deadbeefdeadbeef", "")


def test_a_hit_on_a_blank_title_resolves_to_nothing() -> None:
    """The archive says "this footprint is named nothing": a reading, not a name."""
    assert _resolved("aabbccddeeff0011") == ("aabbccddeeff0011", "")


def test_the_literal_null_title_is_a_name_this_reader_keeps() -> None:
    """Only the DEVICE attributes have a ``"null"`` exclusion; this reader has none,
    and adding one here would be a second reading."""
    assert _resolved("0123456789abcdef") == ("null", "0123456789abcdef")


def test_the_document_states_the_tag_the_footprint_and_the_raw_id_only() -> None:
    projection = _project(SAMPLE)
    assert set(projection) == {"schema", "footprint", "libraryId"}
    assert projection["schema"] == DECLARED_SCHEMA
    rendered = repr(projection)
    for absent in ("titles", "resolved", "docType", "editVersion"):
        assert absent not in rendered


def test_the_matcher_agrees_with_the_rule_the_repository_already_uses() -> None:
    """One vocabulary: the parser's regex, the rule's regex, and the corpus the
    Rust matcher is pinned to. A drift in either direction shows up here."""
    for sample in ID_CORPUS:
        parser_says = bool(schematic.FOOTPRINT_ID_RE.match(sample))
        assert parser_says == bool(LIBRARY_ID_RE.match(sample)), sample
    # The decision the resolution makes on the same corpus: an id-shaped value is
    # looked up (so ``libraryId`` is either the id or ``""``), anything else is not.
    titles = {"0733d61b8033ac9c": "CAP", "null": "N"}
    for sample in ID_CORPUS:
        footprint, library_id = schematic._resolve_declared_footprint(sample, titles)
        if bool(schematic.FOOTPRINT_ID_RE.match(sample)):
            assert library_id in (sample, "")
        else:
            assert library_id == "" and footprint == sample.strip()


def test_the_projection_calls_both_readers_and_returns_what_they_say(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two calls, in the order the model path makes them, with the payload as
    written — and the pair the resolver returns is what is emitted."""
    assert differential._collect_footprint_titles is schematic._collect_footprint_titles
    assert differential._resolve_declared_footprint is schematic._resolve_declared_footprint

    seen: list[tuple] = []

    def titles_spy(text: str) -> dict[str, str]:
        seen.append(("titles", text))
        return {"synthetic": "kept"}

    def resolve_spy(value: str, titles: dict[str, str]) -> tuple[str, str]:
        seen.append(("resolve", value, dict(titles)))
        return "spy-name", "spy-id"

    monkeypatch.setattr(differential, "_collect_footprint_titles", titles_spy)
    monkeypatch.setattr(differential, "_resolve_declared_footprint", resolve_spy)
    assert _project("A||B|", "raw-value") == {
        "schema": DECLARED_SCHEMA,
        "footprint": "spy-name",
        "libraryId": "spy-id",
    }
    assert seen == [
        ("titles", "A||B|"),
        ("resolve", "raw-value", {"synthetic": "kept"}),
    ]


def test_the_sample_contract_requires_its_tag_a_name_the_text_and_the_value() -> None:
    schema = load_path(SCHEMA_PATH)
    good = {"schema": SAMPLE_SCHEMA, "name": "s", "text": SAMPLE, "value": SAMPLE_VALUE}
    assert_valid(good, schema)
    # An empty field is a stated value, not a missing one.
    assert_valid({**good, "value": ""}, schema)

    refused = [
        {"schema": SAMPLE_SCHEMA, "name": "s", "text": SAMPLE},
        {"schema": SAMPLE_SCHEMA, "name": "s", "value": SAMPLE_VALUE},
        {"schema": SAMPLE_SCHEMA, "text": SAMPLE, "value": SAMPLE_VALUE},
        {"schema": SAMPLE_SCHEMA, "name": "", "text": SAMPLE, "value": ""},
        {"schema": "boardwise.footprint-declared-sample/2", **{k: v for k, v in good.items() if k != "schema"}},
        # The field is a string; a number is not a spelling of it.
        {**good, "value": 7},
        # Nor is the library sample's key set part of this contract.
        {**good, "pinKey": "zIndex"},
        {**good, "extra": 1},
    ]
    for payload in refused:
        with pytest.raises(ContractValidationError):
            assert_valid(payload, schema)


def test_the_kind_is_the_tenth_kind_the_runner_gates() -> None:
    assert differential.SCHEMAS[KIND] == "footprint-declared-sample-v1.schema.json"
    assert len(differential.SCHEMAS) == 10


# ------------------------------------------------------- the two published cases

CASES = ROOT / "contracts" / "differential" / "cases.json"
INPUTS = ROOT / "contracts" / "differential" / "inputs"
MANIFEST = ROOT / "contracts" / "differential" / "manifest.json"
DECLARED_SOURCES = (
    ROOT / "contracts" / "differential" / "sources" / "footprint-declared-samples.json"
)

V3_HIT = "footprint-declared-v3-hit"
V4_EMPTY = "footprint-declared-v4-empty"

#: The thirteen case rows published **before** this batch, in book order, with the
#: sha256 of the input bytes each one published then. The batch only adds: the
#: four uncommitted working-tree inputs are pinned exactly like the nine committed
#: ones, so a regenerated byte cannot slip past unnoticed.
PRE_EXISTING = {
    "review-report-projection": (
        "2b2a021e6ccb87d101b9c63709067342a25ec1cd54bd5579ccd0d5148e6585d3"
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
    "footprint-library-v3-title": (
        "5048efbb96d84a4278f674bdc62b43a5142d62a8baa42798b6c78ed979a0d09b"
    ),
    "footprint-library-v4-copies": (
        "d754361b7d4e50a74770b45fcef775d43a3c6cffeaa235999633f6e38802e8d2"
    ),
}


def _declared() -> dict[str, dict]:
    return {entry["caseId"]: entry for entry in load_path(DECLARED_SOURCES)["samples"]}


def test_the_published_cases_are_the_declared_samples_and_their_projection() -> None:
    """Publish the declared pair, project the published file: the golden is the
    projection of the bytes on disk, not of the declaration they came from."""
    declared = _declared()
    assert sorted(declared) == [V3_HIT, V4_EMPTY]
    assert load_path(DECLARED_SOURCES)["schema"] == "boardwise.footprint-declared-samples/1"
    rows = {row["id"]: row for row in load_path(CASES)["cases"]}

    for case_id, entry in declared.items():
        published = load_path(INPUTS / entry["input"])
        # Four keys: the stream and the field it is read against.
        assert set(published) == {"schema", "name", "text", "value"}
        assert published["schema"] == SAMPLE_SCHEMA
        assert published["name"] == entry["name"]
        assert published["text"] == entry["text"], "the input must publish the declared text"
        assert published["value"] == entry["value"], "the input must publish the declared field"

        row = rows[case_id]
        assert row["kind"] == KIND
        assert row["input"] == f"contracts/differential/inputs/{entry['input']}"
        assert row["expected"] == _project(published["text"], published["value"])
        assert differential.project_case(row, ROOT) == row["expected"]


def test_the_two_cases_are_appended_after_the_thirteen_that_came_before() -> None:
    """A case book is keyed by id, and the batch only *adds*: the thirteen earlier
    rows keep their order, their kind and their input bytes."""
    book = load_path(CASES)
    ids = [row["id"] for row in book["cases"]]
    assert ids[:13] == list(PRE_EXISTING)
    assert ids[13:] == [V3_HIT, V4_EMPTY]
    assert len(ids) == len(set(ids)) == 15
    for row in book["cases"][:13]:
        published = INPUTS / row["input"].rsplit("/", 1)[-1]
        assert hashlib.sha256(published.read_bytes()).hexdigest() == PRE_EXISTING[row["id"]]


def test_the_manifest_pins_the_declared_source_and_the_two_inputs() -> None:
    """The published bytes are traceable: the declaration is a hashed source, both
    inputs are hashed under their repo-relative names, and the schema is too."""
    manifest = load_path(MANIFEST)
    assert "contracts/differential/sources/footprint-declared-samples.json" in manifest["sources"]
    for name in ("footprint-declared-v3-hit.json", "footprint-declared-v4-empty.json"):
        relative = f"contracts/differential/inputs/{name}"
        assert manifest["inputs"][relative] == hashlib.sha256(
            (INPUTS / name).read_bytes()
        ).hexdigest()
    assert "contracts/json/footprint-declared-sample-v1.schema.json" in manifest["schemas"]


def test_the_v3_case_is_one_footprint_named_by_the_id_its_field_states() -> None:
    """One FOOTPRINT: a padded title is trimmed, the value is that document's uuid,
    and the golden is the title plus the raw id — the only resolved shape."""
    published = load_path(INPUTS / f"{V3_HIT}.json")
    lines = published["text"].split("\n")
    assert sum(1 for line in lines if '"docType":"FOOTPRINT"' in line) == 1
    assert sum(1 for line in lines if '"type":"META"' in line) == 1
    assert '"title":"  CAP-SMD_L8.0-W6.0-LS11.4  "' in lines[1]
    assert published["value"] == "0a1b2c3d4e5f6071"
    assert '"uuid":"0a1b2c3d4e5f6071"' in lines[0]

    projection = _project(published["text"], published["value"])
    assert projection == {
        "schema": DECLARED_SCHEMA,
        "footprint": "CAP-SMD_L8.0-W6.0-LS11.4",
        "libraryId": "0a1b2c3d4e5f6071",
    }


def test_the_v4_case_copies_one_uuid_and_a_blank_first_title_names_nothing() -> None:
    """V4 copies a used document: the first copy's title is blank, so the archive
    names the footprint nothing and the golden is the raw id with an empty library
    id — the later copies' titles do not fill in an entry that is already there."""
    published = load_path(INPUTS / f"{V4_EMPTY}.json")
    lines = published["text"].split("\n")
    documents = [line for line in lines if '"docType":"FOOTPRINT"' in line]
    assert len(documents) == 3
    assert [line.split('"editVersion":"')[1].split('"')[0] for line in documents] == [
        "4.0.1",
        "4.0.2",
        "4.0.3",
    ]
    assert all('"uuid":"9c8b7a6f5e4d3c2b"' in line for line in documents)
    # The first title is blank and the later copies do state titles.
    assert '"title":"   "' in lines[1]
    assert 'PWR-DFN-8-SYNTH' in published["text"]
    assert 'LATE-SHOULD-NOT-WIN' in published["text"]

    projection = _project(published["text"], published["value"])
    assert projection == {
        "schema": DECLARED_SCHEMA,
        "footprint": "9c8b7a6f5e4d3c2b",
        "libraryId": "",
    }
    assert "PWR-DFN-8-SYNTH" not in repr(projection)
