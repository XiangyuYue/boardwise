"""543G-2: the pair bands may not split a pair the grammar bound as adjacent.

Measured on ch340_serial with the whole 543 opt-in set (``textPlacement:
native-attr`` + ``serviceLayout``, i.e. the pair reading) and the crystal kept
in its own module: **0 candidates / 7 refusals**, every one of them
``presentation-poor/X1`` — "the relation adjacent(X1, C1) is not honoured".

The source is not ``_bay_buckets`` (that pass never runs here — ``_declared_among``
short-circuits it) but the ladder's **band index**, the one the pair reading
hands out per ``(owner, role, symbol)`` group: the crystal ``X1`` and its XI load
capacitor ``C1`` are drawn with two different symbols, so ``X1`` took a group base
three lanes out while ``C1`` collapsed onto band 0 with ``C2``. ``C1`` then had
``C2``'s pin in its trail, the pin dodge moved it 20 units down, and the two
parted rows.

The rule pinned here (543G-2, ``_declared_sibling_owners``): the pair reading
answers the grammar's **silence**. When the grammar states any relation between
two branches of one owner, that owner's branches keep the ladder's old
per-``(owner, direction)`` staircase, and the pair reading does not run for them.
It reads constraint endpoints and slot owners only — no part id, net name or pin
number — and it is the pair reading that is withheld, never the relation.

Three facts are pinned separately, because "restore the row" alone would be
satisfied by switching the feature off:

* the crystal row holds and the page compiles under the full opt-in set;
* an ordinary same-symbol pair (no relation between the two) still shares one
  band, and two branches on one pad still take two seats — 543K/543H-5 are not
  paid for with this fix;
* the guard is what keeps the row: forcing ``_declared_sibling_owners`` to answer
  nothing puts the page back on ``presentation-poor/X1``.
"""

from __future__ import annotations

import copy
import json
import pathlib
from types import SimpleNamespace

import pytest

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawapply
from boardwise.engines import drawcompiler as dc
from boardwise.engines import pagecompiler as pc

import test_098_ic_periphery as e098
import test_543h3b_stated_text_lane as t3b

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPECS = ROOT / "blocklib" / "specs"
CH340 = "ch340_serial"
CH343_CIRCUIT = SPECS / "ch343_uart_534a.circuit.json"
CH343_LIBRARY = SPECS / "ch343_uart_v4.library.json"
PAGE_BOX = (0.0, 0.0, 1170.0, 825.0)

# .tmp_543n/agent_sample/ch340_ext.presentation.json, inlined: the sample's
# module is the whole serial circuit (the crystal is **not** split out), and the
# key set is the one the 543 line asks for.
CH340_543_OPT_IN = {
    "kind": "boardwise-presentation-spec",
    "specVersion": 1,
    "grammarRef": "ic-periphery",
    "textPlacement": "native-attr",
    "sidePreferences": {
        "input": "left", "output": "right", "load": "left",
        "power": "top", "gnd": "bottom",
    },
    "portRoles": {
        "VCC": "input", "TXD": "output", "RXD": "input",
        "D+": "load", "D-": "load",
    },
    "modules": [{
        "id": "serial",
        "parts": ["U1", "X1", "C1", "C2", "C3", "C4"],
        "role": "the USB-serial bridge with crystal and decoupling",
        "grammarRef": "ic-periphery",
        "core": "U1",
    }],
    "labelPolicy": {
        "local": "wire", "crossModule": "label", "highFanout": "label",
        "stub": "straight", "stubMin": 40, "rowModel": "centered",
    },
    "flagLeadLimit": 120,
    "partTexts": {"U1": "above", "X1": "above", "C3": "right", "C4": "right"},
    "gndClustering": {"radius": 100},
    "serviceLayout": {"pinGap": 30},
}


def _book(stem: str, library: str | None = None):
    raw = json.loads(
        (SPECS / f"{library or stem}.library.json").read_text(encoding="utf-8")
    )
    items = raw["profiles"] if isinstance(raw, dict) else raw
    return {p.symbol_ref: p for p in (SymbolProfile.from_dict(i) for i in items)}


def _compile_ch340(payload: dict):
    return dc.compile(
        CircuitSpec.load(SPECS / f"{CH340}.circuit.json"),
        PresentationSpec.from_dict(copy.deepcopy(payload)),
        _book(CH340),
    )


def _pin(plan, book, member: str) -> tuple[float, float]:
    from boardwise.core.geometry import transform_point

    part_id, _, token = member.partition(".")
    placed = plan.part(part_id)
    assert placed is not None, f"{member} is not placed"
    profile = book[placed.symbol_ref]
    pin = profile.pin(token)
    if pin is None:
        pin = next(item for item in profile.pins if item.name == token)
    return transform_point(
        pin.tip[0], pin.tip[1], rotation=placed.rotation, mirror=placed.mirror,
        ox=placed.x, oy=placed.y,
    )


def _module_context(circuit_path, payload: dict, module_id: str, library: str):
    book = drawapply.load_library(SPECS / f"{library}.library.json")
    circuit = CircuitSpec.load(circuit_path)
    presentation = PresentationSpec.from_dict(copy.deepcopy(payload))
    local_circuit, local_presentation = pc._module_view(
        circuit, presentation, presentation.module(module_id)
    )
    binding = dc.bind_grammar(local_circuit, local_presentation, book)
    return dc._prepare(
        local_circuit, local_presentation, binding, book, dc.CompileBudget(),
    ).context


# ------------------------------------------------ the row the grammar asked for


def test_the_whole_543_opt_in_compiles_and_keeps_the_crystal_row():
    """Full opt-in, crystal in its own module: one candidate, X1/C1 on one row."""
    result = _compile_ch340(CH340_543_OPT_IN)
    assert result.ok, result.render_failures()
    plan = result.candidates[0]
    x1 = plan.part("X1")
    c1 = plan.part("C1")
    assert x1 is not None and c1 is not None
    assert abs(x1.y - c1.y) <= 1e-6, (
        f"adjacent(X1, C1) parted rows: X1 ({x1.x}, {x1.y}), C1 ({c1.x}, {c1.y})"
    )
    assert abs(x1.x - c1.x) > 1e-6, "the pair collapsed onto one point"
    # The pair the grammar did not name keeps its baseline relation to the
    # crystal's anchor row; what may not move is the crystal cluster's own shape.
    # 543G-12b: the second load is now seated **on the crystal's own second row**
    # (its other foot, one symbol pitch away) instead of the host pin's row —
    # `_place_clock_bays` hangs it there so its value row cannot land back on the
    # first net's line. The relation asserted is the one that still holds: level
    # with one of the crystal's two feet, on its own point.
    book = _book(CH340)
    c2 = plan.part("C2")
    assert c2 is not None
    feet = {round(float(_pin(plan, book, f"X1.{number}")[1]), 6) for number in (1, 2)}
    assert round(float(_pin(plan, book, "C2.1")[1]), 6) in feet, (feet, c2)


def test_the_page_compiles_under_the_same_opt_in_set():
    result = pc.compile_page(
        CircuitSpec.load(SPECS / f"{CH340}.circuit.json"),
        PresentationSpec.from_dict(copy.deepcopy(CH340_543_OPT_IN)),
        _book(CH340),
        pc.PageCompileBudget(page_box=PAGE_BOX),
    )
    assert result.ok, result.render_failures()
    assert result.pages


def test_the_service_runs_are_still_the_stated_thirty():
    """543B's answer on this sample: C3→VCC(16), C4→V3(4), one straight leg."""
    result = _compile_ch340(CH340_543_OPT_IN)
    assert result.ok, result.render_failures()
    plan = result.candidates[0]
    book = _book(CH340)
    for service, host, net_id in (
        ("C3.1", "U1.16", "VCC"),
        ("C4.1", "U1.4", "V3"),
    ):
        here = _pin(plan, book, service)
        there = _pin(plan, book, host)
        distance = abs(here[0] - there[0]) + abs(here[1] - there[1])
        assert distance == 30.0, f"{service} → {host} is {distance}, not 30"
        assert here[0] == there[0] or here[1] == there[1], (
            f"{service} → {host} is not one orthogonal run: {here} {there}"
        )
        runs = [item for item in plan.segments if item.net == net_id]
        straight = [
            item for item in runs
            if len(item.points) == 2
            and {tuple(item.points[0]), tuple(item.points[1])} == {here, there}
        ]
        assert straight, (
            f"{service} → {host} is not one straight run between the two pins: "
            f"{[item.points for item in runs]}"
        )


# ------------------------------------------------------- what the guard reads


def test_the_guard_names_the_owner_the_grammar_ordered():
    ctx = _module_context(
        SPECS / f"{CH340}.circuit.json", CH340_543_OPT_IN, "serial", CH340,
    )
    assert dc._pair_bands(ctx) is True
    assert dc._declared_sibling_owners(ctx) == frozenset({"U1"})
    # And the bucket reading that would split them: different symbols, one pad.
    rungs = {
        part_id: dc._BranchRung(
            owner=ctx.slots[part_id].owner,
            direction=(-1.0, 0.0),
            anchor=(0.0, float(index)),
            base=60.0,
            step=60.0,
            shared=(0.0, 0.0),
            index=index,
        )
        for index, part_id in enumerate(("X1", "C1"))
    }
    buckets = dc._bay_buckets(["X1", "C1"], rungs, ctx)
    assert buckets == [["C1"], ["X1"]], buckets


def test_an_ordinary_pair_has_no_declared_order_and_keeps_one_band():
    """The CH343 CC pair: same symbol, two pads, nothing stated between them."""
    ctx = _module_context(
        CH343_CIRCUIT, copy.deepcopy(t3b.PAYLOAD), "usb_c", "ch343_uart_v4",
    )
    assert dc._pair_bands(ctx) is True
    assert dc._declared_sibling_owners(ctx) == frozenset()
    rungs = {
        part_id: dc._BranchRung(
            owner=ctx.slots[part_id].owner,
            direction=(-1.0, 0.0),
            anchor=(0.0, float(index) * 60.0),
            base=60.0,
            step=60.0,
            shared=(0.0, 0.0),
            index=index,
        )
        for index, part_id in enumerate(("R1", "R2"))
    }
    buckets = dc._bay_buckets(["R1", "R2"], rungs, ctx)
    assert buckets == [["R1", "R2"]], buckets


def test_two_branches_on_one_pad_still_take_two_seats():
    """543H-5 is not paid for with this fix: one pad, two parts, two seats."""
    spec = e098.circuit(
        [e098.part("U1", "SOIC-16-CORE", "CH340G"),
         e098.part("R1", "R0402", "5.1k"), e098.part("R2", "R0402", "5.1k")],
        [e098.net("VCC", "power", ["U1.16"]),
         e098.net("GND", "gnd", ["U1.1", "R1.2", "R2.2"]),
         e098.net("V3", "signal", ["U1.15", "R1.1", "R2.1"])],
    )
    presentation = PresentationSpec.from_dict({
        "grammarRef": "ic-periphery",
        "modules": [{"id": "m", "parts": ["U1", "R1", "R2"],
                     "role": "core with two pull-downs", "core": "U1"}],
        "textPlacement": "native-attr",
        "serviceLayout": {"pinGap": 30},
    })
    result = dc.compile(spec, presentation, e098.library(), dc.CompileBudget())
    assert result.ok, result.render_failures()
    for plan in result.candidates:
        r1 = plan.part("R1")
        r2 = plan.part("R2")
        assert (r1.x, r1.y) != (r2.x, r2.y), "two branches share one origin"


def test_the_guard_is_what_keeps_the_row(monkeypatch):
    """Negative control: with the guard answering nothing, the page is refused.

    This is the measured defect itself (``presentation-poor/X1`` on all seven
    variants), kept as a test so the guard cannot be dropped as "it now happens
    to work": the fix must be the reading, not the sample.
    """
    monkeypatch.setattr(dc, "_declared_sibling_owners", lambda ctx: frozenset())
    # …and with 543G-12b's bay off as well: on a bay-shaped document the crystal
    # cluster is now seated from its host pins, so what the guard alone answers
    # is only visible on the ladder.
    monkeypatch.setattr(dc, "_place_clock_bays", lambda *args, **kwargs: frozenset())
    result = _compile_ch340(CH340_543_OPT_IN)
    assert not result.ok
    assert not result.candidates
    assert any(
        failure.category == "presentation-poor" and failure.subject == "X1"
        for failure in result.failures
    ), result.render_failures()


# ------------------------------------------- the guard, read on a minimal context


def _slot(part_id: str, kind: str, owner: str = ""):
    role = "shunt" if kind == "branch" else ("core" if kind == "chain" else "")
    return dc._Slot(
        part_id=part_id, role=role, kind=kind, axis="x", rank=0, owner=owner,
    )


def _constraint(subject: str, obj: str):
    return SimpleNamespace(kind="adjacent", subject=subject, object=obj)


def _guard_ctx(slots, constraints):
    """Exactly what `_declared_sibling_owners` reads, and nothing else."""
    return SimpleNamespace(
        slots={slot.part_id: slot for slot in slots},
        binding=SimpleNamespace(constraints=list(constraints)),
    )


def test_a_relation_between_two_branches_of_one_owner_declares_it():
    """Clause ①: the pair the guard exists for."""
    ctx = _guard_ctx(
        [_slot("U1", "chain"), _slot("C1", "branch", "U1"),
         _slot("C2", "branch", "U1")],
        [_constraint("C1", "C2")],
    )
    assert dc._declared_sibling_owners(ctx) == frozenset({"U1"})


def test_a_relation_to_the_core_is_not_an_order_between_siblings():
    """Clause ②: `near(C1, U1)` is every shunt's statement, not an order.

    The core slot is deliberately given the **same** owner string: in the
    shipped contexts a chain part's owner is empty, so a version that checked
    only the constraint's subject would still answer ``{U1}`` here and nothing
    on a real page would notice. The guard's contract is "both ends are
    branches"; this is the stub that says so.
    """
    ctx = _guard_ctx(
        [_slot("U1", "chain", "U1"), _slot("C1", "branch", "U1")],
        [_constraint("C1", "U1")],
    )
    assert dc._declared_sibling_owners(ctx) == frozenset()


def test_branches_of_two_owners_are_not_siblings():
    """Clause ③: one band per owner — two owners are two staircases."""
    ctx = _guard_ctx(
        [_slot("U1", "chain"), _slot("U2", "chain"),
         _slot("C1", "branch", "U1"), _slot("C2", "branch", "U2")],
        [_constraint("C1", "C2")],
    )
    assert dc._declared_sibling_owners(ctx) == frozenset()


def test_a_free_part_is_not_a_branch_either():
    """The third slot kind: a free part declares no sibling order."""
    ctx = _guard_ctx(
        [_slot("R1", "free", "U1"), _slot("C1", "branch", "U1")],
        [_constraint("C1", "R1")],
    )
    assert dc._declared_sibling_owners(ctx) == frozenset()
