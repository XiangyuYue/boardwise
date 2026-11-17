# 548P142 — service channel 与 rail 成员路径联合候选

> 状态：规划，未实施。P139 已证 C3.2 可绕，但静态 detour 与当前3V3 chain不能共存。
> 证据：`evidence/548P139/README.md`、`evidence/548P139/buzz-router-build.log`。

## ① 前因后果

P138 的 cheapest 单脚 seed 反馈只处理自动 rail 组之间的静态冲突。C3.2/BUZZ 要求改变 service
host channel：原 `_seat_first_router` 在 lead+glyph 障碍下能找到绕行并令 C3.2 通过，但随后
C1.1/U1.13 在 `(-160,85)` 与该 channel 共点，U1.18 名称盒也失败。把当前 chain 路径一并加入
router 障碍后 `route=None`。因此不能先定 channel 再让 chain 被动接受，也不能只提前拒绝。

## ② 当前树状态

HEAD `78e43da`，生产未改：drawcompiler `24f13da5219243fa4ee7f881fc9fb7a982bde4210ec1df8559ab9be4d9c030b3`，
placement `752ef00639f7c90c02a3c7bdc5be327f28d4d3a3995c8ff1909dd3b1161d3f11`。
输入P125电路+P126规格+P59库不变。历史cb44c2e/c80eb2c等已提交，不重复整理。

## ③ 文件域与禁触清单

先只读捕获 `_seat_first_signal_preflight`、`_service_channel_claim`、P138 `seat_blocked` 与
`_seat_first_paths` 对 detour 的消费，写 `.tmp_548p142/`、`evidence/548P142/`。若实现，只许
draw线必要文件和一个新测试并先备份。不得新建builder/router、调reach/GAP/预算/排列/页框、
移动C3.2固定terminal、合并GND、恢复P124实验或改shared/review/bridge/connector/dsh-plugin。

## ④ 交付物与验收

证明channel备选与chain候选是否能在**同一联合答案**里生成，至少保留：
- C3.2固定terminal不穿lead/glyph；
- BUZZ两端、net与host_path/通道墙/replay一致；
- C1.1/U1.13无BUZZ共点，3V3联合分配完整；
- U1.18名称盒拒绝若仍在，必须作为下一独立首拒，不掩盖。

若实现，新测试基线先红、至少两项因果变异先红并Copy-Item+SHA恢复；P43/WiFi geometry及
P126/P135/P137/P138/P141聚焦不得退化。只有真实 `ok=True` 才做逐脚/渲染/逐岛视觉。

## ⑤ 纪律与红线

不把单一detour当生产修复，不把预飞信号改成可穿越，不用手改坐标、skip/xfail或新搜索预算凑过。
不做默认全量、真机、apply、移动/直删；Git写需另行明确批准。pytest独立basetemp，parallel只
`-n 4 --dist loadfile`。同一拒因两轮无新证据即停。

## ⑥ 预算与交卷格式

子代理20分钟/40步，主代理约60步内收束。报告命令→真实汇总行→差异、SHA、证据路径、未做项和
下一最小动作；不把router路径存在写成整页候选，不把C3.2通过写成整图通过。
