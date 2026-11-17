# 548H — 页级装箱复核（初稿前提已更正）

日期：2026-11-10。状态：**待并入 548 阶梯**（未并，阶梯文件正被并行会话修改）。
本文件已按 2026-11-10 晚的核查结果改写；初稿的错误前提见 §0。

## 0. 更正：二维装箱不是缺失能力

初稿写「缺的是页级二维装箱」，**错了**。核查结果：

| 事实 | 证据 |
| --- | --- |
| 装箱模块已存在 | `src/boardwise/engines/pagepacking.py`，`pack_frames`（docstring 自述 548D3X §30B） |
| 已接进页面编译 | `src/boardwise/engines/pagecompiler.py:2268` `packed = pagepacking.pack_frames(...)`；另见 `:2351–2353` 的 `STATUS_UNSAT/TRUNCATED/REJECTED` 映射 |
| 已有两本测试 | `tests/test_548d_page_packing.py`、`tests/test_548d_page_arrangement.py` |
| 该文件未跟踪 | `git status` 里不在已跟踪集合；属于工作树未提交堆 |

E3 那个 1689.25×259 是 **548C7A** 的读数（`evidence/548C7A/README.md:37`），早于 §30B。
所以不能拿它证明「现在还在排成一行」。

## 1. 本批要回答的问题（不是「怎么做装箱」）

1. 用现有 `pack_frames` 重跑八岛整页，返回 `status` 是 `packed` / `unsat` / `truncated` / `rejected`？
2. 若 `unsat`：给逐岛尺寸表 + 理论下界（各岛面积和 vs 可用区 1130×785）。`pagepacking` 的 docstring 明说 **unsat 只代表该模块离散候选空间无解**，不代表连续空间无解——必须把这两件事分开写。
3. 若 `truncated`：是 `max_nodes` 太小还是候选空间爆炸，给实际展开节点数。
4. 若 `packed`：为什么 548D 整页仍报 1694.75×1009——是没走这条路径（消费方没接），还是 frames 本身就这么大。
5. E3 三岛页用 `pack_frames` 重测一次，给出真实读数，替换 548C7A 那份过期数字。

## 2. 判据（全部实测，不许推断）

1. 只读复核优先：先用探针跑现有 `pack_frames`，不改生产。
2. 每个 `status` 都要有原文（含 `unsat`/`truncated` 的具体 code 与展开数），**不许只写「无候选」**。
3. 若要动代码，只允许改消费侧接线（frames 的构造、优先级、gap/grid 传入），**不许改 `pack_frames` 的判据、不许调 `max_nodes` 凑通过、不许缩字缩间距、不许改页框**。
4. 同一输入两次结果必须逐项相等。

## 3. 文件域

- 只读探针放 `.tmp_548H/`
- 若需改消费侧：`pagecompiler.py` 相关段落 + 新测试
- 禁止：改 `placement.py`、改 §34/§35 合同、改页框、改 `pagepacking.py` 的判据、真机、git 写

## 4. 证据

`evidence/548D/full-page/island-packing.md`：八岛逐岛尺寸表、`pack_frames` 的 status 原文、E3 新读数（含与 548C7A 旧读数对照）、两次调用一致性。

## 5. 验收

- 八岛整页的 `status` 有原文，不是转述
- E3 新读数有原文
- 旧 panel / seat-first 全册不变（S2 70 条 + 旧 seat-first 册）
- 完成只说明**装箱现状**，不宣称 548D 自动整页通过、不宣称视觉通过

## 6. 排期

**不绑定 0.6.2 发布**。实现类改动必须等当前并行会话的 service-seat 落地、`drawcompiler.py` 不再被写之后再开。
另注：`pagepacking.py` 未跟踪，GA 若要发，它和那 19932 行引擎改动是同一批未提交物，不能当已交付能力。

## 7. 实测状态补记（2026-11-13；只记读数，不重开 packer）

本文件的问题已由只读实测回答，**判据未改、`pack_frames` 未改、gap/页框/max_nodes 未调**：
`evidence/548D/full-page/island-packing-review.md`（探针 `.tmp_548H/`）。

| 问题（§1） | 实测读数 |
| --- | --- |
| ① 真实八岛整页 `status` | generation 0/1 均 **`unsat`**，同一句 detail；内部 `_search` 展开 **137 / 55** 节点 |
| ② 逐岛尺寸 + 理论下界 | mcu 743×604 + wifi 579×200：并排需 1367 宽、上下叠需 849 高，均超 1170×825；gap 必须 ≤21 才可能靠缩距进页 |
| ③ `truncated` | 两代都不是 truncated；`max_nodes=20000` 未触及 |
| ④ 1694.75×1009 是消费侧还是 frames | **frames 本身，且消费侧确实走了 compact**（compact 先跑先被拒，页面报的 4 个 grid 拒因是同一批框的货架排法） |
| ⑤ E3 三岛页 | **`packed`**，节点 **6**，占用 **750×425 / 750×515**；`compile_page` `ok=True`。**548C7A 的 1689.25×259 不得再引用为现状** |

- **报数缺口（只记录，未改）**：`pack_frames` 的 `unsat` 分支走 `_refuse(...)` 时未回填 `nodes`，
  公开返回值 `nodes=0`；真实展开数只能经内部 `_search` 读到。修它必须**单独一批、单文件、带负例**，
  不得同时动判据/gap/页框/`max_nodes`。
- **P1 不进这份页**：全页规格 `serviceLayout={"pinGap":30}` 没有 `localSeats`，`_seat_first_port_columns`
  不启用；frame 尺寸相对 2026-11-10 基线是**零位移**。强制注入 `localSeats` 后模块级就 6/8 `layout-unsat`，
  没有 frame 可比——不能拿它当 P1 反证。
- **结构性判断（进下一批合同）**：P1 生成可见短桩 + label 盒，只会让宿主岛框变大，不可能改善装箱；
  装箱瓶颈只能在「共享上拉/服务支路联合座位」这类**缩小或重排真实框**的设计里解决。
- **结论不变**：本文件只说明装箱现状，**不宣称 548D 自动整页通过、不宣称视觉通过、不重开 packer**。
  最新一轮的整页阻塞与已排除路线见 `evidence/548D/full-page/BLOCKED.md`（差 41.5 宽）。
