# 任务书：576 / W-C — 删除 empty-legacy 死路径

- 日期：2026-11-24
- 范围：仅 **566-C-01**。C-02 suspect 不处理。
- 执行：一个 coder；主代理独立复验。离线小批，不真机、不全量。

## ① 前因后果

`outputs/hole566/c/REPRO.md` 证明 `_flag_alternates` 注释承诺 “empty-legacy rescue”，但 append 过滤对 `old=[]` 恒假。进一步调用序核对给出更强事实：`old = walk(True)` 与 `walk(False)` 的第一次 `_flag_pin_lead` 调用使用完全相同的输入，因此 `old == []` 时 expanded 也必然为空，**不存在可真正接通的空 legacy 救援**。

正确处理是删除死路径与误导承诺：非 `native-attr` 页面无论 old 是否为空都直接返回 old；native-attr 的 expanded opposite-hang 逻辑保持原样。不能为了“实现救援”接受全部 expanded 候选，那会改变合法梯子的语义且仍然救不了空梯子。

569–575 已验收改动必须保留；本批不改候选几何、排序、阈值或页面基线。

## ② 当前树状态

- HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合未提交，零 git 写。
- `engines/drawcompiler.py` 当前 SHA `202ae3f56096f4fd62cd8203206d95979d17416b078f11fe32c8bd601347d29e`，为 HEAD 原样。
- `tests/test_p5_flag_alternates.py` 当前 SHA `d8d13a3eb57d31b83e2ff35f0660d7ddc569ea00a7eb3f01d1f82e1e5e8e08b9`，为 HEAD 原样。
- `_flag_alternates` 约 26670–26744 行；当前非 native 且 old 非空早退，old 为空会空跑第二次 walk。
- 563/568、569–575 其它文件与临时件禁触。

实施前 cp 备份两个文件到 `.tmp_576/backup/` 并记 SHA；禁用 git 恢复。

## ③ 文件域与禁触清单

允许新建/修改仅：

- `src/boardwise/engines/drawcompiler.py`（非 native 早退及对应注释）
- `tests/test_p5_flag_alternates.py`（新增调用序回归）
- 本任务书、`.tmp_576/`、`.tmp_pt_576/`、`evidence/576/`

禁止：其它布局/布线/旗标函数、CLI、contracts、connector、dsh-plugin、fixtures、563/568、569–575 其它文件、outputs 历史证据。

## ④ 交付物与验收

### 先红回归（生产改动前真实运行）

在 `tests/test_p5_flag_alternates.py` 新增：

1. **legacy 空梯子不空跑**：`_flag_pin_lead` 永远返回 `lead=None`、presentation 非 native-attr。断言结果 `[]` 且生产函数只调用 **1 次**。当前实现调用 2 次，测试先红。
2. **native 对照不变**：同样空输入但 `text_placement="native-attr"`，仍走 expanded 第二趟（2 次调用），证明只删除 legacy 死路径。
3. **既有几何不变**：当前 hybrid 的 legacy 顺序、same-run opposite-hang、joint pair 与 ch343 8 pages/0 failures 基线全部继续通过。

### 实施口径

- 非 native-attr 在 `old = walk(True)` 后直接 `return old`，不再以 old 是否为空区分；删除 “empty-legacy rescue” 承诺，注释明确 expanded 仅 native-attr 使用。
- native-attr 的 out/seen/expanded 过滤与 64-rung cap 原样保留，不改 `_flag_pin_lead`、`_corridor_pair_clash` 或其它函数。

### 修后测试与变异

```bash
.venv/Scripts/python.exe -m pytest tests/test_p5_flag_alternates.py -q --basetemp=.tmp_pt_576/new
.venv/Scripts/python.exe -m pytest tests/test_p5_flag_text_escape.py tests/test_053b_drawcompiler.py tests/test_548d_flag_corridor.py tests/test_548j_joint_seats.py -q --basetemp=.tmp_pt_576/neighborhood
```

至少两项变异，cp 备份→指定测试红→cp 恢复并核 SHA：

1. 非 native 早退恢复 `and old` → 空梯子空调用次数从 1 变 2，专项红；
2. native-attr expanded 分支置死/删除 → 既有 opposite-hang 或 ch343 基线红。

交回调用次数、native 对照、基线读数、测试汇总、两变异与最终 SHA。证据 `evidence/576/`。

## ⑤ 纪律与红线

- 零 git 写、零删除文件、零真机；不跑全量；探针单进程，前台带 timeout。
- pytest 独立 basetemp，禁 `-n auto`/`-n >4`；不改旧断言、skip/xfail。
- 不接受全部 expanded 候选、不改几何/排序/预算，不处理 C-02 suspect。
- 本批无新原理图，真机逐脚/视觉不适用、未做。

## ⑥ 预算与交卷格式

- 一个 coder，最多 **30 步或 20 分钟**，不派下一级代理。
- 正文 ≤1500 字：`实际改动` → `先红/修后绿` → `两变异与 SHA` → `未做/红项`。
- 有本批红项、缺调用序或 native 对照，只能交「停止/未完成」。

## ⑦ 交卷记录（执行者，2026-11-24）

- 改动两文件，见 `evidence/576/changes.patch`。`drawcompiler.py`：
  `26728` 早退去掉 `and old`（非 native 一律 `return old`），删 “empty-legacy rescue” 注释并写明
  expanded 仅 native-attr；native 分支与 64-rung cap 未动。`tests/test_p5_flag_alternates.py`：
  新增 1b 两条调用序回归（legacy 空梯 1 次 / native 对照 2 次且两趟首问入参全等）。
- 先红：`pytest tests/test_p5_flag_alternates.py -q -k empty_ladder` →
  `1 failed, 1 passed`（legacy 收到 2 次）。修后整文件 `7 passed in 12.84s`。
- ch343 基线：`pages=8, failures=[]`（`.tmp_576/check_ch343.py`）。
- 邻域四文件：`1 failed, 152 passed, 2 skipped`；唯一红
  `test_548j_joint_seats.py::test_a_forced_topology_round_seats_the_same_groups_once`
  在改前基线 `drawcompiler.py`（SHA `202ae3f5…`）上同样红，非本批回归。
- 变异：①早退恢复 `and old` → 专项红（`1 failed`）；②native expanded 分支置死 → `4 failed`
  （两条 opposite-hang + hybrid + native 对照）。两次 cp 恢复后 `cmp` 字节一致。
- 最终 SHA：`drawcompiler.py = 2b3c3f16d3f27bf18a6b8992e865d5277f7397d430ff6722ea700699672cb320`；
  `test_p5_flag_alternates.py = b04e63554ae3b28fe7a46d8013b2e638f653f8e72ccd8c55a4af9d0894d7fbfe`。
- 未做：C-02、全量、真机（本批无原理图交付）。
