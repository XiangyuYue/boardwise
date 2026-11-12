# 038Q6：AMS1117 封装文件的受控只读通路

日期：2026-11-12。接续 038Q5。本批只增加 `lib.footprint_file.get` 并完成离线验收；
不解析封装容器、不展开 `U.VOUT*`、不改模块候选状态。真实读取需另获本次部署批准。

## 已测事实与目标

- AMS1117/C6186 的 footprint UUID 为 `20c29e37a9b84b4197418483096f9c05`，系统库为
  `0819f05c4eef4c71ace90d822a990e87`；既有 `lib.footprint.get` 只返回名称
  `SOT-223-3_L6.5-W3.4-P2.30-LS7.0-BR` 等元数据，没有 PAD 几何。
- EDA 4.1.93 的正式 Connector 0.6.0 上，`sys.probe` 实测
  `eda.sys_FileManager.getFootprintFileByFootprintUuid` 为 function、arity=3。
  证据：`outputs/review/038q6/footprint-file-api-probe-v2.json`。首次错误形状的 probe 保留，
  不冒充成功；正确形式是 `checks: {sys_FileManager: [method]}`。
- 目标是按明确 footprint UUID 读取一个完整文件，供下一批观察真实容器与 PAD 记录。
  本批仍不声称宿主一定会返回文件，也不猜 manifest 名称、docType、成员后缀或 PAD 编号。

## 最小动作合同

`lib.footprint_file.get`，connector-owned、`risk=read`：

- 参数闭集只有 `uuid/libraryUuid/fileType`；`uuid` 为单个非空字符串，数组拒绝且不扇出。
- `libraryUuid` 省略时原样传 `undefined`，空串拒绝；`fileType` 必填，仅 `elibz2|elibz`。
- 调用 `eda.sys_FileManager.getFootprintFileByFootprintUuid(uuid, libraryUuid, fileType)`。
- 返回 `{uuid,libraryUuid,fileType,source,apiStatus:'beta',encoding:'base64',name,mime,bytes,data,isZip}`。
  `isZip` 只描述文件头，文件名和请求 uuid 都不是容器身份证据；本批不解包。
- 方法缺失为 `NOT_IMPLEMENTED`；throw/undefined/null/零字节为 `CONNECTOR_ERROR`，
  带宿主原文和 `团队库 > 下载库` gate。不得把权限猜测写成事实。
- 不加入 `PROBE_CALL_ACTIONS`，不改旧 archive 权限数组，不增加写动作或任何画布行为。

## 实现约束

- `connector/src/actions.ts`：提取一个受配置约束的内部 library-file 读取实现，让现有
  `lib.symbol_file.get` 与新动作共享参数校验、超时、失败和完整字节读取；两个公开动作各自
  固定 action/path/gate/noun。不得复制第二套 100+ 行失败处理，也不得改变 Q3 的可观察行为。
- `src/boardwise/bridge/protocol.py`：只加新 Action；旧 symbol/device/footprint 条目不变。
- `docs/bridge.md`：登记动作和未测边界；`contracts/cli/v1.json` 只能用正式生成器更新。
- 新增 `connector/tests/library-footprint-file.test.mjs` 与
  `tests/test_038q6_footprint_file_read.py`；Q3 测试原样通过是共享实现的负对照。
- 本任务书及 `outputs/review/038q6/`、`.tmp_038q6/`；不改 parser/Rust/DSH/绘制/catalog。

## 验收与 negative control

1. 通过真实 `buildHandlers()` 验证成功、省略 library、非法参数、数组 uuid、空 library、
   缺/错 fileType、未知参数、方法缺失、throw、undefined/null、零字节和参数顺序。
2. 旧 `lib.symbol_file.get` 的完整测试不放宽；旧 `lib.footprint.get` 合同不变。
3. Connector 全测试 + typecheck，使用既有无删除 esbuild 构建；Python 聚焦 Q3/Q6、
   action catalogue、CLI 合同与只读邻域，独立 `--basetemp=.tmp_pt_038q6`。
4. 至少两处变异并恢复：参数顺序/身份校验、fileType 白名单或完整字节拒绝。cp+SHA-256
   恢复，不用 git 恢复，不直接删除任何文件。
5. 零部署、零真机写、零 git 写。离线通过后，真实文件读取必须另获岳明确批准本次 daemon
   重启和仅 `test V4` 热更；038Q5 的批准不沿用。

## 后续严格分界

- 下一批先只读观察容器，再决定单 footprint reader；PAD `id/num/layer/geometry` 的真实含义
  以文件为准。找不到 PAD 4 是证据，不得用 3D 模型名或封装标题补猜。
- 即使 PAD 2 与 PAD 4 都存在，也只证明两个独立焊盘及编号映射，**不证明器件内部同网**。
  `U.2/U.4` 的电气并联还需要 datasheet 的 VOUT/tab 说明和页码证据，另批裁定。
- 本批完成不等于 AMS 模块可绘制，不解除 `candidate/unverified/notForDrawCompile`。

## 实施记录（子代理 2026-11-12）

### 实际改动

- `connector/src/actions.ts`：把 038Q3 的 `libSymbolFileGet` 主体 1:1 提取为
  `async function readLibraryFile(action, spec, params, eda)`；新增
  `type LibraryFileRead = {path, gate, noun}` 与 `SYMBOL_FILE_READ` /
  `FOOTPRINT_FILE_READ` 两份配置（path/gate/noun 固定）。两公开动作各一行委托，
  失败处理只有一套（`libraryFileFailure(spec, error)` 取代 `symbolFileFailure`）。
  `LIBRARY_SYMBOL_FILE_*` 常量合并为 `LIBRARY_FILE_TYPES/KEYS/TIMEOUT_MS`（值不变）。
  新增 `lib.footprint_file.get` 注册。`file` 变量由 `any` 改 `unknown`（无新增 any）。
  Q3 文案逐字保留：`one symbol per call, never a batch`、`an absent file is not an
  empty symbol and nothing was read` 均由 `spec.noun` 拼出，symbol 结果不变。
- `src/boardwise/bridge/protocol.py`：只新增 `lib.footprint_file.get` 一条 Action
  （无 `confirm`，risk=read，params 闭集 uuid/libraryUuid/fileType），旧
  symbol/device/footprint 条目一字未改。
- `docs/bridge.md`：§4 表新增一行（含 gate、未测边界：方法"present≠working"、
  不解包、不猜 manifest/docType/成员后缀/PAD 编号、不证 PAD 4、不做电气推断）。
- `contracts/cli/v1.json`：仅 `.venv/Scripts/python.exe -m tools.cli_contract --write`
  正式生成（`epilog`/`help` 两处）。
- 新增 `connector/tests/library-footprint-file.test.mjs`（31 例）、
  `tests/test_038q6_footprint_file_read.py`（12 例）。
- 未触碰：`PROBE_CALL_ACTIONS`、025 archive 两个 gate 数组、parser/Rust/DSH/绘制/
  catalog；无 git 写、无删除、无 bridge/daemon/Connector 部署、无真机。

### 测试读数

- `node ../.tmp_038q3/build-connector.mjs`（无删除构建）→ `node --test "tests/**/*.test.mjs"`
  → **691 passed / 0 failed**（含 Q3 原 26 例与 contract-drift）；`npx tsc --noEmit` → 0 错。
- 聚焦 pytest（`--basetemp=.tmp_pt_038q6`）：Q3+Q6+catalogue+537a+540c = **97 passed**；
  另跑 Q3+Q6+038q1+537a+540c = 106 passed；`test_bridge_cli`+`test_doc_claims`+
  `test_069d_doc_claims` = 110 passed。未跑全量。
- `tools.cli_contract`（无 --write）→ `CLI contract matches production`。

### 变异证据（cp 备份 + SHA-256 还原，备份留 `.tmp_038q6/`）

基线 `connector/src/actions.ts` = `f60bf040…e0ce6008`，备份 `.tmp_038q6/actions.ts.final-baseline`。

| # | 变异 | 结果 |
|---|---|---|
| 1 | 参数顺序 `call(uuid, fileType, libraryUuid)` | 红：57 例中 7 失败（三参数顺序、explicit library、两 fileType、Q3 顺序各一）→ `.tmp_038q6/mutation-1-arg-order.log` |
| 2 | 身份：`FOOTPRINT_FILE_READ.path` 改回 symbol 方法 | 红：31 例中 12 失败（source、path、gate、zero/undefined/arrayBuffer 全部）→ `mutation-2-path-identity.log` |
| 3 | fileType 白名单只剩 `elibz2` | 红：57 例中 4 失败（两 fileType、无 type 回退）→ `mutation-3-filetype.log` |
| 4 | 零字节不再拒绝（`if (false && …)`） | 红：31 例中 1 失败（zero-byte）→ `mutation-4-zero-bytes.log` |

每次 `cp` 还原后 `sha256sum -c .tmp_038q6/final-baseline.sha256` → OK，复跑 57/57 与
691/691 全绿。

### 最终关键文件 SHA256

- `connector/src/actions.ts` `f60bf040e1c3ba272339480bce1b76a2bbe4379a5c7cf49722eaf027e0ce6008`
- `src/boardwise/bridge/protocol.py` `0da8d573a94e5cc22da811c5d74f2740540214bc4ceb709926642a54b206bc9d`
- `docs/bridge.md` `bd5c09cca4d2a362d66f45759a67c879329bfb1c4f003eade1d3ff6e01ed2556`
- `contracts/cli/v1.json` `34fb64fea3b760e1d19d52fce61b263590e888d539645b09118ad7c266061c87`
- `connector/tests/library-footprint-file.test.mjs` `dae8677ec8ddb8a65572f2ee57a2df1b1fefabc7c92a2085738191e4cf0cd5c0`
- `tests/test_038q6_footprint_file_read.py` `371234e136ab93680f85de94c6593cbc0371c515c2fdfe86f12e89001f451f4b`

### 未测边界（本批刻意不声称）

- 真实 footprint 文件**未读取**：无 daemon 重启、无连接器热更、无真机调用；宿主是否
  真会导出该文件、返回的 `File` 形状、字节内容全部未测。
- PAD 4 / PAD 2 是否存在、编号映射、`U.2`/`U.4` 是否同网：**零证据**，需真实文件与
  datasheet 另批裁定。
- `isZip` 仅前两字节观测；elibz/elibz2 容器语法未解析；name/docType/成员后缀未猜。
- 失败文案里的 gate 仍只是类型包记载，不是对宿主授权的实测诊断。

## 真机读取与证据裁定（主代理，2026-11-12）

- 岳已明确批准本次部署。候选 bundle SHA-256
  `ba78d505cb1a38c049204699e101a21a1f4fd71de94699eda4576876a6491b34`，仅 `test V4`
  热更并 verified；新实例经 `doc.list` 确认 P41 后完成一次只读封装文件调用。
- 真实 archive SHA-256 `bd42e3f89b49d4810879cfb9ae7fb4b950a9cbd3d9ffa09d7ebf0359e74a9a94`。
  manifest 实测为 `footprint2.json`、docType=4、footprint UUID/library 均匹配；stream 为
  `.elibu`，两个相同 FOOTPRINT DOCHEAD 续段。容器/成员/CRC 与身份检查通过。
- 共 4 个 PAD，编号恰为 1/2/3/4，无重复。PAD 4 唯一，record id=e11、layerId=1、RECT
  92.126×141.732、relativeAngle=90、plated=true、无孔。原始值不换算；单位观察与负证据见
  `outputs/review/038q6/ams1117-footprint.pads.json`。主代理两次观察脚本输出及哈希一致。
- 指定 datasheet 共 8 页，SHA-256
  `189a2651878a87d590b768eaa9b44217a3fdf460352ce6ecaff127221282a3f0`。主代理渲染并亲看
  第 1 页：SOT-223 图只有 1/2/3，tab 无电气注记；`TAB IS OUTPUT` 位于 TO-252 图。
  文本坐标与视觉结论一致。现有手册只支持 U.2=VOUT，**不能证明 PAD 2/4 内部同网**。
- 裁定：`U.VOUT*` **保持未展开**。PAD 4 存在已证实，但内部同网是未证实而非证伪；
  不修改 catalog、生成器或 notForDrawCompile，不用其他封装/经验代替证据。后续需厂商明确
  SOT-223 tab 电气关系的资料，另批评审。
- 正式 Connector 0.6.0 回滚 verified；当前目标实例 `inst-001424639-oblrokor`，三窗均 0.6.0、
  配对指纹 `8b82a227`、P41 一致。listener 为正式 `.tmp_038q1/rollback/v061/boardwise.exe`，
  daemon 任务 `bash-2v4xkz6o` 保持运行。零工程写入，未跑全量、未提交。
- 完整证据：`outputs/review/038q6/ACCEPTANCE.md`、`ams1117-vout-evidence.json`、
  `ams1117-datasheet-p1-1.png`、`final-bridge-status.txt`。
