# 审查闭环 SOP（checkup / 架构走查 / 断连兜底）

> 自 `.kimi-code/skills/boardwise/SKILL.md` §3.1/§3.1b/§3.2 迁入（2026-10-06，SKILL 减重 124）。正文保持迁入时原样；SKILL §3 只留路由图。

### 3.0 开工第一句必须报连接状态（issue #69 条 2，死一步）

**动手之前，先把连接状态说给用户听**——这是一条死步骤，不是「有空就报」：

- **连上了**：一句话点名**哪个工程的哪个窗口**，照抄 `boardwise bridge status` 的结论行即可：
  「已连接 2 个窗口：毕设FOC驱动板、test2——下面审的是 `毕设FOC驱动板`（window-A）」。
- **没连上**：先说没连上，**再说怎么修**，然后才决定走哪条路。**两种「没连上」是两条
  不同的修法**（163b 拆开；照抄机器的话，别混着说）：
  - **`boardwise bridge status` 第一行回「未连接——daemon 在跑……差的是 connector」**
    （daemon 活着、没有窗口连着）：修法是导入扩展，与 daemon 无关——
    「未连接：daemon 在跑，差的是 connector → 立创 EDA 里导入并启用 boardwise 扩展，
    装过就**重启一次编辑器**。本次按断连兜底走（§3.2 的 `--file` 路径），审查能做完，
    但改图/出图/真实页回读做不了。」
  - **任何命令报 `daemon not reachable`**（157 起这条等于**自动拉起也没成功**，本身就是
    短暂状态）：修法是查日志或前台起，与扩展无关——
    「未连接：daemon 不在、自动拉起也没成功 → 看报错上面那几行日志尾部
    （`~/.boardwise/log/daemon-<日期>.log`），或前台跑 `boardwise bridge start` 看它
    怎么说。本次按断连兜底走（§3.2 的 `--file` 路径），审查能做完，但改图/出图/真实页
    回读做不了。」

不许出现的情况：干等 AI 返回、用户不知道连没连上；或者报了一句「连上了」却不说是哪个
工程/哪个窗口（多窗口时这等于没说，daemon 不猜是哪一个）。**连接状态与审查结论分两句说，
不许合并**——一句「已连接，正在审查」里那半个「正在」用户无法核对。

`boardwise doctor` 的「按这个顺序做」块给的就是这套修法（它按安装顺序归并了红项，
每步指向 `docs/getting-started.md` 对应步）；`boardwise bridge status` 的第一行给的是
结论行。**这两个是机器说的，不许你另编一套说法。**

### 3.0a 分阶段交付与可中断审查

**完成环境/身份确认与一次 checkup 之后，先交付首轮检查点，再深挖。** 首轮检查点必须是 `initial` 或
`partial` 状态的可交付结论，不是一句「还在查」——它至少包含五件事：

1. **连接与版本**：daemon / connector / 引擎版本，以及这次读的是哪个工程、哪个窗口；
2. **`report.conclusion`**：板级结论的唯一权威（`summary.conclusion` 只是句子），
   它说 `incomplete` 就不许说「基本通过」；
3. **ERROR 与宿主 DRC**：ERROR 条数、宿主 DRC 的读数（以及它是不是只回了按 kind 的合计）；
4. **待确认项**：`needs-manual` / `open-item` / 待人工复核的条目，一条一句；
5. **产物位置**：`--out` 目录、已经写下的报告与图，用户据此自己核。

**先把这份检查点交付出去**，用户的下一步（继续 / 停 / 换板 / 加手册）建立在它上面；
之后再有预算，才去深挖规则、逐页读图、追手册事实。**禁止**在环境/身份与那一次
checkup 都没完成时一上来就自由探索：先确认环境和身份，再跑 checkup，再交付。首轮检查点里的数字是读数，
不是四舍五入后的「差不多干净」。

#### 批次模板

每一次深挖都先写清四件事，缺一件就不开工：

- **finding**：这一批要找的具体问题（一条一句话，不写「看看有没有问题」）；
- **假设**：我为什么认为这里有（哪条规则、哪一页、哪颗器件）；
- **需要的证据**：打开哪个文件、调哪个动作、看哪张图才能确认或否证；
- **停止条件**：什么情况下本批到此为止（找到了 / 否证了 / 证据拿不到）。

上限：**每批最多 3 条 finding、约 15 分钟**；**约 30 分钟必交付**一次（时间从首轮
检查点之后累计深挖，不把首轮检查点本身算进去）——哪怕只交付「本批零 finding，
理由如下」。**每批结束先更新阶段报告**（把本批的 finding、否证、未覆盖写回报告与
对话），再决定是否继续：**另开一批**继续，或者**得到用户同意**再往下走。**不许**用「再查最后一个」把一轮拖成没有边界的长跑：用户随时可以
叫停，叫停时手上的产物就是交付物。

#### run 的冻结输入

一次 run 的输入是冻结的，开跑时记录并归档（归档 + SHA256）：

- 输入归档与 SHA256（`.epro2` / `.enet`，以及报告目录里被读过的原件）；
- 引擎版本（boardwise 版本 + 规则集/检查器的版本或哈希）；
- `intent`：本次 **DesignIntent 合同**的路径 + 内容 SHA256；合同缺失就显式记
  `missing`，不拿一句人写的问题描述替代，也不在本节另改 verdict；
- 活动页与证据通道：哪几页原理图、哪些通道（live / archive / 图像 / 手册）；
- 模型计数：器件数、网络数、缺手册数。

**输入或证据通道一变，就开新 run**，把新旧两份报告做**语义比较**（finding 增删、
覆盖变化），**不混 findings**——旧 run 报过、新 run 没报的，是「未复现」，不是「已修复」。
一次只换一个变量：不得同时换归档、活动页与测量路径，否则分不清差异归谁。

**同输入哈希 + 同引擎 + 同 intent + 没有新具体证据时，不重复计算。** 普通统计
（计数、按规则聚合、覆盖表）**复读**现有报告 / 结构化产物（`review-read` 的 JSON）/
缓存即可，复读不产生新的板级结论。要**重算**，先给出一条**新具体证据**：新导出、
新页面、新核实的手册事实，或用户指出的具体位置。同一基准的 DRC 稳定性复核
**最多 2 次**；第三次要先有新证据，否则就是在为同一个读数反复付钱。

只用**公开接口**：公开 CLI（`checkup` / `review-read` / `review` 子命令）与公开的
证据接口（报告字段、`review-read` 的结构化输出）。缺公开接口就记**工具缺口**，
不猜私有 API、不手解析内部文件格式。

#### 重复计算与证据变化怎么判定

| 场景 | 同基准？ | 新证据 | 动作 |
| --- | --- | --- | --- |
| 同基准、无新证据，重复 checkup 或 run_pcb_review | 是 | 无 | `reject-use-existing`：复读已有报告 / 结构化产物 / 缓存 |
| 第三次 DRC 稳定性复核（同一基准、无新证据） | 是 | 无 | `reject-needs-new-evidence`：先补一条新具体证据，再谈第三次 |
| 输入归档或证据通道变化 | 否 | 有（新输入） | `new-run-semantic-diff`：开新 run，做语义比较，不混 findings |

这张表是**策略钉，不是运行时闸**：仓库里没有任何代码会拦住第二次 checkup，表只规定
AI 该怎么做（「未形成硬约束」那节把话说死）。

文件大小或哈希变化按下面的语义判定，别自己编原因（`archive-bytes-changed` 是**观察
标签**，不是原因）：

| 观察到的变化 | 允许的标签 |
| --- | --- |
| 文件大小 / 哈希变了 | 只允许 `archive-bytes-changed`（导出或归档被重写） |
| 文件大小 / 哈希变了 | **禁止** `user-modified-design`：文件变化不得单独证明用户改设计 |

要断言「用户改了设计」，必须有设计侧证据（改前改后的对象或字段、用户自己的说明）；
文件字节变化不得单独证明用户改设计。

#### 中途中止：只读已有产物

中止、402（余额/计费）、超时、预算耗尽时，**只读已有产物**出 `partial`，并且
**不新跑**：checkup、run_pcb_review、DRC、采集。不开编辑器、不出图、不读新页面。

- 材料就是盘上那些：`report.json`、`review-read` 的结构化输出、`review-summary.md`、
  已写的图；
- `review finalize` 允许在内存里重算 completion / summary（re-gate 是校验，不是采集），
  但不得为了收尾重新连一次编辑器；
- partial 里逐条分四档，不许揉成一句「部分完成」：
  **已确认**（有证据，结论可直接用）、**疑似**（有线索但证据不足，写明缺什么）、
  **未验证**（没读到：通道缺失、页面没激活、模型为空）、**未覆盖**（这一轮根本没查）；
- 缺手册 / 缺 `intent` / 缺证据的条目落 `needs-manual` 或 `open-item`，不落「通过」；
- 其他板、历史记忆和网名只能当**线索**，不能当证据；
- **缺 `finalize` 不是耗时根因**：它是交付校验，没跑就说没跑；没有 CLI **收据**，
  就不许冒称做过正式 finalize（手写 `finalize.json` 不算）。

这一节是流程纪律，**不是**「固定分钟数完成整板审查」的承诺：板子大小、通道可用性、
手册可得性都会改变耗时，分钟数只用来决定「什么时候先把已经有的交付出去」。

#### 已有机器支撑

- **Python CLI 的 opt-in 闸**：R2 `checkup --file --strict` 对同基准重算拒绝，R4
  `review finalize --strict-partial` 校验 partial 四档披露；默认 CLI 路径不变。`review-read`
  仍只读报告，不产生新结论。
- **541R3/I/R4 DSH pre-execute（隔离真实 DSH 已验，桌面未部署）**：受管 Session 的 checkup 必须显式 out；一批完成
  深挖后，下一项 checkup/review_evidence 需要同目录、同 callId 的 initial/partial Session
  receipt。欠账批次不能靠换 out 绕过。墙钟预算是 30 分钟或 60 model steps，新阶段收据开新段；
  review_read/finalize/doctor 可收尾。联合 DSH **169 passed / 1 skipped**，跨目录、预算与
  error-result 独立变异均先红后恢复；541R4 起 error `tool/result` 只清 pending、不记深挖。
- **公开接口**：受管工具固定 argv，review_read 只有六个公开 section；bridge 由 protocol
  唯一目录在 daemon 前拒绝非 read/未知动作，并附 `tool-gap`。Python 目录闸 **36 passed**，
  DSH 拒绝/普通结果回归已核。

隔离 DSH 0.2.2-rc.3 的两轮实载已验证：文件收据不解锁、initial/partial Session receipt
解锁、跨目录欠账与 tool-gap；证据 `.tmp_541_live/session-4-events.jsonl`。**桌面 profile
未部署**，任意宿主文件解析仍未覆盖。

#### 未形成硬约束 / 未覆盖

- **非受管 harness 顺序**：R3 只覆盖上述 DSH 工具，其它调用方何时加载 skill、先走哪一步
  仍由各自 harness 决定；
- **已派发命令**：预算闸只在下一次 pre-execute 拒绝，不设计时器打断当前命令，也不把杀进程
  写成阶段交付；
- **全局重复计算**：`review-read` 可复读不等于全局去重。Python CLI 默认路径没有全局去重，只有显式 R2 strict 和受管 DSH R3
  按各自合同拒绝；`review-read` 再稳定也不会让下一次 checkup 自动变便宜；
- **任意宿主工具 / 私有 API**：普通 Read/Grep/Bash 手解析内部文件没有被 allowlist 拦截，仍是覆盖缺口；
  bridge 的每个 read 动作也不都有高级工具等价物。

实现与验收边界见 [`../tasks/review-stage-runtime-gates.md`](../tasks/review-stage-runtime-gates.md)、
[`../tasks/541r3_dsh_stage_gate.md`](../tasks/541r3_dsh_stage_gate.md) 和
[`../tasks/541i_public_interface_allowlist.md`](../tasks/541i_public_interface_allowlist.md) 和
[`../tasks/541r4_dsh_error_result_fold.md`](../tasks/541r4_dsh_error_result_fold.md)。

### 3.1 审板子＝`boardwise checkup`（首选，一条命令）

```bash
boardwise checkup                                  # 焦点工程，报告写 checkup/
boardwise checkup --project <工程名|uuid> --out <目录>   # 多窗口时指哪打哪
boardwise checkup --file <导出.epro2> --out <目录>       # 断连兜底：纯离线，跳过在线阶段
```

产出（`--out` 目录内）：`report.json`（契约）· `report.md`（人读，同一份内容）·
`board-report.md`（**整板报告**：ERC+DRC+模块+器件合成一份，按「板 → 阅读层（通用门票 →
PCB 模块 → 器件）→ 模块/规则族」分组、层内按严重度、每条一句话、末段答「整工程能不能投板」，
最后收一个按 `(板, 位号)` 合并的**器件大节**；与 `report.md` 开头那一节同一份渲染，
一键出的就是它）·
`architecture.md`（架构骨架，§3.1b 必须逐槽走；**自动生成、每次覆盖，手填无效**）·
`design-intent.md`（**设计意图**，工程师所有：不存在时建全 TODO 模板，存在则生成器一字不改）·
`review-summary.md`（**审查总结骨架**，见下面的收尾死一步；重跑同一 `--out` 时机器内容
重生成、人工「分析/建议」与第 1/3/4 节按 key 保留，新 finding 留空、消失的进 `## 2b`、
复活回主表；无法对齐旧文件时整份保留并在 `ai_slots.review_summary` 披露 `entries: null`
+ code）·
`canvas-<页名>.png`（每张原理图页一张，PCB 页不出图）。

同一个 `--out` 同时只允许一个 `checkup`：`.checkup.lock` 是 OS 锁的载体，不是「文件在就占用」；
后到者在读模型、拉 daemon 或写报告前 exit 2。进程退出即释放锁，锁文件保留不影响下一次；
锁本身建不起来同样 exit 2，绝不无锁放行。串行重跑仍允许，实际更新机器生成物后会打印
`rerun:`，人工内容按上面的既有规则合并。输出目录不可写、`--out` 形状不对或 `arch --out`
写不进去也是 exit 2 + 一句人话，不再给 traceback；已经写出的文件保留，但这轮不算完整交付。

**先看 `board-report.md` 一眼定盘**（哪块板、哪个模块、几条 ERROR、能不能投板），
再按下面的四步逐段读 `report.md` 做深度审查。

**阅读顺序（200A 起，两份人读产物同一条）**：设备/模块/器件两处的读法是
「主机 DRC（ERC/DRC 门票）→ 模块 → 器件」——`report.md` 的 `## 主机 DRC`、`## 模块`、
`## 器件（未审器件 / 接受未审 / 未知项合并）` 按这个次序出现；`board_report` 的分组按
「通用门票 → PCB 模块 → 器件」排列，**严重度只在同一阅读层内排序**。这是**独立的阅读顺序键**
（`reading_layer`），不是 `WEIGHT_RANK`：后者仍是「重要性」（PCB 模块级 > 器件级 > 通用），
两者不互相推导，谁也不许拿一个当另一个用。

**器件大节（200A 起）**：`unreviewed_parts[]`、`accepted_unknown[]`、`needs_datasheet[]`
三份来源按 **`(板, 位号)`** 合并成一张表，每颗器件每块板**只一行**，行内保留未审原因、
接受未审（理由/谁/何时/状态）与 facts/未知项状态（含依赖的 findings）——
**同名位号在不同板不合并**（那是两颗料，MPN/Value 按该板位置读），三份来源全空时
只印一句话、不出表。`report.md` 与 `board-report.md` 用**同一个渲染器**（`render_part_section`），
器件行逐字相同、顺序相同；JSON 里三份数组原样保留，**没有**新增平行的 JSON 器件清单。

- **只想问「能不能投板」就只读 `report.json` 的 `conclusion` 节**（185 起，顶层）——
  它是这份报告**唯一权威**的结论，六个字段全是既有数据的**读**，不是第二套算法：

  | 字段 | 是什么 | 同源处 |
  |---|---|---|
  | `verdict` | 审查跑完没有（`complete` / `complete-with-open-items` / `incomplete`） | `completion.verdict` |
  | `exitCode` | 这次跑退出几（就是下面那条退出码规则） | `summary.exitCode` |
  | `mayClaimPassed` | **窄义**：没有器件缺手册未审（053 §2.2） | `summary.mayClaimPassed` |
  | `mayQuotePassed` | **脚本判读只看这一个布尔**：`verdict` 是 `complete` 才为 true，其余一律 false（188B） | 由 `verdict` 派生 |
  | `oneLiner` | 那一句话结论，**与 `board-report.md` 的 `### 整工程能不能投板：` 后那一句逐字一致**（同一函数 `board_report_verdict`；两处各自独立调用，确定性保证逐字相同，不是"同一次调用"） | `board_report_verdict` |
  | `blockers` | 为什么不能投/还欠什么，逐条 | `completion.verdictWhy` |

  **AI 汇报、脚本判读一律只读 `conclusion` 节；`summary.*` / `completion.*` / `ai_slots` /
  `board_report` 都是它的投影**，要细节（哪条规则、哪个位号）再往下翻对应节。任何场合都**不要**
  自己拿 `summary.conclusion`（窄义字符串）或 `mayClaimPassed` 拼一句结论——那正是 185 要收掉的缝。
  节里没有的东西就是没有，不许由 `board_report` 或 `report.md` 反推一个「应该通过」。
  **`exitCode 0 ≠ 可投板`**（188B）：退出码 0 还覆盖 `complete-with-open-items`（有欠账但不定
  incomplete），也覆盖"看起来干净"的窄义读数；要拿一句话卡 CI，卡的是
  `conclusion.mayQuotePassed`，不是退出码。
  **旧报告没有 `conclusion` 节**（185 之前的 `report.json`）：重跑一次 `boardwise checkup`，
  或任一重新写报告的子命令（`triage` / `need-datasheet`，它们都走同一个写口）把它重建出来；
  不重跑就按旧五处顺序读——`completion.verdict` → `summary.exitCode` →
  `summary.mayClaimPassed` → `board-report.md` 的结论句 → `completion.verdictWhy`。
- **`needsDatasheet` 三键别读错**（185）：`completion.needsDatasheet` 是**窄义**（审查者手工标记数，
  已判 deprecated，改读 `completion.reviewerMarked`）；`completion.needsDatasheetTotal` 才是
  `needs_datasheet[]` 的全量（facts 触发 + 手工标记）。向工程师报「还差几份手册」时用
  `needsDatasheetTotal`（那才是清单长度），报「你标了几项」才用 `reviewerMarked`。
  **口径（185-中1）**：`needsDatasheetTotal = len(needs_datasheet[])` 是**去重位号数**，
  不是 placement 行数——`unreviewed_parts[]` 每个（板，器件）一行，`needs_datasheet[]`
  按位号折叠成一行，所以它 `≤ len(unreviewed_parts)`，多板工程里严格小于。
  折叠行带 `boards`：该位号出现在哪几块板、**每块板上的 mpn/name/value**（15/14 个位号
  在多板上的身份并不相同，`C2` 一块板无 MPN、另一块板带值码）。所以
  「还差几份手册」= 去重位号数，**但要按「位号 × 板」估工作量**：一块板上一颗料要一份
  手册，多板同位号要逐块核。`report.md` 的未知项节会把多板位号逐条列出来。
  **191B 起两处同形**：`unreviewed_parts[].boards` / `reviewedByShelf[].boards` /
  `accepted_unknown[].boards` 与 `needs_datasheet[].boards` 是**同一个形状**——每条
  `{board, mpn, name, value}`（placement 行，不是板名列表），所以任一节的 `boards` 都能
  直接读成「这块板上的这颗料是什么」；旧报告里的板名列表仍可读（`board_titles`/`board_rows`）。
- **退出码**：`0` 无 ERROR / `1` 有 ERROR（主机 ERC fatalError/error、主机 PCB DRC 逐条、
  自有规则 ERROR 任一命中）/ `2` 输入不可用 / `3` 说不清——在线状态不可陈述（daemon 不通、
  没 connector、三级数据路全被拒）**或 `completion.verdict` 是 `incomplete`**（073：审查没看全——
  没读到模型 / 有器件缺手册未审 / 骨架没生成 / 覆盖有缺口）。优先级：坏输入 `2` > 有 ERROR `1`
  > incomplete `3` > `0`；`complete-with-open-items` **仍是 `0`**。`3` 绝不是"板子干净"，
  CI 里也别当通过。
- **报告自己说数据从哪来**（`source.tier`，缺一级就如实降级）：
  `project-file` 整工程归档（满血，**166 起在线此档即跑 PCB 版面审查**；跑不成显式披露
  「PCB 版面审查未跑（原因）」，不沉默也不背锅 verdict）→ `per-page` 逐页导出合并（跨页连通性按网名，
  不是追出来的连线）→ `netlist` 仅连通性（无值/无 MPN/无位姿）→ `file` 离线文件。
  **per-page 档里跨页同名的网不是已验证的连接**（issue #19；参数两条规则于 076 补齐、
  选型两条于 064 补齐）：按网找
  协同器件的 11 条规则（`decap-required-caps` / `conn-nc-and-must-connect` / `conn-usb-cc-pulldown` /
  `param-divider-output` / `param-led-current` / `param-rc-cutoff` / `path-ldo-dropout` /
  `pwr-domain-vs-range` / `pwr-supply-on-known-domain` / `sel-tvs-standoff-rail` /
  `sel-ldo-fixed-output`）对出现在多于一个页的网名
  **一律不下通过/违规结论，只报 UNKNOWN**
  ——同名可能是同一块板的另一张页（真连），也可能是另一块板碰巧同名（假连），这一档分不出来。
  每条规则只对**它自己真正读的那几条网**查（`rules/unproven.py` 的登记表逐条写明：rc 查 R-C 共用的
  非地网，led 查 LED 与串阻共用的网加那条读出电压的轨），地网不查——地网按构造每页都有，查它等于
  把每对 RC 都拒掉。
  报告在 `source.unprovenNets`（网名 + 各自出现在哪些页 + 拒绝的规则名单）与 notes/档位说明里写明；
  `per-page` 档位说明就是那句「agreement by name is not a verified connection」。
  **单页工程与 project-file 档行为一字不变**（单页的网按构造即为已验证）。
  `drc.*.checked=false` + `reason` 一律是"**没查**"，不是"零错误"。
  **工程真有 PCB 文档而这回宿主 PCB DRC 没跑（`drc.pcb.checked=false`，离线/在线拒绝一样）时，
  verdict 是 `complete-with-open-items` 而不是 `complete`**（038R2）：`coverage.hostPcbDrcUnchecked`=true
  把它写进 `verdictWhy`，`conclusion.mayQuotePassed=false`、整板结论**不得写「可以投板」**；
  无 ERROR 时 `exitCode` 仍是 0，`checked=false` 也不会被改写成 ERROR 或 Finding。
  自有规则没新增 clearance finding **不等于**宿主 DRC 通过。无 PCB 文档的工程不受此闸影响。
- 只读：`doc.open` 只切焦点、`userInterface` 恒 false（不弹底部面板），每个阶段 `finally`
  把焦点复位。旧版 connector 缺某个动作时报告会记 `note` 并降级，不会瞎报。

**审查四步与 AI 槽位（报告 schema /6：`ai_slots` 加四个一等节就是清单，逐条做完再答用户）**：

⓪ **先问再判（事前动作，阻塞——058 起是第一步，做在①之前）**：动手判定任何器件/管脚之前，
先把**「功能建立不起来的器件与管脚」**列成一张清单，它就是报告里的 `needs_datasheet[]`：
两个触发源，一个清单——

- **触发源①（facts）报告生成时就带着**：规则判不了的器件（= `unreviewed_parts[]` 原样纳入）。
- **触发源②（marked）是你的活**：图上读不懂的管脚、或整颗行为不明的新器件，在**下任何判定之前**
  用 `boardwise need-datasheet --out <checkup目录> --part U7 --pins FB,ICG --reason "为什么解释不了"`
  写进报告（`--pins` 可省 = 整颗器件；按 `(part, pin)` 幂等，重复标记只更新 reason；
  命令会重算 `completion` 并重渲染 `report.md`，纯文件操作、不碰编辑器。**报告里记录的那个
  退出码也一起重算**（075）：标上去 `0 → 3`，标记没了回 `0`——命令**自己的**退出码不是它，
  把标记并进报告成功就是 `0`）。
- 清单非空时**一次性向用户索取**对应手册/资料；**资料到位前不得对依赖它的条目下"通过/不符合"
  结论**，只能写「无法确认（等资料）」。
- **边界（写死）**：**不是**"等齐所有手册才准开工"——**能独立算的先算**（分压、耐压、降额、
  驱动电流照算不误），只把**依赖未知器件功能**的条目挂起；**不**默认自动联网抓手册
  （`parts fetch` 的三通道现状不动，官网通道仍然是你的 WebSearch 活）。
- **消歧：「不许涂绿」与「先问再判」是两件事，分属两个阶段，不许合并成一句。**
  「不许涂绿」是**事后标记**（判不了就如实说判不了——早就有）；「先问再判」是**事前动作**
  （判之前先把未知项列出来、要资料——本步）。事后如实 + 事前索取，两道都得有：
  issue #8 踩的是后者缺席，不是前者。

① **ERC 先行**：主机 ERC/DRC 读数在 `drc` 段——error 已在报告头部错误段，先解决；
warn 逐条进 `warning_triage[]`，**把每条的 `verdict` 填成 有益/有害/无害、`reason` 写理由**——
填法：`boardwise triage --out <checkup目录> --key <key> --verdict … --reason …`
（report.md「警告分诊」表里有 `key` 列；填了立即重算 completion 与报告里记录的退出码
（075——命令自己的退出码是 `0`），重跑 checkup 经侧车并入不丢）。
主机 ERC 的逐条形状看宿主版本（§6 坑 27）：**V3 只有 host-wide 合计、没有逐条文本**
（039 真机 probe 实证），对着计数与画布图判，要看文本得去编辑器底部面板；**V4.1.93 起返回值里
直接带逐条对象**（`type/rule/primitives`，落成 `drc.schematic.pages[].items`），按条目分诊即可。
PCB DRC 叶子和自有规则 WARN 是带文本的。
含警告的模块已排在 `modules` 前头（`source.modulesOrderedBy = "warnings-first"`，
每个模块带 `warningFindings`），分模块**先审含警告的**。

**自有规则里有一类 WARN 要按轨分档看：去耦距离**（`pcb-decap-distance`，191D）。
「去耦电容离供电脚多远算超」不是一个数，而是由**这颗器件在这条网上的脚名**读出四档——
消耗端供电脚 200 / 稳压器输入 300 / 稳压器输出 500 / 侧别读不出 200 mil：

| 档名 | 阈值 (mil) | 什么脚名落进这一档 |
|---|---|---|
| 消耗端供电脚 | 200 | 这颗件**吃**这条轨：`VCC`/`VDD`/`AVDD`/`DVDD`/`VDDA`/`VBAT`/`VS`… |
| 稳压器输入 | 300 | 这颗件是稳压器、这条轨喂它：`VIN`/`PVIN` |
| 稳压器输出 | 500 | 这条轨是这颗件**产出**的：`VOUT`/`SW`… |
| 侧别读不出 | 200 | 脚名什么都没说（`RON` 类、裸编号、词表外且 `pin_role` 无角色） |

同一条网上多档并存时**取最严**（证据行点名输了的那档）；超限即 WARN，四档一个口径
（190 那条「VOUT 侧降一级为 INFO」已撤）。**四档数值是 house rule 的初值、可随反馈调**
——它不是标准（IPC-2221 只讲 clearances，不讲摆放距离），来源与实测语料见
`rules/pcb/distance.py::DECAP_TIER_MIL` 与 `outputs/191d/evidence.md`。

② **分模块 + 手册闸**：手册闸的唯一未知项清单是 `needs_datasheet[]`（⓪ 的两源合一）——
`unreviewed_parts[]` 是它的 **facts 触发子集**，保留原名不动，三通道状态
（`channels.engineer/lcsc/official`）就在那些条目里；`summary.unreviewedByClass` 再按
**下一步动作**分两栏——「工具读不懂」（值不可知，再喂手册也没用，要补的是读法）与
「真缺资料」（手册真缺，去要资料）。遇到不熟的器件**不许跳过、不许涂绿**——
按通道取手册：工程师给的 PDF 放 `.tmp_datasheets/`
（`boardwise parts fetch <mpn> --file <PDF>` 落进去）；立创通道 `parts fetch <mpn>`
自动从库条目链接下载并提取候选事实；官网通道永远是你的活
（`channels.official.suggestedQueries` 给了查询词，WebSearch 找规格书，核**周边配置**：
去耦/上下拉/限流/耐压，顺手确认可用型号）。拿到手册当场核完继续审，**三通道全灭**
才让它留在未审器件里。

**整板批量入口（555）**：几十颗未知不要逐颗重复找。首轮 checkup 后，用
`boardwise parts hunt --file <归档> --from-report <checkup/report.json> --out <hunt目录>`，
live 则把 `--file <归档>` 换成 `--live [--project/--instance]`；`--from-report` 只处理
`needs_datasheet` 点名的器件，空清单零外呼，坏报告/报告与工程对不上为 2，不退回全板扫描。
DSH 对应 `boardwise_parts_hunt`（`file` 或 `project`/`instance` 三选一，`out` 必填，
`fromReport` 同一路径）。三阶段仍是同一条既有链：C 号自动下载/缓存 → MPN-only 搜索后以
`answers` 回灌 URL → AI 每批 3–5 颗只读引脚/供电/推荐外围/额定值等相关章节，以
`claims` 回灌 facts+quotes 过逐字引文闸。四个产物是 hunt-report.json / hunt-plan.json /
hunt-report.md / hunt-audit.jsonl；PDF 正文留缓存，不把几十份全文塞进上下文。
`shelf` 只有显式给路径才写，默认不改用户架；机器档只驱动计算且仍待人工签核，
不得把机器核验写成 `verified` 或 `complete`。

**在线连通证据（559 / 559B，direct-only）**：要回答"这两个焊盘在 direct 范围内是否共享
铜"，在焦点就是目标 PCB 时用 `boardwise pcb connection --from U9.2 --to CN3.1`
（可选 `--project/--instance/--port`）；DSH 对应 `boardwise_pcb_connection`
（`from`/`to` 必填，其余可选）。它**只认直接证据**：两端 `getConnectedPrimitives(false)`
报同一根有类型 Line/Arc（`direct-shared-track`），或一端 direct 明确是对方焊盘
（`direct-other-pad`）才是 `CONNECTED`。**不读 `getEntireTrack`**（真实板上它返回的 ID
集合跨离线分离铜分量，见 `evidence/559/entire-track-rejection.json`），多跳/铺铜/过孔
邻接不在本合同内。`NOT_PROVEN`（exit 2）只说「direct 范围内两端没有共享图元」，
**不是开路**——引用否定结论前先看 JSON 的 `scope`/`unknown`；`INDETERMINATE` 与
refusal（stderr 一行 + 空 stdout，含旧 daemon/connector 没这个 action）都是 exit 3，
refusal 不是结论。命令不打开/切换文档、不写设计，焦点 PCB 就是板身份（没有 `--file`、
`--board`、`--live`）。

**该节非空时不得宣称"审查通过"**——结论只能用
`summary.conclusion` 那句（"DRC/连接性已审，N 颗器件缺手册未审；另有 M 项管脚待手册（已标记）"），
`summary.mayClaimPassed` 就是这道闸（**窄义**：只回答"有没有器件缺手册未审"——没别的意思）；
**完整结论/总闸看 `completion.verdict`**（`needsDatasheet > 0` ⇒ `incomplete`，与
`unreviewedParts > 0` 一样让它进不了 `complete`）。
**喂 PDF ≠ 清闸**（186）：`parts fetch` 只写出 `facts_trust: candidate` 的候选；清闸是
`boardwise parts add <MPN> --lcsc <C码> --facts <facts.json> --verified`——你读完 PDF 把
facts 写进货架（每条带出处页码），**由人核验并声明**才驱动规则。
**三档里中间那一档要会读**（522）：`parts hunt --apply-facts` 过了六道闸（引文逐字在它点的
页码上、pin 在文档里、来源是 URL 或 `file:`）写的是 **`machine_verified`**——证据链是机器核
过的，结论不是。它能驱动**计算**（载流 / 降额 / 间距 / dropout / 区间），**不能**驱动连接结
论、安规、隔离；它驱动的每条 finding 都带「参数来源：机器核验（URL），**未人工确认**」，而且它
**不会**让 `completion.verdict` 变 `complete`——这类件在 `unreviewedByClass` 的
「机器核验待人工确认」桶里，等着人签字。板上只有器件名、没有 MPN 的
器件，货架条目按**器件名**也能被认出来（报告里标「按器件名匹配」，证据级别低于 MPN）。
**第三通道：工程师明示接受**（191A）——`boardwise parts accept-unknown <MPN|位号> --reason "<为什么接受>" [--board <板名>]`
把「这颗的未知我接受」写进设计意图合同；下一轮 checkup 里该件从 `unreviewed_parts`
移到报告的 `accepted_unknown[]`，**这一颗**的未知不再挂在 `incomplete` 上（有接受存在时
verdict 至少是 `complete-with-open-items`；别的缺口还在时它仍是 `incomplete`，本轮实际值
看报告 `completion.verdict`——192B ⑪），但结论那句里一直有「另有 N 颗工程师接受未审」——
**它不是「审过了」**，`mayQuotePassed` 仍为 false。撤销加 `--revoke`。

③ **整图布局（审美开关，默认关）**：开关开着报告才有 `layout_review` 节（五轴：
拓扑可辨/流向明确/文字可读/分组合理/网络标识规范），对着 `canvas_images[]` 逐轴打 1–5 分
并写 evidence；**模型没有视觉判断力就写 `skipped`、分数留 null——禁止编分数**
（`layout_review.visionRequired` 说死了）。**首次为用户服务时问一次**"要不要开布局审美评分"，
把选择写进 `boardwise config set review.aesthetics on|off`，不问第二次；
单次想开用 `checkup --aesthetics`（单次覆盖赢配置）。画布图在 `--out` 里，
打开 `report.md` 点链接即可。**`--file` 离线档位没有编辑器截图**：它出的是
`canvas-<board>.svg`（`source: geometry-render`，按归档几何画的两个视窗 + finding 高亮）——
它能读摆放/位号可读性/网络标识，但**不是实物照片**（丝印压焊盘类判定未建模阻焊开窗，
分歧以实物为准），也不含主机 ERC 的逐条文本。

最后 `summary_template` —— 按模板**原样留槽**填四段（结论先行 / 错误与归因 / 警告提醒 /
建议动作），把上面的结论写进去，别重述 `report.json` 的全部内容。

**⓹ 收尾死一步：补全 `review-summary.md`（537E：结构化读取 → 分诊 → 覆盖补全 → 填总结 → finalize → 顺序交付）**

上面四步做完**不算交付**。收尾按下面六步走，**顺序不许换、不许跳步**：

1. **结构化读取**：用 DSH 的 `boardwise_review_read`（命令行形态
   `boardwise review-read --out <目录> --section <节>`）读**完整的 JSON 文件**；
   **不许解析 `runBoardwise` 截断后的 stdout**——半截 JSON「解析成功」比失败更危险
   （缺的节读成空、空的读成通过）。它只是投影：`verdict` 就取 `report.conclusion`，
   不重新判板，也不拿 `summary.conclusion` 升格成结论。
2. **分诊**：无逐条文本的槽位（V3 主机 ERC 只有 host-wide 合计，§6 坑 27；V4.1.93 起带
   逐条 `items`，按条目分诊、不必退化）只能标
   `needs-manual`，它**仍然算 pending**；**不许**用 有益/有害/无害 三词把无细节项关掉
   （537B）。批量 `boardwise triage-batch --out <目录> --input <batch.json>`、单条
   `boardwise triage`，判决都要带理由；`needs-manual` 在
   `completion.warningsPendingTriage` 与 `warningsNeedsManual` 里同时计数，不许把这两个
   数读成 0，也不许拿「pending=0」当板子干净。
3. **environment / evidence 覆盖补全**：`environment`（运行/期望 connector 版本与限制）
   和 `evidence.channels` 的 `liveSchematic` / `archivePcb` / `livePcb` /
   `schematicImage` / `pcbImage` / `datasheets` **live 与 archive 分开记**；状态只用
   `ok / failed / missing / unavailable / not-applicable`，**未采集与失败不合并**、
   **无 PCB 文档与未读 PCB 不合并**；`partial` **只描述证据/交付覆盖**，不等于板子通过
   也不等于不通过（537C）。缺 live 通道就补采集（`boardwise review-evidence`）或如实记
   `missing`，**不许拿归档冒充 live**。
4. **人工填 `review-summary.md`**（留档）。`checkup` 在 `--out` 里留了一份骨架：每条
   finding 一行，**定位链**（工程 → 板 → 页 → 器件/网）已按机器账预填，「分析」「建议」
   两栏等你。收尾时：
   - **逐行填「分析」**：这条为什么是问题、根因在哪（设计意图不符 / 选型 / 布局 / 网表与实物不一致）。
   - **逐行填「建议」**：怎么改，或怎么确认；带不动的写「需要工程师确认 X」。
   - **第 1 节填连接状态**（§3.0 那一句原样抄）、**第 3 节填 `needs_datasheet` 的待确认项**
     （清单非空时这一节不许空着写「通过」）、**第 4 节填下一步**（按优先级编号，工程师照着做得动）。
   - **定位链不许另编**：机器账与骨架同一次推导（`report.json` 的 `location_chains` 节），
     改字不改位置；链上「未标注」的那一环是**要回答的问题**，不是绕过去的借口。
   - 重跑同一 `--out` 时**机器内容重生成、人工内容按 key 合并**：填好的「分析」「建议」
     与第 1/3/4 节保留，新 finding 两栏仍空，消失的 finding 进
     `## 2b. 已消失（重跑保留）`、复活时带着人工列回主表；无法对齐旧文件时（旧
     `report.json` 缺失/坏、旧 summary 结构坏）**旧文件整份保留、一个字节不改**，
     `ai_slots.review_summary` 报 `entries: null` + code，命令行不再说「骨架 N 条」。
     人工内容仍必须同时落在对话里（第 6 步）——2b 与整份保留是兜底，不是对话的替代。
5. **`boardwise review finalize --out <目录>`**：在内存里重算 completion / summary /
   覆盖 / 分诊，核验报告引用的交付件；**输入与内容校验（schema、分诊、覆盖、交付件、
   禁用措辞）全在写盘之前**——这一类的 1/2/3 是本目录一个字没写就退出。内存校验全过
   才调用写口：同步 `review-summary.md` 的 environment/evidence 两个机器段（人工内容
   一字不改）、重写 `report.json` / `report.md` / `board-report.md`。**写口本身出错、
   写后复核或哈希失败可能留下部分已同步的产物**——此时退出 2，**不签发新收据、不得
   交付**，并如实说明目录可能只同步了一部分（`tests/test_537d_finalize_cli.py` 的
   `failures and exceptions` 就是这条契约）。收据 `finalize.json`
   （`boardwise.review-finalize/1`，`scope: delivery-content`，
   `boardConclusionAuthority: report.conclusion`）用 sibling `.tmp` + 原子替换**最后写**；
   旧收据在内容变动后即失效，不能当授权。
   - **DSH 路径**：只有 `boardwise_review_finalize` **成功之后**，当前 Session 的 receipt
     才会写进 projection；`present` **必须等它成功**，**不能与 finalize 并行**（并行时
     Session 里还没有记录，present 直接拒）。**手写 `finalize.json` 没有 Session 特权**
     ——闸只认当前 Session 里真实 finalize 工具写入的记录，不读文件当授权。
   - **不要声称当前运行中的 DSH 已重启或已加载新闸**：源码/独立进程验收 ≠ 运行进程生效
     （537D3），没有重启证据就如实说「闸在源码里、本会话未验证」。
6. **顺序交付**：先文件、后当面讲。`present` 是**文件交付动作**，排在 finalize 成功之后
   （见第 5 步），**不替代对话里的结论**。

**权威边界（537D 写死）**：`finalize.ok` / 退出 0 **只表示 delivery-content 校验通过，
不是板级通过**；板级结论的唯一权威是 `report.conclusion`。`partial` / `needs-manual` /
`open-items` **在披露一致时可以交付**——**不许**为了过 finalize 去编造证据、补一句「通过」，
或强行关闭未决项。**模型记忆不是数据手册证据**：手上没有 PDF / 已核验 facts 时禁用
「已与手册核对」类措辞，`web_search` 失败或没核到就写「资料未取得 / 待确认」，不得把
「手册已核」写上去。**archive 不等于 live**，归档读数不能当在线证据。环境限制与证据缺口
要保留披露，不许在总结里被抹平。

**交付的两个动作，缺一不可**：文件留档（上面的目录）+ **当面把结论讲给工程师**
（2026-10-15 岳的口径：审查结果由 AI 发给工程师，不是让工程师打开文件夹自己看）。
对话里给全：verdict 一句话（能不能投板/为什么不能）→ 每条 ERROR 点名（位号 + 什么病 +
怎么改）→ WARN 分诊建议（有益/有害/无害/needs-manual，理由一句）→ 缺手册几颗、都是谁、
要工程师去拿什么 → 报告目录路径**一句话带过**。只甩文件路径让工程师自己翻 = 什么都没
拿到（2026-10-15 岳的反馈）；只写在聊天窗口里不留档 = 窗口一关同样什么都没了
（issue #69）。**文件留档 + 当面讲全，缺一个都不算交付。**

**不要重算工具已经算过的东西**：DRC 计数与 PCB 逐条在 `drc` 段、模块划分在
`modules` 段、规则 findings 在 `findings` 段；模型只补四件事——**填警告分诊、查不熟
的器件、看画布、写总结**。

### 3.1a 改板后的只读收尾＝`boardwise pcb gate`（038Y5，无 autofix）

改完板子要回答「现在能不能投」，用只读闸，而不是自己再拼一遍 checkup 读数：

```bash
boardwise pcb gate --out <新目录>                                  # 焦点 PCB
boardwise pcb gate --out <新目录> --project <工程名|uuid> --instance <窗口>
```

- **活动 PCB 与身份要求**：先 `doc.list` 证明当前活动文档就是这块 PCB。焦点不是 PCB、
  想退回 `boards[0]`、`--project` / `--instance` 与宿主回报不一致，一律拒绝，闸不自动换板；
  工程身份读不出来时，只有显式 `--instance` 才算身份。
- **fresh checkup**：每次都在 `<新目录>/checkup` 里现跑一遍（含既有间距/丝印规则），不读
  旧报告。`--out` **必须是新目录**，已存在即拒——那里面是上一轮的 report。
- **incomplete 不绿**：checkup `incomplete`、退出码 3、coverage 缺口（模型空/空板、解析不全、
  规则报错或拒绝、页/记录丢失、PCB 审查缺失）都算 INCOMPLETE，且 `incomplete` 优先于 ERROR——那时
  不能声称已看全。退出码 **0 GREEN / 2 RED / 3 INCOMPLETE 或输入、身份、输出不可用**。
- **无 skip、无 autofix**：没有 `--skip-checkup`，没有自动修复、没有 `doc.open`、没有保存；
  写入路径不经过这道闸。要改就回 §3.1 或 `edit` 链，改完另开新目录重闸。
- **兼容边界**：目前只有 fake bridge 与离线 checkup 适配的自动化证据，在线宿主与 V3/V4
  真机门禁未验证；一次 GREEN 不等于「所有宿主已兼容」。

### 3.1b 架构走查（044 起的强制环节，不是可选阅读）

checkup 每次都会在 `--out` 里写**一对文件**，规则从 053 §2.2 起：

- `architecture.md`——**自动生成、每次覆盖，手填无效**（第二行横幅就这么写着）；
- `design-intent.md`——**设计意图，归工程师/AI 提案所有**：不存在时生成器建一份与骨架同构的全 TODO
  模板，存在则**一字不改**。答案写这里才留得住（052 §2.2 实测：填在 `architecture.md` 里的
  `targetVoltage: 3.3V`，重生成后回到 `TODO`）。
- **DesignIntent 合同（090 起的第四份合同，JSON 是源）**——`--intent <path>` 或
  `~/.boardwise/design-intent/<projectUuid>.json`（`BOARDWISE_HOME` 跟着 `config.json` 挪）。
  三段：`requirements`（rails/signals/buses）+ `blocks` + `decisions`，每条带 `provenance`
  （`user_stated` > `verified_recipe` > `ai_asserted`，缺省即草稿）。**有合同时 `design-intent.md`
  是按合同渲染的视图、每次重渲染（手填无效）**；没有合同时仍是上面的 053 §2.2 逐个文件。
  生成/重生成只有一处：`boardwise arch <工程文件> --intent <path>`（已填值逐字节保留，图纸里
  已没有的对象标 `stale` 不删）。`checkup` 只读合同，绝不改写。
  报告 `intent` 节：`totals{slots,filled,missing,requiredMissing}` + `missing[]`（每槽带 `write`
  路径）+ `required[]` 的 `intent-missing` 行（点名槽位 + 文件 + 键）+ `hints[]`（
  `closure-undeclared`：双向电流采样没有 `requires: ["bias-reference"]` 类闭合声明——FOC 偏置案
  的槽位形态，A1 只提问，A3 升级为规则）。**缺槽不抬 verdict、不动退出码**；填缺口的人是
  工程师或模型，工具不代填。**092 A2b 起合同还进规则走查**（不只是报告的一节）：
  `rails[].targetVoltage` 喂 `pwr-cap-voltage-rating`，输出轨的 `continuousCurrent` 喂
  `path-ldo-dissipation`——它们的 finding 与 intent 节是两条独立出口，见 §3.2 的细则。
- **093 A3a 起 intent 进评级**（A1 以来第一次口径变化，`rules/archclosure.py` 的模块
  docstring 是权威表）：

  | 情况 | 级别 |
  |---|---|
  | 违反 `user_stated`（工程师自己声明的架构被图纸违反） | **ERROR**（`apply` 必拦，`--force` 不豁免） |
  | 违反 `verified_recipe` / `ai_asserted`（草稿不一致） | **WARN**（草稿行带「确认前不要照改」，052 §4） |
  | 无合同 | 不查，零移动（读数逐字节不变） |
  | 结构性闭合（开漏上拉、NRST，不依赖合同） | 违反 **WARN** / 闭合 **INFO 测量行** |

  三条规则：`arch-rail-voltage-clash`（合同的 `targetVoltage` vs 图上判定，两个来源的原始值都
  进消息，谁错人裁）、`arch-opendrain-pullup`（货架 `pull_required` 标了 `open_drain` 的脚——
  网成员里有电阻跨到 power-class 轨即闭合；合同 `decisions[]` 里 `user_stated` 的「用 MCU 内部
  上拉」也算，F2 nFAULT 案）、`arch-nrst-closure`（控制器 NRST 脚单成员网 = 裸奔，F3 案）。
  详见 §3.2 的一段。

- **094 A3b 起第四条规则 + 合同进 `apply` 走查**（F1 偏置案落地）：

  - `arch-sense-bias-closure`：合同声明 `signals[].kind = "current-sense"` 且
    `polarity = "bidirectional"`（或该条 `requires` 里点名 bias 类 token）的链，必须真的被
    偏置住。**判定按算术，不按「有没有画东西」**：偏置源内阻 `R_th = (R_up‖R_dn) + Rs`
    与采样电阻 `R_sense`（网上到地那只）比 —— `R_th ≥ R_sense` = 形同虚设（按上表分级，
    `user_stated` ⇒ **ERROR**；实测 F1：`R_th = 10500Ω` vs `R_sense = 0.1Ω`，
    `V_err = 1.65V × 0.1Ω/(10500Ω + 0.1Ω) ≈ 15.7µV`，想要 1.65V，**差 5 个数量级**）；
    `R_sense/10 < R_th < R_sense` ⇒ **WARN**（比值存疑，两个数都进消息）；`R_th ≤ R_sense/10`
    或网里有**运放输出脚**直连 ⇒ **INFO 测量行**（运放输出阻抗 Ω 级，免检分压算术）。
    **「1/10」是本规则自声明的判据，不是标准**——它写在规则 docstring 与
    `BIAS_CLOSURE_RATIO` 里，数字随行；拓扑对不上（网上有外来电阻，但远端网既不是可定价的
    power-class 轨、也不是「一上一下」的分压中点）⇒ **UNKNOWN + 点名去哪补**，不猜。
  - **合同的豁免通道**：`requirements.signals[].closure = "waived"`（可选键，缺省不写出）——
    工程师**明示放弃**这条链的闭合。`user_stated` ⇒ **INFO** 并引 `decisions[]` 的 rationale
    原文（F1 的 R4：「0.1Ω 直采，不加放大器」）；`ai_asserted`/`verified_recipe` ⇒ **WARN**
    （草稿不能自己豁免自己，052 §4）。shipped 合同
    `blocklib/intents/robot-ctrl-foc.intent.json` 的 `U+`/`W+` 已按 R4 决策标 `closure: "waived"`；
    撤掉它，同一条链立刻回到「无偏置网络」的 ERROR。
  - **合同进 apply 走查**（094 起）：`draw apply` / `edit apply`（以及 `draw plan` /
    `edit plan` 记基线那一步）的 findings 走查**带合同**——合同从
    `<BOARDWISE_HOME>/design-intent/<projectUuid>.json` 取（**apply 家族没有 `--intent` flag**），
    两边同一个合同。所以：**这次写造成的**自洽 ERROR 会真的拦保存、`--force` 也不豁免；
    写之前板上本来就有的 ERROR 不算「新增」、不拦这次写（闸比的是**新增**，见 §3.3 的
    `--force` 分工）。

每个槽一个**稳定 ID**：`<projectUuid>/<boardUuid>/<sectionKey>/<slotKey>`（`sectionKey` =
`<节>:<对象>`，节 = power/analog/control/bus/intent）。行内格式：`| 稳定 ID | 槽位 | 值 | 来源 | sig= |`，
来源写 `engineer@2026-09-27` / `ai-proposal@…` / `ai-confirmed@…`；`sig=` 是该槽**关联对象的签名**
（电源树节点集 / 链路器件序列 / 总线成员集），**别手改 sig**——它是"图纸有没有动过"的判据。

`report.json` 的 `architecture` 节是**骨架 ⊕ 意图的合并视图**：`slots[]` 每槽带 `value`/`source`/
`stale`，`totals.{slots,filled,stale,todoSlots}`，`intent.{file,present,filled,stale,orphans}`。
某个槽关联的对象被改画过（签名不符），该槽标 `stale: 图纸已变，此槽待复核`——**不删你的值、不覆盖、
不阻断出报告**；复核完把 `design-intent.md` 里那行的 `sig=` 换成报告给的新值即可。图纸里已无该对象
的行（orphan）同样保留并标 stale，不静默删。**出报告后必须逐槽走一遍**——044 的动机就是 ROBOT 板盲审
漏掉"FOC 采样无偏置"：器件级规则全对，链级意图没人推。
单点跑同一份骨架子加意图文件用 `boardwise arch <工程文件> [--out <path>]`（`design-intent.md`
落在 `--out` 的同目录）。

- **逐槽填 `TODO` 或显式写"不适用"**，一个槽都不许空着走：槽位键是固定英文
  （`quantity`/`range`/`polarity`/`reference`/`gainStage`/`filter`/`sourceImpedance`/
  `endpointConsistency`/`completeness`…），每条链、每张轨各一组。**填不出来不许猜。**
- **设计意图槽位（`targetVoltage`/`continuousCurrent`/`peakCurrent`/`operatingCases`）
  填不了就显式问工程师**：这些数只在他脑中，图自身可以完全自洽（044 §6）。答一次就把答案
  写进 `design-intent.md`（**不是** `architecture.md`），**以后 finding 以它为尺**；需求变了改那里
  （活文档）。AI 提案先写 `ai-proposal@日期`，工程师点头后改 `ai-confirmed@日期`。
- **无电压电源网（issue #65，岳 2026-10-07 裁定）：遇到就停下来逐条问，答一次落合同，
  此后不再问。** `VCC`/`VCCA`/`VBAT`/`VREF` 这类**名字不带电压**的电源轨，规则只出
  `intent-missing` 家族的 UNKNOWN 行、点名 `requirements.rails[net=…].voltage`——
  **那不是让你顺手转述给用户的一句话，而是一张待问清单**。
  两条离线命令把这件事机械化（只读文件，不碰编辑器）：

  - `boardwise intent audit --file <导出.epro2> [--intent <合同>] [--json a.json]`：一块板一段。
    **ask 段 = 待问清单**——每条带「凭什么说它是电源」（网名是电源轨写法，或网上挂着电源脚；
    **脚名本身也得是电源写法**：`VOUT`/`VDD`/`VM` 算，只写 `OUT`/`IN` 的脚不算——互感器、
    电流传感器、电阻的脚都这么写）与「答案写进哪个键」；**settled 段 = 「已经不该再问」的收据**
    ——每条点名答案出处：名字自带电压（`+5V`/`A5V`）、地网（0 V 是定义）、派生轨（`VCC/2`）、
    **图纸架构已定价**（货架稳压器的输出）、**合同里已有电压**（这一条就是「问过不再问」落地的地方）。
    清单非空也是 exit 0——那是这次要干的活，不是错误；exit 2 = 文件读不了。
  - `boardwise intent set-rail <网名> --voltage <值> --file <合同>`：把工程师的答案**同一个值写进
    两个键**——`requirements.rails[net=…].voltage` **和** `.targetVoltage`，`provenance: user_stated`。
    **双写**的理由：`voltage` 是「这条轨是多少伏」的**既定值**语义、`targetVoltage` 是**设计目标**
    语义，`user_stated` 时两者同义；写一份只够一半读端——`pwr-cap-voltage-rating` /
    `path-ldo-dissipation`（及 064 复用的同一个 `rail_voltage`）原本只读 `targetVoltage`，
    139 的 `intent audit` 只读 `voltage`，于是工程师答完一侧、另一侧照样报 `intent-missing`
    （064/139 撞的同一处，证据 `evidence/064/intent_slot_gap.txt`）。**别的键、别的条目、行序一字不动**
    （合同是工程师的文档，这命令只是书记）；合同不存在就建（首跑是正常态）。读不出的值
    （`abc`/`5V 1A`/`VDD`）按名字拒、exit 2，且**一个字节都不落盘**——这个槽是拿算术定价的，
    存一个谁也读不出来的字符串，这条轨就会永远问下去。

  **答案落进 JSON 合同**（`--intent` 或用户级默认位；有合同时 `design-intent.md` 是渲染视图、
  手填无效，见上）。下一轮 audit 里同一条轨**不许再出现在 ask 段**——「不再重复问」的兑现方式是
  settled 段点名收据，不是沉默。两个键**读端都认**：`pcb-voltage-spacing` 一侧按 `voltage` 定价，
  `pwr-cap-voltage-rating` / `path-ldo-dissipation` 两键都读、**`voltage` 优先**（它是「既定」语义；
  两键冲突时取 `voltage` 并在行内 evidence 注明分歧）——所以手写合同只补一个键也算答过。
- **完整结论看 `completion.verdict`**（053 §2.2）：`scope{rules,boards,pages}` / `errors` /
  `unreviewedParts` / `needsDatasheet` / `warningsPendingTriage` / `architectureSlots{total,filled,stale}` /
  `openTodos` / `sourceVersions{ruleset,rulebody}`，三态 `complete`（errors=0 ∧ 未审=0 ∧ 标记=0 ∧ stale=0 ∧
  待分诊=0 ∧ **架构骨架生成了**）/ `complete-with-open-items`（errors=0 但有开放项）/
  `incomplete`（errors>0 **或** `summary.errors` 列表非空——主机 boolean 答复/整组截断时"错的条目在、
  计数未知"，闸与 `exitCode` 同源（issue #15）——**或** 未审>0 **或** 标记>0 **或** 架构骨架没生成，
  强制环节缺席不给最高置信度（issue #14））。
  `summary.mayClaimPassed` 是**窄义**字段（只回答「有没有器件缺手册未审」），**别拿它当"通过"
  的完整结论**；`verdictWhy` 直接列出是哪些开放项。
- **解析覆盖还要读 `coverage.recordsDropped` 与 `source.parseStats`**：除管脚无编号、器件无符号、
  器件无位号外，038J 新增第四类 `conflicting_library_documents`——同一 UUID 的 SYMBOL/DEVICE
  副本若模型可见定义不同，first-wins 保留第一份，后续冲突逐份计数；仅元素 id/zIndex 重编号而
  几何/name/type 不变不算冲突。该计数进入 console/中文摘要与 `coverage.recordsDropped`，非零时
  本次阅读不能判为 `complete`，因为它可能把另一份引脚或器件定义丢在未经审查的一侧。
- **对每条链做目的论走查**：这条链是干什么的 → 端到端能闭合吗。骨架里
  `- evidence: 邻接 R4→GND` 这类行就是为这一步准备的（成员两端各接什么，工具照抄，判断是你的）。
- **不自洽的槽位写进最终结论，并与规则引擎 finding 分开计数**：`summary` 里的 ERROR/WARN 是
  规则引擎的；架构走查的发现单独成段，写明"架构走查 · 链 `<网名>` · 槽位 `<key>`"，
  别让读者以为是规则报的。
- 网名与端点复用功能（`endpointConsistency`）是同一类走查的机械入口：网名说它是什么功能、
  端点引脚说它是什么功能，两者对不上就是问题（TIM1 案的形态）。跨板链在单板模型里看不到，
  骨架会写明"控制器候选：无"，那种板以别处的控制器为准。

### 3.2 断连兜底与单点命令

没编辑器、只要一份规则体检，或要把发现画回画布/改一处值时，走下面这些单点命令。
**它们不替代 3.1**：3.1 能用就用 3.1。

- **手动导出 + 离线审查**（断连兜底）：编辑器 → 文件 → 导出 → **工程备份**，另存 `.epro2`
  （**导出时取消"加密"**，加密的读不了 → 退出码 2）。然后
  `boardwise review <导出.epro2> --json report.json --md report.md`
  —— 看原理图不用带参数：**047 起文件缺省视图就是 `schematic`**（011 家族规则对着
  schematic 模型写，而 schematic 是设计真相）。要审板级内容（焊盘/走线/过孔）显式
  `--view pcb`：它读 PCB 文档自己那份副本，原理图改了而板子没同步时那份副本是旧的
  （017 的幻影 finding 就是这么来的）。不知道文件在哪：`review --latest [<目录>]` 自动挑最新
  的 `.epro2` 并先打印它选了哪个。退出码 `0`/`1` 同 3.1，`2` = 文件读不了，
  `3` = **读出来是空的**（0 器件 0 网络：归档可能被截断/损坏，或 `--view pcb` 看了一份只有
  原理图的导出——"没读到"不是"干净板"，073 起不再退 `0`）。**`review --live` 同一档**（075）：
  在线拿到了模型但模型是空的（0 器件 0 网）也退 `3`，与 `checkup` 的 `coverage.modelEmpty`
  对齐——它与「根本没拿到模型」是两句话，两句话都不许读成通过。
- **两个焊盘之间有没有走线铜**（550 起，离线只读，不写报告文件）：`boardwise pcb net-path FILE
  --from CN3.1 --to U9.2 [--board TITLE_OR_UUID]`。`FILE` 只收 `.epro2` 归档或 `.eprj3` 文件夹工程；
  KiCad、单个 `.epcb2`、在线 `pcb.readback` **按名拒绝**（退出码 `3`）——它不会悄悄借用 `review` 的
  `.kicad_pcb` 能力去扩大承诺。**输出分两条路**：查询真的跑了 → stdout 一份 JSON
  （`schema` = `boardwise.pcbNetPath/1`）；**前置拒绝**（文件不存在、容器名不对、文件夹没有
  `.eprj3` 索引、容器里没有板、多板缺 `--board`、`--board` 匹配不到或匹配多块）→ **stderr 一行理由、
  stdout 为空、退 `3`**，不会给你一个带 `verdict` 的 JSON 让你误以为查过了。三态：
  `CONNECTED` 退 `0`（BFS 真走过一条 pad→track→via 的铜链，网名只用来选图元、**不是**连通证据）；
  `NOT_PROVEN` 退 `2`（受支持图元里无路**且**没有 unknown 能翻案），它只说「本批图元没证明这条连线」，
  **不是开路**——铺铜/PLANE/ARC 都不在图里，先看 `ignored[]` 和 `scope` 再引用否定结论；
  `INDETERMINATE` 退 `3`（输入不成立，或任何可能改变否定结论的证据缺口）。多板必须给 `--board`
  （title 或 board uuid，逐字匹配；缺省、重名、错名一律拒绝，**绝不取第一块**）。首版**没有**
  `--through`/`--layer`/`--json`/`--project`，传了就是 argparse 用法错误（退 `2`），不会静默忽略。
  DSH 工具面本批不跟：离线单点证据先由 CLI 验证，确有必要再立适配。
- **两个焊盘在宿主里是不是同一块铜**（559 起，在线只读，不写报告文件）：`boardwise pcb connection
  --from REF.PAD --to REF.PAD [--project 工程名|uuid] [--instance 窗口] [--port N]`。没有 `FILE`、
  没有 `--live`、没有 `--board`——**焦点 PCB 就是板身份**，它绝不自动选另一块板或第一块板。
  动作面只有两个 `risk: read`：先 `sys.probe`（取宿主与 connector 版本，写进 `source.versions`，
  读不到就是 `null` 并在 `missing` 里点名、`error` 里写原因——不编版本号，也不影响 verdict），
  再 `pcb.connection_probe`（参数封闭为
  `from`/`to` 两个 REF.PAD，多一个键就 `BAD_REQUEST`）。输出 stdout 一份
  `schema=boardwise.pcbConnection/1` JSON；**前置拒绝**（没 connector、旧 connector 没有
  这个 action、REF.PAD 不合法、焦点不是只读 PCB 页）→ stderr 一行理由、**stdout 为空**、退 `3`，
  不会给你一份带 `verdict` 的 JSON 让你以为问过了——「非 PCB 焦点/非只读」属于这一类拒绝，
  **不是**带 verdict 的 `INDETERMINATE`。三态（只在拿到 probe 响应后才有）：`CONNECTED` 退 `0`
  （**只认 direct**：两端 `getConnectedPrimitives(false)` 报同一个有类型的 Line/Arc，
  或一端 direct 明确是对方焊盘——**每个 `sharedId` 都带来源**）；`NOT_PROVEN` 退 `2`（两端与所有
  相关调用都完整、无 unknown 时的「在这条 direct-only 范围内两端没有共享图元」）；
  `INDETERMINATE` 退 `3`（某端没解析成唯一焊盘/空网或异网/direct
  失败/direct 里出现非 proof 类型/legacy 非空 `tracks[]`，或任何可能翻转否定结论的证据缺口）。
- **这个契约是 direct-only，永不读 `getEntireTrack`**：真实板上把一张离线 550 分成 6 个分离铜分量的网
  喂给它，`getEntireTrack(true)` 返回 76 个 ID、`truncated=true`，其中 4 个 ID 属于其他分离分量
  （`evidence/559/entire-track-rejection.json`）——**成员资格不能证明物理连通**，所以 connector 不调它、
  响应里没有 `tracks[]`、没有 id 预算与 `coverage.ids`，Python 侧也不再有 track proof；旧载荷若仍带
  非空 `tracks[]`，只记 `entire-track-unsupported` 的 unknown 并压住否定。多跳铜路径不在本契约承诺内，
  要它得另立 `getAdjacentPrimitives` 图遍历合同并做真机语义验证。
- **`sharedIds` 是集合证据，不是有序 path**：没有跳序；所以 JSON 里没有 `path`/`hopCount`/`viaCount`，
  本命令也不声称阻抗、线长、间距或 DRC 结论。
  **`NOT_PROVEN` 不等于开路**：via/fill/pour/polyline 的邻接语义未裁定，它们一律进 `unknown`
  （`direct-non-proof-type`，宿主漏发 unknown 也照样由 Python 侧补出），而不是拿来补路，
  引用否定结论前先看 `unknown[]`/`ignored[]`/`scope`。`coverage.complete` 只是
  connector 自己的单字段摘要，**不是**否定结论的依据，所以 Python 侧逐项重算两端
  resolved/唯一 pad/net、direct.ok、direct 的 ok/truncated/unreadable、scan/readErrors 和响应
  errors/unknown。**不自动切页、不写设计**：
  非 PCB 焦点直接 `PAGE_MISMATCH` 且什么都不读（CLI 侧表现为 refusal：stderr 一行、stdout 空、退 3，
  不是 INDETERMINATE 载荷），没有 `doc.open`/`doc.focus`，没有任何宿主写动词。
  DSH 对应工具 `boardwise_pcb_connection` 已由 561 接入同一 CLI（`from`/`to` 必填，
  `project`/`instance`/`port` 可选）；适配只传 argv 与文本结果，不在 TS 复制 direct 判据，
  部署与发版另批。
- **`sch.readback` 的 value/mpn 是 087E 起的可选键，缺键才走归档**（pits #3）：**新 connector** 的每行
  可选带 `value` / `mpn` / `valueSource` / `mpnSource`（`value` ← `OtherProperty['Value']`，`mpn` 先
  `ManufacturerId`、空则回退 `OtherProperty` 的料号键，空白是 `null` 不是空串）——这两项能对上，
  **就不必导归档**；但**旧 connector 或响应里没有这四个键**时，`Value`/`mpn` 不在键里，
  **别拿 readback 当复查模型，也别去手解析 `.epru`**。需要按位号核对值/料号时，先按上一段把工程导出成
  `.epro2`（取消加密），再用仓库既有 parser 逐件读这份**只读归档**。把下面这段原样粘进
  `python -`（仓库 checkout 里用 `.venv/Scripts/python.exe -`），并把 `<导出.epro2>`
  换成实际归档路径：

  ```python
  import json
  from boardwise.parsers.schematic import build_project_model

  project = build_project_model("<导出.epro2>")
  rows = [
      {"board": board.board.title, "designator": c.designator,
       "value": c.value, "mpn": c.mpn}
      for board in project.boards
      for c in sorted(board.components.values(), key=lambda c: c.designator)
  ]
  print(json.dumps(rows, ensure_ascii=True, indent=2))
  ```

  何时用：在线 readback 已给出位号（如 `C1`），但值/料号要复核；多板工程逐板输出，
  用 `board` 区分同名位号。返回字段：`board` / `designator` / `value` / `mpn`；
  `value` 是实例的 `Value`，`mpn` 是器件身份（实例字段优先、库 DEVICE 兜底）——
  **读不出就是空串 `""`**，片段不补猜。边界：只读 `.epro2`、只打印到 stdout，
  不碰编辑器、不写工程/货架/报告。**live 传输未在本批复测**：从在线工程经
  `sys.get_project_file` 取归档这一步本批没有真机验证，别把它写成已验命令；
  要在线取档先按 `docs/bridge.md` 核返回形态与落盘方式。**钉子**：
  `tests/test_doc_claims.py` 原样提取上面的代码块，在仓库既有匿名 fixture 上真跑
  （C3 值/料号可读、C1 空值仍空）——改字段或改代码而不改文档，测试当场红。
- **PCB 目视复核：几何与 viewport 两级证据**（pits #23 的 PCB 边界）：`export.render` 是**一个**
  动作，**没有 PCB 专用的第二个出图动作**。**历史边界（已实测，仍成立）**：V4 O2 实测
  （2026-10-31，宿主 4.1.93）PCB1 已 `doc.open` + `document.current` 逐字确证激活，
  `export.render(format=png, scope=page, timeoutMs=60000)` 仍**整 60.01 s 不返回**，同会话原理图页
  ~100 ms 返回（V3 同样；首次 10 s 那次是**同一失效**）。⇒ 不是预算太短、也不是焦点没激活：
  **原理图那条文档出图路径（`sch_ManufactureData.getExportDocumentFile`）只服务原理图**，
  对 PCB 页不适用，是 schematic-only 的宿主能力边界。`timeoutMs` 的 1–60 s 夹取与 30 s 缺省是
  **上限设计**（防一个不 settle 的 promise 占住动作槽），不是修法 ⇒ 不给 60 s 盲重试，也不把一次
  `TIMEOUT` 写成板子的性质。
  **新态：已落 `3d4a0d5`（`origin/main`）、test V4 已在线验收（2026-11-16）、未发布**：connector 0.6.1 的热更实例
  （`inst-121517427-g280bz4e`）上报 `capabilities.pcbRenderViewport=true`；对**已确认的 PCB 目标**，
  `export.render` 另走一条 viewport 分支——目标页 `doc.open` 之后经
  `dmt_SelectControl.getCurrentDocumentInfo` 回读确证（回读不确认就**不取图**、具名报错），
  再 `zoomToAllPrimitives` + `dmt_EditorControl.getCurrentRenderedAreaImage`，答
  `channel: 'viewport'` + `evidenceGrade: 'viewport'`；PCB 只收 `format=png` + `scope=page`，
  `svg`/`pdf`/`selection`/`project` 具名拒绝（`NOT_IMPLEMENTED`，原理图出图口不被触碰）。
  调用前提是能力旗标 `sys.connector_status.capabilities.pcbRenderViewport === true`；**旧 connector
  缺这个键（或回 false）就是零 render 调用**——`review-evidence` 只在旗标为 true 时才渲染 PCB。
  **在线读数（逐字）**：PCB1 196764 B / SHA-256 `5300e566b498…9111f51d878a`、PCB2 93676 B /
  `6c1a51744bda…d40183d8818c`，均为真实 PNG、`channel=evidenceGrade=viewport`、activated uuid 正确；
  PCB1 的 SVG exit 1 / `NOT_IMPLEMENTED`（「不支持 PCB 文档导出，未尝试」）；主代理目检
  `outputs/review/087f3/pcb1.png` 与 `pcb2.png` 分别是 PCB1 板框与 PCB2 空板，**不是缓存错板**。
  默认全部页/板 `review-evidence` **exit 0**：`capture.ok=true`、
  `identity.verifiedAgainstReport=true`、`focusRestore=restored(originalUuid=P43)`；
  `live-evidence.json` 182276 B / `dd0c57cd5083…6678ff03a514`，`pcbImage.status=ok`（三块 PCB 各有
  viewport PNG artifact 与成功 step，第三板 93750 B / `aa3826a13ad0…00d85f216298`）、
  `livePcb.status=ok`（三块 readback + geometry）；delivery 仍 **partial**，只因
  `datasheets=unavailable`——**不写成整板通过**。同批 #87⑤：P43 C24 `100nF/CC0603KRX7R9BB104`、
  R15 `10k/0603WAF1002T5E`、U9 `STM32G431/STM32G431RBT6`（`valueSource=OtherProperty`、
  `mpnSource=ManufacturerId`），`sys.get_document_source` 逐件 ATTR 双源一致，11 个 netflag 的
  value/mpn 全 null。**这不是"已发布"**：实现仍在工作树里，未发版、未进发布件；覆盖面只有
  test V4 这一套（V3、生产非空板、SVG/PDF 与多板并发**未覆盖**）。`channel=viewport`
  是**视口级**画面，不是 document render（不是文档级出图、不含 bbox、不是 SVG/PDF，视口新鲜度
  要自己核），更不是 `export.screenshot` 的缓存帧通道。
  `pcbImage` 按旗标分**三种诚实写法**：**缺旗标**（旧 connector）→ 固定 **`not-applicable`**，
  `detail` 与 `errors` 记的是同一条理由（schematic-only API 不适用于 PCB、本次未调用）——**不生成伪图、不写 `ok`、
  也不写成 `failed`**（调用根本不发生，没有失败步骤可记）；**旗标读不出** → **未核实**（既不是
  `not-applicable` 也不是 `failed`，同样零调用）；**旗标为 true 且真拿到 PNG** → 状态 `ok` +
  `evidenceGrade=viewport`，但它只证明**采集到一张合规 PNG**（magic 字节对、base64 非空）——
  **不证明有人看过**，**PNG≠视觉通过**。原理图 `schematicImage` 仍由 `export.render` 的文档出图
  采集，**原理图成功不能替代 PCB 成功，反之亦然**。PCB 的「看过板子」要两条腿，缺一条就不是看过：
  ① **只读几何**（必做）：参数名核对过的固定命令是
  `boardwise bridge call --action pcb.readback --params '{"includePrimitives": true}'`
  （`pcb.readback` 回 `{kind, components[], componentCount, primitives[]}`：位号/封装/坐标/层，
  `includePrimitives` 才读线、焊盘、过孔）与
  `boardwise bridge call --action pcb.geometry --params '{"bboxIds": ["<primitiveId>"]}'`
  （`pcb.geometry` 给实测包围盒，读不出的 id 点名在 `meta.unreadable`）。它们全是**数字**，用来做离线/自绘
  **几何复核**（间距、越界、丝印压焊盘）。
  ② **图**（才叫「目视」）：旧 connector 上本机**没有** PCB 位图通道，一份 live 版图拿不到；
  工作树这条 viewport 分支（旗标为 true 才走）在 test V4 上已在线出图。两种情况都别把
  `pcb.readback` / `pcb.geometry` / 归档 PCB 审查 / 离线几何 SVG 写成 live 位图或
  `pcbImage: ok`——它们是**不同通道**。没图时报告写 `not-applicable`（缺旗标）或
  旧写法 `pcbImage: missing` / `visual: missing`（本次没有图），也可写成
  **人工待办**并注明「PCB 图未取到」；若用编辑器外部截图人工看过，注明那是人工/外部证据，
  仍不填进 `pcbImage`。
  **`pcb.readback` 回 `ok:true` / `componentCount:N` 只说「这几件被读到了」**：把它写成
  visual-pass、PCB 版面通过或板级通过都是**伪造证据**。另：`canvas.highlight` 回
  `highlighted: 0` 是**一个标记都没画成**（`unresolved` 里点名没解析到的 uuid），不是高亮成功；
  marker 画在交互叠层上，导出的**截图**按合同预期与不加 marker 时逐字节相同
  （`docs/bridge.md` 实测表）——所以别把「高亮过」当看过板子。
- **eprj3 文件夹工程（V4，原理图 + 单 PCB，038F5 起）**：`boardwise review <工程目录> --json ...`
  —— 目录内含 `<同名>.eprj3` 索引即识别（`sch/**/*.esch2` 逐页粘成一条记录流，原理图模型满血；
  缺省 view 正是 schematic，不必再显式写）。`--view pcb` 读取 `pcb/*.epcb2`，容器适配后复用
  同一套 PCB model/geometry 与规则；`checkup --file` 同样产出 `pcb_review` 和几何 SVG。
  当前垂直切片只接**一张 PCB**：没有 `.epcb2`、多张文件或单文件多张 PCB 都明确报错，
  不悄悄选第一张；多张的选板映射仍待后续。
  `--latest` 认 eprj3 目录（按索引 mtime 参选）；工程 uuid 从索引 `owner_uuid` 取
  （补了"只有 .epro2 才带工程 uuid"的老缺口）。**一律只读**：写路径走 bridge API，不落盘。
- **器件事实库（039 parts 工具链，纯离线）**：`boardwise parts missing --file <工程>` 列出每颗
  IC 缺哪些事实（UNKNOWN 的来源清单，含 datasheetUrl）；`parts show <mpn>` 看库里已有什么
  （每条事实带出处页码）；`parts add <mpn> --lcsc <C码>` 追加候选条目；`parts fetch <mpn>`
  取手册（`--file <PDF>` 工程师通道 / 库条目立创链接自动下载 / 都没有就打印官网查询词让你去
  WebSearch），候选事实提取是**窄**的（"引脚表+规格行"同文档才 join，Infineon 那类排版一条
  提不出、如实不改库，全文留给你读——**提取为空时命令会直说，并给出人工路径**）。
  **`facts_trust: candidate` 的候选事实不驱动任何规则**（规则视同无 facts 报 UNKNOWN）——
  **给 PDF ≠ 清闸**。中间的 `machine_verified` 只驱动计算、finding 带「未人工确认」，见上。
  清闸 = 货架条目带**已核验 facts**：
  `boardwise parts add <MPN> --lcsc <C码> --facts <facts.json> --verified`（AI 读完 PDF 写
  facts JSON 走这条；同一命令对货架上已有的候选条目**原地补 facts**，不加 `--verified` 就只
  是候选）。**另一条清闸通道是工程师明示接受**（191A）：
  `boardwise parts accept-unknown <MPN|位号> --reason "<为什么接受>" [--board <板名>]`
  写进设计意图合同，checkup 把该件移到 `accepted_unknown[]` 并在结论里报数（`--revoke` 撤销）。
  板上的器件若**没有 MPN、只有器件名**，身份链按 `MPN → C码 → 器件名` 兜底匹配
  （186；命中在报告里标「按器件名匹配」，证据级别低于 MPN）。细则见 `docs/parts.md`。
- **无电压电源网问答（065 `intent` 工具链，纯离线）**：`boardwise intent audit --file <导出.epro2>`
  列待问清单（settled 段点名已答出处），`boardwise intent set-rail <网名> --voltage <值> --file <合同>`
  把答案落进 DesignIntent 合同。**这是 3.1b 架构走查的一步，不是可选命令**——口径、退出码与
  「问过不再问」的收据形态见 §3.1b。
- **把发现画回画布**（要 daemon + 焦点在那张原理图页）：
  `boardwise bridge call --action doc.list` 拿 `pageUuid` → `boardwise review-mark report.json --page <uuid>`。
  终端那张序号表就是图例（marker 只能画形状、不能写字，`marker#N` = 第 N 个红框）；
  `--focus 3` 跳最后一条、`--no-markers` 只看不画。清标记 `review-mark clear`
  **没有 page 守卫**（清的是最前面那块画布，2026-09-21 实测）。留证据图用 `export.render`，
  **不要**用 `bridge screenshot`（3.2.186 返回缓存空帧）。退出码 `0`/`1` 部分成功/`2` 输入坏。
- **从 finding 到局部修改**（可修范围很窄）：
  `boardwise edit plan --file <导出.epro2> --rule param-value-mpn-match --designator U3 --direction value --after <值> -o plan.json`
  → `edit preview plan.json --file ...`（离线复查，永不写）→ `edit apply plan.json --file ... --json apply.json`。
  **规则不再替你选方向也不给值**（052 §2.1：MPN 矛盾有两个修复方向——改 Value 或改 MPN/LCSC，
  048 实证过"MPN 字段写错、设计值对"的真实情形）：不给 `--direction/--after` plan 直接 exit 5 并列出两个候选；
  `--direction mpn` 本 build 未开放（需新 change kind）。方向和值都由你（或工程师的意图）给，工具一个都不猜。
  *（091 A2a：`edit plan` 这条纪律一个字没动；变的是**发现消息**——契约里有该位号的
  `decisions[].value` 时，`param-value-mpn-match` 的 finding 直接说方向 = 改料号/重选件，
  出处与 provenance 一并带出；没有就两个方向都列 + `intent-missing` 点名写进哪个键。
  **092 A2b 起 `checkup --intent`（或默认位
  `~/.boardwise/design-intent/<projectUuid>.json`）真的把合同传进规则走查了**——
  除了上面这条方向消息，另两条 rail 规则也开始读合同：`pwr-cap-voltage-rating`
  报「电容耐压 vs 所在轨轨压」（耐压 ≥ 轨压 = INFO 测量行报比值；耐压 < 轨压 = WARN；
  读不出 = UNKNOWN 并点名 `C? 的耐压（所在轨 +12V=12V）`），`path-ldo-dissipation`
  报「压差 8.7 V + P=(Vin−Vout)×I」（电流没声明 = `intent-missing` 点名
  `requirements.rails[net=…].continuousCurrent`；货架声明 `ldo.max_dissipation_mw` 才判超限）。
  两条都**不发明降额系数**：测量行永远出，判决只看两个数。
  **093 A3a 起 intent 进评级**（A1 以来第一次口径变化）：合同的 provenance 决定严重度——
  违反 `user_stated` = **ERROR**、违反 `verified_recipe`/`ai_asserted` = **WARN**、无合同不查。
  四条架构自洽规则进 `BUILTIN_RULES`：`arch-rail-voltage-clash`（合同的 `rails[].targetVoltage`
  vs 图上自己的判定，**两个来源的原始字段与值都进消息，谁错人裁**）、`arch-opendrain-pullup`
  （货架 `pull_required` 标 `open_drain` 的脚没电阻跨到 power-class 轨 = WARN；合同
  `decisions[]` 里 `user_stated` 的「用 MCU 内部上拉」算闭合——F2 nFAULT 案）、
  `arch-nrst-closure`（控制器 NRST 脚单成员网 = 裸奔 WARN——F3 案）、`arch-sense-bias-closure`
  （**094 A3b**：双向电流采样链的偏置**算术**——`R_th = R_up‖R_dn + Rs` vs `R_sense`，
  `R_th ≥ R_sense` 形同虚设按上表分级、`R_sense/10 < R_th < R_sense` WARN、`≤ R_sense/10`
  或运放输出直连 INFO；合同 `signals[].closure: "waived"` = 工程师明示放弃闭合 ⇒ INFO 引
  `decisions[]` rationale，草稿豁免 WARN；「1/10」是规则自声明判据，写在 docstring 里——F1 案）。
  **apply 闸**：ERROR 必拦，`--force` 只豁免 WARN（#55 裁决 B）；**094 A3b 起 apply 的走查
  也带合同**（基线两侧同一个 `<BOARDWISE_HOME>/design-intent/<projectUuid>.json`），所以
  「这次写造成的」自洽 ERROR 会真的拦保存，写之前就有的 ERROR 不算新增、不拦这次写。）*
  `--file` 路径**只有 `param-value-mpn-match`（单器件值）可修**，别的规则按名字拒绝
  （029 补器件、035 修脚都走 `--report` 路径，见下条）。`apply` 四道保护：
  写前重读页面 → 只写一个键 → 独立 geometry 回读 → save + 复查；重复执行认 `already_applied` 零写入。
  退出码：`0` 已应用 / `2` 效果不在板上 / `3` 页状态不可陈述（**不重试**）/ `4` 前置条件不再成立 /
  `5` plan 不可用。落盘诚实度：无"关闭重开"动作时只报 `saved_unverified`；要 `saved_verified`
  得走 关闭重开工程 → 回读/导出 #2 → 再 `review`（§6 坑 3、坑 4）。
- **修单个引脚连接**（035 `patch-pin`，要 daemon + 一份 checkup `report.json`）：
  `boardwise edit plan --report report.json --rule conn-nc-and-must-connect --designator U3 --pin 4 -o plan.json`
  → `edit preview` / `edit apply` 同上。三形态：**disconnect**（NC 脚，删掉脚上附着的那段线）、
  **connect**（悬空脚画线到既有同名网段 / power-flag / 页面已有 label）、**reconnect**（删错接 + 画新接）。
  **同一 designator 同规则有多条 pin 级 finding 时 `--pin` 必给**——不给则拒绝并列候选脚号，
  `--pin` 无匹配也拒绝；`--pin` 只作用于 `--report` 路径（029 的 decap `--report` 共用同一选择器，
  不限制在 035），配 `--file` 直接拒。connect/reconnect 的目标网必须是**用户命名网**
  （自动网 `NET\d+` / `$\S+` 判不得身份，plan 时拒，exit 5）；附着在脚上的 **netlabel 删不了**
  （本机 `sch_PrimitiveNetLabel` 连读都不存在），拒绝并点名，不替用户想办法。pin 级验收 =
  **活网表（`sch.netlist`）+ 画布（`sch.geometry`）双证**，缺一 exit 3 `verification_disagrees`；
  导出网表只作事故报告附件——**导出新鲜当且仅当本 run 无删除**（§6 坑 24）。
- **插入 RC / 分压子电路**（036 `insert-subcircuit`，要 daemon；**无驱动规则**——AI 自己判断该插什么，
  工具保证插得对）：
  `boardwise edit plan --insert rc-lowpass --pin U3.5 --r 1k --r-lcsc C7250 --c 100n --c-lcsc C14663 -o plan.json`
  → `edit preview` / `edit apply` 同上。T1 `rc-lowpass` 串联插入（断开锚点脚 → 串 R → 负载侧并 C 到 GND，
  含删除）；T2 `divider` 抽头分压（`--net <网名>` + `--r1/--r1-lcsc/--r2/--r2-lcsc`，纯 create）。
  值与 lcsc **全显式无默认**（029 红线：未验证配方不静默落件）；`--insert` 与 `--file`/`--report` 同给直接拒。
  **判据与 029/035 不同**：本片无规则，幂等探测与回读的判据 = **plan 自己的 postconditions**
  （一个函数两用：写前探测、写后回读），双证缺一 exit 3；范围分家照旧（T1 含删除 → 画布身份级 +
  活网表；T2 纯 create → 导出核对）；apply 后全规则 findings 分级拦（#55 裁决 B，2026-10-02）：
  **ERROR 必拦、WARN 要 `--force` 才放行（放行的 WARN 进报告 `findings.forcedWarns` 与 notes，
  不许静默）、INFO 只进报告永不拦**；仍被拦的走 exit 2 并打印新增行。`draw apply` 与
  `edit apply`（insert / move 两条路径）**同一口径**（同一个 `_new_findings_verdict`）。
  **094 A3b 起这条闸还带合同**：基线（plan 记的那次）与写后重读**同一个** DesignIntent
  （从 `<BOARDWISE_HOME>/design-intent/<projectUuid>.json` 取），所以「这次写造成的」自洽
  ERROR（如把双向采样链的偏置改坏 → `arch-sense-bias-closure` ERROR）会真的拦保存、
  `--force` 也不豁免；写之前板上就有的 ERROR 不算新增、不拦这次写。
  落点是**两件一起**的九宫阶梯（模板自带相对偏移 + bbox 干涉检查），位号池取「页面 ∪ 工程导出」
  （§6 坑 25）。
- **局部移动一个功能块**（037 `move-block`，要 daemon；无驱动规则——AI 点名移什么，工具保证连接不变）：
  `boardwise edit plan --move --designators R7,C9 --dx 100 --dy 0 -o plan.json` → `edit preview` / `edit apply` 同上。
  dx/dy 必须是**网格整数倍**（5 的倍数），否则 plan 拒绝。**宿主移器件不拖线**（§6 坑 26）：
  线一律删除 + 正交重画（组内线在两个移动脚之间 `wire_route` 重画，边界线重画到离移动脚最远的原上报点）。
  五种拒绝并点名：边界 label/netflag/总线、组内非器件图元、目标位压既有图元或压组外走线、
  位号找不到/一对多、off-grid。**验收主判据 = 网表恒等**——移动不许改任何连接
  （活网表逐脚岛屿比对，自动网同岛规则），任何一脚变了 exit 2；幂等与 stale 判据 = plan 自己的
  postconditions（036 先例）；`modify_primitive` 报错先回读位姿、**证明没落地**才许重试一次
  （举证重试，写进报告——盲目重试仍禁）。注意：本机造不出"边界带 label"的现场
  （`place_netlabel` 不可用），该拒绝只有离线用例，别在真机上硬试。

