"""057 stage C2b: a page document through `draw compile|plan|apply` and `draw discard`.

The editor half of the page compiler, against a fake editor whose page really
changes. The seams are 054's (see `test_054_draw_cli`), with three additions
this batch needs:

* **stable primitive ids** — every part, wire and flag the fake holds keeps the
  id it was given, across deletes, because "everything that was not the plan's
  is field-for-field what it was" (057 sec.2) is judged by primitive id, and a
  fake that renumbered its wires after a delete would make that claim untestable;
* **measured extents** — `sch.geometry` with ``bboxIds`` answers each requested
  component's box (origin, pin tips and a small body), which is what the census
  keep-outs are built from;
* **deletes** — `sch.delete_primitives` really removes, one id at a time, and
  answers the connector's own ``{deleted, notFound, failed}`` shape.

The netlist is hand-written from the plan's own islands (054's rule: the
expectation is the test's, never derived from the implementation). The specs are
hand-written JSON (056's rule), written to ``tmp_path``.

E1–E7 are the task book's real-machine scenes; what a fake can decide about each
is decided here, and the real-machine half is the runbook's
(`tools/057_live_runbook.md`).
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from boardwise import cli
from boardwise.core import pageframe
from boardwise.core.changeplan import DRAW_MODULE_KIND, ChangePlan
from boardwise.core.pagelayoutplan import PageLayoutPlan
from boardwise.engines import drawapply, pagecompiler, readability

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "drawapply"
LIBRARY = FIXTURES / "library.json"
PAGE_BOX = "0,0,1169,826"
SHEET = {"minX": 0, "minY": 0, "maxX": 1169, "maxY": 826}
PROV = "verified_recipe"

#: The pin geometry the fake editor answers with, keyed by LCSC number — the
#: fixture library's own geometry (R0402 ±50 vertical, C0402 ±40, the AMS1117
#: with VIN left, VOUT right, GND below), so a correct landing reads back clean.
PIN_OFFSETS = {
    "C25744": {"1": (0.0, 50.0), "2": (0.0, -50.0)},
    "C15525": {"1": (0.0, 40.0), "2": (0.0, -40.0)},
    "C45783": {"1": (0.0, 40.0), "2": (0.0, -40.0)},
    "C6186": {"3": (-60.0, 0.0), "2": (60.0, 0.0), "1": (0.0, -60.0)},
}


class _BridgeError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ------------------------------------------------------------------ the specs


def part(part_id, symbol, value, lcsc):
    return {"id": part_id, "symbolRef": symbol, "value": value, "lcsc": lcsc,
            "provenance": PROV}


def net(net_id, cls, members):
    return {"id": net_id, "class": cls, "members": members, "provenance": PROV}


def page_circuit() -> dict:
    """An LDO and a divider sharing the input rail and the ground (056 scene 1's shape)."""
    return {
        "parts": [
            part("U1", "AMS1117-3.3", "AMS1117-3.3", "C6186"),
            part("C1", "C0402", "10uF", "C15525"),
            part("C2", "C0402", "22uF", "C45783"),
            part("R1", "R0402", "10k", "C25744"),
            part("R2", "R0402", "10k", "C25744"),
        ],
        "nets": [
            net("VIN", "power", ["U1.3", "C1.1", "R1.1"]),
            net("3V3", "power", ["U1.2", "C2.1"]),
            net("TAP", "signal", ["R1.2", "R2.1"]),
            net("GND", "gnd", ["U1.1", "C1.2", "C2.2", "R2.2"]),
        ],
    }


def page_presentation(**extra) -> dict:
    payload = {
        "modules": [
            {"id": "pwr", "parts": ["U1", "C1", "C2"], "role": "regulator",
             "grammarRef": "ldo"},
            {"id": "sense", "parts": ["R1", "R2"], "role": "divider",
             "grammarRef": "voltage-divider"},
        ],
        "flow": [["pwr", "sense"]],
        "portRoles": {"VIN": "input", "3V3": "output"},
        "directWiringObligations": [
            {"nets": ["VIN", "3V3"], "note": "the regulator's own rails are wired"},
        ],
    }
    payload.update(extra)
    return payload


def write_specs(tmp_path: Path, *, circuit=None, presentation=None) -> tuple[Path, Path]:
    circuit_path = tmp_path / "page.circuit.json"
    presentation_path = tmp_path / "page.presentation.json"
    circuit_path.write_text(json.dumps(circuit or page_circuit()), encoding="utf-8")
    presentation_path.write_text(
        json.dumps(presentation or page_presentation()), encoding="utf-8"
    )
    return circuit_path, presentation_path


# ----------------------------------------------------------- the fake editor


class _PageEditor:
    """A schematic page with stable ids, measured extents and real deletes."""

    def __init__(self, *, page: str = "page-1", netlists=None, save_ok: bool = True,
                 timeouts=(), merge_wires_into: str = ""):
        self.page = page
        self.items: dict[str, dict] = {}
        self.order: list[str] = []
        self.counter = 0
        self.calls: list[str] = []
        self.writes: list[tuple[str, dict]] = []
        self.deletes: list[list[str]] = []
        self.netlists = list(netlists or [])
        self.netlist_reads = 0
        self.save_ok = save_ok
        self.timeouts = set(timeouts)
        #: The id of an existing wire the host "merges" every new wire of the same
        #: net into (pit 32) — how a landing that changes somebody else's wire is
        #: faked.
        self.merge_wires_into = merge_wires_into
        #: 180: the host library's ground-flag devices, keyed by device name
        #: (`Ground-PGND` -> {"uuid": …, "libraryUuid": …}). Empty means the library
        #: carries no per-net ground symbol, so the flow falls back to
        #: `sch.place_power` exactly as before.
        self.ground_symbols: dict[str, dict] = {}

    # ------------------------------------------------------------ the page

    def _new(self, prefix: str, item: dict, ident: str = "") -> str:
        self.counter += 1
        ident = ident or f"{prefix}-{self.counter}"
        self.items[ident] = item
        self.order.append(ident)
        return ident

    def add_part(self, designator, x, y, *, lcsc="C25744", value=None, rotation=0.0,
                 mirror=False, ident=""):
        item = {"kind": "part", "designator": designator, "x": float(x), "y": float(y),
                "rotation": float(rotation), "mirror": bool(mirror), "lcsc": lcsc,
                "value": value}
        return self._new("c", item, ident)

    def add_wire(self, net_name, points, ident=""):
        return self._new("w", {"kind": "wire", "net": net_name,
                               "points": [list(point) for point in points]}, ident)

    def add_flag(self, net_name, x, y, ident=""):
        return self._new("f", {"kind": "netflag", "net": net_name, "x": float(x),
                               "y": float(y)}, ident)

    def parts(self) -> dict[str, dict]:
        return {ident: item for ident, item in self.items.items() if item["kind"] == "part"}

    def pins_of(self, item) -> dict[str, tuple[float, float]]:
        out = {}
        for number, (dx, dy) in sorted(PIN_OFFSETS.get(item["lcsc"], {}).items()):
            rotation = item["rotation"]
            # The editor's own composition (054 pit 29): clockwise rotation, then a
            # mirror about the canvas vertical axis.
            if rotation == 90:
                dx, dy = dy, -dx
            elif rotation == 180:
                dx, dy = -dx, -dy
            elif rotation == 270:
                dx, dy = -dy, dx
            if item["mirror"]:
                dx = -dx
            out[number] = (item["x"] + dx, item["y"] + dy)
        return out

    def extent(self, item) -> dict:
        if item["kind"] == "netflag":
            box = (item["x"] - 6, item["y"] - 2, item["x"] + 6, item["y"] + 18)
        else:
            points = list(self.pins_of(item).values()) + [(item["x"], item["y"])]
            xs = [point[0] for point in points]
            ys = [point[1] for point in points]
            box = (min(xs) - 10, min(ys) - 10, max(xs) + 10, max(ys) + 10)
        return {"minX": box[0], "minY": box[1], "maxX": box[2], "maxY": box[3]}

    def geometry(self, bbox_ids=()) -> dict:
        components = [{"primitiveId": "sheet-1",
                       "state": {"ComponentType": "sheet", "Designator": "", "X": 0, "Y": 0}}]
        wires = []
        for ident in self.order:
            item = self.items[ident]
            if item["kind"] == "part":
                state = {"ComponentType": "part", "Designator": item["designator"],
                         "X": item["x"], "Y": item["y"], "Rotation": item["rotation"],
                         "Mirror": item["mirror"], "SupplierId": item["lcsc"]}
                if item["value"] is not None:
                    state["OtherProperty"] = {"Value": item["value"]}
                components.append({"primitiveId": ident, "state": state})
            elif item["kind"] == "netflag":
                components.append({"primitiveId": ident, "state": {
                    "ComponentType": "netflag", "Designator": None, "Net": item["net"],
                    "X": item["x"], "Y": item["y"], "Rotation": 0, "Mirror": False}})
            else:
                wires.append({"primitiveId": ident, "state": {
                    "Line": [c for point in item["points"] for c in point],
                    "Net": item["net"]}})
        bboxes = {"sheet-1": SHEET}
        for ident in bbox_ids:
            if ident in self.items and self.items[ident]["kind"] != "wire":
                bboxes[ident] = self.extent(self.items[ident])
        return {"components": components, "wires": wires, "pins": [], "netlabels": [],
                **{key: [] for key in drawapply.DRAWING_SECTIONS},
                "bboxes": bboxes,
                "meta": {"available": {
                    "components": True, "wires": True, "pins": True,
                    "netlabels": True,
                    **{key: True for key in drawapply.DRAWING_SECTIONS},
                }}}

    # ----------------------------------------------------------- the calls

    async def call(self, action, params=None, **_route):
        params = params or {}
        self.calls.append(action)
        if action in self.timeouts:
            self.timeouts.discard(action)
            raise _BridgeError("TIMEOUT", f"{action} did not answer within 30 s")
        if action == "doc.list":
            return {
                "documents": [{"uuid": self.page, "name": "P1", "type": "sch"}],
                "projects": [{"projectUuid": "proj-1", "name": "test", "focused": True}],
                "active": {"uuid": self.page, "type": "sch"},
            }
        if action == "doc.focus":
            return {"activated": True}
        if action == "sys.get_document_source":
            # The page's own record stream, shaped the way the host writes one
            # (533's `_source`) and stating the sheet this fake page **is**
            # (`SHEET`, i.e. `PAGE_BOX` 0,0,1169,826).  A page plan carries the
            # sheet it was packed for, and `draw apply`'s S-01 leg reads this to
            # compare against it (569): without the answer the leg cannot judge
            # the landing at all.
            from test_533_island_guard import _source

            return {"data": _source({
                "Width": str(SHEET["maxX"] - SHEET["minX"]),
                "Height": str(SHEET["maxY"] - SHEET["minY"]),
            }, attached=True)}
        if action == "sys.identity":
            return {"consistent": True, "consistentBasis": "project-uuid"}
        if action == "sch.geometry":
            return self.geometry(params.get("bboxIds") or ())
        if action == "sch.netlist":
            index = min(self.netlist_reads, len(self.netlists) - 1)
            self.netlist_reads += 1
            payload = self.netlists[index] if self.netlists else {"components": {}}
            return {"type": params.get("type"), "text": json.dumps(payload)}
        if action == "sch.component_pins":
            item = self.items.get(str(params.get("primitiveId") or ""))
            pins = [
                {"X": x, "Y": y, "PinNumber": number, "PinName": number}
                for number, (x, y) in sorted((self.pins_of(item) if item else {}).items())
            ]
            return {"primitiveId": params.get("primitiveId"), "pins": pins}
        if action == "lib.device.search":
            # 180: the ground-flag symbol probe (`draw apply` looks up
            # `Ground-<net>` before falling back to `sch.place_power`), read-only.
            keyword = str(params.get("keyword") or "")
            items = [
                {"name": name, **dict(device)}
                for name, device in self.ground_symbols.items() if name == keyword
            ]
            return {"keyword": keyword, "returned": len(items), "shown": len(items),
                    "items": items}
        if action == "sch.place_component":
            self.writes.append((action, params))
            device_uuid = str(params.get("deviceUuid") or "")
            ground = next(
                (name for name, device in self.ground_symbols.items()
                 if str(device.get("uuid") or "") == device_uuid),
                "",
            )
            if ground:
                # 180: a ground flag placed by its library symbol lands a netflag.
                net = ground[len("Ground-"):] if ground.startswith("Ground-") else ground
                return {"uuid": self.add_flag(net, params.get("x"), params.get("y"))}
            ident = self.add_part(
                str(params.get("designator") or ""), params.get("x"), params.get("y"),
                lcsc=str(params.get("lcsc") or ""),
                rotation=float(params.get("rotation") or 0.0),
                mirror=bool(params.get("mirror")),
            )
            return {"uuid": ident}
        if action == "sch.set_component_attribute":
            self.writes.append((action, params))
            item = self.items[str(params.get("primitiveId"))]
            item["value"] = str(params.get("value") or "")
            return {"applied": True, "readBackAfter": item["value"]}
        if action == "sch.place_wire":
            self.writes.append((action, params))
            net_name = str(params.get("net") or "")
            target = self.items.get(self.merge_wires_into)
            if target is not None and target["net"] == net_name:
                # The host merges a touching wire into the existing primitive.
                target["points"].extend(list(point) for point in params.get("points") or [])
                return {"uuid": self.merge_wires_into}
            return {"uuid": self.add_wire(net_name, params.get("points") or [])}
        if action == "sch.place_power":
            self.writes.append((action, params))
            return {"uuid": self.add_flag(str(params.get("net") or ""), params.get("x"),
                                          params.get("y"))}
        if action == "sch.delete_primitives":
            self.writes.append((action, params))
            ids = [str(item) for item in params.get("primitiveIds") or []]
            self.deletes.append(ids)
            deleted = [ident for ident in ids if ident in self.items]
            for ident in deleted:
                del self.items[ident]
                self.order.remove(ident)
            return {"deleted": deleted,
                    "notFound": [ident for ident in ids if ident not in deleted],
                    "failed": []}
        if action == "sch.doc.save":
            if not self.save_ok:
                raise _BridgeError("CONNECTOR_ERROR", "the editor refused the save")
            self.writes.append((action, params))
            return {"saved": True}
        if action == "export.render":
            blob = b"\x89PNG\r\n\x1a\n" + b"fake page render"
            return {"format": "png", "scope": "page", "pageUuid": self.page,
                    "data": base64.b64encode(blob).decode("ascii")}
        raise AssertionError(f"the flow called {action}, which this fake does not answer")

    async def close(self):
        return None

    def snapshot(self) -> dict:
        return json.loads(json.dumps(self.items))


def _stub_editor(monkeypatch, editor) -> None:
    class _Client:
        @staticmethod
        async def open(*_args, **_kwargs):
            return editor

    monkeypatch.setattr(cli, "_open_cli", lambda args: (_Client, _BridgeError, 61190, "tok"))


def _stub_export(monkeypatch, *, components=None, findings=None, sequence=None):
    """Serve the live export and the findings (a list per read when `sequence`)."""
    reads = list(sequence) if sequence is not None else None

    async def _export(call, notes):
        return b"export-bytes"

    def _parse(blob, notes):
        return type("Model", (), {"components": dict(components or {})})()

    def _findings(model, intent=None):
        if reads is not None:
            return list(reads.pop(0)) if reads else []
        return list(findings or [])

    monkeypatch.setattr(cli, "_live_project_export", _export)
    monkeypatch.setattr(cli, "_model_from_export", _parse)
    monkeypatch.setattr(cli, "_baseline_findings", _findings)


def _netlist_for(plan: ChangePlan, *, split: str = "") -> dict:
    """The netlist the plan says the page must show; ``split`` breaks one net in two.

    Named the way the plan states it where it states one (a flag's own net, or a
    label's wire's name) — what the editor does with the flag/wire it was given; a
    net with no stated name is the editor's own auto name (530D, ruling A).
    """
    live = {"components": {}}
    stated = drawapply.planned_net_names(plan)
    for index, island in enumerate(sorted({tuple(item.mates) for item in plan.change.islands})):
        name = next(
            (stated[member] for member in sorted(island) if member in stated),
            f"NET{index + 1}",
        )
        for position, member in enumerate(island):
            designator, _sep, pin = member.partition(".")
            if split and split in island and position % 2:
                # The pin is on a net of its own — the same-named net did not merge.
                pin_net = f"{name}_ISLAND"
            else:
                pin_net = name
            entry = live["components"].setdefault(
                designator, {"props": {"Designator": designator}, "pinInfoMap": {}},
            )
            entry["pinInfoMap"][pin] = {"net": pin_net}
    return live


def _plan_args(circuit, presentation, *rest):
    return ["draw", "plan", "--circuit", str(circuit), "--presentation", str(presentation),
            "--profiles", str(LIBRARY), "--page-box", PAGE_BOX, *rest]


def _plan_page(monkeypatch, tmp_path, editor, *, findings=(), extra=()):
    """`draw plan` bound to the fake page — the census is read, the keep-outs made."""
    circuit, presentation = write_specs(tmp_path)
    _stub_editor(monkeypatch, editor)
    _stub_export(monkeypatch, findings=list(findings))
    out = tmp_path / "plan.json"
    code = cli.main(_plan_args(circuit, presentation, "--page", editor.page,
                               "--out", str(out), "--json", str(tmp_path / "plan.report.json"),
                               *extra))
    return code, out, circuit, presentation


def _apply(editor, plan_path, circuit, presentation, tmp_path, *extra):
    report = tmp_path / "apply.json"
    code = cli.main([
        "draw", "apply", str(plan_path), "--project", "test",
        "--circuit", str(circuit), "--presentation", str(presentation),
        "--profiles", str(LIBRARY), "--json", str(report),
        "--render", str(tmp_path / "render.png"), *extra,
    ])
    return code, json.loads(report.read_text(encoding="utf-8"))


# ------------------------------------------------------------ the saved page


def _move_saved_page(page: PageLayoutPlan, dy: float) -> None:
    """Move a saved page (drawing, frames, ports) as one rigid body.

    This is the hand-tuned page a saved ``--layout`` stands for: an earlier run's
    document, moved as a whole, with no recompile and no scaling.  Only ``dy`` is
    needed here because the sheet's title block sits in the bottom-right corner
    and the compiled page's second module already shares its x range.
    """
    for part in page.plan.parts:
        part.y += dy
    for segment in page.plan.segments:
        segment.points = [(x, y + dy) for x, y in segment.points]
    for junction in page.plan.junctions:
        junction.y += dy
    for label in page.plan.labels:
        label.y += dy
        label.bbox = (label.bbox[0], label.bbox[1] + dy,
                      label.bbox[2], label.bbox[3] + dy)
    for symbol in page.plan.power_symbols:
        symbol.y += dy
    for text in page.plan.texts:
        if text.y is not None:
            text.y += dy
        text.bbox = (text.bbox[0], text.bbox[1] + dy, text.bbox[2], text.bbox[3] + dy)
    for module in page.modules:
        module.origin = (module.origin[0], module.origin[1] + dy)
        module.frame = (module.frame[0], module.frame[1] + dy,
                        module.frame[2], module.frame[3] + dy)
        for port in module.ports:
            port.y += dy


def _saved_page(tmp_path: Path, *, dy: float = 0.0, name: str = "saved.page.json") -> Path:
    """A real saved page: `draw compile`'s first candidate, optionally moved."""
    circuit, presentation = write_specs(tmp_path)
    out = tmp_path / "compiled"
    code = cli.main([
        "draw", "compile", "--circuit", str(circuit), "--presentation", str(presentation),
        "--profiles", str(LIBRARY), "--page-box", PAGE_BOX, "--out", str(out),
    ])
    assert code == 0, "the page this test starts from did not compile"
    page = PageLayoutPlan.load(sorted(out.glob("cand*.page.json"))[0])
    if dy:
        _move_saved_page(page, dy)
    path = tmp_path / name
    page.dump(path)
    return path


def _report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# -------------------------------------------------------------- draw compile


def test_a_page_presentation_compiles_to_page_documents_on_the_same_command(tmp_path, capsys):
    """057 sec.1: `modules[]` of a page -> page.json candidates, frames in the SVG."""
    circuit, presentation = write_specs(tmp_path)
    out = tmp_path / "previews"
    report = tmp_path / "compile.json"
    code = cli.main([
        "draw", "compile", "--circuit", str(circuit), "--presentation", str(presentation),
        "--profiles", str(LIBRARY), "--page-box", PAGE_BOX, "--out", str(out),
        "--json", str(report),
    ])
    printed = capsys.readouterr().out
    assert code == 0, printed
    assert "page of 2 module(s)" in printed
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["document"] == "page" and payload["pages"]
    assert "recovery" not in payload, "a successful page compile keeps its payload shape"
    document = PageLayoutPlan.load(out / "cand1.page.json")
    assert [module.id for module in document.modules] == ["pwr", "sense"]
    assert payload["pages"][0]["geometrySha256"] == document.page_geometry_sha256()
    svg = (out / "cand1.svg").read_text(encoding="utf-8")
    assert "pwr" in svg and "sense" in svg, "the module frames are drawn and named"
    assert not (out / "cand1.layout.json").exists(), "a page writes page documents"


def test_a_page_compile_without_a_sheet_is_refused_by_name(tmp_path, capsys):
    circuit, presentation = write_specs(tmp_path)
    code = cli.main([
        "draw", "compile", "--circuit", str(circuit), "--presentation", str(presentation),
        "--profiles", str(LIBRARY), "--out", str(tmp_path / "out"),
    ])
    assert code == 5
    assert "--page-box" in capsys.readouterr().err


def test_a_zero_candidate_page_hands_over_the_same_guarded_manual_route(
    tmp_path, capsys
):
    """057 zero-candidate: the page path carries the same `recovery`, key for key.

    A page lock off the page is refused before any module compiles, so no page
    candidate exists. The JSON and the printed next line must say what the
    single-module path says — the keys are the single-module contract's, not a
    second vocabulary invented for pages.
    """
    circuit, presentation = write_specs(
        tmp_path,
        presentation=page_presentation(
            userLocks=[{"partId": "U1", "x": 5000, "y": 500, "scope": "page"}]
        ),
    )
    report = tmp_path / "compile.json"
    code = cli.main([
        "draw", "compile", "--circuit", str(circuit), "--presentation", str(presentation),
        "--profiles", str(LIBRARY), "--page-box", PAGE_BOX, "--out", str(tmp_path / "out"),
        "--json", str(report),
    ])
    captured = capsys.readouterr()
    assert code == 5
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["document"] == "page" and payload["ok"] is False
    assert payload["pages"] == []
    recovery = payload["recovery"]
    assert recovery["route"] == "agent-adjusted"
    assert recovery["automaticCandidates"] == 0
    assert recovery["reuseEmptyPage"] is True
    assert recovery["command"] == "boardwise edit plan --move"
    assert "no legal candidate" in recovery["reason"]
    assert "ask the user" in recovery["reason"]
    assert recovery["forbidden"] == [
        "blind retry of the same input",
        "batch-creating pages",
        "deleting a page without the user's confirmation",
        "running an unguarded executor",
    ]
    next_line = next(
        line for line in captured.out.splitlines() if line.startswith("next: ")
    )
    assert "no automatic candidate" in next_line
    assert "agent-adjusted" in next_line
    assert "boardwise edit plan --move" in next_line
    assert "reuse an existing empty page" in next_line


def test_what_makes_a_presentation_a_page():
    """The single-module documents keep their path (the 054 fixture is one module)."""
    from boardwise.core.presentationspec import PresentationSpec

    single = PresentationSpec.load(FIXTURES / "divider.presentation.json")
    assert not pagecompiler.wants_page(single)
    assert pagecompiler.wants_page(PresentationSpec.from_dict(page_presentation()))
    one_with_flow = page_presentation()
    one_with_flow["modules"] = one_with_flow["modules"][:1]
    one_with_flow["modules"][0]["parts"] = ["U1", "C1", "C2"]
    one_with_flow.pop("flow")
    assert pagecompiler.wants_page(PresentationSpec.from_dict(one_with_flow)), (
        "a module that states its own grammar is a page statement"
    )
    locked = {"grammarRef": "voltage-divider",
              "modules": [{"id": "d", "parts": ["R1", "R2"], "role": "divider"}],
              "userLocks": [{"partId": "R1", "x": 100, "y": 100, "scope": "page"}]}
    assert pagecompiler.wants_page(PresentationSpec.from_dict(locked))


# ----------------------------------------------------------------- draw plan


def test_an_offline_page_plan_is_a_draw_module_plan_of_the_pages_drawing(tmp_path, capsys):
    circuit, presentation = write_specs(tmp_path)
    out = tmp_path / "plan.json"
    code = cli.main(_plan_args(circuit, presentation, "--out", str(out)))
    printed = capsys.readouterr().out
    assert code == 0, printed
    plan = ChangePlan.load(out)
    page = PageLayoutPlan.load(tmp_path / "plan.page.json")
    assert plan.change.kind == DRAW_MODULE_KIND
    # The page's guard evidence is its `plan` field's (057 sec.1): the layout digest
    # the plan carries is the merged drawing's, not a second one invented for pages.
    assert plan.change.layout_sha256 == page.plan.geometry_sha256()
    assert plan.change.circuit_sha256 == page.plan.source.circuit_sha256
    assert plan.target.module.startswith("page pwr+sense")
    assert sorted(part.designator for part in plan.change.draw_parts) == [
        "C1", "C2", "R1", "R2", "U1"
    ]


def test_a_saved_page_inside_the_title_block_is_refused_by_name(tmp_path, capsys):
    """The P1 replay: a saved page whose module frame shares the sheet's table.

    The preflight used to check the census only, so this exact page passed both
    checks and became an applicable plan — J10/J11/J12 and their wires inside the
    title block.  Derived from the saved page's own ``page_box`` (S-01), the block
    is a keep-out and the page is refused by name; nothing is re-packed, scaled or
    repaired, and no product plan is written.
    """
    circuit, presentation = write_specs(tmp_path)
    saved = _saved_page(tmp_path, dy=-300.0, name="overlap.page.json")
    out = tmp_path / "overlap-plan.json"
    report_path = tmp_path / "overlap-report.json"
    code = cli.main(_plan_args(
        circuit, presentation, "--layout", str(saved),
        "--out", str(out), "--json", str(report_path),
    ))
    captured = capsys.readouterr()
    report = _report(report_path)
    title = pageframe.title_block_keepouts((0.0, 0.0, 1169.0, 826.0))[0]
    page = PageLayoutPlan.load(saved)
    overlapping = [
        module.id for module in page.modules
        if min(module.frame[2], title[2]) - max(module.frame[0], title[0]) > 0
        and min(module.frame[3], title[3]) - max(module.frame[1], title[1]) > 0
    ]
    assert overlapping, "the fixture must really sit in the title block"
    assert code == 5, captured.out
    assert report["reason"] == "readability_refused"
    assert report["outcome"] == "refused"
    assert report["checks"]["page"]["ok"] is False
    assert report["plan"] is None
    assert not out.exists(), "a conflicted saved page must not produce an applicable plan"
    assert not (tmp_path / "overlap-plan.page.json").exists(), (
        "no page document is written for a page that is refused"
    )
    assert "[459, 10, 1159, 190]" in captured.err, captured.err
    assert "title block (S-01)" in captured.err, captured.err
    assert "page-keepout-conflict" in captured.err, captured.err
    assert f"module '{overlapping[0]}'" in captured.err, captured.err
    assert "no recompile" in captured.err, captured.err


def test_a_legal_saved_page_is_marked_and_carries_the_exact_title_keepout(
    monkeypatch, tmp_path, capsys
):
    """A saved page that clears the table plans, and says so in the two spellings
    `draw apply` already reads — the island marker and the sheet reservation.

    The checks are handed the census **and** the derived block (the census is not
    dropped, and the block is not added twice), which is what makes the refusal in
    the test above about the saved page rather than about the preflight list.
    """
    editor = _PageEditor()
    editor.add_part("R9", 60, 60, lcsc="C25744", value="1k")
    editor.add_wire("", [(250, 60), (320, 60)])
    editor.add_flag("GND", 250, 120)
    circuit, presentation = write_specs(tmp_path)
    saved = _saved_page(tmp_path)
    captured: list[tuple[str, list[tuple[float, ...]]]] = []
    real_page_check = readability.check_page
    real_drawing_check = readability.check

    def _spy(name, real):
        def called(*args, **kwargs):
            captured.append((
                name,
                [tuple(float(value) for value in box) for box in kwargs.get("keepouts") or ()],
            ))
            return real(*args, **kwargs)
        return called

    monkeypatch.setattr(readability, "check_page", _spy("page", real_page_check))
    monkeypatch.setattr(readability, "check", _spy("drawing", real_drawing_check))
    _stub_editor(monkeypatch, editor)
    _stub_export(monkeypatch)
    out = tmp_path / "legal-plan.json"
    report_path = tmp_path / "legal-report.json"
    code = cli.main(_plan_args(
        circuit, presentation, "--layout", str(saved), "--page", editor.page,
        "--out", str(out), "--json", str(report_path),
    ))
    assert code == 0, capsys.readouterr().out
    report = _report(report_path)
    census = [tuple(row["box"]) for row in report["keepouts"]]
    assert len(census) == 3, "a part, a wire and a flag: the census is not dropped"
    title = tuple(float(value) for value in
                  pageframe.title_block_keepouts((0.0, 0.0, 1169.0, 826.0))[0])
    assert tuple(title) not in census
    assert [name for name, _boxes in captured] == ["page", "drawing"]
    for name, boxes in captured:
        assert boxes == census + [title], name
        assert len(set(boxes)) == len(boxes), "the title block is not added twice"
    plan = ChangePlan.load(out)
    assert cli._draw_plan_is_island_page(plan), "without the marker the S-01 guard is skipped"
    assert pageframe.page_keep_out_from_notes(plan.change.draw_notes) == (
        (0.0, 0.0, 1169.0, 826.0), title,
    )


def test_a_legal_saved_page_plan_enters_the_s01_guard(monkeypatch, tmp_path, capsys):
    """The marker and the reservation put a saved-page plan through S-01 itself.

    Landing on a sheet the reservation was not made for is refused before the
    first write (`landing_sheet_mismatch`).  Before the fix the plan carried no
    marker, `_draw_plan_is_island_page` was False, and this leg never ran.
    """
    from test_533_island_guard import LIVE_SHEET, _source

    class _SheetEditor(_PageEditor):
        async def call(self, action, params=None, **_route):
            if action == "sys.get_document_source":
                self.calls.append(action)
                return {"data": _source(LIVE_SHEET, attached=True)}
            return await super().call(action, params, **_route)

    editor = _SheetEditor()
    _stub_editor(monkeypatch, editor)
    _stub_export(monkeypatch)
    circuit, presentation = write_specs(tmp_path)
    saved = _saved_page(tmp_path)
    plan_path = tmp_path / "plan.json"
    plan_report = tmp_path / "plan-report.json"
    code = cli.main(_plan_args(
        circuit, presentation, "--layout", str(saved), "--page", editor.page,
        "--out", str(plan_path), "--json", str(plan_report),
    ))
    assert code == 0, capsys.readouterr().out
    plan = ChangePlan.load(plan_path)
    assert cli._draw_plan_is_island_page(plan)

    apply_report = tmp_path / "saved-apply.json"
    code = cli.main([
        "draw", "apply", str(plan_path), "--page", editor.page, "--instance", "inst-1",
        "--circuit", str(circuit), "--presentation", str(presentation),
        "--profiles", str(LIBRARY), "--json", str(apply_report),
    ])
    printed = capsys.readouterr().out
    payload = _report(apply_report)
    assert code == 5, printed
    assert payload["reason"] == "landing_sheet_mismatch"
    assert payload["write"]["calls"] == 0
    assert editor.writes == [], "the refusal happens before the first write"
    assert payload["titleBlock"]["planRecordedPageBox"] == [0.0, 0.0, 1169.0, 826.0]
    assert payload["titleBlock"]["livePageBox"] == [0.0, 0.0, 1170.0, 825.0]
    assert "sys.get_document_source" in editor.calls


def test_a_page_label_no_wire_reaches_becomes_a_named_stub(tmp_path, capsys):
    """G4's ground: the divider's VIN pin must carry the name, or it never merges.

    069 sec.7 moved the *default* for a rail from a label to a flag, so the label
    this test is about now comes from the one route a rail can still take one: a
    library that carries no flag symbol for the net (`_net_style`'s "the library
    carries no flag symbol" answer). The downgrade it exercises — a label at a bare
    pin tip is not placeable on this host, so a named stub carries the name — is
    unchanged either way.
    """
    circuit, presentation = write_specs(tmp_path)
    book = json.loads(LIBRARY.read_text(encoding="utf-8"))
    book["profiles"] = [
        profile for profile in book["profiles"]
        if profile["symbolRef"] != "PWR-VIN"
    ]
    flagged_less = tmp_path / "library.no-PWR-VIN.json"
    flagged_less.write_text(json.dumps(book), encoding="utf-8")
    out = tmp_path / "plan.json"
    assert cli.main([
        "draw", "plan", "--circuit", str(circuit), "--presentation", str(presentation),
        "--profiles", str(flagged_less), "--page-box", PAGE_BOX, "--out", str(out),
    ]) == 0
    capsys.readouterr()
    plan = ChangePlan.load(out)
    page = PageLayoutPlan.load(tmp_path / "plan.page.json")
    labels = {(label.net, label.x, label.y) for label in page.plan.labels}
    assert any(net_name == "VIN" for net_name, _x, _y in labels)
    stubs = [wire for wire in plan.change.draw_wires if wire.purpose.startswith("name stub")]
    assert stubs, "a label at a bare pin tip is carried by a named stub"
    for stub in stubs:
        # The **causal** statement, not a size cap (534): the stub exists because the
        # label's anchor has no wire of its net on it, so it starts at that anchor and
        # runs away from the pin as an orthogonal conductor whose longest leg is the
        # one the host prints the name along — horizontally. Which shapes and lengths
        # a stub may take is 099d/099f's and 534's question; 057 does not restate it.
        assert (stub.net, stub.points[0][0], stub.points[0][1]) in labels, (
            "the named stub starts at the label's own anchor")
        assert len(stub.points) >= 2, stub.points
        for start, end in zip(stub.points, stub.points[1:]):
            assert start != end, ("every leg of the stub has a length", start, end)
            assert (abs(start[0] - end[0]) < 1e-9) != (abs(start[1] - end[1]) < 1e-9), (
                "every leg is orthogonal", start, end)
        run = drawapply._StubRun(
            points=tuple(stub.points), side=(1.0, 0.0), shape="", family="",
        )
        assert drawapply._stub_row_is_horizontal(run), (
            "the host prints the name along a horizontal longest run", stub.points)
        assert stub.from_pin, "the stub leaves the pin the label sat on"
    assert any("stub" in line and stub_net in line
               for line in plan.change.draw_downgrades
               for stub_net in ("VIN",)), (
        "the plan discloses the name-stub substitution", plan.change.draw_downgrades)


# ------------------------------------------------------------ E1: empty page


def test_069_a_wire_is_named_only_where_the_wire_is_the_label(
    monkeypatch, tmp_path, capsys
):
    """069 sec.9, as 岳 widened it (530D, ruling A 2026-10-21).

    岳 on the landed page: 「有了旗标就不要反复标注网络标识了。看着很乱啊」— the host
    prints a wire's net name on the canvas, so a net the drawing states elsewhere
    was saying it twice.  069 made that true of a **flagged** net's wires; ruling A
    makes it true of every wire that is not itself a name carrier:
    「名字只住在旗标/标签上」.  So what still lands named is exactly the wire that
    **is** the label (`drawapply.named_wire_nets`), because on this host a label has
    no primitive of its own (`sch.place_netlabel` is unusable, 029) — and that is
    also the set `draw apply`'s live leg reads the names back against.
    """
    editor = _PageEditor()
    code, plan_path, circuit, presentation = _plan_page(monkeypatch, tmp_path, editor)
    assert code == 0
    plan = ChangePlan.load(plan_path)
    # The editor's own netlist still *names* those nets — a flag, or the wire that
    # is the label, is what names them, which is why the unnamed conductors cost
    # the netlist nothing.
    editor.netlists = [{"components": {}}, _netlist_for(plan)]
    assert _apply(editor, plan_path, circuit, presentation, tmp_path)[0] == 0
    calls = [params for action, params in editor.writes if action == "sch.place_wire"]
    assert len(calls) == len(plan.change.draw_wires), [params for params in calls]
    flagged = {item.net for item in plan.change.draw_flags if item.net}
    assert flagged, "premise: this page draws flags"
    named = set()
    for wire, params in zip(plan.change.draw_wires, calls):
        if drawapply.is_label_wire(wire):
            assert params.get("net") == wire.net, (wire.net, params)
            named.add(wire.net)
            continue
        assert "net" not in params, (
            f"{wire.net} is not a label and must be drawn unnamed — the drawing "
            f"states its name on a flag, or nowhere at all: {params}"
        )
    assert "TAP" in named, (
        "TAP has no flag, so the only thing carrying its name is its label's own "
        f"wire (057 sec.4); the named nets were {sorted(named)}"
    )
    assert not (flagged & named), "a flagged net must print its name once, on its flag"


def test_e1_an_empty_page_lands_the_whole_page_and_reads_the_shared_nets_back(
    monkeypatch, tmp_path, capsys
):
    """E1 + E4 (fake half): compile -> plan -> apply; the shared nets are one net."""
    editor = _PageEditor()
    code, plan_path, circuit, presentation = _plan_page(monkeypatch, tmp_path, editor)
    assert code == 0, capsys.readouterr()
    plan = ChangePlan.load(plan_path)
    editor.netlists = [{"components": {}}, _netlist_for(plan)]
    code, report = _apply(editor, plan_path, circuit, presentation, tmp_path,
                          "--layout", str(tmp_path / "plan.page.json"))
    assert code == 0, capsys.readouterr().out
    assert report["outcome"] == "applied"
    assert report["guards"]["checked"]["layoutSha256"] is True
    nets = {tuple(row["pins"]): row for row in report["verification"]["nets"]}
    cross = [row for row in nets.values() if row["crossModule"]]
    assert cross, "VIN and GND span both modules"
    assert all(row["oneNet"] for row in cross)
    assert {tuple(sorted(row["modules"])) for row in cross} == {("pwr", "sense")}
    assert report["range"]["outOfScope"]["changed"] == []
    assert "sch.doc.save" in [action for action, _params in editor.writes]


def test_e4_a_shared_net_that_did_not_merge_is_not_saved(monkeypatch, tmp_path, capsys):
    """A cross-module net whose two ends stayed two islands is a read-back failure."""
    editor = _PageEditor()
    code, plan_path, circuit, presentation = _plan_page(monkeypatch, tmp_path, editor)
    assert code == 0
    plan = ChangePlan.load(plan_path)
    vin = next(
        member for island in plan.change.islands for member in island.mates
        if member.startswith("R") and len(island.mates) == 3
    )
    editor.netlists = [{"components": {}}, _netlist_for(plan, split=vin)]
    code, report = _apply(editor, plan_path, circuit, presentation, tmp_path)
    assert code == 3
    assert report["reason"] == "verification_disagrees"
    assert "sch.doc.save" not in [action for action, _params in editor.writes]


def test_e4_findings_are_judged_by_identity_not_by_count(monkeypatch, tmp_path, capsys):
    """One finding resolved and another created: the count is equal, the run is not clean."""
    editor = _PageEditor()
    circuit, presentation = write_specs(tmp_path)
    _stub_editor(monkeypatch, editor)
    before = ["decap-required-caps|WARN|U9|2|3V3"]
    after = ["decap-required-caps|WARN|U1|2|3V3"]
    _stub_export(monkeypatch, sequence=[before, after])
    out = tmp_path / "plan.json"
    assert cli.main(_plan_args(circuit, presentation, "--page", "page-1", "--out", str(out))) == 0
    plan = ChangePlan.load(out)
    assert plan.change.baseline_findings == before
    editor.netlists = [{"components": {}}, _netlist_for(plan)]
    code, report = _apply(editor, out, circuit, presentation, tmp_path)
    assert code == 2
    assert report["reason"] == "new_findings"
    assert report["findings"]["new"] == after
    assert report["findings"]["resolved"] == before


def test_e4_a_finding_the_page_resolves_is_reported_resolved(monkeypatch, tmp_path, capsys):
    editor = _PageEditor()
    circuit, presentation = write_specs(tmp_path)
    _stub_editor(monkeypatch, editor)
    before = ["decap-required-caps|WARN|U9|2|3V3"]
    _stub_export(monkeypatch, sequence=[before, []])
    out = tmp_path / "plan.json"
    assert cli.main(_plan_args(circuit, presentation, "--page", "page-1", "--out", str(out))) == 0
    plan = ChangePlan.load(out)
    editor.netlists = [{"components": {}}, _netlist_for(plan)]
    code, report = _apply(editor, out, circuit, presentation, tmp_path)
    assert code == 0, report["notes"]
    assert report["findings"]["resolved"] == before and report["findings"]["new"] == []


def _e4_run(monkeypatch, tmp_path, before, after, *extra):
    """The E4 shape end to end: an empty page, a plan built against ``before``, applied.

    ``_stub_export``'s sequence serves the plan's own reading first and the apply's
    fresh one second, so the two findings readings the gate compares are written by
    the test — as the ``_finding_signature`` strings `run_review` really emits, which
    is the gate's input. Returns ``(code, report, editor)``.
    """
    editor = _PageEditor()
    circuit, presentation = write_specs(tmp_path)
    _stub_editor(monkeypatch, editor)
    _stub_export(monkeypatch, sequence=[list(before), list(after)])
    out = tmp_path / "plan.json"
    assert cli.main(_plan_args(circuit, presentation, "--page", "page-1",
                               "--out", str(out))) == 0
    plan = ChangePlan.load(out)
    editor.netlists = [{"components": {}}, _netlist_for(plan)]
    code, report = _apply(editor, out, circuit, presentation, tmp_path, *extra)
    return code, report, editor


def test_e4_an_info_finding_never_stops_the_save(monkeypatch, tmp_path, capsys):
    """Ruling B (issue #55) on the land path: an INFO is a report, not a verdict.

    The flat "the set may only shrink" let a report-only row stop a save — 087's
    live landing was blocked repeatedly by exactly that. The row stays in the
    report, and the drawing is saved.
    """
    before = ["decap-required-caps|WARN|U9|2|3V3"]
    after = before + ["param-rc-cutoff|INFO|RC R1(1k) + C1(1n) on 'TAP': fc = 159,155 Hz"]
    code, report, editor = _e4_run(monkeypatch, tmp_path, before, after)
    assert code == 0, report["notes"]
    assert report["outcome"] == "applied"
    assert report["findings"]["new"] == after[1:]
    assert report["findings"]["newBySeverity"] == {
        "ERROR": [], "WARN": [], "INFO": after[1:],
    }
    assert report["findings"]["forcedWarns"] == [], (
        "an INFO is reported, not released: nothing was blocking it"
    )
    assert report["save"] == {"ok": True, "answered": {"saved": True}}
    assert report["persistence"] == "saved_unverified"
    assert "sch.doc.save" in [action for action, _params in editor.writes]


def test_e4_force_releases_a_warn_finding_and_names_it(monkeypatch, tmp_path, capsys):
    """The middle tier on the land path: a WARN stops the save, ``--force`` releases
    it, and every WARN released is named in the report and in the notes."""
    before = ["decap-required-caps|WARN|U9|2|3V3"]
    after = ["decap-required-caps|WARN|U1|2|3V3", "decap-required-caps|WARN|U2|5|VIN"]

    blocked, report, editor = _e4_run(monkeypatch, tmp_path, before, after)
    assert blocked == 2
    assert report["reason"] == "new_findings"
    assert report["findings"]["new"] == after
    assert report["findings"]["newBySeverity"]["WARN"] == after
    assert report["findings"]["forcedWarns"] == [], "no --force, nothing released"
    assert "sch.doc.save" not in [action for action, _params in editor.writes]

    # A fresh run — a new editor, a new plan, the same readings — with --force.
    code, report, editor = _e4_run(monkeypatch, tmp_path, before, after, "--force")
    assert code == 0, report["notes"]
    assert report["findings"]["forcedWarns"] == after, (
        "the released WARNs are named in the report, never dropped silently"
    )
    assert report["findings"]["newBySeverity"]["WARN"] == after
    assert "sch.doc.save" in [action for action, _params in editor.writes]
    assert any("--force" in note and "forcedWarns" in note for note in report["notes"]), (
        "and in the notes, so a reader of the console sees the release too"
    )


def test_e4_force_does_not_release_an_error_finding(monkeypatch, tmp_path, capsys):
    """The top tier: ``--force`` is not a licence to save a short circuit. The run
    stops with the ERROR named, and the WARN alongside it is released (it is named
    as released) without buying the save."""
    before = ["decap-required-caps|WARN|U9|2|3V3"]
    after = ["conn-duplicate-designators|ERROR|U1||", "decap-required-caps|WARN|U2|5|VIN"]
    code, report, editor = _e4_run(monkeypatch, tmp_path, before, after, "--force")
    assert code == 2
    assert report["reason"] == "new_findings"
    assert report["findings"]["newBySeverity"]["ERROR"] == [after[0]]
    assert report["findings"]["forcedWarns"] == [after[1]]
    assert "sch.doc.save" not in [action for action, _params in editor.writes]
    assert "conn-duplicate-designators|ERROR|U1||" in " ".join(report["notes"]), (
        "the blocking ERROR is named in the notes, not only counted"
    )


# ------------------------------------------------------- E2: a non-empty page


def _seed(editor: _PageEditor) -> None:
    """What was on the page before: a part, a wire and a flag in the top-left corner."""
    editor.add_part("R9", 80, 700, lcsc="C25744", value="1k", ident="c-old-R9")
    editor.add_wire("OLD", [(80, 750), (200, 750)], ident="w-old-1")
    editor.add_flag("GND", 80, 640, ident="f-old-1")


def test_e2_the_census_becomes_keepouts_and_the_page_goes_around_them(
    monkeypatch, tmp_path, capsys
):
    editor = _PageEditor()
    _seed(editor)
    before = editor.snapshot()
    code, plan_path, circuit, presentation = _plan_page(monkeypatch, tmp_path, editor)
    printed = capsys.readouterr().out
    assert code == 0, printed
    report = json.loads((tmp_path / "plan.report.json").read_text(encoding="utf-8"))
    assert report["live"]["keepouts"] >= 3, "a part, a wire segment and a flag"
    assert any("R9" in row["from"] for row in report["keepouts"])
    boxes = [tuple(row["box"]) for row in report["keepouts"]]
    page = PageLayoutPlan.load(tmp_path / "plan.page.json")
    for module in page.modules:
        for box in boxes:
            overlap = (min(module.frame[2], box[2]) - max(module.frame[0], box[0]) > 0
                       and min(module.frame[3], box[3]) - max(module.frame[1], box[1]) > 0)
            assert not overlap, f"{module.id} sits on {box}"
    plan = ChangePlan.load(plan_path)
    editor.netlists = [{"components": {}}, _netlist_for(plan)]
    code, applied = _apply(editor, plan_path, circuit, presentation, tmp_path)
    assert code == 0, applied["notes"]
    assert applied["range"]["outOfScope"] == {
        "items": 3, "changed": [], "basis": applied["range"]["outOfScope"]["basis"],
    }
    for ident, item in before.items():
        assert editor.items[ident] == item, f"{ident} was touched"


def test_e2_a_page_the_census_fills_is_presentation_poor_naming_what_is_there(
    monkeypatch, tmp_path, capsys
):
    editor = _PageEditor()
    for row in range(8):
        for column in range(12):
            editor.add_part(f"R{100 + row * 12 + column}", 50 + column * 95,
                            60 + row * 100, lcsc="C25744", value="1k")
    code, _plan_path, _circuit, _presentation = _plan_page(monkeypatch, tmp_path, editor)
    captured = capsys.readouterr()
    assert code == 5
    assert "presentation-poor" in captured.err
    assert "existing R1" in captured.err, "the keep-out is named by what is there"
    assert not editor.writes


def test_e2_a_landing_that_changes_an_existing_wire_is_not_saved(
    monkeypatch, tmp_path, capsys
):
    """057 sec.2's hard line: one existing primitive changed = the run failed.

    The existing wire is **unnamed** on purpose: 069 sec.9 draws a flagged net's
    wires without a name (the flag states it), so a wire left by an earlier landing
    of that net is unnamed too, and the fake host merges "every new wire of the same
    net" into it by that name.
    """
    editor = _PageEditor()
    editor.add_wire("", [(1100, 60), (1120, 60)], ident="w-old-gnd")
    code, plan_path, circuit, presentation = _plan_page(monkeypatch, tmp_path, editor)
    assert code == 0
    plan = ChangePlan.load(plan_path)
    if not any(wire.net == "GND" for wire in plan.change.draw_wires):
        pytest.skip("this page draws no GND wire to merge")
    editor.merge_wires_into = "w-old-gnd"
    editor.netlists = [{"components": {}}, _netlist_for(plan)]
    code, report = _apply(editor, plan_path, circuit, presentation, tmp_path)
    assert code == 2
    assert report["reason"] == "range_out_of_scope"
    assert any("w-old-gnd" in line for line in report["range"]["outOfScope"]["changed"])
    assert "sch.doc.save" not in [action for action, _params in editor.writes]


# -------------------------------------------------------------- E3: page locks


def test_e3_a_page_locked_part_reads_back_at_its_lock_point(monkeypatch, tmp_path, capsys):
    editor = _PageEditor()
    lock = {"partId": "R1", "x": 800, "y": 500, "scope": "page"}
    circuit, presentation = write_specs(
        tmp_path, presentation=page_presentation(userLocks=[lock]),
    )
    _stub_editor(monkeypatch, editor)
    _stub_export(monkeypatch)
    out = tmp_path / "plan.json"
    assert cli.main(_plan_args(circuit, presentation, "--page", "page-1", "--out", str(out))) == 0
    plan = ChangePlan.load(out)
    r1 = next(part for part in plan.change.draw_parts if part.spec_id == "R1")
    assert (r1.x, r1.y) == (800.0, 500.0)
    editor.netlists = [{"components": {}}, _netlist_for(plan)]
    code, report = _apply(editor, out, circuit, presentation, tmp_path)
    assert code == 0, report["notes"]
    placed = next(item for item in editor.items.values()
                  if item["kind"] == "part" and item["designator"] == r1.designator)
    assert (placed["x"], placed["y"]) == (800.0, 500.0)


@pytest.mark.parametrize(
    "locks, named",
    [
        (
            [{"partId": "R1", "x": 800, "y": 500, "scope": "page"},
             {"partId": "R2", "x": 800, "y": 500, "scope": "page"}],
            ("userLocks[R1@page]", "userLocks[R2@page]"),
        ),
        ([{"partId": "R1", "x": 5000, "y": 500, "scope": "page"}], ("userLocks[R1@page]",)),
        ([{"partId": "U1", "x": 25, "y": 25, "scope": "page"}], ("userLocks[U1@page]",)),
    ],
    ids=["two-locks-disagree", "lock-off-the-page", "frame-off-the-page"],
)
def test_e3_a_lock_that_cannot_hold_is_presentation_poor_and_named(
    tmp_path, capsys, locks, named
):
    circuit, presentation = write_specs(
        tmp_path, presentation=page_presentation(userLocks=locks),
    )
    code = cli.main(_plan_args(circuit, presentation, "--out", str(tmp_path / "p.json")))
    err = capsys.readouterr().err
    assert code == 5
    assert "presentation-poor" in err
    for name in named:
        assert name in err


# ------------------------------------------------------------- E5: discard


def _landed(monkeypatch, tmp_path, capsys, *, seed=True):
    editor = _PageEditor()
    if seed:
        _seed(editor)
    code, plan_path, circuit, presentation = _plan_page(monkeypatch, tmp_path, editor)
    assert code == 0
    plan = ChangePlan.load(plan_path)
    editor.netlists = [{"components": {}}, _netlist_for(plan)]
    code, _report = _apply(editor, plan_path, circuit, presentation, tmp_path)
    assert code == 0, _report["notes"]
    capsys.readouterr()
    return editor, plan_path, plan, circuit, presentation


def _discard(plan_path, *extra, report_name="discard.json", tmp_path=None):
    target = (tmp_path or Path(plan_path).parent) / report_name
    code = cli.main(["draw", "discard", str(plan_path), "--project", "test",
                     "--json", str(target), *extra])
    return code, json.loads(target.read_text(encoding="utf-8"))


def test_e5_discard_deletes_the_plans_drawing_lines_first_and_nothing_else(
    monkeypatch, tmp_path, capsys
):
    editor, plan_path, plan, _circuit, _presentation = _landed(monkeypatch, tmp_path, capsys)
    old = {ident: item for ident, item in editor.snapshot().items() if "old" in ident}
    writes_before = len(editor.writes)
    code, report = _discard(plan_path, "--save")
    assert code == 0, report["notes"]
    assert report["outcome"] == "discarded"
    phases = [row["phase"] for row in report["deletes"]]
    assert phases == sorted(phases, key=["wires", "flags", "parts"].index)
    assert phases[-1] == "parts" and phases[0] == "wires"
    # Only the seeded primitives are left, exactly as they were.
    assert editor.snapshot() == old
    assert report["verify"]["remaining"] == [] and report["verify"]["outOfScope"] == []
    assert ("sch.doc.save", {}) in editor.writes[writes_before:]


def test_e5_a_second_discard_finds_nothing_and_writes_nothing(monkeypatch, tmp_path, capsys):
    editor, plan_path, _plan, _circuit, _presentation = _landed(monkeypatch, tmp_path, capsys)
    assert _discard(plan_path)[0] == 0
    deletes = len(editor.deletes)
    code, report = _discard(plan_path, report_name="second.json")
    assert code == 0
    assert report["outcome"] == "nothing_to_discard"
    assert len(editor.deletes) == deletes, "idempotent: zero deletes the second time"


def test_e5_one_part_that_is_not_the_plans_refuses_the_whole_batch(
    monkeypatch, tmp_path, capsys
):
    editor, plan_path, plan, _circuit, _presentation = _landed(monkeypatch, tmp_path, capsys)
    victim = plan.change.draw_parts[0]
    for item in editor.items.values():
        if item["kind"] == "part" and item["designator"] == victim.designator:
            item["value"] = "somebody else's value"
    snapshot = editor.snapshot()
    code, report = _discard(plan_path)
    assert code == 4
    assert report["reason"] == "identity_mismatch"
    assert any(victim.designator in line for line in report["selection"]["mismatches"])
    assert not editor.deletes, "not half a batch: nothing is deleted"
    assert editor.snapshot() == snapshot


def test_e5_a_moved_part_refuses_the_whole_batch(monkeypatch, tmp_path, capsys):
    editor, plan_path, plan, _circuit, _presentation = _landed(monkeypatch, tmp_path, capsys)
    victim = plan.change.draw_parts[-1]
    for item in editor.items.values():
        if item["kind"] == "part" and item["designator"] == victim.designator:
            item["x"] += 50
    code, report = _discard(plan_path)
    assert code == 4 and not editor.deletes
    assert any("the plan put it at" in line for line in report["selection"]["mismatches"])


def test_e5_a_wire_the_host_merged_with_a_foreign_one_is_never_deleted(
    monkeypatch, tmp_path, capsys
):
    editor, plan_path, plan, _circuit, _presentation = _landed(monkeypatch, tmp_path, capsys)
    wire = plan.change.draw_wires[0]
    # Found by *geometry*: 069 sec.9 draws a flagged net's wires unnamed, so their
    # net name is no longer what identifies them on the page.
    for item in editor.items.values():
        if item["kind"] == "wire" and list(wire.points[0]) in item["points"]:
            item["points"].append([9999.0, 9999.0])
            break
    code, report = _discard(plan_path)
    assert code == 4 and not editor.deletes
    assert any("merged" in line for line in report["selection"]["mismatches"])


def test_e5_a_delete_that_times_out_is_read_back_and_never_retried(
    monkeypatch, tmp_path, capsys
):
    editor, plan_path, _plan, _circuit, _presentation = _landed(monkeypatch, tmp_path, capsys)
    editor.timeouts = {"sch.delete_primitives"}
    code, report = _discard(plan_path, "--save")
    assert code == 3
    assert report["reason"] == "delete_unanswered"
    assert editor.calls.count("sch.delete_primitives") == 1
    assert "sch.doc.save" not in editor.calls[-3:]


def test_e5_a_page_document_is_discarded_by_position(monkeypatch, tmp_path, capsys):
    editor, _plan_path, plan, circuit, presentation = _landed(monkeypatch, tmp_path, capsys)
    old = {ident: item for ident, item in editor.snapshot().items() if "old" in ident}
    code, report = _discard(
        tmp_path / "plan.page.json", "--page", "page-1", "--circuit", str(circuit),
        "--presentation", str(presentation), "--profiles", str(LIBRARY),
    )
    assert code == 0, report["notes"]
    assert report["identifiedBy"].startswith("position")
    assert editor.snapshot() == old


# ------------------------------------------------------ E7: a stale page plan


def test_e7_a_changed_canvas_refuses_the_old_plan_before_any_write(
    monkeypatch, tmp_path, capsys
):
    editor = _PageEditor()
    code, plan_path, circuit, presentation = _plan_page(monkeypatch, tmp_path, editor)
    assert code == 0
    editor.add_part("R50", 1000, 100, lcsc="C25744", value="1k")
    code, report = _apply(editor, plan_path, circuit, presentation, tmp_path)
    assert code == 4
    assert report["reason"] == "canvas_changed"
    assert not editor.writes


def test_e7_a_page_document_whose_frames_were_built_on_is_refused(
    monkeypatch, tmp_path, capsys
):
    circuit, presentation = write_specs(tmp_path)
    out = tmp_path / "previews"
    assert cli.main([
        "draw", "compile", "--circuit", str(circuit), "--presentation", str(presentation),
        "--profiles", str(LIBRARY), "--page-box", PAGE_BOX, "--out", str(out),
    ]) == 0
    capsys.readouterr()
    document = PageLayoutPlan.load(out / "cand1.page.json")
    frame = document.modules[0].frame
    editor = _PageEditor()
    editor.add_part("R77", (frame[0] + frame[2]) / 2, (frame[1] + frame[3]) / 2,
                    lcsc="C25744", value="1k")
    _stub_editor(monkeypatch, editor)
    _stub_export(monkeypatch)
    code, report = _apply(editor, out / "cand1.page.json", circuit, presentation, tmp_path,
                          "--page", "page-1")
    assert code == 4
    assert report["reason"] == "canvas_changed"
    assert any("R77" in line for line in report["guards"]["problems"])
    assert not editor.writes


def test_a_page_document_lands_directly_on_a_free_page(monkeypatch, tmp_path, capsys):
    """057 sec.1: `draw apply page.json` passes the `plan` field to the same flow."""
    circuit, presentation = write_specs(tmp_path)
    out = tmp_path / "previews"
    assert cli.main([
        "draw", "compile", "--circuit", str(circuit), "--presentation", str(presentation),
        "--profiles", str(LIBRARY), "--page-box", PAGE_BOX, "--out", str(out),
    ]) == 0
    capsys.readouterr()
    document = out / "cand1.page.json"
    page = PageLayoutPlan.load(document)
    editor = _PageEditor()
    _stub_editor(monkeypatch, editor)
    _stub_export(monkeypatch)
    rebuilt = cli._draw_plan_from_page(
        page, *cli._draw_inputs(type("A", (), {
            "circuit": str(circuit), "presentation": str(presentation),
            "profiles": str(LIBRARY)})()),
    )
    editor.netlists = [{"components": {}}, _netlist_for(rebuilt)]
    code, report = _apply(editor, document, circuit, presentation, tmp_path, "--page", "page-1")
    assert code == 0, report["notes"]
    assert report["document"] == "page"
    assert report["builtPlan"]["change"]["layoutSha256"] == page.plan.geometry_sha256()
    assert report["guards"]["checked"]["layoutSha256"] is True


def test_a_page_document_compiled_from_other_specs_is_refused_offline(
    monkeypatch, tmp_path, capsys
):
    circuit, presentation = write_specs(tmp_path)
    out = tmp_path / "previews"
    assert cli.main([
        "draw", "compile", "--circuit", str(circuit), "--presentation", str(presentation),
        "--profiles", str(LIBRARY), "--page-box", PAGE_BOX, "--out", str(out),
    ]) == 0
    changed = page_circuit()
    changed["parts"][3]["value"] = "12k"
    circuit.write_text(json.dumps(changed), encoding="utf-8")
    opened = []
    monkeypatch.setattr(cli, "_open_cli", lambda args: opened.append(1) or (_ for _ in ()).throw(
        AssertionError("the daemon must not be contacted")))
    code, report = _apply(None, out / "cand1.page.json", circuit, presentation, tmp_path,
                          "--page", "page-1")
    assert code == 4 and report["reason"] == "guard_refused"
    assert not opened


def test_a_page_document_needs_its_specs(tmp_path, capsys):
    circuit, presentation = write_specs(tmp_path)
    out = tmp_path / "previews"
    assert cli.main([
        "draw", "compile", "--circuit", str(circuit), "--presentation", str(presentation),
        "--profiles", str(LIBRARY), "--page-box", PAGE_BOX, "--out", str(out),
    ]) == 0
    code = cli.main(["draw", "apply", str(out / "cand1.page.json"), "--page", "page-1"])
    assert code == 5
    assert "--circuit" in capsys.readouterr().err


def test_a_layout_guard_given_another_page_refuses(monkeypatch, tmp_path, capsys):
    editor = _PageEditor()
    code, plan_path, circuit, presentation = _plan_page(monkeypatch, tmp_path, editor)
    assert code == 0
    other = tmp_path / "other"
    assert cli.main([
        "draw", "compile", "--circuit", str(circuit), "--presentation", str(presentation),
        "--profiles", str(LIBRARY), "--page-box", PAGE_BOX, "--out", str(other),
    ]) == 0
    pages = sorted(other.glob("cand*.page.json"))
    mine = PageLayoutPlan.load(tmp_path / "plan.page.json").page_geometry_sha256()
    foreign = next(
        (path for path in pages if PageLayoutPlan.load(path).page_geometry_sha256() != mine),
        None,
    )
    if foreign is None:
        pytest.skip("the compile produced a single page")
    code, report = _apply(editor, plan_path, circuit, presentation, tmp_path,
                          "--layout", str(foreign))
    assert code == 4 and report["reason"] == "guard_refused"
    assert not editor.writes
