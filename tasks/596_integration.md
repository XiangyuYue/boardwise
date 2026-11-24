# 任务书：596 — 568/569 修复集成与交付

## ① 前因后果

用户指定 `outputs/hole568/TRIAGE.md`，要求解决其中漏洞。总表 32 条 reproduced 已由 580–595 分批实现，suspect 未当作实锤缺陷。580 另收口此前 572-F SVG 五项及兼容钉。全量 Python 只跑本议题一次，命令已在后台启动，日志 `.tmp_596_full_pytest.log`，JUnit `.tmp_perf_pytest/junit-596-full.xml`。全量运行期间不得修改 `test_doc_claims` 读取的文档，避免输入漂移。

## ② 当前树状态

HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合工作树含 563、566–579 前批与他人改动，以及本轮 580–595。未提交、未推送、未部署、未发布。CLI 合同已一致，DSH `218 passed / 1 skipped` + typecheck/build 已通过。全量 Python 运行中，其他测试线必须等它结束后串行。

## ③ 文件域与禁触清单

全量运行中只允许写 `evidence/596/` 和本任务书，禁止修改 src/tests/docs/contracts/connector/dsh-plugin/tasks 的其他文件，禁止任何测试、bridge、git写或删除。全量结束后，路线文档更新另按结果进行；临时目录不清理，删除需另授权并只能进回收站。

## ④ 交付物与验收

- 变更清单 `evidence/596/CHANGE-INVENTORY.md`：按 580–595 列出洞、生产文件、回归、兼容边界和已知风险，区分 reproduced 与 suspect，不虚构测试读数。
- 全量结束后补 `evidence/596/INTEGRATION.md`：实际命令与完整汇总、失败名单/基线对照、Connector/DSH/Rust、CLI合同、doc claims、repo hygiene、未覆盖项。
- 文档同步应覆盖 handoff/roadmap/TASKMAP/SCHEDULE/draw-line/PROGRESS，明确“32 条已修但未提交/未发布、真机未覆盖、suspect未修”，不得写全仓全绿。

## ⑤ 纪律与红线

不做新实现，不陪跑旧基线红，不跑第三轮全量，不提交/推送/发布，不真机，不删除。所有结论必须能回到实际文件或命令读数；之前批次的转述要在主代理复验后才写成最终结论。

## ⑥ 预算与交卷格式

变更清单最多 2000 字，详细证据只指路径。最终报告按重要度列修复、真实读数、遗留风险和未覆盖项；若全量有本批新红，先定位修复再汇总，不隐瞒。
