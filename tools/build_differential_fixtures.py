"""Regenerate the public/synthetic 540C differential inputs, golden and manifest.

Run from the repository root: `.venv/Scripts/python.exe -m tools.build_differential_fixtures`.

Every artifact is rendered in memory first — sanitized, checked for machine paths,
projected and hashed — and only then written, each with ``\\n`` line endings. A
projection, schema or sanitization failure therefore publishes nothing at all. The
publish step itself is a loop of single-file writes, deliberately *not* described as
a filesystem-wide transaction: a failure inside that loop can still leave the files
it already wrote, but no compute failure can reach it.

Each run produces into a **fresh** directory under :data:`WORK`. That is not
housekeeping: `checkup --out` reads ``<out>/design-intent.md`` back as the intent
records and only creates that file when it is missing, so a second run over the same
output directory would fold the first run's own TODO template into the report — the
second regeneration of the same sources produced a different ``review-report.json``
until this was fixed. The run directory name is sanitized to ``<OUT>`` below, so the
published bytes do not depend on it.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any, Mapping, Sequence

from tools.contract_validate import assert_valid, load_path
from tools.differential import SCHEMAS, project_payload
from tools.differential_compare import write_text_lf

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".tmp_540" / "differential_build"
INPUTS = ROOT / "contracts" / "differential" / "inputs"
CASES = ROOT / "contracts" / "differential" / "cases.json"
MANIFEST = ROOT / "contracts" / "differential" / "manifest.json"
FIXTURES = ROOT / "tests" / "fixtures"
DRAW = FIXTURES / "drawapply"
#: Public/synthetic specs that only the page case reads (not fixture-draw inputs).
SOURCES = ROOT / "contracts" / "differential" / "sources"

#: The per-run output directory, set by :func:`_produce` and mapped to ``<OUT>``.
RUN_ROOT: Path | None = None

INPUTS_RELATIVE = "contracts/differential/inputs"
CASES_RELATIVE = "contracts/differential/cases.json"
# One public input name per **case id**; `_render` publishes in the order
# `_produce` returns. The five producer cases are named after their kind, so their
# ids read as kinds; the two declared `.epru` samples and the two declared SYMBOL
# library samples share one kind each, which is what `CASE_KINDS` says out loud.
INPUT_NAMES = {
    "review-report-projection": "review-report.json",
    "layout-plan-geometry": "divider-cand1.layout.json",
    "compile-result-projection": "divider-compile-result.json",
    "compile-page-result-projection": "page-compile-result.json",
    "lint-result-projection": "empty-page-lint-result.json",
    "epru-stream-v3-eof": "epru-stream-v3-eof.json",
    "epru-stream-v4-eof-truncated": "epru-stream-v4-eof-truncated.json",
    "symbol-library-v3-zindex": "symbol-library-v3-zindex.json",
    "symbol-library-v4-pin-id": "symbol-library-v4-pin-id.json",
}
#: The case ids whose kind is *not* the id itself. A case book is keyed by id, so
#: two cases of one kind need two ids; the kind decides the schema and projection,
#: the id decides the input name and the row it publishes under.
CASE_KINDS = {
    "epru-stream-v3-eof": "epru-stream-sample",
    "epru-stream-v4-eof-truncated": "epru-stream-sample",
    "symbol-library-v3-zindex": "symbol-library-sample",
    "symbol-library-v4-pin-id": "symbol-library-sample",
}
#: The contract tag of a declared sample document (see `contracts/json/
#: epru-stream-sample-v1.schema.json`).
EPRU_SAMPLE_SCHEMA = "boardwise.epru-stream-sample/1"
#: Declared `.epru` sample text — synthetic record streams, not a producer's output.
SAMPLE_SOURCES = SOURCES / "epru-stream-samples.json"
#: The case ids `SAMPLE_SOURCES` must declare, exactly. Stated once so the file
#: that is checked and the file that is read cannot drift apart.
EPRU_SAMPLE_CASE_IDS = frozenset({"epru-stream-v3-eof", "epru-stream-v4-eof-truncated"})
#: The contract tag of a declared SYMBOL library sample (see `contracts/json/
#: symbol-library-sample-v1.schema.json`): a record stream *plus* the `pinKey` its
#: pins are addressed by.
SYMBOL_SAMPLE_SCHEMA = "boardwise.symbol-library-sample/1"
#: Declared SYMBOL library sample text — synthetic record streams, not a
#: producer's output, and no real project content.
SYMBOL_SAMPLE_SOURCES = SOURCES / "symbol-library-samples.json"
SYMBOL_SAMPLE_CASE_IDS = frozenset(
    {"symbol-library-v3-zindex", "symbol-library-v4-pin-id"}
)

# An absolute path that survived sanitization, whatever machine it came from: a
# Windows drive (D:/..., E:\... as it appears inside JSON) or a POSIX home/temp
# root. The markers in `_forbidden_markers` know this checkout and this user; this
# pattern is the machine-independent net under them.
RESIDUAL_ABSOLUTE_PATH = re.compile(
    r"(?<![A-Za-z0-9_])(?:[A-Za-z]:[\\/]|/(?:home|Users|root|mnt|Volumes|private|var/folders)/)"
)


def _run(argv: list[str], accepted: set[int]) -> None:
    result = subprocess.run(argv, cwd=ROOT)
    if result.returncode not in accepted:
        raise RuntimeError(f"producer exited {result.returncode}, expected {sorted(accepted)}: {argv}")


def _produce() -> dict[str, Path]:
    global RUN_ROOT
    WORK.mkdir(parents=True, exist_ok=True)
    # A fresh directory per run: `checkup --out` reads `<out>/design-intent.md` back
    # as intent records, so two runs sharing one output directory disagree.
    RUN_ROOT = Path(tempfile.mkdtemp(prefix="run-", dir=WORK))
    python = str(ROOT / ".venv" / "Scripts" / "python.exe")
    _run([
        python, "-m", "boardwise.cli", "checkup", "--file",
        "tests/fixtures/ch340_golden.epro2", "--out", str(RUN_ROOT / "checkup"),
    ], {0, 3})
    _run([
        python, "-m", "boardwise.cli", "draw", "compile",
        "--circuit", "tests/fixtures/drawapply/divider.circuit.json",
        "--presentation", "tests/fixtures/drawapply/divider.presentation.json",
        "--profiles", "tests/fixtures/drawapply/library.json",
        "--page-box", "0,-1000,1200,0",
        "--out", str(RUN_ROOT / "compile"),
        "--json", str(RUN_ROOT / "compile-result.json"),
    ], {0})
    # The fifth case is the *page* document: a presentation with several islands
    # plus a sheet box makes `draw compile` draw a page, and that result states
    # `pages` instead of `candidates` — the shape the module contract refuses.
    page_circuit = (SOURCES / "page.circuit.json").relative_to(ROOT).as_posix()
    page_presentation = (SOURCES / "page.presentation.json").relative_to(ROOT).as_posix()
    _run([
        python, "-m", "boardwise.cli", "draw", "compile",
        "--circuit", page_circuit,
        "--presentation", page_presentation,
        "--profiles", "tests/fixtures/drawapply/library.json",
        "--page-box", "0,0,1169,826",
        "--out", str(RUN_ROOT / "compile-page"),
        "--json", str(RUN_ROOT / "page-compile-result.json"),
    ], {0})
    snapshot = {
        "components": [{
            "primitiveId": "sheet1",
            "state": {
                "PrimitiveType": "Component",
                "ComponentType": "sheet",
                "PrimitiveId": "sheet1",
            },
        }],
        "wires": [],
        "pins": [],
        "netlabels": [],
        "bboxes": {"sheet1": {"minX": 0, "minY": 0, "maxX": 1170, "maxY": 825}},
        "meta": {"sheets": ["sheet1"]},
    }
    write_text_lf(
        RUN_ROOT / "lint-snapshot.json",
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
    )
    write_text_lf(RUN_ROOT / "lint-render.svg", "<svg></svg>\n")
    _run([
        python, "-m", "boardwise.cli", "draw", "lint",
        "--snapshot", str(RUN_ROOT / "lint-snapshot.json"),
        "--render", str(RUN_ROOT / "lint-render.svg"),
        "--json", str(RUN_ROOT / "lint-result.json"),
    ], {0})
    produced = {
        "review-report-projection": RUN_ROOT / "checkup" / "report.json",
        "layout-plan-geometry": RUN_ROOT / "compile" / "cand1.layout.json",
        "compile-result-projection": RUN_ROOT / "compile-result.json",
        "compile-page-result-projection": RUN_ROOT / "page-compile-result.json",
        "lint-result-projection": RUN_ROOT / "lint-result.json",
    }
    # Declared samples last: they are not produced by a command, they are written
    # out of `SAMPLE_SOURCES`, and they publish after the five producer cases.
    for case_id, path in _declared_samples().items():
        produced[case_id] = path
    # The SYMBOL library samples follow the `.epru` ones: one more declared kind,
    # published after it, so the seven earlier case rows cannot move.
    for case_id, path in _declared_symbol_samples().items():
        produced[case_id] = path
    return produced


def _declared_samples() -> dict[str, Path]:
    """Write each declared `.epru` sample into this run's fresh directory.

    A declared sample is text, so no command runs to obtain it — the manifest says
    so in its ``producers`` list, and names ``SAMPLE_SOURCES`` in ``sources`` so the
    published input can always be traced back to the declaration it came from.

    Sanitization is checked here rather than assumed: a sample whose text contains a
    backslash or a machine path would be rewritten on its way to the golden, and a
    published input that no longer says what the declaration says is not a sample.
    """
    declared = load_path(SAMPLE_SOURCES)
    entries = declared["samples"]
    if sorted(entry["caseId"] for entry in entries) != sorted(EPRU_SAMPLE_CASE_IDS):
        raise RuntimeError(
            f"{SAMPLE_SOURCES.name} declares "
            f"{sorted(entry['caseId'] for entry in entries)}, "
            f"not the case ids {sorted(EPRU_SAMPLE_CASE_IDS)}"
        )
    produced: dict[str, Path] = {}
    for entry in entries:
        payload = {
            "schema": EPRU_SAMPLE_SCHEMA,
            "name": entry["name"],
            "text": entry["text"],
        }
        if _sanitize(payload) != payload:
            raise RuntimeError(
                f"declared sample {entry['caseId']!r} does not survive sanitization; "
                "a declared sample must publish exactly the text it declares"
            )
        path = RUN_ROOT / entry["input"]
        write_text_lf(path, _dump(payload))
        produced[entry["caseId"]] = path
    return produced


def _declared_symbol_samples() -> dict[str, Path]:
    """Write each declared SYMBOL library sample into this run's fresh directory.

    Same shape as :func:`_declared_samples`, one contract further: a SYMBOL
    library sample is a record stream **plus** the `pinKey` its pins are keyed by,
    because a V3 `.epro2` addresses a PIN row by the synthesised `e<zIndex>` while
    an eprj3/`pin_id` stream addresses it by the row's own id. Both spellings are
    part of the contract, so the input states which one it means.
    """
    declared = load_path(SYMBOL_SAMPLE_SOURCES)
    entries = declared["samples"]
    if sorted(entry["caseId"] for entry in entries) != sorted(SYMBOL_SAMPLE_CASE_IDS):
        raise RuntimeError(
            f"{SYMBOL_SAMPLE_SOURCES.name} declares "
            f"{sorted(entry['caseId'] for entry in entries)}, "
            f"not the case ids {sorted(SYMBOL_SAMPLE_CASE_IDS)}"
        )
    produced: dict[str, Path] = {}
    for entry in entries:
        payload = {
            "schema": SYMBOL_SAMPLE_SCHEMA,
            "name": entry["name"],
            "text": entry["text"],
            "pinKey": entry["pinKey"],
        }
        if _sanitize(payload) != payload:
            raise RuntimeError(
                f"declared sample {entry['caseId']!r} does not survive sanitization; "
                "a declared sample must publish exactly the text it declares"
            )
        path = RUN_ROOT / entry["input"]
        write_text_lf(path, _dump(payload))
        produced[entry["caseId"]] = path
    return produced


def _clean_text(value: str) -> str:
    text = value.replace("\\", "/")
    home = str(Path.home()).replace("\\", "/")
    work = str(WORK).replace("\\", "/")
    replacements = []
    if RUN_ROOT is not None:
        # Before WORK: the run directory lives under it, so replacing WORK first
        # would leave the per-run name in the golden.
        replacements.append((str(RUN_ROOT).replace("\\", "/"), "<OUT>"))
    replacements += [
        (work, "<OUT>"),
        ("tests/fixtures/", "<FIXTURES>/"),
        (home + "/.boardwise/", "<HOME>/"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def _sanitize(value: Any, key: str = "") -> Any:
    if key == "generatedAt":
        return "<GENERATED_AT>"
    if isinstance(value, dict):
        return {name: _sanitize(item, name) for name, item in value.items()}
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, str):
        return _clean_text(value)
    return value


def _dump(value: Any) -> str:
    """The exact text every contract artifact is written as (LF line endings)."""
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def _sha_text(text: str) -> str:
    """The hash of the bytes `write_text_lf` will write for this text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _forbidden_markers(root: Path | None = None, home: Path | None = None) -> list[str]:
    """Machine paths that must never reach a public golden, derived at run time.

    Derived from this checkout and this user rather than written out as literals:
    a repository under `D:/work/...` and a home at `/home/...` have to be caught by
    the same code that guards `E:/boardwise` and `C:/Users/...`.
    """
    root = ROOT if root is None else root
    home = Path.home() if home is None else home
    markers = {
        ".tmp_540",
        str(root),
        str(root).replace("\\", "/"),
        str(home),
        str(home).replace("\\", "/"),
    }
    return sorted(marker for marker in markers if len(marker) > 3)


def _assert_clean(
    where: str, text: str, markers: Sequence[str] | None = None
) -> None:
    """Refuse a serialized artifact that still names a machine path."""
    for marker in _forbidden_markers() if markers is None else markers:
        if marker in text:
            raise RuntimeError(
                f"{where}: unsanitized machine path {marker!r} survived — golden "
                "artifacts must not name the machine that generated them"
            )
    leak = RESIDUAL_ABSOLUTE_PATH.search(text)
    if leak:
        raise RuntimeError(
            f"{where}: residual absolute path {leak.group(0)!r} survived sanitization"
        )


def _render(produced: Mapping[str, Path]) -> dict[Path, str]:
    """Render every artifact in memory; write nothing and touch no final file."""
    input_texts: dict[Path, str] = {}
    input_hashes: dict[str, str] = {}
    case_rows: list[dict[str, Any]] = []
    producer_versions: dict[str, Any] | None = None
    schema_hashes: dict[str, str] = {}
    for case_id, source in produced.items():
        # The id names the case; the kind decides the schema and the projection.
        # For the five producer cases they are the same string, so their rows and
        # expected values cannot move.
        kind = CASE_KINDS.get(case_id, case_id)
        # Strict loader: a producer that emitted NaN/Infinity/1e999 has produced a
        # file the Rust side cannot even read, so it must never reach the golden.
        raw = load_path(source)
        payload = _sanitize(raw)
        text = _dump(payload)
        _assert_clean(case_id, text)
        # The schema the Python runner gates this very input with (`SCHEMAS` lives
        # in tools.differential, the module that reads the case book), read through
        # the same strict loader and enforced *before* anything is projected or
        # published. Dropping this check was a real regression: projection alone
        # happily emitted a golden from a contract-invalid file.
        schema_path = ROOT / "contracts" / "json" / SCHEMAS[kind]
        assert_valid(payload, load_path(schema_path))
        schema_hashes[schema_path.relative_to(ROOT).as_posix()] = _sha(schema_path)
        name = INPUT_NAMES[case_id]
        # Projected from the sanitized payload itself, not from a file on disk: the
        # expected value can only describe the object about to be published.
        expected = project_payload(kind, payload)
        relative = f"{INPUTS_RELATIVE}/{name}"
        input_texts[INPUTS / name] = text
        input_hashes[relative] = _sha_text(text)
        case_rows.append({
            "id": case_id,
            "kind": kind,
            "input": relative,
            "expected": expected,
        })
        if kind == "review-report-projection":
            # Provenance copied from the report this run actually publishes — never
            # re-derived, so the manifest cannot claim a rule set the golden is not
            # showing.
            versions = payload.get("completion", {}).get("sourceVersions")
            if not isinstance(versions, dict) or not versions:
                raise RuntimeError(
                    "the review report carries no completion.sourceVersions; "
                    "producerVersions would be a guess"
                )
            producer_versions = dict(versions)
    if producer_versions is None:
        raise RuntimeError(
            "no review-report case was produced; producerVersions cannot be recorded"
        )
    book = {
        "schema": "boardwise.differential-cases/1",
        "normalization": {
            "keyOrder": "lexicographic in report comparisons; input object order is preserved where the contract requires it",
            "paths": "previews are compared by basename; timestamps and machine paths are sanitized",
            "numbers": "JSON numbers are preserved; LayoutPlan geometry uses canonical compact JSON sorted by key",
        },
        "cases": case_rows,
    }
    book_text = _dump(book)
    _assert_clean("cases", book_text)
    sources = [
        FIXTURES / "ch340_golden.epro2",
        DRAW / "divider.circuit.json",
        DRAW / "divider.presentation.json",
        DRAW / "library.json",
        SOURCES / "page.circuit.json",
        SOURCES / "page.presentation.json",
        SAMPLE_SOURCES,
        SYMBOL_SAMPLE_SOURCES,
    ]
    manifest = {
        "schema": "boardwise.differential-manifest/1",
        "sources": {
            path.relative_to(ROOT).as_posix(): _sha(path) for path in sources
        },
        # The rule-set/rule-body digests the published review report states, copied
        # from its `completion.sourceVersions` (see `_render`).
        "producerVersions": producer_versions,
        # The schemas this case book's inputs are validated against, hashed.
        "schemas": schema_hashes,
        "producers": [
            "python -m boardwise.cli checkup --file tests/fixtures/ch340_golden.epro2 --out <OUT>/checkup (accept 0 or 3)",
            "python -m boardwise.cli draw compile --circuit <FIXTURES>/divider.circuit.json --presentation <FIXTURES>/divider.presentation.json --profiles <FIXTURES>/library.json --page-box 0,-1000,1200,0 --out <OUT>/compile --json <OUT>/compile-result.json",
            "python -m boardwise.cli draw compile --circuit contracts/differential/sources/page.circuit.json --presentation contracts/differential/sources/page.presentation.json --profiles <FIXTURES>/library.json --page-box 0,0,1169,826 --out <OUT>/compile-page --json <OUT>/page-compile-result.json",
            "python -m boardwise.cli draw lint --snapshot <OUT>/lint-snapshot.json --render <OUT>/lint-render.svg --json <OUT>/lint-result.json",
            "declared samples contracts/differential/sources/epru-stream-samples.json -> <OUT>/epru-stream-v3-eof.json <OUT>/epru-stream-v4-eof-truncated.json (written from the declaration file, not from the editor, a container or a fixture)",
            "declared samples contracts/differential/sources/symbol-library-samples.json -> <OUT>/symbol-library-v3-zindex.json <OUT>/symbol-library-v4-pin-id.json (written from the declaration file, carrying the pinKey each stream is keyed by)",
        ],
        "regenerate": ".venv/Scripts/python.exe -m tools.build_differential_fixtures",
        "sanitization": [
            "generatedAt -> <GENERATED_AT>",
            "repository work paths -> <OUT>",
            "tests/fixtures paths -> <FIXTURES>",
            "user .boardwise paths -> <HOME>",
            "backslashes in strings -> forward slashes",
            "no real project container is read or copied; inputs come only from the public/synthetic sources above",
        ],
        "inputs": input_hashes,
        # The repo-relative name of the case book, not `CASES` computed against
        # whatever working directory this run happens to use.
        "caseBook": {"path": CASES_RELATIVE, "sha256": _sha_text(book_text)},
    }
    manifest_text = _dump(manifest)
    _assert_clean("manifest", manifest_text)
    return {**input_texts, CASES: book_text, MANIFEST: manifest_text}


def _publish(rendered: Mapping[Path, str]) -> None:
    """Write finished artifacts with LF endings.

    Nothing here can fail on projection, schema, sanitization or hashing — all of
    that ran in `_render`. This is still a loop of single-file writes: it is
    all-or-nothing with respect to *compute* failures, not a filesystem-wide
    transaction, and a failure inside the loop can leave the files it wrote.
    """
    for path, text in rendered.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        write_text_lf(path, text)


def _regenerate(produced: Mapping[str, Path]) -> None:
    """Render everything, then publish; no final file is written before render returns."""
    _publish(_render(produced))


def main() -> int:
    _regenerate(_produce())
    print(f"wrote {len(INPUT_NAMES)} differential cases: {CASES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
