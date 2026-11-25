# 任务书：618 — 548P126 可重放证据的真实性收口

## ① 前因后果

`outputs/hole570/h2/REPRO.md` 的 **570-H2-02**：548P126 的 P43/WiFi 报告只留 geometry 指纹，没有 argv 与模块级 circuit/presentation/profiles 三件套，`reference-replay` 不可重算。原 FIX 建议直接补完整命令，但不能猜。

主代理已复核：
- 当时 drawcompiler/placement 备份仍在 `.tmp_548p126/`，SHA 分别 `2bb3fcea…cd85d3`、`f550f6ea…9859d60`，与 README 一致。
- 全页电路与规格、library 仍在，SHA `90646554…f0d2`、`ec192d86…1fb2d`、`b882cf88…3d0e`。
- 候选 source 指纹为 MCU circuit `70e9953e…` / presentation `a3baa09b…`，WiFi `0af95e6f…` / `50f2847b…`。
- 当前 `_module_view` 得 MCU `d44621d8…`、WiFi `d55f5a6d…`；cb44 版得同样 circuit hash，但都与原指纹不同。说明不能直接写“原命令就是当前 _module_view 的输出”。

本批目标是让证据诚实可重放：只有用当时源码在临时/证据目录真实重算出**同一 geometry**，才可记录“重建输入 + 可复算 argv”；否则明确标记原始三件套/argv 未保留，不得升级为 reference-replay。

## ② 当前树状态

- HEAD/origin `76e08060ded403793bc6fb0eb64b38f9e140c765`；前批全部保留。
- 原候选 `evidence/548P126/{p43,wifi}-compile/cand1.layout.json` 的 geometry 分别为 `a9201cfb85d8878391713a143a1199c9a9bb0e6e1a33404f0a038edcfea3d48e`、`a6232436e8e7f78d6168f353944a8cb0c76b5068684e5865b018149e92be5fda`。
- `.tmp_618/pagecompiler.cb44.py` 是主代理只读提取的 cb44 pagecompiler，供反推；不是生产文件。当前 76e 的 pagecompiler 与当时已漂移。
- `tests/test_548p126_service_host_feedback.py` 显示当时 MCU 通过 `_module_view` 后 bind/_prepare，profiles 用 full.library；WiFi 的确切历史输入仍需证据，不得假设。
- 生产源码、原始报告与候选**不得修改**。他人 563/review-line/router/临时文件禁触。无需 cp 生产备份，本批不预期改 src。

## ③ 文件域与禁触清单

允许新建/修改仅：
- `evidence/548P126/PROVENANCE.md`（新；真实结论）
- `evidence/548P126/replay/`（仅在重算成功后存重建三件套、脚本、结果与日志；若失败只保留调查日志，不伪造成功输入）
- `tests/test_618_p126_provenance.py`（新；校验文档中的实际状态与现存文件/hash，不默认真机/历史）
- 本任务书、`.tmp_618/`、`.tmp_pt_618/`、`evidence/618/`

禁止：src、原报告/原候选、fixtures、历史 outputs、其它 evidence 文件、CLI/contracts/connector/DSH 和他人文件。不得用当前引擎输出覆盖旧 geometry，不得修改候选 source hash 使其匹配，不得 git checkout/worktree。原始 `.tmp_548p126` 只读，不改备份。

## ④ 交付物与验收

### 有限的重建尝试

1. 用 cb44/当前 `_module_view` 派生 MCU/WiFi 三件套，分别与候选 source hash 对照并记录 DIFF（主代理已有读数，需复核）。在隔离子进程中以 `sys.modules` 注册当时的 placement/drawcompiler 备份及所选 pagecompiler，不能让当前生产引擎混入；调用真实 compile，不手改坐标/候选。
2. 若几何不匹配，可再检查**现存历史探针/README** 是否给出另一份明确的模块输入（不是自由调参）。最多两条有证据的输入路径；同一不匹配不得换 seed/budget/页框/规格凑 hash。40步/30分钟到线即停。
3. **成功条件很严格**：同一重建输入与当时源码生成候选，`geometry_sha256()` 与原值完全一致，而且独立重算候选零件/网/逐脚分区与原 LayoutPlan 一致；source hash 不同的要披露“输入是重建等价物，不是原件”。保存 argv、三件套 SHA、引擎 SHA、结果 JSON/log。只有这时 PROVENANCE 才能写 `reference-replay (reconstructed-input)`，并附完整命令。
4. **失败条件**：任一几何不匹配或缺输入，就在 PROVENANCE 写 `not-replayable / raw module inputs and argv not preserved`，列已尝试路径与真实读数；历史指纹保留作事实，不再声称 reference-replay。失败同样是本批的诚实交付，但不许写“已恢复重放”。

### 机器钉与变异

- 新测试读取 PROVENANCE：成功态核对 argv 指向的文件都存在、hash/geometry 与结果一致，并实际重跑至少一条；失败态核对明确 raw not preserved、无虚构命令/无 replayable 字样，原 geometry 与现存报告一致。
- 至少两项变异：① 把成功态的一个输入 hash/geometry 改错（若成功）或把失败态改成 replayable（若失败），测试必须红；② 删除/错指一个必要证据路径或引擎 hash，测试必须红。变异只改临时副本/文档后立即 cp+SHA 恢复，不碰原候选。
- 跑新测试与必要 doc-claims/workspace 测试；不跑全量。文档必须清楚区分原始记录、重建尝试、当前引擎，不宣称新图三关或真机。

## ⑤ 纪律与红线

零 git 写/移动/删除；禁 rm/unlink 和 git checkout/restore/worktree；不全量、不真机、不部署。探针单进程、命令 timeout；不启动 daemon。不得为匹配 geometry 改规格/budget/网名/候选，不能用当前引擎漂移冒充历史结果，不修改原始报告。停止交接必须写真实失败与下一最小证据需求。

## ⑥ 预算与交卷格式

一个 coder，最多 40 步或 30 分钟；不派下级。交卷 ≤2000字，含输入 hash 对照、实际引擎/命令、成功几何或失败读数、PROVENANCE 最终状态、两项变异与 SHA 恢复、未覆盖项。证据落 `evidence/618/`，重建资产仅在成功时落 `evidence/548P126/replay/`。没有真实重算不得写“可重放完成”。
