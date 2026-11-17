"""548P: a joint seat may change row, and a refused trial owns no geometry."""

from __future__ import annotations

from boardwise.engines import drawcompiler as dc
from test_548n_group_seat import _book, _budget, _circuit, _prepared, _spec


def test_a_service_row_leaves_the_host_a_real_ground_flag():
    circuit, spec, book = _circuit(), _spec(), _book()
    result = dc.compile(circuit, spec, book, _budget())
    assert result.ok, [item.detail for item in result.failures]
    plan = result.best()
    assert plan is not None
    assert sum(flag.net == "GND" for flag in plan.power_symbols) == 1


def test_refused_row_trials_restore_the_input_placement(monkeypatch):
    circuit, spec, book = _circuit(), _spec(), _book()
    ctx = _prepared(circuit, spec, book)
    placed, failure = dc._place_chain_and_shelf(ctx, dc._variants(ctx)[0])
    assert failure is None
    origins, poses = dict(placed.origins), dict(placed.poses)
    ports = dc._reserve_open_ports(ctx, placed)
    assert not isinstance(ports, dc.GrammarFailure)
    monkeypatch.setattr(
        dc, "_joint_route_group",
        lambda *args, **kwargs: dc._joint_refusal(
            "$.serviceGroups", "forced routing refusal", "keep the input"),
    )
    refusal = dc._joint_seat_group(
        ctx, placed, spec.service_groups[0], "U1", "pull", "right",
        "$.serviceGroups['config']", ports=ports,
    )
    assert isinstance(refusal, dc.GrammarFailure)
    assert "forced routing refusal" in refusal.detail
    assert placed.origins == origins
    assert placed.poses == poses
