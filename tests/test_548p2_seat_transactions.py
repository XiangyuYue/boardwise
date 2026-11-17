"""548P2: only a complete joint seat may commit placement geometry."""

from __future__ import annotations

import copy

import pytest

from boardwise.engines import drawcompiler as dc
from test_548n_group_seat import _book, _circuit, _prepared, _spec


def _unseated_group():
    circuit, spec, book = _circuit(), _spec(), _book()
    ctx = _prepared(circuit, spec, book)
    placed, failure = dc._place_chain_and_shelf(ctx, dc._variants(ctx)[0])
    assert failure is None, failure
    ports = dc._reserve_open_ports(ctx, placed)
    assert not isinstance(ports, dc.GrammarFailure), ports
    return ctx, placed, spec.service_groups[0], ports


def _seat(ctx, placed, group, ports):
    return dc._joint_seat_group(
        ctx, placed, group, "U1", "pull", "right",
        "$.serviceGroups['config']", ports=ports)


@pytest.mark.parametrize("gate", ["_joint_collisions", "_joint_route_group"])
def test_refused_seat_preserves_the_entire_input_placement(monkeypatch, gate):
    ctx, placed, group, ports = _unseated_group()
    before = copy.deepcopy(placed)
    origins, poses = placed.origins, placed.poses
    tried_origins = []

    def refuse(*args, **kwargs):
        # Both production gates receive the actual page used by this seat.
        tried_origins.append(dict(args[6].origins))
        return dc._joint_refusal(
            "$.serviceGroups['config']", f"forced {gate} refusal", "keep the input")

    monkeypatch.setattr(dc, gate, refuse)
    result = _seat(ctx, placed, group, ports)

    assert isinstance(result, dc.GrammarFailure)
    assert f"forced {gate} refusal" in result.detail
    assert len(tried_origins) == 1
    assert tried_origins[0] != before.origins, "the gate must see a moved trial"
    assert placed == before
    assert placed.origins is origins
    assert placed.poses is poses


def test_a_successful_seat_commits_the_complete_record_to_the_input():
    ctx, placed, group, ports = _unseated_group()
    before = copy.deepcopy(placed)
    origins, poses = placed.origins, placed.poses

    record = _seat(ctx, placed, group, ports)

    assert not isinstance(record, dc.GrammarFailure), record
    assert record.host_paths and record.rails, "commit only after routing the full seat"
    assert placed.origins != before.origins, "the fixture must require a real move"
    assert placed.origins is origins
    assert placed.poses is poses
    for cell in record.cells:
        assert placed.origins[cell.part_id] == cell.origin
        assert placed.poses[cell.part_id] == cell.pose
    assert placed.origins[record.host_part] == before.origins[record.host_part]
    assert placed.poses[record.host_part] == before.poses[record.host_part]
    before.origins.update({cell.part_id: cell.origin for cell in record.cells})
    before.poses.update({cell.part_id: cell.pose for cell in record.cells})
    assert placed == before, "successful seating only commits branch origins and poses"
