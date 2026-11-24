# 任务书：574 / W-E1 — 逐图元 census 摘要与旧摘要识别

- 日期：2026-11-24
- 范围：仅 **567-E-1**。E-3/E-2 已由 572/573 验收。
- 执行：一个 coder；主代理独立复验。离线小批，不真机、不全量。

## ① 前因后果

`outputs/hole567/e/REPRO.md` E-1 证明：`canvas_census` / `census_digest` 只有设计器和六个计数，挪件 30u、改线走向、挪旗 20u、改值四类真改动 digest 完全相同，`expect_census` 仍零 problem。必须让摘要覆盖逐图元身份、位姿、值、点列，并覆盖 570 新增的 pins 与六类 drawing section。

570 的 `PlanDrawBaseline` 公开字段不得改变；`census_items` / `census_changes` 的 057 范围比较和 573 的 host_merges 不得改写。可在 `census_digest(census, geometry=None)` 增加可选 geometry：无 geometry 保留旧计数摘要用于识别旧计划，有 geometry 生成新逐图元摘要。`canvas_census` 必须走新算法。

旧计数型摘要无法证明页面未变。它应与真正变化区分，明确提示“旧 counts-only 摘要，重新生成/取新摘要”，但仍须拒绝，不得为兼容而放行。

## ② 当前树状态

- HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合未提交，零 git 写。
- `engines/drawapply.py` 含 570/572/573，当前 SHA `f8a8376f32f87c522fb807958d7ca476c2e82f29bffe08c108e8f2edf5572675`。
- `core/changeplan.py` 只有 570 的注释变化，公开 PlanDrawBaseline 字段不得再改。
- `canvas_census` 约 4614 行，`census_digest` 约 4729 行，`guard_problems` 约 4791 行；`GEOMETRY_SECTIONS` 与 `DRAWING_SECTIONS` 已在仓。
- 563/568、569–573 其它文件、PROGRESS/handoff/roadmap/TASKMAP/review-line 与临时件禁触。

实施前 cp 备份生产文件到 `.tmp_574/backup/` 并记 SHA；禁用 git 恢复。

## ③ 文件域与禁触清单

允许新建/修改仅：

- `src/boardwise/engines/drawapply.py`（几何指纹、digest 与旧摘要拒因）
- `src/boardwise/core/changeplan.py`（仅 digest 说明，不改字段/序列化）
- `docs/draw.md`（C5 digest 与旧摘要口径）
- `tests/test_574_census_digest.py`（新聚焦回归）
- `tests/test_054_drawapply.py`（仅让 digest 自证断言传入同一 geometry，不放宽）
- 本任务书、`.tmp_574/`、`.tmp_pt_574/`、`evidence/574/`

禁止：`cli.py`、`census_items` / `census_changes` / `host_merges` 的行为、connector、contracts、fixtures、563/568、569–573 其它文件、outputs 历史证据。

## ④ 交付物与验收

### 先红回归（生产改动前真实运行）

新建 `tests/test_574_census_digest.py`：

1. **四个原始变体**：同一 base 上分别挪件、改线点、挪旗、改 OtherProperty.Value；每个 `canvas_census(...).digest != base.digest` 且 `guard_problems(expect_census=base.digest)` 非空。同 dump 仍零 problem，额外插线的正控制也非空。
2. **覆盖面**：pins 新增、Text 新增、Rectangle 几何/文字变化、NetLabel 位置/文本变化都必须改 digest；section/entry 顺序与 dict key 顺序变化不得改 digest。sheet frame 不当作普通 content row，避免把空页身份误算成器件。
3. **确定性/序列化**：指纹只含可 JSON 化的稳定数据，按 section+id  canonical 排序；不得把对象内存地址、meta.available、bboxes 重复派生值写进摘要。PlanDrawBaseline 的字段与 JSON round-trip 不变。
4. **旧摘要识别**：`census_digest(census)`（无 geometry）保留旧计数算法；`census_digest(census, geometry)` 是新的。旧 counts-only expectation 在新算法下必须拒绝并明确提示重新生成/取新摘要，不得写成确定的“用户改图”，也不得 exit 0。
5. **054 自证**：`census.digest == census_digest(census, page)`，而不是拿无 geometry 的旧算法自证。

### 实施口径

- 新增独立几何指纹 helper，遍历 `GEOMETRY_SECTIONS + DRAWING_SECTIONS`；跳过 sheet，保留每项 section、primitiveId 与稳定 state（位号/值/网/位置/姿态/点列等），canonical JSON 序列化。不得复用/改变 `census_items` 的比较合同。
- `canvas_census` 调 `census_digest(census, geometry)`；无 geometry 的旧算法只用于识别旧摘要。
- `guard_problems` 对旧 counts-only digest 给专门拒因；真正的新 digest 不匹配仍走原“页面变化”拒因。不要靠猜版本号或静默接受旧摘要。
- 更新 docstring/docs：新摘要覆盖逐图元，旧计划需重生成；057 `census_changes` 与 573 合法 host merge 不变。

### 修后测试与变异

```bash
.venv/Scripts/python.exe -m pytest tests/test_574_census_digest.py -q --basetemp=.tmp_pt_574/new
.venv/Scripts/python.exe -m pytest tests/test_054_drawapply.py tests/test_054_draw_cli.py tests/test_057_draw_page_cli.py tests/test_143d_page_and_census.py tests/test_573_collinear_merge.py tests/test_572_quantization.py tests/test_570_empty_page.py tests/test_doc_claims.py -q --basetemp=.tmp_pt_574/neighborhood
```

至少三项变异，cp 备份→指定测试红→cp 恢复并核 SHA：

1. 新 payload 去掉逐图元指纹 → 四个原始变体重新同 digest、测试红；
2. 指纹漏掉 drawing sections 或 pins → 对应覆盖用例红；
3. 去掉旧 counts-only 识别 → 旧摘要拒因退化成普通变化/缺失，专项红。

交回四类变体 digest/guard 读数、覆盖与确定性、旧摘要拒因、测试汇总、三变异与最终 SHA。证据 `evidence/574/`。

## ⑤ 纪律与红线

- 零 git 写、零删除、零真机；不跑全量；探针单进程，前台带 timeout。
- pytest 独立 basetemp，禁 `-n auto`/`-n >4`；不改旧断言、skip/xfail。
- 不改变 PlanDrawBaseline 字段，不把旧摘要静默放行，不改 573 的范围豁免。
- 本批无新原理图，真机逐脚/视觉不适用、未做。

## ⑥ 预算与交卷格式

- 一个 coder，最多 **35 步或 25 分钟**，不派下一级代理。
- 正文 ≤1800 字：`实际改动` → `先红/修后绿` → `三变异与 SHA` → `未做/红项`。
- 有本批红项、缺四类原始变体或缺旧摘要证据，只能交「停止/未完成」。
