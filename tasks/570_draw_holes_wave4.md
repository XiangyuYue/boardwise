# 任务书：570 — 绘制线挖洞第四批（存量引擎深处，只读）

- 批号 **570**　日期 2026-11-24
- 承接 `565`（24 洞）、`566/567`（14 洞）、`568/569`（32 洞）。前三批主要挖「delta 面」「口径面」「接口面」，**本批挖引擎内部到今未审的四块大地盘**与两条横向检验。
- **性质：只读挖洞。用户已明确「只负责挖洞，有人负责修」——不修、不做测试、不落画布、不碰真机。**

## ① 前因后果

- 三批之后，洞的分布已从「闸门说谎」扩到「写入面不设防」。但仍有四个文件**从未被任何一批看过**（体量按 KB）：`placement.py` 391、`islandlayout.py` 277、`pagecompiler.py` 262、`readability.py` 200；文法族里 `flyback.py` 122 / `power_entry.py` 61 / `ldo.py` 28 / `voltage_divider.py` 38 / `rc_lowpass.py` 20 也只被间接碰过。
- 同时 567-H 盘出 **20 条承重但零测试**的函数（edit 链与 drawapply 的分区/放置问题），它们没有测试网，最可能有真洞。
- 两条横向检验：① `docs/pits.md` 53 条真机坑是否还与 HEAD 一致（过时 pit 会让工程师按错的原因修）；② `evidence/` 里 547/548 系列记录的输入在 HEAD 上重放是否仍得到记录里的指纹/拒因（reference-replay 是否还成立）。
- 修复工作已有他人负责：**每条洞必须写到「拿起来就能修」**——文件:行、因果、最小复现命令、应有读数、预测最小修法、能先红的变异。

## ② 当前树状态（开工先复核）

| 项 | 读数 |
|---|---|
| HEAD | `f5083286de06b1d1b698a91e51da18463be4f4de`（main，未推送） |
| 工作树 | 混合未提交：563 面（`M core/circuitsemantics.py`、`?? tests/test_563_*.py`、`?? docs/circuit-semantics.md`、`?? tasks/563_*`）+ 他人/临时件（PROGRESS/handoff/roadmap/TASKMAP/review-line、node_modules/、tmp*.json、checkup/、docs/debug.log、blocklib/parts.json.tmp） |
| 已挖（勿重复） | `outputs/hole565/TRIAGE.md`、`outputs/hole566/TRIAGE.md`、`outputs/hole568/TRIAGE.md` |
| 解释器 / CLI | `.venv\Scripts\python.exe` / `.venv\Scripts\boardwise.exe`（`python -m boardwise` 无 `__main__`，exit 1 属环境读数） |

## ③ 八缝分工与文件域（不重叠）

| 缝 | 地盘（只读） | 要证/要找 | 探针 | 报告 |
|---|---|---|---|---|
| **570-A readability 闸门** | `engines/readability.py`（200 KB，从未被本系列审过） | 每个谓词的判据与容差：文字间距、压线、共享网表达、NC 排除集、旗标字形框对象集、跨岛边界、`-1` 哨兵；**声明与实际是否同一把尺**（143 的 03-H1…03-H7 家族是否还有残留）；同一页给两个不同输入是否可能「谓词全过但图明显错」 | `.tmp_hole570/a/` | `outputs/hole570/a/` |
| **570-B islandlayout packer** | `engines/islandlayout.py`（277 KB；567-F 只碰了 `pageframe` 与顶层 bbox） | packer 内部不变量：峰/band/群组/place order、旋转镜像件的 bbox、keep-out 下界、`PageBudget` 与 `IslandBudget` 的消费、失败回退是否静默；**暴力 oracle：从产物逐对象取盒重算**（不许信 packer 自述） | `.tmp_hole570/b/` | `outputs/hole570/b/` |
| **570-C 文法族** | `engines/grammar/{flyback,power_entry,ldo,voltage_divider,rc_lowpass,base}.py`（不碰 ic_periphery/mixed_island，已审） | 143 的 04-H1…04-H7 家族是否还有残留（假诊断、缺 edges 守卫、硬编码 left/right、忽略 sidePreferences、空 direction 放行、伪造地网名、只核一半）；空/单件/畸形电路是否「合法通过」或「假报拒因」；每条文法给出的拒因是否点名真实原因 | `.tmp_hole570/c/` | `outputs/hole570/c/` |
| **570-D 20 条零测试承重函数** | 567-H 清单（`outputs/hole567/h/coverage.csv`）：`drawapply.placement_problems`、`drawapply.validate_layout_partition`、`addcomponent.{landing_spot,allocate_designator,occupied_points,wire_vertices,nearest_wire_point,primitive_id_of}`、`patchpin.{wire_segments,wires_through_pin}`、`moveblock.on_grid`、`select.resolve_identity`、`subcircuit.wire_target`、`core/config.boardwise_home`、`canvasrender.unique_canvas_name` 等 | 直接对这些函数做缺陷挖掘（**它们没有测试网，最可能有真洞**）：坏输入/边界值/重复位号/浮点噪声/跨网取点/重名画布；每条给「若补测试该断言什么」 | `.tmp_hole570/d/` | `outputs/hole570/d/` |
| **570-E `docs/pits.md` 53 条可验性** | `docs/pits.md` 全文 + 各 pit 点名的代码点 | 逐条判：机制是否仍在 HEAD（代码行号还指得对）、结论是否仍成立、有没有**已失效但仍在指导决策**的 pit；只判可离线验的部分（真机项标 suspect 并写清需量什么） | `.tmp_hole570/e/` | `outputs/hole570/e/` |
| **570-F placement 求解器** | `engines/placement.py`（391 KB，最大未审文件） | 约束是否被消费（`RelativeConstraint`、`sidePreferences`、`branchOrder`、`attach`）、求解失败的回退是否静默、**确定性**（同输入两次）、软成本与硬闸是否可能互相掩盖（硬闸全过但成本退化到不可读） | `.tmp_hole570/f/` | `outputs/hole570/f/` |
| **570-G v4facts / pinmap 口径** | `engines/v4facts.py`、circuit/pinmap 派生点（`core/circuitspec.py` 一类） | 单位（mil / 10-mil / px / page unit）、坐标与 `page_y` 符号、姿态（rotation/mirror 复合顺序，坑 29）、多单元与跨页、缺 pose 时的行为；**同一件从 v4-facts 与从 sch.geometry 读出的数是否同口径**（离线部分） | `.tmp_hole570/g/` | `outputs/hole570/g/` |
| **570-H 证据回放漂移** | `evidence/` 里 547S / 548 系列记录的输入（circuit + presentation + profiles）与记录里的几何指纹/拒因 | 用 HEAD 代码**离线重放**这些输入：几何指纹是否仍相同？拒因是否仍相同？若不同，**是哪一批改的**（`git log -S`/blame 定位）？这直接检验 `reference-replay` 三口径之一是否还成立 | `.tmp_hole570/h/` | `outputs/hole570/h/` |

## ④ 交付物与验收

1. `outputs/hole570/<seam>/REPRO.md`：每条六栏（编号/严重度/一句话/**文件:行**/因果/复现命令→实测 vs 应有）。
2. `probes/` + `holes.json`（`schema: "boardwise.hole570/1"`，字段同 565 §④，`status ∈ {reproduced, falsified, suspect}`）。
3. 每条 `reproduced` 有真实运行读数原文；每条至少一次证伪尝试；给**预测最小修法 + 能先红的变异**（不实施）。
4. 严重度四级：`会造假结果` > `会崩` > `会漏` > `仅不一致`。
5. **给修复者的附加要求**：每条洞最后一行写 `FIX: <文件:行> <一句话修法> <先红断言>`，让接手的人不必读完整报告就能开工。
6. 不变量类洞（570-B/F）必须附暴力 oracle 实现；文法类洞（570-C）必须附「输入 → 期望拒因 vs 实测拒因」。

## ⑤ 纪律与红线

- **只读、不修**：不改 `src/ tests/ docs/ contracts/ connector/ dsh-plugin/ evidence/ blocklib/`；不新增测试；探针写 `.tmp_hole570/<seam>/`，报告写 `outputs/hole570/<seam>/`。
- **不动 git**：零 `add/commit/checkout/restore/stash/push`；查历史只 `git show/diff/log/blame`。
- **不删任何东西**；**不碰真机**（零 `boardwise bridge`、零 daemon 拉起、零编辑器、零真实工程写入；一旦某条要连桥，停下记「不可离线」）。
- **测试红线**：只跑点名文件，带 `--basetemp=.tmp_pt_hole570_<seam>`；禁全量、禁 `-n auto`/`-n >4`；探针单进程；前台命令带 timeout。沙箱里 `--basetemp` 可能因 `WinError 5` 失败，**记录该限制并改直接调用，不许当测试通过**。
- **不碰历史证据目录内容**：`outputs/011e*`、`014_*`、`015b_*`、`016_*`、`tests/fixtures/` 只读引用；`evidence/` 只读（570-H 读它，不改它）。
- **保密**：公司/客户名与真实工程名零出现，实名板只写 `PCB1/PCB2/PCB3`。

## ⑥ 预算与交卷格式

- 每缝 **≤40 步或 ≤30 分钟**，先到先停。
- 交卷正文 ≤2000 字，四段：`环境读数` → `洞表（编号/级别/一句话/状态/FIX 一行）` → `证伪清单` → `没查的面 + 下一步最小动作`。
- 零洞也要交，写清查了什么、为什么零。
