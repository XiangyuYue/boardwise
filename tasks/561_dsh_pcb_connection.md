# 561：DSH 接入 direct-only PCB 连通查询

## 1. 前因后果

559/559B 已完成 `boardwise pcb connection --from REF.PAD --to REF.PAD`、封闭 `pcb.connection_probe` action 与 Python 三态投影，原生 action 已在 EDA 4.1.100 完成正反例激活验收；这些成果已随 `0ac8973` 本地提交。560 当时暂缓 DSH 的理由是原生 action 尚未激活，现在该前提已消失。岳已批准先做 DSH 适配，再另立多跳邻接图合同。

本批只回答“两个 REF.PAD 在 direct 范围内是否有共享铜图元”。`CONNECTED` 只认 `direct-shared-track` / `direct-other-pad`；`NOT_PROVEN` 只表示 direct 范围内没有共享图元，**不是开路**；`INDETERMINATE` 与前置 refusal 仍按 CLI 区分。禁止恢复 `getEntireTrack` 或在 TS 重写 verdict。

## 2. 当前树状态

- HEAD `0ac8973`，main 相对 origin/main ahead 3；既有本地提交不推送，本批不 bump、不 pack、不部署、不发布。
- 工作树混有绘制线和其他 owner 的未提交改动。`dsh-plugin/src/transport.ts`、`src/draw-tools.ts`、`tests/draw-plan.spec.ts`、`tests/review-tools.spec.ts`、`tests/finalize.spec.ts`、`package.json`、`package-lock.json` 以及既有 `lib/draw-tools.js`、`lib/transport.js` 特别禁触。
- `dsh-plugin/src/index.ts`、`tests/register.spec.ts`、`tests/projection-async.spec.ts`、`tests/review-stage-gate.spec.ts` 当前只含已提交基线，可做本批最小注册与顺序更新。不要修改 Python/connector/protocol。

## 3. 文件域与禁触

允许：

- 新 `dsh-plugin/src/pcb-connection.ts`、新 `dsh-plugin/tests/pcb-connection.spec.ts`；
- `dsh-plugin/src/index.ts` 仅 import 与在 parts hunt 后、draw 前注册；
- 上述三份既有测试仅更新工具顺序/文本工具集合及新工具合同钉；
- `dsh-plugin/README.md`、`docs/review-sop.md` 仅本工具说明；
- 构建后仅与本批有关的 `dsh-plugin/lib/pcb-connection*`、`lib/index*`、`lib/types/pcb-connection*`、`lib/types/index*`；
- `.tmp_561/`、`.tmp_pt_561/`、`evidence/561/`、`tasks/561_dsh_pcb_connection.md`。

禁触：所有绘制线文件、其他 DSH 源/测试、版本文件、真实工程、daemon/EDA、Python、connector、fixtures、货架。不得格式化整文件，不得改他人未提交 hunks，不做 Git 写、删除、部署或发布。

## 4. 公开合同与交付物

注册 `boardwise_pcb_connection`，参数封闭为：

- `from` / `to`：必填字符串，TS 只检查 trim 后非空，REF.PAD 语法和连通判断交给 Python；
- `project` / `instance`：可选字符串，原样转成 `--project` / `--instance`；
- `port`：可选有限正整数，转成 `--port N`。

argv 固定以 `['pcb', 'connection', '--from', from, '--to', to]` 开头，只追加实际给出的可选参数。不得新增 file/out/live/board，不得自动切页或改走 `boardwise_bridge`。`timeoutMs=120_000`。

复用 `TEXT_OUTPUT + executeCli`，因为 CLI 的答案是 stdout JSON 而没有 `--json PATH`；文本 transport 保留 exit 0/2/3、stdout/stderr 与截断披露，不能伪造 structured 文件。exit 2 `NOT_PROVEN` 和 exit 3 都是 CLI 结果，不转成 TS 异常；spawn/timeout 仍走既有 transport 纪律。描述必须明确 direct-only、NOT_PROVEN≠开路、旧 daemon/connector 缺 action 会拒绝、工具不写设计。

测试至少钉住：

1. 注册顺序为原 13 工具中 parts hunt 后插入本工具，总计 14；文本输出集合包含本工具，参数键/必填/预算正确。
2. 全参数与裸参数的精确 argv；不得出现未给的可选 flag。
3. exit 0 CONNECTED、exit 2 NOT_PROVEN、exit 3（含 stderr refusal / 空 stdout）原样返回而非抛错。
4. from/to 空白及非法 port 在 spawn 前拒绝；spawn ENOENT 仍向上抛。
5. 既有 projection async 与 stage gate 工具顺序同步，stage gate 本身不新增深潜工具。

## 5. 验收与纪律

子代理先读 `AGENTS.md`、本任务、559/559B 现行合同与 `parts-hunt.ts` 的注册/测试范式。先 cp 备份将改的既有文件到 `.tmp_561/backup/` 并记 SHA-256。

开发期只跑：

```bash
cd dsh-plugin
npx vitest run tests/pcb-connection.spec.ts tests/register.spec.ts tests/projection-async.spec.ts tests/review-stage-gate.spec.ts
npm run typecheck
```

主代理随后跑 DSH 全量、build、关键 diff 与至少两项独立变异（撤注册、改错 argv/破坏 exit-2 结果语义）先红后 cp+SHA 恢复；不在本批跑全量 pytest、真机、部署或打包。

## 6. 预算与交卷

一个 coder，≤40 步/30 分钟，结论 ≤2000 字。交卷列实际文件、精确 argv 合同、测试命令→汇总行、未做项；不得只写“测试通过”。文档如实写 DSH 已适配源码但未部署、未发布，direct-only 与多跳边界不变。零 Git 写、零 rm/unlink、零版本 bump/pack。

## 7. 交卷记录（561 子代理，源码适配）

- 新增 `dsh-plugin/src/pcb-connection.ts`（`boardwise_pcb_connection`）与 `tests/pcb-connection.spec.ts`（11 例）；
  `src/index.ts` 仅 import + parts hunt 后、draw 前注册；三份既有测试只同步顺序/文本集合；README 与
  `docs/review-sop.md` 只加本工具说明。argv `['pcb','connection','--from',F,'--to',T]` + 实给可选项，
  `TEXT_OUTPUT + executeCli`，`timeoutMs=120000`；exit 0/2/3 原样返回，exit 2 不转异常，无 `--json` 文件。
- 聚焦：4 文件 `59 passed`；`npm run typecheck` exit 0。自测变异两处先红（撤注册 13 failed/12 passed；
  argv 换端 4 failed/7 passed），cp+SHA 恢复后复绿。
- 未构建（`lib/*` 无本批生成物）、未部署、未发版、未提交；DSH 全量与 build 留主代理。证据
  `evidence/561/dsh-adaptation.md`。


## 8. 主代理最终验收

- DSH `npm run typecheck && npm test && npm run build`：typecheck/build 通过，**218 passed / 1 skipped**；本批生成 `lib/pcb-connection.js`、`lib/types/pcb-connection.d.ts` 与 `lib/index.js` 注册变化。
- 文档/同步 **58 passed**；旧 SOP 的“DSH 不跟”已改为 561 实际入口，新增文档钉同时核 README 与注册。
- 父独立变异：撤注册 **13 failed / 12 passed**，argv 换端 **4 failed / 7 passed**；均 cp+SHA 恢复并复跑 **25 / 11 passed**。证据 `evidence/561/parent-validation.md`。
- 状态：**工作树完成、未提交未推送**；未部署、未 pack、未发布、未做真机或全量 pytest。direct-only 不变，多跳合同另立 562。
