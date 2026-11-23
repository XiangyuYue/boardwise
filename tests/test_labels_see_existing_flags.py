"""548?-flags-first: a label must see the flag ink that is already on the page.

Causal item: the per-net loop in `drawcompiler` walked `_net_order` — promised
trunks first, then the big nets — and a **flag** net could therefore be drawn
after the label net beside it. The label chose its box with `avoid=[]`
(measured: `.tmp_lock_p1/probe-label-flag-order.log`), then `_place_flag` put
the flag's glyph + name row exactly there, and the readability gate refused the
page with `text-overlap`.

The fix is an order, not a second collision model: `_flag_first_order` puts the
flag-style expressions first and keeps every other expression in its old
relative order. These tests pin the three facts that fix has to make true:

* the flag is processed before the label (recorded from the real primitives,
  not from the helper's return value alone);
* the `avoid` the label is placed with contains the flag's ink box — measured
  with the compiler's own `_flag_box` ruler, the same one `_flag_ink_rows`
  uses;
* the finished plan has no text overlap, checked by the independent
  readability gate, not by this file's own arithmetic.

A second test pins the other half: an input with no flag expression keeps its
old order and its old geometry byte for byte.
"""

from __future__ import annotations

from dataclasses import replace

import test_053b_drawcompiler as b053
import test_098_ic_periphery as b098
from boardwise.engines import drawcompiler as dc
from boardwise.engines import readability

#: The single-pin signal net: a name at one pin, nothing to wire it to.
LABEL_NET = "AAA_SIG"
#: The single-pin rail: its expression is a flag, and the library carries
#: `PWR-<net>` for it (added below, so the net does not fall back to a wire).
FLAG_NET = "ZZZ_PWR"
#: The two core pins both hang off the **left** side, so a label on one and a
#: flag on the other compete for the same column of text.
LABEL_PIN = "5"
FLAG_PIN = "4"


def _book():
    return b098.library(**{f"PWR-{FLAG_NET}": b053.flag(f"PWR-{FLAG_NET}")})


def _flag_and_label_circuit():
    """One core, one decoupling cap (the grammar needs the group), one label
    net and one flag net — both single-pin, on adjacent core pins."""
    return b053.circuit(
        [
            b053.part("U1", "SOIC-16-CORE", "CH340G"),
            b053.part("C3", "C0402", "100nF"),
        ],
        [
            b053.net("VIN", "power", ["U1.16", "C3.1"]),
            b053.net("GND", "gnd", ["U1.1", "C3.2"]),
            b053.net(LABEL_NET, "signal", [f"U1.{LABEL_PIN}"]),
            b053.net(FLAG_NET, "power", [f"U1.{FLAG_PIN}"]),
        ],
    )


def _trace(monkeypatch):
    """Record what the two existing primitives are asked to do, with the caller.

    The caller matters: `_reserve_label_stubs` already places *trial* labels
    before the loop, and those must not be read as the loop's own choice.
    """
    events: list[tuple[str, str, str]] = []
    avoid_by_call: dict[str, list] = {}

    real_place_flag = dc._place_flag

    def place_flag(*args, **kwargs):
        net_id = args[0] if args else kwargs.get("net_id", "")
        events.append(("flag", net_id, "loop"))
        return real_place_flag(*args, **kwargs)

    real_label_for = dc._label_for

    def label_for(ctx, net_id, part_id, token, point, placed, occupied,
                  *args, **kwargs):
        avoid = kwargs.get("avoid", args[1] if len(args) > 1 else ())
        caller = "?"
        import sys
        frame = sys._getframe(1)
        if frame is not None:
            caller = frame.f_code.co_name
        events.append(("label", net_id, caller))
        avoid_by_call[(net_id, caller)] = list(avoid)
        return real_label_for(
            ctx, net_id, part_id, token, point, placed, occupied, *args, **kwargs,
        )

    monkeypatch.setattr(dc, "_place_flag", place_flag)
    monkeypatch.setattr(dc, "_label_for", label_for)
    return events, avoid_by_call


def _flag_ink(plan, book):
    symbol = next(s for s in plan.power_symbols if s.net == FLAG_NET)
    profile = book[symbol.symbol_ref]
    # The compiler's own ruler, margin 0 — exactly `_flag_ink_rows`.
    return dc._flag_box(
        profile, symbol.rotation, (symbol.x, symbol.y), symbol.net, margin=0.0,
    )


def test_a_label_is_placed_after_the_flag_beside_it_and_avoids_its_ink(
    monkeypatch,
):
    book = _book()
    circuit = _flag_and_label_circuit()
    sheet = replace(b098.sample_presentation(
        declared=False, core=None, module_parts=(), signals=(), port_roles={},
    ), grammar_ref="mixed-island")
    events, avoid_by_call = _trace(monkeypatch)
    result = dc.compile(circuit, sheet, book)

    assert result.ok, result.render_failures()

    # 1) the flag expression is drawn before the label expression. The caller is
    #    the per-net loop itself (`_build_one_variant`); the pre-loop trial
    #    labels of `_reserve_label_stubs` are a different caller and are
    #    deliberately not what this line reads.
    flag_at = next(
        index for index, (kind, net, _c) in enumerate(events)
        if kind == "flag" and net == FLAG_NET
    )
    label_at = next(
        index for index, (kind, net, caller) in enumerate(events)
        if kind == "label" and net == LABEL_NET and caller == "_build_one_variant"
    )
    assert flag_at < label_at, events

    plan = result.candidates[0]
    ink = _flag_ink(plan, book)

    # 2) the label's ladder saw that ink in its `avoid` list — the flag is not
    #    "future" to the label any more.
    avoid = avoid_by_call[(LABEL_NET, "_build_one_variant")]
    assert any(box == ink for box in avoid), (avoid, ink)

    # 3) the landed label box is clear of the flag ink, and the independent
    #    gate agrees there is no text overlap on the page.
    label = next(item for item in plan.labels if item.net == LABEL_NET)
    assert not dc._overlaps(label.bbox, ink), (label.bbox, ink)
    checked = readability.check(plan, circuit, sheet, book)
    assert checked.hard_violations == [], [
        item.render() for item in checked.hard_violations
    ]


def _fingerprint(plan):
    return (
        tuple((label.net, label.bbox) for label in plan.labels),
        tuple(
            (symbol.net, symbol.x, symbol.y, symbol.rotation)
            for symbol in plan.power_symbols
        ),
        tuple((segment.net, tuple(segment.points)) for segment in plan.segments),
    )


def test_an_input_without_flag_expressions_keeps_its_order_and_geometry(
    monkeypatch,
):
    """No flag expression = the partition is the identity: same trace, same plan."""
    circuit, sheet = b098.minimal_group()
    book = b098.library()

    # The helper itself: flag styles move to the front, everything else keeps
    # its relative order.
    class _Style:
        def __init__(self, style):
            self.style = style

    expressions = {"A": _Style("label"), "B": _Style("flag"), "C": _Style("wire")}
    assert dc._flag_first_order(expressions, ["A", "B", "C"]) == ["B", "A", "C"]
    no_flags = {"A": _Style("wire"), "B": _Style("label")}
    assert dc._flag_first_order(no_flags, ["B", "A"]) == ["B", "A"]

    result = dc.compile(circuit, sheet, book, dc.CompileBudget())
    assert result.ok, result.render_failures()

    real_order = dc._flag_first_order
    monkeypatch.setattr(
        dc, "_flag_first_order", lambda expressions, order: list(order),
    )
    try:
        baseline = dc.compile(circuit, sheet, book, dc.CompileBudget())
    finally:
        monkeypatch.setattr(dc, "_flag_first_order", real_order)

    assert baseline.ok, baseline.render_failures()
    assert _fingerprint(baseline.candidates[0]) == _fingerprint(result.candidates[0])


def _rail_and_label_circuit():
    """A **multi-pin** rail and ground (wire-style) plus one signal at a pad.

    This is the shape the real HMI module has: `+3V3`/`GND` each reach two pads
    there, so their expression is `wire`, and their flag is placed by the
    post-loop `_rail_flag`, never by the net loop. `AAA_SIG_LONG` is a one-pad
    signal, i.e. a label placed *inside* the loop — the label the flag used to
    land on.
    """
    return b053.circuit(
        [
            b053.part("U1", "SOIC-16-CORE", "CH340G"),
            b053.part("C3", "C0402", "100nF"),
        ],
        [
            b053.net("VIN", "power", ["U1.16", "C3.1"]),
            b053.net("GND", "gnd", ["U1.1", "C3.2"]),
            b053.net("AAA_SIG_LONG", "signal", ["U1.5"]),
        ],
    )


def _contains(outer, inner):
    return (outer[0] <= inner[0] and outer[1] <= inner[1]
            and outer[2] >= inner[2] and outer[3] >= inner[3])


def test_a_wire_style_rail_flag_is_avoided_before_it_is_placed(monkeypatch):
    """The rail's flag is reserved before the loop and drawn after it.

    Ordering the loop cannot help here (measured on the HMI module: the symbol
    comes from `_rail_flag` after the last net), so the label has to read the
    **reserved seat** — the flag's own `_flag_box` — instead of waiting for a
    `symbols` list it will never see. One label ladder, one ruler.
    """
    book = b098.library()
    circuit = _rail_and_label_circuit()
    sheet = replace(b098.sample_presentation(
        declared=False, core=None, module_parts=(), signals=(), port_roles={},
    ), grammar_ref="mixed-island")
    events, avoid_by_call = _trace(monkeypatch)
    result = dc.compile(circuit, sheet, book)
    assert result.ok, result.render_failures()

    # The mechanism the fix has to work around, pinned so it is not assumed
    # away: the label is placed in the loop, the rail flag only afterwards.
    label_at = next(
        index for index, (kind, net, caller) in enumerate(events)
        if kind == "label" and net == "AAA_SIG_LONG"
        and caller == "_build_one_variant"
    )
    flag_at = next(
        index for index, (kind, net, _c) in enumerate(events)
        if kind == "flag" and net == "VIN"
    )
    assert label_at < flag_at, events

    plan = result.candidates[0]
    symbol = next(item for item in plan.power_symbols if item.net == "VIN")
    ink = dc._flag_box(
        book[symbol.symbol_ref], symbol.rotation, (symbol.x, symbol.y), "VIN",
        margin=0.0,
    )

    # The label's own ladder already avoided the reserved seat.
    avoid = avoid_by_call[("AAA_SIG_LONG", "_build_one_variant")]
    assert avoid, "the label was placed with an empty avoid list"
    assert any(_contains(box, ink) for box in avoid), (avoid, ink)

    label = next(item for item in plan.labels if item.net == "AAA_SIG_LONG")
    assert not dc._overlaps(label.bbox, ink), (label.bbox, ink)
    checked = readability.check(plan, circuit, sheet, book)
    assert checked.hard_violations == [], [
        item.render() for item in checked.hard_violations
    ]
