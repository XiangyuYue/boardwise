# 541I：公开接口 allowlist 的证据与 tool-gap 披露

日期：2026-11-15。上游：`tasks/review-stage-runtime-gates.md` 的公开接口 allowlist 缺口。与 541R3 分属不同文件域，可独立验收；不改 Python、动作目录或审查规则。

## 1. 现状裁定，避免第二套名单

- DSH 没有通用“任意 boardwise CLI 命令行”工具；各受管工具在 TS 中固定 argv，因此可调用的 CLI 子命令已经由工具注册面限定，不能再拼私有子命令。
- `boardwise_review_read` 的 section 已由参数 enum 限定为 verdict/findings/crossView/coverage/artifacts/netlist。
- `boardwise_bridge` 每次固定传 `bridge call --read-only`。Python `_read_only_refusal()` 在打开 daemon/socket **之前**以 protocol `ACTIONS` 的唯一目录判定：只有 `risk=read` 放行；write/create/dangerous/未知动作全部 exit 2、`READ_ONLY_VIOLATION`，不转发编辑器。不能在 TS 再抄一份动作名单，否则目录漂移后会出现两套真相。
- 普通宿主 Read/Grep/Bash 手解析内部文件不属于这些受管入口，本批不拦普通工具；它仍是覆盖缺口，必须披露，不能宣称已被 allowlist 管住。

所以本批不新建桥动作白名单，而是把既有硬闸的拒绝以稳定 `tool-gap` 形式交回模型，并钉住端到端 argv/拒绝证据。

## 2. 增量合同

`boardwise_bridge` 调用 CLI 后，若格式化结果含稳定 `READ_ONLY_VIOLATION`：

- 保留原 CLI 输出和 exit，不改写 risk/原因；
- 在结果前附加一行 `tool-gap: the requested bridge action is outside the public read-only interface; nothing was forwarded to the editor.`；
- 可再加一句指向受支持的 `boardwise_checkup` / `boardwise_review_evidence` / `boardwise_review_read`，但不能声称某一个高层工具必然覆盖该动作；
- 未知动作同样以 tool-gap 披露为未覆盖能力，不能放行、不能伪称已支持。

成功结果、其它 CLI 错误和普通工具结果逐字不变。该 token 是覆盖/能力披露，不是新的板级 finding，也不改 CLI exit。

## 3. 文件域

- `dsh-plugin/src/shared-tools.ts`：仅 boardwise_bridge 结果处的 tool-gap 包装；`--read-only` argv 不动。
- `dsh-plugin/tests/tools.spec.ts`：拒绝、成功与普通错误回归。
- 本任务书；最终由主代理更新 review-stage-runtime-gates/review-line/TASKMAP 的状态和“手解析内部文件仍不覆盖”的边界。

不得修改 protocol.py、cli.py、review-stage-gate.ts、index.ts、review-finalize.ts、draw 文件、fixtures 或 package 版本。

## 4. 验收与 negative control

- write（如 doc.focus）、create（如 sch.doc.new）、未知动作的模拟 CLI `READ_ONLY_VIOLATION` 结果都带 tool-gap，原 risk=unknown/write/create 文案保留；每次都仍有 `--read-only`。
- 成功 doc.list 不带 tool-gap且正文不变；NO_CONNECTOR、TIMEOUT 等其它错误不被误标为接口覆盖洞。
- 注册测试继续证明 review_read 六 section enum 和固定工具面；无需新增 TS 动作清单。
- 两处变异：①去掉 tool-gap 包装，三条拒绝用例必须红；②去掉 argv 的 `--read-only`，既有钉必须红。cp+SHA-256 恢复。
- `cd dsh-plugin && npm run typecheck && npm test && npm run build`，日志 `.tmp_541i/`；不跑全量 Python、不跑真机、不部署。

## 5. 完成边界

完成后可以说：受管 DSH 工具面的公开子命令/section 有限定，bridge 由唯一 protocol 目录在 daemon 前拒绝非 read/未知动作，拒绝带 tool-gap。不能说：宿主任意 Bash/Read 的私有文件解析已被拦截，或 bridge 每个 read 动作都有高级工具等价物。零 git 写、零删除、零发布。

## 6. 实际结果（子代理交卷，2026-11-15）

**结论：本批绿。** 受管 DSH 工具面的 bridge 入口在 CLI 已拒绝（`--read-only`，exit 2，
stderr 一行 `READ_ONLY_VIOLATION`）时，结果前加两行稳定 `tool-gap:` 披露，CLI 原文与 exit 逐字保留；
成功读、`NO_CONNECTOR` 等普通错误、被杀的运行（timeout/abort 走同一 throw）一律逐字不变。
未新抄任何动作名单：判定仍是 Python `_read_only_refusal()` 对 protocol `ACTIONS` 唯一目录。

### 6.1 改动（仅两个文件，`git diff --stat`）

```
 dsh-plugin/src/shared-tools.ts | 27 ++++++++++++-
 dsh-plugin/tests/tools.spec.ts | 87 ++++++++++++++++++++++++++++++++++++++++++
 2 files changed, 113 insertions(+), 1 deletion(-)
```

- `dsh-plugin/src/shared-tools.ts:18-41`：`READ_ONLY_VIOLATION` 常量、`READ_ONLY_TOOL_GAP` 文案、
  `discloseReadOnlyGap(outcome)`（命中 token 才前置，否则原样返回）。
- `dsh-plugin/src/shared-tools.ts:163`（原 138）：只把 `return await executeCli(...)` 改成
  `return discloseReadOnlyGap(await executeCli(...))`；`argv` 里的 `'--read-only'` 一字未动。
- `dsh-plugin/tests/tools.spec.ts`：新增 `boardwise_bridge: public read-only interface (541I)` 六例
  （write `doc.focus` / create `sch.doc.new` / unknown `no.such.action` 各带 tool-gap 且 `risk=` 原文保留、
  argv 仍有 `--read-only`；成功 `doc.list` 无 tool-gap 且正文不变；`NO_CONNECTOR` 不误标；被杀运行不误标）。
  既有 22 例断言未删未放宽。

未动：Python、`protocol.py`、`cli.py`、`transport.ts`、`index.ts`、`review-finalize.ts`、
`review-stage-gate.ts`、其它测试、draw、fixtures、`package.json`。

### 6.2 实跑读数（日志 `E:\boardwise\.tmp_541i\`）

- `npm run typecheck` → exit 0（`final.log`）
- `npm test` → **Test Files 9 passed (9) / Tests 163 passed | 1 skipped (164)**，exit 0（`final.log`）
  - `tests/tools.spec.ts` 单跑 **28 passed (28)**（`tools-only.log`，verbose 清单见 `tools-verbose.log`）
- `npm run build` → exit 0（`final.log`）
- 交卷时 SHA-256：
  `shared-tools.ts = b57c7bd18aca751b3804a6f43927fefd1d13b3b7122f1fd82595ecaf0259c75e`
  `tools.spec.ts   = 377950483c4f052923e586b9831c62bed8715d122a2cff799f7246e27849635b`

### 6.3 两处变异（`cp` 备份 + SHA-256 还原，`cmp` 字节一致）

1. 去 tool-gap 包装（`return await executeCli(...)`）→ `tools.spec.ts` **3 failed | 25 passed (28)**，
   红的正是 doc.focus / sch.doc.new / no.such.action 三例，成功与普通错误两例仍绿（`mut1.log`）。
2. 去 argv 的 `--read-only` → **6 failed | 22 passed (28)**：既有两例钉子
   （`passes action, params, the read-only gate...`、`pins --read-only on every call...`）先红，
   加上三条 541I 拒绝例与成功例（`mut2.log`）。
3. 还原：`shared-tools.ts` 回到变异前 `aaa447cbb54d...1833d`，`cmp` 报 `restore-byte-identical`；
   之后仅一处 docstring 措辞修正（可执行代码未变），最终 hash 见 6.2。

### 6.4 未覆盖 / 披露

- 宿主任意 `Read`/`Grep`/`Bash` 手解析内部文件**没有**被拦，仍是覆盖缺口；本批只把受管 bridge 入口的
  拒绝披露为 tool-gap，不得据此宣称“私有解析已管住”。
- bridge 的每个 `read` 动作并**不**都有高层工具等价物；tool-gap 第二行只指向
  `boardwise_checkup`/`boardwise_review_evidence`/`boardwise_review_read` 各自认领的读，明确不声称可替代。
- 触发条件按合同原文为“格式化结果含 `READ_ONLY_VIOLATION`”，不再解析 exit；read 结果正常不带该 token。
- 并行提示：跑 `npm test` 期间 541R3 的 `src/review-stage-gate.ts`（21:03:16）与
  `tests/review-stage-gate.spec.ts`（21:02:07）仍在被另一 coder 改写，中途曾见 3 项红、随后自愈
  （`npm-test.log` → `npm-test-last.log` / `final.log` 全绿）。`npm run build` 连带重写了
  `dsh-plugin/lib/*`（tracked），属任务书 ④ 强制的构建产物，非本批手改。

## 7. 主代理独立复核（2026-11-15）

- Python 唯一目录闸聚焦：`tests/test_537a_bridge_readonly.py tests/test_action_catalogue.py` → **36 passed**，不是只信模拟 stderr。
- 联合 DSH typecheck/test/build：**9 files / 165 passed / 1 skipped**；主代理日志 `.tmp_541_main/acceptance.log`。
- 独立去 tool-gap 包装 → **3 failed / 25 passed**；独立去 `--read-only` → **6 failed / 22 passed**。恢复后 `shared-tools.ts` SHA-256 均为 `b57c7bd18aca751b3804a6f43927fefd1d13b3b7122f1fd82595ecaf0259c75e`。
- 普通宿主 Read/Grep/Bash 的私有文件解析仍不覆盖；真实 DSH 桌面/profile 未重启加载，不声称已生效。
