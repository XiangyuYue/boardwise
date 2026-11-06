"""540C: the fixture generator gates every payload on its real schema, strictly.

The regression this file pins: after the generator was made in-memory, it read
producer JSON with plain ``json.loads`` and projected without ``assert_valid`` — so a
contract-invalid or non-finite producer output could be published as golden. Every
read now goes through :mod:`tools.contract_validate`'s strict loader, and every
payload is validated against ``tools.differential.SCHEMAS[kind]`` before projection.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools import build_differential_fixtures as fixtures
from tools.contract_validate import ContractValidationError, load_path, loads_strict
from tools.differential import SCHEMAS

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts" / "differential"
INPUTS = CONTRACTS / "inputs"
#: Every published input, keyed by case id — the two `epru-stream-sample` cases
#: and the two `symbol-library-sample` cases share one kind each, so their keys
#: are ids rather than kind names.
GOLDEN_INPUTS = {
    "review-report-projection": INPUTS / "review-report.json",
    "layout-plan-geometry": INPUTS / "divider-cand1.layout.json",
    "compile-result-projection": INPUTS / "divider-compile-result.json",
    "compile-page-result-projection": INPUTS / "page-compile-result.json",
    "lint-result-projection": INPUTS / "empty-page-lint-result.json",
    "epru-stream-v3-eof": INPUTS / "epru-stream-v3-eof.json",
    "epru-stream-v4-eof-truncated": INPUTS / "epru-stream-v4-eof-truncated.json",
    "symbol-library-v3-zindex": INPUTS / "symbol-library-v3-zindex.json",
    "symbol-library-v4-pin-id": INPUTS / "symbol-library-v4-pin-id.json",
    "device-library-v3-meta": INPUTS / "device-library-v3-meta.json",
    "device-library-v4-copies": INPUTS / "device-library-v4-copies.json",
    "footprint-library-v3-title": INPUTS / "footprint-library-v3-title.json",
    "footprint-library-v4-copies": INPUTS / "footprint-library-v4-copies.json",
    "footprint-declared-v3-hit": INPUTS / "footprint-declared-v3-hit.json",
    "footprint-declared-v4-empty": INPUTS / "footprint-declared-v4-empty.json",
}


def _redirect(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(fixtures, "INPUTS", tmp_path / "inputs")
    monkeypatch.setattr(fixtures, "CASES", tmp_path / "cases.json")
    monkeypatch.setattr(fixtures, "MANIFEST", tmp_path / "manifest.json")


def _assert_nothing_published(tmp_path: Path) -> None:
    assert not (tmp_path / "inputs").exists()
    assert not (tmp_path / "cases.json").exists()
    assert not (tmp_path / "manifest.json").exists()


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity", "1e999"])
def test_strict_loader_rejects_non_finite_numbers(token: str) -> None:
    with pytest.raises(ContractValidationError, match="non-finite"):
        loads_strict('{"probe": %s}' % token)


def test_strict_loader_accepts_a_normal_document(tmp_path: Path) -> None:
    path = tmp_path / "ok.json"
    path.write_text('{"probe": 1.5, "count": 2}', encoding="utf-8")
    assert load_path(path) == {"probe": 1.5, "count": 2}


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity", "1e999"])
def test_a_non_finite_producer_file_publishes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, token: str
) -> None:
    _redirect(monkeypatch, tmp_path)
    poisoned = tmp_path / "review-report.json"
    poisoned.write_text('{"probe": %s}' % token, encoding="utf-8")
    produced = dict(GOLDEN_INPUTS)
    produced["review-report-projection"] = poisoned
    with pytest.raises(ContractValidationError, match="non-finite"):
        fixtures._regenerate(produced)
    _assert_nothing_published(tmp_path)


def test_a_contract_invalid_producer_file_publishes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A violation the old projection-only path accepted: `command` is a const."""
    _redirect(monkeypatch, tmp_path)
    compile_result = json.loads(GOLDEN_INPUTS["compile-result-projection"].read_text(encoding="utf-8"))
    compile_result["command"] = "lint"
    poisoned = tmp_path / "compile-result.json"
    poisoned.write_text(json.dumps(compile_result, ensure_ascii=False), encoding="utf-8")
    produced = dict(GOLDEN_INPUTS)
    produced["compile-result-projection"] = poisoned
    with pytest.raises(ContractValidationError) as error:
        fixtures._regenerate(produced)
    assert "expected const 'compile'" in str(error.value)
    _assert_nothing_published(tmp_path)


def test_a_page_document_that_states_another_document_publishes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The page case is gated by its own contract: a producer output that flips
    `document` back to a module cannot be published as a page golden."""
    _redirect(monkeypatch, tmp_path)
    page_result = json.loads(
        GOLDEN_INPUTS["compile-page-result-projection"].read_text(encoding="utf-8")
    )
    page_result["document"] = "module"
    poisoned = tmp_path / "page-compile-result.json"
    poisoned.write_text(json.dumps(page_result, ensure_ascii=False), encoding="utf-8")
    produced = dict(GOLDEN_INPUTS)
    produced["compile-page-result-projection"] = poisoned
    with pytest.raises(ContractValidationError) as error:
        fixtures._regenerate(produced)
    assert "expected const 'page'" in str(error.value)
    _assert_nothing_published(tmp_path)


def test_a_schema_invalid_report_publishes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _redirect(monkeypatch, tmp_path)
    report = json.loads(GOLDEN_INPUTS["review-report-projection"].read_text(encoding="utf-8"))
    report["summary"]["exitCode"] = 4  # the schema's enum is [0, 1, 2, 3]
    poisoned = tmp_path / "review-report.json"
    poisoned.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    produced = dict(GOLDEN_INPUTS)
    produced["review-report-projection"] = poisoned
    with pytest.raises(ContractValidationError) as error:
        fixtures._regenerate(produced)
    assert "summary.exitCode" in str(error.value)
    _assert_nothing_published(tmp_path)


def test_every_read_goes_through_the_strict_loader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[str] = []
    real = fixtures.load_path

    def spy(path: object) -> object:
        seen.append(str(path))
        return real(path)

    monkeypatch.setattr(fixtures, "load_path", spy)
    _redirect(monkeypatch, tmp_path)
    fixtures._render(GOLDEN_INPUTS)
    for name in SCHEMAS.values():
        assert any(path.endswith(name) for path in seen), name
    for path in GOLDEN_INPUTS.values():
        assert any(seen_path.endswith(path.name) for seen_path in seen), path.name


def test_validation_runs_before_projection(monkeypatch: pytest.MonkeyPatch) -> None:
    order: list[str] = []
    real_project = fixtures.project_payload

    def validate_spy(instance: object, schema: object) -> None:
        order.append("validate")

    def project_spy(kind: str, payload: object) -> dict:
        order.append("project")
        return real_project(kind, payload)

    monkeypatch.setattr(fixtures, "assert_valid", validate_spy)
    monkeypatch.setattr(fixtures, "project_payload", project_spy)
    fixtures._render(GOLDEN_INPUTS)
    assert order == ["validate", "project"] * len(GOLDEN_INPUTS)


def test_valid_public_inputs_still_publish_identical_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The new gate must not change a single byte of the current golden."""
    _redirect(monkeypatch, tmp_path)
    fixtures._publish(fixtures._render(GOLDEN_INPUTS))
    for name in fixtures.INPUT_NAMES.values():
        assert (tmp_path / "inputs" / name).read_bytes() == (INPUTS / name).read_bytes()
    assert (tmp_path / "cases.json").read_bytes() == (CONTRACTS / "cases.json").read_bytes()
    assert (tmp_path / "manifest.json").read_bytes() == (CONTRACTS / "manifest.json").read_bytes()


def test_manifest_schema_hashes_still_match_the_files_it_validates_with() -> None:
    manifest = json.loads((CONTRACTS / "manifest.json").read_text(encoding="utf-8"))
    for name in SCHEMAS.values():
        relative = f"contracts/json/{name}"
        assert manifest["schemas"][relative] == hashlib.sha256(
            (ROOT / relative).read_bytes()
        ).hexdigest()


# ---------------------------------------------------------------------------
# 038X made the checkout's default shelf an absolute path; the golden may not
# carry it. These are the negative controls for that: the default shelf and the
# checkout root publish as placeholders, and anything else absolute is refused.
# ---------------------------------------------------------------------------


def _published_text(payload: object) -> str:
    return json.dumps(fixtures._sanitize(payload), ensure_ascii=False)


def test_the_default_checkout_shelf_publishes_by_its_repository_relative_name() -> None:
    """`shelfPath` is a location, and a location on *this* machine is not a golden.

    038X (``rules/facts.py``) made the checkout default
    ``<this checkout>/blocklib/parts.json``; it used to be the repository-relative
    ``blocklib/parts.json``, resolved against the working directory. Publishing
    the absolute spelling would have changed a byte of the golden and named
    ``E:/boardwise`` — the exact failure the generator now refuses to publish.
    """
    absolute_default = str(fixtures.ROOT / fixtures.DEFAULT_SHELF)
    assert absolute_default != fixtures.DEFAULT_SHELF  # the input is really absolute
    published = fixtures._sanitize({"shelfPath": absolute_default})
    assert published == {"shelfPath": "blocklib/parts.json"}
    fixtures._assert_clean("default shelf", _published_text(published))


def test_the_checkout_root_in_free_text_publishes_as_a_placeholder() -> None:
    """Free text is where the root leaks: 038X's triage note prints paths."""
    note = f"curate the shelf, then re-run against {fixtures.ROOT}/blocklib/parts.json"
    published = fixtures._sanitize({"source": {"notes": [note]}})
    text = _published_text(published)
    assert text.count("<REPO>/blocklib/parts.json") == 1
    for marker in fixtures._forbidden_markers():
        assert marker not in text, marker
    assert not fixtures.RESIDUAL_ABSOLUTE_PATH.search(text)
    fixtures._assert_clean("checkout root in a note", text)


@pytest.mark.parametrize(
    "explicit",
    ["D:/elsewhere/parts.json", "/home/someone/parts.json", "F:\\shelves\\parts.json"],
)
def test_another_absolute_shelf_path_is_refused_rather_than_rewritten(
    explicit: str,
) -> None:
    """An explicit `--library` is the caller's own string, so it is never guessed.

    The path is sanitized like any other text and then **refused** by the same net
    that guards every artifact: publishing it would name a file that exists on one
    machine only, and rewriting it into `blocklib/parts.json` would state a shelf
    the run did not read.
    """
    published = fixtures._sanitize({"shelfPath": explicit})
    assert published == {"shelfPath": explicit.replace("\\", "/")}
    with pytest.raises(RuntimeError, match="residual absolute path"):
        fixtures._assert_clean("explicit shelf", _published_text(published))


def test_a_repository_relative_shelf_path_passes_through_verbatim() -> None:
    """The default's *name*, and any other relative spelling, is already publishable."""
    for shelf in (fixtures.DEFAULT_SHELF, "shelves/my-parts.json"):
        published = fixtures._sanitize({"shelfPath": shelf})
        assert published == {"shelfPath": shelf}
        fixtures._assert_clean("relative shelf", _published_text(published))


def test_an_absolute_default_shelf_and_a_root_note_still_render_a_clean_report(
    tmp_path: Path,
) -> None:
    """End to end on the real report shape, which is what the generator renders.

    The producer now states an absolute shelf and can print the checkout root in
    `source.notes`; `_render` has to answer both without naming this machine and
    without touching any other field.
    """
    report = json.loads(
        GOLDEN_INPUTS["review-report-projection"].read_text(encoding="utf-8")
    )
    report["shelfPath"] = str(fixtures.ROOT / fixtures.DEFAULT_SHELF)
    report["source"]["notes"].append(
        f"the shelf read by this run: {fixtures.ROOT}/blocklib/parts.json"
    )
    poisoned = tmp_path / "review-report.json"
    poisoned.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    produced = dict(GOLDEN_INPUTS)
    produced["review-report-projection"] = poisoned

    rendered = fixtures._render(produced)
    text = rendered[INPUTS / "review-report.json"]
    assert json.loads(text)["shelfPath"] == fixtures.DEFAULT_SHELF
    assert f"<REPO>/{fixtures.DEFAULT_SHELF}" in text
    assert not fixtures.RESIDUAL_ABSOLUTE_PATH.search(text)
    for marker in fixtures._forbidden_markers():
        assert marker not in text, marker
