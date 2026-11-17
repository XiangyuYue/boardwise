# 550A：PCB ARC 数据与几何前置核查

## 当前裁定

550 的 net-path 不因 ARC 存在而变绿。影响面研究 `.tmp_review_attribution/arc-impact.md` 证明：仓内唯一 PCB ARC 样本的 `angle=2.1761`，按度和按弧度会产生相差约 10 mil 的几何；切线、相邻外来铜和现有 DRC 都不能定单位。P3 几何接入前必须先做 P2 宿主只读核查。

## P2 只读宿主探针

唯一目标是判断归档 ARC 的角度单位与方向，不创建、修改、保存或删除任何图元。

- 窗口：`ROBOT ctrl FOC`，实例以当次 `bridge status` 为准；只读真实工程，绝不是写白名单试验场。
- 先用 `doc.list` 逐字核对工程与活动原理图页，记录原页 uuid 和 PCB uuid。
- `doc.open` 仅切换至该 PCB；`document.current` 确证后，以 `pcb.readback(includePrimitives=true)` 读取既有 ARC 的 `ArcAngle/start/end/layer/net` 等字段。
- 与原归档 `.epro2` 的同一 ARC 对照。官方 `getState_ArcAngle` 的类型文档以度表示；宿主返回若与归档数值不同，按实际证据判断，不预设结论。
- finally 中 `doc.open` 回原原理图页并再次 `document.current` 核 uuid；任何失败都保留原文，不盲目重试，不保存。

完成条件：得到 ARC 的宿主数值与归档数值对照，并恢复焦点。若 readback/身份不成立，只交付失败证据，不做 P1/P3 生产改动。

## 后续分阶段（不在本探针中实施）

- P1 数据模型：仅在能明确证明价值时加入 `ArcGeometry`/清单，不为了“支持率”改变 equality/summary。
- P3 几何：只有单位与方向定死才立项；DOT/CENT、零角、非铜层、无网弧分别验收。正路径禁止单弦和外切包络；折线若使用必须证明子集关系并披露矢高。
- 已知事实：ROBOT 的目标焊盘对即使补上 ARC 仍无 pad/track/via 路径，还受 pour 与 via-in-pad 边界约束，不能承诺 ROBOT 变 CONNECTED。


## P2 实际结果与 P1 许可（2026-11-17）

`ROBOT ctrl FOC` 的 `doc.list` 与 `document.current` 均返回 `active=null`、`typeSource=none`；只看到 Start Page、P1.Schematic1、PCB1 tabs。虽然 bridge status 的缓存页给出原理图 uuid，但它不能代替直接活动文档证据，也不能保证探针后恢复原状态，因此未执行 `doc.open`、未读取或修改设计。P2 角度单位/方向仍阻塞，等待可恢复的活动 PCB 窗口。

在此前提下，只允许 **P1 数据模型**：`ArcGeometry` 原样保存 id/net/layer/start/end/angle/width/arcType 等字段，明确 angle 单位未验证，不计算圆心、半径、切线、长度或交点。ARC 可以按 net 分组，以便 net-path 只在**同网 ARC**时降级；不得进入 `_net_shape_records`、distance/touching、track_length、bbox 或任何正路径。既有 `element_count` 等旧聚合口径保持不变，另给 arc 计数披露。

P3 继续禁止，直到 P2 取得宿主角度证据。P1 完成不等于 ARC 几何兼容，也不保证 ROBOT 的否定查询变成 NOT_PROVEN。


## P1 实际验收（工作树未提交）

- `ArcGeometry` 原样保存 ARC，Board/Net 按 net 分组；`element_count`、track length、bbox、`_net_shape_records`、used layers 等旧聚合不变。`summary.arcs` 只在非零出现。真实样本 ARC=1、unconsumed ARC=0，字段逐项一致。
- net-path 只在同网且可能为铜的 ARC 时以 `arc_geometry_unsupported` 降级；非铜层进 ignored，旧手写 stats 仍有 `arc_copper_unparsed` 回退。ROBOT 查询仍为 INDETERMINATE，且仍有 pad_via_contact，未宣称转绿。
- 新测试 17 条；主代理最终组合 **726 passed / 1 skipped in 58.16s**，仓库卫生 **4 passed**。首次组合因主代理写错测试文件名 exit 5，修正为 `test_126a_pcb_review_plumbing.py` 后重跑，未把该次当业务失败。
- 主代理把 parser 临时改成 `math.radians(angle)`，原始值测试 **4 failed / 13 passed**，cp + SHA-256 恢复；子代理的 net 分组和全板 ARC 降级变异也均先红并恢复。
- 格式文档 `docs/epru-format.md` §6.11 已同步。P3 几何、真实 V4 ARC、CENT 样本和在线角度核查仍未覆盖；KiCad 既有弧摊平不在本批改动。
