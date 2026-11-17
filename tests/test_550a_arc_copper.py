"""Task 550A P1: PCB ``ARC`` records are kept verbatim and never interpreted.

The boards here are synthetic ``.epru`` text (``parse_epru_text``) plus one
read-only read of the real fixture that carries the only PCB ``ARC`` the
repository has (ROBOT ctrl FOC). Nothing in this file asserts a centre, radius,
length or intersection: ``angle``'s unit is unverified, so the data model must
carry the record and stop.
"""

from __future__ import annotations

import json

import pytest

from boardwise.core.geometry import (
    ArcGeometry,
    BoardGeometry,
    LayerInfo,
    PadGeometry,
    ParseStats,
    Point,
    TrackSegment,
    index_by_net,
)
from boardwise.core.measure import _net_shape_records, read_stackup
from boardwise.core.netpath import CONNECTED, INDETERMINATE, NOT_PROVEN, find_net_path
from boardwise.parsers.epru import parse_epru_text

ROBOT = "tests/fixtures/ProPrj_ROBOT ctrl FOC_2026-09-16.epro2"

TOP = LayerInfo(layer_id=1, name="Top Layer", layer_type="TOP")
BOTTOM = LayerInfo(layer_id=2, name="Bottom Layer", layer_type="BOTTOM")
SILK = LayerInfo(layer_id=3, name="Top Silkscreen", layer_type="TOP_SILK")


# ---------------------------------------------------------------------------
# a synthetic .epru PCB document
# ---------------------------------------------------------------------------


def _rec(type_: str, *, ticket: int | None = None, id: str | None = None,
         body: dict | None = None) -> str:
    envelope: dict = {"type": type_}
    if ticket is not None:
        envelope["ticket"] = ticket
    if id is not None:
        envelope["id"] = id
    text = json.dumps(envelope)
    return f"{text}|||" if body is None else f"{text}||{json.dumps(body)}|"


def _head(doc_type: str = "PCB", uuid: str = "pcb1") -> str:
    return _rec("DOCHEAD", ticket=0, body={"docType": doc_type, "uuid": uuid})


def _layer_rows(*infos: LayerInfo) -> list[str]:
    return [
        _rec("LAYER", ticket=1, id=str(info.layer_id), body={
            "layerId": info.layer_id, "layerName": info.name,
            "layerType": info.layer_type, "use": True,
        })
        for info in infos
    ]


def _arc(
    ident: str,
    *,
    net: str = "GND",
    layer: int = 1,
    start: tuple[float, float] = (-761.6057, 458.3943),
    end: tuple[float, float] = (-778.4474, 429.1448),
    angle: float = 2.1761,
    width: float = 10.0,
    arc_type: str = "DOT",
    locked: bool = False,
    z_index: int | None = -1,
    ticket: int = 7,
) -> str:
    return _rec("ARC", ticket=ticket, id=ident, body={
        "partitionId": "", "groupId": 0, "netName": net, "layerId": layer,
        "startX": start[0], "startY": start[1], "endX": end[0], "endY": end[1],
        "angle": angle, "width": width, "arcType": arc_type,
        "locked": locked, "zIndex": z_index,
    })


def _parse(*lines: str) -> BoardGeometry:
    return parse_epru_text("\n".join([_head(), *_layer_rows(TOP, BOTTOM), *lines]))


# ---------------------------------------------------------------------------
# the record model
# ---------------------------------------------------------------------------


def test_a_dot_arc_keeps_every_field_verbatim():
    board = _parse(_arc("fd47ea5580af8468"))

    assert len(board.arcs) == 1
    (arc,) = board.arcs
    assert (arc.id, arc.net, arc.layer_id) == ("fd47ea5580af8468", "GND", 1)
    assert (arc.start.x, arc.start.y) == (-761.6057, 458.3943)
    assert (arc.end.x, arc.end.y) == (-778.4474, 429.1448)
    assert (arc.angle, arc.width, arc.arc_type) == (2.1761, 10.0, "DOT")
    assert (arc.locked, arc.z_index) == (False, -1)
    # The census: it is consumed now, and it is still counted as a record.
    assert board.stats.records_by_type.get("ARC") == 1
    assert "ARC" not in board.stats.unconsumed_types


def test_a_cent_arc_is_stored_and_never_read():
    board = _parse(_arc("c1", arc_type="CENT"))

    (arc,) = board.arcs
    assert arc.arc_type == "CENT"
    # Nothing derived: no centre, no radius, no length on the model itself.
    for forbidden in ("center", "radius", "length", "sagitta", "intersection"):
        assert not hasattr(arc, forbidden), forbidden


@pytest.mark.parametrize("angle", [0.0, -2.1761, 360.0])
def test_an_awkward_angle_is_stored_without_arithmetic(angle: float):
    board = _parse(_arc("a1", angle=angle))

    (arc,) = board.arcs
    assert arc.angle == angle
    assert json.dumps(board.summary(), allow_nan=False)


def test_a_netless_arc_is_kept_but_not_grouped():
    board = _parse(_arc("a1", net=""))

    (arc,) = board.arcs
    assert arc.net is None
    assert all(not net.arcs for net in board.nets.values())


def test_arcs_are_grouped_by_net():
    board = _parse(_arc("a1", net="GND"), _arc("a2", net="N2", layer=2))

    assert len(board.arcs) == 2
    assert [arc.id for arc in board.net("GND").arcs] == ["a1"]
    assert [arc.id for arc in board.net("N2").arcs] == ["a2"]
    assert board.net("GND").arc_count == 1
    assert board.net("N2").arc_count == 1


# ---------------------------------------------------------------------------
# old aggregate readings are untouched
# ---------------------------------------------------------------------------


def _board_with(arcs=(), tracks=()) -> BoardGeometry:
    return BoardGeometry(
        source="synthetic",
        name="SYN",
        layers={1: TOP, 2: BOTTOM},
        pads=[
            PadGeometry(id="p1", component="R1", component_id="R1", pin_number="1",
                        net="N1", footprint_layer_id=1, effective_layer_ids=[1],
                        x=0.0, y=0.0, width=10.0, height=10.0, shape="RECT"),
            PadGeometry(id="p2", component="R2", component_id="R2", pin_number="1",
                        net="N1", footprint_layer_id=1, effective_layer_ids=[1],
                        x=100.0, y=0.0, width=10.0, height=10.0, shape="RECT"),
        ],
        tracks=list(tracks),
        arcs=list(arcs),
    )


def _arc_obj(ident: str = "a1", net: str = "N1", layer: int = 1) -> ArcGeometry:
    return ArcGeometry(id=ident, net=net, layer_id=layer,
                       start=Point(0.0, 0.0), end=Point(100.0, 0.0),
                       angle=2.1761, width=10.0, arc_type="DOT")


def test_arcs_join_no_copper_aggregate_and_no_measurement():
    plain = _board_with()
    with_arc = _board_with(arcs=[_arc_obj()])

    net_plain, net_arc = plain.net("N1"), with_arc.net("N1")
    assert net_arc.element_count == net_plain.element_count
    assert net_arc.track_length == net_plain.track_length
    assert net_arc.bbox() == net_plain.bbox()
    assert with_arc.bbox() == plain.bbox()
    assert read_stackup(with_arc).used_copper_layer_ids == read_stackup(plain).used_copper_layer_ids
    # `measure` never sees an arc: the shape list is identical and carries no
    # element of kind "arc".
    assert len(_net_shape_records(with_arc, net_arc, with_area=False)) == len(
        _net_shape_records(plain, net_plain, with_area=False)
    )
    assert all(shape.kind != "arc" for _id, shape, _area in
               _net_shape_records(with_arc, net_arc, with_area=False))


def test_index_by_net_stays_backward_compatible():
    pad = _board_with().pads[0]

    without = index_by_net(pads=[pad])
    assert [p.id for p in without["N1"].pads] == ["p1"]
    assert without["N1"].arcs == []

    with_arcs = index_by_net(pads=[pad], arcs=[_arc_obj()])
    assert [a.id for a in with_arcs["N1"].arcs] == ["a1"]


def test_summary_gains_an_arcs_key_only_when_the_board_has_arcs():
    assert "arcs" not in _board_with().summary()
    assert _board_with(arcs=[_arc_obj()]).summary()["arcs"] == 1


# ---------------------------------------------------------------------------
# the one real sample, read only
# ---------------------------------------------------------------------------


def test_the_real_robot_arc_is_kept_verbatim_and_changes_no_aggregate():
    from boardwise.parsers.epru import build_board_geometry, load_epro2_source

    board = build_board_geometry(load_epro2_source(ROBOT))

    assert len(board.arcs) == 1
    (arc,) = board.arcs
    assert (arc.id, arc.net, arc.layer_id) == ("fd47ea5580af8468", "GND", 1)
    assert (arc.start.x, arc.start.y) == (-761.6057, 458.3943)
    assert (arc.end.x, arc.end.y) == (-778.4474, 429.1448)
    assert (arc.angle, arc.width, arc.arc_type) == (2.1761, 10.0, "DOT")
    assert "ARC" not in board.stats.unconsumed_types
    # The counts this fixture is known by are unmoved: arcs are not tracks.
    assert (len(board.pads), len(board.tracks), len(board.vias)) == (221, 356, 196)
    gnd = board.net("GND")
    assert gnd.arc_count == 1
    assert gnd.element_count == len(gnd.pads) + len(gnd.tracks) + len(gnd.vias) + len(gnd.pours)
    assert board.summary()["arcs"] == 1


# ---------------------------------------------------------------------------
# net-path: same-net ARC escalates, any other net's ARC does not
# ---------------------------------------------------------------------------


def _netpath_board(*, arcs=(), layers=None, stats_arc: int = 0,
                   tracks=()) -> BoardGeometry:
    stats = ParseStats(source="synthetic")
    if stats_arc:
        stats.unconsumed_types["ARC"] = stats_arc
    return BoardGeometry(
        source="synthetic", name="SYN",
        layers={1: TOP, 2: BOTTOM} if layers is None else layers,
        pads=[
            PadGeometry(id="p1", component="R1", component_id="R1", pin_number="1",
                        net="N1", footprint_layer_id=1, effective_layer_ids=[1],
                        x=0.0, y=0.0, width=10.0, height=10.0, shape="RECT"),
            PadGeometry(id="p2", component="R2", component_id="R2", pin_number="1",
                        net="N1", footprint_layer_id=1, effective_layer_ids=[1],
                        x=100.0, y=0.0, width=10.0, height=10.0, shape="RECT"),
        ],
        tracks=list(tracks), arcs=list(arcs), stats=stats,
    )


def test_a_same_net_arc_escalates_a_negative():
    board = _netpath_board(arcs=[_arc_obj()])
    result = find_net_path(board, "R1.1", "R2.1")

    assert result.verdict == INDETERMINATE
    assert [row["code"] for row in result.unknown] == ["arc_geometry_unsupported"]
    assert result.unknown[0]["ids"] == ["a1"]
    assert result.path == []


def test_another_nets_arc_does_not_escalate():
    board = _netpath_board(arcs=[_arc_obj(ident="other", net="N2")])
    result = find_net_path(board, "R1.1", "R2.1")

    assert result.verdict == NOT_PROVEN
    assert result.unknown == []


def test_a_same_net_arc_on_a_silk_layer_is_ignored_not_unknown():
    board = _netpath_board(arcs=[_arc_obj(layer=3)], layers={1: TOP, 2: BOTTOM, 3: SILK})
    result = find_net_path(board, "R1.1", "R2.1")

    assert result.verdict == NOT_PROVEN
    assert result.unknown == []
    assert [row["code"] for row in result.ignored] == ["arc_on_non_copper_layer"]


def test_an_arc_on_a_layer_the_board_never_names_is_an_evidence_gap():
    # 「not in the copper set」 is not the same fact as 「not copper」: layer 99
    # is defined by nobody, so its copper cannot be placed and the negative
    # verdict may not be final. (Before this, the arc was dismissed as
    # non-copper and the run claimed NOT_PROVEN.)
    board = _netpath_board(arcs=[_arc_obj(layer=99)], layers={1: TOP, 2: BOTTOM, 3: SILK})
    result = find_net_path(board, "R1.1", "R2.1")

    assert result.verdict == INDETERMINATE
    assert [row["code"] for row in result.unknown] == ["arc_layer_unclassified"]
    assert result.unknown[0]["ids"] == ["a1"]
    assert result.unknown[0]["layers"] == [99]
    assert result.unknown[0]["count"] == 1
    assert [row["code"] for row in result.ignored] == []
    assert result.path == []


def test_the_two_arc_buckets_are_kept_apart_in_one_answer():
    # Same net, two arcs: layer 3 (the board says silkscreen) is a certain
    # absence, layer 99 is an unknown. Both rows must appear, each with its own
    # id, and only the unknown escalates.
    board = _netpath_board(
        arcs=[_arc_obj(ident="silk", layer=3), _arc_obj(ident="gap", layer=99)],
        layers={1: TOP, 2: BOTTOM, 3: SILK},
    )
    result = find_net_path(board, "R1.1", "R2.1")

    assert result.verdict == INDETERMINATE
    assert [row["code"] for row in result.unknown] == ["arc_layer_unclassified"]
    assert result.unknown[0]["ids"] == ["gap"]
    assert [row["code"] for row in result.ignored] == ["arc_on_non_copper_layer"]
    assert result.ignored[0]["ids"] == ["silk"]


def test_a_walked_path_is_not_overturned_by_a_same_net_arc():
    track = TrackSegment(id="t1", net="N1", layer_id=1,
                         start=Point(0.0, 0.0), end=Point(100.0, 0.0), width=10.0)
    board = _netpath_board(arcs=[_arc_obj()], tracks=[track])
    result = find_net_path(board, "R1.1", "R2.1")

    assert result.verdict == CONNECTED
    assert [row["code"] for row in result.unknown] == ["arc_geometry_unsupported"]
    assert [row["id"] for row in result.path] == ["R1.1", "t1", "R2.1"]


def test_the_legacy_unconsumed_stats_still_escalate():
    board = _netpath_board(stats_arc=1)
    result = find_net_path(board, "R1.1", "R2.1")

    assert result.verdict == INDETERMINATE
    assert [row["code"] for row in result.unknown] == ["arc_copper_unparsed"]
    assert result.coverage["board"]["arcs"] == 0
    assert result.coverage["board"]["arcRecordsUnconsumed"] == 1


def test_coverage_reports_the_modelled_and_the_unparsed_counts_apart():
    board = _netpath_board(arcs=[_arc_obj()])
    result = find_net_path(board, "R1.1", "R2.1")

    assert result.coverage["board"]["arcs"] == 1
    assert result.coverage["board"]["arcRecordsUnconsumed"] == 0
