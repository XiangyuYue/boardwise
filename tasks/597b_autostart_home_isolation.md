# 任务书：597B — autostart 最后一处 HOME 隔离

## ① 前因后果

597 已迁移8处旧式 `setattr`，主代理复跑 `131 passed`，真实审计 SHA/mtime未变。全仓扫尾发现 `tests/test_157_auto_daemon.py:157` 还用字符串模块路径 `monkeypatch.setattr("boardwise.bridge.daemon.BOARDWISE_HOME", tmp_path)`，同样不再隔离动态HOME。必须补上，才能安全重启全量。

## ② 当前树状态

HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合工作树含所有前批改动。`tests/test_157_auto_daemon.py` 的 autouse fixture `_auto_start_on` 负责 autostart 和临时home隔离，只有这一行需要改为 `monkeypatch.setenv("BOARDWISE_HOME", str(tmp_path))`。生产587不动，真实审计文件当前 SHA `a4c7ee1d…`、mtime 01:09:14。

## ③ 文件域与禁触清单

只允许修改 `tests/test_157_auto_daemon.py` 的这一行及必要注释，写 `evidence/597b/`、`.tmp_597b/`、`.tmp_pt_597b/`。禁止生产/其他测试/fixtures/前批证据；不git、不删除、不跑全量、不启动真实daemon/EDA。先cp备份并记录hash，变异只能cp+SHA恢复。

## ④ 交付物与验收

- 将该行改为setenv，保留fixture其它行为与所有测试断言。
- 运行 `tests/test_157_auto_daemon.py tests/test_587_daemon_home.py -q --basetemp=.tmp_pt_597b`，全绿；真实audit SHA/mtime前后一致。
- 全仓 grep 不再残留旧式 `monkeypatch.setattr(...BOARDWISE_HOME...)`（生产模块动态视图除外）。
- 若改回旧写法，用只读路径或mock证明不隔离；不得在真实home写。恢复后hash一致，证据落`evidence/597b/`。

## ⑤ 纪律与红线

只改这一处隔离，不改生产或其他断言，不skip/xfail，不git、不删除、不跑全量、不真机。若失败停止交证据，不扩域。

## ⑥ 预算与交卷格式

最多10步或6分钟。交卷带diff、聚焦汇总、真实home前后hash/mtime、grep结果、恢复hash和未解决项。
