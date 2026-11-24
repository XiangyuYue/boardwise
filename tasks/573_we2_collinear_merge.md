# 任务书：573 / W-E2 — 同网共线合线与范围闸

- 日期：2026-11-24
- 范围：仅 **567-E-2**。E-3 已由 572 验收；E-1 由后续 574 处理。
- 执行：一个 coder；主代理独立复验。离线小批，不真机、不全量。

## ① 前因后果

`outputs/hole567/e/REPRO.md` E-2 给出两种合法形态：

1. 两条同网共线计划线被宿主合并且接头不再是顶点，无名计划线的 `_page_segment_holds_end` 要求合并段两端都落在单条计划折线上，产生 3 个 problem。
2. 计划线并入既有同网铜皮，postcondition 又误判接头；`census_changes` 同时把“宿主把我方线并入既有线”记为既有图元被改，范围闸 exit 2 不保存。

572 已把默认页面精度改为 0.01 格点身份，必须保留。修法不能退回全页几何匹配，也不能把任何既有线变化都豁免：只允许**可证明的同网、共线、原线被完整包含且确有计划线并入**的宿主合并，并在范围报告逐项披露 ID。

## ② 当前树状态

- HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合未提交，零 git 写。
- `engines/drawapply.py` 含 570/572，当前 SHA `5538dcf8656835b9346fd3de6f97ac073e46f03de0c5b1cd18c021670e1c84e6`。
- `cli.py` 含 569–571，当前 SHA `f1f44e48098868281fbb881fc675c55cd7981815fed921fdea9354bec1227100`。
- `_page_segment_holds_end` 约 5919 行；`_wire_problems` 约 5959 行；CLI `items_before/census_changes` 约 15054 行。
- 057 既有 `test_e2_a_landing_that_changes_an_existing_wire_is_not_saved` 的非共线负例必须继续拒绝，不得为让新正例通过而放宽它。
- 563/568、569–572 其它文件与临时件禁触。

实施前 cp 备份两个生产文件到 `.tmp_573/backup/` 并记 SHA；禁用 git 恢复。

## ③ 文件域与禁触清单

允许新建/修改仅：

- `src/boardwise/engines/drawapply.py`（合线 postcondition 与窄豁免 helper）
- `src/boardwise/cli.py`（范围闸消费 helper 并披露）
- `docs/draw.md`（仅既有图元零改动与合法宿主合并的口径）
- `tests/test_573_collinear_merge.py`（新聚焦回归）
- 本任务书、`.tmp_573/`、`.tmp_pt_573/`、`evidence/573/`

禁止：census_digest/canvas_census 算法（574）、pagecompiler/drawcompiler/candidate、569–572 其它文件、563/568、fixtures、contracts、connector、dsh-plugin、outputs 历史证据。

## ④ 交付物与验收

### 先红回归（生产改动前真实运行）

新建 `tests/test_573_collinear_merge.py`，复用 054/057 的真实 plan 与 fake editor，不依赖 outputs 才能运行：

1. **计划线自相接**：追加一条同网共线计划线，宿主合成一个两点 primitive、接头消失。断言 `postcondition_problems.canvas == []`、`all_satisfied=True`。把合并段改成异网必须仍有 problem，证明没有退回全页几何。
2. **既有铜皮合并的底层判据**：before 为两点同网直线，after 完整包含 before 且共线延伸，计划线的两端落在 after 上且至少一端超出 before。helper 只豁免该既有 id；改异网、折线改道、before 不再被完整包含、或无计划延伸时均不得豁免。
3. **完整 draw apply**：用 054 divider plan + fake host，既有 `w-0` 与计划 VIN 线同网共线相接，place 时真实合并成一条并丢接头。断言 exit 0、已保存、范围 `changed == []`、`hostMerges` 明确含 `w-0`；非共线/异网对照仍 exit 2 `range_out_of_scope` 且不保存。057 原非共线负例作为邻域必跑。

### 实施口径

- `_page_segment_holds_end`：对**非空且相同网名**的页面段，允许它经过计划端点，即使合并段延伸到单条计划折线之外；异网仍必须走原严格几何证明。不要把所有空 Net 段当成可随意匹配。
- 新增一个用途单一的 helper 计算 `ignore_ids`：逐条比对 before/after 同 id 的 wire，要求网名稳定一致、合并后所有点共线、before 被完整包含、计划线确实并入并延伸；任何一项不满足就不豁免。不得把 `census_changes` 本体改成忽略所有共线差异。
- CLI 将 helper 结果传给 `census_changes(ignore_ids=...)`，并在 `range.outOfScope.hostMerges` 记录 id 与判据；没有改变 `changed` 的既有语义。
- 更新 docs/draw.md：合法宿主合并不等于“既有图元被用户改坏”，但必须可证明并披露；其它变化仍 exit 2。

### 修后测试与变异

```bash
.venv/Scripts/python.exe -m pytest tests/test_573_collinear_merge.py -q --basetemp=.tmp_pt_573/new
.venv/Scripts/python.exe -m pytest tests/test_054_drawapply.py tests/test_057_draw_page_cli.py tests/test_145d_plan_vertices.py tests/test_163b_gate_truth.py tests/test_572_quantization.py -q --basetemp=.tmp_pt_573/neighborhood
```

至少三项变异，cp 备份→指定测试红→cp 恢复并核 SHA：

1. 删除 `_page_segment_holds_end` 的同网合线分支 → 计划线自相接红；
2. 范围 helper 返回空集或放宽成全部豁免 → 完整 apply 正例红或负例变绿（后者同样判失败）；
3. CLI 不传 `ignore_ids` → 完整 apply 正例 `range_out_of_scope` 红。

交回底层 problem 数、完整 apply exit/保存/hostMerges、负例读数、测试汇总、三变异与最终 SHA。证据 `evidence/573/`。

## ⑤ 纪律与红线

- 零 git 写、零删除、零真机；不跑全量；探针单进程，前台带 timeout。
- pytest 独立 basetemp，禁 `-n auto`/`-n >4`；不改旧断言、skip/xfail。
- 不放宽到全页几何、不隐瞒范围差异、不改 572 的量化实现。
- 本批无新原理图，真机逐脚/视觉不适用、未做。

## ⑥ 预算与交卷格式

- 一个 coder，最多 **35 步或 25 分钟**，不派下一级代理。
- 正文 ≤1800 字：`实际改动` → `先红/修后绿` → `三变异与 SHA` → `未做/红项`。
- 有本批红项、缺完整 apply 或缺负控制，只能交「停止/未完成」。
