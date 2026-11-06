"""543G-1: a shunt on a functional signal node is not a decoupling shunt.

543A reads a two-terminal grounded capacitor and asks which host core it serves.
That question has the same topology whether the capacitor shunts a supply pin or
loads a signal node, so on the second public topology (``ch340_serial``) it
answered "C1 serves U1 pin 7" for the crystal's load capacitor — and
``serviceLayout`` then dragged C1 away from X1, breaking the page's own
``adjacent(X1, C1)`` relation (0 candidates, 7 rejections).

What this file pins, all from circuit and presentation declarations — no refdes,
net name, pin number or net class literal is read for the verdict:

* the crystal lead capacitors report ``not_decoupling`` and the reason names the
  crystal (a functional member), not the net;
* the same part inside a rail-shaped node (one declared core + capacitor-class
  members) stays a decoupling shunt even when the net is declared ``signal`` —
  CH340's ``V3`` rail is exactly that shape;
* a declared ``power`` net is untouched: many capacitors and even a non-core
  member on it keep every shunt served (CH343's ``+5V`` carries the LED);
* an RC filter's capacitor is refused;
* renaming every part id and net id keeps every verdict;
* a core reached only through the net does not turn a signal node into a rail:
  the island-less reading that keeps ``ch343_power``'s C3 served still refuses
  the crystal lead, and an explicit ``attach`` names the host it serves.
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
    STATUS_NOT_DECOUPLING,
    STATUS_SERVED,
    analyze_decoupling,
)

SPEC_DIR = Path(__file__).resolve().parents[1] / "blocklib" / "specs"
CH340_CIRCUIT = SPEC_DIR / "ch340_serial.circuit.json"
CH340_PRESENTATION = SPEC_DIR / "ch340_serial.presentation.json"


def ch340_circuit() -> CircuitSpec:
    return CircuitSpec.load(CH340_CIRCUIT)


def ch340_presentation() -> PresentationSpec:
    return PresentationSpec.load(CH340_PRESENTATION)


def make_circuit(parts: list[tuple[str, str]], nets: list[tuple[str, str, list[str]]]):
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


def one_module(part_ids: list[str], core: str | None = None) -> PresentationSpec:
    module = {"id": "m", "parts": list(part_ids), "role": "group"}
    if core:
        module["core"] = core
    return make_presentation([module])


# ------------------------------------------------- real CH340 declarations


def test_ch340_crystal_load_caps_are_not_decoupling():
    analysis = analyze_decoupling(ch340_circuit(), ch340_presentation())

    for part_id in ("C1", "C2"):
        service = analysis.for_part(part_id)
        assert service is not None
        assert service.status == STATUS_NOT_DECOUPLING
        assert service.host_id is None and service.net_id is None
        # The reason names the functional member, not the net it sits on.
        assert "X1" in service.reason
        assert "pF" not in service.reason


def test_ch340_supply_caps_keep_their_relations():
    analysis = analyze_decoupling(ch340_circuit(), ch340_presentation())

    vcc = analysis.for_part("C3")
    assert vcc.status == STATUS_SERVED
    assert (vcc.host_id, vcc.net_id, vcc.host_pins) == ("U1", "VCC", ("16",))
    assert vcc.basis == BASIS_MODULE_CORE

    # `V3` is declared `signal` and is still a rail: one declared core plus
    # capacitor-class members is the shape the guard accepts.
    v3 = analysis.for_part("C4")
    assert v3.status == STATUS_SERVED
    assert (v3.host_id, v3.net_id, v3.host_pins) == ("U1", "V3", ("4",))


def test_ch340_analysis_still_covers_every_part_once():
    analysis = analyze_decoupling(ch340_circuit(), ch340_presentation())
    assert [service.part_id for service in analysis.services] == [
        "U1", "X1", "C1", "C2", "C3", "C4",
    ]
    assert [service.part_id for service in analysis.resolved] == ["C3", "C4"]


# ------------------------------------------------------- synthetic shapes


def test_a_rail_shaped_signal_node_with_parallel_caps_is_still_decoupling():
    """One declared core and capacitor-class members: no functional third party."""
    circuit = make_circuit(
        parts=[("U1", "CH343G"), ("C1", "100nF"), ("C2", "10uF")],
        nets=[
            ("GND", "gnd", ["U1.1", "C1.2", "C2.2"]),
            ("NODE", "signal", ["U1.4", "C1.1", "C2.1"]),
        ],
    )

    analysis = analyze_decoupling(circuit, one_module(["U1", "C1", "C2"], "U1"))

    for part_id in ("C1", "C2"):
        service = analysis.for_part(part_id)
        assert service.status == STATUS_SERVED
        assert (service.host_id, service.net_id) == ("U1", "NODE")
        assert service.host_pins == ("4",)


def test_a_declared_power_net_keeps_every_shunt_and_ignores_a_third_member():
    """A supply rail may carry another device (CH343's +5V carries the LED)."""
    circuit = make_circuit(
        parts=[("U1", "CH343G"), ("C1", "100nF"), ("C2", "10uF"), ("D1", "RED")],
        nets=[
            ("GND", "gnd", ["U1.1", "C1.2", "C2.2", "D1.2"]),
            ("RAIL", "power", ["U1.16", "C1.1", "C2.1", "D1.1"]),
        ],
    )

    analysis = analyze_decoupling(circuit, one_module(["U1", "C1", "C2", "D1"], "U1"))

    for part_id in ("C1", "C2"):
        service = analysis.for_part(part_id)
        assert service.status == STATUS_SERVED
        assert (service.host_id, service.net_id, service.host_pins) == (
            "U1", "RAIL", ("16",),
        )
    assert analysis.for_part("D1").status == STATUS_NOT_DECOUPLING


def test_an_rc_filter_capacitor_on_a_signal_node_is_refused():
    circuit = make_circuit(
        parts=[("U1", "CH343G"), ("R1", "1k"), ("C1", "100nF")],
        nets=[
            ("GND", "gnd", ["U1.1", "C1.2"]),
            ("NODE", "signal", ["U1.3", "R1.1", "C1.1"]),
            ("SRC", "signal", ["R1.2"]),
        ],
    )

    service = analyze_decoupling(
        circuit, one_module(["U1", "R1", "C1"], "U1")
    ).for_part("C1")

    assert service.status == STATUS_NOT_DECOUPLING
    assert service.host_id is None
    assert "R1" in service.reason


def test_a_declared_core_on_the_same_signal_net_does_not_disqualify():
    """Several ICs on one signal-class rail is a shared supply: host priority rules."""
    circuit = make_circuit(
        parts=[("U1", "CH343G"), ("U2", "CH343G"), ("C1", "100nF")],
        nets=[
            ("GND", "gnd", ["U1.1", "U2.1", "C1.2"]),
            ("NODE", "signal", ["U1.4", "U2.4", "C1.1"]),
        ],
    )
    presentation = make_presentation(
        [
            {"id": "own", "parts": ["U1", "C1"], "role": "group", "core": "U1"},
            {"id": "beside", "parts": ["U2"], "role": "group", "core": "U2"},
        ]
    )

    service = analyze_decoupling(circuit, presentation).for_part("C1")

    assert service.status == STATUS_SERVED
    assert service.host_id == "U1"


def test_a_core_reached_only_through_the_net_does_not_turn_a_signal_node_into_a_rail():
    """An island's core may name the host; it may not outvote the node's members."""
    parts = [("U1", "CH343G"), ("X1", "12MHz"), ("C1", "22pF"), ("C2", "100nF")]
    circuit = make_circuit(
        parts=parts,
        nets=[
            ("GND", "gnd", ["U1.1", "X1.2", "C1.2", "C2.2"]),
            ("XI", "signal", ["U1.7", "X1.1", "C1.1"]),
            ("V3", "signal", ["U1.4", "C2.1"]),
        ],
    )
    # The crystal load sits in its own island with no core and no `attach`; the
    # only core on `XI` is U1's, an island away.
    presentation = make_presentation(
        [
            {"id": "bridge", "parts": ["U1"], "role": "group", "core": "U1"},
            {"id": "clock", "parts": ["X1", "C1"], "role": "group"},
            {"id": "power", "parts": ["C2"], "role": "group"},
        ]
    )

    analysis = analyze_decoupling(circuit, presentation)

    load = analysis.for_part("C1")
    assert load.status == STATUS_NOT_DECOUPLING
    assert load.host_id is None
    assert "X1" in load.reason

    # The same unattached-island reading on a rail-shaped node still resolves
    # (this is how `ch343_power`'s C3 reads), so the guard is about the node's
    # members, not about refusing island-less hosts.
    bypass = analysis.for_part("C2")
    assert bypass.status == STATUS_SERVED
    assert (bypass.host_id, bypass.net_id) == ("U1", "V3")


def test_an_attached_island_names_the_host_it_serves():
    circuit = make_circuit(
        parts=[("U1", "CH343G"), ("C1", "100nF")],
        nets=[
            ("GND", "gnd", ["U1.1", "C1.2"]),
            ("NODE", "signal", ["U1.4", "C1.1"]),
        ],
    )
    attached = make_presentation(
        [
            {"id": "bridge", "parts": ["U1"], "role": "group", "core": "U1"},
            {"id": "bypass", "parts": ["C1"], "role": "group",
             "attach": {"to": "bridge"}},
        ]
    )

    settled = analyze_decoupling(circuit, attached).for_part("C1")

    assert settled.status == STATUS_SERVED
    assert settled.host_id == "U1"
    assert settled.basis == BASIS_ATTACH_CORE


# ----------------------------------------------------------- renaming


def _renamed() -> tuple[CircuitSpec, PresentationSpec, dict[str, str], dict[str, str]]:
    payload = json.loads(CH340_CIRCUIT.read_text(encoding="utf-8"))
    part_map = {part["id"]: f"P{index}" for index, part in enumerate(payload["parts"])}
    net_map = {net["id"]: f"N{index}" for index, net in enumerate(payload["nets"])}

    def rename_pin(member: str) -> str:
        part_id, _, pin = member.partition(".")
        return f"{part_map[part_id]}.{pin}"

    for part in payload["parts"]:
        part["id"] = part_map[part["id"]]
    for net in payload["nets"]:
        net["id"] = net_map[net["id"]]
        net["members"] = [rename_pin(member) for member in net["members"]]
    for entry in payload.get("nc", []):
        entry["pin"] = rename_pin(entry["pin"])
    for interface in payload.get("openInterfaces", []):
        interface["net"] = net_map[interface["net"]]

    modules = json.loads(CH340_PRESENTATION.read_text(encoding="utf-8"))["modules"]
    for module in modules:
        module["parts"] = [part_map[part_id] for part_id in module["parts"]]
        if module.get("core"):
            module["core"] = part_map[module["core"]]

    return (
        CircuitSpec.from_dict(payload),
        PresentationSpec.from_dict({"modules": modules}),
        part_map,
        net_map,
    )


def test_renaming_every_id_and_net_keeps_every_verdict():
    circuit, presentation, part_map, net_map = _renamed()
    analysis = analyze_decoupling(circuit, presentation)

    crystal = part_map["X1"]
    for original in ("C1", "C2"):
        service = analysis.for_part(part_map[original])
        assert service.status == STATUS_NOT_DECOUPLING
        assert crystal in service.reason

    vcc = analysis.for_part(part_map["C3"])
    assert vcc.status == STATUS_SERVED
    assert (vcc.host_id, vcc.net_id) == (part_map["U1"], net_map["VCC"])

    v3 = analysis.for_part(part_map["C4"])
    assert v3.status == STATUS_SERVED
    assert (v3.host_id, v3.net_id, v3.host_pins) == (
        part_map["U1"], net_map["V3"], ("4",),
    )
