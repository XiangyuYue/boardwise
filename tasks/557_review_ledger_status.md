# 557：审查线台账提交状态校正

## 1. 前因后果与只读证据

岳的目标第 2 项。TASKMAP 状态定义为「已落=commit并推送，工作树=完成未提交」，当前多项已与事实不符：

- `git status -sb`：main 相对 origin/main **ahead 2**，即 `9f73ede` 与 `14e8f39` 均未推送。
- 552/553/554/555 的任务书、测试和差分合同已包含在 `14e8f39`；不是“工作树未提交”。
- 550B 的任务书和 connector 实例探针已包含在 `9f73ede`；不是“工作树未提交”。
- 087E/F（F1/F2/F3）五份任务书与实现包含在 `3d4a0d5`，`git branch -r --contains 3d4a0d5` 为 `origin/main`；可记“已落”，Issue 复验边界不因此关闭。
- 556/558/559 是当前新工作树批次，未提交、未推送；不冒充已落。

## 2. 修改合同

- `tasks/review-line.md`：550B、552–555 改“已本地提交 <sha>，未推送”，087E/F 改“已落 3d4a0d5”；测试、真机与未覆盖边界原样保留。
- `tasks/TASKMAP.md` 对应行同样处理，状态措辞不混用“工作树”。
- `tasks/550b_live_primitive_probe.md`、`552…555` 顶部/交付段的提交状态改为实际本地 commit；保留当时的混合树与未发布背景，历史基线不改写。
- 087E/F 五份任务书只改当前状态为已落 `3d4a0d5`；V3/生产非空板未覆盖、未关 Issue 等保留。
- `docs/handoff.md` 顶部增加一个**当前路由**：HEAD 14e8f39、ahead 2；552–555 与 550B 的本地提交归属；556 已完成父验、558/559 在途；当前目标不推送、不部署、不发布，真实设计与人工签核边界不变。旧 beta 2 段作为历史保留下移，不把“等待用户DSH试跑”继续当唯一当前动作。
- 如写 PROGRESS，只新增当前段，不改旧流水；为避免混合 hunk，本批可不改。

## 3. 文件域与禁触

仅限上述文档、`tasks/557_review_ledger_status.md`、`.tmp_557/`、`.tmp_pt_557/`。`docs/handoff.md` 有其他未提交绘制信息，只准顶部插入本批块，不重排或删除他人内容。禁改生产源码、绘制线、bridge、路线图稳定层、fixtures、真实工程、发布件。零 Git 写、零 rm/unlink、零部署发布。

## 4. 验收与交卷

- 搜索这些条目不再存在“未提交/工作树未提交”的当前态错误；不得把 14e8f39/9f73ede 写成已推送，也不得把 3d4a0d5 写成未提交。
- `pytest tests/test_doc_claims.py tests/test_workspace_conventions.py -q --basetemp=.tmp_pt_557`；必要时 `test_dsh_plugin_sync.py`，不改两份同步 skill 就不扩测试。
- 限定 `git diff --check` 通过；主代理逐项核 commit 归属与 handoff 当前路由。
- 一个 coder，≤30 步/20 分钟，≤1500 字，报告文件清单、实际测试汇总和未改边界。

## 557B 收尾待办（总集成时一次完成）

- `docs/review-sop.md:701` 与 `docs/pits.md:30` 的 #87 状态仍写“工作树实现”，需改为已落 `3d4a0d5`（origin/main）、未发布；同步 `tests/test_doc_claims.py` 的状态 token 与测试 docstring，历史在线验收读数不动。
- `tasks/TASKMAP.md` 的 550B 行尾仍有“未提交未发布”，与行首本地提交冲突，需删“未提交”只留“未推送、未发布”。
- 555 行末“CLI 合同快照待与绘制线集成”已在 556 生成并通过，需改为 556 已同步；559 新命令则由 559 收尾再核一次，不倒写成尚未做。
- 这些在 558/559 最终状态一起更新，避免连续多次改 handoff；当前文档测试 67 passed 已覆盖 557 本批，但不能据此忽略上述三处尾巴。

## 557 实际完成（560 收尾时补记）

557B 的三处尾巴已在 560 一次完成：

- `docs/review-sop.md`、`docs/pits.md` 的 #87 状态从“工作树实现”改为**已落 `3d4a0d5`（`origin/main`）、未发布**，`tests/test_doc_claims.py` 的状态 token 与两条测试 docstring 同步，历史在线读数（196764/93676/exit 0 等）一字不动。
- `tasks/TASKMAP.md` 550B 行尾只留“未推送、未发布”；555 行末改为“556 已生成同步”，559 新命令的合同在 560 再核。
- 556–560 的实际状态与读数写入 `tasks/review-line.md`、`tasks/TASKMAP.md`、`docs/handoff.md` 顶部。

状态：**工作树完成、未提交未推送**。
