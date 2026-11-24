# 任务书：599 — route 新字段的测试兼容收口

## ① 前因后果

596 全量除9条既有基线和1条层级违规外，还有6条与590 route/provenance相关的失败：`test_590_plan_provenance` 的旧样本目录已被新编译覆盖；`test_520j` 与 `test_p5_flag_group_scope`、`test_548p64_pre_group_lanes` 的整JSON hash仍钉旧字段集；`test_543c_service_channels` 需要单独差分确认是否仅来源字段变化。另 `commands/draw.py`/`cli.py`/`test_111_draw_lint.py` 仍有九/十一谓词旧文案，属H3扫尾。

本批只修测试合同与文案，不改几何或route实现。每个用例必须证明旧几何/旧字段未变，新增字段符合合同；不得简单删route/provenance假装旧输出，也不得盲改hash掩盖真实几何差。

## ② 当前树状态

HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合工作树含所有前批改动。590 后新直接构造的计划为 automatic 并带封签，旧缺route文档按 reference-replay 且字节不变。`outputs/054_drawcompile` 已被后续真实compile重写，因此590测试不能再假设该目录都是旧文档。9条既有失败（548j、548c6×2、543e、543h3b、543f2、548c4×2、548c5）不属于本批。

## ③ 文件域与禁触清单

允许修改：
- `tests/test_590_plan_provenance.py`（旧样本fixture确定性）
- `tests/test_520j_islands.py`（plan JSON字段分组/hash口径）
- `tests/test_p5_flag_group_scope.py`（同上）
- `tests/test_548p64_pre_group_lanes.py`（同上）
- `tests/test_543c_service_channels.py`（仅经差分证明后的来源字段处理）
- `src/boardwise/commands/draw.py`、`src/boardwise/cli.py`（仅lint帮助/docstring数量）
- `tests/test_111_draw_lint.py`（仅文件docstring数量）
- `tests/test_599_route_compat.py`（如需独立差分）
- `evidence/599/`、`.tmp_599/`、`.tmp_pt_599/`

禁止修改LayoutPlan/PageLayoutPlan/ChangePlan/drawcompiler/其他生产/测试、fixtures、前批证据；不git、不删除、不跑全量、不接触bridge/EDA。先cp备份并记录SHA-256，变异只能cp+SHA恢复。

## ④ 交付物与验收

1. 590 fixture改为从当前真实候选构造“pre-590形状”（去掉route/provenance）到独立tmp，再验证reference-replay与load→dump字节一致；不再依赖输出目录是否被重编译。保留新automatic与真正旧文档兼容证据。
2. 520j/p5/548p64：将整JSON比较拆成“旧字段/几何摘要不变 + route/provenance新增且正确”。可用原旧hash只比较去掉新字段的投影，但必须同时断言新字段存在、route automatic、封签与当前几何匹配，说明不是把新字段删了就算兼容。记录实际diff。
3. 543c：先打印with/without key的差分。若差异仅route/provenance，按上条处理；若几何不同，停止并交证据，不归为新字段兼容。若在老版本也失败，证明并列为基线，不改成假绿。
4. 将commands/draw.py、cli.py、test_111文件docstring中的九/十一旧数量改为以PREDICATES的19条及几何16+网表3分组为准；不改运行逻辑。
5. 运行：`tests/test_590_plan_provenance.py tests/test_520j_islands.py tests/test_p5_flag_group_scope.py tests/test_548p64_pre_group_lanes.py tests/test_543c_service_channels.py tests/test_111_draw_lint.py tests/test_111a_draw_lint_addendum.py tests/test_054_draw_cli.py tests/test_057_draw_page_cli.py tests/test_doc_claims.py -q --basetemp=.tmp_pt_599`，保存完整汇总。至少两个变异（盲删新字段、旧样本automatic、文档数量回退）先红，cp+SHA恢复，证据落`evidence/599/`。

## ⑤ 纪律与红线

只修测试与文案，不改生产几何/来源算法，不通过盲改hash/删字段掩盖真实差异，不skip/xfail，不跑全量、不真机、不git、不删除。若差分不能证明仅新字段，停止交证据。

## ⑥ 预算与交卷格式

最多35步或25分钟。交卷带逐文件diff理由、实际差异、指定命令完整汇总、两个变异与恢复hash、未解决项。
