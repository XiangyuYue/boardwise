# 任务书：617E — agent-adjusted 的三列主信号阅读流

## ① 前因后果

617C 代码修复后 4 候选全部 `backflow>0`（首选 574.5）：原 `moduleColumns=2` 把主链 `usb_c→ch343→hdr` 在两行间折返，右侧大片空白。617D 已修 RXD 脱脚。主代理在内存中只把 `moduleColumns` 改为 3，固定其它输入与生产代码，真实 `compile_page` 得 **4 candidates，全部 `page_backflow_length=0`**。原点序列为 usb_c→ch343→hdr 同行，led 在第二行。

按绘制 SOP，这是 agent 应声明的阅读关系，不是 packer 缺陷。保留 `evidence/543d/effective.presentation.json` 原样，另建 `evidence/617e/effective.presentation.json` 作 agent-adjusted 输入；不得把原 automatic replay 的验收记到这份调整后的图上。

本批只修主阅读流与由其带来的 H1 朝向问题，不改生产代码、坐标、网名或器件功能。D+/D− 的物理镜像关系和 NC 标记不借机改写。

## ② 当前树状态

- HEAD/origin `76e08060ded403793bc6fb0eb64b38f9e140c765`；602–617D 改动保留。
- 617C 自动编译 4 候选，617D RXD 96→20；原始 `moduleColumns=2`。
- 三列对照 `.tmp_617e_columns3.log`：4/4 `backflow=0.0`；首选 origins `usb_c(165,700) / ch343(680,720) / hdr(980,770) / led(40,405)`。该对照是只读探针，不是最终交付。
- `pagecompiler.py` 当前 `b5ffebaf…`，drawcompiler `c5c6da70…`，本批不改。
- 他人 563/review-line/router/201f 与临时文件禁触。开始 cp 备份原 presentation 到 `.tmp_617e/backup/`，原文件只读不改。

## ③ 文件域与禁触清单

允许新建/修改仅：
- `evidence/617e/effective.presentation.json`（从 543d 原输入复制，仅 `moduleColumns: 3`）
- `tests/test_617e_reading_flow.py`（新）
- `evidence/617d/`、`evidence/617e/`（渲染与证据）
- 本任务书、`.tmp_617e/`、`.tmp_pt_617e/`

禁止：生产 Python/TS、543d 原输入、543K payload、contracts/fixtures/其它历史证据、CLI/DSH、他人文件。不得新增坐标/userLocks、修改 moduleOrder/parts/nets/sidePreferences/partTexts，不把三列调整称为 automatic 或原样 reference-replay。

## ④ 交付物与验收

### 语义声明（必须随交付写清）

1. 功能理由：USB 入口 → CH343 桥 → UART 排针是主信号链，LED 是独立指示灯；主链应连续向右，LED 在第二行。
2. 空间/信号关系：usb_c、ch343、hdr 同排依次排列，排针朝向 CH343；LED 留在下方，不与主链抢行。
3. 预期图形结果：主链 `page_backflow_length=0`，排针标签朝向 CH343，CC 成对件保持同向/等节距/各自本地 GND，RXD 保持 617D 的短 stub 和 C3 净空。

### 机器与视觉验收

1. 新输入除 `moduleColumns` 外与原 JSON 逐字段相同，diff 只能有这一行。真实 CLI `ok=True`、至少一个合法候选；4 候选全部 backflow=0，origin span 不再留下主链右侧空白。
2. 58 脚/17 网逐脚不变，RXD 保持短 stub 和 C3 位号 ≥2 净空；543K pinned、617C/D 测试保持。新测试必须断言 backflow、H1 朝向和三项语义预期，不只数 candidates。
3. 用新输入渲染到 `evidence/617e/`，主代理与独立复核看 USB/CC/CH343/HDR/LED 的功能、成对关系、标签净空和标题栏。若 D+/D−、H1 或其它项仍判废，只交局部改善，不写整页完成。
4. 至少两项输入变异：① moduleColumns 回 2，backflow 断言必须红；② 把 hdr 放到 ch343 左侧/破坏主链关系，朝向或 backflow 断言必须红。cp+SHA 恢复并复绿。生产变异不需要，本批零生产修改。
5. PROVENANCE 明确 `agent-adjusted`，包含原输入 SHA、调整输入 SHA、唯一字段差、真实 CLI 命令、候选 geometry、未覆盖项；不得写 original argv preserved。

## ⑤ 纪律与红线

零 git 写/移动/删除；禁 rm/unlink 和 git checkout/restore；不全量、不真机、不部署。pytest 独立 basetemp、单进程、命令 timeout。不得改生产 packer 来强行消 backflow，不隐藏标签/NC/文字，不调整页框/budget/GAP 来凑图，不改旧断言。两轮同拒无新证据即停。

## ⑥ 预算与交卷格式

一个 coder，最多 35 步或 25 分钟；不派下级。交卷 ≤1800字，含三项语义声明、唯一输入 diff、backflow/origins/逐脚/RXD 读数、完整测试汇总、两项变异与 SHA 恢复、渲染与剩余视觉问题。证据落 `evidence/617e/`。缺真实候选或视觉材料只能写「停止/未完成」。
