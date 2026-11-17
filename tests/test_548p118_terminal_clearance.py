"""548P118: joint host routes must not nearly touch a foreign terminal pin."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.engines import drawapply, drawcompiler as dc, placement

ROOT = Path(__file__).resolve().parents[1]
CIRCUIT = ROOT / "evidence/548P4/circuit.wifi.p44.json"
SPEC = ROOT / "evidence/548O/spec-3groups.json"
LIBRARY = ROOT / "evidence/548J/wifi-canvas/calibrated.library.json"
INPUTS = (CIRCUIT, SPEC, LIBRARY)

_missing = [str(path.relative_to(ROOT)) for path in INPUTS if not path.exists()]
if _missing:
    pytest.skip(
        "requires local 548P118 evidence (gitignored, local-only); "
        f"missing: {_missing}",
        allow_module_level=True,
    )


def _placed_wifi():
    circuit = CircuitSpec.load(CIRCUIT)
    spec = PresentationSpec.load(SPEC)
    book = drawapply.load_library(LIBRARY)
    binding = dc.bind_grammar(circuit, spec, book)
    binding = dc._with_panel_groups(binding, spec, circuit)
    binding = dc._with_service_groups(binding, spec, circuit, book)
    prepared = dc._prepare(
        circuit, spec, binding, book,
        dc.CompileBudget(page_box=(0.0, 0.0, 1170.0, 825.0)))
    assert prepared.context is not None
    placed, failure = dc._place(prepared.context, dc._variants(prepared.context)[0])
    assert placed is not None, failure
    return prepared.context, placed


def test_host_route_vertices_keep_the_existing_foreign_pin_clearance():
    ctx, placed = _placed_wifi()
    threshold = ctx.budget.grid * placement.PIN_CLEARANCE_GRID
    problems = []
    for record in placed.service_group_plans:
        for cell in record.cells:
            for path in cell.host_paths:
                for other in record.cells:
                    terminal_net = other.to_net
                    if terminal_net == cell.from_net:
                        continue
                    point = other.to_seat
                    for vertex in path:
                        distance = math.hypot(
                            vertex[0] - point[0], vertex[1] - point[1])
                        if distance < threshold:
                            problems.append((
                                cell.from_net, vertex, terminal_net, point,
                                distance, threshold))
    assert problems == [], problems
