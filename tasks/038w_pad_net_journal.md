# 038W：PAD_NET 增量日志的每脚网络判优

日期：2026-11-06。来源：`D:\dsh\boardwise-reviews\boardwise-bug-pad_net-journal.md`（真实工程只在本地报告中被引用，不读取、不写入、不纳入夹具）。本批是 shared parser 修复，不改规则、绘制、CLI 参数或报告 schema。

## 1. 根因与边界

- 038U 的原子一致性视图按“文档 + 完整归一化 id”判优。`PAD_NET` 的完整 id 含 `(component, pin, pad_element_id)`；改板后 pad element id 也会变化，因此旧/new 两条原子记录都可合法保留。
- PCB 的每脚投影键却只有 `(component, pin)`。当前 `collect_pcb_context` 对该字典使用 `setdefault`，导致文件靠前的旧网值获胜；`build_design_model` 和 `build_pads` 随之读到改板前的网络。
- 不能简单改成“最后一条赢”：038U 已证明 ticket 在文件中可局部倒序。每脚投影必须复用原子视图的同一 ticket/client 判优，不复制第二套比较规则。

## 2. 公开行为合同

1. `iter_epru_records`、`resolve_document(s)` 的原始帧和原子一致性合同不变；不把不同 pad element id 猜成同一个原子 id。
2. `collect_pcb_context` 在建立 `pad_nets_by_pin` 前，按 `(component, pin)` 分组所有活的 PAD_NET 记录，并复用 `epru_stream._resolve_group`：
   - ticket 大者胜；同票时 record.client（缺省回退 DOCHEAD client）字典序大者胜；
   - 只有一条活记录时保持旧行为，即使它没有 ticket；
   - 多条记录但 ticket/client 无法唯一判优、或同 client 同票载荷分歧时，不选 stream order、不保留旧值：该每脚键缺席，并给 `stats.consistency_unresolved` 增加一组诊断。
3. 新值是空网时必须真的覆盖旧网，不能因“空值不填”又回退旧网。空网与 unresolved 仍由不同证据区分；未判优不声称已断开。
4. `pad_nets_by_pad` 的当前元素 id 查表路径不变；原理图、库、原始 ParseStats 其他计数、CLI、finding/severity/verdict 合同不变。
5. 两个实际消费者：PCB 几何 `build_pads` 与 PCB 网表 `build_design_model` 必须读同一个每脚胜者；跨视图不得再把新旧记录拼成不存在的中间状态。

回退只需恢复每脚投影的旧路径，不涉及文件迁移、报告 schema 或真机状态。

## 3. negative control

新增合成测试，不修改 `tests/fixtures/`：

- 旧 `TIM1_CH1` → 新空网，两个文件顺序都必须得到空网；
- 旧空网 → 新 `DAC1`，高 ticket 在前也必须得到 `DAC1`；
- 同票时 client 大者胜，record client 缺省回退 DOCHEAD client；
- 缺 ticket、同票无 client、同 client 同票不同网均不得猜，键缺席且 unresolved 计数正确；
- 单条无 ticket 记录保持旧行为；
- 同一脚的不同 pad element id 可共存于原子记录流，但每脚模型只有一个胜者；其他脚不串网；
- `build_pads` 与 `build_design_model` 的公开读数一致；除已被 ticket 证明属于改板后新值的 PAD_NET 投影外，其他模型/findings 基线不变，有意修正必须逐条记录。

至少两次变异：ticket 比较方向、把空新值误当成可回退旧值；测试必须转红后用 cp+SHA-256 恢复。

## 4. 兼容矩阵

| 维度 | 本批覆盖 | 不得声称 |
|---|---|---|
| V3 `.epro2` | 其他归档读数不变；已被 ticket 证明的旧 PAD_NET 值按新值有意纠正 + 合成增量日志 | 原真实工程已重跑/宿主 DRC 已复核 |
| V4 `.eprj3` | 复用同一 PCB context/一致性视图 | 真实多版本 V4 样本已验证 |
| `.eprj2` | 不改工程壳 | 内部协同 pend/revoke 已支持 |
| 在线/离线 | 仅离线模型输入 | 在线取档或真机已验收 |
| 普通器件/CBB | 普通 PAD_NET | CBB 未覆盖 |

## 5. 文件域与验收

- `src/boardwise/parsers/epru.py`：每脚投影与过时注释。
- 新 `tests/test_038w_pad_net_journal.py` 及必要的 038U 邻域断言。
- 本任务书；完成后同步 `tasks/review-line.md`、`tasks/TASKMAP.md` 和本报告对应任务记录。

聚焦：038W、038U/038I、040/040b、042、049、epro2_model、125/126、owner/doc；随后按串行纪律跑全量及四线。禁止改 fixtures、绘制线、connector/DSH/Rust 业务实现、真实工程；零 git 写、零删除、零真机。

## 6. 实施与实测证据（2026-11-06 子代理落盘）

实现：`src/boardwise/parsers/epru.py` 新增 `_pad_net_pin_projection(document, stats)`，复用 `epru_stream._resolve_group`（import 私有 helper，无第二套比较算法）；`collect_pcb_context` 在遍历前一次性算出 `context.pad_nets_by_pin`；PAD_NET 分支只保留 `pad_nets_by_pad` 写入，删掉 `setdefault`。测试：新增 `tests/test_038w_pad_net_journal.py`（15 条，纯内存合成，未读写夹具）。

夹具实测（`tests/fixtures/*.epro2`，12 份可读 V3 归档 + 4 份无 PCB/非备份跳过；日志 `.tmp_038w/fixture-probe.txt`、`fixture-drift.txt`）：

- 每脚投影覆盖 2248 个 `(comp,pin)`；其中**同脚多条活 PAD_NET 共 99 组**——DCDC 14、FPC 2、ROBOT ctrl FOC 76、毕设FOC v1.0.0 2、llc 1、双面板-全能型 2、新板 2。全部按 ticket/client 判优成功，`consistency_unresolved` 全 0。
- **值漂移只出现在 `ProPrj_ROBOT ctrl FOC_2026-09-16.epro2`：14 个 `(comp,pin)` 键变化（7 个 pad 网变化），其余 11 份为 0 漂移。** 该夹具本身带改板前后的 pad element id（例：`["PAD_NET","add2831eb118fd8a","8","e204"]` ticket 185273 `TIM1_CH1` vs `[…,"8","e23"]` ticket 193923 空网），旧路径 first-wins 读旧网，新路径按 ticket 读新网（该脚记为断开、同脚新编号 33–44 拿到同名网）。**主代理裁定：这是本批要修的有意行为修正，不得为了“基线不变”保留已证伪的旧网值**；其余读数不变才是 negative control。原真实工程未重跑，不声称 crossView 已真机 clean。
- 聚焦 9 文件 228 passed（`-n 4 --dist loadfile --basetemp=.tmp_pt_038w`）；另加跑受影响夹具的邻域 6 文件（040b/epru_parser/072 覆盖闸/039c 审查流/013/090）215 passed，含 `pads_without_net` 与 pad_count 恒等式。

变异（`cp` 备份 + SHA-256 还原，两次都转红后字节一致，`768f9eee50d5a9e0ddcc3a674db24664145559667c5182ce8eb9403f476f6800`）：①ticket 方向取最小 → 10 failed；②空胜者回退首个非空值 → 3 failed。

未做：全量四线、真机、其他线（按合同由主代理统一跑）。


## 7. B5 复核修复 A（2026-11-06，焊盘映射与墓碑走生产视图）

### 7.1 复核发现

1. `PAD_NET` 的两个键不总是关于同一只脚：`padId`（焊盘元素 id）与 `padNum`（脚号）在改板后
   可错位。`build_pads` 先查 `pad_nets_by_pad[(comp.id, template.id)]`，只要元素 id 命中就把
   那个网写到这只焊盘上，而这只焊盘的脚号是 `template.num` —— 于是**PCB 几何**给 pad A 写了
   pin B 的网，**PCB 网表**（`build_design_model`，先读 pads 再读 `pad_nets_by_pin`，
   首见为胜）把同一个网当作 pin A 的网，而 `pad_nets_by_pin` 里 pin A 的胜者却是另一个网。
   两个公开消费者读同一块板读出两个答案。
2. `test_empty_body_tombstone_is_not_a_version` 直接拿原始记录喂 `collect_pcb_context`，
   绕过了生产入口的一致性视图（`load_epro2_source` → `split_documents(consistent=True)`）。
   在原始流里墓碑对 `_pad_net_pin_projection` 不可见（`body is None` 被跳过），旧网胜出 ——
   这个「通过」在生产里根本走不到。

### 7.2 改法

- `PcbContext.pad_pin_by_pad`：`(component id, pad element id) -> PAD_NET.padNum`，
  在 `collect_pcb_context` 的 `PAD_NET` 分支随 `pad_nets_by_pad` 一起写（空体墓碑在
  外层 `body is None` 处已跳过，不产生映射）。
- `build_pads(... , pad_pin_by_pad=None)`：**新增末位关键字可选参数**，五个/六个参数的旧调用
  一字不改即旧行为。映射在场且 `PAD_NET.padNum` 与 `template.num` 不一致时
  `stats.pad_net_pin_mismatch += 1` —— **只披露计数**（见 §8 的返修裁定，B5 最初那版
  「改取每脚胜者」已回退）；网络仍走 `pad_nets_by_pad` 命中即用、`None` 再落
  `pad_nets_by_pin`（所以「判优结果为空网」仍能覆盖旧网）。`collect_pcb_context`
  把 `context.pad_pin_by_pad` 传进去。
- `ParseStats.pad_net_pin_mismatch: int = 0`（**末尾**、每焊盘一次）。**不进** `as_dict()`、
  **不并** `coverage.recordsDropped`、不动 verdict：这里什么都没丢，是窄键赢了宽键。
  （不进 `as_dict` 是硬约束：`tests/test_038u_record_consistency.py` 钉了
  `list(payload)[-3:]` 的键序。）
- 测试：`tests/test_038w_pad_net_journal.py`
  - 墓碑用例改走 `split_documents(..., consistent=True)` 再喂 `collect_pcb_context`，断言
    **生产语义**：获胜墓碑删掉该元素 id 的活记录（视图里只剩 `body=None` 那一条）、
    `(comp, pin)` 键**缺席**、`(comp, "e100")` 在 pad-id 表也缺席、
    `consistency_duplicate_groups == 1`。旧用例（绕过视图）**删除**，不保留不可达断言。
  - 新增合成负例（返修后语义，见 §8）：`test_a_renumbered_pad_is_disclosed_and_keeps_its_pad_id_net`
    （pad id `e204` 的 `PAD_NET.padNum=1`，footprint `num=33`；焊盘读数**仍是 pad-id 网**
    `OLD_PIN_NET`，网表 pin 33 随焊盘同读 `OLD_PIN_NET`，`pad_net_pin_mismatch == 1`，
    `pads_without_net == 0` 证明这不是丢记录）、
    `test_a_caller_without_the_mapping_keeps_the_old_pad_id_path`（旧调用兼容：
    不传映射 → 同一条 pad-id 路径、无披露计数）、
    `test_a_consistent_pad_keeps_the_pad_id_reading_verbatim`（一致 → 旧读数、计数 0）。

### 7.3 真实读数（只读，**不写断言**）

`tests/fixtures/*.epro2` 14 份（2 份无 PCB）：`pad_net_pin_mismatch` 只有
`ProPrj_ROBOT ctrl FOC_2026-09-16.epro2` 为 **1**，其余 13 份 0
（`.tmp_b5_fix_a/probe_out.txt`）。那一处：`C3` 的 pad 元素 `e16`，footprint `num=1`，
`PAD_NET.padNum=2`；pad-id 网 `OSC-OUT`、pin 1 的每脚胜者 `GND`。B5 最初那版把这只焊盘
改读 `GND`，**已按 §8 的裁定回退**：现在读 `OSC-OUT`，`C3` 两脚同网、`GND` 岛 295 成员，
`pads_without_net` 仍 43（`.tmp_b5_repair/probe.py`）。测试里不写任何 ROBOT 预期
（任务要求：只读可解释，不写预期）。

### 7.4 变异（两次，`cp` 备份 + SHA-256 还原）

备份 `.tmp_b5_fix_a/epru.py.bak`，B5 当时的交付版 sha256
`4fd81520a1feef529af6ced4226d02eb1f6e6b818b57c657c96ed7f34646feef`：

1. **padNum 不一致仍按 pad id**：把不一致分支短路成不成立（永远走旧路径）→ 当时那条
   「改用每脚胜者」用例 1 红，其余 17 绿（`.tmp_b5_fix_a/mutation2.log`）；
   还原后字节一致、18 passed（`mutation2_restored.log`）。**该分支已删（§8）**，
   这条变异随行为一起失效，不再主张。
2. 另一半的变异（端点语义）在 `tasks/527c2_cross_view_geometry.md` §8，同样 cp+SHA-256。

### 7.5 回归

聚焦 6 文件（见 §8 的 527C2 同一批命令）→ 156 passed / 1 failed（唯一失败是既有的
`rulebody` 目录指纹，与本批无关，见 527C2 §8）。另加跑受影响夹具邻域
`test_040b_boards test_epru_parser test_013_symbol_fallback test_090_design_intent
test_126c_pcb_ipc_rules test_127b_blind_review_fixes` → **166 passed**
（`.tmp_b5_fix_a/neighborhood.log`），ROBOT 那一处改判没有把任何既有夹具读数推翻。

### 7.6 未做 / 边界

- 未改 `pad_nets_by_pad` 的当前元素 id 查表语义、038U 视图、`build_design_model`、
  规则、CLI、报告 schema。
- V4 `.eprj3` 走的是同一个 `collect_pcb_context`，但本批没有多版本 V4 真实样本，不声称已验证。
- 全量四线、真机、其他批次未碰；零 git 写、零删除、零真机、零额外线 agent。

## 8. B5 返修：padNum 不一致**只披露计数**，pad-id 网保留（2026-11-06 主代理裁定）

### 8.1 裁定内容

`PAD_NET.padNum` 与 `FOOTPRINT.num` 不一致时，`build_pads` **只给
`stats.pad_net_pin_mismatch` 加一，不改这只焊盘的网络**。§7.2 里「不一致就不用 pad-id 的值、
改取每脚胜者」的那一版**整体回退**：`build_pads` 回到 pad-id 优先、`pad_nets_by_pin` 只在
pad-id 表没读数（命中 `None`）时兜底。

### 8.2 为什么要退

B5 那一版在真实夹具上把两个公开消费者改成一致，代价是**改写几何**：

- `ProPrj_ROBOT ctrl FOC_2026-09-16.epro2` 的 `C3`：pad `e16`（`num=1`）的 `PAD_NET`
  写的是 `padNum=2`、网 `OSC-OUT`。改取 pin 1 的每脚胜者后，这只焊盘读 `GND` —— `C3`
  两端变成 `OSC-OUT` + `GND` **双网**，`GND` 岛成员由 295 变 **296**（+1）。
- 也就是说「让网表和几何读到同一个值」这一步，动的是**焊盘的网**，而焊盘的网不是本批该裁决
  的东西。计数能说明「这两条记录不一致」，不需要替板子选一个答案。

### 8.3 现在的读数（只读探针 `.tmp_b5_repair/probe.py`）

| 对象 | 读数 |
|---|---|
| ROBOT `C3` pin1/pin2 | `OSC-OUT` / `OSC-OUT`（双网消失） |
| ROBOT `pad_net_pin_mismatch` | **1**（照旧披露） |
| ROBOT `pads_without_net` | 43（未变） |
| 合成负例 pad `e204`（`padNum=1`、`num=33`） | 焊盘 `OLD_PIN_NET`（pad-id 网保留）、网表 pin 33 随焊盘 `OLD_PIN_NET`、`pad_net_pin_mismatch=1`、`pads_without_net=0` |
| 不传映射的旧调用 | 同一条 pad-id 路径、不披露（无配对可比） |

### 8.4 具体改动

- `src/boardwise/parsers/epru.py`：`build_pads` 的 `if/else` 改回「先 pad-id、`None` 再 per-pin」，
  不一致只在前面多一次 `stats.pad_net_pin_mismatch += 1`；`build_pads` docstring、
  `PcbContext.pad_pin_by_pad` 注释、`collect_pcb_context` 的 `PAD_NET` 分支注释统一改成
  「披露而非改写」。`pad_pin_by_pad` 字段与参数**保留**（它就是披露的来源）。
- `tests/test_038w_pad_net_journal.py` §8：负例改名
  `test_a_renumbered_pad_is_disclosed_and_keeps_its_pad_id_net`，断言 pad 读 pad-id 网、
  网表随焊盘同读、计数 1、`pads_without_net` 0。**负例保留，没删**；另两条（不传映射、
  一致的焊盘）语义不变。
- `tests/test_072_coverage_gate.py`：`NOT_WIRED` 注册 `pad_net_pin_mismatch`
  ——编号不一致披露，不是 record loss，不并 `recordsDropped`、不动 verdict。

### 8.5 回归与实测

聚焦 12 文件（本批 + 131d/133d/88f/131d/layer_rules），命令
`-n 4 --dist loadfile --basetemp=.tmp_pt_b5_repair`：**448 passed / 1 failed**，
唯一失败是 `test_layer_rules.py::test_no_private_name_crosses_a_layer`
（`cli.py: imports core._project_uuid (private)`）—— 那是本批之外的
design-intent 守卫批次在 `cli.py` 新加的函数局部 import，与 PAD_NET 无关，本批文件域内无法修。

修前同一命令是 13 failed / 436 passed，其中 131d（2）、133d（1）、88f（1）正是 8.2 的
`C3` 双网与 `GND` 岛 +1，回退后全绿。

### 8.6 边界

未改 `pad_nets_by_pad` 的当前元素 id 查表语义、038U 视图、`build_design_model`、规则、
CLI、报告 schema；未碰 fixtures、`blocklib/parts.json`、绘制线；零 git 写、零删除、零真机。
