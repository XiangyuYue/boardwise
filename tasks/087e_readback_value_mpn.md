# 087E：#87⑤ `sch.readback` 可选 value / MPN 垂直切片

日期：2026-11-16。前置：HEAD `504e766` 的 `sch.readback` 只提升 designator/name/footprint/supplier/supplierId/manufacturer 等字段；P43 真实只读回读证明 `ManufacturerId` 仅在 `fields` 内，`OtherProperty` 被 `snapshot()` 折叠成 `{object:true}`，顶层没有 value/mpn。本批实现在线字段提升，不用归档替代在线，不改 `pcb.readback`。

## 1. 公开合同与兼容

- 仅 `sch.readback` 的每个 component row 新增可选 `value`、`mpn`、`valueSource`、`mpnSource`。旧 connector 不提供这些键时，Python/CLI/审查消费者保持既有归档兜底，不猜空值。
- `value` 只读 `getState_OtherProperty()['Value']`；`mpn` 优先 `getState_ManufacturerId()`，为空时回退 `OtherProperty['Manufacturer Part'|'ManufacturerPart'|'partNumber']`。来源分别为 `OtherProperty` / `ManufacturerId` / `null`。
- 字符串空白按无值处理并返回 `null`；数字/布尔属性转字符串；键缺失、getter 缺失/抛错均返回 `null`，不得写成 `''`。读取异常加入既有 `readErrors`/`unreadable` 计数，但保留该器件行。
- `fields.OtherProperty` 仍为 `{object:true}`；既有 `fields`、componentCount、primitives、problems、PAGE_MISMATCH 语义不变。`pcb.readback` 行结构与调用次数一字不变。
- 本批不新增动作、参数、CLI 命令或 DSH 工具，不 bump 版本、不发布。protocol 与 `docs/bridge.md` 同步；`docs/pits.md`、两份 boardwise SKILL、`docs/review-sop.md` 与 `tests/test_doc_claims.py` 把旧的“永远没有 value/mpn”改为“新 connector 可选提供，旧 connector/缺字段仍走归档只读配方”。保留配方可执行钉，不删除离线兜底。

## 2. 两个实际消费者与回退

1. 在线 component-value 写后复查/CLI readback 消费：新增键可用于独立复核；缺新键的旧响应仍走原 `readBackAfter`/归档路径，旧 CLI 参数、退出码和 monkeypatch 可观察面不变。
2. `engines/checkup.py` 的 component.value/mpn 审查消费：本批不把在线 readback 自动接入归档模型，不改 finding/verdict；用既有消费测试证明归档值来源和报告不变，避免把连接器新增字段误当已重接审查管线。

回退只移除新增提升键及文档声明即恢复旧行为；无需迁移数据。shared→review/draw 不新增 import。变异用 cp 备份与 SHA-256 恢复，禁 git restore。

## 3. 兼容矩阵与 negative control

| 维度 | 本批覆盖 | 必须不变 / 未覆盖 |
|---|---|---|
| V4 在线普通器件 | 后续热更后验 P43；离线 fake 本批必做 | 热更前不得声称在线已验 |
| V3 在线 | 未覆盖 | 不把 V4 或 fake 读数写成 V3 兼容 |
| 旧 connector 响应 | 无新增键时消费者行为不变 | `null` 不等于空串，旧归档兜底不删除 |
| `.epro2/.eprj2/.eprj3` | parser 未改，仅保留既有归档配方钉 | 不声称容器兼容发生变化 |
| 单/多板 | 单工程单页 readback；多板未覆盖 | 重复 PCB 双审、分歧库串板不在本批改变或宣称验证 |
| 普通器件 / netflag / CBB | 普通器件与无 Value 的 netflag fake；CBB 未覆盖 | 不声称 CBB 属性推断已支持 |
| sch / pcb | 只改 sch | pcb row、getAll 次数与字段保持不变 |

Negative control 至少包括：`OtherProperty` getter 抛错仍返回行且 `value:null` 并计 unreadable；空对象/空串返回 null；数字 `Value:100` 得 `'100'`；只有 `OtherProperty['Manufacturer Part']` 时 `mpnSource==='OtherProperty'`；`ManufacturerId` 优先；netflag 无值；pcb 零新增键；既有 PAGE_MISMATCH 与 sch 普通路径不变。

## 4. 文件域与验收

生产/合同：`connector/src/actions.ts` 的 readback 小区段及 helper、新 `connector/tests/readback-component-value.test.mjs`、`src/boardwise/bridge/protocol.py` 的 sch.readback returns、`docs/bridge.md` 对应行。文档同步仅限上节列出的 pits/SKILL/review-sop/doc-claims 必要段。不得修改绘制线、fixtures、checkup 引擎、CLI 业务、connector/package.json、dsh-plugin。

聚焦验收：connector 新测试 + `readback-page-guard.test.mjs` + 既有 actions/readback 邻域，随后 `npm run typecheck`；Python 只跑 action catalogue、doc-claims、相关 readback/CLI/审查消费与 owner/layer 聚焦测试，独立 `--basetemp`，不跑全量。至少两处有效变异：移除 value 提升、禁用 ManufacturerId 优先/回退，测试必须先红；cp+SHA-256 恢复。

真机验收另段执行：岳批准热更后，仅 `test V4` P43=`797f20b8a217b331`，先核 projectUuid `1ea6af15c2b1bd8132b46a0648d4e149ced21066c4a6650bbffd40dc5e286a5b`，再取 `sch.readback` 与 `sch.list_attributes` 双源对照 C24/R15/U9 的 value/MPN，电源/netflag 应为 null；只读设计，不保存。真实工程禁碰。热更与版本发布均不在本子批自动执行。

## 5. 主代理集成复核补充

- 子代理离线交卷：新 node 11 例、相关 connector 126+38 例、Python doc/action/owner/readback/checkup 聚焦均绿；三项变异均按预期红并恢复。主代理另做独立变异与聚焦复验，不直接转述子代理计数。
- 主代理发现 `src/boardwise/cli.py` 的 `write.valueChannel` 仍写“sch.readback 永远没有 value”，已仅改报告文案为“新 connector 可选提升，旧响应缺键走归档”，`sch.set_component_attribute` 与 finding/verdict/CLI 参数不变；新增聚焦 `tests/test_054_draw_cli.py`。代码注释中未经真机验证的 P43 属性来源断言也已改成已观察到的 snapshot 事实。
- `tests/test_doc_claims.py` 同时含绘制线未提交 hunk，提交时必须只选 #87⑤ 的两个 hunk，不得把 `pytest` import 及 548 系列断言混入审查线提交。

## 6. 主代理独立实测读数

- connector 新测试 + page guard：**22 passed**；typecheck 通过。
- 主代理变异：移除 value 提升与禁用 ManufacturerId 优先均使新测试失败；最终恢复 **11 passed**，`connector/src/actions.ts` 恢复 SHA-256 前后均 `46b48e0f31564ef2b2e5427ee636321b327be47e44ed4355e771cccc97bef5a0`。
- Python：`test_054_draw_cli.py` **41 passed**；#87⑤ doc/pit 聚焦 **13 passed**；`test_025d_checkup_report.py + test_537c_live_capture.py` **60 passed**。日志 `.tmp_087e/main-*.log`。
- 真机事前基线：旧 connector 的 P43 readback 顶层无 value/mpn；`sys.connector_status.capabilities` 不存在。公开 `sys.get_document_source(maxChars=200000)` 完整 102274 字符、323 记录，C24=`100nF/CC0603KRX7R9BB104`、R15=`10k/0603WAF1002T5E`、U9=`STM32G431/STM32G431RBT6`，证据 `.tmp_87_probe/p43-expected-identity.json`。旧 connector 无 `sch.list_attributes`，未把 UNKNOWN_ACTION 写成双源通过。
- 以上仍是离线实现与事前基线，**热更后的在线新字段验收未做**；V3/CBB/多板未覆盖。
