# 排期（2026-11-08 更新；主代理维护，岳裁）

> **2026-10-17 岳裁：v0.6.0 押后到 10 月底**。这段时间不发新版，打磨存量功能，
> 主攻**原理图绘制质量**（目标：先把一个模块画好；布线和布局算法重写），
> 岳会跑测试用例给反馈。0.6.0 的 122 E 阶段 + 高速 A 档冻结到月底前一周再动。

发版规矩不变：挖洞 swarm + 上机 + 实测三闸全过才发；**正式版一周最多一发、何时发由岳定**，其余一律按**内测（prerelease）**发；同一天只发一版；daemon 与 connector 只要求 major.minor 系列同步、补丁号独立，系列升级时两边必须同升；**dsh 插件从 0.6.0 起与 boardwise 外部版本同号**（`0.1.x` 到 `0.1.3` 止；插件改动用固定 commit 复检到达，不为此挪 tag）。

> **549 首次配对显式授权（已随 0.6.1 正式版发布，tag `9ffeb3b`）：本地实现、离线验收及 4.1.93 真机/回滚验收完成；4.1.71 仍只有模拟证据**——
> `boardwise bridge pair <CODE>` 用 CLI token 调 daemon-owned `pair.authorize`（政策测试第四个
> `design_write=False` 例外，`risk=write` 不变），daemon 内存单槽 5 分钟 grant，取消 Origin+TOFU
> 授权；错码不作废 grant（红队裁定），失败只进服务端审计；Connector 编号 Web Crypto only，
> `pairCodeUsed===true` 才轮换。读数：主代理 Python 聚焦 **455 passed / 3 skipped**、Connector
> **608 passed** + typecheck、DSH **137 passed / 1 skipped** + build、Rust **111 passed / 4 ignored**、
> CLI 合同一致；**全量一轮 10611 passed / 25 skipped / 1 xfailed / 23 failed / 5 errors，不是全绿**
> （两条 537A 政策红已补登记、聚焦 126 passed 关闭；4 处 549 测试审计写根目录已改 `tmp_path`；
> 其余为既有货架数据、绘制线在途与 MSYS 环境错误，未跑第二轮）。**真机（EDA 4.1.93 `test V4`）**：
> 独立 home 首次 `bridge pair` 成功、`authorizedBy=pair.authorize`，`checkup` 得 77 components /
> 225 nets（exit 1 是工程自身 85 项 ERROR、`incomplete`），daemon 重启后旧 token 自动重连，
> 回滚后 Connector 0.6.0 / daemon 0.6.1 两窗口 connected、指纹不变；证据
> `outputs/review/549_real/ACCEPTANCE.md`。4.1.71 只有模拟 Origin 证据；
> 部署时 daemon 与 Connector 必须同步。版本号与 Release 另批。

| 版本 | 内容 | 状态 | 依赖 |
|---|---|---|---|
| **v0.5.14**（内测）✅ 10-17 已发 | main 已落：187c / 188A / 188B / 189A1 / 189A2 / 189B / 189C / 189Cf / 190；+ **190S** 底层丝印真机定标（含 editor_pose 上机对拍） | 190S 开工（10-17） | test 窗口在线 |
| **v0.5.15**（**正式版**，岳 10-17 裁）✅ 10-17 已发 | **515B** 保密闸/dsh/文档 12 洞（pre-push 解析失败拒推、hygiene 读不到文件 exit 1、zlib 假头吞流、`-n +8` 绕过、钩子可执行位、dsh 截断标注…）· **516** 岳审查反馈：A1 同电位豁免按绝对电压判、A2 载流按连通分量展开、A3 needs-datasheet 侧车自动并入 + B1/B2 + C1-C5 · R4 实验④结论记档（菜单点击免重载激活成立）· **201C 布线协商踢出本版** | 三闸全过：挖洞✓（23 洞→12 修复）· 实测✓（6242 passed / 0 failed）· 上机✓（双窗热更 verified、在线离线 47/47 对拍、draw lint 0 error） | — |

> **201C 处置（岳 10-17 裁 A）**：201C 布线协商**不进 v0.5.15**。150 落地页回归已实锤——
> 软预留走廊把义务网通道占住，逼 `FB_SENSE` 改走竖段，host 印的**网名行**沿竖段竖排压在 `R8` 器体上
> 0.5 单位，readability 硬拒；而 `FB_SENSE` 恰是 `core/textmetrics.py:126` 已记录的模型例外
> （`WIRE_NAME_MODEL_EXCEPTION`，15/16 吻合、它是唯一例外），readability 从未接这个例外。
> HEAD 对照：HEAD `ok=True`（1 合法候选，5 rejected 全「same geometry」）→ 201C `ok=False`（5 变体全死）。
> 改动整体 backup 在 `.tmp_201c_hold/`（router.py `3375da5b` / drawcompiler.py `221c8c9a` / 201c.patch /
> test_201c_routing.py / test_116 预算版），复活时**按 A 修**：布线后自检网名行，压器体/文本则把名字行盒
> 加进 `blocked` **单网重布一次**（201D 文本行代价的雏形），不接线例外豁免。
| **v0.5.16**（**内测**，岳 10-18 裁） | **审查线资料获取（R6）三连**：**520** `parts hunt` 批量寻址（C 号 → 立创 detail API → `pdfUrl` → 下载 → 带页码 `.txt`；46 颗板 24 个唯一 C 号冷启 41 s、热缓存 1.2 s / 0 外呼；`--offline` 零外呼出工单；只发 C 号，`hunt-audit.jsonl` 逐条留证）· **521** `--apply-facts` 收 AI 读 txt 的产出（六道闸，最硬一条**引文逐字**；改一个字 → `no candidates/` 目录）· **522** `facts_verified` 布尔 → `facts_trust` 三档（`candidate` / `machine_verified` / `verified`；**判据=结论 vs 数字**，十一条算数字的规则吃机器核验、结论类仍要人工；每条 finding 统一带「未人工确认」；verdict 不涂绿）· 附带：`docs/drawing-algorithm-brief.md`（绘图困境/证伪路子/接口，给外部算法推演用） | 三闸：挖洞（522 自审出 2 处回归并修）· 实测见下 · 上机待做 | 真机 daemon 需重启以载入 0.5.16 |
| **v0.5.17**（**内测**，岳 10-18 裁：修完再做真机核验） | **v0.5.16 挖洞补做**（5 缝只读 swarm，46b9c1f..ea6b1ce）→ 12 条高严重级缺陷全修：**521 的引文闸**（纯子串 → 10 字符/3 token 下限 + 两端词边界；`pin_appears` → `pin_appears_in_evidence`，pin 必须印在这条 claim 引的那几行里，一并钉死「引文与事实不绑定」）· **522 的两条绕过**（`OpenDrainPullup`/`UsbCcPulldown` 直接读 `entry.facts`，现在走 `FactsRule.admissible`；四处裸读 `entry.category` 改走 `shelf_declaration`）· **保密审计**（新增 `dest` 记目标 host、审计每次运行清空、`--apply` 只收 http(s)）· **假话与崩溃**（`--offline` 报告不再说「都拿到了」、`facts_trust: null` 报错、`--shelf` 继承 uuid/params、无身份件不再 `IdentityLeak` 崩、`quotes: 5` 不再 TypeError、`.txt` 无页码改判 `no-document`）。新回归 6 条 | 三闸：挖洞✓（12 修）· 实测见下 · 上机待做 | v0.5.16 的 release notes 已标「请用 0.5.17」 |
| **v0.5.18**（**内测**，2026-10-19 立） | **527 收口批**（0.6.0 之前必须落地的尾巴，任务书 `tasks/527_pre060_loose_ends.md`）：**527A** `IntentSource` 转发 `rails`/`signals`/`buses`（按文档构造的合成上下文里合同曾被静默读成空）· **527B** connector `readback` 页型守卫（B4：焦点不在 PCB 页时 `TypeError`）+ 信封文档（B3）· **527C** 189A2 跨视图 7/8/6/2 条分类与裁定 · **527D** `parts classify` + `category_trust`（523：机器核验的件终于有分类授予路径）· **527E** 文档收口（189A1 结案不改、088b DRAFT 归档） | **✅ 2026-10-19 已发**（内测，tag `v0.5.18`）：挖洞两条缝 16 洞 / 14 修 2 记 · 全量 6472 passed / 25 skipped / 0 failed · connector 532 + tsc · dsh 50/1 + build · 上机 3 窗 connector 0.5.18 verified（B4 正/反例 + 对照组）；产物 exe `8e547a0b…` / eext `48abe3b5…` / dsh `e84862c1…` | — |
| **v0.5.19**（内测，未排） | **R4-C（岳 10-19 裁）**：`bridge update-connector --no-reload`（写记录、不 reload，点一次扩展菜单生效，**528A 已落工作树**，含 528A-a 版本闸：显式 `--version` 与 `extension.json` 不一致直接 exit 2，避免一次必然假 FAILED 把人赶去卸载重装）；**stub 方案冻结到 0.6.x 之后**（实验④已证明「写 + 点一次菜单」可用，stub 只剩「零点击」的增量，却要换来无认证 WS 上执行远端载荷的风险）。真机已验：`--no-reload` exit 0、instance id 前后不变、无 `--yes` 也不问确认（`outputs/528a/evidence.md`） | **✅ 2026-10-20 已发（内测，tag `v0.5.19`）**：+ **527D2** `category_provenance` 落货架 · **527D3** 17 个分类读点分档感知（`category_verdict` 三态）· **201F** A\* 可采纳下界（A\* 14.2 s→2.05 s，83 预览逐字节相同）· **四条缝的只读红队 21 洞 / 20 修**（含 3 条比改动前更糟的真回归）。读数：pytest 6621 passed / 25 skipped · connector 536 + tsc · dsh 50/1 + build。产物 exe `4a2fda98…` / eext `4f672ec7…` / dsh `e84862c1…` | — |
| **v0.5.20**（**内测**，2026-10-23） | **审查线实板反馈修复**：#83 铺铜包含性判据恒真（间距静默丢行）· #84 载流不建模铺铜/分支（承担铜时细线档降 UNKNOWN(INFO) 逐段点名）· #85 同封装焊盘对误报间距 · #86 旧库 Value 为空按货架 MPN/C 号补容值；**#88 以 5 条 `xfail(strict=True)` 记档**（铺铜弧当弦视图）· **绘图线并回 main**（merge `534d21f`：520a2–533 多岛落图）+ **535 合并暴露三层回归修复**（`2c71844`：pin-text 单模块容忍、地网降级旗标+记账、埋脚逃逸）+ **535 跟进**（`f4f3709`：143 F1 拒绝保持在 gnd 降级之前）· dsh 迁移（`docs/handoff.md`、SKILL 双副本、根 package.json shim `23b2a53`）；dsh-plugin 0.1.3 | 挖洞✓（dsh 子代理只读红队：0 实锤 / 4 存疑记档）· 实测：dsh 侧 6934 passed / **5 环境红**（3 条钩=沙箱拦 msys BaseNamedObjects、1 条 hunt=假接缝+真网络、1 条=并行竞态单跑即绿，机制均定位记档）——**0 红读数待在非沙箱终端补取**（`--basetemp=$env:TEMP\tmp_pt_rel520`）· connector 536 passed + tsc · dsh 50/1 + build；产物 exe `b0e0dce9…` / eext `E523BD6F…` / dsh `16DA3308…` | — |
| **v0.5.21**（**正式版**，2026-10-23） | **dsh 迁移暴露的测试基建三修**（发布 v0.5.20 时被沙箱环境照出的暗伤）：① `parts hunt` 的 fetch_detail 假接缝修复（`cli.py` 函数内局部 import 甩开猴子补丁 → `globals().get` 优先 + 惰性兜底；`test_520_parts_hunt` 离线密封，521/522 两处同名死补丁一并激活）· ② 钩测试 3 条加 sh 共享对象探测 skip（本机 python 子进程受限时自动 skip，非受限环境照真跑）· ③ guard probe 收集竞态根治（`--confcutdir=tests/`，churn 对拍 5/40→0/40）· 附带：epru docstring 抹除机器路径、handoff「在 dsh 里跑测试」基线节 | 挖洞✓（dsh 红队 0 实锤）· 实测✓（**dsh 与终端双边 6936 passed / 0 failed / 25 skipped / 5 xfailed 逐字一致**，互证等价；钩链另有真实 commit/push 触发旁证）· 上机：无新增 bridge/connector 行为面，闸不适用；产物 exe `93a4be1d…` / eext `55FABAA6…` / dsh `16DA3308…`（0.1.3 未变） | — |
| **v0.6.0**（正式版，2026-10-31） | 200A/B/C 报告与高速审查 + 542 反激人工锚 + CH343 示例 + 527D2/D3 + 540 平台准备 + V4 单 PCB 首批 + #89 同网测量与证据披露 | 全量 **8821 passed / 25 skipped / 0 failed**；connector 542、DSH 127/1、Rust 47+显式4；真机 doctor 9/9、evidence exit 0、P4 lint 0/0/0；三件发布件验收通过 | — |
| **v0.6.1**（**正式版**，2026-11-10 发布；工作树定稿 2026-11-06） | V4 多 PCB 与记录一致性 + 041 跨板声明 + 焊盘/货架/去耦/跨视图修复 + 541 R1/R2/R4 opt-in 闸；CH343 成对布局与持久化 + CH340 第二拓扑；DSH 安装与输出加固；**549 首次配对显式授权** | **已正式发布**：main `47713c2`/`8ad625e`/`9ffeb3b`，tag 与 Release `targetCommitish` 均为 `9ffeb3b`（`prerelease=false`、latest）；发布快照 Python 10628 passed / 39 skipped / 1 xfailed（另两条已登记 115/116 的 098 基线差异、0 errors，不称全量全绿）、Connector 608 + typecheck、DSH 137/1 + build、Rust 111/4 ignored；三件附件回读逐字节比对一致；真机边界以本版 Release 记录为准，不把 partial 写成板级通过 | 真实多板＋库、4.1.94+ 探针、541 R3 与 CH340 重开验证仍开放 |
| **v0.6.x** | **041 跨板网络**（DRAFT → 细化，040b 已落地）+ **V4 适配**（岳 2026-10-19 裁：**11 月起做**，见 `tasks/038-eprj3-tierA.md` §V4） | 0.6.0 后 | — |
| **0.6.0 后（独立方向）** | **AI 电路语义编译层**：网表 → 类型化、类 C 的可读语言，AI 读编译结果而非原始网表；调研任务 `tasks/038_v4_review_line_research.md` 只登记 V3/V4 共用语义边界，不实施编译器 | 先定义语义合同与可验证还原，再逐规则/逐视图小批接入；不与 V4 适配同批 | — |
| 远景 | **R5 SPICE**：岳 10-17 裁——等**原理图绘制过关** + **041 跨板网络**搞定后再开 | 冻结 | 两个前置 |

## 当前主攻（2026-10-31：**0.6.0 已收口，随后进入 0.6.x**）

- **548A 语义窄门：完整 N≥3 面板支路出口通过（2026-11-08，限已测电路族；A-R 补齐灯/蜂鸣器）**：上一轮坐标窄门已回退；本批按证书 §7 补
  G9「同宿主同回流支路组」——同一宿主、同一 other 网、两脚件、组 ≥3 才改行向体位，只读
  网表拓扑与符号脚数，不调坐标阈值/权重。547A 命中 8/9，`--runxfail` 2 passed、出现
  `[XPASS(strict)]` 后摘标（断言未动）2 passed；4 个负控（`201b`×2、`119`、`120`、`534`）
  gate 开/关均 **74 passed / 2 skipped**。邻域 3 条红为工作树既有（gate 关同红），
  `test_547_named_pin_plan` 4 个 error 仍是沙箱 `os.scandir`。**548A 完整 N≥3 面板支路出口通过（限已测电路族，A-R 已补灯/蜂鸣器），仍未跑真机/
  未落画布、不记自动整页**；548B 串联语义不属本批。

- **548C 扰动与组合部分通过（2026-11-08）**：固定 547A 电气夹具，只换表面；A 同功能换符号
  4/4、C 长网名 2/2、D 允许姿态 2/2 过；B 长位号/长值行 0/3 被结构化拒绝（**过拟合**）；
  E 2–3 岛组合 0/2，卡在 mcu 的 GND 7 脚被画成 4 节点。CH343/CH340 既有 pinned 几何前后
  逐字节 identical。未跑真机/未落画布；证据 `evidence/548C/`。
- **548C2 多岛共享电源网统一未通过（2026-11-08，批次前提被证伪）**：E2/E3 的 `layout-unsat/modules[mcu]`
  与岛数无关——547A 自己的 mcu 在 `gndClustering.radius=100` 下**同样** 4 节点失败，它的绿来自出厂测试
  不传预算。真缺口三层：模块层拆分地零命名陈述、页面端口用裸成员名查按脚号建的 `_pin_points`、页面
  label 兜底压住 `texts[7] 'LED'` 且 `segments[20]` 竖命名。「不拆」已被反证（GND 母线横穿 `parts[U1]`）。
  生产代码零改动；4 负控 74 passed / 2 skipped、547A 2 passed、CH34 pinned 逐字节不变。
  **2026-11-08 岳已裁定：禁网络标签、允许库内旗标**；落地由 C7/C7A/C7B（三次未通过）另批。证据 `evidence/548C2/`。

- **0.6.0 四个功能门槛均已完成**：① `200A/200B/200C` 随 `d2130b7` 入库；
  ② 542 P0 反激整页三关、岳人眼和关闭重开验收通过；③ `527D3` 已落；
  ④ `527D2` 已落。早期诊断和失败读数保留在任务书中，不再当作当前进度。
- **本版追加内容**：540 平台准备、CH343 示例、V4 首批单 PCB 工作流，以及 #89 稳压器/FB
  同网测量与证据披露修复。V4 归档的**多 PCB 逐板**已在工作树完成（038P，未提交，
  `test V4` 两个空板对账），多文件合流守卫（038P1，未提交）也已落：同名库**相同副本允许**、
  **分歧拒绝**、**重复 PCB 拒绝**、无 uuid 板按文件名命名；**真实多板 + 库工程、真实 PCB 位图
  和部分样本语义**仍是公开边界（守卫目前只有合成证据）。
- **本版验收已完成**：全量测试、真机、三件发布件与保密闸分别记录；服务端哈希在 Release
  上传后回读。不用旧批次的绿读数替代本版，不把 `incomplete/partial` 写成板级通过。
- **0.6.x**：绘制算法与 Rust strangler 并行；`041` 跨板网络、V4 后续样本与真实多板 + 库工程按任务书
  分批；`R4 stub` 仍冻结，未经岳裁不复活。算法与迁移不同批，shared/全量/真机串行。
- **非阻塞**：R6 的 `L2b`/`L2c`；`529` 去耦分类空白带；`527C2` 跨视图 note 按几何分两句。
- **存量打磨**：岳跑测试用例 → 反馈 → 修复，循环。
- **543J 并联去耦双端共旗返修（2026-11-05 工作树）**：岳发现 P36 的 +5V 共旗而
  GND 不共旗；根因是所有 branch 的 other_net 被写死 `SHARE_ALONE`，未进入距离判断。
  现仅同一 owner/shared_net/other_net 的并联支路开放回流端共簇，CC 等异信号端仍独立。
  新页 **P37=`6087631c7d711217`**：C5/C6 的 GND 合法绕行距离 90≤100，共一面旗；
  19 旗、lint 0E/0W/0I、网表分区与几何逐脚均 55/55+3 NC、逐岛视觉通过。旧 P36 已删，
  Board2 仅 P1；DRC 仅规格 NC 与库属性 WARN。聚焦 **43 passed**，两处变异均先红后
  字节还原。首轮全量另抓到一个 native 哈希合同钉；对照证明非 native 两页不变，
  合同测试 **21 passed**、主代理原失败用例复跑通过。最终全量 **9390 passed /
  25 skipped / 2 既有环境红**；connector 576、dsh 129+1、Rust 111+4、draw smoke
  与 doc-claims 39 均过。证据 `evidence/543j/`。不做 git 写，持久化未重开验证，
  第二拓扑未做。
- **543K/L 成对姿态、文字与 D± 等长（2026-11-05 工作树）**：岳指出 P37 的 USB
  电阻竖放、B6/B7=60/55。现信号型成对二端支路横向且 shared pin 朝宿主，成对文字
  联合选同侧；两网 localLabelObligation 按几何配对、共同长度同时验两脚。新页
  **P38=`0ec4dc022ef38563`**：R7/R8 横向且文字都在左，CC 各130直连，D± 为
  **40/40、60/60、40/40**；C9/C10 共地、R7/R8 独立地旗，USB 去耦竖直和 CH343
  横向未回退。19 旗、lint 0E/0W/0I、两种逐脚均55/55+3 NC、逐岛视觉通过；旧 P37
  已删，Board2 仅 P1；DRC 仅规格 NC 与库属性 WARN。子代理聚焦 29+30、主代理
  8+10、两处主代理变异均先红后字节还原。543M 首轮全量暴露 auto/V45 兼容回归，
  已补 `stub=straight` 门；auto 与 V45 恢复，P38 重编译逐字节不变。子代理聚焦71、
  主代理35、auto 门独立变异先红后还原。最终全量 **9496 passed / 25 skipped /
  2 既有环境红**；connector 576、dsh 129+1、Rust 111+4、draw smoke 与 doc-claims 39
  均过，证据 `evidence/543kl/`。不做 git 写，持久化未重开验证，第二拓扑未做。
- **543G/N/H 第二拓扑与旧账核销（已随 `44901da` 提交）**：P38 已由543N完成
  关闭重开，**saved_verified**。第二拓扑CH340落 **P39=`62e4828acc56a307`**，
  12器件/36计划导线/17旗，lint 0E/0W/0I，独立逐脚 **45/45+15/15NC=60/60**，
  宿主逐岛视觉通过；P38与Board2 P1保留。通用能力补齐信号支路非去耦判定、
  完整flow阅读列、branchOrder消费与振荡bay，未读参考坐标。证据 `evidence/543g/`、
  `evidence/543n/`。P39持久化未重开验证。最终全量 **9962 passed / 25 skipped /
  14 failed**：12条其他agent货架漂移+2条既有Windows环境红，本批6条回归已全修。
  connector 576、dsh 129+1、Rust、draw smoke、CLI合同与仓库卫生均过。
- **201G/515A/201C/201D核销**：201G当前规格1候选、13条软披露和SEC_12V旗位已钉；
  515A六项旧洞有防回归，旗位预留与页框归属两项已修并变异验证；201C/201D经当前
  实验裁决**不复活**（目标缺陷不可复现、旧patch不可应用、201D前提未满足）。
  证据 `evidence/543h/`、`.tmp_543h_201cd/`。交叉与same-statement指标是独立后续项。
- **547 复杂 MCU 实测未通过（2026-11-07）**：SmartMedicineBox 固件约束逻辑重绘形成
  30件/31网/5NC/8岛完整规格，全页0候选；N>=3重复shunt的共享网/座位/回流联合缺口与
  二件串联支路缺口未关闭。三轮窄修复均无交付并还原生产代码，547C2与真机547B未开。
  复现测试1 passed/1 strict xfailed；任务 `tasks/547_smart_medicine_box.md`，证据 `evidence/547/`。
- **547S 已通过、547D 暂停待续（2026-11-07）**：signal→非GND→GND 统一座位/关系尺/修复/lane，
  主代理87 passed/1 strict xfailed，独立变异通过；整页仍0候选。auto 规格对照消除左列死墙，
  但暴露 LED2/LCD_SDA 标签走廊冲突，未改生产；547E 串联与自动线真机串跑未开。
- **547G 辅助整页 G1–G3 完成、G4 部分完成，当前暂停（2026-11-07）**：自动与 agent-adjusted
  分账，辅助线复用现有 LayoutPlan/ChangePlan、lint、逐脚与渲染入口。30件/31网/5NC/8岛辅助页已过
  离线双层页面闸、独立逐脚/NC 与逐岛视觉；真机 profiles 18 份/122 条记录；test V4 / P41 apply
  30件/95线/57旗、write.calls=242 未 force，位号由实时池分配；主代理 lint 0E/0W/13I（12 条旗标
  方向 INFO 保留，`sch.modify_primitive` 不支持 netflag），宿主网表 30/30+31/31+5/5+0短路。
  DRC 0 error/200 warn `passed=false`，**不得称通过**；持久化仅 `saved_unverified`。剩余：岳手动
  关闭重开 test V4 后只读比对、完整四线/卫生检查与最终复验；本批未跑四线。辅助成果不关闭 547D/E，
  不是自动整页、不可直接投板。547F 命名脚修复已验收（仅聚焦 197 passed/1 strict xfailed + 变异）
  但未提交。详见 `tasks/547_smart_medicine_box.md` §547G，证据 `evidence/547/g4/`。
- **548 自动绘制能力阶梯（2026-11-08；不绑定 0.6.1）**：**A 完整 N≥3 面板支路出口通过（限已测电路族；A-R 补齐灯/蜂鸣器）**（语义窄门 G1–G9，547A
  `--runxfail` 2 passed，4 负控 gate 开/关 74 passed / 2 skipped）；**B 已由岳全部按推荐并由
  B1–B3 落地（数据合同 / 跨文档校验 / 串联几何，见下方三条）**；**C 部分通过**（A/C/D 8/11 单岛变体过、B 0/3 长文本过拟合、
  E 0/2 组合未打通）；**C2 批次前提被证伪**（mcu 的 4 节点与岛数无关，生产代码零改动）；**C3 的
  ②③④ 已落**（成员名过 `_profile_pin_ruler` 解析成脚号、页 label 改画自有水平承载杆、④ strict
  xfail 钉覆盖洞；只改 `pagecompiler.py`；① 已裁禁标签旗入库、C7 三次未通过，一行未碰）；**C4 的 B1 落、B2/B3 未落**（只改
  `drawcompiler.py`，闸点名的 `texts × labels` 相撞才补墙重建 ≤4 轮、无碰撞 0 轮 ⇒ 零移动）；
  **R 只补测试与文档、无生产改动**：聚焦 85 passed / 2 skipped / 1 xfailed，两次独立变异（C3
  `preferred` 改错 → 1 failed/4 passed/1 xfailed、C4 `TEXT_LABEL_REPAIR_ROUNDS=0` → 3 failed/1 passed）
  恢复后哈希 `975e6b1c…`/`9c4e5264…`。索引与停止条件见 `tasks/548_drawing_capability_ladder.md`
  §5–§18（§17 为 548A-R/548B3-R 验收缺口复审，两项已关闭、第二轮全量 16 failed / 10130 passed、0 errors、added=[]、removed=[]；§18 为 548D1/D2/D2R——D2 两版均未通过、生产净零改动），证据 `evidence/548A/`、`548B/`、`548B1/`–`548B3/`、`548C/`、`548C2/`、`548C3/`、`548C4/`、`548R/`、`548C5/`–`548C7B/`。
- **548D3（2026-11-09，局部推进，未闭环）**：base MCU 的原 7 条 xfail 已真实通过后摘除；WiFi
  单岛通过机器、逐脚与主代理放大目检；连续旗引线、页/岛 `PWR-+3V3` 回退和局部文字修复保留，
  CH34 `allMatch=true`。强制 topology 仍 0 候选；整页需要 **1694.75×1009**，放不进 1170×825，
  MCU/整页视觉未签。未接消费者的 corridor binder 不算已交付能力。未调预算/排名或放大图幅，
  548E/547G 继续暂停，未做 git 写。当前交接与复验状态见 `evidence/548D/HANDOFF.md`。
  第二轮全量 **10261 passed / 25 skipped / 1 xfailed / 16 failed**，新增7条兼容回归已消除，
  余16条与既有名单一致，不称全绿；connector 576+typecheck、DSH 137/1+typecheck/build、
  Rust 111/4+fmt/clippy通过，三项独立变异均先红并cp/hash恢复。
- **548D3X（2026-11-10，通用页级 compact 小批通过；548D 未闭环）**：普通岛框最小净距仍 40，
  当前 MCU/WiFi 真实框仅靠 packing 放不进 1170×825。默认关闭的 compact 声明、有限二维 packer、
  端口定点回放、attach/mainPath 与旧网格回退已接生产；主代理聚焦 **215 passed / 1 skipped**。
  固定页compact与attach-bottom各6变体、0候选。panelGroups的数据、电气/切片与placement已推进：
  base/topology均真实2×2，默认near=300，host逃逸/spread预留/重绑与hard面积梯度均落地；
  主代理两项有效变异恢复，最终组合 **224 passed**。最小fixture随后 `dc.compile` **ok=True /
  hard=0**，但主代理亲看最新渲染：2×2成立、GND外框仍在，**9交叉31弯，视觉拒收**。
  per-pin无座、聚簇与seat回放不一致、簇内短接出现5簇3座，seat-first需要新合同，目标在本轮
  **blocked**。后续A新建seat-first合同，B接受 `agent-adjusted`，不得冒称automatic。
  真实整页与本轮全量四线未做，548E/547G继续暂停，未做git写。证据 `evidence/548D/page-layout/`。
- **548D3S7/B3（2026-11-10，生产候选已出、视觉未过）**：ServiceSeat与path-first生产已接，
  `dc.compile` ok=True / hard0，3V3六枚、GND五枚，LED2真实fallback；两项变异先红恢复、CH34 MATCH。
  主代理亲看 `service-seat/path-first-final.svg`：LED1长1220、全页4交叉，视觉拒收。下一批只处理LED
  信号走廊与标签/布局共同约束；真实MCU/整页未验收。提交前全量pytest
  **10628 passed / 25 skipped / 1 xfailed / 16 failed**（均既有），connector 608、DSH 137/1、
  Rust 111/4通过，不称全绿；548E/547G继续暂停，提交前未做git写。证据
  `evidence/548D/service-seat/` 与 `evidence/548D/HANDOFF.md`。
  547G 的暂停收口另算，辅助页不抵扣自动能力。**完整四线已执行**：pytest **10022 passed /
  25 skipped / 1 xfailed / 16 failed / 1 warning、0 errors**；16条均非548R新红（12条既有
  货架/分类漂移、2条既有115/116、2条Windows环境），connector 576+typecheck、DSH 137/1+
  typecheck/build、Rust 111/4+fmt/clippy均通过；仓库卫生exit 0，不称全绿。
- **548C5 B2 文字宽度节距（2026-11-08，未通过，生产已还原）**：统一加距与逐件外推均使
  MCU 单列分支超过二维 `near_limit=300`，不是所有布局无解。主代理聚焦 **87 passed /
  2 skipped / 2 xfailed**；connector/DSH/Rust 通过；完整 pytest **10024 passed / 25 skipped /
  2 xfailed / 16 failed / 1 warning、0 errors**，失败节点与 548R 相同、无本批新增。
  注入二维座位的探针经主代理复核为两个候选、hard=0、26 网连通、0 短路，非自动生成能力。
  下一步实现同岛二维座位的闭式生成规则，不默认折行、拆岛或放宽 near。证据 `evidence/548C5/`。
- **548C6 同岛二维支路座位（2026-11-08，离线三关已过；548C6R已收口）**：B2 由生产救援轮自动
  生成 1 候选 `814ed66f…`、hard=0、26网各一节点、0短路、全文完整；C5 strict xfail 已摘为
  3 passed，C6 为12 passed。主代理聚焦 **120 passed / 2 skipped / 1 xfailed**（四负控74/2）、
  CH34 pinned不变，两项变异均先红并cp字节恢复，最终生产渲染逐区目检通过。548B 合同已由 B1–B3
  落地（见下方三条）；B3/548C2① 已由岳 2026-11-08 裁定禁网络标签、允许库内旗标（C7/C7A/C7B
  三次未通过、另批）。多岛与 548D 自动整页、548E 真机前提仍未具备；547G 继续暂停。证据 `evidence/548C6/`。
- **548C6R 绕针后 leg+tail 最终复核（2026-11-08，已通过）**：tail 远端跨网针重合经主代理
  复现后，生产用同一 `_foreign_pins_on_run` 尺在 dodge 后复核两段，残留即整组回退。C6 **13 passed**，
  主代理聚焦 **121 passed / 2 skipped / 1 xfailed**；B2几何/渲染、leg对照、CH34 pinned不变，
  最终复核变异先红并cp恢复。最终全量 **10038 passed / 25 skipped / 1 xfailed / 16 failed /
  1 warning、0 errors**，与548R及第一轮均无新增红；connector/DSH/Rust通过，不称全绿。
  后续仍只剩 B3/548C2① 的落地（岳已裁禁网络标签、旗标入库，C7/C7A/C7B 三次未通过、另批）
  与未具备前提的多岛/548D/E。证据 `evidence/548C6R/`。
- **548C7/C7A/C7B（2026-11-08，未通过，生产零改动）**：岳裁定禁网络标签、旗标可入库；
  三次路径均未出候选，主代理负证据7 passed。后续聚簇与预留/布线契约另批，C3 xfail未摘。
- **548B1 seriesBranches 数据合同（2026-11-08，通过；完整四线已跑）**：岳全部按推荐；
  新测试41 passed、主代理聚焦369/2、旧摘要与CH34 pinned不变、两项变异恢复。完整 pytest
  **10086 passed / 25 skipped / 1 xfailed / 16 failed / 1 warning、0 errors**，16条均既有
  （12条货架/分类漂移、2条115/116、2条Windows环境）；connector 576+typecheck、DSH 137/1+
  typecheck/build、Rust 111/4+fmt/clippy，不称全绿。证据 `evidence/548B1/`。
- **548B2 跨文档校验与页面切片（2026-11-08，通过；本批不做几何；完整四线已跑）**：V1–V8与
  两个消费者前红24/2转26 passed，主代理聚焦423/2，V6与切片变异恢复；CH34 pinned不变。
  完整 pytest **10112 passed / 25 skipped / 1 xfailed / 16 failed / 1 warning、0 errors**
  （同16条既有），connector/DSH/Rust通过。几何属548B3，不称548B完成。证据 `evidence/548B2/`。
- **548B3 串联几何与独立语法检查（2026-11-08，正例 + 不可落座负例通过，禁止静默回退已落地；完整四线已跑）**：每条声明注入
  两件 `RelativeConstraint`，`compile` 与 `check_grammar` 共用 `_with_series_arms`；座位按文档既有
  axis/progress 与真实引脚，几何 宿主→parts[0]→middleNet→parts[1]→终端，pitch 取原布局
  中心距，非GND终端旗挂臂尾真实脚；未声明/[]不变、不自动识别。生产只改 `drawcompiler.py`
  （最终 `d9ba64ab…`），前红10/4→14 passed，主代理聚焦232 passed/2 skipped；高边`9917b0b3cda9…`、
  低边`5eea1a442ce7…`各3候选、六点单调、middle一段10单位，CH34 pinned MATCH。**三项变异均完成：
  第三项先暴露⑤b覆盖洞、测试加强后才复红**；恢复点当时为`2cc92fc0…`，其后520b2兼容修复
  （`getattr` 默认空元组）得到最终hash。第一轮全量 **18 failed / 10124 passed / 25 skipped /
  1 xfailed**，既有16条外2条新红为520b2两条（SimpleNamespace 无 `series_branches` →
  AttributeError），修后 520b2+B3 **21 passed**，测试未改。主代理亲看渲染两件竖直直链、R在
  LED前、中点短、终端旗在臂尾。不跑真机、不落画布、不称 lint 宿主 DRC 或自动整页；
  第二轮最终 **16 failed / 10126 passed / 25 skipped / 1 xfailed、0 errors**（`full-pytest-final.log`，
  与548B2基线比较 added=[]、removed=[]，16条均既有，不称全绿）。证据 `evidence/548B3/`。
- **审查线测试反馈（2026-11-04）**：544P 堵住 DSH `commandLine` 凭据泄露；
  544 修 checkup/arch 写盘异常，545 加同目录 OS 互斥与串行 rerun 提示。主代理邻域
  **226 passed**；connector **576 passed** + typecheck；DSH **129 passed / 1 skipped** +
  typecheck/build；Rust **111 passed / 4 ignored** + fmt/clippy；文档/同步哨兵 **57 passed**。
  全量两轮均 **9301 passed**：首轮 25 skipped / 1 个 MSYS `0xC0000022`，次轮 23 skipped /
  3 个过滤 `sh` 后的钩链环境失败。**没有业务回归红，但也不记为全量全绿**；按纪律不跑第三轮。
  在线 C 组 9 条与真实 500+ 器件样本仍未覆盖。任务书 `tasks/544_checkup_output_errors.md`、
  `tasks/545_checkup_output_lock.md`。

## 038Q 原生 CBB（独立方向，2026-11-03 起）

- **11-03：调研/任务书完成**（`tasks/038q_cbb_native.md`）。状态是**样本驱动**——
  没有真实 CBB 样本就不开阶段 A，**未承诺版本、未承诺发布日期**。
- 与 038P（多 PCB 工作树）、FOOTPRINT、Rust 迁移**不混批**；shared / connector / 规则 /
  真机各自单独成批，先读后写。CBB 目前在仓库里没有原生实现，`core/blocks.py` 的
  `BlockSymbol` 是绘图模板域，不是宿主原生块。
- type 17 是线索不是事实：样本证实前只许写「待证实」；证实/证伪都按实测改口径。

## 待岳拍板（不排期就不动）

### 2026-10-19 已裁（四条，落地见 `tasks/528_060_gate.md`）

- **R4 → C**：先做 `update-connector --no-reload`（528A），stub 冻结到 0.6.x 之后。
- **191D → 数值不动**：`200 / 300 / 800 / 200` mil 保持；改立 `529` 分类空白带（2.2µF/4.7µF 落 unknown）。
- **绘图线磨清楚了才能发 0.6.0**：判据取 roadmap §4 的锚 + §8 三条区域级裁定（不新造判据）。
- **527D3 + 527D2 在 0.6.0 前完成**：从 0.6.x 规划升为 0.6.0 阻塞项。

### 2026-11-08 已裁并落账

- **548B 全部按推荐**：`seriesBranches` 数据合同已由548B1落地，41条新测试通过；548B2 跨文档
  校验（不做几何）与 548B3 正例 + 不可落座负例通过，「禁止静默回退」已落地；
  548D 仍不得用 LED 直连或 agent 坐标冒充完整串联，自动整页需另行复验。
- **548C2① / B3 禁止网络标签、允许库内旗标**：C7/C7A/C7B三次路径均未出候选，
  生产零改动；剩余是聚簇与预留/布线契约，另派小批，不得恢复标签或放宽网表闸。

### 仍待裁

- 121 反激规划落图（10-06 暂停；绘图线 201E/进针/文字行之后才轮得到）
- R4 `stub` 是否复活（冻结到 0.6.x 之后再看；前置是**去工作电脑 `About…` 读一次宿主版本**——
  若那是 3.2.149，懒求值会让 stub 同样不生效，真该做的是升级宿主）
### 已结案（2026-10-19，527E）

- **两份过时 DRAFT 标注归档**：051 早有「已被 052 取代」横幅；088b-deltas 三条偏差已由岳 10-02 逐条裁定并随 followups 落账，本轮加归档横幅，只留作裁决原文。
- **189A1 不改**：`read_stackup.used_copper_layer_ids` 维持「文档声明口径」。改读 `effective_layer_ids` 会把通孔盘的内层带进 used 集，与 `test_125_pcb_measure.py::test_foc_main_board_used_layers` 的实读 `[1,2,16]`（岳 2026-10-07 亲裁值）冲突；裁决注释已在 `core/measure.py:321`。

## 540 平台准备与后续双主线（2026-10-31 复核）

| 工作 | 当前状态 | 证据 / 锁 |
|---|---|---|
| 540A/B 工作区与解耦 | 已落；142 模块/0 legacy、24 CLI 命令、DSH 10 工具；三入口与集成锁已建立 | `evidence/540/b-behavior-equivalence.md`；shared/CLI/bridge 改动走集成锁 |
| 540C Rust 平台 | 已落；最小 workspace、合同、fmt/clippy、显式语料与 5 case 双侧差分均已运行 | `evidence/540/c-acceptance.md`；不批量翻译、不全局安装 |
| 540 最终候选验收 | Python **8132 passed / 94 skipped / 5 xfailed / 0 failed**；其他门禁读数见证据 | **`evidence/540/candidate-regression.md`**；这是 540 历史候选读数，不替代 0.6.0 最终全量 |
| 540 真机追加验收 | 历史结论为 `conclusion=incomplete / delivery=partial`（0 器件 0 网络），不是板级通过 | `evidence/540/real-machine-instance-20261025-233933/25-final-report.md`；0.6.0 真机另验 |

- 审查线派单：`tasks/review-line.md`；绘制线派单：`tasks/draw-line.md`；shared 集成锁：
  `tasks/shared-platform.md`。两线可独立派小批，shared/全量/真机串行，算法与迁移不同批。
- 0.6.x：绘制算法与 Rust strangler 并行；新工具/引擎默认 Rust，旧工具垂直迁移。
- 0.7.0：Rust 接管全部受支持主流程，不是逐行翻译全部 Python；connector/DSH 薄适配可留 TS。

## 200 审查线收口（2026-10-31 复核）

| 项 | 当前状态 | 证据 |
|---|---|---|
| 200A 报告整合 | **已落 `d2130b7`** | `outputs/200a/report-integration-evidence.md` |
| 200B 高速 A1 | **已落 `d2130b7`** | `outputs/200b/evidence.md` |
| 200C 高速 A2/A3 | **已落 `d2130b7`** | `outputs/200c1/evidence.md`、`outputs/200c2/evidence.md` |

200 批历史集成读数 **8540 passed / 25 skipped / 2 failed** 与失败原文仍见
`outputs/200/acceptance.md`，不改写历史。当前 0.6.0 的最终全量、真机与发布件验收单独记录；
功能门槛已收口不等于发布件已经签发。
