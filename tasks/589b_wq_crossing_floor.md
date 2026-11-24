# 任务书：589B / W-Q — S-11 小页交叉下限收口

## ① 前因后果

589 按 568A-H2 将 S-11 的 2% 直接实现为 ERROR，发现已人工验收的 P24 有 2 个 distinct crossing sites / 27 个实际导线段（7.41%），导致 `tests/test_111_draw_lint.py::test_accepted_pages_have_zero_error_and_warn` 新红。证据在 `evidence/589/P24_s11_conflict.txt` 与 `summary.md`。若不加下限，任何不足 100 段且有 1 处交叉的页面都会判废，和现有小页人工验收冲突；若给 P24 单独豁免又违反通用闸原则。

本批采用统一口径：页级 ERROR 的条件为 `cluster_count > max(L6_PAGE_WARN, 0.02 * segment_count)`（当前即同时超过 3 处和 2%）。原 2% 比例仍计算、报告并约束大页；旧 `L6-wire-crossing` 的 >3 site WARN 和逐簇 INFO/WARN 保留。P24 只是证明需要下限的证据，不是白名单。S-08 与 H3 已完成，本批不重构它们。

## ② 当前树状态

HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合工作树含 566–589 与他人改动。589 交付时：
- `src/boardwise/engines/drawlint.py` = `c3e98ba7c0521acf04607fd893431e338ad9cad4a5371ab206eefbfadef9aae5`
- `docs/draw.md` = `bf9007fcdc644a554a41209929d01a580a695e91e34fc34ff4e667336f105c6b`
- `docs/schematic-style-spec.md` = `35c09cb8d59f99f620f11ae8a3c564deb84eca3b673ad80bd575d8490a096a20`
- `tests/test_589_style_gates.py` = `e700af965b1cf4f0147f7f57f28cd8db3b51fdf267e1c93c30bfe75519c05f2c`
- `tests/test_doc_claims.py` = `75c975353315b70a2b629d07ffbe8056862c2e53fb15346475a044690db43816`
589 指定组为 `1 failed / 188 passed`，唯一红就是 P24；另有 543f2 前批基线红，不陪跑。

## ③ 文件域与禁触清单

允许修改：`src/boardwise/engines/drawlint.py`（仅 S-11 阈值和注释）、`docs/draw.md`、`docs/schematic-style-spec.md`（仅 S-11 口径）、`tests/test_589_style_gates.py`（更新冲突钉为通用边界钉）、`tests/test_doc_claims.py`（仅必要口径钉），以及 `evidence/589b/`、`.tmp_589b/`、`.tmp_pt_589b/`。禁止其他生产/测试、fixtures、前批证据和他人未提交改动；不 git、不删除、不跑全量、不接触 bridge/EDA。先 cp 备份并记录 SHA-256，变异只能 cp+SHA 恢复。

## ④ 交付物与验收

1. 将 S-11 ERROR 阈值改为 `max(L6_PAGE_WARN, 0.02 * segment_count)`，保留严格 `>`；message 必须同时披露 sites、segments、2% 计算值、实际采用的下限/阈值及比例，不能隐藏规则变化。零导线/零交叉保持静默。
2. 文档明确“同时超过 3 处和 2% 才 ERROR”，说明这是小页下限而非 P24 特例；旧 >3 WARN 继续存在。删除“2% 没有绝对下限/待裁”的过时描述，换成已落地的通用规则及 P24 实测。
3. 回归至少覆盖：
   - 3 site/102 段（2.94%，但不超过 3）不报 ERROR，证明下限；
   - 4 site/102 段（3.92%，同时超过）报 ERROR，message 读数正确；
   - 大页 3 site/102 段的原测试若需调整，必须保留一个同时超两项的强正例，不能删除 2% 因果覆盖；
   - P22/P23/P24 accepted 页不再有本谓词 ERROR，P24 仍钉 2/27 的实测读数；
   - 原 `L6-wire-crossing` >3 site WARN 与独立 ERROR 同时存在。
4. 修后运行 589 指定组：
   `.venv/Scripts/python.exe -m pytest tests/test_589_style_gates.py tests/test_111_draw_lint.py tests/test_111a_draw_lint_addendum.py tests/test_163b_gate_truth.py tests/test_168_severity_arch.py tests/test_doc_claims.py -q --basetemp=.tmp_pt_589b`
   以及 `tests/test_054_draw_cli.py tests/test_054_drawapply.py`。必须全绿（既有 skip 披露）。
5. 至少两个变异：去掉 `max` 下限退回纯 2% 时 P24/小页负控必须红；把阈值改成 `and` 错逻辑或删除大页 ERROR 时强正例必须红。cp+SHA 恢复，保存原始汇总和 finding 到 `evidence/589b/`。

## ⑤ 纪律与红线

只做 S-11 通用阈值收口，不给 P24 特判，不改 2% 常量，不拆岛、不删除旧 WARN、不改 S-08/H3，不skip/xfail，不跑全量、不真机、不git、不删除。若新口径与更多 accepted 页冲突，停止交证据，不继续扩大豁免。

## ⑥ 预算与交卷格式

最多 25 步或 20 分钟。交卷报告通用规则、P24/大小页读数、修后完整汇总、两个变异与恢复 hash、文档更新和未覆盖项；详细日志落 `evidence/589b/`。有本批未解决红项不得写完成。
