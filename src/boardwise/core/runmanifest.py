"""RunManifest: the machine-readable record of what one review run froze (541 R1).

A review run is only reproducible if somebody can say what it looked at. Until
this module existed, "same baseline" was a sentence in a strategy table: the
inputs' hashes, the engine that judged them, the intent it judged against and
the evidence channels it actually had were spread across the report, the CLI
arguments and the operator's memory, so nobody could tell a *re-run* from a
*new look*. `run.json` is that record — deliberately **not** a section of
`report.json`, because scheduling state (how many DRC reviews this run has
already had, which findings are new) must never be read as a board-level
conclusion.

The shape, one key at a time:

.. code-block:: jsonc

    {
      "schema": "boardwise.run-manifest/1",
      "runId": "…",                                      // this run, not this board
      "inputs": [{"path": "…", "bytes": 12, "sha256": "…"}],
      "engine": {"boardwise": "…", "ruleset": "…", "rulebody": "…"},
      "intent": {"path": "…", "sha256": "…"},            // or null
      "pages": ["…"],                                    // page uuids read this run
      "channels": {"liveSchematic": true, "archivePcb": false, "…": false},
      "modelCounts": {"components": 0, "nets": 0, "datasheetsMissing": 0},
      "findings": ["…"],                                 // stable identities
      "drcReviewCount": 1,                               // starts at 1
      "newEvidence": "archive-bytes-changed"             // or null
    }

Three properties are the whole point, and each one is enforced here rather than
left to the caller:

1. **A baseline is only the evidence, never the result.** :func:`manifest_baseline`
   keeps `inputs` / `engine` / `intent` / `channels` and drops `runId`,
   `findings`, `modelCounts`, `drcReviewCount` and `newEvidence`. Two runs of the
   same files can produce different findings; that is a finding delta, not a
   changed baseline, and mixing the two is how "the design changed" gets asserted
   from "the report changed".
2. **Letting the baseline move needs more than one variable, or it is not an
   attribution.** :func:`semantic_diff` lists the semantic differences and names
   the single variable that moved. When two or more moved (an archive re-export
   *and* a new screenshot, say), the answer is `multi-variable-change` and no
   single-factor story — the diff still shows every difference, it just refuses
   to hand the change to one of them.
3. **A finding is an identity, not a message.** `findings` holds the stable
   identity strings the *caller* produced; this module never formats, parses or
   compares their prose, so a reworded detail is the same finding and two
   distinct defects are not collapsed into one. It also imports no review
   engine: shared code that reached into the reviewer would make the manifest a
   review artifact instead of a record both lines can read.

Refusals are uniform and named: bad JSON, a non-object document, an unknown
`schema` version, an illegal path / hash / count, an unknown key (the closed
schema every contract here follows), a duplicate input path, page or finding
identity all raise :class:`RunManifestError` with the offending path spelled
out. Writing is same-directory temporary file + :func:`os.replace`, so a reader
never sees half a manifest and a failed write does not damage the previous one.

`channels` records what evidence the run **actually** had (`liveSchematic`,
`archivePcb`, `livePcb`, `schematicImage`, `pcbImage`, `datasheets` — absent
keys read as `false`). It is baseline, so :func:`semantic_diff` compares it as
one variable per channel; it is not a place to park run results, and this module
neither infers a channel from a board's name nor turns a channel into a verdict.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import uuid
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

SCHEMA = "boardwise.run-manifest/1"

#: The evidence channels a run either has or does not have. Recording is not
#: guessing: a channel is whatever the caller measured, and a missing key in a
#: manifest reads as "not collected" rather than "not needed".
CHANNELS = (
    "liveSchematic",
    "archivePcb",
    "livePcb",
    "schematicImage",
    "pcbImage",
    "datasheets",
)

#: What a diff calls a change that cannot be handed to one variable.
ATTRIBUTION_MULTI = "multi-variable-change"

_TOP_KEYS = (
    "schema",
    "runId",
    "inputs",
    "engine",
    "intent",
    "pages",
    "channels",
    "modelCounts",
    "findings",
    "drcReviewCount",
    "newEvidence",
)
_REQUIRED_TOP_KEYS = frozenset({"schema", "runId", "inputs", "engine", "channels"})
_INPUT_KEYS = ("path", "bytes", "sha256")
_ENGINE_KEYS = ("boardwise", "ruleset", "rulebody")
_INTENT_KEYS = ("path", "sha256")
_COUNT_KEYS = ("components", "nets", "datasheetsMissing")
_SHA256 = re.compile(r"[0-9a-f]{64}")


class RunManifestError(ValueError):
    """A manifest is unreadable, malformed, or names something that cannot be.

    A ValueError subclass on purpose: every caller that already treats "the
    input file is bad" as a bad-input case keeps working, including the CLI's
    bad-input exit code, without a second exception family to learn.
    """


# --------------------------------------------------------------------------
# Field validators — each one names the offending path, not just the rule
# --------------------------------------------------------------------------


def _object(value: Any, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RunManifestError(f"{where}: expected a JSON object, got {type(value).__name__}")
    return value


def _closed(value: Mapping[str, Any], allowed: Iterable[str], where: str) -> None:
    unknown = sorted(set(value) - set(allowed))
    if unknown:
        raise RunManifestError(
            f"{where}: unknown key(s) {unknown}; the manifest schema is closed"
        )


def _text(value: Any, where: str) -> str:
    if not isinstance(value, str):
        raise RunManifestError(f"{where}: expected a string, got {type(value).__name__}")
    text = value.strip()
    if not text:
        raise RunManifestError(f"{where}: must not be empty")
    if "\x00" in text:
        raise RunManifestError(f"{where}: must not contain NUL")
    return text


def _path(value: Any, where: str) -> str:
    """A recorded path: non-empty, no NUL, no `..` segment, `/` separators.

    Separators are normalised (never resolved) so the same file written from
    Windows and from a POSIX shell is the same input; `..` is refused because a
    manifest that can point above its own root cannot be compared safely.
    """
    text = _text(value, where).replace("\\", "/")
    parts = text.split("/")
    if ".." in parts:
        raise RunManifestError(f"{where}: {text!r} must not traverse with '..'")
    if parts[-1] in ("", "."):
        raise RunManifestError(f"{where}: {text!r} does not name a file")
    return text


def _sha256(value: Any, where: str) -> str:
    if not isinstance(value, str):
        raise RunManifestError(
            f"{where}: expected a 64-character hex digest, got {type(value).__name__}"
        )
    digest = value.strip().lower()
    if not _SHA256.fullmatch(digest):
        raise RunManifestError(f"{where}: {value!r} is not a sha256 hex digest")
    return digest


def _count(value: Any, where: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RunManifestError(f"{where}: expected an integer, got {type(value).__name__}")
    if value < minimum:
        raise RunManifestError(f"{where}: {value} is below the minimum {minimum}")
    return value


def _sequence(value: Any, where: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise RunManifestError(f"{where}: expected a JSON array, got {type(value).__name__}")
    return value


def _unique(seen: dict[str, Any], key: str, where: str) -> None:
    if key in seen:
        raise RunManifestError(f"{where}: {key!r} appears more than once")


# --------------------------------------------------------------------------
# The document
# --------------------------------------------------------------------------


def _inputs(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: dict[str, Any] = {}
    for index, row in enumerate(_sequence(value, "inputs")):
        where = f"inputs[{index}]"
        entry = _object(row, where)
        _closed(entry, _INPUT_KEYS, where)
        path = _path(entry.get("path"), f"{where}.path")
        _unique(seen, path, where)
        seen[path] = entry
        rows.append(
            {
                "path": path,
                "bytes": _count(entry.get("bytes"), f"{where}.bytes"),
                "sha256": _sha256(entry.get("sha256"), f"{where}.sha256"),
            }
        )
    return sorted(rows, key=lambda row: row["path"])


def _engine(value: Any) -> dict[str, str]:
    entry = _object(value, "engine")
    _closed(entry, _ENGINE_KEYS, "engine")
    return {key: _text(entry.get(key), f"engine.{key}") for key in _ENGINE_KEYS}


def _intent(value: Any) -> dict[str, str] | None:
    if value is None:
        return None
    entry = _object(value, "intent")
    _closed(entry, _INTENT_KEYS, "intent")
    return {
        "path": _path(entry.get("path"), "intent.path"),
        "sha256": _sha256(entry.get("sha256"), "intent.sha256"),
    }


def _pages(value: Any) -> list[str]:
    pages: list[str] = []
    seen: set[str] = set()
    for index, page in enumerate(_sequence(value, "pages")):
        where = f"pages[{index}]"
        identity = _text(page, where)
        if identity in seen:
            raise RunManifestError(f"{where}: page {identity!r} appears more than once")
        seen.add(identity)
        pages.append(identity)
    return pages


def _channels(value: Any) -> dict[str, bool]:
    """Evidence as it actually was. A non-boolean is refused, never coerced.

    The known channels are always materialised, a channel the manifest does not
    mention as `false`: "not in the document" and "not collected" are the same
    evidence state, and materialising it here keeps `sameBaseline` and the token
    list in agreement. Extra names are kept (a later channel needs no bump), and
    they are compared the same way.
    """
    entry = _object(value, "channels")
    if not all(isinstance(name, str) and name.strip() for name in entry):
        raise RunManifestError("channels: channel names must be non-empty strings")
    for name in sorted(entry):
        if not isinstance(entry[name], bool):
            raise RunManifestError(
                f"channels.{name}: expected true/false, got {type(entry[name]).__name__}"
            )
    names = sorted(set(CHANNELS) | set(entry))
    return {name: bool(entry.get(name, False)) for name in names}


def _model_counts(value: Any) -> dict[str, int]:
    """The three model counters; a section that is present owes all three."""
    entry = _object(value, "modelCounts")
    _closed(entry, _COUNT_KEYS, "modelCounts")
    missing = [key for key in _COUNT_KEYS if key not in entry]
    if missing:
        raise RunManifestError(
            f"modelCounts: missing required counter(s) {missing}; a counter that is "
            "not measured is an absent section, not a zero"
        )
    return {key: _count(entry[key], f"modelCounts.{key}") for key in _COUNT_KEYS}


def _findings(value: Any) -> list[str]:
    """The caller's stable identities — never message text, never parsed here."""
    findings: list[str] = []
    seen: set[str] = set()
    for index, finding in enumerate(_sequence(value, "findings")):
        where = f"findings[{index}]"
        identity = _text(finding, where)
        if identity in seen:
            raise RunManifestError(f"{where}: finding identity {identity!r} repeats")
        seen.add(identity)
        findings.append(identity)
    return sorted(findings)


def _manifest(value: Any) -> dict[str, Any]:
    """Validate and normalise a manifest document (the one acceptance gate)."""
    entry = _object(value, "manifest")
    _closed(entry, _TOP_KEYS, "manifest")
    missing = sorted(_REQUIRED_TOP_KEYS - set(entry))
    if missing:
        raise RunManifestError(f"manifest: missing required key(s) {missing}")
    if entry.get("schema") != SCHEMA:
        raise RunManifestError(
            f"manifest.schema: {entry.get('schema')!r} is not the supported "
            f"version {SCHEMA!r}"
        )
    evidence = entry.get("newEvidence")
    return {
        "schema": SCHEMA,
        "runId": _text(entry.get("runId"), "manifest.runId"),
        "inputs": _inputs(entry.get("inputs")),
        "engine": _engine(entry.get("engine")),
        "intent": _intent(entry.get("intent")),
        "pages": _pages(entry.get("pages", [])),
        "channels": _channels(entry.get("channels")),
        "modelCounts": (
            _model_counts(entry["modelCounts"])
            if "modelCounts" in entry
            else {key: 0 for key in _COUNT_KEYS}
        ),
        "findings": _findings(entry.get("findings", [])),
        "drcReviewCount": _count(
            entry.get("drcReviewCount", 1), "manifest.drcReviewCount", minimum=1
        ),
        "newEvidence": None if evidence is None else _text(evidence, "manifest.newEvidence"),
    }


# --------------------------------------------------------------------------
# Hashing, reading, writing
# --------------------------------------------------------------------------


def sha256_file(path: str | os.PathLike[str]) -> str:
    """The lowercase hex SHA-256 of a file, read in chunks.

    One implementation for the whole repository: a manifest's `sha256` and the
    guard's recomputation must be the same number, so neither side gets to spell
    the digest differently.
    """
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Read and validate a `run.json`; raises :class:`RunManifestError`.

    A missing file is refused rather than treated as an empty manifest: "there
    is no record of a previous run" and "the previous run froze nothing" are
    different facts, and only the caller can decide which one it is looking at.
    """
    target = Path(path)
    try:
        raw = target.read_text(encoding="utf-8")
    except OSError as error:
        raise RunManifestError(f"{target}: cannot read run manifest ({error})") from error
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        raise RunManifestError(f"{target}: not valid JSON ({error})") from error
    return _manifest(data)


def write_manifest(path: str | os.PathLike[str], manifest: Mapping[str, Any]) -> Path:
    """Validate, then atomically replace `path` with the manifest.

    The bytes go to a temporary file **in the same directory** and are then moved
    into place with :func:`os.replace`, so a concurrent reader sees either the
    old manifest or the new one, never a truncated document. The manifest is
    validated before anything is opened, so a refused document leaves the
    previous file untouched.
    """
    document = _manifest(manifest)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        dir=str(target.parent),
        prefix=f".{target.name}.",
        suffix=".tmp",
        delete=False,
    )
    temporary = handle.name
    try:
        with handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    return target


def make_manifest(
    *,
    inputs: Iterable[Mapping[str, Any]],
    engine: Mapping[str, Any],
    channels: Mapping[str, bool],
    run_id: str | None = None,
    intent: Mapping[str, Any] | None = None,
    pages: Iterable[str] = (),
    model_counts: Mapping[str, Any] | None = None,
    findings: Iterable[str] = (),
    drc_review_count: int = 1,
    new_evidence: str | None = None,
) -> dict[str, Any]:
    """Build a validated manifest, defaulting everything a fresh run has not got.

    `runId` defaults to a fresh uuid (a run, not a board), `intent` to `null`,
    `pages`/`findings` to empty, `modelCounts` to zeros, `drcReviewCount` to 1 —
    the first review of a run — and `newEvidence` to `null`. Defaults are here so
    a caller that has only the evidence does not have to invent scheduling
    fields; the fields stay in the document because a reader cannot tell a
    default from a measurement otherwise.

    `findings` must be the caller's **stable identity strings** (for example the
    rule code plus the objects it is about). This module stores and compares them
    and never asks what they mean; it imports no review engine.
    """
    document = {
        "schema": SCHEMA,
        "runId": str(uuid.uuid4()) if run_id is None else run_id,
        "inputs": list(inputs),
        "engine": dict(engine),
        "intent": None if intent is None else dict(intent),
        "pages": list(pages),
        "channels": dict(channels),
        "modelCounts": (
            {key: 0 for key in _COUNT_KEYS}
            if model_counts is None
            else dict(model_counts)
        ),
        "findings": list(findings),
        "drcReviewCount": drc_review_count,
        "newEvidence": new_evidence,
    }
    return _manifest(document)


# --------------------------------------------------------------------------
# Baseline and semantic diff
# --------------------------------------------------------------------------


def _baseline(document: Mapping[str, Any]) -> dict[str, Any]:
    """The evidence half of an already-normalised manifest."""
    return {
        "inputs": document["inputs"],
        "engine": document["engine"],
        "intent": document["intent"],
        "channels": document["channels"],
    }


def manifest_baseline(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """What this run looked at: `inputs` / `engine` / `intent` / `channels`.

    `runId`, `findings`, `modelCounts`, `drcReviewCount` and `newEvidence` are
    run results and scheduling state, so they are **not** in the baseline: two
    runs over the same evidence are the same baseline even when one of them
    found something new. The returned channels are the run's actual evidence
    status, compared only as baseline fields — this function never merges a run
    result into them.
    """
    return _baseline(_manifest(manifest))


def _input_changes(
    old: Sequence[Mapping[str, Any]], new: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    before = {row["path"]: row["sha256"] for row in old}
    after = {row["path"]: row["sha256"] for row in new}
    changes = []
    for path in sorted(set(before) | set(after)):
        if before.get(path) != after.get(path):
            changes.append({"path": path, "before": before.get(path), "after": after.get(path)})
    return changes


def _identities(value: Iterable[str]) -> set[str]:
    return set(value)


def semantic_diff(
    old: Mapping[str, Any], new: Mapping[str, Any]
) -> dict[str, Any]:
    """Diff two manifests semantically: evidence first, findings separately.

    Returns:

    * `sameBaseline` — the four baseline fields are identical. Findings are not
      part of it, so a run that reported new defects over unchanged evidence is
      still `sameBaseline: true`.
    * `inputsChanged` — one `{path, before, after}` row per input whose digest
      was added, removed or replaced (`before`/`after` are `null` on the side
      that lacks it), sorted by path.
    * `coverageChanged` — the channel names whose evidence state differs, sorted;
      an empty list means the same coverage.
    * `addedFindings` / `removedFindings` — the finding **identities** that
      appeared or disappeared, as sets of the caller's strings. A rewording is
      the same identity and is not a delta; two identities are never merged
      because their prose looks alike.
    * `multiVariableChange` — more than one baseline variable moved.
    * `attribution` — `null` when nothing moved, the single variable token
      (`input:<path>`, `channel:<name>`, `engine:<field>`, `intent`) when exactly
      one did, and `multi-variable-change` when several did. A multi-variable
      change is **never** handed to one variable: the difference list is still
      reported in full, but no single-factor story is offered.

    Findings never move the baseline and never become an attribution token, so
    "the design changed" can only come from evidence, and "the report changed"
    stays what it is.
    """
    old_doc = _manifest(old)
    new_doc = _manifest(new)
    old_base = _baseline(old_doc)
    new_base = _baseline(new_doc)

    inputs_changed = _input_changes(old_base["inputs"], new_base["inputs"])
    channels_changed = sorted(
        name
        for name in set(old_base["channels"]) | set(new_base["channels"])
        if old_base["channels"].get(name) != new_base["channels"].get(name)
    )

    variables = [f"input:{row['path']}" for row in inputs_changed]
    variables += [f"channel:{name}" for name in channels_changed]
    variables += [
        f"engine:{field}"
        for field in sorted(_ENGINE_KEYS)
        if old_base["engine"][field] != new_base["engine"][field]
    ]
    if old_base["intent"] != new_base["intent"]:
        variables.append("intent")

    if not variables:
        attribution = None
    elif len(variables) > 1:
        attribution = ATTRIBUTION_MULTI
    else:
        attribution = variables[0]

    old_findings = _identities(old_doc["findings"])
    new_findings = _identities(new_doc["findings"])

    return {
        "sameBaseline": old_base == new_base,
        "inputsChanged": inputs_changed,
        "coverageChanged": channels_changed,
        "addedFindings": sorted(new_findings - old_findings),
        "removedFindings": sorted(old_findings - new_findings),
        "multiVariableChange": len(variables) > 1,
        "attribution": attribution,
    }
