# 548P132 — LCD_SCK local-label carrier 梯级

> 状态：**侦察完成，预留与名称盒不一致，生产未改**。证据 `evidence/548P132/README.md`。
> 下一步只修预留carrier与最终名称盒一致性，见 `tasks/548p133_reserved_label_alignment.md`。

## 已有事实

- 预飞信号约束使BUZZ、LED1_K冲突消失，chain与三信号段逐段交叉为0；
- 同一placement重试仍有LCD_SCK短载体无合法名称终点、LCD_SCK/LED2_K压宿主通道、
  C1.1/U1.13穿LED2_K；
- 失败布局标签全部钉死后chain=0，不能靠固定标签或豁免交叉解决。
- P109已证明同类载体在 `labelPolicy.stubMin=40` 下仍实际取10，不能假设40已生效。

生产与输入不得改：drawcompiler `2bb3fceaea0f60ae4b5b7bb8d54c6340b2fe8871231151ede4c9490122cd85d3`，
placement `f550f6eafa3d45b3c23a104925c3a9fa1c2d02f8424068bd31dfe8dba9859d60`，P125/P126规格。

## 唯一问题

LCD_SCK（U1.19）在 `(-95,-25)` 的local-label exception为何选择到 `(-105,-25)` 的10单位短桩，
并且该终点没有合法名称盒？

只读捕获现有local label/carrier梯级：40至10各档的候选、实际拒墙、label bbox变化和
`labelPolicy.stubMin` 的消费点。对比P109 `evidence/548P109/` 的LCD证据，但不改P47或照抄坐标。
明确是梯级被提前截断、预留不一致，还是后续名称盒避让无座。

## 文件域与停止线

仅 `.tmp_548p132/`、`evidence/548P132/`。不得改生产/tests/docs/tasks/输入、shared/review/bridge、
P43/WiFi/P130/P131证据。禁止调reach/GAP/预算/排列/页框、扩大桩长凑过、强制共旗或恢复P124实验。
不移动删除、不Git写、不bridge/apply/真机/全量。

交卷需给各档候选与首个真实拒绝、三种最小后续及预测；只有ok=True才逐脚和视觉。
子代理20分钟/40步，主代理独立复核。
