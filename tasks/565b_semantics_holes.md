# 565b — 563 语义投影层的六条洞（S1-1…S1-6）

- 批号 **565b**　日期 2026-11-25　owner：绘制线/shared 语义层　状态：**在途**
- 来源：`outputs/hole565/TRIAGE.md` §1 的 565b 组（2026-11-24 挖洞，2026-11-25 主代理重放确认**六条全部仍复现**）
- 文件域：`src/boardwise/core/circuitsemantics.py`、`src/boardwise/core/netlist.py`、新建 `tests/test_565b_semantics_holes.py`、`evidence/565b/`

## ① 前因后果

565 绘制线挖洞在 563（共享网表 + 电路语义）合并后审到 6 条同族缺口：563 的投影层（`compile_semantics` / `to_c` / `verify_semantics` / `read_netlist_document`）在「类型、身份、名字、零脚件」四点上有静默面。

2026-11-25 主代理在当前树重放 `outputs/hole565/s1/probes/*.py`，六条**全部仍复现**（原文见下 ②）。本批只修这六条，不扩项。

六条的实测读数（子代理开工必须自己复跑一遍，不许直接引用本行）：

```
p1: reader parts ['R1','U9'] / parts table [R1 only] / text mentions U9: False
p2: baseline verify True; bool true verify=True; float 1.0 verify=True
p3: forged net() statement present: True    (pin_count 被裸插值)
p4: 6 component entries stated → parts 2, pins 3, 无拒绝无披露
p5: 同 source_id 两实例: net_of 拒绝 AmbiguousPinError, nets_of 返回 ('A','B')
p6: 同 view 两次编译不同；改 netlist 后 names ['FORGED','2']；verify(old)=False
```

## ② 当前树状态

- HEAD **`76e08060ded403793bc6fb0eb64b38f9e140c765`**（`Harden drawing and bridge safety`），工作树**混合未提交**（93 个路径）。
- `src/boardwise/core/circuitsemantics.py`：**` M` 未提交 8 行**（563 的 `_series` 闭环改动，见 `git diff`），这是基线，**不许回退、不许重写**，只在其上叠加。
- `src/boardwise/core/netlist.py`：干净，与 HEAD 相同。
- 备份与开工哈希（主代理已做，`.tmp_565b/backup/`）：
  - `circuitsemantics.py` `9a5aecea6782840e5343fb1bc32ff5ecf594b39f8c73567bd70edc02e5ecc7a1`
  - `netlist.py` `29f3c6708c85427b2f6e6de4988cb28944d55b691f31d36239d70b7fde65f6b8`
- 聚焦基线（主代理实测）：`tests/test_563_circuit_semantics.py` + `tests/test_563_netlist_view.py` → **36 passed**。
- 测试夹具 `tests/fixtures/ch340_p1_editor_netlist.json`、`ch340_drawn_page_netlist.json` 均为 17 个 component，全部有 `Designator` 与 `pinInfoMap`（主代理已核），S1-4 的严格拒绝不会误伤这两份样本。

## ③ 文件域与禁触清单

**唯一允许修改/新建：**

| 路径 | 允许 |
|---|---|
| `src/boardwise/core/circuitsemantics.py` | 改 |
| `src/boardwise/core/netlist.py` | 改 |
| `tests/test_565b_semantics_holes.py` | 新建 |
| `evidence/565b/REPORT.md` | 新建（交卷报告） |
| `.tmp_565b/**` | 自己的临时目录 |

**禁触（碰了等于破坏他人工作）：**

- `tests/test_563_circuit_semantics.py`、`tests/test_563_netlist_view.py`——**不许删改任何断言**。若本批修复让其中某条合法地变红，停下、把失败断言原文报给主代理，由主代理裁决，不许自行放宽。
- `tests/fixtures/` 既有夹具——一份都不改。
- `src/boardwise/cli.py`、`engines/drawlint.py`、`engines/svgpreview.py`、`core/presentationspec.py`、`core/pageframe.py`、`commands/draw.py`——属其它批（565f/565g/565d/565e）。
- 任何未在本表列出的文件；任何 `outputs/`、`evidence/`（除 `evidence/565b/`）、`tasks/` 既有文件。
- 不许动 `.tmp_565b/backup/` 里的主代理备份。

## ④ 交付物与验收（先红后绿，逐洞）

新建 `tests/test_565b_semantics_holes.py`，**先写全部用例并在未修复代码上跑出红**（把失败原文存 `evidence/565b/RED.txt`），再实施修复。每洞的期望行为：

| 洞 | 期望行为（父级裁决） | 先红断言 |
|---|---|---|
| **S1-1** | `_facts()` 收录 view 知道的**每个** part：有位号零脚件进 `parts` 表且 `pin_count: 0`，`to_c()` 输出 `part("U9", "u9", pins=0);`；`pins`/`nets`/`unconnected`/关系不变。实现：view 增part 清单（设计号、source_id、脚数快照），`_facts` 由它建 part 行，而不是只从 `pin_refs()` 反推 | R1 两脚 + U9 零脚 → parts 表目前只有 R1 |
| **S1-2** | `verify_semantics` 与 `roundtrip_members` 都用**类型严格**比较：`True`/`1.0`/`'1'`/`[1]` 顶替 `1` 一律 False；dict 键集、list 顺序长度、float 精确比较；实现一个递归 `_strict_equal`（`type(a) is type(b)`，bool 与 int 不同型） | `pin_count: true` / `1.0` 当前判 True |
| **S1-3** | `SemanticProgram.as_dict()` 回来再 `to_c()` 时，任何 `parts[].pin_count` 不是真正的 `int`（排除 bool）→ `ValueError`，**不产出任何文本**；合法程序文本与修复前逐字节相同（用小夹具钉全文） | 伪造 `'1); net("FORGED", ["X"]); //'` 当前渲染出整条 `net(...)` |
| **S1-4** | `read_netlist_document` 对「非 dict 的 component 行」和「缺/空 `Designator` 的条目」**拒绝**，`ValueError` 点名条目键与原因；两份 17 件夹具读出的 parts/pins 数不变 | 6 条台账 → 2 件 3 脚，零拒绝 |
| **S1-5** | `nets_of` 与 `net_of` 一致：同一 designator 有两个实例（**即使 source_id 都是 `""`**）时，`nets_of('U1')` 抛 `AmbiguousPinError`；给了 source_id 但该 source_id 下仍有两个实例也拒绝；distinct source_id 时 `nets_of('U1','a')` 只返回该实例的网 | 同 source_id 两实例时 `nets_of` 合并返回 `('A','B')` |
| **S1-6** | view 在**构造时**快照脚名（新 `NetlistView.pin_names()`，返回 `dict[PinRef,str]`），`compile_semantics` 只读快照；构造后改 `netlist.parts[0].pins[0].raw_name` 不影响文档；同一 view 两次编译逐字节相同；`verify_semantics(view, first)` 仍 True | 改 source 后文档变化、`verify(old)` False |

**验收读数（必须原文）：**

```
.venv\Scripts\python.exe -m pytest tests/test_565b_semantics_holes.py -q --basetemp=.tmp_pt_565b
.venv\Scripts\python.exe -m pytest tests/test_565b_semantics_holes.py tests/test_563_circuit_semantics.py tests/test_563_netlist_view.py -q --basetemp=.tmp_pt_565b
```

- 先红：新用例至少 6 条 failed；后绿：上面第二条命令全 passed（≥42 passed：6 新 + 36 旧）。
- **逐洞变异**：修完后把该洞的因果行改成等价于 `if False:` 的形态（或直接删掉该守卫），确认**点名的那条用例**先红，再用 `.tmp_565b/sub-backup/` 的 `cp` 备份 + SHA-256 还原复绿；六次变异读数写进报告。禁止用 `git checkout/restore` 恢复。
- 不许为了让测试过而：删除/放宽既有断言、加 skip/xfail、改夹具、改 `contracts/`。

## ⑤ 纪律与红线

1. **零 git 写**：不 `add`/`commit`/`checkout`/`restore`/`stash`/`push`；只读 `git status`/`git diff` 可以。
2. **零删除**：任何文件/目录不许 `rm`/`rm -f`/`rm -rf`/`unlink`/`Remove-Item`；临时产物留在 `.tmp_565b/`。
3. 不跑全量 pytest、不 `-n auto`、不碰 bridge/daemon/EDA、不联网。
4. 不改他人未提交改动（`circuitsemantics.py` 的 8 行 563 差量必须原样保留）；不新建第二套语义/网表子系统，只在既有函数上补洞。
5. 不得以改参数、改阈值、缩小断言的方式凑绿；不得把「不可复现」写成「已修」——不复现就报「已修/不可复现」并附反证命令。
6. 交卷时本批若有红项或没有读数，写「停止/未验收」，不写「完成」。

## ⑥ 预算与交卷格式

- **上限 40 个模型步骤或 30 分钟**，先到先停；接近上限立即交回（已完成、真实读数、剩余洞、下一步最小动作）。
- 交卷报告 `evidence/565b/REPORT.md` 必须含：开工哈希、先红原文（命令 → 汇总行）、逐洞修复说明（文件:行）、六次变异读数、后绿原文、未做项与风险。
- 最终回复给主代理 ≤2000 字：只写结论 + 关键读数 + 证据路径，不贴整段日志。

## ⑦ 追加：S1-4 的另一半（pin 行，2026-11-25 岳复核提出）

S1-4 只闭了**组件行**。`netlist.py` 的 pin 行仍有一条静默路径：`if not isinstance(info, dict): continue`——3 条 pin 行读成 2 脚、无拒绝无披露。同一条纪律必须覆盖 pin 行。

**父级裁决**：

1. 非对象 pin 行 → `ValueError`，点名**组件位号 + pin 键**，形如 `component 'R1': pin entry '3' is not a pin object (str)`；
2. `pinInfoMap`/`pins` 成员存在但不是 mapping 也不是 list → `ValueError`（当前静默退成零脚件）；
3. **没有** pin map 成员仍是合法的零脚件（S1-1 的合同，不许改成拒绝）。

**先红后绿**：在 `tests/test_565b_semantics_holes.py` 追加用例——`{'1': dict, '2': dict, '3': 'not-a-pin'}` 必抛且消息含 `'3'`；`pinInfoMap: 17` 必抛；`pinInfoMap: {}` 仍 0 脚不抛。未修复树先红（当前 `pins=2` 且不抛）。

**变异**：把新 raise 改回 `continue`/去掉类型检查 → 两条新用例红；`cp` 还原 + SHA-256 核对。

**读数与边界**：追加后聚焦 565b 三文件仍全绿、消费方 377 passed 不回归；写入 `evidence/565b/PARENT-ACCEPTANCE.md` 的「追加」节。上限 15 步。
