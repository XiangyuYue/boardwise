"""543H-5: the twin reading is opt-in, and one pad never gets two seats at once.

Two correctness holes left by the 543H pair work:

* **A.** the symbol-frame → page-frame twin reading of an order relation
  (:func:`drawcompiler._order_across_its_pad`) was applied to *every*
  presentation, so old drawings moved (measured: the flyback's `right-of(D3, T1)`
  and the FB_SENSE round, `tests/test_119_pose_ladder_widening.py` and
  `tests/test_551a_failure_rounds.py`). It is now read only on a document that
  declares **both** `textPlacement: native-attr` and `serviceLayout` — the same
  switch the pair bands use — and the three readers (placement, the relation
  failures and the independent `check_grammar`) take it from one predicate,
  ``_pair_reading(presentation)``, so they cannot disagree.
* **B.** two branches hanging off **one pad** with **one symbol** shared one
  band (the group key has no anchor) and landed at one origin: measured, two
  5.1 k pull-downs on one net were drawn at the same point and the plan said ok.
  The second one now takes the next lane out. The service path already answers
  this with perpendicular seats (543E-2) and keeps them.
"""

from __future__ import annotations

import pathlib

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.engines import drawcompiler as dc
from boardwise.engines import pagecompiler as pc

import test_098_ic_periphery as e098
import test_543h_shunt_escape as t543h

ROOT = pathlib.Path(__file__).resolve().parents[1]


# --------------------------------------------------------------- A: the gate


def _usb_binding():
    circuit, presentation = t543h._usb_module()
    return circuit, presentation, dc.bind_grammar(
        circuit, presentation, t543h._library()
    )


def _cc_relation(binding):
    return next(
        item for item in binding.constraints
        if item.kind == "left-of" and item.subject == "R1"
    )


def test_the_twin_reading_is_the_same_predicate_for_every_reader():
    """One predicate, read by the placement, the gate and the checker."""
    presentation = PresentationSpec.from_dict(t543h._page_payload())
    assert dc._pair_reading(presentation) is True
    circuit, module = t543h._usb_module()
    binding = dc.bind_grammar(circuit, module, t543h._library())
    ctx = dc._prepare(
        circuit, module, binding, t543h._library(), dc.CompileBudget()
    ).context
    assert dc._pair_bands(ctx) is dc._pair_reading(module)
    bare = PresentationSpec.from_dict(
        {k: v for k, v in t543h._page_payload().items()
         if k not in ("textPlacement", "serviceLayout")}
    )
    assert dc._pair_reading(bare) is False


@pytest.mark.parametrize("drop", ["serviceLayout", "textPlacement"])
def test_one_key_alone_grades_the_relation_as_stated(drop):
    """Only the document that states both keys reads the relation turned."""
    payload = t543h._page_payload()
    payload.pop(drop)
    presentation = PresentationSpec.from_dict(payload)
    assert dc._pair_reading(presentation) is False

    circuit, module = t543h._usb_module()
    binding = dc.bind_grammar(circuit, module, t543h._library())
    item = _cc_relation(binding)
    # The page the *both-keys* document draws: the branch stands on its pad's
    # escape side, so the stated `left-of` does not hold. The one thing that
    # decides whether that is a broken relation or the page-frame reading is
    # the switch — measured on the same points, not on a second compile.
    plan = t543h._compile_payload(
        PresentationSpec.from_dict(t543h._page_payload())
    ).pages[0].plan
    escaped = t543h._pin_escape(plan, "USB1", "A5")
    points = dict(
        origin_of=lambda part_id: (
            t543h._part(plan, part_id).x, t543h._part(plan, part_id).y
        ),
        pin_of=lambda part_id, token: t543h._pin_point(plan, f"{part_id}.{token}"),
        grid=5.0, near_limit=300.0,
        lateral=(0.0, 1.0), progress=(1.0, 0.0),
        escape_of=lambda _part_id, _token: escaped,
        frame_of=lambda _part_id, _token: (-1.0, 0.0),
    )
    as_stated = dc._relation_violations(
        circuit, binding, pair_reading=False, **points
    )
    turned = dc._relation_violations(
        circuit, binding, pair_reading=True, **points
    )
    assert item in [entry for entry, _ in as_stated], (
        "without both keys the relation must be graded as the binder wrote it"
    )
    assert item not in [entry for entry, _ in turned], (
        "with both keys the same relation is read in the page frame"
    )


def test_both_keys_turn_it_on_the_ten_grammar_input():
    """The switch is read, not guessed: same documents, only the keys differ."""
    circuit, module = t543h._usb_module()
    binding = dc.bind_grammar(circuit, module, t543h._library())
    item = _cc_relation(binding)
    plan = t543h._compile_payload(PresentationSpec.from_dict(t543h._page_payload())).pages[0].plan
    escaped = t543h._pin_escape(plan, "USB1", "A5")
    broken = dc._relation_violations(
        circuit, binding,
        origin_of=lambda part_id: (
            t543h._part(plan, part_id).x, t543h._part(plan, part_id).y
        ),
        pin_of=lambda part_id, token: t543h._pin_point(plan, f"{part_id}.{token}"),
        grid=5.0, near_limit=300.0,
        lateral=(0.0, 1.0), progress=(1.0, 0.0),
        escape_of=lambda _part_id, _token: escaped,
        frame_of=lambda _part_id, _token: (-1.0, 0.0),
        pair_reading=dc._pair_reading(
            PresentationSpec.from_dict(t543h._page_payload())
        ),
    )
    assert item not in [item for item, _ in broken], (
        "with both keys the relation is read in the page frame"
    )


# ------------------------------------------------- B: one pad, two branches


def _one_pad_circuit():
    """Two identical pull-downs sharing one pad of the core."""
    part, net, circuit = e098.part, e098.net, e098.circuit
    spec = circuit(
        [part("U1", "SOIC-16-CORE", "CH340G"),
         part("R1", "R0402", "5.1k"), part("R2", "R0402", "5.1k")],
        [net("VCC", "power", ["U1.16"]),
         net("GND", "gnd", ["U1.1", "R1.2", "R2.2"]),
         net("V3", "signal", ["U1.15", "R1.1", "R2.1"])],
    )
    payload = {
        "grammarRef": "ic-periphery",
        "modules": [{"id": "m", "parts": ["U1", "R1", "R2"],
                     "role": "core with two pull-downs", "core": "U1"}],
        "textPlacement": "native-attr",
        "serviceLayout": {"pinGap": 30},
    }
    return spec, PresentationSpec.from_dict(payload)


def test_two_branches_on_one_pad_never_share_a_place():
    """543H-5: the second one takes the next lane; the plan may not say ok on
    two parts at one point (measured before the fix: both at (170, -110))."""
    spec, presentation = _one_pad_circuit()
    result = dc.compile(spec, presentation, e098.library(), dc.CompileBudget())
    assert result.ok, result.render_failures()
    for plan in result.candidates:
        r1 = next(item for item in plan.parts if item.reference == "R1")
        r2 = next(item for item in plan.parts if item.reference == "R2")
        assert (r1.x, r1.y) != (r2.x, r2.y), (
            f"two branches share one origin: {(r1.x, r1.y)}"
        )


def test_the_same_circuit_without_the_keys_keeps_its_old_answer():
    """Without both keys the group reading is off and the plan is unchanged."""
    spec, presentation = _one_pad_circuit()
    payload = presentation.to_jsonable()
    payload.pop("textPlacement")
    payload.pop("serviceLayout")
    bare = PresentationSpec.from_dict(payload)
    assert dc._pair_reading(bare) is False
    result = dc.compile(spec, bare, e098.library(), dc.CompileBudget())
    assert result.ok, result.render_failures()
    plan = result.candidates[0]
    r1 = next(item for item in plan.parts if item.reference == "R1")
    r2 = next(item for item in plan.parts if item.reference == "R2")
    assert (r1.x, r1.y) != (r2.x, r2.y)


def _three_on_one_pad():
    """Two same-symbol parts and one different symbol, all on one pad.

    Two host pins on the net keep the service path out of it (543A needs one),
    so all three come through the generic ladder — which is where the lanes are
    handed out.
    """
    part, net, circuit = e098.part, e098.net, e098.circuit
    spec = circuit(
        [part("U1", "SOIC-16-CORE", "CH340G"),
         part("C1", "C0402", "100nF"), part("C2", "C0402", "100nF"),
         part("C3", "C0402-B", "100nF")],
        [net("VCC", "power", ["U1.16"]),
         net("GND", "gnd", ["U1.1", "C1.2", "C2.2", "C3.2"]),
         net("V3", "signal", ["U1.15", "U1.14", "C1.1", "C2.1", "C3.1"])],
    )
    payload = {
        "grammarRef": "ic-periphery",
        "modules": [{"id": "m", "parts": ["U1", "C1", "C2", "C3"],
                     "role": "core with three parts on one pad", "core": "U1"}],
        "textPlacement": "native-attr",
        "serviceLayout": {"pinGap": 30},
    }
    book = e098.library(**{"C0402-B": e098.cap("C0402-B")})
    return spec, PresentationSpec.from_dict(payload), book


def test_a_second_group_on_one_pad_gets_its_own_lanes():
    """543H-5b: a group reserves as many lanes as its pad holds branches.

    Measured before the fix: `C2` (second of its group) and `C3` (first of the
    next group) both took lane 1, so two parts were drawn at one point and the
    plan said ok. The span rule reserves the group's own pad load first.
    """
    spec, presentation, book = _three_on_one_pad()
    result = dc.compile(spec, presentation, book, dc.CompileBudget())
    assert result.ok, result.render_failures()
    for plan in result.candidates:
        seats = {
            item.reference: (item.x, item.y)
            for item in plan.parts if item.reference.startswith("C")
        }
        assert len(set(seats.values())) == len(seats), (
            f"two branches share one origin: {seats}"
        )
