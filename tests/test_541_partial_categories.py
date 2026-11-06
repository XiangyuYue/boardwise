"""541 R4: the opt-in four-class disclosure on a `partial` evidence delivery.

Why this file exists. ``evidence`` already says **whether** coverage is short
(``delivery.status``) and **which** disclosures are owed
(``requiredDisclosures[]``). It does not say **how** each gap stands: a real
reading, a lead that is not enough, a read that failed or never happened, and
evidence nobody went looking for all printed as the same ``partial``. 541 R4
adds one versioned derivation (``partialVersion`` / ``partialCategories``) and
one opt-in gate (``review finalize --strict-partial``).

What this file pins:

1. **the mapping** — derived from the channel rows and the live capture only
   (``ok`` / plain ``not-applicable`` → confirmed; ``failed`` / capability
   limited ``not-applicable`` → suspected; ``missing`` → unverified;
   ``unavailable`` → uncovered; a capture's identity / focus rows → unverified),
   one row per channel, every required disclosure covered exactly once, every
   item quoting its source ``code`` / ``status`` / ``detail``;
2. **the builders** — ``evidence_section``, ``merge_live_capture`` and
   ``refresh_datasheets`` all recompute the field (a re-gate cannot leave last
   run's classes behind), and a ``complete`` delivery carries **no** field;
3. **the gate** — ``validate_review_summary(..., strict_partial=True)`` rejects a
   missing class, a bad count, a foreign status, a duplicate / extra code, a
   stale class, a wrong version, an unknown class, a `complete` delivery with
   residue, and a summary that never says ``needs-manual`` / open item — all as
   the existing structured ``{code, path, message}`` rows;
4. **the compatibility promise** — without the flag the same report validates
   exactly as before, and a pass is a **disclosure** statement: the board
   verdict (``report.conclusion``) is never raised by it;
5. **the wired command** — ``review finalize --strict-partial`` signs a clean
   delivery and refuses a token-free one with zero writes.

All data is synthetic: the acceptance report comes from
``tests/test_537d_finalize_validation.py`` through the real writer, and the
channel/capture helpers are the ones ``tests/test_537c_live_merge.py`` already
uses. No editor, daemon, netlist, image or project file.
"""

from __future__ import annotations

import copy
import json

import pytest

from boardwise import cli
from boardwise.engines import evidence as ev
from boardwise.engines.reviewfinalize import (
    _PARTIAL_DISCLOSURE_TOKEN_RE,
    validate_review_summary,
)

import test_537c_live_merge as lm
import test_537d_finalize_cli as dfx
import test_537d_finalize_validation as fx

CLASSES = ev.PARTIAL_CLASSES


# ---------------------------------------------------------------------------
# synthetic channel rows / sections
# ---------------------------------------------------------------------------


def _row(name: str, status: str = ev.STATUS_OK, errors: list | None = None) -> dict:
    return {
        "status": status,
        "source": ev.CHANNEL_SOURCES[name],
        "detail": f"{name} 的 detail（{status}）",
        "artifacts": [],
        "errors": list(errors or []),
        "steps": [],
    }


def _channels(
    statuses: dict | None = None, errors: dict | None = None
) -> dict:
    return {
        name: _row(
            name,
            (statuses or {}).get(name, ev.STATUS_OK),
            (errors or {}).get(name),
        )
        for name in ev.CHANNEL_ORDER
    }


def _codes(categories: dict, class_name: str) -> list[str]:
    return [item["code"] for item in categories[class_name]["items"]]


def _all_items(categories: dict) -> list[dict]:
    return [item for name in CLASSES for item in categories[name]["items"]]


def _section(channels: dict, live_capture: dict | None = None) -> dict:
    """The section as the module's own builders leave it (classes included)."""
    section = {
        "schema": ev.EVIDENCE_SCHEMA,
        "channels": channels,
        "coverage": ev.evidence_coverage(channels),
        "delivery": ev.evidence_delivery(channels, live_capture=live_capture),
    }
    if live_capture is not None:
        section[ev.LIVE_CAPTURE_KEY] = live_capture
    return ev._apply_partial_categories(section)


# ---------------------------------------------------------------------------
# 1. the mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "status, errors, expected",
    [
        (ev.STATUS_OK, None, ev.PARTIAL_CONFIRMED),
        (ev.STATUS_NOT_APPLICABLE, None, ev.PARTIAL_CONFIRMED),
        (ev.STATUS_FAILED, None, ev.PARTIAL_SUSPECTED),
        (ev.STATUS_NOT_APPLICABLE, ["pcb-image-limit"], ev.PARTIAL_SUSPECTED),
        (ev.STATUS_MISSING, None, ev.PARTIAL_UNVERIFIED),
        (ev.STATUS_UNAVAILABLE, None, ev.PARTIAL_UNCOVERED),
    ],
    ids=[
        "ok-confirmed",
        "plain-not-applicable-confirmed",
        "failed-suspected",
        "capability-limited-not-applicable-suspected",
        "missing-unverified",
        "unavailable-uncovered",
    ],
)
def test_each_channel_status_lands_in_the_class_its_reading_means(
    status, errors, expected
):
    channels = _channels({ev.CHANNEL_LIVE_PCB: status}, {ev.CHANNEL_LIVE_PCB: errors})
    categories = ev.partial_categories(channels)
    code = ev.DISCLOSURE_CODES[ev.CHANNEL_LIVE_PCB]
    assert code in _codes(categories, expected)
    for name in CLASSES:
        if name == expected:
            continue
        assert code not in _codes(categories, name), name


def test_every_channel_is_listed_once_and_count_is_the_items_length():
    channels = _channels({
        ev.CHANNEL_LIVE_SCHEMATIC: ev.STATUS_OK,
        ev.CHANNEL_ARCHIVE_PCB: ev.STATUS_NOT_APPLICABLE,
        ev.CHANNEL_LIVE_PCB: ev.STATUS_FAILED,
        ev.CHANNEL_SCHEMATIC_IMAGE: ev.STATUS_MISSING,
        ev.CHANNEL_PCB_IMAGE: ev.STATUS_UNAVAILABLE,
        ev.CHANNEL_DATASHEETS: ev.STATUS_OK,
    })
    categories = ev.partial_categories(channels)
    assert list(categories) == list(CLASSES)
    for name in CLASSES:
        entry = categories[name]
        assert set(entry) == {"count", "items"}
        assert entry["count"] == len(entry["items"])
    codes = [item["code"] for item in _all_items(categories)]
    assert sorted(codes) == sorted(ev.DISCLOSURE_CODES.values())
    assert len(codes) == len(set(codes))


def test_every_required_disclosure_is_covered_exactly_once():
    channels = _channels(
        {
            ev.CHANNEL_LIVE_PCB: ev.STATUS_MISSING,
            ev.CHANNEL_PCB_IMAGE: ev.STATUS_NOT_APPLICABLE,
        },
        {ev.CHANNEL_PCB_IMAGE: ["pcb-image-limit"]},
    )
    capture = lm._capture(verified=False)
    delivery = ev.evidence_delivery(channels, live_capture=capture)
    required = [row["code"] for row in delivery["requiredDisclosures"]]
    assert required, "本用例必须有必披露"
    codes = [
        item["code"] for item in _all_items(ev.partial_categories(channels, capture))
    ]
    for code in required:
        assert codes.count(code) == 1, code


def test_live_capture_identity_and_focus_are_unverified_rows():
    capture = lm._capture(verified=False, focus={"ok": False, "attempted": False,
                                                 "status": "unavailable",
                                                 "originalUuid": None,
                                                 "error": {"code": "unavailable"}})
    delivery = ev.evidence_delivery(_channels(), live_capture=capture)
    extras = {
        row["code"]: row
        for row in delivery["requiredDisclosures"]
        if not row.get("channel")
    }
    assert set(extras) == {
        ev.DISCLOSURE_IDENTITY_UNVERIFIED,
        ev.DISCLOSURE_FOCUS_RESTORE_FAILED,
    }
    categories = ev.partial_categories(_channels(), capture)
    unverified = {item["code"]: item for item in categories[ev.PARTIAL_UNVERIFIED]["items"]}
    for code, row in extras.items():
        assert unverified[code] == {
            "code": code,
            "status": row["status"],
            "detail": row["message"],
        }
    # 六个通道全闭 + 两条采集披露：delivery 仍是 partial；confirmed 只有通道行，
    # 采集的两条都在 unverified。
    assert delivery["status"] == ev.DELIVERY_PARTIAL
    assert set(_codes(categories, ev.PARTIAL_UNVERIFIED)) == set(extras)
    assert set(_codes(categories, ev.PARTIAL_CONFIRMED)) == set(
        ev.DISCLOSURE_CODES.values()
    )


def test_item_rows_quote_the_channel_row():
    channels = _channels({ev.CHANNEL_LIVE_PCB: ev.STATUS_FAILED})
    channels[ev.CHANNEL_LIVE_PCB]["detail"] = "doc.open 超时，未取到 PCB"
    categories = ev.partial_categories(channels)
    assert categories[ev.PARTIAL_SUSPECTED]["items"] == [{
        "code": ev.DISCLOSURE_CODES[ev.CHANNEL_LIVE_PCB],
        "status": ev.STATUS_FAILED,
        "detail": "doc.open 超时，未取到 PCB",
    }]


# ---------------------------------------------------------------------------
# 2. the builders: derived, never hand-patched, cleared when complete
# ---------------------------------------------------------------------------


def test_evidence_section_carries_the_versioned_classes_when_partial():
    section = ev.evidence_section(tier="file", pcb_had_documents=False)
    assert section["delivery"]["status"] == ev.DELIVERY_PARTIAL
    assert section[ev.PARTIAL_VERSION_KEY] == ev.PARTIAL_VERSION
    assert set(section[ev.PARTIAL_CATEGORIES_KEY]) == set(CLASSES)
    for name in CLASSES:
        entry = section[ev.PARTIAL_CATEGORIES_KEY][name]
        assert entry["count"] == len(entry["items"])


def test_merge_live_capture_recomputes_the_classes_and_drops_the_old_reading():
    stale = lm._evidence({lm.CHANNELS[2]: "failed"})  # livePcb failed
    stale[ev.PARTIAL_VERSION_KEY] = ev.PARTIAL_VERSION
    stale[ev.PARTIAL_CATEGORIES_KEY] = {
        name: {"count": 1, "items": [{"code": "stale", "status": "ok", "detail": ""}]}
        for name in CLASSES
    }
    merged = ev.merge_live_capture(stale, lm._capture())
    assert merged["delivery"]["status"] == ev.DELIVERY_COMPLETE
    assert ev.PARTIAL_VERSION_KEY not in merged
    assert ev.PARTIAL_CATEGORIES_KEY not in merged


def test_merge_live_capture_classifies_the_merged_rows():
    failed = lm._evidence({lm.CHANNELS[2]: "failed"})
    capture = lm._capture(
        verified=False,
        focus={
            "ok": False,
            "attempted": True,
            "status": "failed",
            "originalUuid": "p1",
            "error": {"code": "doc.open-failed"},
        },
    )
    merged = ev.merge_live_capture(failed, capture)
    categories = merged[ev.PARTIAL_CATEGORIES_KEY]
    # 合并把 livePcb 从 failed 换成 ok：suspected 不再留那一行。
    assert _codes(categories, ev.PARTIAL_SUSPECTED) == []
    assert ev.DISCLOSURE_CODES[lm.CHANNELS[2]] in _codes(
        categories, ev.PARTIAL_CONFIRMED
    )
    # 采集自带的两条披露归 unverified，且不是旧的分类。
    assert set(_codes(categories, ev.PARTIAL_UNVERIFIED)) == {
        ev.DISCLOSURE_IDENTITY_UNVERIFIED,
        ev.DISCLOSURE_FOCUS_RESTORE_FAILED,
    }


def test_refresh_datasheets_moves_the_datasheet_row_between_classes():
    # datasheets 失败（suspected），另开一条 unverified 通道，重算后仍为 partial。
    section = lm._evidence({
        lm.CHANNELS[3]: "missing",
        lm.CHANNELS[5]: "failed",
    })
    section[ev.PARTIAL_VERSION_KEY] = ev.PARTIAL_VERSION
    section[ev.PARTIAL_CATEGORIES_KEY] = {
        name: {"count": 0, "items": []} for name in CLASSES
    }
    refreshed = ev.refresh_datasheets(
        section,
        model_empty=False,
        unreviewed=[],
        accepted_unknown=[],
        needs_datasheet=[],
    )
    categories = refreshed[ev.PARTIAL_CATEGORIES_KEY]
    assert ev.DISCLOSURE_CODES[lm.CHANNELS[5]] not in _codes(
        categories, ev.PARTIAL_SUSPECTED
    )
    assert ev.DISCLOSURE_CODES[lm.CHANNELS[5]] in _codes(
        categories, ev.PARTIAL_CONFIRMED
    )
    assert refreshed[ev.PARTIAL_CATEGORIES_KEY] == ev.partial_categories(
        refreshed["channels"], None
    )


def test_refresh_datasheets_clears_the_field_when_the_delivery_turns_complete():
    channels = _channels()
    channels[ev.CHANNEL_DATASHEETS] = _row(ev.CHANNEL_DATASHEETS, ev.STATUS_MISSING)
    section = _section(channels)
    assert ev.PARTIAL_CATEGORIES_KEY in section
    refreshed = ev.refresh_datasheets(
        section,
        model_empty=False,
        unreviewed=[],
        accepted_unknown=[],
        needs_datasheet=[],
    )
    assert refreshed["delivery"]["status"] == ev.DELIVERY_COMPLETE
    assert ev.PARTIAL_VERSION_KEY not in refreshed
    assert ev.PARTIAL_CATEGORIES_KEY not in refreshed


# ---------------------------------------------------------------------------
# 3. the strict gate (validator level, over a real acceptance delivery)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def acceptance(tmp_path_factory):
    """A real `partial` delivery whose summary is filled, and which passes strict."""
    out, written = dfx._make_review(tmp_path_factory.mktemp("acceptance"))
    text = (out / "review-summary.md").read_text(encoding="utf-8")
    assert written["evidence"]["delivery"]["status"] == ev.DELIVERY_PARTIAL
    assert written["evidence"][ev.PARTIAL_VERSION_KEY] == ev.PARTIAL_VERSION
    assert validate_review_summary(written, text, strict_partial=True) == []
    return written, text


def _pair(acceptance):
    return copy.deepcopy(acceptance[0]), acceptance[1]


def _categories_of(report: dict) -> dict:
    return report["evidence"][ev.PARTIAL_CATEGORIES_KEY]


def _strict_codes(report: dict, text: str) -> list[str]:
    return [issue["code"] for issue in validate_review_summary(
        report, text, strict_partial=True
    )]


def test_strict_accepts_the_good_partial_delivery(acceptance):
    report, text = _pair(acceptance)
    assert validate_review_summary(report, text, strict_partial=True) == []


def test_default_validation_ignores_a_broken_field(acceptance):
    report, text = _pair(acceptance)
    del _categories_of(report)[ev.PARTIAL_UNVERIFIED]
    report["evidence"][ev.PARTIAL_VERSION_KEY] = 99
    # 没有 --strict-partial：旧行为，一字不差地通过。
    assert validate_review_summary(report, text) == []
    codes = _strict_codes(report, text)
    assert "partial-category-missing" in codes
    assert "partial-version-invalid" in codes


def test_strict_reports_a_missing_class(acceptance):
    report, text = _pair(acceptance)
    del _categories_of(report)[ev.PARTIAL_SUSPECTED]
    codes = _strict_codes(report, text)
    assert "partial-category-missing" in codes


def test_strict_reports_a_wrong_count(acceptance):
    report, text = _pair(acceptance)
    _categories_of(report)[ev.PARTIAL_CONFIRMED]["count"] += 3
    codes = _strict_codes(report, text)
    assert "partial-category-count-mismatch" in codes


def test_strict_reports_a_status_outside_the_vocabulary(acceptance):
    report, text = _pair(acceptance)
    _categories_of(report)[ev.PARTIAL_CONFIRMED]["items"][0]["status"] = "大概没事"
    codes = _strict_codes(report, text)
    assert "partial-item-status-invalid" in codes
    assert "partial-category-stale" in codes


def test_strict_reports_a_duplicate_code(acceptance):
    report, text = _pair(acceptance)
    categories = _categories_of(report)
    categories[ev.PARTIAL_CONFIRMED]["items"].append(
        copy.deepcopy(categories[ev.PARTIAL_UNVERIFIED]["items"][0])
    )
    categories[ev.PARTIAL_CONFIRMED]["count"] += 1
    codes = _strict_codes(report, text)
    assert "partial-item-duplicate" in codes
    assert "partial-disclosure-duplicated" in codes


def test_strict_reports_an_extra_code(acceptance):
    report, text = _pair(acceptance)
    categories = _categories_of(report)
    categories[ev.PARTIAL_CONFIRMED]["items"].append(
        {"code": "make-believe-evidence", "status": ev.STATUS_OK, "detail": "猜的"}
    )
    categories[ev.PARTIAL_CONFIRMED]["count"] += 1
    codes = _strict_codes(report, text)
    assert "partial-category-stale" in codes


def test_strict_reports_a_rewritten_detail(acceptance):
    report, text = _pair(acceptance)
    _categories_of(report)[ev.PARTIAL_CONFIRMED]["items"][0]["detail"] = "看起来没事"
    codes = _strict_codes(report, text)
    assert "partial-category-stale" in codes


def test_strict_reports_a_missing_version(acceptance):
    report, text = _pair(acceptance)
    del report["evidence"][ev.PARTIAL_VERSION_KEY]
    codes = _strict_codes(report, text)
    assert "partial-version-missing" in codes


def test_strict_reports_an_unknown_class(acceptance):
    report, text = _pair(acceptance)
    _categories_of(report)["probably-fine"] = {"count": 0, "items": []}
    codes = _strict_codes(report, text)
    assert "partial-category-unknown" in codes


def test_strict_reports_a_complete_delivery_that_kept_the_field(acceptance):
    report, _text = _pair(acceptance)
    channels = _channels()
    report["evidence"]["channels"] = channels
    report["evidence"]["coverage"] = ev.evidence_coverage(channels)
    report["evidence"]["delivery"] = ev.evidence_delivery(channels)
    report["evidence"].pop(ev.LIVE_CAPTURE_KEY)
    codes = _strict_codes(report, (acceptance[1]))
    assert "partial-categories-on-complete" in codes


def test_strict_reports_a_summary_that_never_names_an_open_item(acceptance):
    report, text = _pair(acceptance)
    stripped = _PARTIAL_DISCLOSURE_TOKEN_RE.sub("遗留项", text)
    assert stripped != text
    codes = _strict_codes(report, stripped)
    assert "summary-partial-token-missing" in codes


def test_strict_never_raises_the_board_verdict(acceptance):
    report, text = _pair(acceptance)
    before = copy.deepcopy(report["conclusion"])
    assert report["conclusion"]["mayQuotePassed"] is False
    validate_review_summary(report, text, strict_partial=True)
    assert report["conclusion"] == before


# ---------------------------------------------------------------------------
# 4. the wired command
# ---------------------------------------------------------------------------


def test_parser_accepts_strict_partial_and_defaults_to_false():
    assert cli.build_parser().parse_args(["review", "finalize"]).strict_partial is False
    args = cli.build_parser().parse_args(
        ["review", "finalize", "--out", "DIR", "--strict-partial"]
    )
    assert args.command == "review"
    assert args.file == "finalize"
    assert args.out == "DIR"
    assert args.strict_partial is True


def test_finalize_strict_partial_signs_a_clean_delivery(tmp_path, capsys):
    out, _written = dfx._make_review(tmp_path)
    assert dfx._run(out, "--strict-partial") == 0
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert "finalize validation: ok" in captured.out
    assert (out / dfx.FINALIZE_RECEIPT).is_file()
    # 收据是交付收据，不是板级通过。
    assert dfx._receipt(out)["boardConclusionAuthority"] == dfx.RECEIPT_AUTHORITY


#: The acceptance fixture's own next-steps sentence, with the token removed — the
#: human text a `--strict-partial` delivery must not get away with while the
#: evidence still owes disclosures.
_NO_TOKEN_SENTENCE = "3. 复核那条 warning。"


def _token_free_review(tmp_path):
    """A `partial` delivery whose fill text names no needs-manual / open item.

    Built from the acceptance fixture with the triage ledger emptied (so the
    conclusion one-liner has no ``needs-manual`` in it) and the live capture
    dropped: the remaining partial reason is the ``datasheets`` channel. The only
    thing it lacks is the sentence the strict gate asks for.
    """
    report = fx._report(
        zero_findings=True,
        channel_status={ev.CHANNEL_DATASHEETS: ev.STATUS_MISSING},
    )
    report["warning_triage"] = []
    cli._apply_warning_triage(report, [])
    report["conclusion"] = dfx.conclusion_section(report)
    out = tmp_path / "review"
    cli._write_checkup_report(out, report)
    written = json.loads((out / "report.json").read_text(encoding="utf-8"))
    text = dfx._filled(written).replace(
        "3. 复核那条 needs-manual warning。", _NO_TOKEN_SENTENCE
    )
    assert not _PARTIAL_DISCLOSURE_TOKEN_RE.search(text), text
    (out / "review-summary.md").write_text(text, encoding="utf-8")
    return out, written


def test_finalize_without_the_flag_ignores_the_four_class_gate(tmp_path, capsys):
    out, _written = _token_free_review(tmp_path)
    assert dfx._run(out) == 0
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert (out / dfx.FINALIZE_RECEIPT).is_file()


def test_finalize_strict_partial_refuses_a_token_free_delivery_and_writes_nothing(
    tmp_path, capsys
):
    out, _written = _token_free_review(tmp_path)
    before = dfx._files(out)
    assert dfx._run(out, "--strict-partial") == 1
    text = capsys.readouterr().out
    dfx._assert_untouched(out, before, capsys)
    assert "summary-partial-token-missing" in dfx._codes(text)


# ---------------------------------------------------------------------------
# 5. the re-gate cannot repair what the strict gate must judge
# ---------------------------------------------------------------------------


def test_strict_judges_the_named_original_evidence_not_the_recomputed_copy(
    acceptance,
):
    """`partial_evidence` is the delivery as it arrived — not the healed copy."""
    report, text = _pair(acceptance)
    original = copy.deepcopy(report["evidence"])
    del original[ev.PARTIAL_CATEGORIES_KEY][ev.PARTIAL_UNVERIFIED]
    # 重建件的四类是对的（refresh 会这样修），但原始件缺一类：strict 必须报原始件。
    assert validate_review_summary(
        report, text, strict_partial=True, partial_evidence=original
    )
    codes = [
        issue["code"]
        for issue in validate_review_summary(
            report, text, strict_partial=True, partial_evidence=original
        )
    ]
    assert "partial-category-missing" in codes
    # 反过来：原始件正确、重建件被污染，strict 认原始件，四类不报。
    poisoned = _pair(acceptance)[0]
    del poisoned["evidence"][ev.PARTIAL_CATEGORIES_KEY][ev.PARTIAL_SUSPECTED]
    assert validate_review_summary(
        poisoned,
        text,
        strict_partial=True,
        partial_evidence=acceptance[0]["evidence"],
    ) == []


def test_strict_without_a_named_section_still_reads_the_report(acceptance):
    report, text = _pair(acceptance)
    del report["evidence"][ev.PARTIAL_CATEGORIES_KEY][ev.PARTIAL_SUSPECTED]
    assert "partial-category-missing" in [
        issue["code"]
        for issue in validate_review_summary(report, text, strict_partial=True)
    ]


def test_finalize_strict_partial_refuses_an_original_report_without_the_field(
    tmp_path, capsys
):
    out, written = dfx._make_review(tmp_path)
    stripped = copy.deepcopy(written)
    for key in (ev.PARTIAL_VERSION_KEY, ev.PARTIAL_CATEGORIES_KEY):
        stripped["evidence"].pop(key, None)
    dfx._rewrite_report(out, stripped)
    before = dfx._files(out)

    # 原始报告没有四类：re-gate 会在内存里补上，但 strict 判的是原始件 → 拒签。
    assert dfx._run(out, "--strict-partial") == 1
    text = capsys.readouterr().out
    dfx._assert_untouched(out, before, capsys)
    assert "partial-categories-missing" in dfx._codes(text)

    # 同一份输入、没有 flag：旧路径照旧通过（重算后写回）。
    assert dfx._run(out) == 0
    assert (out / dfx.FINALIZE_RECEIPT).is_file()


def test_finalize_strict_partial_refuses_a_malformed_original_category(
    tmp_path, capsys
):
    out, written = dfx._make_review(tmp_path)
    broken = copy.deepcopy(written)
    del broken["evidence"][ev.PARTIAL_CATEGORIES_KEY][ev.PARTIAL_UNVERIFIED]
    dfx._rewrite_report(out, broken)
    before = dfx._files(out)

    assert dfx._run(out, "--strict-partial") == 1
    text = capsys.readouterr().out
    dfx._assert_untouched(out, before, capsys)
    codes = dfx._codes(text)
    assert "partial-category-missing" in codes
