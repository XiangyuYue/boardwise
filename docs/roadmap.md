# Roadmap（统一入口）

> **三份文件的分工，先记这一条**：
> - **本文件 = 稳定层**：产品方向、版本骨架、验收门槛。改得慢，改了要岳点头。
> - `tasks/SCHEDULE.md` = **滚动层**：下几个版本的具体任务、依赖、状态。每周改。
> - `tasks/TASKMAP.md` = **全图**：所有任务（001-516+）的索引（编号/主题/状态/证据）。每批追加。
> - `docs/product-boundary.md` = **边界**：做什么、不做什么。判断「这算不算我们的活」看它。
>
> AI 开工前的最小阅读路径：本文件 §1 → §2 → 你要做的那个任务的 `tasks/<批号>*.md`。
> 不要从 `PROGRESS.md` 开头读（700 行流水账，只用于查历史细节）。

---

## 1. 当前在哪（2026-11-10）

- **当前正式版**：`v0.6.1`（2026-11-10 正式发布，`prerelease=false`、latest；tag 与 Release
  `targetCommitish` 均为 `9ffeb3b2850f8391f75700f1f3f37851a4ee4ac2`
  <https://github.com/XiangyuYue/boardwise/releases/tag/v0.6.1>）；`v0.6.0` 正式版及原始验收读数仍见
  `tasks/SCHEDULE.md`，本段不回头改写旧记录。
- **审查线继续加固**：V4 归档支持多 PCB 逐板与多文件合流守卫；EPRU 记录/tombstone 和
  PAD_NET 按一致性规则判优；非矩形焊盘间距、默认货架缺失披露、mid 去耦分类与跨视图几何
  说明已落地。041 S1/S2 提供显式跨板网络声明；541 R1/R2/R4 提供 opt-in manifest、重算和
  partial 披露闸，R3 与公开接口 allowlist 未实施。
- **绘制人工锚已通过并扩到第二拓扑**：542 反激人工锚不推翻；CH343 页完成成对支路、文字、
  旗标与关闭重开验收，CH340 第二拓扑通过编译、逐脚连通和宿主视觉三关。这里证明的是两个
  已验收拓扑，不扩大为任意电路都能自动画好的承诺；CH340 页的关闭重开仍未验证。
- **540 平台准备已收口**：审查/绘制共享模块化底座，CLI 与 DSH 工具面保持兼容；Rust 最小
  workspace、合同和双侧差分持续运行。Rust 新增库解析垂直切片不代表 Python 主流程已迁移完成。
- **V4 边界仍然明确**：归档多 PCB 逐板不等于真实多板＋库工程已验证；在线容器、部分跨视图
  语义、实时 PCB 位图与原始 PCB-A 复核仍按任务书开放。**V3/V4 的共用层、隔离层和明确
  不承诺项，统一见 [`docs/v3-v4-boundary.md`](v3-v4-boundary.md)。**
- **0.6.0 后双主线**：绘制算法与 Rust strangler 并行；shared、全量测试与真机串行。
  派单入口为 `tasks/review-line.md` / `tasks/draw-line.md` / `tasks/shared-platform.md`。
- **发版节奏**：挖洞 swarm + 上机 + 实测三闸全过才发；同一天原则上只发一版；
  **正式版一周最多一发，且何时发由岳定**（2026-10-17 岳裁）；其余版本一律**内测（prerelease）**；
  daemon 与 connector 只要求 major.minor 系列同步、补丁号独立，系列升级时两边必须同升；
  DSH 插件版本 = boardwise 外部版本，不为对齐自行改号。

---

## 2. 版本骨架（细节在 SCHEDULE）

| 版本 | 主题 | 门槛 |
|---|---|---|
| **v0.5.14** ✅ | 187c~192 + 190S 真机定标（内测） | 已发 |
| **v0.5.15** ✅ | 515B 保密闸/dsh/文档 12 洞 + 516 审查反馈 A/B/C（201C 已踢出） | 已发（正式版，10-17） |
| **v0.5.16** ✅ | 520/521/522 审查线资料获取三连 + 绘制推演简报（内测） | 已发（10-18）；notes 已标「请用 0.5.17」 |
| **v0.5.17** ✅ | v0.5.16 挖洞补做（12 条高严重级，引文闸/pin 绑引文/两规则绕档位/审计 dest…）（内测） | 已发（10-18）；全量 6360 passed |
| **v0.5.18**（内测） | 527 收口批：`IntentSource` 转发 / connector 读回页型守卫 + 信封文档 / 189A2 分类裁定 / `parts classify` + `category_trust` / 189A1·088b 结案 | 三闸：挖洞 + 实测 + 上机 |
| **v0.6.0**（正式版） | 122 E 阶段 + 高速 A 档 1~3 + 542 绘图人工锚 + 527D2/527D3 + 540 平台准备 + V4 单 PCB 首批 + #89 测量修复 | 全量 **8821 passed / 25 skipped / 0 failed**；真机 doctor 9/9、P4 lint 0/0/0；三件发布件与保密/哈希验收完成 |
| **v0.6.1**（正式版，2026-11-10 发布，`targetCommitish=9ffeb3b`） | V4 多 PCB 与记录一致性 + 041 跨板声明 + 审查证据/几何/运行时闸 + CH343/CH340 两拓扑绘制 + CH343 关闭重开 | 已正式发布（`prerelease=false`、latest）；发布快照 Python 10628 passed / 39 skipped / 1 xfailed（另有两条已登记 115/116 的 098 基线差异）、Connector 608 passed + typecheck、DSH 137/1 + build、Rust 111/4 ignored；真实样本与未覆盖边界不关闭；CH340 重开验证仍开放 |
| **v0.6.x** | 041 跨板网络（DRAFT → 细化）+ **V4 适配** + **Rust strangler**：新工具/引擎默认 Rust，例外登记；旧工具垂直迁移 | 合同对齐 → Rust 默认 → 临时 Python fallback → 删除旧实现；迁移与算法不同批 |
| **0.6.0 后（独立方向）** | **AI 电路语义编译层**：网表 → 类型化、类 C 的可读语言；AI 读编译后的电路语义，不再直接读原始网表 | 先调研语义合同与解释器/编译器边界及可验证还原；与 V3/V4 解析适配分批，不阻塞 0.6.0 |
| **v0.7.0** | Rust 接管全部受支持主流程；connector/DSH 薄适配可留 TS | 验收主流程，不追求逐行翻译全部 Python；无长期双业务实现 |
| 远景 | R5 SPICE：等**绘制过关** + **041 跨板网络**两个前置 | 前置未满足不动 |

---

## 3. 五个方向（R1-R5，指针 + 一句话）

| 方向 | 一句话 | 状态 | 详情 |
|---|---|---|---|
| **R1** 桥能力补齐 | connector 四个实测缺口（小件） | 已随 v0.5.12 落 | `tasks/roadmap/R1-bridge-completion.md` |
| **R2** PCB 审查加深 | 禁布区消费/镀铜孔/重构债/丝印闭环 | 已随 v0.5.13 落 | `tasks/roadmap/R2-pcb-review-deepening.md` |
| **R3** KiCad 第二宿主 | 第二宿主接入，先侦察后最小闭环；战略：立创和 KiCad 的 harness 都在野蛮生长期，先到吃赛道 | 侦察未开工（0.6.0 后） | `tasks/roadmap/R3-kicad-harness.md` |
| **R4** 真热更 | stub + 动态载荷，消灭「更新要重载编辑器」；实验④已过（菜单点击免重载激活） | 阶段二待立（岳裁：stub 立不立项） | `tasks/roadmap/R4-true-hot-update.md` + `outputs/R4/` |
| **R5** SPICE 侦察 | 只回答「路在哪、通不通」，不写功能 | 冻结（岳 10-17 裁） | `tasks/roadmap/R5-simulation-recon.md` |

---

## 4. 原理图绘制质量主线（当前主攻，目标「一个模块及格」）

已知病灶（岳 10-15/16 反馈）：线缠在一起、线穿过器件、GND 标识重复（该合并）、
电阻/GND 无意义翻转 180°、走线绕弯。算法层重写布局与布线。

| 批 | 内容 | 状态 |
|---|---|---|
| 201A | 旗标策略「一地一符号」+ 预览旗 136→92 | 已落 |
| 201B | 布局退火重写（33 关系全满足；拓扑搜索兜底） | 已落 |
| 201C | 布线协商（rip-up & reroute、软预留、escape） | **不复活（543H）**：旧实验因 150 落地页回归踢出 v0.5.15；当前基线未复现目标缺陷，旧 patch 对当前代码不可应用。交叉计数是独立后续账，不借它复活旧方案 |
| 201D | 落位搜索加文本行代价 | **部分落，旧方案不复活（543H）**：`pin-text` 随 525 落，`text_overlap` 由 526 撤回。当前 island 路径已在布局前计文字行租金；same-statement 指标披露独立跟进，见 `tasks/201d_text_row_cost.md` |
| 201E | A* 布线效率 | 已落；实测与边界见 `outputs/201e/evidence.md` |
| 525 | 两处真缺陷（`_elbow_route` 拐点漏检 → netlist 并点；布局缺 pin/文字行净空 → 21/21 pin 尖被埋） | 已落 `bbf85a4` |
| 526 | 走廊不是瓶颈（探针筛选零收益、reserved 非真凶、真凶是 `U4.1` 压在 `R8` 值行上沿）；`text_overlap` 撤回 | 结论已记 `898f4e4`，代码未落 |
| 520k–520v + 530A–530G | **多岛原理图**（设计 `evidence/523/DESIGN.md`）：岛内布局/连线/命名、跨岛命名、地/电源旗标、岛命令与标题栏 keepout | 已落；反激岛页 `draw compile` `ok=True`、真机 0 失配 / 10 旗标 / 标题栏零相交，证据 `evidence/530f/` |
| 542 | 反激整页编译、落图、逐脚连通、live/replay lint、宿主视觉和关闭重开持久化 | **P0 完成，岳已确认人工锚**；证据 `evidence/542/final-p4.md`、`evidence/201h/live/` |
| 543 | 拓扑角色驱动的构造式布局：**agent 声明功能岛、核心与阅读关系，解释器负责确定性几何**；CH343/CH340 两个拓扑 | **两拓扑三关通过**，随 `44901da` 提交；CH343 P38 `saved_verified`，CH340 P39 `saved_unverified`（待关闭重开）；证据 `evidence/543g/`、`evidence/543n/`、`evidence/543h/` |
| 547 | SmartMedicineBox 固件约束逻辑原理图实测：30 件 / 31 网 / 8 岛，检验复杂 MCU 与多支路 | **自动整页仍未通过；547S 已通过**：共享网按 signal→非GND→GND 统一，87 passed / 1 strict xfailed + 独立变异通过。547D 暂停于 auto 标签走廊，547E 二件串联与自动整页真机串跑未开。**547F 命名脚/编号同脚修复已验收未提交**（仅聚焦 197 passed / 1 strict xfailed + 变异，不冒充自动整页），证据 `evidence/547/` |
| 547G | **自动 / agent-adjusted 双轨**：自动线继续补通用几何；辅助线复用现有 LayoutPlan/ChangePlan，从 WiFi 单岛扩到整页，不互记成果 | **G1–G3 完成、G4 部分完成、当前暂停**：30件/31网/5NC/8岛辅助页过离线双层闸+独立逐脚/NC+逐岛视觉，主代理 lint 0E/0W/13I、宿主网表 30/30+31/31+5/5；DRC 0 error/200 warn `passed=false`，不得称通过；持久化仅 `saved_unverified`，待岳手动关闭重开。未跑完整四线；辅助成果不关闭 547D/E。详见 `tasks/547_smart_medicine_box.md` §547G |

**验收锚已达成**：反激 `draw compile` 出 `ok=True` 候选，且岳亲眼看 SVG 确认
「一眼认出反激」。542 的三关与持久化结果见 `tasks/542_schematic_3_0_nov01.md`。
这不等于任意电路都能自动画好；后续绘制算法仍以三关和人工视觉验收交付。
下一阶段目标是在**声明支持的电路族**内自动产出工程师首次可接受的图，超出能力边界则给可复现
拒因或明确转入 `agent-adjusted`；不以两个拓扑的成功推断泛化率。`tasks/548_drawing_capability_ladder.md`
把 547D 支路/标签联合几何、547E 串联语义、扰动与组合、自动整页和真机闭环拆成顺序验收批；
547G 的暂停与自动线缺口仍按原任务书分别记账。548A 冻结中查出 547D 夹具缺 `PC0` 脚（已按
真实 547A 库补回，电路与断言不动）。联合几何的杠杆是**支路体体位**；2026-11-07 的坐标窄门
（`_foreign_row_body_direction`）能让冻结夹具 `ok=True` 且 547A `--runxfail` 见绿，但同时把
飞反激页面 5 条测试改红（gate 开/关对照：5 failed ↔ 74 passed），N≥3 收窄也不分开 ⇒ 判据必要
不充分，已整体回退、strict xfail 恢复。2026-11-08 在其上补 **G9「同宿主同回流支路组」**
（同宿主、同 other 网、两脚件、组 ≥3）后，547A 命中 8/9、`--runxfail` 2 passed、出现
`[XPASS(strict)]` 后摘标，4 个负控（`201b`×2、`119`、`120`、`534`）gate 开/关均
**74 passed / 2 skipped**。**548A 完整 N≥3 面板支路出口通过（限已测电路族）**：A-R 已补 `D1`/`D2`/`BZ1` 逐脚独立断言
（七信号七节点、0 短路/分裂/未放置）；仍未跑真机、未落画布，不得记自动整页，也不泛化为任意电路。
2026-11-08 的 **548C** 把同一岛做表面扰动：A 同功能换符号 4/4、C 长网名 2/2、D 允许姿态 2/2
过；B 长位号/长值行 0/3 被结构化拒绝（**过拟合**）；E 2–3 岛组合 0/2（mcu 的 GND 7 脚被画成
4 节点）。CH343/CH340 既有 pinned 几何前后逐字节 identical。**单岛能力有边界、组合能力未打通，
仍不得记自动整页。**
2026-11-08 的 **548C2** 把 E 的拒因钉死：它与「岛数」无关——547A 自己的 mcu 用页面同一预算
（`gndClustering.radius=100`）编译**同样** 4 节点失败，547A 的绿来自出厂测试不传预算（radius=0），
535 的拆分地路径从未被这份夹具走过。真缺口是三层：模块层拆分地每簇**零命名陈述**（库无 `PWR-*`）、
页面端口用**裸成员名**查按脚号建的 `_pin_points`、页面 label 兜底**压住值文本并被竖着命名**；
「库无旗就不拆」已被反证为横穿 MCU 体的母线，不得作为实现形式。本批**生产代码零改动**（负控
74 passed / 2 skipped、547A 2 passed、CH34 pinned 逐字节不变），**仍不记自动整页**；拆分地每簇
命名陈述在库无旗符号时是否用标签（页层已如此、模块层是零陈述）**已于 2026-11-08 由岳裁定：禁网络标签、允许库内旗标；C7/C7A/C7B 三次未通过，缺口另批**。证据 `evidence/548C2/`。
2026-11-08 的 **548C3** 只做 548C2 的 ②③④：端口成员名现在过 `_profile_pin_ruler` 解析成脚号（`J1.VCC→J1.1`），错名点名拒绝；页的兜底 label 改画**自己的水平承载杆**（既有 stub 梯级、不骑模块导线、竖直杆不做），同一 mcu+lcd 模拟页从 3 条硬伤降到 **0 hard、GND/3V3 各 1 节点**；并用 strict xfail 把「547A 在页面预算 radius=100 仍失败」钉成测试（④，转绿即信号）。**①（拆分地每簇命名用标签）与「地/电源一律旗标」红线冲突，岳 2026-11-08 已裁定禁网络标签、允许库内旗标（落地由 C7/C7A/C7B 三次未过后另批），本批一行未碰**；未跑真机、未落画布、不记自动整页。证据 `evidence/548C3/`。

2026-11-08 的 **548C4** 把 548C 首棒的 B 组（长位号/长值行）拆开查：失败层不是「标签梯级不够」，而是**文字座椅的墙集里没有标签走廊**——位号与值先落座（`_part_texts`），标签后落座，93 宽的位号把 value 行拖进 MCU 的 `LCD_SCK` 行，五条 LCD 标签的四方向 × 四梯级已被占满。修法只改 `drawcompiler.py`：闸报 `texts × labels` 相撞时，把闸点名的 label 盒补进文字墙集重建 variant（≤4 轮，148 的 name-run 逃生梯同一形状），**没相撞的页面 0 轮 ⇒ 零移动**。**B1 落**：`ok=True`、1 候选 `868cc95b…`、hard 0、26/26 网 sameNode、0 短路、0 未放置，10 个长位号与 10 条长值行全部整行印出；基线几何与 CH34 pinned 逐字节不变，负控 82 tests/0 failed/3 skipped。**B2 未落**：标签压线已解，剩 159.5 宽值行在 60 节距下无自由侧（实测 2.93×–4.79× 节距下同一修复可过）⇒ 缺「节距由器件自身文字宽度解出」，尺度在 `_chain_and_shelf_layout` 的 `ahead+behind+channel×scale`，属布局层。**B3 未落**：仍卡 `layout-unsat/3V3`（库无旗符号、退化为导线后 8 脚并不上，放大页框到 ±6000 仍拒）⇒ 缺 3V3 的非导线陈述，与 548C2 ① 同族；岳 2026-11-08 已裁禁标签旗入库，落地由 C7/C7A/C7B 另批。未跑真机、未落画布、不记自动整页。证据 `evidence/548C4/`。

**548R（2026-11-08）已把审查发现沉淀为永久回归**：C3 覆盖真实 `_compile_modules + _module_ports`
并限定 xfail 的具体拒因；C4 钉住 B1 与基线零移动。主代理聚焦 **85 passed / 2 skipped /
1 xfailed**，两次源码变异均先红、恢复后绿。完整 pytest **10022 passed / 25 skipped /
1 xfailed / 16 failed / 1 warning、0 errors**：16 条均非本批新红（12 条既有货架/分类漂移、
2 条既有 115/116、2 条 Windows 环境），connector、DSH、Rust 通过；不称全绿或自动整页完成。
证据 `evidence/548R/`。

**548C5（2026-11-08）未通过，生产已还原**：B2 实际走 MCU 单侧分支座位，不是 chain pitch。
统一加距与逐件外推都使分支超过二维 `near_limit=300`；这只证明当前单列座位不能靠加距
容纳长文字，不证明所有布局无解。主代理聚焦 **87 passed / 2 skipped / 2 xfailed**，connector、
DSH、Rust 通过；完整 pytest **10024 passed / 25 skipped / 2 xfailed / 16 failed / 1 warning、
0 errors**，失败节点与 548R 相同、无本批新增。主代理另复核注入二维座位的可行性探针：
两个候选均 hard=0、26 网连通、0 短路、文字完整，**但不是自动生成能力**。下一步实现同岛
二维座位的闭式生成规则，不默认折行、拆岛或放宽 near，不记 B2 或自动整页完成。
证据 `evidence/548C5/`。

**548C6（2026-11-08）已把 B2 的同岛二维支路座位落入生产并通过离线三关**：普通构造轮与
119 加宽轮都无候选时，编译器在 201B 前启用单模块救援轮，按真实器件体、左右文字盒、引脚和
grid 闭式分配横向座位；保留各自 `rung.base`，绕针后重核 near/重叠/文字自由侧，声明 same-line、
服务支路、同 pad 与 bay 所有组均不动。B2 自动得到 1 候选 `814ed66f…`，hard=0、26 网各一节点、
0 短路、长值行完整；C5 strict xfail 实测 XPASS 后摘为 3 passed。主代理聚焦
**120 passed / 2 skipped / 1 xfailed**（四负控 74/2、C6 12、C4 4、C3 5/1），CH34 pinned
不变，两项变异均先红并 cp 恢复，最终生产候选经逐区视觉复核。修复前全量见548C6R，
最终由548C6R收口；多岛页面救援、B3/548C2①、548B 合同、548D/E 与 547G 均不因此关闭。
证据 `evidence/548C6/`。

**548C6R（2026-11-08）补上绕针后的 leg+tail 最终复核**：只读审计与主代理复现证明，bounded
walk 清不掉 tail 远端外来针时，C6 会接受跨网针重合。生产现抽出同一 `_foreign_pins_on_run` 尺，
在二维 root dodge 后复核两段，残留即整组回退，不调 GAP/其他调用者合同。新永久测试前红点名
`C1.2(GND) × S2.2(3V3)`，修后 C6 **13 passed**；主代理聚焦 **121 passed / 2 skipped /
1 xfailed**，正常 B2 几何/渲染、合法 leg、CH34 pinned 均不变，最终复核变异先红并 cp 恢复。
最终全量为 **10038 passed / 25 skipped / 1 xfailed / 16 failed / 1 warning、0 errors**，
与548R及修复前第一轮新增失败/错误均0；connector、DSH、Rust通过，不称全绿。证据 `evidence/548C6R/`。

**548C7/C7A/C7B（2026-11-08）未通过，生产零改动**：岳裁定禁网络标签、旗标可入库。
只补库、候选回退与统一聚簇三次均未出候选，主代理负证据7 passed；后续只针对聚簇与预留/
布线契约另派小批，不再连续换方向。证据 `evidence/548C7/`、`548C7A/`、`548C7B/`。

**548B1–B3（2026-11-08）已把显式二件串联从数据合同做到几何**：B1 落 `seriesBranches`
封闭五键数据合同（不写/[]不写键、旧摘要与CH34 pinned不变，新测试41 passed、主代理聚焦
369/2、两项变异恢复）；B2 落 V1–V8 跨文档校验（standalone/page 都在完整文档几何前拒绝、
跨模块由V7具名拒绝、切片只携带同模块两件；前红24/2转26 passed、聚焦423/2、本批不做几何）；
B3 让声明决定几何——每条两件 `RelativeConstraint`，`compile` 与独立 `check_grammar` 共用
`_with_series_arms`，几何按 宿主→parts[0]→middleNet→parts[1]→终端，pitch 取原布局中心距，
非GND终端轨优先在臂尾真实脚挂旗；未声明/[]不变、不自动识别；前红10/4转14 passed，聚焦
232 passed / 2 skipped，高边`9917b0b3cda9…`/低边`5eea1a442ce7…`各3候选、六点单调、middle
一段10单位，CH34 pinned MATCH。三项变异均完成（第三项先暴露⑤b覆盖洞、测试加强后复红；
恢复点`2cc92fc0…`，其后520b2兼容修复得最终hash`d9ba64ab…`）。第一轮全量18 failed/10124
passed，2条新红为520b2两条（SimpleNamespace 无 `series_branches` 属性），`getattr` 最小兼容
修后两文件21 passed，测试未改；第二轮最终 **16 failed / 10126 passed / 25 skipped / 1 xfailed、
0 errors**（`full-pytest-final.log`，与548B2基线比较 added=[]、removed=[]，16条均既有，不称
全绿）；渲染经主代理逐区目检。**548B3 正例 + 不可落座负例通过，「禁止静默回退」已落地（checker 六点检查未做，不宣称）**；仍不记真机、lint 宿主 DRC、自动整页或 548D/E 完成：548C7 的聚簇/预留/
布线缺口另批，548D 依赖自动整页复验、548E 真机未做，547G 继续暂停。完整四线：B1 pytest
**10086 passed / 25 skipped / 1 xfailed / 16 failed / 1 warning、0 errors**，B2 **10112
passed / 25 skipped / 1 xfailed / 16 failed / 1 warning、0 errors**；两次 16 条均非本批新红
（12条既有货架/分类漂移、2条既有115/116、2条Windows环境），connector **576 passed +
typecheck**、DSH **137 passed / 1 skipped + typecheck/build**、Rust **111 passed / 4
ignored + fmt/clippy**；B3 最终 pytest **16 failed / 10126 passed / 25 skipped / 1 xfailed、
0 errors**（`full-pytest-final.log`，added=[]、removed=[]），同批三线亦通过，均不称全绿。
证据 `evidence/548B1/`、
`evidence/548B2/`、`evidence/548B3/`。

**548A-R / 548B3-R 第二轮全量（2026-11-08）**：**16 failed / 10130 passed / 25 skipped /
1 xfailed、0 errors**（1505.66s，`evidence/548D/full-pytest-rs.log`）；与 548B3 基线 JUnit
比较 baseline=16、final=16、added=[]、removed=[]（`full-compare.log`）。第一轮 16 failed /
10122 passed / 33 skipped 的额外 8 个 skip 未复现；卫生 7 passed、文档钉 40 passed，不称全绿。

**548D2 / D2R（2026-11-09）两版串联座位预留均未通过，生产净零改动**：D2 首版让开 `S1` 后
`D1×D2` 且既有 B3 额外 6 红，已撤回；D2R 统一座位方程后单臂邻域 91 passed，但 MCU 仍 0 候选
（base 兄弟让开不足、topology 轮不经 `_chain_and_shelf_layout` 致 `D2` 压 `D1`）。按停止条件
不做第三轮；`drawcompiler.py` 仍 `300157d5…`，新测试 7 strict xfail + 1 控制未摘，主代理组合
28 passed / 7 xfailed。**548D 暂停于跨轮串联预留，未进入整页实施**，548E 禁止、547G 暂停。
证据 `evidence/548D/series-reservation2/summary.md`。

**548D3（2026-11-09）局部能力推进，目标尚未闭环**：base MCU 的原 7 条 strict xfail 已真实通过
后摘除；连续旗引线、相邻 power/GND 联合选档、页/岛 3V3 旗名回退与局部文字修复保留，
WiFi 单岛通过机器、逐脚与主代理放大目检，CH34 `allMatch=true`。但强制 topology 仍 0 候选，
完整八岛页需要 **1694.75×1009**、放不进固定 1170×825；MCU/整页视觉验收未签。不能把局部
成功写成 548D、自动整页或 548E 完成，也不能把未接生产消费者的 corridor binder 当成能力交付。
当前停止局部试错，权威交接与后续最小缺口见 `evidence/548D/HANDOFF.md`；548E/547G 继续暂停。
第二轮全量 **10261 passed / 25 skipped / 1 xfailed / 16 failed**，新增7条兼容回归已消除，
余16条与既有名单一致，不称全绿；connector/DSH/Rust通过，三项独立变异均先红并cp/hash恢复。

**548D3X（2026-11-10）通用页级 compact 小批通过，548D 仍未闭环**：参考辅助页普通岛框最小净距
为 40；当前 MCU/WiFi 页端口后真实框横放需 1373.5 宽、竖放需 844 高，证明只换 packing 不足以
放进 1170×825。新增默认关闭的 `pageArrangement=compact`、有限二维 packer、端口定点回放、
attach/mainPath 与旧网格回退；主代理聚焦 **215 passed / 1 skipped**，有效变异均先红并恢复。
主代理固定页实测 compact 及 compact+attach bottom 各 6 变体、0 候选，只改附着方向仍不足。
`panelGroups` 的数据、电气与页面切片校验已落，主代理 **272 passed / 1 skipped**、两项变异恢复；
base与topology `_Placement` 已真实通过2×2，默认near=300，host逃逸/spread预留/重绑与hard面积
梯度均落地，主代理两项有效变异恢复。terminal向下预留、host channel、terminal seat与模板文字已
分段回放；宿主相对route cache已落地，最小fixture `dc.compile` 已 **ok=True / hard=0**。
但主代理亲看最新渲染：2×2成立、GND外框仍在，**9交叉31弯，视觉拒收**。per-pin无座、聚簇与
seat回放不一致、簇内短接出现5簇3座；seat-first需要新合同，目标在本轮 **blocked**。
后续A新建seat-first合同，B接受 `agent-adjusted`，不得冒称automatic。真实整页与本轮全量四线未做，
548E/547G继续暂停，未做git写。

**548D3S7/B3（2026-11-10）生产候选已出，LED视觉仍未过**：ServiceSeat与path-first生产已接，
`dc.compile` ok=True / hard0，3V3六枚、GND五枚，LED2真实fallback；两项独立变异先红恢复、CH34 MATCH。
主代理亲看 `evidence/548D/service-seat/path-first-final.svg`：LED1长1220、全页4交叉，仍拒收。
下一步只处理LED信号走廊与标签/布局共同约束；真实MCU/整页未验收。提交前全量pytest
**10628 passed / 25 skipped / 1 xfailed / 16 failed**（均既有），connector 608、DSH 137/1、
Rust 111/4通过，不称全绿；548E/547G继续暂停，提交前未做git写。详见 `evidence/548D/HANDOFF.md` 与
`service-seat/visual-review.md`。

上方 201x 与早期模块级读数保留为诊断历史，不再写成「人工锚尚未通过」的当前状态。

**岳 2026-10-17 裁：「先把这一个模块画好，后面再慢慢扩展到整个电路来」**——重心从扩页
收回模块内部的可读性。模块级五个靶子（`presentation_150` + flyback circuit 的 **201x 基线读数**）：

| 靶子 | 现状 | 目标 |
|---|---|---|
| 模块居中于图框 | `occupied_ratio=2.7%`，挤在左上 | 模块整体居中，留白对称 |
| 交叉 | `crossings=12`（明细见候选 `evidence.softReasons`） | ≤4，理想 0 |
| 文本行间隙 | `min_text_gap=0`（`C11` 的值被裁） | 行间有间隙、无裁字 |
| 器件栅格对齐 | `unaligned_part_pairs=156` | 大幅下降（同列/同排成组） |
| 信号流向 | `HV` 左、`SEC_12V` 右、`GATE`/采样下（已可读） | 保持 |

这些是 201x 时的诊断基线，不是 P38/P39 的当前读数；交叉与 same-statement 文字指标仍是独立后续项。
真机只使用任务书逐字授权的测试工程与空页；**Board2/P1 是用户参考页，不是试验场**。

---

## 5. 不进这条路线的（明确不做）

见 `docs/product-boundary.md` §2。最常被问的四条：通用工艺 DRC 重造、通道层硬拼、
全自由绘制、PCB 自动布局布线——都不做。

---

## 6. 历史路线的处置

- `docs/roadmap-2026-09-18.md`：**已归档**（9-18 的基线判断，部分已被 100+ 批次的落地超越；
  保留作为「当时为什么这么判」的证据，不再作为现行路线）。
- 上游对照快照：`../work/upstream-2026-09-18/`（如有），以及 `outputs/product_audit_2026-10/`（已固化进
  `docs/product-boundary.md`）。

## 7. 审查线的资料获取分层（R6，2026-10-18 立项）

**问题**：审查报告会列出「需要补数据手册」的器件，实板一次几十上百条，工程师不会去做。
真正需要手册的是 IC / 模块 / 隔离器件（一块 98 器件的板通常 10–20 颗）；阻容电感的参数
（值 / 容差 / 功率 / 耐压）本来就在归档的目录字段里，只是没被解析。

**分层**（按成本从零到贵，前面的层吃不完才走后面）：

| 层 | 做法 | 成本 | 现状 |
|---|---|---|---|
| **L0 榨干归档** | `Type` / `LCSC Part Name` / `Supplier Footprint` / 板上 `value` / `mpn_value_code()` 三路交叉，≥2 路一致即确认，冲突记 WARN | 零（无外部调用） | **已落**（`c51e3e8`） |
| **L1 结构化料号库** | 立创/华秋的 part 参数接口，返回字段而非 PDF | 低 | 规划 |
| **L2a 地址直取** | 合法 C 号 → 立创 detail API → `pdfUrl` → 下载 → 提取 | 低（只发一个 C 号） | **已落**（520，`parts hunt`） |
| **L2b 搜索兜底** | 只有 MPN 的料：工具出工单，harness 的子代理检索，URL 回灌同一条下载/提取路径 | 高 | 工具侧已落（520 `--apply`）；harness 侧未接 |
| **L2c 提取面扩科** | 供给名白名单、中文手册、非 TI 排版 | 中 | 规划（521） |
| **L3 问用户** | 只问 L2 也没搜到的，附「查过哪些来源、缺哪个字段」 | — | 现有 |

**2026-10-18 实测修正（520）**：L2 的主体**不是** web search。夹具实测合法 C 号覆盖
42%–98%（llc 23/47、DCDC 22/29、FPC 45/56、超声波 10/24、级联驱动 45/46、级联主拓扑 28/57、
毕设滤波采样 50/56），立创 EDA 导出的板基本都带 C 号，而 `productCode=<C号>` 一次请求就给出
`pdfUrl`（实测 C2977777 → 200 + 真 PDF，1.9 s）。所以贵的那一层（搜索）只留给没有 C 号的
自购件/非立创料，而且**工具只出工单、不收搜索**——搜索是 harness 的活。

**同批实测的硬边界**：`--limit` 全跑 46 颗（24 个唯一 C 号、41 s 冷启、0 次失败）后
**0 颗 `extracted`、45 颗 `no-facts`**——包括 `UCC21520DWR` 的 52 页 TI 手册（文本读得很干净）。
根因是 `engines/datasheet.py` 的供给名白名单只有 11 个（`VCC`/`VDD`/`VIN`/`VS`/`V+`…），
`VDDA`/`VDDB`/`VCCI` 一个都不在，而 `_name_match` 用 `(?![\w])` 挡住了 `VCCI`→`VCC` 的前缀扩展。
**结论：下载通道已经通了，真正卡住的是提取面**——扩它才有下游价值（521）。在那之前，
`parts hunt` 对 IC 的实际产出是「PDF 落地 + 全文 `.txt` + 诚实标注读不出」，不是 facts。

**三档已落（522）**。`facts_verified` 不再是布尔：`facts_trust` 取
`candidate` / `machine_verified` / `verified` 三值，039 的旧布尔保留为**只读 property**
（`== "verified"`），所以三十多处旧读点语义不变。下面是**现状**，不是目标。

**L2 的子代理纪律**（岳 2026-10-18 定）：

- 并发子代理 **最多 5**（硬上限 10）；每子代理 **3–5 颗料 / 3–5 份 PDF**。真正的开销在
  「找」（3–5 次搜索 + 多个候选目录页）而不是「读」，所以限制并发比限制份数更关键。
- **PDF 与网页原文不进主代理**：子代理只回固定 schema 的 JSON（MPN / 解析出的字段 / 缺哪些 /
  来源 URL / 抓取日期 / 状态）。
- **单颗失败隔离**：状态分 `ok` / `not_found` / `ambiguous` / `parse_failed`，一颗失败不让整批失败；
  主代理汇总后再决定是报给用户还是派第二轮。
- **一颗料只取一份权威 PDF**；同 MPN 参数冲突时**不覆盖**已有 `verified`，只记冲突条，留给人看。
- **跨板缓存**：查过的料进货架，后续板子同 MPN 直接命中——第一块板可能 4–5 个子代理，
  之后通常只剩 1–2 个。

**三档可信度（522 已落）**：

| 档 | 谁来授予 | 能驱动什么 |
|---|---|---|
| `candidate` | `parts fetch` 的正则提取、`parts add` 的初稿 | 什么都不能驱动（039 的现状，未松） |
| `machine_verified` | `parts hunt --apply-facts` 过 521 的六道闸（引文逐字、页码、pin 在文档里、来源可追） | 载流 / 降额 / 间距 / dropout / 区间的**计算**；**不驱动连接结论、安规、隔离** |
| `verified` | 人工 | 全部 |

**判据：结论 vs 数字。** `FactsRule.REQUIRES_HUMAN_VERIFIED` 默认 **True**（保守）；只有真正
把事实换算成一个数的规则设 False，逐条列在 `docs/parts.md`「The gate」一节。判「接错了没有」
的（`conn-nc-and-must-connect` / `pwr-supply-on-known-domain` / `arch-nrst-closure` /
`arch-opendrain-pullup` / `arch-sense-bias-closure`）保留 True。

**报告不涂绿的物理保证**：`machine_verified` 驱动的每条 finding 都带
「参数来源：机器核验（`<url 或 file:>`），**未人工确认**」，由
`core.parts.machine_trust_note` **一个函数**生成；`completion.factsTrust` 报三个数，
这类件进 `unreviewedByClass` 的「机器核验待人工确认」桶，**不把 verdict 推向 `complete`**。

**保密**：L2 的查询只含**单个 MPN**，不带网名、位号、工程名或电路功能——批量查询料号本身
就是设计指纹。企业项目可整体关闭 L2（见 `docs/product-boundary.md` 硬边界）。

## 8. 岳 2026-10-18 的三条可读性裁定（绘制线，比「关系全过」高一层）

现有编译器只保证**局部关系**（`same-column` / `below` / `right-of` / `near`…）。
下面三条是**区域级**要求，目前没有任何一等表达——这解释了为什么「33 条关系全过、无硬违规」
的布局仍然会被工程师说「不像」：

1. **高低压分区，一眼能看出隔离带**。高压区与低压区的位置要显式声明并保持成块，
   不允许两侧的件互相穿插。
2. **拓扑核心必须在主环路里；塞不下的可以拎出去，但模块整体仍要像一个完整拓扑**。
   岳的原话：「你可以把塞不下的部分（比如 RCD 等）拆出去，但整个模块一定要像一个完整的拓扑。
   拓扑的核心部分必须保留在这个主环路里，像滤波电容以及一些简单的小外围，才可以拆出来
   放在不远处的空白位置。」
   —— 即**两级结构**：核心（core，主环路）+ 外置（drawn-elsewhere，用网络标签接回）。
   他的板子里 RCD 吸收电路就是典型的外置件。
3. **一眼认出画的是什么**。RC 必须读成 R+C 而不是 CR；Buck 一眼是 Buck，反激/LLC 一眼能认。
   顺序与相对位置要对上人脑里的拓扑图，不只是「几何合法」。

**对一句话判据的要求**（以后每批绘制改动都要过）：

| 判据 | 怎么量 |
| --- | --- |
| 隔离带两侧不穿插 | 高压区与低压区的件包围盒在隔离轴上的投影不交叠 |
| 核心拓扑连通 | 核心件集合在「网连通 + 几何邻近」下是一个连通块 |
| 外置件不越界 | 外置件不得进入主环路的包围盒内部，且必须有 label 接回 |
| 顺序可读 | 两脚件的引脚顺序（如 R 在 C 之前）与信号流向一致 |

**当前缺的东西**：`presentation.modules` 只有一个 `flyback_core`（19 件全在里面），
没有 core / drawn-elsewhere 两级；也没有「高压区 / 低压区」的声明。113 的五模块拆分被撤回，
是因为每个片段单独都不是「完整反激」——这两件事不矛盾：**需要的是「一个模块 + 两种区域」，
不是五个模块**。

## 9. 平台迁移与「hardware harness」（排期 2027-03；岳 2026-10-18 定）

**排期**：岳 2026-10-18 明确——harness 相关安排排到 **2027 年 3 月**；当前阶段的任务是
**把所有工具做好**，之后再谈 harness。本节只作为方向记录，不占当前排期。

**裁定原文要点**：这一批原理图绘制改动做完后，准备**迁到 DeepSeek Harness（DSH）**——
kimi code 已不满足开发需求；要在 DSH 上做**原生适配**，并针对它**深度适配**；最终要做的是
**hardware harness**，不是随便做一个 CLI。DSH 是开源方案，需要深入学习。

### 9.1 先把「真耦合」和「假耦合」分开（否则迁移范围会被估成全部）

| 层 | 现状 | 迁移代价 |
| --- | --- | --- |
| **CLI / exe / bridge / 规则引擎** | 完全 harness-agnostic：`boardwise.exe`、离线优先的 bridge 双轨、29 条 PCB 规则、6000+ 测试 | **零**（搬迁底座不影响它，这是过去刻意做成这样的） |
| **skill 安装** | `.kimi-code/skills/boardwise/SKILL.md`；`install-skill --harness dsh` 目前只打印 advisory、不写文件 | 小：DSH 读工作区 `AGENTS.md`，SKILL 的角色要重新分配到 AGENTS.md / 仓库内文档 |
| **子代理派发** | 由会话宿主提供（本会话用 `Agent` 工具 + worktree 隔离） | **中**：DSH 的子代理机制是它的核心能力之一，要按它的模型重写派发与验收纪律 |
| **会话 / 上下文管理** | 宿主负责；本会话靠 compaction + 手工写文档接续 | **中**：DSH 的持久状态模型要学，现有「PROGRESS/TASKMAP 手工记账」可借机变成它的一等结构 |
| **产品形态** | 现在是「CLI + skill，挂在别人的 harness 上」 | **大**：岳要的是 boardwise **本身就是一个 harness** |

### 9.2 「hardware harness」与「CLI + skill」的区别（我的理解，待岳确认）

- CLI + skill：**模型决定叫哪个命令**，skill 是给模型的说明书。skill 越写越长，因为要约束模型；
  模型变强，skill 的价值下降（岳此前的判断）。
- harness：**宿主决定怎么编排工具、怎么管上下文、怎么派子代理、怎么保存中间状态**。
  产品的护城河在编排与状态，不在提示词。
- 对硬件来说，harness 要管的东西至少包括：设计归档的读取与会话缓存、规则/审查的批处理与并发、
  多器件资料（datasheet）的检索与缓存、绘制任务的迭代与门禁、以及跨工程的料号/知识沉淀。

### 9.3 迁移顺序（建议，避免把开发停下）

1. **先收尾当前绘制工作**（398 的直连矩形 + 区域级改动）——迁移期间不碰算法，否则两边都乱。
2. **DSH 学习期**：读它的源码与文档，回答三个问题——它的工具调用协议、子代理模型、持久状态模型。
   产出 `docs/dsh-notes.md`，不写功能。
3. **原生适配第一步**：把「一个审查任务」在 DSH 上跑通（离线归档 → 规则 → 报告），
   与现有 `boardwise checkup` 的输出逐字段对拍。这一步证明底座可用，不动产品语义。
4. **再谈 harness 化**：把 skill 里的编排知识搬进宿主结构（工具、子代理、状态），
   这一步才动产品形态，需要单独立项。

### 9.4 风险

- 6000+ 测试与 29 条规则是三年积累，**迁移底座不能丢它们**；对拍（第 3 步）就是防线。
- 「hardware harness」的定义如果不清，容易做成「又一个 AI 画图工具」——这正是 `docs/product-boundary.md`
  里已经拒绝的那类产品。立项前要先把「harness 比 CLI 多出来的东西」写成可验收的判据。

### 4B. 绘制完成的验收流程（岳 2026-10-18 定：画完必须过内部审图门）

**规则**：`draw compile` 出了候选、渲染出 SVG 之后，**必须再派一个独立子代理做「看图画审」**。
审查子代理的产物是**给工程师看的人话意见**，不是指标清单；审查结论直接汇报给用户，
不允许把「几项指标达标」当作「画好了」。

**为什么必须是独立子代理**：画的人和看的必须是两个上下文。同一个上下文里刚调完布局的模型
会替自己的结果辩护——它会念 `crossings=4`、`overlap=0`，而工程师第一眼看到的是「这一团挤在
左上角」。它也不会承认「这个反激看起来像个 Buck」。

**审查子代理的输入**（只读，不写代码）：
- 渲染出的 SVG（必须真的看，不是只读 metrics）
- 布局数据：器件坐标、关系判定、`occupied_ratio`、`crossings`、`min_text_gap`
- 人类参考图（如反激辅助电源 P1：32 器件 / crossings=0 / occupancy=35.4% / bbox 1044×326）
- `docs/roadmap.md` §8 的三条可读性裁定

**审查清单（逐条给「像/不像 + 理由」，不许只给分）**：

1. **一眼能叫出名字吗**：这是 Buck / 反激 / LLC / RC 滤波？第一眼看着像什么？（对照岳的判据：
   RC 必须读成 R+C 不能读成 CR）
2. **高低压能分辨吗**：隔离带两侧是不是成块，有没有穿插？
3. **核心在主环吗**：拓扑核心件是否构成连通块；被外置的件是否只有滤波电容/小外围这类可外置件，
   且都用 label 接回。
4. **难看的地方**：器件挤成团、长直连线、线穿过器件/文字、文字压焊盘、器件朝向不一致、
   留白不均衡。要指出**具体哪个器件**，不许写「整体尚可」。
5. **和人类参考图的差距**：差在哪一维（密度 / 交叉 / 对齐 / 流向），差多少。

**审查是内部循环，不向用户提交报告**（岳 2026-10-18 补正）：图是模型画的、审的也是 AI，
所以这一环是**内部质量门**——画完 → 审 → 不过就改 → 过审才把图交给用户。给用户的只有
**图本身**（外加一句必要说明），不是审查意见。审查报告不进交付物。

**审查结论的写法**：用「工程师会怎么喷」的语气，先给结论（能用 / 勉强 / 不能看），
再点名具体器件。这份意见是**内部返工依据**，不是给用户读的文档。

**最终通过权在用户**：过审只代表「敢拿给用户看」；用户看了点头才算通过。

---

## 10. 540 后的双主线与集成锁（2026-10-25）

### A. 绘制算法线

多岛、布局/布线、文字/旗标与真实设计继续按 `tasks/draw-line.md` 独立派单。每批仍过
机器闸、逐脚连通、视觉自审三关；0.6.0 的「一眼认出反激」最终由岳判，不用平台迁移
或 DSH 工具数量替代。CH343/534 等既有工作按各自任务归属，不并入 540 邀功。

### B. Rust strangler

顺序固定为 **纯函数/几何 → parser/model → review → draw → daemon 最后**。0.6.x 新工具/
引擎默认 Rust，例外必须登记；旧工具按「合同对齐 → Rust 默认 → 临时 Python fallback →
删除旧实现」做垂直切片。进程边界优先 Rust CLI + structured JSON，不引入 PyO3/WASM/
Node native addon；Python fallback 只过渡，不形成长期双业务实现。0.7.0 验收受支持主流程，
不要求逐行翻译全部 Python，connector/DSH 薄适配可留 TS。

### 共享平台

review 与 draw 可以独立派小批，shared parser/model/bridge/core/CLI 的变化一律进入
`tasks/shared-platform.md` 的集成锁。迁移与算法变化不得同批；shared、全量测试与真机串行。
540B 的行为证据见 `evidence/540/b-behavior-equivalence.md`，540C 的完成定义见
`tasks/540c_rust_platform.md`。任何发布、真实工程写、git 写或 worktree 操作仍需岳逐次批准。
