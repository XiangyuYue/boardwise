# 548P139 — C3.2 固定地旗与 BUZZ 通道

> 状态：规划，未实施。P138 已使3V3联合座位通过，完整候选当前首拒C3.2/BUZZ。
> 证据：`evidence/548P138/README.md`、`evidence/548P138/full-candidate.log`。

## ① 前因后果

P136已用生产函数证明 `(-205,95)→(-205,65)` 穿过 `_seat_first_channel_walls` 为BUZZ生成的
`(-301,84)-(-94,86)`；当时C2/3V3更早失败，不能处理。P137消除C2回报遮挡，P138以一次
cheapest单脚seed反馈消除3V3联合首拒，现在同一C3.2冲突成为真实第一首拒。

## ② 当前树状态

HEAD `3d4a0d5e666a36809babbfad7871021d84cea24a`，混合未提交保留，绘制线历史批次另行整理提交。
drawcompiler SHA `24f13da5219243fa4ee7f881fc9fb7a982bde4210ec1df8559ab9be4d9c030b3`，
placement SHA `f550f6eafa3d45b3c23a104925c3a9fa1c2d02f8424068bd31dfe8dba9859d60`。
输入仍为P125电路+P126规格+P59库。

## ③ 文件域与禁触清单

先只读捕获C3.2固定terminal、BUZZ channel producer、可见房间与既有通道/支路约束，写
`.tmp_548p139/`、`evidence/548P139/`。若实现，只许draw线必要文件和一个新测试并先备份。
不得改shared/review/bridge/connector/dsh-plugin、真实工程、fixtures、P125/P126输入、P43/WiFi/
P135/P137/P138证据；禁止新建builder/router、调reach/GAP/预算/排列/页框、移动固定terminal、
强制共旗或恢复P124网格实验。

## ④ 交付物与验收

说明C3.2与BUZZ哪个生产关系先决定冲突，给出三种最小改动和预测。若实现，新测试基线先红、
至少两项因果变异先红并Copy-Item+SHA恢复；P43/WiFi geometry及P126/P135/P137/P138聚焦不得退化。
只有真实 `ok=True` 才做逐脚、渲染和逐岛视觉，否则交下一真实首拒。

## ⑤ 纪律与红线

不做移动/直删、默认全量、真机或apply；Git写只按用户已批准的分批整理计划执行。pytest独立
basetemp，parallel只用 `-n 4 --dist loadfile`。保留混合工作树中其他线改动，同一拒因两轮无新
证据即停止交接。

## ⑥ 预算与交卷格式

子代理20分钟/40步，主代理约60步内收束。报告命令→汇总行→差异、SHA、证据路径、未做项和
下一最小动作，不把joint/layout局部成功写成整图完成。
