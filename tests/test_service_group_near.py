"""Service joint seats replace the branch/host ``near`` whatever the host side.

548J's `_with_service_groups` docstring says the automatic near heuristic is
dropped for a declared joint seat because the seat record is the stronger
statement. The implementation only did so when `_service_group_side` could name
one side: an MCU whose ground feet sit on both sides of the same net leaves the
side unknown, and the old ``near`` survived to be judged by `NEAR_LIMIT`.

These tests build the circuit, the presentation and the binding directly (no
compile, no editor, no geometry) and pin the four cases the fix owes:

1. mixed-side host: the seated branch's ``near`` is removed, an unrelated
   part's ``near`` is kept;
2. side undetermined: the original lateral constraint is kept, unchanged;
3. one side determined: the lateral constraint is replaced as before, and the
   ``near`` is dropped (the existing behaviour stays);
4. no `serviceGroups`: the binding comes back identical (the same object).
"""

from __future__ import annotations

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawcompiler as dc
from boardwise.engines.grammar.base import (
    LEFT_OF,
    NEAR,
    RIGHT_OF,
    GrammarResult,
    RelativeConstraint,
)

PROV = "verified_recipe"
PARTS = ["U1", "C9", "C10"]


# --------------------------------------------------------------- synthetic facts


def _pin(number: str, tip, direction: str) -> dict:
    return {"number": number, "name": number, "tip": list(tip),
            "direction": direction, "length": 10.0, "pinType": "passive"}


def _symbol(ref: str, body, pins) -> dict:
    return {"kind": "boardwise-symbol-profile", "profileVersion": 1,
            "symbolRef": ref, "title": ref, "body": list(body), "pins": pins,
            "source": "test fixture (service-near)"}


def _book(mixed: bool) -> dict[str, SymbolProfile]:
    host_pins = [_pin("VDD", [60.0, 20.0], "right")]
    if mixed:
        # The same side net leaves the host on both sides: _service_group_side
        # has no single answer for the seat record.
        host_pins += [
            _pin("GND1", [-60.0, -20.0], "left"),
            _pin("GND2", [60.0, -20.0], "right"),
        ]
    else:
        host_pins += [_pin("GND", [-60.0, -20.0], "left")]
    return {
        "HOST": SymbolProfile.from_dict(copy_payload(_symbol(
            "HOST", [-50.0, -30.0, 50.0, 30.0], host_pins))),
        "C": SymbolProfile.from_dict(copy_payload(_symbol(
            "C", [-5.5, -8.5, 5.5, 8.5], [
                _pin("1", [0.0, 20.0], "up"),
                _pin("2", [0.0, -20.0], "down"),
            ]))),
    }


def copy_payload(payload: dict) -> dict:
    """A fresh profile payload per book so two fixtures never share a dict."""
    return {
        "kind": payload["kind"],
        "profileVersion": payload["profileVersion"],
        "symbolRef": payload["symbolRef"],
        "title": payload["title"],
        "body": list(payload["body"]),
        "pins": [dict(pin, tip=list(pin["tip"])) for pin in payload["pins"]],
        "source": payload["source"],
    }


def _part(part_id: str, symbol: str) -> dict:
    return {"id": part_id, "symbolRef": symbol, "value": symbol,
            "provenance": PROV}


def _net(net_id: str, cls: str, members) -> dict:
    return {"id": net_id, "class": cls, "members": list(members),
            "provenance": PROV}


def _circuit(mixed: bool) -> CircuitSpec:
    gnd = ["U1.GND1", "U1.GND2", "C9.2"] if mixed else ["U1.GND", "C9.2"]
    # C10 is a second two-foot part in the same module, but on PWR/CFG — it is
    # not a host candidate for the decoupling group, and it states no seat.
    return CircuitSpec.from_dict({
        "parts": [_part("U1", "HOST"), _part("C9", "C"), _part("C10", "C")],
        "nets": [
            _net("PWR", "power", ["U1.VDD", "C9.1", "C10.1"]),
            _net("GND", "gnd", gnd),
            _net("CFG", "signal", ["C10.2"]),
        ],
    })


def _spec(mixed: bool, *, groups: bool = True) -> PresentationSpec:
    payload = {
        "grammarRef": "mixed-island",
        "sidePreferences": {"input": "right", "output": "right",
                            "load": "right", "source": "left",
                            "power": "top", "gnd": "bottom"},
        "modules": [{
            "id": "m", "parts": list(PARTS), "role": "host island",
            "grammarRef": "mixed-island", "core": "U1",
        }],
        "labelPolicy": {"local": "wire", "crossModule": "label",
                        "highFanout": "label", "stubMin": 40.0},
    }
    if groups:
        payload["serviceGroups"] = [{
            "id": "decoupling",
            "branches": [{"part": "C9", "from": "PWR", "to": "GND"}],
        }]
    return PresentationSpec.from_dict(payload)


def _binding(*constraints: RelativeConstraint) -> GrammarResult:
    return GrammarResult(ok=True, constraints=tuple(constraints))


def _seated(mixed: bool, *constraints: RelativeConstraint):
    circuit = _circuit(mixed)
    spec = _spec(mixed)
    book = _book(mixed)
    return dc._with_service_groups(_binding(*constraints), spec, circuit, book)


def _kinds(result: GrammarResult) -> list[tuple[str, str, str]]:
    return [(item.kind, item.subject, item.object) for item in result.constraints]


# --------------------------------------------------------------------- the cases


def test_mixed_side_host_drops_the_seated_near_and_keeps_unrelated_near():
    c9_near = RelativeConstraint(
        NEAR, "C9", "U1",
        "ic-periphery: the decoupling pair sits near its host")
    c10_near = RelativeConstraint(
        NEAR, "C10", "U1",
        "ic-periphery: an unrelated part sits near the same host")

    out = _seated(True, c9_near, c10_near)

    assert (NEAR, "C9", "U1") not in _kinds(out), (
        "the joint seat record is stronger than the automatic near heuristic; "
        "it must replace it even when the host ground feet sit on both sides")
    assert (NEAR, "C10", "U1") in _kinds(out), (
        "a near constraint that belongs to no declared service branch must "
        "stay exactly as the grammar stated it")


def test_undetermined_side_keeps_the_original_lateral_constraint():
    left = RelativeConstraint(
        LEFT_OF, "C9", "U1",
        "ic-periphery: the branch is read left of its host")
    near = RelativeConstraint(
        NEAR, "C9", "U1", "ic-periphery: near its host")

    out = _seated(True, left, near)

    kept = [item for item in out.constraints if item.kind == LEFT_OF]
    assert kept == [left], (
        "with no single host side the declared lateral relation is an existing "
        "statement of the document; the compiler may keep it but must not "
        "invent a direction or drop it")
    assert (NEAR, "C9", "U1") not in _kinds(out)


def test_one_side_still_replaces_the_lateral_constraint():
    right = RelativeConstraint(
        RIGHT_OF, "C9", "U1",
        "ic-periphery: a generic right-of reading")
    near = RelativeConstraint(
        NEAR, "C9", "U1", "ic-periphery: near its host")

    out = _seated(False, right, near)

    assert (NEAR, "C9", "U1") not in _kinds(out)
    lateral = [item for item in out.constraints
               if item.kind in (LEFT_OF, RIGHT_OF)]
    assert [(item.kind, item.subject, item.object) for item in lateral] == [
        (LEFT_OF, "C9", "U1")], (
        "one known host side keeps the existing replacement: the branch reads "
        "left of the host, not the generic right-of the grammar emitted")
    assert "548J" in lateral[0].reason


def test_no_service_group_returns_the_binding_unchanged():
    near = RelativeConstraint(
        NEAR, "C9", "U1", "ic-periphery: near its host")
    left = RelativeConstraint(
        LEFT_OF, "C9", "U1", "ic-periphery: left of its host")
    binding = _binding(near, left)

    circuit = _circuit(False)
    spec = _spec(False, groups=False)
    out = dc._with_service_groups(binding, spec, circuit, _book(False))

    assert out is binding
    assert out == binding
