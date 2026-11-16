# 本机验收记录：全量回归、DSH 部署与样本边界（2026-11-16）

## 全量 Python

命令：`.venv/Scripts/python.exe -m pytest tests/ -q -n 4 --dist loadfile --basetemp=.tmp_pt_full_20261116 --durations=50 --durations-min=1.0 --junitxml=.tmp_perf_pytest/junit-full-20261116.xml`，日志 `.tmp_perf_pytest/full-20261116.log`。

实际读数：**154 failed / 41 errors / 11331 passed / 26 skipped / 2 xfailed**，1945.34 s。未拿聚焦测试替代全量。

本批责任并已修复：

- `test_540c_contracts.py` 4 条：`contracts/cli/v1.json` 未随 protocol 更新，已用官方 `tools.cli_contract --write` 重生成，聚焦 **43 passed**。
- `test_review_stage_delivery.py` 的文档钉：SOP 3.0a 补齐“墙钟”“私有 API”“review-read 可复读不等于全局去重”，最终 **10 passed**；doc-claims 另 **52 passed**。

按上述修复扣除后，其余 **149 failed / 41 errors 待按 owner 复核**。这是归因后的待办数，**不是复跑读数**；不得写成全量已恢复全绿。剩余包括绘制线算法/页面、规则注册顺序、既有夹具哈希与既有基线差异，不在本批擅自修。

## 其他工具链

- Connector：**809 passed**，typecheck 通过。
- DSH：**169 passed / 1 skipped**，typecheck/build 通过。
- Rust：**177 passed / 4 ignored**，fmt/clippy/test 通过。
- 以上日志均在 `.tmp_perf_pytest/`，串行执行。

## DSH 桌面部署

- 隔离真实 DSH 0.2.2-rc.3 的两阶段验收已完成，但桌面安装被 `ERR_PNPM_MINIMUM_RELEASE_AGE_VIOLATION` 阻断。
- 已从自动备份恢复 profile 的 package.json/pnpm-lock，hash 一致；旧插件未变，未绕过供应链闸。详见 `tasks/541r5_desktop_deploy.md`。
- 桌面验收仍未完成，不能将隔离 profile 的结果写成桌面已生效。

## 后续样本

- V3 `test`/`test2` 工程与天然 GREEN 测试板；
- 真实 `NO_CONNECT`、SCH_PAGE 本体缺省 `yAxisDirection` 的坐标记录；
- `components>0 && copperLayers>0` 的非空多板；
- 重复 PCB、分歧库、相同库副本的真实多文件样本。

外部提出人复验、发布件安装/升级/回滚与正式发版不在本轮宣称完成。所有改动未提交、未推送。

## V3 `test` 补验（038Y5O）

- 宿主实测仍为 **4.1.100**，不是 3.2.x；本批只证明 `.eprj2` 工程路径。
- PCB1 与 PCB2 均为严格 DRC `errors=1 / items=1 / truncated=false`，gate RED / exit 2，checkup 均未运行。Start Page 已恢复。
- 天然 GREEN 仍未获得；需要清洁授权测试板。V3 宿主兼容性仍需 3.2.x 环境，不能拿该窗口冒充。

## V3 宿主环境裁定

岳确认本机及身边设备均已升级 V4，后续 V3 宿主兼容性等待其他用户反馈验证。该项不再作为本机验收动作；状态仍是**未验证**，不写成已兼容。

## 天然 GREEN 裁定

岳确认没有可满足当前严格审查规则的天然 GREEN PCB：即使成熟畅销产品也可能存在若干问题。天然 GREEN 不再列为本机必做验收项；不为凑通过而放宽规则或制造“干净板”。GREEN 的正向编排继续由既有 fake/合成测试支撑，真实环境保留 RED/INCOMPLETE 证据；后续若用户提供合格样本再补实测。
