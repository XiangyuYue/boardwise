"""P48: native ground bboxes must be adapted before a draw library consumes them."""

from __future__ import annotations

import json

import pytest

from boardwise.core.symbolprofile import flag_glyph_box
from boardwise.engines.drawapply import DrawPlanError, load_library


def _library(tmp_path, symbol_ref, body, *, pins=()):
    path = tmp_path / "library.json"
    path.write_text(json.dumps({"profiles": [{
        "kind": "boardwise-symbol-profile", "profileVersion": 1,
        "symbolRef": symbol_ref, "body": body, "pins": list(pins),
    }]}), encoding="utf-8")
    return path


@pytest.mark.parametrize("symbol_ref", ["PWR-GND", "Ground-GND"])
def test_native_ground_bbox_is_refused_before_a_second_family_turn(tmp_path, symbol_ref):
    # P40's native Ground0 glyph, relative to its connection point. Giving this
    # to flag_glyph_box applies the family's 180-degree turn a second time.
    path = _library(tmp_path, symbol_ref, [-10.5, -19.5, 10.5, -9.5])
    before = path.read_bytes()
    with pytest.raises(DrawPlanError, match="canonical.*reflect.*y") as error:
        load_library(path)
    assert symbol_ref in str(error.value)
    assert path.read_bytes() == before, "the reader must preserve the raw measurement"


def test_adapted_ground_matches_both_independent_native_poses(tmp_path):
    path = _library(tmp_path, "PWR-GND", [-10.5, 9.5, 10.5, 19.5])
    before = path.read_bytes()
    profile = load_library(path)["PWR-GND"]
    # Absolute boxes computed directly from the native negative-y body: pose 0
    # translates it; pose 180 negates both axes before translating it.
    native_boxes = {
        0: (89.5, 180.5, 110.5, 190.5),
        180: (89.5, 209.5, 110.5, 219.5),
    }
    for angle, expected in native_boxes.items():
        assert flag_glyph_box(profile, rotation=angle, anchor=(100, 200)) == pytest.approx(expected)
    assert profile.body == (-10.5, 9.5, 10.5, 19.5)
    assert path.read_bytes() == before


def test_rail_profiles_are_not_subject_to_the_ground_contract(tmp_path):
    # A negative-y rail remains valid input; this guard must not silently
    # normalise either family or turn a ground-specific refusal into a rail one.
    path = _library(tmp_path, "Power-VCC", [-5.5, -10.5, 5.5, -4.5])
    assert load_library(path)["Power-VCC"].body == (-5.5, -10.5, 5.5, -4.5)
    path = _library(tmp_path, "Power-VCC", [-5.5, 4.5, 5.5, 10.5])
    profile = load_library(path)["Power-VCC"]
    assert flag_glyph_box(profile, rotation=0, anchor=(100, 200)) == pytest.approx(
        (94.5, 204.5, 105.5, 210.5))


def test_ground_named_component_with_a_pin_is_not_a_flag(tmp_path):
    path = _library(tmp_path, "Ground-GND", [-10.5, -19.5, 10.5, -9.5], pins=[
        {"number": "1", "name": "GND", "tip": [0, 0], "direction": "down"},
    ])
    profile = load_library(path)["Ground-GND"]
    assert len(profile.pins) == 1
    assert profile.body == (-10.5, -19.5, 10.5, -9.5)
