# 任务书：569 / W-T — page 标题栏 keep-out 与计划往返

- 日期：2026-11-24
- 范围：TRIAGE 的 **567-F-1 + 565-S3-1 + 567-F-2（同根因）**，只修这一缺口。
- 执行：一个 `coder` 子代理；主代理负责独立复验。离线小批，不真机、不全量。

## ① 前因后果

`outputs/hole566/TRIAGE.md` 将三条已复现问题归为 W-T：

1. `outputs/hole567/f/REPRO.md` H-567F-1：page 呈现路径 `_cmd_draw_compile_page` 调 `_draw_page_budget(page_box)` 时不传标题栏；1170×600 的 CH343 页在 `ok=True` 下，首两候选分别有 5/16 个真实呈现盒进入 `(460,10)-(1160,190)`。直接给 `PageCompileBudget` 传 `title_block_keepouts` 后，页数变 6，首两候选 163 盒零相交，证明是 CLI 接线缺口，不需要新 packer。
2. `outputs/hole565/s3/REPRO.md` S3-1：fresh page `draw plan` 不写 `ISLAND_PAGE_KIND` 与 `keep_out_note`，apply 的 S-01 双闸整段跳过；saved-page 路径已有正确实现，可复用，不得另造闸。
3. `outputs/hole567/f/REPRO.md` H-567F-2 与 565-S3-2：`keep_out_note` 用 `%g`，`1234.567` 回读成 `1234.57`，与 apply 的 1e-6 比较精度不匹配。

主代理已通读三份证据及当前实现。必须一次闭合「编译预留 → plan 记录 → apply 消费」整条链，不能只把相交数量藏到别的候选，也不能只加披露文字。

## ② 当前树状态

- HEAD：`f5083286de06b1d1b698a91e51da18463be4f4de`，main，ahead 1；**禁止任何 git 写**。
- 本批文件在开工时均为 HEAD 原样：
  - `src/boardwise/cli.py` SHA-256 `d7a9b5a0e5cb6a63543c72f730a8979dffdd38b68793802d1c70126b34aa7c5e`
  - `src/boardwise/core/pageframe.py` SHA-256 `9bb0c0186d7401762284a46363b5e98d84d1128d86cc8ad355c11a48c76c0724`
- 混合工作树属于他人/既有批次：`PROGRESS.md`、`docs/handoff.md`、`docs/roadmap.md`、`src/boardwise/core/circuitsemantics.py`、`tasks/TASKMAP.md`、`tasks/review-line.md`，以及 563 的 `docs/circuit-semantics.md`、`tasks/563_netlist_semantics.md`、`tests/test_563_*.py`。`tasks/565_*`、`566_*`、 **`tasks/568_draw_holes_wave3.md`** 与临时/未跟踪文件也一律保留。
- 关键现状：
  - `cli.py:15279` `_draw_page_budget` 已支持 `keepouts` / `relocate`；`:15366-15368` 的 page compile 没传。
  - `cli.py:15713-15715` 仅 saved page 派生标题栏；`:15723-15727` fresh compile 只传 census keepouts；`:15753-15757` 仅 saved page 写 S-01 marker/note。
  - `core/pageframe.py:241-258` 八个数值都用 `:g`；`:230-233` 的注释也仍宣称 `%g` 足够，修代码时必须同步修正注释。

实施前先用 `cp` 把两个生产文件备份到 `.tmp_569/backup/`，记录备份与当前 SHA-256；禁止依赖 git 恢复。

## ③ 文件域与禁触清单

允许新建/修改仅：

- `src/boardwise/cli.py`（仅限上述 page compile/plan 装配及必要的 preview keepout 传递）
- `src/boardwise/core/pageframe.py`（`keep_out_note` 精度及对应注释）
- `tests/test_569_title_block.py`（新聚焦回归；项目已有测试体系，允许新增）
- `tests/test_057_draw_page_cli.py`（主代理续审授权：仅让 `_PageEditor` 回答自身图幅的 `sys.get_document_source`，不得改既有断言或生产行为）
- 本任务书、`.tmp_569/`、`.tmp_pt_569/`、`evidence/569/`

禁止触碰：

- ②列出的全部他人文件，尤其 `core/circuitsemantics.py`、563 测试/文档、`tasks/568_draw_holes_wave3.md`。
- `engines/pagecompiler.py`、`engines/islandlayout.py`、`engines/readability.py`：现有机制已被证据证明可用，本批不另造 packer/router/builder，不改算法阈值、页框、预算或候选排名。
- `outputs/hole565/`、`outputs/hole566/`、`outputs/hole567/`、`tests/fixtures/`、`contracts/`、`connector/`、`dsh-plugin/`、`docs/`、`PROGRESS.md`、`tasks/TASKMAP.md`。
- 不修改既有测试断言来凑绿；若既有测试因预期行为变化而红，先交证据，不擅自放宽。

## ④ 交付物与验收

### 先红回归（必须在生产改动前真实运行并留原文）

在 `tests/test_569_title_block.py` 固化以下断言，先对未改源码运行，确认相应用例失败；控制用例必须通过：

1. **page compile 暴力几何 oracle**：仅用仓库 `blocklib/specs/ch343_uart.*` 既有输入，在 `(0,0,1170,600)` 走真实 CLI page compile 路径；对所有产出候选（至少覆盖原报告首两候选）从 `LayoutPlan` 独立重建器件体/脚尖、导线、junction、label、旗 glyph、文字盒，断言每盒在 page box 内且与 `title_block_keepouts` 正面积相交数为 0。不得只检查 module frame，不得拿 `keepout_conflicts` 或 `ok=True` 自证。修复前须复现相交，修复后同一生产尺零相交；preview 也应收到同一标题栏 keepout。
2. **fresh-page 计划记录**：复用 057 的真实 page plan 输入/助手，断言 fresh page 计划含 `islandlayout.ISLAND_PAGE_KIND`，`page_keep_out_from_notes` 精确返回该计划页框与标题栏，且 `cli._draw_plan_is_island_page(plan)` 为真；saved-page 与 single-module 的既有行为不得改变。
3. **fresh-page 编译同时保留两类 keepout**：有 census keepout 时，标题栏必须附加且去重，census 不得被标题栏替换；relocate 必须对合并后的集合适用。
4. **精度往返**：至少覆盖 `(0,0,1234.567,825)`、`(0,0,1169.0049999,826)` 及负坐标/非零原点各一例；`keep_out_note → page_keep_out_from_notes → _draw_same_box` 必须为真，标题栏四值也逐值相等。整数/半整数既有往返为控制，不得退化。

### 实施口径

- `_cmd_draw_compile_page` 从 `page_box` 派生标题栏，传给现有 `_draw_page_budget(..., relocate=True)`；preview 使用同一 keepout 集。
- fresh page plan 使用与 saved page 相同的 S-01 派生、marker 与 note；fresh compile 消费 census + title 的合并 keepout 集，去重沿现有 `_draw_same_box`。saved page 仍只检查、不重排。
- `keep_out_note` 用能往返 Python float 的 `%.17g`（页框和标题栏全部数值），同步修正注释；不改 apply 的 1e-6 比较，不放宽 `_draw_same_box`，不顺手修 S3-3 suspect。
- 不新增公开 CLI 参数、JSON 合同、DSH 工具或 bridge 动作。

### 修后测试与变异

至少运行并留存完整汇总行：

```bash
.venv/Scripts/python.exe -m pytest tests/test_569_title_block.py -q --basetemp=.tmp_pt_569/new
.venv/Scripts/python.exe -m pytest tests/test_057_draw_page_cli.py tests/test_533_island_guard.py tests/test_530g_title_block_keepout.py tests/test_540_cli_draw.py tests/test_owner_rules.py tests/test_layer_rules.py -q --basetemp=.tmp_pt_569/neighborhood
```

- 每项失败都如实交，不把环境错误写成通过，不跑全量。
- 至少两项生产变异，各自先备份、变异、跑聚焦测试必须红、`cp` 恢复、SHA-256 与修后一致：
  1. fresh/page compile 的标题栏入口改回 `()`，暴力几何或 fresh-plan 断言必须红；
  2. `%.17g` 改回 `%g`，精度往返断言必须红。
- 交回：前后几何相交数、plan marker/note 读数、测试命令与汇总行、两项变异原文、修后文件 SHA-256、未覆盖项。证据落 `evidence/569/`，日志落 `.tmp_569/`。

## ⑤ 纪律与红线

- 零 `git add/commit/checkout/restore/stash/push`；不创建/删除 worktree。
- 禁止 `rm`/`unlink`/任何直删；本批无需删除。移动或回收站删除也须另行授权。
- 不碰真机、daemon、编辑器、真实工程；不调用 bridge。
- 不跑全量 pytest；探针单进程，不用 multiprocessing/线程池；前台命令带 timeout。
- pytest 必须带独立 `--basetemp=.tmp_pt_569/...`，禁 `-n auto`、禁 `-n >4`。
- 不修改既有夹具，不碰 `outputs/011e*`、`014_*`、`015b*`、`016_*`。
- 本批是离线机器合同修复，没有新原理图交付，故真机逐脚/视觉标为「不适用，未做」；不得声称 P1、CH343 真机或任意页面已通过三关。

## ⑥ 预算与交卷格式

- 一个 coder，最多 **40 个模型步骤或 30 分钟**，先到先停；不派下一级代理。
- 交卷正文 ≤2000 字，依次写：`实际改动` → `先红→修后绿的实测命令与汇总行` → `两项变异与 SHA 恢复` → `未做/红项/下一步`。
- 详细日志只落文件，正文必须给可复算路径。同一拒因连续两轮无新证据即停止交接，不调参数续命。
- 有未解决本批红项、缺暴力几何读数或缺变异时，只能写「停止/未完成」，不得写「完成」。
