# 038R2：宿主 PCB DRC 未运行不得形成可投板结论

日期：2026-11-11。审查线 shared/completion 小批，只处理用户报告的 `drc.pcb.checked=false` 判决缺口；BoardOffEdge 另批，FOC 证据批已完成。

## 已核实缺口与裁定

- 离线 `--file` 的宿主 DRC 段是 `{checked:false, source:offline-not-available, reason}`；`drc.summarise` 不伪造计数、不加 ERROR，这是必须保留的正确行为。
- 但 `_completion_body` 的 coverage 没有这一项。其余闸全清时，当前可得到 `completion.verdict=complete`、`conclusion.mayQuotePassed=true` 和「可以投板」。自有规则没有新增 clearance finding，并不等于宿主 DRC 通过。
- **裁定为 `complete-with-open-items`，不是 incomplete**：本次能读的审查已完成，但存在明确开放项；无其他 ERROR 时退出码仍为 0，不改成 3。`conclusion.mayQuotePassed=false`、整板结论不得写「可以投板」。不得把 checked=false 改写成 ERROR 或 Finding。
- 只覆盖**工程实际含 PCB 文档、而本次宿主 PCB DRC 未 checked** 的情况，离线或在线拒绝均一样。无 PCB 的工程不因缺少 PCB DRC 被降级；checked=true 行为不变；countsIncomplete 等既有更强闸不变。

## 最小合同

- `_coverage_section` 新增可选 `hostPcbDrcUnchecked`，只在为 true 时写入；无 PCB 或宿主已查时不写，保持普通旧输出键集。
- 在 `cli._cmd_checkup` 已有 `pcb_had_documents` 与 `drc` 的地方计算事实，不能从「没有 clearance finding」倒推，也不能默认 true。旧报告 re-gate 时缺键=False，不追溯改写历史 verdict。
- `_coverage_reasons` 增加一条：宿主 PCB DRC 未运行（`drc.pcb.checked=false`，原因见该段），自有规则零新增不等于宿主通过。它通过既有 `coverage_reasons` 进入 `complete-with-open-items`，不要加进 incomplete 条件。
- `_completion_coverage_gates` 的 open-item coverage_gaps 同步计入这一新类，避免 verdict 与结论句分裂；旧报告缺键仍为 False。
- `drc.pcb` 原字段、reason、countsIncomplete、summary.exitCode 的错误优先级保持不变。`conclusion` 键集不扩，仍读 `verdict/mayQuotePassed/oneLiner/blockers`。
- 更新 `docs/review-sop.md` 现有 `checked=false` 一句，明确 PCB 工程的 verdict 是开放项而不是可引用通过；在 `tests/test_doc_claims.py` 加对应机器钉。

## 兼容矩阵 / negative control

| 维度 | 覆盖 | 必须不变 |
|---|---|---|
| 离线含 PCB | checked=false → complete-with-open-items，mayQuotePassed=false；无 ERROR 时 exitCode 0 | 不伪造宿主计数，不写 DRC 通过 |
| 在线含 PCB | 宿主拒绝/未查同样开放项；checked=true 不加新键 | 不做真机，不把 bridge 拒绝当板缺陷 |
| 无 PCB | 不触发新键 | 原理图-only verdict 不变 |
| V3/V4、容器、多板、CBB | 本批不重新验证 | 模型/parser/规则不变，不声称兼容扩大 |
| 旧报告 re-gate | 缺新键保持旧行为 | 不用新闸追溯惩罚旧归档 |
| BoardOffEdge | 另批 | 本批不改几何规则或 findings |

## 文件域

- `src/boardwise/cli.py`：新 coverage 事实、reason、conclusion gate 与实际调用。
- 新增 `tests/test_038r2_host_drc_coverage.py`，用纯 fake/现有公开夹具，覆盖有/无 PCB、checked true/false、旧报告缺键。
- `docs/review-sop.md`、`tests/test_doc_claims.py`：只更新本新口径。
- 若现有 completion/CLI 测试明确断言旧的“离线宿主未查也 complete”，允许按本新合同做最小期望更新，并逐项记录；不得为求绿删测试或放宽其他断言。
- 日志/备份 `.tmp_038r2/`，pytest 独立 `--basetemp=.tmp_pt_038r2`。

不改 `engines/drc.py`、`engines/checkup.py`、BoardOffEdge、FOC、038Q4、bridge/Connector/DSH/Rust、绘制线、package/version/TASKMAP；零 git 写、零删除、零真机。

## 验收

- 纯 fake 复现修复前：无 ERROR、其他覆盖干净、含 PCB、drc.pcb.checked=false 时旧结论可 complete/mayQuotePassed；修后必须 complete-with-open-items/mayQuotePassed=false，blockers 指明宿主未运行。
- 反向断言：drc.pcb 仍 checked=false，无新增 Finding/ERROR，exitCode 仍 0；无 PCB 不触发；checked=true 不触发；旧报告无新键 re-gate 结果不变。
- 跑 coverage/completion/checkup CLI/report 邻域与 doc claims，实际记录计数。
- 两处变异：① coverage 调用不 facts/true 永远 false；②删除新 reason 或 conclusion gap。对应断言必须红，cp+SHA-256 恢复并复绿。
- 一个 coder，最多 35 步/25 分钟；不全量 pytest，主代理独立复验并决定集成全量。


## 主代理验收（2026-11-11）

- 新 11 测试旧实现 9 红 2 绿，修后全绿；主代理集成邻域 **448 passed**，DSH 137 passed / 1 skipped。
- 三处变异均先红后 cp+SHA-256 恢复复绿；随后仅修正注释与测试匿名，最终 cli.py SHA-256 `4d10aebd4a8605c031542a16ae5047c14886b561277bbb2890a10738be94991a`。
- 合同为 complete-with-open-items，不是 incomplete；无 ERROR 时 exit 0，mayQuotePassed=false，不伪造宿主计数/错误。无 PCB、checked=true 和旧报告缺键不受影响。
- 证据 `outputs/review/038r2/ACCEPTANCE.md`。在线 checked=true/拒绝未做真机；全量由集成批统一验收。
