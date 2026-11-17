"""548P122: independent divider chains share columns, never coincident origins."""

from __future__ import annotations

from functools import partial
from pathlib import Path

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.engines import drawapply, drawcompiler as dc, pagecompiler as pc, readability

ROOT = Path(__file__).resolve().parents[1]
CIRCUIT = ROOT / "evidence/548P120/circuit.full.pinmap.json"
SPEC = ROOT / "evidence/548P122/full.presentation.led-direct.json"
LIBRARY = ROOT / "evidence/548P59/full.library.json"
INPUTS = (CIRCUIT, SPEC, LIBRARY)

_missing = [str(path.relative_to(ROOT)) for path in INPUTS if not path.exists()]
if _missing:
    pytest.skip(
        "requires local 548P122 evidence (gitignored, local-only); "
        f"missing: {_missing}",
        allow_module_level=True,
    )


def _context():
    circuit = CircuitSpec.load(CIRCUIT)
    spec = PresentationSpec.load(SPEC)
    book = drawapply.load_library(LIBRARY)
    module = next(item for item in spec.modules if item.id == "led")
    sub_circuit, sub_presentation = pc._module_view(circuit, spec, module)
    binding = dc.bind_grammar(sub_circuit, sub_presentation, book)
    binding = dc._with_series_arms(binding, sub_presentation)
    binding = dc._with_panel_groups(binding, sub_presentation, sub_circuit)
    binding = dc._with_service_groups(binding, sub_presentation, sub_circuit, book)
    prepared = dc._prepare(
        sub_circuit, sub_presentation, binding, book, dc.CompileBudget())
    assert prepared.context is not None
    return prepared.context


def test_independent_chains_align_columns_without_sharing_a_point():
    ctx = _context()
    built, failure, violations = dc._build_candidate(ctx, dc._variants(ctx)[0], [])
    assert built is not None, (failure, violations)
    plan = built.plan
    assert plan.part("R2").x == plan.part("R3").x
    assert plan.part("D1").x == plan.part("D2").x
    assert plan.part("R2").y != plan.part("R3").y
    assert plan.part("D1").y != plan.part("D2").y
    def box(part_id):
        part = plan.part(part_id)
        return dc._part_box(
            ctx.profile(part_id),
            dc.SymbolPose(int(part.rotation), part.mirror), (part.x, part.y))

    for left, right in (("R2", "R3"), ("D1", "D2")):
        left_box, right_box = box(left), box(right)
        assert not dc._overlaps(left_box, right_box), (left_box, right_box)

    checked = readability.check(
        plan, ctx.circuit, ctx.presentation, ctx.book,
        grammar_checker=partial(dc.check_grammar, budget=ctx.budget),
        page_box=ctx.budget.page_box, grid=ctx.budget.grid)
    assert checked.ok and not checked.grammar_findings
    derived = readability.derive_netlist(plan, ctx.book)
    assert len(derived.pin_points) == len(derived.wired_pins) == 8
    for net in ctx.circuit.nets:
        for member in net.members:
            assert set(derived.group_of(member)) == set(net.members)
