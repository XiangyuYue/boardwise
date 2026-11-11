# 任务全图（TASKMAP）

> **这份文件回答「这个仓库做过什么、现在在哪、还有什么没做」**，按任务编号索引。
> 它不是流水账——流水账在 `PROGRESS.md`（按时间 append，只用于查历史细节）。
>
> **AI 恢复上下文的最小路径**：
> 1. `docs/roadmap.md` §1-§2（当前在哪、版本骨架）→ 2. 本文件 §0（在途/搁置）→
> 3. 你要做的任务的 `tasks/<批号>*.md`（规格）→ 4. 需要历史细节才 grep `PROGRESS.md`。
>
> **状态口径**（五选一，取该编号最后一次记录）：
> `已落` = 已 commit 并推送 · `工作树` = 已完成未提交 · `搁置` = 明确踢出/hold ·
> `在途` = 子代理正在跑 · `规划` = 任务书写了未开工。
>
> **证据**列原样抄自 PROGRESS 行里的路径/commit；空白 = 该行没写路径。
> 只做聚合，不重述结论；细节打开对应任务书/证据目录。

---

## §0 当前在做（截至 2026-11-08）

- **0.6.1 已正式发布（2026-11-10）**：main `47713c2`、`8ad625e`、`9ffeb3b`；tag 与 Release
  `targetCommitish` 均为 `9ffeb3b`（`prerelease=false`、latest）。0.6.1 含审查线 038W/X、527C2、
  529、541 R1/R2/R4 与**首次配对显式授权（549）**，绘制线 CH340 第二拓扑、CH343 持久化与旧任务核销；
  发布快照以本版 Release 为准，候选货架、临时测试计划与探针产物**未入库**。
- **0.6.0 后的审查落地**：`a4fc387`（V4 多 PCB/Rust 库切片）、`d0275ae`（EPRU 一致性）、
  `683a526`（非矩形焊盘间距）、`6253a0b`（041 S1/S2）与上述 `cdff88b` 已形成本版审查内容。
  真实多板＋库、原始 PCB-A、4.1.94+ 宿主探针与 541 R3 不因此关闭。
- **0.6.0 后的绘制落地**：`336cd59`（原生文字与服务布局）、`924a180`（成对姿态）、
  `44901da`（第二拓扑与持久化）已形成本版绘制内容。只承诺两个已验收拓扑，不承诺任意电路；
  CH340 页持久化仍待关闭重开验证。
- **540 平台与 Rust**：`evidence/540/candidate-regression.md` 是历史候选读数，不替代本版验收；
  Rust 的 DEVICE/FOOTPRINT/SYMBOL 等垂直切片不代表 Python 主流程已迁移完成。
- **547G 辅助整页 G1–G3 完成、G4 部分完成，当前暂停（2026-11-07）**：30件/31网/5NC/8岛
  辅助页已过离线双层页面闸、独立逐脚/NC 与逐岛视觉；真实 profiles 18 份/122 条记录。剩余为
  岳手动关闭重开 test V4 后的只读比对、完整四线与最终复验；本批未跑四线，DRC 非通过
  （0 error/200 warn `passed=false`），持久化仅 `saved_unverified`。自动线 547D 暂停待续，
  辅助成果不关闭 547D/E。任务书 `tasks/547_smart_medicine_box.md` §547G。
- **548 自动绘制能力阶梯（2026-11-08；`tasks/548_drawing_capability_ladder.md`）**：从 547S 已完成的合同之后，逐批补 547D 支路/标签联合几何、547E 串联语义、扰动与组合、自动整页与真机闭环。**当前阶段：A 完整 N≥3 面板支路出口通过（限已测电路族，A-R 补齐灯/蜂鸣器）、B1/B2 完成各自离线范围、B3 正例与不可落座负例通过且禁止静默回退已落地（checker 六点未做）、C 部分通过、C2 批次前提被证伪、C3 的 ②③④ 已落、C4 的 B1 落、B2 已由 C6 关闭而 B3 未落、R 只补测试与文档、C7三次未通过（缺口另批）**；各批细节、证据与失败边界见下列各条与 `tasks/548_drawing_capability_ladder.md` §5–§29（§17 为 548A-R/548B3-R 验收缺口复审，两项已关闭、第二轮全量 16 failed / 10130 passed、0 errors、added=[]、removed=[]；§18 为 548D1/D2/D2R——D2 两版均未通过、生产净零改动、暂停于跨轮串联预留）。
  **548D3 当前状态（2026-11-09，局部推进、未闭环）**：base MCU 的原 7 条 xfail 已真实通过后摘除；
  WiFi 单岛通过机器、逐脚与主代理放大目检；连续旗引线、页/岛 `PWR-+3V3` 回退和局部文字修复保留，
  CH34 `allMatch=true`。强制 topology 仍 0 候选；整页需 **1694.75×1009**，放不进 1170×825，
  MCU/整页视觉未签。未接生产消费者的 corridor binder 不算能力交付。未调预算/排名或放大图幅，
  548E/547G 继续暂停，未做 git 写。权威交接与复验状态 `evidence/548D/HANDOFF.md`，任务书 §19–§29。
  第二轮全量 **10261 passed / 25 skipped / 1 xfailed / 16 failed**，新增7条兼容回归已消除，
  余16条与既有名单一致，不称全绿；connector/DSH/Rust通过，三项独立变异均先红并cp/hash恢复。
  **548D3X（2026-11-10，通用页级 compact 小批通过，548D 未闭环）**：参考普通岛框最小净距 40；
  当前 MCU/WiFi 真实框仅靠 packing 仍放不进固定页。新增默认关闭的 compact 声明、有限二维
  packer、端口定点回放、attach/mainPath 与旧网格回退；主代理聚焦 **215 passed / 1 skipped**，
  变异与恢复证据齐全。固定页compact与attach-bottom各6变体、0候选。panelGroups的数据、电气/切片
  与placement已推进：base/topology均真实2×2，默认near=300，host逃逸/spread预留/重绑与hard面积
  梯度均落地；主代理两项有效变异恢复，最终组合 **224 passed**。最小fixture随后 `dc.compile`
  **ok=True / hard=0**，但主代理亲看最新渲染：2×2成立、GND外框仍在，**9交叉31弯，视觉拒收**。
  per-pin无座、聚簇与seat回放不一致、簇内短接出现5簇3座，seat-first需要新合同，目标在本轮
  **blocked**。后续A新建seat-first合同，B接受 `agent-adjusted`，不得冒称automatic。
  真实整页与本轮全量四线未做，548E/547G继续暂停，未做git写。
  **548D3S7/B3（2026-11-10，生产候选已出、视觉未过）**：ServiceSeat与path-first生产已接，
  `dc.compile` ok=True / hard0，3V3六枚、GND五枚，LED2真实fallback；缺seat/跨seat变异先红恢复，
  CH34 MATCH。主代理亲看 `service-seat/path-first-final.svg`：LED1长1220、全页4交叉，仍拒收。
  下一步只处理LED信号走廊与标签/布局共同约束；真实MCU/整页未验收。提交前全量pytest
  **10628 passed / 25 skipped / 1 xfailed / 16 failed**（均既有），connector 608、DSH 137/1、
  Rust 111/4通过，不称全绿；548E/547G继续暂停，提交前未做git写。
  权威交接 `evidence/548D/HANDOFF.md`，任务书§35–§36。
  **548D3B7（2026-11-11，KEY/LED独立岛离线三关通过）**：共同power coreless bank、return显式left/right
  时纵向等节距及全组旗桩联合选档已接生产，缺省GND/横排与CH34 pinned不变。三岛automatic compile、页闸、
  逐脚通过，主代理亲看LED/KEY独立岛PNG通过；生产 `drawcompiler=95b52424…`、`ic_periphery=7346edba…`，
  两项主代理变异先红恢复。旧同岛与13交叉局部多腿方案不采用。真实MCU整页/强制topology/548E未关闭，
  下一步与岳共同规划整页。证据 `evidence/548D/service-seat/semantic-islands-final.md`，任务书§38。
  **548D3C1（2026-11-11，MCU本地供电/BOOT0/GND离线三关通过）**：serviceLayout.localSeats=true显式启用本地服务支路，
  C1/R1联合落座，固定host通道、本地旗与冲突文字重排同一几何；BOOT0直连，3V3两枚、GND三枚本地旗，
  原外框消失。主代理亲看最终MCU/三岛SVG通过本地结构，C1六文件 **126 passed**，两项变异先红恢复。
  第一轮全量158 failed/22 errors暴露误用旧serviceLayout，C2以默认False的localSeats子键恢复旧文档；
  旧失败族 **81 passed**、本批六文件 **129 passed**。新能力仅在localSeats=true且无panelGroups时开启，
  base/topology同源设置内部联合开关；旧panelGroups逐候选恢复，CH34 pinned不变。右侧标签、真实整页、
  强制topology与548E未关闭，未做git写。**岳复验绘制线全量2 failed**；本 agent混合工作区全量
  **10702 passed / 25 skipped / 1 xfailed / 16 failed / 1 warning**，含其他线未提交改动与既有环境项，
  不能全归绘制线，不称全绿。证据
  `evidence/548D/service-seat/mcu-local/final-c1.md`、`compat-local-seats.md`，任务书§39。
  **547S 098 scene08基线修复（2026-11-11）**：岳指出绘制线全量仅115/116两条failed；逐commit证明
  547S统一支路网尺的合法拒因变化，场景不产图、localSeats无影响。保留pre_547s旧版后依法重钉114基线
  与116 hash，生产未改。主代理相关四文件 **93 passed**，变异先红并cp/hash恢复。证据
  `evidence/548D/scene08-baseline-repair.md`，任务书§40。最终全量 **10775 passed / 26 skipped /
  1 xfailed / 0 failed / 0 errors**，两条目标测试均消失，绘制线全绿（另有1条既有编码警告）。
  **548B1 数据合同已落（2026-11-08，41 passed；完整四线 10086 passed / 16 failed 均既有）**：`evidence/548B1/`。
  **548C2 多岛共享电源网统一（2026-11-08，未通过，批次前提被证伪）**：E2/E3 的 `layout-unsat/modules[mcu]`
  与「岛数」无关——547A 自己的 mcu 用页面预算（radius 100）编译同样 4 节点；真缺口是三层（模块层拆分地
  零命名陈述 / 页面端口用裸成员名查脚号键 / 页面 label 兜底压文本且竖命名），「不拆」已被反证为跨体母线。
  生产代码零改动，4 负控 74 passed / 2 skipped + 547A 2 passed + CH34 pinned 逐字节不变。**该语义事实
  已裁（2026-11-08）**：禁网络标签、允许库内旗标——拆分地每簇的命名陈述只能走库内旗标，落地由 C7/C7A/C7B（三次未通过）另批。
  证据 `evidence/548C2/`。
  **548C 扰动与组合部分通过（2026-11-08）**：A/C/D 8/11 单岛变体过、B 0/3（长位号/长值行过拟合）、E 0/2（共享 GND 分区未打通）；证据 `evidence/548C/`。
  **548C3 页面端口成员名解析 + 页 label 兜底承载杆（2026-11-08，②③④ 已落）**：只做 548C2 的 ②③④，**①（拆分地每簇命名）一行未碰（岳 2026-11-08 已裁禁网络标签、允许库内旗标；落地由 C7/C7A/C7B 三次未通过、另批）**。② 成员名过 `readability._profile_pin_ruler` 解析成脚号（`J1.VCC→J1.1`），错名点名拒绝；③ 页兜底 label 改画自己的水平承载杆（既有 40…240 梯级、不骑模块导线、竖直杆不做），模拟页 0 hard、GND/3V3 各 1 节点；④ 新增 strict xfail 钉住 547A 在 radius=100 仍失败。新测试 3 passed / 1 xfailed；4 负控 74 passed / 2 skipped、547A 2 passed、CH34 pinned 逐字节不变。生产只改 `pagecompiler.py`。证据 `evidence/548C3/`。
  **548C4 长位号/长值行文字压线（2026-11-08，B1 落、B2/B3 未落）**：判据先写成文（`evidence/548C4/criteria.md` C1–C6 + P1–P7）。实测失败层＝文字栈按「最宽行定宽」落到 above 侧，93 宽位号把 value 行拖进 MCU 的 `LCD_SCK` 行，而 `_part_texts` 的墙集**没有标签走廊**（表达式 11700 才算、标签 12085 才落座），标签自身 4 方向 × 4 梯级已被五条 LCD 标签占满。修法只改 `drawcompiler.py`：闸报 `texts × labels` 时把闸点名的 label 盒补进文字墙集重建 variant（≤4 轮，148 逃生梯同形），**没相撞的页面 0 轮 ⇒ 零移动**。B1 `ok=True`、1 候选 `868cc95b…`、hard 0、26/26 网 sameNode、0 短路、0 未放置、长位号/长值行全部整行印出；基线几何 `b71fcbcf…` 逐字节不变；负控 82 tests/0 failed/3 skipped、CH34 pinned 不变。B2 只剩 159.5 宽值行无自由侧（2.93×–4.79× 节距下同一修复可过）⇒ 缺「节距由文字宽度解出」，布局层未落；B3 仍卡 3V3 无旗符号（548C2 ① 同族；岳已裁禁标签旗入库，C7 三次未通过、另批）。证据 `evidence/548C4/`。
  **548R 审查整改（2026-11-08，只补测试与文档、无生产改动）**：`tests/test_548c3_page_port_members.py` 加经过 `_compile_modules` + `_module_ports` 的正向回归，`tests/test_548c4_text_label_repair.py` 钉 B1 正向与基线零移动；聚焦 **85 passed / 2 skipped / 1 xfailed**。两次独立变异：C3 源码 `preferred` 改错 → **1 failed / 4 passed / 1 xfailed**，恢复后 **5 passed / 1 xfailed**；C4 把 `TEXT_LABEL_REPAIR_ROUNDS` 置 0 → **3 failed / 1 passed**，恢复后 **4 passed**；恢复哈希 `pagecompiler.py` `975e6b1c…`、`drawcompiler.py` `9c4e5264…`。完整四线已执行：pytest **10022 passed / 25 skipped / 1 xfailed / 16 failed / 1 warning、0 errors**，16条均非本批新红（12条既有货架/分类漂移、2条既有115/116、2条Windows环境）；connector/DSH/Rust通过，不称全绿；547G 仍暂停，不借本批关闭 547D/E、自动整页、真机或 547G。 证据 `evidence/548R/`。
  **548C5 B2 文字宽度节距（2026-11-08，未通过，生产已还原）**：实际缺口是 MCU 单列分支座位，统一加距与逐件外推均撞二维 `near_limit=300`，不是所有布局无解。新 `tests/test_548c5_text_pitch.py` 为 **2 passed / 1 strict xfailed**；主代理聚焦 **87 passed / 2 skipped / 2 xfailed**，connector/DSH/Rust 通过；完整 pytest **10024 passed / 25 skipped / 2 xfailed / 16 failed / 1 warning、0 errors**，失败节点与548R相同、无本批新增。注入二维座位的可行性探针经主代理复核为2候选/hard0/26网，非自动生成能力；下一步实现闭式生成规则，不默认折行、拆岛或放宽 near。证据 `evidence/548C5/`。
  **548C6 同岛二维支路座位（2026-11-08，离线三关通过；548C6R已收口）**：单模块救援轮按真实文字/器件/引脚度量生成 line 轴座位，绕针后重核 near/碰撞/文字侧；B2 自动产出1候选 `814ed66f…`、hard0、26网连通、0短路、全文完整。C5摘标3 passed、C6 12 passed；主代理聚焦 **120 passed / 2 skipped / 1 xfailed**（四负控74/2）、CH34 pinned不变，两项变异先红并cp恢复，最终渲染目检通过。B3/548C2①已裁禁标签旗入库，C7三次未通过另批；548B1/B2/B3已完成各自离线范围（见下），多岛/548D/E/547G不因此关闭。证据 `evidence/548C6/`。
  **548C6R 绕针后 leg+tail 最终复核（2026-11-08，已通过）**：tail跨网针重合经主代理复现，现以同一 `_foreign_pins_on_run` 尺在dodge后复核两段，残留整组回退。C6 **13 passed**，主代理聚焦 **121 passed / 2 skipped / 1 xfailed**，B2几何/渲染、leg与CH34 pinned不变，最终复核变异恢复。最终全量 **10038 passed / 25 skipped / 1 xfailed / 16 failed / 1 warning、0 errors**，与548R及第一轮均无新增红；connector/DSH/Rust通过，不称全绿。证据 `evidence/548C6R/`。
  **548C7/C7A/C7B 库内旗标路线（2026-11-08，未通过，生产零改动）**：岳裁定禁网络标签、旗标可入库；三次路径均未出候选，主代理负证据7 passed，聚簇与预留/布线契约另批，C3 xfail未摘。证据 `evidence/548C7/`、`548C7A/`、`548C7B/`。
  **548B1 seriesBranches 数据合同（2026-11-08，通过；完整四线已跑）**：岳全部按推荐；新测试41 passed、主代理聚焦369/2、旧摘要与CH34 pinned不变、两项变异恢复。完整 pytest **10086 passed / 25 skipped / 1 xfailed / 16 failed / 1 warning、0 errors**（16条均既有：12条货架/分类漂移、2条115/116、2条Windows环境）；connector/DSH/Rust通过，不称全绿。证据 `evidence/548B1/`。
  **548B2 跨文档校验与页面切片（2026-11-08，通过；本批不做几何；完整四线已跑）**：V1–V8与两个消费者前红24/2转26 passed，主代理聚焦423/2，V6与切片变异恢复；CH34 pinned不变。完整 pytest **10112 passed / 25 skipped / 1 xfailed / 16 failed / 1 warning、0 errors**（同16条既有）。几何属548B3，不称548B完成。证据 `evidence/548B2/`。
  **548B3 串联几何与独立语法检查（2026-11-08，正例 + 不可落座负例通过，禁止静默回退已落地；完整四线已跑，16 failed 均既有）**：每条声明注入两件 `RelativeConstraint`，`compile` 与 `check_grammar` 共用 `_with_series_arms`；座位按文档既有 axis/progress/真实引脚，几何 宿主→parts[0]→middleNet→parts[1]→终端，pitch 取原布局中心距，非GND终端旗挂臂尾真实脚；未声明/[]不变、不自动识别。生产只改 `drawcompiler.py`（最终 `d9ba64ab…`），前红10/4→14 passed，主代理聚焦232 passed/2 skipped；高边`9917b0b3cda9…`/低边`5eea1a442ce7…`各3候选、六点单调、middle一段10单位，CH34 pinned MATCH；三项变异均完成（第三项先暴露⑤b覆盖洞、测试加强后复红；恢复点`2cc92fc0…`，其后520b2兼容修复得最终hash）；渲染经主代理目检。第一轮全量 **18 failed / 10124 passed**，既有16条外2条新红为520b2（SimpleNamespace 无 `series_branches` → AttributeError），`getattr` 最小兼容修后 520b2+B3 **21 passed**，测试未改。第二轮最终 **16 failed / 10126 passed / 25 skipped / 1 xfailed、0 errors**（`full-pytest-final.log`，added=[]、removed=[]，16条均既有，不称全绿）。证据 `evidence/548B3/`。
- **既有搁置不变**：`201C`、`121b`、`text_overlap` 与 `R4` 阶段二；发布收口不顺手复活。

---

## 001–099

| 编号 | 主题 | 状态 | 证据/任务书路径 |
|---|---|---|---|
| M0 | 基线统一入口与持久化基线 | 已落 | tag `m0-baseline`；docs/persistence-baseline.md |
| M1 | 原理图审查可用（15规则+度量机具） | 已落 | `5958b1c`；tasks/011-review-rules-m1.md |
| 009d | 持久化基线三态 | 已落 | tasks/009d-persistence-baseline.md |
| 009d2 | 断连诚实（exit 3） | 已落 | tasks/009d2-disconnect-honesty.md |
| 010 | LDO 惯用法 AMS1117 | 已落 | tasks/010-ldo-idiom-ams1117.md |
| 010b | place_wire 锁窗重试（0.4.5） | 已落 | `d409026`；tasks/010b-placewire-retry.md |
| 010c | 坐标约定定案 | 已落 | `ce044a6`；tasks/010c-coordinate-convention.md |
| 011 | M1 审查规则批 | 已落 | `5958b1c`；tasks/011-review-rules-m1.md |
| 011b | facts 库 | 已落 | tasks/011b-facts-library.md |
| 011c | 连接器供电路径规则 | 已落 | tasks/011c-conn-pwr-path-rules.md |
| 011d | decap/param 注入件 | 已落 | tasks/011d-decap-param-injection.md |
| 011e | M1 晋级判据 | 已落 | tasks/011e-m1-graduation.md |
| 012 | 基础体验（内测 0.4.6） | 已落 | `e2bb78c`；tasks/012-basic-experience.md |
| 013 | 真机验证（0.4.10） | 已落 | `1798d7e`；tasks/013-realhost-verification.md |
| 015 | M2 规则批①②（容忍度） | 已落 | `501a2f4`/`5ff0a1d`；tasks/015-review-rules-m2.md |
| 016 | review-to-local-edit（M3 首切片） | 已落 | `15b3da2`；tasks/016-review-to-local-edit.md |
| 017 | 评测集扩充（度量机器/泛化结论） | 已落 | tasks/017-eval-set-expansion.md；outputs/017_* |
| 018 | 朋友内测基础体验 | 已落 | `15b3da2`；tasks/018-beta-basic-experience.md |
| 019 | 空板提示 | 已落 | tasks/019-review-empty-board-hint.md |
| 020 | 上游 issue 加固 | 已落 | `ffbdf77`；tasks/020-upstream-issue-fixes.md |
| 021 | 多工程=多窗口实测 | 已落 | `d70f59b`；tasks/021-multiproject.md |
| 022 | 全新 clone 三 issue | 已落 | `4448c59`；tasks/022-fresh-clone-issues.md |
| 023 | 多窗口路由 | 已落 | `383e524`；tasks/023-multiwindow-routing.md |
| 024 | 3.2.149 bootstrap（0.4.12） | 已落 | `ac465ae`；tasks/024-easyeda-3.2.149-bootstrap.md |
| 024b | About box 读共享运行时（0.4.13） | 已落 | （无独立任务书） |
| 025 | checkup 一条命令（0.4.14–0.4.16） | 已落 | tasks/025-review-flow-v2.md；outputs/025_* |
| 025e | update-connector 假失败修复 | 已落 | outputs/025e_update_connector_false_failed.txt |
| 026 | Worker 闹钟形态定案 | 已落 | tasks/026-worker-watchdog.md；outputs/026_probe.md |
| 026b | Worker 闹钟实现+规格修正 | 已落 | tasks/026b-worker-watchdog-impl.md；outputs/026b_* |
| 026c/026d | 闹钟规格两轮修正 | 已落 | outputs/026c_*；outputs/026d_* |
| 027 | EDITOR_API_FLOOR (3,2,149) | 已落 | tasks/027-editor-api-floor.md |
| 028 | 内测分发三件套（0.4.19） | 已落 | tasks/028-distribution-trio.md |
| 029 | add-component（M3 第2片） | 已落 | tasks/029-edit-add-component.md；outputs/029b_* |
| 030 | update-connector 多窗三档 | 已落 | tasks/030-update-connector-multiwindow.md |
| 031 | export.render PNG 超时→SVG 回退（0.4.20） | 已落 | tasks/031-export-render-png-fallback.md |
| 032 | export.render toast 自清除（0.4.21） | 已落 | tasks/032-export-render-toast-teardown.md |
| 033 | export.render 导出前自激活（0.4.22） | 已落 | tasks/033-export-render-auto-activate.md |
| 034 | activateExportPage 三步补齐（0.4.23） | 已落 | tasks/034-activate-export-page-full.md |
| 035 | patch-pin（M3 第3片） | 已落 | tasks/035-patch-pin.md；outputs/035c_* |
| 036 | insert-subcircuit（M3 第4片） | 已落 | tasks/036-insert-subcircuit.md |
| 036b | 029 位号池盲点修复 | 已落 | tasks/036-insert-subcircuit.md §036b；outputs/036b_* |
| 037 | move-block（M3 第5片收官） | 已落 | tasks/037-move-block.md |
| 038 | eprj3 适配（V4 A 档只读） | 已落 | tasks/038-eprj3-tierA.md |
| 039 | parts 工具链+facts 第一波 | 已落 | tasks/039-parts-toolchain-facts-wave1.md |
| 039b | decap 硬化+REF2033 翻闸 | 已落 | outputs/039b1_* |
| 039批② | 审查流程升级（schema /3） | 已落 | tasks/039b-review-flow-upgrade.md；outputs/039c_* |
| 040 | 解析器页归属修复 | 已落 | tasks/040-parser-page-scope.md |
| 040b | 一板一模型 | 已落 | tasks/040b-per-board-model.md |
| 041 | 跨板网络 | S1/S2 已落（`6253a0b`），S3 暂缓，S4 待真实样本 | tasks/041-cross-board-net-DRAFT.md；tasks/041s1_net_instances.md；tasks/041s2_interconnect.md |
| 042 | 解析器 parentId 双程挂载 | 已落 | `5f7cd58`；tasks/042-parser-attr-parentid.md |
| 043 | MPN 阻值解码偏差 | 已落 | tasks/043-mpn-value-decode.md |
| 044 | arch 骨架生成器 | 已落 | tasks/044-architecture-self-consistency.md |
| 045 | dsh 插件（0.1.0） | 已落 | `f4230e9`/`f01e23d`；tasks/045-dsh-plugin.md |
| 045b | exe 器件库内嵌修复 | 已落 | `634197d`；outputs/045b_blocklib_embed.txt |
| 046 | MPN 译码缺口×4 | 已落 | tasks/046-mpn-decoder-gaps.md |
| 047 | harness 卫生批四修 | 已落 | tasks/047-harness-hygiene-batch.md |
| 048 | 数字指数四位场解码 | 已落 | tasks/048-decoder-numeric-exponent.md |
| 049 | 解析器缺陷批（P2/P3） | 已落 | tasks/049-parser-defect-batch.md |
| 049-P1 | DCDC 并网修复（keep-first） | 已落 | tasks/049-parser-defect-batch.md §P1 |
| 050 | 真构建核对内嵌资源 | 已落 | tasks/050-frozen-build-verification.md |
| 052 | 审查复核与绘制方向建议 | 已落 | tasks/052-schematic-drawing-direction.md（研判；架构被 053 采用，无独立提交） |
| 053 | 画法编译器（阶段 A/B/C 地基） | 已落 | tasks/053-drawing-compiler-ab.md |
| 053B | keepout 真实裁剪等收尾三件 | 已落 | tasks/053-drawing-compiler-ab.md §六 |
| 053C–053F | **画法能力四件**：`modules[].attach`（去耦模块贴宿主岛一侧，只影响摆放）、`partTexts`（位号/型号按器件选边，让开引脚道）、`gndClustering.radius`（地网焊盘按直径上限分簇，每簇一枚 GND 旗标、簇间不连线）、`labelPolicy.stubMin` / `rowModel`（最小桩长与名字行模型）。后三条是**规格声明**：不写＝旧行为逐字节不变 | 已提交 `263929e`；测试 `tests/test_053c_attach.py` / `053d_part_texts.py` / `053e_ground_clusters.py` / `053f_policy_switches.py`；全量 8980 passed / 23 skipped / 2 环境红 | tasks/534b_v4_layout.md 续二–续五 |
| 054 | 画法编译器落图（C1，单模块进编辑器） | 已落 | `aa61768`；tasks/054-draw-stage-c-editor.md |
| 055 | 画图编译器收尾 G1/G2/G3/G6 | 已落 | `50ca8b6`；tasks/055-draw-followups-g1-g6.md |
| 056 | 多模块单页编译（C2a） | 已落 | `0459e74`；tasks/056-draw-stage-c2a-multimodule.md |
| 057 | C2b 编辑器半（离线半，PR #10） | 已落 | `986ecb3`；tasks/057-draw-stage-c2b-editor.md |
| 058 | 手册闸前置（issue #8） | 已落 | `9318506`；tasks/058-review-needs-datasheet.md |
| 059 | 真机验收收口 E1–E7 + 坑36 | 已落 | outputs/059_attr/VERDICT.md |
| defect-μ | 电容解析希腊 μ 崩溃修复 | 已落 | （无编号，PROGRESS.md:158） |
| 060 | 布局质量批（分侧/重复脚/GND 旗） | 已落 | tasks/060-draw-layout-quality.md |
| 061 | install-skill 认 harness（#11） | 已落 | tasks/061-skill-harness-claude.md |
| 062 | install-skill --agent 分发通道 | 已落 | tasks/062-install-skill-agent.md |
| 063 | warning_triage 侧车 + triage 命令（#12） | 已落 | tasks/063-warning-triage-sidecar.md |
| 064 | 旗标罗盘按符号分家 | 已落 | tasks/064-flag-compass-per-symbol.md；outputs/064_railflag/ |
| 065 | 电容挂归属脚物理侧 | 已落 | tasks/065-cap-pin-physical-side.md；outputs/065_capside/ |
| 069 | 岳画法裁决落地（旗/远脚/电源旗） | 已落 | tasks/069-far-sibling-pins-flag-join.md |
| 070 | triage key 撞车修复（#13） | 已落 | tasks/070-triage-key-identity.md |
| 071 | MPN 解码止血批（锚点闸 C） | 已落 | tasks/071-mpn-bleed-stop.md；evidence/071/ |
| 072 | 覆盖闸（#28/#29/#30） | 已落 | tasks/072-coverage-gate.md；evidence/072/ |
| 073 | 边界失败收尾（incomplete 非零退出） | 已落 | tasks/073-boundary-exit-codes.md；evidence/073/ |
| 074 | 旗引线穿越别网硬拒 | 已落 | tasks/074-flag-lead-foreign-crossing.md；evidence/074/ |
| 075 | 退出码一致性 | 已落 | tasks/075-exit-code-consistency.md；evidence/075/ |
| 076 | rc/led 未证实网闸 | 已落 | tasks/076-rc-led-unproven-nets.md；evidence/076/ |
| 077 | 电容中缀记号 | 已落 | tasks/077-capacitance-infix.md；evidence/077/ |
| 078 | MPN 日期码吞锚点 | 已落 | tasks/078-mpn-datecode-anchor.md；evidence/078/ |
| 079 | datasheet 提取器符号/电容口径 | 已落 | tasks/079-datasheet-extractor-signs-caps.md；evidence/079/ |
| 080 | issue 清仓批 0–5 | 已落 | tasks/080-issue-cleanups.md |
| 081 | pintable role≠球名 | 已落 | tasks/081-pintable-role-vs-ball.md；evidence/081/ |
| 082 | 074 遗留两件 | 已落 | tasks/082-074-leftovers.md；evidence/082/ |
| 083 | 值解析统一（values.py 下移 core） | 已落 | tasks/083-value-unification.md；evidence/083/ |
| 084 | doc.open 分类对齐 + pageUuid | 已落 | tasks/084-docopen-pageuuid.md |
| 085 | 覆盖闸补齐丢弃 producer | 已落 | tasks/085-coverage-gate-producer.md |
| 086 | reconcile 收敛 | 已落 | tasks/086-reconcile-convergence.md |
| 087 | 电容中缀无分数族放开 | 已落 | tasks/087-capacitance-nofraction.md；evidence/087/ |
| 088 | power-entry 语法（离线半） | 已落 | tasks/088-power-entry-grammar.md |
| 088b | power-entry 跟进（gnd-outlet/branchOrder） | 已落 | tasks/088b-power-entry-followups.md |
| 089 | power-entry 真机落图 | 已落 | tasks/089-power-entry-landing.md |
| 090 | A1 DesignIntent 合同 | 已落 | tasks/090-A1-design-intent.md |
| 091 | A2a params 冲突方向由 intent 定 | 已落 | tasks/091-A2a-params-fix-direction.md |
| 092 | A2b checkup 接线 + rail 额定核算 | 已落 | tasks/092-A2b-rail-ratings.md |
| 093 | A3a 架构自洽分级框架+三规则 | 已落 | tasks/093-A3a-arch-closure.md |
| 094 | A3b 采样链偏置闭合+合同接进 apply | 已落 | tasks/094-A3b-sense-bias.md |
| 095 | A4 power-entry 消费 intent | 已落 | tasks/095-A4-intent-driven-order.md |
| 096 | 页级两缺陷修复 | 已落 | tasks/096-page-two-defects.md |
| 097 | _annotation_allowance 估算修正 | 已落 | tasks/097-annotation-allowance.md |
| 098 | ic-periphery 语法（离线半） | 已落 | tasks/098-ic-periphery-grammar.md |
| 099 | CH340 真机落成（v0.5.7） | 已落 | tasks/099-ch340-landing.md |
| 099f | stub 阶梯加折线档 | 已落 | tasks/099-ch340-landing.md |

## 100–149

| 编号 | 主题 | 状态 | 证据/任务书路径 |
|---|---|---|---|
| 100 | B1 快速守卫批（#3/#9/#10/#15/#16/#19） | 已落 | tasks/100-b1-quick-guards.md |
| 101 | B2 解析器加固（#4/#5） | 已落 | tasks/101-b2-parser-hardening.md |
| 102 | B3 值解析（#8 容值尺寸码） | 已落 | tasks/102-b3-value-sizecodes.md |
| 103 | B5 规则修正（#14/#17） | 已落 | tasks/103-b5-rule-fixes.md |
| 104 | B4a 核心正确性（#11/#6/#2） | 已落 | tasks/104-b4a-reconcile-roles.md |
| 105 | B4b 位号混网（#1 最重） | 已落 | tasks/105-b4b-designator-membership.md |
| 106 | B6 connector 侧（#12/#13/#18+安全注记） | 已落 | tasks/106-b6-connector-side.md |
| 107 | 重复位号网上结论降级 | 已落 | tasks/107-dup-net-unproven.md |
| 108 | 阻值尺寸码孪生开闸 | 已落 | tasks/108-resistance-sizecodes.md |
| 109 | A4 提案器（intent→PresentationSpec） | 已落 | tasks/109-intent-proposer.md |
| 111 | draw lint 可读性检查器 | 已落 | tasks/111-draw-lint.md |
| 111a | draw lint 增补三规则（L10/L5b/L6） | 已落 | tasks/111a-lint-addendum.md |
| 111b | sys.log_read 日志面板只读（0.4.28） | 已落 | tasks/111b-syslog-action.md |
| 112 | 避障布线 wire_route | 已落 | tasks/112-obstacle-routing.md；outputs/112/ |
| 113 | 反激语法 flyback | 已落 | tasks/113-flyback-grammar.md |
| 114 | 编译器补课（支路串/lane） | 已落 | tasks/114-compiler-islands.md；outputs/114/ |
| 115 | 反激整页出图（序关系保守消费） | 已落 | tasks/115-flyback-page-compile.md |
| 116 | 编译器收官（全部序关系） | 已落 | tasks/116-ordinal-consumption.md |
| 117 | 反激整页翻绿 | 已落 | tasks/117-flyback-gate-green.md；outputs/117/ |
| 118 | 符号库实测化+五脚变压器硬伤 | 已落 | （无独立任务书）；outputs/118/ |
| 119 | 换料收口+位姿阶梯加宽 | 已落 | tasks/119-pose-ladder-widening.md |
| 120 | 第二孤岛落子收口 | 已落 | tasks/120-island-placement.md |
| 121a | spec 订正+语法建模修正 | 已落 | （无独立任务书） |
| 121b | 路径2暂停存档 | 搁置 | tasks/121-hand-plan-next.md |
| 121c | 反激手绘规划落图（离线） | 已落 | （无独立任务书） |
| 121d | 真机段（两硬阻塞如实入账） | 已落 | （无独立任务书） |
| 121e | 修 118/120 红灯 | 已落 | （无独立任务书） |
| 122 | PCB 审查路线图（DRC→模块→器件） | 已落 | tasks/122-pcb-review-roadmap.md |
| 123a | issue #58-61 文档批 | 已落 | （无独立任务书） |
| 123b | self_update 危险档 | 已落 | （无独立任务书） |
| 123c | 阶段 A·DRC 闭环 | 已落 | tasks/123-pcb-drc-stage-a.md |
| 123d | 元审查单位修复（mil/mm） | 已落 | （无独立任务书） |
| 124 | SKILL.md 减重（686→279 行） | 已落 | （无独立任务书） |
| 124b | references 打包 | 已落 | （无独立任务书） |
| 125 | 阶段 B·几何测量库 | 已落 | tasks/125-pcb-measure.md |
| 126 | 阶段 C·模块识别+通用层（母批） | 已落 | tasks/126-pcb-module-review.md |
| 126a | 地基（PcbRule/runner/module_of） | 已落 | tasks/126-pcb-module-review.md |
| 126b | 距离类规则 | 已落 | tasks/126-pcb-module-review.md |
| 126c | IPC 类规则 | 已落 | tasks/126-pcb-module-review.md |
| 126d | verdict schema /7 | 已落 | tasks/126-pcb-module-review.md |
| 127b | 盲审修复五连 | 已落 | tasks/127-blind-review-fixes.md |
| 128 | issue #63 分类器族谱修复 | 已落 | （无独立任务书） |
| 129 | 审计三连修（#67/#66/#68） | 已落 | （无独立任务书） |
| 130 | issue #69 同事上手三条 | 已落 | （无独立任务书） |
| 131a | 阶段 D·引脚名地基+pinrole | 已落 | tasks/131-power-pack.md |
| 131b | 电源包·pcb-regulator-cap-distance | 已落 | tasks/131-power-pack.md |
| 131c | 集成修复+pcb-regulator-fb-placement | 已落 | tasks/131-power-pack.md |
| 131d | MCU 包·OSC 修复+晶振规则 | 已落 | tasks/131-power-pack.md |
| 131e | MCU 包·供电组+复位启动 | 已落 | tasks/131-power-pack.md |
| 131f | MCU 包·POUR+keepout | 已落 | tasks/131-power-pack.md |
| 132 | issue #30⑥ 板级空覆盖闸 | 已落 | （无独立任务书） |
| 133a | 阶段 D·FOC 包三新原语 | 已落 | tasks/133-foc-pack.md |
| 133b | FOC 包·快赢五规则 | 已落 | tasks/133-foc-pack.md |
| 133c | FOC 包·地系统三规则 | 已落 | tasks/133-foc-pack.md |
| 133d | FOC 包·热设计三规则 | 已落 | tasks/133-foc-pack.md |
| 134 | 网络标签策略修复 | 已落 | （无独立任务书） |
| 135 | POURED 结果层破解 | 已落 | （无独立任务书） |
| 136 | validate_full 线-线间距盲区 | 已落 | （无独立任务书） |
| 137 | 布线器避让真修 | 已落 | （无独立任务书） |
| 138 | 审计新四条+#62 | 已落 | （无独立任务书） |
| 139 | issue #65 电源轨枚举/写回 | 已落 | （无独立任务书） |
| 139b | 电压键位统一 | 已落 | （无独立任务书） |
| 140 | issue #64 货架选型规则 | 已落 | （无独立任务书） |
| 141 | 绘制线·通道自适应加宽 | 已落 | evidence/141/ |
| 142 | 修 #75/#74（名单/正则） | 已落 | （无独立任务书） |
| 143 | 绘制线挖洞 swarm（33 洞） | 已落 | tasks/143-drawing-dig-triage.md；outputs/143_dig/ |
| 143a | drawcompiler/presentationspec 修 | 已落 | tasks/143-drawing-dig-triage.md |
| 143b | grammar 修 | 已落 | tasks/143-drawing-dig-triage.md |
| 143c | readability 修 | 已落 | tasks/143-drawing-dig-triage.md |
| 143d | drawapply/cli/changeplan 修 | 已落 | tasks/143-drawing-dig-triage.md |
| 143e | generate/layout 修 | 已落 | tasks/143-drawing-dig-triage.md |
| 143f | subcircuit/symbolprofile 修 | 已落 | tasks/143-drawing-dig-triage.md |
| 144 | 反激落图冲刺（旗标闸拒绝） | 已落 | outputs/144/ |
| 145a | 拆三根能力墙 | 已落 | （无独立任务书） |
| 145c | C13 符号几何修 | 已落 | （无独立任务书） |
| 145d | 修 plan 两缺陷 | 已落 | （无独立任务书） |
| 145e | 终落 P1 | 已落 | （无独立任务书） |
| 146 | 反激可读性抛光 | 已落 | （无独立任务书） |
| 147 | 走线穿体硬闸 | 已落 | （无独立任务书） |
| 147b | 硬闸误伤修复 | 已落 | （无独立任务书） |
| 147c | 复活清单生成 | 已落 | outputs/147c/revival_list.md |
| 148 | 硬闸下重新画出干净图 | 已落 | （无独立任务书） |
| 149 | 对齐岳的 P22 最低标准 | 已落 | （无独立任务书） |

## 150–199

| 编号 | 主题 | 状态 | 证据/任务书路径 |
|---|---|---|---|
| 150 | 修 149 版四处+验闸 | 已落 | （无独立任务书） |
| 155 | 岳裁五条落地 | 已落 | （无独立任务书） |
| 156 | 两案查证（导出丢件/脚号漂移） | 已落 | outputs/156/export_loss_evidence.md |
| 157 | daemon 自动拉起 | 已落 | （无独立任务书） |
| 158 | 原理图对账原则立项 | 已落 | tasks/158-schematic-reconciliation.md |
| 159 | 测试套件性能瘦身 | 已落 | tasks/159-test-perf.md |
| 160 | pytest-xdist 并行 | 已落 | （无独立任务书） |
| 161 | 挖洞审计（~30 洞） | 已落 | tasks/161-hole-triage.md |
| 162a | 测量库正确性（G1/G2） | 已落 | （无独立任务书） |
| 162b | PCB 解析层正确性（H 系列） | 已落 | （无独立任务书） |
| 163a | 布线/生成器闸门（E 系列） | 已落 | （无独立任务书） |
| 163b | 落页/lint/checkup/cli 闸门 | 已落 | （无独立任务书） |
| 164a | FOC 规则原理图对账 | 已落 | （无独立任务书） |
| 164b | 电源/MCU 规则原理图对账 | 已落 | （无独立任务书） |
| 164c | 静默分支与测量口径 | 已落 | （无独立任务书） |
| 165 | update-connector --all confirm | 已落 | （无独立任务书） |
| 166 | 在线 checkup PCB 审查做实 | 已落 | （无独立任务书） |
| 168 | 严重度架构（L8 降 INFO） | 已落 | （无独立任务书） |
| 169 | 测试形状+静默吞规则 | 已落 | （无独立任务书） |
| 170 | 收尾（测试形状对齐） | 已落 | （无独立任务书） |
| 171 | core 两提案（容值尾注/EARTH） | 已落 | （无独立任务书） |
| 172 | 丝印字宽诚实降级 | 已落 | （无独立任务书） |
| 173 | 绘制线积压（A/C/B） | 已落 | （无独立任务书） |
| 174 | pcb.geometry 桥动作（0.4.30） | 已落 | （无独立任务书） |
| 175 | 穿越代价+旗间距 | 已落 | （无独立任务书） |
| 176 | 采样链偏置规则（issue #76） | 已落 | tasks/176-sampling-bias-rule.md |
| 177 | point_in_polygon 收编 | 已落 | tasks/177-point-in-polygon-consolidation.md |
| 178 | 分域地旗入库 | 已落 | tasks/178-library-ground-flags.md |
| 178b | place_power 字形探针 | 已落 | tasks/178b-place-power-probe.md |
| 179 | connector 0.4.31（两坑修复） | 已落 | tasks/179-connector-document-source-rename.md |
| 180 | 地旗按符号放置+173C 收尾 | 已落 | tasks/180-ground-flag-by-symbol.md |
| 182 | 高速规则架子 | 已落 | tasks/182_highspeed_scaffold.md；outputs/182_highspeed_scaffold/ |
| 183 | 描边板框中心线拼合 | 已落 | tasks/183_bug98b_capsule_outline.md；outputs/183_bug98b/ |
| 184 | 值码解码覆盖不足 | 已落 | tasks/184_value_decode_coverage.md；outputs/184_value_decode/ |
| 185 | 结论收口+needsDatasheet 拆名+INSTANCE_STALE | 已落 | `c41f1c1`；tasks/185_conclusion_unified.md |
| 186 | 喂 PDF 链路闭环+hygiene 敏感串闸 | 已落 | `49bad82`；tasks/186_pdf_facts_path.md；outputs/186_pdf_facts/ |
| 187A | 183 系三洞收口 | 已落 | `1b4d3d7`；tasks/187a_outline_holes.md |
| 187B | 发布闸必拦四洞 | 已落 | `dca0373`；tasks/187b_gate_holes.md |
| 187C | daemon 版本自检+parts add --resolve | 已落 | `5932a78`；tasks/187c_daemon_version.md |
| 188A | 值码族补完+细长环披露 | 已落 | `f4bc630`；tasks/188a_value_decode.md |
| 188B | 185/186 低项清扫 | 已落 | `14ec0fe`；tasks/188b_low_items.md |
| 189A1 | 撤 PadGeometry.layer_id | 已落 | `e97c0fb`；tasks/189a1_layer_id.md |
| 189A2 | 原理图视图伪网（镜像引脚落位） | 已落 | `e97c0fb`；tasks/189a2_schematic_nets.md |
| 189A2c | 跨视图检查读数复核（527C）：**旧 7/8/6/2 是错配探针**（没走 154 板链），真读数 34 条/5 板入口，A 0 / B 34 / C 0；`min_pins` 保持 3 | 已落（本批 v0.5.18） | outputs/189a2c/evidence.md；tasks/527_pre060_loose_ends.md §527C |
| 189A2d | 跨视图 note 按**几何**分成「没画线 / 网名不同 / 落位嫌疑」，并点名全部位号（原来只列前 6） | 工作树（2026-11-06 完成，未提交） | tasks/527c2_cross_view_geometry.md；tasks/527_pre060_loose_ends.md §527C |
| 189B | 中危打包（intent/stale/判型） | 已落 | `e97c0fb`；tasks/189b_mid_pack.md |
| 189C | 离线几何渲染 canvas-svg | 已落 | `e9e914c`；tasks/189c_canvas_render.md |
| 189Cf | 底层位号丝印画出视窗 | 已落 | `de2116c`；（无独立任务书） |
| 190 | 判型口径收口+三条小账 | 已落 | `5f88b13`；tasks/190_type_and_basis.md |
| 190f | checkup --file 元数据盲区修复 | 已落 | `5f88b13`；tasks/190_type_and_basis.md §13 |
| 190S | 底层丝印文字延伸方向定标 | 已落 | `5171ed0`；tasks/190s_bottom_silk_direction.md；outputs/190s/ |
| 191A | accept-unknown 真通道 | 已落 | `5171ed0`；tasks/191_mechanisms.md；outputs/191a/ |
| 191B | 用户架/内置架合并+boards 同形 | 已落 | `5171ed0`；tasks/191_mechanisms.md；outputs/191b/ |
| 191C | KiCad 裸 (net N) 序号读取 | 已落 | `5171ed0`；tasks/191_mechanisms.md；outputs/191c/ |
| 191D | 去耦距离按电源轨分档 | 已落 | `5171ed0`；tasks/191d_decap_rail_tiers.md；outputs/191d/ |
| 192A | 挖洞修复·几何/解析/渲染 | 已落 | `5914ee2`；tasks/192_release_holes.md；outputs/192a/ |
| 192B | 挖洞·判型/闸门/合同 | 已落 | `5914ee2`；tasks/192_release_holes.md；outputs/192b/ |
| 192C | 挖洞·货架 CLI/桥 | 已落 | `5914ee2`；tasks/192_release_holes.md；outputs/192c/ |
| 193 | 进程/CPU 硬闸+保密机制补洞 | 已落 | `3434566`；tasks/193_process_and_secrecy.md；outputs/193/ |
| 193D | 文档补齐（190–193 口径） | 已落 | `02d7b9d`；tasks/193_process_and_secrecy.md；outputs/193d/ |

## 200–299

| 编号 | 主题 | 状态 | 证据/任务书路径 |
|---|---|---|---|
| 200A | v0.6.0 122 E 阶段·器件检查收口+报告整合 | 已落 `d2130b7` | tasks/200a_report_integration.md；outputs/200a/report-integration-evidence.md |
| 200B | v0.6.0 高速 A1 跨分割 | 已落 `d2130b7` | tasks/200b_cross_split.md；outputs/200b/evidence.md |
| 200C | v0.6.0 高速 A2 换层地孔+A3 差分对内 | 已落 `d2130b7` | tasks/200c1_ground_via.md、200c2_diffpair.md；outputs/200c1/evidence.md、200c2/evidence.md |
| 201A | 地/电源符号策略重写 | 已落 | `856fb0a`；tasks/201a_flag_strategy.md；outputs/201a/evidence.md |
| 201B | 拓扑感知模块落位+位姿联合搜索 | 已落 | `856fb0a`+`7ce7a5d`；tasks/201b_placement.md；outputs/201b/ |
| 201C | 布线协商三步 | **543H裁不复活**（当前目标缺陷不可复现，旧patch不可应用；交叉账独立） | tasks/201c_routing.md；`.tmp_543h_201cd/` |
| 201D | 落位搜索计价「别人的文本行」 | **部分落**（`pin-text` 随525；`text_overlap` 526撤回；**543H裁不复活**——旧路径前提未满足，island路径已用行租金） | tasks/201d_text_row_cost.md；`.tmp_543h_201cd/` |
| 201E | A* 布线效率 | **已落**（2026-10-19 实测） | outputs/201e/evidence.md；真因：`h` 纯曼哈顿、看不见 `CROSS_COST`，`expanded≈C*²`；23.2 s / 10 次调用（201C 的 68 s / 21 次**不复现**） |
| 201F | A* 可采纳下界（反向 Dijkstra 计价场） | **已完成**（工作树，待发） | outputs/201f/evidence.md；A\* 14.2 s→2.05 s（6.9×）、整页 23.0 s→11.05 s、83 预览逐字节相同；`LED_K`/`COMP` 的 expanded 判据**未达标**（原因见 evidence §4） |
| 201G | 反激整页 0 候选的两个真因（**诊断单**） | **543H已核销**：当前五岛规格1候选，13条软披露与SEC_12V 30单位旗位有5条回归；same-column仍是披露项，非关系全满足 | tasks/201g_flyback_zero_candidate.md；tests/test_543h_201g_islands.py；`.tmp_543h_201g/` |

## 500+

| 编号 | 主题 | 状态 | 证据/任务书路径 |
|---|---|---|---|
| 515A | v0.5.15 绘制引擎修洞（缝1/缝2） | **543H已核销**：6项原有防回归；旗位预留全集与器件页框归属两项修复，主代理21+20及变异通过 | tasks/515a_draw_holes.md；tests/test_515a_draw_holes.py；`.tmp_543h_515a/` |
| 515B | 发版前挖洞修复（S3#1–7 + S4#1–5） | 已落（`337f742`） | outputs/515b/evidence.md |
| 516 | 审查反馈（岳真机实测 A/B/C 级） | 已落（`6ef9ded`） | tasks/516_review_feedback.md |
| 519 | 异网 pin 尖间距：布局把两个网的针尖叠在同一点（修短路，12 对 → 0） | 已落（`1453ac7`） | 本批证据在 PROGRESS |
| 520 | L2a 批量寻址 `parts hunt`：C 号 → detail API → PDF → 提取 → candidate 落架 | 已落（随 v0.5.16/v0.5.17） | docs/parts.md §Bulk addressing |
| 551A | 分轮失败报告（`failures` 不再只保第一条） | 已落（`f56dced`） | outputs/algo_eval/（子代理 393） |
| 551B | L0 榨干归档元数据：被动件参数三路交叉（元数据 / 板上值 / MPN 值码） | 已落（`c51e3e8`） | docs/roadmap.md §7 |
| 551C | L2 datasheet 搜索：子代理并行（≤5 并发 / 每批 3–5 颗）、PDF 不进主上下文、三档可信度 | 第一段已落（520）；**三档可信度已落（522）** | docs/roadmap.md §7 |
| 521 | 提取面：**不做「扩正则」**——AI 读 `.txt` 写 facts，工具当收件闸（六道校验，最硬一条是引文逐字） | 已落（随 v0.5.16/v0.5.17） | tasks/521_ai_facts.md；docs/parts.md §Stage three |
| 522 | `facts_verified` 布尔 → `facts_trust` 三档（`candidate` / `machine_verified` / `verified`）；计算类规则吃机器核验，结论类仍要人工；finding 统一标注「未人工确认」；verdict 不涂绿 | 已落（`05b0302`；follow-up `f2bc7d2` 修层边界+重钉指纹） | tasks/522_facts_trust.md；tests/test_522_facts_trust.py；docs/parts.md §The gate |
| 523 | `category` 的授予路径：`--apply-facts` 只写 facts 不写分类，机器核验的件仍判不了（报告已如实点出两条待办） | 已落（527D，v0.5.18）：`parts classify` + `category_trust`，两道闸都问分类自己的档位 | 522 真板三读数的已知边界；tasks/527_pre060_loose_ends.md §527D |
| 527 | **v0.6.0 之前必须收口的尾巴**（527A `IntentSource` 转发三小节 / 527B connector 页型守卫 `/` 信封文档 / 527C 189A2 分类裁定 / 527D = 523 / 527E 文档收口） | 已落（v0.5.18 内测） | tasks/527_pre060_loose_ends.md |
| 527D2 | `parts classify` 的证据**不落货架**（`machine_verified` 的分类事后无法追溯出处，与 521 口径不一致）；冻结态下内置架条目改不了的提示也没有 | 规划 | tasks/527_pre060_loose_ends.md §527D「已知边界」 |
| 527D3 | **`entry.category` 的直读点**（`rules/pcb/mcureset`/`mcusupply`/`crystal`/`regulator`/`fbplacement`/`foc`/`focground`、`rules/params`/`paramspec`/`decap`/`archclosure`/`railratings`、`core/architecture`/`power_domains`）绕过 `shelf_declaration`，机器档分类仍能驱动结论规则 | **已落**（2026-10-19，工作树待发） | `partkind.declared_category` + `partkind.category_verdict`（ACCEPTED/GATED/ABSENT）+ `facts.category_gate_finding`；17 个读点逐条判档；证据 `outputs/527d3/evidence.md`；指纹 `b05d3384` / `674e07e1` |
| 528 | **0.6.0 门槛重写 + 四条裁决落地**（R4-C `update-connector --no-reload`；191D 数值不动；绘图线做硬门槛；527D2/D3 升为 0.6.0 阻塞项） | 已落 | tasks/528_060_gate.md |
| 529 | 191D 的**分类空白带**（`HF ≤ 1µF` 与 `bulk ≥ 10µF` 之间的 2.2µF/4.7µF 落 unknown → 假 WARN；补档后撤销 191D 的「输入侧无候选才 WARN」收窄） | 工作树（2026-11-06 完成，未提交；mid 档补齐，全 bulk 输入档保留 INFO 特例） | tasks/529_decap_mid_band.md；tasks/528_060_gate.md §4 |
| 528A | `bridge update-connector --no-reload`：写记录不 reload，点一次扩展菜单生效（R4 实验④的产物） | 已落（`6a563e3`） | tasks/528_060_gate.md §1；tests/test_528a_no_reload.py |
| 530A | **岛页旗标**：`IslandBlock.power_symbols`（加性）+ 跨岛地/电源一律旗标（S-16），旗标进 `bbox`；真机 10 旗标落 `test` 新页，连通 44 脚 0 失配。设计见 `evidence/523/DESIGN.md` | 工作树 | evidence/530a/（报告 + probes + raw + 落图 PNG/SVG） |
| 530B | **岛内布局核心**：主器件居中（S-03）+ 两脚件贴它服务的引脚（S-04）+ 去耦贴供电脚 ≤30（S-05）+ 同规格成排（S-06）；单岛路径几何逐字节不变 | 工作树 | evidence/530b/ |
| 530C | **岛内连线修订**：`_route` 加 `bends` / `true_crossings` 两键与「压外来针尖 / 落在外来导体上」两档过滤（S-09/S-11）；导线网名清空档实测硬违反 8→0 并查出开关 | 工作树 | evidence/530c/ |
| 530D | **命名分量化**（S-14：一条网每个连通分量恰好一个名）+ **落图不印导线网名**（岳裁定 A，`label_wire_indices`）+ 连通回验改**分区核对**；真机 16 条 spec 网 / 44 脚 / 0 失配；闸 8→1（残余是 `LED_K` 标签自己的行压 `R7`） | 工作树 | evidence/530d/ |
| 530E | `draw islands propose`（几何聚类只产出**待写的文档**）与 `draw islands apply`（六道闸 + §5.6 四级保守回退 + 件守恒）；离线两条命令，不碰编辑器 | 工作树 | evidence/530e/ |
| 530F | **多岛总验收**：① 闸降级口径落地——电学类硬拒，被容忍的**主机自印行**每页有上限且**逐条点名**（`ISLAND_GATE_TOLERATED_LIMITS`）；② 5 条老红销账（201b/551a 换夹具、113/119 改账簿、145a 改账簿）后全量 0 红；③ `LayoutIsland.name`（加性）+ `apply` 写入 + 岛页 notes 报名字；④ 真机落图终验：`draw compile` ok=True（1 条被容忍且点名）→ 落 `test` 新页 → 连通 0 失配 / 12 根带名导线=标签 / 10 旗标 / 标题栏零相交 → PNG + plan SVG → 删页存盘 | 工作树 | evidence/530f/（报告 + probes + raw + 落图 PNG/SVG） |
| 530G | **标题栏 keepout 进岛打包**（S-01）：矩形是**图页符号自己的 `TABLE`**（700×180，锚在角上、不随图幅缩放，`core.pageframe`）+ 下方留白 15%；真反激岛页对真矩形零相交；无 page_box 的岛页摘要仍冻结 | 工作树 | evidence/530g/ |
| 534 | **CH343 USB 转 UART 小板**：CH343G + Type-C 16P + 2×5P 排针，绘图线第一次全新设计 | **示例已入库 `a8613c5`（四岛版落 `test Board2 P3`）；交付由 534A/534B 收口**：独立 5 岛 spec；**V4 `/test V4` Board2 P2 六岛页全链通过**，V3 P4 与旧 V4 P2 为历史落图 | tasks/534_ch343_uart.md；tasks/534a_ch343_finish.md；tasks/534b_v4_layout.md；evidence/534b/report.md |
| 534A | **CH343 交付收口**：拆岛降低 `usb_c` 线团、三关全过、lint/连通/视觉证据 | **历史五岛页**：`40091c5d26a5db27`（`test V4` P2）；lint 0E/2W；17 网/58 脚/3 NC PASS；已被 534B 六岛页取代，不再作为交付页 | tasks/534a_ch343_finish.md；evidence/534a_v4/report.md |
| 534B | **CH343 V4 布局重做**：从六岛实验页（岳验收 20/100）转成 `attach` 去耦行 + `partTexts` + 地网分簇 | **已落 Board1 P13 `9e6240c6c29a8642`**（唯一原理图页；旧 P2/P3/P4/P5…P12 全部删除）：11 器件 / 54 wire / 18 flag；`draw lint` 0E/1W；宿主 DRC 0E/5W；逐脚 55/55。commit `263929e`。左列标签、去耦行间距、USB回环与D±背对背已由后续543H–M在P38收口；当前页见543行 | tasks/534b_v4_layout.md；evidence/534h/、evidence/534i/ |
| 533 | **岛页落图强制保护**（补 530G 的缺口：`--page-box` 是可选的，不带就没有 keepout → 530F 偏离 4 与 532 页 A 两次落进标题栏）：① 真机探明页面图幅**读得出来**——`sys.get_document_source` 的记录流里图纸符号自己带 `Width/Height/Blade Width/Title Block Position`（`document.current` 的 `schematicPage` 盒是 `{}`，读不出），接进 `parsers.schematic.sheet_attrs_from_text` → `pageframe.title_block_from_sheet_attrs`；② `draw plan` 绑活页 + 多岛时**自动**读图幅推 page_box+keepouts，读不到又没给 `--page-box` 则 exit 5；③ `draw apply` 核对 plan 自己记的 keep-out（`keep_out_note`）与目标页图幅，没记/对不上/读不到则 exit 5，**绝不静默落进标题栏**；④ 真机回归：新建 test 页自动读图幅 → 落图 → 标题栏矩形内 **0** 图元（同口径 532 页 A 仍 32）→ 连通 0 失配 → 删页存盘 | 工作树 | evidence/533/（报告 + probes + raw + 落图 PNG/SVG） |
| 536 | 岛群→子岛：schema、plan 身份与 hard 校验（不含装配/多群页级） | 已提交 `0f638de`（含在 0.5.22 历史） | tasks/536_archipelago_schema.md；tests/test_536_archipelago_schema.py；tests/test_archipelago_contract.py |
| 537 | 审查流程环境/证据/权限/交付硬闸，含已复现的采样值输入与 Windows 编码缺口 | 已提交 `0f638de`（含在 0.5.22 历史） | tasks/537_review_workflow_gates.md；Python 7650 passed；connector 536 passed；dsh-plugin 113 passed/1 skipped |
| 538 | archipelago 独立子岛编译与局部回滚（不含组装配/页级 pack/整页交付） | 已提交 `0f638de`（含在 0.5.22 历史） | tasks/538_island_compile.md；Python 7708 passed；connector 536 passed；dsh-plugin 113 passed/1 skipped |
| 539 | 537/538 对抗审查、真机只读验收与交付证据修复（F1–F9） | 已提交 `0f638de`（含在 0.5.22 历史） | tasks/539_adversarial_real_acceptance.md；真机 incomplete/partial 如实交付；最终 Python 7731 / connector 536 / DSH 113+1 |
| 540 | 0.6.0 前工作区整理、审查/绘制解耦、Rust 迁移平台准备；不改业务算法、不批量翻译 | 已落（A/B/C + 对抗修复 + 只读真机追加验收；最终候选 8132 passed / 94 skipped / 5 xfailed） | tasks/540_pre060_platform.md；tasks/540b_review_draw_decoupling.md；tasks/540c_rust_platform.md；**evidence/540/candidate-regression.md**；outputs/review/540/ |
| 541 | **审查分阶段交付与可中断流程**：initial/partial 检查点、冻结输入、同基准复读、中止只读已有产物出 partial；运行时闸 R1 RunManifest、R2 `--strict` 重算 guard、R4 `--strict-partial` 已实施（显式 opt-in），R3 DSH pre-execute 与公开接口 allowlist 未实施 | 已落（§3.0a 纪律层）；R1/R2/R4 strict 工作树（2026-11-06，未提交） | docs/review-sop.md §3.0a；tasks/review-stage-runtime-gates.md；tasks/541_offline_runtime_gates.md；tests/test_review_stage_delivery.py、test_541_run_manifest.py、test_541_strict_reuse.py、test_541_partial_categories.py |
| 542 | **原理图绘制 3.0**：drawing-line 集成、反激整页三关、四缝挖洞修复、RC 冻结与 V4 交接；CH343 示例 | **P0 完成并纳入 0.6.0**：P4 三关、岳人眼与重开 `saved_verified` 全过 | tasks/542_schematic_3_0_nov01.md；evidence/542/final-p4.md；evidence/201h/live/ |
| 543 | **拓扑角色驱动的构造式布局**：去耦服务关系、文字/旗标/通道硬预留、成对信号与同拓扑自动基准；**agent 语义分岛，解释器负责几何**；自动、参考重放和 agent 微调分开验收 | **CH343 P38 与CH340 P39均过三关**：P38=`0ec4dc022ef38563` 已关闭重开`saved_verified`；P39=`62e4828acc56a307` 为第二拓扑，12器件/36计划导线/17旗、lint 0E/0W/0I、独立逐脚45/45+15NC=60/60、宿主视觉通过。543G补齐非去耦信号支路、完整flow阅读列、branchOrder与振荡bay；无参考坐标。P39持久化未重开验证；最终全量9962 passed/25 skipped/14 failed（12条外部货架漂移+2条环境红，本批6条回归已修） | tasks/543_semantic_layout.md；evidence/543g/、evidence/543n/；543K/L已随`924a180`提交 |
| 544 | **checkup / arch 写盘失败边界**：目录不可写、`--out` 为普通文件、`arch --out` 为目录或骨架写不进去，均 exit 2 + 人话、无 traceback；部分产物已落盘时如实报未完整交付 | **已落**：8 条专项测试，主代理含邻域 213 passed；其它命令写盘合同不改，真实 ACL 只用 monkeypatch 等效分支覆盖 | tasks/544_checkup_output_errors.md；tests/test_544_output_errors.py；.tmp_544/ |
| 544P | **DSH 命令行凭据打码**：`commandLine` 在正常返回与 spawn 异常进入模型前统一过 `redactSecrets`，实际 spawn argv 不变 | **已落**：新增 2 回归；DSH 129 passed / 1 skipped + typecheck/build；原 T-E07 rawOccurrences=0、maskedOccurrences=2 | dsh-plugin/src/cli.ts；dsh-plugin/tests/cli.spec.ts；.tmp_test_run/T-E07/ |
| 545 | **checkup 同目录 OS 互斥与串行重跑提示**：并发后到者在模型/daemon/报告前 exit 2，锁不可用也失败关闭；崩溃由内核释放，串行续审保留并打印 rerun | **已落**：13 条专项含真实跨进程/崩溃释放；主代理含 544 与邻域 226 passed；POSIX 分支未实测 | tasks/545_checkup_output_lock.md；tests/test_545_checkup_output_lock.py；.tmp_545/ |
| 546 | **daemon / connector 同系列版本兼容**：只要求 major.minor 同步，补丁号独立；同系列双向 compatible，新动作按能力探测；0.6.1 daemon 可与 0.6.0 connector 做既有动作 | 工作树（2026-11-06 完成）；聚焦 457 passed / 3 skipped + 桥邻域 153 passed，变异已恢复；**已随 0.6.1 正式版发布（`9ffeb3b`）**；真实编辑器内 0.6.1 daemon + 0.6.0 connector 混跑仍未做真机验收 | tasks/546_version_series.md；tests/test_doctor.py、test_537c_environment.py、test_069c_guided_doctor.py |
| 547 | **SmartMedicineBox 固件约束逻辑原理图实测**：30 件 / 31 网 / 5 NC / 8 岛；来源与假设分账，agent 分岛、解释器几何 | **自动整页仍未通过；547S 已通过**：共享网三档合同统一，主代理 87 passed / 1 strict xfailed + 独立变异通过；四键已锚各自 KEY。547D 暂停于 auto 的 LED2/LCD_SDA 标签走廊。**547F 命名脚/编号同脚生产修复已验收但未提交**：仅聚焦 197 passed / 1 strict xfailed + 独立变异，真实 MCU v5 出 draw-module/65 岛/14 件，不冒充自动整页 | tasks/547_smart_medicine_box.md；evidence/547/；tests/test_547_shared_branch_nets.py、test_547_repeated_shunts.py、test_547_named_pin_plan.py |
| 547G | **自动 / agent-adjusted 双轨与辅助整页**：agent 局部几何计划复用现有 LayoutPlan/ChangePlan 与确定性校验，不互记自动成果 | **G1–G3 完成、G4 部分完成、当前暂停**：30件/31网/5NC/8岛辅助页过离线双层闸+独立逐脚/NC+逐岛视觉；主代理 lint 0E/0W/13I、宿主网表 30/30+31/31+5/5、0短路；DRC 0 error/200 warn `passed=false`（非通过）；持久化仅 `saved_unverified`，待岳手动关闭重开 test V4 + 完整四线/复验。辅助成果不关闭 547D/E，不是自动整页、不可投板 | tasks/547_smart_medicine_box.md §547G；docs/draw.md；evidence/547/g4/ |
| 548 | **自动绘制能力阶梯**：N≥3 支路与标签走廊、显式二件串联、扰动/多岛组合、547 自动整页及真机闭环 | **A 完整 N≥3 面板支路出口通过（限已测电路族，A-R 补齐灯/蜂鸣器）、B1/B2 完成、B3 正例与不可落座负例通过且禁止静默回退已落地（checker 六点未做）、C 部分通过、C2 前提被证伪、C3 的 ②③④ 已落、C4 的 B1 落、B2 已由 C6 关闭而 B3 未落、R 只补测试与文档（2026-11-08）**：548A 冻结夹具与失败证书（`repro.py` 从冻结夹具回读，不随测试漂移），并查出 547D 夹具**缺 `PC0` 脚**（`BUZZ` 声明的 `U1.PC0` 不在内联 `MCU32` 里，真实 547A 库有）——已按真实库左侧补回，电路/网表/断言不动；联合几何实测杠杆＝**支路体体位**（`probe_pose.py` 可 `ok=True` 且四键各成节点），窄门尝试（坐标判据）曾让 547A `--runxfail` 见绿并出现 strict XPASS，但同时把飞反激页面 5 条改红（gate 开 5 failed/69 passed ↔ gate 关 74 passed），已整体回退、xfail 恢复。2026-11-08 补 G9「同宿主同回流支路组（同宿主、同 other 网、两脚件、组 ≥3）」后：547A 命中 8/9，`--runxfail` 2 passed、出现 `[XPASS(strict)]` 后摘标（断言未动）2 passed；4 负控（`201b`×2、`119`、`120`、`534`）gate 开/关均 **74 passed / 2 skipped**。**548A 完整 N≥3 面板支路出口通过（限已测电路族；A-R 补齐灯/蜂鸣器独立断言）；仍不记自动整页**（未跑真机、未落画布）。548B 串联语义不属这批；**548B 语义合同已获岳全部按推荐并实施完毕（2026-11-08）——B1 数据合同、B2 跨文档校验、B3 串联几何与独立 checker，状态见 §13–§15，证据 `evidence/548B/`、`evidence/548B1/`、`evidence/548B2/`、`evidence/548B3/`**；**548C 扰动与组合部分通过（2026-11-08）：A/C/D 8/11 过，B 0/3（长文本过拟合），E 0/2（GND 分区未打通），证据 `evidence/548C/`**；**548C2 批次前提被证伪**（E 的拒因与岛数无关——547A 自己的 mcu 在页面预算 radius=100 下同样 4 节点；生产代码零改动）；**548C3 的 ②③④ 已落**（成员名过 `_profile_pin_ruler` 解析成脚号、页 label 改画自有水平承载杆、④ strict xfail 钉覆盖洞；只改 `pagecompiler.py`，① 已裁禁标签旗入库、C7 三次未通过）；**548C4 的 B1 落、B2/B3 未落**（只改 `drawcompiler.py`，闸点名的 `texts × labels` 相撞才补墙重建 ≤4 轮、无碰撞 0 轮；B2 节距、B3 3V3 陈述未落）；**548R 无生产改动**：聚焦 85 passed / 2 skipped / 1 xfailed，C3 `preferred` 变异 1 failed/4 passed/1 xfailed、C4 `TEXT_LABEL_REPAIR_ROUNDS=0` 变异 3 failed/1 passed，恢复哈希 `975e6b1c…`/`9c4e5264…`。未跑真机、未落画布、不记自动整页；548R完整四线已执行：pytest **10022 passed / 25 skipped / 1 xfailed / 16 failed / 1 warning、0 errors**，16条均非548R新红（12条既有货架/分类漂移、2条既有115/116、2条Windows环境）；connector/DSH/Rust通过，不称全绿。**548C5 B2未通过，生产已还原**：单列分支统一加距与逐件外推均撞二维 `near_limit=300`，不是所有布局无解；主代理聚焦 **87 passed / 2 skipped / 2 xfailed**，完整 pytest **10024 passed / 25 skipped / 2 xfailed / 16 failed / 1 warning、0 errors**，失败节点与548R相同、无本批新增；注入二维座位的可行性探针经主代理复核为2候选/hard0/26网，非自动生成能力。**548C6 已把闭式生成落入生产并通过离线三关**：B2自动1候选 `814ed66f…`、hard0、26网、0短路、全文完整；主代理聚焦120 passed/2 skipped/1 xfailed、四负控74/2、CH34 pinned不变、两项变异恢复及最终视觉通过。**548C6R 已补绕针后leg+tail最终复核**：跨网针残留整组回退，C6增至13 passed，主代理聚焦121 passed/2 skipped/1 xfailed，最终复核变异恢复；最终全量10038/16与548R及第一轮均无新增红。**548C7/C7A/C7B 三次旗标路线未通过、生产零改动**，聚簇与预留/布线契约另批。**548B1 数据合同已落**：41 passed、主代理聚焦369/2、旧摘要与CH34 pinned不变、两项变异恢复；548B2 跨文档校验（本批不做几何）与 548B3 串联几何均已通过各自离线范围（B1 完整 pytest 10086/25/1/16、B2 10112/25/1/16，16 failed 均既有；B3 最终 16 failed/10126 passed、0 errors（`full-pytest-final.log`，added=[]、removed=[]，16条均既有）；第一轮 18/10124 与 520b2 两条新红→21 passed 记录保留）。 | tasks/548_drawing_capability_ladder.md §5–§18；evidence/548A/、548B/、548C/、548C2/、548C3/、548C4/、548R/、548C5/、548C6/、548C6R/、548C7/、548C7A/、548C7B/、548B1/、548B2/、548B3/；tests/test_547_repeated_shunts.py、test_548c3_page_port_members.py、test_548c4_text_label_repair.py、test_548c5_text_pitch.py、test_548c6_two_dimensional_seats.py、test_548b_series_branches.py、test_548b_series_validation.py、test_548b_series_geometry.py |
| 549 | **首次配对显式授权**：取消"Origin + TOFU 即可写配对"；CLI `bridge pair <CODE>` 用 CLI token 调 daemon-owned `pair.authorize`，daemon 内存单槽 5 分钟 grant，编号 8 位 Crockford base32 公开可显示、token 永不显示 | **工作树实现，未提交、未发布、未做真机**：未认证的任何 Origin（`pro.lceda.cn` / `https://client` / 无 Origin）都不能首配或换配，有效旧配对任意 Origin 可重连；旧无编号 Connector 首配报 `code-missing` 要求升级；错码不销毁 grant（红队 2026-11-10 推翻任务书旧的"10 次作废"），失败次数只进服务端审计；未认证 detail 仅 `pairCodeRequired`+`reason`；严格非法码 `BAD_REQUEST` 且不覆盖有效 grant；活动窗口不许顶掉；记录写盘用同目录临时文件 + `os.replace`，成功后才消费 grant；hello `data.pairCodeUsed` 只在真写了记录时 true，Connector 此时才轮换公开编号；Web Crypto only，无 `Math.random`、零/恒定随机失败关闭；编号独立键、重连稳定、re-pair 换 token 和编号。读数：**已随 0.6.1 正式版发布（tag/Release `targetCommitish=9ffeb3b`）；本地实现、离线验收及 4.1.93 真机/回滚验收完成；4.1.71 仍只有模拟证据**。**真机（EDA 4.1.93 `test V4`，独立 BOARDWISE_HOME）**：新 Connector `--no-reload` 写入后经宿主菜单激活，首次 `bridge pair` 成功（审计 `authorizedBy=pair.authorize`，编号只留掩码），`sys.probe`（报 4.1.93）/`doc.list` 通过，`checkup` 得 **77 components / 225 nets**（exit 1 是工程自身 85 项 ERROR，`completion=incomplete`）；隔离 daemon 重启后未再授权、旧 token 自动重连且 `doc.list` 成功（审计 `pair-authorize=1 / pairing=1 / re-pairing=0`）；再用原 0.6.0 bundle `--no-reload` 回滚，最终 Connector **0.6.0** / daemon **0.6.1** / 两窗口 connected、paired fingerprint 不变，源 package/extension 元数据逐字节恢复。主代理 Python 聚焦 **455 passed / 3 skipped**、Connector **608 passed** + typecheck、DSH **137 passed / 1 skipped** + typecheck/build、Rust **111 passed / 4 ignored**、CLI 合同一致；**全量 Python 一轮 10611 passed / 25 skipped / 1 xfailed / 23 failed / 5 errors（27:15），不是全绿**：两条 `test_537a_daemon_write_policy`（549 新动作未登记非 design-write 例外，`pair.authorize` 已补为第四个 `design_write=False` 例外、`risk=write` 不变）由聚焦 **126 passed** 关闭，4 处 549 测试审计写仓库根已改 `tmp_path`，其余为既有货架数据、绘制线在途与已知 MSYS 环境错误，未跑第二轮。红队两轮 7 条 + 3 条非阻断项已修，无已知阻断项。4.1.71 无真机（只有模拟 Origin 证据），新版 daemon 与 Connector 必须同步部署；未做提交/推送/版本 bump/发布/生产升级、未做整板验收 | tasks/549_pairing_authorization.md；outputs/review/549_real/ACCEPTANCE.md；outputs/review/549_real/checkup/；src/boardwise/bridge/{daemon.py,protocol.py}；src/boardwise/cli.py；src/boardwise/commands/shared.py；connector/src/{random,config,transport,index}.ts；tests/test_549_pairing_authorization.py、test_bridge.py、test_bridge_cli.py、test_537a_daemon_write_policy.py；connector/tests/pairing-code.test.mjs、config.test.mjs |
| V4 | **立创 EDA Pro 4.x 适配**：归档与 `.eprj3` 单 PCB 审查、在线容器/page、主机 ERC 与证据边界 | **首批已随 `e431e94` 落入 0.6.0**；**归档多 PCB 逐板已随 `a4fc387` 提交（038P）**；多板 + 库文档同名、真实 NC、缺省 `yAxisDirection`、部分跨视图语义、实时 PCB 位图与后续真样本仍开放。**边界口径见 `docs/v3-v4-boundary.md`** | tasks/038-eprj3-tierA.md；tasks/038_v4_live_gaps.md；tests/test_038p_eprj3_multi_pcb.py；docs/v3-v4-boundary.md |
| 038R | **V4 审查线差分调研**：容器/在线通道与 P0–P2 顺序、共享模型边界 | 调研完成，首批已实施 | tasks/038_v4_review_line_research.md；outputs/review/v4-review-line-research.md |
| 038S | **真实 eprj3 样本只读差分**：证实原理图一致与 PCB builder 复用，发现 EOF、覆盖、版本与 POUR/POURED 单位差 | 样本调研完成，首批适配已实施；POURED 1:10 与旋转矩形已由 038K 关闭，归档多 PCB 已由 038P 关闭并于 `a4fc387` 提交；真实 NC、缺省 yAxisDirection 与 eprj3 在线容器仍开放 | tasks/038_v4_sample_research.md；outputs/review/v4-review-line-research.md §6；.tmp_v4_sample_20261031/REPORT.md |
| 038F | **V3/V4 容器隔离与单 PCB Tier-B**：F1 EOF、F2 版本、F3 覆盖、F4 source、F5 CLI/checkup；共享规则/报告 | **已随 `e431e94` 落入候选**；**归档多 PCB 逐板已由 038P 关闭并随 `a4fc387` 提交（`test V4` 两空板对账，真实多板 + 库工程未实测）**；单模型 `review --view pcb` 多板仍拒绝，真实 NC 与 eprj3 在线容器未关闭，POURED 单位与旋转矩形不再列为开放项 | tasks/038_v4_isolation_plan.md；outputs/review/v4-eof-frame.md；v4-eprj3-version.md；v4-eprj3-pcb-coverage.md；v4-eprj3-pcb-source.md；v4-eprj3-tierb.md；tests/test_038p_eprj3_multi_pcb.py |
| 038O | **V4.1.93 在线只读验收与 O1–O3 修复**：doctor 9/9、page 采集、PCB render 不适用、逐条 ERC 与证据缺口披露 | **已随 `e431e94`/`643cf6d` 落入候选**；板级仍 incomplete，多 PCB/全格式语义未关闭 | tasks/038_v4_online_acceptance.md；tasks/038_v4_live_gaps.md；outputs/review/v4-online-acceptance.md；outputs/review/v4-live-gaps-acceptance.md |
| 038G | **Short-Symbol 网表语义**：跳线不再产生假 `Symbol` 网，按页并网；冗余跳线不再翻转普通簇的显式标签/电源旗标优先级 | 已落 `466ca6e`，冗余守卫随 `d542f14` 收口；合成回归含跨页隔离、悬空脚与命名优先级 | tests/test_038g_short_symbol.py；tests/test_040_page_scope.py |
| 038J | **V4 分歧库副本诊断**：SYMBOL/DEVICE 同 UUID 的模型可见定义不同才计数，纯元素重编号不误报；first-wins 不变，冲突进入 console/md 与 coverage 闸 | 已落 `d542f14`；相同复制 0、真实冲突逐份计数，`coverage.recordsDropped` 含第四项 | tests/test_038_eprj3.py；tests/test_020_parse_drops.py；tests/test_072_coverage_gate.py |
| 038K | **旋转矩形与 POURED 几何**：R 路径按存储 `(x,y)` pivot、声明角度 CCW 读取；空 POURED supersession 语义不变 | 已落 `d542f14`；54 父区域/1843 点 containment 全过，PGND 铜岛 30→12 有元素与面积证据；旋转圆角和 BOARD_OUTLINE 不扩支持 | tests/test_038k_rotated_rectangles.py；tests/test_135_poured_result.py；tests/test_131f_mcu_crystal_keepout.py |
| 038L | **Rust SYMBOL 垂直迁移**：V3 zIndex/V4 pin_id、两阶段 ATTR、重复脚号逐字段合并、重编号不参与冲突判断 | 已落 `d542f14`；Python/Rust 9-case 差分一致，工作区 74 passed/4 ignored | rust/crates/boardwise-core/src/symbol.rs；tests/test_038l_symbol_differential.py；docs/rust-platform.md |
| 038M | **Rust DEVICE 垂直迁移**：`device-library-sample` 成为第 8 个 kind，首 `META`、重复 uuid first-wins、模型可见差异才计冲突 | 已落 `a4fc387`；case book 9→11，Python/Rust 投影一致，旧 9 case 不变；**属性浮点溢出的文本差分已修**（与 Python 对齐 `inf`/`-inf`，`json.dumps` 的 `NaN`/`Infinity` 拼写保留、有限值不变） | rust/crates/boardwise-core/src/device.rs；tests/test_038m_device_differential.py；docs/rust-platform.md |
| 038N | **Rust FOOTPRINT 库垂直迁移**：`footprint-library-sample` 成为第 9 个 kind，首 `META` 生效、重复 uuid first-wins（空标题占位）、字面 `"null"` 标题保留；输出只有 `schema`+`footprints`，无 stats、无冲突计数 | 已落 `a4fc387`；case book 11→13，Python/Rust 投影一致，旧 11 input 不变 | rust/crates/boardwise-core/src/footprint.rs；tests/test_038n_footprint_differential.py；docs/rust-platform.md |
| 038P | **eprj3 多 PCB 逐板审查**：同一 `source`/`runner` 逐板出 `boards`（title/boardUuid/components/checksRun/findings），`checkup --file` 逐板落地；`_load_model(view=pcb)` 多板**列出板名后拒绝**并指向 `checkup`，单板历史形状不变；**合流守卫见 038P1**（重复板拒绝、分歧库拒绝、相同副本允许、无 uuid 板按 stem 命名） | 已落 `a4fc387`；`test V4` 两个空 PCB 在线/离线 `boards`、32 checks、40 findings 一致；**真实多板 + 库工程未实测**（守卫只有合成证据）；`review --view pcb` 多板仍拒绝 | tests/test_038p_eprj3_multi_pcb.py；src/boardwise/parsers/eprj3.py；src/boardwise/engines/pcbreview.py；docs/v3-v4-boundary.md |
| 038P1 | **多文件合流的三处说谎面**：① 无 `DOCHEAD.uuid` 的板按文件 stem 命名（`pcbTitles` 改为按 PCB 文档顺序的列表，不做 uuid 查表）；② 两份文件同一个 PCB 文档 uuid **明确拒绝**（同一块板导出两次不审两遍、不按标题聚合、不静默去重）；③ `FOOTPRINT`/`DEVICE`/`SYMBOL` 同 uuid 只有**记录序列签名相同**（保留顺序/id/body，仅剔 `DOCHEAD` 的 editVersion/updateTime/version/client/user）才允许合流，**分歧拒绝**、不串板 | 已落 `a4fc387`；单文件旧行为不变，旧差分 case 与两空板读数不变；**合成样本证据**，真实多板 + 库工程未实测 | tests/test_038p1_eprj3_multi_guards.py；src/boardwise/parsers/eprj3.py；docs/v3-v4-boundary.md；本地探针 `.tmp_joint_audit/`（ignored，非已提交产物） |
| 038T | **Rust 声明解析投影垂直迁移**：`footprint-declared-sample` 成为第 10 个 kind，输入 `text`+`value` 走同一对 Python 阅读器（`_collect_footprint_titles` → `_resolve_declared_footprint`），只回答原理图 `Footprint` 字段声明了什么；输出 `schema`+`footprint`+`libraryId`，三个分支不单独出字段 | 已落 `a4fc387`；case book 13→15，Python/Rust 15/15 一致，旧 13 input 不变 | rust/crates/boardwise-core/src/footprint.rs；tests/test_038t_footprint_declared.py；docs/rust-platform.md |
| 038W | **`PAD_NET` 增量日志的每脚判优**：PCB 每脚投影键只有 `(component, pin)`，旧实现用 `setdefault` 让文件靠前的旧网获胜；改为复用 038U 原子视图的同一 ticket/client 判优，不复制第二套比较规则 | 工作树（2026-11-06 完成，未提交）；最终全量在途 | tasks/038w_pad_net_journal.md；tests/test_038w_pad_net_journal.py |
| 038X | **默认货架路径与缺失披露**：非 frozen 的默认读写改用 `resources.parts_library()` 绝对路径，只读入口不再把「文件不存在」静默读成「货架为空」；`load_parts` 的「缺文件可建空架」合同不变 | 工作树（2026-11-06 完成，未提交）；最终全量在途 | tasks/038x_shelf_resolution.md；tests/test_038x_shelf_resolution.py |
| 038Q | **原生 CBB 与复用模块准备**：Q1 库只读搜索/身份，Q2 上游候选归一化，Q3 符号文件只读通路，Q4 单符号 elibz2 profile；原生 `block_symbol` 另按真实样件推进 | **Q1–Q4 已完成各自范围（2026-11-11）**；AMS1117 单符号身份/几何已核对，其余器件身份、原生块样件/端口规则和个人库放置未覆盖，**type 17 待证实**；四个模块仍为 candidate/unverified/notForDrawCompile | tasks/038q_cbb_native.md；tasks/038q1_cbb_readonly_inventory.md；tasks/038q2_upstream_module_seed.md；tasks/038q3_symbol_file_read.md；tasks/038q4_elibz2_symbol_profile.md |

## 字母/别名批号与里程碑（E / R / perf / bug98 / releases）

| 编号 | 主题 | 状态 | 证据/任务书路径 |
|---|---|---|---|
| E1 | 封装一致性对账 | 已落 | （无独立任务书） |
| E2 | 极性/丝印检查 | 已落 | （无独立任务书） |
| E2b | 方向不统一降 INFO | 已落 | （无独立任务书） |
| E3 | 降额物理层 | 已落 | （无独立任务书） |
| E3b | 修 focground 读错视图 | 已落 | （无独立任务书） |
| E4 | 报告整合（E 阶段收口） | 已落 | （无独立任务书） |
| bug98-A | 板框描边拼合 | 已落 | tasks/bug98-A-outline-stitch.md |
| bug98-B | footprint id 回退 | 已落 | tasks/bug98-B-footprint-id-fallback.md |
| bug98-C | 控制台 UTF-8（查证=旧 exe） | 已落 | tasks/bug98-C-console-utf8.md |
| perf-01 | 性能热力图测量 | 已落 | tasks/perf-01-measure.md；outputs/perf/heatmap.md |
| perf-02A | 生产备忘化 | 已落 | tasks/perf-02A-memoization.md |
| perf-02B | 测试侧缓存 | 已落 | tasks/perf-02B-test-cache.md |
| R1 | 桥能力补齐 | 已落（v0.5.12） | tasks/roadmap/R1-bridge-completion.md |
| R2 | PCB 审查加深 | 已落（v0.5.13） | tasks/roadmap/R2-pcb-review-deepening.md |
| R3 | KiCad 第二宿主 | 规划（0.6.0 后） | tasks/roadmap/R3-kicad-harness.md |
| R4 | 真热更 stub | 在途（阶段二待立） | tasks/roadmap/R4-true-hot-update.md；outputs/R4/design-proposal.md |
| R4a | 真热更阶段一收尾+安全设计定稿 | 已落 | `779b953`；tasks/R4a_hot_update_stage1b.md；outputs/R4/evidence.md |
| R5 | SPICE 远景侦察 | 规划（冻结） | tasks/roadmap/R5-simulation-recon.md |
| 路线图任务包 | tasks/roadmap/ 五包+README | 已落 | tasks/roadmap/ |
| 六PR合并 | PR #77–#82 合并+修补波 | 已落 | （无独立任务书） |
| 测试制度与发布闸 | 三闸纪律入文档 | 已落 | docs/testing-doctrine.md |
| dsh-market 上架 | 上架 awesome-dsh-plugin+仓库 topics | 已落 | PR #5981 |
| DSH STORE 适配 | dsh-plugin 0.1.2 lib 入库+repository | 已落 | `344f2e1`/`4489750`/`5475f35`/`c04ae32` |
| release v0.5.0 | 补 4 天拖欠（画法编译器全链） | 已落 | `560dae4` |
| release v0.5.2 | 107/108/109/111/111a/111b | 已落 | `a46acbd` |
| release v0.5.7 | 绘制线封存转 PCB 主线 | 已落 | — |
| release v0.5.8 | E 阶段四件 | 已落 | — |
| release v0.5.9 | 157 daemon 自动拉起 | 已落 | — |
| release v0.5.10 | 审查正确性大修 | 已落 | `d6896fd` |
| release v0.5.11 | 地族隔离+connector 诚实化 | 已落 | — |
| release v0.5.12 | R1 桥能力补齐 | 已落 | — |
| release v0.5.13 | R2 PCB 审查加深 | 已落 | tag `v0.5.13` |
| release v0.5.14 | 挖洞修复+192 批+190S | 已落 | tag `v0.5.14`（`5914ee2`/`f2c53ae`） |
| release v0.5.15 | 515B + 516（201C 踢出） | 已发（tag `v0.5.15`） | tasks/SCHEDULE.md |
| release v0.5.16 | 520 + 521 + 522（审查线资料获取三连）+ 绘图推演简报；内测 | 已发（tag `v0.5.16`，prerelease） | tasks/SCHEDULE.md；PROGRESS |
| 524 | **v0.5.16 挖洞补做**（5 缝只读 swarm，12 条高严重级全修：引文闸子串/pin 未绑引文/两规则绕档位/审计无 dest/offline 假话/shelf 清身份/null 变 verified） | 已落（`8c87070`） | PROGRESS；6 条新回归 |
| release v0.5.17 | v0.5.16 的洞修复；内测 | 已发（tag `v0.5.17`，prerelease）；v0.5.16 notes 已标「请用 0.5.17」 | tasks/SCHEDULE.md |
| 525 | **新布局目标**：CP-SAT 六轮推演收口 + 两处真缺陷修复（`_elbow_route` 拐点漏检 → netlist 并点；布局里缺 pin/文字行净空 → 21 处 pin 尖被邻居 value 行埋葬）。新增 `placement.pin-text` 项（topology 轮开） | 已落（`bbf85a4`） | `tests/test_525_pin_text_row.py`；PROGRESS |
| 526 | **走廊不是瓶颈**：探针筛选零收益（restart 0 本来就 7/7 通且代价最小）；reserved 审计推翻上一条（清空 60 个预留道后 `goal_wall` 逐字不变）；真凶是 `U4.1` 压在 `R8` 值行上沿。**「文字行参与占位」试过又撤回**：`presentation_nolocks` 上 pin-text 1.5→1.0、走廊消失，但 A/B 在整页 presentation 上从「拒 `SEC_12V`」退化成 14 条 `text-overlap`（代价项只看见器件行，readability 还数电源旗/网名/旗名）——**只做一半的约束比不做更差** | 结论已记，代码撤回 | PROGRESS；`experiments/reserved/`（`.tmp_corridor`） |

## 待人工核对（不猜测，按原文保守入表）

1. **`052`**：PROGRESS 自述「working tree changes not committed yet」，后续称架构已被 053 采用——表中记「已落（研判）」并注明无独立提交。
2. **有任务书但 PROGRESS 无记录、状态未知**：`002`、`003`、`004b`、`004c`、`004f`、`008`、`008b`、`009c`、`014`、`066`、`067`、`110`、`110a`、`110b`、`110c`、`110d`（多为早期/调查类，未逐条留痕）。其中 `110/110a-d`（反激规划）与「121 反激规划落图暂停」同源，疑为`搁置`，但 PROGRESS 无明文。
3. **`515A`**：任务书存在（10-17），PROGRESS 只有 515B 记录——按 `规划` 记，等 201C/515A 排期明确后升级。
4. **无任务书可引的编号**（「证据」列留空，非歧义）：`132`、`134`–`142`、`123a/b/d`、`124/124b`、`#55`、`E1`–`E4`。
5. **`defect-μ`**：PROGRESS 里唯一无编号的修复条（希腊 μ KeyError），已按原文标题收录。

> **已核（2026-10-17，主代理跑 `git log`）**：草稿中 182–191 长尾、190S、193、193D、201A/201B、R2、R4a 的「工作树」判定**全部升级为 `已落`**，提交号见上表；
> `515B`（`337f742`）与 `516`（`6ef9ded`）已随 v0.5.15 落账。**2026-11-06 新增 `工作树` 行的有
> 038W/038X、189A2d（527C2）、529 与 541 的 R1/R2/R4 strict——均未提交，最终全量在途**；
> 表内其他仍标 `工作树` 的老行按各自证据列自述，未逐条复核提交状态。
