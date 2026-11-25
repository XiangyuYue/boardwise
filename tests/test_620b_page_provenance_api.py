"""620B: `PageLayoutPlan.provenance_sha256()` is the page's own seal.

590's unified contract asks any plan document for `provenance_sha256()`; only
`LayoutPlan` answered, so a page raised AttributeError. The compatibility alias
added here must delegate to `page_provenance_sha256()` and nothing else: the
page's seal is page geometry + route under `PAGE_PROVENANCE_DOMAIN`, never the
nested drawing's seal and never the drawing domain.
"""

from __future__ import annotations

import json

from boardwise.core.layoutplan import (
    LayoutPart,
    LayoutPlan,
    LayoutSegment,
    LayoutSource,
    ROUTE_AUTOMATIC,
    ROUTE_REFERENCE_REPLAY,
    provenance_sha256 as plan_seal,
)
from boardwise.core.pagelayoutplan import (
    PAGE_PROVENANCE_DOMAIN,
    PageLayoutPlan,
    PageModule,
    PagePort,
)

HASH = "a" * 64


def _plan() -> LayoutPlan:
    return LayoutPlan(
        source=LayoutSource(circuit_sha256=HASH, presentation_sha256=HASH),
        parts=[
            LayoutPart(part_id="R1", reference="R101", symbol_ref="R0402",
                       symbol_hash=HASH, x=0.0, y=0.0),
            LayoutPart(part_id="R2", reference="R102", symbol_ref="R0402",
                       symbol_hash=HASH, x=0.0, y=-140.0),
        ],
        segments=[LayoutSegment(net="N1", points=[(0.0, 0.0), (10.0, 0.0)])],
    )


def _page() -> PageLayoutPlan:
    return PageLayoutPlan(
        plan=_plan(),
        modules=[PageModule(
            id="m1", grammar_ref="ic-periphery", parts=["R1", "R2"],
            origin=(0.0, 0.0), frame=(0.0, 0.0, 100.0, 100.0),
            internal_geometry_sha256=HASH,
            ports=[PagePort(module="m1", net="N1", kind="label", x=0.0, y=0.0)],
        )],
        page_box=(0.0, 0.0, 300.0, 200.0),
    )


def _strip_590(body: dict) -> dict:
    """The bytes a pre-590 compiler wrote: route/seal off, nested plan too."""
    document = dict(body)
    document.pop("route", None)
    document.pop("provenanceSha256", None)
    if "plan" in document:
        document["plan"] = dict(document["plan"])
        document["plan"].pop("route", None)
        document["plan"].pop("provenanceSha256", None)
    return document


# ------------------------------------------------------- the alias's identity


def test_the_alias_is_the_page_seal_computed_independently() -> None:
    page = _page()
    assert page.provenance_sha256() == page.page_provenance_sha256()
    assert page.provenance_sha256() == plan_seal(
        page.route, page.page_geometry_sha256(), PAGE_PROVENANCE_DOMAIN
    )


def test_the_alias_does_not_borrow_the_nested_plans_seal_or_domain() -> None:
    page = _page()
    # The page's own picture: not the embedded drawing's digest.
    assert page.provenance_sha256() != page.plan.provenance_sha256()
    # And the same page digest under the drawing's domain is a different value,
    # so the seal cannot be passed off as a `LayoutPlan` seal.
    assert page.provenance_sha256() != plan_seal(
        page.route, page.page_geometry_sha256()
    )
    assert PAGE_PROVENANCE_DOMAIN != "boardwise.layout-plan-provenance/1"


def test_the_alias_tracks_route_and_page_geometry() -> None:
    page = _page()
    before = page.provenance_sha256()
    page.modules[0].frame = (0.0, 0.0, 110.0, 100.0)
    assert page.provenance_sha256() != before
    assert page.provenance_sha256() == plan_seal(
        page.route, page.page_geometry_sha256(), PAGE_PROVENANCE_DOMAIN
    )
    replay = PageLayoutPlan(plan=page.plan, route=ROUTE_REFERENCE_REPLAY)
    assert replay.provenance_sha256() == replay.page_provenance_sha256()
    assert replay.provenance_sha256() != page.provenance_sha256()


# ------------------------------------------------------------- two consumers


def _seal_of(document: object) -> str:
    """What a 590-era consumer does to a plan document of either kind."""
    return document.provenance_sha256()  # type: ignore[attr-defined]


def test_both_plan_kinds_answer_the_same_contract_name() -> None:
    plan, page = _plan(), _page()
    assert _seal_of(plan) == plan.provenance_sha256()
    assert _seal_of(page) == page.page_provenance_sha256()
    assert _seal_of(plan) != _seal_of(page)
    assert plan.route == page.route == ROUTE_AUTOMATIC
    # LayoutPlan's own behaviour is untouched: same helper, same default domain.
    assert plan.provenance_sha256() == plan_seal(plan.route, plan.geometry_sha256())


# ------------------------------------------------------------- the JSON face


def test_to_jsonable_states_the_alias_value() -> None:
    page = _page()
    body = page.to_jsonable()
    assert body["route"] == ROUTE_AUTOMATIC
    assert body["provenanceSha256"] == page.provenance_sha256()
    assert body["provenanceSha256"] == page.page_provenance_sha256()


def test_an_automatic_page_round_trips_with_the_same_seal() -> None:
    page = _page()
    body = page.to_jsonable()
    loaded = PageLayoutPlan.from_dict(body)
    assert loaded.provenance_sha256() == page.provenance_sha256()
    assert loaded.to_jsonable() == body


def test_a_pre_590_page_gains_no_key_and_still_answers() -> None:
    body = _page().to_jsonable()
    old = _strip_590(body)
    assert "route" not in old and "provenanceSha256" not in old
    document = PageLayoutPlan.from_dict(old)
    assert document.route_declared is False
    assert document.route == ROUTE_REFERENCE_REPLAY
    assert document.provenance_sha256() == document.page_provenance_sha256()
    reemitted = document.to_jsonable()
    assert "route" not in reemitted and "provenanceSha256" not in reemitted
    # Byte-level: the old document is not rewritten by asking for its seal.
    dumped = json.dumps(reemitted, ensure_ascii=False, indent=2) + "\n"
    source = json.dumps(_strip_590(_page().to_jsonable()), ensure_ascii=False, indent=2)
    assert json.loads(dumped) == json.loads(source)
