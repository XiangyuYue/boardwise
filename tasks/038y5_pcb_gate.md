# 038Y5 / 只读 `boardwise pcb gate`

## 来源与目标

预研闸门有三条不能移植的行为：checkup incomplete 仍可 GREEN、DRC 红与不可陈述的退出码
颠倒、固定 out 可读到上一轮 report；其 autofix 还依赖本仓不存在的动作。
本批只做**只读编排**：宿主 DRC → 新鲜 checkup（已包含三条新规则与既有丝印审查）→ verdict。
不复制丝印几何，不调用 doc.open，不写设计，不提供 `--skip-checkup` / autofix / save。

## 公开合同

`boardwise pcb gate --out DIR [--project NAME_OR_UUID] [--instance KEY] [--port N]`：

- `doc.list` 必须证明当前活动文档就是要审的 PCB；焦点非 PCB、 boards[0] 回退、工程/实例
  hint 不匹配均拒绝。不得自动换板。项目身份无法读取时只有显式 instance 可作为身份。
- DRC 使用 `pcb.drc_check`，`strict=true / userInterface=false / includeVerboseError=true`。
  `checked/available` 不成立、计数缺失或结果被截断 = INCOMPLETE；errors>0 = RED。
- 无写入步骤，所以不重复跑第二次 DRC。checkup 使用同一 project/instance/port 与新的
  `DIR/checkup`，复用 `_cmd_checkup` 的真实参数和报告，不重造审查链。
- GREEN 必须同时满足：DRC errors=0 且完整；checkup 已跑；退出码与 report 的
  conclusion/summary 一致；`completion.verdict` 为 complete 或 complete-with-open-items；
  无 ERROR；coverage 未声明 parse/model/rules/records/PCB 缺失。
- checkup exit 3、completion/conclusion incomplete、未知 verdict、退出码矛盾、coverage
  红灯、报告缺失或 exit 2 = INCOMPLETE。ERROR/exit 1 且无 incomplete = RED。
  incomplete 优先于 ERROR，因为此时不能声称已看全。
- 退出码：**0 GREEN / 2 RED / 3 INCOMPLETE 或输入、身份、输出不可用**。
  argparse 自身 usage error 仍为2；不再设 RED-DRC 特例。
- `DIR` 必须是新目录（parents 可新建），已存在即拒绝，绝不复用旧 gate/checkup 报告。
  任何失败不得读旧 report 当本次结果。报告只保存必要摘要，不塞巨大原始 DRC。

## 集成与文件域

- 新 `src/boardwise/pcb_gate.py`（assembly）：同步 `run_gate(call, checkup_runner, out, ...)`，
  fake 可测；CLI adapter 每次 bridge action 用自己的短连接，避免在运行中的 event loop 里
  再调同步 checkup。checkup runner 返回 `(report_dict, exit_code)`。
- `commands/assembly.py` 只注册 parser；`cli.py` 仅 build_parser/main 两处接线；
  `tools/cli_contract.py` 与 `contracts/cli/v1.json`（`python -m tools.cli_contract --write`）；
  `contracts/module-owners.json` 加 `pcb_gate.py: assembly`。
- 新 `tests/test_038y5_pcb_gate.py` 及实际 CLI/owner 锚点。禁止 connector/daemon/protocol、
  rules/shared geometry/parser/draw/fixtures、预研 pcb_gate 覆盖。无 differential rulebody 变化。

## 兼容矩阵与 negative control

- V3/V4、在线宿主均未真机验证；本批仅 fake bridge + 真实 CLI/checkup 参数适配测试。
  `.epro2/.eprj2/.eprj3` 不由 gate 直接读取，格式兼容仍属 parser/checkup。
- 单活动PCB可判；多板不回退第一块，跨板不合并。普通器件/CBB 继续走 checkup，不新增语义。
- 必测：DRC未跑/截断/0/红；checkup incomplete+无ERROR不得 GREEN；ERROR→RED；
  complete-with-open-items可GREEN但披露；rulesErrored/parseIncomplete/pcbReviewMissing不得 GREEN；
  陈旧out第二次拒绝且不再调用checkup；非活动PCB与hint错配零DRC；缺报告/退出码矛盾不得 GREEN。

## 验收

新测试、CLI contract、540B/540C、owner/layer/doc 守卫与 checkup 邻域；两处独立变异先红
（忽略 incomplete、允许旧out或boards[0]回退），cp+SHA恢复。不自动全量、不跑真机。
最终记录实际读数、CLI帮助/契约和未覆盖项。

## 状态

实现与主代理验收完成（2026-11-15，工作树，未提交）。最终生产 SHA-256：
`14d25a9f717257f062a1ac87bca754d780286c165bdc8d9b9fc7858e6040842e`。

- 新测试最终 61 条；主代理独立变异：忽略 incomplete `1 failed / 60 passed`；允许旧 out
  `3 failed / 58 passed`，均按 SHA-256 恢复。
- 主代理最终联合：**1505 passed / 2 skipped（82.66s）**，包含三规则与共享几何、
  CLI contract、540B/540C、owner/layer/doc、checkup 与 bridge 邻域。
  `python -m tools.cli_contract` 为 `CLI contract matches production`；`pcb --help` 只显示 gate。
- 主代理复核补齐 rulesRefused/pagesDropped/boardsEmpty、双 verdict 对账、findings 列表与
  直接 ERROR/completion.errors 证据，避免完成段字段互相掩盖。
- 上述是实现批的离线验收基线；后续 038Y5L 已在 test V4 完成活动页拒绝、PCB1 真实 DRC RED
  与旧目录拒绝。V3、天然 GREEN 及 DRC 清洁后的 checkup 联动仍未在线覆盖，见
  `tasks/038y5l_pcb_gate_live.md` 与 `outputs/review/038y5l/`。gate 自己跑 DRC，所以
  hostPcbDrcUnchecked 不另列致命集；其他八类 coverage 缺口均拒绝 GREEN。
- 不支持 autofix/skip-checkup/doc.open/save；autofix 前提另见 038Y6。
