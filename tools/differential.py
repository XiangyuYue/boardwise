"""Run the 540C Python side of the JSON differential/golden cases.

Process boundary (540C F5): an input the runner cannot use — an unknown case kind,
a case book without its ``cases`` array, an input the contract schema refuses, a
missing file, or an ``--output`` whose parent directory does not exist — is a
*request* failure, not a differing golden. It leaves stdout empty and writes one
``boardwise.cli-result/1`` envelope to stderr with ``command: "differential"``,
``exitCode: 2`` and ``error.code: "BAD_REQUEST"``, then exits 2 — the shape the
Rust CLI already states every failure in. The message keeps the local diagnostic
(the path that was not found, the schema error list); it is deliberately *not* a
copy of the Rust text, which carries the OS's own localized wording and would
pin a platform string as if it were a contract.

A run that read every case still exits 0 (goldens agree) or 1 (a golden
disagrees); nothing else about those two paths changed, byte for byte.

Known gap, deliberately left open by this batch: argparse's *usage* errors (an
unknown flag, a flag missing its value, ``-h``/``--help``) keep argparse's own
text on stderr and argparse's own exit 2. The Rust CLI now parses
``--flag=value`` and answers ``-h``/``--help``, so the two surfaces are no longer
missing each other outright; what still differs is argparse's unambiguous-prefix
abbreviation, its help ordering and wording, and its error phrasing (F6).
Freezing one shape here would pin that disagreement instead of removing one. See
:func:`main`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from boardwise.core.layoutplan import LayoutPlan
from boardwise.parsers.epru_stream import ParseStats, iter_epru_records, split_documents
from boardwise.parsers.schematic import _SymbolDef, _collect_symbols
from tools.contract_validate import ContractValidationError, assert_valid, load_path
from tools.differential_compare import canonical_bytes, write_text_lf

ROOT = Path(__file__).resolve().parents[1]
#: The envelope every boardwise command states a failure in: the Rust CLI writes
#: this same document (schema, command, exitCode, error, and no payload).
CLI_RESULT_SCHEMA = "boardwise.cli-result/1"
#: "the request cannot be carried out" — never 1, which means a golden differs.
ERROR_EXIT_CODE = 2
#: ``kind`` → schema file.
#:
#: ``symbol-library-sample`` (038L) joined as the seventh kind once its two
#: declared samples were published into the case book; the projection it gates is
#: :func:`_symbol_library_projection`, the same one the Rust runner derives from
#: the same `text` + `pinKey`.
SCHEMAS = {
    "review-report-projection": "review-report-v1.schema.json",
    "layout-plan-geometry": "layout-plan-v1.schema.json",
    "compile-result-projection": "draw-compile-result-v1.schema.json",
    "compile-page-result-projection": "draw-page-compile-result-v1.schema.json",
    "lint-result-projection": "draw-lint-result-v1.schema.json",
    "epru-stream-sample": "epru-stream-sample-v1.schema.json",
    "symbol-library-sample": "symbol-library-sample-v1.schema.json",
}
#: Schema tag of the `.epru` stream projection both runners emit.
EPRU_STREAM_SCHEMA = "boardwise.epru-stream/1"
#: Schema tag of the SYMBOL library projection both runners emit.
SYMBOL_LIBRARY_SCHEMA = "boardwise.symbol-library/1"
#: The two refs a pin can be addressed by, as the sample contract's
#: ``pinKey`` enum states them (V3 ``.epro2`` vs eprj3).
SYMBOL_PIN_KEYS = ("zIndex", "pin_id")


def _required(mapping: dict[str, Any], key: str, where: str) -> Any:
    """A key the document must state; its absence is a request failure."""
    try:
        return mapping[key]
    except KeyError:
        raise ValueError(f"{where} is missing the required key {key!r}") from None


def _schema_name(kind: Any) -> str:
    """The schema file gating one case kind; an unknown kind is refused by name."""
    try:
        return SCHEMAS[kind]
    except (KeyError, TypeError):
        raise ValueError(f"unknown differential case kind: {kind!r}") from None


def _load_case_input(case: dict[str, Any], root: Path) -> Any:
    path = root / _required(case, "input", "a differential case")
    # The case input and the schema that gates it are both read through the one
    # strict loader: a `NaN`/`Infinity` token is not JSON, and Python's default
    # parser would accept a file the Rust side refuses.
    payload = load_path(path)
    schema = load_path(ROOT / "contracts" / "json" / _schema_name(case.get("kind")))
    assert_valid(payload, schema)
    return payload


def _preview_names(previews: list[str]) -> list[str]:
    """The final path segment of each preview, derived the way the Rust runner does.

    Rust's runner splits on both separators (`/` and a backslash) whatever the
    host OS is. `Path(item).name` does not: on POSIX a backslash is an ordinary
    character, so the same Windows-style preview projected as one long name there
    and as its basename on Windows. Normalizing first makes this host-independent
    and states the same rule the contract's preview pattern enforces.
    """
    return [item.replace("\\", "/").rsplit("/", 1)[-1] for item in previews]


def _epru_stream_projection(text: str) -> dict[str, Any]:
    """Project one ``.epru`` record stream — a second *view*, never a parser.

    The counts and the document split come from the real readers,
    :func:`~boardwise.parsers.epru_stream.split_documents` (which itself walks
    :func:`~boardwise.parsers.epru_stream.iter_epru_records`), so a differential
    mismatch can only ever be about the projection, never about a private copy
    of the framing rules. The per-line loop below re-reads each line **only** to
    recover what the stream scan does not hand back per record — the decoded
    type, body presence, and whether the body was empty — and it reads them from
    the same decoder with a throwaway :class:`ParseStats`, because folding those
    counts into the stream's own stats would count every record twice.

    Line numbers are the file's: the decoder numbers a one-line text from 0, so
    the loop's index replaces ``record.line_no``. A kept-document index is
    attached from the split's own ``records`` (each records its ``line_no``), so
    a record belongs to a document exactly when the splitter put it there.

    What is deliberately **not** emitted: bodies (presence only), the record types
    this parser has never seen (that is a drift signal on ``ParseStats``, not a
    projection field), and any reason a line was malformed — Python never
    classifies the failure, and a classification invented here would be a field
    the Rust side could only agree with by copying it.
    """
    stats = ParseStats()
    documents = split_documents(text, stats)
    owners: dict[int, int] = {}
    for index, document in enumerate(documents):
        for record in document.records:
            owners[record.line_no] = index
    records: list[dict[str, Any]] = []
    for line_no, line in enumerate(text.split("\n")):
        if not line:
            continue
        line_stats = ParseStats()
        decoded = list(iter_epru_records(line, line_stats))
        if not decoded:
            # Malformed: the line is still a record (both runners report the
            # same line count), it just carries no decoded field.
            records.append({
                "lineNo": line_no,
                "type": "",
                "hasBody": False,
                "emptyBody": False,
                "malformed": True,
            })
            continue
        record = decoded[0]
        item: dict[str, Any] = {
            "lineNo": line_no,
            "type": record.type,
            "hasBody": record.has_body,
            "emptyBody": line_stats.empty_body_records > 0,
            "malformed": False,
        }
        # ``docType`` lives in the **body** of a ``DOCHEAD``; ``str`` is what the
        # splitter counts in ``document_types``, so both say the same name.
        doc_type = (record.body or {}).get("docType") if record.type == "DOCHEAD" else None
        if doc_type is not None:
            item["docType"] = str(doc_type)
        owner = owners.get(line_no)
        if owner is not None:
            item["document"] = owner
        records.append(item)
    return {
        "schema": EPRU_STREAM_SCHEMA,
        "records": records,
        "total": stats.total_records,
        "malformed": stats.malformed_records,
        "emptyBody": stats.empty_body_records,
        "documents": [
            {"docType": document.doc_type, "recordCount": len(document.records)}
            for document in documents
        ],
        "documentTypes": dict(stats.document_types),
        "recordsByType": dict(stats.records_by_type),
    }


def _symbol_pin(symbol: _SymbolDef, number: str) -> dict[str, Any]:
    """One pin of a ``_SymbolDef``, in the projection's spelling.

    The point is **already canvas space**: ``_commit_symbol`` negates the stored
    y once (``_page_y``) and rounds to ``COORD_PRECISION``, so flipping it again
    here would be the second negation task 010c forbids. ``name``/``type`` are
    omitted rather than stated empty — a pin the library never named has no
    name, and ``""`` would be a value the Rust side could only reproduce by
    inventing the same placeholder.
    """
    point, ref = symbol.pins[number]
    pin: dict[str, Any] = {"point": [point[0], point[1]], "ref": ref}
    name = symbol.pin_names.get(number)
    if name:
        pin["name"] = name
    pin_type = symbol.pin_types.get(number)
    if pin_type:
        pin["type"] = pin_type
    return pin


def _symbol_library_projection(payload: dict[str, Any]) -> dict[str, Any]:
    """Project one ``.epru`` SYMBOL library — a second *view*, never a parser.

    Both counts and both merge rules come from the real reader:
    :func:`~boardwise.parsers.epru_stream.iter_epru_records` decodes the stream
    into the records the schematic parser consumes, and
    :func:`~boardwise.parsers.schematic._collect_symbols` turns those records
    into ``uuid -> _SymbolDef`` exactly as the review path does — including
    first-wins on a repeated uuid, its conflicting-document counter, and the
    dropped-pin counter for a run that ends with no number. Both counters come
    from the **same** :class:`~boardwise.core.geometry.ParseStats`, so a
    differential mismatch can only ever be about the projection.

    What is deliberately **not** emitted: the ``Pin Name``/``Pin Type`` of a pin
    that has no number (there is no key to file it under — it is counted, not
    projected), any record the symbol parser does not read, and the
    ``editVersion`` of a document (two copies that differ only there are the
    same symbol, and the counter already says so).
    """
    pin_key = payload["pinKey"]
    if pin_key not in SYMBOL_PIN_KEYS:
        raise ValueError(f"unknown symbol pinKey: {pin_key!r}")
    stats = ParseStats()
    records = list(iter_epru_records(payload["text"], stats))
    symbols = _collect_symbols(records, stats, pin_key=pin_key)
    return {
        "schema": SYMBOL_LIBRARY_SCHEMA,
        "pinKey": pin_key,
        "symbols": {
            uuid: {
                "title": symbol.title,
                "pins": {
                    number: _symbol_pin(symbol, number) for number in symbol.pins
                },
            }
            for uuid, symbol in symbols.items()
        },
        "pinsDroppedNoNumber": stats.pins_dropped_no_number,
        "conflictingDocuments": stats.conflicting_library_documents,
    }


def project_payload(kind: str, payload: Any) -> dict[str, Any]:
    """Emit the language-neutral projection from an already-parsed payload.

    Separate from :func:`project_case` so the fixture generator can project the
    exact sanitized object it is about to publish, before any file exists — the
    expected value can then never describe a file other than the one written.
    """
    if kind == "review-report-projection":
        summary = payload["summary"]
        return {
            "schema": payload["schema"],
            "completionVerdict": payload["completion"]["verdict"],
            "summaryExitCode": summary["exitCode"],
            "findingCount": len(payload["findings"]),
            "errorCount": summary["errorCount"],
            "warnCount": summary["warnCount"],
            "infoCount": summary["infoCount"],
            "evidenceDelivery": payload["evidence"]["delivery"]["status"],
        }
    if kind == "layout-plan-geometry":
        plan = LayoutPlan.from_dict(payload)
        return {
            "geometrySha256": plan.geometry_sha256(),
            "partCount": len(plan.parts),
            "segmentCount": len(plan.segments),
            "junctionCount": len(plan.junctions),
            "labelCount": len(plan.labels),
            "powerSymbolCount": len(plan.power_symbols),
            "textCount": len(plan.texts),
        }
    if kind == "compile-result-projection":
        return {
            "command": payload["command"],
            "ok": payload["ok"],
            "candidateCount": len(payload["candidates"]),
            "failureCount": len(payload["failures"]),
            "previewNames": _preview_names(payload["previews"]),
        }
    if kind == "compile-page-result-projection":
        # A page document holds pages. `candidateCount` belongs to the module
        # shape, so the page projection counts what this document actually states
        # rather than renaming it into a field the producer never wrote.
        return {
            "command": payload["command"],
            "ok": payload["ok"],
            "pageCount": len(payload["pages"]),
            "failureCount": len(payload["failures"]),
            "previewNames": _preview_names(payload["previews"]),
        }
    if kind == "lint-result-projection":
        return {
            "source": payload["source"],
            "exitCode": payload["exitCode"],
            "errorCount": payload["counts"]["ERROR"],
            "findingCount": len(payload["findings"]),
            "textReadable": payload["textReadable"],
        }
    if kind == "epru-stream-sample":
        return _epru_stream_projection(payload["text"])
    if kind == "symbol-library-sample":
        return _symbol_library_projection(payload)
    raise ValueError(f"unknown differential case kind: {kind!r}")


def project_case(case: dict[str, Any], root: Path) -> dict[str, Any]:
    """Read one input and emit the language-neutral, deliberately small projection."""
    return project_payload(case["kind"], _load_case_input(case, root))


def run_cases(cases_path: Path, root: Path, runner: str = "python") -> dict[str, Any]:
    book = load_path(cases_path)
    if not isinstance(book, dict):
        raise ValueError(f"a case book is a JSON object, got {type(book).__name__}")
    if book.get("schema") != "boardwise.differential-cases/1":
        raise ValueError(f"unsupported case-book schema: {book.get('schema')!r}")
    cases = book.get("cases")
    if not isinstance(cases, list):
        # A book with no case list has nothing to compare; say so instead of
        # leaving the caller with a KeyError it cannot act on.
        raise ValueError(
            f"case book {str(cases_path)!r} states no cases array "
            f"(got {type(cases).__name__})"
        )
    rows = []
    for index, case in enumerate(cases):
        where = f"case book cases[{index}]"
        if not isinstance(case, dict):
            raise ValueError(f"{where} is a JSON object, got {type(case).__name__}")
        case_id = _required(case, "id", where)
        expected = _required(case, "expected", where)
        actual = project_case(case, root)
        rows.append({
            "id": case_id,
            # Type-strict on purpose: Python's `==` calls True == 1 and
            # 95.0 == 95 equal, so a golden that spells a boolean as 1 would pass
            # here and fail on the Rust side. The bytes are the contract.
            "ok": canonical_bytes(actual) == canonical_bytes(expected),
            "actual": actual,
            "expected": expected,
        })
    return {
        "schema": "boardwise.differential-report/1",
        "runner": runner,
        "ok": all(row["ok"] for row in rows),
        "cases": rows,
    }


def failure_envelope(error: BaseException) -> dict[str, Any]:
    """The ``boardwise.cli-result/1`` document one request failure is stated in.

    No ``payload``: a failure states no result, exactly like the Rust CLI's
    ``CliResult::failure``. The message is this machine's own diagnostic, labelled
    by the kind of failure — an OS error keeps the OS wording and the path, a
    schema refusal keeps its error list.
    """
    message = str(error).strip() or type(error).__name__
    if isinstance(error, ContractValidationError):
        label = "contract error"
    elif isinstance(error, json.JSONDecodeError):
        label = "JSON error"
    elif isinstance(error, OSError):
        label = "I/O error"
    else:
        label = "invalid request"
    return {
        "schema": CLI_RESULT_SCHEMA,
        "command": "differential",
        "exitCode": ERROR_EXIT_CODE,
        "error": {"code": "BAD_REQUEST", "message": f"{label}: {message}"},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default=str(ROOT / "contracts" / "differential" / "cases.json"))
    parser.add_argument("--root", default=str(ROOT), help="Case input root (usually the repository).")
    parser.add_argument("--output", default="", help="Also write the full report as structured JSON.")
    # Usage errors stay argparse's own (see the module docstring): this batch pins
    # the runner's failures, not the abbreviation, help text and error wording the
    # Rust side still spells its own way, so `parse_args` is outside the handler
    # on purpose.
    args = parser.parse_args()
    try:
        report = run_cases(Path(args.cases), Path(args.root))
        text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        # Write before printing: a failed write must leave stdout empty, so nobody
        # reading stdout sees a report that contradicts the exit code.
        if args.output:
            write_text_lf(Path(args.output), text)
    except (ContractValidationError, OSError, ValueError) as error:
        # One envelope, stderr, exit 2 — the same failure surface the Rust CLI has
        # (F5). Never a traceback: a script is allowed to branch on this.
        sys.stderr.write(
            json.dumps(failure_envelope(error), ensure_ascii=False, indent=2) + "\n"
        )
        return ERROR_EXIT_CODE
    print(text, end="")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
