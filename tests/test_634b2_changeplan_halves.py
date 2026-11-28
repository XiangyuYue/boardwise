"""634 缝 B 第二批：`changeplan` 解析里「两半互不相见」的九条（634B-05…-13）+ 635 的四条。

这一批的洞不是「没有判据」，而是**判据各自只看见一半**：

* **634B-05** `target.dx/dy` 与 `change.moves` 的实际位移互不比对——docstring 写着
  「the two must agree」，而 `_move_change_from` 从来拿不到 target。
* **634B-06** `moves[*]` / `islands[*].pin` 可以指向 `target.designators` 之外；`mates`
  用 `str()` 把 `5` 洗成 `'5'`。
* **634B-07** `connection.pin` 与 `target.pin` 无交叉检查（同一处 `net` 与 `afterNet` 有）。
* **634B-08** `insert` 的 `toPin` 可以指回本连接自己的脚（零长线）。
* **634B-09** `keepNames` 用 `bool()` 读：字符串 `"false"` 反而成 True。
* **634B-10 / 635B-02** flag 的 `symbolRef`/`symbolHash` 完全不校验（part 的同类字段是三重拒）。
* **634B-11** insert part 的 `rotation` 用 `int()`：`90.7` 截成 90、`"90"` 当 90。
* **634B-12** 九处 `str()` 把 dict/int 洗成合法字符串。
* **634B-13** 坐标多于两项被静默丢弃，`load → dump` 写出比读入短的点。
* **635B-04** 同网同点两个 flag 读完照写，写后才由回读腿判红。
* **635B-05** `baseline.components` 重复项被接受，而 census 的语义是集合。

**两处刻意没有照 REPRO 的 FIX 做**，各有实测依据，见对应用例的 docstring：

* `islands[*].mates` **不**限制在移动组内——`moveblock.plan_islands` 取的是整张活网表上
  同网的每一个脚，收紧会拒掉每一个有邻居的真 move 计划（B43「mates 悬空」因此撤洞：
  `moveblock.verify_islands` 已用改后的活网表逐条比对）。
* flag 的 `symbolHash` 空值**仍然接受**——`drawapply.py:1516-1543` 的构建侧自己允许
  「有 ref 没 hash」，读侧比写侧严就会拒掉本工具刚写出的计划。
"""

from __future__ import annotations

import pytest

from boardwise.core import changeplan as cp

SHA = "a" * 64
FLAG_SHA = "b" * 64


def _page(target: dict, change: dict) -> dict:
    return {
        "planVersion": 1,
        "source": {"inputSha256": SHA, "projectUuid": "proj-1", "pageUuid": "page-1"},
        "target": target,
        "change": change,
        "preconditions": [],
        "expectedPostcondition": [],
    }


# ------------------------------------------------------------------ move 两半


def _move_change(**overrides) -> dict:
    change = {
        "kind": cp.MOVE_BLOCK_KIND,
        "moves": [
            {
                "designator": "U1",
                "primitiveId": "p-U1",
                "from": {"x": 300.0, "y": 300.0, "rotation": 0},
                "to": {"x": 305.0, "y": 300.0},
            },
        ],
        "wireOps": [],
        "islands": [{"pin": "U1.5", "mates": ["U2.1"]}],
        "baselineFindings": [],
    }
    change.update(overrides)
    return change


def _move_payload(**overrides) -> dict:
    target = {
        "primitiveId": "",
        "designator": "U1, U2",
        "expectedValue": "",
        "designators": ["U1", "U2"],
        "dx": 5.0,
        "dy": 0.0,
    }
    return _page(target, _move_change(**overrides))


def test_b05_a_delta_that_disagrees_with_the_moves_is_refused():
    """`target.dx=100` 而 moves 只走 5——docstring 说两半必须一致，代码看不见对方。"""
    payload = _move_payload()
    payload["target"]["dx"] = 100.0
    with pytest.raises(cp.ChangePlanError) as exc:
        cp.ChangePlan.from_jsonable(payload)
    message = str(exc.value)
    assert "target.dx/target.dy" in message, message
    assert "(100, 0)" in message, message


def test_b05_the_delta_the_writer_states_still_loads():
    """对照组：`cli.py` 用同一个 dx/dy 算 to_at，所以真计划是恒等式，不许被挡。"""
    plan = cp.ChangePlan.from_jsonable(_move_payload())
    assert plan.target.x == 5.0
    assert plan.change.moves[0].to_at == (305.0, 300.0)


def test_b05_a_vertical_delta_is_checked_on_its_own_axis():
    """把检查写成只看 x 的实现会在这一格通过——两轴各自比。"""
    payload = _move_payload()
    payload["target"]["dy"] = 5.0
    with pytest.raises(cp.ChangePlanError) as exc:
        cp.ChangePlan.from_jsonable(payload)
    assert "target.dx/target.dy" in str(exc.value), str(exc.value)


# ------------------------------------------------------------------ 634B-06


def test_b06_a_move_of_a_part_the_target_does_not_name_is_refused():
    change = _move_change()
    change["moves"][0]["designator"] = "R7"
    with pytest.raises(cp.ChangePlanError) as exc:
        cp.ChangePlan.from_jsonable(_page(_move_payload()["target"], change))
    message = str(exc.value)
    assert "target.designators" in message, message
    assert "R7" in message, message


def test_b06_an_island_pin_outside_the_group_is_refused():
    with pytest.raises(cp.ChangePlanError) as exc:
        cp.ChangePlan.from_jsonable(
            _move_payload(islands=[{"pin": "R7.1", "mates": ["U1.5"]}])
        )
    message = str(exc.value)
    assert "change.islands[0].pin" in message, message


def test_b06_an_island_pin_must_be_spelled_designator_pin():
    """`"R11"` 没有点：旧检查只说「必须含点」，现在与 draw 侧同一把尺子。"""
    with pytest.raises(cp.ChangePlanError) as exc:
        cp.ChangePlan.from_jsonable(
            _move_payload(islands=[{"pin": "U15", "mates": []}])
        )
    assert "change.islands[0].pin" in str(exc.value), str(exc.value)


def test_b06_a_mate_that_is_not_a_string_is_refused():
    """`str(5)` 曾把它变成 mate `'5'`——一个永远对不上活网表的位号。"""
    with pytest.raises(cp.ChangePlanError) as exc:
        cp.ChangePlan.from_jsonable(
            _move_payload(islands=[{"pin": "U1.5", "mates": [5]}])
        )
    assert "change.islands[0].mates[0]" in str(exc.value), str(exc.value)


def test_b06_a_mate_of_a_part_outside_the_group_is_still_accepted():
    """对照组，也是 B43 撤洞的依据：mates 是「当时同网的脚」，日常就在组外。

    `moveblock.plan_islands:546` 从**整张活网表**取同网的每一个脚，所以收紧要
    「必须是移动组内的脚」会把每一个有邻居的真计划拒掉。悬空位号由
    `moveblock.verify_islands:613-620` 在改后的活网表上逐条比对时暴露。
    """
    plan = cp.ChangePlan.from_jsonable(
        _move_payload(islands=[{"pin": "U1.5", "mates": ["ZZ.9", "R7.1"]}])
    )
    assert plan.change.islands[0].mates == ["ZZ.9", "R7.1"]


# ---------------------------------------------------------------- patch-pin


PATCH_ATTACHMENT = {
    "kind": "wire",
    "primitiveId": "w1",
    "detail": "the wire on the pin",
    "at": [345.0, 290.0],
}


def _patch_payload(*, pin="4", connection_pin="4", after_net="VCC", attachment=None) -> dict:
    connections = []
    if after_net:
        connections.append(
            {"pin": connection_pin, "net": "VCC", "kind": "wire", "detail": "",
             "to": [345.0, 300.0]}
        )
    change = {
        "kind": cp.PATCH_PIN_KIND,
        "beforeNet": "GND",
        "afterNet": after_net,
        "connections": connections,
        "attachment": PATCH_ATTACHMENT if attachment is None else attachment,
    }
    target = {"designator": "U3", "pin": pin, "primitiveId": "", "expectedValue": ""}
    return _page(target, change)


def test_b07_a_connection_on_another_pin_is_refused():
    """计划说修 U3 的脚 4、连接却写脚 5：apply 跟连接走、复审跟 target 走。"""
    with pytest.raises(cp.ChangePlanError) as exc:
        cp.ChangePlan.from_jsonable(_patch_payload(connection_pin="5"))
    message = str(exc.value)
    assert "target.pin" in message, message
    assert "'4'" in message and "'5'" in message, message


def test_b07_a_connection_with_no_pin_is_refused():
    with pytest.raises(cp.ChangePlanError) as exc:
        cp.ChangePlan.from_jsonable(_patch_payload(connection_pin=""))
    assert "target.pin" in str(exc.value), str(exc.value)


def test_b07_the_pin_the_target_names_still_loads():
    plan = cp.ChangePlan.from_jsonable(_patch_payload())
    assert plan.target.pin == "4"
    assert plan.change.connections[0].pin == "4"


def test_b07_a_numeric_pin_number_is_read_faithfully():
    """`outputs/035_plan_disconnect.json` 写的是 `"pin": 4`（整数），不是缺陷。"""
    payload = _patch_payload(after_net="")
    payload["target"]["pin"] = 4
    payload["change"]["attachment"] = PATCH_ATTACHMENT
    plan = cp.ChangePlan.from_jsonable(payload)
    assert plan.target.pin == "4"


def test_b07_pin_zero_is_a_pin_not_an_empty_string():
    """`str(pin or "")` 把 0 读成空串再拒——顺带修掉的边界。"""
    payload = _patch_payload(pin=0, connection_pin="0", after_net="VCC")
    plan = cp.ChangePlan.from_jsonable(payload)
    assert plan.target.pin == "0"


# --------------------------------------------------------------- insert 自引用


def _insert_payload(*, rotation=0, to_pin="R1.1") -> dict:
    change = {
        "kind": cp.INSERT_SUBCIRCUIT_KIND,
        "template": "rc-lowpass",
        "parts": [
            {"designator": "R1", "role": "series-r", "lcsc": "C1x", "value": "1k",
             "footprint": "", "x": 385.0, "y": 320.0, "rotation": rotation},
            {"designator": "C1", "role": "shunt-c", "lcsc": "C2x", "value": "1n",
             "footprint": "", "x": 385.0, "y": 340.0, "rotation": 0},
        ],
        "connections": [
            {"designator": "R1", "pin": "1", "net": "X", "kind": "wire",
             "detail": "", "to": [345.0, 310.0]},
            {"designator": "R1", "pin": "2", "net": "N1", "kind": "wire",
             "detail": "", "toPin": to_pin},
            {"designator": "C1", "pin": "1", "net": "X", "kind": "wire",
             "detail": "", "to": [345.0, 310.0]},
            {"designator": "C1", "pin": "2", "net": "GND", "kind": "power-flag",
             "detail": ""},
        ],
        "beforeNet": "N1",
        "attachment": PATCH_ATTACHMENT,
        "baselineFindings": [],
    }
    target = {"primitiveId": "", "designator": "U3", "expectedValue": "",
              "anchor": "U3", "anchorNet": "", "pin": "5", "x": 345.0, "y": 310.0}
    return _page(target, change)


def test_b08_a_connection_that_ends_on_its_own_pin_is_refused():
    """R1.2 的连接把远端写成 R1.2：一个「远端」等于近端不是另一个远端。"""
    with pytest.raises(cp.ChangePlanError) as exc:
        cp.ChangePlan.from_jsonable(_insert_payload(to_pin="R1.2"))
    message = str(exc.value)
    assert "toPin" in message, message
    assert "R1.2" in message, message


def test_b08_a_far_end_on_another_planned_pin_still_loads():
    plan = cp.ChangePlan.from_jsonable(_insert_payload(to_pin="C1.1"))
    assert plan.change.connections[1].to_pin == "C1.1"


def test_b11_a_fractional_rotation_is_refused():
    """`int(90.7)` 曾把它截成 90：计划写的姿态与执行的姿态不同。"""
    with pytest.raises(cp.ChangePlanError) as exc:
        cp.ChangePlan.from_jsonable(_insert_payload(rotation=90.7))
    assert "expected one of 0, 90, 180, 270" in str(exc.value), str(exc.value)


def test_b11_a_rotation_spelled_as_a_string_is_refused():
    with pytest.raises(cp.ChangePlanError) as exc:
        cp.ChangePlan.from_jsonable(_insert_payload(rotation="90"))
    assert "must be a number in degrees" in str(exc.value), str(exc.value)


def test_b11_the_pose_the_template_asks_for_still_loads():
    """对照组：divider 的第二颗电阻就是 180°，合法姿态集里。"""
    plan = cp.ChangePlan.from_jsonable(_insert_payload(rotation=180))
    assert plan.change.parts[0].rotation == 180


# ------------------------------------------------------------------ draw 夹具


def _draw_change(**overrides) -> dict:
    change = {
        "kind": cp.DRAW_MODULE_KIND,
        "candidate": 0,
        "layoutSha256": SHA,
        "circuitSha256": SHA,
        "presentationSha256": SHA,
        "profiles": [
            {"symbolRef": "R0402", "geometryHash": SHA},
            {"symbolRef": "PWR-GND", "geometryHash": FLAG_SHA},
        ],
        "parts": [
            {
                "specId": "R1", "designator": "R1", "prefix": "R", "lcsc": "C25744",
                "value": "1k", "footprint": "R0402", "symbolRef": "R0402",
                "symbolHash": SHA, "x": 100.0, "y": 100.0, "rotation": 0,
                "mirror": False,
                "pins": [
                    {"number": "1", "dx": 0.0, "dy": 50.0},
                    {"number": "2", "dx": 0.0, "dy": -50.0},
                ],
            },
        ],
        "wires": [
            {"net": "V3", "points": [[100.0, 50.0], [100.0, 0.0]], "fromPin": "R1.1"},
        ],
        "flags": [],
        "islands": [],
    }
    change.update(overrides)
    target = {"primitiveId": "", "designator": "", "expectedValue": "",
              "module": "divider", "pageUuid": ""}
    return _page(target, change)


def _flag(**overrides) -> dict:
    flag = {
        "net": "GND",
        "kind": cp.DRAW_FLAG_GROUND,
        "symbolRef": "PWR-GND",
        "symbolHash": FLAG_SHA,
        "x": 85.0,
        "y": 720.0,
        "rotation": 0,
        "onPin": "",
    }
    flag.update(overrides)
    return flag


def _draw_payload(**overrides) -> dict:
    return _draw_change(**overrides)


# ------------------------------------------------------------ 634B-09 keepNames


def test_b09_a_string_is_not_a_boolean():
    """`bool("false")` 是 True：说「别保留位号」的计划会保留。"""
    change = _draw_change()
    change["change"]["keepNames"] = "false"
    with pytest.raises(cp.ChangePlanError) as exc:
        cp.ChangePlan.from_jsonable(change)
    message = str(exc.value)
    assert "change.keepNames must be a boolean" in message, message
    assert "'false'" in message, message


@pytest.mark.parametrize("value,expected", [(True, True), (False, False)])
def test_b09_a_real_boolean_is_read_as_written(value, expected):
    change = _draw_change()
    change["change"]["keepNames"] = value
    assert cp.ChangePlan.from_jsonable(change).change.draw_keep_names is expected


# --------------------------------------------------- 634B-10 / 635B-02 旗标符号


def test_b10_a_flag_symbol_the_profiles_does_not_describe_is_refused():
    payload = _draw_payload(flags=[_flag(symbolRef="NOSYM", symbolHash="")])
    with pytest.raises(cp.ChangePlanError) as exc:
        cp.ChangePlan.from_jsonable(payload)
    message = str(exc.value)
    assert "change.flags[0].symbolRef" in message, message
    assert "NOSYM" in message, message


@pytest.mark.parametrize("digest", ["deadbeef", "0" * 64, 5])
def test_b10_a_flag_hash_that_is_not_the_profiles_hash_is_refused(digest):
    payload = _draw_payload(flags=[_flag(symbolHash=digest)])
    with pytest.raises(cp.ChangePlanError) as exc:
        cp.ChangePlan.from_jsonable(payload)
    assert "change.flags[0].symbolHash" in str(exc.value), str(exc.value)


def test_b10_a_hash_without_the_symbol_it_hashes_is_refused():
    payload = _draw_payload(flags=[_flag(symbolRef="", symbolHash=FLAG_SHA)])
    with pytest.raises(cp.ChangePlanError) as exc:
        cp.ChangePlan.from_jsonable(payload)
    message = str(exc.value)
    assert "symbolRef is empty" in message, message


def test_b10_a_flag_with_no_symbol_at_all_is_still_accepted():
    """对照组：`place_power` 的兜底路径——没有库符号，也就没有可校验的几何。"""
    plan = cp.ChangePlan.from_jsonable(
        _draw_payload(flags=[_flag(symbolRef="", symbolHash="")])
    )
    assert plan.change.draw_flags[0].symbol_ref == ""


def test_b10_a_flag_whose_layout_has_no_hash_is_still_accepted():
    """对照组，也是不许照 REPRO 收紧的依据：`drawapply.py:1516-1543` 的构建侧
    只在 layout 给了 hash 时才查表，读侧比写侧严就会拒掉本工具自己写的计划。"""
    plan = cp.ChangePlan.from_jsonable(
        _draw_payload(flags=[_flag(symbolHash="")])
    )
    assert plan.change.draw_flags[0].symbol_ref == "PWR-GND"
    assert plan.change.draw_flags[0].symbol_hash == ""


def test_b10_the_flag_the_builder_writes_still_loads():
    plan = cp.ChangePlan.from_jsonable(_draw_payload(flags=[_flag()]))
    assert plan.change.draw_flags[0].symbol_hash == FLAG_SHA


# ------------------------------------------------------- 635B-03 onPin 与坐标


def test_635b03_a_stated_pin_must_be_where_the_flag_is_placed():
    """`onPin` 曾只进 purpose 文本：说「这面旗挂 R1.1」而落在别处，没人比。

    R1 在 (100, 100)，脚 1 的 posed 偏移是 (0, +50)，所以脚尖端在 (100, 150)。
    """
    with pytest.raises(cp.ChangePlanError) as exc:
        cp.ChangePlan.from_jsonable(_draw_payload(flags=[_flag(onPin="R1.1")]))
    message = str(exc.value)
    assert "change.flags[0].onPin" in message, message
    assert "(100, 150)" in message, message


def test_635b03_a_stated_pin_at_its_own_tip_still_loads():
    plan = cp.ChangePlan.from_jsonable(
        _draw_payload(flags=[_flag(onPin="R1.1", x=100.0, y=150.0)])
    )
    assert plan.change.draw_flags[0].on_pin == "R1.1"


def test_635b03_an_unstated_pin_is_the_ordinary_rail_flag():
    """对照组：真计划（`evidence/534a/plan.json`）每一个旗的 `onPin` 都是空串，
    旗落在母线上而不是某个脚上——这条路径不许被这次收紧挡掉。"""
    plan = cp.ChangePlan.from_jsonable(_draw_payload(flags=[_flag(x=485.0, y=120.0)]))
    assert plan.change.draw_flags[0].on_pin == ""


# ------------------------------------------------------------ 635B-04 重复旗标


def test_635b04_two_flags_on_one_point_under_one_net_are_refused():
    """落图按「点 + 网」认旗，两行在那里是一个旗；旧行为是写两次再判红。"""
    payload = _draw_payload(flags=[_flag(), _flag(rotation=180)])
    with pytest.raises(cp.ChangePlanError) as exc:
        cp.ChangePlan.from_jsonable(payload)
    message = str(exc.value)
    assert "change.flags[1]" in message, message
    assert "same point" in message, message


def test_635b04_two_flags_on_one_point_under_different_nets_are_distinguishable():
    """对照组：不同网的同点旗，回读能分开（`mine` 只按网过滤）。"""
    plan = cp.ChangePlan.from_jsonable(
        _draw_payload(
            flags=[_flag(net="GND"), _flag(net="VCC", kind=cp.DRAW_FLAG_POWER,
                                         symbolRef="", symbolHash="")]
        )
    )
    assert [flag.net for flag in plan.change.draw_flags] == ["GND", "VCC"]


def test_635b04_two_flags_of_one_net_far_apart_still_load():
    plan = cp.ChangePlan.from_jsonable(
        _draw_payload(flags=[_flag(), _flag(x=485.0)])
    )
    assert len(plan.change.draw_flags) == 2


# --------------------------------------------------------- 635B-05 baseline 重复


def _baseline(**overrides) -> dict:
    baseline = {
        "pageUuid": "page-1",
        "components": ["R1", "C1"],
        "wireCount": 1,
        "netflagCount": 0,
        "netlabelCount": 0,
        "unnumberedCount": 0,
        "pinCount": 2,
        "digest": SHA,
        "findingsRead": False,
    }
    baseline.update(overrides)
    return baseline


def test_635b05_a_repeated_baseline_component_is_refused():
    with pytest.raises(cp.ChangePlanError) as exc:
        cp.ChangePlan.from_jsonable(_draw_payload(baseline=_baseline(components=["R1", "R1"])))
    message = str(exc.value)
    assert "change.baseline.components" in message, message
    assert "R1" in message, message


def test_635b05_the_census_the_writer_records_still_loads():
    plan = cp.ChangePlan.from_jsonable(_draw_payload(baseline=_baseline()))
    assert plan.change.draw_baseline.components == ["R1", "C1"]


# --------------------------------------------------------------- 634B-12 str()


def test_b12_the_helper_reads_none_as_empty_and_text_as_is():
    assert cp._plan_text(None, "x") == ""
    assert cp._plan_text("C21190", "x") == "C21190"


def test_b12_a_whole_number_is_only_faithful_where_the_field_is_numeric():
    assert cp._plan_text(4, "x", numbers=True) == "4"
    with pytest.raises(cp.ChangePlanError):
        cp._plan_text(4, "x")


@pytest.mark.parametrize("value", [{"a": 1}, ["a"], 1.5, True])
def test_b12_a_value_that_is_not_text_is_never_invented(value):
    with pytest.raises(cp.ChangePlanError) as exc:
        cp._plan_text(value, "some.field")
    assert "some.field must be a string" in str(exc.value), str(exc.value)


@pytest.mark.parametrize(
    "slot",
    ["source.projectUuid", "target.primitiveId", "change.part.lcsc",
     "change.connections[0].net", "change.moves[0].primitiveId",
     "change.parts[0].specId", "change.wires[0].net"],
)
def test_b12_each_of_the_nine_slots_refuses_a_dict(slot):
    """九处 `str()` 各有一格：dict 曾变成一个谁也搜不到的「位号/网络/订单号」。"""
    payload = {
        "source.projectUuid": lambda p: p["source"].__setitem__("projectUuid", {"a": 1}),
        "target.primitiveId": lambda p: (p["target"].__setitem__("primitiveId", {"a": 1})),
        "change.part.lcsc": lambda p: p["change"]["part"].__setitem__("lcsc", {"a": 1}),
        "change.connections[0].net": lambda p: p["change"]["connections"][0].__setitem__(
            "net", {"a": 1}
        ),
        "change.moves[0].primitiveId": lambda p: p["change"]["moves"][0].__setitem__(
            "primitiveId", {"a": 1}
        ),
        "change.parts[0].specId": lambda p: p["change"]["parts"][0].__setitem__(
            "specId", {"a": 1}
        ),
        "change.wires[0].net": lambda p: p["change"]["wires"][0].__setitem__(
            "net", {"a": 1}
        ),
    }
    factory = {
        "source.projectUuid": _component_value_payload,
        "target.primitiveId": _component_value_payload,
        "change.part.lcsc": _add_payload,
        "change.connections[0].net": _add_payload,
        "change.moves[0].primitiveId": _move_payload,
        "change.parts[0].specId": _draw_payload,
        "change.wires[0].net": _draw_payload,
    }[slot]
    payload_obj = factory()
    payload[slot](payload_obj)
    with pytest.raises(cp.ChangePlanError) as exc:
        cp.ChangePlan.from_jsonable(payload_obj)
    assert slot in str(exc.value), str(exc.value)


def _component_value_payload() -> dict:
    target = {"designator": "R1", "primitiveId": "p1", "expectedValue": "10k"}
    return _page(target, {"kind": cp.COMPONENT_VALUE_KIND, "before": "10k", "after": "22k"})


def _add_payload() -> dict:
    target = {
        "primitiveId": "", "designator": "C7", "expectedValue": "0.1uF",
        "anchor": "U1", "assignedDesignator": "C7", "x": 0.0, "y": -5.0,
        "connection": "wire", "connectionDetail": "test",
    }
    change = {
        "kind": cp.ADD_COMPONENT_KIND,
        "part": {"lcsc": "C1525", "value": "0.1uF", "footprint": ""},
        "connections": [
            {"pin": "1", "net": "VCC", "kind": "wire", "detail": "", "to": [5.0, 0.0]},
            {"pin": "2", "net": "GND", "kind": "label", "detail": ""},
        ],
        "recipeSource": "operator:C1525",
    }
    return _page(target, change)


# --------------------------------------------------------------- 634B-13 坐标


@pytest.mark.parametrize("value", [[0.0, 0.0, 7.0], (0.0, 0.0, 7.0)])
def test_b13_a_point_with_a_third_component_is_not_a_point(value):
    assert cp._insert_independent_point(value) is None


def test_b13_a_wire_point_with_a_third_component_is_refused_not_shortened():
    payload = _draw_payload(
        wires=[{"net": "V3", "points": [[100.0, 50.0, 7.0], [100.0, 0.0]],
                "fromPin": "R1.1"}]
    )
    with pytest.raises(cp.ChangePlanError) as exc:
        cp.ChangePlan.from_jsonable(payload)
    assert "change.wires[0].points[0]" in str(exc.value), str(exc.value)


def test_b13_an_ordinary_pair_is_still_a_point():
    assert cp._insert_independent_point([1, 2]) == (1.0, 2.0)
