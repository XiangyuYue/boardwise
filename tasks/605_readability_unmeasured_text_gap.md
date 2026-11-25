# 任务书：605 — 单旗标文字间距不可量时不得崩

## ① 前因后果

`outputs/hole570/a2/REPRO.md` 的 **570-A2-H1** 复现：`_min_text_gap` 声明不足两句返回 `UNMEASURED=-1.0`，但页面只有一个旗标时 `_text_boxes` 给出字形与自身名字两个盒；147b 的配对豁免把唯一一对跳过，`best` 保持 None，2789–2805 行最后 `assert best is not None` 崩掉整次 check。当前 76e0806 的 readability SHA 与挖洞时一致。

本批只修“所有配对均被合理豁免后返回不可量”，不处理同报告的跨岛导体识别，不改文字宽度、字体、盒位置、豁免规则或任何距离阈值。

## ② 当前树状态

- HEAD/origin `76e08060ded403793bc6fb0eb64b38f9e140c765`；前批生产改动全部保留。
- `src/boardwise/engines/readability.py` SHA-256 `0c42bca12766d05a98c417e53cc8f1f6f2bd4f19eafbfd14f6569127f9082ab0`。
- 原探针 `outputs/hole570/a2/probes/p1_gap_two_box.py` 可读；`_min_text_gap` 在 2784 行只挡 `len(boxes)<2`，2796 行跳过旗标自身 name，2805 行 assert。
- 工作树有他人 `core/circuitsemantics.py`、563 文档/测试与 `tasks/review-line.md`，禁触。开始 cp 备份 readability 到 `.tmp_605/backup/` 并记 hash。

## ③ 文件域与禁触清单

允许修改/新建仅：
- `src/boardwise/engines/readability.py`（仅 `_min_text_gap` 的 None 出口及必要局部注释）
- `tests/test_605_unmeasured_text_gap.py`（新）
- 本任务书、`.tmp_605/`、`.tmp_pt_605/`、`evidence/605/`

禁止：`derive_netlist`、`_cross_module_wires`、其它 readability 谓词、textmetrics、drawcompiler、shared/CLI/connector/DSH、fixtures 和他人文件。不得删旗标配对豁免、改容差或把指标伪造成 0；不改既有测试来凑绿。

## ④ 交付物与验收

先新增并运行回归，单旗标两盒用例必须红（基线为 AssertionError，不允许用 pytest.raises 把它写成合法控制）：

1. 直接复用原探针的两个盒：旗标字形 `powerSymbols[0]` 与 `powerSymbols[0] name`，调用 `_min_text_gap` 必须返回 `(UNMEASURED, reasons)`，reasons 非空且说明只有一句/无可测间距，不抛异常。
2. 0 盒、1 盒保持既有 UNMEASURED；加入一个独立文字盒后仍返回真实最近间距，豁免只作用于旗标自身配对，不能把该盒与其它文字的测量一起跳过。
3. 两个普通器件文字仍返回正常 gap；touching/overlap 计数语义不变。
4. 至少一个通过真实 `_text_boxes` 得到的单旗标盒集进入 `_min_text_gap`，证明不是只在手工名字上有效；若构造需要 profile，使用现有测试 helper，不改 fixtures。

最小实现：`best is None` 时走与 `<2` 盒相同常量 UNMEASURED 的独立、明确理由出口，移除 assert；不要提前禁用 annotations，也不要复制一套盒过滤。

修后运行新测试与 `tests/test_053b_readability.py`，再按实际涉及补 147b/文本邻域测试与 owner/layer；命令带独立 `.tmp_pt_605/...` basetemp，保存完整汇总。

两项变异：① 恢复 `assert best is not None`；② 把 None 出口返回 0.0。每项新测试必须红，cp 恢复 SHA-256 一致后复绿。兼容矩阵：仅 LayoutPlan 文本软指标，无几何/电气语义变化；真实宿主、V3/V4、多板/CBB 未覆盖。negative control 为真实可测页数值与原因不变，UNMEASURED 不冒充 0 间距。无新图交付。

## ⑤ 纪律与红线

零 git 写/移动/删除；不全量、不真机、不部署。禁 rm/unlink、禁 git checkout/restore；变异只能 cp+SHA。不得改布局或盒生成来避开 None，不新增第二套文本度量，不跑其它算法批，不放宽测试。命令 timeout、探针单进程。

## ⑥ 预算与交卷格式

一个 coder，最多 35 步或 25 分钟；不派下级。交卷 ≤1500 字，含先红原文、修后完整测试汇总、两项变异与 SHA 恢复、真实盒集读数和未覆盖项。证据落 `evidence/605/`；缺任一项只能写「停止/未完成」。
