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

## §0 当前在做（资产整理基线 2026-11-17；流水历史截至 2026-11-14）

- **提交状态（562A/B 实现后）**：HEAD `0b21342` 与 origin/main 一致。550B=`9f73ede`、552–555=`14e8f39`、556–560=`0ac8973`、561=`0b21342` 均已推送；087E/F=`3d4a0d5` 在远端。绘制线与其他 owner 的未提交 hunks 保留。
- **562A/B 工作树完成、未提交未推送**：Connector `pcb.path_probe` 仅图证据；Python `core/livepath.py` 双向邻接+BFS；`pcb path`、protocol、owners=161、`--json` 原子写入已接通。主代理 52 passed、十三文件 376 passed、Connector 876 passed；Arc/预算、单向/截断、错 action/JSON 写失败变异均先红后 cp+SHA 恢复。562C 仅真机激活与同会话对拍，DSH 适配不做。
  推送、部署与发布仍需岳逐次批准；人工签核、V3/生产非空板与真实设计写边界不变。
- **559/560 收尾口径（2026-11-19，560；2026-11-20 原生激活成立后更订）**：`pcb.connection_probe` 的原生 action **已激活**——
  daemon 重启 + connector 写入 + 用户完整重启 EDA 后，新实例 `inst-015644463-2wuenu0j`（`bootstrapAt`/`activateAt`
  =2026-11-20T01:56:44.463/465Z）返回 `boardwise.pcbConnection/1`；正例 `LED1.2→U10.2` exit0 `CONNECTED`、唯一
  `direct-shared-track` `2988899bbc9547de`，反例 `C22.1→C23.2` exit2 `NOT_PROVEN`、`proof=[]`，unknown/errors 均 0，
  与离线 550 一致，`designWrites=0`（权威证据 `evidence/559/native-activation-success.json`）。
  **历史保留**：激活前旧 daemon exit 3、stdout 空、`unknown action`，旧 connector `no handler`；菜单点击只增
  `evaluations` 不改 `bootstrapAt`，必须完整重启。`host-prevalidation.json` 的两条真实对拍仍是**预验**（走已激活 550B
  + 同会话归档身份），与正式激活分开记；范围仍 **direct-only**，多跳铜需另立 `getAdjacentPrimitives` 合同，
  `NOT_PROVEN` 不是开路。558 的三份机器档已由岳签核为 verified；U8 的行内身份与
  EST026 的原始判类没有被伪造（U8 只体现 `pinoutSource: "none"`，EST026 由 558B 精确族词而非补货架转类）；
  机械件退出 hunt 工作清单**不等于**审查通过，它仍留在闸内按 `no-ic-facts` 待人工结案。
- **绘制线资产路由**：先读 `docs/draw-assets.md` 与 `evidence/draw-assets/manifest.json`。
  当前工作集为P125 G3C电路 + P126服务规格与生产 + P118 WiFi锚；548P126**机制通过/页面未通过**；548P127三种分组均证伪；548P128联合座存在但完整未闭环；548P129捕获built=False；548P130捕获path-first首拒；548P131信号有效/标签载体未过；548P132证实预留不一致；548P133重选未过且已回退；548P134定位跨网row-gap误伤；548P135同网过滤**机制通过/页面未通过**；548P136证实BUZZ冲突但offset未解决；548P137**C2最终首拒修复/整图未通过**，真实 `_place` 已5/5；548P138**3V3联合反馈修复/整图未通过**，真实首次plans第二次joint为chain5、expansions6，聚焦77 passed，完整候选首拒前移为C3.2/BUZZ；548P139**规划未实施**。
  P124 GND分组与网格实验是拒绝证据，不是续作基线；仅经明确批准回收12个可再生目录，其他资产未移动或删除。
- **绘制线历史索引 P2–P124（2026-11-14 至 2026-11-16）**：这一段是同一轮绘制线实验/迭代弧，逐批证据在
  `evidence/548P2` … `evidence/548P124`（`-independent` 为独立复验副本），恢复点链与文件清单见
  `tasks/548p140_draw_history_commits.md` §1–§2。除 P2/P6/P14 等少数任务书外，其余批次**没有任务书，
  不伪造 26 份**；查历史按 `evidence/548P*` 与 `PROGRESS.md` 的 2026-11-14/15/16 段。
- **548P140 已由用户落地（2026-11-17）**：历史绘制批次由 `cb44c2e` 一次性提交，`4271fea` 随后做0.6.2发布准备；
  原六批计划不再重复执行。任务书 `tasks/548p140_draw_history_commits.md`。
- **548P141 DSR修复已落地（2026-11-17，`c80eb2c`）**：placement网端点不可平移守卫，基线3红/修复3过、两项变异、聚焦69 passed；
  SHA `752ef006…3f11`。543i后续为CTS脚侧拒绝，J/O/K/L/cross-side/forced/P16等独立处理。任务书 `tasks/548p141_net_endpoint_repair.md`。
- **548P142/P143 机制通过、未提交（2026-11-17）**：detour+foreign联合首拒前移为C1.2；多成员网端点不可裁决使完整543i恢复9 passed。
  P142回归3 passed，P143/P141合计18 passed；drawcompiler `87f82009…cd5473`，placement `0674eb38…96bb82`。
- **548P144 固定glyph场景通过、未提交（2026-11-17）**：固定terminal glyph纳入port-columns的scene，C1.2消失；
  新测试3 passed、两项变异、P43/WiFi geometry不变。drawcompiler `976a4c2c…b2ea`。
- **548P145 规划（2026-11-17）**：U1.18 local-label exception与LED2_K/LCD_SCK回放冲突，见 `tasks/548p145_u18_label_replay.md`。
- **绘制线 2026-11-14 四批（工作树未提交；全量 2 红均既有）**：
  - **548K / 548K-R**：名字桩带先于旗位预留，显式开关 `labelPolicy.stubLaneReserve`（默认关闭、`false` 等价不写、
    只在 true 时序列化、非布尔具名拒绝）。不开开关的校准件几何 `f4f1c58c…` 与 548J 记录逐字相同且 `plan` 拒绝；
    开开关后 `plan ok=True`（6 件/17 线/7 旗）。
  - **548L**：两脚 `style=wire` 网的直线走廊也在旗位之前预留（同一开关门控），`ESP_EN`/`ESP_RST` 变回导线、
    `wired route not found` 三处归零。
  - **548M / 548M2**：新增 `railClustering: {"radius": N}`，把 053E 的 GND 聚簇能力开到 power（声明时该网取
    `wire` 样式；053 sec.7 默认裁决未动；`gndClustering` 语义未动）。`3V3` 旗 6→3、GND 旗 1→2、
    y=795 底边 rail 消失、`crossings=0`、默认页 `8802d317cfae…` 仅指纹（不作验收；见 `docs/draw.md` §Baseline）。
  - **548N / 548N2**：548N 在独立 worktree `E:\boardwise-wt-548n`（分支 `drawing-548n`）试组级座位**未达成、
    净改动为零**（前提被证伪：`IO0` 在左侧 → 应为两组；且与 `test_548j_joint_seats.py:692` 跨侧负例互斥）；
    548N2 修好"组座位不避让已预留开放端口房间"这一真缺陷并**已并入主仓**，只对声明 `serviceGroups` 的页生效。
    **三组真实页仍 `ok=False`**（新一层：宿主 GND 挂旗带与 PWR rail 争地），按停止线停手。
  - 最终生产：`drawcompiler=05139E85…5EA3E`、`presentationspec=F63B89AC…0BA60`；完整 pytest
    **2 failed / 11070 passed / 22 skipped / 1 xfailed**（两条红既有：panel 路由次数、193 Windows 环境）；
    connector 740、dsh-plugin 137/1、Rust 全过。**不称全绿。**
  - 视觉：旗域已按岳 P44 判据同形，**仍未过视觉闸**（`ESP_RST` 绕行）；逐项差距
    `evidence/548M/p44-comparison.md`。派单账 `tasks/draw-line.md`。
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
  **548J（2026-11-13，A合同通过；B1停止、视觉未过）**：`serviceGroups`公开合同/负例/页面切片与两项
  独立变异完成；岳人工P44及ESP-01S双列校准证据可复用。B1目标测试22 passed、交接组合233 passed/1 skipped，
  但当前合成图仍有CFG_A/PWR大回环，主代理视觉拒收；直接令row_y=min(feet)（不扣body/GAP）等实验已回退，真实WiFi未消费，
  B1真机/独立变异/全量四线未做。当前 `drawcompiler=11b2b3b9…`（B1前058a3032…），工作树混合未提交，
  不得git restore或直接续写独立builder。P44人工页/P42/P43/Board2不动，P45空白，daemon已停。
  **权威交接 `evidence/548J/HANDOFF.md`**，任务书 `tasks/548j_pullup_joint_seats.md`；清理或重设计由岳另裁。
  **548D3D-H3–H6/P1 → T1 → F1A → P43（2026-11-13，单岛与三岛闭环，整页仍 BLOCKED）**：
  H3–H6 统一宿主脚绑定、本件文字逃逸、旗位方向与相邻脚独立备选；P1 宿主端口列只在
  `localSeats:true` + `stubMin>0` + 无 `panelGroups` 时启用；T1 强制 topology 三岛 port-native
  （coreless 投影、同网重旗预占）机器与主代理视觉通过，主代理 **79 聚焦全绿**、CH34/seat-first 邻域
  **171 passed**，有效变异 3 failed / 1 failed 先红后 cp+SHA-256 恢复（「删普通信号墙」为**无效变异**，
  不记成功）；F1A 同模块独立分压链族按「信号顶端 + `serviceLayout` + `stubMin>0`」启用（native-attr
  全局门已撤，实测它让 bmp280/wifi 失候选），LED 岛 236×216.5、6/6、**14 测试 + 333/2 邻域**，
  变异 7/7 与 2/12 先红恢复。**P43 automatic 真实 64 脚 MCU 已落 test V4 Board1 `797f20b8a217b331`**：
  三件/19 wire/11 flag、39 写调用、`verify live ok · canvas ok`、独立逐脚 **20/20 + 48/48 NC**、
  `draw lint` **0/0/0**、显式 save 但只记 **`saved_unverified`**；**DRC 开放项照记**（209 WARN/0 ERROR，
  含 6 SHOWDANDLING、3 CHECKFLOATPIN、1 跨页 ATTRMATCHCODE，新增 NRST WARN）；P42 不动。
  B1前历史基线 `drawcompiler=058a3032…`、`drawapply=f713895f…`、`placement=326d96e9…`、
  `voltage_divider=2f67af65…`。**真实整页仍 BLOCKED**：10/10 岛可编译，页级 packer 两次真实调用
  均 unsat，三列差 **41.5**；buzzer 独立岛、`partTexts`、`panelGroups` WiFi 上拉、native-attr 门、
  packer/页框/gap 调参**全部实测排除**；该方向随后进入548J，当前停止状态见上条交接。
  最终全量 **10973 passed / 26 skipped / 1 xfailed / 1 failed /
  1 warning**（唯一红仍为既有 panel 路由次数，无新增失败，不称全绿）；Connector 740、DSH 137/1、Rust 177/4 均通过。
  日志 `evidence/548D/host-binding/full-pytest-final.log`、`connector-final.log`、`dsh-final.log`、`rust-final.log`。
  证据 `evidence/548D/host-binding/p43/ACCEPTANCE.md`、
  `host-binding/three-island/implementation/ACCEPTANCE.md`、`full-page/BLOCKED.md`、
  `full-page/divider-families/README.md`、`full-page/island-packing-review.md`、
  `host-binding/full-pytest-t1.log`，任务书 §44。**不得写成 548D 自动整页或 548E 完成；547G 仍独立暂停。**
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
| 541 | **审查分阶段交付与可中断流程**：initial/partial 检查点、冻结输入、同基准复读、中止只读已有产物出 partial；运行时闸 R1 RunManifest、R2 `--strict` 重算 guard、R4 `--strict-partial`（显式 opt-in）；R3/I/R4 见下 | 纪律层及 R1/R2/R4 strict 已随 `cdff88b` 落地；R3/I/R4 工作树实现，隔离真实 DSH 已验，桌面未部署 | docs/review-sop.md §3.0a；tasks/review-stage-runtime-gates.md；tasks/541_offline_runtime_gates.md；tests/test_review_stage_delivery.py、test_541_run_manifest.py、test_541_strict_reuse.py、test_541_partial_categories.py |
| 541R3 | **DSH 检查点与预算 pre-execute**：显式 out、receipt+callId+stage 配对、跨目录欠账拒绝、30 分钟/60 model steps；新收据开新预算段，read/finalize/doctor 可收尾且不取消已派发命令 | **工作树实现与隔离实载（2026-11-16）**：DSH 169 passed/1 skipped；文件收据不解锁、initial/partial 解锁、跨目录欠账均实跑；桌面 profile 未部署 | tasks/541r3_dsh_stage_gate.md；dsh-plugin/src/review-stage-gate.ts；dsh-plugin/tests/review-stage-gate.spec.ts；.tmp_541_live/session-4-events.jsonl |
| 541I | **公开接口 allowlist 与 tool-gap**：受管工具固定 argv、review_read 六 section enum；bridge 复用 protocol 唯一目录的 `--read-only`，非 read/未知动作在 daemon 前拒绝并附 tool-gap，不复制第二份动作名单 | **工作树实现与独立复核完成**：Python 目录闸 36 passed；DSH 联合 169/1；真实 DSH tool-gap + READ_ONLY_VIOLATION 已验；任意宿主 Read/Grep/Bash 私有解析仍不覆盖，桌面未部署 | tasks/541i_public_interface_allowlist.md；dsh-plugin/src/shared-tools.ts；dsh-plugin/tests/tools.spec.ts；.tmp_541_live/session-3-events.jsonl |
| 541R4 | **DSH error `tool/result` 记账**：真实 DSH 对被 pre-execute 拒绝的调用也写 error result；只清 pending 并推进 step，不增加 diveCount/检查点，exit 1/3 正常返回与缺 isError 旧日志不变 | **工作树实现与隔离实载（2026-11-16）**：主代理变异 3 failed/22 passed 后恢复 25 passed；同一 Session 拒绝文案由错误的 2 修为 1，initial/partial 均放行；桌面未部署 | tasks/541r4_dsh_error_result_fold.md；dsh-plugin/src/review-stage-gate.ts；tests/review-stage-gate.spec.ts；.tmp_541r4/；.tmp_541_live/session-4-events.jsonl |
| 087E | **#87⑤ `sch.readback` 可选 value/MPN**：`OtherProperty.Value` 与 ManufacturerId 优先/OtherProperty 回退，附 valueSource/mpnSource；空白为 null、getter 失败计 unreadable，pcb 行和 fields 折叠不变；旧 connector 缺键仍走归档 | **已落 `3d4a0d5`（origin/main）；test V4 在线验收完成（2026-11-16），未发布**：主代理 node 22、Python 41+13+60、connector 809；两类变异先红后恢复；P43 三器件 readback 与公开 ATTR 双源一致，11 netflag 为 null；V3/CBB/多板未覆盖 | tasks/087e_readback_value_mpn.md；connector/src/actions.ts；connector/tests/readback-component-value.test.mjs；.tmp_087f3/p43-readback-new.json；.tmp_087f3/p43-document-source-new.json |
| 087F1/F2 | **#87② PCB viewport 与证据能力闸**：确证 PCB 后 activate/re-read + zoom + viewport PNG，channel/evidenceGrade 明示；`capabilities.pcbRenderViewport` 让旧 connector 零 render，新能力才接 liveevidence；document render 不冒充 viewport | **已落 `3d4a0d5`（origin/main）；PCB viewport 在线验收完成（2026-11-16），未发布**：F1 74、F2 Python 242、connector 809；独立变异均先红后恢复；直接 render 两板目检、SVG 拒绝，review-evidence exit0/capture.ok=true/pcbImage ok 三板/livePcb ok/焦点恢复；V3/生产非空板未覆盖 | tasks/087f_pcb_render.md；tasks/087f1_pcb_viewport_render.md；tasks/087f2_pcb_evidence_integration.md；tasks/087f3_pcb_visual_docs_live.md；outputs/review/087f3/ |
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
| 550B | **在线只读 PCB 实例探针**：`sys.probe.instances` 封闭调用 connected/entireTrack/adjacent；精确 PCB 页守卫、只回 ID；基类 pad 缺方法时有界 ComponentPad 回退 | **已本地提交 `9f73ede`，未推送；EDA 4.1.100 真机验收完成（2026-11-18）**：line/arc/via 方法实测可用，includeVias 差分成立；ComponentPad 回退 55 组件唯一匹配、零读错误，true/false 各 2 条走线。Connector 全量 846 passed + typecheck，Python 合同/政策 113 passed；主代理变异先红后恢复。V3 未验，不宣称 live net-path，未推送、未发布 | tasks/550b_live_primitive_probe.md；connector/src/actions.ts；connector/tests/pcb-instance-probe.test.mjs；.tmp_550_live/ |
| 552 | **多单元器件身份与真实网表**：按 `PIN.partId` 拆单元；同板同位号仅在相同非空 Unique ID/Device 且不同 partId 时合并，冲突与复制件保留重号 | **已本地提交 `14e8f39`，未推送**：既有归档四个双单元器件不再误报；宿主网表 4 件 / 32 脚成员集合全对拍通过；17 条专项含 NC/真重号负对照，主代理变异先红后恢复。DSH 实际 CLI 同档复跑 0 ERROR、0 位号 finding。未跑全量 | tasks/552_multi_unit_designators.md；tests/test_552_multi_unit_designators.py；evidence/552/ |
| 553 | **跨板共用位号不再报 ERROR**：保留跨板事实与项目级歧义，只取消缺陷判决；同板同页/跨页重号不变 | **已本地提交 `14e8f39`，未推送**：双板 18 个跨板名由 18 ERROR 降为 0，同板负对照仍 ERROR；7 条专项，主代理变异先红后恢复。未跑全量 | tasks/553_cross_board_designators.md；tests/test_553_cross_board_designators.py；evidence/553/ |
| 554 | **552/553 派生基线与差分合同集成**：签名评审集不改，报告/041/规则指纹按真实语义同步 | **已本地提交 `14e8f39`，未推送**：A 域 80 passed、B 域 188 passed；最终综合 552 passed，另有 127 项合同/卫生通过；差分 `cases.json` 不变。综合命令另暴露 4 条绘制线 CLI 合同漂移，layer 另有 1 条既有跨层红，均未越线处理；不称全量全绿 | tasks/554_designator_integration.md；evidence/554/；contracts/differential/ |
| 555 | **批量手册链 live/DSH 集成**：`parts hunt --live`、按 checkup `needs_datasheet` 精确过滤、跨板同位号按真实身份寻址、候选 sidecar 身份后缀、DSH `boardwise_parts_hunt` | **已本地提交 `14e8f39`，未推送；真实试点完成**：18 个身份行；4 份 claims 过生产闸、0 拒绝，其中 3 颗转为机器核验待签核，另 1 颗原已 verified。真缺资料桶 20→17，机器待签 0→3；needs_datasheet 仍 15、verdict 仍 incomplete，不宣称全部清闸。Python 218 passed、DSH 207/1、真实适配层零外呼冒烟通过；无全局货架/真实设计写入。U8 身份、EST026 图像文字层、4 个机械件与部分连接器仍需人工；CLI 合同快照已由 556 生成同步，559 新增命令的合同由 560 再核 | tasks/555_datasheet_hunt_integration.md；evidence/555/；tests/test_555_parts_hunt_live.py；dsh-plugin/src/parts-hunt.ts |
| 556 | **CLI 合同与 `_page_y` 跨层集成**：`parsers.schematic.page_y` 公有化（保留 `_page_y` 兼容别名），`engines/v4facts.py` 只消费公有入口；`tools/cli_contract.py --write` 从真实 parser 一次生成，把 hunt/draw/bridge 三类既有漂移同批收口 | **已本地提交 `0ac8973`，未推送**：父验两次独立变异先红后 cp+SHA 恢复——v4facts 回退私有 `_page_y` → 1 failed/8 passed，去掉 `page_y` 负号 → 4 failed/37 passed；恢复后 50 passed in 15.23s。540c/layer/owner/v4_facts/agentadjusted 聚焦绿 | tasks/556_shared_cli_layer_integration.md；evidence/556/；.tmp_556/ |
| 557 | **审查线台账提交状态校正**：550B/552–555/087E-F 的“工作树未提交”改按真实归属；handoff 顶部加当前路由 | **已本地提交 `0ac8973`，未推送**：只改文档；文档/工作区测试 67 passed（557 读数）。558 开始时那两条 `owner` 红来自他批新增 `core/connection.py` 未登记 157→159，与本批无关，559 已同步 | tasks/557_review_ledger_status.md |
| 558 | **手册异常件义务分类**：四类义务（ic-facts/connector-pinout/identity-unresolved/no-ic-facts）+ 机械件三通道 `ok:null/applicable:false` + 连接器 `pinout/引脚定义/脚位图`；机械件退出 hunt 但仍留闸 | **已本地提交 `0ac8973`，未推送**：真实重算 unreviewed **23→23**、needs_datasheet **15→11**、机器待签 3 与 `verdict=incomplete` 不变；父验 135 passed、变异 A 4 红 / B 2 红，恢复 SHA `2e2b228f…`。EST026 三行本批仍 ic-facts（`partkind` 禁触），交 558B。三份机器档已由岳签核为 verified | tasks/558_datasheet_obligations.md；evidence/558/ |
| 558B | **EST026 精确族词判型**：`partkind` 精确族词后 EST026 三行转 `connector-pinout`；机械 marked seed 仍收集、过滤下沉到 facts 触发循环 | **已本地提交 `0ac8973`，未推送**：父移除该族词 → **3 failed**，cp+SHA 恢复后 EST026 三行回到 connector-pinout；聚焦 5 文件 135 passed、修复后子集复跑 109 passed、真实重算 needs 15→11 不变 | tasks/558b_est026_part_kind.md；evidence/558/558b-marked-seed-fix.md |
| 559 | **在线 PCB 连通证据（550B → typed tool）**：纯函数 `core.connection.project_connection`（`boardwise.pcbConnection/1`，无 path/hop）+ `pcb connection` CLI + connector `pcb.connection_probe` 只读 action | **已本地提交 `0ac8973`，未推送**：父验 268 Python + 43 Node/typecheck 全绿、两有效变异先红后 cp+SHA 恢复（类型闸 2 红、缺口闸 9 红）；真实**预验**用已激活 550B + 同会话归档身份，正反 verdict 与离线 550 一致（CONNECTED / NOT_PROVEN），但原生 action 在旧 daemon 上报 `unknown action 'pcb.connection_probe'`、exit 3、stdout 空——**当时未热更、未部署**（历史保留）。**2026-11-20 原生激活已成立**：daemon 重启 + connector 写入 + 用户完整重启 EDA 后，新实例 `inst-015644463-2wuenu0j` 正例 CONNECTED（唯一 `direct-shared-track` `2988899bbc9547de`）/ 反例 NOT_PROVEN，unknown/errors 0，与离线 550 一致，`designWrites=0`；证据 `evidence/559/native-activation-success.json`，预验与正式激活分记 | tasks/559_live_pcb_connection.md；evidence/559/ |
| 559B | **在线连通收窄为 direct-only（实测否决 entireTrack）**：真实板上 6 个离线分离铜分量的网，`getEntireTrack(true)` 返回 76 ID 且 truncated，含其他分量 4 ID ⇒ 成员资格不能证明连通。删除两类 track 正证据与 connector 的 entireTrack 调用/`tracks[]`/总 ID 预算/`coverage.ids`；legacy 非空 `tracks[]` 只记 `entire-track-unsupported` 并压否定；`NOT_PROVEN` 语义重定为「direct 范围内无共享图元」 | **已本地提交 `0ac8973`，未推送**：保留 P2 三项披露修复（direct-non-proof-type / refusal 文案 / versions.missing·error）；新反例「from direct=t1、to direct=t2、from.tracks 含 t2」不得 CONNECTED，Connector happy path 断言 entireTrack 调用为零；`contracts/cli/v1.json` 官方重生成。真实预验仍为**预验**；原生 action 激活已于 2026-11-20 另行成立（见 559 行），本行不改 direct-only 范围 | tasks/559b_direct_only_connection.md；evidence/559/entire-track-rejection.json |
| 560 | **目标 1/2/4/5 总集成与文档收尾**：#87 改已落 `3d4a0d5`、550B/555 行尾与 direct/last-dot 说明校正、556–560 实况入账 | **已本地提交 `0ac8973`，未推送**：第三轮全量 **11 failed / 11921 passed / 26 skipped / 2 xfailed in 2593.86s**——二轮 9 处审查/shared 红（537A/540/038）已消失，剩余 11 处全为绘制线（116/548m/543h2/548c7×4/548d_wifi_ground/543h3b/draw_plain_carrier/548k）按绘制线归属披露，**不写全仓全绿、无第四次全量计划**；connector 864、DSH 207/1、Rust 177/4 ignored 为各线读数，合同父变异 2/4/3 红后 cp 恢复 119 passed。本轮不推送、不部署 DSH、不发布；native `pcb.connection_probe` 激活已于 2026-11-20 另行成立（`evidence/559/native-activation-success.json`），三份机器档已由岳签核为 verified | tasks/560_goal_integration.md；evidence/560/ |
| 561 | **DSH `boardwise_pcb_connection`**：parts hunt 后、draw 前注册第 14 个工具；只构造 `pcb connection` argv 并复用文本 transport，不重判 direct/verdict | **已随 `0b21342` 推送**：DSH **218 passed / 1 skipped** + typecheck/build，文档/同步 **58 passed**；父变异撤注册 13 failed/12 passed、argv 换端 4 failed/7 passed，均 cp+SHA 恢复并复绿。未部署/pack/发布；多跳合同另立 562 | tasks/561_dsh_pcb_connection.md；evidence/561/ |
| 562 | **在线多跳 PCB 铜路径**：独立 `pcb.path_probe` / `pcb path` / `boardwise.pcbLivePath/1`；Connector 收集证据、Python BFS；双向邻接 proof、固定预算、entireTrack 禁用 | **562A–D 工作树完成、未提交未推送；DSH 不做**：主代理 52/376/85 passed、Connector 876 passed；真机 direct/多 Line+Via CONNECTED、分离负例 NOT_PROVEN、Pad↔Via INDETERMINATE，内部图元与离线一致；20 组跨层直接边=0，Arc 未启用。最终 Python 35 failed/11997 passed/26 skipped/2 xfailed/3 errors，差分仅移除 shared owner 计数红，其他归绘制线；DSH 218/1、Rust 177/4 ignored | tasks/562_live_pcb_path_graph.md；tasks/562a_connector_path_probe.md；tasks/562b1_live_path_projection.md；tasks/562b2_live_path_cli.md；tasks/562c_live_path_live_acceptance.md；tasks/562d_live_path_hole_fixes.md；evidence/562a/、562b1/、562b2/、562c/、562d/ |
| V4 | **立创 EDA Pro 4.x 适配**：归档与 `.eprj3` 单 PCB 审查、在线容器/page、主机 ERC 与证据边界 | **首批已随 `e431e94` 落入 0.6.0**；**归档多 PCB 逐板已随 `a4fc387` 提交（038P）**；多板 + 库文档同名、真实 NC、缺省 `yAxisDirection`、部分跨视图语义、实时 PCB 位图与后续真样本仍开放。**边界口径见 `docs/v3-v4-boundary.md`** | tasks/038-eprj3-tierA.md；tasks/038_v4_live_gaps.md；tests/test_038p_eprj3_multi_pcb.py；docs/v3-v4-boundary.md |
| 038R | **V4 审查线差分调研**：容器/在线通道与 P0–P2 顺序、共享模型边界 | 调研完成，首批已实施 | tasks/038_v4_review_line_research.md；outputs/review/v4-review-line-research.md |
| 038S | **真实 eprj3 样本只读差分**：证实原理图一致与 PCB builder 复用，发现 EOF、覆盖、版本与 POUR/POURED 单位差 | 样本调研完成，首批适配已实施；POURED 1:10 与旋转矩形已由 038K 关闭，归档多 PCB 已由 038P 关闭并于 `a4fc387` 提交；真实 NC、缺省 yAxisDirection 与 eprj3 在线容器仍开放 | tasks/038_v4_sample_research.md；outputs/review/v4-review-line-research.md §6；.tmp_v4_sample_20261031/REPORT.md |
| 038F | **V3/V4 容器隔离与单 PCB Tier-B**：F1 EOF、F2 版本、F3 覆盖、F4 source、F5 CLI/checkup；共享规则/报告 | **已随 `e431e94` 落入候选**；**归档多 PCB 逐板已由 038P 关闭并随 `a4fc387` 提交（`test V4` 两空板对账，真实多板 + 库工程未实测到非空板）**；单模型 `review --view pcb` 多板仍拒绝，真实 NC 与 eprj3 在线容器未关闭，POURED 单位与旋转矩形不再列为开放项 | tasks/038_v4_isolation_plan.md；outputs/review/v4-eof-frame.md；v4-eprj3-version.md；v4-eprj3-pcb-coverage.md；v4-eprj3-pcb-source.md；v4-eprj3-tierb.md；tests/test_038p_eprj3_multi_pcb.py |
| 038O | **V4.1.93 在线只读验收与 O1–O3 修复**：doctor 9/9、page 采集、PCB render 不适用、逐条 ERC 与证据缺口披露 | **已随 `e431e94`/`643cf6d` 落入候选**；板级仍 incomplete，多 PCB/全格式语义未关闭 | tasks/038_v4_online_acceptance.md；tasks/038_v4_live_gaps.md；outputs/review/v4-online-acceptance.md；outputs/review/v4-live-gaps-acceptance.md |
| 038G | **Short-Symbol 网表语义**：跳线不再产生假 `Symbol` 网，按页并网；冗余跳线不再翻转普通簇的显式标签/电源旗标优先级 | 已落 `466ca6e`，冗余守卫随 `d542f14` 收口；合成回归含跨页隔离、悬空脚与命名优先级 | tests/test_038g_short_symbol.py；tests/test_040_page_scope.py |
| 038G2 | **Short-Symbol 显式标签别名闭包**：短接主名不再吞掉另一侧 NET 别名；同名孤岛按闭包归并，forced 优先且定序，board 边界不变 | **已落 `6b82189`（2026-11-15，离线 + test V4 在线验收完成）**：四个离线样本共 30 个受影响脚与归档 PAD_NET 一致；test V4 P45 宿主与离线均把 R901.1/R902.1 归入 PHASE、无 SENSE 网；最终扩大聚焦 396 passed；此前全量 11232 passed / 26 skipped / 3 xfailed / 3 failed（三红均为既有绘制线 548D/K/P）；Connector 774、DSH 137/1、Rust 177/4；R23 脚号、V3、多板与 CBB 内部展开未覆盖 | tasks/038g2_short_symbol_aliases.md；src/boardwise/parsers/schematic.py；tests/test_038g_short_symbol.py、test_040_page_scope.py、test_040b_boards.py、test_041_cross_board_nets.py、test_041s2_interconnect.py、test_105_b4b_designator_membership.py、test_527c2_cross_view_geometry.py |
| 038J | **V4 分歧库副本诊断**：SYMBOL/DEVICE 同 UUID 的模型可见定义不同才计数，纯元素重编号不误报；first-wins 不变，冲突进入 console/md 与 coverage 闸 | 已落 `d542f14`；相同复制 0、真实冲突逐份计数，`coverage.recordsDropped` 含第四项 | tests/test_038_eprj3.py；tests/test_020_parse_drops.py；tests/test_072_coverage_gate.py |
| 038K | **旋转矩形与 POURED 几何**：R 路径按存储 `(x,y)` pivot、声明角度 CCW 读取；空 POURED supersession 语义不变 | 已落 `d542f14`；54 父区域/1843 点 containment 全过，PGND 铜岛 30→12 有元素与面积证据；旋转圆角和 BOARD_OUTLINE 不扩支持 | tests/test_038k_rotated_rectangles.py；tests/test_135_poured_result.py；tests/test_131f_mcu_crystal_keepout.py |
| 038L | **Rust SYMBOL 垂直迁移**：V3 zIndex/V4 pin_id、两阶段 ATTR、重复脚号逐字段合并、重编号不参与冲突判断 | 已落 `d542f14`；Python/Rust 9-case 差分一致，工作区 74 passed/4 ignored | rust/crates/boardwise-core/src/symbol.rs；tests/test_038l_symbol_differential.py；docs/rust-platform.md |
| 038M | **Rust DEVICE 垂直迁移**：`device-library-sample` 成为第 8 个 kind，首 `META`、重复 uuid first-wins、模型可见差异才计冲突 | 已落 `a4fc387`；case book 9→11，Python/Rust 投影一致，旧 9 case 不变；**属性浮点溢出的文本差分已修**（与 Python 对齐 `inf`/`-inf`，`json.dumps` 的 `NaN`/`Infinity` 拼写保留、有限值不变） | rust/crates/boardwise-core/src/device.rs；tests/test_038m_device_differential.py；docs/rust-platform.md |
| 038N | **Rust FOOTPRINT 库垂直迁移**：`footprint-library-sample` 成为第 9 个 kind，首 `META` 生效、重复 uuid first-wins（空标题占位）、字面 `"null"` 标题保留；输出只有 `schema`+`footprints`，无 stats、无冲突计数 | 已落 `a4fc387`；case book 11→13，Python/Rust 投影一致，旧 11 input 不变 | rust/crates/boardwise-core/src/footprint.rs；tests/test_038n_footprint_differential.py；docs/rust-platform.md |
| 038P | **eprj3 多 PCB 逐板审查**：同一 `source`/`runner` 逐板出 `boards`（title/boardUuid/components/checksRun/findings），`checkup --file` 逐板落地；`_load_model(view=pcb)` 多板**列出板名后拒绝**并指向 `checkup`，单板历史形状不变；**合流守卫见 038P1**（重复板拒绝、分歧库拒绝、相同副本允许、无 uuid 板按 stem 命名） | 已落 `a4fc387`；`test V4` 两个空 PCB 在线/离线 `boards`、32 checks、40 findings 一致；**真实多板 + 库工程未实测到非空板**（守卫只有合成证据）；`review --view pcb` 多板仍拒绝 | tests/test_038p_eprj3_multi_pcb.py；src/boardwise/parsers/eprj3.py；src/boardwise/engines/pcbreview.py；docs/v3-v4-boundary.md |
| 038P1 | **多文件合流的三处说谎面**：① 无 `DOCHEAD.uuid` 的板按文件 stem 命名（`pcbTitles` 改为按 PCB 文档顺序的列表，不做 uuid 查表）；② 两份文件同一个 PCB 文档 uuid **明确拒绝**（同一块板导出两次不审两遍、不按标题聚合、不静默去重）；③ `FOOTPRINT`/`DEVICE`/`SYMBOL` 同 uuid 只有**记录序列签名相同**（保留顺序/id/body，仅剔 `DOCHEAD` 的 editVersion/updateTime/version/client/user）才允许合流，**分歧拒绝**、不串板 | 已落 `a4fc387`；单文件旧行为不变，旧差分 case 与两空板读数不变；**合成样本证据**，真实多板 + 库工程未实测到非空板 | tests/test_038p1_eprj3_multi_guards.py；src/boardwise/parsers/eprj3.py；docs/v3-v4-boundary.md；本地探针 `.tmp_joint_audit/`（ignored，非已提交产物） |
| 038T | **Rust 声明解析投影垂直迁移**：`footprint-declared-sample` 成为第 10 个 kind，输入 `text`+`value` 走同一对 Python 阅读器（`_collect_footprint_titles` → `_resolve_declared_footprint`），只回答原理图 `Footprint` 字段声明了什么；输出 `schema`+`footprint`+`libraryId`，三个分支不单独出字段 | 已落 `a4fc387`；case book 13→15，Python/Rust 15/15 一致，旧 13 input 不变 | rust/crates/boardwise-core/src/footprint.rs；tests/test_038t_footprint_declared.py；docs/rust-platform.md |
| 038W | **`PAD_NET` 增量日志的每脚判优**：PCB 每脚投影键只有 `(component, pin)`，旧实现用 `setdefault` 让文件靠前的旧网获胜；改为复用 038U 原子视图的同一 ticket/client 判优，不复制第二套比较规则 | 工作树（2026-11-06 完成，未提交）；最终全量在途 | tasks/038w_pad_net_journal.md；tests/test_038w_pad_net_journal.py |
| 038X | **默认货架路径与缺失披露**：非 frozen 的默认读写改用 `resources.parts_library()` 绝对路径，只读入口不再把「文件不存在」静默读成「货架为空」；`load_parts` 的「缺文件可建空架」合同不变 | 工作树（2026-11-06 完成，未提交）；最终全量在途 | tasks/038x_shelf_resolution.md；tests/test_038x_shelf_resolution.py |
| 038Y | **PCB 几何三规则 + 只读 `pcb gate`**：`pcb-pad-overlap`（异器件焊盘共享铜层正面积相交，同网不豁免）、`pcb-silk-on-foreign-pad`、`pcb-silk-under-body` 分别复用 038Y1 铜面、038Y3A 墨迹×铜面及现有文字/真实本体几何，不再以外接框作最终判定；`boardwise pcb gate --out <新目录>` 只读编排活动 PCB 身份 → 一次严格宿主 DRC → 新鲜 checkup → verdict（0/2/3，incomplete 不绿、无 `--skip-checkup`、无 autofix/保存） | **Y1–Y5 已落 `d422e7a`**：联合生产 **1505 passed / 2 skipped**；两条既有归档 4 板实跑 WARN=0、近似 INFO 4（不是所有板干净）；038Y5L/M/N 已完成活动页拒绝、PCB1/2 DRC RED、第三板 DRC=0 后真实 checkup（工程 INCOMPLETE）；V3 与天然 GREEN 仍未覆盖；038Y6 silk autofix **暂缓** | tasks/038y1_pad_copper_overlap.md；tasks/038y2_pad_overlap_rule.md；tasks/038y3a_pad_ink_overlap.md；tasks/038y3b_silk_on_foreign_pad.md；tasks/038y4_silk_under_body.md；tasks/038y5_pcb_gate.md；tasks/038y5l_pcb_gate_live.md；tasks/038y5m_pcb_gate_checkup_live.md；tasks/038y5n_pcb_gate_third_live.md；tasks/038y6_silk_autofix.md |
| 038Y5L | **`pcb gate` 在线只读验收**：test V4 活动 P45 时 exit 3、零 DRC/checkup；PCB1 严格 DRC `checked=true / errors=1 / truncated=false` 得 exit 2 RED 并按合同不跑 checkup；旧目录复用 exit 3，焦点恢复 P45 | **已完成本轮真实路径（2026-11-15）**；未写设计、未改生产代码。DRC 清洁后的在线 checkup 已由 038Y5N 补齐；V3 与天然 GREEN 未覆盖，不为凑路径制造缺陷 | tasks/038y5l_pcb_gate_live.md；outputs/review/038y5l/ |
| 038Y5M | **PCB2 在线 gate**：test V4 PCB2 严格 DRC `checked=true / errors=1 / items=1 / truncated=false`，exit 2 RED、checkup 未运行；恢复 P43 | **已完成本轮真实路径（2026-11-16）**；没有为跑 checkup 换真实工程或制造清洁板 | tasks/038y5m_pcb_gate_checkup_live.md；outputs/review/038y5m/ |
| 038Y5N | **第三板 DRC 清洁后的真实 checkup**：test V4 第三板严格 DRC `errors=0 / items=0 / truncated=false`，新鲜 checkup 真跑 exit 1；因工程 26 ERROR、缺手册/分诊与 boardsEmpty，gate INCOMPLETE / exit 3 | **已完成 DRC 清洁后的在线编排（2026-11-16）**；不是 GREEN。天然 GREEN 不再本机必做，V3 宿主验收等待外部反馈 | tasks/038y5n_pcb_gate_third_live.md；outputs/review/038y5n/ |
| 038Y5O | **V3 `test` 在线 gate**：宿主实测仍为 4.1.100，PCB1/2 各严格 DRC errors=1 / items=1 / truncated=false，gate RED / exit 2，checkup 均未运行；Start Page 已恢复 | **只完成 `.eprj2` 路径验证（2026-11-16）**；不是 3.2.x 宿主验收，也没有 GREEN。天然 GREEN 不再本机必做，V3 宿主验收等待外部反馈 | tasks/038y5o_v3_gate_live.md；outputs/review/038y5o/ |
| 038Z1 | **test V4 真实三板归档在线/离线差分**：两次 117295 B 导出哈希不同，只做语义对拍；两侧 exit 1、57 条自有 findings 一致；三板各 35 checks、findings 20/20/9，title/uuid/components/copperLayers/crossView 全一致 | **已完成真实骨架范围（2026-11-15）**：PCB1/2/晶振全 0 器件、铜层 2/0/0；不是非空多板，也不是同字节对拍。真实多文件守卫、真实 NC、缺省 yAxisDirection 仍待样本 | tasks/038z1_v4_live_archive_differential.md；outputs/review/038z1/differential.json；docs/v3-v4-boundary.md |
| 038Z2 | **真实 eprj3 多文件与 4.1.100 在线/离线差分**：3 个 `.epcb2`、7 个 `.esch2` 合流；三板字段一致，60 条 findings 多重集一致，archivePcb ok/errors 一致 | **已完成真实多文件正路径（2026-11-16）**：无库副本，三种 guard 未在真实文件上触发；17 个合成测试仅补充，不冒充真实负例 | tasks/038z2_v4_folder_live.md；outputs/review/038z2/differential.json；tests/test_038p1_eprj3_multi_guards.py |
| 038Z3 | **真实 NC 与 yAxisDirection 样本核查**：2603 条标记全为 up；NO_CONNECT=0；SCH_PAGE 本体内缺省标记的坐标记录=0 | **样本不存在，保持未覆盖**：未修改工程制造 NC 或缺省坐标，未用其它工程替代 | tasks/038z3_nc_yaxis_live.md；outputs/review/038z3/record-scan.json |
| 038Z4 | **真实非空多板判据核查**：三块 PCB components 全为 0、copperLayers 为 2/0/0；原理图器件数不冒充 PCB 已放置器件 | **非空多板仍未覆盖**：没有 `components>0 && copperLayers>0` 样本，未放置器件或借真实工程补样本 | tasks/038z4_nonempty_multiboard_live.md；outputs/review/038z4/board-scan.json |
| 038Q | **原生 CBB 与复用模块准备**：Q1 库只读搜索/身份，Q2 上游候选归一化，Q3 符号文件只读通路，Q4 单符号 elibz2 profile，Q5 AMS 三电容，Q6 封装文件与 PAD，Q7 SY8089 双身份/profile，Q8 受管 symbol book，Q9 剩余身份集中采集，Q10 真实 symbolRef，Q11/Q13 离线试点，Q12 CH340 显式电气脚位，Q14 原生块只读取档，Q15 库路径幻影放置，Q16 项目内真实放置，Q17 块实例只读识别，Q18 块端口 unproven 与 N1–N3；原生 `block_symbol` 首轮垂直链已验证 | **Q1–Q10、Q12 已完成各自范围；Q11/Q13 及 Q11A/Q13A 的 CBB 绘制相关工作全部搁置（岳 2026-11-12 裁）**。已有离线试点与视觉拒证据保留，不再推进内部网语义命名、多脚ESD/短载体或旗标，不 plan/apply。19 身份已齐，SY8089/CH340 已 bound；CH340 五组通配显式落成12脚、U.7 唯一 NC；EP 厂家依据未关闭，book/模块仍 candidate/notForDrawCompile；提交前四项挖洞已修，完整 Python 10873 passed / 26 skipped / 1 xfailed，Connector 691、DSH 137/1、Rust 177/4。**Q14–Q18 在工作树：真实 block_symbol 的放置、回读、导出、三锚识别及 N1–N3 已验证；已接块端口转 TRUNCATED_BY_BLOCK_PORT unproven，普通真悬空仍报，无块 findings 不变；V3/嵌套/非端点接触/块内部展开未覆盖；最终全量 11226 passed / 26 skipped / 3 xfailed / 3 failed（三红均属绘制线 548D/K/P，本批新增失败清零），Connector 774、DSH 137/1、Rust 177/4** | tasks/038q_cbb_native.md；tasks/038q14_native_block_bootstrap.md；tasks/038q1_cbb_readonly_inventory.md；tasks/038q2_upstream_module_seed.md；tasks/038q3_symbol_file_read.md；tasks/038q4_elibz2_symbol_profile.md；tasks/038q5_ams_passive_profiles.md；tasks/038q6_footprint_file_read.md；tasks/038q7_sy8089_identity_profiles.md；tasks/038q8_symbol_book.md；tasks/038q9_remaining_identity_sweep.md；tasks/038q10_sy8089_symbol_binding.md；tasks/038q11_sy8089_offline_pilot.md；tasks/038q11a_buck_grammar_gap.md；tasks/038q12_ch340c_electrical_contract.md；tasks/038q13_ch340c_offline_pilot.md；tasks/038q13a_ch340_presentation_gaps.md |

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
