# 审查线派单入口（540B8）

> 这是 review 线的任务路由，不复制规则规格。操作 SOP 以 `.agents/skills/boardwise/SKILL.md`
> 为准；现状与证据以 `tasks/540b_review_draw_decoupling.md` 和
> `evidence/540/b-behavior-equivalence.md` 为准。

## 1. 业务边界

| 可以派给 review 线 | 不应夹带 |
|---|---|
| `rules/**`（shared 的 `rules.base`/`rules.values` 除外） | 布局、布线、旗标、文字几何或绘制算法 |
| checkup、PCB review、证据/覆盖、review-read、triage/finalize、ReviewReport | `engines/draw*`、`core/layoutplan.py` 等 draw 内部 |
| parts/BOM/datasheet/catalog/harvest 等资料与器件链 | shared parser/model/bridge 的“顺手优化” |
| `commands/review.py` 的审查命令注册/分派 | 其他 19 个顶层命令的注册或 DSH draw 工具 |

依赖方向只能是 **review → shared / review**。不得新增 review→draw；shared 不能反向
import review。Finding、severity、mode 与报告措辞仍归 review；B1–B3 下沉的命名、
引脚连通、去耦库存和 CapDecision 是 shared 合同，不能在规则里复制第二份。

## 2. 公开入口

- CLI：`review`、`checkup`、`need-datasheet`、`triage`、`triage-batch`、
  `review-evidence`、`review-read`、`review-eval`、`review-mark`、`parts`、`bom`。
- DSH：现有 review 工具名保持；`review finalize` 的 Session receipt 与 delivery gate 不变。
- 共享输入：公开导出 / DesignModel / CircuitSpec / DesignIntent / 部件货架；输出是报告与
  审查证据，不是 LayoutPlan 的内部对象。

## 3. 派单规则

1. 一张派单只写一个缺口和一个文件域，先列允许文件与相邻测试；不夹带 shared 或 draw 改动。
2. 确需改 shared parser/model/bridge/core/CLI 时，停止按普通 review 批处理，改走
   `tasks/shared-platform.md` 的集成锁；审查规则变化与迁移不得同批。
3. 规则语义、严重度或 verdict 变化必须先有行为证据和反例；纯解耦批不得借测试红灯改判。
4. 全量 pytest 一次只跑一轮，`-n 4 --dist loadfile` 且每批独立 basetemp；真机操作串行，
   只碰任务书逐字点名的 `test`/`test2`，真实工程不写。
5. 任何 git 写、push、发布、删除或 worktree add/remove/prune 都要另获岳的明确批准。

## 4. 验收与交接

- 小批先跑 `tests/test_540_cli_review.py`、对应规则/报告邻域和 `tests/test_owner_rules.py`；
  shared 边界改动另跑 `tests/test_540_shared_{naming,connectivity,decap}.py`。
- 最终串行验收包含全量 Python、connector、DSH 和（540C 后）Rust；邻域读数不能写成全量。
- 交接写清：行为基线、实际命令与读数、变异及 SHA-256 恢复、未覆盖项、后续依赖。
- #87/#88 验收矩阵与四视图锚见 `tasks/issue-87-88-acceptance.md`；#87④已由 `d2130b7` 落地
  并于 2026-11-06 复核（289 Python + 2 Rust，限 `pcb-voltage-spacing`），②仍开放、
  ⑤仅离线替代，**整单不关**；#88 的 1/295、四视图及 55=14+35+6 已获提出人确认并关单，
  `element_ids` 唯一性另立。
- 当前路线债：0.6.0 的 200A/B/C 仍按 `tasks/528_060_gate.md` 验收；540B 不替它们报完成。
- Rust 顺序：shared 纯函数/几何与 parser/model 之后才是 review；不在本线提前批量翻译。

**当前 worktree 状态**：审查线工作区 `E:\boardwise\.tmp_review_line`，分支 `review-v4`，
owner=审查线；绘制线独立开发、互不改文件，主仓及绘制线的未提交改动不碰。shared 集成、
全量测试与真机仍由 `tasks/shared-platform.md` 串行。旧 worktree 审计结论：没有可安全回收
项，证据区不按名字清理。`git worktree add/remove/prune` 仍逐次经岳明确批准。

## 5. 当前任务入口（2026-11-05）

- **038U1/U2 记录一致性**：已完成并提交 `d0275ae`，合同与验收记录见
  `tasks/038u_record_consistency.md` 和 `tasks/038u2_document_tombstones.md`。
- **038V 焊盘形状间距修正（实现与验收完成，已随 `683a526` 提交）**：任务书为
  `tasks/038v_pad_shape_clearance.md`。圆盘/长圆改为精确胶囊，非圆椭圆采用有界外接 32 边形；
  `pad_corners()` 的外接框公开合同不变。全量 9509 passed / 25 skipped / 2 个既有 Windows 环境失败；
  connector、DSH、Rust 均通过，未跑原始 PCB-A 或真机。
- **041 S1 跨板网络实例（实现与验收完成）**：合同与证据见
  `tasks/041s1_net_instances.md`。真实 uuid 的 NetInstance/unproven_edges、checkup/review 披露和
  triage 保守归属已落地；多板 DRC 叶子无板身份，统一不归属。全量 9542 passed / 25 skipped /
  2 个既有 Windows 环境失败，connector、DSH、Rust 均通过；S1 本身不含声明读取器或 proven 边。
- **041 S2 显式声明读取（实现与离线验收完成）**：合同与证据见
  `tasks/041s2_interconnect.md`。`review <file>` / `checkup --file` 新增显式 `--interconnect`，
  严格校验后只在报告中披露 proven 边，不合并网表、不改 findings/severity/verdict；空路径、坏文件、
  错误板身份、live/PCB/finalize/在线均拒绝。真实 3 板与 2 板 `.epro2` 均完成双报告对拍；
  最终全量 **9682 passed / 25 skipped / 2 个既有 Windows 环境失败**；connector、DSH、Rust 均通过。
  S3 宿主交叉验证继续暂缓，S4 必须先有真实板间证据。
- **038W PAD_NET 每脚网络判优（已随 `cdff88b` 提交）**：合同见 `tasks/038w_pad_net_journal.md`。
  每脚投影复用 038U 原子视图的同一 ticket/client 判优，改板前的旧网不再靠 `setdefault` 获胜；
  不改规则、CLI 参数与报告 schema。
- **038X 默认货架绝对路径与缺失披露（已随 `cdff88b` 提交）**：合同见
  `tasks/038x_shelf_resolution.md`。非 frozen 的默认读写统一改用 `resources.parts_library()`
  绝对路径，只读入口显式披露货架缺失，`load_parts` 的「缺文件可建空架」底层合同不变。
- **529 去耦 mid 容值带（已随 `cdff88b` 提交）**：合同见 `tasks/529_decap_mid_band.md`。
  2.2/4.7µF 落入 mid 档，191D 的临时收窄按原判据回退，全 bulk 输入档保留 INFO 特例；
  四个距离阈值 `200/300/800/200` 不动。
- **527C2 跨视图几何分类与全部位号（已随 `cdff88b` 提交）**：合同见
  `tasks/527c2_cross_view_geometry.md`。lonely-pin 的 note 按几何分「没画线 / 网名不同 /
  落位嫌疑」并点名全部位号；`min_pins` 仍为 3，哪一侧电气结论更有权威不变。
- **541 可离线运行时闸（R1/R2/R4 strict 已随 `cdff88b` 提交）**：合同见
  `tasks/541_offline_runtime_gates.md`。R1 `core/runmanifest.py` 版本化 manifest 与语义 diff；
  R2 `checkup --file --strict` / `--new-evidence`；R4 `review finalize --strict-partial`
  四档披露校验。R3 的 DSH profile pre-execute 闸等重启授权，**未实施**；公开接口 allowlist
  也**未实施**，不得写成 R3/R4 全部完成。
- 以上批次的最终全量 **9893 passed / 25 skipped / 14 failed / 1 warning**。
  其中 12 条是工作树既有货架数据漂移，2 条是既有 Windows 环境失败，不宣称全量全绿；
  connector、DSH、Rust 均通过。
- 新版宿主能力探针仍等明确的 4.1.94+ 测试环境和授权非空 PCB。
