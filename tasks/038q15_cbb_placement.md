# 038Q15：真实 CBB 的受控页内放置与记录回读

日期：2026-11-12。前置：038Q14 只读通路；真实样件已由岳新建，未经本批修改。

## 已核实的输入

- CBB：`晶振`，uuid=`e1534426e8710eee54c05f40826edc26bf1eecd6ca9eb35a0b324c431e2ae845`，
  libraryUuid=`08be6a96fc064a03b488fd9d5a25ccea`；`lib.cbb.get` 精确 found=true。
- CBB symbol：uuid=`c657f757a2cf294b`；在线 `sys.get_document_source` 与工程导出均证明
  `META.docType=17`、`Designator=CBB?`、140×140 外框，**没有 PIN**。
- `lib.cbb.export` 30s TIMEOUT，不盲重试；CBB 工程自己的 `sys.get_project_file` 成功，
  `.tmp_038q_native/crystal-project.epro2` 10825 bytes，SHA-256
  `ba4d300697ea8dc7333b5c31099ced460f28dbad35cb3407a046aaa9281636d0`。
- 原 CBB P1 没有块实例，也没有 PIN/WIRE/NET；所以本批只能证明真实块身份/空端口/放置形态，
  不能证明块端口网表或 N1–N3。分析：`.tmp_038q_native/crystal-record-analysis.md`。

## 范围与 shared 集成锁

新增唯一 `sch.place_cbb` write action，做库身份、活动工程/页、前后器件清单、真实
`getState_ComponentType() === 'block_symbol'`、CBB/CBB Symbol 身份、几何与端口清单回读。
`lib_Symbol.get` 对本样件 found=false；只有调用方显式 `allowUnverifiedSourceSymbol:true` 才允许
在这种已另获真实源文档证据的情况下尝试放置，结果必须标 `symbolVerification`。
任何放置后不符都返回 partial/verified=false 和 primitiveId，不冒称成功、不自动重放。

- 不改 parser/review/draw 算法、不改 `core/blocks.py`、不创建库样件、不写源 CBB。
- DSH 走通用 bridge，不新增工具、不 bump、不发布；零 git 写、零直删。
- 公开 action 必须同步 protocol、buildHandlers、docs/bridge、CLI 合同和测试。

## 真机边界与完成判据

唯一工程：`test V4`，projectUuid=`1ea6af15c2b1bd8132b46a0648d4e149ced21066c4a6650bbffd40dc5e286a5b`。
写前 `doc.list` 名称/UUID 全等；既有 P38–P42、Board2 P1 与 PCB 不写。用既有 `sch.doc.new`
新建一页，实际页名以宿主回读为准；页必须为空，所有写带该 pageUuid。

1. 在空页放置上述一个 CBB symbol；前后普通器件几何保持不变，器件总数恰 +1。
2. 回读真实 `block_symbol`、CBB/符号 uuid/libraryUuid、位姿和端口数组；空数组是实测，不能补造端口。
3. 保存后导出该页/工程 source 和 `.epro2`，分析真实实例记录、身份和 type；未取得记录前不写解析器。
4. 证据落 `.tmp_038q_native/`，脱敏结论可追加 `evidence/038q14/report.md`。探针页可用既有
   `doc.delete_page` 删除并回读；**岳的源 CBB 保留，不删除、不修改**。
5. 若放置失败，先回读页清单并保留 primitiveId/错误，不重建页、不重复写。

## 兼容矩阵 / negative control

| 维度 | 本批 | 不得外推 |
|---|---|---|
| V4 4.1.93 / test V4 | 一个空页、一个零端口 CBB | 不称 V3、其他版本或真实工程已验 |
| 在线 / `.epro2` | 在线状态+项目导出对照 | `lib.cbb.export` 超时不能写成已恢复 |
| 普通器件 | 前后几何逐项不变 | 不改普通器件审查读数 |
| CBB 端口 | 仅真实空数组 | N1 已接端口、N2/N3 规则仍未覆盖 |
| 多板 | 未覆盖 | 不改变重复 PCB/分歧库既有守卫 |

## 文件域与验收

- 新增 `connector/src/cbb-placement.ts`、`connector/tests/cbb-placement.test.mjs`；
  `connector/src/actions.ts` 仅 import/注册；`src/boardwise/bridge/protocol.py` 一个 Action；
  `tests/test_038q15_cbb_placement.py`、`docs/bridge.md`、`contracts/cli/v1.json` 正式生成器、本任务书。
- fake 覆盖身份/页守卫、零写负例、唯一新增、几何保持、block_symbol、库/符号绑定、空/非空端口、
  mismatch partial；真实 buildHandlers 入口。禁止运行直删 dist 的 build.mjs，使用无删除 esbuild。
- 聚焦 pytest `--basetemp=.tmp_pt_038q15`；至少两项变异（跳过 block_symbol 检查、跳过页身份/旧件保持）
  先红后 cp+SHA-256 恢复。shared 集成、全量和真机串行，最终读数如实记录。

## 实际结果（2026-11-12）

离线 action 与合同已实现：Connector 740 passed，Python 邻接 176 passed，两个变异均先红后恢复。
真机新建 P43 后，`createCbbSymbol` 返回 `40960b3e03c37c1e`，但组件清单、source 和主代理亲看的
渲染都没有块；动作正确报 partial/verified=false，没有重试。P43 已删除并回读不存在，源 CBB 保留。
当前只有零 PIN、`boards=[]` 的空壳，下一硬前提是宿主 UI 已真实放置、最好带至少一个 PIN 的块实例。
完整证据：`evidence/038q15/live-report.md`。
