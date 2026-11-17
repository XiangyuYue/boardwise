# 548P144 — C1.2 固定地旗与标签房间

> 状态：规划，未实施。P142/P143 联合与CTS机制已验收，当前真实下一首拒是C1.2。
> 证据：`evidence/548P142/baseline-joint-foreign.log`、`evidence/548P143/README.md`。

## ① 前因后果

P142 的 detour+foreign 联合使 C3.2 与 C1.1/U1.13 的 BUZZ 冲突消失，P143 又使543i恢复出图。
但完整 `_build_one_variant` 仍拒绝：C1.2 固定terminal `(-165,5)` 被
`(-156,-16)-(-94,-14)` 的导体/房间及 `(-190,-9.5)-(-144,-0.5)` 的 LED1_K 名称盒覆盖。
这是固定旗与标签/导体的独立缺口，不能回到移动C1.2或修改portRoles。

## ② 当前树状态

HEAD `e32737a`。P143 drawcompiler `87f82009ca85109faacd0bbccddf5cb98ef7207201f1cdc47444caf3f5cd5473`，
placement `0674eb3842529fe280d06dc59c426f9eda7a1789cd0a1c35b86e89244596bb82`，
pagecompiler `28b2907d8904da9917a64d3015ae8fd37619313abfaf6a6ee3987e7763628e1c`。
P142/P143未提交实现保留，P125/P126/P59输入不变。

## ③ 文件域与禁触清单

先捕获C1.2 glyph/lead、两个占用盒的真实producer、LED1_K名称重选与U1.18标签关系，写
`.tmp_548p144/`、`evidence/548P144/`。若实现，只许draw线必要文件和一个新测试并先备份。
不得移动固定terminal、调reach/GAP/预算/页框、合并GND、新建builder/router、改shared/review/
bridge/connector/dsh-plugin、真实工程或fixtures。

## ④ 交付物与验收

说明哪个生产关系先决定C1.2冲突，给出三种最小改动和预测。若实现，新测试基线先红、
至少两项因果变异先红并Copy-Item+SHA恢复；P43/WiFi/543i/P126/P135/P137/P138/P141/P142/P143
不得退化。只有真实 `ok=True` 才逐脚、渲染和逐岛视觉；否则交下一真实首拒。

## ⑤ 纪律与红线

不把P142/P143机制成功写成整图通过，不把C1.2的固定seat移动、把名称删除或加xfail。
不做默认全量、真机、apply、移动/直删；Git写需另行批准。pytest独立basetemp，parallel只
`-n 4 --dist loadfile`。同一拒因两轮无新证据即停。

## ⑥ 预算与交卷格式

子代理20分钟/40步，主代理约60步内收束。报告命令→真实汇总行→差异、SHA、证据路径、
未做项和下一最小动作；不把拒绝前移当作完成。
