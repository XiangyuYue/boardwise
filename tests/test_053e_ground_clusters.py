"""053e：地网的**就近分簇**——小簇各自挂旗标，不拉跨簇母线。

535 的规则只有一条，但它在图上的后果分三种，这个文件逐条钉住：

1. **直径上限**（`:func:`boardwise.engines.drawcompiler._gnd_clusters``）：一簇
   里任意两脚 ≤ ``GND_LOCAL_RADIUS``，且按 member 顺序贪心并入（能并就并）；短
   跳串成的链**不算**一簇——链两端那一步正是要消掉的那段母线；
2. **单簇不变**：一簇时 ``_Expression.clusters`` 留空，走的是原来那条路 ——
   同样的输入跑两次逐字节一致，且图上没有 535 的痕迹（一枚旗标、无簇注记）；
3. **多簇**：每簇一枚旗标、簇内短 stub，**簇与簇之间没有 GND 段**；三簇里
   某一簇挂不上旗标时拒绝，且文案点名 ``cluster i/n near (x, y)``。

几何用 053B 的手写 spec 夹具（`test_053b_drawcompiler`），所以这里只断言
"画法的结构"，不钉坐标：坐标是编译器的产物。
"""

from __future__ import annotations

from dataclasses import replace

import test_053b_drawcompiler as b053

from boardwise.engines import drawcompiler as dc


def declared_budget(scene, radius: float = dc.GND_LOCAL_RADIUS):
    """053f: clustering is a **document statement** now — state it (radius 100)."""
    return replace(scene.budget, gnd_cluster_radius=radius)


def gnd_segments(plan):
    return [segment for segment in plan.segments if segment.net == "GND"]


def gnd_symbols(plan):
    return [symbol for symbol in plan.power_symbols if symbol.net == "GND"]


def clusters_in(result, scene):
    """Every ``_gnd_clusters`` answer the compile asked for, in call order.

    053f: the compile carries ``gndClustering.radius`` into the budget, so the
    spy sees the radius the scene declared (100 here, the split's own constant).
    """
    calls: list[tuple] = []
    real = dc._gnd_clusters

    def spy(points, radius=dc.GND_LOCAL_RADIUS):
        answer = real(points, radius)
        calls.append((tuple(points), answer))
        return answer

    dc._gnd_clusters = spy
    try:
        result = dc.compile(scene.circuit, scene.presentation,
                            b053.library(), declared_budget(scene))
    finally:
        dc._gnd_clusters = real
    return result, calls


# ---------------------------------------------------------------- 半径与簇


def test_radius_is_a_named_constant_sized_for_one_flag():
    """100 是常量、写清了用途，并且按"一簇里任意两脚都够得着"来分。"""
    assert dc.GND_LOCAL_RADIUS == 100.0
    # 三脚成团：两两 ≤ 100（最长 84.9）→ 一簇。直径，不是单链接。
    club = (
        ("A.1", (0.0, 0.0)), ("B.1", (60.0, 0.0)), ("C.1", (0.0, 60.0)),
    )
    assert len(dc._gnd_clusters(club)) == 1
    # 一跳 60 的链 A–B–D：A 与 D 相距 120，**不是**一簇（那一步就是母线本身）。
    chain = (("A.1", (0.0, 0.0)), ("B.1", (60.0, 0.0)), ("C.1", (120.0, 0.0)))
    assert len(dc._gnd_clusters(chain)) == 2
    # 贪心按 member 顺序：B 先并入 A，D 无处可并 → 自己一簇。
    assert [tuple(member for member, _point in cluster)
            for cluster in dc._gnd_clusters(chain)] == [("A.1", "B.1"), ("C.1",)]
    # 直接 150 的两个脚：各自一簇。
    far = (("A.1", (0.0, 0.0)), ("B.1", (150.0, 0.0)))
    assert len(dc._gnd_clusters(far)) == 2
    # 单脚与空输入：一簇（空输入是空），不制造空簇。
    one = (("A.1", (0.0, 0.0)),)
    assert dc._gnd_clusters(one) == (one,)
    assert dc._gnd_clusters(()) == ()


def test_one_cluster_leaves_the_expression_unsplit_and_the_drawing_as_it_was():
    """单簇：``clusters`` 为空，输出与改前一致（两跑同 bytes + 固定字段）。"""
    scene = b053.scenes()[1]  # divider：GND 只有一个焊盘
    first = b053.compile_scene(scene)
    second = b053.compile_scene(scene)
    assert first.ok and second.ok
    left, right = first.candidates[0], second.candidates[0]
    assert left.geometry_sha256() == right.geometry_sha256()
    assert len(gnd_symbols(left)) == 1
    assert not [note for note in left.notes if "535" in note], (
        "a one-cluster ground must not be described as split"
    )


# ---------------------------------------------------------------- 多簇


def test_two_clusters_get_one_flag_each_and_no_wire_between_them():
    """两簇：每簇一枚旗标，簇内短 stub，且没有任何 GND 段跨过两簇之间。"""
    scene = b053.scenes()[8]  # LDO：C1.2 / U1.1 / C2.2 互距 ≥120
    # 053f：分簇是**文档的语句**，所以这个场景显式声明半径（不再靠默认开）。
    result = dc.compile(
        scene.circuit, scene.presentation, b053.library(), declared_budget(scene),
    )
    assert result.ok, [failure.detail for failure in result.failures]
    plan = result.candidates[0]
    pads = [
        (member, b053.pin_point(plan, member))
        for member in ("C1.2", "U1.1", "C2.2")
    ]
    assert all(point is not None for _member, point in pads)
    groups = dc._gnd_clusters(pads)
    assert len(groups) == len(pads) == 3, (
        "this scene's GND pads are 120+ apart, so each is its own neighbourhood"
    )
    symbols = gnd_symbols(plan)
    assert len(symbols) == len(groups), (
        f"one symbol per cluster: {len(symbols)} symbol(s) for {len(groups)} clusters"
    )
    # 每枚旗标都挨着自己那一簇的焊盘（一支旗标够得着），不是全岛一枚。
    for group in groups:
        assert any(
            min(abs(symbol.x - x) + abs(symbol.y - y)
                for _member, (x, y) in group) <= 2.0 * dc.FLAG_LEAD
            for symbol in symbols
        ), f"cluster {group} has no nearby symbol of its own"
    # 簇与簇之间没有导体：每段 GND 都是簇内的短 run（没有全岛母线）。
    for segment in gnd_segments(plan):
        span = max(
            abs(segment.points[0][0] - segment.points[-1][0]),
            abs(segment.points[0][1] - segment.points[-1][1]),
        )
        assert span <= dc.GND_LOCAL_RADIUS, (
            f"segment {segment.points} spans {span} units — a cross-cluster bus"
        )
    assert [note for note in plan.notes if "535" in note], (
        f"a split ground says so on the plan: {plan.notes}"
    )


def test_a_cluster_with_no_legal_flag_seat_refuses_and_names_that_cluster():
    """簇内挂不上旗标：仍是 layout-unsat，文案点名 ``cluster i/n near (x, y)``。

    这条拒绝由 :func:`_rail_flag_room_failure` 组装（rail flag 的座位阶梯唯一
    的出口），这里直接问它：分簇地面必须带簇名，单簇地面一个 "cluster" 字都不
    能多出来（后者是逐字节不变的承诺）。
    """
    phrase = dc._gnd_cluster_phrase("3/3", (300.0, 645.0))
    split = dc._rail_flag_room_failure(
        "GND", "USB1.2", (300.0, 645.0), "the obstacle this test stands in for",
        cluster=phrase,
    )
    assert split.category == dc.FAILURE_LAYOUT_UNSAT
    assert "net 'GND' cluster 3/3 near (300, 645)" in split.detail
    assert "that cluster" in split.detail
    plain = dc._rail_flag_room_failure(
        "GND", "USB1.2", (300.0, 645.0), "the obstacle this test stands in for",
    )
    assert "cluster" not in plain.detail
    assert "net 'GND' is a rail drawn as a wire" in plain.detail


def test_a_cluster_expression_carries_only_its_own_pads():
    """席位/路由拿到的是**簇**，所以它们只能在这一簇里找位置。"""
    expression = dc._Expression(
        net="GND", style="wire",
        points=(("C1.2", (0.0, 0.0)), ("C2.2", (400.0, 0.0))),
        reason="a split ground",
        clusters=(
            (("C1.2", (0.0, 0.0)),),
            (("C2.2", (400.0, 0.0)),),
        ),
    )
    parts = dc._gnd_cluster_expressions(expression)
    assert [label for _expression, label in parts] == ["1/2", "2/2"]
    assert [item.points for item, _label in parts] == [
        (("C1.2", (0.0, 0.0)),), (("C2.2", (400.0, 0.0)),)
    ]
    assert all(item.clusters == () for item, _label in parts)
    # 不分簇的表达式原样交回：调用方走的是改前那条路。
    plain = dc._Expression(
        net="GND", style="wire", points=(("C1.2", (0.0, 0.0)),), reason="one",
    )
    assert dc._gnd_cluster_expressions(plain) == ()
