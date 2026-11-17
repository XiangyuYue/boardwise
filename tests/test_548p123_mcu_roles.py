"""548P123: MCU port roles must agree with the measured pin directions."""

from __future__ import annotations

from pathlib import Path

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.engines import drawapply, drawcompiler as dc, pagecompiler as pc
from boardwise.engines.grammar import ic_periphery

ROOT = Path(__file__).resolve().parents[1]
CIRCUIT = ROOT / "evidence/548P120/circuit.full.pinmap.json"
SPEC = ROOT / "evidence/548P123/full.presentation.mcu-roles.json"
LIBRARY = ROOT / "evidence/548P59/full.library.json"
INPUTS = (CIRCUIT, SPEC, LIBRARY)

_missing = [str(path.relative_to(ROOT)) for path in INPUTS if not path.exists()]
if _missing:
    pytest.skip(
        "requires local 548P123 evidence (gitignored, local-only); "
        f"missing: {_missing}",
        allow_module_level=True,
    )


def _case():
    circuit = CircuitSpec.load(CIRCUIT)
    spec = PresentationSpec.load(SPEC)
    book = drawapply.load_library(LIBRARY)
    module = next(item for item in spec.modules if item.id == "mcu")
    return (*pc._module_view(circuit, spec, module), book)


def test_single_pin_port_roles_match_the_measured_pin_side():
    circuit, presentation, book = _case()
    profile = book["MCU-STM32G431RBT6"]
    for net in circuit.nets:
        if net.cls != "signal" or len(net.members) != 1:
            continue
        role = presentation.port_roles.get(net.id)
        if not role:
            continue
        _, _, token = net.members[0].partition(".")
        pin = profile.pin(token)
        assert pin is not None
        assert presentation.side_for(role) == pin.direction, (
            net.id, role, presentation.side_for(role), pin.direction)


def test_buzzer_and_boot0_binding_use_the_same_orientation():
    circuit, presentation, book = _case()
    binding = dc.bind_grammar(circuit, presentation, book)
    by_pair = {(item.subject, item.object): item.kind for item in binding.constraints}
    assert by_pair[("BZ1", "U1")] == "left-of"
    assert by_pair[("BOOT0", "U1")] == "right-of"
    core_nets = set().union(*(
        set(dc._part_nets(circuit, part).values())
        for part in ("U1", "C1", "C2", "C3", "R1", "BZ1")
    ))
    signals = ic_periphery._signals(circuit, "U1", core_nets, "3V3", "GND")
    orientation = ic_periphery._orientation_reading(
        book, circuit, "U1", presentation, signals)
    assert orientation.flip == 0, orientation.note
