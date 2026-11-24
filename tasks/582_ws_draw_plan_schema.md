# 任务书：582 / W-S(draw) — LayoutPlan 与 PageLayoutPlan 载入合同

## ① 前因后果

用户指定修复 `outputs/hole568/TRIAGE.md` 的 32 条 reproduced。569-E 的原始报告 `outputs/hole569/e/REPRO.md` 证明：LayoutPlan/PageLayoutPlan 接受 NaN/Inf/1e400 并 dump 非标准 JSON（E-02）；非 UTF-8 load 泄漏 UnicodeDecodeError（E-03）；缺省/布尔/浮点 planVersion 被接受（E-04）；缺 kind 被接受（E-05）；真实 page load→dump 将 0 写成 0.0（E-06）；`_point` 接受第三分量并静默截断（E-07）。E-01/E-08 属于 ChangePlan，下一批 shared 单独处理，不在本批。

581 已在 shared `symbolprofile.check_box` 加有限性检查，必须保留；本批补齐两个 draw 文档自己的 `_number`/`_point`/身份/载入路径，不能重复造一套页面尺寸闸。前批 566–581 的混合工作树改动均须保留。

## ② 当前树状态

HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`。开工 hash（若实测不同先记录并以实际为基线）：
- `src/boardwise/core/layoutplan.py` `4fed2bcca99eb04365b888b2d3628078926163e6e22af081c1cf5ff2c745b2b9`
- `src/boardwise/core/pagelayoutplan.py` `41757223a02e299dd98c486b760465efe80475c26a4cb51cdedcbd29f2c1684a`
- `src/boardwise/core/symbolprofile.py` 已被 581 修为 `3d82e1a82dca69b9a255944c2d7ae43eab708cdad2b4b6edf4bc16a35b5075f0`，禁止恢复。
`changeplan.py`、`cli.py` 有其他批次改动，本批不碰。真实往返样本在 `outputs/054_drawcompile/`，审计探针在 `outputs/hole569/e/probes/`。

## ③ 文件域与禁触清单

允许修改/新建：
- `src/boardwise/core/layoutplan.py`
- `src/boardwise/core/pagelayoutplan.py`
- `tests/test_582_draw_plan_schema.py`（新建）
- `evidence/582/`、`.tmp_582/`、`.tmp_pt_582/`

禁止修改 `changeplan.py`、`cli.py`、`symbolprofile.py`、其他生产/测试、fixtures、前批证据及他人未提交改动。不做 git 写、不删除、不跑全量、不接触 bridge/EDA。开始先 cp 备份两个目标文件并记录 SHA-256；所有变异用 cp 恢复并核 hash，禁用 git checkout/restore。

## ④ 交付物与验收

逐项修复并加真实行为回归：
1. E-02：两个文档的所有数值入口（包括 part 坐标、bbox、module frame、port、pageBox 及嵌套点）拒绝 bool/非数/NaN/±Inf/溢出值，dump 不得产生 NaN/Infinity；保留正常整数/浮点数值语义。`check_box` 的 581 闸不能被绕开。
2. E-03：`load` 将 UnicodeDecodeError 包成各自 `LayoutPlanError`/`PageLayoutPlanError`，路径与 “not UTF-8” 清楚，CLI 所需错误类型不变；坏 JSON/目录/缺失文件话术不回归。
3. E-04/E-05：`planVersion` 必须显式存在且 `type(version) is int`、值等于 1；`kind` 必须存在且是对应文档身份，缺失与错误都具名拒绝。先核对现有真实产物均带这两个键；不改变 future version 的拒绝口径。
4. E-06：对 `outputs/054_drawcompile/cand1.page.json` 等真实 page 产物，load→dump 的数值序列化应与写者统一，至少固定原 `0`→`0.0` 的差异并保持二次往返稳定。优先最小的 reader/writer 规范化，不改几何、digest、verdict 或其他字段；若全仓既有合法文档需要保留浮点规范，改用写者统一 canonical 形态并提供前后证据，不能删断言凑过。
5. E-07：点必须恰好两个分量，第三分量具名拒绝；保留 list/tuple 正常形式。
6. 先红：最终新增测试在备份基线上运行，记录每个目标缺陷的真实失败，不接受只有 import/compile 绿。
7. 修后运行：
   `.venv/Scripts/python.exe -m pytest tests/test_582_draw_plan_schema.py tests/test_145d_plan_vertices.py tests/test_draw_plan_saved_page.py tests/test_056_pagecompiler.py tests/test_054_drawapply.py -q --basetemp=.tmp_pt_582`
   另按实际影响补 `tests/test_053b_drawcompiler.py` 的窄相关用例（不要全量）。记录完整汇总；若遇前批基线红逐名披露，不掩盖。
8. 至少两个有针对性的源码变异（如 `_number` 去有限性、版本/kind 校验放宽、point 恢复 `<2`）先红，cp+SHA 恢复。保存前后 JSON/结构化读数与命令到 `evidence/582/`。

兼容要求：现有合法 LayoutPlan/PageLayoutPlan、真实 page 的 source/digest/geometry、CLI 错误类型不变；旧文档若确实没有 kind/version 要在交卷逐项列出并说明依据，不得静默继续接受。V3/V4、容器、多板/CBB、真机未覆盖。

## ⑤ 纪律与红线

只在原 loader/dump 链内最小修改，不新增平行 schema/reader，不改变绘制算法，不用 allow_nan=True 掩盖非法输出，不删改宽既有断言，不 skip/xfail。探针单进程、命令带超时；不跑全量、不真机、不部署、不发布。若 E-06 需要改变公开 canonical 合同或影响大量既有钉，停止该子项并交最小证据，不擅自扩域。

## ⑥ 预算与交卷格式

最多 40 步或 30 分钟。交卷 ≤2000 字，逐项报告 E-02…E-07、基线先红原文、修后命令与完整汇总、变异先红/恢复 hash、真实 page 往返 diff、兼容与未覆盖项。详细日志落 `evidence/582/`；任何本批未解决红项不得写完成。
