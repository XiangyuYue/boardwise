# 554：552/553 派生基线集成验收（已本地提交 `14e8f39`，未推送）

## 来源

552 恢复多单元真实网表，553 按岳 2026-11-19 的裁决取消跨板共用位号 ERROR。主代理聚焦复验：

- 第一组：433 passed / 5 failed，失败在 `test_annotations.py`、`test_154_board_report.py`、`test_review_eval.py`、`test_069a_location_chain.py`。
- 第二组：661 passed / 10 failed，失败在 `test_041_cross_board_nets.py`、`test_041s2_interconnect.py`、`test_126a_pcb_review_plumbing.py`（规则正文指纹）。
- 其他已通过：552/553、040/040b/049/105/107 等 118 条；164/176/025d/185/200a/facts/injected/036/013 等随第一组通过；V4 facts、187b、131b–f、151/153/190/188a/162b/038r2/038u2/527c2/527d3/038f4/200b 等随第二组通过。

## 集成原则

1. 本批不改生产代码，不改签名 `reviewsets` 或任何 fixture，不改绘制线及他人未提交文件。
2. 历史签名 annotation 原样保留；测试必须明确哪些旧裁决被 552 证明为多单元、哪些被 553 改为非缺陷。不得删除原始记录、修改签名日期或假装历史从未存在。
3. `evaluate_annotations` 对旧签名集出现的 missed/cross-match 是旧裁决与新语义的真实差分，不能通过改评估器或过滤输入来造出旧的满分。
4. 报告总数只按逐规则读数更新：552/553 消失的只能是合法多单元和跨板重号；封装等其他 ERROR 必须保持。
5. `finding_chains` 的跨板旧报告兼容测试可在内存中注入一条 legacy finding，不能让生产重新发出 553 已取消的告警。
6. 041/041s2 的跨板网未证明、显式连接声明和按板 NetInstance 事实不变；只移除位号 ERROR 基线。
7. 规则正文指纹按最终 `rules/connectivity.py` 重新实测并记录原因，不修改指纹算法。

## 文件域与验收

A 域：`tests/test_annotations.py`、`test_154_board_report.py`、`test_review_eval.py`、`test_069a_location_chain.py`，`evidence/554/a/`、`.tmp_pt_554a_*`。

B 域：`tests/test_041_cross_board_nets.py`、`test_041s2_interconnect.py`、`test_126a_pcb_review_plumbing.py`，`evidence/554/b/`、`.tmp_pt_554b_*`。

两域均先保存旧断言与当前失败，再给出新断言的电气/合同理由；运行各自文件全集，独立 basetemp，不跑全量。若出现不能用 552/553 解释的红项，停止并报告，不能改成表面绿。

零 git 写、零 `rm/unlink`、零真实工程写、零发布。每域最多 25 步/25 分钟；交卷给实际命令、汇总、逐处新旧读数和未覆盖项。
