//! The `boardwise.symbol-library/1` projection, read the way
//! `boardwise/parsers/schematic.py::_collect_symbols` reads it (038L).
//!
//! Every fixture is a synthetic `.epru` fragment: no real project content, no
//! fixture file. The two expected documents below are written out twice — here
//! and as `ZINDEX_EXPECTED`/`PIN_ID_EXPECTED` in
//! `tests/test_038l_symbol_differential.py`. The two literals are the contract;
//! a change on one side has to change both.

use boardwise_core::epru::{iter_epru_records, project_stream};
use boardwise_core::symbol::{PinKey, project_library};
use serde_json::Value;

/// The sample `tests/test_038l_symbol_differential.py:SAMPLE` projects.
///
/// One line per shape that matters: a dropped `SCH` document, a SYMBOL whose
/// `PIN` row carries an `id` that is *not* `e<zIndex>`, an `ATTR` before its
/// `PIN`, an `ATTR` addressed by the format's ref as well as by the row's id, an
/// `ATTR` with no `parentId` (open-run fallback), numeric-string coordinates, a
/// by_id/by_ref collision, a run with no number, an empty-body `PIN`, a SYMBOL
/// with no uuid, an identical copy (record order swapped, other `editVersion`),
/// a copy that differs (and loses, first-wins), and a `DEVICE` document that is
/// not read at all.
const SAMPLE: &str = concat!(
    r#"{"type":"DOCHEAD","ticket":1}||{"docType":"SCH"}|"#,
    "\n",
    r#"{"type":"PIN","ticket":2}||{"zIndex":99,"x":1,"y":1}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":3}||{"docType":"SYMBOL","uuid":"sym-a","editVersion":"1"}|"#,
    "\n",
    r#"{"type":"META","ticket":4}||{"title":"USB-C"}|"#,
    "\n",
    r#"{"type":"ATTR","ticket":5}||{"key":"Pin Number","value":"A1","parentId":"e9"}|"#,
    "\n",
    r#"{"type":"PIN","ticket":6,"id":"e9"}||{"zIndex":5,"x":12.25,"y":-30.5}|"#,
    "\n",
    r#"{"type":"ATTR","ticket":7}||{"key":"Pin Name","value":"VBUS","parentId":"e5"}|"#,
    "\n",
    r#"{"type":"ATTR","ticket":8}||{"key":"Pin Type","value":"Power"}|"#,
    "\n",
    r#"{"type":"PIN","ticket":9,"id":"p1"}||{"zIndex":1,"x":"7","y":"3"}|"#,
    "\n",
    r#"{"type":"ATTR","ticket":10}||{"key":"Pin Number","value":"1","parentId":"p1"}|"#,
    "\n",
    r#"{"type":"PIN","ticket":11,"id":"e1"}||{"zIndex":4,"x":0.1234567,"y":5.5}|"#,
    "\n",
    r#"{"type":"ATTR","ticket":12}||{"key":"Pin Number","value":"4","parentId":"e4"}|"#,
    "\n",
    r#"{"type":"ATTR","ticket":13}||{"key":"Pin Name","value":"SENSE","parentId":"e1"}|"#,
    "\n",
    r#"{"type":"PIN","ticket":14}||{"zIndex":6,"x":4.5,"y":4.5}|"#,
    "\n",
    r#"{"type":"ATTR","ticket":15}||{"key":"Pin Number","value":"6"}|"#,
    "\n",
    r#"{"type":"PIN","ticket":16,"id":"p8"}||{"zIndex":8,"x":2,"y":2}|"#,
    "\n",
    r#"{"type":"ATTR","ticket":17}||{"key":"Pin Name","value":"NC"}|"#,
    "\n",
    r#"{"type":"PIN","ticket":18,"id":"p9"}||"#,
    "\n",
    r#"{"type":"ATTR","ticket":19}||{"key":"Pin Name","value":""}|"#,
    "\n",
    r#"{"type":"ATTR","ticket":20}||{"key":"Pin Type","value":"null"}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":21}||{"docType":"SYMBOL"}|"#,
    "\n",
    r#"{"type":"PIN","ticket":22,"id":"d1"}||{"zIndex":1,"x":0,"y":0}|"#,
    "\n",
    r#"{"type":"ATTR","ticket":23}||{"key":"Pin Number","value":"1","parentId":"d1"}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":24}||{"docType":"SYMBOL","uuid":"sym-b","editVersion":"1"}|"#,
    "\n",
    r#"{"type":"META","ticket":25}||{"title":"R"}|"#,
    "\n",
    r#"{"type":"PIN","ticket":26,"id":"b1"}||{"zIndex":1,"x":-1.5,"y":2.25}|"#,
    "\n",
    r#"{"type":"ATTR","ticket":27}||{"key":"Pin Number","value":"1","parentId":"b1"}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":28}||{"docType":"SYMBOL","uuid":"sym-b","editVersion":"2"}|"#,
    "\n",
    r#"{"type":"ATTR","ticket":29}||{"key":"Pin Number","value":"1","parentId":"b1"}|"#,
    "\n",
    r#"{"type":"PIN","ticket":30,"id":"b1"}||{"zIndex":1,"x":-1.5,"y":2.25}|"#,
    "\n",
    r#"{"type":"META","ticket":31}||{"title":"R"}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":32}||{"docType":"SYMBOL","uuid":"sym-b","editVersion":"3"}|"#,
    "\n",
    r#"{"type":"META","ticket":33}||{"title":"R"}|"#,
    "\n",
    r#"{"type":"PIN","ticket":34,"id":"b1"}||{"zIndex":1,"x":-1.5,"y":2.25}|"#,
    "\n",
    r#"{"type":"ATTR","ticket":35}||{"key":"Pin Number","value":"1","parentId":"b1"}|"#,
    "\n",
    r#"{"type":"ATTR","ticket":36}||{"key":"Pin Name","value":"OUT","parentId":"b1"}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":37}||{"docType":"DEVICE","uuid":"dev"}|"#,
    "\n",
    r#"{"type":"ATTR","ticket":38}||{"key":"Pin Number","value":"99"}|"#,
);

/// The Python half states this document as `ZINDEX_EXPECTED`.
const ZINDEX_EXPECTED: &str = r#"{
  "schema": "boardwise.symbol-library/1",
  "pinKey": "zIndex",
  "symbols": {
    "sym-a": {
      "title": "USB-C",
      "pins": {
        "A1": {"point": [12.25, 30.5], "ref": "e5", "name": "VBUS", "type": "Power"},
        "1": {"point": [7.0, -3.0], "ref": "e1"},
        "4": {"point": [0.123457, -5.5], "ref": "e4", "name": "SENSE"},
        "6": {"point": [4.5, -4.5], "ref": "e6"}
      }
    },
    "sym-b": {"title": "R", "pins": {"1": {"point": [-1.5, -2.25], "ref": "e1"}}}
  },
  "pinsDroppedNoNumber": 1,
  "conflictingDocuments": 1
}"#;

/// The Python half states this document as `PIN_ID_EXPECTED`.
const PIN_ID_EXPECTED: &str = r#"{
  "schema": "boardwise.symbol-library/1",
  "pinKey": "pin_id",
  "symbols": {
    "sym-a": {
      "title": "USB-C",
      "pins": {
        "A1": {"point": [12.25, 30.5], "ref": "e9", "name": "VBUS", "type": "Power"},
        "1": {"point": [7.0, -3.0], "ref": "p1"},
        "4": {"point": [0.123457, -5.5], "ref": "e1", "name": "SENSE"},
        "6": {"point": [4.5, -4.5], "ref": "e6"}
      }
    },
    "sym-b": {"title": "R", "pins": {"1": {"point": [-1.5, -2.25], "ref": "b1"}}}
  },
  "pinsDroppedNoNumber": 1,
  "conflictingDocuments": 1
}"#;

fn project(text: &str, pin_key: PinKey) -> Value {
    let records = iter_epru_records(text);
    let library = project_library(&records, pin_key).expect("the library projects");
    serde_json::to_value(library).expect("the projection serializes")
}

fn expected(literal: &str) -> Value {
    serde_json::from_str(literal).expect("the expected literal is JSON")
}

#[test]
fn zindex_sample_matches_the_python_contract_literal() {
    assert_eq!(project(SAMPLE, PinKey::ZIndex), expected(ZINDEX_EXPECTED));
}

#[test]
fn pin_id_sample_matches_the_python_contract_literal() {
    assert_eq!(project(SAMPLE, PinKey::PinId), expected(PIN_ID_EXPECTED));
}

#[test]
fn a_pin_id_ref_is_the_rows_own_id_not_the_synthesised_zindex() {
    // V3: the PIN row's `id` is `e9` while its zIndex makes the ref `e5`.
    let text = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u"}|"#,
        "\n",
        r#"{"type":"PIN","id":"e9"}||{"zIndex":5,"x":1,"y":2}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Number","value":"1","parentId":"e9"}|"#,
    );

    assert_eq!(
        project(text, PinKey::ZIndex)["symbols"]["u"]["pins"]["1"]["ref"],
        "e5"
    );
    assert_eq!(
        project(text, PinKey::PinId)["symbols"]["u"]["pins"]["1"]["ref"],
        "e9"
    );
    // A PIN with no envelope id has no other spelling in either mode.
    let without_id = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u"}|"#,
        "\n",
        r#"{"type":"PIN"}||{"zIndex":5,"x":1,"y":2}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Number","value":"1"}|"#,
    );
    assert_eq!(
        project(without_id, PinKey::PinId)["symbols"]["u"]["pins"]["1"]["ref"],
        "e5"
    );
}

#[test]
fn an_attribute_before_its_pin_is_filed_by_parent_id() {
    let text = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u"}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Number","value":"A1","parentId":"e9"}|"#,
        "\n",
        r#"{"type":"PIN","id":"e9"}||{"zIndex":5,"x":1,"y":2}|"#,
    );

    assert_eq!(
        project(text, PinKey::ZIndex)["symbols"]["u"]["pins"],
        expected(r#"{"A1": {"point": [1.0, -2.0], "ref": "e5"}}"#)
    );
}

#[test]
fn an_attribute_after_the_last_pin_is_filed_by_parent_id() {
    // The shape 3.2.186 writes: the numbers sit in one block after the last PIN.
    let text = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u"}|"#,
        "\n",
        r#"{"type":"PIN","id":"p1"}||{"zIndex":1,"x":0,"y":0}|"#,
        "\n",
        r#"{"type":"PIN","id":"p2"}||{"zIndex":2,"x":0,"y":0}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Number","value":"2","parentId":"p2"}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Number","value":"1","parentId":"p1"}|"#,
    );

    let pins = &project(text, PinKey::ZIndex)["symbols"]["u"]["pins"];
    assert_eq!(pins.as_object().map(|pins| pins.len()), Some(2));
    assert_eq!(pins["1"]["ref"], "e1");
    assert_eq!(pins["2"]["ref"], "e2");
}

#[test]
fn an_attribute_naming_nothing_falls_back_to_the_open_run() {
    let text = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u"}|"#,
        "\n",
        r#"{"type":"PIN","id":"p1"}||{"zIndex":1,"x":0,"y":0}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Number","value":"1","parentId":"nobody"}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Name","value":"NAME","parentId":""}|"#,
    );

    assert_eq!(
        project(text, PinKey::ZIndex)["symbols"]["u"]["pins"],
        expected(r#"{"1": {"point": [0.0, -0.0], "ref": "e1", "name": "NAME"}}"#)
    );
}

#[test]
fn a_parent_id_naming_two_pins_resolves_by_id_first() {
    // `p1`'s ref is `e1` and the *next* row's own id is `e1`: one spelling, two
    // pins. The id owner takes the attribute, exactly like Python's `by_id or
    // by_ref`, and the field it fills cannot be stolen back afterwards.
    let text = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u"}|"#,
        "\n",
        r#"{"type":"PIN","id":"p1"}||{"zIndex":1,"x":0,"y":0}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Number","value":"1","parentId":"p1"}|"#,
        "\n",
        r#"{"type":"PIN","id":"e1"}||{"zIndex":4,"x":0,"y":0}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Number","value":"4","parentId":"e4"}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Name","value":"SENSE","parentId":"e1"}|"#,
    );

    let pins = &project(text, PinKey::ZIndex)["symbols"]["u"]["pins"];
    assert_eq!(pins["1"]["ref"], "e1");
    assert!(pins["1"].get("name").is_none(), "the ref owner keeps none");
    assert_eq!(pins["4"]["ref"], "e4");
    assert_eq!(pins["4"]["name"], "SENSE");
}

#[test]
fn a_run_without_a_number_is_dropped_and_counted() {
    let text = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u"}|"#,
        "\n",
        r#"{"type":"PIN","id":"p1"}||{"zIndex":1,"x":0,"y":0}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Name","value":"ONLY_A_NAME"}|"#,
        "\n",
        r#"{"type":"PIN","id":"p2"}||{"zIndex":2,"x":1,"y":1}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Number","value":"2","parentId":"p2"}|"#,
    );

    let library = project(text, PinKey::ZIndex);
    assert_eq!(library["pinsDroppedNoNumber"], 1);
    assert_eq!(
        library["symbols"]["u"]["pins"],
        expected(r#"{"2": {"point": [1.0, -1.0], "ref": "e2"}}"#)
    );
}

#[test]
fn an_empty_body_record_is_neither_a_run_nor_a_drop() {
    // `{env}||` and `{env}|||` are legal empty bodies: nothing to read, so no
    // run, no `parentId`, and — because no run exists — no dropped-pin count.
    let text = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u"}|"#,
        "\n",
        r#"{"type":"PIN","id":"p1"}||"#,
        "\n",
        r#"{"type":"PIN"}||{"zIndex":1,"x":2,"y":3}|"#,
        "\n",
        r#"{"type":"ATTR"}|||"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Number","value":"1"}|"#,
    );

    let library = project(text, PinKey::ZIndex);
    assert_eq!(library["pinsDroppedNoNumber"], 0);
    assert_eq!(
        library["symbols"]["u"]["pins"],
        expected(r#"{"1": {"point": [2.0, -3.0], "ref": "e1"}}"#)
    );
}

#[test]
fn an_identical_duplicate_document_is_not_a_conflict() {
    // Same symbol, other `editVersion`, records written in another order.
    let text = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u","editVersion":"1"}|"#,
        "\n",
        r#"{"type":"META"}||{"title":"R"}|"#,
        "\n",
        r#"{"type":"PIN","id":"b1"}||{"zIndex":1,"x":1,"y":2}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Number","value":"1","parentId":"b1"}|"#,
        "\n",
        r#"{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u","editVersion":"2"}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Number","value":"1","parentId":"b1"}|"#,
        "\n",
        r#"{"type":"PIN","id":"b1"}||{"zIndex":1,"x":1,"y":2}|"#,
        "\n",
        r#"{"type":"META"}||{"title":"R"}|"#,
    );

    let library = project(text, PinKey::ZIndex);
    assert_eq!(library["conflictingDocuments"], 0);
    assert_eq!(library["pinsDroppedNoNumber"], 0);
}

#[test]
fn a_different_duplicate_document_is_one_conflict_and_the_first_wins() {
    let text = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u"}|"#,
        "\n",
        r#"{"type":"META"}||{"title":"R"}|"#,
        "\n",
        r#"{"type":"PIN","id":"b1"}||{"zIndex":1,"x":1,"y":2}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Number","value":"1","parentId":"b1"}|"#,
        "\n",
        r#"{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u"}|"#,
        "\n",
        r#"{"type":"META"}||{"title":"R"}|"#,
        "\n",
        r#"{"type":"PIN","id":"b1"}||{"zIndex":1,"x":1,"y":2}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Number","value":"1","parentId":"b1"}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Name","value":"OUT","parentId":"b1"}|"#,
    );

    let library = project(text, PinKey::ZIndex);
    assert_eq!(library["conflictingDocuments"], 1);
    // First-wins: the later copy's extra name never lands.
    assert_eq!(
        library["symbols"]["u"]["pins"],
        expected(r#"{"1": {"point": [1.0, -2.0], "ref": "e1"}}"#)
    );
}

#[test]
fn a_document_without_a_uuid_is_no_symbol() {
    let text = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"SYMBOL"}|"#,
        "\n",
        r#"{"type":"PIN","id":"d1"}||{"zIndex":1,"x":0,"y":0}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Number","value":"1","parentId":"d1"}|"#,
    );

    let library = project(text, PinKey::ZIndex);
    assert_eq!(library["symbols"], expected("{}"));
    // The pin had a number, so nothing was dropped either.
    assert_eq!(library["pinsDroppedNoNumber"], 0);
}

#[test]
fn the_stored_y_is_negated_once_and_rounded_to_six_decimals() {
    let text = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u"}|"#,
        "\n",
        r#"{"type":"PIN","id":"p1"}||{"zIndex":1,"x":12.25,"y":-30.5}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Number","value":"1"}|"#,
        "\n",
        r#"{"type":"PIN","id":"p2"}||{"zIndex":2,"x":0.1234567,"y":"-0"}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Number","value":"2"}|"#,
        "\n",
        r#"{"type":"PIN","id":"p3"}||{"zIndex":3}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Number","value":"3"}|"#,
    );

    let pins = project(text, PinKey::ZIndex)["symbols"]["u"]["pins"].clone();
    // Canvas space: the file stores y opposite to the canvas, so it is negated
    // exactly once — flipping again would put the pin at the top of the page.
    assert_eq!(pins["1"]["point"], expected("[12.25, 30.5]"));
    assert_eq!(pins["2"]["point"], expected("[0.123457, 0.0]"));
    // A missing coordinate is 0 (and `-0` is still zero).
    assert_eq!(pins["3"]["point"], expected("[0.0, -0.0]"));
}

#[test]
fn an_unknown_pin_key_is_refused() {
    let error = PinKey::parse("pinId").expect_err("only the two declared spellings");
    assert!(error.to_string().contains("pinKey"));
}

#[test]
fn the_stream_projection_still_states_no_ids_or_bodies() {
    // The record now carries the envelope id and the decoded body internally:
    // `boardwise.epru-stream/1` must not grow a field for either.
    let encoded = serde_json::to_value(project_stream(SAMPLE)).expect("projection serializes");
    let record = encoded["records"][5]
        .as_object()
        .expect("a record is an object");
    let mut keys: Vec<&str> = record.keys().map(String::as_str).collect();
    keys.sort_unstable();
    assert_eq!(
        keys,
        [
            "document",
            "emptyBody",
            "hasBody",
            "lineNo",
            "malformed",
            "type"
        ]
    );
    assert!(encoded["records"][5].get("id").is_none());
    assert!(encoded["records"][5].get("body").is_none());
}

#[test]
fn a_repeated_number_keeps_the_name_and_type_its_duplicate_omits() {
    // A pin number is filed per **field**: point and ref are last-wins, while a
    // name or type only moves when the duplicate run actually carries one.
    // Replacing the whole pin would erase a name that is already placed.
    let text = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u"}|"#,
        "\n",
        r#"{"type":"PIN","id":"r1"}||{"zIndex":1,"x":0,"y":0}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Number","value":"1","parentId":"r1"}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Name","value":"VCC","parentId":"r1"}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Type","value":"Power","parentId":"r1"}|"#,
        "\n",
        r#"{"type":"PIN","id":"r2"}||{"zIndex":2,"x":10,"y":10}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Number","value":"1","parentId":"r2"}|"#,
    );

    let pins = project(text, PinKey::ZIndex)["symbols"]["u"]["pins"].clone();
    assert_eq!(
        pins["1"],
        expected(r#"{"point":[10.0,-10.0],"ref":"e2","name":"VCC","type":"Power"}"#)
    );

    // A duplicate that *does* carry a value overwrites that field — and only it.
    let carrying = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u"}|"#,
        "\n",
        r#"{"type":"PIN","id":"r1"}||{"zIndex":1,"x":0,"y":0}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Number","value":"1","parentId":"r1"}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Name","value":"VCC","parentId":"r1"}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Type","value":"Power","parentId":"r1"}|"#,
        "\n",
        r#"{"type":"PIN","id":"r2"}||{"zIndex":2,"x":10,"y":10}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Number","value":"1","parentId":"r2"}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Name","value":"GND","parentId":"r2"}|"#,
    );

    assert_eq!(
        project(carrying, PinKey::ZIndex)["symbols"]["u"]["pins"]["1"],
        expected(r#"{"point":[10.0,-10.0],"ref":"e2","name":"GND","type":"Power"}"#)
    );
}

#[test]
fn a_renumbered_copy_is_the_same_definition_and_a_moved_pin_is_not() {
    // Same points, same names, same types; only the element numbering differs
    // (`id`, `zIndex` and the `parentId` naming them). A ref is a handle inside
    // one document, so this copy is not a conflict.
    let renumbered = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u"}|"#,
        "\n",
        r#"{"type":"PIN","id":"a1"}||{"zIndex":1,"x":3,"y":4}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Number","value":"1","parentId":"a1"}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Name","value":"IN","parentId":"a1"}|"#,
        "\n",
        r#"{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u"}|"#,
        "\n",
        r#"{"type":"PIN","id":"b7"}||{"zIndex":9,"x":3,"y":4}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Number","value":"1","parentId":"b7"}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Name","value":"IN","parentId":"b7"}|"#,
    );

    let library = project(renumbered, PinKey::ZIndex);
    assert_eq!(library["conflictingDocuments"], 0);
    // First-wins keeps the first copy's ref, renumbering or not.
    assert_eq!(library["symbols"]["u"]["pins"]["1"]["ref"], "e1");

    // A moved pin *is* a different definition and is counted.
    let moved = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u"}|"#,
        "\n",
        r#"{"type":"PIN","id":"a1"}||{"zIndex":1,"x":3,"y":4}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Number","value":"1","parentId":"a1"}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Name","value":"IN","parentId":"a1"}|"#,
        "\n",
        r#"{"type":"DOCHEAD"}||{"docType":"SYMBOL","uuid":"u"}|"#,
        "\n",
        r#"{"type":"PIN","id":"b7"}||{"zIndex":9,"x":3,"y":5}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Number","value":"1","parentId":"b7"}|"#,
        "\n",
        r#"{"type":"ATTR"}||{"key":"Pin Name","value":"IN","parentId":"b7"}|"#,
    );

    assert_eq!(project(moved, PinKey::ZIndex)["conflictingDocuments"], 1);
}
