# 038U2：EPRU 整文档删除与复活

日期：2026-11-05。状态：**裁定已批准，已实施（尚未提交）**。前置：038U1 已完成元素级一致性。

## 1. 岳的裁定

按主代理建议执行，明确接受以下口径：

> 允许两个已删除空页及其统计发生有意变化；同批实现 `isDelete=true/false` 和非空页删除，
> 异常墓碑保留并披露，空板保留身份；正常删除不算解析丢失，多 DOCHEAD、pend/revoke、
> Rust 和真机协同继续延期。

因此，旧归档兼容线从 038U1 的「全部读数不变」收窄为：

> **除已确认删除页的页面清单、DELETE_DOC 相关统计及由删除内容直接导致的读数外，
> 旧归档的电气模型、几何和 findings 必须不变。任何额外 delta 都先停下。**

## 2. 官方规则与现有证据

官方固定版本
[`easyeda-format-skill/SKILL.md@4fcab174`](https://github.com/easyeda/easyeda-format-skill/blob/4fcab1747d47b2ae01d7f93a485859970c5cf933/SKILL.md)：

- 元素删除是空 body；**文档删除**是 `{"type":"DELETE_DOC","ticket":N}||{"isDelete":true}`。
- `isDelete:false` 可撤销删除；`DELETE_DOC` 空 body 判为**未删除**，不能与元素空 body 混用。
- META 不用空 body 删除，文档级删除走 DELETE_DOC。
- 多条标记仍按 ticket、再按 client 判优；本批不实现协同 pend/revoke。

现有 14 份 `.epro2` 中有两份各带一个三行空 SCH_PAGE（DOCHEAD/META/DELETE_DOC），无器件、
无导线。当前它们仍进入 `BoardRef.page_uuids`。本批允许这两个页面消失，其他模型读数不得变。

## 3. 公开合同

1. **raw 不变**：`iter_epru_records` 和默认 `split_documents(..., consistent=False)` 保留所有
   原始文档和标记；原始 `total_records`、`empty_body_records`、`malformed_records`、
   `records_by_type` 不改写。DELETE_DOC 登记为已知类型，停止误报 `unknown_types`。
2. **一致性视图**：`resolve_document` 先判定文档最终存活状态，再做 038U1 的元素判优。
   最终删除的文档带 `deleted=True` 且不暴露模型记录；`resolve_documents`、
   `split_documents(consistent=True)` 和 `resolve_records` 不把它交给模型消费者。
3. **true/false 全链**：最终 `isDelete=true` 删除，false 保留/恢复；乱序 ticket 和同票 client
   仍按 038U1 同一判优器处理。空 DELETE_DOC body 是合法「未删除」。
4. **异常不猜**：缺失/非布尔 isDelete、非法 ticket、同票无法判 client、同 client 同票冲突时，
   整份文档保留，增加 `consistency_unresolved`，不删除、不假装复活已确认、不按 stream order 猜。
   文档状态未决时不做内容判优，避免把部分修复误当完整结论。
5. **不合并文档**：多 DOCHEAD 同 uuid、跨文件来源和 pend/revoke 不在本批实现；每个现有段独立
   判定，不发明真实样本之外的合并规则。
6. **删除非空页**：页面 uuid 从 `BoardRef.page_uuids` 消失，页内器件/网/findings 同步消失；
   同一板其他页不变。若整板无页，保留 BOARD/BoardModel 身份和空 `page_uuids`，走现有空板
   披露；不把其他页猜进这块板，unattached 仍不可寻址。
7. **库与 PCB**：被删除的 DEVICE/FOOTPRINT/SYMBOL/PCB 同样不进入一致模型；重复 PCB 和
   分歧库守卫继续只针对实际交给模型的文档，不能借墓碑绕过拒绝。

## 4. 统计与报告

- `ParseStats.deleted_documents` 只追加，统计最终确认删除且被本视图过滤的文档，一次一个；
  `as_dict()` 同步追加。`deleted_documents=0` 时 coverage 没有 `deletedDocuments` 键。
- 非零时 coverage 增加 `deletedDocuments`，仅作披露：**不计入 recordsDropped，不触发
  parseIncomplete，不产生新 finding，不单独改变 severity/verdict**。
- 文档状态异常仍走 038U1 的 `consistency_unresolved` / parseIncomplete。
- 两份旧归档的页面清单、`deletedDocuments`、`unknown_types` 是有意修正；其余 findings、
  电气模型和几何不得变化。report.md 人类行不在本批新增。

## 5. 两个消费者与回退

- 原理图：`build_project_model` / `collect_page_layout`，验收页面清单、非空页删除、同板跨页
  重号消失、空板身份保留，其他页和 042 ATTR 归属不变。
- PCB/库：`parse_epru_text` / `load_epro2_source` / eprj3 PCB reader，验收删除后无 placements
  或库定义；false 后恢复；重复 PCB 与分歧库负例不放松。
- 回退是模型输入退回 raw 视图，CLI 参数、raw 差分、ChangePlan、connector/DSH 工具面不变。
  本批不改审查规则、绘制算法或 Rust；Rust 只保留 raw 既有差分。

## 6. 兼容矩阵与 negative control

| 维度 | 本批覆盖 | 不得声称 |
|---|---|---|
| V3 `.epro2` | 14 份旧归档对拍 + true/false/非空合成页 | 真机协同已验证 |
| V4 `.eprj3` | 同一记录视图与多板守卫 | 真实删除样本已验证 |
| `.eprj2` 内部日志 | 不改 | pend/revoke/envelope 全链已支持 |
| 在线 / 离线 | 仅离线；零真机 | 在线删除同步或宿主网表已验证 |
| 单 / 多板 | 页清单、空板、重复 PCB/分歧库反例 | 跨板网络连接规则已完成 |
| 普通器件 / CBB | 普通 SCH_PAGE/PCB/库合成记录 | CBB/type 17 已支持 |

Negative control 必须包括：空 DELETE_DOC 不删除；非法墓碑不删除；低票 true 不覆盖高票 false；
同票大 client 胜；正常删除不算 recordsDropped/parseIncomplete；空板不被删除或重新猜归属；
重复 PCB/分歧库仍拒绝；未涉及页面的 findings 不变。

## 7. 实施与验收

- 新建独立合成测试，不改 fixtures/reviewsets；038U1 中与「不过滤 DELETE_DOC」相关的旧断言
  只能按本裁定的有意行为变更更新，并保留 raw 不变反例。
- 对 14 份旧归档保存修复前指纹：除两份页面清单/统计有意变化外，其他五类模型和 findings
  指纹必须零 mismatch；发现额外 delta 停止，不改预期凑绿。
- 聚焦：038U/038F1/038I/038P1、040/040b、042、049、072、101、131a、epro2_model、
  epru_parser、owner/doc claims。批次验收按仓库纪律跑完整四线；全量一次一轮，独立 basetemp。
- 至少两处变异：true 过滤、false 恢复/异常不猜删；各必须有测试变红，cp 恢复并核 SHA-256。
- 零 git 写、零真机、零删除；子代理最多 40 步/30 分钟，主代理复核差异和旧归档对拍。

## 8. 实施与独立对拍证据（2026-11-05，尚未提交）

- `Document.deleted` 只在一致性视图中出现；最终删除文档的记录为空并被 resolve/split 消费者过滤，
  raw 仍保留完整文档。`DELETE_DOC` 已登记为已知类型。
- 文档标记复用元素级 ticket/client 判优器；空 body/空对象未删除，异常保留整个文档并计入
  `consistency_unresolved`。多标记不计入“元素 id 重复组”，该统计口径在主代理复核时单独钉回。
- `deleted_documents` 与非零-only `deletedDocuments` 已接入；正常删除不进 recordsDropped、
  parseIncomplete 或 verdictWhy。空 BoardModel 保留板身份与空 page_uuids。
- 聚焦验收：**491 passed**，追加 V4/ poured 邻域 **57 passed**；统计口径复核后 U2+038U
  **88 passed**。新 U2 为 32 项，覆盖闸为 75 项。
- 14 份旧归档特殊对拍：仅两份各移除一个已确认空页，得到 **expected_deltas=2 / mismatches=0**；
  排除 page_uuids 后的 schematic、PCB、库、符号、导出工程指纹均不变，run_review findings
  **0 mismatch**。
- 真实 CLI 分别读取这两份归档：report.json 均为 `deletedDocuments=1`、`consistencyUnresolved=0`、
  `DELETE_DOC` 不再出现在 unknown_types；页面数分别为 `[1,1,1]` 与 `[1,1]`。
  预期修正后 025d/U2/038U/040b/072/doc/owner 聚焦集为 **251 passed**。
- 变异：移除 consistent 文档过滤 6 红、false 不复活 5 红、非布尔被猜删 5 红，均 cp+SHA-256
  恢复。另一次仅删 resolve_records 的显式 deleted 防线无红，证明它是冗余防线而非唯一判定点；
  保留该防线，未拿无效变异充数。
- 未覆盖仍是：多 DOCHEAD 合流、pend/revoke、真实协同日志、Rust 一致性视图、CBB 真实样本。
  最终全量与其他三线读数在验收完成后追加，不提前写全绿。

## 9. 最终验收读数

- 第一轮全量：**9493 passed / 25 skipped / 4 failed**。除两项已知环境红外，
  `test_025d_checkup_report.py` 仍钉住旧的 4 页（批准删除后应为 3 页），另有一项绘制线在途
  digest 红。只修正 025d 的页面数预期并注明空页删除事实，没有改其他业务预期。
- 第二次也是最后一次全量：**9496 passed / 25 skipped / 2 failed / 1 warning，1227.58 s**。
  025d、绘制线和全部 038U/U2 测试通过；仅剩：
  - `test_193_process_guards.py::test_whole_suite_run_queues_behind_two_slots`：
    `C:\Users\xiangyu\.boardwise\pytest-slots` 的 `Errno 13 Permission denied`；
  - `test_193_secrecy_hooks.py::test_the_posix_installer_sets_hooks_path_and_the_exec_bit`：
    Git/MSYS `NtCreateDirectoryObject(...): 0xC0000022`。
  没有第三轮全量。可以声明 038U2 业务回归通过，**不能宣称全量全绿或发布闸通过**。
- connector：**576 passed**，typecheck 通过；DSH：**129 passed / 1 skipped**，
  typecheck/build 通过；Rust：**111 passed / 4 ignored**，fmt/clippy/test 通过。
  三条线的构建产物在 git status 中均为干净。
- 全部改动仍未提交、未推送；真实工程和 fixtures/reviewsets 未写，未做真机操作。
  `TASKMAP.md`、`SCHEDULE.md` 和 `docs/handoff.md` 仍有绘制线未提交内容，本批未覆盖它们；
  当前权威入口为 `tasks/review-line.md` 与本任务书。
