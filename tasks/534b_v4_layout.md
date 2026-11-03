# 534B — CH343 V4 六岛布局（worktree 实验）

日期：2026-11-01 · 分支 `534b-layout` · worktree `E:/boardwise-wt-layout`
授权：岳「拉个 worktree 去改，token 预算无限大胆试错」

> **2026-11-01 撤回（岳验收 20/100）**：Board2 P2 `dc46ef64fc7385ec` 已删除，
> Board2 只保留岳的 P1 参考页；Board1 P3 `5d5f8f9f7ac34562` 目前是空页。
> 本文件下方六岛结果只作为实验记录，**不是当前交付**。根因已定位：
> 宿主网名以导线端点为起点向右排，5–10 单位短桩会把文字压回引脚/器件体；
> 统一最小桩长 40 又会被 U1 reference 文本（748–763）占住的右标签走廊挡住，
> V3 只能退成 5 上 + 60 右折线。下一批要先解决“标签走廊 / reference 文本占位”，
> 再谈落 Board1。

## 目标

把 CH343 从“五岛/电源岛沉底”改成：
CC 并入 USB、去耦按服务脚拆成卫星岛贴 U2、LED 独立、H1 独立；
标签优先直跑，地/电源旗标按簇就近；不再靠人工坐标硬凑。

## 结果（V4 Board2 P2 `dc46ef64fc7385ec`）

- 6 岛：`usb_c` / `v3_cap` / `ch343` / `vcc_cap` / `hdr` / `led`
- 11 器件、54 段计划线、43 个宿主 wire、16 旗标
- `draw apply` exit 0；`outOfScope.items=0`；`{saved:true}`，`saved_unverified`
- `draw lint` **0 ERROR / 1 WARN**（D+ 可逆脚同线双标签）
- 独立逐脚：**17 网 / 58 脚 / 55 连通 / 3 NC PASS**
- H2 `Name` 改为 `2x5P`，不再显示长 MPN

证据：`evidence/534b/report.md`、`render_final.png`、`apply.json`、`plan.json`、
`lint.json`、`netlist.json`、`connectivity.json`、`SHA256SUMS`。

## 编译器变更

1. `PresentationSpec.moduleOrder`：显式页面摆放顺序（必须是 modules 的排列），
   不冒充信号 flow；未写时不改变旧页。
2. `PresentationSpec.moduleColumns`：固定网格列数；未写时仍 1..N 自动搜索。
3. `pagecompiler._placement_orders` / `_variants` 读取这两个字段。
4. `ch343_uart_v4.library.json`：C0603/C0805/R0603/LED 增加 90/180/270 pose；
   声明 pose，不是逐角度实测文字行，只按本页 apply/lint 结果使用。
5. 保留 534A 的 lint end-anchor 修复与 `labelPolicy.stub` 能力。

## 未关闭

- C7/C8 是卫星岛 frame 相邻（间距约 80 单位），不是同一岛内部贴脚；
  还没到 Board2 P1 的“电容贴 U2 左右”程度。
- 页面仍有大片空区，H2/LED 偏下；布局紧凑度不是最优。
- S-21 标签名称行仍有贴 2 单位下限的软项。
- native netlabel 仍不可用；`saved_unverified`；未做 checkup/PCB。
- 已提交 `1c8cc56` 并经 `b74ee91` 合并入 `main`；worktree 保留为实验证据。

## 测试

- schema/compiler/page 聚焦：**220 passed / 3 skipped**
- 全量 Python（主树、worktree 代码）：**8829 passed / 25 skipped / 2 failed**
  - 两条均为既有环境红：`pytest-slots` ACL、MSYS `0xC0000022`
  - 没有本批回归

## 2026-11-01 续：同岛去耦的自动排版边界（v14–v21）

目标：C3/C4 与 U1 同岛、无回折、标签 40 直桩、D+/D− 朝 USB。实测矩阵：

| 变体 | 做法 | 结果 |
| --- | --- | --- |
| v14 | 模块锁 C3(−120,0,90)/C4(120,0,90) | 编译过；真机 plan 拒：VCC 竖线 x=490 横穿左侧 40 桩走廊，CTS 无桩 |
| v15/v19 | 去掉电容锁（flag lead 120/200） | 编译拒：`+5V` 在 U1.7 无 lead，邻居器件挤住 |
| v16 | C3/C4 换边 | 编译拒：`left-of(C3,U1)` 关系不成立 |
| v17 | 加 U1 `(0,0,0)` 姿态锁 | 编译器改选未镜像姿态（D+/D− 回左侧对 USB）；只剩 +5V/VCC 文字重叠 |
| v18 | 电容外移 −160/+200 | 编译过；plan 拒：右侧 DSR 桩撞 +5V 引线、VCC 竖线、`CH343G` 值文字 |
| v20 | 电容移到芯片上方 | 编译过；V3 竖线 x=470 仍横穿 TXD/RXD 桩 |
| v21 | 电容横放对齐引脚行 | 编译拒：+5V lead 横穿 C3 的 GND 竖线 |

**根因（两条，均已定位，不是调参能修的）**：

1. `drawcompiler` 选 `mirror=true` 后，C3/C4 仍按未镜像方位落位，V3/VCC 各绕芯片一圈；给 U1 加姿态锁可逼出未镜像姿态。
2. CH343 符号的电源脚（U1.7 VBUS、U1.15 VIO、U1.16 VDD5）夹在信号脚之间，两侧同时要“40 标签桩 + 电源旗标 + 去耦电容引线”，`ic-periphery` 的走廊模型没有一侧能同时容下三者；换任何落点只是把冲突挪到另一根线。

**未落图**：Board1 P3 `5d5f8f9f7ac34562` 仍为空页；Board2 只有参考 P1；本批无 commit。

**下一步最小动作**（二选一，需要定方向）：

- A. 给 presentation 增加“去耦行”块：C3/C4 作为芯片岛内的底部一行，两端各挂旗标/标签（照参考页 C15–C17 的画法），不让路由器从电容拉长线到引脚；
- B. 允许手写 ChangePlan 覆盖几何（先给 `draw plan` 加 `--from-plan` 入口），由人给 C3/C4 与标签定坐标，编译器只做校验。

### 2026-11-01 执行 A：053c `attach`（已实现，未落图）

- 规格：`modules[].attach = {"to": 宿主 id, "side": bottom|top|left|right, "gap": n}`。
  语义**只影响摆放**：被贴模块仍是独立模块、仍在 `page.modules`、图形不合并，
  页面把它放在宿主已放置 frame 的指定一侧；两模块之间仍按跨模块同名旗标/标签连接，
  **不画连接线**（实测 caps↔ch343 跨框段 0）。
- 实现：`presentationspec.py`（`ModuleAttach`、`attach` 解析/序列化/交叉校验，默认不写出）、
  `pagecompiler.py`（`_attachments`/`_attach_shift`/`_attached_placement`/`_settle_attached`；
  被贴模块不进 `_arrange`，宿主用 union 占位框参与网格，settle 后还原真实 frame）。
  新建 `tests/test_053c_attach.py`（24 passed）；`053a+056` 89 passed / 1 skipped。
- `gap` 下限受 `readability._check_frame_separation` 约束：文档写 10，实际取 `max(10, module_gap 40)`，
  `page.notes` 写明两者。
- v25 编译：`ok=True`、4 候选；C3(490,525)/C4(545,525)、U1(510,725)，
  caps frame(416.5,450,618.5,604) 落在 U1 frame(380,645,658,824) 正下方居中。

**仍未落图**：v25 真机 `draw plan` 在**模块级**被拒，4 个候选同一处——

- `net V3: the label at (555,730) has no free name stub`：U1.4 的标签要往右走 40，
  名字行的 730–740 与 RXD 标签盒 (591,735.5)-(615,744.5) 重叠；往上撞 GND 线端、往下撞 +5V 线端、
  往左是本体，右侧还有 U1 reference 文本 (563,727.5)-(578,736.5)。
- 根因：CH343 两侧引脚 10 单位间距、名字行高 9、S-21 要求两行至少隔 2 ——
  同侧相邻两个标签**永远差 1 单位**。离线 `draw compile` 的检查器按更松的盒子放行，
  真机 plan 用宿主真实文字盒，两者模型不一致；这不是换 pose 能修的（rot0/rot180 变体
  改在 U1.15/VCC 旗标无 lead 处失败）。

下一步二选一：①把 compile 侧的标签盒/行高与 plan 侧统一（同一套 `render_box`），
让离线结果不再假通过；②给该符号一个“两侧标签行错位 5 单位”的排法（奇偶行错半格），
这是参考页实际在用的手法。

### 2026-11-01 落图：v28（错行）已上 Board1 P3

- 岳选 ②。做法：`labelPolicy.stub` 去掉 `straight`（= `auto`），让 apply 的标签梯子用
  5/10 单位折返错行绕开相邻文字盒 → `draw plan` 通过（5 模块 / 11 器件 / 33 段 / 25 标签 / 15 旗标）。
- `draw apply` 已落 Board1 P3 `5d5f8f9f7ac34562`：11 器件、54 wire、15 flag，
  宿主网表 + 画布双回读通过并保存（`saved_unverified`；bridge 无 close/reopen）。
- 去耦行：caps origin(475,600)、frame 411.5–613.5 × 450–604，位于 ch343 frame
  (380–642 × 645–824) 正下方居中，两岛之间 **0 根连接线**（V3 标签 + VCC/GND 旗标跨岛同名）。
- `draw lint`：**0 error / 1 warn**（L5 D+ 可逆脚同线双标签，A6/B6 固有）。
- 独立逐脚：按 `U1→U2/USB1→USB2/H1→H2/D1→D2/R3→R6/C1→C5/C2→C6/C3→C7/C4→C8` 映射核 55 脚，
  51 脚网名一致；CC1/CC2 4 脚落在 `$4N6`/`$4N7`（未命名局部网，两两成对连接）——**连通 PASS**。
- 证据：`evidence/534c/`（render_p3.png、page_plan.json、changeplan.json、lint.json、netlist.json、presentation.json）。

**视觉自审（未过）**：

- U2 左侧 6 个调制标签仍是“错行但挤”：折返桩彼此交叉，读起来像一团线（参考页是短桩、不交叉）。
- C7/C8 去耦行在 U2 正下方，但间距 41，看上去仍像独立小组而不是芯片岛的一部分。
- USB2 岛（左上）仍是大回环 + 散落 +5V 旗标，与 20/100 那版同源，未改。
- D+/D− 标签在 USB2 左侧、U2 右侧，仍然背对背，没有形成参考页那种“隔空相对”。

下一批要动的两处：①调制标签改两列扇出（行距 20、列距错开），去掉线交叉；
②去耦行与芯片岛之间改用同侧短旗标（或把 caps 贴到 ch343 的 `top`/`right` 侧再收紧）。

### 2026-11-01 续二：标签行模型 + `partTexts`（P4 v30）

- **标签行模型**（`drawapply.py`）：标签桩候选的名字行改为**以锚点居中**（宿主 netlabel 的实际画法），
  并新增 `LABEL_ROW_FLOOR = 1.0`——标签对标签 1 单位、其余仍 2。`test_534_label_stub_typography.py`
  6 条冻结断言按新口径重钉（14 passed）。
- **`partTexts`**（presentationspec/drawcompiler/pagecompiler）：`{"U1": "above"}` 让位号/型号离开
  引脚道。实测 U1 reference (563,727.5)-(578,736.5) → (487.5,795)-(502.5,804)，
  value → (487.5,781)-(532.5,790)；未声明文档重编逐字节不变。
- **落图**：P3 上的 v28 用 `draw discard` 撤不掉（宿主合并导线，身份不符整批拒删，057 §五）。
  改为新建 **P4 `40d5eb1d1830a2ff`** 落 v30：11 器件 / 54 wire / 15 flag，双回读通过并保存。
- **P4 lint：2 ERROR / 1 WARN**：
  - `L1-text-on-wire`：`RXD` 文字 (575,740) 被 TXD 导线横穿 15 单位；
  - `L2-text-on-text`：C11 的 `100nF` 与 `V3` 盒子重叠 8.7×10；
  - `L5`：D+ 双标签（固有）。
- 渲染：`evidence/534c/render_p4_v30.png`。左列调制标签明显好转（短桩、不交叉、不压字），
  但右侧 TXD/RXD 拉出长线、去耦行仍隔 41 且 C11 值压 V3 标签。

**当前页面**：Board1 P2（旧 20/100 页）、P3（v28，lint 0E/1W）、P4（v30，lint 2E/1W）；Board2 只有参考 P1。
两个实验页都未删（删除需岳点头）。下一批：修 P4 的两条 lint 错（RXD 行让开 TXD 线、C11/C12 值改侧），
再去收紧去耦行间距。

### 2026-11-01 续三：清页 + v32（P5，lint 0E）

- 岳要求“建新页就把老页删掉，否则 DRC 查不了”。已删 Board1 P2、P3、P4；现在
  **Board1 只有 P5 `ada13e21dde3e006`**，Board2 只有参考 P1。
- P5 用 v32：`labelPolicy.stub` 回 `auto`（错行折返）+ `partTexts={"U1":"above"}`。
  落图 11 器件 / 54 wire / 15 flag，双回读通过并保存。
- **lint：0 error / 1 warn**（仅 D+ 双标签）；**独立逐脚 55/55 一致**。
- 证据：`evidence/534d/`（render_p5.png 等）。
- 仍不理想：左列调制标签仍偏挤；去耦行与芯片岛间距 41；USB2 岛回环未改；
  D+/D− 标签仍背对背。下一批继续。

### 2026-11-01 续四：地网按簇挂旗标（535）→ P6

岳反馈：去耦电容想自成小岛，却因“一个 GND 旗标”被拉大环去别处接地。
实现（`drawcompiler.py`，子代理 053e）：

- 新增 `GND_LOCAL_RADIUS = 100`，地网焊盘按**直径上限贪心聚类**（簇内任意两点 ≤100）；
  每簇各自 rail + 恰好一枚 GND 旗标，**簇间不连线**；单簇时逐字节不变。
- 新测试 `tests/test_053e_ground_clusters.py`（5 passed）；更新 `test_053b_drawcompiler.py`
  两条“全网一枚旗标”的旧断言（535 取代 201A）。
- 实测 usb_c：GND 段 10 段不变，总长 **940→565**、最长段 **205→85**、旗标 **1→4**
  （去耦那簇旗标在 (145,600)，C1/C2 就在 90–100 内）。
- 落图：新建 **P6 `202c0cbe296dde3a`**，11 器件 / 54 wire / **18 旗标**，双回读通过并保存；
  同时删除 P5。**Board1 现在只有 P6**，Board2 只有参考 P1。
- `draw lint` **0 error / 1 warn**（D+ 双标签固有）；**独立逐脚 55/55**（CC1/CC2 4 脚落自动名 $\7N7/$\7N8）。
- 证据：`evidence/534e/`。

### 2026-11-01 续五：审计 + 三个开关（053f）+ P13

- 审计（4 个子代理，21 条发现）。修掉三条：`flag_lead_limit` 未传进模块预算（页编译写 120 实际按 60 跑）、
  `flagLeadLimit: NaN/Infinity` 能过校验并取消上限、注释里的 `"U1"` 触发“场景常量”红。
- 审计发现的根本问题：053c/053d/053e/534 r25/536 里**改了默认行为**的规则把全量打到
  44 failed。按“规格声明、不写＝旧行为”改造：

| 开关 | 默认 | 本图 |
| --- | --- | --- |
| `gndClustering.radius` | 不写＝不分簇（旧：一个地网一枚旗标） | 100 |
| `labelPolicy.stubMin` | 0＝旧梯子（首档 10） | 40 |
| `labelPolicy.rowModel` | `anchored`＝旧行模型 | `centered` |

- 新测试 `tests/test_053f_policy_switches.py`（22 条）；`053e/053b/534` 夹具改成显式声明。
- 落图：**P13 `9e6240c6c29a8642`**（P11/P12 已删），11 器件 / 54 wire / 18 flag，双回读通过并保存。
- `draw lint` **0 error / 1 warn**；宿主 **DRC 0 error / 5 warn**（D+ 双标签、两处旗标不在栅格、
  R1/R2/R6 属性与库不符、USB B8/A8 与 U1.8 是电路里声明的 NC）；独立逐脚 **55/55**。
- 证据：`evidence/534i/`。

### 2026-11-03 续六：两列直桩扇出（053J，已落 P15）

- 缺口：P13 的 CH343 左列 RI/CTS/DSR/RTS/DTR/DCD 六枚标签都取 40 直桩，名字落在同一 x 带；
  本批只把相邻引脚的首选直桩交替成 40/100，保留既有全部短桩、折线和拒绝/回退逻辑。
- 文件域：`src/boardwise/engines/drawapply.py` 的 `_label_stub_candidates` 与新增
  `tests/test_534j_two_column_stubs.py`；规格仍用 `.tmp_fix/v42.presentation.json`，证据落
  `evidence/534j/`。不改 `_place_label_stub`、共享 CLI、connector、dsh-plugin、他人的未提交文件。
- 兼容边界：`stubMin`/`rowModel` 未声明、非页面严格路径及其他既有档位必须保持旧候选序列；
  40/100 只重排/增补首选，不许删除任何旧候选。
- 子代理预算：最多 40 步或 30 分钟；只跑聚焦 pytest（必须带独立 `--basetemp=.tmp_pt_534j`），
  不做真机写、不做 git 写、不跑全量。交卷给出 diff 摘要、候选序列断言和真实测试计数。
- 主代理验收：审 diff + 至少两项独立变异抽验；离线 `draw compile` 后，在任务书点名的
  `test V4` 新建 P14，真机 `draw plan/apply`，三关全过后删除 P13；Board2 P1 不动。
  若候选 `ok=False` 或三关不过，只留证据，不交付新页。
- 结果：只在 `stubMin=40 + rowModel=centered` 的页面严格水平路径交替提供 40/100 首选；
  偶数名字行深档优先，其他楼层/未声明键/非严格路径逐点保持旧梯子。左向深档还须满足
  `x>=100`，避免 H3 的 100 桩越出图幅。`_place_label_stub` 未改。
- 真页落档为 RI40 / CTS40 / DSR100 / RTS40 / DTR100 / DCD40：CTS/RI 的 100 候选穿 VCC
  竖线，RTS 的 100 候选穿 VCC 旗标文字，均由既有 chooser 回退 40；DSR/DTR 干净走 100。
  同一既有严格测试中一条首选坐标断言同步改为 100，行×线相切判据本身未放松。
- P14 首版 apply 后 lint 4E（H3 左桩到 x=-40），只作实验证据；加左边界门槛后新建
  **P15 `b2d7282510e14bb2`** 重走全流程，11 器件 / 54 wire / 18 flag。
  P13/P14 均已删除，Board1 只有 P15，Board2 参考 P1 `30560d9c0a52a6d2` 未动。
- 最终三关：`draw lint` **0E/1W**（D+ 双标签固有）；宿主 DRC **0E/5W**（同 P13 五类）；
  删除旧页后的独立逐脚 **17 网 / 58 脚 / 55 连通 / 3 NC**，missing/extra/absent 均空；
  `evidence/534j/render_final.png` 已逐岛目检，CH343 左列成两条文字带、无交叉折线。
- 复验：聚焦 **76 passed / 1 既有 GBK warning**；最终两项变异（删左边界门槛、反转奇偶）
  分别 **2 failed**、**4 failed**，恢复后源码 SHA-256 均为
  `f9b78796b6db2e142b57d0dfca7cf774ac7e9bcf4a1ba193ac76e05b9aed52b0`。
  证据：`evidence/534j/`（compile、plan/apply、lint/DRC、netlist、connectivity、render、测试日志）。

### 2026-11-03 续七：attach 成对间距（053K，已落 P16）

- 缺口：P15 的去耦行仍按 `max(attach.gap=10, module_gap=40)` 摆放，视觉上不像芯片岛的
  贴身旁岛。本批让**显式 attach 的一对模块**按声明 gap 摆放；该对只豁免 module_gap，
  面积重叠仍硬拒，其他模块对仍保持 40。
- 文件域：`src/boardwise/engines/readability.py`（`_check_frame_separation` 及 check_page 的
  attach 对传入）、`src/boardwise/engines/pagecompiler.py`（`_attach_shift`、`_settle_attached`
  与 attach notes）、`tests/test_053c_attach.py` 的两条旧 40 断言，新增
  `tests/test_053k_attach_gap.py`。规格 `.tmp_fix/v42.presentation.json` 已经声明 gap=10，无需改键。
- 兼容边界：未写 attach 的文档保持旧检查顺序、候选和序列化；attach 对接触边但无面积重叠可接受，
  任何面积重叠不可豁免；被贴模块与其他非宿主模块仍按 module_gap。
- 子代理预算：最多 40 步或 30 分钟，只跑 053c/053k/056/readability 聚焦测试，独立
  `--basetemp=.tmp_pt_534k`；不做真机/git/全量，不碰 053J 文件或他人脏文件。
- 主代理验收：审 diff、两项变异、离线 compile；新建 P16 做 plan/apply，三关全过后删 P15，
  证据落 `evidence/534k/`，Board2 P1 不动。
- 结果：attach 对按声明 gap 摆放、豁免页面 module_gap，面积重叠仍硬拒；非宿主对仍 40，
  未写 attach 的旧路径不变。schema 中旧 floor 注释也已同步。真规格 4 候选全过，
  caps–ch343 实测间距 **14.5**（声明 10 + 栅格外取整），其他对最小 **45**。
- 落图：**P16 `a1544f69ead6f273`**，11 器件 / 54 wire / 18 flag；P15 已删，Board2 P1 未动。
  最终 `draw lint` **0E/1W**、宿主 DRC **0E/5W**、独立逐脚 **55/55 + 3NC**；
  `evidence/534k/render_final.png` 已逐岛目检，去耦行明显贴近 CH343，仍无两岛间导线。
- 复验：主代理聚焦 **76 passed / 1 skipped**；两项独立变异（check_page 不传 attach 对、
  摆放恢复 max40）分别 **20 failed**、**14 failed**，readability/pagecompiler 恢复哈希
  `d042f6f6…0a05` / `bbec0875…605c`。证据：`evidence/534k/`。

### 2026-11-03 续八：USB CC 电阻横放（053L，已落 P19）

- 缺口：P16 的 R1 CC1 走线长 **365**（30,725→30,805→190,805→190,730→235,730→235,725），
  R2 CC2 长 90；参考页是两颗电阻横放在 USB 左侧、pin1 朝连接器、pin2 朝地。
- 本批先不改源码：从 `.tmp_fix/v42.presentation.json` 派生 `.tmp_fix/v43.presentation.json`，
  仅加 module-scope userLocks：R1(-80,25,180)、R2(-80,-35,180)。USB 本地坐标中
  A5=(-35,25)、B5=(-35,-35)，R pin1 在旋转 180 后朝右，目标各约 25 的直连接。
- 文件域：新规格、`.tmp_534l/` 探针和 `evidence/534l/` 离线证据；不改 053J/053K 源码、
  blocklib 电路/符号库或他人文件。子代理最多 20 步/20 分钟，只做离线 compile + module_plan
  几何核对；被拒绝候选只留 `.tmp_534l/`。无源码变更时不做伪变异、不新增测试文件。
- 主代理验收：审规格 diff 与 CC/GND 导线，离线 ok=True 后新建 P17 真机 plan/apply，
  三关全过后删 P16，Board2 P1 不动；若短直路径导致 GND/文字冲突，回到本批规格试验，不扩大改码。
- v43 离线即达 CC1/CC2 **25/25**（原 365/90），GND 无跨网接触；P17 真机 lint 1E：
  R1/R2 GND 竖干 x=145 穿 C1 值盒 `[135,720]-[155.2655,730]`。v43b 试 `partTexts.C1=left`
  只改变规划盒、宿主文字未动，且候选镜像翻转，P18 lint 2E，判为实验页。
- 最终规格 `evidence/534l/v43c/presentation.json` 在 v43 上只加 C1(-125,50,270) 锁；
  +10 的 y=40 被编译器证明使 R1.2 无地旗引线，+20 是第一合法档。选 candidate 1 保持 U1
  mirror=true，新建 **P19 `e1ea4d1af5f7547d`**，11 器件 / **54 wire / 17 flag**
  （以最终 apply 回读为准；早期探针摘要的 53/18 不是最终页）。
- P19 三关：lint **0E/1W**、宿主 DRC **0E/5W**、独立逐脚 **55/55 + 3NC**；
  宿主 SVG 实测 C1 值盒 `[85,735]-[105.2655,745]`，R 地竖干最高 y=725，纵向净空 10。
  最终 CC 仍 25/25，GND 总长 510（P16 为 565），旗标 17；P16/P17/P18 全删，Board2 P1 未动。
  `evidence/534l/render_final.png` 已逐岛目检，USB 大回环消失且其他岛无新增缺陷。
- 本批无生产代码改动，故无伪变异/新增测试；主代理独立重跑每份接受规格的 compile 与几何探针。
  证据：`evidence/534l/`（含各实验页失败原因、最终 plan/apply/lint/DRC/netlist/connectivity/SVG/PNG）。

### 2026-11-03 续九：D+/D− 隔空相对（053M，已落 P20）

- 缺口：P19 是 usb_c 在左、ch343 在右；USB 左侧 D 标签与 CH343 右侧 D 标签都朝页外，
  形成背对背。参考页实际是 CH343 在左、USB 在右，现有两侧标签天然隔空相对。
- 本批只交换 `moduleOrder` 前两项为 `ch343, usb_c`，不改 flow、器件姿态、userLocks、
  电路或源码。规格从 `evidence/534l/v43c/presentation.json` 派生为
  `.tmp_fix/v44.presentation.json`，证据 `evidence/534m/`。
- 离线验收：compile ok=True；候选须保持 U1 mirror=true、CC=25/25、C1 值盒/GND 净空；
  ch343 的 x 小于 usb_c，U1 D+/D− 在芯片右侧、USB D+/D− 在连接器左侧，形成相向标签。
  子代理最多 15 步/15 分钟，只做离线 compile/module_plan；无源码变更不新增测试/伪变异。
- 主代理新建 P20 真机 plan/apply，三关全过后删 P19，Board2 P1 不动；真机 SVG/PNG 必须
  亲眼确认两对 D 标签的朝向与间距，不能只用模块 x 坐标冒充视觉通过。
- 结果：candidate 0 为 ch343 x=130、usb_c x=525、U1 mirror=true，CC=25/25，岛内几何仅平移。
  新建 **P20 `e02907a663e2f6b8`**，11 器件 / 54 wire / 17 flag，与 P19 最终计数相同；
  P19 已删，Board2 P1 未动。
- 最终三关：lint **0E/1W**、宿主 DRC **0E/5W**、独立逐脚 **55/55 + 3NC**。
  宿主 SVG 的 U1 D 名字带约 x=180–203，USB 最近 D 名字带约 x=437–497，中间留空且相向；
  `evidence/534m/render_final.png` 已逐岛目检，CC 短线、C1 净空和 CH343 两列调制标签均保持。
- 本批无生产代码改动，故无伪变异/新增测试；主代理独立重跑 v44 compile。
  证据：`evidence/534m/`（compile、plan/apply、lint/DRC、netlist、connectivity、SVG/PNG）。

### 2026-11-03 总复验与交付状态

- 全量 Python：**9090 passed / 25 skipped / 2 failed / 1 warning**（740.10 s）。
  两条均为既有环境红：`test_193_process_guards.py::test_whole_suite_run_queues_behind_two_slots`
  （`~/.boardwise/pytest-slots` ACL，fail-open 后无排队文案）与
  `test_193_secrecy_hooks.py::test_the_posix_installer_sets_hooks_path_and_the_exec_bit`
  （MSYS `NtCreateDirectoryObject` `0xC0000022`）；没有本批回归。
- connector：`npm test` **542 passed / 0 failed**，`npm run typecheck` 通过。
  dsh-plugin：typecheck 通过、**127 passed / 1 skipped**、build 通过；CLI 内部绘制变化不需要
  新增 DSH 工具或 bump。`npm run smoke:draw` 在系统 Temp 首次因写 SVG 权限失败（编译本身
  3 候选成功），按 Windows 约束把 `TEMP/TMP` 指到工作区后同一标准脚本通过：普通编译
  3 候选、页面编译 8 页、lint 回放均 PASS。
- Rust：`cargo fmt --check`、`cargo clippy -- -D warnings`、`cargo test` 全过；
  workspace **111 passed / 4 ignored**（语料依赖项）。
- 最终只保留 Board1 **P20 `e02907a663e2f6b8`** 与 Board2 参考 P1 `30560d9c0a52a6d2`；
  daemon 已停。`evidence/534j/`、`534k/`、`534l/`、`534m/` 的 `SHA256SUMS` 全部校验 OK。
  本工作树的 053J/053K 源码、测试与本说明均未提交；`package.json`、`cases/` 和根下 `tmp*`
  属于其他工作，未触碰。

### 2026-11-03 续十：P20 拒收与官方 skill 调研（053N）

- **撤回上面的“最终交付”判断**：岳用局部截图指出 V3 折线、旗标压线、重复 D−、
  D+/A6 与 D−/A7、VCC/RTS 等重叠。主代理的视觉自审失职；`lint 0E/1W` 与逐脚通过只说明
  机器读数，不能抵销这些真实缺陷。P20 改记为**拒收实验页**，后续不得作为成品推荐。
- 官方仓库（均为 MIT）：
  [easyeda-api-skill](https://github.com/easyeda/easyeda-api-skill)、
  [easyeda-format-skill](https://github.com/easyeda/easyeda-format-skill)、
  [easyeda-eprj3-skill](https://github.com/easyeda/easyeda-eprj3-skill)。
  前者的
  [SCH_PrimitiveAttribute](https://github.com/easyeda/easyeda-api-skill/blob/main/references/classes/SCH_PrimitiveAttribute.md)
  明确提供 `createNetLabel/get/getAll/modify`，ATTR 的 `x/y` 可独立修改；
  [源格式 ATTR](https://github.com/easyeda/easyeda-api-skill/blob/main/format/schematic/attr.md)
  同样把文字坐标作为独立字段。
- 当前宿主 **4.1.93** 只读探针实测：`createNetLabel/get/getAll/modify`、
  `sch_PrimitiveText.create/get/modify`、`sch_PrimitiveWire.create/get/modify` 全部存在且为 function，
  arity 与官方文档一致（`createNetLabel=3`、ATTR `modify=2`）。
  证据：`evidence/534n/native-api-probe.json`。这推翻了把 3.2 时代的“native label 不可用”
  直接套到当前宿主的假设，但尚未做写操作，不能据此宣称功能已验收。
- eprj3 的
  [布局约束](https://github.com/easyeda/easyeda-eprj3-skill/blob/main/SKILL.md)
  与当前缺陷同因：近处必须画可见导线、不要让每个引脚扇成 netlabel、去耦与 IC 同块、
  标签只做远距离连接。其
  [add-netlabel](https://github.com/easyeda/easyeda-eprj3-skill/blob/main/scripts/add-netlabel.js)
  仍默认把 NET ATTR 放在导线中点，其 `validate.js` 只查结构不查文字重叠，**不能原样替代
  boardwise 的布局/视觉闸**。
- 推荐集成顺序：先在空测试页做原生 netlabel + ATTR get/modify 垂直切片（标签电气锚点与
  文字显示坐标分离，回读/渲染/网表验证）；再把最小 typed attr 读写动作接入现有 boardwise
  daemon 与页守卫；随后让 `partTexts` 真正移动 ATTR，并处理同线重复标签。最后才按官方
  “近处走线、去耦同块”的规则改布局。官方 `/execute` 任意 JS 桥不替换现有白名单、审计、
  R1–R3；format/eprj3 校验只作为结构闸补充，不冒充可读性验收。

### 2026-11-03 053O：原生标签空页垂直切片（一个缺口）

- **目标**：只验证当前 4.1.93 宿主能否用既有 typed action 创建可回读的 V3 原生 NET ATTR；
  不实现 connector、不改 P20、不改折线算法。成功后才派下一批最小 ATTR 读写动作。
- **唯一真机范围**：工程名逐字 `test V4`；以 `bridge status` 当前实例寻址，旧实例 id 不得猜测。
  R1 的 `doc.list` 必须同时见 Board1 P20 `e02907a663e2f6b8` 与 Board2 P1
  `30560d9c0a52a6d2`；参考页与 ROBOT 窗口绝不写。仅允许 `sch.doc.new` 新建一页，随后以返回的
  新页 UUID 为每次写动作的 `pageUuid`，并先回读证明新页 0 器件、0 wire、0 flag。
- **探针**：新页放 C25744 于 `(300,300)`，designator `R900`；先用 `sch.component_pins` 与
  `sch.geometry` 实测引脚，不预设 ±20 成立。由实测右侧引脚向外画一条水平 V3 导线，在导线末端
  调一次 `sch.place_netlabel`（`timeoutMs=8000`），不得用折线或手工 NET ATTR 替代。
  超时/失败先回读，禁止重试堆件；失败即停并交回失败证据。
- **禁止**：不写 package.json、cases、未提交的 053J/K 文件；不删除页或件；不执行任意 JS；
  不做 git 写；不用 `rm`；不派生新 agent；不修改源码；不动 Board2 P1。
- **证据**：`.tmp_534o/` 只放即时输出，长期证据落 `evidence/534o/`：环境身份、空页、引脚、导线、
  `place_netlabel` 原始结果、创建后 `sch.geometry`、宿主 `sch.netlist`、PNG 与 SVG。JSON 必须记录
  pageUuid；渲染路径按 `export.render` 实际返回写盘，不把不存在的返回字段当成功。
- **验收**：原生标签 action 成功或明确报告 landedAnyway，网表证明 R900 右 pin 属于 V3，
  渲染中能看见且只看见一枚 V3 名称，导线为直线。主代理亲看 PNG/SVG 与原始回读后裁决；
  这里不验收 ATTR modify、D+/D−、VCC/RTS、旗标或整页可读性。
- **执行预算**：一个 coder，最多 30 步 / 25 分钟；聚焦检查只读现有 handler，不跑全量测试。
  交回 ≤1200 字，含 pageUuid、实际命令、原始返回摘要、证据路径和未验证项。

#### 053O 复跑决定（同一缺口，不扩大验收）

- 首轮遵守缺件即停：C25744 的 lcsc / deviceUuid 均不在 `test V4` 工程库，原生标签尚未调用。
  P21 `6f7a271dfc7ec3e0` 已证明只有 A4 sheet，证据 `evidence/534o/probe-summary.json`。
- 复跑只允许在该空页放 **C21190（本 CH343 电路的 R0603-1k，P20 apply 已有成功记录）**，
  designator R900，坐标 `(300,300)`；这是同功能双端器件的探针锚点，不声称电阻值与原计划相同。
  仍须实测引脚，不接受无器件降级；若该已入工程库器件也失败即停。复用 P21，不再建页。
  后续文件名以 `resume-` 前缀与首轮失败证据区分，其余 R1、禁止事项和验收条件不变。

### 2026-11-03 053P：只读 ATTR 枚举与两枚 V3 定性（一个缺口）

- **053O 结果**：R900(C21190) pin2=`(320,300)`，水平 V3 线到 `(420,300)`，宿主网表连通。
  `createNetLabel` 2 ms 返回 undefined；旧回读无匹配，但 SVG/PNG 的中点与末端各一枚 V3，
  故原生标签创建是**未定性**，不是通过。P21=`6f7a271dfc7ec3e0`，wire=`826fcdf4abadc39b`，
  R900=`c60fb2a670afdc5c`，末端文本=`157f86e71e6e601b`（以真机新读为准，不拿旧 id 写）。
- **实现范围**：新增 `sch.list_attributes` 只读 typed action；同步
  `connector/src/actions.ts` 注册/handler、`src/boardwise/bridge/protocol.py`、`docs/bridge.md` §4、
  双方 contract-drift 与新聚焦测试。不得实现 modify、隐藏、删除或任意 JS 执行；不改 drawapply。
- **契约**：`pageUuid` 必填且先 `guardPage`；可选非空 `parentPrimitiveId`，传给
  `sch_PrimitiveAttribute.getAll(parentPrimitiveId)`，缺省才无参 `getAll()`。逐项回读
  primitiveId/parentPrimitiveId/key/value/x/y/rotation/alignMode/fillColor/keyVisible/valueVisible；
  字段失败进入带 primitiveId 的 `readErrors`，API 缺失显式 NOT_IMPLEMENTED，空数组不得伪装成功创建。
  返回 pageUuid/count/attributes/readErrors，不把 `sch_PrimitiveNetLabel` 缺失当成无属性。
- **真机**：只读 `test V4` 的 P21，R1 仍须 P20=`e02907a663e2f6b8`、Board2 P1=
  `30560d9c0a52a6d2` 同时命中；禁止写 P20/P1/ROBOT。需要聚焦仅允许 P21。
  热更只用于当前 `test V4` connector；daemon 是本任务拉起的旧代码，可用项目既有停止/自启动流程
  加载新目录，不能杀未知进程。读取整页、R900、wire 三组 ATTR；另用现有
  `sys.get_document_source(uuid=P21)` 对拍末端文本的来源。不得再调 createNetLabel。
- **验收**：聚焦单测、contract-drift、connector typecheck、Python 动作目录测试通过；
  两处独立变异（页守卫与 parent/字段映射）测试必须红并 `cp` 恢复、sha256 一致。
  真机原始结果落 `evidence/534p/`，包括身份、整页/父级属性、source、结论与版本；
  主代理据此判断末端 V3 是否真是可定位的 NET ATTR，随后才派移动写动作。
- **预算/边界**：一个 coder，最多 40 步 / 30 分钟；不跑全量，不改 package.json/cases/既有053J/K，
  不删页/件，零 git 写、零 rm，临时文件仅 `.tmp_534p/`。交回 ≤1500 字，含测试计数、
  原始 ATTR 摘要、两枚 V3 的判定及仍未验证项；无法实现或热更失败要如实停，不绕过白名单。

### 2026-11-03 053Q：受约束 ATTR 移动垂直切片（一个缺口）

- **主代理复核**：两枚 V3 都是 wire `826fcdf4abadc39b` 的真实 ATTR；API key=`Name`，
  source key=`NET`，坐标 `(370,300)`/`(420,300)`。R900 Designator=`ba64d7a50b448f30`
  @ `(290,305)`，Name=`8096e77dafd038b2`、value=`={Value}` @ `(290,285)`；Value 数据键本身
  无文字坐标，不能选错。053P 的 read action、66 个 connector 聚焦测试、22 个目录测试与两次
  变异证据已抽查。真机仍有 4 窗口，只准 instance 当前报 `test V4` 的那个，绝不按序号猜。
- **实现**：新增 `sch.move_attribute`，同步 actions 注册、protocol、docs/bridge §4、contract-drift
  与聚焦测试。必填 pageUuid/primitiveId/parentPrimitiveId/expectedKey/expectedValue；
  先页守卫，再从**本页** `getAll` 找该 id，核对父级、原 key/value，任何一个不匹配零写入。
  expectedValue 允许空字符串但类型必须匹配；`Name` 的显示值可以是 `={Value}`，不得先展开猜成 1k。
- **写面**：只允许 x/y/rotation/alignMode 至少一项，严格构造白名单 property，禁止透传 params、
  key/value/keyVisible/valueVisible/字体或任意 JS。x/y/rotation 有限数值，alignMode 仅声明允许的类型；
  未提供字段不得发给宿主。modify 前后都读，返回 before/requested/after/applied/mismatched；
  `applied` 只由 fresh `get(id)` 回读所请求字段决定，返回 undefined 但确实移动要如实区分，
  不匹配不算通过。无 sch.modify_primitive、文本覆盖或删除回退。
- **真机顺序**：先恢复主会话 daemon 审计并确认 connector 重连，审计不可用不得写。R1 同前，
  仅 P21=`6f7a271dfc7ec3e0`，先重新 list，旧 attr id 只有核对一致才使用。
  ① R900 Designator 移 `(290,305)→(280,335)`；② wire 中点 V3 移 `(370,300)→(370,320)`。
  两次独立回读，任何一次失败停止后续写并保留现场；不移动末端 V3、不再 createNetLabel、
  不宣称重复标签已解决。最后取 source/netlist/PNG/SVG；R900 pin2 必须仍属 V3，导线几何不变，
  图片明确两处文字已移动且不压本体/导线。本批只验文字移动，不验整页美观或原生创建唯一性。
- **验收**：聚焦 connector、contract-drift、typecheck、目录测试；两处变异（页/父级守卫、
  白名单或回读判成）必须红并 cp+sha256 恢复。证据 `evidence/534q/`，临时 `.tmp_534q/`；
  主代理亲看移动后图片与 source/netlist 后才进入“单线单名”批。
- **预算/边界**：一个 coder，40 步/30 分钟；不跑全量、不改 drawapply/既有053J/K/package.json/cases，
  不建/删页、不删件、零 git 写/零 rm/零额外线 agent。交回≤1500字，含真实移动读数、
  审计文件、测试计数、证据和未验证项；失败不得继续整页布局。

- **审计隔离决定（主代理）**：默认 `~/.boardwise` 当前沙箱仅 RX，审计确实未落盘。
  使用项目公开的 `BOARDWISE_HOME=E:/boardwise/.tmp_534q/home` 隔离测试 daemon 状态；
  daemon/CLI 一律显式携带同一 env，配对 token 由程序自行生成、保存，禁止读取或复制 token。
  这是受支持的隔离配置，不改 ACL、不伪造审计、不绕过页/工程白名单。审计文件必须是
  `.tmp_534q/home/audit/2026-11-03.jsonl`，写动作后在真实记录中核对 action/page/instance。

### 2026-11-03 053R：计划内 ATTR 移动与 P22 单线单名

- 053P/Q 主代理已抽查 diff、变异与真实 ATTR，并亲看 `evidence/534q/moved-page.png`：
  R900 Designator 和 wire Name 都实际移走，netlist 前后字节相同、Line 不变。两枚 V3 尚未消除。
- 按共享集成锁，公开合同/兼容矩阵/negative control 先写在 `tasks/shared-platform.md` §6。
  本批只增加可选 `attributeMoves` 与 draw-module apply 消费，空列表不序列化、不增加调用；
  **不在本批改 label stub、partTexts 算法、attach、readability 或 review**。
- 真机只在 `test V4` 新建 P22：现有编译链出一颗 C21190 和一根 V3 标签线，附加两行
  version=1 的 reference/net 移动形成一次性合成计划，**不调用 createNetLabel**。
  验收是每根连续 wire 恰一枚 Name=V3、文字移动回读、R.pin2∈V3、Line 不变、lint/PNG/SVG
  目检；不把它称作自动布局或 CH343 成品。具体文件域、回退与未覆盖维度以 shared §6 为准。
- 后续批才增加显式 `textPlacement` 规格开关，让 partTexts 和最终标签框生成移动；未写开关的
  旧规格必须保持原字节/旧行为。官方“近处走线、去耦同块”布局改动再另批处理，不混入 shared。

### 2026-11-03 053S：显式 native-attr 文字布局（一个缺口）

- **前置**：053R P24=`fa854ea5b0442773` 主代理亲看过：单线单名、reference/net 移动、
  `lint 0E/0W`；P22/P23 均为失败实验页。value 的 `Name="={Value}"` 幂等修正由 114 项聚焦
  测试覆盖。共享合同不再改，本批只在绘制线生成它已支持的 `attributeMoves`。
- **规格**：新增可选顶层 `textPlacement`，唯一非缺省值 `native-attr`。缺省不序列化、不改变
  spec 或 plan 的字节/行为；未知值/嵌套坐标仍拒绝。pagecompiler 切模块时传递该字段。
  文档写清它要求 V4 ATTR 能力，旧宿主/connector 在写器件前拒绝，不能静默退回折线。
- **器件文字**：native 模式下把 `LayoutText` 的 reference/value 生成 `PlanAttributeMove`，
  以其 x/y（缺省 bbox 中心）为目标，只移动 x/y，不发明旋转/对齐。`partTexts` 指定侧的器件，
  即使有 symbol 自然锚点也走文字侧候选阶梯，让声明真正可生效；未指定器件仍沿用自然锚点。
  非 native 完全保留 `_part_texts` 原分支。value 数据键无坐标，apply 只能移动可见 Name。
- **网名**：native 模式在最终 wires 确定后，把 LayoutLabel 的 bbox 中心映射到承载它的
  label wire，生成 role=net 的移动。一个 label 找不到/有多个 carrier，或同一 wire 对应多个
  label，**明确报 native 标签歧义并拒绝**，不挑第一枚、不额外调用 createNetLabel。
  本批不宣称连续多段同名去重、不禁弯、不改旗标；这些留给下一批，故 CH343 若撞歧义不得落图。
- **测试**：新增 `tests/test_534s_native_text.py`，覆盖 spec 缺省逐字节、非法值、模块字段传递、
  partTexts 覆盖自然锚点、ref/value/net 三类 move、歧义零计划、未开启时零 attr 调用。
  更新 `docs/draw.md` 053R“本批不生成”与 053S 的实际行为；两处变异（缺省输出、目标映射）
  必须红并 cp+sha256 恢复。聚焦回归含 053R/053d/053J/K 等相关测试，不跑全量。
- **真机**：只 `test V4` 新 P25，合法两 R divider，真实图幅 `0,0,1170,825`，规格开启
  native-attr 且 `partTexts.R1=left`。**不得用合成脚本附 moves**，plan 必须自行生成
  R1.reference、R1.value 和 V3.net 三项且目标与 layout 一致；apply 后回读三项 after、
  Name 公式不变、V3 中点两端连通、Line 不变、`draw lint 0E`、PNG/SVG。保留旧页不删。
- **执行**：一个 coder，显式 `opencode go/deepseek-v4.1-flash`，40 步/30 分钟；文件域限
  presentationspec/pagecompiler/drawcompiler/drawapply、上述新测试、docs/draw 与 `.tmp_534s`/
  `evidence/534s`。不改 cli/changeplan/connector/readability/review/package.json/cases/既有053J/K；
  零 git 写/零 rm/零额外线 agent。交回≤1500字含真实测试计数、自动 moves、P25 证据与未验证项。

### 2026-11-03 053T：连续导线单名、直桩与真实文字模型

- **053S 验收**：P25=`2699d78364e7ad9c`，主代理亲看全图与局部：R13 ref/value 在左、
  V3 单枚在直桩右端，无压线；自动三项移动 after=to，`Name="={Value}"` 不变，V3 两端连通，
  `lint 0E/0W`。自然锚点且未声明 partTexts 的器件不重复发空移动，这是实现的有意选择。
- **目标**：仅 native-attr 改变标签。连续同网 wires（含顶点落在另一段上的 T 接）只显示一个
  名字；不连续同网岛各留一个，绝不把 Type-C 可逆脚用线短接。native 短桩只走直线，
  没有合法直桩就拒绝，不再退回 V3 的 5+5 折线。未开启时旧 candidates/labels/plan 逐字节不变。
- **实现约束**：可在 `LayoutLabel` 加可选 `text_mode`，缺省不序列化/不影响旧 digest。
  native 编译在 **readability 与 geometry hash 之前**按现有 segments 的同网连通分量筛选并标记
  要显示的标签；被省略标签的引脚本来就有导体连接，电气语义不变。旗标覆盖的网名不走该移动。
  `_native_attribute_moves` 继续以最终 wire 下标和保留 label 的 bbox 中心生成，不再撞一对多。
  readability 必须读保留 label 的实际 bbox，不再额外建一个导线中点的幽灵 Name；native 的
  水平 ATTR 不再按导线方向判竖排。默认 `_named_wire_rows` / 旧 label 逻辑不变。
- **stub**：native 的候选只含直段；名字行、owner/其它文字碰撞和 name_carriers 用保留 label 的
  实际 bbox，而不是未移动的中点盒。候选的导线净空仍逐段检查，文本避让失败不得借折线通过。
  native 的 downgrade/note 改成“wire 承载网名 + ATTR 移字”，不得说当前 V4 的 ATTR 不可用；
  029 的历史说明只限旧宿主，不改旧输出文本。
- **测试**：新增 `tests/test_534t_native_labels.py`，覆盖共端点/T接只一名、断开同名各一名、
  旗标例外、native 全直桩、旧候选不变、readability 无幽灵/竖排误判、最终 move 下标与去重后
  连通期望。跑 053S/R/534 标签与 readability 相关聚焦回归，两次变异（分量去重、native 行模型）
  红后 cp+sha256 恢复。未写 textPlacement 的计划仍无 attributeMoves。
- **证据边界**：用 `.tmp_fix/v45.presentation.json`（v44 + native-attr，不改其它布局）跑离线
  compile/预览，记录保留 D+/D− 数、全部 label wire 是否直段、移动目标与编译/readability 读数到
  `evidence/534t/`。**旗标压线/去耦/USB回环尚未修，本批不把 CH343 整页 apply 到画布**；
  若要真机 plan 必须先新建空 P26，只落 plan/report，不 apply，不宣称整页通过。最终三关在旗标批后。
- **执行**：一个 coder，显式 `opencode go/deepseek-v4.1-flash`，40 步/30 分钟；文件域限
  layoutplan/drawcompiler/drawapply/readability、新测试、docs/draw、`.tmp_534t`/`evidence/534t`。
  不改 cli/changeplan/connector/package.json/cases/既有053J/K；零 git 写/零 rm/零额外线 agent。

### 2026-11-03 053V：每岛一枚显示名，重复 NET 隐藏

- **053T 复验**：聚焦 376 passed/4 skipped，v45 离线 compile 通过但 plan 被 Type-C D−
  两个可逆脚名字行相距 8.5 拒绝，未建 P26。`pagecompiler.py` 两处 `text_mode` 传播是页面路径
  必需补丁，主代理接受该必要文件扩展；缺它整个功能在 page path 失效。旧规格路径不变。
- **053U 复验**：P21 末端 V3 隐藏、另一枚仍显示，主代理亲看通过，netlist 字节相同；
  `moveVersion` 缺失恢复为拒绝，72 项版本/doc 测试绿。现在可生成 version=2 的 wire/net
  `valueVisible=false`，不能删除标签或清空导线 net。
- **策略**：先保留053T的物理连通去重，再在每个模块编译视图内、对**不连续**的同网标签
  只选一枚显示，其余标 `text_mode="native-hidden"`。显示项按“label bbox 中心离 pin 更远”
  优先、同距离按原顺序，避免留下5单位短桩文字而隐藏更清楚的长桩。隐藏label仍参与
  derive_netlist与同名跨岛合并；不得变成无网名导线，也不跨可逆脚补线。旗标网维持原例外。
- **落地**：`native-hidden` 生成 version=2、role=net、`to={valueVisible:false}`；可见项仍
  version=1、移到label bbox中心。隐藏项不再产生文字盒/name carrier/owner碰撞，但仍要导线净空、
  只用直桩；readability不得为隐藏项再造默认中点幽灵。可见/隐藏都保持最终wire下标唯一，
  候选重复仍拒绝。旧规格/无native标记行为不变，pagecompiler继续传播两种text_mode。
- **测试**：新增 `tests/test_534v_label_visibility.py`：同模块断开同名一显一隐、优先清楚位置、
  隐藏label电气命名不丢、v2 move/隐藏幂等、无幽灵/无8.5重复carrier误报、旧计划不变。
  跑053T/S/R/U相关聚焦与doc_claims，两次变异（可见项选择、隐藏文字模型）红后cp+sha恢复。
- **离线/真机计划**：同一 v45 规格重跑compile；若过，R1后在test V4新建空P26，真实图幅
  `0,0,1170,825`跑draw plan/report，记录D+/D−各一显、隐藏move与直桩。**本批仍不apply整页**，
  旗标/去耦/USB局部布局下一批改，P26空白或plan失败都如实交证据，不借机器编译称视觉通过。
- **执行**：一个coder，显式 `opencode go/deepseek-v4.1-flash`，40步/30分钟；文件域限
  layoutplan/drawcompiler/drawapply/readability/新测试/docs draw、`.tmp_534v`/`evidence/534v`。
  不改cli/changeplan/connector/package.json/cases/既有053J/K，零git写/零rm/零额外线agent。

### 2026-11-03 053W：旗标外形压线的整页闭环

- **053V 状态**：P26=`9b729f3ad67a20d6` 仅空白页+plan，D+/D−各一显一隐、直桩、
  257 passed/1 skipped；未apply。`pagecompiler._add_flag`只在模块occupied登记外形，
  不核整页导线；同时不能先验认定它就是唯一来源，必须让最终plan指出每个碰撞。
- **硬检查**：readability新增 `flag-body-on-wire`：用`flag_glyph_box`的实测外形，逐段
  `_first_box_crossing`检查正长度内部交叉，报旗标net/symbolRef/位置、被穿wire及net。
  沿框/角点接触不误报；未知的profile/body不伪造零碰撞。自己的主干穿旗也不豁免
  （_flag_room已有同规则）；正常引线从连接点向后离开不应被误判。此检查对所有图纸有效，
  因为它指出真实缺陷，不是排版选项。
- **native修复**：在整页拼装/readability前，对碰撞旗标按网格最近距离尝试合法移位。
  保留symbolRef/net与竖直姿态，方向轮转/距离顺序固定；原anchor到候选点用同net直线连接，
  若旧anchor是既有lead末端就延长它，否则新增一段，不能留下悬空或跨异网线。
  新外形须避开全部导线、器件、其它旗标/文字/页界，相关module frames同步，不得静默扩大重叠。
  原位置与候选、距离和lead变化写plan notes。找不到即候选失败，不回退到压线原位置。
  非native的摆放/字节不变（新增检查除外），不得为避碰撞删除旗标或清空net。
- **测试**：新增`tests/test_534w_flag_body.py`：GND压RXD/+5V能复现、边接触豁免、同网主干
  穿过也报、native最近合法移位及net/lead保持、无法落位拒绝、非native布局不变。
  相关053V/T/S/R、069/074/147旗标与pagecompiler/readability聚焦回归；两次变异（碰撞检测、
  移位后lead/外形）红后cp+sha恢复。不得删旧夹具或把失败改成通过。
- **证据**：v45离线compile/plan候选逐个记碰撞与修复，若全部合法才在test V4用现有空白P26
  重新`draw plan`（P26仍须空，否则新页），**仍不apply整页**，因CC/去耦文字布局未验收。
  记录`evidence/534w/`的before/after旗标框、碰撞清单和plan。无合法候选就如实停，不改电路net。
- **执行**：一个coder，显式`opencode go/deepseek-v4.1-flash`，40步/30分钟；文件域限
  pagecompiler/drawcompiler/readability/新测试/docs draw、`.tmp_534w`/`evidence/534w`。
  不改cli/changeplan/connector/package.json/cases/既有053J/K，零git写/零rm/零额外线agent。

#### 053W 续：贴边也是缺陷（既有 FLAG_CLEARANCE=5）

- 主代理不接受“0内部交叉＝没有缺陷”：P20 的 GND 是外形边缘与导线相贴，线宽后就是岳截图的
  重合。`drawcompiler.FLAG_CLEARANCE=5.0` 的既有注释明确写着“is about touching”，这不是新阈值。
- `flag-body-on-wire` 改为按**glyph外扩5单位**检查，报告实际间距不足，不再把边缘接触豁免。
  唯一豁免是同网、从anchor**向glyph反方向**离开的正常引线；同网其它主干、异网导线不豁免。
  pagecompiler的碰撞识别与候选复检必须调用同一个判定，不能一边5净距、另一边仍只查内部。
  `readability.__all__`补新常量；HARD_KINDS不新增第二种kind，只修正同一规则的含义。
- 把“边/角都豁免”的测试改成：净距内贴边必报、超过5才放行、正常lead豁免、同网主干仍报；
  native重定位后逐flag净距≥5且net/lead不变。跑053W/V/T/S/R与069/074/147/pagecompiler相关
  聚焦集；做一次净距判定变异，cp+sha256恢复。053W子代理自报约60步超预算，本续批最多30步/
  25分钟，显式opencode go/deepseek-v4.1-flash，不扩范围。
- v45重跑compile与P26空白页plan，记录实际移动的旗标、最近净距和readability；若仍不合法
  就停下，不能拿“0内部交叉”宣称修复。CC/去耦留下一批，整页仍不apply。

#### 053W 续二：模块梯子与整页净距统一

- 053W续实测：新检查在P20抓出GND主干净距1，证明贴边不能被内部交叉掩盖；但v45变成
  0候选，原因是usb_c R1.2的模块旗标梯子仍走旧room模型，临时置空检查才恢复4候选。
  **不得保留这个绕过**。下一批只统一native候选判定，非native路径保持原样。
- native `_rail_flag_seat` / `_flag_pin_lead` 的fits在计算候选glyph后，对router.edges与
  own_edges调用同一`readability._flag_body_offence`，同时保留solid/page/blocked/lead净空；
  正常lead豁免的语义双方一致。可以让room接受一个判线回调，不能复制一把不同尺子或关掉检查。
- 钉住usb_c R1.2这类原本被旧room误拒的位置：候选应真实落在净距≥5处，v45恢复合法候选，
  最终`flag-body-on-wire`为零；不得把失败测试改成无检查通过。跑053W/V/T/S/R与069/074/147/
  pagecompiler相关聚焦；一次“fits与最终判定不一致”的变异必须红并cp+sha恢复。
- 更新docs/draw.md的053W规则，补v45合法候选与P26空白页plan（R1同前，真实图幅
  0,0,1170,825）。逐旗记录before/after净距，CC/去耦布局仍未验收，整页不apply。
- 一个coder，显式opencode go/deepseek-v4.1-flash，35步/25分钟；文件域同053W，
  不改cli/changeplan/connector/package.json/cases/既有053J/K，零git写/零rm/零额外线agent。

### 2026-11-03 053X：页间 native 标签、去耦同块与整页验收

- **053W 验收边界**：统一5净距与native旗标梯子/预留墙后，v45恢复4候选，聚焦
  302 passed/5 skipped；P26=`9b729f3ad67a20d6`仍空白，plan 11件/53线/17旗通过。
  尚不能据此宣称渲染正确。子代理超预算情况已记录，本批不扩算法范围。
- **页间缺口**：pagecompiler `_port`/`_add_label`产生或选出的label仍可能`text_mode=""`，
  导致跨岛V3可回到折线、readability继续建旧中点幽灵。native规格下这些label必须标为
  `native`（已有native-hidden不改成可见），保留其既有version1移字，候选也遵守直桩。
  非native保持原对象与字节；补页间V3/RTS的text_mode、直桩、readability和move测试。
- **布局规格**：新建`.tmp_fix/v46.presentation.json`（以v45为基）：C3/C4从caps移入ch343，
  删除caps模块/attach及moduleOrder对应项；保留其module locks（先C3=-30,0/C4=35,0），
  partTexts改C3=left、C4=right，去耦在芯片左右外侧。R1=above、R2=below，分开CC电阻文字。
  不改电路net/class、USB可逆脚拓扑、其它器件lock或旧规格。若编译证据表明该相对位置不合法，
  只允许将C3/C4锁到同块芯片外侧的合法位置并记录，不得改回远端独立岛来冒充“同块”。
- **工序**：相关聚焦测试与两次变异（页间native传播、非native不变）后，离线compile；
  R1工程`test V4`、P20=`e02907a663e2f6b8`、Board2 P1=`30560d9c0a52a6d2`，新建空P27，
  真实图幅`0,0,1170,825`做plan。plan不ok只进evidence，不apply。ok才apply P27并取
  draw lint、宿主DRC、独立逐脚（目标52/52连接+3NC=55项）、ATTR/netlist/source/PNG/SVG。
  重点核对V3无折线、旗标不压线、D+/D−无局部重复、D+/A6和D−/A7不重叠、VCC/RTS不重叠、
  USB/CC无绕线、去耦贴近且文字在外。主代理亲看后才判视觉，agent不得自称最终验收。
- **清理条件（用户已明确要求“新建页就删旧页”）**：只有上述机器检查与主代理视觉都通过，
  才另按R1核对并删除P20和本批产生的P21–P26实验页，Board2 P1绝不动；P27保留为唯一
  Board1原理图页。任何一页缺失/身份不符按R3停下，不猜、不替代；未通过一页都不删。
  清理后重跑全工程DRC，证明失败实验页也不再参与计数。
- **执行**：一个coder，显式`opencode go/deepseek-v4.1-flash`，40步/30分钟；文件域限
  pagecompiler/新测试/docs draw/v46规格/`.tmp_534x`/`evidence/534x`。不改其它源码/
  cli/changeplan/connector/package.json/cases/既有053J/K，零git写/零rm/零额外线agent。
  真机env沿用`.tmp_534q/home`与写白名单，收工保留现场和daemon供主代理验收。

### 2026-11-03 053Y：局部网名、H1长文字与lint清零误差

- **P27拒收**：主代理亲看确认V3直桩、去耦在芯片左右、VCC/RTS分开、Type-C无重复D+/D−；
  但lint `1E/2W`，H1长型号被地线穿过，CTS/DSR各报重复名，CC1/CC2/V3被自动命名。
  独立脚本实测**55/55连接+3/3NC=58/58**（原任务书的52是线数，纠正，不改验收含义）。
- **先查再改**：只读P27的ATTR/geometry/source与drawlint对应行，给CTS/DSR每条Name的
  parent、文本坐标、Line点列、是否同一连续导体。若确实跨模块接线后同线重复，在整页合并后
  再跑物理连通去重（只去掉有导体保证的冗余显示）；若是不同岛的合法边界标签，保留并记录
  为什么L5归组/报警，不能为清零而删网名或把真缺陷改判合法。必要时修drawlint的归组，
  但必须有逐点反例，不能单纯压WARN。
- **规格v47**：以v46为基，`partTexts.H1=above`，位号与长型号都离开下方地线。
  新增一条`localLabelObligations`（V3、CC1、CC2），说明这些是工程师显式命名、同块后仍需
  保留的局部网名；导体尽量直连，显示名每模块一枚，重复文字可隐藏但NET不可清。
  不改C3/C4同块位置、Type-C条目、其它locks、net/class或v45/v46。
- **验证**：补局部网名保留/页间真实连续去重或L5反例、H1目标框无穿线测试；053X/W/V/T/S/R
  聚焦与两次cp+sha变异。新P28离线compile→空页plan→ok后apply，目标draw lint 0E；
  每个WARN给出具体导线/岛/距离解释，未解释不准交付。宿主DRC按P28计0E，独立逐脚55/55+3NC，
  CC1/CC2/V3不得再是`$8N…`自动名；保存PNG/SVG/ATTR/source/audit到`evidence/534y/`。
- **边界**：仍不删P20–P27或参考页，主代理亲看P28全图及五类局部后才另批清理。
  一个coder，显式opencode go/deepseek-v4.1-flash，40步/30分钟；文件域限
  pagecompiler/drawcompiler/drawlint/readability/新测试/docs draw/v47规格/`.tmp_534y`/
  `evidence/534y`。不改cli/changeplan/connector/package.json/cases/既有053J/K，零git写/零rm。

### 2026-11-03 053Z：文字回到自身载体，H1移出地线区

- **053Y复核**：CTS/RI的Name离岸40–55，压到RXD/DSR，不是该删除的重名；L5消息重复
  第一文本的报告bug已修且不改分组/严重度。P27导出实际有正常CC1/CC2/V3、无$8N/$1N/$2N，
  前一条“自动名”判断撤回，**v47新增localLabelObligations取消**（它改契约且实测不可编译）。
- **硬检查**：native可见label的文字盒距自身承载wire超过一个10单位网格即报
  `native-label-off-carrier`；隐藏label不检查显示位置，非native不变。distance量文字盒到
  polyline的最近距离，不能只看anchor或lineGroup。P27的CTS=40/RI=55必须能复现，
  防止以后再把“名字移到别的线上”当成attr移字成功。
- **页间标签**：native `_add_label` 在既有label box/occupied基础上，用固定的近距/两列候选
  重选文字盒：保持锚点/net、盒子尺寸与水平阅读，候选文字盒距异网导线≥10，且自身能用
  一条直桩到达（盒中心为候选终点）；无合法位置返回layout-unsat，不回退离岸短桩。
  该选择发生在page最终geometry hash/readability之前，因此`_native_attribute_moves`的
  目标box、直桩和门禁是同一位置。旧规格的旧`_label_box`路径不变。
- **H1**：v47改为v46 + `partTexts.H1=right` 优先，目标是长型号不再跨x=140地旗引线；
  先用离线几何验证。若right不合法，才比较其它侧并保留失败证据，不许只凭编译成功选定。
  不新增V3/CC义务、不改C3/C4位置、其它locks/net/class或v45/v46。
- **测试**：`tests/test_534z_label_carriers.py`复现CTS/RI离岸、候选盒与异网净距、
  直桩终点/ATTR目标一致、非native字节不变、H1不被穿。053X/Y/W/V/T/S/R与drawlint相关聚焦，
  两次cp+sha变异（离岸检测、候选净距）红后恢复。新P28 compile→空页plan→ok后apply。
- **验收**：P28 draw lint 0E，WARN逐条几何解释；宿主DRC按P28 0E，独立逐脚
  55/55连接+3NC=58/58，CC1/CC2/V3保持规格名，PNG/SVG/ATTR/source/audit落
  `evidence/534z/`。主代理亲看全图与五类局部后才清理旧页，agent不得自称最终视觉通过。
- **执行**：一个coder，显式opencode go/deepseek-v4.1-flash，40步/30分钟；文件域限
  layoutplan/pagecompiler/drawcompiler/drawapply/readability/drawlint/新测试/docs draw/
  v47规格/`.tmp_534z`/`evidence/534z`。不改cli/changeplan/connector/package.json/cases/
  既有053J/K，零git写/零rm/零额外线agent。

### 2026-11-03 053AA：参考页模板重放（停止自动布局反复试错）

- **P28拒收**：自动布局的路径仍让模块自带标签离岸、H1与DSR相碰，未达lint0E；旧页全保留。
  继续微调桩长/位置已缺少可靠依据。Board2 P1=`30560d9c0a52a6d2`已只读导出并亲看，
  器件值/MPN多重集与规格一致，几何清楚，是用户提供的实测模板。
- **做法**：`.tmp_534ab/`一次性`build_reference_plan.py`读取`evidence/534aa/`的
  source/geometry/attributes和现有电路+符号库，生成`LayoutPlan`与正常`ChangePlan`。
  不复用原primitive id、不调用set_document_source、不改参考页/电路规格，不新增生产算法。
  器件origin/pose、真实wire折线、旗标、可见文字锚点按模板；位号由现有plan分配器给。
  交付仍走现有typed place/wire/flag/ATTR移动与页守卫，不是源文档覆盖。
- **映射纪律**：固定器件U1/H1/USB1/D1按身份，R5→R3；VBUS电容按值对应；
  CC电阻和芯片去耦按**引脚几何+导线连通**确定，不凭编号猜。输出ref→spec映射、pin groups、
  不能判定的成员即停止。参考NET/label归属与规格网不一致即停止，不能拿“同器件”替代连通。
  单module presentation只为module_plan承载，native-attr只移动文字，不重写电气拓扑。
- **文字**：按参考ATTR的Designator/可见Name生成LayoutText；partTexts依实际侧别声明以便
  生成移动。NET label anchor取其在父wire上的真实最近点，文字盒距该wire>10即拒绝模板，
  不把参考中的好位置变成离岸文字。Type-C同part同名按053V保留较清楚一枚、其余version2隐藏；
  不全局删跨岛同名标签。每枚label必须能映射父wire/网名；缺父级、歧义或库profile不符即停。
- **验证**：builder自身assert覆盖11器件、NC引脚集合、映射、flag/label父级、原始连通分组、
  ChangePlan.from_jsonable与readability/flag净距。失败不生成可apply计划，证据仍落盘。
  新P29先空页census/真实page pool和baseline，再生成plan并apply；禁止无pool的spec-id直接落图。
- **验收**：P29 draw lint 0E（WARN须逐条几何解释）、宿主DRC按P29 0E、独立逐脚
  55/55连接+3NC=58/58、ATTR/netlist/source/PNG/SVG。重点亲看参考页五区与V3/旗标/
  D±/A6/A7/VCC-RTS/H1长型号，过了才另批清理P20–P28。任何旧页都不提前删除。
- **执行**：一个coder，显式opencode go/deepseek-v4.1-flash，40步/30分钟；文件域限
  `.tmp_534ab/`与`evidence/534ab/`及必要的一次性验证脚本，**不改生产源码**/规格库/
  package.json/cases/既有053J/K，零git写/零rm/零额外线agent。bridge沿用`.tmp_534q/home`
  与写白名单，实例以status为准，不读token。

### 2026-11-03 053AC：P29视觉通过与旧实验页清理

- **最终验收**：P29=`6625ff26bf59d14c`，draw lint `0E/0W/0I`、宿主DRC按本页0、独立逐脚
  **55/55连接+3/3NC=58/58**。主代理亲看全图和CH343/USB/H1局部：去耦贴近、D+/D−单显、
  旗标净空、VCC/RTS分离。H5完整Name从`(555,450)`移至`(555,420)`（`3e75b7908fff0b01`），
  因为参考短`2x5P`不会碰地线、完整型号会；源仅该ATTR与时间戳变化，netlist字节相同。
  最终宿主PNG `evidence/534ab/final_p29.png` 已亲看，长型号与地线分离。
- **用户既定授权**：“新建页就删旧页”。现在可删的只有以下9个实验页，身份以doc.list焦点
  `test V4`+UUID+页名+特征核对，禁止按内容相似度/编号猜：
  P20 `e02907a663e2f6b8`(CH343拒收页，11件)、P21 `6f7a271dfc7ec3e0`(R900单件V3探针)、
  P22 `f5be857b564e7f3c`(两电阻失败页)、P23 `11466f39d6ac4507`(两电阻图幅失败页)、
  P24 `fa854ea5b0442773`(两电阻通过探针)、P25 `2699d78364e7ad9c`(两电阻ATTR探针)、
  P26 `9b729f3ad67a20d6`(空白计划页，0件/0线/0旗)、P27 `fcbf0ddbe79dc94d`(CH343拒收页)、
  P28 `ea468a6523625fa0`(CH343拒收页)。
- **禁地**：保留P29与Board2 P1=`30560d9c0a52a6d2`，不得按`P1`名字或11件特征选删；
  其它窗口/工程不写。逐次删除前核对目标仍在且特征匹配，失败/缺失按R3停止，不补删、不重试。
  每次写原始结果和审计存`evidence/534ac/`。任何异常不得声称“已清空”。
- **清后**：doc.list必须只剩Board1 P29与Board2 P1两张原理图页；重跑全工程DRC、
  P29 draw lint、独立逐脚58/58和最终render。失败实验页不得再贡献DRC计数。
  任务完成前daemon保留给主代理独立复核，最终测试后由主代理停止。
- **执行**：一个coder，显式opencode go/deepseek-v4.1-flash，最多20步/20分钟；只写
  `.tmp_534ac/`与`evidence/534ac/`，不改源码、不git写、零rm、零额外线agent。

### 2026-11-03 续十一：053AA–053AC 模板重放与最终验收

- **最终页**：Board1 P29=`6625ff26bf59d14c`；Board2 仍只有用户参考P1=
  `30560d9c0a52a6d2`。主代理独立`doc.list`确认两张原理图页，参考页未改。
- **路线**：自动布局的P27/P28都未通过，不继续调桩。读取Board2 P1的实际source/geometry/
  attributes，在`.tmp_534ab/build_reference_plan.py`生成正常LayoutPlan/ChangePlan，经现有typed
  apply重建图元；没有`set_document_source`、没有复用primitive id、没有改生产算法或电路规格。
- **映射纠错**：不能按编号猜去耦。实测参考C2接U1.4(V3)→规格C3，参考C3接U1.15(VCC)→规格C4；
  参考R3接USB1.A5(CC1)→规格R1，参考R4接USB1.B5(CC2)→规格R2；R5→R3，VBUS电容按值。
  证据`evidence/534ab/mapping.json`、`selfcheck.json`。位号由真实page pool分配，不是套用参考位号。
- **机器验收**：`draw lint 0E/0W/0I`（`evidence/534ab/lint2.json`）；全工程DRC在旧页清理后
  `passed=true`（`evidence/534ac/drc_p29_after_cleanup.json`）；独立逐脚**55/55连接+3/3NC=
  58/58**（`evidence/534ac/p29_perpin_after_cleanup.json`），以规格成员+实际位号+宿主netlist为据。
- **视觉验收**：主代理亲看CH343/USB/H1/LED各区，V3无折线、旗标不压线、D+/D−局部单显、
  D+/A6与D−/A7不重叠、VCC/RTS分离、去耦贴近。H5的完整Name由(555,450)上移至(555,420)，
  因为参考短2x5P不碰地线而完整型号会；回读applied=true，netlist字节相同。最终宿主PNG
  `evidence/534ab/final_p29.png`与清后`evidence/534ac/p29_after_cleanup.png`均已亲看。
- **清理**：按用户“新建页就删旧页”，逐页核对UUID/名称/特征后删除P20–P28共9个实验页，
  未碰Board2 P1或任何真实工程；`evidence/534ac/delete_P*.json`和`doclist_final.json`在案。
  清后DRC不再计入失败实验页。页面/删除的落盘持久性没有重启宿主复核，记为未验证，不冒称。
- **能力边界**：053P–053Z新增ATTR读取/受约束移动/可见性、versioned attributeMoves、可选
  textPlacement、同名隐藏、旗标净距与lint修正；默认不写这些规格键时旧行为保留。
  这些API在V4为BETA，旧宿主/connector缺能力要在写器件前拒绝，不能静默退回折线。
  **053AA的模板生成器是一次性证据脚本，不是通用自动布局命令**；不得声称其它板子都能自动
  生成这张效果，也不以官方skill的源码替代boardwise的页守卫、白名单、审计与视觉闸。
- **复验**：最终命令与计数见053AD及`tasks/shared-platform.md` §8；全量仅余两条既有环境红，
  其余各线通过。`package.json`与`cases/`是其他agent的工作，未触碰；本任务没有commit/add/push。

#### 执行与预算记录

- 本轮共22个coder子代理（含resume）。早期付费备用通道一次402后，后续新派单显式使用
  `opencode go/deepseek-v4.1-flash`；没有使用k3-256k。
- 多批实际步数超过派单预算：053U约48/35、053W约60/40、053W续二约50/35、
  053X约55/40、053Z约100/40、053AA约85/40，H5微调约26/12，053U版本复验约30/8。
  超支主要源于宿主行为、页级路径和真实连通排障；没有以扩大文件域/删减验收来续命，
  但拆分与停止纪律未达到预期。后续应先做窄证据切片，不能把大批预算耗在反复试布局。
- 主代理负责任务书、关键diff/变异复核、真实身份/渲染验收与最终测试；子代理实现和证据落盘。
  复验时会话日志可观察主代理`step.begin`共505次（含前段与探索，不是单批配额读数）。
  平台未提供可核的input/output/cache usage，故只记录可观察批次与子代理自报步数，不编token数。
- 真机只写`test V4`的测试页；保留Board2参考页，不动真实工程。daemon的审计HOME隔离在
  `.tmp_534q/home`，程序自行生成/保存配对，未读取或复制token；真机结束后已停止daemon。

### 2026-11-03 053AD：全量回归定位与公开合同补齐

- 第一次全量：**97 failed / 13 errors / 9104 passed / 25 skipped**。主体是053W把5单位
  旗标净距无条件用于旧规格，违背“未开启新能力不改变旧行为”；不是环境故障。
  现将`readability.check()`的该检查限定到`textPlacement=native-attr`，专项直接审计仍可用。
  新negative control证明同一碰撞plan非native `check()`不报、native才报，变异恢复无条件检查即红。
- 指定回归（536/538/533/542/175/143a/178/535/093等）：**225 passed / 1 skipped / 1 failed**；
  剩余093结构钉是去旧打印函数找门禁，实际仍在`_draw_apply_flow`，已改为真实路径而非删断言。
- `contracts/cli/v1.json` 用`.venv/Scripts/python.exe -m tools.cli_contract --write`正式重建，
  只增加`sch.list_attributes`与`sch.move_attribute`的契约说明，未混入无关变更。
  `test_540c_contracts.py + test_093_arch_closure.py`：**81 passed**，证据`evidence/534ad/`。
- 两条既有环境红（pytest槽位ACL、POSIX安装器）单独看待，不能将上述97+13归因于环境。
  最终全量只重跑一次：**9213 passed / 25 skipped / 2 failed**，两条正是既有
  `test_193_process_guards`槽位ACL与`test_193_secrecy_hooks` MSYS权限，97+13回归全部消除。
  connector **576 passed**且typecheck通过；dsh-plugin **127 passed / 1 skipped**且typecheck/build通过；
  `smoke:draw` 3候选/6产物、8页/16产物通过；Rust fmt/clippy/test **111 passed / 4 ignored**；
  `test_doc_claims.py` **33 passed**。P29/参考页未因回归修复改变，未执行git提交。
