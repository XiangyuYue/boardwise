# 527C2：跨视图 lonely-pin 的几何证据与完整披露

日期：2026-11-06。上游：`tasks/527_pre060_loose_ends.md` §527C。按 shared 集成锁分两片：parser 几何投影、pcbreview/CLI 披露。只改读法，不改哪一侧电气结论更有权威，也不改 finding/severity/verdict。

## 1. 公开几何合同

- `DesignModel` 增加可选 `pin_wires`，缺省 `None`；字段放在 dataclass 末尾，旧位置构造与手工模型不变。它只搬 parser 已算出的几何，不包含布局决策。
- EasyEDA `_fill_board_model` 填充：
  - `binding="endpoint"`：与当前原理图绑定律一致，只认引脚点精确落在线段端点；
  - `pins[(designator, pin)] = (page_uuid, x, y)`；
  - `wires[page_uuid] = [(Point, Point), ...]`，只含 WIRE 组的真实线段，不含符号图形，不跨页/跨板合并。
- 不使用 `BoardModel.raw`（多页合并会 first-wins），不使用 `collect_page_layout`（缺 page 维）。几何在 `_fill_board_model` 的 `placed`、`split.segments/pages` 作用域内一次生成。
- KiCad/`.enet`/手工模型本批不生成该字段：保持 `None`，报告走旧 generic note，不假装有几何。KiCad 的 endpoint-or-interior 规则若后续接入必须另写 `binding`，不能套 EasyEDA 判据。

## 2. section 级披露，不改 lonely 行

`cross_view_section` 仅在 `checked=true`、`lonely` 非空且模型带 `pin_wires` 时，在现有键之后追加 `geometry`。`checked:false`、`lonely:[]`、无几何模型的键集合逐字不变；lonely 行的六个旧键一个不加。

`geometry` 含：

- `binding`；
- `noWire[]`：最近线段端点距离 >0 的行，含 designator/pin/distance；
- `differentNet[]`：距离 ==0 且 schematicNet != pcbNet 的行，含两端网名；
- `allOffWire[]`：某器件在 lonely 中的脚全部 distance>0，含 `offWire/pins` 原数；
- `unresolved[]`：模型缺该脚坐标的行，不能归入 noWire；
- `counts`：上述四类计数。

`allOffWire` 是 noWire 的子集，只提示整块落位嫌疑，不设比例阈值；高速 10/16 落线不得被误判。距离为 0 但同名也不进 differentNet。缺坐标不等于没画线。

## 3. checkup note

`_note_cross_view_lonely`：

- 去掉 `lonely[:6]` 与省略号，完整列出所有 `designator.pin`；
- 有 `geometry` 时追加分类说明，逐类列出全部相关脚：
  - 「图纸没画线」附最近线端距离；
  - 「落线但网名不同」附 schematicNet→pcbNet；
  - 「整块未落线（落位嫌疑）」附 offWire/pins；
  - unresolved 单独披露。
- 措辞只描述观测，不写「已证明陈旧板」。038W 修正后的真空脚不出 lonely 就不进分类；未判优不算未连接。
- review-read/reviewfinalize 继续 verbatim 传递 crossView；status、suspected、candidateMappings 和板级结论不变。

## 4. negative control

- parser：两只脚同名不同页不得共享线段；WIRE 与符号图形严格区分；旧模型 pin_wires=None。
- 几何：没画线、落线别名、同名落线、整块全未落线、部分落线、缺坐标各自准确分类。
- 无几何时 section/note 完全旧行为；有几何时 lonely 行键集合保持六键；空 lonely 不出现 geometry。
- v1.0.0 真实夹具的落线别名作为消费者证据；038W 后的 ROBOT 真断开不得被拿来硬凑旧 7 条预期。
- 至少两次变异：跨页线段误并入、缺坐标被当成 noWire；红后 cp+SHA-256 恢复。

## 5. 文件域与验收

- 片 1：`core/model.py`、`parsers/schematic.py`、parser 合同测试。
- 片 2：`engines/pcbreview.py`、`cli.py` 的 note、527C2/189A2/537C/autoNetAlias/reviewread 相关测试。
- 本任务书与最终 review-line/TASKMAP/handoff。

禁止改 fixtures、绘制算法、connector/DSH/Rust 业务实现、真实工程；零 git 写、零删除、零真机。聚焦后按串行纪律跑全量及四线。

## 6. 片 1 交卷（parser 几何投影）

落点：`core/model.py` 的 `DesignModel.pin_wires`（dataclass 末位，缺省 `None`，`BoardModel` 继承，旧位置构造与既有字段序不变）；`parsers/schematic.py::_fill_board_model` 在 `placed`/`split.wire_groups`/`split.pages` 作用域内生成 `{"binding": "endpoint", "pins": {(designator, pin): (page, x, y)}, "wires": {page: [(Point, Point), ...]}}`。`wires` 只取 `split.wire_groups`（040 §WI-2 的门原样复用），页键取 `model.board.page_uuids` ∪ 实例所在页——**空页也是键**（「这张图纸没有线」是读数，不能与「没看」同形）。`pins` 只由模型**保留**的那一次放置写（049/105），用 `setdefault` 表达先到先得。未用 `BoardModel.raw`（跨页 first-wins）、未用 `collect_page_layout`（缺 page 维）。KiCad/`.enet`/手工模型不填，保持 `None`。

合同测试 `tests/test_527c2_pin_geometry.py`（10 条，全合成流 + 真实只读夹具）：

- 字段形状：`binding`、空页键、`pins` 坐标 == `transform_point`（90°+mirror 的 posed 点）；
- 两只脚/两页/两板：同页两脚各在自己那段线上且不共段；两页同坐标不并；两板同坐标同设计ator各带各页（`page-1`/`page-2` 互不出现）；同页重复设计ator 报**保留的那次**位置；
- 符号图形：`POLYLINE` 头 + `LINE` 落在两脚上，`wires` 只有真 WIRE 段，两脚仍分属两网；
- 缺省：`DesignModel()`/`BoardModel()`/位置构造旧序（`components` 仍是第 1 位）均为 `None`；
- 真实夹具：`ch340_golden.epro2` 两次解析投影逐字节相等、`pins` 键集与模型 `component.pins` **完全相等**（不缺脚不多脚）、页键 ⊆ 板页；`ProPrj_毕设FOC驱动板`（3 板）各板页集互不相交。

真实计数（`.tmp_527c2_parser/probe_output.log`，只读夹具，`pinDelta` 恒 0）：

| 夹具 | 板 | 页 | WIRE 段 | 脚 | 落脚点 |
|---|---|---|---|---|---|
| ch340_golden | 1 | 1 | 77 | 66 | 54 |
| llc_board | 1 | 1 | 158 | 118 | 103 |
| 毕设FOC Board1/2/3 | 3 | 1/1/1 | 504/27/251 | 428/30/141 | 359/21/133 |
| 高速电机控制器（2 板） | 2 | 1/1 | 527/310 | 427/192 | 352/183 |
| 智能药箱 | 1 | 1 | 241 | 205 | 165 |
| DCDC-12V9V转5V3V3 | 1 | 1 | 133 | 86 | 73 |

「落脚点 < 脚数」不是缺脚：这些脚经电源旗标/网络标签成网，没有线段端点可落（golden 12/66、FOC Board1 69/428），正是片 2 要分类的对象；`pinDelta` 全 0 才是「不缺脚」的证据。

变异（三次，均 `cp` 备份 + SHA-256 还原，还原后与备份同为 `db0c997b…`，10 条全绿）：

1. 跨页线段误并入（去掉 page 维，全部塞进 `""` 桶）→ 7 红（两页/两板/真实多板/空页/图形各中）；
2. 符号图形当 WIRE（`split.wire_groups` 改 `split.segments`）→ 图形那条红，其余 8 绿；
3. 重复设计ator 用后一次放置覆盖（去掉 049/105 的保留判定）→ 「保留的那次」红。

兼容边界：`core/compare.reconcile` 重建模型时 `pin_wires` 落回 `None`（该文件不在本片文件域；重建要把一次重命名的候选交出去，几何是重建前的读数，宁缺不搬）——片 2 必须把 `None` 读成「没几何」而不是「没画线」。`pcbreview`/`cli` 本片零改动。


## 7. 片 2 交卷（pcbreview / CLI 披露）

落点：`engines/pcbreview.py` 新增 `cross_view_geometry(schematic_board, lonely)`（紧接
`cross_view_lonely_pins`，用 `DesignModel.pin_wires` + `core.measure.point_segment_distance`，
`Point` 从 `core.geometry` 取），`cross_view_section` 在三处 `checked:false`、空 `lonely`、
无 `pin_wires` 时**逐字不动**，只在 `checked:true` + `lonely` 非空 + 模型真带几何时，于
`autoNetAliases`（或 `candidateMappings`）之后**追加** `geometry`；`_note_cross_view_lonely`
去掉 `[:6]` 与省略号，有几何时逐类全列。lonely 行仍六键，未加任何字段。

语义边界（都在 `cross_view_geometry` docstring 里写明）：

- `noWire`：`distance > 0`（原理图 canvas 单位，**不是** PCB mil 换算）；该页在 `wires` 里是空表时归 `noWire` 且
  `distance: None` —— 读数写「该页无导线」，**不是**距离 0，也不是「没看」。
- 距离按**脚自己那一页**的线段算（`wires[page]`），不并页：两页同坐标不得互相作证。
- `differentNet`：`distance == 0` 且 `schematicNet != pcbNet`，带两端网名；同名落线不进
  （该行已被 `lonely` 自身披露，是成员数不同、不是网名不同）。
- `allOffWire`：同一 designator 在 `lonely` 里的脚**全部**在 `noWire` 里，给
  `offWire/pins` 原数；部分落线不算，无任何比例阈值。
- `unresolved`：模型没这个脚的坐标（`missingPin`）或坐标所在页 geometry 从未投影
  （`missingPage`）。两档都**既不进 `noWire` 也不进线上**，单独披露，避免「没看」被读成
  「看了没有」。
- `counts`：四类计数。`binding` 原样搬（`endpoint`）。

CLI note：全列 `designator.pin`；有几何时追加一段
「几何读数（binding=…，引脚点到本页 WIRE 线段的距离）：…」，逐类全列，另加
「落在线上且两视图网名相同 N 个」把不属于四类的行也说出来（不留沉默）。措辞只报观测：
`整块未落线（落位嫌疑，只报观测）`，全文无「已证明 / 陈旧板 / 确认」。

### 真实计数（`.tmp_527c2_review/probe_output_utf8.json`，只读夹具）

| 夹具 | 板 | lonely | noWire | differentNet | allOffWire | unresolved |
|---|---|---|---|---|---|---|
| 毕设FOC v1.0.0 | PCB1 | 6 | 0 | 6 | 0 | 0 |
| 毕设FOC v1.0.0 | PCB2 | 1 | 0 | 0 | 0 | 0 |
| 毕设FOC 2026-09-17 | PCB3 | 9 | 0 | 9 | 0 | 0 |
| 毕设FOC 2026-09-17 | PCB1/PCB2 | 0 | — 无 geometry 键（空 lonely 不出现几何） | | | |
| 高速电机控制器 | PCB2 | 9 | 0 | 9 | 0 | 0 |
| ch340_golden / llc_board / 智能药箱 / DCDC-12V9V转5V3V3 / ROBOT ctrl FOC | — | 0 | — | — | — | — |

真实读数只出现两类：落线别名（`differentNet`）与落线同名（PCB2 的 `CN2.5`：两视图都叫
`SPI3_MISO`，成员数 1 vs 3，几何四类全 0 —— 正是 note 里那句「落在线上且两视图网名相同」）。
`noWire` / `allOffWire` / `unresolved` 在这批夹具上全 0，合成流负责覆盖（见下）。

`ROBOT ctrl FOC` 本片**不设断言**：038W 修正后的真空脚不出 `lonely`，此处 `lonely` 为 0，
拿旧「7 条」当预期就是把夹具形状当读数（任务书 §4）。

### 真实端到端（`checkup --file`，`.tmp_527c2_review/out/`）

`report.md` 的 `> …` 行与 `report.json.source.notes[4]`（`.tmp_527c2_review/note_real.md`）：

```
PCB1：6 个引脚（U10.6、U10.8、U10.9、U10.11、U10.14、U10.16）；几何读数（binding=endpoint，
引脚点到本页 WIRE 线段的距离）：落线但两视图网名不同 6 个：U10.6（SHA→MOTA）、…、
U10.16（SLC→IC+）；PCB2：1 个引脚（CN2.5）；几何读数（…）：落在线上且两视图网名相同 1 个
```

`report.json` 的 `pcb_review.boards[0].crossView` 键序：
`checked, minPins, lonely, status, candidateMappings, autoNetAliases, geometry`（geometry 末位），
`geometry.counts = {noWire:0, differentNet:6, allOffWire:0, unresolved:0}`。

消费者证据：同一真实 section 过 `review_read_section(report, "crossView")` 后与原件**逐字相等**
（deepcopy，report 未被改），`status` 仍是 `suspected`；
`review_finalize._suspected_boards(report) == [0, 1]` —— 几何不参与，verdict/status 不变。

### 合成负例（`tests/test_527c2_cross_view_geometry.py`，14 条）

没画线（含距离与「该页无导线」两档）、落线别名、同名落线（四类全 0 但 note 说出来）、整块未落线
（U7 3/3）与部分落线（U9 3 落 1 在线上 → 不算）、缺坐标两档（`missingPin` / `missingPage`
且不进 `noWire`）、空页、两页同坐标不互证、无几何（旧键集 `checked,minPins,lonely,status,
candidateMappings`，note 无几何句）、空 lonely（三键逐字）、`checked:false` 两形、lonely 行六键、
note 全列 8 行（`…` 不出现、`距最近线端` 出现 8 次）、真实 v1.0.0 消费者（见上）。

### 变异（两次，均 `cp` 备份 + SHA-256 还原）

备份 `.tmp_527c2_review/pcbreview.py.bak`，还原后与备份同为
`2056e0d0af70d57ad552fd73daff2ebabacafc8e577453b1ee7f615c7becb956`，14 条复绿。
（变异后另做了一处**纯 docstring** 的措辞订正——`noWire` 距离量的是线段最近点、
不是端点，`binding` 仍写 parser 的 `endpoint`——交付版文件 sha256 为
`0530db5f1e30dcba833391b562cb76382b9091685b5557de97b5de194e3cbda9`，`.bak` 已按交付版重取；
该订正无代码改动，14 条与聚焦 178 条在交付版上复跑仍全绿。）

1. **跨页误并**：`segments = wires.get(page)` → 并全部页的线段 → 2 红
   （`test_a_foot_off_the_lines_and_a_sheet_with_no_wires_are_two_readings`、
   `test_two_sheets_sharing_one_line_are_still_two_sheets`：第二页的脚被第一页同坐标的线
   认成落线），其余 12 绿；
2. **缺坐标误归 noWire**：`missingPin` 分支改塞 `noWire`（并记进 `off_wire`）→ 2 红
   （`test_a_missing_coordinate_is_its_own_state_and_never_no_wire`、
   `test_two_sheets_sharing_one_line_are_still_two_sheets`），其余 12 绿。

### 聚焦回归

`tests/test_527c2_cross_view_geometry.py test_527c2_pin_geometry.py test_189a2_schematic_nets.py
test_537c_crossview_candidates.py test_auto_net_alias.py test_537d_review_read.py
test_537c_review_evidence_cli.py`，`-q -n 4 --dist loadfile
--basetemp=.tmp_pt_527c2_review` → **178 passed**（`.tmp_527c2_review/focused.log`；
docstring 订正后的交付版复跑同名命令再绿一次，`focused_final.log`）。
另跑相邻的 `test_537c_live_candidates.py test_537d_finalize_validation.py
test_537d_review_read_artifacts.py test_537d_review_read_netlist.py` → 214 passed。
另抽查 `test_126a_pcb_review_plumbing.py test_154_board_report.py test_039c_review_flow.py
test_073_exit_codes.py test_072_coverage_gate.py test_063_warning_triage.py` → 183 passed，
**1 失败与本片无关**：`test_the_rulebody_digest_covers_the_pcb_subpackage` 期望
`1854fea9`、量得 `626e16ef`——该摘要是 `src/boardwise/rules/` 目录的指纹，工作树里
`rules/facts.py`、`rules/pcb/distance.py` 已有他人在途改动（`git status` 可见），本片
只动 `engines/pcbreview.py`、`cli.py` 与新增测试，不在该目录内。未改该断言。

### 未做 / 边界

- KiCad / `.enet` / 手工模型 / `core.compare.reconcile` 重建后的模型 `pin_wires is None`：
  片 2 读成「没几何」，section 与 note 保持旧形，不假装「没画线」。
- 未改 parser/model/其他源码、fixtures、绘制线、041/038W/X/529 文件；零 git 写、零删除、
  零真机、零额外 agent。
- 既有 `test_189a2 / test_537c_crossview_candidates / test_auto_net_alias / test_537d_review_read /
  test_537c_review_evidence_cli` **一条未改**：几何是加性键，旧断言（含 `list(section) ==
  ["checked","minPins","lonely"]` 与 `["checked","reason"]` 两处键序钉）全绿。
- `allOffWire` 只在本片新增的合成流上被覆盖：这批只读夹具没有「整块未落线」的真实样本，
  真实世界里它是否常见，需要真机/更多归档才有读数，本片不声称。


## 8. B5 复核修复 A（2026-11-06，端点语义）

复核发现：`cross_view_geometry` 原来用 `core.measure.point_segment_distance`（到线段**最近点**），
于是引脚落在一条线的**内部**时距离读 0 → 被归进 `differentNet`（「落线但网名不同」），
而 parser 的 `binding="endpoint"` 说的是「只在端点相连」。两个读数自相矛盾：把
「没落在任何端点上」说成「落在这条线上，只是网名不同」。

改法（`engines/pcbreview.py`）：

- 距离改为 **引脚点到该页所有 WIRE 线段两个端点的最小欧氏距离**，用 `math.hypot` 现算；
  `point_segment_distance` 的 import 删除，`read_stackup` 保留（PCB 走线规则仍用它）。
  单位不变：原理图 canvas 单位，不是 PCB mil 换算。
- 判据仍是一条：`distance > 0` → `noWire`（含「该页无导线」`distance: None`），
  `distance == 0` 且网名不同 → `differentNet`。变的只是「0」的含义：**落在端点上**，
  与 `binding` 同一条规则。
- docstring 与 `noWire` 那一段同步改写：写明测的是端点距离、不是线段内部距离，
  并点明「线中间」正是 endpoint 判据说「不连」的那种情形。
- 内部函数注释写清为什么不用线段距离（否则会报出网表从没说过的 `differentNet`）。

合成负例（`tests/test_527c2_cross_view_geometry.py` 新增
`test_a_foot_in_the_middle_of_a_line_is_off_the_line_not_an_alias`）：脚在 (5, 0)、线段
(0, 0)-(10, 0)、两视图网名不同 → **必须** `noWire` 且 `distance == 5`，`differentNet`
为空；同一测试里两只落在两端点 (0,0)/(10,0) 的脚仍进 `differentNet`（真落线别名不误伤）。
该文件其余用例凡是「落在线上」的坐标都改成真的端点（原来有 6 处落在内部，改端点后含义才是
endpoint 语义）：

| 用例 | 原坐标 | 现坐标 |
|---|---|---|
| `test_a_foot_off_the_lines_and_a_sheet_with_no_wires_are_two_readings` | U9.3 (60, 50) | (100, 50) |
| `test_two_sheets_sharing_one_line_are_still_two_sheets` | U9.1 (60, 50) | (100, 50) |
| `test_the_same_name_on_a_line_is_a_difference_the_netlist_already_states` | U9.1 (10, 0) | (100, 0) |
| `test_a_whole_block_off_the_lines_is_a_hint_and_a_partial_one_is_not` | U9.4 (40, 0) | (100, 0) |
| `test_a_missing_coordinate_is_its_own_state_and_never_no_wire` | U9.1 (10, 0) | (100, 0) |
| `test_the_clause_is_observation_only` | U9.3 (60, 0) | (100, 0) |

真实夹具（只读）：`test_the_real_v100_board_carries_its_landed_aliases_through_the_reader`
与 `test_the_note_clause_on_the_real_board_names_all_six_aliases` **一字未改**仍绿 ——
毕设FOC v1.0.0 的 6 条 `differentNet`（U10.6/8/9/11/14/16）在端点语义下距离仍为 0，
即本片此前的「落线别名」真实读数不因判据收紧而改变（15 passed，见下）。这正是收紧判据该有的
negative control：改的是「内部点」，不是「端点」。

### 变异（两次，`cp` 备份 + SHA-256 还原，本批只针对本项）

备份 `.tmp_b5_fix_a/pcbreview.py.bak`，变异时的版本 sha256
`b5ebd3940e7f6932e8534163bfa84a2653523e392bc196250a100e6e32f20c91`；变异后另做了一处
**纯 docstring/注释**的措辞订正（`differentNet` 一句写明「距离 0 = 恰在线段**端点**上」），
交付版 sha256 `45a627ccb85cc2a3cd5d8163c7d33c4b4e5200f5ba350a23a1ee85fff795788c`，
`.bak` 已按交付版重取；该订正无代码改动，交付版上 6 文件聚焦复跑仍 156 passed / 1 既有失败，
本文件 15 passed。

1. **内部点误算落线**：距离改回 `point_segment_distance`（到线段最近点）→
   `test_a_foot_in_the_middle_of_a_line_is_off_the_line_not_an_alias` 1 红
   （`noWire == []`，内部点被判成落线），其余 14 绿（`.tmp_b5_fix_a/mutation1.log`）。
   还原后字节一致、15 passed（`mutation1_restored.log`）。

### 聚焦回归

`tests/test_527c2_cross_view_geometry.py test_527c2_pin_geometry.py
test_038w_pad_net_journal.py test_038u_record_consistency.py test_125_pcb_measure.py
test_126a_pcb_review_plumbing.py`，`-q -n 4 --dist loadfile --basetemp=.tmp_pt_b5_fix_a`
→ **156 passed, 1 failed**（`.tmp_b5_fix_a/focused2.log`），失败项是本任务书 §7 已记过的
`test_the_rulebody_digest_covers_the_pcb_subpackage`（期望 `1854fea9`、量得 `626e16ef`，
量的是 `src/boardwise/rules/` 目录指纹，该目录有他人在途改动，本批未动该目录、未改该断言）。

### 未做 / 边界

- `cli.py` 的 note 前缀「引脚点到本页 WIRE 线段的距离」按本批文件域**未动**（cli.py 不在允许
  修改清单内）；语义已变成「到线段**端点**的距离」，措辞偏旧。这是**待办**：下一批允许碰
  cli.py 时把该句改成「引脚点到本页 WIRE 线段**端点**的距离」，并同步
  `test_527c2_cross_view_geometry.py` 里对 note 的断言（现有断言只钉了
  `几何读数（binding=endpoint` 与前缀常量，未钉该句，故今日不红）。
- 未改 finding/severity/verdict、`lonely` 行六键、section 键序、`binding` 取值。
- 全量四线、真机、其他批次（041/038X/529/541/绘制线）一律未碰。
