"""629B：岛链端到端三条（`outputs/hole629/TRIAGE.md` 缝 B）。

三条都落在 `draw islands propose` 与 `apply` 之间那一段，共同点是**上游的沉默被下游
当成事实**：

* 629B-01：`judgement: []` 时 apply 仍 exit 0，把几何簇原样写成 `auto-1`（无 role），
  `draw compile` 随后按 `role -` 规划候选——「没人判断」在整条链上没留下痕迹；
* 629B-02：同一份判过的提案二次 apply 不幂等，落成「提案是对着另一份声明做的」
  （626B-04 的闸说了实话，但没有说「这份提案已经应用过」），而它默认原地改写
  `--presentation`，于是文档给的复跑命令在成功一次之后必失败；
* 629B-03：语义拒绝（幽灵件 / 一件两岛）从 spec 的 `ValueError` 里漏出来，与「文件
  读不了」同在 exit 2，而 help 写的是 2 =「输入读不出」、5 = 拒绝。

夹具复用 `test_530e_islands_propose_apply`：几何是**注入**的（§5.3 的判据是盒子的
函数），`_three_clusters` 是那颗演示页（`bridge=[T1]` + 三颗待判簇）。
"""

from __future__ import annotations

import json

import test_530e_islands_propose_apply as t530

from boardwise import cli
from boardwise.engines import islandproposal as ip


def _judged(proposal, *, role="primary", name="第一块", index=0):
    """把一条 `accept` 填进提案的 `judgement[]`（§5.4 step ②）。

    `reason` 只引用 `islandId`：§5.5 闸 5 要的是「引用了提案印过的名字」，不是
    「理由写得对」——那句话本来就不由机器判。
    """
    document = json.loads(json.dumps(proposal.document))
    cluster = document["clusters"][index]
    document["judgement"] = [{
        "islandId": cluster["islandId"],
        "verdict": "accept",
        "role": role,
        "name": name,
        "reason": cluster["islandId"],
    }]
    return document


# ================================================================== 629B-01
# 零判断的提案一路走到合法候选：apply exit 0，写出的岛没有 `role`。


def test_b01_a_proposal_with_no_judgement_writes_no_document(monkeypatch):
    """`judgement: []` 是「§5.4 step ② 还没答」，不是「每颗岛都判成了几何簇」。

    旧读数：apply 把它当 §5.6 L0 的 fallback 落盘（`auto-1`，无 role），只多印一句
    `judged: 0`；下游拿到的是与「判过」逐字节同形的 spec，compile 按 `role -` 出候选。
    """
    circuit, payload, book = t530._three_clusters(monkeypatch)
    proposal = ip.build_proposal(circuit, payload, book)
    document = json.loads(json.dumps(proposal.document))
    assert document["judgement"] == []

    application = ip.apply_proposal(document, payload)

    assert application.result.written is False, application.result.report
    assert application.spec is None
    report = application.result.report
    assert report["applied"] is False
    assert report["gate"] == ip.APPLY_GATE_INPUT, report
    assert "judgement" in report["why"], report
    assert [island.id for island in application.result.islands] == ["bridge"], (
        "拒绝时另一半原样退回：声明的岛一颗不少"
    )


def test_b01b_the_cli_refuses_and_names_the_empty_judgement(
    monkeypatch, tmp_path, capsys
):
    """键在、值是 `[]`：读者要知道该去补 `judgement[]`，不是去查文件路径。"""
    circuit, payload, book = t530._three_clusters(monkeypatch)
    proposal = ip.build_proposal(circuit, payload, book)
    proposal_path = tmp_path / "islands-proposal.json"
    spec_path = tmp_path / "partial.presentation.json"
    out_path = tmp_path / "applied.presentation.json"
    ip.write_proposal(proposal.document, proposal_path)
    t530._write(payload, spec_path)

    code = cli.main([
        "draw", "islands", "apply",
        "--proposal", str(proposal_path),
        "--presentation", str(spec_path),
        "--out-spec", str(out_path),
    ])
    captured = capsys.readouterr()

    assert code == 5, captured
    assert not out_path.exists(), "零判断不许写出任何 spec"
    assert "judgement" in captured.err, captured.err


# ================================================================== 629B-02
# 同一份判过的提案二次 apply：落成「对着另一份声明做的」，而不是「已经应用过」。


def test_b02_applying_the_same_proposal_twice_writes_the_same_bytes(monkeypatch):
    """幂等的定义是逐字节：同一份提案、已应用过的 document，输出不许动。"""
    circuit, payload, book = t530._three_clusters(monkeypatch)
    proposal = ip.build_proposal(circuit, payload, book)
    document = _judged(proposal)

    first = ip.apply_proposal(document, payload)
    assert first.result.written is True, first.result.report
    assert first.payload is not None
    # 判过的 `auto-1` 带着 role 与 name；另外两颗簇是 §5.6 L0 的几何簇。
    assert [island["id"] for island in first.payload["islands"]] == [
        "bridge", "auto-1", "auto-2", "auto-3",
    ]

    second = ip.apply_proposal(document, first.payload)

    assert second.result.written is True, second.result.report
    assert second.payload == first.payload, "二次 apply 必须逐字节相同"
    report = second.result.report
    assert report["applied"] is True
    assert report["alreadyApplied"] == ["auto-1", "auto-2", "auto-3"], report
    assert report["islands"] == [], "没有新岛可写"


def test_b02c_a_judgement_that_arrives_later_replaces_its_fallback_in_place(monkeypatch):
    """先落一遍、后判另一颗：第二遍不许因为「id 已被自己上一遍占用」而拒。

    同一 id、同一 parts 是**同一块**，只是上一遍还没有 role 与 name；判到了就
    就地替换（顺序不变），而不是加第二份，也不是 gate 0 的「两个块共用一个名字」。
    """
    circuit, payload, book = t530._three_clusters(monkeypatch)
    proposal = ip.build_proposal(circuit, payload, book)
    document = _judged(proposal)
    first = ip.apply_proposal(document, payload)
    assert first.result.written is True

    later = json.loads(json.dumps(document))
    later["judgement"].append({
        "islandId": "auto-2",
        "verdict": "accept",
        "role": "secondary",
        "name": "第二块",
        "reason": "auto-2",
    })

    second = ip.apply_proposal(later, first.payload)

    assert second.result.written is True, second.result.report
    report = second.result.report
    assert report["alreadyApplied"] == ["auto-1", "auto-3"], report
    assert [row["islandId"] for row in report["islands"]] == ["auto-2"], report
    islands = {island["id"]: island for island in second.payload["islands"]}
    assert list(islands) == ["bridge", "auto-1", "auto-2", "auto-3"], "顺序不许变"
    assert islands["auto-2"]["role"] == "secondary"
    assert islands["auto-2"]["name"] == "第二块"


def test_b02b_the_second_apply_rewrites_the_same_file_in_place(
    monkeypatch, tmp_path, capsys
):
    """默认原地改写 `--presentation`：文档里的复跑命令成功一次之后不许失败。"""
    circuit, payload, book = t530._three_clusters(monkeypatch)
    proposal = ip.build_proposal(circuit, payload, book)
    proposal_path = tmp_path / "islands-proposal.json"
    spec_path = tmp_path / "partial.presentation.json"
    ip.write_proposal(_judged(proposal), proposal_path)
    t530._write(payload, spec_path)

    command = [
        "draw", "islands", "apply",
        "--proposal", str(proposal_path),
        "--presentation", str(spec_path),
    ]
    assert cli.main(command) == 0, capsys.readouterr()
    first_bytes = spec_path.read_bytes()

    assert cli.main(command) == 0, capsys.readouterr()
    assert spec_path.read_bytes() == first_bytes, "第二次原地改写必须是空操作"
    assert "already" in capsys.readouterr().out

    # 判过的那一颗岛在文件里仍然只有一份，且仍带着判断给的 role 与 name。
    islands = json.loads(spec_path.read_text(encoding="utf-8"))["islands"]
    assert [island["id"] for island in islands] == [
        "bridge", "auto-1", "auto-2", "auto-3",
    ]
    assert islands[1]["role"] == "primary"
    assert islands[1]["name"] == "第一块"


# ================================================================== 629B-03
# 语义拒绝走 5（读进去了、判下来不成立），2 只留「输入读不出」。


def test_b03_a_cluster_naming_a_part_this_spec_does_not_have_is_gate_zero(monkeypatch):
    """幽灵件：提案说的这件东西不在这份 presentation 里 —— 两份文档对不上。"""
    circuit, payload, book = t530._three_clusters(monkeypatch)
    proposal = ip.build_proposal(circuit, payload, book)
    document = _judged(proposal)
    document["clusters"][0]["parts"][0]["id"] = "R9"

    application = ip.apply_proposal(document, payload)

    assert application.result.written is False, application.result.report
    report = application.result.report
    assert report["gate"] == ip.APPLY_GATE_INPUT, report
    assert "R9" in report["why"], report


def test_b03b_a_part_a_declared_island_already_holds_cannot_be_named_again(monkeypatch):
    """一件两岛：`bridge` 已经持有 T1，判出来的岛不许再点它一次。"""
    circuit, payload, book = t530._three_clusters(monkeypatch)
    proposal = ip.build_proposal(circuit, payload, book)
    document = _judged(proposal)
    document["clusters"][0]["parts"].append(
        {"id": "T1", "symbolRef": "XFMR", "value": "EE25", "pins": 4}
    )

    application = ip.apply_proposal(document, payload)

    assert application.result.written is False, application.result.report
    report = application.result.report
    assert report["gate"] == ip.APPLY_GATE_INPUT, report
    assert "T1" in report["why"], report
    assert "bridge" in report["why"], report


def test_b03c_the_two_codes_split_on_readability_not_on_the_verdict(
    monkeypatch, tmp_path, capsys
):
    """同一族语义拒绝必须同一个码：2 给读不出的输入，5 给读得懂但不成立的文档。"""
    circuit, payload, book = t530._three_clusters(monkeypatch)
    proposal = ip.build_proposal(circuit, payload, book)
    document = _judged(proposal)
    document["clusters"][0]["parts"][0]["id"] = "R9"
    ghost_path = tmp_path / "ghost.json"
    ghost_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    spec_path = tmp_path / "partial.presentation.json"
    t530._write(payload, spec_path)

    missing = cli.main([
        "draw", "islands", "apply",
        "--proposal", str(tmp_path / "not-here.json"),
        "--presentation", str(spec_path),
        "--out-spec", str(tmp_path / "a.presentation.json"),
    ])
    assert missing == 2, "读不到的输入仍然是 2"

    refused = cli.main([
        "draw", "islands", "apply",
        "--proposal", str(ghost_path),
        "--presentation", str(spec_path),
        "--out-spec", str(tmp_path / "b.presentation.json"),
    ])
    captured = capsys.readouterr()

    assert refused == 5, captured
    assert not (tmp_path / "b.presentation.json").exists()
    assert "R9" in captured.err, captured.err
