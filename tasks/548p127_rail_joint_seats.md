# 548P127 — MCU 3V3 联合旗位（P126后单缺口）

> 状态：**侦察完成，三种分组路线均证伪，生产未实施**。最终证据 `evidence/548P127/README.md`。
> 后续只查同网旁组引脚与通道，见 `tasks/548p128_member_corridors.md`；不重开服务顺序、GND分组、WiFi或P43。

## 基线与首拒

- 输入：`evidence/548P125/circuit.full.g3c.pinmap.json` +
  `evidence/548P126/full.presentation.service-feedback.json`。
- 生产：drawcompiler `2bb3fceaea0f60ae4b5b7bb8d54c6340b2fe8871231151ede4c9490122cd85d3`；
  placement `f550f6eafa3d45b3c23a104925c3a9fa1c2d02f8424068bd31dfe8dba9859d60`。
- P126已证明C1/C3/BZ1/C2/R1按声明顺序、C2经13→3→1达到5/5服务落座。
- 完整variant反向复算 `.tmp_548p126/custom-full-baseline.log`：GND固定终端共席已消失；
  3V3 `share:chain` 的每个候选都站在U1组候选上，U1.12/15级联未分配，仍无候选。

## 文件域与禁触

先只读捕获 `_seat_first_groups`、3V3各候选seat/path/lanes及冲突对象，写 `evidence/548P127/`、
`.tmp_548p127/`。实现若必要只允许draw线相关文件与一个新测试；不得改shared/review/bridge、
P126输入、P43/WiFi证据、既有fixtures。禁止调reach/GAP/预算/排列上限/页框、强制共旗、
新增builder/router或恢复P124网格实验。

## 完成条件与负控

1. 先用真实MCU候选数据说明是哪一条seat/path与U1组哪一对象冲突，给出三种最小改动及预测；
   同一拒因不得连续两轮无新证据。
2. 新测试基线先红，至少两项变异先红后Copy-Item+SHA恢复；不能仅断言helper被调用。
3. P126五条服务支路保持5/5和宿主序列；P43/WiFi原geometry不变；相关聚焦无新增红。
4. 只有`ok=True`才做逐脚与渲染视觉；否则交“侦察/机制状态 + 下一最小首拒”，不宣称MCU完成。
5. 不默认全量、真机、apply或Git写；子代理20分钟/40步，主代理独立验收。
