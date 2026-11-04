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

## 6. 测试员的自我约束

1. **先跑 A 再跑 C**：离线都不对，在线结论没有意义。
2. **每条都留证据**：没有产物路径/退出码的结论不算结论。
3. **FAIL 不修**：测试员只报，不改生产代码；修复由审查线另派。
4. **BLOCKED 要有前置检查证据**（daemon 状态、样本路径）。
5. 发现文档与实现对不上，记 `DOC` 并引用文档行号。
6. 一轮跑完把汇总表与 FAIL 清单交回；不要边跑边改文档。
