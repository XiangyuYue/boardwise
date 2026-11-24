"""593 / W-L: the lint's replay input and its skipped conclusions.

Four truth gaps closed here, all offline (no daemon, no bridge, no editor):

* 569G-07 — `draw lint --snapshot` used to take "the file parsed" for "there is
  a page here": `{}`, `{"primitives": "notalist"}`, string coordinates and NaN
  coordinates all printed `0 error / 0 warn / 0 info` and exited 0. A replay
  dump is now shape-checked once, before any predicate runs: bad root,
  containers, entries/states, non-finite coordinates or no geometry at all is
  exit 2 with a named reason.
* 565-S6-H3 — `--bodies` is the probe's **wrapped** `{"bboxes": {…}}` document
  (what `sch.geometry --params {"bboxIds": …}` prints) or a bare mapping, and
  every unreadable box is refused by name instead of silently becoming 0 boxes.
* 565-S2-H1/H7 — a run without a netlist, or without measured bodies covering
  every part, names the predicates that did not run (stdout and JSON) and is
  never called clean.
* The other direction: a page whose render parsed, whose netlist ran and whose
  bodies cover every part keeps the exact sentence and exit it had before.
"""

from __future__ import annotations

import json

import pytest

from boardwise import cli
from boardwise.engines import drawlint


# ---------------------------------------------------------------------------
# shared fixtures: a replay dump, a netlist answer, the CLI argv
# ---------------------------------------------------------------------------


def _page(*, parts=(), wires=(), netflags=()) -> dict:
    """A `sch.geometry` dump in the measured shape (111/163b's helper shape)."""
    return {
        "components": [
            {"primitiveId": "",
             "state": {"ComponentType": "sheet", "Designator": "", "X": 0, "Y": 0}},
        ] + [
            {"primitiveId": primitive,
             "state": {"ComponentType": "part", "Designator": designator,
                       "X": x, "Y": y, "Rotation": rotation, "Mirror": False}}
            for designator, primitive, x, y, rotation in parts
        ] + [
            {"primitiveId": f"flag-{index}",
             "state": {"ComponentType": "netflag", "Designator": None, "Net": net,
                       "X": x, "Y": y, "Rotation": 0}}
            for index, (net, x, y) in enumerate(netflags)
        ],
        "wires": [
            {"primitiveId": primitive,
             "state": {"Line": [c for point in points for c in point], "Net": net}}
            for primitive, net, points in wires
        ],
        "netlabels": [],
        "pins": [],
        "meta": {"available": {"components": True, "wires": True}},
    }


def _netlist(components: dict[str, dict[int, tuple[str, str]]]) -> dict:
    """An `sch.netlist` answer: {type, text} with the host's EasyEDA shape."""
    body = {}
    for index, (designator, pins) in enumerate(components.items()):
        body[f"gge{index}"] = {
            "props": {"Designator": designator},
            "pinInfoMap": {
                str(number): {"name": name, "number": str(number), "net": net}
                for number, (name, net) in pins.items()
            },
        }
    return {"type": "EasyEDA", "text": json.dumps({"components": body})}


CLEAN_NETLIST = _netlist({"U1": {1: ("1", "VIN"), 2: ("2", "VOUT")}})
READABLE_RENDER = '<svg><text style="fill:#0000FF" x="10" y="-10">VCC</text></svg>'


def _args(*extra: str):
    return cli.build_parser().parse_args(["draw", "lint", *extra])


def _write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# 569G-07 — a replay snapshot that is not a page is exit 2, never a clean bill
# ---------------------------------------------------------------------------


BAD_SNAPSHOTS = {
    "empty-object": {},
    "unknown-keys-only": {"primitives": "notalist"},
    "empty-containers": {"components": [], "wires": [], "pins": [], "netlabels": []},
}


@pytest.mark.parametrize("name", sorted(BAD_SNAPSHOTS))
def test_a_snapshot_with_no_page_is_refused(tmp_path, capsys, name):
    snap = _write_json(tmp_path / f"{name}.json", BAD_SNAPSHOTS[name])
    report = tmp_path / "report.json"
    assert cli._cmd_draw_lint(_args(
        "--snapshot", str(snap), "--json", str(report),
    )) == 2
    err = capsys.readouterr().err
    assert "no geometry to inspect" in err
    assert "Traceback" not in err
    assert not report.exists(), "a refused snapshot must not write a clean report"


def test_a_snapshot_whose_root_is_not_an_object_is_refused(tmp_path, capsys):
    snap = _write_json(tmp_path / "root.json", [{"components": []}])
    assert cli._cmd_draw_lint(_args("--snapshot", str(snap))) == 2
    err = capsys.readouterr().err
    assert "root is not a JSON object" in err
    assert "Traceback" not in err


BAD_CONTAINERS = {
    "components-is-a-string": {"components": "nope"},
    "wires-is-an-object": {"components": [], "wires": {}},
    "pins-is-a-string": {"components": [{"state": {}}], "pins": "nope"},
    "netlabels-is-an-object": {"components": [{"state": {}}], "netlabels": {}},
    "bboxes-is-a-list": {"components": [{"state": {}}], "bboxes": []},
    "meta-is-a-list": {"components": [{"state": {}}], "meta": []},
}


@pytest.mark.parametrize("name", sorted(BAD_CONTAINERS))
def test_a_snapshot_with_a_wrong_container_type_is_refused(tmp_path, capsys, name):
    snap = _write_json(tmp_path / f"{name}.json", BAD_CONTAINERS[name])
    assert cli._cmd_draw_lint(_args("--snapshot", str(snap))) == 2
    err = capsys.readouterr().err
    key = name.split("-is-")[0]
    assert key in err
    assert "not a list" in err or "not an object" in err
    assert "Traceback" not in err


BAD_ENTRIES = {
    "component-entry": {"components": [42]},
    "component-state": {"components": [{"primitiveId": "p", "state": []}]},
    "wire-entry": {"components": [], "wires": ["w"]},
    "wire-state": {"components": [], "wires": [{"primitiveId": "w", "state": 7}]},
    "pin-entry": {"components": [{"state": {}}], "pins": [1.5]},
    "netlabel-entry": {"components": [{"state": {}}], "netlabels": ["l"]},
}


@pytest.mark.parametrize("name", sorted(BAD_ENTRIES))
def test_a_snapshot_with_a_wrong_entry_shape_is_refused(tmp_path, capsys, name):
    snap = _write_json(tmp_path / f"{name}.json", BAD_ENTRIES[name])
    assert cli._cmd_draw_lint(_args("--snapshot", str(snap))) == 2
    err = capsys.readouterr().err
    assert "is not an object" in err
    assert "Traceback" not in err


@pytest.mark.parametrize(
    "snapshot, needle",
    [
        ({"components": [{"state": {"ComponentType": "part", "X": "10", "Y": 20}}]},
         "X='10'"),
        ({"components": [{"state": {"ComponentType": "part", "X": float("nan")}}]},
         "is not a finite number"),
        ({"components": [{"state": {"ComponentType": "part", "Rotation": float("inf")}}]},
         "Rotation=inf"),
        ({"components": [], "wires": [{"state": {"Line": ["1", 2]}}]},
         "Line holds '1'"),
        ({"components": [], "wires": [{"state": {"Line": [0, float("nan")]}}]},
         "not a finite number"),
        ({"components": [{"state": {}}],
          "bboxes": {"s": {"minX": "0", "minY": 0, "maxX": 10, "maxY": 10}}},
         "minX='0'"),
        ({"components": [{"state": {}}],
          "bboxes": {"s": [0, 0, float("inf"), 10]}},
         "not a finite number"),
        ({"components": [{"state": {}}], "bboxes": {"s": [0, 0, 10]}},
         "is not a box"),
    ],
)
def test_a_snapshot_with_unreadable_coordinates_is_refused(
    tmp_path, capsys, snapshot, needle
):
    snap = _write_json(tmp_path / "coords.json", snapshot)
    assert cli._cmd_draw_lint(_args("--snapshot", str(snap))) == 2
    err = capsys.readouterr().err
    assert needle in err
    assert "Traceback" not in err


def test_a_well_formed_snapshot_still_lints(tmp_path, capsys):
    """The other direction: the shape check must not refuse a real page."""
    snap = _write_json(
        tmp_path / "ok.json",
        _page(wires=[("wSIG", "SIG", ((100, 100), (200, 100)))]),
    )
    assert cli._cmd_draw_lint(_args("--snapshot", str(snap))) == 0
    out = capsys.readouterr().out
    assert "0 error / 0 warn / 0 info" in out


# ---------------------------------------------------------------------------
# 565-S6-H3 — the wrapped/bare bodies mapping, and named box refusals
# ---------------------------------------------------------------------------


def test_the_wrapped_bboxes_probe_answer_is_unwrapped():
    """`sch.geometry --params {"bboxIds": …}` prints `{"bboxes": {…}, "meta": …}`
    and that whole document used to become 0 boxes (136 ERROR → 0 ERROR)."""
    boxes = cli._draw_lint_body_boxes(
        {"bboxes": {"p1": [0, 0, 10, 10]},
         "meta": {"available": {"bboxes": True}}}
    )
    assert boxes == {"p1": (0.0, 0.0, 10.0, 10.0)}


def test_both_box_shapes_are_read_from_a_bare_mapping():
    boxes = cli._draw_lint_body_boxes(
        {"p1": [0, 0, 10, 10],
         "p2": {"minX": 1, "minY": 2, "maxX": 3, "maxY": 4}}
    )
    assert boxes == {"p1": (0.0, 0.0, 10.0, 10.0), "p2": (1.0, 2.0, 3.0, 4.0)}


BAD_BODIES = {
    "root-is-a-list": [{"p1": [0, 0, 1, 1]}],
    "length-5": {"p1": [0, 0, 10, 10, 99]},
    "length-3": {"p1": [0, 0, 10]},
    "missing-key": {"p1": {"minX": 0, "minY": 0, "maxX": 10}},
    "not-a-number": {"p1": ["0", 0, 10, 10]},
    "bool-is-not-a-number": {"p1": [True, 0, 10, 10]},
    "nan": {"p1": [float("nan"), 0, 10, 10]},
    "inf": {"p1": [0, 0, float("inf"), 10]},
    "inverted": {"p1": [10, 10, 0, 0]},
    "not-a-box": {"p1": "0,0,10,10"},
    "wrapper-not-an-object": {"bboxes": [["p1", [0, 0, 1, 1]]]},
}


@pytest.mark.parametrize("name", sorted(BAD_BODIES))
def test_a_bad_box_is_refused_by_name(name):
    with pytest.raises(ValueError) as caught:
        cli._draw_lint_body_boxes(BAD_BODIES[name])
    message = str(caught.value)
    assert "Traceback" not in message
    if name != "root-is-a-list" and name != "wrapper-not-an-object":
        assert "p1" in message, message


def test_a_bad_bodies_file_is_exit_2_with_no_report(tmp_path, capsys):
    snap = _write_json(tmp_path / "snap.json", _page())
    bodies = _write_json(tmp_path / "bodies.json", {"p1": [0, 0, 10, 10, 99]})
    report = tmp_path / "report.json"
    assert cli._cmd_draw_lint(_args(
        "--snapshot", str(snap), "--bodies", str(bodies), "--json", str(report),
    )) == 2
    err = capsys.readouterr().err
    assert "'p1'" in err and "expected 4" in err
    assert "Traceback" not in err
    assert not report.exists()


# ---------------------------------------------------------------------------
# 565-S2-H1/H7 — skipped predicates are named, and never called clean
# ---------------------------------------------------------------------------


TWO_PARTS = _page(
    parts=[("U1", "p-U1", 100.0, 100.0, 0.0), ("Q1", "p-Q1", 300.0, 300.0, 0.0)]
)


def test_no_materials_is_not_a_clean_page(tmp_path, capsys):
    snap = _write_json(tmp_path / "snap.json", TWO_PARTS)
    render = tmp_path / "render.svg"
    render.write_text(READABLE_RENDER, encoding="utf-8")
    report = tmp_path / "report.json"
    assert cli._cmd_draw_lint(_args(
        "--snapshot", str(snap), "--render", str(render), "--json", str(report),
    )) == 0
    out = capsys.readouterr().out
    assert "0 error / 0 warn / 0 info" in out
    assert "reads clean" not in out
    assert "NOT called clean" in out
    assert "L12-two-pin-same-net" in out and "L11-part-overlap" in out
    assert "measured 0 of 2" in out
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["skipped"] == [
        *drawlint.NETLIST_PREDICATES, "L11-part-overlap",
    ]
    assert payload["bodies"] == {
        "provided": False, "count": 0, "measured": 0, "parts": 2,
    }
    assert payload["textReadable"] is True


def test_a_partial_bodies_file_is_named_as_partial(tmp_path, capsys):
    snap = _write_json(tmp_path / "snap.json", TWO_PARTS)
    render = tmp_path / "render.svg"
    render.write_text(READABLE_RENDER, encoding="utf-8")
    bodies = _write_json(tmp_path / "bodies.json", {"p-U1": [90, 90, 110, 110]})
    report = tmp_path / "report.json"
    assert cli._cmd_draw_lint(_args(
        "--snapshot", str(snap), "--render", str(render),
        "--bodies", str(bodies), "--json", str(report),
    )) == 0
    out = capsys.readouterr().out
    assert "cover 1 of 2 part(s)" in out
    assert "reads clean" not in out
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["bodies"] == {
        "provided": True, "count": 1, "measured": 1, "parts": 2,
    }
    assert "L11-part-overlap" in payload["skipped"]


def test_findings_still_carry_the_not_run_list(tmp_path, capsys):
    """With findings the report must also say what was not checked."""
    snap = _write_json(
        tmp_path / "snap.json",
        _page(wires=[("wSlant", "DIAG", ((100, 100), (300, 300)))]),
    )
    render = tmp_path / "render.svg"
    render.write_text("<svg></svg>", encoding="utf-8")
    assert cli._cmd_draw_lint(_args(
        "--snapshot", str(snap), "--render", str(render),
    )) == 1
    out = capsys.readouterr().out
    assert "L13-non-orthogonal" in out
    assert "not run / not fully checked:" in out
    assert "L12-two-pin-same-net" in out


def test_complete_materials_keep_the_original_clean_sentence(tmp_path, capsys):
    """The legit clean negative control: render + netlist + every part measured."""
    snap = _write_json(
        tmp_path / "snap.json",
        _page(parts=[("U1", "p-U1", 100.0, 100.0, 0.0)]),
    )
    render = tmp_path / "render.svg"
    render.write_text(READABLE_RENDER, encoding="utf-8")
    bodies = _write_json(tmp_path / "bodies.json", {"bboxes": {"p-U1": [90, 90, 110, 110]}})
    netlist = _write_json(tmp_path / "netlist.json", CLEAN_NETLIST)
    report = tmp_path / "report.json"
    assert cli._cmd_draw_lint(_args(
        "--snapshot", str(snap), "--render", str(render),
        "--bodies", str(bodies), "--netlist", str(netlist),
        "--json", str(report),
    )) == 0
    out = capsys.readouterr().out
    assert "draw lint: no findings — the page reads clean." in out
    assert "NOT called clean" not in out
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["skipped"] == []
    assert payload["bodies"] == {
        "provided": True, "count": 1, "measured": 1, "parts": 1,
    }
    assert payload["netlist"]["provided"] is True
    assert payload["exitCode"] == 0
