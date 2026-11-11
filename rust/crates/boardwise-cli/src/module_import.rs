//! `module-import`: normalise the pinned upstream module samples into candidate
//! `boardwise-circuit-spec` files plus their catalog and manifest.
//!
//! The command is deliberately narrow. It reads the redacted inputs named by the
//! curation file, computes every document in memory, and only then writes. A
//! refusal writes nothing at all; an existing file with the same bytes is fine
//! (the run is idempotent) and one with different bytes is refused, never
//! overwritten — there is no `--force`.
//!
//! Usage errors keep the plain-text surface (`--output` is required, unknown
//! flags are usage); a refusal from the normaliser is the shared
//! `boardwise.cli-result/1` envelope on stderr with exit 2.

use boardwise_core::module_import;
use std::path::{Path, PathBuf};

use crate::{Failure, Output, Run, flag_value, repository_root};

const USAGE: &str =
    "usage: boardwise-cli module-import [--curation PATH] [--root DIR] --output DIR";

const HELP: &str = "\
usage: boardwise-cli module-import [--curation PATH] [--root DIR] --output DIR

Normalise the pinned upstream module samples into candidate circuit specs.
Every output is a candidate: nothing here claims compose readiness, native CBB
compatibility, PCB or hardware validation, and the catalog marks each module
notForDrawCompile because no symbol identity has been verified.

options:
  -h, --help       show this help and exit
  --curation PATH  curated port rulings (default:
                   <repository>/contracts/module-import/curation.json)
  --root DIR       input root the curation paths are relative to
                   (default: the repository)
  --output DIR     directory to write circuits/, catalog.json and manifest.json
                   into (required; created when missing)

An existing file identical to the computed one is accepted, so the command can
be re-run; a differing file is refused rather than overwritten.

Exit codes: 0 the candidates were written, 2 the request failed (usage text, or
one boardwise.cli-result/1 envelope on stderr).
";

fn usage(detail: impl std::fmt::Display) -> Failure {
    Failure::Usage(format!(
        "{USAGE}\nboardwise-cli module-import: error: {detail}\n"
    ))
}

pub(crate) fn run(rest: &mut impl Iterator<Item = String>) -> Result<Run, Failure> {
    let mut curation: Option<String> = None;
    let mut root: Option<String> = None;
    let mut output: Option<String> = None;
    while let Some(argument) = rest.next() {
        let (flag, attached) = match argument.split_once('=') {
            Some((flag, value)) => (flag, Some(value)),
            None => (argument.as_str(), None),
        };
        match flag {
            "-h" | "--help" if attached.is_none() => return Ok(Run::Help(HELP)),
            "--curation" | "--root" | "--output" => {
                let value = flag_value(rest, flag, attached)?;
                match flag {
                    "--curation" => curation = Some(value),
                    "--root" => root = Some(value),
                    _ => output = Some(value),
                }
            }
            other => return Err(usage(format!("unrecognized argument {other:?}"))),
        }
    }
    let Some(output) = output else {
        return Err(usage("--output DIR is required"));
    };
    if output.is_empty() {
        return Err(usage("--output must not be empty"));
    }
    // The repository default is the same one `differential` uses: the checkout
    // this binary was built in, never the current directory.
    let root = root.map_or_else(repository_root, PathBuf::from);
    let curation = curation.map_or_else(
        || repository_root().join("contracts/module-import/curation.json"),
        PathBuf::from,
    );
    let plan = module_import::plan(&root, &curation)?;
    module_import::write_outputs(Path::new(&output), &plan.files)?;
    Ok(Run::Report(Output {
        value: module_import::report(&plan),
        exit_code: 0,
        stderr: false,
    }))
}
