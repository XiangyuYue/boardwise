"""548P-scope: `flagShareGroups` groups the nets it names, and only those.

The bug this pins: a GND-only declaration used to make the **page-level**
`_flag_grouping` true, so an undeclared high-fan-out rail lost its per-pin
flags (053 sec.7) and became wire-style, and `_apply_flag_groups` grouped nets
nobody declared. The baseline of a page with no such key is
`_flag_grouping_baseline` (a `panelGroups` declaration, or `native-attr` +
`serviceLayout`), never "group everything".

Every assertion below is driven through the production consumers
(`_expression_style`, `_apply_flag_groups` via `_build_candidate`, the reach
audit) rather than reading the predicate alone, so replacing
`_flag_grouping_for_net` with the old global `_flag_grouping(ctx)` turns this
file red.
"""

from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from boardwise.core.layoutplan import ROUTE_AUTOMATIC
from boardwise.core.presentationspec import PresentationSpec
from boardwise.engines import drawcompiler as dc
from test_548p64_pre_group_lanes import _lcd_case

#: canonical JSON of the built plan for the plain page with no declaration —
#: captured from the pre-change compiler and byte-identical after the change.
#: Since 590 the document states `route`/`provenanceSha256`, neither of which is
#: part of `geometry_json`: the pin is compared against the projection with the
#: two keys taken off, and the keys are asserted separately in the test.
PLAIN_UNDECLARED_SHA = (
    "0f1a5299d9a5a2afb547538bee052ead4f6f43c472abe26d68f47c3fb420322f"
)

_ROUTE_KEYS = ("route", "provenanceSha256")


def _document(base, *, declared=False, plain=False):
    document = json.loads(json.dumps(base))
    if plain:
        document.pop("textPlacement", None)
        document.pop("serviceLayout", None)
        policy = dict(document.get("labelPolicy") or {})
        policy.pop("stubLaneReserve", None)
        document["labelPolicy"] = policy
    if declared:
        document["flagShareGroups"] = [
            {"net": "GND", "groups": [["J1.2", "C4.2"]]}
        ]
    return document


def _rebuild(base_ctx, document):
    """The lcd circuit/book with a different presentation, ready to build."""
    spec = PresentationSpec.from_dict(document)
    circuit, book = base_ctx.circuit, base_ctx.book
    binding = dc.bind_grammar(circuit, spec, book)
    binding = dc._with_series_arms(binding, spec)
    binding = dc._with_panel_groups(binding, spec, circuit)
    binding = dc._with_service_groups(binding, spec, circuit, book)
    assert binding.ok, binding
    prepared = dc._prepare(circuit, spec, binding, book, base_ctx.budget)
    assert prepared.context is not None and not prepared.failures
    return prepared.context


def _case(*, declared=False):
    base_ctx, *_ = _lcd_case()
    document = _document(
        base_ctx.presentation.to_jsonable(), declared=declared, plain=True,
    )
    return _rebuild(base_ctx, document)


def _pre_590_sha(built) -> str:
    """The pinned sha is the pre-590 document: compare its projection.

    590 adds exactly `route`/`provenanceSha256`; neither is inside
    `geometry_json`. A third moving key is a geometry change and the pin must not
    absorb it. The new keys are asserted separately by the caller.
    """
    body = built.plan.to_jsonable()
    projection = {key: value for key, value in body.items() if key not in _ROUTE_KEYS}
    assert set(body) - set(projection) == set(_ROUTE_KEYS), (
        "590 must add exactly `route` and `provenanceSha256`; any other key is a "
        "changed field hiding behind the new ones"
    )
    payload = json.dumps(projection, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _first_built(ctx):
    """First candidate the production ladder accepts, not a hard-coded rung."""
    for index, variant in enumerate(dc._variants(ctx)):
        built, failure, _notes = dc._build_candidate(ctx, variant)
        if built is not None:
            return index, built
    raise AssertionError(f"no candidate was accepted: {failure}")


def _net_geometry(built, net):
    """The exact geometry of one net, excluding unrelated GND-only changes."""
    plan = built.plan.to_jsonable()
    return {
        key: [row for row in plan.get(key, []) if row.get("net") == net]
        for key in ("segments", "powerSymbols", "labels")
    }


def test_gnd_only_declaration_keeps_an_undeclared_rail_on_per_pin_flags():
    declared = _case(declared=True)
    undeclared = _case(declared=False)

    # `_expression_style` is the consumer that decides the style: a rail above
    # the high-fan-out limit is stated per pin unless *its own* net opted in.
    count = dc.HIGH_FANOUT + 1
    style, _why = dc._expression_style(
        declared, "3V3", "power", count, set(),
    )
    baseline, _why = dc._expression_style(
        undeclared, "3V3", "power", count, set(),
    )

    assert baseline == "flag"
    assert style == "flag", (
        "a GND-only flagShareGroups declaration must not turn the undeclared "
        "3V3 rail into wire-style"
    )
    assert dc._flag_grouping_for_net(declared, "3V3") is False
    assert dc._flag_grouping_for_net(declared, "GND") is True


def test_apply_flag_groups_does_not_process_an_undeclared_net(monkeypatch):
    ctx = _case(declared=True)
    grouped_nets: list[str] = []
    original = dc._flag_groups

    def record(context, expression, cls, router, *args, **kwargs):
        grouped_nets.append(expression.net)
        return original(context, expression, cls, router, *args, **kwargs)

    monkeypatch.setattr(dc, "_flag_groups", record)
    _index, built = _first_built(ctx)

    assert built is not None
    assert "GND" in grouped_nets
    assert "3V3" not in grouped_nets, (
        "the undeclared 3V3 rail entered the grouping pass a declaration for "
        "GND must not open"
    )


def test_undeclared_net_keeps_the_native_grouping_baseline():
    base_ctx, *_ = _lcd_case()
    document = base_ctx.presentation.to_jsonable()
    native = _rebuild(base_ctx, _document(document))
    declared = _rebuild(base_ctx, _document(document, declared=True))

    assert dc._flag_grouping(native) is True
    assert dc._flag_grouping_for_net(native, "3V3") is True
    # A declaration for one net does not narrow the page's own baseline.
    assert dc._flag_grouping_for_net(declared, "3V3") is True
    assert dc._flag_grouping_for_net(declared, "GND") is True


def test_panel_groups_remain_a_page_wide_baseline():
    presentation = SimpleNamespace(
        flag_share_groups=(),
        panel_groups=(object(),),
        text_placement="",
        service_layout=None,
    )
    ctx = SimpleNamespace(presentation=presentation)

    assert dc._flag_grouping_for_net(ctx, "3V3") is True


def test_a_page_with_no_declaration_keeps_its_bytes():
    ctx = _case(declared=False)
    built, failure, _notes = dc._build_candidate(ctx, dc._variants(ctx)[0])

    assert built is not None, failure
    assert dc._flag_grouping(ctx) is False
    assert _pre_590_sha(built) == PLAIN_UNDECLARED_SHA, (
        "the pre-590 fields and coordinates must be byte-identical to the pin; "
        "only `route`/`provenanceSha256` may be new"
    )
    body = built.plan.to_jsonable()
    assert body["route"] == ROUTE_AUTOMATIC and built.plan.route_declared is True
    assert body["provenanceSha256"] == built.plan.provenance_sha256(), (
        "the seal is this plan's own route + geometry digest"
    )


def test_a_gnd_only_declaration_keeps_the_undeclared_rail_geometry():
    undeclared_ctx = _case(declared=False)
    declared_ctx = _case(declared=True)
    # Candidate 0 is now rejected by an unrelated LCD_DC/GND text overlap. The
    # scope invariant belongs to candidate 1, not to that ladder ordering: the
    # same rung on both pages keeps the undeclared rail byte-for-byte identical.
    undeclared, undeclared_failure, _notes = dc._build_candidate(
        undeclared_ctx, dc._variants(undeclared_ctx)[1],
    )
    declared, declared_failure, _notes = dc._build_candidate(
        declared_ctx, dc._variants(declared_ctx)[1],
    )

    assert undeclared is not None, undeclared_failure
    assert declared is not None, declared_failure
    assert dc._flag_grouping(declared_ctx) is True
    assert _net_geometry(undeclared, "3V3") == _net_geometry(declared, "3V3")


def test_declared_net_reach_audit_is_not_relaxed(monkeypatch):
    ctx = _case(declared=True)
    monkeypatch.setattr(dc, "_flag_group_reach", lambda _context: 1.0)

    built, failure, _notes = dc._build_candidate(ctx, dc._variants(ctx)[0])

    assert built is None
    assert failure is not None
    assert failure.subject == "$.flagShareGroups[GND]"
