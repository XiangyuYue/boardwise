# 547：SmartMedicineBox 固件约束逻辑原理图（绘制水平实测）

## 0. 目标与事实边界

岳要求以 `E:\SmartMedicineBox` 为输入，安排子代理实际画出原理图，检验当前绘制线，而不是再用既有 CH343/CH340 示例代替。

已核实：该目录是 STM32 固件/Android 工程，没有 `.epro2/.eprj2/.eprj3/.epru/.esch/.epcb/.kicad_*` 或 Altium 原理图文件。输入因此是**固件约束驱动的逻辑重绘**，不是原板制造原理图还原，也不能据此做投板结论。

- 原目录及其 git 一律只读，不在其中生成文件；不把固件中的热点、云端或任何其他凭据复制到规格、日志、任务账或渲染图。
- `README.md`、`Smartbox.ioc`、`Core/Src`、`Core/Inc`、`MDK-ARM/code` 是证据源。固件实际代码与 `.ioc` 不一致时记录冲突，不静默任选：当前 `Core/Src/main.c` 使用 HSI 作为 PLL 源，不得只凭 `.ioc` 的 HSE 字段画晶振。
- 已出现的功能范围不得为迁就编译器而删减：STM32G431RBT6、ST7789、MPU6050、AHT20、ESP-01S、无源蜂鸣器、LED1/2、KEY1–4、USART1、SWD；BMP280 是可选件，必须标清可选身份。
- 固件没有给出的供电来源、分立件参数和模块内部电路只能列为 `assumed`，不得冒充原板事实。优先使用诚实的模块边界；若采用典型去耦/上拉/限流等连接，必须在假设账中逐项说明。
- 结果分 `automatic` / `agent-adjusted` 记账。不得读取或复制参考页坐标；agent 负责功能分岛、信号流和阅读关系，解释器负责几何。

## 1. 547A：证据合同与离线候选（当前派单）

**唯一目标**：从固件证据形成完整电路/展示规格，产出 `ok=True` 的离线候选与可审图像。本批不碰真机、不改生产代码。

### 可写范围

- `evidence/547/a/`：来源映射、假设账、电路/展示/符号规格、候选、编译报告、渲染和自检结果。
- `.tmp_547/`：一次性探针、独立逐脚检查及中间产物。
- 本任务书的 547A 交卷段（只许一次 append，append 后独立计数防双执行）。

不得改 `src/`、`connector/`、`dsh-plugin/`、`blocklib/`、其他任务文档或原工程；不做任何 git 写，不跑全量测试。若发现解释器缺口，保留可复现候选并报告，不能顺手改算法或缩小功能范围。

### 必须交付

1. **来源映射**：每个 MCU 信号网给出外设端点、来源文件与行号；区分 `observed` / `assumed` / `optional`。检查 `.ioc` 与实际 GPIO/时钟代码的冲突，尤其 HSE/HSI、LCD 控制脚、ESP 控制脚和按键上下拉。
2. **假设账**：所有固件无法证明的电源、阻容、极性、模块引脚和 NC 逐项列出；没有依据的具体值不得写成事实。
3. **功能分岛说明**：逐岛写功能理由、与宿主/其他岛的关系、预期图形结果。附属件不得为了好摆而拆成无约束孤岛。
4. **自动候选**：规格不含参考坐标或手填器件坐标；用当前 CLI 跑离线 `draw compile`，保存全部候选与报告。离线符号几何必须标为未真机标定，不能声称可直接 apply。
5. **离线三关**：编译/可读性 `ok=True`；一次性独立脚本按生成电路逐脚核对候选分区并覆盖声明 NC；渲染后逐岛视觉自审，对照 S-01…S-21，不能只看 lint。
6. **缺口清单**：符号库、复杂 MCU、页面容量或算法导致的失败逐项给原始错误和最小复现；`ok=False` 只进 evidence，不进入下一批。

### 预算与交卷

子代理最多 40 步或 30 分钟，先到先交回当前证据。岳允许其再派一级子代理辅助：若工具面支持，可把一个只读证据提取或独立视觉审查任务派给一名 helper；不得再向下派层，不得并行写同一文件。没有该工具面就自行完成，不虚报委派。

交卷不超过 2000 字，详细日志落 `evidence/547/a/`。报告实际功能覆盖、自动/假设边界、候选路径与哈希、编译/逐脚/视觉各自读数、未解决项和 547B 最小下一步。主代理亲自看渲染与关键规格后才批准真机批。

## 2. 547B：真机符号标定与三关（待 547A 复验后另派）

- 只写任务书逐字点名的 **`test V4`**，Board1 新建独立页；先重新读取 instance 和 `doc.list`，核对工程名与空页身份。原 SmartMedicineBox 工程及所有其他窗口禁写。
- 保留既有 P38、P39 和 Board2 用户参考 P1，不删除、不冒充本批新图。目标不存在或身份不符就停下，不自行替代。
- `--profiles` 必须来自真机实测；器件型号/库解析失败不得换成假器件。先空页 `draw plan`，成功后 `apply`，再走 `draw lint`、宿主 netlist 独立逐脚、宿主 DRC、全页与逐岛渲染视觉。
- 失败候选只留 evidence；不通过不得交付。DRC 的规格内 NC/库属性 WARN 与真实错误分开披露；保存但未关闭重开只能记 `saved_unverified`。
- 任何受控人工微调须记 `agent-adjusted`，保存前后证据并重跑三关，不能冒称 `automatic`。算法修复、共享层修改和 git 提交均另批另授权。

## 3. 最终评价口径

最终回答的不只是“画出来没有”，还要分开评价：功能覆盖与证据诚实度、自动分岛/几何质量、逐脚正确性、文字/旗标/成对支路、绕线交叉与整体可读性、真机落地与持久化边界。任何未覆盖或人工修补都必须从总分和结论中体现，不能用机器全绿替代人的视觉验收。

## 547A 交卷段（子代理，2026-11-07）

**结论：规格做全，图纸没画全。全页 compile exit 5（0 候选）；8 岛中 7 岛 ok=True，`mcu` 岛 8 个变体全被拒。**

**功能覆盖**：30 件 / 31 网 / 5 NC / 8 岛，含 STM32G431RBT6（32 个固件功能脚）、ST7789 8 脚屏、MPU6050、AHT20、BMP280（optional，独立岛 + value 标 optional）、ESP-01S（USART3+EN/RST/IO0）、无源蜂鸣器（TIM1_CH1）、LED1/2、KEY1–4、USART1、SWD。

**边界**：observed＝全部 MCU 信号网的固件证据（`source_map.md` 逐条带文件:行）；assumed＝3V3 轨与来源、全部阻容数值/上拉、按键接 3V3、LED 高有效、屏 CS 拉低、MPU AD0 接地、BMP280 CSB/SDO 接法、USART1/SWD 排针存在、蜂鸣器直驱（`assumptions.md`）；optional＝仅 BMP280。记录 5 条固件/文档冲突：HSE 不画（按裁决）、KEY2 固件从未读、蜂鸣器 1200 Hz 非 2.7 kHz、BMP280 可缺省、LCD 软/硬 SPI 并存。

**自动/人工**：全部 `automatic`（规格无器件坐标、无参考页坐标、无 userLocks）；本批 `agent-adjusted` 为零，未落真机。

**候选与渲染**：全页无候选（`ok=False` 只进 evidence）。唯一 ok=True 候选是单岛 wifi：`evidence/547/a/island_check/candidates/cand1.page.json`（`dd53c98c197bec07`）与 `cand1.svg`（`4a2fa2e5147a8471`）；规格哈希 `d2b95507235e9414`/`93bd379e5c064e48`/`23a27caa4a3b5a84`。

**三关读数**：编译闸＝全页 `ok=False`、逐岛 7/8 True、wifi 单岛 `legality=0 findings=1 crossings=0`；逐脚＝独立几何脚本对 wifi 候选 **PASS**（6 件/8 线/18 脚，5 网各 1 分量，NC `J2.IO2` 不接触导体），全页**无对象可核对**；视觉＝**未执行**，本子代理工具面无图像读取（无 ReadMediaFile），只看得到 SVG 文本与报告，**不得**把机器读数当视觉通过。

**未解决项**：G1 `mcu` 岛容量——近/地旗引线/四键同轨短接三种失败，缩到 9 件仍短接，缩到 U1+C1+C2+C3+R1 才过；G2 ic-periphery 无"串联两支路"形状（LED+R 只能两端直连画，限流电阻未落图）；G3 C2/C3 在缩容探测里被临时去掉，全量规格仍在；G5 视觉关未做。详见 `gaps.md`（含原始错误与最小复现）。

**547B 最小下一步**：①先由主代理亲眼审 `cand1.svg` 与三份规格，裁定 G1/G2 是"改展示规格（如把面板件拆成显式附着的小岛）"还是"派单补 ic-periphery 的分支容量/串联支路通用能力"；②真机批次在 G1 关闭、且全页出现 ok=True 之前不得开；③真机仍须逐字点名 `test V4` 空页并现场量 profiles（本库几何全部标 `uncalibrated`）。

## 547A 主代理复核（2026-11-07）

- 来源账、假设账、全量规格与失败日志已抽读；全页确实没有可验收候选，547B 不开。
- 主代理经本地 HTTP + 浏览器实际看了 WiFi SVG 的全图与三倍局部：`ok=True` 不等于视觉通过。J2 位号/型号挤在左侧标签/引脚区，供电与去耦阅读关系不清；当前占位符号只允许用于离线排布，不能作为最终宿主符号验收。
- 不为了绕开容量把按键/LED/蜂鸣器拆成语义不成立的 coreless 岛。G1 作为重复同类支路的通用几何缺陷处理；G2 作为显式声明的串联支路能力另批处理。

## 547C1：N 路重复 shunt 不短接（当前算法小批）

**唯一缺口**：同一核心下三个及以上同型/同类二端支路不能因共享 lane 或成对对齐逻辑而跨网短接；547 的 KEY1–4 是最小真实触发场景。不新增规格键，不改电气语义。

- 生产文件域原则上限 `src/boardwise/engines/drawcompiler.py`；确需改 grammar 判断时可含 `src/boardwise/engines/grammar/ic_periphery.py`，不得碰 shared parser/CLI/bridge/connector。
- 新测试仅 `tests/test_547_repeated_shunts.py`；证据与复现放 `evidence/547/c1/`、`.tmp_547/c1/`。547A 原始证据不得覆盖。
- 先落一个修复前必红的 N>=3 独立 KEY 网回归，再修座位/lane/旗标。不得通过删支路、合并 KEY 网、隐藏文字、放宽连通闸或手填坐标变绿；既有 pair 行为与未触发输入保持不变。
- 聚焦跑新测试及 `test_543g*`、`test_543h*`、`test_534*` 邻域，使用独立 basetemp `.tmp_pt_547_c1`。本批不跑全量、不碰真机、不做 git 写。
- 用 547 的 LED 直连**诊断变体**复验 G1（只用于隔离 G2，不能交付）；保存修复前后候选/错误。完整串联电路由 547C2 回验。
- 子代理最多 40 步或 30 分钟。交卷写清根因、文件 diff、修复前红/修复后绿计数、邻域读数、诊断候选与剩余 G2；本任务书只 append 一次交卷段并独立计数。

## 547C2：显式二件串联支路（待 C1 复验后另派）

目标只覆盖 agent 显式声明的两件二端件串联路径，例如 GPIO→R→LED→GND；中间网恰好两件，外端是一核心信号与 power/gnd。不自动猜所有自由二端件，不承诺任意长链。新规格键默认关闭，未写时旧行为/哈希不变。`contracts/module-owners.json` 确认 `core/presentationspec.py` 归 draw 而非 shared；仍须独立合同批留兼容矩阵，不得夹在 C1 中顺手改。


## 547C1 交卷段（子代理，2026-11-07）

**结论：根因已定位到机制与实测几何，但 30 分钟预算内没有做出可验证修复；生产代码零改动，交回不扩域。**

**根因**（实测 `evidence/547/c1/geometry_probe.txt`）：U1 的 PC6/PB15/PB14/PB13 是一**竖列**（y=15/5/-5/-15，x=80），四个按键却在全部 6 个姿态变体里被归成 **same-row** 组、统一落到 y=25，并沿 x 以 60/90/135 递增外走（variant0：S1(-260,25)…S4(-440,25)；variant5 镜像到 +870）；同时梯子的 `index` 按 `(owner, direction)` 计数（`_chain_and_shelf_layout` else 分支），4 键+2 灯+蜂鸣器共用一个计数器 → 距离 30/60/90/120，越 near() 的 300 上限，7 个变体全拒。547A 全页里同一批按键被压到同一坐标带、`netlist-partition-mismatch` 把 KEY3/KEY4 画成一节点，是同源的第二症状（横向节距 10 < 键体高 13，`clearance` 只量沿方向外扩）。

**修改文件**：仅新增 `tests/test_547_repeated_shunts.py`（自包含的 547 逻辑库/电路内联）；`src/boardwise/engines/drawcompiler.py` **未改**，未碰 grammar、shared、CLI、真机、git。

**前红后绿读数**：修复前 `pytest tests/test_547_repeated_shunts.py -q --basetemp=.tmp_pt_547_c1` = **1 failed, 1 passed**（触发用例红：`near(S1,U1)` 340+ 单位；对照用例绿：无面板支路的 MCU 岛 ok=True）。**没有后绿**——没有修复可验。邻域 `test_543g*`/`test_543h*`/`test_534*` **未跑**（预算耗尽，交回时如实标注，不得读成通过）。

**诊断候选**：**未生成**（LED 直连变体复验未做）。

**剩余问题 / 547C1 下一步最小动作**：①按 anchor 实际轴线分组（竖列→same-column），②`index` 以 anchor 为界重置、只在同 pad 重复支路上递增，③横向节距 < 体宽时给节距档或拒绝而不是重叠；改后必须让本批红测试转绿且对照用例仍绿、邻域四组重跑全绿。`evidence/547/c1/README.md` 有完整几何与建议；触发测试保持红色入库，为下一批的"修复前红"。

## 547 实测收口（整页未通过，2026-11-07）

- 547C1 后续又进行了两轮窄修复，加上首轮共三轮，均没有形成可验证修复。主代理确认
  `drawcompiler.py` sha256=`c7f6414addf5d9a9d0ab80877497502c317c81c1d109501d9a7be675d537b520`，
  与修复前一致，grammar/shared/CLI 无本批生产 diff。
- 最后实测把联合缺口收敛为：支路共享网选择、`near()`/placement 的关系点仍读另一共享网、
  同型键脚距与 MCU pad 节距冲突，以及 3V3 回流/旗标车道。单纯改 anchor 或错开距离只移动失败点；
  关系点一致性须先独立成批，不能再夹带试补丁。详见 `evidence/547/c1/attempts.md`。
- 按预设停止线终止本轮实现，不启动 547C2 或真机 547B。没有全页候选、没有全页逐脚对象、
  没有真机页，也没有任何持久化结论；WiFi 单岛只证明其机器与局部几何检查，主代理视觉不通过。
- 未解决复现保留为 `tests/test_547_repeated_shunts.py` 的 **strict xfail**，不断言放宽、不删除几何检查；
  收口读数 **1 passed / 1 xfailed**。修复后 XPASS 会强制失败，必须摘标并恢复普通通过用例。
- 本轮最终评价：证据整理与范围披露完成，复杂 MCU 自动整页绘制未通过；不能拿既有 CH343/CH340
  或本次 WiFi 单岛冒充 SmartMedicineBox 整页交付。后续重开须先完成关系点一致性与
  N>=3 支路联合几何，再实现显式二件串联支路，最后重新从全页离线三关开始。
- 本段只记**自动线**当时的收口。547G 辅助线后来在 test V4 的 A2 页完成真实 apply，
  当前状态见文末「547G 暂停快照」；自动整页缺口（547D/E/F）未因此关闭。

## 547S：支路共享网与关系点合同统一（当前）

### 公开合同与 owner 修正

- `contracts/module-owners.json` 实测确认 `engines/placement.py`、`core/presentationspec.py` 均归 **draw**；
  前文把它们当 shared 的说法撤回。本批仍是独立合同批，不夹带座位、位姿、回流旗标或串联支路实现。
- 对两端件的共同网，统一顺序分三档：**①声明为 `signal` 的网优先；②其余非 `gnd` 共同网按旧
  sorted 顺序；③`gnd` 最后**。这样 VCC+GND 选 VCC（旧 `_shared_nets` 的 non_return 语义）、
  KEY+3V3 选 KEY、LED+GND 选 LED、纯 3V3+GND 仍 3V3、undeclared+GND 仍选非 GND。
  未声明类别的网不参与 signal 提升但保留其 sorted 位置。该规则同时回答 `shared_net`、关系测量网、
  `other_net`/pin_shared 的归属。（修正：早期写法“无 signal 时直接 sorted”会让 VCC+GND 落到 GND，
  与旧 non_return 行为相反，已废弃。）
- 支路座位 `_branch_slot`、搜索/终审 `relation_points_between`、修复 `_shared_net_of` 与
  `_branch_lane_edges` 必须调用同一个排序合同，不允许一个选 KEY、另一个仍选 3V3。
- 没有“信号网+轨”歧义的旧输入保持逐字节/行为不变；有歧义的旧页必须逐页对拍并说明变化，
  不得只更新哈希。回退是恢复统一排序函数的旧顺序，cp+sha256，不用 git checkout。

### 文件域与 negative control

- 仅 `src/boardwise/engines/drawcompiler.py`、`src/boardwise/engines/placement.py`、
  `tests/test_547_shared_branch_nets.py`、`evidence/547/s/`、`.tmp_547/s/` 与本任务书交卷段。
- 新测试至少覆盖：KEY+3V3 选 KEY、LED+GND 旧行为、纯 power/gnd 回退、四个支路 slot 与 near
  关系点一致、lane/修复读数一致、无歧义输入不变。禁止 KEY 网名或器件名特判。
- negative control：强制排序函数回到 rail-first 时新测试必须红；恢复后哈希一致。
  当前 `test_547_repeated_shunts.py` 保持 strict xfail，本批不要求也不许提前摘标。
- 聚焦跑新测试、`test_201b_placement.py` 及与 543 支路/lane 相关邻域，basetemp `.tmp_pt_547_s`。
  不跑全量、不碰真机、不做 git 写。全页 compile 只用于记录下一个失败点，不作为本批验收条件。
- 子代理最多 35 步或 25 分钟。交卷列统一函数与四个消费者、前红后绿、邻域计数、
  有歧义旧页对拍、未覆盖项；只 append 一次交卷段并独立计数。主代理复核后才进入 547D。

## 547S 交卷段（子代理，2026-11-07）

**结论：合同已统一并转绿；547 岛仍 0 候选（座位/回流缺口留给 547D），本批未碰座位/位姿/旗标/串联文法。**

**统一函数**：`placement.shared_net_order(nets_here, nets_there, class_of=None)` —— 三档顺序为
**声明 signal → 其余非 `gnd` 按旧 sorted → `gnd` 最后**；`class_of=None` 时逐字返回旧 sorted，
未声明类别不参与 signal 提升。`_is_signal_class` 是唯一定义。

**四个消费者全部改接**：`drawcompiler._shared_nets`（座位，`_branch_slot` 经它取 `shared_net/pin_shared/other_net`）、
`drawcompiler._points_for_relation` → `placement.relation_points_between(class_of=…)`（终审尺）、
`placement.relation_points` → 同一函数并接 `PlacementNet.cls`（201B 搜索尺）、
`drawcompiler._shared_net_of`（修复）、`drawcompiler._branch_lane_edges`（lane）。
唯一新增参数 `class_of` 默认 `None` = 旧行为；`_net_class` 与新 `_circuit_net_class` 分名，避免遮蔽既有 helper。
`_tap_axis_by_net` 也读共同网但顺序无关（对每条都 setdefault），不属消费者。

**前红后绿**：新测试 `tests/test_547_shared_branch_nets.py` —— 初版 11 条 **11 passed**；
主代理复验发现 VCC+GND 回退漏洞后修正为三档顺序并加两条（VCC+GND 选 VCC、undeclared+GND 保持非 GND），
现 **13 条 13 passed**（`.tmp_pt_547_s_retry`）。
红证用 negative control：把 `shared_net_order` 的三档逻辑强制成 `return common`（naive sorted =
回归形状）→ **9 failed / 4 passed**（`evidence/547/s/negative_control_sorted_retry.txt`，失败含
`shared_net '3V3' != 'KEY1'`、VCC+GND 落 GND、四兄弟全落轨、关系尺测在 VDD、lane 取 3V3）；
`cp` 还原后 `sha256(placement.py)=ec1182d746e5…` 与备份一致，复跑 13 passed。
（首轮的 `_is_signal_class → False` 变异不再能复现回归形状，仅作历史证据 `negative_control_rail_first.txt`。）

**邻域**：`test_201b_placement.py` + `test_543h_shunt_escape.py` + `test_543g_layoutroles.py` +
`test_543h5_explicit_gate.py` = **73 passed**（含既有几何/哈希钉子 → 无歧义页未变）。
`test_547_repeated_shunts.py` 保持 strict xfail：**1 passed / 1 xfailed**，未摘标。

**有歧义旧页对拍（547 岛）**：前 = 四键 `shared=3V3/pin_s=2`、anchor 全为 `(-80,45)`、拒因 `near(S1,U1)`；
后 = 四键 `shared=KEY1..KEY4/pin_s=1`、anchor 各自 `PC6/PB15/PB14/PB13`，首拒因变为 `SWCLK` 标签压线
（BOOT0 走线穿 `[-133.5,0.5,-92,9.5]`，`evidence/547/s/ambiguous_page_after.txt`）。**解释**：座位网改变
⇒ 该岛左右拥挤分布改变；两种状态都是 0 候选拒绝，无已交付图形被改写；剩余失败是同一拥挤岛内的标签座位，
属 547D。

**未覆盖**：未跑全量、未碰真机/git；547 岛座位/回流联合缺口（N>=3）仍未解，按任务书留给 547D。
**证据**：`evidence/547/s/README.md`、`negative_control_rail_first.txt`、`ambiguous_page_after.txt`、`after.sha256`。

## 547S 主代理复验（通过，2026-11-07）

- 复跑 13 条合同测试、73 条邻域与 547 对照：**87 passed / 1 strict xfailed**。
- 主代理抓回首版“无 signal 直接 sorted”造成的 VCC+GND 回退错误，修正为三档并补负例；
  子代理 negative control 为 9 failed / 4 passed，证明 plain sorted 会准确暴露回归。
- 主代理另把 `_shared_net_of` 单独退化到旧 sorted：修复一致性测试 **1 failed**（3V3 != KEY1）；
  只用 cp 备份还原后 sha256=`f6825e8a2924fafbfe5518fab549474f364d82238b79d13c3948920f014895ca`，复跑通过。
- 547S 合同验收通过，547 整页仍未通过；`docs/draw.md` 已同步三档规则，旧测试说明也已清理。

## 547D：N>=3 支路联合几何（当前）

**唯一目标**：在 547S 合同之上，让现有 `test_547_repeated_shunts.py` 的四键/两灯/蜂鸣器夹具真正通过，
并摘掉 strict xfail。不是只消除 near，而是消除跨网短接、异网引脚重合、回流穿体与标签冲突。

- 生产文件域限 `src/boardwise/engines/drawcompiler.py`；`placement.py` 与 547S 排序合同不改。
  测试限 `tests/test_547_repeated_shunts.py`（不得改电气夹具或放宽断言），证据 `evidence/547/d/`、
  `.tmp_547/d/` 与本任务书交卷段。
- 547S 回退基线：drawcompiler sha256=`f6825e8a2924fafbfe5518fab549474f364d82238b79d13c3948920f014895ca`，
  placement sha256=`ec1182d746e5bef7dd21d251bad74761a97cfaea07fd1da3ae480f6b5557dc91`。
  若本批失败，只能回到该基线，不得把 547S 一并撤掉。
- 原夹具没有电源旗标，必须保留并修通其安全回退；可另加有旗标对照，但不能用改夹具规避铁路短接。
  四个 KEY 必须是四个不同节点，S.1 接各自 GPIO，S.2 不与自己的 KEY 短接，所有面板件真实落位。
- 先复现当前失败，再针对同型件位姿/pad band、不同 pad 的外扩计数和 3V3 回流联合设计；
  禁止 KEY 特判、删件、并网、藏字、手填坐标、放宽连通/可读性闸或只移动失败点。
- 绿后跑 547 两个测试文件、201B 与此前 73 条邻域，使用 `.tmp_pt_547_d`；旧 pair 和未触发输入不变。
  再跑 LED 直连诊断页，结果只作 G1 诊断，不冒充完整电路交付。
- 不跑全量、不碰真机、不做 git 写。最多 40 步或 30 分钟；若仍失败，恢复 547S 基线并交坐标证据。
  交卷列根因、前红后绿、邻域、诊断候选与剩余问题；只 append 一次交卷段并独立计数。

## 547D 交卷段（子代理，2026-11-07）

**结论：未修通，生产代码零改动（drawcompiler 仍 `f6825e8a…`、placement 仍 `ec1182d7…`，与 547S 基线逐字节一致，无需 cp 恢复）。**

**当前首拒（`--runxfail`）**：`[layout-unsat] the label 'SWCLK' at (-80,5) has a conductor through
its box that no seat on its own ladder clears: a BOOT0 run runs through [-133.5,0.5,-92,9.5]`。

**根因（坐标实证 `evidence/547/d/label_band_probe.txt`）**：
- U1 左列标签带已被**每 10 单位引脚行占满**（SWCLK `[-133.5,0.5,-92,9.5]`、SWDIO `[-129,10.5,-92,19.5]`、
  I2C3_SDA `[-148.5,-9.5,-92,-0.5]`、I2C3_SCL `[-148.5,-19.5,-92,-10.5]`），SWCLK 四向梯子无位可退。
- **C1（3V3 去耦，竖放 40 高）box `[-148.5,5,-131.5,45]` 正压 BOOT0 走廊 y=25**；R1 origin `(-200,5)`。
  路由器只能绕：`(-200,25)→(-155,25)→(-155,0)→(-125,0)→(-125,25)→(-80,25)`，其 `x=-125` 竖直段穿 SWCLK 盒。
- 从 y<0 绕过后**任何回升位置都撞标签**（x∈[-131.5,-92] 全被占，x>-92 只剩 12 单位引脚根部），
  即“标签带 + 跨行支路体”是一堵死墙，不是单点可挪的冲突。

**两条已实测死路**（`evidence/547/d/experiments.txt`）：
1. 按 `shared_net` 类别把信号支路排内、导轨支路排外 → BOOT0 线冲突消失，但 R1 位号文本
   `[-127.5,7.5,-112.5,16.5]` 与 SWCLK 标签**文本重叠**（线冲突换成字冲突）。
2. 电源类支路改走 `sidePreferences.power=top`（C1 移到 U1 上方）→ 左列解除，但 `3V3`（8 脚、
   库无旗标符号）铁路 `could not be joined inside the searched corridor`，整页仍 0 候选。

**右列现状（未验完，闸先停左列）**：547S 后四键已各自坐 KEY 网（`shared=KEY1..KEY4`、`pin_s=1`、
anchor `(80,15/5/-5/-15)`、layout `260/320/380/440`）；**假设**（未验证）：near 现在测在 KEY 脚上，
S4 的 360 会被裁到 ~300 使 S3/S4 同列（13 高体 / 10 节距体相交），需左列修好后复测。

**未做**：未改测试、未摘 xfail、未改 production、未跑邻域与 LED 诊断页（无改动可验），未碰真机/git/全量。

**留给下一批的最小判断**：座位必须与**标签带联合求解**——支路体整块落在标签带外且不跨任何外来
引脚行；在此之前，位姿/顺序/方向单独调都只能把失败点搬家（本批已两次实测）。

## 547D 续：auto 规格纠正与标签走廊联合几何

- 主代理核查 `core/presentationspec.py:165-169`：straight 禁止弯桩，auto 才保留直桩→一步让位弯桩。
  547 没有必须 straight 联合等长的差分对，547A 是机械沿用 CH343。诊断副本仅 straight→auto 后，
  左列 SWCLK/BOOT0 死墙消失，首拒变为右列 **LED2 走线穿 LCD_SDA 标签盒**；
  原断言仍 1 failed / 1 passed，故尚未改正式测试或摘标。证据 `evidence/547/d/auto_policy_*`。
- 续批允许正式测试使用 auto，但只能在全部原几何断言通过后摘 xfail；不得把这条规格纠错说成放宽。
  不承诺 straight 在此高密度 MCU 上必有解，也不许借 auto 隐藏跨网、引脚重合、回流穿体或文字冲突。
- 换一名独立 coder，只修 auto 暴露的支路座位/走线与标签走廊联合问题。生产域仍限 drawcompiler；
  不改 placement/shared_net_order，不改电气夹具，不做 LED/LCD/KEY 名字特判，不扫 stubMin 数值。
- 绿后验收仍按 547D：原几何分区全过、摘 xfail、547 两个文件 + 201B + 73 邻域、LED 直连诊断页。
  失败则 drawcompiler 回 547S、测试保持 straight+strict xfail，保留 auto 对照证据，不交半成品。
  最多 40 步或 30 分钟，交卷只 append 一次续批结果并独立计数。

## 547G：自动 / agent-adjusted 双轨（G1–G3已过；G4部分完成，已暂停）

岳 2026-11-07 批准按主代理建议更新文档并规划子代理。Konnect-EDA 调研的结论是**借鉴分工，
不移植代码**：当前 `Orchis-ai-LLC/Konnect-EDA` 未公开内部实现；旧 `mixelpixx/Konnect`
可见 AGPL-3.0 Rust 源码，具有确定性 KiCad 局部编辑、校验和渲染工具，但 `connect_pins`
只做共轴直线或固定 H→V L 弯，模板放件后仍由 agent 接线。调研快照只放 `.tmp_konnect/`，
不进入生产代码，不新增 Konnect 运行时依赖；boardwise 是 MIT，不复制 AGPL 实现后继续按 MIT 发布。

公开来源：<https://github.com/Orchis-ai-LLC/Konnect-EDA>、<https://github.com/mixelpixx/Konnect>。
本地只读核对点：`sch_wiring.rs:551-561`、`templates.rs:548-571`；这些行号属于调研快照，
不是 boardwise 的可调用能力。

### 两条路线，两套诚实账，同一组质量闸

| 路线 | Agent 负责 | 确定性工具负责 | 当前状态 |
|---|---|---|---|
| `automatic` | 功能分岛、核心、阅读关系等语义规格 | 全部器件/导线/旗标/文字几何，编译与校验 | 547S 已通过；547D 暂停待续；547E及自动整页三关未开；547F命名脚子项另记 |
| `agent-adjusted` | 上述语义，以及显式局部几何计划或受控微调；逐项说明理由 | 确定性执行、既有可读性/lint、逐脚/NC、渲染与真机守卫 | G1–G3 已通过；G4 真机页已 apply/lint/netlist/render，暂停于 saved_verified 与完整四线（文末快照） |

Agent 编写 PresentationSpec 不等于 `agent-adjusted`；只有 agent 直接提供几何或做受控后调整才改账。
辅助路线**不豁免交付三关**：机器关使用同一套现有可读性/lint 与独立逐脚/NC 校验，主代理逐岛视觉另验；
没有经过自动 `draw compile` 的对象不得写成“自动编译 ok=True”。不得以辅助候选关闭 547D/E，
也不得删电阻、并网、隐藏问题文字或用未标定符号落真机。

既有“局部微调不能冒充通用能力”的红线不变。547G 先验证一个 WiFi 单岛，不允许直接手画整页后
宣布路线成功；若需要成体系的外部几何输入，先形成最小合同、来源记录和校验入口，再决定是否扩展。

### 547G1：WiFi 单岛接口盘点与辅助试绘合同（下一批，唯一目标）

回答一个问题：**现有对象和校验器能否消费 agent 提供的单岛计划，并复用现有质量闸；缺的最小接口是什么？**
先做窄接口盘点，再产出一个 WiFi 单岛草稿及实际校验读数；本批不改生产代码，不新增公开 CLI。

- 只读入口限 `core/layoutplan.py`、`core/changeplan.py`、`engines/drawapply.py`、
  `engines/drawlint.py`、`engines/readability.py`、`commands/draw.py` 及 547A WiFi 规格/候选。
  先 grep 定位，每次窄读；不得整读 CLI 或长日志。
- 可写 `evidence/547/g1/`、`.tmp_547/g1/` 和本任务书一次交卷段。原工程 `E:\SmartMedicineBox`
  只读；不得改 `src/`、测试、其他任务文档、connector、dsh-plugin、shared/CLI，不做 git 写、不碰真机。
- 交付 `interface-map.md`：现有 LayoutPlan/ChangePlan 构造、离线 lint/逐脚、渲染各自的真实入口；
  标明哪些能直接复用、哪些缺失，禁止把设想写成已有命令。
- 交付 `wifi.agent-plan.json` 草稿：器件身份、显式局部几何、连接意图、旗标/文字、页框及
  `provenance=agent-adjusted`；不使用参考页坐标，不包含可执行 Python/eval，不改电路网和 NC。
- 用当前已有校验器实际执行能够覆盖的机器检查，保存原始 JSON/日志和渲染；缺接口就如实记
  `not-run`/`blocked`，不得自造一个 `ok=True` 绕过。主代理亲眼视觉复核后才算单岛试点通过。
- 若需一次性适配/验证脚本，只放 `.tmp_547/g1/`，它不是生产能力。聚焦测试只跑定位到的既有
  layout/lint 邻域，独立 `--basetemp=.tmp_pt_547_g1`；不跑全量。
- 子代理模型 `opencode go/deepseek-v4.1-flash`，最多 35 步或 25 分钟，不再派 helper。
  交卷 ≤2000 字，列真实入口、运行命令/计数、候选哈希、未覆盖项和 G2 最小文件域；只 append 一次并独立计数。

### 后续串行批次（每批复验后再派）

1. **547G2：WiFi 单岛最小落地。**只在 G1 证明的缺口上选一个文件域；若现有接口足够则不加生产接口。
   新能力默认关闭，新增聚焦测试与负控制；主代理复验逐脚/NC、lint 和视觉。不得夹带 CLI/DSH 或整页扩展。
2. **547G3：30 件辅助整页。**G2 通过后才另写任务书；逐岛记录 agent 调整、机器检查与视觉结论。
   结果只记 `agent-adjusted`，不冒充 547F 自动整页通过。
3. **547G4：真机验收。**辅助离线三关后才在 `test V4` 新页标定真实 profiles 并走 plan/apply/lint、
   宿主 netlist、DRC、渲染和持久化；保留 P38、P39 和 Board2 P1。删页与其他破坏操作另行确认。
4. **自动线不取消。**547D 从 auto 暴露的 LED2/LCD_SDA 标签走廊继续；547E 再做默认关闭的
   二件串联；547F 最后回完整 30 件规格做自动整页三关。首轮先串行做 G1，不与 D 并发改生产或跑全量。


## 547G1 交卷段（子代理，2026-11-07）

**结论：现有校验器能消费 agent 单岛几何，无需新引擎；缺的是入口与记账，不是判据。** 几何注入点在**文档层**
（`core/layoutplan.py:463/670/709`，`kind=boardwise-layout-plan`、`planVersion=1`），不在编译器：
`islandcompile.compile_island`（`engines/islandcompile.py:202`）的图由摆放器产出、无注入点。

**真实入口（本批实际调用过的）**：`readability.check`（`engines/readability.py:829`，配
`ReadabilityScope`（`:478`）判本地图）→ `drawcompiler.island_gate_violations`（`:9876`）→
`readability.soft_floor_violations`（`:2597`）→ `drawcompiler.check_grammar`（`:16142`，走 `grammar_checker`
钩子，即 `draw compile` 的同一语法层）→ `svgpreview.render_svg`（`engines/svgpreview.py:97`）→
`drawapply.module_plan`（`:1033`，`LayoutPlan→ChangePlan`，要求 source 摘要/分区/库几何/LSCS+value）。
`draw lint`（`commands/draw.py:446` → `drawlint.run_lint`（`:1926`））吃 `sch.geometry` 快照 + 宿主 SVG，
仓库无 `LayoutPlan→sch.geometry` 序列化器 → 本批 **blocked**。

**草稿**：`evidence/547/g1/wifi.agent-plan.json`（`sha256=8d0a4c5ce8f69fcfce346c24582a91320966a6b20f425132cd1fa6565307fbec`，
`geometrySha256=61c41eae77cbc9e3…`），6 件/9 段/4 旗标/8 标签/12 文字/0 junction；`provenance=agent-adjusted`
只写在 `notes`（LayoutPlan 无 provenance 槽），未用参考页坐标、无 Python/eval、电路网与 NC 未改
（`source` 绑定 547A 单岛规格原始摘要 `bce498ff…`/`1ce07716…`）。渲染 `wifi.agent-plan.svg`
（`sha256=d5a95981589aa17d…`），机器读数 `readability.json`。

**实际读数**：hard=0、refusing=0、tolerated=0、`soft_floor_violations=[]`、`ok=True`；逐脚反推网表 8 组
＝7 网＋1 隔离脚，17 只脚已连，`J2.8(IO2)` 声明 NC 不接触导体；crossings=0、bends=1、wire_length=1690、
unaligned_pairs=5、min_text_gap=0（TXD/RXD 两条宿主印刷行 edge-to-edge 相接，非 overlap 违规）、
occupied=5.30%。**`check_grammar` 报 6 条 `grammar-relation-broken`**（R4/R5/R6 的 near/left-of 不成立）：
为避开 10 单位脚距的文字挤压把核心转 180°，语法层按符号本地方向判左右，不接受 → **草稿未过语法层**，
不得当成单岛试点通过。`module_plan` 被拒（缺 LCSC 事实，未编造）。视觉 **not-run**（无图像工具）。

**命令与计数**：`.venv/Scripts/python.exe .tmp_547/g1/build_plan.py`（写计划）、`… .tmp_547/g1/run_gate.py`
（闸+渲染+ChangePlan 探测）、`pytest tests/test_053b_readability.py tests/test_538_island_scope.py
tests/test_538_island_compile.py tests/test_054_drawapply.py -q -n 4 --dist loadfile
--basetemp=.tmp_pt_547_g1` → **179 passed**（12.4 s）。仅写 `evidence/547/g1/`、`.tmp_547/g1/`、本段；
未改 `src/`、测试、connector、dsh-plugin，无 git 写、无真机、无 daemon。

**G2 最小文件域（详见 `evidence/547/g1/gaps.md`）**：若只要求草稿可机器复核并可重跑 → **无需生产改动**
（复用上述公开函数，一条 `tests/` 用例即可固化）；若要求命令入口 → `src/boardwise/commands/draw.py`
（`--layout` 或 `draw check-layout`）＋ `src/boardwise/cli.py` dispatch（CLI，须单独批）；若要求机器可读
provenance → `src/boardwise/core/layoutplan.py` 加默认空槽（独立兼容批）。落地前必须先补 LCSC 事实。

## 547G1 主代理复验（接口通过，草稿判废）

- 主代理复跑同一闸链与四个邻域文件：**179 passed**；hard/refusing/tolerated=0、软下限为空、
  17 只脚有导体且 J2.8 隔离，与交卷一致。`readability.json` 的 6 条语法 finding 仍成立，
  不得被 `readability.ok=True` 吞掉；`draw lint` 仍 blocked，ChangePlan 仍缺 LCSC。
- 主代理通过本地 HTTP + 内置浏览器亲眼看了 `wifi.agent-plan.svg`：上拉和去耦远离宿主形成长轨，
  信号长梳齿与远端电阻排像两张分离图，供电脚—电容—回流阅读路径不成立，**视觉判废**。
- 证据 `evidence/547/g1/main-review.md`。G1 的接口问题已经回答，草稿不是 G2 可交付基线；
  不重写 G1 候选，下一批另存 G2。

## 547G2：WiFi 单岛几何重做（当前；先不加生产接口）

**唯一目标**：用既有 LayoutPlan 文档和校验函数得到一份语法、硬闸、逐脚与主代理视觉都通过的
WiFi `agent-adjusted` 单岛；不先解决公开 CLI、provenance 新字段或离线 `draw lint` 入口。

- 只读 G1 接口记录、547A WiFi 规格与 SOP；可写 `evidence/547/g2/`、`.tmp_547/g2/` 和本任务书
  一次交卷段。G1 evidence 不得覆盖；不得改 `src/`、tests、CLI/shared、connector、dsh-plugin、
  原 SmartMedicineBox，不做 git 写、删文件或真机操作。
- 以 G1 判废原因为输入，恢复语法接受的宿主朝向；上拉和去耦回到服务脚附近，用局部旗标取代长轨，
  保持功能岛与电路语义。不得改 grammar/readability、删器件/网名、短接 NC、隐藏冲突文字或抄参考页坐标。
- 新计划必须在 notes 记 `provenance=agent-adjusted` 与逐项几何理由，source 继续绑定 547A WiFi 规格；
  一次性生成/验证脚本只放 `.tmp_547/g2/`。
- 机器验收：`LayoutPlan.load`；同一 `readability.check + check_grammar`；`grammar_findings=[]`、
  hard/refusing=0、软下限为空；独立逐脚必须得到 7 网、17 只有导体脚、J2.8(IO2) 无导体，且网名/分区不改。
  保存原始 JSON、SVG、计划与 geometry 哈希。`module_plan` 缺 LCSC 与离线 `draw lint` blocked 要明示，
  不伪装通过；不为了消拒绝编造 LCSC。
- 复跑 G1 的四个邻域文件，独立 basetemp `.tmp_pt_547_g2`；不跑全量。子代理没有视觉工具就标 not-run，
  主代理亲眼复核后才关闭 G2；视觉不通过则保留 negative evidence 再修，不落真机。
- 最多 40 步或 30 分钟。交卷 ≤2000 字，列前后几何、实际命令/计数、哈希、剩余入口/事实缺口；
  只 append 一次并独立计数。需要生产接口才能满足上述条件时停止交回，不得顺手扩域。

## 547G2 交卷段（子代理，2026-11-07）

**结论：单岛几何重做完成，机器三关全清（hard/refusing/tolerated=0、grammar_findings=[]、soft_floor=[]），
逐脚 7 网/17 只导体脚/NC 隔离；视觉 not-run，待主代理亲验。** 未改一行生产代码、未动规格网表与 NC。

**几何（对照 G1 判废点）**：①J2 恢复 **rotation 0**（语法按符号本地方向判 left-of/near，转 180° 必 6 条失败）；
②R4/R5/R6 回到 **EN/RST/IO0 自己那一行**（x=-144，距核心 144–165），pin2 直连本脚，3V3 端各 20 单位短线接
**自己的局部 +3V3 旗标**（3 个，无共享轨）；③C8/C9 卡在 **3V3 引脚本段（y=40→120）与 GND 引脚本段
（y=30→80）之间**，成对用局部 +3V3/GND 旗标收尾 → 供电脚→电容→本地回流是一条短环；④ESP_TXD/ESP_RXD 为
80/145 单位口岸，名称行落在核心本体之外，EN/RST/IO0 不再重复标注；⑤J2 位号+型号移到无引脚的一侧。
读数对比：wire_length **1690→954**，crossings 0，bends 4/14 根，旗标 5 个（4×+3V3 + 1×GND），0 junction。

**实际命令与计数**：`build_plan.py`（写计划）→ `run_gate.py`（`LayoutPlan.load` + `readability.check`
（`ReadabilityScope(parts=6)`，`pageBox=[-220,-160,140,180]`）+ `check_grammar` + `island_gate_violations` +
`soft_floor_violations` + `render_svg` + `module_plan` 探测）→ `pin_audit.py`（自写并查集，不复用
`readability._derive`）。读数：ok=True、hard=0、refusing=0、tolerated=0、grammar=0、floor=[]；7 网各 1 个连通
分量、17 只有导体脚、`J2.8(IO2)` 零导体；crossings=0、bends=4、wire_length=954、occupied=10.09%。
聚焦测试 `pytest tests/test_053b_readability.py tests/test_538_island_scope.py tests/test_538_island_compile.py
tests/test_054_drawapply.py -q -n 4 --dist loadfile --basetemp=.tmp_pt_547_g2` → **179 passed（21.3 s）**。

**哈希**：计划 `3b3b17568f2aba15…`（`geometrySha256=a1ce529691dd1ee9…`，`source` 仍绑定 547A 单岛规格
`bce498ff…`/`1ce07716…`）；SVG `80f8b207f3e8994f…`（标题 `547G2 WiFi island (agent-adjusted)`）；`readability.json` `c4528208…`；`pin-audit.json`
`c6536c91…`。全部落在 `evidence/547/g2/`（含 `README.md`），一次性脚本仅 `.tmp_547/g2/`；G1 证据未覆盖。

**未覆盖 / 阻塞（不伪装通过）**：视觉 **not-run**（本子代理无图像读取，须主代理亲眼看 SVG 后关闭 G2）；
离线 `draw lint` **blocked**（只吃 `sch.geometry` 快照 + 宿主 SVG，无 LayoutPlan 入口，未拿 SVG 冒充）；
`module_plan` **blocked**（`J2 has no LCSC number…`，未编造 LCSC）；库符号全部 `uncalibrated`，落地前须真机标定。

**是否需生产改动**：不需要。G1 结论不变——`LayoutPlan` + `readability.check(scope=…)` + `check_grammar` +
`island_gate_violations` + `soft_floor_violations` + `render_svg` + `module_plan` 已足够；本轮所有失败都是
几何取舍问题，靠调坐标解决，未触碰接口。剩余入口缺口（`--layout` 命令、provenance 槽、`sch.geometry`
适配器）继续留待各自批次。

## 547G2 主代理复验（通过）

- 主代理独立复跑 `run_gate.py` 与 `pin_audit.py`：grammar=[]、hard/refusing=0、软下限为空；
  7 网与声明成员一致，17 只有导体脚，J2.8(IO2) 无导体。四个邻域文件 **179 passed**。
- 主代理通过本地 HTTP + 内置浏览器查看全图并裁切放大：三个上拉各在自己的 EN/RST/IO0 行，
  C8/C9 靠近供电/地脚，TXD/RXD 与电阻文字无实质重叠，长轨问题已消除，**离线视觉通过**。
- 最终 SVG 标题已改为 547G2，geometrySha256=`a1ce529691dd1ee99aa234bf9b8faa6f902537120d23deb4bd6a9dbda4cb12e5`，
  SVG sha256=`80f8b207f3e8994fec0c7da82897d566e7472b705fdded72c5a9fc603de07dea`。
  证据 `evidence/547/g2/main-review.md`。离线 draw lint、LCSC、真实 profiles 和真机仍未通过/未执行。

## 547G3A：整页集成合同与岛候选清单（当前，与G3B并行）

**唯一目标**：确认 PageLayoutPlan 的真实组装/校验/渲染链，准备全页独立逐脚脚本和除 MCU 外的
岛候选；不完成整页、不改生产。

- 可写仅 `evidence/547/g3/integration/`、`.tmp_547/g3/integration/`；不写任务书交卷段，
  由主代理统一记账。不得改 src/tests/CLI/shared/connector/dsh-plugin/原工程，不做git/删除/真机。
- 窄读 `core/pagelayoutplan.py`、`engines/pagecompiler.py`、`engines/readability.py`、
  `engines/svgpreview.py`、`commands/draw.py` 的直接相关函数。特别核实 page document 在
  plan/apply/discard 的既有入口，更正G1只看了单岛而遗漏的页面入口，不虚报新能力。
- 对 lcd/imu/env/bmp280_optional/uart1/swd 重跑或提取各自自动岛候选；WiFi使用G2，MCU留给G3B。
  不覆盖547A证据，不读参考页坐标。每个候选记录来源（automatic/agent-adjusted）、哈希与机器读数；
  没有候选就保留原始拒绝，不能凑数。
- 产出一个明确标注 **partial smoke** 的页面文档/渲染，验证LayoutPlan平移、PageModule frame/
  internalGeometrySha256、page source和PageLayoutPlan.load；partial不能冒充30件整页。
- 准备可复用的整页组装与独立逐脚脚本（后者不复用readability._derive），最终必须能核对30件、
  31网、5NC及额外短路；本批可用partial负例验证脚本会拒绝缺件，不得把partial报pass。
- 交付 `interface-map.md`、`candidate-inventory.json`、脚本与原始报告。最多35步/25分钟，
  不派helper、不跑全量。交回真实入口、候选数量、最小剩余缺口。

## 547G3B：MCU岛agent-adjusted几何（当前，与G3A并行）

**唯一目标**：为自动编译0候选的13件MCU岛做出可机器复核的人工局部几何；不解决整页打包。

- 可写仅 `evidence/547/g3/mcu/`、`.tmp_547/g3/mcu/`；不写任务书交卷段，由主代理统一记账。
  不得改src/tests/CLI/shared/connector/dsh-plugin/原工程，不做git/删除/真机，不派helper。
- 范围恰为 U1、C1/C2/C3、R1/R2/R3、D1/D2、S1–S4、BZ1，保持547A电路网/NC/岛归属。
  agent可显式给几何，但不得删串联电阻、合并KEY网、隐藏冲突文字或把失败改称automatic。
- 成对LED串联支路同向、同节距，GPIO→R→LED→GND逐脚真实连通；四键各自GPIO与3V3，
  不短自己的KEY网；去耦/NRST/BOOT0/蜂鸣器靠近各自服务脚；SWCLK/SWDIO/LCD_SDA等标签带不得穿线。
- notes记录provenance=agent-adjusted与每组几何理由。用完整547A规格+ReadabilityScope(parts=13)
  跑同一 readability+grammar+软下限链；独立逐脚按MCU声明网逐网核对并检查未声明短接。
  保存计划、SVG、原始gate/pin报告和哈希。语法不支持二件串联时保留最小失败，不能忽略finding过闸。
- 复跑 `test_547_shared_branch_nets.py`、`test_547_repeated_shunts.py`（后者允许既有strict xfail）
  及G1四个邻域，独立basetemp `.tmp_pt_547_g3_mcu`，不跑全量。主代理视觉后验。
- 最多40步/30分钟。若必须改生产才能通过，交回最小证据，不顺手扩域；不与G3A共享任何写文件。

## 547G3A/B 主代理复验（接口可用，候选未验收）

- G3A的PageLayoutPlan/页apply/discard入口与partial smoke可用；主代理复跑 `--require-full`
  负例：16/30件、0/31网、5/5NC、0短路，缺件必拒。六个自动岛均有3V3旗标义务缺失，
  LCD/BMP280另有弯数下限失败，只能作为待修几何来源。
- G3B复跑 **193 passed / 1 strict xfailed**；MCU硬闸/软下限为0，模块切片语法为0，
  31网58脚匹配。全量presentation语法存在8 core装订限制，LED串联无语法绑定，均不得隐去。
- 主代理亲眼看了MCU SVG，确认扇出与成对支路已有结构，但发现输入规格自相矛盾：
  assumptions/mcu.role说C3=NRST滤波、R1=BOOT0下拉，circuit却把C3.1/R1.1放3V3、
  C3.2/R1.2放GND，NRST/BOOT0只剩U1单脚网。当前MCU候选判废，不用“匹配旧规格”放行。
- 任务书中的“13件”是主代理笔误；547A mcu实际为**14件**，后续一律按14件。
  证据 `evidence/547/g3/main-review-a-b.md`。

## 547G3C：NRST/BOOT0规格纠错（当前，先于重画）

**唯一目标**：保留547A原始证据，另产一份与显式假设一致的纠正版CircuitSpec；不改生产、不改网数。

- 可写仅 `evidence/547/g3/spec/`、`.tmp_547/g3/spec/`；不得覆盖547A、G1/G2或G3A/B证据，
  不得改src/tests/CLI/shared/connector/dsh-plugin/原工程，不做git/删除/真机，不派helper。
- 从 `.tmp_547/gen_specs.py` 复制一次性生成器到新tmp域，仅纠正两处成员：
  **C3.1：3V3→NRST；R1.1：3V3→BOOT0**。C3.2/R1.2仍GND；其余电路、30件/31网/5NC、
  presentation与库逐字不变。输出 `evidence/547/g3/spec/smart_medicine_box.circuit.json`。
- 新写 `corrections.md`：原文件/哈希、纠正后文件/哈希、两处成员diff；明确NRST电容/BOOT0下拉
  仍是assumed而非固件observed。保留旧规格作为错误证据，不篡改历史。
- 用CircuitSpec.load/PresentationSpec.load实测新合同，独立断言旧成员已移除、新成员恰好出现一次、
  其它网逐字相同；保存JSON报告。不得顺手调整R1/C3数值或添加reset开关等新器件。
- 最多20步/15分钟，不跑全量。交回新circuit sha256与差异读数；后续MCU和其他岛统一改用这份规格。

## 547G3C 主代理复验（通过）

- 主代理复跑 `verify_g3c.py`：**49/49 passed**。新circuit sha256=
  `946494753452ee0f574235943435b6ebcdfd49da119a64e532787de74ba0b1d6`；
  原circuit仍为 `d2b95507235e9414b9ed8411d7791b2b5498ee4f54b0cb5c09a90f848510d285`。
- 只有C3.1→NRST、R1.1→BOOT0两处成员变化；30件/31网/5NC及其它网不变。
  连接仍为assumed而非observed。后续所有岛/页source必须使用新circuit。

## 547G3D：MCU的NRST/BOOT0重画（与G3E并行）

- 可写仅 `evidence/547/g3/mcu_corrected/`、`.tmp_547/g3/mcu_corrected/`；不改旧候选、
  src/tests/CLI/shared/connector/dsh-plugin/原工程，不写任务书，不做git/删除/真机，不派helper。
- 以G3B几何为起点，但source改用G3C新circuit。C3移到NRST服务脚、R1移到BOOT0服务脚，
  各以短导线连接对应脚与本地GND；不得再把它们接3V3。C1/C2保持供电去耦。
- 尽量保留已具结构的LCD/ESP/LED/KEY扇出；若NRST/BOOT0仅为岛内支路，不为制造跨岛口岸而保留无意义标签。
  notes逐项记录纠正与provenance=agent-adjusted。
- 重跑readability+模块语法+软下限、独立逐脚/额外短路；明确全量presentation的8 core限制和LED串联无语法绑定。
  保存计划/SVG/原始JSON/哈希。复跑G3B六个测试文件，basetemp `.tmp_pt_547_g3_mcu_corrected`。
- 主代理视觉后才验收；最多40步/30分钟，不跑全量，需要生产修改则停止交回。

## 547G3E：六个外围小岛受控修整（与G3D并行）

- 范围为 lcd/imu/env/bmp280_optional/uart1/swd；WiFi用已验收G2，不在本批。
  可写仅 `evidence/547/g3/peripherals/`、`.tmp_547/g3/peripherals/`；不改其他证据、
  src/tests/CLI/shared/connector/dsh-plugin/原工程，不写任务书，不做git/删除/真机，不派helper。
- 从G3A自动候选出发逐岛补电源/地旗标并修绕线；source统一从G3C新circuit重新投影。
  每岛输出独立LayoutPlan、SVG、gate/pin JSON，notes记录provenance=agent-adjusted、
  自动候选来源及每一处人工修改；不得只改报告或把旧自动候选改个名字。
- 每岛必须readability hard/refusing=0、模块grammar=[]、软下限=[]，独立逐脚与NC通过。
  LCD消除单根6弯；BMP280保持optional标识和env阅读关系；IMU的INT/XDA/XCL保持NC；
  uart1/swd的3V3/GND用旗标，信号标签贴自己的载体。不得改电路网、删件或隐藏文字。
- 复跑G1四个邻域文件，basetemp `.tmp_pt_547_g3_peripherals`，不跑全量。
  主代理逐岛视觉后才验收。最多40步/30分钟，需要生产修改则停止交回。

## 547G3D/E 主代理复验（外围通过，MCU局部返修）

- 主代理统一复跑六个测试文件：**193 passed / 1 strict xfailed**；MCU gate/pin与六岛
  gate/pin/不变式均复现通过。C3.1=NRST、R1.1=BOOT0、其余31网与NC正确。
- 主代理通过紧边界viewer逐岛看了 lcd/imu/env/bmp280_optional/uart1/swd：功能归属、
  电源/地旗标、信号载体、NC与optional标记均可读，**六岛离线视觉通过**。
- MCU首轮C3位号撞自己的GND旗名；局部修正后，C3 value又撞R1的GND名称行，仍不验收。
  已退回按真实名称盒修正，主代理将再看局部。机器hard=0从未替代视觉裁决。

## 547G3D最终视觉复核（通过）

- 主代理再次查看全图并裁切NRST/BOOT0：C3位号、100nF、R1与两处GND名称均分离，
  导线和支路归属清楚，**MCU最终离线视觉通过**。最终geometry前缀 `f5e19416c034…b992`，
  电气未因两轮文字修正改变。完整证据 `evidence/547/g3/main-review-d-e.md`。
- 另实测source口径：circuit对象摘要 `617c9dc3893ce663ab66ad056a06f1a4d5ebfc68d03f11b399f6806b0fd94f71`，
  presentation对象摘要 `18f900d5eea6aa3bb6732461ef691374651e6b893ff62153351f92b5d831d5d3`；
  与文件字节哈希不同，G3F必须使用对象摘要。
- 主代理又指出G3A命名NC归一漏洞：J2.IO2不能误建成J2.8后仍查IO2；
  G3F必须以真实接导体负例证明NC审计有效。

## 547G3F：30件整页组装与双层页面闸（当前）

**唯一目标**：把八岛合成一份30件/31网/5NC的agent-adjusted PageLayoutPlan，并通过页面域、
合并图、独立逐脚与主代理视觉；不把一次组装脚本变成公开自动编译能力。

- 输入固定：G3C circuit `94649475…`、547A presentation/library、G2 WiFi、
  G3D最终MCU、G3E六岛plan。可写仅 `evidence/547/g3/page/`、`.tmp_547/g3/page/`；
  不改旧证据、src/tests/CLI/shared/connector/dsh-plugin/原工程，不写任务书，
  不做git/删除/真机，不派helper。
- 修正G3A一次性组装的两处漏洞：端口必须从**本岛局部几何**收集，不能给每岛分配全部跨岛网；
  frame必须包含器件+引脚、文字/标签、旗标glyph、导线及margin。保留origin平移和
  internalGeometrySha256合同，flow保留presentation声明。**页source必须用加载对象的
  `CircuitSpec.sha256()` / `PresentationSpec.sha256()`，不能用文件字节sha256**；
  主代理实测纠正版circuit二者为 `617c9dc3…`（对象）≠`94649475…`（文件），presentation为
  `18f900d5…`（对象）≠`93bd379e…`（文件）。文件哈希仅写notes作溯源，并加断言防止apply stale。
- page_box=`0,0,1170,825`；按信号流人工布置八岛，env与bmp280_optional保持attach阅读关系。
  离线保守标题栏占位可用 `(470,0,1170,180)`，必须注明真机还要重读实际图幅，不能冒充实测。
  不得为塞页而缩放器件、删支路或改岛归属；放不下就交最小拒绝证据。
- 必须依次实跑 `readability.check_page` 与 `readability.check`：page/drawing hard=0、
  软下限=[]、PageLayoutPlan.load往返哈希稳定。合并页不对8 core跑单语法；改为汇总八岛各自
  grammar=0证据，并明示LED串联无语法绑定。证据只能写实际执行的checker，不得自填pass。
- `page_pincheck.py --require-full` 必须30/30件、31/31网、5/5NC、0额外短路。
  先修正审计器的命名脚/编号归一：声明NC的 `J2.IO2` 必须落到物理脚 `J2.8`，
  不能因它不在pin_net而另建键。做三个临时负例：①给假端口/异岛端口，组装器的
  `validate_ports`必须拒绝（`check_page`不读PagePort，不能冒称它能发现）；②让两个frame重叠，
  `check_page`必须拒绝；③给J2.IO2接导体，独立审计必须失败。原候选不受影响，负例单独存tmp/evidence。
- 渲染全页frames+图元，保存plan/page/gate/pin/哈希与组装脚本；主代理逐岛和整页视觉后验。
  复跑G1四邻域+547两文件，basetemp `.tmp_pt_547_g3_page`，不跑全量。
- 最多40步/30分钟。离线draw lint仍blocked，真机G4另验；需要生产修改则停止交回。

## 547G3F 主代理复验（547G3通过）

- 主代理复跑六个聚焦文件：**193 passed / 1 strict xfailed**；check_page/check均hard=0，
  软下限=[]；独立逐脚 **30/30件、31/31网、5/5NC、0短路**，102只有导体脚。
- 四个负例全有效：未平移端口、异岛/假锚点、重叠frame、NC接导体分别被对应闸拒绝。
  最终顺序 negatives→run_gates→pin 后页文档仍为pass，两层checker齐全。
- 页source使用对象摘要，flow=7，54个ports均为页坐标；pageGeometrySha256=
  `7275279ab8cd391aed9d00243cb67f315e7045154fdc4edf23618014af7c1244`，plan=
  `97e551fcbb19ad38908ed323ef7cef2bae9c8012e67c30ff8b840c25c101cc83`，
  page文件sha256=`860d8decb196c82a880729b10abcb57f58fcf2ee989ce21fa1524713767b0a34`。
- 主代理看全页及底部IMU，八岛功能/支路/跨岛标签/标题栏占位均可接受，**整页视觉通过**。
  证据 `evidence/547/g3/main-review-f.md`。547G3完成；离线draw lint和真机未执行，进入G4。

## 547G4A：真实器件与引脚映射清单（当前，只读盘点）

**唯一目标**：为30件逻辑器件找出可真实放置的库器件和所需profiles/pin映射；
不把货架选择冒充原板事实，不碰真机。

- 可写仅 `evidence/547/g4/facts/`、`.tmp_547/g4/facts/`；不改其他证据、src/tests/CLI/
  shared/connector/dsh-plugin/原工程，不写任务书，不做git/删除/daemon/真机，不派helper。
- 以G3C circuit与547A library的30件/18个占位profile为输入，只读检索blocklib货架及现有公开规格。
  每件记录：逻辑身份、value、候选MPN/LCSC/来源、选择性质（exact-MPN或generic-module-boundary）、
  所需真实profile、引脚名/编号映射。没有确切依据就写missing，留 live-search 查询词，禁止猜LCSC。
- 特别核对STM32G431RBT6、ESP-01S、ST7789/MPU6050/AHT20/BMP280模块边界、通用R/C/LED/KEY/BZ/
  排针和电源旗标。若用排针表示模块，必须给数值引脚映射并明确不是原板制造器件还原。
- 产出 `recipes-draft.json`、`pin-map.md`、`missing.md`：区分电路observed/assumed与器件选择
  library-selected；现有货架中的历史工程引用只能证明“库里有这个件”，不能证明原SmartMedicineBox实板。
- 最多30步/25分钟，不跑全量。交回已确定/缺失数量、唯一profile数量、可能的命名脚冲突和G4B最小动作。

## 547G4A 主代理复核（事实盘点可用，输入缺口必须关闭）

- 子代理盘点30件：25个exact-MPN候选、4个模块边界、C2缺器件；13/18占位profile有
  库符号线索，5个缺失。离线符号表仅作对照，**不能替代真机profiles**。
- 已核 `pin-map.md`/`missing.md`：U1 VDD/VSS一名四脚、NRST/BOOT0别名、J2.3V3↔VCC、
  LED真实1=C/2=A、U4.CSB漏网均是实缺口；另有VREF+未表达。主代理回查固件确认KEY4
  为NOPULL且从未读取，原假设的“外部10k下拉”在30件规格中没有器件。
  为不擅自扩成31件，KEY4只按**未启用保留项**记账，启用前必须外加10k，不假装它已有。
- 子代理自报38步，超过30步预算8步且已披露；后续复用其上下文但严格限30步。
  证据 `evidence/547/g4/facts/`。货架/历史工程只证明库里有件，不证明原板选型。

## 547G4B：live电路与库引脚合同（当前，先于真机）

**唯一目标**：从G3C派生一份保持30件/31网/5NC、但能被真实库引脚表达的live CircuitSpec；
不改生产，不碰真机。

- 可写仅 `evidence/547/g4/spec/`、`.tmp_547/g4/spec/`；不得覆盖G3/G4A证据、
  src/tests/CLI/shared/connector/dsh-plugin/原工程，不写任务书，不做git/删除/daemon/真机。
- 输出 `live.circuit.json`，仅作以下有证据的修正并写 `corrections.md`：
  ①U1.VDD→16/32/48/64、U1.VSS→15/31/47/63；②U1.28(VREF+)加入3V3（assumed与VDDA同轨）；
  ③NRST→7(PG10-NRST)、BOOT0→61(PB8-BOOT0)；④J2.3V3→J2.8(VCC)，其余同名脚不改；
  ⑤D1/D2按高有效与真实1=C/2=A交换1/2：阳极2接各自LEDx_A、阴极1接GND；
  ⑥U4.CSB加入3V3，落实原I2C模式假设。不得改网id、器件值、功能范围或添加/删除器件。
- KEY4保持原30件和原KEY4网，不虚构已装下拉；在 `open-items.md` 写明固件NOPULL/未读取、
  当前是未启用保留项，启用前必须外加10k。后续图面需要保留这条注释，不能藏。
- 25个exact-MPN候选可按recipes-draft写入lcsc字段；C2/J1/U2/U3/U4缺失或模块边界没有
  最终选择前不得猜C码。器件选择在外部 `selection-map.json` 记library-selected，不改成observed。
- 实际用CircuitSpec.load验证；独立断言上述引脚集合、LED极性、CSB/VREF、每脚唯一网、
  30件/31网/5NC不变。保存 `verification.json`、文件/对象哈希与 `pin-alias-map.json`。
  验证审计器能按编号/名字alias找到真实脚，不能复用“名字找不到就忽略”的旧路径。
- 最多30步/25分钟，不跑全量。交回修正计数、剩余missing、对象摘要与G4C最小动作。

## 547G4B 主代理复验（通过）

- 主代理重跑 `gen_live.py`：33项全过、11处网成员修正、100脚解析、26个模块边界脚明确unresolved；
  6个alias负例有效。`CircuitSpec.load`确认 **30件/31网/5NC**，live对象摘要=
  `c0762e22861ee5e6aada693e9756eca98d3bcc2a9752d988abc76398345065a3`。
- LED极性、VDD/VSS多脚、VREF+、CSB、NRST/BOOT0别名已关闭；C2、四个模块边界、
  PWR-+3V3与KEY4注释仍是公开未决项。证据 `evidence/547/g4/spec/`。

## 547G4C：test V4身份、在线选型与标定空页（当前）

**唯一目标**：在逐字授权的 **test V4** 中确认身份，完成缺失器件在线选型并创建一个
专用于标定的空页；本批不放器件、不做最终apply。

- 先 `bridge status`，再 `doc.list` 取得最新instance、工程名和页面树。焦点工程名必须逐字为
  **test V4**；保留P38、P39和Board2 P1，原SmartMedicineBox及其他窗口禁写。
  若daemon/身份不符，停止并保存异常，不自行替代工程。
- 写操作仅限 `test V4` 的**一个新标定页**（建议名 `547G-calibration`），
  `sch.doc.new confirm=true`前再次核对instance与页面特征。已存在同名/同用途页时不得重复建，
  先交回身份请主代理裁决；不得删除任何页或探针件。
- 只读 `lib.device.search` 复核已选器件，并搜索C2 4.7uF/0603、1x8或2x4、1x6排针及
  PWR-+3V3真实字形。优先真实模块；没有就用排针表达模块边界，不能换裸芯片或改值/封装。
  每个最终LCSC/deviceUuid/MPN必须来自实际在线返回，禁止猜编号。
- 输出 `identity.json`、`search-log.json`、`selection-final.json`、新页uuid与doc.list前后证据。
  完成C2/J1/U2/U3/U4和旗标选择，更新selection-map的最终列；仍未解决就停止，不开profile标定。
- 可写证据 `evidence/547/g4/live/select/`、`.tmp_547/g4/live/select/`；不写任务书，
  不改src/tests/CLI/shared/connector/dsh-plugin/原工程，不做git/删除，不派helper。
- 最多35步/25分钟。交回身份、页面uuid、选型数量与G4D标定清单。

## 547G4C 主代理复核与续批

- 子代理在 `test V4` 新建唯一标定页 **P40 `eb22558f9f36db43`**，创建前R1身份完整；
  未放器件。C2选C466777，J1/U2选C492407(1x8)，U4选C492405(1x6)，均来自在线搜索。
- 子代理遇到daemon中断时，主代理查明是先前启动任务300s超时所致，已改用持久受控任务恢复；
  不把它误报为工程损坏。主代理重新 `doc.list` 确认P40仍在，`sch.readback`只有1个sheet、
  primitives=[]，即空页（componentCount包含sheet，不能读成有一颗器件）。
- U3的1x4在线复核、25个exact-MPN deviceUuid复核与真实profiles尚未完成。G4C不以部分选型记完成，
  由G4D先补齐再标定。

## 547G4D：P40真实profiles标定（当前）

**唯一目标**：在既有P40上完成全部器件/旗标的真机几何标定，产出可用于plan的profiles；
本批不做最终页apply、不删除探针。

- 写操作仅限实例 `inst-013606759-na2iblwm` 的 **test V4 / P40 `eb22558f9f36db43`**。
  先doc.list+readback核对工程名、P40活跃身份与空页特征；P38/P39/Board2 P1及其他窗口禁写。
  目标缺失、非空或身份不符即停止（R3/R2，不自行解释）。
- 先补U3 1x4和25个exact-MPN的在线deviceUuid复核，再放件。最终选型必须全部有实际在线返回；
  C2/J1/U2/U4沿用G4C结果，U3未定不得猜。
- 按既有SOP在P40分散放置每个唯一候选符号，`sch.component_pins` + `sch.geometry(bboxIds)`实测
  引脚偏移/长度/body。重点核U1 64脚、ESP-01S 8脚、LED C/A、1x8/1x6/1x4模块边界。
  电源/地用实际 `sch.place_power` 路径确认+3V3/GND真名，不得用VCC顶替。
- 输出 `profiles.json`（含各逻辑symbolRef→实测profile映射、库几何hash、deviceUuid/LCSC、
  原始readback与标定页坐标）、`selection-final.json`、`calibration-log.json`、P40回读。
  占位profile只允许作对照，任何引脚/body差异都必须记录，不能把离线值抄成实测。
- 不删除探针或页面，不做最终plan/apply/DRC，不新建第二页。可写证据
  `evidence/547/g4/live/profiles/`、`.tmp_547/g4/live/profiles/`；不写任务书，
  不改src/tests/CLI/shared/connector/dsh-plugin/原工程，不做git，不派helper。
- 最多40步/30分钟。交回唯一器件/profile数量、引脚总数、差异清单与G4E最小动作；
  未标定完整就停止，不许开最终页。

## 547G4D 主代理复核（标定通过，落件路径已核）

- P40保留13个器件探针+2个旗标（readback含sheet共16），18份profile全部
  `SymbolProfile.load`通过，122个profile引脚记录；25个exact-MPN和U3均完成在线复核。
- 主代理解析profiles文件确认18份可读。U1真实64脚/body±85.5×±165.5，ESP为8=VCC，
  LED为1=K/2=A，G4B live映射成立；15/18 body与占位不同，旧几何不得直接落图。
- `sch.place_component lcsc=`失败不需要新生产功能：`cli.py:13517-13552`已有
  精确 `lib.device.search`→`deviceUuid+libraryUuid` 重试，与本次实测相同。
  G4E必须使用现有fallback并保存其报告，不另造uuid旁路。
- 证据 `evidence/547/g4/live/profiles/`；探针未删除，P40不用于最终图。

## 547G4E0：最终live规格与真实profile绑定（当前，先于重排）

**唯一目标**：把四个模块边界映射到实际排针编号，补齐全部30件在线选型，
并证明live circuit的每个声明脚都能在18份实测profile中解析。

- 可写仅 `evidence/547/g4/live/spec/`、`.tmp_547/g4/live/spec/`；不改旧证据、
  src/tests/CLI/shared/connector/dsh-plugin/原工程，不写任务书，不做git/删除/daemon写/真机写。
- 从 `evidence/547/g4/spec/live.circuit.json` 派生 `final.circuit.json`：
  J1=VCC1,GND2,SCL3,SDA4,RES5,DC6,CS7,BLK8；
  U2=VCC1,GND2,SCL3,SDA4,XDA5,XCL6,AD0 7,INT8；
  U3=VDD1,GND2,SCL3,SDA4；U4=VCC1,GND2,SCL3,SDA4,CSB5,SDO6。
  这些是generic-module-boundary的编号映射，不是原板制造脚序。
- 从 `evidence/547/g4/live/profiles/{selection-final,profiles}.json` 补齐30件LCSC/MPN/
  deviceUuid/libraryUuid外部映射；C2/J1/U2/U3/U4用在线实测选择，不能猜。
  保持30件/31网/5NC和G4B全部电气修正，KEY4不加件。
- 输出 `final.circuit.json`、`device-map.json`、`verification.json`：真实
  CircuitSpec.load+18份SymbolProfile.load；逐网逐脚解析到真实number/name，
  不再允许unresolved。记录文件/对象hash、全部选择性质和LED/NC负例。
- 最多25步/20分钟，不跑全量。交回解析脚数、最终对象摘要与G4E重排输入。

## 547G4E0 主代理复核（通过）

- 子代理最终规格30件/31网/5NC，126/126声明脚（121网成员+5NC）全部解析到
  18份实测profile，0 unresolved；30件均有LCSC+MPN，26 exact+4模块边界。
- 主代理另用 `drawapply.load_library` 实读：**18 profiles / 122 pins**。
  final对象摘要=`391667fb9bbf3c0e735db24a47845c0bc74f3f4932306dd5197cb20d2c85a846`。
- 模块编号NC同步为U2.5/6/8；旧U2.XDA/J1.VCC负例会失败，LED极性/CSB/VREF保持正确。
  证据 `evidence/547/g4/live/spec/`。后续页source必须用该对象摘要。

## 547G4E1：真实profile的MCU岛重排（与G4E2并行）

- 可写仅 `evidence/547/g4/live/mcu/`、`.tmp_547/g4/live/mcu/`；不改旧证据、
  src/tests/CLI/shared/connector/dsh-plugin/原工程，不写任务书，不做git/删除/真机写，不派helper。
- 使用final circuit、547A presentation、实测profiles重排14件；旧占位坐标仅可作阅读结构参考，
  每个symbolHash/pin/body必须来自实测。保持R2→D1/R3→D2极性、四组VDD/VSS、VREF+、
  NRST/BOOT0、四键与蜂鸣器网。
- 保留LED成对、按键同向、信号扇出与本地旗标策略；C3/R1文字不得再撞旗名。
  S4附近加可读注释：**KEY4未启用/NOPULL/启用前需外加10k下拉**，不得画成已有电阻。
- notes记agent-adjusted和实测来源。跑readability+MCU切片grammar+软下限、独立逐脚/NC/短路；
  保存plan/SVG/gate/pin/hash。复跑G1四邻域+547两文件，basetemp `.tmp_pt_547_g4_mcu`，不跑全量。
- 最多40步/30分钟；主代理视觉后验，不能拿旧profile的通过记录替代。

## 547G4E2：真实profile的其余七岛重排（与G4E1并行）

- 范围 lcd/imu/env/bmp280_optional/uart1/swd/wifi；可写仅
  `evidence/547/g4/live/peripherals/`、`.tmp_547/g4/live/peripherals/`；限制同G4E1。
- 逐岛使用final circuit与实测profile重排，symbolHash/pin/body真实；保持G2/G3E电气和阅读关系、
  电源地旗标、IMU三个NC、BMP optional与WiFi上拉/去耦。
- 四个模块边界在图面注明generic header boundary（不是原板制造器件还原），数值脚与final circuit一致；
  不能用模块裸芯片或旧脚名代替。KEY4不在本批。
- 每岛readability hard/refusing=0、模块grammar=[]、软下限=[]、独立逐脚/NC/短路通过；
  保存plan/SVG/gate/pin/hash和每处人工调整。复跑G1四邻域，basetemp `.tmp_pt_547_g4_peripherals`。
- 最多40步/30分钟；主代理逐岛视觉后验，需要生产修改则停止。

## 547G4E1/E2首轮主代理复核（均未通过）

- MCU首轮hard=38（文字/旗标/穿体），逐脚脚本未跑通，不能进整页。主代理亲眼看图确认
  不是单点文字问题：真实64脚/10节距下，24面旗与信号口岸互相挤占，需要结构性重排。
- 其余七岛独立逐脚已全对，UART/SWD机器闸通过；LCD/BMP/WiFi有旗标硬错，
  IMU/ENV/LCD/BMP/WiFi还有S-11交叉，WiFi另有S-21，均不验收。
- 实测自动编译七岛也0候选，进一步说明本批必须记agent-adjusted，不能改记automatic。
  失败证据 `evidence/547/g4/live/{mcu,peripherals}/`，不覆盖。

## 547G4E1R：MCU供电汇流与信号走廊重排（续批）

- 新写 `evidence/547/g4/live/mcu_v2/`、`.tmp_547/g4/live/mcu_v2/`；旧失败候选只读。
  其它限制同G4E1，最多40步/30分钟。
- 主代理视觉裁决：不要逐点挪动旧图。按真实脚位重排供电/回流——就近同网脚可用短合法路径
  汇成少量本地组，每组一面旗，路径必须绕开信号标签带；不要为每脚机械塞一面旗。
  旗标glyph/名称行一律按实测box，禁止凭rot角度猜朝向。
- 左/右信号分别用不同深度扇出，器件块与标签带分开；NRST/BOOT0/BZ/LED/KEY各自有
  可读服务区。ESP_RXD等最下脚不得穿键块；S4注释保留。
- 先hard/refusing=0、软下限=[]，再修通独立逐脚alias并跑六个聚焦文件；仍失败就只交坐标证据，
  不进整页。

## 547G4E2R：外围旗标与交叉收口（续批）

- 新写 `evidence/547/g4/live/peripherals_v2/`、`.tmp_547/g4/live/peripherals_v2/`；
  旧失败候选只读。其它限制同G4E2，最多40步/30分钟。
- UART/SWD保持已通过几何；LCD/BMP先外移再落旗，IMU/ENV把供电支路移出端口行，
  WiFi按真实脚位重做上拉/去耦，不能只挪动失败点。目标hard=0、grammar=[]、软下限=[]、
  逐脚/NC/短路全过后再跑邻域；主代理视觉后验。

## 547G4E1R/E2R复核（进展但未过）

- MCU第二版hard 38→19，供电已改成少量本地组、扇出不再压本体，仍剩VSSA/BZ/R1及
  LED局部冲突；未跑逐脚，不验收。
- 外围LCD/IMU/UART/SWD达到hard/grammar/floor=0且逐脚通过；ENV剩文字、BMP剩S-11、
  WiFi因R4/R5朝向造成电气短接与23 hard，均不验收。继续第三批点修，保留v2失败证据。

## 547G4E1R2：MCU剩余19条点修（续批）

- 新写 `evidence/547/g4/live/mcu_v3/`、`.tmp_547/g4/live/mcu_v3/`；限制同前，最多40步/30分钟。
- 以v2 `README.md` 的剩余清单为唯一范围：VSSA旗朝向、BZ/VSS15/VDD16走廊、
  R1/VSS63与R1文字、BZ与LED地线/R2文字。保持已成立的供电分组、扇出和KEY4注释。
- 必须实际做到hard/refusing=0、软下限=[]，修通独立逐脚alias并跑六个聚焦文件；
  不再只交“下一轮建议”。若仍失败，保存逐项坐标和原始报告后停止交回。

## 547G4E2R2：ENV/BMP/WiFi最后收口（续批）

- 新写 `evidence/547/g4/live/peripherals_v3/`、`.tmp_547/g4/live/peripherals_v3/`；
  限制同前，最多40步/30分钟。
- LCD/IMU/UART/SWD保持v2通过几何；ENV只修C6文字与GND glyph，BMP只修GND支路交叉；
  WiFi按v2证据改R4/R5朝向使pin2朝核心、R6保持正确方向，C8/C9旗标落在真实连接点，
  消除junction/pin-line和S-11/S-21。七岛全部hard/grammar/floor=0、逐脚/NC/短路通过再跑邻域。

## 547G4E1R2/E2R2复核（仍未整页）

- MCU第三轮19→10，剩余VSS47、LED对/BZ、VSS15/BZ旗/C3文字、BZ文字四组局部。
  子代理曾把v3写到v2，随后用v2脚本恢复；主代理实测v2 geometry=
  `978e199b9f2f0ded569b7f4f0160e0131eb6d53838f3d2f69c8c85b0e8b6cc28`，恢复成立。
- 外围六岛达标，WiFi剩gnd_x旧旗坐标、EN/RST标签行、TXD名字压本体和两只3V3旗名互压。
  继续最后点修，不改生产。

## 547G4E1R3：独立执行者收口MCU（续批）

- 新写 `evidence/547/g4/live/mcu_v4/`、`.tmp_547/g4/live/mcu_v4/`；旧证据只读，
  禁止事项同前，最多40步/30分钟。
- 以v3为唯一几何起点，只处理其README四组：VSS47旗朝向、LED对/BZ横线、
  VSS15/BZ旗/C3文字、BZ文字与供电竖线。先核对OUT再运行，禁止覆盖v2/v3。
- 必须hard/refusing=0、软下限=[]，再跑独立逐脚与六个聚焦文件；不再只给建议。

## 547G4E2R3：WiFi最后四处（续批）

- 新写 `evidence/547/g4/live/peripherals_v4/`、`.tmp_547/g4/live/peripherals_v4/`；
  旧证据只读，禁止事项同前，最多40步/30分钟。
- 六岛沿用v3通过几何；WiFi同步gnd_x导线与旗标、分开C8/C9旗glyph、让EN/RST名字行
  不碰相邻导线、TXD名字放锚点右侧、两只3V3旗名错行。保持R4/R5/R6朝向和全部电气。
- 七岛全部hard/grammar/floor=0、逐脚/NC/短路通过后跑邻域并交主代理视觉。

## 547G4E1R3/E2R3复核（机器过，视觉与plan待办）

- MCU v4 hard=0、软下限=[]、独立逐脚31网/65只有导体脚/U1.PA6隔离/0短路；
  其余七岛均hard/grammar/floor=0、逐脚/NC通过。主代理统一复跑 **193 passed / 1 strict xfailed**。
- MCU子代理披露D1/D2位号仍压本体，视觉未签收；另有 `rm -f` 删除一次性tmp备份的纪律违规，
  无生产影响，已记档，后续不得再犯。
- `modulePlan` 报合法命名脚不存在。主代理实测U1 profile含PA3等名字，定位到
  `drawapply.py:1674-1678` 只比较pin.number；不能把改名当修复。

## 547F：module_plan命名脚/编号同脚校验（生产小批）

**唯一缺口**：`module_plan` 的岛分区校验必须把同一真实引脚的number与name视为同一身份，
未知token仍拒绝。不得改变其它布局/落地行为。

- 生产仅 `src/boardwise/engines/drawapply.py`；新测试仅 `tests/test_547_named_pin_plan.py`；
  证据 `evidence/547/f/`、`.tmp_547/f/`。不改cli/shared/connector/其它源码，不碰真机，不做git。
- 先加修复前必红用例：真实profile有 `17=PA3`、`7=PG10-NRST` 时，电路成员U1.PA3/U1.NRST
  不得被误判；原有编号路径不变；U1.PA4等不存在token仍抛DrawPlanError。
  重复VDD/VSS名字不得引入重复脚或改变既有netlist。
- 最小实现可让built parts同时声明其profile的真实number与非空name，不能简单跳过missing检查。
  保持未写新键时行为不变，不放宽后续live netlist。
- 跑新测试、test_054_drawapply及G1四邻域+547两文件，basetemp `.tmp_pt_547_f`；不跑全量。
  子代理给至少一个负控制；主代理随后做独立变异（去掉name身份必须红）+cp/hash还原。
- 最多30步/25分钟。交回根因、diff、前红后绿、邻域计数和是否暴露后续问题。

## 547G4E1V：MCU v5视觉复核（通过）

- 主代理用Windows原生栅格化PNG查看全图及失败局部：D1/D2位号已出本体，C1/C2文字已断开，
  R1与VSS63分离，C3、LED对、四键、蜂鸣器和KEY4注释均可读，**MCU离线视觉通过**。
- 证据 `evidence/547/g4/visual/mcu-v5-review.md`；v5 geometry前缀 `ca4a62f3…`。
  SVG footer仍误写v4，整页组装须改为最终547G标题，不能把标题当几何身份。
- 外围BMP的3V3与C7/GND/容值叠字、LCD/IMU/ENV同类名称行仍在v5修整批，未全过。

## 547G4E4：真实profile整页与ChangePlan（547F已通过；外围视觉收尾后开）

- 输入：final circuit对象 `391667fb…`、547A presentation、18实测profiles、MCU v5、
  外围v8。可写仅 `evidence/547/g4/live/page/`、`.tmp_547/g4/live/page/`；
  不改生产/旧证据/原工程，不写任务书，不做git/删除/真机写，不派helper。
- 沿用G3F的完整合同：页source用加载对象摘要、ports页坐标、flow=7、frame包含全部墨迹、
  internalGeometrySha256=局部图、env/BMP attach、保守标题栏占位 `(470,0,1170,180)`。
  真实profile导致尺寸变化时重新排frame，不缩放器件或改岛归属。
- 依次跑 `readability.check_page`、`readability.check`、独立 `page_pincheck --require-full`：
  page/drawing hard=0、软下限=[]、30件/31网/5NC/0额外短路；汇总八岛模块语法并保留
  8-core全量限制与LED串联无语法绑定。PageLayoutPlan证据按实跑结果写回pass。
- 用547F修复后的 `drawapply.module_plan` 实际生成ChangePlan，全部30件有真实LCSC/MPN、
  symbolHash和引脚。保存page/plan/gate/pin/哈希；后续命名脚、重复旗名或文字错误不得静默放过。
- 负例至少覆盖：未平移port、frame重叠、NC接导体、未知pin token。跑547F新测试+G1四邻域+
  547两文件，basetemp `.tmp_pt_547_g4_page`，不跑全量。主代理视觉后验。
- 最多40步/30分钟；未生成合法ChangePlan就不开最终真机页。

## 547G4E4 主代理复核（通过）

- A2整页 `page.verdict=pass`，双层hard=0、软下限=[]；30件/31网/5NC/0短路，
  ChangePlan为draw-module、30件全配方/真实引脚，四负例有效；主代理复跑 **197 passed / 1 strict xfailed**。
- 主代理看全页及局部，八岛关系与文字可读。最终元数据已改为547G，pageGeometry=
  `67ba373e49b985af26e0f619a78521dbb3407b7c20f0f44589e4e10c512c9790`，
  SVG=`155b8ab79b001aa0…`。证据 `evidence/547/g4/live/page/`。

## 547G4G：P41真实apply与机器三关（当前）

**唯一目标**：在P41的A2空页落图并完成lint、宿主netlist、DRC、全页渲染和持久化基线；
未经主代理视觉仍不端给用户。

- 只允许实例 `inst-013606759-na2iblwm` 的 **test V4 / P41 `037f5a63d7825dfe`**。
  先doc.list+readback+geometry确认唯一A2 sheet且无器件；P38/P39/P40/Board2 P1及其他窗口禁写。
- 输入 `evidence/547/g4/live/page/page.json`、`plan.changeplan.json`、final circuit、
  547A presentation、实测profiles。按现有apply路径执行，必须带真实spec/profile/layout守卫、
  pageUuid、render/out/json。记录LCSC失败后精确搜索→uuid重试证据，不新增旁路。
- `draw plan`已由547G4E4实际生成ChangePlan，apply前核对其30件/源摘要/页面框。
  ERROR不得force；WARN先交主代理，不得为了保存强压。失败/部分写入保留现场并报告，禁止discard/删页。
- 成功后跑 `draw lint --page`（目标0E，WARN逐条解释）、`sch.netlist`独立逐脚/NC（30/31/5，
  自动网名按成员调和）、`sch.drc_check`（pageUuid、strict=false、userInterface=false）、
  `export.render`全页PNG和 `sch.doc.save`。保存只记 `saved_unverified`。
- 用 `boardwise persistence --out` 保存重开前基线；不得关闭编辑器，关闭重开由岳后续手动完成。
- 可写证据 `evidence/547/g4/live/apply/`、`.tmp_547/g4/live/apply/`；不写任务书，
  不改生产/git，不派helper，最多40步/30分钟。交回apply/lint/netlist/DRC/render/save全部原始结果。

## 547G4G首次apply：位号池拒绝与标准页文档路径

- 首次apply在写入前 `designator_taken` 拒绝，P41仍只有A2 sheet。离线plan沿用spec id，
  其中16个已被工程其他页占用；不得改旧页位号或强force。
- 主代理选择既有页文档路径：`draw apply page.json` 在apply时通过 `_draw_plan_from_page`
  读取工程实时pool并用 `keep_names=False` 重新分配，而不是手工改spec或绕守卫。
  预先读回的新plan必须记录specId→实际designator映射，后续netlist按实际位号验收。

## 547G4G apply通过，剩余lint/DRC分诊

- 页文档实时分配后apply成功：30件/95线/57旗，write.calls=242，未force。
  实际位号包括U1→U5、U2→U6、U3→U7、U4→U8、R1→R6、R2→R10、R3→R11、
  R4→R12、D1→D2、D2→D4；后续一律用 `designator-map.json`。
- 独立宿主netlist **30/31/5、0短路**；export.render与save完成，saved_unverified。
- `draw lint`有2E：`10k`@495,745被USART1_RX、`10k`@1560,535被ESP_RXD穿过；
  其余13 INFO为交叉与90/270旗朝向。DRC为0错误/200 warn组，栅格/属性/浮空分诊另记，
  本页NC与固件未用脚不得混为新增短路。
- `persistence`命令当前多窗口无寻址，子代理已按同一两次只读调用构造同形baseline；
  关闭重开由岳手动后，主代理复读比较，不能自报saved_verified。

## 547G4G1：两处10k值行受控修正（当前）

- 只允许 `test V4 / P41` 的两处value文字移动，目标lint **0E**。不得改导线/器件/网/NC，
  不得force、discard或删页；P38/P39/P40/Board2 P1继续禁写。
- 先用 `sch.list_attributes`/geometry定位两个value primitive，保存before；用离线快照+
  `draw lint --snapshot` 对候选位置预演，选不压线/不碰字/不出框的最小移动，禁止盲写试位。
- 仅用受控ATTR位姿接口写value的x/y，记录primitiveId、before/after和agent-adjusted理由。
  写后必须回读坐标并重跑live `draw lint`、宿主netlist逐脚、DRC、export.render、save。
- 更新persistence baseline与全页/局部渲染。若ATTR接口不支持，停止并报告，不得直接改源码字段。
- 证据 `evidence/547/g4/live/apply-fix/`、`.tmp_547/g4/live/apply-fix/`；不写任务书，
  不改生产/git，不派helper，最多30步/25分钟。

## 547G4G1复验与G4G2：旗标竖直化和源计划同步

- 主代理复跑live lint：**0E/0W/13I**；重新取宿主netlist并运行独立审计：
  **30/30件、31/31网、5/5NC、0短路/0问题**。两处值行局部渲染清晰。
- DRC仍0错误/200 warn组，按栅格、库属性与浮空脚分诊，不把NC说成新短路。
- 剩余12个90/270旗标不符合项目0/180竖直约定，继续做小批修正，目标0E/0W/1I
  （仅保留可解释的无结点交叉INFO）。

## 547G4G2：旗标竖直化与最终源计划同步（当前）

- 只允许P41的12个netflag姿态调整与两处已完成value移动的证据同步；不得改网、导线、
  器件位置或删对象。先在离线快照中为每枚旗标选0或180，确保glyph不碰导线/文字/
  器件，live lint仍0E，再用受控pose接口写rotation并回读。
- 保留其余电气与layout，重跑live lint、宿主netlist、DRC、export.render、save和persistence baseline。
- 将最终两处value位置与全部旗标姿态同步回 `evidence/547/g4/live/page/page.json`，
  使复现源与活页一致；重跑离线check_page/check/page_pincheck，保留agent-adjusted调整记录。
- 证据 `evidence/547/g4/live/finalize/`、`.tmp_547/g4/live/finalize/`；不写任务书，
  不改生产/git，不派helper，最多30步/25分钟。若接口不支持，停止，不改源码字段。

## 547G4G2复验：netflag姿态接口边界与受理口径

- `sch.modify_primitive`对12枚netflag全部返回“仅当器件类型为元件时允许使用该函数进行修改”，
  P41几何逐项未变；不得伪造0/180姿态。项目lint将其记为12条L8 INFO，另有1条L6无结点交叉。
- 主代理决定不为INFO新增宿主动作或删建旗标；最终保留0E/0W/13I并披露该接口限制。
  这13条INFO不改变宿主netlist，唯一交叉也不构成额外短路。
- 两次值行ATTR修正已完成并实测0E，不能用netflag失败否定已通过的页面。

## 547G4G3：最终value文本正确同步（当前，离线）

- 将 `sync-proposal.json` 中两处**实际完成**的ATTR结果同步回源：spec R1（live R6）
  value=(495,715)、spec R6（live R14）value=(1560,521)，同步更新text bbox和必要的x/y。
- 只改 `evidence/547/g4/live/page/page.json` 的对应LayoutText与agent-adjusted notes，
  用 `PageLayoutPlan.dump`重算派生摘要；禁止unknown key、手工写旧geometrySha256或伪造旗标姿态。
- 重跑离线check_page/check/page_pincheck、PageLayoutPlan.load和SVG渲染，
  记录新pageGeometry/file hash；apply历史保持原样，后续复现必须同时参考 `sync-proposal.json`。
- 证据 `evidence/547/g4/live/finalize/`、`.tmp_547/g4/live/finalize/`；不写任务书，
  不改生产/git/真机，不派helper，最多15步/12分钟。

## 547F 主代理复验（通过）

- 主代理复跑指定集：**197 passed / 1 strict xfailed**；真实MCU v4生成65岛ChangePlan，
  v5亦复跑 `draw-module / 65 islands / 14 parts` 成功，PA3→17、NRST网岛=[C3.1,U1.7]。
- 主代理临时将 `named=[...]` 改为 `named=[]`：新增测试 **2 failed / 2 passed**，
  证明名字与重复供电脚身份均承重；仅用cp备份还原，sha256=
  `c80428056580b2c83386c138fc01dcc2cf074e6c02086609de04ec83b21902be`，复跑4 passed。
- 生产仅drawapply，新测试 `tests/test_547_named_pin_plan.py`；未知token仍拒绝，
  数字路径不变，歧义别名不猜。文档 `docs/draw.md` 已同步，证据 `evidence/547/f/`。

## 547G4E2V：外围v8视觉复核（通过）

- 主代理逐岛查看原生PNG并对C5–C7与BMP顶部做局部放大：BMP双3V3已分开，
  C5/C6/C7的reference与value均和GND名称分行，WiFi上拉/去耦与NC可读，UART/SWD清晰。
- v5/v6/v7连读均判废留证，最终v8七岛readability/grammar/floor=0、逐脚/NC/短路全过，
  **外围离线视觉通过**。证据 `evidence/547/g4/visual/peripherals-v8-review.md`。
- 547F已通过，MCU v5与外围v8可进入G4E4真实整页和ChangePlan批。

## 547G4E4首轮：A4面积拒绝与A3裁决

- 八岛 `_module_frame(...,padding=0)` 的墨迹总面积 **1,048,371 > A4 965,250**，
  零间隙也放不下；padding=20为1,307,179。不是排布搜索问题，不能压frame造假。
- 主代理选择先试**标准A3 1587×1123** 以保留已通过视觉的间距，不缩器件、不删支路、
  不改岛归属；若宿主不支持再考虑独立收紧批，不直接缩交付。

## 547G4E4A：test V4的A3图幅可行性（先于整页）

- 写操作仅限 `test V4` 的**一个新图幅验证页**（建议名547G-layout），不得改P38/P39/
  Board2 P1/P40或其他窗口，不删页/探针，不做最终apply。
- 先bridge status+doc.list确认实例和工程逐字一致，创建后读取sheet Width/Height和keepout。
  用受控属性通道尝试把新页设为标准A3 `1587×1123`，必须用sys.get_document_source/geometry
  读回实际属性；失败就停止并保留原始错误，不猜、不改生产。
- 保存 `identity.json`、`sheet-before.json`、`sheet-after.json`、新页uuid、属性写入回读与
  标题栏keepout计算。可写证据 `evidence/547/g4/live/sheet/`、`.tmp_547/g4/live/sheet/`；
  不写任务书，不做git/删除，不派helper。最多25步/20分钟。
- 成功才允许用page_box=`0,0,1587,1123` 回G4E4；否则保留A4失败证据并交回收紧方案。

## 547G4E4A复验：属性通道失败，模板候选已找到

- P41=`037f5a63d7825dfe` 已创建但未放器件。`sch.set_component_attribute`对sheet报
  “仅当器件类型为元件时允许使用该函数进行修改”，读回仍A4，不存在半写A3状态。
- 在线库存在 `Drawing-Symbol_A3`：uuid=`0c5d0e47f9f04f14b0906112873b8a58`，
  symbolUuid=`b3ee1e6e9a054ea393eb4634fec943c6`。标题栏keepout尚未实测，G3F的
  `(470,0,1170,180)`只能算离线占位，不能当真机值。

## 547G4E4B：A3模板放置探针（不删除任何对象）

- 仅允许在 **test V4 / P41 `037f5a63d7825dfe`** 用在线返回的uuid/libraryUuid放置一次
  `Drawing-Symbol_A3`，并读回sheet列表、Width/Height、Title Block Position和keepout。
  不得删除旧sheet、不得apply、不得改其他页/窗口、不得改生产或git。
- 先doc.list+readback确认P41仍只有sheet，保存before。放置后若出现两个sheet、错误、
  非A3或不可判定，立即停止并保留现场，不重试、不清理；交主代理选择A4收紧或请岳手工改图幅。
- 若宿主自动替换为唯一A3 sheet，读回 `1587×1123` 后才允许回G4E4，并重新计算真实标题栏keepout。

## 547G4E4B复验：A3模板成功，实测尺寸采用

- A3两次排布仍形状无解：MCU与env+BMP上下叠需要1063.5>870，左右并排留下315宽死角；
  三模块横排在padding=0时也需1656>1655。不是面积不够，不能再靠随机排序解释。
- 主代理裁决不改已通过视觉的岛内间距，改试标准A2模板，保留全部功能与间距。
  离线标题栏仍只用保守占位，apply前由真实页守卫复核。

## 547G4E4C：A2模板替换（不删除任何对象）

- 只读搜索 `Drawing-Symbol_A2`；只有实际在线返回uuid/libraryUuid后才允许在
  **test V4 / P41 `037f5a63d7825dfe`** 放置一次模板。不得删除A3 sheet、不得apply、
  不得改其他页/窗口/生产/git。
- 放置后必须读回唯一sheet和实际Width/Height；若两sheet/错误/不可判定，停止不重试不清理。
  保存before/after和真实page_box。标题栏keepout只给保守占位，不冒充实测。
- 证据 `evidence/547/g4/live/sheet-a2/`、`.tmp_547/g4/live/sheet-a2/`；不写任务书，
  不派helper，最多20步/15分钟。成功后回G4E4，不再扩大图幅。

## 547G4E4C复验：A2为最终图幅

- P41已替换为唯一A2 sheet `93e5fa80765af875`，实测 **2338×1652**，只有图框无器件；
  未删除任何对象，P38/P39/P40/Board2 P1未动。TIMEOUT与替换效果不一致已由readback/geometry澄清。
- G4E4最终使用 `page_box=0,0,2338,1652`，不再扩图幅、不缩间距。
  标题栏仅用保守占位 `(939,0,2338,360)`（假设，非实测）；apply仍需宿主真实页面守卫。

- `sch.place_component`虽回TIMEOUT，但回读证明宿主已把旧A4 **替换**为唯一A3 sheet，
  未重试、未删除任何对象；sheet=`4e9b343511b3d280`，Page Size=A3、**1655×1170**。
  P41=`037f5a63d7825dfe`仍只有这一张sheet，P38/P39/P40/Board2 P1未动。
- 主代理采用实测 `page_box=0,0,1655,1170`（面积1,936,350），不坚持1587×1123。
  标题栏符号变换仍不可测，G4E4离线只用保守占位 `(600,0,1655,300)`，不冒充实测；
  apply前必须让宿主按真实页面重读并守keepout。
- 证据 `evidence/547/g4/live/sheet-a3/`、`.tmp_547/g4/live/sheet-a3/`；不写任务书，
  不派helper，最多20步/15分钟。

## 547G 暂停快照 / 当前状态（2026-11-07，用户暂停）

547G 整体**未完成**，长期目标保持 **paused**；本节是当前权威状态，前面各批标题里的“当前”
只作历史。547G 是 agent-adjusted 辅助路线，与 automatic 分账，不得用辅助成果关闭
547D/E/F 的自动整页缺口。

**已完成（agent-adjusted）**

- G1 接口盘点、G2 WiFi 单岛三关、G3 30 件/31 网/5 NC/8 岛离线双层页面闸
  （页面域 `readability.check_page` + 合并图 `readability.check` 均 hard=0），
  独立逐脚/NC 校验与主代理逐岛视觉均通过。
- G4 在 test V4 / P41 真实 apply：30 件 / 95 线 / 57 旗，write.calls=242，未 force。
  首次 `designator_taken` 未写入，最终经页文档实时位号池分配；映射 U1→U5、U2→U6、
  U3→U7、U4→U8、R1→R6、R2→R10、R3→R11、R4→R12、D1→D2、D2→D4，权威
  `evidence/547/g4/live/apply/designator-map.json`。
- 两处 10k 值行已移开导线：live R6 Name=`d82668814cf08d3a` (495,745)→(495,715)，
  live R14 Name=`fc9163139ca10b3c` (1560,535)→(1560,521)。
- 主代理 live lint **0 ERROR / 0 WARN / 13 INFO**（12 枚 90/270 旗标方向 INFO + 1 个无结点
  交叉 INFO）。`sch.modify_primitive` 不支持 netflag（宿主只允许元件），未新增动作、
  未伪造旗标姿态，12 条方向 INFO 保留。
- 独立宿主 netlist 审计 **30/30 件、31/31 网、5/5 NC、0 短路 / 0 问题**。
- DRC 已执行但**不能称通过**：0 error / 200 warn，`passed=false`；栅格、库属性、浮空脚
  分诊，NC 与固件未用脚不是新增短路。
- 全页与局部宿主渲染已由主代理亲眼复核（`page-after.png`、`page-local.png`）。
- 保存状态仅 `saved_unverified`，**不是** `saved_verified`。

**权威输入与页面**

- 最终电路 `evidence/547/g4/live/spec/final.circuit.json`，对象 sha256=
  `391667fb9bbf3c0e735db24a47845c0bc74f3f4932306dd5197cb20d2c85a846`。
- Presentation `evidence/547/a/smart_medicine_box.presentation.json`，对象 sha256=
  `18f900d5eea6aa3bb6732461ef691374651e6b893ff62153351f92b5d831d5d3`。
- 真机 profiles `evidence/547/g4/live/profiles/profiles.json`：18 份、122 条 profile 引脚记录。
- test V4 / P41 uuid=`037f5a63d7825dfe`，A2 sheet=`93e5fa80765af875`，2338×1652。标题栏离线
  矩形 `(939,0,2338,360)` 只是保守占位，不是实测；apply 用真实页面守卫。
- P40=`eb22558f9f36db43` 保留为 13 器件+2 旗标探针标定页；P38=`0ec4dc022ef38563`、
  P39=`62e4828acc56a307`、Board2 P1=`30560d9c0a52a6d2` 均保留；未删页；
  `E:\SmartMedicineBox` 全程只读。
- 最终源页 `evidence/547/g4/live/page/page.json` 已同步两处 value 并由
  `PageLayoutPlan.dump` 重算摘要：pageGeometrySha256=`71ea409395579e7a…`、
  planGeometrySha256=`679c231875496bd2…`、page.json 文件 sha256=`1d435eade83f1c60…`、
  page.svg sha256=`31069d2c9b109308…`；verdict=pass、30/31/5、0 短路。
  离线 check_page / check / page_pincheck 均通过。apply/fix 历史不伪改。

**证据路径**

- apply 权威历史与位号：`g4/live/apply/apply-page.json`、`g4/live/apply/designator-map.json`
- lint / 宿主 netlist / DRC：`g4/live/apply-fix/{lint-main.json,netlist-audit.json,drc-main.json}`
- 渲染 / 保存 / 持久化同形基线：
  `g4/live/apply-fix/{page-after.png,page-local.png,save-after.json,persistence-baseline.json}`
- 源页与 value 同步：`g4/live/page/page.json`、`g4/live/page/page.svg`、
  `g4/live/finalize/value-sync.json`

**剩余（恢复后）**

1. 岳手动关闭并重开 test V4（最好只留此窗口）。多窗口时 persistence 返回
   `WINDOW_UNSPECIFIED`；不得强行关编辑器。重开前后只读快照/比较：
   `boardwise persistence --out <before>.json` → 手动关闭重开 →
   `boardwise persistence --baseline <before>.json`；现有同形基线为
   `g4/live/apply-fix/persistence-baseline.json`。**现在不要执行。**
2. 完整四线（pytest / connector `npm test` + typecheck / dsh-plugin / rust）与卫生检查。
   本批未运行；只有 547F 聚焦读数 **197 passed / 1 strict xfailed**，不得据此称全绿。
3. 最终复验与岳签字。G3/G4 页面是固件约束的逻辑重绘（observed/assumed/optional 分账），
   不是 automatic、不是参考临摹、不能直接投板。

**547F（相关生产修复，未提交）**

- `src/boardwise/engines/drawapply.py` 已能解析真实 pin number / Pin Name / 别名，
  测试 `tests/test_547_named_pin_plan.py`；真实 MCU v5 生成 draw-module / 65 islands /
  14 parts。独立变异 `named=[...]`→`named=[]` 后 2 failed / 2 passed，cp 恢复后 4 passed，
  恢复 sha256=`c80428056580b2c83386c138fc01dcc2cf074e6c02086609de04ec83b21902be`。
  该生产修复未提交。
