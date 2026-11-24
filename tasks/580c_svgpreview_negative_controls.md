# 任务书：580C — SVG 缩放置换负控收尾

## ① 前因后果

580/580B 已修复 572-F 并更新 scale=2 的旧快照与正期望，主代理复跑五文件 `56 passed`。实现者交卷指出 `tests/test_548p44_native_art_preview.py:124,143` 仍断言旧半径 `2.2/1.6` 不存在；新正确半径为 `4.4/3.2`，所以即使 native art 没有替换诊断点，这两条负向断言也会恒真。这是本批改动造成的测试覆盖回退，必须收口，不扩展到 568。

## ② 当前树状态

HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合工作树保留所有前批改动。生产 `src/boardwise/engines/svgpreview.py` SHA-256 `79eed51c1d39ad5d92f02fc1fb9e4b5dd7d3158a7d5aec6612024acfe837bfa2`；`tests/test_548p44_native_art_preview.py` 已由 580B 更新，五文件当前 `56 passed`。只需处理该测试文件的两个负控，不动生产。

## ③ 文件域与禁触清单

允许修改 `tests/test_548p44_native_art_preview.py` 中两处负向断言及必要说明，写 `evidence/580c/`、`.tmp_580c/`、`.tmp_pt_580c/`。禁止改任何生产文件、其他测试、fixtures、568 文件；不 git 写、不删除、不跑全量、不接触 bridge/EDA。先 cp 备份并记录 SHA-256，禁用 git restore/checkout。

## ④ 交付物与验收

把两处负控改为能识别当前正确诊断点的断言（优先结构性断言，或至少检查 `4.4/3.2` 而不是旧 `2.2/1.6`），保留原生 art 内容、导线、pin-name 等既有正向断言。运行：
`.venv/Scripts/python.exe -m pytest tests/test_548p44_native_art_preview.py tests/test_580_svgpreview.py -q --basetemp=.tmp_pt_580c`
必须全绿。再做一个反向变异：临时让生产缺失 native art 时仍保留诊断点，或将负控针对的正确半径改回旧值，证明新断言会红；cp 恢复并核对 SHA-256。交回前后读数和证据路径。

## ⑤ 纪律与红线

只改两处负控，不删除其他断言，不借改测试掩盖生产问题，不 skip/xfail，不跑全量，不 git、不删除、不真机。若发现生产行为与 580 目标不一致，停止交证据，不自行改生产。

## ⑥ 预算与交卷格式

最多 15 步或 10 分钟。交卷列出两处变更、测试原始汇总、反向变异与恢复哈希；详细日志落 `evidence/580c/`。未验证不得写完成。
