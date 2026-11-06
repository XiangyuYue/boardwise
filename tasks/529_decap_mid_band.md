# 529：去耦 mid 容值带与 191D 收窄回退

日期：2026-11-06。上游：`tasks/528_060_gate.md` §4。只改审查线 `pcb-decap-distance` 的分类与既有临时收窄，不改 MCU supply、FOC 自有 100µF 池、稳压器判定、绘制或四个距离阈值。

## 1. 实测结论

只读探针（`.tmp_529_probe/`）确认：

- 当前 `HF_FARADS=1µF`、`BULK_FARADS=10µF` 之间没有角色，常见 2.2/4.7µF 全落 unknown。
- 五块覆盖夹具与实板代号样本中，2.2µF×14、4.7µF×3；FOC 输入档的 2.2µF 假 WARN 正是空白带造成。
- `HF_FARADS` 被 `mcusupply` 复用并钉死为 1µF，不能直接上调。
- 四个距离档 `200/300/800/200` 是岳已裁不变的值；mid 复用这些既有轨档，不新增 mil 档。
- 191D 的临时收窄是「输入档只有一个候选都没有才 WARN」。补全分类后应恢复「输入档没有 HF/mid 去耦就 WARN」，候选存在但只是 bulk/unknown 不能冒充高频去耦。

主代理裁定：新增 **`mid` 角色**，表示 >1µF 且 <10µF 的电容（边界容差沿用 `_BOUNDARY_FARADS`）；它进入去耦候选池，但不改变 `HF_FARADS` 常量或其他规则。

## 2. 公开行为合同

1. `capacitor_role()`：
   - `>=10µF` 仍为 bulk；
   - `<=1µF` 仍为 high-frequency；
   - 中间为 `mid`，不再 unknown；
   - 无值/无法恢复仍 unknown，不猜。
2. `pcb-decap-distance` 的近距离候选池接受 high-frequency 与 mid；bulk 仍只作 bulk 证据，unknown 仍只作未知证据。变量可保留 `high_freq` 名称以减小 diff，但注释/证据文案必须说明池含 HF+mid。
3. 距离阈值继续由 `DECAP_TIER_MIL/PINS` 的轨角色决定；mid 不创建新 tier，不修改 `DECAP_TIER_ORDER`。
4. 撤销 191D 的 `not candidates` 临时收窄，但**只作用于「general 无 HF/mid」分支**
   （bulk+unknown、unknown-only、一颗电容都没有）：输入档按 `_no_candidate_severity(tier)`
   判 WARN，即使存在 bulk/unknown 候选也不把它当高频去耦。`bulk and not unreadable` 的
   **全 bulk 分支仍是 `severity="INFO"`**（127b 岳裁定 5b 的既有特例，529 不改、也不给它加
   regulator input 子句）。无电容的真实负例仍必须 WARN。
5. `HF_FARADS`、`mcusupply.HF_CEILING_FARADS`、`regulator.HF_POOL_FARADS`、FOC 100µF 池及所有其他规则不变。

## 3. 有意读数变化与负例

- FPC `U5@+5V`：2.2µF 进入池后，原 337.4 mil 假 WARN 消失。
- FOC-OLD `U11@+5V` 的 2.2µF 假 WARN 消失；4.7µF 的 INFO 消失。
  **整份夹具的读数**（`tests/fixtures/ProPrj_毕设FOC驱动板_2026-09-17.epro2`，`checkup --file`）：
  findings **241 → 239**，severity **50E/21W/170I → 50E/20W/169I** —— 消失的正是一条
  `decap-required-caps` WARN 和随它的那条 INFO，`completion.verdict` 仍 `incomplete`
  （另有缺数据手册与未分类 WARN）。这是 529 的有意读数，041/041s2 的冻结常量已按此同步
  （`tests/test_041_cross_board_nets.py`、`tests/test_041s2_interconnect.py`），review 侧
  45 findings、30E/1W/14I 不变。
- FOC-V1 的 4.7µF INFO 消失。
- DCDC `U9@+12V`：4.7µF 是唯一去耦，距离 522.6 mil 超过输入档 300，**新增 WARN 是恢复检测能力后的有意发现，不为保旧计数而豁免**。
- 撤销收窄后，智能药箱 `U11@+5V` 的 bulk+无值组合不再被“有候选”掩盖，恢复输入档 WARN；这是「无 HF/mid」与「一颗电容都没有」的区别。
- 合成负例：完全无电容仍 WARN；2.2/4.7µF 近距离不再报 unknown；bulk-only/unknown-only 输入轨仍报；MCU/FOC 规则读数不变。

## 4. 文件域与验收

- `src/boardwise/rules/pcb/distance.py` 的角色、候选池、临时收窄与注释。
- `tests/test_529_decap_mid_band.py` 新增合同测试；`test_127b_blind_review_fixes.py`、`test_191d_decap_tiers.py` 及真实夹具相关断言只做有证据的调整。
- 本任务书与最终 review-line/TASKMAP 记录。

聚焦至少跑 529、191d、127b、131b、126b、131e、164b、011d、regulator/mcusupply/foc 邻域。至少两次变异：mid 被排除出池、恢复 `not candidates` 收窄；必须转红后 cp+SHA-256 恢复。禁止改 fixtures、绘制线、真实工程；零 git 写、零删除、零真机。全量在夜间总验收串行执行。

## 5. 实施与证据（子代理 2026-11-06）

**实现**（`src/boardwise/rules/pcb/distance.py`）：

- 新增 `CAP_ROLE_MID = "mid"`；`capacitor_role()` 的 `1 µF < c < 10 µF` 分支由
  `CAP_ROLE_UNKNOWN` 改为 `mid`，reason 文案 `… — mid-band decoupling`。`unknown` 只剩
  「没有可读容值」两例（空值 / 非容值字符串）。**未新增 farad 常量**，`BULK_FARADS` /
  `HF_FARADS` / `_BOUNDARY_FARADS` 一字未动。
- `_one_net()` 候选池 `high_freq` 收入 `(CAP_ROLE_HF, CAP_ROLE_MID)`（变量名保留）；
  docstring、角色证据与两条「无候选」行的证据文案改成 HF+mid。距离仍取
  `DECAP_TIER_MIL`（200/300/800/200），未加档。
- 撤销 191D 的 `not candidates` 收窄，**只作用于 general 无 HF/mid 分支**：bulk+unknown、
  unknown-only、无电容三类的 `severity` 改为 `_no_candidate_severity(tier)`。`bulk and not
  unreadable` 的全 bulk 分支保持 `severity="INFO"` 与原文案（岳裁定 5b 特例），529 未改其
  严重度、也未加 regulator input 子句。

**实际计数**（聚焦九文件，`-q -n 4 --dist loadfile --basetemp=.tmp_pt_529`）：
`287 passed, 1 skipped`（529 新增 22 例；日志 `.tmp_529/run_final.txt`）。

**真实夹具漂移**（只有三处，全部有探针证据 `.tmp_529/probe_drift.txt`）：

| 读数 | 旧 | 新 | 理由 |
|---|---|---|---|
| 毕设FOC `U11@+5V` | WARN 561.3 mil（对 C30 100nF，`recovered`） | 静默 | C28 `2.2uF` 距 VIN 焊盘 **31.7 mil**，输入档 300 内。561.3 是「最近的**可读 HF**」而非「最近的去耦件」，故 529 判它是 #86 前提自带的假阳性 |
| 毕设FOC `U7@+24V` | INFO 无候选 | 静默 | C17 `4.7UF` 距 **26.4 mil**，输入档 300 内 |
| 毕设FOC `U11@NET10` | INFO | INFO（不变） | C26/C27 值为 `C104`/`C103`，输出档 800，unknown → INFO |

DCDC `U9@+12V`（522.6 mil，mid 唯一去耦）与智能药箱 `U11@+5V`（bulk+无值→WARN）在聚焦
夹具外，已用合成用例在 `tests/test_529_decap_mid_band.py` 里钉住（`522.6` 与 bulk+unreadable）。

调整的真夹具断言：`test_126b` 的 FOC 锚（3 行→1 行，改名 `…_one_info_after_529`）、
`test_127b` 的 FOC 验收（3 行→1 行）与 bulk-only 文案、`test_131b` 的 4.7uF 角色名
（unknown→mid，分歧本身保留）、`test_191d` 的「全 bulk/未分类仍 INFO」一例（拆成
mid 进池 WARN / bulk-only **INFO** / bulk+unknown WARN / unknown-only WARN 四类形状）。
**没有删除任何负例**：无电容 WARN、consumer 与输入档 bulk-only INFO、100nF 310 mil WARN 全部保留。

**主代理复核后的收窄（同批）**：全 bulk 的 INFO 是 127b 岳裁定 5b 特例，529 不动——branch 1
恢复 `severity="INFO"` 并删掉为该分支新加的 regulator input 子句，只有 general 无 HF/mid 分支
按轨判；529/191d 的 bulk-only 期望改回 INFO（`test_529` 的 `_stays_info_but_keeps_the_bulk_message`、
`test_191d` 的 `…_keeps_its_info`），bulk+unknown 仍 WARN。

**变异**（`cp` 备份 + SHA-256 还原，`.tmp_529/distance.py.bak`，前后哈希一致
`2a790d3b…99d`）：

1. mid 被排除出池（`role in (CAP_ROLE_HF,)`）→ **10 红**（含 529 四档参数化、DCDC 522.6、
   mid 静默/超限、127b+126b 两块真实夹具），`.tmp_529/mut1_mid_excluded.txt`；
2. 恢复 `not candidates` 收窄 → **4 红**（529 unknown-only、bulk+unknown、191d 两例），
   `.tmp_529/mut2_narrowing_restored.txt`。

**未做**：全量（按任务书留给夜间串行）；真机与绘制线零触碰；`tasks/TASKMAP.md` /
`review-line.md` 的登记由主代理做。
