# 038Y5M：`pcb gate` DRC 清洁后的在线 checkup 验收

日期：2026-11-16。前置：038Y5L 已在 `test V4` 的活动 PCB1 上实测严格宿主 DRC `errors=1`，按合同 gate RED / exit 2 且未跑 checkup。本批只补“宿主 DRC 清洁后继续运行新鲜 checkup”这一条既有路径，不重写闸门、不扩规则、不制造设计缺陷、不做 autofix。

## 1. 身份与边界

唯一允许路由的工程：

- friendlyName：`test V4`
- projectUuid：`1ea6af15c2b1bd8132b46a0648d4e149ced21066c4a6650bbffd40dc5e286a5b`
- 本批开始时 instance：`inst-015320415-gqzhsc3h`（重连后以新的 `bridge status` 和指定工程的 `doc.list` 重核）
- 开始时活动页：P43=`797f20b8a217b331`
- 本批目标现有 PCB：PCB2=`523016c3df10ea8d`，parentName=`Board2`

另一在线窗口及一切真实工程禁碰，不得以其名字/uuid/instance 发起调用。只允许 `bridge status`、指定 `--project "test V4"` 的 `doc.list`/`document.current`、为构造焦点在上述 P43 与 PCB2 之间 `doc.open`，以及 `boardwise pcb gate --project "test V4" --out <全新目录>`。`doc.open` 只切换焦点，不创建、保存或修改设计。

禁止：路由到其它工程或文档、新建/删除页或板、修改图元、保存、autofix、`--skip-checkup`、复用旧输出目录、daemon/connector 热更或重启。若身份不符或目标缺失，停止，不寻找替代工程。

## 2. 完成条件

1. 活动 PCB2 上运行 gate，记录真实 DRC 参数、checked/errors/items/truncated。
2. 若 DRC 清洁，必须证明 checkup 真正运行，且 `DIR/checkup/report.json` 是当次新产物；记录其 exit、completion.verdict、report.conclusion、coverage 与 gate verdict/exitCode。空板/覆盖不足导致 INCOMPLETE 是合法实测结果，不得写成 GREEN。
3. 若 DRC 非清洁，保留 RED 原文并停止，本路径不能宣称完成。
4. 结束后切回 P43，并以指定工程的 `doc.list` 证明活动 uuid 恢复。全程不得产生设计写动作。
5. V3 与天然 GREEN 不在本批伪造：没有逐字点名的 `test` V3 窗口或天然合格非空板，就继续披露未覆盖，不用其它工程替代。

## 3. 证据与纪律

长输出与当次 gate 目录放 `outputs/review/038y5m/`，一次性脚本放 `.tmp_038y5m/`。记录每条命令、真实 exit、前后身份、DRC/checkup/gate 关键字段和 daemon 审计动作序列。

本批唯一计划入库文件为本任务书；证据默认本地。不得修改生产代码、绘制线及其未提交文件、fixtures、真实工程容器、daemon/connector。零 git 写、零 push、零删除命令；废弃文件只能进回收站。只读真机与全量串行，本批不自动跑全量。若发现生产缺陷，保留响应并停止，修复另开小批。

## 4. 实际结果（2026-11-16）

- 已核对 `test V4` 的 projectUuid 与 PCB2 uuid，活动文档切换响应 `matchesRequest=true / type=3`，`document.current` 确认为 PCB2。
- gate 实跑 exit **2 / RED**：严格宿主 DRC `ran=true / checked=true / errors=1 / items=1 / truncated=false`，按既有合同 `checkup.ran=false`。因此本批没有触发 DRC 清洁后的 checkup，不能把本路径记为通过。证据 `outputs/review/038y5m/b-pcb2/gate-report.json`、`b-gate-command.log`。
- 已切回 P43=`797f20b8a217b331` 并以指定工程 `doc.list` 复核活动 uuid；最终 `bridge status` 也显示该页。没有创建、保存或修改设计，没有路由另一窗口。
- V3 窗口仍不存在；PCB1 与 PCB2 都是宿主 DRC 1 条错误，当前没有任务书授权且天然 DRC 清洁的非空测试板。V3、天然 GREEN 和 DRC 清洁后的 checkup 在线路径仍未覆盖，不为凑路径制造缺陷或改用真实工程。
