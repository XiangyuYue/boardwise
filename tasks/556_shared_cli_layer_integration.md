# 556：CLI 合同与 `_page_y` 跨层集成

## 1. 前因后果

岳的目标第 1 项。14e8f39 已提交 552–555，但 `parts hunt --live/--from-report` 未进入 `contracts/cli/v1.json`；绘制线与 bridge 也有未提交 CLI 表面。当前实测 `test_540c_contracts + test_layer_rules` 为 **5 failed / 47 passed**，其中四条合同快照红，一条为 `engines/v4facts.py` 私有导入 `parsers._page_y`。证据 `.tmp_goal_shared/`。

## 2. 当前树与最小裁决

- HEAD `14e8f39`，混合工作树。不得覆盖 `commands/draw.py`、`bridge/protocol.py`、`cli.py`、`commands/review.py` 或绘制线 hunks。
- 合同只由 `PYTHONPATH=. .venv/Scripts/python.exe tools/cli_contract.py --write` 从真实 parser 一次生成，把**当前已经存在的** hunt/draw/bridge 表面一起纳入；不手工拼、不把生成快照当成对这些 hunks 的源码所有权。
- `_page_y` 定义在 shared `parsers/schematic.py`，draw 的 v4facts 可依赖 shared 但不能依赖私有名。最小修复：同文件提升公有 `page_y`，保留 `_page_y = page_y` 兼容别名，内部旧调用与文档不改；v4facts 仅改公有 import 和调用。禁止 `import page_y as _page_y`、模块名绕私有访问或搬到 core。

## 3. 文件域与禁触

只允许：`src/boardwise/parsers/schematic.py`、`src/boardwise/engines/v4facts.py` 上述两行、`contracts/cli/v1.json` 生成物、`.tmp_556/`、`.tmp_pt_556/`、`evidence/556/`。不改测试、文档、owner 表、其他源码或真实工程。

开工前 cp 备份两个源码到 `.tmp_556/backup/` 并记 SHA-256。禁止 Git 写、rm/unlink、git restore、全量 pytest、bridge/EDA、部署和发布。

## 4. 验收与 negative controls

- `test_no_private_name_crosses_a_layer` 修复前已红，修后必须绿；把 `_page_y` 加回 v4facts 的独立变异必须再红。
- 去掉 page_y 负号，`test_v4_facts.py` 与 `test_agentadjusted.py` 的实际翻转断言必须红；恢复后绿，证明不是复制第二份转换。
- `tests/test_540c_contracts.py`、`test_layer_rules.py`、`test_owner_rules.py`、`test_v4facts.py`（实际文件名 `test_v4_facts.py`）、`test_agentadjusted.py` 及 552/553/555 聚焦测试通过；pytest 必带 `--basetemp=.tmp_pt_556`。
- 只读 `git diff` 证明除上述两个源码 hunk 与生成合同外零生产改动；`tools/cli_contract.py` check mode 通过。
- 主代理亲看关键 diff、独立做两项变异并 cp+SHA 恢复。后续 559 新 CLI 仍会要求最终再生成一次合同，这不构成重复全量。

## 5. 交卷

一个 coder，≤40 步/30 分钟，≤2000 字。报告实际命令→汇总→差异、生成合同包含的三类 drift、源码 SHA 和未覆盖项；失败不得写成全绿。零 Git 写、零部署、零发布。

## 6. 实际完成（560 收尾时补记）

- `parsers.schematic.page_y` 公有化并保留 `_page_y` 兼容别名；`engines/v4facts.py` 只消费公有入口，没有第二份转换。
- `contracts/cli/v1.json` 由 `tools/cli_contract.py --write` 从真实 parser 一次生成，hunt/draw/bridge 三类既有漂移同批收口，check mode 通过。
- 主代理两组独立变异（`evidence/556/parent-mutations.md`）：v4facts 回退私有 `_page_y` → **1 failed / 8 passed**；去掉 `page_y` 负号 → **4 failed / 37 passed**；两次均 cp+SHA 恢复，恢复后 **50 passed in 15.23s**。
- 状态：**工作树完成、未提交未推送**。本批不宣称全量绿，全量由 560 之后的主代理统一跑。
