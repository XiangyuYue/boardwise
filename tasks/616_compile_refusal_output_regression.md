# 任务书：616 — F2-07 拒绝路径输出合同回归

## ① 前因后果

`outputs/hole570/f2/REPRO.md` 的 **570-F2-07** 在旧 HEAD 上复现：布局拒绝后写 `--json`，父目录不存在导致 FileNotFoundError 吞掉具名拒绝，没有 exit 5/result.json。报告建议自动 mkdir，但 76e0806 已包含 584 的新合同：所有 `--json` 在编译前检查，父目录不存在就具名 exit 5，不自动建目录、不生成候选；`--out` 是候选目录，允许新建。

本批任务是用真实 CLI 证明“编译本身也会拒绝”时输出预检仍优先、无 traceback/半成品，并保留合法父目录下原有拒绝 JSON。若当前测试全绿，不修改生产，不虚构新 bug；把它记为“旧洞已由 584 关闭，本批补拒绝×拒绝回归”。

## ② 当前树状态

- HEAD/origin `76e08060ded403793bc6fb0eb64b38f9e140c765`；前批全部保留。
- `src/boardwise/cli.py` 在 12639–12646 已先 `_draw_output_checks`，11903–11906 明确缺父目录拒绝，12689–12756 合法路径仍写 result 后 exit 5。
- `tests/test_584_draw_cli_outputs.py` 已有缺父目录正向输入预检，但没有显式叠加“布局也会拒绝”的用例；F2 原输入为 `blocklib/modules/circuits/sy8089_buck_3v3.circuit.json`、`blocklib/specs/sy8089_buck_3v3.presentation.json`、`blocklib/symbols/profiles.json`，page-box 0,0,420,300 可得 layout-unsat。
- 开始 cp 备份 cli.py 仅用于变异恢复，不要求生产 diff。他人 563/review-line/router/临时文件禁触。

## ③ 文件域与禁触清单

允许修改/新建仅：
- `tests/test_616_compile_refusal_outputs.py`（新）
- 本任务书、`.tmp_616/`、`.tmp_pt_616/`、`evidence/616/`
- `src/boardwise/cli.py` **仅限**真实 CLI 暴露尚未覆盖的回归时最小修复；当前证据预期不改

禁止：自动 mkdir、drawcompiler/layout、shared/connector/DSH、fixtures、584 既有断言和他人文件。不得把旧报告的“应写 result”置于 584 的“预检拒绝无产物”之上，不放宽 exit 5 或无 traceback 要求。

## ④ 交付物与验收

1. 真实 CLI 对 F2 三件输入和窄 page-box，传不存在的 `--json` 父目录及新 `--out`：必须 exit 5，stderr 指明 `--json`/父目录，不得 Traceback，不得创建 result.json，不得写 cand 半成品。可用 monkeypatch spy 补充证明编译函数没被调用，但不能替代真实 CLI。
2. 同输入、合法 `--json` 父目录：必须得到原 layout-unsat 的 exit 5、无 traceback，result.json 存在且 `ok=false`、failures 非空，证明没有吞掉编译拒绝。若当前页框的拒因变化，以实际结构化拒绝为准，不强行保留旧文案。
3. `tests/test_584_draw_cli_outputs.py` 全量文件作为邻域；合法 `--out` 新目录行为不变。先运行新测试：若全绿即当前基线证明，不能伪写“先红”。变异恢复旧无预检行为后新测试必须红。
4. 至少两项独立变异：① 跳过 `_draw_output_checks`；② 把缺父目录检查改成自动 mkdir。每项先 cp 备份，真实/聚焦测试必须红（第二项要断言“不创建父目录/无 result”，能抓住只验 exit 5 的空转），cp+SHA 恢复后复绿。不得长期保留变异。

兼容矩阵：单模块离线 CLI 拒绝路径与 584 邻域；page compile 可由既有 584 覆盖，不额外声称。真机/V3/V4、多板/CBB 未覆盖。negative control 为合法父目录拒绝 JSON 不变、无父目录不创建、无半成品。

## ⑤ 纪律与红线

零 git 写/移动/删除；禁 rm/unlink 和 git checkout/restore；不全量、不真机、不部署。pytest 独立 basetemp、命令 timeout、单进程。不得自动创建用户拼错目录，不修改原 hole570 证据，不把“测试本来绿”写成生产修复，不为了先红故意破坏后再称修 bug（变异只作覆盖证明）。

## ⑥ 预算与交卷格式

一个 coder，最多 30 步或 20 分钟；不派下级。交卷 ≤1500字，含当前基线真实命令/exit/stderr/文件清单、两项变异与 SHA 恢复、是否生产零改动、未覆盖项。证据落 `evidence/616/`。缺合法路径对照或有效变异只能写「停止/未完成」。
