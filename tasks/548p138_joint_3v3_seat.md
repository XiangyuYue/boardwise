# 548P138 — 3V3 share:chain / share:part:U1 联合座位

> 状态：**3V3联合反馈已修复 / 完整整图未通过**。真实首次plans返回中第二次joint成功、chain=5；
> 完整候选首拒已前移为C3.2/BUZZ，下一批见 `tasks/548p139_ground_buzz_channel.md`。
> 证据：`evidence/548P138/README.md`、`evidence/548P138/full-candidate.log`。

## ① 前因后果

P126 已证明 C2 经 13→3→1 在 offset=0 达到5/5；P137 发现完整5/5方案被最早的 C2=13
拒绝覆盖，并以单一 drawcompiler hunk 修复。修复后真实 `_place` 返回 `placed=True`，但
`_build_candidate` 仍为 `built=False`：3V3 `share:chain` 与 `share:part:U1` 的每个候选
都相交。P127/P128 曾记录同类联合座位缺口，本批只在 P137 新首拒上继续，不重开 C2。

## ② 当前树状态

HEAD 仍是外部 review 提交 `3d4a0d5e666a36809babbfad7871021d84cea24a`，混合未提交工作树保留。
P138 后 drawcompiler SHA `24f13da5219243fa4ee7f881fc9fb7a982bde4210ec1df8559ab9be4d9c030b3`，
placement SHA `f550f6eafa3d45b3c23a104925c3a9fa1c2d02f8424068bd31dfe8dba9859d60`。
输入仍为 P125 电路 + P126 规格 + P59 库；不得用旧 P120/P123/P124 规格替代。

## ③ 文件域与禁触清单

先只读捕获 `_seat_first_groups`、3V3 chain/U1 候选 seat/path/lane 与冲突墙，写
`.tmp_548p138/`、`evidence/548P138/`。若需实现，只允许 draw 线必要文件和一个新测试，先备份。
不得改 shared/review/bridge/connector/dsh-plugin、真实工程、既有 fixtures、P125/P126 输入、
P43/WiFi/P135/P137 证据；禁止新建 builder/router、调 reach/GAP/预算/排列上限/页框、强制共旗、
恢复 P124 网格实验或移动 C3.2 来绕过本首拒。

## ④ 交付物与验收

提交每个3V3候选的具体 seat/path、与 U1 组哪一对象相交，以及三种最小改动和预测读数。
若实现，新测试必须基线先红，至少两项因果变异先红，Copy-Item+SHA-256恢复；主代理独立复核。
只有真实 `ok=True` 候选才做逐脚、渲染和逐岛视觉；否则交“机制状态+下一真实首拒”，不得称
MCU 或整图完成。

## ⑤ 纪律与红线

不做 Git 写、移动或直删；不跑默认全量、真机或 apply。pytest 用独立 basetemp， parallel 只用
`-n 4 --dist loadfile`。保留混合工作树与他人改动；P43/WiFi geometry、P126 5/5、P135 同网行距
不得退化。同一拒因连续两轮无新证据必须停止交接。

## ⑥ 预算与交卷格式

子代理最多20分钟/40步，主代理约60步内收束。交卷必须带命令→真实汇总行→差异、生产/输入SHA、
证据路径、未做项和下一最小动作；不得只写“测试通过”或把局部布局成功当整图通过。

## 实测交卷

- cheapest单脚seed一次反馈：首次chain17失败，第二次chain5、joint ok、expansions6；只多一次目标枚举。
- 新测试基线 `2 failed in 8.81s`，实现后 `2 passed in 14.05s`；M1 `2 failed`、M2 `1 failed, 1 passed`，均恢复SHA。
- 聚焦 `77 passed in 534.62s`；P43/P118 geometry均不变。
- 完整候选仍 `built=False`，首拒为C3.2固定地旗 `(-205,65)` 穿BUZZ通道 `(-301,84)-(-94,86)`；
  无整图候选，未做逐脚/渲染/视觉。
