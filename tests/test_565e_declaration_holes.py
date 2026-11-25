"""565e：PresentationSpec 声明闭合的两条洞（S4-1 / S4-2）。

`modules[].freeParts`（548L）是「这一组里属于本岛、但不绑核心角色的两脚支路」
的声明。它只被 `ic-periphery` 与 `mixed-island` 两个文法消费；在这之前，
文档层对它的**消费闭合性**什么都没说，于是有两个静默面：

* **S4-1**：同一模块的 `core` 与 `freeParts` 点名同一件——解析层原样收下，
  矛盾只被无关的「2 脚不能当 core」拒因掩盖（换成多脚件或 page 路径就不报）。
  合同：`from_dict` 必须拒绝，话术同时点名 `modules[<id>].core` 与
  `modules[<id>].freeParts[i]`，并说明一件只能属于一个角色。
* **S4-2**：模块声明了 `freeParts`，但**有效文法**（模块 `grammarRef`，缺省
  取文档 `grammarRef`）不是这两个文法之一——声明被收下、零披露、几何零影响。
  合同：`from_dict` 必须拒绝，话术点名有效文法名，并说明只有那两个文法消费它。

反向保护（这些必须仍然能解析/编译）：`mixed-island` + `freeParts`、
`ic-periphery` + `freeParts`、不带 `freeParts` 的 `voltage-divider` 基线。

本文件不用 `tmp_path`（本机 Python 3.14 在 Windows 上把 `os.mkdir(mode=0o700)`
写成受限 DACL，`tmp_path` 会假红）；CLI 用例的中间件写在 `.tmp_565e/` 下。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from boardwise import cli
from boardwise.core.presentationspec import PresentationSpec, PresentationSpecError

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "drawapply"
WORK = ROOT / ".tmp_565e" / "test_page"

MIXED = "mixed-island"
IC = "ic-periphery"
DIVIDER = "voltage-divider"


# ------------------------------------------------------------------ 手写夹具
#
# 一份最小的展示文档：一个模块，`parts` 由用例给。`core`/`freeParts`/`grammarRef`
# 只在用例声明时写入，这样「不声明」就真的一个键都没有。
def module(parts: list[str], **stated) -> dict:
    body: dict = {"id": "island", "parts": list(parts), "role": "the island"}
    body.update(stated)
    return body


def payload(module_body: dict, grammar: str | None = None) -> dict:
    root: dict = {"modules": [module_body]}
    if grammar is not None:
        root["grammarRef"] = grammar
    return root


def parse(module_body: dict, grammar: str | None = None) -> PresentationSpec:
    return PresentationSpec.from_dict(payload(module_body, grammar))


# ------------------------------------------------------- S4-1：core 与 freeParts
#                                         同一件 = 两个角色，解析层拒绝


def test_s4_1_a_part_cannot_be_both_the_core_and_a_free_part():
    """S4-1 因果行：`core` 与 `freeParts[0]` 点名同一件 → 解析期拒绝。

    用四脚件当 core，缺口就不是「2 脚不能当 core」那条无关拒因——矛盾本身
    必须被点名。
    """
    with pytest.raises(PresentationSpecError) as caught:
        parse(module(["J1", "C9"], core="J1", freeParts=["J1"]), MIXED)
    text = str(caught.value)
    assert "modules[island].core" in text, text
    assert "modules[island].freeParts[0]" in text, text
    assert "role" in text, text


def test_s4_1_a_two_terminal_core_is_refused_for_the_contradiction_not_the_pin_count():
    """同一件是 2 脚电阻时也一样：拒绝理由必须是「一件一个角色」，不是脚数。

    这正是缺口原来的掩盖方式——换文法/换件就变成别的拒因或干脆不报。
    """
    with pytest.raises(PresentationSpecError) as caught:
        parse(module(["R1", "R2"], core="R1", freeParts=["R1"]), DIVIDER)
    text = str(caught.value)
    assert "modules[island].freeParts[0]" in text, text
    assert "role" in text, text
    assert "two-terminal" not in text, text


def test_s4_1_the_page_path_refuses_in_the_parse_layer_before_any_sheet(capsys):
    """带 `--page-box` 的 page 路径同样在解析层拒绝，不靠几何/脚数拒因。

    page 编译入口先读 PresentationSpec；声明矛盾必须在读文档时停住，而不是
    先要一张纸、再在页面上发现画不出来。
    """
    base = json.loads((FIXTURES / "divider.presentation.json").read_text(encoding="utf-8"))
    base["modules"][0]["core"] = "R1"
    base["modules"][0]["freeParts"] = ["R1"]
    WORK.mkdir(parents=True, exist_ok=True)
    stated = WORK / "conflict.presentation.json"
    stated.write_text(json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8")
    out = WORK / "out_conflict_refused"
    out.mkdir(parents=True, exist_ok=True)

    code = cli.main([
        "draw", "compile",
        "--circuit", str(FIXTURES / "divider.circuit.json"),
        "--presentation", str(stated),
        "--profiles", str(FIXTURES / "library.json"),
        "--page-box", "0,0,1170,825",
        "--out", str(out),
    ])
    printed = capsys.readouterr()
    assert code == 5, printed.err
    assert "modules[divider].core" in printed.err, printed.err
    assert "modules[divider].freeParts[0]" in printed.err, printed.err
    assert not list(out.glob("*.svg")), "a refused document must not fall through to geometry"


# -------------------------------------- S4-2：freeParts 在无消费者文法下被吞掉


def test_s4_2_free_parts_under_a_grammar_that_does_not_consume_them_is_refused():
    """S4-2 因果行：`voltage-divider` + `freeParts` 必须在解析期拒绝。

    声明只有 `ic-periphery` / `mixed-island` 会读；别的文法收下就是静默丢弃，
    而「静默丢弃」正是这条洞。
    """
    with pytest.raises(PresentationSpecError) as caught:
        parse(module(["J1", "C9"], freeParts=["C9"]), DIVIDER)
    text = str(caught.value)
    assert "freeParts" in text, text
    assert DIVIDER in text, text
    assert IC in text and MIXED in text, text
    assert "silently" in text or "consumed" in text, text


def test_s4_2_the_effective_grammar_is_the_modules_own_first():
    """有效文法 = 模块 `grammarRef`，缺省才取文档 `grammarRef`。

    两个方向都钉住：模块写 `voltage-divider`、文档写 `mixed-island` → 仍拒绝
    并点名 `voltage-divider`；反之模块写 `mixed-island` → 合法（模块自己的
    声明优先，文档的缺省不该把它改判）。
    """
    with pytest.raises(PresentationSpecError) as caught:
        parse(
            module(["J1", "C9"], freeParts=["C9"], grammarRef=DIVIDER),
            MIXED,
        )
    text = str(caught.value)
    assert DIVIDER in text, text
    assert "modules[island].grammarRef" in text, text

    accepted = parse(module(["J1", "C9"], freeParts=["C9"], grammarRef=MIXED), DIVIDER)
    assert accepted.modules[0].free_parts == ["C9"]
    assert accepted.grammar_ref == DIVIDER


def test_s4_2_a_document_with_no_grammar_consumes_no_free_parts():
    """没有文法就没有消费者：空文法 + `freeParts` 同样是拒绝，不是默认收下。"""
    with pytest.raises(PresentationSpecError) as caught:
        parse(module(["J1", "C9"], freeParts=["C9"]))
    text = str(caught.value)
    assert "freeParts" in text, text
    assert "grammar" in text and "empty" in text, text


def test_s4_2_an_empty_free_parts_list_is_not_a_declaration():
    """空 `freeParts` 不受影响：它不声明任何东西，序列化时照旧省略。"""
    spec = parse(module(["R1", "R2"], freeParts=[]), DIVIDER)
    assert spec.modules[0].free_parts == []
    assert "freeParts" not in spec.to_jsonable()["modules"][0]


# ---------------------------------------------------- 反向保护：合法声明仍能读


@pytest.mark.parametrize("grammar", [MIXED, IC])
def test_r1_the_two_consuming_grammars_still_accept_free_parts(grammar: str):
    """`mixed-island` / `ic-periphery` + `freeParts` 必须仍然解析并原样往返。"""
    spec = parse(module(["J1", "C9"], core="J1", freeParts=["C9"]), grammar)
    assert spec.modules[0].free_parts == ["C9"]
    again = PresentationSpec.from_dict(spec.to_jsonable())
    assert again.to_jsonable() == spec.to_jsonable()
    assert again.sha256() == spec.sha256()


def test_r2_the_module_grammar_is_enough_without_a_document_one():
    """模块自己写了消费文法时，文档可以一个字都不写 `grammarRef`。"""
    spec = parse(module(["J1", "C9"], freeParts=["C9"], grammarRef=MIXED))
    assert spec.grammar_ref == ""
    assert spec.modules[0].grammar_ref == MIXED


def test_r3_a_voltage_divider_without_free_parts_still_compiles(capsys):
    """不带 `freeParts` 的 `voltage-divider` 基线：原样解析，原样编译出候选。"""
    spec = PresentationSpec.load(FIXTURES / "divider.presentation.json")
    assert spec.modules[0].free_parts == []
    assert "freeParts" not in spec.to_jsonable()["modules"][0]

    out = WORK / "out_baseline"
    out.mkdir(parents=True, exist_ok=True)
    code = cli.main([
        "draw", "compile",
        "--circuit", str(FIXTURES / "divider.circuit.json"),
        "--presentation", str(FIXTURES / "divider.presentation.json"),
        "--profiles", str(FIXTURES / "library.json"),
        "--out", str(out),
    ])
    printed = capsys.readouterr()
    assert code == 0, printed.err
    assert "3 candidate(s)" in printed.out, printed.out
    assert len(list(out.glob("*.svg"))) == 3
