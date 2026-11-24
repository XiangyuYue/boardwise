# 任务书：580 — 572-F SVG 预览五项缺陷

## ① 前因后果

用户要求解决新一批 triage 漏洞。`outputs/hole572/f/REPRO.md` 与 `holes.json` 已复现 F-1…F-5：空 plan 画布宽度为 0；无页框时 keep-out/frame/junction 被裁出画布；scale 只缩几何不缩视觉属性；不透明器件体遮住穿体导线/结点；反向 bbox 产生负 width。它们会让预览掩盖真实的可读性问题，不能作为交付视觉证据。572 总 TRIAGE 文件目前未落盘，本批只处理这份已交付 F 报告，不推测 G/H。

上一阶段 566–579 的修复仍在混合工作树中，未提交、未推送。本批不重开旧洞，不做全量测试，不接触真机。

## ② 当前树状态

开工 HEAD 为 `f5083286de06b1d1b698a91e51da18463be4f4de`，主分支有既有本地提交。`src/boardwise/engines/svgpreview.py` 当前 SHA-256 为 `abafff7bdd0646a360c71cd904f1f99419546a397a7dd25528b179c6206449f2`，与审计基线一致，工作树干净；`core/layoutplan.py`、`core/symbolprofile.py` 也不是本批改动。`cli.py`、`drawcompiler.py`、`drawapply.py`、Connector 及多份文档/测试有他人或前批未提交改动，不能恢复或覆盖。

已有预览测试：`tests/test_svgpreview_label_carrier.py`、`tests/test_svgpreview_native_text.py`、`tests/test_548p44_native_art_preview.py`。项目已有 pytest，允许新增本批回归测试。

## ③ 文件域与禁触清单

唯一允许修改/新建：
- `src/boardwise/engines/svgpreview.py`
- `tests/test_580_svgpreview.py`（新建）
- `.tmp_580/`、`.tmp_pt_580/`（探针/测试临时产物）
- `evidence/580/`（交卷证据）

禁止触碰：其他生产文件、其他测试、`tests/fixtures/`、`outputs/011e*`、`014_*`、`015b_*`、`016_*`、前批证据与混合工作树中的他人改动；不改 git，不 commit/add/checkout/restore/push，不删除任何文件或目录，不调用 bridge/daemon/EDA，不部署、不发布。不要用 git 恢复文件；如需保留基线，先 `cp` 到本批临时目录并记录 SHA-256。

## ④ 交付物与验收

1. 在原 `render_svg` 生产链内修复 F-1…F-5，不新增第二套渲染器，不改变既有公开入口的默认坐标/变换约定。
2. 每条至少一个真实回归断言，并保留正常 R1、旋转/镜像、native art、label carrier 的兼容控制：
   - F-1：空 plan 仍有正的 SVG width/height 和可见 caption，不能出现 `width="0"`。
   - F-2：`page_box=None` 时 keep-outs、frames、junctions 纳入内容范围且实际落在 viewBox 内；正常有页框路径不被扩大。
   - F-3：同一 plan 的 scale=1/2 中，几何、字体、描边、虚线、点半径保持同一视觉倍率，文字盒与字号比例不漂移；不要给已经带 scale transform 的 native art 重复缩放。
   - F-4：穿体导线和结点在 SVG 绘制顺序上不被不透明器件体隐藏，且正常层叠关系可读。
   - F-5：反向 text/label/keep-out 等 bbox 不得写出负 width/height；采用与现有 `_body_box` 一致的归一化，不能静默丢掉文字。
3. 先保存基线并运行新增测试，记录修复前预期失败原文；再实施最小修复，运行：
   `.venv/Scripts/python.exe -m pytest tests/test_580_svgpreview.py tests/test_svgpreview_label_carrier.py tests/test_svgpreview_native_text.py tests/test_548p44_native_art_preview.py -q --basetemp=.tmp_pt_580`
   必须取得完整汇总行。
4. 至少做两个有针对性的源码变异，证明对应回归先红；变异前后用 `cp` 备份/恢复并核对 SHA-256。保存修复前后关键 SVG 或结构化读数到 `evidence/580/`，交回实际命令、汇总行和差异。不要以单纯 import/compile 代替行为测试。

## ⑤ 纪律与红线

只做本批五项缺口；不调布局预算、页框、字体业务规则来凑过，不删改既有宽松断言，不 skip/xfail 遮缺口，不改测试以适应错误行为。探针单进程、命令带超时；不跑全量 pytest，不跑真机，不做任何 git 写或删除。发现报告与当前源码不一致时停止该子项并交证据，不自行扩项。

## ⑥ 预算与交卷格式

最多 40 个模型步骤或 30 分钟，先到先停。交卷不超过 2000 字，详细日志落 `evidence/580/`。必须逐项报告 F-1…F-5 状态、基线先红读数、修复后命令与原始汇总行、两个变异的先红/恢复哈希、兼容测试结果、未做项和证据路径。任何未解决红项或缺少行为验证都不得写“完成”。
