"""547F: `module_plan` reads a pin's number and its name as the same identity.

The measured trigger is the real STM32G431RBT6 profile from
`evidence/547/g4/live/profiles/profiles.json`: pin 17 is named ``PA3``, pin 7 is
named ``PG10-NRST``, and the 547 live circuit writes its members as
``U1.PA3``.  `module_plan` built its declaration set from ``pin.number`` alone
(`drawapply.py` 547F), so a legal drawing was refused with *"the circuit spec
connects pin(s) the library symbol does not carry: U1.PA3, …"* and the G4 real
geometry could never become a `ChangePlan`.

What is pinned here:

1. a member spelled with the symbol's own pin **name** (``U1.PA3``) and one
   spelled with the ``<port>-<function>`` alias a host library writes
   (``U1.NRST`` against ``PG10-NRST``) both resolve to the pin's own **number** —
   the identity the plan's pin table and the editor's read-back share;
2. the number path is unchanged;
3. a token no profile pin answers (``U1.PA4``) is still refused by name — the
   missing check is not skipped;
4. a name carried by several pins (``VDD`` on 16/32/48/64) does not multiply the
   island or the plan's pin table: it is one node, stated in numbers.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.layoutplan import LayoutPlan
from boardwise.core.presentationspec import PresentationSpec
from boardwise.engines import drawapply
from boardwise.engines.drawapply import DrawPlanError

# The numbers and names are the measured ones the 547 G4D calibration recorded
# (17=PA3, 7=PG10-NRST, 16/32/48/64=VDD, 15/31/47/63=VSS, 61=PB8-BOOT0); the tips
# are this test's own layout, only so the fixture is a drawable symbol.
PINS = [
    ("1", "PC13", (0.0, -120.0)),
    ("7", "PG10-NRST", (-120.0, 100.0)),
    ("15", "VSS", (-60.0, -120.0)),
    ("16", "VDD", (60.0, 120.0)),
    ("17", "PA3", (0.0, 120.0)),
    ("31", "VSS", (-40.0, -100.0)),
    ("32", "VDD", (40.0, 120.0)),
    ("47", "VSS", (-20.0, -80.0)),
    ("48", "VDD", (20.0, 120.0)),
    ("56", "PB3", (120.0, 0.0)),
    ("61", "PB8-BOOT0", (-120.0, -100.0)),
    ("63", "VSS", (-80.0, -140.0)),
    ("64", "VDD", (80.0, 120.0)),
]


def _library() -> dict:
    return {
        "profiles": [
            {
                "kind": "boardwise-symbol-profile",
                "profileVersion": 1,
                "symbolRef": "STM32G431RBT6",
                "title": "STM32G431RBT6",
                "body": [-90.0, -140.0, 90.0, 140.0],
                "pins": [
                    {
                        "number": number,
                        "name": name,
                        "tip": [tip[0], tip[1]],
                        "direction": "up" if tip[1] > 0 else "down",
                    }
                    for number, name, tip in PINS
                ],
            }
        ]
    }


def _presentation() -> dict:
    return {
        "grammarRef": "voltage-divider",
        "modules": [{"id": "mcu", "parts": ["U1"], "role": "divider"}],
    }


def _circuit(nets: list[dict]) -> dict:
    return {
        "parts": [
            {
                "id": "U1",
                "symbolRef": "STM32G431RBT6",
                "value": "STM32G431RBT6",
                "lcsc": "C784940",
                "provenance": "verified_recipe",
            }
        ],
        "nets": nets,
    }


def _net(net_id: str, members: list[str], cls: str = "signal") -> dict:
    return {
        "id": net_id,
        "class": cls,
        "members": members,
        "provenance": "verified_recipe",
    }


def _write(tmp_path: Path, circuit: dict, presentation: dict, library: dict):
    (tmp_path / "circuit.json").write_text(
        json.dumps(circuit, indent=2) + "\n", encoding="utf-8"
    )
    (tmp_path / "presentation.json").write_text(
        json.dumps(presentation, indent=2) + "\n", encoding="utf-8"
    )
    (tmp_path / "library.json").write_text(
        json.dumps(library, indent=2) + "\n", encoding="utf-8"
    )
    circuit_spec = CircuitSpec.load(tmp_path / "circuit.json")
    presentation_spec = PresentationSpec.load(tmp_path / "presentation.json")
    profiles = drawapply.load_library(tmp_path / "library.json")
    profile = profiles["STM32G431RBT6"]
    layout = {
        "kind": "boardwise-layout-plan",
        "planVersion": 1,
        "source": {
            "circuitSha256": circuit_spec.sha256(),
            "presentationSha256": presentation_spec.sha256(),
        },
        "parts": [
            {
                "partId": "U1",
                "reference": "U1",
                "symbolRef": "STM32G431RBT6",
                "symbolHash": profile.geometry_hash(),
                "x": 0.0,
                "y": 0.0,
                "rotation": 0.0,
                "mirror": False,
            }
        ],
        "segments": [],
        "labels": [],
        "powerSymbols": [],
        "texts": [],
    }
    (tmp_path / "layout.json").write_text(
        json.dumps(layout, indent=2) + "\n", encoding="utf-8"
    )
    return circuit_spec, presentation_spec, profiles, LayoutPlan.load(
        tmp_path / "layout.json"
    )


def _plan(tmp_path: Path, circuit: dict):
    circuit_spec, presentation_spec, profiles, layout = _write(
        tmp_path, circuit, _presentation(), _library()
    )
    return drawapply.module_plan(layout, circuit_spec, presentation_spec, profiles)


def _islands(plan) -> dict[str, list[str]]:
    return {island.pin: sorted(island.mates) for island in plan.change.islands}


# ------------------------------------------------------------------ the fix


def test_named_pin_and_numbered_pin_are_one_identity(tmp_path: Path):
    """`U1.PA3` / `U1.NRST` / `U1.PB8-BOOT0` are the pins 17 / 7 / 61."""
    plan = _plan(tmp_path, _circuit([
        _net("LED1_K", ["U1.PA3"]),
        _net("NRST", ["U1.NRST"]),
        _net("BOOT0", ["U1.PB8-BOOT0"]),
        _net("NUMBERED", ["U1.56"]),
    ]))
    islands = _islands(plan)
    assert islands["U1.17"] == ["U1.17"]
    assert islands["U1.7"] == ["U1.7"]
    assert islands["U1.56"] == ["U1.56"]
    # The alias the host writes on the boot pin names 61 too, by the same rule.
    assert islands["U1.61"] == ["U1.61"]
    # Nothing is left spelled as a name: the expectation is in numbers.
    assert not [pin for pin in islands if not pin.partition(".")[2].isdigit()]


def test_number_path_is_unchanged(tmp_path: Path):
    """A spec that writes numbers (what every pre-547 page does) is untouched."""
    plan = _plan(tmp_path, _circuit([_net("NRST", ["U1.7"]), _net("SIG", ["U1.17"])]))
    assert _islands(plan) == {"U1.7": ["U1.7"], "U1.17": ["U1.17"]}


def test_unknown_named_token_is_still_refused(tmp_path: Path):
    """`U1.PA4` is not on this symbol: the missing check still names it."""
    with pytest.raises(DrawPlanError) as caught:
        _plan(tmp_path, _circuit([_net("LED2_K", ["U1.PA4"])]))
    message = str(caught.value)
    assert "U1.PA4" in message
    assert "does not carry" in message


def test_duplicate_pin_name_is_one_node_not_four_entries(tmp_path: Path):
    """`VDD` names 16/32/48/64: one node, stated once per number, no duplicates."""
    plan = _plan(tmp_path, _circuit([_net("3V3", ["U1.VDD"], "power")]))
    islands = _islands(plan)
    assert sorted(islands) == ["U1.16", "U1.32", "U1.48", "U1.64"]
    for pin, mates in islands.items():
        assert mates == ["U1.16", "U1.32", "U1.48", "U1.64"]
        assert len(mates) == len(set(mates))
    assert not [pin for pin in islands if pin == "U1.VDD"]
    # The plan's own pin table is the profile's, once each.
    part = plan.change.draw_parts[0]
    numbers = [pin.number for pin in part.pins]
    assert sorted(numbers) == sorted(number for number, _name, _tip in PINS)
    assert len(numbers) == len(set(numbers))
