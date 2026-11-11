# 038Q3：库符号文件的受控只读通路

日期：2026-11-11。038Q1/Q2 后的 shared + Connector 小批；本批只解决「按明确库 UUID 读取一个符号文件」，不解包、不生成 profile、不进入绘制。

## 已测事实与目标

- 当前宿主 EDA 4.1.93，焦点工程逐字为 `test V4`，活动页 P41=`037f5a63d7825dfe`；正式 daemon 0.6.1、Connector 0.6.0。
- `lib.device.get` 已读回 AMS1117-3.3 / C6186：device=`9f9c6cb41c7449fd8acf96aceed2661a`，library=`0819f05c4eef4c71ace90d822a990e87`，symbol=`06f50e10ab7d460599b3fe3ee8717a78`。
- 当前 `lib.symbol.get` 实读只有名称、UUID、分类和 otherProperty，**没有引脚或 body 几何**。旧接口保持这一元数据合同，不往其中塞文件字节。
- `sys.probe` 实读 `sys_FileManager.getSymbolFileBySymbolUuid` 为 function，arity=3。存在不等于导出成功；权限、返回 File 和容器格式仍未测。
- 类型包 `index.d.ts:17063` 声明 `(symbolUuid, libraryUuid?, fileType?: 'elibz'|'elibz2') => Promise<File|undefined>`，`@beta`，文档门槛是「团队库 > 下载库」。

## 公开合同：`lib.symbol_file.get`

只允许以下参数，未知参数在任何宿主调用前拒绝：

- `uuid`：必填，**单个**非空字符串；数组、对象、空字符串拒绝。不允许批量 UUID。
- `libraryUuid`：可选，非空字符串；省略时传宿主的 `undefined`，使用宿主系统库缺省；空字符串不静默变成系统库。
- `fileType`：**必填**，只接受 `elibz2` 或 `elibz`。本批不假定宿主的缺省格式，也不要求调用方先猜容器内容。

调用形状固定为：

```ts
getSymbolFileBySymbolUuid(uuid, libraryUuidOrUndefined, fileType)
```

成功返回：

```text
{uuid, libraryUuid, fileType,
 source: 'sys_FileManager.getSymbolFileBySymbolUuid', apiStatus: 'beta',
 encoding: 'base64', name, mime, bytes, data, isZip}
```

- 复用既有 `hostFilePayload` 的 arrayBuffer、非零字节、文件名去路径分隔符、base64、MIME 和 PK 观测。`isZip` 只描述文件头，不断言 elibz2 的内部格式。
- File 的 filename/type 不是符号身份证明；本批不从文件名猜 UUID，不把请求 UUID 回显当作容器内身份核对。后者必须等解包后完成。
- 字节必须完整，禁止截断 base64 后伪装成功。沿用既有文件动作的传输限制，不新加分片或扩容。
- namespace/method 不存在或 getter 抛错：`NOT_IMPLEMENTED`，带准确 path。
- 宿主抛错：结构化 `CONNECTOR_ERROR`，保留宿主安全错误摘要，并标注文档门槛「团队库 > 下载库」；不能从 throw 断言用户实际缺哪项权限。
- 宿主返回 undefined/null：`CONNECTOR_ERROR`，不当作空符号；零字节也失败。
- 固定 30 s 超时，复用 `raceHostCall`；本批不扩 timeout 参数。
- daemon 目录 `owner=connector`、`risk=read`，`bridge call --read-only` 允许；不加入 `PROBE_CALL_ACTIONS`，不提供通用 JS/任意路径执行。
- 禁止 `importProject*`、`setDocumentSource`、符号/器件/CBB 创建修改删除、画布放置、工程切换与保存。读文件不等于授权打开或落图。

实现可复用 `actions.ts` 已有的 `requireFn`、`raceHostCall`、`hostFilePayload`、`fileReadFailure`。若增加下载库权限提示，只对该新动作追加；旧 `sys.get_document_file/project_file` 的 `detail.permissions`、错误文案和返回形状必须保持不变。不得为此批搬移旧 helper 或重构 readArchive。

## 兼容矩阵与 negative control

| 维度 | 本批覆盖 | 必须不变 / 未覆盖 |
|---|---|---|
| V4 4.1.93 | 已有真实 device/symbol 元数据与 API 存在读数；文件动作先 fake，另批授权后才真机 | 不拿 probe 存在冒充文件导出成功 |
| V3 | 未覆盖 | 不从类型声明声称 V3 可用；缺失方法必须结构化拒绝 |
| `.epro2/.eprj2/.eprj3` | parser 未改，均未覆盖 | 不声称 elibz/elibz2 已可解包或三种工程容器兼容改变 |
| 在线 / 离线 | 离线 fake 与 CLI mock；在线真机待部署批准 | mock 绿不冒充真实 SymbolProfile |
| 单 / 多板 | 只读系统库中一个普通器件符号 | 重复 PCB 双审、分歧库串板均不改变、不验证 |
| 普通器件 / CBB | 本批只读普通符号文件 | 不调用 CBB 文件接口，不声称 CBB 几何或原生放置兼容 |
| 旧 / 新 Connector | 旧 Connector 对新动作可返回 UNKNOWN_ACTION | 旧 `lib.symbol.get` 元数据、旧文件导出权限数组和 CLI 参数树不变 |
| 绘制 | 零变化 | 不生成 PresentationSpec、不解除 `notForDrawCompile`、不写画布 |

两个旧消费者回归锚：`lib.symbol.get` 仍返回 `{uuid,libraryUuid,found,item}`；`sys.get_document_file` 的调用参数、权限数组、字节返回与 gate 文案不变。新能力只走新动作，旧 CLI 参数、顺序、退出码、DSH 工具名不变。CLI 合同快照只能由正式生成器更新；结构化差分须证明除 bridge epilog 新 action 说明外 argparse 树不变。

## 允许文件域

- `connector/src/actions.ts`：新增薄 handler、注册和最小权限上下文；不改旧 handler 语义。
- 新增 `connector/tests/library-symbol-file.test.mjs`，必须经真实 `buildHandlers()`。
- `src/boardwise/bridge/protocol.py`：只新增一个 Action 条目。
- 新增 `tests/test_038q3_symbol_file_read.py`，只测目录、只读门和 CLI 透传。
- `docs/bridge.md`：只补新 action 行，不改旧动作的能力描述。
- `contracts/cli/v1.json`：只用 `.venv/Scripts/python.exe -m tools.cli_contract --write` 生成。
- 本任务书；真机证据后续放 `outputs/review/038q3/`，探针临时文件放 `.tmp_038q3/`。

不改绘制线文件、package/version、DSH、Rust、TASKMAP、worktree、生产 daemon/Connector；零 git 写、零删除、零真实工程写入。

## 实施与验收

1. 单个 coder，最多 40 步或 30 分钟。只实现以上合同，不提前写 elibz parser 或 profile。
2. fake 覆盖：三元组精确实参、系统库 undefined、两种 fileType、未知参数/数组/path 零宿主调用、缺方法、getter 抛错、宿主拒绝与 gate、undefined/null、零字节、File 无 arrayBuffer、文件名清洗、非 ZIP 观测、旧文件权限数组不变。
3. 聚焦 pytest（独立 `--basetemp=.tmp_pt_038q3`）、Connector 全测试和 typecheck、action catalogue/contract-drift、CLI 合同与 025/038Q1 邻域。不能省必要检查。
4. **禁止 `connector/build.mjs`、`npm test`、`npm run build`**（其中 `rm` 不符合本机删除纪律）。沿用 build.mjs 的 esbuild shared/define 配置，以独立 `.mjs` 脚本或无删除 Node API 直接生成 ESM 测试产物，然后 `node --test "tests/**/*.test.mjs"`。
5. 两处独立变异：① `fileType` 白名单或未知参数前置拒绝；② 下载库权限上下文或请求参数顺序。每处必须先红、再 cp 恢复并核对 SHA-256，不能用 git 恢复。
6. 全量测试与部署不在本子代理批次。主代理审查 diff、独立复跑、检查既有失败集合后，另行申请候选 daemon 重启和**仅 `test V4`** 的候选 Connector 热更。未经明确批准不得部署。
7. 真机取得文件后先只读观察容器成员和身份，再决定最小解包适配。身份、真实脚号、body 未核对前，四个模块继续 `identityStatus=unverified`、`notForDrawCompile=true`。


## 离线验收（主代理，2026-11-11）

- 真实只读身份已核对：AMS1117-3.3/C6186 的 device/library/symbol UUID 与 `lib.symbol.get` 元数据吻合；元数据没有几何，官方文件 API 在 EDA 4.1.93 实测存在、arity=3。原始响应与哈希见 `outputs/review/038q3/ACCEPTANCE.md`。
- Connector 660 passed、typecheck 通过；最终注释修正后新动作 26 passed。Python 聚焦 296 passed，补充邻域 127 passed。DSH 137 passed / 1 skipped，typecheck/build 通过。
- 两处变异（fileType 白名单、参数顺序）均先红后 cp+SHA-256 恢复，恢复后测试复绿。最终注释校正不改变行为，最终源码和候选 bundle 哈希见验收文件。
- 第一轮完整 pytest 在 900 s 工具上限截断，无最终汇总。第二轮实际完成：**10678 passed / 25 skipped / 1 xfailed / 24 failed / 1 warning**。与 038Q2 基线逐项比较 **added=[]**；24 条均已有，48 条消失项全是绘制线当前变化，不归入本批成果，不称全量全绿，不跑第三轮。
- 本批尚未部署，未导出 elibz/elibz2、未核对容器内 UUID、未生成 SymbolProfile；四模块继续保持 unverified/notForDrawCompile。生产 daemon/Connector 未改，零 git 写、零真实工程写入。
- 下一步需另获本次候选部署批准：daemon 重启和仅 `test V4` 热更；真机只读文件后先检查容器格式与身份，再决定最小解包适配，完成恢复后才进入 profile 小批。


## 真机补验与环境恢复（2026-11-11）

- 岳已明确批准本次部署。仅 `test V4` 热更候选 Connector；真实 `lib.symbol_file.get(elibz2)` 成功，1874 字节 ZIP，SHA-256 `53f58e3706a078178c6883264130330db4be5d84d35ff1f150a595d0d752d4cb`。
- 容器有 `.elibu` + `symbol2.json` 两成员；UUID/library path 均与请求一致。原始 4 脚为 1=GND、2=VOUT、3=VIN、4=VOUT，rotation/length 可读。证据：`outputs/review/038q3/container-identity.json`。
- 原 `.elibu` 有两个相同 SYMBOL DOCHEAD。旧 `collect_symbol_details` 实测 body 正确但 **0 pins**，证明本批文件动作成功不等于现有解析器可消费；下一批只处理该单符号容器边界，不拿猜测几何补缺。
- 正式 daemon 0.6.1 与三窗 Connector 0.6.0 已恢复，`test V4` / P41 回读一致，配对指纹不变，实际 exe 路径与哈希已核验。候选 daemon 已停止，正式 daemon 保持运行；零原理图/PCB 写入。详见 `outputs/review/038q3/ACCEPTANCE.md` 末节。
