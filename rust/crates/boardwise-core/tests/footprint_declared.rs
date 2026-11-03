//! The `boardwise.footprint-declared/1` projection — what one declared
//! `Footprint` field says, read the way
//! `boardwise/parsers/schematic.py::_resolve_declared_footprint` reads it (038T).
//!
//! Every fixture is a synthetic `.epru` fragment: no real project content, no
//! fixture file. The sample, its field value and the expected document below are
//! written out twice — here and as `SAMPLE`/`SAMPLE_VALUE`/`EXPECTED` in
//! `tests/test_038t_footprint_declared.py`. The two literals are the contract; a
//! change on one side has to change both.

use boardwise_core::epru::iter_epru_records;
use boardwise_core::footprint::{is_library_id, project_declared, project_library};
use serde_json::Value;

/// The sample `tests/test_038t_footprint_declared.py:SAMPLE` projects.
///
/// One document per shape that matters: a `SCH` document whose `META` must not
/// become a title, a 16-digit id whose title is padded (that is the resolved
/// case), a 32-digit id, a two-segment id (a screw footprint), an id whose title
/// is blank (the archive names it nothing), and an id whose title is the editor's
/// literal `"null"` — non-empty, so it *is* a name this reader keeps.
const SAMPLE: &str = concat!(
    r#"{"type":"DOCHEAD","ticket":1}||{"docType":"SCH","uuid":"sch-1"}|"#,
    "\n",
    r#"{"type":"META","ticket":2}||{"title":"Board"}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":3}||{"docType":"FOOTPRINT","uuid":"0733d61b8033ac9c","editVersion":"1"}|"#,
    "\n",
    r#"{"type":"META","ticket":4}||{"title":"  CAP-SMD_L8.0-W6.0-LS11.4  "}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":5}||{"docType":"FOOTPRINT","uuid":"c4dc0f6ef1616584702a893414cd16c7"}|"#,
    "\n",
    r#"{"type":"META","ticket":6}||{"title":"PWR-QFN-32-SYNTH"}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":7}||{"docType":"FOOTPRINT","uuid":"308cffdb9f930ec1_c4dc0f6ef1616584702a893414cd16c7"}|"#,
    "\n",
    r#"{"type":"META","ticket":8}||{"title":"SCREW-M3-SYNTH"}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":9}||{"docType":"FOOTPRINT","uuid":"aabbccddeeff0011"}|"#,
    "\n",
    r#"{"type":"META","ticket":10}||{"title":"   "}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":11}||{"docType":"FOOTPRINT","uuid":"0123456789abcdef"}|"#,
    "\n",
    r#"{"type":"META","ticket":12}||{"title":" null "}|"#,
);

/// The field value `tests/test_038t_footprint_declared.py:SAMPLE_VALUE` states:
/// the 16-digit id above, padded — the one branch that resolves.
const SAMPLE_VALUE: &str = " 0733d61b8033ac9c ";

/// The document `tests/test_038t_footprint_declared.py:EXPECTED` states.
const EXPECTED: &str = r#"{
  "schema": "boardwise.footprint-declared/1",
  "footprint": "CAP-SMD_L8.0-W6.0-LS11.4",
  "libraryId": "0733d61b8033ac9c"
}"#;

/// The matcher corpus `tests/test_038t_footprint_declared.py:ID_CORPUS` states:
/// every shape either side of the boundary, so the hand-written matcher and the
/// two Python regexes cannot drift apart unnoticed.
const ID_CORPUS: [&str; 17] = [
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
];

fn project(value: &str) -> Value {
    let records = iter_epru_records(SAMPLE);
    let declared = project_declared(&records, value);
    serde_json::to_value(declared).expect("the projection serializes")
}

fn expected(literal: &str) -> Value {
    serde_json::from_str(literal).expect("the expected literal is JSON")
}

fn resolved(value: &str) -> (String, String) {
    match project(value) {
        Value::Object(fields) => (
            fields["footprint"].as_str().expect("a string").to_owned(),
            fields["libraryId"].as_str().expect("a string").to_owned(),
        ),
        other => panic!("the projection is an object, not {other:?}"),
    }
}

#[test]
fn sample_matches_the_python_contract_literal() {
    assert_eq!(project(SAMPLE_VALUE), expected(EXPECTED));
}

#[test]
fn a_plain_name_is_trimmed_and_stays_unresolved() {
    // The field holds a name: it comes back trimmed and without a library id, so
    // a caller cannot mistake "not an id" for "an id that did not resolve".
    assert_eq!(
        resolved("  CAP-SMD_L8.0-W6.0-LS11.4  "),
        ("CAP-SMD_L8.0-W6.0-LS11.4".to_owned(), String::new())
    );
    assert_eq!(resolved("0603"), ("0603".to_owned(), String::new()));
}

#[test]
fn an_empty_field_states_nothing() {
    assert_eq!(resolved(""), (String::new(), String::new()));
    assert_eq!(resolved("   "), (String::new(), String::new()));
    assert_eq!(resolved("\t\n "), (String::new(), String::new()));
}

#[test]
fn ids_of_every_allowed_shape_resolve_to_the_title_the_archive_states() {
    // 16 digits, 32 digits and two `_`-joined segments are all one shape; the
    // title is the document's first `META`, trimmed.
    assert_eq!(
        resolved("c4dc0f6ef1616584702a893414cd16c7"),
        (
            "PWR-QFN-32-SYNTH".to_owned(),
            "c4dc0f6ef1616584702a893414cd16c7".to_owned()
        )
    );
    assert_eq!(
        resolved(" 308cffdb9f930ec1_c4dc0f6ef1616584702a893414cd16c7 "),
        (
            "SCREW-M3-SYNTH".to_owned(),
            "308cffdb9f930ec1_c4dc0f6ef1616584702a893414cd16c7".to_owned()
        )
    );
}

#[test]
fn uppercase_hex_is_legal_and_the_title_table_still_matches_exact_case() {
    // `A-F` is accepted by the *shape* (Python's `[0-9a-fA-F]` accepts both
    // cases), and the archive keys its table by the uuid as written — so this is
    // a legal id that names nothing, not an illegal one.
    assert!(is_library_id("C4DC0F6EF1616584702A893414CD16C7"));
    assert_eq!(
        resolved("C4DC0F6EF1616584702A893414CD16C7"),
        ("C4DC0F6EF1616584702A893414CD16C7".to_owned(), String::new())
    );
}

#[test]
fn an_id_the_archive_does_not_name_stays_an_id() {
    assert_eq!(
        resolved("deadbeefdeadbeef"),
        ("deadbeefdeadbeef".to_owned(), String::new())
    );
}

#[test]
fn a_hit_on_a_blank_title_resolves_to_nothing() {
    // The archive says "this footprint is named nothing". That is a reading, and
    // it is not a name: the field stays the id with no library id beside it.
    assert_eq!(
        resolved("aabbccddeeff0011"),
        ("aabbccddeeff0011".to_owned(), String::new())
    );
}

#[test]
fn the_literal_null_title_is_a_name_this_reader_keeps() {
    // Only the DEVICE attributes have a `"null"` exclusion; the footprint title
    // reader has none, and adding one here would be a second reading.
    assert_eq!(
        resolved("0123456789abcdef"),
        ("null".to_owned(), "0123456789abcdef".to_owned())
    );
}

#[test]
fn the_document_states_the_tag_the_footprint_and_the_raw_id_only() {
    let projection = project(SAMPLE_VALUE);
    let fields = projection.as_object().expect("an object");
    assert_eq!(fields.len(), 3, "three keys, nothing else");
    assert_eq!(projection["schema"], "boardwise.footprint-declared/1");
    assert!(fields.contains_key("footprint"));
    assert!(fields.contains_key("libraryId"));
    let rendered = projection.to_string();
    for absent in ["titles", "resolved", "docType", "editVersion"] {
        assert!(!rendered.contains(absent), "{absent} must not be projected");
    }
}

#[test]
fn the_matcher_refuses_every_shape_just_outside_the_rule() {
    for sample in ID_CORPUS {
        let expected = matches!(
            sample,
            "0733d61b8033ac9c"
                | "0733D61B8033AC9C"
                | "c4dc0f6ef1616584702a893414cd16c7"
                | "308cffdb9f930ec1_c4dc0f6ef1616584702a893414cd16c7"
                | "0733d61b8033ac9c_0733d61b8033ac9c_0733d61b8033ac9c"
                | "c4dc0f6ef1616584702a893414cd16c7_c4dc0f6ef1616584702a893414cd16c7_c4dc0f6ef1616584702a893414cd16c7"
        );
        assert_eq!(is_library_id(sample), expected, "{sample:?}");
    }
}

#[test]
fn the_resolution_reads_the_table_the_library_projection_publishes() {
    // One table, read once: the ids this resolution can hit are exactly the keys
    // `project_library` publishes, so the two arms of the differential cannot
    // disagree about what the archive names.
    let records = iter_epru_records(SAMPLE);
    let titles = project_library(&records).footprints;
    assert_eq!(
        titles.keys().cloned().collect::<Vec<_>>(),
        vec![
            "0123456789abcdef",
            "0733d61b8033ac9c",
            "308cffdb9f930ec1_c4dc0f6ef1616584702a893414cd16c7",
            "aabbccddeeff0011",
            "c4dc0f6ef1616584702a893414cd16c7",
        ]
    );
    for id in titles.keys() {
        let (footprint, library_id) = resolved(id);
        let title = &titles[id];
        if title.is_empty() {
            // "Named nothing" is a reading, not a name: the id stays unpaired.
            assert_eq!(&footprint, id, "a blank title leaves the id");
            assert_eq!(library_id, "", "{id}");
        } else {
            assert_eq!(&footprint, title, "{id}");
            assert_eq!(&library_id, id, "a named id keeps its raw spelling");
        }
    }
}
