"""548P137：服务退休后的最佳失败答案不能回退到首个 C2 拒绝。

548P126 已证明真实 MCU 的 C2 会沿 13→3→1 退休并在 offset=0 达到 5/5。
本批只钉住另一个独立因果点：若这个 5/5 答案随后被下游旗房拒绝，返回给
上层诊断的必须是首个完整服务答案，而不是循环最早保存的 C2=13 拒绝。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from boardwise.engines import drawcompiler as dc


def _plan(host: str, seated: bool):
    cell = SimpleNamespace(host_token=host) if seated else None
    return SimpleNamespace(
        group_id="service:C2",
        seated=seated,
        cells=(cell,) if cell is not None else (),
        tried_hosts=() if seated else (("C2", host),),
    )


def _placed():
    return dc._Placement(origins={"U1": (0.0, 0.0)}, poses={})


def test_failed_downstream_returns_first_complete_service_answer(monkeypatch):
    """13/3 拒绝后 1 已全落座，不能回报最初那份 C2=13 拒绝。"""
    attempts = iter((("13", False), ("3", False), ("1", True)))
    calls = []

    def bind(origins, poses, offset, bans):
        host, seated = next(attempts)
        calls.append((offset, host, seated, dict(bans)))
        return (_plan(host, seated),)

    monkeypatch.setattr(dc, "_service_flag_room_ok", lambda *_args: False)
    plans, _origins, _poses = dc._service_seats_in_flag_room(
        None, _placed(), bind, feet=3,
    )

    assert [(offset, host, seated) for offset, host, seated, _ in calls] == [
        (0, "13", False), (0, "3", False), (0, "1", True),
    ]
    assert plans[0].seated
    assert plans[0].cells[0].host_token == "1"


def test_no_complete_service_answer_keeps_the_original_first_refusal(monkeypatch):
    """没有任何完整服务答案时，仍保留旧的首个拒绝，不伪造落座。"""
    attempts = iter((("13", False), ("3", False)))

    def bind(origins, poses, offset, bans):
        host, seated = next(attempts)
        return (_plan(host, seated),)

    monkeypatch.setattr(dc, "_service_flag_room_ok", lambda *_args: False)
    plans, _origins, _poses = dc._service_seats_in_flag_room(
        None, _placed(), bind, feet=2,
    )

    assert not plans[0].seated
    assert plans[0].tried_hosts == (("C2", "13"),)


def test_complete_answer_that_passes_downstream_still_returns_immediately(monkeypatch):
    """下游通过的完整答案保持原有立即返回路径。"""
    def bind(origins, poses, offset, bans):
        return (_plan("1", True),)

    monkeypatch.setattr(dc, "_service_flag_room_ok", lambda *_args: True)
    plans, _origins, _poses = dc._service_seats_in_flag_room(
        None, _placed(), bind, feet=3,
    )
    assert plans[0].seated
    assert plans[0].cells[0].host_token == "1"
