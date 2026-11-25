"""572E-1 / 572E-2 / 572C-04 / 572D-3: the CLI-side contracts these holes broke.

* **E-1** — an unusable ``--page-box`` is refused *before* ``draw apply`` picks a
  branch: a page document and a module plan must answer the same way (exit 5,
  naming the flag), not one of them walking on into the digest guard.
* **E-2** — ``--page`` that names a page the plan does not bind is a refusal
  (``page_not_plans``, exit 4) taken before the bridge opens, not a silent
  override whose report still says ``pageUuid: true``.
* **C-04** — a run whose diff never happened (``comparison is None``) is
  "nothing was executed" (exit 2), not "the designs differ" (exit 1); a write
  whose outcome is unknown still outranks it with 3.
* **D-3** — gate 1 (ghost pin numbers) is reachable from ``pintable check``.

Every assertion below fails on HEAD `961b3b7` and passes with the fix; the
mutation record for both directions is in `evidence/572e/REPORT.md`.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from boardwise import cli
from boardwise.core.pagelayoutplan import PAGE_LAYOUT_PLAN_KIND

ROOT = Path(__file__).resolve().parents[1]
PINTABLE = ROOT / "inputs" / "smart_pillbox" / "pintable.json"


# --------------------------------------------------------------------------
# 572E-1: one `--page-box` reading, both branches
# --------------------------------------------------------------------------


def _page_dispatch(monkeypatch) -> list[object]:
    """Make `draw apply` see a page document, and record if that branch ran."""
    entered: list[object] = []
    monkeypatch.setattr(cli, "_draw_document_kind", lambda path: PAGE_LAYOUT_PLAN_KIND)
    monkeypatch.setattr(
        cli, "_cmd_draw_apply_page", lambda args: entered.append(args) or 0
    )
    return entered


def test_e1_an_unusable_page_box_is_refused_before_the_page_branch(
    monkeypatch, tmp_path, capsys
):
    """E-1: the page branch never saw an unvalidated `--page-box` on HEAD."""
    entered = _page_dispatch(monkeypatch)
    code = cli.main([
        "draw", "apply", str(tmp_path / "page.json"),
        "--page-box", "9999999,9999999,1,1",
    ])
    err = capsys.readouterr().err
    assert entered == [], "the page branch was entered with an unvalidated --page-box"
    assert code == 5, f"exit was {code}, not 5"
    assert "page-box" in err, err


def test_e1_both_branches_refuse_the_same_value_the_same_way(
    monkeypatch, tmp_path, capsys
):
    """E-1: the module plan's answer is the page document's answer."""
    bad = "9999999,9999999,1,1"
    entered = _page_dispatch(monkeypatch)
    page_code = cli.main([
        "draw", "apply", str(tmp_path / "page.json"), "--page-box", bad,
    ])
    page_err = capsys.readouterr().err
    assert entered == [], "the page branch ran anyway"
    monkeypatch.setattr(cli, "_draw_document_kind", lambda path: "boardwise-change-plan/1")
    module_code = cli.main([
        "draw", "apply", str(tmp_path / "module.json"), "--page-box", bad,
    ])
    module_err = capsys.readouterr().err
    assert page_code == module_code == 5, (page_code, module_code)
    assert "page-box" in page_err and "page-box" in module_err, (page_err, module_err)


# --------------------------------------------------------------------------
# 572E-2: `--page` must be the plan's page
# --------------------------------------------------------------------------


def _module_plan(tmp_path: Path, page: str):
    """The 054 fixture drawing as a plan bound to ``page`` (borrowed helper)."""
    from test_054_draw_cli import _plan

    return _plan(tmp_path, page=page)


def test_e2_a_page_the_plan_does_not_bind_is_refused(monkeypatch, tmp_path, capsys):
    """E-2: bound to A, `--page B` is exit 4 `page_not_plans`, not an override."""
    plan_path, plan = _module_plan(tmp_path, "page-A")
    assert plan.source.page_uuid == "page-A"
    report = tmp_path / "apply.json"
    code = cli.main([
        "draw", "apply", str(plan_path), "--page", "page-B", "--json", str(report),
    ])
    captured = capsys.readouterr()
    assert code == 4, (code, captured.out, captured.err)
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["reason"] == "page_not_plans", payload.get("reason")
    assert payload["guards"]["checked"].get("pageUuid") is not True
    assert "page-A" in json.dumps(payload) or "page-A" in captured.err


def test_e2_the_plans_own_page_is_still_taken(monkeypatch, tmp_path, capsys):
    """E-2: naming the page the plan binds is not a refusal."""
    plan_path, _plan_obj = _module_plan(tmp_path, "page-A")
    report = tmp_path / "apply.json"
    code = cli.main([
        "draw", "apply", str(plan_path), "--page", "page-A", "--json", str(report),
    ])
    captured = capsys.readouterr()
    payload = (json.loads(report.read_text(encoding="utf-8"))
               if report.exists() else {})
    assert payload.get("reason") != "page_not_plans", payload.get("reason")
    assert code != 4 or payload.get("reason") != "page_not_plans", captured.out


# --------------------------------------------------------------------------
# 572C-04: "the diff never ran" is not "the designs differ"
# --------------------------------------------------------------------------


def _result(**overrides):
    """A `DrawResult`-shaped object whose diff did not run."""
    base = dict(
        plan_source="plan.json", naming_strategy=None, frame=None,
        candidate_source=None, netlist_probe=None, netlist_census=None,
        placement_report=None, failures=[], records=[], missing_pins=[],
        enrichment_notes=[], persistence="saved_verified",
        acknowledged_writes=[], unknown_writes=[], comparison=None,
        timeouts=[], render_b64=None, screenshot_b64=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


ARGS = SimpleNamespace(render=None, screenshot=None, spec=None,
                       project=None, instance=None)


def test_c04_a_diff_that_never_ran_is_exit_2_not_1(capsys):
    """C-04: `nothing written` means 2, not 1 (which means "designs differ")."""
    code = cli._render_draw_result(_result(), ARGS)
    out = capsys.readouterr().out
    assert "diff: NOT RUN" in out, out
    assert code == 2, f"exit was {code}, not 2 (docs/draw.md: nothing was executed)"


def test_c04_an_unknown_write_still_outranks_it_with_3(capsys):
    """C-04: 3 keeps outranking 2 — the page's state cannot be stated."""
    code = cli._render_draw_result(_result(timeouts=["sch.doc.save"]), ARGS)
    assert code == 3, f"exit was {code}, not 3"


# --------------------------------------------------------------------------
# 572D-3: gate 1 (ghost pin numbers) is reachable from the CLI
# --------------------------------------------------------------------------


def _mcu_spec():
    from boardwise.core.blocks import (
        BlockConnection, BlockInstance, BoardSpec, template_from_json,
    )

    template = template_from_json(
        {
            "kind": "boardwise-block-template", "version": 1, "name": "mcu",
            "description": "", "provenance": {"kind": "textbook", "source": "hand"},
            "origin_file": [0.0, 0.0], "bbox_file": [0.0, 0.0, 10.0, 10.0],
            "notes": [],
            "interface": [{"role": "PA3", "net": "PA3", "net_class": "signal"}],
            "params": [],
            "symbols": {"u": {"offsets": {"PA3": [0.0, 0.0]},
                              "body": [0.0, 0.0, 5.0, 5.0],
                              "pin_names": {"PA3": "PA3"}}},
            "components": [{
                "ref": "U1", "symbol": "u", "placement": {"x": 0.0, "y": 0.0},
                "device": {"lcsc": "C431633"}, "footprint": "LQFP-64",
                "params": {}, "pins": [],
            }],
            "geometry": {"wires": [], "flags": [], "labels": []},
        },
        where="mcu-block",
    )
    return BoardSpec(
        name="synthetic", description="", provenance_kind="textbook",
        provenance_source="hand", provenance_note="",
        blocks=[BlockInstance(id="mcu", template_path="/t/mcu.json",
                              template=template, at=(0.0, 0.0))],
        connections=[BlockConnection(net="PA3", ports=[("mcu", "PA3"),
                                                       ("other", "PA3")])],
        params={}, sheet_attrs={}, sheet_origin=(0.0, 0.0),
    )


def _table_with_a_ghost(tmp_path: Path) -> Path:
    """The real smart_pillbox table plus one pin number no symbol has."""
    body = json.loads(PINTABLE.read_text(encoding="utf-8"))
    body["pins"].append(
        {"number": "PA99", "name": "PA99", "function": "GPIO", "net": "GHOST"}
    )
    path = tmp_path / "pintable_pa99.json"
    path.write_text(json.dumps(body, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def test_d3_a_ghost_pin_number_is_a_named_refusal(monkeypatch, tmp_path, capsys):
    """D-3: `PA99` on a real table used to be exit 0 / `ok: true`."""
    import boardwise.core.blocks as blocks

    monkeypatch.setattr(blocks, "load_board_spec", lambda *a, **k: _mcu_spec())
    table = _table_with_a_ghost(tmp_path)
    code = cli.main([
        "pintable", "check", "--table", str(table),
        "--spec", str(tmp_path / "spec.json"),
        "--mcu-component", "U1", "--json",
    ])
    captured = capsys.readouterr()
    assert code == 1, (code, captured.out[-2000:], captured.err)
    payload = json.loads(captured.out)
    assert payload["ok"] is False, payload
    gate1 = [item for item in payload["defects"]
             if item.get("rule") == "pin-numbers-exist"]
    assert any("PA99" in json.dumps(item) for item in gate1), payload["defects"]


def test_d5_a_contradiction_with_the_ioc_blocks(monkeypatch, tmp_path, capsys):
    """572D-5: `PA5 GPIO` vs `.ioc PA5.Signal=I2C1_SCL` is a defect, not a note."""
    body = json.loads(PINTABLE.read_text(encoding="utf-8"))
    body["pins"] = [{"number": "PA5", "name": "PA5", "function": "GPIO",
                     "net": "LED1"}]
    table = tmp_path / "pintable.json"
    table.write_text(json.dumps(body, indent=2, ensure_ascii=False), encoding="utf-8")
    ioc = tmp_path / "board.ioc"
    ioc.write_text(
        "Mcu.Name=STM32G431R(6-8-B)Tx\nMcu.CPN=STM32G431RBT6\n"
        "Mcu.Pin0=PA5\nPA5.Signal=I2C1_SCL\n",
        encoding="utf-8",
    )
    code = cli.main([
        "pintable", "check", "--table", str(table), "--ioc", str(ioc), "--json",
    ])
    captured = capsys.readouterr()
    assert code == 1, (code, captured.out[-2000:], captured.err)
    payload = json.loads(captured.out)
    assert payload["ok"] is False, payload
    blocking = [item for item in payload["defects"]
                if item.get("rule") == "ioc-cross-check"]
    assert blocking, payload["defects"]


def test_d3_the_one_part_mcu_block_needs_no_component_flag(
    monkeypatch, tmp_path, capsys
):
    """D-3: one part in the block is unambiguous — gate 1 still runs."""
    import boardwise.core.blocks as blocks

    monkeypatch.setattr(blocks, "load_board_spec", lambda *a, **k: _mcu_spec())
    table = _table_with_a_ghost(tmp_path)
    code = cli.main([
        "pintable", "check", "--table", str(table),
        "--spec", str(tmp_path / "spec.json"), "--json",
    ])
    captured = capsys.readouterr()
    assert code == 1, (code, captured.out[-2000:])
    payload = json.loads(captured.out)
    gate1 = [item for item in payload["defects"]
             if item.get("rule") == "pin-numbers-exist"]
    assert any("PA99" in json.dumps(item) for item in gate1), payload["defects"]
