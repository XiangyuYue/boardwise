# 038Y2 / `pcb-pad-overlap` 规则接入

## 来源与边界

预研包证明「同网焊盘正面积重叠」会绕过既有间距规则，但其面积实现退回外接矩形。
本批消费 038Y1 的 `pad_copper_overlap()`，只新增审查规则与必要注册/契约，不改共享几何，
不移植预研包的 `pad_overlap_area()`，不声称输出所有形状的精确面积。

## 规则合同

- id `pcb-pad-overlap`，level `L1-pcb-geometry`，severity `ERROR`。
- 同一 BoardGeometry 内，不同器件的两块焊盘只要在共享铜层有正面积交集即报；
  同网、异网、空网均不豁免。仅相切、跨层、无铜层均不报。
- 同一非空 designator 的封装内部焊盘不报；两个空 designator 不得因此被误认为同器件。
- 每个无序焊盘对一条 Finding，顺序确定，target 同时指向两个器件；证据给位置、形状、
  尺寸、角度和网名，不写未经计算的面积。
- 使用 `pad_copper_overlap()` 作判定；`pad_corners()` 只能作安全的 bbox 粗筛，不能作最终铜面。
- 注册在 `BoardOffEdge()` 后、`TrackAmpacity()` 前。预研包的 `device_footprints` 解析改动
  不属于本规则依赖，不得带入。

## 文件域

允许新建 `src/boardwise/rules/pcb/overlap.py`、`tests/test_038y2_pad_overlap.py`；
允许修改 `src/boardwise/engines/pcbreview.py` 的 import/注册两处、`contracts/module-owners.json`
及实际受新模块/规则影响的锚点测试与 differential 生成物。不得改 parser/model/CLI/draw/
fixtures/其他规则。TASKMAP 与其他文档由主代理统一收尾。

## 验收

- 正反例：同网/异网重叠、相切、同器件、空器件名、圆盘对角 0.569949 mil 真实间隙、
  45° 旋转矩形外接框假交、跨层、通孔到底层、完全包含、注册顺序与 owner。
- 两处独立规则层变异必须先红：例如同网被跳过、空器件名被当同器件；cp+SHA-256 恢复。
- 跑新测试、038Y1、126a/126b/126c、127b、owner/layer、实际受 digest/report 影响的聚焦测试；
  differential 用既有 builder 重建，不手填摘要。不自动跑全量或真机。

## 状态

实现与主代理验收完成（2026-11-15，工作树，未提交）。

- 最终规则 SHA-256：`efd12c3bded9880e8edc307e5ae242e8ec3d0aeb97ef780010c6314b7d6dfbe8`；
  038Y1 共享文件保持 `4c34e224…64ed`。最终 recursive rulebody=`7818d3a8`，direct 不变；
  differential 由官方 builder 生成，版本字段随当前生成器为 0.6.1，其他 case 未变。
- 主代理最终扩大邻域：**648 passed / 1 skipped（82.86s）**。两个真实只读归档夹具共 4 块
  PCB 的本规则读数均为 0；没有据此宣称所有真实板零误报。
- 主代理独立变异：同网跳过 `3 failed / 23 passed`；空位号归为同器件
  `2 failed / 24 passed`，均按 SHA-256 恢复。另复核修正离线 primitive_id、单侧 pin_refs、
  同网装配冲突与异网短路的理由分层。
- 未跑全量或真机；非圆椭圆仍继承 038Y1 的 32 边形保守边界。本规则不输出未计算的面积。
