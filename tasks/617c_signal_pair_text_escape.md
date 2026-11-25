# 任务书：617C — 信号配对横放必须给旗/文字逃逸留路

## ① 前因后果

617 未修并留证，617B 已定位：`_signal_pair_body_direction` 是首个可证行为变化点。543d 的 R1/R2 被它强制为 0°，R2 declared 值行堵住 USB1.B4A9；仅 `_signal_pair_body_direction → None` 的对照 F1 得 `ok=True / 1 candidate`，R1/R2=270、USB1=0+mirror。只恢复历史未镜像 USB1 又到 D+/D− 拒因，不能照搬旧指纹。

同一块板的 pinned `tests/test_543k_signal_pair_pose.py` 今天 7 passed，其 `partTexts` 明确 `USB1:left`；543d 的 effective.presentation 没给 USB1 文字侧。推荐的代码侧结构条件因此是：**当宿主有需要水平逃逸的旗座且有 declared 行时，只有 presentation 显式把该宿主文字移到 left/right，才允许 opt-in 信号配对横放；没有该声明就保持原来的竖直回流姿态。** 这不是全局关闭配对，也不是给文字/旗标放宽墙体。

不得修改 effective.presentation 来掩盖缺口；要让未声明的默认输入安全编译。真实 CLI 是最终尺，不再只跑模块探针。

## ② 当前树状态

- HEAD/origin `76e08060ded403793bc6fb0eb64b38f9e140c765`；602–616 改动保留。
- `drawcompiler.py` 当前含 607，SHA `9ded2eb312648dc653c58f7b9720c43ab6a4c4da847dda9f0b387606eac4caf9`；617/617B 未留生产改动。
- `_signal_pair_body_direction` 3688–3753；调用点 3155；`_flag_seats(ctx)` 在 4769 起，提供 owner 上 power/gnd 旗预留（含 part_id/token/net）；`_stated_part_text_side` 在 17284 起。
- 权威证据：`evidence/617b/REPORT.md` §3–5、F1 `falsify_pair_off_side_on.stdout`、F2 `falsify_pair_off_side_off.stdout`、`tests/test_543k_signal_pair_pose.py` 的 pinned payload 与 `USB1:left`。
- 固定输入与 page-box 同 617；真实基线 `.tmp_hole570_fix/h2/replay.log` 为 0 候选。
- 他人 563/review-line/router/201f/placement/textmetrics 禁触。开始 cp 备份 drawcompiler 到 `.tmp_617c/backup/`。

## ③ 文件域与禁触清单

允许修改/新建仅：
- `src/boardwise/engines/drawcompiler.py`（`_signal_pair_body_direction` 的结构闸及注释）
- `tests/test_617c_signal_pair_text_escape.py`（新）
- 本任务书、`.tmp_617c/`、`.tmp_pt_617c/`、`evidence/617c/`

禁止：effective.presentation、circuit/library、placement/grammar/textmetrics/pagecompiler/readability、CLI/shared/connector/DSH、fixtures、旧断言及他人文件。不得调页框/budget/GAP/reach、删文字/墙、改 USB1 合法姿态、全局禁用 543K，或修改 543K 的 pinned 期望。不得新增第二套座位/文本子系统。

## ④ 交付物与验收

### 最小实现与因果测试

1. 在 `_signal_pair_body_direction` 已判出水平配对后、return 前检查该 owner 的 `_flag_seats(ctx)`：若 owner 有旗座且有 declared 行，而 `_stated_part_text_side(ctx, owner.part_id)` 不是明确的 `left/right`，返回 None，让既有 `_branch_body_direction` 接管。声明 left/right 才返回水平方向。无旗座、无 declared 行、其它既有早退保持不变。
2. declared 行必须经现有 `textmetrics.symbol_rows`/对应 helper 读取，不能按 part id 猜；只需要布尔“是否有行”，不计算坐标或新阈值。若现有 helper 需要 pose，使用 accepted owner pose，不能创造新姿态。若实测 owner 无行，不阻止横放。
3. 快速回归先红：543d 的 R1/R2 在该闸下准备为竖直；543K 的 `USB1:left` 仍返回 `(1,0)` 且横放；无旗座/无 declared 行的合成结构不被误伤；one-key-alone 保持旧行为。断言必须能区分“有声明才允许横放”，不是只测 pair off。
4. **真实 CLI 先红/修后**：固定三件输入与 page-box，当前 0 候选；修后至少 1 个合法 page candidate。记录候选数、geometry/provenance 与历史差异，不能要求恰好 4 个或重钉 `85995cd…`。F1 的模块级 1 候选是预测证据，不替代真实 CLI。
5. 对所有产出 page candidate 做 loader/可读性与逐脚独立复核，记录 P1–P4；首选渲染到 `evidence/617c/`，主代理必须能目检 USB/CC/CH343/LED 的功能关系与标签。543K 全文件 7 passed 不得减少，另跑 543D/543G/543I/543H/607 邻域与 owner/layer，不跑全量。
6. 至少两项生产变异：① 删除“旗座+declared 行+无文字侧”闸，543d 回到 0 候选；② 闸误判 `USB1:left` 仍禁止横放，543K 的结构/完整 pinned 测试必须红。每项 cp+SHA 恢复并复绿。若真实 CLI 只在修后出候选，先红可由当前基线 + 变异共同证明，不伪造测试历史。

### 兼容矩阵

- 543d 未声明文字侧 → 默认竖直、合法候选。
- 543K 显式 `USB1:left` → 原横放配对、成对一致性不变。
- 无旗座/无 declared 行/单 opt-in key → 原行为不变。
- 真机、V3/V4 宿主、真实容器、多板/CBB 未覆盖；只签本离线 replay 的三关，不宣称任意电路。

## ⑤ 纪律与红线

零 git 写/移动/删除；禁 rm/unlink 和 git checkout/restore/worktree；不全量、不真机、不部署。pytest 独立 basetemp、单进程、命令 timeout。不得改输入/调参/删墙/强制未镜像/放宽 room/ruler，不把 F1 的模块绿当完整页绿。同一拒因搬家两轮无新证据即停止，不续试参数。

## ⑥ 预算与交卷格式

一个 coder，最多 40 步或 30 分钟；不派下级。交卷 ≤2000字，含结构闸、快速/真实先红与修后、候选数与逐脚/P1–P4、完整测试汇总、两项变异与 SHA 恢复、渲染路径和未覆盖项。证据落 `evidence/617c/`。缺真实候选、543K 负控或渲染只能写「停止/未完成」。
