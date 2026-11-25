# 任务书：620 — hole570 修复集成与交接

## ① 前因后果

用户指定 `outputs/hole570/TRIAGE.md` 继续修。26 条 reproduced 分派为 602–619：602/603 grammar，604 V4 shared evidence，605/606 readability，607/608 多岛，609/609B 落点与 CLI，610 位号，611 patch-pin，612 身份，613 网格，614 文件名，615 shared HOME，616 输出回归，617 543d，618 历史重放，619 pits。原 G2-H1 由成对格式证据推翻，F2-07 由既有 584 关闭；suspect 不当实锤修。

本批只在各小批父验完成后做集成：核对 26 条覆盖、完整影响面、四线/合同/卫生、交接文档。任何新红先定位归属，不能为集成改宽测试或省略基线；本批新回归另开最小批，不把全量当侦察。

## ② 当前树状态

- 起点 HEAD/origin `76e08060ded403793bc6fb0eb64b38f9e140c765`；开工前重新 `git rev-parse` 与 status。
- 混合工作树中非本系列内容：`src/boardwise/core/circuitsemantics.py`、563 文档/测试、`tasks/review-line.md`、600/router/201f、依赖与临时文件，全部保留，不提交/还原/清理。
- 596 的最终全量为 `12 failed / 12743 passed / 26 skipped / 2 xfailed`，随后 600 修三条 owner 计数，**只剩 9 条已登记基线，12746 不是实测数**。本批不能沿用旧通过数或把其他线红项隐藏。
- 各批 `evidence/602`–`evidence/619`、`evidence/620/COVERAGE.md` 与 PARENT-ACCEPTANCE 是输入；若有未完成批，本集成不得启动全量或写“完成”。

## ③ 文件域与禁触清单

允许修改/新建仅：
- `evidence/620/`（集成报告、测试日志、最终覆盖账）
- `docs/handoff.md`、`docs/roadmap.md`（仅顶部当前路由）
- `tasks/TASKMAP.md`（602–620 条目）
- `tasks/draw-line.md`（顶部绘制线路由）
- 本任务书与必要 `tests/test_doc_claims.py` 钉（仅新当前声明冲突时）

禁止：生产源码、其它任务文档、PROGRESS/SCHEDULE（除非主代理另裁）、fixtures、历史 outputs/evidence、contracts、connector/dsh/rust 源码、他人未提交内容。不得更新旧提交状态为“已发布/全绿”，不删除临时文件，不做 git 写。

## ④ 交付物与验收

1. 逐条核对 COVERAGE：26 项都有生产修复/既有修复/格式反证与证据路径；F2-06、ch343 core、H2-03/04、29 条真机 pit 仍 suspect，未关闭。新生产 diff 仅限任务书范围，关键 hunk由主代理亲看。
2. 影响面先列：grammar/readability/netlist/group/edge/digest、page keepout/bbox/report/markdown、V4 facts/meta/pose、edit geometry/identity/output、HOME daemon/config、文档同步；crossView/unproven/NC/CBB 未覆盖须明说，不能拿全量找已知遗漏。
3. 代码稳定后，主代理串行跑一轮全量：

```bash
.venv/Scripts/python.exe -m pytest tests/ -q -n 4 --dist loadfile \
  --basetemp=.tmp_pt_620_full --durations=50 --durations-min=1.0 \
  --junitxml=.tmp_perf_pytest/junit-620-full.xml \
  > .tmp_620_full_pytest.log 2>&1
```

随后 connector `npm test && npm run typecheck`，dsh-plugin typecheck/test/build，Rust fmt/clippy/test；合同生成一致、`tools/check_repo_hygiene.py`、`git diff --check`。只有已定位并修掉的本批新红才允许一次完整复跑，第三轮先向岳说明。
4. 对 9 条基线逐名 diff，新增/消失分别列；其他线 600/router/201f 失败归 owner 披露，不陪跑、不冒充本批成果。若 543d 渲染产生候选，主代理必须亲眼目检；缺渲染/逐脚/视觉不得签该回放完成。
5. 文档写实际测试计数、各批变异和 SHA 恢复、未覆盖项、未提交/未推送/未部署状态；不生成发布包、不部署 daemon、不真机。
6. 文档类变异至少两项（错误测试数/错误覆盖状态）应让相应钉红，cp+SHA 恢复；生产变异已在各小批父验，不在集成期重复改代码。

## ⑤ 纪律与红线

零 git add/commit/checkout/restore/stash/push；禁 rm/unlink 和任何直删；不创建 worktree、不真机、不部署/发布。全量只一轮且 `-n 4 --dist loadfile`、独立 basetemp；不与其他全量并行，不擅自加 worker/skip/xfail。不得清理他人文件或把未跟踪等同可删。停止时写真实红绿和下一最小动作。

## ⑥ 预算与交卷格式

主代理亲验，文档可派一个 coder（最多 40 步/30 分钟）；全量耗时不计入子代理 30 分钟窗口但须后台带 timeout。交卷 ≤2000字 + evidence 文件，包含 26 项状态、完整命令与汇总、基线 diff、四线、合同/卫生、视觉、未覆盖与下一最小动作。缺任一未完成批或有未解释本批红项，只能写「停止/未验收」，不能写「完成」。

## 执行记录（2026-11-25，交卷）

- 26 条 reproduced 全部有生产修复、既有修复或格式反证；逐条账 `evidence/620/COVERAGE.md`，suspect（含 570-G2-H3）与 29 条真机 pit 不关闭。
- 首轮全量：**11 failed / 12953 passed / 26 skipped / 2 xfailed in 3667.49s**；两条本系列新增（590 API、534z 净距）定位后由 620B/620C–D 关闭，按 §④ 允许的一次完整复跑执行第二轮。
- 第二轮（最终，命令同 §④，basetemp `.tmp_pt_620_full_r2`、junit `junit-620-full-r2.xml`）：**9 failed / 12976 passed / 26 skipped / 2 xfailed in 1912.19s**，`newFailures=[]`，resolved 为 590 与 534z；剩余 9 条与既有基线逐名一致。机器摘要 `evidence/620/full-r2-summary.json`。
- 620B 父验 230 passed；620D 父验 36 passed + 两项生产变异 + 四候选编译/逐脚/当前视觉三关；620E 最终源码重放 P43/WiFi 一致。Connector 900、DSH 218/1、Rust 177/4 ignored；CLI 合同、repo hygiene、`git diff --check` 通过。
- 文档与声明钉在全量之后新增，后续只跑聚焦（`tests/test_doc_claims.py`、`test_workspace_conventions.py`、`test_repo_hygiene.py`）；**无第三轮全量计划**。全部改动在工作树，未提交、未推送、未部署、未发布；真机/V3/V4/容器/多板/CBB/crossView 未覆盖。
