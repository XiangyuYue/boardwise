# 038R5：全量暴露的合同断言同步

日期：2026-11-11。仅测试与验收集成，不改运行时代码。首轮全量 10751 passed / 24 failed；与 038Q3 基线相比新增 8 项、绘制线原 8 项转绿、16 项既有失败保持。

## 逐项裁定

1. `test_540_cli_{draw,shared,review}.py` 三个 owner manifest 数量仍写 147。038Q4 新增 `parsers/elibz.py=shared` 后实际为 148；只同步数量，并在适当一处钉该模块归属。`test_owner_rules` 已证明没有层违规。
2. `test_038{m,n,t}_*.py` 的 PRE_EXISTING review-report 哈希仍钉生成前字节。038R1/R3 合法改变 rulebody，官方生成器已把输入更新为 SHA-256 `9457f6d0c5210033027ab74148f9dace2f8a630b1fb82b85ef95c0b22a549243`；只更新这一项，其他 case 输入哈希逐项不变，并在注释说明这不是无审改基线。
3. `test_166_online_pcb_review.py` 与 `test_170_cold_export_layers.py` 旧断言「verdictWhy 不含任何 PCB」与 038R2 冲突。原测试的 stronger verdict 都是 incomplete（已有缺手册等原因），它们的主题是 runner 失败/冷启动不再额外改判，不是豁免宿主 DRC 开放项。
   - 保留原 exit/verdict、pcbReviewMissing/pcbReviewNotRun 和 disclosure 断言。
   - 明确 `hostPcbDrcUnchecked=true` 及恰好一条宿主 DRC 理由；滤除这条独立理由后，不得新增与 runner/冷启动相关的第二条 PCB 判决理由。
   - 不把 fake 改成 checked=true 来求绿，不回滚 038R2，不把 online runner 失败重新设为 pcbReviewMissing。

## 边界与 negative control

- 仅上述八个测试文件及本任务书/验收；不改 src、contracts、fixtures、其他测试、绘制线、bridge/Connector/DSH/Rust。
- 不改 Q4 owner/layer 行为，不改 rulebody=d2ff8ae4 或其合同输入字节；版本元数据继续保留生成前的 0.6.0，不引入 0.6.1 漂移。
- 无真机、无 git 写、零删除、零额外线 agent；pytest 独立 `--basetemp=.tmp_pt_038r5`。
- 反向断言：三个 owner 数量都 148 且 shared 归属正确；三份 PRE_EXISTING 只有 review-report 哈希变化；166/170 原 stronger verdict 与 disclosure 不变，host DRC 理由不得消失或重复。

## 验收

- 一个 coder，最多 25 步/20 分钟。先确认当前失败证据，再做上述最小编辑。
- 跑这八个文件、`test_owner_rules.py`、`test_038r2_host_drc_coverage.py`、`test_126a_pcb_review_plumbing.py`，记录实际计数。
- 主代理复核 diff 和测试后，按仓库纪律允许**一次**完整复跑；首轮失败已解释清楚，不盲目第三轮。


## 主代理验收（2026-11-11）

- 修前八文件 **8 failed / 84 passed**，与首轮新增失败逐项一致；主代理独立复跑扩至 owner/038R2/rulebody 后 **133 passed**。
- 五条变异均先红后 cp+SHA-256 恢复复绿；非 report 输入哈希也验证过不能偷改。038 三份 PRE_EXISTING 各只有 review-report 一处值变化，166/170 原 stronger verdict 与 disclosure 未变。
- 证据 `outputs/review/038r5/ACCEPTANCE.md`。完整复跑已启动，最终结果补记；不做第三轮常规全量。


## 完整复跑结果（主代理，2026-11-11）

- **10759 passed / 25 skipped / 1 xfailed / 16 failed / 1 warning**，1476.25 s。
- 相对首轮 **added=[]**，首轮八项全部转绿；相对 038Q3 也是 **added=[]**，16 项均为既有基线，不称全量全绿。
- 原绘制线八项转绿不是本批成果；没有第三轮常规全量。日志 `.tmp_038r5/full-pytest.log`，差分 `.tmp_038r5/failure-comparison.json`。
