# 038G2：Short-Symbol 显式网名别名闭包

> 2026-11-15，审查线 / shared parser 独立小批。真实样本在公开材料中只称 PCB-A；
> 本机路径、完整网表和逐脚差分只放 `.tmp_038g2/`，不入库。

## 1. 前因与实测基线

岳提供的漏洞包证明旧 `netext/netbuild/floating` 有大量假悬空，但其 §4 对 boardwise
只做了静态检查。038R 只读复核用当前 `b78c214` 的生产 loader +
`build_project_model()` 跑了一份 V4 `.eprj3` 两页工程：旧报 69 个误判中 62 个在
boardwise 有多成员网，1 个受重复位号 first-wins/unproven 影响，剩余 6 个驱动器
SHx 脚仍为单成员网。

这不是旧工具 V1 的原样复现。boardwise 已有 Short-Symbol 几何短接，但 038g 的命名
只给短接簇保留一个主名：有器件脚一侧的 `MOT*` 获胜后，另一侧的 `SH*` 显式 NET
被丢弃。驱动器存根与短接件并未直接共点，它依赖相同的 `SH*` 名字连接；主名被改成
`MOT*` 后，原有 `nets.setdefault(name, …)` 再也合并不了这两座岛。

真实基线：1 board / 2 pages / 142 components / 508 pins / 112 nets；六个 SHx 网各
1 个成员，三个相线网各 13 个成员。65 个现存 NC 全部为 `Pin.net is None`；重复位号
`U15/U16` 的 unproven 不得借此批消失。主代理独立重跑锚点与短接探针，读数一致；
现有 038g + 040 + 180 聚焦为 43 passed。

## 2. 公开合同（先冻结，后实现）

1. 对**实际连接了不同几何簇**的 Short-Symbol，短接簇所有侧的显式 `NET` 名都是
   后续同名并网的等价证据，即使该名字没被选作显示主名。别名按原字符串精确匹配，
   不 casefold，不把器件脚名当网名。
2. 先沿用 038g 的规则确定短接簇主名（forced 旗标 > 有器件脚侧标签 > 字母序），
   再把与该短接簇显式标签等价的独立簇归到这个主名。只改变必要的 `labels[name]` /
   `Pin.net` / `Net.pins` 归属；不新增公开 aliases 字段，不在 `model.nets` 同时保留
   主名和别名两份网。
3. 等价关系必须传递闭合。若一个别名闭包含多个短接主名，forced 主名优先；否则按
   确定性的主名字符串顺序选，不允许记录流 first-wins。该项只是防止别名合并制造
   新不确定性，不扩大为通用“所有多标签簇”重构。
4. 只对 038g 已接受的 `short_sides` 生效。冗余短接、悬空一脚的短接、普通多标签簇、
   没有 Short-Symbol 的模型保持原行为。不得全局 union 所有同名标签的几何节点；
   页内几何 UF、跨页按名成员合并和 board 隔离仍是三套既有边界。
5. 不改变 NC、重复位号 first-wins/unproven、CBB block-port unproven、自动 `NETn`
   防碰撞、镜像顺序、组件/旗标/导线几何、CLI/JSON/schema 或任何绘制决策。

建议实现位置仅现有 `_fill_board_model()` 的 038g/命名段：保留每簇显式标签和实际
短接根，主名初次确定后构建“短接显式标签 ↔ 主名”的等价闭包，再统一重定向相关
`labels[root]`。不要新增第二套网表构建器，不改公开模型来绕开局部缺口。

## 3. 回归与 negative control

先在未改生产代码时新增测试并保存真实 RED，再实施：

- **核心判别夹具**：一个短接左侧为无器件的 `SENSE` 标签存根，右侧为带 R1 的
  `PHASE` 网；另一独立存根带 R2 且同名 `SENSE`。旧实现 R1→PHASE、R2→SENSE；
  修复后两者及各自全部脚同属 PHASE，`SENSE` 不作为另一张网残留。
- **无短接对照**：去掉短接、保留相同标签布局，R1/R2 的网及成员逐字不变。
- **大小写对照**：`SENSE` 与 `sense` 不得合并。
- **传递/多主名对照**：别名链必须收敛；两个短接主名共处一闭包时结果确定，forced
  优先。不得用输入记录顺序决定答案。
- **既有行为不变**：038g 的短接命名、冗余短接、 dangling pin、普通两标签字母序、
  跨页坐标隔离；040/040b/041 的页/board 边界；180 的旗标；189A2 的镜像/网表；
  038Q18 的块端口 unproven。
- 变异必须命中因果：禁用别名闭包或最终重定向时核心测试 RED；恢复后 GREEN。
  仅断言“短接两侧原来已同网”的测试不算覆盖本缺口。

## 4. 两个消费者与真实样本差分

- 网表/规则消费者：`build_project_model()` → `DesignModel.nets` / `Pin.net`；
  跑 038g、040、040b、041、189A2。
- 几何与后续审查消费者：placed geometry 不变，block-port 仍按相同 labels/unproven
  通道工作；跑 527C2 pin geometry、038Q18 及适用 owner/layer 守卫。
- 实施前把 PCB-A 的全量语义基线写 `.tmp_038g2/model-baseline.json`（本地、脱敏公开
  报告另写）；实施后同脚本重算并 diff。预期只有六个 SHx `Pin.net` 改到对应相线/采样主名：
  **三个相线网与三个采样网各增加一个成员**（六脚 = 3 + 3，不是六脚都进相线网——本行初稿
  把这两类写成"六脚进三个相线网、各 +1"，3 ≠ 6，已按实测改正），六个旧单成员网消失；
  其他 pin/net 成员、65 个 NC、duplicate/unproven、stats 和 placed geometry 必须不变。
  若不吻合，停止而不是调宽断言。

## 5. 兼容矩阵

| 维度 | 本批证据 | 不得外推 |
| --- | --- | --- |
| V3 | 038g 合成 `.epro2`、189A2 既有校准回归 | 不做新 V3 真机声称 |
| V4 | PCB-A `.eprj3` 只读全模型差分 | 不等于整板所有规则审查通过 |
| 在线 / 离线 | 仅离线 parser；在线路径未改 | 不称在线宿主已复验 |
| 单 / 多板 | 真实单板 + 040b/041 row/multi-board 回归 | 不把同名别名跨 board 合并 |
| 普通器件 / CBB | 普通短接样本 + 038Q18 负控 | 不扩 CBB 内部展开或非端点端口 |
| 镜像 / NC / 重复位号 | 189A2、真实基线逐脚差分 | 不采信桌面旧工具 mirror-first 的 R23 脚号裁定 |

## 6. 文件域、纪律与交卷

允许：`src/boardwise/parsers/schematic.py`、`tests/test_038g_short_symbol.py`、本任务书
的交卷段；本地 `.tmp_038g2/` 与 `.tmp_pt_038g2/`。不改其他文件，尤其不碰绘制线、
既有混合工作树、fixtures、TASKMAP/shared-platform 的他人未提交 hunk。

真实工程与桌面证据只读；真实容器和派生副本不入库。零 git 写、零删除、零
checkout/restore、零 daemon/EDA/联网、零全量 pytest（由主代理批次验收另跑）。
实施前 `cp` 备份两个允许修改的源码/测试文件并记 SHA-256；变异只能 cp+hash 恢复。

一个 coder，最多 40 步或 30 分钟。交卷不超过 1800 字，必须含：先红后绿原文、聚焦
命令与计数、真实样本语义 diff 汇总、两处变异及 SHA 恢复、兼容矩阵逐项证据、未覆盖项。
详细日志留 `.tmp_038g2/`，主代理随后独立审查 diff、跑变异和真实差分，不接受转述签绿。

## 7. 交卷（038G2 执行，2026-11-15）

**状态：核心缺口已按 §2 闭环并在 PCB-A 全模型差分上全中；但 §3「既有行为不变」与另一块
V3 fixture 板的既有校准断言冲突，交回裁决（详见 7.7）。本批不写「验收通过」。**

### 7.1 基线与备份

| 文件 | 开工 SHA-256 | 交卷 SHA-256 |
| --- | --- | --- |
| `src/boardwise/parsers/schematic.py` | `c8856ae771d385b6183f1b8c009aa938f4f773752842b21e7767d1b5f0e203ba` | `d64463100b99c34bbb819334f1beab6be8dbf5cd7bd1e0b0c379cad4a87c2a8d` |
| `tests/test_038g_short_symbol.py` | `63c4ef6d55b7d453f9995cf224332ce9dac0bc76ea46a3b56c95913765801562` | `77f8c9b00a03525fe5079cf1e0fbb9f2a7580bf51aab681f6f60dc0e866a5cc8` |

备份与新实现副本：`.tmp_038g2/schematic.py.pre`、`.tmp_038g2/test_038g_short_symbol.py.pre`、
`.tmp_038g2/schematic.py.new`。干净开工（两文件开工前无未提交改动）。零 git 写、零删除、
零 checkout/restore、未跑全量 pytest、未开 daemon/EDA/网络。

PCB-A 全量语义基线 `.tmp_038g2/model-pre.json`：1 board / 2 pages / 142 components /
508 pins / 112 nets / 65 NC / 443 成员 / 22 单成员网，含每脚 `(number, name, net)`、
每网成员表、duplicate/unproven、`pin_wires`（placed geometry）与全量 ParseStats。

### 7.2 先红后绿（原文）

未改生产代码时（`c8856ae7`）新增夹具：

```
FAILED tests/test_038g_short_symbol.py::test_an_alias_label_still_joins_what_the_main_name_hid
FAILED tests/test_038g_short_symbol.py::test_an_alias_chain_converges_on_one_deterministic_name
FAILED tests/test_038g_short_symbol.py::test_a_forced_main_name_wins_over_the_string_order
3 failed, 17 passed in 0.52s
```

报错原文（forced 用例）：`AssertionError: R2 must follow the flag name; got 'MMM'`，
`assert 'MMM' == 'PGND'`；核心用例 `R2.1='SENSE'`（旧实现只连 R1 到 `PHASE`）。

修复后 `20 passed in 0.36s`。三条对照在旧代码即 GREEN、修复后仍 GREEN（防空转）：
无短接同布局（`R1=PHASE`、`R2=SENSE` 逐字不变）、`SENSE`/`sense` 不合并、冗余短接不拉同名声岛。
新增夹具共 6 条：核心别名并网、「无短接」对照、大小写精确、传递链收敛（两主名同闭包取字符串序）、
forced 优先、冗余短接负控。

### 7.3 实现摘要（`_fill_board_model()`，+60 行，无新字段、无第二套网表）

1. 命名段收集 `short_alias_labels[root] = set(group_labels)`：只对 038g 已接受、真正跨两簇的
   `short_sides` 建键（`short_pin_labels` 的既有门），内容是**短接簇两侧全部显式 NET 标签**。
2. `labels = explicit` 之后（auto `NETn` 之后，故自动名序列不变）建标签等价闭包：
   `main ↔ 每一条簇内显式标签`；闭包里出现多个短接主名时，`forced` 主名优先，否则
   `sorted(mains)[0]` 定序，与记录流顺序无关。
3. 只重定向 `labels[root]`；`Pin.net` / `Net.pins` 仍只填一次，别名不留网。
   未命中的簇不动；页内 UF、跨页按名合并、board 隔离三套边界未动；未新增公开字段、
   未全局 union 同名标签、未改镜像/NC/重复位号/CBB/自动命名。

### 7.4 聚焦读数

`pytest --basetemp=.tmp_pt_038g2`（日志 `.tmp_038g2/focus.log`）：

| 命令 | 结果 |
| --- | --- |
| 038g+040+040b+041+180+189A2+527C2 pin geometry+038Q18+owner+layer 十条 | **7 failed, 167 passed in 36.57s** |
| 同上但去掉 040/040b/041 | **102 passed in 21.77s** |
| 旧代码同一组（040/040b/041） | **72 passed in 15.98s** |

7 个红全部落在 040 / 040b / 041，且全部由本批改动引起（旧代码同组 72 passed）：
`test_040_page_scope::test_the_header_brackets_no_longer_short_u2s_columns`、
`::test_pages_are_not_welded`、`test_040b_boards::test_the_project_totals_count_parts_not_names`、
`test_041_cross_board_nets` 的 4 条。见 7.7。

### 7.5 PCB-A 前后全模型差分（`.tmp_038g2/model-diff.txt`）

| 项 | 前 → 后 |
| --- | --- |
| nets | 112 → 106（仅少 6 张单成员网，无新增网） |
| 单成员网 | 22 → 16，消失的正是六个 `SH*`/`SL*` 存根网 |
| `Pin.net` 变化 | **6 处，全在驱动器的 6/8/9/11/14/16 脚** |
| 成员变化 | 三个相线网 13→14、三个采样网 6→7（各 +1，合计 +6；成员总数 443 不变） |
| NC / duplicate / unproven / stats / `pin_wires` / 其余 141 个器件 / 每网成员 | **逐字段不变** |

与 §4 字面预期的差异：只写在 `.tmp_038g2/`（本段不复述具体网名）。六个脚并非都落到三个相线网——
实测是三个相线网各 +1、三个采样网各 +1，六个单成员存根网全部消失、总数与成员守恒。
按 §4「不吻合就停」的口径这属预期外，但 §4 自身的「六脚→三个相线网各 +1」自相矛盾（3≠6），
故按「六脚迁移 + 六网消失 + 其余零变化」这一可判定的不变量报出，请主代理裁定这是否算吻合。

### 7.6 两处因果变异（cp + SHA-256 恢复）

| 变异 | 改法 | 结果 | 恢复 |
| --- | --- | --- | --- |
| M1 关掉最终重定向 | `labels[root] = redirect.get(name, name)` → `= name` | 3 failed, 17 passed（三条核心红） | `cp schematic.py.new` → `d6446310…` |
| M2 去掉 forced 优先 | `main = (flagged or sorted(mains))[0]` → `sorted(mains)[0]` | 1 failed, 19 passed（只有 forced 用例红，说明该用例非空转） | 同上，`d6446310…` |

恢复后 `sha256sum` = `d6446310…`（与变异前逐字节一致），复跑 102 passed。

### 7.7 裁决：主代理已按 PAD_NET 裁定保留本实现（2026-11-15）

同一实现跑 040/040b/041 用的三板 V3 fixture：该板有同一缺口的 **9 个脚**（驱动器 + 排针上
六个 `SH*`/`SL*` 与三个采样负端 `I?-`），旧读法让它们各自独占一张单成员网。
别名闭包按合同把它们并入对应相线/采样网，三个采样负端按 038g 既有「forced 旗标优先」并入地网；
板内网数 34→25，工程网数 146→137 / 156→147。三相线/采样网各 +1 成员，无跨页、无跨 board、
无新增网、无成员丢失；其余两块板逐字段不变。

三个测试文件原先写死了旧读数（精确成员表、每板网数、`net_instances == net_count`），故 7 红。
**主代理另派只读跨视图核验**（`host_adjudication.py`，走 boardwise 自己的 PCB 解析 +
`build_design_model(source, document=…)` 读活 PAD_NET，非手写 first-wins），结论：

- 真实样本 **15/15** 改动脚与 PCB PAD_NET 一致（6 个主体脚 + 9 个 FOC 脚分别核过；
  排针 U2.4 与 U2.6 在 PCB3 同为 `IC+`，U2.2 = `PGND`，U2.10 = `MOTC`，PCB3 的 14 个网里
  根本没有 `IC-`/`SLC`/`SHC`）；
- 主代理独立重跑，输出逐字节相同；
- 主代理把生产暂时换回 `schematic.py.pre` 实测「新增测试 + 040/040b/041」= **3 failed, 89 passed**，
  随后 `cp` 恢复当前实现，`SHA-256 = d6446310…7c2a8d`（与本批交卷一致）。

所以旧 header 论断「PCB3 confirms six *different* nets」确实是错的，7 红是旧期望被 PCB 证伪，
不是实现越界。裁定：保留实现，改期望值 → 见 §8。

### 7.8 未覆盖项

- 只在 parser 离线路径验证；在线宿主、bridge、checkup/review 报告未复验（本轮无授权）。
- `--interconnect` 报告与 `unproven` 文案未因本批改变，但未针对新合并网逐条目检。
- 现实现只重定向「最终标签落在闭包里」的簇；一个普通多标签簇若其**非**选中标签落在闭包里，
  该别名不参与合并（有意保守，对应 §2.4「普通多标签簇保持原行为」），未做专门夹具。
- 真实样本只有一块板、一个 V4 工程；多板同名别名的负控由 040b/041 既有回归承担
  （§8 已按 PCB 裁决更新期望值，现全绿）。
- 未跑全量 pytest，未跑 connector / dsh-plugin / tsc 三线。

### 7.9 证据路径

`.tmp_038g2/`：`model-pre.json`、`model-post.json`、`model-diff.txt`、`model_baseline.py`、
`diff_model.py`、`probe_short_sides.py` + `short-sides.json`（七个短接两侧标签实测）、
`probe_foc.py` + `foc-pre.json`/`foc-post.json`、`red-038g.log`、`green-038g.log`、
`focus.log`、`focus-restored.log`、`mutation-m1.log`、`mutation-m2.log`、`pre-sha256.txt`、
`schematic.py.pre`/`.new`、`test_038g_short_symbol.py.pre`。

---

## 8. 续批交卷（038G2 续，2026-11-15）：MOTOR 差分 + 旧期望更新

**状态：全绿。** 生产算法未再改动（`schematic.py` SHA 仍是 `d6446310…7c2a8d`）；
本续批只改三个测试文件的过期读数、任务书 §4/§7.7 与本节。

### 8.1 MOTOR 差分与 PCB 逐脚裁决（`probe_measure.py` + `probe_motor_adjudication.py`）

MOTOR 有 2 块 PCB（PCB1 114 件/84 网、PCB2 49 件/39 网）。用设计号重叠把原理图板对到 PCB：
`控制板`↔PCB1（重叠 114/114），`驱动板`↔PCB2（49/49）——匹配分数逐条打印可复核。

| 板 | nets | 改动的脚 | 其余 |
| --- | --- | --- | --- |
| `控制板` | 104 → 104 | **0** | 逐字段不变 |
| `驱动板` | 52 → 43 | **9** | duplicate / cross_page / unproven 全同 |

九个脚全部与 PCB2 活 PAD_NET 逐一相同（`AGREE=True`）：`U18.6→MOTC`、`U18.8→IC+`、
`U18.9→IA+`、`U18.11→MOTA`、`U18.14→MOTB`、`U18.16→IB+`、`U2.7→PGND`、`U4.7→PGND`、
`U4.8→PGND`。其余证据：

- 消失的九个旧名 `IA-/IB-/IC-/SHA/SHB/SHC/SLA/SLB/SLC` **都不是 PCB2 的网**
  （`is_a_pcb_net=False`，PCB 成员表为空）；
- 每个改动脚的落点网，其全部成员的 PAD_NET 是**同一个**（IA+/IB+/IC+/MOTA/MOTB/MOTC 各 7/7/7/15/15/15，
  PGND 23/23，`all_on_one_pcb_net=True`）；
- 全板锚点：schematic 落点网（≥2 脚在 PCB 上）**39 个全一致、0 split**。

结论：MOTOR 与 PCB-A、FOC 是**同一缺口**，PCB 支持新读数，故改期望；生产无需对齐动作。

### 8.2 完整派生账（改断言前一次算完）

| 量 | FOC | MOTOR |
| --- | --- | --- |
| 每板 nets | [99,13,34] → **[99,13,25]** | [104,52] → **[104,43]** |
| `net_count` = `net_instances` | 146 → **137** | 156 → **147** |
| 跨板 groups | 39（34 对 + 5 三元）→ **30（25 对 + 5 三元）** | 38 → **35** |
| `unproven_edges` | 49 → **40**（25 + 5×3） | 38 → **35** |
| 离开的组合名 | 九个（`IA-/IB-/IC-/SHA/SHB/SHC/SLA/SLB/SLC`） | `IA-/IB-/IC-` |
| checkup findings / summary | 239 / (50,20,169) **不变** | 229 / (22,14,193) **不变** |
| `crossBoardNets.count` | 39 → **30** | 38 → **35** |
| `warning_triage` 有归属行 | 6 **不变** | 4 **不变** |
| `unproven_nets` / 非可寻址页 | 空 / 空 **不变** | 空 / 空 **不变** |

组/边下降是**派生**而非新语义：九个名只在一块板上还有实体后就不再是"同名跨板"，
`unproven_nets` 与"同名未证明"口径一字未改（前后逐字段相同）。

### 8.3 改了哪些断言、为什么

| 文件 | 改动 |
| --- | --- |
| `tests/test_040_page_scope.py` | header 逐脚期望改为 PCB3 读数 `{2,1,3,5:PGND, 4:IC+, 6:IC+, 10:MOTC, 8:GLC, 12:GHC, 7,9,11:+24V}`；删掉"六个不同网"叙述与已不成立的 triple≤1 断言，换成能区分 PCB 各独立网的断言：`GLC`/`GHC` 各自两成员网、`MOTC` 的排针成员恰为 `{10}`、`IC+` 的排针成员恰为 `{4,6}`、七个旧标签不在 Board3 网表里。页/板隔离断言（无跨页网、每板网数、`+24V`/`PGND` 不共网、最大网 <100）原样保留 |
| 同上 | `test_pages_are_not_welded`：`[99,13,34]`→`[99,13,25]`、`[104,52]`→`[104,43]`，注释补 038g2 的重测原因 |
| `tests/test_040b_boards.py` | `net_count()` 146→137 + 注释（155 件/121 名不动） |
| `tests/test_041_cross_board_nets.py` | 三元组 146/39/49→137/30/40、156/38/38→147/35/35；checkup 段 `section["count"]` 39→30、markdown `"39 个网名"`→`"30 个网名"`；`len(shared)` 39→30，均带 038g2 注释。findings 数、summary、verdict、attributed=6、R18 归属、无"已证明"用词等断言未动 |

### 8.4 聚焦读数（`PYTHONIOENCODING=utf-8`，各批独立 basetemp）

| 命令 | 结果 |
| --- | --- |
| `tests/test_040_page_scope.py tests/test_040b_boards.py tests/test_041_cross_board_nets.py -q --basetemp=.tmp_pt_038g2b` | **72 passed in 19.18s** |
| 原十条 + `test_013_symbol_fallback.py` + `test_049_parser_defects.py` `--basetemp=.tmp_pt_038g2c` | **194 passed in 44.08s** |
| 同一条命令，在**行尾归一之后**的交付字节上复跑 `--basetemp=.tmp_pt_038g2d`（`.tmp_038g2/focus-final.log`） | **194 passed in 44.12s** |

**残留红：0。** 本轮未跑全量（见 §9.1：首轮全量已于第三轮跑完，第二轮主代理在途）。

### 8.5 行尾与 SHA 检查

- `tests/test_038g_short_symbol.py` 原文件 CRLF；上批追加段曾留 175 行裸 LF，已就地归一为
  全 CRLF（620 CRLF / 0 裸 LF），`git diff --stat` 仍是 `+175 / -0`，无内容改动、无无关格式化。
- 三个被更新的测试文件本来就是全 CRLF，编辑后仍 0 裸 LF；`schematic.py` 亦全 CRLF。
- `src/boardwise/parsers/schematic.py` = `d64463100b99c34bbb819334f1beab6be8dbf5cd7bd1e0b0c379cad4a87c2a8d`（本续批未改）。
- `tests/test_038g_short_symbol.py` = `ae8019396b25a4b9482355749e5d9e37777f1ca77a5193985b688a1773dc7b8a`
  （行尾归一后；上批交卷值 `77f8c9b0…` 是归一前的 LF 混合态）。
- pre 对照读数：`schematic.py` 换回 `.pre`（`c8856ae7…`）时「新增测试 + 040/040b/041」
  = 3 failed / 89 passed，恢复后 SHA 一致（主代理已独立复跑；本续批两次换回/恢复用
  `cp .tmp_038g2/schematic.py.final` + `trap` 兜底，收尾 `sha256sum` 复核）。

### 8.6 未覆盖项（更新）

- 仍只在 parser 离线路径；在线宿主 / bridge 未复验（本轮无授权）。
- MOTOR 的检查点：`findings`/`summary` 前后相同，但未对 229 条 finding 逐条 diff；
  只断言了数量与 summary 三元组（测试原口径）。
- MOTOR 的 `控制板`（104 网）零变化是**实测**，但未逐网与 PCB1 做全量锚点比对（只对改动板的
  落点网做 39/39 锚点核验）。
- `--interconnect` 声明式证据、CBB 展开、多板同名别名的"跨 board 不合并"仍由 040b/041 既有
  断言承担，未新增专门夹具。
- 未跑全量 pytest 与 connector / dsh-plugin / tsc 三线（§9.1 起：首轮全量已完成，第二轮主代理在途）。

### 8.7 证据路径（本续批新增）

`.tmp_038g2/`：`probe_measure.py`、`measure-pre.json`、`measure-post.json`、`measure-post.out.txt`、
`probe_motor_adjudication.py`、`motor-adjudication.out.txt`、`checkup-pre-foc/`、`checkup-post-foc/`、
`checkup-pre-motor/`、`checkup-post-motor/`（CLI 报告原件，含 `report.json` / `report.md`）、
`focus3-continued.log`、`focus-continued.log`、`schematic.py.final`。
主机侧裁决原件（主代理产出，只读引用）：`host_adjudication.py`、`host_adjudication.out.txt`。

---

## 9. 第三轮交卷（038G2 下游收尾，2026-11-15）

**状态：6 条本批下游红全部按证据重钉，聚焦零红。** 生产 `schematic.py` 未再改动
（SHA `d6446310…7c2a8d`，逐轮复核）。本续批只动三个测试文件 + 本节。

### 9.1 首轮全量真实读数与分类（`.tmp_038g2/full-pytest.log`）

`9 failed, 11226 passed, 26 skipped, 3 xfailed`。九红分两类：

| 类 | 条目 | 处理 |
| --- | --- | --- |
| **既有绘制线红（3 条，禁触）** | `test_548d_panel_base::test_the_topology_search_spends_a_bounded_number_of_routes`、`test_548k_stub_floor::test_a_page_that_states_no_stubMin_keeps_its_geometry_bytes`、`test_548p_service_rows::test_a_service_row_leaves_the_host_a_real_ground_flag` | 本批一字未碰（`tests/test_548*`、`engines/**` 不在文件域） |
| **本批别名语义的下游旧期望（6 条）** | `test_041s2_interconnect` 三条（`count 39/38`、`other 38`、`39 groups` 等派生文字）、`test_105_b4b_designator_membership` 一条（Board3 digest）、`test_527c2_cross_view_geometry` 两条（V100 六别名 `status`/`differentNet`/note） | 逐类取证后改期望（9.2–9.4） |

### 9.2 105：19 块一次全算（`.tmp_038g2/probe_105_digests.py`）

用**测试自己的** `_loaded_boards()` / `_membership_digest()`（同一 `json.dumps(sort_keys=True)`
序列化）跑完全部 **26 块**，其中钉住的 19 块：**17 块不动、2 块动**，其余 7 块是「有重复位号」
的 REPEATED 板（本就不在钉表里）。

| 板（文件键省略中间路径） | 旧 digest | 新 digest | 依据 |
| --- | --- | --- | --- |
| 三板 V3 fixture `[Board3]` | `6916d714…f1547` | `0d755edb…2ad96` | 9 脚，PCB3 PAD_NET 9/9（八个 MOT/采样 + 三个 `PGND`，第七节已列） |
| 两板 V3 fixture `[驱动板]` | `5ce9cfdc…43db` | `58755ba3…4a5ad` | 9 脚，PCB2 PAD_NET 9/9（`motor-adjudication.out.txt`） |

**没有第三块差异板**，两块都在 24 脚已证范围内；digest 仍只覆盖「网键 + 成员集合」，19 块覆盖数、
member-only 语义、`REPEATED_NET_KEYS` 表全部未改。测试名由
`…did_not_move_one_byte` 改为 `…match_their_pinned_reading`，docstring 写明这是 105 自己的零变化钉、
038g2 是**带 PCB 证据的显式重钉**，不是放宽。

### 9.3 V100：6/6 逐脚 PCB 证据（`.tmp_038g2/v100-u10-adjudication.out.txt`）

fixture 两块 PCB：**PCB1**（uuid `ab812fb7…`，122 件 / 87 网）、PCB2（10 件 / 8 网，无 U10）。
用 `build_design_model(source, document=…)` 读活 PAD_NET，与**当前**原理图 `Board1` 逐脚比：

| 脚 | 原理图（当前） | PCB1 PAD_NET | 该网其余成员 |
| --- | --- | --- | --- |
| U10.6 | `MOTA` | `MOTA` | Q7.1/2/3、Q8.5–9、U12.1 |
| U10.8 | `IA+` | `IA+` | Q8.1/2/3、R16.1、R43.2 |
| U10.9 | `IB+` | `IB+` | Q2.1/2/3、R3.1、R8.2 |
| U10.11 | `MOTB` | `MOTB` | Q1.1/2/3、Q2.5–9、U12.2 |
| U10.14 | `MOTC` | `MOTC` | Q3.1/2/3、Q4.5–9、U12.3 |
| U10.16 | `IC+` | `IC+` | Q4.1/2/3、R15.1、R18.2 |

**6/6 一致**，board identity 用 PCB 文档自身的 META title 与设计号集合（U10 只在 PCB1 上）。

改写后的两条 527C2 断言（名字同步改为当前事实）：
PCB1 走「空 lonely」通道 —— `checked=True`、`lonely == []`、**无 `status` 键**、**无 `geometry` 键**
（与合成的 `test_an_empty_lonely_list_never_grows_a_geometry` 同一形状），并新增「六个旧标签不得
以任何形式残留在 `autoNetAliases` 里」；PCB2 仍是 `status=suspected`、1 条 `CN2.5` 同名落线、
geometry counts 全 0；reader 仍逐字深拷贝不变；finalize 的 `_suspected_boards` 由 `[0, 1]` 改 **`[1]`**。
note 仍是 1 条，含 `PCB2：1 个引脚（CN2.5）` 与 `落在线上且两视图网名相同 1 个`，
不含 `落线但两视图网名不同`、不含 `U10.`/六个别名/`PCB1`，仍保留「两侧都不是天然权威」与
「不宣称陈旧」的口径。合成 `differentNet` 用例（§1–3 的 5 条）**全部保留未动**。

### 9.4 041S2：一次改全派生数字（`.tmp_038g2/full-pytest.log:163–215,331–395,737–775`）

FOC `count 39→30`、`34 pairs + 5 triples → 25 pairs + 5 triples`；MOTOR
`156 instances / 38 shared names / 38 unproven edges → 147 / 35 / 35`、`plain count 38→35`、
两处 `section["count"] == 38 → 35`；`other 38 same-named groups → 29`；
`provenCount == 1` 的三处断言与「30 groups 不会各自变成 proven」的文字同步。
**行为断言全部保留**：checkup exit 1 / 239 findings / 50-20-169 / `incomplete`、review exit 1 /
45 findings / 30-1-14、`review --json` 两次逐字节相同、`provenCount=1`、只升级被声明的端点、
未声明组仍 `E0` + `welded-by-name` + `merged=false`、声明是**并列追加**而非覆盖或删除、
两份 markdown 的 section 逐字相同。声明机制本身一个字都没删。

### 9.5 聚焦读数（`PYTHONIOENCODING=utf-8`，各轮独立 basetemp）

| 命令 | 结果 |
| --- | --- |
| `test_041s2_interconnect + test_105_b4b_designator_membership + test_527c2_cross_view_geometry + test_527c2_pin_geometry`，`--basetemp=.tmp_pt_038g2e`（`focus-round3-a.log`） | **198 passed in 65.39s** |
| 此前 12 文件集 ∪ 上面四个（15 文件），`--basetemp=.tmp_pt_038g2f`（`focus-round3-full.log`） | **382 passed in 110.34s** |

**残留红：0。** 本轮未跑全量：**首轮全量已完成（9 red 如上），第二轮由主代理在途**；
第二轮结果未出前，本批不宣称全量绿。

### 9.6 行尾与 SHA

| 文件 | 开工 SHA（本轮） | 交卷 SHA |
| --- | --- | --- |
| `src/boardwise/parsers/schematic.py` | `d6446310…7c2a8d` | `d6446310…7c2a8d`（**未改**） |
| `tests/test_041s2_interconnect.py` | `2450d60a…b47ba` | `3f3392d2…3fb9d3` |
| `tests/test_105_b4b_designator_membership.py` | `11de8a29…e2a24` | `0a4717c2…fc9a45` |
| `tests/test_527c2_cross_view_geometry.py` | `3ce4570f…e3c58` | `55071b75…f79ca4` |

行尾：041s2 / 105 原本全 CRLF，改动后 `CRLF 1455 / 0 裸 LF`、`CRLF 567 / 0 裸 LF`，无 `\r\r`；
527c2_cross_view 原本就是纯 LF（`0 CRLF / 581 LF`），沿用原风格，未混入 CRLF。
备份：`.tmp_038g2/test_041s2_interconnect.py.pre`、`test_105_b4b_designator_membership.py.pre`、
`test_527c2_cross_view_geometry.py.pre`（与开工 SHA 逐字节一致）。零 git、零删除、零 checkout、零全量。

### 9.7 未覆盖项

- 第二轮全量未跑（主代理在途）；本轮只跑点名聚焦与 15 文件并集。
- 三条绘制线红未复验、未定位（不属本批，禁触）。
- V100 的 note 只验证了「含 CN2.5 / 不含六别名」，未对 note 其余 24 条 `autoNetAliases` 逐条读。
- 105 的两块重钉依赖已存档的 PCB PAD_NET 读数（本处只复核范围 9+9=18 脚，未重跑 24 脚全集）。

---

## 10. 主代理最终验收（2026-11-15）

**最终状态：审查线离线闭环，工作树未提交。全仓不是全绿：第二轮全量只剩既有绘制线三红。**
本节是最终读数，取代 §8/§9 中“第二轮在途/未跑”的 interim 表述。

### 10.1 主代理独立复验

- 扩大聚焦 15 文件：`389 passed in 136.74s`（`.tmp_038g2/parent-round3.log`）。
- M1 禁用最终别名重定向：`3 failed / 17 passed`；M2 去掉 forced 优先：
  `1 failed / 19 passed`。两次都先红，再 `cp` 恢复并核对 SHA-256；
  生产 `schematic.py` 最终仍为 `d64463100b99c34bbb819334f1beab6be8dbf5cd7bd1e0b0c379cad4a87c2a8d`。
- 恢复态 038g：`20 passed`；V100 格式/语法复核：`15 passed`。
  `git diff --check` 通过（527c2_cross_view 保留原 LF 风格）。
- PCB-A 当前模型与已验 post 逐字节一致；FOC/MOTOR 当前派生模型与已验 post
  逐字节一致。PCB `PAD_NET` 跨视图裁决覆盖 PCB-A 6 脚、FOC 9 脚、MOTOR 9 脚，
  另有 V100 6 脚，全部一致；不是只看网名，亦核对了同网成员。

### 10.2 第二轮全量 Python

命令：

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m pytest tests/ -q -n 4 \
  --dist loadfile --basetemp=.tmp_pt_038g2_full2
```

真实汇总（`.tmp_038g2/full-pytest-2.log`）：

```text
3 failed, 11232 passed, 26 skipped, 3 xfailed, 1 warning in 2073.34s (0:34:33)
```

三红逐字为：

- `tests/test_548d_panel_base.py::test_the_topology_search_spends_a_bounded_number_of_routes`
- `tests/test_548k_stub_floor.py::test_a_page_that_states_no_stubMin_keeps_its_geometry_bytes`
- `tests/test_548p_service_rows.py::test_a_service_row_leaves_the_host_a_real_ground_flag`

与首轮既有绘制线三红完全相同；首轮的 041S2×3、105×1、527C2×2 已全部清零，
本批没有新增全量红项。未跑第三轮，未修改或豁免绘制线测试。

### 10.3 其余三线

| 线 | 真实读数 |
| --- | --- |
| Connector | `774 passed / 0 failed`；`npm run typecheck` 通过 |
| DSH | `137 passed / 1 skipped`；typecheck 与 build 通过；测试沿用回收站适配，无直删 |
| Rust | `177 passed / 4 ignored`；`cargo fmt --check`、`cargo clippy -- -D warnings`、`cargo test` 全过 |

日志：`.tmp_038g2/connector-{test,typecheck}.log`、`dsh-{test,typecheck,build}.log`、
`rust-{fmt,clippy,test}.log`。

### 10.4 最终边界

- 本批证明的是离线 schematic parser 的 Short-Symbol 显式标签别名语义，以及归档 PCB
  `PAD_NET` 交叉一致性；未做在线宿主 `sch.netlist`、bridge 或 EDA 写操作。
- 桌面旧工具的 R23 mirror-first 脚号与项目 189A2 的 mirror-last 校准冲突；该样本 PCB
  无 R23，故脚号仍未裁，不能用本批结果覆盖现有镜像规则。
- 普通多标签簇的非主标签、通用无位号器件、CBB 内部展开不在本批范围。
- 未提交、未推送、未发布；真实工程与桌面证据保持只读，真实容器未入库。

---

## 11. test V4 在线宿主验收（2026-11-15）

**结论：核心别名闭包与宿主网表一致，允许单独提交；不是整板或全宿主兼容声明。**

- 环境：daemon 仅放行 `test V4`，保留原配对；另一真实工程窗口未做任何读写。P45 开工只有
  sheet 外框、无电路图元。三颗器件为官方 `Short-Symbol` 与两颗可检索 R0603 电阻。
- 核心反例：短接左侧无器件 `SENSE` 存根，右侧 R901 的 `PHASE`，独立 R902 仍为 `SENSE`。
  首张 netlabel 超时且回读确认未落件，没有盲目重试；改用导线自带 NET 属性完成相同布局。
- 宿主 `sch.netlist`：**R901.1 = R902.1 = `PHASE`**；保存后新导出的离线模型同样为
  **R901.1 = R902.1 = `PHASE`**，且没有 `SENSE` 网残留。两只 2 脚在宿主为空网、离线为自动
  `NET1/NET2`，属于既有自动命名差异，不参与本反例裁决。
- 最终扩大聚焦 15 文件：**396 passed（40.53s）**。其中两条旧计数钉因 038Y 每板新增一条
  近似 INFO 从 239→242，已保留 038G2 原 hunks 并补齐 50/20/172 因果后通过；不是 038G2 回归。
- 证据仅存 `.tmp_038g2/`：`p45-online-netlist.json`、`p45-after.epro2`、写入/回读记录与
  pytest 日志；真实工程容器不入库。R23 脚号、V3、多板与 CBB 内部展开仍未覆盖。
