# V3 / V4 边界（唯一口径）

日期：2026-10-31 · 适用：审查线、绘制线、在线 bridge / connector
状态：**边界说明，不是“V4 全兼容”声明**

> 一句话：**语义只有一套，差异止于容器与宿主适配层。**
> 任何规则、布局、布线、可读性、报告结论都不得出现 `if V3 / if V4` 两套实现。
> 版本差异只能用**能力（capability）或数据包（profile）**注入。

相关细节件：
[`tasks/038_v4_isolation_plan.md`](../tasks/038_v4_isolation_plan.md)、
[`tasks/038_v4_live_gaps.md`](../tasks/038_v4_live_gaps.md)、
[`tasks/038_v4_draw_line_plan.md`](../tasks/038_v4_draw_line_plan.md)、
[`outputs/review/v4-online-acceptance.md`](../outputs/review/v4-online-acceptance.md)、
[`docs/pits.md`](pits.md)。

## 1. 版本与证据锚

| 项 | V3 | V4 |
|---|---|---|
| 宿主 | EasyEDA Pro **3.2.186**（历史真机锚） | EasyEDA Pro **4.1.93**（当前真机锚） |
| 工程壳 | `.eprj2`（SQLite） | `.eprj3` 文件夹；实测也仍可打开 `.eprj2` |
| 导出容器 | `.epro2` ZIP | `.epro2` ZIP，或 `.eprj3` 文件夹 |
| 在线页面单位 | 容器文档 / 页面均可寻址 | **只有 SCH_PAGE 可寻址**；schematic 容器无 tab |
| 当前承诺 | 生产主路径 | **Tier-A 归档 + 单 PCB 在线审查/绘制已验证部分** |

“V4 能读”不等于“V4 能写”；“V4 单页能写”不等于“V4 全工程兼容”。
所有结论按下面矩阵逐项说，禁止合并成一句“V4 可用”。

## 2. 分层边界

| 层 | V3 | V4 | 裁决 | 代码落点 |
|---|---|---|---|---|
| 工程壳 | `.eprj2` | `.eprj3` / 仍可 `.eprj2` | **不直接读设计**，引导导出；壳只做元数据 | `parsers/`、CLI 输入层 |
| 导出容器 | `.epro2` | `.epro2` / `.eprj3` 文件夹 | 适配器隔离 | `parsers/epru_stream.py`、`parsers/eprj3.py` |
| 记录帧 | `{env}||{body}|` | 同帧；真样本 EOF 可缺最后 `|` | **共享** `epru_stream`，只修合法尾帧 | `parsers/epru_stream.py` |
| 原理图变换 | V3 坐标/key | `yAxisDirection`、PIN id、页内嵌库 | 只在 eprj3/schematic 既有分支隔离 | `parsers/eprj3.py`、`parsers/schematic.py` |
| PCB 容器 | `.epro2` 内 PCB 文档 | `pcb/*.epcb2` | 新增 V4 source 适配；`split_documents` 后继承 | `parsers/eprj3.py` → `Epro2Source` |
| 语义模型 | DesignModel / BoardGeometry / ProjectModel | 同左 | **全部继承**，禁止两套规则 | `core/`、`rules/` |
| 审查规则/报告 | Finding、ReviewReport、conclusion、triage/finalize | 同左 | **冻结合同**；只修覆盖与证据真实性 | `rules/`、`review/` |
| 绘制合同 | CircuitSpec / PresentationSpec / LayoutPlan / ChangePlan | 同左 | **全部继承** | `core/*spec.py`、`core/changeplan.py` |
| 编译器/语法/布局/布线 | `drawcompiler` / `pagecompiler` / grammar / island / router | 同左 | **一份实现**，不得复制 | `engines/drawcompiler.py` 等 |
| 可读性/lint 几何 | `readability` / `drawlint` 谓词 | 同左 | 谓词共用；**测量数据按宿主校准** | `engines/readability.py`、`drawlint.py` |
| 页面寻址/图幅/落图 | V3 页 | V4 只认 SCH_PAGE；图幅从 `sys.get_document_source` 记录流读 | **宿主适配层隔离** | `cli.py` 的 draw live 函数 |
| 符号/字体/渲染测量 | V3 profile | 本页 11 件共享 profile 与 V4 引脚回读一致；新符号仍需**真机现量** | 合同共用，数据包隔离 | `core/symbolprofile.py`、`textmetrics.py` |
| 标签载体 | native label + stub 回退 | **native netlabel 在 4.1.93 不可用** → name stub | 能力注入，不复制 apply | `engines/drawapply.py` |

## 3. 在线能力矩阵（V4 4.1.93 实测）

| 能力 | V3 | V4 | 口径 |
|---|---|---|---|
| 归档审查（`.epro2` / `.eprj3`） | 支持 | 支持（单 PCB） | Tier-A；多 PCB 不承诺 |
| `doc.list` / `document.current` | 支持 | 支持 | 容器与页面要分清 |
| schematic 容器 `doc.open` | 可用 | **无 tab**，不可作为采集目标 | 只寻址 SCH_PAGE |
| 页面 `sch.readback` / `sch.netlist` | 支持 | 支持（P1/P2 实测） | 焦点必须在页 |
| 页面 `export.render`（PNG/SVG） | 支持 | 支持（原理图页） | 导出前先激活 |
| PCB `export.render` | 支持 | **不适用**：60 s 不返回 | `pcbImage = not-applicable`，不伪造图 |
| 主机 ERC | 聚合计数 | 4.1.93 起逐条对象 | 解析器保留两种形状；`total=0/passed` 不等于通过 |
| 新建原理图页 | 支持 | `sch.doc.new` 可用；**页名可能被忽略** | 以 `doc.list` 实际名为准 |
| `sch.place_component` | 支持 | 支持；LCSC 索引可能漏，CLI 有精确搜索回退 | 回退只在“匹配不到库器件”时触发 |
| `sch.component_pins` | 支持 | 支持 | 引脚回读用于落图前校验 |
| `sch.place_wire` / `sch.place_power` | 支持 | 支持 | 写前带 `pageUuid` |
| `sch.place_netlabel` | 可用 | **4.1.93 超时/不可用** | 继续 name stub，不把降级写成 V4 缺陷 |
| `sch.doc.save` | 支持 | 支持，但只到 `saved_unverified` | 无 close/reopen 就不能写 `saved_verified` |
| 删除页/图元 | 支持 | 支持（逐件慢） | 破坏性动作先确认 |
| 绘制 compile/plan/apply | 支持 | **CH343 五岛页已在 V4 P2 全链实测**；简单分压页 D3 也通过 | 只按页面类型/符号集合声明，不外推全库 |

**当前样本归属（2026-11-01 更正）**：534A 的 CH343 五岛页现在以 **V4 `/test V4` P2**
（`40091c5d26a5db27`，`.eprj3`）为交付页：11 器件 / 54 段计划线 / 15 旗标，
apply exit 0、lint 0E/2W、独立逐脚 **17 网 / 58 脚 / 3 NC PASS**、`saved_unverified`。
V3 `/test` P4（`26e6a63bae878c44`）的同一份 spec 落图仍在，但**已被 V4 P2 取代，
不再作为交付页**；V3 页未删除。

V4 本页实测差异：LCSC 索引对 11 个器件全 miss（精确搜索/MPN 回退后才落位）、
native netlabel 仍不可用（走 name stub）、H1 `Name` 表达式需改为 `2x5P` 才不压线、
`sch.set_component_attribute` 回执 `applied:false` 但 readback 正确、标题栏页码
字段显示 `1/1`（宿主元数据未刷新）。详见
[`evidence/534a_v4/report.md`](../evidence/534a_v4/report.md)。

## 4. 绘制线专用边界

### 4.1 共用

`CircuitSpec`、`PresentationSpec`、`SymbolProfile` 合同、`draw compile`、`draw plan`、
`ChangePlan`、`draw apply` 的纯计算（位号/引脚/census/回验）、`readability` 与
`drawlint` 的几何谓词，全部一份实现。

### 4.2 必须隔离

1. **容器入口**：`.eprj3` 的页面/PCB 解析只在 parser；绘制编译器不得 import 容器。
2. **页面寻址**：V4 只认 `SCH_PAGE` UUID；schematic 容器只做元数据。
3. **图幅**：V4 从 `sys.get_document_source` 的图纸符号记录读
   `Width/Height/Blade Width/Title Block Position`；读不到就拒绝，不补 A4。
4. **测量包**：V4 符号/文字行必须现量；V3 profile 不得直接套到 V4。
5. **标签能力**：V4 只有 capability 明确为真才走 native label；当前为假，走 stub。
6. **保存语义**：V4 只报 `saved_unverified`；close/reopen 由人做，不能自证。
7. **PCB 图像**：V4 没有独立已验图像通道；PCB 只走 `pcb.readback` + `pcb.geometry`。

### 4.3 明确不承诺

- V4 **多 PCB** 映射与审查；
- V4 全部跨视图语义、网差与单位语义（POUR/POURED 等）；
- V4 实时 PCB 位图；
- V4 native netlabel；
- “V4 全格式、全工程、全电路都能自动画好”；
- 用 V4 单页 D3 的通过，替代任意新页的三关验收。

## 5. 改动检查清单

改任何一层前，先回答：

1. 这是**语义**还是**适配**？语义改动只能有一份，适配改动只能落在上表“隔离”列。
2. 是否在 `rules/`、`drawcompiler`、`readability` 里写了版本分支？写了就是越界。
3. 是否把 V3 实测的符号/文字/页面常量带进 V4？带了就必须改为 capability/profile 注入。
4. 是否把 `saved_unverified`、`incomplete`、`partial`、`not-applicable` 写成了通过？
5. 是否同时改了 V3 行为？V3 必须有回归或逐字节等价证据。
6. 文档、测试、证据是否同时更新？只改代码不改边界文档，视为未完成。

## 6. 证据边界

- V3 历史真机锚：3.2.186；V4 当前真机锚：4.1.93。
- V4 在线只读验收：`outputs/review/v4-online-acceptance.md`（阶段 A/B、O1/O2/O3）。
- V4 绘制基线/写探针/完整链：`outputs/review/v4-draw-baseline.md`、
  `outputs/review/v4-draw-write-probe.md`、`outputs/review/v4-draw-apply.md`。
- V4 单 PCB 审查与 #89：`tasks/038-eprj3-tierA.md`、`docs/handoff.md` §3.0。
- 以上证据只证明**写明的范围**；未写明的 V4 能力一律按“未验证”处理。
