# 544 · checkup / arch 写盘失败退出码（审查线 shared 小批）

> 来源：`boardwise-测试问题清单-20261104.md` 的 T-E02 / T-E03 / T-A06。
> 本批只修写盘失败边界，不处理同目录并发、重跑提示、解析规则或绘制算法。

## 完成条件

- `checkup --out` 指向不可写目录时：exit 2、一句可操作的写盘错误、无 Python traceback。
- `checkup --out` 指向普通文件时：exit 2；原文件逐字节不变，不产出半个 `report.json`。
- `arch --out` 指向目录时：exit 2，明确这里要的是文件路径；目录不变。
- 合法调用的模型、报告内容、stdout/stderr 既有语义、退出码不变。
- 不做全局 `OSError` 一概映射；只在实际输出边界转换错误。其它调用方保持自己的合同。

## 允许文件域

- `src/boardwise/cli.py`：仅限 `_cmd_checkup` 的报告输出边界与 `_cmd_arch` 的 `--out` 写边界；不改 `_write_checkup_report` 的其它消费者语义。
- 新增 `tests/test_544_output_errors.py`（集中放三条回归，避免改并行测试文件）。
- 本文及最终必要的台账更新由主代理处理。

## 兼容矩阵与 negative control

| 维度 | 本批覆盖 | 不得外推 / 必须不变 |
|---|---|---|
| 离线输入 | 现有公开 `.epro2` 夹具 + `tmp_path` 输出形状 | 不改解析，不声称新增 `.eprj3` 能力 |
| 在线 | 不连接 daemon / 编辑器 | 不声称在线写盘或真机验收 |
| V3 / V4 宿主 | 不涉及 | 无宿主版本分支、无真机结论 |
| 单 / 多板 | 既有输入读取路径不变 | 不改多板合并、拒绝或 findings |
| 普通器件 / CBB | 不涉及 | 不改器件、规则与 CBB 口径 |
| 输出 | 三个失败分支 + 合法路径回归 | 原输入不变；合法产物与既有内容不变 |
| 其它命令 | `_write_checkup_report` 的 triage/finalize 等调用方 | 不把它们的异常统一吞成 checkup 文案 |

## 验证

- 先让三条回归在旧实现失败，再修到全绿。
- 聚焦跑新测试、`tests/test_checkup_cli.py`、`tests/test_architecture.py`、`tests/test_owner_rules.py`。
- 至少两处独立变异必须被测试捕获；用 `cp` 备份恢复并核对 SHA-256，不用 git 还原。
- 不跑全量、不派下级代理、不连真机；日志和探针放 `.tmp_544/`。
- 禁止 git 写、提交、推送、删除、依赖安装和其它文件改动。

## 执行与验收（2026-11-04，工作树）

- `tests/test_544_output_errors.py` 最终 **8 passed**：三个报告场景、后续产物失败不谎称无报告、arch 骨架/父目录失败、两条合法路径负控。
- 主代理独立复跑 544 + checkup/arch/owner/报告邻域：**213 passed**（独立 `.tmp_pt_544_main`）。
- 原始 T-E03 与 T-A06 命令均实际 exit 2，两个原路径的 SHA-256 前后不变。
- 原 T-E02 ACL 目录复测时已可写，故没有冒充 ACL 复现；`PermissionError` 分支由 monkeypatch 确定性覆盖，后续产物失败也明确报「未完整写出，不能当作完整交付」。
- 子代理两组红绿与变异证据在 `.tmp_544/`；主代理退回并修复了后续文件已落盘时的虚假文案及 arch 普通写盘 OSError。
- 未覆盖：`review`/`triage`/`finalize`/`need-datasheet` 的其它写盘边界、真实 ACL 复现、真机/POSIX；这些不借本批外推。
