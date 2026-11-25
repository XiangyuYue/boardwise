# 任务书：602 — flyback 全部地网对的短路闸

## ① 前因后果

用户指定继续修 `outputs/hole570/TRIAGE.md` 的 reproduced 项。最高优先级 **570-C2-N1** 已在 `outputs/hole570/c2/REPRO.md` 复现：`src/boardwise/engines/grammar/flyback.py::_short_failure` 只取 `sorted(state.ground)[:2]`，在 `minimal_circuit()+Y99(PGND↔SEC_GND)` 上再加无害 `AUXGND+R98` 后，`ok=False/subject=Y99` 变成 `ok=True`；把第三地网改名 `ZGND` 又恢复拒绝。`AUXGND↔SEC_GND` 的两脚桥也被漏掉。答案由网名排序决定，会放行跨地族短路。

本批只修 C2-N1，不夹带同报告的 power_entry 方向、V4 坐标或布局问题。当前源码与挖洞时的 flyback SHA-256 完全相同，说明不是已修项；仍然先跑当前基线与先红回归，不拿旧读数当新验收。

## ② 当前树状态

- HEAD 与 `origin/main` 均为 `76e08060ded403793bc6fb0eb64b38f9e140c765`，main；本批禁止任何 git 写。
- `src/boardwise/engines/grammar/flyback.py` 当前 SHA-256 `baaf27e7030a1b3a2023a2f1ae80f0e004d3c44d1d4941060adca3de9218bc10`；`_short_failure` 的 1195 行确为 `first, second = sorted(state.ground)[:2]`。
- `tests/test_113_flyback_grammar.py::test_a_part_shorting_the_two_ground_families_is_refused` 已覆盖两个地网的 Y 电容负例，但没有第三地网/名字扰动。
- 工作树保留他人改动：`src/boardwise/core/circuitsemantics.py`、`tasks/review-line.md`、563 文档/任务书/测试，以及依赖、锁和临时文件。它们不属于本批，不得改、还原或清理。
- 原始可重跑输入在 `outputs/hole570/c2/probes/probe_c2.py:96-112,150-174`，只读复用，不改探针期望。

实施前 `cp` 备份 flyback 到 `.tmp_602/backup/`，记录 SHA-256；不得用 git 恢复。

## ③ 文件域与禁触清单

允许新建/修改仅：

- `src/boardwise/engines/grammar/flyback.py`（仅 `_short_failure` 及必须同步的局部注释/docstring）
- `tests/test_602_flyback_ground_pairs.py`（新聚焦回归；项目已有测试体系）
- 本任务书、`.tmp_602/`、`.tmp_pt_602/`、`evidence/602/`

禁止触碰：

- ②列出的他人文件，`outputs/hole570/` 原始证据，`tests/fixtures/` 既有夹具。
- `power_entry.py`、其它 grammar、`drawcompiler.py`、`readability.py`、shared parser/model/CLI/connector/DSH；不改布局、几何、候选排序或任何阈值。
- 既有测试断言不得删改、放宽、skip/xfail；不新增第二套绑定器或短路检查旁路。

## ④ 交付物与验收

### 先红回归

在生产改动前新增并真实运行测试，保存命令与完整汇总；第三地网用例必须红，既有双地网控制必须绿：

1. 按原探针构造 `minimal_circuit()+Y99+R98`，`Y99` 跨 `PGND↔SEC_GND`，第三地网 `AUXGND` 只经 R98 接 `VOUT2`：绑定必须 `not result.ok`，且 `circuit-invalid` 的失败 `subject=="Y99"`，detail 点名两个真正地网。
2. 同一短路分别将第三地网命名 `AUXGND` / `ZGND`，拒因类别与 subject 完全相同，证明与排序无关。
3. `Y99` 改跨 `AUXGND↔SEC_GND` 同样具名拒绝，覆盖非前两位地网对。
4. 保留 `minimal_circuit()` 正常绑定与既有 `YC1` 双地网拒绝；宽器件（transformer）豁免语义不变，同地网两脚件不误报。
5. 断言失败对象必须对应真实跨地网的 part，不允许仅检查 `not ok`（否则其它缺件拒因会空转）。

### 最小实现

把判定改为检查所有**不同的 gnd-class 网**，不再预取排序前两项。可遍历确定性排序的 edges，若某非-wide 两脚件的两个端网不同且都属于 `state.ground`，直接以该 part 与真实两端网生成现有失败；或等价实现全部无序对。不得要求所有 gnd 网都必须成对参与绑定，也不新增“第三地网非法”规则。保留现有 `len(state.ground)<2`、wide 豁免、category/action 合同和确定性。

修后至少运行：

```bash
.venv/Scripts/python.exe -m pytest tests/test_602_flyback_ground_pairs.py -q --basetemp=.tmp_pt_602/new
.venv/Scripts/python.exe -m pytest tests/test_602_flyback_ground_pairs.py tests/test_113_flyback_grammar.py tests/test_143b_grammar_contracts.py tests/test_201b_placement.py -q --basetemp=.tmp_pt_602/neighborhood
```

若最后文件不存在，改为任务书证据中实际 flyback 邻域测试，并明确替换原因；不得扩大成全量。

至少两项生产变异分别先红：① 恢复只看 `sorted(state.ground)[:2]` 的集合判据；② 把异网条件改成同网/删除 ground 成员判定。每次先 `cp` 备份修后文件，跑新测试必须出现目标红，再 `cp` 恢复并用 SHA-256 证明与修后一致，恢复后复绿。不得使用 `git checkout/restore`。

兼容矩阵：CircuitSpec 内存输入与 flyback grammar 为覆盖范围；离线 compile/真机/V3/V4/容器/多板/CBB 未覆盖。negative control 是正常 flyback、原有双地短路、wide 变压器和同网件行为不变；没有新原理图交付，编译/逐脚/视觉三关不冒充已做。

## ⑤ 纪律与红线

- 零 `git add/commit/checkout/restore/stash/push`，不创建/删除 worktree。
- 禁止 `rm`/`unlink`/任何直删；不移动或清理文件。
- 不跑全量 pytest，不接触 bridge/daemon/EDA/真实工程，不部署/发布。
- pytest 必须独立 `--basetemp=.tmp_pt_602/...`；禁 `-n auto`、禁 `-n >4`；探针单进程，命令带 timeout。
- 不调预算、页框或几何阈值凑绿；不通过改输入网名规避问题；不碰历史证据目录和 fixtures。
- 新发现超出 C2-N1 的失败只记录，不顺手修；同一拒因两轮无新证据即停止交接。

## ⑥ 预算与交卷格式

- 一个 coder，最多 **40 个模型步骤或 30 分钟**，先到先停；不再派下一级代理。
- 交卷正文 ≤2000 字，依次列：实际改动、基线先红原文、修后命令与完整汇总、两项变异与 SHA 恢复、兼容矩阵和未覆盖项。
- 详细日志落 `evidence/602/`，临时读数落 `.tmp_602/`；必须给实际文件 SHA-256 与测试计数，不只写“通过”。
- 有本批未解决红项、缺先红或缺变异，只能写「停止/未完成」，不得写「完成」。

## 交卷记录（2026-11-25）

- 改动：`flyback.py::_short_failure` 删 `sorted(state.ground)[:2]`，改为对 `sorted(state.edges)` 里
  每个非 wide 两脚件判 `left in grounds and right in grounds`；新增 `tests/test_602_flyback_ground_pairs.py`（9 例）。
- 修前 SHA `baaf27e7…bc10` → 修后 `c78aec35…d3aaf`；测试文件 SHA `72748656…97da`。
- 先红：新测试 4 failed / 5 passed（四条洞用例全 `ok=True`）；邻域基线 115 passed, 1 skipped。
- 修后：新测试 9 passed；邻域（602+113+143b+201b）124 passed, 1 skipped；原探针 N1a–N1d 全部 `circuit-invalid, subject=Y99`。
- 变异：M1 单对判据 → 4 failed（同先红四条）；M2 异网改同网 → 5 failed；均 `cp` 恢复并 `CMP_IDENTICAL`，SHA 回到 `c78aec35…d3aaf`。
- 证据：`evidence/602/SUMMARY.md` 与同目录日志/diff。
- 未覆盖：离线 compile/真机/V3/V4/容器/多板/CBB；C2-N2 未动。
