# 038U：EPRU 记录一致性只读差分与 shared 集成合同

日期：2026-11-05。状态：**038U1/U2 均已实施（尚未提交）**。
调查阶段没有修改解析器、规则、夹具或真机工程；实施证据见 §8。

## 1. 官方格式依据

官方 `easyeda-format-skill` 在固定版本
[`4fcab1747d47b2ae01d7f93a485859970c5cf933/SKILL.md`](https://github.com/easyeda/easyeda-format-skill/blob/4fcab1747d47b2ae01d7f93a485859970c5cf933/SKILL.md)
的「最终一致性」「删除怎么表达」两节明确写明：

- 判优键是「文档 + 归一化 id」，**type 不参与竞争**；同 id 换 type 仍属于同一条链。
- ticket 不同，大者胜；ticket 相同，比较文档头的 `client`，**字典序大者胜**。
- 原子记录删除是同一 id 追加一行空 body；它不是普通“没有几何”的未知记录。
- 文档删除是 `DELETE_DOC` + `{"isDelete":true}`；`false` 可撤销删除。它不同于原子空 body。
- 协同内部的 pend/revoke 不属于本次静态归档范围。

旧 2.0 文档的 client 方向与实现相反，本任务只采用上述官方 3.0 校准后的「大者胜」。

## 2. 现状与旧归档基线

`parsers/epru_stream.py` 当前只解码并原样产出记录；`ticket` 被保存但没有判优消费者，
`firstTicket` 也没有判优消费者。下游各自使用 stream order、first-wins 或 last-wins，
不是同一个一致性视图。

对 `tests/fixtures/*.epro2` 的 14 份归档逐文档扫描（只读）得到：

| 检查 | 实测 |
|---|---|
| 重复文档段（同 docType + uuid） | 0 |
| 文档内重复 id | 0 |
| 文档内跨 type 同 id | 0 |
| id 非空的空 body 记录 | 5,844；均没有同 id 的活记录版本 |
| `DELETE_DOC isDelete=true` | 2 个 SCH_PAGE；均为 3 行空页（DOCHEAD/META/墓碑），无器件、无导线 |

因此必须区分两件事：**ticket 在文件里局部倒序是常见现象**，但只有「同文档同 id 多版本」
才需要判优。现有归档有前者，没有后者，不能拿 ticket 下降次数冒充重复记录缺陷。

这也意味着 038U1 的元素级一致性视图在这 14 份归档上应保持所有公开模型读数不变；
空 body 从“跳过”改读为“删除同 id 旧版本”仍不会改变它们，因为没有同 id 旧版本。

## 3. 四类合成探针：缺陷已证实

探针走现有 `iter_epru_records` + `schematic._split_page`，只使用手写 SCH_PAGE 记录。
client 用例使用同页 uuid、不同 DOCHEAD client 的两个版本流；它证明当前没有判优，
不声称真实导出已经观察到这种物理排布。

| 场景 | 官方应得 | 当前实测 |
|---|---|---|
| 同 id ATTR，ticket=20 的 `R_NEW` 在 ticket=10 的 `R_OLD` 前 | `R_NEW` | `R_OLD` |
| 同票同 id，client=`b…` 的值在 client=`a…` 前 | client b 的 `R_CLIENT_B` | 后到的 `R_CLIENT_A` |
| 同 id 的 ATTR ticket=10、TEXT ticket=20 | TEXT 获胜，旧 ATTR 不生效 | `R_STALE` 仍生效 |
| 同 id ATTR ticket=10、空 body ticket=20 | ATTR 被删除 | `R_STALE` 仍生效 |
| 页内 `DELETE_DOC isDelete=true` | 整页不进入模型 | 器件 `R1` 仍进入模型 |

结论：不是“再调一个 first/last-wins”能修的问题；必须在进入原理图、PCB 和库模型前
建立同一个静态一致性视图。它属于 shared parser/model，不得夹带审查规则或绘制算法改动。

## 4. 038U1：元素级一致性集成（下一小批）

### 公开合同

1. `iter_epru_records` 保持**原始帧视图**：逐行解码、原始 ParseStats、038I Rust 差分投影不变。
   新增的一致性视图是模型输入层，不把原始日志重写或排序后冒充原始文件。
2. 在每个文档身份 + 归一化 id 内选唯一胜者，type 不参与键。普通字符串 id 精确比较，
   空字符串按无 id 原样保留；JSON 数组 id 解析后 canonical JSON 比较，不删除数组里的类型、
   不修剪普通 id、不猜别名。**复合数组是否还应剥掉类型前缀，公开资料没有说明**：
   本批只合并解析后完全相同的数组，数组成员不同的不猜成同 id，不宣称这一维已经判优完成。
3. ticket 大者胜；同票再比较来源 client，字典序大者胜。任一版本 ticket 缺失/非数值、
   同票时 client 缺失、或同 client 同票同 id 但载荷分歧时，不得用 stream order 冒充已判优：
   保留原始组并给出显式 `consistency_unresolved` 诊断，模型覆盖必须能披露这一点。
4. 获胜空 body 删除该 id 的所有活版本；较低 ticket 的空 body 不得误删较新版本。
   **获胜墓碑仍以 body=None 留在记录流里充当顺序边界**，但不产生任何模型对象；否则旧原理图里
   本被空行结束的 ATTR 邻接会错误落到前一颗 COMPONENT。DOCHEAD / DELETE_DOC 按文档级
   记录类型排除，不进入原子 id 竞争。重复组的胜者占该 id 第一次出现的位置，其他版本移除，
   以最大限度保持原有邻接；胜者自己的 line_no 保留用于溯源。无重复的文档（包括只有墓碑的 id）
   必须逐记录原样返回，从结构上保证现有 14 份归档零漂移。
5. 记录 envelope 有 client 时优先使用，否则回退所属 DOCHEAD client。纯视图与公开 PCB 入口
   都用两个显式来源 client 做单元验收；同源多 DOCHEAD 的物理合流没有真实样本，本批不发明
   新的容器形状。重复 PCB、分歧库、多文件库副本的现有拒绝/first-wins 合同不变。
6. **038U1 不过滤整份 DELETE_DOC 文档**，也不改变现有页面清单；原因见 §7。

### 两个实际消费者与回退

- 原理图：`build_project_model` / `collect_page_layout` 经同一一致性视图读取 SCH_PAGE，
  042 的 ATTR parentId 双程归属保持；验证位号、页内网与布局投影。
- PCB/库：`Epro2Source` 的 PCB、FOOTPRINT、DEVICE、SYMBOL 文档经同一视图读取；
  验证 placements、PAD_NET、pour 与库 pin/meta 投影。原理图和 PCB 不得各写一份判优器。
- `describe`、原始帧差分等明确诊断原始日志的工具仍可读 raw view，但输出不得称为最终模型。
- 回退是切回 raw model input view；不涉及 CLI 参数、finding/severity/verdict、ChangePlan、
  connector/DSH 工具面或真机写操作。

### 必须不动的边界

- 单板/多板分区、跨板重号、同名网作用域、重复 PCB 拒绝、分歧库拒绝均不变。
- 既有 14 份归档的 components/nets/geometry/library/board refs 指纹与审查 findings 不变；
  原始 ParseStats 计数不变。新增一致性诊断只能另加，不能改写旧计数含义。
- Rust 038I 原始帧合同不变。本批是 Python shared 行为修复，不同时做 Rust 迁移；
  Python/Rust 既有 case book 必须逐字节一致。Rust 将来消费一致性视图前另立差分任务，
  本批不得宣称 Rust 已支持记录判优。

## 5. 038U1 兼容矩阵与 negative control

| 维度 | 本批覆盖 | 不得声称 |
|---|---|---|
| V3 `.epro2` | 14 份旧归档等价 + 合成多版本 | 真机协同日志已验证 |
| V4 `.eprj3` | 复用相同 record view；合成 SCH_PAGE/PCB | 真实多版本 V4 样本已验证 |
| `.eprj2` 本地 SQLite 壳 | 不改现有本地工程读取 | 内部编辑日志的 envelope client/pend/revoke 已支持 |
| 在线 / 离线 | 仅离线归档；在线读取零改动 | 在线宿主网表或真机协同已验收 |
| 单 / 多板 | 既有板身份与重复 PCB/分歧库守卫回归 | 跨板网络连通已改变或完成 |
| 普通器件 / CBB | 普通 COMPONENT/ATTR/LINE 等合成记录 | CBB 真实样本与 type 17 已支持 |

Negative control 至少包括：低票删除不能删高票版本；TEXT 与 ATTR 同 id 必须竞争；
不同文档同 id 不竞争；同 client 同票分歧不许后到者静默胜；无 id DOCHEAD 不消失；
两个独立板的同名 GND 不因本批被焊接；重复 PCB 与分歧库仍按原合同拒绝。

## 6. 验收与变异

- 为 §3 的五个场景及 §5 的负例建立独立合成测试；至少从原理图和 PCB 两个公开模型入口
  各验收一次，不只测一个比较函数。
- 对 14 份旧归档保存并比较修复前后的公开模型/审查指纹；任何 delta 都先停下，不改预期凑绿。
- 聚焦测试：038F1/038I/038P1、040/040b、042、049、EPRU/epro2_model、owner/doc claims。
  批次验收按仓库规定跑完整四线；全量一次一轮，独立 basetemp。
- 至少两处变异：ticket 比较方向、获胜空 body 删除；必须各有测试变红，再用 cp 备份恢复并
  核对 SHA-256。零 git 写、零真机、零删除。

## 7. 038U2：文档墓碑为什么必须另批

现有两份归档各带一个已删除的空 SCH_PAGE。当前 `board_partition` 仍把这两个页 uuid 放进
`BoardRef.page_uuids`。若按官方语义过滤 DELETE_DOC，电气模型不变，但**页面清单会变**，
与本批「旧归档读数必须保持不变」的 negative control 冲突。

所以 038U1 只修元素级判优，不偷偷删页。038U2 需要单独明确：

- 是否接受这两个已删除空页从 page_uuids 消失，并把它写成有意行为修正；
- DELETE_DOC 的 ticket/client 链、`isDelete=false` 复活、META 特例与 ParseStats.unknown_types
  的同步口径；
- 删除非空真实页面的合成反例，以及板归属链悬空时不得重新猜板；
- 真实样本后再决定多文档段/多 client 的物理合流，不能用本任务的合成形状冒充真实证据。

**038U2 裁定已获岳批准**：允许两个已删除空页及其统计发生有意变化，同批实现 true/false
和非空页删除，异常墓碑保留并披露，空板保留身份；正常删除不算解析丢失，多 DOCHEAD、
pend/revoke、Rust 和真机协同继续延期。实施合同见 `tasks/038u2_document_tombstones.md`。

## 8. 038U1 实施证据（2026-11-05，尚未提交）

### 实现落点

- `parsers/epru_stream.py`：新增 `resolve_document` / `resolve_documents` / `resolve_records`，
  以及 `split_documents(..., consistent=True)`。raw 帧入口与 038I 差分不变。
- `parsers/schematic.py`：SCH_PAGE/SYMBOL/DEVICE 与 SCH/BOARD META 在筛选前统一判优；
  FOOTPRINT 第二遍不重复计数。042 parentId 归属保持。
- `parsers/epru.py` / `eprj3.py`：Epro2Source、文本 PCB 与每份 eprj3 PCB 文件使用一致视图；
  重复 PCB 和分歧库仍在原位置拒绝。
- `parsers/board_source.py`：DEVICE META 也走同一视图；`core/geometry.py` 只追加两个诊断计数。
- `cli.py`：未判优组进入 `coverage.parseIncomplete`，非零时增加 `consistencyUnresolved`；
  旧报告的 coverage 键集合与顺序不变，recordsDropped 不把组数伪装成记录丢失。

### 独立复验

- 新合同测试 `tests/test_038u_record_consistency.py`：**56 passed**；覆盖闸
  `tests/test_072_coverage_gate.py`：**72 passed**。主代理另跑 038U/038I/042/epro2_model：
  **108 passed**。
- 14 份旧归档连续两次对拍：schematic、PCB、libraryDocuments、symbolDetails、exportedProject
  五类公开模型指纹均 **0 mismatch**；run_review findings 也 **0 mismatch**。
- 真实 CLI 合成未决探针：`checkup --file` 生成 report.json，
  `completion.coverage.consistencyUnresolved=1`、`consistency_unresolved=1`，verdict 为
  `incomplete`、退出 **3**。证明解析计数确实到达最终报告，不只是两个独立单测各绿。
- 变异均先红再用 cp+SHA-256 恢复：ticket 比较方向 8 红；丢弃获胜墓碑 1 红；
  原理图回退 raw 4 红、PCB 回退 raw 4 红；coverage 去掉 unresolved 条件 1 红。
- `tests/fixtures` 与 `reviewsets` 零改动；所有合成容器、指纹和日志都在 gitignored `.tmp_*`，
  未做真机操作或 git 写。

### 最终验收读数

- 第一轮全量 Python 到 97% 后在 900 s 超时，未形成汇总；第二轮完整复跑为
  **9453 passed / 25 skipped / 4 failed / 1 warning，1003.01 s**。按纪律没有第三轮。
- 四项红不属于本批文件域，但也不能写成全量全绿：
  - `test_193_process_guards.py::test_whole_suite_run_queues_behind_two_slots`：
    `C:\Users\xiangyu\.boardwise\pytest-slots` 的 `Errno 13 Permission denied`，队列守卫 fail-open；
  - `test_193_secrecy_hooks.py::test_the_posix_installer_sets_hooks_path_and_the_exec_bit`：
    Git/MSYS `NtCreateDirectoryObject(...): 0xC0000022`；
  - `test_543i_flag_grid.py::test_the_nearest_legal_node_is_what_was_chosen` 与
    `test_543i_visible_labels.py::test_every_reversible_run_names_itself_on_its_own_carrier`：
    绘制线当前未提交算法/测试的坐标预期失败，本批未改绘制文件，留绘制线验收。
- connector：**576 passed**，typecheck 通过；DSH：**129 passed / 1 skipped**，
  typecheck/build 通过；Rust：**111 passed / 4 ignored**，fmt/clippy/test 通过。
  三条线的构建产物在 git status 中均为干净。
- 因全量仍有上述四项红，038U1 可以说明自身聚焦验收与旧模型零回归，
  **不能**据此宣称发布闸通过或 0.6.x 全量全绿。

### 未覆盖

- 真实同 id 多版本归档仍未获得；14 份旧归档只能证明零回归，不能证明真机协同形状。
- 多 DOCHEAD 合流、DELETE_DOC 整页删除/复活、复合 id 类型前缀的额外归一化、Rust 一致性
  视图均未覆盖；不得把 038U1 称为全格式或 Rust 兼容完成。
- 人类可读 report.md 尚未单独渲染 `consistencyUnresolved` 行；JSON coverage 与 verdictWhy
  已披露，是否需要再加人类行由后续小批决定，不借本批扩大报告面。
