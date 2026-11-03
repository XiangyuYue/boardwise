"""543B: the opt-in service interval for a uniquely served shunt.

The batch adds one top-level PresentationSpec key, ``serviceLayout.pinGap``, and
consumes it only when 543A resolved a shunt to **one** host pin on the net the
branch already hangs on. These tests pin the mechanism and its guards:

* the key is absent from every document that does not state it, and an absent
  key draws the historical 60-unit branch (the old drawing is not enabled by
  default);
* a stated gap is the distance between the shunt's service pin and the one host
  pin, with the two on one row/column joined by one straight orthogonal segment;
* the page compiler's per-module slice carries the key (a slice that dropped it
  would draw the page and the standalone module differently);
* several equivalent host pins, several hosts at the same priority, a missing
  relation, a non-shunt role and a chain slot all keep the ordinary ladder —
  the key is a distance, not a licence to guess.

The CH343 acceptance attempt itself is evidence, not a test: with the merged,
lock-free page spec and ``pinGap: 30`` the page is refused by the existing
readability gate (C3's GND lead crosses U1's D+ label column), and 25/20 are
refused too. See ``evidence/543b/service_gap_attempt_*.txt``.
"""

from __future__ import annotations

import math

import pytest

import test_098_ic_periphery as e098

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec, PresentationSpecError
from boardwise.engines import drawcompiler as dc
from boardwise.engines import pagecompiler as pc
from boardwise.engines.layoutroles import analyze_decoupling

part = e098.part
net = e098.net
circuit = e098.circuit


def _payload(gap: float | None = None) -> dict:
    payload: dict = {
        "grammarRef": "ic-periphery",
        "modules": [
            {"id": "m", "parts": ["U1", "C1"], "role": "group", "core": "U1"}
        ],
    }
    if gap is not None:
        payload["serviceLayout"] = {"pinGap": gap}
    return payload


def _spec() -> CircuitSpec:
    """A core with one V3 shunt: U1.15 is the only host pin on the served net."""
    return circuit(
        [part("U1", "SOIC-16-CORE", "CH340G"), part("C1", "C0402", "100nF")],
        [
            net("VCC", "power", ["U1.16"]),
            net("GND", "gnd", ["U1.1", "C1.2"]),
            net("V3", "signal", ["U1.15", "C1.1"]),
        ],
    )


def _compile(spec: CircuitSpec, presentation: PresentationSpec):
    return dc.compile(spec, presentation, e098.library(), dc.CompileBudget())


def _service_distance(plan) -> tuple[float, float, float]:
    cap = e098.pin(plan, "C1.1")
    host = e098.pin(plan, "U1.15")
    return abs(cap[0] - host[0]) + abs(cap[1] - host[1]), cap[1], host[1]


# --------------------------------------------------------------- the key


def test_an_absent_key_is_not_serialised_and_keeps_the_old_distance():
    presentation = PresentationSpec.from_dict(_payload())

    assert presentation.service_layout is None
    assert "serviceLayout" not in presentation.to_jsonable()

    result = _compile(_spec(), presentation)
    assert result.ok, result.render_failures()
    distance, cap_y, host_y = _service_distance(result.candidates[0])
    assert (distance, cap_y, host_y) == (60.0, cap_y, host_y)
    assert cap_y == host_y


def test_the_stated_gap_is_the_service_pin_distance_and_one_straight_run():
    spec = _spec()
    presentation = PresentationSpec.from_dict(_payload(30))

    assert presentation.service_layout.pin_gap == 30.0
    assert presentation.to_jsonable()["serviceLayout"] == {"pinGap": 30.0}

    result = _compile(spec, presentation)
    assert result.ok, result.render_failures()
    plan = result.candidates[0]
    e098.clean(plan, spec, presentation)

    distance, cap_y, host_y = _service_distance(plan)
    assert distance == 30.0
    assert cap_y == host_y, "the service pin stays on the host pin's row"
    runs = [item for item in plan.segments if item.net == "V3"]
    assert len(runs) == 1, f"one straight V3 run, got {[item.points for item in runs]}"
    assert len(runs[0].points) == 2, "no bend on the service run"


def test_the_page_slice_carries_the_service_layout():
    spec = _spec()
    presentation = PresentationSpec.from_dict(_payload(30))
    module = presentation.module("m")

    local_circuit, local_presentation = pc._module_view(
        spec, presentation, module
    )

    assert local_presentation.service_layout is presentation.service_layout
    result = _compile(local_circuit, local_presentation)
    assert result.ok, result.render_failures()
    assert _service_distance(result.candidates[0])[0] == 30.0


@pytest.mark.parametrize("gap", [0, -5, "30", math.nan, math.inf])
def test_an_invalid_pin_gap_is_refused(gap):
    with pytest.raises(PresentationSpecError):
        PresentationSpec.from_dict(_payload(gap))


def test_a_service_layout_without_pin_gap_is_refused():
    payload = _payload()
    payload["serviceLayout"] = {}

    with pytest.raises(PresentationSpecError):
        PresentationSpec.from_dict(payload)


# -------------------------------------------------------------- the guards


def test_several_equivalent_host_pins_keep_the_ordinary_ladder():
    spec = circuit(
        [part("U1", "SOIC-16-CORE", "CH340G"), part("C1", "C0402", "100nF")],
        [
            net("VCC", "power", ["U1.16"]),
            net("GND", "gnd", ["U1.1", "C1.2"]),
            # Two host pins are electrically the served net: no unique pin.
            net("V3", "signal", ["U1.14", "U1.15", "C1.1"]),
        ],
    )
    presentation = PresentationSpec.from_dict(_payload(30))

    result = _compile(spec, presentation)
    assert result.ok, result.render_failures()
    cap = e098.pin(result.candidates[0], "C1.1")
    nearest = min(
        abs(cap[0] - e098.pin(result.candidates[0], member)[0])
        + abs(cap[1] - e098.pin(result.candidates[0], member)[1])
        for member in ("U1.14", "U1.15")
    )
    assert nearest != 30.0, "the interval was applied without a unique host pin"


def test_several_hosts_at_one_priority_are_not_shortened():
    spec = circuit(
        [part("U1", "SOIC-16-CORE", "CH340G"),
         part("U2", "SOIC-16-CORE", "CH340G"),
         part("C1", "C0402", "100nF")],
        [
            net("VCC", "power", ["U1.16", "U2.16"]),
            net("GND", "gnd", ["U1.1", "U2.1", "C1.2"]),
            net("V3", "signal", ["U1.15", "U2.15", "C1.1"]),
        ],
    )
    presentation = PresentationSpec.from_dict(
        {
            "grammarRef": "ic-periphery",
            "serviceLayout": {"pinGap": 30},
            "modules": [
                {"id": "m1", "parts": ["U1"], "role": "group", "core": "U1"},
                {"id": "m2", "parts": ["U2"], "role": "group", "core": "U2"},
                {"id": "plain", "parts": ["C1"], "role": "group"},
            ],
        }
    )
    relation = analyze_decoupling(spec, presentation).for_part("C1")
    assert relation.status == "ambiguous_host"
    assert relation.host_candidates == ("U1", "U2")

    slot = dc._Slot(
        part_id="C1", role="shunt", kind="branch", axis="h", rank=0,
        owner="U1", shared_net="V3", pin_shared="1",
    )

    class _Ctx:
        def __init__(self):
            self.circuit = spec
            self.presentation = presentation

        def services(self):
            return analyze_decoupling(self.circuit, self.presentation)

    assert dc._service_pin_gap(_Ctx(), slot) is None


def test_a_missing_relation_or_a_non_shunt_role_does_not_get_the_interval():
    presentation = PresentationSpec.from_dict(_payload(30))

    class _Ctx:
        circuit = _spec()
        presentation = PresentationSpec.from_dict(_payload(30))

        def services(self):
            return analyze_decoupling(self.circuit, self.presentation)

    shunt = dc._Slot(
        part_id="C1", role="shunt", kind="branch", axis="h", rank=0,
        owner="U1", shared_net="V3", pin_shared="1",
    )
    bridge = dc._Slot(
        part_id="C1", role="bridge", kind="branch", axis="h", rank=0,
        owner="U1", shared_net="V3", pin_shared="1",
    )
    unknown = dc._Slot(
        part_id="U1", role="shunt", kind="branch", axis="h", rank=0,
        owner="U1", shared_net="V3", pin_shared="1",
    )
    ctx = _Ctx()

    assert dc._service_pin_gap(ctx, shunt) == 30.0
    assert dc._service_pin_gap(ctx, bridge) is None
    assert dc._service_pin_gap(ctx, unknown) is None
    assert presentation.service_layout.pin_gap == 30.0
