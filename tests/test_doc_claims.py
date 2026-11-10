"""文档声明钉（doc-claims audit）：让重要声明没法再悄悄过期（issue #57  finding #7，
岳 2026-10-03 裁「病在文案」）。

仓库没有 CI，"实时更新文案"的实现方式就是这组测试：**load-bearing 的声明配机器可验的
钉子，谁让声明失效，谁的测试当场红**。v1 家族 = README 的评审纪律段 vs 规则常量引用
的取证板与评审集分堆。往这个文件里加新声明钉的规矩：

1. 声明必须是**机器可验**的（能量化的、能对拍的、能 grep 判真伪的）；验不了的散文
   不许写成断言式口号——要么改写，要么补一个能验的机制。
2. 钉子读**源头**（代码常量/评审集记录/argparse 定义），不读二手转述。
3. 每条钉子注释里写明它护的是哪句话、失效时的样子。
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_readme_raw = (REPO / "README.md").read_text(encoding="utf-8")
#: 声明钉按整句找——README 的换行是排版不是语义，先把空白归一再对拍。
README = re.sub(r"\s+", " ", _readme_raw)
#: 审查 SOP 的正文（139 收口的两条声明钉读这里：§3.1 的「按网找协同器件的 N 条规则」
#: 与 §3.1b 的 set-rail 双写）。同样先归空白再对拍。
SOP = (REPO / "docs" / "review-sop.md").read_text(encoding="utf-8")

#: 旧的绝对化口号（#7 的病灶原文，中英两版）：README 曾经断言验收集「从不参与调参」，
#: 而 params 的两条常量恰恰是在 holdout 板的证据上定出来的。
ABSOLUTE_CLAIMS = ("never used for tuning", "不许参与规则调试")
#: 替代它的诚实形态（README 现在的措辞钉）：机制无法泄漏 + 早期常量如实披露。
DISCLOSURE_TOKENS = (
    "predate the split discipline",
    "cannot leak",
    "先于分堆制度诞生",
)
DENOMINATOR_TOKEN = "holdout records enter no denominator"

_CONSTANT_RE = re.compile(r"^([A-Z][A-Z0-9_]{3,}) = ", re.MULTILINE)
_DESIGNATOR_RE = re.compile(r"\b[URCLDJQ]\d+\b")
_EVIDENCE_VERBS = re.compile(r"实测|measured|witness|oracle|见证|ruling|signed", re.IGNORECASE)
_EVIDENCE_BOARDS_RE = re.compile(r"^#: evidence-boards:\s*(.+)$", re.MULTILINE)


def _rules_comment_blocks() -> list[tuple[str, str, Path]]:
    """Every (constant name, the `#:` comment block directly above it, file)."""
    out: list[tuple[str, str, Path]] = []
    for path in sorted((REPO / "src" / "boardwise" / "rules").glob("*.py")):
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            match = re.match(r"^([A-Z][A-Z0-9_]{3,}) = ", line)
            if not match:
                continue
            block: list[str] = []
            cursor = index - 1
            while cursor >= 0 and lines[cursor].startswith("#:"):
                block.append(lines[cursor])
                cursor -= 1
            out.append((match.group(1), "\n".join(reversed(block)), path))
    return out


def _constants_citing_board_evidence() -> list[tuple[str, str, Path, list[str]]]:
    """Tuning constants whose comment cites designator evidence, with boards declared."""
    found = []
    for name, block, path in _rules_comment_blocks():
        if not (_DESIGNATOR_RE.search(block) and _EVIDENCE_VERBS.search(block)):
            continue
        declaration = _EVIDENCE_BOARDS_RE.search(block)
        boards = []
        if declaration:
            boards = [item.strip() for item in declaration.group(1).split(",") if item.strip()]
        found.append((name, block, path, boards))
    return found


def _reviewset_splits() -> dict[str, str]:
    """``board name -> split_default`` for every annotation record that says one."""
    splits: dict[str, str] = {}
    for record in sorted((REPO / "reviewsets").glob("*.json")):
        try:
            payload = json.loads(record.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        board = str(payload.get("board") or record.stem)
        split = str(payload.get("split_default") or "")
        if split:
            splits[board] = split
    return splits


def _resolve_board(fragment: str, splits: dict[str, str]) -> str | None:
    """The split of the one reviewset board this fragment names, or ``None``."""
    matches = [split for board, split in splits.items() if fragment in board]
    return matches[0] if len(matches) == 1 else None


def test_every_evidence_citing_constant_declares_its_boards():
    """引用取证板的常量必须声明是哪些板——否则下一条常量又会悄悄在 holdout 上定出来。"""
    missing = [
        f"{name} ({path.name})"
        for name, _block, path, boards in _constants_citing_board_evidence()
        if not boards
    ]
    assert missing == [], (
        "these constants cite board evidence but declare no `evidence-boards:` line: "
        + ", ".join(missing)
    )


def test_every_declared_board_resolves_to_one_reviewset_record():
    """声明的板必须能唯一解析到评审集记录——写个模糊名字等于没声明。"""
    splits = _reviewset_splits()
    bad: list[str] = []
    for name, _block, path, boards in _constants_citing_board_evidence():
        for fragment in boards:
            if _resolve_board(fragment, splits) is None:
                bad.append(f"{name} ({path.name}): {fragment!r}")
    assert bad == [], "evidence-boards fragments that resolve to no single record: " + ", ".join(bad)


def test_readme_never_resurrects_the_absolute_claim():
    """旧口号一个字都不许回来——它曾经是真话的对立面（#7），中英两版同查。"""
    for claim in ABSOLUTE_CLAIMS:
        assert claim not in README


def test_readme_states_the_mechanism_and_the_disclosure():
    """替代形态的两半都在：harness 结构上无法泄漏 + 早期常量如实披露。"""
    for token in (*DISCLOSURE_TOKENS, DENOMINATOR_TOKEN):
        assert token in README, f"README's eval paragraph lost {token!r}"


def test_holdout_evidence_and_the_readme_stay_consistent():
    """核心不变量：只要还有常量的取证板是 holdout，README 就必须带着那句披露。

    反过来：哪天常量全部改在 dev 堆上标定（evidence-boards 里不再有 holdout），
    这条测试允许 README 换成无前缀的强声明——但那是另一次有意的文案决定，
    不是悄悄发生的。
    """
    splits = _reviewset_splits()
    holdout_citing: list[str] = []
    for name, _block, _path, boards in _constants_citing_board_evidence():
        for fragment in boards:
            if _resolve_board(fragment, splits) == "holdout":
                holdout_citing.append(f"{name} ← {fragment}")
    if holdout_citing:
        assert "predate the split discipline" in README, (
            "constants tuned on holdout evidence exist ("
            + ", ".join(holdout_citing)
            + ") but README dropped the disclosure — the claim outran the data again"
        )


def _cli_registration_text() -> str:
    """All argparse registration sources, after the 540 command-surface split."""
    package = REPO / "src" / "boardwise"
    sources = [package / "cli.py", *sorted((package / "commands").rglob("*.py"))]
    return "\n".join(path.read_text(encoding="utf-8") for path in sources)


def test_the_harness_default_stays_leak_proof():
    """审计确认过的机制钉死：`--split` 默认 `dev`（holdout 不显式给就进不了分母）。"""
    source = _cli_registration_text()
    split_block = re.search(
        r'add_argument\(\s*"--split",.*?default="(?P<default>[a-z]+)"', source, re.DOTALL
    )
    assert split_block is not None, "the --split argument definition was not found"
    assert split_block.group("default") == "dev", (
        "--split's default moved off dev — the harness's leak-proof claim in README "
        "is only true while holdout is opt-in, never the default"
    )


# ============================================================ issue #58-#60
#: 命令面抽取：README/SKILL 提到的命令必须与 cli.py + commands/ 的注册表**双向**对拍（issue #60
#: 的「contract-drift 同一把尺子对准自己」+ issue #62 的反向那一半）。只数**首词是真
#: 命令**的序列——散文里的「boardwise daemon」不是命令提及（:data:`PROSE_AFTER_BOARDWISE`
#: 逐个声明）；真命令的第二个词必须是它注册过的子命令。
def _cli_commands() -> tuple[set[str], dict[str, set[str]]]:
    """（顶层命令集, 顶层 -> 子命令集），从 assembly 与 commands/ 注册处直读。"""
    source = _cli_registration_text()
    tops = dict(re.findall(r'(\w+)\s*=\s*sub\.add_parser\(\s*"([^"]+)"', source))
    subparsers = dict(re.findall(r'(\w+)_sub\s*=\s*(\w+)\.add_subparsers', source))
    tree: dict[str, set[str]] = {name: set() for name in tops.values()}
    for match in re.finditer(r'(\w+)_sub\.add_parser\(\s*"([^"]+)"', source):
        sub_var, name = match.groups()
        parent = tops.get(subparsers.get(sub_var, ""), "")
        if parent:
            tree.setdefault(parent, set()).add(name)
    return set(tree), tree


#: `boardwise <词>` 后面跟的词里，**不是命令**的那些——散文（issue #62）。
#:
#: 写成表而不是隐式跳过：「哪些词是散文」是一个要有人负责的声明，写出来才能审。
#: 反向断言（未知顶层词）比正向断言更依赖这张表，所以它必须小而显式：这里每个词都是
#: 一次人工判读的结果，不是「跑出来啥是啥」。实测 SKILL.md 正文全集只有 ``connector``
#: 一个（`boardwise connector —— …` 指的是那个 npm 包，不是子命令）。
PROSE_AFTER_BOARDWISE: frozenset[str] = frozenset({"connector", "daemon"})


def _mentioned_commands(document: str) -> tuple[set[str], set[str]]:
    """文档提到的 boardwise 命令集，以及提到的**未知顶层词**集。

    返回 ``(commands, unknown_tops)``——issue #62 把这个 helper 从单向改成双向：
    原实现对未知首词 `continue`，于是「顶层命令被删/改名」这件事连同整条提及一起被丢掉，
    `checkup` 改名后 SKILL.md 十几处引用**不会让任何测试红**（实测 `review-mark` /
    `persistence` / `triage` / `checkup` 四个删掉都是 `stale=[]` 静默通过）。

    按**行**提取（行内反引号段 + 代码块里的裸命令行），不靠全局反引号配对
    （全文 2100+ 个反引号，一处失配全文档翻转——实测过）。三段判定：
    首词必须是注册的顶层命令（散文「boardwise daemon 常驻」不是命令提及）；
    第二词是注册的子命令才算双词命令；第二词紧跟 `.` 的是文件名参数
    （`review-mark report.json`），不是子命令。
    未知首词则进第二个返回值——由 :data:`PROSE_AFTER_BOARDWISE` 豁免散文，
    其余每一个都是「文档指向一个不存在的命令」。
    """
    tops, tree = _cli_commands()
    commands: set[str] = set()
    unknown_tops: set[str] = set()
    pattern = re.compile(
        r"boardwise\s+([a-z][a-z0-9-]*)(?:\s+([a-z][a-z0-9-]*)(\.?))?"
    )
    for line in document.splitlines():
        pieces = re.findall(r"`([^`]+)`", line) or [line]
        for piece in pieces:
            for match in pattern.finditer(piece):
                first, second, dot = match.groups()
                if first not in tops:
                    if first not in PROSE_AFTER_BOARDWISE:
                        unknown_tops.add(first)
                    continue
                if second is None or dot:
                    commands.add(first)
                else:
                    commands.add(f"{first} {second}")
    return commands, unknown_tops


def test_readme_rule_count_matches_builtin_rules():
    """护 #58：README 的规则数必须 == len(BUILTIN_RULES)，谁加规则谁更新 README。"""
    from boardwise.engines.review import BUILTIN_RULES

    count = len(BUILTIN_RULES)
    assert f"{count} design rules" in README, (
        f"README's English rule count drifted from BUILTIN_RULES ({count})"
    )
    assert f"{count} 条设计规则" in README, (
        f"README 中文段的规则数与 BUILTIN_RULES（{count}）漂移"
    )


def test_readme_export_sentence_tells_the_truth():
    """护 #59：「各一条命令」从未成立——export-fab 一条同时出三样，网表没有导出命令。"""
    assert "one command each" not in README
    assert "各一条命令" not in README
    assert "export-fab" in README, "README 的导出句丢了 export-fab 这个真身"


def test_skill_md_mentions_only_real_commands():
    """护 #60 主治法 + #62 的反向那一半：SKILL.md 提到的命令必须双向对拍。

    正向（#60）：SKILL ⊆ CLI——SKILL 是 SOP 不是命令参考，不反向要求 74 条全覆盖。
    反向（#62）：未知顶层词——SKILL 里 `boardwise <词>` 的首词若是 CLI 从未注册过的，
    就是 SOP 指向一个不存在的命令。旧实现对未知首词 `continue`，把整条提及丢掉，
    于是顶层命令被删/改名时这条钉子静默通过（实测把 `cli.py` 里 `review-mark` 注册名
    改成 `mark`：单向 11 passed 静默通过，双向 CAUGHT）。散文由
    :data:`PROSE_AFTER_BOARDWISE` 豁免——「哪些词不是命令」是有人负责的声明。
    """
    skill = (REPO / ".kimi-code" / "skills" / "boardwise" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    tops, tree = _cli_commands()
    known = set(tops)
    for parent, subs in tree.items():
        known.update(f"{parent} {sub}" for sub in subs)
    mentioned, unknown_tops = _mentioned_commands(skill)
    stale = sorted(m for m in mentioned if m not in known)
    assert stale == [], (
        "SKILL.md names commands the CLI no longer has: " + ", ".join(stale)
    )
    # 反向：SKILL.md 提到的、CLI 没有的顶层命令（不是子命令）。
    phantom = sorted(unknown_tops)
    assert phantom == [], (
        "SKILL.md mentions `boardwise <word>` for top-level commands the CLI "
        "never registered (or dropped): " + ", ".join(phantom)
        + " — either the command was removed/renamed, or PROSE_AFTER_BOARDWISE "
        "needs the word declared as prose"
    )


def test_skill_md_covers_the_load_bearing_commands():
    """护 #60 的另一半：承重命令（画图链的机器闸与提案器）不许再 0 次提及。"""
    skill = (REPO / ".kimi-code" / "skills" / "boardwise" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    mentioned, _unknown = _mentioned_commands(skill)
    for command in ("draw lint", "draw propose"):
        assert command in mentioned, (
            f"SKILL.md no longer mentions `{command}` — the draw pipeline's "
            "acceptance gate/proposer must stay discoverable in the SOP"
        )


def test_skill_md_protocol_line_refs_resolve():
    """护 #60 的次级实测：坑表里 `protocol.py:NNN` 的出处行号必须对得上——
    同一行里提到的大写常量，至少有一个真的定义在那一行（坑 2 曾引 :120，
    DELETE_TIMEOUT 真身在 :152）。124 减重后全表在 docs/pits.md，两处同查。"""
    protocol_lines = (
        REPO / "src" / "boardwise" / "bridge" / "protocol.py"
    ).read_text(encoding="utf-8").splitlines()
    bad: list[str] = []
    for doc in (
        REPO / ".kimi-code" / "skills" / "boardwise" / "SKILL.md",
        REPO / "docs" / "pits.md",
    ):
        for lineno, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            for ref in re.finditer(r"protocol\.py:(\d+)", line):
                target = int(ref.group(1))
                constants = re.findall(r"\b[A-Z][A-Z0-9_]{3,}\b", line)
                resolved = (
                    1 <= target <= len(protocol_lines)
                    and any(
                        re.match(rf"{re.escape(name)}\s*=", protocol_lines[target - 1])
                        for name in constants
                    )
                )
                if not resolved:
                    bad.append(f"{doc.name}:{lineno} -> protocol.py:{target}")
    assert bad == [], "stale protocol.py line refs: " + ", ".join(bad)


# ============================================================ 124 减重预算闸
SKILL_BUDGET_LINES = 320


def test_skill_md_stays_within_its_line_budget():
    """护 124 的战果：SKILL.md 是运行时必读路由层，不是知识库（岳 2026-10-06：
    「skill 是对方的 5、6 倍」——峰值 686 行，拆层后 279）。预算 320 行：
    撞线的人先去压实或外置，不许再把 SKILL 当仓库写。"""
    skill_lines = (
        REPO / ".kimi-code" / "skills" / "boardwise" / "SKILL.md"
    ).read_text(encoding="utf-8").splitlines()
    assert len(skill_lines) <= SKILL_BUDGET_LINES, (
        f"SKILL.md is {len(skill_lines)} lines (budget {SKILL_BUDGET_LINES}) — "
        "深水区内容外置到 docs/，别在路由层续写"
    )


def test_skill_md_doc_pointers_resolve():
    """路由层的存在理由是指针，指针烂掉路由层就死了：SKILL.md 提到的每个
    `docs/*.md` / `tasks/*.md` 都必须真的在仓库里。"""
    skill = (REPO / ".kimi-code" / "skills" / "boardwise" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    missing: list[str] = []
    for ref in sorted(set(re.findall(r"(?:docs|tasks)/[A-Za-z0-9._-]+\.md", skill))):
        if not (REPO / ref).is_file():
            missing.append(ref)
    assert missing == [], "SKILL.md points at files that do not exist: " + ", ".join(missing)


def test_skill_md_referenced_docs_are_shipped_not_pointed_at_air():
    """护 124b（外部审计「路由层指向空气」）：SKILL.md 引用的 docs/*.md 必须同时
    在 **spec 的 DATAS**（exe 打包清单）与 **resources 的引用清单**（install-skill
    拷到 references/ 的清单）里——读者有两类（仓库内 AI / 装了 exe 的朋友），
    指针只对一类解析就是只对一类成立。"""
    from boardwise import resources

    skill = (REPO / ".kimi-code" / "skills" / "boardwise" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    mentioned = set(re.findall(r"docs/[A-Za-z0-9._-]+\.md", skill))

    spec_body = (REPO / "packaging" / "boardwise.spec").read_text(encoding="utf-8")
    in_spec = {m for m in mentioned if all(p in spec_body for p in m.split("/"))}
    shipped = {f"docs/{path.name}" for path in resources.skill_reference_paths()}
    missing_spec = sorted(mentioned - in_spec)
    missing_ship = sorted(mentioned - shipped)
    assert not missing_spec and not missing_ship, (
        f"SKILL.md references docs the install cannot resolve — "
        f"not in spec DATAS: {missing_spec}; not in resources.skill_reference_paths(): "
        f"{missing_ship}"
    )


# ================================================ 139 收口：轨电压的两个键与那份清单
#: §3.1 的那句清单：``协同器件的 N 条规则（`id` / `id` …）``。
_SOP_TIER_CLAIM_RE = re.compile(r"协同器件的\s*(\d+)\s*条规则（([^）]*)）")
#: 清单里的规则 id——反引号段里全小写带连字符的那些。
_SOP_RULE_ID_RE = re.compile(r"`([a-z][a-z0-9-]+)`")


def test_the_sop_rule_list_in_the_per_page_tier_matches_the_registry():
    """护 064/139：SOP 说的「按网找协同器件的 N 条规则」必须与真实清单对拍。

    失效时的样子（本钉就是为此写的）：064 把 `sel-tvs-standoff-rail` /
    `sel-ldo-fixed-output` 加进 `NET_MEMBERSHIP_RULES`，而 SOP 仍写着「9 条」并列着
    老的九个——读 SOP 的人以为少两条规则不下结论，per-page 档的诚实度就少两块。

    钉子读**源头**：条数 == 清单里真有几个 id，成员 ⊆ `BUILTIN_RULES` 的 id
    （注册表）**且** ⊆ `NET_MEMBERSHIP_RULES`（这段话真正的断言是「它们对出现在多于
    一个页的网名不下结论」，只有后者能担保）。数字与清单本身必须是同一个数。
    """
    from boardwise.engines.review import BUILTIN_RULES
    from boardwise.rules.unproven import NET_MEMBERSHIP_RULES

    match = _SOP_TIER_CLAIM_RE.search(re.sub(r"\s+", " ", SOP))
    assert match is not None, (
        "docs/review-sop.md §3.1 lost its per-page rule list — the sentence that says "
        "which rules refuse on a welded net"
    )
    stated, listing = int(match.group(1)), _SOP_RULE_ID_RE.findall(match.group(2))
    assert len(listing) == stated, (
        f"the SOP says {stated} rules and lists {len(listing)}: {listing}"
    )
    builtin = {rule.id for rule in BUILTIN_RULES}
    assert set(listing) <= builtin, (
        "the SOP names rules that are not in BUILTIN_RULES: "
        + str(sorted(set(listing) - builtin))
    )
    assert set(listing) <= set(NET_MEMBERSHIP_RULES), (
        "the SOP lists rules that do not refuse on a welded net: "
        + str(sorted(set(listing) - set(NET_MEMBERSHIP_RULES)))
    )


def test_the_sop_and_the_writer_agree_that_one_answer_fills_both_voltage_keys():
    """护 139 收口：SOP 的 set-rail 段必须写明**双写**并点名两个键，且代码真的一次
    写两份——「答一次就不问」这句话两半都要成立。

    失效时的样子（139 之前）：文档写着「`intent set-rail` 写 `voltage`；要那两条规则
    也算答过，就在同一份合同里补 `targetVoltage`」——把缝留给工程师手工补，于是
    `pwr-cap-voltage-rating` / `path-ldo-dissipation` 对一条已经答过的轨继续报
    `intent-missing`（`evidence/064/intent_slot_gap.txt`）。

    文档那一半（「双写」二字与两个键名）与代码那一半（`set_rail_voltage` 真落两键，
    键名与 `RAIL_VOLTAGE_SLOTS` 逐字一致）分开断言：只写文档不改代码，或反过来，
    这条测试都会红。
    """
    from boardwise.core.designintent import SECTION_RAILS, DesignIntent
    from boardwise.core.railquery import RAIL_VOLTAGE_SLOTS, set_rail_voltage

    assert "双写" in SOP, "the SOP stopped explaining why one answer goes into two keys"
    updated, _ = set_rail_voltage(DesignIntent(), "VCCA", "3.3V")
    entry = updated.entry(SECTION_RAILS, "VCCA")
    for slot in RAIL_VOLTAGE_SLOTS:
        assert entry.value(slot) == "3.3V", f"set_rail_voltage stopped writing {slot}"
        assert f"`{slot}`" in SOP, f"the SOP no longer names the {slot} key"
    assert RAIL_VOLTAGE_SLOTS == ("voltage", "targetVoltage"), (
        "the pair moved — update docs/review-sop.md §3.1b in the same breath, and this "
        "pin with it"
    )


# ============================ #87⑤ readback 缺 value/mpn 的离线归档配方
#: SOP §3.2 里那条配方的标题锚点（pits #3 指向它）。
_READBACK_RECIPE_MARKER = "**`sch.readback` 没有 value/mpn**"
#: 仓库既有匿名 fixture：47 个器件，C3 的 Value/MPN 都可读，C1 有 MPN 但没有 Value
#: ——后半句正是「空值不伪造」要钉的形状。
_READBACK_FIXTURE = REPO / "tests" / "fixtures" / "llc_board.epro2"


def _sop_readback_section() -> str:
    """SOP 的 readback 配方段：从标题到下一个顶层 bullet 为止。"""
    assert _READBACK_RECIPE_MARKER in SOP, (
        "docs/review-sop.md lost the `sch.readback` value/mpn recipe — pit #3 "
        "would then point at nothing"
    )
    tail = SOP.split(_READBACK_RECIPE_MARKER, 1)[1]
    end = re.search(r"\n- \*\*", tail)
    return tail[: end.start()] if end else tail


def _sop_readback_recipe_code() -> str:
    """The ```python block the SOP tells the reader to copy, verbatim."""
    match = re.search(r"```python\n(.*?)```", _sop_readback_section(), re.DOTALL)
    assert match is not None, "the readback recipe lost its ```python block"
    return match.group(1)


def test_the_sop_readback_recipe_runs_and_reads_real_value_mpn():
    """护 #87⑤：文档里的配方必须能直接跑，且读的是 fixture 的真字段。

    提取 SOP 原文的代码块执行（不是测试里另写一份），把公开占位符
    `<导出.epro2>` 换成仓库既有匿名 fixture：C3 的值/料号可读，C1 的空
    Value 仍是空串——空值不补猜。字段改名或文档改了代码没改，这条当场红。
    """
    code = _sop_readback_recipe_code()
    section = _sop_readback_section()
    assert '"<导出.epro2>"' in code, (
        "the recipe must keep the public placeholder `<导出.epro2>`, not a real path"
    )
    assert "`C1`" in section, "the public example designator must stay generic C1"
    runnable = code.replace('"<导出.epro2>"', json.dumps(str(_READBACK_FIXTURE)))
    proc = subprocess.run(
        [sys.executable, "-c", runnable],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    assert proc.returncode == 0, (
        "the SOP recipe does not run as written:\n" + proc.stderr
    )
    rows = json.loads(proc.stdout)
    by_designator = {row["designator"]: row for row in rows}
    assert by_designator["C3"]["value"] == "330uF 400V"
    assert by_designator["C3"]["mpn"].strip(), (
        "C3's MPN must be read from the archive, not left empty"
    )
    assert by_designator["C1"]["value"] == "", (
        "a component with no Value must print an empty string, not an invented value"
    )
    assert set(by_designator["C3"]) == {"board", "designator", "value", "mpn"}


def test_the_sop_readback_recipe_keeps_its_readonly_and_live_gap_disclosure():
    """护 #87⑤ 的边界：配方只读归档，且不把未复测的 live 取档写成已验。"""
    section = _sop_readback_section()
    for token in ("只读", "不碰编辑器", "不写工程", "stdout"):
        assert token in section, f"the readback recipe lost its boundary token {token!r}"
    assert "sys.get_project_file" in section
    assert "未在本批复测" in section, (
        "the recipe claims a live archive transfer this batch did not verify"
    )
    assert "tests/test_doc_claims.py" in section, (
        "the SOP must name the test that keeps this recipe from drifting"
    )
    assert "C3" in section and "C1" in section, (
        "the recipe's coverage sentence must name what the pin reads"
    )


def test_pit_3_points_at_the_sop_readback_recipe():
    """pits #3 与 SOP 不许各说各话：坑表必须把读者送到同一条配方。"""
    pits = (REPO / "docs" / "pits.md").read_text(encoding="utf-8")
    rows = [line for line in pits.splitlines() if line.startswith("| 3 |")]
    assert len(rows) == 1, "docs/pits.md lost its readback row (pit 3)"
    row = rows[0]
    assert "`sch.readback`" in row
    assert "docs/review-sop.md" in row and "§3.2" in row
    assert "value/mpn" in row, "pit 3 must name the fields the recipe recovers"


# ============================ #87② PCB 目视复核：没有独立的已验图像通道
#: SOP §3.2 里 PCB 目视复核那条的标题（pits #23 的 PCB 边界指向它）。
_PCB_VISUAL_MARKER = "- **PCB 目视复核没有独立的已验图像通道**"
_ACTIONS_TS = REPO / "connector" / "src" / "actions.ts"


def _sop_pcb_visual_section() -> str:
    """SOP 的 PCB 目视条：从标题到下一个顶层 bullet 为止。

    按**原文**切，不按模块级的 `SOP`（那份已把空白折叠，切不出行边界）——
    否则「这一条说了什么」会被后面几节的字混进来。
    """
    raw = (REPO / "docs" / "review-sop.md").read_text(encoding="utf-8")
    assert _PCB_VISUAL_MARKER in raw, (
        "docs/review-sop.md lost the PCB visual-review bullet — pit #23's PCB "
        "boundary would then point at nothing"
    )
    tail = raw.split(_PCB_VISUAL_MARKER, 1)[1]
    end = re.search(r"\n- \*\*", tail)
    return tail[: end.start()] if end else tail


def test_the_sop_separates_pcb_readonly_geometry_from_having_looked_at_the_board():
    """护 #87② 的第一句话：只读几何与「看过板子」是两条腿，不许合并。

    `pcb.readback` / `pcb.geometry` 回的是一组数字（位号/坐标/包围盒），
    `export.render` 出的才是图。**这条只钉文案与来源**：它不证明真机出过图，
    也不证明自绘/离线几何被渲染过——那种断言只有真机证据能给。
    """
    section = _sop_pcb_visual_section()
    for action in ("pcb.readback", "pcb.geometry"):
        assert f"`{action}`" in section, (
            f"the PCB visual bullet must name {action} as the read-only geometry route"
        )
    assert "`export.render`" in section
    assert "只读几何" in section and "几何复核" in section
    assert "数字" in section, "the bullet must say what the readback route returns"
    assert "这几件被读到了" in section, (
        "a readback ok must be described as 'these parts were read', never as a pass"
    )
    assert "没有 PCB 专用的第二个出图动作" in section, (
        "the bullet must say the render action is shared with the schematic route"
    )


def test_the_sop_never_turns_a_readback_or_a_png_into_a_visual_pass():
    """护 #87② 的第二句话：没图就写 missing / 人工待办，不写 visual-pass。

    `pcbImage` 的 `ok` 只等于「采集到一张合规 PNG」；`visual: missing` 才是
    「本次没有看过板子」的诚实写法。真机出图与否**不在本条断言范围**。
    """
    section = _sop_pcb_visual_section()
    assert "pcbImage: missing" in section
    assert "visual: missing" in section
    assert "人工待办" in section and "PCB 图未取到" in section
    assert "不证明有人看过" in section, (
        "a pcbImage ok must be read as 'a compliant PNG was collected', not as "
        "evidence that someone looked at it"
    )
    assert "伪造证据" in section
    assert "视觉通过" not in section, (
        "the bullet must not claim a visual pass; the honest states are "
        "missing / failed / a named manual todo"
    )


def test_the_sop_records_the_v4_pcb_60s_timeout_and_stops_calling_render():
    """护 #87② 的第三句话：PCB 上的 60 s 是 **V4.1.93 实测**，此后不再调用该 API。

    O2（2026-10-31）在已 `doc.open` + `document.current` 确证的 PCB1 上单发一次
    `timeoutMs:60000`，整 60.01 s 不返回；同会话原理图页秒回 ⇒ schematic-only。
    所以 SOP 必须写实测读数、`not-applicable`、以及"停止对 PCB 调用"，
    **不许**回退成「本批没有复现」这类过期口径。
    SOP 说的两个数字（`timeoutMs` 夹取 1–60 s、缺省 30 s）必须仍对得上
    connector 源码，否则文案里的「上限」就成了二手转述。
    """
    section = _sop_pcb_visual_section()
    assert "60.01" in section, (
        "the SOP must carry the measured wall clock of the V4 PCB render timeout"
    )
    assert "not-applicable" in section, (
        "the SOP must fix pcbImage at not-applicable — the call no longer happens"
    )
    assert "停止对 PCB 调用" in section, (
        "the SOP must say the render action is no longer invoked on PCB pages"
    )
    assert "只服务原理图" in section, (
        "the SOP must name the API as schematic-only, not as a budget problem"
    )
    assert "本批没有复现" not in section and "历史报告" not in section, (
        "the stale 'unreproduced this batch / historical report' wording is back; "
        "O2 reproduced it on V4.1.93"
    )
    assert "不给 60 s 盲重试" in section
    assert "上限" in section and "TIMEOUT" in section
    source = _ACTIONS_TS.read_text(encoding="utf-8")
    assert "const EXPORT_RENDER_TIMEOUT_MS = 30_000;" in source, (
        "the connector no longer defaults to 30 s; the SOP's default is stale"
    )
    assert "const EXPORT_RENDER_TIMEOUT_MAX_MS = 60_000;" in source, (
        "the connector no longer clamps to 60 s; the SOP's upper bound is stale"
    )
    assert "1–60 s" in section and "30 s" in section


def test_every_pcb_visual_command_in_the_sop_uses_a_parameter_the_connector_reads():
    """护 #87② 的第四句话：固定命令里的参数名不许 invent。

    从 SOP 原文抠 `--action X --params '<json>'`，逐个参数回 connector 源码对，
    并确认动作真的注册过；参数名对不上就是文档自己编的（#87 的 old draft
    正是在这一步编出过不存在的高亮成功）。
    """
    section = _sop_pcb_visual_section()
    calls = re.findall(
        r"boardwise bridge call --action ([a-z.]+) --params '(\{[^']*?\})'", section
    )
    assert calls, "the PCB visual bullet lost its fixed `bridge call` commands"
    assert {action for action, _ in calls} == {"pcb.readback", "pcb.geometry"}
    bridge_doc = (REPO / "docs" / "bridge.md").read_text(encoding="utf-8")
    assert "--params" in bridge_doc, "`bridge call` no longer documents --params"
    source = _ACTIONS_TS.read_text(encoding="utf-8")
    for action, payload in calls:
        assert f"'{action}': bind(" in source, f"{action} is not a registered action"
        for key in json.loads(payload):
            assert f"params.{key}" in source or f"params?.{key}" in source, (
                f"the SOP tells the reader to pass {key!r} to {action}, but the "
                "connector never reads that parameter"
            )


def test_pit_23_carries_the_pcb_boundary_without_growing_a_new_pit_number():
    """护 #87② 的第五句话：坑表与 SOP 说同一句话，且不另开坑号。

    PCB 边界是同一个坑的另一个面：新开坑号会让「导出挂死」在坑表里看起来像
    两个不同的病。锚点原文必须仍在 SOP 里（上一条测试钉着它）。
    """
    pits = (REPO / "docs" / "pits.md").read_text(encoding="utf-8")
    rows = [line for line in pits.splitlines() if line.startswith("| 23 |")]
    assert len(rows) == 1, "docs/pits.md lost its export.render row (pit 23)"
    row = rows[0]
    assert "PCB 例外/边界" in row and "#87②" in row
    assert "docs/review-sop.md" in row and "§3.2" in row
    assert "PCB 目视复核没有独立的已验图像通道" in row, (
        "pit 23 must quote the SOP anchor verbatim or the pointer rots"
    )
    assert "`export.render`" in row and "`pcb.readback`" in row and "`pcbImage`" in row
    for token in ("V4.1.93", "60.01", "not-applicable", "停止对 PCB 调用", "schematic-only"):
        assert token in row, (
            f"pit 23 must carry the V4 O2 measured boundary token {token!r}; "
            "the '未复现' era wording is gone"
        )
    assert "本批未复现" not in row and "没有逐项条目" not in row


def test_pit_27_records_both_the_v3_aggregate_and_the_v4_per_item_shape():
    """护 O3：主机 ERC 在 V4.1.93 返回逐条，坑表不能再说"所有版本都没有逐项"。

    V3（039 实测）只有 `counts/byType/total`；V4.1.93（2026-10-31 O3）每页 519 个
    `{type,rule,primitives}`、没有 `count`。connector 的归一化键 `entryShape` /
    `per-item` / `items` 必须仍在源码里，否则坑表描述的接口已经不存在；
    SOP 的两处 ERC 说明也必须按版本分家。
    """
    pits = (REPO / "docs" / "pits.md").read_text(encoding="utf-8")
    rows = [line for line in pits.splitlines() if line.startswith("| 27 |")]
    assert len(rows) == 1, "docs/pits.md lost its host-ERC row (pit 27)"
    row = rows[0]
    assert "没有逐项条目" not in row, (
        "pit 27 still claims host ERC has no per-item entries; V4.1.93 returns them"
    )
    for token in ("V3", "V4.1.93", "519", "entryShape", "per-item", "items",
                  "host-wide", "pages[].items"):
        assert token in row, f"pit 27 must state the current ERC contract token {token!r}"
    source = _ACTIONS_TS.read_text(encoding="utf-8")
    assert "entryShape" in source and "'per-item'" in source, (
        "the connector no longer emits entryShape='per-item'; pit 27 is stale"
    )
    assert "items" in source
    sop = (REPO / "docs" / "review-sop.md").read_text(encoding="utf-8")
    assert "V3 只有 host-wide 合计、没有逐条文本" in sop
    assert "V4.1.93 起返回值里" in sop and "直接带逐条对象" in sop


# ========================================== dsh 迁移：SOP 的两个入口必须同源
#: SOP 的**两份同步副本**。dsh 的 skill 扫描根是 `<repo>/.dsh/skills` 与
#: `<repo>/.agents/skills`（顶层 `<name>/SKILL.md`），`.kimi-code/` 不在其中；而 kimi
#: 的约定恰好就是 `.kimi-code/`。所以同一份 320 行 SOP 落两次——它们是**一份文件放在
#: 两个地方**，不是两个版本。两份路径与 `AGENTS.md` 的权威指针段逐字对应。
SOP_COPIES: tuple[str, ...] = (
    ".kimi-code/skills/boardwise/SKILL.md",
    ".agents/skills/boardwise/SKILL.md",
)


def test_the_two_sop_copies_stay_byte_identical():
    """护 dsh 迁移（2026-10-22）：两份 SKILL.md 必须**逐字节**相同。

    失效时的样子（本钉就是为此写的）：在 `.kimi-code/` 那份里改一条纪律、忘了同步
    `.agents/` 那份。两边各自「存在、frontmatter 合法、指针解析得通」，所以没有任何东西
    会响——直到某个 dsh 会话按**另一套规矩**干活。这不是 DRY 洁癖：读哪份决定按哪套规矩
    办事，两份分叉就是两套 SOP（kimi 会话纠正过的坑，dsh 会话照旧踩）。

    比字节而不是比正文，是因为行尾也在契约里：`core.autocrlf=true` 下一次 checkout 会把
    两份一起写成 CRLF，逐字节仍然相等；只改一份的内容或行尾都会在这里红。搬家/复制用
    `cp`，不要手抄。
    """
    reference = REPO / SOP_COPIES[0]
    assert reference.is_file(), f"the SOP itself is missing: {SOP_COPIES[0]}"
    expected = reference.read_bytes()
    for relative in SOP_COPIES[1:]:
        path = REPO / relative
        assert path.is_file(), (
            f"the SOP copy at {relative} is missing — dsh's skill roots are "
            "`.dsh/skills` and `.agents/skills`, so a SOP that only lives under "
            "`.kimi-code/` is invisible there and its session silently loses R1–R3"
        )
        assert path.read_bytes() == expected, (
            f"{relative} drifted from {SOP_COPIES[0]} — the two are one file in two "
            "places; re-copy it (`cp`), never re-edit one side"
        )


# ============================================ 537E：收尾顺序与交付边界（dsh 审查闭环）
#: 收尾小节从 `⓹ 收尾死一步` 起，到下一个 `### ` 标题为止。只解析**这一小节**：
#: 拿全文做等值比较，正文别处改一个字就红，钉住的是排版不是语义。
_SOP_TAIL_HEADING = "⓹ 收尾死一步"
#: 六步的**加粗标题**，按 SOP 要求的顺序。它们是顺序本身，不只是关键词。
_SOP_TAIL_STEPS = (
    "**结构化读取**",
    "**分诊**",
    "**environment / evidence 覆盖补全**",
    "**人工填 `review-summary.md`**",
    "**`boardwise review finalize --out <目录>`**",
    "**顺序交付**",
)


def _sop_tail_section() -> str:
    """`docs/review-sop.md` 的收尾小节（含 `⓹` 标题行，到下一个 `### ` 为止）。"""
    lines = SOP.splitlines()
    start = next((i for i, line in enumerate(lines) if _SOP_TAIL_HEADING in line), None)
    assert start is not None, (
        "docs/review-sop.md lost its `⓹ 收尾死一步` section — the 537E delivery order "
        "lives there"
    )
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith("### ")),
        len(lines),
    )
    return "\n".join(lines[start:end])


def test_the_sop_tail_section_keeps_the_537e_order():
    """护 537E：收尾必须依次是 读取 → 分诊 → 覆盖补全 → 填总结 → finalize → 交付。

    失效时的样子（537E 之前）：SOP 的收尾只有「填 review-summary + 当面讲」两个动作，
    结构化读取、needs-manual 仍 pending、live/archive 覆盖分开、finalize 收据全没写；
    照着读的人照样解析 `runBoardwise` 的截断 stdout、照样用三词关掉无细节 ERC。
    """
    section = _sop_tail_section()
    positions: list[int] = []
    for step in _SOP_TAIL_STEPS:
        assert step in section, f"the 537E tail section lost its step {step!r}"
        positions.append(section.index(step))
    assert positions == sorted(positions), (
        "the 537E tail steps are out of order: " + " → ".join(_SOP_TAIL_STEPS)
    )
    assert "runBoardwise" in section and "截断" in section, (
        "the tail section stopped forbidding truncated `runBoardwise` stdout parsing"
    )
    assert "needs-manual" in section and "pending" in section, (
        "the tail section stopped saying a `needs-manual` slot stays pending"
    )


def test_the_sop_tail_section_keeps_finalize_and_the_board_verdict_apart():
    """护 537D2/537E：`finalize.ok`/退出 0 只是交付校验，板级结论只认 `report.conclusion`。

    失效时的样子：把 `finalize.ok` 读成板子通过（或拿 `summary.conclusion` 拼一句结论），
    于是交付校验冒充板级裁决；或者为了过闸，把模型记忆当手册证据、把归档当实时。
    """
    section = _sop_tail_section()
    assert "finalize.ok" in section and "不是板级通过" in section
    assert "report.conclusion" in section and "唯一权威" in section
    assert "在披露一致时可以交付" in section, (
        "the tail section stopped allowing partial/needs-manual deliveries when disclosed"
    )
    assert "只描述证据/交付覆盖" in section, (
        "the tail section stopped saying `partial` describes coverage, not a board verdict"
    )
    assert "编造证据" in section, "the tail section no longer forbids fabricating evidence"
    assert "模型记忆不是数据手册证据" in section
    assert "web_search" in section and "手册已核" in section, (
        "the tail section lost the rule that a failed web_search may not be worded as a "
        "checked datasheet"
    )
    assert "archive 不等于 live" in section
    assert "环境限制与证据缺口" in section and "披露" in section


def test_the_sop_tail_section_orders_the_dsh_receipt_before_present():
    """护 537D3：`boardwise_review_finalize` 成功之后才有 Session receipt，present 等它。

    失效时的样子（原会话 seq 431）：同一步里发检查与 present，present 在没有任何
    finalize 记录时把文件端出去；或把模型可写的手写 `finalize.json` 当成授权。
    闸由插件实现，但**顺序与「手写文件没有 Session 特权」是 SOP 必须说清的那一半**。
    """
    section = _sop_tail_section()
    finalize_at = section.index("boardwise_review_finalize")
    present_at = section.index("present")
    assert finalize_at < present_at, (
        "the tail section puts `present` before the Session receipt exists"
    )
    assert "不能与 finalize 并行" in section
    assert "手写 `finalize.json` 没有 Session 特权" in section
    assert "当前运行中的 DSH" in section and "新闸" in section, (
        "the tail section stopped warning that the running DSH has not loaded the new gate"
    )


def test_the_skill_review_route_compresses_the_tail_order_and_points_at_the_sop():
    """护 537E 的路由层：SKILL 只留压缩后的顺序 + 权威边界，细节指到 SOP。

    SKILL 是运行时必读的路由层（320 行预算由上面那条钉着），所以这里只要求它点到
    顺序与两个权威边界，不要求它复制 SOP 的正文。
    """
    skill = (REPO / SOP_COPIES[0]).read_text(encoding="utf-8")
    for token in (
        "收尾固定顺序",
        "boardwise_review_read",
        "runBoardwise",
        "boardwise_review_finalize",
        "present",
        "report.conclusion",
        "手写 `finalize.json` 没有 Session 特权",
        "docs/review-sop.md",
    ):
        assert token in skill, f"SKILL lost {token!r} from the review route"


def test_rust_platform_names_the_real_case_book_size():
    """护 `docs/rust-platform.md` §3 的那句「仓库 case book 当前有 **N 个 case**」。

    唯一的量是 `contracts/differential/cases.json` 的 `cases` 长度；文档只是它的转述。
    失效形态：加了一组差分 case（038M 从 9 变 11、038N 从 11 变 13、038T 从 13 变 15）
    而平台文档仍写旧数——读的人会误判 Rust 覆盖率；反向同样算漂移——文档一旦不再提
    `device-library-sample`、`footprint-library-sample` 或 `footprint-declared-sample`，
    那句「五组各一个 kind、两个 case id」、「三组才是库投影」与「最后一组是声明解析投影」
    就失去字面支撑，读者找不到 DEVICE / FOOTPRINT / DECLARED 投影的入口。
    """
    cases = json.loads(
        (REPO / "contracts" / "differential" / "cases.json").read_text(encoding="utf-8")
    )["cases"]
    platform = re.sub(
        r"\s+",
        " ",
        (REPO / "docs" / "rust-platform.md").read_text(encoding="utf-8"),
    )
    count = len(cases)
    assert f"**{count} 个 case**" in platform, (
        "docs/rust-platform.md's case-book count drifted from "
        f"contracts/differential/cases.json ({count} cases)"
    )
    for kind, label in (
        ("device-library-sample", "DEVICE"),
        ("footprint-library-sample", "FOOTPRINT"),
        ("footprint-declared-sample", "DECLARED"),
    ):
        assert kind in platform, (
            f"docs/rust-platform.md no longer names `{kind}` — the {label} "
            "projection kind lost its entry in the case-book paragraph"
        )


def test_the_cbb_book_pins_its_negative_controls_and_its_unproven_lead():
    """护 038Q 的两处口径钉，它们都是「删掉一句就变成假话」的脆弱点。

    ① 原生 CBB 目前**不存在**实现，`type 17` 只是线索。任务书一旦把「待证实」写丢、
    或把「先读后写」写丢，后来的人就会照着线索去写解析或先写后补证据（R3 的反面）。
    ② 三条 negative control 是「兼容 CBB」这句话的全部支撑：已接块端口静默、真悬空仍报、
    普通器件读数不变。少一条，误报修复就会退化成全局静默。
    ③ 兼容矩阵的要求归 `tasks/shared-platform.md` 的集成锁管；它被删掉时，以后每批都会
    拿单一维度的绿读数冒充兼容。
    """
    book = re.sub(
        r"\s+",
        " ",
        (REPO / "tasks" / "038q_cbb_native.md").read_text(encoding="utf-8"),
    )
    for token in (
        "type 17 待证实",
        "先读后写",
        "block_symbol",
        "已接块端口",
        "真悬空",
        "普通器件读数不变",
    ):
        assert token in book, f"tasks/038q_cbb_native.md lost {token!r}"
    platform = re.sub(
        r"\s+",
        " ",
        (REPO / "tasks" / "shared-platform.md").read_text(encoding="utf-8"),
    )
    for token in ("兼容矩阵", "negative control", "未覆盖不得写"):
        assert token in platform, f"tasks/shared-platform.md lost {token!r}"


def test_the_boundary_doc_names_the_multi_board_guards_without_hiding_the_gap():
    """护 038P1 之后 `docs/v3-v4-boundary.md` 与 `tasks/shared-platform.md` 的口径。

    多板合流的三道守卫（相同库副本允许 / 分歧拒绝 / 重复 PCB 拒绝 / 无 uuid 板按文件名）
    是「多板能读了」这句话的全部支撑；边界文档一旦退回泛泛的「多板未支持」，或把守卫写丢，
    后来的人就会以为多板 + 库要么全能读、要么全都不能读——两种误读都会让人跳过真实样本。
    缺口那句同理：守卫只有合成证据，**真实多板 + 库工程未实测**必须留着，否则合成样本
    会被读成真机覆盖。

    `tasks/shared-platform.md` 的集成锁要求每批写 negative control，两个多板例子是它唯一的
    具体样式：少了它们，「不该变的东西必须不变」就退化成一句口号。
    """
    def tight(relative: str) -> str:
        return re.sub(r"\s+", "", (REPO / relative).read_text(encoding="utf-8"))

    boundary = tight("docs/v3-v4-boundary.md")
    for token in ("相同库副本允许", "分歧拒绝", "重复PCB拒绝", "按文件名命名"):
        assert token in boundary, (
            "docs/v3-v4-boundary.md no longer states the multi-board guard "
            f"{token!r} — the boundary fell back to a blanket 「多板未支持」"
        )
    assert "真实多板+库工程未实测" in boundary, (
        "docs/v3-v4-boundary.md lost the honest gap: the guards are synthetic-sample "
        "evidence, no real multi-board + library project has been read"
    )

    platform = tight("tasks/shared-platform.md")
    for token in ("分歧库", "重复PCB"):
        assert token in platform, (
            "tasks/shared-platform.md no longer carries the multi-board negative "
            f"control example {token!r}"
        )


# ============================ 绘制线专项 skill（分岛裁决与路由，2026-11-04）
#: 绘制线专项 skill 的**两份同步副本**，规矩同 :data:`SOP_COPIES`：一份文件放两个地方
#: （kimi 读 `.kimi-code/`，dsh 扫 `.agents/skills`），复制用 `cp`、不许手抄。
DRAW_SOP_COPIES: tuple[str, ...] = (
    ".kimi-code/skills/boardwise-draw/SKILL.md",
    ".agents/skills/boardwise-draw/SKILL.md",
)


def _frontmatter(document: str) -> dict[str, str]:
    """frontmatter 的顶层 `<key>: <value>` 对（本仓库用的是扁平形态，不解析 YAML）。"""
    lines = document.splitlines()
    assert lines and lines[0] == "---", "the file does not open with frontmatter"
    block: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return block
        key, sep, value = line.partition(":")
        assert sep, f"frontmatter line without a colon: {line!r}"
        block[key.strip()] = value.strip()
    raise AssertionError("the frontmatter is not closed by a second `---`")


def test_the_draw_skill_ships_as_two_byte_identical_copies():
    """护绘制线专项 skill 的两个入口：必须都在场、逐字节相同。

    失效时的样子：只写 `.kimi-code/skills/boardwise-draw/`——kimi 会话看得到，
    dsh 的 skill 根是 `.agents/skills`，它的绘制会话会退回总 SOP，分岛提交条件、
    成对支路一致性、机器闸/视觉闸的分工整套静默消失。
    """
    reference = REPO / DRAW_SOP_COPIES[0]
    assert reference.is_file(), f"the draw skill is missing: {DRAW_SOP_COPIES[0]}"
    expected = reference.read_bytes()
    for relative in DRAW_SOP_COPIES[1:]:
        path = REPO / relative
        assert path.is_file(), (
            f"the draw skill copy at {relative} is missing — dsh scans "
            "`.agents/skills`, so this entry would be invisible there"
        )
        assert path.read_bytes() == expected, (
            f"{relative} drifted from {DRAW_SOP_COPIES[0]} — the two are one file "
            "in two places; re-copy it (`cp`), never re-edit one side"
        )


def test_the_draw_skill_declares_its_name_and_its_trigger_surface():
    """护 skill 的可发现性：frontmatter 名字必须是 `boardwise-draw`，触发面要覆盖
    原理图绘制 / PresentationSpec / 分岛 / 布局布线 / draw 编译与画回编辑器。

    失效时的样子：名字抄成 `boardwise`（两个 skill 抢一个名字，加载哪个看运气），
    或描述只写「画图」——分岛、旗标、视觉自审的调用就落不到这个 skill 上。
    """
    skill = (REPO / DRAW_SOP_COPIES[0]).read_text(encoding="utf-8")
    front = _frontmatter(skill)
    assert front.get("name") == "boardwise-draw", (
        "the draw skill's frontmatter name must be `boardwise-draw`, got "
        f"{front.get('name')!r}"
    )
    for key in ("description", "whenToUse"):
        assert front.get(key), f"the draw skill frontmatter lost `{key}`"
    surface = front["description"] + "\n" + front["whenToUse"]
    for token in ("原理图", "PresentationSpec", "分岛", "布局布线", "draw compile"):
        assert token in surface, (
            f"the draw skill's trigger surface lost {token!r} — a caller asking "
            "for that job would not load this skill"
        )


def test_the_draw_skill_keeps_its_ruling_rules():
    """护本批立下的裁决规则本身：语义归属、拆岛前三条、成对一致性、两道闸分工、
    修复优先级、责任边界与反例。只钉语义关键词，不做全文等值（排版不是契约）。

    失效时的样子：规则被压成「机器闸全过即可交付」（`E` 被删），或把「编译能过」
    重新当成拆岛的合法理由（`B` 被删），或不再说明哪些关系是已有合同、哪些要派单
    （于是有人以为解释器已经自动保证成对支路）。
    """
    skill = (REPO / DRAW_SOP_COPIES[0]).read_text(encoding="utf-8")
    for token in (
        "语义归属优先",
        "功能理由",
        "预期图形结果",
        "等节距",
        "不自动语义分岛",
        "agent-adjusted",
        "机器全绿不改变判废结论",
        "没实现的约束",
        "每条不连续导线都要有可见去向",
        "导线终点的合法绕行距离",
        "禁止用焊盘欧氏距离",
    ):
        assert token in skill, f"the draw skill lost its ruling {token!r}"


def test_the_draw_skill_mentions_only_real_commands():
    """同 :func:`test_skill_md_mentions_only_real_commands` 的尺子对准绘制线 skill：
    文档指向的命令必须是 CLI 真注册过的（正反两向），不许写出想象中的子命令。"""
    skill = (REPO / DRAW_SOP_COPIES[0]).read_text(encoding="utf-8")
    tops, tree = _cli_commands()
    known = set(tops)
    for parent, subs in tree.items():
        known.update(f"{parent} {sub}" for sub in subs)
    mentioned, unknown_tops = _mentioned_commands(skill)
    stale = sorted(m for m in mentioned if m not in known)
    assert stale == [], (
        "the draw skill names commands the CLI no longer has: " + ", ".join(stale)
    )
    assert sorted(unknown_tops) == [], (
        "the draw skill mentions `boardwise <word>` for commands the CLI never "
        "registered: " + ", ".join(sorted(unknown_tops))
    )


def test_the_draw_skill_pointers_resolve():
    """路由层的指针必须落地：skill 里点到的 `docs/*.md` / `tasks/*.md` 都得在。"""
    skill = (REPO / DRAW_SOP_COPIES[0]).read_text(encoding="utf-8")
    missing = [
        ref
        for ref in sorted(set(re.findall(r"(?:docs|tasks)/[A-Za-z0-9._-]+\.md", skill)))
        if not (REPO / ref).is_file()
    ]
    assert missing == [], (
        "the draw skill points at files that do not exist: " + ", ".join(missing)
    )


def test_the_general_sop_and_the_agents_route_still_lead_to_the_draw_skill():
    """护路由：总 SOP 的两份副本与 `AGENTS.md` 都必须把绘制线指向 `boardwise-draw`，
    同时**保留** `boardwise` 作为通用 SOP / 真机纪律的权威入口。

    失效时的样子：新 skill 建好了但没人路由（等于没写），或者为了加路由把总 SOP 的
    权威指针删掉，于是通用 R1–R3 失去唯一出处。
    """
    for relative in SOP_COPIES:
        skill = (REPO / relative).read_text(encoding="utf-8")
        assert "boardwise-draw" in skill, (
            f"{relative} no longer routes the drawing line to the boardwise-draw skill"
        )
        assert "绘制线任务必须加载" in skill, (
            f"{relative} lost the hard requirement that draw-line tasks load the "
            "draw skill"
        )
        assert "docs/draw.md" in skill, (
            f"{relative} stopped pointing at the drawing manual"
        )

    agents = (REPO / "AGENTS.md").read_text(encoding="utf-8")
    assert "绘制线任务开工前必须加载" in agents, (
        "AGENTS.md lost the hard routing requirement for draw-line tasks"
    )
    for relative in DRAW_SOP_COPIES:
        assert relative in agents, f"AGENTS.md does not name the draw skill entry {relative}"
    for relative in SOP_COPIES:
        assert relative in agents, (
            f"AGENTS.md dropped the general SOP entry {relative} — boardwise must "
            "stay the authority for R1–R3 and the live-editor discipline"
        )

    draw_line = (REPO / "tasks" / "draw-line.md").read_text(encoding="utf-8")
    assert "boardwise-draw" in draw_line, (
        "tasks/draw-line.md does not require loading the boardwise-draw skill"
    )
    assert "开工前必须加载" in draw_line, (
        "tasks/draw-line.md lost the hard loading requirement"
    )


# ============================ 543O：roadmap 稳定层与任务账同步（2026-11-06）
#: 543 的权威验收账（两拓扑真机读数）与总索引（543/201x 状态）。路线图是稳定层，
#: 它对 543 的每句话都必须能在这两处源头里找到同一句——否则稳定层就成了二手转述。
_543_LEDGER = "tasks/543_semantic_layout.md"
_TASKMAP = "tasks/TASKMAP.md"


def _squash(document: str) -> str:
    """声明钉按整句对拍：换行是排版不是语义，先把空白归一再比。"""
    return re.sub(r"\s+", " ", document)


def _table_row(document: str, key: str) -> str:
    """`| <key> | ...` 的整行；索引/表格里那行就是源头，找不到即失败。"""
    match = re.search(rf"^\|\s*{re.escape(key)}\s*\|.*$", document, re.MULTILINE)
    assert match, f"no table row starting with | {key} |"
    return match.group(0)


def test_the_roadmap_keeps_543_states_roles_and_non_revivals_in_sync():
    """护 `docs/roadmap.md` §1/§4 与 543 权威验收账、TASKMAP 索引的同一句话。

    稳定层必须让只读路线图的人看到：543 有**两个各自不同**的持久化状态——CH343 P38 已关闭
    重开 `saved_verified`，CH340 P39 仍 `saved_unverified`、待关闭重开；agent 声明功能岛/
    核心/阅读关系而解释器负责确定性几何；201C/201D 经 543H 裁不复活、201E 已落；
    Board2/P1 是用户参考页而不是试验场；201x 读数只是诊断基线、不冒充 P38/P39 当前读数。

    失效时的样子：只写「两个拓扑都过了」而抹平 P39 仍待重开（或反过来把 P39 写成已重开/
    已 `saved_verified`）；删掉 agent/解释器分工，让「构造式布局」退化成一句空话；把
    201C/201D 写回「待复活」，或把 201E 写回「规划/在途」；再把 Board2/P1 写成试验场；
    把 201x 的历史读数当成当前页读数。状态与裁决先从任务账/索引读出来再要求路线图说同一句，
    防止两处各说各话。
    """
    ledger_raw = (REPO / _543_LEDGER).read_text(encoding="utf-8")
    taskmap_raw = (REPO / _TASKMAP).read_text(encoding="utf-8")
    roadmap_raw = (REPO / "docs" / "roadmap.md").read_text(encoding="utf-8")
    ledger = _squash(ledger_raw)
    roadmap = _squash(roadmap_raw)
    map_543 = _table_row(taskmap_raw, "543")

    # --- 源头：哈希在场，持久化状态钉死为具体事实（不是「两者只要不同」）。
    instances = {"P38": "0ec4dc022ef38563", "P39": "62e4828acc56a307"}
    for designator, instance in instances.items():
        for name, text in (
            ("tasks/TASKMAP.md", map_543),
            ("tasks/543_semantic_layout.md", ledger),
        ):
            assert f"{designator}=`{instance}`" in text, (
                f"{name} lost the {designator} instance hash"
            )
    assert "P39持久化未重开验证" in map_543, (
        "tasks/TASKMAP.md 543 row stopped disclosing that P39 was not reopened"
    )

    states: dict[str, str] = {}
    match = re.search(
        rf"P38=`{instances['P38']}`[^；。]*?`(saved_verified|saved_unverified)`",
        map_543,
    )
    assert match, "tasks/TASKMAP.md 543 row no longer states P38's persistence state"
    states["P38"] = match.group(1)
    match = re.search(r"P39[^。]{0,40}`(saved_verified|saved_unverified)`", ledger)
    assert match, "tasks/543_semantic_layout.md no longer states P39's persistence state"
    states["P39"] = match.group(1)
    assert states == {"P38": "saved_verified", "P39": "saved_unverified"}, (
        "the source ledger/index must record CH343 P38 as saved_verified and CH340 P39 as "
        f"saved_unverified awaiting a reopen; got {states!r}"
    )

    # --- 路线图：两个拓扑都要在场，且各自的持久化状态与源头逐字一致。
    roadmap_543 = _table_row(roadmap_raw, "543")
    assert "两拓扑三关" in roadmap_543, (
        "docs/roadmap.md 543 row lost the two-topology three-gate verdict"
    )
    for topology, designator in (("CH343", "P38"), ("CH340", "P39")):
        assert topology in roadmap_543, (
            f"docs/roadmap.md 543 row dropped the {topology} topology"
        )
        match = re.search(
            rf"{topology}[^；。|]*?{designator}[^；。|]*?`(saved_verified|saved_unverified)`",
            roadmap_543,
        )
        assert match, (
            f"docs/roadmap.md 543 row no longer pairs {topology} {designator} with a "
            "persistence state"
        )
        assert match.group(1) == states[designator], (
            f"docs/roadmap.md says {designator}={match.group(1)!r} but the source "
            f"ledger/index says {states[designator]!r}"
        )
    assert "待关闭重开" in roadmap_543, (
        "docs/roadmap.md 543 row stopped naming P39's pending close-and-reopen"
    )

    # --- P39 不许被写成已重开（状态对拍已挡 saved_verified，这里再挡散文说法）。
    for match in re.finditer("P39", roadmap):
        window = roadmap[match.start(): match.start() + 80]
        assert not re.search(r"已关闭重开|重开验证通过|重开完成", window), (
            "docs/roadmap.md describes P39 as reopened/verified although the ledger keeps "
            "it saved_unverified awaiting a close-and-reopen"
        )

    # --- agent / 解释器分工：路线图与索引都要保留，且分工方向不能反。
    assert "agent 声明功能岛" in roadmap, (
        "docs/roadmap.md lost 'agent declares functional islands' — the constructive "
        "layout claim becomes content-free"
    )
    assert "解释器负责确定性几何" in roadmap, (
        "docs/roadmap.md lost 'the interpreter owns deterministic geometry'"
    )
    assert "agent 语义分岛" in map_543 and "解释器负责几何" in map_543, (
        "tasks/TASKMAP.md 543 row lost the agent/interpreter division of labour"
    )
    assert not re.search(r"解释器[^；。]{0,20}声明功能岛", roadmap), (
        "docs/roadmap.md inverted the division of labour: the interpreter does not "
        "declare islands"
    )

    # --- 201C/201D 不复活、201E 已落：裁决从索引读出，再要求路线图同判。
    for key, verdict in (("201C", "不复活"), ("201D", "不复活"), ("201E", "已落")):
        source_row = _table_row(taskmap_raw, key)
        assert verdict in source_row, (
            f"tasks/TASKMAP.md {key} row no longer carries the {verdict!r} verdict"
        )
        roadmap_row = _table_row(roadmap_raw, key)
        assert verdict in roadmap_row, (
            f"docs/roadmap.md {key} row no longer carries the {verdict!r} verdict"
        )
        assert "待复活" not in roadmap_row, (
            f"docs/roadmap.md {key} row was written back to 'pending revival'"
        )
        if key == "201E":
            assert "规划" not in roadmap_row and "在途" not in roadmap_row, (
                "docs/roadmap.md 201E row was written back to planning/in-flight although "
                "the index records it as landed"
            )

    # --- Board2/P1 是用户参考页，不是试验场；任何提到它的窗口都不许反过来。
    assert "Board2/P1 是用户参考页，不是试验场" in roadmap, (
        "docs/roadmap.md lost the ruling that Board2/P1 is the user's reference page, "
        "not a proving ground"
    )
    for match in re.finditer("Board2", roadmap):
        window = roadmap[match.start(): match.start() + 60]
        if "试验场" in window:
            assert "不是试验场" in window, (
                "docs/roadmap.md calls Board2 a proving ground again"
            )

    # --- 201x 历史读数只能当基线，不许冒充 P38/P39 的当前读数。
    assert "不是 P38/P39 的当前读数" in roadmap, (
        "docs/roadmap.md stopped marking the 201x readings as historical baselines rather "
        "than the current P38/P39 readings"
    )


# ==================================== 549：`role-not-allowed` 属于 BAD_REQUEST，不属于 UNAUTHENTICATED


def test_bridge_doc_files_role_not_allowed_under_bad_request():
    """护 549 §4 的 `pair.authorize` 行与 §5 的错误码表（第二轮复核第 3 条）。

    失效时的样子（就是修之前的两处）：`bridge.md` 的 `pair.authorize` 行写着
    「connector-role caller gets `UNAUTHENTICATED` with `reason: role-not-allowed`」，
    §5 的 `UNAUTHENTICATED` 行把 `role-not-allowed` 列进 reason 清单。daemon 实际上
    在 `_local_action` 的角色闸就抛 `ErrorCodes.BAD_REQUEST`——帧已经认证过了，错的
    是「这个角色没资格调这个动作」。照错的那份读，读者会去 revoke + 重新配对，而正确
    的处置是改用 CLI。

    钉子读三处：文档不许把两个词写进同一行；`pair.authorize` 那一行必须写明
    `BAD_REQUEST`；daemon 源码那段角色闸抛的也必须是 `BAD_REQUEST`（文档跟着代码走，
    不是反过来）。
    """
    doc = (REPO / "docs" / "bridge.md").read_text(encoding="utf-8")

    # 1) 任何一行都不许再用「gets `UNAUTHENTICATED`」这种归属句式挂 role-not-allowed。
    attributed = [
        line
        for line in doc.splitlines()
        if "role-not-allowed" in line and "gets `UNAUTHENTICATED`" in line
    ]
    assert attributed == [], (
        "docs/bridge.md attributes `role-not-allowed` to UNAUTHENTICATED again; the "
        "daemon answers BAD_REQUEST for a wrong role on `pair.authorize`. Offending "
        "lines: " + " || ".join(attributed)
    )

    # 2) `pair.authorize` 那一行必须把真正的错误码写出来。
    rows = [line for line in doc.splitlines() if line.startswith("| `pair.authorize`")]
    assert len(rows) == 1, "docs/bridge.md lost its `pair.authorize` row"
    row = rows[0]
    assert "role-not-allowed" in row and "gets `BAD_REQUEST`" in row, (
        "the `pair.authorize` row must say a connector-role caller gets BAD_REQUEST with "
        "reason role-not-allowed; it is a role refusal, not an authentication one"
    )

    # 3) §5 的 `UNAUTHENTICATED` 行里那句 reason 清单不许再收 role-not-allowed
    #    （这一行可以提到它，但只能用来把读者指向 BAD_REQUEST）。
    unauth = [line for line in doc.splitlines() if line.startswith("| `UNAUTHENTICATED`")]
    assert len(unauth) == 1, "docs/bridge.md lost its §5 `UNAUTHENTICATED` row"
    enumerated = re.search(r"`reason` is one of ([^.]*?)\.", unauth[0])
    assert enumerated, "the §5 `UNAUTHENTICATED` row no longer lists its reasons"
    reasons = set(re.findall(r"`([a-z0-9-]+)`", enumerated.group(1)))
    assert "role-not-allowed" not in reasons, (
        f"the §5 reason list is {sorted(reasons)}; role-not-allowed is BAD_REQUEST (§4)"
    )
    assert reasons == {
        "no-grant",
        "grant-expired",
        "code-missing",
        "code-mismatch",
        "record-changed",
        "connector-attached",
    }, f"the documented pairing-refusal reasons are {sorted(reasons)}"

    # 4) 文档跟着代码走：daemon 的角色闸抛的必须仍是 BAD_REQUEST。
    daemon = (REPO / "src" / "boardwise" / "bridge" / "daemon.py").read_text(
        encoding="utf-8"
    )
    gate_start = daemon.index('if action == "pair.authorize":')
    gate = daemon[gate_start: daemon.index("return self._authorize_pairing", gate_start)]
    assert "ErrorCodes.BAD_REQUEST" in gate, (
        "the daemon no longer refuses a connector-role `pair.authorize` with BAD_REQUEST; "
        "docs/bridge.md and its §5 table are now describing something else"
    )
    assert "ErrorCodes.UNAUTHENTICATED" not in gate, (
        "the role gate now raises UNAUTHENTICATED — that is the doc defect the 549 review "
        "fixed, and it has come back in the code"
    )
