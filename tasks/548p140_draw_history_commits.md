# 548P140 — 绘制线历史未提交批次整理与分批提交

> 状态：盘点完成，待逐批授权/执行。用户明确要求：不只P137/P138，所有此前未提交绘制线批次都整理提交，文档同步。
> 本任务只覆盖绘制线；550、review/shared其他线、真实工程、临时/撤回实验不纳入。

## 1. 盘点依据

- HEAD：`3d4a0d5e666a36809babbfad7871021d84cea24a`；最近绘制源码提交为 `ba3fd2d`。
- 只读盘点：`.tmp_548p140/source-inventory.md`、`docs-test-inventory.md`、`hunks.json`。
- 恢复点证明：drawcompiler HEAD 1228651B → P124 `2348a140`/1483601B → P126 `2bb3fcea`
  → P135 `6614fc04` → P137 `324a4db6` → P138 `24f13da5`/1498117B。
- placement 在P126前为 `af5413f9`，P126后为当前 `f550f6ea`；svgpreview整份delta属P44。
- `core.presentationspec` 按 `tasks/shared-platform.md` §1 属draw模块，不因目录名成为shared；
  548D3D-H集成锁记录在同文件§19。
- 证据目录与`.tmp_*`默认本地；不用`git add -f`纳入大日志、真实工程或探针副本。

## 2. 为什么不能按批号机械拆成几十次提交

D3D-H到J、J到K/L、P55到P112等区间缺完整兼容快照；同一函数还交织多批hunk。
这些区间只在有可靠恢复点的边界提交，不用mtime或注释猜旧状态。P133/P134撤回实现禁止恢复，
P135才是同网行距的正式落地。无净生产改动的P127–P134/P136只进入任务/文档同步。

## 3. 批准的提交序列（6批）

| 批 | 范围与源码边界 | 测试/任务与验收 |
|---|---|---|
| C1 `feat(draw): integrate service layouts and native carriers through P124` | drawcompiler取 `.tmp_548p124/drawcompiler.p43-good.py`；placement取 `.tmp_548p126/placement.before.py`；presentationspec/pagecompiler/drawapply/voltage_divider/svgpreview取当前已验收状态。包含此前所有绘制线源码与P124及以前回归，不含P126+测试 | P124及以前测试、5个本地证据测试中前4个加缺失skip守卫；历史任务书。沿用P124/P118等真实读数并跑该快照聚焦 |
| C2 `feat(draw): retire refused service host feet (548P126)` | drawcompiler取 `.tmp_548p126/drawcompiler.candidate.py`；placement取当前 `f550f6ea` | P126测试与任务书；P140守卫静态测试（此时5个证据测试均已入库）。真实5/5与两项变异证据 |
| C3 `feat(draw): reselect reserved labels with same-net gaps (548P135)` | drawcompiler取 `.tmp_548p135/drawcompiler.reviewed.py` | P135测试与任务书；35 focused历史锚、两项变异、P43/WiFi geometry |
| C4 `feat(draw): preserve the first complete service answer (548P137)` | drawcompiler取 `.tmp_548p137/drawcompiler.after.py` | P137测试与任务书；17 focused、两项变异、真实 `_place` 5/5 |
| C5 `feat(draw): re-enumerate the largest joint seat once (548P138)` | drawcompiler取当前 `.tmp_548p138/drawcompiler.after.py` | P138测试与任务书；77 focused、两项变异、第二次joint chain5；整图仍C3.2未过 |
| C6 `docs(draw): synchronize the drawing history and current handoff` | 仅绘制线文档hunks：TASKMAP/PROGRESS/roadmap/SCHEDULE/handoff/draw-line/draw-assets/ladder/shared-platform/AGENTS与两份同步skill、test_doc_claims，以及其余任务书P127–P134/P136/P139/P140 | 文档/工作区测试、链接/同步副本/资产钉；其他线hunks留工作树 |

同一文件的旧状态通过**恢复点生成index补丁** staging，不用`git checkout/restore`改写当前工作树。
后续批的补丁从上一恢复点到下一恢复点生成；最终drawcompiler必须仍等于当前SHA。

## 4. 明确排除

- 550/PCB/review：`core/netpath.py`、`pcb_netpath.py`、`assembly.py`、`cli.py`的550行、
  `pcbreview.py`、550测试/任务书、contracts、owner/review文档及测试。
- 审查归因：`test_038m/n/t`、`test_151`、`test_153`、`tasks/local-acceptance-20261116.md`。
- 临时/废弃：`cases/`、根`tmp*`、`pytest-of-xiangyu/`、`blocklib/parts.json.tmp`、`docs/debug.log`、
  `checkup/.checkup.lock`、`.tmp_*`、P133/P134未验收副本、真实工程和fixtures。
- `evidence/`与`outputs/`默认本地；文档可引用其路径，但测试在证据缺失时必须明确skip而非fail。

## 5. 文档同步要求

- TASKMAP补P2–P124的历史索引口径，不伪造26份任务书；现有P125–P139逐项状态保留。
- PROGRESS补P115–P138的可验证里程碑与本地证据链接，不回写虚构的全绿。
- roadmap/SCHEDULE从548J停止点更新到P138机制通过、整图仍C3.2；提交计划指向本文件。
- `test_doc_claims.py`/新钉覆盖资产链接、同步副本、当前派单一致、证据缺失skip；
  不为省时间删除既有声明钉。

## 6. 执行闸

1. 5个本地证据测试先加守卫，当前机器实际运行不得skip；静态守卫测试先红后绿。
2. 主代理复核placement、drawcompiler关键恢复点diff、drawapply/test_543i；每批先看cached diff再commit。
3. 每批运行其聚焦测试或引用同SHA历史验收并补必要复跑；C1/C2若快照不兼容就停止，不强行提交。
4. 最终核对工作树只剩他人/本地资产、drawcompiler与P138恢复点一致；文档测试及资产检查全过。
5. 每次Git写只执行用户明确批准的对应批次；不push、不改其他线、不移动/删除文件。
