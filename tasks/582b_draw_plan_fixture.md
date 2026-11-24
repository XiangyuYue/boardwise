# 任务书：582B — 更新 LayoutPlan 测试夹具身份

## ① 前因后果

582 按 hole568 的 569-E-04/E-05 将 `kind` 与整数 `planVersion` 改为载入必填。实现后 `tests/test_053a_specs.py` 的 `_layout()` 仍构造缺这两个键的旧夹具，导致 6 条既有测试在业务断言前被拒绝。失败已主代理复跑确认，全部首先报 `$.kind is missing`。这不是放宽新合同的理由；正确收口是让合法夹具写出生产文档本来就会写的身份字段。

## ② 当前树状态

HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合工作树保留所有前批改动。`layoutplan.py` 当前 SHA-256 `e362a4e9f17ab1614768ccc2cc91b3006836ba7a0f5bacb9eb290e70a6dfd83f`，`pagelayoutplan.py` 为 `4d3c903c611709d30736a61155d70fccbd94a98cbc4b07f00a029aa7b84ebd76`。582 指定组已 `221 passed, 1 skipped`；`tests/test_053a_specs.py` 当前 `6 failed, 45 passed`，仅有 `_layout()` 缺身份这一已知原因。

## ③ 文件域与禁触清单

允许修改 `tests/test_053a_specs.py` 的 `_layout()` payload（只加正确 `kind`/`planVersion` 及必要注释），并写 `evidence/582b/`、`.tmp_582b/`、`.tmp_pt_582b/`。禁止修改任何生产文件、其他测试、fixtures、前批证据；不 git、不删除、不跑全量、不接触 bridge/EDA。先 cp 备份并记录 SHA-256，变异恢复只用 cp+SHA。

## ④ 交付物与验收

- 在 `_layout()` 的基础 payload 加 `kind: boardwise-layout-plan` 与 `planVersion: 1`，不修改任何既有测试断言或测试语义。
- 运行：
  `.venv/Scripts/python.exe -m pytest tests/test_053a_specs.py tests/test_582_draw_plan_schema.py tests/test_145d_plan_vertices.py tests/test_draw_plan_saved_page.py tests/test_056_pagecompiler.py tests/test_054_drawapply.py -q --basetemp=.tmp_pt_582b`
  必须全绿（既有 skip 可保留并披露）。
- 做一个负控：临时把夹具 kind 改成 page 身份或移除 kind，必须只有身份相关预期发生变化；恢复后核对测试文件 SHA-256。不得通过放宽生产校验取得绿灯。

## ⑤ 纪律与红线

只补夹具身份，不批量改其他测试，不删改断言，不 skip/xfail，不碰生产，不跑全量、不真机、不 git、不删除。若还有其它失败，停止并逐项交证据，不自行扩域。

## ⑥ 预算与交卷格式

最多 15 步或 10 分钟。交卷带改前/改后 hash、指定命令完整汇总、负控读数、恢复 hash、证据路径和任何未解决项；未全绿不得写完成。
