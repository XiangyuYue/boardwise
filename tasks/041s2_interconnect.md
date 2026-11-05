# 041 S2：显式跨板互联声明

日期：2026-11-05。上游合同：`tasks/041-cross-board-net-DRAFT.md` §4.1、§5、§7。
本批按 `tasks/shared-platform.md` 的集成锁单独实施，只做声明读取、校验和披露；不做 S3/S4，不改 finding/severity/verdict，不把网表合并。

## 1. 公开文件合同

只接受命令行显式给出的 `--interconnect <path>`；不自动发现、不读默认路径。JSON 形状：

```json
{
  "interconnectVersion": 1,
  "projectUuid": "可选；给出时必须与当前工程的真实 uuid 逐字一致",
  "edges": [
    {
      "from": {"boardUuid": "board-a", "net": "5V_IN"},
      "to": {"boardUuid": "board-b", "net": "VSYS"},
      "declaredBy": "engineer",
      "note": "CN2 pin1-pin4 线束"
    }
  ]
}
```

严格门槛：

- 根对象只许 `interconnectVersion/projectUuid/edges`；`interconnectVersion` 与 `edges` 必填，`projectUuid` 可选。版本只认整数 1，布尔值不算整数。
- `projectUuid` 可省略；一旦给出必须是非空字符串并逐字匹配当前工程身份。当前容器没有真实 projectUuid（例如 `.epro2`）时拒绝，不能拿文件名摘要、title 或位置冒充。`.eprj3` 沿用 `_snapshot_identity()` 读取的索引身份。
- `edges` 必须是数组，允许显式空数组；成功读取空数组时可披露 0 条，坏文件绝不能降级成这个状态。
- 每条边只许 `from/to/declaredBy/note`；前三项必填，`declaredBy` 只认精确字符串 `engineer`，`note` 可省略、缺省为空字符串但给出时必须是字符串。
- 端点只许 `boardUuid/net`，均为非空字符串，不 trim、不折叠大小写。uuid 必须命中真实可寻址 BOARD，net 必须逐字存在于该板；title、implicit、unattached、页 uuid 均不可替代。
- 两端必须属于不同板；相同实例自环和同板两网都拒绝，本合同不表达板内短接。
- 重复边按无序端点对判定，交换 from/to 也算重复；declaredBy/note 不同不能绕过重复拒绝。
- 根、边或端点的未知键、错误类型、缺键均拒绝。JSON 对象自身重复键也拒绝，避免后值悄悄覆盖前值。
- 不同网名完全合法；声明不会反向证明其他同名网相连，也不构成“未声明即断开”。

## 2. 数据与读取 API

新增 shared 模块 `core/interconnect.py`，并在 `contracts/module-owners.json` 登记为 shared：

- `ProvenNetEdge(first, second, declared_by="engineer", note="")`：冻结数据类，两端为 `NetInstance`，构造时再次拒绝同板端点和非法声明人。
- `InterconnectContract(project_uuid, edges)`：冻结数据类，保存已验证的声明；`edges` 为 tuple。
- `parse_interconnect(payload, model, *, project_uuid="", source="<memory>")`：纯校验，不读文件。
- `load_interconnect(path, model, *, project_uuid="")`：读取 UTF-8 JSON 后调用纯校验。
- `InterconnectError(ValueError)`：路径、JSON、版本、结构和模型语义错误统一带可读原因；CLI 捕获后退 2，不打 traceback。

声明是报告输入，不写进 `ProjectModel`，不改 `net_instances()`、`cross_board_net_instances()`、`unproven_edges` 或旧 `unproven_nets`。E0 同名组仍表示“仅凭名字未证明”，即使另有一条声明也不被偷偷升级或删除；声明单独成为 proven 披露，且不执行并查集或网表焊接。

## 3. CLI 与报告合同

- `review <file> --interconnect PATH` 与 `checkup --file FILE --interconnect PATH` 支持本批。
- `review --live`、`review --view pcb`、`review finalize`、在线 `checkup` 给此参数均明确退 2；本批不定义在线或 PCB 视图声明。`review finalize` 不得静默忽略它。
- 普通 `DesignModel`、单板或 implicit 工程给此参数也退 2；无可寻址跨板端点可声明。无参数的旧路径完全不变。
- 给了参数但文件不存在、是目录、不可读、非 UTF-8、坏 JSON、版本或语义校验失败：拒绝运行、退 2、说明原因，不写 `report.json/report.md` 或 review 输出，也不出现“0 条已声明连接”。
- `cross_board_net_section(model, interconnect=None)` 保持旧调用兼容。仅当声明成功读取且属于多板报告时新增：
  - `provenCount`；
  - `proven[]`，每行含 `from/to`（各含 `boardUuid/boardTitle/netName`）、`declaredBy/note/evidenceLevel="engineer-declared"/merged=false`。
- 报告文案写“M 条已声明跨板连接（显式工程师声明；仅披露，不合并网表）”，逐条列两端和 note。带声明时标题用“跨板网络（含已声明连接）”；无声明的旧标题、键集合和文本保持不变。
- checkup 的 `source.crossBoardNets` 与 `review --md` 共用同一函数/渲染器。`review --json` 仍是原 findings 数组；声明必须校验，但不向该 JSON 增加字段。
- `contracts/cli/v1.json` 用 `tools.cli_contract --write` 重建，钉住两个新参数。DSH 不新增工具参数或 JSON 字段，本批不改 DSH/connector，不发版。

## 4. 两个实际消费者与回退

1. checkup 离线报告：模型与真实 projectUuid 校验后，在 source/Markdown 披露同一份声明。
2. review 离线 Markdown：复用同一 section；findings、退出码和 console verdict 不变。

回退为撤掉显式参数、互联模块与可选 `proven*` 键；无文件迁移，无自动默认文件，无既有模型或网表状态需要回滚。

## 5. negative control 与验收

新增 `tests/test_041s2_interconnect.py`，必要时只调整 S1 中“尚无 `--interconnect`”的反断言：

1. `5V_IN@A ↔ VSYS@B` 成功；同名但未声明的 GND 仍无 proven 边、无网表合并。
2. 无参数正常运行且无 `proven*`；旁边存在任何约定文件名也不会被自动读取。
3. 缺文件、目录路径、坏 JSON、非 UTF-8、缺版本、版本 2/布尔版本、未知根/边/端点键、JSON 重复键均拒绝。
4. 空 uuid、title 替代、unattached、未知板、该板不存在的 net、空 net、自环、同板边、正反向重复边均拒绝。
5. projectUuid 匹配成功；不匹配、空值、当前容器无真实身份时给出该键均拒绝。
6. 非 engineer、缺 declaredBy、非字符串 note 拒绝；显式空 edges 成功并如实披露 0。
7. live/PCB/finalize/在线 checkup/单板与 implicit 给参数拒绝；旧路径无参数逐字节不变。
8. checkup/review 声明披露一致；finding 数、severity、completion.verdict 和退出码保持各自既有基线。
9. `test_038p1_eprj3_multi_guards.py` 的重复 PCB 与分歧库拒绝保持不变；owner/layer 守卫通过。
10. 至少两次源码变异必须让测试转红，再用 cp+SHA-256 恢复；不得用 git checkout/restore。

## 6. 兼容矩阵

| 维度 | S2 覆盖 | 必须不变 / 未覆盖 |
|---|---|---|
| V3/V4 宿主 | 不跑真机；仅离线文件 | 不声称宿主网表、ERC/DRC 已验证 |
| `.epro2` | 真实 3 板夹具跑显式声明；内存 2 板覆盖解析；S1 的真实 2 板夹具仅复验无参旧路径 | 真实 2 板的声明路径未单独跑；给出 projectUuid 必须拒绝；不新增电气结论 |
| `.eprj2` | 未覆盖 | 不声称多板互联兼容 |
| `.eprj3` | 内存/合成模型与既有身份、重复 PCB、分歧库守卫 | 真实多板线束未覆盖 |
| 在线/离线 | 仅离线 | live/在线 checkup 明确拒绝，不扩张 |
| 单/多板 | 单板无参数不变；多板严格声明与披露 | 同名不自动相连，未声明不等于断开 |
| 普通器件/CBB | 仅板级网实例 | CBB 内部网与器件配对未覆盖 |
| S3/S4 | 不启动 | 无宿主交叉验证、语义函数层或正式规则 |

## 7. 文件域与纪律

- 新 `src/boardwise/core/interconnect.py`、`tests/test_041s2_interconnect.py`、本任务书。
- `src/boardwise/engines/checkup.py`、`src/boardwise/cli.py`、`src/boardwise/commands/review.py` 的必要接线。
- `contracts/module-owners.json`、生成的 `contracts/cli/v1.json`；S1 中已被 S2 取代的注释/反断言。
- 完成后更新上游 DRAFT、`tasks/TASKMAP.md`、`tasks/review-line.md` 的实际状态。

禁止改 fixtures、`package.json`、038V 文件、绘制线、connector/DSH/Rust 业务实现。零 git 写、零删除、零真机。开发期先跑 041/040b/038p1/checkup/review/CLI contract/owner/doc 聚焦集；最终按串行纪律跑全量及四线。

## 8. 实施与聚焦验收记录

- 纯解析首批 112 项测试通过；报告批累计 173 项通过；CLI 与对抗复核收尾后的九文件聚焦集为 **322 passed**。这些集合有重叠，不相加成全量。
- 真实三板 `.epro2` 上，不同网名与同名 GND 两类声明均进入 checkup/review 的同一段披露；checkup 保持 241 findings、50E/21W/170I 和 `completion.verdict="incomplete"`，review 保持 45、30E/1W/14I，退出码均仍为 1。`review --json` 仍只有 findings/summary。
- 显式空 `edges` 披露 `provenCount=0`；缺文件、坏 JSON、无真实身份却给 projectUuid 均退 2 且不写报告。live、PCB view、finalize、在线 checkup、单板均拒绝；在线拒绝发生在锁与在线加载器之前。
- 只读对抗复核发现显式 `--interconnect ""` 曾被当成未给参数。两个 parser 的默认值改为 None、六处闸门改为 `is not None` 后，空字符串在离线/在线/finalize 均拒绝，并新增 10 项回归。另修复空白 BOARD uuid 漏出裸 ValueError、重复 BOARD uuid 首板命中和报告渲染器 return 后重复死代码。
- 两次解析器变异均被测试抓住：布尔版本被误接受（1 failed / 111 passed）、正反重复边未拒绝（2 failed / 110 passed）；随后用 cp 备份恢复并核对 SHA-256。日志在 `.tmp_041s2_core/mutation1.log`、`mutation2.log`。
- `contracts/cli/v1.json` 由生成器重建并用 `tools.cli_contract` 独立核对；最终两个新参数的 default 都是 None。模块 owner 总数由 144 同步为 145，import/layer 守卫通过。
- DSH 既有 `boardwise_checkup` 只暴露 file/project/instance/out，连 CLI 已有的 intent 也未暴露；本批不新增 DSH 工具面，不改变其旧 JSON/参数。connector 与 Rust 无业务代码变化。
- **锁载体边界**：离线声明必须在模型读取后才能完整校验，因此 545 的 `--out/.checkup.lock` 可能先于退 2 落盘；保证的是不写 report.json/report.md，不保证离线拒绝连锁载体也不存在。在线 `--interconnect` 拒绝仍保证不创建 out/锁。本批不为声明重排既有输出锁架构。
- 第一轮全量 Python 为 **9680 passed / 25 skipped / 3 failed / 1 warning，1075.50 s**。两个失败仍是既有 pytest 槽位 ACL 与 MSYS `0xC0000022` 环境问题；新增回归是 finalize 拒绝块把 `_cmd_review_finalize(` 挤出 DSH 同步钉的 400 字 dispatch 窗口。拒绝逻辑已移到 finalize handler 入口，dispatch 恢复原形，直接调用 handler 也拒绝；相关 **177 passed**。按纪律只再复跑一轮全量。
- 第二轮全量 Python 为 **9681 passed / 25 skipped / 2 failed / 1 warning，1064.46 s**。仅剩既有的 `test_193_process_guards.py::test_whole_suite_run_queues_behind_two_slots`（`~/.boardwise/pytest-slots` 权限）与 `test_193_secrecy_hooks.py::test_the_posix_installer_sets_hooks_path_and_the_exec_bit`（Git/MSYS `0xC0000022`）；不宣称全量全绿。
- finalize 修复后的最终聚焦集为 **327 passed**；文档声明与仓库卫生测试 **43 passed**，`tools/check_repo_hygiene.py` 和 `git diff --check` 通过。
- connector **576 passed**、typecheck 通过；DSH **129 passed / 1 skipped**、typecheck/build 通过；Rust **111 passed / 4 ignored**，fmt/clippy/test 通过。
- 未提交、未推送、未发布、未跑真机。仍未覆盖 V3/V4 宿主、eprj2 多板、真实多板 eprj3 与 projectUuid 实测、真实 2 板声明路径、CBB 和板间线束；S3/S4 不自动接续。
