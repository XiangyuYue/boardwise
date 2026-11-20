# 562：在线多跳 PCB 铜路径——`getAdjacentPrimitives` 图合同（仅立项）

## 1. 前因与当前结论

550 已从离线几何图给出 `pcb net-path` 的有序路径；559/559B 的在线 `pcb connection` 只证明 direct 共享图元，刻意不含 `path` / `hopCount` / `viaCount`。真实反例已经证明 `getEntireTrack(true)` 会把其他离线分离铜分量的 ID 也返回，且可能 truncated，**成员集合不能证明物理连通**。

550B 只证明 EDA 4.1.100 的 Line/Arc/Via 实例会回答 `getAdjacentPrimitives`，没有证明这些回答足以直接拼成路径。562 因此先定义图、证据、预算和真机反例，**本批只写合同，不实现**。

裁定如下，不再摇摆：

- 新建独立 `pcb.path_probe` action、`boardwise pcb path` 在线命令与 `boardwise.pcbLivePath/1` 输出；**不改 559 的 direct-only schema/语义**。
- Connector 只收集宿主证据，Python 纯函数构图、找路和判三态；不在 TS 复制 verdict。
- 禁止 `getEntireTrack` 参与任何正证据、补路或“诊断性”连通判断。
- 路径必须能逐跳回溯到具体邻接调用，不能只给一组 ID 后声称它是一条路径。

## 2. 目标与非目标

目标：回答焦点 PCB 上两个 `REF.PAD` 之间，是否存在一条**有序、逐跳有宿主证据**的多跳铜路径，并输出路径、跳数、过孔数、证据缺口与覆盖范围。

非目标：不判 DRC、线长、阻抗、载流、间距或电气规则；不把 `NOT_PROVEN` 写成开路；不自动切页、选另一块板或写设计；不承诺 V3、铺铜/PLANE、任意 CBB 内部展开或任意板型。

## 3. 公开入口与输出

### 3.1 Connector action

`pcb.path_probe`，`risk=read`、`design_write=False`，参数只允许 `{from,to}` 两个 `REF.PAD`；未知键拒绝。复用 559 的精确 PCB 焦点守卫与一次 ≤512 组件扫描，绝不自动 `doc.open` / `doc.focus`。

返回宿主证据，不返回 verdict：

- `page / readOnly / from / to`：板页与两端解析证据；
- `nodes[]`：`{primitiveId,type,net,layer?}`，类型与 ID 必须同读，层读不到为 null 并披露，不猜盲埋孔层；
- `edges[]`：`{from,to,method,callIndex,hostOrder}`，每条边指向一次具体 `getConnectedPrimitives(false)` 或 `getAdjacentPrimitives()`；
- `seeds[] / frontier[]`：起点种子与预算结束时尚未展开的节点；
- `coverage / unknown / ignored / errors`：调用计数、截断、不可读项、排除项与失败原文。

### 3.2 CLI

```bash
boardwise pcb path --from REF.PAD --to REF.PAD \
  [--project NAME_OR_UUID] [--instance ID] [--port N] [--json PATH]
```

- 在线-only，无 FILE、`--live`、`--board`；焦点 PCB 就是板身份。
- 退出码：`CONNECTED=0`、`NOT_PROVEN=2`、`INDETERMINATE=3`；argparse 用法错误仍为 2。
- 不带 `--json`：stdout 一份 `boardwise.pcbLivePath/1`。带 `--json`：同一规范 JSON 写 PATH、stdout 为空；写失败具名退 3，不能拿部分文件冒充结果。该文件面是为多跳大图和将来的 DSH structured transport 预留，避免 32 KiB stdout 截断。
- 前置 refusal（无 connector、旧 action、REF.PAD 非法、非 PCB 焦点）仍是 stderr 一行 + 空 stdout + exit 3，不打印 verdict。

### 3.3 结果形状

`schema / verdict / source / query / path / hops / hopCount / viaCount / unknown / ignored / errors / coverage / scope` 永远存在。

- `path[]` 是有序顶点：`{primitiveId,type,net}`；`hops[]` 是有序边，逐条带 `method + callIndex` 证据。
- `hopCount=len(hops)`，`viaCount` 只数 path 中 `type=Via` 的顶点；`CONNECTED` 时两者必须与 path 一致。
- `source.versions` 复用 559 的 host/connector 读取与 missing/error 披露；版本缺失不翻转 verdict。
- `coverage.complete` 只作摘要，Python 必须逐项重算，不得用它单独放行 NOT_PROVEN。

## 4. 图顶点：谁可以进入证明

首批只支持有明确类型与身份的：

- 查询两端的 `Pad` / `ComponentPad`；
- `Line`、`Arc`、`Via`，且每个节点都能读到非空、与两端相同的 net。net 只用于筛选，**永不作为连通证据**。

约束：

1. 节点键为 `(primitiveId,type)`，不能仅按 ID 猜类型；展开前还要从对应管理器取实例并复核 ID/type。
2. 缺 ID、缺类型、缺 net、管理器 get 失败、实例不匹配、非数组返回都是 `unknown`，不能展开，且会压否定。
3. 其他 net 的返回项只记 `ignored:other-net`，不遍历；跨网短接不是本命令要回答的问题。
4. 中间出现的其他 Pad 首批不展开，记 `unknown:intermediate-pad-unsupported`；只有查询两端 Pad 可以作为路径端点。
5. `Fill` / `Pour` / `Poured` / PLANE 是 `ignored:pour-excluded`，与离线 550 一样属于主动排除，不单独升级 INDETERMINATE。
6. `Polyline`、`Region`、未知类型或其他可能构成桥接的图元是 `unknown:unsupported-adjacent-type`，不得当 ignored 掩盖。
7. Pad↔Via 直接接触首批记 `unknown:pad-via-contact`，不得进入正路径；只有另行真机证实该语义后才能放开。
8. Arc 只有在真实板上取得“邻接调用 ↔ 同一时刻导出身份”的正路径证据后才可作为 proof；没有该样本时 Arc 一律 unknown，不能拿 550B 的“方法存在”冒充语义已验。

## 5. 图边与找路：什么叫逐跳证明

### 5.1 端点种子

两端各读 `getConnectedPrimitives(false)`：

- Pad→Line/Arc：可作为 `pad-direct` 边（Arc 仍须先满足 §4.8 的真实样本门槛）；Pad→对方 Pad：可作为 `pad-direct-other-pad` 边。
- Pad→Via：按 §4.7 只记 unknown；Pad→铺铜/未知类型按 §4.5/4.6 处理。
- 两端 direct 共享同一 Line/Arc 时，可形成 `fromPad → track → toPad`，与 559 的证据相容，但输出属于新 LivePath 合同。

### 5.2 中间邻接

对 Line/Arc/Via 实例调用 `getAdjacentPrimitives()`：

- 首批**只把双向都读到的邻接当作 proof**：A 的回答点名 B，B 的回答也点名 A，而且两边类型/net 一致。单向邻接记 `unknown:non-reciprocal-adjacency`，不进入正路径。
- 这条保守规则避免把宿主可能存在的方向性误读成无向铜连接。若真机证明该 API 的方向语义不同，必须另改合同并保留本批反例，不得静默删掉双向校验。
- 端点 `pad-direct` 使用其自身直接连接语义，不伪造一次不存在的反向 `getAdjacentPrimitives`。

### 5.3 BFS 与确定性

- 从 from 做 BFS，返回最短跳数路径；邻居统一按 `(type,primitiveId)` 排序，不能依赖宿主返回顺序。
- 节点首次发现顺序、邻接调用顺序、unknown 阶段顺序均固定；JSON canonical `sort_keys=True`。
- 找到合法路径即可停止，未探索区域记 `coverage.partial`；已证路径不被无关缺口推翻，但缺口仍披露。
- `NOT_PROVEN` 仅在可达 frontier 已穷尽且没有 unknown/errors/truncation/预算耗尽时成立；它仍不是开路。

## 6. 预算与截断语义

首批预算为固定上限，不开放调用方随意放大：

- 组件扫描 ≤512；
- 每次 direct/adjacent 最多回 64 个节点，保留宿主 `count` 与 `truncated/unreadable`；
- 全图最多 512 个顶点、512 次邻接调用、2048 条候选边；
- CLI/DSH 总时间预算 120 s；Connector 在每次宿主读取之间检查预算，单个宿主调用的异常/挂死按现有 bridge 失败披露，不声称能硬取消宿主函数。

任何 per-call 截断、ID 不可读、顶点/调用/边/时间预算耗尽，都写 `unknown:budget-exhausted` 或对应精确 code；负向必须 `INDETERMINATE`，绝不能报 NOT_PROVEN。正向只使用预算内已完整证明的路径，不能用截断处继续猜路。

## 7. Negative controls（实现批必须先红）

1. 同名但不同 net 的 ID 相交不得 CONNECTED；缺 net 不得放行。
2. A→B 单向邻接不得形成路径；A↔B 双向且类型/net 一致才可。
3. 非数组、方法 absent/error、ID/type 不可读、管理器 get 错实例均压否定。
4. per-call truncated、顶点/调用/边/时间预算耗尽均使负向 INDETERMINATE。
5. `getEntireTrack` 即使返回一条完整候选路径上的全部 ID，也不得产生任何 proof；调用次数必须为 0。
6. Pad↔Via、铺铜、Polyline、中间 Pad 不得进入正路径，各自 unknown/ignored 分类正确。
7. BFS 最短路径、同输入字节一致、hops 与 hopCount/viaCount 一致；每条 hop 都能定位到真实 callIndex。
8. 无关 unknown 不推翻已证正路径，但 `coverage.partial` 必须保留；负向遇同一 unknown 必须降级。
9. 559 direct-only 原测试与输出形状不变，550 离线 net-path 不变。

主代理至少做两项独立变异：允许单向邻接形成 proof、把预算截断当完整遍历，相关测试先红后 cp+SHA 恢复；另做 entireTrack 调用为零的 Connector 断言。

## 8. 真机验收门槛（后续 562C，不在本合同批执行）

在同一授权非空 PCB、同一时刻导出身份下，至少取得：

1. 一组 direct 正例；
2. 一组至少两根 Line 的多跳正例；
3. 一组经过 Via 的正例（若板内存在）；
4. 一组离线 550 判为分离铜分量的完整负例；
5. 一组 Pad↔Via 接触披露，证明没有偷跑进正路径；
6. Arc 正例若无样本则保持 unsupported，不得找替代图元冒充。

在线 verdict、端点、逐跳 ID/type 与离线 550 对拍；ID 映射必须来自同一会话导出，不能比较不同导出的原始 ID 或要求字节相同。恢复焦点、设计写为零；真实容器与工程身份只留本地 `.tmp_562_live/`，公开证据只保留匿名读数。

V3 未验不宣称兼容；EDA 4.1.100 的样本不能外推其他板型。新 action 必须重新走 daemon/connector 激活与行为回读，版本字符串相同不算激活。

## 9. 实施拆分与文件域（后续批次）

- **562A Connector**：仅新 `pcb.path_probe` helper/handler/注册与 `connector/tests/pcb-path-probe.test.mjs`；复用 559 的端点解析，不改 559 action。
- **562B Python/CLI**：新 `core/livepath.py`、`pcb_path.py`、最小 assembly/protocol 注册、测试与官方 CLI 合同；shared 走 `tasks/shared-platform.md` 集成锁，绘制线 hunks 不夹带。
- **562C 真机与 DSH**：先完成 562A/B 和真机，再接 `boardwise_pcb_path`；优先消费 `--json PATH`，不让大证据走截断 stdout。版本 bump/pack/deploy/push/release 均另获岳批准。

算法与迁移不同批，shared/全量/真机串行；每批只一个文件域，禁止顺手修改 550/559 旧合同或绘制线。

## 10. 本合同批边界

本次只新增本任务书并更新台账，**没有实现 action、CLI、图遍历或 DSH 工具，也没有做真机**。后续若双向邻接、Arc 或 Pad↔Via 的真实语义被新证据推翻，先修订本合同和负例，再写生产代码。
