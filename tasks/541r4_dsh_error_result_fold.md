# 541R4：DSH error `tool/result` 不得记成深挖/检查点

日期：2026-11-16。前置：541R3 离线测试假设 pre-execute 拒绝后没有 `tool/result`；真实 DSH 0.2.2-rc.3 + boardwise-clean Session `session-8c0db486-c180-4468-8c8f-fedfd1f65a3a` 证明宿主会追加 `tool_result(status=error)`。首轮实际事件：无 out 拒绝正确；live-a checkup exit 3 且报告生成；随后的 review_evidence 被闸拒绝，却使下一次跨目录拒绝文案变成“2 completed deep dive(s)”，预期应为 1。原始事件 `.tmp_541_live/session-3-events.jsonl` 第 12–21 行。

## 1. 公开合同

- `tool/result.message.isError === true` 只推进 lastStep 并清对应 pending，**不得**新增/增加批次 diveCount，也不得新增 initial/partial checkpoint。
- 协议级 exit 1/3 是 boardwise 工具正常返回，DSH `status=completed` / `message.isError=false`，仍按已完成深挖记账；本批不改变它。
- 缺 `isError` 的旧事件按 false 处理，保持旧日志兼容。error 后同 callId 不能留下 pending，后续同 id 正常结果也不得重复记账。
- 拒绝仍不取消已派发命令；read/finalize/doctor 收尾自由不变。receipt+callId+out 的既有检查点判据不变。

## 2. 文件域与 negative control

仅 `dsh-plugin/src/review-stage-gate.ts`、`dsh-plugin/tests/review-stage-gate.spec.ts`、本任务书；lib 由官方 build 重生成。不得改其它生产文件、fixtures、绘制线、版本或发布件。

新增真实事件形 negative controls：
1. A 一次正常 dive 后，B 的受管 call 以 `isError:true` 结束：不得创建 B，A 仍 diveCount=1；拒绝文案保持 1。
2. staged finalize 的 error result 不产生 checkpoint，即使同目录旧 receipt 仍存在，也不能靠这次 error 重置预算段。
3. 正常 exit 1/3（isError=false）仍计 dive；缺 isError 的旧结果仍计 dive。
4. error 清 pending，重复结果不重复记账。

至少一处变异：忽略 isError 后前两条必须红；cp+SHA-256 恢复。跑 DSH typecheck/test/build，长日志 `.tmp_541r4/`。主代理独立复验并重新打包隔离 profile，再用新 out 做实载首轮；真实桌面 profile 不热更。

## 3. 纪律与完成

零 git 写、零删除、零全量 Python、零真机、零桌面重启。完成不等于 541 全部验收：initial/partial 解锁与后续实载仍需在本修复安装后验证。最终报告真实计数、变异红绿、恢复 hash、实载待办。

## 4. 实现与真实 DSH 复验（2026-11-16）

- 实现：`foldResult` 新增 failed 实参，`message.isError===true` 只推进 lastStep 并清 pending；false/缺失保持旧记账。新增四条真实 Session negative controls。子代理 DSH **169 passed / 1 skipped**，typecheck/build 通过。
- 主代理独立变异：忽略 isError → **3 failed / 22 passed**；恢复后 **25 passed**，源码 SHA-256 前后均 `9335c356415fccff40efa8c45dcd81e31281cf324cb383fdba24d3097e77fae3`。隔离 profile 安装 lib SHA 与仓库一致：`c9754455c7c6b4b65baba7e4683789907a3fecd87acda77ac6ab2f79219d4e2d`。
- 真实 DSH 0.2.2-rc.3、同一 Session `session-8c0db486-c180-4468-8c8f-fedfd1f65a3a` 第二轮：①文件 finalize.json 存在时换 out 仍拒绝且准确显示 **1 completed deep dive**；②initial finalize 返回 `sessionRecord seq=57`，随后 evidence 真跑 exit 3；③partial finalize 返回 `seq=68`，随后 evidence 再次真跑；④有当前检查点后 live-b checkup 真跑并生成四件产物。原始事件 `.tmp_541_live/session-4-events.jsonl`。
- 541 的隔离真实 profile 验收至此完成。使用本机 scripted 模型只驱动固定工具队列，内核、插件、两个 projection、listener 和 CLI 都是真实执行；未消耗外部模型额度。**未安装/重启桌面 profile**，桌面生效仍需独立部署，不把隔离验收写成桌面已加载。

## 5. 格式收尾

`git diff --check` 发现官方 tsc 发射在参数注释前留下尾随空格；已仅移动注释并重 build。聚焦复验 **25 passed**，最终 `src/review-stage-gate.ts` SHA-256=`53d3f3054ea67563d1c78f622ef7279ff82d065899cd102f89682d1e3304e8b0`，`lib/review-stage-gate.js`=`6c15cb2ae93b0ed8ccb9385c58de14a136a588ee3aed6364e3a8d531a25045d5`，diff-check 通过。该格式变化不改变上述实载结论；隔离 profile 实载用的是同逻辑的先前构建。
