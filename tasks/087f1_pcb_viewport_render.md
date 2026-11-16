# 087F1：`export.render` PCB viewport 分支

日期：2026-11-16。前置：`tasks/087f_pcb_render.md` 已在 test V4 证明 EDA 4.1.93 上 PCB1/PCB2 的 `getCurrentRenderedAreaImage` 返回不同、真实且与当前板一致的 PNG。该通道只能是 viewport 级，不是 document render。本批实现 connector 动作，不把 `export.screenshot` 的全局缓存警告洗白。

## 1. 公开合同与两个消费者

- `export.render` 在**确证目标为 PCB**时走新分支；目标由直接活动文档或 `doc.list` 中 `pageUuid` 的类型确定。未知类型保持旧路径，不得猜测。
- PCB 只接受 `format=png` 与 `scope=page`；svg/pdf、selection/project 具名 `NOT_IMPLEMENTED`/`BAD_REQUEST`，不得再进 `sch_ManufactureData.getExportDocumentFile`。
- 先复用 `activateExportPage` 激活并回读目标，确认 direct active type=pcb；调用 `zoomToAllPrimitives` 和 `dmt_EditorControl.getCurrentRenderedAreaImage(tabId?)`。缺 API、空 Blob、零字节、非 PNG 签名、超时均具名失败；不能凭 `blob.type` 认图。
- 返回新增 `channel:'viewport'`、`evidenceGrade:'viewport'`，保留 `format:'image/png'`、encoding/bytes/data/scope/activatedPageUuid/activated，并在 note 写明“不是 document render，使用前须核新鲜度”。不得返回 bboxes 或把 geometry 当 render。
- 消费者 A：CLI/审查直接 `export.render` 可在 PCB 得到具等级的 PNG。消费者 B：后续 `liveevidence` 只在 channel/evidenceGrade 匹配时采集；本批保留其“不调用 PCB render”行为，下一小批接入。原理图 CLI/draw 的 document render 是反向消费者：scope/objectLiteral/fileType/timeout/selection/project 和输出保持原行为，`channel:'document'` 可显式附加但不得改其它字段。

## 2. 兼容矩阵与 negative control

| 维度 | 覆盖 | 必须不变 / 未覆盖 |
|---|---|---|
| V4 PCB | test V4 探针已证 viewport；本批 fake + 后续热更候选验收 | 热更前不得写在线新分支已验 |
| V3 PCB | 未覆盖；旧缓存坑仍披露 | 不把 V4 读数写成 V3 可用 |
| sch | 既有 actions006b 等回归 | document render 调用/输出、timeout 与 scope 不变 |
| 文件格式/容器 | 仅在线 PNG；SVG/PDF、`.epro2/.eprj2/.eprj3` 未改 | 不声称矢量或容器渲染支持 |
| 单/多板 | 单工程逐块活动 PCB；多板同时采集未覆盖 | 重复 PCB 双审、分歧库串板不在本批改变或宣称验证 |
| 普通板/CBB | 普通 PCB viewport；CBB 无关 | 不以空骨架板外推生产板全部视觉结论 |

Negative control：PCB+PNG 时 sch getExportDocumentFile 调用 0；PCB+svg/pdf/selection/project 拒绝且无 data；空 Blob/零字节/伪 PNG/超时各自具名错误；pageUuid 指向 PCB 时也能分支；目标未知不误判；sch 三 scope 与 timeout 钳制旧测试不变。

## 3. 文件域与验收

仅 `connector/src/actions.ts` 的 exportRender 及紧邻 helper、新 `connector/tests/export-render-pcb.test.mjs`、`src/boardwise/bridge/protocol.py` 的 export.render 合同、`docs/bridge.md` 对应行、本任务书。不得改 `liveevidence`、review-sop/doc-claims/pits、#87⑤ readback 段、绘制线、fixtures、版本或发布件。087F2 再接消费者与 SOP。

验收：connector 新测试 + `actions006b.test.mjs` + screenshot/render 邻域，npm typecheck；Python action catalogue/read-only 聚焦。至少两处变异：PCB 分支误走 sch API、去掉 PNG 签名检查，必须先红；cp+SHA-256 恢复。真机热更后只在 test V4 PCB1/PCB2 候选复验，另批授权，当前不做。

## 4. 实现与主代理复核（2026-11-16）

- 已实现目标类型读取、确证 PCB 的 activate/re-read、zoom+viewport capture、PNG 签名、timeout、channel/evidenceGrade、pageUuid 与错误路径；sch 返回增加 `channel:'document'`。新文件 `connector/tests/export-render-pcb.test.mjs` 23 例。
- 首轮调度曾改变“缺 sch API + 坏参数”的报错优先级，主代理拒收后返工：非 PCB 恢复先探测 mfg 再校验 format/scope；新增 sch 缺 API+坏格式仍 NOT_IMPLEMENTED、PCB 无 sch_ManufactureData 仍成功两钉。
- 主代理最终：新测试+actions006b **74 passed**，typecheck；Python action/read-only/owner/doc-claims **102 passed**。变异：PCB 误走 sch → **17 failed / 6 passed**；去 PNG 签名 → **2 failed / 21 passed**；恢复后 74/74，`connector/src/actions.ts` SHA 前后一致（最终 `cf281b939b32899a4e411cddb5f56743509a7939075848576187e9484b2aa5b7`）。
- 子代理首轮约 47 步，超过 40 步预算，后续 8 步小返工完成；记录为流程偏差，不扩大本批范围。
- 真机新分支、V3、生产非空板、SVG/PDF、多板并发仍未覆盖。087F2 接能力旗帜和 live evidence，087F3 才做热更与 SOP 更新。
