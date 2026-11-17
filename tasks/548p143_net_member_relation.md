# 548P143 — 多成员网端点不可由单一坐标裁决

> 状态：**CTS/543i 已恢复出图并通过验收；多成员声明边的视觉合理性未证明**。
> 证据 `evidence/548P143/README.md`。本批未提交，不改 portRoles、夹具、默认边或加 xfail。

## ① 前因后果

P141 已修 `_repair_delta` 对无 origin 端点的崩溃，但 net→part 的度量仍把“同一零件引脚+origin”
当成可平移关系，CH343 八条跨模块信号在拓扑搜索与最终关系闸中反复拒绝。用户裁定：
多成员网没有唯一几何端点，返回 None；单成员保留 P107 合同，缺省调用不变，零件↔零件不变。
镜像、角色和断言都不能用来掩盖这个度量边界。

## ② 当前树状态

起点 drawcompiler 为 P142 修复版 `34e43bd…`，placement 为 P141 `752ef006…3f11`。
最终 drawcompiler `87f82009ca85109faacd0bbccddf5cb98ef7207201f1cdc47444caf3f5cd5473`，
placement `0674eb3842529fe280d06dc59c426f9eda7a1789cd0a1c35b86e89244596bb82`，
pagecompiler `28b2907d8904da9917a64d3015ae8fd37619313abfaf6a6ee3987e7763628e1c`。
P142 未提交实现保留；其他 review/netpath 工作不动。

## ③ 文件域与禁触

生产：`placement.py`、`drawcompiler.py`，以及仅用于根成员表传递的 `pagecompiler.py`。
测试：`test_548p143_net_member_relation.py`、543i、098 两条拒报钉。备份 `.tmp_548p143/`，
证据 `evidence/548P143/`。不得改 shared/review/bridge/connector/dsh-plugin、真实工程、fixtures、
portRoles、镜像、默认边或新预算。

## ④ 实现与验收

- `relation_points_between` 新增可选 `net_members`：>1 返回 None，=1 保持核心引脚+origin，
  未传保持旧行为；两个 net→part 方向一致。
- `relation_points` 使用 PlacementInput 末尾的可选映射；缺省回退到 request.nets。
- `_points_for_relation` / `check_grammar` 同步映射。页编译将根电路成员表传给模块编译，
  模块零件、位姿和 `net.members` 切片不变；跨模块关系按用户确认的“根成员数”处理。
- P141 两种 which 守卫原样保留。

实测：定向基线 `6 failed` → `6 passed`；完整543i 基线 `2 failed, 7 passed` → **9 passed**。
M1 `>0`：`2 failed, 7 passed`（单成员变红）；M2 drawcompiler漏传：`2 failed, 7 passed`
（543i回到CTS）。均Copy-Item+SHA恢复。P107/P201B/P126/P137/P138/P141为 `89 passed`，
098重钉后 `23 passed`，最终543i/P143/P141 `18 passed`；P43/WiFi geometry不变。

## ⑤ 纪律与风险

不改 `_PIN_KINDS`、`class_of`、零件↔零件分支、portRoles、镜像或默认边。多成员声明边不再
形成硬约束，页面会恢复 `cb44c2e` 之前的行为：这是恢复合法输入出图，不等于声明边视觉合理，
`_ORIENTATION_CONFLICT` 仍只作 note。scene08 仍 `ok=False`、`candidates=0`；经用户批准只更新
拒报基线（`68340ef2…`→`88c8e198…`），不得写成通过。

## ⑥ 实测交卷与下一步

精确diff和日志在 `evidence/548P143/`。P142 联合 detour 回归 **3 passed in 253.33s**；
其 C1.2 仍是整图下一独立首拒。
本批不宣称30件整图完成、不宣称全量四线或视觉通过；新提交需另行明确批准，不push。

## ⑦ 最终语义（主代理裁定）与双向负例

**net→part 的次序关系是姿态偏好，不是页面硬闸。** 该关系量的是「object 自己在该网上的引脚」与
「object 的 origin」——两点同属一个零件，平移同时移动两点，548P141 已明确拒绝把它当可平移修复
的对象；因此它**不可能被摆布满足**，只能表达「这个符号的引脚本来朝哪边」。把它当页闸，等于用
符号事实去拒一份合法输入（CH340/ESP/CH343 的 `right-of(TXD,U)`、`left-of(BOOT0,U1)` 全被逐 variant 拒）。

**保留的度量（不倒退）**：`relation_points_between` 的单成员读法（P107：核心引脚 + origin）与
多成员「无唯一端点 → None」（P143）都不动；搜索仍可拿这份度量作姿态偏好。
**保留的硬判**：零件↔零件次序关系（两个 origin 可以分开摆，真的存在「摆错」）继续硬拒。

**为什么不能拿 P107 的度量结果当页面硬闸**：P107 钉的是「尺子怎么量」，不是「量出不符就拒页」。
同一份度量在两个消费者手里含义不同——搜索拿它当偏好（可影响选哪个变体），闸门拿它当判决
（一个变体也不给）。对不可修复的关系，判决只有一个结局：全拒。所以闸门在
`drawcompiler._relation_violations` 对该类关系不产出 violation（多成员本已 None）。

**双向负例**（`tests/test_548p143_net_member_relation.py`）：

- `test_the_gate_does_not_refuse_a_single_member_net_endpoint` —— 单成员网、声明边与引脚相反：
  尺子仍量出 `((45,5),(0,0))`，`_relation_violations` 返回 `[]`。
- `test_the_gate_does_not_refuse_the_reversed_part_to_net_order` —— 端点序反过来（`right-of(U1,DSR)`）
  同样 `[]`。
- `test_the_gate_still_refuses_a_part_to_part_order` —— `left-of(C3,U1)` 仍返回 1 条 violation，
  两点为两个 origin：证明这是定向豁免，不是关掉整类秩序关系。

实测：`test_548p143 + test_548p107 + test_548p141` → **16 passed in 0.50s**。
变异（把 skip 条件改成 `if False and …`）→ 两条 net 端点负例 **2 failed**，零件↔零件那条仍绿
（`2 failed, 7 passed in 1.85s`）；`cp` 还原后 `drawcompiler.py` sha256
`976a4c2cad08804f994466419950e498aae2296a49de0b87536a72a7a653b2ea`（与变异前逐字节相同）。
相关页面回归：`test_548l_pending_corridor + test_548d_series_reservation` → **11 passed in 42.40s**。
