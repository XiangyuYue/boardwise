"""548C3：页端口成员名解析（②）与页 label 兜底承载杆（③），以及覆盖洞（④）。

② `pagecompiler._port_members` 把 `<位号>.<token>` 过
`readability._profile_pin_ruler`（脚号优先、再脚名）解析成该符号自己的**脚号**，
再用它查 `_pin_points`；符号没有的 token 是点名拒绝，不是静默 `None`。
③ `pagecompiler._label_port_point` 给页的兜底 label 一根**自己的水平承载杆**，
不让模块既有导线因为 label 锚点而变成宿主打印名字的载体。
④ 547A 夹具在**页面预算**（`gndClusterRadius=100`）下仍失败——出厂测试只走
radius=0，这条路径从未被它走过（548C2 的假绿）。① 未裁定前不可能绿，故 strict xfail；
转绿（XPASS(strict)）即信号：该洞已被补上，需回改 548C3 的账。
"""

from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest

import test_547_repeated_shunts as m547

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.core.textmetrics import wire_name_row
from boardwise.engines import drawcompiler as dc
from boardwise.engines import pagecompiler as pc


def _document(radius: int = 0):
    """The 547A documents, with the page's own module budget stated."""
    circuit_payload = copy.deepcopy(m547._circuit())
    presentation_payload = copy.deepcopy(m547._presentation())
    if radius:
        presentation_payload["gndClustering"] = {"radius": radius}
    else:
        # radius=0 is "the key states nothing" (the module budget's default), and
        # the spec schema refuses to *state* a zero.
        presentation_payload.pop("gndClustering", None)
    circuit = CircuitSpec.from_dict(circuit_payload)
    presentation = PresentationSpec.from_dict(presentation_payload)
    book = {
        profile.symbol_ref: profile
        for profile in (
            SymbolProfile.from_dict(copy.deepcopy(payload))
            for payload in m547._profiles().values()
        )
    }
    return circuit, presentation, book


def _module(module_id: str, radius: int = 0):
    """One module's own view, compiled the way the page compiles it."""
    circuit, presentation, book = _document(radius)
    module = presentation.module(module_id)
    sub_circuit, sub_presentation = pc._module_view(circuit, presentation, module)
    budget = dc.CompileBudget(gnd_cluster_radius=float(radius))
    result = dc.compile(sub_circuit, sub_presentation, book, budget)
    return result, module, sub_circuit, sub_presentation, book


def _ctx(sub_circuit, sub_presentation, module, book):
    """Only the two answers `_port_members` reads, not a fabricated full context."""
    return SimpleNamespace(
        views={module.id: (sub_circuit, sub_presentation)}, book=book
    )


# --------------------------------------------------------------------------
# ② 成员名解析
# --------------------------------------------------------------------------


def test_named_pin_members_resolve_to_the_symbols_own_numbers():
    """`J1.VCC`/`J1.GND`/`J1.CS` are names; `_pin_points` speaks numbers."""
    result, module, sub_circuit, sub_presentation, book = _module("lcd")
    assert result.ok, [failure.detail for failure in result.failures]
    plan = result.candidates[0]
    ctx = _ctx(sub_circuit, sub_presentation, module, book)

    members, failure = pc._port_members(ctx, plan, module, "3V3")
    assert failure is None
    assert members == ["J1.1"]

    members, failure = pc._port_members(ctx, plan, module, "GND")
    assert failure is None
    # the ruler sorts by the *spec* spelling: J1.CS -> J1.7 comes before J1.GND
    assert members == ["J1.7", "J1.2"]

    pins = pc._pin_points(plan, book)
    assert "J1.1" in pins and "J1.2" in pins and "J1.7" in pins
    point = pc._port_point(members, pins, (1.0, 0.0))
    assert point == (-30.0, 20.0)


def test_a_member_the_symbol_lacks_is_refused_by_name():
    """A wrong token is a named refusal — never a guessed near match.

    The page's resolver is asked directly: the *module* compiler refuses the same
    document even earlier (`required-pin-not-connected`), so compiling the typo
    would prove the other layer's refusal, not this one.
    """
    good, module, _sub_circuit, _sub_presentation, book = _module("lcd")
    assert good.ok
    plan = good.candidates[0]

    payload = copy.deepcopy(m547._circuit())
    for net in payload["nets"]:
        if net["id"] == "3V3":
            net["members"] = [
                "J1.NOPE" if member == "J1.VCC" else member
                for member in net["members"]
            ]
    circuit, presentation, _book = _document()
    circuit = CircuitSpec.from_dict(payload)
    sub_circuit, sub_presentation = pc._module_view(
        circuit, presentation, presentation.module("lcd")
    )
    ctx = _ctx(sub_circuit, sub_presentation, module, book)

    members, failure = pc._port_members(ctx, plan, module, "3V3")
    assert members == []
    assert failure is not None
    assert "J1.NOPE" in failure.detail
    assert "'LCD'" in failure.detail
    assert "VCC" in failure.detail


# --------------------------------------------------------------------------
# ③ 页 label 兜底承载杆
# --------------------------------------------------------------------------


def test_the_pages_fallback_label_gets_its_own_horizontal_lead():
    """The anchor must not ride the module's conductor (548C2 C/③)."""
    result, module, sub_circuit, sub_presentation, book = _module("lcd")
    assert result.ok, [failure.detail for failure in result.failures]
    plan = result.candidates[0]
    ctx = _ctx(sub_circuit, sub_presentation, module, book)
    members, failure = pc._port_members(ctx, plan, module, "GND")
    assert failure is None
    pins = pc._pin_points(plan, book)
    point = pc._port_point(members, pins, (1.0, 0.0))
    assert point is not None
    # the module's own GND wire really runs through that pin tip
    assert pc._rides_conductor(plan, "GND", point)

    occupied = pc._module_boxes(plan, book)
    occupied_before = list(occupied)
    before = list(plan.segments)
    end, preferred = pc._label_port_point(
        plan, "GND", members, pins, point, (1.0, 0.0), occupied
    )

    assert len(plan.segments) == len(before) + 1
    lead = plan.segments[-1]
    assert lead.net == "GND"
    (ax, ay), (bx, by) = [(float(x), float(y)) for x, y in lead.points]
    assert ay == by, "the page's carrier runs horizontally (S-20)"
    assert abs(abs(bx - ax) - 40.0) < 1e-9, "the first rung of the compiler's ladder"
    assert preferred in ((1.0, 0.0), (-1.0, 0.0))
    assert (bx - ax) * preferred[0] > 0, "the label's box faces along its own lead"
    assert end == (bx, by)
    # the anchor stands on the page's lead alone, never on a module conductor
    assert not any(
        pc._on_run(end, (float(a[0]), float(a[1])), (float(b[0]), float(b[1])))
        for segment in before
        for a, b in zip(segment.points, segment.points[1:])
    )

    row = wire_name_row([(ax, ay), (bx, by)], "GND")
    assert row is not None and row.horizontal
    assert not any(pc._overlaps(row.box, box) for box in occupied_before)


# --------------------------------------------------------------------------
# ②③ → 页：真实 `_module_ports` 上的正向回归（548R1）
#
# 上面三条测的是 helper 本身；下面两条走页面自己的 stage 1–2 —— `_nets_by_module`
# 定共享网、`_compile_modules` 逐模块调 `drawcompiler.compile`，再把真
# `_module_ports` 的端口表与它写进图里的东西一起断言。因此覆盖链是
# 「命名脚解析 → 页自有水平 label 承载杆 → preferred 进 `_port` → 端口表」，不停在
# helper 的返回值上。
# --------------------------------------------------------------------------


def _page_context(radius: int = 0):
    """The page's own context, built the way `compile_page` builds it."""
    circuit, presentation, book = _document(radius)
    budget = pc.PageCompileBudget(page_box=(0.0, 0.0, 2000.0, 2000.0))
    ctx = pc._Context(
        circuit=circuit,
        presentation=presentation,
        book=book,
        budget=budget,
        modules=list(presentation.modules),
        results={},
        views={},
        nets_by_module=pc._nets_by_module(circuit, presentation),
    )
    failures = pc._compile_modules(ctx, pc.PageCompileResult())
    assert failures == [], [failure.detail for failure in failures]
    return ctx, book


def _page_ports(ctx, module_id: str, generation: int = 0):
    """One module's real port table, from its own `generation`-th drawing."""
    module = ctx.module(module_id)
    candidates = ctx.results[module_id].candidates
    assert candidates, f"module {module_id!r} has no drawing to port"
    plan = pc._copy_plan(candidates[min(generation, len(candidates) - 1)])
    segments_before = len(plan.segments)
    order = tuple(item.id for item in ctx.modules)
    index = {name: position for position, name in enumerate(order)}
    variant = pc._Variant(generation=generation, order=order, columns=3, rung=1.0)
    ports, failure = pc._module_ports(ctx, module, plan, variant, index)
    assert failure is None, failure.detail
    return plan, ports, segments_before


def test_the_page_ports_the_named_pins_and_owns_the_labels_lead():
    """A named member reaches the page as its pin number, on the page's own lead.

    `lcd` (the LCD connector) is the case ② is about: its `GND` members are
    spelled `J1.GND`/`J1.CS` while the drawing is keyed by numbers, and the
    module's own GND run already passes the chosen pin — so a page label put
    straight on that point would turn the module's wire into its name carrier,
    and ③ has to give the page's label a lead of its own. Both are checked on
    the port table the page keeps and on the drawing the page ships.
    """
    ctx, book = _page_context()
    plan, ports, segments_before = _page_ports(ctx, "lcd")
    gnd = next(port for port in ports if port.net == "GND")
    assert gnd.kind == pc.PAGE_PORT_LABEL
    pins = pc._pin_points(plan, book)
    # ②'s two spellings: the module's own circuit says `J1.GND`/`J1.CS`, the
    # drawing is keyed by the numbers the profile gives those two pins — and the
    # port below could not have a point at all if the ruler had not resolved them
    # (`_module_ports` returns a named refusal instead, which the helper above
    # already refuses to accept).
    local_members = {
        member.partition(".")[2] for member in ctx.views["lcd"][0].net("GND").members
    }
    assert {"GND", "CS"} <= local_members, local_members
    assert "J1.2" in pins and "J1.7" in pins, sorted(pins)

    added = plan.segments[segments_before:]
    assert len(added) == 1, [segment.points for segment in added]
    lead = added[0]
    assert lead.net == "GND"
    (ax, ay), (bx, by) = [(float(x), float(y)) for x, y in lead.points]
    assert ay == by, "the page's carrier for its own label runs horizontally (S-20)"
    assert abs(bx - float(gnd.x)) <= 1e-6 and abs(by - float(gnd.y)) <= 1e-6, (
        "the port is the far end of the lead the page drew, not the module's pin")
    # the lead starts on a conductor the module already drew: the page's carrier
    # is its own, the module's wire is not turned into the name's carrier.
    assert any(
        pc._on_run((ax, ay), (float(a[0]), float(a[1])), (float(b[0]), float(b[1])))
        for segment in plan.segments[:segments_before]
        for a, b in zip(segment.points, segment.points[1:])
    ), f"the lead starts at {(ax, ay)}, not on the module's own wiring"
    assert not any(
        pc._on_run((float(gnd.x), float(gnd.y)),
                   (float(a[0]), float(a[1])), (float(b[0]), float(b[1])))
        for segment in plan.segments[:segments_before]
        for a, b in zip(segment.points, segment.points[1:])
    ), "the page's anchor must not ride a module conductor (the E2 defect)"
    label = next(item for item in plan.labels
                 if (item.x, item.y) == (gnd.x, gnd.y) and item.net == "GND")
    box = label.bbox
    centre_x = (box[0] + box[2]) / 2.0
    assert abs(centre_x - float(gnd.x)) > 1e-6, "the label's box leaves its anchor"
    assert box[1] <= float(gnd.y) <= box[3], (
        "the page's label stands on the anchor's own row, so one horizontal lead "
        "reaches its box")


def test_the_page_port_stands_on_the_label_the_module_faces():
    """③'s `preferred` decides **which** of a module's own labels the page names.

    The second drawing (`generation=1`) of `wifi`/`env` states `GND` with two
    labels: the connector pin's and the decoupling cap's. `wifi` closes its row,
    so the page reads out of it downwards and the port must be the **bottom**
    label; `env` stands in a column that continues with `bmp`, so it faces down
    too. Naming the other label would put the page's cross-module statement on
    the side the reader does not leave by.
    """
    ctx, _book = _page_context()
    for module_id, drawing, facing, behind in (
        ("wifi", [(20.0, 25.0), (30.0, 15.0)], (30.0, 15.0), (20.0, 25.0)),
        ("env", [(25.0, 15.0), (35.0, 5.0)], (35.0, 5.0), (25.0, 15.0)),
    ):
        plan, ports, _segments_before = _page_ports(ctx, module_id, generation=1)
        gnd_labels = [(float(item.x), float(item.y)) for item in plan.labels
                      if item.net == "GND"]
        assert gnd_labels == drawing, (
            f"{module_id}: the second drawing should state GND twice, got "
            f"{gnd_labels}")
        port = next(item for item in ports if item.net == "GND")
        assert port.kind == pc.PAGE_PORT_LABEL
        assert (port.x, port.y) == facing, (
            f"{module_id}: the GND port is at {(port.x, port.y)}, not on the label "
            f"facing the module's partner at {facing}; the module's own other GND "
            f"label {behind} is the one away from it")
        # the port names a label the module's own drawing already holds — the
        # page did not invent a second statement of a net the module states.
        assert any(item.net == "GND" and (item.x, item.y) == (port.x, port.y)
                   for item in plan.labels)


# --------------------------------------------------------------------------
# ④ 覆盖洞：547A 在页面预算下仍失败
# --------------------------------------------------------------------------


class _PageBudgetGap(AssertionError):
    """The one refusal 548C3's strict xfail is allowed to record as expected.

    Everything else — a different category, a different net or a refusal this
    gap does not describe — stays a plain `AssertionError`, which pytest does
    **not** match against the marker's `raises=`: an unrelated red is a red, not
    a stale expectation.
    """


def _assert_the_known_page_budget_gap(result) -> None:
    """Pin *why* 547A still fails at the page budget, then declare the known gap.

    The refusal is ①'s: the +100 radius splits the island's GND into four
    unnamed neighbourhoods, so the independent gate reads one net as four nodes
    (`netlist-partition-mismatch`). Every clause below is part of that refusal
    and none of it is optional; the point is that a *different* failure — a
    rewritten gate, another net, another split — cannot be swallowed by this
    marker.
    """
    assert result.failures, "a refusing compile must carry at least one failure"
    failure = result.failures[0]
    assert failure.category == "layout-unsat", (
        f"the page budget's refusal is layout-unsat, got {failure.category!r}: "
        f"{failure.detail}")
    assert failure.subject == "gate", (
        f"the refusal comes from the independent gate, got {failure.subject!r}")
    assert "netlist-partition-mismatch" in failure.detail, failure.detail
    assert "4 separate node(s)" in failure.detail, failure.detail
    assert "BZ1.2 ; C1.2, R1.2 ; D1.2, D2.2 ; U1.VSS, U1.VSSA" in failure.detail, (
        "the split the gate reports is no longer the one 548C3 recorded: "
        + failure.detail)
    raise _PageBudgetGap(failure.detail)


@pytest.mark.xfail(
    strict=True,
    raises=_PageBudgetGap,
    reason=(
        "548C2 的假绿：547A 出厂测试只编译 radius=0（dc.compile 不传预算），"
        "页面预算 gndClusterRadius=100 的拆分地路径从未被它走过。该预算下 547A 的 "
        "mcu 仍是 layout-unsat（GND 拆成 4 个零命名邻域），① 每簇命名未裁定前不可能绿；"
        "本测试转绿即说明 ① 或等价能力已落地，需回改 548C3 的账"
    ),
)
def test_the_547a_island_still_refuses_the_page_budget():
    result, module, _sub_circuit, _sub_presentation, _book = _module(
        "mcu", radius=100
    )
    if not result.ok:
        _assert_the_known_page_budget_gap(result)
    assert result.ok, [
        f"[{failure.category}] {failure.detail}" for failure in result.failures
    ]
