# 任务书：595 / W-DSH — 完整 argv 同步哨兵

## ① 前因后果

hole568-C-01 已复现：`tests/test_dsh_plugin_sync.py` 只取 `const argv` 的首 token，`v4-facts→v4facts` 或 `--out-circuit→--write-circuit` 改名后哨兵仍绿。568-C-02 虽为 suspect（父路径被拍平），可与同一根因一并解决：直接以生产 `build_parser()` 的 argparse 子命令树比较完整路径和每个 option string，而不是扫描 `add_parser` 名字集合。C-03/568-B-04 的工具描述仍是 suspect，本批不扩。

本批只改测试哨兵与其反例，不改插件生产代码；现有14个工具真实argv已证合法，修后应保持绿。

## ② 当前树状态

HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合工作树含所有前批改动。`tests/test_dsh_plugin_sync.py` 当前 `_cli_commands()` 扫扁平名字，`_wrapped_commands()` 只取首token。`dsh-plugin/src/*.ts` 同时有数组字面命令、`argv.push('--flag',…)` 和 `{flag:'--out-circuit'}` 形态。`cli.py` 与 `commands/draw.py` 提供生产 `build_parser()`，可直接 introspect，避免第二套静态注册表。

## ③ 文件域与禁触清单

允许修改 `tests/test_dsh_plugin_sync.py`，新建 `tests/test_595_dsh_argv_sentinel.py`（如需隔离反例），写 `evidence/595/`、`.tmp_595/`、`.tmp_pt_595/`。禁止修改 dsh-plugin生产、CLI、其他测试、contracts、fixtures、前批证据；不 git、不删除、不跑全量、不接触 bridge/EDA。先 cp 备份并记录 SHA-256，变异只能 cp+SHA 恢复。

## ④ 交付物与验收

1. `_cli_commands()` 改为生产 argparse 树：每个完整命令路径（root/subcommand嵌套）对应 option_strings集合，保留父路径；不再用无父 set。
2. `_wrapped_commands()` 对每个插件argv提取完整前导非flag token路径，以及数组内所有 `--flag`、动态 `argv.push` 与 `{flag:'…'}` 字面flag，保留来源模块。spread `cli.prefix` 继续跳过，不伪造命令。
3. 主断言逐工具验证路径存在且每个flag属于该路径的option_strings；缺路径/缺flag都点名模块、路径和token。保持现有命令全部通过，review finalize专用钉不变。
4. 反例必须真跑：`v4-facts→v4facts`、`--out-circuit→--write-circuit`、把 `draw lint` 挪到 `edit lint`（或等效父路径变异）都检出；真实树无 missing。可用临时插件副本，禁止修改生产。
5. 运行：`.venv/Scripts/python.exe -m pytest tests/test_dsh_plugin_sync.py tests/test_595_dsh_argv_sentinel.py tests/test_doc_claims.py -q --basetemp=.tmp_pt_595`，以及 `cd dsh-plugin && npm run typecheck && npm test && npm run build`（若修改仅Python测试，仍验证插件无回归）。
6. 至少两个因果变异证明旧哨兵绿/新哨兵红，cp+SHA恢复；保存前后缺失项和真实工具计数到 `evidence/595/`。

## ⑤ 纪律与红线

只改哨兵，不通过改插件来迎合测试，不删弱断言，不把suspect描述当新功能，不跑全量pytest、不真机、不git、不删除、不skip/xfail。探针单进程、命令带超时；禁止用git restore/checkout。

## ⑥ 预算与交卷格式

最多30步或20分钟。交卷带真实工具/路径/flag计数、三个反例读数、Python与DSH完整汇总、两个变异恢复hash、未覆盖项。
