# 绘制线派单入口（540B8）

> **当前落点（2026-11-22，分线提交已完成）**：NC/共享bridge/recovery/关系锁/transport 已分别推送，算法提交为 `319a76e`。原生候选兼容修复保留最近带与成对桶顺序，expanded 仅 native-attr 或空 legacy 启用，新旗座计划仅 native-attr 生效；P5 与雷达座席回归随提交。修复后全量 **12039 passed / 22 skipped / 2 xfailed**，仅 `test_193` 的 POSIX chmod 环境失败；connector **893 passed**、DSH **218 passed / 1 skipped**，Rust/两端构建均通过。后续新功能仍须逐批验收，不以本次集成结果替代新页面三关。
>
> **当前派单（2026-11-19）：A/B及C普通标签窄修复已有源码验收，进入本地beta 2集成**。A入口已校正；B1保存page候选预检父验97 passed，B2 DSH工具父验50 passed、typecheck/build通过，见[B1](../evidence/draw-reliability-b1/README.md)、[B2](../evidence/draw-reliability-b2/README.md)。C1/C2用3件2岛复现并修显式reserve普通非service载线，父验70+10 passed、三独立因果变异检出并恢复；默认关闭四候选几何保持，见[C证据](../evidence/draw-reliability-c/README.md)。owner与CLI合同漂移现已修，打包和当前未提交内容提交已获用户授权，最终读数见[本地包任务](063_beta2_local_package.md)。下一批先离线回放原会话失败输入，service名称冲突与真实符号模块分别验收；未校准旧输入不落图。实际DSH端到端与新三件套真机激活仍待验。不夹带迁移，不把合成通过当任意布局质量已修复，见[方案](../docs/draw-reliability-plan.md)。
>
> **沿P48已完成结果继续**：`test V4/P48` 的30件/31网/5NC/8岛为agent-adjusted reference replay；GND已修为28枚0°、网表前后一致、lint 0E/0W/9I、原生图已目检。持久化仍saved_unverified，DRC历史206 WARN groups、passed=false。见[P48交接](../evidence/v4-fullpage/HANDOFF.md)。不要重画药箱、不重启U1.18/P145、不做eprj2绘图开发。
>
> **默认输入纪律**：新设计先按用户要求固定电路与目标，不能因有现成三件套自行换设计。547A是旧逻辑草图，未校准profile不能落图；P48旧page/recipe未随现场GND修复改写，不能当修后可执行输入。选用真实符号/物理脚号/文字与姿态后，再按既有计划与三关验收推进；B/C不得另造builder/router或绕计划闸。
>
> **资产路由**：[当前资产索引](../docs/draw-assets.md)；`evidence/draw-assets/manifest.json`仅为2026-11-17历史快照，本批未更新。HEAD `75347ab53068a5efe3c1cbce454474dff113e6d9`，混合未提交保留，无Git清理授权。

## 历史自动线入口（保留追溯，不构成当前派单）

> **历史派单（2026-11-17，548P145，现暂停）：先查U1.18名称盒与标签回放**。P142联合detour+foreign、P143多成员度量、P144固定glyph场景均已验收；完整整图首拒已前移为U1.18。证据 `evidence/548P144/README.md`，任务书 `tasks/548p145_u18_label_replay.md`。
>
> **当时生产与输入**：HEAD `108e42d`；drawcompiler SHA `976a4c2cad08804f994466419950e498aae2296a49de0b87536a72a7a653b2ea`，placement SHA `0674eb3842529fe280d06dc59c426f9eda7a1789cd0a1c35b86e89244596bb82`，pagecompiler SHA `28b2907d8904da9917a64d3015ae8fd37619313abfaf6a6ee3987e7763628e1c`（P142/P143/P144未提交）。输入 `evidence/548P125/circuit.full.g3c.pinmap.json` + `evidence/548P126/full.presentation.service-feedback.json`。
>
> **当时任务约束（现不再派发） `tasks/548p145_u18_label_replay.md`**：先捕获U1.18 far/bbox/run、LED2_K/LCD_SCK channel与名称回放；不得删除名称、移动固定terminal、扩reach/GAP/预算/页框或恢复P124实验。完整30件/31网/4NC仍未出候选，LCD automatic另列；P142/P143/P144未提交实现保留。
>
> **当时资产索引（manifest为历史快照）**：`docs/draw-assets.md` 与 `evidence/draw-assets/manifest.json` 为当时资产路由；此前整理仅经批准将12个可再生目录送回收站，其他资产未移动或删除。
>
> **P113 历史侦察结论（2026-11-16）**：P113 已证伪固定近档 corridor：仅 router `16 failed / 16 passed`，仅 gate `6 failed / 26 passed`。真实旗位提前选择缩到 `11 failed / 21 passed`，P64 全绿、U1 仅余 text-on-wire，但全局启用会改变 P54/P6 尝试次数和 P55 旧座位，不能直接落生产。当前 `drawcompiler.py` SHA-256 仍为 `25ef2fc17fdf058683d81ecf426c54212acb89afb0bf41331e594cc4950df9c5`，HEAD `504e766450453d5a10abef03c6f2263f29d910bf`，混合未提交保留。证据 `evidence/548P113/README.md`。
>
> **P113 当时证据**：固定近档 corridor 在 gate/router 两点都过约束；全局提前选旗虽让 P64 恢复、U1 只剩 text-on-wire，却改变 P54/P6 尝试次数和 P55 座位，因此未落生产。完整矩阵见 `evidence/548P113/README.md`。P114 已把接缝进一步收窄到 compile 最外层，以上述 P114 实现/验收边界为准。
>
> **P112 历史停止点（2026-11-16）：未验收，生产净零**。P111 的 J2.GND 旗引线撞既有 3V3 是实际冲突，但三轮 corridor 实现均未通过邻域：A 全脚预留为 `22 failed / 59 passed`；B 仅 host 未覆盖脚后原旗位拒因消失、转入 3 条 text-on-wire；C 加 seat 铜线文字墙首轮 `7 passed`，12 文件为 `14 failed / 69 passed`。根独立只放 B 窄 corridor，同四个失败文件复现 `14 failed / 12 passed`，原码为 26 passed，证明硬 corridor 本身堵掉既有 PWR rail 旗位和 BOOT0 路径。当前 `drawcompiler.py` SHA-256 仍为 `25ef2fc17fdf058683d81ecf426c54212acb89afb0bf41331e594cc4950df9c5`，HEAD `504e766450453d5a10abef03c6f2263f29d910bf`，混合未提交保留。详见 `evidence/548P112/README.md`。
>
> **P112 当时的停止裁决（已被 P113 侦察完成）**：三轮 corridor 均撤回；固定近档硬盒不可再用。保留的 `tests/test_548p112_local_flag_corridor.py` 是洞口证据，基线 helper AttributeError 不算验收。P44 关系仍以 `evidence/548J/wifi-canvas/agent-adjusted/RULES.md`、`evidence/548M/p44-comparison.md` 和 `docs/draw.md` §Baseline 为准，不复制绝对坐标。P113 未跑 WiFi、全量、真机、渲染或视觉，无 Git 写、移动或删除。
>
> **P111 原始证据（2026-11-16）**：当前 P44 WiFi 三组页原 compile 为 23.97s、0 候选、7 变体拒绝。J2.GND 旗位追踪记录 480 个候选，其中 336 个引线与 3V3 段冲突；另有 ESP_IO0/文字/实体障碍，其他变体还报 VCC→3V3 rail 无路径和 ESP_RXD 段撞 J2。本批只读审计确认 `_flag_seats` 只作为 placement 软成本，joint service seat/rail/local flag 没有显式消费；这是机制线索，不是修复证明。下一位先读 `evidence/548P111/README.md`、`compile.json`、`j2-ground-flag-trace.json`，在原 build/route/flag 链内做单缺口修复，配因果断言、变异先红，再过编译/逐脚/视觉三关。禁止调 GAP/页框/reach/预算凑过，不新建 builder/router，不改 shared/review；旗标处不打网络标签。源码 SHA-256 `25ef2fc17fdf058683d81ecf426c54212acb89afb0bf41331e594cc4950df9c5`，main HEAD `504e766450453d5a10abef03c6f2263f29d910bf`，混合未提交工作树保留。

> **P111 前检查点（548N2）**：N2修好组座位避让开放端口房间；当时真实三组页仍报`J2.GND`地旗无可用直立挂位，R4/R5/R6旧距离只是诊断，不是接受阈值。N2细节见`evidence/548N2/README.md`；当前停止点和下一侦察以 548P112 为准。

> **LCD automatic 仍未验收（次序在 WiFi 三组页之后）**：P108独立复算10/10脚且旗标分组与P47一致；五个信号标签脱离10单位carrier，C4目标姿态缺原生图形。P109一次原compile证明五个carrier均为10，尽管输入`stubMin=40`。证据`evidence/548P108-independent/README.md`、`evidence/548P109/`。后续只读记录40至10各档拒因和label框变换，再局部修原carrier/label链；不改P47功能关系，旗标处不打网络标签。

> **P97/P98（2026-11-16）**：LCD已按用户请求放入 `test V4/P47` 并由用户调整。以
> `evidence/548P97/human-reference-summary.json` 和原生PNG为人工参考：去耦/VCC同行；C4.2和J1.2
> 共本地地旗，J1.7独立地旗；五个信号等长有名桩。10脚7网调整前后相同。
> 用户明确“打了旗标就不要打网络标签”；既有apply已支持，本次手动脚本调用错误已改，生产未改。
> 只作人工参考；继续优化原解释器，不能把人工坐标抄成automatic。

> 这是 draw 线的任务路由。画图交付仍受 `AGENTS.md` 的三关、
> `docs/schematic-style-spec.md` 与画法宪法约束；解耦不改变任何算法验收锚。
>
> **开工前必须加载 `boardwise-draw` skill**
> （`.agents/skills/boardwise-draw/SKILL.md`；`.kimi-code/skills/boardwise-draw/SKILL.md`
> 是它的逐字节副本）。分岛/合岛的提交条件、成对支路一致性、机器闸与视觉闸互不替代
> 的裁决都以它为准；漏加载等于没有验收口径。通用 SOP、R1–R3 与真机纪律仍以
> `boardwise` skill 为唯一权威。

> **P94/P96更新（2026-11-16）**：原S20分行已复用于严格声明的input链；父独立禁helper3红/去碰撞3红，cp+SHA恢复后63 passed, 1 warning in 60.23s (0:01:00)。drawcompiler当前c8c49503…29f07d，grammar618529e3…170c5。
> 只完成合成机制：四器件文字standoff均26.5、8脚5网；真实LED/ATTR旋转/视觉未验，独立地旗仍开放。P95只是静态方案。根已接管用户要求的LCD人工调整起点（P97）；子链不再派实施、不碰bridge，写锁已交根。证据`evidence/548P94/`、`evidence/548P96/`。
>
> **P90–P93更新**：生产方向真实一次build与P82全plan/change精确相同。P91仅更正LED内部直连语义，原build通过；父P93独立核对8脚5网、内部15/15直线与两负控，原计划4件6线1旗10attr。内部tap/name均已去掉。
> 父已亲看P93原生器件/实际ATTR诊断：文字仍同侧，共地旗仍待改，视觉未过。P94正复用原_part_texts的P38上下分行；P95只读设计独立链终端共享键。新输入`evidence/548P91/full.presentation.json`；证据`evidence/548P90/`–`548P93/`。未跑整页/真机/全量。
>
> **P82–P89更新**：LED方向机制已过独立验收，整图/视觉仍未完成。P87仅原grammar读取两条等臂input链的既有方向；父P89禁helper7红、放宽门控15红，逐轮cp+SHA恢复，聚焦96passed/1warning。grammar当前618529e3…170c5，drawcompiler仍81422c73…bd4a86。
> P82一次原topology内存方向验证可构建，P86独立8脚/5网及原module_plan一致；P84原生姿态/真实ATTR诊断被视觉拒收（文字同侧、内部多余抽头、独立支路共GND待改），未签LED完成。
> P83的pair None是首选无冲突时的no-op，不能说明无解或直接修复rail入口。LCD同网旗重叠仍开放。
> 证据：`evidence/548P82/`、`548P83/`、`548P84/`、`548P85/`、`548P86/`、`548P87/`、`548P89/`。P90正做一次生产版本真实输入消费；P88只读查语义输入与现有文字链。无新整页/真机/全量。
>
> **当前接续（2026-11-15，用户已恢复工作）**：智能药箱 automatic 整图未完成。
> P67 完整轨迹证实零长度提前返回使横向无转折轮不执行；根独立冻结反证及 P69 整链
> 反证成立；P70 原梯级终止已独立验收，J1.2 预留可通过。P71 已定位 J1.7 的 LCD_BLK 标签首墙，
> P72 整链传入所有 service_walls 会堵回 J1.2，前提不成立，生产/测试零改动。
> P73 已结束：一次原 compile 7.231567s，基础6/二维6/拓扑1共13尝试，0候选。
> P75 原 LED 载体机制通过 P78 两项独立变异及恢复51passed，但真实LED仍0候选，输入载体方向待查。
> P76 旧按键原生图S20未过，UART/SWD原module_plan拒绝。P79仅传lead bodies的整链仍有GND重叠3hard；P81证实同网旗glyph未反馈下一旗，补墙后无座，P83正评估原联合走廊。
> P80证实LED同排35与40短桩冲突；signal grammar未消费input=left，P82正做一次内存方向反证。以上均未实施，不能算完成模块。
> 保持原输入、预算、reach 与页框，证据见 `evidence/548P71/`、`evidence/548P72/`。`evidence/548P67/TOOL-V2.md`、
> `parent-zero-tail.json`、`evidence/548P69/report.json` 为证据；详见 `docs/handoff.md`。
> P66 两派生姿态已独立复算，仍仅 derivedPose；LED grammar、整页及真机保持未完成。

## 1. 业务边界

| 可以派给 draw 线 | 不应夹带 |
|---|---|
| PresentationSpec、LayoutPlan/PageLayoutPlan、岛/archipelago、候选/verify | review 的 Finding、severity、triage/finalize 或报告结论 |
| 布局/布线、文字/旗标、pageframe/textmetrics、draw apply/lint | shared parser/model/bridge 的顺手重写 |
| edit 引擎与画布写侧（edit 不另设第三业务线） | 复制 rules.facts / rules.decap 的电气判断 |
| `commands/draw.py` 的 draw/edit/layout-lint/pintable/validate 注册分派 | review/shared 命令或 apply 的新 DSH 暴露 |
| DSH 离线 `boardwise_draw_compile` / `boardwise_draw_lint` | live page、daemon、apply 或 TS 侧业务判断 |

依赖方向只能是 **draw → shared / draw**。地网域/自动网名、NC/引脚连通、去耦库存与
CapDecision 只从 shared 公共合同读取；不得靠 import review 或复制函数“走捷径”。

### 工程实现约束（岳 2026-11-14 补充）

1. **复用现有解释器与绘制规则。** 优先在既有解释器、build/route/flag/text 链上优化，
   不另起解释器或并行规则体系，不用第二套实现绕开现有缺口。
2. **控制模块与代码耦合。** 明确输入、输出与模块职责，减少跨模块内部状态依赖；
   不堆积临时变量、重复派生值和一次性状态。保留能说明含义的命名中间值，
   不为减少变量而把复杂计算塞进长表达式，也不为了拆函数扩大接口。
3. **工具优先考虑 Rust。** 新增独立工具优先使用 Rust，并复用现有 Rust workspace 与合同；
   现有解释器的局部修复沿原链进行。算法优化与语言迁移分批，
   不因使用 Rust 而再造一套绘制引擎；平台边界见 `docs/rust-platform.md`。
4. **审查线与绘制线独立。** 不新增 draw→review 或 review→draw 依赖；
   共用能力只经 shared 公共合同，shared 变更单独走 `tasks/shared-platform.md` 集成批。
   派单文件域不重叠，不借共享文件或可变全局状态把两线绑在一起。
5. **代码可读性优先。** 使用清楚的命名、显式步骤和单一职责；可以多写几行，
   不为节省 token 压缩成难读的一行、嵌套表达式或隐式控制流。

## 2. 公开入口与算法锚

- CLI：`draw`、`edit`、`lint`（layout lint）、`pintable`、`validate`。
- DSH：新增的两个工具仅走离线 `draw compile` 与 `draw lint --snapshot --render`；
  旧 8 个工具顺序不变，新工具是第 9/10 个，没有 `boardwise_draw_apply`。
- 0.6.0 的绘制门槛仍是：反激 `draw compile` 出 `ok=True`，且岳亲眼看 SVG
  「一眼认出反激」。机器 `ok=True` 不等于这道人的门槛已经关闭。542 的 P4 已于
  2026-10-27 同时通过逐脚、lint、主代理/独立代理视觉、岳人眼与重开 `saved_verified`；
  这只关闭该候选，后续新页仍须各自过三关。
- 任何要交给用户的原理图必须依次过：① 编译/可读性 `ok=True`；② 对照源网表逐脚连通；
  ③ 渲染后逐岛视觉自审。缺一不交付，也不许把失败候选落到真实画布。
- **547 当前派单入口（已暂停）**：`tasks/547_smart_medicine_box.md` §547G。自动与 agent-adjusted
  分轨记账；G1–G3 完成、G4 部分完成，辅助整页为 30件/31网/5NC/8岛，已过离线双层闸、独立
  逐脚/NC 与逐岛视觉，但 DRC 非通过、持久化仅 `saved_unverified`。下一派单只做暂停后的收口：
  岳手动关闭重开 test V4 后只读比对，再跑完整四线与卫生检查、最终复验；不重开 G1，不借辅助
  成果关闭自动线 547D/E，也不宣称自动整页或可投板。
- **后续自动能力派单（当前阶段见 `tasks/TASKMAP.md` §0 与下方 548A–548R 各条、任务书 §17 的 548A-R/548B3-R 与 §18 的 548D2/D2R 结局）**：`tasks/548_drawing_capability_ladder.md`。从已完成的
  547S 之后，按 N≥3 支路/标签走廊 → 显式二件串联 → 扰动与多岛组合 → 547 自动整页 → 真机
  闭环推进；每批只关一个通用缺口。548 不改变上述 547G 暂停收口，`automatic`、
  `reference-replay`、`agent-adjusted` 分开记账。
- **548A 窄门尝试（2026-11-07，未通过，已回退）**：冻结与夹具缺脚修复照旧（`evidence/548A/`，
  `repro.py` 从冻结夹具回读编译）。本批试过坐标感知窄门（`_foreign_row_body_direction`，G1–G8，
  只在「另一脚落在宿主外来网引脚行」且行向体位有合法位姿时改体位）：冻结夹具命中 8/9、547A
  `--runxfail` 见绿并出现 strict XPASS。但 gate 开/关对照证明它同时改红飞反激页面 5 条
  （`201b`×2、`119`、`120`、`534`；gate 关 74 passed），N≥3 收窄也不分开 ⇒ 判据必要不充分。
  **已删除该函数、恢复原调用点、恢复 strict xfail**；复验 `1 passed, 1 xfailed` 与附带 4 文件
  `74 passed, 2 skipped`。未跑真机、未落画布、不宣称自动整页；下一派单先补**语义**条件
  （重复支路组），不调坐标阈值。**548B 的串联语义合同仍不属这批。**
- **548A 语义窄门（2026-11-08，完整 N≥3 面板支路出口通过，限已测电路族；A-R 补齐灯/蜂鸣器独立断言）**：按上一份证书 §7 补 G9「同宿主同回流支路组」
  （同一宿主、同一 other 网、两脚件、组 ≥3；只读网表拓扑与符号脚数，不读坐标/权重）。
  生产落 `_foreign_row_body_direction`（G1–G9）+ `_same_return_bank`；547A `--runxfail`
  2 passed、出现 `[XPASS(strict)]` 后摘标（断言未动）2 passed；4 负控（`201b`×2、`119`、
  `120`、`534`）gate 开/关均 **74 passed / 2 skipped**。证据
  `evidence/548A/narrow-gate-semantic-certificate.md`。**仍不记自动整页**（未跑真机、未落画布）；
  **548B 不属本批。**
- **548C 扰动与组合（2026-11-08，部分通过）**：固定 547A 电气夹具，A 同功能换符号 4/4、
  C 长网名 2/2、D 允许姿态 2/2 过；B 长位号/长值行 0/3 被结构化拒绝（**过拟合**）；
  E 2–3 岛组合 0/2（mcu 的 GND 7 脚被画成 4 节点）。CH343/CH340 既有 pinned 几何前后
  逐字节 identical。未跑真机/未落画布；证据 `evidence/548C/`。
- **548C2 多岛共享电源网统一（2026-11-08，未通过；批次前提被证伪）**：判据先写成文
  （`evidence/548C2/criteria.md`，C1–C6 + P1–P5 预测），8 个只读探针。E2/E3 的拒因**不是多岛**：
  547A 自己的 mcu 用页面同一预算（`gndClustering.radius=100`）编译**同样** 4 节点失败，547A 的绿
  来自出厂测试 `dc.compile(...)` 不传预算（radius=0），535 拆分地路径从未被这份夹具走过。真缺口三层：
  ① 模块层拆分地每簇零命名陈述（库无 `PWR-*`）+ `BZ1.2` 悬空；② 页面端口用裸成员名 `J1.VCC` 查按
  脚号建的 `_pin_points`；③ 页面 label 兜底压住 `texts[7] 'LED'`、`segments[20]` 竖命名。
  **「不拆」已被反证**（GND 母线横穿 `parts[U1]`），不得作为实现形式。**生产代码零改动**；4 负控
  74 passed / 2 skipped、547A 2 passed、CH34 pinned 逐字节不变。**2026-11-08 岳已裁定：禁网络标签、允许库内旗标**——该命名陈述只能走库内旗标，落地由 C7/C7A/C7B（三次未通过）另批。证据 `evidence/548C2/`。

- **548C3 页面端口成员名解析 + 页 label 兜底承载杆（2026-11-08，②③④ 已落，① 未碰）**：判据先写成文（`evidence/548C3/criteria.md` C1–C6 + P1–P6）。② `J1.VCC` 这类成员名经 `readability._profile_pin_ruler`（脚号优先、再脚名）解析成 `J1.1` 再查 `_pin_points`，错名点名拒绝；③ 页兜底 label 不再把模块导线变成名字载体，改画**自己的水平承载杆**（既有 40…240 stub 梯级 × 端口朝向排序的成员脚 × 水平两向；有同向短桩则从远端续画；竖直杆不做），模拟页 0 hard、GND/3V3 各 1 节点；④ 新增 strict xfail 钉住「547A 在页面预算 radius=100 仍失败」。新测试 3 passed / 1 xfailed；4 负控 74 passed / 2 skipped、547A 2 passed、CH34 pinned 逐字节不变。**①（拆分地每簇在库无旗符号时用标签陈述）与交付红线冲突；岳 2026-11-08 已裁定禁网络标签、允许库内旗标，落地由 C7/C7A/C7B（三次未通过）另批，本批一行未碰。** 证据 `evidence/548C3/`。
- **548C4 长位号/长值行文字压线（2026-11-08，B1 落、B2/B3 未落）**：判据先写成文（`evidence/548C4/criteria.md` C1–C6 + P1–P7，写于任何 `src/` 改动之前）。失败层实测（只读探针，不是推断）：文字栈按「最宽行定宽、以器件为中心」落到 above 侧，93 宽位号把 value 行拖进 MCU 右侧 `LCD_SCK` 行；`_part_texts` 的墙集只有 keepout/别家体与引线/已落文字，**没有标签走廊**（`expressions` 11700 才算、标签 12085 才落座），标签自身 4 方向 × 4 梯级已被五条 LCD 标签占满 → 回退首选方向。修法只改 `drawcompiler.py`：`_build_one_variant` 增 `extra_text_walls`/`text_repair_round`，闸报 `texts[i] × labels[j]` 时把闸点名的 label 盒补进文字墙集重建（≤ `TEXT_LABEL_REPAIR_ROUNDS`=4，148 逃生梯同一形状），**没相撞的页面 0 轮 ⇒ 零移动**。B1 `ok=True`、1 候选 `868cc95b…`、hard 0、26/26 网 sameNode、0 短路、0 未放置、10 个长位号与 10 条长值行全部整行印出（无隐藏/缩写/折行）；基线几何 `b71fcbcf…` 与 CH34 pinned 逐字节不变；负控 82 tests / 0 failed / 3 skipped。**B2 只剩 159.5 宽值行无自由侧（实测 2.93×–4.79× 节距下同一修复可过）⇒ 缺「节距由器件自身文字宽度解出」，尺度属 `_chain_and_shelf_layout` 的 `ahead+behind+channel×scale`，布局层未落；B3 仍卡 `layout-unsat/3V3`（库无旗符号，放大页框到 ±6000 仍拒）⇒ 缺 3V3 的非导线陈述，与 548C2 ① 同族；岳已裁禁标签旗入库（C7 三次未通过、另批）。** 未跑真机/未落画布。证据 `evidence/548C4/`。
- **548R 审查整改（2026-11-08，只补测试与文档、无生产改动）**：`tests/test_548c3_page_port_members.py` 加经过 `_compile_modules` + `_module_ports` 的正向回归，`tests/test_548c4_text_label_repair.py` 钉 B1 正向与基线零移动；聚焦 **85 passed / 2 skipped / 1 xfailed**。两次独立变异：C3 源码 `preferred` 改错 → **1 failed / 4 passed / 1 xfailed**，恢复后 **5 passed / 1 xfailed**；C4 把 `TEXT_LABEL_REPAIR_ROUNDS` 置 0 → **3 failed / 1 passed**，恢复后 **4 passed**。恢复哈希 `pagecompiler.py` `975e6b1c…`、`drawcompiler.py` `9c4e5264…`。完整四线已执行：pytest **10022 passed / 25 skipped / 1 xfailed / 16 failed / 1 warning、0 errors**，16条均非本批新红（12条既有货架/分类漂移、2条既有115/116、2条Windows环境）；connector/DSH/Rust通过，不称全绿；547G 仍暂停，不借本批关闭 547D/E、自动整页、真机或 547G。 证据 `evidence/548R/c3/`、`evidence/548R/c4/`。

- **548C5 B2 文字宽度节距（2026-11-08，未通过，生产已还原）**：统一加距与逐件外推均使 MCU 单列分支超过二维 `near_limit=300`，不证明所有布局无解。新增 `tests/test_548c5_text_pitch.py` 为 **2 passed / 1 strict xfailed**；主代理聚焦 **87 passed / 2 skipped / 2 xfailed**，connector/DSH/Rust 通过；完整 pytest **10024 passed / 25 skipped / 2 xfailed / 16 failed / 1 warning、0 errors**，失败节点与548R相同、无本批新增。注入二维座位的探针经主代理复核为两个候选、hard=0、26网连通、0短路，非自动生成能力。下一批实现同岛二维支路座位的闭式生成规则，不默认折行、拆岛、放宽 near 或手填坐标；B3/①仍独立待裁。证据 `evidence/548C5/`。
- **548C6 同岛二维支路座位（2026-11-08，离线三关已过；548C6R已收口）**：单模块救援轮只在普通与119加宽轮均无候选时启用；按真实文字/器件/引脚度量闭式分配 line 轴座位，保留 `rung.base`，绕针后重核 near/碰撞/文字侧，并排除 same-line/service/shared-pad/bay 所有组。B2 自动产出 1 候选 `814ed66f…`、hard=0、26网连通、0短路、全文完整；C5 摘标后 3 passed，C6 12 passed。主代理聚焦 **120 passed / 2 skipped / 1 xfailed**（四负控74/2）、CH34 pinned不变，两项变异先红后cp恢复，最终渲染逐区目检通过。B3/548C2① 已由岳裁定禁网络标签、允许库内旗标（C7/C7A/C7B 三次未通过、另批），548B 合同已由 B1–B3 落地；多岛页面、548D/E、真机与547G未因此关闭。证据 `evidence/548C6/`。
- **548C6R 绕针后 leg+tail 最终复核（2026-11-08，已通过）**：只读审计与主代理复现发现 tail 远端跨网针重合会被接受；现用同一 `_foreign_pins_on_run` 尺在 dodge 后复核两段，残留即整组回退，不调 GAP。C6 增至 **13 passed**，主代理聚焦 **121 passed / 2 skipped / 1 xfailed**，正常B2几何/渲染、leg对照与CH34 pinned不变，最终复核变异先红后cp恢复。最终全量 **10038 passed / 25 skipped / 1 xfailed / 16 failed / 1 warning、0 errors**，与548R及修复前第一轮均无新增失败/错误；connector/DSH/Rust通过，不称全绿。证据 `evidence/548C6R/`。
- **548C7/C7A/C7B 库内旗标路线（2026-11-08，未通过，生产零改动）**：岳裁定禁网络标签、旗标可入库。只补库、候选回退、统一聚簇三次均未出候选；主代理负证据7 passed。实际剩余缺口是聚簇与预留/布线契约，不再连续换方向；C3 strict xfail未摘。证据 `evidence/548C7/`、`548C7A/`、`548C7B/`。
- **548B1 seriesBranches 数据合同（2026-11-08，通过；完整四线已跑）**：岳全部按推荐。封闭五键、恰好两件、id/声明去重、无数字/坐标；不写/[]不写出且旧摘要不变。新测试41 passed，主代理聚焦369/2，CH34 pinned不变；parts与空数组变异各3红后恢复。完整 pytest **10086 passed / 25 skipped / 1 xfailed / 16 failed / 1 warning、0 errors**，16条全为既有（12条货架/分类漂移、2条115/116、2条Windows环境）；connector/DSH/Rust通过，不称全绿。证据 `evidence/548B1/`。
- **548B2 跨文档校验与页面切片（2026-11-08，通过；本批不做几何；完整四线已跑）**：V1–V8在standalone/page完整文档几何前接入；跨模块由V7具名拒绝，切片只携带同模块两件。前红24/2转26 passed，主代理聚焦423/2；V6与切片变异分别2红/1红后cp恢复。完整 pytest **10112 passed / 25 skipped / 1 xfailed / 16 failed / 1 warning、0 errors**（同16条既有）；connector/DSH/Rust通过。几何属548B3，不称548B完成。证据 `evidence/548B2/`。
- **548B3 决定串联几何与独立语法检查（2026-11-08，正例 + 不可落座负例通过，禁止静默回退已落地；checker 六点检查未做；完整四线已跑，16 failed 均既有）**：每条声明注入两件 `RelativeConstraint`，`compile` 与独立 `check_grammar` 共用 `_with_series_arms`；座位按文档既有 axis/progress 与真实引脚，几何按 宿主→parts[0]→middleNet→parts[1]→终端 构造，pitch 取原布局中心距，非GND终端轨优先在臂尾真实脚挂旗；未声明/[]不变、不自动识别。生产只改 `drawcompiler.py`（最终 `d9ba64ab…`），新测试前红 **10 failed / 4 passed** → **14 passed**，主代理聚焦 **232 passed / 2 skipped**；高边首选 `9917b0b3cda9…`、低边 `5eea1a442ce7…` 各3候选、六点单调、middle一段10单位；CH34 pinned `6ed82091…`/`2ec6b700…` MATCH。**三项变异均完成，第三项（仅删checker注入）先暴露⑤b覆盖洞、测试加强后才复红**；变异恢复点当时是 `2cc92fc0…`，其后另有520b2兼容修复（`getattr(..., "series_branches", ())`）才得到最终hash。第一轮完整 pytest **18 failed / 10124 passed / 25 skipped / 1 xfailed**：既有16条外2条新红为520b2两条（SimpleNamespace 规格无 `series_branches` → AttributeError），修后 520b2+B3 **21 passed**（`regression-520b2.log`），测试未改。主代理亲看渲染：两件均竖直直链、R在LED前、中点短、终端旗在臂尾、位号值行完整。connector 576+typecheck、DSH 137/1+typecheck/build、Rust 111/4+fmt/clippy。**不跑真机、不落画布、不称 lint 宿主 DRC 或自动整页**；第二轮最终 **16 failed / 10126 passed / 25 skipped / 1 xfailed、0 errors**（`full-pytest-final.log`，added=[]、removed=[]，16条均既有，不称全绿）。证据 `evidence/548B3/`。
- **548A-R / 548B3-R 第二轮全量（2026-11-08）**：**16 failed / 10130 passed / 25 skipped / 1 xfailed、0 errors**（1505.66s，`evidence/548D/full-pytest-rs.log`），与 548B3 基线 JUnit 比较 added=[]、removed=[]（`full-compare.log`）；第一轮 16 failed / 10122 passed / 33 skipped 多出的 8 个 skip 未复现、不虚构；卫生 7 passed、文档钉 40 passed，不称全绿。**548D2/D2R 两版串联预留均未通过、生产净零改动，548D 暂停于跨轮串联预留、未进入整页实施**（§18）。

- **548D3 当前状态（2026-11-09，未闭环）**：base MCU 的原 7 条 xfail 已真实通过后摘除；WiFi
  单岛已通过机器、逐脚与主代理放大目检，连续旗引线、页/岛 `PWR-+3V3` 回退和局部文字修复保留，
  CH34 `allMatch=true`。强制 topology 仍 0 候选；整页需 **1694.75×1009**，放不进 1170×825，
  MCU/整页视觉未签。**不派 548E 真机、不把 corridor binder 的未接消费者测试当生产能力**。
  后续从 `tasks/548_drawing_capability_ladder.md` §23–§29 的真实阻塞进入，不再重复局部试错；
  权威交接 `evidence/548D/HANDOFF.md`。548E/547G 继续暂停，未做 git 写。第二轮全量
  **10261 passed / 25 skipped / 1 xfailed / 16 failed**，新增7条兼容回归已消除，余16条与既有
  名单一致，不称全绿；connector/DSH/Rust通过，三项独立变异均先红并cp/hash恢复。

- **548D3X 页级 compact（2026-11-10，通用小批通过；548D 未闭环）**：普通岛框最小净距仍 40；
  实测当前 MCU/WiFi 真实框横放需 1373.5 宽、竖放需 844 高，证明只换 packing 不足以进
  1170×825。默认关闭的 `pageArrangement=compact`、纯二维 packer、端口定点回放、attach/mainPath
  与旧网格回退已接生产，主代理聚焦 **215 passed / 1 skipped**，变异与恢复证据齐全。
  固定页 compact 与 attach-bottom 各 6 变体、0 候选，只改附着方向仍不足。`panelGroups` 数据合同
  的数据、电气与页面切片校验已落，主代理 **272 passed / 1 skipped**、两项变异恢复。base与
  topology `_Placement` 随后均真实通过2×2，默认near=300，host逃逸/spread预留/重绑与hard面积
  梯度均落地；主代理两项有效变异恢复。terminal向下预留、host channel、terminal seat与模板文字已
  分段回放；宿主相对route cache已落地，最小fixture `dc.compile` 已 **ok=True / hard=0**。
  但主代理亲看最新渲染：2×2成立、GND外框仍在，**9交叉31弯，视觉拒收**。per-pin无座、聚簇与
  seat回放不一致、簇内短接出现5簇3座，seat-first需要新合同，目标在本轮 **blocked**。
  后续A新建seat-first合同，B接受 `agent-adjusted`，不得冒称automatic。真实整页与本轮全量四线未做，
  548E/547G继续暂停，未做git写。

- **548D3S7/B3（2026-11-10，生产候选已出，视觉未过）**：ServiceSeat与path-first生产已接，
  `dc.compile` ok=True / hard0，3V3六枚、GND五枚，LED2真实fallback；缺seat和跨seat变异均先红恢复，
  CH34 MATCH。主代理亲看 `service-seat/path-first-final.svg`：LED1长1220、全页4交叉，仍视觉拒收。
  下一批只处理LED信号走廊与标签/布局共同约束，不重开packer或无依据挪座位；真实MCU/整页未验收。
  提交前全量pytest **10628 passed / 25 skipped / 1 xfailed / 16 failed**（均既有），connector 608、
  DSH 137/1、Rust 111/4通过，不称全绿；548E/547G继续暂停，提交前未做git写。权威证据
  `evidence/548D/service-seat/` 与 `evidence/548D/HANDOFF.md`。

- **548D3B7 KEY/LED独立岛（2026-11-11，离线三关通过）**：岳明确两功能可独立成岛，旧同岛走廊与13交叉
  局部多腿方案不采用。共同power coreless bank、return显式left/right时纵向等节距及全组旗桩联合选档已接
  生产；缺省GND/横排与CH34 pinned不变。三岛automatic compile、页闸和独立逐脚通过，LED/KEY独立岛渲染
  由主代理签收。最终生产 `drawcompiler=95b52424…`、`ic_periphery=7346edba…`，两项主代理变异先红恢复。
  **下一步只与岳共同处理MCU整页边界名/布局和强制topology，不重开LED/KEY岛，不进入548E**。证据
  `evidence/548D/service-seat/semantic-islands-final.md`，全量读数以该文件为准。

- **548D3C1 MCU本地供电/BOOT0/GND（2026-11-11，离线三关通过）**：岳明确右侧标签后置，先修C1/R1座位
  与绕旗。`serviceLayout.localSeats=true`（配 `pinGap=30`）启用本地服务支路，R1近端、C1在VBAT行外侧，BOOT0直连；3V3两枚、
  GND三枚本地旗，原外框消失。主代理亲看最终MCU/三岛SVG通过本地结构，C1六文件 **126 passed**，两项
  主代理变异先红恢复。第一轮全量158 failed/22 errors暴露误用旧serviceLayout，C2以默认False的localSeats
  子键恢复旧文档；旧失败族81 passed、本批六文件129 passed。新能力仅在localSeats=true且无panelGroups时开启，
  base/topology同源设置内部联合开关；旧panelGroups逐候选恢复，CH34 pinned不变。右侧标签、真实整页、
  强制topology与548E仍未做。**岳复验绘制线全量2 failed**；本 agent混合工作区全量
  **10702 passed / 25 skipped / 1 xfailed / 16 failed / 1 warning**，含其他线未提交改动与既有环境项，
  不能全归绘制线，不称全绿；Connector 660+typecheck、DSH 137/1+build、Rust 150/4+fmt/clippy。
  证据 `evidence/548D/service-seat/mcu-local/final-c1.md`、`compat-local-seats.md`，任务书§39、shared §17–18。

- **547S 098 scene08基线修复（2026-11-11）**：岳指出绘制线全量仅115/116两条failed。逐commit证明
  547S统一支路网尺的合法拒因变化，场景不产图、localSeats无影响。保留pre_547s旧版后依法重钉114基线
  与116 hash，生产未改。主代理相关四文件 **93 passed**，变异先红并cp/hash恢复。证据
  `evidence/548D/scene08-baseline-repair.md`，任务书§40。最终全量 **10775 passed / 26 skipped /
  1 xfailed / 0 failed / 0 errors**，两条目标测试均消失，绘制线全绿（另有1条既有编码警告）。

- **548J 当前交接（2026-11-13）：A合同通过，B1联合座位停止，视觉未过**。`serviceGroups`解析/封闭负例/
  页面切片及两项主代理变异已验收；岳人工P44和ESP-01S双列校准件可复用。B1虽22条目标测试通过、
  交接组合 **233 passed / 1 skipped**，但 `evidence/548J/b1/synthetic.png` 仍有CFG_A/PWR大回环，
  主代理视觉拒收。最近脚端子行、去耦GND行与障碍抽头没有组合正例；真实WiFi未消费，B1真机/独立变异/
  全量四线未做。当前 `drawcompiler=11b2b3b9…`（B1前058a3032…），工作树混合未提交，**不得git restore、
  不得继续给独立builder打补丁**。P44人工页/P42/P43/Board2不动，P45空白，daemon已停。
  **下一任先读 `evidence/548J/HANDOFF.md`**；保留人工页、清理或重设计由岳另裁。若重做，只做组级计划供
  现有标准build/route/flag/page-anchor消费，先过一个无回环小闭环再接真实WiFi。548D自动整页/548E未完成，
  547G仍独立暂停。此前H3–H6/P1、P43、T1、F1A证据见 `evidence/548D/host-binding/` 与 `full-page/`。

- **548K 名字桩下限同源 + 单脚标签网先预留（2026-11-14，机制批；图判废、未签收）**：根因实测两条——
  编译期 `_reserve_label_stubs` 承诺 `LABEL_LANE_STEPS=2` 格（10 单位），交付侧
  `drawapply._label_stub_candidates` 按 `labelPolicy.stubMin`（该页 40）找桩；且名字桩带排在旗标引线与
  宿主支路**之后**。改法只 `engines/drawcompiler.py`：新增 `_stated_stub_floor()`、`reach` 取
  `max(10, stubMin)`（service 页除外）、`stubMin` 阳性时把**单脚** label 网并入既有 `local_first`
  两趟机制。**不新增布局器**。
  **完整四线第一轮抓出 6 条老金标准红**（534x×2 属顺序 hunk；534/543c/548c4/548c6 属长度 hunk），
  归因用两次反向变异分离，另 2 条为既有红（panel 路由次数、193 Windows 环境）。
  **548K-R 已收口**：两处行为收进显式开关 `labelPolicy.stubLaneReserve`（默认不写=逐字节旧行为、
  `false` 等价不写、只在 true 时序列化、非布尔具名拒绝）；文件域 `core/presentationspec.py` +
  `engines/drawcompiler.py` + `tests/test_548k_stub_lane.py` + `docs/draw.md`，最终
  `drawcompiler=B965AC…1F66`、`presentationspec=667475…9BC8`。校准 WiFi 件三态：不写开关 →
  `f4f1c58c00ee…`（与 548J §16 记录逐字相同）+ plan 拒绝；写开关 → plan `ok=True`（6 件/17 线/7 旗），
  图与开门前那版逐项相同；去门控 → 6 条老页红。聚焦复验 **63 passed**；三种变异 4/2/7 红均 cp+sha256 还原。
  **校准 WiFi 件仍判废**：编译器自述 `ESP_EN/ESP_RST: wired route not found; labelled instead`
  （两截裸名长桩 200/80 单位）+ 三条名字行贴边；强令成线 `[wire-through-body]` 0 候选。**真因已定位**：
  去耦那枚地旗图形盒 `(310,680)-(330,699)` 与引线 `(320,705)-(320,680)` 正压在两条待走直线上；
  `gndClustering.radius=100` 已反证无效 → 批次2 `tasks/548l_flag_corridor.md`。
  未做真机、未 git 写；P44/P45 未动。证据 `evidence/548K/README.md`、任务书 `tasks/548k_stub_floor.md`。

- **548L 待走直线走廊先预留（2026-11-14，机器过、视觉判废）**：548K 之后编译器仍自述
  `net ESP_EN/ESP_RST: wired route not found; labelled instead`，真因是去耦那枚 GND 旗盒
  `(310,680)-(330,699)` + 引线 `(320,705)-(320,680)` 压在两条待走直线上（`gndClustering.radius=100`
  已反证无效）。改法只在既有预留链加第四类：新增 `_reserve_pending_runs`，在
  `_lead_lane_reservations` 旗位/标签之前把 `style=wire`、两脚、正交的网直线 `_take_lane` 预留，
  条件同 548K 开关（`_stub_lane_reserved and not _service_layout_page`）；旗位不改——`_flag_room`
  预留趟本来就拒绝压在别网通道上的旗盒。文件域两个：`drawcompiler.py`（+74/−1）与新建
  `tests/test_548l_pending_corridor.py`；最终 `drawcompiler=AA86C1CE…FC5C2`、
  `test_548l=775F62DB…D9C0`。正例：校准件 `compile ok=True` / `plan ok=True`、两条网**各一条导线**、
  `wired route not found` 三处均 False、GND 旗让到 `(350,730)`、7 网 17/18 脚；默认关闭复现旧态
  （几何 `81557467…`）。变异 M-L1（去调用）真件复现拒因、新用例 1 failed；M-L2（去门控）
  4 failed（548c4×2、548c6×2）；两次 cp+sha256 还原。主代理聚焦 11 文件 **124 passed**。
  **视觉判废**：三枚 3V3 旗挤在去耦对上方且旗名压相邻旗盒；`ESP_RST` 因 R4 本体占住 y=695
  被逼下绕 y=785 往返；`ESP_RXD/ESP_TXD` 名字盒压自己引脚线与编号。逐岛四问见
  `evidence/548L/README.md` §6。不落画布、不真机、不宣称 548J 完成。
  下一批入口：旗域与文字的联合座位（同网旗聚簇/共享短轨、开放标签贴自己引脚、服务件让开走廊）。

- **548M 同网轨旗聚簇（2026-11-14，旗域改善、图仍判废）**：`railClustering: {"radius": N}` 新顶层可选键，
  形状/校验照抄 `gndClustering`；`_expression_style` 的 power 分支在**声明该键时**取 `wire` 样式
  （053 sec.7 默认裁决一行未动），`_cluster_radius_for` 收窄为只认 power（**不碰 GND**），
  下游 535 逐簇绘制一行未动。真件：`3V3` 旗 **6 → 3**（`(280,765)`/`(430,750)`/`(120,750)`，每簇短轨 +
  簇号注记）、`GND` 仍 1 枚、`crossings=0`、默认关闭几何 `8802d317cfae…` 与 548L 记录逐字节相同；
  变异 M-M3（去样式分支）→ 旗回 6 枚、正例 1 failed；M-M1/M-M2 各自有红；聚焦 11 文件 **165 passed**。
  全量第一轮 7 failed 暴露两条本批回归（位置参数被挪位、假 budget 无新属性），已修；另把
  `test_548j_service_groups::test_the_new_field_is_appended_after_every_old_field` 的尾部期望顺延一格
  （追加是契约允许方向，docstring 写明未放宽；旧位置参数由 23 参数构造用例护住），修后 63 passed。
  **视觉仍判废**：`ESP_RST` 因 R4 本体坐在 y=695 直线上，仍从 J2.7 下绕到 y=785 再横穿底边回来。
  证据 `evidence/548M/README.md`（含 `renders/rail-zoom.png`）。下一批：让 placement 看见
  "两脚 wire 网的直线走廊"或降低该绕行代价等级，仍不新建规划器。

- **548M2（2026-11-14，GND 同策略，已全量）**：`railClustering` 恢复为 power+gnd 都生效
  （`gndClustering` 语义一行未动、两者都适用取大者）。GND 旗 **1 → 2 枚**（`(350,730)` + `(180,730)`），
  **y=795 底边 rail 消失**；3V3 仍 3 枚；geometry `61f52837…`、`crossings=0`；默认关闭 `8802d317cfae…` 逐字；
  M-M4（去 gnd 条件）→ GND 回 1 枚 + 新用例 2 failed，已还原 `32F849BA…`。聚焦 11 文件 **165 passed**；
  完整 pytest **2 failed / 11066 passed / 22 skipped / 1 xfailed（27:55）**，两条红均既有，零新增。

- **548N 组级座位（2026-11-14，**未达成**，净改动为零，前提被证伪）**：独立 worktree
  `E:\boardwise-wt-548n`（分支 `drawing-548n`）里试三条路线，全部撞在同一组已验收断言上：
  ① 三颗上拉一组 → `the host feet ['IO0'] … do not all face right`；② 拆两组 → `branch 'R4' …
  stands on reserved port 'ESP_TXD' run`；③ 组行改成员外延 → `host foot 'VCC' has no crossing-free run
  to the '3V3' terminal rail` 且冻结用例 18 failed（已逐字还原）。
  **两个真前提问题**：(i) 我任务书写错了——校准 profile 的 `IO0` 在左侧，岳 P44 本身也是 `R18` 靠左，
  正确形态是**两组**（R4/R5 右、R6 左）；(ii) 与 `tests/test_548j_joint_seats.py:692`「跨侧组 = 具名拒绝」
  **互斥**。需岳二选一：**(a)** 解冻该负例改"跨侧允许、各按脚侧"（改 3–4 处座位合同）；
  **(b)** 接受两组声明并把验收改成"R6 到左脚"、同时修 `_joint_rail` 的 VCC→3V3 候选方向。
  两条都不新建 builder，但都动已验收的 548J 合同，故停。**岳 2026-11-14 裁 (b)**：接受两组声明
  （R4/R5 右、R6 左，去耦另组），**不解冻** `test_548j_joint_seats.py:692`；worktree 保留为**只读证据档案**
  （不是当前实现，548N2 已并主仓 `05139E85…`），后续同一层在主仓继续。
  环境缺口：worktree 缺
  `evidence/543d2/effective.presentation.json`，导致 `test_548c6` 等 4 个 collection error（非本批改动）。
  证据 `evidence/548N/README.md`。

- **548N2 组座位避开开放端口房间（2026-11-14，缺陷已修并并入主仓；真实三组页仍不 ok）**：
  `_joint_seat_group` 评估座位时没有把已预留的开放端口房间当障碍，座位压在 `ESP_TXD` 预留 run 上
  （`branch 'R4' (260.5,645,269.5,685) stands on reserved port 'ESP_TXD' run (259.5,674.5,265.5,675.5)`）。
  修法：复用 `_reserve_open_ports` 的同一份 `ports`（run 盒 + label bbox）当墙，命中沿宿主侧外退一档
  `GAP`（≤8 档），全不退交既有 `_joint_collisions` 具名拒绝；同侧第二组从只支持去耦推广到任意组。
  只对声明 `serviceGroups` 的页生效，默认页仍 `61f52837…`。最终 `drawcompiler=05139E85…5EA3E`、
  新测试 `tests/test_548n_group_seat.py=F78CC5A2…1A6A`；变异 M-N3（删换档）→ 合成正例 2 failed +
  真实页逐字复现拒因，cp+sha256 还原。主代理复验：worktree 11 文件 **121 passed/5 skipped**、
  主仓并入后 14 文件 **185 passed**。
  **三组页仍 `ok=False`**，卡在新一层：`the pin J2.GND has no clear upright hang for its 'GND' flag`
  ——让位把 PWR rail 推进了宿主 GND 的挂旗带（座位/轨道/宿主本地旗三方争地，合成件同因）。
  距离也没缩小（R4→J2.RST 125.4、R5→J2.EN 189.3、R6→J2.IO0 121.8，离 P44 的 30–65 更远）。
  按停止线不再续跑；下一层最小动作见 `evidence/548N2/README.md` §4。


## 3. 派单规则

1. 一张派单只写一个算法缺口或一个集成点，先写文件域、基线与相邻测试。
2. **算法与迁移永不同批**：不改共享 import 时顺手调布局，也不在算法批里做 Rust 翻译。
3. 需要 shared 电气合同、parser/model/bridge/CLI 变化时，改走 `tasks/shared-platform.md`
   的集成锁；不得把 draw→review 边登记成新 legacy。
4. 几何或输出变化必须给前后指纹/图像证据；纯解耦批则要求逐字节或行为等价，不能趁红灯改图。
5. 全量、共享底座与真机串行；真机只碰任务书逐字点名的 `test`/`test2`。删除、git 写、
   push、发布和 worktree 操作逐次问岳。

## 4. 验收与交接

- 小批先跑 `tests/test_540_cli_draw.py` 与对应 drawcompiler/drawapply/lint/edit/pintable
  邻域；owner 变更另跑 `tests/test_owner_rules.py` 和 layer 守卫。
- DSH draw 改动跑 `dsh-plugin` typecheck/test/build 与 `npm run smoke:draw`；真实 smoke
  只用公开/合成输入，不连接编辑器，不删除产物。
- 交接必须说明机器闸、逐脚连通、视觉自审各自证据；不适用时写不适用及原因，不能互相替代。
- **基准口径（548O 复盘，2026-11-14）**：`geometry_sha256` 只是**指纹**，证明"没挪动"，
  不证明"能看"——**不得把「逐字节不变」写成通过**。真基准只有一张：岳接受过的图；在出现
  之前如实写"没有质量基准"。`docs/draw.md` §Baseline 的 P44 四项按功能关系验收：
  P1 宿主脚侧/脚序与同组端子对齐、P2 功能组本地旗、P3 无多余绕行及可见连接、
  P4 功能子组关系与一致对齐；距离和原点跨度逐项记录，不能代替视觉结论。
- **P44 指标勘误（岳 2026-11-14 明确授权）**：以 P44 样例为准，按功能关系修正机械指标。
  P1 统一距离 30–65 与 P4 原点纵向跨度 ≥60 退役；P44 实测距离为 50/95/70/205/165、
  原点跨度 265×25，均只作诊断，不设成新阈值。旧候选 RST 的无必要绕行仍是拒因，
  不能因撤下错误跨度门槛就把旧图放行。
- **勘误（同日）**：`8802d317cfae…` 作废——它是 **548L 自己**的候选（`evidence/548L/README.md:32`，
  原始值 `evidence/548L/renders/cand1.layout.json:581`），当时已被视觉闸判废；548M 起被当作
  "默认页逐字节不变"的验收线，548N2/548O 沿用，于是三批的验收合起来只证明了"没变坏"。
  它也不是"默认页"：那个 spec 带着 `stubLaneReserve: true`，开关全关是 `81557467…`。
  三批的**能力**读数（旗数、拒因、变异红项）不受影响，失效的只有"以不变当通过"这一句。
- CH343/534 等既有工作已在 `0f638de` 提交，按原任务归属，不因 540 解耦而变成 540 成果。
- Rust 顺序：纯函数/几何、parser/model、review 之后才到 draw；connector/DSH 薄适配可留 TS。

**当前 worktree 状态**：542 经岳批准使用 `E:\boardwise-wt-draw` / `drawing-line`；
`E:\boardwise` 主工作区及其未提交 201H 文件保留，`E:\boardwise-wt520` 仍是只读证据档案。
542 P0 已冻结；后续隔离仍须先写清路径、分支、owner、集成锁和证据保留并逐次申请。
