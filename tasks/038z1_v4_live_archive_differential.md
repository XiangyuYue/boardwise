# 038Z1：test V4 真实三板归档的在线/离线对拍

日期：2026-11-15。前置：038P/P1 已支持 eprj3 多 PCB 与多文件合流守卫，但真实证据只有空板/合成守卫。本批只取得当前 test V4 的真实整工程归档，并用既有 checkup 在线、离线链各跑一次，如实划定兼容边界。零生产代码改动。

## 1. 样本与身份

唯一允许路由的工程：

- friendlyName：`test V4`
- projectUuid：`1ea6af15c2b1bd8132b46a0648d4e149ced21066c4a6650bbffd40dc5e286a5b`
- 当前活动页：P45=`22d51b7d8e39974b`
- doc.list 当前列出 5 个原理图页与 3 个 PCB 文档；是否非空、是否有铜层必须以本次归档实际读数为准，不预设。

另一个在线窗口“六层伺服驱动设计”及一切真实工程禁碰。不得路由到该窗口，不得打开/保存/修改任何设计，不为制造非空板而放置器件。

## 2. 只读步骤

1. `bridge status` + 指定 `--project "test V4"` 的 `doc.list` 再核身份。若工程名/uuid 不符或目标消失，停止，不替代。
2. 用既有只读动作取整档：
   `boardwise bridge call --project "test V4" --action sys.get_project_file --params '{"fileType":"epro2"}'`。
   原始响应与解码后的 `.epro2` 只放 `.tmp_038z1/`，不入库；解码复用 `cli._archive_bytes()`，校验 ZIP 头、字节数和 SHA-256。
3. 离线：`.venv/Scripts/python.exe -m boardwise.cli checkup --file .tmp_038z1/test-v4.epro2 --out outputs/review/038z1/offline`。
4. 在线：`.venv/Scripts/python.exe -m boardwise.cli checkup --project "test V4" --out outputs/review/038z1/online`。
   两条均用当前源码，真实 exit 0/1/2/3 原样记录；exit 3/incomplete 不是工具失败，也不是板级通过。
5. 从在线 report 的 `attempts[]` 找 `tier=project-file` 的 bytes/sha256，与手动归档比对。相同才可声称“同一字节对拍”；若宿主两次导出字节不同，只准做语义差分并明确哈希不同，不得涂成同档。
6. 对拍两份 report 的 PCB 逐板 `title/boardUuid/components/copperLayers/checksRun/findings`、crossView、`completion.coverage.pcbReviewMissing`、`evidence.channels.archivePcb`、schema 和 exit。findings 用稳定身份多重集，不因数组顺序差异制造假回归。在线额外通道/证据字段应按来源解释，不要求整份 report 逐字相同。
7. 当前活动页/焦点不被本批切换；完成后 doc.list 再读一次证明仍是 P45。

## 3. negative control 与边界

- `review --view pcb` 的多板拒绝合同不变；本批不把它改成偷偷选择 boards[0]。
- 重复 PCB 拒绝、分歧库拒绝、相同库副本允许只由既有合成 eprj3 多文件测试支撑；本次单文件 `.epro2` 不触发这些守卫，不能声称真实多文件证据。
- 三块 PCB 若全为 `components=0 / copperLayers=0`，结论只能是“真实三 PCB 文档骨架 + 库文档共存 + 逐板路由”，不是“真实非空多板审查”。
- 当前工程走 `.epro2` 导出，不含 eprj3 `.esch2` 的缺省 `yAxisDirection` 观测面；真实 NC 也无已证实样本。这两项保持开放。
- CBB 导入形成的额外 BOARD 只按宿主文档事实报告，不解释成工程师刻意设计的多板产品。

## 4. 后续切片

- 038Z2：真实 eprj3 文件夹且 `pcb/` 至少两个 `.epcb2` 的合流守卫验证——等待样本。
- 038Z3：真实 NC + 缺省 `yAxisDirection` 样本——等待样本。
- 038Z4：至少一块 `components>0 && copperLayers>0` 的真实多板逐板规则证据——等待样本；不得借其它真实工程补。

## 5. 文件域与纪律

本批入库文件只有本任务书；真实归档和一次性输出在 `.tmp_038z1/`，报告在 `outputs/review/038z1/`。完成后由主代理把实际边界同步到 `docs/v3-v4-boundary.md`、TASKMAP/review-line 的对应行，不碰绘制线 hunks。

零 git 写、零 push、零删除命令、零部署/热更/daemon 重启、零设计写入。真机串行，不自动跑全量；如需修代码，停止本验收并另开 shared/CLI 小批，先写公开合同、两个消费者、回退和 negative control。

## 6. 实际结果（2026-11-15）

- 手动归档 117295 B，SHA-256 `cdfc34ad39b8556308df3411395990f2a8da416c597bfdaf4d1ad75c79d64f08`；在线 checkup 的 project-file 归档同为 117295 B，但 SHA-256 为 `fd4f94162c3f03d2816920984445fb24d990906afba1e7e51b688d422a3351f0`。因此本轮是**两次导出的语义对拍**，不是同一字节对拍。
- 离线/在线均 exit **1**，schema 都是 `boardwise.checkup/7`，两份自有 findings 各 57 条，完整多重集一致。在线另有宿主 ERC/DRC；离线 `hostPcbDrcUnchecked=true` 是未查披露，不与在线额外证据强行抹平。
- 三块 PCB 的 title/uuid/components/copperLayers/checksRun/crossView 与 findings 顺序、完整内容均一致：PCB1=`208fca9353e38230`（0 器件、2 铜层、35 checks、20 findings）；PCB2=`47aeb1b4f9e9eecf`（0、0、35、20）；晶振=`99b8a7f883a07ca6`（0、0、35、9）。`pcbReviewMissing=false`，archivePcb 的 status/artifacts/errors 一致。
- 证据：`outputs/review/038z1/differential.json`、两条 `*-command.log` 与各自 report；归档只在本机 `.tmp_038z1/`。最终 doc.list 活动文档仍为 P45=`22d51b7d8e39974b`。
- 归档文档计数为 PCB 3、FOOTPRINT 9、DEVICE 20、SYMBOL 20、SCH_PAGE 5（另有 BOARD/SCH/CONFIG 等），证据 `outputs/review/038z1/archive-documents.json`。本轮证明的是**真实三 PCB 文档骨架、真实库文档共存、逐板规则执行及在线/离线语义一致**。三块板全部 0 器件，不能写成真实非空多板；PCB1 的 2 铜层不等于有器件。真实多文件守卫、真实 NC、缺省 yAxisDirection 仍未覆盖。
- 未修改生产代码、未跑全量、未写设计、未切换焦点；038Z2–Z4 继续等待对应样本。
