# 任务书：579 — textmetrics 保留内置 sum 的浮点舍入

- 日期：2026-11-24
- 范围：575 引入的三条新增几何回归（530e/530g/530d），不扩新功能。
- 执行：一个 coder；主代理独立复验。离线小批，不真机、不全量。

## ① 前因后果

全量发现 12 failed，其中 9 条与 564 既有失败逐名一致，真正新增是：

- `test_530e_islands_propose_apply.py::test_the_declared_island_page_compiles_to_the_same_geometry_as_before`
- `test_530g_title_block_keepout.py::test_a_page_with_no_sheet_packs_exactly_where_it_did_before`
- `test_530d_component_names.py::test_the_real_page_names_every_blob_exactly_once`

隔离证据：临时恢复 HEAD `textmetrics.py` 后三条全过，恢复 575 文件后仍失败。逐 JSON diff 只有 VFB_NF 的 bbox 从 `(22.593256544502623, 50.0)` 变为 `(22.59325654450261, 49.999999999999986)`，是 **1 ulp 浮点舍入差**，不是全角加宽或标题栏几何变化。

575 把原来的 `em = sum(TEXT_ADVANCE_EM.get(ch, fallback) for ch in text)` 改成手动 `em=0; for: em += advance`。内置 `sum()` 的浮点累加/舍入语义与手动循环不同，导致共享反激几何指纹改变。正确修法是恢复内置 `sum()` 的生成器表达式，只在生成器内按 ASCII/非 ASCII 选择 fallback，保持原累加顺序。

## ② 当前树状态

- HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合未提交，零 git 写。
- `core/textmetrics.py` 当前 SHA `a2aa0fb92de1e7d0d7862e53be338edaf1d1de38ed1f2974f778769e3790b6ca`。
- 575 的全角 1.1 em、ASCII 分流和 `TEXT_ADVANCE_EM_FALLBACK_ASCII=0.9` 必须保留。
- `tests/test_575_text_metrics.py` 已有 25 条，新增失败的三条 530 测试可作为端到端验收。
- 其它 569–578 文件与既有基线红项不碰。

实施前 cp 备份 `core/textmetrics.py` 到 `.tmp_579/backup/` 并记 SHA；禁用 git 恢复。

## ③ 文件域与禁触清单

允许新建/修改仅：

- `src/boardwise/core/textmetrics.py`（恢复内置 sum 与注释）
- `tests/test_575_text_metrics.py`（新增精确浮点回归）
- 本任务书、`.tmp_579/`、`.tmp_pt_579/`、`evidence/579/`

禁止：其它生产文件、其它测试、563/568、569–578 其它批次、fixtures、contracts、connector、dsh-plugin、真实工程。

## ④ 交付物与验收

### 先红回归（生产改动前真实运行）

在 `tests/test_575_text_metrics.py` 新增：

1. **内置 sum 的精确舍入**：用测试自己写的内置 `sum(...)` 计算 VFB_NF 的 em，断言 `render_width("VFB_NF") == expected_em * RENDER_TEXT_PX`（精确相等，不是 approx）。当前手动累加实现必须先红。
2. **保留 575 行为**：全角仍 ≥1.0 em、非 ASCII fallback 仍 1.1、表外 ASCII 标点仍 0.9，不能把修复变成回退全角合同。
3. **反激共享基线**：上述三条 530e/530g/530d 全绿，验证几何指纹恢复而不改测试 hash。

### 实施口径

- 用内置 `sum(<generator>)` 代替手动 `em=0; for +=`；生成器内按 `ord(ch)>0x7F` 选择 `TEXT_ADVANCE_EM_FALLBACK` 或 `TEXT_ADVANCE_EM_FALLBACK_ASCII`，表内 advance 不变。
- 注释明确保留内置 sum 是为了不改变既有浮点舍入和几何指纹；不得引入新的累加器、四舍五入或 Kahan 算法。

### 修后测试与变异

```bash
.venv/Scripts/python.exe -m pytest tests/test_575_text_metrics.py -q --basetemp=.tmp_pt_579/new
.venv/Scripts/python.exe -m pytest tests/test_530e_islands_propose_apply.py::test_the_declared_island_page_compiles_to_the_same_geometry_as_before tests/test_530g_title_block_keepout.py::test_a_page_with_no_sheet_packs_exactly_where_it_did_before tests/test_530d_component_names.py::test_the_real_page_names_every_blob_exactly_once -q --basetemp=.tmp_pt_579/flyback
```

至少一项因果变异：把内置 sum 再改回手动累加，精确 VFB_NF 与三条 530 测试必须红；cp 恢复并核 SHA。另跑一次 575 全文件确认没有回退全角合同。

交回精确 em/bbox 差、三条 530 汇总、575 全文件汇总、变异与最终 SHA。证据 `evidence/579/`。

## ⑤ 纪律与红线

- 零 git 写、零删除、零真机；不跑全量；探针单进程，前台带 timeout。
- pytest 独立 basetemp，禁 `-n auto`/`-n >4`；不改三条 530 的既有 hash，不用 skip/xfail 掩红。
- 不回退 575 的全角/ASCII 分流，不碰其它基线失败。
- 本批无新原理图，真机逐脚/视觉不适用、未做。

## ⑥ 预算与交卷格式

- 一个 coder，最多 **15 步或 10 分钟**，不派下一级代理。
- 正文 ≤1200 字：`根因` → `先红/修后绿` → `变异与 SHA` → `未做项`。
- 有本批红项或缺精确浮点证据，只能交「停止/未完成」。
