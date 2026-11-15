# 038Y6 / PCB 丝印 autofix 前提（暂缓）

## 结论

暂缓，不移植预研 `--autofix-silk`。038Y5 已提供无写入的 `pcb gate`，本批没有实现自动修。

## 本机证据

- 预研依赖的 `pcb.list_attributes` / `pcb.move_attribute` / `pcb.save` 不在当前协议。
- 现有 `pcb.modify_primitive` 的 `POSE_CLASSES` 只有 component/via/pad；
  `connector/src/actions.ts:5440-5452` 明确 **attribute primitives absent**。
  因位号 ATTR id 可由离线归档读出，不能推出宿主允许移动它。
- `sch.list_attributes` / `sch.move_attribute` 是原理图 ISCH 命名空间，不能拿来写 PCB。
- `sch.doc.save` 只证明 `sch_Document.save` 的项目保存通道，未证明 PCB 修改后的保存与导出语义。
- 现有 `pcb.geometry --bboxIds` + `_designator_attr_ids()` 可以测量位号文字盒，
  但 footprint 印字没有同等的宿主实测通道；估算/mixed 不得驱动自动写。

## 重开前提（缺一不可）

1. 在明确授权的 `test` 或 `test2` 上只读探针证明 PCB 属性的枚举、父子身份、可写 pose、
   保存和写后回读；缺能力就实现独立、最小、带 pageUuid 的 connector 动作，不能复用 sch 名。
2. 版本化 ChangePlan：board/pageUuid、primitiveId、parentPrimitiveId、expectedKey/Value、
   before x/y/rotation、目标与原因；重复位号/重复文字不得按字符串挑选。
3. 所有移动对象必须有宿主实测盒；候选位置复用审查线真实焊盘/墨迹/本体几何与顶底面，
   不另造一套较弱的自动修尺。库文字、无稳定 id、估算盒、身份不明均零写。
4. 写前计划/授权、逐动作回读、失败现场保留与可执行恢复计划；超时也先回读，不能假定未写，
   不得宣称有事务回滚。保存后重新导出并再跑 038Y5 gate。
5. 真机验收包含幂等第二次零写、部分失败、跨面、同名文字、无合法位置、旧 connector 拒绝；
   只碰任务书逐字点名的测试工程。发布前仍需完整四线验收。

## 下一步最小动作

另开 connector/shared 集成批，先提交「PCB 属性能力矩阵 + 零写探针」供裁定；
在证据齐全前，审查只报告，不自动移动任何文字。
