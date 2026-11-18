"""DesignModel -> CircuitSpec, with incompleteness kept visible.

The parser already proved the model; this adapter only changes its shape. It does
not infer NCs, open interfaces, electrical classes, voltages or page hierarchy.
Those remain open questions or are enriched later from V4 flag evidence.
"""
from __future__ import annotations

from typing import Any

from ..core.circuitspec import CircuitSpec, SpecNet, SpecPart
from ..core.model import DesignModel


def _pin_key(pin: tuple[str, str]) -> tuple[str, int | str]:
    designator, number = pin
    try:
        return designator, 0, int(number)
    except (TypeError, ValueError):
        return designator, 1, str(number)


def circuit_spec_from_design_model(
    model: DesignModel,
    profiles: Any = None,
) -> tuple[CircuitSpec, dict[str, Any]]:
    """Convert one complete model, refusing any lossy/invalid representation."""
    repeated = sorted(set(model.duplicate_designators) | set(model.cross_page_designators))
    cross_board = sorted(getattr(model, "cross_board_designators", ()))
    if repeated:
        raise ValueError(
            "the model has repeated designators, so a CircuitSpec cannot name "
            "one placement without dropping another: " + ", ".join(repeated)
        )
    if not model.components:
        raise ValueError("the model has no components; an empty circuit is not a CircuitSpec")

    by_lcsc: dict[str, list[str]] = {}
    if profiles is not None:
        for symbol_ref, profile in profiles.items():
            _prefix, separator, number = symbol_ref.rpartition("-C")
            if separator and number.isdigit():
                by_lcsc.setdefault(f"C{number}", []).append(symbol_ref)

    parts: list[SpecPart] = []
    missing_refs: list[str] = []
    for designator in sorted(model.components):
        component = model.components[designator]
        symbol_ref = str(component.props.get("device_uuid") or "")
        if profiles is not None:
            candidates = sorted(by_lcsc.get(component.lcsc_part, []))
            if len(candidates) > 1:
                raise ValueError(
                    f"ambiguous measured profile/LCSC binding for {designator} "
                    f"({component.lcsc_part}): " + ", ".join(candidates)
                )
            symbol_ref = candidates[0] if candidates else ""
        if not symbol_ref:
            missing_refs.append(designator)
        parts.append(SpecPart(
            id=designator,
            symbol_ref=symbol_ref,
            value=component.value,
            mpn=component.mpn,
            lcsc=component.lcsc_part,
            provenance="",
        ))
    if missing_refs:
        reason = (
            "component(s) have no measured profile/LCSC binding for SpecPart.symbolRef: "
            if profiles is not None else
            "component(s) have no device_uuid for SpecPart.symbolRef: "
        )
        raise ValueError(reason + ", ".join(missing_refs))

    nets: list[SpecNet] = []
    for name in sorted(model.nets):
        net = model.nets[name]
        nets.append(SpecNet(
            id=name,
            members=[f"{designator}.{number}" for designator, number in sorted(
                net.pins, key=_pin_key,
            )],
            provenance="",
            scope="",
        ))

    single_member = sorted(name for name, net in model.nets.items() if len(net.pins) == 1)
    questions: list[dict[str, str]] = [{
        "kind": "nc-status-unproven",
        "detail": (
            "DesignModel does not carry a deliberate-NC decision; nc=[] only means "
            "no NC declaration was inferred, not that every unmentioned pin is connected."
        ),
    }]
    if single_member:
        questions.append({
            "kind": "open-interface-unproven",
            "detail": (
                "Single-member net(s) " + ", ".join(single_member)
                + " may be open interfaces, stubs, or truncated evidence; no "
                "SpecOpenInterface was invented."
            ),
        })
    if cross_board:
        questions.append({
            "kind": "cross-board-designator-shared",
            "detail": (
                "Designator(s) also used on another board were kept as board-local "
                "facts, not merged or treated as a within-board duplicate: "
                + ", ".join(cross_board)
            ),
        })
    unproven = []
    for name in sorted(model.unproven_nets):
        reason, detail = model.unproven_reason(name)
        unproven.append({
            "net": name,
            "pages": list(model.unproven_nets[name]),
            "reason": reason,
            "detail": detail,
        })
    return CircuitSpec(parts=parts, nets=nets), {
        "singleMemberNets": single_member,
        "openQuestions": questions,
        "unprovenNets": unproven,
        "crossBoardDesignators": cross_board,
    }
