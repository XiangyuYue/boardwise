# 任务书：597 — 动态 HOME 的测试隔离迁移

## ① 前因后果

587 将 daemon/autostart 的 HOME 改为调用时读取后，旧测试若仍 `monkeypatch.setattr(daemon_module, "BOARDWISE_HOME", tmp_path)`，生产路径不会再读这个赋值，审计可能落到真实用户家。主代理因此停止了首次 596 全量（约 21 分钟、日志约 91%，未完成）。目前真实 `~/.boardwise/audit/2026-11-24.jsonl` mtime `2026-11-24 01:09:14`、SHA-256 `a4c7ee1dce5c26b445693e2054e61768e81b0ce3703f1a1f6ac328d11fd48e06`，均早于本轮，暂未发现副作用。

生产动态解析保持不动。迁移测试到 `monkeypatch.setenv("BOARDWISE_HOME", str(tmp_path))`，让真实生产路径读 env 并落到临时目录。Grep 找到只有 `tests/test_candidate_draw.py`（3处）、`tests/test_persistence.py`（4处）、`tests/test_187c_daemon_version.py`（1处）需要迁移。

## ② 当前树状态

HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合工作树含所有前批改动。`daemon.py=f82f9932…`、`autostart.py=23949f53…`、`core/config.py=64322fc3…` 为587/586修后状态，禁止回退。`tests/test_587_daemon_home.py` 已覆盖动态 env 与显式 home。596 首次全量被主动停止，日志 `.tmp_596_full_pytest.log`，不能当成完成读数。

## ③ 文件域与禁触清单

只允许修改上述三个测试文件的8处隔离调用及必要说明，写 `evidence/597/`、`.tmp_597/`、`.tmp_pt_597/`。禁止修改生产、其他测试、fixtures、前批证据；不 git、不删除、不启动真实daemon/EDA、不跑全量。先 cp 备份三个文件并记录SHA-256，变异恢复只能cp+SHA。

## ④ 交付物与验收

- 将8处 `monkeypatch.setattr(daemon_module, "BOARDWISE_HOME", tmp_path)` 改为 `monkeypatch.setenv("BOARDWISE_HOME", str(tmp_path))`，不改测试断言、顺序或业务语义；说明动态 HOME 下用 env 隔离的理由。
- 运行：`tests/test_candidate_draw.py tests/test_persistence.py tests/test_187c_daemon_version.py tests/test_587_daemon_home.py tests/test_157_auto_daemon.py -q --basetemp=.tmp_pt_597`，必须全绿。
- 测试前后各记录真实 audit 文件 SHA/mtime，必须一致；测试产生的审计只能位于 pytest tmp/basetemp，不得写真实 home。
- 做一个反向证明：若把其中一处改回 setattr，生产不再隔离，测试应失败或审计路径错误；禁止在真实 home 实际写审计，可用路径断言/mock append_audit 证明，恢复后 hash一致。记录到 `evidence/597/`。

## ⑤ 纪律与红线

只改测试隔离，不修改生产或断言，不用真实home做反例，不skip/xfail，不git、不删除、不跑全量、不真机。若还有其它失败，逐项交证据，不扩域。

## ⑥ 预算与交卷格式

最多20步或15分钟。交卷带8处diff、聚焦完整汇总、真实home前后hash/mtime、反向证明与恢复hash、未解决项。
