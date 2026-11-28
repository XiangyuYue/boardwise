"""583: the ChangePlan loader is a **closed** schema, and its errors are named.

569-E reproduced four holes in `core/changeplan.py`; this file pins the fix, not
the hole:

* **E-01** an unknown key at the top level, in `source`, `target` or `change` (and
  in the nested blocks the readers consume) used to be accepted on read and
  silently dropped on the next `dump`. A plan is an executable document, so a key
  nobody reads is an instruction nobody executes — refused by name now.
* **E-03** a file that is not UTF-8 leaked `UnicodeDecodeError` (a `ValueError`,
  not an `OSError`) through `load`, which the documented contract says never
  happens.
* **E-04** `planVersion` is required and must be a real `int` equal to 1:
  `True`/`1.0` only compare equal to 1 by accident, and a version is a schema
  number.
* **E-08** feeding a `boardwise-layout-plan` / `boardwise-page-layout-plan` to
  this reader said "change must be a JSON object, got NoneType" instead of naming
  the document it actually got.

The negative controls matter as much as the refusals: every kind the code itself
writes (all `SUPPORTED_KINDS`, with and without the optional keys) must still
load and round-trip, and the real 016 plan on disk must round-trip **byte for
byte**.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from boardwise.core.changeplan import (
    ADD_COMPONENT_KIND,
    COMPONENT_VALUE_KIND,
    DRAW_MODULE_KIND,
    INSERT_SUBCIRCUIT_KIND,
    MOVE_BLOCK_KIND,
    PATCH_PIN_KIND,
    PLAN_VERSION,
    SUPPORTED_KINDS,
    ChangePlan,
    ChangePlanError,
)

ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 64


# --------------------------------------------------------------------------
# legal payloads, one per kind — the documents the refusals must not touch
# --------------------------------------------------------------------------


def _source(**overrides) -> dict:
    body = {
        "inputSha256": SHA,
        "projectUuid": "",
        "pageUuid": "",
        "hostVersion": "",
        "connectorVersion": "",
    }
    body.update(overrides)
    return body


def _payload(target: dict, change: dict, **overrides) -> dict:
    payload = {
        "planVersion": PLAN_VERSION,
        "source": _source(),
        "target": target,
        "change": change,
        "preconditions": [],
        "expectedPostcondition": [],
    }
    payload.update(overrides)
    return payload


def _component_value_payload() -> dict:
    return _payload(
        {"primitiveId": "", "designator": "R1", "expectedValue": "4.7k"},
        {"kind": COMPONENT_VALUE_KIND, "before": "4.7k", "after": "1k"},
    )


def _patch_pin_payload() -> dict:
    """The disconnect shape: a beforeNet, the attachment taken off, no connection."""
    return _payload(
        {"primitiveId": "", "designator": "U3", "expectedValue": "", "pin": "4"},
        {
            "kind": PATCH_PIN_KIND,
            "beforeNet": "NET1",
            "afterNet": "",
            "connections": [],
            "attachment": {"kind": "wire", "primitiveId": "w-1", "detail": "the stub",
                           "at": [330.0, 300.0]},
        },
    )


def _add_payload() -> dict:
    return _payload(
        {
            "primitiveId": "",
            "designator": "C7",
            "expectedValue": "0.1uF",
            "anchor": "U1",
            "assignedDesignator": "C7",
            "x": 0.0,
            "y": -5.0,
            "connection": "wire",
            "connectionDetail": "test",
        },
        {
            "kind": ADD_COMPONENT_KIND,
            "part": {"lcsc": "C1525", "value": "0.1uF", "footprint": ""},
            "connections": [
                {"pin": "1", "net": "VCC", "kind": "wire", "detail": "", "to": [5.0, 0.0]},
                {"pin": "2", "net": "GND", "kind": "label", "detail": ""},
            ],
            "recipeSource": "operator:C1525",
        },
    )


def _insert_payload() -> dict:
    return _payload(
        {
            "primitiveId": "",
            "designator": "U3",
            "expectedValue": "",
            "anchor": "U3",
            "anchorNet": "",
            "pin": "5",
            "x": 345.0,
            "y": 310.0,
        },
        {
            "kind": INSERT_SUBCIRCUIT_KIND,
            "template": "rc-lowpass",
            "parts": [
                {"designator": "R1", "role": "series-r", "lcsc": "C1x", "value": "1k",
                 "footprint": "", "x": 385.0, "y": 320.0, "rotation": 0},
                {"designator": "C1", "role": "shunt-c", "lcsc": "C2x", "value": "1n",
                 "footprint": "", "x": 385.0, "y": 340.0, "rotation": 0},
            ],
            "connections": [
                {"designator": "R1", "pin": "1", "net": "X", "kind": "wire",
                 "detail": "", "to": [345.0, 310.0]},
                {"designator": "R1", "pin": "2", "net": "N1", "kind": "wire",
                 "detail": "", "to": [600.0, 310.0]},
                {"designator": "C1", "pin": "1", "net": "X", "kind": "wire",
                 "detail": "", "to": [345.0, 310.0]},
                {"designator": "C1", "pin": "2", "net": "GND", "kind": "power-flag",
                 "detail": ""},
            ],
            "beforeNet": "N1",
            "attachment": {"kind": "wire", "primitiveId": "w-attach",
                           "detail": "the wire on the pin", "at": [345.0, 310.0]},
            "baselineFindings": [],
        },
    )


def _move_payload() -> dict:
    return _payload(
        {
            "primitiveId": "",
            "designator": "U1, U2",
            "expectedValue": "",
            "designators": ["U1", "U2"],
            "dx": 100.0,
            "dy": 0.0,
        },
        {
            "kind": MOVE_BLOCK_KIND,
            "moves": [
                {"designator": "U1", "primitiveId": "p-U1",
                 "from": {"x": 300.0, "y": 300.0, "rotation": 0},
                 "to": {"x": 400.0, "y": 300.0}},
                {"designator": "U2", "primitiveId": "p-U2",
                 "from": {"x": 600.0, "y": 300.0, "rotation": 0},
                 "to": {"x": 700.0, "y": 300.0}},
            ],
            "wireOps": [
                {"primitiveId": "w-1", "kind": "redraw", "net": "GROUP_NET",
                 "pointsBefore": [[300.0, 300.0], [400.0, 300.0]],
                 "pointsAfter": [[400.0, 300.0], [500.0, 300.0]]},
            ],
            "islands": [{"pin": "U1.5", "mates": ["U2.1"]}],
            "baselineFindings": ["rule|WARN|old|1|"],
        },
    )


def _draw_payload(*, optional: bool = False, moves=None) -> dict:
    """A hand-written draw-module plan: minimal by default, full when asked.

    The minimal shape is what a pre-055 document looked like (no device pair, no
    `valueKey`/`valueVisible`, no `keepNames`, no `attributeMoves`); the optional
    shape carries every key the writer only emits when the plan sets it.
    """
    part = {
        "specId": "R1",
        "designator": "R1",
        "prefix": "R",
        "lcsc": "C25744",
        "value": "1k",
        "footprint": "R0402",
        "symbolRef": "R0402",
        "symbolHash": SHA,
        "x": 100.0,
        "y": 100.0,
        "rotation": 0,
        "mirror": False,
        "pins": [
            {"number": "1", "dx": 0.0, "dy": 50.0},
            {"number": "2", "dx": 0.0, "dy": -50.0},
        ],
    }
    change = {
        "kind": DRAW_MODULE_KIND,
        "candidate": 0,
        "layoutSha256": SHA,
        "circuitSha256": SHA,
        "presentationSha256": SHA,
        "profiles": [{"symbolRef": "R0402", "geometryHash": SHA}],
        "parts": [part],
        "wires": [
            {"net": "V3", "points": [[100.0, 50.0], [100.0, 0.0]],
             "fromPin": "R1.1", "purpose": "connect"},
        ],
        "flags": [],
        "islands": [],
        "downgrades": [],
        "notes": [],
        "baselineFindings": [],
    }
    if optional:
        part.update({
            "deviceUuid": "dev-1",
            "libraryUuid": "lib-1",
            "mpn": "RC0402FR-071KL",
            "valueKey": "Value",
            "valueVisible": False,
        })
        change.update({
            "keepNames": True,
            "baseline": {
                "pageUuid": "",
                "components": ["R1"],
                "wireCount": 1,
                "netflagCount": 0,
                "netlabelCount": 0,
                "unnumberedCount": 0,
                "pinCount": 2,
                "digest": SHA,
                "findingsRead": False,
            },
        })
    if moves is not None:
        change["attributeMoves"] = moves
    return _payload(
        {"primitiveId": "", "designator": "", "expectedValue": "", "module": "divider",
         "pageUuid": ""},
        change,
    )


BUILDERS = {
    COMPONENT_VALUE_KIND: _component_value_payload,
    PATCH_PIN_KIND: _patch_pin_payload,
    ADD_COMPONENT_KIND: _add_payload,
    INSERT_SUBCIRCUIT_KIND: _insert_payload,
    MOVE_BLOCK_KIND: _move_payload,
    DRAW_MODULE_KIND: _draw_payload,
}


def _legal_payloads() -> dict[str, dict]:
    payloads = {kind: build() for kind, build in BUILDERS.items()}
    payloads[DRAW_MODULE_KIND] = _draw_payload(optional=True)
    return payloads


# --------------------------------------------------------------------------
# E-01: the schema is closed, block by block
# --------------------------------------------------------------------------


def test_the_builders_cover_every_supported_kind():
    assert set(BUILDERS) == set(SUPPORTED_KINDS)


def test_every_legal_payload_loads_and_round_trips_by_jsonable():
    for kind, payload in _legal_payloads().items():
        plan = ChangePlan.from_jsonable(payload)
        written = plan.to_jsonable()
        assert ChangePlan.from_jsonable(written).to_jsonable() == written, kind


def test_an_optional_moves_plan_loads_and_keeps_the_rows():
    moves = [
        {"moveVersion": 1, "owner": {"kind": "part", "specId": "R1"},
         "role": "reference", "to": {"x": 90.0, "y": 100.0}},
        {"moveVersion": 2, "owner": {"kind": "wire", "index": 0},
         "role": "net", "to": {"x": 100.0, "y": 40.0, "valueVisible": False}},
    ]
    plan = ChangePlan.from_jsonable(_draw_payload(moves=moves))
    assert [row.move_version for row in plan.change.attribute_moves] == [1, 2]
    written = plan.to_jsonable()
    assert written["change"]["attributeMoves"] == moves
    assert ChangePlan.from_jsonable(written).to_jsonable() == written


UNKNOWN = "thisBuildDoesNotReadIt"


@pytest.mark.parametrize("kind", sorted(BUILDERS))
@pytest.mark.parametrize("block", ["top", "source", "target", "change"])
def test_an_unknown_key_in_a_plan_block_is_refused_by_name(kind, block):
    payload = BUILDERS[kind]()
    if block == "top":
        payload[UNKNOWN] = True
        where = "$"
    else:
        payload[block][UNKNOWN] = True
        where = block
    with pytest.raises(ChangePlanError) as caught:
        ChangePlan.from_jsonable(payload)
    message = str(caught.value)
    assert UNKNOWN in message, message
    assert "unknown key" in message, message
    assert message.startswith(where), message


@pytest.mark.parametrize(
    "kind, where",
    [
        (ADD_COMPONENT_KIND, ("change", "connections", 0)),
        (ADD_COMPONENT_KIND, ("change", "part")),
        (PATCH_PIN_KIND, ("change", "connections", 0)),
        (PATCH_PIN_KIND, ("change", "attachment")),
        (INSERT_SUBCIRCUIT_KIND, ("change", "parts", 0)),
        (INSERT_SUBCIRCUIT_KIND, ("change", "connections", 1)),
        (INSERT_SUBCIRCUIT_KIND, ("change", "attachment")),
        (MOVE_BLOCK_KIND, ("change", "moves", 0)),
        (MOVE_BLOCK_KIND, ("change", "moves", 0, "from")),
        (MOVE_BLOCK_KIND, ("change", "moves", 0, "to")),
        (MOVE_BLOCK_KIND, ("change", "wireOps", 0)),
        (MOVE_BLOCK_KIND, ("change", "islands", 0)),
        (DRAW_MODULE_KIND, ("change", "profiles", 0)),
        (DRAW_MODULE_KIND, ("change", "parts", 0)),
        (DRAW_MODULE_KIND, ("change", "parts", 0, "pins", 0)),
        (DRAW_MODULE_KIND, ("change", "wires", 0)),
        (DRAW_MODULE_KIND, ("change", "islands", 0)),
    ],
)
def test_an_unknown_key_in_a_nested_block_is_refused_by_name(kind, where):
    payload = BUILDERS[kind]()
    if kind == DRAW_MODULE_KIND and "islands" in where:
        payload["change"]["islands"] = [{"pin": "R1.1", "mates": ["R1.2"]}]
    if kind == PATCH_PIN_KIND and where[:2] == ("change", "connections"):
        payload["change"]["connections"] = [
            {"pin": "5", "net": "NET2", "kind": "wire", "detail": "", "to": [1, 2]}
        ]
    node = payload
    for step in where:
        node = node[step]
    node[UNKNOWN] = True
    with pytest.raises(ChangePlanError) as caught:
        ChangePlan.from_jsonable(payload)
    message = str(caught.value)
    assert UNKNOWN in message, message
    assert "unknown key" in message, message
    assert message.startswith("change"), message


def test_a_plan_that_loads_does_not_silently_drop_unknown_keys(tmp_path):
    """The E-01 shape exactly: accept-then-drop is what made the hole invisible."""
    payload = json.loads((ROOT / "outputs" / "016_plan_r1.json").read_text("utf-8"))
    payload["dryRun"] = True
    payload["change"]["expectedWireCount"] = 3
    path = tmp_path / "edited.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ChangePlanError) as caught:
        ChangePlan.load(path)
    message = str(caught.value)
    assert "dryRun" in message and UNKNOWN not in message, message


# --------------------------------------------------------------------------
# E-03: a non-UTF-8 file is a ChangePlanError, like every other read failure
# --------------------------------------------------------------------------


def test_a_non_utf8_file_is_refused_as_a_changeplan_error(tmp_path):
    path = tmp_path / "plan.json"
    path.write_bytes(b"\xff\xfe{\"planVersion\": 1}")
    with pytest.raises(ChangePlanError) as caught:
        ChangePlan.load(path)
    message = str(caught.value)
    assert str(path) in message, message
    assert "not UTF-8" in message, message


def test_the_other_read_failures_keep_their_wording(tmp_path):
    missing = tmp_path / "nope.json"
    with pytest.raises(ChangePlanError) as caught:
        ChangePlan.load(missing)
    assert "cannot be read" in str(caught.value)

    directory = tmp_path / "dir.json"
    directory.mkdir()
    with pytest.raises(ChangePlanError) as caught:
        ChangePlan.load(directory)
    assert "cannot be read" in str(caught.value)

    broken = tmp_path / "broken.json"
    broken.write_text("{nope", encoding="utf-8")
    with pytest.raises(ChangePlanError) as caught:
        ChangePlan.load(broken)
    assert "is not JSON" in str(caught.value)


# --------------------------------------------------------------------------
# E-04: `planVersion` is an int, is present, and is this build's version
# --------------------------------------------------------------------------


@pytest.mark.parametrize("version", [True, False, 1.0, "1", None, [1], 2, 0])
def test_a_version_that_is_not_the_integer_one_is_refused(version):
    payload = _component_value_payload()
    payload["planVersion"] = version
    with pytest.raises(ChangePlanError) as caught:
        ChangePlan.from_jsonable(payload)
    assert "planVersion" in str(caught.value)


def test_a_missing_version_is_still_refused():
    payload = _component_value_payload()
    del payload["planVersion"]
    with pytest.raises(ChangePlanError) as caught:
        ChangePlan.from_jsonable(payload)
    assert "planVersion" in str(caught.value)


def test_true_is_refused_through_a_real_file_too(tmp_path):
    payload = _component_value_payload()
    payload["planVersion"] = True
    path = tmp_path / "bool-version.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ChangePlanError) as caught:
        ChangePlan.load(path)
    assert "planVersion" in str(caught.value)


# --------------------------------------------------------------------------
# E-08: a foreign plan document is named as what it is
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sample, kind",
    [
        ("cand1.layout.json", "boardwise-layout-plan"),
        ("cand1.page.json", "boardwise-page-layout-plan"),
    ],
)
def test_a_layout_document_fed_to_changeplan_is_named(sample, kind):
    path = ROOT / "outputs" / "054_drawcompile" / sample
    if not path.exists():
        pytest.skip(f"{path} is not in this checkout")
    with pytest.raises(ChangePlanError) as caught:
        ChangePlan.load(path)
    message = str(caught.value)
    assert kind in message, message
    assert "not a ChangePlan" in message, message
    assert "NoneType" not in message, message


def test_an_ordinary_missing_block_still_reads_like_a_schema_error():
    payload = _component_value_payload()
    del payload["change"]
    with pytest.raises(ChangePlanError) as caught:
        ChangePlan.from_jsonable(payload)
    assert "change must be a JSON object" in str(caught.value)


def test_an_unknown_document_without_the_changeplan_shape_is_still_refused():
    payload = {"planVersion": 1, "source": _source(), "target": {}, "kind": "whatever"}
    with pytest.raises(ChangePlanError) as caught:
        ChangePlan.from_jsonable(payload)
    message = str(caught.value)
    assert "unknown key" in message or "change must be a JSON object" in message, message


# --------------------------------------------------------------------------
# the real sample: the closed schema must not refuse the documents it wrote
# --------------------------------------------------------------------------


def test_the_real_016_plan_round_trips_byte_for_byte(tmp_path):
    source = ROOT / "outputs" / "016_plan_r1.json"
    if not source.exists():
        pytest.skip(f"{source} is not in this checkout")
    plan = ChangePlan.load(source)
    out = tmp_path / "rt.json"
    plan.dump(out)
    assert out.read_bytes() == source.read_bytes()
    assert ChangePlan.load(out).to_jsonable() == plan.to_jsonable()
