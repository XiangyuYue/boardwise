# 038R7：只读槽句柄也必须参与真实并发锁

日期：2026-11-11。只修 `test_193_process_guards` 的环境失败，不绕过全机槽、不改槽数量、不改 ACL。

## 已核实根因

- 当前会话令牌对 `C:\Users\xiangyu\.boardwise` 只允许读；`open(...,'rb')` 成功，`open(...,'r+b')` WinError 5。文件本身正常，ACL 不是普通只读属性问题。
- `_try_lock` 只用 r+b，EACCES 被 `acquire_slot` 的 fail-open 吞掉，于是没有排队。
- explore 子代理实测：Windows 的只读句柄上 `msvcrt.locking(LK_NBLCK)` 可以真实加锁，另一只读句柄和 r+b 句柄都会冲突。当前两字节槽文件已存在，不需要在本会话创建它。

## 合同

- `tests/_process_guards.py` 的 `_try_lock` 在 Windows 且 `open(r+b)` 抛 PermissionError 时，若目标已是普通文件，则回退 `open(rb)`；之后的 seek/locking/slot-index/handle-lifetime 完全复用现有逻辑。
- 只读回退不是 fail-open：必须真实获得锁才返回 `(index, handle)`，占用期间第二个调用者必须等待，关闭后必须能重新取得。失败仍走原有诚实失败路径。
- 非 Windows 行为不变；文件不存在且无法创建、rb 也读不了、锁 API 不支持时不伪造成功。不得改 BOARDWISE_HOME 来分割全机锁，不得改成无锁运行，不得修改槽文件内容或系统权限。
- `acquire_slot` 的 SLOT_COUNT=2、排队/取得日志、等待/Ctrl+C 语义保持不变。

## 文件域与验收

- `tests/_process_guards.py`、 `tests/test_193_process_guards.py`、`.tmp_038r7/`；独立 `--basetemp=.tmp_pt_038r7`。
- 新增一个快速真实锁测试：临时槽文件存在，mock 仅让 r+b 抛 PermissionError，rb 正常；第一次获得槽、第二个 `_try_lock` 失败、close 后重新获得。非 Windows 明确 skip。
- 原有 `test_whole_suite_run_queues_behind_two_slots` 在当前受限环境必须真实出现「排队等待中」和「已取得全机并发槽」，所有子进程 exit 0；不得只测 open 模式。
- 跑完整 `test_193_process_guards.py`，确认 fail-open 破坏文件用例、worker 上限和线程闸不变。
- 两处变异：①删除 rb 回退，快速测试必须红；②让 rb 锁不参与互斥，第二个调用者/关闭重取断言必须红。cp+SHA-256 恢复复绿，不删备份。
- 一个 coder，最多 25 步/20 分钟；零真机、零 git 写、零删除、零额外线 agent。主代理独立复跑。


## 主代理验收（2026-11-11）

- 主代理完整进程闸测试：**42 passed**；真实排队输出见 `.tmp_038r7/queue_probe.log`，第三个进程等待后取得槽，三者 exit 0，槽文件内容未变。
- 两处变异均先红后 cp+SHA-256 恢复复绿。最终 `_process_guards.py` SHA-256 `417fb614023c049379d51984f3455d198703ee97b9a961115f5590a5f903852e`。
- 证据 `outputs/review/038r7/ACCEPTANCE.md`。非 Windows 与槽文件不可创建/读取的边界未扩大承诺。
