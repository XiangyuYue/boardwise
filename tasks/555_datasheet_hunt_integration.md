# 555：批量手册链接入 live 审查与 DSH（实现与试点完成，未提交）

## 1. 前因后果

实际审查一次缺几十份手册，工程师逐颗找 PDF 不可持续。上游主要让 Agent 读原厂 PDF 并保存页码证据，没有等价的整板批量闭环。仓库已有 `parts hunt` 三阶段：C 号下载/缓存、MPN 搜索工单与 `--apply`、AI facts+quotes 与 `--apply-facts`、三档 facts trust；但 CLI 只收离线文件，不能消费 live 工程，也不能只处理 checkup 的未知项，DSH 没有入口。

岳 2026-11-19 批准把现有链接入 checkup/DSH，并拿本次二十几颗器件试点。不得另写第二套下载、事实或信任判定。

## 2. 当前树与基线

- 主仓 `E:/boardwise` 是混合工作树；552/553/554 位号修复及绘制线、bridge 等未提交改动均保留。
- `src/boardwise/cli.py` 含其他线未提交 hunks；只允许改 `_cmd_parts_hunt` 必要段，禁止覆盖或还原整文件。
- `commands/review.py`、`dsh-plugin/src/index.ts` 当前无本批前改动；绘制线 `dsh-plugin/src/draw-tools.ts` 和生成物不许碰。
- 旧 `parts hunt --file --out` 行为、输出字段、缓存、审计、退出码、三档 trust 必须不变。

## 3. 公开合同

### CLI

- `parts hunt --file <archive> --out <dir>` 旧入口不变。
- 新增 `--live` 与可选 `--project/--instance`，复用 `_load_model_online`；只接受 `project-file` 或 `per-page` 全身份读数。`netlist` 档没有 MPN/身份，返回 3 并明确原因，不得把整板写成 no-identity。
- `--file` 与 `--live` 二选一，缺任一为 2；`project/instance` 只能配 live；`--live --offline` 拒绝为 2，避免把在线读取与零外呼混为一谈。
- 新增 `--from-report <checkup/report.json>`：只处理报告 `needs_datasheet[].designator` 选中的器件；空清单产生零器件报告、零外呼。报告缺该键、模型缺所选位号、形状不支持均为 2，不静默全板扫描。
- `--limit` 在报告过滤之后生效；其余 `apply/apply-facts/cache/no-cache/shelf` 语义不变。
- live 报告的 board 增加 `source`（tier/project 等）；离线字段与字节形状不增加。`shelf` 仍必须显式路径，绝不默认改用户架；`verified` 仍只能人工授予。

### DSH

- 新工具 `boardwise_parts_hunt`，位于旧八工具之后、draw 工具之前，旧顺序不变。
- 参数：`file/project/instance` 三选一；`out` 必填；可选 `fromReport`、`offline`、`limit`、`cache`、`noCache`、`shelf`、`answers`、`claims`。
- `answers` / `claims` 是数组，插件机械写入自己的 transport temp 文件，再传 `--apply` / `--apply-facts`；验证、信任、结论全留 Python。
- 返回 `executeCli` 文本摘要与四个既有产物路径：hunt-report.json、hunt-plan.json、hunt-report.md、hunt-audit.jsonl。不得把几十份 PDF 文本塞进模型上下文。
- 不新增默认货架写入，不自动联网搜索；在线 hunt 由用户/Agent 明确调用，audit 继续只允许 C 号或 MPN 外发。

### 审查编排

`checkup` 仍先出首轮报告，不隐式联网。needs_datasheet 非空时调用 hunt；先处理 C 号，MPN-only 搜索后用 answers 回灌，AI 每批 3–5 颗只读相关章节，claims 过闸后重算受影响审查。最终分「自动取得 / 机器核验待签字 / 仍需人工」三栏，不宣称 machine_verified = complete。

## 4. 文件域与禁触

A（CLI）：`src/boardwise/cli.py` 的 hunt 段、`commands/review.py` 的 hunt 注册段、新增 `tests/test_555_parts_hunt_live.py`、`docs/parts.md`、`.tmp_555/`、`evidence/555/`。

B（DSH）：新增 `dsh-plugin/src/parts-hunt.ts` 与 `tests/parts-hunt.spec.ts`；`dsh-plugin/src/index.ts`、`tests/register.spec.ts`、`dsh-plugin/README.md`；构建产生的对应 `lib` 文件。不得改 `package.json` 版本、draw 工具或他人文件。

C（文档路由，后续小批）：两份同步 boardwise SKILL 与 `docs/review-sop.md`。

禁改：552/553/554 以外不相关源码、绘制线、fixtures/reviewsets、真实工程文件、全局 `~/.boardwise/parts.json`、历史证据。试点货架只放 `.tmp_555/`。

## 5. 验证与负对照

- A：旧 520/521/522 全部聚焦；live project-file/per-page 成功，netlist 拒绝；file/live 互斥、缺输入、offline+live、坏报告/缺位号、空清单零外呼；离线旧测试无变化。
- B：fake spawn 验证 argv、三选一、fromReport、apply/claims 文件、显式 shelf、四产物、错误传播和注册顺序；typecheck/test/build。无真实 daemon 假验收。
- 主代理独立变异至少两处：撤掉报告过滤会多处理器件；DSH 丢掉 fromReport 或错误路由必须红。
- 真实试点先重新 `bridge status` 与 `document.current` 确认身份，只读 live 工程，写操作仅限本地输出/缓存/试点货架；真实 EDA 设计零写入。
- 真机只读取公开器件身份对应的 C 号/MPN；不向搜索或下载请求发送工程名、板名、网名或客户信息。
- 不跑全量作为侦察；集成点按受影响 Python + DSH + 合同/卫生测试。未跑四线不得称全量通过。

## 6. 纪律与交卷

- 每批先 `cp` 备份既有目标到 `.tmp_555/backup-<域>/`，记录哈希；变异只用 cp 恢复。
- 零 git 写、零 `rm/unlink`、零发布、零全局货架写入、零真实设计写入。
- 子代理每批 ≤40 步/30 分钟，结论 ≤2000 字，实测命令→汇总→差异，不能只写“通过”。
- 若宿主/网络/原厂 PDF 不成立，保留可复现失败、audit 和剩余清单，不伪造自动完成或人工签字。

## 7. 实际交付与试点结论

实现、真实试点和聚焦验收已完成，全部留在工作树，未提交、未推送、未发布。权威读数与边界见 `evidence/555/trial-summary.md`：18 个身份行，4 份 claims 全部 accepted、0 rejected；真缺资料桶 20→17、机器待签 0→3，但 needs_datasheet 仍 15、verdict 仍 incomplete。插件包为 `.tmp_555/boardwise-dsh-0.6.3-beta.3.tgz`，未部署到 DSH profile。

真实试点后新增并验证两项身份约束：跨板同位号按 lcsc/mpn 分别寻址；多身份 sidecar 文件名带身份后缀。主代理两组独立变异均先红后 cp+SHA 恢复。未决人工项与 CLI 合同快照集成边界均按证据保留，未把机器档冒充人工 verified 或完整审查通过。
