# 038Y1 / 焊盘正面积重叠共享几何原语

## 来源与目标

2026-11-15 另一设备的 PCB 审查预研包提出了 `pcb-pad-overlap`，但实现把
`pad_corners()` 外接矩形误称为真实铜面。主代理用两只 Ø98.425 mil、圆心偏移
(70,70) mil 的圆焊盘复现：预研包报 807.980625 mil² ERROR，当前 038V 几何测得真实边距
0.569949 mil。不得移植该回归。

本批只增加一个**层感知、正面积重叠**的共享原语 `pad_copper_overlap(board, a, b) -> bool`，
供下一批规则消费。本批不注册规则、不改变任何 finding/report/CLI，不移植预研包实现。

## 公开合同

- 只在至少一个共享铜层上、两块铜的交集具有正面积时返回 True；相离和仅相切均 False。
- 圆盘、长圆胶囊、旋转矩形分别按自身几何判；非圆椭圆沿用 038V 的外接 32 边形，
  误差上界与保守方向必须在 docstring 说明，不能声称解析精确椭圆。
- 层读取复用 `_comparable_layers()`：`effective_layer_ids=None` 走既有回退，`[]` 是无铜层，
  二者不得混淆。纯几何计算与层判断不得复制到 rules。
- 复用 `_pad_copper()`、`point_in_polygon()`、`point_segment_distance()` / `_segment_distance()`；
  不新增第二套焊盘形状模型，不改变 `pad_corners()` / `pad_edge_distance()` /
  `component_distance()` 的结果。
- 多边形交集需要处理旋转、包含和贴边；胶囊交集需要处理圆/圆、圆/长圆、长圆/长圆及
  胶囊/多边形。不得以 `pad_edge_distance()==0` 代替，因为它无法区分相切与正面积重叠。
- 数值容差只处理浮点噪声并写清量纲，不设置工艺余量。本原语不返回伪造的“精确面积”。

## 文件域与集成锁

允许：`src/boardwise/core/measure.py`、新建 `tests/test_038y1_pad_copper_overlap.py`、本任务书。
禁止：规则注册、rules 改动、parser/model/CLI/connector/draw、fixtures、其他未提交文件。
主仓 HEAD `b78c21441db140a8556d685750665307c278eadf`；工作树混合，现有改动不归本批。
`core/measure.py` 开工 SHA-256：`7f30ac0070dffc578c507ff1a62b5f484c86e575f88f5d6259bce01190bbde7f`。

## 兼容矩阵与 negative control

| 维度 | 本批覆盖 | 不得声称 |
|---|---|---|
| V3/V4 | 仅 `PadGeometry` 合成输入；parser 未改 | 未完成两种宿主真机兼容 |
| `.epro2/.eprj2/.eprj3` | 不读取容器，未覆盖 | 不声称格式兼容扩大 |
| 在线/离线 | 纯离线函数 | 未做在线验证 |
| 单/多板 | 单层感知、单 BoardGeometry | 不合并跨板铜面，不重复审板 |
| 普通器件/CBB | 只读已实例化焊盘，不读库身份 | 不声称 CBB 新能力 |
| 既有消费者 | `pad_edge_distance` 与 `component_distance` 聚焦回归 | 不改变既有间距、层回退、finding |

Negative control：对角分离圆盘不得再被外接方框判重叠；同径相切不得报；不同铜层不得报；
同位置同层必须报；旋转矩形仅外接框相交而铜面分离不得报；多边形完全包含必须报。

## 验收

聚焦测试至少包含上述反例，以及圆/长圆/旋转矩形、None/[] 层读数；两处独立变异必须
分别让关键断言变红，再 cp+SHA-256 恢复。运行新测试、038V 所在邻域（按实际测试名定位）、
126b/127b、owner/layer/doc 守卫；不自动跑全量，不跑真机。

## 状态

实现与主代理验收完成（2026-11-15，工作树，未提交）。最终生产 SHA-256：
`4c34e22419c54050f584aa9e01188254e9acfa229c757e366943aa2b981064ed`。

- 主代理发现首版 `_centreline_distance` 漏掉段内交叉：同原点 0°/90° 长圆曾误报 False；
  已复用 `_segment_distance` 修正并加正/反例，最终新测试 18 条。
- 主代理合并聚焦：**179 passed / 1 skipped（19.92s）**，覆盖新测试、125/125b、126b、
  127b、038K 与 owner；skip 为既有条件跳过。
- 主代理独立变异：层闸关闭 `2 failed / 16 passed`；退回 `pad_corners` 外接框
  `2 failed / 16 passed`。均按 SHA-256 恢复，恢复态通过上述合并聚焦。
- 未跑全量、真机或容器差分；只覆盖合成 `PadGeometry`。非圆椭圆仍是 038V 的外接
  32 边形保守读法，不声称解析精确。层完全未知的合成焊盘不猜共享层，返回 False。
