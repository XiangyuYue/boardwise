"""053K：显式 `attach` 的一对模块按声明 gap 摆放，页面 module gap 只管其他对。

053c 让 `attach` 把模块贴到宿主一侧，但摆放取 ``max(attach.gap, module_gap)``：
声明 10 的文档在 40 间距的页面上仍然被摆到 40，于是去耦行看起来仍是独立小组。
本批把「声明即契约」落到两处：编译器按声明 gap 摆（只做向外的栅格取整），
检查器对这一对豁免 module gap。边界不变——**面积重叠仍然硬拒**，别的模块对仍按
module gap，没写 `attach` 的文档逐点保持旧行为。

这里断言的是可观测结果，不重述 `_attach_shift` 的算术：编译出来的 frame 间距、
`readability.check_page` 的 findings、以及页面 notes 的说法。
"""

from __future__ import annotations

from dataclasses import replace

import pytest

import test_053c_attach as b053c
import test_056_pagecompiler as p056

from boardwise.core.pagelayoutplan import PageLayoutPlan
from boardwise.engines import pagecompiler as pc
from boardwise.engines import readability

PAGE = b053c.PAGE
GAP = 10.0


def compile_chain(presentation):
    return b053c.compile_chain(presentation)


def modules_of(page) -> dict:
    return {module.id: module for module in page.modules}


def page_check(page, presentation):
    """The page domain's findings for one page, at the 056 sheet's module gap."""
    return readability.check_page(
        page, p056.chain_circuit(), presentation, p056.library(),
        module_gap=PAGE.module_gap,
    )


def overlap_findings(check) -> list:
    return [
        item for item in check.hard_violations
        if item.kind == readability.KIND_MODULE_FRAME_OVERLAP
    ]


def evidence_for(findings, left: str, right: str) -> list[str]:
    """Evidence of the findings whose two subjects are exactly these modules."""
    wanted = {
        f"pageLayout.modules[{left}]", f"pageLayout.modules[{right}]",
    }
    return [item.evidence for item in findings if set(item.objects) == wanted]


def moved_below(frame, host, gap: float):
    """``frame`` of the same size, centred under ``host`` at ``gap`` units."""
    width, height = frame[2] - frame[0], frame[3] - frame[1]
    centre = (host[0] + host[2]) / 2
    return (
        centre - width / 2, host[1] - gap - height,
        centre + width / 2, host[1] - gap,
    )


def with_frames(page: PageLayoutPlan, **frames) -> PageLayoutPlan:
    return replace(page, modules=[
        replace(module, frame=frames[module.id])
        if module.id in frames else module
        for module in page.modules
    ])


# ------------------------------------------------------- attach 对按声明 gap


def test_an_attach_pair_keeps_its_ten_units_on_a_forty_unit_page():
    result = compile_chain(b053c.attached_chain({"to": "rc", "gap": GAP}))
    assert result.pages, [failure.detail for failure in result.failures]
    page = result.pages[0]
    assert page.verdict == "pass"
    host, attached = modules_of(page)["rc"], modules_of(page)["div"]
    assert PAGE.module_gap == 40
    separation = host.frame[1] - attached.frame[3]
    assert GAP - 1e-6 <= separation < GAP + PAGE.grid + 1e-6, separation
    # The pair is exempt, so the checker has nothing to say about it.
    assert evidence_for(
        overlap_findings(page_check(page, b053c.attached_chain({"to": "rc", "gap": GAP}))),
        "div", "rc",
    ) == []


def test_an_attached_pair_that_overlaps_is_still_refused():
    presentation = b053c.attached_chain({"to": "rc", "gap": GAP})
    page = compile_chain(presentation).pages[0]
    modules = modules_of(page)
    host = modules["rc"].frame
    # Same-size frame, shifted onto the host: area overlap, the one thing the
    # attach exemption never covers.
    frame = modules["div"].frame
    width, height = frame[2] - frame[0], frame[3] - frame[1]
    on_host = (host[0] + 5, host[1] + 5, host[0] + 5 + width, host[1] + 5 + height)
    check = page_check(with_frames(page, div=on_host), presentation)
    evidence = evidence_for(overlap_findings(check), "div", "rc")
    assert evidence, [item.render() for item in check.hard_violations]
    assert "overlap" in evidence[0]


def test_a_pair_without_attach_is_still_refused_at_ten():
    presentation = b053c.plain_chain()
    page = compile_chain(presentation).pages[0]
    modules = modules_of(page)
    check = page_check(
        with_frames(page, div=moved_below(modules["div"].frame, modules["rc"].frame, GAP)),
        presentation,
    )
    evidence = evidence_for(overlap_findings(check), "div", "rc")
    assert evidence, [item.render() for item in check.hard_violations]
    assert "module gap is 40" in evidence[0], evidence[0]


def test_an_attached_module_keeps_the_module_gap_to_a_non_host_neighbour():
    presentation = b053c.attached_chain({"to": "rc", "gap": GAP})
    page = compile_chain(presentation).pages[0]
    modules = modules_of(page)
    check = page_check(
        with_frames(page, pwr=moved_below(modules["pwr"].frame, modules["div"].frame, GAP)),
        presentation,
    )
    evidence = evidence_for(overlap_findings(check), "pwr", "div")
    assert evidence, [item.render() for item in check.hard_violations]
    assert "module gap is 40" in evidence[0], evidence[0]
    # And the host pair itself is still quiet.
    assert evidence_for(overlap_findings(check), "div", "rc") == []


@pytest.mark.parametrize("side", ["bottom", "top", "left", "right"])
@pytest.mark.parametrize("gap", [GAP, 25.0])
def test_every_side_keeps_the_declared_gap_rounded_outward_only(side, gap):
    presentation = b053c.attached_chain({"to": "rc", "side": side, "gap": gap})
    result = compile_chain(presentation)
    assert result.pages, [failure.detail for failure in result.failures]
    page = result.pages[0]
    host, attached = modules_of(page)["rc"], modules_of(page)["div"]
    if side == "bottom":
        separation = host.frame[1] - attached.frame[3]
    elif side == "top":
        separation = attached.frame[1] - host.frame[3]
    elif side == "left":
        separation = host.frame[0] - attached.frame[2]
    else:
        separation = attached.frame[0] - host.frame[2]
    assert gap - 1e-6 <= separation < gap + PAGE.grid + 1e-6, separation
    assert overlap_findings(page_check(page, presentation)) == []


def test_the_page_note_states_the_declared_gap_and_the_exemption():
    presentation = b053c.attached_chain({"to": "rc", "gap": GAP})
    page = compile_chain(presentation).pages[0]
    notes = [note for note in page.notes if "is attached to" in note]
    assert len(notes) == 1, page.notes
    note = notes[0]
    assert "keeping the document's 10 canvas units" in note, note
    assert "exempt from the page's module gap of 40" in note, note
    assert "keeping 40 canvas units" not in note, note


# ------------------------------------------------------- 未写 attach ＝旧行为


def test_a_document_without_attach_compiles_and_checks_as_before():
    presentation = b053c.plain_chain()
    result = compile_chain(presentation)
    assert result.pages, [failure.detail for failure in result.failures]
    page = result.pages[0]
    assert page.verdict == "pass"
    assert not [note for note in page.notes if "is attached to" in note], page.notes
    modules = modules_of(page)
    names = sorted(modules)
    for index, left in enumerate(names):
        for right in names[index + 1:]:
            gap = pc._frame_gap(modules[left].frame, modules[right].frame)
            assert gap >= PAGE.module_gap - 1e-6, (left, right, gap)
    # Same page, same statement at every pair: no exemption is in play.
    assert overlap_findings(page_check(page, presentation)) == []
