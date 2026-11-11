# 038Q1：原生 CBB 只读搜索与身份核对

日期：2026-11-11。038Q 的第一个 shared/Connector 小批；不进入绘制算法、归档导出或个人库写入。

## 目标与集成锁

- owner：shared + Connector；本批只增加两个只读动作及其合同、测试、文档。
- `lib.cbb.search`：按关键词分页搜索原生复用模块；空字符串是合法的全量清点入口。
- `lib.cbb.get`：读取一个原生复用模块的身份和 `boards` 元数据。
- 默认库是官方 `lib_Cbb.search/get` 的系统库缺省值；显式 `libraryUuid` 才访问其他调用者指定的库。本批不枚举个人库、不导出任何模块。
- 禁止：`create/copy/modify/delete/openProjectInEditor/openSymbolInEditor`、原理图或 PCB 放置、`getCbbFileByCbbUuid`、任何真实工程写入。
- 不改绘制线文件、现有未提交改动、package/version、DSH、Rust、worktree 和生产 Connector；零 git 写、零删除。

## 公开合同

### `lib.cbb.search`

输入只允许：
- `query?: string`，默认 `""`，必须允许空关键词；其余字符串原样传给宿主，不替用户猜搜索词。
- `libraryUuid?: string`，省略时使用宿主系统库缺省值。
- `limit?: integer`，默认 20，范围 1..100。
- `page?: integer`，默认 1，必须 >=1。

调用 `eda.lib_Cbb.search(query, libraryUuid, undefined, limit, page)`；省略 `libraryUuid` 时传 `undefined`，不能编造 UUID。

成功返回：`{query, libraryUuid, limit, page, count, items, source:"lib_Cbb.search", apiStatus:"beta"}`。
`libraryUuid` 未指定时返回 `null`。`count` 只表示本页数量，绝不命名为全库 total。

宿主必须返回数组，且数量不得超过 limit。每一项必须含非空字符串 `uuid`、字符串 `name`。
搜索返回的每一项还要经 `lib_Cbb.get` 核对：
- `get` 必须找到同一 uuid；
- `get` 返回非空 `libraryUuid`；
- 若调用方显式给库，两个来源的库 UUID 必须一致；
- 若 search item 自带 `libraryUuid`，与 `get` 不一致必须报错；
- 返回项保留公开搜索元数据，并补 `libraryUuid`、`libraryIdentitySource:"lib_Cbb.get"`。

### `lib.cbb.get`

输入只允许必填非空 `uuid` 与可选 `libraryUuid`。不得自动打开模块工程。
返回 `{uuid, libraryUuid, found, cbb, source:"lib_Cbb.get", apiStatus:"beta"}`。
`cbb` 是宿主公开元数据，含原始 `boards` 数组；找到时 `found=true`，否则 `found=false, cbb=null`。
找到时必须验证 `cbb.uuid` 与请求一致、`libraryUuid` 非空且与显式请求一致、`boards` 是数组。

### 失败与兼容

- namespace/method 缺失：`NOT_IMPLEMENTED`，指出准确路径。
- 参数非法：`BAD_REQUEST`，不得把非法参数改写成默认搜索。
- 宿主抛错：结构化 `CONNECTOR_ERROR`，保留安全错误摘要。
- 非数组搜索响应、畸形条目、身份矛盾、缺 boards：`CONNECTOR_ERROR`，不得伪装成空库。
- 两个动作在 daemon 目录均为 `risk="read"`；`bridge call --read-only` 必须允许，不新增确认旁路。
- 不把 `sys.probe` 的 function 存在当作搜索成功；真实分页、空库与分页参数行为仍须另做只读真机核验。

## 允许文件域

- 新增 `connector/src/library-cbb.ts`、`connector/tests/library-cbb.test.mjs`。
- `connector/src/actions.ts`：只 import 与注册两个 handler；不放进 `PROBE_CALL_ACTIONS`。
- `src/boardwise/bridge/protocol.py`：只增加两个 Action 条目。
- 新增 `tests/test_038q1_cbb_readonly.py`，覆盖目录风险、参数和只读合同。
- `docs/bridge.md`：在现有 library action 表补两个条目，写明单页计数与系统库缺省。
- 本任务书；必要时 `tasks/TASKMAP.md` 只更新 038Q 行，其他行不动。

## 验收

- 空关键词与分页参数精确保留；非法 limit/page、未知参数拒绝。
- 搜索正常、空数组、缺方法、宿主异常、非数组、缺字段、search/get 身份冲突、未找到均有测试。
- 测试通过真实 `buildHandlers()` 入口，不只测一个脱离注册的辅助函数。
- `npm run typecheck`；聚焦 Node 测试；聚焦 pytest（`--basetemp=.tmp_pt_038q1`）。
- **禁止直接运行会删除 dist 的 `connector/build.mjs` / `npm test` / `npm run build`**。本机删除纪律要求回收站，故用 esbuild 直接生成测试 ESM，不先删除旧 dist；产物是 ignored 生成物，不改源码。
- 主代理审查 diff、独立复跑、核对未提交文件边界后，再决定是否申请候选 Connector 的真机部署。没有部署就不声称已得到官方库真实总数。

## 当前验收（主代理，2026-11-11）

- 聚焦 pytest：33 passed（`tests/test_038q1_cbb_readonly.py` + `tests/test_action_catalogue.py`）。
- Connector：634 passed；typecheck 通过。`npm test` 因 build.mjs 的直接删除行为未运行，使用 esbuild 无删除构建后执行同一 Node 测试集。
- DSH：137 passed / 1 skipped，typecheck/build 通过。DSH 的 `boardwise_bridge` 是通用只读 action 通道，无需新增工具或 bump。
- Rust：111 passed / 4 ignored，fmt/clippy/test 通过；本批无 Rust 业务变化。
- 变异①默认 limit 20→10：默认参数用例如期失败；变异②删除 search/get 库身份冲突检查：冲突用例如期失败。两次均 cp 恢复，源码 SHA-256 均为 `430e0bb821114bbed84191cd79019d1fa651a5c0a16fe5f38980b761aa495035`。
- 候选 bundle：`.tmp_038q1/connector-index.js`，SHA-256 `a684223f48b8a8d7a5f4052bb9aab5519c7dae1d3835d330f8177aacc5d3a9d3`；经岳批准后仅热更 `test V4` 完成真机清点，随后已回滚。
- 第一轮完整 pytest：**10645 passed / 25 skipped / 1 xfailed / 20 failed**，日志 `.tmp_038q1/full-pytest.log`（UTF-8 转换副本同目录）。其中 16 条为已登记货架数据、098 基线和 Windows 环境失败；新增 4 条均为 `contracts/cli/v1.json` 未吸收两个新 action 的说明。结构化差分证明 argparse 参数树完全不变，仅 bridge `epilog` 增加 `lib.cbb.search/get` 两行并相应重排 help；已用 `python -m tools.cli_contract --write` 正式生成，修正后聚焦合同与 CBB 测试 **76 passed**。未手改快照、未改既有 16 条基线。
- 第二轮完整 pytest：**10649 passed / 25 skipped / 1 xfailed / 16 failed / 1 warning**，日志 `.tmp_038q1/full-pytest-r2.log`（UTF-8 转换副本同目录）。与第一轮逐项集合比较，消失的恰为已修的 4 条 CLI 合同失败，**added=[]**；剩余 16 条全部为既有货架数据、098 基线和 Windows 环境失败。不是全量全绿，但本批新增失败为 0；不再做第三轮常规全量。
- **真机清点（2026-11-11，EDA 4.1.93）**：系统库缺省与显式已知系统库 UUID 的空关键词搜索均返回 **0 条**，原始响应与部署证据在 `outputs/review/038q1/`。结论只限当前账号/工作区/宿主；未读取个人库、团队库或其他工作区，不外推全站总量。空页使真实 get/boards 仍未覆盖，不宣称原生 CBB 全兼容。
- 已恢复正式 daemon 0.6.1（exe 哈希与 Release 一致）及 `test V4` Connector 0.6.0，三窗在线、配对指纹不变、目标工程 P41 回读一致。候选 daemon 已停止，正式 daemon 保持运行；没有写真实工程。详见 `outputs/review/038q1/ACCEPTANCE.md`。

## 下一批

固定上游 `easyeda-agent@69af00c0db3960757bff36a68edb286adcd64458` 的公共数据，做许可证/manifest 和 Rust 归一化，首批只取 AMS1117、SY8089、CH340C 三个候选。该批与本批分开，不能夹进此 Connector 小批。设计任务书：`tasks/038q2_upstream_module_seed.md`。
