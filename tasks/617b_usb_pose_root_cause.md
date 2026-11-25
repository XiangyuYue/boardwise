# 任务书：617B — 543d USB 姿态/标签链只读根因差分

## ① 前因后果

617 已停止并留证，不能照原 triage 修旗梯：543d 当前 R1/R2 rotation=0，历史 270；R2 值行堵 B4A9，强制 R2=270 只把拒因搬到 D+/D− 标签载体。旧 924a180 drawcompiler + 当前 placement/readability/textmetrics 仍 0 候选，说明根因在其它模块。

当前用户已明确要求全部修复，但下一步不能盲目把 R1/R2 强制 270，也不能只放宽文字墙。先做只读差分，确定是哪一项 PlacementInput/grammar binding/请求轴/座位选择变化使姿态与标签通道同时变坏，再给最小可修文件与验收预测。没有根因就不写生产补丁。

## ② 当前树状态

- HEAD/origin `76e08060ded403793bc6fb0eb64b38f9e140c765`；602–615 改动保留。
- `placement.py` 当前 SHA `0674eb3842529fe280d06dc59c426f9eda7a1789cd0a1c35b86e89244596bb82`，**工作树无未提交修改**；`ic_periphery.py` 当前 `830151ad7781fb776686c45b3613e0055d6964646243f5ad66fb70bf9860eff6`。
- `drawcompiler.py` 当前含 607，SHA `9ded2eb3…caf9`；617 未留下生产改动。
- 权威侦察：`evidence/617/REPORT.md`、`trace_flags.stdout`、`trace_forced_pose.stdout`、`old_engine_probe.py`。
- 固定输入同 617；历史 `evidence/543d/compile/cand1.page.json` 的 R1/R2=270。历史提交链可由 `git log 924a180..HEAD -- placement.py grammar/ic_periphery.py` 读取，禁止 checkout/worktree。
- 他人 563/review-line/router/201f 与临时文件禁触；不得改既有测试/fixtures/输入。

## ③ 文件域与禁触清单

本批**只读**，允许新建仅：
- 本任务书、`.tmp_617b/`、`.tmp_pt_617b/`、`evidence/617b/`（探针、历史源码临时副本、读数与 REPORT）

禁止：一切 `src/`、`tests/`、`contracts/`、`docs/`、`blocklib/`、历史证据修改；不修改 617 的探针结论。不得 git checkout/worktree/add/commit，不得删文件、跑全量、真机/bridge。若找到根因，只在报告建议下一批文件域，不直接实施。

## ④ 交付物与验收

1. **请求级对拍**：用同一 circuit/presentation/library 的 usb_c `_module_view`，捕获当前 binding.constraints、PlacementInput.chain/progress/lateral/poses/service flags，以及 R1/R2 的候选姿态与最终选择。不能只看最终 rotation；必须指出轴、角色或约束中哪个字段改变。
2. **历史隔离**：只读 `git show` 提取必要旧文件到 `.tmp_617b/`，以独立模块名/受控 `sys.modules` 跑，不污染生产。优先比较 924a180 与当前 placement 的同一请求；若旧接口不兼容，记录 AttributeError 是结构不兼容，不能当成“旧版也失败”。先做请求级差分，再对最可疑的 1–2 个提交做一次真实模块编译，不盲目全链二分。
3. **两个独立证伪实验**：例如仅恢复历史 placement 是否恢复合法候选；若不能，进一步分别检查 grammar/请求轴/文本度量。强制 R2=270 已知只搬拒因，不得重复当修复。每个实验保留真实拒绝/成功原文，不能只写推断。
4. 报告必须给：首个可证明的行为变化点（文件/函数/输入字段）、三种最小修复候选及各自影响面/预测读数、推荐下一批唯一文件域和既有 pinned 负控。若只能定位到一组可能项，明确未定案，不编造“根因行”。
5. 对照历史 4 候选与当前 7 变体首拒，记录 D+/D− 标签与 +5V 两层障碍，不能只修 +5V 就宣称恢复。下一批验收须包含完整真实 CLI、逐脚、渲染和 P1–P4。

## ⑤ 纪律与红线

零生产修改、零 git 写/移动/删除；禁 rm/unlink、checkout/worktree、全量、真机、部署。探针单进程，真实编译命令带 timeout，最多两个有信息增量的历史点；同一失败两轮无新证据即停。不得调大页框/budget/reach、改输入或强写姿态来制造“根因”。不得把旧接口不兼容误报成行为缺陷。

## ⑥ 预算与交卷格式

一个 coder，最多 40 步或 30 分钟；不派下级。交卷 ≤2000字 + `evidence/617b/REPORT.md`，依次给请求差分、两个实验原文、首个变化点、三候选与推荐下一批文件域、未证项。没有可复现根因只能写「停止/未定位」，不得直接转实施。
