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
