# 任务书：565 — 绘制线挖洞 swarm（只读，六缝）

- 批号 **565**　日期 2026-11-24　来源：用户要求「挖 boardwise 绘制线的洞」。
  按 `docs/testing-doctrine.md` §发布闸①「对自上一版以来的 delta 派一轮只读审计 swarm（六缝模板）」执行；
  模板先例 `tasks/192_release_holes.md`、`tasks/143-drawing-dig-triage.md`。
- **性质：只读挖洞。只提交可复现问题，不修、不写生产代码与测试、不落画布、不碰真机。**
  「挖洞与修复分批」（AGENTS.md §DSH-2）——发现即交报告，修复另批派单。

## ① 前因后果

- `539169c`（0.6.3 发布准备）之后只有一个代码提交：**`f508328`（564，`Harden schematic drawing and verification flow`）**，
  src 20 文件 **+3290/−144**，是 0.6.3 之后**未经外部挖洞**的最大一段绘制线 delta。本次挖洞就是这个区间
  （`28b9345..HEAD` 的源码面）+ 563 的**未提交工作树**最终闭环改动。
- 564 的验收只覆盖**一张页**：P1（pageUuid `65522bd768798a16`）47 件/52 旗、逐脚 189/189、lint 0E/1W/7I、独立视觉 ACCEPT、
  重开 `saved_verified`。交接明写「仅证明本页与当前输入，不宣称任意自动布局」。**单页通过 ≠ 通用能力**，
  这正是要挖的缝：同一条链在别的输入、别的页、别的旗标/标签组合上是否仍成立。
- 564 修的四类根因（`docs/handoff.md` 顶部）：原会话自写 `lock_parts.py`/`lock_wire.py`/`lock_redraw.py` **绕过生产链**、
  无 GND、轨短接、电容同网、实体叠放；批次补齐「电气 lint」「saved-page 标题栏双闸」「空复制属性身份」
  「0.01 量化与共线回读」「预览 7.006px 字号」「`wire_name_row` 名字载体模型」。**每个新闸都是本次的挖洞对象：
  它拦得住原会话那种写法，拦不拦得住下一步的变形写法？**
- 历史教训（不许重复踩）：
  - 143a「锁 rotation 只校验不应用」——**校验了常量却从不消费**，19 个锁全过是巧合。**声明 → 消费**这条缝每批都出新洞。
  - 143a「旗标兜底把多脚网画成零导体」——postcondition 恒不成立却报通过。
  - 548B3「仅删 checker 注入」变异仍绿 → **测试覆盖洞伪装成能力**。
  - 548O/548M「以几何指纹不变当通过」——指纹只证明没挪动，不证明能看（`tasks/draw-line.md` §4）。
  - P27「svgpreview 只画 bbox 和 tip 圆点，不是原生外观」——预览自述与实际不符即洞。
  - 坑 51「`sch.geometry` 的 `netflag.Component.name` 是字形名（`Ground-PGND`），网名在 `Net`/`Name`/`Global Net Name`」。
- 当前线的已知红（不是本批要修，只需知道别当发现）：全量 Python `12101 passed / 18 failed`，其中 9 项在 HEAD 也失败；
  交接未写「全仓全绿」，挖洞报告不得把它读成本批新洞，也不得掩盖。

## ② 当前树状态（开工先复核，与本节不符就停手报告）

| 项 | 读数（2026-11-24 主代理实测） |
|---|---|
| 分支 / HEAD | `main` / `f5083286de06b1d1b698a91e51da18463be4f4de`（`Harden schematic drawing and verification flow`），**未推送、未发布** |
| 工作树 | **混合未提交**：`M src/boardwise/core/circuitsemantics.py`、`?? tests/test_563_circuit_semantics.py`、`?? tests/test_563_netlist_view.py`、`?? docs/circuit-semantics.md`、`?? tasks/563_netlist_semantics.md`（563 的最终闭环修复，**属本次审计面**）；`M PROGRESS.md / docs/handoff.md / docs/roadmap.md / tasks/TASKMAP.md / tasks/review-line.md` 与 `?? node_modules/ tmp*.json checkup/ blocklib/parts.json.tmp docs/debug.log` 是他人或临时件（**不是本批对象，不许碰**） |
| 挖洞区间源码面 | `git diff --stat 28b9345 HEAD -- src/` → 20 files, 3290 insertions / 144 deletions |
| 解释器 | `E:\boardwise\.venv\Scripts\python.exe`（**只用这个**，不要用系统 python） |

开工第一件事：`git rev-parse HEAD` + `git status --porcelain=v1` 抄下来贴进报告，证明你看的是同一棵树。

## ③ 六缝分工与文件域（域与域不重叠；同一文件只查自己点名的函数/区间）

| 缝 | 地盘（只读） | 已知高危类（不限于此） | 探针落点 | 报告落点 |
|---|---|---|---|---|
| **S1 网表与电路语义** | `core/netlist.py`、`core/circuitsemantics.py`（**工作树版本**）、对照只读 `tests/test_563_*.py` | `PinRef` 身份/解析边界（同号脚、同名实例、名字含 `.`/`-`/空格/非 ASCII、`U1.1.2`）；多单元/跨板重号；NC 与悬空；`series` 两端网闭合；`verify_semantics` 是否**真复算**而非拿同一份 payload 自证；`to_c()` 转义与确定性（set/dict 序 → 输出抖动）；`unproven_nets` 语义；`compile_semantics` 对空模型/单脚网/自环的行为 | `.tmp_hole565/s1/` | `outputs/hole565/s1/` |
| **S2 电气 lint 与闸门口径** | `engines/drawlint.py`（新增 `check_wire_rail_conflict` / `check_part_overlap` / `check_rail_without_flag` / `check_netlist_electrical` 及其调用点）、`cli.py` 中 `draw lint` 装配区间（约 **16600–17100**） | 缺 `--netlist` 时电气谓词**显式未跑**——输出/退出码/报告是否诚实披露，别把「没跑」印成「通过」；E/W/I 计数与 findings 数量是否自洽；坑 51 字形名当网名；数字脚名（`1`/`01`/`1.1`）判读；564 四类真实故障（无 GND/轨短接/电容同网/实体叠放）在**变形输入**下是否仍被抓；旗标自己名字被当冲突对象（`_is_flag_own_name`）；`_page_flag_lands`/`_page_segment_holds_end` 的容差是否给「明显脱线」开脱 | `.tmp_hole565/s2/` | `outputs/hole565/s2/` |
| **S3 plan/apply/持久化守卫** | `engines/drawapply.py`、`core/changeplan.py`、`core/candidate.py`、`engines/agentadjusted.py`；`cli.py` 的 plan/apply 装配区间（约 **11700 / 13700 / 15700** 三处 `_draw_plan_is_island_page` 及其邻域，另 **17400–17700** `saved_verified/saved_unverified` 账目） | 563/564 新代码：页标题栏双闸是否**每次**都真的跑（注释自承曾有「silently skipped the title-block guard」）；空复制属性身份；0.01 量化与共线回读；`wire_name_row` 载体；`device_uuid` 混合图元的 preflight 去重；`saved:true` vs 落盘（坑 5）；`saved_unverified` 会不会被写成 `saved_verified`；`discard` 删除面（143 的「误删同网外来走线」旧洞）；agent-adjusted 记账能否冒称 automatic | `.tmp_hole565/s3/` | `outputs/hole565/s3/` |
| **S4 编译/布局/文法** | `engines/drawcompiler.py`、`engines/grammar/ic_periphery.py`、`engines/grammar/mixed_island.py`、`engines/pagecompiler.py`、`core/presentationspec.py` | **声明有没有被消费**：`stubMin`/`reach`/`branchOrder`/`sidePreferences`/`attach`/`core`/`role`/`railClustering`/`gndClustering`/`labelPolicy.*`/`pageArrangement`/`serviceGroups` 逐键查「解析 → 传递 → 真正生效」；mixed island 的 `free_parts` 与 `_free_parts_problem` 是否放行了无约束孤岛；成对支路一致性（boardwise-draw §3）；`ok=True` 是否可能由「零候选 + 兜底」假通过；同输入两次编译是否确定性 | `.tmp_hole565/s4/` | `outputs/hole565/s4/` |
| **S5 CLI / DSH 合同面** | `cli.py` 的 draw/lint/plan/apply 参数注册与 `commands/draw.py`；`bridge/protocol.py`（本区间新增项）；`dsh-plugin/src/draw-tools.ts`；`contracts/cli/v1.json` | 参数**收下但不用**（143 洞1「`--new-page` 静默忽略仍 exit 0」同族）；`--json` 非原子写；退出码与 `docs/draw.md`/help 文案不符；DSH 工具构造 argv 时**丢参/改参**或把 stdout 当结论；`contracts/cli/v1.json` 与真实命令面漂移（555 有「一次生成」机制，查它是否仍被绕过）；未知参数是否静默吞 | `.tmp_hole565/s5/` | `outputs/hole565/s5/` |
| **S6 预览/渲染诚实性与文字盒** | `engines/svgpreview.py`、`core/textmetrics.py`（`wire_name_row` 相关）、`cli.py` 的 `_draw_lint_body_boxes`（约 **16640–16760**）与 `--bodies` | 预览是否**冒充原生外观**（P27 教训：bbox+tip 圆点 vs 真原生引脚线/脚名/ATTR）；新增 native text / label carrier 是否只在特定开关下生效而默认仍画假文字；`--bodies` 文档写 list-of-list、实测 geometries 是别的形状 → 是否静默接受垃圾或静默丢盒；`7.006px` 字号模型与实际渲染字宽是否对得上；渲染失败/缺字时是否静默出图；SVG 里的非法字符/未转义文本 | `.tmp_hole565/s6/` | `outputs/hole565/s6/` |

## ④ 交付物与验收（每缝都一样）

1. **`outputs/hole565/sN/REPRO.md`**：每条洞按下面六栏写，**命令必须可被主代理原样抄走复现**：
   `编号 | 严重度 | 一句话 | 定位（文件:行） | 因果 | 复现命令 → 实测读数 vs 应有读数`。
2. **`outputs/hole565/sN/probes/`**：探针脚本原样保留（单文件、`argv` 可重跑），别只贴片段。
3. **`outputs/hole565/sN/holes.json`**：机读行，`schema: "boardwise.hole565/1"`，每条含
   `id / seam / severity / status / title / file / line / cause / repro / observed / expected / evidence / falsifiedAttempt / fixSketch / mutationIdea`。
   `status ∈ {reproduced, falsified, suspect}`：**证伪也是交付**（写清「原以为 X，实测不是，证据在 …」），
   没有 `reproduced` 的猜测一律 `suspect` 并单列，**不许混进洞表**。
4. **严重度四级**（143 口径）：`会造假结果` > `会崩` > `会漏` > `仅不一致`。
5. **验收要求（缺一不算交卷）**：
   - 每条 `reproduced` 洞必须有**一次真实运行的读数原文**（命令 + 输出关键行），不是推理。
   - 每条至少试过一次**证伪**（换输入/换顺序/换开关），把结果写 `falsifiedAttempt`；没试过就写「未试」。
   - 每条给出**预测的最小修法**（一句话 + 打在哪一行/哪个键）+ **一个能先红的变异/断言**，**但不许实施**。
   - 报告开头写「本缝查了什么、没查什么」——**没查的要写清**，不许用没查当通过。

## ⑤ 纪律与红线（逐条写死）

- **只读**：不修改 `src/`、`tests/`、`docs/`、`contracts/`、`connector/`、`dsh-plugin/`、`blocklib/`、`tests/fixtures/` 任何文件；
  不新增测试；探针脚本只写在 `.tmp_hole565/sN/`，报告只写在 `outputs/hole565/sN/`。
- **不动 git**：零 `add/commit/checkout/restore/stash/push`；不用 `git checkout --` 还原任何东西（本批不需要还原）。
- **不删任何东西**：不 `rm`/`unlink`/`rmdir`；临时件留着即可。
- **不碰真机**：零 `boardwise bridge …`、零 daemon 启停、零编辑器操作、零 `.epro2/.eprj3` 真实工程写入。
  真实容器只可**只读**解析既有夹具/证据文件；不要新建导出。
- **跑测试的红线**：只说点名文件的聚焦测试；每条命令带 `--basetemp=.tmp_pt_hole565_sN`；
  **禁全量 pytest、禁 `-n auto`、禁 `-n >4`**（`-n 0` 或不带 `-n` 即可）；探针与脚本**单进程**，禁 multiprocessing/线程池扇出；
  前台命令给 timeout，挂死的命令杀掉并记一条。
- **不碰历史证据**：`outputs/011e*`、`014_*`、`015b_*`、`016_*`、`tests/fixtures/` 既有夹具一律只读引用，不改不搬。
- **保密**：报告与路径不出现公司/客户名与真实工程名，实名板只写 `PCB1/PCB2/PCB3`（R4b）。
- **不得把疑似写成洞**；不得把「测试通过」写成「这条路径没问题」——没有覆盖本身就可能是洞，但要写成 `suspect` + 缺哪条覆盖。

## ⑥ 预算与交卷格式

- 每缝**≤40 个模型步骤**或**≤30 分钟**，先到先停；范围漂移、连续失败无新信息即停止交卷。
- 交卷正文 **≤2000 字**，固定四段：`复核的环境读数` → `洞表（编号/严重度/一句话/状态）` → `证伪清单` → `没查的面 + 下一步最小动作`。
  细节全部落 `REPRO.md`，正文不复述日志。
- 找到 ≥1 条 `reproduced` 即算交卷；**零洞也要交**，写清查过哪些缝面、为什么是零（并给出「若要我继续该往哪查」）。
- 报告不得出现「大概」「可能」作为结论句；不确定的一律进 `suspect` 并写明缺什么证据。
