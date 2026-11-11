# 038R8：POSIX installer 测试复用既有 MSYS 环境探针

日期：2026-11-11。只修测试环境分类，不伪造脚本通过，不修改 Git 安装。

## 已核实根因

- `D:\Git\usr\bin\sh.EXE -c true` 从原生 Python 父进程派生时 24/24 报 `NtCreateDirectoryObject ... 0xC0000022`，从 MSYS 父进程运行正常。失败发生在脚本第一行之前，不是 install-hooks.sh 的行为失败。
- 同文件三条真实钩链测试已使用 `_skip_without_msys_shared_objects` 与 `_hook_shell()`；只有 `test_the_posix_installer_sets_hooks_path_and_the_exec_bit` 漏用，直接把环境不支持当 FAILED。

## 合同

- 给该测试补 `@_skip_without_msys_shared_objects`，并用 `_hook_shell()` 替代单独的 `shutil.which("sh")`，与被测 Git 实际 hook shell 对齐。
- 当前受限环境应显示 SKIP 及真实探针原因，不是 PASS。正常终端的 probe 通过时，原脚本、`core.hooksPath` 与 `chmod +x` 断言逐字执行，不能删改。
- 不新增广泛 skip、不捕获脚本错误、不降低测试要求；其他 hook 测试不变。

## 文件域与验收

- 仅 `tests/test_193_secrecy_hooks.py` 的必要两行/注释与 `.tmp_038r8/`；独立 `--basetemp=.tmp_pt_038r8`。
- 先跑目标测试确认真实 skip，再跑全文件，确认无新的 FAILED。记录 pass/skip，不把 skip 写成通过。
- 一个 coder，最多 12 步/12 分钟；零真机、零 git 写、零删除、零额外线 agent。


## 主代理验收（2026-11-11）

- 主代理全文件：**14 passed / 4 skipped / 0 failed**。目标由环境 FAILED 改为真实 SKIP，另外三个 skip 为既有同环境测试。
- 正常终端下脚本真跑未在本受限环境验证；不得把这条写成 POSIX 功能通过。断言体未改，探针通过时仍原样执行。
- 证据 `outputs/review/038r8/ACCEPTANCE.md`；非绘制线 14 项目标处理完成，未跑全量。
