"""548D3X §30C：页面 consumer 的黑盒验收（compact 排布 + 端口—框—布局同源）。

这个文件只从**公开产物**判卷：一份 `PresentationSpec` 声明了
`pageArrangement={"strategy":"compact"}` 之后，`compile_page` 交出的
`PageLayoutPlan` 与 `PageCompileResult` 必须满足 §30C 的合同。它不读、不指定任何
参考器件、岛坐标或目标位置：器件/网络/模块/场景全部来自 `test_056_pagecompiler`
（同一批手写 JSON 夹具与同一个符号库），座标只出现在断言「在框内 / 相距 ≥ 40 /
落在页内」里，绝不断言「应该在某个点」。

七条验收，逐条对应任务书 §30C 的编号：

1. 未声明 `pageArrangement` 时旧 variant 标签、页 digest 与拒绝序列逐项不变
   （旧输出是基线，先钉死；任何「顺手改旧路径」的集成都会在这里变红）；
2. 声明 compact 后真实产生至少一页合法页：`check` + `check_page` 干净、
   origin/frame 由生产从真实编译候选平移而来、无重复标签、每个模块的几何都在
   它自己声明的 frame 内；
3. 带 `mainPath` 的真实场景在 compact 下由 `_wire_shared_nets` 真实产生跨岛导线，
   不是静默降级成 label；另有一条窄判据直接问 `_net_style`：假想 grid 里非相邻的
   两个模块，在 packed 页上不得按旧 columns 邻接被判成 label（不冒充真实走线覆盖）；
4. packer `unsat` 时旧 grid 回退，且回退出的页逐项等于旧 grid 页并合法；
5. packer 返回 overlap / 出界 / truncated 时必须拒绝且理由可区分，不得放行
   （出界一例曾由生产用 `_pull_inside` 平移回页内后交付；已在生产修复并回归，
   见 `evidence/548D/page-layout/blackbox-tests.md`）；
6. 端口确实是从**干净的**模块候选（`internalGeometrySha256` 可对回候选）重建，
   最终 frame 与端口/内容一致，重复编译逐字节相同；
7. 三模块真实夹具：同一份真实 frames 下旧 grid 排不下、compact 参差回填排得下，
   小测试页由生产 frame 现测得出，不放大到 1170×825。

负例用真实 `PackingResult` 的拒绝形状（`unsat`/`truncated`/坏的 packed）注入，
不伪造一个「合法」的排布去绕开最终 checker；注入点就是生产自己的
`pagepacking.pack_frames`，测试同时验证这个调用确实发生。
"""

from __future__ import annotations

import re

import pytest

import test_056_pagecompiler as p056

from boardwise.core.layoutplan import LayoutPlan
from boardwise.core.presentationspec import PageArrangement, PresentationSpec
from boardwise.engines import pagecompiler as pc
from boardwise.engines import pagepacking, readability
from boardwise.engines.pagecompiler import PageCompileBudget
from boardwise.engines.pagepacking import (
    FAILURE_BUDGET_EXHAUSTED,
    FAILURE_UNSAT,
    FramePlacement,
    PackingFailure,
    PackingResult,
)

#: §30C: the page's own gap, not a smaller one invented by the packer.
GAP = pc.MODULE_GAP
#: The delivery sheet is a future condition (30D); no test here may grow a page to it.
DELIVERY_PAGE = (0.0, 0.0, 1170.0, 825.0)
PAGE = p056.PAGE
EPS = 1e-6

#: §30C's "compact 变体" label. The page's own note states the variant it came from.
COMPACT_TAG = "arrangement=compact"


# --------------------------------------------------------------- 声明与页面


def compact_spec(presentation: PresentationSpec) -> PresentationSpec:
    """The same document, plus the one declaration §30C defines — nothing else.

    Written through the document's own JSON (rather than `dataclasses.replace`) so
    the test exercises the same parser a user's file goes through, and asserts the
    declaration is the *only* difference between the two specs.
    """
    document = dict(presentation.to_jsonable())
    assert "pageArrangement" not in document, "the fixture must not already state one"
    document["pageArrangement"] = {"strategy": "compact"}
    declared = PresentationSpec.from_dict(document)
    plain = PresentationSpec.from_dict(presentation.to_jsonable())
    without = dict(declared.to_jsonable())
    without.pop("pageArrangement", None)
    assert without == presentation.to_jsonable(), (
        "the compact declaration changed another key of the document"
    )
    assert plain.page_arrangement is None
    assert declared.page_arrangement == PageArrangement(strategy="compact")
    return declared


def arrangement(page) -> str:
    """Which arrangement a delivered page came from, from its own variant note."""
    label = page.notes[0] if page.notes else ""
    assert "variant" in label, f"a page states the variant it came from, got {label!r}"
    return "compact" if COMPACT_TAG in label else "grid"


def pages_of(result, *, compact: bool | None = None):
    """The delivered pages, optionally only those of one arrangement."""
    if compact is None:
        return list(result.pages)
    wanted = "compact" if compact else "grid"
    return [page for page in result.pages if arrangement(page) == wanted]


def compile_both(scene, presentation=None, budget=None):
    """Compile the scene with a stated (or the scene's own) presentation."""
    presentation = presentation or scene.presentation
    return pc.compile_page(
        scene.circuit, presentation, p056.library(), budget or scene.budget
    )


def compact_page(scene, budget=None, presentation=None):
    """The best compact page of a scene, refusing to pass when none exists.

    Every positive compact test goes through here first: a red here says the
    declaration produced no packed page, which is the whole subject of §30C, and
    it prevents a test from silently passing on the *grid* fallback instead.
    """
    presentation = presentation or compact_spec(scene.presentation)
    result = compile_both(scene, presentation, budget)
    assert result.ok, p056.render(result)
    pages = pages_of(result, compact=True)
    assert pages, (
        "pageArrangement='compact' produced no compact page; delivered variants: "
        + ", ".join(page.notes[0] for page in result.pages)
    )
    return result, pages[0], presentation


def recheck(page, scene, presentation, budget=None):
    """Both independent layers, re-run on the finished page (no compiler state)."""
    budget = budget or scene.budget
    drawing = readability.check(
        page.plan, scene.circuit, presentation, p056.library(),
        page_box=budget.page_box, keepouts=budget.keepouts, grid=budget.grid,
    )
    page_domain = readability.check_page(
        page, scene.circuit, presentation, p056.library(),
        keepouts=budget.keepouts, module_gap=budget.module_gap,
    )
    return drawing, page_domain


def assert_clean(page, scene, presentation, budget=None) -> None:
    drawing, page_domain = recheck(page, scene, presentation, budget)
    assert drawing.hard_violations == [], [
        item.render() for item in drawing.hard_violations
    ]
    assert page_domain.hard_violations == [], [
        item.render() for item in page_domain.hard_violations
    ]
    assert page.verdict == "pass"


def _inside(box, point) -> bool:
    return (
        box[0] - EPS <= point[0] <= box[2] + EPS
        and box[1] - EPS <= point[1] <= box[3] + EPS
    )


def _inside_box(inner, outer) -> bool:
    return (
        outer[0] - EPS <= inner[0] and inner[2] <= outer[2] + EPS
        and outer[1] - EPS <= inner[1] and inner[3] <= outer[3] + EPS
    )


def module_named(page, module_id):
    found = page.module(module_id)
    assert found is not None, module_id
    return found


def candidate_of(result, module):
    """The compiled candidate a page says its module drawing came from.

    `internalGeometrySha256` is the page's own statement of that binding, so the
    page must match one real candidate exactly — this is what rules out a module
    drawing edited in place during port replay.
    """
    compiled = result.modules[module.id]
    for candidate in compiled.candidates:
        assert isinstance(candidate, LayoutPlan)
        if candidate.geometry_sha256() == module.internal_geometry_sha256:
            return candidate
    assert False, (
        f"module {module.id!r} says its internal drawing is "
        f"{module.internal_geometry_sha256[:12]}…, which is none of the "
        f"{len(compiled.candidates)} candidate(s) the module compiler produced"
    )


def statement_points(page, net_id) -> set[tuple[float, float]]:
    """Every page-level anchor that states `net_id` (a label, a flag, a wire end)."""
    points: set[tuple[float, float]] = set()
    for label in page.plan.labels:
        if label.net == net_id:
            points.add((round(label.x, 6), round(label.y, 6)))
    for symbol in page.plan.power_symbols:
        if symbol.net == net_id:
            points.add((round(symbol.x, 6), round(symbol.y, 6)))
    for segment in page.plan.segments:
        if segment.net == net_id:
            for end in (segment.points[0], segment.points[-1]):
                points.add((round(end[0], 6), round(end[1], 6)))
    return points


# ------------------------------------------------ 1. 没声明 = 旧输出逐项不变

#: The old-page baseline this batch may not move. These are the delivered 056
#: fixture's own numbers, captured on the *pre-548* page compiler: the variant
#: label, the page digest and the eight rejected variants in their order.
OLD_BEST_VARIANT = (
    "boardwise-pagecompiler/1 variant generation=0 columns=3 gap=1x "
    "order=pwr/rc/div"
)
OLD_BEST_DIGEST = (
    "c179b6168108788bd936ed788bf6cfbf8a45de8350f46ad1f88b234a5d19c6cf"
)
OLD_REJECTED = [
    "generation=0 columns=1 gap=1x order=pwr/rc/div",
    "generation=0 columns=1 gap=1.6x order=pwr/rc/div",
    "generation=0 columns=2 gap=1x order=pwr/rc/div",
    "generation=0 columns=2 gap=1.6x order=pwr/rc/div",
    "generation=1 columns=1 gap=1x order=pwr/rc/div",
    "generation=1 columns=1 gap=1.6x order=pwr/rc/div",
    "generation=1 columns=2 gap=1x order=pwr/rc/div",
    "generation=1 columns=2 gap=1.6x order=pwr/rc/div",
]


def test_without_the_declaration_the_old_variant_labels_and_page_digest_are_unchanged():
    """§30C: 未写新键的 variant 序列逐项相同，旧 digest 不变."""
    scene = p056.scenes()[3]
    presentation = scene.presentation
    assert presentation.page_arrangement is None
    assert "pageArrangement" not in presentation.to_jsonable()

    result = compile_both(scene)
    assert result.ok, p056.render(result)
    assert len(result.pages) == 4
    best = result.pages[0]
    assert best.notes[0] == OLD_BEST_VARIANT
    assert best.page_geometry_sha256() == OLD_BEST_DIGEST
    assert [item.variant for item in result.rejected] == OLD_REJECTED
    assert all(item.variant.startswith("generation=") for item in result.rejected), (
        "a document that states no pageArrangement gained a new variant kind"
    )

    # The same document read back from its own JSON is the same document: the
    # digest is a statement about the page, not about how the bytes were handed in.
    again = compile_both(scene, PresentationSpec.from_dict(presentation.to_jsonable()))
    assert again.ok, p056.render(again)
    assert again.pages[0].page_geometry_sha256() == OLD_BEST_DIGEST
    assert [item.variant for item in again.rejected] == OLD_REJECTED


# ------------------------------------- 2. compact 真实产出且几何都在声明 frame 内


def test_compact_produces_a_legal_page_whose_geometry_sits_in_its_frames():
    """§30C: 至少一张合法 compact 页，origin/frame 是生产算的，几何都在框内."""
    scene = p056.scenes()[2]
    result, page, presentation = compact_page(scene)
    assert arrangement(page) == "compact"
    assert page.page_box == scene.budget.page_box
    assert_clean(page, scene, presentation)

    frames = {module.id: module.frame for module in page.modules}
    assert set(frames) == {item.id for item in scene.presentation.modules}
    assert len(pages_of(result, compact=True)) >= 1

    # 每个模块的 origin 是「干净候选 → 页坐标」的平移，frame 是同一个生产的框。
    for module in page.modules:
        assert module.frame[2] > module.frame[0] and module.frame[3] > module.frame[1]
        assert _inside_box(module.frame, scene.budget.page_box), (
            f"module {module.id!r} frame {module.frame} leaves the page"
        )
        candidate = candidate_of(result, module)
        for part_id in module.parts:
            local = candidate.part(part_id)
            placed = page.plan.part(part_id)
            assert local is not None and placed is not None, part_id
            assert placed.x == pytest.approx(local.x + module.origin[0], abs=1e-6)
            assert placed.y == pytest.approx(local.y + module.origin[1], abs=1e-6)
            assert (placed.rotation, placed.mirror) == (local.rotation, local.mirror), (
                f"part {part_id!r} was re-posed on the page"
            )
            profile = p056.library()[placed.symbol_ref]
            extent = pc._part_extent(profile, placed)
            assert _inside_box(extent, module.frame), (
                f"part {part_id!r} draws {extent} outside its module frame {module.frame}"
            )
        for port in module.ports:
            assert _inside(module.frame, (port.x, port.y)), (
                f"port {module.id}.{port.net} at {(port.x, port.y)} is outside "
                f"its own frame {module.frame}"
            )

    # 无重复标签：一个锚点不重复陈述同一个网。
    anchors = [(label.net, round(label.x, 6), round(label.y, 6)) for label in page.plan.labels]
    assert len(anchors) == len(set(anchors)), "the page states one net twice at one anchor"

    # 模块框之间保持页级净距（不是 40 以下；40 恰好是 checker 的门槛）。
    names = sorted(frames)
    for index, left in enumerate(names):
        for right in names[index + 1:]:
            gap = pagepacking.frame_gap(frames[left], frames[right])
            assert gap >= GAP - EPS, (
                f"frames {left} and {right} are {gap:g} apart; page gap is {GAP:g}"
            )


# --------------------------------------- 3. mainPath 跨岛导线，不是静默 label


def test_a_main_path_edge_is_wired_across_islands_and_never_silently_labelled():
    """§30C: mainPath 是否相邻由真实页面几何/通道决定，不能静默降级为名字."""
    scene = p056.scenes()[3]
    result, page, presentation = compact_page(scene)
    assert_clean(page, scene, presentation)

    frames = {module.id: module.frame for module in page.modules}
    cross = p056.cross_wires(page)
    cross_nets = {segment.net for segment in cross}
    assert cross, "a packed page with a mainPath edge must carry a real cross-module wire"

    # 056 scene 3's two main-path edges: pwr -> rc on 3V3, rc -> div on 3V3F.
    for net_id, (left, right) in {"3V3": ("pwr", "rc"), "3V3F": ("rc", "div")}.items():
        stated = p056.net_names(page)[net_id]
        assert stated == {"wire"}, (
            f"net {net_id!r} is stated as {sorted(stated)} on the page; a mainPath "
            "edge is one whole wire, not a name"
        )
        assert net_id in cross_nets
        ends = {
            p056._frame_of(segment.points[0], frames)
            for segment in cross
            if segment.net == net_id
        } | {
            p056._frame_of(segment.points[-1], frames)
            for segment in cross
            if segment.net == net_id
        }
        assert ends == {left, right}, (
            f"net {net_id!r} crosses {sorted(ends)}, not exactly {left} -> {right}"
        )
        assert not [label for label in page.plan.labels if label.net == net_id], (
            f"net {net_id!r} is also named; one net stated two ways"
        )
        for module_id in (left, right):
            port = module_named(page, module_id).port(net_id)
            assert port is not None and port.kind == "wire"
            assert port.partner == (right if module_id == left else left)


def test_a_packed_page_does_not_read_the_grid_s_adjacency_for_a_main_path_edge():
    """§30C: packed 页无 grid，mainPath 的陈述不得按旧 columns 的邻接静默降级.

    这条是窄判据：只问 `_net_style` 一个决定（`wire` 还是 `label`），不冒充真实
    走线/通道覆盖（那由上面的端到端测试判）。构造的正是旧 grid 会误判的形状：
    `moduleOrder=a,b,c`、3 列，`_adjacent(0, 2, 3, 3)` 为 False（a 与 c 在假想网格的
    同一行、隔着一列），而 flow 里只有 `a -> c` 一条 mainPath 边。若 compact 分支
    退回读旧 columns 邻接，这里会得到 `label`——一个 packed 页从不使用的网格位置
    冒充了页面几何。
    """
    import types

    circuit = p056.circuit(
        [p056.part("R1", "R0402", "10k"), p056.part("R6", "R0402", "10k")],
        [p056.net("A", "signal", ["R1.1", "R6.1"])],
    )
    presentation = p056.spec(
        [
            p056.module("a", ["R1"], "regulator", "ldo"),
            p056.module("b", ["R2"], "filter", "rc-lowpass"),
            p056.module("c", ["R6"], "divider", "voltage-divider"),
        ],
        [{"from": "a", "to": "c", "mainPath": True}],
        moduleOrder=["a", "b", "c"],
        pageArrangement={"strategy": "compact"},
    )
    assert presentation.page_arrangement == PageArrangement(strategy="compact")
    ctx = types.SimpleNamespace(
        circuit=circuit,
        presentation=presentation,
        nets_by_module={"A": ("a", "c")},
    )
    variant = pc._Variant(
        generation=0, order=("a", "b", "c"), columns=3, rung=1.0, compact=True,
    )
    index = {"a": 0, "b": 1, "c": 2}

    # The hypothetical grid is what the compact branch must *not* read: a and c are
    # two columns apart there, and a grid page would name the edge.
    assert pc._adjacent(0, 2, 3, 3) is False
    style, reason = pc._net_style(ctx, variant, "A", index)
    assert style == pc.PAGE_PORT_WIRE, (
        "a packed page decided the mainPath edge by the old grid's adjacency: "
        + reason
    )
    assert "packs its frames" in reason


# ------------------------------------------- 4. packer unsat -> 旧 grid 回退


def install_packer(monkeypatch, answer):
    """Patch every name the page compiler could call the pure packer through."""
    calls = {"count": 0}

    def spy(frames, order, page, **kwargs):
        calls["count"] += 1
        return answer(frames, order, page, **kwargs)

    owners = [owner for owner in (pagepacking, pc) if hasattr(owner, "pack_frames")]
    assert owners, "the page compiler must reach the packer through pagepacking"
    for owner in owners:
        monkeypatch.setattr(owner, "pack_frames", spy)
    return calls


def packed_result(placements):
    frames = {item.name: item.frame for item in placements}
    return PackingResult(
        status=pagepacking.STATUS_PACKED,
        placements=tuple(placements),
        frames=frames,
        width=max(box[2] for box in frames.values()) - min(box[0] for box in frames.values()),
        height=max(box[3] for box in frames.values()) - min(box[1] for box in frames.values()),
        nodes=1,
    )


def refused_result(status, code, detail):
    return PackingResult(
        status=status, placements=(), frames={}, width=0.0, height=0.0, nodes=9,
        failure=PackingFailure(code, detail),
    )


def test_when_the_packer_is_unsat_the_old_grid_page_comes_back_legal(monkeypatch):
    """§30C: unsat 是「这个离散角点空间放不下」，旧 grid 回退且回退页合法."""
    scene = p056.scenes()[3]
    baseline = compile_both(scene)
    assert baseline.ok, p056.render(baseline)

    calls = install_packer(monkeypatch, lambda frames, order, page, **kw:
                           refused_result(
                               pagepacking.STATUS_UNSAT, FAILURE_UNSAT,
                               "test-injected: the corner space holds no packing",
                           ))
    result = compile_both(scene, compact_spec(scene.presentation))
    assert calls["count"] >= 1, (
        "the compact consumer never called pagepacking.pack_frames — the fallback "
        "test would be judging a branch that does not exist"
    )
    assert result.ok, p056.render(result)
    assert pages_of(result, compact=True) == [], (
        "a page was delivered from a packer that refused to place it"
    )

    fallbacks = pages_of(result, compact=False)
    assert fallbacks, "unsat on the packed variants must leave the grid's own pages"
    page = fallbacks[0]
    assert_clean(page, scene, compact_spec(scene.presentation))
    # The fallback is the *old* page, not a re-ranked lookalike: same frames as the
    # baseline grid page, because the grid variants are unchanged and only the
    # packed candidates before them failed.
    assert [module.frame for module in page.modules] == [
        module.frame for module in baseline.pages[0].modules
    ]

    refusals = [item for item in result.rejected
                if COMPACT_TAG in item.variant and item.kind == pc.KIND_PACKING_UNSAT]
    assert refusals, (
        "the packed attempt must be recorded as packing-unsat; kinds seen: "
        + repr(sorted({item.kind for item in result.rejected}))
    )
    assert any("could not pack" in item.reason for item in refusals)


# ------------------------- 5. 坏的 packer 答案（overlap / 出界 / truncated）


def _overlap_answer(frames, order, page, **kwargs):
    placements = []
    for index, name in enumerate(order):
        local = frames[name]
        x = page[0] + 10.0 * index
        y = page[1] + 10.0 * index
        box = (x, y, x + (local[2] - local[0]), y + (local[3] - local[1]))
        placements.append(FramePlacement(name, box, (box[0] - local[0], box[1] - local[1])))
    return packed_result(placements)


def _outside_answer(frames, order, page, **kwargs):
    placements = []
    x = page[2] + 100.0
    for name in order:
        local = frames[name]
        box = (x, page[1], x + (local[2] - local[0]), page[1] + (local[3] - local[1]))
        placements.append(FramePlacement(name, box, (box[0] - local[0], box[1] - local[1])))
        x = box[2] + GAP
    return packed_result(placements)


def _truncated_answer(frames, order, page, **kwargs):
    return refused_result(
        pagepacking.STATUS_TRUNCATED, FAILURE_BUDGET_EXHAUSTED,
        "test-injected: the node budget ran out before the space was exhausted",
    )


BAD_ANSWERS = {
    "overlap": (_overlap_answer, re.compile(r"overlap", re.I)),
    "outside": (
        _outside_answer,
        re.compile(r"outside|leaves the page|off the page|page bound|out of the page", re.I),
    ),
    "truncated": (_truncated_answer, re.compile(r"truncat|node budget|max_nodes", re.I)),
}


@pytest.mark.parametrize("kind", sorted(BAD_ANSWERS))
def test_a_packer_answer_that_breaks_its_own_contract_is_refused_with_a_reason(
    monkeypatch, kind,
):
    """§30C: overlap/出界/truncated 一律拒绝，reason 可区分，不能放行."""
    answer, keyword = BAD_ANSWERS[kind]
    scene = p056.scenes()[2]
    calls = install_packer(monkeypatch, answer)
    result = compile_both(scene, compact_spec(scene.presentation))
    assert calls["count"] >= 1, "the compact consumer never consulted the packer"

    delivered = pages_of(result, compact=True)
    assert delivered == [], (
        f"a {kind} packer answer was delivered as {len(delivered)} compact page(s); "
        "the packer's refusal is not a best-effort hint"
    )
    refusals = [item for item in result.rejected if COMPACT_TAG in item.variant]
    assert refusals, f"the {kind} packed attempt left no rejection record"
    text = " ".join(item.reason for item in refusals)
    assert keyword.search(text), (
        f"the {kind} refusal does not name what went wrong: {text[:400]!r}"
    )
    # Whatever comes out instead is still judged by both checkers: the grid has to
    # be the thing that saves the compile, not a page grown from the bad answer.
    for page in result.pages:
        assert_clean(page, scene, compact_spec(scene.presentation))


def test_the_three_bad_packer_answers_are_told_apart(monkeypatch):
    """§30C: overlap / 出界 / truncated 的理由互不相同，不得混成一个「放不下」."""
    scene = p056.scenes()[2]
    seen: dict[str, set[str]] = {}
    for kind, (answer, _keyword) in BAD_ANSWERS.items():
        install_packer(monkeypatch, answer)
        result = compile_both(scene, compact_spec(scene.presentation))
        refusals = [item for item in result.rejected if COMPACT_TAG in item.variant]
        assert refusals, f"the {kind} answer left no rejection to read"
        seen[kind] = {item.kind for item in refusals}
        assert pages_of(result, compact=True) == [], (
            f"the {kind} answer was delivered as a compact page"
        )
    assert all(seen.values()), seen
    assert len({frozenset(kinds) for kinds in seen.values()}) == len(seen), (
        "the three failures share a reason kind, so a caller cannot act on which: "
        + repr(seen)
    )
    # `overlap` is the page checker's own named violation; the packer statuses keep
    # their separate names (see `_PACKING_KINDS`), and none reads as "does not fit".
    assert "module-frame-overlap" in seen["overlap"], seen["overlap"]
    assert pc.KIND_PACKING_TRUNCATED in seen["truncated"], seen["truncated"]


# ------------------------------- 6. 端口—框—布局同源，且来自干净候选


def test_every_port_is_replayed_from_a_clean_candidate_and_the_final_geometry():
    """§30C: 每轮从原 module candidate 的干净副本重建；frame 与端口一致."""
    scene = p056.scenes()[3]
    presentation = compact_spec(scene.presentation)
    result, page, _ = compact_page(scene, presentation=presentation)
    assert_clean(page, scene, presentation)

    for module in page.modules:
        candidate = candidate_of(result, module)
        # 端口是从候选重建的：先有干净候选，后有端口，再有 frame。
        assert module.ports, f"module {module.id!r} states no shared net at all"
        seen = set()
        for port in module.ports:
            key = (module.id, port.net)
            assert key not in seen, f"module {module.id!r} states {port.net!r} twice"
            seen.add(key)
            anchor = (round(port.x, 6), round(port.y, 6))
            assert anchor in statement_points(page, port.net), (
                f"port {module.id}.{port.net} at {anchor} is a point the page's "
                "final geometry does not state"
            )
            assert _inside(module.frame, anchor), (
                f"port {module.id}.{port.net} is outside its own frame"
            )
            if port.partner:
                other = module_named(page, port.partner).port(port.net)
                assert other is not None and other.partner == module.id, (
                    f"port {module.id}.{port.net} names partner {port.partner!r}, "
                    "whose own port does not name it back"
                )
        # No geometry was moved after the ports were derived: the parts are the
        # candidate's, translated by exactly the stated origin.
        for part_id in module.parts:
            local = candidate.part(part_id)
            placed = page.plan.part(part_id)
            assert local is not None and placed is not None
            assert (placed.x, placed.y) == pytest.approx(
                (local.x + module.origin[0], local.y + module.origin[1]), abs=1e-6
            )

    # 回放收敛、确定性：同一份文档连编两遍，页与拒绝序列逐项相同。
    again = compile_both(scene, presentation)
    assert again.ok
    assert [item.page_geometry_sha256() for item in again.pages] == [
        item.page_geometry_sha256() for item in result.pages
    ]
    assert [item.variant for item in again.rejected] == [
        item.variant for item in result.rejected
    ]
    assert again.pages[0].plan.to_jsonable() == result.pages[0].plan.to_jsonable()


# ------------------------- 7. 三模块：旧 grid 放不下，compact 参差回填放得下


def test_a_three_module_page_the_grid_cannot_hold_but_a_ragged_fill_can():
    """§30C: 最小页面夹具——旧 grid 排不下、新参差布局排得下，且携带跨岛信号.

    The small sheet is **measured**, not guessed: the grid page and the packed page
    are both compiled on the calibration sheet first, their real frames (ports
    included, production's own numbers) are taken per module, and the test page is
    then the ragged fill of those frames plus three module gaps of slack. It is a
    three-module fixture, not the real delivery sheet: the page stays far below
    1170×825 and the test says so.
    """
    scene = p056.scenes()[3]
    baseline = compile_both(scene)
    assert baseline.ok, p056.render(baseline)
    generous = compact_page(scene)[1]

    measured = {}
    for page in (baseline.pages[0], generous):
        for module in page.modules:
            box = module.frame
            width, height = box[2] - box[0], box[3] - box[1]
            old = measured.get(module.id, (0.0, 0.0))
            measured[module.id] = (max(old[0], width), max(old[1], height))
    assert len(measured) == 3

    tall = max(sorted(measured), key=lambda name: measured[name][1])
    rest = [name for name in sorted(measured) if name != tall]
    wide = rest[0] if measured[rest[0]][0] >= measured[rest[1]][0] else rest[1]
    stack = [name for name in rest if name != wide][0]
    width = measured[tall][0] + GAP + measured[wide][0]
    height = max(
        measured[tall][1],
        measured[wide][1] + GAP + measured[stack][1],
    )
    page_box = (0.0, 0.0, width + 3 * GAP, height + 3 * GAP)
    assert page_box[2] < DELIVERY_PAGE[2] and page_box[3] < DELIVERY_PAGE[3], (
        "the fixture must stay a small test page, not the 1170×825 delivery sheet"
    )
    assert (page_box[2] * page_box[3]) < (DELIVERY_PAGE[2] * DELIVERY_PAGE[3])

    small = PageCompileBudget(page_box=page_box)
    grid = compile_both(scene, budget=small)
    assert not grid.ok, (
        "the fixture does not demonstrate a page the old grid cannot hold: "
        + p056.render(grid)
    )
    assert set(grid.categories()) & {"presentation-poor", "layout-unsat"}, (
        f"a page that does not fit is refused by name, got {grid.categories()}"
    )

    result = compile_both(scene, compact_spec(scene.presentation), small)
    assert result.ok, p056.render(result)
    packed = pages_of(result, compact=True)
    assert packed, "the packed arrangement produced nothing on the tight page"
    page = packed[0]
    assert page.page_box == page_box
    assert_clean(page, scene, compact_spec(scene.presentation), small)
    assert p056.cross_wires(page), "the tight page must still carry its cross-island wire"
    for module in page.modules:
        assert _inside_box(module.frame, page_box), (
            f"module {module.id!r} frame {module.frame} leaves the small page {page_box}"
        )
