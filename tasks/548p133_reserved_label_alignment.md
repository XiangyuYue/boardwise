# 548P133 — 预留 carrier 与最终名称盒一致性

> 状态：**未验收，已回退**。完图重选34/34被rowGap拒绝且没有测试，生产已恢复P133前基线。
> 证据 `evidence/548P133/README.md`；下一步只做标签名称行联合重排，见 `tasks/548p134_label_rows.md`。

## 已有事实

- LCD_SCK的10来自 `_lead_lane_reservations` preplan，reserved分支跳过普通梯级；
- 原10的左向盒被宿主通道/其他名称行挡住，其余方向撞MCU本体；
- 15/20/35/40均有合法路径；35/40的一档下方名称盒合法；
- preplan35只消除“无名称盒”，裸标签压宿主通道仍在，不能只改长度或普通far+box回退。
- 生产与输入不得改：drawcompiler `2bb3fceaea0f60ae4b5b7bb8d54c6340b2fe8871231151ede4c9490122cd85d3`，
  placement `f550f6eafa3d45b3c23a104925c3a9fa1c2d02f8424068bd31dfe8dba9859d60`，P125/P126规格。

## 唯一问题

预留 `_lead_lane_reservations` 接受的路径与 `_local_label_carriers` 最终名称盒不一致：
预留只保证导线/name-row可用，最终trial-box却被宿主通道、其他名称行或本体占满。
需要在**同一预留链**内让far、carrier、最终标签盒一起合法，或让标签列选择与它们一致，
不能事后把失败留给path-first。

## 完成条件

1. 先确定在哪一层重放/修正预留，不能新建第二套标签解释器；reserved/input-wire和stubMin行为不变。
2. 新测试先在基线红：preplan合法但盒无座时应重选或具名拒绝，不得接受矛盾预留；
   真实MCU至少消除LCD_SCK的同类不一致，不隐藏LED2_K等独立冲突。
3. 两项变异先红并Copy-Item+SHA恢复；P43/WiFi geometry不变，相关聚焦无新增红。
4. 只有ok=True才逐脚/渲染/视觉；否则交机制结论与下一首拒，不宣称整页完成。
5. 子代理20分钟/40步，主代理独立复核；不默认全量、真机、apply或Git写。
