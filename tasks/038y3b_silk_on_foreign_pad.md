# 038Y3B / `pcb-silk-on-foreign-pad` 规则

## 规则合同

- id `pcb-silk-on-foreign-pad`，level `L1-pcb-geometry`，实际压铜为 WARN。
- 一颗器件的 TOP/BOT_SILK 墨迹与**另一器件**焊盘真实铜面有正面积交集才报；
  同器件、仅相切、跨面、无归属板级图元均不报。无位号但有 component_id 的实例仍可识别。
- 最终判定只调用 038Y3A `pad_ink_overlap()`；`pad_corners` 与墨迹 bbox 只能粗筛。
- 支持线段/折线、单点圆（radius+width/2）、单环 filled 区域；closed 只补几何末边。
  不输出预研那种描边/填充混合的“最大深度”，证据点名焊盘、图元和器件对即可。
- 按（丝印器件、焊盘器件）聚合一条 WARN，每只受影响焊盘一条 evidence；
  target 指向两侧，离线 primitive_id 留空，不把模板 id 当 live id。

## 近似披露（不能静默）

`arc_count>0` 或带半径的多点圆角矩形只能按当前 parser 的弦/角点模型测量。
规则每板至多聚合一条 **INFO**，列出涉及器件并明确「弦化/角点近似，非解析圆弧」；
这不计为实际压铜 WARN，也不得被写成全图元精确。多环/镂空与 fillStyle 仍不支持，
本批不改 parser；两个既有归档的多环 FILL=0 只是局部证据。

## 注册与文件域

本批注册在 `SilkDesignator()` 后；下一批把 `SilkUnderBody()` 插到它前面。
允许新建 `src/boardwise/rules/pcb/silkpad.py`、`tests/test_038y3b_silk_on_foreign_pad.py`；
修改 engine import/注册、module-owners、实际锚点与 differential 生成物。
禁止改 shared/parser/model/CLI/draw/fixtures/其他规则。038Y2 文档措辞已收口，不顺手改。

## 验收

异器件/同器件、顶底面、相切、真实穿盘、圆盘外接框耳朵、单点圆、凹填充及凹口、
closed、板级无归属、无位号实例、聚合、近似 INFO 唯一且非 WARN、注册/owner。
两处独立变异先红：同器件误豁免翻转、跨面误报或填充被跳过；cp+SHA 恢复。
跑新测试、038Y3A/Y1/Y2、152/172、126a/b/c、owner/layer、实际 report/digest 邻域；
官方 builder 重建 differential。跑两个只读归档，记录 WARN/INFO 与耗时，不宣称真机。

## 状态

实现与主代理关键验收完成（2026-11-15，工作树，未提交）。最终规则 SHA-256：
`e92a2f4cd8edcce1a8af342bdff2b15906710d5586d0ac5c3a5c621f0c4a1ebd`；rulebody=`3f90b257`。

- 子代理扩大聚焦：**352 passed / 2 skipped**；新增网格/无网格对拍覆盖负坐标、跨格长线、
  圆盘外接框耳朵、filled、无位号实例与确定性，最终新文件 19 条。
- 主代理独立变异：同器件豁免翻转 `16 failed / 3 passed`；跨面放开
  `1 failed / 18 passed`，均按 SHA-256 恢复。
- 子代理只读归档：两个既有归档共 4 块 PCB 实际压铜 WARN=0，近似披露每板 1 条 INFO；
  含解析耗时约 0.10–0.35s。该读数只适用于这些归档，不据此否定其他设备的预研样本。
- 多环/镂空、fillStyle、解析 ARC 与单点圆内环仍未支持；披露已落入 INFO/evidence。
  后续 038Y4 注册时将本规则保持在 SilkUnderBody 之后。
