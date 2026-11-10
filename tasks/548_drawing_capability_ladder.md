# 548：原理图自动绘制能力阶梯（分批实施，自动整页未完成）

## 0. 产品目标与边界

目标是在**声明支持的电路族**内，让 agent 只给出电路与展示语义，工具自动产出工程师首次可接受的原理图；超过能力边界时给出可复现的拒绝原因，或明确转入 `agent-adjusted`。不承诺任意电路一键成图，也不以单张图 `ok=True` 推断泛化能力。短期仍聚焦原理图，不把 PCB 自动布局布线并入本任务。

`CircuitSpec` 是电气事实与来源，`PresentationSpec` 是功能岛、核心器件、主信号流、支路次序和阅读关系；解释器负责器件、导线、旗标、文字的确定性几何。Agent 声明上述语义仍属于 `automatic`；只有直接提供几何或受控调整才记 `agent-adjusted`。`reference-replay` 单独记账，不得把参考坐标灌入自动规格。现有合同字段以 `docs/draw.md` 为准，下面提出的串联支路合同尚未实现。

质量顺序是：电气正确且来源诚实 → 功能归属与阅读顺序清楚 → 同类支路一致、文字/旗标/线不互相妨碍 → 布局紧凑。机器硬闸不能证明审美；每张候选仍需渲染后逐岛视觉自审，并对照 `docs/schematic-style-spec.md`。任何机器拒绝或视觉不合格的候选只留在 evidence，不落画布、不端给用户。

## 1. 当前基线与不重复的工作

- 543 的 CH343 P38、CH340 P39 已各过三关；P38 `saved_verified`，P39 `saved_unverified`。它们是两个已验收拓扑，不是任意电路的成功率。
- 547 是压力测试：固件约束的逻辑重绘为 30 件 / 31 网 / 5 NC / 8 岛；自动整页仍 0 候选。`observed` / `assumed` / `optional` 的边界不得因画法需要而抹掉。
- 547S 已完成 signal → 非 GND → GND 的共享网座位/关系/修复/lane 统一；不再重立这一批。自动线后续缺口是 547D 的 N≥3 重复 shunt 联合几何（目前暴露 LED2 导线与 LCD_SDA 标签走廊冲突），以及 547E 尚未实现的 GPIO → R → LED 二件串联支路。
- 547G 的辅助整页是 `agent-adjusted`，G4 当前暂停。其 DRC 为 `0 error / 200 warn` 且 `passed=false`，持久化仅 `saved_unverified`，完整四线未跑。它可供比较视觉结果与失败形状，但不关闭 547D/E，也不替代自动整页。547G 的重开后只读复核仍按 `tasks/547_smart_medicine_box.md` §547G 单独收口。

开工先冻结 547 的完整输入、失败报告、独立电气 oracle 和渲染证据，记录当前 commit 与未提交基线。失败证书至少指出哪个网/支路、哪段线或文字盒、哪个占位冲突、用尽哪些合法候选；不能只报第一条错误后宣称整页死因已找全。保留现有 strict xfail，直到相应能力真实通过并摘标。

## 2. 分批路线与出口

每批只解一个可复用缺口；实施前另写小派单，列出文件域、输入冻结点、前红后绿、相邻回归和证据路径。下表给出能力出口与依赖，各子批实际进度以 §5–§8 为准，不绑定 0.6.1 发布。

| 批 | 能力与最小输入 | 出口；未达则停在哪里 |
|---|---|---|
| 548A：重复支路与标签走廊 | 以 547D 的四键、两灯、蜂鸣器 N≥3 同宿主支路为主例。支路座位、共享网服务空间、回流路径、宿主引脚标签和支路文字须联合选择；同类支路按相同姿态/节距处理。对 `stub=auto` 的诊断规格与原规格分别记账 | 原电气夹具不减件、不并网、不藏字、不手填坐标；四键各接自己的 KEY 网，异网脚重合、跨网短接、回流穿体、导线穿外来标签盒均为 0；`tests/test_547_repeated_shunts.py` 的 strict xfail 真正 XPASS 后摘标。若只能把冲突从左列搬到右列，保留失败证书，不进下一批 |
| 548B：显式二件串联 | 为 GPIO → R → LED → GND 这类支路增加**语义合同**，表达器件顺序、两个端点与中间网；字段名与结构先经合同评审，不把坐标当合同。默认关闭新语法 | 完整支路的三段电气关系与姿态/阅读顺序均通过独立核对；未声明该语法的旧规格行为和哈希不变。LED 直连诊断变体不得冒充完整支路；不能靠 agent 指定元件位置来通过 |
| 548C：扰动与组合 | 固定同一电气 `CircuitSpec`，替换同功能符号的外形、引脚方位、较长网名/位号和值行，改变允许的姿态；再组合 2–3 个岛 | 每种变体同样通过电气与可读性硬闸，逐岛视觉能识别功能、主路径和支路归属；无解时给结构化拒因。CH343/CH340 两拓扑不回退。若只在原位号、原字体或原符号尺寸下过关，仍算过拟合 |
| 548C2：共享电源网诊断 | 用页面同一 `gndClustering.radius=100` 对照单岛与多岛 | **批次前提已证伪**：单岛同样四节点，不能靠“不拆”恢复穿体母线；拆分地每簇命名仍待裁，生产代码未改 |
| 548C3：页端口与 label 承载杆 | `<位号>.<脚名>`、页兜底 label 压文字/竖命名，及页面预算覆盖洞 | **②③④ 已落**：同一把脚尺、未知脚拒绝、自有水平杆、具体 strict xfail；① 与整页最终 gate 未关闭，永久回归覆盖 `_compile_modules + _module_ports` |
| 548C4：长位号/长值行 | 固定电气，只加长文字；独立闸点名 `texts × labels` | **B1 已落、B3 未落**：有界文字重座椅与零移动已入回归；B2 由 548C6 关闭，B3 电源陈述仍待独立批 |
| 548C6：同岛二维支路座位 | 普通/119 加宽轮均无候选的单模块；真实文字/器件/引脚度量 | **B2 已落并通过离线三关**：救援轮闭式分配 line 轴座位、绕针后重核 near/碰撞/文字侧；旧可编译页零移动。多岛页不启用，最终全量见§9 |
| 548D：547 自动整页 | 使用冻结的 30 件 / 31 网 / 5 NC / 8 岛完整语义规格，以 `draw compile` 自动生成整页；不读参考图坐标，不使用 547G 的显式几何计划 | 同一候选 `ok=True` 且 hard violation 为 0，独立逐脚/NC 与 0 短路全部通过；渲染逐岛检查功能归属、流向、成对一致性、文字/旗标和页面禁区。任何一关失败都不记“自动整页完成” |
| 548E：真机闭环 | 仅在 548D 离线三关通过后，按 `tasks/547_smart_medicine_box.md` §2 的真机纪律，在逐字核对身份的 `test V4` 新页用实测 profiles 执行 plan/apply | live lint、宿主独立网表/NC、DRC 分诊、全页及逐岛渲染、关闭重开持久化分别留证；DRC `passed=false` 或仅 `saved_unverified` 必须如实披露。保留既有页和相邻回归；未通过不交付，也不触碰原 SmartMedicineBox 工程 |

若 548A 将正式规格的 `stub` 从 `straight` 改为 `auto`，保留两者的对照与原电气断言；不宣称旧 `straight` 在该密度下已通过。548A/548B 的先后依赖是自动整页集成；若 548A 的标签走廊问题需要独立合同，应从该批拆出最小一批，但不得借“换一处冲突”宣称完成。548C 可以在相应单岛能力过闸后逐步累积，548D 必须等 A/B 与必要的 C 变体通过。每批失败都保留原输入、候选/拒绝报告、图像、独立 oracle 和复现命令；不要反复整页 apply 寻找运气。

## 3. 约束与验收账本

| 账 | 必须记录 | 不可替代 |
|---|---|---|
| 输入 | 电气来源/假设、功能岛、主路径、支路意图；有没有人工几何 | 不能以删件、拆散附属支路、改网或参考坐标换取过闸 |
| 自动机器闸 | `draw compile` 的 `ok`、hard/soft 拒因、候选和指纹；独立逐脚/NC/短路核对 | lint 或编译成功不等于电气正确 |
| 人的视觉闸 | 每岛一句功能与流向、主支路可辨、同类支路一致、线/字/旗/标题栏归属清楚；逐项对照样式规格 | 不能用 machine green 或分数代替读图 |
| 真机与保存 | 工程/页身份、profiles、plan/apply、live lint、宿主网表、DRC 原始 verdict、渲染、重开状态 | `0 error` 不等于 DRC `passed=true`；保存不等于 `saved_verified` |
| 结果类别 | `automatic` / `reference-replay` / `agent-adjusted`；后者每次调整的原因和前后证据 | 辅助三关通过不关闭自动能力缺口 |

Agent 微调是合法兜底，但必须走受守卫接口，记录改动前后并重跑同一组三关。同类微调第二次出现时，回提为通用约束的候选需求；不能累积隐形坐标脚本。超出已支持电路族时，明确列出不支持的语义/几何原因和人工接手点，拒绝也算诚实结果。

阶段评估记录首次可接受率、人工返工分钟、结构化拒绝率、读图正确率和模型/工具成本，按电路族和结果类别分层，不预设没有样本支持的百分比目标。首次可接受须由工程师在**不看网表答案**的情况下说明功能、主路径和关键支路，再与电气 oracle 对照；视觉意见和机器读数分栏。

## 4. 实施纪律与停止条件

- 不复活 201C rip-up 或 201D 旧加权文本方案，不直接对整页上 CP-SAT。优先让构造候选显式预留支路体、标签、旗标和线路走廊；路由失败若能给冲突证书，可将有限的禁止顺序/通道需求反馈给下一档候选，避免无界重排。具体算法要以最小失败证据决定，不把方案预写成已实现能力。
- 算法批与 Rust 迁移分开；shared/parser/model/bridge/CLI 合同变更走 `tasks/shared-platform.md` 集成锁。保留旧拓扑输出指纹与 547S 排序回归；新语法显式 opt-in。
- 每批先聚焦测试与负控制，再按 `tasks/draw-line.md` 的范围做邻域及交付验证。完整四线、真机和 shared 变更串行；真机前提与安全边界以仓库 SOP 和 547 任务书为准。未跑的检查写“未跑”，不得沿用别批绿读数。
- 连续两次只把冲突移动位置、无新的失败证据时停下缩小复现；不能通过调权重、扫数值或放宽硬闸消掉红灯。阶段出口未满足就留在该阶段，后续整页与真机不得提前记完成。

## 5. 批次进度账

### 548A（2026-11-07）：冻结完成，夹具缺陷已修，联合几何未落生产代码

**冻结**（`evidence/548A/`，一条命令可复现且不随测试文件漂移）：`repro.py` 先把 547A 岛的三份
输入写进 `fixture/` 再回读编译；`fixture-manifest.json` 与 `baseline-hashes.json` 记夹具/基线
哈希（开工时 `drawcompiler.py` `f6825e8a…`、`placement.py` `ec1182d7…`，与 547D 记录的 547S
验收基线逐位一致）；`dirty-baseline.txt` 是开工前 33 项未提交改动快照。

**冻结时查出的输入缺陷（547D 未报）**：`BUZZ` 网声明 `U1.PC0`，但同文件内联的 `MCU32` 没有
PC0 脚（14+18=32）。真实 547A 库 `evidence/547/a/smart_medicine_box.library.json:170` 有它，
电路 `:329` 也把 `U1.PC0` 接在 BUZZ 上 —— 内联副本抄漏。后果是 `BZ1` 的 anchor 落到岛原点
`(0,0)`，独立可读性闸以 `required-pin-not-connected … U1.PC0` 拒稿，**修复前该用例不可能绿**。
已把 PC0 按真实库的**左侧**补回（tip `(-80,-55)`），电路/网表/断言/`stubMin` 不动；修后左列
15 引脚、多一条 GND 跑线，工况更紧。

**失败证书**（`evidence/548A/README.md` §3）：`BOOT0`（R1，anchor `(-80,25)`）与 `GND`（C1 回流）
两条跑线穿过 `SWCLK` 盒 `[-133.5,0.5,-92,9.5]`；元凶是 `C1`＝3V3 去耦（`U1.VBAT`，行 45）按
"挂在回流侧"体位摆放，40 单位脚距覆盖行 25…65，恰好压住 `BOOT0` 的引脚行；7 个 variant 全拒，
标签四方向梯子耗尽（`_reseat_crossed_labels` → `_reseat_failure`）。

**联合几何：杠杆已定位，生产修复未实施。**`probe_band.py` 证明单改逃逸方向不成（上行让 3V3
八个脚无法连通）；`probe_pose.py` 证明"体厚超过一个引脚行距的两端件沿自己那行摆"可让
`ok=True`、1 候选，且 strict xfail 自己的分区算术 `four KEY nets: ok`。那版门太宽（四键、两灯、
蜂鸣器一起改），只证明杠杆，不是可交付补丁。

**出口判定（当轮）：未通过。**生产代码零改动、xfail 未摘、未跑邻域/全量四线/真机、无候选落画布。
下一步最小动作（已执行）：在 `_signal_pair_body_direction` 旁加坐标感知的窄门。

### 548A 窄门尝试（2026-11-07）：判据被证伪，已回退，未通过

**补丁**：`drawcompiler._foreign_row_body_direction()`（紧邻 `_signal_pair_body_direction`；调用点在
543K 之后、`_branch_body_direction` 之前）。判据是坐标事实而非形状：G1 二端件（`len(pins)==2`、
共享/回流脚可解析、符号自身坐标系内两脚共轴）；G3 宿主为本槽 owner 且是 chain、`_accepted_poses`
非空；G4 旧体位竖向；G5 宿主上存在异网引脚（网 ≠ 共享网）；G6 在与 seat 同侧**每个**宿主合法位姿下，
另一脚行（共享脚行 + `hang[1]×脚距`）落在某个异网引脚行（±GRID/2）；G7 seat 由
`_branch_offset_direction`（默认位姿）读出且水平。G6 收窄到 seat 同侧位姿，是因为 `_prepare`
阶段宿主位姿尚未被关系锁死（实测 8 个位姿全在集合里），而 mirror 只翻 x 不改行。

**命中面**（冻结夹具，`.tmp_548A/probe_gate.py`，清单 `evidence/548A/gate_hits.txt`）：8/9 命中
（`C1/R1/D1/D2/S1–S4`），`BZ1` 不命中（PC0 行减 40 无宿主脚）——比旧宽门「体厚 > 行距」窄。
`ok=True`、1 候选、`four KEY nets: ok`；窄门前同夹具 `ok=False`（`layout-unsat`，`SWCLK` 盒被
BOOT0/GND 两条跑线穿过）。

**验收**：`--runxfail` → 2 passed；不带 runxfail 先见 `[XPASS(strict)]`（1 failed/1 passed），
之后才删 `xfail` 装饰器（断言未动），摘标后 2 passed。邻域 547 系列 + 543K：22 passed；
`tests/test_547_named_pin_plan.py` 的 4 个 `tmp_path` 用例因沙箱 basetemp 更新（运行时新建目录
不可 `os.scandir`，WinError 5）记「未跑干净」，不计绿。读数：`evidence/548A/green_readings.txt`；
证书：`evidence/548A/narrow-gate-certificate.md`。

**边界**：未跑真机、未落画布、未宣称自动整页；548D 出口不变，548B 串联语义仍不属本批。

**回退与判定（决定性）**：窄门同时改动了飞反激页面——`201b`（2 条）、`119`、`120`、`534` 在
gate 开时红、gate 关时全绿（74 passed / 2 skipped）；`115/116` 两条合成夹具另由 G8「行向体位须有
合法位姿」挡住。「另一脚落在异网引脚行」是**必要不充分**条件；只对同宿主 N≥3 二端支路生效的收窄
也未分开（534 转绿、201b/119/120 仍红）。按纪律不以别处红换此处绿：`drawcompiler.py` 删除
`_foreign_row_body_direction`（125 行）恢复原调用点、`test_547_repeated_shunts.py` 恢复 xfail 标记，
复验 `1 passed, 1 xfailed` 与 4 文件 `74 passed, 2 skipped`。**548A 未通过，strict xfail 保留。**
完整反证与下一步（给窄门补重复支路组的**语义**条件，不再调坐标阈值）见
`evidence/548A/narrow-gate-certificate.md`。

### 548A 语义窄门（2026-11-08）：同宿主同回流支路组，4 负控复绿，strict xfail 已摘（A-R 后：完整 N≥3 面板支路出口通过，见 §17）

**起点**：上一轮坐标窄门（「另一脚落在宿主外来引脚行」）必要不充分，已回退。本批只做
548A 的下一步最小动作：补一条**语义**条件；不许动坐标阈值、不许调权重、不许扫数值。

**步骤 A（先做，断言级证据）**：从上一轮 gate 开时全量 junit（`.tmp_548A/full2.xml`）抽出
5 条失败原文；按派单 §4 的 G1–G7 与上一份证书 §1 的 G8 把已删除的窄门重建为**只读探针**
（`.tmp_548A/gate_probe.py`），先验证等价——547A `--runxfail` → 2 passed，4 负控 gate 开 →
**5 failed / 69 passed / 2 skipped** 且失败节点逐条相同。5 条红的断言/期望/实际：

| # | 测试节点 | 断言 | 期望 | 实际 |
|---|---|---|---|---|
| 1 | `test_201b_placement::test_the_flyback_has_no_candidate_today_which_is_why_this_module_exists` | `label_fallbacks` net 列表（`:537`） | `HVDC, SEC_12V, SEC_GND` | 多一条 `SRC` |
| 2 | `test_201b_placement::test_the_flyback_is_placed_with_every_relation_kept_and_nothing_hard_broken` | `misses == []`（`:562`） | 0 | `relation:left-of(U5,U4)` 差 2.5；`U5=(-15,-720)`、`U4=(-15,-670)` |
| 3 | `test_119_pose_ladder_widening::test_the_single_module_flyback_still_shows_the_widening_reading` | `label_fallbacks`（`:652`） | 同上三条网 | 多一条 `SRC` |
| 4 | `test_120_island_placement::test_the_near_trim_spends_a_whole_lattice_step_not_a_half_one` | `closed` 非空（`:683`） | 存在 margin = 整格 5 的一对 | `closed=[]`；`near(R15,T1)` margin **4.3228** |
| 5 | `test_534_label_stub_typography::test_the_legacy_three_island_sheet_overflows_the_stated_page_and_is_named` | detail 含 `draws 1146.5 x 240`（`:539`） | `1146.5 x 240` | `1131.5 x 240` |

**被移到什么位姿**（探针逐条记录）：附加门把 `C5`（T1，HVDC→CLAMP）与 `R15`（T1，
HVDC→CLAMP_B）从 `90` 位姿改到 `0` 位姿；把 `C3`（U1，V3→GND）从 `270` 改到 `180`。
第 1/3 条是 `C5/R15` 换横后 `SRC` 无法并线被降级，第 2 条是同一换位改变 `U5/U4` 链布局，
第 4 条是 `R15` 换位后 `near(R15,T1)` 余量掉到 4.3228，第 5 条是 `C3` 换横后 ch343 模块窄 15。

**步骤 B（先写成文，再改生产）**：新证书
`evidence/548A/narrow-gate-semantic-certificate.md`。判据 **G9「同宿主同回流支路组」**：

> `B(S) = { b ∈ ctx.slots | b.kind=="branch" ∧ b.owner==S.owner ∧
> b.other_net==S.other_net ∧ len(ctx.profile(b.part_id).pins)==2 }`；
> **仅当 `|B(S)| ≥ 3` 时窄门才返回行向体位**。

成员只读网表拓扑与符号脚数，不读坐标/间距/标签宽度/权重。实测组规模：548A 的 U1 上
GND 组 5（`BZ1,C1,D1,D2,R1`）、3V3 组 4（`S1–S4`）；飞反激 T1 的 CLAMP 组 2（`C5,D1`）、
CLAMP_B 组 1（`R15`）；534/ch343 的 GND 组 2（`C1,C3`）——G9 对后三条负控支路全部说
「不是本闸的事」。预测先落纸：547A 命中 8（`BZ1` 另被 G6 挡），4 负控 0 命中、合计
`74 passed / 2 skipped`。只读探针验证预测全中（547A 2 passed；4 负控 74/2）。

**步骤 C（生产落码与验收）**：`drawcompiler._foreign_row_body_direction()`（G1–G9，
紧邻 `_signal_pair_body_direction`）+ `_same_return_bank()`；调用点在 543K 之后、
`_branch_body_direction` 之前。硬顺序读数：`tests/test_547_repeated_shunts.py`
`--runxfail` → **2 passed**；不带 → **`[XPASS(strict)]`（1 failed/1 passed）**；此后才摘
`xfail` 装饰器（断言一字未动），摘标后 **2 passed**。4 个负控 gate 开 **74 passed / 2 skipped**、
gate 关（`GATE_548A=off`）**74 passed / 2 skipped**；邻域 543K + 547 三文件 + 115/116：
42 passed，3 条红（`115/116` 的 `098_scene08` 与 `116::test_the_pass_moves_nothing_…`）在
gate 关时同样红 ⇒ 工作树既有；`test_547_named_pin_plan` 4 个 `tmp_path` error 仍是沙箱
`os.scandir` PermissionError（与上一轮同因，记「未跑干净」）。

**全量合树**（2026-11-08，`-n 4 --dist loadfile --basetemp=.tmp_pt_548a_full2` +
`--junitxml=.tmp_548A/full3.xml`）：**10054 tests / 18 failed / 2178 errors / 22 skipped**。
与上一轮同树基准（`.tmp_548A/full2.xml`：10054 / 25 failed / 2178 errors / 22 skipped）逐节点
比较：少掉的 7 条正是旧坐标窄门打红的 `201b`×2、`119`、`120`、`534`、
`115::test_the_criterion_is_conservative_when_another_pose_would_say_it`、
`116::test_a_branch_order_naming_the_other_axis_is_honoured`；剩余 18 条全部在旧基准里存在
（parts library、harvest、rehome、process guards、098 等），**无新增失败**。2178 个 error 全是
`failed on setup with "PermissionError"`（沙箱 `os.scandir`），与上一轮同因，不计为本批红。
汇总行仍被 `pytest_sessionfinish` 的 basetemp PermissionError 吞掉，计数取自 junit XML。

**边界**：未跑真机、未落画布、不宣称自动整页；548B 串联语义合同不属本批；改的是通用窄门
（判据不是 547A 专属），但只证明了 547A 与两条负控页的边界。证据
`evidence/548A/narrow-gate-semantic-certificate.md`；复跑装置 `.tmp_548A/gate_switch.py`。

### 548B（2026-11-08）：语义合同评审包已出，未实施

**本批 = 草案，未实施。**只产出 `evidence/548B/contract-draft.md`（合同提案 + 8 条反例 + 2 条
正例 + 与 CircuitSpec/PresentationSpec/LayoutPlan/DesignIntent 的边界）与
`evidence/548B/review-checklist.md`（10 条二选一）——**当时状态：评审包待拍板**（后续：岳已全部按推荐，实施与验收见 §13–§15）。**零生产代码**：`src/`、`tests/`
在开工与交卷时逐位相同（13 个既有脏文件 sha256 前后一致，`drawcompiler.py` 仍是 548A 证书的
`1dac9bb3…`），`git status --porcelain` 与开工基线 33 行逐行相同，本批未新增 git 条目
（证明见 `evidence/548B/zero-code-proof.md`；`evidence/` 按 `.gitignore:52` 是本地证据）。

**提案要点**：`PresentationSpec` 新增可选顶层键 `seriesBranches`，条目五键
`id` / `from` / `to` / `parts` / `middleNet`，封闭 schema、`parts` 恰好两件有序、**条目里没有
数字**；只表达器件顺序、两个端点、中间网，坐标仍只在 `userLocks`（`_refuse_coordinates`
原始载荷遍历 + 封闭键集 + 无数字 + 独占坐标入口四道）。**默认关闭**写成 C1–C7 可验收条款：
未写该键的文档 `presentation_sha256` 钉住数字不变、旧夹具编译 `geometry_sha256` 逐位不变、
`[]` 等同不写、不新增 CLI flag、旧规格不自动识别、先出"前"读数再落码。

**未跑 pytest**（零实现，无新断言）、未跑真机、未落画布。548D 仍等 548B **实现**过闸；本草案
不改这个依赖。拍板后另开实施批（字段若选备选，先改草案再送一轮评审）。

### 548C（2026-11-08）：扰动与组合，部分通过

**结论：部分通过。** 固定 547A 同一电气夹具，只换表面后逐变体走同一套闸：**A 同功能换符号 4/4 过、
C 长网名 2/2 过、D 允许姿态 2/2 过；B 长位号/长值行 0/3（全被结构化拒绝）；E 2–3 岛组合 0/2
（全被拒）**。8/11 个单岛变体过闸、0/2 个组合变体过闸。**不能记“能力已泛化”**：B 组证明它对
短位号/短值行是特化的；E 组证明单岛通过不能直接加和成页面能力。

**输入**：`evidence/548A/fixture` 未改一字（21 件 / 26 网 / 7 module）；A–D 走与 547A 测试/repro
相同的 `pc._module_view(circuit, presentation, "mcu")`（10 件 / 51 脚 / 26 网，其中 16 条单成员
跨模块端口）；E2/E3 是同一电气的显式子集（11/59/15、15/73/20）。13 个变体全部由
`evidence/548C/variants/build_variants.py` 从冻结夹具生成，无 `userLocks`、无摆放坐标、无删件/
拆支路/改网/缩短文本；生成后逐件逐脚逐网自检通过。

**闸与读数**（`evidence/548C/tools/gate.py`；官方 `draw compile` 另复核 A1/A2/A4/C2/E2，读数一致）：

| 变体组 | 变体 | 结果 | 几何指纹 / 拒因（摘要） |
|---|---|---|---|
| A | KEY 横脚 / LED 竖脚 / 蜂鸣器竖脚 / MCU 体窄脚长 70 | **4/4 过** | `32d614e0…` / `764f2b2c…` / `47399909…` / `be51891f…`；各 1 候选、hard 0、短路 0、NC 0 |
| B | 长位号 / 长值行 / 两者 | **0/3 过** | B1 `[text-overlap] texts[7] 'LED' [113.5,51,137.5,60] × labels[10] 'LCD_SCK' [92,50.5,147,59.5]`（7 variant 全拒）；B2 同类 4 条 + 1 网降级；B3 3V3 八脚无法并线；均 0 候选 |
| C | 面板本地网长名 / 全 26 网长名 | **2/2 过** | `0e9c350d…` / `051eb4fe…`；C2 的 16 条 20–32 字符跨模块长名**全部整行印出**；8 条本地 wire 网与 2 条轨旗按基线同款不印名 |
| D | sidePreferences 全翻 / 再加 KEY 镜像脚序 | **2/2 过** | `96b00a73…` / `846afd79…`；hard 0、短路 0 |
| E | mcu+lcd 两岛 / mcu+lcd+wifi 三岛 | **0/2 过** | `layout-unsat/modules[mcu]`：GND 的 7 脚被画成 4 个独立节点（`BZ1.2`；`C1.2,R1.2`；`D1.2,D2.2`；`U1.VSS,U1.VSSA`），lcd 岛本身 ok、整页 0 页 |

**独立电气**：`readability.derive_netlist` 重新推导连通分量后与 `CircuitSpec.nets` 逐网比对；
通过变体均 26 网 sameNode、0 短路、0 未放置。本夹具 `nc=[]`，NC 检查为空集通过，不伪造正例。
**可读性**：与 548A 同一套 `readability.check/check_page`，通过变体 hard 0；软指标原样留档。
**视觉**：编译器 `cand1.svg` 用本机 WPF 栅格化为 PNG 后逐张读过（A1/A2/A4/D2/C2），逐岛能认出
U1 宿主、四键、两灯、蜂鸣器、去耦/BOOT0 支路与 16 条跨模块长名；成对支路未被打散，无标签互压。
证据 `evidence/548C/README.md`、`results/*.json`、`render/*/cand1.png`。

**零移动**：`tools/ch34_readings.py` 复现 CH340 pinned 几何 `6ed82091…` + plan json `3757542a…`、
CH343 pinned 页几何 `2ec6b700…`；开工前与收尾两次输出整文件 sha256 均为
`213931eba47b01f89b4b044186955f54585ce945e9173d126291c67917a1ba4a`，**逐字节 identical**。
本批未改 `src/`，这是实测不是保证。

**基线证据的一处已知瑕疵**：`evidence/548A/repro.py` 成功路径也会把 `None` 追加进 `merged`，
于是打印 RED/exit 1；同一夹具的 `tests/test_547_repeated_shunts.py` 本轮复跑 **2 passed**。这是
548A repro 自己的记账 bug，**本批不回改 548A**；548C 基线以测试与 `results/baseline.json` 为准。

**全量合树**（2026-11-08，`-n 4 --dist loadfile --basetemp=.tmp_pt_548C_full`
`--junitxml=.tmp_548C/full.xml`）：**10054 tests / 18 failed / 2178 errors / 22 skipped**。
与 548A 的 `full3.xml`（同 10054/18/2178/22）逐节点比较：失败/错误节点集合 **新增 0、减少 0**；
18 failed 全是既有节点，2178 error 全是沙箱 `os.scandir` 的 setup PermissionError（含
`pytest_sessionfinish` 吞汇总行），不计本批红。

**边界**：未跑真机、未落画布、不记 `automatic` 整页；未使用 548B 的新语法；548D 出口不变。
E 的拒因是 `pagecompiler` 在共享 GND 上的能力缺口，不得靠改页框/删件/指定坐标绕过。

### 548C2 多岛共享电源网统一（2026-11-08）：未通过，批次前提被证伪

**先写成文**：`evidence/548C2/criteria.md`（C1–C6 判据 + P1–P5 预测，改动任何生产代码前写定），
8 个只读探针在 `evidence/548C2/probes/`（单进程、无 fan-out）。

**结论（决定性）**：E2/E3 的 `layout-unsat/modules[mcu]` **不是多岛问题**。把 547A 自己的 mcu
用页面同一预算（`gndClustering.radius=100`）编译，**它同样失败、同样 4 个节点**；547A 之所以绿，
是因为出厂测试 `dc.compile(local_circuit, local_presentation, book)` **不传预算**（radius=0），
535 的拆分地路径从未被这份夹具走过。单变量对照见 `readings_e3.txt`。

**三层缺口**（对象与实测尺寸见 `evidence/548C2/README.md` §2）：**A** 模块层拆分地的每个邻域
**一句命名陈述都没有**（库无 `PWR-*` 符号，`_flag_plan` 返 None 后整网 `continue`）⇒ 7 脚 4 节点，
`BZ1.2` 连导线都没有；**B** 页面端口用**裸成员名**（`J1.VCC`/`J1.GND`/`J1.CS`）去查按**脚号**
`J1.1…J1.8` 建的 `_pin_points` ⇒ `_port_point` 返 None，整页拒；**C** 页面 label 兜底的承载杆压住
模块自己的值文本 `texts[7] 'LED'` `[488,726,512,735]`，另一根 `segments[20] 'GND'` 被**竖着命名**
（`name-row-vertical`）。

**「不拆」已被反证，不得作为实现形式**：强制 radius=0 后 GND 变成 420 单位母线，
`segments[8] 'GND'` 的 (100,580)→(190,580) 横穿 `parts[U1]` `[210,585,350,785]` —— 正是 535
当初要消灭的形态。

**生产代码零改动**：`src/` 全部文件 mtime 早于本批开工时刻 03:30:04（`drawcompiler.py` 01:07:56），
本批写入只落 `evidence/548C2/` 与 `.tmp_548C2/`。**零移动**：548A 四负控 **74 passed / 2 skipped**、
`tests/test_547_repeated_shunts.py` **2 passed**、CH340 `6ed82091…` / CH343 `2ec6b700…` MATCH、
`ch34-before/after.json` sha256 均 `213931eb…a4a`。**全量合树**
（`-n 4 --dist loadfile --basetemp=.tmp_pt_548C2`，junit `.tmp_548C2/full.xml`）：
**10054 tests / 18 failed / 2178 errors / 22 skipped**，与 548C 的 `full.xml` 逐节点比较
**新增 0、减少 0**；18 failed 全既有、2178 error 全是沙箱 `os.scandir` 的 setup PermissionError
（汇总行被 `pytest_sessionfinish` 吞掉，已知现象），不计本批红。

**还缺的那一条语义事实**：拆分地的**每个邻域必须有一句可读的命名陈述**；库无该网旗符号时这句
只能是**标签**（页层 `_net_style` 已经如此，模块层给的是「零陈述」）。是否采「模块层补标签兜底」
**要岳拍板**——它会把 GND 标签写进模块图，与「地/电源网一律旗标、禁网络标签」的交付红线的关系
需岳裁定；在此之前本批不落地。

路由入口：`tasks/draw-line.md`；产品边界：`docs/product-boundary.md`；现有绘制合同：`docs/draw.md`；验收样式：`docs/schematic-style-spec.md`；压力测试与暂停快照：`tasks/547_smart_medicine_box.md`。

### 548C3（2026-11-08）：页面端口成员名解析（②）与页 label 兜底承载杆（③），④ 覆盖洞已钉

**范围**：只做 548C2 的 ②③④。**①（拆分地每簇在库无旗符号时用标签陈述）与「地/电源一律旗标、
禁网络标签」的交付红线冲突，已上交项目主人裁定——本批一行未碰，也没有换写法绕过。**

**判据先写成文**（`evidence/548C3/criteria.md`，C1–C6 + P1–P6，写于任何 `src/` 改动之前；
开工基线哈希 `evidence/548C3/baseline.txt`）。**文件域**：派单写的是 `drawcompiler.py`，但 ②③ 的
实际失败代码在 `pagecompiler.py`（`_module_ports`/`_port_point`/`_add_label`），按真实归属只改
`pagecompiler.py` 一个生产文件；`drawcompiler.py`/`readability.py`/夹具零改动。

**② 落**：`pagecompiler._port_members()` 把 `<位号>.<token>` 过
`readability._profile_pin_ruler`（脚号优先、再脚名）解析成该符号自己的**脚号**，再查按脚号建的
`_pin_points`；符号没有的 token 成为 `GrammarFailure`，detail 逐字点名成员、符号与脚表
（`J1.NOPE` → `symbol 'LCD' carries no pin 'NOPE' (the symbols pins are 1/VCC, 2/GND, …)`）。
不猜、不按前缀撞、不起第二把尺子。

**③ 落**：页在「模块无陈述 + 库无旗符号」时加的兜底 label，原先把锚点放在模块引脚尖端——只要该点
落在模块自己的导线上（端点/顶点/中段），`core.layoutplan.label_wire_indices` 就把**经过该点的
每一根线**都当成名字载体，宿主在每根线最长直段中点印名字：E2 的 `texts[7] 'LED'` 被
`segments[9] 'GND'` 的名字行压住、`segments[8]` 的名字行压 `U1` 体、lcd 的 `segments[20]` 因
50 单位竖跑线被竖着命名。改为：锚点骑导线时，页给 label **自己的水平承载杆**——候选顺序是编译器
既有直线 stub 梯级（`drawapply.LABEL_STUB_LENGTHS_STRAIGHT` 40…240，短→长）× 按端口朝向排序的
成员脚 × 水平两向；引脚已有同向短桩时从该桩**远端**续画（同一条直线只画一次）；杆体、名字行、
label 盒三者都要清空 `_module_boxes` 的 occupied；竖直杆一律不做（S-20 / `name-row-vertical`）。
没有新阈值、没有扫坐标。

**读数**（只读探针 `evidence/548C3/probes/`，单进程）：
- `probe_p0` provenance：一个 label 锚在 `(240,25)` 时 `segments[8]` 与 `segments[9]` **同时**成为载体。
- `probe_p1` 可行性：朝向侧（mcu D2.2 东）在 40…240 全被邻件挡住；C1.2/BZ1.2 西向、lcd J1.7 西向 40 合法。
- `probe_p2` 修后（只把模块预算 radius 按 548C2 单变量改 0，端口/label 都是生产函数）：
  `page ok=True pages=4 captured=0`；548C2 的三条违规全部消失；GND 9 脚 1 节点、3V3 9 脚 1 节点；
  页新增三根 40 单位水平杆（3V3 `(675,720)-(715,720)`、GND `(190,760)-(150,760)`、
  GND `(935,770)-(975,770)`）。

**④ 落**：`tests/test_548c3_page_port_members.py` 新增 strict xfail
`test_the_547a_island_still_refuses_the_page_budget`：547A 的 mcu 在页面预算 `radius=100` 下仍
`ok=False`（GND 拆成 4 个零命名邻域）。reason 写明「出厂测试不传预算、radius=0，此路径从未被
547A 夹具走过；① 未裁定前不可能绿」；**转绿（XPASS(strict)）即信号**：该洞已被 ① 或等价能力补上。
这是覆盖洞的记录，不改生产代码。

**验收**：新测试 **3 passed / 1 xfailed**；548A 四负控 **74 passed / 2 skipped**、
`test_547_repeated_shunts.py` **2 passed**、CH340 `6ed82091…`/CH343 `2ec6b700…` MATCH、
`ch34-*.json` sha256 均 `213931eb…a4a` 逐字节不变。全量合树读数见 `evidence/548C3/README.md` §7。

**边界**：未跑真机、未落画布、不宣称自动整页；未拆岛/删件/改网/缩短网名；未调阈值、权重或坐标；
未指定元件位置。

**留给岳的唯一裁定（①）**：拆分地的每一个邻域在库无旗符号时如何陈述——用标签就与红线冲突，
不用标签就是零命名（`netlist-partition-mismatch`）。②③ 只让页层不再制造假绿与承载杆硬伤，
不替这条裁定做决定。

### 548C4（2026-11-08）：长位号 / 长值行文字压线 — B1 落，B2/B3 未落

**先写成文**：`evidence/548C4/criteria.md`（C1–C6 判据 + P1–P7 预测，写于任何 `src/` 改动之前；
开工哈希 `drawcompiler.py 1dac9bb3…`、`placement.py ec1182d7…`、`pagecompiler.py 975e6b1c…`、
`readability.py 0c42bca1…`）。

**失败层（只读探针实测，不是推断）**：`_line_boxes` 把整个文字栈「以器件包围盒中心为轴、按
最宽行定宽、位号与值同侧」摆放；B1 的 93 宽位号把 value 行左缘拖到 113.5，正压 MCU 右侧的
`LCD_SCK` 行 `[92,50.5,147,59.5]`。而 `_part_texts` 的墙集只有 keepout、别家器件体/引线与已落
文字——**没有标签走廊**：`expressions` 在 11700 才算、标签在 12085 才落座，都在文字之后；标签
自己的 4 方向 × 4 梯级已被 MCU 右侧五条 LCD 标签占满，只能回退首选方向。文字梯级顺序是
**rung 外、side 内**（9138–9148），无解时按 `TEXT_SIDES[0]` 落座并让闸拒稿（053 §5 既定口径）。

**落地的修法（只改 `drawcompiler.py` 一个文件）**：`_build_one_variant` 增
`extra_text_walls` / `text_repair_round`；闸报 `text-overlap` 且对象是 `texts[i] × labels[j]`
时，用新增的 `_text_label_repair_boxes` 取**闸自己点名的** label 盒补进文字墙集、重建该
variant，最多 `TEXT_LABEL_REPAIR_ROUNDS = 4` 轮（148 的 name-row 逃生梯同一形状）。
`texts[i] × parts[...]` 不在此列：那是「该节距下无自由侧」，补墙集挪不动器件。
**零移动是结构性的**：没有该相撞的页面 `text_repair_round` 恒 0 ⇒ 与改前逐字节相同
（实测基线 `b71fcbcf…` 两次一致）。**为什么不选别的文件**：`readability.py` 是裁判（放宽即
放水）、`pagecompiler.py` 是页层（B 组走单岛 `dc.compile`）、`placement.py` 是分支座位/姿态
（B2 的节距在 `_chain_and_shelf_layout` 的 `pitch = ahead + behind + channel × scale`）。

**读数**：B1 `ok=True`、1 候选、几何 `868cc95b5570e55a`、hard 0、grammar findings 0、
26/26 网 sameNode、0 短路、0 未放置、必需文本缺失 0、10 个长位号与 10 条长值行**全部整行印出**
（无隐藏/缩写/折行）；渲染 `evidence/548C4/render/b1-long-refdes/cand1.png` 逐岛读过（宿主、
四键、两灯、蜂鸣器、去耦/BOOT0 归属与基线一致，16 条跨模块名仍在引脚侧成列，无文字互压）。

**B2 未落**：标签压线已解，剩 `texts[5] 'Red LED 2.0 V 20 mA 0603' [188,23.5,347.5,32.5] ×
parts[D2]/parts[S1]`——159.5 宽值行在 60 节距下四方向 × 四梯级全被挡（MCU 引线桩 0.3 单位 +
D2 体 + MCU 体）。实测同一修复 + 节距 2.93×/3.5×/4.79× 均 `ok=True`、hard 0 ⇒ **缺的是
「节距必须容纳器件自身的文字行」**，尺度属布局/变体层，本批不落。
**B3 未落**：第一拒因仍是 `layout-unsat/3V3`（power 网、库无旗符号、退化为导线后 8 脚在走廊内
并不上；放大页框到 ±6000 仍拒）⇒ 缺「3V3 用非导线方式陈述」这条事实，与 548C2 ① 同族；岳 2026-11-08 已裁为禁网络标签、旗标入库，落地由 C7/C7A/C7B（三次未通过）另批。

**负控零移动**：548A 四负控 74 passed / 2 skipped、`test_547_repeated_shunts.py` 2 passed、
`test_548c3_page_port_members.py` 3 passed / 1 xfailed（三组合跑 junit 82 tests / 0 failed /
3 skipped）；CH340 `6ed82091…`、CH343 `2ec6b700…` MATCH，`ch34-after.json` sha256
`213931eba47b01f89b4b044186955f54585ce945e9173d126291c67917a1ba4a` 逐字节不变。

**边界**：未跑真机、未落画布、不记自动整页；未改夹具/网表/文本长度/阈值/坐标；未加「长文字
特例分支」（新分支的触发条件是**闸自己点名的对象对**，与文字长短无关）。证据 `evidence/548C4/`。

## 6. 548R：审查整改（2026-11-08，当前）

主代理审查复现了 548C3 模拟整页与 548C4 B1，但两次独立变异证明聚焦测试不能防止回退。
岳批准在 2026-11-08 完成本轮整改；本批只补回归与文档，不扩大自动整页、真机或 547G
暂停目标，不做 git 写。

### 548R1：页面 consumer 与失败原因（一个测试文件域）

- 只改 `tests/test_548c3_page_port_members.py`。新增经过 `_module_ports` 或
  `compile_page` 的正向回归，不能只直接调用 `_port_members` / `_label_port_point`。
- 可用冻结的内联 547A 电路与受控 `gndClusterRadius=0` 模拟绕过本批范围外的①；
  不得 monkeypatch 被测的端口解析、label 承载杆或页面 gate。
- strict xfail 必须先钉 `layout-unsat` 与拆分 GND 的具体拒因，再保持 `assert result.ok`
  作为修复信号；无关失败不能继续记成预期 xfail。
- 主代理独立将 `pagecompiler._module_ports` 的 `preferred` 改错，新增回归必须红；
  cp 恢复并核对 sha256 后再复跑。

### 548R2：B1 正向与基线零移动（一个新测试文件域）

- 只新增 `tests/test_548c4_text_label_repair.py`，不改生产代码。
- 从 `test_547_repeated_shunts` 的内联电气/展示夹具按 548C B1 规则生成长位号，
  不得依赖 ignored 的 `evidence/` 作为测试运行输入，不指定元件坐标。
- 钉住 B1 `ok=True`、1 候选、hard=0、独立电气连通与长文字完整；保留基线几何零移动。
- 主代理独立把 `TEXT_LABEL_REPAIR_ROUNDS` 置 0，B1 回归必须红；cp 恢复并核对
  sha256 后复跑。若测试暴露生产缺陷，停止交主代理另派最小生产批，不在测试批顺手修。

### 548R3：文档与最终验收

- 清除 `docs/roadmap.md` / `tasks/SCHEDULE.md` 的控制字符与错误转义，修正 548
  “规划未实施”残留、索引遗漏、历史分界和 548 任务书的混杂行尾；保留全部失败边界。
- `docs/draw.md` 补 548C3 页端口解析与自有水平承载杆、548C4 有界文字重座椅的公开合同；
  未支持的 B2/B3、拆分地命名、真机与自动整页不得写成已完成。
- 聚焦与四负控复验后跑项目标准完整四线和卫生检查；既有环境或其他 agent 失败单独披露，
  不伪称全绿。最终真实读数写回本任务书、handoff、TASKMAP、SCHEDULE 与证据索引。
- 聚焦证据落 `evidence/548R/`，一次性变异备份与探针放 `.tmp_548r/`。删除仍走回收站，
  git 提交/推送逐次经岳批准。两名执行者各最多 40 步/30 分钟，不派第三级子代理。

### 548R 主代理验收与收口（2026-11-08）

- 两项永久回归已落：C3 覆盖 `_compile_modules + _module_ports` 并以 `_PageBudgetGap`
  限定 xfail；C4 从内联夹具生成长位号，钉住 B1、26 网/四键分区、完整文字和基线零移动。
  主代理聚焦 **85 passed / 2 skipped / 1 xfailed**。
- C3 `preferred` 源码变异为 **1 failed / 4 passed / 1 xfailed**，恢复后 **5 passed /
  1 xfailed**；C4 修复轮数置 0 为 **3 failed / 1 passed**，恢复后 **4 passed**。
  两次均 cp 恢复且 sha256 一致：`975e6b1c…` / `9c4e5264…`。
- 文档合同、路线图、handoff、TASKMAP、SCHEDULE、draw-line 与本任务书已同步，非法控制
  字符与“规划未实施”残留已清除。C3 最终组装页 gate 仍无正向覆盖；B2/B3、拆分地命名、
  自动整页、native/真机不因此批关闭。
- 完整 pytest **10022 passed / 25 skipped / 1 xfailed / 16 failed / 1 warning、0 errors**；
  两项新测试均通过。16 条均非本批新红：12 条既有货架/分类漂移、2 条既有 115/116、
  2 条 Windows 环境；527d2 的旧 setup error 与本次货架差异已单独对账，不伪称全绿。
- connector **576 passed + typecheck**；DSH **137 passed / 1 skipped + typecheck/build**；
  Rust **111 passed / 4 ignored + fmt/clippy**。仓库卫生 exit 0，两个历史二进制夹具按工具
  规则未扫描。完整证据与日志索引 `evidence/548R/README.md`。
- 本批无生产改动、无真机、无 git 写；547G 继续暂停。C4 测试批约 34 分钟略超软预算；
  文档批两处控制字符在 Edit 无法匹配时使用带唯一锚点和预期字符断言的字节替换，
  已由主代理复核并记录为执行偏差，不作为通用做法。

## 7. 548C5：由实际文字宽度推导支路节距（未通过，生产已还原）

岳批准继续推进自动线。本批只关闭 548C 的 **B2 长值行无自由侧**，不处理 B3、
548C2①、548B 串联语义、547G 或真机。开工生产基线：`drawcompiler.py`
`9c4e5264e8309f3d0f5e575416adcd1a1fdd38cbdb0b1d7517b47395e8262d36`。

### 文件域与前置读数

- 生产只许 `src/boardwise/engines/drawcompiler.py`；永久回归只许新增
  `tests/test_548c5_text_pitch.py`。不得改 placement/pagecompiler/readability、
  旧夹具、CLI/DSH、其他测试或文档。证据 `evidence/548C5/`，临时探针 `.tmp_548C5/`。
- 先用现有 B2 证明 `dc.compile` 当前 **0 候选**，首拒为长值行 `texts[5] × parts[D2]/[S1]`；
  记录新测试前红。548C4 的 2.93×/3.5×/4.79× 仅是诊断读数，**禁止**把这些数或任何
  数值扫描直接加入 spacing ladder。
- 新测试从内联 547A 夹具按 548C 的 LONG_VALUES 生成 B2，不读取 ignored evidence、
  不指定坐标、不改网名/位号/符号/电气。复用已有 C4 测试的生成接口时不得改写 C4 文件。

### 实现合同

- 在 `_chain_and_shelf_layout` 的实际节距层解决问题：邻件距离须由**各自实际文字行、
  符号位姿、已有 ahead/behind/channel 与既有文字侧/梯级**推导。优先最小通用改动；
  若必须改另一层，停止交主代理复核，不夹带第二文件域。
- 禁止按长文本字符串/特定位号特判，禁止缩短/隐藏/折行/改字号/位号与值分侧，
  禁止放宽 `TEXT_GAP`/`TEXT_SIZE`/`TEXT_ESCALATION_STEPS`/软硬闸/权重，禁止手填坐标。
- 不新增规格字段或 CLI。旧行为兼容的判据是：原有短文本及 CH34 pinned 几何逐字节不变；
  若旧节距已能合法容纳文本，不得仅为“更宽”而移动它。
- B2 必须 `ok=True`、至少 1 候选、hard=0，独立重推 26 网各一节点、0 短路、0 未放置，
  全部值行原文保留；B1/547A 不回退。若仍失败，保留结构化拒因，不改 B3 凑成果。

### 验收与停止线

1. 新测试先红后绿；B1、547A、C3 **5 passed / 1 xfailed**、548A 四负控
   **74 passed / 2 skipped** 与 CH34 pinned 零移动。主代理独立关闭新节距逻辑，
   B2 必须红，随后 cp 恢复并核对 sha256。
2. 主代理亲看 B2 渲染，逐区回答宿主、四键、两灯、蜂鸣器、去耦/BOOT0 的归属与文字；
   机器通过不等于视觉通过。未跑真机、未落画布，不记自动整页。
3. 聚焦后跑完整四线和卫生检查；548R 的 16 条非本批红是历史对照，不得用来掩盖新红。
4. 执行者最多 40 步/30 分钟，先交前红、设计依据、聚焦读数、hash 和剩余边界；
   连续两次只是移动冲突或无新证据即停，不扩项。

### 548C5 主代理复验（未通过，生产零净改动）

- 开工判断已纠正：该岛只有 `ctx.chain == ['U1']`，实际冲突位于分支 `lane*scale`
  与 `near_limit=300`，不是 chain pitch 的独立数值问题。两种加距实现均实测撞 near 后还原，
  `drawcompiler.py` sha256 与开工完全一致：
  `9c4e5264e8309f3d0f5e575416adcd1a1fdd38cbdb0b1d7517b47395e8262d36`。
- 新 `tests/test_548c5_text_pitch.py` 为 **2 passed / 1 strict xfailed**，保留 B2 的
  0 候选、首拒对象与 547A 基线指纹。主代理含 C3/C4、547A、四负控聚焦为
  **87 passed / 2 skipped / 2 xfailed**；日志 `evidence/548C5/focused-main.log`。
- B2 无候选，因此没有渲染可供主代理视觉放行，也没有新生产逻辑可做独立变异；
  不能把失败图或探针当交付。该结论只否定当前单列加距，不证明所有布局无解。
- connector **576 passed + typecheck**，DSH **137 passed / 1 skipped + typecheck/build**，
  Rust **111 passed / 4 ignored + fmt/clippy**。完整 pytest **10024 passed / 25 skipped /
  2 xfailed / 16 failed / 1 warning、0 errors**，失败节点与 548R 相同、无本批新增；
  仓库卫生 exit 0。完整日志与对账在 `evidence/548C5/`。
- 主代理另独立复跑注入二维座位的可行性探针：两个候选均 hard=0、26 网各一节点、
  0 短路、值行完整；渲染未见文字互压。探针显式注入 `x=210/top=115/row=40`，
  **只证明下游可行，不是自动生成能力**，详见 `evidence/548C5/README.md` §8。
- 下一批实现同岛二维支路座位的闭式生成规则，保持功能岛、文字原文和 near 约束；
  不默认折行、拆岛、放宽 near 或照抄探针坐标。B3/①仍独立待裁，547G 继续暂停。
- 执行偏差：实现者一次生产多行编辑使用 Python 字符串替换，一次新测试重构使用整文件
  Write，均不符合约定编辑通道；主代理已复核生产恢复哈希与最终测试内容，记为流程偏差，
  不作为后续通用做法。

## 8. 548C6：同岛二维支路座位生成（离线三关通过；548C6R见§9）

岳批准设定持续目标推进自动绘制线。本批只关闭 548C B2 的**自动二维座位生成**；
不处理 B3、548C2①、548B 串联合同、547G、真机或发布。判据先落
`evidence/548C6/criteria.md`，开工哈希与脏树边界落 `evidence/548C6/baseline.txt`。

### 文件域与分工

- 生产只许 `src/boardwise/engines/drawcompiler.py`；永久正向/负控回归只许新增
  `tests/test_548c6_two_dimensional_seats.py`。证据 `evidence/548C6/`，临时探针
  `.tmp_548C6/`，pytest basetemp `.tmp_pt_548C6*`。
- 先由测试执行者新增 C6 测试并取得旧生产前红；另一执行域只读复核几何与后续 pass，
  两者不得改生产。主代理审过前红和方案后，再派一名实现者改上述唯一生产文件。
- C5 的 strict xfail 若因真实修复出现 XPASS(strict)，实现者才可在
  `tests/test_548c5_text_pitch.py` 摘除该标记、把测试名与过期当前行为说明改为正向；
  不许放宽原断言、删除失败历史或改其他 C5 断言。未先见 XPASS 不得动该文件。
- 不改 placement/pagecompiler/readability、旧夹具、其他测试、CLI/DSH、shared 合同或文档。
  文档与全量验收由主代理在实现复验后另行收口。执行者不派第三级子代理。

### 实现合同

- 普通单列座位已经能容纳实际文字时保持原样。只有由**真实文字盒、器件体/引脚、当前
  合法位姿和现有走廊**证明普通座位不足时，才为同一功能岛的支路生成二维座位；不得按
  B2、特定位号/网名/值文字特判，也不得默认全页重排。
- 座位须由 `_part_lines`、`_line_boxes`、`text_width/font_text_box`、`_part_box`、
  `_extent`、引脚尖端和 `_snap` 等真实度量闭式求出并落 grid。可复用既有 pass，但不得
  扫数值/权重、复活旧 rip-up 或上 CP-SAT，不得把 C5 的 `x=210/top=115/row=40`、
  探针几何指纹或任何人工坐标抄进生产。
- 保持 chain/locked 件、功能岛、每个支路自己的 anchor/net、成对/同类支路和声明的
  same-row/same-column 关系。必须核对 `_share_one_bay`、`_align_branch_lanes` 及后续
  pass 后的最终座位；只在中间包装里成立不算完成。若需要调整调用顺序，先证明旧页面
  零移动且声明关系不被撤销。
- 不折行、缩字、隐藏/缩写文字，不改字号/位号与值分侧，不拆岛/删件/并网，不放宽
  `near_limit`、页框、TEXT 闸、软硬闸或既有拒绝，不新增规格字段或 CLI。
- 同 host pin 重复 shunt 仍走 543E2 的独立座位/具名拒绝；横向或页框空间不足、near
  超限仍须结构化拒绝，绝不以重叠、越界、跨网短接或丢文字换 `ok=True`。

### 前红、回归与出口

1. 新测试从内联 547A 夹具生成 B2，不读取 ignored evidence、不指定元件坐标。旧生产必须
   先复现 0 候选；修复后至少 1 候选，所有候选 hard=0，独立重推 26 网各一节点、
   0 短路、0 未放置，10 件位号与值行原文完整。
2. 新增或复用负控钉住：同 pad 重复 shunt、same-row/pair 不被二维分配撤销、横向/页框
   空间不足仍拒绝、near 超限仍拒绝。547A 与 B1 指纹不变，CH34 pinned 逐字节不变。
3. 聚焦至少覆盖 C6、C3 **5 passed / 1 xfailed**、C4 **4 passed**、547A、543E2、
   548A 四负控 **74 passed / 2 skipped**。C5 修复前为 2 passed / 1 xfailed；真实
   XPASS 后摘标应变为 **3 passed**，不得把最终读数仍写成预期失败。
4. 实现者交前红、设计公式/触发条件、最终座位来源、聚焦读数、SHA-256 与剩余边界；
   主代理独立关闭新逻辑令 B2 变红，cp 恢复核对哈希，再亲看最终生产候选渲染并逐区
   视觉验收。机器闸、独立电气和视觉分别记录。
5. 主代理随后跑完整四线与卫生检查，和 548C5 的 16 条既有失败逐节点对账；不伪称全绿。
   未跑真机、未落画布，不记自动整页，不提前关闭 548D/E。

### 停止线

每名执行者最多 40 步或 30 分钟。连续两次只移动冲突、无新证据即停；若闭式二维生成
不能同时满足上述约束，保留结构化失败证书并交主代理，不扩到 B3、548B、真机，不用
人工微调或注入探针冒充 automatic。所有增量编辑必须先 Read 再 Edit；禁止 Python
字符串替换、sed 或整文件 Write 绕过，变异恢复只用 cp 备份并核对 SHA-256。

### 548C6 主代理复验（离线三关通过；548C6R见§9）

- **生产能力已落**：`drawcompiler.py` 最终 SHA-256
  `25abdddfe45062de4d28c868627a6e26841c42cd4acf78e34ce80d2ff34808e0`。
  单模块救援轮在普通/119 加宽轮无候选后、201B 前运行；`_seat_branch_stack` 由真实文字/
  器件/引脚度量计算 line 轴座位，绕针后重核 near、重叠与文字自由侧，声明 same-line、
  service、shared-pad 与 bay 所有组不动。救援轮使用独立 `CompileResult`，避免既有构造
  variant 计数翻倍。C5 注入坐标未进入生产。
- **编译与独立电气**：B2 自动产出 1 候选，几何
  `814ed66f3be35e2c5ce157c83b499b980cdd849ff7668f07fa6f82d42924db04`；
  主代理直接调用生产 `dc.compile` 复核 hard=0、26 网各一节点、0 未绘制、0 短路、
  10 件位号/值行原文完整。唯一 grammar finding 是既有 module-level 3V3 无旗问题，
  由 548C2①/B3 继续挂账，本批未把它写成已解决。
- **回归**：主代理 12 文件聚焦 **120 passed / 2 skipped / 1 xfailed**；JUnit 分文件确认
  四负控 **74 passed / 2 skipped**、C6 **12 passed**、C5 **3 passed**、C4 **4 passed**、
  C3 **5 passed / 1 xfailed**。CH340 `6ed82091…` / CH343 `2ec6b700…` 均 MATCH，
  `allMatch=true`。变异恢复后 C6+C5 再跑 **15 passed**。
- **独立变异**：关闭救援轮 → B2 正向红（原文压 D2）；去掉新座位绕针 → 外来引脚负控红，
  点名 S4 导线仍穿针。两次均 cp 恢复且 `cmp=0`，生产哈希保持上述值。
- **视觉**：主代理亲看最终生产 SVG/PNG 及 2×局部，MCU 左侧去耦/BOOT0/蜂鸣器、右侧两灯/
  四键归属清楚；两灯与四键分别同向等距，支路只有一次必要正交拐弯，共享回流与源网表一致，
  名字与长值行可读、无互压。证据 `evidence/548C6/b2-main-candidate-0*.svg/.png`。
- **边界**：多岛页面不启用本轮；117① tail 缺口由 §9 的 548C6R 关闭，`_rung_reproduces`
  特殊截断形状仍无专项夹具。B3/548C2① 已由岳裁为禁网络标签、旗标入库（C7/C7A/C7B 三次未通过、另批），548B 合同已由 B1–B3 落地，548D/E、真机与 547G 不因此
  关闭。修复前完整四线已读完，修复后第二轮全量见 §9；详细证据 `evidence/548C6/`。

## 9. 548C6R：绕针后的 leg+tail 最终复核（已通过）

C6 只读 tail 审计发现一个真实缺口，故 C6 暂不记最终收口：`_dodge_foreign_pins` 的
bounded walk 在“远离 owner”与 trail 外推同向时清不掉 tail 远端外来针，耗尽仍返回 root；
C6 随后只查 near/盒/文字，会接受跨网针重合。主代理独立复现
`C1.2/R1.2 (GND) × S2.2/S4.2 (3V3)`，见 `evidence/548C6/tail-main.log`、
`evidence/548C6/tail-review.md`。判据先落 `evidence/548C6R/criteria.md`。

- **文件域**：生产仅 `drawcompiler.py`，永久回归仅 `tests/test_548c6_two_dimensional_seats.py`；
  证据 `evidence/548C6R/`，临时 `.tmp_548C6R/`，basetemp `.tmp_pt_548C6R*`。不得改
  其他调用者合同、GAP/near/page/文字闸、fixtures、CLI/DSH 或文档。
- **前红**：新增真实 tail 测试，从 ladder origins 单次调用生产 `_seat_branch_stack`，现状必须
  因“六件落座且跨网针重合”而红；合法 leg 对照继续绕开，D1/D2 同网对照不得冒充跨网正例。
- **修复**：抽用 `_dodge_foreign_pins` 自己使用的外来针判定，在二维 root dodge 后复核
  anchor→root 与 root→other-pin；同网/自身脚排除、shared/other local 差值与 `_on_polyline`
  必须用同一把尺。任一成员 leg/trail 仍有 foreign pin 即整组回退，不留半组，不扫 GAP，
  不把 dodge 改成其他调用者也要接收的新返回类型。
- **出口**：C6 增至 **13 passed**；正常 B2 候选/几何 `814ed66f…`、hard=0、26 网、0 短路、
  全文与 CH34 pinned 不变，C5/C4/C3、四负控不回退。主代理独立去掉最终复核时 tail 测试
  必须红，cp 恢复核对哈希后复绿；最终生产编译/渲染仍需复核。
- **全量**：修复前第一轮完整 pytest 已读完：**10037 passed / 25 skipped / 1 xfailed /
  16 failed / 1 warning、0 errors**，与 548R 新增失败/错误均 0。修复后只允许再跑一轮
  完整 pytest并逐节点对账；执行者只跑聚焦，完整四线由主代理收口。
- **停止线**：执行者最多 40 步/30 分钟，不派第三级代理，不做 git/真机/daemon/删除。
  正常 B2 或合法 leg 控制若因最终复核失败，停止交几何证据，不删用例、不扫参数。增量修改
  先 Read 再 Edit，禁 Python 替换/sed/整文件 Write，恢复只用 cp 并核 SHA-256。

### 548C6R 主代理复验（已通过）

- 新 tail 永久测试在旧生产 **1 failed / 12 deselected**，红因为接受的座位保留
  `C1.2(GND) × S2.2(3V3)` 跨网针点；生产抽出 `_foreign_pins_on_run`，dodge 后逐件复核
  leg+tail，残留即整组回退。最终生产 SHA-256
  `5d7c931cfa4d002273c984bee5b4759efd2431cea756875664b155e0f79fc703`。
- 修后 S2/S4 的 C1/R1 tail 场景全部 `taken=0` 且回 ladder，跨网重合 `{}`；合法 leg 仍六件
  落座且绕开。主代理独立去掉最终复核，tail 测试红，cp 恢复 `cmp=0`。
- 主代理 12 文件聚焦 **121 passed / 2 skipped / 1 xfailed**，C6 **13 passed**、四负控
  **74 passed / 2 skipped**。B2 仍为 1 候选 `814ed66f…`、hard=0、26 网、0 短路、全文完整，
  CH34 pinned MATCH；最终 2× 渲染经主代理复看，与修复前一致。
- 最终完整 pytest **10038 passed / 25 skipped / 1 xfailed / 16 failed / 1 warning、
  0 errors**，与548R及修复前第一轮新增失败/错误均0；connector **576 passed + typecheck**、
  DSH **137 passed / 1 skipped + typecheck/build**、Rust **111 passed / 4 ignored + fmt/clippy**。
  文档声明钉与仓库卫生通过，不伪称全绿。证据 `evidence/548C6R/`。

## 10. 548C7：库内旗标补全拆分网陈述（派单）

岳已裁定：548C2①/B3 **不允许网络标签，可以把旗标收入库中**。本批只验证
`PWR-GND`/`PWR-3V3` 入库后的既有模块拆分、E2/E3 页面和 B3，不引入 CBB 导入器，
不处理 548B，不跑真机或落画布。判据 `evidence/548C7/criteria.md`。

- 先用测试副本注入实测旗形族，确认生产 `dc.compile`/`pc.compile_page` 是否已能工作；
  能则生产零改动，确有结构缺口才只改 `drawcompiler.py`。禁止恢复网络标签或跨体母线。
- 新测试 `tests/test_548c7_library_flags.py`；C3 仅限原 strict xfail/对应库场景。不得全局改
  547A/B1/B2 默认测试书，旧 pinned 必须零移动。`PWR-3V3` 离线别名不等于宿主标定，
  本批不得宣称真机可用。
- 出口：radius=100 的 GND 每簇本地旗且一个节点、BZ1.2 不悬空；E2/E3 hard=0、全网 sameNode、
  0短路；B3 26网、全文完整；地/电源无网络标签。无旗库仍给具体拒绝。C3 只有实测 XPASS
  才能摘标并保留无旗负控，目标6 passed；C6 13、C5 3、C4 4、四负控74/2不回退。
- 主代理负责关键 diff、变异、逐岛视觉、完整四线和卫生。执行者最多40步/30分钟，不派第三级
  代理，不做git/删除/真机。若旗标不足，交真实缺口，不扫参数、不改标签兜底。

## 11. 548C7A：无预留座位时补走 rail 旗标候选梯级（派单）

主审纠正 C7 初报：`_rail_flag` 已重放预留候选，真正缺口是 **seat 为空时只试首选脚**，
没有继续尝试其余未预留脚。既有 `_rail_flag_room_failure` 已承诺走其它 pad，实现与此不符。
判据 `evidence/548C7A/criteria.md`。

- 仅在 `_rail_flag` 的 `seat is None` 回退里，按 `_flag_seat_pins` 的真实页面顺序逐个调用
  `_rail_flag_seat`，首选脚仍第一、其余 nearest-first，第一处合法即停，全部失败才给原拒因。
  不改预留/per-pin 逻辑、簇归属、GAP/near/page/文字闸或网络标签。
- 先用内存回退证明首选 U1.VSSA 失败而其余脚合法，再改生产；记录实际脚位。生产仅该文件，
  C7测试与C3原xfail场景限域。不得每脚一面旗、跨簇挂旗或移动pinned几何。
- 出口同 C7：每簇本地旗、E2/E3 hard0、B3 26网全文、无地电源标签、C3真实XPASS后6 passed。
  主代理移除回退必须恢复旧拒绝并cp复绿；最终逐簇视觉、完整四线与卫生，不跑真机。
- 执行者最多40步/30分钟，不派第三级代理，不做git/删除。若改变per-pin数量或移动旧图即停。

## 12. 548C7B：启用既有统一旗标聚簇路径（派单）

C7A 又证明其回退在当前场景不可达。真实堵点提前到布线：547A 只有 `serviceLayout`，
没有 `textPlacement: native-attr`，所以高扇出3V3走每脚旗并挤死GND主干。现有
`_flag_grouping` 已支持地与电源统一按功能/终点路径成簇，本批只在测试规格中显式补齐这个
既有开关与库内旗标，不改 `_expression_style`、不指定座位。判据 `evidence/548C7B/criteria.md`。

- 唯一输入变化：测试场景加 `textPlacement: native-attr` + PWR-GND/PWR-3V3；原547A/B1/B2
  规格、默认测试书、模块/电气/坐标不改。优先生产零改动；统一路径自身若有实证缺陷才限改
  `drawcompiler.py`，禁止回退每脚旗、网络标签或C7A不可达分支。
- 出口同前：每簇本地旗、E2/E3 hard0、B3 26网全文、无地电源标签、C3实测XPASS后6 passed。
  native-attr 的文字必须单独验收，不裁字/压线；3V3宿主未标定，不跑真机。
- 主代理负责diff、变异、逐岛视觉、完整四线与卫生。执行者最多40步/30分钟，若仍失败交真实
  拒因，不再换方向凑成果，不做git/删除/第三级代理。

### 548C7/C7A/C7B 主审结论（未通过，停止连续换方向）

- C7：只补库条目，GND降级每脚旗后在U1.VSSA拒；生产零改动。C7A：证明 `_rail_flag`
  的候选重放存在，拟修回退在当前场景不可达；生产零改动。C7B：启用统一聚簇后，出现
  单脚簇无旗位与预留旗盒被导线穿过，仍无候选；生产零改动。主代理独立负证据 **7 passed**。
- 三条路线均未达到每簇本地旗/E2/E3/B3出口，C3 strict xfail未XPASS且未摘。真缺口保留为
  **聚簇与预留/布线契约**，不再连续换方向凑成果；后续须另写最小失败证书和派单。
  证据 `evidence/548C7/`、`548C7A/`、`548C7B/`。

## 13. 548B1：seriesBranches 解析、封闭校验与默认关闭（派单）

岳已批准548B评审清单全部按推荐。本批只实现数据合同，**不做跨文档V1–V8、不改
drawcompiler、不自动识别、不生成几何**。判据 `evidence/548B1/criteria.md`。

- 生产仅 `core/presentationspec.py`；新测试 `tests/test_548b_series_branches.py`。
  新增冻结 `SeriesBranch`（`id/from_net/to_net/parts/middle_net`）与可选 `series_branches`；
  JSON每条五键 `id/from/to/parts/middleNet`，parts恰好两个不同件，id唯一、完整声明去重，
  无数字/provenance/module/note/第六键，userLocks仍是唯一坐标入口。
- 不写=不读不写出；`[]`与不写等价且规范JSON无此键。既有摘要 `50b112…`、specVersion、CLI、
  旧几何与CH34 pinned不变。不得自动识别同形状两件串联。
- 负例逐项具名：未知键/缺字段/类型/空id/parts长度或重复件/重复id/重复完整声明/数字与坐标。
  解析/序列化与既有draw消费者在未声明时行为不变，跑053A/053B邻域、547A与owner/layer守卫。
- 主代理做非法parts与空数组等价变异、完整四线与卫生。执行者最多40步/30分钟，若需要编译
  消费才能证明则停止交548B2，不夹带。证据 `evidence/548B1/`，临时 `.tmp_548B1/`。

### 548B1 主代理复验（数据合同通过，完整四线已跑）

- `SeriesBranch` 与 `seriesBranches` 已落，生产仅 `core/presentationspec.py`，SHA-256
  `2ce3bd4290ef3c15e56df1dfad0bcbfc65917ed11f2e6d2129bbcdac535abbb0`。
  新测试 **41 passed**；主代理13文件聚焦 **369 passed / 2 skipped**，既有摘要 `50b112…`
  与CH34 pinned逐字节不变。未声明/空数组不写键，旧规格不自动识别。
- 主代理两项变异：放开parts长度 → **3 failed / 38 passed**；空数组也序列化 →
  **3 failed / 38 passed**。均cp恢复且字节一致，恢复后 **41 passed**。
- **完整四线（2026-11-08 已跑）**：pytest **10086 passed / 25 skipped / 1 xfailed /
  16 failed / 1 warning、0 errors**；16 条均非本批新红（12 条既有货架/分类漂移、2 条既有
  115/116、2 条 Windows 环境）。connector **576 passed + typecheck**、DSH **137 passed /
  1 skipped + typecheck/build**、Rust **111 passed / 4 ignored + fmt/clippy**。日志
  `evidence/548B1/full-pytest.log`、`connector.log`、`dsh.log`、`rust.log`。不称全绿。
- 本批没有跨文档V1–V8、provenance派生、几何或真机。548B2第一件事是让页面切片携带
  `series_branches`，再由同时持有CircuitSpec的消费者校验并构造串联；不得把schema通过
  写成548B完成。

## 14. 548B2：seriesBranches 跨文档校验与页面切片携带（派单）

548B1 数据合同已通过。本批只做 V1–V8 电气/归属校验与两个真实消费者接入；
**串联几何另批548B3**。判据 `evidence/548B2/criteria.md`。

- 统一 `drawcompiler.validate_series_branches(...)`，standalone `dc.compile` 与
  `pc.compile_page` 都在完整两份文档上先校验再进几何。页面切片只携带同模块两件；
  跨模块/无模块归属必须先由V7具名拒绝，不得静默吞掉。
- V1事实存在、V2两脚两网、V3声明顺序、V4中间节点私有、V5端点互异、V6宿主唯一、
  V7共同模块唯一、V8一件一支路逐项实现；只用既有四类拒因，失败在几何之前无候选/页。
- 高边与低边LED正例均按阅读方向，不按电流重排；provenance可按被引用事实最弱档派生，
  但不写成工程师确认。未声明/[]的旧几何、plan JSON、CLI/DSH与CH34 pinned不变。
- 新测试 `tests/test_548b_series_validation.py`；生产仅 `drawcompiler.py`、`pagecompiler.py`。
  不改PresentationSpec/schema/CircuitSpec/CLI/DSH/旧fixtures。每条V1–V8及两个消费者都有
  正反例，548B1/053邻域/547A/owner/layer守卫不回退。
- 主代理至少两处独立变异并cp恢复，完整四线与卫生。执行者最多40步/30分钟，若需要改几何
  才能通过则停止交548B3，不夹带。证据 `evidence/548B2/`，临时 `.tmp_548B2/`。

### 548B2 主代理复验（校验通过、不做几何；完整四线已跑）

- `validate_series_branches` 已在 `dc.compile` 与 `pc.compile_page` 的完整文档几何前接入，
  V1–V8逐项具名；`_module_view` 只携带同模块两件，跨模块由V7先拒，不再静默吞掉。
  生产hash：`drawcompiler.py af7ccce9…`、`pagecompiler.py 98b14d39…`。
- 前红 **24 failed / 2 passed** → **26 passed**，测试未改一字。主代理15文件聚焦
  **423 passed / 2 skipped**；548B1 41、053邻域、547A与CH34 pinned均不回退。
- V6变异 → **2 failed**；切片丢弃声明变异 → **1 failed / 1 passed**。均cp恢复且字节一致，
  恢复后 **26 passed**。
- **完整四线（2026-11-08 已跑）**：pytest **10112 passed / 25 skipped / 1 xfailed /
  16 failed / 1 warning、0 errors**；16 条均为既有（12 条货架/分类漂移、2 条 115/116、
  2 条 Windows 环境）。connector **576 passed + typecheck**、DSH **137 passed / 1 skipped +
  typecheck/build**、Rust **111 passed / 4 ignored + fmt/clippy**，日志 `evidence/548B2/`。
  不称全绿。
- 本批没有串联几何或provenance派生（几何是548B3，另行验收），不称548B完成。

## 15. 548B3：seriesBranches 决定串联几何与独立语法检查（派单）

548B3 探针证明：合法声明可出 hard=0 图，但声明不改变几何，R→LED中间网折返；
低边好candidate来自后topology。前红测试 **10 failed / 4 passed**，只调排序不能过。
判据 `evidence/548B3/criteria.md`。

- 在绑定/准备阶段把每条声明变成两件的结构化 `RelativeConstraint`，standalone与独立
  `check_grammar` 同见；方向由axis/progress/真实引脚侧决定，不写死左→右或按电流。
  几何按宿主→parts[0]→middleNet→parts[1]→终端构造，不得只调分、用坐标或reference-replay。
- 所有返回候选：六点在链轴单调且中途无回退；middleNet至多2段且≤2×本图中心距，不得只挂
  两端网名；hard0、图分区==电路、0短路/0分裂/0未放置、每件一次、位号值行完整；
  声明版首选画面不同于不声明版。真需信号网标签须记label_fallbacks并另开判据。
- 生产仅 `drawcompiler.py`，新测试 `tests/test_548b_series_geometry.py`；pagecompiler已携带。
  不改PresentationSpec/schema/CircuitSpec/CLI/DSH/旧fixtures。未声明/[]的旧几何、旧拒绝、
  plan JSON与CH34 pinned不变，不自动识别。
- 主代理至少两处变异（关系注入、方向/短链），cp恢复后复绿；最终SVG/PNG逐岛视觉、完整四线
  与卫生，不跑真机。执行者最多40步/30分钟，若关系不足可在该文件内最小构造座位，但不得扫
  数值、放宽硬闸、删候选或改测试；仍失败则交真实拒因。

### 548B3 主代理复验（离线通过；完整四线已跑，16 failed 均既有）

**实现**：生产只改 `src/boardwise/engines/drawcompiler.py`，最终 SHA-256
`d9ba64ab79486dfa61ac60c8c04f034aecf331642468b95533b6a7b634691a3d`（548B3-R 后最终为
`300157d57e49decd24931e8ba6f5db66f8d4c8025259b8763e89897ba6d691ee`，见 §17）。每条声明在绑定/准备
阶段变成两件（`parts[0]`/`parts[1]`）的 `RelativeConstraint`；`compile` 与独立
`check_grammar` 共用 `_with_series_arms`，机器闸与语法检查读同一组关系。座位按文档既有
`axis`/`progress` 与真实引脚决定，几何按 宿主 → parts[0] → middleNet → parts[1] → 终端
构造；pitch 取原布局自己的中心距，不新增数值档；非 GND 终端轨优先在臂尾真实脚挂旗。
未声明或 `[]` 的文档规格与几何逐字节不变，同形状两件不自动识别。`pagecompiler.py` 本批
未改（548B2 已携带切片）。

**测试**：`tests/test_548b_series_geometry.py`，SHA-256
`10529f1c31f1807dc803c8be8af4cd0d51459f8912ed4e9a8de4f92b9c999a8f`；前红
**10 failed / 4 passed** → **14 passed**。主代理聚焦（B1+B2+B3+053A/B+547A）
**232 passed / 2 skipped**；第一轮全量暴露新红后主代理另跑
`tests/test_520b2_flag_seat_ladder.py` + 本批测试 **21 passed**
（`evidence/548B3/regression-520b2.log`），执行者扩大聚焦 **239 passed / 2 skipped**
（执行者读数，不是主代理读数）。

**第一轮完整 pytest（2026-11-08）**：**18 failed / 10124 passed / 25 skipped / 1 xfailed /
1 warning、0 errors**（`evidence/548B3/full-pytest.log`）。既有 16 条之外，**2 条本批新红**是
`test_520b2_flag_seat_ladder.py::test_a_rail_ladder_reaches_every_pad_of_its_own_net_nearest_first`
与 `::test_a_rail_with_no_chain_part_still_walks_its_pads`：轻量 `SimpleNamespace` 规格没有
`series_branches` 属性，`_arm_terminal_members` 抛 `AttributeError`。修法只在
`drawcompiler.py` 用 `getattr(ctx.presentation, "series_branches", ())` 做最小兼容，**测试
未改**；修后两文件 **21 passed**。

**第二轮最终完整 pytest（2026-11-08，1441.23s）**：**16 failed / 10126 passed / 25 skipped /
1 xfailed / 1 warning、0 errors**（`evidence/548B3/full-pytest-final.log`）。与 548B2 基线做
结构化比较（`evidence/548B3/full-compare.log`）：baseline=16、final=16、**added=[]、removed=[]**；
16 条全是既有（12 条货架/分类漂移、2 条 115/116、2 条 Windows 环境），本批新增 0。不称全绿。

**几何读数**：高边首选 `9917b0b3cda9…`、低边 `5eea1a442ce7…`，各 3 候选；六点沿链轴单调，
`middleNet` 一段 10 单位。CH340 pinned `6ed82091e2c8…`、CH343 首选 page `2ec6b700d997…`
均 MATCH，`allMatch=true` 且 plan JSON matches（未声明路径零移动）。

**变异（主代理亲做，当时全部 cp 恢复并核对 sha256 到 `2cc92fc0…`）**：① 关系注入置空 →
**2 failed / 12 passed**（⑤a×2）；② 座位方向反转 → **2 failed / 12 passed**（高边①、
低边⑤b）；③ 仅删 `check_grammar` 侧注入时最初仍是 **14 passed**，暴露 ⑤b 的覆盖洞——
随后**只强化测试**（每个 case 保留好候选不报，并从同电路未声明候选选真实折返负例，用
声明版 presentation 检查且必须报），强化后 14 passed，再重做③ → **2 failed / 12 passed**
（⑤b×2）。这是补覆盖，不是为消红改测试。**变异历史止于 `2cc92fc0…`**：之后才做上面的
520b2 兼容修复，最终生产 hash 因此是 `d9ba64ab…`；恢复点不追改成新 hash。

**视觉自审（主代理亲看 `evidence/548B3/series-arm-{high-side,low-side}.{svg,png}`）**：
两件均成竖直直链，R 在 LED 之前（按声明阅读序），中点一段短线，终端旗挂在臂尾，位号与值行
完整；低边长 L 线属于 3V3 既有干线，不是 `middleNet` 折返。

**其他三线**（日志 `evidence/548B3/`）：connector **576 passed + typecheck**
（`connector.log`）、DSH **137 passed / 1 skipped + typecheck/build**（`dsh.log`）、
Rust **111 passed / 4 ignored + fmt/clippy**（`rust.log`）。

**边界**：本批不跑真机、不落画布、不宣称 lint 宿主 DRC 通过或自动整页；548C7 的聚簇/预留/
布线缺口另批，548D 依赖自动整页复验、548E 真机未做，547G 继续暂停。verification 记录见
`evidence/548B3/verification.md`。

**完整四线已跑（不称全绿）**：最终 pytest **16 failed / 10126 passed / 25 skipped / 1 xfailed /
1 warning、0 errors**（1441.23s，`evidence/548B3/full-pytest-final.log`）；与 548B2 基线结构化
比较（`evidence/548B3/full-compare.log`）baseline=16、final=16、**added=[]、removed=[]**，
16 条全既有（12 条货架/分类漂移、2 条 115/116、2 条 Windows 环境）。connector
**576 passed + typecheck**、DSH **137 passed / 1 skipped + typecheck/build**、Rust
**111 passed / 4 ignored + fmt/clippy** 本批均实际通过。第一轮 18 failed/10124 passed 与
520b2 两条新红→21 passed 的修复记录保留在上一段。

## 16. 548D0：547 自动整页依赖复验（诊断已完成；整页未开始实施）

548A/B/C 的已完成能力接入后，先复验冻结的30件/31网/5NC/8岛自动规格，不直接宣称548D。
三份547A输入已核对与历史sha256一致，原文件只读；判据与四格定义见`evidence/548D/criteria.md`。

- 仅比较`baseline`、`auto`、`series`、`auto+series`四格；两条声明为
  `LED1_K→R2→LED1_A→D1→GND`与`LED2_K→R3→LED2_A→D2→GND`。
  整页与MCU最小岛分域派单，派生规格只放`.tmp_548D/`，证据放`evidence/548D/`。
- 本批不改生产/测试/原规格，不扫参数、不填坐标、不删件并网藏字，不跑真机/git/全量。
  每格保留ok/候选数/完整失败/首败模块与复现命令；有候选才进入独立逐脚/NC与主代理视觉。
- 出口只是确认下一处最小通用缺口。0候选是合法探针结果，不记548D自动整页完成；
  不用547G辅助图或LED直连诊断替代。548E不得提前，547G继续暂停。
- **探针结果（诊断，不构成依赖齐备）**：`series` 让 MCU 0→1 候选、8 模块过闸，但模块候选
  仍报缺 `PWR-3V3` 旗（库内 `PWR-+3V3` 与查找串 `PWR-3V3` 不一致）；`LED2_K` 有 850 单位
  9 点回环与交叉；**整页 0 候选**，`series` 最小 1766×935.5、`auto+series` 最小 1832×930.5，
  均超 1170×825。无整页候选 ⇒ 逐脚/NC 与逐岛视觉未跑，该候选不得写成 hard=0 可交付。

## 17. 548A-R / 548B3-R：验收缺口复审（两项已关闭；完整四线已跑）

**结论（2026-11-08，A-R/B3-R 完成后）**：两项 P1 均已关闭，下面是当时的缺口与关闭依据。
**第二轮最终完整 pytest**：**16 failed / 10130 passed / 25 skipped / 1 xfailed / 1 warning、
0 errors**（1505.66s，`evidence/548D/full-pytest-rs.log`，JUnit `evidence/548D/full-pytest.xml`）；
与 548B3 基线经 JUnit 结构化比较（`evidence/548D/full-compare.log`）baseline=16、final=16、
errors=0、**added=[]、removed=[]**。第一轮曾为 16 failed / 10122 passed / **33 skipped**
（`full-pytest.log`）：首次额外 8 个 skip 未在第二轮复现，不虚构其节点或原因；第二轮恢复
25 skipped，新增 4 条全计入。卫生 **7 passed**（`hygiene-serial.log`）、文档钉 **40 passed**
（`doc-claims.log`），其他三线此前已通过；不称全绿。**该全量跑在 D2 实验之前**：D2/D2R 失败
实验没有另跑全量，新测试 7 个 xfail 不计入该读数（见 §18）。548D 整页仍未开始实施（§16 只是诊断）。

### P1-1 548A：完整 N≥3 支路出口 —— 已关闭

- 缺口（历史）：`tests/test_547_repeated_shunts.py:281` 只断言 `D1`/`D2`/`BZ1` 已放置；独立
  分区/短路断言集中在四个 `KEY`，两灯与蜂鸣器没有逐脚验证。
- **548A-R 关闭**：新增 `test_lamps_and_buzzer…`，用独立 `derive_netlist` 对照本地
  `CircuitSpec` 全部分区，`D1`/`D2`/`BZ1` 逐脚、七信号七节点、0 短路/分裂/未放置。测试文件
  sha256 `36d22e6074643caf12f7e061125dce643c10c3dfdd85a913fee0ee7c63f8cab9`；本文件
  **3 passed**、547 邻域 **24 passed**、四负控 **74 passed / 2 skipped**。主代理变异：把 LED1
  期望宿主由 PA3 改为 PA4 → **1 failed / 2 passed**，cp 恢复后 hash 一致。
- 执行偏差（如实记录）：执行者首次 `Edit` 前漏备份，后用会话原文重建改前文件；细节
  `evidence/548D/a-r/a-r-coverage.md`。
- 口径：**完整 N≥3 面板支路出口通过，仅限已测电路族**，不外推为任意电路的泛化能力。

### P1-2 548B3：负例与完整链 —— 已关闭（合同为「不可落座 → 具名拒绝」）

- 缺口（历史）：`_seat_series_arms` 在 first/second pose 为 `None`、缺 pin、无 host、碰撞等
  路径 `continue` 保留旧布局，没有失败语义。
- **548B3-R 关闭**：上述路径改为 `layout-unsat` **具名拒绝**，build variant 立即返回，不再
  `continue` 保留旧布局。新增 `tests/test_548b_series_failures.py` 3 条（无合法 pose、座位
  冲突、任何候选不得旧折返），前红 **3 failed** → **3 passed**。生产 sha256
  `300157d57e49decd24931e8ba6f5db66f8d4c8025259b8763e89897ba6d691ee`，新测试
  `2c3646f6aa0f865589516067f9f163d8ae8c8daa021fb9a9e537b51c8ac87c6b`。
- 主代理组合（A-R+B3-R+B3+520b2）**27 passed**（`evidence/548D/main-focus.log`），恢复后
  **27 passed**（`restored.log`）；pose 拒绝失效 → **1 failed / 2 passed**、冲突拒绝失效 →
  **1 failed / 2 passed**，均 cp 恢复 `300157…`。CH34 `allMatch=true`（CH340 `6ed82091…`、
  CH343 `2ec6b700…`），高边/低边仍各 3 候选、无新增拒绝。
- 口径：**正例 + 不可落座负例通过，「禁止静默回退」已落地**。合同选择的是「不可落座 variant
  具名拒绝」；**checker 的完整六点几何检查本轮未做**，不得宣称 checker 六点能力。
- 执行者邻域 448 passed / 2 skipped（执行者读数，非主代理）。

### 顺序

548A-R 与 548B3-R 已关闭；548D 整页仍未开始实施。§16 的B3-R前MCU候选已由主代理视觉判废
（标签堆叠、回环/交叉、缺电源旗），不得交付。548E真机、547G继续暂停。

## 18. 548D1/D2/D2R：旗名非首因；串联座位预留两版均未通过（生产净零改动，已停第三轮）

- **548D1已完成（纯派生库探针）**：保留`PWR-+3V3`并新增几何等价`PWR-3V3`后查表可解析，
  但当前B3-R生产在原库/别名库下均为MCU 0候选，旗标阶段根本未到达。当前首败不是旗名：
  base轮R3压S1、topology轮R2压S2，其余为既有left-of/near拒绝。证据
  `evidence/548D/power-flag/report.md`。不得把别名探针写成缺旗已修复。
- **548D2 / D2R 均未通过（生产净零改动）**：两次尝试都未进入整页实施，也没有候选或 SVG
  可交付。**D2 第一版**让开 `S1` 但随后 `D1×D2`，且既有 B3 额外 6 红，已撤回。**D2R**
  证明不同 pitch 是旧回归原因，统一座位方程后单臂邻域 **91 passed**，但 MCU 仍 **0 候选**：
  base 兄弟 `S1` 让开不足；topology 轮不经过 `_chain_and_shelf_layout`，导致 `D2` 压
  `D1`。按停止条件**不做第三轮**。
- 生产 `drawcompiler.py` 保持
  `300157d57e49decd24931e8ba6f5db66f8d4c8025259b8763e89897ba6d691ee`（与
  `.tmp_548D/main/drawcompiler.py.clean` 一致）。新测试 `tests/test_548d_series_reservation.py`
  保留 **7 条 strict xfail + 1 普通控制**，hash
  `347997377200889f2f5dd458f25fe3f934f903c3a7abfc5be95b67c55db5f5b7`；主代理最终组合
  **28 passed / 7 xfailed**（`evidence/548D/series-reservation2/main-restored.log`），
  **未摘任何 xfail**。
- 证据 `evidence/548D/series-reservation/outcome.md`、`series-reservation2/summary.md`。
- 下一缺口是**跨 base+topology 一致的串联座位 / 兄弟让开合同**，不是继续调数值。**548D
  暂停于跨轮串联预留，未进入整页实施**；548E 禁止，547G 暂停。**时间边界**：§17 的
  10130/25/16 全量在 D2 实验之前跑，D2 失败实验没有另跑全量，7 个 xfail 不计入该读数。

## 19. 548D3A：统一 SeriesSeatPlan 设计与集成边界（设计完成，实现未开始）

判据与完整数据流分别见 `evidence/548D/series-seat-plan-criteria.md`、
`evidence/548D/series-seat-plan.md`。本节是实现合同摘要，不得把设计状态写成能力已通过。

- 两个独立只读审计与主代理复核确认：base 在普通 rung、bays/alignment 后才由
  `_seat_series_arms` 移动两件；topology 完全不经过 `_chain_and_shelf_layout`。
  第三次事后调参禁止。新设计分 `SeriesSeatTemplate` 与 `BoundSeriesSeatPlan`，至少携带
  branch id、两件 origin/pose、reserved boxes、普通支路 yield 映射和结构化 refusal。
- pitch 从同一普通构造种子量一次并冻结；lane 以整条臂为单位。base 必须在普通支路
  数据流内消费预留；topology 必须在 seed 与每次 candidate move 后投影，宿主移动时
  整臂随动，外国件侵占预留是具名 hard violation。不得伪造 userLock、跑两次独立退火、
  调权重/near/排名或恢复旧折返。
- 现有 `PlacementInput` 没有宿主随动的串联约束，故**不能只在 drawcompiler.py 内实现**。
  先走 `tasks/shared-platform.md` §10 的 draw 内部 placement 集成锁；不因此改
  CircuitSpec/PresentationSpec/ChangePlan/CLI/DSH。若发现必须改这些公共合同，立即停批。
- 文件域第一阶段仅 `src/boardwise/engines/placement.py` 与其新窄测试；第二阶段才接
  `drawcompiler.py` 和既有 548D 合同。未声明/`[]` 必须零行为变化；测试只能在真实断言
  通过后逐条摘 strict xfail，不得删除或放宽。
- 最低出口：548D+548B3+548B3-R+520b2+548A-R 组合 **28 passed / 0 xfailed**，
  CH34 `allMatch=true`；主代理做 base 禁用、topology 禁用、错误兄弟让开三项变异并
  cp+SHA-256 恢复，再亲看 MCU 渲染。MCU 三关后才处理派生库 3V3 旗名和整页容量；
  不放大页框遮岛内缺陷。548E 真机、547G 继续暂停。

## 20. 548D3B–D3F：base MCU 通过，整页与强制 topology 未闭环（暂停交接）

- **base 单模块**：联合 lane 候选、pair-band 与真实盒分排已落地；`PWR-3V3` 缺席时
  精确使用 `PWR-+3V3`，多臂同模块 power rail 采用 wire+本地单旗。主代理五文件组合
  **35 passed / 0 xfailed**，七条 strict xfail 已全部真实通过后摘除；CH34 双 MATCH。
  当前 `drawcompiler.py` SHA-256 `6c1c44fc6df11145e2f2c63b8662bab5b45a33f5bc2d50841358653894c5cc6a`，
  `placement.py` `b94edcb3f629f3b1b4b1057600f58ec0aa0c9baf55995aa5d75593fa1f0bb11c`。
- **强制 topology 未通过**：S3 让位和 binder 档 GND 簇 4/5 无旗位；band 分排实测零移动，
  不宣称 topology 完成。**冻结整页未通过**：MCU `D1.2` 与 WiFi `J2.GND` 无旗位，
  `evidence/548D/full-page/compile.log`。pagecompiler/islandlayout 的旗名别名尚未统一。
- 主代理已亲看 LED 短直候选，但最终视觉、独立三项变异、完整四线未做。单模块既有
  42 条 out-of-page 属局部坐标，须整页 frame 验收，不得称图幅通过。548E/547G 继续暂停。
- 完整停点、哈希、FOC 只读参照与下一步见 **`evidence/548D/HANDOFF.md`**。不得恢复
  `.tmp_548D3*` 中 joint_flag、self-wall、channel-reserve 等失败实验，不提交、不真机。

## 21. 548D3F：整页 MCU/WiFi GND 旗位差异（诊断完成，WiFi 实施中）

只诊断并修复整页模块切片相对单模块测试的 GND 数据差异，不重开串联布局或整页容量实验。
单模块入口是 `tests/test_548d_series_reservation.py::_compiled`；真实整页入口是
`pagecompiler._module_view` / `_module_budget_for`。以同一冻结输入实际构造并序列化 MCU/WiFi
view，分别打印预算、profile、GND style/detached/clusters、ground domains，追踪
`drawcompiler._expressions`、`_gnd_cluster_expressions`、`_flag_groups` 与
`_lead_lane_reservations`。没有数据证据不得推测根因或把两个模块混为一例。

- 文件域仅限经证据确认的 `pagecompiler.py`、`drawcompiler.py` 及一个既有 548D 测试文件域；
  不改 `placement.py`、公共输入合同、旧 fixtures、其它 agent 文件或 `package.json`。
  只有找到明确差异才做最小生产改动，并加正向回归与缺失域/配置的 negative control。
- 不写配置时旧行为不变；不放宽既有断言、不删测试。禁止恢复 joint_flag、self-wall、
  channel-reserve，禁止增加 reach、放大页框、拆功能岛、伪造锁或调硬闸/排名。
- 本批冻结离线 SmartMedicineBox 单页；parser、`.epro2/.eprj2/.eprj3`、多板、CBB、V3/V4
  真机均未改变也未覆盖。重复 PCB 双审与分歧库串板不属于本批，不得宣称兼容完成。
  不扩 CLI/DSH，不做真机、git 写、rm 或全量测试。
- 诊断与命令日志写 `evidence/548D/full-page/gnd-diagnosis.md`，临时探针放
  `.tmp_548D3/gnd_compare/`。聚焦 pytest 使用独立 basetemp；完整整页 compile 仅在
  聚焦回归后运行一次，沿用 §20 命令。若根因不在本文件域或 25 步/25 分钟仍无新证据，
  停止并交回差异表、命令与最小下一步，不扩项。

主代理已亲跑 `probe_control.py` 复核双向因果：page MCU 加两臂通过，inline MCU 去两臂同点失败；
WiFi 有无 page ground domains 均失败。原始冻结电路/展示/库保持只读，派生展示规格
`.tmp_548D/full/presentation.series.json` 除 `seriesBranches` 两条 LED 声明外逐键相同，主代理已断言。
这是补齐既有显式电路意图，不改电气、坐标、分岛或约束；后续整页验收固定该派生规格，
并在证据中区分原冻结件与派生件，不修改 547A 原件、不自动识别串联。

### 21A. WiFi `J2.GND` 旗位饱和（一个缺口）

生产域限 `drawcompiler.py`，测试限一个新 `tests/test_548d_wifi_ground.py`；若证实必须改
placement 或其它合同即停回，不夹带。先用独立 WiFi 最小复现核对七档各件、pin/文字与旗位几何，
仅对有数据支持的通用座位缺陷做最小修复；不恢复旧失败方案、不增加 reach、不放大页框、
不拆岛、不伪造锁、不自动语义推断。默认未涉及该结构的行为不变，CH34 必须 MATCH。

测试须真实读候选几何：独立逐脚与分区、NC/短路、3V3/GND 旗标各自归支路、语法和 readability；
包括阻挡物负例，不能只断言 `ok`。聚焦后再跑一次冻结电路/库 + 已审计派生规格的整页 compile。
不真机、不 git 写、不 rm、不扩其它岛，不跑全量。证据 `evidence/548D/full-page/wifi-ground.md`，
临时 `.tmp_548D3/wifi_ground/`，25 步/25 分钟；无新证据即停并交最小剩余缺口。

首轮四种旗引线形状均失败且已 cp/hash 还原，主代理核哈希一致；见
`evidence/548D/full-page/wifi-ground.md`。此轮“去耦支路移动必须改 placement.py”只是执行者建议，
并非已证明的合同边界：base 的 `_chain_and_shelf_layout` 本就在允许文件域内。

### 21B. 去耦支路座位释放（仅验证一个结构假设）

不恢复上批旗引线变化。用真实 `_build_one_variant(placement_override=…)` 对照，仅沿 C8/C9
各自既有 branch escape/reading axis 移动格点，保持位姿、冻结电路/库与已审计派生规格不变；
记录是否同时释放 3V3/GND 合法旗位并通过全部现有闸。不是手填目标坐标，也不是验收绕过。

若一个明确、通用的支路盒/文字避让缺口被证明，可在 `_chain_and_shelf_layout` 的既有支路阶段
实现最小修复并加本批正/负例；否则零净生产改动，停止 WiFi 旗位方向，不转调参数或拓扑退火。
不改 `placement.py` / `_flag_anchor` / `_flag_pin_lead` / `_flag_pins`，不新增引线档，不扩页框。
最多 15 步/15 分钟，其余文件域、测试与交付纪律同 §21A；结果续写同一份 `wifi-ground.md`。

§21B 探针证明 C8 沿 escape 一格可出机器候选，但独立几何有 GND `(-75,35)-(-30,35)` 跨
3V3 旗引线 `(-60,40)-(-60,27.5)`，不可收。主代理在真实 `_build_one_variant` 插桩确认：
`3V3` ref=`PWR-+3V3`、style=flag；预留表有 `(-60,30)` 而无 `(-60,35)`，最终实际旗引线
到达 y=27.5。即 `_lattice_nodes` 按端点估计步数，不能代表连续引线与路由格线的交点；
缺的是实际导体登记，不是别名或新增旗形。

### 21C. 实际旗引线的连续段预留（一个漏检）

文件域仍仅 `drawcompiler.py` 与一个新 548D WiFi 测试；不改 `placement.py` 或公共合同。
最小方向是在 `_remember_lead` / 既有预留边界按**连续线段与现有格线的真实交点**登记已落定
旗引线，不移动旗锚、不引入半格车道、不改变 `_flag_anchor` 或 `_flag_pin_lead` 的选择、
不改普通导线间交叉/CROSS_COST 规则。必须区分同网共享和外国网；不覆盖外国针脚/已有预留，
不静默短路。若需要改 router.py 或其它模块，先交回证据，不夹带。

正负例须覆盖非格点终点的实际跨线拒绝、合法绕行/同网豁免、没有相关引线时旧行为，及真实 WiFi
几何的逐脚分区。先复现上例后红，再跑 074/145a/175 邻域和 CH34；即使修后 WiFi 仍无候选也须
如实报告，不能用旧跨线图充当成功。20 步/20 分钟，证据续写 `wifi-ground.md`，不真机/git/rm/全量。

主代理已抽读新函数/测试并亲跑 wifi+series+geometry+failures+flag+shunts+topology：
**43 passed / 0 xfailed**（78.47s），无 xfail。21C 已保留；它不冒充 WiFi 座位通过。

### 21D. 完整旗盒驱动的去耦让位（最后一个座位假设）

§21B 只测 C9 沿 escape 一格，未测能容纳完整旗盒的盒尺寸步数。现只补测 C9 沿其既有 escape
方向 +2/+3 格（C8不动），在当前连续引线修复后的真实 build 中核对旗位、全部机器闸及独立跨线；
不扫描大范围数值。若有合法候选，依据实际盒/文本边界形成通用最小让位，并补要求 WiFi 必须出
候选的逐脚/分区/旗位/负例；若仍失败，停止该座位方向，零净改动，不转向更大搜索。
最多8步/8分钟，仍限 §21C 文件域，不真机/git/rm/全量。

### 21E. 新前置下有限复验统一旗标聚簇

§12 的 C7B 失败含“预留旗盒被导线穿过”，与21C实测漏检同类，因此新修复改变了该次失败的前置。
仅复验既有 `_flag_grouping`：在测试的 WiFi 展示切片显式 `textPlacement=native-attr`（已有
serviceLayout），不改原始547A、不改电气/坐标/分岛、不添加手写座位或扩大 reach。它表达同组
并联去耦两端同一共旗策略，不把不同信号支路合并。

若有候选必须独立逐脚/分区、NC/短路、3V3/GND簇与本地旗、文字、连续导体交叉和SVG主审；
无候选记录真实首败与阻挡，不再回退per-pin或逐件扫坐标。只有聚簇自身的明确代码缺陷才可在
`drawcompiler.py`小修并加钉，否则保持生产现状。最多12步/12分钟，证据续写wifi-ground.md；
不真机/git/rm/全量。不能把这次复验写成C7B或整页已经通过。

## 22. 548D3G：联合旗位内部合同（设计已修订，实施未闭环）

主代理修订设计见 `evidence/548D/full-page/flag-corridor-design.md`，集成锁见
`tasks/shared-platform.md` §11。规划者初稿的“服务件禁移/最多两格”未被采纳：服务件可以在
原服务与near约束下让位，位移按真实盒必要量；该合同必须默认空、无公共输入或绝对坐标。

### 22A. placement 数据与绑定（第一批）

文件域仅 `src/boardwise/engines/placement.py` 与新增 `tests/test_548d_flag_corridor.py`，不接
生产 compile、不改 drawcompiler。实现最小 `FlagCorridorTemplate`/`BoundFlagCorridorPlan`、
尾插默认空 input/result、有限真实相对候选的联合选择、盒/引线互斥、复用series yield/refusal、
平移/mismatch。让位包括服务支路，不越过锁/host，不用第二套退火或soft分数替代hard约束。
空 tuple 不加成本、不改seed/moves/输出；两相邻脚可选不互压候选，碰撞时服务支路能按必要量
让位，锁/无合法档/服务冲突具名拒绝。不宣称 WiFi 已通过。

测试须含空等价、默认旧构造器、联合选档、服务支路正/负例、平移/漂移、旧`FlagReservation`
兼容；聚焦pytest独立basetemp，至少一处cp+SHA-256独立变异。最多30步/30分钟，若必须公共合同或
第二套搜索立即停回。证据 `evidence/548D/full-page/flag-corridor-placement.md`，临时
`.tmp_548D3/flag_corridor/`；不真机/git/rm/全量/额外线agent。

主代理抽读 binder/测试并亲跑 **20 passed**。注意现有 `place()` 只在搜索后绑定，尚未满足
topology 过程约束；`_flag_yield_keeps_relations` 只覆盖 grammar relations，不自动等价于
`serviceLayout.pinGap` 保持。这些是接入前必须补的合同缺口，不得用文字报告掩盖。

### 22B. 真实候选、两个消费者与 WiFi（第二批）

文件域限 `placement.py`、`drawcompiler.py` 和 `tests/test_548d_flag_corridor.py`，同属 §11 集成锁。
候选从既有 `_flag_anchor` 的方向/梯级与 `_flag_box` 产生，只有同宿主相邻、实际需要逐脚旗的
脚头档互压才形成 corridor；无该结构、CH34 与未声明输入保持原行为。相对几何须正确随 pose
旋转/镜像，不能拿一种姿态套所有候选。yield 只允许普通 branch（含服务件），不动其它 host/core/
锁；服务件 pinGap 必须在最终实际 pin 点验证，不能只靠 near。

base 在普通支路构造后绑定并让位，topology 必须在 seed 后绑定、候选移动时重投影，而非结束后
补一个计划；两处结果逐字段核对。最终 `_lead_lane_reservations`/`_flag_pins_seats` 回放同一
candidate，漂移具名拒绝，不再静默回普通梯级。原 series/其它 flag nets 不改语义。

WiFi 必须出真实候选，独立逐脚/分区、NC/短路、连续导体交叉、文字/图框、check_grammar/readability
及SVG全过才称通过。若仍无候选，保留真实拒绝，不扩reach/页框/形状族/拓扑退火，不交“成败皆可”
测试。跑 corridor+548D相关+CH34；必要时修上一批 binder 但保持20条原断言。最多35步/30分钟，
证据 `evidence/548D/full-page/flag-corridor-integration.md`，临时同目录。不真机/git/rm/全量。

22B 停止时只新增 `ServicePinGap` 和3条测试（23 passed），未接 drawcompiler；pinGap 已有真实点守卫。
其“联合后一次回放=第二套搜索”过宽：禁止的是另起退火/随机重试，**不是**既有 series 同款的
确定性 plan → `placement_override` → 同一 `_build_one_variant` 全闸回放。该路径不得绕过任何检查。

### 22C. 联合旗位的确定性单次回放

先在不移动任何器件的 `_lead_lane_reservations` 阶段，对同宿主相邻逐脚旗用**现有** `_flag_anchor`
候选做联合选择（备选而非首个合格档），写 `router.flag_seats` 并在最终严格回放。若已有合法
组合，placement 不需要出手。若仍没有，才以现有 binder（含service_gaps）求 yield，生成确定的
`_Placement` 和 bound plan，用同一 `_build_one_variant(placement_override=…)` 重走全部文本、
预留、布线与闸一次；不能循环试错、另起退火或静默改变计划。

`_Placement.flag_corridors=()` 尾插；有计划时 reservation 只取绑定seat，冲突/漂移必须拒绝，
不能退回另一梯级。候选考虑真实文本/器件，服务支路移动前后都必须满足pinGap；成员pin/姿态保持。
若真实 WiFi 有候选，补严格逐脚/分区/NC/短路/连续导体/文字图框/grammar/readability/SVG；
若无候选，记录最小联合失败，停止不扩shape/page/reach。topology 的同源数据可在本批窄测试验证，
不得借WiFi base偶然成功宣称topology MCU已通过。文件域仍 §22B，最多25步/25分钟，证据续写
flag-corridor-integration.md。不真机/git/rm/全量/其它方向。

22C 证明前置漏了一层：预留阶段 `3V3 style=flag`，但 `GND style=wire`，所以同宿主的两脚
根本没一起进入 `_lead_lane_reservations`。联合实现已整体撤回并核hash；不能称WiFi无解。

### 22D. wire-ground 实际旗脚进入同一预留

只对真实会发生头档冲突的同宿主相邻电源/地脚建立联合候选：power 按 `style=flag`，ground
虽 `style=wire` 也按 `_flag_seat_pins` 的实际出口和 `_flag_plan` 进入同一预留，不把所有
wire-ground 改成逐脚旗。用 `_flag_alternates`（复用现有 `_flag_anchor`）联合选档并严格回放。
无此冲突的旧页面与CH34保持行为；不得改变GND簇/别名/回路与网名。

若联合无座，本批必须继续调用binder求yield并做一次同构建回放，不能再因“本阶段没有GND”停下。
服务件的让位轴优先取宿主—服务pin连线的垂线，保持pinGap；普通branch仍沿既有escape/阅读轴。
只有有限候选、已有binder和一次回放，不扩reach/形状/页框、不第二套退火。topology只接受同一
模板+binder与重投影，未接不得标完成。

WiFi 正向仍须 §22C 全部独立验收，失败则给最小联合无座/yield拒绝证书。文件域不变，最多
20步/20分钟，证据续写integration，不真机/git/rm/全量。

22D 实测 WiFi 真实候选，主代理复跑548D邻域 **124 passed**、CH34 `allMatch=true`，并亲看WiFi
放大图未见跨线/文字互压。整页八岛局部均有候选，但页框失败1696×955.5；MCU渲染左侧与右侧
标签拥挤，视觉未签。`placement.py` 的 corridor binder/service_gaps 尚未被生产WiFi消费，不能
把API测试称完整集成；yield回放、topology corridor同源仍未接。

## 23. 548D3D-R：强制 topology 的 S3 让位（一个缺口）

当前强制 topology 仍为0候选，首败是 `S3` 处于串联保留区时两侧让位均落在label/part/foreign pin；
`evidence/548D/full-page/topology-current.log`（原GBK）及 `.tmp_548D3/topology-current.utf8.log`。
先逐 lane 记录实际S3 origin、冲突盒、label/pin owner和最终失败，不根据失败的泛化文案猜根因。
文件域限 `placement.py`、`drawcompiler.py` 与 `tests/test_548d_topology_band.py`；series共享合同仍按
shared-platform §10串行。不得把guard盒简单推给旧分排（旧实验已证ESP_EN穿框）、扩reach/page、
改near/排名/硬闸、删失败断言、伪造锁或恢复旧折返。

修复后强制 topology 必须真实出候选并独立逐脚/分区、NC/短路、文字/连续导体/grammar/readability/
SVG；更新原“仍拒绝”测试为当前真实合同，不保留成败皆可。重跑548D组合、CH34与WiFi正向。
主代理负责变异和视觉签字。最多25步/25分钟，证据 `evidence/548D/full-page/topology-s3.md`，
临时 `.tmp_548D3/topology_s3/`；不真机/git/rm/全量/其它方向。

23 的穷举证明只修S3不足：当前4个联合lane耗尽于互锁；其它座位各有LED1_K/ESP_EN标号或R1.2
GND失败。不得擅自增加预算/改排名；另查通用文字归属与页级真实几何。

## 24. 两个不重叠小批（并行文件域，串行复验）

### 24A. 页级电源旗名回退

`drawcompiler._flag_ref` 已按原名优先、缺席时精确回退 `PWR-+3V3`，但 `pagecompiler._flag_profile`
与 `islandlayout._flag_ref` 未统一。文件域仅这两个生产文件及新增 `tests/test_548d_page_flags.py`；
仅power net=3V3且原名缺席时回退，原名优先、其它电源名不变、GND永不别名、无改名/合网。
用同名不同几何negative control证明不能静默替代，页面端口/库旗ref一致。旧行为除该缺口外不变。
证据 `evidence/548D/full-page/power-alias.md`，临时 `.tmp_548D3/page_flags/`；最多15步/15分钟。

### 24B. 声明串联支路的文字归属

MCU 当前D2本体y=15，其reference/value却落在y≈−20/−5，成对支路文字被局部首适配打散。
文件域仅 `drawcompiler.py` 与新增 `tests/test_548d_text_ownership.py`，不改placement/topology预算、
输入合同或旧断言。消费已声明的seriesBranches，让同型臂件联合尝试文字侧/档，优先生成同属一支路
可读的一致排列；stated side仍是首选但回退不能把另一臂文字挤到远方。无声明/CH34保持原行为。
必须测量真实文字盒与owner距离、成对一致性、无互压和SVG；若无合法排列应具名拒绝，不能远处
放字冒充可读。跑548D邻域、CH34及WiFi正向。证据 `evidence/548D/full-page/text-ownership.md`，
临时 `.tmp_548D3/text_owner/`；最多20步/20分钟。不真机/git/rm/全量/额外线agent。

24A 完成页/岛 `PWR-+3V3` 原名优先回退及negative control；24B 同型臂件联合文字侧/档使D2回到
本体行带，主代理已看新渲染，仍需整页验收。当前整页仍页框失败；大组4^n待有界优化，不能隐瞒。

## 25. 548D3D-L：straight 标签盒参与后续布线避障

强制 topology 的 binder 座位在当前代码已不再首败R1.2，而败于 `ESP_EN` 标签盒被后布LED1_K穿过
（`evidence/548D/full-page/topology-binder-current.log`）。`_label_at`选盒时看已布导线，但其
`occupied.append(box)`没有进入后续router的实体墙。文件域仅 `drawcompiler.py` 与新增
`tests/test_548d_label_walls.py`，不改placement/枚举/预算/排名/公共输入。

只在显式 `labelPolicy.stub="straight"` 且调用方提供实体墙列表时，把最终文字盒加入该列表；
缺省参数、旧标签路径与CH34不变。不得通过删文字、容忍穿越或改评分放行。先直接证明ESP_EN盒在
后布LED1_K的障碍集中，再跑同一binder座位的真实全构建；若转到其它真实失败逐项记录，不扫lane。
正向需无文字/导体穿越、逐脚分区与SVG；负例证明未指定stub/未给墙旧行为。跑548D邻域、CH34、WiFi。
最多20步/20分钟，证据 `evidence/548D/full-page/label-walls.md`，临时
`.tmp_548D3/label_walls/`；不真机/git/rm/全量/额外线agent。

### 25A. 先定位真正穿盒的绘制帧（不得凭首轮route回退）

首轮三处 wall 试改后同一座位仍拒绝，生产已还原，但 `ESPCHK` 仅测第一次route，未测LED1_K
实际run。须在产生穿盒的那次route/_stub_label/_flag_anchor记录 `ESP_EN bbox in router.boxes /
solids / bodies` 与调用栈。若普通route看solids，旗引线看bodies，分别修对应传递，不能只看一处。
经直接单元/几何验证的局部修复可以保留，不因后续另有R1.2/label/页框失败就回退；不得以整页
尚未通过为由省略测试。默认路径保持、CH34 MATCH，禁止新增容忍。最多10步/10分钟，证据续写
label-walls.md；仍无候选则给精确阻塞，不扫描其它座位。

### 25B. 用既有 extra_text_walls 处理后至标签冲突

主代理补探针证明：预留与最终 ESP_EN 的anchor=(-115,-45)、preferred=(1,0)、U1=(-195,0)完全一致；
首选盒 `(-103,-49.5,-56,-40.5)` 与 R1 文字带 `(-92,-46.5,-68,-37.5)` 相交。原“后布run穿既有盒”
与“只是wall未传”均被时序证据推翻。`_build_one_variant` 已有 548C4 的 `extra_text_walls` 递归，
用于器件文字避开后至标签；本例最后 `_reseat_crossed_labels` 先失败，未能进入文字修复。

仅当显式 straight 且最终标签冲突有具体盒时，把**该冲突盒**交给现有extra_text_walls，在同一
placement上做至多一次文字重排+全部后续检查；不得全量盲加标签墙、循环重试、改placement/搜索/
near/排名/阈值。非straight/CH34默认不变。必须有R1文字移开、ESP_EN无穿线/叠字、墙随文字更新、
逐脚分区与SVG；若随后暴露其它真实失败保留已证局部修复并单独记录，不回退有效修复。
文件域仍drawcompiler.py+新tests/test_548d_label_walls.py，最多20步/20分钟，证据续写label-walls.md。

### 25C. 在正确的预留入口保护 straight 文字盒

25B 已保留一次 `label_text_reseat` 修复（drawcompiler `f8a478d9…`），但测试只测“不相交”不足。
主代理复跑probe_seq：二次构建预留时 R1 旧带已不占首选，ESP_EN仍落 `(-103,-49.5,-56,-40.5)`；
LED1_K 由 `_connect_net` 产生 `(-115,35)→…→(-75,-110)` 并穿盒。`_reserve_label_stubs` 的
`_reserve_service_label_box` 仅service页面生效，straight本身不保证完整label bbox进入router.boxes。

只在该函数、显式straight路径，把试用label的真实bbox去重加入router.boxes及后续service_walls保留；
不改 `_label_at`、不重复加调用点、不改auto/CH34。必须证明LED1_Kroute前盒在墙里且实际不穿；
另断言R1文字前后坐标真实改变而非只测最终不相交。保留25B修复，若转其它失败单列，不回退有效项。
最多12步/12分钟，跑聚焦+548D邻域+CH34+WiFi，证据续写label-walls.md，不真机/git/rm/全量。

### 25D. 标签分支与生成时序复核（缺旗形分支归因已撤回）

25B 插入代码后旧行号失效；当前 `_build_one_variant:14710` 实际是 `expression.style=="label"` 的
`_label_for`。ESP_EN 是纯标签网，不经过 `_connect_net`，也不是缺旗形分支。LED1_K 先于最终标签
生成，单纯在后续分支同步wall来不及。25B文字重排保留，25C/D试改均无净生产改动。

### 25E. straight 标签的座位、文字墙与最终对象同源回放

`_reserve_label_stubs` 已在布线前调用 `_label_for`，但只保留试用bbox/部分桩；最终per-net重新选盒，
导致试用盒与最终盒不同，且最终盒可能晚于其它网的导线。只在显式straight下，预留阶段保存实际
`(net,member) -> LayoutLabel`，将该bbox去重加入router.boxes及后续保留墙，per-net回放同一对象而非
重新 `_label_for`。同阶段已有标签墙参与后续候选避让，保持net_order、锚点、梯子、pin与文本不变。
auto/CH34及未提供seat映射的旧调用保持行为，不改placement/排名/预算/公共输入。

新测试必须钉住预留对象与最终对象身份/盒一致、LED1_K之前墙已生效且无穿盒、重复名不漏；25B保留，
真实同座位跑全构建与SVG。若仍拒绝须给真实下一失败，不把无候选写成通过。文件域drawcompiler.py+
tests/test_548d_label_walls.py，最多15步/15分钟，证据续写label-walls.md；不真机/git/rm/全量。

### 25F. 同源回放只在既有冲突的文字修复构建启用

25E 实测回放使ESP_EN不再穿线，但LED1_K为避让多走245>215；全局straight回放又让WiFi的
后续旗名行与早回放标签相撞，已回退。正确作用域不是按网名，而是25B已有的 `label_text_reseat=1`：
仅在实际冲突触发的那一次文字修复构建提供seat映射并启用同源回放；初始构建不提供映射，行为不变。
无冲突的WiFi/CH34不进入该路径，不能改默认标签合同。

保留25B，重接25E时增加显式repair开关，初始default关闭。测试须同时证明：WiFi正向、MCU
ESP_EN不穿、同一placement只一次修复、默认无回放；真实后续LED1_K通道245/215须单独记为未解，
不得放宽长度/包络。若只是该通道仍拒绝，可保留已证标签修复，不用候选预算/排名掩盖。
最多15步/15分钟，文件域不变，证据续写label-walls.md；不真机/git/rm/全量。

### 25G. 标签选位看见已声明的 series host 通道

25F 已落地repair-only标签回放（drawcompiler `fd00d57a…`），WiFi与组合112 passed；ESP_EN不再
被穿线，唯一失败是LED1_K绕行245>215。labels预留早于 `_series_channels` 的使用，标签盒/载体
未把已声明host path作为障碍，导致router事后绕开。只在25F的repair路径，把既有 `_series_channels`
作为标签选位的几何障碍（不画两次、不提前注入另一批通道、不改net顺序），让标签和carrier在绑定前
避开计划host path；原通道、185+30判据、其它nets及默认路径不变。不得恢复旧channel-reserve失败实验。

新测试钉住标签选位避host path、实际LED1_K长度≤215且不穿盒、通道连接逐脚，WiFi/CH34不变；
若仍有下一失败单独记录，不能把245/215放宽。保留25B/F有效项，文件域drawcompiler.py+
tests/test_548d_label_walls.py，最多15步/15分钟，证据续写label-walls.md，不真机/git/rm/全量。

25G实测未改善，已撤回；不能据此放宽245/215。

### 25H. 纯标签不预留未绘制的载体

当前 `_reserve_label_stubs` 在 `local=False` 仍为每枚标签预留40单位stub，但per-net纯label分支
只 `_label_for` + labels/solids，没有对应 `_stub_label`/local carrier；`localLabelObligations`才有
实际carrier。repair回放已能保存真实label和文字墙，因此其 `local=False` 分支不应再替未绘制的
stub挡路。只在25F的repair/seat映射路径跳过这条ghost-stub lane，保留label bbox、文字墙、实际
localLabelObligations carriers及auto/初始构建旧行为。不是删除文字或允许穿线。

测试钉住ESP_EN无实际carrier、40单位ghost lane不占、label bbox仍在墙、LED1_K真实长度≤215且
不穿文字/逐脚连通；WiFi/CH34与既有25B/F全绿。无候选则给真实下一失败，不放宽任何阈值。
文件域不变，最多12步/12分钟，证据续写label-walls.md；不真机/git/rm/全量。

25H撤掉整条ghost lane会把GND引到ESP_RST且另一座位LED1_K=645，已回退；不能用删墙凑候选。

## 26. 548D3D-A：让位轴由保留区角色决定

主代理复读binder发现：`5/0` 座位上S3只命中臂内器件盒 `part0`，不命中host/middle，
但 `_series_yields_for` 一律取plan.lateral，把它推向其它键/标签。器件盒碰撞应沿阅读轴progress
让开；host/middle通道仍沿lateral。此前“两轴全放开”实验把所有碰撞混谈，未验证这个角色差异。
文件域仅 `placement.py`、`tests/test_548d_series_placement.py`、`tests/test_548d_topology_band.py`；
若确需drawcompiler只读接点可改，禁止输入/CLI/排名/预算变更。

仅在全部命中角色为臂内器件（part0/part1）时用progress；混合或host/middle仍lateral。
初次yield和repair必须同源，锁/host/ordinary约束不变。先测5/0实际S3yield，再跑同一强制topology；
没有真实候选不摘旧拒绝断言，有候选须完整逐脚/分区/NC/短路/文字/grammar/readability/SVG。
保留25B/F、WiFi、CH34，跑548D邻域。主代理做独立变异与视觉。最多20步/20分钟，证据
`evidence/548D/full-page/series-yield-axis.md`，临时 `.tmp_548D3/yield_axis/`；不真机/git/rm/全量。

## 27. 548D3 当前收口：局部修复保留，目标未闭环

- base MCU 的原 7 条 xfail 已真实通过后摘除；WiFi 单岛有真实候选并通过机器、逐脚和主代理
  放大目检。连续旗引线、相邻power/GND联合选档、页/岛 `PWR-+3V3` 回退、同型臂件文字成组、
  repair-only 的一次文字重排与同源标签回放保留。CH34 `allMatch=true`。
- 最新整页 `evidence/548D/full-page/final-compile.{log,json}` 八岛局部均有候选，但页级尺寸
  **1694.75×1009** 超出固定 1170×825；不放大页框。强制 topology 仍 0 候选，S3/R1.2/标签/
  245>215 是多层独立失败，不可只修首败便宣称完成。MCU/整页视觉未签。
- §26 的角色让位轴实测改变种子与成本面并产生新冲突，已完整还原；全局标签回放、删ghost lane、
  逐件调C8/C9等 likewise 均未作为生产修复保留。未接生产消费者的 corridor binder/service_gaps
  只有内部数据测试，**不记能力完成**。主代理也没有接受提高候选预算/改排名/伪造锁等绕行。
- 当前权威交接、生产hash和剩余复验清单见 `evidence/548D/HANDOFF.md`。全量 pytest 日志
  `evidence/548D/full-page/full-pytest.log`；connector/DSH/Rust/文档钉读数按实际补录。
  548E/547G继续暂停，未做git写。后续新批应做页级二维布局与通道/文字共同约束，不重复局部试错。

## 28. 548D3 全量回归的兼容修复（不改变整页未闭环结论）

第一轮全量 `10253 passed / 25 skipped / 1 xfailed / 23 failed`，日志
`evidence/548D/full-page/full-pytest.log`。与既有16条相比新增7条：`_lead_lane_reservations`
新增label_seats按位置传入，破坏 `test_145a_walls` 两条与 `test_053b_drawcompiler` 一条旧
monkeypatch；`_declared_sibling_owners` 直接读 `constraint.reason`，破坏 `test_543g_adjacent_bands`
四条无该字段的轻量上下文。只允许最小兼容修复：新增可选参数keyword-only并保留旧位置参数，
reason用缺省空串兼容，不改旧断言或布局结果。

同批清理 `_topology_placement` / `_place_chain_and_shelf` 关于base不再被compile调用的陈旧注释、
`pagecompiler.py` 末尾额外空行及 `test_548d_wifi_ground.py` 新增段两行换行风格。先跑
`test_145a_walls.py`、`test_053b_drawcompiler.py::test_a_refused_lane_never_becomes_a_seat`、
`test_543g_adjacent_bands.py`、548D label/WiFi/reservation与doc_claims聚焦；主代理审diff并做
独立变异后才允许第二轮全量。不是用修测试、放宽判决或回退有效修复来消红。

第二轮全量 **10261 passed / 25 skipped / 1 xfailed / 16 failed**（1429.46s），新增7条兼容回归
全部消除，余16条与既有名单一致，不称全绿。connector **576 passed + typecheck**、DSH
**137 passed / 1 skipped + typecheck/build**、Rust **111 passed / 4 ignored + fmt/clippy**。
当前 `drawcompiler.py` `39846ced5653ef83742bfc122181abfb824289ee0e22bb1d9cc793045fb97341`，
`pagecompiler.py` `167a770c5e25f22be93a6d2cfd36bd9c5d431bdbfdaef7f63d0f60045a22ded7`。
日志与逐项命令 `evidence/548D/full-page/toolchain.md`；整页未闭环结论不变。

## 29. 主代理三项独立变异与覆盖缺口

- base 禁用 `_place_chain_and_shelf` 的共享series分支：`test_the_series_mcu_island_draws_a_candidate`
  1 failed，恢复hash `8a63ec3c…`；日志 `evidence/548D/full-page/mutation-base.log`。
- topology 禁用 `_topology_request` 的模板：首个选择只测 `placement.place` 不经过此入口，未变红，
  不算有效变异；改选 `test_the_build_spends_its_four_seats_on_joint_lanes` 后1 failed，
  恢复hash一致；日志 `mutation-topology.log`（未变红对照）与 `mutation-topology-shared.log`。
- 错误让位：翻转 `_yield_target_is_legal` 的自身/他件排除后，既有正向测试仍绿，证明缺直接负例。
  恢复placement `2d795ed9…`，日志 `mutation-sibling.log`。仅在既有测试文件补一条“目标盒压住
  其它器件必须拒绝”的真实负例，再重复该变异，不通过删断言或放宽结果冒充测试有效。

三项已完成：新 `test_a_seat_on_another_parts_box_is_refused_and_a_clear_seat_is_allowed`
在真实函数下通过、变异后如期失败，placement恢复 `2d795ed9…`。汇总见
`evidence/548D/full-page/mutations.md`。这只证明测试敏感性与恢复，不证明强制topology已通过。

## 30. 548D3X：参考间距、真实二维排布与 MCU 面板联合合同（岳选 A，实施中）

### 30A. 实测裁决：40 不是唯一瓶颈，packing 也不是万能解

岳提示参考自己的岛布局。可查的是 `evidence/547/g4/` 的 **agent-adjusted A2 辅助重绘**，不是
automatic 或原始手绘；`E:\SmartMedicineBox` 没有原始原理图文件。主代理已亲看整页图。参考页普通
模块框最小净距为 **40**，attach 对的更小净距是既有豁免；生产 `PAGE_MODULE_GAP=40`，默认网格实取
`rung*40+grid=45`。不把参考坐标、绝对列数或 A2 图幅搬进规格，也不把普通岛距降到 40 以下。

`evidence/548D/page-layout/README.md` 以同一 `.tmp_548D/full/presentation.series.json` 捕获最终页端口
处理后的 `_Assembled.frame`：MCU 743×604、WiFi 590.5×200，横放至少 1373.5 宽、竖放至少 844 高，
都超过 1170×825。三列网格确实把短外围岛撑到 MCU 的行高，存在大量单元空白；但即便理想二维装箱，
当前真实框也不能直接进页。故路线是 **MCU 内部二维面板整理 + 页级二维布局**，不是只调 gap、只加
packer 或缩小文字。`attach.side=bottom` 能把 env/bmp 合体框从 564×169 改为 294.5×309，作为显式语义
派生实验保留，但仍不能独立使整页可行。

页端口参与 frame 后，只调用 `_compile_modules` 得到的局部尺寸不等于最终 `_Assembled.frame`。不同
诊断口径不得混用；以端到端 `_assemble/_arrange` 捕获为准。`frame-anatomy.md` 中的数字是页端口处理
后的 frame，不是纯局部模块大小。

### 30B. 第一小批：声明解析与纯几何排布（不碰真实整页验收）

新增显式 `pageArrangement={"strategy":"compact"}`，缺省 `None` 时不序列化、不生成新变体、不改变
旧 digest/variant/输出。它只授权解释器在既有 `moduleOrder`/`flow` 语义下计算紧凑岛位；**不接收任何
坐标、框尺寸、userLocks、分岛决定或新阈值**。未知 strategy、额外键、坐标键、非对象均具名拒绝。
不是自动语义分岛，也不把 `moduleOrder` 改写成坐标表。

文件域一：`core/presentationspec.py` + 新 `tests/test_548d_page_arrangement_spec.py`；至少覆盖
缺省等价、round-trip、非法 strategy/键/坐标，原 `test_053a_specs.py` 不回退。文件域二：新
`engines/pagepacking.py` + 新 `tests/test_548d_page_packing.py`，只做真实矩形、固定页框、gap、grid、
keepout 的确定性有限排布，不 import drawcompiler/placement，不猜电路语义。输入为本体局部 frame、
既有模块优先序和页面可用框，输出解释器计算的 origin；不能旋转、缩放、改 frame 或放宽净距。

最小几何夹具必须包含旧规则 grid 无法表达的“左侧高框 + 右侧参差短框”形状，以及：
恰好 40 可过、39.x 拒绝；重叠/出界/keepout 拒绝；attach 已合成占位框后不重复排列；确定性与
hash-seed 等价；有限空间找不到时返回结构化失败而非无限搜索。不能以提高候选预算、改 lane 排名、
放大交付页框或放宽断言证明成功。两个文件域可并行，完成前不接 pagecompiler、不宣称整页改善。

### 30C. 第二小批：页面 consumer 与端口—框—布局同源回放

仅允许 `core/presentationspec.py`（若首批有集成修正）、`engines/pagepacking.py`、
`engines/pagecompiler.py` 与新 `tests/test_548d_page_arrangement.py`。`PresentationSpec` 是 draw 域
合同，不修改 parser/DesignModel/CircuitSpec/ChangePlan/CLI/DSH/Rust；无 shared→draw 新依赖。
`readability.py` 的 40 闸和全部既有终审不改。

compact 变体使用每个模块真实 generation、attach 合成框和纯 packer；原 grid 保留为后续回退，未写
新键的 variant 序列必须逐项相同。搜索空间有限且确定性，超限/不可行具名 `presentation-poor` 或
`layout-unsat`，不得输出一个框重叠的“最佳努力”结果。最终普通岛框净距门槛是 `budget.module_gap=40`，
不得另设更小值。实现时 compact packer 的候选净距取 `module_gap + grid`：局部 frame 含小数坐标，
page origin 还需吸附到格点，这一格候选余量用于保证最终原点回放后仍满足 40；它不是放宽 40，
也不是把参考页的普通间距改为 45。最终所有 frame、文本、图框、NC/短路、mainPath 与跨岛导线仍由
原 checker/路由拒绝不合格候选。

**端口联合约束**：`_module_ports` 目前依赖旧 columns/order 决定出口方向，而端口文字又改变 frame。
compact 不得继续只按假想网格方向排版。每次从原 module candidate 的干净副本构造，先得到候选排布，
再按真实邻接/唯一 partner 方向重建端口与 frame、重算 attach 并重排；用同一最终 LayoutPlan 终审。
有限回放收敛才接受，振荡/退化具名拒绝；不得累加重复标签、事后挪 frame、伪造端口或手填 origin。
mainPath 是否相邻必须由实际页面几何和合法通道决定，不能沿用旧 columns 的位置公式冒充邻接。

最小页面夹具为三个模块的真实 compile：旧 grid 放不下而新参差布局能放下，并携带一个跨岛信号；
断言端口重建前后无重复图元、最终 frame 与内容一致、独立 `check` + `check_page` 通过、旧输入输出
不变。负例覆盖端口振荡、mainPath 穿第三框、attach 与邻岛过近、页框差一单位、非法重复模块。
开发只跑聚焦，不接真实整页、不跑全量；主代理独立审 diff 和至少两项源码变异后才进下一批。

### 30D. 后续 MCU 面板与整页出口（不在第一小批冒称完成）

MCU 当前 14 件、长供电回线、按键一列和左右标签扇出同时造成框过大与视觉未签；不是 frame 多算
20 的空白。下一批从最小 MCU topology 夹具定义 Agent 可声明的面板支路行列/宿主侧阅读关系，解释器
共同安排器件、通道、文字和 GND，不允许只挪 KEY 文字、删 ghost lane、改 side 偶然种子或功能拆岛。
base/topology 必须消费同一决定；真实串联臂与按键/蜂鸣器不可混为同一种电气链。冻结电路/库不改，
派生 presentation 的每项语义差异单独记账。

只有在当前生产代码真实生成整页候选后，才做固定 1170×825 的逐脚/分区、NC/短路、连续导体、文字/
图框、grammar/readability、SVG 主代理逐岛视觉和完整四线。强制 topology 的 S3/R1.2/标号/245>215
仍是独立未关闭缺口；任何页级候选都不能替代它的验收。548E 真机继续暂停，不做 git 写。

### 30E. 通用小批主代理验收（2026-11-10，已通过；真实整页未开始）

`pageArrangement`、`pagepacking` 与 pagecompiler consumer 已接生产；旧规格不变，普通岛框最终净距
仍 40。声明/纯几何/真实页面三层测试、出界/重叠/truncated、旧 grid 回退、端口同源与 mainPath
实际布线均有证据。主代理最终聚焦 **215 passed / 1 skipped**，日志
`evidence/548D/page-layout/main-focused-final.log`。生产 `pagecompiler.py` hash
`54b2426ae2ee5709f9be04511e1d8a2c0ec357d56ea7bc4e2d17afe988014cd8`，`pagepacking.py`
hash `68f6bae73669d1b7bd13006047fff40297e95d0206d041f9f08d629c891b0c84`。

主代理先发现两个无效变异（旧39.5页界用例与三模块假想相邻主路径用例没有覆盖目标guard），补对角
净距和假想 grid 非邻接的直接判据后，净距/主路径变异均先红并 cp/hash 恢复；二维回填变异亦有效。
出界 packer 答案被 `_pull_inside` 修回页内的独立黑盒缺陷已修并回归。证据 `evidence/548D/page-layout/`。

端口真实振荡电路与本轮全量四线未做；MCU 面板、topology、逐脚/渲染视觉不记完成。
因子代理额度告警在通用小批边界暂停扩展，下一批从 §30D 进入，不重开 packer。

### 30F. 固定页完整输入的 compact 基线（2026-11-10，主代理实测，0 候选）

主代理未再派子代理，以冻结电路/库和固定 1170×825 运行两份派生展示件。`compact.presentation.json`
相对 `.tmp_548D/full/presentation.series.json` 只增加 compact；`compact-bottom.presentation.json`
再只把 `bmp280_optional.attach.side` 从 right 改为 bottom。两次均 exit 5：两个 compact generation
都 `packing-unsat`，随后 4 个旧 grid 都拒绝，合计各 **6 变体、0 候选**。bottom 的旧 grid 最小 need
为 1756×1144；没有整页逐脚/plan/lint/最终渲染可验收。原始读数、输入 hash 与命令见
`evidence/548D/page-layout/full-compact-baseline.md`。这关闭了“只改间距/附着方向/packer即可”的假设，
下一批仍是 §30D 的 MCU 面板，不能写成真实整页未运行或 compact 已通过。

## 31. 548D3X3A：二端支路面板的显式阅读合同（本批只做数据，不做几何）

### 31A. 缺口与边界

当前 MCU 的按键与 LED 臂由局部支路座位偶然排成单列，页级 packer 已证明无法仅靠岛间重排解决。
需要 Agent 把**重复二端支路的阅读分组**写出来，解释器再生成二维座位；不允许从位号/器件值猜功能、
自动拆岛、写器件坐标或伪造锁。第一批只增加数据合同，**不承诺改变候选或整页尺寸**。

新增顶层可选 `panelGroups`，每项是一组同类二端支路：

```json
"panelGroups": [{
  "id": "keys",
  "side": "bottom",
  "columns": 2,
  "branches": [
    {"from": "KEY1", "to": "GND", "part": "S1"},
    {"from": "KEY2", "to": "GND", "part": "S2"},
    {"from": "KEY3", "to": "GND", "part": "S3"},
    {"from": "KEY4", "to": "GND", "part": "S4"}
  ]
}]
```

这只是说明数据形状，不是把 SmartMedicineBox 的位号写进引擎。`id/side/columns/branches` 为组闭合四键；
每个支路闭合 `from/to/part` 三键。`side` 为宿主阅读侧 top/bottom/left/right，`columns` 是阅读列数
（不是画布坐标/间距/缩放），必须正整数且不超过本组支路数；行数由解释器按声明顺序求出。
`from` 是宿主侧网，`to` 是支路终端网；电气成员、pin、真实宿主与姿态由后续 CircuitSpec+profile
校验，parser 不猜。每组至少两个支路，id 唯一、支路器件跨组唯一；一个器件不能同时属于 panel 和
seriesBranches。拒绝重复/未知器件名、空字段、布尔列数、额外键、坐标键、少于两支路、跨组重复器件。

缺省 `panelGroups` 与显式 `[]` 均不写出，旧 digest/JSON/variant/布局逐字节不变。显式组是 opt-in；
本批不改 `seriesBranches` 的五键合同，不把单件开关伪装成二件串联，也不自动把 LED 加入面板。
LED 臂后续只能复用既有 series 身份与同一面板阅读关系，不能复制电气声明或形成两套座位真相。

### 31B. 文件域与验收

仅 `src/boardwise/core/presentationspec.py` 和新 `tests/test_548d_panel_groups.py`。沿用
`PageArrangement`/`SeriesBranch` 的 frozen 数据类和闭合解析风格，新增轻量 `PanelGroup`/`PanelBranch`
与 `PresentationSpec.panel_groups`（默认空列表），仅非空时序列化。不得改 pagecompiler、drawcompiler、
placement、readability、冻结输入、旧 fixtures、CLI/DSH/Rust、package.json，不做 git/真机/全量。

测试至少覆盖：缺省/空数组等价与旧 digest；合法 JSON/dump/load round-trip；组/支路闭合键、id/side/
columns/branches 类型与边界；少于两支路；重复 id/器件、series 冲突；坐标键拒绝。电路拓扑、两脚
校验、宿主唯一性、页面切片属下一批，不能用“parser接受”冒充电气合同已验证。

聚焦运行新测试、`test_053a_specs.py`、`test_548b_series_branches.py`、
`test_548d_page_arrangement_spec.py`，独立 basetemp。至少两项源码变异先红后 cp+sha256 恢复。
后续几何的最小夹具为同一宿主四个 GPIO 各接一只二端件到 GND，声明 side=bottom、columns=2；
预期阅读关系是 2×2 面板，底座/旗标/文字由真实度量联合排布，不接受四个偶然横坐标或手填 origin。

### 31C. 主代理复验（数据合同通过，几何未开始）

子代理实现后主代理聚焦 **163 passed**；38 条 panel 新测试覆盖缺省/空数组、round-trip、闭合键、
四向、columns 边界、重复/未声明器件、series 冲突与坐标拒绝。生产 `presentationspec.py` hash
`63ab7638d402ebce938872c65299bdb20616fd65b850f4ea2c512283ae0b8341`。主代理分别禁用模块成员
检查与 panel/series 互斥检查，`test_an_undeclared_part_is_refused` 和
`test_a_series_arm_part_cannot_join_a_panel` 均先红，随后 cp+SHA-256 恢复；日志
`evidence/548D/page-layout/panel-mutation-{member,series}.log`。

**本批没有几何 consumer，不能写成 panel 已能排成 2×2。**下一批先做电路与页面切片校验：
每个 part 的真实两脚分别落在 from/to；from 的其余成员各自解析为一个唯一宿主脚，组内所有支路
必须属于同一宿主件（四个 GPIO 是同一 MCU 的四个不同脚，不是同一个脚）；
缺少/多个宿主、跨模块组、错误脚数、from==to、错误 NC/短路与 panel/series 重复归属均具名拒绝。
page 切片必须完整携带同模块 panel，不能像早期 series 一样静默丢失。然后才允许 base/topology
共用同一 PanelSeatPlan 生成 2×2 座位，禁伪造锁、参考坐标和两套独立退火。

## 32. 548D3X3B：panel 电气与页面切片校验（本批不做几何）

### 32A. 消费者与判定顺序

新增 `drawcompiler.validate_panel_groups(circuit, presentation) -> list[GrammarFailure]`，复用
`_series_pin_nets` 的电路分区读法，不复制一套成员解析。`drawcompiler.compile` 在 series 校验之后、
grammar/几何之前调用；`pagecompiler.compile_page` 也在整份文档上先调用。无 panel/[]立即返回[]，
旧 SimpleNamespace 可用 `getattr(..., "panel_groups", ())` 兼容，旧调用序/候选不变。

每个支路按依赖顺序判定，拒绝后不做依赖该事实的后续判断：

1. **事实存在**：part/from/to 必须在 CircuitSpec，缺失为 `facts-missing`，声明不能创造连接。
2. **同一模块**：组内所有 part 必须恰好同属一个模块；跨模块/无模块/重复归属具名拒绝，不能切片一半。
3. **两端不同且两脚两网**：from != to；该 part 的电路脚恰好两个，分别落在 from/to，不能第三网、
   同网短接或 NC 兼任。错误为 `circuit-invalid`，拒绝文本给出真实 pin→net。
4. **每支路唯一宿主脚、全组同一宿主件**：from 在该模块内除去本支路 part 后必须恰好一个宿主成员；
   各支路有自己的宿主脚，但所有宿主脚必须属于同一 `hostPart`，宿主不得是本组支路件。零宿主/
   多宿主/同件不同脚造成的歧义均具名列出候选，不按位号或网名猜。四个按键就是同一 MCU 的四个
   不同 GPIO，不是全组共用一个 GPIO。模块外同名网成员不冒充本地宿主；terminal/to 的公共回流
   可以有其它成员。

至少一个有效四支路夹具证明校验本身接受合法输入；不得只写全负例。每个负例必须证明在 grammar bind/
placement 前退出（spy 或拒绝阶段），不是靠后续无候选碰巧同类失败。合法 panel 在本批仍走旧几何，
**不宣称声明已产生二维布局**。

### 32B. 页面切片与兼容矩阵

`pagecompiler._module_view` 仅在该模块拥有组内全部支路件时携带完整 panel group；整页 V2 已拒绝跨模块，
所以不允许出现半组切片。standalone 与 page 切片的 panel id/side/columns/from/to/part 逐项相同。
缺省 panel 的旧页面输出、monkeypatch 调用和 CH34 pinned 不变。

| 维度 | 本批覆盖 | 不得声称 / negative control |
| --- | --- | --- |
| standalone / page | 同一有效/无效 panel 的整文档校验与同组切片 | 一方接受不替代另一方；跨模块必须在切片前拒绝 |
| 二端件与宿主 | 两脚两网、唯一宿主脚、组内同宿主 | 三脚件、缺/多宿主、from==to、NC兼任必须红 |
| 未声明 / [] | 旧调用序、输出与 CH34 pinned 不变 | 不得因直接属性访问破坏轻量旧 presentation |
| base / topology | **本批不接几何** | 不宣称 PanelSeatPlan、2×2 或 topology 已通过 |
| 在线 / 容器 / 多板 / CBB / V3/V4 | 均未覆盖 | 只做离线普通器件；不进入548E、不声称兼容完成 |

文件域：`src/boardwise/engines/drawcompiler.py`、`src/boardwise/engines/pagecompiler.py` 与
新 `tests/test_548d_panel_validation.py`；不改 placement/readability/core 公共合同、旧 fixtures、CLI/DSH/
Rust/package.json。聚焦新测试、548B validation/geometry、056 pagecompiler、548D panel/series 邻域，
独立 basetemp，不跑全量/真机/git。至少两项主代理可复现变异：禁用两脚两网校验、禁用同宿主校验，
均须先红并 cp/hash 恢复。交回后由主代理审真实页面切片与拒绝阶段，再决定是否接座位。

### 32C. 主代理复验（电气/切片通过，几何未开始）

主代理组合 **272 passed / 1 skipped**，含 standalone/page 正例、14类负例、整组切片、缺省与轻量旧
presentation。`drawcompiler.py` hash `41129e4e68f395d56b9aeb801b5ba519ee97f5eb3d36d13a063e6467693ca207`，
`pagecompiler.py` hash `9c4b8f95909d12bfbbf79ca2593e9c37a16ac406c20502e5f60b7a23b0377308`。
禁用两脚两网检查使 `[third-net]` 红，禁用唯一宿主脚检查使 `[two-hosts]` 红，均 cp+SHA-256 恢复；
日志 `evidence/548D/page-layout/panel-validation-mutation-{nets,host}.log`。

子代理指出主代理原“全组同一 hostPart.hostPin”写法与四键四 GPIO 矛盾，裁决为**每支路唯一宿主脚、
全组同一宿主件**，§31C/§32A 已纠正，未让实现迁就错误文字。合法 panel 仍走旧几何，不能宣称
PanelSeatPlan/2×2、MCU尺寸改善或整页通过。下一批只接 base/topology 同源面板座位，未跑全量四线、
548E继续禁止、未做git写。

## 33. 548D3X3C：base/topology 同源 PanelSeatPlan（placement层，非完整图纸候选）

### 33A. 本批出口与不做什么

**实施分解（33C首次停止后修订，不缩小总出口）**：首次把binder、两个消费者与全部负例放入30分钟，
执行者按停止线零生产改动交回，未形成可验证2×2。改为 **33C1 topology真实PlacementResult先行**
（`placement.py` + `tests/test_548d_panel_placement.py`，由真实template产生2×2、plan随result返回、
panel件不得单独move、外国预留hard、空输入不变），随后 **33C2接drawcompiler base/topology模板与
锚点复核**，§34才接最终route/text/flag。33C1没有base与完整图纸时不记§33完成；binder无消费者、
只读设计或仅测试坐标均不算通过。总目标仍是base/topology同一binder，不是接受单消费者方案。

把已验证的 bottom/columns panel 变成 **真实 placement 座位**：base `_Placement` 与 topology
`PlacementResult` 都携带同一 bound plan，panel 器件原点/姿态与计划一致，文本/旗/宿主通道的预留
无非法碰撞。**本批不要求 `draw compile` 整张 LayoutPlan 通过**；实际 from/to 导线、文字与旗标回放
属于 §34，不能写“2×2原理图已交付”。

首版只接 `side="bottom"`；其它 side 在几何入口具名 `layout-unsat`，不悄悄当 bottom。`columns`
按声明行主序消费，四件 columns=2 必须是两行两列，每件仍属于自己 from/to 网，宿主件不得被搬入
面板。首版不做复杂 sibling yield：外国器件/userLock/外国针脚侵入预留即具名拒绝，不挪锁、不放宽
hard、不改变排名/near/页框。无 panel/[]时模板/计划为空，旧随机轨迹与 CH34 pinned 不变。

### 33B. 唯一数据与网格方程

`placement.PanelSeatTemplate`/`PanelCell` 为纯数据：group id、host part、side/columns、每格 part/
from/to token 与 from/to net、由 `_arm_pose(..., (0,-1))` 得出的确定姿态、grid/lattice、文本相对盒
和已有 `FlagReservation` 所需终端信息。**没有绝对 origin**；文本相对盒由 drawcompiler 的既有
`_line_boxes` 生成，禁止 placement 再发明一套文字度量。

`BoundPanelSeatPlan` 至少含：每格 origin/pose/from/to seat point、真实 part/text/flag 预留盒、每个
host pin→cell from pin 的正交路径、guard/refusal，及 `mismatches/translated`。唯一 binder 在宿主
origin/pose已知后物化；base/topology不得各写一个网格公式。

- 先以宿主 `_body_box` 求面板中心，不用宿主脚x均值（同侧脚x相同，不能形成两列）。
- 列宽取该列真实 part+text+flag 横向预留的最大值，行高取该行对应纵向预留的最大值；节距沿用
  既有 GAP/TEXT_GAP/grid，不新增场景常数。按声明列数在宿主本体下方居中排列，行主序不换身份。
- 每格原点由目标格框与确定 pose 的引脚偏移求出并吸附 residue；from朝宿主、to朝外，无姿态具名拒绝。
- host path从真实host pin到该格from pin，允许沿宿主外侧再转入面板的正交路径，不能穿宿主本体、
  其它支路/文本/旗/外国针。不得因为“side=bottom而脚在右侧”直接臆判无解，也不许任意绕线。
- terminal旗用已有 `FlagReservation.box_at` 的同一几何；旗与文字相对盒随格物化，不能等最终绘制
  才发现它们没有空间。相邻格、外国件、锁和既有预留相交均拒绝。

### 33C. 两个消费者与兼容边界

- **base**：在 `_place_chain_and_shelf` 的series消费后、page anchor前绑定并回写panel origins/poses；
  anchor后仅整体translate并mismatch复核。panel件从普通band/bay/stack/spread及series yield中排除，
  不能被后续普通 sibling pass搬回去。`_Placement` 增加默认空 `panel_plans`。
- **topology**：`_topology_request`携带相同templates；`placement.place`在普通seed后绑定并投影，
  panel件不得单独随机移动/交换/转姿，宿主移动时以同一binder重投影。外国件与panel预留相交为hard，
  最终result带panel plans；`_topology_placement`在anchor后复核。不能跑两次独立退火或伪造锁。
- 空tuple不得进入新binder/cost/move分支； PlacementInput/Result新字段均默认空，旧monkeypatch
  位置参数兼容。此合同是draw内部placement API，按 `tasks/shared-platform.md` 登记，不是shared
  CircuitSpec/ChangePlan/CLI/DSH/Rust合同，不覆盖容器/多板/CBB/V3/V4真机。

### 33D. 最小测试与停止线

文件域仅 `placement.py`、`drawcompiler.py` 和新 `tests/test_548d_panel_placement.py`；不改
readability/pagecompiler/core公共合同/CLI/旧fixtures/package.json，不接最终route/text/flag消费者。

复用§32真实MCU32/KEY夹具，直接检查base `_Placement` 与 topology `PlacementResult`：四件恰两条x带、
两条y带，每带两件；身份/姿态/from/to seat与plan一致；文本/旗/宿主路径在预留内且正交；最终
mismatches为空。不得断言参考绝对坐标。负例：非bottom、无合法pose、外国件/锁侵入、host path穿体、
文本/旗相撞、panel件被普通spread或随机move搬走、禁用topology投影。空输入与CH34 pinned不变。

聚焦新测试、548D series placement/validation、201B placement、548D panel/page邻域，独立basetemp，
不跑全量/真机/git。至少两项主代理变异：base不消费panel、topology不投影panel，均先红并恢复。
若只能得到binder而未接两个消费者，或没有真实2×2 placement，则按未通过交回，不把接口当能力。

### 33C1 主代理验收（topology真实2×2通过；base未接，§33未完成）

`PanelCell/PanelSeatTemplate/BoundPanelSeatPlan` 与 `PlacementInput.panel_templates`、
`PlacementResult.panel_plans` 已落。宿主body中心+真实part/text/flag预留产生网格，bottom四件columns=2
形成两x带两y带；host path正交、外国件/锁/非bottom具名拒绝。搜索四类move排除panel件，宿主候选
在**每次evaluate之前**由同一binder重投影，不是只在place末尾补一张plan。主代理组合
**81 passed**（新测试10 + 201B/series），随后邻域复验见 `panel-place-c1-main-fix.log`。
生产 `placement.py` hash `d24461ebb6d9a4069b78378bbe5370bc32113e6b8bd28a0ef1cd19bde5ae8ff7`。

主代理禁move排除，`test_panel_cells_never_enter_the_search_moved` 先红并恢复；首次禁候选投影测试
因误把place末尾bind计入而无效，改为直接观察anneal后，同一变异真实先红并恢复。无效旧测试不计通过。
日志 `panel-c1-mutation-{moves,projection-verified}.log`、`panel-c1-projection-test-fix.log`。

**33C1不是§33完成**：drawcompiler尚未从presentation构造templates，base `_Placement`、页锚点、
最终route/text/flag回放均未接；不宣称完整LayoutPlan或MCU改善。

### 33C2 下一批：drawcompiler模板与base消费者（一个集成点）

文件域限 `drawcompiler.py` 与新 `tests/test_548d_panel_base.py`；placement仅在主代理发现真实缺陷时
另行小修。由已验证panelGroups生成相同templates：每支路唯一host token/from/to token与确定pose，
文本相对盒用既有 `_line_boxes`，终端flag box用 `_flag_seats` 的真实profile，缺失旗型必须明示。
base在series后、anchor前调用同一 `bind_panel_plans`，`_Placement`携带panel plans，anchor后仅translate
并复核；panel件从普通band/bay/stack/spread及series yield排除。`_topology_request`也消费同一模板，
`_topology_placement`在anchor后复核，不得另写网格。

最小base正例必须真实 `_Placement` 两x带两y带且mismatch空，并与topology同一模板对拍；负例证明
普通spread/series yield不搬panel件、锁/外国件/非bottom具名拒绝、页锚点不破坏计划。空panel与
CH34 pinned不变。两项主代理变异：base不消费、普通pass搬panel件，均先红并恢复。未完成这些前，
不得进入§34最终route/text/flag或宣称§33完成。

**33C2a 合同冲突裁决与回滚恢复**：首次实现发现 `ic-periphery` 自动 `right-of(cell, host)` 与
`panelGroups.side=bottom` 冲突，不能以关闸消红。更具体的 panel 声明必须新增对应的显式
`BELOW(cell, host)`（或后续已支持侧的等价关系），并**只替换**这对 cell/host 的自动侧向关系；
其它电气关系与未声明panel的页面不变。compiler与独立 `check_grammar` 必须共用 `_with_panel_groups`，
错误挪回非below位置仍须失败，不能变成“没有right-of就算通过”。§32的“合法panel仍走旧几何”
是几何接入前的历史预期，本批明确改为检查新panel关系/座位，不保留矛盾断言、不删除负例。

首次回滚还误改 `arm_parts` 作用域并把原CRLF归一成LF，执行者最初误报只差空行。主代理用
`8a63ec3c…` 快照对照、枚举已知的空白/作用域/注释差异及行尾，恢复精确
`drawcompiler.py=41129e4e68f395d56b9aeb801b5ba519ee97f5eb3d36d13a063e6467693ca207`（CRLF），
`panel_validation+panel_placement` 复跑 **45 passed**。恢复记录
`evidence/548D/page-layout/drawcompiler-hash-gap.log`。后续只允许cp备份+小编辑，禁止字符串大段切割回滚。

**33C2b near 合同裁决（禁止调420）**：第二版在默认 `near_limit=300` 下，第二行panel被自动
`near(cell,host)` 拒绝；夹具预算改420虽可过，但这正是本目标禁止的near调参，不能采用。裁决是：
对明确声明的cell/host，自动near启发式由**更强的PanelSeatPlan核对**替代——计划逐格绑定真实宿主脚、
from/to身份、姿态、正交host path与预留，并在base/topology/anchor后做mismatch和hard复核。
`_with_panel_groups`只过滤这对cell/host的自动near与自动侧向关系；显式below和其它件/其它关系不动。
不是删除检查，而是换成更具体的检查；非panel支路的300预算与near判定不变。测试必须保持默认300，
并证明plan错位/穿通道仍失败、非panel的near仍失败。`check_grammar`只负责同一声明/关系，不能用
它看不到placement的事实冒充几何已验；实际几何由placement复核。第二次失败的实现/测试存证为
`evidence/548D/page-layout/drawcompiler.c2-attempt.py` 与 `panel-base2.test.py`，只能在其基础上做
这一合同修正，不得把near_limit改成420或删除旧负例。

### 33E. 主代理最终验收（base/topology 2×2 均通过；最终图纸回放待§34）

- **两个真实消费者都成立**：base `_Placement` 与 topology `_Placement` 都返回 seated plan、两x带两y带、
  mismatches空；主代理独立探针确认 topology 不再以具名拒绝充当正例。默认 `near_limit=300`，没有420、
  排名/页框调整或伪造锁。
- **几何与阶段修正**：host pin按真实pose的逃逸方向离开本体；未落座plan也是hard；外国侵入以真实
  相交面积给搜索梯度，任何正面积仍拒；topology spread把panel预留当障碍，spread后同一binder重绑复核。
  无方向pin具名拒绝，不默认+x。普通spread/series yield不搬panel件。
- **有效变异**：base不消费使2×2测试红；未落座plan不计hard使直接负例红，均cp+SHA-256恢复。
  spread去预留的一次变异在当前几何下未变红，明确记无效，未计入通过。33C1的候选投影/move排除
  变异此前已闭合，第一次投影测试的无效版本也已单独记录。
- **最终生产hash**：`drawcompiler.py` = `f1e47b11bce6aa482032fb918d935b299b9b6da505db2a70ba0894ce6b8f7c50`；
  `placement.py` = `abc285ef48fecbb4eacbe0630cf84f546e8355ef0a3c2c1f5661320eca234f05`。
  首次33C2回滚偏差已按 `41129e4e…` 精确恢复后再开发，当前差异均属本批实现/注释。
- **边界**：§33只证明placement层2×2与预留，不证明最终route/text/flag或整张LayoutPlan；
  SmartMedicineBox真实MCU/整页、强制topology原有多层失败、548E真机与本轮全量四线仍未完成。

### 34. 下一批：panel最终route/text/flag同源回放（一个交付缺口）

1. `host_paths` 必须成为最终from网的真实正交导线，不能被另一条路由随意替换；若与外国文字/导体
   相撞，具名拒绝而不是绕成无意义回环。from网各自连通，跨网短接=0。
2. terminal旗必须消费模板对应的真实 `FlagReservation`/glyph/lead，保留当地旗策略，不能在to网
   拉一条全板母线或把GND换成标签；缺旗型与姿态不符具名拒绝。
3. `_part_texts` 必须消费模板由 `_line_boxes` 产生的相同相对盒，不得在后续fallback把文字挪出
   预留。最终 LayoutText/LayoutPowerSymbol/LayoutSegment 与 plan 对账，默认无panel时旧路径不变。
4. 先用§32最小四支路fixture做到 compile ok、独立逐脚/分区、NC/短路、连续导体、grammar/readability
   和SVG主代理视觉三关；不先碰真实整页。然后才派生SmartMedicineBox的keys bottom/columns=2规格，
   量真实MCU frame并重跑固定页compact。必须记录 `automatic`，不能手填坐标或伪造锁。

文件域限 `drawcompiler.py` 与 `tests/test_548d_panel_base.py`（真实缺陷需要placement小修另报），
不接pagecompiler/shared公共合同/CLI/DSH/Rust/真机/git。至少两项主代理变异：最终host path不回放、
最终文字/旗不回放，均先红并恢复。

### 34A. 分段进展与联合路由性能停止线（2026-11-10，完整compile未通过）

已验证并保留：terminal bus 的向下预留、`_panel_channels` 的 host path→from网 `existing` 回放、
`_lead_lane_reservations` 的 terminal seat、`_part_texts` 的模板相对盒。对应分段读数分别为
60/89/91/94 passed；当前恢复版 `tests/test_548d_panel_base.py` **25 passed**，证据
`panel-final.log`、`panel-channels.log`、`panel-flags.log`、`panel-text.log`。

真实compile证明旧lane算法让不同net共用 `x=90`，不是可豁免的自有节点。两趟 `_Router` 原型在base
约1.7s 能得到各占 x=150/130/110/90 的合法引线，channel首因消失；但 topology 每个候选都重路由，
**80次bind约64s、220s未收敛**，不能进生产。原型还发现 entry需向上吸附residue、stub需作为本net
edge并封锁格点防发夹。原型未留下生产改动；原执行者上下文558k已停止续写，后续未派新agent。

**停止线**：不接受手工共线豁免、拓扑超时或“base有合法路径就称完成”。下一小批必须先做宿主相对
坐标的 route cache/整块平移与窄bounds，搜索期使用便宜代理或只在最终placement重路由；保留跨net
节点/共线/T接触检查。当前生产 `placement.py=e3de2122…`、`drawcompiler.py=ee4c1ade…`，完整
`dc.compile` 与 `panel-final.svg` 仍未通过，§34不能记完成。证据 `panel-router.log`、
`panel-joint-router.log`、`panel-joint-main.log`。

### 34B. 宿主相对缓存已落地，动态外国锚点成本未闭环（2026-11-10）

宿主相对 route cache 已保留：同姿态后续79次bind零新增 `_Router.route`，topology约11s、7个宿主
姿态/29次调用；channel改为在net loop前注入，GND label由 `_label_at` 避让；非法host-body路径
仍以显式负例拒绝。当前生产 `placement.py=68e48013…`、`drawcompiler.py=3298609c…`，
`panel_base + panel_placement` 主代理复跑 **38 passed**。

随后两版外国环境处理均未达标并回滚：①把外国part/引脚几何签名纳入cache key，环境逐候选变化使
**topology >300s**；②每候选对冲突短段做局部 `_Router` detour，**150s仍未完成、真实compile >200s**。
因此不再接受“动态环境全重解”或“每候选局部搜索”作为生产路线。当前首因仍是KEY2
`(75,35)->(75,40)` 内外国pin/anchor，**完整dc.compile与panel-final.svg未通过**。

证据 `panel-route-cache.log`、`panel-order.log`、`panel-pins.log`、`panel-detour.log`。
后续若恢复，只允许把动态detour限制在**最终候选**或使用预计算的解析绕行表，不得在搜索中反复
全环境/局部重路由。未得到可接受性能前，§34和548D均不记完成，548E禁止、未做git写。

### 34C. 机器编译通过，视觉验收 blocked（2026-11-10）

静态缓存、联合路径简化、panel terminal显式seat与聚簇最终使最小fixture `dc.compile` **ok=True、
1 candidate、hard=0**。随后主代理亲看最新 `panel-final.svg`：四个按键确为2×2，但GND仍形成
外框，soft metrics **9 crossings / 31 bends**，视觉拒收。最新图 `panel-final.svg` =
`54344f3a3d97882ed21814e08a60760737ac38c8d05f5d1d11f0107ca7ed6c3d`，浏览器证据
`panel-gnd-browser.png` 已保存，不能因机器通过就交付。

供电/地网后续实验证明：per-pin旗无座；扩 `_apply_flag_groups` 与既有seat回放不一致；簇内短接出现
**5簇3座**；seat-first需要新的“真实可用seat枚举 → member分配 → 短接 → 审计”合同，现有接口
并不具备。多次尝试均回滚，未留下未验证半成品。当前保留生产 `drawcompiler.py=add9ea56…`、
`placement.py=68e48013…`；`panel_base + panel_placement` **50 passed**，邻域 **237 passed**。

因此目标在本轮 **blocked**：不是缺少机器候选，而是没有可读图。继续有两条合法路线，需岳裁决：
A. 新写seat-first地网分配与审计合同；B. 接受 `agent-adjusted` 人工语义微调并重跑三关，不能冒称
automatic。548E真机、真实SmartMedicineBox整页与本轮全量四线均未做，未做git写。

### 34D. seat-first地/电源分配合同与34D-A枚举小批（2026-11-10，未接最终回放）

岳让主代理继续，按路线A执行。验收合同先落 `evidence/548D/seat-first-criteria.md`。主代理再次亲看
`panel-gnd-browser.png` 并对照既有网段取证：要消除的不只GND的201A外框，还有3V3宿主侧U形回环；
因此本能力对panel文档的地/电源采用同一本地旗座数据流，不能只换GND样式而留下另一个回环。

唯一决定为draw内部 `SeatFirstPlan`：语义share key → 固定panel terminal → 真实可用座枚举 →
全member合法正交路径分配 → lane/导线/旗同源回放 → 同一plan与成品segments审计。独立支路不得按距离
合并；每个member恰好一座；跨assignment不拉线；无座/不可达具名拒绝，不回退201A远端trunk。
`_Expression.clusters` 若保留只能由plan派生，不得另起分组。未写panelGroups时旧路径、digest、CH34不变。

本批只做 **34D-A**：内部数据、语义分组、固定终端输入、真实座/路径枚举与负例，证明当前fixture每个
语义组是否有完整候选；**不接最终接线/旗标回放，不宣称compile或视觉改善**。文件域限
`drawcompiler.py` 与新 `tests/test_548d_panel_seat_first.py`，不改既有测试、placement、core、page、
CLI/DSH/Rust、真机或git。若必须改placement/shared，或当前placement对独立支路无完整候选，交具体
net/member/obstacle证据并停止，另裁集成；禁止合并语义、调reach/near/排名/预算或放大页框遮缺口。
34D-B只有在A通过后才接预留/局部接线/最终旗/audit，仍需独立逐脚、两项变异与主代理视觉三关。

### 34D-A2. 跨网候选联合选择（2026-11-10，本批不改placement）

34D-A已落内部plan、真实座/path枚举与validator；主代理复跑 **70 passed**。当前3V3完整，GND仍缺
C1.2真实座位；U1.VSS则是次序冲突：3V3→GND时其(-110,85)座被3V3 lane占住，GND→3V3时可用且
3V3六座不变。只读审查起初判断旧候选可直接联合；实现实测纠正为：旧path并不兼容，必须先把单候选
（强制）座入障碍池、多备选组交给联合选择，重测path后才得到共存解。联合选择本身不重新搜索器件或路由。

本批只把auto候选枚举与选择分开：固定panel terminal和真实障碍先入墙；各语义组保留全部完整auto候选；
随后按当前兼容候选数（MRV）、成本、net/group/owner确定性联合选择，兼容判断只读候选节点集，
选择阶段禁止再调 `_Router.route`。冲突搜索必须有明确、固定的展开上限；超限与无联合解分别具名拒绝，
不得为通过调大预算。所有缺座语义组仍保持不完整，不把C1.2合并到别组。

文件域仍限 `drawcompiler.py`、`tests/test_548d_panel_seat_first.py` 与新证据；不改placement、最终compile
接线/旗标/audit、旧测试、真机或git。必须断言U1.VSS与3V3宿主组同时成立、反转net处理顺序结果不变、
联合选择零新增route，并保持70条复核及无panel负控通过。完成这只关闭次序缺口，不称34D-A全组可行。

C1.2另由34D-A3处理：现有FlagCorridor至少两pin且不消费本件文字，不能复用；placement.FlagReservation
也不含文字/完整lead，本批不改placement。只读裁决建议用同一SeatFirstPlan驱动一次既有
`extra_text_walls` 文字重排，再要求座位逐点一致；是否可行必须先实测，不预设通过。

### 34D-A3. 独立支路假设座与一次文字让位（2026-11-10，未接compile）

A2主代理复跑 **76 passed**，U1.VSS与3V3宿主组同时成立，GND只剩C1.2缺座；证据
`page-layout/panel-seat-first-joint.log`。本批只关闭独立支路文字/座位同源缺口，不接最终compile、
接线、旗标或audit，不改placement/shared/旧fixture/真机/git。

缺座组目前没有已接受glyph，不能拿“现有座位”回喂文字。只允许对缺座的 `SHARE_ALONE` 组提出假设座：
暂时移除owner自身文字盒，用真实 `_rail_flag_seat` 几何得到candidate；假设座不得直接进入assignments。
将假设glyph作为一次性 `extra_text_walls`，用真实 `_part_texts` 重排后重新枚举并联合选择整份plan。
只有假设anchor/lead在真实场景逐项复现、固定terminal不动、全部member完整且validator通过才返回成功；
文字未移动、座位变化、其它既有auto座不稳定或任何冲突都具名拒绝，不做第三轮或无限迭代。

实现必须让调用方能取得**同一份实际texts与所用walls**，禁止 `_seat_first_scene` 和 `_build_one_variant`
各自选一套文字。本批可以新增内部helper及可选输入，但不能改变无panel文档和旧调用签名默认值的行为。
同步修正A2中“所有候选座都入池”的旧注释，实际算法只有强制座入池。

文件域限 `drawcompiler.py` seat-first段及必要文字场景适配、`tests/test_548d_panel_seat_first.py`、新证据
`page-layout/panel-seat-first-text.log`。测试须含C1真实完整、假设座未提前入plan、文字实际移动且不压
其它实体、最终texts/walls同源、重排不收敛具名拒绝、固定terminal不变及原76条；不宣称视觉改善。

### 34D-A4. 重排终态独立验收（2026-11-10，不改A3旧断言）

A3主代理复跑 **83 passed**，其原合同拒绝仍成立：假设座(-110,35)未被真实自然向下座(-140,-15)
复现，C1.1与U1.VSS自动座也移动。**但同一A3返回的最终scene/plans2里，全部语义组在真实文字上完整。**
主代理裁决：假设座只是发现text wall的探针，“必须画假设座、自动座不得随整页重排改变”是本代理添加的
过程约束，不是电气/视觉不变量；不能因为过程不满足就丢弃一个可能更好的终态，也不能把A3改绿。

本批新增独立terminal结果与验收，不修改 `_seat_first_text_plan` 的A3逻辑、拒绝或既有测试。terminal保存
A3 discovery证据，但只以最终scene重跑整份plan：page=None、所有plan.complete、validator零失败、固定
terminal不动、文字/器件/keepout无碰撞、跨net/assignment无占用、同一scene重放逐项相等且两次调用确定，
全部满足才ok。discovery refusals原样保留供审计，不得删除、过滤后冒充A3成功；terminal失败另给具名原因。
C1.2最终必须来自真实枚举的自然本地座，不得直接采用hypothetical或测试注入坐标。

文件域仍限 `drawcompiler.py` seat-first段、`tests/test_548d_panel_seat_first.py`、新证据
`page-layout/panel-seat-first-terminal.log`；不接compile/最终接线/旗标/audit，不改placement/shared/
旧测试/真机/git。新增测试必须同时断言 `A3.ok is False` 与terminal真实终态，证明不是翻旧账；文字碰撞、
固定座变动、最终不完整各有负例。完成仍不宣称compile或视觉通过，34D-B必须消费terminal的同一场景。

### 34D-B. terminal同源生产回放与最小fixture三关（2026-11-10）

A4主代理复跑 **88 passed**，terminal终态完整而A3 discovery拒绝原样保留。本批才接 `_build_one_variant`
生产消费者，文件域限 `drawcompiler.py`、`tests/test_548d_panel_seat_first.py`、必要的同册新测试与
`page-layout/` 新证据；不改placement/core/page/CLI/DSH/Rust/旧fixture/真机/git。

必须只有一份答案：
1. panel文档由 `_seat_first_text_terminal` 给最终texts/scene/plans，build实际印出的就是这些texts；
   native-attr host row与既有extra_text_walls要同看，不能scene一套、build另一套。无panel走旧 `_part_texts`。
2. wire-style地/电源的expression clusters只由terminal assignments派生，detached仍走069本地旗；
   `_apply_flag_groups` 不再对这些net另聚簇。单脚/非wire网不被新分配器误改。
3. 每assignment的seat anchor/rotation/lead、owner、member paths进入同一lane/glyph预留；旧
   `_seat_wire_flags`/`_wire_flag_seats`不得给这些net再选座或叠旗。只改map而未预留/未移动实际glyph=失败。
4. 接线只回放本assignment的member path与seat lead；owner的单点path不画零长导线，重复共线段去重。
   不把整网交给旧 `_connect_net` 拉trunk，不在不同assignment间连线，不退回201A外框。
5. 最终每assignment恰好一枚真实旗，位置/方向/lead与plan一致；固定panel terminal逐点不变。
6. `_flag_group_audit` 对这些net改为消费同一plan和实际segments/symbols：逐脚连通、path/lead几何覆盖、
   每座一旗、assignment间无接触/跨接、跨网短接为零；不得再调 `_flag_groups` 事后重聚类。

验收：真实 `dc.compile` ok/hard0，独立逐脚分区、NC/短路、连续导体、grammar/readability通过；记录
crossings/bends/wire_length与11枚语义旗（本fixture 3V3六枚、GND五枚）及每net几何。输出新SVG，主代理
逐区目检四键、宿主供电、去耦、BOOT与LED，明确旧GND外框和3V3宿主U形回环是否消失；机器ok不等于视觉
通过。先跑新册+base+placement的88条，再跑原237条邻域与CH34无panel负控；本轮不跑全量四线。
主代理独立变异至少缺失seat分配、错误跨seat接线两项，先红后cp/hash恢复。若需改placement/shared或
无法同源回放，交具体接口/网段拒因并停止，不调near/reach/排名/页框/文字大小遮缺口。

### 34D-B0. 宿主通道进入terminal场景（2026-11-10，生产试接回滚后新增）

34D-B第一次生产试接未留半成品，drawcompiler已恢复A4 hash `2c5fa8f1…`。主代理复跑 **89 passed**，
其中新增反证证明A4 texts让U1两行进入S3宿主通道；旧texts的 `_panel_channels` 合法，A4 texts则
`layout-unsat`。证据 `panel-seat-first-replay-blocked.log`。所以不能直接消费A4 terminal，也没有新SVG或
视觉改善。A3/A4旧逻辑、拒绝与测试继续保留。

本批新增**生产用panel terminal入口**，不改A3/A4默认调用结果：先用页面自身texts计算既有
`_panel_channels`，把每条channel leg按现有 `PIN_TEXT_WALL=1` 生成真实正box；这些box同时作为
① `_part_texts` 的extra walls，② seat-first scene obstacles。可给A3/A4 helper增加默认空的可选输入，
但缺省调用与旧断言逐字节不变。用同一channel-aware terminal重排/枚举/联合选择后，再以最终texts重算
`_panel_channels`：必须无拒绝且每net每条path逐点等于初始通道；文字不得碰channel wall，所有seat/path/
lead也经含channel障碍的validator。通道变化、文字占道、seat穿道或terminal不完整均具名拒绝。

文件域限 `drawcompiler.py` seat-first段、`tests/test_548d_panel_seat_first.py`、新证据
`page-layout/panel-seat-first-channels.log`；仍不接build生产回放，不改placement/shared/旧测试/真机/git。
正例必须证明当前fixture terminal.ok、C1完整、固定terminal不动、通道逐点一致且原S3反证不再发生；
另测通道被文字/座位侵入具名拒绝及原89条。通过后才允许34D-B第二次生产接入。

B0主代理复跑 **93 passed**，`_seat_first_channel_terminal.ok=True`、18面通道墙、C1.2真实自然座
(-170,-15)，最终通道逐点一致，S3反证消失；drawcompiler=`3c5c5da7…`。第二次34D-B生产接入必须改吃
`_seat_first_channel_terminal` 的terminal.scene/plans，不得直接使用无通道墙的A4入口。原S3反证和A3/A4
默认行为测试继续保留，不得为让生产通过而删除。

### 34D-B1. label座位进入terminal场景（2026-11-10，第二次生产试接回滚后新增）

第二次34D-B生产试接再次回滚到B0 hash，主代理复跑 **93 passed**。最终反证为BOOT0标签盒
[-127,35.5,-88,44.5]同时被3V3 VBAT→VDD run与GND U1.VSS lead穿过，既有label梯子无替代座；
证据 `panel-seat-first-replay2-blocked.log`。仍无生产回放、新SVG或视觉改善。

本批新增label-aware生产terminal，不改channel/A3/A4默认结果：先取B0最终texts与固定通道，用既有
`_label_for` 真实梯子和实际part/text/channel障碍放置所有 `expression.style=='label'` 的名字；
形成可回放的 `(net,pin point)->LayoutLabel` map。随后把这些真实label boxes加入scene solids/bodies及
`_blocked_points`，重新枚举并联合选择整份seat plan。最终仍须全组完整、固定terminal不动、通道逐点一致、
文字/label/channel不碰撞，所有path/lead避开label盒；同一scene与label map重放确定。不得把BOOT0特判、
缩字、删label、调reach/near或改电路语义。

文件域限 `drawcompiler.py` seat-first段、`tests/test_548d_panel_seat_first.py`、新证据
`page-layout/panel-seat-first-labels.log`；不接build生产回放，不改placement/shared/旧测试/真机/git。
正例须证明当前fixture label-aware terminal.ok、BOOT0不再被3V3/GND穿越、C1完整、通道不变；
label碰撞、path穿label、错误label回放各负例，原93条保留。若现有label也无联合座，交候选/障碍反证停止。
通过后才允许34D-B第三次生产接入，build必须回放同一label map且后续reseat不得另选位置。

B1主代理复跑 **99 passed**。缺省fixture九网全是wire、labels空；以真实BOOT0两盒作named压力测试时，
label-aware terminal完整且U1.VSS改到(-110,85)，没有plan穿label。drawcompiler=`bb328c24…`。但这不是
生产可直接硬编码的输入：主代理实测 `_obligation_nets=[]`、旧compile labels=[]，BOOT0是新顺序造成的
generic fallback，不是既有label网。

### 34D-B2a. 信号preflight与真实fallback进入terminal（2026-11-10）

本批只补信号先行场景，不接build生产。对panel文档中所有非gnd/power、初始style=wire且不是panel host
channel的网，用既有 `_connect_net` 在页面自身texts/通道上预路由；成功的segments与leg walls必须固定，
后续文字/seat/label都避开，不得最终再换一条path。真实失败的信号按旧generic fallback变成label网，
保留原因；不能假定BOOT0一定失败，也不能把named测试标签写进生产。

preflight输出segments、逐leg `PIN_TEXT_WALL` boxes、fallback nets及原因。channel/label terminal增加默认空
的extra walls与fallback net输入：这些wire walls同时约束文字重排、label梯子和seat scene；label map除
expression label外还必须给真实fallback网每脚放名字。缺省输入保持B1及A3/A4/B0结果不变。

当前fixture预期BOOT0预路由成功、labels为空，不能再让seat-first顺序把它挤成fallback；若实测仍失败，
必须记录generic fallback并以真实label进入terminal，不伪造成功。最终label-aware terminal须全组完整、
通道不变、signal path不漂移、label/signal/seat无碰撞；新增preflight成功、真实fallback、signal墙侵入和
缺省等价负例，原99条保留。文件域限 `drawcompiler.py` seat-first段、`tests/test_548d_panel_seat_first.py`、
新证据 `page-layout/panel-seat-first-signals.log`；不改build/placement/shared/旧测试/真机/git。
通过后的第三次生产接入必须回放preflight segments/fallbacks，不得重路由或重复记 downgrade。

B2a主代理复跑 **104 passed**，但正例未达成：signal-first使LED1成为generic fallback，且U1组lead/path与
LED2/BOOT0共享顶点；signal terminal具名拒绝。证据 `panel-seat-first-signals.log`，drawcompiler=`f409bdab…`。
此路线不作为生产入口，失败反证与helper保留，不把交叉异网旗引线放行。

### 34D-B2b. 旗座→信号→成员路径的同源顺序原型（2026-11-10）

本批只验证新的完整顺序，不接build：从B0 channel terminal取得完整座位后，先把每座真实glyph与lead作为
硬障碍；再让普通信号经既有 `_connect_net` 绕开这些座位，真实失败仍generic fallback并在随后用 `_label_for`
放名；最后保持所有seat anchor/rotation/lead不动，仅为每assignment重新求member paths（信号与labels作为
foreign几何）。不得直接采用B2a的signal-first plan，不得为解冲突移动座位、删除fallback或允许T接。

输出必须含同一最终texts、channels、seat plans、signal segments/fallbacks与label map。验收：全组完整、
固定terminal不动、通道不漂移、座位逐项等于B0已选座、每member path真实合法、signal/fallback真实可回放、
文字/label/channel/signal/seat/member path无非法共享顶点，validator零失败，两次调用确定。若同座路径不成立，
点名member/seat/foreign run并停止，不在本批加多rung、重选座或迭代固定点。

文件域限 `drawcompiler.py` seat-first段、`tests/test_548d_panel_seat_first.py`、新证据
`page-layout/panel-seat-first-ordered.log`；不改build/placement/shared/旧测试/真机/git。新增正例、
同座不可达、signal/label碰撞、座位漂移负例及原104条。通过后才接34D-B3生产；性能须记录，不能反复全量
重枚举掩盖成本。

B2b主代理完整聚焦组合复跑 **108 passed**（含修正后的ordered负例），但正例未达成：同座路径10/11成立，
U1.VBAT被VSS lead挡住；一次性全局重选与VSS `_flag_alternates` 实测仍只有现座，扩枚举无解。异网引脚和
正交穿越规则本身正确，pool也不能简单删除。证据 `panel-seat-first-ordered.log` 与主代理复验记录。
因此结束draw-only顺序试验，进入ServiceSeat placement集成。

### 35. 548D3S1：ServiceSeatTemplate与共享binder（集成锁S1，未实施）

完整合同、阶段与兼容矩阵见 `evidence/548D/service-seat-criteria.md` 和 `tasks/shared-platform.md` §13。
新增draw内部 `ServiceSeatTemplate` + 默认空 `service_templates/service_plans`，复用PanelCell/binder但
**不复用panelGroups公共语义、不混入panel_plans**。PanelCell新增默认空flag_lead供以后回放，空时旧向下
行为不变；left/right单cell用本地帧复用bottom求解、cache、宿主随动与外国件检查。

S1文件域仅 `placement.py` 与新 `tests/test_548d_service_placement.py`，证据 `evidence/548D/service-seat/`。
不接drawcompiler、真实C1/R1/D、生产compile、最终旗/线、真机或git。验收left/right真实落位、宿主平移/
换姿、mismatches、cache key完整、外国件/锁/非法输入具名拒绝，空模板轨迹/JSON/CH34不变；新册与既有
panel base+placement 50条通过。S2才接base/topology真实服务支路，S3才接SeatFirstPlan与三关。

S1主代理复跑 **63 passed**，CH34 `allMatch=true`；审diff曾发现from脚未与宿主脚同轴且测试恒等式，
已修为真实from pin对齐并补左右/lattice负例。placement=`9be2c565…`，证据
`service-seat/service-seat-s1.log`、`service-seat/ch34-current.json`。S1仍未接draw或整图。

### 35A. 548D3S2：base/topology真实服务支路消费者（2026-11-10）

文件域限 `drawcompiler.py`、必要 `placement.py` 小修、`tests/test_548d_service_placement.py` 与新
`tests/test_548d_service_consumers.py`、service-seat新证据。只在显式panelGroups文档启用服务模板；
无panel文档保持旧路径与CH34。服务件来自ctx.slots二端branch，排除panel cells；owner内唯一host pin、
真实from/to、left/right pin side、横向合法pose、外侧文字、自然终端flag lead/box均由同一事实生成，
不写绝对origin、不猜多宿主、不把FlagCorridor或panel终端语义混进来。

`_Placement.service_plans` 默认空；base与topology经同一 `_service_templates` + binder消费。base在panel后、
anchor前落座并随anchor平移；topology在seed/候选/终态重投影，结果单独存service_plans并检查
`service-*` hard/mismatches。普通move/spread/series yield排除服务件，外国reserve相交具名hard；host pose
与声明side的出脚方向不符要具名拒绝，不许把旋转后的脚摆到错误阅读侧。

验收：模板恰为C1/R1/D1/D2且无KEY；C1 owner内唯一host=VDD，其余host正确；base与topology宿主相对
origin/from/to/reserve一致，from脚与宿主脚同轴，service/panel不混；空模板/CH34不变；外国件、锁、
错误side/pose与缺pin负例。跑新册、S1 63条及原panel邻域，记录耗时；不要求最终compile/视觉。
主代理独立变异至少base不消费、topology宿主候选不重投影，先红后cp/hash恢复。S3才接SeatFirstPlan。

### 35A1. S2主代理复审纠偏（2026-11-10，4条旧测试红，尚未签收）

首轮S2主代理复现 **65 passed / 4 failed**。新增消费者6条全绿，但宿主选择用“符号pin顺序第一脚”
不符合语义不猜测：必须改为既有 `_series_host_candidates(ctx,(part,),shared_net)` 过滤
`host_part==slot.owner`，唯一才接受，零/多候选具名拒绝；当前C1由此仍唯一得到U1.VDD，不是新启发式。

四条旧panel测试不得改成“允许拒绝”消红。它们是panel detour/普通foreign-yield算法单元测试，
依赖D1/D2仍为普通branch的旧几何。下一批明确允许修改这四条，仅在测试内monkeypatch
`_service_templates` 返回空，以隔离新消费者并保留**原场景、原断言、原计数**；新S2测试另行证明
模板启用和服务件不可yield。不得在生产关闭ServiceSeat，不得删负例或把红改成xfail。

同侧让位的魔数 `range(0,9)` 改为由request器件数给出的结构上限，避免新增调参预算；不降低碰撞要求。
复审文件域新增这四条旧测试与 `service-seat-s2-review.log`，其余边界不变。全69条通过、CH34复验与
两项主代理变异完成前，S2仍不签收，仍不接最终compile/视觉。

S2最终主代理 **70 passed**、CH34 MATCH，两项变异均先红并cp/hash恢复；证据
`service-seat/mutations.md`。生产hash drawcompiler=`7bfc1337…`、placement=`4d35eea4…`。

### 35B. 548D3S3：service文字与固定旗进入SeatFirst（2026-11-10）

新placement直跑 `_seat_first_ordered_terminal` 仍拒：R1文字被后续 `_part_texts` 挪到C1旗旁，
D1自动lead又走旧梯子。对账证明binder reserve无重叠，缺的是回放，不是再加间距。证据
`service-seat/ordered-probe.log`。

本批只接模板同源：`_panel_text_map` 同时遍历 `_service_templates` 的cells，按实际origin输出固定文字，
不得再让R1/D1等走fallback；`_panel_terminal_seats` 同时遍历 `placed.service_plans`，用对应
ServiceSeatTemplate.cell.flag_lead生成绝对lead/anchor/rotation。panel无flag_lead时保持历史向下，
service来源在SeatFirstPlan中明确标 `service-terminal`，不得冒写panel-terminal或混入panel_plans。

文件域限 `drawcompiler.py`、必要service测试与新证据；placement生产文件不改，不接build生产compile、
真机或git。测试须含service文字逐盒回放、4个service固定座+4个panel固定座、service/panel来源区分、
固定座不可被自动覆盖、原70条。随后直跑ordered原型，记录完整/refusal、信号fallback与耗时；
只有原型通过才接34D-B3生产。若仍有缺口，给具体net/member/obstacle，不改near/reach/页框/缩字。

### 35B1. S3合同纠偏与旧场景隔离（2026-11-10，首次接入已还原）

首次S3接入失败：直接扩 `_panel_terminal_seats` 使旧panel测试seats 4→8，并把GND误纳入panel net
分组；service固定座也改变A3/A4/B2旧期望。子代理无法可靠还原，主代理已用S2事前备份恢复
drawcompiler=`7bfc1337…` 并复跑 **70 passed**，未知工作树未作为基线。证据 `s3-incomplete.log`。

下一版必须保持 `_panel_terminal_seats` **panel-only**，新增 `_service_terminal_seats` 与
`_seat_first_terminal_seats`（合并并附source）；只有SeatFirst消费者使用合并表，旧panel compile/audit继续
读panel-only。service模板文字仍按§35B接入 `_panel_text_map`，不得触发panel_nets重分组。

旧 `tests/test_548d_panel_seat_first.py` 全部属于无ServiceSeat的算法场景：允许加autouse monkeypatch
`_service_templates→((),None)` 和 `_service_branch_parts→frozenset()`，保留A3/A4/B0/B2原fixture、
缺座与拒绝断言，不逐个改期望、不xfail。新service测试放在service_consumers或独立新册，证明模板文字、
4 service+4 panel合并固定座、source区分、不可自动覆盖及ordered原型。生产没有关闭开关。

文件域限drawcompiler.py、上述两本测试、service新证据；placement不改、不接build生产compile/真机/git。
S2 70条与旧seat-first全册均须通过；若ordered仍拒，交具体net/member/obstacle，不调参遮缺口。

S3新版主代理 **78 passed**，旧隔离seat-first全册 **58 passed**。合并固定座与文字回放成立，drawcompiler=
`bb08643f…`；但ordered仍因D1.2旗盒与KEY1 host path `(154,40)->(154,-105)` 的1单位墙相交而拒，
见 `s3-ordered.log`。服务终端并非panel net，诊断中panel terminal字样仅是既有通用文案，不能据此改分组。

### 35C. 548D3S4：panel通道成为ServiceSeat让位障碍（2026-11-10）

文件域限 `placement.py`、必要 `drawcompiler.py` 消费者、两本service测试与新证据；不接build生产compile、
真机或git。`bind_service_plans` 增加默认空 `panel_plans` 输入，把panel reserve和每条host_path leg按
`PIN_TEXT_WALL=1` 的正box加入同侧让位的taken与最终foreign复核；缺省调用形状与旧测试不变。
base在panel后传同一panel_plans；topology seed/候选/终态以及spread后都传对应重绑panel_plans，不能用
seed旧通道或只让件不让通道。service件依然不被普通move/yield挪动，host pin同轴不变，冲突无可让档具名拒绝。

验收：当前fixture D1.2 reserve与KEY1墙不相交，D1/D2仍同轴且无service/panel重叠；panel为空时旧结果、
CH34不变；补host_path碰撞、候选通道更新与无可让档负例，原78条及隔离58条通过。重跑ordered记录下一
真实状态，未过不得接生产。另将 `_seat_first_text_terminal` 的 `again_page` 与 `again != plans` 分开报告，
保留真实拒因而非统称不确定性，并加诊断负例。

### 35D. 548D3S5：service-active宿主文字看到已定位通道（2026-11-10）

S4主代理单测复现 `test_panel_terminal_seats_win_over_the_grouping_pass` 失败：base因U1文字堵panel通道而无
候选，compile退到另一placement，并非应修改的固定旗合同。ordered同样首拒S1 host lead穿U1右侧两行。
证据 `s4-ordered.log` 与单测输出。不得把该测试改接受或删除。

本批只在 `placed.service_plans` 非空时给 `_part_texts` 增加已定位障碍：panel/service reserve和panel
host_path逐leg的PIN_TEXT_WALL盒。placement已确定host_path，不需要先调用 `_panel_channels`，因此打破
“文字→通道→文字”循环。service/panel固定文字仍按模板；U1等未固定件只能在这些真实墙之外选侧，
不得特判above/left/right，不缩字、不调间距。无service_plans的旧panel及无panel CH34路径逐字不变。

文件域限drawcompiler.py、必要service测试与新证据；placement不改，不直接接生产SeatFirst回放、真机/git。
测试须证明U1文字不碰任何host path，初始 `_panel_channels` 合法，旧固定旗测试原断言恢复通过；
无service的文字与旧场景不变。随后跑ordered，记录下一真实状态及85+1组合是否全绿；仍失败给具体
net/member/obstacle，不接生产、不调参。

S5主代理 **89 passed**，旧固定旗断言恢复；ordered只剩U1.VBAT与BOOT0在(-95,10)/(-125,10)共点，
另有LED2 fallback。证据 `s5-ordered.log`。R1与BOOT0同轴直连带被C1.2固定旗挡住，说明“所有支路必须
同轴”过强；需要允许有依据的正交折线，而不是继续加外让距离。

### 35E. 548D3S6：直连优先的服务支路正交折线座位（2026-11-10）

文件域限 `placement.py`、必要 `drawcompiler.py`、两本service测试与新证据；不接build生产、真机/git。
在ServiceSeat绑定中，**零偏移直连优先**；只有直连或一弯host→from路径被其它service reserve、panel墙或
外国件阻挡时，才沿pin轴正交方向尝试偏移。偏移档位由grid/pitch与request器件数确定，零档后按固定正负
顺序，不写绝对origin、不加reach/排名预算。每候选检查两种一弯路径（非直接网不保存为panel channel），
最终 `host_paths` 仍为空，普通 `_connect_net` 决定真实线；无一弯路径合法才具名拒绝。

同侧x向让位保留，y偏移与其联合验证，from/to方向、reserve不重叠、userLock/host pose规则不变。
旧“from必须与host同轴”断言只能收紧为：**无阻挡时仍同轴；有阻挡时必有真实合法正交host→from路径**，
不得删断言或接受斜线。当前R1应通过偏移让开C1.2旗带，C1/D1/D2无阻挡仍直连； ordered复跑记录
BOOT0/VBAT及LED2下一状态，失败给具体路径，未过不接生产。跑原89条、隔离58条与CH34负控。

**S6拒收并已回滚**：偏移未解除BOOT0/VBAT冲突且R1/D2更远、LED2仍fallback，placement与测试已恢复
S5 hash，组合89 passed。随后只读路径探针证明：S5完整plan的seat lead+member paths先作真实障碍，
BOOT0/LED1可布通，LED2走既有generic fallback且label×plan=0。证据
`service-seat/s6-rollback-and-path-order.log`。不再挪器件。

### 35F. 548D3S7：path-first terminal与真实fallback（2026-11-10）

文件域限 `drawcompiler.py`、两本service测试与新证据；placement不改、不接build生产、真机/git。
新增独立 `_seat_first_path_first_terminal`，不修改旧ordered/A3/A4/B0：以S5 channel terminal的完整
texts/plans/channels为输入，先将每座glyph/lead/member path变成真实障碍；普通信号用 `_connect_net`
绕行，真实失败保留generic fallback并以 `_label_for` 放名；plan不重选、不重排文字、不做固定点迭代。

输出同一scene/plans/signals/fallbacks/label map/path walls。终检必须含逐脚与固定座、通道不漂移、
signal与plan无共享顶点/非法穿越、label与plan/text/channel无碰撞、fallback可回放、validator零失败及
两次调用确定。当前fixture应BOOT0/LED1布线、LED2两枚真实label；不得为消灭fallback再挪器件或删名字。
测试含正例、path/signal顶点、label碰撞、结果确定及原89条和隔离58条；记录耗时。只有这个独立terminal
通过后，34D-B3才消费其path walls/signals/labels/plans进入生产。

S7主代理复跑 **94 passed**，drawcompiler=`3c76b349…`，独立terminal ok=True。下一批才接生产。

### 36. 548D3B3：path-first生产回放、逐脚与视觉三关（2026-11-10）

文件域限 `drawcompiler.py`、service测试与同册新测试、`evidence/548D/service-seat/`；placement/core/page/
CLI/DSH/Rust/旧fixtures不改，不真机/git。仅 `placed.service_plans` 非空时启用
`_seat_first_path_first_terminal`；其它页面旧路径与CH34不变。

生产必须消费同一答案：terminal.scene文字（含native host row一致性）、plans派生的wire地/电源clusters、
path walls与固定seat、signal segments/fallbacks、label map。信号和panel channel逐点回放，不重路由；
generic fallback标签沿用既有载体与原因，不伪造成direct-wire。旧 `_apply_flag_groups`、`_wire_flag_seats`
不得另选一套；每assignment一旗且anchor/rotation/lead一致，跨assignment不拉线。最终audit直接读
terminal plan+实际segments/symbols/labels，检查逐脚、path/lead覆盖、跨assignment/跨网短接、signal/label
冲突，不再事后聚簇。生产可用 `replay=False` 避免内部重复，但不能省最终audit或逐脚。

验收：真实 `dc.compile` ok/hard0，3V3六枚、GND五枚，BOOT0/LED1直接线、LED2两枚真实label；独立逐脚
分区、NC/短路、连续导体、grammar/readability通过。记录crossings/bends/wire_length与各net几何，明确旧
GND外框和3V3宿主U形回环是否消失，生成 `service-seat/path-first-final.svg`，主代理逐区目检四键、去耦、
BOOT、LED与宿主供电；机器ok不等于视觉通过。跑新94条、隔离58条、原237邻域与CH34；不跑全量四线。
主代理独立变异至少缺失seat分配、错误跨seat接线，先红后cp/hash恢复。若失败交具体接口/网段，禁止调
near/reach/排名/页框/缩字或删LED2 fallback。

**B3实际结局（2026-11-10，机器候选成立，视觉仍拒收）**：生产 `_build_path_first_variant` 已接，
`dc.compile` ok=True / hard0，3V3六枚、GND五枚，BOOT0/LED1直接线、LED2两枚真实fallback；
`drawcompiler=08c1d17e…`、`placement=e2eb191a…`。缺seat与跨seat接线两项主代理变异均先红并cp/hash恢复，
CH34 MATCH，证据 `service-seat/mutations-b3.md`。主代理复跑 **99 passed / 237 passed / 58 passed**；
owner与文档卫生 **60 passed**。但主代理亲看 `path-first-final.svg`：LED1仍从(80,0)绕到
(85,-95)→(-245,-95)→(-245,25)→(-235,130)→(190,130)→(190,0)，长1220，全页4交叉，视觉拒收，
见 `visual-review.md`。扇出边界与六种信号顺序探针均未得到短直解，S6偏移已回滚。下一缺口是LED信号
走廊/标签与布局共同约束，不是再调seat档位；真实MCU/整页未验收。提交前全量pytest
**10628 passed / 25 skipped / 1 xfailed / 16 failed**（均既有），connector 608、DSH 137/1、
Rust 111/4通过，不称全绿；548E继续暂停，提交前未做git写。
