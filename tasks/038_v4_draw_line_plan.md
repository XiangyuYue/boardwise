# 038D V4 绘制线隔离与适配计划（2026-10-31）

> 规划稿，未实施。本文只回答“V3/V4 绘制线哪些共用、哪些隔离、按什么顺序验证”，
> 不授权设计写入、不授权 connector 热更、不授权 git 写。
>
> **总边界以 [`docs/v3-v4-boundary.md`](../docs/v3-v4-boundary.md) 为准**；本文只展开绘制线。
>
> 目标不是做两套绘制器，而是让**容器与宿主差异止于适配层**：
> 编译器、语法、布局、布线、可读性和落图计算保持一份实现。

## 1. 结论先行

- **共用**：`CircuitSpec` / `PresentationSpec` / `LayoutPlan` / `PageLayoutPlan` /
  `ChangePlan`，单模块与整页编译器，语法/岛/布局/布线，`readability` 与
  `drawlint` 的几何谓词，`drawapply` 的位号/引脚/census/回验纯计算。
- **隔离**：工程容器（`.epro2` / `.eprj3`）、页面寻址（V4 容器文档无 tab）、
  页面框读取、宿主能力（native netlabel、新建页、写动作）、符号/字体/渲染测量包。
- **当前新绘制链不读工程容器**：`draw compile` 只吃
  `--circuit / --presentation / --profiles / --page-box`，所以 V4 的 `.eprj3`
  容器变化**不需要改绘制编译器**。只有将来做“从已有 V4 页面回放”时，才在
  parser 入口增加分派。
- **V4 现在能读页面，不等于能画**：P1/P2 的 readback / netlist / render 已成功，
  但 `sch.geometry`、`sys.get_document_source` 图幅、`sch.component_pins`、
  写动作与 native netlabel 尚未覆盖。

## 2. 分层边界

| 层 | 现有代码 | 裁决 |
|---|---|---|
| 设计意图与数据合同 | `core/circuitspec.py`、`presentationspec.py`、`layoutplan.py`、`pagelayoutplan.py`、`changeplan.py` | **共用**，不出现 V3/V4 分支 |
| 单模块/整页编译 | `engines/drawcompiler.py`、`engines/pagecompiler.py`、`engines/grammar/*`、`engines/island*`、`layout.py`、`router.py` | **共用**，不得复制 |
| 可读性门 | `engines/readability.py` | **共用**，阈值与规则一份 |
| 落图纯计算 | `engines/drawapply.py` 的位号、引脚偏移、census、postcondition | **共用**；但当前文件混入 V3 实测事实，需按 D1b 抽出 |
| lint 谓词 | `engines/drawlint.py` | **共用**；渲染文本提取与阈值按宿主校准 |
| 工程容器 | `parsers/epru_stream.py`、`parsers/eprj3.py`、`parsers/schematic.py` | **隔离在 parser**；绘制编译器不得 import |
| 页面寻址/图幅/落图执行 | `cli.py` 的 `_draw_live_page_box`、`_draw_live_context`、`_draw_apply_flow`、`_cmd_draw_lint` | **隔离为宿主适配层**；只寻址 SCH_PAGE |
| 符号/字体/渲染测量 | `core/symbolprofile.py`、`core/textmetrics.py`、`drawlint` 的 SVG 常量 | **合同共用，数据包隔离**；不能默认复用 V3 测量 |

## 3. 批次

### D0 —— V4 绘制只读基线（0 生产代码）

**目标**：在不动画布的前提下，把“V4 能不能被绘制线读”量化到五项：
页面身份、图幅、几何、渲染、lint 回放。

**范围**

- 只读：`doc.list` / `document.current` / `sys.identity` /
  `sys.get_document_source` / `sch.geometry` / `export.render`。
- 不写：不 `doc.open` 容器文档，不 `doc.new`，不 place/delete/save。
- 仅对任务书**逐字点名**的 V4 工程；当前证据版本 4.1.93，现场版本不同则以
  `sys.probe.version` 为准。

**步骤**

1. 核身份：焦点工程名、page UUID、`document.current` 三者一致；不一致即停。
2. 取当前页 UUID，不用 schematic 容器 UUID。
3. `sys.get_document_source` 读当前页，提取 `Width/Height/Blade Width/
   Title Block Position`，记录原始字符数与属性名。
4. `sch.geometry` 读当前页，记录 `components/wires/pins/netlabels/bboxes`
   的可用性、计数、空槽与 `meta`。
5. `export.render format=svg` 读当前页，确认非空、文字节点存在、页面类别可识别。
6. 用捕获的 snapshot + SVG 跑 `boardwise draw lint --snapshot … --render …`，
   记录 exit、ERROR/WARN/INFO、`text_readable` 与“不可读”原因。
7. 复位焦点；记录 `focusRestore`。

**完成条件**

- 五项分别给出 `pass / fail / unknown`，不允许合并成“V4 可用”。
- 页面身份、图幅、几何、SVG 四项均有原始文件与 sha256。
- lint 回放有真实 exit 与 findings 计数；文本几何不可读时必须写
  `text_readable=false`，不得报 0 ERROR 冒充通过。
- 证据：`.tmp_038d0/` 原始 JSON/SVG + `outputs/review/v4-draw-baseline.md`。

**停止条件**

- 工程名不符、page UUID 不唯一、焦点无法复位。
- `sys.get_document_source` 为空但无法说明是页面无图幅还是通道失败。
- `sch.geometry` 为空、`components=0` 或返回错误结构。
- 任何一步需要写画布才能继续——停下来交主代理，不自行扩权。

### D1a —— 页面/图幅适配（只在 D0 证明有差异时开）

**目标**：把 V4 的“页面可寻址、图幅可读”收进一个页面适配器，不改绘制算法。

**文件域**

- `src/boardwise/cli.py` 的 draw live 页面函数（`_draw_live_page_box`、
  `_draw_live_context`、`_cmd_draw_lint` 的 live 半段）。
- 必要时 `core/pageframe.py` 的输入适配；图幅数学本身不动。
- 新测试 `tests/test_038d_page_adapter.py`，只读夹具/合成 payload。

**要求**

- 永远解析到 SCH_PAGE；容器文档只作为元数据，不作为 `doc.open` 目标。
- 图幅读不到时拒绝并说明“页面没声明”，不补 A4。
- V3 的 `sys.get_document_source` + `sheet_attrs_from_text` 行为逐字节不变。
- 若需要改 `core` 或 CLI 的共享入口，按 `tasks/shared-platform.md` 的集成锁
  单列，不与算法批同批。

**完成条件**

- V4 synthetic payload 能解析出页面框；V3 既有测试全绿。
- 无 V4 页时仍按原错误码拒绝（3=状态不可陈述，5=页面没声明）。
- 至少两处变异：容器 UUID 误当页面、图幅缺失时补默认值，均应变红。

### D1b —— 测量包与 lint 校准（只在 D0 证明渲染/文本差异，或 D2a 证明 profile/写回差异时开）

**目标**：把“V3 实测数据”从算法中分离；算法仍只有一份。

**文件域**

- `src/boardwise/core/symbolprofile.py`（只加宿主/来源元数据，不改几何合同）。
- `src/boardwise/core/textmetrics.py`（只加宿主校准常量或读取入口）。
- `src/boardwise/engines/drawlint.py`（渲染文本提取与颜色/字号校准）。
- `src/boardwise/engines/drawapply.py`（把 label stub、flag glyph、文字行等
  V3 实测事实改为注入的宿主能力，不改默认行为）。
- 新测试 `tests/test_038d_host_profile.py`、`tests/test_038d_lint_render.py`。

**要求**

- `SymbolProfile` 几何合同不变；profile 文件增加结构化 `host` / `library`
  来源字段，不能只靠 `source` 字符串。
- V3 默认 profile 与 lint 常量保持不变；V4 数据包单独命名。
- 不按版本号在 core 写 `if V4`；用 capability/profile 参数注入。
- 真实工程内容不入库；profile 只保留符号几何与来源哈希。

**完成条件**

- V3 现有 draw 测试全绿，离线预览/计划哈希不变（纯重构批要求逐字节等价）。
- V4 渲染样本的 lint 文本谓词不再因颜色/class 漂移而静默失准；无法校准时明确
  `text_readable=false`。
- 至少两处变异：V4 profile 误用 V3 文字行、V4 SVG class 误判，均应变红。

### D2a —— V4 写能力探针（只在 `test`/`test2`，需另行授权）

**目标**：回答“V4 能不能落图”，不先改生产代码。

**范围**

- 在任务书逐字点名的测试工程临时页上，依次 probe：
  `sch.doc.new` → `sch.place_component` → `sch.component_pins` →
  `sch.place_wire` → `sch.place_power` → `sch.place_netlabel` →
  `sch.doc.save` → readback。
- 每次只做一个能力；失败先回读，不重试；超时/断连按未知结果记录。
- `sch.place_netlabel` 单独记录：成功、超时但已落、彻底不可用三种结果。
- 不碰真实工程；不删除临时页，除非另行授权。

**完成条件**

- 每个动作给出 `ok / failed / unknown` 与真实耗时、回读证据。
- 若 native netlabel 可用，记录它是否产生可连通网表；若不可用，明确继续用
  name stub，不把 V3 降级路径误写成 V4 缺陷。
- 若 `sch.doc.new` 或 place 动作失败，停止，不进入 D2b。

### D2b —— 标签/写路径适配（只在 D2a 证明需要时开）

**目标**：只改“标签载体”与宿主能力注入，不复制 apply。

**文件域**

- `src/boardwise/engines/drawapply.py` 的 label carrier 选择。
- `src/boardwise/cli.py` 的 apply live 调用与报告字段。
- 新测试 `tests/test_038d_label_carrier.py`。

**要求**

- V3 默认仍是 stub；V4 只有 capability 明确为真时才走 native label。
- 两条路径共用同一份 `ChangePlan`、同一套 netlist/postcondition 验证。
- 失败必须回退到 stub 或明确拒绝，不能“先落一半标签再报成功”。
- 不改 `LayoutPlan` / `PageLayoutPlan` schema。

**完成条件**

- V3 落图行为不变；V4 标签路径有真实 readback 证据。
- 无论走哪条，最终网表成员与 `drawapply` 的 postcondition 一致。
- 至少两处变异：capability 误报为真、标签失败后静默继续，均应变红。

### D3 —— V4 完整绘制验收

**目标**：用一条**合成/公开**的小电路，在 V4 测试页走完
`compile → plan → apply → lint → 逐脚 → 视觉 → 保存`。

**范围**

- 使用现有合成规格（如分压/LDO/RC），不使用真实工程内容。
- 只在 `test`/`test2` 的临时页；先写身份，后写画布。
- 逐脚对照源网表；lint 0 ERROR；渲染 SVG/PNG 人眼复核；保存后回读。
- 不做 PCB，不碰真实工程，不发布。

**完成条件**

- 编译 `ok=True`、lint 0 ERROR、逐脚全通、视觉逐岛说清。
- V3 同一规格的离线计划/预览哈希不变；V4 计划有单独证据。
- 失败候选只进 `.tmp_038d3/`，不落正式画布、不端给用户。

### D4 —— 回归与交接

- Python 全量（独立 `--basetemp=.tmp_pt_038d`，`-n 4 --dist loadfile`）。
- connector `npm test` + typecheck；DSH typecheck/test/build；Rust 按仓库要求。
- 回归前先跑聚焦：`tests/test_053b_drawcompiler.py`、
  `test_054_drawapply.py`、`test_056_pagecompiler.py`、
  `test_057_draw_page_cli.py`、`test_111_draw_lint.py`、
  `test_534_*`。
- 交接写清：哪些是 V4 实测、哪些是 V3 回归、哪些仍未证实。
- 不做 git 写；commit/push 逐次问岳。

## 4. 决策闸

| D0 结果 | 下一步 |
|---|---|
| 页面/图幅/几何/渲染/lint 全 pass，profile 与 V3 一致 | **不加生产代码**，只补 V4 证据与测试；V4 记为“绘制只读可用” |
| 页面/图幅有差异 | 开 D1a |
| geometry/render 文本有差异 | 开 D1b |
| 写动作/native label 有差异 | 先 D2a，再决定是否 D2b |
| 任一项 unknown | 不进入 D2，先补证据或明确记录环境限制 |

## 5. 非目标

- 不做 V4 专用 `drawcompiler` / `pagecompiler` / `readability`。
- 不为 `.eprj3` 改绘制算法；当前 `draw compile` 不读容器。
- 不把 V3 的 profile、文字宽度、lint 颜色当通用常量。
- 不把 V4 schematic 容器当页面打开。
- 不改 ReviewReport / conclusion / triage / DSH 工具面。
- 不因本计划自动获得写权限；D2/D3 必须另行逐字点名测试工程。

## 6. 证据与落点

- 一次性探针：`.tmp_038d0/`、`.tmp_038d2/`、`.tmp_038d3/`。
- 只读报告：`outputs/review/v4-draw-baseline.md`。
- 长期验收：`evidence/038d/`（只在需要长期保留时建）。
- 计划本身：本文件。

## 7. 与现有 038 的关系

- `tasks/038_v4_isolation_plan.md` 管审查线容器/语义继承；本文件只管绘制线。
- 两者共享的原则相同：**容器差异止于适配层，语义/规则/报告不复制**。
- 现有 `038F1–F5` 的 parser/CLI 批次不并入本计划；如果 D1a/D1b 需要动
  共享 parser/CLI，按 `tasks/shared-platform.md` 另开集成锁批次。

## 8. 执行记录（2026-10-31）

- **D0 通过**：`test` V4 的 P3 页，页面身份/图幅/几何/SVG/lint 五项通过；
  `drawlint` 0E/2W/0I，`textReadable=true`。证据 `outputs/review/v4-draw-baseline.md`。
- **D2a 基本通过**：`test V4` P1 空白页上 place/component_pins/wire/power/save/netlist
  均通过；`sch.doc.new` 建 P2 并 `doc.delete_page` 删除成功；native netlabel 仍失败
  （5 ms 无值、readback 无标签），继续 name stub。证据
  `outputs/review/v4-draw-write-probe.md`。
- **D3 通过**：10k 分压器在 `test V4` P1 走完 `compile → plan → apply → lint`；
  apply exit 0、网表 VIN/TAP/GND 逐脚正确、lint 0E/0W/1I、PNG 已出、保存
  `saved_unverified`。证据 `outputs/review/v4-draw-apply.md`、`evidence/038d/`。
- **V4 实测差异**：
  1. 库 `getByLcscIds` 对 `C9900012843` / `C20482775` 返回空，但 `lib.device.search`
     精确命中同一 Supplier Part；`draw apply` 已加“明确 miss 才精确搜索 + uuid 重试”
     的窄回退。
  2. 宿主把 TAP 的 named label 载体与 unnamed 同网导线合并；canvas 无名线长度桶
     改为按每条计划导线的几何覆盖并封顶，不再误报缺段。
- **代码变动**：`src/boardwise/cli.py`、`src/boardwise/engines/drawapply.py`；
  回归 `tests/test_054_draw_cli.py`、`tests/test_054_drawapply.py`。
- **未做**：D1a/D1b（D0 没有触发页面/图幅/profile 差异），D2b（native label 不可用），
  PCB。全量 Python **8824 passed / 23 skipped / 1 known MSYS failure**；
  connector 542 pass + typecheck；DSH 127 pass/1 skip + typecheck/build；Rust 47 pass/4 ignored。
- **D3 追加（2026-11-01，534A-V4）**：同一套绘制链在 `test V4` P2 上落下
  **CH343 五岛全页**（11 件 / 54 计划线 / 15 旗标），apply exit 0、lint 0E/2W、
  独立逐脚 17 网/58 脚/3 NC PASS、`saved_unverified`。这不是分压页的外推：
  Type-C 16P、CH343G、2×5P 排针、5 岛跨岛标签都在同一页上。
  证据 `evidence/534a_v4/report.md`。V4 本页新增实测：LCSC 索引 11/11 miss，
  精确搜索/MPN 回退后可落；native netlabel 仍不可用；H1 `Name` 表达式需改
  `2x5P`；`sch.set_component_attribute` 回执 `applied:false` 但 readback 正确。
- **D4（部分）**：本轮未改生产代码，未重跑四线；只做 V4 真机全链和独立网表核对。
  V3 页 `test` P4 保留但已被 V4 P2 取代；不把 V4 结果写成全库/PCB 兼容。
