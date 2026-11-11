# 038Q4：elibz2 单符号解析与 AMS1117 SymbolProfile

日期：2026-11-11。038Q3 真机补验后的 shared/parser 小批，不改 bridge/Connector/DSH/Rust/绘制算法，不再次部署。

## 已测输入与缺口

- 真实公开 LCSC 符号文件：`outputs/review/038q3/ams1117.elibz2`，SHA-256 `53f58e3706a078178c6883264130330db4be5d84d35ff1f150a595d0d752d4cb`。
- symbol=`06f50e10ab7d460599b3fe3ee8717a78`，library=`0819f05c4eef4c71ace90d822a990e87`，title=AMS1117-3.3。
- ZIP 恰有 `.elibu` 与 `symbol2.json`，CRC 正常、无加密、成员路径平坦。manifest 的唯一 UUID 和 library path 已与请求核对一致。
- `.elibu` 有**两个完全相同的 SYMBOL DOCHEAD 身份**：第一段给 META，第二段给 CANVAS/RECT/PIN/ATTR。原始 4 脚为 1=GND、2=VOUT、3=VIN、4=VOUT；脚坐标/rotation/length 完整。
- 主代理把原 stream 仅外包装成 `.epru` 后，旧 `collect_symbol_details` 实测 body 正确但 **0 pins**：重复头触发 first-wins 空符号。证据 `outputs/review/038q3/container-identity.json` 与 `.tmp_038q3/legacy-collector-probe.json`。
- 不得简单让 `load_epru_text` 接受 elibz2，也不得全局改变工程归档里相同 UUID 的 first-wins/冲突规则。

## 目标与最小架构

新增一个**单符号 elibz2**读取口，完成容器校验、身份核对、受控重复头归并，再复用现有 SYMBOL 引脚/body 解析，输出可审核的 `SymbolProfile`。只支持本批实测的 elibz2 形状；elibz 未覆盖。

建议公开形状（可在不扩大语义的情况下微调命名）：

```python
read = load_elibz2_symbol(
    path, symbol_uuid="06f50e10ab7d460599b3fe3ee8717a78",
    library_uuid="0819f05c4eef4c71ace90d822a990e87",
)
profile = read.symbol_profile()
```

返回一个小只读结果对象，至少含 `detail: SymbolDetail`、archive/stream SHA-256、library/symbol UUID、editorVersion、原始 SYMBOL head 数；`symbol_profile()` 复用 `core.symbolprofile.from_parsed_symbol`，source 使用 `elibz2:<uuid>:sha256:<archive-hash>`，不写本机绝对路径。

### 复用而不是复制几何逻辑

- 在 `parsers/schematic.py` 把 `collect_symbol_details` 现有的 records → details 主体提取成私有 helper；旧 path 入口仍走 `load_epru_text`、原 stats、原 `_pin_key_for(meta)`，输出保持不变。
- 新 elibz2 reader 可复用该私有 helper 和 `_iter_schematic_records`，不能复制一套 RECT/POLY/CIRCLE/PIN 业务规则。
- 先读 records 并验证所有 SYMBOL DOCHEAD。只有**同一请求 UUID、body 完全相同的连续重复头**才能视为本容器续段，去掉后续重复头后交给同一个收集器。不同 UUID、不同 DOCHEAD body、非 SYMBOL 文档、额外 symbol 身份均拒绝；不能靠 first-wins 吞掉分歧。
- 本批原生 stream 的 Pin ATTR 以 PIN 自己的 `id` 为 parentId，显式使用 `pin_key="pin_id"`；不能谎称它是 eprj3，也不能全局切换 V3 的 pin key。
- 拒绝重复 PIN record id、重复/缺失脚号、解析后脚数与原始 PIN 行数不一致、共享 tip 等歧义。重复头归并不得把同脚后写覆盖前写。
- profile 沿用现有坐标翻转：pin1=(-45,10,left/GND)、pin2=(-45,0,left/VOUT)、pin3=(-45,-10,left/VIN)、pin4=(45,0,right/VOUT)，body=(-35,-20,35,20)，title=AMS1117-3.3。
- 本批**不扩 SymbolDetail/SymbolProfile 字段**：原始 rotation=0/0/0/180、length=10 已留在 038Q3 证据；现有 profile 仍如实声明 length 未进入 SymbolDetail、direction 来自 body-box。不得把派生 direction 冒充原始 rotation。
- body 仅复用现有 RECT/POLY/CIRCLE 能力。当前 RECT 与 PART BBOX 相同；ELLIPSE/ARC 等未覆盖，不宣称通用符号 body 已完整。

## 容器与身份合同

- 输入必须是可读 ZIP，恰一份 `.elibu` 与一份 `symbol2.json`；重复成员、额外成员、加密、CRC 错、绝对/父级路径均明确拒绝。合理限制声明大小，拒绝解压炸弹，不静默截断。
- `symbol2.json` 必须是对象，`symbols` 只含请求的 UUID；entry.uuid=请求、`path`=请求 library、docType=2。额外 symbols/devices/footprints 不在本批单符号合同中，拒绝而非猜用哪一个。
- stream 的所有 DOCHEAD 必须是请求 symbol；至少一个 head，重复 head body 必须逐字段一致。manifest 的 display_title 与解析 title 不一致时拒绝。
- 原始脚号、名称、类型和几何不可从 manifest/文件名/上游 layout-input 补猜。任何不一致都 fail closed，并给出具体原因。
- `SymbolProfile.source` 带容器哈希；两次读取同一文件应得到相同 `geometry_hash()` 和相同 JSON。source/notes 不参与几何哈希的既有规则不变。

## 兼容矩阵与 negative control

| 维度 | 本批覆盖 | 必须不变 / 未覆盖 |
|---|---|---|
| V4 4.1.93 | 038Q3 真实 elibz2 的离线解析与 profile | 不再部署，不声称在线 place/readback 已通过 |
| V3 / elibz | 未覆盖 | 不从 dts 或 elibz2 推断 V3/elibz 兼容 |
| `.epro2` | 旧 `collect_symbol_details` 邻域回归，行为不变 | 重复头修复只限新单符号 reader，不改工程 first-wins |
| `.eprj2/.eprj3` | 未覆盖 | 不称三种容器兼容完成 |
| 在线 / 离线 | 本批离线；在线证据只回指 038Q3 | 不触发 daemon/Connector/真实工程 |
| 单 / 多板 | 只读单 symbol | 重复 PCB 双审、分歧库串板均不改变、不验证 |
| 普通器件 / CBB | 一个普通 LCSC 符号 | 不声称 CBB geometry/place 兼容 |
| CircuitSpec / draw | 只生成候选 profile | 不展开模块、不改 catalog、不解除 notForDrawCompile、不编译落图 |

两个消费者锚：旧 `collect_symbol_details` 的既有 fixtures/测试输出不变；新 detail 经既有 `from_parsed_symbol` 得到上述 4 脚与 body。旧工程相同 UUID 的冲突计数仍按原逻辑处理，负例须证明该路径未被全局改成续段合并。

## 允许文件域

- 新增 `src/boardwise/parsers/elibz.py`。
- `src/boardwise/parsers/schematic.py`：只做 records helper 提取与必要导出，旧函数行为不变。
- 新增 `tests/test_038q4_elibz_symbol.py`，使用 tmp_path 内合成的公开最小 symbol stream，不把真实工程或整份上游自由文本做成 fixture。
- `contracts/module-owners.json` 与 `tests/test_owner_rules.py`：仅登记 `parsers/elibz.py` 为 shared，并把模块总数从 147 改为 148；这是新模块入册的必需集成，不改其他 owner/layer 规则。
- 本任务书；实际 profile/验收写 `outputs/review/038q4/`，一次性探针写 `.tmp_038q4/`。

不改 `core/symbolprofile.py`、blocklib/modules、bridge/Connector/DSH/Rust、绘制线文件、package/version、TASKMAP、worktree；零 git 写、零删除、零真机调用。

## 实施与验收

1. 一个 coder，最多 40 步或 30 分钟。先读任务书、AGENTS 和必要 SOP；范围漂移即停。
2. 测试至少覆盖：真实形状的重复头续段、4 脚映射/角色/body、确定性 profile、错误 UUID/library/title、额外 symbol、不同 DOCHEAD、重复 PIN id/脚号、缺脚号、非 ZIP、坏成员/路径、旧工程重复 UUID 不被新逻辑合并。
3. **负对照**：同一个合成 stream 走旧 path 收集器应复现 first-wins 的低脚数/空脚现象，新 reader 必须完整读出；不能用测试只证明新代码自洽。
4. 聚焦 pytest 必须带独立 `--basetemp=.tmp_pt_038q4`；跑 schematic/SymbolProfile/owner/layer 邻域与 Q3 合同，不跑 Connector/DSH 全测试（本批零 TS 改动）。
5. 两处变异：①不再归并续段头，真实形状脚数断言必须红；②删除库身份或重复脚号拒绝，对应负例必须红。均 cp+SHA-256 恢复并复跑，不用 git 恢复，不删备份。
6. 用真实 `outputs/review/038q3/ams1117.elibz2` 生成 `outputs/review/038q4/ams1117.symbol-profile.json` 和采集摘要；主代理独立复跑、核对脚号/body/hash/source 后，才决定后续是否晋升模块库。
7. 全量 pytest 由主代理串行决定。四模块继续保持 unverified/notForDrawCompile；本批完成不等于 AMS 模块全部器件身份齐全，更不等于三个试点完成。


## 主代理验收（2026-11-11）

- owner 阻塞已按 shared 入册解决：`parsers/elibz.py=shared`，模块数 147→148，未改其他 owner/layer 规则。
- 主审再修两处：通用 notes 不硬编码 AMS 的 rotation/length；三类 Pin ATTR 都校验 parent/重复，新增孤儿 Pin Name 与重复 Pin Type 的旧路径错配负对照。
- 主代理独立聚焦 **169 passed**；真实采集脚本复跑通过。候选 profile SHA-256 `e85c8b64921f248e078cd6a4f4a89e02abbd029ea753d11a9b10e8de91ee5652`，geometry hash `36162e0377a1a4becac77a5d73726d548ca34013645a11b177e750e8dddd78a3`。
- 两处变异均先红后 cp+SHA-256 恢复复绿。最终源码 SHA-256 `4afcb20a44c56c1c235a3e8e3614cd0490df2ee0f0467334ec1b3f97d43f2ee3`。
- 证据：`outputs/review/038q4/ACCEPTANCE.md`。仍未做集成全量；未改模块 catalog，四模块继续 unverified/notForDrawCompile，未进入绘制。
