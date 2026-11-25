# 任务书：617 — 543d 的 ic-periphery 页恢复合法候选

## ① 前因后果

`outputs/hole570/h2/REPRO.md` 的 **570-H2-01**：543d 原记录同一电路/规格/library 得 4/4 页候选，旧 HEAD 变 0 候选，拒因是 usb_c 的 +5V 在 USB1.B4A9 无旗座。主代理已在 76e0806 用真实 CLI 重放，91.1s 后仍 exit 5，原文为 `7 variant(s) ... no lead fits ... USB1.B4A9 (35,-45)`；日志 `.tmp_hole570_fix/h2/replay.log`。

原 FIX 说“先试脚自身逃逸侧备用格”，但当前 `_flag_pin_lead` 28473–28493 已按 `escape` 优先再四方向，不能重复加同一机制。必须先定位实际哪个生产者/墙体/备用梯级导致全灭，并证明最小因果改动。可以只读 `git show/log` 和临时提取历史源码做差分，禁止 checkout/worktree，禁止恢复整份旧编译器。

本批只修 H2-01，不夹带 B2、A2 或证据文档。543d 是 CH343 已验收拓扑的回放，不重开 SmartMedicineBox 自动整页。

## ② 当前树状态

- HEAD/origin `76e08060ded403793bc6fb0eb64b38f9e140c765`；前批 602–616 的改动必须保留，尤其 607 drawcompiler（若已先落，以其修后 SHA 为基线）。
- 开工时 `src/boardwise/engines/drawcompiler.py` SHA-256 `2b3c3f16d3f27bf18a6b8992e865d5277f7397d430ff6722ea700699672cb320`；607 若改同文件，串行后重新记录。
- 真实输入固定：`blocklib/specs/ch343_uart_534a.circuit.json`、`evidence/543d/effective.presentation.json`（SHA `644268369f…d3d10`）、`blocklib/specs/ch343_uart_v4.library.json`、page-box `0,0,1170,825`。
- 历史记录：`evidence/543d/compile/result.json` 4 候选，首 geometry `85995cd645be…`；当前输入的 source/provenance 字段可能因后续合法合同变化，分别核几何与合同，不强改 JSON。
- 当前 `router.py` 有非本批修改，禁止触碰或恢复。他人 563/review-line/临时文件禁触。开始 cp 备份 drawcompiler 到 `.tmp_617/backup/`。

## ③ 文件域与禁触清单

允许修改/新建仅：
- `src/boardwise/engines/drawcompiler.py`（已定位的 ic-periphery 旗座最小因果 hunk 与注释）
- `tests/test_617_543d_replay.py`（新；可有快速因果用例 + 一次真实 CLI）
- 本任务书、`.tmp_617/`、`.tmp_pt_617/`、`evidence/617/`

禁止：presentation/circuit/library 输入、pagecompiler/placement/router/readability/grammar、CLI/shared/connector/DSH、fixtures、历史证据、他人文件。不得调页框/GAP/reach/flagLeadLimit/variant预算、删文字或约束、换岛、改网名、绕过 flag gate，不新增 builder/router/第二套旗位器。607 的 keepout hunk必须保留。

## ④ 交付物与验收

### 先定位再实现

1. 用真实 CLI 保留当前 0 候选基线；进一步沿现有 build/seat 调用捕获 USB1.B4A9 的候选梯级与首堵墙，指出哪一行/哪次搜索丢掉 543d 的合法逃逸。必要时只读比较 319a76e 前后 hunk 或 543d 历史引擎，不能用“某提交很大”代替根因。
2. 快速回归先红：同一输入的 USB 模块或最小等价真实 profile 场景，证明当前候选枚举不含合法逃逸/最终 0 候选；负控证明不是把硬性穿体/跨网/文字冲突放宽。
3. 最小修复后，真实 CLI 必须 `ok=True`、至少一个合法 page candidate；历史合同目标是 **4 candidates**，若数量不同须逐项解释由哪项已验收行为变更导致，不能简单改记录。首选 geometry 与历史 `85995cd645be…` 对照；若不同，按几何/路线/provenance 分开列差，不得修改历史 hash。
4. 所有产出 page candidate 必须经既有 `LayoutPlan/PageLayoutPlan.load` 与可读性/逐脚独立复核；报告 P1–P4（离宿主脚距离、旗域同形、无绕行、二维跨度）及失败数。首选及有代表性的候选渲染到 `evidence/617/`，供主代理视觉检查；机器绿不等于视觉通过。
5. 邻域至少跑 CH343/CH340 的 pinned、543d/543g/543i/548D flag orientation、607 及 owner/layer 相关测试；不跑全量。既有基线红逐名披露，不能为了新回放改宽断言。

至少两项生产变异：① 删除新逃逸/恢复漏掉的梯级，真实或快速目标红；② 让新路径绕过原有 room/ruler/crossing 检查，负控必须红。每项 cp+SHA 恢复并复绿。若第一轮补丁只是拒因搬家，停止先侦察，不连续试参。

兼容矩阵：固定 CH343 离线 page replay + 既有 pinned 邻域；V3/V4 真机、真实容器、多板/CBB 未覆盖。只有编译/逐脚/视觉分别通过才可说该离线回放恢复，不外推任意电路。

## ⑤ 纪律与红线

零 git 写/移动/删除；禁 rm/unlink 和 git checkout/restore/worktree；不全量、不真机、不部署。pytest 独立 basetemp、命令 timeout、单进程。不得改输入/调参/删除墙凑候选，不把旧指纹重钉当修复，不用 agent-adjusted 冒充 automatic，不碰真实工程。两轮同拒无新证据即交接。

## ⑥ 预算与交卷格式

一个 coder，最多 40 步或 30 分钟（真实 CLI 计时如实记录）；不派下级。交卷 ≤2000字，含根因行与首堵墙、先红/修后候选数及 geometry、完整测试汇总、两项变异与 SHA 恢复、逐脚/P1–P4/渲染路径、未覆盖项。证据落 `evidence/617/`。无合法候选或缺视觉材料只能写「停止/未完成」，不得写完成。
