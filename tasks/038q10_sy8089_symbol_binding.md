# 038Q10：SY8089 block 的真实 symbolRef 绑定

日期：2026-11-12。接续 038Q9。目标是让 module-import 能按模块 opt-in 使用受管 book，
并只给 `block.sy8089_buck_3v3` 绑定真实符号；不修改绘制语法，不在本批宣称 compile 通过。

## opt-in 合同

`contracts/module-import/curation.json` 顶层新增：

```json
"symbolBook": {
  "index": "blocklib/symbols/index.json",
  "profiles": "blocklib/symbols/profiles.json",
  "defaultIdentity": "generic"
}
```

仅 SY8089 block 资产新增 `identityBinding: "book"`。缺省资产仍走原 GENERIC 路径；
role_topology 若声明该值必须拒绝，本批不支持。声明 symbolBook 但无资产使用不是错误。

绑定开启后，该模块每个 part 必须同时在 catalog 与 CircuitSpec 得到 book 中的同一
`symbolRef`，任何 part 不得回落 GENERIC。deviceUuid 保留，symbolRef 不取 deviceUuid。

## 生成器校验（失败即整批不写）

Rust `module_import` 读取 index/profiles，两个文件进入 manifest.inputs，永不在 outputs：

- 实算 `index.profileBookSha256 == sha256(profiles.json)`；
- 每条 entry 实算 `profileSha256`（插入键序、indent=2、尾换行，与 Q8 同算法）；
- entry.maturity=candidate，bindings 中 deviceUuid 唯一，lcsc/mpn 与模块声明一致；
- 每个非通配 `role.pin` 必须以脚号或脚名**全等**命中对应 profile；禁止前缀/模糊匹配；
- 启用模块含任何 `*` 成员即拒绝，未启用模块保持原通配记录，不借机展开；
- 缺 book、缺 profile、重复 binding、哈希/LCSC/脚名不符、role_topology 开启均 Err，
  且输出目录不得留下半套新文件。

Q8 的完整 book 校验仍由 `tools/check_symbol_book.py` 负责；本批不是另写一套 geometry
算法或绕过该工具。

## catalog 状态

仅 SY8089 block：

- `identityStatus` 从 `unverified` 改为 `bound`，表示 device→symbol 绑定及哈希/脚名通过；
- `maturity` 仍 `candidate`，`notForDrawCompile` 仍 `true`，`unresolvedWildcards` 仍 `[]`；
- limitations 改为真实 book 来源及“离线编译/编辑器/硬件验收未完成”，不得保留“没读
  SymbolProfile”的旧句，也不得写可投板或可互换。

其余三个资产的身份、symbolRef、CircuitSpec 与限制保持原样；book 本身不修改。

## 文件域与验证

- `contracts/module-import/curation.json`、Rust core `module_import.rs` 及必要测试；
- `blocklib/modules/{catalog.json,manifest.json,circuits/sy8089_buck_3v3.circuit.json}`
  只能由生成器在新临时目录生成后复核复制；其他 circuit 必须逐字节不变；
- 新增 `tests/test_038q10_symbol_binding.py`，更新 Q2/Q8 中把“全部 GENERIC”钉死的断言为
  “SY8089 bound、其余不变”；
- 本任务书、`docs/rust-platform.md` 必要小节、`.tmp_038q10/`。

验证：Rust fmt/clippy/test、真实 CLI 生成幂等、Q10+Q2+Q8+module-import 邻域、
`tools/check_symbol_book.py`、文档声明。至少两处变异（哈希/脚名或回落）先红后 cp+SHA-256
恢复。零真机、零部署、零 git 写，暂不跑全量。

## 后续边界

本批只证明真实身份绑定。PresentationSpec 与离线编译另批处理；不得修改
`engines/grammar/**` 来迎合本批。若现有 `ic-periphery` 不能完整表达 buck，记录缺口交绘制线，
不在 CBB 生成批里改绘制算法。

## 实施记录（2026-11-12，子代理执行）

- 合同：`contracts/module-import/curation.json` 顶层新增 `symbolBook`（`index`/`profiles`/`defaultIdentity:
  "generic"`）；仅 `block.sy8089_buck_3v3` 新增 `identityBinding: "book"`，其余三个资产一字未动。
- Rust（`rust/crates/boardwise-core/src/module_import.rs`）：`read_symbol_book` 把两文件读进
  `manifest.inputs`（永不进 outputs）；校验 index schema、`notForDrawCompile=true`、`profileBookSha256`、
  逐条 `profileSha256`（新增公开 `profile_digests`：serde_json 默认 map 会排序键，故不重渲染，
  而是从 book 原文取该 profile 对象字节、去掉“数组元素”缩进——算法与 Q8 逐字节等价，实测 19/19 命中）、
  `maturity=candidate`、binding 内 `deviceUuid` 唯一、lcsc/mpn 与模块声明完全一致、每个 `role.pin`
  以脚号或脚名**全等**命中、启用模块含 `*` 即拒绝、`role_topology` 声明即拒绝、`defaultIdentity` 非
  `generic` 拒绝、缺 book 拒绝。通过后 catalog 与 CircuitSpec 同得同一真实 `symbolRef`，
  `identityStatus=bound`（`maturity`/`notForDrawCompile` 不变），limitations 换成真实 book 来源 +
  「离线编译/编辑器/硬件验收未完成」，旧「没读 SymbolProfile」句与 GENERIC 字样均不再出现。
- 生成物：真实 CLI 三次（`.tmp_038q10/gen1`、`gen2`，变异还原后再跑 `gen3`）逐字节一致；仅
  `catalog.json`、`manifest.json`、`circuits/sy8089_buck_3v3.circuit.json` 三个允许文件复制进
  `blocklib/modules/`（无删除），另三份 circuit 与 `upstream/LICENSE`、`blocklib/symbols/*` 逐字节不变
  （sha256 前后比对，见 `.tmp_038q10/before.sha256`）。
- 测试：`rust/crates/boardwise-core/tests/module_import.rs` 改 3 处旧断言 + 新增 11 个用例（1 个 reseal 对照、
  9 个拒绝路径、1 个绑定断言）；新建 `tests/test_038q10_symbol_binding.py`（8 个用例）；Q2 改 allowlist
  （`symbolBook` / `identityBinding`）并把「全部 GENERIC」改成「SY8089 bound、其余不变」；Q8 改 catalog
  symbolRef 与「book 是输入不是输出」两处。
- 验证读数：`cargo fmt --check` OK；`cargo clippy --all-targets -- -D warnings` 干净；`cargo test` 15 个
  test binary 全绿（core `module_import` 41 passed）；`tools/check_symbol_book.py` exit 0（19 profiles）；
  `pytest` Q10+Q2+Q8+doc_claims+540_shared_connectivity+540_shared_naming = 157 passed
  （`--basetemp=.tmp_pt_038q10`，未跑全量）。
- 变异（3 处，cp 备份 + SHA-256 还原，恢复后与备份字节一致 `3b21c45a…`，全绿复验）：① profile 摘要比较
  短路 → `a_book_whose_profile_digest_moved_is_refused` 红；② 脚名匹配放松为双向前缀（模拟“模糊匹配”）
  → `a_pin_that_only_prefixes_a_profile_pin_name_is_refused` 红；③ lcsc/mpn 比较短路（模拟“回落/跳过绑定校验”）
  → `a_binding_whose_lcsc_contradicts_the_part_is_refused` 红。
- 未覆盖边界：PresentationSpec 与离线编译未做（另批）；`ic-periphery` 能否完整表达 buck 未评估（缺口交绘制线）；
  真机/网络/部署/git 写零动作；`engines/grammar/**` 与绘制算法未触碰。

## 主代理独立复验（2026-11-12）

- Rust fmt/clippy/test 全部通过，core `module_import` **41 passed**；`tools/check_symbol_book.py`
  exit 0（19 profiles）。主代理 Python 组合 **105 passed**，`git diff --check` 通过。
- SY8089 的 catalog 为 `identityStatus=bound`，七个 part 的 catalog/CircuitSpec symbolRef 一致；
  maturity/notForDrawCompile 不变，其余三份 circuit 与 book 未改。后续离线试点见 038Q11。
