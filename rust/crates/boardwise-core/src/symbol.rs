//! The `.epru` **SYMBOL library** — pin number to point, ref, name and type.
//!
//! A field-for-field port of `boardwise.parsers.schematic._collect_symbols` and
//! `_commit_symbol`: the same two phases, the same two indexes, the same
//! first-writer-wins fields, so the projection below is the document the Python
//! differential runner derives from the same text.
//!
//! Two phases, and the order is the whole point. Every `PIN` of a document is
//! collected **first**, so an `ATTR` that names its pin by `parentId` can be
//! filed even when it sits before the `PIN`, or in a block after the last one
//! (3.2.186's incremental save writes both shapes). Then the pin attributes are
//! attributed in stream order:
//!
//! 1. to the run its `parentId` names, by the PIN row's own `id` first and by the
//!    format's ref second — the two can *collide across pins* (a V3 `.epro2`
//!    synthesises `e<zIndex>` while a row may carry any `id`), and indexing them
//!    into one map hands one pin's attributes to its neighbour;
//! 2. otherwise to the **open run** (the last `PIN` seen) when it still misses
//!    the key — the stream-adjacency rule, kept as the fallback.
//!
//! A field is never overwritten, so a duplicate attribute cannot move a value
//! that is already placed. A run that ends the document with no `Pin Number` is
//! counted (`pins_dropped_no_number`) and dropped: there is no key to file it
//! under, and guessing one is how a number-only identity becomes a false bank of
//! differences.
//!
//! A repeated document uuid merges **first-wins**; `conflicting_documents`
//! counts a later copy that is *not* the same **definition** (a pin more, a
//! moved pin, another name) and stays 0 for the copies a V4 export repeats page
//! by page, which differ only in `editVersion`, in the order their records were
//! written, or in the element numbering their document happens to use. The
//! comparison is the definition the model reads — title, pin number → point,
//! name and type — and **not** a pin's `ref`, which is a document-local handle
//! ([`SymbolView::same_definition`]); the first copy's refs survive first-wins
//! untouched.
//!
//! Nothing here knows what a symbol is *for*: no netlist, no review rule, no
//! drawing decision.

use serde::Serialize;
use serde_json::{Map, Value};
use std::collections::{BTreeMap, HashMap};

use crate::epru::{DOCHEAD_RECORD_TYPE, EpruRecord, python_text};
use crate::{ContractError, Result, python_whitespace};

/// Schema tag of the library projection.
pub const SYMBOL_LIBRARY_SCHEMA: &str = "boardwise.symbol-library/1";

/// The document type [`project_library`] reads. Every other document is
/// skipped, exactly like `_collect_symbols`' `buffering` flag.
pub const SYMBOL_DOC_TYPE: &str = "SYMBOL";

/// The three `ATTR` keys that describe one pin. Everything else a SYMBOL
/// document carries (`Device`, `Value`, `Add into BOM`) describes the symbol or
/// an element, not a pin.
pub const PIN_ATTR_KEYS: [&str; 3] = ["Pin Number", "Pin Name", "Pin Type"];

/// How a `PIN` row is addressed: the synthesised `e<zIndex>` a V3 `.epro2`
/// writes (its NO_CONNECT parents carry `-e<zIndex>`), or the row's own envelope
/// `id`, which is what an eprj3 folder's `ATTR parentId` names.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PinKey {
    ZIndex,
    PinId,
}

impl PinKey {
    /// The contract's `pinKey` enum, refused by name for anything else.
    pub fn parse(value: &str) -> Result<Self> {
        match value {
            "zIndex" => Ok(Self::ZIndex),
            "pin_id" => Ok(Self::PinId),
            other => Err(ContractError::Shape(format!(
                "unknown symbol pinKey {other:?}"
            ))),
        }
    }

    /// The spelling the projection states back.
    pub fn as_str(self) -> &'static str {
        match self {
            Self::ZIndex => "zIndex",
            Self::PinId => "pin_id",
        }
    }
}

/// One pin of a symbol, in the projection's spelling.
///
/// `point` is **canvas space** — `y` is already negated and rounded to six
/// decimals — so a consumer must never flip it again. `name`/`type` are absent
/// rather than empty: a pin the library never named has no name.
///
/// `ref` is a **handle inside one document** (see [`PinKey`]), not part of the
/// pin's definition — which is why [`SymbolView::same_definition`], and never a
/// structural comparison of this struct, decides whether two copies of a uuid
/// disagree.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct PinView {
    pub point: (f64, f64),
    #[serde(rename = "ref")]
    pub reference: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
    #[serde(rename = "type", skip_serializing_if = "Option::is_none")]
    pub type_name: Option<String>,
}

/// One SYMBOL library document, keyed in the projection by its uuid.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct SymbolView {
    pub title: String,
    /// Pin **number** to pin. Numbers are a string key on purpose: a library
    /// spells them `1`, `A1B12`, `B5`.
    pub pins: BTreeMap<String, PinView>,
}

impl SymbolView {
    /// Is this the **same definition** as another copy of one uuid?
    ///
    /// Everything a reading of the part depends on — title, pin number →
    /// *point*, pin name, pin type — and deliberately **not** each pin's `ref`.
    /// A ref is document-local numbering (`e<zIndex>` for a V3 `.epro2`, the
    /// PIN row's own `id` for eprj3), so a copy that renumbers its elements
    /// while describing the same part (same points, same names, same types) is
    /// the same definition and must not read as a conflict. The first copy's
    /// refs stay in the projection untouched — that is what first-wins means.
    ///
    /// This is the Python `_symbol_definition` relation. Structural equality of
    /// [`PinView`] would include `ref` and answer a different question, which is
    /// why the merge calls this instead.
    fn same_definition(&self, other: &Self) -> bool {
        self.title == other.title
            && self.pins.len() == other.pins.len()
            && self.pins.iter().all(|(number, pin)| {
                other.pins.get(number).is_some_and(|copy| {
                    pin.point == copy.point
                        && pin.name == copy.name
                        && pin.type_name == copy.type_name
                })
            })
    }
}

/// The `boardwise.symbol-library/1` document.
#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SymbolLibraryProjection {
    pub schema: String,
    pub pin_key: String,
    pub symbols: BTreeMap<String, SymbolView>,
    /// Runs that ended a document with no `Pin Number`: dropped, counted, never
    /// guessed at.
    pub pins_dropped_no_number: usize,
    /// Later documents under a uuid whose symbol differs from the first one's.
    pub conflicting_documents: usize,
}

#[derive(Debug, Default)]
struct Counts {
    pins_dropped_no_number: usize,
    conflicting_documents: usize,
}

/// One `PIN` record of a document, mutable because its attributes may arrive
/// after the next `PIN` has opened.
#[derive(Debug)]
struct Run {
    point: (f64, f64),
    reference: String,
    number: String,
    name: String,
    type_name: String,
}

impl Run {
    /// Write one pin attribute unless the field already carries one; `false`
    /// means "try the next candidate", which is what stops a duplicate
    /// attribute from overwriting a value that is already placed.
    fn fill(&mut self, key: &str, value: &str) -> bool {
        let field = match key {
            "Pin Number" => &mut self.number,
            "Pin Name" => &mut self.name,
            _ => &mut self.type_name,
        };
        if !field.is_empty() {
            return false;
        }
        *field = value.to_owned();
        true
    }
}

/// Group the SYMBOL documents of one record stream into the projection.
///
/// Records outside a `SYMBOL` document are not read (Python's `buffering`), and
/// a `DOCHEAD` without a `docType` drops the records that follow it.
pub fn project_library(records: &[EpruRecord], pin_key: PinKey) -> Result<SymbolLibraryProjection> {
    let mut symbols: BTreeMap<String, SymbolView> = BTreeMap::new();
    let mut counts = Counts::default();
    let mut buffer: Vec<&EpruRecord> = Vec::new();
    let mut buffering = false;
    for record in records {
        if record.record_type == DOCHEAD_RECORD_TYPE {
            if buffering {
                commit(&buffer, &mut symbols, &mut counts, pin_key)?;
            }
            buffer.clear();
            buffering = record.doc_type.as_deref() == Some(SYMBOL_DOC_TYPE);
            if buffering {
                buffer.push(record);
            }
            continue;
        }
        if buffering {
            buffer.push(record);
        }
    }
    if buffering {
        commit(&buffer, &mut symbols, &mut counts, pin_key)?;
    }
    Ok(SymbolLibraryProjection {
        schema: SYMBOL_LIBRARY_SCHEMA.to_owned(),
        pin_key: pin_key.as_str().to_owned(),
        symbols,
        pins_dropped_no_number: counts.pins_dropped_no_number,
        conflicting_documents: counts.conflicting_documents,
    })
}

/// Turn one buffered SYMBOL document into a [`SymbolView`].
fn commit(
    records: &[&EpruRecord],
    symbols: &mut BTreeMap<String, SymbolView>,
    counts: &mut Counts,
    pin_key: PinKey,
) -> Result<()> {
    let mut uuid = String::new();
    let mut title = String::new();
    let mut runs: Vec<Run> = Vec::new();
    // Two indexes, never one: see the identifier-collision note in the module
    // doc. `by_id` answers a `parentId` first, `by_ref` is the format's own
    // spelling, and both keep the **first** run that claims a name.
    let mut by_id: HashMap<String, usize> = HashMap::new();
    let mut by_ref: HashMap<String, usize> = HashMap::new();

    for record in records {
        if record.record_type == DOCHEAD_RECORD_TYPE {
            uuid = str_or_empty(record.body.as_ref().and_then(|body| body.get("uuid")));
            continue;
        }
        let Some(body) = record.body.as_ref() else {
            // An empty (or non-object) body is nothing to read: the record is
            // skipped, never turned into a key or a position. Already counted as
            // an empty-body record by the stream scan.
            continue;
        };
        match record.record_type.as_str() {
            // A META is assigned, not merged: the last one wins, like Python.
            "META" => title = str_or_empty(body.get("title")),
            "PIN" => {
                let index = runs.len();
                runs.push(Run {
                    point: pin_point(body)?,
                    reference: pin_ref(record, pin_key),
                    number: String::new(),
                    name: String::new(),
                    type_name: String::new(),
                });
                if let Some(id) = record
                    .envelope_id
                    .as_ref()
                    .filter(|value| python_truthy(value))
                {
                    by_id.entry(python_text(id)).or_insert(index);
                }
                by_ref.entry(runs[index].reference.clone()).or_insert(index);
            }
            _ => {}
        }
    }

    let mut open_run: Option<usize> = None;
    for record in records {
        if record.record_type == DOCHEAD_RECORD_TYPE {
            open_run = None;
            continue;
        }
        let Some(body) = record.body.as_ref() else {
            continue; // same skip: no key, and no ``parentId`` to file by
        };
        if record.record_type == "PIN" {
            let id_key = str_or_empty(record.envelope_id.as_ref());
            open_run = by_id
                .get(&id_key)
                .or_else(|| by_ref.get(&pin_ref(record, pin_key)))
                .copied();
            continue;
        }
        if record.record_type != "ATTR" {
            continue;
        }
        let Some(key) = body.get("key").map(python_text) else {
            continue;
        };
        if !PIN_ATTR_KEYS.contains(&key.as_str()) {
            continue;
        }
        let value = str_or_empty(body.get("value"))
            .trim_matches(python_whitespace)
            .to_owned();
        if value.is_empty() || value == "null" {
            continue;
        }
        let named = by_id
            .get(&str_or_empty(body.get("parentId")))
            .or_else(|| by_ref.get(&str_or_empty(body.get("parentId"))))
            .copied();
        for candidate in [named, open_run].into_iter().flatten() {
            if runs[candidate].fill(&key, &value) {
                break;
            }
        }
    }

    // Three maps, not one: Python files a repeated pin number per **field** —
    // `pins[number]` takes the last run's point and ref, while `pin_names` and
    // `pin_types` only take a value that run actually carries. Replacing a
    // whole `PinView` would let a later nameless duplicate erase a name that is
    // already placed.
    let mut points: BTreeMap<String, (f64, f64)> = BTreeMap::new();
    let mut references: BTreeMap<String, String> = BTreeMap::new();
    let mut names: BTreeMap<String, String> = BTreeMap::new();
    let mut types: BTreeMap<String, String> = BTreeMap::new();
    for run in runs {
        if run.number.is_empty() {
            counts.pins_dropped_no_number += 1;
            continue;
        }
        // Point and ref are last-wins; name and type are last-**non-empty**-wins,
        // each on its own, so a duplicate run cannot clear a field it omits.
        points.insert(run.number.clone(), run.point);
        references.insert(run.number.clone(), run.reference);
        if !run.name.is_empty() {
            names.insert(run.number.clone(), run.name);
        }
        if !run.type_name.is_empty() {
            types.insert(run.number.clone(), run.type_name);
        }
    }
    let pins: BTreeMap<String, PinView> = points
        .into_iter()
        .map(|(number, point)| {
            let pin = PinView {
                point,
                reference: references.remove(&number).unwrap_or_default(),
                name: names.remove(&number),
                type_name: types.remove(&number),
            };
            (number, pin)
        })
        .collect();
    let symbol = SymbolView { title, pins };
    if uuid.is_empty() {
        // A document with no uuid is no library symbol; nothing to merge.
        return Ok(());
    }
    match symbols.get(&uuid) {
        None => {
            symbols.insert(uuid, symbol);
        }
        Some(first) => {
            // First-wins keeps `first` and its refs untouched; only the
            // *definition* decides whether the drop is reported.
            if !first.same_definition(&symbol) {
                counts.conflicting_documents += 1;
            }
        }
    }
    Ok(())
}

/// `str(value or "")` — Python's falsy-to-empty-string idiom, which is what the
/// reader uses for a uuid, a title, an attribute value and a `parentId`.
fn str_or_empty(value: Option<&Value>) -> String {
    match value {
        Some(value) if python_truthy(value) => python_text(value),
        _ => String::new(),
    }
}

/// Python truthiness of a decoded JSON value. Only `None`, `False`, `0`, `""`
/// and the empty containers are falsy; `float("nan")` is truthy here and in
/// Python (`bool(nan)` is `True`).
fn python_truthy(value: &Value) -> bool {
    match value {
        Value::Null => false,
        Value::Bool(flag) => *flag,
        Value::Number(number) => number.as_f64().is_none_or(|value| value != 0.0),
        Value::String(text) => !text.is_empty(),
        Value::Array(items) => !items.is_empty(),
        Value::Object(fields) => !fields.is_empty(),
    }
}

/// The key that ties a PIN to the attributes naming it. `pin_id` uses the row's
/// own envelope id when it has one; both fall back to `e<zIndex>`, and
/// `str(None)` is how Python spells a missing zIndex (`eNone`).
fn pin_ref(record: &EpruRecord, pin_key: PinKey) -> String {
    if pin_key == PinKey::PinId
        && let Some(id) = record
            .envelope_id
            .as_ref()
            .filter(|value| python_truthy(value))
    {
        return python_text(id);
    }
    let z_index = record.body.as_ref().and_then(|body| body.get("zIndex"));
    match z_index {
        Some(value) => format!("e{}", python_text(value)),
        None => format!("e{}", python_text(&Value::Null)),
    }
}

/// `(round(float(x), 6), round(-float(y), 6))` — the point in canvas space.
fn pin_point(body: &Map<String, Value>) -> Result<(f64, f64)> {
    let x = round_coordinate(to_float(body.get("x"))?);
    let y = round_coordinate(-to_float(body.get("y"))?);
    if !x.is_finite() || !y.is_finite() {
        // Python would emit `Infinity`, which is not JSON and which the
        // canonical comparison refuses; refusing the record states the same
        // thing at the same gate.
        return Err(ContractError::Shape(format!(
            "a SYMBOL pin coordinate is not finite: ({x}, {y})"
        )));
    }
    Ok((x, y))
}

/// `float(value or 0)`: a missing, null or otherwise falsy coordinate is 0, a
/// number reads through `f64`, and a numeric string is parsed the way Python's
/// `float()` parses one. Anything else is a request failure on both sides —
/// Python raises `TypeError`/`ValueError` there.
fn to_float(value: Option<&Value>) -> Result<f64> {
    let Some(value) = value else { return Ok(0.0) };
    if !python_truthy(value) {
        return Ok(0.0);
    }
    match value {
        Value::Bool(_) => Ok(1.0), // the only truthy boolean
        Value::Number(number) => number.as_f64().ok_or_else(|| {
            ContractError::Shape(format!("a SYMBOL pin coordinate is not a float: {number}"))
        }),
        Value::String(text) => text
            .trim_matches(python_whitespace)
            .parse::<f64>()
            .map_err(|_| {
                ContractError::Shape(format!("a SYMBOL pin coordinate is not a number: {text:?}"))
            }),
        other => Err(ContractError::Shape(format!(
            "a SYMBOL pin coordinate is neither a number nor a string: {other}"
        ))),
    }
}

/// `round(value, 6)` — correctly rounded decimal rounding, half to even.
///
/// Not `(value * 1e6).round() / 1e6`: that scales the *binary* value and can
/// land on the neighbouring double, while CPython rounds the value's exact
/// decimal expansion and returns the nearest double to that decimal. Formatting
/// to six decimals is the same computation `{:.6}` performs exactly, and
/// re-parsing gives the nearest double.
fn round_coordinate(value: f64) -> f64 {
    if !value.is_finite() {
        return value;
    }
    format!("{value:.6}").parse::<f64>().unwrap_or(value)
}
