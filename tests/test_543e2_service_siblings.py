"""543E-2: a second shunt on the same host pin takes a perpendicular seat.

The first shunt keeps the 543B/C baseline: one straight 30-unit run along the
host pin's own escape direction. A later shunt on **the same host pin** may not
share that origin; the compiler tries the two perpendicular seats at the same
interval, and only accepts one whose 30-unit run is straight and clear. U1.15's
neighbours sit 20 units above and below on the same side, so both perpendicular
runs cross another pin tip: there is no legal seat, and the drawing is refused
as `layout-unsat` naming `U1.15` — never returned as an overlapping `ok=True`.

This file pins that outcome and the physical reason, plus the unchanged
single-shunt baseline.
"""

from __future__ import annotations

import test_543e_perturbations as e


def _add_c5(raw):
    raw["parts"].append({
        "id": "C5", "symbolRef": "C0603-100nF-C1590", "value": "100nF",
        "lcsc": "C1590", "mpn": "CL10B104KA8NNNC",
        "provenance": "engineer_confirmed",
    })
    for net in raw["nets"]:
        if net["id"] == "VCC":
            net["members"].append("C5.1")
        if net["id"] == "GND":
            net["members"].append("C5.2")


def _add_c5_result():
    circuit = e._circuit(_add_c5)
    presentation = e._presentation(["U1", "C3", "C4", "C5"])
    return circuit, presentation, e._compile(circuit, presentation, e._book())


def test_one_shunt_keeps_the_baseline_horizontal_thirty():
    circuit = e._circuit()
    page = e._first_page(e._compile(circuit, e._presentation(), e._book()))
    service = e._service(page, "C4", "15", "VCC", e._book())
    assert service["manhattan"] == 30.0
    assert service["same_row"] and service["straight"]
    assert service["cap_point"][0] != service["host_point"][0]
    assert service["cap_point"][1] == service["host_point"][1]


def test_two_shunts_on_one_host_pin_are_a_named_layout_unsat():
    _circuit, _presentation, result = _add_c5_result()
    assert not result.ok
    assert result.pages == []
    failure = result.failures[0]
    assert failure.category == "layout-unsat"
    assert "C5" in failure.detail
    assert "U1.15" in failure.detail
    assert "first shunt's origin" in failure.detail


def test_the_perpendicular_seats_really_cross_u1_neighbours():
    # The refusal is a physical fact, not a missing search: both vertical
    # candidates from U1.15 (x=785) pass U1.16 (760) or U1.14 (740), 10 units
    # away on the same x — a 30-unit vertical run crosses one of them.
    page = e._first_page(
        e._compile(e._circuit(), e._presentation(), e._book())
    )
    host = e._pin(page.plan, "U1.15", e._book())
    above = e._pin(page.plan, "U1.16", e._book())
    below = e._pin(page.plan, "U1.14", e._book())
    assert host[0] == above[0] == below[0]
    assert 0 < abs(host[1] - above[1]) < 30
    assert 0 < abs(host[1] - below[1]) < 30
