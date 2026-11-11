# 交接记忆 —— 换 harness / 开新会话先读这份

> **这份文件是路由，不是规格。** 它只回答三件事：这是什么项目、三条线现在各在哪、
> 干活要去读哪份权威文件。细节一律不在这里复制；两处说法冲突时以它指的文件为准。
> 写它的场合：从 Kimi Code 迁到 DeepSeek Harness（dsh）这类**换 harness**、开新会话、
> 或换人接手。口径是岳定的那句：**机制不搬，只搬记忆**。最后核对：**2026-11-08**。

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

## 3. 三条线的当前状态（核对日期 2026-11-08）

### 3.0 0.6.x与派单路由（先看这里）

- **0.6.1 已正式发布（2026-11-10）**：main 推送 `47713c2`、`8ad625e`、`9ffeb3b`；release tag 与
  Release `targetCommitish` 均为 `9ffeb3b2850f8391f75700f1f3f37851a4ee4ac2`
  <https://github.com/XiangyuYue/boardwise/releases/tag/v0.6.1>，`prerelease=false` 且 latest。
  发布只带已提交内容，不带候选货架、临时测试计划、锁文件和探针产物。版本骨架见 `docs/roadmap.md`，
  发布结果与能力边界以本版 Release 为准。
- **549 首次配对显式授权：已随 0.6.1 正式版发布（tag `9ffeb3b`）；本地实现、离线验收及 4.1.93 真机/回滚验收完成；4.1.71 仍只有模拟证据**：`boardwise bridge pair <CODE>`
  用 CLI token 调 daemon-owned `pair.authorize`，daemon 内存单槽 5 分钟 grant（8 位公开编号、
  授权时记指纹、一次性消费、重启失效）；未认证的任何 Origin 都不能首配或换配，有效旧配对任意
  Origin 可重连；**错码不作废 grant**（红队 2026-11-10 推翻“10 次作废”，次数只进审计）；
  记录写盘同目录临时文件 + `os.replace`，写完才消费；Connector 编号 Web Crypto only、
  `pairCodeUsed===true` 才轮换。`pair.authorize` 是政策测试里的第四个 `design_write=False` 例外
  （`risk=write` 不变）。读数：主代理 Python 聚焦 **455 passed / 3 skipped**、Connector
  **608 passed** + typecheck、DSH **137 passed / 1 skipped** + typecheck/build、Rust
  **111 passed / 4 ignored**、CLI 合同一致。**全量一轮 10611 passed / 25 skipped / 1 xfailed /
  23 failed / 5 errors（27:15）——不是全绿**：两条 `test_537a_daemon_write_policy` 是 549 新动作
  未登记例外（已补，聚焦 126 passed 关闭），4 处 549 测试审计写根目录已改 `tmp_path`，其余为
  既有货架数据、绘制线在途与已知 MSYS 环境错误；未跑第二轮全量。红队两轮 7 条 + 3 条非阻断项
  已修，无已知阻断项。**真机（2026-11-10，EDA 4.1.93 `test V4`）**：独立 `BOARDWISE_HOME` 首次
  `bridge pair` 成功（审计 `authorizedBy=pair.authorize`，编号只留掩码）；`sys.probe`/`doc.list`
  通过；`checkup` 取到 **77 components / 225 nets**，exit 1 是工程自身 85 项 ERROR、
  `completion=incomplete`；隔离 daemon 重启后未再授权，旧 token 自动重连且 `doc.list` 成功
  （审计 `pair-authorize=1 / pairing=1 / re-pairing=0`）；随后回滚到原 0.6.0 bundle，最终
  Connector 0.6.0 / daemon 0.6.1 / 两窗口 connected、paired fingerprint 不变。证据
  `outputs/review/549_real/ACCEPTANCE.md` 与 `outputs/review/549_real/checkup/`。
  4.1.71 只有模拟 Origin 证据，朋友的真实候选跑通不是本实现的验收；
  部署时新版 daemon 与 Connector 必须同步（旧内嵌 Connector 的热更不算安全包）。**未做**：提交、
  推送、版本 bump、发布、生产升级、整板验收。
- **daemon / connector 版本纪律（岳 2026-11-06 定）**：只要求 major.minor 系列同步，补丁号独立；
  同系列混跑为 `compatible`，不是全功能相等，新动作仍按能力探测，缺失时明确 `UNKNOWN_ACTION`。
  0.6.1 daemon 可与 0.6.0 connector 做常规审查；`attributeMoves` 仍需要支持它的 connector。
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
- **审查线本批已随 `cdff88b` 提交**：038W PAD_NET 每脚判优、038X 默认货架绝对路径与
  缺失披露、527C2 跨视图几何分类与全部位号、529 mid 容值带、541 R1/R2/R4 strict；
  任务书 `tasks/038w_pad_net_journal.md`、`tasks/038x_shelf_resolution.md`、
  `tasks/527c2_cross_view_geometry.md`、`tasks/529_decap_mid_band.md`、
  `tasks/541_offline_runtime_gates.md`。最终全量 **9893 passed / 25 skipped / 14 failed /
  1 warning**（12 条工作树既有货架数据漂移 + 2 条既有 Windows 环境失败，不宣称全量全绿）；
  connector、DSH、Rust 均通过。541 R3 与公开接口 allowlist 仍未实施，不写成 R3/R4 全部完成。
- **038Q 的 Q1–Q4 支撑批已完成各自范围（2026-11-11）**：库只读 `lib.cbb.search/get`、
  上游候选归一化、符号文件只读通路与单符号 elibz2 profile；AMS1117 单符号身份/几何已核对。
  四模块仍 candidate/unverified/notForDrawCompile，其余器件身份未齐。原生 `block_symbol`
  样件、端口规则与个人库放置未做，type 17 仍待真实样本证实；库搜索成功不等于原生块兼容。
  `core/blocks.py` 的 `BlockSymbol` 是绘图模板域，不是宿主原生块。
- **独立派单**：审查读 `tasks/review-line.md`，绘制读 `tasks/draw-line.md`，shared/CLI/bridge/
  parser/model 的集成改动读 `tasks/shared-platform.md`。两线可独立派小批，shared、全量、真机串行；
  算法与迁移不同批。旧档案 worktree 不当可写工作区；新建/删除 worktree 仍逐次问岳。
- **行为与证据**：540B 见 `evidence/540/b-behavior-equivalence.md`，540C 见
  `evidence/540/c-acceptance.md`；构建见 `docs/rust-platform.md`。V4 在线证据见
  `outputs/review/v4-online-acceptance.md`，#89 见 `tasks/89a_regulator_same_net_distance.md`、
  `tasks/89b_fb_same_net_distance.md`。
- **下一段**：0.6.x 绘制算法与 Rust strangler 并行，V4 后续样本/多板 + 库组合和 041 跨板网络分批；
  R4 stub 仍冻结。版本骨架见 `docs/roadmap.md` §1–§2。
- **绘制下一批路由**：`tasks/548_drawing_capability_ladder.md`。A、C4-B1 与 **548C6/C6R 的 B2
  同岛二维支路座位**已落并通过离线三关：普通/加宽轮无候选后才启用单模块救援轮，真实文字与器件
  度量闭式分配 line 轴座位；绕针后再以同一 `_foreign_pins_on_run` 尺复核 leg+tail，残留外来针
  整组回退。B2 自动产出 1 候选 `814ed66f…`、hard=0、26 网各一节点、0 短路、全文完整；C5
  摘标 3 passed、C6 **13 passed**。主代理聚焦 **121 passed / 2 skipped / 1 xfailed**（四负控
  74/2）、CH34 pinned不变；关闭救援/绕针/最终复核三项变异均先红并 cp 字节恢复，最终生产渲染
  已逐区目检。最终完整 pytest **10038 passed / 25 skipped / 1 xfailed / 16 failed / 1 warning、
  0 errors**，与548R及修复前第一轮均无新增失败/错误；connector **576 passed + typecheck**、
  DSH **137 passed / 1 skipped + typecheck/build**、Rust **111 passed / 4 ignored + fmt/clippy**。
  仓库卫生与文档声明钉通过，不称全绿。
  下一批仍从 `tasks/draw-line.md` 进入。**548C7/C7A/C7B 库内旗标三次未通过、生产零改动**，
  剩余聚簇与预留/布线契约另派小批，C3 strict xfail未摘。**548B1/B2 已完成各自离线范围；548B3 正例 + 不可落座负例通过，「禁止静默回退」已落地（checker 六点检查未做，不宣称）；A-R/B3-R 第二轮全量 **16 failed / 10130 passed / 25 skipped / 1 xfailed、0 errors**（`evidence/548D/full-pytest-rs.log`，added=[]、removed=[]，不称全绿）**：B1 数据合同（41 passed、聚焦369/2、旧摘要与CH34 pinned
  不变、两项变异恢复）、B2 V1–V8 跨文档校验（前红24/2转26 passed、聚焦423/2、本批不做几何）、
  B3 串联几何与独立 checker 合同（`_with_series_arms` 让 `compile` 与 `check_grammar` 共见
  同一组两件关系；宿主→parts[0]→middleNet→parts[1]→终端，pitch 取原布局中心距，非GND终端
  旗优先挂臂尾真实脚；未声明/[]不变；前红10/4转14 passed，聚焦232 passed/2 skipped，三项
  变异均完成（第三项先暴露⑤b覆盖洞、测试加强后复红；恢复点`2cc92fc0…`，其后520b2兼容修复
  得到最终hash`d9ba64ab…`），渲染经主代理目检）。完整四线：B1 pytest **10086 passed / 25 skipped / 1 xfailed /
  16 failed / 1 warning、0 errors**，B2 **10112 passed / 25 skipped / 1 xfailed / 16 failed /
  1 warning、0 errors**，16 条均为既有（12条货架/分类漂移、2条115/116、2条Windows环境）；
  connector 576+typecheck、DSH 137/1+typecheck/build、Rust 111/4+fmt/clippy；B3 第一轮全量
  **18 failed / 10124 passed / 25 skipped / 1 xfailed**（= 既有16条 + 520b2 两条新红：
  SimpleNamespace 无 `series_branches` → AttributeError；`getattr` 最小兼容修后 520b2+B3
  21 passed，测试未改）；第二轮最终全量 **16 failed / 10126 passed / 25 skipped / 1 xfailed、
  0 errors**（`full-pytest-final.log`，与 548B2 基线比较 added=[]、removed=[]，16 条均既有，
  不称全绿）。下一步：548C7 聚簇/预留/
  布线缺口另批，**548D 暂停于跨轮串联预留（D2/D2R 两版均未通过、生产净零改动、未进入整页实施）**、
  548E 真机未做，不能把离线通过记成 548D/548E 完成；
  547G 保持暂停，其只读复核依原任务书单独收口，不借548成果关闭547D/E、自动整页或真机。

  **548D3 当前交接（2026-11-09）**：base MCU 的原 7 条 xfail 已真实通过后摘除；连续旗引线、
  相邻 power/GND 联合选档、页/岛 `PWR-+3V3` 回退及局部文字修复已保留，WiFi 单岛候选通过
  机器、逐脚和主代理放大目检，CH34 `allMatch=true`。但强制 topology 仍 0 候选，完整页面
  需要 **1694.75×1009**、放不进 1170×825，MCU/整页视觉未签，**548D 仍未闭环**。
  corridor binder/service_gaps 只有内部测试、未接生产消费者，不写成可用能力。局部让位轴、
  全局标签回放与删 ghost-lane 等实验均已还原，未调预算/排名或放大图幅。第二轮全量
  **10261 passed / 25 skipped / 1 xfailed / 16 failed**，新增7条兼容回归全部消除，余16条与既有
  名单一致，不称全绿；connector 576+typecheck、DSH 137/1+typecheck/build、Rust 111/4+fmt/clippy。
  最新生产哈希、全量复验状态和失败矩阵见 **`evidence/548D/HANDOFF.md`**；548E/547G 继续暂停，未做 git 写。

  **548D3X 通用小批（2026-11-10）**：岳选页级二维路线。参考辅助页普通岛框最小净距为 40；实测
  当前 MCU/WiFi 页端口后 frame 横放需 1373.5 宽、竖放需 844 高，故只换 packing 仍不能放进
  1170×825。新增默认关闭的 `pageArrangement=compact`、有限二维 packer 与页面 consumer，支持
  attach、端口方向定点回放、mainPath 实际布线及原网格回退；未写新键时旧 variant/digest 不变。
  主代理聚焦 **215 passed / 1 skipped**，有效变异均先红并 cp/hash 恢复；两个旧用例的覆盖洞已补。
  主代理随后固定页实测 compact 及 compact+attach bottom，各 **6 变体、0 候选**，只改附着方向
  仍不足，证据 `evidence/548D/page-layout/full-compact-baseline.md`。
  `panelGroups` 的数据、电气与页面切片校验已落：两脚两网、每支路唯一宿主脚、全组同一宿主件，
  主代理 **272 passed / 1 skipped**、两项变异恢复。topology 已真实产生2×2 panel plan，宿主逐候选
  重投影、panel件禁止单独move。base与topology `_Placement` 随后均真实通过2×2，默认near=300，
  host逃逸/spread预留/重绑与hard面积梯度均落地；主代理两项有效变异恢复。terminal向下预留、
  host channel、terminal seat与模板文字已分段回放；宿主相对route cache已落地，最小fixture
  `dc.compile` 已 **ok=True / hard=0**。但主代理亲看最新渲染：2×2成立、GND外框仍在，
  **9交叉31弯，视觉拒收**。per-pin无座、聚簇与seat回放不一致、簇内短接出现5簇3座；
  seat-first需要新合同，目标在本轮 **blocked**。后续A新建seat-first合同，B接受
  `agent-adjusted`，不得冒称automatic。真实整页与本轮全量四线未做，交接见
  `evidence/548D/HANDOFF.md`。

  **548D3S7/B3（2026-11-10）**：ServiceSeat与path-first生产已接，`dc.compile` ok=True / hard0，
  3V3六枚、GND五枚，LED2真实fallback；缺seat与跨seat变异先红恢复、CH34 MATCH。主代理亲看
  `service-seat/path-first-final.svg`：LED1长1220、全页4交叉，视觉拒收。真实MCU/整页未验收；
  提交前全量pytest **10628 passed / 25 skipped / 1 xfailed / 16 failed**（均既有），connector 608、
  DSH 137/1、Rust 111/4通过，不称全绿；548E/547G暂停。

  **548D3B4反证（2026-11-10）**：显式命名候选虽机器/逐脚通过，主代理放大后仍因裸名脱离自己的
  引脚而拒收。两版载体WIP均失败回滚，第三版只读证明冻结KEY通道下MCU侧name row/name box没有
  共同可读合法档；不再做第四轮标签调参，转panel/service联合走廊布局。生产仍为
  `drawcompiler=08c1d17e…`、`placement=e2eb191a…`，两轮聚焦各 **99 passed**，`src/tests`无改动。
  当前权威交接 `evidence/548D/HANDOFF.md`、`service-seat/visual-review.md` 与
  `service-seat/led-corridor-verdict.md`；未做git写。

  **548D3B7（2026-11-11，KEY/LED独立岛离线三关通过）**：岳明确KEY/LED可独立成岛，旧同岛走廊与
  13交叉局部多腿版本停止并回滚。现共同power coreless bank、return侧向驱动的纵向支路及全组旗桩联合
  选档已接生产；缺省GND/横排与CH34 pinned不变。三岛automatic page compile、页闸、逐脚通过，跨岛仅名字；
  主代理亲看LED/KEY独立岛PNG通过。生产 `drawcompiler=95b52424…`、`ic_periphery=7346edba…`、placement
  不变；主代理两项变异先红恢复。**MCU整页边界名拥挤，整页视觉不签，留与岳共同规划**；真实SmartMedicineBox、
  强制topology、548E未做，未做git写。最终证据 `evidence/548D/service-seat/semantic-islands-final.md`。

  **548D3C1（2026-11-11，MCU本地结构离线三关通过）**：岳明确右侧标签后置，先修C1/R1座位与绕旗。
  `serviceLayout.localSeats=true`（配 `pinGap=30`）启用本地服务支路，R1近端、C1在VBAT行外侧，BOOT0直连；3V3两枚、GND三枚
  本地旗，原外框消失。主代理亲看最终MCU/三岛SVG通过本地结构，KEY/LED不退化。新能力仅在serviceLayout
  且无panelGroups时开启，base/topology同源设置内部联合开关；旧panelGroups逐候选恢复，CH34 pinned不变。
  C1六文件 **126 passed**，两项变异先红后cp/hash恢复；第一轮全量158 failed/22 errors暴露误用旧
  serviceLayout，C2以默认False的localSeats子键恢复，旧失败族81 passed、本批六文件129 passed。
  生产 `drawcompiler=48c2c89d…`、`presentationspec=9f72836f…`、`placement=a8aa1d35…`。
  **岳复验绘制线全量2 failed**；本 agent混合工作区全量 **10702 passed / 25 skipped / 1 xfailed /
  16 failed / 1 warning**，含其他线未提交改动与既有环境项，不能全归绘制线，不称全绿；Connector 660+typecheck、DSH 137/1+build、Rust 150/4+fmt/clippy。右侧标签、真实整页、
  强制topology与548E仍未做；未做git写。证据 `evidence/548D/service-seat/mcu-local/final-c1.md`。另注意：topology request无placed姿态时
  C1仍读VDD，与base VBAT不同；联合开关同源不表示宿主座位/强制topology统一，该项后续另批。

  **547S 098 scene08基线修复（2026-11-11）**：岳指出绘制线全量仅115/116两条failed。旧提交可逐字节
  复现旧基线，HEAD与当前工作树一致，证明是547S统一支路网尺的合法拒因演进，场景不产图且localSeats
  零影响。保留pre_547s旧版后依法重钉114基线与116 hash，生产未改。主代理相关四文件 **93 passed**，
  变异先红并恢复。证据 `evidence/548D/scene08-baseline-repair.md`。最终全量
  **10775 passed / 26 skipped / 1 xfailed / 0 failed / 0 errors**，两条目标测试均消失，绘制线全绿
  （另有1条既有编码警告）。

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
- **543G/N/H 已随 `44901da` 提交（2026-11-06）**：P38 已关闭重开并 `saved_verified`；
  自动网名重编号只在 persistence 按成员分区调和，通用 compare 不变。第二拓扑 CH340
  页 **P39=`62e4828acc56a307`** 已三关：12器件/36计划导线/17旗、lint 0E/0W/0I、
  独立逐脚 **45/45+15/15NC=60/60**、宿主逐岛视觉通过；P38和Board2 P1不动。
  543G补齐信号支路非去耦、完整flow阅读列、branchOrder与振荡bay，规格无参考坐标。
  201G披露合同和515A两项真缺陷已核销；201C/201D裁决不复活。证据 `evidence/543g/`、
  `evidence/543n/`、`evidence/543h/`。P39持久化未重开验证。最终全量 **9962 passed /
  25 skipped / 14 failed**（12条其他agent货架漂移+2条既有Windows环境红，本批6条回归已修）；
  connector 576、dsh 129+1、Rust、draw smoke、CLI合同与仓库卫生均过。
- **547 复杂 MCU 自动整页实测未通过（2026-11-07，工作树）**：以只读 `E:\SmartMedicineBox` 固件证据形成
  30 件 / 31 网 / 5 NC / 8 岛的逻辑重绘规格；observed/assumed/optional 分账，HSI 与 `.ioc` HSE
  冲突未臆画晶振。全页 **0 候选**，只有 7/8 单岛机器通过；自动线 WiFi 单岛主代理视觉仍不通过
  （辅助线 G2 已过三关，见下条，不互记）。
  G1 是 N>=3 重复 shunt 的共享网、座位与回流联合缺口，G2 是 GPIO→R→LED 二件串联支路未表达。
  三轮窄修复均未形成可验证交付，`drawcompiler.py` 已按 sha256 恢复；547C2/真机 547B 未开。
  复现 `tests/test_547_repeated_shunts.py` 为 **1 passed / 1 strict xfailed**，修通 XPASS 必须摘标。
  任务与停止边界 `tasks/547_smart_medicine_box.md`，证据 `evidence/547/`；该阶段未写原工程或
  真机页，辅助线的后续 live 验收见下条。
- **547S 已通过，547D 暂停待续（2026-11-07，工作树）**：`placement.shared_net_order` 以
  signal→非GND→GND 统一支路座位、搜索/终审关系尺、修复和 lane；VCC+GND 不再落 GND，四键已锚各自 KEY。
  主代理 **87 passed / 1 strict xfailed**，独立变异先红后 cp+sha256 还原。整页仍 0 候选；
  547D 已确认 straight→auto 消除左列死墙，但右列成为 LED2 走线穿 LCD_SDA 标签，尚无生产修复。
  547E 串联支路与自动线真机串跑未开（辅助线 live 见下条，不互记）。证据 `evidence/547/s/`、
  `evidence/547/d/`，生产基线见任务书。
- **547G 辅助整页（2026-11-07，工作树，当前暂停）**：自动线保留 547D/E 整页缺口（547F 命名脚修复单记）；辅助线
  `agent-adjusted` 复用现有 LayoutPlan/ChangePlan、lint、逐脚与渲染入口，未另造几何引擎。
  G1 接口盘点、G2 WiFi 单岛三关、G3 30件/31网/5NC/8岛离线双层页面闸+独立逐脚/NC+主代理逐岛视觉
  均完成；真机 profiles 18 份 / 122 条引脚记录。test V4 / P41（uuid=`037f5a63d7825dfe`，
  sheet=`93e5fa80765af875`）apply 走实时位号池，30件/95线/57旗、write.calls=242、未 force，
  位号非一一对应（U1→U5、R1→R6、D1→D2）。主代理 lint 0E/0W/13I（12 条 90°/270° 旗标方向
  INFO + 1 无结点交叉；`sch.modify_primitive` 不支持 netflag，未伪造姿态），独立宿主网表
  30/30件、31/31网、5/5NC、0 短路；DRC 已跑但 **不能称通过**（0 error/200 warn，`passed=false`）。
  全页与局部渲染主代理已亲看。持久化仅 `saved_unverified`（未关闭重开；多窗口返回
  `WINDOW_UNSPECIFIED`）。G4 仅部分完成；**待岳手动关闭重开 test V4 后只读比对 + 完整四线/卫生
  检查/最终复验**，本批未跑四线。547F 命名脚修复仅聚焦 197 passed/1 strict xfailed，未提交。
  辅助页是固件约束重绘（observed/assumed/optional 分账），不是自动整页、不是参考临摹，不可直接投板。
  详见 `tasks/547_smart_medicine_box.md` §547G，证据 `evidence/547/g4/`。
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
