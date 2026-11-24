# 任务书：600 — owner 清单计数同步 165

## ① 前因后果

596 最终全量 `12 failed / 12743 passed`。9 条是已登记基线失败，另外 `test_540_cli_draw/shared/review` 三条 owner manifest 测试仍断言164个生产模块。598 新增 shared `home.py` 并在 `contracts/module-owners.json` 登记后，`test_owner_rules.py` 已同步165并通过，但这三个兄弟测试仍钉旧数。只更新计数与必要说明，不改生产或owner结构，不跑第三轮全量。

## ② 当前树状态

HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合工作树含所有前批改动。`home.py` 已存在且 `contracts/module-owners.json` 含 `home.py: shared`；`tests/test_owner_rules.py` 已期望165。`tests/test_540_cli_draw.py`、`test_540_cli_shared.py`、`test_540_cli_review.py` 仍各有一处164计数断言。

## ③ 文件域与禁触清单

只允许修改上述三个测试文件的计数断言/必要注释，写 `evidence/600/`、`.tmp_600/`、`.tmp_pt_600/`。禁止生产、其他测试、fixtures、前批证据；不git、不删除、不跑全量、不接触bridge/EDA。先cp备份并记录SHA-256，恢复只能cp+SHA。

## ④ 交付物与验收

- 三处164改165，说明新增shared根home模块，不断言行为变化。
- 运行 `tests/test_540_cli_draw.py tests/test_540_cli_shared.py tests/test_540_cli_review.py tests/test_owner_rules.py tests/test_layer_rules.py -q --basetemp=.tmp_pt_600`，必须全绿。
- 反向变异把home.py owner行去掉，应导致owner/layer失败（只在临时副本或cp备份后执行并恢复），证明计数不是空转；保存到`evidence/600/`。
- 记录最终全量只剩9条基线失败的名单，不把这三条写成未解决。

## ⑤ 纪律与红线

只改三处计数，不改生产、owner映射或其他断言，不skip/xfail，不跑全量、不真机、不git、不删除。第三轮全量不启动。

## ⑥ 预算与交卷格式

最多10步或6分钟。交卷带三处diff、指定命令完整汇总、反向变异与恢复hash、最终剩余9条基线名单和未解决项。
