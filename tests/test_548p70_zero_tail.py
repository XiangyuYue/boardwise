"""The flag ladder's zero fallback follows every nonzero shape round."""

import pytest

from boardwise.engines import drawcompiler as dc


def _router():
    return dc.lattice_router(
        grid=5.0, residue=(0.0, 0.0), boxes=(),
        bounds=(-500.0, -500.0, 500.0, 500.0),
    )


def _flat_room(origin):
    """The production containment ruler, with room only in this pad's row."""
    corridor = (-500.0, origin[1], 500.0, origin[1])
    return lambda anchor, _hang: dc._inside((*anchor, *anchor), corridor)


@pytest.mark.parametrize("point,direction", [
    ((0.0, 0.0), (1.0, 0.0)),
    ((75.0, -40.0), (-1.0, 0.0)),
])
def test_flat_round_is_reached_after_every_bent_shape_is_refused(point, direction):
    anchor, lead, hang = dc._flag_anchor(
        _router(), point, direction, set(), fits=_flat_room(point),
    )
    expected = (point[0] + direction[0] * dc.FLAG_LEAD, point[1])
    assert lead == (point, expected)
    assert anchor == expected
    assert hang == 1.0


def test_all_crowded_shapes_keep_the_original_first_fallback():
    point = (0.0, 0.0)
    original = dc._flag_anchor(_router(), point, (1.0, 0.0), set())
    crowded = dc._flag_anchor(
        _router(), point, (1.0, 0.0), set(), near=lambda _lead: "crowded",
    )
    assert crowded == original
    assert crowded[1] == (point, (30.0, 0.0), (30.0, 25.0))


def test_a_roomier_flat_shape_precedes_the_crowded_bent_fallback():
    point = (0.0, 0.0)
    anchor, lead, _hang = dc._flag_anchor(
        _router(), point, (1.0, 0.0), set(),
        near=lambda lead: "crowded bend" if len(lead) == 3 else None,
    )
    assert anchor == (30.0, 0.0)
    assert lead == (point, anchor)


def test_no_shape_with_room_still_returns_no_lead():
    router = _router()
    room = dc._flag_room(router, [(-500.0, -500.0, 500.0, 500.0)], None, set())
    anchor, lead, hang = dc._flag_anchor(
        router, (0.0, 0.0), (1.0, 0.0), set(),
        fits=lambda anchor, _hang: room(
            (anchor[0] - 1.0, anchor[1] - 1.0, anchor[0] + 1.0, anchor[1] + 1.0),
            (anchor[0] - 1.0, anchor[1] - 1.0, anchor[0] + 1.0, anchor[1] + 1.0),
        ),
    )
    assert (anchor, lead, hang) == ((0.0, 0.0), None, 1.0)


def test_available_bent_shape_remains_the_first_choice():
    point = (0.0, 0.0)
    anchor, lead, hang = dc._flag_anchor(_router(), point, (1.0, 0.0), set())
    assert anchor == (30.0, 25.0)
    assert lead == (point, (30.0, 0.0), anchor)
    assert hang == 1.0


def test_flat_round_cannot_cross_a_foreign_wire():
    router = _router()
    router.edges = [((15.0, -5.0), (15.0, 5.0))]
    router.edge_nets = ["FOREIGN"]
    crossings = []
    anchor, lead, _hang = dc._flag_anchor(
        router, (0.0, 0.0), (1.0, 0.0), set(),
        only_length=30.0, fits=_flat_room((0.0, 0.0)), crossings=crossings,
    )
    assert anchor == (0.0, 0.0)
    assert lead is None
    assert crossings and all("FOREIGN" in item for item in crossings)


@pytest.mark.parametrize("blocked", [{(15.0, 0.0)}, {(30.0, 0.0)}])
def test_flat_round_cannot_pass_a_blocked_tip(blocked):
    anchor, lead, _hang = dc._flag_anchor(
        _router(), (0.0, 0.0), (1.0, 0.0), blocked,
        only_length=30.0, fits=_flat_room((0.0, 0.0)),
    )
    assert anchor == (0.0, 0.0)
    assert lead is None


@pytest.mark.parametrize("direction", [(1.0, 0.0), (0.0, -1.0)])
def test_explicit_zero_length_still_terminates_without_a_lead(direction):
    assert dc._flag_anchor(
        _router(), (0.0, 0.0), direction, set(), only_length=0.0,
    ) == ((0.0, 0.0), None, 1.0)


def test_vertical_shape_keeps_its_original_first_rung():
    assert dc._flag_anchor(_router(), (0.0, 0.0), (0.0, -1.0), set()) == (
        (0.0, -30.0), ((0.0, 0.0), (0.0, -30.0)), -1.0,
    )
