# 绘制线派单入口（540B8）

> 这是 draw 线的任务路由。画图交付仍受 `AGENTS.md` 的三关、
> `docs/schematic-style-spec.md` 与画法宪法约束；解耦不改变任何算法验收锚。
>
> **开工前必须加载 `boardwise-draw` skill**
> （`.agents/skills/boardwise-draw/SKILL.md`；`.kimi-code/skills/boardwise-draw/SKILL.md`
> 是它的逐字节副本）。分岛/合岛的提交条件、成对支路一致性、机器闸与视觉闸互不替代
> 的裁决都以它为准；漏加载等于没有验收口径。通用 SOP、R1–R3 与真机纪律仍以
> `boardwise` skill 为唯一权威。

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
- CH343/534 等既有工作已在 `0f638de` 提交，按原任务归属，不因 540 解耦而变成 540 成果。
- Rust 顺序：纯函数/几何、parser/model、review 之后才到 draw；connector/DSH 薄适配可留 TS。

**当前 worktree 状态**：542 经岳批准使用 `E:\boardwise-wt-draw` / `drawing-line`；
`E:\boardwise` 主工作区及其未提交 201H 文件保留，`E:\boardwise-wt520` 仍是只读证据档案。
542 P0 已冻结；后续隔离仍须先写清路径、分支、owner、集成锁和证据保留并逐次申请。
