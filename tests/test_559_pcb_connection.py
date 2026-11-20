"""Task 559 batch B1/B2: the pure verdict projection over `pcb.connection_probe`.

Every payload here is hand-built to the exact shape `connector/src/actions.ts`
reports (`page`/`readOnly`/`from`/`to`/`errors`/`unknown`/`ignored`/`coverage`),
so these tests pin the *verdict* contract, not the host. The task book's negative
controls are the test names.

559B narrowed the contract to **direct-only**: `getEntireTrack` was measured
returning ids of other, offline-disconnected copper components, so the tests that
used a track id set as proof are now counterexamples — the same payloads must
*not* answer CONNECTED, and a legacy non-empty `tracks[]` is a named gap that
blocks the negative too.

What these tests are *not*: they do not call the connector, the bridge, the CLI
or any editor, and no fixture is read.
"""

from __future__ import annotations

import copy
import json

import pytest

from boardwise.core.connection import (
    CONNECTED,
    INDETERMINATE,
    NOT_PROVEN,
    SCHEMA,
    ConnectionResult,
    project_connection,
)

PAD_FROM = "pad-r1-1"
PAD_TO = "pad-j1-1"
TRACK_A = "track-aaa"
TRACK_B = "track-bbb"
VIA = "via-ccc"
POLY = "polyline-ddd"


# --------------------------------------------------------------------------
# payload builders — one per shape the connector emits
# --------------------------------------------------------------------------
def _item(primitive_id: str, kind: str = "Line") -> dict:
    return {"primitiveId": primitive_id, "type": kind}


def _direct(
    items: list[dict],
    *,
    ok: bool = True,
    error: str | None = None,
    truncated: bool = False,
    unreadable: int | None = None,
    ids: list[str] | None = None,
) -> dict:
    if not ok:
        row: dict = {"ok": False}
        if error is not None:
            row["error"] = error
        return row
    named = sorted({item["primitiveId"] for item in items}) if ids is None else list(ids)
    row = {
        "ok": True,
        "count": len(items),
        "ids": named,
        "items": [dict(item) for item in items],
        "truncated": truncated,
    }
    if unreadable:
        row["unreadable"] = unreadable
    return row


def _track(
    primitive_id: str,
    ids: list[str],
    *,
    kind: str = "Line",
    ok: bool = True,
    status: str = "function",
    truncated: bool = False,
    unreadable: int | None = None,
    error: str | None = None,
) -> dict:
    """One row of the **legacy** ``tracks[]`` (559B: production no longer sends it)."""
    if ok:
        call: dict = {
            "ok": True,
            "count": len(ids),
            "ids": sorted(ids),
            "truncated": truncated,
        }
        if unreadable:
            call["unreadable"] = unreadable
    else:
        call = {"ok": False, "error": error or "getEntireTrack(true) threw"}
    return {"primitiveId": primitive_id, "type": kind, "status": status, "call": call}


def _end(
    designator: str,
    pad: str,
    pad_id: str | None,
    net: str | None,
    *,
    items: list[dict] | None = None,
    tracks: list[dict] | None = None,
    direct: dict | None = None,
    matches: int = 1,
    read_errors: list[str] | None = None,
    truncated: bool = False,
    status: str = "resolved",
    resolution: dict | None = None,
) -> dict:
    row = {
        "ref": {"designator": designator, "pad": pad},
        "status": status,
        "resolution": resolution
        if resolution is not None
        else {
            "components": 4,
            "matches": matches,
            "candidates": [pad_id] if pad_id else [],
            "readErrors": list(read_errors or []),
            "truncated": truncated,
            "complete": not truncated and not read_errors,
        },
        "pad": None
        if pad_id is None and net is None
        else {"primitiveId": pad_id, "padNumber": pad, "net": net, "type": "ComponentPad"},
        "direct": direct if direct is not None else _direct(items or []),
    }
    # The production probe no longer sends `tracks` at all (559B); only the
    # legacy-payload tests below add it back, and only to prove it is ignored.
    if tracks is not None:
        row["tracks"] = list(tracks)
    if status != "resolved":
        row["error"] = f"{status} for {designator}.{pad}"
    return row


def _coverage(*, complete: bool = True, **overrides) -> dict:
    row = {
        "scan": {
            "manager": "pcb_PrimitiveComponent",
            "cap": 512,
            "components": 4,
            "truncated": False,
            "readErrors": 0,
            "complete": complete,
        },
        "direct": {
            "perEnd": 16,
            "reported": {"from": 1, "to": 1},
            "truncated": {"from": False, "to": False},
        },
        "unknown": 0,
        "ignored": 0,
        "errors": 0,
        "complete": complete,
    }
    row.update(overrides)
    return row


def _probe(
    *,
    from_end: dict | None = None,
    to_end: dict | None = None,
    page: dict | None = None,
    read_only=None,
    errors: list | None = None,
    unknown: list | None = None,
    ignored: list | None = None,
    coverage: dict | None = None,
) -> dict:
    return {
        "page": {"uuid": "doc-uuid-1", "type": "pcb"} if page is None else page,
        "readOnly": True if read_only is None else read_only,
        "from": _end("R1", "1", PAD_FROM, "GND") if from_end is None else from_end,
        "to": _end("J1", "1", PAD_TO, "GND") if to_end is None else to_end,
        "errors": list(errors or []),
        "unknown": list(unknown or []),
        "ignored": list(ignored or []),
        "coverage": _coverage() if coverage is None else coverage,
    }


def _codes(rows: list[dict]) -> set[str]:
    return {str(row.get("code")) for row in rows}


def _round_trip(payload: dict) -> dict:
    """What a CLI would print and a reader would parse."""
    return json.loads(project_connection(copy.deepcopy(payload)).to_json())


# --------------------------------------------------------------------------
# positives: a typed, sourced intersection is the only way to CONNECTED
# --------------------------------------------------------------------------
def test_legacy_track_containing_other_ends_direct_track_is_not_connected() -> None:
    # 559B counterexample: from's direct answer names t1, to's names t2, and a
    # legacy `from.tracks` claims t2. An entireTrack id set was measured to span
    # other, offline-disconnected copper components, so this is **not** proof —
    # it is a named gap that blocks the negative too.
    payload = _probe(
        from_end=_end(
            "R1",
            "1",
            PAD_FROM,
            "GND",
            items=[_item(TRACK_A)],
            tracks=[_track(TRACK_A, [TRACK_A, TRACK_B])],
        ),
        to_end=_end("J1", "1", PAD_TO, "GND", items=[_item(TRACK_B, "Arc")]),
    )
    result = project_connection(payload)

    assert result.verdict == INDETERMINATE
    assert result.proofs == []
    assert result.shared_ids == []
    assert "entire-track-unsupported" in _codes(result.unknown)
    row = next(row for row in result.unknown if row["code"] == "entire-track-unsupported")
    assert row["end"] == "from"
    assert row["primitiveIds"] == [TRACK_A], "only the track rows are named, never their id sets"


def test_direct_shared_track_is_connected() -> None:
    payload = _probe(
        from_end=_end("R1", "1", PAD_FROM, "GND", items=[_item(TRACK_A)]),
        to_end=_end("J1", "1", PAD_TO, "GND", items=[_item(TRACK_A, "Arc")]),
    )
    result = project_connection(payload)

    assert result.verdict == CONNECTED
    assert [row["kind"] for row in result.proofs] == ["direct-shared-track"]
    assert result.proofs[0]["from"] == {"end": "from", "call": "direct"}
    assert result.proofs[0]["to"] == {"end": "to", "call": "direct"}
    assert result.shared_ids[0]["type"] == "Line"
    assert result.shared_ids[0]["sources"] == [
        {"end": "from", "call": "direct"},
        {"end": "to", "call": "direct"},
    ]
    assert {row["end"] for row in result.shared_ids[0]["sources"]} == {"from", "to"}


def test_direct_other_pad_is_connected() -> None:
    payload = _probe(
        from_end=_end("R1", "1", PAD_FROM, "GND", items=[_item(PAD_TO, "ComponentPad")]),
        to_end=_end("J1", "1", PAD_TO, "GND", items=[]),
    )
    result = project_connection(payload)

    assert result.verdict == CONNECTED
    assert [row["kind"] for row in result.proofs] == ["direct-other-pad"]
    assert result.proofs[0]["to"] == {"end": "to", "call": "pad"}
    assert result.shared_ids[0]["primitiveId"] == PAD_TO


def test_legacy_track_containing_other_pad_is_not_connected() -> None:
    # Same counterexample with the other pad as the claimed member: a pad id in a
    # legacy entireTrack set proves nothing either.
    payload = _probe(
        from_end=_end(
            "R1",
            "1",
            PAD_FROM,
            "GND",
            items=[_item(TRACK_A)],
            tracks=[_track(TRACK_A, [TRACK_A, PAD_TO])],
        ),
        to_end=_end("J1", "1", PAD_TO, "GND", items=[]),
    )
    result = project_connection(payload)

    assert result.verdict == INDETERMINATE
    assert result.proofs == []
    assert "entire-track-unsupported" in _codes(result.unknown)


def test_direct_shared_track_still_proves_with_a_legacy_track_beside_it() -> None:
    # A proven direct intersection is never overturned by the legacy disclosure,
    # and the legacy set itself never adds or removes a proof.
    payload = _probe(
        from_end=_end(
            "R1",
            "1",
            PAD_FROM,
            "GND",
            items=[_item(TRACK_A)],
            tracks=[_track(TRACK_A, [TRACK_B, PAD_TO])],
        ),
        to_end=_end("J1", "1", PAD_TO, "GND", items=[_item(TRACK_A)]),
    )
    result = project_connection(payload)

    assert result.verdict == CONNECTED
    assert [row["kind"] for row in result.proofs] == ["direct-shared-track"]
    assert [row["primitiveId"] for row in result.shared_ids] == [TRACK_A]
    assert "entire-track-unsupported" in _codes(result.unknown)


def test_connected_keeps_gaps_visible() -> None:
    payload = _probe(
        from_end=_end("R1", "1", PAD_FROM, "GND", items=[_item(TRACK_A)]),
        to_end=_end("J1", "1", PAD_TO, "GND", items=[_item(TRACK_A)]),
        unknown=[{"end": "from", "reason": "not-a-track", "primitiveId": VIA, "type": "Via"}],
    )
    result = project_connection(payload)

    assert result.verdict == CONNECTED
    assert result.shared_ids
    assert [row.get("primitiveId") for row in result.unknown] == [VIA]


# --------------------------------------------------------------------------
# the honest negative, and every gap that forbids it
# --------------------------------------------------------------------------
def test_complete_no_intersection_is_not_proven() -> None:
    payload = _probe(
        from_end=_end("R1", "1", PAD_FROM, "GND", items=[_item(TRACK_A)]),
        to_end=_end("J1", "1", PAD_TO, "GND", items=[_item(TRACK_B)]),
    )
    result = project_connection(payload)

    assert result.verdict == NOT_PROVEN
    assert result.proofs == []
    assert result.shared_ids == []
    assert result.unknown == []
    assert "no-intersection" in _codes(result.ignored)


def test_unknown_item_downgrades_negative_to_indeterminate() -> None:
    payload = _probe(
        from_end=_end("R1", "1", PAD_FROM, "GND", items=[_item(TRACK_A)]),
        to_end=_end("J1", "1", PAD_TO, "GND", items=[_item(TRACK_B)]),
        unknown=[{"end": "from", "reason": "not-a-track", "primitiveId": VIA, "type": "Via"}],
    )
    result = project_connection(payload)

    assert result.verdict == INDETERMINATE
    assert result.proofs == []
    assert any(row.get("primitiveId") == VIA for row in result.unknown)


def test_coverage_false_downgrades_negative() -> None:
    payload = _probe(
        from_end=_end("R1", "1", PAD_FROM, "GND", items=[_item(TRACK_A)]),
        to_end=_end("J1", "1", PAD_TO, "GND", items=[_item(TRACK_B)]),
        coverage=_coverage(complete=False),
    )
    result = project_connection(payload)

    assert result.verdict == INDETERMINATE
    assert "coverage-incomplete" in _codes(result.unknown)


def test_legacy_track_gap_blocks_negative_even_with_complete_coverage() -> None:
    # A legacy payload can still say coverage.complete == true beside a tracks[]
    # the connector no longer produces, and the gap must be re-derived from the
    # reading rather than from the summary — regardless of what the track row
    # claimed (a failed call or a truncated set included).
    for row in (
        _track(TRACK_A, [TRACK_A], unreadable=2),
        _track(TRACK_A, [TRACK_A], truncated=True),
        _track(TRACK_A, [], ok=False, status="error"),
    ):
        payload = _probe(
            from_end=_end("R1", "1", PAD_FROM, "GND", items=[_item(TRACK_A)], tracks=[row]),
            to_end=_end("J1", "1", PAD_TO, "GND", items=[_item(TRACK_B)]),
        )
        assert payload["coverage"]["complete"] is True

        result = project_connection(payload)

        assert result.verdict == INDETERMINATE
        assert "entire-track-unsupported" in _codes(result.unknown)
        assert result.proofs == []


def test_an_empty_legacy_track_array_is_absent_not_a_gap() -> None:
    # The old connector sent `tracks: []` for every end. An empty set withholds
    # nothing, so it must not turn an honest negative into a third verdict.
    payload = _probe(
        from_end=_end("R1", "1", PAD_FROM, "GND", items=[_item(TRACK_A)], tracks=[]),
        to_end=_end("J1", "1", PAD_TO, "GND", items=[_item(TRACK_B)], tracks=[]),
    )
    result = project_connection(payload)

    assert result.verdict == NOT_PROVEN
    assert "entire-track-unsupported" not in _codes(result.unknown)


def test_scan_read_errors_block_negative() -> None:
    payload = _probe(
        from_end=_end(
            "R1", "1", PAD_FROM, "GND", items=[_item(TRACK_A)], read_errors=["component #2: Designator read null"]
        ),
        to_end=_end("J1", "1", PAD_TO, "GND", items=[_item(TRACK_B)]),
        coverage=_coverage(complete=False),
    )
    result = project_connection(payload)

    assert result.verdict == INDETERMINATE
    assert "resolution-read-errors" in _codes(result.unknown)


def test_missing_coverage_is_a_gap() -> None:
    payload = _probe(
        from_end=_end("R1", "1", PAD_FROM, "GND", items=[_item(TRACK_A)]),
        to_end=_end("J1", "1", PAD_TO, "GND", items=[_item(TRACK_B)]),
    )
    del payload["coverage"]
    result = project_connection(payload)

    assert result.verdict == INDETERMINATE
    assert "coverage-missing" in _codes(result.unknown)


# --------------------------------------------------------------------------
# no fabricated proof: untyped arrays, non-proof types, other nets, one pad
# --------------------------------------------------------------------------
def test_untyped_id_arrays_are_not_a_proof() -> None:
    # The two answer arrays overlap, but neither side carries a typed item for
    # that id — comparing bare id arrays would be a fabricated intersection.
    payload = _probe(
        from_end=_end(
            "R1", "1", PAD_FROM, "GND", direct=_direct([], ids=[TRACK_A, TRACK_B])
        ),
        to_end=_end("J1", "1", PAD_TO, "GND", direct=_direct([], ids=[TRACK_A])),
    )
    result = project_connection(payload)

    assert result.verdict == INDETERMINATE
    assert result.proofs == []
    assert result.shared_ids == []
    assert "direct-ids-without-type" in _codes(result.unknown)


def test_same_id_with_non_proof_type_is_not_a_proof() -> None:
    payload = _probe(
        from_end=_end("R1", "1", PAD_FROM, "GND", items=[_item(POLY, "Polyline")]),
        to_end=_end("J1", "1", PAD_TO, "GND", items=[_item(POLY, "Polyline")]),
        unknown=[{"end": "from", "reason": "not-a-track", "primitiveId": POLY, "type": "Polyline"}],
    )
    result = project_connection(payload)

    assert result.verdict == INDETERMINATE
    assert result.shared_ids == []
    assert all(proof["primitiveId"] != POLY for proof in result.proofs)


def test_non_proof_type_without_a_host_unknown_row_is_still_a_named_gap() -> None:
    # Conservative negative control (560/P2-1): the projection may not lean on the
    # host having remembered to disclose the Via. Both ends reach the same Via, no
    # proof type is shared, so the answer is the honest third verdict, the gap has
    # a name of its own, and the exclusion is still disclosed as "not a proof".
    payload = _probe(
        from_end=_end("R1", "1", PAD_FROM, "GND", items=[_item(VIA, "Via")]),
        to_end=_end("J1", "1", PAD_TO, "GND", items=[_item(VIA, "Via")]),
    )
    result = project_connection(payload)

    assert result.verdict == INDETERMINATE
    assert result.proofs == []
    assert result.shared_ids == []
    assert "not-a-track-type" in _codes(result.ignored)
    named = [row for row in result.unknown if row["code"] == "direct-non-proof-type"]
    assert [(row["end"], row["type"], row["primitiveId"]) for row in named] == [
        ("from", "Via", VIA),
        ("to", "Via", VIA),
    ]


def test_a_proof_is_not_overturned_by_a_non_proof_type_beside_it() -> None:
    # The gap is disclosed, never used: a typed shared Line still answers the
    # question, and the Via is never promoted to a proof.
    payload = _probe(
        from_end=_end("R1", "1", PAD_FROM, "GND", items=[_item(TRACK_A), _item(VIA, "Via")]),
        to_end=_end("J1", "1", PAD_TO, "GND", items=[_item(TRACK_A), _item(VIA, "Via")]),
    )
    result = project_connection(payload)

    assert result.verdict == CONNECTED
    assert [proof["primitiveId"] for proof in result.proofs] == [TRACK_A]
    assert all(proof["primitiveId"] != VIA for proof in result.proofs)
    assert "direct-non-proof-type" in _codes(result.unknown)


def test_different_net_refused_even_with_intersection() -> None:
    payload = _probe(
        from_end=_end("R1", "1", PAD_FROM, "GND", items=[_item(TRACK_A)]),
        to_end=_end("J1", "1", PAD_TO, "VCC", items=[_item(TRACK_A)]),
    )
    result = project_connection(payload)

    assert result.verdict == INDETERMINATE
    assert "different-net" in _codes(result.errors)
    assert result.proofs == []


def test_same_pad_is_refused() -> None:
    payload = _probe(
        from_end=_end("R1", "1", PAD_FROM, "GND", items=[_item(TRACK_A)]),
        to_end=_end("J1", "1", PAD_FROM, "GND", items=[_item(TRACK_A)]),
    )
    result = project_connection(payload)

    assert result.verdict == INDETERMINATE
    assert "same-pad" in _codes(result.errors)
    assert result.shared_ids == []


def test_missing_pad_identity_is_refused() -> None:
    payload = _probe(
        from_end=_end("R1", "1", None, "GND", items=[_item(TRACK_A)]),
        to_end=_end("J1", "1", PAD_TO, "GND", items=[_item(TRACK_A)]),
    )
    result = project_connection(payload)

    assert result.verdict == INDETERMINATE
    assert "pad-id-missing" in _codes(result.errors)


def test_missing_net_is_refused() -> None:
    payload = _probe(
        from_end=_end("R1", "1", PAD_FROM, None, items=[_item(TRACK_A)]),
        to_end=_end("J1", "1", PAD_TO, None, items=[_item(TRACK_A)]),
    )
    result = project_connection(payload)

    assert result.verdict == INDETERMINATE
    assert "net-missing" in _codes(result.errors)


def test_direct_not_ok_is_refused() -> None:
    payload = _probe(
        from_end=_end(
            "R1",
            "1",
            PAD_FROM,
            "GND",
            direct=_direct([], ok=False, error="getConnectedPrimitives(false) threw"),
        ),
        to_end=_end("J1", "1", PAD_TO, "GND", items=[_item(TRACK_A)]),
    )
    result = project_connection(payload)

    assert result.verdict == INDETERMINATE
    assert "direct-not-ok" in _codes(result.errors)
    assert result.proofs == []


def test_unresolved_end_is_refused() -> None:
    payload = _probe(
        from_end=_end("R1", "1", None, None, status="ambiguous"),
        to_end=_end("J1", "1", PAD_TO, "GND", items=[_item(TRACK_A)]),
    )
    result = project_connection(payload)

    assert result.verdict == INDETERMINATE
    assert "end-not-resolved" in _codes(result.errors)


# --------------------------------------------------------------------------
# envelope: page, read-only, schema shape, determinism, input untouched
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "page",
    [
        {"uuid": "doc-uuid-1", "type": "schematic"},
        {"uuid": "doc-uuid-1", "type": None},
        None,
    ],
)
def test_non_pcb_page_is_refused(page) -> None:
    payload = _probe(
        from_end=_end("R1", "1", PAD_FROM, "GND", items=[_item(TRACK_A)]),
        to_end=_end("J1", "1", PAD_TO, "GND", items=[_item(TRACK_A)]),
        page=page if page is not None else {"uuid": None, "type": None},
    )
    result = project_connection(payload)

    assert result.verdict == INDETERMINATE
    assert "page-not-pcb" in _codes(result.errors)
    assert result.proofs == []


def test_read_only_false_is_refused() -> None:
    payload = _probe(
        from_end=_end("R1", "1", PAD_FROM, "GND", items=[_item(TRACK_A)]),
        to_end=_end("J1", "1", PAD_TO, "GND", items=[_item(TRACK_A)]),
        read_only=False,
    )
    result = project_connection(payload)

    assert result.verdict == INDETERMINATE
    assert "not-read-only" in _codes(result.errors)


def test_payload_shape_is_the_schema_and_has_no_path() -> None:
    payload = _probe(
        from_end=_end("R1", "1", PAD_FROM, "GND", items=[_item(TRACK_A)]),
        to_end=_end("J1", "1", PAD_TO, "GND", items=[_item(TRACK_A)]),
    )
    body = _round_trip(payload)

    assert body["schema"] == SCHEMA
    for key in (
        "verdict",
        "source",
        "query",
        "evidence",
        "sharedIds",
        "proofs",
        "unknown",
        "ignored",
        "errors",
        "coverage",
        "scope",
    ):
        assert key in body, key
    for absent in ("path", "hopCount", "viaCount"):
        assert absent not in body
    assert body["query"]["from"]["ref"] == {"designator": "R1", "pad": "1"}
    assert body["query"]["from"]["padId"] == PAD_FROM
    assert body["query"]["from"]["net"] == "GND"
    assert body["source"]["connector"] == "pcb.connection_probe"
    assert body["source"]["page"] == {"uuid": "doc-uuid-1", "type": "pcb"}
    assert body["source"]["readOnly"] is True


def test_empty_payload_still_reports_every_array() -> None:
    result = project_connection({})

    assert result.verdict == INDETERMINATE
    body = result.as_dict()
    for key in ("sharedIds", "proofs", "unknown", "ignored", "errors"):
        assert isinstance(body[key], list)
    assert body["schema"] == SCHEMA
    assert json.loads(result.to_json()) == body


def test_canonical_json_is_deterministic_and_sorted() -> None:
    payload = _probe(
        from_end=_end(
            "R1",
            "1",
            PAD_FROM,
            "GND",
            items=[_item(TRACK_B), _item(TRACK_A)],
        ),
        to_end=_end("J1", "1", PAD_TO, "GND", items=[_item(TRACK_B), _item(TRACK_A)]),
    )
    first = project_connection(copy.deepcopy(payload)).to_json()
    second = project_connection(copy.deepcopy(payload)).to_json()

    assert first == second
    keys = list(json.loads(first).keys())
    assert keys == sorted(keys)
    body = json.loads(first)
    assert [row["primitiveId"] for row in body["sharedIds"]] == sorted(
        row["primitiveId"] for row in body["sharedIds"]
    )


def test_input_payload_is_not_modified() -> None:
    payload = _probe(
        from_end=_end("R1", "1", PAD_FROM, "GND", items=[_item(TRACK_A)]),
        to_end=_end("J1", "1", PAD_TO, "GND", items=[_item(TRACK_A)]),
        unknown=[{"end": "to", "reason": "primitive-type-unknown", "primitiveId": None, "type": None}],
    )
    frozen = copy.deepcopy(payload)
    result = project_connection(payload)

    assert payload == frozen
    assert result.evidence["from"] == frozen["from"]
    assert result.evidence["to"] == frozen["to"]


def test_result_defaults_are_indeterminate() -> None:
    assert ConnectionResult().verdict == INDETERMINATE
    assert ConnectionResult().shared_ids == []
    assert ConnectionResult().proofs == []
