# 共享底座与集成锁（540B8）

> shared 不是第三条业务线，也不是“谁都能顺手改”的公共目录。它承载 review/draw 共同
> 依赖的公开合同；任何变化都按**两线集成改动**单独复审。

## 1. 范围

- `.epro2` / netlist parser、DesignModel、单位/几何、设计身份、CircuitSpec/DesignIntent、
  ChangePlan/SymbolProfile/Compare/Blocks/PinTable 等公开合同。
- bridge/connector/daemon 的传输、权限和身份；纯 `engines.assemble`。
- B1–B3 的 `core/netdomains.py`、`core/connectivity.py`、`core/decap.py`。
- `commands/shared.py` 与 assembly 的 24 命令组装；`commands/assembly.py` 仅 assembly 表面。
- 540C 的跨语言合同、差分/golden 和最小 Rust 进程骨架。

shared 只能 import shared。`core.annotations`/`core.railquery` 等既有 review 模块和
`core.presentationspec`/`core.layoutplan` 等 draw 模块不因放在 core 就变成 shared。
逐模块权威是 `contracts/module-owners.json`，由 `tests/test_owner_rules.py` 机器执行。

## 2. 集成锁

1. shared 改动必须单独成批，先写公开合同、调用方、行为基线和回退方式；不得夹在 review
   规则或 draw 算法批里，也不得为了“顺手”改变 verdict、几何或输出。
2. 至少验证两个实际消费者的等价性。Finding/severity/mode 留 review，绘制决策留 draw；
   shared 不复制任何一端的业务判断。
3. AST/owner/layer 守卫必须保持：shared→review/draw=0，review→draw=0，legacy 集合为空。
   新跨线边不能靠登记例外偷偷通过，必须先回到架构裁定。
4. CLI 旧参数/顺序/退出码/输出与 monkeypatch 可观察面要冻结；DSH 旧名与 JSON 同理。
   新业务一律先给版本化合同，不给隐式默认值。
5. **shared、全量测试、真机全部串行**。全量 pytest 一次一轮，connector/DSH/Rust 随后；
   真机只读或写入都需任务书逐字授权，真实工程不写。
6. git 写、push、发布、删除、全局安装与 worktree add/remove/prune 逐次问岳。
7. **每批任务书必须写兼容矩阵与 negative control**：按该批实际涉及的维度逐项列
   （V3/V4、`.epro2`/`.eprj2`/`.eprj3`、在线/离线、单/多板、普通器件/CBB），
   并写清「不该变的东西必须不变」的反向断言。矩阵里没有的维度就是**未覆盖**——
   未覆盖不得写「兼容完成」，也不得用别的维度的绿读数替代。
   多板这一维的反向断言要有两个具体例子：**重复 PCB 不许双审**（同一块板导出两次即拒绝，
   不按标题聚合、不静默去重），**分歧库不许串板**（同名库副本只有内容相同才合流，
   内容分歧就拒绝读取，不拿另一块板的几何去审）。

## 3. 交接与证据

- 当前行为矩阵：`evidence/540/b-behavior-equivalence.md`。它记录邻域和结构证据，
  不把邻域读数冒充最终全量。
- CLI 兼容锚：完整 argparse 树/帮助/默认值/namespace 对拍；规则源码指纹只说明源码位置，
  不能代替行为测试。
- 每批交接写清实际命令、读数、变异与 SHA-256 恢复、未覆盖项和对两线的影响。
- 证据/探针按 `docs/workspace-conventions.md` 落位；未跟踪/ignored 不等于可回收。

## 4. Rust strangler 接口

迁移顺序固定为：**纯函数/几何 → parser/model → review → draw → daemon 最后**。
进程边界优先 Rust CLI + structured JSON，不引入 PyO3/WASM/Node native addon。
0.6.x 新工具/引擎默认 Rust，例外登记；旧工具按「合同对齐 → Rust 默认 → 临时 Python
fallback → 删除旧实现」垂直迁移。Python fallback 只过渡，不形成长期双业务实现。
0.7.0 的目标是 Rust 接管全部受支持主流程，不是逐行翻译所有 Python；connector/DSH 薄适配可留 TS。

540C 的任务书与完成定义见 `tasks/540c_rust_platform.md`，构建/差分命令见
`docs/rust-platform.md`，证据见 `evidence/540/c-acceptance.md`。迁移与算法变化不得同批；
没有真实工程夹具、全局安装或发布。

## 5. worktree 与并行派单

审查线工作区是 `E:\boardwise\.tmp_review_line`（分支 `review-v4`，owner=审查线）；
绘制线独立开发、互不改文件，主仓及绘制线的未提交改动不碰。两线可独立派小批，但 shared
集成、全量测试与真机由本文件串行。旧 worktree 审计结论：没有可安全回收项，证据区不按
名字清理。`git worktree add/remove/prune` 仍逐次经岳批准；已注册 worktree 不可解释成
可写工作区或临时目录。

## 6. 053R：可选 ATTR 移动的 ChangePlan / apply 集成

### 公开合同与边界（先合同，后实现）

- 053P/Q 已分别验证 `sch.list_attributes` / `sch.move_attribute`，没有改绘制决策。本批只把
  既有能力接进公开计划与 draw-module apply，**不改 compiler、readability、label stub 或 attach**。
- `PlanChange` 增加可选 `attributeMoves`，缺省 `[]` 且序列化时**整个键省略**。每行：

  ```json
  {"moveVersion": 1, "owner": {"kind": "part", "specId": "R1"},
   "role": "reference", "to": {"x": 280, "y": 335}}
  {"moveVersion": 1, "owner": {"kind": "wire", "index": 0},
   "role": "net", "to": {"x": 370, "y": 320}}
  ```

  part 只允许 reference/value，wire 只允许 net；wire.index 是 `draw_wires` 的非负整数下标。
  `to` 只含 x/y/rotation/alignMode，至少一项，数值有限，alignMode=1..9。moveVersion 只认 1；
  拒绝任意 primitiveId、key/value 改写、visibility/字体、额外键和不合理 owner/role 组合。
  `plan_version` 不变：这是带行级版本的可选附加合同，旧文档不含它。
- apply 以本 plan 的 `spec_id` / wire 顺序解析父图元，以页面真实位号、导线网名、可见 Name
  文字行解析目标，再交给已有 `sch.move_attribute` 的页+父级+原键值守卫。目标不是任意 id；
  重复候选、找不到、父级/键值不符、回读不符均拒绝，不挑第一个、不改文字内容、不动导线。
- 仅在非空 moves 时增加写前 `sch.list_attributes` + `sys.probe(modify)` 能力检查；失败在器件
  写入前停止。检查只证明 API 面，不冒充移动成功。运行时移动失败保留现场、不保存、不清理、
  不静默退回折线。空 moves 的 monkeypatch 调用序、CLI 参数/退出码、旧 JSON 输出保持不变。
- `attributeMoves` 由后续显式绘制规格开关生成，本批不增加那个开关、不决定布局。P22 的计划
  是**一次性合成计划探针**：用现有 compiler 出一颗 R0603-1k 和一条 V3 标签线，再只附加
  reference/net 两行移动；不得把这份探针规格说成 CH343 成品或自动生成能力。

### 两个消费者与回退

- review/edit 的 component-value / patch-pin 既有计划：不含新键，round-trip、动作序、finding/
  verdict 不变；shared 不读 review 业务。
- draw-module 的旧计划（含 `.tmp_fix/v44.presentation.json` 编译结果）：不含新键，计划字节、
  apply 调用序和退出码不变；新行只走 draw-module 的明确附加段，不改变其他 edit 命令。
- 回退是去掉可选行/规格开关即恢复旧行为；无需删数据库、迁移文件或改旧计划。不得用
  `git checkout/restore` 回退未提交源码，变异一律 cp 备份 + sha256 恢复。DSH 无新 CLI 参数、
  工具或 JSON 字段，本批不扩 DSH 工具面；connector 版本不 bump、不 release。

### 兼容矩阵与 negative control

| 维度 | 本批覆盖 | 必须不变 / 不得声称 |
|---|---|---|
| V3 3.2 宿主 | fake：旧计划零 ATTR 调用；新计划在写器件前拒绝 | 不声称 V3 真机可用；不许退回折线后称新合同成功 |
| V4 4.1.93 宿主 | test V4 新 P22，一普通 R、一直线 V3、两个 move | P20/Board2 P1/ROBOT 不写；R 右 pin 仍 V3、Line 不变 |
| 在线 / 离线 | 离线 JSON round-trip/apply fake；在线合成 plan/apply | 离线通过不冒充宿主移动；真机移动不冒充自动生成布局 |
| `.epro2/.eprj2/.eprj3` | parser 未改，**未覆盖** | 不声称三种容器兼容完成 |
| 单/多板 | 仅 test V4 单工程、页 UUID 守卫，**多板未覆盖** | 重复 PCB 双审与分歧库串板均不得借本批宣称改变或验证 |
| 普通器件 / CBB | 仅 C21190 普通器件，**CBB 未覆盖** | 不声称 CBB 属性行形状已支持 |
| 旧 connector / 新 connector | 旧计划不调用新动作；新计划缺能力先拒绝 | UNKNOWN/NOT_IMPLEMENTED 不得视为空属性或移动成功 |
| 单线单名 | P22 不再调用 createNetLabel，父 wire 恰一枚 Name=V3 | 两枚同名、选第一枚、网表丢名、导线折弯均不通过 |

### 实施与验收

- 文件域：`core/changeplan.py`、draw-module apply 的 `cli.py` 必要段、对应现有测试与公开
  `docs/changeplan.md`/`docs/draw.md`（若合同实际所在文件不同以仓库索引为准，不新写综述）。
  connector 的 053P/Q 动作已验收，本批不扩 JS 写面、不改 review 规则、不改 draw 算法。
- 测试：新旧计划 round-trip、空 moves 调用序、非法行零写、目标重复/缺失零移动、applied=false
  不保存、owner/layer 守卫；两处独立变异必须红并 cp+sha256 恢复。全量只在最终交付批一次串行。
- 真机：沿用 `.tmp_534q/home` 的 BOARDWISE_HOME 与写白名单、真实审计；R1 两旧页 UUID 同前。
  新建 P22 且保持 P21/P20/参考页不动；合成 plan/apply 后取 ATTR/source/netlist/lint/PNG/SVG。
  P22 必须一 R、一根直 V3 线、每线一枚 Name，参考文字/网名到计划位置，55/55 之类整板口径
  不得套到这颗探针。失败页只进 evidence，不删页/件，不替换 P20。
- 预算：一个 coder，40 步/30 分钟，证据 `evidence/534r/`，临时 `.tmp_534r/`；不跑全量、
  零 git 写、零 rm、零额外线 agent。交回≤1500字，含测试计数、兼容矩阵逐项证据、未覆盖项。

#### 053R 续审：负合同夹具与完成探针（同一公开合同）

- 首轮未交卷：1 红且 P22 未做。主代理复跑为 108 passed / 1 failed；失败实际是空 profiles
  先拒，参数化用例又未断言错误内容，不能当成行校验通过。改为 `base._plan()` 的真实有效
  payload 注入非法行，并断言 `attributeMoves[0]` 与相应原因；移除无效的最小夹具，不放宽校验。
- **完成探针补充**：非空 moves 必须在 early `already_applied` 前读取整页 ATTR，逐行核对
  role、内容、可见性和 `to` 中所声明的字段。part 的父级由本页实际 designator 器件解析；
  wire 的父级须属于本页 wires，按该 wire 的 net 找匹配文字。允许用同网的实际父级完成重跑判定
  （宿主可合并线、id 可变），但同一 move 多个候选、不同 move 复用同一 attr、readErrors、
  坐标/姿态不符均不得 already_applied。空 moves 不增加这次读取或报告字段。
- 新钉：文字未到位 → 不得成功/不得 already_applied；全部到位 → already_applied 且零
  `sch.move_attribute` / 零器件导线重写。这里只读，不借完成探针提前执行移动。
- 修正后重跑 053R/054/121c/532/owner 聚焦集，再做 P22。续单最多 35 步/25 分钟，仍不扩范围。

#### 053R P22 载体裁定（不缩实验收）

- 单件 R + 单信号网没有合法 grammar，编译实测四种配置均拒绝，零 bridge 写；原文一颗 R 的
  **载体**不可行，不新增单件 grammar、不手工补线。原始输出 `evidence/534r/p22-compile-failure.md`。
- 改用仓库既有 `divider` 拓扑：两颗同实测 R0603-1k-C21190，VCC(power)=R1.1、
  V3(signal)=R1.2+R2.1、GND(gnd)=R2.2；`grammarRef=voltage-divider`，V3=output。
  本决定替代本节前面 P22「一颗 R / R 右 pin」的载体描述，其他合同不变。
- 必须先确认 plan 有 net=V3 的 label wire，再附 R1.reference 与该 wire.net 两个 move。
  验收是 **R1.2 与 R2.1 均属于 V3**、该连续 wire 恰一枚可见 Name=V3、文字移动、Line 不变、
  lint/PNG/SVG 目检；这不是减少连通或视觉条件，也不代表 CH343 的 55 脚验收。

#### 053R P22 失败与 P23 重验

- P22=`f5be857b564e7f3c` 已落两 R/线/旗标，但 apply 以 `attribute_move_failed` 停止、未保存，
  无 render/lint，判为实验页。根因是 `primitive_ids` 按实际 designator 键、move 却按 specId 查，
  fake 两者相同而漏测；不得重用 P22 叠加写入。
- 修正只做 `spec_id → 本 plan 的 designator → primitive_ids` 映射，并新增 designator≠specId
  的 apply 钉，断言移动父级是实际 `c-R7`、不是猜测的 `c-R1`。聚焦测试全绿后，先建空 P23，
  `draw plan --page P23` 再附同两行 moves、apply 到 P23；不得在 P22 或任何旧页重放。
- P23 成功才补齐移动后 ATTR、netlist、source、lint、PNG/SVG 与审计。若宿主合线导致 wire 父级
  失效，同样停下取证，不把缺失父级当成可随意选择的标签。

#### 053R P23 图幅失败与 P24 强制条件

- 主代理亲看 P23 并亲跑页级 `draw lint`：文字移动/netlist 虽成功，但内容在图框外，
  **15E/0W/1I**，P23=`11466f39d6ac4507` 改为拒收实验页，上一条“成功”仅指 ATTR 动作。
  原因是 plan 未给真实图幅，落入测试默认负坐标；apply 的 exit0 不是视觉/图幅验收。
- P24 必须新建空页，`draw plan --page <新uuid> --page-box 0,0,1170,825`（当前实测 A4），
  落图前断言所有 part/wire/flag/文本目标在图内。R1 reference 移到本体左侧净空，V3 Name
  移到水平直段上方20，不沿用负坐标页的手写目标。成功后必须跑 `boardwise draw lint`
  （不是 `boardwise lint`）0E，PNG/SVG 由主代理亲看；缺一项仍不算 P22/P23/P24 探针通过。

#### 053R P24 验收与 value 幂等收尾

- 主代理亲看 `evidence/534r/p24.png` 全图与局部：P24=`fa854ea5b0442773`，R11 位号左侧
  净空、V3 单枚且在直线上方、R12/GND 清楚，无文字压线；`draw lint 0E/0W/1I`（L9 仅小探针
  面积提示）。R11/R12 中点两端 V3、两个 move after=to、Line 不变，**能力切片通过**；
  这不是 CH343 整页通过，也不外推 V3/多板/CBB/容器格式。
- 主代理审完成探针发现未覆盖的真实形状：R900 可见 `Name` 是 `={Value}`，不是设计值 `1k`。
  `_draw_attribute_move_problems` 对 role=value 不应把显示公式与设计值比较。收尾仅允许：
  在已解析的实际器件父级下，要求**唯一有坐标且 valueVisible=true 的 Name**，再比 to 字段；
  不猜公式、不读别的器件、不放宽重复候选拒绝。fake 改用 `Name="={Value}"` + part.value=`1k`，
  钉住全部到位可 already_applied、未到位不可 already_applied；其余 reference/net 行为不变。
- 这是一个共享小修，不改 draw 算法。子代理显式 `opencode go/deepseek-v4.1-flash`，最多 12 步/
  12 分钟；跑 053R/054/121c/532/owner 聚焦集与一次针对该行的 cp+sha256 变异。真机 value 移动
  留给下一批显式 textPlacement，不在这批新建页面。

## 7. 053U：版本化 ATTR 可见性与重复网名隐藏

### 公开合同与 negative control

- Type-C 可逆脚需要各自保留 NET 才能合并电气网络，但不需要每个脚都显示同名文字。
  本批只增加“隐藏已确认的一个 ATTR 文字”，**不把导线 net 清空、不删除 ATTR、不跨脚拉线**。
  这也不改 053T 的物理连通去重；页内显示策略是下一批绘制线的职责。
- `sch.move_attribute` 新增可选 `valueVisible`（严格 bool），与 x/y/rotation/alignMode 共用既有
  page/parent/id/expectedKey/expectedValue 守卫，至少一项；仍禁 key/value/keyVisible/字体/任意 JS。
  前后 fresh get 必须含 ValueVisible，缺该读口写前拒绝。未提供 valueVisible 的调用逐字节旧行为。
- `PlanAttributeMove` 增加 `move_version`（缺省 1）与可缺省 `value_visible`。version=1 保持
  x/y/rotation/alignMode；**version=2** 才允许 `to.valueVisible`，且只允许 wire/net，可单独
  构成一次隐藏。旧 plan 无该字段/版本仍 1，序列化和 apply 调用序不变；未知版本、part/ref/value
  的可见性、非 bool、其它可见性键均拒绝。version=2 是显式新合同，不偷偷改写 version=1。
- apply 的隐藏目标仍是父 wire 下唯一 Name=net；找不到/重复不挑。隐藏完成探针不得再要求
  valueVisible=true；应核对该 ATTR `valueVisible=false`、net/父级不变。显示目标仍要求可见。
  version=2 的移动 after/to 必须逐字段一致，失败不保存。缺 API/旧 connector 写器件前拒绝。
- 两消费者：review/edit 旧计划不含 v2，动作/verdict 不变；draw-module 无 moves 或 version=1
  计划保持调用/输出。文件格式、多板、CBB、V3 真机仍**未覆盖**，不称兼容完成。
  negative control：隐藏后宿主 netlist 必须逐字节等价，绝不能用“看不见”冒充“电气断开”。

### P21 垂直切片与验收

- 文件域限 connector move handler及测试、protocol/docs bridge、changeplan/cli 的 v2 必要段、
  053R/Q 相关测试；不改 compiler/readability/drawapply/review/package.json/cases。
- 先离线：v1 旧 roundtrip、v2 net 隐藏、v2 part 拒绝、非 bool 零写、缺 ValueVisible 写前拒绝、
  hidden idempotence、重复候选不挑、原Name/netlist不变。两处变异（bool白名单、hidden完成判定）
  红后 cp+sha256 恢复；connector/目录聚焦测试，不全量。
- 真机只 `test V4` 的 P21=`6f7a271dfc7ec3e0`，R1 同前，允许聚焦 P21 但不写其它页。
  写前重新 list 必须仍见 wire=`826fcdf4abadc39b` 下两枚 Name=V3：中点 `ce37cb4e5d0aff36`
  @ `(370,320)`、末端 `157f86e71e6e601b` @ `(420,300)`。只隐藏末端这一枚（valueVisible=false），
  不移动中点、不再 createNetLabel、不删图元。热更仅当前 test V4 connector；不 bump/release。
  后读必须一枚可见 V3、一枚隐藏 V3，R900.pin2 仍 V3、Line/netlist不变；保存 source/netlist/
  PNG/SVG/审计到 `evidence/534u/`。这是属性能力证据，不是 CH343 成品。
- 一个 coder，显式 `opencode go/deepseek-v4.1-flash`，35 步/25 分钟；临时 `.tmp_534u/`，
  零 git 写/零 rm/零额外线 agent。交回≤1200字含测试计数、真实 before/after、网表/图片/未覆盖项。

### 053U 主代理复验：版本必填与图片结论

- P21 图片已亲看：只剩中点 V3，R900/1kΩ/直线不变；hide_write 的 after=false，source 仅
  valueVisible 变化，netlist 字节相同。R900.pin2 不在本次独立读数中重新断言，只沿用053O记录，
  不拿“器件中心网表读不到”冒充新的逐脚证据。
- `moveVersion` 自 053R 就是**行内必填**。当前 parser 的 `item.get("moveVersion", 1)` 不当放宽
  旧合同，须改回缺失拒绝；`PlanAttributeMove(move_version=1)` 仅是程序构造默认值，输出仍写 1。
  新增缺失版本负例与文档钉，跑053R/doc_claims聚焦，一次该行的cp+sha256变异，不跑全量/真机。
- 执行记录：053U 子代理自报约48步/30分钟，超过35步/25分钟预算，未扩任务范围；本复验
  新派一个显式 `opencode go/deepseek-v4.1-flash` 小批，最多8步/8分钟，不做额外套件或真机。

## 8. 053AD：回归修正与最终集成状态

- **兼容裁决**：053W 的5单位净距只在显式 `textPlacement=native-attr` 时进入
  `readability.check()`；不写该键的旧计划/调用序/判定不变。`_check_flag_body_on_wire`
  仍可被专项审计直接调用。第一次全量的97 failed/13 errors主要来自该无条件启用，
  修正后225项指定回归通过（仅093旧结构钉另修），negative control与变异证据在`evidence/534ad/`。
- **公开合同**：`contracts/cli/v1.json` 已由`.venv/Scripts/python.exe -m tools.cli_contract --write`
  重建，新增 `sch.list_attributes`（read）与 `sch.move_attribute`（write，位姿/可选可见性）。
  无任意JavaScript执行入口，page/parent/id/expectedKey/expectedValue与回读是写前必需。
  540c+093共81项通过，旧render打印函数不被误当成实际门禁。
- **两消费者证据**：旧edit/review计划无新字段/新动作，draw-module无moves保持原调用；
  native的新draw计划才产生ATTR动作。P24/P25验证reference/value/net移动，P21验证隐藏后
  可见名减少而netlist不变，P29验证完整CH343落地。未覆盖V3真机、多板、CBB和三种容器格式，
  不得写成这些维度已完成兼容。
- **真机交付**：P29=`6625ff26bf59d14c`，lint 0E/0W/0I、全工程DRC通过、独立58/58，
  模板证据`evidence/534ab/`，清后证据`evidence/534ac/`。P20–P28由用户既定“新页删旧页”
  授权清理，Board2 P1不变。持久化未关闭重开验证，不能据此发版或宣称真实工程已交付。
- **最终复验**：全量pytest **9213 passed / 25 skipped / 2 failed**，只有既有的pytest槽位ACL与
  MSYS POSIX安装器权限两条环境红，第一次的97+13回归全部消除，未跑第三轮。
  connector **576 passed**+typecheck；dsh-plugin **127 passed / 1 skipped**+typecheck/build+
  draw smoke；Rust **111 passed / 4 ignored**（fmt/clippy/test）；doc-claims **33 passed**。
  这些读数不替代P29视觉验收，也不把未覆盖维度写成兼容完成；本任务没有commit/add/push。

## 9. 543N：persistence 自动网名重编号（集成小批）

### 公开合同与回退

- `core.compare.reconcile_names` 复用既有 membership 匹配与防合并逻辑，新增默认关闭的
  `auto_only` 过滤；只接受**源名与目标名都满足 `core.netdomains.is_auto_net`** 的改名。
  通用 compare/calibration 缺省行为不变，不修改 `compare_models` 的严格网名合同。
- `cli._compare_persistence` 在调用 `compare_models` 前，以 golden=baseline 对 reopened 做
  `reconcile_names(..., auto_only=True)`。自动编号可以变，成员分区不能变；用户命名网改名、
  命名↔自动、拆网、并网、丢脚、改脚仍失败。回退是去掉该调用，缺省 reconcile 不变。
- 真实基线：P38 重开前后 11 器件不变，四个 `$19N…`→`$1N…` 自动网的成员集合逐一相同，
  所有用户命名网相同，几何没有缺失；证据 `evidence/543n/`。不把这次误报写成丢图，也不
  在未修比较器前写 `saved_verified`。

### 兼容矩阵与 negative control

| 维度 | 本批覆盖 | 必须不变 / 不得声称 |
|---|---|---|
| V4 在线 | `test V4` P38 已关闭重开后的真实 netlist/geometry | Board2 P1、ROBOT 不写；P38 分区一致才可验收 |
| V3 在线 | **未覆盖** | 不把 V4 读数写成 V3 宿主兼容 |
| 离线比较 | persistence 与既有 compare/calibration 测试 | 缺省 reconcile、Finding/verdict、CLI 旧退出码不变 |
| `.epro2/.eprj2/.eprj3` | 仅在线 EasyEDA netlist 文本；容器 parser 未改，**未覆盖** | 不声称三种容器持久化兼容完成 |
| 单/多板 | 单工程单页；多板**未覆盖** | 重复 PCB 双审、分歧库串板不在本批改变或宣称验证 |
| 普通器件/CBB | 11 个普通器件；CBB **未覆盖** | 不声称 CBB 持久化语义已支持 |
| 自动→自动且分区相同 | 允许，返回 `saved_verified` | 必须披露这是成员归并，不是网名稳定 |
| 命名网变化 / 命名↔自动 | 拒绝 | 同成员集合也不许冒充名字未变 |
| 自动网拆并、脚移动/丢失 | 拒绝 | negative control 必须红，不得用自动名豁免真实电气差异 |

实施文件域限 `core/compare.py`、`cli.py`、`tests/test_persistence.py` 与必要的
compare 邻域测试。至少两处变异、owner/layer 守卫、两个消费者证据；全量与真机串行。
