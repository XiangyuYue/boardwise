# 562C：在线多跳路径真机激活与对拍（不做 DSH）

## 1. 前置与范围

562A/B 已完成并通过聚焦验收。岳要求除 DSH 适配外全部完成，因此本批只做真实宿主激活、只读正反例与同会话离线对拍，**不注册 DSH 工具、不 bump/pack/deploy、不发布**。

真实宿主与容器身份只留本地 `.tmp_562_live/`，公开证据只写匿名读数。所有操作只读设计，不自动切页、不创建/修改/删除图元；恢复原焦点。禁止 `getEntireTrack` 正证据。

## 2. 激活纪律

1. 先 `bridge status` + `doc.list` + `sys.connector_status`，核对真实焦点、daemon/connector 版本与 bootstrap/activate 实例，不能用版本字符串相同推断新 action 已加载。
2. 直接试 `pcb.path_probe` 的封闭 action；旧 daemon 的 `unknown action` 或旧 connector 的 `no handler` 只作失败史。
3. 需要激活时：重建 connector、更新开发态 daemon 与 connector bundle，随后由岳完整重启 EDA。菜单点击只增 evaluations 不算激活；必须以新实例的 bootstrapAt/activateAt 和目标 action 行为回读为准。
4. daemon 重启只动开发态进程，不碰真实工程文件；EDA 重启前不得关闭未保存设计，必要时由岳亲自执行。

## 3. 同会话样本选择

在当前已授权的非空 PCB 上，先导出同会话归档到 `.tmp_562_live/`，用离线 550 与只读 host 图元探针共同选择：

- A：direct 正例（可复用 559 的 LED1.2→U10.2 身份，若当前板仍一致）；
- B：至少两根 Line 的多跳正例；
- C：经过 Via 的正例（若板内存在）；
- D：离线 550 判为 NOT_PROVEN 的分离铜分量负例（可复核 C22.1→C23.2，若语义仍一致）；
- E：Pad↔Via 接触披露样本（若存在），验证它不进入正路径；
- F：Arc 只在有明确邻接正例时启用；无样本保持 `arc-unverified`，不得找替代图元冒充。

真实 ref、ID、容器和板名只写本地文件。在线/离线使用同一时刻导出，不能拿不同导出的原始 ID 硬比对。

## 4. 验收判据

- A/B/C 的 `CONNECTED` 必须有有序 path/hops；每个 hop 有 typed from/to、method、callIndex、hostOrder，中间邻接有双向证据；hopCount/viaCount 与 path 一致。
- D 只有在图完整、无 unknown/errors/truncation/frontier 时才允许 NOT_PROVEN；任何缺口为 INDETERMINATE。NOT_PROVEN 仍不解释为开路。
- E 的 Pad↔Via 只在 unknown 中披露，不得成为 hop。
- Arc 无真实证据时不得成为 path 节点。
- 查询后恢复焦点、设计写为零；出现非 PCB 焦点必须 PAGE_MISMATCH 且零组件/图元读取。
- 若真实宿主几乎全部单向邻接或读取语义与 fake 不同，先记录实际返回并回到合同，不得删双向规则或改 fake 凑绿。

## 5. 完成定义与边界

完成本批需要：新 action 原生激活成立、A/B/C/D/E 的实际读数、同会话离线对拍、焦点恢复与设计写零、证据落盘。V3、其他板型、CBB 内部、多板自动选择未覆盖；Arc/Pad↔Via 未获真实语义前不支持。

562A/B 的全量 Python、Connector、DSH 与 Rust 读数另记，不能用这些离线读数替代真机。DSH 适配明确不做。


## 6. 对抗审查追加：跨层语义只读探针

只读审查指出当前合同只比 type/net，没有定义跨层邻接。真机必须追加：

- 若板上存在同网跨层交叠但没有过孔的 Line，分别读取两端 layer 与双向 `getAdjacentPrimitives`，判断宿主是否把跨层交叠报成邻接；不能仅按几何推断 API 语义。
- 记录 Via 的有效层读数，不能用单层字段猜盲埋孔连接。
- 若宿主确实把无过孔跨层交叠报成邻接，先回合同增加 cross-layer 负例再修生产；若宿主只报真实连接，则记录该语义，不为 layer=null 的正路径额外造拒绝规则。


## 7. 实际完成（2026-11-21）

- 新实例 `inst-001605508-glojp393` 激活成立。direct CONNECTED；多 Line＋Via CONNECTED（hopCount=8、viaCount=1、内部图元与离线一致）；分离负例 NOT_PROVEN；U5.2 的 Pad↔Via 接触为 INDETERMINATE，没有进入正路径。
- 20 组同网跨层几何接触候选的双向邻接均为 0 条直接跨层边，没有新增 cross-layer 生产规则。Arc 无正例，保持 unsupported。
- 非 PCB 焦点 exit 3/空 stdout，原 P1 焦点恢复，设计写为零；开发态 daemon 已停止。公开证据 `evidence/562c/live-acceptance.md`，本地原始证据 `.tmp_562_live/`。
- 最终 Python **35 failed / 11997 passed / 26 skipped / 2 xfailed / 3 errors**，与上轮仅移除 shared owner 计数红、added=[]，其余归绘制线；Connector 876、DSH 218/1、Rust 177/4 ignored 均通过。**562C 真机完成，DSH 适配明确不做。**
