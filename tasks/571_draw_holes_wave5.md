# 任务书：571 — 绘制线挖洞第五批（八缝，只读，已缩窄）

- 批号 **571**　日期 2026-11-24
- 承接 565（24）、566/567（14）、568/569（32）、570（26）。本批换三个新角度：**文法三本**、**引擎内部成本/预算**、**闸门入口矩阵（横向）**。
- **只挖不修。修复由他人负责**：每条洞必须能直接开工（文件:行 + 复现命令 + 应有读数 + `FIX:` 一行 + 先红断言）。
- **树在动**：修复线已开工（`cli.py`、`drawapply.py`、`connector/`、`docs/` 有未提交改动）。开工先记 `git rev-parse HEAD` 与**你被审文件的 sha256**，收工再复算一次；若中途变了，在报告里标出并说明结论对应的版本。

## ① 前因

前三批把「delta 面 / 口径面 / 接口面 / 引擎四块大地盘」挖了 96 条。剩下三类高风险面没碰：
1. **文法三本**（`ldo` 28 KB、`voltage_divider` 38 KB、`rc_lowpass` 20 KB、`base` 45 KB）——143 的 04-H1…H7 家族在 flyback/power_entry 上已被 570-C2 翻案一半（4 条已修、2 条新洞），这三本还没人看过；
2. **引擎内部的成本与预算**——`placement._anneal/_energy` 的软成本、`pagecompiler` 的 `PageCompileBudget` 字段，最可能出现「硬闸全过但结果不可读」；
3. **闸门入口矩阵（横向）**——565/567/570 三条独立证据都指向「同一道闸只在某个入口生效」：标题栏 keep-out 在 page 路径不存在（565-S3-1 / 567-F-1 / 570-B2-1 三个入口三种表现）、空页复用绕过非空闸（566-A）、L11/L12 缺输入仍印 clean（565-S2 / S6-H3）。**没有一份矩阵**告诉修复线「还有哪些入口能绕过」。

## ② 当前树状态（开工复核）

| 项 | 读数 |
|---|---|
| HEAD | `f5083286de06b1d1b698a91e51da18463be4f4de`（未推送） |
| 工作树 | 混合且**正在被修复线改动**：`M cli.py / drawapply.py / agentadjusted.py / connector/src/actions.ts / contracts/cli/v1.json / docs/{draw,bridge,pits,handoff,roadmap}.md / PROGRESS.md` 等；563 面仍在（`M core/circuitsemantics.py`、`?? tests/test_563_*.py`）。`placement.py`、`pagecompiler.py`、`readability.py`、`grammar/*` 相对 HEAD 干净 |
| 已挖（勿重复） | `outputs/hole565|566|568|570/TRIAGE.md` |
| 解释器 / CLI | `.venv\Scripts\python.exe` / `.venv\Scripts\boardwise.exe` |

## ③ 八缝（窄范围，逐条只问 1–3 件事）

| 缝 | 地盘 | 只查这些 | 探针 | 报告 |
|---|---|---|---|---|
| **571-A** | `grammar/{ldo,voltage_divider,rc_lowpass,base}.py` | ① 每本对**空/单件/畸形**电路的 6 个输入：是「合法通过」还是「拒因点名真实原因」；② 04 家族残留：伪造地网名（`rc-lowpass` 双地族）、`uniform-gnd` 只核一半、`base` 的 `edges` 守卫缺失；③ 每本给出的约束（`RelativeConstraint` kind）是否都在 `base` 词表内且被 placement 消费 | `.tmp_hole571/a/` | `outputs/hole571/a/` |
| **571-B** | `engines/pagecompiler.py`（262 KB） | ① `PageCompileBudget` **每个字段**是否被消费（`page_box`/`keepouts`/`relocate_around_keepouts`/`grid`/变体数…）；② 多 keep-out 时搬家是否一致（一个模块避开 A 却压 B）；③ 多候选（>2）时排序与去重是否稳定 | `.tmp_hole571/b/` | `outputs/hole571/b/` |
| **571-C** | `placement.{_energy,_anneal,_anneal_with_seed}` + 各 `_solve*` 的 fallback | ① 软成本项有没有可能压过硬违规（硬闸在 `_energy` 里是常数还是可被软项抵消）；② 失败回退梯度：试几档放弃、放弃时返回什么（带违规的图还是拒绝）；③ 温度/种子参数是否影响**确定性**（同 seed 同结果） | `.tmp_hole571/c/` | `outputs/hole571/c/` |
| **571-D** | pinmap / 引脚身份全链（`core/pinrole.py`、circuit→pinmap 派生、`engines/patchpin` 的 pin 解析） | ① 同名脚（多单元同号）/`U1.1` vs `U1.01`/脚名含点；② 多单元与跨页；③ 单位是否与 `v4facts` 一致（570-G2 已钉 page unit）；用 `blocklib/modules/circuits/` 一件真实电路验证 | `.tmp_hole571/d/` | `outputs/hole571/d/` |
| **571-E** | 证据回放：`evidence/547S*` 与 `evidence/548{A..N}*` 各 1 组 | 记录里的输入在 HEAD 上重放是否仍得到记录指纹/拒因；不同则 `git log -S/blame` 定位批次。`evidence/` 只读 | `.tmp_hole571/e/` | `outputs/hole571/e/` |
| **571-F** | `engines/readability.py::check()` 端到端 | 跑 1–2 个整页输入（既有夹具/证据），逐条列出「谓词全过但图上明显错」的候选（不许只凭观感，要给坐标/盒数值） | `.tmp_hole571/f/` | `outputs/hole571/f/` |
| **571-G** | 横向：闸门入口矩阵 | 对三条主根因各出一张矩阵：① 标题栏 keep-out（`draw compile` CLI / 引擎 API / `draw plan` page 路径 / `draw plan --layout` / `draw apply`）；② 空页复用（`draw apply` 页路径 / 项目路径 / `--new-page`）；③ L11/L12 披露（`draw lint` 有/无 `--netlist`、有/无 `--bodies`、DSH 工具）。每格写「能到闸 / 绕过 / 未实现」+ 证据位置 | `.tmp_hole571/g/` | `outputs/hole571/g/` |
| **571-H** | `edit` 写语义（`engines/{addcomponent,patchpin,moveblock,subcircuit}` 与 `drawapply` 的写入/删除段） | ① `draw discard` 连做两次（第二次必须 `nothing_to_discard` 且零写）；② 属性移动（`attributeMoves`）是否出现在 census 之外（570 的 D 系列已钉 census 盲，这里查它是否**零记账**）；③ `--keep-names` 是否把未校验 spec id 当位号 | `.tmp_hole571/h/` | `outputs/hole571/h/` |

## ④ 交付物与验收

1. `outputs/hole571/<seam>/REPRO.md`：六栏（编号/级别/一句话/文件:行/因果/复现命令→实测 vs 应有）+ **`FIX:` 一行**（文件:行 + 一句话修法 + 先红断言）。
2. `probes/` + `holes.json`（`schema: "boardwise.hole571/1"`，`status ∈ {reproduced,falsified,suspect}`）。
3. 每条 `reproduced` 有真实运行读数原文；每条至少一次证伪尝试；`suspect` 要写清缺什么证据。
4. 严重度：`会造假结果` > `会崩` > `会漏` > `仅不一致`。**571-G 的矩阵单独成表**，不进洞表（矩阵里有「绕过」格才升为洞）。

## ⑤ 纪律（与 570 相同，逐条写死）

- 只读：不改 `src/ tests/ docs/ contracts/ connector/ dsh-plugin/ evidence/ blocklib/`；不新增测试；探针写 `.tmp_hole571/<seam>/`，报告写 `outputs/hole571/<seam>/`。
- 零 git 写（不 add/commit/checkout/restore/stash/push）；查历史只 `git show/diff/log/blame`。**不删任何文件**。
- **不碰真机**：零 `boardwise bridge`、零 daemon 拉起、零编辑器、零真实工程写入；要连桥就停手记「不可离线」。
- 测试：只跑点名文件，`--basetemp=.tmp_pt_hole571_<seam>`；禁全量、禁 `-n auto`/`-n >4`；探针单进程；前台命令带 timeout。沙箱 `WinError 5` 时记录并改直调。
- 保密：公司/客户名与真实工程名零出现。

## ⑥ 预算与交卷

- 每缝 **≤25 步或 ≤20 分钟**，先到先停。
- 正文 ≤1200 字：`环境读数（含 HEAD + sha256）` → `洞表（含 FIX 一行）` → `证伪` → `没查的面`。
- 零洞也交，写清为什么零。
