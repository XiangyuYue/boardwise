# 548L：旗位决策看见「还没走的直线走廊」（批次2）

日期：2026-11-14。owner：绘制线。前置：548K（`tasks/548k_stub_floor.md`，机制已落、图判废）。
基线：`drawcompiler.py` 工作树版本 `6351A85E…`（548K 收口点）。

## 1. 一个缺口

编译器自己点名的一句话：`net ESP_EN: wired route not found; labelled instead`、
`net ESP_RST: wired route not found; labelled instead`。这两条是 **`style=wire`、两脚**
的宿主本地网（探针原文：`ESP_EN J2.EN(35,-5) → R4.2(215,-5)`、`ESP_RST J2.RST(35,5) → R5.2(275,5)`），
本该是一条直线，结果被画成两截各自带名的裸长桩（200/80 单位）。

挡在直线上的不是"没有空间"，是**一枚具体的旗**：

| 走廊 | 阻挡物（探针 `.tmp_548k_lead/probe_corridor.py` 原文） |
|---|---|
| `ESP_EN` (250,685)→(430,685) | GND 旗图形盒 `(310,680)-(330,699)`、GND 引线 `(320,705)-(320,680)` |
| `ESP_RST` (250,695)→(490,695) | 同一枚旗盒 + 同一条引线 |

去耦那枚地旗按"就近挂在自己焊盘旁"落在 `C8.2` 下 25 单位，正好横在模块右列引脚与服务支路之间。
**规格侧无解已反证**：加 `gndClustering:{"radius":100}` 同一候选逐项不变。

## 2. 改法（复用既有预留链，不新建规划器）

`_lead_lane_reservations` 的第一趟已经在给"成品图一定会画的引线"预留车道（旗引线、标签桩、
wire 网的旗）。缺的是同一件事的第四类：**一条 `style=wire`、恰好两脚的网，它那条直线本身**。

所以：在同一个函数里、旗位与标签轮到之前，把这些网的直线走廊按
`_lattice_nodes(point_a, point_b)` 预留进 `router.reserved`（`_take_lane`，own = 该网自己，
因此只墙别的网，不墙自己）。路由本来就会绕开 `router.reserved`；旗位用的
`_flag_room` / `_flag_wire_ruler` 也读同一份 —— 于是旗自己让到走廊之外，两条网就能成线。

门控与 548K 相同：`_stated_stub_floor(ctx.presentation) > 0`（文档声明了 `stubMin`）。
**不写这个键的页不受影响，逐字节不变。**

## 3. 验收（写死，缺一不交）

1. **正例**：校准 WiFi 件（`evidence/548J/wifi-canvas/` 的 calibrated circuit + library +
   `wifi-island.clean.j2-below.presentation.json`）编译后，`ESP_EN`/`ESP_RST` 的 note 里
   **不再出现** `wired route not found`；计划里这两条网各是**一条可见导线**（不是两截带名桩），
   且 7 个网络分区、17/18 脚连通（`J2.IO2 = NC`）不变。
2. **默认关闭**：同一件删掉 `stubMin` 一键 → 几何与 548K 收口的默认页读数一致（或均 0 候选时
   如实记录），不得"顺手"改变没声明该键的页。
3. **两项独立变异**（cp 备份 + sha256 还原，禁 git restore）：
   - 去掉走廊预留 → 正例必须退回 `wired route not found`；
   - 去掉门控（无条件预留）→ 必须能观察到至少一个既有页几何变化（证明门控是承重的，不是装饰）。
4. 聚焦邻域：548J 三件 + 548K 两件 + 053f + 543i + 540 CLI + 056 + 548D panel + owner/layer +
   doc claims，记录 passed/skipped。
5. **视觉**：本批必须渲染目检并给出逐岛四问；未过视觉就只能记"候选/判废"，不得写完成。

## 4. 不做

不新建 builder/路由器/旗位器/页锚；不改 `placement.py`；不改页框、不调 `near`/`max_nodes`/GAP/
`stubMin`；不用 `userLocks`/参考坐标/缩字；不碰 review 线文件；不 git 写、不删除、不真机；
不宣称 548J/548D/548E/547G 完成。

## 5. 结果（2026-11-14，**机器过、视觉判废**）

- 改法落地：`_reserve_pending_runs` + 在 `_lead_lane_reservations` 预留趟按
  `_stub_lane_reserved and not _service_layout_page` 调用；文件域两个
  （`drawcompiler.py` +74/−1、新建 `tests/test_548l_pending_corridor.py`）。
  最终 `drawcompiler=AA86C1CE…FC5C2`、`test_548l=775F62DB…D9C0`。
- 正例：校准 WiFi 件（开关开）`compile ok=True`、`plan ok=True`、**两条网各成一条导线**、
  `wired route not found` 三处均 False、GND 旗从 `(320,680)` 让到 `(350,730)`、7 网 17/18 脚。
- 默认关闭：不写开关 → 复现 `wired route not found`、GND 旗回 `(320,680)`、几何 `81557467…`。
- 变异：M-L1（去掉调用）→ 真件复现拒因、新用例 1 failed；M-L2（去门控）→ 4 failed
  （548c4×2、548c6×2），门控承重；两次均 cp+sha256 还原 `AA86C1CE…`。
- 聚焦（主代理自跑）11 文件 **124 passed**。
- **视觉判废**：六枚 3V3 旗中三枚挤在去耦对上方、旗名与相邻旗盒相压；`ESP_RST` 因 R4 本体坐在
  y=695 直线上，被迫下绕到 y=785 再回来；`ESP_RXD`/`ESP_TXD` 名字盒压在自己引脚线与编号上。
  逐岛四问见 `evidence/548L/README.md` §6。
- 因此本批**只交机制与回归**，不落画布、不真机、不宣称 548J 完成。
- 下一批入口（同一层缺口）：**旗域与文字的联合座位**——同网旗聚簇/共享短轨（岳 P44 人工判据）、
  开放标签贴自己的引脚、服务件让开待走走廊。仍然不新建规划器。
