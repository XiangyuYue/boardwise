//! The `.epru` **DEVICE library** — the per-device metadata the review reads.
//!
//! A field-for-field port of `boardwise.parsers.schematic._collect_device_meta`:
//! the same document gate, the same first-`META` rule, the same attribute
//! vocabulary, so the projection below is the document the Python differential
//! runner derives from the same text.
//!
//! A DEVICE document states what a placed part **is**; a placed COMPONENT's own
//! `ATTR`s are only a partial copy of it, which is why the library copy decides.
//! The meta is per **document**, keyed by its uuid, and holds what the model may
//! see: the title, the six [`DEVICE_ATTR_FIELDS`] values, the library `Symbol`
//! uuid, the three declared-type keys (under `declared_type`) and `is_part` —
//! `"yes"` when the library device declares a `Designator` template, `"no"` for a
//! power symbol, a net flag or the page frame.
//!
//! Three rules, each with a shape that looks like a shortcut and is not:
//!
//! 1. **The first `META` of a document wins**; a second one is ignored. Python
//!    assigns the document's meta once, so a later `META` cannot move a field.
//! 2. **`attributes` is read the way `body.get("attributes") or {}` reads it.**
//!    A **falsy** non-object (an empty array, an empty string, `0`, `null`) is
//!    the empty object, so the attribute block runs and `is_part` is written
//!    (`"no"`). A **truthy** non-object is not an object at all: Python's
//!    `isinstance(attributes, dict)` guard skips the whole block, which leaves
//!    the meta title-only and writes **no** `is_part` — absent is a different
//!    statement from `"no"`.
//! 3. **A repeated uuid merges first-wins.** `conflicting_documents` counts a
//!    later document whose *model-visible* meta differs from the first one's and
//!    stays 0 for the copies a V4 export repeats page by page, which differ only
//!    in `editVersion`, in the order their records were written, or in the
//!    element numbering their document happens to use.
//!
//! Nothing here knows what a device is *for*: no netlist, no rule, no drawing
//! decision.

use serde::Serialize;
use serde_json::{Map, Value};
use std::collections::BTreeMap;

use crate::epru::{DOCHEAD_RECORD_TYPE, EpruRecord, python_text};
use crate::{python_truthy, python_whitespace};

/// Schema tag of the DEVICE library projection.
pub const DEVICE_LIBRARY_SCHEMA: &str = "boardwise.device-library/1";

/// The document type [`project_library`] reads. Every other document is skipped,
/// exactly like `_collect_device_meta`'s `uuid = ""`.
pub const DEVICE_DOC_TYPE: &str = "DEVICE";

/// The `META.attributes` keys the resolver needs, mapped to the meta field each
/// one fills (`DEVICE_ATTR_FIELDS`).
pub const DEVICE_ATTR_FIELDS: [(&str, &str); 6] = [
    ("Supplier Part", "lcsc_part"),
    ("Manufacturer Part", "mpn"),
    ("Manufacturer", "manufacturer"),
    ("Datasheet", "datasheet"),
    ("Supplier Footprint", "footprint"),
    ("Name", "name_template"),
];

/// The 立创 strings that declare *what the part is* (`METADATA_TYPE_KEYS`). Read
/// under their own key inside `declared_type` and nowhere else, so a rule cannot
/// see one vocabulary on one view and another on the other.
pub const DECLARED_TYPE_KEYS: [&str; 3] = ["Type", "LCSC Part Name", "Supplier Footprint"];

/// The meta key the declared-type strings travel under.
pub const DECLARED_TYPE_KEY: &str = "declared_type";

/// One DEVICE document's model-visible metadata, keyed in the projection by its
/// uuid.
///
/// Every optional field is **absent** rather than empty: `_collect_device_meta`
/// only writes a key it has a value for, and `""` would be a value the Python
/// side could only reproduce by inventing the same placeholder.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct DeviceMeta {
    pub title: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub lcsc_part: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mpn: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub manufacturer: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub datasheet: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub footprint: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub name_template: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub symbol: Option<String>,
    #[serde(rename = "declared_type", skip_serializing_if = "Option::is_none")]
    pub declared_type: Option<BTreeMap<String, String>>,
    /// `"yes"`/`"no"` — and **absent** for a `META` whose `attributes` is not an
    /// object, which is a different statement from `"no"`.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub is_part: Option<String>,
}

impl DeviceMeta {
    fn titled(title: String) -> Self {
        Self {
            title,
            lcsc_part: None,
            mpn: None,
            manufacturer: None,
            datasheet: None,
            footprint: None,
            name_template: None,
            symbol: None,
            declared_type: None,
            is_part: None,
        }
    }

    /// Fill the six [`DEVICE_ATTR_FIELDS`] values from one `attributes` object.
    ///
    /// `str(value).strip()`, and `"null"` is the editor's literal for "unset"
    /// (006 finding), so a stale string cannot outrank a real value. A `null`
    /// *value* is skipped before `str()` runs — `str(None)` would spell `"None"`
    /// and be kept as if it were a value.
    fn fill_fields(&mut self, attributes: &Map<String, Value>) {
        for (key, field) in DEVICE_ATTR_FIELDS {
            let Some(value) = attributes.get(key).filter(|value| !value.is_null()) else {
                continue;
            };
            let text = python_text(value)
                .trim_matches(python_whitespace)
                .to_owned();
            if text.is_empty() || text == "null" {
                continue;
            }
            match field {
                "lcsc_part" => self.lcsc_part = Some(text),
                "mpn" => self.mpn = Some(text),
                "manufacturer" => self.manufacturer = Some(text),
                "datasheet" => self.datasheet = Some(text),
                "footprint" => self.footprint = Some(text),
                _ => self.name_template = Some(text),
            }
        }
    }
}

/// The `boardwise.device-library/1` document.
#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DeviceLibraryProjection {
    pub schema: String,
    pub devices: BTreeMap<String, DeviceMeta>,
    /// Later documents under a uuid whose meta differs from the first one's.
    pub conflicting_documents: usize,
}

/// Group the DEVICE documents of one record stream into the projection.
///
/// Records outside a `DEVICE` document are not read — the document gate is the
/// one `uuid` variable Python keeps, and a `DOCHEAD` that is not a `DEVICE` (or
/// carries no uuid) resets it, so the records that follow belong to no device.
pub fn project_library(records: &[EpruRecord]) -> DeviceLibraryProjection {
    let mut devices: BTreeMap<String, DeviceMeta> = BTreeMap::new();
    let mut conflicting_documents = 0usize;
    let mut uuid = String::new();
    // Whether the *current* document's first `META` has already been read: per
    // document, not per uuid.
    let mut read_meta = false;
    for record in records {
        if record.record_type == DOCHEAD_RECORD_TYPE {
            uuid = match record.doc_type.as_deref() {
                Some(DEVICE_DOC_TYPE) => {
                    str_or_empty(record.body.as_ref().and_then(|body| body.get("uuid")))
                }
                _ => String::new(),
            };
            read_meta = false;
            continue;
        }
        if uuid.is_empty() || record.record_type != "META" || read_meta {
            continue;
        }
        read_meta = true;
        let meta = read_meta_body(record.body.as_ref());
        match devices.get(&uuid) {
            None => {
                devices.insert(uuid.clone(), meta);
            }
            Some(first) => {
                // First-wins keeps `first` untouched; only whether the reading
                // would differ decides the count.
                if first != &meta {
                    conflicting_documents += 1;
                }
            }
        }
    }
    DeviceLibraryProjection {
        schema: DEVICE_LIBRARY_SCHEMA.to_owned(),
        devices,
        conflicting_documents,
    }
}

/// Read one `META` body into [`DeviceMeta`] with Python's exact guard order.
fn read_meta_body(body: Option<&Map<String, Value>>) -> DeviceMeta {
    let mut meta = DeviceMeta::titled(trimmed_text(body.and_then(|body| body.get("title"))));
    // `attributes = body.get("attributes") or {}` — a **falsy** value (including
    // an empty array, an empty string, `0` and `null`) is the empty object, while
    // a truthy non-object is not an object at all and leaves the meta title-only.
    let empty = Map::new();
    let attributes = match body
        .and_then(|body| body.get("attributes"))
        .filter(|value| python_truthy(value))
    {
        None => Some(&empty),
        Some(Value::Object(object)) => Some(object),
        // A truthy non-object: only the title survives, and `is_part` is never
        // written — a different document from one that says `"no"`.
        Some(_) => None,
    };
    let Some(attributes) = attributes else {
        return meta;
    };
    meta.fill_fields(attributes);
    // The DEVICE's own Symbol uuid is the library symbol *as saved in the
    // library*, which can differ from the instance's stale copy.
    meta.symbol = declared_text(attributes, "Symbol");
    let declared: BTreeMap<String, String> = DECLARED_TYPE_KEYS
        .iter()
        .filter_map(|key| {
            let text = declared_text(attributes, key)?;
            Some(((*key).to_owned(), text))
        })
        .collect();
    if !declared.is_empty() {
        meta.declared_type = Some(declared);
    }
    // Whether the *library* device is a part or a symbol: a real part's META
    // declares the designator it will be assigned.
    meta.is_part = Some(
        if str_or_empty(attributes.get("Designator"))
            .trim_matches(python_whitespace)
            .is_empty()
        {
            "no".to_owned()
        } else {
            "yes".to_owned()
        },
    );
    meta
}

/// `str(attributes.get(key) or "").strip()`, omitted when that is empty or the
/// editor's `"null"`: the spelling the symbol, the declared-type keys and a
/// `Designator` are read with.
fn declared_text(attributes: &Map<String, Value>, key: &str) -> Option<String> {
    let text = str_or_empty(attributes.get(key))
        .trim_matches(python_whitespace)
        .to_owned();
    if text.is_empty() || text == "null" {
        return None;
    }
    Some(text)
}

/// `str(value or "").strip()` for a value that may be a field of an absent body.
fn trimmed_text(value: Option<&Value>) -> String {
    str_or_empty(value)
        .trim_matches(python_whitespace)
        .to_owned()
}

/// `str(value or "")` — Python's falsy-to-empty-string idiom, which is what the
/// reader uses for a uuid, a title, a `Designator` and an attribute value.
fn str_or_empty(value: Option<&Value>) -> String {
    match value {
        Some(value) if python_truthy(value) => python_text(value),
        _ => String::new(),
    }
}
