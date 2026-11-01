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
