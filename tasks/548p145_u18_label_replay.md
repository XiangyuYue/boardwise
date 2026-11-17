# 548P145 — U1.18 名称盒与标签回放

> 状态：规划，未实施。P144 已把固定glyph纳入port-columns场景，C1.2消失；当前首拒为U1.18。
> 证据：`evidence/548P144/fixed-glyph-scene.log`、`evidence/548P144/README.md`。

## ① 前因后果

P142/P143 联合与CTS机制通过，P144进一步把C1.2固定terminal的房间提前给标签/载体避让。
当前完整 `_build_one_variant` 首先报：U1.18 `(-95,-15)` 的local-label exception无合法名称盒；
同时LCD_SCK、LED2_K与panel host channel、C1.1/U1.13与LED2_K标签存在后续冲突。
这是名称/载体与最终回放的独立问题，不能回到移动C1.2或删除名称。

## ② 当前树状态

HEAD `108e42d`。P144 drawcompiler `976a4c2cad08804f994466419950e498aae2296a49de0b87536a72a7a653b2ea`，
placement `0674eb3842529fe280d06dc59c426f9eda7a1789cd0a1c35b86e89244596bb82`，
pagecompiler `28b2907d8904da9917a64d3015ae8fd37619313abfaf6a6ee3987e7763628e1c`。
P142/P143/P144未提交实现保留，P125/P126/P59输入不变。

## ③ 文件域与禁触清单

先捕获U1.18 far/bbox/run、LED2_K/LCD_SCK channel与name replay、C1.1/U1.13路径冲突，写
`.tmp_548p145/`、`evidence/548P145/`。若实现，只许draw线必要文件和一个新测试并先备份。
不得移动固定terminal、删除名称、调reach/GAP/预算/页框、合并GND、新建builder/router、改
shared/review/bridge/connector/dsh-plugin、真实工程或fixtures。

## ④ 交付物与验收

说明U1.18为何无合法run/box，给出三种最小改动和预测。若实现，新测试基线先红、至少两项
因果变异先红并Copy-Item+SHA恢复；P43/WiFi/543i/P142/P143/P144及P126/P135/P137/P138/P141
不得退化。只有真实 `ok=True` 才逐脚、渲染和逐岛视觉，否则交下一真实首拒。

## ⑤ 纪律与红线

不把C1.2通过写成整图通过，不把名称从引脚删掉或加xfail，不把不同网标签当可共享。
不做默认全量、真机、apply、移动/直删；Git写需另行批准。pytest独立basetemp，parallel只
`-n 4 --dist loadfile`。同一拒因两轮无新证据即停。

## ⑥ 预算与交卷格式

子代理20分钟/40步，主代理约60步内收束。报告命令→真实汇总行→差异、SHA、证据路径、
未做项和下一最小动作；不把首拒前移当作完成。
