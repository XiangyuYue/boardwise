# 任务书：584 / W-P(CLI) — draw 输入与输出预检

## ① 前因后果

hole568 总表的 569-G-01/02/05/06 已复现：`draw compile --circuit` 非 UTF-8 裸 traceback；`--out` 指已有文件裸 `FileExistsError`；`--json` 父目录缺失/为目录以及 `draw plan --out` 父目录缺失裸栈，compile 在报错前已写出多份候选；`draw plan --out` 指目录却静默改成目录下的计划文件。原始矩阵在 `outputs/hole569/g/REPRO.md` 与 `matrix.md`。

本批只修 CLI 入口的预检和错误映射，目标：所有这类输入问题具名 exit 5、无 traceback、在任何候选文件生成前停止。`ChangePlan.dump` 自身的写文件合同留给下一批 shared，不在本批改动；本批可以用 CLI 预检覆盖其命令面。

## ② 当前树状态

HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合工作树含前批 566–583 与他人改动。`src/boardwise/cli.py` 当前 SHA-256 `82994bc726dfb944825dd0c1fce0edaa30fc89a5dd0f11ee283e397bf13d1666`（含 581 页框修复），必须保留所有 hunk。`src/boardwise/core/changeplan.py` 当前 `ffbd8f08df3a400fad6fe138d65ab652e5657fd8c3254e17b94abe8e725f21f1`，本批不碰。现有入口：`_draw_inputs` 约 11864，`_cmd_draw_compile` 12250，`_cmd_draw_plan` 12508，page compile/plan 约 15427/15697；`_write_draw_previews`/`_write_page_previews` 在实际编译后写候选。

## ③ 文件域与禁触清单

允许修改/新建：
- `src/boardwise/cli.py`（仅 draw 输入/输出预检、必要错误映射与调用点）
- `tests/test_584_draw_cli_outputs.py`（新建）
- `evidence/584/`、`.tmp_584/`、`.tmp_pt_584/`

禁止修改 `changeplan.py`、其他生产/测试、fixtures、前批证据和他人未提交改动；不 git 写、不删除、不跑全量、不接触 bridge/daemon/EDA。开工 cp 备份 cli.py 并记录 SHA-256；变异只能 cp+SHA 恢复，注意保持 CRLF 与前批 hunk。

## ④ 交付物与验收

1. 569G-01：`_draw_inputs` 将 circuit/presentation/profiles 的 UnicodeDecodeError 统一包装为 `_DrawInputError`，exit 5、无 traceback；已有坏 JSON/缺失文件话术不回归。
2. 569G-02：compile 的 `--out` 已存在且为文件时，在编译前具名拒绝；合法新目录/既有目录保持可用。
3. 569G-05：compile 与 page compile 的 `--json`，以及 plan 的 `--json`/`--out`，在编译/计划生成前检查：目标为目录、父目录不存在、父路径不是目录等情况具名 exit 5；不允许先写候选再报错。不要在本批依赖 ChangePlan.dump 来兜住 CLI 错误。
4. 569G-06：`draw plan --out` 已存在目录必须具名拒绝，不得静默拼入 `<dir>/afile.page.json`；合法文件路径保持原语义。compile 的目录语义与 plan 的文件语义在错误文案中说清。
5. 用真实 CLI/入口行为测试覆盖单模块与 page 两路至少各一组，断言 exit、stderr 无 Traceback、输出目录没有任何 `cand*` 半成品；合法输入的既有测试不变。测试缺父目录时不得反过来要求自动创建父目录，本批按 triage 的“具名拒绝”验收。
6. 先保存基线并运行新测试取得先红；修后运行：
   `.venv/Scripts/python.exe -m pytest tests/test_584_draw_cli_outputs.py tests/test_054_draw_cli.py tests/test_057_draw_page_cli.py tests/test_581_page_box.py -q --basetemp=.tmp_pt_584`
   另按影响补 `tests/test_draw_plan_saved_page.py`，记录完整汇总。
7. 至少两个因果变异（如删掉输出预检/恢复 UnicodeDecodeError 未捕）先红，cp+SHA 恢复；保存命令、汇总、半成品清单和差异到 `evidence/584/`。

兼容要求：正常 compile/plan 输出字段、候选几何、退出码不变；`--json -`/默认输出路径按现有合同处理；不改变 ChangePlan 的 shared loader。V3/V4、容器、多板/CBB、真机未覆盖。

## ⑤ 纪律与红线

只在既有 CLI 链加预检/错误映射，不新增第二套输出 writer，不改布局或计划内容，不通过自动建父目录/删除半成品掩盖问题，不删改宽断言、不 skip/xfail。探针单进程、命令带超时；不跑全量、不真机、不部署、不发布。若 page 入口与模块入口行为不同，必须分别测试，不能推断。

## ⑥ 预算与交卷格式

最多 40 步或 30 分钟。交卷 ≤2000 字，逐项报告 G-01/02/05/06、基线先红、修后命令完整汇总、两个变异及恢复 hash、合法路径兼容和未覆盖项；详细日志落 `evidence/584/`。有本批未解决红项不得写完成。
