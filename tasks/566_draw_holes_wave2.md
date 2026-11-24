# 任务书：566 / 567 — 绘制线挖洞第二批（八缝，只读）

- 批号 **566**（0.6.3 已发布 delta）+ **567**（存量不变量面）　日期 2026-11-24
- 承接 `tasks/565_draw_holes.md`（第一批六缝，24 洞）。本批把面从「最新一批」扩到**已发布但只浅挖过的 delta** 与**存量引擎不变量**。
- **性质：只读挖洞。只提交可复现问题，不修、不写生产与测试、不落画布、不碰真机。**

## ① 前因后果

- 565 只挖了 `28b9345..f508328`（0.6.3 之后）。再往前一段是 **0.6.3 正式发布的内容**，当时的挖洞只做了两项实锤
  （`recompile-with-locks` 改用 page locks、`pcb.path_probe` daemon 预算 150 s），其余面**没有第三双眼睛**：
  - `319a76e` **drawcompiler +1321 行**（legacy 保守 + 旗座救援/band/order），是 0.6.3 最大的绘制改动；
  - `0d989da` **cli.py +335 行**（零候选恢复、空页复用）；`0364fbc` **agentadjusted +180 行**（锁式移动、记账）；
  - `c6d7b25` / `1344464` 两笔桥侧写守卫（删页、pin NC），connector 侧 +446/+341 行测试。
- 这些提交都已**发布给用户**（0.6.3）：洞的代价比未发布批次高——用户手上跑的就是它。
- 567 挖的是**没有 delta 也能挖的面**：承重不变量（docs/testing-doctrine.md §模式 5 清单）——
  量化往返、粗筛下界、coverage 声称 ⊆ 实跑、packer keep-out、文本宽度上界、幂等。这些一旦破，
  任何一次自动布局的结论都不成立，且不依赖某批改动。
- 历史教训同前：143a「锁 rotation 只校验不应用」、143a「旗标兜底零导体」、548O「指纹不变当通过」、
  548B3「删 checker 注入仍绿」、坑 5「保存异步」、坑 24「导出文件对删除永不重算」。

## ② 当前树状态（开工先复核，不符就停）

| 项 | 读数 |
|---|---|
| HEAD | `f5083286de06b1d1b698a91e51da18463be4f4de`（main，**未推送**） |
| 工作树 | 混合未提交；563 面：`M src/boardwise/core/circuitsemantics.py`、`?? tests/test_563_*.py`、`?? docs/circuit-semantics.md`、`?? tasks/563_*`；其余 `M`（PROGRESS/handoff/roadmap/TASKMAP/review-line）与 `?? node_modules/ tmp*.json checkup/ docs/debug.log blocklib/parts.json.tmp` 是他人或临时件 |
| 565 产物 | `outputs/hole565/`（24 洞，`TRIAGE.md` 已分级）、`tasks/565_draw_holes.md` |
| 解释器 | `E:\boardwise\.venv\Scripts\python.exe`（只用这个） |

开工先抄 `git rev-parse HEAD` 与 `git status --porcelain=v1` 贴进报告。

## ③ 八缝分工与文件域（不重叠；同文件只查点名函数/区间）

### 566 — 0.6.3 已发布 delta

| 缝 | 地盘（只读） | 高危怀疑面 | 探针 | 报告 |
|---|---|---|---|---|
| **566-A 零候选恢复 / 空页复用** | `cli.py` 中 `_draw_zero_candidate_recovery`、`_draw_zero_candidate_next_line`、`_draw_page_rows`、`_draw_active_schematic`、`_draw_candidate_pages`、`_draw_geometry_readable`、`_draw_page_label` 及其调用点（`git show 0d989da -- src/boardwise/cli.py` 拿全量 diff）；`dsh-plugin/src/draw-tools.ts` 该批 7 行改动 | 恢复建议是否被读成「已修复」；空页复用会不会选中**非空页/别的工程页/带内容页**；`--candidate` 与复用页的对应；恢复条件在 `scope=page/project` 下是否一致；复用后 census/标记是否重置 | `.tmp_hole566/a/` | `outputs/hole566/a/` |
| **566-B 锁式移动与记账** | `engines/agentadjusted.py`（`_measured_pose`、`_recompile_with_locks`、`_declared_units` 及 `propose_agent_adjusted_move`）、`commands/draw.py`（该批 21 行）、`engines/v4facts.py`、`contracts/cli/v1.json` 的对应段 | 锁是否真的写回计划/落图（143a 洞1 同族）；**rotation/mirror 锁是否只校验不应用**；`automatic` 与 `agent-adjusted` 记账能否互换；`_declared_units` 的单位（mil/10-mil/px）与 v4facts 读取口径；proposal 在无测量 pose 时的回退 | `.tmp_hole566/b/` | `outputs/hole566/b/` |
| **566-C 旗座救援与 legacy 两轨** | `engines/drawcompiler.py`（`git show 319a76e -- src/boardwise/engines/drawcompiler.py` 拿 +1321 行；重点 `_flag_grouping_baseline/_flag_grouping/_flag_grouping_for_net`、`_flag_escape_bands`、`_FlagBandWalls`、`_WireFlagSeat`、`_placed_flag_obstacles`、`_wire_flag_seat_plan`、`_wire_flag_lead_band`、`_planned_seat_order`）、`engines/drawapply.py` 该批 8 行 | **legacy 与 native 两轨的判定条件**（哪一轨在什么输入下生效、有没有输入两轨都不走）；救援是否改变已验收页的几何（"preserve legacy" 是否真的零移动）；旗座 order 与 band walls 的一致；`grouping` 的 net 作用域；同网旗聚簇是否越过 S-01 keep-out | `.tmp_hole566/c/` | `outputs/hole566/c/` |
| **566-D 桥侧写守卫** | `bridge/protocol.py`（两笔新增 40/39 行）、`bridge/daemon.py` 该批 21 行、`connector/src/actions.ts`（删页守卫与 pin NC writer 段）；对照只读 `tests/test_page_delete_guard.py`、`connector/tests/pin-no-connected.test.mjs` | 守卫能否被绕过（缺 `confirm`/缺 `pageUuid`/错误工程名/别名工程）；**删除是"进回收站"还是直删**；NC writer 是否会写错页/错工程、是否校验回读；多窗口 hint 缺失时是否退化成"猜"；错误码是否与 docs 一致 | `.tmp_hole566/d/` | `outputs/hole566/d/` |

### 567 — 存量不变量面（不限 delta）

| 缝 | 地盘（只读） | 要证的不变量 | 探针 | 报告 |
|---|---|---|---|---|
| **567-E 量化 / 共线 / 幂等** | `engines/drawapply.py`（census、postcondition、discard、quantize 段）、`core/changeplan.py`、`core/candidate.py` | ① 0.01 量化往返：任意一位小数坐标 → 写入 → 回读相等；边界 0.005/0.015/负数/超大值；② 共线回读：宿主把相接线段合并后读数仍能对上计划（坑 32）；③ **幂等**：同一 plan 连做两次 apply，第二次必须 `already-applied` 且零改动；④ census 差异为空 ⇔ 无写入 | `.tmp_hole567/e/` | `outputs/hole567/e/` |
| **567-F packer 与页框 keep-out** | `engines/islandlayout.py`、`engines/pagecompiler.py`、`core/pageframe.py` | ① 任何 `ok=True` 的页，其所有呈现盒都在 `page_box` 内且不与任何 keep-out 相交（**暴力 oracle**：从布局产物逐件/逐线/逐旗/逐文字取盒，自己算交集，不信 packer 自述）；② 标题栏 keep-out 的派生与页框自洽（`title_block_keepouts` 随宽高变化）；③ 旋转/镜像件的 bbox 上界；④ 退化页框（宽<标题栏、高<band）是否干净拒绝 | `.tmp_hole567/f/` | `outputs/hole567/f/` |
| **567-G 文本度量与载体** | `core/textmetrics.py`、`core/presentationspec.py`（`wire_name_row` 相关）、与 `engines/svgpreview.py` **只读交叉**（不复述 S6 的 H1/H2/H4） | ① 宽度模型**单调性**（更长/更宽字符集不窄）与**上界**（不超过同字符数的最大前进宽）；② 名字行 ↔ 载体一一对应（每个需要名字的网恰好一行，无孤儿行）；③ 字号/像素常量只有一个来源（今天有 `RENDER_TEXT_PX` 与 `NATIVE_TEXT_FONT_SIZE` 两个数）；④ 非 ASCII/全角/emoji 的宽度与转义 | `.tmp_hole567/g/` | `outputs/hole567/g/` |
| **567-H 承重无测试覆盖（静态盘点）** | 全 `src/boardwise/{engines,core,commands}` 的 public 函数与 `cli.py` 的 draw 分支，对照 `tests/` 的 import/调用 | 找**承重但零测试**的面：无任何测试 import/调用、只有 happy-path 覆盖、或断言只钉"不崩"（`assert x is not None`）。输出一张「函数/分支 → 有无测试 → 覆盖类型」表，**只报承重缺口的 suspect**，不写洞 | `.tmp_hole567/h/` | `outputs/hole567/h/` |

## ④ 交付物与验收（每缝同 565）

1. `outputs/hole56{6,7}/<seam>/REPRO.md`：每条六栏（编号/严重度/一句话/文件:行/因果/复现命令→实测 vs 应有）。
2. `probes/`：可重跑原样脚本；`holes.json`（`schema: "boardwise.hole56{6,7}/1"`，字段同 565 §④，
   `status ∈ {reproduced, falsified, suspect}`）。
3. 每条 `reproduced` 必须有一次真实运行读数原文；每条至少一次证伪尝试写进 `falsifiedAttempt`；给预测最小修法 + 能先红的变异，**不许实施**。
4. 严重度四级沿用：`会造假结果` > `会崩` > `会漏` > `仅不一致`。
5. **566 额外要求**：洞必须能指到「哪一笔提交引入」与「0.6.3 是否已发布给它」——用 `git log -S`/`git blame` 给行号归属。
6. **567 额外要求**：不变量类洞必须附**暴力 oracle 的实现**（自己重算一遍再比）或**属性测试思路**，不许只凭读代码说"这里可能不成立"。

## ⑤ 纪律与红线（逐条写死）

- **只读**：不改 `src/ tests/ docs/ contracts/ connector/ dsh-plugin/ blocklib/`；不新增测试；探针只写自己的 `.tmp_hole56x/<seam>/`，报告只写自己的 `outputs/hole56x/<seam>/`。
- **不动 git**：零 `add/commit/checkout/restore/stash/push`；查历史只用 `git show/diff/log/blame`（只读）。
- **不删任何东西**；**不碰真机**（零 `boardwise bridge`、零 daemon、零编辑器、零真实工程写入；566-D 只做代码与离线合同测试的只读审计）。
- **测试红线**：只说点名文件；每条命令带 `--basetemp=.tmp_pt_hole56x_<seam>`；禁全量、禁 `-n auto`/`-n >4`；探针单进程；前台命令带 timeout。
- **不碰历史证据**：`outputs/011e*`、`014_*`、`015b_*`、`016_*`、`tests/fixtures/` 只读引用。
- **保密**：不出现公司/客户名与真实工程名，实名板只写 `PCB1/PCB2/PCB3`。
- 不重复 565 已报的洞（见 `outputs/hole565/TRIAGE.md`）——撞到就写一行「与 565-XX 同源」并跳过。

## ⑥ 预算与交卷格式

- 每缝 **≤40 步或 ≤30 分钟**，先到先停。
- 交卷正文 ≤2000 字，四段：`环境读数（含本条洞的提交归属）` → `洞表（编号/严重度/一句话/状态）` → `证伪清单` → `没查的面 + 下一步最小动作`。
- 零洞也要交，写清查了什么、为什么零。
