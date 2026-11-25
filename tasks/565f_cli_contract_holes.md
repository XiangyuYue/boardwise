# 565f — CLI 合同面两条洞（S5-H2 / S5-H3）

- 批号 **565f**　日期 2026-11-25　owner：CLI　状态：**待派**
- 来源：`outputs/hole565/TRIAGE.md` §1 的 565f 组；`outputs/hole565/s5/holes.json` 的 `H-S5-02`（S5-H2）、`H-S5-03`（S5-H3）；`H-S5-01`（S5-H1）主代理重放已修（缺父目录 exit 5、无 traceback），**本批不修只关单**。
- 文件域：`src/boardwise/commands/draw.py`、`src/boardwise/cli.py`、新建 `tests/test_565f_cli_contract.py`、`evidence/565f/`

## ① 前因后果

2026-11-24 的 565 挖洞在 `draw` 父级/`plan --layout` 上留了两条：

- **S5-H2**：`draw` 父级的 11 个参数（`--from/--spec/--port-meta/--naming/--out/...`）在 `compile|plan|apply|lint` 路由被 argparse 收下后无人消费——`draw --spec <不存在> compile ...` 仍 exit 0，输出与基线无差（143 洞1 同族）。
- **S5-H3**：`draw plan --layout candN.layout.json` 把 compile 自己写的**单模块 LayoutPlan** 当成 closed-schema 未知键拒绝（exit 5），消息不提「要的是 page 候选 `candN.page.json`」。

主代理 2026-11-25 重放（子代理开工必须自己复跑并留原文）：

```
P2 parent --spec nonexistent (compile) → exit 0（仍出 3 候选，静默忽略）
P7/P8 plan --layout c1/cand1.layout.json → exit 5, "unknown key(s) evidence, junctions, labels, parts, powerSegments…"
P3 --json 缺父目录 → exit 5（S5-H1 已修，作反证）
```

## ② 当前树状态

- HEAD/工作树：**混合未提交**（2026-11-25 多批在工作树；`cli.py`、`commands/draw.py` 均有既有未提交改动，属 600R/620 等批，**不许回退**）。
- 本批相关位置：
  - `src/boardwise/commands/draw.py` `register_draw_parser`（父级 11 参 + `--layout` help）与 `dispatch_draw`（子命令路由入口）。
  - `src/boardwise/cli.py` `:15629` 前后（`--layout` 读取）、`:13928`（`--layout` 读失败 note）、`:15763`（`_layout_*` 辅助）、`:16149`。
- 开工前：`cp` 两个源文件到 `.tmp_565f/backup/` 并记 SHA-256（主代理派工时给读数）。

## ③ 文件域与禁触清单

**允许：** `src/boardwise/commands/draw.py`、`src/boardwise/cli.py`、新建 `tests/test_565f_cli_contract.py`、`evidence/565f/`、`.tmp_565f/**`。

**禁触：** `contracts/cli/v1.json`、`contracts/module-owners.json`（改合同=另一批，需主代理授权）；`core/*`、`engines/*`（属 565b/565d/565g）；`tests/fixtures/`；任何既有测试断言（合法变红就停下报告）；`docs/`（本批不改文档）。

## ④ 交付物与验收（先红后绿）

新建 `tests/test_565f_cli_contract.py`（纯内存 CLI 调用，抄 `tests/test_lock_p1_delivery_gates.py` 的 `cli_module.build_parser()` + `_cmd_*` + `capsys` 风格；**不用 `tmp_path`**，需要目录就用 `.tmp_565f/`）。父级裁决：

| 洞 | 期望行为 | 先红断言 |
|---|---|---|
| **S5-H2** | 给了子命令（`draw_command` 非空）且任一父级参数非默认值 → 打印一条点名该参数、说明「父级参数只服务旧的整体重画流程，不进入子命令」并 **return 2**；全部默认值时行为与今天逐字一致（脚本兼容）。守卫加在 `dispatch_draw` 入口，一处覆盖 11 个参数，不逐个子命令写 | `draw --spec <不存在> compile` 当前 exit 0 |
| **S5-H3** | `--layout` 读到的文档 `kind` 不是 page 计划（`boardwise-island-page/1` 的 plan / PageLayoutPlan）而像 compile 候选时，抛/打印**专用**消息：说明这是单模块 LayoutPlan、`--layout` 要的是 page 候选，点名 `candN.page.json`（compile 的 `<cand>.page.json` 兄弟文件）并 exit 5；不再落成 closed-schema 未知键列表 | 现有消息不含 `page.json`/`not a PageLayoutPlan` |

**验收读数：**

```
.venv\Scripts\python.exe -m pytest tests/test_565f_cli_contract.py -q --basetemp=.tmp_pt_565f
.venv\Scripts\python.exe -m pytest tests/test_565f_cli_contract.py tests/test_054_draw_cli.py tests/test_057_draw_page_cli.py tests/test_540_cli_draw.py tests/test_draw_plan_saved_page.py -q --basetemp=.tmp_pt_565f
```

- 先红 ≥2 failed；后绿全 passed（相邻四份的基线由主代理派单时给）。
- **逐洞变异**：S5-H2 守卫改 `if False:` → 点名用例红；S5-H3 的专用消息分支改 `if False:` → 点名用例红；各自 `cp` 还原 + SHA-256 核对。两次读数写报告，禁用 git 恢复。
- 若改 `--layout` help 文字导致合同测试（`contracts/cli/v1.json` 相关）变红：**回退 help 改动并在报告说明**，不许改合同文件。

## ⑤ 纪律与红线

1. 零 git 写；零删除（禁 `rm`/`Remove-Item`）。
2. 不跑全量 pytest、不 `-n auto`、不碰 bridge/EDA、不联网。
3. 不改他人未提交改动（`cli.py`/`draw.py` 上的既有差量原样保留）；不新建第二套 dispatch；父级守卫只加一处。
4. 不得放宽既有断言、skip/xfail、改夹具；不得把「不可复现」写成「已修」。
5. 有红项或无读数，写「停止/未验收」。

## ⑥ 预算与交卷格式

- 上限 **40 步 / 30 分钟**。
- `evidence/565f/REPORT.md`：开工哈希、先红原文、两洞修复点（文件:行）、两次变异读数、后绿原文、S5-H1 关单反证（缺父目录 exit 5）、未做项。
- 最终回复 ≤2000 字：结论 + 关键读数 + 证据路径 + 需裁决项。

## ⑦ 追加：S5-H2 的前置残余（`--render` 写在子命令前，2026-11-25 岳复核提出）

当前守卫只挡「子命令**不**消费的参数」。反方向漏了：子命令**消费**的参数若写在子命令**前**，会被子 parser 的同名 `dest` 默认值覆盖 → 值丢失、且不报错。

实测（主代理 2026-11-25 重放）：

```
boardwise draw --render <svg> lint --snapshot tests/fixtures/ch340_p1_geometry.json
→ exit 0，输出 note: no --render sidecar …（--render 被吞）
boardwise draw lint --render <svg> --snapshot …   → 正常消费
```

**父级裁决：按「子命令是否消费该参数」双向判断**。实现建议：

1. 给 `draw` 父级的全部 11 个 option 注册一个专用 `argparse.Action`：照常写自己的 dest，**同时**把 flag 字符串追加进 `namespace._parent_draw_seen`（子 parser 不会碰这个属性，位置信息因此保住）。
2. `_parent_draw_options_given` 改为读 `_parent_draw_seen`（不再靠「值≠默认值」——显式给默认值也算「给了」）。
3. `dispatch_draw`：有子命令且 seen 非空 →
   - flag 是子命令自己消费的（`--render` on `apply`/`lint`）：话术必须说「它写在子命令**前**，会被子命令自己的默认值覆盖；把它写到子命令**后**」；
   - 其它 flag：沿用现有「父级参数不进入子命令」话术；
   - 两者都 `return 2`。
4. 无子命令的旧整体重画流：`args.render` 等照旧可用，行为逐字不变。

**先红**：新测 `draw --render <svg> lint --snapshot …` → exit 2 且 stderr 含 `--render` 与「after the subcommand」；`draw lint --render <svg> …` 仍 exit 0；`draw --naming wire compile …`（显式给默认值）也 exit 2。

**变异**：①Action 不记录 seen → 新测红；②dispatch 不看 seen 只看值 → 新测红（`--render` 前置那条仍绿回）。各自 `cp` 还原 + SHA-256。

**读数与边界**：五文件仍全绿（≥128 passed + 新用例）；`contracts/` 与 help 不动；写入 `evidence/565f/PARENT-ACCEPTANCE.md` 的「追加」节。上限 25 步。
