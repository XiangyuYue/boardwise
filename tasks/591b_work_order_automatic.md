# 任务书：591B / W-R2 — recompileWithLocks.automatic 消费

## ① 前因后果

591 已让 work order 的 schema/mode/status/designators/delta 在 bridge 前被校验，并把 agent-adjusted route 写入 ChangePlan。主代理交卷复核发现 D4 点名的另一个字段 `recompileWithLocks.automatic` 仍未被读取：替代路线可以在 work order 中写 `automatic:true`，下游照样按 agent-adjusted 人工提案消费。原 568-D4 因而还缺最后一条负控。

本批只补：存在 `recompileWithLocks` 时必须是对象且 `automatic is False`；true/缺失/非 bool/非对象均在任何 bridge 调用前 exit 5。字段为 false 时保持现有成功路径，不重实现 lock 编译。

## ② 当前树状态

HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合工作树保留所有前批改动。`cli.py` 当前 SHA-256 `57f51afabd548dbfbc4a77b35ae3203b26044f4ac6372a588c80e205d52de58c`，`_move_work_order` 在约 25916–26001 行；`tests/test_591_work_order.py` 已有早拒参数矩阵和 fake live 成功路径。591 主代理聚焦为 `330 passed`，CLI 合同一致。

## ③ 文件域与禁触清单

只允许修改 `src/boardwise/cli.py` 的 `_move_work_order` 校验和 `tests/test_591_work_order.py` 的新负例/负控，写 `evidence/591b/`、`.tmp_591b/`、`.tmp_pt_591b/`。禁止其他生产/测试、contracts、docs、fixtures、前批证据；不 git、不删除、不跑全量、不启动真实 daemon/EDA。先 cp 备份并记录 hash，变异只能 cp+SHA 恢复。

## ④ 交付物与验收

- `recompileWithLocks` 存在时必须是 dict，且 `automatic` 必须显式为 `False`；true、缺失、0/1、字符串、null、列表均具名拒绝，不能让“自动路线”混入人工计划。
- 新测试覆盖 true、缺字段、非 bool、非对象四种早拒，均 exit 5、无 traceback、`_open_cli` 未被调用；`automatic=False` 的 fake live 成功计划仍 route=agent-adjusted。
- 运行：`tests/test_591_work_order.py tests/test_agentadjusted.py tests/test_583_changeplan_schema.py tests/test_037_moveblock.py -q --basetemp=.tmp_pt_591b`，必须全绿。
- 做一个因果变异：去掉 automatic=false 检查，true 用例必须红且可能打开 bridge（用 `_no_bridge` 证明路径改变）；cp+SHA 恢复。保存原始汇总与恢复 hash 到 `evidence/591b/`。

## ⑤ 纪律与红线

只补来源校验，不改变 lock 生成、move-block、route、CLI 合同或其他字段，不删改宽断言，不 skip/xfail，不跑全量、不真机、不 git、不删除。若失败模式不同，交证据不扩域。

## ⑥ 预算与交卷格式

最多 12 步或 8 分钟。交卷带 true/false 读数、指定命令完整汇总、变异与恢复 hash、证据路径和未解决项。
