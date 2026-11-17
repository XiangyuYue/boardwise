"""A single shunt return may join its nearest host ground pin."""

from types import SimpleNamespace

from boardwise.core.presentationspec import PresentationSpec
from boardwise.engines import drawcompiler as dc
from test_548p64_pre_group_lanes import _lcd_case


def test_single_shunt_return_shares_nearest_host_pin_only():
    context, _host, ground, _signals = _lcd_case()
    document = context.presentation.to_jsonable()
    document["flagShareGroups"] = [{
        "net": ground,
        "groups": [["C4.2", "J1.2"], ["J1.7"]],
    }]
    context.presentation = PresentationSpec.from_dict(document)
    points = (
        ("C4.2", (0.0, 0.0)),
        ("J1.2", (60.0, 0.0)),
        ("J1.7", (35.0, 140.0)),
    )
    expression = SimpleNamespace(net=ground, points=points)

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
