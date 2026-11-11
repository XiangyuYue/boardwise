//! 038Q2: the normaliser's contract.
//!
//! Two halves. The first reads the repository's own pinned inputs and pins what
//! the four candidate modules are: their parts, nets, ports, wildcard pins,
//! attribution, the published licence and the "nothing here is verified" marks.
//! The second builds small synthetic inputs under `CARGO_TARGET_TMPDIR` and pins
//! the refusals — quantity, unknown role, an undeclared `PORT:`, a port outside
//! its own net, an unruled port, `pins[].net` disagreeing with `nets[].members`,
//! explicit NC versus a pin that merely states no net, a ledger that disagrees
//! with the curation, path escape in either direction, and the never-overwrite
//! write rule.
//!
//! Scratch paths are a fresh directory per call (`process id` + an atomic
//! counter): nothing is deleted, and a repeated `cargo test` never has to clean
//! anything up.

use boardwise_core::module_import::{self, file_sha256};
use serde_json::{Value, json};
use std::collections::BTreeSet;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicUsize, Ordering};

fn repository_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .ancestors()
        .nth(3)
        .expect("repository root")
        .to_path_buf()
}

fn curation_path() -> PathBuf {
    repository_root().join("contracts/module-import/curation.json")
}

fn repository_plan() -> module_import::ImportPlan {
    module_import::plan(&repository_root(), &curation_path()).expect("the pinned inputs normalise")
}

fn scratch(name: &str) -> PathBuf {
    static NEXT: AtomicUsize = AtomicUsize::new(0);
    let serial = NEXT.fetch_add(1, Ordering::Relaxed);
    let directory = Path::new(env!("CARGO_TARGET_TMPDIR"))
        .join("module-import-core")
        .join(format!("{}-{serial}-{name}", std::process::id()));
    fs::create_dir_all(&directory).expect("scratch directory is writable");
    directory
}

fn write_json(path: &Path, value: &Value) {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).expect("fixture directory is writable");
    }
    fs::write(
        path,
        serde_json::to_string_pretty(value).expect("fixture serializes") + "\n",
    )
    .expect("fixture is writable");
}

fn module_of(plan: &module_import::ImportPlan, id: &str) -> Value {
    plan.modules
        .iter()
        .find(|module| module.id == id)
        .unwrap_or_else(|| panic!("{id} is in the plan"))
        .circuit
        .clone()
}

fn net(module: &Value, id: &str) -> Vec<String> {
    module["nets"]
        .as_array()
        .expect("nets is a list")
        .iter()
        .find(|net| net["id"] == id)
        .unwrap_or_else(|| panic!("net {id} exists"))["members"]
        .as_array()
        .expect("members is a list")
        .iter()
        .map(|member| member.as_str().expect("member is a string").to_owned())
        .collect()
}

fn interface(module: &Value, net_id: &str) -> Value {
    module["openInterfaces"]
        .as_array()
        .expect("interfaces is a list")
        .iter()
        .find(|entry| entry["net"] == net_id)
        .unwrap_or_else(|| panic!("interface over {net_id} exists"))
        .clone()
}

fn catalog_of(plan: &module_import::ImportPlan) -> Value {
    let file = plan
        .files
        .iter()
        .find(|file| file.path == "catalog.json")
        .expect("the plan carries catalog.json");
    serde_json::from_str(&file.bytes).expect("catalog is JSON")
}

fn catalog_module(plan: &module_import::ImportPlan, id: &str) -> Value {
    let catalog = catalog_of(plan);
    catalog["modules"]
        .as_array()
        .expect("modules is a list")
        .iter()
        .find(|module| module["id"] == id)
        .unwrap_or_else(|| panic!("{id} is in the catalog"))
        .clone()
}

fn manifest_of(plan: &module_import::ImportPlan) -> Value {
    let file = plan
        .files
        .iter()
        .find(|file| file.path == "manifest.json")
        .expect("the plan carries manifest.json");
    serde_json::from_str(&file.bytes).expect("manifest is JSON")
}

fn output_file<'a>(
    plan: &'a module_import::ImportPlan,
    path: &str,
) -> &'a module_import::OutputFile {
    plan.files
        .iter()
        .find(|file| file.path == path)
        .unwrap_or_else(|| panic!("{path} is planned"))
}

fn collect_keys(value: &Value, out: &mut BTreeSet<String>) {
    match value {
        Value::Object(body) => {
            for (key, item) in body {
                out.insert(key.clone());
                collect_keys(item, out);
            }
        }
        Value::Array(items) => {
            for item in items {
                collect_keys(item, out);
            }
        }
        _ => {}
    }
}

const BANNED_KEYS: [&str; 10] = [
    "at",
    "bom_note",
    "desc",
    "pcb_layout",
    "points",
    "rotation",
    "schematic_layout",
    "validated",
    "x",
    "y",
];

// --------------------------------------------------- the repository's assets

#[test]
fn the_four_pinned_assets_normalise_and_are_candidates() {
    let plan = repository_plan();
    assert_eq!(
        plan.module_ids(),
        vec![
            "block.ams1117_ldo_3v3",
            "block.ch340c_usb_serial",
            "block.sy8089_buck_3v3",
            "lib.sy8089_buck_3v3_live",
        ]
    );
    for module in &plan.modules {
        assert_eq!(module.circuit["kind"], "boardwise-circuit-spec");
        assert_eq!(module.circuit["specVersion"], 1);
        assert_eq!(module.circuit["draft"], true);
        assert_eq!(module.circuit["operatingConditions"], json!({}));
        assert_eq!(module.circuit["nc"], json!([]));
        for part in module.circuit["parts"].as_array().expect("parts") {
            assert_eq!(part["provenance"], "ai_asserted");
        }
        for entry in module.circuit["nets"].as_array().expect("nets") {
            assert_eq!(entry["provenance"], "ai_asserted");
            assert!(entry.get("memberProvenance").is_none());
            assert!(
                entry["members"]
                    .as_array()
                    .is_some_and(|list| !list.is_empty())
            );
        }
        for entry in module.circuit["openInterfaces"].as_array().expect("ports") {
            assert_eq!(entry["provenance"], "ai_asserted");
        }
        let catalog = catalog_module(&plan, &module.id);
        assert_eq!(catalog["maturity"], "candidate");
        assert_eq!(catalog["identityStatus"], "unverified");
        assert_eq!(catalog["notForDrawCompile"], true);
        assert_eq!(catalog["circuit"], module.path);
    }
    assert_eq!(
        plan.files
            .iter()
            .map(|file| file.path.as_str())
            .collect::<Vec<_>>(),
        vec![
            "catalog.json",
            "circuits/ams1117_ldo_3v3.circuit.json",
            "circuits/ch340c_usb_serial.circuit.json",
            "circuits/sy8089_buck_3v3.circuit.json",
            "circuits/sy8089_buck_3v3_live.circuit.json",
            "manifest.json",
            "upstream/LICENSE",
        ]
    );
}

type PortRow = (&'static str, &'static str, &'static str, &'static str);

#[test]
fn curated_port_mappings_are_written_verbatim() {
    let plan = repository_plan();
    let expected: Vec<(&str, Vec<PortRow>)> = vec![
        (
            "block.ams1117_ldo_3v3",
            vec![
                ("port.3V3", "3V3", "load", "power"),
                ("port.GND", "GND", "", "gnd"),
                ("port.VIN_5V", "VIN_5V", "source", "power"),
            ],
        ),
        (
            "block.sy8089_buck_3v3",
            vec![
                ("port.3V3", "3V3", "load", "power"),
                ("port.EN", "EN", "input", "signal"),
                ("port.GND", "GND", "", "gnd"),
                ("port.VIN", "VIN", "source", "power"),
            ],
        ),
        (
            "lib.sy8089_buck_3v3_live",
            vec![
                ("port.GND", "GND", "", "gnd"),
                ("port.POWER_IN", "POWER_IN", "source", "power"),
                ("port.POWER_OUT", "POWER_OUT", "load", "power"),
            ],
        ),
        (
            "block.ch340c_usb_serial",
            vec![
                ("port.DTR", "DTR", "output", "signal"),
                ("port.GND", "GND", "", "gnd"),
                ("port.RTS", "RTS", "output", "signal"),
                ("port.RXD", "RXD", "input", "signal"),
                ("port.TXD", "TXD", "output", "signal"),
                ("port.VBUS_5V", "VBUS_5V", "load", "power"),
            ],
        ),
    ];
    for (id, ports) in expected {
        let module = module_of(&plan, id);
        let catalog = catalog_module(&plan, id);
        for (net_id, role, direction, class) in ports {
            let entry = interface(&module, net_id);
            assert_eq!(entry["direction"], direction, "{id} {net_id} direction");
            assert_eq!(entry["role"], role, "{id} {net_id} role");
            let net_class = module["nets"]
                .as_array()
                .expect("nets")
                .iter()
                .find(|net| net["id"] == net_id)
                .expect("port net")["class"]
                .clone();
            assert_eq!(net_class, class, "{id} {net_id} class");
            let catalog_port = catalog["ports"]
                .as_array()
                .expect("catalog ports")
                .iter()
                .find(|port| port["name"] == role)
                .expect("catalog port");
            assert_eq!(catalog_port["direction"], direction);
            assert_eq!(catalog_port["class"], class);
            assert_eq!(catalog_port["net"], net_id);
        }
    }
    // The USB-C receptacle realises the 5V interface, so the interface says so,
    // and `dir: "out"` upstream is not a CircuitSpec direction — curation rules.
    let ch340 = module_of(&plan, "block.ch340c_usb_serial");
    let vbus = interface(&ch340, "port.VBUS_5V");
    assert_eq!(vbus["part"], "J_USB");
    assert_eq!(vbus["direction"], "load");
}

#[test]
fn suggested_net_names_do_not_short_vin_and_en() {
    let plan = repository_plan();
    let module = module_of(&plan, "block.sy8089_buck_3v3");
    let vin = net(&module, "port.VIN");
    let en = net(&module, "port.EN");
    assert_eq!(vin, vec!["C_IN.1".to_owned(), "U.IN".to_owned()]);
    assert_eq!(en, vec!["U.EN".to_owned()]);
    assert!(vin.iter().all(|member| !en.contains(member)));
    // Both suggest VSYS — that is a hint for a future composition, not wiring.
    let catalog = catalog_module(&plan, "block.sy8089_buck_3v3");
    let hints: Vec<&str> = catalog["ports"]
        .as_array()
        .expect("ports")
        .iter()
        .filter(|port| port["defaultNet"] == "VSYS")
        .map(|port| port["name"].as_str().expect("name"))
        .collect();
    assert!(hints.contains(&"VIN") && hints.contains(&"EN"));
}

#[test]
fn wildcard_pins_survive_unexpanded_and_mark_the_module() {
    let plan = repository_plan();
    let ams = module_of(&plan, "block.ams1117_ldo_3v3");
    assert!(net(&ams, "port.3V3").contains(&"U.VOUT*".to_owned()));
    let ch340 = module_of(&plan, "block.ch340c_usb_serial");
    let gnd = net(&ch340, "port.GND");
    assert!(gnd.contains(&"J_USB.GND*".to_owned()));
    assert!(gnd.contains(&"J_USB.EP*".to_owned()));
    assert!(net(&ch340, "port.VBUS_5V").contains(&"J_USB.VBUS*".to_owned()));

    let ams_catalog = catalog_module(&plan, "block.ams1117_ldo_3v3");
    assert_eq!(ams_catalog["unresolvedWildcards"], json!(["U.VOUT*"]));
    assert_eq!(ams_catalog["notForDrawCompile"], true);
    let ch340_catalog = catalog_module(&plan, "block.ch340c_usb_serial");
    assert_eq!(
        ch340_catalog["unresolvedWildcards"],
        json!([
            "D_ESD.I/O1*",
            "D_ESD.I/O2*",
            "J_USB.EP*",
            "J_USB.GND*",
            "J_USB.VBUS*",
        ])
    );
    // No pin number was invented: every wildcard member keeps its `*`.
    let text = serde_json::to_string(&ch340).expect("circuit serializes");
    assert!(text.contains("I/O1*"));
    assert!(!text.contains("\"I/O1.1\""));
}

#[test]
fn symbol_refs_are_placeholders_never_device_uuids() {
    let plan = repository_plan();
    let standard: Value = serde_json::from_str(
        &fs::read_to_string(repository_root().join("contracts/module-import/standard-parts.json"))
            .expect("standard parts are readable"),
    )
    .expect("standard parts are JSON");
    let device_uuids: BTreeSet<&str> = standard["parts"]
        .as_object()
        .expect("parts")
        .values()
        .filter_map(|part| part["deviceUuid"].as_str())
        .collect();
    for module in &plan.modules {
        for part in module.circuit["parts"].as_array().expect("parts") {
            let symbol = part["symbolRef"].as_str().expect("symbolRef is a string");
            assert!(
                symbol.starts_with("GENERIC-"),
                "{symbol} is the documented placeholder"
            );
            assert!(
                !device_uuids.contains(symbol),
                "{symbol} is not a device UUID"
            );
        }
        let catalog = catalog_module(&plan, &module.id);
        for part in catalog["parts"].as_array().expect("catalog parts") {
            assert_eq!(part["symbolRef"], "", "the sidecar claims no symbol");
        }
    }
}

#[test]
fn block_attribution_is_structured_and_topology_has_none() {
    let plan = repository_plan();
    for id in [
        "block.ams1117_ldo_3v3",
        "block.sy8089_buck_3v3",
        "block.ch340c_usb_serial",
    ] {
        let catalog = catalog_module(&plan, id);
        let attribution = &catalog["attribution"];
        assert!(
            attribution["author"]
                .as_str()
                .is_some_and(|a| !a.is_empty()),
            "{id} keeps its author"
        );
        assert!(attribution["contributors"].is_array(), "{id} contributors");
    }
    let ch340 = catalog_module(&plan, "block.ch340c_usb_serial");
    assert_eq!(ch340["attribution"]["contributors"], json!(["Codex"]));
    let ams = catalog_module(&plan, "block.ams1117_ldo_3v3");
    assert_eq!(ams["attribution"]["contributors"], json!([]));
    // A shape with no author field does not get one invented.
    let topology = catalog_module(&plan, "lib.sy8089_buck_3v3_live");
    assert!(topology.get("attribution").is_none());
}

#[test]
fn the_published_licence_is_the_curated_copy() {
    let plan = repository_plan();
    let licence = output_file(&plan, "upstream/LICENSE");
    let curated = repository_root().join("contracts/module-import/LICENSE");
    let copied = fs::read_to_string(&curated).expect("the curated licence is readable");
    assert_eq!(licence.bytes, copied);
    let manifest = manifest_of(&plan);
    let inputs: Vec<&str> = manifest["inputs"]
        .as_array()
        .expect("inputs")
        .iter()
        .map(|entry| entry["path"].as_str().expect("path"))
        .collect();
    for expected in [
        "contracts/module-import/LICENSE",
        "contracts/module-import/source-manifest.json",
    ] {
        assert!(inputs.contains(&expected), "{expected} is an input");
    }
    let digest = file_sha256(&curated).expect("the curated licence hashes");
    assert!(
        manifest["outputs"]
            .as_array()
            .expect("outputs")
            .iter()
            .any(|entry| entry["path"] == "upstream/LICENSE"
                && entry["sha256"].as_str() == Some(digest.as_str()))
    );
}

#[test]
fn layout_prose_and_coordinates_do_not_reach_the_output() {
    let plan = repository_plan();
    for module in &plan.modules {
        let mut keys = BTreeSet::new();
        collect_keys(&module.circuit, &mut keys);
        for banned in BANNED_KEYS {
            assert!(!keys.contains(banned), "{} carries {banned}", module.id);
        }
    }
    let catalog = catalog_of(&plan);
    let mut keys = BTreeSet::new();
    collect_keys(&catalog, &mut keys);
    for banned in BANNED_KEYS {
        assert!(!keys.contains(banned), "catalog carries {banned}");
    }
}

#[test]
fn the_manifest_digests_every_input_and_output_but_not_itself() {
    let plan = repository_plan();
    let manifest = manifest_of(&plan);
    assert_eq!(manifest["schema"], "boardwise.module-import-manifest/1");
    assert_eq!(
        manifest["upstream"]["commit"],
        "69af00c0db3960757bff36a68edb286adcd64458"
    );
    let inputs = manifest["inputs"].as_array().expect("inputs");
    assert_eq!(inputs.len(), 8);
    for input in inputs {
        assert!(
            input["path"]
                .as_str()
                .is_some_and(|path| path.starts_with("contracts/module-import/"))
        );
        assert_eq!(input["sha256"].as_str().expect("sha").len(), 64);
    }
    let outputs = manifest["outputs"].as_array().expect("outputs");
    assert_eq!(outputs.len(), 6);
    assert!(
        outputs
            .iter()
            .all(|output| output["path"] != "manifest.json")
    );
    for file in &plan.files {
        if file.path == "manifest.json" {
            continue;
        }
        assert!(
            outputs
                .iter()
                .any(|output| output["path"] == file.path.as_str())
        );
    }
}

#[test]
fn planning_twice_produces_the_same_bytes() {
    let first = repository_plan();
    let second = repository_plan();
    assert_eq!(first.files, second.files);
}

#[test]
fn identical_outputs_are_written_twice_and_differences_are_refused() {
    let plan = repository_plan();
    let directory = scratch("idempotent");
    let written = module_import::write_outputs(&directory, &plan.files).expect("first write");
    assert_eq!(written.len(), plan.files.len());
    module_import::write_outputs(&directory, &plan.files).expect("second write is idempotent");
    let target = directory.join("catalog.json");
    let original = fs::read_to_string(&target).expect("catalog is readable");
    fs::write(&target, "{\"tampered\":true}\n").expect("catalog is writable");
    let error = module_import::write_outputs(&directory, &plan.files)
        .expect_err("a differing file is never overwritten");
    assert!(error.to_string().contains("never overwrites"), "{error}");
    assert_eq!(
        fs::read_to_string(&target).expect("catalog is readable"),
        "{\"tampered\":true}\n"
    );
    fs::write(&target, original).expect("catalog is restored");
    module_import::write_outputs(&directory, &plan.files).expect("restored file is accepted again");
}

// ------------------------------------------------------------------ path safety

#[test]
fn write_outputs_refuses_an_escaping_path() {
    let directory = scratch("escape-write");
    let outside = directory.join("escaped.json");
    for path in [
        "../escaped.json",
        "sub/../../escaped.json",
        "./escaped.json",
    ] {
        let error = module_import::write_outputs(
            &directory,
            &[module_import::OutputFile {
                path: path.to_owned(),
                bytes: "x\n".to_owned(),
            }],
        )
        .expect_err("an escaping or non-normal path is refused");
        assert!(error.to_string().contains("refused"), "{path}: {error}");
    }
    let absolute = std::env::temp_dir().join("module-import-escape.json");
    let error = module_import::write_outputs(
        &directory,
        &[module_import::OutputFile {
            path: absolute.to_string_lossy().into_owned(),
            bytes: "x\n".to_owned(),
        }],
    )
    .expect_err("an absolute output path is refused");
    assert!(error.to_string().contains("refused"), "{error}");
    assert!(
        !outside.exists(),
        "nothing was written outside the directory"
    );
    assert!(
        !absolute.exists(),
        "nothing was written to the absolute path"
    );
}

// --------------------------------------------------------- synthetic refusals

fn standard_parts() -> Value {
    json!({
        "libraryUuid": "library-demo",
        "parts": {
            "ldo.demo": {
                "value": "DEMO-3V3",
                "mpn": "DEMO-3V3",
                "lcsc": "C1",
                "manufacturer": "DEMO",
                "deviceUuid": "device-demo-uuid",
                "footprint": "SOT-23-3",
                "basic": false
            }
        }
    })
}

const DEMO_LICENSE: &str = "MIT License\n\nA fixture licence, not a real one.\n";

fn demo_block(nets: Value, ports: Value, parts: Value) -> Value {
    json!({
        "id": "block.demo",
        "category": "power",
        "author": "@demo",
        "contributors": ["Fixture"],
        "parts": parts,
        "internal_nets": nets,
        "ports": ports,
    })
}

fn one_part() -> Value {
    json!({"U": {"part": "ldo.demo", "qty": 1}})
}

fn demo_curation(kind: &str, id: &str, source: &str, ports: Value) -> Value {
    json!({
        "schema": "boardwise.module-import-curation/1",
        "upstream": {"repo": "https://example.invalid/demo", "commit": "demo-commit"},
        "license": "LICENSE",
        "sourceManifest": "source-manifest.json",
        "standardParts": "parts/standard-parts.json",
        "assets": [{
            "id": id,
            "kind": kind,
            "output": "circuits/demo.circuit.json",
            "ports": ports,
            "source": source,
            "sourcePath": "modules/demo.upstream.json",
            "sourceSha256": "0".repeat(64),
            "upstreamMaturity": "unstated",
        }],
    })
}

/// A project root with one asset: source, standard parts, the licence copy and
/// the provenance ledger the curation is checked against.
fn project(
    name: &str,
    kind: &str,
    id: &str,
    source_rel: &str,
    source: &Value,
    ports: Value,
) -> PathBuf {
    let root = scratch(name);
    write_json(&root.join(source_rel), source);
    write_json(&root.join("parts/standard-parts.json"), &standard_parts());
    fs::write(root.join("LICENSE"), DEMO_LICENSE).expect("licence is writable");
    write_json(
        &root.join("source-manifest.json"),
        &json!({
            "schema": "boardwise.module-import-source-manifest/1",
            "upstream": {"repo": "https://example.invalid/demo", "commit": "demo-commit"},
            "files": [
                {
                    "upstreamPath": "modules/demo.upstream.json",
                    "originalSha256": "0".repeat(64),
                    "redactedPath": source_rel,
                    "redactedSha256": module_import::file_sha256(&root.join(source_rel))
                        .expect("source hashes"),
                },
                {
                    "upstreamPath": "LICENSE",
                    "originalSha256": module_import::file_sha256(&root.join("LICENSE"))
                        .expect("licence hashes"),
                    "redactedPath": "LICENSE",
                    "redactedSha256": module_import::file_sha256(&root.join("LICENSE"))
                        .expect("licence hashes"),
                },
            ],
        }),
    );
    write_json(
        &root.join("curation.json"),
        &demo_curation(kind, id, source_rel, ports),
    );
    root
}

fn plan_block(name: &str, block: Value, ports: Value) -> Result<module_import::ImportPlan, String> {
    let root = project(
        name,
        "block_template",
        "block.demo",
        "blocks/demo.json",
        &block,
        ports,
    );
    module_import::plan(&root, &root.join("curation.json")).map_err(|error| error.to_string())
}

fn demo_ports() -> Value {
    json!({"VIN": {"class": "power", "direction": "source"}})
}

#[test]
fn a_quantity_other_than_one_is_refused() {
    let block = demo_block(
        json!([["U.IN", "PORT:VIN"]]),
        json!({"VIN": {"dir": "in", "at": "U.IN"}}),
        json!({"U": {"part": "ldo.demo", "qty": 2}}),
    );
    let error = plan_block("quantity", block, demo_ports()).expect_err("qty 2 is refused");
    assert!(error.contains("qty is 2"), "{error}");
}

#[test]
fn a_role_the_module_does_not_declare_is_refused() {
    let block = demo_block(
        json!([["U.IN", "Z.1", "PORT:VIN"]]),
        json!({"VIN": {"dir": "in", "at": "U.IN"}}),
        one_part(),
    );
    let error = plan_block("unknown-role", block, demo_ports()).expect_err("unknown role");
    assert!(error.contains("Z.1"), "{error}");
    assert!(error.contains("does not declare"), "{error}");
}

#[test]
fn a_port_the_source_does_not_declare_is_refused() {
    let block = demo_block(
        json!([["U.IN", "PORT:NOPE"]]),
        json!({"VIN": {"dir": "in", "at": "U.IN"}}),
        one_part(),
    );
    let error = plan_block("undeclared-port", block, demo_ports()).expect_err("PORT:NOPE");
    assert!(error.contains("PORT:NOPE"), "{error}");
}

#[test]
fn a_port_outside_its_own_net_is_refused() {
    let block = demo_block(
        json!([["U.GND", "PORT:VIN"]]),
        json!({"VIN": {"dir": "in", "at": "U.IN"}}),
        one_part(),
    );
    let error = plan_block("port-outside", block, demo_ports()).expect_err("at is not a member");
    assert!(error.contains("not a member of its own net"), "{error}");
}

#[test]
fn a_port_without_a_curated_ruling_is_refused() {
    let block = demo_block(
        json!([["U.IN", "PORT:VIN"]]),
        json!({"VIN": {"dir": "in", "at": "U.IN"}}),
        one_part(),
    );
    let error = plan_block("unruled", block, json!({})).expect_err("no ruling");
    assert!(error.contains("no curated direction/class"), "{error}");
}

#[test]
fn a_port_ruled_without_a_class_is_refused() {
    let block = demo_block(
        json!([["U.IN", "PORT:VIN"]]),
        json!({"VIN": {"dir": "in", "at": "U.IN"}}),
        one_part(),
    );
    let rulings = json!({"VIN": {"class": "", "direction": "source"}});
    let error = plan_block("unruled-class", block, rulings).expect_err("no class");
    assert!(error.contains("no ruled net class"), "{error}");
}

#[test]
fn a_net_with_no_members_is_refused() {
    let block = demo_block(
        json!([["U.IN", "PORT:VIN"], ["PORT:VIN"]]),
        json!({"VIN": {"dir": "in", "at": "U.IN"}}),
        one_part(),
    );
    let error = plan_block("empty-net", block, demo_ports()).expect_err("empty net");
    assert!(error.contains("no pin members"), "{error}");
}

#[test]
fn a_pin_on_two_nets_is_refused() {
    let block = demo_block(
        json!([["U.IN", "PORT:VIN"], ["U.IN"]]),
        json!({"VIN": {"dir": "in", "at": "U.IN"}}),
        one_part(),
    );
    let error = plan_block("two-nets", block, demo_ports()).expect_err("one pin, two nodes");
    assert!(error.contains("two nets"), "{error}");
}

#[test]
fn a_source_path_that_escapes_the_root_is_refused() {
    let block = demo_block(
        json!([["U.IN", "PORT:VIN"]]),
        json!({"VIN": {"dir": "in", "at": "U.IN"}}),
        one_part(),
    );
    let root = project(
        "escape-source",
        "block_template",
        "block.demo",
        "blocks/demo.json",
        &block,
        demo_ports(),
    );
    let mut curation: Value =
        serde_json::from_str(&fs::read_to_string(root.join("curation.json")).expect("readable"))
            .expect("curation is JSON");
    curation["assets"][0]["source"] = json!("../outside.json");
    write_json(&root.join("curation.json"), &curation);
    let error = module_import::plan(&root, &root.join("curation.json"))
        .expect_err("a `..` input path is refused");
    assert!(error.to_string().contains("refused"), "{error}");

    for key in ["sourceManifest", "standardParts"] {
        let mut curation: Value = serde_json::from_str(
            &fs::read_to_string(root.join("curation.json")).expect("readable"),
        )
        .expect("curation is JSON");
        curation[key] = json!("../outside.json");
        write_json(&root.join("curation.json"), &curation);
        let outcome = module_import::plan(&root, &root.join("curation.json"));
        let error = match outcome {
            Ok(_) => panic!("{key} escape must be refused"),
            Err(error) => error,
        };
        assert!(error.to_string().contains("refused"), "{key}: {error}");
    }
}

#[test]
fn a_licence_path_that_escapes_the_root_is_refused() {
    let block = demo_block(
        json!([["U.IN", "PORT:VIN"]]),
        json!({"VIN": {"dir": "in", "at": "U.IN"}}),
        one_part(),
    );
    let root = project(
        "escape-licence",
        "block_template",
        "block.demo",
        "blocks/demo.json",
        &block,
        demo_ports(),
    );
    let mut curation: Value =
        serde_json::from_str(&fs::read_to_string(root.join("curation.json")).expect("readable"))
            .expect("curation is JSON");
    curation["license"] = json!("../LICENSE");
    write_json(&root.join("curation.json"), &curation);
    let error = module_import::plan(&root, &root.join("curation.json"))
        .expect_err("an escaping licence path is refused");
    assert!(error.to_string().contains("refused"), "{error}");
}

#[test]
fn an_output_path_that_escapes_the_output_directory_is_refused() {
    let block = demo_block(
        json!([["U.IN", "PORT:VIN"]]),
        json!({"VIN": {"dir": "in", "at": "U.IN"}}),
        one_part(),
    );
    let root = project(
        "escape-output",
        "block_template",
        "block.demo",
        "blocks/demo.json",
        &block,
        demo_ports(),
    );
    let mut curation: Value =
        serde_json::from_str(&fs::read_to_string(root.join("curation.json")).expect("readable"))
            .expect("curation is JSON");
    curation["assets"][0]["output"] = json!("../escape.circuit.json");
    write_json(&root.join("curation.json"), &curation);
    let error = module_import::plan(&root, &root.join("curation.json"))
        .expect_err("an escaping output path is refused");
    assert!(error.to_string().contains("refused"), "{error}");
}

#[test]
fn the_ledger_and_the_curation_must_agree() {
    let block = demo_block(
        json!([["U.IN", "PORT:VIN"]]),
        json!({"VIN": {"dir": "in", "at": "U.IN"}}),
        one_part(),
    );
    let root = project(
        "ledger-mismatch",
        "block_template",
        "block.demo",
        "blocks/demo.json",
        &block,
        demo_ports(),
    );
    let mut curation: Value =
        serde_json::from_str(&fs::read_to_string(root.join("curation.json")).expect("readable"))
            .expect("curation is JSON");
    curation["assets"][0]["sourceSha256"] = json!("f".repeat(64));
    write_json(&root.join("curation.json"), &curation);
    let error = module_import::plan(&root, &root.join("curation.json"))
        .expect_err("a digest disagreement is refused");
    assert!(error.to_string().contains("sourceSha256"), "{error}");

    let mut curation: Value =
        serde_json::from_str(&fs::read_to_string(root.join("curation.json")).expect("readable"))
            .expect("curation is JSON");
    curation["upstream"]["commit"] = json!("another-commit");
    write_json(&root.join("curation.json"), &curation);
    let error = module_import::plan(&root, &root.join("curation.json"))
        .expect_err("a different upstream is refused");
    assert!(error.to_string().contains("another-commit"), "{error}");
}

#[test]
fn duplicate_output_paths_are_refused_before_anything_is_written() {
    let directory = scratch("duplicate-paths");
    let twice = [
        module_import::OutputFile {
            path: "circuits/x.circuit.json".to_owned(),
            bytes: "x\n".to_owned(),
        },
        module_import::OutputFile {
            path: "circuits/x.circuit.json".to_owned(),
            bytes: "x\n".to_owned(),
        },
    ];
    let error = module_import::write_outputs(&directory, &twice)
        .expect_err("a repeated path is a contradiction, not an overwrite");
    assert!(error.to_string().contains("planned twice"), "{error}");
    assert!(
        !directory.join("circuits/x.circuit.json").exists(),
        "nothing was written"
    );
    // The same path spelled with a redundant separator is still the same file.
    let spelled = [
        module_import::OutputFile {
            path: "circuits/x.circuit.json".to_owned(),
            bytes: "a\n".to_owned(),
        },
        module_import::OutputFile {
            path: "circuits//x.circuit.json".to_owned(),
            bytes: "b\n".to_owned(),
        },
    ];
    let error = module_import::write_outputs(&directory, &spelled)
        .expect_err("the same path in another spelling is still a duplicate");
    assert!(error.to_string().contains("planned twice"), "{error}");
    assert!(!directory.join("circuits/x.circuit.json").exists());
}

#[test]
fn an_asset_may_not_claim_a_reserved_output_path() {
    let block = demo_block(
        json!([["U.IN", "PORT:VIN"]]),
        json!({"VIN": {"dir": "in", "at": "U.IN"}}),
        one_part(),
    );
    let root = project(
        "reserved-output",
        "block_template",
        "block.demo",
        "blocks/demo.json",
        &block,
        demo_ports(),
    );
    for reserved in ["catalog.json", "manifest.json", "upstream/LICENSE"] {
        let mut curation: Value = serde_json::from_str(
            &fs::read_to_string(root.join("curation.json")).expect("readable"),
        )
        .expect("curation is JSON");
        curation["assets"][0]["output"] = json!(reserved);
        write_json(&root.join("curation.json"), &curation);
        let error = module_import::plan(&root, &root.join("curation.json"))
            .expect_err("an asset may not claim an importer-owned path");
        assert!(
            error.to_string().contains("writes itself"),
            "{reserved}: {error}"
        );
    }
}

// ---------------------------------------------------------- role topologies

fn demo_topology(pins: Value, nets: Value) -> Value {
    json!({
        "schemaVersion": 1,
        "kind": "role_topology_module",
        "module": {
            "id": "lib.demo",
            "title": "demo topology",
            "maturity": "topology_ready",
            "parts": [{
                "role": "REG",
                "lcsc": "C1",
                "device": {"libraryUuid": "lib", "deviceUuid": "dev", "name": "DEMO-NAME"},
                "footprint": "SOT",
                "pins": pins,
            }],
            "nets": nets,
            "verification": {
                "pinNetReadback": "passed",
                "deviceIdentityResolution": "passed",
                "geometry": "not_captured",
                "pcb": "not_tested",
                "bringup": "not_tested",
            },
        },
    })
}

fn topology_pins() -> Value {
    json!([
        {"number": "1", "name": "IN", "net": "port.IN"},
        {"number": "2", "name": "GND", "net": "port.GND"},
        {"number": "3", "name": "NC1", "net": "", "connectionState": "unconnected"},
        {"number": "4", "name": "UNSTATED"},
    ])
}

fn topology_nets() -> Value {
    json!([
        {"id": "port.IN", "members": ["REG.1"], "port": "IN"},
        {"id": "port.GND", "members": ["REG.2"], "port": "GND"},
    ])
}

fn topology_ports() -> Value {
    json!({
        "IN": {"class": "power", "direction": "source"},
        "GND": {"class": "gnd", "direction": ""},
    })
}

fn plan_topology(name: &str, source: Value) -> Result<module_import::ImportPlan, String> {
    plan_topology_with(name, source, topology_ports())
}

fn plan_topology_with(
    name: &str,
    source: Value,
    ports: Value,
) -> Result<module_import::ImportPlan, String> {
    let root = project(
        name,
        "role_topology",
        "lib.demo",
        "topologies/demo.json",
        &source,
        ports,
    );
    module_import::plan(&root, &root.join("curation.json")).map_err(|error| error.to_string())
}

#[test]
fn an_explicit_nc_and_an_unstated_pin_are_different() {
    let plan = plan_topology(
        "topology-nc",
        demo_topology(topology_pins(), topology_nets()),
    )
    .expect("the demo topology normalises");
    let module = module_of(&plan, "lib.demo");
    assert_eq!(
        module["nc"],
        json!([{"pin": "REG.3", "provenance": "ai_asserted"}])
    );
    let catalog = catalog_module(&plan, "lib.demo");
    assert_eq!(catalog["unstatedPins"], json!(["REG.4"]));
    assert_eq!(catalog["unresolvedWildcards"], json!([]));
    assert_eq!(module["parts"][0]["mpn"], "", "device.name is not an MPN");
    assert_eq!(module["parts"][0]["value"], "", "no value was stated");
    assert_eq!(module["parts"][0]["symbolRef"], "GENERIC-REG");
    assert_eq!(catalog["parts"][0]["deviceName"], "DEMO-NAME");
}

#[test]
fn pins_and_net_members_must_agree_in_both_directions() {
    // A member the pin does not claim.
    let extra = demo_topology(
        topology_pins(),
        json!([
            {"id": "port.IN", "members": ["REG.1", "REG.2"], "port": "IN"},
            {"id": "port.GND", "members": ["REG.2"], "port": "GND"},
        ]),
    );
    let error = plan_topology("topology-extra", extra).expect_err("extra member is refused");
    assert!(error.contains("must agree"), "{error}");

    // A pin that claims a net which does not list it.
    let missing = demo_topology(
        json!([
            {"number": "1", "name": "IN", "net": "port.IN"},
            {"number": "2", "name": "GND", "net": "port.GND"},
        ]),
        json!([{"id": "port.IN", "members": ["REG.1"], "port": "IN"}]),
    );
    let error = plan_topology("topology-missing", missing).expect_err("missing net is refused");
    assert!(error.contains("does not declare"), "{error}");

    // A pin whose net is not the net it is listed under.
    let moved = demo_topology(
        json!([
            {"number": "1", "name": "IN", "net": "port.GND"},
            {"number": "2", "name": "GND", "net": "port.GND"},
        ]),
        json!([
            {"id": "port.IN", "members": ["REG.1"], "port": "IN"},
            {"id": "port.GND", "members": ["REG.2"], "port": "GND"},
        ]),
    );
    let error = plan_topology("topology-moved", moved).expect_err("contradiction is refused");
    assert!(error.contains("must agree"), "{error}");
}

#[test]
fn an_unconnected_pin_that_is_a_net_member_is_refused() {
    let source = demo_topology(
        json!([
            {"number": "1", "name": "IN", "net": "port.IN", "connectionState": "unconnected"},
        ]),
        json!([{"id": "port.IN", "members": ["REG.1"], "port": "IN"}]),
    );
    let error = plan_topology("topology-nc-member", source).expect_err("NC cannot contradict");
    assert!(error.contains("cannot contradict the wiring"), "{error}");
}

#[test]
fn a_port_net_without_its_port_field_is_refused() {
    let source = demo_topology(
        topology_pins(),
        json!([
            {"id": "port.IN", "members": ["REG.1"]},
            {"id": "port.GND", "members": ["REG.2"], "port": "GND"},
        ]),
    );
    let error = plan_topology("topology-no-port-field", source).expect_err("port.* needs a port");
    assert!(error.contains("declares no port"), "{error}");
}

#[test]
fn a_topology_port_part_must_be_a_declared_role() {
    let source = demo_topology(topology_pins(), topology_nets());
    let unknown = json!({
        "IN": {"class": "power", "direction": "source", "part": "NOPE"},
        "GND": {"class": "gnd", "direction": ""},
    });
    let error = plan_topology_with("topology-part-unknown", source.clone(), unknown)
        .expect_err("a port naming a role the module does not have is refused");
    assert!(error.contains("is not a role of this module"), "{error}");

    // A declared role is kept as the interface's part, the same as a Block port.
    let declared = json!({
        "IN": {"class": "power", "direction": "source", "part": "REG"},
        "GND": {"class": "gnd", "direction": ""},
    });
    let plan = plan_topology_with("topology-part-reg", source, declared)
        .expect("a declared role is accepted");
    let module = module_of(&plan, "lib.demo");
    assert_eq!(interface(&module, "port.IN")["part"], "REG");
    assert!(interface(&module, "port.GND").get("part").is_none());
}
