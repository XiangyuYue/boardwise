# 041 S1：跨板 NetInstance、披露与保守消费者

日期：2026-11-05。上游合同：`tasks/041-cross-board-net-DRAFT.md`。本批按 `tasks/shared-platform.md` 的集成锁单独实施，**不实现 S2/S3/S4，不改 finding/severity/verdict**。

## 1. 公开数据合同

在 `core/model.py` 增加：

- `NetInstance(board_uuid, net_name)`：冻结数据类；`board_uuid` 必须是非空真实 BOARD uuid，空串直接拒绝。title 不参与身份。
- `UnprovenNetEdge(first, second, reason, evidence_level)`：两端都是 `NetInstance`；同名网的证据只标 `E0`，原因复用 `WELDED_BY_NAME`。它只是“未证明的问题”，不是 proven 边，也不是“已断开”。
- `ProjectModel.net_instances()`：按工程板序列出可寻址板的网络实例；implicit/unattached 的空 uuid 一律排除。
- `ProjectModel.cross_board_net_instances()`：`net_name -> [NetInstance, ...]`，只保留出现在多个可寻址板上的组；与同位号的 `multi_board_designators()` 对应，但值用 uuid 而非 title。
- `ProjectModel.unproven_edges`：由上述组确定性派生两两 unproven 边；无声明文件、无 proven 字段、无 `board#0`。
- `ProjectModel.non_addressable_pages()`：多板工程里空 uuid 组的 `(page_uuid, board_title)`，只披露，不参与实例或边。

**兼容裁决**：现有 `DesignModel.unproven_nets` 和 `ProjectModel.unproven_nets` 保持原义。把跨板名塞进旧字段会让现有网成员规则新增 UNKNOWN，违反“不新增 finding/verdict”的硬约束；新边是同一“未证明”语义的独立数据通道，不改变旧 UNKNOWN 通道。

## 2. 披露合同

`engines/checkup.py` 提供唯一的 `cross_board_net_section(model)` 与 Markdown 渲染器：

- 仅 `ProjectModel` 且板组数 >1 时产生内容；普通 `DesignModel`、单板、隐式板返回空，旧输出逐字节不变。
- `source.crossBoardNets` 含 `boards`（真实 uuid+title）、`count`、`nets[]`、`nonAddressablePages[]`、`note`。每个 net 行含 `name`、涉及实例、`evidenceLevel="E0"`、`reason="welded-by-name"`、`merged=false`。
- 多板无同名网时 `count=0`，证明做过检查；单板整键缺席。无 `proven`、`provenCount` 或“已声明连接”占位。
- checkup 的 `report.json` 增加上述 source 键，`report.md` 独立一节；`boardwise review --md` 复用同一数据/渲染器。`review --json` 的 findings 数组和 CLI 参数、退出码、console verdict 不变。

## 3. 两个实际消费者及回退

1. **triage net→module 归属**：`warning_triage_slots()` 不再通过 `_model_nets()` 合并多板网。按板逐个读取；任一名称出现在多个板组（含 non-addressable）时，不分配模块，绝不 first-board-wins。`_model_nets()` 对多板改为拒绝，防止后续调用者重新引入合并；单板路径不变。
2. **checkup/review 报告**：两个报告共用同一披露派生，不能一个合并、另一个说未合并。报告只披露，不产 finding。

额外兼容锚：`edit plan` 的 `_board_for_designator()` / `repeated_designators()` 拒绝逻辑保持不变；BOM 的 `_parts_with_boards()` 已逐 placement 枚举，无需改动。`engines/bom.py` 吃 `BoardSpec`，不属于本批。

回退：移除新模型派生和披露键，恢复 triage 旧路径即可；无文件迁移、无声明文件、无 CLI/schema 版本变化。

## 4. negative control

新测试 `tests/test_041_cross_board_nets.py`，全部用内存模型/临时目录和既有只读夹具：

1. 两板同名 GND：各实例独立，存在 unproven 边，`run_review` 不新增 finding，无 proven 字段。
2. 相同 CN 位号：不因位号/封装产生网边；A1 的既有 ERROR 独立存在。
3. 数据手册内部短接字段、PCB 铜皮分离均不产 proven/proven-open 结论。
4. 三板组产生确定性两两边；不同 title、相同 title 都以 uuid 区分。
5. implicit 单板无 NetInstance/披露，checkup/review 文本逐字节不变。
6. unattached 被披露但不产实例/边，无位置合成 id；triage 对含它的同名网也不分配模块。
7. 重复 PCB、分歧库继续由 `test_038p1_eprj3_multi_guards.py` 拒绝，本批不放宽。
8. 既有 3 板与 2 板 `.epro2` 真实夹具：板 uuid 全保留、披露与 finding 数/severity/verdict 不变。
9. S2 反断言：无 `--interconnect` 参数、无声明读取器、无 proven 报告键；负例 3/10 留待 S2。

## 5. 兼容矩阵

| 维度 | S1 覆盖 | 必须不变 / 未覆盖 |
|---|---|---|
| V3/V4 宿主 | 仅既有离线板链；真机未跑 | 不声称宿主网表或 DRC 已验证 |
| `.epro2` | 3 板、2 板既有夹具 | 电气连接结论不新增 |
| `.eprj2` | 未覆盖，不套用 eprj3 索引 | 不声称多板兼容 |
| `.eprj3` | 既有板链与重复 PCB/分歧库守卫 | 真实板间线束未覆盖 |
| 在线/离线 | 离线模型与报告；在线不新增声明 | 在线行为不扩张 |
| 单/多板 | 单板逐字节不变；多板数据+披露 | 不自动合并同名网 |
| 普通器件/CBB | 普通器件；CBB 未覆盖 | 不声称 CBB 已支持 |
| S2/S3/S4 | 全部未开工 | 无声明文件、宿主交叉验证或正式规则 |

## 6. 文件域与验收

- `src/boardwise/core/model.py`
- `src/boardwise/engines/checkup.py`
- `src/boardwise/engines/review.py`
- `src/boardwise/cli.py`（仅接入披露，不增参数）
- 新 `tests/test_041_cross_board_nets.py` 及必要的既有报告测试
- 本任务书、`tasks/review-line.md`、上游 DRAFT 状态

禁止改 fixtures、`package.json`、038V 文件、绘制线、connector/DSH/Rust 业务实现。零 git 写、零删除、零真机。先跑聚焦与 040b/038p1/checkup/review/owner/doc，再按串行纪律决定是否全量；至少两次变异并 cp+sha256 恢复。

## 7. 对抗复核与有意行为修正

- 初轮只读复核发现：扁平 `designator -> module` 仍会让同位号跨板首板优先。现按
  `module["board"]` 建立逐板映射，WARN finding 只读 `finding["board"]` 的模块；同 title 或
  多候选一律 None。跨板候选按 `(board index, module name)` 计数，并再查模型中的真实 placements，
  防止裁剪模块清单把两个候选伪装成一个。
- host PCB DRC 叶子没有板身份。多板工程里即使网名只在一块板出现，也可能来自未同步 PCB，
  因此所有多板 `pcb-drc` 行统一 `module=None`；boardwise finding 因带板名，仍可按板归属。
- 空 `ProjectModel` 不再落回 single-board 读法；Markdown 直接打印 JSON 的 `section.note`，
  `count=0` 也能读出“已检查”；uuid 短码统一为后 6 位；`UnprovenNetEdge` 拒绝自环。
- FOC 实测归属行 8 → 7：R18 同时位于 Board1/Board3，旧 `Board1/P1` 是首板误归属，现为 None。
  这是归属语义修正，不是 finding/severity/verdict 变化；FOC `completion.verdict="incomplete"`
  和 review/checkup 退出码 1 均有精确断言。

## 8. 实际验收记录

- 模型首批 34 passed；报告批 62 passed；triage 安全网 60 passed；复核返修后 82 passed；
  最终相关守卫与历史流程 171 passed。各集合有重叠，不相加成全量。
- 全量 Python：**9542 passed / 25 skipped / 2 failed / 1 warning，1244.59 s**。
  仅 `test_193_process_guards.py::test_whole_suite_run_queues_behind_two_slots`
  （`~/.boardwise/pytest-slots` 权限）和
  `test_193_secrecy_hooks.py::test_the_posix_installer_sets_hooks_path_and_the_exec_bit`
  （Git/MSYS `0xC0000022`）失败，与本批前已知环境问题一致，不宣称全量全绿。
- connector：**576 passed**，typecheck 通过。DSH：**129 passed / 1 skipped**，typecheck/build
  通过。Rust：**111 passed / 4 ignored**，fmt/clippy/test 通过。
- 四次变异均转红并以 cp+sha256 恢复：位置合成 board id、单板组误算跨板、triage 跨板拒绝失效、
  单板披露误出现。返修新增的同位号/同模块名/裁剪模块清单负例也钉住后续回退。
- 真实夹具：FOC 146 个 NetInstance、39 个同名组、49 条 unproven 边；MOTOR 分别 156/38/38。
  两夹具 finding 数与 severity 不变；S1 当时记的是 checkup FOC 241 findings、50E/21W/170I，
  review 45 findings、30E/1W/14I。
- **2026-11-06 计数更新（529，不是 041 的改动）**：529 让 2.2/4.7µF 进入 mid 近距离去耦池后，
  FOC 的 checkup 读数是 **239 findings、50E/20W/169I**（少了一条 `decap-required-caps` WARN
  和随它的 INFO）。`tests/test_041_cross_board_nets.py`、`tests/test_041s2_interconnect.py`
  的冻结常量已同步为 239 / (50, 20, 169)；review 仍 45、30E/1W/14I，`completion.verdict`
  仍 `incomplete`，041 自己仍不增不减一条 finding。
- 未覆盖：V3/V4 真机、eprj2 多板、CBB、真实多板 eprj3 文件夹与板间线束。S2 声明读取、
  S3 宿主交叉验证、S4 正式规则均未开工。实现与文档未提交、未推送。
