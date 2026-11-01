//! The `.epru` record *stream*: line framing and document splitting.
//!
//! A field-for-field port of `boardwise.parsers.epru_stream.iter_epru_records`
//! and `split_documents`, kept deliberately unfaithful in nothing: the shapes
//! below are the contract the differential runner will compare against, so the
//! four line shapes must not be conflated, no count may be "tidied", and no
//! malformed line may be repaired.
//!
//! ``.epru`` is a line record format: ``{envelope-json}||{body-json}|``
//! terminated by ``\n``. Two real-world deviations are tolerated and both are
//! legal input, never malformed:
//!
//! * ``{env}||{body-json}`` — the final line of a file may lack the terminator.
//! * ``{env}|||`` — a record may carry an empty body, counted as an empty-body
//!   record and kept (there is no payload to read, but the line is a record).
//!
//! The two compose: a real V4 export ends every document stream with
//! ``{env}||`` — an empty body whose terminator is missing (038F1). That line
//! is **not** ``{env}|``: there the field separator itself is gone, which is
//! what a genuinely truncated record looks like. Stripping the trailing ``|``
//! unconditionally is what turned the V4 EOF shape into ``{env}|`` and made
//! every V4 document stream report one damaged line at EOF.
//!
//! The stream is a concatenation of documents, each opened by a ``DOCHEAD``
//! record carrying a ``docType``. [`split_documents`] keeps only ``PCB``,
//! ``FOOTPRINT``, ``DEVICE`` and ``SYMBOL`` documents; the records of every
//! other document are dropped after being counted, which is why a dropped
//! record still appears in [`EpruStreamProjection::records_by_type`] while
//! belonging to no document.
//!
//! Nothing here knows what a pad, a track or a netlist is, and nothing is
//! projected that a later consumer can re-derive: bodies are reported as
//! presence only, and unknown record types are not counted (they are simply
//! keys of [`EpruStreamProjection::records_by_type`]).
//!
//! Known decoder dialect gaps against Python's `json.loads`, which only a
//! non-object `type`/`docType` value or a JSON extension could reach:
//! `NaN`/`Infinity` literals are refused here and accepted by Python, and an
//! array or object `type` prints as JSON rather than Python's `repr`.

use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};
use std::collections::BTreeMap;

use crate::{python_float_repr, python_whitespace};

/// Separator between the envelope JSON and the body JSON.
pub const FIELD_SEP: &str = "||";

/// [`FIELD_SEP`] plus the record terminator — the terminated empty-body shape.
pub const FIELD_SEP_TERMINATED: &str = "|||";

/// The record type that opens a document.
pub const DOCHEAD_RECORD_TYPE: &str = "DOCHEAD";

/// Document types [`split_documents`] keeps. Everything else is dropped after
/// being counted, so memory stays proportional to useful data.
pub const KEPT_DOCUMENT_TYPES: [&str; 4] = ["PCB", "FOOTPRINT", "DEVICE", "SYMBOL"];

/// Schema tag of the stream projection.
pub const EPRU_STREAM_SCHEMA: &str = "boardwise.epru-stream/1";

/// One decoded ``.epru`` line.
///
/// `line_no` is zero-based: the index of the line in ``text.split('\n')``.
/// Blank lines are not records at all and get no entry, so `line_no` skips
/// them — exactly the lines Python's `enumerate` would have counted.
///
/// A malformed line keeps its entry (the differential has to see the same
/// lines Python saw) but carries no decoded fields: Python skips such a line
/// before any record exists, so a `type` reported here would be a field no
/// counter ever saw.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct EpruRecord {
    pub line_no: usize,
    /// `str(envelope["type"])`, or `""` when the envelope has no `type` key.
    #[serde(rename = "type")]
    pub record_type: String,
    /// The body decoded to an object: Python's `EpruRecord.has_body`.
    pub has_body: bool,
    /// The body was blank, so there was no payload to read.
    pub empty_body: bool,
    /// The decode refused this line — and that is the whole record: Python
    /// counts such a line and skips it before any record exists, so classifying
    /// *why* here would be a field only this side could state.
    pub malformed: bool,
    /// ``docType`` a ``DOCHEAD`` record carries in its body; `None` on every
    /// other record, and on a ``DOCHEAD`` whose body carries no ``docType``.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub doc_type: Option<String>,
    /// Index into [`EpruStreamProjection::documents`], once [`split_documents`]
    /// has run. `None` = the record belongs to no kept document.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub document: Option<usize>,
}

/// A kept ``DOCHEAD``-delimited document.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct EpruDocument {
    pub doc_type: String,
    /// Records in the document, counting the ``DOCHEAD`` itself.
    pub record_count: usize,
}

/// Everything the stream scan saw, in one serializable projection.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct EpruStreamProjection {
    pub schema: String,
    /// Every non-empty line, malformed ones included, in file order.
    pub records: Vec<EpruRecord>,
    /// `records.len()` — Python's `ParseStats.total_records`.
    pub total: usize,
    /// `ParseStats.malformed_records`.
    pub malformed: usize,
    /// `ParseStats.empty_body_records`.
    pub empty_body: usize,
    pub documents: Vec<EpruDocument>,
    /// `ParseStats.document_types`: one count per ``DOCHEAD`` carrying a
    /// ``docType``, kept or dropped.
    pub document_types: BTreeMap<String, usize>,
    /// `ParseStats.records_by_type` over every **decoded** record, in kept
    /// documents or not.
    pub records_by_type: BTreeMap<String, usize>,
}

/// Decode ``.epru`` text line by line. Never fails, never repairs.
///
/// Returns one entry per non-empty line, malformed ones flagged rather than
/// dropped: the caller decides what to do with them, and the projection needs
/// to report the same lines Python counted.
pub fn iter_epru_records(text: &str) -> Vec<EpruRecord> {
    text.split('\n')
        .enumerate()
        .filter(|(_, line)| !line.is_empty())
        .map(|(line_no, line)| decode_line(line_no, line))
        .collect()
}

/// Split decoded records into documents, keeping only [`KEPT_DOCUMENT_TYPES`].
///
/// A new document starts at every ``DOCHEAD`` record. Records that follow a
/// dropped document belong to nothing and keep `document = None`, while
/// records before the first ``DOCHEAD`` do the same — Python's `current is
/// None` covers both. The function writes the document index into every record
/// it assigns, so the two views cannot disagree.
pub fn split_documents(records: &mut [EpruRecord]) -> Vec<EpruDocument> {
    let mut documents: Vec<EpruDocument> = Vec::new();
    let mut current: Option<usize> = None;
    for record in records.iter_mut() {
        if record.malformed {
            continue;
        }
        if record.record_type == DOCHEAD_RECORD_TYPE {
            current = None;
            let Some(doc_type) = record.doc_type.as_deref() else {
                continue;
            };
            if !KEPT_DOCUMENT_TYPES.contains(&doc_type) {
                continue;
            }
            let index = documents.len();
            documents.push(EpruDocument {
                doc_type: doc_type.to_owned(),
                record_count: 1,
            });
            record.document = Some(index);
            current = Some(index);
            continue;
        }
        if let Some(index) = current {
            record.document = Some(index);
            documents[index].record_count += 1;
        }
    }
    documents
}

/// Scan and split in one step, deriving every counter from the records so the
/// counts cannot drift away from the list they describe.
pub fn project_stream(text: &str) -> EpruStreamProjection {
    let mut records = iter_epru_records(text);
    let documents = split_documents(&mut records);
    let mut malformed = 0;
    let mut empty_body = 0;
    let mut records_by_type: BTreeMap<String, usize> = BTreeMap::new();
    let mut document_types: BTreeMap<String, usize> = BTreeMap::new();
    for record in &records {
        if record.malformed {
            malformed += 1;
            continue;
        }
        if record.empty_body {
            empty_body += 1;
        }
        *records_by_type
            .entry(record.record_type.clone())
            .or_insert(0) += 1;
        if record.record_type == DOCHEAD_RECORD_TYPE
            && let Some(doc_type) = &record.doc_type
        {
            *document_types.entry(doc_type.clone()).or_insert(0) += 1;
        }
    }
    EpruStreamProjection {
        schema: EPRU_STREAM_SCHEMA.to_owned(),
        total: records.len(),
        records,
        malformed,
        empty_body,
        documents,
        document_types,
        records_by_type,
    }
}

// --------------------------------------------------------------- line shapes

fn decode_line(line_no: usize, line: &str) -> EpruRecord {
    let core = framing_core(line);
    let Some((envelope_text, body_text)) = core.split_once(FIELD_SEP) else {
        return malformed_line(line_no);
    };

    let envelope = match serde_json::from_str::<Value>(envelope_text) {
        Ok(envelope) => envelope,
        Err(_) => return malformed_line(line_no),
    };
    let Value::Object(fields) = envelope else {
        return malformed_line(line_no);
    };

    let empty_body = !body_text
        .chars()
        .any(|character| !python_whitespace(character));
    let mut body: Option<Map<String, Value>> = None;
    if !empty_body {
        match serde_json::from_str::<Value>(body_text) {
            Ok(Value::Object(fields)) => body = Some(fields),
            // A non-object body is no payload either, yet it is neither empty
            // nor malformed: Python keeps the record with `body=None`.
            Ok(_) => {}
            Err(_) => return malformed_line(line_no),
        }
    }
    let has_body = body.is_some();

    let record_type = fields.get("type").map_or_else(String::new, python_text);
    // ``docType`` lives in the **body**, not the envelope: Python reads
    // ``(record.body or {}).get("docType")``, so an empty or non-object body
    // yields no docType and the document is dropped after counting.
    let doc_type = if record_type == DOCHEAD_RECORD_TYPE {
        body.as_ref()
            .and_then(|fields| fields.get("docType"))
            .filter(|value| !value.is_null())
            .map(python_text)
    } else {
        None
    };
    EpruRecord {
        line_no,
        record_type,
        has_body,
        empty_body,
        malformed: false,
        doc_type,
        document: None,
    }
}

/// Strip the record terminator, honouring the four shapes in order.
///
/// ``{env}||{body}|`` loses its ``|``; ``{env}||`` loses nothing (the separator
/// ends the line and both of its characters are the separator's); ``{env}|||``
/// loses one ``|`` and keeps the separator; ``{env}`` loses nothing.
fn framing_core(line: &str) -> &str {
    // ``{env}||`` — the separator ends the line, so both characters are the
    // separator's and neither is a terminator. This branch must come first:
    // ``{env}|||`` also ends with ``||``, and stripping it here would eat the
    // separator's second character (038F1).
    if line.ends_with(FIELD_SEP) && !line.ends_with(FIELD_SEP_TERMINATED) {
        return line;
    }
    line.strip_suffix('|').unwrap_or(line)
}

fn malformed_line(line_no: usize) -> EpruRecord {
    EpruRecord {
        line_no,
        record_type: String::new(),
        has_body: false,
        empty_body: false,
        malformed: true,
        doc_type: None,
        document: None,
    }
}

/// `str(value)` for a decoded JSON value — what Python interpolates into
/// `record_type` and `document_types`.
///
/// Scalars match CPython: `None`, `True`, `False`, integers as written, floats
/// through [`python_float_repr`]. Arrays and objects fall back to compact JSON
/// (Python would print `repr`); the gap is recorded in the module doc because
/// only a non-object `type`/`docType` could reach it.
fn python_text(value: &Value) -> String {
    match value {
        Value::Null => "None".to_owned(),
        Value::Bool(true) => "True".to_owned(),
        Value::Bool(false) => "False".to_owned(),
        Value::Number(number) => {
            let literal = number.to_string();
            if literal
                .bytes()
                .any(|byte| matches!(byte, b'.' | b'e' | b'E'))
            {
                number.as_f64().map_or(literal, python_float_repr)
            } else {
                literal
            }
        }
        Value::String(text) => text.clone(),
        other => other.to_string(),
    }
}
