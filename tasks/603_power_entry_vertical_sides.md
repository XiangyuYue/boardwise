# 任务书：603 — power_entry 的 top/bottom 声明

## ① 前因后果

`outputs/hole570/c2/REPRO.md` 的 **570-C2-N2** 实测 `PowerEntryGrammar.bind` 只把 `sidePreferences.input=="right"` 映射为 `right-of`，其余合法值都折成 `left-of`，因此 `top/bottom` 没有几何作用，理由串却仍引用声明。当前 76e0806 的 `power_entry.py` SHA-256 与挖洞时一致，342 行仍是二值映射。

报告对方向的预期有一处自相矛盾：表格一处写 `input=top` 应 `below`，但 §3 的正式 FIX 与 flyback 当前 `_side_kind` 都写 `top→ABOVE`、`bottom→BELOW`。本批采用后者：`RelativeConstraint` 的 subject 是 entry，入口声明在上方就意味着 entry 在 shunt 上方。不能用相反的断言把另一处方向修反。只修被忽略的纵向声明，不改横向行为、不重构七本 grammar。

## ② 当前树状态

- HEAD/origin `76e08060ded403793bc6fb0eb64b38f9e140c765`；602 flyback 是前批，必须保留其改动。
- `src/boardwise/engines/grammar/power_entry.py` 开工 SHA-256 `22d467ff3274d9b1d3356dae585cf4e2c873db0246ba9862d456f4d8a88e6dad`。
- 同文件 339–342 行读取并校验 `SIDES`，随后 `side_kind = RIGHT_OF if in_side == "right" else LEFT_OF`；438–444 行把该 kind 与 `sidePreferences.input=<原值>` 写入约束。
- flyback 的同义表为 `left→LEFT_OF/right→RIGHT_OF/top→ABOVE/bottom→BELOW`；本批局部复用相同四值语义，不把 helper 提到 base（那是跨多文件的另一批）。
- 工作树中 `core/circuitsemantics.py`、`tasks/review-line.md`、563 文档/测试及临时文件是他人内容，不得触碰。开始先 `cp` 备份本文件到 `.tmp_603/backup/` 并记 hash。

## ③ 文件域与禁触清单

允许修改/新建仅：
- `src/boardwise/engines/grammar/power_entry.py`（纵向 side 映射及必要的附近注释）
- `tests/test_603_power_entry_vertical_sides.py`（新）
- 本任务书、`.tmp_603/`、`.tmp_pt_603/`、`evidence/603/`

禁止：flyback/base/ldo/其它 grammar、编译器、shared parser/model、CLI、connector/DSH、fixtures、历史证据及他人文件。不得修改 602 的测试或生产 hunk，不改默认 side、约束数量、理由文本的其它部分或候选布局阈值。既有测试不得删改宽、skip/xfail。

## ④ 交付物与验收

### 先红与行为合同

新增测试并先对未改生产运行，top/bottom 两条必须红，left/right 控制必须绿：

1. 复用 `outputs/hole570/c2/probes/probe_c2.py` 的 power_entry 最小输入构造（不执行其全部探针、不改原文件），有至少一个 shunt，使入口→shunt 约束可观察。
2. `sidePreferences.input="top"` 时，entry subject、shunt object 的约束 `kind==ABOVE`；`"bottom"` 时 `kind==BELOW`。reason 必须分别含 `sidePreferences.input=top/bottom`，不得再与 `left-of` 同现。
3. `left/right` 仍分别 `LEFT_OF/RIGHT_OF`，默认未声明仍为 LEFT_OF，非法 side 的既有回退不变。
4. 绑定角色、入口证据、约束总数与 shunt 顺序除 kind 外不变；测试不能只检查“四个值产生不同结果”，要钉住正确方向。

### 实现与测试

仅在现有映射处使用四值表，保持非法值已经归一为 left 的行为；不新增 constraint kind、不改 flyback。

```bash
.venv/Scripts/python.exe -m pytest tests/test_603_power_entry_vertical_sides.py -q --basetemp=.tmp_pt_603/new
.venv/Scripts/python.exe -m pytest tests/test_603_power_entry_vertical_sides.py tests/test_088_power_entry.py tests/test_088b_power_entry_order.py tests/test_113_flyback_grammar.py tests/test_143b_grammar_contracts.py tests/test_602_flyback_ground_pairs.py -q --basetemp=.tmp_pt_603/neighborhood
```

如 088 文件名与实际不符，先用 Glob 定位真实 power_entry 测试并在报告说明替换，不得省略邻域。

两项因果变异：① top/bottom 再折回 LEFT_OF；② 把 top/bottom 方向对调。各自先备份修后文件、跑新测试必须对应红，`cp` 恢复并 SHA-256 与修后一致，再复绿。禁 git 恢复。

兼容矩阵：仅 power_entry 的 PresentationSpec 声明和 binding；布局结果只跑既有邻域，不声称真机/视觉通过。left/right/default/非法值是 negative control；V3/V4、容器、多板/CBB 未覆盖，无新原理图交付。

## ⑤ 纪律与红线

零 git 写/移动/删除；不跑全量、不接触 bridge/daemon/EDA；不部署/发布。pytest 独立 basetemp，探针单进程、命令带 timeout，禁 `-n auto` 和 `-n >4`。不调整布局/页框/budget 凑绿，不另建 builder 或共享 helper 子系统，不修改 fixtures 和他人未提交内容。发现原报告方向冲突不得两边同时满足，按本任务书的 subject/object 语义留证。

## ⑥ 预算与交卷格式

一个 coder，最多 40 步或 30 分钟；不再派代理。交卷 ≤2000 字，含改动、先红→修后绿的命令与完整汇总、两项变异与 SHA 恢复、四向读数、兼容矩阵和未覆盖项。详细证据落 `evidence/603/`。缺先红、变异或有本批未解决红项，只能写「停止/未完成」。

## 交卷记录（coder，2026-11-25）

- HEAD `76e0806`；本批零 git 写、零删除、未跑全量、未接触 bridge/EDA。开工备份与三段 SHA 见
  `evidence/603/README.md`。
- 生产改动：`src/boardwise/engines/grammar/power_entry.py` —— 入库 `ABOVE`/`BELOW`，339–352 行
  把二值映射换成 flyback/ldo 同义四值表（`left/right/top/bottom`，越界回退 `LEFT_OF`），
  并同步 110–119 行 docstring 里只讲 `left-of`/`right-of` 的那一条。未动约束数量、理由文本结构、
  默认 side、非法值归一、flyback/base/ldo。
- 新测试 `tests/test_603_power_entry_vertical_sides.py`（10 条）：四个合法值钉住正确 kind，
  `top→above`/`bottom→below` 单独一条防对调，未声明默认、非法回退、绑定角色/shunt 顺序/
  约束条数在四向下不变。
- 先红：`pytest tests/test_603_power_entry_vertical_sides.py -q` → **4 failed, 6 passed**
  （top/bottom 全红，left/right/default/非法全绿；读数 `evidence/603/red_before_fix.txt`）。
- 修后绿：同上 → **10 passed**。
- 邻域（任务书列表中的 `test_088b_power_entry_order.py` 不存在，实际为
  `tests/test_088b_followups.py`，按 §④ 替换）：
  `pytest tests/test_603_power_entry_vertical_sides.py tests/test_088_power_entry.py
  tests/test_088b_followups.py tests/test_113_flyback_grammar.py
  tests/test_143b_grammar_contracts.py tests/test_602_flyback_ground_pairs.py -q` →
  **149 passed, 1 skipped**（修复后、docstring 前 26.63s；最终文件 38.22s）。
- 两项变异（均对最终文件重跑）：① 折回 `RIGHT_OF if right else LEFT_OF` → 4 failed/6 passed；
  ② `top/bottom` 对调 → 4 failed/6 passed；各自 `cp` 恢复后 SHA-256 回到
  `2f19f2ca…11492`、`cmp` BYTE_IDENTICAL、复绿 10 passed。
- 四向读数（真实语法）：`left→left-of`、`right→right-of`、`top→above`、`bottom→below`，
  未声明与非法值 `left-of`；四处 bindings 均为 `CN1,VIN,GND,C1`、约束 3 条。
- 未覆盖：落图/布局层对纵向 `above`/`below` 的消费、页框/容器/多板/CBB、真机与视觉、
  全量 pytest。方向语义按任务书裁定（subject 是 entry，`top` 即 entry 在上），与 570-C2
  报告表格中写反的一处相反，未两边同时满足。
