# 任务书：580B — SVG 行为变更后的兼容钉收口

## ① 前因后果

前一批按 `tasks/580_svgpreview_holes.md` 修复 572-F 的空画布、缩放和图层缺陷后，生产行为与新增 11 条回归均通过，但既有测试仍有三处红：`tests/test_548p44_native_art_preview.py` 的 scale=2 快照/诊断点半径，以及 `tests/test_100_b1_quick_guards.py` 的空 plan caption 总高度。它们钉的是已被 572-F 明确判错的旧输出，不是应恢复的旧行为。原始证据在 `evidence/580/README.md` §4。用户随后指定 568 总 triage 为主任务；本批只收口已产生的新红，不扩展到 568。

## ② 当前树状态

HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合工作树保留前批所有未提交改动。`src/boardwise/engines/svgpreview.py` 当前 SHA-256 `79eed51c1d39ad5d92f02fc1fb9e4b5dd7d3158a7d5aec6612024acfe837bfa2`，新增 `tests/test_580_svgpreview.py` 已有 11 用例。前一批聚焦读数：本批域 19 passed；含 548p44 为 2 failed/38 passed；扩展影响面为 1 failed/258 passed/4 skipped。当前源码不得回滚到旧 SVG 行为；其他前批文件不是本批所有物。

## ③ 文件域与禁触清单

允许修改：
- `tests/test_548p44_native_art_preview.py`（仅三处与新 scale/图层输出直接相关的期望）
- `tests/test_100_b1_quick_guards.py`（仅空 plan/one-note 的新总高度及必要说明）
- `tests/test_580_svgpreview.py`（仅在需要补兼容语义时）
- `evidence/580b/`、`.tmp_580b/`、`.tmp_pt_580b/`

禁止修改生产源码、其他测试、fixtures、568 的任何文件、他人未提交改动；不 git 写、不删除、不跑全量、不接触 bridge/EDA。先 `cp` 备份将改文件并记录 SHA-256，禁用 git checkout/restore。

## ④ 交付物与验收

- 逐一证明三处旧断言为什么对应已修复的缺陷，再更新为语义等价的新期望：scale=2 的诊断点半径应为 4.4/3.2；默认快照须由当前生产输出重算并记录哈希；空 plan 画布 80 + caption 90 = 170。不得删除 native art 替换、无缺省材料回退、caption 行数/可读性等断言。
- 如果能用更稳健的语义断言替代整篇 hash，必须保留一个确定性快照钉，不能借修复之名删掉回归保护。
- 运行：
  `.venv/Scripts/python.exe -m pytest tests/test_580_svgpreview.py tests/test_svgpreview_label_carrier.py tests/test_svgpreview_native_text.py tests/test_548p44_native_art_preview.py tests/test_100_b1_quick_guards.py -q --basetemp=.tmp_pt_580b`
  必须全绿并保留完整汇总。
- 至少一个反向检查：把生产 `px()` 临时改回不缩放或恢复空兜底，相关测试必须红；随后 cp 恢复并核对生产 SHA-256。若改动测试导致变异仍全绿，停止并报告空转。

## ⑤ 纪律与红线

只改三处已点名的旧期望，不宽泛重写测试，不调生产参数凑过，不 skip/xfail，不掩盖其他红项。测试命令带 basetemp 和超时；不跑全量；不做 git、删除、部署、真机。交卷必须披露所有红绿，不得把“旧断言改绿”当生产行为独立证明。

## ⑥ 预算与交卷格式

最多 30 步或 20 分钟。交卷列出三处 diff 理由、实际命令与汇总原文、反向变异读数、恢复 SHA-256、证据路径和未做项；详细日志落 `evidence/580b/`。未全绿不得写完成。
