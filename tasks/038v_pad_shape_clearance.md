# 038V：圆形 / 长圆 / 椭圆焊盘的间距测量修正

日期：2026-11-05。来源：岳提供的 PCB-A 脱敏误报分析。按 `tasks/shared-platform.md` 的集成锁单独成批；不改解析、规则阈值、finding 文案或绘制算法。

## 1. 已复现的问题

`core/measure.py` 把所有焊盘交给 `pad_corners()` 变成外接旋转矩形。圆形焊盘在对角方向的半径因此被放大为 `r*sqrt(2)`，间距被低估 `r*(sqrt(2)-1)`。

本批用等价合成几何复现，不声称拿到或重跑了 PCB-A 原工程：

- 圆形焊盘 `66.929 x 66.929 mil`，`shape=ELLIPSE`；铺铜挖空边到圆心 `47.548 mil`。
- 旧模型：`47.548 - (66.929/2)*sqrt(2) = 0.222050 mil`。
- 圆盘模型：`47.548 - 66.929/2 = 14.0835 mil`。
- 两个直径 60 mil、圆心在对角线上相距 100 mil 的圆盘：旧 `pad_edge_distance=15.147186 mil`，真实值 `40 mil`。

## 2. 公开合同与调用方

- `pad_corners()` 的公开合同不变：仍返回 `width x height` 外接旋转矩形的四个 CCW 角点。板框、丝印等需要外接框的调用方不得被改成圆或胶囊。
- 新增内部焊盘测量几何，统一供以下三个实际消费者使用：
  1. `net_clearance()` / `clearances_vs()`（以及共用 shape 的 `pour_connectivity()`）；
  2. `pad_edge_distance()`；
  3. `component_distance()`。
- `ELLIPSE` 且 `width == height`（仅允许浮点零噪声容差）：用中心点 + 半径，距离精确。
- `OVAL`：用长轴两圆心构成的线段 + 短轴半径，旋转后仍是同一体育场形；等宽高等高时退化为圆。
- 非圆 `ELLIPSE`：用 32 条切线相交形成的**外接**多边形，必须包含真实椭圆，距离只允许保守低估，不允许内接多边形造成高估；径向最大放大系数 `sec(pi/32)`。它不是“精确椭圆”声明。
- 矩形及其他形状保持旧读法。真实相交、真实小间距和 same-layer / cross-layer 语义不得改变。

## 3. 行为基线与回退

- 先让圆盘-挖空、对角圆盘两个回归在旧实现上失败，再实施；保留读数。
- `pcb-voltage-spacing` 的合成规则闸：14.0835 mil 不得再WARN；另做真实小间隙负例，仍必须WARN。
- 矩形焊盘、走线、过孔、铺铜 ring/void、层集合和最近对身份描述保持原合同。
- 回退只需恢复旧焊盘矩形测量分支；无数据迁移、CLI/schema/connector/DSH/Rust 变化。

## 4. 兼容矩阵与 negative control

| 维度 | 本批覆盖 | 必须不变 / 不得声称 |
|---|---|---|
| V3 / V4 | 仅共享 `PadGeometry` 离线测量；宿主未改、真机未跑 | 不声称宿主 DRC 已重新核验 |
| `.epro2` / `.eprj2` / `.eprj3` | parser 未改；已有 EPRU 几何聚焦回归 | 不声称三种容器新增兼容能力 |
| KiCad | 共用 circle/oval 映射与测量；跑相邻测试 | 不新增 roundrect/custom 形状支持 |
| 在线 / 离线 | 仅离线纯函数 | 在线 bridge、CLI 输出和退出码不变 |
| 单 / 多板 | 仅单板合成几何；多板未覆盖 | 重复 PCB 双审、分歧库串板行为均不变 |
| 普通器件 / CBB | 只改已实例化焊盘几何；CBB 未覆盖 | 不声称 CBB 兼容完成 |
| negative control | 真正相交/不足间距仍报；矩形旧手算值不变 | 不得借修假阳性吞掉真问题 |

## 5. 文件域与验收

- 实现：`src/boardwise/core/measure.py`。
- 回归：`tests/test_125_pcb_measure.py`、`tests/test_125b_pcb_clearance.py`、`tests/test_126b_pcb_distance_rules.py`、`tests/test_126c_pcb_ipc_rules.py`，以及实际消费者锚 `test_88f_measure_perf.py`、`test_89b_fb_same_net_distance.py`、`test_131b_regulator_cap_distance.py`、`test_131c_regulator_fb_placement.py`、`test_131d_mcu_crystal_placement.py`、`test_131e_mcu_supply_reset.py`、`test_133b_foc_rules.py`、`test_155a_ruling_upgrades.py`；必要时补 owner/文档声明测试。
- 文档同步：原 125 任务书增加 superseded 指引，`tasks/review-line.md` 记录当前批次；不改历史 `PROGRESS.md`。
- 开发期只跑聚焦测试；最终由主代理跑相关 PCB 测量/规则集、owner 与文档闸。全量另按仓库串行纪律决定。
- 禁止修改既有 fixtures、`package.json`、`tasks/041-cross-board-net-DRAFT.md` 及绘制线文件；零 git 写、零删除、零真机。

## 6. 实际验收记录

- 旧实现先红：新增关键测试后为 **7 failed / 93 passed**；主代理另行用等价挖空几何复现
  `0.22205024196556777` 对 `14.0835 mil`，排除“测试只迁就新实现”。
- 相关测量、PCB 规则与 KiCad 邻域：**515 passed / 1 skipped**；电源、反馈与 FOC 消费者：
  **108 passed**；155a 阈值裁决：**12 passed**。核心、shared、owner、layer、doc 闸：
  **243 passed / 1 skipped**。这些集合有重叠，不相加成“全量”。
- 完整 Python 一轮：**9509 passed / 25 skipped / 2 failed / 1 warning，984.91 s**。
  仅 `test_193_process_guards.py::test_whole_suite_run_queues_behind_two_slots`
  （`~/.boardwise/pytest-slots` 权限）与
  `test_193_secrecy_hooks.py::test_the_posix_installer_sets_hooks_path_and_the_exec_bit`
  （Git/MSYS `0xC0000022`）失败，和本批前的已知环境问题一致；没有第三轮全量，不宣称全量全绿。
- connector：**576 passed**，typecheck 通过。DSH：**129 passed / 1 skipped**，typecheck/build
  通过。Rust：**111 passed / 4 ignored**，fmt/clippy/test 通过。
- 变异 M1 把圆半径改为 `r*sqrt(2)`：40 mil 回归变回 15.147186 并转红；M2 把 OVAL
  圆心偏移改为 `long_half`：123.431457 回归变 109.289322 并转红。两次均用 `cp` 恢复，
  `sha256sum -c` 为 OK。

## 7. 真实夹具的有意读数变化

- ROBOT `GND/VCC` same-layer：3.5382 → **5.984311 mil**，不再触发 4 mil WARN；六条
  `pcb-foc-decap-proximity` 只改距离，INFO/WARN 等级逐项不变。
- 毕设FOC `+24V/PGND`：1.0387 → **14.078304 mil**，不再触发电压间距 WARN；四个无电压
  INFO 保留。R18/U16 器件间距 15.1 → **15.8**，其余三项不变。
- llc `CHS/DC+`：85.965 → **95.0**（最近对变为 pour/pour）；隔离的 OVAL pad/fill 对另钉
  **99.884**，避免板级最小值掩盖焊盘路径。`CHG/CLG` 为圆盘与走线端帽并列
  **362.688078**。
- 其余 MCU、电源、反馈锚均按 `component_distance` / `same_net_loop_distance` 直接复算后更新，
  未改器件、pad 对、net、阈值或 severity。

## 8. 未覆盖与遗留

- 未提供原始 PCB-A 导出文件，本批没有重跑原板或重新调用宿主 DRC；只验证等价合成几何和
  仓库既有真实夹具。V3/V4 真机、多板、CBB 未覆盖。
- `vias_on_pad` 仍用外接框做保守包含，非矩形焊盘框角里的过孔可能多计；这是既有行为，
  本批仅修正文档，没有扩项改散热规则。
- KiCad `roundrect` / `custom` 等仍走矩形保守模型；非圆椭圆是最差径向放大
  `sec(pi/32)` 的外接近似，不宣称精确椭圆。
- 实现与文档均未提交、未推送；`package.json` 与 041 的既有修改不属于本批。
