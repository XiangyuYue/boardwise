# 任务书：607 — 引擎 API 声明页框即保护标题栏

## ① 前因后果

`outputs/hole570/b2/REPRO.md` 的 **570-B2-1** 复现：直接调用 `drawcompiler.compile(flyback, CompileBudget(page_box=(0,0,1170,825)))`，不给 keepouts，得到 `ok=True`，但 25/174 个呈现盒进入 `(460,10)-(1160,190)`；1170×600 为 36/174。CLI `_draw_compile` 已派生标题栏，所以缺口是公开引擎 API 的假绿入口。当前 76e0806 仍在 `_try_island_variants` 原样转发 `budget.keepouts`，并在 19900 行注释称由 caller 派生。

本批只修多岛 engine 的 S-01 同源，不改 B2-2 的 IslandBlock bbox（下一批），不改 CLI 合同、pagecompiler、单岛路径或标题栏尺寸。不能用“调用者应该自己传”关闭问题，也不能只给 warning 仍 ok。

## ② 当前树状态

- HEAD/origin `76e08060ded403793bc6fb0eb64b38f9e140c765`；前批改动的 flyback/power_entry 等保留。
- `src/boardwise/engines/drawcompiler.py` 开工 SHA-256 `2b3c3f16d3f27bf18a6b8992e865d5277f7397d430ff6722ea700699672cb320`。
- `_try_island_variants` 19851 起；PageBudget 在 19905–19908 原样接 keepouts，readability 在 20041–20047 也原样接，必须同源。CLI 11993–11996 已派生，会产生重复项风险，修复必须去重且保留显式自定义 keepouts。
- `core.pageframe.title_block_keepouts` 是现有唯一派生尺，禁止另写矩形。
- 原暴力 oracle `outputs/hole570/b2/probes/{01_page_oracle,02_no_keepout}.py` 可复用，输出放本批临时目录，不改原探针。他人 563/review-line/临时文件禁触。开始 cp 备份 drawcompiler 到 `.tmp_607/backup/`。

## ③ 文件域与禁触清单

允许修改/新建仅：
- `src/boardwise/engines/drawcompiler.py`（多岛 keepout 派生、同源传递与相关旧注释）
- `tests/test_607_island_engine_keepouts.py`（新）
- 本任务书、`.tmp_607/`、`.tmp_pt_607/`、`evidence/607/`

禁止：CLI/pageframe/pagecompiler/islandlayout/readability、placement/router、shared/connector/DSH、fixtures、旧证据和他人文件。不得改页框、GAP、预算、候选排名来躲开标题栏，不修改既有断言凑绿，不新增第二套 packer。

## ④ 交付物与验收

### 实现合同

1. 多岛且 `budget.page_box is not None` 时，引擎内部从同一个 `page_box` 调 `title_block_keepouts`，与调用者显式 keepouts 合并去重；显式 keepouts 不得被覆盖或丢弃。无 page_box 不多造 S-01，单岛隐式/显式路径不变。
2. PageBudget、packer floor/冲突、readability、失败说明中的 keepout 数量都消费同一份有效集合；CLI 已传入同一标题栏时不得重复。修正“只能由 caller 派生/第二次派生必然分歧”的旧注释。
3. 用真实 flyback 原输入走公开 `compile`，不能只测 helper；必须得到合法候选且独立暴力 oracle 对全部呈现对象（器件体、pin tip、线段、文字/label、旗 glyph+名称、junction）核查页内与标题栏正面积相交均为 0。不得只信 `keepout_conflicts` 或 `ok=True`。
4. 1170×825 是主回归；1170×600 若原报告复现，也重算并记录实际候选/拒因，不为了拿候选放页框。保留一个显式额外 keepout 与 title 的合并去重测试；无 page_box 控制保持原行为。

### 先红与修后

新增真实 compile 测试先跑未改生产，1170×825 应复现至少 1 个 title 相交（原报告 25），CLI 对照为 0；修后同一 oracle 为 0。至少运行新测试、`tests/test_569_title_block.py`、`tests/test_530g_title_block_keepout.py`、`tests/test_533_island_guard.py`、`tests/test_520m_island_packing.py`（先 Glob 核名）、owner/layer 和 flyback 相关邻域；不全量。

至少两项变异：① 禁止引擎派生，真实 oracle 红；② 用原始 `budget.keepouts` 而非有效集合喂 readability/PageBudget，合并/同源断言红。每项 cp+SHA 恢复并复绿。另记录 CLI 输入是否重复、显式 keepout 是否保留。

兼容矩阵：多岛 engine API + 既有 CLI 为两个消费者；单岛/page 文档/无 page_box 为负控。真机、V3/V4、多板/CBB 未覆盖；本批是离线编译闸，不声称逐脚或视觉通过。

## ⑤ 纪律与红线

零 git 写/移动/删除；禁 rm/unlink 和 git checkout/restore；不全量、不真机、不部署。pytest 独立 basetemp，命令 timeout、探针单进程。不得通过扩大页框、减少对象或修改规格使相交消失；不删改旧断言，不将缺候选伪写为通过。历史输出与他人未提交 hunk不动。

## ⑥ 预算与交卷格式

一个 coder，最多 40 步或 30 分钟；不派下级。交卷 ≤2000字，含先红相交数、修后逐类 oracle 计数、测试完整汇总、两项变异及 SHA 恢复、CLI/显式 keepout 兼容和未覆盖项。证据落 `evidence/607/`。缺真实 oracle 或变异只能写「停止/未完成」。

## 交卷记录（2026-11-25）

- 生产改动：`src/boardwise/engines/drawcompiler.py` 新增 `_island_keepouts`（显式 keepouts ∪ `pageframe.title_block_keepouts(page_box)`，1e-9 去重），`PageBudget` / 页框拒绝说明 / `readability.check` 三处共用一个元组；开工 SHA `2b3c3f16…2320` → 交卷 SHA `9ded2eb3…caf9`。
- 先红：真实 flyback `compile(flyback, CompileBudget(page_box=(0,0,1170,825)))` 修前候选 1、174 盒中 25 进 title（1170×600 为 36）；CLI 同口径 0。新测试对未改生产 2 failed / 3 passed。
- 修后：同一暴力 oracle（8 类对象）825/600 均 0 相交、0 出页、各 1 候选；`effective.json` 证 Packer 与 gate 同集合、CLI 的 title 去重为 1 条、显式额外 keepout 保留。
- 测试：新测试 5 passed；4 个命名文件 68 passed；终版合跑 73 passed；邻域 17 文件 275 passed, 1 skipped。
- 变异：①禁引擎派生 ②两消费者用原始 `budget.keepouts`，各 2 failed / 3 passed，均 cp+SHA 还原复绿。
- 证据：`evidence/607/`（pre_fix / post_fix / pre_fix_cli_equivalent / effective / mutation1 / mutation2 / neighborhood / final_green / drawcompiler.diff / report.md）。
- 未覆盖：570-B2-2（608）、page 文档路径、draw plan/apply、真机与视觉、V3/V4、多板/CBB。
