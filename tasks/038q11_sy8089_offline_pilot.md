# 038Q11：SY8089 block 的离线编译与视觉试点

日期：2026-11-12。依赖 038Q10 的真实 symbolRef。只做离线数据、编译、逐脚和视觉自审；
不改绘制语法，不申请落图，不解除 catalog 的 notForDrawCompile。

## 输入与最小 PresentationSpec

新增 `blocklib/specs/sy8089_buck_3v3.presentation.json`，复用现有 `ic-periphery`，核心为 U，
模块包含 C_HF/C_IN/C_OUT/L/R_FBB/R_FBT/U。`portRoles` 的键必须使用 CircuitSpec 的真实
net id（`port.VIN`、`port.3V3`、`port.EN`、`port.GND`），不能用显示名 VIN/3V3 代替。

本批不伪造 buck 语法。`ic-periphery` 未绑定的输出侧器件必须在证据中明确列出；
如果需要，可用既有语义约束字段表达 L 位于 LX→3V3、反馈分压和去耦关系，但禁止
userLocks/像素坐标、位号特判或修改 `engines/grammar/**`。

## 必查电气关系

- `U.LX ↔ L.1`、`L.2 ↔ port.3V3`：电感串在开关节点与输出之间，不得接到 VIN。
- `U.FB ↔ R_FBT.2/R_FBB.1`、R_FBT.1→3V3、R_FBB.2→GND：反馈分压完整。
- C_IN 在 VIN/GND，C_OUT+C_HF 在 3V3/GND；不得漏输出电容。
- EN 与 VIN 是不同端口，禁止因同电位合并；EN 必须出边界标签。
- VIN/3V3/GND 使用旗标，不拉全板母线；七个 part 都使用 038Q10 的真实 symbolRef。

## 三关与 negative control

1. **编译/机器闸**：用模块 CircuitSpec + PresentationSpec + `blocklib/symbols/profiles.json`
   运行真实 `draw compile`，记录 ok/candidates/rejected/failures/readability hard。
2. **逐脚回验**：用现有 readability/derive_netlist，按脚号优先、脚名次之的现有规则归一，
   与源 CircuitSpec 六个网逐成员比对；记录 6/6、短路、悬空与缺失件，不能只看 ok=True。
3. **视觉自审**：渲染首候选，主代理必须亲看并说明电感主回路、反馈、输入/输出电容、
   EN/GND/电源旗各在哪里、是否一眼像 buck。看不懂或拓扑被自由摆放破坏即拒收，不端给用户。

负例至少覆盖：L 错接 VIN、EN 合并到 VIN、删 R_FBT、删 C_OUT；这些只能在临时变异副本
或内存中进行，真实输入不动，预期必须被源网对账或机器闸发现。

## 文件域与纪律

- PresentationSpec、新增 `tests/test_038q11_sy8089_offline_pilot.py`；
- `outputs/review/038q11/`（compile JSON、候选 SVG/PNG、逐脚与视觉证据）；
- `.tmp_038q11/`（一次性渲染/验证脚本和备份）；
- 本任务书及必要文档。

不改模块生成器、book、catalog、Rust、bridge/DSH、grammar 或其他绘制文件。零真机、零部署、
零 git 写、零 apply。测试使用独立 `--basetemp=.tmp_pt_038q11`，暂不跑全量。

## 实施记录（2026-11-12，子代理执行）

**交付物**：`blocklib/specs/sy8089_buck_3v3.presentation.json`（最小 ic-periphery）、
`tests/test_038q11_sy8089_offline_pilot.py`（9 用例）、`outputs/review/038q11/`
（`compile.json`、`verification.json`、cand1–3 的 layout+SVG）、`.tmp_038q11/`
（`verify_per_pin.py` 一次性逐脚脚本、`cli.log`）。grammar、绘制算法、模块生成器、book、
catalog、Rust、bridge/DSH 零改动；真机/部署/git 写/apply 零动作；真实输入未动。

**文档**：单模块 `buck`（7 件全部：U/L/C_IN/C_OUT/C_HF/R_FBT/R_FBB，`core: "U"`），
文档级 `grammarRef: "ic-periphery"`；`portRoles` 用真实 net id —— `port.VIN: source`、
`port.3V3: load`、`port.EN: input`；`sidePreferences` 声明 input/output/load/source/power/gnd 六向；
无 `userLocks`、无坐标、无 `islands`/`seriesBranches`/`panelGroups`/`serviceLayout`，无位号特判。
两点实测约束：① **模块级 `grammarRef` 会把文档路由到页编译器**（`pagecompiler.wants_page`
的第三条），单模块离线编译只能在文档级声明，故模块只写 `core`；② `port.GND` 虽是真实 net id，
但 `portRoles` 的值域是本仓 `PORT_DIRECTIONS`（source/load/input/output/feedback，无 gnd，且
`_port_roles` 拒绝空串），给它填方向就是伪陈述，接地由 net class + `sidePreferences["gnd"]` 表达，
该键故意缺席（测试钉住了这一点）。

**机器闸**（真实 CLI 编译；本包无 `boardwise/__main__.py`，`python -m boardwise` 不可用，
用同一入口的 console script）：

```
.venv/Scripts/boardwise.exe draw compile --circuit blocklib/modules/circuits/sy8089_buck_3v3.circuit.json \
  --presentation blocklib/specs/sy8089_buck_3v3.presentation.json \
  --profiles blocklib/symbols/profiles.json --out outputs/review/038q11 --json outputs/review/038q11/compile.json
```

读数 exit 0：`ok=true`、**3 candidates / 0 failures / 3 rejected**、`categories=[]`；
三个候选 `hardViolations=0`；软指标（首候选）bends=10、crossings=0、wire_length=1005、
min_text_gap=1.5、unaligned_part_pairs=14；**2 条 grammar 软发现**：`port.3V3`、`port.VIN`
「power net drawn without a power flag」（069 §7）。生成 `cand1–3.svg/layout.json`。

**逐脚回验**（`.tmp_038q11/verify_per_pin.py`，`readability.derive_netlist` + `_canonical_pin`
的 number-first 归一，结果 `outputs/review/038q11/verification.json`）：三个候选**均 6/6 逐成员相等**，
`missing=[]`、`extra={}`、shorts=0、dangling=0、missing_parts=0。命名：仅 `port.EN` 有标签名
（跨模块信号出边界标签，符合要求）；`port.GND` 的 5 个引脚名都在但**没有旗标**，且 GND 网
被 520E 降级为「按名表达」（`label_fallbacks: port.GND [C_HF.2,C_IN.2,C_OUT.2,R_FBB.2,U.GND]`，
attachment 阶段失败：`(95,-50)` 无可用走线）。**旗标一项本批未达成**，原因在输入而非文档：
`profiles.json` 只有 19 个器件符号、无 `PWR-*`/地旗标族，`_flag_ref` 按 `PWR-<netId>` 查书必然
落空（且 net id 带 `port.` 前缀，即便书里有 `PWR-VIN` 也对不上 `PWR-port.VIN`）。

**ic-periphery 未绑定器件（本批关键缺口）**：`C_HF`、`C_OUT`、`L`、`R_FBT`。grammar 的 `rail`
取「core 自己脚上的 power 网」＝`port.VIN`（U 没有 3V3 脚），于是：L（LX↔3V3）与 R_FBT（FB↔3V3）
「一网是 core 脚网、另一网既非 rail/gnd 也非 core 脚网」→ 既非 bridge 也非 shunt，落在自由货架；
C_OUT/C_HF（3V3↔GND）只碰 core 的地、不碰 core 的脚网 → 同样未绑定。已绑定：`U`=core、
`port.VIN`=rail、`port.GND`=gnd、`C_IN`=shunt、`R_FBB`=shunt。这些器件**未被拒**（非 stray），
所以机器闸与逐脚对账都过，但「一眼像 buck」的输出侧（电感主回路、输出电容、反馈上臂）
不是 grammar 摆的 —— 视觉结论交主代理亲看，本记录不自称通过。

**负例（内存变异，真实输入未动）**：① L.1 接到 `port.VIN` → 机器闸**接受**（VIN→3V3 仍是
rail-rail 形状），源网对账抓到：`U.3` 从 L.1 的节点消失、`C_IN.1` 与 L.1 同节点；
② EN 并入 VIN → 有 `portRoles` 声明时机器闸 `facts-missing: portRoles names 'port.EN', which is
not one of the circuit's nets` 直接拒；把 `portRoles` 摘掉后能编译，源网对账抓到 `port.EN`
节点多出 `C_IN.1`/`U.4`、`port.VIN` 多出 `U.1`、exact=4/6；③ 删 R_FBT → 机器闸无候选；
④ 删 C_OUT → 机器闸无候选。

**测试**：`python -m pytest tests/test_038q11_sy8089_offline_pilot.py -q --basetemp=.tmp_pt_038q11`
→ **9 passed**（文档合同、portRoles 真实性、编译出候选、6/6 逐成员、未绑定集合钉住、四条负例）；
未跑全量。变异自证未做（本批只加文档+测试+证据，未改产品代码）。

## 主代理视觉裁定（2026-11-12）

- 主代理通过本地只读 HTTP 浏览器亲看首候选 `cand1.svg`。首候选虽然 hard=0、6/6 逐脚一致，
  但电感/输出电容/反馈上臂没有形成可读主回路，GND 退化为重复的 `port.GND` 标签，VIN/3V3
  也缺电源旗，**一眼不能认成 Buck，视觉拒收**。
- 结论是**机器过、视觉拒**：不把候选端给用户，不执行 plan/apply，不解除 notForDrawCompile。
  主代理复跑数据合同 **9 passed**；预览 HTTP 服务与浏览器 tab 均已关闭。
- 绘制线缺口单独移交 `tasks/038q11a_buck_grammar_gap.md`：输出侧四件未绑定与旗标族/net id
  对齐必须解决，不能靠放宽机器闸或手摆坐标消缺。CBB 不修改 grammar。
