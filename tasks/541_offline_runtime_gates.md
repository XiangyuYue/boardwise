# 541：可离线运行时闸（R1/R2/R4 垂直切片）

日期：2026-11-06。上游：`tasks/review-stage-runtime-gates.md`。本批不碰绘制线、真实工程、DSH profile、规则判据或报告 verdict。默认行为保持；只有显式 strict 路径启用新拒绝。

## 1. R1：版本化 RunManifest 与语义 diff

新增 shared `core/runmanifest.py`：

- `SCHEMA="boardwise.run-manifest/1"`；`RunManifestError(ValueError)`。
- `sha256_file(path)`、`load_manifest(path)`、`write_manifest(path, manifest)`、`make_manifest(...)`、`manifest_baseline(manifest)`、`semantic_diff(old, new)`。
- manifest 是独立 `run.json`，**不是 report.json 的一部分**：`schema/runId/inputs/engine/intent/pages/channels/modelCounts/findings/drcReviewCount/newEvidence`。
  - inputs 行 `{path,bytes,sha256}`；engine 行 `{boardwise,ruleset,rulebody}`；intent 可空或 `{path,sha256}`；
  - channels 是实际证据状态；findings 是 CLI 传入的稳定身份字符串列表，core 不 import review 引擎；
  - drcReviewCount 从 1 开始，newEvidence 可空。
- `manifest_baseline` 只取 inputs/engine/intent/channels 的基准字段，不包括 runId/findings/modelCounts/drcReviewCount。
- `semantic_diff` 返回 `sameBaseline/inputsChanged/coverageChanged/addedFindings/removedFindings/multiVariableChange/attribution`。同基准时无 finding 增删归因；多变量变化必须标 `multi-variable-change`，不得归因单因子。finding 增删始终按身份集合给出。
- 读取拒绝坏 JSON、非对象、未知版本、非法路径/哈希/count；写采用同目录临时文件 + `os.replace`，不写真实工程。

负例：完全同基准、只换输入哈希、同时换归档与活动页、finding 增删、未知版本、缺文件、写后复读。

**R1 已实施（2026-11-06，纯 shared 切片，未接 CLI）**：`src/boardwise/core/runmanifest.py`
（owner=shared，不 import review；findings 只收调用方给的稳定身份字符串）、
`tests/test_541_run_manifest.py`（69 例）、`contracts/module-owners.json`（模块普查 145→146）。

- 公开面：`SCHEMA`、`RunManifestError`、`sha256_file`、`load_manifest`、`write_manifest`、
  `make_manifest`、`manifest_baseline`、`semantic_diff`。`make_manifest` 可缺省
  `runId`（新 uuid）/`intent`/`pages`/`modelCounts`（全 0）/`findings`/`drcReviewCount`（1）/
  `newEvidence`，字段本身仍完整落盘，避免 R2 自造调度字段。
- 基准只取 `inputs`/`engine`/`intent`/`channels`。`channels` 载入时补齐已知六通道
  （文档未提及 = 未采集 = `false`），因此 `sameBaseline` 与归因 token 由同一批变量推出；
  归因取值 `input:<path>` / `channel:<name>` / `engine:<field>` / `intent` /
  `multi-variable-change` / `None`，finding 增删永不参与归因。
- 读拒绝（一律 `RunManifestError`）：坏 JSON、非对象、未知 `schema`、未知键（含嵌套）、
  非法 path（空/NUL/`..`）、非法 sha256/bytes/count、重复 input path/page/finding 身份。
  写：先校验再开文件，同目录临时文件 + `os.replace`，失败不留临时文件也不损旧文件。
- 命令：`.venv/Scripts/python.exe -m pytest tests/test_541_run_manifest.py
  tests/test_owner_rules.py tests/test_540_cli_draw.py tests/test_540_cli_review.py
  tests/test_540_cli_shared.py -q -n 4 --dist loadfile --basetemp=.tmp_pt_541_r1`
  → **110 passed**（test_541 占 69）。日志 `.tmp_541_r1/pytest_final.log`。
- 变异（各 `cp` 备份 + SHA-256 还原，恢复后 `cmp` 字节一致，sha256 `958fa150…`）：
  ①把 `len(variables) > 1` 分支改成取 `variables[0]`（漏掉多变量）→ 2 红；
  ②`_identities` 改成 `split("|")[0]`（把 finding 身份当 message 比）→ 3 红。
  日志 `.tmp_541_r1/mutation1.log`、`.tmp_541_r1/mutation2.log`。
- 未做：任何 CLI 入口、`run.json` 落盘路径、退出码、`--new-evidence`——R2 仍待实施。

## 2. R2：`checkup --strict` 重算 guard

CLI 新增两个 opt-in 参数并更新 `contracts/cli/v1.json`：

- `--strict`：只支持 `checkup --file`；在线路径明确退 2，不连 daemon、不建 out/锁。
- `--new-evidence archive-bytes-changed`：声明项目归档字节已变；guard 必须用当前 SHA-256 与旧 manifest 对拍，不能只信这句话。其他理由本切片不支持，明确退 2。

在 `_cmd_checkup` 取输出锁之前执行：

- 无 `run.json` → 放行；
- 同 inputs/engine/intent 且无新证据：
  - `drcReviewCount >= 2` → `reject-needs-new-evidence`；
  - 否则 → `reject-use-existing`，提示改用 `review-read`；
- 同基准却给 `archive-bytes-changed` → `reject-evidence-not-new`；
- 基准已变 → 开新 run，并写 `run-diff.json`；不根据文件变化单独断言用户改了设计。

**拒绝必须发生在模型加载、规则、PCB runner、DRC、报告写出和输出锁之前**，退出码 2、stderr 含拒绝码；不得只打印警告后照跑。拒绝时不创建 out/锁。

放行后按原流程完成，并写：

- `run.json`（drcReviewCount 旧值+1、当前依赖/通道/模型计数/findings 身份）；
- 有旧 manifest 时写 `run-diff.json`（语义 diff 与实际 finding 增删）。

默认无 `--strict` 时不读/写这些文件、不改变任何旧调用、JSON、退出码和 monkeypatch 形状。Intent/library/interconnect 的实际路径与哈希必须进入基准，避免换证据却复用旧结论。

**R2 已实施（2026-11-06）**：`commands/review.py`（`--strict`、`--new-evidence`
choices、`NEW_EVIDENCE_ARCHIVE_BYTES/CHOICES`）、`cli.py`（R2 helper 段 +
`_checkup_out_preflight` 两条新拒绝 + `_cmd_checkup` 接线）、`contracts/cli/v1.json`
（`python -m tools.cli_contract --write` 重生成，check 模式复验一致）、
`tests/test_541_strict_reuse.py`（14 例）。

- 拒绝码与退出码（一律 2，stderr 逐字含码）：`reject-use-existing`（同基准、无新证据、
  count<2）、`reject-needs-new-evidence`（同基准、count>=2）、`reject-evidence-not-new`
  （声明 `archive-bytes-changed` 但当前归档 SHA-256 与旧 inputs 同路径行相同）、
  `reject-unreadable-manifest`（`run.json` 读不懂，**不**当首次运行）。
- 闸位：`_cmd_checkup` 里 `_checkup_out_preflight` 之后、`_checkup_report_stamp` 与
  `_checkup_lock_acquire` 之前；`_cmd_checkup_run` 与 `_run` 返回路径未改。改后写
  `run.json`/`run-diff.json` 在**锁内**、`_run` 返回之后（`_checkup_strict_record`），
  exit 0/1/3 且 report.json 存在才写；写失败只 stderr 提示、不改退出码。
- 基准（`_checkup_strict_baseline`）：项目归档（目录工程按 relpath+size+sha256 折叠成
  一个内容摘要）、`_checkup_shelf_path` 的绝对货架（默认 038X 路径）、显式
  `--interconnect`；intent 走 `core.architecture.project_uuid` +
  `cli._load_intent_contract`（不另造默认路径），文件不存在记 `null`；engine =
  `{_local_version, ruleset_fingerprint, rulebody_fingerprint() or "unavailable"}`。
  基准比较只取 inputs/engine/intent（channels 运行前不可知，故不进闸，只进 diff）。
- 报告派生（`_checkup_manifest_fields`）：pages=boards[].pages（缺则 source.pageUuid）、
  channels=evidence.channels 状态映射（`ok`/`not-applicable`→true，其余 false）、
  modelCounts=`{model.components, model.nets, summary.unreviewedParts}`、findings=
  `_checkup_finding_identities`（`triage_key` 的 `boardwise-rule` 配方，**全severity**，
  过 `disambiguate_triage_keys`/`triage_order` 消歧）。
- `run-diff.json` 不是 manifest schema：`_write_json_atomic`（同目录临时文件 + fsync +
  `os.replace`），内容就是 `semantic_diff(old,new)` 的七键。
- 实测：`.venv/Scripts/python.exe -m pytest tests/test_541_strict_reuse.py
  tests/test_541_run_manifest.py tests/test_checkup_cli.py tests/test_540c_contracts.py
  tests/test_owner_rules.py -q -n 4 --dist loadfile --basetemp=.tmp_pt_541_r2`
  → **200 passed**（14 例为本片，13 例 + 目录工程一例）。日志 `.tmp_541_r2/pytest_final.log`；
  `python -m tools.cli_contract` 复验一致。
- 目录工程（038F3 `.eprj3`）：基准取**工程根目录的内容摘要**（relpath+size+sha256 折叠，
  `_checkup_tree_digest`），不取那份 354 B 的 index——只哈希 index 会让重画过的 `sch/`
  页面复用旧结论。给目录或给目录里的 index 折叠成同一行（同为根目录路径）。
- 拒绝先后证据（真跑）：第二次同基准 run → rc 2，间谍
  `['_checkup_lock_acquire','_load_model',…]` **全零调用**；锁载体 `.checkup.lock`
  未创建、report.json 未写（用「run.json 拷进空目录」证明，不靠删文件）。
- 变异（各 `cp` 备份 + SHA-256 还原，恢复后 `cmp` 字节一致；变异在目录工程补丁**之前**的
  版本上做，被改的两处此后未再改动）：①把闸的拒绝从 wrapper 挪到 `_load_model` 之后
  → 3 红，证据 `AssertionError: a refusal reached ['_checkup_lock_acquire', '_load_model']`；
  ②`--new-evidence` 文案直接放行（去掉归档哈希对拍）→ 1 红（`assert 3 == 2`，
  同归档假理由照跑）。日志 `.tmp_541_r2/mutation1.log`、`.tmp_541_r2/mutation2.log`。
  最终 sha256：`cli.py 92c9d9b6…`、`review.py ceb05321…`、测试 `9a60c3b2…`。
- 未做/已知：`--new-evidence` 无 `--strict` 时在 preflight 退 2（本片自定，非任务书原文）；
  在线 strict 拒绝发生在 preflight（不连 daemon、不建 out/锁）；`run.json` 写失败不重试；
  R4 strict partial 已实施，R3 与公开接口 allowlist 未实施。

### 2.1 R2 复核修复 B（2026-11-06，B5 复核复现的四个洞）

只加固 R2 的重算闸，不动 R4/038W/X/529/527C2/绘制线/fixtures，零 git 写、零删除、零真机。

四个已复现的洞与对应加固（文件域：`cli.py` R2 helper 段、`tests/test_541_strict_reuse.py`、本文档）：

1. **`--out` 在 `.eprj3` 工程树内会自我哈希、永不拒绝**。`_checkup_tree_digest(root, out_dir)`
   新增 `out_dir`：`_checkup_out_skip` 把 `--out` 折成相对 `root` 的路径前缀，其下**全部**
   跳过（report.json / run.json / run-diff.json / 侧车 / 锁载体一并跳过）；`--out` 就是工程
   根本身时改为按名排除本轮的机器产物（`_CHECKUP_OUT_ARTIFACT_NAMES`：report.json/report.md/
   board-report.md/review-summary.md/architecture.md/design-intent.md/run.json/run-diff.json/
   .checkup.lock），工程内容照旧计入——否则「跳过 out 子树」等于跳过整个工程。另无条件跳过
   `.checkup.lock` 与原子临时文件（`.<name>.<rand>.tmp`，`_checkup_is_run_state`）。
   `_checkup_input_identity(path, out_dir)` → `_checkup_strict_baseline(args, out_dir)` 全链传
   `out_dir`（guard 传自己的 `out_dir`，record 复用 plan 的 inputs 因而同源）。
2. **`out/needs-datasheet.json` 新人工证据被漏**。`_CHECKUP_STRICT_SIDECARS =
   (needs-datasheet.json, warning-triage.json)` 存在才入基准（不凭空造行）：新增/修改/删除任一
   侧车都移动基准并放行，不再被 `reject-use-existing` 丢掉。intent/library/interconnect 三行不变。
3. **同字节换路径可绕过**。`_checkup_baseline_contents` 把 inputs 折成 `(bytes, sha256)` 多重集
   （丢 path 排序），同基准判定改用它：仅换路径 = 同基准 → 拒绝；不同哈希或增删输入才开新 run。
   带 `--new-evidence` 也照拒：归档路径与哈希都未变 → `reject-evidence-not-new`（541 R2 原码），
   只换了路径（基准换个名字回来）→ `reject-use-existing`（≥2 轮升
   `reject-needs-new-evidence`，`_checkup_strict_stop_code` 一处拼写）。
4. **写 manifest 失败无稳定 token**。`_checkup_strict_record` 两条未写路径（report.json 读不出 /
   `write_manifest` 抛错）stderr 均带固定 `STRICT_MANIFEST_UNWRITTEN = "run-manifest-unwritten"`，
   退出码不动（报告已交付则仍是 0/1/3）。

- 新增 6 例（本文件共 20 例）：out 在工程树内不自我哈希（并对照「不带排除的扫描确实会动」）、
  `--out` = 工程根的跨轮稳定、侧车新增/修改/离开各自移动基准并放行、同字节换路径（含
  `--new-evidence` 两种码）搁置、`run-manifest-unwritten` token + 退出码不变、锁载体与
  `.<name>.<rand>.tmp` 不进摘要（真实页面照旧会动摘要）。
  既有 `test_a_changed_library_or_intent_opens_a_new_run` 按新语义收窄为
  `test_a_changed_library_opens_a_new_run`（同路径改内容 → 新 run；仅换货架路径已属第 3 条）。
- 实测（任务书指定的聚焦命令）：
  `.venv/Scripts/python.exe -m pytest tests/test_541_strict_reuse.py tests/test_541_run_manifest.py
  tests/test_checkup_cli.py tests/test_540c_contracts.py -q -n 4 --dist loadfile
  --basetemp=.tmp_pt_b5_fix_b` → **191 passed**（`test_541_strict_reuse.py` 单跑 **20 passed**）。
  日志 `.tmp_b5_fix_b/pytest_first.log`（20 例单跑）、`.tmp_b5_fix_b/pytest_final.log`。
- 变异（三次，各 `cp` 备份 + `cmp` + sha256 还原；恢复后与备份字节一致）：
  ①`_checkup_tree_digest` 里丢掉 `out_dir` 排除（out 参与摘要）→ **2 红**
  （`test_an_out_dir_inside_the_project_tree_does_not_hash_itself`、
  `test_out_at_the_project_root_is_stable_across_runs`，
  `AssertionError: assert (69915, '69bb…') == (3275, '7479…')`），日志 `.tmp_b5_fix_b/mutation1.log`；
  ②`_CHECKUP_STRICT_SIDECARS` 只留 `warning-triage.json`（漏 needs-datasheet）→ **1 红**
  （`test_a_new_edited_or_vanished_sidecar_moves_the_baseline`，`assert 2 == 3`：带新标记的 run
  被当成同基准拒掉），日志 `.tmp_b5_fix_b/mutation2.log`；
  ③同基准判定退回整行比较（path 参与）→ **1 红**
  （`test_the_same_bytes_at_a_new_path_are_the_same_baseline`，`assert 3 == 2`：换路径的拷贝归档
  照样跑），日志 `.tmp_b5_fix_b/mutation3.log`。
  最终 sha256：`cli.py 9fdc778c…`、`tests/test_541_strict_reuse.py 3d395576…`
  （改动前 `cli.py 3d04e378…`；备份 `.tmp_b5_fix_b/cli.py.orig`、`cli.py.good`）。
- 未做/待裁：
  ①第 3 条里「带 `--new-evidence` + 同字节换路径」的拒绝码取 `reject-use-existing`（按任务书
  字面），同一归档同路径仍报 `reject-evidence-not-new`（保住既有测试与那句「字节没变」的诚实
  语义）——两码都是「拒绝、零工作」，若要求统一成一个码需裁定。
  ②`--out` = 工程根时按名排除的集合是本轮机器产物的白名单：run 若将来往 `--out` 写新文件名，
  需同步该集合（本轮跑通 report.json/run.json 两文件落地后摘要不变）。
  ③`_checkup_tree_digest` 的 `out_dir` 为可选参数（默认 `None`，无排除）：只为本段单测便利，
  生产两个调用点都传；如需强制可改为必填。
  ④未跑全量、未跑 connector/dsh-plugin/tsc/Rust 四线（任务书只指定聚焦命令）。

## 3. R4：严格 partial 四档披露（独立小片）

R3 DSH pre-execute 需要 profile 重启与独立加载授权，本批不自称实现。公开接口 allowlist 若没有明确的离线受管入口，不另造拦截层。

R4 只做 opt-in `review finalize --strict-partial`：

- `evidence.partialCategories` 是可选、版本化的披露字段，含 `confirmed/suspected/unverified/uncovered`，每类 `{count,items[]}`；`evidence.partialVersion=1`。
- checkup 在 `evidence.delivery.status=partial` 时生成它：confirmed=证据 ok/合法 N/A；suspected=有线索但不足；unverified=读取失败/缺采集；uncovered=本轮未查。每行 `{code,status,detail}` 直接引用已有通道/披露，不能凭板名猜。
- 默认 finalize 对旧报告保持现状；显式 `--strict-partial` 时，partial 交付缺任一类别、count 与 items 不一致、类别外状态、缺 needs-manual/open-item 都产生结构化 issue 并不签收据。它只校验披露，不把四档齐全写成板级通过。
- 默认 checkup 新字段是加性披露；`checked:false`/无 evidence 不补造。`review-read` 原样传递。

R4 与 R2 分开派单、分开聚焦验收；若四档映射无法从现有通道无歧义推导，先停并写清，不编造分类。

**R4 已实施（2026-11-06，opt-in 披露闸）**：`engines/evidence.py`
（`PARTIAL_CLASSES`/`PARTIAL_VERSION=1`/`partial_categories`/`_apply_partial_categories`）、
`engines/reviewfinalize.py`（`_check_partial_categories` + `validate_review_summary(..., *,
strict_partial=False)`）、`commands/review.py`（`--strict-partial`）、`cli.py`
（finalize 传参）、`contracts/cli/v1.json`（`python -m tools.cli_contract --write`
重生成，check 模式复验一致）、`tests/test_541_partial_categories.py`（32 例）。

- 字段落在 **evidence 节根**：`evidence.partialVersion`（int 1）+
  `evidence.partialCategories`（四类，每类 `{count, items[]}`，item 恰好
  `{code, status, detail}`）。`delivery.complete` 时两个键都 **pop 掉**（不是留空）。
  `delivery` 自身三键（status/note/requiredDisclosures）一字未动，`review-read` 原样透传。
- 映射（只用通道行与采集记录）：`ok` / 无 `errors` 的 `not-applicable` → confirmed；
  `failed` / 带 capability `errors` 的 `not-applicable` → suspected；`missing` → unverified；
  `unavailable` → uncovered；`liveCapture` 的 identity / focus 两条披露 → unverified。
  每行原样引用该通道的 `code`（`DISCLOSURE_CODES`）/ `coverage` 状态 / 行内 `detail`，
  采集行引用披露行的 `code`/`status`/`message`。六通道各一行（含闭通道的 confirmed），
  因此每条 `requiredDisclosures` 恰好出现一次。
- 重算点：`evidence_section`、`merge_live_capture`、`refresh_datasheets` 末尾统一走
  `_apply_partial_categories`；finalize 的 re-gate 走 `refresh_datasheets`，所以内存件
  永远与通道自洽（这也是为什么 CLI 侧 strict 的牙齿只剩 summary 里的 token）。
- 严格校验（只在 `strict_partial=True`）：版本缺/错（`partial-version-missing/invalid`）、
  字段缺（`partial-categories-missing`）、缺类（`partial-category-missing`，逐类）、
  未知类（`partial-category-unknown`）、count 非整数/与 items 不等
  （`partial-category-count-invalid`/`-mismatch`）、条目形状/状态/详情
  （`partial-item-shape`/`-status-invalid`/`-detail-invalid`/`-code-invalid`）、
  重复 code（`partial-item-duplicate`）、类别内容与派生不符（`partial-category-stale`，
  code 序列或同一 code 的 status/detail 都算）、必披露落空/重复
  （`partial-disclosure-uncovered`/`-duplicated`）、complete 残留
  （`partial-categories-on-complete`）、summary 缺 needs-manual/open-item
  （`summary-partial-token-missing`，复用 `_MANUAL_WORD_RE` 词表 + open-item 写法）。
  一律走既有 `{code,path,message}` 结构化 issue、沿用 finalize 退出码 1、失败零写；
  通过不碰 `report.conclusion`（有测试断言 `mayQuotePassed` 仍 false）。
- 默认路径不变：无 flag 时 `_check_partial_categories` 根本不调用，旧 partial 报告
  （无该字段）照旧通过；§3 的 "默认 checkup 新字段是加性披露" 由字段派生保证
  （`checked:false`/无 evidence 不补造）。
- 实测（本轮）：`tests/test_541_partial_categories.py tests/test_537c_evidence_coverage.py
  tests/test_537d_finalize_validation.py tests/test_537d_finalize_cli.py
  tests/test_review_stage_delivery.py tests/test_540c_contracts.py -q -n 4
  --dist loadfile --basetemp=.tmp_pt_541_r4` → **296 passed, 1 failed**（见「待裁」）。
  邻域加测 `test_537c_live_merge / test_537c_review_evidence_cli / test_537d_review_read /
  test_checkup_cli / test_540_cli_review` → **188 passed**。
  日志 `.tmp_541_r4/pytest_final.log`、`.tmp_541_r4/collateral.log`。
- 变异（各 `cp` 备份 + `git hash-object` 对拍，恢复后 `cmp` 字节一致）：
  ①`merge_live_capture` 直接返回原 dict（漏掉 merge 重算）→ 1 红
  （`test_merge_live_capture_classifies_the_merged_rows`，KeyError partialCategories）；
  ②缺类分支改成 `continue`（缺类不拒绝）→ 2 红
  （`test_strict_reports_a_missing_class`、`test_default_validation_ignores_a_broken_field`）。
  日志 `.tmp_541_r4/mutation1.log`、`.tmp_541_r4/mutation2.log`；恢复后
  `evidence.py 1370b083…`、`reviewfinalize.py 829906a7…`。
- **收尾（主代理裁定后，2026-11-06）**：
  ①`tests/test_537c_evidence_coverage.py` 的 `EVIDENCE_KEYS` 补
  `partialVersion`/`partialCategories`（本批加性字段；`delivery` 三键未动），该文件已全绿；
  ②**re-gate 洗白问题已修**：`_cmd_review_finalize` 在 `deepcopy(report)` 之前留
  `original_evidence = deepcopy(report.get("evidence"))`（缺失即 `None`），
  `validate_review_summary(..., partial_evidence=...)` 新增该可选哨兵参数；strict 时
  四类闸判**原始件**（用它自己的 channels/liveCapture 重算派生值，非法行剔除不炸），
  非 strict 与直接调用默认仍读 `report.evidence`，默认行为一字不变。于是
  `refresh_datasheets` 的内存重算不能再把「原始缺/坏四类」掩盖掉。
  ③新增 4 例（共 36 例）：闸判原始件而非重建件（双向）、无哨兵仍读报告、CLI
  「原始报告缺字段 → `--strict-partial` 退 1 / 码 `partial-categories-missing` /
  零写零收据，同一输入无 flag 退 0 并签收据」、「原始坏类不被洗白 → 退 1」。
  ④最终实测（同一条聚焦命令，`--basetemp=.tmp_pt_541_r4`）：**301 passed, 0 failed**；
  日志 `.tmp_541_r4/pytest_final.log`。CLI 证据：`.tmp_541_r4/` 见上两例的断言，
  收据仅在有 flag 且通过时生成。
- 未做：`review-read` 不渲染四档（报告 md/summary 字节未变，旧渲染契约保留）；
  没有暴露任何新的公开 allowlist 项；R3 未碰。

## 4. 验收与文件域

- R1：`core/runmanifest.py`、`tests/test_541_run_manifest.py`、owner 登记。
- R2：`commands/review.py`、`cli.py` 必要段、CLI 合同、`tests/test_541_strict_reuse.py`、既有 checkup 邻域。
- R4：`engines/evidence.py`、`engines/reviewfinalize.py`、`commands/review.py`、CLI 合同、相应生成/校验测试。
- 每片至少两次针对性变异，cp+SHA-256 恢复；全量在夜间总验收串行执行。

禁止改 fixtures、绘制线、真实工程、DSH profile、connector/Rust 业务实现；零 git 写、零删除、零真机。旧报告、旧 CLI 默认路径和旧退出码必须不变。

## 5. 最终验收（2026-11-06）

- R1 聚焦 **110 passed**；R2 初版 **200 passed**、加固后 **191 passed**；R4 **301 passed**；跨批最终聚焦 **333 passed**。文档与仓库卫生 **49 passed**，CLI 合同一致，官方差分生成器与脱敏聚焦 **129 passed**。
- 最终全量 Python：**9893 passed / 25 skipped / 14 failed / 1 warning，1293.73 s**。其中 12 条为工作树既有 `blocklib/parts.json` 数据漂移（110 条、候选条目及事实字段变化），2 条为既有 pytest 槽位 ACL 与 Git/MSYS `0xC0000022` 环境失败；不宣称全量全绿。
- connector **576 passed** + typecheck；DSH **129 passed / 1 skipped** + typecheck/build；Rust **111 passed / 4 ignored**，fmt/clippy/test 通过。
- 两路只读对抗复核及后续修复均完成：PAD_NET 编号不一致仅披露不改网、527C2 距离按 endpoint、R2 out 自我哈希/侧车/同字节换路径、R4 原始证据防 re-gate 洗白、生成器绝对路径脱敏与公开 `project_uuid` 跨层接口。
- 未提交、未推送、未发布、未跑真机；R3 与公开 allowlist 未实施。
