# 交接记忆 —— 换 harness / 开新会话先读这份

> **这份文件是路由，不是规格。** 它只回答三件事：这是什么项目、三条线现在各在哪、
> 干活要去读哪份权威文件。细节一律不在这里复制；两处说法冲突时以它指的文件为准。
> 写它的场合：从 Kimi Code 迁到 DeepSeek Harness（dsh）这类**换 harness**、开新会话、
> 或换人接手。口径是岳定的那句：**机制不搬，只搬记忆**。最后核对：**2026-11-06**。

## 1. 一句话

boardwise 是**立创 EDA Pro（EasyEDA Pro）的 AI harness**，五条能力：① 离线审查
（20 条自有规则 + 主机 ERC/DRC + 数据手册闸）② 把审查发现画回编辑器画布 ③ 从一条 finding
生成并执行局部修改 ④ 经本机 bridge 读写**活着的**编辑器 ⑤ 原理图自动绘制（画法编译器
`draw compile → plan → apply → lint`）。

仓库 `E:\boardwise`（GitHub `xianyuyijinban/boardwise`，分支 `main`）。跑 Python 一律用
**仓库自己的解释器** `.venv/Scripts/python.exe`。桥 daemon 默认 `127.0.0.1:61190`，
不在时任何需要桥的命令会自己 detached 拉起（日志 `~/.boardwise/log/`）。

## 2. 先读哪几份（入口路由）

| 什么时候 | 读哪份 |
|---|---|
| 动手之前（任何一次） | [`AGENTS.md`](../AGENTS.md)——红线 + 项目地图；**dsh 原生自动读它** |
| 审查 SOP（何时加载 / 闭环 / R1–R3 / 坑表 / 命令面） | `SKILL.md` 的**两份同步副本**：`.kimi-code/skills/boardwise/SKILL.md`（kimi 的约定路径）与 `.agents/skills/boardwise/SKILL.md`（dsh 等通用入口）；两份**逐字节相同**，同步由 `tests/test_doc_claims.py` 盯着 |
| 现在在哪 / 版本骨架 / 方向 | [`docs/roadmap.md`](roadmap.md)（**稳定层**） |
| 做什么、不做什么 | [`docs/product-boundary.md`](product-boundary.md) |
| **V3 / V4 边界（唯一口径）** | [`docs/v3-v4-boundary.md`](v3-v4-boundary.md)——哪些共用、哪些只在适配层、V4 明确不承诺什么 |
| 任务全图（编号 / 状态 / 证据） | [`tasks/TASKMAP.md`](../tasks/TASKMAP.md) |
| 下一版排期 | [`tasks/SCHEDULE.md`](../tasks/SCHEDULE.md) |
| 查历史细节 | `PROGRESS.md`——**不要从头读**（1000+ 行流水账），只在需要时 grep |

深水区各自的权威件：审查操作细节 [`docs/review-sop.md`](review-sop.md)｜画法
[`docs/draw.md`](draw.md)｜桥协议全表 [`docs/bridge.md`](bridge.md)｜真机坑全表
[`docs/pits.md`](pits.md)｜V3/V4 边界 [`docs/v3-v4-boundary.md`](v3-v4-boundary.md)｜
测试与保密闸地图 [`docs/testing-doctrine.md`](testing-doctrine.md)。

## 3. 三条线的当前状态（核对日期 2026-11-06）

### 3.0 0.6.0与派单路由（先看这里）

- **0.6.0 功能门槛已收口**：200A/B/C 已随 `d2130b7` 入库；542 P0 反激三关、岳人眼和重开
  `saved_verified` 全过；527D2/D3 已落。CH343 示例随 `a8613c5` 入库。
- **540 已完成**：A/B/C + 对抗修复 + 只读真机验收；142 模块/0 legacy、24 CLI 命令、DSH 10 工具。
  最终候选读数见 `evidence/540/candidate-regression.md`（Python **8132/94/5/0 failed**），
  不再等待该文件；它是 540 的历史读数，0.6.0 发布验收另记。
- **V4 / #89 已进入候选**：`e431e94`、`ba4fbae`、`1a7e4a1`、`643cf6d` 覆盖 V4 单 PCB、
  主机 ERC、同网测量与证据边界。归档**多 PCB 逐板**已随 `a4fc387` 提交（038M/N/P/T 同批）；
  真实多板 + 库工程、部分跨视图语义和实时 PCB 位图缺口仍公开；
  `incomplete/partial` 不解释为板级通过。
- **038G–038L 已随 `d542f14` 收口**：Short-Symbol 不再造假网；分歧库副本有第四类覆盖计数，
  纯重编号不误报；旋转 R 矩形按 `(x,y)` pivot 读取（54 父区域/1843 点全过，PGND 30→12）；
  Rust SYMBOL 与 Python 9-case 差分一致，重复脚号逐字段合并。真机 `test` doctor 9/9、
  evidence 与焦点恢复正常，`conflicting_library_documents=0`；在线没有这些专项实例，不冒充覆盖。
- **038M 已随 `a4fc387` 提交**：Rust DEVICE 库垂直迁移——`device-library-sample` 成为
  第 8 个 kind，case book 9→11（新增 `device-library-v3-meta`、`device-library-v4-copies`），
  Python/Rust 投影一致、旧 9 case 不变。输入只有 `text`（无 `pinKey`），输出
  `boardwise.device-library/1`，合并语义对齐 `_collect_device_meta`（首 `META`、重复 uuid
  first-wins、模型可见差异才计冲突）。
- **038N 已随 `a4fc387` 提交**：Rust FOOTPRINT 库垂直迁移——`footprint-library-sample`
  成为第 9 个 kind，case book 11→13（新增 `footprint-library-v3-title`、
  `footprint-library-v4-copies`），Python/Rust 投影一致、旧 11 input 不变。输入只有 `text`，
  输出 `boardwise.footprint-library/1`，形状只有 `schema` + `footprints`（uuid→title），
  **没有** `stats`、也没有冲突计数：首个 `META` 生效、重复 uuid first-wins（空标题同样占位），
  字面 `"null"` 标题原样保留（DEVICE 属性值的排除规则不适用于这里）。
- **038P 已随 `a4fc387` 提交**：eprj3 **多 PCB 逐板审查**——同一 `source`/`runner` 逐板
  出 `boards`（title/boardUuid/components/checksRun/findings，索引不串板），`checkup --file`
  逐板落地；`_load_model(view="pcb")` 对多板**列出板名后拒绝**并指向 `checkup`（一模型一板），
  单板历史形状不变。实测 `test V4` 两个**空 PCB**：在线/离线 `boards`、32 checks、
  40 findings 一致；空板读 0 器件是读数不是缺板。**未覆盖**：真实多板 + 库工程（只有合成证据）。
- **联合挖洞修复（038P1，已随 `a4fc387` 提交；四类）**：多板合流那道缝挖出的四类问题一次修掉——
  ① **Rust DEVICE 属性浮点溢出**与 Python 对齐成 `inf`/`-inf`（`json.dumps` 的
  `NaN`/`Infinity` 拼写保留，有限值读数不变）；② 板文档 **`DOCHEAD` 无 uuid** 时按文件
  stem 命名，不再出无名板（板名改按 PCB 文档顺序逐位消费，不再用 uuid 查表）；③ **重复 PCB
  文档 uuid 明确拒绝**——同一块板导出两次不合流、不审两遍、不静默去重；④ `FOOTPRINT` /
  `DEVICE` / `SYMBOL` 同 uuid 只有**签名（记录顺序/id/body，剔 `DOCHEAD` 簿记字段）相同**
  才允许合流，**分歧即拒绝**，不拿另一块板的库几何去审。证据：
  `tests/test_038p1_eprj3_multi_guards.py` 与 Rust 侧 `device_library` 差分；本地探针在
  `.tmp_joint_audit/`（ignored，未提交，不是已提交产物）。单文件工程与旧差分 case 读数不变；
  真实多板 + 库工程仍未实测，分歧/重复守卫是**合成证据**。
- **038T 已随 `a4fc387` 提交**：`footprint-declared-sample` 成为第 10 个 kind，case book
  13→15（新增 `footprint-declared-v3-hit`、`footprint-declared-v4-empty`），Python/Rust
  15/15 一致、旧 13 input 不变。输入 `{schema,name,text,value}`——`text` 是一份 `.epru`
  记录流，`value` 是器件 `Footprint` 字段原文；输出
  `{schema:"boardwise.footprint-declared/1",footprint,libraryId}`：`value` 先 trim，只有
  命中且该标题非空才返回标题 + 原始库 id，空标题/未命中都保留 raw text、`libraryId` 为空；
  普通名称 trim 后不解析。
- **038U / 038V 已提交**：记录一致性与文档 tombstone 随 `d0275ae`，焊盘形状间距修正随
  `683a526`；两者的共同缺口（真实多板 + 库、原始 PCB-A、真机）仍在，不因提交消失。
- **2026-11-04 测试反馈**：544P 已堵住 DSH `commandLine` 正常返回与
  spawn 异常的凭据形状泄露；544 已把 checkup/arch 写盘失败统一为局部 exit 2 人话；545 已为
  同一 `--out` 加 OS 互斥（锁失败关闭）与串行 `rerun:` 提示。专项 8+13 条、主代理邻域
  213/226 passed；DSH 129 passed / 1 skipped。任务书 `tasks/544_checkup_output_errors.md`、
  `tasks/545_checkup_output_lock.md`，证据 `.tmp_544/`、`.tmp_545/`。
- **审查线下一步（真实外部依赖，逐项不合并）**：eprj3 在线容器、真实 NO_CONNECT、`down` 与
  envelope marker（信封字段缺省形态）、缺省 `yAxisDirection`、旋转几何样本需明确的 4.1.94+
  测试环境；真实多板 + 库工程 / CBB 样本 / 原始 PCB-A 复核 / 真机复测各自单独排期，缺样本
  不开工；541 R3 的 DSH profile 重启授权未拿到，pre-execute 闸不算已加载；R6 资料获取、Rust
  迁移、绘制线各自独立，不并进审查线。041 S1/S2 均已完成离线验收（S2 入口
  `tasks/041s2_interconnect.md`，已随 `6253a0b` 提交），真实 3 板与 2 板声明均已双报告对拍；
  全量 9682 passed / 25 skipped / 2 个既有 Windows 环境失败，connector/DSH/Rust 通过。
  S3 宿主交叉验证与语义网表函数层继续暂缓，S4 正式规则必须先有真实板间证据，不自动接续。
- **工作树新完成（未提交）**：038W PAD_NET 每脚判优、038X 默认货架绝对路径与
  缺失披露、527C2 跨视图几何分类与全部位号、529 mid 容值带、541 R1/R2/R4 strict；
  任务书 `tasks/038w_pad_net_journal.md`、`tasks/038x_shelf_resolution.md`、
  `tasks/527c2_cross_view_geometry.md`、`tasks/529_decap_mid_band.md`、
  `tasks/541_offline_runtime_gates.md`。最终全量 **9893 passed / 25 skipped / 14 failed /
  1 warning**（12 条工作树既有货架数据漂移 + 2 条既有 Windows 环境失败，不宣称全量全绿）；
  connector、DSH、Rust 均通过。541 R3 与公开接口 allowlist 仍未实施，不写成 R3/R4 全部完成。
- **原生 CBB 已排为独立方向（038Q，11-03 调研/任务书完成）**：仓库当前**没有**原生 CBB
  实现；`core/blocks.py` 的 `BlockSymbol` 是绘图模板域，不是宿主原生块。type 17 只是线索，
  **待证实**，不得写成事实。**需真实 CBB 样本**才开阶段 A（离线只读），先读后写；
  与 038P / FOOTPRINT / Rust 迁移**不混批**，未承诺版本与发布日期。
- **独立派单**：审查读 `tasks/review-line.md`，绘制读 `tasks/draw-line.md`，shared/CLI/bridge/
  parser/model 的集成改动读 `tasks/shared-platform.md`。两线可独立派小批，shared、全量、真机串行；
  算法与迁移不同批。旧档案 worktree 不当可写工作区；新建/删除 worktree 仍逐次问岳。
- **行为与证据**：540B 见 `evidence/540/b-behavior-equivalence.md`，540C 见
  `evidence/540/c-acceptance.md`；构建见 `docs/rust-platform.md`。V4 在线证据见
  `outputs/review/v4-online-acceptance.md`，#89 见 `tasks/89a_regulator_same_net_distance.md`、
  `tasks/89b_fb_same_net_distance.md`。
- **下一段**：0.6.x 绘制算法与 Rust strangler 并行，V4 后续样本/多板 + 库组合和 041 跨板网络分批；
  R4 stub 仍冻结。版本骨架见 `docs/roadmap.md` §1–§2。

> 以下 3.1–3.4 保留 2026-10-23/24 的业务与发布历史；当前派单和平台状态以 §3.0 为准。

> **2026-10-23 已合并提交到 `17893f4`（version 0.5.20）**：绘图线 worktree 已并回 main
> （merge `534d21f`），审查线 #83–#86、插件线 shim、记忆交接均已 commit。工作树另有一笔
> **未 commit 的 535 跟进修复**（143 F1 分支序，见 §3.2 末）。一切 git 写操作仍逐次经岳批准。

### 3.1 审查线 —— 实板反馈的修复循环

GitHub issue **#83–#88 全部仍是 OPEN**。仓库纪律：**issue 不由我们关**——修复落地只
comment「待验证」+ 验证步骤，由提出人实测确认后自己关；代码完成 ≠ 问题解决。

| # | 一句话 | 状态 |
|---|---|---|
| 83 | `core/measure.py::_capsule_distance` 的铺铜包含性判据两个析取项都拿多边形比**自己的顶点** → 有铺铜的配对**恒判 `contained`**（间距静默丢行、岛数恒相连） | **修复已在工作树**：`src/boardwise/core/measure.py`；新回归 `tests/test_83_pour_containment.py`（手算几何） |
| 84 | `pcb-track-ampacity` 不建模铺铜/分支：铺铜担主电流、10 mil 细线只做取样时按最小线宽判过载（实板 4 条假 ERROR） | **修复已在工作树**：`measure.py` 新增 `conductor_copper`（分段分辨率 + 铺铜面积/跨度粗读），`ipc.py` 有承担铜（门槛 `max(3×最窄段, 所需宽度)`，屋规）时细线档降 **UNKNOWN(INFO)** 逐段点名；新回归 `tests/test_84_ampacity_branch.py`（11 条）；实板 A 6 ERROR→0/5 INFO |
| 85 | `pcb-voltage-spacing` 把**同一颗器件封装内**的焊盘对当间距违规（实板 10 条 WARN 里 4 条同颗） | **修复已在工作树**：`measure.py` 新增 `_Shape.component` / `ClearanceResult.within_one_footprint` / `net_clearance(ignore_within_component=…)`，消费侧 `src/boardwise/rules/pcb/ipc.py`（并排报间距、不当 WARN） |
| 86 | 去耦候选池：旧库实例 `Value` 为空时读不到容值（MPN/货架其实有）→ 身旁去耦被报成很远 | **修复已在工作树**：`rules/decap.py`（`value_source` + `recovered_capacitance`，原理图 `Value` 为空时按货架 MPN / C 号补值并标注来源），消费侧 `rules/pcb/distance.py` / `pcb/regulator.py`；新回归 `tests/test_86_legacy_value.py` |
| 87 | 审查顺手性五条：报告不带引擎版本 / `export.render` 对 PCB 超时 / `review-summary` 覆盖 / finding 无元素身份 / `sch.readback` 无 value | 未动 |
| 88 | **#83 的修复带出来的新问题**：铺铜多边形用 `PourShape.points`（弧当弦，见 135）参与间距/连通判定 → 假 0.0 短路 WARN 与假岛数 | 已开；作为 **5 条 `xfail(strict=True)`** 记档（`test_126c` ×2、`test_131f`、`test_133d`、`test_135`）；根因是弧当弦的视图，修法指向「弧展开的 rings 视图」 |

**下一步**：#87（顺手性五条，未动）→ 回收 #88（现在有 5 条 xfail 占位，修好会自己变红提醒摘掉）。

### 3.2 绘图线 —— 多岛原理图（**已并回 main**，worktree 仅作证据档案）

- **规格（当前有效）**：`docs/schematic-style-spec.md`——黄金板绘图规格 S-01…S-21，每条标
  `[硬]`（违反即判废）/`[统计]`/`[观察]`。算法困境与接口简报在
  [`docs/drawing-brief-v2.md`](drawing-brief-v2.md)（它已取代 `docs/drawing-algorithm-brief.md`）；
  画法宪法（R1–R12）在 [`docs/schematic-conventions.md`](schematic-conventions.md)。
- **520a2–533 已全部并回 main**（merge `534d21f`，绘图线分支 `drawing-530-533` =
  `73c5e1d`）。worktree `E:\boardwise-wt520` 保留为证据档案（`evidence/520*/53x*` 在那边，
  未入 git 是惯例），别再往里写东西。
- **合并暴露的三层回归（535 批修复，commit `2c71844`）**——worktree 没拷 `outputs/`，
  一批夹具测试在那边一直 skip，合并到主树才真跑（「全绿变假」）：
  ① `pin-text-press`（同器件符号内部艺术字自压，摆放不可分离）单模块路径按岛路径同条款
  容忍（`drawcompiler.single_module_gate_violations`，cap=3，tolerated 记 notes 不进
  hard_violations）；② 地网布线失败的降级改为**旗标+记账**（530A 铁律：地/电源不许网络
  标签），unrouted 分支重排顺带消除了 520E 记录被 clobber 的潜伏 bug；③ 埋脚逃逸
  （`_no_step_out` + `_elbow_route(crossings=)`：搜索一步迈不出时才许取被跨线拒的 L）。
  全量 **6942 passed / 0 failed / 19 skipped / 5 xfailed**。
- **工作树里还有一笔未 commit 的 535 跟进**：自审抓到自己把 gnd 降级排到了 143 F1 拒绝
  （库无旗标符号的多脚网不许落成标签）**前面**，已把 `flag_downgraded` 拒绝挪回 gnd 分支
  之前。**提交前先跑受影响的测试文件 + 全量**。
- **534B 实验页已撤回（岳验收 20/100）**：Board2 P2 `dc46ef64fc7385ec` 已删除，
  Board2 只保留岳的 P1 参考页。之后按岳的三轮反馈重做（`tasks/534b_v4_layout.md` 续二–续五）：
  - **053C `attach`**：`modules[].attach = {to, side, gap}`，把去耦模块贴在宿主岛的一侧
    （只影响摆放、不合并图形，两岛之间 0 根连接线）；
  - **053D `partTexts`**：按器件声明位号/型号放在哪一侧，把引脚道让给网络标签；
  - **053E `gndClustering.radius`**：地网焊盘按直径上限聚类，每簇一枚 GND 旗标、簇间不连线
    （usb_c 实测 GND 总长 940→565、最长段 205→85、旗标 1→4）；
  - **053F**：以上三条＋`labelPolicy.stubMin`/`rowModel` 全部改成**规格声明**，
    **不写＝旧行为逐字节不变**，现有 44 条被打破的测试因此回绿。
  - **最终落地**：Board1 **P29 `6625ff26bf59d14c`**；Board2 只有用户参考页
    P1 `30560d9c0a52a6d2`，未改。最终是**参考页模板重建 + 少量受控 ATTR 修正**，
    不是通用自动布局；`draw lint` 0E/0W/0I，清理失败实验页后全工程 DRC 通过，
    独立逐脚 **55/55 连接 + 3/3 NC = 58/58**。证据 `evidence/534ab/`、
    `evidence/534ac/`，任务账 `tasks/534b_v4_layout.md` 续十一/053AD；关闭重开持久化未验。
  - **543I–L 当前交付页为 P38（2026-11-05；543K/L 已随 `924a180` 提交）**：543I/J 完成可见连接、真实墨迹、
    支路走廊、格点与并联去耦双端共旗；543K/L 修正岳指出的成对姿态与桩长不一致。
    信号型成对二端支路横向且 shared pin 朝宿主，成对文字联合选同侧；电源去耦不一律
    旋转。两网 localLabelObligation 按几何配对，共同长度同时验两脚，伙伴回放同一决定。
    P38=`0ec4dc022ef38563`：R7/R8 横向且文字都在左，CC 各 130 水平直连；D± 为
    **40/40、60/60、40/40** 且可见贴名。C9/C10 共地、R7/R8 独立地旗、USB 去耦竖直与
    CH343 电容横向未回退。11 器件、49 计划导线、19 旗；lint **0E/0W/0I**，网表分区与
    导线几何均 **55/55 + 3/3 NC**，主代理逐岛目检通过。旧 P37 已删，Board2 仅 P1；
    DRC 仅 3 个规格 NC + 3 个库属性 WARN。该页后由 543N 完成关闭重开，升级为 `saved_verified`。
    543M 已补上联合等长的 `stub=straight` 门：auto/V45 恢复旧逐脚逻辑，straight 的
    P38 重编译与验收版逐字节相同；主代理 V45/auto/格点复跑 **35 passed**，独立
    删除门时 auto 负控制变红并已还原。最终 drawcompiler sha256=`0451d93a…`。
    证据 `evidence/543j/`、`evidence/543kl/`；543J 全量 **9390 passed / 25 skipped /
    2 既有环境红**，543K/L/M 最终全量 **9496 passed / 25 skipped / 2 既有环境红**；
    connector 576、dsh 129+1、Rust 111+4、draw smoke 与 doc-claims 39 均过。
- **543G/N/H 当前状态（2026-11-06，工作树）**：P38 已关闭重开并 `saved_verified`；
  自动网名重编号只在 persistence 按成员分区调和，通用 compare 不变。第二拓扑 CH340
  页 **P39=`62e4828acc56a307`** 已三关：12器件/36计划导线/17旗、lint 0E/0W/0I、
  独立逐脚 **45/45+15/15NC=60/60**、宿主逐岛视觉通过；P38和Board2 P1不动。
  543G补齐信号支路非去耦、完整flow阅读列、branchOrder与振荡bay，规格无参考坐标。
  201G披露合同和515A两项真缺陷已核销；201C/201D裁决不复活。证据 `evidence/543g/`、
  `evidence/543n/`、`evidence/543h/`。P39持久化未重开验证。最终全量 **9962 passed /
  25 skipped / 14 failed**（12条其他agent货架漂移+2条既有Windows环境红，本批6条回归已修）；
  connector 576、dsh 129+1、Rust、draw smoke、CLI合同与仓库卫生均过。
- **合并记录**：worktree `E:/boardwise-wt-layout` 分支 `534b-layout` 已合并 main
  （`b74ee91`）；本批（053C–053F）直接在 main 提交（`263929e`），全量
  **8980 passed / 23 skipped / 2 failed**（两条环境红：pytest-slots ACL、
  MSYS `0xC0000022`/POSIX installer）。

### 3.3 插件线 —— boardwise-dsh（发给 dsh 用户的产品面）

- **0.6.0**：根 shim 与 `dsh-plugin/package.json` 已统一为 0.6.0；`index.ts` 仅组装
  review/shared/draw 注册，旧 8 工具顺序不变，另有离线 `boardwise_draw_compile` /
  `boardwise_draw_lint` 共 10 工具。**127 passed / 1 skipped** + typecheck + build；新 tarball 为
  `boardwise-dsh-0.6.0.tgz`。下列 0.1.x 内容只作历史，不是当前版本。
- `dsh-plugin/package.json` 0.1.2 → **0.1.3**（commit `23b2a53`）：`npm run check` 全绿
  （51 passed / 1 skipped + typecheck + build），`npm pack` 出 `boardwise-dsh-0.1.3.tgz`，
  `npm publish --dry-run` exit 0。
- **headless store 分裂按新建 profile 处置**（2026-10-24）：从 headless 模板建
  `boardwise-clean`，装 `boardwise-dsh-0.1.3.tgz`，`--dump-config` 见 `tool-boardwise`；
  旧 `headless` 的 `node_modules` / store 未动。PATH 只接受 `boardwise.exe`，`.cmd/.bat`
  不再直接 spawn（Node 批处理 EINVAL），改用 `BOARDWISE_EXE` 指向 exe 或 Python。
- **web store 分裂**（2026-10-24）：现有 `web` profile 的 `node_modules/.modules.yaml`
  仍指向 `C:\Users\xiangyu\.dsh\profiles\web\...`，在原 profile 上 `add` 会报
  `ERR_PNPM_UNEXPECTED_VIRTUAL_STORE`；不改旧 profile，从 web 模板新建
  `boardwise-web-clean` 并装 0.1.3，`--dump-config` 见 `tool-boardwise`，旧 `web` 未动。
- 仓库根 `package.json` **shim 已随 23b2a53 入库**（`main`/`types` 指进 `dsh-plugin/lib/`）——
  DSH STORE 那条 `dsh plugin add github:xianyuyijinban/boardwise` 以 **push 后的 HEAD 树**
  为准，push 前商城安装仍装到空壳。
- **待做**：`npm login` → `cd dsh-plugin && npm publish --access public`（**岳的 npm 账号，
  未 publish**）；push 后等几小时复检商城页。
- **版本策略执行**：从 **0.6.0 起插件与 boardwise 外部版本同号**，根 shim
  `package.json` 与 `dsh-plugin/package.json` 已一起改成 0.6.0。`0.1.3` 是 `0.1.x`
  最后一版。`BOARDWISE_EXE` 持久化暂不做，保留环境变量方式；npm registry 发布仍按上面的
  待做处理，不因本地 `npm pack` 或 GitHub Release 自动视为已 publish。
- 纪律：**TS 侧不实现任何审查逻辑**；CLI 命令面变更时检查 dsh-plugin 工具面要不要跟，
  漂移哨兵 `tests/test_dsh_plugin_sync.py` 常跑。

### 3.4 迁移线（Kimi Code → dsh）

方案在**仓库外**：`C:\Users\xiangyu\.kbw-dsh-migration\migration-to-dsh.md`（782 行，调研稿，
**待岳审 §5 的 Q1–Q14**）。口径是「**机制不搬，只搬记忆**」：

- **dsh 原生的**（不用自建）：`AGENTS.md` 自动注入（含用户级 $DSH_HOME/AGENTS.md）、
  `subagent` / `subagent_fork` / `workflow` / `jobs` 的派单与并行、`session.v4.jsonl.zstd` +
  `headless --json` 事件流、`/compact` 与 `compaction-basic`。
- **本次搬的**：SOP 落点 → `.agents/skills/boardwise/SKILL.md`（+ 与 kimi 路径的同步测试）；
  `AGENTS.md` 权威指针 → 两份同步副本；这份 `docs/handoff.md`。
- **与 harness 正交、原样生效的**：保密闸（`.githooks/*` + `tools/check_repo_hygiene.py`）、
  进程闸（`tests/conftest.py` → `tests/_process_guards.py`）、`evidence/`+`outputs/` 惯例。
- **dsh 侧已知硬约束**（动手前先读方案，别现场发现）：Windows 上 dsh 的 agent **只有 pwsh 工具、
  没有 bash**（`tool-bash` 在 win32 被 base 关掉）；`dsh-schedule` 默认不装且 headless 装不上
  （要 Host Web 的 session controller）；`maxActiveSubagents` 默认 8，与仓库「整机全量槽 = 2」
  不联动，**要降到 2**；Kimi 那边第三方网关（opencode 等 provider）在 dsh 侧没有对应物。

## 4. 铁律索引（为什么、怎么做都在权威件里，这里只指路）

| 铁律 | 权威件 |
|---|---|
| 不动 git；**删除一律进回收站**（禁 `rm`/`rm -f`/`unlink` 直删，临时目录/变异备份也没有例外） | `AGENTS.md` §红线；SKILL.md §7（Windows 原生通道写法） |
| 真机写操作前：**R1 身份判定**（`doc.list` 焦点工程名与任务书**逐字一致** + 页特征全项命中）/ **R2 事故申报**（证据不足只许报「异常待裁」，假警报与误删同等对待）/ **R3 找不到 ≠ 已清** | SKILL.md §4；`tasks/012-basic-experience.md` |
| 只碰任务书**逐字点名**的测试工程；真实工程是禁地（`CH340G.eprj2` 等一律不许写） | SKILL.md §4 |
| 工程容器文件（`.epro2/.eprj2/.eprj3/.epru/.esch/.epcb`）**永不入库**，派生副本（`.bak`/`.orig`…）同罪 | SKILL.md §4 R4；`tools/check_repo_hygiene.py` |
| 公开产物里公司板只用 `PCB1/PCB2/PCB3` 匿名代号；产品名/应用场景/客户/关键型号零出现 | SKILL.md §4 R4b |
| **绘图交付红线**：100% 横平竖直、导线不穿器件框、交叉趋零、内容不进标题栏、交付前过 `draw lint` | `docs/schematic-style-spec.md`（S-01/S-08/S-10/S-11…）；SKILL.md §3 |
| 文档里 load-bearing 的声明必须**机器可验**，并在 `tests/test_doc_claims.py` 有钉（文案不许跑赢数据） | SKILL.md §7；`tests/test_doc_claims.py` 的模块 docstring |
| 发布闸三闸（挖洞 swarm / 上机 / 实测）缺一不发；正式版一周最多一发、何时发由岳定 | `docs/testing-doctrine.md` §发布闸；`docs/roadmap.md` §1 |
| 新增 bridge 动作三处同步（`protocol.py` 目录 + connector handler + `docs/bridge.md` §4） | SKILL.md §7 |

## 5. 怎么干活

**四线（全绿才交卷）**——

```bash
.venv/Scripts/python.exe -m pytest tests/ -q -n 4 --dist loadfile --basetemp=.tmp_pt_home
cd connector && npm test && npm run typecheck
cd dsh-plugin && npm run typecheck && npm test && npm run build
```

- `--basetemp` 一个字都不能省（Windows 上否则汇总行被吞、假 exit 1）；并行**只许**
  `-n 4 --dist loadfile`——`-n auto` 打满主机被岳叫停过，`--dist load` 会把同文件的测试对拆到
  不同 worker；多前场并行时各用各的 `.tmp_pt_<批名>`。

**在 dsh 里跑测试**（dsh 的 pwsh 工具给子进程套受限令牌：宿主本身不受限，同一条命令 pwsh
能过、它拉起的 python 就死——写工作区外一律 `WinError 5`，目录 ACL 是好的，拦在进程令牌）——

- **basetemp 只能落工作区**：python 的 `tempfile.gettempdir()` 被改写为工作区根，写工作区外
  （`%LOCALAPPDATA%`、`~/.boardwise`）一律 `WinError 5`；`C:\tmp_pt_*` 另有一道墙——C 盘根
  建目录要管理员权限，非沙箱的普通终端也一样。
- **`BOARDWISE_HOME=<工作区内路径>`** 可救进程闸的槽文件（默认落 `~/.boardwise`，在 dsh 下
  写不进去）：`$env:BOARDWISE_HOME = ".tmp_bwhome"`，再跑上面四线里的 pytest。
- **必红的清单（环境红，不是代码回归）**：`tests/test_193_secrecy_hooks.py` 3 条（git 钩子的
  `sh.exe` 在 python 子进程链里建 `\BaseNamedObjects\msys-2.0…` 被拒 `0xC0000022`；0.5.21 起
  这 3 条带探测、在此环境自动转 skip 而不是红）。**这台机器的 python 子进程受限是机器级的**
  （普通终端同样建不了 Temp 目录、起不了 sh，疑与 Codex 沙箱残留策略有关，待查），因此
  2026-10-23 起钩测试在本机任何环境都转 skip——钩链健康度以真实 commit/push 触发钩子的
  输出为旁证。更正：沙箱里 python **有**外网（`urlopen` 可通）；LCSC 的 SSL 超时是单站/瞬态，
  且 0.5.21 起 `test_520_parts_hunt` 的 fetch_detail 接缝已修、离线密封，不再依赖网络。
  **dsh 侧全量读数与终端等价**（2026-10-23 双边 `6936/0 failed/25/5` 逐字互证），
  发布验收的全量读数 dsh 侧自跑即可。
- `.tmp_review_line` 当前由全局 `core.autocrlf=true` 检出，三件 `tests/fixtures/drawapply/*.json`
  是 CRLF，而 differential manifest 固定 LF blob 的 SHA。**不要在该 worktree 直接重生成
  golden**；038i 采用隔离的 LF blob 树生成并复验，三条相关环境用例也在该树通过。

- **子代理纪律**：一个任务书只装一个缺口 / 一个文件域，串行小批，每批半小时内交卷
  （两小时黑箱 + 大上下文 = 幻觉与返工，060 实测被 timeout 斩）。整机全量并发槽只有 2
  （`tests/_process_guards.py` 在机器侧兜底，理由见 `AGENTS.md` §子代理纪律）；探针/脚本
  单进程；长命令带 timeout；交卷前收干净自己起的 daemon 与后台任务。
- **证据与目录惯例**：长期依据放 `evidence/<批号>/`（报告 + `probes/` + `raw/` + 产物 sha256），
  可重跑审查产物放 `outputs/review/<批号>/`，一次性探针放 `.tmp_<批号>/`，pytest 用独立
  `.tmp_pt_<批号>`。`evidence/`、`outputs/`、`.tmp_*` 默认 gitignore，既有跟踪文件不动；
  未跟踪/ignored 不等于可回收。实验与 worktree 边界见
  [`docs/workspace-conventions.md`](workspace-conventions.md)（540A）。
  变异验证 ≥2（**`cp` 备份 + `sha256`/`cmp` 还原，禁用 `git checkout --`**：它拉回 HEAD，
  会把未提交的改动整个冲掉）；append 落盘后立刻 `grep -c` 独立计数防双执行。

## 6. 还没定的（换会话/换 harness 时别自作主张）

- **v0.5.20（正式版，6.0.0 前最后一个正式版）发布在途**：修复与合并已提交到
  `17893f4`；发布闸②上机（在线≡文件对拍 56=56、draw lint、daemon 0.5.20）与③实测
  （exe 重打 `ffdec920…`、隔离端口冒烟、版本同号、全量 6942 绿）已过；闸①挖洞因子代理
  通道全死（opencode go 429 / step-5 400 / space-bunny 403 / commandcode 欠费）改主循环
  自审——自审抓到并修了一个洞（143 F1 分支序，未 commit）。**剩下的发布步骤**：535 跟进
  commit → 全量复跑 → exe 重打（代码变了必须重打）→ SCHEDULE.md 行 → tag v0.5.20 →
  push（git 走代理 `https_proxy=http://127.0.0.1:7890`）→ gh release。
- **地网旗标降级的电源类问题待岳裁**：`_label_fallback` 现在只对 gnd 类改旗标；power 类
  （如 HVDC/SEC_12V）仍按 520E 落网络标签——岳的 520E 与 530A 两条裁定在这里冲突，
  是他的电话，不是我们的默认值。
- **E: 盘三项待岳拍板**：`E:\boardwise-sources-backup-20261015`（21MB，与
  `blocklib/sources/` 逐字节冗余）；两个 mirror（`boardwise-mirror-backup-2026101{5,7}`，
  共 85MB，10-15 历史清洗前旧历史的**唯一**副本）；11 个注册旧实验 worktree
  （`.tmp_cpsat` 等，约 1.2GB）：经审计均有未提交或独有证据，**当前无安全回收项**，
  保留并逐批归档裁定，不按旧写法直接 `git worktree remove`。
- **迁移方案 §5 的 Q1–Q14 全部待岳裁**：主代理载体（Web / Desktop / headless）·
  `DSH_HOME` 要不要做一次性 pnpm 重链（store 分裂，裸 `dsh plugin` 必报
  `ERR_PNPM_UNEXPECTED_STORE`）· 子代理模型接不接第三方网关 · 500k 红线纪律怎么改写 ·
  cron 怎么接 · 阶段 2 做哪几个 layer。方案里的【推断】不是裁决。
- **版本**：`v0.5.19` 已发（内测，tag）；`v0.6.0` 冻到 10 月底，**四个阻塞项缺一不发**——
  122 E 阶段（200A/B/C）+ 高速 A 档 1~3、**绘图线过锚**、527D2/527D3（✅ 已落）。
  见 `tasks/528_060_gate.md`。
- `R4` stub 冻结到 0.6.x 之后；`201C` 与 `121` 搁置（`201C` 备份在 `.tmp_201c_hold/`）；
  `text_overlap` 代价项由 526 撤回（「只做一半的约束比不做更差」）；`v0.6.x` 起做 V4 适配。
