# 任务书：619 — pits 五条失效口径与可复核出处

## ① 前因后果

`outputs/hole570/e/REPRO.md` 的 E-01…E-05 涉及 `docs/pits.md`：坑 41/48/49/50/51 引用不存在的原始证据；坑 12 仍称已知实现偏差；坑 15 来源批次写错；坑 43 把每本旗标书都说成同一理想盒；坑 2 的 3.7 s/件未指向坑 53。

当前树与挖洞时有一点关键不同：76e0806 已包含 566-A-2 的六类 drawing sections 与前批提交。坑 15 不能再按旧建议写“仅工作树、HEAD 不含”，应写“566-A-2 起，当前版本已包含”，并机器核 connector 与 drawapply 同步。其余按当前真实文件与测试修正，不能把历史缺失件补造出来。

## ② 当前树状态

- HEAD/origin `76e08060ded403793bc6fb0eb64b38f9e140c765`；前批全部保留。
- `docs/pits.md` 开工 SHA-256 `17c70671fa4f950ac523b418d4220401431a74efb388412cb83b938df3ae1d31`。
- E-01 原死路径：`outputs/057_live/e1/plan2.txt`、`evidence/530f/report.md`、`evidence/532/532_page_a.svg`、`evidence/533/*`、`evidence/530a/report.md`；原报告已证 0 tracked 文件。现存机制可用 `LayoutPlan.evidence.grammarFindings`、`cli` 的 island keepout/sheet attrs 守卫、`tests/test_533_island_guard.py`、`tests/test_569_title_block.py` 与 connector 的 netflag 字段作当前出处。
- 坑 12 的 exit 3 有 `tests/test_018_cli_review.py::test_edit_apply_exits_3_when_the_daemon_is_unreachable`。
- 坑 15 当前 connector 已含 texts/buses/circles/rectangles/arcs/polygons，drawapply 已含 DRAWING_SECTIONS；来源是 566-A-2，不是 570。
- 坑 43 当前 flyback library GND `(-10.5,0,10.5,19.5)`、power `(-5.5,0,5.5,10.5)`；ch340/power_entry 仍 `(-6,0,6,18)`。
- 两份 boardwise skill 是同一份同步副本，坑 12 索引也需从“实现偏差”改“已修”；其它索引不扩写。开始 cp 备份 pits 与两份 SKILL 到 `.tmp_619/backup/`。他人 563/review-line/router/临时文件禁触。

## ③ 文件域与禁触清单

允许修改/新建仅：
- `docs/pits.md`（E-01…E-05 对应行）
- `.kimi-code/skills/boardwise/SKILL.md` 与 `.agents/skills/boardwise/SKILL.md`（仅坑 12 索引，保持逐字节相同）
- `tests/test_619_pits_current.py`（新）
- `tests/test_doc_claims.py` **仅当已有钉与新事实直接冲突，须逐条给出原因；默认不改**
- 本任务书、`.tmp_619/`、`.tmp_pt_619/`、`evidence/619/`

禁止：生产 Python/TS、contracts、fixtures、历史 evidence/outputs、boardwise-draw skill、他人文件。不得伪造/恢复历史证据，不得把未保留读数写成当前复测，不扩到 29 条真机 suspect。不得删改宽既有断言。

## ④ 交付物与验收

1. **E-01**：坑 41/48/49/50/51 删除五个死链接，逐条标“原始件未保留（raw not preserved）”，保留当时事实的历史归属，并给当前可核机制/测试入口；不得声称这些历史数值今天重新跑过。新测试断言死路径不再出现，现存代码/测试路径与关键符号存在。
2. **E-02**：坑 12 标“已修（018 §C.1）”，断 daemon edit apply exit 3，有真实测试名；不再写“已知实现偏差/读到 2 按连不上”。两份 skill 的坑 12 索引同步且逐字节一致。
3. **E-03**：坑 15 标“566-A-2 起，当前版本已含后六类”，不再写“570 加入/仅工作树”。测试实际解析 connector/drawapply 六键与守卫，不能只测文案。
4. **E-04**：坑 43 改成按书：ch340/power_entry 理想盒、flyback 逐族实测盒；保留原生 SVG 四姿态终检，不宣称所有书已校准。测试从三本 library 重算盒，而不是复制一句结论。
5. **E-05**：坑 2 写“3.7 s/件仅是当时队列状态，速率随队列见坑 53”，保留先回读不重发，不把 15 s 写成新固定值。
6. 新测试先对未改文档运行，五组目标应红；修后跑新测试、`tests/test_doc_claims.py` 与必要 workspace/doc 测试，保存完整汇总。至少两次“旧文案变异”（例如恢复坑 12 已知偏差、恢复坑 15 错误批次/死链接）必须让对应测试红，cp+SHA 恢复并复绿；两份 skill 恢复后 hash 一致。

兼容矩阵：仅文档与可机验声明；不重新验真机，29 条 suspect 未关闭。negative control 为历史结论不升格、原始件缺失明说、当前代码闸路径真实存在。

## ⑤ 纪律与红线

零 git 写/移动/删除；禁 rm/unlink 和 git checkout/restore；不全量、不真机、不部署。pytest 独立 basetemp、单进程、命令 timeout。不得为让 Path.exists 通过创建空 evidence 文件，不编造 argv/截图/读数，不改历史 outputs，不修改其它坑或发布状态。

## ⑥ 预算与交卷格式

一个 coder，最多 35 步或 25 分钟；不派下级。交卷 ≤1800字，含五项先红/修后汇总、死链接清零读数、六键与旗盒机验、两次变异及 SHA 恢复、未覆盖项。证据落 `evidence/619/`。缺任一机验只能写「停止/未完成」。
