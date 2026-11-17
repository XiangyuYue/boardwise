# 548P：组级行候选（绘制线，2026-11-14 接手）

## 1. 来源与完成条件

用户授权接手接下来两天的绘制线开发，特别要求绘制与审查可并行、不得耦合。
当前状态以 `docs/handoff.md` §0 优先；侦察已经完成，证据为
`.tmp_548o_over/recon/SEAM_REPORT.md`，不重复开展 548O 的旗房间预留路线。

本批只有一个缺口：声明 `serviceGroups` 的校准 WiFi 三组页，组级座位没有行候选。
原始拒因为 `the pin J2.GND has no clear upright hang`。目标是在既有 build/route/flag
链里消费组座位，三组页在 `0,0,1170,825` 产生合法候选，同组仍同姿、同端子行、共享本地轨。
不得增加另一套 builder/router/flag/page-anchor，不扩页框或放宽距离、碰撞与预算。

`evidence/548M/presentation.rail.json` **没有 serviceGroups**，其 P4 洞口属于默认链，
本批不改该链，不借此摘 `tests/test_548o_island_shape.py` 的第一条 strict xfail。

## 2. 输入与现场

- 分支 `main`，HEAD `f23b801aff30772c888f4e0ed129e73c4d741e35`；混合未提交。
- 开工 `drawcompiler.py` SHA-256：
  `05139E85246A0735BC3A1F554742C37BDDCEA40C14C19E11FBD6FA8C0AA5EA3E`。
- `presentationspec.py` SHA-256：
  `F63B89AC61C55FE11555C9BCC9131F87326C0AF501D4A16C652BAD22EC40BA60`。
- 两文件均已 cp 备份至 `.tmp_548p_session/`，不用 git 恢复现场。
- 源网表/校准符号：`evidence/548J/wifi-canvas/calibrated-wifi-island.circuit.json`、
  `calibrated.library.json`；三组声明：`evidence/548O/spec-3groups.json`。
- 明确分组沿用岳裁 (b)：R4/R5 靠右、R6 靠左、C8/C9 去耦；跨侧负例不解冻。

## 3. 文件域与解耦

算法域只允许 `src/boardwise/engines/drawcompiler.py` 的 service-group 座位邻域及
新增 `tests/test_548p_service_rows.py`。原有 shared、review、parser/model、CLI、bridge、
Connector、DSH、Rust、owner manifest、fixtures 与其他未提交改动均冻结。
证据进入 `evidence/548P/`，临时脚本进入 `.tmp_548p_*`。

边界证据：`evidence/548P/boundary-audit.md`。现有 owner 闸检查两线直接依赖，
本批另实测传递闭包；layer 闸不能单独代替 owner 闸。同属 engines 层不代表可以跨业务线 import。
不新建或清理 worktree，不碰 `.tmp_review_line` 与历史只读 worktree。

后续实施遵守 `tasks/draw-line.md` §1「工程实现约束」：复用既有解释器，
模块边界明确，避免堆积临时状态，可读性优先。新工具优先考虑现有 Rust workspace，
本批 Python 解释器修复不夹带语言迁移；审查线和 shared 合同保持各自文件域。

## 4. 验收

先用合成正例证明旧代码为红，再验证候选选择与失败试探不会污染 placed 状态。
主代理至少独立做两项生产变异，必须先红，再 cp 恢复并核 SHA-256；不改既有宽断言。
记录哪些测试在指定变异下仍绿，避免把不相关的默认链断言当成因果覆盖。

实现与图面验收分属不同上下文。编译、逐脚连通、视觉分开记账；必须打印
`docs/draw.md` §Baseline 的 P1 距离、P2 旗域、P3 绕行/穿越、P4 两维跨度。
同组共享短轨与三组编译成功只关闭本批条件，不自动代表 P1–P4、整页、真机或 548E 完成。
连续两轮同一拒因无新证据，或需跨文件域/放阈值，立即停止并留真实失败交接。

## 5. 两天的推进顺序

1. 11 月 14 日：复算输入与基线、锁定耦合边界，完成或证伪本批行候选；独立变异与三关验收。
2. 11 月 15 日：只按本批实测拒因派下一个单缺口批；质量目标仍是 P44 的 P1–P4。
   默认链 P4、真实整页、宿主落图分别记账，不自动串成一个扩大范围的实施批。

这是开发顺序，不是已完成两天工作的声明，也不创建后台定时任务。
git 写、移动/删除、真机与发布保持原有逐次授权要求。

## 6. 已实测基线

系统 `C:/Python314/python.exe` 可用；仓库 `.venv/Scripts/python.exe` 加载 `_ssl` DLL 失败，
不修改环境安装。系统解释器通过 `PYTHONPATH=E:/boardwise/src;E:/boardwise/.venv/Lib/site-packages`
读取同一代码与依赖。

点名 8 文件聚焦：**82 passed, 2 xfailed in 58.16s**，exit 0，
日志 `evidence/548P/baseline-pytest.log`。此选择与旧交接的 93 条组合不同，不冒称复现 93。
owner/layer：**24 passed, 1 warning**；双向跨线 import 内存注入均被 owner 闸拒绝。
后续结果以 `evidence/548P/` 独立验收报告为准；没有报告的验收项视为未做。

## 7. 本轮结局（停止 / 未验收）

实现未保留：修正错误flag helper后聚焦仍1 failed/27 passed，三组0候选；生产已cp恢复
开工hash。新增P两条回归洞口保持红，恢复后组合2 failed/116 passed/2 xfailed，
doc-claims45 passed。未跑全量四线，未真机，无新候选可签图。

新因果在 `evidence/548P/row-recon.md`：行搜索已有placement，去掉提前return无差异；
预检漏宿主文字，生产build加文字后才正确拒绝。下一最小动作改为先补预检/生产墙集同源回归，
不是继续扩行参数。完整收据和P1–P4读数见 `evidence/548P/README.md`。
