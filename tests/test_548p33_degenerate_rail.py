"""548P33: joint rail records may be points; serialized wires may not."""

from __future__ import annotations

import copy

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.layoutplan import LayoutPlan
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawcompiler as dc, readability
from test_548n_group_seat import _prepared
from test_548p14_rail_entry import _assert_canonical_connectivity
from test_548p16_native_service import _fixture as native_fixture
from test_548p18_final_rail import _seated


def _built_case(*, native=True, single=True):
    circuit, spec, book, _ctx = native_fixture(native=native)
    if single:
        payload = circuit.to_jsonable()
        payload["parts"] = [part for part in payload["parts"] if part["id"] != "R2"]
        payload["nets"] = [net for net in payload["nets"] if net["id"] != "CFG_B"]
        for net in payload["nets"]:
            net["members"] = [member for member in net["members"] if not member.startswith("R2.")]
        circuit = CircuitSpec.from_dict(payload)
        host = book["HOST4"].to_jsonable()
        host["pins"] = [pin for pin in host["pins"] if pin["name"] != "CFG_B"]
        for pin in host["pins"]:
            if pin["name"] == "CFG_A":
                pin.update(tip=[-50.0, 20.0], direction="left")
        book["HOST4"] = SymbolProfile.from_dict(host)
        document = spec.to_jsonable()
        document["modules"][0]["parts"].remove("R2")
        document["serviceGroups"][0]["branches"] = [
            branch for branch in document["serviceGroups"][0]["branches"]
            if branch["part"] == "R1"]
        spec = PresentationSpec.from_dict(document)
    ctx = _prepared(circuit, spec, book)
    variant = dc._variants(ctx)[0]
    placed, failure = dc._place(ctx, variant)
    assert placed is not None, failure
    records = copy.deepcopy(placed.service_group_plans)
    built, failure, violations = dc._build_one_variant(
        ctx, variant, [], placement_override=placed)
    assert built is not None, (failure, violations)
    assert not built.checked.hard_violations
    return circuit, spec, book, built.plan, records, placed.service_group_plans


@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("single", [True, False])
def test_complete_joint_build_round_trips_and_every_pin_stays_connected(tmp_path, native, single):
    circuit, _spec, book, plan, before, after = _built_case(native=native, single=single)
    # This is the original production parser, not a cleaned or reconstructed plan.
    restored = LayoutPlan.from_dict(plan.to_jsonable())
    target = tmp_path / "joint-rail.json"
    plan.dump(target)
    loaded = LayoutPlan.load(target)
    assert restored.to_jsonable() == loaded.to_jsonable() == plan.to_jsonable()
    _assert_canonical_connectivity(circuit, book, loaded)
    derived = readability.derive_netlist(loaded, book)
    assert len(derived.pin_points) == len(derived.wired_pins) == (7 if single else 10)
    assert [(rail.runs[0], rail.anchor, rail.rotation, rail.lead)
            for record in after for rail in record.rails] == [
        (rail.runs[0], rail.anchor, rail.rotation, rail.lead)
        for record in before for rail in record.rails]
    trunk = after[0].rails[0].runs[0]
    assert (trunk[0] == trunk[-1]) is single
    true_runs = [(rail.net, run) for record in after for rail in record.rails
                 for run in rail.runs if len(dc._compress(run)) > 1]
    if not single:
        assert any(len(run) == 2 for _net, run in true_runs), "nonzero two-branch trunk control"
    for net, run in true_runs:
        assert any(segment.net == net and tuple(segment.points) == run
                   for segment in loaded.segments), "keep each nonzero run's original vertices"


def test_removing_the_single_branch_flag_lead_breaks_the_production_net_partition():
    circuit, _spec, book, plan, _before, records = _built_case()
    _assert_canonical_connectivity(circuit, book, plan)
    rail = records[0].rails[0]
    assert rail.lead[0] != rail.lead[-1]
    assert rail.runs[0][0] == rail.runs[0][-1]
    broken = copy.deepcopy(plan)
    removed = [segment for segment in broken.segments
               if segment.net == rail.net and tuple(segment.points) == rail.lead]
    assert len(removed) == 1
    broken.segments.remove(removed[0])
    # A broken real wire is still valid JSON geometry; electrical closure must fail.
    parsed = LayoutPlan.from_dict(broken.to_jsonable())
    derived = readability.derive_netlist(parsed, book)
    assert "R1.2" not in derived.wired_pins
    assert set(derived.group_of("R1.2")) != {"R1.2", "U1.1"}
    with pytest.raises(AssertionError):
        _assert_canonical_connectivity(circuit, book, parsed)


def test_real_two_point_decoupling_lead_is_preserved_and_its_removal_disconnects_ground():
    circuit, _spec, book, ctx, variant, placed = _seated()
    built, failure, violations = dc._build_one_variant(
        ctx, variant, [], placement_override=placed)
    assert built is not None, (failure, violations)
    plan = LayoutPlan.from_dict(built.plan.to_jsonable())
    _assert_canonical_connectivity(circuit, book, plan)
    rail = next(rail for record in placed.service_group_plans if record.group_id == "decouple"
                for rail in record.rails if rail.net == "GND")
    assert len(rail.lead) == 2 and rail.lead[0] != rail.lead[-1]
    matches = [segment for segment in plan.segments
               if segment.net == rail.net and tuple(segment.points) == rail.lead]
    assert len(matches) == 1, "a genuine two-point flag lead is still emitted unchanged"
    plan.segments.remove(matches[0])
    broken = LayoutPlan.from_dict(plan.to_jsonable())
    derived = readability.derive_netlist(broken, book)
    assert set(derived.group_of("C1.2")) != {"C1.2", "C2.2", "U1.5"}
    with pytest.raises(AssertionError):
        _assert_canonical_connectivity(circuit, book, broken)
