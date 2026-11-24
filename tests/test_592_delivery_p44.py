"""592 W-R3: a compile's success states a delivery that is not an acceptance.

hole568 D-6 measured the gap: a real ``draw compile`` exited 0 with ``ok: true``
and printed none of the P44 readings the drawing SOP requires, so a missing
checklist item could not lower the answer. ``delivery`` is that checklist and it
is stated, never granted: the compile's ``ok`` keeps its meaning (a legal
candidate came out), the delivery says ``ok: false, status: "unverified"``, and
P3/P4 are recomputed here from the written plan with plain arithmetic rather
than read back from the code that printed them.
"""

from __future__ import annotations

import json
from pathlib import Path

from boardwise import cli
from boardwise.core.layoutplan import (
    LayoutPart,
    LayoutPlan,
    LayoutSegment,
    ROUTE_AGENT_ADJUSTED,
    ROUTE_AUTOMATIC,
)
from boardwise.core.pagelayoutplan import PageLayoutPlan

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "drawapply"
LIBRARY = FIXTURES / "library.json"
CIRCUIT = FIXTURES / "divider.circuit.json"
PRESENTATION = FIXTURES / "divider.presentation.json"
PAGE_BOX = "0,-1000,1200,0"
PROV = "verified_recipe"
HASH = "a" * 64


# ------------------------------------------------------------------ fixtures


def _compile(tmp_path: Path, *, page: bool = False) -> tuple[int, dict, Path]:
    out = tmp_path / "previews"
    report = tmp_path / "compile.json"
    circuit, presentation = CIRCUIT, PRESENTATION
    if page:
        circuit, presentation = _page_specs(tmp_path)
    code = cli.main([
        "draw", "compile",
        "--circuit", str(circuit), "--presentation", str(presentation),
        "--profiles", str(LIBRARY), "--page-box", PAGE_BOX,
        "--out", str(out), "--json", str(report),
    ])
    return code, json.loads(report.read_text(encoding="utf-8")), out


def _page_specs(tmp_path: Path) -> tuple[Path, Path]:
    circuit = {"parts": [
        {"id": "U1", "symbolRef": "AMS1117-3.3", "value": "AMS1117-3.3",
         "lcsc": "C6186", "provenance": PROV},
        {"id": "C1", "symbolRef": "C0402", "value": "10uF", "lcsc": "C15525",
         "provenance": PROV},
        {"id": "R1", "symbolRef": "R0402", "value": "10k", "lcsc": "C25744",
         "provenance": PROV},
        {"id": "R2", "symbolRef": "R0402", "value": "10k", "lcsc": "C25744",
         "provenance": PROV},
    ], "nets": [
        {"id": "VIN", "class": "power", "members": ["U1.3", "C1.1", "R1.1"],
         "provenance": PROV},
        {"id": "3V3", "class": "power", "members": ["U1.2"], "provenance": PROV},
        {"id": "TAP", "class": "signal", "members": ["R1.2", "R2.1"],
         "provenance": PROV},
        {"id": "GND", "class": "gnd", "members": ["U1.1", "C1.2", "R2.2"],
         "provenance": PROV},
    ]}
    presentation = {
        "modules": [
            {"id": "pwr", "parts": ["U1", "C1"], "role": "regulator",
             "grammarRef": "ldo"},
            {"id": "sense", "parts": ["R1", "R2"], "role": "divider",
             "grammarRef": "voltage-divider"},
        ],
        "flow": [["pwr", "sense"]],
        "portRoles": {"VIN": "input", "3V3": "output"},
    }
    circuit_path = tmp_path / "page.circuit.json"
    presentation_path = tmp_path / "page.presentation.json"
    circuit_path.write_text(json.dumps(circuit), encoding="utf-8")
    presentation_path.write_text(json.dumps(presentation), encoding="utf-8")
    return circuit_path, presentation_path


def _p3_rows(plan: dict) -> tuple[list[dict], dict, dict | None]:
    """P3 recomputed from the plan body alone: sub-edge sums, no helper.

    Straight Manhattan runs have ``path == direct``, so a wrong ``excess`` on
    them would still read zero; the detour case below is what pins the formula.
    """
    rows: list[dict] = []
    by_net: dict[str, dict] = {}
    worst: dict | None = None
    for index, segment in enumerate(plan["segments"]):
        points = [(float(x), float(y)) for x, y in segment["points"]]
        path = 0.0
        for (ax, ay), (bx, by) in zip(points, points[1:]):
            path += abs(bx - ax) + abs(by - ay)
        direct = (
            abs(points[-1][0] - points[0][0]) + abs(points[-1][1] - points[0][1])
            if len(points) >= 2 else 0.0
        )
        excess = path - direct
        rows.append({
            "index": index, "net": segment["net"], "points": len(points),
            "path": path, "direct": direct, "excess": excess,
        })
        aggregate = by_net.setdefault(
            segment["net"], {"segments": 0, "path": 0.0, "direct": 0.0, "excess": 0.0}
        )
        aggregate["segments"] += 1
        aggregate["path"] += path
        aggregate["direct"] += direct
        aggregate["excess"] += excess
        if worst is None or excess > worst["excess"]:
            worst = {"net": segment["net"], "index": index, "excess": excess}
    return rows, by_net, worst


def _p4_span(plan: dict) -> list[float]:
    xs = [float(part["x"]) for part in plan["parts"]]
    ys = [float(part["y"]) for part in plan["parts"]]
    if not xs:
        return [0.0, 0.0]
    return [max(xs) - min(xs), max(ys) - min(ys)]


def _delivery_lines(stdout: str) -> list[str]:
    return [
        line.strip() for line in stdout.splitlines()
        if line.strip().startswith("delivery:") or line.strip().startswith("P44-P")
    ]


# ------------------------------------------------------------------- module


def test_a_successful_compile_states_an_unverified_delivery(tmp_path, capsys) -> None:
    code, payload, out = _compile(tmp_path)
    printed = capsys.readouterr().out
    assert code == 0, printed
    # the compile's own answer and the candidate's geometry keep their meaning
    assert payload["ok"] is True
    plan = LayoutPlan.load(out / "cand1.layout.json")
    assert payload["candidates"][0]["geometrySha256"] == plan.geometry_sha256()

    delivery = payload["delivery"]
    assert delivery["ok"] is False, "a compile is not an acceptance"
    assert delivery["status"] == "unverified"
    assert delivery["visualReview"] == "required"
    assert delivery["route"] == plan.route == ROUTE_AUTOMATIC
    assert delivery["scope"] == "single-module" and delivery["candidate"] == 0
    assert delivery["missing"] == []
    assert list(delivery["p44"]) == ["P1", "P2", "P3", "P4"]
    for item in ("P1", "P2", "P3", "P4"):
        assert delivery["p44"][item]["status"] == "unverified", item
        assert delivery["p44"][item]["reason"], item
    # P1/P2 state counts and say the counts cannot establish a functional group
    assert delivery["p44"]["P1"]["countsProveNothing"]
    assert delivery["p44"]["P2"]["countsProveNothing"]
    assert delivery["p44"]["P1"]["counts"]["parts"] == len(plan.parts)


def test_a_successful_page_compile_states_the_same_delivery(tmp_path, capsys) -> None:
    code, payload, out = _compile(tmp_path, page=True)
    printed = capsys.readouterr().out
    assert code == 0, printed
    assert payload["ok"] is True and payload["document"] == "page"
    page = PageLayoutPlan.load(out / "cand1.page.json")
    delivery = payload["delivery"]
    assert delivery["ok"] is False and delivery["status"] == "unverified"
    assert delivery["visualReview"] == "required"
    assert delivery["scope"] == "page" and delivery["candidate"] == 0
    assert delivery["route"] == page.plan.route == ROUTE_AUTOMATIC
    assert list(delivery["p44"]) == ["P1", "P2", "P3", "P4"]
    assert delivery["missing"] == []
    for item in ("P1", "P2", "P3", "P4"):
        assert delivery["p44"][item]["status"] == "unverified", item
    # the page's readings describe the merged drawing, not one module
    assert delivery["p44"]["P1"]["counts"]["parts"] == len(page.plan.parts)
    assert len(delivery["p44"]["P3"]["segments"]) == len(page.plan.segments)


# ------------------------------------------------------------------- console


def test_the_console_prints_delivery_and_all_four_p44_lines(tmp_path, capsys) -> None:
    code, payload, _ = _compile(tmp_path)
    printed = capsys.readouterr().out
    assert code == 0, printed
    lines = _delivery_lines(printed)
    assert len(lines) == 5, lines
    assert lines[0] == (
        "delivery: UNVERIFIED — route automatic, visual review required "
        "(single-module candidate 0; compile ok is not an acceptance)"
    )
    for position, item in enumerate(("P1", "P2", "P3", "P4"), start=1):
        assert lines[position].startswith(f"P44-{item} unverified:"), lines[position]
    p44 = payload["delivery"]["p44"]
    span = p44["P4"]["span"]
    assert f"[{span[0]:g}, {span[1]:g}]" in printed
    assert f"{p44['P1']['counts']['parts']} part(s)" in printed
    assert f"{len(p44['P3']['segments'])} segment(s)" in printed


def test_the_page_console_prints_the_same_five_lines(tmp_path, capsys) -> None:
    code, payload, _ = _compile(tmp_path, page=True)
    printed = capsys.readouterr().out
    assert code == 0, printed
    lines = _delivery_lines(printed)
    assert len(lines) == 5, lines
    assert "delivery: UNVERIFIED" in lines[0]
    assert "page candidate 0" in lines[0]
    for position, item in enumerate(("P1", "P2", "P3", "P4"), start=1):
        assert lines[position].startswith(f"P44-{item} unverified:"), lines[position]


# ------------------------------------------------------------------ readings


def test_p3_recomputes_every_segment_from_the_written_plan(tmp_path, capsys) -> None:
    code, payload, out = _compile(tmp_path)
    capsys.readouterr()
    assert code == 0
    body = json.loads((out / "cand1.layout.json").read_text(encoding="utf-8"))
    rows, by_net, worst = _p3_rows(body)
    p3 = payload["delivery"]["p44"]["P3"]
    assert len(p3["segments"]) == len(body["segments"]) == len(rows)
    for stated, recomputed in zip(p3["segments"], rows):
        assert stated["index"] == recomputed["index"]
        assert stated["net"] == recomputed["net"]
        assert stated["points"] == recomputed["points"]
        assert stated["path"] == recomputed["path"], stated
        assert stated["direct"] == recomputed["direct"], stated
        assert stated["excess"] == recomputed["excess"], stated
    assert set(p3["byNet"]) == set(by_net)
    for net, aggregate in by_net.items():
        stated = p3["byNet"][net]
        assert stated["segments"] == aggregate["segments"], net
        for key in ("path", "direct", "excess"):
            assert stated[key] == aggregate[key], (net, key)
    assert p3["maxExcess"] == worst


def test_p3_reports_a_real_detour_and_its_excess() -> None:
    plan = LayoutPlan(
        parts=[LayoutPart(part_id="R1", symbol_ref="R0402", symbol_hash=HASH,
                          x=0.0, y=0.0)],
        segments=[
            LayoutSegment(net="STRAIGHT", points=[(0.0, 0.0), (100.0, 0.0)]),
            # down, right and back left: the reader sees 220 units of wire to
            # reach a point 100 units away on the Manhattan metric.
            LayoutSegment(net="DETOUR", points=[
                (0.0, 0.0), (100.0, 0.0), (100.0, 60.0), (40.0, 60.0),
            ]),
        ],
    )
    delivery = cli._draw_delivery(plan, scope="single-module")
    p3 = delivery["p44"]["P3"]
    straight, detour = p3["segments"]
    assert (straight["path"], straight["direct"], straight["excess"]) == (100.0, 100.0, 0.0)
    assert (detour["path"], detour["direct"], detour["excess"]) == (220.0, 100.0, 120.0)
    assert p3["byNet"]["DETOUR"] == {
        "segments": 1, "path": 220.0, "direct": 100.0, "excess": 120.0,
    }
    assert p3["maxExcess"] == {"net": "DETOUR", "index": 1, "excess": 120.0}
    # a detour is a diagnostic, never a rejection: the status stays unverified
    assert p3["status"] == "unverified" and delivery["ok"] is False


def test_p4_span_recomputes_from_part_origins_and_is_zero_when_empty(
    tmp_path, capsys
) -> None:
    code, payload, out = _compile(tmp_path)
    capsys.readouterr()
    assert code == 0
    body = json.loads((out / "cand1.layout.json").read_text(encoding="utf-8"))
    span = _p4_span(body)
    p4 = payload["delivery"]["p44"]["P4"]
    assert p4["span"] == span
    assert p4["parts"] == len(body["parts"])

    empty = cli._draw_delivery(LayoutPlan(), scope="single-module")
    assert empty["p44"]["P4"]["span"] == [0.0, 0.0]
    assert empty["p44"]["P4"]["parts"] == 0
    assert empty["p44"]["P3"]["maxExcess"] is None


# -------------------------------------------------------------- not invented


def test_a_zero_candidate_compile_carries_no_delivery(tmp_path, capsys) -> None:
    spec = json.loads(CIRCUIT.read_text(encoding="utf-8"))
    spec["nets"][1]["members"] = ["R1.2", "R2.9"]
    broken = tmp_path / "broken.circuit.json"
    broken.write_text(json.dumps(spec), encoding="utf-8")
    report = tmp_path / "compile.json"
    code = cli.main([
        "draw", "compile", "--circuit", str(broken),
        "--presentation", str(PRESENTATION), "--profiles", str(LIBRARY),
        "--page-box", PAGE_BOX, "--out", str(tmp_path / "out"),
        "--json", str(report),
    ])
    printed = capsys.readouterr().out
    assert code == 5
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["ok"] is False
    assert "delivery" not in payload, "no drawing, no delivery: recovery is the answer"
    assert "P44-P" not in printed and "delivery: UNVERIFIED" not in printed
    assert payload["recovery"]["route"] == ROUTE_AGENT_ADJUSTED
