# 任务书：620C — 不放宽 10 单位合同的 RXD/服务座位修复

## ① 前因后果

617D 把 `_native_label_seat` 的外来导线净距从 `NATIVE_LABEL_CARRIER_LIMIT=10` 降为 `FLAG_BODY_CLEARANCE=5`，使 RXD 近座可用，但全量新增 `tests/test_534z_label_carriers.py::test_a_candidate_seat_clears_a_foreign_conductor`：近座被返回且距他网导线不足 10。这是本系列引入的真实回归，不能靠修改该既有测试或保留 5 单位绕过。

目标是同时满足：① 534z 原有 10 单位合同恢复并通过；② RXD 仍比旧 96 更短、在自身引脚外侧、不压 C3 位号/器件体；③ 合法候选保留，逐脚/视觉不退化。必须先恢复 10，再用现有服务座位/标签梯级解决占位，不能用“近座无合法解就放宽”关闭。

## ② 当前树状态

- HEAD/origin `76e08060ded403793bc6fb0eb64b38f9e140c765`；602–620A 改动保留。
- 全量 `.tmp_620_full_pytest.log`：`11 failed / 12953 passed / 26 skipped / 2 xfailed`，其中 9 条既有基线，新增 590 API 与 534z 两条。590 另批 shared 处理。
- `pagecompiler.py` 当前 `b5ffebaf…`，`_native_label_seat` 的 `gap_limit` 被 617D 改错；`drawcompiler.py` 当前 `c5c6da70…`。
- 617E 当前候选 C3 位于 (590,725)，V3 线段含 `(605,725)-(635,725)`；RXD anchor=(635,735)，617D 的盒 `(603,730.5)-(627,739.5)`，与 V3 仅 5.5。现有 534z 用例明确钉 10。
- `tests/test_617d_rxd_label_carrier.py` 已加固 stub<96、外向侧、不得压体、C3 gap≥2，不能删改宽。
- 他人 563/review-line/router/201f 与临时文件禁触。开始分别 cp 备份 pagecompiler/drawcompiler 到 `.tmp_620c/backup/`。

## ③ 文件域与禁触清单

允许修改/新建仅：
- `src/boardwise/engines/pagecompiler.py`（恢复原外来导线净距及必要的重座逻辑）
- `src/boardwise/engines/drawcompiler.py`（仅当必须调整既有服务座位时的最小 hunk）
- `tests/test_620c_rxd_clearance.py`（新）
- 本任务书、`.tmp_620c/`、`.tmp_pt_620c/`、`evidence/620c/`

禁止：534z/617D/617E/543K 既有断言、规格/library/CLI/shared/connector/DSH、fixtures、placement/router/readability/textmetrics、他人文件。不得把 10 改 5、把 NATIVE_LABEL_CARRIER_LIMIT 改名换义、隐藏文字、删除 C3、扩大页框/stubMin/GAP/预算，不新增第二套座位器。若只需 pagecompiler 即可，不改 drawcompiler；若必须动服务座位，优先复用现有梯级。

## ④ 交付物与验收

### 基线与最小实现

1. 先恢复 `gap_limit = NATIVE_LABEL_CARRIER_LIMIT` 并跑 534z 证明恢复合同；随后修座位，不能通过把 `flag_body_clearance` 当作他网净距。
2. 捕获 RXD 的候选梯级和占用：找出能同时满足“距他网导体 ≥10、外向侧、stub<96、C3 gap≥2”的合法座位。若没有，使用**既有服务座位梯级**调整服务件位置/文字，复用原路由/占位和电气校验；不得写死 C3 坐标或 part id 特判。移动后服务连接仍逐脚一致，新增绕行必须有记账且合理。
3. 新回归先红：当前 5 单位回归必须被 534z 和 RXD 断言抓住；修后所有候选满足净距、stub、外向侧、C3 净空，不能靠 0 候选或隐藏标签通过。
4. 真实 CLI 保持 `ok=True`、至少一个合法候选，58 脚/17 网不变；RXD stub<96、与 C3 位号 gap≥2，且外来导体净距≥10。逐项打印 seat、stub、foreign gap、C3 gap、服务连接。
5. 543K pinned、534z 全文件、617C/D/E、543D/G/I 邻域通过；既有 543e/543h3b 基线红按原名披露，不重钉。渲染到 `evidence/620c/`，主代理必须看 C3/RXD 与相邻导线。
6. 至少两项生产变异：① 净距再降 5，534z 必须红；② 禁用新服务座位/重排路径，RXD 的合法近座或净空必须红。每项 cp+SHA 恢复并复绿。不得为凑绿改 534z 或 617D 断言。

### 兼容矩阵

- 534z 原合同、543d/RXD、617E agent-adjusted 页面、543K pinned 横放对照。
- 真机、V3/V4、真实容器、多板/CBB 未覆盖；本批只签这两个具体合同与离线 replay，不泛化任意标签布局。

## ⑤ 纪律与红线

零 git 写/移动/删除；禁 rm/unlink 和 git checkout/restore；不全量（修后仅允许集成轮复跑）、不真机、不部署。pytest 独立 basetemp、单进程、命令 timeout。不得降低既有净距/可读性标准，不改测试、输入或隐藏冲突，不把新拒绝当完成。两轮同拒无新证据即停。

## ⑥ 预算与交卷格式

一个 coder，最多 40 步或 30 分钟；不派下级。交卷 ≤2000字，含 534z 恢复证据、座位/梯级、先红/修后净距/stub/C3 gap、真实 CLI 与逐脚、完整测试汇总、两项变异与 SHA 恢复、渲染和未覆盖项。证据落 `evidence/620c/`。缺任一合同或渲染只能写「停止/未完成」。
