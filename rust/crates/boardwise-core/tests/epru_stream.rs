//! The four `.epru` line shapes and the DOCHEAD/kept-document split, read the
//! way `boardwise/parsers/epru_stream.py` reads them (038F1 framing, 131a
//! SYMBOL documents). Every fixture is a synthetic two-or-three record
//! fragment: no real project content, no large fixture.

use boardwise_core::epru::{
    EPRU_STREAM_SCHEMA, EpruDocument, EpruStreamProjection, KEPT_DOCUMENT_TYPES, iter_epru_records,
    project_stream, split_documents,
};

/// A V4 export shape: document stream terminated, its last line an empty body
/// with no terminator (`{env}||`, legal EOF, 038F1).
const V4_STREAM: &str = concat!(
    r#"{"type":"DOCHEAD","ticket":1}||{"docType":"PCB","editVersion":"3.0.0","uuid":"p1"}|"#,
    "\n",
    r#"{"type":"LAYER","ticket":2}||{"id":1,"name":"TopLayer","visible":true}|"#,
    "\n",
    r#"{"type":"META","ticket":3}||"#,
);

/// Every document shape the splitter has to classify, plus the two kinds of
/// record that end up in no document.
const SPLIT_STREAM: &str = concat!(
    r#"{"type":"DOCHEAD","ticket":1}||{"docType":"PCB","uuid":"b1"}|"#,
    "\n",
    r#"{"type":"LAYER","ticket":2}||{"id":1}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":3}||{"docType":"SCH"}|"#,
    "\n",
    r#"{"type":"WIRE","ticket":4}||{"id":2}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":5}||{"docType":"FOOTPRINT"}|"#,
    "\n",
    r#"{"type":"PAD","ticket":6}||{"number":"1"}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":7}||"#,
    "\n",
    r#"{"type":"ARC","ticket":8}||{"id":3}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":9}||{"docType":"DEVICE","uuid":"d1"}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":10}||{"docType":"SYMBOL"}|"#,
);

#[test]
fn v3_terminated_final_line_decodes_as_a_body_record() {
    let stream = concat!(
        r#"{"type":"DOCHEAD","ticket":1}||{"docType":"PCB","uuid":"p1"}|"#,
        "\n",
        r#"{"type":"ARC","ticket":2}||{"id":"arc1","net":"GND"}|"#,
    );
    let projection = project_stream(stream);

    assert_eq!(projection.total, 2);
    assert_eq!(projection.malformed, 0);
    assert_eq!(projection.empty_body, 0);
    assert!(projection.records.iter().all(|record| record.has_body));
    assert_eq!(
        projection.documents,
        vec![EpruDocument {
            doc_type: "PCB".to_owned(),
            record_count: 2,
        }]
    );
    assert_eq!(projection.records_by_type.get("ARC"), Some(&1));
}

#[test]
fn v4_eof_empty_body_is_legal_and_not_malformed() {
    let projection = project_stream(V4_STREAM);

    assert_eq!(projection.total, 3);
    assert_eq!(projection.malformed, 0);
    assert_eq!(projection.empty_body, 1);
    let last = &projection.records[2];
    assert_eq!(last.line_no, 2);
    assert_eq!(last.record_type, "META");
    assert!(last.empty_body);
    assert!(!last.has_body);
    assert!(!last.malformed);
    assert_eq!(last.document, Some(0));
    // The EOF record is part of the document it terminates, DOCHEAD included.
    assert_eq!(
        projection.documents,
        vec![EpruDocument {
            doc_type: "PCB".to_owned(),
            record_count: 3,
        }]
    );
    assert_eq!(projection.records_by_type.get("META"), Some(&1));
}

#[test]
fn terminated_empty_body_is_legal_and_keeps_its_separator() {
    let stream = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"FOOTPRINT"}|"#,
        "\n",
        r#"{"type":"PAD"}|||"#,
        "\n",
        r#"{"type":"PAD"}||"#,
    );
    let projection = project_stream(stream);

    assert_eq!(projection.records.len(), 3);
    assert_eq!(projection.malformed, 0);
    // Both empty bodies count; the terminated one is not a body of `"|"`.
    assert_eq!(projection.empty_body, 2);
    for record in &projection.records[1..] {
        assert!(record.empty_body);
        assert!(!record.has_body);
        assert_eq!(record.document, Some(0));
    }
    assert_eq!(projection.documents[0].record_count, 3);
}

#[test]
fn truncated_records_stay_malformed() {
    let stream = concat!(
        r#"{"type":"DOCHEAD"}||{"docType":"PCB"}|"#,
        "\n",
        r#"{"type":"PAD","ticket":9}"#,
        "\n",
        r#"{"type":"PAD"}|"#,
    );
    let projection = project_stream(stream);

    assert_eq!(projection.total, 3);
    assert_eq!(projection.malformed, 2);
    for record in &projection.records[1..] {
        assert!(record.malformed);
        // A malformed line carries no decoded fields: Python never yields one,
        // so it states no type, no document and no reason either.
        assert_eq!(record.record_type, "");
        assert_eq!(record.document, None);
        let encoded = serde_json::to_value(record).expect("record serializes");
        let mut keys: Vec<&str> = encoded
            .as_object()
            .expect("record is an object")
            .keys()
            .map(String::as_str)
            .collect();
        keys.sort_unstable();
        assert_eq!(
            keys,
            ["emptyBody", "hasBody", "lineNo", "malformed", "type"]
        );
    }
    assert_eq!(projection.documents[0].record_count, 1);
    assert_eq!(
        projection.records_by_type,
        [("DOCHEAD".to_owned(), 1)].into()
    );
}

#[test]
fn each_malformed_stage_counts_once_without_a_reason() {
    let stream = concat!(
        r#"{"type":"PAD"||{"a":1}|"#,
        "\n",
        r#"[1,2]||{"a":1}|"#,
        "\n",
        r#"{"type":"PAD"}||{oops}|"#,
        "\n",
        r#"{"type":"PAD"}||[1,2]|"#,
    );
    let projection = project_stream(stream);

    assert_eq!(projection.total, 4);
    assert_eq!(projection.malformed, 3);
    assert_eq!(projection.empty_body, 0);
    let malformed: Vec<bool> = projection
        .records
        .iter()
        .map(|record| record.malformed)
        .collect();
    // Three refused lines and the array body the decoder keeps: the boolean says
    // which, and nothing here names *why* a line was refused.
    assert_eq!(malformed, vec![true, true, true, false]);
    // A non-object body is no payload, yet neither empty nor malformed.
    let array_body = &projection.records[3];
    assert!(!array_body.malformed);
    assert!(!array_body.has_body);
    assert!(!array_body.empty_body);
    assert_eq!(projection.records_by_type.get("PAD"), Some(&1));
    assert!(projection.documents.is_empty());
}

#[test]
fn dochead_filtering_keeps_four_types_and_counts_the_dochead() {
    let mut records = iter_epru_records(SPLIT_STREAM);
    let split = split_documents(&mut records);
    let projection = project_stream(SPLIT_STREAM);
    // The two entry points cannot disagree.
    assert_eq!(split, projection.documents);

    assert_eq!(
        split,
        vec![
            EpruDocument {
                doc_type: "PCB".to_owned(),
                record_count: 2,
            },
            EpruDocument {
                doc_type: "FOOTPRINT".to_owned(),
                record_count: 2,
            },
            EpruDocument {
                doc_type: "DEVICE".to_owned(),
                record_count: 1,
            },
            EpruDocument {
                doc_type: "SYMBOL".to_owned(),
                record_count: 1,
            },
        ]
    );
    assert!(
        split
            .iter()
            .all(|document| KEPT_DOCUMENT_TYPES.contains(&document.doc_type.as_str()))
    );

    assert_eq!(projection.malformed, 0);
    assert_eq!(projection.empty_body, 1);
    assert_eq!(projection.document_types.get("PCB"), Some(&1));
    assert_eq!(projection.document_types.get("SCH"), Some(&1));
    assert_eq!(projection.document_types.get("FOOTPRINT"), Some(&1));
    assert_eq!(projection.document_types.get("DEVICE"), Some(&1));
    assert_eq!(projection.document_types.get("SYMBOL"), Some(&1));
    // A DOCHEAD whose body is empty has no docType, so it is counted nowhere.
    assert_eq!(projection.document_types.len(), 5);

    // Records of a dropped document, and records after a docType-less
    // DOCHEAD, belong to no document — yet both still count by type.
    let ownership: Vec<Option<usize>> = records.iter().map(|record| record.document).collect();
    assert_eq!(
        ownership,
        vec![
            Some(0),
            Some(0),
            None,
            None,
            Some(1),
            Some(1),
            None,
            None,
            Some(2),
            Some(3),
        ]
    );
    assert_eq!(projection.records_by_type.get("DOCHEAD"), Some(&6));
    assert_eq!(projection.records_by_type.get("WIRE"), Some(&1));
    assert_eq!(projection.records_by_type.get("ARC"), Some(&1));
}

#[test]
fn every_non_empty_line_enters_records_including_malformed() {
    let stream = concat!(
        "\n",
        r#"{"type":"LAYER"}||{"id":1}|"#,
        "\n",
        "\n",
        "   \n",
        r#"{"type":"LAYER"}"#,
        "\n",
    );
    let projection = project_stream(stream);

    // Blank lines are not records; the whitespace-only line is one (and malformed).
    assert_eq!(projection.total, 3);
    assert_eq!(projection.records.len(), 3);
    let line_numbers: Vec<usize> = projection
        .records
        .iter()
        .map(|record| record.line_no)
        .collect();
    assert_eq!(line_numbers, vec![1, 3, 4]);
    assert_eq!(projection.malformed, 2);
    assert_eq!(projection.records_by_type.get("LAYER"), Some(&1));
    assert!(projection.documents.is_empty());
}

#[test]
fn projection_serializes_with_camel_case_keys() {
    let encoded = serde_json::to_value(project_stream(V4_STREAM)).expect("projection serializes");

    assert_eq!(encoded["schema"], EPRU_STREAM_SCHEMA);
    assert_eq!(encoded["total"], 3);
    assert_eq!(encoded["malformed"], 0);
    assert_eq!(encoded["emptyBody"], 1);
    assert_eq!(encoded["records"][0]["type"], "DOCHEAD");
    assert_eq!(encoded["records"][0]["lineNo"], 0);
    assert_eq!(encoded["records"][0]["hasBody"], true);
    assert_eq!(encoded["records"][0]["docType"], "PCB");
    assert_eq!(encoded["records"][0]["document"], 0);
    // Only the documented keys: no diagnostic field rides along.
    let mut keys: Vec<&str> = encoded["records"][0]
        .as_object()
        .expect("record is an object")
        .keys()
        .map(String::as_str)
        .collect();
    keys.sort_unstable();
    assert_eq!(
        keys,
        [
            "docType",
            "document",
            "emptyBody",
            "hasBody",
            "lineNo",
            "malformed",
            "type"
        ]
    );
    assert_eq!(encoded["records"][2]["emptyBody"], true);
    assert_eq!(encoded["documents"][0]["docType"], "PCB");
    assert_eq!(encoded["documents"][0]["recordCount"], 3);
    assert_eq!(encoded["documentTypes"]["PCB"], 1);
    assert_eq!(encoded["recordsByType"]["DOCHEAD"], 1);
    assert_eq!(encoded["recordsByType"]["META"], 1);

    let decoded: EpruStreamProjection =
        serde_json::from_value(encoded).expect("projection round-trips");
    assert_eq!(decoded, project_stream(V4_STREAM));
}

/// The sample `tests/test_038i_epru_differential.py:SAMPLE` projects, line for
/// line: a dropped `SCH` document, a kept one, a terminated empty body, a
/// truncated line, a DOCHEAD without its terminator, the V4 EOF shape mid-stream
/// and at EOF, and a terminated last line that carries a body.
const SAMPLE_STREAM: &str = concat!(
    r#"{"type":"DOCHEAD","ticket":1}||{"docType":"SCH"}|"#,
    "\n",
    r#"{"type":"WIRE","ticket":2}||{"id":7}|"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":3}||{"docType":"PCB"}|"#,
    "\n",
    r#"{"type":"PAD","ticket":4}||{"number":"1"}|"#,
    "\n",
    r#"{"type":"PAD","ticket":5}|||"#,
    "\n",
    r#"{"type":"META","ticket":6}"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":7}||{"docType":"FOOTPRINT"}"#,
    "\n",
    r#"{"type":"PAD","ticket":8}||"#,
    "\n",
    r#"{"type":"DOCHEAD","ticket":9}||{"docType":"SYMBOL"}|"#,
    "\n",
    r#"{"type":"PIN","ticket":10}||"#,
);

/// The Python half states this document as `EXPECTED`; the two literals are the
/// contract, so a field added on one side has to be added on the other.
const SAMPLE_EXPECTED: &str = r#"{
  "schema": "boardwise.epru-stream/1",
  "records": [
    {"lineNo": 0, "type": "DOCHEAD", "hasBody": true, "emptyBody": false,
     "malformed": false, "docType": "SCH"},
    {"lineNo": 1, "type": "WIRE", "hasBody": true, "emptyBody": false,
     "malformed": false},
    {"lineNo": 2, "type": "DOCHEAD", "hasBody": true, "emptyBody": false,
     "malformed": false, "docType": "PCB", "document": 0},
    {"lineNo": 3, "type": "PAD", "hasBody": true, "emptyBody": false,
     "malformed": false, "document": 0},
    {"lineNo": 4, "type": "PAD", "hasBody": false, "emptyBody": true,
     "malformed": false, "document": 0},
    {"lineNo": 5, "type": "", "hasBody": false, "emptyBody": false,
     "malformed": true},
    {"lineNo": 6, "type": "DOCHEAD", "hasBody": true, "emptyBody": false,
     "malformed": false, "docType": "FOOTPRINT", "document": 1},
    {"lineNo": 7, "type": "PAD", "hasBody": false, "emptyBody": true,
     "malformed": false, "document": 1},
    {"lineNo": 8, "type": "DOCHEAD", "hasBody": true, "emptyBody": false,
     "malformed": false, "docType": "SYMBOL", "document": 2},
    {"lineNo": 9, "type": "PIN", "hasBody": false, "emptyBody": true,
     "malformed": false, "document": 2}
  ],
  "total": 10,
  "malformed": 1,
  "emptyBody": 3,
  "documents": [
    {"docType": "PCB", "recordCount": 3},
    {"docType": "FOOTPRINT", "recordCount": 2},
    {"docType": "SYMBOL", "recordCount": 2}
  ],
  "documentTypes": {"SCH": 1, "PCB": 1, "FOOTPRINT": 1, "SYMBOL": 1},
  "recordsByType": {"DOCHEAD": 4, "PAD": 3, "PIN": 1, "WIRE": 1}
}"#;

#[test]
fn sample_projection_matches_the_python_contract_literal() {
    let encoded =
        serde_json::to_value(project_stream(SAMPLE_STREAM)).expect("projection serializes");
    let expected: serde_json::Value =
        serde_json::from_str(SAMPLE_EXPECTED).expect("the expected literal is JSON");

    assert_eq!(encoded, expected);
}
