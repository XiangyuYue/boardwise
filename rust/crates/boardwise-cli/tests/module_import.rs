//! CLI surface for `module-import` (038Q2).
//!
//! The process contract: `--output` is required (usage text, exit 2), an
//! unreadable input is the shared `boardwise.cli-result/1` envelope on stderr
//! (exit 2), and a successful run prints the candidate report on stdout and
//! exits 0. Re-running into the same directory is allowed; a directory holding
//! a differing file is refused and left untouched, and the run publishes the
//! upstream licence next to the modules.
//!
//! Scratch paths are a fresh directory per call (`process id` + an atomic
//! counter); nothing is deleted, so a repeated `cargo test` never has to clean
//! anything up.

use serde_json::Value;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, Output};
use std::sync::atomic::{AtomicUsize, Ordering};

fn run(arguments: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_boardwise-cli"))
        .args(arguments)
        .output()
        .expect("the CLI process runs")
}

fn repository_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .ancestors()
        .nth(3)
        .expect("repository root")
        .to_path_buf()
}

fn scratch(name: &str) -> PathBuf {
    static NEXT: AtomicUsize = AtomicUsize::new(0);
    let serial = NEXT.fetch_add(1, Ordering::Relaxed);
    let directory = Path::new(env!("CARGO_TARGET_TMPDIR"))
        .join("module-import-cli")
        .join(format!("{}-{serial}-{name}", std::process::id()));
    fs::create_dir_all(&directory).expect("scratch directory is writable");
    directory
}

fn stdout(output: &Output) -> Value {
    serde_json::from_slice(&output.stdout).expect("stdout is one JSON object")
}

fn stderr(output: &Output) -> Value {
    serde_json::from_slice(&output.stderr).expect("stderr is one JSON object")
}

#[test]
fn a_run_writes_four_candidates_and_reports_them() {
    let directory = scratch("write");
    let output = run(&[
        "module-import",
        "--output",
        directory.to_str().expect("utf-8 path"),
    ]);
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert!(
        output.stderr.is_empty(),
        "a successful run says nothing on stderr"
    );
    let report = stdout(&output);
    assert_eq!(report["schema"], "boardwise.module-import-report/1");
    assert_eq!(report["modules"], 4);
    assert_eq!(report["candidate"], true);
    assert_eq!(report["maturity"], "candidate");
    assert_eq!(
        report["moduleIds"],
        serde_json::json!([
            "block.ams1117_ldo_3v3",
            "block.ch340c_usb_serial",
            "block.sy8089_buck_3v3",
            "lib.sy8089_buck_3v3_live",
        ])
    );
    for relative in [
        "catalog.json",
        "manifest.json",
        "upstream/LICENSE",
        "circuits/ams1117_ldo_3v3.circuit.json",
        "circuits/ch340c_usb_serial.circuit.json",
        "circuits/sy8089_buck_3v3.circuit.json",
        "circuits/sy8089_buck_3v3_live.circuit.json",
    ] {
        assert!(directory.join(relative).is_file(), "{relative} was written");
    }
    // The licence is byte-identical to the curated copy of the upstream one.
    assert_eq!(
        fs::read(directory.join("upstream/LICENSE")).expect("licence is readable"),
        fs::read(repository_root().join("contracts/module-import/LICENSE"))
            .expect("curated licence is readable"),
        "the published licence is the upstream one, byte for byte"
    );
    let catalog: Value = serde_json::from_str(
        &fs::read_to_string(directory.join("catalog.json")).expect("readable"),
    )
    .expect("catalog is JSON");
    assert_eq!(catalog["schema"], "boardwise.module-catalog/1");
    assert_eq!(catalog["modules"].as_array().expect("modules").len(), 4);
    let manifest: Value = serde_json::from_str(
        &fs::read_to_string(directory.join("manifest.json")).expect("readable"),
    )
    .expect("manifest is JSON");
    assert!(
        manifest["outputs"]
            .as_array()
            .expect("outputs")
            .iter()
            .any(|entry| entry["path"] == "upstream/LICENSE")
    );
    assert!(
        !manifest["outputs"]
            .as_array()
            .expect("outputs")
            .iter()
            .any(|entry| entry["path"] == "manifest.json")
    );
}

#[test]
fn a_second_run_into_the_same_directory_is_idempotent() {
    let directory = scratch("idempotent");
    let path = directory.to_str().expect("utf-8 path");
    assert!(run(&["module-import", "--output", path]).status.success());
    let before = fs::read(directory.join("catalog.json")).expect("catalog is readable");
    let second = run(&["module-import", "--output", path]);
    assert!(
        second.status.success(),
        "{}",
        String::from_utf8_lossy(&second.stderr)
    );
    assert_eq!(
        fs::read(directory.join("catalog.json")).expect("catalog is readable"),
        before
    );
}

#[test]
fn a_differing_file_is_refused_and_left_untouched() {
    let directory = scratch("refuse");
    let path = directory.to_str().expect("utf-8 path");
    assert!(run(&["module-import", "--output", path]).status.success());
    let target = directory.join("circuits/ams1117_ldo_3v3.circuit.json");
    fs::write(&target, "{\"kind\":\"something else\"}\n").expect("fixture is writable");
    let refused = run(&["module-import", "--output", path]);
    assert_eq!(refused.status.code(), Some(2));
    assert!(
        refused.stdout.is_empty(),
        "a refusal writes nothing to stdout"
    );
    let envelope = stderr(&refused);
    assert_eq!(envelope["schema"], "boardwise.cli-result/1");
    assert_eq!(envelope["command"], "module-import");
    assert_eq!(envelope["error"]["code"], "BAD_REQUEST");
    assert!(
        envelope["error"]["message"]
            .as_str()
            .expect("message")
            .contains("never overwrites")
    );
    assert_eq!(
        fs::read_to_string(&target).expect("readable"),
        "{\"kind\":\"something else\"}\n",
        "the differing file keeps its bytes"
    );
}

#[test]
fn output_is_required_and_a_usage_error() {
    let output = run(&["module-import"]);
    assert_eq!(output.status.code(), Some(2));
    assert!(output.stdout.is_empty());
    let text = String::from_utf8_lossy(&output.stderr);
    assert!(
        text.starts_with("usage: boardwise-cli module-import"),
        "{text}"
    );
    assert!(text.contains("--output DIR is required"), "{text}");
    assert!(
        !text.contains("boardwise.cli-result/1"),
        "usage stays plain text"
    );
}

#[test]
fn an_unknown_flag_is_a_usage_error() {
    let directory = scratch("unknown-flag");
    let output = run(&[
        "module-import",
        "--output",
        directory.to_str().expect("utf-8 path"),
        "--force",
    ]);
    assert_eq!(output.status.code(), Some(2));
    let text = String::from_utf8_lossy(&output.stderr);
    assert!(
        text.starts_with("usage: boardwise-cli module-import"),
        "{text}"
    );
    assert!(text.contains("--force"), "{text}");
}

#[test]
fn help_prints_usage_on_stdout() {
    let output = run(&["module-import", "--help"]);
    assert!(output.status.success());
    assert!(output.stderr.is_empty());
    let text = String::from_utf8_lossy(&output.stdout);
    assert!(
        text.contains("usage: boardwise-cli module-import"),
        "{text}"
    );
    assert!(text.contains("notForDrawCompile"), "{text}");
}

#[test]
fn an_unreadable_curation_is_the_domain_envelope() {
    let directory = scratch("missing-curation");
    let missing = directory.join("does-not-exist.json");
    let output = run(&[
        "module-import",
        "--curation",
        missing.to_str().expect("utf-8 path"),
        "--output",
        directory.join("out").to_str().expect("utf-8 path"),
    ]);
    assert_eq!(output.status.code(), Some(2));
    assert!(output.stdout.is_empty());
    let envelope = stderr(&output);
    assert_eq!(envelope["schema"], "boardwise.cli-result/1");
    assert_eq!(envelope["command"], "module-import");
    assert_eq!(envelope["error"]["code"], "BAD_REQUEST");
    assert!(
        !directory.join("out").exists(),
        "a refused run creates no output directory"
    );
}

#[test]
fn the_default_curation_is_the_repository_one() {
    // No `--root`/`--curation`: both default to this checkout, never the cwd,
    // and the run still finds the pinned inputs.
    let directory = scratch("defaults");
    let output = Command::new(env!("CARGO_BIN_EXE_boardwise-cli"))
        .args(["module-import", "--output"])
        .arg(directory.join("out"))
        .current_dir(repository_root().join("rust"))
        .output()
        .expect("the CLI process runs");
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(stdout(&output)["modules"], 4);
}
