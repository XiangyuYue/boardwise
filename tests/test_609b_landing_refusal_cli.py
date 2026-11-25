"""609-b: `LandingRefused` reaches the CLI as the same named exit-5 refusal.

609 made `landing_spot` refuse a non-finite anchor (a `ValueError`) instead of
returning a `nan` spot, but `edit plan --add-component` only caught
`LadderExhausted`, so the real command died with a bare traceback. These cases
run the **real** `cli.main` against a fake bridge and never touch
`landing_spot` itself: the NaN comes in through `sch.geometry`, exactly where a
degenerate page would carry it.

The neighbours are pinned too, so the fix cannot buy the NaN case by widening
the channel: an exhausted ladder keeps its own text, and a legal page still
plans at the ladder's first free rung.
"""

from __future__ import annotations

import json

import test_029a_addcomponent as b029

from boardwise import cli
from boardwise.core.changeplan import ADD_COMPONENT_KIND, ChangePlan
from boardwise.engines.addcomponent import LADDER


def _report(tmp_path, anchor="U1"):
    report = tmp_path / "r.json"
    report.write_text(json.dumps({"findings": [{
        "rule_id": "decap-required-caps", "severity": "WARN", "message": "m",
        "target": {"component_ref": anchor, "pin_refs": ["1"], "net_refs": ["VCC"],
                   "suggested_after": "0.1uF"},
    }]}), encoding="utf-8")
    return report


def _run_plan(tmp_path, capsys, report, *extra):
    snap = tmp_path / "s.epro2"
    snap.write_bytes(b"x")
    code = cli.main(["edit", "plan", "--file", str(snap), "--rule",
                     "decap-required-caps", "--designator", "U1",
                     "--report", str(report), "--lcsc", "C1525", *extra])
    captured = capsys.readouterr()
    return code, captured


def test_a_non_finite_anchor_refuses_with_exit_five_and_no_plan(
    monkeypatch, tmp_path, capsys
):
    """The 609 regression: a NaN origin is a named refusal, not a traceback."""
    bridge = b029._FakeBridge(
        geometry=b029._geometry(components=[("U1", float("nan"), 0.0), ("C3", 40.0, 40.0)])
    )
    b029._stub_bridge(monkeypatch, bridge)
    out_path = tmp_path / "plan.json"

    code, captured = _run_plan(
        tmp_path, capsys, _report(tmp_path), "-o", str(out_path)
    )

    assert code == 5, f"a non-finite origin must refuse, got {code}: {captured.out}"
    err = captured.err
    assert "Traceback" not in err, err
    assert "landing origin" in err and "not finite" in err, err
    assert "No plan is written" in err, "the refusal says no plan was written"
    assert "finite coordinate" in err, "and what the operator has to repair"
    assert not out_path.exists(), "a refused plan must not leave a plan file behind"
    assert bridge.writes == [], "a refused plan must not write to the page"


def test_a_non_finite_anchor_is_not_mistaken_for_an_exhausted_ladder(
    monkeypatch, tmp_path, capsys
):
    """The message names the actual cause, so the operator repairs the right thing."""
    bridge = b029._FakeBridge(geometry=b029._geometry(components=[("U1", 0.0, float("inf"))]))
    b029._stub_bridge(monkeypatch, bridge)

    code, captured = _run_plan(tmp_path, capsys, _report(tmp_path))

    assert code == 5
    err = captured.err
    assert "Traceback" not in err, err
    assert "landing origin" in err and "not finite" in err, err
    assert "no free landing spot" not in err, (
        "an unwalkable ladder is not an exhausted one: the ladder never tried a rung"
    )


def test_an_exhausted_ladder_keeps_its_own_refusal(monkeypatch, tmp_path, capsys):
    """609-b must not widen the channel into `landing_spot`'s other refusal."""
    occupied = [("U1", 0.0, 0.0)] + [
        (f"C{10 + index}", dx * 5.0, dy * 5.0)
        for index, (dx, dy) in enumerate(LADDER[1:])
    ]
    bridge = b029._FakeBridge(geometry=b029._geometry(components=occupied))
    b029._stub_bridge(monkeypatch, bridge)

    code, captured = _run_plan(tmp_path, capsys, _report(tmp_path))

    assert code == 5
    assert "no free landing spot" in captured.err
    assert "绝不放原点" in captured.err
    assert "not finite" not in captured.err


def test_a_legal_page_still_plans_at_the_first_free_rung(monkeypatch, tmp_path, capsys):
    """Negative control: the fix must not turn a good plan into a refusal."""
    geometry = b029._geometry(
        components=[("U1", 0.0, 0.0), ("C3", 40.0, 40.0)],
        wires=[[(0.0, 0.0), (10.0, 0.0)], [(0.0, 999.0), (5.0, 999.0)]],
    )
    bridge = b029._FakeBridge(geometry=geometry)
    b029._stub_bridge(monkeypatch, bridge)
    out_path = tmp_path / "plan.json"

    code, captured = _run_plan(
        tmp_path, capsys, _report(tmp_path), "-o", str(out_path)
    )

    assert code == 0, captured.err
    plan = ChangePlan.load(out_path)
    assert plan.change.kind == ADD_COMPONENT_KIND
    assert (plan.target.x, plan.target.y) == (0.0, -5.0)
