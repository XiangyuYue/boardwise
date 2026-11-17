"""548P138：静态 joint 失败后的一次单脚 seed 反馈重枚举。

真实 MCU 第一次 `_seat_first_plans` 中，chain=17、U1.3=5、GND=4/2，
chain×U1.3 为85/85共点。旧F1只把seed交给成员路径 `taken`，没有约束旗座
lead/glyph，因而失败。本批要求：同一个 `_seat_first_net_jobs` / router 同时收到
这些节点，候选最多的 chain 只重枚举一次，第二次 joint 才允许接受。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from boardwise.core.presentationspec import PresentationSpec
from boardwise.engines import drawcompiler as dc
from test_548p126_service_host_feedback import SPEC, _context

ROOT = Path(__file__).resolve().parents[1]


class _FirstThreeRailPlan(Exception):
    pass


@pytest.fixture(scope="module")
def first_plan_capture():
    ctx = _context(PresentationSpec.load(ROOT / SPEC))
    calls = []
    job_calls = []
    real_joint = dc._seat_first_joint
    real_plans = dc._seat_first_plans
    real_jobs = dc._seat_first_net_jobs

    def joint_spy(jobs, taken, *, limit=None):
        result = real_joint(jobs, taken, limit=limit)
        ok, chosen, limit_hit, expansions = result
        calls.append({
            "jobs": tuple(jobs),
            "counts": {f"{job.net}/{job.group}": len(job.candidates)
                       for job in jobs},
            "ok": ok,
            "chosen": chosen,
            "limitHit": limit_hit,
            "expansions": expansions,
            "limit": limit,
        })
        return result

    def jobs_spy(*args, **kwargs):
        job_calls.append(dict(kwargs))
        return real_jobs(*args, **kwargs)

    def plans_spy(context, placed, **kwargs):
        plans, failure = real_plans(context, placed, **kwargs)
        if any(plan.net == "3V3" for plan in plans):
            raise _FirstThreeRailPlan
        return plans, failure

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(dc, "_seat_first_joint", joint_spy)
    monkeypatch.setattr(dc, "_seat_first_net_jobs", jobs_spy)
    monkeypatch.setattr(dc, "_seat_first_plans", plans_spy)
    try:
        with pytest.raises(_FirstThreeRailPlan):
            dc._place(ctx, dc._variants(ctx)[0])
    finally:
        monkeypatch.undo()
    return calls, job_calls


def test_first_plan_re_enumerates_only_chain_once_and_joint_succeeds(first_plan_capture):
    calls, job_calls = first_plan_capture
    assert len(calls) == 2, [(call["ok"], call["counts"]) for call in calls]
    first, second = calls
    assert not first["ok"] and not first["limitHit"]
    assert first["counts"]["3V3/share:chain"] == 17
    assert second["ok"] and not second["limitHit"]
    assert second["counts"]["3V3/share:chain"] == 5
    assert second["expansions"] == 6
    # Two original rail enumerations plus exactly one targeted re-enumeration.
    assert len(job_calls) == 3
    assert "seat_blocked" in job_calls[-1]
    assert tuple(job_calls[-1]["seat_blocked"]) == ("share:chain",)


def test_seed_is_the_cheapest_single_foot_nodes_and_final_seats_are_disjoint(
        first_plan_capture):
    calls, job_calls = first_plan_capture
    assert len(calls) == 2
    first, second = calls
    target = max(first["jobs"], key=lambda job: (
        len(job.candidates), job.net, job.group))
    assert target.group == "share:chain"
    expected = set()
    for job in first["jobs"]:
        if job is target or len(job.members) != 1:
            continue
        cheapest = min(job.candidates, key=lambda item: (item.cost, item.owner))
        expected.update(dc._seat_first_candidate_nodes(cheapest))
    assert set(job_calls[-1]["seat_blocked"]["share:chain"]) == expected

    chosen = list(second["chosen"].items())
    assert second["chosen"][("3V3", "share:chain")].owner == "C2.1"
    for index, (_key_a, candidate_a) in enumerate(chosen):
        for _key_b, candidate_b in chosen[index + 1:]:
            assert not (
                dc._seat_first_candidate_nodes(candidate_a)
                & dc._seat_first_candidate_nodes(candidate_b)
            )
