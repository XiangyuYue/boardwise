# 038Q14：原生 block_symbol 样件引导与首条闭环

日期：2026-11-12。岳授权主代理自定目标并完成；daemon 可重启。目标是在不碰绘制线的前提下，
取得真实原生块证据并完成只读识别、受控放置回读和块端口审查；不把上游 fake 测试当本机证据。

## 上游调查对 038Q 顺序的修正

固定上游 `easyeda-agent@69af00c0db3960757bff36a68edb286adcd64458` 没有真实 CBB
样件，也没有真机验收文件；`cbb-author.test.ts` 是 fake eda。系统库空搜索为 0 不能证明官方库无 CBB，
上游也没有一个可借用的官方样件名。因此本批新增 **A0 样件引导**：只在岳的个人库创建一个受管最小样件，
立即用库只读和归档回读，再进入 038Q 的 A/B。它不是跳过先读后写：每次写都有写前身份与写后真实回读。
若个人库已有真实样件，优先只读，不创建。

个人库样件名固定 `BOARDWISE__NATIVE_PROBE_V1`；同名已存在时不覆盖，先读取核对，不能证明归本批所有就停止。
宿主个人库资产的生命周期删除只走正式受控 action，逐身份回读；这不是本地文件删除，不宣称宿主提供回收站。
本地文件和目录仍全部遵守回收站红线，禁止 `rm` / `rm -rf` / `unlink` 等直删。

## 分批与 shared 集成锁

owner=shared + Connector，随后才是 parser 和 review 各自独立小批。工作期间不改
`engines/drawcompiler.py`、`engines/placement.py`、`tasks/548*` 或任何绘制算法；不使用 worktree 写操作。
公开动作必须进 daemon 目录、Connector `buildHandlers()`、文档、CLI 合同与测试；DSH 继续走通用 bridge，
不新增 DSH 工具、不 bump、不发布。

1. **Q14a 只读库通路**：`lib.cbb.personal` 读取 `lib_LibrariesList.getPersonalLibraryUuid()`；
   `lib.cbb.libraries` 只读 `getAllLibrariesList()`，逐项核对非空 uuid、字符串 name 与 uuid 唯一性，
   不把其他库当个人库；`lib.cbb.export` 在 `lib.cbb.get` 身份核对后调用
   `sys_FileManager.getCbbFileByCbbUuid(uuid, libraryUuid, {fileName: <get 返回的模块名>, fileType:'epro2'})`。
   声明（`@jlceda/pro-api-types` index.d.ts:17087）写明 `fileName` 即**复用模块名**，故一律传 `get` 读回的
   `name` 原文，不得硬编码固定文件名；`name` 缺失或空白时 `CONNECTOR_ERROR` 且**不调用** file API。
   `personal` 的 `undefined`/`null` 只说明**当前 workspace/session 未解析到 personal library UUID**
   （`detail.reason='personal-library-unresolved'`）；类型声明只说私有部署恒 undefined，不能据此诊断本次原因，
   也不是空库证据——真机公开版的 undefined 不得写成"已证实私有部署"。
   归档必须非空、不超过 16 MiB，完整 base64 返回， Connector 不解包、不猜内部格式。
   三个动作 risk=read；export 必须显式 uuid/libraryUuid，不写工程、不打开模块工程。
2. **Q14b 受控样件与归档**：个人库没有可用样件时，另写最小创建/符号构建合同与 fake 测试。
   先回读个人库身份与目标不存在，再创建；创建后 get 必须精确匹配 uuid/libraryUuid/name。
   导出归档落 `.tmp_038q_native/`，长期脱敏证据落 `evidence/038q14/`；真实容器永不入库。
3. **Q14c 容器只读识别**：只有拿到真实记录后才实现解析。逐条对照普通器件、分页、库文档与在线身份；
   `type 17` 仍只是上游 API 读值线索，未逐字节证实前不得写成容器事实。读不出要显式 unknown，不降级普通器件。
4. **Q14d 页内受控放置**：只写 `test V4`，项目 uuid=`1ea6af15c2b1bd8132b46a0648d4e149ced21066c4a6650bbffd40dc5e286a5b`。
   新建独立探针页，原 P41=`037f5a63d7825dfe` 与既有页/板不写。写前 `doc.list` 工程名必须逐字为 `test V4`，
   新页必须空；放置后同时核对 `getState_ComponentType() === 'block_symbol'`、符号/CBB 身份、端口和原页几何不变。
   结束删除探针页与受管个人库样件并回读；页面/库资产异常不得伪称已清。部署只热更 `test V4`，其他窗口不动。
5. **Q14e 审查规则另批**：N1 已接块端口在展开网表缺席时不误报；N2 普通器件真悬空仍报；
   N3 不含 CBB 的对照输入 findings 逐字不变。通过既有 unproven 通道披露证据不足，不全局豁免、不改 verdict/exit code。

## 兼容矩阵与 negative control

| 维度 | 本批覆盖 | 不得外推 |
|---|---|---|
| V4 4.1.93 / `test V4` | 在线只读、受控样件、独立空页、归档 | 不称 V3、4.1.94+ 或其他工程已验 |
| `.epro2` / `.eprj3` | 按真实取得的样本逐项记录 | 没有样本的容器写未覆盖；`.eprj2` 壳不冒充设计数据 |
| 单/多板 | 仅当前原理图页与所属样件 | 重复 PCB 双审、分歧库串板均不因本批改变或已验 |
| 普通器件 / CBB | 原页只读基线、普通器件负例、真实块 | 不用 fake type=17 证明容器兼容 |
| 审查 | N1/N2/N3 分开对拍 | 不用静默无 finding 代替端口证据 |

## 文件域与验收

- Q14a 允许：`connector/src/library-cbb.ts`、`connector/tests/library-cbb.test.mjs`、
  `connector/src/actions.ts` 的 import/注册、`src/boardwise/bridge/protocol.py` 三个 Action、
  `tests/test_038q14_cbb_native.py`、`tests/test_action_catalogue.py` 的 CBB 只读命名例外、
  `docs/bridge.md` 对应表项、`contracts/cli/v1.json` 由工具生成、本任务书。
- Connector 禁止运行会直接删除 dist 的 `build.mjs` / `npm test` / `npm run build`；用 esbuild 无删除输出。
- 聚焦 pytest 必须 `--basetemp=.tmp_pt_038q14`；开发期不跑全量。至少两次变异（cp + SHA-256 恢复），
  覆盖库身份核对和归档缺失/身份不符；真实读数与失败原文分开保存。
- 任何写库/写页前先完成对应只读部署、身份回读和 fake 负例；任何宿主前提失败即保留可复现探针与边界，
  不写成 CBB 兼容。零 git 写、零 push、零发布、零真实工程写。

## 实际结果（2026-11-12）

Q14a 三个只读动作及合同/测试已实现，Q14b–e 因真实样件前提不成立而停闸：个人库 UUID 未解析，
系统库非空关键词、当前工程库及两个其他可读库均返回 0 个 CBB。没有调用归档导出，没有创建库样件或页面，
没有解析记录或修改审查规则，type 17 仍未证实。挖洞修正了归档模块名和 undefined 归因，四组变异均先红后恢复。

Q14 聚焦 94 passed；Connector 720 passed + typecheck；DSH 137 passed / 1 skipped + typecheck/build；
Rust 177 passed / 4 ignored + fmt/clippy。全量 Python 10902 passed / 26 skipped / 1 xfailed / 1 failed，
唯一红项为绘制线未提交的 548D forced-topology，不由本批修复，不称全量全绿。
原始读数、恢复边界与日志索引见 `evidence/038q14/report.md`。
