# 任务书：572 / W-E3 — 0.01 回读的半厘边界

- 日期：2026-11-24
- 范围：仅 **567-E-3**。合线与 census 分别由后续 573/574 处理。
- 执行：一个 coder；主代理独立复验。离线小批，不真机、不全量。

## ① 前因后果

`outputs/hole567/e/REPRO.md` E-3 证明：页面按 0.01 回读，容差恰为半步 0.005；第三位小数为 5 时，二进制差可能为 `0.0050000000000008 > 0.005`，导致 `_near` / `_near_polyline` 把自己刚落的点判成未落。[-20,20] 全部 4001 个半厘值中 348 个失败，合法计划因此 `all_satisfied=False`，重复 apply 无法进入 `already_applied`。

不得把容差简单放宽到 0.006 以上，那会把不同格点误认为同一点。正确口径是：默认页面精度下比较同一个 0.01 格点身份；折线也先量化计划和页面点，再走原 `_on_polyline`，非默认容差保持原逻辑。

569–571 已验收改动必须保留。本批不动合线或 census。

## ② 当前树状态

- HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合未提交，零 git 写。
- `engines/drawapply.py` 含 570 空页辅助，当前 SHA `39661f3e2366f15765f9c44ca895a5ef292f15dbc2da3666a517fad7a187045b`。
- `_near` 在约 4881 行，默认页面精度常量在约 5872 行，`_near_polyline` 在约 5885 行；`_on_polyline` 是既有精确判定，可复用，不另写第二套几何。
- 他人的 563/568、569–571 其它 hunk、PROGRESS/handoff/roadmap/TASKMAP/review-line 与临时件禁触。

实施前 cp 备份 `engines/drawapply.py` 到 `.tmp_572/backup/` 并记 SHA；禁用 git 恢复。

## ③ 文件域与禁触清单

允许新建/修改仅：

- `src/boardwise/engines/drawapply.py`（页面精度比较及对应注释）
- `tests/test_572_quantization.py`（新聚焦回归）
- 本任务书、`.tmp_572/`、`.tmp_pt_572/`、`evidence/572/`

禁止：`cli.py`、`core/candidate.py`、census/合线相关代码、569–571 其它文件、563/568、fixtures、contracts、connector、dsh-plugin、outputs 历史证据。

## ④ 交付物与验收

### 先红回归（生产改动前真实运行）

新建 `tests/test_572_quantization.py`：

1. **穷举**：[-20,20] 内全部 4001 个 `n/100 + 0.005`，逐个断言 `_near((v,0),(round(v,2),0),0.005)` 与 `_near_polyline` 都为真；至少保留一个不同格点负控制（如 0 vs 0.01）不得为真。
2. **真实计划完成判定**：用 054 的 divider fixture/helper 生成 ChangePlan，使合法端点落在会触发原浮点误差的半厘位置，页面回读按 `round(v,2)`，断言 `postcondition_problems.canvas == []` 且 `all_satisfied=True`，从而重复 apply 的 already-applied 前置成立。
3. **非默认容差不变**：1e-6、HALF_GRID 等其它调用不经过页面 0.01 特化；量化后跨格点不得被新容差吞并。

### 实施口径

- 默认 `tol == PAGE_POINT_PRECISION/2` 时，`_near` 比较 `round(x,2)` / `round(y,2)` 的格点身份。
- `_near_polyline` 同精度下先量化 point 与 polyline 的每个点，再复用原 `_on_polyline`；其它 tolerance 走原实距算法。不得复制一份新的折线实现。
- 更新注释说明为什么格点身份比 `<=0.005` 正确，不改 PAGE_POINT_PRECISION、不改非默认容差。

### 修后测试与变异

```bash
.venv/Scripts/python.exe -m pytest tests/test_572_quantization.py -q --basetemp=.tmp_pt_572/new
.venv/Scripts/python.exe -m pytest tests/test_054_drawapply.py tests/test_057_draw_page_cli.py tests/test_145d_plan_vertices.py tests/test_163b_gate_truth.py -q --basetemp=.tmp_pt_572/neighborhood
```

至少两项变异，cp 备份→指定测试红→cp 恢复并核 SHA：

1. `_near` 退回浮点 `abs(...) <= tol` → 穷举红；
2. `_near_polyline` 去掉页面量化路径 → 穷举或合法计划完成判定红。

交回穷举计数、失败示例修复前后、完成判定、测试汇总、变异与最终 SHA。证据 `evidence/572/`。

## ⑤ 纪律与红线

- 零 git 写、零删除、零真机；不跑全量；探针单进程，前台带 timeout。
- pytest 独立 basetemp，禁 `-n auto`/`-n >4`；不改旧断言、skip/xfail。
- 不扩大容差遮洞，不改合线/census，不新增几何引擎。
- 本批无新原理图，逐脚/视觉不适用、未做。

## ⑥ 预算与交卷格式

- 一个 coder，最多 **30 步或 20 分钟**，不派下一级代理。
- 正文 ≤1500 字：`实际改动` → `先红/修后绿命令与汇总` → `两变异与 SHA` → `未做/红项`。
- 有本批红项或缺穷举/变异证据，只能交「停止/未完成」。
