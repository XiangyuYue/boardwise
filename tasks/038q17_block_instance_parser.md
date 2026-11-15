# 038Q17：原生块实例的只读识别与假信号修复

日期：2026-11-15。前置：038Q16 已在 P46 得到真实 `block_symbol` 与项目导出。
本批是 shared parser 小批，不改 review 规则、verdict、绘制或 connector。

## 真实证据

`.tmp_038q_native/q46-project.epro2`，SHA-256
`8dcec81d5688a4c50b24acbcd6eae33bcd11ea615002f29d389598e5f07a7413`。
P46 的 `COMPONENT bf1c81ee9e14827d`：`partId=32c6fc8b0adcd464`、x=400,y=-300，
子 ATTR `Symbol=ca89fed3a434c5cb`，`Reuse Block/Designator/Name=null`。
对应 SYMBOL 的 `META.docType=17`、`META.source='c657f757a2cf294b|e1534426…'`、0 PIN。
在线 state=`block_symbol`, x=400,y=300；source 的 y 经既有归一化与之一致。

当前 `_split_page` 把它当无位号普通件：`instances_without_designator` 0→1 并 `continue` 静默丢弃。
这不是普通器件问题，不能放宽普通无位号规则。`Reuse Block=null` 不是反证，Designator/Name 空也不是身份。
详细证据：`.tmp_038q_native/q46-record-analysis.md`。

## 公开合同

新增只读 `collect_block_instances(path)`，复用 `_iter_schematic_records` / `_split_page`，不扩白名单。
每行至少披露：pageUuid、primitiveId、partId、local symbolUuid、sourceSymbolUuid/sourceCbbUuid（可溯源时）、
title、位姿、符号端口集合、identityStatus。当前样件端口为空数组，不能补造。

有效块身份三锚：
1. `COMPONENT.partId` 命中某 SYMBOL 文档的 `PART.id`；
2. 子 `ATTR Symbol` 逐字等于该 SYMBOL uuid；
3. 该 SYMBOL `META.docType===17`（数字，不是 DOCHEAD 字符串命名空间）。

溯源来自 `META.source` 的**两段**：源符号 uuid | 源 CBB 工程 uuid；第二段不是 libraryUuid。
空/畸形 source 要标 source-unresolved，不猜。partId 命中块但 Symbol 缺失/不符要显式 unresolved，
不得静默丢成普通器件，也不得算有效块。Designator/Name/Reuse Block 任意值不改变三锚判定。

`_split_page` 在 `_looks_like_a_nameless_part` 前先分流已识别块和 unresolved 块候选；
普通器件的既有无位号语义不变。无 CBB 输入的 `instances_without_designator`、普通 instances、
components/nets/BOM 逐字不变；有块时不再产生这条假信号。空 CBB 板仍为空，不造器件或网络。

顺带修复真样本暴露的假漂移：`TABLE`（pageframe 已消费）与 `UNIVERSAL`（CONFIG 选项记录）
加入 `KNOWN_RECORD_TYPES`；其他未知类型仍必须报告。

## 必须有的 negative control

- 普通器件 `<device>.1`、A4 sheet、电源/地旗标 docType18、未放置的17号符号均不成为块实例。
- partId 命中块但缺 `Symbol`：unresolved，不能 verified/静默普通件。
- source 为空：块可识别但 source-unresolved。
- 同 partId 一块一非块：按实例 id + Symbol 分，不串身份。
- 手填 Designator、Reuse Block 填值：不改变三锚判定。
- 普通工程组件、网络、位号、findings 与无位号计数不变。

## 文件域与验收

- `src/boardwise/parsers/schematic.py`、`src/boardwise/parsers/epru_stream.py`（仅两个已知类型）、
  `tests/test_038q17_block_instances.py`、必要的既有 parser 邻接测试、
  `tasks/038q17_block_instance_parser.md`、`docs/v3-v4-boundary.md` 的真实覆盖说明。
- 测试夹具必须是匿名合成记录，不复制真实工程容器或派生副本进 tests/fixtures。
- 真样本只在本机 `.tmp_038q_native/` 验证：旧导出普通读数不变；Q46 能读出 bf1c…、三锚、源身份、
  位姿和空端口，instances_without_designator 不再增加；普通 3 板/多板错误合同不变。
- 两消费者等价：`build_project_model` 与 `collect_part_devices`/普通组件视图；不改 CLI/DSH schema。
- 聚焦 pytest `--basetemp=.tmp_pt_038q17`；至少两变异（漏 Symbol 锚、错误分流普通无位号件）
  先红后 cp+SHA-256 恢复。零 git 写、零直删、零真机写。
- 本批仍不证明非空块端口、N1–N3、V3、多块嵌套或 `lib.cbb.export` 成功。

## 实际结果（2026-11-15，工作树，未提交）

只读解析已落：`collect_block_instances(path)` 走 `_iter_schematic_records` + `_split_page`，
不扩白名单；块身份三锚全中才算 verified，`partId` 命中**任一** docType17 文档即算命中块（共享模板 id
同样，`Symbol` 仍单独定身份），此时 `Symbol` 缺失/不命中报 `unresolved`（`symbol-missing` /
`symbol-mismatch`）；`META.source` 只要求恰好两段、两段非空且无首尾空白，两段按**不透明身份**
原样保留（名字型 id 照收），空/缺段/多段/带空白报 `source-unresolved`（`source-empty` /
`source-malformed`），不猜。块文档目录与 pin 读取同取**首份**副本（V4 会把同一符号拷进每一页），
副本的可见投影（title/docType/source/排序后 part_ids）不同才计入 `conflicting_library_documents`，
相同副本不计数、pin-only 差异仍只由既有 `_collect_symbols` 计数。`_fill_board_model` 在**每个**实例
的位号分支之前分流块与未决块候选：任何位号状态（含手填位号）都不成模型 `Component`、不进普通网表，
也不产生无位号假信号；普通件语义未动。`KNOWN_RECORD_TYPES` 仅新增 `TABLE`、`UNIVERSAL`。

真样本读数（`.tmp_038q_native/q17-parser-check.json`，前置/后置同一进程内对照）：
`test-v4-cbb-project.epro2`（`8ad4558f…`，107854 B）与 `q46-project.epro2`（`8dcec81d…`，109249 B）
除两项外逐字一致。q46 读到一块：页 `393dfe0bb84bf7cb`、`primitiveId=bf1c81ee9e14827d`、
`partId=32c6fc8b0adcd464`、本地符号 `ca89fed3a434c5cb`、源符号 `c657f757a2cf294b`、
源 CBB `e1534426…e2ae845`、title 晶振、位姿 x400/y300/rot0/mirror False/zIndex1、`ports=[]`、
`identity_status=verified`；放置前容器 0 块。普通读数不变：三块板 components 9/0/11、
nets 63/0/20、20 位号、18 符号、`part_devices` 20、多板拒绝仍 3 boards。两项变化：
`instances_without_designator` 1→0（q46，假信号）、`unknown_types` `{TABLE:1,UNIVERSAL:1}`→`{}`。
另对 14 份既有夹具做前后对照：0 个块实例、无位号计数全 0 且不变、`unknown_types` 只减去
TABLE/UNIVERSAL（LAYER_FILL/IMAGE/META_MODIFY 等真漂移仍在）。

聚焦 pytest：`tests/test_038q17_block_instances.py` 26 passed；连同 13 份既有 parser 邻接测试
与 `test_doc_claims.py` 合计 385 passed（均 `--basetemp=.tmp_pt_038q17`）。合成夹具全匿名，
真实容器未进 `tests/fixtures`。变异先红后 `cp`+SHA-256 还原：漏 Symbol 锚 3 failed、去掉块分流
4 failed（`049fce71…`）；「共享 hits 退回静默普通件」2 failed（`05cfa640…`）；「恢复 last-wins」
1 failed、「分流移回无位号分支」1 failed（`df48cad9…` 字节一致）。

未覆盖：非空块端口（无样件）、多块同页、嵌套块、块在网表里的接线、`lib.cbb.export`、V3 块实例。
