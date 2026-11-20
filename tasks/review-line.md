# 审查线派单入口（540B8）

> 这是 review 线的任务路由，不复制规则规格。操作 SOP 以 `.agents/skills/boardwise/SKILL.md`
> 为准；现状与证据以 `tasks/540b_review_draw_decoupling.md` 和
> `evidence/540/b-behavior-equivalence.md` 为准。

## 1. 业务边界

| 可以派给 review 线 | 不应夹带 |
|---|---|
| `rules/**`（shared 的 `rules.base`/`rules.values` 除外） | 布局、布线、旗标、文字几何或绘制算法 |
| checkup、PCB review、证据/覆盖、review-read、triage/finalize、ReviewReport | `engines/draw*`、`core/layoutplan.py` 等 draw 内部 |
| parts/BOM/datasheet/catalog/harvest 等资料与器件链 | shared parser/model/bridge 的“顺手优化” |
| `commands/review.py` 的审查命令注册/分派 | 其他 19 个顶层命令的注册或 DSH draw 工具 |

依赖方向只能是 **review → shared / review**。不得新增 review→draw；shared 不能反向
import review。Finding、severity、mode 与报告措辞仍归 review；B1–B3 下沉的命名、
引脚连通、去耦库存和 CapDecision 是 shared 合同，不能在规则里复制第二份。

## 2. 公开入口

- CLI：`review`、`checkup`、`need-datasheet`、`triage`、`triage-batch`、
  `review-evidence`、`review-read`、`review-eval`、`review-mark`、`pcb`（子命令 `gate`，038Y5
  只读闸）、`parts`、`bom`。
- DSH：现有 review 工具名保持；`review finalize` 的 Session receipt 与 delivery gate 不变。
- 共享输入：公开导出 / DesignModel / CircuitSpec / DesignIntent / 部件货架；输出是报告与
  审查证据，不是 LayoutPlan 的内部对象。

## 3. 派单规则

1. 一张派单只写一个缺口和一个文件域，先列允许文件与相邻测试；不夹带 shared 或 draw 改动。
2. 确需改 shared parser/model/bridge/core/CLI 时，停止按普通 review 批处理，改走
   `tasks/shared-platform.md` 的集成锁；审查规则变化与迁移不得同批。
3. 规则语义、严重度或 verdict 变化必须先有行为证据和反例；纯解耦批不得借测试红灯改判。
4. 全量 pytest 一次只跑一轮，`-n 4 --dist loadfile` 且每批独立 basetemp；真机操作串行，
   只碰任务书逐字点名的 `test`/`test2`，真实工程不写。
5. 任何 git 写、push、发布、删除或 worktree add/remove/prune 都要另获岳的明确批准。

## 4. 验收与交接

- 小批先跑 `tests/test_540_cli_review.py`、对应规则/报告邻域和 `tests/test_owner_rules.py`；
  shared 边界改动另跑 `tests/test_540_shared_{naming,connectivity,decap}.py`。
- 最终串行验收包含全量 Python、connector、DSH 和（540C 后）Rust；邻域读数不能写成全量。
- 交接写清：行为基线、实际命令与读数、变异及 SHA-256 恢复、未覆盖项、后续依赖。
- #87/#88 验收矩阵与四视图锚见 `tasks/issue-87-88-acceptance.md`；#87④已由 `d2130b7` 落地
  并于 2026-11-06 复核（289 Python + 2 Rust，限 `pcb-voltage-spacing`），②仍开放、
  ⑤仅离线替代，**整单不关**；#88 的 1/295、四视图及 55=14+35+6 已获提出人确认并关单，
  `element_ids` 唯一性另立。
- 当前路线债：0.6.0 的 200A/B/C 仍按 `tasks/528_060_gate.md` 验收；540B 不替它们报完成。
- Rust 顺序：shared 纯函数/几何与 parser/model 之后才是 review；不在本线提前批量翻译。

**当前 worktree 状态**：审查线工作区 `E:\boardwise\.tmp_review_line`，分支 `review-v4`，
owner=审查线；绘制线独立开发、互不改文件，主仓及绘制线的未提交改动不碰。shared 集成、
全量测试与真机仍由 `tasks/shared-platform.md` 串行。旧 worktree 审计结论：没有可安全回收
项，证据区不按名字清理。`git worktree add/remove/prune` 仍逐次经岳明确批准。

## 5. 当前任务入口（2026-11-05）

- **038U1/U2 记录一致性**：已完成并提交 `d0275ae`，合同与验收记录见
  `tasks/038u_record_consistency.md` 和 `tasks/038u2_document_tombstones.md`。
- **038V 焊盘形状间距修正（实现与验收完成，已随 `683a526` 提交）**：任务书为
  `tasks/038v_pad_shape_clearance.md`。圆盘/长圆改为精确胶囊，非圆椭圆采用有界外接 32 边形；
  `pad_corners()` 的外接框公开合同不变。全量 9509 passed / 25 skipped / 2 个既有 Windows 环境失败；
  connector、DSH、Rust 均通过，未跑原始 PCB-A 或真机。
- **041 S1 跨板网络实例（实现与验收完成）**：合同与证据见
  `tasks/041s1_net_instances.md`。真实 uuid 的 NetInstance/unproven_edges、checkup/review 披露和
  triage 保守归属已落地；多板 DRC 叶子无板身份，统一不归属。全量 9542 passed / 25 skipped /
  2 个既有 Windows 环境失败，connector、DSH、Rust 均通过；S1 本身不含声明读取器或 proven 边。
- **041 S2 显式声明读取（实现与离线验收完成）**：合同与证据见
  `tasks/041s2_interconnect.md`。`review <file>` / `checkup --file` 新增显式 `--interconnect`，
  严格校验后只在报告中披露 proven 边，不合并网表、不改 findings/severity/verdict；空路径、坏文件、
  错误板身份、live/PCB/finalize/在线均拒绝。真实 3 板与 2 板 `.epro2` 均完成双报告对拍；
  最终全量 **9682 passed / 25 skipped / 2 个既有 Windows 环境失败**；connector、DSH、Rust 均通过。
  S3 宿主交叉验证继续暂缓，S4 必须先有真实板间证据。
- **038W PAD_NET 每脚网络判优（已随 `cdff88b` 提交）**：合同见 `tasks/038w_pad_net_journal.md`。
  每脚投影复用 038U 原子视图的同一 ticket/client 判优，改板前的旧网不再靠 `setdefault` 获胜；
  不改规则、CLI 参数与报告 schema。
- **038X 默认货架绝对路径与缺失披露（已随 `cdff88b` 提交）**：合同见
  `tasks/038x_shelf_resolution.md`。非 frozen 的默认读写统一改用 `resources.parts_library()`
  绝对路径，只读入口显式披露货架缺失，`load_parts` 的「缺文件可建空架」底层合同不变。
- **038Y PCB 几何三规则 + 只读 `pcb gate`（Y1–Y5 已随 `d422e7a` 提交）**：
  任务书 `tasks/038y1_pad_copper_overlap.md`、`tasks/038y2_pad_overlap_rule.md`、
  `tasks/038y3a_pad_ink_overlap.md`、`tasks/038y3b_silk_on_foreign_pad.md`、
  `tasks/038y4_silk_under_body.md`、`tasks/038y5_pcb_gate.md`（autofix 另见
  `tasks/038y6_silk_autofix.md`，**暂缓**）。联合读数 **1505 passed / 2 skipped**（不是全量）；
  两条既有归档 4 板实跑 WARN=0、近似披露 INFO 4，**不能写成所有板干净**。
  038Y5L/M/N 已完成 test V4 在线验收：活动页拒绝、PCB1/2 严格 DRC 各 1 错得 RED 且不继续
  checkup；第三板天然 DRC=0 后新鲜 checkup 真跑，因工程自身 26 ERROR、缺手册/分诊与
  boardsEmpty 得 INCOMPLETE/exit 3，不是 GREEN。DRC 清洁后的在线 checkup 已补齐；V3 与天然
  GREEN 仍待合适授权样本。证据 `outputs/review/038y5l/`、`038y5m/`、`038y5n/`，任务书
  `tasks/038y5l_pcb_gate_live.md`、`tasks/038y5m_pcb_gate_checkup_live.md`、
  `tasks/038y5n_pcb_gate_third_live.md`。
- **038Z1 test V4 真实三板骨架对拍（2026-11-15）**：两次 117295 B 导出哈希不同，
  只报语义对拍；离线/在线均 exit 1，57 条自有 findings 一致，三板各 35 checks、findings
  20/20/9，逐板字段与 crossView 一致。三板全 0 器件、铜层 2/0/0，不声称真实非空多板或
  真实多文件守卫；真实 NC、缺省 yAxisDirection 继续等样本。任务书
  `tasks/038z1_v4_live_archive_differential.md`，证据 `outputs/review/038z1/differential.json`。
- **529 去耦 mid 容值带（已随 `cdff88b` 提交）**：合同见 `tasks/529_decap_mid_band.md`。
  2.2/4.7µF 落入 mid 档，191D 的临时收窄按原判据回退，全 bulk 输入档保留 INFO 特例；
  四个距离阈值 `200/300/800/200` 不动。
- **527C2 跨视图几何分类与全部位号（已随 `cdff88b` 提交）**：合同见
  `tasks/527c2_cross_view_geometry.md`。lonely-pin 的 note 按几何分「没画线 / 网名不同 /
  落位嫌疑」并点名全部位号；`min_pins` 仍为 3，哪一侧电气结论更有权威不变。
- **541 运行时闸（R1/R2/R4 strict 已随 `cdff88b`；R3/I/R4 隔离实载）**：
  R3 `dsh-plugin/src/review-stage-gate.ts` 提供显式 out、receipt+callId 检查点、跨目录欠账拒绝和
  30 分钟/60 model steps 预算；541I 复用 protocol 唯一目录的 `--read-only` 并补 tool-gap。
  541R4 让 error `tool/result` 只清 pending、不记深挖/检查点。联合 DSH **169 passed / 1 skipped**，
  主代理独立变异均先红且哈希恢复；Python 目录闸 **36 passed**。隔离 DSH 0.2.2-rc.3 已验文件收据
  不解锁、initial/partial 解锁、跨目录欠账与 tool-gap；桌面 profile 未部署，任意宿主文件解析不覆盖。
  任务书 `tasks/541r3_dsh_stage_gate.md`、`tasks/541i_public_interface_allowlist.md`、
  `tasks/541r4_dsh_error_result_fold.md`，实载 `.tmp_541_live/session-4-events.jsonl`。
- 以上批次的最终全量 **9893 passed / 25 skipped / 14 failed / 1 warning**。
  其中 12 条是工作树既有货架数据漂移，2 条是既有 Windows 环境失败，不宣称全量全绿；
  connector、DSH、Rust 均通过。
- 新版宿主能力探针仍等明确的 4.1.94+ 测试环境和授权非空 PCB。

- **#87②⑤ 已落 `3d4a0d5`（origin/main）；test V4 在线验收完成（2026-11-16），未发布**：087E `sch.readback`
  可选 value/mpn 与来源已实现，P43 三器件与公开 ATTR 双源一致、11 netflag 为 null；087F1/F2
  PCB viewport、`capabilities.pcbRenderViewport` 与 liveevidence 已接入，旧 connector 缺 flag
  零 render。主代理 F1 **74 passed**、F2 Python **242 passed**、connector **809 passed**，
  独立变异均先红后恢复；直接 render 两板目检、SVG 具名拒绝；`review-evidence` exit0/
  capture.ok=true，`pcbImage.status=ok` 三板、livePcb ok、P43 焦点恢复，delivery 仅
  datasheets=unavailable。V3/生产非空板未覆盖，#87 待提出人复验不关单。任务书
  `tasks/087e_readback_value_mpn.md`、`tasks/087f1_pcb_viewport_render.md`、
  `tasks/087f2_pcb_evidence_integration.md`、`tasks/087f3_pcb_visual_docs_live.md`。

- **038Z2–Z4 真实 eprj3 兼容核查（2026-11-16，EDA 4.1.100）**：真实目录
  `E:/LC Project/test V4` 的 3 个 `.epcb2` 与 7 个 `.esch2` 只读合流；离线/在线均 exit 1、
  schema7，三板字段完全相同，60 条 findings 多重集一致，archivePcb ok/errors 一致。
  真实多文件正路径成立，但三块文件没有库副本，重复 PCB/分歧库/相同库三种 guard 未在真实文件
  上触发；17 个合成测试仅补充，不冒充真实负例。7 页 2603 条 `yAxisDirection` 全为 up，
  NO_CONNECT=0，SCH_PAGE 本体内缺省标记的坐标记录=0；NC 与缺省路径仍未覆盖。逐板
  components 全为 0，真实非空多板仍未覆盖。证据 `outputs/review/038z2/differential.json`、
  `038z3/record-scan.json`、`038z4/board-scan.json`。

- **038Y5O V3 `test` 在线 gate（2026-11-16）**：宿主实测仍为 4.1.100，PCB1/2 各严格
  DRC errors=1 / items=1 / truncated=false，gate RED / exit 2，checkup 均未运行；Start Page
  已恢复。只完成 `.eprj2` 路径验证，不是 3.2.x 宿主验收，也没有 GREEN。后续需清洁授权
  测试板与 V3 宿主环境。证据 `outputs/review/038y5o/`。

- **天然 GREEN 与 V3 环境裁定（岳，2026-11-16）**：没有满足当前严格审查规则的天然
  GREEN PCB，成熟产品也可能存在若干问题；天然 GREEN 不再列为本机必做，不为凑通过放宽规则。
  GREEN 正向编排继续由既有 fake/合成测试支撑，真实 RED/INCOMPLETE 如实保留。身边设备均为
  V4，V3 宿主验收转为等待其他用户反馈，仍不宣称 V3 已验证。


- **550 离线 PCB 铜路径（已实现并完成本批验收）**：`boardwise pcb net-path FILE --from REF.PAD --to REF.PAD [--board]` 只读 `.epro2/.eprj3`，输出 `boardwise.pcbNetPath/1`，三态 CONNECTED/NOT_PROVEN/INDETERMINATE；只用 pad/直线 track/via，pour/PLANE 排除，ARC、未知几何、netless 铜与 via-in-pad 不制造证据，多板必须选板。核心与 CLI 最终聚焦 **371 passed**、卫生 **4 passed**，真实归档三种判定和两组主代理变异均核过；未跑全量。任务书 `tasks/550_pcb_net_path.md`，公开说明 `docs/review-sop.md` §3.2。在线、ARC 建模、through/layer、真实非空多板与 via-in-pad 宿主语义仍未覆盖。550A P1 已完成原始 ARC 数据与同网降级，最终组合 **726 passed / 1 skipped**；角度单位仍未证实，P3 几何禁止，ROBOT 不转绿。P2 与静态在线探针已做，test/ROBOT 均 active=null，未强行切页。551 `pcb.net_class.list` 已完成 connector/protocol/docs 离线实现：Connector **821 passed**、Python 邻域 **339 passed**，读不到为 null 不伪造空类，非 PCB 焦点拒绝；ROBOT 真实调用已完成：classes=[] 且 netRules=49，双 reads 成功、规则集前后逐字不变，Start Page 已恢复，daemon/connector 0.6.2 保留；非空网络类仍未覆盖。ARC 宿主角度已证实为度，但几何 bbox 不能判定扫向，P3 继续禁止。任务书 `tasks/551_pcb_net_class_list.md`。sch replace/rebind 与 PCB 同步各自独立成批，不在本批夹带。

- **550B 在线只读实例探针（已本地提交 `9f73ede`，未推送；2026-11-18 真机验收完成）**：`sys.probe {instances:[…]}` 以封闭 kind/method 调用既有 PCB 图元，严格 PCB 页守卫，只回 ID；line/arc/via 的 entireTrack/adjacent 均实测可用，includeVias=true 确实多返回 via。基类 pad 无 getConnectedPrimitives，有界 ComponentPad 回退实测 55 组件唯一匹配、零读错误，true/false 各返回 2 条走线。Connector 全量 **846 passed** + typecheck，Python 合同/政策 **113 passed**；主代理两组独立变异先红后恢复。V3 未验，不宣称 live net-path。任务书 `tasks/550b_live_primitive_probe.md`，本机证据 `.tmp_550_live/`。

- **552/553/554 多单元与跨板位号误报修复（已本地提交 `14e8f39`，未推送；2026-11-19 完成）**：多单元按 PIN.partId 拆引脚，并以相同非空 Unique ID/Device + 不同 partId 认定同一物理件；同引脚冲突、缺身份与复制件仍报重号。跨板同名保留项目事实但不再产生 ERROR，同板同页/跨页重号不变。宿主网表 4 件 / 32 脚的完整成员集合全部对拍一致；DSH 实际 CLI 同一归档复跑为 0 ERROR、0 条位号 finding。A/B 派生基线 80+188 passed，最终综合 552 passed，合同/卫生另 127 passed；主代理两组独立变异均先红后 cp+SHA 恢复。未跑全量；综合命令另见 4 条绘制线 CLI 合同漂移，layer 另有 1 条其他线跨层红，未越线处理。任务书 `tasks/552_multi_unit_designators.md`、`tasks/553_cross_board_designators.md`、`tasks/554_designator_integration.md`，证据 `evidence/552/`、`evidence/553/`、`evidence/554/`。

- **555 批量手册链 live/DSH 集成（已本地提交 `14e8f39`，未推送；真实试点 2026-11-19 完成）**：`parts hunt --live` 复用全身份阶梯，`--from-report` 只处理 needs_datasheet；跨板同位号按真实身份分别寻址，候选 sidecar 加身份后缀防覆盖。DSH 新增 `boardwise_parts_hunt`，支持 answers/claims 和显式 shelf，不重写下载器。真实报告展开为 18 个身份行；4 份 claims 过生产闸、0 拒绝，3 颗转机器核验待签，1 颗原已 verified。真缺资料 20→17、机器待签 0→3，needs_datasheet 仍 15、verdict 仍 incomplete。Python **218 passed**、DSH **207 passed / 1 skipped**，真实适配层零外呼冒烟通过，主代理两组变异先红后恢复。全局货架与真实设计未写，临时 daemon 已收。插件包 `.tmp_555/boardwise-dsh-0.6.3-beta.3.tgz` 未部署；CLI 合同快照已由 556 生成并同步（559 新增命令的合同由 560 再核）。U8 身份、EST026 图像文字层、机械件与无脚表连接器仍需人工。任务书与证据 `tasks/555_datasheet_hunt_integration.md`、`evidence/555/`。

- **556 shared CLI 合同与 `_page_y` 跨层集成（工作树完成、未提交未推送）**：`parsers.schematic.page_y` 公有化并保留 `_page_y` 兼容别名，`engines/v4facts.py` 只消费公有入口；`tools/cli_contract.py --write` 从真实 parser 一次生成，hunt/draw/bridge 三类既有漂移同批收口。主代理两组独立变异先红后 cp+SHA 恢复：v4facts 回退私有 `_page_y` → **1 failed / 8 passed**（`test_no_private_name_crosses_a_layer`），去掉 `page_y` 负号 → **4 failed / 37 passed**（v4facts 与 agentadjusted/CLI 坐标断言同时翻转），恢复后 **50 passed in 15.23s**。证据 `evidence/556/`，任务书 `tasks/556_shared_cli_layer_integration.md`。

- **557 审查线台账提交状态校正（工作树完成、未提交未推送）**：只改文档，按真实归属写 550B=`9f73ede`、552–555=`14e8f39`、087E/F=`3d4a0d5`（`origin/main`），均**未推送**；文档/工作区聚焦 **67 passed**。558 开始时那两条 `owner` 红来自他批新增 `src/boardwise/core/connection.py` 未登记（157→159），与本批无关，559 已最小同步。任务书 `tasks/557_review_ledger_status.md`。

- **558/558B 手册义务分类（工作树完成、未提交未推送）**：新增四类义务 `ic-facts` / `connector-pinout` / `identity-unresolved` / `no-ic-facts`，机械件走 `ok:null + applicable:false` 三通道、不查本地 PDF、问题指向 `parts accept-unknown --reason`，连接器查询改 `pinout/引脚定义/脚位图`；机械 marked 行仍收集 seed，过滤只在 facts 触发输出循环。真实重算（同一 `.epro2` + `.tmp_555` parts-v2 只读）：unreviewed **23→23**、needs_datasheet **15→11**、义务分布 no-ic-facts 8 / connector-pinout 6 / ic-facts 9、verdict 仍 `incomplete`、`factsTrust` 三份 `machine_verified` 不变。父验聚焦 **135 passed in 19.03s**，变异 A（禁机械分支）**4 failed**、变异 B（禁连接器分支）**2 failed**，恢复 SHA `2e2b228f…`。558B 由 `partkind` 精确族词把 EST026 三行转为 `connector-pinout`，父移除该词 **3 failed**、恢复后聚焦 **68 passed**。**三份机器档已由岳签核为 verified；U8 身份只体现为 `pinoutSource: "none"`，未伪造行内身份结论；机械件退出 hunt 工作清单不等于审查通过。** 证据 `evidence/558/`，任务书 `tasks/558_datasheet_obligations.md`、`tasks/558b_est026_part_kind.md`。

- **559 在线 PCB 连通证据（工作树完成、未提交未推送）**：纯函数投影 `core.connection.project_connection`（schema `boardwise.pcbConnection/1`，无 `path`/`hopCount`/`viaCount`）+ `boardwise pcb connection --from REF.PAD --to REF.PAD`（仅在线，退出码 0/2/3）+ connector `pcb.connection_probe` 只读 action（`risk=read`、`design_write=False`、`params=(from,to)`）。父验 **268 passed in 29.66s** Python、connector typecheck + **43 passed / 0 failed**；两有效变异先红后 cp+SHA 恢复（类型闸 **2 failed**、缺口闸 **9 failed**）。真实**预验**：用已激活的 550B `sys.probe` + 同会话归档身份，正例 CONNECTED、负例 NOT_PROVEN，与离线 550 判定一致——这是**预验，不是新 action 的激活**。原生 `pcb.connection_probe` 在旧 daemon 上 **exit 3、stdout 空、`unknown action 'pcb.connection_probe'`**，当时未热更、未部署、未发布（此失败史保留）。**2026-11-20 原生激活成立**：经用户另行授权，daemon 重启 + connector 写入 + 用户完整重启 EDA 后，`sys.connector_status` 新实例 `inst-015644463-2wuenu0j`（`bootstrapAt`/`activateAt`=2026-11-20T01:56:44.463/465Z），首次激活成立；正例 `LED1.2→U10.2` exit0 `CONNECTED`、唯一 `direct-shared-track` `2988899bbc9547de`，反例 `C22.1→C23.2` exit2 `NOT_PROVEN`、`proof=[]`，unknown/errors 均 0，与离线 550 一致，焦点恢复、`designWrites=0`；权威证据 `evidence/559/native-activation-success.json`。菜单点击只增 `evaluations` 不改 `bootstrapAt`、必须完整重启这一条也一并留档。证据 `evidence/559/`，任务书 `tasks/559_live_pcb_connection.md`。
- **559B 在线连通收窄为 direct-only（工作树完成、未提交未推送）**：真实板上取一个离线 550 分成 **6 个分离铜分量**的网，`getEntireTrack(true)` 返回 **76 个 ID 且 truncated=true**，其中四个 ID 来自其他分离分量（`evidence/559/entire-track-rejection.json`）⇒ **成员资格不能证明物理连通**。proof 只剩 `direct-shared-track`（两端 direct 同一有类型 Line/Arc）与 `direct-other-pad`（一端 direct 明确是对方焊盘）；connector 不再调 `getEntireTrack`，响应无 `tracks[]`、无总 ID 预算与 `coverage.ids`；legacy 非空 `tracks[]` 在 Python 侧记 `entire-track-unsupported` unknown，永不用于正证明，也压住否定。`NOT_PROVEN` 重定为「direct 范围内两端无共享图元」，**不是开路**；多跳铜需另立 `getAdjacentPrimitives` 图合同（激活成立后仍不越此界）。P2 三项披露修复保留（`direct-non-proof-type` / refusal 文案与 stdout 分离 / `versions.missing·error`）。新反例：from direct=t1、to direct=t2、from.tracks 含 t2 **不得 CONNECTED**；无 tracks 且完整无交集才 `NOT_PROVEN`；Connector happy path 断言 entireTrack 调用为零。`contracts/cli/v1.json` 官方重生成。任务书 `tasks/559b_direct_only_connection.md`。

- **560 目标 1/2/4/5 总集成与文档收尾（工作树完成、未提交未推送）**：#87 的 087E/F 状态改「已落 `3d4a0d5`（`origin/main`）、未发布」，550B 行尾只留「未推送、未发布」，555 行末合同状态改「556 已同步」，protocol/connector 的 last-dot 说明改为「designator 可含点」、protocol `returns` 的 `direct` 示例删除 TS 无有的 `status` 键；556–560 实况入账本文件与 TASKMAP。DSH **不新增 connection 工具**：typed CLI 底座先验收，原生 action 激活需另获授权后再裁是否适配；本批只核既有 DSH 全套不回归，不 bump、不 pack。本批不推送、不部署 DSH、不发布；**最终验收（第三轮全量）11 failed / 11921 passed / 26 skipped / 2 xfailed in 2593.86s**：二轮 9 处审查/shared 红（537A 2 / 540 4 / 038 3）全部消失，剩余 **11 处全部落在绘制线**（`test_116_ordinal_consumption` 1、548m 1、543h2 1、548c7 4、548d_wifi_ground 1、543h3b 1、draw_plain_carrier 1、548k_stub_lane 1），按绘制线归属披露；**不写全仓全绿，也不安排第四次全量**。connector 864 passed + typecheck、DSH 207 passed/1 skipped + typecheck/build、Rust 177 passed/4 ignored 为各线读数；合同父变异移除 connection_probe 例外 2 红、owner 回退 4 红、038 旧 hash 回退 3 红，cp 恢复后 119 passed。native action 激活已于 2026-11-20 另行成立（`evidence/559/native-activation-success.json`，direct-only 范围不变、不声称板卡 GREEN）、三份机器档已由岳签核为 verified、U8/EST026 身份未伪造。
