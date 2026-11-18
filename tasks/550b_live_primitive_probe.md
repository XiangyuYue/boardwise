# 550B — `sys.probe {instances: […]}`：在线只读实例探针

> 批次：550B（0.6.2 后的在线只读能力探针批）
> 状态：**代码、离线测试与 EDA 4.1.100 真机验证均已完成（2026-11-18）**。
> 本批不宣称 live net-path，不做设计写；V3 与其他样本边界见 §5。
> 前置：550 离线 net-path 已发布；本批只回答「运行中的编辑器在那三个方法上到底答不答」。

## 0. 真机实测（EDA 4.1.100）

| 组合 | 真机结果 |
| --- | --- |
| `line.getEntireTrack(includeVias)` | 可用；`includeVias=true` 比 `false` 多返回真实 via |
| `line/via/arc.getAdjacentPrimitives` | 可用 |
| `arc.getEntireTrack` | 可用；样本返回 236 项，`limit=64` 与 `truncated=true` 如实 |
| `pad.getConnectedPrimitives`（基类实例） | **`typeof undefined`** |
| `pad.getConnectedPrimitives`（ComponentPad 回退） | **`function` + `resolution='component'`**；走查 55 个组件、唯一匹配、零读错误、未截断；`onlyCentreConnection=true/false` 各返回 2 个真实走线 ID |

类型包核清：`getConnectedPrimitives` 只声明在 `IPCB_PrimitiveComponentPad`（器件自带的焊盘），
不在基类 `IPCB_PrimitivePad`。所以首版「不做 component fallback」的边界被真实证据推翻——
基类缺这个方法**不等于**器件焊盘也没有。最终有界回退已在 2026-11-18 的真机验证通过。

激活边界：ROBOT 窗口曾出现 `activateObserved=no`，随后虽恢复为 `yes`，`--no-reload` 后的菜单点击仍只增加
`evaluations`、`bootstrapAt` 不变，运行的还是旧 bundle；**完整重启立创 EDA 后才加载新包**。
不能把菜单点击或版本串相同当成新代码已激活，必须用目标行为回读。探针后原 P1 页已恢复，
非 PCB 焦点实测 `PAGE_MISMATCH`，设计写为零。原始证据 `.tmp_550_live/`（本机，不入库）。

## 1. 为什么需要它

`sys.probe` 的静态检查（`checks` 模式）在宿主 EDA 4.1.100 / connector 0.6.2 上显示：

```
pcb_PrimitivePad.getConnectedPrimitives   undefined
Line/Arc.getEntireTrack                   undefined
Line/Via/Arc.getAdjacentPrimitives        undefined
```

**这不是反证**。类型包（`@jlceda/pro-api-types`）把这三个方法分别声明在 `IPCB_PrimitiveComponentPad`
`IPCB_PrimitiveLine` / `IPCB_PrimitiveArc` / `IPCB_PrimitiveVia` 这些**实例接口**上，
`pcb_Primitive*` 管理器命名空间上本来就没有它们——命名空间上的 `typeof` 无论宿主如何实现
都只会答 `undefined`。要判断宿主到底有没有它们，必须拿到**实例**。

而现有的两条读口都拿不到实例：`pcb.readback` / `pcb.geometry` 只回 JSON 摘要，`sys.probe`
其它模式只枚举命名空间。所以本批扩展 `sys.probe` 的 `instances` 模式：**闭集**、**只读**、
**不新增 action**、**不开放任意方法名**、**不设计 live net-path**。

## 2. 公开合同

### 2.1 请求

```jsonc
{
  "instances": [
    { "kind": "pad",  "primitiveId": "<既有 ID>", "method": "connected" },
    { "kind": "line", "primitiveId": "<既有 ID>", "method": "entireTrack", "includeVias": true },
    { "kind": "via",  "primitiveId": "<既有 ID>", "method": "adjacent" }
  ],
  "limit": 32
}
```

- `instances`：数组，长度 **1..4**。每项只允许五个键：
  `kind` / `primitiveId` / `method` / `onlyCentreConnection` / `includeVias`；**未知键拒绝**。
- `kind`：`pad` | `line` | `via` | `arc`（`pad`→`pcb_PrimitivePad`，
  `line`→`pcb_PrimitiveLine`，`arc`→`pcb_PrimitiveArc`，`via`→`pcb_PrimitiveVia`）。
- `primitiveId`：非空字符串，**必须是该 PCB 页既有的图元 ID**（真机 ROBOT 板已取到
  237 pads / 363 lines / 204 vias / 2 arcs）。本批**不自动选件**、**不做整板枚举**：唯一的
  枚举是 `pad.connected` 在基类实例缺方法时的**有界 ComponentPad 回退**（≤512 个组件，见 §2.5）。
- `method` 与 `kind` 的对应（照类型包，不自行扩大）：

  | kind | method | 宿主方法 | 参数 |
  | --- | --- | --- | --- |
  | `pad` | `connected` | `getConnectedPrimitives` | `onlyCentreConnection: boolean`（缺省 `true`） |
  | `line` / `arc` | `entireTrack` | `getEntireTrack` | `includeVias: boolean`（缺省 `false`） |
  | `line` / `arc` / `via` | `adjacent` | `getAdjacentPrimitives` | 无 |

- 参数键也按方法封死：`connected` **只**接受 `onlyCentreConnection`，`entireTrack` **只**接受
  `includeVias`，`adjacent` **两个都不接受**；给了不属该方法的键是 `BAD_REQUEST`（不复用、
  不静默丢弃）；给了非布尔值同样是 `BAD_REQUEST`。
- `limit`：整数 **1..64**，缺省 **32**。只在有 `instances` 时有意义；单独出现是 `BAD_REQUEST`。
- `instances` 与 `realm` / `call` / `checks` / `namespace` / `namespaces` / `functionsOnly`
  **不得混用**，冲突 `BAD_REQUEST`。**不传 `instances` 时旧模式行为完全不变**。

### 2.2 页守卫

任何 `get()` 之前先跑精确 PCB 页守卫（复用 `activeDocument` 的直读
`dmt_SelectControl.getCurrentDocumentInfo`）：

- 非 PCB 页 → `PAGE_MISMATCH`；
- 焦点只能由按类回退（`page`/`pcb`）读出、无法证明确实是 PCB → 同样 `PAGE_MISMATCH`；
- 无活动文档 → 同样 `PAGE_MISMATCH`。

**绝不自动切页**。请求方自己 `doc.open` 把 PCB 页调到前台再来。

### 2.3 返回

```jsonc
{
  "version": "4.1.100",
  "connector": "0.6.2",
  "topLevel": ["…"],
  "page": { "uuid": "<pcb uuid>", "type": "pcb" },
  "readOnly": true,
  "instances": [
    { "kind": "pad", "primitiveId": "…", "method": "connected", "status": "function",
      "arity": 1,
      "call": { "ok": true, "count": 3, "ids": ["…", "…", "…"], "truncated": false } }
  ]
}
```

`status` 各自代表**不同事实**，任何一个都不许折叠进另一个：

| status | 含义 | `call` |
| --- | --- | --- |
| `function` | 方法在实例上存在，**已调用** | 有：`{ok: true, count, ids, truncated, unreadable?}` |
| `absent` | 实例在，方法**不是函数** | 无 |
| `not-found` | `get(primitiveId)` 答了 `undefined`/`null`：本页没有这个图元 | 无 |
| `unavailable` | 管理器命名空间或其 `get` 不在这个 build 上 | 无 |
| `error` | 宿主在 `get`/方法上抛错，或方法返回**非数组** | 抛错：`{ok: false, error}`；`get` 抛错时无 `call` |

- “无候选”**不写成**“方法不存在”：`function` + `call.count = 0` 才是真的空连接；
- “方法不存在”**不写成**空连接：`absent` 不带 `call`；
- 非数组返回（`null` / 对象 / 字符串 / 布尔）是 `error`，**不是空数组**；
- `count` 保留宿主原数组长度；`ids` 最多 `limit` 条；`truncated` 如实披露是否截断；
- `unreadable` 计数：返回的图元里 `getState_PrimitiveId` 读不出来的个数（`count` 提到多少个，
  `ids` 命名了几个，差额说清楚）；
- **只从返回图元读 `getState_PrimitiveId`**，不回整对象、不回 net、不回几何、不回层。
- pad 行额外带 `resolution` 与 `componentFallback`（见 §2.5）；line / arc / via 行**不变**，
  两个键都不出现。

### 2.5 pad.connected 的有界 ComponentPad 回退（550B-c）

真机实测：基类 pad 实例没有 `getConnectedPrimitives`，方法在
`IPCB_PrimitiveComponentPad`（器件焊盘）上。因此：

- **直接命中**：基类实例的方法在 → 原路径调用，**不做任何组件枚举**，`resolution: 'direct'`。
- **直接缺失**：走有界回退 —— `pcb_PrimitiveComponent.getAll()`，每个组件的 `getAllPins()`，
  只用 `getState_PrimitiveId` 与请求的 pad ID **精确匹配**；最多检查 **512** 个组件，
  超出必须披露 `truncated: true`；逐组件失败（`getAllPins` 缺失 / 抛错 / 非数组 / 引脚 ID
  读不出）计入 `readErrors` 并**继续**。
- **恰好一个匹配**：在该 ComponentPad 上重读目标方法，`resolution: 'component'`；
  方法可调用则正路径（参数照 `onlyCentreConnection`），仍披露 `readErrors` / `truncated`。
- **多个匹配**：`error`（`/ambiguous/`），**不挑第一个**，也不在任一候选上调用。
- **无匹配**：只有在 `readErrors` 为空且未截断时才可保持 `absent`；任何读取缺口或截断存在时
  负向 `absent` **必须升级为 `error`**（组件命名空间/`getAll` 本身不可用则 `unavailable`），
  不得宣称“ComponentPad 也没有这个方法”。
- `componentFallback: {components, matches, readErrors, truncated}` 随 pad 行返回，
  供调用方区分「直接基类答案」与「器件焊盘证据」。

### 2.6 只读边界

- 复用既有 `readMember` / `getState` / `settle` / `ActionError`，位置参数守卫复用
  `activeDocument` / `readbackKindOf` / `describeDocument`。
- 不出现 `create` / `modify` / `delete` / `reset` / `done` / `setState_*` 任何一个；
  回退只调 `getAll` / `getAllPins` / `getState_PrimitiveId` 与目标读方法，不读 net、不读几何、
  不做任何 component 写操作。
- 测试用记录器把宿主上每一次调用记账，断言日志里没有任何写动词。

## 3. 兼容矩阵

| 维度 | 取值 | 本批的处理 |
| --- | --- | --- |
| 编辑器世代 | V3（3.2.x） | **未验**；需要 V3 真实实例探针，不用 V4 结果外推，也不预设 `absent` |
| | V4（4.1.100） | 真机实测：line/arc/via 三方法可用；基类 pad 无 `getConnectedPrimitives`，§2.5 的 ComponentPad 回退亦已跑通 |
| 在线 / 离线 | 在线（bridge + 扩展） | 本模式唯一的运行位置，因为它必须有活着的编辑器实例 |
| | 离线（pytest / 解析器） | 不参与：无实例可拿；离线侧只消费 550 的 net-path，本批不改 |
| 单板 / 多板 | 单板（一页一 PCB） | 页守卫按焦点页判，正常路径 |
| | 多板（同工程多 PCB 页） | 只认**焦点**那一页；拿别的页的 ID 会得 `not-found`，不会跨页取件 |
| 普通器件 / CBB | 普通器件焊盘 | `pcb_PrimitivePad.get(id)` 得基类实例；方法缺时走 §2.5 回退，`resolution` 说清是哪一层答的 |
| | CBB 器件 / CBB 子图 | 回退按 `getAll()` 的组件列表走，不按器件类型筛选、不做 component 写；CBB 里的图元同样只用 ID 直接 `get()`；ID 不属本页即 `not-found`；组件列表里无法读引脚的点计入 `readErrors`，负向答案随缺口升级为 `error` |
| 焦点状态 | 精确 PCB | 正常返回值 |
| | 精确非 PCB / 只能回退读出 / 无文档 | 三种都 `PAGE_MISMATCH`，零 `get` |
| 方法形态 | 存在 | `function` + 实调用 |
| | 存在但抛错 | `error` + `call.ok=false` + `arity` 仍在 |
| | 不存在 | `absent` |
| | 返回非数组 | `error`（不是空数组） |
| 参数 | 缺省 | `connected` 默认 `true`，`entireTrack` 默认 `false` |
| | 显式 | 原值透传，测试逐项核对实参 |

## 4. Negative controls（离线）

`connector/tests/pcb-instance-probe.test.mjs` 覆盖，且都能在关键 hunk 被禁用时转红：

1. **非 PCB 零 get**：原理图页焦点、只能回退读出、无活动文档三种情形都 `PAGE_MISMATCH`，
   且 `get` 调用记录为空数组。
2. **无实例 vs 缺方法区分**：同一调用里 `absent` / `unavailable` / `not-found` 三态并存，
   且三者都不带 `call`。
3. **三方法正路径及参数**：`pad.connected` → `[true]`（缺省）与 `[false]`（显式）、
   `line.entireTrack` → `[false]` / `[true]`、`line/via.adjacent` → `[]`；`arity` 逐个核对。
4. **方法抛错**：该方法项 `error` + `call.ok=false`，同批下一项仍正常返回。
5. **非数组**：`null` / `undefined` / 对象 / 布尔 / 字符串五种都判 `error`，并显式断言它
   **不等于** `{ok:true,count:0,ids:[],truncated:false}`。
6. **5000 返回计数 + limit 截断**：`count=5000`；缺省 `ids=32`、`limit=5` 时 `ids` 前五条、
   `limit=64` 时 64 条；`truncated` 均为 `true`。
7. **ID 读不出要计数**：4 个返回图元里只有 1 个 ID 可读 → `count=4`、`ids=['ok-1']`、
   `unreadable=3`。
8. **非法 kind / method / 键 / 模式冲突 / limit 越界**：全部 `BAD_REQUEST`，且零 `get`。
9. **旧模式不回归**：不传 `instances` 时 `checks`、`call`、`realm`、枚举、空参数五种模式
   的答案形状与之前一致，且不解析任何图元。
10. **零写调用**：整个测试期间宿主上的调用日志不含 `create` / `modify` / `delete` / `reset` /
    `done` / `setState_*` / `set*`。

550B-c 追加（ComponentPad 回退）：

11. **直接有方法时零组件枚举**：基类命中时 `pcb_PrimitiveComponent.getAll()` 一次都不调用
    （`componentListings === 0`），`resolution: 'direct'`，无 `componentFallback`。
12. **唯一 ComponentPad 正路径**：基类缺失 → 回退找到唯一匹配 → 在该 ComponentPad 上以请求的
    `onlyCentreConnection=false` 实调，`resolution: 'component'`，
    `componentFallback = {components:2, matches:1, readErrors:[], truncated:false}`。
13. **重复匹配拒绝**：两个组件带同一 pad ID → `error` `/ambiguous/`，且两个候选上都**没有**调用。
14. **无匹配且无缺口才 absent**：完整走完、零匹配（或唯一匹配但确实没方法）→ `absent`；
    同一个负向在有一处组件读失败时**必须**变 `error` 且文案含 `/did not complete/`。
15. **组件读失败不降级为 absent**：`getAllPins` 缺失 / 抛错 / 非数组三种，各计一条 `readErrors`、
    走完其余组件，负向答案升级为 `error`。
16. **>512 组件截断披露**：匹配在 512 内 → 正路径 + `truncated: true` + `components: 512`；
    匹配在第 550 个 → `error` + `/only the first 512 components were inspected/`。
17. **组件命名空间不可用**：命名空间缺失或 `getAll` 不是函数 → `unavailable`（不是 `absent`）。
18. **line/arc/via 不变**：四行都不带 `resolution` / `componentFallback`。

## 5. 明确未做 / 未验

- **V3 未验**：本批真机证据只覆盖 EDA 4.1.100 的一块真实板，不外推其他宿主、板型或 CBB。
- **不宣称 live net-path**：本模式只回答“方法在不在、调用抛不抛、返回是不是数组”，
  不推导连通网、不做 net-path 语义，也不把 `ids` 拼成图。宿主 `entireTrack` 的遍历范围与
  `onlyCentreConnection=false` 的 fill/polyline 语义仍需在后续 typed 工具合同中单独裁定。
- **不自动选件、不做整板枚举**：`getAllPrimitiveId` 本批一律不碰；`getAll` 只在 pad.connected 基类缺方法时按 §2.5 作有界组件回退，且上限 512、截断披露。
- 本批不新增 action、不改 connector 版本号、不动 review 规则 / parser / model / CLI / DSH；
  当前 ROBOT 运行的是本批开发 bundle，版本串仍为 0.6.2，**未提交、未发布**。
