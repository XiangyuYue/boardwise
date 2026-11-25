# 任务书：613 — move-block 网格输入有限且非零

## ① 前因后果

`outputs/hole570/d/REPRO.md` 的 **D4**：`moveblock.on_grid` 对 NaN 抛 ValueError、Inf 抛 OverflowError、grid=0 抛 ZeroDivisionError；`check_grid` 因此不能按合同给 `MoveRefused`。当前 76e0806 仍只有一行 `round(value/grid)`。

本批只修网格谓词与既有拒绝映射，不动 poses 的其它字段、移动路径、删线重画、router 或宿主。正常网格、微小浮点容差和负 grid 拒绝保持不变。

## ② 当前树状态

- HEAD/origin `76e08060ded403793bc6fb0eb64b38f9e140c765`；前批保留。
- `src/boardwise/engines/moveblock.py` SHA-256 `141070309aa8ea10acded809861c971b11af5162ebe25518cd39edc272fd2a42`。
- 112–114 行 on_grid；198–210 行 check_grid 用默认 GRID 调用 on_grid(dx/dy/item.x/y)，合法拒绝已经是 MoveRefused。
- 开始 cp 备份 moveblock 到 `.tmp_613/backup/`。他人 563/review-line/router/临时文件禁触。

## ③ 文件域与禁触清单

允许修改/新建仅：
- `src/boardwise/engines/moveblock.py`（on_grid 有限性/grid 校验及必要注释）
- `tests/test_613_moveblock_grid.py`（新）
- 本任务书、`.tmp_613/`、`.tmp_pt_613/`、`evidence/613/`

禁止：addcomponent/router/changeplan/CLI/connector/DSH、fixtures 和他人文件。不得改 GRID 常量、容差、group 处理或删除/重画逻辑，不修改既有断言凑绿。

## ④ 交付物与验收

1. `on_grid` 对 value/grid 为 NaN、±Inf 返回 False，对 grid<=0 返回 False；bool/非数值如既有类型注解不可达不扩新合同，但不能用数学异常替代 False（若现有调用可传入则明确测试）。
2. `check_grid` 遇到 NaN/Inf delta 或 part 坐标必须抛既有 `MoveRefused`，错误文案可定位 delta/part，不出现 traceback 的 ValueError/OverflowError/ZeroDivisionError。正常 dx/dy、part x/y 合法仍通过，off-grid 仍按原文拒。
3. 先对未改生产运行 on_grid NaN/Inf/0/负 grid 与 check_grid NaN 用例，必须红（不是 pytest.raises 捕获后算正确）；正常 10、1e-7、负 grid 原行为控制绿。

修后运行新测试、037/move-block 全邻域、029/036 必要测试、owner/layer；不跑全量。至少两项变异：① 去掉有限性；② 去掉 grid>0 检查。每项对应测试必须红，cp+SHA 恢复并复绿。

兼容矩阵：纯 moveblock 输入与既有 Part；真实 host、V3/V4、多板/CBB 未覆盖。negative control 为正常网格返回值、原 off-grid 拒绝文字和容差不变，无真机移动声明。

## ⑤ 纪律与红线

零 git 写/移动/删除；禁 rm/unlink 和 git checkout/restore；不全量、不真机、不部署。pytest 独立 basetemp、命令 timeout、单进程。不得把非法输入 coerce 成 0/True、改变 grid 或捕获所有异常掩盖其它错误。

## ⑥ 预算与交卷格式

一个 coder，最多 30 步或 20 分钟；不派下级。交卷 ≤1500字，含先红/修后汇总、MoveRefused 原文、两项变异与 SHA 恢复、未覆盖项。证据落 `evidence/613/`。缺任一变异只能写「停止/未完成」。
