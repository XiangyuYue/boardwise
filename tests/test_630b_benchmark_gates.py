"""630 缝 B：benchmark 闸与证据消费四条（630B-01 / -03 / -05 / -06）。

缝 B 六条里，两条留给裁决（B-02 的 `--target` 是路径还是名字、B-04 的 `root` 缺省
要不要阻断），本文件只钉**已经改掉**的四条：

* **630B-01**：`sources` 闸的「declared input is real」只问 `Path.exists()`——目录、
  spec 自己、越出 root 的绝对路径都算真；
* **630B-03**：answer-leak 的正文侧用裸子串，`ch340x` 会被 `ch340` 误判（路径侧
  `_traces_to` 早已按分隔符判，文档也承诺了这一点）；
* **630B-05**：`--json` 下「`--benchmark` 无 `--target`」的提示被吞进 `else` 分支；
* **630B-06**：`_as_evidence` 静默 strip，`"  ds  "` 与 `"ds"` 在内存里是同一个 id。

夹具全部复用 `test_validate_spec` 的构造器（`spec_json` / `reference` / `build` /
`template_body` / `port` / `fully_cited`），不另立一套 spec 字面量。
"""

from __future__ import annotations

import test_validate_spec as tvs

import pytest

from boardwise import cli
from boardwise.core.blocks import BlockError
from boardwise.engines.validate_spec import validate_spec


def _rules(report) -> list[str]:
    return [finding.rule for gate in report.gates for finding in gate.findings]


def _messages(report) -> str:
    return " ".join(
        finding.message for gate in report.gates for finding in gate.findings
    )


def _spec_with_path(tmp_path, path: str):
    return tvs.build(
        tmp_path,
        tvs.spec_json(
            blocks=[{"id": "a", "template": "ta", "at": [0.0, 0.0],
                     "evidence": ["intent"]}],
            connections=[],
            references=[tvs.reference("intent", "intent", path=path)],
        ),
        {"ta": tvs.template_body("ta", [tvs.port("A")], source="textbook")},
    )


# ------------------------------------------------------------------ 630B-01


def test_b01_a_directory_is_not_a_readable_citation(tmp_path):
    """`exists()` 说「有东西在这里」，闸问的是「这份证据在这里」。

    这一条**直测判据**而不是走 `load_board_spec`：装载器自己就拒了绝对路径与
    `.`，也拒了没有扩展名的相对目录，所以那几种形状到不了这道闸。`_citation_problem`
    是这道闸现在的判据——`""` 只在「一个真的可读文件」时返回。
    """
    from boardwise.engines.validate_spec import _citation_problem

    (tmp_path / "datasheets").mkdir()
    (tmp_path / "real.pdf").write_text("readable", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "doc.pdf").write_text("readable", encoding="utf-8")

    assert _citation_problem("real.pdf", tmp_path, "") == ""
    assert _citation_problem("sub/doc.pdf", tmp_path, "") == ""
    assert "a directory" in _citation_problem("datasheets", tmp_path, "")
    assert _citation_problem("no/such/file.pdf", tmp_path, "") == "not there"
    assert "the spec itself" in _citation_problem(
        "real.pdf", tmp_path, str(tmp_path / "real.pdf")
    )
    assert "no root" in _citation_problem("real.pdf", None, "")


# ------------------------------------------------------------------ 630B-03


def test_b03_a_longer_word_is_not_a_false_accusation(tmp_path):
    """`ch340x` 不许因为「像 `ch340`」被定罪——路径侧早就这样，正文侧同样。"""
    spec = tvs.fully_cited(
        tmp_path, notes=["compared against ch340x_board and its datasheets"]
    )
    report = validate_spec(spec, target="ch340.epro2", benchmark=True)
    assert "answer-leak" not in _rules(report), _messages(report)


def test_b03_a_real_mention_is_still_a_leak(tmp_path):
    """对照组：真的点名前缀（`ch340_golden`）仍然要红。"""
    spec = tvs.fully_cited(
        tmp_path, notes=["copied from ch340_golden page by page"]
    )
    report = validate_spec(spec, target="ch340.epro2", benchmark=True)
    assert "answer-leak" in _rules(report), _messages(report)


# ------------------------------------------------------------------ 630B-05


def test_b05_the_json_run_still_says_which_flag_is_missing(tmp_path, capsys):
    """退出 1 但 stderr 为空：机器消费者拿不到「该给 --target」这个修法。"""
    spec = tvs.fully_cited(tmp_path)
    code = cli.main([
        "validate", "--spec", str(spec.path), "--benchmark", "--json",
    ])
    captured = capsys.readouterr()
    assert code == 1, captured
    assert "note:" in captured.err, captured.err
    assert "--target" in captured.err, captured.err
    assert captured.out.lstrip().startswith("{"), "stdout 仍然只该是一份 JSON"


# ------------------------------------------------------------------ 630B-06


def test_b06_whitespace_in_an_evidence_id_is_refused(tmp_path):
    """id 是身份字段：文件里写 `"  intent  "` 与写 `"intent"` 不是同一件事。"""
    raw = tvs.spec_json(
        blocks=[{"id": "a", "template": "ta", "at": [0.0, 0.0],
                 "evidence": ["  intent  "]}],
        connections=[],
        references=[tvs.reference("intent", "intent", path="intent.md")],
    )
    with pytest.raises(BlockError) as exc:
        tvs.build(tmp_path, raw,
                  {"ta": tvs.template_body("ta", [tvs.port("A")], source="textbook")})
    assert "whitespace" in str(exc.value), str(exc.value)
    assert "intent" in str(exc.value), "错误里要回显文件写的原值"
