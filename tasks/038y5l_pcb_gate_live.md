# 038Y5L：`pcb gate` 在线只读验收

日期：2026-11-15。前置：038Y1–Y5 已落入 `d422e7a`，本批只验收既有命令，不重写闸门、不扩规则、不做 autofix。

## 1. 缺口与完成条件

038Y5 已有 fake bridge、真实 CLI 参数适配和归档证据，但 V3/V4 在线身份、严格宿主 DRC 与新鲜 checkup 联动未实测。本批回答：真实 Connector 上，命令是否按公开合同拒绝错误焦点，并在活动 PCB 上跑出一条新鲜的只读链。

完成不等于 GREEN。真实结果可以是 INCOMPLETE/RED；必须如实保留退出码、理由和证据。空板、缺资料或覆盖不足不得写成板级通过。

## 2. 真机身份与允许动作

唯一允许路由的工程：

-  friendlyName：`test V4`
- projectUuid：`1ea6af15c2b1bd8132b46a0648d4e149ced21066c4a6650bbffd40dc5e286a5b`
- 当前 instance：`inst-025631744-lpfqlw6m`（若重连变化，以新 `bridge status` + `doc.list` 重新核对，不沿用旧 key）
- 当前活动页：P45=`22d51b7d8e39974b`
- 目标现有 PCB：PCB1=`847fb91471c76cab`

另一个在线窗口“六层伺服驱动设计”及一切真实工程均为禁地；不得以其名字/uuid/instance 发起任何 bridge call。

只允许：

1. `bridge status`、指定 `--project "test V4"` 的 `doc.list`、`document.current` 与必要的只读几何/网表读取；
2. 为构造焦点，在已核身份的 test V4 内用 `doc.open` 切换上述现有 P45 与 PCB1；这只是验收准备，不由 `pcb gate` 自己调用，也不创建、保存或修改设计；
3. `boardwise pcb gate --project "test V4" --out <全新目录>`。

禁止：`doc.open` 到任何其它工程/文档、新建/删除页或板、修改图元、保存、autofix、`--skip-checkup`、复用旧输出目录、daemon/connector 热更或重启。若目标缺失或身份不符，停止，不寻找替代工程。

## 3. 验收序列

A. 活动页负例：P45 为活动文档时运行 gate。预期 exit 3 / INCOMPLETE，理由明确“活动文档不是 PCB”；不得执行 `pcb.drc_check` 或 checkup。

B. 活动 PCB 实跑：核对 test V4 后切换至 PCB1，再以新目录运行 gate。记录真实 DRC 参数、DRC checked/errors/truncated、checkup exit/report verdict/conclusion/coverage、gate verdict/exitCode。必须生成当次 `gate-report.json`；checkup 若运行，其 `DIR/checkup/report.json` 必须是本次新产物。

C. 输出防复用：对 B 的同一目录再运行一次，预期在任何 bridge/DRC/checkup 前拒绝；目录及旧报告不得被覆盖。

D. 焦点恢复：切回 P45，再读 doc.list 证明活动 uuid 恢复。整个序列不得产生设计写动作。

E. V3 只有在另一个窗口经 `bridge status` 明确显示为任务书逐字点名的 `test` 时才可另加；当前未出现则不启动、不替代、不宣称 V3 已验。RED/GREEN 若没有天然符合条件的活动 PCB，不制造设计缺陷来凑路径，保留既有 fake 覆盖并披露未做真机路径。

## 4. 证据与审计

- 长输出、命令记录和 gate 新目录放 `outputs/review/038y5l/`；一次性脚本放 `.tmp_038y5l/`。
- 汇总记录：每条命令、真实 exit、活动身份、DRC/checkup/gate 关键字段、前后 `doc.list`、输出目录复用拒绝及 daemon 审计中的动作序列。
- 若发现生产缺陷，先保留可复现原始响应并停止；修复另开一个小批，不能夹在本验收中顺手改 shared/CLI/rules。

## 5. 文件域与纪律

本批任务书唯一入库改动为 `tasks/038y5l_pcb_gate_live.md`；证据目录按上节，验收完成后另由主代理更新 TASKMAP/review-line 的对应行。不得修改绘制线及其未提交文件、fixtures、真实工程容器、daemon/connector。

零 git 写、零 push、零删除命令；废弃文件只能进回收站。只读真机与 shared/全量串行；本批不自动跑全量。若需代码修复，聚焦测试必须带独立 `--basetemp`，并另写公开合同、negative control 与回退方式。

## 6. 实际结果（2026-11-15）

- A 活动页负例通过：P45 上 exit **3 / INCOMPLETE**，`drc.ran=false`、`checkup.ran=false`，理由为活动 page 不是 PCB。证据 `outputs/review/038y5l/a-page-active/gate-report.json`。
- B 活动 PCB 实跑完成：PCB1=`847fb91471c76cab`，严格 DRC `ran=true / checked=true / errors=1 / items=1 / truncated=false`，gate exit **2 / RED**。按既有合同在宿主 DRC 已红时停止，`checkup.ran=false`；这不是工具执行异常，也不能写成板级 GREEN。证据 `outputs/review/038y5l/b-pcb1/gate-report.json`。
- C 同一输出目录复跑 exit **3 / INCOMPLETE**，在再次审查前明确拒绝已存在目录；没有新 checkup 产物。证据 `outputs/review/038y5l/c-reuse-command.log`。
- D 已切回 P45=`22d51b7d8e39974b` 并以 doc.list 复核。最终 bridge status 仍只显示原两个窗口，test V4 的 routed=8；未对另一窗口发起调用。证据 `outputs/review/038y5l/d-doc-list-restored.json`。
- 本批未修改生产代码、未保存/修改设计、未跑全量。V3 未出现逐字匹配的 `test` 窗口，未验；天然 GREEN 及“DRC 清洁后继续 checkup”的在线路径未覆盖，RED 之外路径仍由既有 fake 测试支撑。没有为凑路径制造板子缺陷或换一块板。
