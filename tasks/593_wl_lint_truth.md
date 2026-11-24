# 任务书：593 / W-L — replay snapshot 与 skipped 结论诚实性

## ① 前因后果

hole568 的 569G-07 证明 `draw lint --snapshot` 对 `{}`、`{"primitives":"notalist"}`、字符串坐标、NaN 坐标都印 `0 error / 0 warn / 0 info` 并 exit 0。其 W-L 同时点名 565-S6-H3（`--bodies` 包装形被整份丢弃、坏长度/NaN/倒盒静默）与 565-S2-H1/H7（缺 netlist/bodies 时对应谓词没跑，终句仍 “reads clean”）。原始证据在 `outputs/hole569/g/REPRO.md`、`outputs/hole565/s6/REPRO.md` §H3、`outputs/hole565/s2/REPRO.md` §H1/H7。

本批闭合四个 lint 真相缺口，不改谓词算法、severity 或 live/bridge 路径。非法/没有可检几何的 replay 输入 exit 2；合法但缺检查材料的页面保留既有退出码语义，却在 stdout/JSON 明确 skipped，不能称 clean。正常、材料齐全的 clean 页面文案保持不变。

## ② 当前树状态

HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合工作树含所有前批改动。`cli.py` 当前含 581/584/589/590/591/592 全部 hunk；`_draw_lint_body_boxes` 在约 17192，`_cmd_draw_lint` 在约 17224；`drawlint.render_report` 只有 `text_readable` 一个披露通道。`Sheet.measured_bodies()` 可给出实际测量器件，`NETLIST_PREDICATES` 给出 L12 三项。现有 `test_163b` 的 clean 正例需要补 netlist/bodies 才能在新口径下继续称 clean，不能用放宽新规则维持旧断言。

## ③ 文件域与禁触清单

允许修改/新建：
- `src/boardwise/cli.py`（replay 形状校验、bodies 解析、skipped装配与JSON）
- `src/boardwise/engines/drawlint.py`（仅 render_report 的 skipped 通道，保留589新谓词）
- `tests/test_593_lint_truth.py`（新建）
- `tests/test_163b_gate_truth.py`（仅 clean 正例补齐材料/相应说明）
- `docs/draw.md`（仅 replay/skipped/bodies 口径）
- `evidence/593/`、`.tmp_593/`、`.tmp_pt_593/`

禁止修改其他生产/测试、fixtures、前批证据和他人未提交改动；不 git、不删除、不跑全量、不接触 bridge/daemon/EDA。开工 cp 备份目标文件并记录 SHA-256；变异只能 cp+SHA 恢复。

## ④ 交付物与验收

1. 569G-07：replay JSON 解析后验证根为 dict，components/wires/pins/netlabels 为 list，bboxes/meta 为 dict，图元 entry/state 形状正确；至少有一项可检几何（sheet框也可）。缺键、类型错、空 `{}`、没有任何图元、字符串/NaN/Inf 坐标、非法 bbox 都 exit 2、无 traceback、不得写“0 error clean”报告。允许现有合法奇数点 path fallback 与旧 snapshot 可选 drawing sections，不重写 Sheet 的坐标语义。
2. S6-H3：`_draw_lint_body_boxes` 正确解包 `{"bboxes":{…}}` 与裸映射、list四元组/minX对象；非 dict、长度≠4、缺键、非数/bool、NaN/Inf、倒盒具名 ValueError，CLI exit2。合法盒字节与坐标值不变，禁止静默丢成0盒。
3. S2-H1/H7：`render_report(..., skipped=...)` 加可选披露通道；CLI 将无 netlist 的 L12 三项和未完整测量 bodies 的 L11-part-overlap 加入 skipped。`bodies` 缺失或只覆盖部分 part 时，notes 明确 measured/total，JSON 增 `skipped` 和 `bodies{provided,count,measured,parts}`。有 findings 时也要附“未跑项/未完整检查”，无 findings 时不得再印 reads clean。
4. 正常 clean 正例必须有可读 render、netlist 和覆盖所有 part 的 bodies；此时原文案和 exit 不变。缺材料不强行改 exit 1（现有几何结果语义保留），但机器 JSON 能区分 skipped 与完整运行。
5. 新测试先在基线先红，覆盖四类坏 snapshot、包装/裸 bodies、所有坏盒、缺/部分 bodies、缺 netlist、材料齐全 clean。运行：
   `.venv/Scripts/python.exe -m pytest tests/test_593_lint_truth.py tests/test_163b_gate_truth.py tests/test_lock_p1_delivery_gates.py tests/test_111_draw_lint.py tests/test_111a_draw_lint_addendum.py tests/test_589_style_gates.py tests/test_054_draw_cli.py -q --basetemp=.tmp_pt_593`
   另跑 `tests/test_540c_contracts.py tests/test_540c_schema_semantics.py tests/test_doc_claims.py`，完整记录所有红绿。
6. 至少两个因果变异（恢复 bodies静默丢、去掉 skipped、去掉 snapshot形状校验）先红，cp+SHA恢复；保存原始CLI读数、JSON skipped/bodies、合法clean负控到 `evidence/593/`。

兼容要求：live 路径不调用新桥；旧合法 replay 几何/谓词/退出码不变；新增JSON字段加性，旧 schema 语义不破；V3/V4、容器、多板/CBB、真机未覆盖。

## ⑤ 纪律与红线

只在现有 CLI/render_report 链修，不新增第二套 snapshot parser，不把空模型当合法页面，不把 skipped 当 pass，不删改宽断言、不 skip/xfail。探针单进程、命令带超时；不跑全量、不真机、不部署、不发布。禁止用 git restore/checkout 恢复混合工作树。

## ⑥ 预算与交卷格式

最多 40 步或 30 分钟。交卷 ≤2000 字，逐项报告 569G-07/S6-H3/S2-H1/H7、基线先红、修后完整汇总、两个变异与恢复 hash、合法clean负控、JSON形状和未覆盖项；详细日志落 `evidence/593/`。有本批未解决红项不得写完成。
