# 038X：默认货架路径与缺失披露

日期：2026-11-06。来源：`D:\dsh\boardwise-reviews\boardwise-bug-shelf-not-loaded.md`。本批修复 facts 层在非仓库 CWD 下静默失效，不改规则判据、货架内容、DSH 工具面或真机。

## 1. 根因与公开合同

- 非 frozen 的 `default_library_path()` 返回字面量 `blocklib/parts.json`，由进程 CWD 解析；`core.parts.load_parts` 又故意把缺文件读成空货架（写入侧需要能创建新架）。两者叠加，使只读审查把“文件不存在”静默当成“货架为空”。
- `DEFAULT_LIBRARY_PATH` 常量保留为文档/帮助中的仓库相对名称和 broken-bootstrap 回退，不改变含义。
- 非 frozen 的默认读写路径统一改为 `resources.parts_library()` 的绝对路径，定位到当前 checkout 的 `blocklib/parts.json`；frozen 的用户架/内置架优先级与合并逻辑不变。DSH 不再依赖 spawn CWD，无需插件侧补丁。
- `load_parts` 的“缺文件可创建空架”底层合同不变；缺失判定放在只读入口，避免破坏 `parts add/fetch` 的创建语义。

## 2. 只读入口与报告

1. `_read_default_shelf` 统一检查本次实际读取的每条路径：
   - 路径不存在或不是文件 → 返回 `(None, 具体路径与原因)`，不返回空 PartLibrary；
   - 文件存在但 0 条 → 返回空架，并用 note 明确“这是空货架，不是读取失败”；
   - 多路径默认合并时任一必需路径缺失 → 不把残缺合并伪装成完整覆盖。
2. `_checkup_shelf` 复用同一入口，不再让显式 `--library` 绕过缺失检查。架构、parts show/list/missing 等既有只读消费者共享同一行为；写命令不走该限制。
3. checkup 在货架不可读时增加顶层 `shelfMissing: true`（缺席而非 false 的加性字段），`shelfPath` 保留实际路径，`source.notes` 与 Markdown 继续给出原因；`completion` 不得把 facts 层不可用写成完整审查。空货架不得设置该键。
4. `parts show <真实空架里的不存在的 key>` 保持“未命中”语义与退出码；`--library <不存在路径>` 必须变成明确的货架读取失败，不能与 0 entries 的未命中相同。
5. 默认 `shelfPath` 从相对字符串变成绝对路径是有意修正；显式 `--library` 仍逐字使用用户输入。旧 findings 除恢复应有 facts 覆盖外不得被规则语义改动。

## 3. negative control

- 在无 `blocklib/` 的临时 CWD 中，默认 `default_library_path()` 仍命中仓库货架；同一份夹具用默认路径与显式绝对路径的 `reviewedByShelf` 一致。
- 显式缺失路径与默认缺失路径均返回 None、可读原因和 checkup `shelfMissing=true`；不写“空货架已加载”。
- 真实 0 条 JSON 货架与不存在路径在 `parts show` 的文案和退出码上严格区分。
- frozen 的用户架/内置架优先级、创建新架的写入路径、显式单架不合并且顺序不变。
- 默认 CWD 变化只影响路径解析，不改变模型、规则阈值或绘制行为。

至少两次变异：非 frozen 默认路径退回 CWD 相对值、缺文件被当空架；测试必须转红后用 cp+SHA-256 恢复。

## 4. 兼容矩阵

| 维度 | 本批覆盖 | 不得声称 |
|---|---|---|
| checkout | 任意 CWD 的绝对默认路径、缺失/空架披露 | 不声称所有旧文案保持相对路径 |
| frozen exe | 既有资源/用户架逻辑与回归 | 未重打 exe 时不声称新包已验证 |
| 在线/离线 | 离线文件与 CLI/DSH 共用入口 | 在线真机未重跑 |
| 读/写 | 只读缺失拒绝；写入仍可创建 | 不把写入侧缺文件改成错误 |
| 普通器件/CBB | 普通 facts 货架 | CBB 未覆盖 |

## 5. 文件域与验收

- `src/boardwise/rules/facts.py`、`src/boardwise/cli.py` 的必要段。
- `tests/test_038x_shelf_resolution.py` 及受影响的 resources/facts/parts/checkup 既有测试。
- 本任务书；完成后同步 review-line、TASKMAP 与 handoff。

禁止改 `blocklib/parts.json`、fixtures、绘制线、DSH/connector/Rust 业务实现、真实工程；零 git 写、零删除、零真机。聚焦后按串行纪律跑全量及四线。

## 6. 聚焦证据（子代理 2026-11-06）

实现域：`src/boardwise/rules/facts.py`（非 frozen `default_library_path()` →
`resources.parts_library()` 绝对路径，`DEFAULT_LIBRARY_PATH` 与 frozen 顺序不变）、
`src/boardwise/cli.py`（`_read_default_shelf` 路径检查 + 空架 note、`_checkup_shelf` /
`_architecture_shelf_evidence` 统一走它、`_parts_library_path(writable=True)` 同答案、
`_checkup_report(shelf_missing=)` 加性 `shelfMissing`、`_coverage_section(shelf_unreadable=)`
→ `coverage.shelfUnreadable` + `verdictWhy` 条款 + incomplete 闸、`parts show` 货架读不了
退出码 3）、新 `tests/test_038x_shelf_resolution.py`（20 条）。既有断言按新行为改：
`test_resources.py` 两条 checkout 用例、`test_191b_shelf_merge.py` checkout 分支、
`test_187b_gate_holes.py` checkout 分支。

读数：`tests/test_038x_shelf_resolution.py` 20 passed。聚焦批（本文件 + resources /
facts_library / 191b / 039 / parts_library / checkup_cli / 192c / 187b / 126b / 186 /
188b / 522 / 039c）**415 passed, 1 skipped, 5 failed**；5 条失败为工作树既有
`blocklib/parts.json` 数据漂移（`git show HEAD:blocklib/parts.json` 109 条 vs 工作树 110 条，
`fact_verified` 一条不同），与本批路径解析无关，货架文件 sha256 本批前后一致
（`3081197f…9262`）。

变异（cp 备份 + SHA-256 还原，均绿后字节一致）：
① 非 frozen 默认退回 `DEFAULT_LIBRARY_PATH` → 4 红（默认绝对路径 / tmp CWD 查询 /
写目标 / 默认与显式一致）；
② `_read_default_shelf` 跳过路径检查（缺文件当空架）→ 10 红（缺失披露、目录、多路径、
show 退出码、checkup `shelfMissing`、arch 证据）。

主代理独立复跑 `tests/test_038x_shelf_resolution.py` + `tests/test_checkup_cli.py`：**79 passed**。
`parts show` 的货架不可读退 3 与真实空架未命中退 2 为有意区分；`parts list` 保持旧退 2，未扩大命令面改动。

执行异常记录：子代理首轮探针未隔离 `BOARDWISE_HOME`，在真实 home 生成了一份
`~/.boardwise/design-intent/file-871d6d74ad8a.json` 模板。随后 `_checkup` helper 已统一设置临时
`BOARDWISE_HOME`，后续测试不再写真实 home。该既有文件未擅自删除，待岳决定是否回收；本批未修改任何真实工程。

## 7. B5 收尾：黄金生成器脱敏（子代理 2026-11-06）

**触发**：038X 之后官方 `python -m tools.build_differential_fixtures` 直接失败
`review-report-projection: unsanitized machine path 'E:/boardwise' survived`——`shelfPath` 由相对拼写变成当前
checkout 绝对路径，而 `_clean_text` 只认 RUN_ROOT / WORK / fixtures / home，不认 checkout 根。修生成器，
不动规则、不手改黄金。

**生成器改动**（`tools/build_differential_fixtures.py`，唯一实现文件）：
1. `_clean_text` 增加 `(ROOT, "<REPO>")`，**放在最后**——RUN_ROOT、WORK、`tests/fixtures/`、home 都是同一
   前缀下更窄的说法，必须先命中；自由文本（`source.notes`、triage note 里的 `--out`）因此不再带出 checkout 根。
2. 新增 `DEFAULT_SHELF = "blocklib/parts.json"` 与 `_shelf_path(value)`；`_sanitize` 对 `key == "shelfPath"`
   走它：**当前 checkout 的默认货架**（`ROOT/blocklib/parts.json`）发布成仓库相对名，其余拼写只做文本
   脱敏——显式 `--library` 是调用者自己的字符串，仓内路径丢根成 `<REPO>/...`，外机绝对路径**保持绝对**
   交给 `_assert_clean` 的 `RESIDUAL_ABSOLUTE_PATH` 拒绝，绝不改写成 `blocklib/parts.json`（那会声称一个
   本次没读的货架）。
3. manifest `sanitization` 增两条（`<REPO>` 与 shelfPath 规则）。所有发布物仍逐份过 `_assert_clean`。

**重生成 diff**（`.tmp_b5_generator/backup/differential` 与现文件 `diff -rq`）：只动 2 个文件——
`inputs/review-report.json`（sha256 `2b2a021e…` → `f0818da8…`）与 `manifest.json`（`ac0894cf…` → `6f3c1867…`）；
`cases.json`（`442d57b4…`）与其余 14 份 inputs **字节不变** → 几何/投影/合成源零翻转。report 内三处 hunk，
`"shelfPath": "blocklib/parts.json"` 一行**字节未变**（泄漏消除点在此，脱敏成功即是这个结果）：
- `parseStats` 增 `consistency_duplicate_groups` / `consistency_unresolved` / `deleted_documents`（**038W**
  的解析器改动，工作树既有，不在本批文件域）；
- `completion` 后新增 `partialVersion` / `partialCategories`（**541** 的 R4，同样工作树既有）；
- `completion.sourceVersions.rulebody` `541db813` → `424e2fd2`。

**指纹**：direct `1854fea9` → **`626e16ef`**（038X 改 `rules/facts.py`，顶层文件，直接口径覆盖它）；
recursive `541db813` → **`424e2fd2`**（038X 的 facts.py + 529 的 `rules/pcb/distance.py`）。manifest
`producerVersions.rulebody` 与 report `completion.sourceVersions.rulebody` 两处都是 `424e2fd2`；`ruleset`
仍 `a0c5e0a0`。`tests/test_126a_pcb_review_plumbing.py` 的两个断言按此重钉，注释写清归因（B5 本身没碰
`rules/` 任何文件）。

**幂等**：同一命令连跑两次，两个改动文件 sha256 各自一致（`sha256sum -c` OK）。

**负例**（`tests/test_540c_generator_validation.py` 新增 5 个用例 / 7 例）：默认绝对 shelfPath → 相对名且过
clean；note 里带 ROOT → `<REPO>/blocklib/parts.json`，`_forbidden_markers` 全无、`RESIDUAL_ABSOLUTE_PATH`
不命中；`D:/…`、`/home/…`、`F:\…` 三者**不被改写**且被 `residual absolute path` 拒；相对拼写逐字通过；
端到端 `_render`：绝对 shelfPath + ROOT note 的真实报告形状渲染后 `shelfPath` 仍相对、note 为 `<REPO>/…`。

**读数**：`tests/test_540c_generator_validation.py test_540c_differential.py test_540c_contracts.py
test_126a_pcb_review_plumbing.py test_038x_shelf_resolution.py -q -n 4 --dist loadfile
--basetemp=.tmp_pt_b5_generator` → **129 passed**。

**变异**（cp 备份 + SHA-256 还原，还原后 `cmp` 字节一致）：
① 删 `(root, "<REPO>")` → 2 红（note 占位符、端到端渲染）；
② `_shelf_path` 去掉默认名映射 → 2 红（默认货架名、端到端渲染）；
③ 任何绝对 shelfPath 都改写成默认名 → 3 红（三条外机路径用例）。

**未做 / 遗留**：全量与四线未跑（本批只动 `tools/` 与两个测试文件，零生产代码）；黄金已吸收 038W/541
在工作树里既有的未提交产物——必须吸收，否则 manifest 的 `inputs` 哈希与 `rulebody` 会与实体文件互相打架，
但这两批的黄金同步严格说应回到各自任务书里记账；`.tmp_540/differential_build/run-*` 每跑一次生成器多一个
run 目录，未回收（删除需批准）。
