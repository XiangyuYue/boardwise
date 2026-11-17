"""548P144：固定 terminal glyph 必须进入 port-columns 的标签场景。

C1.2 在标签形成后才被画成固定旗，旧 scene 没有它的 glyph，LED1_K 因而先占
了它的房间，最终固定旗才被拒。修复不是移动旗或标签，而是让标签重选时先
看见所有已声明的固定 terminal glyph。U1.18 是下一独立首拒，不是整图通过。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from boardwise.core.presentationspec import PresentationSpec
from boardwise.engines import drawcompiler as dc
from test_548p126_service_host_feedback import SPEC
from test_548p142_joint_channel_candidates import _context, _placed

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def ctx():
    return _context(PresentationSpec.load(ROOT / SPEC))


def _detail(failure):
    return failure.detail if failure is not None else ""


def test_fixed_glyph_scene_moves_the_first_refusal_from_c12_to_u18(ctx):
    placed = _placed(ctx)
    built, failure, _notes = dc._build_one_variant(
        ctx, dc._variants(ctx)[0], [], placement_override=placed)
    detail = _detail(failure)
    assert built is None, "U1.18 is still an independent refusal"
    assert "U1.18" in detail, detail
    assert "C1.2" not in detail, detail
    assert "C3.2" not in detail, detail


def test_fixed_flag_boxes_include_the_c12_terminal_glyph(ctx):
    placed = _placed(ctx)
    boxes, failure = dc._seat_first_fixed_flag_boxes(ctx, placed)
    assert failure is None, failure
    seats, terminal_failure = dc._seat_first_terminal_seats(ctx, placed)
    assert terminal_failure is None, terminal_failure
    anchor, lead, hang, _source = seats[("GND", "C1.2")]
    net = ctx.circuit.net("GND")
    profile, _ref = dc._flag_plan(ctx, "GND", net.cls)
    rotation = dc._flag_rotation((0.0, hang), dc.flag_glyph_kind(profile))
    rotation = dc._flag_rotation_away(profile, anchor, lead, rotation)
    expected = dc._flag_box(profile, rotation, anchor, "GND")
    assert expected in boxes


def test_removing_fixed_glyphs_brings_back_c12(ctx, monkeypatch):
    monkeypatch.setattr(
        dc, "_seat_first_fixed_flag_boxes", lambda *_args: ((), None))
    placed = _placed(ctx)
    _built, failure, _notes = dc._build_one_variant(
        ctx, dc._variants(ctx)[0], [], placement_override=placed)
    detail = _detail(failure)
    assert "C1.2" in detail, detail
    assert "fixed terminal is not moved" in detail, detail
