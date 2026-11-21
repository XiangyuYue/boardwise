# 562A：Connector `pcb.path_probe` 邻接证据采集

## 1. 前因后果

562 总合同已随 `0b21342` 推送，岳已批准除 DSH 外完成实现与真机验收。559 的 `pcb.connection_probe` 只采集 direct 证据，559B 已否决 `getEntireTrack`。本批新增独立 `pcb.path_probe`，为 Python 多跳 BFS 提供逐跳证据；本批不接 protocol/CLI、不判 verdict、不做 DSH。

现行合同：`tasks/562_live_pcb_path_graph.md`。中间邻接的双向互证由 562B Python 判定；Connector 必须分别记录两个方向的调用，不能自己把单向边删成“未知”或把它拼成路径。

## 2. 当前树状态

- HEAD `0b21342` 与 origin/main 一致，工作树混有绘制线和其他 owner 的未提交改动。
- `connector/src/actions.ts` 在 1696 附近有他人的 lib search hunks，559 段与 registration 附近也有既有内容；只能追加本批 helper/handler/注册，不能格式化或还原文件。
- 562A 不改 `pcb.connection_probe`、550B `sys.probe`、Python、protocol、CLI、DSH、真实工程、版本号。

## 3. 文件域与禁触

只允许：

- `connector/src/actions.ts`：在 559 段后追加 path helper/handler，并在 `buildHandlers` 注册 `pcb.path_probe`；
- 新 `connector/tests/pcb-path-probe.test.mjs`；
- `.tmp_562a/`、`evidence/562a/`、`tasks/562a_connector_path_probe.md`。

禁触其他所有文件，包括 connector 其他测试、dist 生成物的手工编辑、package 版本、fixtures、真实设计。先 cp 备份 actions.ts 到 `.tmp_562a/backup/` 并记 SHA-256。零 Git 写、零 rm/unlink、零真机/daemon/EDA、零部署发布。

## 4. 实现合同

复用 `connectionParams` 与一次 `scanConnectionPads`（≤512），先 `requirePcbFocus`，保持精确 REF.PAD/唯一焊盘/非空同 net 的证据。action 只返回：

`page / readOnly / from / to / nodes / edges / seeds / frontier / coverage / unknown / ignored / errors`。

- 顶点：`{primitiveId,type,net,layer?}`，键为 `(type,primitiveId)`；net 仅筛选，不作 proof。
- 边：`{from,to,method,callIndex,hostOrder}`，每条能定位到具体 `getConnectedPrimitives(false)` 或 `getAdjacentPrimitives()`。
- `from/to` 保留 559 的端点解析与 direct 调用读数；`seeds` 是起点可展开节点，`frontier` 是预算/遍历结束未展开节点。
- **不返回 verdict/path/hopCount/viaCount/sharedIds，不调用 getEntireTrack，不写设计。**

分类：

1. Pad direct → Line 可作为 seed 边；Arc 目前一律 `unknown:arc-unverified`，只有以后真实样本解锁后才可 proof；Pad→Via 记 `unknown:pad-via-contact`，不得 seed。
2. Pad→对方 Pad 可记 `pad-direct-other-pad` 边；中间其他 Pad 记 `unknown:intermediate-pad-unsupported`。
3. Line/Via 可由对应管理器 `pcb_PrimitiveLine` / `pcb_PrimitiveVia`.get(id) 展开；Arc 不展开。取实例后复核 PrimitiveId/PrimitiveType/Net。
4. `getAdjacentPrimitives()` 的 Line/Via 候选加入有界遍历，Arc、中间 Pad 不加入；缺 ID/type/net、实例不符、非数组、absent/error 都是 unknown。缺 net 不得展开，其他 net 记 `ignored:other-net`。
5. Fill/Pour/Poured/PLANE 记 `ignored:pour-excluded`；Polyline/Region/未知类型记 `unknown:unsupported-adjacent-type`，不得掩盖。
6. 每个候选按 `(type,primitiveId)` 排序，邻接调用按确定顺序执行；hostOrder 保留原始返回位置。

固定预算：每次 direct/adjacent 回 64，最多 512 顶点、512 次邻接调用、2048 候选边、120000ms（每次宿主读取之间检查）。截断/超预算写 `unknown:budget-exhausted` 或更精确 code，frontier 与 coverage 如实；不得把它当完整遍历。action 不需要为了找路提前停止，它只采集。

## 5. 测试与验收

新 fake host 测试至少覆盖：

- 非 PCB 焦点零读取；两端只扫一次组件；无 verdict/path 等字段。
- 两端 direct + 两段 Line + Via 的双向邻接证据，callIndex/hostOrder 可追溯、重复运行确定。
- 单向邻接只保留单向证据，不由 Connector 判 proof。
- Pad↔Via、Arc、铺铜、Polyline、中间 Pad、缺 net、其他 net 各自分类正确。
- 非数组/方法缺失/抛错/ID或type不可读/管理器 get 错实例均披露且不展开。
- per-call >64 截断；顶点/调用/边预算至少一项用可复现夹具触发，frontier/unknown 正确。
- `getEntireTrack` 设陷阱并断言调用为零；全部调用无写动词；559 既有 `pcb-connection-probe.test.mjs` 不回归。

运行：

```bash
cd connector
node --test tests/pcb-path-probe.test.mjs tests/pcb-connection-probe.test.mjs tests/pcb-instance-probe.test.mjs
npm run typecheck
```

主代理随后跑 Connector 全量，并做至少两项变异（允许 Arc/缺 net 展开、吞掉预算或整个 Track 被调用）先红后 cp+SHA 恢复。子代理 ≤40 步/30 分钟，交卷 ≤2000 字，报告真实测试汇总和未覆盖项。

## 6. 兼容矩阵与交卷边界

- V4 fake：本批覆盖；V3 未覆盖，不得外推。
- 在线 action 结构：本批覆盖 fake；真机未做，归后续 562C。
- `.epro2/.eprj2/.eprj3`：本批不改 parser，未覆盖。
- 单板焦点：覆盖；多板不自动选择。重复 PCB 双审、分歧库串板均不得借本批宣称改变或验证。
- 普通 ComponentPad：覆盖；CBB 内部展开未覆盖。
- 559 direct-only 与 550 离线路径必须逐字不变。

状态只能是“工作树完成、未提交未推送、未真机激活”。证据写实际命令、计数、SHA 与未覆盖项，不能写通用宿主兼容。


## 7. 实际完成与父代理验收

- 新 action 仅追加图证据采集与注册，顶层为 `page/readOnly/from/to/nodes/edges/seeds/frontier/coverage/unknown/ignored/errors`，无 verdict/path；每边带 method/callIndex/hostOrder，Arc、Pad↔Via、缺 net、铺铜、预算均按合同分类。
- 主代理独立跑三文件 **52 passed / 0 failed**，typecheck 通过；Arc 早退变异 **11 passed / 1 failed**、预算披露变异 **11 passed / 1 failed**，均 cp+SHA 恢复并复绿。证据 `evidence/562a/path-probe-evidence.md`、`evidence/562a/parent-validation.md`。
- Connector 全量在 562B 注册 protocol 后为 **876 passed / 0 failed**；此前唯一红是预期的 `inRegistryOnly=['pcb.path_probe']`，已关闭。
- 状态：实现完成、未提交未推送、未做真机；V3/Arc/Pad↔Via/其他板型未覆盖，DSH 不做。
