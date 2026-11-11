# 038R1：FOC 锐角对象与带线网计数证据修正

日期：2026-11-11。审查线单文件域小批，只修 `pcb-foc-track-corners` / `pcb-foc-gate-trace-width` 的事实读数，不改严重度、规则阈值、网表或布局。

## 已核实问题

1. `rules/pcb/foc.py` 的 `_whole_board` 先 `angles=sorted(...)`，却用排序后下标索引原 `corners`。因此 sharpest 实际取了原列表第一项，正文和直方图/逐脚记录可能互相矛盾。应直接 `min(corners, key=lambda c: c.angle_deg)`，同角度保持原顺序，不复制或重排 corners。
2. `FocGateTraceWidth` 在「没有识别到 power-path 网」的 INFO 行里写 `nets carrying tracks on this board: len(board.net_names())`。`net_names()` 是所有有几何元素的网，不等于有走线的网；未布线网也被计入。应按 `board.tracks` 的非空 `track.net` 去重计数，证据文案与真实集合一致。

## 合同与边界

- 只改上述两个事实计算及其证据字符串；其他 finding 数、severity、level、target、直方图和逐折弯输出不变。
- 锐角必须同时满足角度、网名、位置/轨迹对属于同一个 corner；不能取排序后的角度配原顺序的网。
- 带线网计数只认真实 tracks：同一网多段只算一次，无网名段不伪造成一个网名。文案改为明确的 `named nets with routed track segments`；不新增门限或通过结论。
- 普通 `.epro2/.eprj2/.eprj3` 模型合同不变，V3/V4、在线/离线、多板、普通器件/CBB 均不改变；本批仅离线 fake/现有公开夹具，不做真机。
- 既有 BoardGeometry.net_names() 含义保持不变，其他调用方不改；不能为了让本规则好看而全局改 net_names。

## 文件域

- `src/boardwise/rules/pcb/foc.py`：只改两处。
- `tests/test_133b_foc_rules.py`：新增/加强回归断言。
- 本任务书；日志/备份在 `.tmp_038r1/`，pytest 独立 `--basetemp=.tmp_pt_038r1`。

不改 shared parser、checkup/completion、BoardOffEdge、绘制线、bridge/Connector/DSH/Rust、package/version/TASKMAP；零 git 写、零删除、零真机。

## 验收

- 现有 R13 夹具重新计算 `expected=min(primitive,key=angle)`，断言 whole-board message 的角度和网名与 expected 完全一致；修复前必须能复现不一致，不能只断言包含 sharpest 字样。
- R11 的 existing no-power-path 行：期望计数由 tracks 的非空 net 去重得出，并证明它不同于 net_names 总数；再构造 tracks=[] 的内存模型，期望带线网为 0，而原网集合不必为空。
- 跑 `test_133b_foc_rules.py`、`test_133a_foc_primitives.py` 及必要的 FOC/report 邻域，独立 basetemp。
- 两处变异：① sharpest 退回原列表第一项；②带线网计数退回 net_names。对应测试均须红，cp+SHA-256 恢复并复绿，不用 git 恢复，不删备份。
- 一个 coder，最多 25 步或 20 分钟；主代理负责 diff 与独立复验。全量 pytest 由后续集成批串行运行。


## 主代理验收（2026-11-11）

- 主代理核心复跑 **62 passed**；coder 邻域 230、报告邻域 113。三个新回归对旧实现均红，修后全绿。
- 两处变异均 cp+SHA-256 恢复复绿，最终 foc.py SHA-256 `db7c6e696fc83f63756c86f00404d1a2e75d9d9eaf8df1ccb5b274b942b53934`。
- 证据 `outputs/review/038r1/ACCEPTANCE.md`。rulebody 与 differential 的集成同步见 `outputs/review/038r4/ACCEPTANCE.md`，最终 recursive=d2ff8ae4，direct 不变。
