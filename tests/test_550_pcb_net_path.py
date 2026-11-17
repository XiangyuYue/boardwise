"""Task 550 core: offline copper-path evidence, synthetic boards only.

Every board here is hand-built so the geometry is readable in the test and no
fixture is edited or depended on. The task book's negative controls are the
test names: ``n1`` … ``n12``.

What these tests are *not*: a parser test (the ARC record these boards
simulate is measured on a real fixture in
``.tmp_review_attribution/local-net-path.md``) and not a CLI test (container
and board selection are the next batch's).
"""

from __future__ import annotations

import json

import pytest

from boardwise.core.geometry import (
    BoardGeometry,
    LayerInfo,
    PadGeometry,
    ParseStats,
    Point,
    PourShape,
    TrackSegment,
    ViaGeometry,
)
from boardwise.core.netpath import (
    CONNECTED,
    INDETERMINATE,
    NOT_PROVEN,
    SCHEMA,
    find_net_path,
)

TOP = LayerInfo(layer_id=1, name="Top Layer", layer_type="TOP")
BOTTOM = LayerInfo(layer_id=2, name="Bottom Layer", layer_type="BOTTOM")
PLANE = LayerInfo(layer_id=15, name="Inner1", layer_type="PLANE")


def _layers(*infos: LayerInfo) -> dict[int, LayerInfo]:
    return {info.layer_id: info for info in infos}


def _pad(
    ref: str,
    pin: str,
    net: str | None,
    x: float,
    y: float,
    *,
    shape: str = "RECT",
    width: float = 10.0,
    height: float = 10.0,
    angle: float = 0.0,
    layers: tuple[int, ...] | None = (1,),
    plated: bool | None = None,
) -> PadGeometry:
    return PadGeometry(
        id=f"{ref}-{pin}",
        component=ref,
        component_id=ref,
        pin_number=pin,
        net=net,
        footprint_layer_id=1,
        effective_layer_ids=None if layers is None else list(layers),
        x=x,
        y=y,
        width=width,
        height=height,
        shape=shape,
        angle=angle,
        plated=plated,
    )


def _track(
    ident: str,
    net: str | None,
    layer_id: int | None,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    width: float = 10.0,
) -> TrackSegment:
    return TrackSegment(
        id=ident,
        net=net,
        layer_id=layer_id,
        start=Point(*start),
        end=Point(*end),
        width=width,
    )


def _via(
    ident: str,
    net: str | None,
    x: float,
    y: float,
    *,
    via_diameter: float = 12.0,
    hole_diameter: float = 6.0,
    unused_inner_layers: tuple[int, ...] = (),
) -> ViaGeometry:
    return ViaGeometry(
        id=ident,
        net=net,
        x=x,
        y=y,
        hole_diameter=hole_diameter,
        via_diameter=via_diameter,
        via_type="THROUGH",
        unused_inner_layers=list(unused_inner_layers),
    )


def _pour(
    ident: str,
    net: str | None,
    layer_id: int | None,
    corners: list[tuple[float, float]],
    *,
    kind: str = "fill",
) -> PourShape:
    return PourShape(
        id=ident,
        net=net,
        layer_id=layer_id,
        kind=kind,
        points=[Point(*corner) for corner in corners],
    )


def _board(
    *,
    pads: tuple[PadGeometry, ...] = (),
    tracks: tuple[TrackSegment, ...] = (),
    vias: tuple[ViaGeometry, ...] = (),
    pours: tuple[PourShape, ...] = (),
    layers: dict[int, LayerInfo] | None = None,
    arc_records: int = 0,
) -> BoardGeometry:
    stats = ParseStats(source="synthetic")
    if arc_records:
        stats.unconsumed_types["ARC"] = arc_records
    return BoardGeometry(
        source="synthetic",
        name="SYN",
        layers=_layers(TOP, BOTTOM) if layers is None else layers,
        pads=list(pads),
        tracks=list(tracks),
        vias=list(vias),
        pours=list(pours),
        stats=stats,
    )


def _codes(rows: list[dict]) -> list[str]:
    return [row["code"] for row in rows]


# ---------------------------------------------------------------------------
# N1 — same net, no copper between the pads: NOT_PROVEN and nothing unknown
# ---------------------------------------------------------------------------


def test_n1_same_net_with_no_copper_is_not_proven_and_nothing_is_unknown():
    board = _board(
        pads=(_pad("R1", "1", "N1", 0, 0), _pad("R2", "1", "N1", 100, 0)),
    )
    result = find_net_path(board, "R1.1", "R2.1")

    assert result.verdict == NOT_PROVEN
    assert result.path == []
    assert result.via_count == 0
    assert result.hop_count == 0
    assert result.unknown == [], "a clean negative may not carry an unknown"
    assert result.ignored == []
    assert result.errors == []
    assert result.coverage["net"] == "N1"
    assert result.coverage["graph"] == {"vertices": 2, "edges": 0, "excluded": 0}


# ---------------------------------------------------------------------------
# N2 — two different nets: refused, never a path
# ---------------------------------------------------------------------------


def test_n2_different_nets_are_refused():
    board = _board(
        pads=(_pad("R1", "1", "N1", 0, 0), _pad("R2", "1", "N2", 10, 0)),
        tracks=(_track("t1", "N1", 1, (0, 0), (10, 0)),),
    )
    result = find_net_path(board, "R1.1", "R2.1")

    assert result.verdict == INDETERMINATE
    assert _codes(result.errors) == ["net_mismatch"]
    assert result.path == []


# ---------------------------------------------------------------------------
# N3 — only a pour could connect them: excluded, never CONNECTED
# ---------------------------------------------------------------------------


def test_n3_a_pour_between_the_pads_is_excluded_not_connected():
    board = _board(
        pads=(_pad("R1", "1", "N1", 0, 0), _pad("R2", "1", "N1", 100, 0)),
        pours=(
            _pour("p1", "N1", 1, [(-20, -20), (120, -20), (120, 20), (-20, 20)]),
        ),
    )
    result = find_net_path(board, "R1.1", "R2.1")

    assert result.verdict == NOT_PROVEN
    assert result.path == []
    assert _codes(result.ignored) == ["pour_excluded"]
    assert result.unknown == [], "pour is excluded by contract, never an unknown"


def test_n3_a_plane_layer_is_excluded_by_name():
    board = _board(
        pads=(_pad("R1", "1", "N1", 0, 0), _pad("R2", "1", "N1", 100, 0)),
        layers=_layers(TOP, BOTTOM, PLANE),
    )
    result = find_net_path(board, "R1.1", "R2.1")

    assert result.verdict == NOT_PROVEN
    assert "plane_excluded" in _codes(result.ignored)
    assert result.coverage["copperLayers"] == [1, 2, 15]


# ---------------------------------------------------------------------------
# N6 — unparsed ARC copper escalates a negative, and never overturns positive
# ---------------------------------------------------------------------------


def test_n6_arc_records_escalate_a_negative():
    board = _board(
        pads=(_pad("R1", "1", "N1", 0, 0), _pad("R2", "1", "N1", 100, 0)),
        arc_records=1,
    )
    result = find_net_path(board, "R1.1", "R2.1")

    assert result.verdict == INDETERMINATE
    assert _codes(result.unknown) == ["arc_copper_unparsed"]
    assert result.unknown[0]["count"] == 1
    # 550A split the coverage row: "arcs" is the modelled ARC count (0 here —
    # this board only hand-writes the legacy stats), "arcRecordsUnconsumed"
    # is the old board-level statement. The verdict and the code above are
    # unchanged by that rename.
    assert result.coverage["board"]["arcs"] == 0
    assert result.coverage["board"]["arcRecordsUnconsumed"] == 1


def test_n6_arc_records_do_not_overturn_a_walked_path():
    board = _board(
        pads=(_pad("R1", "1", "N1", 0, 0), _pad("R2", "1", "N1", 100, 0)),
        tracks=(_track("t1", "N1", 1, (0, 0), (100, 0)),),
        arc_records=2,
    )
    result = find_net_path(board, "R1.1", "R2.1")

    assert result.verdict == CONNECTED
    assert _codes(result.unknown) == ["arc_copper_unparsed"]
    assert [row["id"] for row in result.path] == ["R1.1", "t1", "R2.1"]


# ---------------------------------------------------------------------------
# N7 — unsupported shape / unread layer / unknown stackup
# ---------------------------------------------------------------------------


def test_n7_an_unsupported_endpoint_shape_is_an_input_error():
    board = _board(
        pads=(
            _pad("R1", "1", "N1", 0, 0, shape="POLYGON"),
            _pad("R2", "1", "N1", 100, 0),
        ),
        tracks=(_track("t1", "N1", 1, (0, 0), (100, 0)),),
    )
    result = find_net_path(board, "R1.1", "R2.1")

    assert result.verdict == INDETERMINATE
    assert "unsupported_pad_shape" in _codes(result.errors)
    assert result.path == []


@pytest.mark.parametrize(
    "shape,width,height",
    [("POLYGON", 20.0, 20.0), ("ELLIPSE", 60.0, 10.0), ("", 20.0, 20.0)],
)
def test_n7_an_approximated_pad_in_the_middle_cannot_manufacture_a_path(
    shape: str, width: float, height: float
):
    """The middle pad's copper is only a box / circumscribing 32-gon.

    Both tracks stop far enough inside that polygon's extent that an
    approximate model would join them; the exact-only rule must not.
    """
    board = _board(
        pads=(
            _pad("R1", "1", "N1", 0, 0),
            _pad("RM", "1", "N1", 50, 0, shape=shape, width=width, height=height),
            _pad("R2", "1", "N1", 100, 0),
        ),
        tracks=(
            _track("t1", "N1", 1, (0, 0), (41, 0)),
            _track("t2", "N1", 1, (59, 0), (100, 0)),
        ),
    )
    result = find_net_path(board, "R1.1", "R2.1")

    assert result.verdict == INDETERMINATE
    assert "unsupported_pad_shape" in _codes(result.unknown)
    assert result.path == []


def test_n7_an_unread_endpoint_layer_is_an_input_error():
    board = _board(
        pads=(
            _pad("R1", "1", "N1", 0, 0, layers=None),
            _pad("R2", "1", "N1", 100, 0),
        ),
        tracks=(_track("t1", "N1", 1, (0, 0), (100, 0)),),
    )
    result = find_net_path(board, "R1.1", "R2.1")

    assert result.verdict == INDETERMINATE
    assert "pad_layer_unread" in _codes(result.errors)


def test_n7_an_unread_layer_on_a_middle_pad_escalates_a_negative():
    board = _board(
        pads=(
            _pad("R1", "1", "N1", 0, 0),
            _pad("RM", "1", "N1", 50, 0, layers=None),
            _pad("R2", "1", "N1", 100, 0),
        ),
        tracks=(
            _track("t1", "N1", 1, (0, 0), (41, 0)),
            _track("t2", "N1", 1, (59, 0), (100, 0)),
        ),
    )
    result = find_net_path(board, "R1.1", "R2.1")

    assert result.verdict == INDETERMINATE
    assert _codes(result.unknown) == ["pad_layer_unread"]
    assert result.path == []


def test_n7_no_copper_layer_table_escalates_a_negative():
    board = _board(
        pads=(_pad("R1", "1", "N1", 0, 0), _pad("R2", "1", "N1", 100, 0)),
        layers={},
    )
    result = find_net_path(board, "R1.1", "R2.1")

    assert result.verdict == INDETERMINATE
    assert "copper_layers_unknown" in _codes(result.unknown)
    assert result.coverage["stackup"] == "empty"


# ---------------------------------------------------------------------------
# N9 — bad / missing / ambiguous references
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ref", ["R1", "", "R1.", ".1", "   "])
def test_n9_a_malformed_reference_is_refused_without_a_traceback(ref: str):
    board = _board(pads=(_pad("R1", "1", "N1", 0, 0),))
    result = find_net_path(board, ref, "R1.1")

    assert result.verdict == INDETERMINATE
    assert "bad_ref" in _codes(result.errors)


def test_n9_an_unknown_pad_is_refused():
    board = _board(pads=(_pad("R1", "1", "N1", 0, 0),))
    result = find_net_path(board, "R1.1", "R9.1")

    assert result.verdict == INDETERMINATE
    assert _codes(result.errors) == ["pad_not_found"]
    assert result.query["to"]["ref"] == "R9.1"


def test_n9_a_duplicated_ref_pad_is_ambiguous():
    board = _board(
        pads=(
            _pad("R1", "1", "N1", 0, 0),
            _pad("R1", "1", "N1", 20, 0),
            _pad("R2", "1", "N1", 100, 0),
        )
    )
    result = find_net_path(board, "R1.1", "R2.1")

    assert result.verdict == INDETERMINATE
    assert _codes(result.errors) == ["pad_ambiguous"]
    assert result.errors[0]["pads"] == ["R1.1", "R1.1"]


def test_n9_a_pad_without_a_net_is_refused():
    board = _board(pads=(_pad("R1", "1", None, 0, 0), _pad("R2", "1", "N1", 10, 0)))
    result = find_net_path(board, "R1.1", "R2.1")

    assert result.verdict == INDETERMINATE
    assert "pad_without_net" in _codes(result.errors)


# ---------------------------------------------------------------------------
# N10 — a pad touching a via directly is disclosed, never an edge
# ---------------------------------------------------------------------------


def test_n10_direct_pad_via_contact_is_not_a_path():
    """Two pads on opposite faces, overlapping in plan, one via through both.

    Allowing pad<->via would answer CONNECTED here. The contract forbids it
    until the host's own semantics for via-in-pad are measured, so the answer
    is INDETERMINATE with the contact disclosed.
    """
    board = _board(
        pads=(
            _pad("R1", "1", "N1", 0, 0, layers=(1,)),
            _pad("R2", "1", "N1", 0, 0, layers=(2,)),
        ),
        vias=(_via("v1", "N1", 0, 0),),
    )
    result = find_net_path(board, "R1.1", "R2.1")

    assert result.verdict == INDETERMINATE
    assert result.path == []
    assert _codes(result.unknown) == ["pad_via_contact"] * 2
    assert result.coverage["graph"]["edges"] == 0


# ---------------------------------------------------------------------------
# N11 — blind / buried vias join by their effective layers only
# ---------------------------------------------------------------------------


def _two_layer_chain(*, unused: tuple[int, ...]) -> BoardGeometry:
    return _board(
        pads=(
            _pad("R1", "1", "N1", 0, 0, layers=(1,)),
            _pad("R2", "1", "N1", 100, 0, layers=(2,)),
        ),
        tracks=(
            _track("tTop", "N1", 1, (0, 0), (50, 0)),
            _track("tBottom", "N1", 2, (50, 0), (100, 0)),
        ),
        vias=(_via("v1", "N1", 50, 0, unused_inner_layers=unused),),
    )


def test_n11_a_via_spanning_both_layers_connects_the_chain():
    result = find_net_path(_two_layer_chain(unused=()), "R1.1", "R2.1")

    assert result.verdict == CONNECTED
    assert result.via_count == 1
    assert [row["kind"] for row in result.path] == ["pad", "track", "via", "track", "pad"]
    via_row = result.path[2]
    assert via_row["center"] == [50.0, 0.0]
    assert via_row["viaDiameter"] == 12.0
    assert via_row["holeDiameter"] == 6.0
    assert via_row["layers"] == [1, 2]


def test_n11_a_via_that_skips_the_bottom_layer_breaks_the_chain():
    result = find_net_path(_two_layer_chain(unused=(2,)), "R1.1", "R2.1")

    assert result.verdict == NOT_PROVEN
    assert result.path == []
    assert result.unknown == [], "a via's own layer span is a fact, not a gap"


# ---------------------------------------------------------------------------
# N12 — same input, byte-identical output
# ---------------------------------------------------------------------------


def test_n12_the_same_board_gives_byte_identical_json():
    def build() -> BoardGeometry:
        return _board(
            pads=(
                _pad("R1", "1", "N1", 0, 0),
                _pad("RM", "1", "N1", 40, 0),
                _pad("R2", "1", "N1", 100, 0),
            ),
            tracks=(
                _track("tLow", "N1", 1, (0, 0), (100, 0)),
                _track("tUp", "N1", 1, (0, 0), (40, 0)),
                _track("tAcross", "N1", 1, (40, 0), (100, 0)),
            ),
        )

    first = find_net_path(build(), "R1.1", "RM.1").to_json()
    second = find_net_path(build(), "R1.1", "RM.1").to_json()

    assert first == second
    assert first.encode("utf-8") == second.encode("utf-8")
    assert [row["id"] for row in json.loads(first)["path"]] == ["R1.1", "tLow", "RM.1"]


# ---------------------------------------------------------------------------
# conTRACT shape: always-present arrays, exact pad models, degenerate query
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "shape,width,height",
    [("RECT", 10.0, 10.0), ("OVAL", 20.0, 10.0), ("ELLIPSE", 10.0, 10.0)],
)
def test_the_three_exact_pad_models_all_connect(
    shape: str, width: float, height: float
):
    board = _board(
        pads=(
            _pad("R1", "1", "N1", 0, 0, shape=shape, width=width, height=height),
            _pad("R2", "1", "N1", 100, 0, shape=shape, width=width, height=height),
        ),
        tracks=(_track("t1", "N1", 1, (0, 0), (100, 0)),),
    )
    result = find_net_path(board, "R1.1", "R2.1")

    assert result.verdict == CONNECTED
    assert result.path[0]["shape"] == shape


def test_path_rows_carry_the_figures_the_contract_names():
    board = _board(
        pads=(
            _pad("R1", "1", "N1", 0, 0, angle=30.0),
            _pad("R2", "1", "N1", 100, 0),
        ),
        tracks=(_track("t1", "N1", 1, (0, 0), (100, 0), width=8.0),),
    )
    rows = find_net_path(board, "R1.1", "R2.1").path

    pad_row, track_row = rows[0], rows[1]
    assert pad_row["ref"] == "R1" and pad_row["pad"] == "1"
    assert pad_row["shape"] == "RECT" and pad_row["angle"] == 30.0
    assert pad_row["net"] == "N1" and pad_row["layers"] == [1]
    assert track_row["width"] == 8.0
    assert track_row["start"] == [0.0, 0.0] and track_row["end"] == [100.0, 0.0]


def test_the_json_contract_keeps_every_array_on_an_error_path():
    board = _board(pads=(_pad("R1", "1", "N1", 0, 0),))
    payload = find_net_path(board, "R1.1", "R9.9").as_dict()

    assert payload["schema"] == SCHEMA
    for key in ("unknown", "ignored", "path"):
        assert payload[key] == []
    assert _codes(payload["errors"]) == ["pad_not_found"]
    for key in ("source", "query", "coverage", "scope", "verdict"):
        assert key in payload
    assert payload["viaCount"] == 0
    assert payload["scope"]["excludes"]


def test_same_pad_is_refused_not_a_zero_hop_connection():
    """One terminal is not a path: a zero-hop CONNECTED would claim a search."""
    board = _board(
        pads=(_pad("R1", "1", "N1", 0, 0), _pad("R2", "1", "N1", 100, 0)),
        tracks=(_track("t1", "N1", 1, (0, 0), (100, 0)),),
    )
    result = find_net_path(board, "R1.1", "R1.1")

    assert result.verdict == INDETERMINATE
    assert _codes(result.errors) == ["same_pad"]
    assert result.path == []
    assert result.hop_count == 0


def test_a_netless_track_escalates_a_negative():
    board = _board(
        pads=(_pad("R1", "1", "N1", 0, 0), _pad("R2", "1", "N1", 100, 0)),
        tracks=(_track("stray", None, 1, (45, 0), (55, 0)),),
    )
    result = find_net_path(board, "R1.1", "R2.1")

    assert result.verdict == INDETERMINATE
    assert _codes(result.unknown) == ["netless_copper"]
    assert result.unknown[0]["tracks"] == 1


def test_a_zero_width_track_is_invalid_copper_not_an_edge():
    board = _board(
        pads=(_pad("R1", "1", "N1", 0, 0), _pad("R2", "1", "N1", 100, 0)),
        tracks=(_track("t0", "N1", 1, (0, 0), (100, 0), width=0.0),),
    )
    result = find_net_path(board, "R1.1", "R2.1")

    assert result.verdict == INDETERMINATE
    assert _codes(result.unknown) == ["invalid_track_geometry"]
    assert result.path == []


def test_a_pad_on_a_face_does_not_join_the_other_face():
    """The same plan-view point on two faces is two pieces of copper."""
    board = _board(
        pads=(
            _pad("R1", "1", "N1", 0, 0, layers=(1,)),
            _pad("R2", "1", "N1", 0, 0, layers=(2,)),
        )
    )
    result = find_net_path(board, "R1.1", "R2.1")

    assert result.verdict == NOT_PROVEN
    assert result.coverage["graph"]["edges"] == 0


# ---------------------------------------------------------------------------
# Host-review boundaries: same pad, impossible barrels, non-finite pads
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "hole,outer",
    [(-1.0, 12.0), (12.0, 12.0), (13.0, 12.0)],
    ids=["negative-hole", "hole-equals-pad", "hole-larger-than-pad"],
)
def test_a_physically_impossible_barrel_is_invalid_copper(hole: float, outer: float):
    """``0 <= hole < via_diameter`` is the only shape a barrel can have."""
    board = _board(
        pads=(
            _pad("R1", "1", "N1", 0, 0, layers=(1,)),
            _pad("R2", "1", "N1", 100, 0, layers=(2,)),
        ),
        tracks=(
            _track("tTop", "N1", 1, (0, 0), (50, 0)),
            _track("tBottom", "N1", 2, (50, 0), (100, 0)),
        ),
        vias=(_via("v1", "N1", 50, 0, via_diameter=outer, hole_diameter=hole),),
    )
    result = find_net_path(board, "R1.1", "R2.1")

    assert result.verdict == INDETERMINATE
    assert _codes(result.unknown) == ["invalid_via_geometry"]
    assert result.path == []


def test_a_non_finite_endpoint_pad_is_an_input_error_not_a_crash():
    board = _board(
        pads=(
            _pad("R1", "1", "N1", 0, 0, width=float("nan")),
            _pad("R2", "1", "N1", 100, 0),
        ),
        tracks=(_track("t1", "N1", 1, (0, 0), (100, 0)),),
    )
    result = find_net_path(board, "R1.1", "R2.1")

    assert result.verdict == INDETERMINATE
    assert _codes(result.errors) == ["invalid_pad_geometry"]
    assert result.path == []
    # The projection must not carry the NaN through: `to_json` refuses NaN.
    assert "nan" not in result.to_json().lower()


def test_a_non_finite_middle_pad_cannot_join_and_does_not_crash():
    """An infinite angle raises inside ``math.cos`` if measure ever sees it."""
    board = _board(
        pads=(
            _pad("R1", "1", "N1", 0, 0),
            _pad("RM", "1", "N1", 50, 0, angle=float("inf")),
            _pad("R2", "1", "N1", 100, 0),
        ),
        tracks=(
            _track("t1", "N1", 1, (0, 0), (41, 0)),
            _track("t2", "N1", 1, (59, 0), (100, 0)),
        ),
    )
    result = find_net_path(board, "R1.1", "R2.1")

    assert result.verdict == INDETERMINATE
    assert _codes(result.unknown) == ["invalid_pad_geometry"]
    assert result.path == []


def test_a_duplicated_pad_key_keeps_every_copy_out_of_the_graph():
    """Both pads sharing one REF.PAD are dropped, not just the second.

    Either copy on its own would bridge the two track halves, so a first-copy-
    wins graph would answer CONNECTED while the walked vertex id stayed
    ambiguous.
    """
    board = _board(
        pads=(
            _pad("R1", "1", "N1", 0, 0),
            _pad("RM", "1", "N1", 30, 0),
            _pad("RM", "1", "N1", 70, 0),
            _pad("R2", "1", "N1", 100, 0),
        ),
        tracks=(
            _track("t1", "N1", 1, (0, 0), (41, 0)),
            _track("t2", "N1", 1, (59, 0), (100, 0)),
        ),
    )
    result = find_net_path(board, "R1.1", "R2.1")

    assert result.verdict == INDETERMINATE
    assert _codes(result.unknown) == ["duplicate_pad_id"]
    assert result.unknown[0]["count"] == 2
    assert result.path == []
    assert result.coverage["graph"]["excluded"] == 2


def test_an_npth_land_no_larger_than_its_hole_is_ignored_not_unknown():
    """``effective_layer_ids == []`` is 「no copper」 — a fact, not a gap."""
    board = _board(
        pads=(
            _pad("R1", "1", "N1", 0, 0),
            _pad("MH", "1", "N1", 50, 0, layers=(), plated=False),
            _pad("R2", "1", "N1", 100, 0),
        ),
        tracks=(
            _track("t1", "N1", 1, (0, 0), (41, 0)),
            _track("t2", "N1", 1, (59, 0), (100, 0)),
        ),
    )
    result = find_net_path(board, "R1.1", "R2.1")

    assert result.verdict == NOT_PROVEN
    assert _codes(result.ignored) == ["pad_without_copper_layer"]
    assert result.unknown == [], "a certain absence of copper must not escalate"


def test_the_projection_refuses_nan_outright():
    from boardwise.core.netpath import NetPathResult

    with pytest.raises(ValueError):
        NetPathResult(verdict=CONNECTED, coverage={"x": float("nan")}).to_json()
