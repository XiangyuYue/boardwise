"""548P117: a port-room seat must clear printed rows, not only part bodies."""

from __future__ import annotations

from dataclasses import replace

from boardwise.engines import drawcompiler as dc
from test_548n_group_seat import _book, _circuit, _prepared, _spec

# Measured on the original first rung of this synthetic fixture: R2's reference
# row. The R2 body ends at x269.5, so this wall touches text only, never the body.
TEXT_ONLY_WALL = (257.5, 647.5, 272.5, 656.5)


def test_port_room_rung_clears_branch_text_as_well_as_its_body():
    circuit, spec, book = _circuit(), _spec(), _book()
    ctx = _prepared(circuit, spec, book)
    placed, failure = dc._place(
        ctx, dc._variants(ctx)[0], seat_service_groups=False)
    assert placed is not None, failure
    ports = dc._reserve_open_ports(ctx, placed)
    assert not isinstance(ports, dc.GrammarFailure), ports
    port = ports[0]
    modified = (
        replace(port, label=replace(port.label, bbox=TEXT_ONLY_WALL)),
        *ports[1:],
    )
    record = dc._joint_seat_group(
        ctx, placed, spec.service_groups[0], "U1", "pull", "right",
        "$.serviceGroups['config']", ports=modified,
    )
    assert not isinstance(record, dc.GrammarFailure), record.detail

    for cell in record.cells:
        body = dc._part_box(ctx.profile(cell.part_id), cell.pose, cell.origin)
        assert not dc._overlaps(body, TEXT_ONLY_WALL), (cell.part_id, body)
        for kind, _text, box in cell.text_boxes:
            assert not dc._overlaps(box, TEXT_ONLY_WALL), (
                cell.part_id, kind, box, TEXT_ONLY_WALL)
