"""548D3D-L §25B：straight 标签被器件文字占位时，交给既有 extra_text_walls。

实测的病（旧布局）：`ESP_EN` 的最终盒 `(-103,-49.5,-56,-40.5)` 压在 `R1` 的文字带
`(-92,-46.5,-68,-37.5)` 上，`_reseat_crossed_labels` 先失败，548C4 的文字修复根本轮不到。
本文件钉三件事：

1. 只有「显式 `labelPolicy.stub == "straight"` 且标签盒与**具体的**文字盒相交」时，才把那些
   盒交给既有的 `extra_text_walls`，在**同一个** placement 上再构建一次（至多一次）；
2. 非 straight（`auto`）一次都不走这条杠杆，调用序列与旧路径一致；
3. `_label_row_conflicts` 这个测量本身只报真正相交的盒。

**2026-11-17（0.6.2）夹具与数值更新**：`C1` 的默认座位 `(30,20)` 在 069 sec.1 的固定
地旗闸上是死结（`C1.2` 的 GND 旗四个朝向都放不下 glyph + 名字行），整页在旗阶段就被拒，
标签阶段根本测不到。改用 `fixture._documents(c1_flag_room=True)`（C1 钉到 `(30,60)`）后
页面过闸、并且**仍然真实需要一次文字重选址**（`builds == [初始, reseat#1]`）。岛内重排
使旧坐标失效，下面每个常量都是这份输入上的**实测值**，与机制的对应关系写在各自注释里；
旧值（`R1_ROW`、`245/215`）是旧布局的数字，不是机制本身。
"""

from __future__ import annotations

import math

from boardwise.engines import drawcompiler as dc
from boardwise.engines import placement as pl

import test_548d_series_reservation as fixture

#: `_label_row_conflicts` 的纯测量用例仍用旧的那一对盒（它不编译页面，只测“相交才报”
#: 这条规则，与布局无关）。
ESP_BOX_MEASURED = (-103.0, -49.5, -56.0, -40.5)
R1_ROW_MEASURED = (-92.0, -46.5, -68.0, -37.5)

#: 新布局上 `ESP_EN` 的最终盒（三次 `_label_for` 读数一致）。
ESP_BOX = (126.5, 19.0, 173.5, 28.0)
#: 初始构建测到的四个文字冲突盒，就是修复构建交给 `extra_text_walls` 的那四个
#: （顺序即 `_label_row_conflicts` 的输出顺序）。旧值只有 `R1` 一行，因为旧布局只
#: 踩到它；新布局踩到四行，**机制相同**：相交的行进墙，且只进一次修复构建。
TEXT_WALLS = (
    (228.0, 27.5, 243.0, 36.5),
    (228.0, 13.5, 252.0, 22.5),
    (94.0, 27.5, 117.0, 36.5),
    (69.0, 13.5, 117.0, 22.5),
)
#: 修复构建之后页面仍被拒，且拒因换成“标签盒压在导体上”（旧布局是 `$.seriesBranches`
#: 的 LED1_K 绕行 245 > 215）。两者是同一类收尾：`layout-unsat` + 拒交而不是带病交付。
TAIL_SUBJECT = "labels[3]"
TAIL_CONDUCTOR = "[194.5, 19, 225.5, 28]"


def _forced_topology(monkeypatch):
    """把 topology 轮逼成唯一一轮，并带回这一轮的 `(ctx, variant, placed)`。"""
    captured: dict[str, object] = {}
    real = dc._build_candidate

    def record(ctx, variant, label_fallbacks=None):
        captured["ctx"], captured["variant"] = ctx, variant
        return real(ctx, variant, label_fallbacks)

    monkeypatch.setattr(dc, "_build_candidate", record)
    monkeypatch.setattr(dc, "_variants", lambda *_args: [])
    monkeypatch.setattr(dc, "_widened_variants", lambda *_args: [])
    circuit, presentation = fixture._documents(c1_flag_room=True)
    ground = frozenset(
        dc._ground_domain(net.id) for net in circuit.nets if net.cls == "gnd"
    )
    dc.compile(
        circuit, presentation, fixture._book(), fixture._budget(),
        page_ground_domains=ground,
    )
    ctx = captured["ctx"]
    placed, failure = dc._place(ctx, captured["variant"])
    assert failure is None and placed is not None
    return ctx, captured["variant"], placed


def _measured_seat(ctx, placed):
    """binder 自己的 led1 lane + led2 移到 -150（本批实测的那个座位）。"""
    templates, failure = dc._series_templates(
        ctx, placed.residue, tuple(sorted(placed.origins)),
    )
    assert failure is None and templates
    request = dc._series_placement_request(ctx, templates, placed.poses)
    arms = [plan for plan in placed.series_plans if plan.seated]
    assert len(arms) == 2

    def seat(plan, lane):
        span = math.hypot(plan.lateral[0], plan.lateral[1]) or 1.0
        lateral = (plan.lateral[0] / span, plan.lateral[1] / span)
        shift = lane - plan.lane
        return pl.replace(
            plan,
            first_origin=(plan.first_origin[0] + lateral[0] * shift,
                          plan.first_origin[1] + lateral[1] * shift),
            second_origin=(plan.second_origin[0] + lateral[0] * shift,
                           plan.second_origin[1] + lateral[1] * shift),
            lane=lane,
        )

    plans = [seat(arms[0], arms[0].lane), seat(arms[1], -150.0)]
    plans = list(
        pl.separate_series_lanes(request, plans, placed.origins, placed.poses)
    )
    seated, state = pl.place_series_seats(
        request, plans, placed.origins, placed.poses,
    )
    return dc._Placement(
        origins=dict(state.origins), poses=dict(state.poses),
        residue=placed.residue, series_plans=seated,
    )


def _run(monkeypatch, ctx, variant, override):
    """构建一次，记录 `_build_one_variant` 的入参与每轮的 part texts。"""
    builds: list[dict] = []
    texts: list[list] = []
    real_build = dc._build_one_variant
    real_texts = dc._part_texts

    def build(context, var, fallbacks, **kwargs):
        builds.append(kwargs)
        return real_build(context, var, fallbacks, **kwargs)

    def part_texts(context, placed, occupied, walls):
        out, refusal = real_texts(context, placed, occupied, walls)
        texts.append(list(out))
        return out, refusal

    monkeypatch.setattr(dc, "_build_one_variant", build)
    monkeypatch.setattr(dc, "_part_texts", part_texts)
    try:
        built, failure, _violations = dc._build_one_variant(
            ctx, variant, [], placement_override=override,
        )
    finally:
        monkeypatch.setattr(dc, "_build_one_variant", real_build)
        monkeypatch.setattr(dc, "_part_texts", real_texts)
    return built, failure, builds, texts


def test_label_row_conflicts_names_only_the_row_it_lands_on():
    """测量本身：相交的盒才进墙，不相交的一律不进。"""
    label = dc.LayoutLabel(
        net="ESP_EN", text="ESP_EN", bbox=ESP_BOX_MEASURED, x=-115.0, y=-45.0,
    )
    row = dc.LayoutText(
        kind="value", text="10k", bbox=R1_ROW_MEASURED, part_id="R1", x=-80.0, y=-42.0,
    )
    far = dc.LayoutText(
        kind="value", text="100nF", bbox=(200.0, 200.0, 260.0, 209.0),
        part_id="C9", x=230.0, y=204.0,
    )
    assert dc._label_row_conflicts([label], [row, far]) == [R1_ROW_MEASURED]
    assert dc._label_row_conflicts([label], [far]) == []


def test_straight_stub_reseats_the_conflicting_row_once(monkeypatch):
    """straight：相交的文字行交给 extra_text_walls，同一 placement 只多构建一次。"""
    ctx, variant, placed = _forced_topology(monkeypatch)
    override = _measured_seat(ctx, placed)
    built, failure, builds, texts = _run(monkeypatch, ctx, variant, override)

    assert built is None, "the measured seat now builds; this claim is stale"
    assert len(builds) == 2, [b.get("label_text_reseat") for b in builds]
    first, second = builds
    assert first.get("label_text_reseat", 0) == 0
    assert second["label_text_reseat"] == 1
    # 机制：初始构建测到的冲突行就是修复构建的墙，一个不多一个不少。
    assert tuple(second["extra_text_walls"]) == TEXT_WALLS
    assert second["placement_override"] is override, (
        "the text re-seat must stay on the same placement"
    )
    # 墙是**文字**盒，不是标签自己的盒：机制要的是“把踩到的文字交给文字修复”。
    assert not any(dc._overlaps(ESP_BOX, wall) for wall in second["extra_text_walls"])
    rows = texts[-1]
    assert rows, "the second build produced no part rows"
    assert len(rows) == 28, "the repair build must still emit every part row"
    # 修复构建确实重排了文字：至少一行落在墙的旧位置上，且尺寸是可比较的实数盒。
    assert any(
        dc._overlaps(wall, text.bbox) for wall in second["extra_text_walls"] for text in rows
    ), "the repair build never re-placed text near the walls it was given"
    # 收尾：页面仍被拒，且是“标签盒压在导体上”这一类拒绝（拒交而不是带病交付）。
    # 旧布局这里是 `$.seriesBranches` 的 LED1_K 绕行 245 > 215——同一类 layout-unsat
    # 收尾，换成了新布局的真实拒因。
    assert failure.category == dc.FAILURE_LAYOUT_UNSAT, failure.category
    assert failure.subject == TAIL_SUBJECT, failure.subject
    assert "conductor through its box" in failure.detail
    assert TAIL_CONDUCTOR in failure.detail
    assert "refused rather than delivered" in failure.detail


def test_auto_stub_never_takes_the_lever(monkeypatch):
    """auto（缺省）：一次构建都不多，调用序列与旧路径一致。"""
    ctx, variant, placed = _forced_topology(monkeypatch)
    override = _measured_seat(ctx, placed)
    monkeypatch.setattr(dc, "_label_stub_policy", lambda _ctx: "auto")
    _built, failure, builds, _texts = _run(monkeypatch, ctx, variant, override)

    assert len(builds) == 1, [b.get("label_text_reseat") for b in builds]
    assert all(b.get("label_text_reseat", 0) == 0 for b in builds)
    assert failure.subject.startswith("labels[")


def _crosses_box(path, box):
    for start, end in zip(path, path[1:]):
        if start[1] == end[1]:
            low, high = sorted((start[0], end[0]))
            if box[1] < start[1] < box[3] and low < box[2] and high > box[0]:
                return True
        else:
            low, high = sorted((start[1], end[1]))
            if box[0] < start[0] < box[2] and low < box[3] and high > box[1]:
                return True
    return False


def test_replay_is_off_by_default_and_on_in_the_one_repair_build(monkeypatch):
    """§25F：初始构建不给 seat 映射（无回放），只有那次冲突修复构建回放同一对象。

    同时在修复构建里钉住：ESP_EN 的盒在**布线前**已在 `router.boxes`，且没有任何
    route 穿过它——回放的作用域就是这一次构建。
    """
    ctx, variant, placed = _forced_topology(monkeypatch)
    override = _measured_seat(ctx, placed)

    reserves: list[bool] = []          # 每次预留是否拿到了 seat 映射
    builds: list[int] = [0]            # 第几次构建（1 = 初始，2 = 冲突修复）
    esp_boxes: list[tuple] = []
    walls: list[tuple[bool, int, list | None, list]] = []

    real_build_inner = dc._build_one_variant

    def build_inner(context, var, fallbacks, **kwargs):
        builds[0] += 1
        return real_build_inner(context, var, fallbacks, **kwargs)

    real_stubs = dc._reserve_label_stubs

    def stubs(context, place, net_id, expression, router, occupied, tips, taken,
              service_walls=None, *, seats=None, **kwargs):
        reserves.append(seats is not None)
        return real_stubs(
            context, place, net_id, expression, router, occupied, tips, taken,
            service_walls, seats=seats, **kwargs,
        )

    real_label_for = dc._label_for

    def label_for(context, net_id, part_id, token, point, *args, **kwargs):
        label = real_label_for(context, net_id, part_id, token, point, *args, **kwargs)
        if net_id == "ESP_EN":
            esp_boxes.append(label.bbox)
        return label

    real_route = dc._Router.route

    def route(self, start, goal, **kwargs):
        path = real_route(self, start, goal, **kwargs)
        box = esp_boxes[-1] if esp_boxes else None
        walls.append((box in self.boxes if box else False,
                      self.boxes.count(box) if box else 0,
                      path, builds[0]))
        return path

    monkeypatch.setattr(dc, "_build_one_variant", build_inner)
    monkeypatch.setattr(dc, "_reserve_label_stubs", stubs)
    monkeypatch.setattr(dc, "_label_for", label_for)
    monkeypatch.setattr(dc._Router, "route", route)
    built, failure, _violations = dc._build_one_variant(
        ctx, variant, [], placement_override=override,
    )
    monkeypatch.setattr(dc, "_build_one_variant", real_build_inner)
    monkeypatch.setattr(dc, "_reserve_label_stubs", real_stubs)
    monkeypatch.setattr(dc, "_label_for", real_label_for)
    monkeypatch.setattr(dc._Router, "route", real_route)

    assert built is None
    # 两次构建：初始那次没有映射，修复那次有（且只多一次）。
    assert reserves.count(False) >= 1, reserves
    assert reserves.count(True) >= 1, reserves
    # 修复构建里盒进了墙、只出现一次，且没有 route 穿它。
    reserved = esp_boxes[-1]
    repair = [entry for entry in walls if entry[3] == builds[0] and entry[3] > 1]
    assert repair, "the repair build routed nothing"
    assert any(present for present, _count, _p, _b in repair), (
        "the replayed straight box never entered router.boxes"
    )
    assert max(count for _present, count, _p, _b in repair) == 1
    # 修复构建里没有任何 route 穿过 ESP_EN 的盒（初始构建允许——那正是要修的病）。
    crossed = [p for _x, _c, p, _b in repair if p and _crosses_box(p, reserved)]
    assert not crossed, crossed[:1]
    # 后续真实失败：新布局上页面以 `labels[3]` 的“标签盒压在 3V3 导体上”收尾
    # （旧布局是 LED1_K 绕行 245 > 215；同为 layout-unsat、同为拒交而不带病交付）。
    assert failure.category == dc.FAILURE_LAYOUT_UNSAT, failure.category
    assert failure.subject == TAIL_SUBJECT, failure.subject
    assert "conductor through its box" in failure.detail
    assert TAIL_CONDUCTOR in failure.detail
