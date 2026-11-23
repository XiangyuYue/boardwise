"""548P44: optional captured art replaces diagnostic glyphs in the same renderer.

All symbols and SVG below are handwritten synthetic inputs. No ignored evidence,
live editor, compiler or assembly builder is used by these tests.
"""

from __future__ import annotations

import hashlib
import re
from xml.etree import ElementTree as ET

import pytest

from boardwise.core.layoutplan import (
    LayoutPart, LayoutPlan, LayoutPowerSymbol, LayoutSegment, LayoutText,
)
from boardwise.core.symbolprofile import SymbolPin, SymbolProfile
from boardwise.engines import svgpreview


SVG = "http://www.w3.org/2000/svg"
PAGE = (10.0, 20.0, 110.0, 120.0)
# Includes the measured 7.006px native-text attribute on LayoutText; the rest of
# the default diagnostic output is unchanged (see test_svgpreview_native_text.py).
DEFAULT_SHA256 = "d66a1b4859e7beceaaf12ade8007c243e0fe053c430319628699f6f2ba7a3253"
SOURCE = "548P44 handwritten captured-pose test art; not a live calibration"
ART = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="-15 -10 30 20">
<style>*{stroke-linejoin:round}.pin-bar{stroke:#880000}</style>
<g id="body" c_partid="part">
  <line id="plate" data-probe="plate" x1="0" y1="-4" x2="0" y2="4" style="stroke:#A00000;fill:none"/>
  <g id="terminal" c_partid="part_pin">
    <path id="lead" data-probe="pin" d="M -10 0 h 5" class="pin-bar" style="stroke:#880000;fill:none"/>
    <text id="pin-name" c_partid="part_attr" x="-3" y="-2" style="font-family:Arial;font-size:7px">NATIVE_IN</text>
  </g>
</g></svg>"""


def _case(*, duplicate=False):
    parts = [LayoutPart(part_id="U1", symbol_ref="SYN", x=30, y=40, reference="U1")]
    if duplicate:
        parts.append(LayoutPart(part_id="U2", symbol_ref="SYN", x=80, y=70, reference="U2"))
    plan = LayoutPlan(
        parts=parts,
        segments=[LayoutSegment(net="SIG", points=[(20, 40), (10, 40)])],
        texts=[LayoutText(kind="reference", text="PLAN_U1", part_id="U1",
                          bbox=(25, 52, 45, 61))],
    )
    book = {"SYN": SymbolProfile(
        symbol_ref="SYN", body=(-5, -5, 5, 5),
        pins=[SymbolPin(number="1", name="IN", tip=(-10, 0), direction="left", length=5)],
    )}
    return plan, book


def _art(**changes):
    fields = dict(symbol_ref="SYN", rotation=0.0, mirror=False, svg=ART, source=SOURCE)
    fields.update(changes)
    return svgpreview.NativeSymbolArt(**fields)


def _render(plan=None, book=None, **options):
    if plan is None:
        plan, book = _case()
    return svgpreview.render_svg(
        plan, book, page_box=PAGE, title="P44 synthetic preview", scale=2.0, **options,
    )


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _probe(root, kind):
    return [node for node in root.iter() if node.get("data-probe") == kind]


def _world(root, node, point):
    """Independently compose the actual SVG ancestors' affine transforms."""
    parents = {child: parent for parent in root.iter() for child in parent}
    chain = []
    current = node
    while current is not None:
        chain.append(current)
        current = parents.get(current)
    x, y = point
    # Applying a nested SVG transform goes from the leaf out; each transform's
    # operations themselves apply right to left under the SVG column convention.
    for item in chain:
        operations = re.findall(r"([A-Za-z]+)\s*\(([^)]*)\)", item.get("transform", ""))
        for name, raw in reversed(operations):
            values = [float(value) for value in re.split(r"[ ,]+", raw.strip()) if value]
            if name == "translate":
                x += values[0]
                y += values[1] if len(values) == 2 else 0
            elif name == "scale":
                x *= values[0]
                y *= values[1] if len(values) == 2 else values[0]
            elif name == "matrix":
                a, b, c, d, tx, ty = values
                x, y = a * x + c * y + tx, b * x + d * y + ty
            else:
                pytest.fail(f"captured art was unexpectedly rotated or mirrored: {name}")
    return x, y


def test_no_art_default_matches_the_original_svg_snapshot():
    actual = _render()
    assert hashlib.sha256(actual.encode()).hexdigest() == DEFAULT_SHA256
    assert 'r="2.2"' in actual and 'r="1.6"' in actual


def test_explicit_empty_art_keeps_the_original_default_bytes():
    assert _render(native_art=()) == _render()


def test_native_geometry_and_pin_name_replace_fallback_marks_but_keep_plan_ink():
    rendered = _render(native_art=[_art()])
    root = ET.fromstring(rendered)
    assert len(_probe(root, "plate")) == len(_probe(root, "pin")) == 1
    assert "NATIVE_IN" in "".join(root.itertext())
    assert "PLAN_U1" in "".join(root.itertext())
    assert 'r="2.2"' not in rendered and 'r="1.6"' not in rendered
    assert not any(node.get("fill") == "#e8e8e8" for node in root.iter())
    assert any(_local(node.tag) == "polyline" and node.get("stroke") == "#0b6b3a"
               for node in root.iter()), "plan conductors still use the existing renderer"
    assert _probe(root, "pin")[0].get("style") == "stroke:#880000;fill:none"
    assert "diagnostic" in "".join(root.itertext()).lower()


@pytest.mark.parametrize("proof", ["pin-name", "pin-line", "fallback-marks"])
def test_native_art_replacement_has_independent_content_proofs(proof):
    rendered = _render(native_art=[_art()])
    root = ET.fromstring(rendered)
    if proof == "pin-name":
        assert "NATIVE_IN" in "".join(root.itertext()), "native pin name must be drawn"
    elif proof == "pin-line":
        assert any(node.get("d") == "M -10 0 h 5" for node in root.iter()), (
            "native pin segment must retain its captured endpoints"
        )
    else:
        assert 'r="2.2"' not in rendered and 'r="1.6"' not in rendered, (
            "native art must replace the diagnostic pin and origin circles"
        )


def test_planned_value_and_flags_remain_on_the_existing_diagnostic_chain():
    plan, book = _case()
    plan.texts.append(LayoutText(kind="value", text="PLAN_VALUE", part_id="U1",
                                 bbox=(25, 22, 55, 31)))
    plan.power_symbols.append(LayoutPowerSymbol(symbol_ref="PWR-GND", net="GND", x=90, y=40))
    book["PWR-GND"] = SymbolProfile(symbol_ref="PWR-GND", body=(-5, 4, 5, 10), pins=[])
    default = ET.fromstring(_render(plan, book))
    native = ET.fromstring(_render(plan, book, native_art=[_art()]))
    for text in ("PLAN_U1", "PLAN_VALUE", "GND"):
        assert text in "".join(native.itertext())
    flag_ink = lambda root: [ET.tostring(node, encoding="unicode") for node in root.iter()
                             if node.get("fill") == "#b45309" or node.get("stroke") == "#b45309"]
    assert flag_ink(native) == flag_ink(default)
    wires = lambda root: [ET.tostring(node, encoding="unicode") for node in root.iter()
                          if _local(node.tag) == "polyline" and node.get("stroke") == "#0b6b3a"]
    assert wires(native) == wires(default)


@pytest.mark.parametrize("rotation,mirror", [(0.0, False), (90.0, True)])
def test_actual_art_endpoint_is_mapped_by_origin_y_flip_and_scale_only(rotation, mirror):
    plan, book = _case()
    plan.parts[0].rotation, plan.parts[0].mirror = rotation, mirror
    root = ET.fromstring(_render(plan, book, native_art=[_art(rotation=rotation, mirror=mirror)]))
    pin = _probe(root, "pin")[0]
    # Art is already in its captured pose in SVG x-right/y-down coordinates.
    # Canvas origin (30,40) maps to (40,160), then local(-10,0)*2 maps to (20,160).
    assert _world(root, pin, (-10.0, 0.0)) == pytest.approx((20.0, 160.0))
    assert _world(root, pin, (-5.0, 0.0)) == pytest.approx((30.0, 160.0))
    plate = _probe(root, "plate")[0]
    assert _world(root, plate, (0.0, -4.0)) == pytest.approx((40.0, 152.0))
    assert _world(root, plate, (0.0, 4.0)) == pytest.approx((40.0, 168.0))
    assert "NATIVE_IN" in "".join(root.itertext())


def test_repeated_symbol_instances_keep_unique_ids_and_distinct_endpoints():
    plan, book = _case(duplicate=True)
    first = _render(plan, book, native_art=[_art()])
    assert first == _render(plan, book, native_art=[_art()]), "prefixes must be deterministic"
    root = ET.fromstring(first)
    identifiers = [node.get("id") for node in root.iter() if node.get("id")]
    assert len(identifiers) == len(set(identifiers))
    assert len(_probe(root, "pin")) == 2
    assert sorted(_world(root, pin, (-10.0, 0.0)) for pin in _probe(root, "pin")) == [
        (20.0, 160.0), (120.0, 100.0),
    ]
    assert "".join(root.itertext()).count("NATIVE_IN") == 2
    scopes = [node for node in root.iter() if node.get("data-native-source") == SOURCE]
    assert len(scopes) == 2
    for scope in scopes:
        assert scope.get("id"), "each captured-art scope needs an addressable id"
        styles = list(scope.iter(f"{{{SVG}}}style"))
        assert len(styles) == 1, "the captured stylesheet must not be dropped"
        for style in styles:
            assert not (style.text or "").lstrip().startswith("*")
            assert f"#{scope.get('id')}" in (style.text or ""), "captured CSS must stay in its part scope"
            assert "stroke-linejoin:round" in (style.text or "")


def test_material_selection_uses_exact_symbol_and_pose_and_preserves_the_source():
    wrong = _art(rotation=180.0, svg=ART.replace("NATIVE_IN", "WRONG_POSE"), source="wrong pose")
    root = ET.fromstring(_render(native_art=[wrong, _art()]))
    assert "WRONG_POSE" not in "".join(root.itertext())
    assert any(node.get("data-native-source") == SOURCE for node in root.iter())


def test_missing_material_keeps_the_diagnostic_part_fallback():
    rendered = _render(native_art=[_art(symbol_ref="OTHER")])
    assert 'r="2.2"' in rendered and 'r="1.6"' in rendered
    assert "NATIVE_IN" not in rendered


def test_present_material_with_wrong_pose_refuses_by_part_and_symbol():
    with pytest.raises(ValueError) as caught:
        _render(native_art=[_art(rotation=270.0)])
    assert "U1" in str(caught.value) and "SYN" in str(caught.value)
    assert "pose" in str(caught.value).lower()


def test_material_requires_a_nonempty_source():
    with pytest.raises(ValueError, match="(?i)source"):
        _render(native_art=[_art(source="")])


def test_art_does_not_import_a_previous_manual_designator_or_value():
    polluted = ART.replace("</svg>", '<text c_partid="part_attr">OLD_MANUAL_REFERENCE</text></svg>')
    with pytest.raises(ValueError) as caught:
        _render(native_art=[_art(svg=polluted)])
    assert any(word in str(caught.value).lower() for word in ("attr", "pin", "manual"))
    clean = ET.fromstring(_render(native_art=[_art()]))
    assert "NATIVE_IN" in "".join(clean.itertext()), "calibrated pin text stays visible"


@pytest.mark.parametrize("payload", [
    '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><image href="https://example.test/a.png"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><g onclick="alert(1)"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><style>*{fill:url(https://example.test/a)}</style></svg>',
    '<!DOCTYPE svg [<!ENTITY x "expansion">]><svg xmlns="http://www.w3.org/2000/svg"><text>&x;</text></svg>',
])
def test_art_refuses_active_or_external_svg_content(payload):
    with pytest.raises(ValueError):
        _render(native_art=[_art(svg=payload)])


def test_duplicate_ids_inside_one_art_asset_are_refused():
    duplicate = ART.replace('id="plate"', 'id="lead"')
    with pytest.raises(ValueError, match="(?i)id"):
        _render(native_art=[_art(svg=duplicate)])
