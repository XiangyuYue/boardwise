# 任务书：589 / W-Q — S-08/S-11 硬闸与谓词文档一致

## ① 前因后果

用户指定修复 `outputs/hole568/TRIAGE.md` 的 32 条 reproduced。568-A 的原始报告 `outputs/hole568/a/REPRO.md` 证明：S-08 写明“100% 横平竖直，出现斜线即判废”，但 draw lint 对 45° 线仍 0 ERROR/exit 0（H1）；S-11 写明交叉上限为导线段数 2%，实现却是全页交叉 site >3 才一条 WARN，163 site 仍 exit 0（H2）；`docs/draw.md` 写“九条几何谓词”，实际 `PREDICATES` 有 17 个 id，引擎 docstring 也只列 11 个（H3）。S-17 单处标签 H4 仍是 suspect，不在本批实施。

本批只修 H1/H2/H3，不改布局算法、网表语义或其他 lint 规则。保留 L6 已有的逐簇 INFO/WARN 和 accepted-page 校准读数，新增 S-11 页级 ERROR，不把旧的 >3 site WARN 静默删掉。

## ② 当前树状态

HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合工作树含 566–588 与他人改动。`src/boardwise/engines/drawlint.py` 当前含前批文本/census等未提交改动，必须全部保留；`docs/draw.md`、`docs/schematic-style-spec.md`、`tests/test_doc_claims.py` 也有前批或既有内容，禁止整文件恢复。`run_lint` 当前依次调用 `check_crossings`，`PREDICATES` 在约 2336 行列 17 个 id；`Wire.segments` 在 `__post_init__` 已由 `_wire_segments` 构造，可复用做逐子边正交检查。现有 111/111a 测试含 accepted-page 校准。

## ③ 文件域与禁触清单

允许修改/新建：
- `src/boardwise/engines/drawlint.py`
- `docs/schematic-style-spec.md`（仅补充机器闸与 2% 统计口径的必要说明）
- `docs/draw.md`（仅 lint 谓词清单/数量与新增硬闸说明）
- `tests/test_589_style_gates.py`（新建）
- `tests/test_doc_claims.py`（仅新增/更新对应的文档-代码一致性钉）
- `evidence/589/`、`.tmp_589/`、`.tmp_pt_589/`

禁止修改其他生产/测试、fixtures、前批证据和他人未提交 hunk；不 git 写、不删除、不跑全量、不接触 bridge/EDA。开工 cp 备份所有将改文件并记录 SHA-256；变异只能 cp+SHA 恢复。

## ④ 交付物与验收

1. H1/S-08：在原 `run_lint` 链中新增逐子边正交检查，任一非零线段的 x、y 同时变化即 ERROR，finding 指明 wire、子边坐标和 S-08；水平、垂直、零长段不报错，正交折线不多报。使用明确的新 predicate id（建议 `L13-non-orthogonal`），加入 `PREDICATES`，不得只改文档。
2. H2/S-11：在 `check_crossings` 以当前实际参与检查的导线段数为分母，统计 distinct crossing sites（沿用现有 pair+cluster 去重口径），当 `cluster_count > 0.02 * segment_count` 时新增页级 ERROR，message 同时给出 sites、segments、2% 阈值（含小数）与实际比例。零导线/零交叉不产生除法或假红。保留原 `L6_PAGE_WARN` 的 >3 site WARN 及 cluster WARN/INFO；同一超限可有一条独立 S-11 ERROR，不能把旧 WARN 升级为代替品。使用明确 id（建议 `L13-crossing-budget`），加入 `PREDICATES`。
3. H3：更新 `docs/draw.md` 的 lint 清单与 `drawlint.py` 顶部谓词表，完整列出实际所有 id（含新两条），解释几何与 netlist-only 三组，不再写九/十一。`PREDICATES` 是机器可读源，新增测试验证文档列出的 id 集合与 `PREDICATES` 完全一致，并验证 S-08/S-11 文本与 ERROR 级别一致。
4. 新行为测试至少包括：45° 单线 ERROR、水平/垂直/零长负控、多段折线只报斜子边；交叉超 2% ERROR 的分子/分母读数、恰好不超阈值的负控、现有 >3 site WARN 仍在；PREDICATES 与文档 id 对齐。CLI 层若已有统一 ERROR→exit1，补一条真实 replay/入口断言，不接触 bridge。
5. 先保存基线并运行新测试取得先红；修后运行：
   `.venv/Scripts/python.exe -m pytest tests/test_589_style_gates.py tests/test_111_draw_lint.py tests/test_111a_draw_lint_addendum.py tests/test_163b_gate_truth.py tests/test_168_severity_arch.py tests/test_doc_claims.py -q --basetemp=.tmp_pt_589`
   另按影响补 `tests/test_054_draw_cli.py` 或 lint replay 邻居，记录完整汇总和 accepted-page 的任何新红，不能用“旧校准”掩盖。
6. 至少两个因果变异（去掉正交检查、去掉2% ERROR或改回固定3 WARN、文档id删一项）先红，cp+SHA 恢复；保存原始命令、完整汇总、finding原文和文档diff到 `evidence/589/`。

兼容要求：现有 L1–L12 id 与局部 finding 语义不变；accepted-page 若本身超 S-11，必须如实披露为规格与样本冲突并停止交证据，不得调 2% 或拆岛凑绿。V3/V4、容器、多板/CBB、真机未覆盖。

## ⑤ 纪律与红线

只在原 lint 链添加通用谓词，不新增第二套 checker，不改跨岛/分岛规格，不把 S-17 suspect 实施成新规则，不删改宽既有断言，不 skip/xfail。探针单进程、命令带超时；不跑全量、不真机、不部署、不发布。禁止用 git restore/checkout 恢复混合工作树。

## ⑥ 预算与交卷格式

最多 40 步或 30 分钟。交卷 ≤2000 字，逐项报告 H1/H2/H3、基线先红、修后命令完整汇总、两个变异与恢复 hash、accepted-page影响、文档id集合和未覆盖项；详细日志落 `evidence/589/`。有本批未解决红项不得写完成。
