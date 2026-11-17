# 550：离线 PCB 铜路径证据（首条只读垂直切片）

## 背景与目标

岳要求参考上游 easyeda-agent 补齐 EDA 操作工具。能力矩阵见 `.tmp_review_attribution/eda-capability-matrix.md`；上游精确合同见 `upstream-net-path.md`，本地模型盘点见 `local-net-path.md`。

本批只交付一个最小可用工具：在两个 `REF.PAD` 之间寻找一条由 **pad / 直线 track / via** 构成的有序、确定性铜路径。它补的是审查证据，不是自动布线，不修改设计，不移植上游整套测量器。

公开入口：

```bash
boardwise pcb net-path FILE --from REF.PAD --to REF.PAD [--board TITLE_OR_BOARD_UUID]
```

- `FILE` 只接受 `.epro2` 或 `.eprj3` 文件夹/索引文件；KiCad、单个 `.epcb2`、在线 `pcb.readback` 和 `--project` 本批不支持，按名拒绝。
- **输出分两条路（最小合同，不另造结果对象）**：查询真的执行了 → stdout 一份 JSON（`schema=boardwise.pcbNetPath/1`），`CONNECTED` exit 0、`NOT_PROVEN` exit 2、`INDETERMINATE` exit 3；**前置拒绝**（文件不存在、容器按名拒绝、文件夹无 `.eprj3` 索引、容器无板、多板缺 `--board`、`--board` 匹配不到或匹配多块）→ **stderr 一行理由、stdout 为空、exit 3**，不伪造一个 `verdict`；argparse 用法错误（含 `--through/--layer/--json/--project`）保持 stderr/exit 2。
- 多板必须显式 `--board`，匹配 review 公开的 `review_units()` 的 title 或 board uuid；缺省、重名或找不到均拒绝，绝不取第一块。单板可不传。
- 首版**不提供** `--through`、`--layer`、`--json`、`--project`；传入未知选项由 argparse 明确拒绝，不得静默忽略。
- 起点与终点必须是两个不同的物理焊盘；`from == to` 返回 `INDETERMINATE + errors.same_pad`，不输出零跳 PASS。非有限坐标/尺寸、负孔径或 `via_diameter <= hole_diameter` 都是无效几何，不得制造路径。

## JSON 合同

`schema` 固定为 `boardwise.pcbNetPath/1`，至少包含：

- `source`: 输入容器、boardCount、所选 title/uuid；路径只作本机证据，不写公开文档。
- `query`: from/to 的 ref、pad、net、layers、shape。
- `verdict`: `CONNECTED | NOT_PROVEN | INDETERMINATE`。
- `path`: 从起点到终点的有序图元，含 id/kind/layers/net；track 带 width/start/end，via 带 center/diameters，pad 带 ref/shape/angle。不得输出没有走过图的“网表路径”。
- `viaCount`、`unknown[]`、`ignored[]`、`errors[]`、`coverage`。这些数组即使为空也必须存在。
- `scope`: 明示仅支持归档中的 pad/直线 track/via；pour/fill/PLANE 不参与路径，未证明不等于电气开路，ARC 未建模。

本批不输出长度、转角、阻抗、线宽合规或 DRC 通过结论。

## 判定纪律

1. **CONNECTED**：BFS 找到一条真实路径；每一跳至少共享一个铜层，且现有 `measure._touching()` 判铜体相接。网名只用于选图元，不是连通证据。路径不得含 pour、ARC 或直接 pad↔via 边。
2. **NOT_PROVEN**：在受支持的图集合中无路径，且 `unknown[]` 为空。含义仅为“未由本批支持的铜图元证明”，不是电气开路；pour/PLANE 的排除写在 `ignored[]` 和 `scope`。
3. **INDETERMINATE**：任何可能改变否定结论的证据缺口存在，或输入本身不成立。未知项包括：板上 ARC 未消费、同网不支持焊盘、有效层/铜层表缺失、无网 track/via、直接 pad↔via 接触、无效 track/via 几何。正路径已经找到时，未知项仍披露，但不推翻这条已走通的路径。
4. 焊盘仅支持 `RECT`、圆形 `ELLIPSE`、`OVAL` 的现有精确模型。非圆 `ELLIPSE` 的外接 32 边形和其它/未知 shape 不得制造正路径；端点不支持直接 INDETERMINATE，同网非端点不支持使否定结论降级。
5. 直接 pad↔via 的宿主连接语义尚未由 boardwise 真机确认，首版禁止作为边。track↔via、pad↔track、pad↔pad 及 via 的 `unused_inner_layers` 继续复用现有 measure 语义。
6. pour/fill/POUR/POURED/PLANE 一律排除，不能因为“只有铺铜能连”而 CONNECTED，也不必仅因铺铜存在而把否定结果降级。无网 track/via 可能补路，否定结果必须降级；无网 pour 只是 excluded，不是 unknown。
7. BFS 的图元顺序和邻接顺序必须确定，同一输入重复运行输出逐字节一致。

## 文件域与分层

- `core/netpath.py`（新，shared）：纯 `find_net_path(board, from_ref, to_ref)`、结果模型与 JSON 投影；只 import shared，复用 `measure._net_shape_records/_touching/_element_layers/_bbox_distance`，不复制解析器或几何数学。
- `pcb_netpath.py`（新，assembly）：容器/板选择、CLI 输出与退出码；复用 review 公开的 `review_units()`，core 不得反向 import review。
- `engines/pcbreview.py`：为 550 增公开包装 `review_units(source_path)`（assemble 侧唯一入口）。它是 `_review_units` 的一行转发，**返回形状与逐板 lazy 语义完全不变**，私有名继续供层内 `run_pcb_review` 使用；跨层只走公开名（`tests/test_layer_rules.py` 的私有名守卫因此保持绿）。
- `commands/assembly.py`：注册 `pcb net-path`，保持 `pcb gate` 原参数与行为。
- `cli.py`：只增加 net-path 分派，不改 gate。
- `contracts/module-owners.json`：登记 core 为 shared、CLI 为 assembly；`contracts/cli/v1.json` 由官方生成器重生成。
- `tests/test_550_pcb_net_path.py`、`tests/test_550_pcb_net_path_cli.py`；不改既有 fixtures，真实工程容器不入库。
- 公开说明优先补 `docs/review-sop.md` 的单点命令段；本批不是 bridge action，不改 connector/protocol/docs/bridge，也不新增 DSH 工具（离线单点证据，先由 CLI 验证，后续确有需要再立 DSH 适配）。

## 兼容矩阵与 negative control

| 维度 | 本批承诺 | 不得声称 |
|---|---|---|
| V3 `.epro2` 单板 | 合成 + 既有公开夹具只读验收 | 不声称 V3 3.2.x 宿主在线能力 |
| V3/V4 多板 | 必须 `--board`；重名/缺省/错名拒绝 | 不跨板拼路径，不重复板双审 |
| V4 `.eprj3` | 复用公开 `review_units()` 同一读取链，合成目录验收 | 不声称真实非空多板已覆盖 |
| 在线 | 不支持，按名拒绝 | `pcb.readback` 数组摘要不能冒充 BoardGeometry |
| ARC | 披露并在否定结论时降级 | 不把缺 ARC 当无 ARC |
| pour/PLANE | 排除并披露 | 不声称整板电气开路或 DRC 连通 |
| CBB | 无 PCB 特殊分支，REF 只按实际 PCB designator | 不展开块内部，不声称 CBB 兼容 |
| KiCad | 本批拒绝 | 不借 `review_units` 的既有能力悄悄扩大承诺 |

必须覆盖：N1 同网断开 NOT_PROVEN；N2 两端异网拒绝；N3 仅铺铜可连不得 CONNECTED；N4/N5 through/layer 未知选项拒绝；N6 ARC 使否定降级；N7 未知 shape/层/stackup 降级；N8 多板缺 `--board`；N9 REF 不存在/重名/写法错误；N10 直接 via-in-pad 不得 CONNECTED；N11 盲埋孔按有效层；N12 同输入确定性。

## 验收与回退

- 核心批：上述合成测试、measure 邻域、owner/layer 守卫；至少两处独立变异（删一条合法边、错误允许 pad↔via 或跨层边）先红，cp + SHA-256 恢复。
- CLI 批：真实既有 `.epro2` 只读正/反例、合成 `.eprj3` 多板选择、argparse/退出码/JSON、540C 合同、`pcb gate` 邻域；官方重生成 CLI 合同。
- 日常不跑全量；集成/发布另按四线。零真机写入、零 daemon、零 connector、零发布。DSH 工具面本批不跟，交卷写明理由。
- 回退是移除新命令与新模块，不改旧模型、规则、gate、报告或 fixture；不得用 git restore 回退混合工作区。


## 实际验收（2026-11-17，工作树未提交）

- 核心 42 条、CLI 27 条通过。主代理最终合并：550 核心/CLI、125B、038Y5、038P/P1、540C、540 CLI、owner/layer/architecture/doc-claims/DSH-sync，**371 passed in 36.94s**；仓库卫生 **4 passed**。未跑全量，不称全绿。
- 真实 CLI：CONNECTED exit 0 / 2跳，NOT_PROVEN exit 2，ARC INDETERMINATE exit 3，same_pad exit 3，多板缺 `--board` 前置 stderr+exit 3，`--layer` argparse exit 2；CONNECTED 两次 stdout SHA-256 一致。`tools.cli_contract` 与生产一致。
- 主代理独立变异：跨层放行 → 核心 **7 failed / 35 passed**；删 net-path 分派 → CLI **20 failed / 7 passed**。均 cp + SHA-256 恢复。子代理另完成合法边、pad↔via、same_pad、非法桶径、多板默认第一块及私有 import 变异。
- 最终组合曾发现 `test_540_cli_review` 的模块计数仍钉 152，已同步为 154 后复跑 371 passed；没有隐藏这一轮红项。

### 仍未覆盖与后续顺序

1. ARC 仍是独立 shared parser/model 批；本批只降级披露，不借本批绿灯宣称 ARC 兼容。
2. 在线先只做官方 `getConnectedPrimitives/getEntireTrack/getAdjacentPrimitives` 的 capability 与只读探针，证实后才设计 live net-path；`pcb.readback` 摘要不能直接转 BoardGeometry。
3. `--through` 的整体有序证明和 `--layer` 语义另立合同，不把首版拒绝当成永久不支持。
4. 真实非空多板 `.eprj3`、via-in-pad 宿主语义、前置拒绝的结构化 error code 未覆盖；不伪造样本。
5. 后续 EDA 工具顺序：DRC/net class 只读证据 → `sch replace/rebind` 独立写垂直链 → `pcb new-board/import-changes` 同步链。高层自动布局布线不混入这些 typed 底座批。
