# 038Q16：项目内原生 CBB 的搜索与放置

日期：2026-11-15。前置：038Q14/Q15。真实样件已经导入 `test V4`，但不是 `cbb_project`。

## 新实证

- `lib_Symbol.get(ca89fed3a434c5cb, 'project')`：found=true，`name=晶振`、`libraryType='2'`、
  `type=17`；它是工程内本地符号，源符号为 `c657f757a2cf294b`，源 CBB 工程为
  `e1534426e8710eee54c05f40826edc26bf1eecd6ca9eb35a0b324c431e2ae845`。
- `lib_Cbb.search('', 'project')` 能返回本地 `ca89…`，但现有 `lib.cbb.search` 再用
  `lib_Cbb.get(ca89…, 'project')` 核对时被拒，合法项目结果被误报 CONNECTOR_ERROR。
- 全工程 `.epro2`：`.tmp_038q_native/test-v4-cbb-project.epro2`，SHA-256
  `8ad4558f5b1c604adb39fbbf6e7bd87ca7d3098c609a2ae590dc78caf6e4149e`。
  `cbb_project:false`，导入块文档的 `META.source='<源文档uuid>|<源CBB工程uuid>'`，**没有真实块实例**；
  符号仍 0 PIN。P43/P44 是普通器件页，P45 只有图框，全部不写。
- 详细证据：`.tmp_038q_native/live-block-record-analysis.md`。

## A：项目作用域搜索修正（shared + Connector 单独小批）

`libraryUuid === 'project'` 时，不再用 `lib_Cbb.get` 核本地条目；逐项改用
`lib_Symbol.get(entry.uuid, 'project')`，要求 uuid 一致、name 为字符串、`type===17`、
`libraryType==='2'`。源库 UUID 原样保留为 `sourceLibraryUuid`，不得拿它替代调用方的 `project` 作用域。
返回 `libraryUuid:'project'`、`libraryIdentitySource:'lib_Symbol.get(project)'`，错误/缺失/矛盾仍拒绝，
不放宽普通库 `lib_Cbb.get` 的硬核对。非 project 调用必须逐字节保持旧行为。

允许：`connector/src/library-cbb.ts`、对应测试、`tests/test_038q16_project_cbb.py`、
`src/boardwise/bridge/protocol.py` 的项目作用域说明、`docs/bridge.md`、CLI 合同生成器、本任务书。

## B：项目内块放置（另一个小批）

新增 `sch.place_project_cbb` write action，参数闭集：
`schematicUuid, expectedName, symbolUuid, projectUuid, pageUuid, x, y, rotation, mirror`。

1. `dmt_Schematic.getSchematicInfo(schematicUuid)` 必须核到同一工程、`itemType='CBB Schematic'`、
   名称和 `cbbSymbol.type===17`；保留 graph 的源符号/CBB 身份。
2. 复用修正后的 `libCbbSearch(expectedName,'project')`，按本地 uuid + `lib_Symbol.get(project)`
   的权威显示名唯一解析 `expectedName`；请求 `symbolUuid` 必须等于本地 uuid。不得按搜索行名称猜。
3. 项目/活动页逐字守卫，页必须 `documentType=1`；前后组件清单完整且旧件几何不变。
4. 走上游项目内路径 `sch_PrimitiveComponent.create({libraryType:'2',libraryUuid:projectUuid,
   uuid:symbolUuid}, x, y, '', 0, false, true, true)`；rotation/mirror 本批固定 0/false，
   不另猜通用姿态 API。回读总数恰 +1、真实 `block_symbol`、`getState_Symbol().uuid===symbolUuid`、
   位姿与端口数组。空端口是实测；任何不符 partial/verified=false，保留 primitiveId，不盲重试。
5. timeout 使用 PLACEMENT_TIMEOUT；protocol/buildHandlers/docs/CLI 合同同步。DSH 通用 bridge，无 bump。

允许：新增 `connector/src/project-cbb-placement.ts` 与测试；actions 注册；protocol 一个 Action/timeout；
`tests/test_038q16_project_cbb.py`；docs/CLI 合同/本任务书。不得改绘制线/parser/review。

## 真机与 negative control

只写 `test V4`（uuid=`1ea6af15c2b1bd8132b46a0648d4e149ced21066c4a6650bbffd40dc5e286a5b`）。
现有 P43/P44/P45、模块 P1、Board2 P1 与 PCB 全部不写；另建一个新探针页，实际名称以 doc.list 为准。
成功必须同时有：项目内搜索成功、真实 `block_symbol`、唯一本地 symbol 身份、端口数组、旧件不变、
source/项目导出与渲染证据。探针页删除并回读；导入的模块文档保留。

普通器件几何与记录不变；非 project 搜索 fake 读数不变。零 PIN 样件仍不覆盖 N1–N3、真实块网络、
V3、多块嵌套或 `lib.cbb.export` 成功。至少两变异（project 身份核对、block_symbol/页守卫）先红后恢复。

## 实际结果（2026-11-15）

A/B 均已落地并真机验证。project 搜索真机返回 ca89…，普通库 checkedCbb 不变；P46 的项目内放置
返回真实 block_symbol、local Symbol、空端口、preserved=true、verified=true。保存后 source/项目导出、
在线 geometry 和主代理视觉均对齐。P46 与误建于模块图纸的空 P2 已分别回收，导入模块与其他页保留。
Connector 774 passed；主代理恢复 Q15 被覆盖的 params_schema 后聚焦 112 passed。
038Q17 继续完成实例三锚解析与普通读数不变证明。完整证据：`evidence/038q16/live-report.md`。
当前只剩非空真实块端口及 N1–N3 未开闸，不能称完整 CBB 电气兼容。
