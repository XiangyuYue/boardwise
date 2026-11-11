# Rust 迁移平台：构建、差分与派单边界（540C）

## 1. 当前范围

`rust/` 是一个最小 Cargo workspace，只有两个 crate：

- `boardwise-core`：语言中立 JSON 投影、LayoutPlan 几何哈希、`contracts/json`
  输入 schema 校验（`src/schema.rs`，`tools/contract_validate.py` 的移植）、
  结构化 CLI envelope，以及 **business-free 的 `.epru` 行框与文档切分**
  （`src/epru.rs`，`boardwise/parsers/epru_stream.py` 的行框/切分移植——只认
  `{envelope}||{body}` 行形与 `DOCHEAD` 文档边界，不知道 pad、track、netlist 为何物）；
- `boardwise-cli`：`differential` 与无业务 `smoke` 的进程边界。

它不是现有 `boardwise` Python CLI 的替代品，也不连接编辑器或 daemon。翻译边界的准确
口径是：只放行 EPRU stream 的行框与文档切分这类无业务读出，**审查规则、业务 model、
布局/布线算法仍不翻译**；也不接管容器读取（`load_epru_text` / `.epro2` / `.eprj3`
解包、`project2.json`）与 Python CLI 的任何命令面。不引入 PyO3、WASM 或 Node native addon。

## 2. 工具链与构建

需要 stable Rust、`rustfmt`、Clippy 和当前 target 的完整本机链接环境。Windows 的
`x86_64-pc-windows-msvc` 除了 Rust 标准库，还需要匹配的 MSVC CRT 与 Windows SDK
import libraries；只看到 `cargo --version` 成功，不能证明链接环境完整。不得混用
MinGW 与 MSVC CRT 来制造通过结果。工具链安装或全局配置变化必须另行取得批准。

在仓库根执行：

```bash
cd rust
cargo fmt --check
cargo clippy -- -D warnings
cargo test
```

`Cargo.lock` 随 workspace 固定依赖解析；`rust/target/` 是可再生构建产物，不进入提交。
测试包含 core 单元测试与 CLI 进程测试，覆盖参数、stdout/stderr JSON envelope、
退出码、错误形状和仓库差分 case。

## 3. Python/Rust 差分与 golden

`contracts/differential/` 只使用既有公开夹具或匿名合成输入。生成器会清理时间戳和
机器路径；来源、输入与 case book 的 SHA-256 记录在 `manifest.json`。不要在变更无关
业务输出时顺手再生成 golden。

仓库 case book 当前有 **15 个 case**：review 投影、layout 几何、module compile 投影、
page compile 投影、lint 投影，加上五组各两个 case 的 kind——`epru-stream-sample` 是
**记录流投影**（`.epru` 记录逐个翻译成 JSON，不做任何库合并），`symbol-library-sample`、
`device-library-sample`、`footprint-library-sample` 三组才是**库投影**，最后一组
`footprint-declared-sample` 是**声明解析投影**（不是库投影：它不产库表，只回答一个字段
声明了什么）。五组各自「一个 kind、两个 case id」：kind 决定 schema 与投影，id 决定输入名
与 case 行。
`symbol-library-sample` 的输入多带一个 `pinKey`（`zIndex` 对 V3 `.epro2` 的 `e<zIndex>` 寻址，
`pin_id` 对 eprj3 行自身 `id` 寻址），两台风扇都会从同一份 `text`+`pinKey` 推出同一份
`boardwise.symbol-library/1`。`device-library-sample` 的输入**只有 `text`**（不发 `pinKey`），
输出 `boardwise.device-library/1`，合并语义对齐 Python 的 `_collect_device_meta`：每个
文档的首个 `META` 生效，重复 uuid first-wins，只有模型可见字段不同才计入
`conflicting_documents`。`footprint-library-sample` 的输入同样**只有 `text`**，输出
`boardwise.footprint-library/1`，形状只有 `schema` 与 `footprints`（uuid → 封装标题），
**没有 `stats`、也没有冲突计数**——它是 `_collect_footprint_titles` 的查表，不做差异判定：
`FOOTPRINT` 文档的首个 `META` 生效，重复 uuid first-wins，**空标题也占位**（先到的空串
挡住后来的标题），字面 `"null"` 标题原样保留（DEVICE 属性值那条排除规则在这里不适用）。
`footprint-declared-sample` 的输入是 **`text` 加 `value`**：`text` 是一份 `.epru` 记录流，
`value` 是原理图器件 `Footprint` 字段的原文（原样，空串也算一条）。两侧都先用
`_collect_footprint_titles` 建同一张 `uuid → 标题` 表，再交给 `_resolve_declared_footprint`
回答「这个字段声明了什么」，输出 `boardwise.footprint-declared/1`，形状只有
`schema`/`footprint`/`libraryId`：`value` 先 trim；**只有命中表且该标题非空**才返回标题
加原始库 id；普通名称、空串、以及本归档没有的中 id 一律把 trim 后的原文回填
`footprint`、`libraryId` 留空串。是哪个分支**不单独出字段**——`(footprint, libraryId)`
这一对已经说清，多读一个字段就是 Rust 侧只能靠复制该投影才对得上的东西。
两份 compile 结果是**彼此独立的合同**：module 文档用
`draw-compile-result-v1.schema.json` 的 `candidates`，page 文档用
`draw-page-compile-result-v1.schema.json` 的 `pages`，投影字段也各说各的名字
（`candidateCount` 对 `pageCount`），不得把一份改名成另一份。两种形状共有的
`command`/`ok`/`failureCount`/`previewNames` 由 Rust 侧同一个阅读器产出；page 投影
只数 `pages`，不伪造它从未声明的 `candidateCount`。

### 3.1 两侧命令（默认路径与参数形态）

两侧 `differential` 共用同一套可观察参数面：`--flag PATH` 与 `--flag=PATH` 等价，
三个参数重复时**后者生效**（与 Python `argparse` 一致），并且都有仓库默认值。

```bash
mkdir -p .tmp_540/c1

# 不写 --cases/--root：默认是“代码旁的仓库”，与当前 cwd 无关
.venv/Scripts/python.exe -m tools.differential --output .tmp_540/c1/python-differential.json
rust/target/debug/boardwise-cli.exe differential --output .tmp_540/c1/rust-differential.json

# 等号写法与重复参数（后者生效）
rust/target/debug/boardwise-cli.exe differential \
    --cases=contracts/differential/cases.json --root=. \
    --output .tmp_540/c1/rust-differential.json

.venv/Scripts/python.exe -m tools.differential_compare \
    .tmp_540/c1/python-differential.json .tmp_540/c1/rust-differential.json \
    --output .tmp_540/c1/comparison.json
```

默认值固定为仓库自身：Rust 用编译期 `CARGO_MANIFEST_DIR` 上溯得到的仓库根，对应
Python 的 `Path(__file__).resolve().parents[1]`。`--cases` 缺省是
`<repo>/contracts/differential/cases.json`，`--root` 缺省是 `<repo>`，两者互相独立：
只给 `--root DIR` 时仍读仓库 case book。**不得**把 cwd 当作默认值。

比较器只移除 `runner` 字段，其余 JSON 值（包括 case 顺序、actual/expected 与 ok）
必须完全一致；报告同时给出双方规范化 SHA-256。`ok=true` 才表示对拍通过，不能把
“两个进程都退出 0”当作内容一致。

### 3.2 退出码与错误边界

| 情形 | 退出码 | stdout | stderr |
| --- | --- | --- | --- |
| 全部 golden 一致 | 0 | differential 报告 | 空 |
| golden 不一致 | 1 | 报告（`ok=false`） | 空 |
| `-h` / `--help` | 0 | usage 文本 | 空 |
| usage error（未知 flag、缺值） | 2 | 空 | 纯 usage 文本，**不是** JSON envelope |
| runner 拒绝（schema 拒绝、I/O、未知 kind、`--output` 父目录不存在） | 2 | 空 | 一个 `boardwise.cli-result/1` envelope（`command: differential`、`error.code: BAD_REQUEST`） |

usage 文本不要求与 argparse 逐字相同（flag 语法是各自实现的），但两边都不许把
usage error 混成 domain envelope。`--output` 在打印报告**之前**写盘：写失败时 stdout
保持为空，不会出现“报告已打印但退出码是 2”。`--output` 文件用 LF（与 Python 的
`write_text_lf` 一致，便于按字节记录）。

### 3.3 输入 schema 校验与依赖

`boardwise-core/src/schema.rs` 是 `tools/contract_validate.py` 的 Rust 移植：
`project_case` 在每种 kind 投影前都会用 `contracts/json/<kind>.schema.json` 校验输入，
schema 文件按 Python 口径从“代码旁”的仓库读（不受 `--root` 影响）。语义要点：全树
预检（未知关键字、未知 `type`、`$ref` 链/环/悬空）、`$ref` 是 applicator、`items` 只
作用于 `prefixItems` 之后、`enum/const` 递归且 `true ≠ 1`、`1.0` 算 integer、非有限数
拒绝（`NaN` token 与 `1e999`）。

`contracts/json` 现有 **8 份 schema**（`bridge-error-v1`、`draw-compile-result-v1`、
`draw-lint-result-v1`、`draw-page-compile-result-v1`、`epru-stream-sample-v1`、
`layout-plan-v1`、`review-report-v1`、`symbol-library-sample-v1`）。每一份都由 `schema.rs` 的单元测试整树预检（可读且落在支持的
子集内），仓库里的公开差分输入则作为正例逐个跑一遍；page 与 module 两份 compile
合同还各有负例，证明任一输入都过不了对方的 schema、也进不了对方的 kind。
`epru-stream-sample-v1` 的输入就是两个声明样本（`contracts/differential/sources/
epru-stream-samples.json` 的合成文本，无真实工程），两侧都用它做正例。

`regex` 依赖**只**服务于 schema 的 `pattern` 关键字（`tests/test_540c_workspace.py`
钉住：它只能出现在 `schema.rs`，CLI 依赖里不许有）。Rust `regex` 没有反向引用/环视，
Python 合法而 Rust 拒的 pattern 会报 schema 错误——更严，不会放空闸。现有 pattern
全部落在 `regex` 实际支持的语法里：字符类（如 `[0-9a-f]`、排除分隔符的 `[^/\\]`）、
分组（含非捕获组 `(?:…)`）、交替 `|`、`{64}`/`*`/`+`/`?` 量词与 `^`/`$` 锚点；没有
反向引用，也没有环视。Python 的 `$` 在串尾换行前也会匹配，这一点由 `pattern_matches`
模拟，不靠改写 pattern。新增 pattern 前先确认它在两个引擎里同义——不要依赖一份会
过时的“现有 pattern 清单”。

### 3.4 语料对照（`--ignored`）

两批对照语料由 Python 侧生成，默认不跑：`cargo test` 里它们显示 **ignored**，
ignored 不是通过。需要显式带上语料变量并加 `--ignored`：

```bash
.venv/Scripts/python.exe .tmp_adversarial540/geometry-rust/gen_float_corpus.py
.venv/Scripts/python.exe .tmp_adversarial540/geometry-rust/gen_number_corpus.py
.venv/Scripts/python.exe .tmp_adversarial540/geometry-rust/gen_geometry_corpus.py
.venv/Scripts/python.exe .tmp_adversarial540/rust-schema/gen_schema_corpus.py

BOARDWISE_540C_FLOAT_CORPUS=.tmp_adversarial540/geometry-rust/float-corpus.jsonl \
BOARDWISE_540C_NUMBER_CORPUS=.tmp_adversarial540/geometry-rust/number-corpus.jsonl \
BOARDWISE_540C_GEOMETRY_CORPUS=.tmp_adversarial540/geometry-rust/geometry-corpus.jsonl \
BOARDWISE_540C_SCHEMA_CORPUS=.tmp_adversarial540/rust-schema/schema-corpus.jsonl \
bash .tmp_540/rust-buildtools/cargo-local.sh test -p boardwise-core \
    --test python_compat_corpus --test schema_parity -- --ignored
```

### 3.5 跨语言 CLI 检查

`tests/test_540c_cross_language.py` 起两个真实进程对比：成功（空格/等号写法、重复
参数、`--output` 文件与 LF）、`-h/--help`、usage error、schema 拒绝、未知 kind、
`--output` 父目录缺失，以及 golden 不一致的 0/1 语义。Rust 二进制未构建时该模块
**skip** —— skip 不是验收：交卷前必须先 `cargo build -p boardwise-cli` 再实跑，
并看到这组测试 passed。

需要有意重建公开 golden 时，先审查输入来源与 diff，再运行：

```bash
.venv/Scripts/python.exe -m tools.build_differential_fixtures
```

永久兼容闸位于 `tests/test_540c_contracts.py`、`tests/test_540c_differential.py`、
`tests/test_540c_schema_semantics.py`、`tests/test_540c_generator_validation.py`、
`tests/test_540c_process_contract.py`、`tests/test_540c_cross_language.py` 和
`tests/test_540c_workspace.py`，覆盖 CLI 漂移与跨语言进程边界、真实/合成 JSON 正例、
schema 负例、来源哈希、golden 失败路径与 workspace/文档边界。

## 3.6 `module-import`（038Q2）

第三个 CLI 子命令，也是 Rust 侧第一处**带业务输入结构**的纯转换：把固定上游
（`easyeda-agent@69af00c0db3960757bff36a68edb286adcd64458`）的两种模块 JSON
归一化成既有的 `boardwise-circuit-spec` v1，并生成候选 catalog/manifest。

```bash
rust/target/debug/boardwise-cli.exe module-import --output blocklib/modules
# 显式输入：--curation <PATH>（默认 <repo>/contracts/module-import/curation.json）
#          --root <DIR>（默认仓库根，curation 里的相对路径相对它解析）
```

边界与纪律：

- **输入只能是脱敏派生物**（`contracts/module-import/`）。原始下载留在
  `.tmp_038q2_upstream/` 不入库；`source-manifest.json` 同时记原始 SHA、脱敏派生
  物 SHA、上游 LICENSE 与过滤口径，`curation.json` 逐条记端口的人工 direction/class
  裁定——端口缺裁定、或裁定的方向不在 `source/load/input/output/feedback` 里一律拒绝，
  `dir` 与端口名从不被猜成方向。curation 的 `sourceManifest` / `license` 指向这两份
  输入，run 会校验：ledger 与 curation 的 upstream repo/commit 一致、每个 asset 的
  `sourcePath`/`sourceSha256` 与 ledger 一致、脱敏源文件与 LICENSE 的字节哈希与
  ledger 记录一致，否则整批拒绝。
- 输出**只到目录**：`circuits/*.circuit.json`、`catalog.json`、`manifest.json`、
  `upstream/LICENSE`（curation 那份的逐字节副本）。先算完所有候选再预检写盘；同名
  同字节允许（可重跑），不同则拒绝，不覆盖、无 `--force`。manifest 记全部输入/输出
  SHA（含 `source-manifest.json`、`LICENSE` 与 `upstream/LICENSE`），自身不入哈希，
  不写时间戳。
- **路径边界**：curation 内的一切输入相对路径（`standardParts`/`sourceManifest`/
  `license`/`source`）必须是相对 root 的普通组件，绝对路径与 `..` 一律拒绝；`output`
  必须是非绝对的、仅 Normal 组件的相对路径。`write_outputs` 自己再查一遍，不依赖上层。
- 全部事实 `provenance: ai_asserted`、`draft: true`；catalog 一律
  `maturity: candidate`、`identityStatus: unverified`、`notForDrawCompile: true`。
  **catalog 的器件 `symbolRef` 为空**（没有识别出任何符号）；**CircuitSpec 的
  `symbolRef` 用 `GENERIC-<role>` 占位**——它的 loader 对 `symbolRef` 是
  `required=True`，空串直接拒绝。占位不是已解析身份，device UUID 绝不进该字段；
  本批不接入 draw compile，catalog 同时标记 `notForDrawCompile`。接口 `role` 同理不可空，
  写上游端口名。
- Block 的 `author`/`contributors` 作为结构化 `attribution` 写进 catalog；没有该字段的
  Role Topology 不编造。
- 通配脚（`U.VOUT*`、`J_USB.VBUS*`…）原样留在 members 并列入
  `unresolvedWildcards`，不猜脚号；本批不声称 compose、原生 CBB、PCB 或硬件验证，
  也不进入 draw compile。
- 退出码：0 写出候选；usage error（缺 `--output`、未知 flag）纯文本 2；输入/归一化
  拒绝是 `boardwise.cli-result/1` envelope（`command: module-import`）2。
- 测试：`rust/crates/boardwise-core/tests/module_import.rs`（真实四资产 + 合成拒绝用例，
  scratch 目录每次唯一、不删除）、`rust/crates/boardwise-cli/tests/module_import.rs`
  （进程面、LICENSE 字节一致）、`tests/test_038q2_upstream_module_seed.py`（用既有
  CircuitSpec loader 读回四个输出，核对端口映射、来源 allowlist、catalog/manifest
  哈希，并在原始样本存在时用运行期收集的 free text 反查泄漏——具体标识不写进仓库）。

## 4. 迁移与派单纪律

迁移顺序固定为 **纯函数/几何 → parser/model → review → draw → daemon 最后**。
0.6.x 新工具/引擎默认 Rust，例外必须登记；旧工具按「合同对齐 → Rust 默认 →
临时 Python fallback → 删除旧实现」垂直迁移。Python fallback 只过渡，不形成长期
双业务实现；0.7.0 验收受支持主流程，不要求逐行翻译全部 Python，connector/DSH
薄适配可留 TypeScript。

跨语言合同、shared parser/model/core/CLI 或进程边界变化，走
`tasks/shared-platform.md` 的集成锁；审查与绘制算法分别由 `tasks/review-line.md`、
`tasks/draw-line.md` 派单。迁移与算法变化不得同批，shared、全量测试与真机串行。
路线与版本边界见 `docs/roadmap.md` §10；540C 验收记录见
`tasks/540c_rust_platform.md`。本文件不授权全局安装、真实工程写、Git 写或发布。
