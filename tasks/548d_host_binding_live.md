# 548D3D-H-LIVE：test V4 的 MCU 人工调整对照页

2026-11-12 岳提出：把当前 MCU 摆到 `test V4`，由岳亲手改好，再由 agent 读回改动并总结通用规则。

## 性质与边界

- 这是独立的 **agent-adjusted 教学/诊断对照页**，不是 automatic 548D 验收，也不关闭强制 topology 的红测试，不进入548E交付。
- 强制 topology 当前 `ok=False`、没有候选，禁止把被拒几何落画布。落图输入只能是当前真实 `draw compile` 的合法 base MCU 候选，编译/逐脚不通过就停止。
- 唯一授权工程：`test V4`；唯一授权窗口在开工时为 `inst-030035529-hq99k1gc`（重连后须重新查，不记死）。
- R1开工证据：`doc.list` 报 `friendlyName=test V4`、`focused=true`；Board1已有P38 `0ec4dc022ef38563`、P39 `62e4828acc56a307`、P40 `eb22558f9f36db43`、活动P41 `037f5a63d7825dfe`；Board2 P1 `30560d9c0a52a6d2`。这些既有页全部不碰、不删。
- 只新建Board1 **P42**，先回读确认新页空白，再plan/apply；所有写调用显式带该新页uuid与当前test V4 instance。禁止写智能药箱、ROBOT ctrl FOC及任何真实工程。
- 本批不删除任何页或文件，不更新connector，不做git写。若P42已存在或非空，停止报告（R3），不得另起名替代。

## 交付与后续

1. 证据、派生输入和临时plan放 `.tmp_548dh_live/`；长期读数与渲染放 `evidence/548D/host-binding/live-reference/`。
2. plan → apply → lint → 宿主DRC → 宿主网表 → render，逐项留证据。任何写失败先回读，不盲目重试。
3. 交卷时明确P42页名/uuid、器件数、lint、DRC、逐脚/网表及渲染路径，主代理亲看后才把页面交给岳调整。
4. 岳调整期间agent不写。岳说改完后，只读回P42 geometry/readback/netlist/render，与调整前比较，提炼“相邻电源/地脚旗位、服务支路座位”的通用规则；手工调整永远记agent-adjusted，不冒称自动能力。

## 执行补充：真实MCU符号绑定（主代理据岳的落图请求裁定）

首轮真机零写入，证明15脚合成 `MCU32` 与本机64脚 `C431633` 的脚号集合完全不相交，且单岛标签桩可能拒绝；原文 `evidence/548D/host-binding/live-reference/README.md`。本批只允许继续尝试该文件的选项①，不扩大成三岛整页：

- 以P41实际U5的 `sch.component_pins` / `sch.geometry` 为证据派生host-bound库；每个电路脚名必须唯一映射到实际PinName，再改用对应PinNumber。未使用脚保持NC，不猜映射、不省略必要脚、不改网络归属。
- 新输入只放 `.tmp_548dh_live/host-bound/`；原冻结输入与证据不改。真实profile会改变几何，必须重新生产compile、独立逐脚与未绑页plan，全部通过后才创建P42；不得再拿15脚夹具候选冒充。
- 建P42后以其uuid重跑bound plan，再apply；真实引脚回读键和库几何闸仍必须通过。若单岛标签仍无解或映射不唯一，停止并保持真机零写入/报告现状，不改放三岛、不手摆孤儿件。
- 派生profile属于本机实测输入，不是参考坐标或userLock；本页仍只记agent-adjusted教学对照。

## 标准自动链受阻后的reference-replay交付路线

真实64脚输入的single/three-island自动compile均无候选，继续重试不再作为本交付路线。为满足岳“快点放”的明确请求，本页改为 **`reference-replay` 教学对照**：只读复用P41上已经存在且可回读的真实MCU功能局部（含实际器件、必要导线、电源/地旗与信号名），在新P42复现一个完整可编辑局部；不重开automatic编译，不用ok=False候选，不算548D自动能力。

优先用现有module_plan/draw apply守卫从参考LayoutPlan建plan；若需 `sch.place_*`，必须先形成完整参考几何/电气计划和离线readability+逐脚检查，再按真实库/引脚回读执行，不能只放三颗孤儿件。禁止 `sys.set_document_source` 整页覆写。源P41只读，参考坐标只用于本reference-replay页，不得写回automatic输入或userLocks。设计ators冲突必须具名处理，不能复制重号。

交付仍需新P42的readback/geometry/netlist/lint/DRC/export.render和主代理视觉；局部未包含的P41其他电路不属于本页网表验收范围。写失败先回读，不盲重试；若不完整必须明说，不能交给岳当已验收页。其余禁地、不删旧页、不git写不变。

## 结局：岳已完成agent-adjusted修正，规则已提炼

参考回放落P42 `48e9e0af4c45e37f` 后，初版有3个lint ERROR及5个横放旗INFO，不能记通过。
岳指出旗标全反并亲手修正。只读after显示：12枚旗全部竖直（0/180），C50/C51成对同向同节距，
U50/C52/R50功能组整体重排，冗余远旗减少一枚；`draw lint=0/0/0`，C/R全接、U50已连接12脚与
参考页一致。主代理已亲看after全图与局部放大，确认横放旗、旗字压线和文字出框已消失。
工程级DRC仍201 warn，持久化未关闭重开，不能称整工程全绿。

证据：`evidence/548D/host-binding/live-reference/README-adjusted.md`、`P42_adjusted.png`。
通用规则与禁止写死的实例数值见同目录 `rules-from-adjustment.md`。本页只关闭
reference-replay→agent-adjusted教学任务，不关闭548D3D-H强制topology红测试或automatic能力。

## 岳催促后的最终执行口径

岳在主代理明确“使用真实MCU和它的完整电源脚生成教学页”后指示“快点放吧”。据此本页授权真实器件的全部VDD(16/32/48/64)接3V3、全部VSS(15/31/47/63)接GND，并将唯一 `PB8-BOOT0`(61)作为BOOT0；这是本教学页的显式派生电路，不再声称与15脚夹具逐脚相同。优先真实64脚单岛；若其合法候选仍仅因单岛跨界标签桩无法建plan，为尽快交付可改用当前合法三岛页，岳只调整MCU区域，其余岛不语义重画。两种路线都必须真实compile/逐脚/plan通过才apply，不能落被拒候选或手摆孤儿件。C/R也须核对本机同LCSC实测几何，不沿用未经验证的假设。WARN逐项审查，ERROR不得force。其余R1、新页、禁地与证据纪律不变。

## P43：真实64脚 automatic MCU 单岛（岳明确恢复目标后授权）

- P42仍是agent-adjusted教学对照，不拿它冒充自动能力；P43必须完全由当前生产 `draw compile → plan → apply` 生成。P38–P42、Board2 P1与其他工程/窗口不写、不删。
- 开工实例 `inst-151817878-mqpd9jj1`，重连后重查；R1要求 `doc.list` 的 `friendlyName=test V4`、`focused=true`。既有P43（038Q15探针）已由其owner删除并回读不存在；本批新建页名P43，若已存在或非空停止，不另起名。
- 输入：`live-reference/circuit_hostbound.json`、`profiles_hostbound.json`、`p43/presentation_hostbound.json`。规格含localSeats、stubMin=40、native-attr；无参考坐标/userLocks。离线真实compile、逐脚/readability/grammar、主代理放大视觉及未绑plan已过；plan应用侧单run native carrier修复和6个可见attributeMoves均有证据。
- 新页回读空白后以 `--page <P43 uuid> --page-box 0,0,1170,825 --keep-names` 重绑plan，apply只用该plan和该实例。失败先回读，不盲重试，不落ok=False候选。
- 交付检查：draw lint、宿主DRC、宿主网表逐脚、export.render及主代理视觉。WARN逐项解释，ERROR不force；保存与关闭重开持久化分别报告，未做就不写saved_verified。
- 证据 `evidence/548D/host-binding/p43/`；真机串行，收工停本批拉起的daemon（不杀其他owner进程），零git写。
