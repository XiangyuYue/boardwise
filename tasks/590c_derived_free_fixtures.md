# 任务书：590C — 让 582 派生字段夹具与新来源合同一致

## ① 前因后果

590B 已让 automatic 封签始终与当前几何比较，堵住删除 geometrySha256 的绕过。`tests/test_582_draw_plan_schema.py::_layout_doc()` 的原意是“去掉派生声明，使坐标变异首先落在数值校验而不是摘要校验”，但它现在仍带 automatic route 和旧封签，导致 `test_normal_integers_and_floats_keep_their_semantics` 被来源闸先拒。`_page_doc()` 有同样的派生字段结构，也应一致处理，避免页/嵌套计划残留旧来源承诺。

本批只修测试夹具的来源声明：派生字段免费夹具同时去掉 verdict、geometrySha256、route、provenanceSha256；不改变任何数值测试、断言或生产校验。

## ② 当前树状态

HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合工作树保留所有前批改动。`layoutplan.py=73a55c4e…`、`pagelayoutplan.py=30eb3396…` 为 590B 修后状态。590B 指定组 `1 failed / 240 passed`，唯一红是 `_layout_doc` 的正常整数测试；将 `_layout_doc` 去掉 route/seal 的副本已证 `78 passed`。`_page_doc` 位于同文件 97–114 行，当前只剥 verdict/geometrySha256。

## ③ 文件域与禁触清单

只允许修改 `tests/test_582_draw_plan_schema.py` 的 `_layout_doc()`、`_page_doc()` 及注释，写 `evidence/590c/`、`.tmp_590c/`、`.tmp_pt_590c/`。禁止修改生产、其他测试、fixtures、前批证据；不 git、不删除、不跑全量、不接触 bridge/EDA。先 cp 备份并记录 SHA-256，恢复只能 cp+SHA。

## ④ 交付物与验收

- `_layout_doc()` 在已有 verdict/geometrySha256 剥离后再去掉 route/provenanceSha256，注释说明“无派生声明”在新合同下包含来源与封签。
- `_page_doc()` 对页顶层与嵌套 plan 同样去掉 route/provenanceSha256，避免两套口径。
- 运行：`tests/test_590_plan_provenance.py tests/test_582_draw_plan_schema.py tests/test_053a_specs.py tests/test_054_draw_cli.py tests/test_057_draw_page_cli.py -q --basetemp=.tmp_pt_590c`，必须全绿。
- 反向检查：只删 geometry 而保留 stale route/seal 的 590 负例仍必须拒；不得通过修改生产或删除该负例取得绿色。记录夹具 diff 和测试汇总到 `evidence/590c/`。

## ⑤ 纪律与红线

只改派生字段夹具，不修改任何测试断言、不放宽生产校验、不 skip/xfail，不跑全量、不真机、不 git、不删除。若还有其他失败，停止交证据，不扩域。

## ⑥ 预算与交卷格式

最多 12 步或 8 分钟。交卷带夹具 diff 理由、指定命令完整汇总、590 负例仍拒绝的证据、文件 SHA-256 和未解决项。
