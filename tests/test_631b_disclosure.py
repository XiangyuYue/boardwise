"""631B-02 / -03 / -06: the three disclosure holes (岳 J3).

None of these refuses anything — the ruling is 「松一点，但要让 agent 知道」:

  * **B-02** (J3.1) an illegal candidate is **not** dropped; the ranking already
    sorts on legality, and `compile_page` now says out loud that one of the listed
    pages carries hard violations.
  * **B-03** (J3.3) the page chain does **not** derive the sheet's title-block
    keep-out — the island chain does — and the leg stays closed. What changes is
    that a page nobody checked reads differently from a page that passed.
  * **B-06** the `modules=[]` branch of `_reference_failures` was reported as
    unreachable ("the schema refuses it first"). It is reachable: an explicit
    `"modules": []` is a legal document. The test below is the proof, so the
    branch is a judgement with coverage rather than dead code.
"""

from __future__ import annotations

import dataclasses

import test_056_pagecompiler as base

import boardwise.engines.pagecompiler as pc
from boardwise.core.presentationspec import (
    PRESENTATION_SPEC_KIND,
    PRESENTATION_SPEC_VERSION,
    PresentationSpec,
)


# ------------------------------------------------------------------ 631B-02


def test_b02_a_listed_page_with_a_hard_violation_is_called_out(monkeypatch):
    """J3.1：非法候选**不删**，但必须有一条 note 说「它在列表里，而且不合法」。"""
    real = pc._measure

    def forced(page):
        candidate = real(page)
        key = candidate.key
        return dataclasses.replace(candidate, key=(1,) + tuple(key[1:]))

    monkeypatch.setattr(pc, "_measure", forced)
    scene = base.scenes()[1]
    result = pc.compile_page(
        scene.circuit,
        base.regulator_plus_divider_spec(),
        base.library(),
        pc.PageCompileBudget(page_box=(0.0, 0.0, 1170.0, 825.0)),
    )
    assert result.pages, "这条用例要有页，才谈得上「它在列表里」"
    text = " ".join(result.notes)
    assert "hard readability violation(s)" in text, text
    assert "listed rather than removed" in text, text


def test_b02_a_clean_page_says_nothing_about_violations():
    """对照组：没有硬违规就不许冒这条 note。"""
    scene = base.scenes()[1]
    result = pc.compile_page(
        scene.circuit,
        base.regulator_plus_divider_spec(),
        base.library(),
        pc.PageCompileBudget(page_box=(0.0, 0.0, 1170.0, 825.0)),
    )
    assert "hard readability violation(s)" not in " ".join(result.notes), result.notes


# ------------------------------------------------------------------ 631B-03


def test_b03_a_page_with_no_stated_keepout_says_s01_was_not_checked():
    """J3.3：不开那条腿，但「没查」必须写成一条可读的读数。"""
    scene = base.scenes()[1]
    result = pc.compile_page(
        scene.circuit,
        base.regulator_plus_divider_spec(),
        base.library(),
        pc.PageCompileBudget(page_box=(0.0, 0.0, 1170.0, 825.0)),
    )
    text = " ".join(result.notes)
    assert "S-01's block is NOT protected" in text, text
    assert "budget.keepouts" in text, text


def test_b03_a_stated_keepout_is_not_told_it_was_skipped():
    """对照组：调用方自己给了 keep-out，就不该读到「没查」。"""
    scene = base.scenes()[1]
    result = pc.compile_page(
        scene.circuit,
        base.regulator_plus_divider_spec(),
        base.library(),
        pc.PageCompileBudget(
            page_box=(0.0, 0.0, 1170.0, 825.0),
            keepouts=((460.0, 10.0, 1160.0, 190.0),),
        ),
    )
    assert "S-01's block is NOT protected" not in " ".join(result.notes), result.notes


# ------------------------------------------------------------------ 631B-06


def test_b06_a_document_with_no_modules_is_a_page_level_refusal():
    """`modules: []` 是合法文档，所以这条分支**可达** —— 它就是页级分类的出口。"""
    presentation = PresentationSpec.from_dict(
        {
            "kind": PRESENTATION_SPEC_KIND,
            "specVersion": PRESENTATION_SPEC_VERSION,
            "modules": [],
        }
    )
    scene = base.scenes()[1]
    failures = pc._reference_failures(scene.circuit, presentation)
    assert len(failures) == 1, failures
    assert failures[0].subject == "PresentationSpec.modules"
    assert failures[0].category == pc.FAILURE_PRESENTATION_POOR
