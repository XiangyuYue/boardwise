# 审查链路测试用例（boardwise 0.6.0 · DSH 0.2.1 内核）

> 面向 AI 测试员：按表逐条执行，把结果按 §5 模板回填。
> 这是**上机验收**，不是单元测试；每条用例都要真的跑起来，记录命令、退出码、产物路径和实际观感。
> 不通过的不许写成通过；环境缺失写 `BLOCKED`，不许用「应该没问题」代替。

## 1. 这份文档测什么

| 面 | 覆盖 |
|---|---|
| 离线审查 | `checkup --file`（`.epro2` / `.eprj3`）、`arch`、`review`、`compare` |
| 报告消费 | `review-read`、`triage`、`triage-batch`、`review finalize`、`review-evidence` |
| 在线通道 | `doctor`、`bridge status` / `bridge call`、多窗口寻址 |
| 绘制离线 | `draw compile`、`draw lint` |
| DSH 工具面 | 10 个 `boardwise_*` 工具（`driver` 是 DSH，不是 CLI） |
| 极端与对抗 | 坏输入、坏路径、坏版本、坏状态、超时、重复、并发 |
| 焊盘几何 | 圆盘 / `OVAL` / 非圆 `ELLIPSE` 的间距读数、外接框假阳性回归、已知残留（038V） |

**不测**：绘制落图（`draw apply` / `review-mark`）的视觉质量——那要人眼验收，另见 `docs/schematic-style-spec.md`。

## 2. 环境与前置

```sh
cd E:/boardwise
BW=".venv/Scripts/python.exe -m boardwise.cli"     # 仓库解释器，不要用系统 python
$BW --version                                       # 期望 boardwise 0.6.0
```

| 前置 | 检查命令 | 期望 |
|---|---|---|
| CLI 可用 | `$BW doctor` | 输出带 `cli:`，退出码 0/3 都可（见 T-A00） |
| 离线夹具在 | `ls tests/fixtures/ch340_golden.epro2` | 存在 |
| V4 文件夹样本 | 由任务书指定路径（**不得使用真实工程副本**） | 存在 |
| 真机（仅在线用例） | `boardwise bridge status` | `doc.list` 的焦点工程名与任务书**逐字一致** |

红线（违反即整批作废）：

1. 真机只碰 `test` / `test2`；任务书没点名的工程一律不写。
2. 不 `rm` 删除；临时产物进 `.tmp_t_<用例号>/`，回收走回收站。
3. 不改 `tests/fixtures/` 既有夹具，不把样本复制进仓库。
4. 不碰 `outputs/011e*` / `014_*` / `015b_*` / `016_*`。

## 3. 通用判定

| 词 | 含义 |
|---|---|
| **PASS** | 命令按预期退出，产物内容与预期一致 |
| **FAIL** | 退出码/产物/文案与预期不符（记下实际值） |
| **BLOCKED** | 环境缺失（daemon 不在、样本没有），且不是被测功能的错 |
| **DOC** | 文档与实现不一致（也按 FAIL 记，附一句话） |

退出码语义（全局，不是建议）：

| 码 | 含义 | 常见于 |
|---|---|---|
| 0 | 完成，结论可用 | 多数命令 |
| 1 | 有差异/有失败/审查发现问题 | `compare`、`draw lint` |
| 2 | 输入坏（不存在、格式不对、参数冲突） | 所有命令 |
| 3 | **说不清**：审查没看全（`incomplete`）、写结果未知 | `checkup`、`draw` |

**exit 3 不得当通过**，也不得当失败——它是「结果不可陈述」。

## 4. 用例表

### A. 离线审查（不需要编辑器）

| ID | 目的 | 操作 | 预期 |
|---|---|---|---|
| T-A01 | 黄金板离线审查跑通 | `$BW checkup --file tests/fixtures/ch340_golden.epro2 --out .tmp_t_A01` | exit 0 或 3；`report.json` / `report.md` / `architecture.md` / `design-intent.md` 四个都在且非空 |
| T-A02 | `--file` 不存在 | `$BW checkup --file nope.epro2 --out .tmp_t_A02` | exit 2；错误文案点名路径；**不生成** `report.json` |
| T-A03 | `.epro2` 被截断（模拟传输中断） | `head -c 2000 tests/fixtures/ch340_golden.epro2 > .tmp_t_A03/broken.epro2` 后 `checkup --file .tmp_t_A03/broken.epro2` | exit 2；报「不是有效的归档/无法解析」，不许退化成 0 器件报告 |
| T-A04 | 空文件当工程 | `type nul > .tmp_t_A04/empty.epro2` 后 `checkup --file ...` | exit 2，理由与「空模型」区分开 |
| T-A05 | 把**目录**当文件传 | `$BW checkup --file tests/fixtures --out .tmp_t_A05` | exit 2（或按 `.eprj3` 判定，但必须说清它被当成什么） |
| T-A06 | 架构骨架 | `$BW arch tests/fixtures/ch340_golden.epro2 --out .tmp_t_A06/architecture.md` | exit 0；文件非空；器件数/网表数与 `report.json` 的 `model` 段一致 |
| T-A06b | `--out` 误给目录 | `$BW arch <epro2> --out .tmp_t_A06/`（目录） | **期望** exit 2 并说明「这是文件路径」；**2026-11-04 实测是 traceback + exit 1**（已知缺陷，见 T-E02 同源根因） |
| T-A07 | 规则审查（`review`） | `$BW review tests/fixtures/ch340_golden.epro2 --out .tmp_t_A07` | exit 0；finding 有 severity/rule/位置，可逐条追溯 |
| T-A08 | `compare` 同板自比 | `$BW compare tests/fixtures/ch340_golden.epro2` | exit 0（自己 vs 自己必须逐脚相等）；`compare` **没有** `--out`，不要加 |
| T-A09 | `compare` 对坏输入 | `$BW compare nope.epro2` | exit 2 |
| T-A10 | `.eprj3` 文件夹工程 | `$BW checkup --file <v4样本目录> --out .tmp_t_A10` | exit 0 或 3；`editor_version` **非 null**（取 DOCHEAD 的 4.x）。注意：`edit_version` 实测**恒为 null**，这与 `tests/test_038f2_eprj3_version.py` 的设计断言一致，不是缺陷 |
| T-A11 | `.eprj3` 有 PCB 但未跑 PCB 审查 | 同上，看 `coverage` 与 canvas note | 必须写「PCB 存在但未审」，**不许**写「没有 PCB 文档」（038F3） |
| T-A12 | `.eprj3` 无 PCB 文件 | 构造/指定一个只有 `sch/` 的目录 | 写「没有 PCB」，且 `pcbReviewMissing=false` 与文案一致 |
| T-A13 | 多 PCB 的处置 | 含两个 `pcb/*.epcb2` 的目录，分别跑 `checkup --file` 与 `--view pcb` | `checkup --file` 当前**逐板各审一节**（`pcb_review.boards` 两节），`--view pcb` 才硬拒绝。判定：两种行为二选一，但必须**说得清**审了哪几块；不许静默只审一块 |
| T-A14 | 同输入重复跑 | T-A01 连跑两次到不同 out | 两次 `report.json` 的 findings 计数与结论一致（允许时间戳/路径差异） |

### B. 报告读取与分诊

| ID | 目的 | 操作 | 预期 |
|---|---|---|---|
| T-B01 | 结构化读报告 | `$BW review-read --out <T-A01 的 out> --section verdict --json <B01>/verdict.json` | exit 0；JSON 可解析；`verdict` 就是 `report.conclusion` 本身；非法 section → exit 2 并列出合法值 |
| T-B01b | 合法 section 全覆盖 | 依次跑 `verdict` / `findings` / `crossView` / `coverage` / `artifacts` / `netlist` | 每个 exit 0，或明确说「该段不存在」；**不许**给默认 0 |
| T-B02 | 读坏报告 | 把 `report.json` 改成 `{"a":1}` 后 `review-read --section verdict` | 当前 exit 0，但 payload 明确 `status: "missing"`（显式声明，不是静默空对象）。判定：显式声明即合格；静默返回 `{}` 才算失败 |
| T-B03 | 缺报告文件 | `review-read --out .tmp_t_nonexistent` | exit **3**（`review-read --help` 自己写的就是 3），点明「报告不存在」 |
| T-B04 | 单条分诊 | 对 T-A01 的 warning 跑 `triage --out ... --key <key> --verdict 有益 --reason 测试` | exit 0；重读报告该条 verdict 变了 |
| T-B05 | 分诊非法 verdict | `--verdict 随便写` | exit 2，列出合法值 |
| T-B06 | 批量分诊原子性 | `triage-batch` 给 3 行，其中第 2 行坏 | exit 2，且**一行都没写**（报告 hash 不变） |
| T-B07 | 分诊后不丢 | T-B04 之后重跑 `checkup` 到同一 out | verdict 仍保留（重跑不许冲掉分诊，issue #12） |
| T-B08 | finalize 收据 | `$BW review finalize --out .tmp_t_A01`（`finalize` 是 `review` 的**保留位置参数**，不是子命令） | 骨架/结论/引用一致时 exit 0 并写 `finalize.json`；不一致时 exit 1 并逐行列出（骨架注释残留也算不一致） |
| T-B09 | finalize 缺报告 | `$BW review finalize --out .tmp_t_不存在` | exit 3（`no report.json`）；坏 JSON/错 schema 才是 exit 2 |
| T-B10 | `need-datasheet` 标记 | 对缺手册器件标记后重跑 | `completion` 仍为 `incomplete`，不许因标记而变绿 |

### C. 在线通道（真机，仅 `test`/`test2`）

| ID | 目的 | 操作 | 预期 |
|---|---|---|---|
| T-C01 | doctor 全项 | `$BW doctor` | 逐项有结论；daemon 不在时点名而不是沉默 |
| T-C02 | 指定工程 doctor | `$BW doctor --project test` | 焦点工程名逐字匹配才 PASS，否则明确报错 |
| T-C03 | bridge status | `$BW bridge status` | 列出窗口/焦点；多窗口时不许瞎猜 |
| T-C04 | bridge 只读动作 | `$BW bridge call --read-only --action doc.list --params '{}'` | 返回文档列表；**不带** `--read-only` 时拒绝写动作 |
| T-C05 | 非法 params | `--params 'not json'` | exit 2，不 spawn 编辑器动作 |
| T-C06 | daemon 离线 | 停掉 daemon 后立刻 `bridge status` | 报「daemon 不在」并给启动提示；不许挂死 |
| T-C07 | review-evidence 采集 | 对在线工程 `review-evidence --out ... --project test` | 四通道状态如实（ok/failed/not-applicable），`pcbImage` 在 V4 为 `not-applicable` |
| T-C08 | 焦点错位 | 把焦点切到另一窗口后跑 T-C07 | 报 PAGE_MISMATCH 或要求显式 `--instance`；不许采错页 |
| T-C09 | 空模型失败 | 采集到 0 器件 | 通道标 `failed`/`incomplete`，**不许**写 ok |

### D. 绘制离线

| ID | 目的 | 操作 | 预期 |
|---|---|---|---|
| T-D01 | divider 编译 | `$BW draw compile --circuit <夹具> --presentation <夹具> --profiles <夹具> --out .tmp_t_D01 --json .tmp_t_D01/r.json` | exit 0；`candidates` 非空；JSON 可解析 |
| T-D02 | 编译拒绝（写 JSON） | 给缺字段的 circuit | exit 5，且 `--json` 文件**会写出**（`ok=false` + 失败原因）——这与「输入读不出」的 exit 5（不写文件）是两种情形，判定看文件里有没有把失败原因说清 |
| T-D03 | lint 回放 | `$BW draw lint --snapshot <夹具> --render <夹具> --json ...` | exit 0；违规项可定位 |
| T-D04 | lint 坏输入 | 传不存在的 snapshot | exit 2 |

### E. 极端与对抗（重点）

| ID | 目的 | 操作 | 预期 |
|---|---|---|---|
| T-E01 | 路径含空格与中文 | 把夹具复制到 `.tmp_t_E01/带 空格 的 目录/板子.epro2` 后 checkup | 正常跑通；路径原样出现，不许截断 |
| T-E02 | 输出目录不可写 | 选一个只读目录做 `--out` | exit 2，报写入失败；不许半写 |
| T-E03 | 输出目录是文件 | `--out <某个文件路径>` | exit 2 |
| T-E04 | 重复 out（已有报告） | 第二次 checkup 到同一 out | 覆盖或拒绝，二者必须**说得清**；不许静默合并 |
| T-E05 | 插件版本与 CLI 不一致 | `BOARDWISE_EXE` 指向不存在的 exe | 工具报「路径不存在」，不静默换 CLI |
| T-E06 | 超长 stdout 截断 | 构造大报告或长输出 | 返回里标明「丢了多少字节」，不是静默截断 |
| T-E07 | token 打码 | 输出里含 `token=abc` | 变成 `token=***` |
| T-E08 | exit 3 不被当通过 | 对 incomplete 报告调用工具 | 返回 exit 3 + `incomplete` 理由；调用方不许写「通过」 |
| T-E09 | 并发同 out | 两个 checkup 同时写同一 out | 一胜一败且败者报冲突；不许产出交错 JSON |
| T-E10 | 网络/daemon 超时 | 桥动作指向黑洞端口 | 有界超时（≤ 工具 timeoutMs），不许无限挂 |
| T-E11 | 大小写/相对路径 | `--file TESTS/FIXTURES/CH340_GOLDEN.EPRO2`（Windows 大小写不敏感） | 跑通或明确说不支持，二者选一写进结果 |
| T-E12 | 空参数 | `checkup` 不带目标 | 无参数是在线单窗口的合法用法，不强制三选一；无 daemon/连接器时 exit 3 并如实说明没有取得模型，自动拉起必须有界；多窗口且无法确定默认窗口时才要求 `--project`/`--instance` |
| T-E13 | 互斥参数 | `checkup --file X --project test` | exit 2，明确互斥 |
| T-E14 | 报告被手改后 finalize | 改坏 `report.json` 再 finalize | 拒绝签发，指出坏在哪 |
| T-E15 | 超大器件数 | 用 500+ 器件的样本 | 有界时间返回，或明确报「超限」；不许 OOM/静默丢器件 |

### F. 焊盘形状与间距测量（038V，几何假阳性族）

> **背景**：PCB-A 的 Ø1.7 mm 圆盘焊盘被外接方框建模，对角方向半径放大成 `r·√2`，
> 把真实 **14.08 mil** 报成 **0.22 mil**，触发 `pcb-voltage-spacing` 假 WARN（宿主 DRC 0 条）。
> 038V 已修（`src/boardwise/core/measure.py` 的 `_pad_copper`）：圆盘 = 圆心 + 半径、
> `OVAL` = 体育场、非圆 `ELLIPSE` = 32 边**外切**多边形、其余仍走 `pad_corners()`。
> 本组钉的是**修复本身 + 同族边界 + 已知残留**，防回归。已有单测锚：
> `tests/test_125b_pcb_clearance.py` 的 `test_round_pad_inside_a_pour_void_is_fourteen_mil_clear` 等三条。

**F.0 构造器（复制到 `.tmp_t_F*/probe.py`，每条用例只改 `pads` / 期望）**：

```python
import math
from boardwise.core.geometry import BoardGeometry, LayerInfo, PadGeometry, Point, PourShape, StackupEntry
from boardwise.core.measure import net_clearance

LAYERS = {1: LayerInfo(1, "Top Layer", "TOP"), 2: LayerInfo(2, "Bottom Layer", "BOTTOM")}
STACKUP = [StackupEntry(1, 1000, "cu", 1.378), StackupEntry(2, 9000, "cu", 1.378)]

def pad(pid, net, x, y, w, h, shape="ELLIPSE", angle=0.0, layer=1):
    return PadGeometry(id=pid, component=None, pin_number=None, net=net,
                       footprint_layer_id=layer, x=x, y=y, width=w, height=h,
                       shape=shape, angle=angle, hole_diameter=None)

def board(pads=(), pours=()):
    return BoardGeometry(layers=LAYERS, stackup=STACKUP, pads=list(pads), pours=list(pours))
```

| ID | 目的 | 构造 | 期望 |
|---|---|---|---|
| T-F01 | **PCB-A 原案**：圆盘 ↔ 圆角挖空 | A：`pad(66.929, 66.929, ELLIPSE)` @(0,0)；B：`POURED` 铺铜，挖空为 512 边形、半径 47.548 | `net_clearance == 14.0826 ± 0.002`；**且读数与 0.22205 的差 > 1**（旧矩形值必须被排除）；`overlapping=False` |
| T-F02 | 对角圆盘 | 两个 60×60 圆盘，圆心在 45° 线上相距 100 | `40.0 ± 1e-9`；与 15.147186 相差 > 1 |
| T-F03 | 矩形 negative control | 同 T-F02，但 `shape="RECT"` | `15.147186 ± 1e-9`（矩形路径不许被改） |
| T-F04 | OVAL 体育场 ↔ 圆盘 | A：`OVAL 100×40` @(0,0)；B：`pad(20,20)` @(0,100) | `70.0`（体育场短轴半径 20，不是长轴 50） |
| T-F05 | 非圆椭圆·切点方向 | A：`ELLIPSE 200×100` @(0,0)；B：`pad(20,20)` @(0,200) | `140.0`（切点方向多边形与椭圆相切，精确） |
| T-F06 | 非圆椭圆·斜向（最差方向） | 同 T-F05，B 放在 45° 方向、距原点 200 | `116.75 ± 0.5`；数值法真实椭圆为 117.058，**多边形只许更小**（保守低估 ≤ 0.48% 半长轴） |
| T-F07 | 小圆盘对 | 两个 20×20 圆盘 @(0,0) 与 @(50,0) | `30.0 ± 1e-9` |
| T-F08 | 阈值边界 | 两个 20×20 圆盘 @(0,0) 与 @(30,0)，间隙正好 10.0 mil | 测量值 `10.0`；再跑 `pcb-voltage-spacing`，规则集平面间距 10 mil 时**不得**判违规（等于阈值不是小于） |
| T-F09 | 旋转 OVAL | T-F04 的 A 加 `angle=30` | 读数与 `angle=0` 相同（体育场旋转后仍是同一形状） |
| T-F10 | 端到端：真实夹具 | `$BW checkup --file tests/fixtures/llc_board.epro2 --out .tmp_t_F10`，读 `CHS`/`DC+` 的间距证据 | 间距读数为 **95.0 mil**（038V §7 记录），不再是 85.965；findings 里没有由该对引起的电压间距 WARN |
| T-F11 | 已知残留：`vias_on_pad` 外接框 | 圆盘焊盘外接方框的**角点**放一个过孔、圆盘外、方框内 | **不判 FAIL**：记录实际行为（过孔是否被算进焊盘），并核对 `docs` 里「非矩形焊盘仍用外接框做保守包含」的披露是否一致；不一致记 DOC |
| T-F12 | 已知残留：KiCad `roundrect`/`custom` | 有此类焊盘的 KiCad 夹具（若无则 BLOCKED） | 仍是矩形保守模型；读数偏小但不报错；文档披露一致 |

**F 组的判定要点**：

1. **方向性**：多边形近似只许**低估**（间隙更小），不允许高估——高估会把真问题藏起来。
2. **不许吞真问题**：T-F03 与 T-F08 是 negative control，修假阳性不能把「真小间隙」也放过。
3. **读数变化要能解释**：038V 让 llc 的 `CHS/DC+` 从 85.965 变 95.0、毕设 FOC 的 `+24V/PGND` 从 1.0387 变 14.078——这些是**真实值变准**，不是规则被放松；若某条读数变了但无法用几何解释，记 FAIL。

### G. 审查线 038W / 038X / 529 / 527C2 / 541 回归（2026-11-06）

> 这批是最近落地的审查线工作。**「本轮实测」列是 2026-11-06 主代理在真机 `test V4` 上跑过的结果**；
> 标「待跑」的留给测试员按同一格式补。真机红线不变：只碰 `test` / `test2`，
> 动手前 `doctor --project` 核对焦点工程名逐字一致。

| ID | 目的 | 操作 | 期望 | 本轮实测 |
|---|---|---|---|---|
| T-G01 | 真机身份 | `$BW doctor --project "test V4"` | 9/9 项 PASS；焦点工程名逐字为 `test V4` | ✅ 9/9，编辑器 4.1.93、daemon 0.6.0 |
| T-G02 | 真机在线审查 | `$BW checkup --project "test V4" --out .tmp_t_G02/out` | 两板两页（P1/P2 + P38/P1）；四件产物齐；exit 0/1/3 且结论可解释 | ✅ exit 1（23 项 ERROR），2 板 / 2 页 / 20 槽 |
| T-G03 | **038X** 非仓库 CWD | `cd /d && TMPDIR=<可写目录> E:/boardwise/.venv/Scripts/python.exe -m boardwise.cli checkup --project "test V4" --out <out>` | `shelf` 显示**绝对路径** `E:\boardwise\blocklib\parts.json` 且确实加载；不因 CWD 静默变空架 | ✅ 绝对路径正确、货架加载 |
| T-G04 | **038X** 坏货架 | `checkup --file <夹具> --library <不存在的 parts.json> --out <out>` | 明确「货架读取失败」+ 路径；`shelfMissing: true`；**不许**当成 0 条空架 | ✅ exit 3，报告顶层 `shelfMissing: true` |
| T-G05 | **038X** 空货架 | 造一个 0 条的合法 `parts.json`，`--library` 指它 | 空架 + note 说明「这是空货架，不是读取失败」；**不设** `shelfMissing` | 待跑 |
| T-G06 | **038W** PAD_NET 判优 | 合成四负例：①旧网→新空网（两文件顺序）②旧空网→新网（高 ticket 在前）③同票 client 大者胜 ④无法唯一判优 | ①②必须得到新值（空网要真的覆盖）；③按 client 判；④该脚键**缺席**且 `stats.consistency_unresolved` 有诊断；四条都不许「文件靠前胜」 | 待跑 |
| T-G07 | **529** mid 去耦 | 含 2.2µF 输入档的夹具跑 `checkup --file`，再与纯 bulk 样本对比 | 2.2/4.7µF 进 mid 池，输入档不再报「没有高频去耦」假 WARN；只有 bulk 的输入档仍 WARN；四个距离档 200/300/800/200 不变 | 待跑 |
| T-G08 | **527C2** 跨视图几何 | 真机 `checkup --project "test V4"` 后读 cross-view 段（`cross_view_section`） | `checked=true` 且 lonely 非空时带 `geometry`（端点绑定）；`checked=false` / `lonely=[]` / KiCad 模型时键集合逐字不变 | 待跑（本轮 report.json 顶层无 `cross_view` 键，需按 review 段核） |
| T-G09 | **#87θ** 库元素身份 | 同一库元素多副本 + 重复脚号 | 合并成同一结构化身份；副本不算两个器件 | 待跑 |
| T-G10 | **541 R1** RunManifest | `make_manifest → write → load → semantic_diff`；再喂坏 JSON / 未知版本 / `..` 路径 | 同基准 `sameBaseline=true`；只换输入哈希 `attribution="input:<path>"`；多变量变化必须是 `multi-variable-change`；坏输入一律 `RunManifestError` | 待跑（单测 `tests/test_541_run_manifest.py` 69 例可先跑） |
| T-G11 | **541 R2** strict 闸 | ①`checkup --file <夹具> --out <out> --strict`（首次，无 `run.json` 基线）②同 out 再跑 `--strict` ③再跑 `--strict --new-evidence archive-bytes-changed` | ①正常出报告（无基线不拒）；②无新证据的重算必须被拒并说明原因；③显式声明后放行并记入 manifest | ①② 已实测：① exit 3 正常出报告；② **exit 2 `reject-use-existing`**，明确说「在取锁、读模型、跑规则、写报告之前就停下」；`--new-evidence` 只收枚举 `archive-bytes-changed`（自由文本 exit 2） |
| T-G12 | **541 R4** strict-partial | `$BW review finalize --out <已审查目录> --strict-partial` | 四档披露校验：披露不完整即拒签；**不许**被 re-gate 洗白 | 待跑 |
| T-G13 | 对抗：自我哈希 | 检查 `run.json` 的 `inputs` | 不含 `report.json` / `run.json` 自身哈希；输出目录产物不进入自己的基准 | 待跑 |
| T-G14 | 对抗：侧车漏入基准 | 跑一次 triage 产生 `warning-triage.json` 后再生成 manifest | 侧车**不**被算进 `inputs`（否则每轮基准都变） | 待跑 |

**G 组判定要点**：

1. **038X 的「绝对路径」是有意变化**：默认 `shelfPath` 从相对字符串变成绝对路径，不是 bug；显式 `--library` 仍逐字使用用户输入。
2. **038W 不许「最后一条赢」也不许「靠前赢」**：只能复用原子视图的 ticket/client 判优；判不了就缺席 + 诊断。
3. **529 只改分类**：四个距离阈值一个都不许动；bulk 的 INFO 特例必须保留。
4. **strict 是 opt-in**：默认路径行为不变；不带 strict 的回归不能因为 strict 新增而变红。

## 5. 反馈模板

每条用这个格式回填（缺一不可）：

```text
用例: T-A03
结论: PASS | FAIL | BLOCKED | DOC
命令: <逐字复制实际执行的命令>
退出码: <真实数字>
证据: <产物路径 / stdout 摘要 / hash>
观察: <一句话——实际看到什么>
期望: <文档写的预期>
差异: <FAIL 时写清差在哪；PASS 写「无」>
```

汇总表：

| 分组 | 总数 | PASS | FAIL | BLOCKED | DOC |
|---|---|---|---|---|---|
| A 离线审查 | 14 | | | | |
| B 报告消费 | 10 | | | | |
| C 在线通道 | 9 | | | | |
| D 绘制离线 | 4 | | | | |
| E 极端对抗 | 15 | | | | |
| F 焊盘形状与间距（038V） | 12 | | | | |
| G 审查线 038W/038X/529/527C2/541 | 14 | | | | |
| **合计** | **78** | | | | |

## 6. 测试员的自我约束

1. **先跑 A 再跑 C**：离线都不对，在线结论没有意义。
2. **每条都留证据**：没有产物路径/退出码的结论不算结论。
3. **FAIL 不修**：测试员只报，不改生产代码；修复由审查线另派。
4. **BLOCKED 要有前置检查证据**（daemon 状态、样本路径）。
5. 发现文档与实现对不上，记 `DOC` 并引用文档行号。
6. 一轮跑完把汇总表与 FAIL 清单交回；不要边跑边改文档。
