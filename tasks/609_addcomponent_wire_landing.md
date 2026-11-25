# 任务书：609 — add-component 的线段落点与有限坐标

## ① 前因后果

`outputs/hole570/d/REPRO.md` 的三个同域缺口在当前源码仍可复现：

- **D1**：`nearest_wire_point` 只量顶点，`Line=[-200,0,200,0]` 穿过 `(0,0)` 却答最近点 `(-200,0)` 距离 200；`choose_connection` 因此拒绝一条实际可接的线。
- **D2**：`occupied_points` 只收顶点，同一长线中点 `is_free(0,0)=True`，去耦件会落在铜线中段且不连接。
- **D3**：`is_free(nan,nan,[])` 返回 True，`landing_spot((nan,1),[])` 返回 NaN 落点；非有限占点还会把所有候选伪装成占满。

本批只修 addcomponent 的“线段几何 + 有限落点”这一缺口，不夹带同文件的 D6/D7 身份分配，也不改 patchpin 的奇数 Line 合同（另批）。保持纯函数、现有返回类型与正常路径。

## ② 当前树状态

- HEAD/origin `76e08060ded403793bc6fb0eb64b38f9e140c765`；前批改动保留。
- `src/boardwise/engines/addcomponent.py` 开工 SHA-256 `5168ea888a3535e24b96e1e10d345f14153e5fe5257dc63bc2d61f651577b3f5`。
- 584–756 行：occupied/is_free/landing、wire_vertices、nearest_wire_point；`_number` 接受 float NaN；LANDING_GRID/CLEARANCE 都 5。patchpin 已有 `WireSegment` 和 `_on_segment`，且不 import addcomponent，可在函数内复用其段读取，避免循环依赖。
- 既有 tests/test_029a_addcomponent.py 是主邻域；不改 fixtures。他人 563/review-line/router 与临时文件禁触。开始 cp 备份 addcomponent 到 `.tmp_609/backup/`。

## ③ 文件域与禁触清单

允许修改/新建仅：
- `src/boardwise/engines/addcomponent.py`（线段读取/投影、占用、有限性及对应注释）
- `tests/test_609_addcomponent_wire_landing.py`（新）
- 本任务书、`.tmp_609/`、`.tmp_pt_609/`、`evidence/609/`

禁止：patchpin/moveblock/canvasrender/select/core changeplan/CLI/shared/connector/DSH、fixtures、D6/D7 函数和他人文件。不得改 CONNECT_RADIUS、LANDING_CLEARANCE、LADDER 顺序或网名匹配来凑过；不新增第二套几何库。既有测试不得删改宽、skip/xfail。

## ④ 交付物与验收

### 实现合同

1. **D1**：nearest 改为点到每条有限线段的投影最近点，t 截到 `[0,1]`，零长段退化为点；返回 `(x,y,distance)` 保持。`choose_connection` 对穿身目标网线段返回 `kind=="wire"` 且目标为投影点。跨网仍 None，顶点最近与超出半径的旧行为不变。spot/线坐标非有限不得产生最近点。
2. **D2**：occupied_points 保留 `list[(x,y)]` 公共形状，同时纳入线中段。可在每条线段上以不大于 `LANDING_CLEARANCE/2` 的间隔确定性采样并包含端点，使任何距铜线小于 clearance 的候选不会被误判为自由；或提供等价的线段距离判定而不改变调用者形状。不得只加中点一个样本，长线任意位置都要覆盖，避免性能失控/无限循环。
3. **D3**：is_free 对非有限候选或非有限占点返回 False；landing_spot 对非有限 origin/grid、非正 grid 或计算出的非有限梯级具名拒绝（ValueError 或既有专用拒绝），不得返回 NaN，也不得抛 ValueError/OverflowError 裸数学异常。正常一格边界 `is_free(5,0,[(0,0)]) is True` 不变。
4. 可复用 patchpin.wire_segments 读取折线；其后续奇数 Line 拒绝会被 611 单独钉住，本批不得趁机动它。必要的小 helper 保持本文件内，不新增生产子系统。

### 先红与修后

先新增并跑未改生产：D1 穿身线/choose_connection、D2 长线中点与偏离中点的梯级、D3 NaN/Inf/零 grid 必须目标红；普通顶点、跨网、自由点、有限 ladder 为绿。至少覆盖折线第二段、反向线段、零长段和长线非中点位置，防止只修原坐标。

修后运行新测试、`tests/test_029a_addcomponent.py`、`tests/test_035_patch_pin.py`（先 Glob 核名）、`tests/test_036_subcircuit.py` 及必要 owner/layer；不跑全量。保存完整汇总。

至少三项变异：① 只量顶点；② occupied 不采样中段；③ 去掉 isfinite。每项对应新测试必须红，cp+SHA 恢复并复绿。negative control 是合法顶点连接、跨网拒绝、原 ladder 顺序和边界不变；真机/bridge/V3/V4、多板/CBB 未覆盖。

## ⑤ 纪律与红线

零 git 写/移动/删除；禁 rm/unlink 和 git checkout/restore；不全量、不真机、不部署。pytest 独立 basetemp、命令 timeout、单进程。不得调大连接半径/落点间距、跳过异常输入、修改既有断言或改 D6/D7 凑绿。发现 patchpin 奇数线问题只记录交 611，不扩大文件域。

## ⑥ 预算与交卷格式

一个 coder，最多 40 步或 30 分钟；不派下级。交卷 ≤2000字，含 D1/D2/D3 先红与修后读数、完整测试汇总、三项变异与 SHA 恢复、采样/复杂度和未覆盖项。证据落 `evidence/609/`。缺任一洞的有效变异只能写「停止/未完成」。
