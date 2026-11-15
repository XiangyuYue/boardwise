# 541R3：DSH 检查点与批次预算 pre-execute 硬闸

日期：2026-11-15。上游：`tasks/review-stage-runtime-gates.md`。本批只实现 R3；公开接口 allowlist 另批，不夹带 Python CLI、规则、绘制或真机改动。

## 1. 缺口与边界

目前第一批 checkup 后是否先交付检查点、预算到线后是否停止下一项深挖，仍靠模型自觉。本批在 DSH `tools/pre-execute` 上拒绝下一项受管深挖；已派发的当前命令自然收尾，不杀进程，也不把中断写成已交付。

只管理 `boardwise_checkup` 与 `boardwise_review_evidence` 两个深挖/重算入口。`boardwise_review_read`、`boardwise_review_finalize`、`boardwise_doctor` 是收尾入口，始终 `next()`；draw、普通宿主工具和其它非审查工具不在本批拦截。`boardwise_bridge` 的公开动作 allowlist 属下一批，本批不改变它。

## 2. 可证明的检查点

- `boardwise_review_finalize` 增加可选 `stage: 'initial' | 'partial'`；缺省调用参数、argv、收据 schema 和旧行为完全不变。带 stage 时 argv 追加 `--strict-partial`，结果可附加同名 stage 作为调度元数据；stage 不是板级 verdict，也不宣称 complete。
- 复用既有 `boardwiseReviewFinalized` Session receipt：只有 CLI finalize 成功、完整回读并记录的 receipt 才算交付，手写 `finalize.json` 不算。
- 新 host-only projection 从 Session `tool/call` / `tool/result` fold 出：实际完成的深挖批次、首条深挖的 event.time/model step、最近 model step、带 stage 的 finalize `{callId,out,stage,time,step}`。不得以一次被拒绝的 tool/call 开启新批次；深挖开始以对应 tool/result 完成为准，协议级 exit 1/3 仍是一次已完成审查。
- 当前批次的检查点必须同时满足：receipt 的 reviewDir 与当前显式 out 归一化键一致；receipt.callId 等于一次 initial/partial finalize 的 callId；stage finalize 的 out 与该 receipt 一致。只证明这一阶段交付已签名，不把 stage 标签当电气结论。
- checkup 的 `out` 在受管工作流中必须显式给出；省略 out 在 pre-execute 直接拒绝并说明原因，避免临时目录无法绑定检查点。review_evidence 本来就要求 out。旧 Python CLI 的 out 默认不变。

## 3. 放行/拒绝状态机

1. Session 无已完成深挖：首个带显式 out 的 checkup 放行。
2. 当前批次没有匹配检查点：下一项 checkup/review_evidence 一律 deny，reason 要求先以 initial/partial finalize 交付当前 out；不得通过换 out 绕过。收尾工具仍可调用。
3. 有匹配检查点：同 out 的后续深挖可放行；另一个显式 out 的 checkup 可开启新独立批次，其预算从该批首个实际完成的深挖重新计时。
4. 预算常量：`REVIEW_STAGE_TIME_LIMIT_MS = 30 * 60 * 1000`、`REVIEW_STAGE_STEP_LIMIT = 60`。以当前有效检查点为预算基线；没有检查点则以本批首个深挖为基线。墙钟用注入的 `now()` 减 event.time，步数用 Session tool/call 的 model step 差，不伪造成 token 或工具调用次数。
5. 到线（>=，不是 >）拒绝下一项深挖，但允许当前已派发调用和收尾工具。此后必须用当前 out 的一个**更新** initial/partial finalize receipt 交付；新检查点成为下一预算段基线。旧检查点不能永久解锁。
6. 无 Session、projection/receipt 不可用、时间或步数无法判定时，受管深挖 fail closed；普通工具不受影响。deny reason 不泄露 token，不调用引擎。

## 4. 实现文件域

- 新增 `dsh-plugin/src/review-stage-gate.ts`：projection、常量、纯判定/监听工厂与注册。
- 修改 `dsh-plugin/src/review-finalize.ts`：仅上述可选 stage 参数、argv/结果附加；不改既有 receipt envelope。
- 修改 `dsh-plugin/src/index.ts`：兼容 0.2.1 同步注册与 0.2.2 awaitable 注册，两个 projection 都 ready 后才发布依赖它们的闸；不得 await 旧版 disposer。
- 新增 `dsh-plugin/tests/review-stage-gate.spec.ts`；必要时修改 `dsh-plugin/tests/register.spec.ts`、`projection-async.spec.ts`、`delivery-gate.spec.ts` 的 listener 收集方式。多个 `tools/pre-execute` listener 必须串联，单槽 Map 覆盖属于测试 harness 缺陷，不得靠删旧测试绕过。
- 本任务书。最终由主代理另更新 review-stage-runtime-gates/review-line/TASKMAP/README 中确有必要的声明。

不得修改 Python、connector、draw-tools、shared-tools、transport、既有 fixtures、package 版本或发布件。allowlist 不在本批。

## 5. negative control 与验收

至少覆盖：

- 第一次 checkup 放行；无 out 拒绝；首批后直接 evidence/第二次 checkup/换 out 均拒绝；read/finalize/doctor 仍放行。
- 手写 finalize.json 无 Session receipt 不解锁；普通无 stage finalize 不解锁；stage finalize 但 out/callId 不匹配不解锁；匹配 initial 与 partial 均解锁。
- 到 30 分钟、到 60 model steps 各拒绝下一项深挖；临界前放行；已派发命令不取消；同批新检查点重置预算段，旧 receipt 不重置。
- 被拒的 tool/call 不产生 tool/result，不得把批次切到另一个 out；projection 损坏/缺 Session fail closed。
- 0.2.1/0.2.2 注册和旧 present delivery gate 同时存在，旧工具顺序与缺省 finalize argv 不变。
- 至少两处有效变异：①把无检查点的 deny 改 next，首批后深挖用例必须红；②把预算 >= 改 >，到线用例必须红。cp 备份、SHA-256 恢复，禁 git restore。

聚焦验收：`cd dsh-plugin && npm run typecheck && npm test && npm run build`，测试输出写 `.tmp_541r3/`；不跑 Python 全量、不跑真机、不部署、不重启 DSH。真实 DSH 独立加载验收另列，未重启不得声称已加载。

## 6. 交付

交回真实测试计数、关键合同/断言、两处变异及恢复哈希、注册兼容证据、未覆盖项。零 git 写、零删除命令、零发布。若无法从无 stage receipt 与 Session 事件无歧义证明检查点，停止并报告，不退化成“ finalize 过就算检查点”的弱口径。

## 7. 实际结果与主代理复核（2026-11-15）

- 已实现 `review-stage-gate.ts`、可选 finalize stage、0.2.1/0.2.2 双 projection 注册与多 listener 串联。检查点要求 receipt+callId+out 匹配；任何欠检查点的批次都阻止同目录和换目录深挖；30 分钟/60 model steps 到新收据才开新段。
- 首轮主代理拒收两处：换 out 被错误放行、测试用 `rmSync` 直删临时目录。返修后新增跨目录缺失/陈旧 receipt 负例，直删清理全部移除；另补第二 projection pending 时不发布和 exec.signal 不中止断言。
- 最终 DSH：**9 files / 165 passed / 1 skipped**，typecheck、build 均通过；主代理独立复跑读数相同，日志 `.tmp_541_main/acceptance.log`。
- 主代理独立变异：①跳过所有欠账批次 → **7 failed / 14 passed**，两条跨目录负例均红；②时间/步数 `>=`→`>` → **3 failed / 18 passed**。恢复后 `review-stage-gate.ts` SHA-256 均为 `33682d65712d82432562b1fefb686f339c7f4c06128ea73c7e54fea6dda018f5`。
- 同步更新 `review-tools.ts`、README 的显式 out 与新预算说明，tracked `lib/` 已由官方 build 重生成。未跑 Python 全量、未部署、未重启真实 DSH；桌面/profile 独立加载仍未验证。
