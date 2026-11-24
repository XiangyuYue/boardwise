# 任务书：568 / 569 — 绘制线挖洞第三批（口径面 + 存量机制面，只读）

- 批号 **568**（合同/口径/说法面）+ **569**（存量机制面）　日期 2026-11-24
- 承接 `tasks/565_draw_holes.md`（24 洞）、`tasks/566_draw_holes_wave2.md`（14 洞）。前两批挖的是「代码做错什么」，本批挖**「说的和做的是不是一回事」**与**「机制层不变量」**。
- **性质：只读挖洞。只提交可复现问题，不修、不写生产与测试、不落画布、不碰真机。**

## ① 前因后果

- 0.6.3 与 564 之后，代码侧的闸门类洞已经挖出两条主根因（闸门"没跑"仍印 clean、标题栏 keep-out 在 page 路径不存在）。
  第三批换角度：**声明面**——`docs/draw.md`（126 KB）、`docs/schematic-style-spec.md`（S-01…S-21，14 KB）、
  `contracts/cli/v1.json`（570 KB）、DSH 工具描述、两份 SOP 副本，都是"load-bearing 声明"，按 `AGENTS.md` 纪律
  「文档声明必须机器可验」，验不了的就是洞。
- 569 换机制角度：载入/往返/闭合 schema、进程级状态与环境变量、退出码矩阵、既有 xfail/skip 与永真断言。
  这四类在 143（洞2「NaN 崩 CLI」、洞1「锁只校验不应用」）、548B3（"删 checker 注入仍绿"）都出过真洞。
- 用户明确要求：**只挖不修**。任何"顺手改一下"都算越界。

## ② 当前树状态（开工先复核）

| 项 | 读数 |
|---|---|
| HEAD | `f5083286de06b1d1b698a91e51da18463be4f4de`（main，未推送） |
| 工作树 | 混合未提交：563 面（`M core/circuitsemantics.py`、`?? tests/test_563_*.py`、`?? docs/circuit-semantics.md`、`?? tasks/563_*`）+ 他人/临时件（PROGRESS/handoff/roadmap/TASKMAP/review-line、node_modules/、tmp*.json、checkup/、docs/debug.log、blocklib/parts.json.tmp） |
| 已挖 | `outputs/hole565/TRIAGE.md`（24）、`outputs/hole566/TRIAGE.md`（14）——**不要重复**，撞到写「与 565-XX / 566-XX 同源」并跳过 |
| 解释器 | `E:\boardwise\.venv\Scripts\python.exe` |

## ③ 八缝分工与文件域

### 568 — 合同 / 口径 / 说法面

| 缝 | 地盘（只读） | 要找的 | 探针 | 报告 |
|---|---|---|---|---|
| **568-A 文档声明 vs 代码** | `docs/draw.md`、`docs/schematic-style-spec.md`、`docs/pits.md`；对照 `tests/test_doc_claims.py` 已有的钉 | 逐条挑**承重断言**（命令/参数/退出码/默认值/阈值/"永不"/"只"/"必须"），判：① 有机器钉且真成立；② 有钉但钉的是过时值（钉本身说谎）；③ **无钉**且与代码不符/无法验；④ S-01…S-21 哪几条被写成"机器已验"而其实只靠人眼。**每条洞给「文档行号 → 代码行号 → 实跑读数」三段** | `.tmp_hole568/a/` | `outputs/hole568/a/` |
| **568-B CLI 契约对拍** | `contracts/cli/v1.json`、`docs/bridge.md` §4 动作表、`cli.py` 的参数注册（只按字面定位）、`tests/test_action_catalogue.py` | 契约是否**单向漂移**：json ⊆ 实跑（实跑有而契约无）；退出码声明与实测（0/1/2/3/5、daemon 拒绝码）；`--json` 输出 schema；新增面是否都在契约里（`draw lint --netlist/--bodies`、`draw plan --layout`、`draw v4-facts`、`edit plan --move`、`pcb path`）；`bridge/protocol.py` 目录 vs docs §4 vs connector handler 三处是否仍同步 | `.tmp_hole568/b/` | `outputs/hole568/b/` |
| **568-C DSH 工具面与 SOP 副本** | `dsh-plugin/src/draw-tools.ts`、`dsh-plugin/src/*.ts` 工具描述、`tests/test_dsh_plugin_sync.py`、`.agents/skills/boardwise/SKILL.md` 与 `.kimi-code/skills/boardwise/SKILL.md`（两份逐字节同源）、`.agents/skills/boardwise-draw/SKILL.md` | 工具 description 的断言（"offline"/"read-only"/"never recomputes"/"exit 5 是拒绝"）与实现是否一致；argv 组装是否丢参/改参；错误映射；同步哨兵**覆盖到哪**、漏了哪些新面；SOP 里点名的命令/工具/路径是否都还存在（点名的命令不存在 = 文档洞） | `.tmp_hole568/c/` | `outputs/hole568/c/` |
| **568-D 三种记账口径** | `engines/agentadjusted.py`、报告/交付摘要的生成点（`cli.py` 的 draw 交付段、`engines/*` 里 `reference-replay`/`automatic` 字面）、`docs/handoff.md` 与 `evidence/548J/agent-adjusted/RULES.md` 的规则 | `automatic` / `reference-replay` / `agent-adjusted` 三者是否**真可区分**：字段在哪、谁写、谁读；能否把 agent 微调写成 automatic（或反过来）；`automatic` 字段有没有消费者；RULES.md 的规则有没有代码执行；交付摘要能否缺项仍报通过 | `.tmp_hole568/d/` | `outputs/hole568/d/` |

### 569 — 存量机制面

| 缝 | 地盘（只读） | 要找的 | 探针 | 报告 |
|---|---|---|---|---|
| **569-E 载入 / 往返 / 闭合 schema** | `core/layoutplan.py`、`core/pagelayoutplan.py`、`core/changeplan.py` 的 load/save | ① 未知键是否具名拒绝（closed schema）；② 版本升级/降级（`planVersion`、`PAGE_LAYOUT_PLAN_KIND`）是否可读旧件；③ NaN/Inf/超大值/重复键/空文件/目录当文件的行为；④ **往返**：save→load 是否逐字节等价（浮点、键序、可选键省略）；⑤ 附带键（如 `dshArtifacts`）会不会被静默丢弃或当未知键拒；⑥ 一个 LayoutPlan 被误喂给 PageLayoutPlan 的报错是否具名 | `.tmp_hole569/e/` | `outputs/hole569/e/` |
| **569-F 进程级状态 / 环境 / 路径** | 全 `src/boardwise` 的模块级可变全局、`functools.cache`/`lru_cache`、`os.environ` 读取点（`BOARDWISE_*`）、`core/config.boardwise_home`、原子写工具（`_write_json_atomic` 一类）、临时文件命名 | ① 同进程两次调用是否串味（缓存/全局被上一次污染）；② 环境变量组合（`BOARDWISE_HOME` 不存在/只读/UNC/超长路径、`BOARDWISE_WRITE_PROJECTS`、`BOARDWISE_NO_*`）；③ 写失败时是否留半成品/临时文件（原子性）；④ 非 ASCII/空格/长路径目录；⑤ Windows 特有（盘符大小写、`\\?\`、结尾空格）| `.tmp_hole569/f/` | `outputs/hole569/f/` |
| **569-G 退出码与「输入问题永不抛栈」** | draw/lint/plan/apply/v4-facts/edit/pintable 的 CLI 入口与错误类型；对照 `docs/draw.md` 的退出码声明 | 对每个命令喂坏输入：坏 JSON、缺必填键、目录当文件、空文件、超长串、NaN、互斥参数同给、`--page-box` 反盒、不存在路径、只读目标；核对**退出码 / 话术 / 是否带 traceback / 是否已落半成品**。143 洞2 家族（NaN/Inf 崩 CLI）优先 | `.tmp_hole569/g/` | `outputs/hole569/g/` |
| **569-H xfail/skip 与永真断言盘点** | `tests/test_54*.py`、`tests/test_draw*.py`、`tests/test_*draw*.py` 里 60 处 `xfail|skip`，以及全 draw 测试的断言形态 | ① 每条 xfail/skip：堵的是哪个洞、洞是否已在 HEAD 修好（可摘）、是否 strict；② 静态找**永真断言**：`assert True`、只 `assert x is not None`、断言宽到任何实现都过、`pytest.raises` 包住恒不抛的调用；③ 同一测试里"先跑生产函数再拿它的输出当期望"的自证式断言。**只报 suspect 与清单，不改测试** | `.tmp_hole569/h/` | `outputs/hole569/h/` |

## ④ 交付物与验收（每缝同前两批）

1. `outputs/hole56{8,9}/<seam>/REPRO.md`：每条六栏（编号/严重度/一句话/文件:行/因果/复现命令→实测 vs 应有）。
2. `probes/` + `holes.json`（`schema: "boardwise.hole56{8,9}/1"`，字段同 565 §④，`status ∈ {reproduced, falsified, suspect}`）。
3. 每条 `reproduced` 有一次真实运行读数原文；每条至少一次证伪尝试；给预测最小修法 + 能先红的变异（**不实施**）。
4. 严重度四级：`会造假结果` > `会崩` > `会漏` > `仅不一致`。
5. **568 额外**：文档类洞必须给「文档行号 → 代码行号 → 实跑读数」三段，否则只算 suspect。
6. **569 额外**：不变量类洞必须附暴力 oracle 或属性测试思路。

## ⑤ 纪律与红线（逐条写死）

- **只读**：不改 `src/ tests/ docs/ contracts/ connector/ dsh-plugin/ blocklib/`；不新增测试；探针写自己的 `.tmp_hole56x/<seam>/`，报告写自己的 `outputs/hole56x/<seam>/`。
- **不动 git**：零 `add/commit/checkout/restore/stash/push`；查历史只 `git show/diff/log/blame`。
- **不删任何东西**；**不碰真机**（零 `boardwise bridge`、零 daemon、零编辑器、零真实工程写入）。
- **不修**：用户明确「只挖不修」。任何生产/测试改动都算越界。
- **测试红线**：只说点名文件；带 `--basetemp=.tmp_pt_hole56x_<seam>`；禁全量、禁 `-n auto`/`-n >4`；探针单进程；前台命令带 timeout。若沙箱下 pytest 因 `WinError 5`/scandir 失败，**记录该环境限制并改用直接调用**，不许把它当"测试通过"。
- **不碰历史证据**：`outputs/011e*`、`014_*`、`015b_*`、`016_*`、`tests/fixtures/` 只读引用。
- **保密**：公司/客户名与真实工程名零出现，实名板只写 `PCB1/PCB2/PCB3`。

## ⑥ 预算与交卷格式

- 每缝 **≤40 步或 ≤30 分钟**，先到先停。
- 交卷正文 ≤2000 字，四段：`环境读数` → `洞表（编号/严重度/一句话/状态）` → `证伪清单` → `没查的面 + 下一步最小动作`。
- 零洞也要交，写清查了什么、为什么零。
