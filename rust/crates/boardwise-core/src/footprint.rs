//! The `.epru` **FOOTPRINT library** — the archive's own `id -> 封装名` table.
//!
//! A field-for-field port of `boardwise.parsers.schematic._collect_footprint_titles`:
//! a schematic's `Footprint` attribute may store the *library footprint uuid*
//! rather than a name, and the same archive carries the `FOOTPRINT` document that
//! uuid names, with the footprint's name in its `META.title`. This module is that
//! lookup table, and the one reading it makes possible — [`resolve_declared`],
//! the port of `_resolve_declared_footprint`: no geometry, no rule, no drawing
//! decision.
//!
//! Four rules, each with a shape that looks like a shortcut and is not:
//!
//! 1. **Only a `FOOTPRINT` document opens a uuid.** Python keeps one `uuid`
//!    variable and resets it to `""` on every other `DOCHEAD`, so the records that
//!    follow belong to no footprint; a `FOOTPRINT` `DOCHEAD` with no uuid opens
//!    nothing either.
//! 2. **Only the document's first `META` is read.** An empty title still occupies
//!    the entry (`uuid: ""`) and keeps the document's later `META`s out — "the
//!    footprint is named nothing" is a reading, "there is no footprint" is not.
//! 3. **`title` is `str(body.get("title") or "").strip()`.** A `null` title is
//!    `""`, and — unlike the DEVICE library's attribute values — the editor's
//!    literal `"null"` is **kept**: this reader has no such exclusion, and adding
//!    one here would be a second reading.
//! 4. **A repeated uuid is first-wins across documents too**, because the entry
//!    written by the first document is already there when the copy's `META`
//!    arrives.
//!
//! `attributes`, `editVersion`, the element numbering and the order the records
//! were written are never read.

use serde::Serialize;
use serde_json::Value;
use std::collections::BTreeMap;

use crate::epru::{DOCHEAD_RECORD_TYPE, EpruRecord, python_text};
use crate::{python_truthy, python_whitespace};

/// Schema tag of the FOOTPRINT library projection.
pub const FOOTPRINT_LIBRARY_SCHEMA: &str = "boardwise.footprint-library/1";

/// Schema tag of the declared-footprint resolution.
pub const FOOTPRINT_DECLARED_SCHEMA: &str = "boardwise.footprint-declared/1";

/// The two segment lengths a raw library id is made of: 16 or 32 hex digits.
const LIBRARY_ID_SEGMENT_LENGTHS: [usize; 2] = [16, 32];

/// The `boardwise.footprint-declared/1` document: what one schematic `Footprint`
/// field declared, and the raw library id when that is what it declared.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct DeclaredFootprintProjection {
    pub schema: String,
    pub footprint: String,
    #[serde(rename = "libraryId")]
    pub library_id: String,
}

/// `(footprint name, raw library id)` for one declared field, read against one
/// archive's `uuid -> title` table.
///
/// The `(text, "")` pair is the two failures Python folds into one spelling: a
/// real name, an empty field and an id this archive does not name are all "not
/// resolved", and `""` as the id is how the projection says so. Only a hit whose
/// title is non-empty names a footprint *and* keeps the id beside it — the raw
/// value must survive, because "the editor wrote an id" and "the editor wrote a
/// name" are two different statements about the file.
///
/// A hit whose title is empty resolves to nothing on purpose: `uuid: ""` is the
/// library reader's way of saying "this footprint is named nothing", which is a
/// reading, not a name.
pub fn resolve_declared(value: &str, titles: &BTreeMap<String, String>) -> (String, String) {
    let text = value.trim_matches(python_whitespace).to_owned();
    if text.is_empty() || !is_library_id(&text) {
        return (text, String::new());
    }
    match titles.get(&text) {
        Some(title) if !title.is_empty() => (title.clone(), text),
        _ => (text, String::new()),
    }
}

/// Resolve one declared field against one record stream.
///
/// The titles are [`project_library`]'s — the same table, read once — so the
/// resolution cannot disagree with the library projection about what this archive
/// names.
pub fn project_declared(records: &[EpruRecord], value: &str) -> DeclaredFootprintProjection {
    let library = project_library(records);
    let (footprint, library_id) = resolve_declared(value, &library.footprints);
    DeclaredFootprintProjection {
        schema: FOOTPRINT_DECLARED_SCHEMA.to_owned(),
        footprint,
        library_id,
    }
}

/// `FOOTPRINT_ID_RE`, hand-written: one or more `_`-joined segments, each exactly
/// 16 or 32 **ASCII** hex digits, case-insensitive, whole string.
///
/// Written out rather than compiled because this crate takes no `regex`
/// dependency outside the contract validator. The shapes that look close and are
/// refused: an empty segment (a leading, doubled or trailing `_`), any other
/// length, and a non-ASCII digit — Python's `[0-9a-fA-F]` is ASCII-only too.
///
/// Public so the corpus test can pin the matcher itself, not only its answers.
pub fn is_library_id(text: &str) -> bool {
    !text.is_empty()
        && text.split('_').all(|segment| {
            LIBRARY_ID_SEGMENT_LENGTHS.contains(&segment.len())
                && segment.chars().all(|c| c.is_ascii_hexdigit())
        })
}

/// The document type [`project_library`] reads. Every other document is skipped,
/// exactly like `_collect_footprint_titles`'s `uuid = ""`.
pub const FOOTPRINT_DOC_TYPE: &str = "FOOTPRINT";

/// The `boardwise.footprint-library/1` document: uuid → the document's `META`
/// title, and nothing else.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct FootprintLibraryProjection {
    pub schema: String,
    pub footprints: BTreeMap<String, String>,
}

/// Group the FOOTPRINT documents of one record stream into the projection.
pub fn project_library(records: &[EpruRecord]) -> FootprintLibraryProjection {
    let mut footprints: BTreeMap<String, String> = BTreeMap::new();
    let mut uuid = String::new();
    for record in records {
        if record.record_type == DOCHEAD_RECORD_TYPE {
            uuid = if record.doc_type.as_deref() == Some(FOOTPRINT_DOC_TYPE) {
                str_or_empty(record.body.as_ref().and_then(|body| body.get("uuid")))
            } else {
                String::new()
            };
            continue;
        }
        if uuid.is_empty() || record.record_type != "META" {
            continue;
        }
        // Python tests `uuid in titles` *before* it reads the title, so a later
        // `META` — of this document or of a copy filed under the same uuid — is
        // not read at all; an empty first title still holds the entry.
        footprints.entry(uuid.clone()).or_insert_with(|| {
            trimmed_text(record.body.as_ref().and_then(|body| body.get("title")))
        });
    }
    FootprintLibraryProjection {
        schema: FOOTPRINT_LIBRARY_SCHEMA.to_owned(),
        footprints,
    }
}

/// `str(value or "").strip()` — the title's own reading, with no `"null"` rule.
fn trimmed_text(value: Option<&Value>) -> String {
    str_or_empty(value)
        .trim_matches(python_whitespace)
        .to_owned()
}

/// `str(value or "")` — Python's falsy-to-empty-string idiom, which is what the
/// reader uses for a document uuid and for a title.
fn str_or_empty(value: Option<&Value>) -> String {
    match value {
        Some(value) if python_truthy(value) => python_text(value),
        _ => String::new(),
    }
}
