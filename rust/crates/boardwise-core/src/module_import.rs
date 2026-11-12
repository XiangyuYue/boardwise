//! 038Q2: the offline half of seeding the module library from upstream data.
//!
//! Two upstream shapes exist (`block_template` and `role_topology`). Neither is
//! this repository's circuit contract, and neither may be republished as it
//! stands: the raw files carry free text (`desc`, `validated`, `source`,
//! `schematic_layout`, `bom_note`) that can name historical projects. So the
//! redacted copies under `contracts/module-import/` are the only input, the
//! output is `boardwise-circuit-spec` v1, and everything the circuit contract
//! has no slot for (directory, maturity, wildcard pins, device identity hints,
//! upstream verification status) rides in a thin sidecar catalog.
//!
//! What this module refuses, on purpose:
//!
//! * a port with no curated direction/class — `dir: "in"` in the upstream file
//!   is **not** `source`, and guessing would turn a vocabulary mismatch into a
//!   wrong electrical claim;
//! * `qty != 1` — copying a part to satisfy a quantity would invent a second
//!   instance with its own connectivity;
//! * a `PORT:` token whose port the source does not declare, a role/pin that
//!   does not exist, a net with no members, a pin on two nets, a port that is
//!   not a member of its own net, and (role topology) `pins[].net` disagreeing
//!   with `nets[].members` in either direction;
//! * coordinates and layout prose: nothing here reads them, and the circuit
//!   contract rejects a document that carries one.
//!
//! Everything it writes is a **candidate**: every fact is `ai_asserted` (the
//! conservative tier for "this repository has not verified it"), `draft` is
//! true, and the catalog says `identityStatus: "unverified"` and
//! `notForDrawCompile: true`. A catalog part's `symbolRef` is empty because no
//! symbol was identified; a CircuitSpec part's `symbolRef` **cannot** be empty
//! (its loader requires a non-empty string), so it carries the
//! `GENERIC-<role>` placeholder — that is not a resolved identity, and a device
//! UUID is never put in that field. Nothing here claims compose readiness,
//! native CBB compatibility, PCB or hardware validation.
//!
//! 038Q10 adds **one** opt-in on top of that: a curation asset may say
//! `identityBinding: "book"`, and then every part of that module must resolve
//! through the managed symbol book (`blocklib/symbols/`) to a real `symbolRef`
//! in both the catalog and the CircuitSpec. The book's whole-file digest, each
//! profile's digest, each binding's deviceUuid/LCSC/MPN and every `role.pin`
//! (matched against a pin number or pin name, exactly) are re-checked here; a
//! module that keeps a wildcard pin and a `role_topology` asset may not be bound
//! at all. Assets that do not ask keep the GENERIC path above, byte for byte.
//! The book is read as an **input** — never copied into the output directory —
//! and the full geometry contract still lives in `tools/check_symbol_book.py`.
//!
//! 038Q12 adds the electrical half of the same opt-in: a bound block may state
//! `pinGroups` (`<role>.<pin>*` → explicit physical pins), `portPins` (the pads a
//! port whose name matches several pins is on) and `nc` (explicit no-connects).
//! Each member resolves to exactly one profile pin — number or name, exact, and a
//! name two pins share resolves to neither — a group may not be missing, extra,
//! empty or cross-role, an NC may not sit on a net, and every profile pin ends up
//! connected, NC or `unstatedPins`. No wildcard is expanded by prefix: the mapping
//! is a human decision recorded in curation, and an unbound asset may not state
//! one at all.

use serde_json::{Map, Value, json};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::{Component, Path, PathBuf};

use crate::{ContractError, Result};

/// The versioned input contract that records the human port rulings.
pub const CURATION_SCHEMA: &str = "boardwise.module-import-curation/1";
/// The thin sidecar a consumer reads before it trusts a candidate.
pub const CATALOG_SCHEMA: &str = "boardwise.module-catalog/1";
/// Input/output digests for one import run.
pub const MANIFEST_SCHEMA: &str = "boardwise.module-import-manifest/1";
/// The provenance ledger the curation points at (originals + redacted copies).
pub const SOURCE_MANIFEST_SCHEMA: &str = "boardwise.module-import-source-manifest/1";
/// The ledger's own name for the upstream licence entry.
pub const LICENSE_UPSTREAM_PATH: &str = "LICENSE";
/// Where the published copy of that licence goes, inside the output directory.
pub const LICENSE_OUTPUT_PATH: &str = "upstream/LICENSE";
/// Paths the importer writes itself; an asset may not claim one of them.
pub const RESERVED_OUTPUT_PATHS: [&str; 3] = ["catalog.json", "manifest.json", "upstream/LICENSE"];
/// What the CLI prints on success.
pub const REPORT_SCHEMA: &str = "boardwise.module-import-report/1";
/// The circuit contract this module targets (`core/circuitspec.py`).
pub const CIRCUIT_SPEC_KIND: &str = "boardwise-circuit-spec";
pub const CIRCUIT_SPEC_VERSION: u64 = 1;
/// The tier every imported fact gets: "this repository has not verified it".
pub const PROVENANCE_AI: &str = "ai_asserted";
pub const AUTO_NET_PREFIX: &str = "auto:";
pub const PORT_NET_PREFIX: &str = "port.";
pub const MATURITY_CANDIDATE: &str = "candidate";
pub const IDENTITY_UNVERIFIED: &str = "unverified";
/// The circuit contract refuses an *empty* `symbolRef`, and this batch has not
/// read any host symbol. A placeholder in the repository's existing
/// "no real library profile" namespace is the honest middle: it is not a device
/// UUID, it resolves to nothing, and the catalog still says `symbolRef: ""`
/// because no symbol has been identified.
pub const GENERIC_SYMBOL_PREFIX: &str = "GENERIC-";

/// The curation key that opts a run into a managed symbol book (038Q10).
pub const SYMBOL_BOOK_KEY: &str = "symbolBook";
/// The only `identityBinding` value this batch supports.
pub const IDENTITY_BINDING_BOOK: &str = "book";
/// The only global identity default this batch supports: an asset must ask.
pub const DEFAULT_IDENTITY_GENERIC: &str = "generic";
/// The book index schema this build reads (`blocklib/symbols/index.json`).
pub const SYMBOL_BOOK_SCHEMA: &str = "boardwise.symbol-book/1";
/// The catalog status of a module whose every part resolved to a book profile.
pub const IDENTITY_BOUND: &str = "bound";

pub const NET_CLASSES: [&str; 4] = ["power", "gnd", "signal", "other"];
pub const PORT_DIRECTIONS: [&str; 5] = ["source", "load", "input", "output", "feedback"];

/// One file the run wants to write, relative to the `--output` directory.
#[derive(Debug, Clone, PartialEq)]
pub struct OutputFile {
    pub path: String,
    pub bytes: String,
}

/// One normalised module: its id, where its circuit file goes, and the document.
#[derive(Debug, Clone, PartialEq)]
pub struct ImportedModule {
    pub id: String,
    pub path: String,
    pub circuit: Value,
}

#[derive(Debug, Clone, PartialEq)]
pub struct ImportPlan {
    pub modules: Vec<ImportedModule>,
    pub files: Vec<OutputFile>,
}

impl ImportPlan {
    /// The module ids in output order.
    pub fn module_ids(&self) -> Vec<&str> {
        self.modules
            .iter()
            .map(|module| module.id.as_str())
            .collect()
    }
}

/// Read every input, normalise every module, and hash the result — but write
/// nothing. A caller that gets an `Err` has no partial set of files.
pub fn plan(root: &Path, curation_path: &Path) -> Result<ImportPlan> {
    let curation = read_object(curation_path, "curation")?;
    expect_text(&curation, "schema", "curation", CURATION_SCHEMA)?;
    let upstream = object_field(&curation, "upstream", "curation")?;
    let repo = text_field(upstream, "repo", "curation.upstream")?.to_owned();
    let commit = text_field(upstream, "commit", "curation.upstream")?.to_owned();

    let mut inputs: BTreeMap<String, String> = BTreeMap::new();
    let standard_parts_rel = text_field(&curation, "standardParts", "curation")?.to_owned();
    let standard_parts_path = relative_input(root, &standard_parts_rel, "curation.standardParts")?;
    let standard_parts = read_hashed(&standard_parts_path, root, &mut inputs)?;
    let library_uuid = text_field(&standard_parts, "libraryUuid", "standard-parts")?.to_owned();
    let library = object_field(&standard_parts, "parts", "standard-parts")?;

    inputs.insert(
        display_path(root, curation_path),
        file_sha256(curation_path)?,
    );

    // The derivative manifest is the provenance ledger: it must agree with the
    // curation (same upstream, same originals, same redacted bytes) or the run
    // is refused. It is also an input, so its own digest is in the output.
    let source_manifest_rel = text_field(&curation, "sourceManifest", "curation")?.to_owned();
    let source_manifest_path =
        relative_input(root, &source_manifest_rel, "curation.sourceManifest")?;
    let source_manifest = read_hashed(&source_manifest_path, root, &mut inputs)?;
    expect_text(
        &source_manifest,
        "schema",
        "source-manifest",
        SOURCE_MANIFEST_SCHEMA,
    )?;
    let declared_upstream = object_field(&source_manifest, "upstream", "source-manifest")?;
    if optional_text(declared_upstream, "repo") != repo
        || optional_text(declared_upstream, "commit") != commit
    {
        return Err(shape(format!(
            "{} records upstream {}@{}, but curation records {repo}@{commit} — the \
             provenance ledger and the rulings must describe the same snapshot",
            display_path(root, &source_manifest_path),
            optional_text(declared_upstream, "repo"),
            optional_text(declared_upstream, "commit"),
        )));
    }
    let manifest_dir = source_manifest_path.parent().unwrap_or(root);
    let mut declared_files: BTreeMap<String, DeclaredSource> = BTreeMap::new();
    for (index, entry) in list_field(&source_manifest, "files", "source-manifest")?
        .iter()
        .enumerate()
    {
        let spot = format!("source-manifest.files[{index}]");
        let entry = as_object(entry, &spot)?;
        declared_files.insert(
            text_field(entry, "upstreamPath", &spot)?.to_owned(),
            DeclaredSource {
                original_sha256: text_field(entry, "originalSha256", &spot)?.to_owned(),
                redacted_path: text_field(entry, "redactedPath", &spot)?.to_owned(),
                redacted_sha256: text_field(entry, "redactedSha256", &spot)?.to_owned(),
            },
        );
    }

    // The published licence is a byte-for-byte copy of the upstream one, and the
    // ledger says so — both digests must be the copy we are about to publish.
    let license_rel = text_field(&curation, "license", "curation")?.to_owned();
    let license_path = relative_input(root, &license_rel, "curation.license")?;
    let license_bytes = fs::read(&license_path)?;
    let license_digest = sha256_hex(&license_bytes);
    inputs.insert(display_path(root, &license_path), license_digest.clone());
    let declared_license = declared_files.get(LICENSE_UPSTREAM_PATH).ok_or_else(|| {
        shape(format!(
            "{} records no {} entry — the licence cannot be published without its \
             pinned digests",
            display_path(root, &source_manifest_path),
            LICENSE_UPSTREAM_PATH
        ))
    })?;
    if manifest_dir.join(&declared_license.redacted_path) != license_path
        || declared_license.redacted_sha256 != license_digest
        || declared_license.original_sha256 != license_digest
    {
        return Err(shape(format!(
            "{} is not the upstream {} recorded by {} — the copy must be byte for \
             byte (original and redacted digest both {license_digest})",
            display_path(root, &license_path),
            LICENSE_UPSTREAM_PATH,
            display_path(root, &source_manifest_path),
        )));
    }
    let license_text = String::from_utf8(license_bytes).map_err(|_| {
        shape(format!(
            "{} is not UTF-8 text",
            display_path(root, &license_path)
        ))
    })?;

    // 038Q10: the book is an input of every run that declares it, and nothing
    // about it is republished — the output directory never holds a copy.
    let symbol_book = read_symbol_book(root, &curation, &mut inputs)?;

    let assets = list_field(&curation, "assets", "curation")?;
    if assets.is_empty() {
        return Err(shape(
            "curation.assets is empty — there is nothing to import",
        ));
    }

    let mut seen_ids: BTreeSet<String> = BTreeSet::new();
    let mut seen_outputs: BTreeSet<String> = BTreeSet::new();
    let mut modules: Vec<ImportedModule> = Vec::new();
    let mut catalog_modules: Vec<Value> = Vec::new();

    for (index, asset) in assets.iter().enumerate() {
        let spot = format!("assets[{index}]");
        let asset = as_object(asset, &spot)?;
        let id = text_field(asset, "id", &spot)?.to_owned();
        if !seen_ids.insert(id.clone()) {
            return Err(shape(format!("{spot}.id is {id:?}, already curated")));
        }
        let kind = text_field(asset, "kind", &spot)?.to_owned();
        let output = text_field(asset, "output", &spot)?.to_owned();
        let output_name = output_name(&output, &format!("{spot}.output"))?;
        if RESERVED_OUTPUT_PATHS.contains(&output_name.as_str()) {
            return Err(shape(format!(
                "{spot}.output is {output:?}, which this importer writes itself — an \
                 asset may not claim {}; a second file at the same path would overwrite \
                 the first",
                RESERVED_OUTPUT_PATHS.join(", ")
            )));
        }
        let output = output_name;
        if !seen_outputs.insert(output.clone()) {
            return Err(shape(format!("{spot}.output is {output:?}, already used")));
        }
        let source_rel = text_field(asset, "source", &spot)?.to_owned();
        let source_path = relative_input(root, &source_rel, &format!("{spot}.source"))?;
        let source_bytes = fs::read(&source_path)?;
        let source_digest = sha256_hex(&source_bytes);
        let source: Value = serde_json::from_slice(&source_bytes)?;
        inputs.insert(display_path(root, &source_path), source_digest.clone());
        let source_path_upstream = text_field(asset, "sourcePath", &spot)?.to_owned();
        let source_sha = text_field(asset, "sourceSha256", &spot)?.to_owned();
        let declared = declared_files.get(&source_path_upstream).ok_or_else(|| {
            shape(format!(
                "{spot}.sourcePath is {source_path_upstream:?}, which {} does not record",
                display_path(root, &source_manifest_path)
            ))
        })?;
        if declared.original_sha256 != source_sha {
            return Err(shape(format!(
                "{spot}.sourceSha256 is {source_sha}, but the provenance ledger pins \
                 {source_path_upstream} at {}",
                declared.original_sha256
            )));
        }
        if declared.redacted_sha256 != source_digest {
            return Err(shape(format!(
                "{} hashes to {source_digest}, but the provenance ledger records {} \
                 for the redacted copy",
                display_path(root, &source_path),
                declared.redacted_sha256
            )));
        }
        if manifest_dir.join(&declared.redacted_path) != source_path {
            return Err(shape(format!(
                "{spot}.source is {source_rel:?}, but the provenance ledger points at \
                 {:?}",
                declared.redacted_path
            )));
        }
        let upstream_maturity = text_field(asset, "upstreamMaturity", &spot)?.to_owned();
        let rulings = object_field(asset, "ports", &spot)?;

        // 038Q10's opt-in. Absent = the GENERIC path this batch has always
        // written; every other value is refused rather than read as "book".
        let bound_book = match optional_text(asset, "identityBinding") {
            binding if binding.is_empty() => None,
            binding if binding == IDENTITY_BINDING_BOOK => {
                if kind != "block_template" {
                    return Err(shape(format!(
                        "{spot}.identityBinding is {IDENTITY_BINDING_BOOK:?} on a {kind:?} \
                         asset; this batch binds block_template assets only — a role \
                         topology's pins are not library pins, and half-matching them would \
                         be worse than refusing"
                    )));
                }
                let book = symbol_book.as_ref().ok_or_else(|| {
                    shape(format!(
                        "{spot}.identityBinding is {IDENTITY_BINDING_BOOK:?}, but curation \
                         declares no {SYMBOL_BOOK_KEY} — a module may not bind to a book this \
                         run does not read"
                    ))
                })?;
                Some(book)
            }
            other => {
                return Err(shape(format!(
                    "{spot}.identityBinding is {other:?}; expected absent or \
                     {IDENTITY_BINDING_BOOK:?}"
                )));
            }
        };

        // 038Q12: an explicit pin contract is meaningful only on a bound block —
        // stated anywhere else it would be a decision nothing checks against a
        // profile, so it is refused rather than read and dropped.
        let stated: Vec<&str> = CONTRACT_FIELDS
            .into_iter()
            .filter(|field| asset.contains_key(*field))
            .collect();
        if !stated.is_empty() && bound_book.is_none() {
            return Err(shape(format!(
                "{spot} states {} but is not bound to the symbol book — every explicit pin \
                 is resolved against a profile, and an asset that reads no profile would \
                 carry a decision this run never applies",
                stated.join(", ")
            )));
        }
        let contract = read_pin_contract(asset, &spot)?;

        let normalised = match kind.as_str() {
            "block_template" => {
                block_module(&id, &source, library, rulings, bound_book, &contract, &spot)?
            }
            "role_topology" => topology_module(&id, &source, rulings, &spot)?,
            other => {
                return Err(shape(format!(
                    "{spot}.kind is {other:?}; expected block_template or role_topology"
                )));
            }
        };

        let mut catalog_module = json!({
            "circuit": output.clone(),
            "id": id.clone(),
            "identityStatus": if bound_book.is_some() {
                IDENTITY_BOUND
            } else {
                IDENTITY_UNVERIFIED
            },
            "kind": kind,
            "limitations": normalised.limitations.clone(),
            "maturity": MATURITY_CANDIDATE,
            "notForDrawCompile": true,
            "parts": normalised.parts.clone(),
            "ports": normalised.ports.iter().map(CatalogPort::to_json).collect::<Vec<_>>(),
            "source": {
                "commit": commit.clone(),
                "path": source_path_upstream,
                "sha256": source_sha,
            },
            "title": normalised.title.clone(),
            "unresolvedWildcards": normalised.wildcards.clone(),
            "unstatedPins": normalised.unstated.clone(),
            "upstreamMaturity": upstream_maturity,
        });
        // Structured attribution only where upstream states it; a shape that
        // has no author field does not get an invented one.
        if let Some(attribution) = &normalised.attribution {
            catalog_module["attribution"] = attribution.clone();
        }
        catalog_modules.push(catalog_module);

        modules.push(ImportedModule {
            id,
            path: output,
            circuit: normalised.circuit,
        });
    }

    catalog_modules.sort_by(|left, right| {
        left["id"]
            .as_str()
            .unwrap_or("")
            .cmp(right["id"].as_str().unwrap_or(""))
    });
    let catalog = json!({
        "modules": catalog_modules,
        "schema": CATALOG_SCHEMA,
        "standardPartsLibraryUuid": library_uuid,
        "upstream": {"commit": commit.clone(), "repo": repo.clone()},
    });

    let mut files: Vec<OutputFile> = Vec::new();
    for module in &modules {
        files.push(OutputFile {
            path: module.path.clone(),
            bytes: render(&module.circuit)?,
        });
    }
    files.push(OutputFile {
        path: "catalog.json".to_owned(),
        bytes: render(&catalog)?,
    });
    files.push(OutputFile {
        path: LICENSE_OUTPUT_PATH.to_owned(),
        bytes: license_text,
    });
    let mut outputs: Vec<Value> = files
        .iter()
        .map(|file| json!({"path": file.path, "sha256": sha256_hex(file.bytes.as_bytes())}))
        .collect();
    outputs.sort_by(|left, right| {
        left["path"]
            .as_str()
            .unwrap_or("")
            .cmp(right["path"].as_str().unwrap_or(""))
    });
    let manifest = json!({
        "inputs": inputs
            .iter()
            .map(|(path, sha)| json!({"path": path, "sha256": sha}))
            .collect::<Vec<_>>(),
        "outputs": outputs,
        "schema": MANIFEST_SCHEMA,
        "upstream": {"commit": commit, "repo": repo},
    });
    files.push(OutputFile {
        path: "manifest.json".to_owned(),
        bytes: render(&manifest)?,
    });
    files.sort_by(|left, right| left.path.cmp(&right.path));
    modules.sort_by(|left, right| left.id.cmp(&right.id));

    Ok(ImportPlan { modules, files })
}

/// Write every planned file, after refusing as a *set* when one already exists
/// with different bytes. Identical files are allowed (the command is idempotent),
/// nothing is overwritten, and there is no force flag to ask for one.
///
/// Each relative path is re-checked here rather than trusting the caller: an
/// absolute path or a `..` component would write outside `directory`, and this
/// is the last layer that can refuse it.
pub fn write_outputs(directory: &Path, files: &[OutputFile]) -> Result<Vec<String>> {
    let mut seen: BTreeSet<String> = BTreeSet::new();
    for file in files {
        let name = output_name(&file.path, "output path")?;
        // Two planned files at one path is a contradiction in the caller's plan:
        // the second would replace the first, which is exactly the overwrite this
        // command refuses. Identical bytes do not make it acceptable.
        if !seen.insert(name.clone()) {
            return Err(shape(format!(
                "{name} is planned twice — one run writes one file per path, and the \
                 second would overwrite the first"
            )));
        }
    }
    for file in files {
        let path = directory.join(&file.path);
        if path.exists() && fs::read_to_string(&path)? != file.bytes {
            return Err(shape(format!(
                "{} already exists with different content — this batch never overwrites; \
                 move it aside or import into another --output",
                display_path(directory, &path)
            )));
        }
    }
    for file in files {
        let path = directory.join(&file.path);
        if path.exists() && fs::read_to_string(&path)? == file.bytes {
            continue;
        }
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }
        fs::write(&path, file.bytes.as_bytes())?;
    }
    Ok(files.iter().map(|file| file.path.clone()).collect())
}

/// What the CLI prints on success: how many modules, which files, and the fact
/// that these are candidates and nothing more.
pub fn report(plan: &ImportPlan) -> Value {
    json!({
        "candidate": true,
        "maturity": MATURITY_CANDIDATE,
        "moduleIds": plan.module_ids(),
        "modules": plan.modules.len(),
        "outputs": plan.files.iter().map(|file| file.path.clone()).collect::<Vec<_>>(),
        "schema": REPORT_SCHEMA,
    })
}

// --------------------------------------------------------------- symbol book

/// One profile pin, as the book states it: a number **and** a name.
struct BookPin {
    number: String,
    name: String,
}

impl BookPin {
    /// Exact equality only: a prefix (`IN` for `VIN`) or a fuzzy match would
    /// turn an identification into a guess.
    fn matches(&self, pin: &str) -> bool {
        pin == self.number || pin == self.name
    }
}

/// One `device -> symbol` binding an index entry states.
struct BookBinding {
    device_uuid: String,
    lcsc: String,
    mpn: String,
}

/// One admitted profile: the symbol it resolves to, the devices it binds, and
/// the pins a `role.pin` member may name.
struct BookEntry {
    symbol_ref: String,
    bindings: Vec<BookBinding>,
    pins: Vec<BookPin>,
}

/// The managed symbol book (`blocklib/symbols/`), reduced to what a bound
/// module is checked against. It is an *input*: nothing here is republished.
struct SymbolBook {
    profile_book_sha256: String,
    entries: Vec<BookEntry>,
}

impl SymbolBook {
    /// The one entry that binds `device_uuid`, with the binding that does it.
    ///
    /// Zero entries is an unbound part (refused, never a GENERIC fallback); two
    /// is a duplicate binding (refused) — either way this run may not pick one
    /// and carry on.
    fn entry_for(&self, device_uuid: &str, where_: &str) -> Result<(&BookEntry, &BookBinding)> {
        let hits: Vec<(&BookEntry, &BookBinding)> = self
            .entries
            .iter()
            .flat_map(|entry| entry.bindings.iter().map(move |binding| (entry, binding)))
            .filter(|(_, binding)| binding.device_uuid == device_uuid)
            .collect();
        match hits.len() {
            1 => Ok(hits[0]),
            0 => Err(shape(format!(
                "{where_}: device {device_uuid} is bound by no profile in the symbol book — a \
                 module that asks for the book may not leave a part on the GENERIC placeholder"
            ))),
            count => Err(shape(format!(
                "{where_}: device {device_uuid} is bound by {count} profiles in the symbol book \
                 — a duplicate binding cannot say which symbol the part is"
            ))),
        }
    }
}

/// One physical pin of a profile: the role it belongs to and the profile's own
/// pin number, which is an opaque atom (`A1B12` is one pin, not two).
#[derive(Clone, Debug, Eq, Ord, PartialEq, PartialOrd)]
struct PhysicalPin {
    role: String,
    number: String,
}

impl PhysicalPin {
    /// `role.number`, the spelling the catalog and the circuit spec use.
    fn label(&self) -> String {
        format!("{}.{}", self.role, self.number)
    }
}

/// Resolve a `role.pin` member to exactly one profile pin.
///
/// `pin` may be the profile's number or its name, by exact equality only — and
/// when a name is carried by two pins the token identifies neither, so the
/// caller has to name the number. Guessing here would put a pad on a net
/// nobody decided.
fn resolve_pin(
    roles: &BTreeMap<String, &BookEntry>,
    token: &str,
    where_: &str,
) -> Result<PhysicalPin> {
    let (role, pin) = split_pin(token, where_)?;
    let Some(entry) = roles.get(role) else {
        return Err(shape(format!(
            "{where_}: {token} names role {role:?}, which this module's parts do not declare"
        )));
    };
    let hits: Vec<&str> = entry
        .pins
        .iter()
        .filter(|candidate| candidate.matches(pin))
        .map(|candidate| candidate.number.as_str())
        .collect();
    match hits.len() {
        1 => Ok(PhysicalPin {
            role: role.to_owned(),
            number: hits[0].to_owned(),
        }),
        0 => Err(shape(format!(
            "{where_}: {token} is not a pin number or pin name of profile {} — an exact match \
             is required, and a prefix or fuzzy match is not an identification",
            entry.symbol_ref
        ))),
        count => Err(shape(format!(
            "{where_}: {token} is a pin name carried by {count} pins of profile {} ({}) — a \
             pin named twice identifies neither, so name the pin number",
            entry.symbol_ref,
            hits.iter()
                .map(|number| format!("{role}.{number}"))
                .collect::<Vec<_>>()
                .join(", ")
        ))),
    }
}

/// 038Q12: what a bound block states about its own pins — the explicit members
/// of each upstream wildcard group, the physical pins of a port, and the
/// explicit no-connects. Absent unless the asset both binds to the book and
/// states it.
#[derive(Default)]
struct PinContract {
    pin_groups: BTreeMap<String, Vec<String>>,
    port_pins: BTreeMap<String, Vec<String>>,
    nc: Vec<String>,
}

/// The fields a pin contract may be stated with, in the order they are refused.
const CONTRACT_FIELDS: [&str; 3] = ["pinGroups", "portPins", "nc"];

/// Read `pinGroups`/`portPins`/`nc` off one curation asset. Shape only here:
/// whether a member exists, is unique or lands on a net is decided against the
/// profiles inside [`block_module`].
fn read_pin_contract(asset: &Map<String, Value>, spot: &str) -> Result<PinContract> {
    let mut contract = PinContract::default();
    if let Some(declared) = asset.get("pinGroups") {
        let where_ = format!("{spot}.pinGroups");
        for (member, listed) in as_object(declared, &where_)? {
            if !member.contains('*') {
                return Err(shape(format!(
                    "{where_}: {member:?} is not a wildcard member — this field names the \
                     explicit pins an upstream `<role>.<pin>*` group stands for, and a plain \
                     pin is already explicit"
                )));
            }
            contract.pin_groups.insert(
                member.clone(),
                tokens(listed, &format!("{where_}.{member}"))?,
            );
        }
    }
    if let Some(declared) = asset.get("portPins") {
        let where_ = format!("{spot}.portPins");
        for (port, listed) in as_object(declared, &where_)? {
            contract
                .port_pins
                .insert(port.clone(), tokens(listed, &format!("{where_}.{port}"))?);
        }
    }
    if let Some(declared) = asset.get("nc") {
        contract.nc = tokens(declared, &format!("{spot}.nc"))?;
    }
    Ok(contract)
}

/// A list of distinct non-empty strings, as one field of the contract states it.
fn tokens(value: &Value, where_: &str) -> Result<Vec<String>> {
    let mut listed: Vec<String> = Vec::new();
    for (index, item) in as_array(value, where_)?.iter().enumerate() {
        let text = item
            .as_str()
            .ok_or_else(|| shape(format!("{where_}[{index}] is not a string")))?;
        if text.is_empty() {
            return Err(shape(format!("{where_}[{index}] is empty")));
        }
        if listed.iter().any(|existing| existing == text) {
            return Err(shape(format!(
                "{where_}[{index}] is {text:?}, already listed — one pin is named once"
            )));
        }
        listed.push(text.to_owned());
    }
    Ok(listed)
}

/// Read the two files `curation.symbolBook` names, hash them into `inputs`, and
/// check every digest the index records. `None` when curation declares no book.
fn read_symbol_book(
    root: &Path,
    curation: &Map<String, Value>,
    inputs: &mut BTreeMap<String, String>,
) -> Result<Option<SymbolBook>> {
    let Some(declared) = curation.get(SYMBOL_BOOK_KEY) else {
        return Ok(None);
    };
    let declared = as_object(declared, "curation.symbolBook")?;
    let index_rel = text_field(declared, "index", "curation.symbolBook")?.to_owned();
    let profiles_rel = text_field(declared, "profiles", "curation.symbolBook")?.to_owned();
    let default_identity = text_field(declared, "defaultIdentity", "curation.symbolBook")?;
    if default_identity != DEFAULT_IDENTITY_GENERIC {
        return Err(shape(format!(
            "curation.symbolBook.defaultIdentity is {default_identity:?}; this batch has one \
             global default ({DEFAULT_IDENTITY_GENERIC:?}) and an asset opts in with \
             identityBinding: {IDENTITY_BINDING_BOOK:?}"
        )));
    }

    let index_path = relative_input(root, &index_rel, "curation.symbolBook.index")?;
    let profiles_path = relative_input(root, &profiles_rel, "curation.symbolBook.profiles")?;
    let index = read_hashed(&index_path, root, inputs)?;
    let profiles_bytes = fs::read(&profiles_path)?;
    let profile_book_sha256 = sha256_hex(&profiles_bytes);
    inputs.insert(
        display_path(root, &profiles_path),
        profile_book_sha256.clone(),
    );
    let profiles_text = String::from_utf8(profiles_bytes).map_err(|_| {
        shape(format!(
            "{} is not UTF-8 text",
            display_path(root, &profiles_path)
        ))
    })?;

    let index = as_object(&index, "symbol index")?;
    expect_text(index, "schema", "symbol-index", SYMBOL_BOOK_SCHEMA)?;
    if index.get("notForDrawCompile") != Some(&Value::Bool(true)) {
        return Err(shape(
            "symbol-index.notForDrawCompile must be true — the book holds candidates, and a \
             run may not bind a module to a book that says it is drawable",
        ));
    }
    let declared_sha = text_field(index, "profileBookSha256", "symbol-index")?;
    if declared_sha != profile_book_sha256 {
        return Err(shape(format!(
            "symbol-index.profileBookSha256 is {declared_sha}, but {} hashes to \
             {profile_book_sha256} — the index describes a different book",
            display_path(root, &profiles_path)
        )));
    }

    let book: Value = serde_json::from_str(&profiles_text)?;
    let profile_objects = list_field(&book, "profiles", "symbol book")?;
    let digests = profile_digests(&profiles_text)?;
    let entries_declared = list_field(index, "profiles", "symbol-index")?;
    if entries_declared.len() != profile_objects.len() || digests.len() != profile_objects.len() {
        return Err(shape(format!(
            "symbol-index names {} profile(s), {} holds {} and re-reading it yields {} — the \
             index and the book describe different books",
            entries_declared.len(),
            display_path(root, &profiles_path),
            profile_objects.len(),
            digests.len()
        )));
    }

    let mut entries: Vec<BookEntry> = Vec::new();
    for (position, declared_entry) in entries_declared.iter().enumerate() {
        let spot = format!("symbol-index.profiles[{position}]");
        let declared_entry = as_object(declared_entry, &spot)?;
        let symbol_ref = text_field(declared_entry, "symbolRef", &spot)?.to_owned();
        if symbol_ref.is_empty() {
            return Err(shape(format!("{spot}.symbolRef is empty")));
        }
        let maturity = text_field(declared_entry, "maturity", &spot)?;
        if maturity != MATURITY_CANDIDATE {
            return Err(shape(format!(
                "{spot}.maturity is {maturity:?}; the book this run reads holds \
                 {MATURITY_CANDIDATE} profiles only"
            )));
        }
        let declared_profile_sha = text_field(declared_entry, "profileSha256", &spot)?;
        if declared_profile_sha != digests[position] {
            return Err(shape(format!(
                "{spot}.profileSha256 is {declared_profile_sha}, but the profile object at that \
                 position hashes to {} — the profile moved or was edited after it was admitted",
                digests[position]
            )));
        }
        let profile = as_object(&profile_objects[position], "symbol book profile")?;
        let profile_ref = text_field(profile, "symbolRef", "symbol book profile")?;
        if profile_ref != symbol_ref {
            return Err(shape(format!(
                "{spot}.symbolRef is {symbol_ref:?}, but the profile at that position declares \
                 {profile_ref:?} — the index and the book disagree about which symbol is here"
            )));
        }

        let mut bindings: Vec<BookBinding> = Vec::new();
        let mut bound: BTreeSet<String> = BTreeSet::new();
        for (bind_index, binding) in list_field(declared_entry, "bindings", &spot)?
            .iter()
            .enumerate()
        {
            let binding_spot = format!("{spot}.bindings[{bind_index}]");
            let binding = as_object(binding, &binding_spot)?;
            let read = BookBinding {
                device_uuid: text_field(binding, "deviceUuid", &binding_spot)?.to_owned(),
                lcsc: text_field(binding, "lcsc", &binding_spot)?.to_owned(),
                mpn: text_field(binding, "mpn", &binding_spot)?.to_owned(),
            };
            if read.device_uuid.is_empty() {
                return Err(shape(format!("{binding_spot}.deviceUuid is empty")));
            }
            if !bound.insert(read.device_uuid.clone()) {
                return Err(shape(format!(
                    "{binding_spot}.deviceUuid is {:?}, already bound by this entry — one \
                     device, one symbol",
                    read.device_uuid
                )));
            }
            bindings.push(read);
        }
        if bindings.is_empty() {
            return Err(shape(format!(
                "{spot}.bindings is empty — a profile nothing binds is not an identity"
            )));
        }

        let mut pins: Vec<BookPin> = Vec::new();
        for (pin_index, pin) in list_field(profile, "pins", "symbol book profile")?
            .iter()
            .enumerate()
        {
            let pin_spot = format!("symbol book profile {symbol_ref}.pins[{pin_index}]");
            let pin = as_object(pin, &pin_spot)?;
            let read = BookPin {
                number: text_field(pin, "number", &pin_spot)?.to_owned(),
                name: text_field(pin, "name", &pin_spot)?.to_owned(),
            };
            // 038Q12: a pin *number* is the atom a member is resolved to, so two
            // pins may not share one. Two pins sharing a *name* is the profile's
            // own business; naming such a pin by that name is refused where it
            // happens (`resolve_pin`). Composite numbers (`A1B12`) compare whole.
            if pins.iter().any(|existing| existing.number == read.number) {
                return Err(shape(format!(
                    "{pin_spot}.number is {:?}, which the profile already uses — a pin \
                     number identifies one pad, and a duplicate would resolve a member to \
                     whichever came first",
                    read.number
                )));
            }
            pins.push(read);
        }
        if pins.is_empty() {
            return Err(shape(format!(
                "profile {symbol_ref} declares no pins, so no member could ever match it"
            )));
        }
        entries.push(BookEntry {
            symbol_ref,
            bindings,
            pins,
        });
    }
    Ok(Some(SymbolBook {
        profile_book_sha256,
        entries,
    }))
}

/// The per-profile digests a book index must record, in book order.
///
/// Public for the same reason [`file_sha256`] is: a caller verifying a book
/// should not re-implement the definition. The definition is 038Q8's — the
/// profile object *as stored* (`indent=2`, insertion key order, final newline) —
/// and serde_json's default map sorts keys, so the object is not re-rendered
/// here: its bytes are taken from the book text and only the extra indentation
/// of being an array element is removed.
pub fn profile_digests(profiles_text: &str) -> Result<Vec<String>> {
    Ok(profile_texts(profiles_text)?
        .iter()
        .map(|text| sha256_hex(text.as_bytes()))
        .collect())
}

fn profile_texts(profiles_text: &str) -> Result<Vec<String>> {
    let bytes = profiles_text.as_bytes();
    let key = profiles_text.find("\"profiles\"").ok_or_else(|| {
        shape("the symbol book has no \"profiles\" key, so it holds no profile to hash")
    })?;
    let start = key
        + profiles_text[key..]
            .find('[')
            .ok_or_else(|| shape("the symbol book's \"profiles\" is not an array"))?;
    let mut spans: Vec<(usize, usize)> = Vec::new();
    let mut depth = 0usize;
    let mut begin = 0usize;
    let mut in_string = false;
    let mut escaped = false;
    for (offset, byte) in bytes[start..].iter().enumerate() {
        let position = start + offset;
        if in_string {
            if escaped {
                escaped = false;
            } else if *byte == b'\\' {
                escaped = true;
            } else if *byte == b'"' {
                in_string = false;
            }
            continue;
        }
        match *byte {
            b'"' => in_string = true,
            b'{' => {
                if depth == 0 {
                    begin = position;
                }
                depth += 1;
            }
            b'}' => {
                if depth == 0 {
                    return Err(shape("the symbol book's \"profiles\" array is malformed"));
                }
                depth -= 1;
                if depth == 0 {
                    spans.push((begin, position + 1));
                }
            }
            b']' if depth == 0 => break,
            _ => {}
        }
    }
    if depth != 0 || in_string {
        return Err(shape(
            "the symbol book's \"profiles\" array is not terminated",
        ));
    }
    if spans.is_empty() {
        return Err(shape("the symbol book holds no profile"));
    }
    Ok(spans
        .iter()
        .map(|(begin, end)| dedent_object(&profiles_text[*begin..*end]))
        .collect())
}

/// The stored object text with the indentation of being an array element
/// removed, so it reads exactly as `json.dumps(obj, indent=2) + "\n"` would.
fn dedent_object(text: &str) -> String {
    let mut lines = text.split('\n');
    let first = lines.next().unwrap_or("");
    let rest: Vec<&str> = lines.collect();
    let indent = rest
        .first()
        .map(|line| line.len() - line.trim_start_matches(' ').len())
        .unwrap_or(0);
    let strip = indent.saturating_sub(2);
    let mut out = String::from(first);
    for line in rest {
        out.push('\n');
        let lead = line.len() - line.trim_start_matches(' ').len();
        out.push_str(&line[lead.min(strip)..]);
    }
    out.push('\n');
    out
}

// ------------------------------------------------------------------ outcomes

struct CatalogPort {
    name: String,
    net: String,
    direction: String,
    class: String,
    default_net: String,
    part: String,
}

impl CatalogPort {
    fn to_json(&self) -> Value {
        let mut body = Map::new();
        body.insert("class".to_owned(), Value::String(self.class.clone()));
        body.insert(
            "direction".to_owned(),
            Value::String(self.direction.clone()),
        );
        body.insert("name".to_owned(), Value::String(self.name.clone()));
        body.insert("net".to_owned(), Value::String(self.net.clone()));
        if !self.default_net.is_empty() {
            body.insert(
                "defaultNet".to_owned(),
                Value::String(self.default_net.clone()),
            );
        }
        if !self.part.is_empty() {
            body.insert("part".to_owned(), Value::String(self.part.clone()));
        }
        Value::Object(body)
    }
}

/// One normalised module, before it is dressed as catalog rows.
struct Normalised {
    title: String,
    circuit: Value,
    parts: Vec<Value>,
    ports: Vec<CatalogPort>,
    wildcards: Vec<String>,
    unstated: Vec<String>,
    limitations: Vec<String>,
    /// Structured author/contributors, only when the source shape states them.
    attribution: Option<Value>,
}

/// One `source-manifest.files` entry, as the ledger states it.
struct DeclaredSource {
    original_sha256: String,
    redacted_path: String,
    redacted_sha256: String,
}

struct Ruling {
    direction: String,
    class: String,
    part: String,
    /// `true` when curation says the port has no upstream net and its net is
    /// the port pin alone. Default `false` = the port must sit on a net.
    port_pin_only: bool,
}

fn curated_ruling(rulings: &Map<String, Value>, name: &str, spot: &str) -> Result<Ruling> {
    let Some(entry) = rulings.get(name) else {
        return Err(shape(format!(
            "{spot}.ports.{name}: no curated direction/class — an unruled port is \
             refused rather than guessed from `dir`/`at`"
        )));
    };
    let where_ = format!("{spot}.ports.{name}");
    let entry = as_object(entry, &where_)?;
    let direction = text_field(entry, "direction", &where_)?.to_owned();
    if !direction.is_empty() && !PORT_DIRECTIONS.contains(&direction.as_str()) {
        return Err(shape(format!(
            "{where_}.direction is {direction:?}; expected one of {} or \"\" when the \
             upstream text cannot state it",
            PORT_DIRECTIONS.join(", ")
        )));
    }
    let class = text_field(entry, "class", &where_)?.to_owned();
    if !NET_CLASSES.contains(&class.as_str()) {
        return Err(shape(format!(
            "{where_}.class is {class:?}; expected one of {} — a port with no ruled net \
             class would be written as the neutral default and claim a class nobody decided",
            NET_CLASSES.join(", ")
        )));
    }
    let part = match entry.get("part") {
        None | Some(Value::Null) => String::new(),
        Some(Value::String(value)) => value.clone(),
        Some(other) => {
            return Err(shape(format!(
                "{where_}.part is {other}; expected a role id string"
            )));
        }
    };
    let port_pin_only = match entry.get("netSource") {
        None => false,
        Some(Value::String(value)) if value == "internal_net" => false,
        Some(Value::String(value)) if value == "port_pin_only" => true,
        Some(other) => {
            return Err(shape(format!(
                "{where_}.netSource is {other}; expected \"internal_net\" or \
                 \"port_pin_only\""
            )));
        }
    };
    Ok(Ruling {
        direction,
        class,
        part,
        port_pin_only,
    })
}

// --------------------------------------------------------------------- block

fn block_module(
    id: &str,
    source: &Value,
    library: &Map<String, Value>,
    rulings: &Map<String, Value>,
    book: Option<&SymbolBook>,
    contract: &PinContract,
    spot: &str,
) -> Result<Normalised> {
    let source_id = text_field(source, "id", spot)?;
    if source_id != id {
        return Err(shape(format!(
            "{spot}.id is {id:?} but the source declares {source_id:?} — the catalog id \
             and the source id must be the same module"
        )));
    }

    // Attribution is structured data upstream states; the free-text `source`
    // and `validated` fields are not carried at all.
    let author = optional_text(source, "author");
    let contributors: Vec<String> = match source.get("contributors") {
        None | Some(Value::Null) => Vec::new(),
        Some(Value::Array(items)) => items
            .iter()
            .map(|item| {
                item.as_str()
                    .map(str::to_owned)
                    .ok_or_else(|| shape(format!("{spot}.contributors holds a non-string entry")))
            })
            .collect::<Result<Vec<String>>>()?,
        Some(other) => {
            return Err(shape(format!(
                "{spot}.contributors is {other}; expected a list of names"
            )));
        }
    };
    let attribution = if author.is_empty() && contributors.is_empty() {
        None
    } else {
        Some(json!({"author": author, "contributors": contributors}))
    };

    let roles = object_field(source, "parts", spot)?;
    if roles.is_empty() {
        return Err(shape(format!(
            "{spot}: parts is empty, and a module with no parts is not a module"
        )));
    }
    let mut circuit_parts: Vec<Value> = Vec::new();
    let mut catalog_parts: Vec<Value> = Vec::new();
    let mut role_entries: BTreeMap<String, &BookEntry> = BTreeMap::new();
    for (role, entry) in roles {
        let where_ = format!("{spot}.parts.{role}");
        if role.contains('.') {
            return Err(shape(format!(
                "{where_}: a role may not contain '.', a member is '<role>.<pin>'"
            )));
        }
        let entry = as_object(entry, &where_)?;
        let quantity = entry
            .get("qty")
            .and_then(Value::as_u64)
            .ok_or_else(|| shape(format!("{where_}.qty must be a positive integer")))?;
        if quantity != 1 {
            return Err(shape(format!(
                "{where_}.qty is {quantity}; this batch imports one part per role — \
                 copying a part to meet a quantity would invent a second instance with \
                 its own connectivity"
            )));
        }
        let reference = text_field(entry, "part", &where_)?.to_owned();
        let standard = library.get(&reference).ok_or_else(|| {
            shape(format!(
                "{where_}.part is {reference:?}, which the imported standard-parts table \
                 does not carry"
            ))
        })?;
        let standard = as_object(standard, &format!("{where_}.part"))?;
        let override_value = match entry.get("value_override") {
            None | Some(Value::Null) => String::new(),
            Some(Value::String(value)) => value.clone(),
            Some(other) => {
                return Err(shape(format!(
                    "{where_}.value_override is {other}; expected a string"
                )));
            }
        };
        let value = if override_value.is_empty() {
            optional_text(standard, "value")
        } else {
            override_value
        };
        let mpn = optional_text(standard, "mpn");
        let lcsc = optional_text(standard, "lcsc");
        let footprint = optional_text(standard, "footprint");
        let device_uuid = optional_text(standard, "deviceUuid");

        // 038Q10: a bound module resolves every part through the book, and no
        // part may fall back to the placeholder.
        let symbol_ref = match book {
            None => format!("{GENERIC_SYMBOL_PREFIX}{role}"),
            Some(book) => {
                if device_uuid.is_empty() {
                    return Err(shape(format!(
                        "{where_}: a module bound to the symbol book must declare every part's \
                         deviceUuid, and this part states none"
                    )));
                }
                let (book_entry, binding) = book.entry_for(&device_uuid, &where_)?;
                if binding.lcsc != lcsc || binding.mpn != mpn {
                    return Err(shape(format!(
                        "{where_}: the book binds device {device_uuid} to {:?} / {:?}, but this \
                         module declares {lcsc:?} / {mpn:?} — a binding and a part that \
                         disagree are not the same component",
                        binding.lcsc, binding.mpn
                    )));
                }
                role_entries.insert(role.clone(), book_entry);
                book_entry.symbol_ref.clone()
            }
        };

        circuit_parts.push(json!({
            "id": role,
            "symbolRef": symbol_ref.clone(),
            "value": value,
            "mpn": mpn,
            "lcsc": lcsc,
            "params": Map::<String, Value>::new(),
            "provenance": PROVENANCE_AI,
        }));
        let mut catalog_part = Map::new();
        catalog_part.insert("role".to_owned(), Value::String(role.clone()));
        catalog_part.insert(
            "symbolRef".to_owned(),
            Value::String(if book.is_some() {
                symbol_ref
            } else {
                String::new()
            }),
        );
        catalog_part.insert("value".to_owned(), Value::String(value));
        catalog_part.insert("mpn".to_owned(), Value::String(mpn));
        catalog_part.insert("lcsc".to_owned(), Value::String(lcsc));
        catalog_part.insert("standardPart".to_owned(), Value::String(reference));
        if !footprint.is_empty() {
            catalog_part.insert("footprint".to_owned(), Value::String(footprint));
        }
        if !device_uuid.is_empty() {
            catalog_part.insert("deviceUuid".to_owned(), Value::String(device_uuid));
        }
        catalog_parts.push(Value::Object(catalog_part));
    }

    // 038Q12: each explicit pin group is validated once, before any net is read:
    // the key has to be a wildcard of a declared role, the value non-empty, and
    // every listed pin has to resolve to exactly one pin *of that role*.
    let mut group_pins: BTreeMap<String, Vec<PhysicalPin>> = BTreeMap::new();
    if book.is_some() {
        for (member, listed) in &contract.pin_groups {
            let where_ = format!("{spot}.pinGroups.{member}");
            let (group_role, _pin) = split_pin(member, &where_)?;
            if !roles.contains_key(group_role) {
                return Err(shape(format!(
                    "{where_}: group {member:?} names role {group_role:?}, which this module's \
                     parts do not declare"
                )));
            }
            if listed.is_empty() {
                return Err(shape(format!(
                    "{where_} is empty — a wildcard group stands for at least one physical pin, \
                     and an empty list would silently drop the members the upstream net names"
                )));
            }
            let mut resolved: Vec<PhysicalPin> = Vec::new();
            for entry in listed {
                if entry.contains('*') {
                    return Err(shape(format!(
                        "{where_}: {entry:?} still carries a wildcard — a member of this field \
                         is one explicit physical pin"
                    )));
                }
                let pin = resolve_pin(&role_entries, entry, &where_)?;
                if pin.role != group_role {
                    return Err(shape(format!(
                        "{where_}: {entry:?} belongs to role {:?} but group {member:?} is role \
                         {group_role:?} — a group may not reach across roles",
                        pin.role
                    )));
                }
                if resolved.iter().any(|existing| existing == &pin) {
                    return Err(shape(format!(
                        "{where_}: {entry:?} resolves to {}, which the group already lists — \
                         one pin is one member",
                        pin.label()
                    )));
                }
                resolved.push(pin);
            }
            group_pins.insert(member.clone(), resolved);
        }
        // 038Q12: one physical pin belongs to one explicit group. Two groups
        // that share a pin are an unresolved ownership question, and a net that
        // carries both groups would answer it by silently writing the pin once.
        let mut group_owner: BTreeMap<PhysicalPin, &str> = BTreeMap::new();
        for (member, listed) in &group_pins {
            let where_ = format!("{spot}.pinGroups.{member}");
            for pin in listed {
                if let Some(previous) = group_owner.insert(pin.clone(), member.as_str())
                    && previous != member.as_str()
                {
                    return Err(shape(format!(
                        "{where_}: {} also belongs to {spot}.pinGroups.{previous} — one physical \
                         pin belongs to one explicit group, and two groups claiming it would make \
                         its membership a guess",
                        pin.label()
                    )));
                }
            }
        }
    }

    let declared_ports = object_field(source, "ports", spot)?;
    for name in declared_ports.keys() {
        curated_ruling(rulings, name, spot)?;
    }
    for name in rulings.keys() {
        if !declared_ports.contains_key(name) {
            return Err(shape(format!(
                "{spot}.ports.{name} is curated but the source does not declare it — a \
                 ruling for a port that does not exist is a stale decision"
            )));
        }
    }
    // 038Q12: `portPins` is read by port name, so a key that matches no declared
    // port would rule nothing at all and leave the typo to surface as a defect
    // of the port it was meant for.
    for key in contract.port_pins.keys() {
        if !declared_ports.contains_key(key) {
            return Err(shape(format!(
                "{spot}.portPins.{key} is not a port the source declares — a stale or unknown \
                 key names no port, so the decision it carries never takes effect"
            )));
        }
    }

    let raw_nets = list_field(source, "internal_nets", spot)?;
    if raw_nets.is_empty() {
        return Err(shape(format!("{spot}.internal_nets is empty")));
    }
    let mut nets: Vec<(Vec<String>, Option<String>)> = Vec::new();
    let mut pin_owner: BTreeMap<String, usize> = BTreeMap::new();
    let mut raw_wildcards: BTreeSet<String> = BTreeSet::new();
    for (index, raw_net) in raw_nets.iter().enumerate() {
        let where_ = format!("{spot}.internal_nets[{index}]");
        let tokens = as_array(raw_net, &where_)?;
        let mut members: Vec<String> = Vec::new();
        let mut port: Option<String> = None;
        let mut resolved_here: Vec<PhysicalPin> = Vec::new();
        for token in tokens {
            let token = token
                .as_str()
                .ok_or_else(|| shape(format!("{where_} holds a non-string token")))?;
            if let Some(name) = token.strip_prefix("PORT:") {
                if name.is_empty() {
                    return Err(shape(format!("{where_} has an empty PORT: token")));
                }
                if !declared_ports.contains_key(name) {
                    return Err(shape(format!(
                        "{where_} names PORT:{name}, which the source does not declare in \
                         ports"
                    )));
                }
                if port.is_some() {
                    return Err(shape(format!(
                        "{where_} carries more than one PORT: token — one net exposes one \
                         port"
                    )));
                }
                port = Some(name.to_owned());
                continue;
            }
            let (role, _pin) = split_pin(token, &where_)?;
            if !roles.contains_key(role) {
                return Err(shape(format!(
                    "{where_} names {token}, whose role {role:?} this module does not declare"
                )));
            }
            if book.is_some() {
                // A bound module writes physical pins only. A wildcard member is
                // replaced by the pins curation names for it — never by a prefix
                // expansion, which would guess which pads the group meant.
                if token.contains('*') {
                    raw_wildcards.insert(token.to_owned());
                    let Some(expanded) = group_pins.get(token) else {
                        return Err(shape(format!(
                            "{where_}: a module bound to the symbol book may not keep a wildcard \
                             member ({token}) — {spot}.pinGroups must name the physical pins this \
                             group stands for"
                        )));
                    };
                    for pin in expanded {
                        let label = pin.label();
                        if resolved_here.iter().any(|existing| existing == pin) {
                            continue;
                        }
                        resolved_here.push(pin.clone());
                        members.push(label);
                    }
                    continue;
                }
                let pin = resolve_pin(&role_entries, token, &where_)?;
                if !resolved_here.iter().any(|existing| existing == &pin) {
                    resolved_here.push(pin);
                    members.push(token.to_owned());
                }
                continue;
            }
            if !members.iter().any(|existing| existing == token) {
                members.push(token.to_owned());
            }
            if let Some(previous) = pin_owner.insert(token.to_owned(), index)
                && previous != index
            {
                return Err(shape(format!(
                    "{token} appears on two nets ({where_} and \
                     {spot}.internal_nets[{previous}]) — one pin is on one node"
                )));
            }
        }
        if members.is_empty() {
            return Err(shape(format!(
                "{where_} has no pin members — a net that connects nothing is not a net"
            )));
        }
        members.sort();
        nets.push((members, port));
    }

    let mut port_counts: BTreeMap<String, usize> = BTreeMap::new();
    for name in declared_ports.keys() {
        port_counts.insert(name.clone(), 0);
    }
    let mut circuit_nets: Vec<Value> = Vec::new();
    let mut seen_net_ids: BTreeSet<String> = BTreeSet::new();
    for (index, (members, port)) in nets.iter().enumerate() {
        let class = match port {
            Some(name) => {
                if let Some(count) = port_counts.get_mut(name) {
                    *count += 1;
                }
                let ruling = curated_ruling(rulings, name, spot)?;
                if ruling.port_pin_only {
                    return Err(shape(format!(
                        "{spot}.ports.{name} is curated as port_pin_only but appears in \
                         {spot}.internal_nets[{index}] — the ruling and the source disagree"
                    )));
                }
                ruling.class
            }
            None => String::new(),
        };
        let net_id = match port {
            Some(name) => format!("{PORT_NET_PREFIX}{name}"),
            None => auto_net_id(members),
        };
        if !seen_net_ids.insert(net_id.clone()) {
            return Err(shape(format!(
                "{spot}: two nets both computed id {net_id:?}"
            )));
        }
        let mut body = Map::new();
        body.insert("id".to_owned(), Value::String(net_id));
        if !class.is_empty() {
            body.insert("class".to_owned(), Value::String(class));
        }
        body.insert(
            "members".to_owned(),
            Value::Array(members.iter().cloned().map(Value::String).collect()),
        );
        body.insert(
            "provenance".to_owned(),
            Value::String(PROVENANCE_AI.to_owned()),
        );
        circuit_nets.push(Value::Object(body));
    }

    let mut wildcards: BTreeSet<String> = BTreeSet::new();
    for (members, _) in &nets {
        for member in members {
            if member.contains('*') {
                wildcards.insert(member.clone());
            }
        }
    }

    let mut ports: Vec<CatalogPort> = Vec::new();
    let mut circuit_interfaces: Vec<Value> = Vec::new();
    let mut pin_only: Vec<String> = Vec::new();
    for (name, entry) in declared_ports {
        let where_ = format!("{spot}.ports.{name}");
        let entry = as_object(entry, &where_)?;
        let at = text_field(entry, "at", &where_)?.to_owned();
        let (at_role, _pin) = split_pin(&at, &where_)?;
        if !roles.contains_key(at_role) {
            return Err(shape(format!(
                "{where_}.at is {at:?}, whose role {at_role:?} this module does not declare"
            )));
        }
        let default_net = optional_text(entry, "default_net");
        let ruling = curated_ruling(rulings, name, spot)?;
        if !ruling.part.is_empty() && !roles.contains_key(ruling.part.as_str()) {
            return Err(shape(format!(
                "{spot}.ports.{name}.part is {:?}, which is not a role of this module",
                ruling.part
            )));
        }
        let count = port_counts.get(name).copied().unwrap_or(0);
        let net_id = format!("{PORT_NET_PREFIX}{name}");
        let listed_pins = contract.port_pins.get(name);
        if ruling.port_pin_only {
            if listed_pins.is_some() {
                return Err(shape(format!(
                    "{where_} is curated as port_pin_only but {spot}.portPins also lists its \
                     pins — this port's net is the port pin alone, so it has no second member \
                     to name"
                )));
            }
            if count != 0 {
                return Err(shape(format!(
                    "{where_} is curated as port_pin_only but PORT:{name} appears {count} \
                     time(s) in internal_nets"
                )));
            }
            if pin_owner.contains_key(&at) {
                return Err(shape(format!(
                    "{where_} is curated as port_pin_only but {at} is already a member of \
                     another net — the pin would be on two nodes"
                )));
            }
            if book.is_some() {
                // The port pin is the whole net, so it has to identify one pin.
                resolve_pin(&role_entries, &at, &where_)?;
            }
            circuit_nets.push(json!({
                "id": net_id.clone(),
                "class": ruling.class,
                "members": [at.clone()],
                "provenance": PROVENANCE_AI,
            }));
            pin_only.push(name.clone());
        } else {
            if count != 1 {
                return Err(shape(format!(
                    "{where_} appears on {count} nets; every port sits on exactly one"
                )));
            }
            let members = nets
                .iter()
                .find(|(_, port)| port.as_deref() == Some(name.as_str()))
                .map(|(members, _)| members)
                .ok_or_else(|| shape(format!("{where_} has no net")))?;
            match listed_pins {
                // 038Q12: upstream names one physical pad group by one pin name
                // (`J_USB.VBUS`), and `portPins` says which pads the port is on.
                // Each listed pin has to be a member of this net and to be one of
                // the pins `at` names, so the port and the pads stay one statement.
                Some(listed) if book.is_some() => {
                    if listed.is_empty() {
                        return Err(shape(format!(
                            "{spot}.portPins.{name} is empty — the field exists to name the \
                             physical pins of the port, and an empty list names none"
                        )));
                    }
                    let at_pin = split_pin(&at, &where_)?.1;
                    for entry in listed {
                        let pin = resolve_pin(&role_entries, entry, &where_)?;
                        if pin.role != at_role {
                            return Err(shape(format!(
                                "{where_}.at is {at}, but {spot}.portPins.{name} lists {entry} \
                                 of role {:?} — a port's pins are pins of the part it names",
                                pin.role
                            )));
                        }
                        let named_by_at = role_entries
                            .get(pin.role.as_str())
                            .and_then(|profile| {
                                profile
                                    .pins
                                    .iter()
                                    .find(|candidate| candidate.number == pin.number)
                            })
                            .is_some_and(|candidate| {
                                pin.number == at_pin || candidate.name == at_pin
                            });
                        if !named_by_at {
                            return Err(shape(format!(
                                "{where_}.at is {at}, but {spot}.portPins.{name} lists {entry}, \
                                 which that pin name or number does not carry"
                            )));
                        }
                        if !members.iter().any(|member| member == entry) {
                            return Err(shape(format!(
                                "{where_}.at is {at} and {spot}.portPins.{name} lists {entry}, \
                                 but the port's net holds ({}) — a port pin that is not on the \
                                 port's net is a lie",
                                members.join(", ")
                            )));
                        }
                    }
                }
                _ => {
                    // A wildcard member (`U.VOUT*`) covers the pin the port names;
                    // the port's `at` is never expanded or guessed into a pin
                    // number here.
                    let covered = members.iter().any(|member| member == &at)
                        || members.iter().any(|member| member == &format!("{at}*"));
                    if !covered {
                        return Err(shape(format!(
                            "{where_}.at is {at}, which is not a member of its own net ({}) — a \
                             port whose pin is not on the net it names is a lie",
                            members.join(", ")
                        )));
                    }
                }
            }
            if book.is_some() && listed_pins.is_none() {
                // A bound port names one physical pin: `at` has to be that pin,
                // which a duplicated pin name cannot say (`resolve_pin` refuses).
                // A port that states `portPins` says which pads it is on instead.
                resolve_pin(&role_entries, &at, &where_)?;
            }
        }
        circuit_interfaces.push(interface(&net_id, name, &ruling));
        ports.push(CatalogPort {
            name: name.clone(),
            net: net_id,
            direction: ruling.direction,
            class: ruling.class,
            default_net,
            part: ruling.part,
        });
    }
    ports.sort_by(|left, right| left.name.cmp(&right.name));
    circuit_interfaces.sort_by(|left, right| {
        left["net"]
            .as_str()
            .unwrap_or("")
            .cmp(right["net"].as_str().unwrap_or(""))
    });
    circuit_nets.sort_by(|left, right| {
        left["id"]
            .as_str()
            .unwrap_or("")
            .cmp(right["id"].as_str().unwrap_or(""))
    });

    // 038Q12: every physical pin of every profile lands in exactly one of three
    // classes — connected, NC, unstated — and the run writes the last two. A pin
    // group that mapped to no member, a group curation invented, an NC that the
    // wiring already uses, and one pad written two ways across two nets are each
    // refused here.
    let mut no_connects: Vec<PhysicalPin> = Vec::new();
    let mut unstated_pins: Vec<String> = Vec::new();
    if book.is_some() {
        for member in contract.pin_groups.keys() {
            if !raw_wildcards.contains(member) {
                return Err(shape(format!(
                    "{spot}.pinGroups maps {member}, which no net of this module carries — a \
                     mapping for a group the source does not state is a stale decision"
                )));
            }
        }
        let mut on_net: BTreeMap<PhysicalPin, String> = BTreeMap::new();
        for net in &circuit_nets {
            let id = net["id"].as_str().unwrap_or("").to_owned();
            for member in net["members"].as_array().into_iter().flatten() {
                let token = member
                    .as_str()
                    .ok_or_else(|| shape(format!("{spot}: net {id} holds a non-string member")))?;
                let pin = resolve_pin(&role_entries, token, &format!("{spot} net {id}"))?;
                if let Some(previous) = on_net.insert(pin.clone(), id.clone())
                    && previous != id
                {
                    return Err(shape(format!(
                        "{spot}: {} is written as {token} on net {id} but is already on net \
                         {previous} — one physical pin is on one node, however it is spelled",
                        pin.label()
                    )));
                }
            }
        }
        for entry in &contract.nc {
            let where_ = format!("{spot}.nc");
            let pin = resolve_pin(&role_entries, entry, &where_)?;
            if no_connects.iter().any(|existing| existing == &pin) {
                return Err(shape(format!(
                    "{where_}: {entry} resolves to {}, which is already listed — one pin, one \
                     no-connect",
                    pin.label()
                )));
            }
            if let Some(net) = on_net.get(&pin) {
                return Err(shape(format!(
                    "{where_}: {entry} is a no-connect, but {} is a member of net {net} — NC \
                     and a net cannot both be true of one pin",
                    pin.label()
                )));
            }
            no_connects.push(pin);
        }
        no_connects.sort_by_key(PhysicalPin::label);
        let mut unstated: BTreeSet<String> = BTreeSet::new();
        for (role, profile) in &role_entries {
            for pin in &profile.pins {
                let physical = PhysicalPin {
                    role: (*role).clone(),
                    number: pin.number.clone(),
                };
                if on_net.contains_key(&physical) || no_connects.iter().any(|nc| nc == &physical) {
                    continue;
                }
                unstated.insert(physical.label());
            }
        }
        unstated_pins = unstated.into_iter().collect();
    }

    let mut limitations = if let Some(book) = book {
        vec![
            "candidate: the electrical facts come from the pinned upstream sample; each \
             part's device identity is bound in the managed symbol book, which checks \
             hashes, LCSC/MPN and pin names and proves nothing about the circuit"
                .to_owned(),
            format!(
                "identity bound: every part resolves through blocklib/symbols/index.json to a \
                 profile in blocklib/symbols/profiles.json (profileBookSha256 {}); offline \
                 compile, editor readback and hardware acceptance are all unfinished",
                book.profile_book_sha256
            ),
            "no compose, native CBB, PCB or hardware claim is made here".to_owned(),
            "each port's default_net is a suggestion for a future composition and is not \
             wiring: ports that suggest the same net (VIN and EN) stay separate nets here"
                .to_owned(),
        ]
    } else {
        vec![
            "candidate: the electrical facts come from the pinned upstream sample; this \
             repository has verified neither the symbol nor the device identity (see \
             identityStatus)"
                .to_owned(),
            "not for draw compile: no SymbolProfile has been read, so pin numbers and bodies \
             are unverified, and every part's circuit symbolRef is the GENERIC-<role> \
             placeholder rather than a resolved symbol"
                .to_owned(),
            "no compose, native CBB, PCB or hardware claim is made here".to_owned(),
            "each port's default_net is a suggestion for a future composition and is not \
             wiring: ports that suggest the same net (VIN and EN) stay separate nets here"
                .to_owned(),
        ]
    };
    if !wildcards.is_empty() {
        limitations.push(format!(
            "wildcard pin groups are kept as written ({}) and were not expanded to \
             physical pads — no pin number was guessed",
            wildcards.iter().cloned().collect::<Vec<_>>().join(", ")
        ));
    }
    if !pin_only.is_empty() {
        limitations.push(format!(
            "ports {} have no upstream internal net; their net is the port pin alone \
             (curated netSource=port_pin_only), not an inferred connection",
            pin_only.join(", ")
        ));
    }
    if book.is_some() && !contract.pin_groups.is_empty() {
        limitations.push(format!(
            "explicit pin groups ({}) name the physical pins the upstream wildcard members \
             stood for, decided one group at a time in contracts/module-import/curation.json; \
             naming several pins of one symbol is not a claim that the symbol shorts them \
             internally, and it is not a datasheet reading, an offline compile, an editor \
             readback or a hardware acceptance",
            contract
                .pin_groups
                .keys()
                .cloned()
                .collect::<Vec<_>>()
                .join(", ")
        ));
    }

    let circuit = json!({
        "draft": true,
        "kind": CIRCUIT_SPEC_KIND,
        "nc": no_connects
            .iter()
            .map(|pin| json!({"pin": pin.label(), "provenance": PROVENANCE_AI}))
            .collect::<Vec<Value>>(),
        "nets": circuit_nets,
        "openInterfaces": circuit_interfaces,
        "operatingConditions": Map::<String, Value>::new(),
        "parts": circuit_parts,
        "specVersion": CIRCUIT_SPEC_VERSION,
    });
    Ok(Normalised {
        title: id.to_owned(),
        circuit,
        parts: catalog_parts,
        ports,
        wildcards: wildcards.into_iter().collect(),
        unstated: unstated_pins,
        limitations,
        attribution,
    })
}

// ------------------------------------------------------------------ topology

fn topology_module(
    id: &str,
    source: &Value,
    rulings: &Map<String, Value>,
    spot: &str,
) -> Result<Normalised> {
    let module = object_field(source, "module", spot)?;
    let module_spot = format!("{spot}.module");
    let source_id = text_field(module, "id", &module_spot)?;
    if source_id != id {
        return Err(shape(format!(
            "{spot}.id is {id:?} but the source module declares {source_id:?}"
        )));
    }
    let title = text_field(module, "title", &module_spot)?.to_owned();
    let maturity = text_field(module, "maturity", &module_spot)?.to_owned();
    let verification = object_field(module, "verification", &module_spot)?;

    let raw_parts = list_field(module, "parts", &module_spot)?;
    if raw_parts.is_empty() {
        return Err(shape(format!("{module_spot}.parts is empty")));
    }
    // (role, pin number) -> net, and (role, pin number) -> connectionState
    let mut pin_nets: BTreeMap<(String, String), String> = BTreeMap::new();
    let mut pin_states: BTreeMap<(String, String), String> = BTreeMap::new();
    let mut roles: BTreeSet<String> = BTreeSet::new();
    let mut circuit_parts: Vec<Value> = Vec::new();
    let mut catalog_parts: Vec<Value> = Vec::new();
    for (index, raw_part) in raw_parts.iter().enumerate() {
        let where_ = format!("{module_spot}.parts[{index}]");
        let raw_part = as_object(raw_part, &where_)?;
        let role = text_field(raw_part, "role", &where_)?.to_owned();
        if role.contains('.') {
            return Err(shape(format!(
                "{where_}.role is {role:?}, which contains '.' — a member is '<role>.<pin>'"
            )));
        }
        if !roles.insert(role.clone()) {
            return Err(shape(format!(
                "{where_}.role is {role:?}, already used — one role is one part"
            )));
        }
        let lcsc = text_field(raw_part, "lcsc", &where_)?.to_owned();
        let footprint = text_field(raw_part, "footprint", &where_)?.to_owned();
        let device = object_field(raw_part, "device", &where_)?;
        let device_name = optional_text(device, "name");
        let library_uuid = optional_text(device, "libraryUuid");
        let device_uuid = optional_text(device, "deviceUuid");
        let pins = list_field(raw_part, "pins", &where_)?;
        if pins.is_empty() {
            return Err(shape(format!("{where_}.pins is empty")));
        }
        for (pin_index, raw_pin) in pins.iter().enumerate() {
            let pin_spot = format!("{where_}.pins[{pin_index}]");
            let raw_pin = as_object(raw_pin, &pin_spot)?;
            let number = text_field(raw_pin, "number", &pin_spot)?.to_owned();
            text_field(raw_pin, "name", &pin_spot)?;
            let key = (role.clone(), number.clone());
            if pin_nets.contains_key(&key) {
                return Err(shape(format!(
                    "{pin_spot}.number is {number:?}, already used by role {role:?}"
                )));
            }
            let net = match raw_pin.get("net") {
                None | Some(Value::Null) => String::new(),
                Some(Value::String(value)) => value.clone(),
                Some(other) => {
                    return Err(shape(format!(
                        "{pin_spot}.net is {other}; expected a net id string"
                    )));
                }
            };
            if let Some(state) = raw_pin.get("connectionState") {
                let state = state
                    .as_str()
                    .ok_or_else(|| shape(format!("{pin_spot}.connectionState must be a string")))?;
                pin_states.insert(key.clone(), state.to_owned());
            }
            pin_nets.insert(key, net);
        }
        circuit_parts.push(json!({
            "id": role,
            "symbolRef": format!("{GENERIC_SYMBOL_PREFIX}{role}"),
            "value": "",
            "mpn": "",
            "lcsc": lcsc,
            "params": Map::<String, Value>::new(),
            "provenance": PROVENANCE_AI,
        }));
        let mut catalog_part = Map::new();
        catalog_part.insert("role".to_owned(), Value::String(role.clone()));
        catalog_part.insert("symbolRef".to_owned(), Value::String(String::new()));
        // `device.name` is the symbol's display name; it is not an MPN, and this
        // batch does not promote it to one.
        catalog_part.insert("deviceName".to_owned(), Value::String(device_name));
        catalog_part.insert("footprint".to_owned(), Value::String(footprint));
        catalog_part.insert("lcsc".to_owned(), Value::String(lcsc));
        catalog_part.insert("libraryUuid".to_owned(), Value::String(library_uuid));
        catalog_part.insert("deviceUuid".to_owned(), Value::String(device_uuid));
        catalog_parts.push(Value::Object(catalog_part));
    }

    let raw_nets = list_field(module, "nets", &module_spot)?;
    let mut members_by_net: BTreeMap<String, Vec<String>> = BTreeMap::new();
    let mut port_nets: BTreeMap<String, String> = BTreeMap::new();
    let mut order: Vec<String> = Vec::new();
    for (index, raw_net) in raw_nets.iter().enumerate() {
        let where_ = format!("{module_spot}.nets[{index}]");
        let raw_net = as_object(raw_net, &where_)?;
        let net_id = text_field(raw_net, "id", &where_)?.to_owned();
        if members_by_net.contains_key(&net_id) {
            return Err(shape(format!(
                "{where_}.id is {net_id:?}, already declared"
            )));
        }
        let members = list_field(raw_net, "members", &where_)?;
        if members.is_empty() {
            return Err(shape(format!(
                "{where_}.members is empty — a net that connects nothing is not a net"
            )));
        }
        let mut kept: Vec<String> = Vec::new();
        for member in members {
            let member = member
                .as_str()
                .ok_or_else(|| shape(format!("{where_}.members holds a non-string")))?;
            let (role, pin) = split_pin(member, &where_)?;
            if !roles.contains(role) {
                return Err(shape(format!(
                    "{where_} names {member}, whose role {role:?} this module does not declare"
                )));
            }
            let key = (role.to_owned(), pin.to_owned());
            let Some(authoritative) = pin_nets.get(&key) else {
                return Err(shape(format!(
                    "{where_} names {member}, which role {role:?} does not have as a pin"
                )));
            };
            if authoritative != &net_id {
                return Err(shape(format!(
                    "{where_} lists {member} but that pin's own net is {authoritative:?} — \
                     pins[].net and nets[].members must agree"
                )));
            }
            if kept.iter().any(|existing| existing == member) {
                return Err(shape(format!("{where_} lists {member} twice")));
            }
            kept.push(member.to_owned());
        }
        kept.sort();
        if let Some(port) = raw_net.get("port") {
            let port = port
                .as_str()
                .ok_or_else(|| shape(format!("{where_}.port must be a string")))?;
            let expected = format!("{PORT_NET_PREFIX}{port}");
            if net_id != expected {
                return Err(shape(format!(
                    "{where_} declares port {port:?} but its id is {net_id:?}; a port net is \
                     named {expected}"
                )));
            }
            if port_nets.insert(port.to_owned(), net_id.clone()).is_some() {
                return Err(shape(format!(
                    "{where_} declares port {port:?} twice — one port, one net"
                )));
            }
        } else if net_id.starts_with(PORT_NET_PREFIX) {
            return Err(shape(format!(
                "{where_} is named {net_id:?} but declares no port"
            )));
        }
        order.push(net_id.clone());
        members_by_net.insert(net_id, kept);
    }

    // Every pin that states a net must be listed by that net; every pin that
    // states none is *unstated*, and only `connectionState: "unconnected"` is NC.
    let mut unstated: BTreeSet<String> = BTreeSet::new();
    let mut nc: Vec<String> = Vec::new();
    for ((role, number), net) in &pin_nets {
        let key = role.clone() + "." + number;
        let unconnected = pin_states
            .get(&(role.clone(), number.clone()))
            .is_some_and(|state| state == "unconnected");
        if net.is_empty() {
            if unconnected {
                nc.push(key);
            } else {
                unstated.insert(key);
            }
            continue;
        }
        let Some(members) = members_by_net.get(net) else {
            return Err(shape(format!(
                "{module_spot}: pin {key} sits on net {net:?}, which the module does not \
                 declare"
            )));
        };
        if !members.iter().any(|member| member == &key) {
            return Err(shape(format!(
                "{module_spot}: pin {key} says it sits on {net:?}, but that net does not list \
                 it — pins[].net and nets[].members must agree"
            )));
        }
        if unconnected {
            return Err(shape(format!(
                "{module_spot}: pin {key} is connectionState unconnected but a member of net \
                 {net:?} — NC cannot contradict the wiring"
            )));
        }
    }
    nc.sort();

    let mut ports: Vec<CatalogPort> = Vec::new();
    let mut circuit_nets: Vec<Value> = Vec::new();
    let mut circuit_interfaces: Vec<Value> = Vec::new();
    for net_id in &order {
        let members = members_by_net
            .get(net_id)
            .cloned()
            .expect("every ordered net was inserted");
        let port = port_nets
            .iter()
            .find(|(_name, id)| *id == net_id)
            .map(|(name, _id)| name.clone());
        match &port {
            Some(name) => {
                let ruling = curated_ruling(rulings, name, spot)?;
                if ruling.port_pin_only {
                    return Err(shape(format!(
                        "{spot}.ports.{name} is curated as port_pin_only but the source \
                         already declares net {net_id}"
                    )));
                }
                // Same rule as a Block port: an interface may name the part that
                // realises it, and that part has to exist in this module.
                if !ruling.part.is_empty() && !roles.contains(ruling.part.as_str()) {
                    return Err(shape(format!(
                        "{spot}.ports.{name}.part is {:?}, which is not a role of this module",
                        ruling.part
                    )));
                }
                circuit_nets.push(json!({
                    "id": net_id.clone(),
                    "class": ruling.class,
                    "members": members,
                    "provenance": PROVENANCE_AI,
                }));
                circuit_interfaces.push(interface(net_id, name, &ruling));
                ports.push(CatalogPort {
                    name: name.clone(),
                    net: net_id.clone(),
                    direction: ruling.direction,
                    class: ruling.class,
                    default_net: String::new(),
                    part: ruling.part,
                });
            }
            None => {
                circuit_nets.push(json!({
                    "id": net_id.clone(),
                    "members": members,
                    "provenance": PROVENANCE_AI,
                }));
            }
        }
    }
    for name in rulings.keys() {
        if !port_nets.contains_key(name) {
            return Err(shape(format!(
                "{spot}.ports.{name} is curated but the source declares no such port net"
            )));
        }
    }
    ports.sort_by(|left, right| left.name.cmp(&right.name));

    let mut limitations = vec![
        "candidate: the electrical facts come from the pinned upstream sample; this \
         repository has verified neither the symbol nor the device identity (see \
         identityStatus)"
            .to_owned(),
        "not for draw compile: no SymbolProfile has been read, so pin numbers and bodies \
         are unverified, and every part's circuit symbolRef is the GENERIC-<role> \
         placeholder rather than a resolved symbol"
            .to_owned(),
        "no compose, native CBB, PCB or hardware claim is made here".to_owned(),
        "net ids are kept as written, so internal.* and port.* nets of one variant are \
         never merged with another variant"
            .to_owned(),
    ];
    for key in [
        "pinNetReadback",
        "deviceIdentityResolution",
        "geometry",
        "pcb",
        "bringup",
    ] {
        let status = verification
            .get(key)
            .and_then(Value::as_str)
            .unwrap_or("unstated");
        limitations.push(format!("upstream {key}: {status}"));
    }
    limitations.push(format!("upstream maturity: {maturity}"));

    let circuit = json!({
        "draft": true,
        "kind": CIRCUIT_SPEC_KIND,
        "nc": nc.iter().map(|pin| json!({"pin": pin, "provenance": PROVENANCE_AI})).collect::<Vec<_>>(),
        "nets": circuit_nets,
        "openInterfaces": circuit_interfaces,
        "operatingConditions": Map::<String, Value>::new(),
        "parts": circuit_parts,
        "specVersion": CIRCUIT_SPEC_VERSION,
    });
    Ok(Normalised {
        title,
        circuit,
        parts: catalog_parts,
        ports,
        wildcards: Vec::new(),
        unstated: unstated.into_iter().collect(),
        limitations,
        // A role topology states no author; this shape does not get one invented.
        attribution: None,
    })
}

// -------------------------------------------------------------------- helpers

fn interface(net: &str, role: &str, ruling: &Ruling) -> Value {
    let mut body = Map::new();
    body.insert(
        "direction".to_owned(),
        Value::String(ruling.direction.clone()),
    );
    body.insert("net".to_owned(), Value::String(net.to_owned()));
    body.insert(
        "provenance".to_owned(),
        Value::String(PROVENANCE_AI.to_owned()),
    );
    // The interface contract also refuses an empty `role`, so the upstream port
    // name is kept as the role name rather than dropped.
    body.insert("role".to_owned(), Value::String(role.to_owned()));
    if !ruling.part.is_empty() {
        body.insert("part".to_owned(), Value::String(ruling.part.clone()));
    }
    Value::Object(body)
}

fn auto_net_id(members: &[String]) -> String {
    let mut sorted: Vec<&str> = members.iter().map(String::as_str).collect();
    sorted.sort_unstable();
    format!("{AUTO_NET_PREFIX}{}", sorted.join("|"))
}

fn split_pin<'a>(token: &'a str, where_: &str) -> Result<(&'a str, &'a str)> {
    match token.split_once('.') {
        Some((role, pin)) if !role.is_empty() && !pin.is_empty() => Ok((role, pin)),
        _ => Err(shape(format!(
            "{where_} holds {token:?}; a pin is written '<role>.<pin>'"
        ))),
    }
}

fn shape(message: impl Into<String>) -> ContractError {
    ContractError::Shape(message.into())
}

fn render(value: &Value) -> Result<String> {
    Ok(serde_json::to_string_pretty(value)? + "\n")
}

/// Resolve one curation-declared input path against the root, refusing anything
/// that could leave it: an absolute path, a root/prefix component, or `..`.
fn relative_input(root: &Path, relative: &str, where_: &str) -> Result<PathBuf> {
    let parts = normal_components(relative, where_, true)?;
    let mut path = root.to_path_buf();
    for part in parts {
        path.push(part);
    }
    Ok(path)
}

/// A file written under `--output` must name only ordinary components: no
/// absolute path, no `..`, no `.`, no drive prefix. The canonical spelling is
/// what a duplicate check compares, so `a//b` and `a/b` are the same file.
fn output_name(relative: &str, where_: &str) -> Result<String> {
    Ok(normal_components(relative, where_, false)?.join("/"))
}

fn normal_components(relative: &str, where_: &str, allow_current: bool) -> Result<Vec<String>> {
    let text = relative.trim();
    if text.is_empty() {
        return Err(shape(format!("{where_} is empty")));
    }
    let path = Path::new(text);
    if path.is_absolute() {
        return Err(shape(format!(
            "{where_} is {relative:?}; an absolute path is refused — it must be a \
             relative path that stays inside the directory it is relative to"
        )));
    }
    let mut parts: Vec<String> = Vec::new();
    for component in path.components() {
        match component {
            Component::Normal(part) => parts.push(part.to_string_lossy().into_owned()),
            Component::CurDir if allow_current => {}
            other => {
                return Err(shape(format!(
                    "{where_} is {relative:?}; the {other:?} component is refused — the \
                     path must stay inside the directory it is relative to"
                )));
            }
        }
    }
    if parts.is_empty() {
        return Err(shape(format!(
            "{where_} is {relative:?}, which names no file"
        )));
    }
    Ok(parts)
}

fn display_path(root: &Path, path: &Path) -> String {
    let relative = path.strip_prefix(root).unwrap_or(path);
    relative
        .components()
        .map(|component| component.as_os_str().to_string_lossy().into_owned())
        .collect::<Vec<_>>()
        .join("/")
}

fn sha256_hex(bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    format!("{:x}", hasher.finalize())
}

/// The digest this module writes into its manifest. Public so a caller can
/// verify an output directory without re-implementing the hashing.
pub fn file_sha256(path: &Path) -> Result<String> {
    Ok(sha256_hex(&fs::read(path)?))
}

fn read_object(path: &Path, what: &str) -> Result<Map<String, Value>> {
    let bytes = fs::read(path)?;
    let value: Value = serde_json::from_slice(&bytes)?;
    Ok(as_object(&value, what)?.clone())
}

fn read_hashed(path: &Path, root: &Path, inputs: &mut BTreeMap<String, String>) -> Result<Value> {
    let bytes = fs::read(path)?;
    inputs.insert(display_path(root, path), sha256_hex(&bytes));
    Ok(serde_json::from_slice(&bytes)?)
}

fn as_object<'a>(value: &'a Value, where_: &str) -> Result<&'a Map<String, Value>> {
    value
        .as_object()
        .ok_or_else(|| shape(format!("{where_} must be a JSON object")))
}

fn as_array<'a>(value: &'a Value, where_: &str) -> Result<&'a Vec<Value>> {
    value
        .as_array()
        .ok_or_else(|| shape(format!("{where_} must be a JSON array")))
}

/// A JSON object reached either as a `Map` (already unwrapped) or as a `Value`;
/// the readers below should not care which.
trait Fields {
    fn fields(&self) -> Option<&Map<String, Value>>;
}

impl Fields for Map<String, Value> {
    fn fields(&self) -> Option<&Map<String, Value>> {
        Some(self)
    }
}

impl Fields for Value {
    fn fields(&self) -> Option<&Map<String, Value>> {
        self.as_object()
    }
}

fn object_field<'a, T: Fields + ?Sized>(
    body: &'a T,
    key: &str,
    where_: &str,
) -> Result<&'a Map<String, Value>> {
    let fields = body
        .fields()
        .ok_or_else(|| shape(format!("{where_} must be a JSON object")))?;
    let value = fields
        .get(key)
        .ok_or_else(|| shape(format!("{where_}.{key} is missing")))?;
    as_object(value, &format!("{where_}.{key}"))
}

fn list_field<'a, T: Fields + ?Sized>(
    body: &'a T,
    key: &str,
    where_: &str,
) -> Result<&'a Vec<Value>> {
    let fields = body
        .fields()
        .ok_or_else(|| shape(format!("{where_} must be a JSON object")))?;
    let value = fields
        .get(key)
        .ok_or_else(|| shape(format!("{where_}.{key} is missing")))?;
    as_array(value, &format!("{where_}.{key}"))
}

fn text_field<'a, T: Fields + ?Sized>(body: &'a T, key: &str, where_: &str) -> Result<&'a str> {
    body.fields()
        .ok_or_else(|| shape(format!("{where_} must be a JSON object")))?
        .get(key)
        .and_then(Value::as_str)
        .ok_or_else(|| shape(format!("{where_}.{key} must be a string")))
}

fn optional_text<T: Fields + ?Sized>(body: &T, key: &str) -> String {
    match body.fields().and_then(|fields| fields.get(key)) {
        Some(Value::String(value)) => value.clone(),
        _ => String::new(),
    }
}

fn expect_text<T: Fields + ?Sized>(
    body: &T,
    key: &str,
    where_: &str,
    expected: &str,
) -> Result<()> {
    let actual = text_field(body, key, where_)?;
    if actual != expected {
        return Err(shape(format!(
            "{where_}.{key} is {actual:?}; this build reads {expected:?}"
        )));
    }
    Ok(())
}
