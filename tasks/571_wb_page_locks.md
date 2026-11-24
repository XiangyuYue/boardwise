# 任务书：571 / W-B — recompile-with-locks 的模块覆盖与姿态拒绝

- 日期：2026-11-24
- 范围：TRIAGE **566-B-1 / B-2**，只修 agent-adjusted 的 recompile-with-locks。
- 执行：一个 coder；主代理独立复验。离线小批，不真机、不全量。

## ① 前因后果

`outputs/hole566/b/REPRO.md` 的两个生产探针已证明：

1. **B-1 会漏**：只点名 R1，page 锁反推整个模块原点，未点名 R2 同delta移动，其他模块也被 packer 重排；工作单却只列 R1。正确最低防线是：调用方必须给 PresentationSpec 证明模块成员，任一被点名模块只覆盖子集就拒绝并点名遗漏同伴；缺成员证明也 fail closed，不得继续靠猜。
2. **B-2 会造假结果**：证据 rotation=270/isMirror=true，page 锁不带姿态，重编译回 0/False；页锁检查又从被检图取姿态而恒等。正确最低防线是：recompile 策略遇到非 0 旋转（360 的整数倍除外）或镜像即拒绝，明确 page lock 只钉位置；direct-move 路径不变。

569 W-T、570 W-A 已验收并在工作树，必须保留。不得通过扩大工作单到未知器件、添加 page rotation 字段、放宽锁检查或修改 pagecompiler 来遮洞。

## ② 当前树状态

- HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合未提交，零 git 写。
- `src/boardwise/cli.py` 含 569/570，当前 SHA `6139d13bd967986a4747d909e18e1f3be73da07e1602b6f4ff5536f2ecd87bc5`。
- `engines/agentadjusted.py` 当前 SHA `6f701948c0f77c2eef5f3b1df676dfcfa0f0fe8eff65ba77e339596eafc83cf6`，为 HEAD 原样。
- `commands/draw.py` 当前 SHA `7762f54313f33362bdc4482d675ce93e22a68699e5e97b232b4ccdd62c529333`，为 HEAD 原样。
- `tests/test_agentadjusted.py` 为 HEAD 原样；`_posed_evidence()` 目前让 R31 rotation=90，且 recompile 正例预期成功——这正是 B-2 要改的旧预期。成功 recompile 夹具应改自然姿态，另加 direct-move 旋转正控制，不能删除负例。
- 569/570 文件、563 文件、`tasks/568_draw_holes_wave3.md`、PROGRESS/handoff/roadmap/TASKMAP/review-line 与临时件均保留。

现状：`agentadjusted.py:67-200 _recompile_with_locks` 只检查 x/y 与跨页；`:203-313 propose_agent_adjusted_move` 没有 PresentationSpec 输入；`cli.py:17374-17407` 只读 evidence；`commands/draw.py:803-834` 没有 `--presentation`。

实施前 cp 备份本批生产文件到 `.tmp_571/backup/`，记录 SHA；禁用 git 恢复。

## ③ 文件域与禁触清单

允许新建/修改仅：

- `src/boardwise/engines/agentadjusted.py`
- `src/boardwise/cli.py`（仅 move-propose 读取/转发 PresentationSpec）
- `src/boardwise/commands/draw.py`（仅 move-propose `--presentation` 注册与 help）
- `contracts/cli/v1.json`（只用官方生成器更新）
- `docs/draw.md`（仅 page-lock / recompile-with-locks 的现行约束说明）
- `tests/test_agentadjusted.py`（更新成功夹具姿态并增加 B-1/B-2/CLI 回归，不删负例）
- 本任务书、`.tmp_571/`、`.tmp_pt_571/`、`evidence/571/`

禁止：

- `engines/pagecompiler.py`、`core/presentationspec.py`、`core/changeplan.py`、drawcompiler/readability/moveblock；不改锁的几何含义。
- 569/570 的其它 hunk与测试；563/568、fixtures、connector、dsh-plugin、outputs 历史证据。
- 不新增 DSH 工具，不 bump/package/release；`--presentation` 只是既有 CLI 子命令的可选参数，无新 action。

## ④ 交付物与验收

### 先红回归（生产改动前真实运行）

在 `tests/test_agentadjusted.py` 固化：

1. **缺成员证明拒绝**：recompile-with-locks 未给 PresentationSpec 时 ValueError，CLI exit 5 且不写工作单；direct-move 不需要它且文档键/字节保持旧合同。
2. **模块子集拒绝**：PresentationSpec 的 sense 模块含 R1/R2，只选 R1 必须 ValueError 并点名 R2；CLI 同样 exit 5 点名 R2。覆盖两个完整模块的正控制可成功，不能只支持单模块。
3. **完整模块成功**：选 R1/R2 且 rotation=0/isMirror=false，锁仍为 `partId/x/y/scope=page`，无 rotation；`presentationSpecReview` 说明成员证明来自给定规格，未选模块仍可能由 page packer 重排、必须审查完整计划，不冒称只改两件。
4. **姿态拒绝**：rotation=90/270、isMirror=true 分别拒绝，错误明确 page lock 不保存姿态并建议 direct-move；360/-360 可作为等效 0 的正控制。direct-move 对 rotation=90 的输入仍成功。
5. **CLI 合同**：`--presentation` 只在 recompile 时成为必需证明；解析错误/缺文件 exit 2/5 按现有错误分类且不写输出。官方 `tools.cli_contract --write` 后合同一致，无其它参数漂移。

### 实施口径

- `propose_agent_adjusted_move(..., presentation=None)` 增加可选输入；仅 recompile 要求它。用 `PresentationSpec.modules[].parts` 与设计器名（大小写归一）求覆盖：被点名的每个模块必须全成员都被选中，被选器件必须能归属至少一个模块；遗漏者逐个点名。
- 只检查被点名模块的完整性，不把全页所有器件强塞进工作单；但必须在 review 文案中披露未选模块仍可能由页编译器重排，需审查完整重编译计划。
- 姿态守卫在生成 locks 前执行：有限数值 rotation，取模 360 非 0 或 isMirror 为真即拒绝；NaN/inf/非数值不得穿过。
- CLI 加载 PresentationSpec 并转发，direct-move 返回文档形状不变；`contracts/cli/v1.json` 只能 `.venv/Scripts/python.exe -m tools.cli_contract --write` 生成。
- 不改 page lock 的 key 集，不给它添加 rotation/mirror，不改 direct-move。

### 修后测试与变异

至少运行并留汇总：

```bash
.venv/Scripts/python.exe -m pytest tests/test_agentadjusted.py -q --basetemp=.tmp_pt_571/new
.venv/Scripts/python.exe -m pytest tests/test_057_draw_page_cli.py tests/test_569_title_block.py tests/test_570_empty_page.py tests/test_540c_contracts.py tests/test_540_cli_draw.py tests/test_doc_claims.py tests/test_owner_rules.py tests/test_layer_rules.py -q --basetemp=.tmp_pt_571/neighborhood
.venv/Scripts/python.exe -m tools.cli_contract
```

至少三项生产变异，各自 cp 备份→指定测试红→cp 恢复并核 SHA：

1. 去掉/绕过模块覆盖检查 → R1 子集用例红；
2. 去掉/绕过姿态守卫 → rotation/isMirror 用例红；
3. CLI 不读取/不转发 `--presentation` → CLI 缺证明或子集用例红。

交回实际错误文案、成功正控制、CLI 合同读数、测试汇总、三项变异与最终 SHA。证据 `evidence/571/`，日志 `.tmp_571/`。

## ⑤ 纪律与红线

- 零 git 写、零删除、零真机/daemon/编辑器；不跑全量 pytest；探针单进程，前台带 timeout。
- pytest 独立 basetemp，禁 `-n auto`/`-n >4`。
- 不通过修改旧成功用例来保留旋转重编译；只能把它改成合法自然姿态正控制并新增明确拒绝。不得删既有负例、skip/xfail。
- 不新增第二套 planner，不改页框/预算/阈值，不伪造 `automatic` 或证明标记。
- 本批不交付新原理图，真机逐脚/视觉不适用、未做。

## ⑥ 预算与交卷格式

- 一个 coder，最多 **40 步或 30 分钟**，不派下一级代理。
- 正文 ≤2000 字：`实际改动` → `先红/修后绿实测` → `三变异与 SHA` → `未做/红项`。
- 有本批红项、缺 CLI 合同或缺变异，只能交「停止/未完成」。同一拒因两轮无新证据即停止交接。

## 交卷（2026-11-24，coder）

566-B-1 / B-2 已闭合，证据 `evidence/571/REPORT.md`、日志 `evidence/571/*.log`、错误文案 `evidence/571/messages.txt`。

- 生产改动：`agentadjusted.py`（`presentation` 成员证明 + 姿态守卫）、`cli.py`/`commands/draw.py`（`--presentation` 读取与转发）、
  `contracts/cli/v1.json`（官方 `--write` 重生成）、`docs/draw.md`（page-lock/recompile 现行约束一段）、`tests/test_agentadjusted.py`。
- 实测：`tests/test_agentadjusted.py` 50 passed；指定邻域 8 文件 226 passed；`python -m tools.cli_contract` exit 0。
- 先红：37 failed / 13 passed（缺参数/缺 flag，非夹具意外）。变异 4 项各自红，cp+SHA 还原
  （agentadjusted `076ec2bb…fc9b4b`、cli `f1f44e48…2217100`）。
- 未做：真机/daemon/编辑器、全量 pytest、git 写、删除。披露：合同由官方生成器整体重写，因此同时吸收了工作树里
  570 面 `sch.geometry` help 漂移（本批自身漂移仅 `--presentation`）。
