# 558：手册异常件的义务分类与诚实结案路径

## 1. 前因后果与已取得的证据

岳的目标第 4 项。555 的真实试点暴露：机械件被给 `(没有 MPN) datasheet pdf`，连接器被要求七类 IC facts；SCREW 的 `M3螺丝` 还会以弱 name 匹配误中 `STM32…pdf`。EST026 的扫描 PDF 已用 `pdfimages` 取图并由主代理视觉读取：有 WI05-1-028 / 9A.042063080 机械图，无 EST026 字样、无脚表，不能过文字引文闸。U8 公开搜索只有非同字 MPN 的家族候选，身份仍未决。证据 `evidence/558/`。

本批只修报告与工单语义，不放宽 verdict/facts 闸，不写货架或 trust，不安装 OCR。三份 `machine_verified` 继续待人工签核。

## 2. 公开合同

`unreviewed_parts[]` 每行新增：

- `obligation`: `ic-facts` / `connector-pinout` / `identity-unresolved` / `no-ic-facts`。
- `obligationBasis` 与 `kind`：来自现有 `classify_part` 或本批机械义务声明，不另造 PartKind。
- 连接器另带 `pinoutSource: "none"`：当前货架没有可消费的通用脚表证据；板上已有引脚不等于厂家脚表。

义务判定：

1. 只有明确机械声明（`螺丝/螺母/铜柱/螺柱/安装孔/固定孔/mounting hole/standoff`，英文按边界）给 `no-ic-facts`。不能只凭 SCREW 前缀、U 位号、未知 kind 或 `screw terminal` 判机械。
2. `classify_part(..., library=..., pin_floor=False)` 为 connector 时给 `connector-pinout`，不再列七类 IC `missingFacts`，查询词改问 pinout/引脚定义/脚位图。
3. 非机械、无 MPN 且无合法 C 号时给 `identity-unresolved`，不列七键；合法 C 号复用 `engines.hunt.is_c_number`，服务是否认识另记。
4. 其余需要 IC facts 的现行行保持 `ic-facts`，七键、查询词与行为不变。

机械件的 engineer/lcsc 通道为 `ok:null + applicable:false`，不做本地 PDF 匹配；official 查询为空，question 指向 `parts accept-unknown --reason`。新增第四类 `无 IC facts 义务（待人工结案）`，机械行从「真缺资料」改归此类；`unreviewed_parts` 行和 `verdict=incomplete` 均保留。

`needs_datasheet_section` 不再把 `no-ic-facts` 的 facts 种子交给 hunt，但审查者显式 marked 的行仍保留。折叠时传播 obligation/basis/kind/pinoutSource；跨板同位号不同身份仍逐行，不合并。

## 3. 文件域与禁触

仅 `src/boardwise/engines/checkup.py` 相关段、新 `tests/test_558_datasheet_obligations.py`、`docs/parts.md` 本批说明、`.tmp_558/`、`.tmp_pt_558/`、`evidence/558/`。不改 `core/partkind.py`、cli.py、绘制线、bridge、合同快照、fixtures/reviewsets、真实设计、全局/试点货架和历史证据。

先 cp 备份 checkup.py 并记 SHA。零 Git 写、零 rm/unlink、零全量 pytest、零 bridge/EDA、零部署发布。

## 4. 测试与 negative controls

新测试至少钉住：

1. `M3螺丝` 无身份：no-ic-facts、无查询、无误配 STM32 PDF、needs 不再含 facts 种子，但 unreviewed 与 incomplete 仍在；显式 marked 不被过滤。
2. U 位号三脚 MX 连接器：connector-pinout、missingFacts=[]、pinoutSource=none、查询含脚表，needs/unreviewed/verdict 不清闸。
3. C 号有效但无 MPN 的 EST026 形连接器：connector-pinout，不是 identity-unresolved。
4. 无 MPN/C 的三脚 IC：identity-unresolved，不得变 no-ic-facts；U 位号 330k 电阻与 ≤2 脚既有被动豁免不变。
5. `screw terminal` 不得仅凭英文 screw 变机械；跨板同名不同身份不并行；机器档 trust 和机器待签类不变。
6. 旧 186/188B/190/191A/522/555 聚焦不回归；owner/layer/doc-claims 通过。

主代理至少两独立变异：机械行重新进入 hunt、连接器重新列七键，相关测试必须先红后 cp+SHA 恢复。真实 `.tmp_555` 只读重算到 `.tmp_558/after/`，对拍机械、EST026、U8、三机器档和 verdict，不改原报告。

## 5. 交卷

一个 coder，≤40 步/30 分钟，≤2000 字。实际命令→汇总→差异、真实对拍计数、SHA、未决项。找不到身份仍具名待人工，绝不把 no-ic-facts 写成 clean/verified。

## 6. 实际完成（560 收尾时补记）

- 父验聚焦 **135 passed in 19.03s**；变异 A（禁机械分支）**4 failed**、变异 B（禁连接器分支）**2 failed**，恢复 SHA `2e2b228f…`（`evidence/558/parent-validation.md`）。
- 父关键 diff 复核检出首版缺口：机械行在 `seed_by_part` 构建前就被过滤，`marked` 只剩外壳。558B 返修——标记行仍收集 seed，过滤下沉到 facts 触发输出循环。
- 真实重算的不变式（unreviewed **23→23**、needs_datasheet **15→11**、`verdict=incomplete`、三份 `machine_verified`）以 `evidence/558/obligation-recompute.json`、`obligation-recompute-558b.log` 为准，不写成清闸。
- EST026 三行在本批仍是 `ic-facts`（`partkind` 禁触），由 558B 用 shared 精确族词处理；三份机器档仍待人工签核，U8 身份未在行内伪造结论。
- 状态：**工作树完成、未提交未推送**。
