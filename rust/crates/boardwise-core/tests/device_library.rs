//! The `boardwise.device-library/1` projection, read the way
//! `boardwise/parsers/schematic.py::_collect_device_meta` reads it (038M).
//!
//! Every fixture is a synthetic `.epru` fragment: no real project content, no
//! fixture file. The expected document below is written out twice — here and as
//! `EXPECTED` in `tests/test_038m_device_differential.py`. The two literals are
//! the contract; a change on one side has to change both.

use boardwise_core::device::project_library;
use boardwise_core::epru::iter_epru_records;
use serde_json::Value;

/// The sample `tests/test_038m_device_differential.py:SAMPLE` projects.
///
/// One line per shape that matters: a `SCH` document whose `META` must not be
/// read, a DEVICE with every declared field (padded with whitespace), a DEVICE
/// whose attributes are all empty or the editor's `"null"`, a document with two
/// `META`s (the first wins), a DEVICE with no uuid, a copy that differs only in
/// `editVersion`/record order (not a conflict), a copy that differs in what the
/// model reads (first wins, counted), a device with no `Designator`, a `truthy`
/// non-object `attributes`, a **falsy** non-object `attributes` (the empty array
/// — Python's `or {}` makes it the empty object), and a `META` with no
/// attributes at all.
const SAMPLE: &str = concat!(
    r#"{"type":"DOCHEAD","ticket":1}||{"docType":"SCH","uuid":"sch-1"}|"#,
    "\n",
    r#"{"type":"META","ticket":2}||{"title":"Board","attributes":{"Designator":"A?"}}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":3}||{"docType":"DEVICE","uuid":"dev-full","editVersion":"1"}|"#,
    "\n",
    r#"{"type":"META","ticket":4}||{"title":"  USB-C Receptacle  ","attributes":{"Supplier Part":" C12345 ","Manufacturer Part":"MPN-1","Manufacturer":"ACME Corp","Datasheet":" https://example.invalid/usb-c.pdf ","Supplier Footprint":"0805","Name":"{{Value}}","Symbol":" sym-1 ","Type":" Connector ","LCSC Part Name":"Type-C 16P","Designator":" J? "}}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":5}||{"docType":"DEVICE","uuid":"dev-empty"}|"#,
    "\n",
    r#"{"type":"META","ticket":6}||{"title":"   ","attributes":{"Supplier Part":"","Manufacturer Part":"null","Manufacturer":null,"Datasheet":"  ","Name":" null ","Symbol":"null","Type":"null","Designator":"   "}}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":7}||{"docType":"DEVICE","uuid":"dev-first-meta"}|"#,
    "\n",
    r#"{"type":"META","ticket":8}||{"title":"First","attributes":{"Designator":"R?"}}|"#,
    "\n",
    r#"{"type":"META","ticket":9}||{"title":"Second","attributes":{"Designator":"C?"}}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":10}||{"docType":"DEVICE"}|"#,
    "\n",
    r#"{"type":"META","ticket":11}||{"title":"No-Uuid","attributes":{"Designator":"U?"}}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":12}||{"docType":"DEVICE","uuid":"dev-same","editVersion":"1"}|"#,
    "\n",
    r#"{"type":"META","ticket":13}||{"title":"Same","attributes":{"Supplier Part":"C1","Designator":"D?"}}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":14}||{"docType":"DEVICE","uuid":"dev-same","editVersion":"2"}|"#,
    "\n",
    r#"{"type":"ATTR","ticket":15}||{"key":"Convert to PCB","value":"1"}|"#,
    "\n",
    r#"{"type":"META","ticket":16}||{"attributes":{"Designator":"D?","Supplier Part":"C1"},"title":"Same"}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":17}||{"docType":"DEVICE","uuid":"dev-conflict","editVersion":"1"}|"#,
    "\n",
    r#"{"type":"META","ticket":18}||{"title":"First Wins","attributes":{"Designator":"R?","Supplier Part":"C100"}}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":19}||{"docType":"DEVICE","uuid":"dev-conflict","editVersion":"2"}|"#,
    "\n",
    r#"{"type":"META","ticket":20}||{"title":"Second Loses","attributes":{"Designator":"R?","Supplier Part":"C200"}}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":21}||{"docType":"DEVICE","uuid":"dev-no-designator"}|"#,
    "\n",
    r#"{"type":"META","ticket":22}||{"title":"GND","attributes":{"Symbol":"sym-pwr","Name":"GND"}}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":23}||{"docType":"DEVICE","uuid":"dev-odd-attrs"}|"#,
    "\n",
    r#"{"type":"META","ticket":24}||{"title":"Odd","attributes":["not","an","object"]}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":25}||{"docType":"DEVICE","uuid":"dev-empty-array"}|"#,
    "\n",
    r#"{"type":"META","ticket":26}||{"title":"Empty Array","attributes":[]}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":27}||{"docType":"DEVICE","uuid":"dev-bare"}|"#,
    "\n",
    r#"{"type":"META","ticket":28}||{"title":"Bare"}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":29}||{"docType":"DEVICE","uuid":"dev-overflow"}|"#,
    "\n",
    r#"{"type":"META","ticket":30}||{"title":"Overflow","attributes":{"Supplier Part":1e309,"Manufacturer Part":-1e309,"Datasheet":1e-400}}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":31}||{"docType":"DEVICE","uuid":"dev-big-int"}|"#,
    "\n",
    r#"{"type":"META","ticket":32}||{"title":"Big Integer","attributes":{"Supplier Part":123456789012345678901234567890}}|"#,
);

/// The Python half states this document as `EXPECTED`.
const EXPECTED: &str = r#"{
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
        "Supplier Footprint": "0805"
      },
      "is_part": "yes"
    },
    "dev-empty": {"title": "", "is_part": "no"},
    "dev-first-meta": {"title": "First", "is_part": "yes"},
    "dev-same": {"title": "Same", "lcsc_part": "C1", "is_part": "yes"},
    "dev-conflict": {"title": "First Wins", "lcsc_part": "C100", "is_part": "yes"},
    "dev-no-designator": {
      "title": "GND",
      "name_template": "GND",
      "symbol": "sym-pwr",
      "is_part": "no"
    },
    "dev-odd-attrs": {"title": "Odd"},
    "dev-empty-array": {"title": "Empty Array", "is_part": "no"},
    "dev-bare": {"title": "Bare", "is_part": "no"},
    "dev-overflow": {
      "title": "Overflow",
      "lcsc_part": "inf",
      "mpn": "-inf",
      "datasheet": "0.0",
      "is_part": "no"
    },
    "dev-big-int": {
      "title": "Big Integer",
      "lcsc_part": "123456789012345678901234567890",
      "is_part": "no"
    }
  },
  "conflictingDocuments": 1
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
fn a_document_that_is_not_a_device_is_skipped() {
    // The `SCH` document at the top of the sample states a `META` with a
    // designator; it belongs to no device and is not in the projection.
    let text = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"SCH","uuid":"sch-1"}|"#,
        "\n",
        r#"{"type":"META"}||{"title":"Board","attributes":{"Designator":"A?"}}|"#,
        "\n",
        r#"{"type":"DOCHEAD"}||{"docType":"DEVICE","uuid":"dev"}|"#,
        "\n",
        r#"{"type":"META"}||{"title":"R0402"}|"#,
    );
    let projection = project(text);
    assert_eq!(projection["conflictingDocuments"], 0);
    assert_eq!(
        projection["devices"],
        expected(r#"{"dev": {"title": "R0402", "is_part": "no"}}"#)
    );
}

#[test]
fn every_declared_field_travels_with_its_python_name() {
    // The six `DEVICE_ATTR_FIELDS` values, the library `Symbol`, the three
    // declared-type keys and `is_part` — stripped, and under the names the
    // Python reader gives them.
    let device = &project(SAMPLE)["devices"]["dev-full"];
    assert_eq!(device["lcsc_part"], "C12345");
    assert_eq!(device["mpn"], "MPN-1");
    assert_eq!(device["manufacturer"], "ACME Corp");
    assert_eq!(device["datasheet"], "https://example.invalid/usb-c.pdf");
    assert_eq!(device["footprint"], "0805");
    assert_eq!(device["name_template"], "{{Value}}");
    assert_eq!(device["symbol"], "sym-1");
    assert_eq!(
        device["declared_type"],
        expected(
            r#"{"Type": "Connector", "LCSC Part Name": "Type-C 16P",
                "Supplier Footprint": "0805"}"#
        )
    );
    assert_eq!(device["is_part"], "yes");
}

#[test]
fn an_empty_or_null_attribute_is_absent() {
    // `""`, `"  "`, `"null"`, `" null "` and a JSON `null` are all "no value":
    // none of them becomes a key, and none of them outranks a real one.
    let device = project(SAMPLE)["devices"]["dev-empty"].clone();
    assert_eq!(device, expected(r#"{"title": "", "is_part": "no"}"#));

    // A `null` *value* is skipped before `str()` runs — `str(None)` would spell
    // `"None"` and be kept as if it were a value.
    let text = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"DEVICE","uuid":"d"}|"#,
        "\n",
        r#"{"type":"META"}||{"title":"t","attributes":{"Manufacturer":null,"Symbol":null,"Type":null,"LCSC Part Name":"","Designator":null}}|"#,
    );
    assert_eq!(
        project(text)["devices"]["d"],
        expected(r#"{"title": "t", "is_part": "no"}"#)
    );
}

#[test]
fn the_first_meta_of_a_document_wins() {
    let text = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"DEVICE","uuid":"d"}|"#,
        "\n",
        r#"{"type":"META"}||{"title":"First","attributes":{"Supplier Part":"C1"}}|"#,
        "\n",
        r#"{"type":"META"}||{"title":"Second","attributes":{"Supplier Part":"C2"}}|"#,
    );
    assert_eq!(
        project(text)["devices"]["d"],
        expected(r#"{"title": "First", "lcsc_part": "C1", "is_part": "no"}"#)
    );
}

#[test]
fn a_device_without_a_uuid_is_no_device() {
    let text = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"DEVICE"}|"#,
        "\n",
        r#"{"type":"META"}||{"title":"No uuid","attributes":{"Designator":"U?"}}|"#,
        "\n",
        r#"{"type":"DOCHEAD"}||{"docType":"DEVICE","uuid":"kept"}|"#,
        "\n",
        r#"{"type":"META"}||{"title":"Kept"}|"#,
    );
    let projection = project(text);
    assert_eq!(
        projection["devices"],
        expected(r#"{"kept": {"title": "Kept", "is_part": "no"}}"#)
    );
    assert_eq!(projection["conflictingDocuments"], 0);
}

#[test]
fn an_identical_duplicate_is_not_a_conflict() {
    // Same uuid twice: the second copy moved its records around and carries
    // another `editVersion`, and neither is part of the reading.
    let text = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"DEVICE","uuid":"d","editVersion":"1"}|"#,
        "\n",
        r#"{"type":"META"}||{"title":"R","attributes":{"Supplier Part":"C1","Designator":"R?"}}|"#,
        "\n",
        r#"{"type":"DOCHEAD"}||{"docType":"DEVICE","uuid":"d","editVersion":"7"}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Convert to PCB","value":"1"}|"#,
        "\n",
        r#"{"type":"META"}||{"attributes":{"Designator":"R?","Supplier Part":"C1"},"title":"R"}|"#,
    );
    let projection = project(text);
    assert_eq!(projection["conflictingDocuments"], 0);
    assert_eq!(
        projection["devices"]["d"],
        expected(r#"{"title": "R", "lcsc_part": "C1", "is_part": "yes"}"#)
    );
}

#[test]
fn a_differing_duplicate_is_one_conflict_and_the_first_wins() {
    let text = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"DEVICE","uuid":"d"}|"#,
        "\n",
        r#"{"type":"META"}||{"title":"First Wins","attributes":{"Supplier Part":"C100"}}|"#,
        "\n",
        r#"{"type":"DOCHEAD"}||{"docType":"DEVICE","uuid":"d"}|"#,
        "\n",
        r#"{"type":"META"}||{"title":"Second Loses","attributes":{"Supplier Part":"C200"}}|"#,
    );
    let projection = project(text);
    assert_eq!(
        projection["devices"]["d"],
        expected(r#"{"title": "First Wins", "lcsc_part": "C100", "is_part": "no"}"#)
    );
    assert_eq!(projection["conflictingDocuments"], 1);
}

#[test]
fn a_device_without_a_designator_is_not_a_part() {
    let text = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"DEVICE","uuid":"pwr"}|"#,
        "\n",
        r#"{"type":"META"}||{"title":"GND","attributes":{"Symbol":"sym-pwr","Designator":"  "}}|"#,
        "\n",
        r#"{"type":"DOCHEAD"}||{"docType":"DEVICE","uuid":"part"}|"#,
        "\n",
        r#"{"type":"META"}||{"title":"R0402","attributes":{"Designator":"R?"}}|"#,
    );
    let devices = project(text)["devices"].clone();
    assert_eq!(devices["pwr"]["is_part"], "no");
    assert_eq!(devices["part"]["is_part"], "yes");
}

#[test]
fn attributes_that_are_not_an_object_keep_the_title_only() {
    // A truthy non-object: the whole attribute block is skipped, and `is_part`
    // is **absent** — a different document from one that states `"no"`.
    let text = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"DEVICE","uuid":"list"}|"#,
        "\n",
        r#"{"type":"META"}||{"title":"Odd","attributes":["not","an","object"]}|"#,
        "\n",
        r#"{"type":"DOCHEAD"}||{"docType":"DEVICE","uuid":"word"}|"#,
        "\n",
        r#"{"type":"META"}||{"title":"Word","attributes":"nope"}|"#,
    );
    let devices = project(text)["devices"].clone();
    assert_eq!(devices["list"], expected(r#"{"title": "Odd"}"#));
    assert_eq!(devices["word"], expected(r#"{"title": "Word"}"#));
    assert!(devices["list"].get("is_part").is_none());
}

#[test]
fn falsy_attributes_are_the_empty_object_not_a_non_object() {
    // Python's `body.get("attributes") or {}` makes every **falsy** value an
    // empty dict — including an empty array — so `is_part` is written (`"no"`),
    // where a truthy non-object above leaves it out.
    let text = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"DEVICE","uuid":"arr"}|"#,
        "\n",
        r#"{"type":"META"}||{"title":"Empty Array","attributes":[]}|"#,
        "\n",
        r#"{"type":"DOCHEAD"}||{"docType":"DEVICE","uuid":"blank"}|"#,
        "\n",
        r#"{"type":"META"}||{"title":"Blank","attributes":""}|"#,
    );
    let devices = project(text)["devices"].clone();
    assert_eq!(
        devices["arr"],
        expected(r#"{"title": "Empty Array", "is_part": "no"}"#)
    );
    assert_eq!(
        devices["blank"],
        expected(r#"{"title": "Blank", "is_part": "no"}"#)
    );
}

#[test]
fn the_projection_states_no_document_text_or_edit_version() {
    let projection = project(SAMPLE).to_string();
    assert!(!projection.contains("editVersion"));
    assert!(!projection.contains("ticket"));
    assert!(!projection.contains("docType"));
}

#[test]
fn a_float_literal_beyond_f64s_range_spells_inf_not_the_literal() {
    // `1e309` denotes no f64: Python's `float()` saturates it to an infinity, so
    // the reader's `str()` gives `inf`/`-inf`, and `1e-400` underflows to `0.0`.
    // The Python half (`tests/test_038m_device_differential.py`) states the same
    // document; spelling the literal back out would be a mismatch.
    let text = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"DEVICE","uuid":"d"}|"#,
        "\n",
        r#"{"type":"META"}||{"title":"t","attributes":{"#,
        r#""Supplier Part":1e309,"Manufacturer Part":-1e309,"Datasheet":1e-400}}|"#,
    );
    assert_eq!(
        project(text)["devices"]["d"],
        expected(
            r#"{"title": "t", "lcsc_part": "inf", "mpn": "-inf",
                "datasheet": "0.0", "is_part": "no"}"#
        )
    );
}

#[test]
fn a_bare_integer_literal_keeps_every_digit() {
    // An integer literal is not a float — Python prints the exact integer, so it
    // must not travel through a double (which would round it to 1.2345678901234568e29).
    let text = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"DEVICE","uuid":"d"}|"#,
        "\n",
        r#"{"type":"META"}||{"title":"t","attributes":{"#,
        r#""Supplier Part":123456789012345678901234567890}}|"#,
    );
    assert_eq!(
        project(text)["devices"]["d"],
        expected(
            r#"{"title": "t", "lcsc_part": "123456789012345678901234567890",
                    "is_part": "no"}"#
        )
    );
}
