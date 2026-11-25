"""604: V4 facts evidence metadata — page unit, generator, pose coverage.

Three things are pinned here and nothing else:

* **the pair of file frames**. A V4 `up` file stores cartesian y and carries the
  marker; the loader flips it once into the V3 stored frame, and ``page_y``
  negates that stored y once into canvas. Deleting the marker from an `up` file
  does not produce the same circuit (the record becomes a `down` one), so the
  proof has to be a **pair**: the same part written as stored ``-500`` without a
  marker and as raw ``+500`` with one must land on the same canvas pose;
* **the facts meta says what it means**: generator (module + package version),
  the instance pose count, and the page unit (10 mil);
* **a legacy product is refused by name**. A ``boardwise.v4-facts/1`` document
  written before the generator/pose fields existed cannot be told apart from a
  project whose parts declare no pose, so deriving presentation evidence from
  it raises instead of silently reporting "no pose".
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import boardwise
from boardwise.engines.v4facts import (
    SCHEMA,
    presentation_evidence,
    read_v4_facts,
)
from boardwise.parsers.schematic import collect_page_layout

VERSION = boardwise.__version__

#: What one page unit means, stated by the product itself (A4 = 1170x825 page
#: units = 297x210 mm, so one unit is 10 mil — a reader must not have to guess).
PAGE_UNIT = "page-unit (10 mil)"


# --------------------------------------------------------------------------
# a minimal V4 folder writer: the same circuit in either file frame
# --------------------------------------------------------------------------


def _record(envelope: dict, body: dict | None = None) -> str:
    head = json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))
    if body is None:
        return head + "|||"
    return head + "||" + json.dumps(body, ensure_ascii=False, separators=(",", ":")) + "|"


def _symbol() -> list[str]:
    out = [
        _record({"type": "DOCHEAD"}, {"docType": "SYMBOL", "uuid": "sym-1"}),
        _record({"type": "META", "id": "META"}, {"title": "R", "docType": "SYMBOL"}),
    ]
    for index, (number, x) in enumerate((("1", 0.0), ("2", 20.0))):
        pin_id = f"e{index + 1}"
        out.append(_record({"type": "PIN", "id": pin_id},
                           {"x": x, "y": 0.0, "zIndex": index + 2}))
        out.append(_record({"type": "ATTR", "id": f"n{index}"},
                           {"parentId": pin_id, "key": "Pin Number",
                            "value": number}))
    return out


def _page(*, y_up: bool, components: list[dict]) -> list[str]:
    """One component page in either frame.

    ``marker`` is the file's own ``yAxisDirection`` — the only thing that makes
    a coordinate cartesian. ``y`` is what the file literally stores: a `down` (or
    markerless) file stores canvas y negated, an `up` file stores it as written.
    """
    marker = {"yAxisDirection": "up"} if y_up else {}

    def stored(canvas_y: float) -> float:
        return canvas_y if y_up else -canvas_y

    out = [_record({"type": "DOCHEAD", **marker},
                   {"docType": "SCH_PAGE", "uuid": "page-1"})]
    out += _symbol()
    for part, body in components:
        payload = dict(body)
        if "y" in payload:
            payload["y"] = stored(payload["y"])
        out.append(_record({"type": "COMPONENT", "id": f"c-{part}", **marker},
                           {"partId": part, "rotation": 0, "isMirror": False,
                            "zIndex": 10, **payload}))
        out.append(_record({"type": "ATTR", "id": f"d-{part}"},
                           {"parentId": part, "key": "Designator", "value": part}))
        out.append(_record({"type": "ATTR", "id": f"s-{part}"},
                           {"parentId": part, "key": "Symbol", "value": "sym-1"}))
    return out


def _write(root: Path, *, y_up: bool, components: list[dict]) -> Path:
    page_dir = root / "sch" / "Schematic1"
    page_dir.mkdir(parents=True, exist_ok=True)
    (root / f"{root.name}.eprj3").write_text(json.dumps({
        "name": root.name,
        "owner_uuid": "0123456789abcdef0123456789abcdef",
        "format": "folder",
        "profile": {"schematics": {}, "sheets": {}, "pcbs": {}},
    }, ensure_ascii=False), encoding="utf-8")
    (page_dir / "P1.esch2").write_text(
        "\n".join(_page(y_up=y_up, components=components)) + "\n",
        encoding="utf-8",
    )
    return root


#: One part, canvas pose ``(300, 500)`` — the number the two frames must agree on.
POSE = [("U1", {"x": 300.0, "y": 500.0})]

#: A posed part, a part with no declared pose, and one whose x is a bool (JSON
#: ``true`` is an ``int`` in Python, but it is not a measured coordinate).
MIXED = [
    ("U1", {"x": 300.0, "y": 500.0}),
    ("U2", {}),
    ("U3", {"x": True, "y": 500.0}),
]


# --------------------------------------------------------------------------
# 1. H1, by the format's own pair: up file and down file, one circuit
# --------------------------------------------------------------------------


def test_the_down_file_stores_minus_500_and_the_up_file_stores_plus_500(tmp_path):
    """The premise of the pair, read straight off the written files."""
    down = _write(tmp_path / "down", y_up=False, components=POSE)
    up = _write(tmp_path / "up", y_up=True, components=POSE)
    page_down = (down / "sch" / "Schematic1" / "P1.esch2").read_text(encoding="utf-8")
    page_up = (up / "sch" / "Schematic1" / "P1.esch2").read_text(encoding="utf-8")
    component_down = json.loads(
        [line for line in page_down.splitlines() if '"COMPONENT"' in line][0]
        .split("||", 1)[1][:-1]
    )
    component_up = json.loads(
        [line for line in page_up.splitlines() if '"COMPONENT"' in line][0]
        .split("||", 1)[1][:-1]
    )
    assert component_down["y"] == -500.0 and "yAxisDirection" not in page_down
    assert component_up["y"] == +500.0 and '"yAxisDirection":"up"' in page_up
    assert component_down["x"] == component_up["x"] == 300.0


def test_up_and_down_files_give_the_same_canvas_pose(tmp_path):
    """The proof H1's original probe lacked: a **pair**, not a stripped marker.

    Deleting the `up` marker while keeping ``+500`` would describe another
    circuit (a `down` record at ``+500``), so "still 500" says nothing. The two
    files below are the same circuit in the two frames, and both readings — the
    facts reader and the shared page layout — must give canvas ``(300, 500)``.
    """
    down = _write(tmp_path / "down", y_up=False, components=POSE)
    up = _write(tmp_path / "up", y_up=True, components=POSE)

    poses = {}
    layouts = {}
    for name, path in (("down", down), ("up", up)):
        instance = read_v4_facts(path)["instances"][0]
        poses[name] = (instance["x"], instance["y"])
        layouts[name] = [
            (part.designator, round(part.x, 3), round(part.y, 3))
            for part in collect_page_layout(path).parts or []
        ]

    assert poses == {"down": (300.0, 500.0), "up": (300.0, 500.0)}
    assert layouts["down"] == layouts["up"] == [("U1", 300.0, 500.0)]


def test_a_markerless_file_is_a_down_file_for_the_pose_too(tmp_path):
    """The spec's rule at the pose: no marker means `down`, so ``-500`` → 500."""
    plain = _write(tmp_path / "plain", y_up=False, components=POSE)
    facts = read_v4_facts(plain)
    assert (facts["instances"][0]["x"], facts["instances"][0]["y"]) == (300.0, 500.0)


# --------------------------------------------------------------------------
# 2. H2/H3, the facts meta: generator, pose coverage, page unit
# --------------------------------------------------------------------------


def test_meta_names_the_generator_and_the_page_unit(tmp_path):
    facts = read_v4_facts(_write(tmp_path / "down", y_up=False, components=POSE))
    meta = facts["meta"]
    assert facts["schema"] == SCHEMA
    assert "boardwise.v4facts" in meta["generator"]
    assert VERSION in meta["generator"], (
        "a product without its package version cannot be told from another build"
    )
    assert meta["units"] == PAGE_UNIT


def test_instances_with_pose_counts_only_finite_numeric_pairs(tmp_path):
    """U1 is posed, U2 declares nothing, U3's x is a bool — count 1, not 3."""
    facts = read_v4_facts(_write(tmp_path / "mixed", y_up=False, components=MIXED))
    by_part = {instance["partId"]: instance for instance in facts["instances"]}
    assert facts["meta"]["instancesWithPose"] == 1
    assert (by_part["U1"]["x"], by_part["U1"]["y"]) == (300.0, 500.0)
    assert "x" not in by_part["U2"] and "y" not in by_part["U2"], (
        "an unposed part must keep the axes absent, never a fabricated 0"
    )


def test_the_fixture_project_reports_all_of_its_instances_as_posed():
    facts = read_v4_facts(Path(__file__).parent / "fixtures" / "eprj3_synth")
    declared = [instance for instance in facts["instances"]
                if "x" in instance and "y" in instance]
    assert facts["meta"]["instancesWithPose"] == len(declared) > 0


# --------------------------------------------------------------------------
# 3. legacy products are refused by name, new ones derive as before
# --------------------------------------------------------------------------


def _legacy(facts: dict, drop: str = "generator") -> dict:
    legacy = copy.deepcopy(facts)
    legacy["meta"].pop(drop, None)
    return legacy


@pytest.mark.parametrize("drop", ["generator", "instancesWithPose"])
def test_a_legacy_product_without_metadata_is_refused_by_name(tmp_path, drop):
    facts = read_v4_facts(_write(tmp_path / "down", y_up=False, components=POSE))
    with pytest.raises(ValueError) as caught:
        presentation_evidence(_legacy(facts, drop))
    message = str(caught.value)
    assert "generator" in message or "legacy" in message
    assert "draw v4-facts" in message, (
        "the refusal has to say how to get a product the reader can trust"
    )


def test_legacy_facts_never_derive_a_zero_pose_evidence(tmp_path):
    """The failure H2 named: old products used to read as "no part has a pose"."""
    facts = read_v4_facts(_write(tmp_path / "down", y_up=False, components=POSE))
    with pytest.raises(ValueError):
        presentation_evidence(_legacy(facts))
    # The control: the same facts with their metadata derive normally.
    evidence = presentation_evidence(facts)
    assert evidence["pageGroups"][0]["instances"][0]["x"] == 300.0


def test_evidence_carries_the_same_source_meta(tmp_path):
    facts = read_v4_facts(_write(tmp_path / "down", y_up=False, components=POSE))
    evidence = presentation_evidence(facts)
    assert evidence["sourceMeta"]["generator"] == facts["meta"]["generator"]
    assert evidence["sourceMeta"]["units"] == PAGE_UNIT
    assert evidence["sourceMeta"]["instancesWithPose"] == 1


def test_evidence_notes_state_both_coordinate_layers(tmp_path):
    """The old note claimed "v4facts converts exactly once" and hid the loader.

    The reader's own step is legitimately "exactly once"; what must not be
    missing is the layer before it, so the note that says ``page_y`` has to name
    eprj3's up -> stored flip in the same breath.
    """
    facts = read_v4_facts(_write(tmp_path / "down", y_up=False, components=POSE))
    notes = presentation_evidence(facts)["notes"]
    stage = next(note for note in notes if "page_y" in note)
    assert "eprj3" in stage and "stored" in stage, (
        "the note must name the loader's up -> stored flip before claiming one step"
    )
    assert "two layers" in stage, (
        "the note has to say this reader's step is the second of two"
    )
    assert PAGE_UNIT in " ".join(notes)


def test_a_document_that_is_not_v4_facts_keeps_the_old_behaviour():
    """No widening: the legacy refusal is a v4-facts contract, not a schema check."""
    evidence = presentation_evidence({"schema": "other/1", "pages": []})
    assert evidence["pageGroups"] == []
