# 任务书：601 — 集成证据与路线文档同步

## ① 前因后果

用户指定修复 `outputs/hole568/TRIAGE.md`。32 条 reproduced 已由580–595实现，580另收572-F五项SVG；598/599/600收口全量暴露的7项新问题，597/597B迁移9处HOME测试隔离。最终全量已完成：`12 failed / 12743 passed / 26 skipped / 2 xfailed in 3100.49s`，随后600的3条540 owner计数已单独修复（聚焦50 passed），故当前只剩9条已登记基线失败。**没有跑第三轮全量，不能把12746写成实测数。**

其他实测：Connector `900 passed` + typecheck；DSH `218 passed / 1 skipped` + typecheck/build；Rust fmt/clippy/test `177 passed / 4 ignored`；`tools.cli_contract` 一致；`tools/check_repo_hygiene.py` 与 `git diff --check` 通过。未提交、未推送、未部署、未发布，真机/V3/V4/容器/多板/CBB未覆盖，suspect未当实锤修复。

## ② 当前树状态

HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合工作树含563、566–579前批、580–600本轮及他人改动。`evidence/596/CHANGE-INVENTORY.md`、`FIXES-AFTER-R2.md`、`STOPPED-FIRST.md` 已存在；各批 `evidence/<批号>/` 有独立先红/变异记录。9条剩余基线失败名单与600 `REPORT.md` 一致。`src/boardwise/home.py` 是新shared根模块，owner计数165。

## ③ 文件域与禁触清单

允许修改：
- `evidence/596/INTEGRATION.md`（新建/完整替换）
- `docs/handoff.md`、`docs/roadmap.md`
- `tasks/TASKMAP.md`、`tasks/SCHEDULE.md`、`tasks/draw-line.md`
- `PROGRESS.md`（仅末尾追加一次）
- `evidence/601/`（文档diff与验证日志）、`.tmp_601/`、`.tmp_pt_601/`

禁止修改生产、其他测试、contracts、fixtures、前批证据和他人未提交hunk；不git、不删除、不跑全量、不接触bridge/EDA、不部署/发布。先cp备份文档并记录hash，变异/恢复只能cp+SHA。`PROGRESS.md` append后立即独立计数防双写。

## ④ 交付物与验收

1. `INTEGRATION.md` 汇总32条修复分组、真实读数、R2后7项收口、剩余9条基线名单、四线、合同/卫生、未覆盖项和公开边界：封签只自洽非作者签名；delivery恒unverified；S-11同时超过3处和2%；shared home动态读取；输出父目录缺失拒绝；测试隔离迁移。
2. handoff顶部当前路由更新为本议题，保留566–579历史；roadmap当前在哪加一条；TASKMAP在579后增加分组行（580、581、582/583、584–588、589/589B、590–592、593、594、595、598/599/600可合行），指向对应任务书和 `evidence/596/INTEGRATION.md`；SCHEDULE/draw-line顶部同步；PROGRESS只追加简短实际记录。
3. 文案不得写全仓全绿、已提交、已发布、真机通过或12746实测；明确“最终全量12失败后3条计数已单独修复，剩9条基线，未跑第三轮”。suspect与旧566–579未覆盖项分开，不把572后续A–E漏洞混入本议题。
4. 修改后运行：`tests/test_doc_claims.py tests/test_540_cli_draw.py tests/test_540_cli_shared.py tests/test_540_cli_review.py tests/test_owner_rules.py tests/test_599_route_compat.py -q --basetemp=.tmp_pt_601`，再跑 `tools.cli_contract`、`tools/check_repo_hygiene.py`、`git diff --check`，保存完整输出到 `evidence/601/`。
5. 主代理会抽diff，文档须与实际文件/证据一致，不能为读通顺隐瞒旧红或过程事故。

## ⑤ 纪律与红线

只做文档与证据同步，不修改生产，不删旧历史，不隐瞒首次停止/R2失败/新增问题，不skip/xfail，不跑全量、不真机、不git、不删除。若某项无实测依据，写未验证，不补造。

## ⑥ 预算与交卷格式

最多30步或20分钟。交卷列出修改文件、验证命令与完整汇总、文档中的剩余9条、未覆盖项和任何未解决不一致。
