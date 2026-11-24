# 任务书：591 / W-R2(shared) — work order 进入下游 ChangePlan

## ① 前因后果

hole568-D4 证明 `agentadjusted.py` 的 `mode/status/automatic` 没有生产消费者：`nextCommand` 只是 argv，`edit plan --move` 不读 work order，字段改成别的值也不会有任何下游反应。590 已给 LayoutPlan/PageLayoutPlan 和 compile JSON 加来源；本批只闭合“agent-adjusted work order → edit plan --move → ChangePlan”这一条链，不处理 D6/P44。

实现合同：`draw move-propose -o work.json` 的 `nextCommand` 增加 `--work-order work.json`；`edit plan --move --work-order work.json` 在打开 bridge 前读取并严格校验 schema、mode、designators、delta，再用现有 live planner 生成计划，并在 ChangePlan 顶层写 `route:"agent-adjusted"`。不带 work-order 的旧命令、旧计划字节、live guard 和退出码不变。ChangePlan 的 route 是可选来源字段，不是自动/人工质量证明。

## ② 当前树状态

HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合工作树含所有前批改动。`agentadjusted.py` 当前 `nextCommand` 在约 438–462 行只带 `--designators/--dx/--dy`；CLI `_cmd_draw_move_propose` 在约 17588，`edit plan --move` 在约 25899；`commands/draw.py` 的 edit plan 参数在约 1005–1030。`core/changeplan.py` 已经 583 闭合键、585 原子 dump，必须保留所有 hunk。`contracts/cli/v1.json` 是官方生成合同，新增 flag 必须用 `tools.cli_contract` 正确重生成，不能手改。

## ③ 文件域与禁触清单

允许修改/新建：
- `src/boardwise/engines/agentadjusted.py`（仅 nextCommand 在 CLI 已知 out_path 时的消费链接，若放在 cli 则本文件不改）
- `src/boardwise/cli.py`（move-propose 输出链接、edit move 的 work-order 读取/校验/传递与结果字段）
- `src/boardwise/commands/draw.py`（仅 edit plan `--work-order` 注册）
- `src/boardwise/core/changeplan.py`（可选 route 字段、闭合 reader、move_block_plan 可选传递）
- `contracts/cli/v1.json`（仅官方生成）
- `tests/test_591_work_order.py`（新建）
- `tests/test_agentadjusted.py`、`tests/test_583_changeplan_schema.py`（仅直接受新合同影响的断言）
- `docs/draw.md`（仅 work-order 消费说明）
- `evidence/591/`、`.tmp_591/`、`.tmp_pt_591/`

禁止修改 LayoutPlan/PageLayoutPlan、其他生产/测试、fixtures、前批证据和他人未提交改动；不 git、不删除、不跑全量、不启动/连接真实 daemon/EDA。开工 cp 备份所有目标文件并记录 hash；变异只能 cp+SHA 恢复。

## ④ 交付物与验收

1. CLI 保存 work order 后，`nextCommand` 能直接指向该文件（仅 `out_path` 存在时附加），引擎直接构造的默认 work order 字段/顺序保持 570/571 合同。
2. `--work-order` 读取必须是 dict 且 `schema=="boardwise.agent-adjusted-move/1"`、`mode=="agent-adjusted"`、`status=="proposed"`；位号按同一大写规则逐项一致，delta 与 `--dx/--dy` 数值一致；缺文件、坏 JSON/UTF-8、错 schema/mode/status、位号或 delta 不一致，必须在任何 bridge 调用前具名拒绝，exit 5 无 traceback。
3. 成功消费时把 `route="agent-adjusted"` 传给现有 `move_block_plan`，ChangePlan 顶层序列化 route；`--json` 结果也带 route 和 workOrder 路径。无 work-order 时不得新增 route 键或改变输出。
4. ChangePlan `_TOP_KEYS` 接受可选 route；reader 对缺失保持旧行为，对提供值限定 `automatic|reference-replay|agent-adjusted`，其他值具名拒绝；所有 kind 的旧文档、执行逻辑、583/585 兼容和 writer 字节不变。不要把 route 变成全计划默认字段。
5. 新测试覆盖：work order nextCommand、parser flag、全部早拒负例、fake live 成功计划 route、无 work-order 不变、ChangePlan roundtrip/非法 route。成功路径不得连接真实 daemon，可复用现有 fake client/geometry。
6. 先红后修，运行：
   `.venv/Scripts/python.exe -m pytest tests/test_591_work_order.py tests/test_agentadjusted.py tests/test_583_changeplan_schema.py tests/test_585_changeplan_dump.py tests/test_037_moveblock.py tests/test_016_edit_cli.py -q --basetemp=.tmp_pt_591`
   再跑 `tests/test_owner_rules.py tests/test_dsh_plugin_sync.py tests/test_doc_claims.py`、583 的 172 旧文档等价探针，以及 `.venv/Scripts/python.exe -m tools.cli_contract`。完整记录汇总。
7. 至少两个因果变异（不读/不校验 work-order、成功计划不传 route、旧文档被强加 route）先红，cp+SHA 恢复；保存成功计划、早拒无桥证据、旧文档 diff 和 CLI 合同结果到 `evidence/591/`。

shared 兼容矩阵：agent work-order 与 live move-block 两个消费者；review/edit 其他 kind 和 draw-module 旧计划不变；无 route 旧文档字节不变；V3/V4、容器、多板/CBB、真实 bridge/EDA 未覆盖，不声称。DSH 不新增工具，因为这里只扩展现有 CLI edit 参数，不增加新命令能力面；最终说明是否需 DSH 跟进。

## ⑤ 纪律与红线

只在现有 work-order/move-block/ChangePlan 链修，不新增第二套 planner 或签名系统，不绕过 live guard，不把 mode 当质量证明，不删改宽断言、不 skip/xfail。探针单进程、命令带超时；不跑全量、不真机、不部署、不发布。禁止用 git restore/checkout 恢复混合工作树。

## ⑥ 预算与交卷格式

最多 40 步或 30 分钟。交卷 ≤1800 字，报告 D4、基线先红、修后完整汇总、两个变异与恢复 hash、两个消费者与旧文档兼容、CLI 合同、未覆盖项；详细日志落 `evidence/591/`。有本批未解决红项不得写完成。
