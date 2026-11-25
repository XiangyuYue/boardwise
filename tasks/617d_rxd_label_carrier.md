# 任务书：617D — 修复 RXD 脱脚与 C3 位号挤占

## ① 前因后果

617C 恢复了 4 个编译候选，但独立视觉复核判废，最明确的单点缺陷是：`evidence/617c/render/cand1.page.json` 中 U1.3/RXD 的锚点 `(640,740)`，文字盒却为 `(532,735.5)-(556,744.5)`；与 C3 位号盒 `(557,732)-(572,742)` 横向仅 1 单位间隙。TXD 同排脚文字却贴近引脚，RXD 读者会误以为属于 C3。该问题不是编译/电气错误，是当前 native label 与 C3 的占位/避让失败。

本批只修这个缺口，不同时处理 D+/D−、H1 阶梯、页面 backflow 或 NC 样式。不能简单把“更严格拒绝”当修复；目标是至少保留 617C 的合法候选，并让 RXD 贴近自己的载体且与 C3 位号保持规格要求的清晰间隔，且 netlist 不变。若必须改模块排布，复用既有 seat/label 搜索，不新造 builder。

## ② 当前树状态

- HEAD/origin `76e08060ded403793bc6fb0eb64b38f9e140c765`；602–619 与 617C 改动保留，drawcompiler SHA `c5c6da702f9c1c83eaab665705c4a6a27e43bbb098c7496fabe6326a415f5b11`。
- 617C 的 4 个候选中，U1.3/RXD 的上述脱脚是结构性事实，不是图片缩放造成；独立审查给出 C3 位号 `(557,732)-(572,742)` 与 1 单位间隙。
- `pagecompiler._reseat_native_labels` 在 3019–3088 允许 anchor 同行/同列的任意水平 stub；`_native_label_seat` 在 5278 起选择固定梯级。`LayoutLabel.x/y` 是载体，`bbox` 是文字位置，当前 `textMode=native`。
- 真实 circuit 的 U1.3 是 RXD；不得改网名、引脚、partTexts、规格、页框或 NC。不得删除 C3 文字、隐藏 RXD 或把其它候选的简单平移当通用修复。
- 独立视觉 REJECT 的其他项（D+/D−、H1、backflow）不属于本批，需保留披露。开始先 cp 备份实际要改的生产文件到 `.tmp_617d/backup/`。

## ③ 文件域与禁触清单

优先唯一文件域：
- `src/boardwise/engines/pagecompiler.py`（原生标签座/重排与注释）
- `tests/test_617d_rxd_label_carrier.py`（新）
- 本任务书、`.tmp_617d/`、`.tmp_pt_617d/`、`evidence/617d/`

若证据明确根因只在 drawcompiler 的既有服务座位选择，可在开工报告先写清因果行后改为 `src/boardwise/engines/drawcompiler.py` 单文件，**不得两文件都改**。禁止：placement/router/readability/textmetrics、规格/library/CLI/shared/connector/DSH、fixtures、旧断言及他人文件。不得新增第二套标签/服务布局器，不调大页框/stubMin/GAP/预算来掩盖，不改 P44 其它问题。

## ④ 交付物与验收

### 先定位与先红

1. 捕获 RXD 的 `_native_label_seat` 所有梯级、实际占用盒和拒绝原因，说明为什么近端座位不可用、C3 位号为什么没被正确避让。若 614–638 这类近端盒确实可用，定位是哪张表/规则把它错误过滤；若被实体/导线真实挡住，定位既有服务座位应如何先让出通道，不能只改文案。
2. 新回归先红：直接读当前编译产物的 RXD，要求文字盒贴近 anchor 的合法载体（优先短直 stub，且不得比修前更远）并与 C3 位号无接触/无连续墨迹。按 `docs/schematic-style-spec.md` S-21 的至少 2 单位净空检查，不能只满足“不重叠”。测量需同时含 `bbox` 与 anchor，不能只读 `x/y` 就判贴脚。
3. 真实 CLI 修后仍需 `ok=True`、至少一个合法候选；候选的 `RXD` 文字必须在自己的短 stub 上，C3 位号不挤占，逐脚 58/58 与 17 网语义不变。修前/修后给出 anchor、box、stub、C3 位号间隙及最小其它文字间隙。

### 实现与负控

- 复用 `_native_label_seat`、既有占用盒/服务座位/属性移动链，不手写 RXD 坐标或 part 特判。若需要让 C3 移动，必须在既有座位梯级里做因果重排，不能写死 C3 新位置；保留 C3 的去耦功能与 30 单位服务关系。
- 保留 543K pinned 7 passed、617C 新测试与 543D/543G/543I 邻域。不能通过删除 declared 行、隐藏标签或改 partTexts 让问题消失。
- 至少两项生产变异：① 恢复旧座位/避让，RXD 脱脚/压字回归；② 让新路径绕过文字净空或 netlist 检查，负控必须红。每项 cp+SHA 恢复并复绿。
- 渲染到 `evidence/617d/`，父级会亲看；独立视觉的其他判废项仍需另批，不能因 RXD 修好后写整页 ACCEPT。

## ⑤ 纪律与红线

零 git 写/移动/删除；禁 rm/unlink 和 git checkout/restore；不全量、不真机、不部署。pytest 独立 basetemp、单进程、命令 timeout。不得修改输入/调参/隐藏文字/拉更长 stub 或让页面 0 候选冒充修复，不新增第二套布局器。连续两轮同拒无新证据即停。

## ⑥ 预算与交卷格式

一个 coder，最多 40 步或 30 分钟；不派下级。交卷 ≤2000字，含梯级与堵墙、先红/修后 anchor+box+stub+间隙、真实候选/逐脚读数、两项变异与 SHA 恢复、测试汇总、渲染和剩余视觉问题。证据落 `evidence/617d/`。缺合法候选或视觉材料只能写「停止/未完成」。
