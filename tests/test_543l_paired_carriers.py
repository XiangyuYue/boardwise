"""543L: a mirrored D+/D- pin pair is drawn at **one** carrier length.

岳's review (P37) measured the CH343 sheet's reversible data pins as `A6`/`A7`
40/40, `U1.5`/`U1.6` 40/40 — and `B6`/`B7` 60/55. The two long runs are one
mirrored pair of the same `localLabelObligations` entry, so the odd 5 units read
as an accident: the pass walked `B6`'s ladder to 60, then walked `B7`'s on its
own and stopped one rung earlier where the 60-unit run met `A6`'s already
reserved row.

The rule pinned here (`drawcompiler._local_label_pin_pairs` +
`_reserve_paired_carriers`):

* the pair is read from the **placed geometry** — same part, same escape
  direction, mirrored offsets from the body centre — never from a net name, a
  part name or a literal coordinate;
* one length is offered to **both** pins and both runs and both name rows are
  measured against the same picture; only the first length legal for both is
  taken, so neither pin is placed first and the other matched afterwards;
* a pair with no common legal length is a named ``layout-unsat`` for the pair,
  never two different lengths.

The A/B groups are not forced to agree with each other: this page's A pair keeps
its 40 (5 + the 35 the native stub adds) and the B pair settles on 60/60.

`drawapply.module_plan` runs the 543I gate (`native_carrier_problems` /
`_native_carrier_cover`) on the page it builds and raises when any visible name
is off its own conductor, so a plan that builds here has none.
"""

from __future__ import annotations

import copy
import json
import pathlib

from boardwise.core.circuitspec import CircuitSpec
from boardwise.core.presentationspec import PresentationSpec
from boardwise.core.symbolprofile import SymbolProfile
from boardwise.engines import drawapply
from boardwise.engines import drawcompiler as dc
from boardwise.engines import pagecompiler as pc

import test_543h3b_stated_text_lane as t3b

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPECS = ROOT / "blocklib" / "specs"
CIRCUIT = CircuitSpec.load(SPECS / "ch343_uart_534a.circuit.json")
LIBRARY = {
    item["symbolRef"]: SymbolProfile.from_dict(item)
    for item in json.loads(
        (SPECS / "ch343_uart_v4.library.json").read_text(encoding="utf-8")
    )["profiles"]
}
PAGE_BOX = (0.0, 0.0, 1170.0, 825.0)


def _presentation() -> PresentationSpec:
    return PresentationSpec.from_dict(t3b.PAYLOAD)


def _compile():
    result = pc.compile_page(
        CIRCUIT, _presentation(), LIBRARY,
        pc.PageCompileBudget(page_box=PAGE_BOX),
    )
    assert result.ok, result.render_failures()
    return result


def _runs(page, presentation) -> dict[tuple[str, str], list[tuple[float, float]]]:
    """Every D+/D- carrier of one candidate page, keyed by (net, from_pin)."""
    plan = drawapply.module_plan(
        page.plan, CIRCUIT, presentation, LIBRARY,
        candidate_index=0, label_stubs=True, page_box=PAGE_BOX,
        module_label="page " + "+".join(module.id for module in page.modules),
    )
    out: dict[tuple[str, str], list[tuple[float, float]]] = {}
    for wire in plan.change.draw_wires:
        net = str(wire.net)
        if net not in ("D+", "D-"):
            continue
        out[(net, str(wire.from_pin))] = [
            (round(float(point[0]), 3), round(float(point[1]), 3))
            for point in wire.points
        ]
    return out


def _length(points) -> float:
    return sum(
        abs(second[0] - first[0]) + abs(second[1] - first[1])
        for first, second in zip(points, points[1:])
    )


def test_the_pair_is_read_from_the_placed_geometry(monkeypatch):
    """`A6` pairs with `A7` and `B6` with `B7`, and nothing tells the rule so."""
    seen: list[dict] = []
    original = dc._local_label_pin_pairs

    def record(ctx, placed, nets, expressions):
        pairs = original(ctx, placed, nets, expressions)
        seen.append(dict(pairs))
        return pairs

    monkeypatch.setattr(dc, "_local_label_pin_pairs", record)
    _compile()

    assert seen, "no two-net obligation was paired"
    pairs = next((item for item in seen if len(item) == 4), None)
    assert pairs is not None, seen
    # the relation is symmetric and no pin is in two pairs
    for point, partner in pairs.items():
        assert pairs[partner[2]][2] == point
    mirrored = [
        (point, partner[2])
        for point, partner in pairs.items()
        if point < partner[2]
    ]
    assert len(mirrored) == 2, mirrored
    for point, partner in mirrored:
        # one side of one part: same escape column, mirrored rows
        assert point[0] == partner[0], (point, partner)
        assert point[1] != partner[1], (point, partner)
    centres = {(point[1] + partner[1]) / 2.0 for point, partner in mirrored}
    assert len(centres) == 1, mirrored  # both pairs mirror about the body centre
    pitches = sorted(
        abs(point[1] - partner[1]) for point, partner in mirrored
    )
    assert pitches == [10.0, 30.0], pitches


def test_the_pair_is_drawn_at_one_length():
    """`B6` and `B7` share one run length; `A6`/`A7` and `U1` keep theirs."""
    result = _compile()
    presentation = _presentation()
    expected = {
        ("D+", "USB1.A6"): 40.0,
        ("D-", "USB1.A7"): 40.0,
        ("D+", "USB1.B6"): 60.0,
        ("D-", "USB1.B7"): 60.0,
        ("D+", "U1.5"): 40.0,
        ("D-", "U1.6"): 40.0,
    }
    for index, page in enumerate(result.pages):
        runs = _runs(page, presentation)
        lengths = {key: _length(points) for key, points in runs.items()}
        for key, value in expected.items():
            assert key in lengths, (index, key, sorted(lengths))
            assert lengths[key] == value, (index, key, lengths[key])
        # the reading statement itself: the pair and U1 are equal by construction
        assert lengths[("D+", "USB1.B6")] == lengths[("D-", "USB1.B7")]
        assert lengths[("D+", "USB1.A6")] == lengths[("D-", "USB1.A7")]
        assert lengths[("D+", "U1.5")] == lengths[("D-", "U1.6")]
        # the mirrored groups need not agree with each other
        assert lengths[("D+", "USB1.A6")] != lengths[("D+", "USB1.B6")]


def test_the_pair_is_measured_together(monkeypatch):
    """Both pins are offered the same lengths — one decision, not two."""
    tried: dict[tuple[str, tuple[float, float]], set[float]] = {}
    original = dc._local_label_candidate

    def record(ctx, net_id, point, direction, path, router, tips, taken, rows):
        tried.setdefault((net_id, tuple(point)), set()).add(
            round(_length([path[0], path[-1]]), 3)
        )
        return original(
            ctx, net_id, point, direction, path, router, tips, taken, rows,
        )

    monkeypatch.setattr(dc, "_local_label_candidate", record)
    _compile()

    def longest(net: str) -> set[float]:
        lengths = [value for key, value in tried.items() if key[0] == net]
        assert lengths, net
        return max(lengths, key=len)

    # `B6`/`B7` are the pins that had to escalate; `A6`/`A7` accept the first rung.
    assert longest("D+") == longest("D-"), (longest("D+"), longest("D-"))
    assert 60.0 in longest("D+") and 55.0 in longest("D+")


def test_a_document_that_leaves_the_stub_auto_is_not_paired():
    """543M: the joint length belongs to the **straight-stub** contract only.

    V45 (native-attr, no `serviceLayout`) and 543f2's pre-fix page measured the
    cost of pairing unconditionally: `B7` went to 60, that lane took the room a
    ground flag needed, and the page had no seat left. A document that leaves
    `labelPolicy.stub` to `auto` never stated a straight carrier, so it keeps the
    per-pin ladder — `B6` 60, `B7` 55, exactly as before 543L.
    """
    payload = copy.deepcopy(t3b.PAYLOAD)
    payload["labelPolicy"]["stub"] = "auto"
    presentation = PresentationSpec.from_dict(payload)
    result = pc.compile_page(
        CIRCUIT, presentation, LIBRARY,
        pc.PageCompileBudget(page_box=PAGE_BOX),
    )
    assert result.ok, result.render_failures()
    lengths = {
        key: _length(points)
        for key, points in _runs(result.pages[0], presentation).items()
    }
    assert lengths[("D+", "USB1.B6")] == 60.0, lengths
    assert lengths[("D-", "USB1.B7")] == 55.0, lengths
    assert lengths[("D+", "USB1.A6")] == 40.0, lengths
    assert lengths[("D-", "USB1.A7")] == 40.0, lengths
