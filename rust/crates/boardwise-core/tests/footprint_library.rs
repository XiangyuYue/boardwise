//! The `boardwise.footprint-library/1` projection, read the way
//! `boardwise/parsers/schematic.py::_collect_footprint_titles` reads it (038N).
//!
//! Every fixture is a synthetic `.epru` fragment: no real project content, no
//! fixture file. The expected document below is written out twice — here and as
//! `EXPECTED` in `tests/test_038n_footprint_differential.py`. The two literals are
//! the contract; a change on one side has to change both.

use boardwise_core::epru::iter_epru_records;
use boardwise_core::footprint::project_library;
use serde_json::Value;

/// The sample `tests/test_038n_footprint_differential.py:SAMPLE` projects.
///
/// One line per shape that matters: a dropped `SCH` document and its `META`, a
/// FOOTPRINT whose title is padded (and whose `ATTR` comes first, so a
/// non-`META` record must neither become an entry nor block the first one), a
/// FOOTPRINT whose first title is blank and whose second is blocked anyway, a
/// document with two `META`s (the first wins), a FOOTPRINT with no uuid, a copy
/// that differs only in `editVersion`/record order, a copy that states another
/// title (first wins), a `META` with no title key, a JSON `null` title, the
/// editor's literal `"null"` title (kept — this reader has no such exclusion), and
/// a FOOTPRINT document with no `META` at all.
const SAMPLE: &str = concat!(
    r#"{"type":"DOCHEAD","ticket":1}||{"docType":"SCH","uuid":"sch-1"}|"#,
    "\n",
    r#"{"type":"META","ticket":2}||{"title":"Board"}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":3}||{"docType":"FOOTPRINT","uuid":"fp-full","editVersion":"1"}|"#,
    "\n",
    r#"{"type":"ATTR","ticket":4}||{"key":"Footprint Name","value":"ignored"}|"#,
    "\n",
    r#"{"type":"META","ticket":5}||{"title":"  SMD-0402  ","attributes":{"Footprint Name":"whatever"}}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":6}||{"docType":"FOOTPRINT","uuid":"fp-empty-title"}|"#,
    "\n",
    r#"{"type":"META","ticket":7}||{"title":"   "}|"#,
    "\n",
    r#"{"type":"META","ticket":8}||{"title":"Blocked"}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":9}||{"docType":"FOOTPRINT","uuid":"fp-first-meta"}|"#,
    "\n",
    r#"{"type":"META","ticket":10}||{"title":"First"}|"#,
    "\n",
    r#"{"type":"META","ticket":11}||{"title":"Second"}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":12}||{"docType":"FOOTPRINT"}|"#,
    "\n",
    r#"{"type":"META","ticket":13}||{"title":"No-Uuid"}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":14}||{"docType":"FOOTPRINT","uuid":"fp-dup","editVersion":"1"}|"#,
    "\n",
    r#"{"type":"META","ticket":15}||{"title":"Same"}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":16}||{"docType":"FOOTPRINT","uuid":"fp-dup","editVersion":"2"}|"#,
    "\n",
    r#"{"type":"ATTR","ticket":17}||{"key":"Layer","value":"1"}|"#,
    "\n",
    r#"{"type":"META","ticket":18}||{"attributes":{"Pads":"2"},"title":"Same"}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":19}||{"docType":"FOOTPRINT","uuid":"fp-conflict"}|"#,
    "\n",
    r#"{"type":"META","ticket":20}||{"title":"First Wins"}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":21}||{"docType":"FOOTPRINT","uuid":"fp-conflict"}|"#,
    "\n",
    r#"{"type":"META","ticket":22}||{"title":"Second Loses"}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":23}||{"docType":"FOOTPRINT","uuid":"fp-bare"}|"#,
    "\n",
    r#"{"type":"META","ticket":24}||{"attributes":{"Pads":"4"}}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":25}||{"docType":"FOOTPRINT","uuid":"fp-null-title"}|"#,
    "\n",
    r#"{"type":"META","ticket":26}||{"title":null}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":27}||{"docType":"FOOTPRINT","uuid":"fp-literal-null"}|"#,
    "\n",
    r#"{"type":"META","ticket":28}||{"title":" null "}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":29}||{"docType":"FOOTPRINT","uuid":"fp-no-meta"}|"#,
    "\n",
    r#"{"type":"ATTR","ticket":30}||{"title":"Attr Title"}|"#,
);

/// The document `tests/test_038n_footprint_differential.py:EXPECTED` states.
const EXPECTED: &str = r#"{
  "schema": "boardwise.footprint-library/1",
  "footprints": {
    "fp-full": "SMD-0402",
    "fp-empty-title": "",
    "fp-first-meta": "First",
    "fp-dup": "Same",
    "fp-conflict": "First Wins",
    "fp-bare": "",
    "fp-null-title": "",
    "fp-literal-null": "null"
  }
}"#;

fn project(text: &str) -> Value {
    let records = iter_epru_records(text);
    let library = project_library(&records);
    serde_json::to_value(library).expect("the projection serializes")
}

fn expected(literal: &str) -> Value {
    serde_json::from_str(literal).expect("the expected literal is JSON")
}

#[test]
fn sample_matches_the_python_contract_literal() {
    assert_eq!(project(SAMPLE), expected(EXPECTED));
}

#[test]
fn a_document_that_is_not_a_footprint_is_skipped() {
    // The `SCH` document at the top of the sample states a `META`; it owns no
    // footprint and is not in the projection.
    let text = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"SCH","uuid":"sch-1"}|"#,
        "\n",
        r#"{"type":"META"}||{"title":"Board"}|"#,
        "\n",
        r#"{"type":"DOCHEAD"}||{"docType":"FOOTPRINT","uuid":"fp"}|"#,
        "\n",
        r#"{"type":"META"}||{"title":"QFN-32"}|"#,
    );
    assert_eq!(
        project(text),
        expected(r#"{"schema": "boardwise.footprint-library/1", "footprints": {"fp": "QFN-32"}}"#)
    );
}

#[test]
fn the_title_is_stripped_and_the_rest_of_the_meta_is_not_read() {
    assert_eq!(
        project(SAMPLE)["footprints"]["fp-full"],
        Value::from("SMD-0402")
    );
    let text = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"FOOTPRINT","uuid":"fp"}|"#,
        "\n",
        r#"{"type":"META"}||{"title":"  QFN 32  ","attributes":{"Footprint Name":"other"},"editVersion":"9"}|"#,
    );
    assert_eq!(project(text)["footprints"], expected(r#"{"fp": "QFN 32"}"#));
}

#[test]
fn the_first_meta_of_a_document_wins() {
    let text = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"FOOTPRINT","uuid":"fp"}|"#,
        "\n",
        r#"{"type":"META"}||{"title":"First"}|"#,
        "\n",
        r#"{"type":"META"}||{"title":"Second"}|"#,
    );
    assert_eq!(project(text)["footprints"], expected(r#"{"fp": "First"}"#));
}

#[test]
fn an_empty_title_still_occupies_the_entry_and_blocks_the_next() {
    // `""` is a reading ("named nothing"), not an absence: it is written under
    // the uuid, and the document's later `META` never gets in.
    let text = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"FOOTPRINT","uuid":"fp"}|"#,
        "\n",
        r#"{"type":"META"}||{"title":"   "}|"#,
        "\n",
        r#"{"type":"META"}||{"title":"Late Winner"}|"#,
    );
    let projection = project(text);
    assert_eq!(projection["footprints"], expected(r#"{"fp": ""}"#));
    assert!(!projection.to_string().contains("Late Winner"));
    assert_eq!(project(SAMPLE)["footprints"]["fp-empty-title"], "");
}

#[test]
fn a_footprint_without_a_uuid_is_no_footprint() {
    let text = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"FOOTPRINT"}|"#,
        "\n",
        r#"{"type":"META"}||{"title":"No uuid"}|"#,
        "\n",
        r#"{"type":"DOCHEAD"}||{"docType":"FOOTPRINT","uuid":"kept"}|"#,
        "\n",
        r#"{"type":"META"}||{"title":"Kept"}|"#,
    );
    assert_eq!(project(text)["footprints"], expected(r#"{"kept": "Kept"}"#));
}

#[test]
fn a_record_that_is_not_a_meta_is_not_read() {
    // An `ATTR` before the `META` neither becomes an entry nor blocks it, and a
    // document whose only record is an `ATTR` states no footprint at all.
    let text = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"FOOTPRINT","uuid":"fp-attr-first"}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"title":"Attr Title"}|"#,
        "\n",
        r#"{"type":"META"}||{"title":"Real"}|"#,
        "\n",
        r#"{"type":"DOCHEAD"}||{"docType":"FOOTPRINT","uuid":"fp-no-meta"}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"title":"Attr Only"}|"#,
    );
    assert_eq!(
        project(text)["footprints"],
        expected(r#"{"fp-attr-first": "Real"}"#)
    );
}

#[test]
fn a_repeated_uuid_is_first_wins_across_documents() {
    // Two copies of one footprint: the second loses, and there is no counter to
    // disagree about — the Python reader takes no `ParseStats`.
    let text = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"FOOTPRINT","uuid":"fp","editVersion":"1"}|"#,
        "\n",
        r#"{"type":"META"}||{"title":"First Wins"}|"#,
        "\n",
        r#"{"type":"DOCHEAD"}||{"docType":"FOOTPRINT","uuid":"fp","editVersion":"2"}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Layer","value":"1"}|"#,
        "\n",
        r#"{"type":"META"}||{"title":"Second Loses"}|"#,
    );
    let projection = project(text);
    assert_eq!(
        projection["footprints"],
        expected(r#"{"fp": "First Wins"}"#)
    );
    assert_eq!(
        projection.as_object().map(|fields| fields.len()),
        Some(2),
        "the document is the tag and the map, nothing else"
    );
}

#[test]
fn the_projection_states_no_counter_and_no_extra_field() {
    let projection = project(SAMPLE);
    let fields = projection.as_object().expect("an object");
    assert_eq!(fields.len(), 2, "the tag and the map, nothing else");
    assert!(fields.contains_key("schema"));
    assert!(fields.contains_key("footprints"));
    let rendered = projection.to_string();
    for absent in [
        "conflictingDocuments",
        "pinsDropped",
        "editVersion",
        "docType",
    ] {
        assert!(!rendered.contains(absent), "{absent} must not be projected");
    }
}
