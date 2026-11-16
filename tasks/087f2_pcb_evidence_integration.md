# 087F2：PCB viewport 接入 live evidence（能力闸）

日期：2026-11-16。前置：087F1 提供 `export.render channel=viewport / evidenceGrade=viewport`。旧 connector 没有该能力，不能为了探测而再进 schematic-only API 等 10 s。本批用显式能力旗帜接入采集，保持旧 connector 的零 PCB render 调用。

## 1. 公开合同与两个消费者

- `sys.connector_status` 新增可选 `capabilities.pcbRenderViewport: true`（仅新 connector）。旧响应缺该键或返回 false = 无此能力；不得靠版本号猜测。
- `liveevidence` 在已核焦点的 PCB 上先读能力：缺键/false → 不调用 `export.render`，`pcbImage=not-applicable` 并保留 `PCB_IMAGE_LIMIT`；状态读取失败/无法判定 → 不得写 ok，按未验证披露。
- 有能力时才调用 PCB `export.render(format=png,scope=page,pageUuid,timeoutMs=10000)`；响应必须同时满足 PNG 校验、`channel='viewport'`、`evidenceGrade='viewport'`，否则该 step failed，不能写 ok。成功 PNG 写 `live-pcb-<板名>-<短uuid>.png`，artifact 带 channel/bytes/sha256，detail 明示 viewport 而非 document render。
- 消费者 A：`review-evidence`/checkup 的 pcbImage 槽可采集真实 viewport；消费者 B：`sys.connector_status`/doctor 能读到同一能力，供调用方避免旧宿主超时。原理图 schematicImage、livePcb readback+geometry、focus restore 与其它通道不变。

## 2. 兼容矩阵与 negative control

| 维度 | 覆盖 | 必须不变 / 未覆盖 |
|---|---|---|
| 新 connector + V4 PCB | fake viewport 成功；后续 test V4 真机另批 | 热更前不得声称在线采集已验 |
| 旧 connector | 缺 capabilities 键，export.render 调用 0，not-applicable+limit | 不得用 10 s 超时探测能力 |
| 能力状态失败 | 不得写 ok/伪造图 | 不将未知读成有能力 |
| 错 channel/grade/伪 PNG | step failed、无 artifact | document/geometry 不能冒充 viewport |
| 无 PCB / 显式子集 / 焦点失败 | 既有状态语义不变 | 无 PCB 不变成 failed；子集成功不变成全覆盖 ok |
| sch / livePcb / restore | 既有回归 | 原理图 document render、几何和焦点恢复不变 |
| 容器/多板/CBB/V3 | 未覆盖 | 重复 PCB 双审、分歧库串板不宣称改变；不外推 V3 |

Negative control：缺 flag、false、status 异常、channel=document、grade 缺失、伪 PNG、render 异常、无 PCB、焦点失败、显式子集。`CHANNEL_PCB_IMAGE` 的 step/artifact 归属必须正确，sch PNG 不计入 PCB。

## 3. 文件域与验收

生产：`connector/src/actions.ts` 的 connector-status 小区段、`src/boardwise/engines/liveevidence.py`、`src/boardwise/bridge/protocol.py` 的 sys.connector_status returns、`docs/bridge.md` 对应行。测试：既有 connector-status 邻域、新/既有 `tests/test_537c_live_capture.py`、必要的 `test_537c_evidence_coverage.py`。不得改 exportRender 的 087F1 分支、#87⑤ readback、绘制线、fixtures、版本或发布件。

验收：connector 邻域 + typecheck；Python `test_537c_live_capture.py`、`test_537c_evidence_coverage.py`、action/owner 聚焦，独立 basetemp，不跑全量。至少两处变异：缺 flag 仍 render、接受错误 grade，必须先红；cp+SHA-256 恢复。SOP/pits/doc-claims 的口径更新与真机热更候选验收另列 087F3，不在本批。

## 4. 实现与主代理复核（2026-11-16）

- 已实现 `capabilities.pcbRenderViewport`、一次 host 级能力读取、viewport provenance/PNG 校验、artifact 归属与三态通道判定。旧 connector 缺 flag/false 时 PCB render=0；能力不可读为 missing；有能力才逐板出图。
- 子代理：live capture 63 passed，四件套 152 passed，bridge 172 passed，connector 809 passed；主代理独立四件套+action/owner/doc-claims **242 passed**，connector **809 passed** + typecheck。
- 主代理独立变异：把 absent 也当 available → **18 failed / 45 passed**；接受错误 grade → **4 failed / 59 passed**；恢复后 **63 passed**，`liveevidence.py` SHA 前后均 `af28df6b7578951ffd2807bb2495325a1b5bece5d0885daff53e2a807efa08ee`。
- `tests/test_537c_review_evidence_cli.py` 的 FakeClient 也补了旧 connector 默认 `sys.connector_status` 应答，原断言未改。另有一组扩展 537C 测试出现 1 条「墙钟」文档红，属于其他线未提交改动，本批未碰、未掩藏。
- 能力读取在导航前执行一次，出图仍在逐板焦点证实后；新 connector 焦点失败会使 pcbImage failed，旧 connector 保持 not-applicable+limit。真机热更与 SOP/pits/doc-claims 更新归 087F3。
