# 559：在线 PCB 连通证据（550B → typed tool）

> **已被 559B 收窄（2026-11-19，`tasks/559b_direct_only_connection.md`）**：真实板上 `getEntireTrack(true)`
> 返回的 ID 集合跨越多个离线分离铜分量且 truncated（`evidence/559/entire-track-rejection.json`），
> 所以本文件里「entireTrack 集合参与正证明」「响应含 tracks[]」「256/1024 ID 预算」等契约表述**全部作废**；
> 现行语义是 direct-only（只认 direct 同一 Line/Arc 与 direct 对方焊盘），legacy 非空 `tracks[]`
> 只记 `entire-track-unsupported` 并压否定。下文保留为历史决策记录，不再作为验收依据。

## 1. 前因后果与边界

550 的 `pcb net-path` 只读归档，以 pad/直线 track/via 几何图给出有序路径；550B 已在 EDA 4.1.100 证明 `getConnectedPrimitives/getEntireTrack/getAdjacentPrimitives` 的实例能力，但只返回 ID，明确不是 live net-path。岳的目标第 5 项要求把这条能力做成封闭只读工具，并与离线 550 对拍。

本批新增 **`boardwise pcb connection`**，不改造或冒充 550 的有序几何路径。它回答的是：宿主是否能用两个焊盘各自的**直接**连接（`getConnectedPrimitives(false)`）证明这两端共享同一铜图元。输出 host evidence，不输出虚构的逐跳几何、不判 DRC、不把 NOT_PROVEN 说成开路。559B 之后明确：整个契约不读 `getEntireTrack`。

不改 550B 的 `sys.probe` 合同，不开放任意方法，不写设计、不自动切页。真实板只在任务执行时重新核对身份；允许为用户已连接的授权实板做只读导航和读取，必须恢复原焦点，真实项目名、容器和板级数据只留本地 `.tmp_559_live/`，不进公开文档或提交。

## 2. 当前树与集成约束

- HEAD `14e8f39`；工作树混合。`connector/src/actions.ts` 有他人的 lib search hunks，`bridge/protocol.py`/`docs/bridge.md` 有他人的删页确认与 lib search hunks，必须保留。
- `cli.py`、绘制线、bridge daemon 其他 hunks 不属于本批；本批不改 `cli.py` 和 daemon。
- shared/bridge/CLI 按 `tasks/shared-platform.md` 串行集成；协议与 connector 改动单独复审，不夹规则语义变化。
- 开工前备份目标到 `.tmp_559/backup-<域>/` 并记 SHA-256；变异只用 cp+SHA 恢复。

## 3. 公开合同

### CLI

```bash
boardwise pcb connection --from REF.PAD --to REF.PAD [--project NAME_OR_UUID] [--instance ID] [--port N]
```

- 命令仅在线，无 FILE、`--live` 或 `--board`；焦点 PCB 就是板身份，绝不自动选另一块板或第一块板。
- stdout 一份 `schema=boardwise.pcbConnection/1` JSON；`CONNECTED` exit 0、`NOT_PROVEN` exit 2、`INDETERMINATE`/读取拒绝 exit 3；argparse 错误 exit 2。
- `source` 带 host/connector/page 身份和 readOnly；`query.from/to` 带 ref、component/pad ID、net；`evidence` 保留两端 direct 与 track 调用读数；`sharedIds` 是交集证据，不叫 path。
- `unknown[]`、`ignored[]`、`errors[]`、`coverage`、`scope` 始终存在。任何截断、组件/引脚读失败、未知图元、方法缺失、非数组或无法判定层/网身份必须披露；它们使否定结论降为 INDETERMINATE。已由明确交集证明的正结论可保留，但未知项不得消失。
- 同 pad、REF  malformed、重名/多匹配、异网或空网不可判：INDETERMINATE，不制造零跳 PASS 或跨网正常连接。

### Connector action

新增唯一 `pcb.connection_probe`，risk=read、design_write=False，参数封闭为 `{from,to}` 两个 REF.PAD 字符串；未知键拒绝。严格复用 550B 的精确 PCB 焦点守卫，不自动 doc.open。

Connector 只做宿主读取与证据收集，**不计算 verdict**：

1. 一次有界组件扫描（≤512）解析两端：组件 Designator + ComponentPad PadNumber 精确匹配；读 `snapshot` 的 PrimitiveId/Net 等既有公开字段。无匹配、多个匹配、扫描不完整分别报告，绝不挑第一个。
2. 在已解析的 ComponentPad 上调用 `getConnectedPrimitives(false)`。只从返回对象读 PrimitiveId 与 PrimitiveType，保留 count/ids/truncated/unreadable；不把 absent/error 当空数组。
3. **559B 起的现行语义**：不再调用 `getEntireTrack`，因此没有 `tracks[]`、没有每端 16 之外的 ID 上限与 `coverage.ids`；每端最多 16 个 direct 图元，上限与截断显式返回。direct pad→目标 pad 可作为直接宿主证据；direct via/fill/pour/polyline/未知类型不猜连通语义，列 unknown。
4. 返回 `{page,readOnly,from,to,errors,unknown,ignored,coverage}`。每端含解析证据与 direct call；不包含 verdict/path/tracks，不写任何宿主状态。

Python shared 纯函数根据证据求交集并投影 verdict：两端 direct 报同一有类型 Line/Arc，或 direct 明确包含对方 pad，才可 CONNECTED。交集 ID 必须非空且可追溯到具体调用。NOT_PROVEN 仅限两端及所有相关调用完整、无未知项时，且语义是「direct 范围内无共享图元」，不是开路。

## 4. 文件域

A（connector）：`connector/src/actions.ts` 仅追加本批 helper/handler/注册；新增 `connector/tests/pcb-connection-probe.test.mjs`。保留 lib search 未提交 hunks。

B（协议/共享/CLI）：`src/boardwise/bridge/protocol.py` 仅新增 action；新 `src/boardwise/core/connection.py`、`src/boardwise/pcb_connection.py`；`src/boardwise/commands/assembly.py` 仅注册/分派 connection；新 `tests/test_559_pcb_connection.py`、`tests/test_559_pcb_connection_cli.py`；`contracts/module-owners.json` 必要登记；`docs/bridge.md`、`docs/review-sop.md` 本批段。CLI 合同由 shared 集成统一生成，不在 A 手工改。

禁改：`sys.probe` 既有行为、550 离线算法、review 规则、绘制线、daemon、DSH、fixtures/reviewsets、真实工程、全局货架、package 版本。未经另行任务不新增 DSH 工具。

## 5. Negative controls 与验收

- 非 PCB/无焦点/启发式焦点：PAGE_MISMATCH，零组件及图元读取。
- 两端合并一次组件扫描；重复组件/重复 pad、>512 截断、引脚读失败不得变成有效端点或干净否定。
- direct absent/error/non-array、ID 不可读、超过 direct/ID 上限均披露；否定必为 INDETERMINATE。
- 无交集 NOT_PROVEN；有任意 unknown 时同输入必须 INDETERMINATE；伪造无来源 sharedId 不得 CONNECTED；异网即使 ID 相交也报输入错误。
- **559B**：不调用 `getEntireTrack`（实测其 ID 集合跨离线分离分量，`evidence/559/entire-track-rejection.json`），legacy 非空 `tracks[]` 记 `entire-track-unsupported` 并压否定；direct via/fill/pour 不得伪造路径；所有 host 写动词调用为零。
- 550 旧 net-path 测试逐字保持；旧 sys.probe 测试保持；owner/layer、action catalogue/policy、CLI 合同通过。
- 至少两处主代理独立变异：去掉交集真实来源检查、把 unknown 不再降级，对应测试先红后 cp+SHA 恢复。
- Connector 聚焦 + typecheck；Python 559 + 550 + bridge/action/CLI/owner/layer 聚焦；不拿全量当侦察，最终必要四线在总集成点执行。

## 6. 真实对拍与交卷

- 先 `bridge status` + `document.current`，确认运行 bundle 含新 action；仅版本号相同不算激活。真实板身份只记本地证据。
- 在同一授权非空 PCB 取至少一组可由 host 证明的同网连接和一组完整证据下的无交集查询；用同一时刻 `sys.get_project_file` 导出走 550 离线命令。比较 verdict、端点、交集/路径与 unknown，不把两种证据模型差异伪装成字节相同。
- 若没有完整负例，负向只能记 INDETERMINATE，不为凑 NOT_PROVEN 改规则；宿主前提不成立则交可复现探针和失败原文。
- 恢复真实原焦点，设计写为零；本地证据 `.tmp_559_live/`，公开证据只放匿名合成/读数。
- 零 Git 写、零 rm/unlink、零部署、零发布。子代理每批 ≤40 步/30 分钟、结论 ≤2000 字，实际命令→汇总→差异，未决项单列。

## 7. 主代理 A 域验收补充（B 必须遵守）

- 父验：Connector 新15例 + 旧25例共 **40 passed**，typecheck通过；撤掉新 action 的 `requirePcbFocus` 后三条页守卫均转红，cp+SHA 恢复后40/40绿，源码 SHA `d7d004c8…6596`。
- `coverage.complete` 只是 Connector 摘要，**不是 Python 的否定结论依据**。B 必须自行检查 endpoint resolved/唯一 pad id/net、direct.ok、track.call.ok/truncated/unreadable、scan/readErrors、response errors/unknown；coverage 缺失或 false 且无交集时一律 INDETERMINATE。
- 可接受的交集来源必须具体（559B 后只剩两类）：两端 direct 的同一 Line/Arc、一端 direct 明确是对方焊盘。Via/fill/pour 不能进入 proof；legacy 非空 `tracks[]` 也不是 proof（`entire-track-unsupported`）。每个 sharedId 都要带来源，不能仅比较两个无类型 ID 数组。
- Connector 当前 track 的 `call.unreadable` 只在调用行披露，不会自动进入 unknown；B 必须把它当证据缺口。正向已有明确 proof 时可保留 CONNECTED，但缺口不得删除；负向不得因 coverage.complete 单字段变 NOT_PROVEN。
- A 的真机与合同目录未验，B 加 protocol 后需重跑 contract-drift；不改 sys.probe 或550旧行为，不补未裁定的 capability 位。

## 8. 实际完成（560 收尾时补记）

- A 域 connector：typecheck 通过、Node **40 passed / 0 failed**；父变异把 `requirePcbFocus` 换成固定 PCB 页后 **3 failed / 12 passed**，cp 恢复并重建回 40 passed（`evidence/559/parent-a-review.md`）。
- B1 纯投影：父复跑 **73 passed**；两有效变异（类型闸 **2 failed / 29 passed**、缺口闸 **9 failed / 22 passed**）先红后 cp+SHA 恢复（`evidence/559/b1-parent.md`）。
- B2 CLI/合同：父合并 **268 passed in 29.66s**，connector typecheck + **43 passed / 0 failed**，`tools/cli_contract.py` check 通过（`evidence/559/b2-parent.md`）。
- 真实：`evidence/559/host-prevalidation.json` 的正例 CONNECTED、负例 NOT_PROVEN 与离线 550 判定一致（各 4/0 条 proof、0 unknown、0 error），但这只是**预验**——走已激活的 550B `sys.probe` + 同会话归档身份。原生 `pcb.connection_probe` 在旧 daemon 上 **exit 3、stdout 空、`unknown action 'pcb.connection_probe'`**（`evidence/559/native-activation.json`）：未重启 daemon、未热更 connector、未部署 DSH、未发布，**不写成已激活或通用宿主兼容**。
- 下一步最小授权动作（留给岳裁定）：另行授权一次开发态激活——加载新 daemon 目录与 connector bundle，用该 action 自证激活，再跑同一组正反查询。
- 状态：**工作树完成、未提交未推送**。
