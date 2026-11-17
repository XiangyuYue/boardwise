# 绘制线资产索引

> 整理基线：2026-11-17；P137状态已更新。本文只做资产路由，不授权移动、删除或 Git 写。
> 当前派单仍以 [`tasks/draw-line.md`](../tasks/draw-line.md) 为准，历史结论以各批次验收文件为准。
> 机器元数据（文件大小、SHA-256、目录计数、worktree 原文）见
> [`evidence/draw-assets/manifest.json`](../evidence/draw-assets/manifest.json)。

## 1. 当前唯一工作集

| 资产 | 当前身份 | 权威位置 / 边界 |
|---|---|---|
| 当前任务书 | **P144固定glyph场景通过、未提交 / 整图未通过** | [`tasks/548p144_ground_label_terminal.md`](../tasks/548p144_ground_label_terminal.md) + [`验收`](../evidence/548P144/README.md)：固定glyph纳入scene.solids/bodies；新测试3 passed、两项变异，C1.2消失，完整候选仍拒 |
| 下一任务书 | **规划，未实施** | [`tasks/548p145_u18_label_replay.md`](../tasks/548p145_u18_label_replay.md)：U1.18名称盒与LED2_K/LCD_SCK回放冲突 |
| 当前电路 | **下一批输入；电气纠正已核，页面未通过** | [`evidence/548P125/circuit.full.g3c.pinmap.json`](../evidence/548P125/circuit.full.g3c.pinmap.json)：30件/31网/4NC/114成员；仅C3.1→NRST、R1.1→BOOT0，沿用547G3C assumed意图 |
| 当前 presentation | **P126语义输入，不是通过基线** | [`evidence/548P126/full.presentation.service-feedback.json`](../evidence/548P126/full.presentation.service-feedback.json)：G3C + localSeats + branchOrder + 真实GND分组；尚无候选 |
| 当前符号库 | **本整图输入的实测库** | [`evidence/548P59/full.library.json`](../evidence/548P59/full.library.json)；WiFi/P43各有自己的校准库，不混用 |
| 生产编译器 | **P144固定glyph场景通过、未提交，整图未通过** | `src/boardwise/engines/drawcompiler.py`，SHA `976a4c2cad08804f994466419950e498aae2296a49de0b87536a72a7a653b2ea` |
| 服务座位器 | **P143多成员度量已验收、未提交** | `src/boardwise/engines/placement.py`，SHA `0674eb3842529fe280d06dc59c426f9eda7a1789cd0a1c35b86e89244596bb82` |
| 其他关键源码 | **混合工作树资产，不归属本批独占** | `drawapply.py`、`pagecompiler.py`、`core/presentationspec.py`；精确SHA见manifest，禁止覆盖他人改动 |
| 当前回归 | **P144固定glyph + P143多成员度量 + P141端点守衛 + P138联合反馈 + P137答案保留 + P135同网行距 + P126服务反馈 + P43精确输入钉** | [`tests/test_548p144_ground_label_terminal.py`](../tests/test_548p144_ground_label_terminal.py)、[`tests/test_548p143_net_member_relation.py`](../tests/test_548p143_net_member_relation.py)、[`tests/test_548p141_net_endpoint_repair.py`](../tests/test_548p141_net_endpoint_repair.py)、[`tests/test_548p138_joint_3v3_seat.py`](../tests/test_548p138_joint_3v3_seat.py)、[`tests/test_548p137_c2_service_seat.py`](../tests/test_548p137_c2_service_seat.py)、[`tests/test_548p135_same_net_gap.py`](../tests/test_548p135_same_net_gap.py)、[`tests/test_548p126_service_host_feedback.py`](../tests/test_548p126_service_host_feedback.py)、[`tests/test_548p124_p43_regression.py`](../tests/test_548p124_p43_regression.py)：一次反馈、完整服务答案、同/异网负例、真实5/5、完整P43 |
| 当前证据说明 | **P144固定glyph通过，U1.18未通过** | [`evidence/548P144/README.md`](../evidence/548P144/README.md)：固定glyph纳入scene.solids/bodies；新测试3 passed、两项变异、P142/P143/P144合计6 passed；完整候选首拒U1.18；P43/WiFi geometry不变；整图无候选、未视觉 |

生产基线：`108e42d`；历史绘制批次已由用户 `cb44c2e` 落地，原P140六批不重复执行。
P142/P143/P144实现未提交，其他线未提交改动保留。禁止用 `git restore/checkout` 选择“干净基线”。
当前整图、LCD automatic、真机/apply和全量验收均未完成。

## 2. 已验收锚（只在其声明范围内有效）

| 锚 | 已通过范围 | 不能外推 |
|---|---|---|
| P43真实64脚MCU | [`ACCEPTANCE.md`](../evidence/548D/host-binding/p43/ACCEPTANCE.md)：automatic单岛，20/20声明脚+48/48 NC、lint 0/0/0、已apply；持久化仅`saved_unverified` | 不是当前六件MCU、不是完整三岛/整页；DRC开放项仍在 |
| P124 P43 regression | [`p43-regression/README.md`](../evidence/548P124/p43-regression/README.md)：当前生产码恢复原P43 geometry/SVG；119 focused、两项变异、主代理视觉 | 不证明当前整图MCU通过，不是新真机验收 |
| WiFi三组页 | [`548P118/README.md`](../evidence/548P118/README.md) + [`独立验收`](../evidence/548P118-independent/README.md)：1候选、18/18物理脚、7网、独立视觉 | 不返工；不签宿主标签外观、真机或整页 |
| LED | [`548P122/README.md`](../evidence/548P122/README.md)：隔离页`PAGE=True`、3候选，同列与局部直连恢复 | 不把旧P60候选当可回放基线，不证明整页LED |
| UART | [`full.presentation.uart.json`](../evidence/548P120/full.presentation.uart.json)：模块级`presentation.sidePreferences`恢复 | 不回到P119伪节点异常，不改shared placement |
| MCU脚向 | [`548P123/README.md`](../evidence/548P123/README.md) + `role-delta.json`：15个角色变化 | 是历史输入层；后续应与P125 G3C语义合并，不单独当最新整图输入 |
| LCD人工参考 | P47及[`548P108-independent/README.md`](../evidence/548P108-independent/README.md)：人工关系与独立拒因 | LCD automatic未验收；禁抄人工绝对坐标，旗标处不重复网络标签 |

## 3. 被取代或拒绝的资产（保留作证据，禁止续用为基线）

| 资产 | 分类与原因 |
|---|---|
| [`548P120/circuit.full.pinmap.json`](../evidence/548P120/circuit.full.pinmap.json) | **被P125 G3C输入取代，但保留为映射来源**；仍把C3.1/R1.1放3V3，与547G3C冲突 |
| [`548P123/full.presentation.mcu-roles.json`](../evidence/548P123/full.presentation.mcu-roles.json) | **历史输入**；脚向纠正有效，但不包含P125电气纠正/localSeats实验 |
| [`548P124/full.presentation.gnd-groups.json`](../evidence/548P124/full.presentation.gnd-groups.json) | **完整页拒绝证据**；生产校验实测：GND不含U1.31/U1.47/U1.63，不能进入整页 |
| `.tmp_548p124/drawcompiler.flag-walls.unverified.py`、`.tmp_548p124/drawcompiler.candidate.py` | **撤回的grid_check/flag_walls实验副本**；没有消除后续重叠，禁止恢复生产 |
| `.tmp_548p125/probe_custom_service.py`及custom日志 | **反向探针**；人工限定顺序/host只证明有解，不是生产路径或候选 |
| P111/P112 corridor、P113/P114救援材料 | **历史拒绝/侦察证据**；不得重开固定近档硬盒或隐式增加build。WiFi最终通过以P118为准 |
| `tests/test_548p112_local_flag_corridor.py` | **洞口测试资产**，不是当前能力证明；运行相关测试时须读其实际断言与历史边界 |

## 4. 证据、实验与临时资产分类

### 保留

- 上两节全部当前输入、验收锚、拒绝证据及其原始读数；`untracked/ignored`不改变保留身份。
- `evidence/548P*` 的历史README与唯一原始证据。历史检索走 `tasks/TASKMAP.md`，细节才查
  `PROGRESS.md`，不把旧README逐份搬入当前工作集。
- 当前源码备份与变异恢复点，至少在对应批次验收和后续集成完成前保留。
- `tests/fixtures/`、黄金板、真实会话核实区，以及 `outputs/011e*`、`014_*`、`015b_*`、`016_*`，一律不碰。

### 归档候选（只登记，未移动）

- P111–P114已否决corridor/救援实现与大段过程日志：有历史价值，但不参与当前派单。
- `.tmp_548p124/p43-rungs.log`（6,238,299 bytes）等 unique 原始追踪：可评估归档，不能仅因体积大回收。
- 更早548P批次的过程性探针：先核对是否被任务书、测试、文档或变异恢复引用，再逐批提出归档路径和敏感信息审查。

### 已批准回收（2026-11-17，已完成）

用户先批准回收范围，随后对实际数量更正再次明确批准。相关Edge/pytest进程均为0；
12个目录逐一解析核对后，以 `SendToRecycleBin` 送入Windows回收站，全部确认路径不存在。
未使用任何直删命令。准确路径与执行口径见
[`recycle-log.json`](../evidence/draw-assets/recycle-log.json)。

| 资产 | 处理 |
|---|---|
| `.tmp_548p124/edge-profile-p43/` | 248文件/6,942,687 bytes；独立Edge渲染配置，已回收；最终PNG/SVG仍在P124 evidence |
| 11个 `.tmp_pt_548p12*` basetemp | 多数为空，合计20,277 bytes；已回收，pytest可按批次独立重建 |

其他`.tmp_*` **暂不列为可回收**：先证明可再生成、无引用、无独有证据、非注册worktree，
再单独申请。`.tmp_548p124` 其余内容和 `.tmp_548p125` 暂保留，包含唯一探针、反向实验和恢复点，
不能按前缀整目录清理。

## 5. worktree 边界

`git worktree list --porcelain` 当前共20项（含主仓），原文在manifest。主仓之外的
`.tmp_algo_eval`、`.tmp_corridor*`、`.tmp_review_line`、`E:\boardwise-wt-*` 等均是独立边界，
**不按普通临时目录归档或回收**。绘制线、审查线及release worktree互不改文件；
`worktree add/remove/prune` 仍需逐次批准。

## 6. 后续批次的资产纪律

1. 开工先读本索引与对应任务书，记录生产SHA、输入SHA、混合工作树归属和备份位置。
2. 长期证据放 `evidence/<批号>/`；一次性探针建议 `.tmp_<批号>/probes/`，原始输出放
   `.tmp_<批号>/raw/`；pytest使用独立 `.tmp_pt_<批号>`，不在仓根散放文件。
3. 每批结束只更新本索引的状态与链接，附真实命令/读数；不把实验规格写成通过基线，
   不把局部候选写成整页完成。
4. 移动、归档、回收分别申请；删除只进回收站。任何Git写仍逐次批准。
