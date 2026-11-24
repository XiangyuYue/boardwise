"""585 / W-P(shared): `ChangePlan.dump` refuses an impossible target by name.

569-G-05 named two writers. 584 fixed the CLI's preflight (`_draw_output_check`),
but the plan writer itself still let `Path.write_text` raise a bare
`FileNotFoundError` / `PermissionError` / `IsADirectoryError` at any caller that
dumps a plan directly — the test suite does, and `draw plan --out` can still
race its own preflight. Every negative case here calls `dump` with no CLI in
front of it and asks for a `ChangePlanError` that names the target and the
reason (never an `OSError`), plus no half-written plan and no temporary file
left beside it.

The legal shapes are pinned in the same file, because a check that refused
everything would pass every negative case: an existing directory, an existing
file, a new file beside one, `dump` returning `None`, and the real 016
(component-value) and draw-module plans re-dumping byte for byte.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from boardwise.core.changeplan import ChangePlan, ChangePlanError

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "outputs" / "016_plan_r1.json"
DRAW_SAMPLE = ROOT / "outputs" / "054_c1" / "plan.json"
#: A draw-module plan written by the writer this batch touches (the older
#: 054_c1 sample predates `netlabelCount`/`pinCount` and never round-tripped —
#: evidence/583/roundtrip-fixed.txt lists that drift, and it is not this batch's).
DRAW_ROUND_TRIP = ROOT / "outputs" / "146" / "plan.json"


def _samples() -> list[tuple[str, Path]]:
    return [("component-value", SAMPLE), ("draw-module", DRAW_SAMPLE)]


@pytest.fixture(params=_samples(), ids=[name for name, _ in _samples()])
def plan(request) -> ChangePlan:
    """Both consumers of the write port: an edit plan and a draw-module plan."""
    _name, path = request.param
    if not path.exists():
        pytest.skip(f"{path} is not in this checkout")
    return ChangePlan.load(path)


def _temp_residue(directory: Path) -> list[str]:
    """The writer's own temporary siblings — the only thing it may ever leave."""
    if not directory.is_dir():
        return []
    return sorted(
        path.name for path in directory.iterdir() if path.name.endswith(".tmp")
    )


def _refusal(callable_) -> ChangePlanError:
    with pytest.raises(ChangePlanError) as caught:
        callable_()
    assert not isinstance(caught.value, OSError), caught.value
    return caught.value


# --------------------------------------------------- 569G-05: the four shapes


def test_585_g05_a_missing_parent_directory_is_a_named_refusal(plan, tmp_path):
    target = tmp_path / "nope" / "plan.json"
    message = str(_refusal(lambda: plan.dump(target)))
    assert str(target) in message, message
    assert "does not exist" in message, message
    assert not target.exists()
    assert not target.parent.exists(), "dump invented the directory nobody named"
    assert _temp_residue(tmp_path) == []


def test_585_g05_a_parent_that_is_a_file_is_a_named_refusal(plan, tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    target = blocker / "plan.json"
    message = str(_refusal(lambda: plan.dump(target)))
    assert str(target) in message, message
    assert "is a file, not a directory" in message, message
    assert blocker.read_text(encoding="utf-8") == "x"
    assert _temp_residue(tmp_path) == []


def test_585_g05_a_directory_target_is_a_named_refusal(plan, tmp_path):
    target = tmp_path / "outdir"
    target.mkdir()
    message = str(_refusal(lambda: plan.dump(target)))
    assert str(target) in message, message
    assert "is a directory" in message, message
    assert not message.startswith(f"{target}: cannot be written"), (
        "the refusal came from the write, not from a check made before it: "
        + message
    )
    assert list(target.iterdir()) == []
    assert _temp_residue(tmp_path) == []


def test_585_g05_a_write_failure_is_named_and_leaves_no_half_plan(
    plan, tmp_path, monkeypatch
):
    """The check can pass and the write still fail (a volume that says no).

    `os.replace` is the last step of the sibling-temp writer; exploding it is
    the narrowest way to make the *write* fail while the target stays legal.
    """
    target = tmp_path / "plan.json"
    target.write_text("previous\n", encoding="utf-8")
    original = os.replace

    def explode(src, dst):
        raise OSError("synthetic dump rename")

    monkeypatch.setattr(os, "replace", explode)
    message = str(_refusal(lambda: plan.dump(target)))
    monkeypatch.setattr(os, "replace", original)
    assert str(target) in message, message
    assert "cannot be written" in message, message
    assert "synthetic dump rename" in message, message
    assert target.read_text(encoding="utf-8") == "previous\n", "a half plan landed"
    assert _temp_residue(tmp_path) == [], "the temporary file survived the failure"


# ------------------------------------------------- the legal shapes are untouched


def test_585_the_legal_shapes_still_write_and_return_none(plan, tmp_path):
    existing_dir = tmp_path / "existing"
    existing_dir.mkdir()
    beside = existing_dir / "plan.json"
    assert plan.dump(beside) is None
    assert ChangePlan.load(beside).to_jsonable() == plan.to_jsonable()

    replaced = tmp_path / "replaced.json"
    replaced.write_text("{}\n", encoding="utf-8")
    assert plan.dump(replaced) is None
    assert ChangePlan.load(replaced).to_jsonable() == plan.to_jsonable()
    assert _temp_residue(tmp_path) == []
    assert _temp_residue(existing_dir) == []


@pytest.mark.parametrize(
    "name,path",
    [("component-value", SAMPLE), ("draw-module", DRAW_ROUND_TRIP)],
)
def test_585_the_real_plans_round_trip_byte_for_byte(name, path, tmp_path):
    if not path.exists():
        pytest.skip(f"{path} is not in this checkout")
    plan = ChangePlan.load(path)
    out = tmp_path / f"{name}.json"
    plan.dump(out)
    assert out.read_bytes() == path.read_bytes(), name
    assert ChangePlan.load(out).to_jsonable() == plan.to_jsonable()
