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

        let normalised = match kind.as_str() {
            "block_template" => block_module(&id, &source, library, rulings, &spot)?,
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
            "identityStatus": IDENTITY_UNVERIFIED,
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

        circuit_parts.push(json!({
            "id": role,
            "symbolRef": format!("{GENERIC_SYMBOL_PREFIX}{role}"),
            "value": value,
            "mpn": mpn,
            "lcsc": lcsc,
            "params": Map::<String, Value>::new(),
            "provenance": PROVENANCE_AI,
        }));
        let mut catalog_part = Map::new();
        catalog_part.insert("role".to_owned(), Value::String(role.clone()));
        catalog_part.insert("symbolRef".to_owned(), Value::String(String::new()));
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

    let raw_nets = list_field(source, "internal_nets", spot)?;
    if raw_nets.is_empty() {
        return Err(shape(format!("{spot}.internal_nets is empty")));
    }
    let mut nets: Vec<(Vec<String>, Option<String>)> = Vec::new();
    let mut pin_owner: BTreeMap<String, usize> = BTreeMap::new();
    for (index, raw_net) in raw_nets.iter().enumerate() {
        let where_ = format!("{spot}.internal_nets[{index}]");
        let tokens = as_array(raw_net, &where_)?;
        let mut members: Vec<String> = Vec::new();
        let mut port: Option<String> = None;
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
        if ruling.port_pin_only {
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
            // A wildcard member (`U.VOUT*`) covers the pin the port names; the
            // port's `at` is never expanded or guessed into a pin number here.
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
        "each port's default_net is a suggestion for a future composition and is not \
         wiring: ports that suggest the same net (VIN and EN) stay separate nets here"
            .to_owned(),
    ];
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

    let circuit = json!({
        "draft": true,
        "kind": CIRCUIT_SPEC_KIND,
        "nc": Vec::<Value>::new(),
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
        unstated: Vec::new(),
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
