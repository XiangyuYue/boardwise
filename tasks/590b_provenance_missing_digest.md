# 任务书：590B / W-R1 — 省略几何摘要不得绕过封签

## ① 前因后果

590 已为 automatic LayoutPlan/PageLayoutPlan 加 route 与 provenanceSha256，原 D-1 手改+只重算 geometrySha256 已被拒。但主代理审查发现 `_check_seal` 在 `geometrySha256` 缺失时直接 return。实测用 590 的 `_resealed_plan_doc()` / `_resealed_page_doc()` 手改后删除 `geometrySha256`，两个类型都以 `automatic` 接受。这绕过了 D-1 的核心目标，必须先收口再做 D4/D6。

正确合同：geometrySha256 是可选的派生展示字段，但 provenanceSha256 是对当前几何的承诺。只要文档带 automatic 封签，就必须始终与 loader 从当前几何重算的值一致，不能取决于派生几何摘要是否写出。合法 automatic 文档即使省略 geometrySha256，只要封签正确仍应可读。

## ② 当前树状态

HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合工作树含所有前批改动。当前 hash：`layoutplan.py=556ce69ab1e6f1d524dc32f4c660911c492902b9a793f454b70b12662a5c0c6f`，`pagelayoutplan.py=4ece4bf48681bda45c37190b2a0fb35751fbb992c07b9307e8b6210f104b098d`，`cli.py=16a2871d…`（本批不改）。590 指定组主代理已 `294 passed, 1 skipped`。`tests/test_590_plan_provenance.py` 已含 D1 正例，但缺“删除几何摘要”的负例。

## ③ 文件域与禁触清单

允许修改两个生产文件的 `_check_seal` 及注释、`tests/test_590_plan_provenance.py`（新增两类边界用例）、`docs/draw.md`（仅若含“仅在 geometrySha256 在场才校验”的旧说明），以及 `evidence/590b/`、`.tmp_590b/`、`.tmp_pt_590b/`。禁止其他生产/测试、cli、ChangePlan、fixtures、前批证据；不 git、不删除、不跑全量、不接触 bridge/EDA。先 cp 备份并记录 hash，变异只能 cp+SHA 恢复。

## ④ 交付物与验收

- 删除两个 `_check_seal` 中“geometrySha256 不在就 return”的跳过路径；automatic 文档有封签时始终与当前几何重算比较。保留旧缺 route 文档、非 automatic route 与显式剥掉封签的既有规则。
- 新增 LayoutPlan 与 PageLayoutPlan 两测试：手改后删除 geometrySha256 必须因 provenance 陈旧拒绝；另测未改几何、只删除 geometrySha256 且封签正确仍可 load，证明没有把派生展示键变成必填。
- 修后运行：`tests/test_590_plan_provenance.py tests/test_582_draw_plan_schema.py tests/test_053a_specs.py tests/test_054_draw_cli.py tests/test_057_draw_page_cli.py -q --basetemp=.tmp_pt_590b`，完整汇总必须无本批红项。
- 至少一个主因果变异（恢复 missing-digest early return）必须让两个新负例红，cp+SHA 恢复；保存绕过前后原文到 `evidence/590b/`。

## ⑤ 纪律与红线

只修封签校验，不改 route/几何/digest算法，不把公开哈希说成作者签名，不删改宽断言，不 skip/xfail，不跑全量、不真机、不 git、不删除。若影响旧文档字节或合法剥字段流程，停止交证据，不擅自扩域。

## ⑥ 预算与交卷格式

最多 15 步或 10 分钟。交卷带两类绕过原文、修后汇总、变异与恢复 hash、合法省略摘要负控和证据路径；未全绿不得写完成。
