# 565e — PresentationSpec 声明闭合的两条洞（S4-1 / S4-2）

- 批号 **565e**　日期 2026-11-25　owner：绘制线/声明层　状态：**待派**
- 来源：`outputs/hole565/TRIAGE.md` §1 的 565e 组；2026-11-25 主代理重新判定：**两条都仍复现**
- 文件域：`src/boardwise/core/presentationspec.py`、`src/boardwise/engines/grammar/mixed_island.py`（若确需）、新建 `tests/test_565e_declaration_holes.py`、`evidence/565e/`

## ① 前因后果

`modules[].freeParts` 是 548L 加的声明：这一组的某些两脚支路属于本岛但不绑 core 角色。它只被 **`ic-periphery`** 与 **`mixed-island`** 两个文法消费。于是有两个静默面：

- **S4-1**：同一件同时被 `modules[].core` 与 `modules[].freeParts` 点名——文档原样收下，矛盾只被无关的「2 脚不能当 core」拒因掩盖（换 3 脚件或 page 路径就不报）。
- **S4-2**：`freeParts` 在别的文法（如 `voltage-divider`）下被收下、零披露、**几何零影响**。

主代理 2026-11-25 重放 `outputs/hole565/s4/probes/probe_conflict.py` + `diff_layout.py` 的读数（子代理开工必须自己复跑）：

```
ROUNDTRIP module core/freeParts: [('divider', 'R1', ['R1'])]      ← S4-1 仍收下
out_free_parts_ignored_by_divider: 3 differing leaf paths
  .geometrySha256 / .provenanceSha256 / .source.presentationSha256  ← 只有哈希变
  （parts/segments 等几何叶子零差异）                                ← S4-2 仍是零影响
```

## ② 当前树状态

- HEAD **`76e08060ded403793bc6fb0eb64b38f9e140c765`**，工作树混合未提交；两个文件均为已提交面（本批是 2026-11-25 首改）。
- 相关位置：
  - `_modules_from` `presentationspec.py:1536-1569`（收 `root`，可读文档级 `grammarRef`；每模块已解析 `core` 与 `free_parts` 到 `PresentationModule`）
  - `_module_free_parts` `:1702-1736`（只校验成员资格与重复）
  - `_module_core`、`_module_grammar` `:1739-1749`
  - `grammar/mixed_island.py:74` `free_parts()`、`grammar/ic_periphery.py:239/759`（唯二消费者）
- 全仓 `free_parts|freeParts` 消费者只有 `ic-periphery` 与 `mixed-island`（主代理已扫）；`pagecompiler.py:1209` 只做传递。
- 开工备份：`cp` 两个文件到 `.tmp_565e/backup/` 并记 SHA-256。

## ③ 文件域与禁触清单

**允许：** `src/boardwise/core/presentationspec.py`、`src/boardwise/engines/grammar/mixed_island.py`、新建 `tests/test_565e_declaration_holes.py`、`evidence/565e/`、`.tmp_565e/**`。

**禁触：** `core/circuitsemantics.py`、`core/netlist.py`（565b）、`engines/drawlint.py`（565g）、`cli.py`、`commands/draw.py`、`engines/svgpreview.py`、`tests/fixtures/`、任何既有测试断言（合法变红就停下报告）。不许改 `_MODULE_KEYS`（不新增键）。

## ④ 交付物与验收（先红后绿）

新建 `tests/test_565e_declaration_holes.py`，先红原文存 `evidence/565e/RED.txt`。父级裁决：

| 洞 | 期望行为 | 先红断言 |
|---|---|---|
| **S4-1** | `PresentationSpec.from_dict` 对同一模块 `core` 与 `freeParts` 点名同一件 → `PresentationSpecError`，话术同时点名 `modules[<id>].core` 与 `modules[<id>].freeParts[i]`，并说明「一件只能属于一个角色」。带 `--page-box` 的 page 路径同样在解析层拒绝（不靠脚数拒因） | 现返回对象；`divider` + `core=R1` + `freeParts=[R1]` 不抛 |
| **S4-2** | 模块声明了 `freeParts`，但**有效文法**（模块 `grammarRef`，缺省取文档 `grammarRef`）不是 `ic-periphery` / `mixed-island` → `PresentationSpecError`，话术说明「freeParts 只由这两个文法消费；其它文法收下就是静默丢弃」。空 `freeParts` 不受影响 | `voltage-divider` + `freeParts=[R1]` 现编译 exit 0、三个候选、几何零差异 |

**验收读数：**

```
.venv\Scripts\python.exe -m pytest tests/test_565e_declaration_holes.py -q --basetemp=.tmp_pt_565e
.venv\Scripts\python.exe -m pytest tests/test_565e_declaration_holes.py <相邻既有 presentationspec/grammar 测试> -q --basetemp=.tmp_pt_565e
.venv\Scripts\python.exe outputs\hole565\s4\probes\probe_conflict.py      ← 重放要看到两条都转「拒绝」
```

- 先红 ≥2 failed；后绿全 passed。
- **逐洞变异**：S4-1 把冲突判断改成 `if False:`；S4-2 把文法白名单判断改成 `if False:`——各自点 named 用例先红，再 `.tmp_565e/sub-backup/` `cp` + SHA-256 还原复绿。两次读数写报告，禁用 git 恢复。
- 反向保护：**合法**用例必须仍绿——`mixed-island` + `freeParts`、`ic-periphery` + `freeParts`、不带 `freeParts` 的其它文法（voltage-divider 基线）都要能解析/编译。

## ⑤ 纪律与红线

1. 零 git 写；零删除（禁 `rm`/`Remove-Item`）。
2. 不跑全量 pytest、不 `-n auto`、不碰 bridge/EDA、不联网。
3. 不新建第二套声明校验器；只在这两个既有函数上补拒绝。不把 `freeParts` 静默改写成别的东西来"修复"。
4. 不得放宽既有断言、加 skip/xfail、改夹具；不为通过而扩大白名单（白名单就是 `ic-periphery`/`mixed-island` 两项，新增需主代理裁决）。
5. 有红项或无读数，写「停止/未验收」。

## ⑥ 预算与交卷格式

- 上限 **40 步 / 30 分钟**。
- `evidence/565e/REPORT.md`：开工哈希、先红原文、修复点（文件:行）、两次变异读数、后绿原文、`probe_conflict.py` 前后对照、合法用例清单、未做项。
- 最终回复 ≤2000 字：结论 + 关键读数 + 证据路径 + 需裁决项。
