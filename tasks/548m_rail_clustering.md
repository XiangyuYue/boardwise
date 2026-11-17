# 548M：同网轨旗聚簇（power 也走簇；默认关闭）

日期：2026-11-14。owner：绘制线。前置 548K/548K-R、548L。证据 `evidence/548M/README.md`。

## 1. 一个缺口

548L 之后校准 WiFi 页机器全过，但 `3V3` 一颗网 6 枚旗、三枚挤在去耦对上方（间距 7.2 单位）。
岳的人工 P44 依据页是「三件共享一条短轨 + 一枚旗」。仓库里 GND 已有这套聚簇能力
（`gndClustering.radius`，053E），但只对 GND 开；`boardwise-draw` skill §5A 说 power 逐脚 /
GND 聚簇的分歧不是合法视觉裁决。

## 2. 改法（复用 535 既有聚簇链，不新建规划器）

1. `core/presentationspec.py`：顶层可选 `railClustering: {"radius": N}`，形状/校验照抄
   `gndClustering`（只许 radius、必须正有限、缺省不写不序列化、非法值具名拒绝），落
   `rail_cluster_radius` 并进 `CompileBudget`。
2. `engines/drawcompiler.py`：
   - `_expression_style` 的 power 分支新增首条：`rail_cluster_radius > 0` 且 `count >= 2` → `wire`
     （理由文案写明"文档声明 railClustering"）。**053 sec.7 的默认裁决一行未动**；
   - `_cluster_radius_for` 收窄为 `net_cls == "power"`，`railClustering` 不碰 GND；
   - 下游逐簇绘制（535）一行未动。

## 3. 验收（已过）

- 真件：`compile ok=True`、`crossings=0`、`3V3` 旗 **6 → 3**（`(280,765)`、`(430,750)`、`(120,750)`，
  每簇短轨 + 簇号注记）、`GND` 仍 1 枚 `(350,730)`。
- 默认关闭：不写 `railClustering` → 几何 `8802d317cfae…` 与 548L 记录**逐字节相同**。
- 变异：M-M3（去掉样式分支）→ 3V3 回到 6 枚、正例 1 failed；M-M1（去网类门控）→ 整页 `ok=False`
  + 2 failed；M-M2（半径恒 0）→ 6 枚。均 cp+sha256 还原（`54364928…225818`）。
- 聚焦 11 文件 **146 passed**（主代理自跑）。

## 4. 视觉：部分改善，**仍判废**

旗域按岳 P44 的形状改善了；但 `ESP_RST` 仍从 J2.7 向下绕到 y=785 再横穿底边回来 —— 根因是
服务件 R4 本体坐在 y=695 的直线上。属结构性瑕疵，本批不处理。

## 5. 不做 / 下一批

不改页框/`near`/`max_nodes`/GAP/字号；不改 `_gnd_clusters` 判据；不碰 service 页；不 git 写、
不删除、不真机。下一批：让 placement 看见"两脚 wire 网的直线走廊"（548L 思想的上一层），
或降低该绕行的代价等级；两条都在既有决策链内，不新建规划器。
