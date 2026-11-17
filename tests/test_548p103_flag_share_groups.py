"""548P103: explicit flag-sharing intent uses the existing draw consumers."""

from dataclasses import replace

import pytest

from boardwise.core.presentationspec import PresentationSpec, PresentationSpecError
from boardwise.engines import drawcompiler as dc
from test_548p64_pre_group_lanes import _lcd_case


def _declared_spec(context, groups):
    document = context.presentation.to_jsonable()
    document["flagShareGroups"] = groups
    return PresentationSpec.from_dict(document)


def _lcd_ground_groups():
    return [{
        "net": "GND",
        "groups": [["C4.2", "J1.2"], ["J1.7"]],
    }]


def test_empty_flag_share_groups_keep_legacy_canonical_spec():
    context, _host, _ground, _signals = _lcd_case()
    original = context.presentation.to_jsonable()

    absent = PresentationSpec.from_dict(original)
    empty_document = {**original, "flagShareGroups": []}
    empty = PresentationSpec.from_dict(empty_document)

    assert absent.to_jsonable() == original
    assert empty.to_jsonable() == original
    assert empty.sha256() == absent.sha256()


def test_flag_share_groups_round_trip_and_reject_unknown_keys():
    context, _host, _ground, _signals = _lcd_case()
    declared = _declared_spec(context, _lcd_ground_groups())

    assert declared.to_jsonable()["flagShareGroups"] == _lcd_ground_groups()
    assert PresentationSpec.from_dict(declared.to_jsonable()).sha256() == declared.sha256()

    with pytest.raises(PresentationSpecError, match="unknown key"):
        _declared_spec(context, [{
            **_lcd_ground_groups()[0],
            "unexpected": True,
        }])


@pytest.mark.parametrize("value", [
    ["GND"],
    [{"net": "GND", "groups": []}],
    [{"net": "GND", "groups": [[]]}],
    [{"net": "GND", "groups": [["C4.2"], ["C4.2"]]}],
    [{"net": "GND", "groups": [["C4.2"], ["J1.2"]]},
     {"net": "GND", "groups": [["J1.7"]]}],
])
def test_flag_share_groups_reject_malformed_or_duplicate_members(value):
    context, _host, _ground, _signals = _lcd_case()
    document = context.presentation.to_jsonable()
    document["flagShareGroups"] = value

    with pytest.raises(PresentationSpecError):
        PresentationSpec.from_dict(document)


def test_explicit_lcd_ground_partition_is_consumed_by_existing_flag_grouping():
    context, _host, ground, _signals = _lcd_case()
    context.presentation = _declared_spec(context, _lcd_ground_groups())
    points = (
        ("C4.2", (0.0, 0.0)),
        ("J1.2", (60.0, 0.0)),
        ("J1.7", (35.0, 140.0)),
    )
    expression = dc._Expression(
        net=ground, style="wire", points=points, reason="flag-share test",
    )

    groups = dc._flag_groups(
        context,
        expression,
        "gnd",
        router=None,
        ruler=lambda start, end: (
            abs(end[0] - start[0]) + abs(end[1] - start[1])
        ),
    )

    partition = {
        frozenset(member for member, _point in group)
        for group in groups
    }
    assert partition == {
        frozenset({"C4.2", "J1.2"}),
        frozenset({"J1.7"}),
    }


def test_explicit_group_still_obeys_route_reach():
    context, _host, ground, _signals = _lcd_case()
    context.presentation = _declared_spec(context, _lcd_ground_groups())
    points = (
        ("C4.2", (0.0, 0.0)),
        ("J1.2", (60.0, 0.0)),
        ("J1.7", (35.0, 140.0)),
    )
    expression = dc._Expression(
        net=ground, style="wire", points=points, reason="flag-share test",
    )

    groups = dc._flag_groups(
        context,
        expression,
        "gnd",
        router=None,
        ruler=lambda _start, _end: 200.0,
    )

    partition = {
        frozenset(member for member, _point in group)
        for group in groups
    }
    assert partition == {
        frozenset({"C4.2"}),
        frozenset({"J1.2"}),
        frozenset({"J1.7"}),
    }
    failure = dc._flag_share_group_failure(context, ground, groups)

    assert failure is not None
    assert failure.category == dc.FAILURE_LAYOUT_UNSAT
    assert failure.subject == "$.flagShareGroups[GND]"
    assert "C4.2, J1.2" in failure.detail


@pytest.mark.parametrize("declared_groups,actual_groups,should_fail", [
    (
        [["C4.2", "J1.2", "J1.7"]],
        [["C4.2", "J1.2", "J1.7"]],
        False,
    ),
    (
        [["C4.2", "J1.2"], ["J1.7"]],
        [["C4.2", "J1.2", "J1.7"]],
        True,
    ),
])
def test_actual_flag_groups_preserve_the_declared_partition(
    declared_groups, actual_groups, should_fail,
):
    context, _host, ground, _signals = _lcd_case()
    context.presentation = _declared_spec(context, [{
        "net": ground,
        "groups": declared_groups,
    }])
    points = {
        "C4.2": (0.0, 0.0),
        "J1.2": (60.0, 0.0),
        "J1.7": (35.0, 140.0),
    }
    actual = tuple(
        tuple((member, points[member]) for member in group)
        for group in actual_groups
    )

    failure = dc._flag_share_group_failure(context, ground, actual)

    assert (failure is not None) is should_fail
    if should_fail:
        assert failure.category == dc.FAILURE_LAYOUT_UNSAT
        assert failure.subject == "$.flagShareGroups[GND]"


def test_full_builder_names_a_flag_group_beyond_route_reach(monkeypatch):
    context, _host, _ground, _signals = _lcd_case()
    context.presentation = _declared_spec(context, _lcd_ground_groups())
    monkeypatch.setattr(dc, "_flag_group_reach", lambda _context: 1.0)

    built, failure, _notes = dc._build_candidate(
        context, dc._variants(context)[0],
    )

    assert built is None
    assert failure is not None
    assert failure.category == dc.FAILURE_LAYOUT_UNSAT
    assert failure.subject == "$.flagShareGroups[GND]"
    assert "C4.2, J1.2" in failure.detail


def test_explicit_partition_blocks_service_channel_union(monkeypatch):
    context, _host, ground, _signals = _lcd_case()
    context.presentation = _declared_spec(context, _lcd_ground_groups())
    points = (
        ("C4.2", (0.0, 0.0)),
        ("J1.2", (60.0, 0.0)),
        ("J1.7", (35.0, 140.0)),
    )
    monkeypatch.setattr(
        dc,
        "_seat_first_channel_pairs",
        lambda *_args, **_kwargs: (("C4.2", "J1.7"),),
    )

    groups = dc._seat_first_groups(context, ground, points, placed=object())

    partition = {
        frozenset(members)
        for _share, _group, members in groups
    }
    assert partition == {
        frozenset({"C4.2", "J1.2"}),
        frozenset({"J1.7"}),
    }


@pytest.mark.parametrize("groups", [
    [{"net": "LCD_SCK", "groups": [["C4.2", "J1.2"], ["J1.7"]]}],
    [{"net": "GND", "groups": [["C4.2", "J1.2"], ["J1.8"]]}],
    [{"net": "3V3", "groups": [["C4.2", "J1.2"], ["J1.7"]]}],
])
def test_draw_validator_rejects_wrong_net_class_or_pin(groups):
    context, _host, _ground, _signals = _lcd_case()
    presentation = _declared_spec(context, groups)

    failures = dc.validate_flag_share_groups(context.circuit, presentation)

    assert failures
    assert failures[0].subject.startswith("$.flagShareGroups")


def test_draw_validator_allows_unstated_pins_to_keep_legacy_grouping():
    context, _host, _ground, _signals = _lcd_case()
    presentation = _declared_spec(context, [{
        "net": "GND",
        "groups": [["C4.2", "J1.2"]],
    }])

    failures = dc.validate_flag_share_groups(context.circuit, presentation)

    assert failures == []
