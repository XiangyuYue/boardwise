# boardwise — AI 协作约定（轻量）

本仓库 AI 通用约定的**唯一权威**是 SOP 的**两份同步副本**：
[`.kimi-code/skills/boardwise/SKILL.md`](.kimi-code/skills/boardwise/SKILL.md)（kimi 的约定路径）
与 [`.agents/skills/boardwise/SKILL.md`](.agents/skills/boardwise/SKILL.md)（dsh 等通用入口——
它们的 skill 扫描根是 `.agents/skills`，`.kimi-code/` 不在其中）：何时加载、审查闭环、
真机纪律 R1–R3、bridge 动作速查、真机坑表、三线命令与交付纪律，全在那里。两份是**同一份
文件放在两个地方**，同步由 `tests/test_doc_claims.py` 盯着（逐字节不一致即红），
**clone 下来读哪份都行**。本文件只列最常被违反的红线，**不复制**那份内容；
两处说法冲突时以 SKILL.md 为准。绘制线的专项裁决（分岛/合岛、成对支路、机器闸与
视觉闸的分工）不在总 SOP 里，在 `boardwise-draw` 的两个同步副本（见「业务线派单」）。

## 项目地图（动手前先读这三份）

- [`docs/roadmap.md`](docs/roadmap.md)——**稳定层**：当前在哪、版本骨架（0.5.x→0.6.0→远景）、
  五个方向（R1–R5）、绘制主线的验收锚（「一眼认出反激」）。
- [`docs/product-boundary.md`](docs/product-boundary.md)——**边界**：做什么、不做什么（硬边界清单）、
  撞车区/独有区、威胁雷达。判断「这算不算我们的活」看它。
- [`tasks/TASKMAP.md`](tasks/TASKMAP.md)——**任务全图**：001–516+ 的编号/主题/状态（已落/工作树/
  搁置/在途/规划）/证据路径。按编号查，不按时间查。

`tasks/SCHEDULE.md` 是**滚动排期**（最近几个版本的具体任务与依赖）；
`PROGRESS.md` 是按时间的**流水账**，**不要从头读**——只在需要查历史细节时 grep 它。
[`docs/handoff.md`](docs/handoff.md) 是**交接记忆**：三条线的当前状态与下一步、铁律索引、
怎么干活（命令/子代理纪律/证据惯例）。**换 harness、开新会话、或换人接手时先读它**，
它只做路由，细节一律指到上面那几份权威文件。

## 业务线派单（540B8）

- 审查线从 [`tasks/review-line.md`](tasks/review-line.md) 派单；绘制线从
  [`tasks/draw-line.md`](tasks/draw-line.md) 派单。两者共享一个模块化单体，不复制业务逻辑。
- **绘制线任务开工前必须加载 `boardwise-draw` skill**：
  [`.kimi-code/skills/boardwise-draw/SKILL.md`](.kimi-code/skills/boardwise-draw/SKILL.md)
  与 [`.agents/skills/boardwise-draw/SKILL.md`](.agents/skills/boardwise-draw/SKILL.md)
  （两份逐字节相同，dsh 扫 `.agents/skills`，由 `tests/test_doc_claims.py` 盯着）。
  它只写绘制线裁决——语义分岛、成对支路、机器闸与视觉闸互不替代、修复优先级；
  通用 SOP、R1–R3 与真机纪律仍以 `boardwise` skill 为唯一权威。
- shared parser/model/bridge/core/CLI 的改动一律走
  [`tasks/shared-platform.md`](tasks/shared-platform.md) 的**集成锁**，不得夹在规则或算法批里。
- shared、全量测试与真机串行；算法与迁移不得同批。审查线工作区 `E:\boardwise\.tmp_review_line`
  （分支 `review-v4`，owner=审查线）；绘制线独立开发、互不改文件；主仓及绘制线的未提交改动
  不碰。`git worktree add/remove/prune` 仍逐次经岳批准。

## 工作区落点

- 一次性探针/中间态放 `.tmp_<批号>/`，pytest 用独立 `.tmp_pt_<批号>`；**不在仓库根散放临时文件**。
- 长期依据放 `evidence/<批号>/`，可重跑审查产物放 `outputs/review/<批号>/`；两者默认本地，
  未跟踪/ignored 不等于可回收。实验说明与生成物分别按 `experiments/`、`outputs/experiments/` 落位。
- 分类、保留/归档/回收判据和 worktree 边界见
  [`docs/workspace-conventions.md`](docs/workspace-conventions.md)；移动/删除与 git 写仍逐次问岳。

## 红线

1. **不动 git**：不 `commit` / `add` / `checkout` / `restore` / `push`。任何 git 变更逐次经用户点头。
2. **pytest 必带 `--basetemp=.tmp_pt_home`**：Windows 上否则汇总行被吞、假 exit 1。
   并行只许 `-n 4 --dist loadfile`（**不许 `-n auto`**——打满主机被岳叫停过；
   不许 `--dist load`——它把同文件的测试对拆到不同 worker，test_bridge_cli 的
   审计序就这么死过）；多前场并行时各用各的 basetemp（`.tmp_pt_<批名>`）。

   ```bash
   .venv/Scripts/python.exe -m pytest tests/ -q -n 4 --dist loadfile --basetemp=.tmp_pt_home
   cd connector && npm test && npm run typecheck
   cd dsh-plugin && npm run typecheck && npm test && npm run build
   cd rust && cargo fmt --check && cargo clippy -- -D warnings && cargo test
   ```

   集成/发布验收的既有四线（pytest / connector / dsh-plugin / tsc）与 540C Rust workspace
   全绿才算全量通过；日常小批按下文「测试成本与全量闸」交卷，不把全量当默认侦察。
   Rust 构建/差分与迁移派单见 [`docs/rust-platform.md`](docs/rust-platform.md)。
3. **真机只碰 `test` / `test2`**：动手前先 `boardwise bridge status`（daemon 会自行死亡），
   `doc.list` 报的焦点工程名与任务书**逐字一致**才算对上身份。**禁地**：毕设FOC驱动板、
   `CH340G.eprj2`、`ROBOT ctrl FOC.eprj2`，以及一切真实工程；任务书没点名 = 不许写。
   目标缺失就停下来问（R3），不许自行解释、自行替代。
4. **删除一律进回收站，禁止任何直删命令**（xianyuyijinban 2026-09-28 定、2026-10-02 重申、
   2026-11-12 再次强调）：明确禁止 `rm` / `rm -f` / **`rm -rf`** / `unlink` 等直接删除；
   任何文件或目录，包括临时目录、测试产物、变异备份和废弃产物，**没有例外**。Git Bash 走
   Windows 原生 PowerShell 通道（`DeleteFile`/`DeleteDirectory` + `SendToRecycleBin`），
   写法照抄 SKILL.md §7。

其余纪律——变异验证 ≥2（`cp` 备份 + `sha256` 还原，禁用 `git checkout --`）、append 落盘后
`grep -c` 防双执行、不碰 `outputs/011e*` / `014_*` / `015b_*` / `016_*` 与 `tests/fixtures/`
既有夹具——见 SKILL.md §7。

## 测试成本与全量闸（岳 2026-11-15 定）

不得用减少必要审查、测试或验收来省时间；要消除的是**把全量当侦察、影响面漏算和无效复跑**。

1. **日常小批不默认跑全量**：按任务书跑受影响测试、owner/layer、真实输入或模型差分及必要变异；
   发现新缺口只扩大对应聚焦范围。全量、真机仍须任务书明确点名，不因“交卷”二字自动升级。
2. **全量前先算影响面**：shared parser/model 批次必须先列所有已知派生钉及对应聚焦测试，
   至少按实际涉及维度覆盖网表/成员、net/group/edge、digest、report/markdown、crossView、
   unproven/NC 和 CBB；一次算全再启动全量。禁止首轮漏算后拿第二轮全量寻找已知类型的遗漏。
3. **全量时机与复跑**：放在集成点和发布验收，同一议题原则上一次；只有已定位并修掉的本批新红
   才允许完整复跑一次，第三轮必须先向岳说明原因。其他线的既有红项归其 owner 披露和处置，
   不得无新证据反复陪跑；也不得隐藏红项或把“非本批”写成“全绿”。
4. **发布闸不降级**：`docs/testing-doctrine.md` 的挖洞、上机、实测、四线和发布要求不变；
   日常小批收窄测试范围不等于发布可以少验，其他线红项也不等于可以带病发版。
5. **性能靠逐测试证据**：下一次必要的全量起附带 `--durations=50 --durations-min=1.0` 和
   `--junitxml=.tmp_perf_pytest/junit-<round>.xml`（先建父目录，basetemp 仍按批次独立）。
   同树同参数跨轮 diff，先区分测试本体、调度长尾和机器环境再优化；不得擅自加 worker、
   改 `--dist`、skip/xfail，或为了补计时额外跑一轮全量。

## 绘图交付红线（岳 2026-10-20 定，520o 被拒候选落画布被骂后的裁决）

任何画出来的原理图，端给用户之前三关全过，缺一关不许端（分岛/成对支路的裁决细则与
逐条检查清单见 `boardwise-draw` skill）：

1. **自审闸**：编译/可读性闸 `ok=True`。闸不过的候选只许进 evidence 目录看几何，
   **不落画布、不端给用户**（`ok=False` 的图端出去 = 让用户替我们做验收）。
2. **连通回验**：画完对照源网表逐脚核对连通——任何一脚不通（电阻只接一边、
   栅极悬同类）整张判废。
3. **视觉自审**：渲染成图后自己用视觉看一遍，逐个岛说清「这是什么、怎么接的、
   和网表对不对得上」；说不清就回去改，不端。

配套硬规矩：地/电源网（GND/PGND/HVDC/SEC_12V 等）一律**旗标**，禁网络标签；
**一个旗标可汇聚多个就近引脚**（岳 2026-10-20 裁定，黄金板常态），但不拉全板母线；
网络标签只许跨岛信号边界。图纸标题栏是禁地，岛打包必须避开。

「什么叫读得懂」的对照规格在 [`docs/schematic-style-spec.md`](docs/schematic-style-spec.md)
（521/522 黄金板解剖提炼，S-01…S-21），视觉自审逐条对照它核。

## 子代理纪律（193 立；**已由机器兜底**）

并行子代理是这台机器上最大的 CPU 来源：三个子代理各开 4 个 xdist worker 再叠加探针/变异
重跑，旗舰机直接被铺满。四条规矩，**机器侧已经拦住了**（`tests/conftest.py` →
`tests/_process_guards.py`，机制地图见 `docs/testing-doctrine.md`）——下面写的是为什么，
不是唯一防线：

1. **单全量**：一次只跑一轮全量 pytest。要并发并发别的，别并发全量（整机槽只有 2）。
2. **探针/脚本单进程**：一次性探针、变异、测量脚本不许 multiprocessing / 线程池 fan-out；
   非并发不可时，子进程数 < 4 且总时长 < 30 秒。
3. **长命令带超时**：前台命令给 timeout，后台任务标 timeout，别让一条挂死的命令把机器占住。
4. **交卷前清理自己起的子进程**：daemon、watcher、后台 pytest 一律收干净。

机器侧实际拦的是：pytest 进程降到 BELOW_NORMAL 优先级、整机全量并发槽 = 2（拿不到就排队并
打印提示）、`-n auto` / `-n >4` 直接拒绝（`-n 0` 与 `-n 4` 放行）、OMP/MKL/OpenBLAS/NumExpr
线程数封顶 1；`BOARDWISE_NO_TEST_GUARDS=1` 一次全关。
保密是另外四道闸（暂存区正文 / 提交说明 / 发布件 / 推出前 diff+message），见同一份地图。

## DSH 低成本小批执行（岳 2026-10-26 定）

不得以减少必要审查、测试或验收来省额度；只减少重复上下文、无效调用和范围漂移。
以下预算是停止线，不是目标值；平台硬限制优先于本节。AGENTS.md 只能要求代理自停与汇报，
不能代替运行时对步数、时间和 token 的硬截断。

1. **角色边界**
   - 主代理负责规划、派单、关键 diff 审查、失败证据复核和独立验收。
   - 实现、机械修改、重复读取和报告整理优先交给子代理。
   - 主代理不得连续亲自开发；为独立复验而执行的窄读、测试和变异检查不属于连续开发。
2. **小批与停止线**
   - 一批只含一个缺口、一个文件域和一个完成条件。默认串行；并行最多两个互不重叠的文件域。
   - 挖洞与修复分批：挖洞只提交可复现问题，不得顺手转实施。
   - 主代理每批最多 60 个模型步骤；子代理最多 40 步或 30 分钟，先到先停。
   - 平台可读 usage 时，每批派生日志量（input+output+cacheRead+cacheWrite，非账单）软上限 3000 万。
   - 接近上限必须交回：已完成内容、真实测试读数、剩余问题、下一步最小动作；不得扩项续命。
3. **上下文纪律**
   - 先 grep/glob 定位，再读窄区间；默认每次不超过 300 行，超出须说明具体证据缺口。
   - 文件未变且证据仍在，不重复读取；不得反复整读 cli.py、TASKMAP、长报告或旧日志。
   - 长日志放 `.tmp_<批号>/` 或 `evidence/<批号>/`；主代理只读汇总、失败项、hash、测试计数和证据路径。
   - 子代理结论最多 2000 字；详细日志落文件。使用完成通知，不轮询代理状态。
   - 独立批次优先新会话；需要清理上下文时明确告知，不得自称已清理实际未清理的上下文。
4. **派单与异常停止**
   - **派单必须写全六节，不许写短派单**（岳 2026-11-14 定，起因见本节末）。缺任何一节，子代理就只能
     猜上下文，产出的东西看着绿、其实空转：

     | 节 | 必须写的内容 |
     |---|---|
     | ① 前因后果 | 这批从哪来、上一个批号卡在哪一句、原始拒因原文、为什么现在做这件事。**不是"已实测，不用你重新论证"就够** |
     | ② 当前树状态 | HEAD、工作树是混合未提交还是干净、哪些未提交改动是别人的、哪几处 hunk 是本批的因果项（可贴代码） |
     | ③ 文件域与禁触清单 | 唯一允许新建/修改的文件；**逐项列出**不许碰的目录与文件（他人未提交改动、证据目录、fixtures），以及为什么碰了会造成什么损坏 |
     | ④ 交付物与验收 | 要什么产物、断言要钉住什么、**并要求在指定变异下先红**（"测试通过"不等于覆盖了因果项） |
     | ⑤ 纪律与红线 | git 写、删除、`git restore`、改他人文件、调参数凑过、跑全量 pytest 等，逐条写死 |
     | ⑥ 预算与交卷格式 | 步数/时间上限；交卷必须带**实测读数原文**（命令 → 汇总行 → 差异），不许只写结论 |

   - 派单里必须写清"哪些断言在变异下仍然绿"的检验方式：子代理自报"测试都过了"不是验收，
     主代理必须自己跑一次变异复验；本次事故就是一个空转用例在变异下 3 passed。
   - 范围漂移、连续失败无新信息、无意义重复输出、超长参数或长时间无新证据，均为停止信号。
   - 不得通过增加子代理数量掩盖任务拆分问题。
   - 事故记录（2026-11-14，548K）：回归子代理派单只写了"背景已实测、不用重新论证"，结果三条用例
     全部钉在改动前就恒成立的值上，把因果 hunk 变异成 `if False:` 后仍然 3 passed——真缺口是
     **单脚标签网先预留**这一项，测试一条都没覆盖。

5. **开工、续跑与停止交接（2026-11-14 固化，548J 复盘）**
   - **开工先证输入与基线**：真机符号 profile 未校准不得落图；先记当前 SHA-256、混合工作树归属和
     聚焦基线。实现开始前必须 `cp` 备份本批文件，不能指望事后用 git 恢复别人的未提交改动。
   - **不得另造生产子系统**：已有 build/route/flag/text/page-anchor 必须优先复用。任务书未证明旧链
     不能消费并明确批准架构前，禁止新增第二套 builder、路由器、旗位器或页锚来绕开局部缺口。
   - **token 不限额 ≠ 步数/时间/范围不限额**。`resume` 只能携带新证据、同一文件域和同一完成条件；
     不得因"再试一个参数/最后一处"连续续跑。相同硬拒或视觉拒因连续两轮无新证据、超预算、需要
     扩页框/放宽阈值/另起一套算法才能继续时，立即停止并交接，不拿下一轮修补当进展。
   - **测试不得被代理做成表面绿**：不得删改宽既有断言、用错误 helper、skip/xfail 遮缺口、扩大页框或
     以自写宽松检查替代生产尺。开发期只跑任务书点名的聚焦测试；全量、真机、git、移动/删除文件
     都必须有明确授权。交卷时有本批未解决红项或没有渲染，不得写"完成"；其他线红项按归属披露，不陪跑、不掩藏。
   - **主代理验收不可转述**：关键 diff 亲看、独立变异先红后 cp+SHA-256 恢复、渲染亲眼目检。
     合成图未过视觉，不得接真实模块或真机；任一验收缺失都只能交"停止/未验收"，不能交"通过"。
   - **停止交接也是交付**：写当前 hash、真实红绿、视觉结论、未做项、混合工作树风险、证据路径和
     下一步最小动作；停自己起的进程并核对 daemon 没被自动重拉。不得以长时间尝试代替交接，更不得
     擅自清理工作树或提交 git。

6. **工具与测试**
   - 不主动使用 workflow；用户明确要求时参数不得超过 32KB，不得包含占位字段、重复片段或原始测试日志。一次无效后改普通子代理，不盲目重试。
   - 日常小批只跑任务书点名的聚焦测试与差分；全量按上文「测试成本与全量闸」放在集成点/发布验收。同一议题原则上一次，已定位的本批新红修完后完整复跑最多一次；需要第三轮必须先说明原因。
   - 本节不得被解释成减少仓库要求的四线检查、发布闸、真机验收或保密检查。
7. **交卷报告**
   - 报告主代理步骤数、子代理数量及各自实际完成内容。
   - 报告关键证据、实际测试命令与结果，以及范围漂移、重复重试、超长参数和预算接近情况。
   - 平台提供 usage 时附 input/output/cacheRead/cacheWrite；没有则只报可观察的步骤和工具计数。

## 给 clone 本仓库的 AI（入口指引，不是第五条红线）

- 审查 SOP 的权威文件是
  [`.agents/skills/boardwise/SKILL.md`](.agents/skills/boardwise/SKILL.md)
  （[`.kimi-code/skills/boardwise/SKILL.md`](.kimi-code/skills/boardwise/SKILL.md) 是它的同步
  副本，两份逐字节相同，由 `tests/test_doc_claims.py` 盯着）：
  **仓库内文件，clone 下来直接读，零安装**。要审板子先读它。
- 你的 harness 若有用户级 skill 目录：把这份文件复制成
  `<你的用户级 skills>/boardwise/SKILL.md`（约定在哪你自己知道；已有一份异版先备份成
  `SKILL.md.bak-<年月日-时分秒>` 再覆盖，别覆盖已经存在的同名备份），复制完用你自己发现 skill 的方式确认它在场。
- 手上只有 exe、没有仓库：`boardwise install-skill`（Kimi Code / Claude Code 两处）或
  `boardwise install-skill --agent`——后者打印一段引导指令，粘给你在用的 AI，它自己装。
- **DeepSeek Harness（dsh）不用装 skill**：它读**工作区**的 `AGENTS.md`，本仓库自带一份
  并已指向 `docs/roadmap.md` / `docs/product-boundary.md` / `tasks/TASKMAP.md`，把仓库当工作区
  打开即可。SOP 本身也随仓库走——dsh 扫 `.agents/skills`，那里有一份与 kimi 路径逐字节相同的
  `boardwise/SKILL.md`（`tests/test_doc_claims.py` 盯着同步）。`boardwise install-skill
  --harness dsh` 把这句原因打印出来（exit 0，不写任何文件）。
