# 559B：在线连通收窄为 direct-only（实测否决 entireTrack）

## 1. 新证据与裁决

初版 559 允许 `entireTrack` 与另一端 direct 的交集作为正证据。主代理随后在真实板上取一个离线 550 图分为 **6 个分离铜分量**的网，调用 `getEntireTrack(true)`：返回 **76 个 ID 且 truncated=true**，其中四个 ID 来自其他离线分离分量（`evidence/559/entire-track-rejection.json`）。这不必证明它总是返回整网，但足以证明：**membership alone 不能证明物理连通**。

本批移除 `track-joins-direct-track` 与 `track-joins-other-pad` 两类正证据，只保留：

- `direct-shared-track`：两端 `getConnectedPrimitives(false)` 返回同一个有类型的 Line/Arc primitive ID；
- `direct-other-pad`：一端 direct 明确包含另一端已解析的 pad ID。

`NOT_PROVEN` 仅表示在该 direct-only 范围内没有共享图元，绝不是开路。多跳路径不在本批承诺；需要它时必须另立 `getAdjacentPrimitives` 图遍历合同和真机语义验证，不能拿 entireTrack 代替。

## 2. 必须保留的其他修复

- 对抗审查 P2-1：direct 非 proof 类型即使宿主漏发 unknown，Python 也补 `direct-non-proof-type` 并压否定。
- P2-2：page/bridge refusal 与拿到证据后的 INDETERMINATE 在文案上分开，refusal 继续 stderr+空 stdout。
- P2-3：版本任一缺失在 `source.versions.missing/error` 具名，不影响 verdict。
- 558 的 connector 优先级修复和 558B 精确 EST026 词不在本批范围，禁止改动。

## 3. 改动合同

- Connector：删除 direct Line/Arc 的 `getEntireTrack` 调用及 `tracks[]`、总 ID 预算与 coverage.ids；direct 仍限16、组件扫描限512。不得调用 entireTrack 来“保留诊断”。响应不再有 tracks。
- Python：删除 `_check_tracks` 和两类 track proof。legacy payload 若有非空 tracks[]，记 `entire-track-unsupported` unknown；不能用于证明。无 tracks 且 direct 无交集、其它证据完整时才 NOT_PROVEN。
- protocol/docs/CLI：只描述 direct shared/direct pad，明确 direct-only 范围与实测否决原因。`boardwise.pcbConnection/1` 尚未发布，按新语义定稿，不保留错误的兼容承诺。
- 测试：新增“from direct=t1、to direct=t2、from.tracks 包含 t2”仍不得 CONNECTED；无 tracks 且完整无交集才 NOT_PROVEN。Connector happy path 断言 entireTrack 调用为零。
- 文档和 handoff/TASKMAP 改写旧 entireTrack 读数，不能留着互相矛盾的承诺；记录 native 未激活和 direct-only 的真实预验。

## 4. 文件域与禁触

`core/connection.py`、`connector/src/actions.ts` 仅559段、`tests/test_559_pcb_connection*.py`、`connector/tests/pcb-connection-probe.test.mjs`、`bridge/protocol.py` 仅559段、`commands/assembly.py` 仅connection描述、`pcb_connection.py` 仅注释、`docs/{bridge,review-sop}.md`、`contracts/cli/v1.json` 官方生成、`tasks/{TASKMAP,review-line}.md`、`docs/handoff.md` 当前559段、`tasks/559*`、`evidence/559/`、`.tmp_559b/`、`.tmp_pt_559b/`。保留他人 lib search/delete-page hunks。禁改checkup/partkind/绘制线/真实工程/货架。先cp备份并记SHA。

## 5. 验收

- 全部559 core/CLI/connector测试、550旧测试、540c/owner/layer/doc-claims/action catalogue通过；Node contract-drift通过。
- 至少两条父独立变异：恢复track交集必须被负控抓住；direct非proof类型漏降级必须被抓住。cp+SHA恢复。
- 主代理用既有550B真实预验复跑：direct shared正例仍CONNECTED，空direct负例仍NOT_PROVEN；entireTrack反例只作拒绝证据，不再参与正证明。原生action未激活边界不变。
- 零Git写、零rm/unlink、零全量（总验收统一一次）、零bridge/EDA（父代理复跑真机预验）、零部署发布。
