# 038Q2：上游模块数据的候选归一化（设计/任务书）

日期：2026-11-11。依赖 038Q1 的 shared/Connector 批次验收；本批与 Connector、绘制算法、真机分开。

## 范围

固定 `easyeda-agent@69af00c0db3960757bff36a68edb286adcd64458`，首批只处理：

- `block.ams1117_ldo_3v3`；
- `block.sy8089_buck_3v3` 与独立的 `lib.sy8089_buck_3v3_live`（两个不同变体，**不得按标题合并**）；
- `block.ch340c_usb_serial`。

产出候选模块目录、来源/许可证/哈希清单和 Rust 纯 JSON 归一化器。不是原生 CBB 样件创建，不放置、不写真实工程、不复制上游 Go 布局求解器。

## 数据与许可证边界

- 保留上游作者、MIT 许可证、固定提交、源文件路径和 SHA-256；同步必须显式审 diff，不自动跟随 main。
- 原始公开下载只进 `.tmp_038q2_upstream/`。**不得把原始 JSON 全量入库**：其中 `source`、`validated`、器件 `desc` 等自由文本可能含历史工程标识。
- 入库的是过滤后的电气事实和结构化来源，不复制原始自由文本。公开产物不得出现历史工程名、整板成员映射、原始坐标或客户/产品线索。
- 上游的 `validated`、`verification`、库 UUID 和“已放置”声明只是待复核线索，不能在本仓自动变成 `verified`。新导入事实默认用 CircuitSpec 的 `ai_asserted` 保守档，使其 `draft=true`；这是**本仓未核验**的含义，不是断言上游由 AI 生成。
- 160 项标准器件不整架搬运，只读取本批实际依赖。器件身份需经当前宿主 `lib.device.get` 再核对，并从 `association.symbol` 取得真实 symbol UUID；在此之前 `symbolRef` 留空，不能拿 device UUID 冒充。

## 归一化合同

建议新增版本化 Rust 输入/输出合同，复用现有 `boardwise-circuit-spec` v1 作为电气输出，不发明第二套电路模型。目录、来源、成熟度、变体、警告放在薄 sidecar，不塞进 CircuitSpec 的自由键。

### Block Template 输入

- `parts` 的 map key 成为稳定逻辑角色 id；`part` 是标准器件引用，不是 symbol UUID。
- 首批遇到 `qty != 1` 明确拒绝，不擅自复制器件。实读发现 AMS1117/CH340C 含 `VOUT*`、`VBUS*` 等多物理脚通配引用：**本批原样保留并列 `unresolvedWildcards`**，不猜脚号、不冒充已展开，未解决前不得进入 draw compile；实测身份后另批展开。
- `internal_nets` 的 `ROLE.PIN` 进入 nets.members；`PORT:<名字>` 解析为 open interface，并关联到该网。
- 每个 Block 端口网使用独立的 `port.<端口名>` id。`ports` 的 `default_net` 只是将来组合时的建议，既不得把不同模块实例的同名网自动合并，也不得把同模块中 VIN/EN 这类建议同网、当前却未相连的端口提前短接。无端口内部网使用 `auto:` + 排序后的成员列表，与现有 CircuitSpec 一致。
- `schematic_layout`、坐标、导线、keepout、框不进入 CircuitSpec。`flow/attach/pair` 只有在另批映射成 PresentationSpec 草稿后才能消费，绝不直接落图。
- 未提及的引脚不是 NC；旧 Block 没有明确 NC 证据时 `nc=[]`。

### Role Topology 输入

- `module.parts[].role` 是逻辑 id；逐脚 `pins[].number/name/net` 与 `nets[].members` 必须互证，任何单向缺席、重复或矛盾都拒绝。
- `port.*` 成为开放接口；`internal.*` 保持模块内部，不因名字相同跨变体合并。
- 只有明确的 `connectionState:"unconnected"` 可进入 `nc`；`net` 缺失、空串或字段缺席都不能推断 NC。
- `geometry:not_captured`、`pcb:not_tested`、`bringup:not_tested` 原样成为 sidecar 的限制，不得提升为 compose/PCB/硬件通过。

### 端口与网类别

- `in/out/bidir` 与 CircuitSpec 的 `source/load/input/output/feedback` **不是同一词表**。
- 电源输入、信号输入、电源/信号输出按端口实际角色显式映射并逐条测试；不能把 `in` 机械翻成 `source`，也不能把 `out` 机械翻成 `load`。
- `bidir` 及未裁定方向的 `direction` 留空，保留角色名；不得猜成双向 source/load。GND 网使用 `class:"gnd"`，旗标策略由绘制线后续决定，不用网络标签代替。
- 输出必须经现有 CircuitSpec loader 再读一次；坐标键、重复 id、无宿主网、空成员、未知端口引用均失败，不输出“尽力而为”的候选。

## 测试与完成判据

- 四个候选（AMS1117、SY8089 Block、SY8089 Role Topology、CH340C）逐脚对拍：逻辑器件、网成员、端口、NC、变体身份。
- 至少覆盖：qty 拒绝、未知角色/脚、PORT 未声明、members 与 pins 矛盾、假 NC、方向不猜、坐标不传播、来源脱敏、symbolRef 不冒充。
- Rust `fmt/clippy/test`，既有 Python/Rust 差分合同不变；另以 Python CircuitSpec loader 读回全部输出，不改变既有 findings 或绘制候选。
- 至少两处源码变异，测试先红后用 cp+SHA-256 恢复；不修改既有 fixtures/golden。
- 本批不声称 `compose_ready`、原生 CBB 兼容、PCB 或硬件验证。真实器件身份与 SymbolProfile 采集是下一独立只读批；绘制构图另批验收。

## 后续顺序

1. 当前宿主器件/符号身份只读核对与 SymbolProfile 采集。
2. 三个试点的 CircuitSpec → PresentationSpec 草稿 → 编译/lint/逐脚/视觉三关。
3. 在明确任务书授权后，才于 `test V4` 做受控个人库样件与真实 `block_symbol` 回读。
4. 试点通过后再扩到其余非 draft 资产；12 条 draft 不进入自动生成。

## 实现读数（子代理批，2026-11-11）

本批落地（仅候选，未做真机/网络/git 写）：

- Rust：`boardwise-core/src/module_import.rs`（纯转换+校验）、`boardwise-cli/src/module_import.rs`
  （`module-import` 子命令）、`main.rs` 只加 `mod`/dispatch，未加新第三方依赖。
- 输入：`contracts/module-import/{blocks/*.json,topologies/*.json,standard-parts.json,curation.json,source-manifest.json}`。
  脱敏由一次性脚本 `.tmp_038q2/redact_upstream.py` 从 `.tmp_038q2_upstream/` 生成，脚本先按
  该目录 `source-manifest.json` 校验原始 SHA 再写派生文件；`LICENSE` 逐字节复制。
- 输出：`blocklib/modules/{circuits/*.circuit.json ×4, catalog.json, manifest.json}`。
- 实测计数（`CircuitSpec.load` 读回）：AMS1117 4 parts/3 nets/3 接口；SY8089 Block 7/6/4；
  SY8089 Role Topology 10/6/3；CH340C 7 parts/**11 nets**/6 接口。

三处与任务书字面不一致，均为 ContractSpec/CircuitSpec 既有合同的硬约束，已按「不猜、
不冒充、可加载」取最小偏离：

1. `symbolRef` 不能为空：`circuitspec.py` 的 `_text(..., required=True)` 拒绝空串，故 circuit 里写
   `GENERIC-<role>` 占位（仓内既有的「无真实 library profile」命名），catalog 的 `symbolRef`
   仍为空串，device UUID 从不进该字段。
2. `openInterface.role` 同样被 loader 拒空，故写上游端口名（任务书「保留角色名」）。
3. CH340C 上游 `internal_nets` 里没有 TXD/RXD/DTR#/RTS# 的成员，4 个端口各自由 curation 裁定
   `netSource: port_pin_only`，网 `port.<名字>` 成员即该脚本身，故 net 数 7+4=11；若按任务书的
   7 网，则这 4 个已裁定端口要么被静默丢弃（接口从 6 掉到 2），要么被猜接——两者都比多 4 个单脚
   端口网更糟。

其余照任务书：`ai_asserted` + `draft: true`、`maturity: candidate`、`identityStatus: unverified`、
`notForDrawCompile: true`、`unresolvedWildcards` 原样保留、同模块 VIN/EN 不因同 `default_net`
短接、`auto:` + 排序成员命名无端口内部网、Block `nc=[]`、Role 只认 `connectionState:
unconnected` 且缺网脚列 `unstatedPins`。

## 复审修订（同一小批，2026-11-11）

主代理复审不签收后按定位问题修订，四资产与端口裁定不变，**CH340C 仍为 7 parts / 11 nets /
6 interfaces**（7 条上游 internal_nets + TXD/RXD/DTR#/RTS# 各一条 curation 裁定
`netSource: port_pin_only` 的单脚 `port.<名字>` 网；这四脚在上游 internal_nets 里没有任何
成员，单脚开放网是唯一既保留端口又不猜接的表达）。

1. **脱敏测试不再写死标识**：`tests/test_038q2_upstream_module_seed.py` 删掉全部历史工程/产品
   字面量；原始样本存在时**运行期**递归收集 desc/source/validated/bom_note/schematic_notes/
   pcb_layout/schematic_layout/placement/keepout/_doc/note 等自由文本（长度 ≥8），在
   `blocklib/modules` 与 `contracts/module-import` 全文反查（本次收到 217 条、最长 337 字符）；
   原始样本不存在时仍跑来源 allowlist（逐文件字段白名单）与 catalog/manifest 结构检查。
2. **测试不删任何东西**：Rust core/CLI 测试的 scratch 改为 `进程 id + 原子计数` 唯一目录，
   去掉 `remove_dir_all`；Python 侧新增静态检查，本批自有 Rust 源码不得出现
   `remove_dir_all` / `remove_dir(` / `remove_file(` / `TempDir`。
3. **LICENSE 与 source-manifest 进入流程**：curation 增 `sourceManifest` / `license` 两个输入；
   `contracts/module-import/LICENSE` 逐字节等于上游 LICENSE；plan 读取并哈希两者，校验
   ledger 与 curation 的 upstream repo/commit、每 asset 的 `sourcePath`/`sourceSha256`、
   脱敏源文件与 LICENSE 的字节哈希；输出新增 `upstream/LICENSE`，manifest.inputs 有
   `source-manifest.json` 与 `LICENSE`（8 项），manifest.outputs 有 `upstream/LICENSE`
   （6 项），manifest 自身仍不入哈希。
4. **路径边界**：curation 内 `standardParts`/`sourceManifest`/`license`/`source` 必须是相对
   root 且只含普通组件（绝对路径与 `..` 拒绝）；`output` 必须非绝对、仅 Normal 组件。
   `write_outputs` 独立复查一遍。负例覆盖 source/sourceManifest/standardParts/license/output
   逃逸与 `write_outputs` 直调逃逸，证明目标目录外零写入。
5. **注释/文档与实际一致**：catalog 的器件 `symbolRef` 为空；CircuitSpec 的 `symbolRef` 因
   loader `required=True` 使用 `GENERIC-<role>` 占位（不是已解析身份，不拿 device UUID 冒充；
   本批不接入 draw compile，catalog 同时标记 `notForDrawCompile`）；接口 `role` 同理不可空，
   写上游端口名。
6. **attribution**：Block 的 author/contributors 以结构化 `attribution` 进 catalog（CH340C
   contributors=`["Codex"]`），Role Topology 无该字段则不编造。

读数：`cargo fmt --check` OK；`cargo clippy -- -D warnings`（含 `--all-targets`）无告警；
`cargo test` 全绿（新 core 28、新 CLI 8）；`pytest test_038q2… + test_053a_specs +
test_540c_workspace + test_doc_claims --basetemp=.tmp_pt_038q2_review` = 114 passed。
重新生成到新目录与 `blocklib/modules` 逐字节相同（幂等），四份 CircuitSpec.load 读数
4/3/3、7/6/4、10/6/3、7/11/6，nc 全 0，draft 全 True。

## 主代理独立复验（2026-11-11）

- 真实 `boardwise-cli module-import` 在全新目录生成四份 circuit、catalog、manifest 与
  `upstream/LICENSE`，与 `blocklib/modules` 逐字节相同；manifest 为 8 inputs / 6 outputs，
  自身不入哈希，所有 digest 重算通过。
- 追加负例：asset 不得占用 `catalog.json` / `manifest.json` / `upstream/LICENSE`，
  `write_outputs` 拒绝计划内重复路径（同字节也拒绝），Role Topology 的 `part` 必须是已声明
  role。最终新 core 31、新 CLI 8，Rust 合计 **150 passed / 4 ignored / 0 failed**。
- 变异①通配覆盖 `at*`→`at?`：11 条测试转红；变异②绕过重复路径拒绝：1 条测试转红。
  两次均 cp 恢复且源码 SHA-256 为 `35c3bc43d34ed88e86639e9d0864ca837932ee237aa21267dfc87ab0a1a4838b`。
- 聚焦 Python 114 passed；仓库卫生检查通过（既有两个未扫描二进制目录披露，不属于本批）。
- 完整 pytest：**10614 passed / 25 skipped / 1 xfailed / 72 failed / 1 warning**，日志 `.tmp_038q2/full-pytest.log`（UTF-8 副本同目录）。逐项与 038Q1 第二轮基线比较：16 条为既有货架/098/Windows 问题；新增 56 条全部位于绘制线在途的 `test_548d_*`（panel/service），代表性错误为 `layout-unsat: a service branch has no legal seat`，当前绘制线有对应未提交实现改动。**038Q1/038Q2、module-import 与本批相关合同没有失败**，不把 72 条全称为既有基线，也不替绘制线修或改其文件；本批不以全量全绿交付。
- 本批只交付候选数据与导入器，未核验器件/符号身份、未展开通配脚、未接入 draw compile、
  未做原生 CBB/PCB/硬件验证。下一批是当前宿主只读身份核对与 SymbolProfile 采集，再决定是否
  进入 PresentationSpec 和绘制三关。
