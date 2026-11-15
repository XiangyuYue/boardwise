# 038Y4 / `pcb-silk-under-body` 规则

## 规则合同

- id `pcb-silk-under-body`，level `L1-pcb-geometry`，WARN；title 用英文短标题。
- 只审 `source=="footprint"` 的可见丝印文字；位号仍归 `pcb-silk-designator`，自由文字、
  装配层文字、隐藏文字不归本规则。
- 本体是 TOP/BOTTOM 同面的 `COMPONENT_SHAPE` 单个简单多边形，实际多边形面积
  **>= 80000 mil²** 才计入；不得用 bbox 面积或合并多颗/多段本体后的 bbox。
- 同器件不豁免；异器件也审。文字盒与真实本体多边形有正面积交集即报，支持凹形本体、
  部分覆盖与完全覆盖；仅相切不报。每个（文字、本体器件）对一条，target 双向。
- 文字几何必须复用现有 `SilkText.corners` / `text_box` 与实测优先通道，不能另写
  `(x,y,x+0.62w,y+h)`。估算统一用现有 `WIDE_ADVANCE`，evidence 明确实测/估算；
  不谎称所有 footprint 文字都有宿主实测盒。
- 物理面按 SilkShape.face / placement 与 SilkText.layer_kind 配对；跨面不报。
- 本体 ARC/圆角使用现有弦化/24边形读法时，每板至多一条 INFO 披露近似；
  不把 bbox 相交称为“完全盖住”，message 区分部分/全部角点落体。

## 实现约束

优先继承/复用 `SilkDesignator` 的 `_measured_box`、`_shape_polygon` 和现有文字模型，
不改既有 `pcb-silk-designator` 行为。文字矩形 vs 任意简单本体可用严格内点、
真边穿越和文本中心包含判正面积，不得退化为两个 bbox 相交。多环、自交、
独立 mirror/reverse 字形语义未另校准，必须披露继承边界，不能发明修正。

注册顺序：`SilkDesignator()` → `SilkUnderBody()` → `SilkOnForeignPad()`。

## 文件域

允许新建 `src/boardwise/rules/pcb/silkbody.py`、`tests/test_038y4_silk_under_body.py`；
修改 engine import/注册、module-owners、实际锚点与 differential 生成物。
禁止 shared/parser/model/CLI/draw/fixtures/其他规则；038Y3B 已收尾，不改其算法。

## 验收

同/异器件、79999/80001 面积、凹形本体凹口、旋转180°文字、RIGHT/CENTER anchor、
顶底面、非丝印层、designator/free/hidden、部分/完全覆盖、相切、实测盒、
每文字-本体对聚合、近似 INFO、注册/owner。两处独立变异先红（bbox代替多边形、
同器件豁免或跨面），cp+SHA恢复。跑新测试、038Y3B/Y3A/Y1/Y2、152/172、126a/b/c、
owner/layer、report/digest邻域；官方builder；只读归档记录WARN/INFO与耗时。

## 状态

实现与主代理验收完成（2026-11-15，工作树，未提交）。最终规则 SHA-256：
`4df7c44ae5ce93f2fb465d91f0bebc83bc92a12135cddcc6ed4c7b1ed3380236`；最终 rulebody=`1cc2bff3`，
differential 保留官方 builder 的 0.6.1 版本字段。

- 主代理独立变异：bbox 代替本体 `1 failed / 26 passed`；同器件豁免
  `1 failed / 26 passed`，均按 SHA-256 恢复。另补齐圆本体24边形近似与小本体 INFO
  被提前return吞掉两处披露缺口。
- 首轮联合集发现 6 个旧锚点未登记两条丝印规则，已只修锚点并为 llc 增加
  0 WARN/1 INFO/under-body 0 行的直接旁证；最终联合复跑 **1274 passed / 2 skipped（91.32s）**。
- 主代理三规则联合只读归档：两个既有归档共4板，pad-overlap与两条丝印实际WARN均0；
  silk-on-foreign-pad近似INFO共4条，耗时0.336s/0.121s。这些归档的 footprint 印字为0，
  所以 under-body 的0不解释为「量过所有文字」。
- 同器件不豁免保持岳裁，不因其他归档出现极性印字命中而改规则。估算字宽、
  mirror/reverse、退化共线、多环/自交与解析圆弧仍未覆盖，已披露。
