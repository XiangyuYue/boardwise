# 551：`pcb.net_class.list` 真实网络类只读证据

## 来源与边界

DRC/net class 影响面见 `.tmp_review_attribution/drc-netclass-impact.md`。现有 `pcb.drc_ruleset` 只读当前/默认规则集，并不读宿主持久化网络类。本批新增一个**独立、纯读** bridge action，不把网络类塞进窄读的 drc_ruleset，也不实现任何 create/edit/delete。

必须区分：

- `getAllNetClasses()` / `getNetRules()` 返回的宿主持久化网络类与约束；
- 上游或本地路由器按网名/电压猜测的启发式线宽表。后者不是本动作的数据源，也不能写成“真实网络类”。

离线归档没有对应的网络类通道，本批只做 connector/bridge，不伪造离线兼容。

## Action 合同

```json
{"action":"pcb.net_class.list","params":{"maxChars":400000}}
```

- `maxChars` 可选，沿用 drc_ruleset 的 1000..4_000_000 限制与 sanitiseHostValue 洗手/截断披露。
- 每次读取 `getAllNetClasses` 与 `getNetRules`；`getNetByNetRules`、差分对、等长组、layer list 不混入首版。
- 输出与 drc_ruleset 的证据形状一致：
  `{source:"pcb_Drc", page, classes, netRules, count, reads[], missing[], unreadable[], jsonChars, elapsedMs, readOnly:true, notes?}`。
- `classes` 只有宿主明确返回空数组时才是 `[]`；方法缺失、调用失败或值不可读时为 `null` 并写入 `missing[]`/`unreadable[]`，绝不能把“读不到”写成“没有网络类”。`count` 仅在 classes 可读时为其长度，否则 `null`。
- `netRules` 原样经过宿主值洗手，不用 `classes` 的存在性推断它是否为空；classes 为空而 netRules 非空必须同时可见。
- 非 PCB 焦点按既有 `PAGE_MISMATCH` 拒绝，不自动 `doc.open`。active=null 不能被当作已确认 PCB。
- `sys.connector_status.capabilities.pcbNetClassList` 仅在新 handler 存在时声明 true；旧 connector 不具备该能力。

## 文件域

- `connector/src/actions.ts`：handler、注册与 capability；复用现有 page guard、成员读取和 sanitiseHostValue。
- `connector/tests/net-class-list.test.mjs`：fake eda 的正负例与只读调用序。
- `src/boardwise/bridge/protocol.py`：ActionSpec，risk=read、design_write=False、参数/返回目录。
- `tests/test_551_pcb_net_class_list.py`：协议目录、参数、能力/旧 connector 边界和只读政策邻域。
- `docs/bridge.md`：动作表与能力边界；不改 CLI 合同，不新增 DSH 工具（先由 `bridge call` 验证）。

不改 daemon 路由业务、connector 版本号、绘制线、规则判定、checkup verdict 或真实工程。daemon/connector 热更与真机验收另批，当前运行中的 daemon 不重启。

## Negative controls

1. 非 PCB 焦点：PAGE_MISMATCH，零网络类读取、零切页。
2. `getAllNetClasses` 缺失或抛错：classes=null + missing/unreadable，不能返回空数组冒充无类。
3. `getNetRules` 缺失：netRules=null + 具名披露；classes 的可读事实不覆盖 netRules 的缺口。
4. classes=[] + netRules 非空：两者原样返回。
5. 只读调用序中不得出现 create/delete/modify/add/remove/save/overwrite；不得调用任何写 action。
6. NaN/Inf、Date、循环引用、过深/超长值按现有 sanitise 规则处理并披露，不能污染 JSON。
7. 旧 connector 无 capability 时不得被调用方当成支持。

## 验收与真实样本前提

- 离线：connector 全量测试与 typecheck、协议/action-catalogue/政策/文档合同聚焦、至少两处独立变异（空数组冒充、缺页 guard）先红并 cp+SHA-256 恢复。
- 真机另行等待：活动 test/test2 PCB，焦点可恢复，且板内至少一个真实网络类、两个成员网。调用前后 `pcb.drc_ruleset` 的 current 内容逐字不变，作为零写旁证。
- 当前 test/ROBOT 窗口都 active=null，且没有已确认的网络类样本；离线通过不得写成真机兼容或发布验收。


## 离线实际验收（2026-11-17，工作树未提交）

- Connector **821 passed / 0 failed**，typecheck 通过；新 action 12 条。Python 协议、只读政策、bridge、catalogue、环境与文档邻域 **339 passed**。
- 新 capability 已补入 `actions026b` 的既有全分支钉；`NOT_DESIGN_WRITES` 只新增本 action。审查时发现新批误给旧 `pcb.drc_ruleset` 加 `design_write=False`，已撤回该行，未用扩大白名单掩盖旧目录漂移；三段命名家族已显式登记本 action。
- 主代理变异 `count:null → 0`：第一次未重建 dist，变异无效，不记成功；重建后 **2 failed / 10 passed**，分别钉住 missing/throwing 不得伪造 0。随后 cp + SHA-256 恢复、重建 dist，12/12 恢复通过。子代理的空数组与去页 guard 变异也均先红并恢复。
- 没有新增 CLI/DSH 工具，没有改 daemon 路由、版本号或真实工程，没有重启/热更。旧 drc_ruleset 行为不变。

### 真机待办（下列 ROBOT 补验前的状态）

当前没有活动 PCB 与已确认网络类样本，daemon 也未加载新目录，因此 `getAllNetClasses/getNetRules` 的真实字段、classes 空/非空两态、daemon 端到端和调用前后规则集零变化均未验证。不得把上述离线读数写成真机兼容或发布通过。


## ROBOT 真实只读验收（2026-11-17）

岳点名在 `ROBOT ctrl FOC` 验证。先准备 0.6.1 回滚包，再以 `--no-reload` 写入 0.6.2 connector；岳点击扩展菜单后，新实例上报 `pcbNetClassList=true`。没有页面 reload、没有设计写、没有丢失未保存状态。

- `doc.focus` 精确进入 PCB1，`document.current` 确证后调用；finally 恢复 Start Page，恢复后 active=null 与原始状态一致。
- 实际 `classes=[]`、`count=0`、`netRules` 为 **49 条**对象，两个 reads 均 true，missing/unreadable 均空，jsonChars=19156。这是合同中的真实「classes 为空而 netRules 非空」负例，不是“读不到”。
- netRules 实测为 `type:"net"` 的记录，含 `name/targetNet` 及 Track、Via Size、Safe Spacing、Copper Zone、Plane Zone、Differential Pair 等约束键；原始值完整保存在本地 `.tmp_551_live/net-class-list.json`，公开文档不复制板级明细。
- 调用前后 `pcb.drc_ruleset.ruleset` **逐字相同**，jsonChars 均 7128，零写旁证成立。
- 因真实调用成功且无设计副作用，保留 daemon/ROBOT connector 0.6.2；0.6.1 回滚包仍留在 `.tmp_551_live/rollback/`。

**仍未覆盖**：至少一个非空网络类及其 `{name,nets,color}` 字段、非空 classes 与 netClass 规则的对应关系。当前样本只能证明空 classes + 49 条 netRules 的真实路径，不能宣称非空网络类已验。新增样本不得通过修改这块真实工程制造。
