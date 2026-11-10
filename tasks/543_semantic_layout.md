# 543：拓扑角色驱动的构造式原理图布局

> 2026-11-03 岳批准方向并明确：解释器暂时做不好的地方，agent 发现后可以手动微调。
> 本任务把**自动布局**与**受控人工微调**分开验收，不把微调后的页面冒称全自动结果。

## 0. 目标与边界

目标是从 CircuitSpec、PresentationSpec、SymbolProfile 和页面尺寸出发，不读取参考页坐标，
让 CH343 USB-UART 自动布局达到 P29 的三关水平，再逐步泛化到相似拓扑。P29
`6625ff26bf59d14c` 是参考质量基准，不是自动布局成果；Board2 P1
`30560d9c0a52a6d2` 仍是用户参考页，不能改写。

路线不是继续调桩长，也不是另起纯 CP-SAT / 加权全局优化器。仓库已有失败实证：
`docs/drawing-brief-v2.md` §3 记录了关系全过仍画不出、软文字权重被淹没、布线阶段协商退化。
本任务采用**拓扑角色识别 → 服务关系 → 构造式落位 → 文字/旗标/通道硬预留 → 局部正交布线**。

**分岛分工（岳 2026-11-03 裁定）**：功能分岛、合岛、核心器件与主信号流由 agent 根据电路语义决定，
写入显式 PresentationSpec 并说明理由；解释器不自动做语义分岛，只消费这份意图完成几何布局、
布线、文字避让与连通校验。agent 的分岛声明属于语义输入，不算手动修改几何；对应结果记为
**“agent 分岛 + 解释器自动布局”**。只有 agent 后续改器件/导线/文字坐标或可见性，才记
`agent-adjusted`。543B 的 C3/C4 合岛正是主代理在临时规格中所做，不是解释器自动分岛。

非目标：

- 不把 `.tmp_534ab/build_reference_plan.py` 直接改名为通用解释器；它仍是 534 的一次性模板证据。
- 不在自动编译时读取 `evidence/534aa`、P29 或 Board2 P1 的坐标、source、attributes。
- 不用 `set_document_source`、原图元 ID 复制或任意 JavaScript 执行代替正常 plan/apply。
- 不承诺任意原理图、多板、CBB、V3 真机或三种工程容器均已支持。
- 不动其他 agent 的 `package.json`、`cases/`，不清理 534 未提交工作，不做任何 git 写。

## 1. 三种结果必须分开记账

| 结果 | 允许的依据 | 报告口径 |
| --- | --- | --- |
| 自动布局 | 仅电路、画法规格、符号库、页面约束；生产编译器生成全部几何 | `automatic`；必须保存编译输入、plan 和未经人工修改的渲染 |
| 参考模板重放 | 显式参考页及其拓扑映射 | `reference-replay`；不得称自动布局 |
| agent 微调 | 自动或模板候选之后，由 agent 做受控局部修改 | `agent-adjusted`；保存调整前候选、逐条修改、调整后证据 |

agent 微调是合法兜底，但不能用来关闭“解释器自动生成能力”的缺口。微调只能走正常
plan/apply、ATTR 移动/可见性等受守卫接口；调整前后均须核连通，不能靠隐藏错误通过视觉验收。

## 2. 分批路线

每一批开工前只扩写本任务对应小节，遵守“一缺口、一文件域、一完成条件”。算法与迁移不同批，
shared/CLI/bridge 改动另走 `tasks/shared-platform.md` 集成锁；新规格键缺省必须保持旧行为。

### 543A：去耦服务关系图与自动基线（当前批）

建立一个纯函数、draw-owned 的只读分析层，回答“哪个两脚 shunt 器件服务哪个宿主及哪个网络”。
第一批只覆盖去耦服务关系，不同时做 USB/CC、LED、布线或页面摆放，也不把分析接进生产编译。
保留当前 CH343 自动编译结果作为后续对照。

完成条件：

- 对 CH343，C3 的服务关系必须指向 U1 的 V3 / pin 4；C4 必须指向 U1 的 VCC / pin 15。
- C1/C2 可定位到 usb_c 的核心 USB1 和 +5V 网；若同一宿主有多个等价供电脚，保留候选集合，
  不按脚号排序挑一个冒充唯一答案。
- 识别依据是器件类别、模块核心、attach 关系和网表连接，不允许生产代码写死
  `U1/C3/C4/V3/VCC` 等字面量，不依赖 refdes 编号推断服务关系。
- 有多个同等优先级宿主时必须返回歧义及原因，不许猜测；非电容两脚件不得被当成去耦。
- 器件分类只准复用现有 shared 公共合同；若必须修改 shared 才能继续，停下交回缺口，
  不得在 draw 复制 review 的分类/电气规则。
- 新分析层不被旧编译路径调用；同一 CH343 输入在新旧代码下的自动编译结果字节一致。
- 保存当前自动基线：`ok`、候选/拒绝数、hard violations、产物 hash 和实际命令。
  基线不许读取参考页，也不许把 534 的 P29 计划当成当前自动编译输出。

建议文件域：新增 `src/boardwise/engines/layoutroles.py`，在
`contracts/module-owners.json` 登记为 draw；新增 `tests/test_543_layout_roles.py`。
若发现已有同职责公共实现，优先复用并报告，不再造一份。除上述文件和证据外不改生产代码。

测试与变异：

```bash
.venv/Scripts/python.exe -m pytest tests/test_543_layout_roles.py tests/test_owner_rules.py -q --basetemp=.tmp_pt_543a
```

至少两处独立变异：①宿主优先级被颠倒时测试必须红；②歧义拒绝被改成首项时测试必须红。
每次先 `cp` 备份，还原后 sha256 与备份前一致；禁止 `git checkout/restore`。不跑全量，不起 daemon，
不做真机写。证据 `evidence/543a/`，临时 `.tmp_543a/`。一个 coder，显式
`opencode go/deepseek-v4.1-flash`，最多 40 步或 30 分钟，不再派下级 agent；交回不超过 2000 字，
列文件、实际测试计数、基线、变异 hash、未覆盖项。

#### 543A 主代理复验（通过）

- 亲读 `layoutroles.py`、测试与关键 diff；主代理复跑为 **26 passed**。生产分析层未接入 compiler，
  未写死 CH343 位号/网名，未改 shared 电气判断。
- 主代理独立变异两处：`min(best_level)` 改为 `max` → **5 failed / 6 passed**；清空
  `host_pins` → **4 failed / 7 passed**。每次均以 cp 备份恢复，恢复 sha256 均为
  `4c561cde88b6f1327d88bf29d5ae3e0ed6a8a678c6dbb90e87c436b1475facf7`，最终 **26 passed**。
- 已亲看 `evidence/543a/cand1_browser.png`：当前自动候选虽有 `ok=True`，仍有 CH343 左侧网名挤叠、
  V3 回绕、USB/CC 长绕线；基线不能当作视觉达标。复验记录 `evidence/543a/review.md`。

### 543B：服务关系进入构造式落位（先做无坐标合岛探针）

只消费已验证的服务关系，让去耦相对其宿主供电脚构造落位；位姿和间距由符号几何及文字盒推出，
不写参考绝对坐标。必须先证明未启用新路径的旧规格字节不变。完成条件是同一 CH343 自动候选中
C3/C4 的服务侧、方向和净距正确，且不比基线增加硬违反；不是仅把 `attach.gap` 改小。

先用临时 PresentationSpec 把 C3/C4 声明进 `ch343` 核心模块、移除独立 `caps` 与所有 userLocks，
不改生产代码运行自动 compile。现有 `ic-periphery` 已声明 shunt 贴自己的核心脚；若该声明式分岛
即可满足服务关系，就不重写算法，只记录可复用能力与剩余缺口。若仍失败，按实际拒因另写窄实施批，
任何新行为都需显式 opt-in，旧 v42 输入的字节结果不得改变。

#### 543B 探针读数与实施批

- 探针输入 `evidence/543b/merged_no_locks.presentation.json`：C3/C4 并入 ch343，无 caps、无 attach、
  无 userLocks，未读参考页。自动 compile **4 candidates / 0 rejected / 0 hard violations**。
- `evidence/543b/service_geometry.json` 实测：C3.1 `(415,730)` → U1.4 `(475,730)`，一条 V3 水平线；
  C4.1 `(625,750)` ← U1.15 `(565,750)`，一条 VCC 水平线。服务脚和位姿已经正确，
  **不需要重写现有 ic-periphery 的贴脚能力**；两段 Manhattan 距离均为 **60**，超过 S-05 目标 30。
- 主代理已亲看 `merged_cand1_browser.png` 与 `ch343_crop.png`。UART 标签挤叠、D− 竖排等
  后续缺口仍在；本批不宣称整页视觉通过。

实施只解决“唯一服务脚的 shunt 距离 60 → ≤30”这一缺口。优先复用现有声明/档位；若没有控制口，
新增顶层可选 `serviceLayout: {"pinGap": 30}`。`pinGap` 必须有限、为正数；缺省不序列化，
旧行为与 digest 不变。它只消费 543A 的**已解析且宿主脚唯一**的服务关系；歧义、多宿主、多等价脚
不许猜测或套用到其他器件。新路径是构造/档位选择，不是参考坐标，也不是软评分权重。

完成条件：以无 userLocks 的合岛规格显式开启后，C3/C4 各自与 U1 的服务脚保持一行或一列、
一条非零正交直连线，`0 < Manhattan ≤ 30`，整页 `ok=True` 且零硬违反；不能靠隐藏文字、
删除 lint、容忍新违反或 agent 手改 plan 达成。旧 v42 再编译的 SVG/page 产物须与 543A 基线逐字节一致。
若不满足，交回具体占位冲突与零写证据，不放宽门禁。

文件域限 `core/presentationspec.py`（仅确需新键时）、实际负责 shunt 构造的 draw 引擎文件、
`docs/draw.md` 对应合同段、新增 `tests/test_543b_service_layout.py` 与证据 `evidence/543b/`。
不得顺手改 UART/USB 路由、shared、CLI/bridge、package.json、cases 或既有夹具。跑新测试、
`tests/test_543_layout_roles.py`、`tests/test_098_ic_periphery.py`、owner/layer 邻域及 v42 字节对照；
两处独立变异（pinGap 真被消费、缺省旧行为不能被开启）必须红后 cp+sha256 恢复。一个 coder，
显式 `opencode go/deepseek-v4.1-flash`，最多 40 步/30 分钟；不跑全量、不起 daemon、不派下级 agent、
零 git 写/零 rm。交回≤2000字，含真实几何、测试计数、hash、未覆盖项。

#### 543B 主代理复验：机制通过，CH343 目标未关闭

- 亲读 ServiceLayout、`_service_pin_gap`、page slice 与测试；主代理复跑 543B+543A+098
  **80 passed**。v42 的 cand1..4 SVG/page 与 543A 基线逐字节一致，缺省确实惰性。
- 合成电路的 30 单位直连成立，但 CH343 `pinGap=30` 主代理独立复跑仍为 **exit 5 / 0 candidate**，
  原话是 D+ 名字盒被 GND run 穿过；没有把机制绿读数写成 CH343 验收通过。
- 岳已裁定分岛由 agent 负责：本任务的合岛是语义输入，不研发自动语义分岛；解释器只需修复
  自己消费该意图后的几何缺口。

### 543C：文字、旗标和局部走线通道硬预留（当前批）

在落位完成前把真实器件文字、符号脚号/脚名、旗标及局部短网通道纳入占用几何。
硬预留先于评分，不重复 201C/201D 的布线后补救和软权重路线。compile 与 plan 必须共用几何判断；
模型与宿主有差异时保留实测标定，不擅自加网名例外。

本批只处理 543B 阻断的 **serviceLayout=30 时 CH343 核心岛的标签列/GND 回程冲突**。
以 `.tmp_543b/gap30.presentation.json` 的等价输入为基线（agent 分岛、无 userLocks），
让标签名字盒与 GND 旗标/回程通道在布线前成为硬占用；可复用现有 Router blocked/reserved、
旗标席位与文字盒，不新增软权重，不改 UART/USB 的其他布局决策，不另加规格键。
新逻辑只能随显式 `serviceLayout` 启用，未写该键的旧编译结果不变。

完成条件：自动 compile 至少一个 `ok=True` 候选，C3/C4 服务连接均 `0<Manhattan≤30`、
一条非零正交直连线，整页零硬违反；D+/D− 和其他标签名字盒不得被 GND 导体穿过。
保存候选 plan/SVG 与逐脚连通证据，不以隐藏文字、删 lint、放大 pinGap 或手改 plan 通过。
旧 v42 SVG/page 继续逐字节一致。若仍无解，交回具体占用矩形与零写证据，不扩到别的岛。

文件域限实际负责标签/旗标/GND 通道的 draw 引擎文件、新增 `tests/test_543c_service_channels.py`
与证据 `evidence/543c/`；不改 shared、CLI/bridge、其他规格、package.json、cases 或既有夹具。
跑新测试、543A/543B/098、owner/layer 邻域与 v42 字节对照；两处独立变异
（通道预留确实生效、缺省不启用）红后 cp+sha256 恢复。一个 coder，显式
`opencode go/deepseek-v4.1-flash`，最多 40 步/30 分钟，不跑全量、不起 daemon、不派下级 agent、
零 git 写/零 rm。交回≤2000字，含几何、测试计数、hash、未覆盖项。

#### 543C 主代理复验（通过，视觉软项转入 543D）

- 主代理复跑 543C+543B+543A+098+owner/layer **111 passed**；独立 compile exit 0，
  4/4 SVG/page 与子代理产物逐字节一致，v42 旧产物也逐字节一致。
- 独立关闭 `_service_channels` → **5 failed / 2 passed**，cp 恢复 sha256
  `d1ac20cf05b679a3fca669f84edf3809197879ef3e8fe868cbf540509ca2ddf2`，随后 **7 passed**。
- 亲看 `cand1_browser.png` 与 `ch343_crop.png`：V3 回绕消失、C3/C4 服务线均为 30、
  GND 不穿标签；UART 名字列仍拥挤、C4 周边旗标偏挤，故只关闭本批硬缺口，不称整页视觉完成。

### 543D：成对信号与标签排版（当前批）

先覆盖 D+/D−：成对通道、相邻顺序、同一连通导线恰一枚可见名字，短网直连/长网断名；
同时处理 UART 标签列。USB/CC 的导体回环另批，不在本批顺手改。连通、零碰撞优先于线长；
交叉、回环、文字冲突不能靠隐藏 lint。

先用 543C 的生产能力做**声明式探针**：agent 可在临时规格中显式选择
`textPlacement: native-attr`、`labelPolicy.stub: straight`，并用模块自己的
`presentation.sidePreferences` 让 USB 的 D+/D− 向右、CH343 的 D+/D− 向左。
这些是分岛/阅读方向/文字模式意图，不是坐标微调。必须用离线 `drawapply.module_plan`
检查最终 ChangePlan 的承载线、直桩与 ATTR 目标盒，不能只看模块 SVG 就宣称宿主文字问题解决。

若现有声明已足够，不加生产算法，只把有效规格与回归测试固化；若仍有缺口，只改一个标签分配点，
且必须沿用 native/service 的显式 opt-in，缺省旧行为不变。完成条件：至少一个自动候选
`ok=True`、543C 的两个 30 单位服务连接不退化、整页零硬违反；UART 名字全部水平且互不重叠，
D+/D− 在 USB 与 CH343 两端隔空相对，每模块视图每网只显示一枚；保留逐脚连通。
不把 `native-hidden` 当成删除网络或掩盖异名重叠。若需改代码，两处独立变异必须红后恢复；
若纯声明成功，去掉 native/方向声明的 negative control 必须证明对应断言会失败。

文件域限必要的单一 draw 标签引擎文件、新增 `tests/test_543d_label_layout.py`、
有效规格与证据 `evidence/543d/`；不改 USB/CC 导体路由、shared、CLI/bridge、package.json、
cases 或既有夹具。跑新测试、543A/B/C、534J/534T/534V/534X/534Z 邻域和 v42 字节对照。
一个 coder，显式 `opencode go/deepseek-v4.1-flash`，最多 40 步/30 分钟；不跑全量、不起 daemon、
不派下级 agent、零 git 写/零 rm。交回≤2000字，区分“纯声明”与“算法改动”，附最终桩/文字盒、
测试计数、negative control/变异和未覆盖项。

#### 543D 主代理视觉退回与续单

主代理复跑 **231 passed**、独立 compile 与 v42 字节对照均一致，但亲看
`evidence/543d/cand1_browser.png` / `usb_crop.png` 后发现**不能验收**：USB D+ 可见盒中心
x=185 而 A6 引脚 x=205，仍在引脚左侧；CH343 的名字也在自己引脚左侧，两端仍同向。
原测试只比较岛框与名字盒顺序，漏掉“相对自己引脚的方向”，因此 231 绿不关闭本批。

续单先补硬断言：USB 的 D+/D− 可见名字盒中心必须位于其 A6/A7 服务引脚的**右侧**，
CH343 的对应名字盒中心必须位于 U1.5/U1.6 的**左侧**，且最终 ChangePlan 的直桩与 ATTR 目标
与该方向一致。不能只改 visible keeper 或把盒子塞在岛框边缘冒充相对。允许编译器选择不同的
核心符号位姿，但禁止 userLocks/手改坐标/手改导体；所有几何须由编译器重新生成并保持
543C 的 30 单位服务连接、零硬违反和逐脚连通。USB/CC 的其他拓扑决策不主动改，位姿引起的
全岛几何必须重新验收。缺省旧行为与 v42 字节仍不变。续单最多 30 步/25 分钟，仍由
`opencode go/deepseek-v4.1-flash` 的同一 coder 执行；先让新增方向断言在当前候选上变红，
再实施最小修复，交回前后图片、ChangePlan 和测试，不扩展到真机。

#### 543D 续单结果与 543D-2：USB/CC 岛级重排（当前批）

续单已让方向两项在当前候选真实变红，主代理独立复跑 **2 failed / 9 passed**。
位姿补丁试验得到 0 候选：右向位姿 `0+mirror` / `180` 同时翻转 CC 支路，R1 的 GND 旗标
无 lead，其他档又倒在 D+/D− 名字盒/lane。补丁已恢复，生产 `drawcompiler.py` sha256 回到
`7d697a3f…`，没有把失败实验留在代码里；红断言保留，不修改验收迎合现状。

本批授权进入 **USB/CC 岛级重排**，这是上述阻挡的直接后续，不再限制“不能动 CC”。
先用 agent 的语义分岛能力尝试把 R1/R2 拆成独立 CC 模块，让连接器翻转不再拖着 CC 支路；
可使用现有 modules/flow/attach/mainPath 等声明，但禁止 userLocks、参考坐标和伪造符号位姿。
若纯分岛不足，恢复并收窄已有 `_label_side_pose_ok` 位姿约束，只修必要的 CC 支路/旗标/
标签通道。新行为仍只随 native+service 的显式声明启用，旧 v42 字节不变。

完成条件：543D 的两条方向红测试转为通过，其余 9 条不退化；USB D+/D− 名字与直桩在
A6/A7 右侧，CH343 在 U1.5/U1.6 左侧，ATTR 目标一致；543C 两个 30 服务连接、UART 水平不重叠、
每模块每网一枚可见名和 55 脚连通全部保持，整页零硬违反。若拆分 CC，须证明 CC1/CC2
仍按规格连接，不能用删线/加名遮蔽断路。保存 agent 分岛后的有效规格、plan/ChangePlan、
前后 SVG 和测试。缺省旧行为及 v42 字节不变。

文件域限 drawcompiler/pagecompiler 中实际承担位姿或 CC 通道的最小文件集合、
`tests/test_543d_label_layout.py`、新增 `tests/test_543d2_usb_pair.py`、有效规格与
`evidence/543d2/`。不改 shared、CLI/bridge、package.json、cases、任务书或既有夹具。
跑新旧聚焦集与 v42 字节对照，两处独立变异红后 cp+sha256 恢复。一个 coder，显式
`opencode go/deepseek-v4.1-flash`，最多 40 步/30 分钟；不跑全量、不起 daemon、不派下级 agent、
零 git 写/零 rm。交回≤2000字，区分 agent 分岛与算法改动，附方向几何、测试、hash 和未覆盖项。

#### 543D-2 主代理复验与测试盲区收尾

- 主代理复跑 **235 passed**，独立 compile 三候选 SVG/page 与证据逐字节一致，v42 亦一致。
  已亲看 `after_cand1_browser.png`、`usb_crop.png`、`ch343_crop.png`：USB 数据名在连接器右侧，
  CH343 在左侧，CC 小岛清楚，方向缺陷关闭；预览仍显示 native-hidden 文字，最终重复名须以
  ChangePlan 与真机回读为准，不能拿 SVG 当宿主 ATTR 证据。
- 主代理把 `_pose_satisfies` 中 `_label_side_pose_ok` 调用改成 `if False`，两条方向测试仍
  **2 passed**：CC 分岛后编译器自然也会选对位姿，说明整页测试没有钉住这个新增守卫本身。
  已按 cp 恢复 `fb1f81cc…` 并复跑回绿。这不是证明函数错误，而是证明它的直接测试缺失。
- 收尾小批：coder 必须给 `_label_side_pose_ok` 增加直接正/反单元测试，证明错误位姿被拒、
  正确位姿被接受且缺省不启用；若论证它在最终路径完全多余，也可移除函数与调用，但不得仅凭
  “现在碰巧会选对”就保留无测试代码。另修正 `_native_label_visibility` 返回 note 仍写
  “farthest from its pin”的旧文案，明确声明侧候选采用最近者。最多 12 步/12 分钟，
  不扩其他行为；跑原 235 项与一次直接变异，证据并入 `evidence/543d2/`。

#### 543D-2 收尾复验结论

直接守卫测试已补齐，主代理复跑单文件 **8 passed**；保留 `_label_side_pose_ok`，其左向拒绝、
镜像接受、缺省关闭都有直接断言。keeper note 已改为“声明侧候选取最近者，否则走 053V 最远者”。
543D 与 543D-2 至此完成离线验收；真机 ATTR 与 hidden 仍属 543F，不提前宣称。

### 543E：同拓扑自动基准与扰动（当前批）

- 同一 CH343 输入：自动 `ok=True`，离线几何无硬违反，产物可复现。
- 小扰动：更换排针文字长度、增删一只去耦、改变符号引脚节距；不得退回到人工绝对坐标。
- 对照 P29 检查关键关系，不要求逐像素相等；三关仍须分别验证。
- 自动候选与 agent 微调候选分别保存，报告不得混写。

本批以 `evidence/543d2/effective.presentation.json` 为固定 agent 分岛基线，先做测试，不预设有
生产缺陷。新增 `tests/test_543e_perturbations.py` 和 `evidence/543e/`：
1. 把 H1 的短值换成真实长型号 `PZ254V-22-10-A60-3000`，长文字不得与地线/其他文字相交；
2. 从电路副本删除 C4，再另加一只接到 U1.15/VCC 与 GND 的同类去耦（增、删分别验证），
   规格成员与逐脚检查同步，不能用旧 55 脚数硬套变体；服务关系仍是唯一宿主脚时才许 pinGap 生效；
3. 在内存副本中改变 CH343 引脚节距并同步符号外框，不修改既有 library 夹具，验证标签仍能
   水平排布且页面无硬违反。

每个变体都必须无 userLocks、自动 compile `ok=True`、零硬违反、逐脚连通，未删除的 C3/C4
保持 30 单位直连、D+/D− 方向保持。若某一变体当前不支持，保存真实拒因并标未覆盖，不能删测试、
放宽闸或改坐标凑过。基线重复编译须与 543D-2 产物逐字节一致。发现生产缺陷时先交窄证据，
不把修复和三类扰动混成一大批。跑新测试与 543D/D-2/A/B/C 邻域；测试/negative control 本身
须证明会变体失效时能检出。一个 coder，显式 `opencode go/deepseek-v4.1-flash`，最多 30 步/
25 分钟；不跑全量、不起 daemon、不派下级 agent、零 git 写/零 rm。交回每项实际读数与未覆盖项。

#### 543E 主代理复验与 543E-2：重复去耦同址（当前批）

主代理复跑 **246 passed / 1 xfailed**，确认 add-C5 的全部三候选都有 C4/C5 同 origin 且 hard=0；
这不是可交付候选。其他扰动（长 H1、删 C4、双倍节距）与基线字节复现已通过。

本批只修这个缺陷。优先让后续同服务脚 shunt 在宿主脚的正交方向寻找同一 `pinGap` 的合法座位：
基线的水平服务线不变；新增电容可以在同一行**或同一列**，与原任务书一致，不能靠放宽到 >30、
隐藏器件或删检查来避开。若正交座位也无解，编译器必须 `layout-unsat` 并点名同址服务脚，
**不得返回重叠但 ok=True**。不得把“拒不出图”当成变体自动布局成功；那种结果只记未覆盖。

完成条件：add-C5 不再出现同 origin；若能出图，C4/C5 均 30、正交直连、不同 origin、零硬违反、
逐脚连通，原 strict xfail 应转正常通过；若物理阻挡无解，测试改为明确拒绝并保留未覆盖说明。
543D-2 基线、长 H1、删 C4、双倍节距与旧 v42 全部保持。两处独立变异证明同址检测/正交分配有效。
文件域限实际 shunt 构造/门禁的 draw 文件、`tests/test_543e_perturbations.py`、必要的
`tests/test_543e2_service_siblings.py`、`evidence/543e2/`；不改 shared、CLI/bridge、package.json、
cases 或既有 fixtures。一个 coder，显式 `opencode go/deepseek-v4.1-flash`，最多 35 步/30 分钟，
不跑全量/真机、不派下级 agent、零 git 写/零 rm。交回几何/拒因、测试计数、hash 和未覆盖项。

#### 543E-2 主代理复验结论

主代理复跑 **250 passed**，无 xfail；add-C5 为点名 U1.15 的 `layout-unsat`，不再产生同址假 pass。
独立重编译 543D-2 基线与 v42，全部 SVG/page 逐字节一致。第二只同脚去耦因当前符号邻脚阻挡
仍未覆盖；不扩任务，不影响无 C5 基线进入真机。

### 543F：真机垂直验收（当前批）

真机只写任务书逐字点名的 **`test V4`** 新空页；沿用 `BOARDWISE_HOME=E:/boardwise/.tmp_534q/home`
和 `BOARDWISE_WRITE_PROJECTS='test,test2,test V4'`。先 R1 核对焦点工程名逐字一致、
Board1 P29 `6625ff26bf59d14c` 与 Board2 P1 `30560d9c0a52a6d2` 的特征；目标缺失即停，
其他窗口/真实工程不写。实例 ID 以新读数为准，不沿用旧值。

输入固定为 `blocklib/specs/ch343_uart_534a.circuit.json`、
`evidence/543d2/effective.presentation.json`、`blocklib/specs/ch343_uart_v4.library.json`，
candidate 0，无 userLocks。只新建 **P30** 并取其新 UUID，plan 绑定该空页与
`--page-box 0,0,1170,825`，再 apply。第一轮不做 agent 微调；plan/apply 失败就保存证据并停止，
不改代码、不换旧页叠加写、不用 draw discard、不删任何页面。P29 与 Board2 P1 始终不动。

证据落 `evidence/543f/`：doc.list/R1、plan/report、apply、宿主 PNG/SVG、draw lint、全工程 DRC、
netlist、ATTR 与独立逐脚。必须证明 55 个连接脚与 3 个 NC，可见网名与隐藏 ATTR 一致，
C3/C4 服务线为 30，USB/CH343 的 D+/D− 方向正确。缺一项不算通过。
主代理随后独立复跑 lint/DRC/逐脚并亲看渲染；只有主代理三关通过后才按岳既定“新页删旧页”
授权清理 P29。若失败，由主代理清理本批新建的 P30，保留 P29。任何其他页面都不删。

一个**新 coder**，显式 `opencode go/deepseek-v4.1-flash`，最多 40 步/30 分钟，不派下级 agent、
不跑全量、零 git 写/零 rm。子代理收工停 daemon 并交回实际页面 UUID、命令、读数、证据和未覆盖项；
不得把 apply exit 0 当成三关通过。页面持久化未重开验证必须披露。

#### 543F 第一轮结果与 543F-2：最终 ChangePlan 的页面边界（当前批）

P30=`cc334404179f440c` 已落地但未通过：逐脚 **58/58**、两个 30 服务线和 D 方向正确，
然而 CC1 的最终 ChangePlan 导线为 `(35,440)→(-5,440)`，宿主 lint **1E**、
DRC `OBJECTOUTSIDESHEET` / `passed=false`。主代理已亲看 `evidence/543f/host_p30.png`，
P29 与参考页不动，不替换交付页。离线 LayoutPlan 没有这根桩，说明只验 LayoutPlan 的图幅不够。

本批先用 `drawapply.module_plan` 的最终 ChangePlan 复现越界并加红测试，再修 native 标签桩
方向选择或页级空间预留，使最终导线/文字均在 pageBox 内。不得手工把 P30 的线挪回去，
不得只在 apply 前加拒绝而不修生成器；修复后同一输入的 ChangePlan 应自行合法。
保持 C3/C4=30、D 方向、CC1/CC2 连通、UART/native-hidden 与旧 v42 字节；两处变异证明
边界检查/新桩选择有效。测试至少覆盖最终 ChangePlan 的所有 wire 端点和 pageBox，不能只查 SVG。

离线修复后只新建 **P31** 做同一套真机验收，证据 `evidence/543f2/`。P30/P29/参考页均不写；
若再失败，不新建 P32，交回证据。文件域限实际标签桩/页面边界实现、
`tests/test_543f2_changeplan_bounds.py`、证据；不改 shared、CLI/bridge、package.json、cases 或旧证据。
真机纪律同 543F，子代理最多 40 步/30 分钟，收工停 daemon，交回新 UUID、三关读数与未覆盖项。
主代理最终统一决定 P29/P30/P31 的清理，子代理不删页。

#### 543F-2 结果与 2026-11-03 暂停状态

- 离线先复现 CC1 `(35,440)→(-5,440)`，随后为 `drawapply.module_plan` 增加可选
  `page_box`，`draw plan` 传入实际页框。候选桩逐段检查边界，越界即换档，无候选则按名拒绝；
  未传 `page_box` 的调用保持旧行为。边界专项与 543B/C/D/D-2/E/E2 合计 **53 passed**，
  旧 v42 的 SVG/page 逐字节一致。
- 真机 P31=`add2db5ffcc5799b`：11 器件落地，`draw lint` **0E/0W/0I**，独立逐脚
  **55/55 连接 + 3/3 NC = 58/58**；C3/C4 均 30，USB/CH343 的 D+/D− 方向正确，
  隐藏两枚同网重复名。证据 `evidence/543f2/`。
- **仍未通过最终验收**：CC1 改为竖直桩后，宿主名字也竖排，违背 S-20，不能替换 P29。
  全工程 DRC 仍 `passed=false`：包括 P30 遗留的 `OBJECTOUTSIDESHEET`，以及各页共有的
  3 个规格内 NC 和电阻库属性告警。P31 自身没有越界项。
- 岳要求暂停时，Board1 同时存在 P29=`6625ff26bf59d14c`、P30=`cc334404179f440c`、
  P31=`add2db5ffcc5799b`；Board2 P1=`30560d9c0a52a6d2` 未改。没有删页，没有 P32，
  daemon 已停且 61190 无监听，所有源码/文档改动尚未提交。
- 下一步最小动作：让 native 标签桩在页框内选择水平承载线并验证宿主 CC1 水平，
  再做主代理三关、清理实验页和最终全量。当前不能宣称 CH343 自动布局总目标完成。
- 随后岳要求先更新文档并提交当前工作；提交只覆盖 534/543 相关文件，其他 agent 的
  `package.json`、`dsh-plugin/package.json`、`dsh-plugin/README.md`、`cases/`、
  `tasks/review-test-plan.md` 不纳入。

#### 提交前复验记录

- 第一次全量：**9273 passed / 25 skipped / 6 failed**（828.95s）。两条为既有环境红：
  `test_193_process_guards` 槽位 ACL 与 `test_193_secrecy_hooks` POSIX 安装器。
  四条真实回归为：`page_box` 无条件下传破坏旧 monkeypatch，以及 540 draw/shared/review
  三处 owner 计数仍写 142。
- 修复：`page_box=None` 时不再向 `_place_label_stub` 传该关键字，显式页框才传；三处计数
  同步为 143；新增默认旧签名与显式页框下传两条回归。主代理聚焦复跑 **48 passed**。
  变异令 None 也下传时两条测试变红，cp 恢复后 `drawapply.py` sha256 为
  `f89ca06659eb3ae573d509065153547f1e813482b2d9a8dfc88747466d5f0c48`。
- 第二次全量：**9279 passed / 25 skipped / 2 failed**（847.48s），两条仅为上述既有环境红，
  四条兼容回归全部消除。connector **576 passed** 且 typecheck 通过；dsh-plugin
  **127 passed / 1 skipped** 且 typecheck/build 通过；draw smoke 为 3 candidates/6 artifacts、
  8 pages/16 artifacts；Rust fmt/clippy/test 为 **111 passed / 4 ignored**。
  `test_doc_claims.py` **33 passed**，`tools.cli_contract` 报 `matches production`，
  仓库卫生检查与 `git diff --check` 通过。CC1 竖排、实验页清理和第二拓扑仍是独立未完成项，
  不因提交检查通过而关闭。

### 543G：第二拓扑泛化（另立样本后再派）

使用另一份已授权、可公开留证的相似电路，验证角色识别与构造规则不是 CH343 特判。
没有第二样本前不得宣称通用自动布局完成。

### 543H：skill 引导的 CC 同侧与标签同步修复（当前）

岳 2026-11-04 批准修复完成后再交付。冷启动 skill 验证已把两只 CC 下拉保留在 `usb_c`，
但 30 个候选均出现支路绕体和文字错贴，故未落画布；基线规格与判废证据在
`evidence/543g_skill_trial/`。本批不得退回独立无约束 `cc` 岛，不得用参考坐标或手工微调
掩盖解释器缺口。

- **H1 附属支路同侧**：只修核心符号已镜像/旋转时，二端 shunt 的座位仍按核心局部引脚
  逃逸侧确定，使 CC1/CC2 不再分处连接器两侧后绕体；成对支路须同向、对齐，缺合法座位要
  明确拒绝。生产域限 `drawcompiler.py` 实际落位/位姿代码与新增 `test_543h*` 聚焦测试。
- **H2 标签同步**：只修最终 ChangePlan 桩长/方向与页级 native ATTR 名字盒不一致；最终桩
  改变后名字必须重新贴最终锚点并避让，RXD 不得贴到 C3。生产域限实际生成最终桩或 ATTR
  的文件与新增聚焦测试；不与 H1 同批混改。
- **H3 验收**：沿用 `evidence/543g_skill_trial/spec_v1.json`，离线 compile 与主代理视觉通过
  后才可在 `test V4` 新建 P32 落图；完成 lint、独立逐脚、宿主 DRC 和渲染目检。保留
  P29/P30/P31 与 Board2 P1，不做 git 写。缺省输入与旧 v42 字节/行为不变，最终串行跑规定测试线。

#### 543H-1…H-4 结果

- H1 先修符号系/页面系引脚方向不一致，再在 `native-attr + serviceLayout` 显式路径按
  同角色/同符号/异锚点成组分 lane；R1/R2 同列同姿态，CC1/CC2 各 2 点直连，镜像候选
  同样成立。H2 在最终桩生成后重落可见 native 名字行，RXD 从 C3 旁回到自己的桩；
  hidden 与旧路径不变。H3B 给显式 `partTexts` 增加 6/4/2 收紧档，最终规格只声明
  C1 文字向右，C1/C2 不再与 R1 面对面。未写相应能力的 v42 四候选 page/SVG 逐字节不变。
- 独立审查后的 H5/H6 收尾：符号系关系翻转也统一受同一显式开关控制，反激 119/551a
  三条回归复绿；同 pad 的分组按最大只数累计 lane span，同/异符号均不共址。短桩名字
  必须留在 carrier 行带内，重落后的实际行进入后续 ink 与 duplicate-carrier 记账；
  无合法座位具名拒绝，不写回 LayoutLabel.bbox、不改 layout digest。最终 P32 规格
  page 与已验收候选逐字节一致，证据 `evidence/543h5b/`、`evidence/543h6/`。
- H4 真机页 **P32=`8b33fa321b2f564d`**：自动候选经空页 plan/apply 落地，无 userLocks、
  参考坐标或 agent 几何微调；`draw lint` **0E/0W/0I**，独立几何与宿主网表逐脚
  **55/55 连接 + 3/3 NC**，主代理逐岛目检 `evidence/543h4/render.png` 通过。
  DRC 本页仅 3 个规格 NC 与 3 个电阻库属性 WARN；旧 P30 越界项仍属旧页。
- 最终检查：全量 **9347 passed / 25 skipped / 2 failed**，仅 pytest 槽位 ACL 与 MSYS
  POSIX 安装器两条既有环境红（日志 `evidence/543h4/final_pytest.log`）；connector
  **576 passed** + typecheck，dsh-plugin **129 passed / 1 skipped** + typecheck/build，
  Rust **111 passed / 4 ignored** + fmt/clippy，draw smoke 3 候选/6 产物、8 页/16 产物、
  replay lint 全过，doc-claims **39 passed**，CLI 合同与 `git diff --check` 通过。
  主代理两次独立变异均先红后按 sha256 字节还原。
- 最终规格与证据：`evidence/543h3b/spec_h3b.json`、`evidence/543h1b/`、
  `evidence/543h2/`、`evidence/543h3b/`、`evidence/543h4/`。P29/P30/P31 与 Board2 P1
  未改未删；P32 持久化为 `saved_unverified`，第二拓扑仍未覆盖。工作树未提交。

### 543I：可见连接与旗标策略返修（当前）

岳复审撤回 P32 的交付结论：D+/D− 的 A6/A7 文字脱离 5 单位短桩，B6/B7 隐藏名字后留下
60/55 单位裸线；R10/R11 被距离聚簇共用 GND；C13/C14 的 +5V 因高扇出逐脚放旗而 GND
却聚簇。上述问题证明 lint、宿主网表和此前逐脚脚本不能代替视觉连接审查，P32 不再算通过。

- **I1 可见连接**：每条不连续导线必须有清楚可见、贴着自己载体的名字/去向；隐藏重复名
  不得留下无解释长裸桩，同名不等于同一条连续导线。补离线/真机回归与 lint 或等效机器闸。
- **I2 旗标策略**：GND 与 power 使用同一套“支路语义优先 + 导线终点合法绕行距离”规则；
  成对独立支路默认各自本地旗，不强制共享。不得使用焊盘欧氏距离或线上任意点最近距离，
  不得让 power 高扇出与 gnd 聚簇继续各说一套。无路可绕记不可达，不共簇。
- **I3 审查与重验**：把上述判据纳入 `boardwise-draw`、独立逐脚/视觉检查和测试，先在 P32
  证明会红，再生成新页；主代理逐岛目检，尤其逐段核对可逆脚、成对支路和每一面旗。
  验收前保留旧页；新页三关通过后，按岳 2026-11-04 的明确授权删除旧 P29/P30/P31/P32，
  Board2 P1 用户参考页始终不动。不做 git 写，不用参考坐标或手改图掩盖解释器缺口。

#### 543I-1…I-5 结果

- I1 让每条不连续 native 导线各自可见贴名：A6/A7 载名线延长到 40，B6/B7 不再隐藏，
  `native_carrier_problems` 对旧 P32 报 4 条缺陷，对新 plan 报 0。I2 以 `flaggroups.py`
  统一地/电源分组：shared_net 干线端可候选共簇，other_net 返回端默认本地旗，距离为
  导线终点的 Router 合法正交路径；支路信号走廊先预留，最终 audit 17 次 0 拒。
- I4 真机又修两类问题：native 部件行按宿主实际墨迹参与布线避让，消除 C21 穿线；
  半格旗只在局部尝试相邻整格并重查全部障碍，不移动其它图元。缺省/v42 字节不变。
- I5 独立审查收尾：删除 `BW_D` 调试输出；中间 run 延伸改为插入远点，跨弯/回折/
  斜线具名拒绝；跨末段双轴半格不再硬贴成斜线；最终分组审计增加拒绝反例。
  `tests/test_543i_edge_guards.py` **10 passed**，P34 page/plan 与已验收版逐字节一致。
- 全量后的 I6 收口：严格处理 local-label 载体与轨旗最终座位，恢复 USB 镜像自然顺序和
  v46/v47；旗引线障碍纳入先前旗盒，恢复 C3/C4 各 30 直连。part ATTR 与真实墨迹统一
  使用 `text.bbox` 左下角，骑脚候选在排名阶段拒绝；`flaggroups.py` 已登记 owner=draw。
  LED_A 的规格内直连不再生成多余 T 桩/名字，单 run 脱线也会被 `native_carrier_problems`
  拒绝。最终 **P36=`92d1b55ee5b38511`**：D± 六段 40/60/40/40/55/40 且 D+ 在 D-上；
  CC 直连，R7/R8 各自本地 GND，LED_A 一根直连无多余名；lint **0E/0W/0I**、
  独立逐脚 **55/55 + 3/3 NC**、主代理逐岛目检 `evidence/543i8/apply.png` 通过。
- 岳授权的旧页清理已完成：P29/P30/P31/P32/P33/P34/P35 均 `deleted=true`，Board1
  只剩 P36，Board2 P1=`30560d9c0a52a6d2` 未动。清理后 DRC 只剩 3 个规格 NC 与
  3 个电阻库属性 WARN。持久化 `saved_unverified`，第二拓扑未覆盖，工作树未提交。
  证据 `evidence/543i1/`、`evidence/543i2d/`、`evidence/543i4b/`、`evidence/543i5/`、
  `evidence/543i6*/`、`evidence/543i_led/`、`evidence/543i8/`。最终全量 **9387 passed /
  25 skipped / 2 failed**，仅 pytest 槽位 ACL 与 MSYS POSIX 安装器两条既有环境红
  （`evidence/543i8/final_pytest.log`）；connector **576 passed** + typecheck，
  dsh-plugin **129 passed / 1 skipped** + typecheck/build，Rust **111 passed / 4 ignored**
  + fmt/clippy，draw smoke 3 候选/6 产物、8 页/16 产物、replay lint 全过，
  doc-claims **39 passed**，CLI 合同与 `git diff --check` 通过。

### 543J：并联去耦回流端共旗（当前）

岳在 P36 指出 C9/C10 的 +5V 已合并而 GND 仍各自一面旗。实查不是绕行距离超限：
`_flag_share_keys` 把所有 branch 的 `other_net` 一律写成 `SHARE_ALONE`，GND 两端点
根本没有进入 Router 距离比较；shared_net 端则为 `SHARE_CHAIN`，所以 +5V 能合并。
这是 543I 把“独立支路默认本地旗”过度泛化成“所有支路回流端禁止共旗”，P36 撤回。

- 只给同一 `owner/shared_net/other_net` 的多个 branch 一个结构化并联回流共旗键；
  是否合并仍由导线终点的合法正交绕行距离、reach、全对约束与最终视觉共同决定。
  异信号端的 CC1/CC2 继续各自地旗，V3/VCC 两组去耦也不强行共地。不改距离算法、
  opt-in 路径、PresentationSpec、CLI 或其它几何策略。
- 离线真实 CH343：C1/C2 的 GND pairCost **90≤100**，+5V **100≤100**；R1/R2、
  C3/C4 不共簇；分组 audit **17 次 / 0 拒绝**。主代理聚焦复跑 **43 passed**。
  两个独立变异（共旗键退化、并联数量门槛退化）均使对应测试变红，随后 cp 还原且
  sha256 与原文件一致。子代理在 45 步停止；其合同外审计测试改动仅把具体网名断言
  泛化为“实际被墙切断的网”，主代理审过后保留，无生产文件越域。
- 首轮全量为 **9389 passed / 25 skipped / 3 failed**：除两条既有环境红外，
  `test_543h3b_stated_text_lane` 的 native 页哈希改变。独立对照证明禁用新并联规则后
  native 精确恢复 `8ac928…`，两个非 native 页 `d1fd62…` / `5f0f67…` 均不变；故这是
  有意共地的合同升级，不是旧路径回归。测试更新 native 哈希并分别钉死两个非 native
  全页哈希，子代理聚焦 **21 passed**、主代理原失败用例复跑通过。第二轮全量
  **9390 passed / 25 skipped / 2 failed**，仅剩上述两条既有环境红，未跑第三轮。
- 新页 **P37=`6087631c7d711217`**：11 器件、49 计划导线、19 旗（GND 11/+5V 6/
  VCC 2）。C5/C6 上下分别共用 +5V/GND，R1/R2 各自地旗，D± 和 CC 形态不回退。
  `draw lint` **0E/0W/0I**；宿主网表分区 **55/55 + 3/3 NC**，导线几何独立逐脚
  **55/55 + 3/3 NC、48 岛一致**；主代理全页及 USB/去耦/CH343 局部渲染逐岛目检通过。
  清理后 DRC 只有 3 个电阻库属性 WARN 和 3 个规格 NC（`passed=false` 是 WARN 导致）。
- 旧 P36 已按既定授权删除并有回执；Board1 只有 P37，Board2 只有用户 P1。建页时
  曾因参考页焦点误建 Board2 空页 P2=`79574dac85d0359a`，核对 `primitives=[]`
  后已按本次新建 UUID 撤销，未写电路图元；随后先打开 P36 再在 Board1 建 P37。
- 持久化仍 `saved_unverified`，第二拓扑未覆盖，不做 git 写。证据 `evidence/543j/`；
  最终全量与其它测试线读数见该批 README 和日志。

### 543K/L：成对支路姿态、文字与 D± 联合等长（当前）

岳在 P37 指出两处成对图形不一致：CH343 电容横放而 USB 的 R1/R2 竖放；A6/A7 和
芯片侧虽为 40/40，B6/B7 却是 60/55。实查分别是 branch 沿 other_net 方向转身、
local-label 逐脚独立选档造成，不是电路需要的不对称，P37 撤回。

- **543K 信号型成对二端支路**：只在既有 `_pair_bands`（native-attr + serviceLayout）
  下，针对同 owner/role/symbol、异 shared_net 的两端 signal 支路，且宿主共享脚出脚
  方向统一为水平时，身体沿水平连接摆放。电源去耦不强制旋转，C1/C2 保持竖直，
  CH343 C3/C4 保持横向。bay 由内向外落位，避免 CC 被去耦挤出去后绕线。
- **成对文字同侧**：同结构 pair 共用第一组两边都合法的 `(side,rung)`，显式
  `partTexts` 优先；无共同座位才回旧阶梯。两种 USB connector pose 都在模块编译层
  实际生成并验证 R1/R2 横向、文字同侧、CC 各一条 2 点直连。初审退回的一左一右文字
  与弱化 seen 覆盖已补齐；子代理聚焦 **29 passed**，主代理关键复跑 **8 passed**。
- **543L 联合等长**：恰好两网的 localLabelObligation 才配对；按同 part、同出脚方向、
  相对 body 中心镜像对侧且最近的几何关系配对，不读网名/位号。共同长度同时试两脚、
  两条导体与名字行，第一组两者都合法的档位才落格，伙伴回放同一决定；无共同解即
  具名拒绝。子代理聚焦 **30 passed**，主代理联合/镜像/旗标复跑 **10 passed**。
  主代理另做两处变异：关闭横向规则、关闭联合选档均使测试变红，随后 cp 还原，
  drawcompiler sha256=`661215161388f307df7ead77e3ac5e681c1c0cffa1f73a308dfeb63e59174ae2`。
- 新页 **P38=`0ec4dc022ef38563`**：R7/R8 横向且位号/值都在左，CC 各 130 水平
  直连；D± 为 **40/40、60/60、40/40**，可见贴名。C9/C10 共地、R7/R8 各自地旗、
  USB 去耦竖直与 CH343 电容横向均未回退。11 器件、49 计划导线、19 旗；
  `draw lint` **0E/0W/0I**；网表分区与导线几何均 **55/55 + 3/3 NC、48 岛一致**；
  主代理全页及 USB/去耦/CH343 局部渲染目检通过。DRC 仅 3 个规格 NC 与 3 个库属性
  WARN。旧 P37 已删除，Board2 只有用户 P1。持久化 `saved_unverified`，第二拓扑未做。
- **543M 全量兼容修复**：首轮 **9449 passed / 25 skipped / 8 failed / 5 errors**。
  联合选档只看 native-attr，漏了 `labelPolicy.stub=straight`，导致 auto/V45 被改且
  地旗无解。现仅在明说 straight 时联合，auto 恢复逐脚旧阶梯；V45/534x/534w 与
  543f2 原哈希不动。straight 的 543e/native 哈希和 D±60 属合同升级；flag-grid 的
  最近合法格点改由直接正向几何钉，未删碰撞/拒绝覆盖。子代理聚焦 **71 passed**、
  主代理 V45/auto/格点复跑 **35 passed**；重编译 P38 与验收版逐字节相同。
  主代理删除 straight 门的变异使 auto 测试变红，cp 还原后 drawcompiler sha256=
  `0451d93a7c8a49b1ca1708bfb7dda2ef3e5e6d250059146c043313c397d68a4d`。
  第二轮全量 **9496 passed / 25 skipped / 2 failed**，仅剩两条既有环境红，未跑第三轮。
- 证据 `evidence/543kl/`；最终全量与其它测试线读数见该批 README 和日志。不做 git 写。

### 543G：CH340 第二拓扑泛化（完成；外部漂移与环境红另记）

- 第二样本为公开合成 `blocklib/specs/ch340_uart_543g.*`：CH340G + Type-C/CC +
  两组去耦 + 12 MHz 晶振与两负载 + 2x5 UART。不是读取参考页坐标或复制 CH343 网名。
- agent 最终只声明三个功能岛：`usb_c`、`serial`、`uart`。晶振及负载是 CH340 的附属
  支路，留在 serial；H1.9 正常输出 +5V。曾尝试的独立 coreless clock 岛与纯信号排针岛
  属于过度拆分，相关 grammar 限制只记边界，不借本样本扩写一套新语法。
- 通用修复分批：543G-1 信号网上的晶振/RC 电容不再误判为去耦，V3 内部轨仍识别；
  543G-2 grammar 已声明同 owner 支路关系时退回旧阶梯；543G-7 完整 flow 链 +
  `moduleColumns` 使用阅读列；543G-11 既有 `branchOrder` 真正进入支路排序；
  543G-12b 仅在一条 bridge、两个 shunt、同宿主同侧且 jog≤30 时按宿主脚联合成 bay。
- H1 文字右侧、时钟三件文字朝外是 agent 的可读性声明，已写入规格，不是手填坐标。
  最终 draw plan 的 Type-C D± 为 40/40、60/60，U1 D± 与 U1/H1 TXD/RXD 各 40；
  XI/XO 各 90，后者只有一次由脚距造成的 30 正交折线。主代理已亲看
  `.tmp_543n/g12c_clock_text/final.svg` 全页、时钟与 USB 局部，离线视觉通过。
- 测量教训：编译 `page.plan.segments` 的 5 单位预留段会在落地扩成 40，不能再与最终
  `drawapply.module_plan` 的导线混用；P38 同样是 `200→205→240`。G-5/G-9 的
  「Type-C 必须腾空间」结论已作废，不为这个假缺口改算法。
- **真机授权边界**：只在 `test V4` Board1 新建一页作为 CH340 独立示例；P38 与
  Board2 用户参考 P1=`30560d9c0a52a6d2` 不改，`ROBOT ctrl FOC` 及一切其他工程禁写。
  新页先空页 plan/apply，lint、独立逐脚和宿主渲染三关全过才保留；失败只进证据。
  两页分别代表 CH343/CH340 两个通过拓扑，不删除 P38 冒充“替换验收”。
- **最终真机页 P39=`62e4828acc56a307`**：12 器件、36 计划导线、17 旗；apply 成功并保存。
  `draw lint` 0E/0W/0I；一次性独立逐脚 **45/45 连接 + 15/15 NC = 60/60**；主代理
  已亲看宿主 PNG 全页与三岛局部。早期两份 plan 因 C1590 的 MPN 未声明而零写入失败，
  补齐真实 MPN 后重新出 plan 成功，未新增生产放件解析器。失败证据 `evidence/543g/live/`，
  成功证据 `evidence/543g/live_mpn/`。
- DRC 仅规格内 15 个 P39 NC、P39 两个电阻库属性 WARN 与 P38 既有 WARN；不写 DRC 全绿。
  主代理聚焦 **47 passed**，MPN 后第二拓扑 **18 passed**；有效变异均先红后字节还原。
  全量回归在目标收尾批执行，P39 当前仍 `saved_unverified`，总索引 `evidence/543g/README.md`。

### 543N：P38 关闭重开持久化（完成）

- 只读验收对象为 `test V4` Board1 P38=`0ec4dc022ef38563`；Board2 仅有用户参考页
  P1=`30560d9c0a52a6d2`，未改。`ROBOT ctrl FOC` 与所有其他工程未写。
- 基线冻结后，岳已关闭重开 test V4；新 instance 为 `inst-004022079-0uroct26`，重新读取
  doc.list 确认同一工程 UUID、同一 P38、Board2 P1 不变。多窗口下一次性
  `.tmp_543n/persistence_targeted.py` 显式寻址，未让旧 persistence 命令猜窗口。
- 首次比较发现四个自动网 `$19N…`→`$1N…`，没有器件/图元丢失；独立逐脚证明四个自动网
  分区与全部用户命名网完全相同。shared 小批给 `reconcile_names` 增加默认关闭的
  `auto_only`，仅 persistence 启用，命名↔自动、命名网变化、拆并网与脚变化仍拒绝。
  通用 compare 缺省行为不变，兼容矩阵见 `tasks/shared-platform.md` §9。
- 主代理邻域 **187 passed**、合同 **43 passed**；过滤全关与命名/自动混用两组变异均先红，
  cp 还原 sha256 一致。最终真实在线比较：11 components / 17 nets / 76 primitives，
  **saved_verified**；四个改名按成员集合并披露，证据 `evidence/543n/`。

### 543H 最终回归与旧任务裁决（完成）

- 201G 当前五岛规格1候选，13条软披露及SEC_12V旗位由 `test_543h_201g_islands.py` 钉住；
  515A六项旧洞有防回归，旗位预留与器件页框归属两项已修。201C/201D经当前实验
  裁决不复活，证据 `evidence/543h/`、`.tmp_543h_201cd/`。
- 首轮全量发现6条旗位成本回归；`_priced_seats` 改为每网首档计价、全集覆盖后，
  六条独立复跑29 passed。最终第二轮 **9962 passed / 25 skipped / 14 failed**：
  12条其他agent货架漂移与2条既有Windows环境红，本批业务回归全消，未跑第三轮。
- connector **576 passed** + typecheck；DSH **129 passed / 1 skipped** + typecheck/build；
  Rust fmt/clippy/test通过；draw smoke、CLI合同、仓库卫生均通过。
  最终日志 `evidence/543h/final_pytest_rerun.log`，源码哈希 `final_source_hashes.txt`。
  本批成果已随 `44901da` 提交；后续发布状态见 `docs/handoff.md`。

## 3. 总验收与兼容口径

- 总验收不是单一 `ok=True`：自动基线、离线硬违反、逐脚连通、渲染视觉和真机门禁各自有证据。
- 未写新规格键、未调用新分析层的旧输入必须保持字节/行为不变；新能力不能默认改变旧页面。
- 当前只规划 V4 单页普通器件；V3、多板、CBB、`.epro2/.eprj2/.eprj3` 不在本任务已覆盖范围。
- 最终批次才串行跑全量 pytest、connector、dsh-plugin、Rust 和 draw smoke；开发期跑聚焦测试。
- 全量一次只跑一轮，失败后先聚焦修复；任何 git 写仍逐次经岳批准。

### 543O：roadmap 同步声明钉（文档批）

- 岳指出稳定路线图没有随 543G/N/H 收口，要求及时更新。主代理只改 `docs/roadmap.md` 与本任务账；
  保留其他 agent 在同文件已有的版本规则改动，不碰发布或其他业务文件。
- 路线图必须记录两个已验收拓扑及各自持久化边界、agent/解释器职责、201C/201D 不复活、
  201E 已落，并清除 Board2/P1 是试验场的过期说法。历史读数保留为基线，不冒充当前页读数。
- 子代理文件域仅 `tests/test_doc_claims.py`：新增一条 roadmap 与本任务账、TASKMAP 的同步声明钉。
  最多 20 步或 15 分钟；不碰真机、不跑全量、不改生产代码、不做 git 写。先跑新增用例，
  再跑完整 `tests/test_doc_claims.py`，pytest 使用独立 `--basetemp=.tmp_pt_543o`。
- 完成条件：声明钉与文档 diff 经主代理复核，文档测试通过；本批不自行提交或推送。
