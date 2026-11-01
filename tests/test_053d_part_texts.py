"""053d：`partTexts` —— 声明某个器件的位号/型号两行文字落在哪一侧。

两段，各钉一件事：

1. **schema**。`partTexts` 是顶层闭集键：值只能是 `above | below | left | right`
   之一，键只能是文档自己的模块声明过的器件。没声明时**不写出该键**——和
   `moduleOrder` / `userLocks` 同一套规矩，旧文档一个字节不变，进而 spec 摘要
   （以及由它 pin 住的每个 plan）也不动。未知器件、非法侧、未知键、非对象四种
   错法都要点名出错的器件 id 与键名，因为这一类错在建库的人眼里就是"我写的那
   个器件没生效"，报错不点名等于没报。
2. **编译器**。同一条 circuit + presentation，加一行 `partTexts: {"R1": "above"}`
   之后 R1 的 reference/value **两行一起**换到上方，且不压这颗器件自己的引脚道
   （另一侧让给网络标签，正是参考页「位号在上、型号在下」的读法）。两行不拆开
   是 `_line_boxes` 的既有承诺，这里从产物上再钉一次。

用例全部手写 spec/符号（053 的惯例：不建夹具文件、不喂参考图坐标），只走离线
`drawcompiler.compile`，不碰 connector / cli。
"""

from __future__ import annotations

import json

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import (
    PART_TEXT_SIDES,
    PresentationSpec,
    PresentationSpecError,
)
from boardwise.core.symbolprofile import SymbolPin, SymbolProfile, SymbolPose
from boardwise.engines import drawcompiler as dc

PROV = "verified_recipe"

#: A box the divider fits in with room on every side, so a stated side has a
#: free rung to take and the test measures the *choice*, not a squeeze.
PAGE = (0.0, 0.0, 800.0, 600.0)


# --------------------------------------------------------------- 器件库/电路


def _resistor(ref: str = "R0402") -> SymbolProfile:
    """A vertical two-pin resistor; ``length`` is stated so its leads exist.

    With a lead length the profile also produces real pin walls
    (:func:`drawcompiler._pin_walls`), which is what lets the compile case say
    "the rows left the pin lane" about a box that is actually drawn.
    """
    return SymbolProfile(
        symbol_ref=ref, title="Resistor", body=(-10.0, -20.0, 10.0, 20.0),
        pins=[
            SymbolPin(number="1", name="1", tip=(0.0, 50.0), direction="up",
                      length=20.0),
            SymbolPin(number="2", name="2", tip=(0.0, -50.0), direction="down",
                      length=20.0),
        ],
    )


def _flag(ref: str) -> SymbolProfile:
    return SymbolProfile(
        symbol_ref=ref, title=ref, body=(-6.0, 0.0, 6.0, 18.0), pins=[],
    )


def _book() -> dict[str, SymbolProfile]:
    book = {"R0402": _resistor()}
    for name in ("PWR-GND", "PWR-VIN", "PWR-OUT", "PWR-VIN5", "PWR-3V3"):
        book[name] = _flag(name)
    return book


def _divider_circuit() -> CircuitSpec:
    return CircuitSpec.from_dict({
        "parts": [
            {"id": "R1", "symbolRef": "R0402", "value": "10k", "provenance": PROV},
            {"id": "R2", "symbolRef": "R0402", "value": "10k", "provenance": PROV},
        ],
        "nets": [
            {"id": "VIN", "class": "power", "members": ["R1.1"], "provenance": PROV},
            {"id": "TAP", "class": "signal", "members": ["R1.2", "R2.1"],
             "provenance": PROV},
            {"id": "GND", "class": "gnd", "members": ["R2.2"], "provenance": PROV},
        ],
    })


def _divider_presentation(**overrides) -> PresentationSpec:
    payload = {
        "grammarRef": "voltage-divider",
        "modules": [{"id": "divider", "parts": ["R1", "R2"], "role": "divider"}],
        "portRoles": {"VIN": "input", "TAP": "output"},
        "directWiringObligations": [
            {"nets": ["VIN", "TAP", "GND"], "note": "the whole ladder is wired"}
        ],
    }
    payload.update(overrides)
    return PresentationSpec.from_dict(payload)


def _compile(presentation: PresentationSpec):
    result = dc.compile(
        _divider_circuit(), presentation, _book(),
        dc.CompileBudget(page_box=PAGE),
    )
    assert result.ok, result.failures
    assert result.candidates, "the divider has to keep producing a candidate"
    return result.candidates[0]


def _part_rows(plan, part_id: str) -> dict[str, tuple[float, float, float, float]]:
    return {text.kind: tuple(text.bbox) for text in plan.texts
            if text.part_id == part_id}


def _part_box(plan, part_id: str):
    item = [p for p in plan.parts if p.part_id == part_id][0]
    profile = _book()[item.symbol_ref]
    pose = SymbolPose(rotation=item.rotation, mirror=item.mirror)
    return dc._part_box(profile, pose, (item.x, item.y)), profile, pose, (
        item.x, item.y)


# ------------------------------------------------------------------- schema


def test_a_stated_side_round_trips_and_the_bytes_are_stable(tmp_path):
    payload = {
        "modules": [{"id": "m-core", "parts": ["U1"], "role": "ic"}],
        "partTexts": {"U1": "above"},
    }
    spec = PresentationSpec.from_dict(payload)
    assert spec.part_texts == {"U1": "above"}

    first = json.dumps(spec.to_jsonable(), ensure_ascii=False, indent=2) + "\n"
    assert json.loads(first)["partTexts"] == {"U1": "above"}
    # parse -> serialize -> parse -> serialize: the bytes do not drift.
    again = PresentationSpec.from_dict(json.loads(first))
    assert again == spec
    second = json.dumps(again.to_jsonable(), ensure_ascii=False, indent=2) + "\n"
    assert second == first

    # And through the file API the document is byte-stable both ways.
    path = tmp_path / "part_texts.presentation.json"
    spec.dump(path)
    assert PresentationSpec.load(path).to_jsonable() == spec.to_jsonable()
    assert path.read_text(encoding="utf-8") == first


def test_a_spec_that_states_no_side_does_not_write_the_key():
    spec = PresentationSpec.from_dict({
        "modules": [{"id": "m-core", "parts": ["U1"], "role": "ic"}],
    })
    assert spec.part_texts == {}
    written = spec.to_jsonable()
    assert "partTexts" not in written
    assert "partTexts" not in json.dumps(written, ensure_ascii=False)
    # The empty mapping is "nothing stated" the same way `moduleOrder` is: it is
    # not written, so a document parsed from an older file keeps its bytes.
    assert "partTexts" not in PresentationSpec.from_dict(written).to_jsonable()


def test_an_undeclared_part_id_is_refused_by_name():
    with pytest.raises(PresentationSpecError) as refused:
        PresentationSpec.from_dict({
            "modules": [{"id": "m-core", "parts": ["U1"], "role": "ic"}],
            "partTexts": {"U9": "above"},
        })
    message = str(refused.value)
    assert "U9" in message and "partTexts" in message


def test_an_unknown_side_is_refused_by_name():
    with pytest.raises(PresentationSpecError) as refused:
        PresentationSpec.from_dict({
            "modules": [{"id": "m-core", "parts": ["U1"], "role": "ic"}],
            "partTexts": {"U1": "top"},
        })
    message = str(refused.value)
    assert "U1" in message and "partTexts" in message
    assert "above" in message and "below" in message and "left" in message


def test_an_unknown_key_is_refused_by_name():
    with pytest.raises(PresentationSpecError) as refused:
        PresentationSpec.from_dict({
            "modules": [{"id": "m-core", "parts": ["U1"], "role": "ic"}],
            "partTextz": {"U1": "above"},
        })
    assert "partTextz" in str(refused.value)


def test_a_non_object_is_refused_by_name():
    with pytest.raises(PresentationSpecError) as refused:
        PresentationSpec.from_dict({
            "modules": [{"id": "m-core", "parts": ["U1"], "role": "ic"}],
            "partTexts": ["U1", "above"],
        })
    assert "partTexts" in str(refused.value)


def test_the_closed_vocabulary_is_the_one_the_compiler_places():
    assert PART_TEXT_SIDES == ("above", "below", "left", "right")


# ------------------------------------------------------------------ compile


def test_a_stated_side_moves_both_rows_and_keeps_off_the_pin_lane():
    default = _compile(_divider_presentation())
    stated = _compile(_divider_presentation(partTexts={"R1": "above"}))

    default_rows = _part_rows(default, "R1")
    stated_rows = _part_rows(stated, "R1")
    assert set(default_rows) == {"reference", "value"}
    assert set(stated_rows) == {"reference", "value"}

    box, profile, pose, origin = _part_box(default, "R1")
    stated_box, *_ = _part_box(stated, "R1")

    # The ladder's own first choice is the right side; the stated side is above.
    for kind, item in default_rows.items():
        assert item[0] >= box[2], f"{kind} should start right of the part: {item}"
    for kind, item in stated_rows.items():
        assert item[1] >= stated_box[3], (
            f"{kind} should sit above the part: {item} vs {stated_box}"
        )

    # Both rows move together — a reference here and a value there would read as
    # two unrelated texts, which is the one thing `_line_boxes` promises not to
    # do and the reason this key names a side rather than a place per line.
    assert stated_rows["reference"][1] >= stated_box[3]
    assert stated_rows["value"][1] >= stated_box[3]

    # ...and they do not sit on the pin lanes they just vacated.
    lanes = dc._pin_walls(profile, pose, origin)
    assert lanes, "the fixture's leads have to be drawn for this check to bite"
    for kind, item in stated_rows.items():
        for lane in lanes:
            assert not dc._overlaps(item, lane), (
                f"{kind} {item} overlaps the pin lane {lane}"
            )

    # The two documents differ in the rows' place, not in whether the part has
    # text at all: the stated side is a placement, not a suppression.
    assert stated_rows != default_rows
