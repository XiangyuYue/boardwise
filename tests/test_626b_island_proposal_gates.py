"""626B：岛提案入口六条洞（`outputs/hole626/TRIAGE.md` 缝 B）。

全部落在 `engines/islandproposal.py` 与 `cli.py` 的 `draw islands` 段。两条主题：
**契约之间的一致性要检查**（提案的 `declared[]` 与 presentation 的 `islands[]` 不是同一份
文档的证据），以及**「测不出」的三张脸要分开说**（电路里没有 / 库缺符号 / 全页都测不出）。

夹具复用 `test_530e_islands_propose_apply`：它的 `_inject(monkeypatch, table)` 是几何
**注入**（§5.3 的判据是盒子的函数，不靠探针碰巧落位），`_three_clusters` 是演示页。
"""

from __future__ import annotations

import json

import pytest

import test_530e_islands_propose_apply as t530

from boardwise.engines import islandproposal as ip

PROV = t530.PROV


def _pair_circuit():
    """U1（6 脚）挂两颗电容：C1 距 U1 5 units，C2 在页面另一头。"""
    return t530._circuit(
        [
            t530._part("U1", "IC6"),
            t530._part("C1", "C0402"),
            t530._part("C2", "C0402"),
        ],
        [
            t530._net("VCC", "power", ["U1.1"]),
            t530._net("GND", "gnd", ["C1.2", "C2.2"]),
            t530._net("A", "signal", ["U1.2", "C1.1"]),
            t530._net("B", "signal", ["U1.3", "C2.1"]),
        ],
    )


def _pair_boxes():
    return {
        "U1": t530._box(0.0, 0.0, 100.0, 100.0),
        "C1": t530._box(105.0, 0.0, 20.0, 20.0),
        "C2": t530._box(600.0, 0.0, 20.0, 20.0),
    }


def _pair(payload_extra=None):
    payload = t530._payload(
        ["U1", "C1", "C2"], islands=[{"id": "core", "parts": ["U1"]}]
    )
    if payload_extra:
        payload.update(payload_extra)
    return payload


def _book():
    book = t530._book()
    book.setdefault("C0402", t530._passive("C0402"))
    return book


# ================================================================== 626B-01
# 已声明的锚对未声明件永不可见，诊断还写「nearest: none」。


def test_b01_a_declared_anchor_is_named_even_though_it_cannot_anchor(monkeypatch):
    """U1（6 脚）已经声明成 `core`，两颗电容未声明，C1 距 U1 只有 5 units。

    旧读数：两脚件没有锚可挂 ⇒ 各成一个单件岛，`why` 写「nearest: none」——
    与「页面上根本没有多脚件」逐字相同。§5.3 的锚确实只取**未声明**件，所以
    规则不动；但诊断必须点名「最近的 ≥3 脚件是 U1，它已声明，所以当不了锚」，
    并在这块岛因此被逐件拆开时留一条 note。
    """
    t530._inject(monkeypatch, _pair_boxes())
    proposal = ip.build_proposal(_pair_circuit(), _pair(), _book())

    assert len(proposal.clusters) == 2, [c.parts for c in proposal.clusters]
    why = {cluster.anchor: cluster.evidence["why"] for cluster in proposal.clusters}
    assert "nearest: none" not in why["C1"], why["C1"]
    assert "U1" in why["C1"], why["C1"]
    assert "declared" in why["C1"], why["C1"]
    notes = " ".join(proposal.document["notes"])
    assert "already declared" in notes, notes


# ================================================================== 626B-02
# 12 件全部测不出时仍 exit 0 并写出空提案。


def test_b02_a_page_where_nothing_can_be_measured_is_exit_five():
    """文档点名了件，但每一件都测不出：`clusters` 空、声明又不完整。

    旧读数：`cli.py` 只在「一个件都没点名」时 exit 5，这种页面写出一份空提案
    并 exit 0 —— 与 help 承诺相反。判据收进 `propose_outcome`，CLI 与用例同源。
    """
    circuit = t530._circuit(
        [t530._part("U1", "IC6"), t530._part("R1", "R0402")], []
    )
    book: dict = {}  # 一个符号都没有 ⇒ 两件都测不出
    proposal = ip.build_proposal(circuit, t530._payload(["U1", "R1"]), book)

    assert proposal.empty
    assert proposal.declared.complete is False
    code, message = ip.propose_outcome(proposal)
    assert code == 5, (code, message)
    assert "measured" in message or "measure" in message, message


def test_b02b_a_fully_declared_spec_still_proposes_nothing_with_exit_zero(monkeypatch):
    """对照组：声明已覆盖全页时「无事可提」是正常结果，仍 exit 0。"""
    circuit, payload, book = t530._three_clusters(monkeypatch)
    proposal = ip.build_proposal(circuit, payload, book)
    complete = ip.build_proposal(
        circuit,
        dict(payload, islands=[
            {"id": "a", "parts": list(proposal.declared.parts)},
        ]),
        book,
    )
    assert complete.declared.complete
    assert ip.propose_outcome(complete)[0] == 0


# ================================================================== 626B-03
# `unresolved` 诊断把「库缺 symbolRef」说成「电路或库都没有」。


def test_b03_the_two_reasons_a_part_cannot_be_measured_are_told_apart():
    """GHOST 不在电路里，R1 在电路里但库缺它的符号 —— 两种事实，两句话。

    旧读数：两处文案都写「the circuit or the library does not have them」，
    读者无从知道该去补电路还是补库。
    """
    circuit = t530._circuit(
        [t530._part("U1", "IC6"), t530._part("R1", "R0402")], []
    )
    book = {"IC6": t530._ic("IC6", 6)}
    proposal = ip.build_proposal(circuit, t530._payload(["U1", "R1", "GHOST"]), book)

    assert proposal.document["unresolved"] == ["GHOST", "R1"]
    notes = " ".join(proposal.document["notes"])
    assert "not in the circuit" in notes, notes
    assert "no symbol" in notes, notes
    reasons = proposal.document["unresolvedReasons"]
    assert "circuit" in reasons["GHOST"], reasons
    assert "library" in reasons["R1"], reasons


# ================================================================== 626B-04
# `apply` 从不读提案里的 `declared[]`。


def test_b04_a_proposal_made_against_another_declaration_is_refused(monkeypatch):
    """提案里的 `declared[]` 与 presentation 的 `islands[]` 不一致时不许静默取后者。

    旧读数：`apply_proposal` 只 `read_declared(payload)`，提案里那份副本从不比较，
    于是提案之后改过 presentation 也照写，落盘的东西与 judged 的东西不是一份。
    """
    circuit, payload, book = t530._three_clusters(monkeypatch)
    proposal = ip.build_proposal(circuit, payload, book)
    document = json.loads(json.dumps(proposal.document))
    document["declared"] = [{"id": "core", "role": "", "parts": ["U1"]}]

    application = ip.apply_proposal(document, payload)

    assert application.result.written is False
    assert application.spec is None
    report = application.result.report
    assert "different declaration" in report["why"], report
    assert "core" in report["why"], report


# ================================================================== 626B-05
# `judgement: []` 也落成 `auto-*` 岛（六个闸对「零判断」真空成立）。


def test_b05_a_proposal_with_no_judgement_is_refused_not_written(monkeypatch):
    """§5.6 L0 是**判断过、栽在某道闸**的 fallback，不是「一个判断都没有」。

    626B 只把零判断写进报告（`judged: 0` 加一句 fallback），`written` 仍是 True；
    629B-01 量到那条链的下游：`draw compile` 按 `role -` 规划候选，于是「没人判断」
    的分区带着机器名进了页产物。现在零判断在 gate 0 就被拒，报告仍然说出
    `judged: 0` —— 「一个判断都没有」与「判了三条」在报告里依旧分得开，只是前者
    不再被认证成一份画出来的分区。
    """
    circuit, payload, book = t530._three_clusters(monkeypatch)
    proposal = ip.build_proposal(circuit, payload, book)
    application = ip.apply_proposal(proposal.document, payload)

    assert application.result.written is False, application.result.report
    assert application.spec is None
    report = application.result.report
    assert report["judged"] == 0, report
    assert report["gate"] == ip.APPLY_GATE_INPUT, report
    assert "judgement" in report["why"], report


# ================================================================== 626B-06
# 提案里的未知键被静默忽略（无 schema 校验）。


def test_b06_an_unknown_key_in_the_proposal_is_refused_not_ignored(monkeypatch):
    """把 `judgement` 拼成 `judgements` 的提案，旧读数照写 `auto-*` 岛。

    判断入口是 §5.4 的闭合契约：键拼错不是「另一种说法」，是「这份提案不是
    这个版本能读的文档」，应当作为输入错误说出来（CLI 因此 exit 2）。
    """
    circuit, payload, book = t530._three_clusters(monkeypatch)
    proposal = ip.build_proposal(circuit, payload, book)
    document = json.loads(json.dumps(proposal.document))
    document["judgements"] = []

    with pytest.raises(ip.IslandsProposalError) as exc:
        ip.apply_proposal(document, payload)
    assert "judgements" in str(exc.value), str(exc.value)
