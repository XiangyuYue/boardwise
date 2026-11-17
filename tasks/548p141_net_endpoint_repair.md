# 548P141 — 网/端口端点不可平移修复

> 状态：**DSR 崩溃已修复 / 543i 后续 CTS 输入矛盾未解决**。证据 `evidence/548P141/`。
> 本批只改 `placement.py` 一处 `_repair_delta` 守卫与一个新测试，未提交。

## ① 前因后果

历史绘制批次由用户的 `cb44c2e` 一次性落地，HEAD 随后为 `4271fea`。提交前集成复跑发现
13 个同源红项，其中 tracked `test_543i_visible_labels.py` 在 topology anneal 中索引
`origins['DSR']` 崩溃。判因证明 DSR 是网名，关系是合法的网→核 `left-of(DSR,U1)`，
两端测量点都随 U1 平移，不是可平移修复的零件↔零件关系。

## ② 当前树状态

修复前 HEAD `4271fea`（0.6.2 prep），drawcompiler `24f13da5…c030b3`、placement
`f550f6eafa3d45b3c23a104925c3a9fa1c2d02f8424068bd31dfe8dba9859d60`。
历史 `cb44c2e` 与 release prep 已存在，不再执行原P140六批提交。工作树中其他线文件不动。

## ③ 文件域与禁触

只允许 `src/boardwise/engines/placement.py`、新 `tests/test_548p141_net_endpoint_repair.py`、
`.tmp_548p140/dsr-*` 与 `evidence/548P141/`。不得改drawcompiler、输入、fixtures、shared/review、
543i页声明、其他红项或文档；不得Git写、移动/删除、全量、真机/apply。

## ④ 交付物与验收

`_repair_delta` 在任一端点无 origin 时返回 None，两个 `which` 均覆盖；零件↔零件delta不变。
新测试基线 `3 failed`，修复后 `3 passed`；M1删守卫、M2只守一端均 `2 failed, 1 passed`，
Copy-Item+SHA恢复。placement/P126/P137/P138聚焦 `69 passed`；P43/WiFi geometry不变。

## ⑤ 纪律与边界

不在6130简单吞KeyError、不过滤原关系、不改RNG流、不调阈值。543i修掉崩溃后仍因CTS输入脚侧
与库/规格矛盾而 `presentation-poor`，本批不擅自改库或sidePreferences；cross-side/forced/K/L/
P16等其余红项分批处理。未做整图/视觉/真机。

## ⑥ 实测与下一步

- 修复后 placement SHA `752ef00639f7c90c02a3c7bdc5be327f28d4d3a3995c8ff1909dd3b1161d3f11`。
- 543i两条后续测试仍为 `2 failed`，明确是 `left-of(CTS,…)`，不再是 `KeyError: DSR`。
- 下一最小动作：先由owner裁定CH343G引脚侧/规格表达，再处理其他测试钉和生产缺口；
  新提交需另行授权，不push。
