# 038Q8：受管 SymbolProfile book 与身份来源账

日期：2026-11-12。接续 038Q4/Q5/Q7。目标是让六份真实 profile 在 clean checkout 可加载、
可校验、可引用；不晋升模块，不改绘制输入，不接入 draw compile。

## 形态裁定

新增两个受管文件，**不放进 Rust 生成域 `blocklib/modules/`**：

- `blocklib/symbols/profiles.json`：只含 `{ "profiles": [...] }`，由既有
  `engines.drawapply.load_library` 直接读取。六份 profile 保持既有字段白名单，不往 profile
  对象里塞 deviceUuid/libraryUuid 等身份字段。
- `blocklib/symbols/index.json`：独立的身份、绑定、来源与哈希账。几何本体不重复保存，
  原始 elibz2/manifest/宿主响应仍只在 ignored 证据区，不是 clean checkout 的校验依赖。

准入范围仅为：AMS1117 主符号（Q4）、三个电容（Q5）、两种 SY8089（Q7），共六份。
没有其他“同族”“同封装”扩展，也不改 `blocklib/specs/` 的既有实测库。

## index 合同

根字段：`schema=boardwise.symbol-book/1`、`libraryUuid`、`notForDrawCompile=true`、
`profileBookSha256`、`profiles[]`。profileBookSha256 是 profiles.json 全文件字节哈希。

每条按 symbolRef 排序，至少包含：

- `symbolRef/libraryUuid/title/maturity=candidate`；
- `archiveSha256/geometryHash/profileSha256`；
- `reader=boardwise.parsers.elibz.load_elibz2_symbol`、`editorVersion=4.1.93`、
  `sourceTier=measured-live`、`acquiredOn`、informational `evidence[]`；
- `bindings[]`：已核 deviceUuid、lcsc、mpn、footprintUuid，以及实际存在的
  supplierFootprint/footprintName；不补没读过的字段。

`profileSha256` 的唯一定义：对该 profile 对象按插入键序
`json.dumps(obj, ensure_ascii=False, indent=2) + "\n"` 的 UTF-8 字节哈希；不改用 sort_keys。
`geometryHash` 必须调用现有 `profile.geometry_hash()` 实算。`source` 必须同时与 symbolRef
和 archiveSha256 对齐。三个 0805/0402 几何族可以相似，但 symbolRef/source 不得合并。

## 校验器与 clean checkout

新增 `tools/check_symbol_book.py`，只读受管 book/index/catalog，**不得读取 outputs 或网络**：

1. 既有 loader 真能读出六份 profile，index 与 book 的 symbolRef 集合、顺序一致；
2. 实算全文件、每份 profile、geometry、source/archive 哈希；
3. 每条 binding 在 `blocklib/modules/catalog.json` 的 parts 中能找到相同 deviceUuid，
   已声明的 lcsc/mpn/footprint 字段一致；catalog 缺字段不得补猜，未覆盖的其他 parts 允许存在；
4. evidence 只作来源说明，不要求文件存在，不含本机绝对路径；
5. `notForDrawCompile=true` 与 candidate 状态是发布边界，不谎称它是运行时绘制闸。

校验器实现 `validate_book(root) -> list[str]` 和 CLI，错误逐条指出对象/字段，非零退出；
不能只验证 JSON 语法或把缺证据 SKIP 掉。

## 负例与验收

新增 `tests/test_038q8_symbol_book.py`，所有变异在 tmp_path 的 book 副本中，不改真实数据：

- archive/profile/hash 任一字符变化必须红；tip 变化导致 geometry 红；
- 只改 valueRow/texts 时 geometry 不变但 profile hash 必须红；
- 删除/合并一条 SY8089 必须红；profile 内加入 deviceUuid 必须被现有 loader 拒绝；
- binding 与 catalog 冲突必须红；outputs 不存在仍必须完整通过；
- 六份真实数据通过，且不改 catalog/CircuitSpec/module-import manifest/notForDrawCompile。

至少两处对校验器的真实变异（去掉 archive 校验、geometry 校验），先红后 cp+SHA-256
恢复并复绿。聚焦跑 Q8、Q2 module-import、drawapply/profile 邻域和文档声明，独立
`--basetemp=.tmp_pt_038q8`；零真机、零部署、零 git 写，暂不跑全量。

## 明确不做

- 不改 catalog 的 symbolRef、不把 CircuitSpec 的 GENERIC-* 替换为真 UUID，不生成
  PresentationSpec，不跑 draw compile/plan/apply。
- 不解除 AMS 的 U.VOUT* 未决项，不合并 SY8089 两种身份，不解除任何模块的
  candidate/unverified/notForDrawCompile。
- 不新增 src 死代码、不改 Rust module-import、不给现有 loader 增加第四种输入形状。

## 实施记录（2026-11-12，子代理 038q8 执行）

**新增文件**（未改 catalog / CircuitSpec / manifest / Rust / 绘制算法）：

- `blocklib/symbols/profiles.json`（21354 B，sha256 `7991c28f2fac47075339a93c939072d00e2ce397c825ad99ec93d5f10c540b10`）：
  六份 profile 原样对象，按 symbolRef 升序，只含 `{"profiles": [...]}`；既有 loader 直接读出六份。
- `blocklib/symbols/index.json`（11858 B，sha256 `450d749911f454098ffa3d05cabcaf97e9a273bf5ffd7ba8a099eb438897ea66`）：
  `schema/libraryUuid/notForDrawCompile/profileBookSha256/profiles[]`，每条含 symbolRef/libraryUuid/
  title/maturity=candidate/source/archiveSha256/geometryHash/profileSha256/reader/editorVersion/
  sourceTier/acquiredOn/evidence[]/bindings[]。
- `tools/check_symbol_book.py`（sha256 `93aff1483ecac0bb2963215ac37640a6ccae51ca9cf24734be66de6810748fdb`）：
  `validate_book(root) -> list[str]` + CLI，只读两份 book 文件 + `blocklib/modules/catalog.json`。
- `tests/test_038q8_symbol_book.py`（32 tests）。
- `docs/draw.md` 新增一节「A candidate symbol book is not a compile input」（15 行）。

**实算哈希**（`SymbolProfile.geometry_hash()` 与全文件 sha256；与 Q4/Q5/Q7 汇总逐条相符）：

| LCSC | symbolRef | geometryHash | archiveSha256 | profileSha256 |
|---|---|---|---|---|
| C6186 | 06f50e10ab7d460599b3fe3ee8717a78 | 36162e0377a1a4becac77a5d73726d548ca34013645a11b177e750e8dddd78a3 | 53f58e3706a078178c6883264130330db4be5d84d35ff1f150a595d0d752d4cb | 6b6cf8fcaf4847568206de8de8bd24efd4851e1756208617db6e48a38d9b6d8c |
| C440198 | 2e54d9f6ef024fd6a073cb020500c9e8 | b0f29952d01dfb134fe2190fbaddf6fc4f0351f0d3665c092d195cd166da30c1 | 83d18ee62326704840c0a7e2354948d662480727c59bd21039b523098673a4ec | 99725839d4fb3472bcf41351f50555cfe3235458a76e7185ab801d6f36ca27e9 |
| C1525 | 5d54ad1e3ff64cdb9e7c9f449679d79f | a06c2c33f9f5dec67f96458463ea36bc63214066718360e059cc77296969e08e | 396c40ceaa9fd16f84bb2324e0aea3aee0ce43c7794ee0a113188932f263efd2 | 0a143a8843f2b0aa4b5021f75b627007952743e68e60c46a1183566f86f11496 |
| C45783 | a945ad0780e84529829fad9eef7941b6 | f92b600cb8b816b9469edcc2fad46bcd4bbf5687c35a9779d065e39600b48592 | 4a371cc61d8da136294a3d7594e2266bb4e760dc644f59249456dad7ff857a43 | 34d6f70d048409dcd654a61ae01430336b90e8dbd73610a45e764664c2756a0b |
| C78988 | ef98186cdedd4b58bd8e66a11ff8b5be | 4851909350218d7598dc09e3ac9dfd3abccb8288e270c05a6c916f2a8fadc83e | 8b4b61760502ae4284303401fc9b0402c9c55971266a0e8f4af5be30f1e5925e | e7909022a37f978f5678388cf3b61167df783c356101035d1d99ca737e58be26 |
| C479074 | f88e34d680e646e38a7b77e29201ff30 | 3c07aad715b2055243760b9636ec0ce070459a721c4219b1371a4cf87ca8ba65 | 36f627dfa671d0e2adc512c8576afda78b864eee24477a1d109ca92efdadab1a | 2e7a80352261817a05ffa10fa501df4be00e323245c4f6030a6f70bfc01e4cc1 |

**记录在案的偏差**：index 的 bindings 除任务书点名的 `deviceUuid/lcsc/mpn/footprintUuid/supplierFootprint`
外，另带 `catalogFootprint`——即 catalog 对该 deviceUuid 已声明的 `footprint` 标签（如 `C0402`／`SOT-223-3`）。
理由：catalog 的 `footprint` 是 EasyEDA 封装名、device 响应的 `supplierFootprint` 是供应商族名
（`C0402` vs `0402`），两者词表不同、不能互相校验；把 catalog 侧标签原样带进来，校验器才能对
「binding 与 catalog 的 footprint 字段一致」做**精确**比对（漂移即红），而不是靠子串猜测。
C479074 的 catalog part 未声明 footprint，故该条不写 `catalogFootprint`（不补没读过的字段）。
`footprintName` 六个 device 响应里均为 null，故一条都没写。

**验证**：`tools/check_symbol_book.py` exit 0（6 candidate，profileBookSha256 7991c28f…）；
聚焦 pytest `tests/test_038q8_symbol_book.py` **32 passed**；Q8+Q2 module-import+drawapply/SymbolProfile
邻域 `127 passed, 1 skipped`；doc claims/175_docs/069d `55 passed`；basetemp `.tmp_pt_038q8`。
两处校验器变异（去 source↔archive 对齐 → 2 红；去 geometry 比对 → 2 红），cp 备份 + SHA-256
还原（`93aff148…` 前后一致）后复绿，证据 `.tmp_038q8/MUTATION.md`。零真机、零部署、零 git 写、未跑全量。

## 主审收尾（2026-11-12，同批追加）

### 1) 校验器对畸形 symbolRef 改为逐条报错（不再可能崩溃）

`index.profiles[i].symbolRef` 为 `null`／数字／空串／数组时的行为修正：

- 每个非「非空字符串」的 symbolRef 逐条报 `index.profiles[i].symbolRef: … is not a non-empty string`；
- 另加一条汇总 `… entry(ies) carry no string symbolRef, so the order cannot be compared with the book`，
  且**不再**进入集合/顺序比较——`sorted()` 在混合类型上会抛 `TypeError`，把整份报告带走；
- 成员判断前先过类型：数组等不可哈希值不是 dict 键，`symbol_ref not in book` 会抛 `TypeError`，
  现在直接跳过（该条已按位置报过）；
- 同一 symbolRef 出现两次时明确报 `symbolRef <ref> names N entries at positions […]`。

新增负例：`null`/`42`/`""`/`["06f50e10"]` 四参数化（要求返回而非抛出）、全六条均为数字
（六条逐条错误 + 汇总）、重复 symbolRef（按名字与位置报）。真数据与既有合同未动。

### 2) 两个已裁点（口径固定，后来者勿改）

**(a) bindings 的 `catalogFootprint` 是可选字段，允许存在。** 它只**复制 catalog 侧自己的
`footprint` 标签**（`C0402`/`SOT-223-3`/`SOT-23-5_L3.0-…`），用途是让校验器对
「catalog 与 binding 的 footprint 字段是否漂移」做**精确**对拍。它**不与** device 响应的
`supplierFootprint`（供应商族名 `0402`/`SOT-223`/`SOT-23-5`）混词表、不互相校验——两套词表
本就不同。catalog part 未声明 footprint 时（C479074）该字段**不写**，也不许补猜。

**(b) `profileSha256` 是 LF 规范化后的对象哈希，不等于 evidence 里原始 profile 文件的字节哈希。**
定义不变：对该 profile 对象按插入键序 `json.dumps(obj, ensure_ascii=False, indent=2) + "\n"`
的 UTF-8 字节哈希（即 LF 换行）。evidence 里的 `*.symbol-profile.json` 是 Q4/Q5/Q7 当时的原始落盘
文件，若以 CRLF 写出，其文件 sha256 与规范化哈希**必然不同**——**AMS1117 就是这种情形**：
原始文件 `e85c8b64…ee5652`（CRLF，3446 B）vs `profiles.json` 里的规范化对象哈希
`6b6cf8fc…d9b6d8c`（LF，3326 B）。其余五份原始文件恰好是 LF，所以两者相同
（C440198 `99725839…`、C1525 `0a143a88…`、C45783 `34d6f70d…`、C78988 `e7909022…`、
C479074 `2e7a8035…`）。

**这不是数据漂移**，是换行规范化；本批没有改动任何 profile 内容（六份 geometryHash 与
Q4/Q5/Q7 汇总逐条相同即为证）。先前实施记录里「profileSha 与原文件逐条相符」的说法不严谨，
以本节为准：只有五份相符，AMS1117 因 CRLF 不同而是 `e85c8b64…`（原始）/`6b6cf8fc…`（规范化）。
测试与校验器一律只读受管 book（LF）与 catalog，**不依赖 outputs**，故不受该差异影响。

### 3) 收尾后复跑

`tools/check_symbol_book.py` exit 0；`tests/test_038q8_symbol_book.py` **38 passed**；
原聚焦集（Q8 + Q2 module-import + 054/143a drawapply + 143f SymbolProfile + doc_claims/175_docs/069d）
**189 passed, 1 skipped**（skip 为 Q2 既有 raw 样本缺失）；`--basetemp=.tmp_pt_038q8`。
零真机、零网络、零 git 写、零删除、未跑全量。

## 提交前挖洞修复（2026-11-12）

- `.gitattributes` 仅为 `/blocklib/symbols/*.json` 与 `/blocklib/modules/**/*.json` 钉 `eol=lf`，
  防止 Windows autocrlf fresh clone 改变字节哈希；`git check-attr` 已验证模块根文件和 circuits
  均命中，未把规则扩到 specs 或全仓 JSON。
- checker 新增 catalog `symbolRef` 对拍：bound 模块逐 part 等于 book 对该 deviceUuid 的
  symbolRef；未 bound 模块继续只允许空串。错指向另一个真实符号、bound 回落空串、unbound
  长出 ref 都有负例；旧 checker 新负例 **3 failed / 4 passed**，修复后 Q8 **46 passed**。
- 短路 symbolRef 比较的实现变异得 **2 failed**，cp+SHA-256 已恢复。主代理复跑 validator exit 0、
  Python Q8+Q10+Q2+Q12+doc-claims **123 passed**，不读 outputs。
