# 交接记忆 —— 换 harness / 开新会话先读这份

> **当前路由（2026-11-25，568/569 第三批挖洞修复集成；601 文档同步）**：`outputs/hole568/TRIAGE.md` 的 **32 条 reproduced** 已由 **580–595** 分批修复并独立复验（分组：581 页框 2；582/583 计划 schema 8；584–588 CLI/config/HOME/parts 10；589/589B 风格闸 3；590–592 provenance/work-order/delivery 5；593 lint 真值 1；594 CLI 合同 2；595 DSH 哨兵 1），580 另收口 572-F 五项 SVG。R2 暴露的 7 项由 597/597B（HOME 测试隔离迁 `setenv`）、598（`src/boardwise/home.py`，owner=shared，模块 165）、599（route/provenance 兼容）、lint 文案收口。**最终全量 `12 failed / 12743 passed / 26 skipped / 2 xfailed in 3100.49s`**；其中 3 条 540 owner 计数已由 **600 单独修复**（聚焦 `50 passed`），**剩 9 条已登记基线**（564/579 线，名单见证据）；**未跑第三轮全量，12746 不是实测数**。Connector **900 passed + typecheck**；DSH **218 passed / 1 skipped** + typecheck/build；Rust fmt/clippy/test **177 passed / 4 ignored**；`tools.cli_contract` 一致、`check_repo_hygiene` 与 `git diff --check` 通过。接入点：[`evidence/596/INTEGRATION.md`](../evidence/596/INTEGRATION.md)、`tasks/580*`–`tasks/600*`、逐批 `evidence/580`–`evidence/600`。**未提交、未推送、未部署、未发布**；真机/V3/V4/容器/多板/CBB 未覆盖；suspect（568-A-H4、568-B-03、569-G-08/09 等）未当实锤修。首次全量在约 91% 因 HOME 测试隔离风险主动停止，该轮不作读数。
>
> **历史路由（2026-11-24，566–579 修复集成）**：TRIAGE 的 **14 条 reproduced** 已逐批修复并独立复验：569 标题栏，570 空页，571 页面锁，572/573/574 量化/合线/census，575 文本，576 empty-legacy，577 实时写闸，578 删页回读；579 另修复 575 引入的内置 sum 舍入回归，关闭 530e/530g/530d 三条新增几何红项。任务书与父验收分别在 `tasks/56{9,70,71,72,73,74,75,76,77,78,79}_*.md`、`evidence/56{9,70,71,72,73,74,75,76,77,78,79}/PARENT-ACCEPTANCE.md`。Connector **900 passed + typecheck**；DSH **218 passed / 1 skipped** + typecheck/build；Rust fmt/clippy/test 通过（**177 passed / 4 ignored**）；最终全量 Python **12343 passed / 26 skipped / 2 xfailed / 9 failed**：9 条与 564 的既有失败逐名一致，**没有本批新增红项，也不得写成全仓全绿或已发布**。所有改动仍在工作树，未提交、未推送、未部署。
>
> **当前路由（2026-11-24，564 P1 闭环；下方 556–562 为历史验收记录）**：
> 代码提交 **`f5083286de06b1d1b698a91e51da18463be4f4de`**（`Harden schematic drawing and verification flow`），**未推送、未发布**。最终 P1（pageUuid `65522bd768798a16`）为 47 件/52 旗，逐脚 **171 连接 + 18 NC = 189/189**，GND 41/+3V3 27/+5V 7；完整 lint **0E/1W/7I**，独立原生视觉 **ACCEPT**，关闭重开 **saved_verified**（96 件/45 网/218 图元）。交付汇总见 `.tmp_lock_p1/j7-final-candidate/live/delivery-summary.json`，最终原生图见 `.tmp_lock_p1/p1-final.png`，自动编号映射见同目录 `designators.json`。
> 根因链已落地：原会话自写 `lock_parts.py` / `lock_wire.py` / `lock_redraw.py` 绕过生产链，造成无 GND、轨短接、电容同网与实体叠放；本批补齐电气 lint、saved-page 标题栏双闸、空复制属性身份、0.01 量化与共线回读、预览 7.006px 字号及 `wire_name_row` 名字载体模型，并以受守卫属性移动修正原生文字。不要恢复那三条脚本或反复试布局参数。
> 集成读数：全量 Python **12101 passed / 18 failed**，其中 **9 项在 HEAD 上也失败**，4 项 CLI 合同和 4 项 owner 已修，1 项为 POSIX 环境项；合同/owner 聚焦 **84 passed**。connector 测试与 typecheck、DSH **218 passed / 1 skipped** + typecheck/build、Rust fmt/clippy/test 均通过。**不得写成全仓全绿**，基线失败归各自 owner 处理，不陪跑、不掩盖。
> 后续接手：以 `f508328` 为代码基线；当前三份文档更新在工作树，未另提交。真实 P1 已通过四关，不再重开旧绘制路线；其它页面、其它拓扑和任意自动布局能力不因此推定。临时文件、其它工作线新模块与未跟踪测试文档未纳入本提交，不清仓、不擅自提交或推送。

> **563 共享网表与电路语义（2026-11-24，聚焦验收完成）**：`core/netlist.py` 统一 drawlint/candidate 读取，`PinRef(source_id,pin_key)` 保留同名实例与同号脚；`core/circuitsemantics.py` 输出 `boardwise.circuitSemantics/1`、确定性类 C 文本和整体回验。two_pin/parallel/series 只表达拓扑；series 含两个端网，闭环、重复位号和 unproven 不猜连接。整组 **246 passed**；父级四项变异分别 **5/1/5/1 failed** 后 cp+SHA 恢复。`f508328` 已含主体，最终闭环修复、563 测试与文档仍在工作树，未提交、未推送。任务书 `tasks/563_netlist_semantics.md`，公开合同 `docs/circuit-semantics.md`；无新 CLI/DSH/真机/全量，器件功能语义与 CBB 内部不开放。
>
> **历史路由（2026-11-22，0.6.3 发布集成；下方 556–562 为历史验收记录）**：
> 主仓 `E:/boardwise`。绘制线 `1344464`、`c6d7b25`、`0d989da`、`0364fbc`、`d665034`、`319a76e`、`28b9345` 与审查线 `bd5e8a7` 均已推送。本版三件套统一 **0.6.3**；多跳 DSH 工具仍不注册。
> 发布挖洞修复两项实锤：`recompile-with-locks` 改用 page locks，避免页面姿态再加模块 offset；`pcb.path_probe` daemon 预算改为 **150 s**，不再先于 Connector 的 120 s 走查挂断。聚焦 **365 passed**，两项主代理独立变异均先红并 cp+SHA 恢复；CLI 官方合同一致。
> Connector **893 passed**、DSH **218 passed / 1 skipped**、Rust **177 passed / 4 ignored**，typecheck/build/fmt/clippy 均通过。三件套位于 `outputs/releases/0.6.3/`；eext 两条目与 bundle、DSH 包版本、527 个 exe 压缩流和保密扫描已核。隔离 exe 的版本、离线审查、daemon 自起/收回、双端 skill 与打包后 DSH 保存候选调用均通过。
> 最终全量 Python **12039 passed / 26 skipped / 2 xfailed in 2013.69s，0 failed / 0 errors**；真机只读结果和发布哈希以 `PROGRESS.md` 及 GitHub `v0.6.3` Release 为准。未提交 `node_modules/`、pytest 临时目录、根 `tmp*`、lock、debug 或真实容器；下文历史“未提交/未推送/不发布”只作当时记录，不再作为当前状态。
> **562A Connector `pcb.path_probe` 工作树完成**：主代理三文件 **52 passed**，Arc/预算两项变异各 1 红后恢复；`getEntireTrack=0`，输出仅图证据，无 verdict/path。
> **562B Python/CLI 工作树完成**：`core/livepath.py` 双向邻接+BFS，`boardwise pcb path`、protocol、owners=161 与 `--json` 原子写入已接通；十三文件 **376 passed**、Connector **876 passed**。父变异单向 2 红/截断16红、错action16红/写失败1红，均 cp+SHA 恢复并复绿。证据 `evidence/562a/`、`evidence/562b1/`、`evidence/562b2/`。
> **562D 对抗审查三处小修完成**：两遍扫描消 `Pad` 伪 non-reciprocal、`calls > cap` 才额外判截断、JSON 写入覆盖 `OSError+ValueError`；主代理 **85 passed**，单遍与 `>= cap` 变异先红后恢复。跨层只留 562C 真机探针，没有新增 cross-layer 生产规则。
> **562C 真机验收完成，DSH 适配明确不做**：新实例 `inst-001605508-glojp393` 激活后，direct 与多 Line＋Via 均 CONNECTED（8 hops/1 via、内部图元与离线一致），分离负例 NOT_PROVEN，U5.2 Pad↔Via 为 INDETERMINATE；20 组跨层候选直接边均为 0，Arc 未启用。非 PCB 焦点拒绝、原 P1 恢复、设计写零，开发态 daemon 已停止。最终 Python **35 failed / 11997 passed / 26 skipped / 2 xfailed / 3 errors**，差分仅移除 shared owner 计数红，其他归绘制线；DSH 218/1、Rust 177/4 ignored。证据 `evidence/562c/live-acceptance.md`，真实容器只留 `.tmp_562_live/`。未提交、未推送、未部署、未发布。
> 556：`page_y` 公有化 + CLI 合同一次生成；父两变异（私有导入 1 红、去负号 4 红）后 **50 passed** 恢复。557：台账与 handoff 路由，文档/工作区 **67 passed**。
> 558/558B：义务四类 + 机械三通道 + 连接器 pinout；真实重算 unreviewed **23→23**、needs **15→11**、`verdict=incomplete` 与三份 `machine_verified` 不变；父验 135 passed、变异 A 4 红 / B 2 红，558B 精确族词后 EST026 三行转 `connector-pinout`（父移除词 3 红、聚焦 68 passed）。三份机器档已由岳签核为 verified，U8 身份与 EST026 原始判类未伪造，机械件退出 hunt 工作清单**不等于**审查通过。
> 559：纯投影 + `pcb connection` CLI + connector 只读 action；父 **268 Python + 43 Node**、typecheck 绿，两有效变异先红后恢复；真实**预验**（已激活 550B + 同会话归档身份）正反 verdict 与离线 550 一致，但原生 `pcb.connection_probe` 在旧 daemon 上 **exit 3 / stdout 空 / `unknown action`**——当时**未热更、未部署、未激活**，预验不等于完整宿主兼容（此失败史保留；2026-11-20 另行授权激活已成立，见下一条）。
> 559B（同一议题的安全收窄，非扩张）：真实板上把一张离线 550 分成 **6 个分离铜分量**的网喂给 `getEntireTrack(true)`，回来 **76 ID 且 truncated**、含其他分量 4 个 ID（`evidence/559/entire-track-rejection.json`）⇒ **成员资格不能证明连通**。proof 只剩 direct 两类（`direct-shared-track` / `direct-other-pad`）；connector 不再调 entireTrack，响应无 `tracks[]`、无总 ID 预算与 `coverage.ids`；legacy 非空 `tracks[]` 记 `entire-track-unsupported` unknown、压否定、永不用于正证明；`NOT_PROVEN` 是「direct 范围内无共享图元」，**不是开路**，多跳铜要另立 `getAdjacentPrimitives` 图合同。P2 三项披露修复保留，反例与「entireTrack 调用为零」已入测试，`contracts/cli/v1.json` 官方重生成。当时“原生 action 未激活”的边界留作历史口径，已由 2026-11-20 激活成立取代。
> 560：只做文档/台账收尾（#87 改已落 `3d4a0d5`、direct 与 last-dot 说明校正、556–560 入账）；**DSH 不新增 connection 工具**——typed CLI 底座先验收，原生激活另授权后再裁适配，本批只核既有 DSH 不回归、不 bump/pack（2026-11-20 激活已成立，DSH 适配仍未做，属另裁项）。
> **560 最终验收（2026-11-19 第三轮全量已出；本条是当前唯一验收读数）**：第三轮只跑一次做确认，命令 `.venv/Scripts/python.exe -m pytest tests/ -q -n 4 --dist loadfile --basetemp=.tmp_pt_560_full_r3 --durations=50 --durations-min=1.0 --junitxml=.tmp_perf_pytest/junit-560-r3.xml` → **11 failed / 11921 passed / 26 skipped / 2 xfailed in 2593.86s (0:43:13)**；日志 `.tmp_560/full-pytest-r3.log`，UTF-8 快照 `.tmp_560/full-r3-final-utf8.log`。第二轮 19 failed 里 **9 处审查/shared 红（537A 2 / 540 4 / 038 3）在第三轮全部消失**（父聚焦 243 passed 后才启动第三轮），**剩余 11 处全部是绘制线**：`test_116_ordinal_consumption` 1（`test_098_scene08_refusal_is_byte_identical_to_the_recorded_baseline`）、`548m` 1、`543h2` 1、`548c7` 4、`548d_wifi_ground` 1、`543h3b` 1、`draw_plain_carrier` 1、`548k_stub_lane` 1；**无 537A/540/038 红**。相对二轮名单是 10 处同名延续 + 上述 116 一条，均按绘制线归属披露。**不写全仓全绿**：11 处不越线修、不隐藏，也无第四次全量计划。
> 其余三线（同树独立读数）：connector **864 passed** + typecheck；DSH **207 passed / 1 skipped** + typecheck + build；Rust fmt/clippy 通过、**177 passed / 4 ignored**。
> 合同父变异（放在第三轮全量之后做，避免全量与磁盘变异交叉）：移除 `pcb.connection_probe` 例外 → **2 failed**；owner 行数回退 → **4 failed**；038 旧 `review-report.json` hash 回退 → **3 failed**；`cp` + SHA-256 恢复后聚焦 **119 passed**。
> 验收边界（2026-11-20 更订）：native `pcb.connection_probe` **已激活**——新实例 `inst-015644463-2wuenu0j`（`bootstrapAt`/`activateAt`=2026-11-20T01:56:44.463/465Z），正例 `LED1.2→U10.2` exit0 `CONNECTED`、唯一 `direct-shared-track` `2988899bbc9547de`，反例 `C22.1→C23.2` exit2 `NOT_PROVEN`、`proof=[]`，两例 unknown/errors 均 0，与离线 550 一致；权威证据 [`evidence/559/native-activation-success.json`](../evidence/559/native-activation-success.json)。**激活前**的旧 daemon（exit 3 / stdout 空 / `unknown action`）与旧 connector（`no handler`）失败史保留，559 的 direct-only 预验与正式激活不混为一谈。范围仍 **direct-only**：多跳铜要另立 `getAdjacentPrimitives` 图合同，`NOT_PROVEN` 不是开路。三份机器档已由岳签核为 verified，U8/EST026 身份未伪造；**不声称板卡 GREEN**。逐项汇总见 [`evidence/560/final-validation.md`](../evidence/560/final-validation.md)。
>
> **激活方式（2026-11-20，一次性账）**：仅 daemon 重启 + connector 写入 + 用户完整重启 EDA 后才生效；此前**菜单点击只增 `evaluations`、不改 `bootstrapAt`**，热更不成立。`designWrites=0`、焦点已恢复。本条只更新文档状态，不改生产代码、不碰绘制线。
> 当前目标明确：**不推送、不部署、不发布**。`outputs/releases/0.6.3-beta.2/` 的包与三件套只作本地基线，未安装给用户环境；不重启 61190、不热更、不写真实工程。
> 边界不变：真实设计写、人工签核、V3 宿主、生产非空板、真实 CBB 与“天然 GREEN”仍未覆盖；555 的 3 颗机器档已由岳签核为 verified；U8/EST026/机械件仍需人工，#87 待提出人复验不关单。台账状态校正不等于验收升级。
> 本批（560）只改文档与必要状态钉：`tasks/560_goal_integration.md`、`tasks/review-line.md`、`tasks/TASKMAP.md`、`docs/review-sop.md`、`docs/pits.md`、`tests/test_doc_claims.py`、`bridge/protocol.py`（仅注释/returns 文字）、connector `connectionEnd` 注释；零 Git 写、零删除、零全量 pytest、零 bridge/EDA。

> **Board2 P5 已完成（2026-11-19）**：test V4 / Board2 / P5 已在原 pageUuid `52123f7fe6cac768` 落最终 cand2，**未创建或删除图页，只按 plan 清理并替换页内图元**。最终 `draw apply` applied/exit0（6件、18线、15旗），`draw lint` **0E/0W/0I**，独立宿主逐脚 **21/21、37/37 NC、0 problems**，原生渲染逐岛目检通过。P44：NRST 145/0、BOOT0 90/0、3V3 327.5/4、GND 415/4，框688.5×351、内容648.5×311。cand1因1.5文字接触判退，不选。0候选 recovery、空页复用、库搜索limit64、MCU关系锁、文字逃生带、混合alternates、flagShareGroups net作用域和删页create确认闸均已落地；ch343 **8/0**、最终聚焦130+2 skipped、discard139、删页219均通过并做独立变异。最终证据与持久化边界（saved_unverified）见 [`evidence/p5-audit/FINAL-ACCEPTANCE.md`](../evidence/p5-audit/FINAL-ACCEPTANCE.md)，图见 [`live-after.png`](../evidence/p5-audit/live-after.png)。
>

> **当前落点（2026-11-19，已交付，等用户本地DSH试跑）**：本地提交已完成，branch `main`，HEAD **`9f73edebaf3fda7b23a8ddb8132dc46b7236c547`**，57个文件；**未推送、未打tag、未公开发布**。交付包为[`boardwise-0.6.3-beta.2-windows.zip`](../outputs/releases/0.6.3-beta.2/boardwise-0.6.3-beta.2-windows.zip)，SHA-256 `c9404df9f5cf7107df213fea7867168e4bd0dfde7b20b500ee70a92fd8862c2a`，包内manifest已绑定本提交。最终三件套在`outputs/releases/0.6.3-beta.2/verified/`；其他构建目录保留追溯，不作交付入口。验收明细见[`evidence/release-063-beta2/README.md`](../evidence/release-063-beta2/README.md)。本次只补交接文档，开发与试跑结果以此提交为基线。
>
> **旧 eprj2 已物理封存（2026-11-19）**：11 个旧实验 worktree 的基线历史、tracked diff 与未跟踪源码已归档到 [`worktrees/eprj2-legacy-20261119`](https://github.com/XiangyuYue/boardwise-workspace-archive/tree/worktrees/eprj2-legacy-20261119)，commit `d7c2eb3dbada0451b8e86cb65eaaf702af4ed7de`；云端核对后目录全部进回收站，约释放 2.04 GB，另6个失效登记已移除。当前只剩主仓与 `.tmp_review_line` 两个 worktree。清单与恢复方法见 [`evidence/draw-assets/eprj2-archive-HANDOFF.md`](../evidence/draw-assets/eprj2-archive-HANDOFF.md)；旧实验不得直接覆盖当前 eprj3 工作树。
>
> **接续动作**：用户准备自行用本地DSH验证效果。先确认DSH使用新exe（`BOARDWISE_EXE`绝对路径、`--version`为`0.6.3-beta.2`）、安装本包tgz并重启DSH；现场桥接另需确认新connector及daemon实际激活，不能用同版本号证明新bundle已加载。安装说明随ZIP；本代理未替用户安装或切换现有环境。后续根据用户试跑的输入、会话日志和真实拒因分诊，再派最小修复；当前不自动启动新绘制开发，也不主动重启61190或改工程。用户“提交后不要推送”的约束继续有效。
>
> **本地beta 2集成（2026-11-19）**：用户授权打包`0.6.3-beta.2`及提交当前未提交源码/测试/文档，并重申**不要推送**，由本地DSH试跑。最终pytest **11756 passed/22 skipped/2 xfailed，34:46**；connector846 passed、DSH193 passed/1 skipped，两端typecheck/build及Rust fmt/clippy/test通过。owner/CLI合同漂移与三项审计P2已修；全量暴露的C2真实单脚网范围扩大已按root成员数收窄，原指纹/通道/跨岛接线合同均恢复，父独立变异检出。最终exe隔离daemon/skill同步及打包插件保存候选plan已验，包路径`outputs/releases/0.6.3-beta.2/boardwise-0.6.3-beta.2-windows.zip`。命令、误设30分钟及临时目录关键字导致重跑的记录见[打包任务](../tasks/063_beta2_local_package.md)、`PROGRESS.md`与`evidence/release-063-beta2/README.md`。实际DSH普通用户端到端、service名称冲突和新三件套真机激活仍待验；保留61190旧daemon，不重画药箱或恢复eprj2/P145。
>
> **可靠性A/B源码验收（2026-11-18）**：A任务/资产路由已校正；B1新增`draw plan --layout candN.page.json`，一次真实合成编译的8份候选预检新增编译调用为0，父验97 passed、两因果变异先红恢复，见[B1证据](../evidence/draw-reliability-b1/README.md)。B2新增离线`boardwise_draw_plan`，父验50 passed，typecheck/build通过、两父变异先红恢复，见[B2证据](../evidence/draw-reliability-b2/README.md)。实际DSH安装及真机/发布验收的当前覆盖以上方beta 2记录为准；当时遗留owner与CLI合同漂移现已在集成批修复。
>
> **可靠性C1/C2：普通标签载线源码已修，限显式reserve的合成合同**。3件2岛复现了compile绿/plan拒DATA_BUS；现在复用原预留与carrier输出、长度筛选和既有文字避让反馈。父验核心70 passed、local/paired/service邻域10 passed，40/60长度、改网名、模块平移与默认关闭四候选指纹均有证据；三项父独立磁盘变异检出并copy+SHA恢复。另一个方向覆盖变异仍5 passed，已删去该无必要性证据的6行，不为留代码倒造测试。见[C证据](../evidence/draw-reliability-c/README.md)。未安装DSH、未真机或原生视觉验收，不签任意新电路布局完成。
>
> **试跑后候选小批（尚未开工）**：按用户反馈决定是否用原会话失败输入做离线接缝回放，分别记录普通与service路径；ESP_RXD/ESP_EN名称盒冲突仍是未验子项，不能用本组合成通过代替。原包未校准profile只作失败证据，不作落图资产；真实符号新模块与DSH端到端另按既有三关。默认reserve关闭保持兼容，也保留原默认路径的失败；未强开开关、重画药箱、重启P145或做eprj2绘图开发。详见[方案](draw-reliability-plan.md)；入口为[tasks/draw-line.md](../tasks/draw-line.md)与[docs/draw-assets.md](draw-assets.md)。

> **会话审计结论（2026-11-18，调查时暂停开发，现已授权分批修复）**：以下保留当时调查结果，实施以顶部当前派单为准。最新ZIP SHA `97101604…e3878` 含下午0.6.3-beta升级及晚间smartbox重绘；不能只按0.6.2解释。turn13落图耗103分32秒，约65分钟命令活动，至少21次plan无成功；每次CLI plan重新整页compile，同拒因六组重跑耗46分钟。初版绕开编译器逐脚桩+标签，后版用547A未校准profile（19/19、无texts），非P48真实几何；compile通过后plan仍exit5，reserve后又ESP_RXD压ESP_EN，没有三关合格成品。详情与逐调用计时见 [`evidence/dsh-session-37f77c38-audit/README.md`](../evidence/dsh-session-37f77c38-audit/README.md)。以下先前“只因插件没plan/apply”的说法不完整，不能覆盖这份新证据；代理实际上用shell调用了CLI plan。

> **当前交接（2026-11-18，P48 GND已修并保存）**：`test V4` 的 P48 `e4a3658c0417c139`，A2 2338×1652，547G **agent-adjusted reference replay** 的30件/31网/5NC/8岛已完成。原5枚0°保留，仅删除并重放23枚异常GND，现 **28枚全部0°自然朝下**。锚点/网及导线几何保留；94条非零线完整状态一致，12条零长线几何多重集一致（其中6条随旗重放换ID）。全工程43件250脚、P48 30件150脚逐脚0差异，完整宿主网表前后SHA完全相同。live lint **0E/0W/9I**；最终原生图已目检。再次保存返回saved:true，持久化仍仅 **saved_unverified**。DRC本轮未重跑，历史 **0 error / 206 warn groups，passed=false** 保留。证据见 [`evidence/v4-fullpage/HANDOFF.md`](../evidence/v4-fullpage/HANDOFF.md)。
>
> **DeepSeek 0.6.2 根因**：DSH 插件只注册离线 `boardwise_draw_compile` / `boardwise_draw_lint`，没有把自然语言/岛定义转成逐脚 CircuitSpec 的 `propose`，也没有 `plan/apply` 落画布链。会话包中的药箱整页编译是0候选；[`evidence/547/a/compile_full.log`](../evidence/547/a/compile_full.log) 的拒因是 GND 旗引线没有可用位置。会话转而用脚本手工组 CircuitSpec / PresentationSpec；插件自身既不从分岛补网表，也不把候选写回画布。源码证据在 [`dsh-plugin/src/draw-tools.ts`](../dsh-plugin/src/draw-tools.ts)。
>
> **根因与最小防复发**：547G4D校准脚本把原生GND负y bbox直接写入profile，而既有 `flag_glyph_box` 还会叠加Ground family 180°，与宿主自然姿态相反；正确canonical body在P30已有 `[-10.5,9.5,10.5,19.5]` 先例。`drawapply.load_library` 新增7行拒绝pinless Ground族负y body，明确要求输入适配；这是拒绝错误输入，**没有自动修正旧校准脚本或旧reference recipe**。聚焦 **81 passed**；主代理禁用检查变异 **2 failed/3 passed**、误推广全部旗族变异 **1 failed/4 passed**，cp+SHA恢复。
>
> **P48沿用边界**：沿P48已完成结果推进。待用户关闭重开 test V4 后按需只读核对持久化、分诊历史DRC警告；不要重画智能药箱、不要继续 eprj2 自动绘图开发，也不重启U1.18/P145。用户指出局部朝向问题耗时过长，后续按最小因果改动处理，不再扩成新系统或整页算法批。该修复当时的旧HEAD、未提交与daemon停止记录仅属历史；当前提交/待办以顶部为准，61190状态须使用前重新只读核对。
>

> **历史交接（2026-11-17，548P144后，P145现暂停）：当时整图下一首拒为U1.18名称盒**。P142 detour+foreign和P143多成员度量通过，P144把固定terminal glyph纳入port-columns的scene，C1.2消失；P142旧下一首拒断言已按证据更新为U1.18。完整整图仍无候选。证据 `evidence/548P144/README.md`。
>
> **历史生产与输入（不作当前路由）**：HEAD `108e42d`；drawcompiler SHA `976a4c2cad08804f994466419950e498aae2296a49de0b87536a72a7a653b2ea`，placement SHA `0674eb3842529fe280d06dc59c426f9eda7a1789cd0a1c35b86e89244596bb82`，pagecompiler SHA `28b2907d8904da9917a64d3015ae8fd37619313abfaf6a6ee3987e7763628e1c`（P142/P143/P144未提交）。输入 `evidence/548P125/circuit.full.g3c.pinmap.json` + `evidence/548P126/full.presentation.service-feedback.json`，尚无完整候选。
>
> **历史下一批（现暂停，不再派发） `tasks/548p145_u18_label_replay.md`**：先捕获U1.18 far/bbox/run、LED2_K/LCD_SCK channel与名称回放，不得删除名称、移动固定terminal、扩reach/GAP/预算/页框或恢复P124实验。完整30件未出候选，LCD automatic另列；P142/P143/P144实现未提交，未做真机/全量/apply。
>
> **资产索引**：先读 [`docs/draw-assets.md`](draw-assets.md) ；`evidence/draw-assets/manifest.json`为2026-11-17历史快照；此前整理仅经批准将12个可再生目录送回收站，记录见`evidence/draw-assets/recycle-log.json`。

> **P97/P98 人工 LCD 样例（2026-11-16）**：用户要求放入 EDA 后已亲手调整 `test V4` /
> `Schematic1` / `P47`，pageUuid `678f22680140b828`。原生源/几何/网表/PNG 位于 `evidence/548P97/`，
> `human-reference-summary.json` 是当前依据。10脚7网与源及调整前一致；C4 与 VCC 同行，C4.2 与
> J1.2 共地旗，J1.7 单独地旗，五个信号桩等长。**用户重申：打了旗标不再打网络标签。**
> P98已查明既有apply本来按此做，P97手动调用无条件传net才造成重复，临时脚本已改；无需另造规则。
> 只记人工参考，LCD automatic仍未完成；P108已确认旗标关系与样例一致。当时先推进 WiFi 三组页，LCD carrier/label 链列为当时后续待办；当前按顶部可靠性派单；禁止抄人工绝对坐标。

> **P108/P109 LCD automatic 检查点（2026-11-16，另一未完成子项）**：LCD仍未验收。P108独立复算确认候选逐脚10/10，且P47的C4.2/J1.2共旗、J1.7独立旗关系一致；拒因是五个信号名与10单位载体分离，以及C4目标姿态缺少原生图形。P109一次原编译追踪到五条载体均为10，输入`stubMin=40`；证据与精确下一步见`evidence/548P108-independent/README.md`、`evidence/548P109/`。WiFi三组页恢复后，再只读捕获40至10各档拒因和标签框变换，修原carrier/label链。旗标处不再加网络标签。
>
> **这份文件是路由，不是规格。** 它只回答三件事：这是什么项目、三条线现在各在哪、
> 干活要去读哪份权威文件。细节一律不在这里复制；两处说法冲突时以它指的文件为准。
> 写它的场合：从 Kimi Code 迁到 DeepSeek Harness（dsh）这类**换 harness**、开新会话、
> 或换人接手。口径是岳定的那句：**机制不搬，只搬记忆**。最后核对：**2026-11-19**（beta 2已本地提交并交付、未推送，等待用户本地DSH试跑；P48持久化边界仍见上文）。

> **P94/P96更新（2026-11-16）**：原S20分行已复用于严格声明的input链；父独立禁helper3红/去碰撞3红，cp+SHA恢复后63 passed, 1 warning in 60.23s (0:01:00)。drawcompiler当前c8c49503…29f07d，grammar618529e3…170c5。
> 只完成合成机制：四器件文字standoff均26.5、8脚5网；真实LED/ATTR旋转/视觉未验，独立地旗仍开放。P95只是静态方案。根已接管用户要求的LCD人工调整起点（P97）；子链不再派实施、不碰bridge，写锁已交根。证据`evidence/548P94/`、`evidence/548P96/`。
>
> **P90–P93更新**：生产方向真实一次build与P82全plan/change精确相同。P91仅更正LED内部直连语义，原build通过；父P93独立核对8脚5网、内部15/15直线与两负控，原计划4件6线1旗10attr。内部tap/name均已去掉。
> 父已亲看P93原生器件/实际ATTR诊断：文字仍同侧，共地旗仍待改，视觉未过。P94正复用原_part_texts的P38上下分行；P95只读设计独立链终端共享键。新输入`evidence/548P91/full.presentation.json`；证据`evidence/548P90/`–`548P93/`。未跑整页/真机/全量。
>
> **P82–P89更新**：LED方向机制已过独立验收，整图/视觉仍未完成。P87仅原grammar读取两条等臂input链的既有方向；父P89禁helper7红、放宽门控15红，逐轮cp+SHA恢复，聚焦96passed/1warning。grammar当前618529e3…170c5，drawcompiler仍81422c73…bd4a86。
> P82一次原topology内存方向验证可构建，P86独立8脚/5网及原module_plan一致；P84原生姿态/真实ATTR诊断被视觉拒收（文字同侧、内部多余抽头、独立支路共GND待改），未签LED完成。
> P83的pair None是首选无冲突时的no-op，不能说明无解或直接修复rail入口。LCD同网旗重叠仍开放。
> 证据：`evidence/548P82/`、`548P83/`、`548P84/`、`548P85/`、`548P86/`、`548P87/`、`548P89/`。P90正做一次生产版本真实输入消费；P88只读查语义输入与现有文字链。无新整页/真机/全量。
>
## 0. 历史状态通告（2026-11-16，不构成当前派单）

> 下列automatic探索状态保留追溯；P48已完成的参考与当前本地DSH试跑安排见顶部。不要据此重画药箱或恢复P145。

> **智能药箱 automatic 整图与 LCD automatic 均未完成。** WiFi 三组页最新状态及P111拒因见本文首段和`evidence/548P111/README.md`；P44 是人工关系参考，不是 automatic 结果。
> 548N2 是端口避让修复历史，不代表当前已通过；P44 是人工关系参考，不是 automatic 结果。LCD 当前唯一可接受的产物仍是 P47 人工参考，P108 候选不得当作 automatic 完成，细节见上方 P108/P109 条目。暂停历史见
> [`evidence/548P68_PAUSE/HANDOFF.md`](../evidence/548P68_PAUSE/HANDOFF.md)。
> 历史接续：P67 完整旗位轨迹证明 `_flag_anchor` 的零长兜底提前结束横向第一轮，
> 现有无转折第二轮未被执行。112 条记录=100 拒绝+12 零长终止，无未解释条目；
> P67 共跑 3 次原 base（前两次为工具缺陷，记录未掩盖），未扩预算或阈值。
> 根独立冻结回放仅延后零长兜底，J1.2 预留从无座变为 (-20,25)→(-80,25)，
> 恢复原函数后重现无座。P69 一次同变异整链进入 J1.7 半格旗位后继拒因，仍 built=False。
> 证据：`evidence/548P67/TOOL-V2.md`、`parent-zero-tail.json`、`evidence/548P69/report.json`。
> **P70 原旗位梯级零长终止已独立验收。P71 查明 J1.7 落格首墙是已知 LCD_BLK 标签盒；P72 全量传墙反证失败，未实施。**
> P71 冻结回放单补该墙能过局部落格，但 P72 整链传入全部五块 service_walls 会堵回 J1.2，不能把局部成功当修复。
> 证据：`evidence/548P71/README.md`、`parent-wall-replay.json`、`evidence/548P72/README.md`。
> P73 一次原 LCD compile 7.231567s，13 次布局尝试（基础6/二维6/拓扑1），0候选；独立输入/预算及两数据负控通过。
> P75原解释器单脚input/source可见载体机制已由P78独立两变异验收（6红/3红），恢复聚焦51passed；
> 当前source `81422c73…bd4a86`。真实LED一次compile仍0候选，拓扑输入载体撞邻脚，未完成。
> P76原生图验旧keys/UART/SWD：原闸及逐脚均过，KEYS因S20拒收，UART/SWD被原module_plan文字/载体冲突拒绝。
> P79 一次完整base反证：仅传lead bodies虽越过落格拒因，原readability仍因C4/J1.2两GND字形重叠报3hard，不得实施为完成修复。
> P81冻结复算证实：已定旗glyph只存入稍后返回的walls，没有传下一旗；同net_id又豁免20个重叠预留格。补glyph可防错但第二旗无座，P83只读评估原联合走廊能否复用。
> P80定位LED两输入同排35而stubMin40，无同向可行载体；signal family仍读power方向，忽略input=left。P82仅内存验证原grammar方向和完整构建，不改规格或生产。
> 不扩预算、不改输入、不另造算法。详见 `evidence/548P79/`、`548P80/`、`548P81/`；原生诊断限制仍见P76。
> P70 生产 drawcompiler `494e8e59…01c5f6`；独立变异 3红/4红，恢复聚焦 50 passed。
> P66 两派生姿态已独立核 4/4 脚、9/9 本体及两负控，只签 derivedPose 几何；
> `evidence/548P66/independent/README.md`。WiFi 既有局部通过不代表整页完成；
> P60 整页 pages=0、五模块无候选仍是最后整页读数。无新成功 LCD plan、无新候选渲染、无全量或真机。
> 主仓 HEAD 已由其他工作推进至 `504e766450453d5a10abef03c6f2263f29d910bf`；
> 混合改动保留，本线无 Git 写、移动删除或审查线修改。

> **P25–P28校准纠偏（暂停前历史）**：用户指出离线preview桩位与立创不同。
> P25证实P18/P24用的是`HOST4/R/C`合成库，不能代表真实ESP；548J混合库的电容body、ESP边界和旗几何
> 与P40有差异，不再作为真实WiFi编译输入。P44六件18脚与P40实测库的脚号/名字/端点/方向/长度一致；
> 根另用整数四分之一转从P40局部tip推回P44绝对坐标18/18、最大误差0，tip偏移5负控红。
> 读回state角与place API请求角不可混用；直接取负会制造40单位假误差，不据此改生产转换。
> P27独立审计并目看：svgpreview只画bbox和tip圆点，不画原生引脚线/极板/完整脚名，文字也不是宿主ATTR复刻。
> 该图只能作几何诊断，不能冒充立创最终外观或真实符号校准。
> P26已从P8物理full精确切出6件/7网/0NC/18端点（IO0保留J2.2与J2.3），六份profile完整复用P40；
> spec仅加native-attr，J2 below仍待验。根独立源对象核对及删IO2/错TX两负控均通过预期。
> P28以这组实测输入、原1170×825和默认预算做一次真实编译：18.9367s，ok=False/0候选。
> 主拒因为J2.1本地GND旗；cfg-right+50.5/cfg-left0一档到checker后4hard，首项导线穿实测旗本体。
> **P29/P30继续纠偏**：P40的GND.body是原生负y坐标，但既有`flag_glyph_box`要求先规范为正向后再加family180。
> P26原对象相等只证来源，不能替代格式适配。P29原checker不改，捕获到两只GND各自引线穿自己glyph，共4hard；
> 同plan仅内存规范body后4→0，单翻一旗仍2hard。P30新库只将GND.body转为[-10.5,9.5,10.5,19.5]，
> 原P40/P26测量保留；根独立全对象差分核对，并用原helper复原P44 rot0/180两bbox各四边0，未转换均差29。
> 新库`evidence/548P30/library.flag-contract.json` SHA203f520f…4b12a，转换provenance单列。P31正按原预算固定复编，
> **P31结果**：原compile ok=True/1候选/15.5844524s，但原LayoutPlan.load拒segment6同点(290,675)，
> 因此未继续最终逐脚/module_plan/视觉签字；不得把编译绿当通过。P32定位单支共同trunk退化且record端点有语义用途。
> **P33已过窄修复验收**：原追加口仅2行guard，保留record/非零原顶点；source现
> `f5d92aaf4d550dfe4e9b1ac9a9077fcb108755dbb49529a2e9b354fd166be425`。实施4文件18passed，
> 根独立两变异各3红3绿并cp+hash恢复，恢复P33/owner/layer/doc共78passed。
> **P37消费结果**：一次compile15.683s/1候选，原loader/往返成功，hard0/grammar0、18/18脚及7网分区一致；
> 根独立重算相同，VCC端点偏移1负控17/18缺J2.8。相对P31只少零长段，非零线/器件/旗/文字/标签不变。
> 原module_plan仍被543I拒：ESP_RXD文字盒(298,660.5)-(353,669.5)在carrier x365..405外，未生成可执行落图计划；
> P39只读查原标签链，不能缩网名或放宽守卫凑绿。P35独立视觉仍拒J2 below。
> P36证partTexts同块单侧无法表达S20上下分置，原native ATTR可分别移动；P38已授权仅原_part_texts对native+
> serviceGroups+声明core+无天然锚/显式侧的宿主优化S20，复用原单行font/碰撞/ATTR；已新增38行。
> 原码新测3failed/6passed；实施19passed，根独立关闭门控3failed/6passed、去碰撞2failed/7passed，
> 各cp+SHA恢复，恢复P38+owner/layer33passed/25.49s。额外宽旧回归180s超时，无汇总，不算通过。
> P38释放时source=6837ffff…55a58080，后续P45当前hash见下；未动core/schema/drawapply。
> P39已交只读侦察：原开放端口用stubMin40固定长度，55宽ESP_RXD放在线外，apply补长又撞IO0。
> P40首次pin-anchor方案被原dangling闸拒绝，已cp恢复上述hash；新测两红三绿保留，未签修复。
> P43只读确认既有两阶段合同：compile保留外置label盒，apply在足够长carrier内移动最终ATTR行。
> 下一最小修复只提前预留长名所需长度，不改far anchor/riding/线尾守卫；不能要求原Layout盒也已内置。
> P41/P42已从P44提取六份原生art，18条pin线内外端误差0、去12人工ATTR、留16嵌套脚字；
> 根独立原图18/18及提取树6/6复算/负控通过。两电容270度art对x镜像逐线相等且无字，限定证明见P42。
> P44已扩展原svgpreview可选同pose原生art；根亲看diff，独立去placement3failed/18passed、
> fallback15failed/6passed，各cp+SHA恢复，恢复21passed。source=f7750137…2d3e9f7，默认输出不变。
> P45原端口提前预留长名仅11行+保留stubMin语义，实施13passed，根独立两变异均2failed/3passed，
> 恢复29passed；compiler现5e4fc1fd7817c9dc36fccf52759c01f3a2a423b1d36f0d1a6e734666066ef038。
> P46真实输入仅移除J2 below，原compile一次9.098s/1候选，原loader/hard0/grammar0/18脚7网/原moduleplan全过；
> TX/RX各80，最终55宽实际ATTR原cover无问题且wire点列不变。根独立逐脚同样18/18、断VCC+1为17/18。
> **P46视觉仍拒**：右RST长465vsManhattan95，VCC最终host→rail595vs端点35，上绕y800/805；
> 宿主S20已修但不能用机器绿放行。P47独立原闸/18脚一致且视觉拒，大绕上廊下移5仍原闸绿可省20，
> 下移10撞旗名而红，两反证保留。用户明确指出左右电阻位置都有问题：以P44 RST近/EN远、左IO0靠宿主左上为验。
> P48静态证P46在(right40.5,left0)首绿返回，最大真实脚行尚未尝试；branch数组不承诺几何序，
> module.branchOrder原合同可表达近远但joint漏消费，单补顺序不能修左R6上下位置。
> P49最高真实脚行同时纠正上下/近远，但仍被J2.1 GND拒；P50/P51证左R6距host−50挤占旗位，
> 人工短肩也经原尺拒绝，不能靠加短挂修。P52只将左组原start_x沿本侧外推一个GAP，原seater/build
> 得R6(−70,+25)、RST(+50,+25)、EN(+120,+25)，hard0/grammar0、18脚7网、原module_plan/ATTR通过；
> 根独立断VCC+1得17/18、P53另上下文复算与亲看局部电阻/供电通过。六条宿主路径excess均0。
> **P52只是原内部候选探针（compileCalls=0），生产自动搜索尚未选中它**；原生器件art已复用，旗仍诊断。
> P54已补原列向外一档候选，生产SHA42ff7b25536f493aa2f54fff71ca67b39976f2607adebed0fbdba44472be7275；
> 根独立去列/断offset各3红3绿、重置budget1红，各cp+SHA恢复，恢复聚焦40passed/50.23s。
> 仅P6单预算test隔离行集合，全部跨variant/计数断言保留，不加生产调度特判。P54不改旧成功早返回。
> P55已消费显式近远意图与原真实行；source e6812c79e1b5d88d4ee0f1f54a9da7b8f76476c3c4d0dd72e243992c6cdd7f8b，
> 根独立禁preferred/禁preferred列各4红5绿、禁顺序拒绝1红8绿，cp+SHA恢复，恢复49passed/82.15s。
> P56用P55I spec（只增wifi branchOrder=[R5,R4]）一次原compile24.267758s/2候选，首选18脚7网/hard0grammar0/
> 原moduleplan最终ATTR通过；根亲看图与已验P52关系一致，左右电阻正确且无大绕线。
> P58已独立验两候选hard0/grammar0、18脚7网、原计划/实际ATTR及断J2.8负控；局部视觉通过。
> 两候选编译标签预留盒不同，分别生成的最终计划图形全等，未把预留盒相等当验收。
> P57同步边界文档+docclaims49passed。仍是离线automatic WiFi局部，未签整页/真机外观。
> P59完整10模块输入已备：30件31网4NC/120成员，五处spec意图变化与GND.body两个y适配；
> 根独立逆向差分及删IO2负控复算一致。P60一次原pagecompile102.658185s，1170×825/default24variants/max8，
> 显式沿原title_block_keepouts保护(460,10)-(1160,190)，未扩页框；pages0，模块层未过，不是页排布无解。
> keys6/led1/wifi2/uart2/swd2候选；mcu/lcd/imu/env/bmp0，详见evidence/548P60/report.json。
> 根独立13候选：WiFi同P58电阻关系/18脚7网/断端负控及原计划通过，keys/uart/swd原尺和逐脚NC过；
> LED虽8脚/hard0，原grammar2仍开放（单端LED1/2_K链承诺与label表达），不得签完整图。
> P63已提取18资产+引用P42一资产，根以profile端点/方向独立复算150脚最大误差2.842e-14、
> 内端+1/错误pose两负控红，亲看原生WiFi局部通过；P60其余5种缺pose未补，旗/字体仍诊断。
> P62已定位LCD预分组与最终foreign桩位分歧，根冻结原Router复算预尺50/终尺200，
> 删自GND仍200，仅去四条foreign reservation为60，实际GND长200；保留reach100和最终audit。
> P64已备份冻结源码，仅实施原标签早段前置/同状态消费；P65另域只静态侦察LED文法，未签修复。
> 当前用户质疑仍成立：实测profile校准不使bbox/圆点预览等同立创；最终外观须原生导出验收。
> P34证模块override只有sidePreferences，native/label全局传，railClustering未传入模块spec/预算；未接真实整页。
> WiFi局部已签，完整图仍未签；不再执行旧P22混合库脚本，不为此改shared/helper。
> 原校准纠偏阶段未改生产；随后P33/P38仅修改既有drawcompiler，未真机/git写。
> 证据：`evidence/548P25/profile-fidelity.md`、`evidence/548P26/INPUT-DELTA.md`、`evidence/548P27/renderer-audit.md`；
> 根独立脚位与输入读数在`.tmp_548p25_parent_checkpoint/pins-check.log`及`.tmp_548p26_parent/verify.log`；
> P28读数在`evidence/548P28/report.json`。本段文档钉48passed；18输入物理键可解析不代表最终连通已验。

> **同日继续 P13–P17（优先于下文较旧状态）**：目标仍是智能药箱automatic整图，用户明确要求有下一步就继续。
> P13原Router反证：VCC到共同轨内端被未来去耦旧座挡住，另一既有端点可达。P14仅接有限外端回退，
> 当前drawcompiler SHA `3e2f6d5045d2ee2aae25a924f04cb54014e0fa368687b6cc0232b7f56c049027`；
> 实施20passed，父独立两变异3红/1红并cp+hash恢复，恢复P14/owner/layer 28passed。
> 合成13脚/hard0，但父亲看供电有多余上绕，**视觉拒绝，不接真实页**；独立视觉继续复算。
> P17只读查未来组旧墙与最终路由几何。P15另已静态确认service builder漏现有native标签三helper，
> 真实spec未声明native；不得直接把P44人工文字锚冒充自然库profile。证据`evidence/548P14/parent/acceptance.md`、
> `evidence/548P15/recon.md`。无审查/shared改动、无新解释器、无git写/清理/真机/全量四线。

> **续进 P16/P17 后进入 P18**：P16 service尾部复用原native三收尾；hash
> `b1e11cf996011a910ad7abf53fd9711882bc8ada1362dffdff24f4698be6c482`，实施55passed，
> 父两变异2红/1红并恢复，恢复P16/owner/layer28passed。P14独立视觉最终拒绝，13/13、断供电12/13；
> P17最终所有真实墙下原Router量近端45（旧155），反序控制也完整build/13脚通过，不推广成去耦优先。
> P18仅让原host→rail消费口使用最终placement并替换具体旧run，正在实施；P19只读查native+serviceLayout载体接缝。
> 不写新builder/Router，不清墙；真实WiFi和智能药箱整页仍未验收。详见`evidence/548P16/parent/acceptance.md`、`evidence/548P17/recon.md`。

> **P18已过合成局部，继续P20（最新）**：source
> `98d2321efaa6d96d0f18b1183ce0e60b03c1df48f937c56ceda4e50ae2457793`；实施聚焦29passed，
> 父三变异4红/2红/2红均cp+SHA恢复，恢复owner/layer等29passed。原Router最终墙下替换旧155为唯一45，
> 独立13/13、断端12/13、追加旧路仍13/13但P3环红；父与独立视觉均通过合成局部。
> P19定位_open_far逐grid点未压缩，native载体把40桩末段误读为5；P20只复用原_compress保角/长度/端点，
> native+serviceLayout门控，在实施。P21只读准备P8整页输入路线。实际WiFi仍未编译新版本，整图未完成。

> **P20机制通过，P24局部示范在途（最新）**：hash
> `a10667e45603f915d8c4afb28d0ea198330604be47345d0b77bd279fc37e59ba`；实施35passed，
> 父变异2红/1红cp+SHA恢复，恢复P20/owner/layer28passed。旧P20合成图沿P6低行/below仍视觉拒绝，
> P24只把native载体接到已验P18合成结构；独立视觉过后才执行已准备`.tmp_548p22_wifi/compile.py`。
> P21证实10语义模块自动底件f19bf72c…58d8e46与P8静态30件唯一覆盖，不能换成g4辅助8岛。
> P23未找到自然文字锚；P44另有12条人工锚，仅agent-adjusted证据，不能直接塞profile冒充默认。
> 真实Wifi/整图仍未验收，目标持续推进。证据`evidence/548P20/parent/acceptance.md`、`evidence/548P21/full-input-route.md`、`evidence/548P23/text-source-audit.md`。

> **工程约束补充（岳 2026-11-14）**：后续绘制开发复用现有解释器与规则，控制模块耦合和
> 临时状态，新工具优先考虑 Rust，审查/绘制保持独立，代码可读性优先于省 token。
> 具体约束在 [`tasks/draw-line.md`](../tasks/draw-line.md) §1「工程实现约束」；
> Rust 工具与算法迁移仍分批，不由此另造绘制引擎。

> **同日持续推进 P5–P13（优先于下文旧中止状态）**：用户要求目标/下一步明确时持续推进，
> 当前goal仍是智能药箱automatic整图。P6已把真实宿主脚行接回原完整builder，P10让原页锚
> 消费已有record.frame/port边界；当前drawcompiler SHA-256
> `cfd563464cd94d5cdab0ad38b4ce0e883612ec63d363deb3b343ac7a7a1af77e`，Pspec仍F63B89AC…0BA60。
> P6四独立变异、P10两独立变异均红并cp+hash恢复。P10聚焦32passed；根恢复宽邻域
> 1failed/60passed，唯一原P宿主GND目标仍红。P6旧合成因功能名误作脚号及U1 below视觉拒绝，
> P11只修纯合成输入，9/9连通与断端负控、独立视觉通过；不得把旧拒图当基准。
> P8按P4连接做物理脚派生（30/31/4，120网成员），未采用g4的C3/R1/VREF+/CSB assumed改接，
> 输入证据 `evidence/548P8/INPUT-DELTA.md`。
> P12真实WiFi当前0候选：9个行组合已试，右组真实脚行均在座位器被host VCC→3V3 rail路径拒，
> 旧行完整build仍GND拒；不是漏试max/max，也未扩预算。证据 `evidence/548P12/compile.json`。
> 下一单缺口P13只读侦察原路由器固定host-facing rail入口与P44真实VCC走向，不另造router，
> 不跳host接线、不清文字。尚无真实WiFi新渲染/视觉，更无整页/真机/全量四线通过。
> 全部生产变更仅drawcompiler内部，未改审查/shared/bridge/CLI；混合未提交现场保留，无git写。

> **同日续跑 548P2–P4：局部推进，整图未验收。** P2 只修现有解释器的座位事务：失败不改输入，
> 成功才写回；源码现 hash `66A865339AFC785687535985B83D6D53D8D3103018D1BB0DC28800D8E2D7B4DC`，
> `presentationspec.py` 仍 `F63B89AC…0BA60`。聚焦43 passed；主代理独立变异分别3红/1过、1红/3过，
> 均cp+hash恢复；恢复后事务/owner/layer共28 passed。详情 `evidence/548P2/acceptance.md`。
> 岳明确裁定“以 P44 样例为准，按功能关系修正机械指标”：P1/P4不再统一判距离或跨度；
> P44实测265×25，因此下文§0.2/§0.6将“一字带/跨度”当根因的表述只保留为被推翻的历史判断，
> 不再指导实现。现行口径见 `docs/draw.md` §Baseline、`evidence/548P3/README.md`。
> P4派生输入 `evidence/548P4/circuit.full.p44.json` 为30件/31网/4NC，WiFi为6/7/0；
> 只把IO2从NC并入ESP_IO0，固件UART方向及其他字段未变，旧输入不覆盖。修正WiFi后编译仍0候选，
> 7个变体在现预算内均被J2.GND旗拒绝；不能据此断言所有布局无解。
> 最新文档/原P洞口组合1 failed/49 passed，唯一红项为宿主GND旗；O的两个真实目标仍strict xfail。
> **不重接旧行候选的漏字预检，也不扩参数续试。** 下一最小动作是设计行选择如何复用现有
> `_build_service_group_variant` 的最终结果，让旗/文字/座位使用同一生产判断；组间回退另批，
> 不新增第二套builder/router。未跑全量四线、未真机、无新渲染；未做git写、清理或审查线改动。
>
> **同日接手 548P：停止 / 未验收。** 用户已授权接下来两天绘制线开发；首批已复算边界与基线，
> 但行候选补丁未产出合法图，已 cp 恢复本节原hash，生产净零。恢复后聚焦
> **2 failed / 116 passed / 2 xfailed**，两红为新增 `tests/test_548p_service_rows.py`，不隐藏。
> 新反向实验推翻“只改row_y就够”：预检漏宿主文字，placement绿而build红；不是提前return截断。
> 下一批先补预检/生产墙集同源回归，不继续堆行参数；详见
> [`evidence/548P/README.md`](../evidence/548P/README.md)、`row-recon.md`。
> 原校准电路IO2=NC与P44共上拉不等价，不能冒称P44电气交付；两天推进顺序在
> [`tasks/548p_service_row_candidates.md`](../tasks/548p_service_row_candidates.md)。下文原通告保留为历史。

绘制线**中止**。本会话在 548K–548P 上工作一天，产出四批可用代码，但**没有交付一张能被
岳接受的图**；岳叫停并指示写这份交接。**本通告优先于下文各节"四批已落"的叙述**——那四批
代码可用，但它们的验收口径已被推翻，见 §0.3。

### 0.1 现在什么在、什么不在

| 项 | 状态 |
|---|---|
| 主仓 `E:\boardwise` | **混合未提交，未做任何 git 写**。绘制线因果文件只有两个：`drawcompiler.py` = `05139E85246A0735BC3A1F554742C37BDDCEA40C14C19E11FBD6FA8C0AA5EA3E`、`presentationspec.py` = `F63B89AC61C55FE11555C9BCC9131F87326C0AF501D4A16C652BAD22EC40BA60`。其余 `M`/`??`（`docs/bridge.md`、`docs/roadmap.md`、`tasks/038q*`、`tasks/shared-platform.md`、`connector/**`、`contracts/**`、`blocklib/parts.json.tmp`、`cases/`、`checkup/`）是他人或早前批次，本会话没碰 |
| 548K / 548L / 548M / 548N2 | 代码在，测试 8 文件 **93 passed**；能力真实，验收口径作废（§0.3-1） |
| 548N | 净零，已撤 |
| 548O（宿主旗房间预留） | **判废**，补丁存 `.tmp_548o_over/548o-wrong-layer.patch`，未合并；理由见 [`evidence/548O/README.md`](../evidence/548O/README.md) |
| 548P（组座位行候选） | **未完成**，实现在 worktree 被叫停，`drawcompiler.py` 已还原为 `05139E85…5EA3E` |
| worktree `E:\boardwise-wt-548o` | 分支 `drawing-548o`，HEAD `f23b801`，只读档案；岳指示"这批不解决就整删" |

### 0.2 唯一确定的结论：根因是一行代码

校准 WiFi 岛（6 件 + 2×4 宿主）在 1170×825 上只占 **370 × 45**（31.6% 宽 × 5.5% 高，
`whitespace_ratio=0.991`、`occupied_ratio=0.0089`）。三组 `serviceGroups`（岳裁 (b) 接受）
下整页 `ok=False`：`the pin J2.GND has no clear upright hang…`。

`drawcompiler.py:28985` `row_y = min([host_body[1]] + [全组宿主脚 y]) - GAP` —— **全组一个
标量行**；`:29023` 的候选生成器只沿 x 扫 8 档；`:29263` 的 `_joint_rail` 把"所有 pad 同一 y"
写成硬条件。三条独立实验（548O 补丁 / 页框翻倍 2340×1650 / 默认页测量）都指向它。

**下一步最小动作**：把 `row_y` 改成**每组的行候选**（宿主本行 / 上方 / 下方 + 组间
`taken rows` 表），行距量出来不造常数；一行一 rail 语义保留（同组 pad 仍同一 y）；门控只对
声明 `serviceGroups` 的页生效；判据用"这一行剩下的 rail 旗能不能落座"。侦察全文
`.tmp_548o_over/recon/SEAM_REPORT.md`（A/B/C 三方案 + 预测读数；结论选 A）。

### 0.3 这一天被推翻的三个判断（**别再照旧结论做**）

1. **"默认页 `8802d317cfae…` 逐字节不变"曾被当作验收线**（548M 起，548N2/548O 沿用）。
   它是 548L 自己产出的候选指纹，那张图当时**已被视觉闸判废**；该 spec 带
   `stubLaneReserve: true`，也不是"默认页"（开关全关是 `81557467…`）。
   **指纹不证明能看。** 规则：[`docs/draw.md`](draw.md) §Baseline。
2. **"548L 的 `not _service_layout_page(...)` 把 service 页排除了，所以三组页失败"** —— 错。
   `_service_layout_page`（`:5557`）要求 `serviceLayout.localSeats is True`，校准页只写
   `pinGap: 30` → 恒 False → 548L 一直生效；`if True` / `if False` 两测几何都不变。
3. **"缺的是预留"** —— 错，缺的是**行**。548O 因此判废（拒因只是搬家）。

### 0.4 本会话在仓库里留下的改动（要撤按此清单）

文档/测试（主仓，均未提交）：[`docs/draw.md`](draw.md) §Baseline（新增）；
[`tasks/draw-line.md`](../tasks/draw-line.md) §4（基准口径 + 勘误）；
[`PROGRESS.md`](../PROGRESS.md)（一条 548O + 基准勘误流水）；
[`tasks/TASKMAP.md`](../tasks/TASKMAP.md) / [`tasks/SCHEDULE.md`](../tasks/SCHEDULE.md) /
[`tasks/548_drawing_capability_ladder.md`](../tasks/548_drawing_capability_ladder.md)
（三处"逐字不变"→"仅指纹"）；[`tests/test_doc_claims.py`](../tests/test_doc_claims.py)
（两条新钉：基准口径、验收独立性）；新增
[`tests/test_548o_island_shape.py`](../tests/test_548o_island_shape.py)（两条 strict xfail 洞口）；
`.agents/skills/boardwise-draw/SKILL.md` + `.kimi-code/…`（新增 §5B 验收独立性，两份逐字节同步
`6954663EE024E8C5C616CBB3E77E53C34B8131C4CCB2FE52C69D5F810590BBA0`）；
[`tasks/548p_island_shape_recon.md`](../tasks/548p_island_shape_recon.md)（侦察任务书）。

证据：`evidence/548O/README.md`、`evidence/548O/spec-3groups.json`；`evidence/548L`、
`evidence/548M` 各加一个勘误块。临时：`.tmp_548o_over/`（读数、recon 报告、548O 补丁）。

### 0.5 环境坑（省一小时）

`E:\boardwise\.venv\Scripts\python.exe` **不能写** `E:\boardwise-wt-*`（`PermissionError` /
`WinError 5`；主仓内正常、系统 Python 正常）。在 worktree 里一律：

```powershell
$env:PYTHONPATH = "E:\boardwise-wt-548o\src;E:\boardwise\.venv\Lib\site-packages"
$env:TEMP = "E:\boardwise\.tmp_548o_pt"; $env:TMP = $env:TEMP
C:\Python314\python.exe -m pytest tests/<file>.py -q --basetemp=E:\boardwise\.tmp_548o_pt\pt -p no:cacheprovider
```

新 worktree 从 HEAD 切出**不含**主仓未提交的改动，须按 sha256 从主仓 `cp` 7 个 src + 8 个
548 测试 + 三份 evidence 输入（`evidence/548J/wifi-canvas/calibrated-*`、
`evidence/548M/presentation.rail.json`）。行为对等已验：默认页 `8802d317cfae…`、两组件
`ok=True`（`317E7FD773E76A66`）、三组件 `ok=False`（同一拒因）。

### 0.6 给下一任的一句

**四批能力是真的，方向是错的。先量岛的形状（半小时），再修那四个错误。** 在"图能看"之前
不要再写能力批次；判过一张图之前，不要用"逐字节不变"当验收。

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

## 3. 三条线的当前状态（核对日期 2026-11-13）

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
  不开工；541 R3/I/R4 已在隔离真实 DSH 0.2.2-rc.3 验收，桌面 profile 尚未部署；R6 资料获取、Rust
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
  connector、DSH、Rust 均通过。后续 541R3/I/R4 已在工作树实现（DSH 169 passed/1 skipped），
  隔离 DSH 0.2.2-rc.3 已验文件收据不解锁、initial/partial 解锁、跨目录欠账与 tool-gap；
  桌面 profile 尚未部署，任意宿主文件解析仍不覆盖；见 `tasks/541r3_dsh_stage_gate.md`、
  `tasks/541r4_dsh_error_result_fold.md` 与 `.tmp_541_live/session-4-events.jsonl`。
- **#87②⑤ 已落 `3d4a0d5`（`origin/main`）与 test V4 在线验收（2026-11-16，未发布）**：087E 的 `sch.readback`
  可选 value/mpn 与来源已实现，P43 三器件与公开 ATTR 双源一致、11 netflag 为 null；087F1/F2
  PCB viewport、`capabilities` 能力闸与 liveevidence 已接入，旧 connector 缺 flag 零 render。
  主代理 F1 74、F2 Python 242、connector 809，独立变异均先红后恢复；直接 render 两板目检、SVG
  具名拒绝；`review-evidence` exit0/capture.ok=true，`pcbImage.status=ok` 三板、livePcb ok、
  P43 焦点恢复，delivery 仅 datasheets=unavailable。V3/生产非空板未覆盖，#87 待提出人复验不关单。
  任务书 `tasks/087e_readback_value_mpn.md`、`tasks/087f1_pcb_viewport_render.md`、
  `tasks/087f2_pcb_evidence_integration.md`、`tasks/087f3_pcb_visual_docs_live.md`。
- **038Y5L/M/N 在线验收（2026-11-15/16）**：test V4 活动页拒绝、PCB1 与 PCB2 严格 DRC
  各 1 错得 RED/exit 2、旧目录拒绝和焦点恢复均完成；第三板天然 DRC=0 后新鲜 checkup 真跑，
  因工程自身 26 ERROR、缺手册/分诊与 boardsEmpty 得 INCOMPLETE/exit 3，不是 GREEN。
  DRC 清洁后的 checkup 编排已补齐；V3 与天然 GREEN 仍需合适授权样本。证据
  `outputs/review/038y5l/`、`038y5m/`、`038y5n/`，任务书同名 `tasks/038y5l_pcb_gate_live.md`、
  `tasks/038y5m_pcb_gate_checkup_live.md`、`tasks/038y5n_pcb_gate_third_live.md`。
- **038Y5O 与验收边界裁定（2026-11-16）**：V3 `test` 的宿主实测仍为 4.1.100，PCB1/2
  各严格 DRC errors=1，gate RED、checkup 未运行，Start Page 已恢复；只完成 `.eprj2` 路径验证，
  不是 3.2.x 宿主验收。岳确认没有天然 GREEN 可用板，天然 GREEN 不再本机必做、不为凑通过放宽规则；
  V3 宿主验收等待外部用户反馈，仍不宣称已验证。证据 `outputs/review/038y5o/`。
- **038Z1 真实三板骨架对拍（2026-11-15）**：两次导出哈希不同，只做语义对拍；离线/在线
  57 条自有 findings 一致，三板各 35 checks、findings 20/20/9。三板全 0 器件、铜层 2/0/0，
  不是非空多板或真实多文件守卫证据；NC/缺省 yAxisDirection 待样本。证据
  `outputs/review/038z1/differential.json`，任务书 `tasks/038z1_v4_live_archive_differential.md`。
- **038Z2–Z4 真实 eprj3 兼容核查（2026-11-16，EDA 4.1.100）**：`E:/LC Project/test V4`
  的 3 个 `.epcb2` 与 7 个 `.esch2` 只读合流；离线/在线均 exit 1、schema7，三板字段一致、
  60 条 findings 多重集一致。真实多文件正路径成立，但无库副本，三种 guard 未在真实文件上触发；
  17 个合成测试仅补充。NC 与缺省 yAxisDirection 样本均不存在；逐板 components 全为 0，
  真实非空多板仍未覆盖。证据 `outputs/review/038z2/differential.json`、`038z3/record-scan.json`、
  `038z4/board-scan.json`，任务书同名 `tasks/038z2_v4_folder_live.md`、`038z3_nc_yaxis_live.md`、
  `tasks/038z4_nonempty_multiboard_live.md`。
- **038Q 的 Q1–Q4 支撑批已完成各自范围（2026-11-11）**：库只读 `lib.cbb.search/get`、
  上游候选归一化、符号文件只读通路与单符号 elibz2 profile；AMS1117 单符号身份/几何已核对。
  四模块仍 candidate/unverified/notForDrawCompile。Q5 已补齐 AMS1117 三个电容的真实身份与
  elibz2 profile（`tasks/038q5_ams_passive_profiles.md`）。Q6 已读出 PAD 1/2/3/4，PAD 4 存在；
  但 datasheet 的 TAB 注记属于 TO-252，SOT-223 内部同网未证实，`U.VOUT*` 保持未展开
  （`tasks/038q6_footprint_file_read.md`）。Q7 已完成 SY8089 双身份与双 profile，5 脚映射均吻合，
  但几何和电气变体不同，不合并（`tasks/038q7_sy8089_identity_profiles.md`）。Q8 已把六份真实
  profile 收进 `blocklib/symbols/`，`tools/check_symbol_book.py` 可在无 outputs 的 clean checkout
  全量校验（`tasks/038q8_symbol_book.md`）。Q9 已按集中窗口方式补齐剩余13个身份，book 现有
  19份、覆盖四个候选全部19个唯一 device UUID（`tasks/038q9_remaining_identity_sweep.md`）。
  Q10 已让 SY8089 block 绑定七个真实 symbolRef（identityStatus=bound）；Q11 编译3候选且
  6/6逐脚一致，但输出侧四件未绑定、旗标缺失，主代理亲看首候选后**视觉拒收**
  （`tasks/038q11_sy8089_offline_pilot.md`），缺口交绘制线 `tasks/038q11a_buck_grammar_gap.md`。
  Q12 已把 CH340 五组通配显式落成12个物理脚并绑定七 part；复合脚号不拆，U.7 是唯一 NC，
  其余未声明脚进 unstatedPins，Rust core 56、主代理 Python 125
  （`tasks/038q12_ch340c_electrical_contract.md`）。Q13 两岛4候选11/11网及NC一致，但长自动
  网名压字、缺旗标且 D_ESD 未绑定，主代理亲看后视觉拒收（`tasks/038q13_ch340c_offline_pilot.md`）。
  **Q11/Q13 及 Q11A/Q13A 的 CBB 绘制相关工作已由岳裁定搁置（2026-11-12）**：保留现有离线
  证据，不再推进内部网语义命名、多脚ESD/短载体或旗标，不 plan/apply
  （`tasks/038q13a_ch340_presentation_gaps.md`）。book/模块仍是 candidate、不接 compile；
  CH340 的 EP 与 GND 关系缺厂家图纸。**038Q16–Q18 已打通原生块首轮垂直链（2026-11-15）**：
  project 搜索改用 `lib_Symbol.get(project)`，`sch.place_project_cbb` 得到真实 block_symbol、
  local/源身份与视觉/容器证据；`collect_block_instances` 三锚读出，普通读数不变，无位号假信号已修。
  Q18 用真实 PIN 证明 N1：已接块端口不再被 `arch-nrst-closure` 误报单成员网，转为
  `TRUNCATED_BY_BLOCK_PORT` 的 unproven；N2 普通真悬空仍报，N3 无块 findings 逐字不变。
  探针页全部回收，导入模块保留。V3、嵌套、非端点接触和块内部展开未覆盖；证据
  `evidence/038q16/live-report.md`、`evidence/038q18/live-report.md`。
  最终 Python **11226 passed / 26 skipped / 3 xfailed / 3 failed**，本批新增失败清零，
  三红均属绘制线未提交 548D/K/P；Connector 774、DSH 137/1、Rust 177/4，均通过，不称全量全绿。
  **038Q14 只读调查（2026-11-12）**：工作树新增 `lib.cbb.personal/libraries/export`，只负责个人库身份、
  其他可枚举库与身份核对后的 opaque `.epro2` 归档。真机个人库 UUID 为 `undefined`，系统库非空关键词、
  当前工程库及两个其他可读库均返回 0 个 CBB；故没有真实样件可归档，创建/放置/解析与端口规则继续停闸。
  未写任何库或工程内容，test V4 Connector 0.6.0 已恢复。恢复阶段曾读到 daemon 0.6.1；随后当前进程变为
  另一工作流拉起的源码 daemon，本批不再重启或冒称正式 exe 仍在运行；详见
  `tasks/038q14_native_block_bootstrap.md`、`evidence/038q14/report.md`。
  Q14 聚焦 94 passed，Connector 720、DSH 137/1、Rust 177/4；全量 Python 10902 passed / 26 skipped /
  1 xfailed / **1 failed**，唯一红项属于未提交绘制线 548D forced-topology，不称四线全绿。
  **038Q15 真实样件与幻影放置**：`晶振` CBB 身份和工程导出已核实，`META.docType=17`，但零 PIN、
  `boards=[]`，源页无块实例。`sch.place_cbb` 已实现并在 test V4 新 P43 试探；宿主返回 primitiveId，
  但组件清单/source/渲染均无块，动作正确报 partial。P43 已回收，源 CBB 未改；下一步需要岳用宿主 UI
  真实放置、最好带 PIN 的块实例。Connector 740、Python 邻接 176；证据 `evidence/038q15/live-report.md`。
  提交前挖洞的 portPins key、跨组重复脚、LF 与 catalog symbolRef 四项已修；最终完整 Python
  **10873 passed / 26 skipped / 1 xfailed / 1 warning**，Connector 691、DSH 137/1、Rust 177/4
  均通过（`.tmp_038q14_final/`、`.tmp_038q14_accept/`）。
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

**最新（2026-11-14，本机第二天）：548K/R、548L、548M 三个机制批落账；图仍判废，差距已定位到 placement 层。**
- **548K + 548K-R**：名字桩带先预留（`labelPolicy.stubLaneReserve`，默认关闭）。校准 WiFi 件不写开关
  → 几何 `f4f1c58c…`（与 548J §16 记录逐字相同）+ `draw plan` 拒绝；写开关 → `plan ok=True`、17 线/7 旗。
  第一版把行为挂在 `stubMin` 上，全量抓出 6 条老金标准红（534x×2、534、543c、548c4、548c6），已改成显式开关。
  最终 `drawcompiler=B965AC…1F66`、`presentationspec=667475…9BC8`。
- **548L**：两脚 `wire` 网的直线走廊在旗位**之前**预留（同一开关门控）。`ESP_EN`/`ESP_RST` 变回导线，
  `wired route not found` 归零，GND 旗从 `(320,680)` 让到 `(350,730)`。最终 `drawcompiler=AA86C1CE…FC5C2`。
- **548M**：`railClustering: {radius}` 把 GND 既有聚簇能力开到 power 轨（声明时该网取 `wire` 样式；
  053 sec.7 默认裁决未动；不碰 GND）。`3V3` 旗 **6 → 3**，与岳 P44 的三枚同构。
  全量第一轮暴露两条本批回归（`PresentationSpec` 位置参数被挪位、假 budget 无新属性）已修；
  另把 `test_548j_service_groups` 的"追加字段"pin 顺延一格（追加是契约允许方向，证据里写明未放宽）。
  最终 `drawcompiler=54364928…225818`、`presentationspec=F63B89AC…0A60`。
- **四线（每批各一轮全量）**：最终 **2 failed / 11066 passed / 22 skipped / 1 xfailed**，两条红均既有
  （`test_548d_panel_base` 的 panel 路由次数、`test_193_secrecy_hooks` 的 Windows 环境）；connector **740**、
  dsh-plugin **137/1**、Rust fmt/clippy/test 全过。**不称全绿。**
- **548N / 548N2**：548N 在独立 worktree `E:\boardwise-wt-548n`（分支 `drawing-548n`）试组级座位，
  **未达成、净改动为零**，前提被证伪（`IO0` 在左侧 → 正确形态是两组；且与 `test_548j_joint_seats.py:692`
  的"跨侧组=具名拒绝"互斥）。**岳裁 (b)**：接受两组声明（R4/R5 右、R6 左、去耦另组），不解冻那条负例；
  worktree 保留为**只读证据档案**（与 `boardwise-wt520` 同待遇，**不是当前实现**）。548N2 修好一个真缺陷并**已并入主仓**：`_joint_seat_group` 把
  `_reserve_open_ports` 的同一份端口房间当墙、命中沿宿主侧外退（≤8 档，全不退仍具名拒绝），
  同侧第二组推广到任意组；只对声明 `serviceGroups` 的页生效。最终 `drawcompiler=05139E85…5EA3E`、
  新测试 `tests/test_548n_group_seat.py=F78CC5A2…1A6A`，变异 M-N3 可复现原拒因。
  **三组真实页仍 `ok=False`**（新一层：`J2.GND has no clear upright hang`，座位/轨道/宿主旗三方争地），
  已按停止线停手，下一层最小动作见 `evidence/548N2/README.md` §4。worktree 保留为证据，不清理。
- **最终读数（5 批合并后）**：pytest 全量 **2 failed / 11070 passed / 22 skipped / 1 xfailed**；
  两条红均既有。connector 740、dsh-plugin 137/1、Rust 全过。**不称全绿。**
- **下一步（需岳裁）**：交接给过的唯一合规出路是「组级计划供现有标准 build/route/flag 消费」，
  不新建第二套 builder/planner；那是架构级改动，未获裁量前不开工。548D 自动整页/548E/547G 仍未完成或暂停。

**上一阶段（2026-11-13）：548J-A合同通过，B1联合座位停止交接，不能发布。**
- 可选 `serviceGroups` 的解析、封闭负例、页面切片与两项主代理变异已通过；岳人工P44及真实2×4 ESP-01S
  校准证据可复用。**B1目标测试22 passed、交接组合233 passed/1 skipped，但合成图仍有CFG_A/PWR大回环，
  主代理视觉拒收**；最近脚端子行等实验已回退，真实WiFi未消费，B1真机/独立变异/全量四线未做。
- 当前 `drawcompiler=11b2b3b9…`（B1前058a3032…），工作树混合未提交；不得git restore或直接续写独立builder。
  P44人工页/P42/P43/Board2不动，P45空白，daemon已停。**下一任先读 `evidence/548J/HANDOFF.md`**，
  清理或重设计由岳另裁；548D自动整页/548E/547G不因此关闭。

**上一阶段：P43 落真机、强制 topology 三岛与 LED 分压链族过；真实整页仍 BLOCKED。**
- B1前历史基线 `drawcompiler=058a3032…`、`drawapply=f713895f…`、`placement=326d96e9…`、`voltage_divider=2f67af65…`。
- **P43 automatic**：test V4 Board1 P43 `797f20b8a217b331`，三件/19 wire/11 flag，独立逐脚
  20/20 + 48/48 NC、lint 0/0/0、`saved:true` 但只记 **`saved_unverified`**；**DRC 开放项不隐藏**
  （209 WARN/0 ERROR，含 6 SHOWDANDLING、3 CHECKFLOATPIN、1 跨页 ATTRMATCHCODE，并新增 NRST WARN —
  复位脚未真实闭合）。P42 未动，本页是 MCU 单岛教学切片，不可投板。证据 `host-binding/p43/ACCEPTANCE.md`。
- **T1 强制 topology 三岛**：port-native 由真实 placement + topology 回放产图（base 兜底零调用），
  三岛 ok、crossings=0、主代理逐岛视觉签收；主代理 79 聚焦全绿、CH34/seat-first 邻域 171 passed；
  有效变异（coreless 投影关、同网重旗预占放开）先红后恢复，**「删除普通信号墙」是无效变异，不记成功**。
  baseline 仍带旧裸标签与 BOOT0 交叉，只记机器合同。
- **F1/F1A LED 分压链族**：多链只在「信号顶端 + `serviceLayout` + `stubMin>0`」启用（native-attr 门已撤，
  实测它让 bmp280/wifi 失候选）；LED 236×216.5、6/6 逐脚、14 测试 + 333/2 邻域、两项变异先红恢复。
- **整页仍 BLOCKED**：10/10 岛可出候选但页级 packer unsat，三列差 **41.5**；buzzer 岛、partTexts、
  panelGroups WiFi 上拉、native-attr 门、packer/页框/gap 调参**均已实测排除**；该方向随后进入548J，
  当前停止状态见上条交接，不能调 pinGap/缩字/降 40/扩页框冒充。
  详见 `evidence/548D/full-page/BLOCKED.md`；**不得写成 548D 自动整页或 548E 完成，547G 仍独立暂停**。
- 最终全量 **10973 passed / 26 skipped / 1 xfailed / 1 failed / 1 warning**（唯一红仍是既有 panel 路由次数，
  无新增失败，不称全绿）；Connector 740、DSH 137/1、Rust 177/4 均通过。日志
  `evidence/548D/host-binding/full-pytest-final.log` 与 `connector-final.log`、`dsh-final.log`、`rust-final.log`。

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
