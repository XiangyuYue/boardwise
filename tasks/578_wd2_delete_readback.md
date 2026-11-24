# 任务书：578 / W-D2 — 删页后的页表回读与 confirmed（shared 集成锁）

- 日期：2026-11-24
- 范围：仅 **566-D-3**，connector/shared 独立批；D-1 已由 577 验收，D-2/D-4 suspect 不处理。
- 执行：一个 coder；主代理独立复验。离线，不真机、不全量。

## ① 前因后果

`outputs/hole566/d/REPRO.md` D-3 证明：`docDeletePage` 只信 `deleteSchematicPage() === true`，不重读 `getAllSchematicPagesInfo`。宿主返回 true 但没删、返回 true 却删了另一页，都回答 `deleted:true`，调用方无法分辨。

修法不能只加一句“目标仍在就报错”就完事：成功必须是**目标不在回读中，且回读页集合恰好等于删除前减去目标**。这样同时识别没删、删错页、额外删页。页表读失败/形状异常也报错，不得把不可确认写成成功。

返回加性增加 `confirmed:true` 与 `readBack:{pagePresent:false, remaining:[...]}`；错误带 `confirmed:false` 与相应回读证据。既有 `deleted/pageUuid/name` 和 CONFIRMATION_REQUIRED 语义不变。

577 的实时身份闸已验收，必须保留；本批不夹 daemon 或绘制算法。

## ② 当前树状态

- HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合未提交，零 git 写。
- `connector/src/actions.ts` 含 570，当前 SHA `4962c8f11e973d1ee3ee9e315dac2ec3564c7adb7b75e1a19e352147621a1977`。
- `bridge/protocol.py` 含 570，当前 SHA `6bce8cf190b036c04903f09e0b1d4a9aabb735afd8835f826f411c4d0d1b3184`。
- `docs/bridge.md` 含 570/577，当前 SHA `983c90fc426b3a5a91670d822b76477ffe0dac25c1d22ad10eb475c72018ff38`。
- `docDeletePage` 约 8865–8891 行；`docRename` 的 confirmed 回读是既有先例。
- `connector/tests/actions012.test.mjs` 的假宿主目前总把目标页返回，需要改成真实页 store 才能验回读；不得删正例或让成功假宿主继续“返回 true 但不删”。
- `tests/test_page_delete_guard.py` 的成功响应精确比较需要按加性字段更新，不能改成只检查部分字段来掩盖漂移。
- 563/568、569–577 其它文件与临时件禁触。

实施前 cp 备份生产文件到 `.tmp_578/backup/` 并记 SHA；禁用 git 恢复。

## ③ 文件域与禁触清单

允许新建/修改仅：

- `connector/src/actions.ts`（docDeletePage 与对应注释）
- `connector/tests/actions012.test.mjs`（真实页 store 与回读负例）
- `src/boardwise/bridge/protocol.py`（仅 doc.delete_page returns/summary 的必要口径）
- `docs/bridge.md`（仅 doc.delete_page 行）
- `tests/test_page_delete_guard.py`（成功响应增加 confirmed/readBack，不删原断言）
- 本任务书、`.tmp_578/`、`.tmp_pt_578/`、`evidence/578/`

禁止：daemon.py、CLI/DSH、contracts、绘制引擎、563/568、569–577 其它文件、outputs 历史证据、真实工程。

## ④ 交付物与兼容矩阵

| 维度 | 必须达到 | negative control / 不得声称 |
|---|---|---|
| 真删除 | before 减 target 与 after 集合一致，返回 deleted=true、confirmed=true、readBack.pagePresent=false、remaining | 不再只信宿主 true |
| 返回 true 但没删 | target 仍在 → CONNECTOR_ERROR、confirmed=false | 不得 exit 0/deleted:true |
| 返回 true 但删错/多删 | 页集合与 before-target 不一致 → CONNECTOR_ERROR，带 missing/unexpected/readBack | 不得只查 target 就漏过额外删除 |
| 回读失败/形状异常 | 报错且不确认 | 不得把读不到当 confirmed |
| 未知 uuid / 缺 pageUuid | 既有 BAD_REQUEST/NOT_FOUND 不变 | 不得进入 delete 调用 |
| confirm 门 | daemon CONFIRMATION_REQUIRED 与 confirm 被剥离不变 | 不得绕过人工确认 |
| V3/V4、容器格式、在线/离线、单/多板、普通器件/CBB | 仅 fake host 离线合同，其它维度不变 | 全部真机/容器/多板/CBB 未覆盖；重复 PCB 双审、分歧库串板与本批无关 |

### 先红回归（生产改动前真实运行）

在 `connector/tests/actions012.test.mjs` 固化：

1. 真删除成功：页 store 真移除目标，readBack 目标不在、remaining 恰为 before-target；`confirmed:true` 与 `deleted:true` 同现。
2. 宿主 true 但 store 不变：CONNECTOR_ERROR，confirmed=false，target 仍在。
3. 宿主 true 但删另一页/额外页：CONNECTOR_ERROR，回读差异具名；不能只查 target 就通过。
4. 回读 getAll 抛错/返回异常：错误，不确认；未知 uuid 与缺参数仍走原错误且 delete 调用为零。
5. `tests/test_page_delete_guard.py` 的真实 socket 成功响应除原三键外必须精确包含 confirmed/readBack；无 confirm 仍零帧。

### 实施口径

- delete 前记录页 UUID 集，delete 后再次 `readDocItems`；用集合比较避免宿主合法重排造成误报。缺 uuid/重复 uuid 等异常按不可确认处理。
- 返回 `readBack={pagePresent:false, remaining:[...]}`；失败 detail 可含 targetPresent/missing/unexpected/readBack，confirmed=false。
- protocol/docs 同步 confirmed/readBack 与“完整页集合对账”，不新增 action、参数或 CLI 命令。

### 修后测试与变异

```bash
cd connector && npm test && npm run typecheck
.venv/Scripts/python.exe -m pytest tests/test_page_delete_guard.py tests/test_bridge.py tests/test_bridge_cli.py tests/test_action_catalogue.py tests/test_doc_claims.py tests/test_owner_rules.py tests/test_layer_rules.py -q --basetemp=.tmp_pt_578/neighborhood
```

至少三项变异，cp 备份→指定测试红→cp 恢复并核 SHA：

1. 删除回读、恢复只信 true → 没删/删错用例红；
2. 只查 target、不核完整页集合 → 额外删除负例红；
3. 去掉 confirmed/readBack 合同或 Python 成功响应断言 → 合同/真实 socket 用例红。

交回成功/没删/删错/额外删/回读失败读数、测试汇总、三变异与最终 SHA。证据 `evidence/578/`。

## ⑤ 纪律与红线

- 零 git 写、零删除文件、零真机/daemon/编辑器/真实工程；不跑全量 pytest；探针单进程，前台带 timeout。
- pytest 独立 basetemp，禁 `-n auto`/`-n >4`；不改旧断言、skip/xfail。
- 不新增 bridge action，不把回读不可确认写成成功，不碰真实工程。
- D-2（回收站可恢复性）仍是 suspect，本批不声称删页可恢复；D-4 不处理。

## ⑥ 预算与交卷格式

- 一个 coder，最多 **35 步或 25 分钟**，不派下一级代理。
- 正文 ≤1800 字：`实际改动` → `先红/修后绿` → `三变异与 SHA` → `兼容矩阵与未覆盖项`。
- 有本批红项、缺额外删除或回读失败证据，只能交「停止/未完成」。
