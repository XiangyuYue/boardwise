"""543A: the decoupling service relation, read from topology alone.

The batch's question is "which host core, which net, and which of the host's
pins does this two-terminal shunt capacitor serve". These tests pin the four
properties the task book makes acceptance criteria:

* the CH343 relations (C3 -> U1 pin 4 on V3, C4 -> U1 pin 15 on VCC, C1/C2 ->
  USB1 on +5V with both equivalent VBUS contacts kept);
* every part id and every net id may be renamed and the same relations come
  back, so nothing is inferred from a refdes letter or a net's spelling;
* equal-priority hosts are reported as an ambiguity, never as the first
  candidate, and a host with several equivalent pins keeps the whole set;
* a non-capacitor two-terminal part is not a decoupling shunt, and a capacitor
  with no host says so instead of inventing one.

The presentation payload is the module structure of the current CH343
presentation (``.tmp_fix/v42.presentation.json``); it is written inline because
that file is a 534 work-in-progress artifact and the test must not depend on it.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.engines.layoutroles import (
    BASIS_ATTACH_CORE,
    BASIS_MODULE_CORE,
    STATUS_AMBIGUOUS_HOST,
    STATUS_AMBIGUOUS_NET,
    STATUS_NO_HOST,
    STATUS_NOT_DECOUPLING,
    STATUS_SERVED,
    analyze_decoupling,
)

SPEC_DIR = Path(__file__).resolve().parents[1] / "blocklib" / "specs"
CH343_CIRCUIT = SPEC_DIR / "ch343_uart_534a.circuit.json"

#: `modules` of the current CH343 presentation, verbatim. The `caps` module is
#: the one that carries an `attach`; everything else is context for the netlist
#: priorities (and for the C1/C2 own-module core).
CH343_MODULES = [
    {"id": "usb_c", "parts": ["USB1", "C1", "C2", "R1", "R2"], "role": "group", "core": "USB1"},
    {"id": "ch343", "parts": ["U1"], "role": "group", "core": "U1"},
    {"id": "hdr", "parts": ["H1"], "role": "group", "core": "H1"},
    {"id": "led", "parts": ["D1", "R3"], "role": "group"},
    {"id": "caps", "parts": ["C3", "C4"], "role": "group", "attach": {"to": "ch343"}},
]


def ch343_presentation() -> PresentationSpec:
    return PresentationSpec.from_dict({"modules": copy.deepcopy(CH343_MODULES)})


def ch343_circuit() -> CircuitSpec:
    return CircuitSpec.load(CH343_CIRCUIT)


def make_circuit(parts: list[tuple[str, str]], nets: list[tuple[str, str, list[str]]]):
    """A minimal valid CircuitSpec: ``(id, value)`` parts, ``(id, class, pins)`` nets."""
    return CircuitSpec.from_dict(
        {
            "kind": "boardwise-circuit-spec",
            "specVersion": 1,
            "parts": [
                {"id": part_id, "symbolRef": f"SYM-{part_id}", "value": value}
                for part_id, value in parts
            ],
            "nets": [
                {"id": net_id, "class": cls, "members": members}
                for net_id, cls, members in nets
            ],
        }
    )


def make_presentation(modules: list[dict]) -> PresentationSpec:
    return PresentationSpec.from_dict({"modules": copy.deepcopy(modules)})


# ------------------------------------------------------------ CH343 relations


def test_ch343_c3_serves_u1_pin_4_on_v3():
    analysis = analyze_decoupling(ch343_circuit(), ch343_presentation())
    service = analysis.for_part("C3")

    assert service is not None
    assert service.status == STATUS_SERVED
    assert (service.host_id, service.net_id) == ("U1", "V3")
    assert service.host_pins == ("4",)
    assert service.has_unique_host_pin
    assert (service.service_pin, service.return_pin) == ("1", "2")
    assert service.host_module == "ch343"
    # `caps` has no core; the relation came from its attach host.
    assert service.basis == BASIS_ATTACH_CORE


def test_ch343_c4_serves_u1_pin_15_on_vcc():
    analysis = analyze_decoupling(ch343_circuit(), ch343_presentation())
    service = analysis.for_part("C4")

    assert service is not None
    assert service.status == STATUS_SERVED
    assert (service.host_id, service.net_id) == ("U1", "VCC")
    assert service.host_pins == ("15",)
    assert service.has_unique_host_pin
    assert (service.service_pin, service.return_pin) == ("1", "2")
    assert service.host_module == "ch343"
    assert service.basis == BASIS_ATTACH_CORE


def test_ch343_c1_and_c2_serve_usb1_on_the_five_volt_net_with_both_contacts():
    analysis = analyze_decoupling(ch343_circuit(), ch343_presentation())

    for part_id in ("C1", "C2"):
        service = analysis.for_part(part_id)
        assert service is not None
        assert service.status == STATUS_SERVED
        assert (service.host_id, service.net_id) == ("USB1", "+5V")
        assert service.host_module == "usb_c"
        assert service.basis == BASIS_MODULE_CORE
        # Both Type-C VBUS contacts sit on +5V; the whole set is the answer.
        assert service.host_pins == ("A4B9", "B4A9")
        assert not service.has_unique_host_pin
        assert (service.service_pin, service.return_pin) == ("1", "2")


def test_ch343_analysis_is_pure_and_covers_every_part():
    circuit, presentation = ch343_circuit(), ch343_presentation()
    before_circuit = circuit.to_jsonable()
    before_presentation = presentation.to_jsonable()

    analysis = analyze_decoupling(circuit, presentation)

    assert circuit.to_jsonable() == before_circuit
    assert presentation.to_jsonable() == before_presentation
    assert {service.part_id for service in analysis.services} == set(circuit.part_ids())
    for part_id in ("R1", "R2", "R3", "D1", "U1", "USB1", "H1"):
        service = analysis.for_part(part_id)
        assert service is not None
        assert service.status == STATUS_NOT_DECOUPLING
        assert service.host_id is None and service.net_id is None


# ------------------------------------------------------- ids and names renamed


def _renamed_payloads() -> tuple[
    CircuitSpec, PresentationSpec, dict[str, str], dict[str, str]
]:
    """CH343 with every part id, net id, module id and module reference renamed."""
    circuit_payload = json.loads(CH343_CIRCUIT.read_text(encoding="utf-8"))
    part_map = {
        part["id"]: f"P{index}"
        for index, part in enumerate(circuit_payload["parts"])
    }
    net_map = {
        net["id"]: f"N{index}"
        for index, net in enumerate(circuit_payload["nets"])
    }

    def rename_pin(member: str) -> str:
        part_id, _, pin = member.partition(".")
        return f"{part_map[part_id]}.{pin}"

    for part in circuit_payload["parts"]:
        part["id"] = part_map[part["id"]]
    for net in circuit_payload["nets"]:
        net["id"] = net_map[net["id"]]
        net["members"] = [rename_pin(member) for member in net["members"]]
    for entry in circuit_payload.get("nc", []):
        entry["pin"] = rename_pin(entry["pin"])
    for interface in circuit_payload.get("openInterfaces", []):
        interface["net"] = net_map[interface["net"]]

    module_map = {
        module["id"]: f"M{index}"
        for index, module in enumerate(CH343_MODULES)
    }
    modules = copy.deepcopy(CH343_MODULES)
    for module in modules:
        module["id"] = module_map[module["id"]]
        module["parts"] = [part_map[part_id] for part_id in module["parts"]]
        if module.get("core"):
            module["core"] = part_map[module["core"]]
        if module.get("attach"):
            module["attach"]["to"] = module_map[module["attach"]["to"]]

    return (
        CircuitSpec.from_dict(circuit_payload),
        PresentationSpec.from_dict({"modules": modules}),
        part_map,
        net_map,
    )


def test_renaming_every_id_and_net_name_keeps_the_relations():
    circuit, presentation, part_map, net_map = _renamed_payloads()
    analysis = analyze_decoupling(circuit, presentation)

    c3 = analysis.for_part(part_map["C3"])
    assert c3.status == STATUS_SERVED
    assert (c3.host_id, c3.net_id) == (part_map["U1"], net_map["V3"])
    assert c3.host_pins == ("4",)

    c4 = analysis.for_part(part_map["C4"])
    assert c4.status == STATUS_SERVED
    assert (c4.host_id, c4.net_id) == (part_map["U1"], net_map["VCC"])
    assert c4.host_pins == ("15",)

    for original in ("C1", "C2"):
        service = analysis.for_part(part_map[original])
        assert service.status == STATUS_SERVED
        assert (service.host_id, service.net_id) == (
            part_map["USB1"],
            net_map["+5V"],
        )
        assert service.host_pins == ("A4B9", "B4A9")

    assert analysis.for_part(part_map["R1"]).status == STATUS_NOT_DECOUPLING


# ------------------------------------------------------------ host priority


def test_a_caps_own_module_core_outranks_its_attach_host():
    circuit = make_circuit(
        parts=[("U1", "CH343G"), ("U2", "CH343G"), ("C1", "100nF")],
        nets=[
            ("GND", "gnd", ["U1.1", "U2.1", "C1.2"]),
            ("V3", "signal", ["U1.4", "U2.4", "C1.1"]),
        ],
    )
    presentation = make_presentation(
        [
            {"id": "own", "parts": ["U1", "C1"], "role": "group", "core": "U1",
             "attach": {"to": "beside"}},
            {"id": "beside", "parts": ["U2"], "role": "group", "core": "U2"},
        ]
    )

    service = analyze_decoupling(circuit, presentation).for_part("C1")

    assert service.status == STATUS_SERVED
    assert service.host_id == "U1"
    assert service.basis == BASIS_MODULE_CORE


# ------------------------------------------------------- honest non-answers


def test_equal_priority_hosts_are_an_ambiguity_not_the_first_one():
    circuit = make_circuit(
        parts=[("U1", "CH343G"), ("U2", "CH343G"), ("C1", "100nF")],
        nets=[
            ("GND", "gnd", ["U1.1", "U2.1", "C1.2"]),
            ("V3", "signal", ["U1.4", "U2.4", "C1.1"]),
        ],
    )
    presentation = make_presentation(
        [
            {"id": "m1", "parts": ["U1"], "role": "group", "core": "U1"},
            {"id": "m2", "parts": ["U2"], "role": "group", "core": "U2"},
            {"id": "plain", "parts": ["C1"], "role": "group"},
        ]
    )

    service = analyze_decoupling(circuit, presentation).for_part("C1")

    assert service.status == STATUS_AMBIGUOUS_HOST
    assert service.host_id is None
    assert service.host_pins == ()
    assert service.host_candidates == ("U1", "U2")
    assert "refusing to pick the first" in service.reason


def test_one_host_on_two_rails_is_an_ambiguous_net():
    circuit = make_circuit(
        parts=[("U1", "CH343G"), ("C1", "100nF")],
        nets=[
            ("RAIL_A", "power", ["U1.4", "C1.1"]),
            ("RAIL_B", "power", ["U1.5", "C1.2"]),
        ],
    )
    presentation = make_presentation([{"id": "m1", "parts": ["U1"], "role": "group", "core": "U1"}])

    service = analyze_decoupling(circuit, presentation).for_part("C1")

    assert service.status == STATUS_AMBIGUOUS_NET
    assert service.host_id == "U1"
    assert service.net_id is None
    assert service.host_candidates == ("U1",)


def test_a_capacitor_with_no_host_on_its_net_says_no_host():
    circuit = make_circuit(
        parts=[("C1", "100nF"), ("R1", "1k")],
        nets=[
            ("GND", "gnd", ["C1.2", "R1.2"]),
            ("SIG", "signal", ["C1.1", "R1.1"]),
        ],
    )
    presentation = make_presentation([{"id": "plain", "parts": ["C1", "R1"], "role": "group"}])

    service = analyze_decoupling(circuit, presentation).for_part("C1")

    assert service.status == STATUS_NO_HOST
    assert service.host_id is None
    assert service.net_id is None


def test_a_non_capacitor_two_terminal_part_is_not_a_decoupling_shunt():
    circuit = make_circuit(
        parts=[("U1", "CH343G"), ("R1", "5.1k"), ("D1", "RED")],
        nets=[
            ("GND", "gnd", ["U1.1", "R1.2", "D1.2"]),
            ("V3", "signal", ["U1.4", "R1.1"]),
            ("LED_A", "signal", ["D1.1", "U1.5"]),
        ],
    )
    presentation = make_presentation([{"id": "m1", "parts": ["U1"], "role": "group", "core": "U1"}])

    analysis = analyze_decoupling(circuit, presentation)

    for part_id in ("R1", "D1"):
        service = analysis.for_part(part_id)
        assert service.status == STATUS_NOT_DECOUPLING
        assert service.host_id is None and service.net_id is None


def test_a_capacitor_with_three_terminals_is_not_a_two_terminal_shunt():
    circuit = make_circuit(
        parts=[("U1", "CH343G"), ("C1", "100nF")],
        nets=[
            ("GND", "gnd", ["U1.1", "C1.2"]),
            ("V3", "signal", ["U1.4", "C1.1"]),
            ("VCC", "power", ["U1.15", "C1.3"]),
        ],
    )
    presentation = make_presentation([{"id": "m1", "parts": ["U1"], "role": "group", "core": "U1"}])

    service = analyze_decoupling(circuit, presentation).for_part("C1")

    assert service.status == STATUS_NOT_DECOUPLING
    assert service.host_id is None
