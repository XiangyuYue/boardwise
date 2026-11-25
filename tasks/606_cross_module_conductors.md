# 任务书：606 — 跨岛判定按真实导体而非单段端点

## ① 前因后果

`outputs/hole570/a2/REPRO.md` 的 **570-A2-H2** 实测：`_cross_module_wires` 只看单个 `LayoutSegment.points[0]/[-1]`。同一根 VIN 在岛间隙接点断成 `(90,50)→(150,50)` 与 `(150,50)→(210,50)` 两段后，cross 为空，mainPath 被误报 “no wire joins the two modules”。另一个用例把唯一跨岛段的 `segment.net` 置空，也报未连。

当前 readability 与挖洞时 SHA 相同。模块总说明已经明确“segment.net 是 decoration，不能当网表身份”，而 `_derive` 已按相同几何规则做 union-find。本批要复用同一连接事实，不另造连接语义。原探针 2c 只有空段和岛框，**没有任何可作为 VIN 的证据**，不能直接要求它返回 VIN；正确修复必须在真实 `check_page` 有 CircuitSpec + pins 时证明回落，在证据不足时仍不命名。

本批只修跨岛导体识别，不处理 A2-H1 文本出口（605），不改 mainPath 词表、岛框、布线或电气分区。

## ② 当前树状态

- HEAD/origin `76e08060ded403793bc6fb0eb64b38f9e140c765`；前批改动保留。
- `src/boardwise/engines/readability.py` 开工 SHA-256 `0c42bca12766d05a98c417e53cc8f1f6f2bd4f19eafbfd14f6569127f9082ab0`（若 605 已先落，以其实际修后 hash 为基线并保留该 hunk）。
- `_derive` 在 722–823 行已 union `seg:<index>`、pin、label、power symbol；`DerivedNetlist` 当前只公开 pin 分组/命名，未公开段分组。
- `check_page` 3273–3296 行构造 placed 后直接 `_cross_module_wires(plan,frames)`；`_check_main_paths` 与 `_check_shared_expressions` 消费同一 cross。
- 原探针 `outputs/hole570/a2/probes/p2_cross_island.py` 只读。他人 563/review-line 和临时文件禁触。开始 cp 备份 readability 到 `.tmp_606/backup/`。

## ③ 文件域与禁触清单

允许修改/新建仅：
- `src/boardwise/engines/readability.py`（派生段的加性事实、跨岛聚合与调用点、必要注释）
- `tests/test_606_cross_module_conductors.py`（新）
- 本任务书、`.tmp_606/`、`.tmp_pt_606/`、`evidence/606/`

禁止：layoutplan/pagelayoutplan schema、compiler/island packer/router、textmetrics、CLI/shared parser/connector/DSH、fixtures、既有测试及他人文件。不得改 `segment.net` 的原值、把跨岛段自动命名为 VIN、用距离/岛名猜连接，不新增第二套网表算法。605 若已改同文件必须保留其 None 出口。

## ④ 交付物与验收

### 合同与实现边界

1. 在既有 `_derive` 的 union-find 结果上**加性**暴露每个 segment 所属导体（segment indices）、该导体的 pins 与 labels/power symbols 网名；不得复制“顶点落在线段上即 T、单纯交叉不连接”的规则。公开 `derive_netlist` 的旧字段/值完全不变。
2. `_cross_module_wires` 以导体为单位取真正外端点：两段在间隙共享接点时，该接点不是外端；A/B 两端仍形成一条 cross。返回既有四元组形状，代表 index 确定性取导体最小 index；多外端/多岛组合不得悄悄只取第一个。
3. 网名优先级：导体上的 label/power symbol 证据；无此证据时可用成员 segment 一致的非空 `segment.net` 作兼容声明；有冲突不得任选一个。完整 `check_page` 还可在**派生导体的 pin 集与 CircuitSpec 某 net 的物理成员集精确一致**时回落该 net.id；子集、无 pin、身份不明仍留空，不得凭“跨两个岛”猜 VIN。
4. `check_page` 复用同一次 `_derive(plan, placed)` 并传 CircuitSpec，使空 segment.net 的真实 mainPath 能通过；`_check_shared_expressions` 与 `_page_metrics` 消费同一 cross，不出现 mainPath 已连而 shared/metrics 仍说未连。
5. 不改 `derive_netlist` 对 segment.net 的独立网表语义，不把跨网短接合法化；现有 netlist hard violations 仍负责拒绝错误连接。

### 先红回归

生产改动前运行，以下目标必须红（原 2c 的“无证据也返回 VIN”不得写成断言）：

- 原 2b：两段同 VIN 在 gap 接点相连，cross 含 `(0,"VIN","A","B")` 或代表 index 合同指定的等价项，mainPath wired 非空。
- 折线拆成 3 段、T 形外端、跨网交叉不共点：分别验证真实导体、所有外端与不误并；重叠岛框负例不扩大本批范围。
- 真实 `check_page`：两个模块各有一个器件/引脚，CircuitSpec 声明二者为 VIN，跨岛导体由两段组成且至少一段 `net=""`，mainPath 不再报未连；电气分区仍与 spec 一致。
- 反证：完全没有网名、label/power、CircuitSpec pin 证明的裸跨岛段不得返回 VIN；两个不同网在间隙只交叉不相接不得合并；pin 集只是某 CircuitSpec net 的真子集时不得借名。
- 旧 2a 单折线、无 mainPath 页和全部既有 page readability 行为不变。

### 测试与变异

修后跑新测试、`tests/test_053b_readability.py`、`tests/test_056_page_readability.py`（先 Glob 核实际名）、057/page 邻域、owner/layer；不跑全量。至少三项因果变异：① 恢复逐段首尾判定，2b 红；② 禁用物理导体/CircuitSpec 回落，真实空-net 用例红；③ 把“精确 pin 集”放宽为任意子集/无条件 VIN，反证红。每项 cp+SHA 恢复并复绿。

兼容矩阵：LayoutPlan/PageLayoutPlan 离线 page checker 与合成 pins；真实编译候选仅作邻域，不声称新图三关。V3/V4、真实容器、多板/CBB 未覆盖。negative control 为未知身份不猜、交叉不连、电气短路仍拒、旧四元组消费者不变。

## ⑤ 纪律与红线

零 git 写/移动/删除；不全量、不真机、不部署；禁 rm/unlink 和 git checkout/restore。pytest 独立 basetemp、命令 timeout、探针单进程。不得为了过原探针捏造网名、改输入岛框/电气规格或放宽 mainPath 检查；不修改旧断言凑绿，同一失败两轮无新证据即停。

## ⑥ 预算与交卷格式

一个 coder，最多 40 步或 30 分钟；不派下级。交卷 ≤2000字，含实现、先红/修后完整汇总、2b 与真实空-net 读数、三项变异及 SHA 恢复、未知身份反证、未覆盖项。证据落 `evidence/606/`。缺任一关键验收只能写「停止/未完成」。
