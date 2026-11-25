"""612 — a C-number hit must agree with the MPN typed beside it.

`resolve_identity` already refuses an MPN hit whose own C-number disagrees with
the one on the command line; the C-number direction never looked at the MPN, so
`C8734` + `STM32F103C8T6` resolved to whatever the C-number hit happened to be
(570-D D8). Both directions now refuse with the same sentence, and an item that
carries no MPN of its own is still not guessed at — the host names devices by its
own convention (`Ground-GND`), which is not an MPN.
"""

from __future__ import annotations

import asyncio

import pytest

from boardwise.engines.select import resolve_identity


def _item(**over: object) -> dict:
    """One `lib.device.search` item: the C-number, the uuid pair, nothing else."""
    item: dict = {"uuid": "du-1", "libraryUuid": "lu-1", "supplierId": "C8734"}
    item.update(over)
    return item


class _FakeClient:
    """Answers `lib.device.search` from one list and records the keywords asked."""

    def __init__(self, items: list) -> None:
        self.items = items
        self.calls: list[tuple[str, dict]] = []

    async def call(self, action: str, params: dict | None = None) -> dict:
        self.calls.append((action, dict(params or {})))
        return {"items": self.items}


def _resolve(items: list, **terms) -> tuple[object, _FakeClient]:
    client = _FakeClient(items)
    return asyncio.run(resolve_identity(client, **terms)), client


def test_a_c_number_hit_that_names_another_mpn_is_refused():
    """570-D D8, verbatim: the two terms describe different parts."""
    result, client = _resolve(
        [_item(lcsc="C8734", mpn="NE555DR")],
        lcsc="C8734",
        mpn="STM32F103C8T6",
    )
    assert result.resolved is False
    assert result.reason == (
        "the LCSC hit carries mpn=NE555DR, not the given STM32F103C8T6; "
        "refusing a pair that disagrees"
    )
    # The refused hit is quoted, and neither half of a uuid leaks out.
    assert result.candidates and "mpn=NE555DR" in result.candidates[0]
    assert (result.deviceUuid, result.libraryUuid) == ("", "")
    assert result.matched_by == ""
    # The MPN keyword is never searched: the exact hit already contradicted it.
    assert client.calls == [("lib.device.search", {"keyword": "C8734", "limit": 8})]


@pytest.mark.parametrize(
    "key", ["mpn", "partNumber", "partCode", "manufacturerPartNumber"]
)
def test_the_refusal_names_whichever_part_number_key_the_item_spells(key: str):
    result, _ = _resolve([_item(**{key: "NE555DR"})], lcsc="C8734", mpn="STM32F103C8T6")
    assert result.resolved is False
    assert f"the LCSC hit carries {key}=NE555DR" in result.reason


def test_an_agreeing_pair_resolves_off_the_c_number():
    """Case and surrounding blanks are the existing rule, not a new one."""
    result, client = _resolve(
        [_item(supplierId="C8734", mpn="STM32F103C8T6")],
        lcsc=" c8734 ",
        mpn=" stm32f103c8t6 ",
    )
    assert result.resolved is True
    assert (result.matched_by, result.matched_key) == ("lcsc", "supplierId")
    assert (result.deviceUuid, result.libraryUuid) == ("du-1", "lu-1")
    assert client.calls == [("lib.device.search", {"keyword": "C8734", "limit": 8})]


@pytest.mark.parametrize(
    "carried",
    [
        {},
        {"mpn": ""},
        {"mpn": "   "},
        # The host's own device naming is not an MPN: a `Ground-GND` device
        # carries no manufacturer part number, so the MPN is not compared here.
        {"name": "Ground-GND"},
    ],
    ids=["absent", "empty", "blank", "host-name-only"],
)
def test_a_c_number_hit_that_carries_no_mpn_is_not_guessed(carried: dict):
    result, _ = _resolve([_item(**carried)], lcsc="C8734", mpn="STM32F103C8T6")
    assert result.resolved is True, result.reason
    assert result.matched_by == "lcsc"


def test_the_mpn_hit_still_refuses_a_conflicting_c_number():
    """The reverse control: unchanged wording, unchanged order."""
    result, client = _resolve(
        [_item(supplierId="C9999", mpn="NE555DR")], lcsc="C8734", mpn="NE555DR"
    )
    assert result.resolved is False
    assert result.reason == (
        "the MPN hit carries supplierId=C9999, not the given C8734; "
        "refusing a pair that disagrees"
    )
    assert client.calls == [
        ("lib.device.search", {"keyword": "C8734", "limit": 8}),
        ("lib.device.search", {"keyword": "NE555DR", "limit": 8}),
    ]


def test_one_term_alone_behaves_exactly_as_before():
    """No second term ⇒ no cross-check at all, in either direction."""
    only_lcsc, lcsc_calls = _resolve([_item(mpn="NE555DR")], lcsc="C8734")
    assert only_lcsc.resolved is True
    assert (only_lcsc.matched_by, only_lcsc.matched_key) == ("lcsc", "supplierId")
    assert lcsc_calls.calls == [("lib.device.search", {"keyword": "C8734", "limit": 8})]

    only_mpn, mpn_calls = _resolve(
        [{"uuid": "du-2", "libraryUuid": "lu-2", "mpn": "NE555DR"}], mpn="NE555DR"
    )
    assert only_mpn.resolved is True
    assert (only_mpn.matched_by, only_mpn.matched_key) == ("mpn", "mpn")
    assert mpn_calls.calls == [("lib.device.search", {"keyword": "NE555DR", "limit": 8})]


def test_the_pair_is_refused_before_the_uuid_half_is_mourned():
    """A contradicting MPN is the reason; a missing uuid would only move it later."""
    result, _ = _resolve(
        [{"supplierId": "C8734", "mpn": "NE555DR"}], lcsc="C8734", mpn="STM32F103C8T6"
    )
    assert result.resolved is False
    assert "refusing a pair that disagrees" in result.reason
    assert "no device uuid" not in result.reason
