# 038Z3：test V4 真实 NC 与 yAxisDirection 样本核查

日期：2026-11-16。前置：需要真实 `NO_CONNECT` 与缺省 `yAxisDirection` 证据；不能从合成夹具或空记录推断。

唯一样本目录 `E:/LC Project/test V4`，只读。逐文件、逐记录统计 `NO_CONNECT`、`yAxisDirection` 和坐标字段；必须区分 SCH_PAGE 本体与内嵌 SYMBOL/FOOTPRINT 库载荷，空 `|||` 记录和无坐标记录不能当缺省坐标样本。

完成条件：存在真实 NC 时，回查其 parent/pin 链和模型消费；存在缺省标记的实际坐标记录时，对拍转换前后坐标与在线读数。若不存在，交付计数证据并保持未覆盖，不修改工程制造样本，不使用其它工程替代。证据 `outputs/review/038z3/`，零生产改动、零 git 写、零删除。

## 实际结果（2026-11-16）

- 7 个 `.esch2` 共 2603 条 `yAxisDirection` 记录，取值全部 `up`；`NO_CONNECT` 记录为 **0**。
- 按 DOCHEAD 分段后，SCH_PAGE 本体内带坐标但缺省 `yAxisDirection` 的记录为 **0**。内嵌库中的 PAD/空记录不能当缺省页面坐标样本。
- 证据 `outputs/review/038z3/record-scan.json`。真实 NC 与缺省标记路径仍未覆盖，未修改工程制造样本，也未使用其它工程替代。
