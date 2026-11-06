"""541 R1: the versioned RunManifest, its strict reader and the semantic diff.

The contract under test is `tasks/541_offline_runtime_gates.md` §1: a `run.json`
that freezes what a run looked at, a baseline that is evidence only, and a diff
that says *which* variable moved or refuses to name one. Two properties are the
reason this file exists at all:

* a finding is an **identity**, so a delta is a set difference of the caller's
  strings — never a comparison of message text, never a prefix collapse;
* a baseline change needs **one** variable to be attributed. Two variables that
  moved together are `multi-variable-change`, and the difference list is still
  reported in full, just without a single-factor story.

Nothing here touches the CLI, the review engine, fixtures or a real project: a
manifest is built from literals and `tmp_path`.
"""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import pytest

from boardwise.core import runmanifest

ROOT = Path(__file__).resolve().parents[1]
MODULE = Path(runmanifest.__file__)

DIGEST = "a" * 64
DIGEST_B = "b" * 64
DIGEST_C = "c" * 64

TOP_KEYS = [
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
]


def _manifest(**overrides):
    """A valid manifest, one input / one engine / one intent — ready to mutate."""
    fields = {
        "inputs": [{"path": "board.epro2", "bytes": 10, "sha256": DIGEST}],
        "engine": {"boardwise": "0.6.0", "ruleset": "2026-11", "rulebody": "body-1"},
        "channels": {"liveSchematic": True, "archivePcb": True, "livePcb": False},
        "run_id": "run-1",
        "intent": {"path": "intent.json", "sha256": DIGEST_B},
        "pages": ["page-uuid-1"],
        "model_counts": {"components": 12, "nets": 9, "datasheetsMissing": 2},
        "findings": ["r1:U+|cap-missing", "r3:R4|value"],
        "drc_review_count": 1,
    }
    fields.update(overrides)
    return runmanifest.make_manifest(**fields)


def _raw(tmp_path, document, name="run.json"):
    target = tmp_path / name
    target.write_text(json.dumps(document), encoding="utf-8")
    return target


def _refused(tmp_path, document, name="run.json"):
    path = _raw(tmp_path, document, name)
    with pytest.raises(runmanifest.RunManifestError) as caught:
        runmanifest.load_manifest(path)
    assert str(caught.value), "a refusal must say what is wrong"


# --------------------------------------------------------------------------
# The public surface and the digest
# --------------------------------------------------------------------------


def test_the_contract_names_are_the_documented_ones():
    assert runmanifest.SCHEMA == "boardwise.run-manifest/1"
    assert issubclass(runmanifest.RunManifestError, ValueError)
    assert runmanifest.CHANNELS == (
        "liveSchematic",
        "archivePcb",
        "livePcb",
        "schematicImage",
        "pcbImage",
        "datasheets",
    )
    assert runmanifest.ATTRIBUTION_MULTI == "multi-variable-change"
    for name in (
        "sha256_file",
        "load_manifest",
        "write_manifest",
        "make_manifest",
        "manifest_baseline",
        "semantic_diff",
    ):
        assert callable(getattr(runmanifest, name)), name


def test_the_module_is_shared_and_imports_no_review_engine():
    """Shared means shared: the manifest may not reach into the reviewer.

    Findings arrive as the caller's identity strings, so any in-package import
    here would be the wrong direction, not a convenience.
    """
    owners = json.loads(
        (ROOT / "contracts" / "module-owners.json").read_text(encoding="utf-8")
    )["modules"]
    assert owners["core/runmanifest.py"] == "shared"
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    foreign = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (
            node.level or (node.module or "").startswith("boardwise")
        ):
            foreign.append(node.module)
        elif isinstance(node, ast.Import):
            foreign += [
                alias.name for alias in node.names if alias.name.startswith("boardwise")
            ]
    assert foreign == []


def test_sha256_file_is_the_digest_every_other_reader_computes(tmp_path):
    empty = tmp_path / "empty.bin"
    empty.write_bytes(b"")
    abc = tmp_path / "abc.bin"
    abc.write_bytes(b"abc")
    assert runmanifest.sha256_file(empty) == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )
    assert runmanifest.sha256_file(abc) == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )
    big = tmp_path / "big.bin"
    big.write_bytes(b"abc" * 400_000)
    assert len(runmanifest.sha256_file(big)) == 64
    with pytest.raises(OSError):
        runmanifest.sha256_file(tmp_path / "missing.bin")


def test_make_manifest_defaults_the_fields_a_fresh_run_has_not_got():
    first = runmanifest.make_manifest(
        inputs=[],
        engine={"boardwise": "0.6.0", "ruleset": "r", "rulebody": "b"},
        channels={},
    )
    assert list(first) == TOP_KEYS
    assert first["schema"] == runmanifest.SCHEMA
    assert first["runId"] and first["runId"] == first["runId"].strip()
    assert first["intent"] is None and first["pages"] == [] and first["findings"] == []
    assert first["modelCounts"] == {"components": 0, "nets": 0, "datasheetsMissing": 0}
    assert first["drcReviewCount"] == 1 and first["newEvidence"] is None
    second = runmanifest.make_manifest(
        inputs=[],
        engine={"boardwise": "0.6.0", "ruleset": "r", "rulebody": "b"},
        channels={},
    )
    assert first["runId"] != second["runId"], "a run id names a run, not a board"


def test_make_manifest_keeps_what_the_caller_gave():
    document = _manifest(
        findings=["z:2", "a:1"],
        pages=["p2", "p1"],
        drc_review_count=2,
        new_evidence="archive-bytes-changed",
    )
    assert document["findings"] == ["a:1", "z:2"], "findings are a set of identities"
    assert document["pages"] == ["p2", "p1"], "page order is the caller's"
    assert document["drcReviewCount"] == 2
    assert document["newEvidence"] == "archive-bytes-changed"


# --------------------------------------------------------------------------
# Writing: round trip and atomicity
# --------------------------------------------------------------------------


def test_write_then_load_round_trips(tmp_path):
    document = _manifest()
    target = runmanifest.write_manifest(tmp_path / "run.json", document)
    assert target == tmp_path / "run.json"
    assert runmanifest.load_manifest(target) == document
    on_disk = json.loads(target.read_text(encoding="utf-8"))
    assert on_disk == document
    assert target.read_text(encoding="utf-8").endswith("\n")


def test_write_replaces_through_a_same_directory_temporary(tmp_path, monkeypatch):
    target = tmp_path / "run.json"
    runmanifest.write_manifest(target, _manifest(run_id="run-1"))
    seen = {}
    real_replace = runmanifest.os.replace

    def spy(source, destination):
        seen["source"] = Path(source)
        seen["destination"] = Path(destination)
        assert seen["source"].parent == target.parent, "temp must be a sibling"
        assert seen["source"] != target
        return real_replace(source, destination)

    monkeypatch.setattr(runmanifest.os, "replace", spy)
    runmanifest.write_manifest(target, _manifest(run_id="run-2"))
    assert seen["destination"] == target
    assert runmanifest.load_manifest(target)["runId"] == "run-2"
    assert [path.name for path in tmp_path.iterdir()] == ["run.json"], "no temp left"


def test_a_failed_write_leaves_the_previous_manifest_intact(tmp_path, monkeypatch):
    target = runmanifest.write_manifest(
        tmp_path / "run.json", _manifest(run_id="run-1")
    )
    before = target.read_bytes()

    broken = _manifest()
    broken["drcReviewCount"] = 0  # refused before anything is opened
    with pytest.raises(runmanifest.RunManifestError):
        runmanifest.write_manifest(target, broken)
    assert target.read_bytes() == before

    def explode(source, destination):
        raise OSError("disk gave up")

    monkeypatch.setattr(runmanifest.os, "replace", explode)
    with pytest.raises(OSError):
        runmanifest.write_manifest(target, _manifest(run_id="run-3"))
    assert target.read_bytes() == before
    assert [path.name for path in tmp_path.iterdir()] == ["run.json"]


# --------------------------------------------------------------------------
# Reading: every refusal is named
# --------------------------------------------------------------------------


def test_load_rejects_a_missing_file(tmp_path):
    with pytest.raises(runmanifest.RunManifestError) as caught:
        runmanifest.load_manifest(tmp_path / "run.json")
    assert "cannot read" in str(caught.value)


def test_load_rejects_bad_json(tmp_path):
    path = tmp_path / "run.json"
    path.write_text('{"schema": ', encoding="utf-8")
    with pytest.raises(runmanifest.RunManifestError) as caught:
        runmanifest.load_manifest(path)
    assert "not valid JSON" in str(caught.value)


@pytest.mark.parametrize("document", [[], "text", 7, None, True])
def test_load_rejects_a_non_object_document(tmp_path, document):
    _refused(tmp_path, document)


@pytest.mark.parametrize(
    "schema",
    ["boardwise.run-manifest/2", "boardwise.run-manifest", "", None, 1],
)
def test_load_rejects_an_unknown_version(tmp_path, schema):
    document = _manifest()
    document["schema"] = schema
    with pytest.raises(runmanifest.RunManifestError) as caught:
        runmanifest.load_manifest(_raw(tmp_path, document))
    assert "version" in str(caught.value)


def test_load_rejects_a_missing_schema(tmp_path):
    document = _manifest()
    del document["schema"]
    _refused(tmp_path, document)


def test_load_rejects_an_unknown_key_at_every_level(tmp_path):
    top = _manifest()
    top["verdict"] = "pass"
    _refused(tmp_path, top, "run-top.json")

    nested = _manifest()
    nested["engine"]["rulebodyHash"] = DIGEST
    _refused(tmp_path, nested, "run-engine.json")

    row = _manifest()
    row["inputs"][0]["mtime"] = 1
    _refused(tmp_path, row, "run-row.json")

    counts = _manifest()
    counts["modelCounts"]["pins"] = 4
    _refused(tmp_path, counts, "run-counts.json")


@pytest.mark.parametrize("path", ["", "   ", "a\x00b", "../escape.epro2", "dir/", ".", 5])
def test_load_rejects_an_illegal_path(tmp_path, path):
    document = _manifest()
    document["inputs"][0]["path"] = path
    _refused(tmp_path, document)


def test_load_normalises_separators_and_feeds_them_to_the_diff(tmp_path):
    document = _manifest()
    document["inputs"][0]["path"] = "sub\\board.epro2"
    loaded = runmanifest.load_manifest(_raw(tmp_path, document))
    assert loaded["inputs"][0]["path"] == "sub/board.epro2"


@pytest.mark.parametrize("digest", ["", "abc", "A" * 63, "g" * 64, 12, None])
def test_load_rejects_an_illegal_hash(tmp_path, digest):
    document = _manifest()
    document["inputs"][0]["sha256"] = digest
    _refused(tmp_path, document)


@pytest.mark.parametrize("value", [-1, "10", True, 1.5, None])
def test_load_rejects_an_illegal_input_size(tmp_path, value):
    document = _manifest()
    document["inputs"][0]["bytes"] = value
    _refused(tmp_path, document)


@pytest.mark.parametrize("count", [0, -3, "1", True, None])
def test_load_rejects_an_illegal_drc_review_count(tmp_path, count):
    document = _manifest()
    document["drcReviewCount"] = count
    _refused(tmp_path, document)


@pytest.mark.parametrize("value", ["true", 1, 0, None])
def test_load_rejects_a_channel_that_is_not_a_boolean(tmp_path, value):
    document = _manifest()
    document["channels"]["livePcb"] = value
    _refused(tmp_path, document)


def test_load_rejects_duplicate_inputs_pages_and_finding_identities(tmp_path):
    duplicate_input = _manifest()
    duplicate_input["inputs"].append(
        {"path": "board.epro2", "bytes": 11, "sha256": DIGEST_C}
    )
    _refused(tmp_path, duplicate_input, "run-inputs.json")

    duplicate_page = _manifest(pages=["p1", "p2"])
    duplicate_page["pages"] = ["p1", "p1"]
    _refused(tmp_path, duplicate_page, "run-pages.json")

    duplicate_finding = _manifest(findings=["a:1", "b:2"])
    duplicate_finding["findings"] = ["a:1", "a:1"]
    _refused(tmp_path, duplicate_finding, "run-findings.json")


def test_load_rejects_an_empty_finding_identity(tmp_path):
    document = _manifest()
    document["findings"] = ["  "]
    _refused(tmp_path, document)


def test_every_reader_refuses_the_same_document(tmp_path):
    broken = _manifest()
    broken["schema"] = "boardwise.run-manifest/0"
    with pytest.raises(runmanifest.RunManifestError):
        runmanifest.manifest_baseline(broken)
    with pytest.raises(runmanifest.RunManifestError):
        runmanifest.semantic_diff(broken, _manifest())
    with pytest.raises(runmanifest.RunManifestError):
        runmanifest.write_manifest(tmp_path / "run.json", broken)


# --------------------------------------------------------------------------
# Baseline: evidence in, results out
# --------------------------------------------------------------------------


def test_the_baseline_holds_only_the_evidence_half():
    baseline = runmanifest.manifest_baseline(_manifest())
    assert list(baseline) == ["inputs", "engine", "intent", "channels"]
    for dropped in (
        "runId",
        "findings",
        "modelCounts",
        "drcReviewCount",
        "newEvidence",
        "pages",
        "schema",
    ):
        assert dropped not in baseline


def test_the_baseline_ignores_run_results():
    """A second run that found something new is still the same baseline."""
    old = _manifest(findings=["a:1"], drc_review_count=1, run_id="run-1")
    new = _manifest(
        findings=["a:1", "b:2"],
        drc_review_count=2,
        run_id="run-2",
        new_evidence="archive-bytes-changed",
    )
    assert runmanifest.manifest_baseline(old) == runmanifest.manifest_baseline(new)


# --------------------------------------------------------------------------
# Semantic diff: one variable, several variables, or nothing
# --------------------------------------------------------------------------


def test_an_unchanged_baseline_reports_no_attribution():
    old = _manifest()
    new = _manifest(run_id="run-2", pages=["page-uuid-2"])
    diff = runmanifest.semantic_diff(old, new)
    assert diff == {
        "sameBaseline": True,
        "inputsChanged": [],
        "coverageChanged": [],
        "addedFindings": [],
        "removedFindings": [],
        "multiVariableChange": False,
        "attribution": None,
    }


def test_finding_deltas_alone_are_not_a_baseline_change():
    old = _manifest(findings=["r1:U+|cap-missing", "r3:R4|value"])
    new = _manifest(findings=["r1:U+|cap-missing", "r9:V+|short"])
    diff = runmanifest.semantic_diff(old, new)
    assert diff["sameBaseline"] is True
    assert diff["multiVariableChange"] is False
    assert diff["attribution"] is None, "findings never become an attribution token"
    assert diff["addedFindings"] == ["r9:V+|short"]
    assert diff["removedFindings"] == ["r3:R4|value"]


def test_replacing_one_input_hash_is_exactly_one_row():
    old = _manifest()
    new = _manifest(
        inputs=[{"path": "board.epro2", "bytes": 10, "sha256": DIGEST_C}]
    )
    diff = runmanifest.semantic_diff(old, new)
    assert diff["inputsChanged"] == [
        {"path": "board.epro2", "before": DIGEST, "after": DIGEST_C}
    ]
    assert diff["sameBaseline"] is False
    assert diff["multiVariableChange"] is False
    assert diff["attribution"] == "input:board.epro2"
    assert diff["addedFindings"] == [] and diff["removedFindings"] == []


def test_an_added_or_removed_input_has_a_null_side():
    old = _manifest()
    new = _manifest(
        inputs=[
            {"path": "board.epro2", "bytes": 10, "sha256": DIGEST},
            {"path": "pcb.png", "bytes": 20, "sha256": DIGEST_C},
        ]
    )
    added = runmanifest.semantic_diff(old, new)
    assert added["inputsChanged"] == [
        {"path": "pcb.png", "before": None, "after": DIGEST_C}
    ]
    assert runmanifest.semantic_diff(new, old)["inputsChanged"] == [
        {"path": "pcb.png", "before": DIGEST_C, "after": None}
    ]


def test_two_inputs_changed_together_refuse_a_single_factor_story():
    """The archive re-export and the live page moved at once (review R1)."""
    old = _manifest(
        inputs=[
            {"path": "archive.epro2", "bytes": 10, "sha256": DIGEST},
            {"path": "live.epro2", "bytes": 20, "sha256": DIGEST_B},
        ],
        findings=["a:1"],
    )
    one_moved = _manifest(
        inputs=[
            {"path": "archive.epro2", "bytes": 11, "sha256": DIGEST_C},
            {"path": "live.epro2", "bytes": 20, "sha256": DIGEST_B},
        ],
        findings=["a:1"],
    )
    diff = runmanifest.semantic_diff(old, one_moved)
    assert [row["path"] for row in diff["inputsChanged"]] == ["archive.epro2"]
    assert diff["multiVariableChange"] is False
    assert diff["attribution"] == "input:archive.epro2"

    both_moved = _manifest(
        inputs=[
            {"path": "archive.epro2", "bytes": 11, "sha256": DIGEST_C},
            {"path": "live.epro2", "bytes": 21, "sha256": DIGEST},
        ],
        findings=["a:1", "b:2"],
    )
    diff = runmanifest.semantic_diff(old, both_moved)
    assert [row["path"] for row in diff["inputsChanged"]] == [
        "archive.epro2",
        "live.epro2",
    ]
    assert diff["sameBaseline"] is False
    assert diff["multiVariableChange"] is True
    assert diff["attribution"] == runmanifest.ATTRIBUTION_MULTI
    assert diff["attribution"] not in ("input:archive.epro2", "input:live.epro2")
    assert diff["coverageChanged"] == []
    assert diff["addedFindings"] == ["b:2"]


def test_coverage_and_inputs_moving_together_is_multi_variable():
    old = _manifest()
    new = _manifest(
        inputs=[{"path": "board.epro2", "bytes": 10, "sha256": DIGEST_C}],
        channels={"liveSchematic": True, "archivePcb": False, "livePcb": True},
    )
    diff = runmanifest.semantic_diff(old, new)
    assert diff["coverageChanged"] == ["archivePcb", "livePcb"]
    assert diff["multiVariableChange"] is True
    assert diff["attribution"] == runmanifest.ATTRIBUTION_MULTI


def test_one_channel_is_a_coverage_change_with_its_own_token():
    old = _manifest()
    new = _manifest(
        channels={"liveSchematic": True, "archivePcb": True, "livePcb": True}
    )
    diff = runmanifest.semantic_diff(old, new)
    assert diff["coverageChanged"] == ["livePcb"]
    assert diff["inputsChanged"] == []
    assert diff["sameBaseline"] is False
    assert diff["multiVariableChange"] is False
    assert diff["attribution"] == "channel:livePcb"


def test_a_missing_channel_key_reads_as_not_collected():
    old = _manifest(channels={"liveSchematic": True})
    new = _manifest(channels={"liveSchematic": True, "datasheets": False})
    assert runmanifest.semantic_diff(old, new)["sameBaseline"] is True
    new["channels"]["datasheets"] = True
    assert runmanifest.semantic_diff(old, new)["attribution"] == "channel:datasheets"


def test_the_engine_is_a_variable_of_its_own():
    old = _manifest()
    new = _manifest(
        engine={"boardwise": "0.6.0", "ruleset": "2026-12", "rulebody": "body-1"}
    )
    diff = runmanifest.semantic_diff(old, new)
    assert diff["sameBaseline"] is False
    assert diff["attribution"] == "engine:ruleset"
    assert diff["multiVariableChange"] is False


def test_the_intent_arriving_or_changing_is_one_variable():
    none_intent = _manifest(intent=None)
    with_intent = _manifest()
    diff = runmanifest.semantic_diff(none_intent, with_intent)
    assert diff["attribution"] == "intent"
    assert diff["multiVariableChange"] is False

    other = _manifest(intent={"path": "intent.json", "sha256": DIGEST_C})
    assert runmanifest.semantic_diff(with_intent, other)["attribution"] == "intent"


def test_findings_do_not_turn_one_change_into_a_multi_variable_one():
    """Findings are results: they never inflate the variable count."""
    old = _manifest(findings=[])
    new = _manifest(
        inputs=[{"path": "board.epro2", "bytes": 10, "sha256": DIGEST_C}],
        findings=["a:1", "b:2"],
    )
    diff = runmanifest.semantic_diff(old, new)
    assert diff["multiVariableChange"] is False
    assert diff["attribution"] == "input:board.epro2"
    assert diff["addedFindings"] == ["a:1", "b:2"]
    assert diff["removedFindings"] == []


def test_findings_are_compared_as_identities_not_as_messages():
    """Two defects that share a prefix are two identities, not one family.

    A rewording of the same identity is *not* a delta either: this module never
    looks inside the string.
    """
    old = _manifest(findings=["r9:U+|cap-missing"])
    new = _manifest(findings=["r9:U+|short-to-ground", "r9:V+|short-to-ground"])
    diff = runmanifest.semantic_diff(old, new)
    assert diff["addedFindings"] == ["r9:U+|short-to-ground", "r9:V+|short-to-ground"]
    assert diff["removedFindings"] == ["r9:U+|cap-missing"]

    reworded = _manifest(findings=["r9:U+|cap-missing"])
    quiet = runmanifest.semantic_diff(old, reworded)
    assert quiet["addedFindings"] == [] and quiet["removedFindings"] == []
    assert quiet["sameBaseline"] is True


def test_the_diff_does_not_mutate_its_arguments():
    old = _manifest()
    new = _manifest(
        inputs=[{"path": "board.epro2", "bytes": 10, "sha256": DIGEST_C}],
        findings=["z:9"],
        channels={"liveSchematic": False},
    )
    before = copy.deepcopy((old, new))
    runmanifest.semantic_diff(old, new)
    assert (old, new) == before


def test_the_diff_reads_two_manifests_from_disk(tmp_path):
    old_path = runmanifest.write_manifest(tmp_path / "run-old.json", _manifest())
    new_path = runmanifest.write_manifest(
        tmp_path / "run-new.json",
        _manifest(
            inputs=[{"path": "board.epro2", "bytes": 10, "sha256": DIGEST_C}],
            findings=["r9:V+|short"],
        ),
    )
    diff = runmanifest.semantic_diff(
        runmanifest.load_manifest(old_path), runmanifest.load_manifest(new_path)
    )
    assert diff["sameBaseline"] is False
    assert diff["attribution"] == "input:board.epro2"
    assert diff["removedFindings"] == ["r1:U+|cap-missing", "r3:R4|value"]
    assert diff["addedFindings"] == ["r9:V+|short"]
