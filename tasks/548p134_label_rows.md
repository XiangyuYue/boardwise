# 548P134 — 标签名称行联合重排

> 状态：**侦察完成，已定位跨网row-gap误伤，生产未改**。证据 `evidence/548P134/README.md`。
> 下一步只落同网名称行距过滤，见 `tasks/548p135_same_net_gap.md`。

## 已有事实

- 24个local-label move全部reserved，LCD_SCK/LED1/LED2 far均为10；
- 完图重选确实执行，但34个候选全部 `rowGapReject=True`，另有22个垂直中段、2个span失败、1个dedicated；
- 35/40的trial-box仅单条件合法，未满足同网名称行距，不能当成完整合法；
- 生产已恢复到drawcompiler `2bb3fceaea0f60ae4b5b7bb8d54c6340b2fe8871231151ede4c9490122cd85d3`，
  placement `f550f6eafa3d45b3c23a104925c3a9fa1c2d02f8424068bd31dfe8dba9859d60`。

## 唯一问题

候选名称行与哪些现有名称行发生冲突，是否必须在**标签列/行联合布局**中同时移动标签和3V3路径？

先记录每个被拒绝候选的 `row`、`other`、`gap`，找出主冲突对象；不得再用trial-box单条件放行。
优先复用 `_seat_first_port_columns`、`_local_label_trial_box` 和name-row尺，不能新建第二套标签解释器。

## 完成条件与停止线

- 先给主冲突对象及三种最小后续：联合移动标签列、调整3V3通道、保持现状具名拒绝；实测选择或停止。
- 新测试基线先红，至少两项变异先红并恢复；P43/WiFi geometry不变。
- 只有ok=True才逐脚/渲染/视觉；否则交真实首墙，不宣称整页完成。
- 仅 `.tmp_548p134/`、`evidence/548P134/`；不得改生产/tests/docs/tasks/输入、shared/review/bridge、
  P43/WiFi/P132/P133证据；不调reach/GAP/预算/排列/页框、统一拉长、恢复P124实验。
- 不移动删除、不Git写、不bridge/apply/真机/全量；子代理20分钟/40步，主代理独立复核。
