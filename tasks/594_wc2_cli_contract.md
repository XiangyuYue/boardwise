# 任务书：594 / W-C2 — edit 无输入与 doc.open 风险合同

## ① 前因后果

hole568-B-01 实测 `boardwise edit plan` 无参时 `Path(None)` 产生 TypeError 裸栈，契约 `edit` 只声明 0/2/3/4/5；正确答案是 exit 2 的用法拒绝、无 traceback。568-B-02 证明 `docs/bridge.md` 把 `doc.open` 标为 read，而 `bridge/protocol.py` 与 `tests/test_action_catalogue.py` 都明确它是 write（会改变下一次写入落点）。本批只修这两项，不把 suspect 568-B-03/04 或 569G-08/09 扩进来。

## ② 当前树状态

HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合工作树含所有前批改动。`cli.py:_cmd_edit_plan` 在约 25839，现有分派在 value path 前未检查 args.file；`commands/draw.py` 的 `edit plan` 所有输入参数均 optional。`docs/bridge.md` §4 的 `doc.open` 行仍为 read。`cli.py` 已含591 work-order分派，必须先识别并保留。

## ③ 文件域与禁触清单

允许修改/新建：`src/boardwise/cli.py`（仅无输入闸）、`docs/bridge.md`（仅 doc.open risk）、`tests/test_594_cli_contract.py`（新建）、`tests/test_action_catalogue.py`（仅必要 doc.open文档一致性钉）、`evidence/594/`、`.tmp_594/`、`.tmp_pt_594/`。禁止其他生产/测试、contracts、fixtures、前批证据和他人未提交改动；不 git、不删除、不跑全量、不接触 bridge/EDA。先 cp 备份并记录 hash，变异只能 cp+SHA 恢复。

## ④ 交付物与验收

1. `edit plan` 无 `--file/--report/--insert/--move` 时，在 `_cmd_edit_plan_value` 前给出用法错误，exit 2、stderr 指明至少一种输入方式、无 Traceback、不得打开 bridge。已有 `--work-order` 无 `--move` 的 exit 5 语义不变，其它非法参数组合不因此改码。
2. `docs/bridge.md` 的 `doc.open` risk 改 write，新增测试验证文档表中该行与 `protocol.ACTIONS['doc.open'].risk` 一致，并与 doc.focus 同口径；其他 action 文档不变。
3. 新测试先在基线先红，修后运行：`tests/test_594_cli_contract.py tests/test_016_edit_cli.py tests/test_591_work_order.py tests/test_action_catalogue.py tests/test_doc_claims.py -q --basetemp=.tmp_pt_594`，再跑 `tests/test_540c_contracts.py` 和 `.venv/Scripts/python.exe -m tools.cli_contract`。CLI合同不应因只改错误处理而变化。
4. 至少两个变异（删无输入闸、文档read/write回退）先红，cp+SHA恢复，保存真实CLI输出、协议/文档对照到 `evidence/594/`。

## ⑤ 纪律与红线

只改无输入处理和文档风险，不重构edit、不新增命令/flag、不跑全量、不真机、不git、不删除、不skip/xfail。禁止用git restore/checkout恢复混合工作树。

## ⑥ 预算与交卷格式

最多20步或15分钟。交卷带无参实际读数、文档/协议对照、指定命令完整汇总、两个变异与恢复hash、未覆盖项。
